"""The organic edit and its delivery files (Task 16): the handoff's OrganicCaptions composition in the plugin's Remotion
project, `tm tool deliver`'s refusals (speed cap, the 15 MB upload stop, never overwriting) and the G1/G2 step
checks `final_checked` (tm.organic_final) and `kit_checked` (tm.kit). The tool's ffmpeg work is proven in
tests/tools/test_deliver.py; the real OrganicCaptions render of ExampleEdu M5 PL runs only with `-m video`."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import typing
from datetime import date
from pathlib import Path

import exampleedu
import pytest
from conftest import remotion_cache, video_asked_for

from tm import config, flow, kit, organic_config, organic_final, render, state, stepchecks
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import _common as common
from tm.tools import deliver

PLUGIN = Path(__file__).resolve().parents[2]
REPO = PLUGIN.parents[1]
REMOTION = PLUGIN / "remotion" / "src"
HANDOFF_REMOTION = REPO / "handoff" / "organic-video_v02" / "tools" / "remotion" / "src"
TOO_LONG = "The video is too long for the page's 15 MB download; it stays a local file."
GOOD = {"width": 1080, "height": 1920, "vcodec": "h264", "acodec": "aac", "sample_rate": 48000, "lufs": -14.2}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _blocks(root: str) -> dict[str, str]:
    """Each `<Composition ... />` of a Root.tsx, by its id."""
    return {re.search(r'id="(\w+)"', b).group(1): b
            for b in re.findall(r"<Composition\n.*?\n  />", root, re.S)}


@pytest.fixture
def ov(tmp_path):
    """A production run for ExampleEdu's M5 (state.organic.proposal), with the organic config."""
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.organic = {"proposal": "M5", "channel": "exampleedu"}
    state.save(run, s)
    config.save(run, organic_config.defaults())
    return run


def _tool(capsys, *argv) -> tuple[int, dict]:
    code = deliver.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _final(run: RunFolder, version: int = 1) -> Path:
    path = run.path / "04_final" / f"M5_final_v{version:02d}.mp4"
    path.write_bytes(b"final picture and sound" + bytes([version]))
    return path


# --- the composition --------------------------------------------------------------------------------

@pytest.mark.private_data
def test_organic_captions_registered():
    """The handoff's OrganicCaptions.tsx, grown in the plugin (the fonts of issue 3, the two text layers of issue 89)
    with the handoff's safe zone and every prop it had, and its <Composition> from the handoff's Root.tsx; refresh-ad's
    two stay (the handoff's quiz and rankings follow, Task 20: test_organic_sections)."""
    ours, handoff = _text(REMOTION / "OrganicCaptions.tsx"), _text(HANDOFF_REMOTION / "OrganicCaptions.tsx")
    safe = next(line for line in handoff.splitlines() if line.startswith("export const SAFE_1080"))
    assert safe in ours.splitlines()
    for prop in re.findall(r"^  (\w+)\??:", handoff, re.M):
        assert re.search(rf"^  {prop}\??:", ours, re.M), prop
    root, original = _text(REMOTION / "Root.tsx"), _text(HANDOFF_REMOTION / "Root.tsx")
    ours, theirs = _blocks(root), _blocks(original)
    assert list(ours)[:3] == ["HookSwap", "WordCaptions", "OrganicCaptions"]
    assert all(ours[name] == theirs[name] for name in ours)
    assert ('import { OrganicCaptions, OrganicCaptionsProps, organicCaptionsDefaults, totalSeconds } from '
            '"./OrganicCaptions";') in root
    assert render.COMPS[:3] == ("HookSwap", "WordCaptions", "OrganicCaptions")
    assert typing.get_args(render.Comp) == render.COMPS
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "plugins/trendsmesh-playbooks/remotion/src/OrganicCaptions.tsx text eol=lf" in lines


@pytest.mark.private_data
def test_organic_props_name_files_inside_the_run(tmp_path):
    """M5 PL's edit props pass once its take is in the run; a segment, music or voice file outside it is refused."""
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    props = exampleedu.edit_props()
    path = run.path / "03_wip" / "edit_v02.props.json"
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(common.ToolError, match="M5_pl/take_v01_0.mp4"):
        render._check_props(run, "OrganicCaptions", path)
    (run.path / "M5_pl").mkdir()
    (run.path / "M5_pl" / "take_v01_0.mp4").write_bytes(b"take")
    assert render._check_props(run, "OrganicCaptions", path)["segments"][0]["end"] == 15.0
    for bad in ({"music": {"src": "../music.mp3", "volume": 0.2}},
                {"audioTracks": [{"src": "/tmp/vo.mp3", "from": 0, "volume": 1}]}):
        path.write_text(json.dumps({**props, **bad}), encoding="utf-8")
        with pytest.raises(common.ToolError, match="inside the run folder"):
            render._check_props(run, "OrganicCaptions", path)


# --- tm tool deliver: what it refuses ------------------------------------------------------------------

def test_speed_capped_at_1_25(ov, capsys):
    take = ov.path / "03_wip" / "take_v01_0.mp4"
    take.write_bytes(b"take")
    code, out = _tool(capsys, "speed", "--run", str(ov.path), "03_wip/take_v01_0.mp4", "--factor", "1.3")
    assert (code, out["status"]) == (2, "stop")
    assert "×1.3" in out["message"] and "×1.25" in out["message"]
    cfg = organic_config.defaults()
    cfg["qa"]["speed_max"] = 1.1   # the run's own cap is read
    config.save(ov, cfg)
    code, out = _tool(capsys, "speed", "--run", str(ov.path), "03_wip/take_v01_0.mp4", "--factor", "1.2")
    assert code == 2 and "×1.1" in out["message"]
    code, out = _tool(capsys, "speed", "--run", str(ov.path), "03_wip/take_v01_0.mp4", "--factor", "0.9")
    assert code == 1 and "above 1" in out["message"]
    assert sorted(p.name for p in take.parent.iterdir()) == ["take_v01_0.mp4"]


def test_upload_copy_stops_over_15mb(ov, capsys, monkeypatch):
    final = _final(ov)
    tried = []

    def encode(src, part, crf):
        tried.append(crf)
        part.write_bytes(b"copy")

    monkeypatch.setattr(deliver, "_encode_upload", encode)
    monkeypatch.setattr(deliver, "_size", lambda path: 16_000_000)
    code, out = _tool(capsys, "upload", "--run", str(ov.path), "04_final/M5_final_v01.mp4")
    assert (code, out["status"], out["message"]) == (2, "stop", TOO_LONG)
    assert tried == [26, 27, 28]
    assert sorted(p.name for p in final.parent.iterdir() if p.is_file()) == ["M5_final_v01.mp4"]
    over = state.load(ov).checked[organic_final.UPLOAD_OVER]
    assert (over["file"], over["sha256"], over["crf"]) == ("04_final/M5_final_v01.mp4", stepchecks.sha256(final), 28)


def test_upload_copy_takes_the_first_crf_under_the_limit(ov, capsys, monkeypatch):
    _final(ov)
    sizes = {26: 15_200_000, 27: 14_990_000, 28: 13_000_000}
    monkeypatch.setattr(deliver, "_encode_upload", lambda src, part, crf: part.write_bytes(bytes([crf])))
    monkeypatch.setattr(deliver, "_size", lambda path: sizes[path.read_bytes()[0]])
    code, out = _tool(capsys, "upload", "--run", str(ov.path), "04_final/M5_final_v01.mp4")
    assert (code, out["outputs"], out["crf"]) == (0, ["04_final/M5_final_v01_upload.mp4"], 27)
    assert (ov.path / "04_final" / "M5_final_v01_upload.mp4").read_bytes() == bytes([27])
    assert organic_final.UPLOAD_OVER not in state.load(ov).checked


@pytest.mark.parametrize("action,given,taken", [
    ("speed", "03_wip/take_v01_0.mp4", "03_wip/take_v01_0_speed120.mp4"),
    ("upload", "04_final/M5_final_v01.mp4", "04_final/M5_final_v01_upload.mp4"),
    ("preview", "04_final/M5_final_v01.mp4", "showcase/M5_final_v01_720p.mp4"),
    ("cover", "04_final/kits/cover_M5_v01.png", "04_final/kits/cover_M5_v01.jpg"),
    ("nosound", "04_final/M5_final_v01.mp4", "04_final/M5_final_v01_nosound.mp4"),
])
def test_never_overwrites(ov, capsys, monkeypatch, action, given, taken):
    for name in ("03_wip/take_v01_0.mp4", "04_final/M5_final_v01.mp4", "04_final/kits/cover_M5_v01.png"):
        (ov.path / name).parent.mkdir(parents=True, exist_ok=True)
        (ov.path / name).write_bytes(b"input")
    (ov.path / taken).parent.mkdir(parents=True, exist_ok=True)
    (ov.path / taken).write_bytes(b"made earlier")

    def never(*args, **kwargs):
        raise AssertionError("ffmpeg ran")

    monkeypatch.setattr(deliver.subprocess, "run", never)
    extra = ["--factor", "1.2"] if action == "speed" else []
    code, out = _tool(capsys, action, "--run", str(ov.path), given, *extra)
    assert code == 1 and "never overwritten" in out["message"] and taken in out["message"].replace("\\", "/")
    assert (ov.path / taken).read_bytes() == b"made earlier"


def test_finish_writes_the_next_version(ov):
    _final(ov, 1)
    assert deliver.final_path(ov, "M5") == ov.path / "04_final" / "M5_final_v02.mp4"
    with pytest.raises(common.ToolError, match="letters, digits"):
        deliver.final_path(ov, "../M5")


# --- the step checks ---------------------------------------------------------------------------------

def test_final_gap_names_what_is_missing(ov, monkeypatch):
    seen = {}
    monkeypatch.setattr(organic_final, "_probe", lambda path: seen.setdefault("probe", GOOD))
    assert "04_final/M5_final_vNN.mp4" in stepchecks.run("final_checked", ov)
    final = _final(ov)
    seen["probe"] = {"width": 768, "height": 1344, "vcodec": "hevc", "acodec": "mp3", "sample_rate": 44100,
                     "lufs": -16.6}
    gap = stepchecks.run("final_checked", ov)
    for said in ("04_final/M5_final_v01.mp4", "1080×1920 (it is 768×1344)", "H.264 (it is hevc)",
                 "AAC 48 kHz (it is mp3 44100 Hz)", "−14 LUFS ±1 (it is −16.6)", "upload copy under 15 MB",
                 "tm tool deliver upload", "cover JPG", "04_final/kits/cover_M5_vNN.jpg"):
        assert said in gap, said
    seen["probe"] = GOOD
    upload = final.with_name("M5_final_v01_upload.mp4")
    upload.write_bytes(b"copy")
    (ov.path / "04_final" / "kits").mkdir()
    (ov.path / "04_final" / "kits" / "cover_M5_v01.jpg").write_bytes(b"jpg")
    assert stepchecks.run("final_checked", ov) is None
    monkeypatch.setattr(organic_final, "_size", lambda path: 15_000_000)
    assert "it is 15.0 MB" in stepchecks.run("final_checked", ov)
    monkeypatch.setattr(organic_final, "_size", lambda path: 14_999_999)
    # no copy, and the over-limit stop recorded for this final: it stays a local file
    upload.unlink()
    stepchecks.mark(ov, organic_final.UPLOAD_OVER, final, extra={"crf": 28})
    assert stepchecks.run("final_checked", ov) is None
    # a newer final needs its own copy, cover (Task 16 review M3) and loudness
    newer = _final(ov, 2)
    os.utime(newer, (newer.stat().st_mtime + 60, newer.stat().st_mtime + 60))   # made after the v01 cover
    gap = stepchecks.run("final_checked", ov)
    assert "M5_final_v02.mp4" in gap and "upload copy" in gap and "cover_M5_v01.jpg is older than it" in gap
    newer.with_name("M5_final_v02_upload.mp4").write_bytes(b"copy")
    cover_v02 = ov.path / "04_final" / "kits" / "cover_M5_v02.jpg"
    cover_v02.write_bytes(b"jpg")
    os.utime(cover_v02, (newer.stat().st_mtime, newer.stat().st_mtime))
    assert stepchecks.run("final_checked", ov) is None


def test_final_gap_reads_the_asmr_target_from_the_finish_record(ov, monkeypatch):
    final = _final(ov)
    final.with_name("M5_final_v01_upload.mp4").write_bytes(b"copy")
    (ov.path / "04_final" / "kits").mkdir()
    (ov.path / "04_final" / "kits" / "cover_M5_v01.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(organic_final, "_probe", lambda path: {**GOOD, "lufs": -16.3})
    assert "−14 LUFS ±1 (it is −16.3)" in stepchecks.run("final_checked", ov)
    common.record(ov, final, "tm tool deliver finish", request={"action": "finish", "lufs_target": -16, "asmr": True})
    assert stepchecks.run("final_checked", ov) is None


def test_final_gap_needs_the_runs_idea(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    assert "tm organic start" in stepchecks.run("final_checked", run)
    assert "tm organic start" in stepchecks.run("kit_checked", run)


def test_kit_checked_is_the_kit_check_mark(ov):
    assert "04_final/kits/M5_kit_vNN.json" in stepchecks.run("kit_checked", ov)
    path = ov.path / "04_final" / "kits" / "M5_kit_v01.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"id": "M5"}), encoding="utf-8")
    assert "tm kit check" in stepchecks.run("kit_checked", ov)
    stepchecks.mark(ov, kit.KEY, path)
    assert stepchecks.run("kit_checked", ov) is None
    path.write_text(json.dumps({"id": "M5", "changed": True}), encoding="utf-8")
    assert "changed after it was checked" in stepchecks.run("kit_checked", ov)


def test_steps_require_the_checks():
    steps = {s.id: s for s in flow.steps(ORGANIC_VIDEO)}
    assert steps["G1"].requires == ("final_checked", "sections_covered", "text_followed") and steps["G2"].requires == ("kit_checked",)
    assert stepchecks.NAMES["final_checked"] == "tm.organic_final:final_gap"
    assert stepchecks.NAMES["kit_checked"] == "tm.kit:kit_gap"


# --- the real render (opt-in) -------------------------------------------------------------------------

@pytest.mark.private_data
@pytest.mark.video
def test_real_render_organic_captions(request, tmp_path, tmp_path_factory, monkeypatch):
    """ExampleEdu M5 PL's edit props over a 15 s navy placeholder take: 1080×1920 at 24 fps, 15 s, with sound, the
    white hook box at the top of the safe zone and the navy picture below it."""
    if not video_asked_for(request.config):
        pytest.skip("the real render runs with -m video (pixi run -e dev-full test-video)")
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    sys.path.insert(0, str(Path(__file__).parent / "tools"))
    from _media import ffmpeg, make_clip

    cache = remotion_cache(tmp_path_factory)
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(PLUGIN))
    monkeypatch.setattr(render.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(render, "_prefix", lambda: [])  # already inside an environment with Node
    monkeypatch.setattr(render.envtiers, "installed", lambda tier: True)
    render.setup()
    run = RunFolder.create(tmp_path / "Pulpit Łukasz", "exampleedu m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    props = exampleedu.edit_props()
    for segment in props["segments"]:   # the reference run's public folder was 03_wip; here it is the run folder
        segment["src"] = f"03_wip/{segment['src']}"
        make_clip(run.path / segment["src"], vf="drawbox=x=0:y=0:w=iw:h=ih:color=navy:t=fill",
                  seconds=segment["end"])
    path = run.path / "03_wip" / "M5_pl" / "edit_v02.props.json"
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    out = render.video(run, "OrganicCaptions", path, run.path / "03_wip" / "M5_pl" / "edit_v02_render.mp4")
    info = common.probe(out)
    assert (info["width"], info["height"], info["fps"], info["has_audio"]) == (1080, 1920, 24.0, True)
    assert abs(info["duration"] - 15.0) < 0.1
    frame = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-ss", "1", "-i", str(out), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    assert len(frame) == 1080 * 1920

    def mean(y0, y1, x0=400, x1=680):
        return sum(frame[y * 1080 + x] for y in range(y0, y1) for x in range(x0, x1)) / ((y1 - y0) * (x1 - x0))

    assert mean(261, 268) > 200    # the hook box's white top edge, inside the safe zone (top 260)
    assert mean(900, 1000) < 60     # the navy take in the middle of the frame


# --- the PR C fix wave -----------------------------------------------------------------------------

def _started_m5(tmp_path):
    """ExampleEdu's M5 as `tm organic start` leaves it: the proposals file's id `m5` in run.json and in
    00_raw/proposal.json, its config; the pack (the handoff's spelling, `M5`) is checked."""
    run = exampleedu.build(tmp_path / "ws")
    m5 = next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m5")
    s = state.load(run)
    s.organic = {**(s.organic or {}), "proposal": m5["id"], "channel": exampleedu.CHANNEL}
    state.save(run, s)
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"proposal": m5, "channel": exampleedu.CHANNEL}),
                                                       encoding="utf-8")
    pack = json.loads((Path(__file__).parent / "fixtures" / "organic" / "m5_pl_pack.json").read_text(encoding="utf-8"))
    assert pack["id"] == "M5"
    return run


@pytest.mark.private_data
def test_one_idea_id_in_any_case(tmp_path, capsys, monkeypatch):
    """PR C review I1, Task 18 I2: the engine's id is the proposals file's (`m5`); `--id M5` and `--id m5` are that
    idea and write its spelling, a final or a kit named in another case is found (one name on a case-blind disk), so
    G1 and G2 pass, and a version number is never given twice."""
    run = _started_m5(tmp_path)
    assert organic_final.idea_id(run) == "m5"
    for given in ("M5", "m5"):
        assert deliver.final_path(run, given) == run.path / "04_final" / "m5_final_v01.mp4"
    with pytest.raises(common.ToolError, match="not this run's idea, m5"):
        deliver.final_path(run, "M6")
    # finish --id M5 writes m5_final_v01, which the G1 check finds
    monkeypatch.setattr(deliver, "_has_audio", lambda path: True)
    monkeypatch.setattr(deliver, "_not_vertical", lambda path: None)   # a 9:16 render
    monkeypatch.setattr(deliver, "_first_pass", lambda src, target, *more: {"input_i": -20})
    monkeypatch.setattr(deliver, "_finish", lambda run, src, out, target, m, *more: out.write_bytes(b"the final"))
    monkeypatch.setattr(deliver, "loudness", lambda path: (-14.0, -1.6))
    (run.path / "03_wip" / "render_v01.mp4").write_bytes(b"render")
    code, out = _tool(capsys, "finish", "--run", str(run.path), "03_wip/render_v01.mp4", "--id", "M5")
    assert (code, out["outputs"]) == (0, ["04_final/m5_final_v01.mp4"]), out
    # a final, an upload copy and a cover written by hand in the pack's spelling count too
    legacy = run.path / "04_final" / "M5_final_v02.mp4"
    legacy.write_bytes(b"made by hand")
    assert organic_final.final_of(run, "m5").name == "M5_final_v02.mp4"
    assert deliver.final_path(run, "m5").name == "m5_final_v03.mp4"     # v02 is taken, in any case
    legacy.with_name("M5_final_v02_upload.mp4").write_bytes(b"copy")
    kits = run.path / "04_final" / "kits"
    kits.mkdir(parents=True)
    (kits / "cover_M5_v01.png").write_bytes(b"png")
    monkeypatch.setattr(deliver, "_ffmpeg", lambda args: Path(args[-1]).write_bytes(b"jpg"))
    code, out = _tool(capsys, "cover", "--run", str(run.path), "04_final/kits/cover_M5_v01.png")
    assert (code, out["outputs"]) == (0, ["04_final/kits/cover_m5_v01.jpg"]), out
    monkeypatch.setattr(organic_final, "_probe", lambda path: GOOD)
    assert stepchecks.run("final_checked", run) is None
    # the kit in the pack's spelling, checked under either name, passes G2
    kit_file = kits / "M5_kit_v01.json"
    kit_file.write_text(json.dumps({"id": "M5"}), encoding="utf-8")
    assert "04_final/kits/m5_kit_vNN.json" in stepchecks.run("kit_checked", run)
    s = state.load(run)
    s.checked[kit.KEY] = {"file": "04_final/kits/m5_kit_v01.json", "sha256": stepchecks.sha256(kit_file),
                          "at": "2026-11-08T10:00:00+00:00"}           # as checked with --file …/m5_kit_v01.json
    state.save(run, s)
    assert stepchecks.run("kit_checked", run) is None


# --- the PR C fix wave (Task 16 review M1, M2, M3, M5) ---------------------------------------------

def test_props_segments_and_audio_tracks_must_be_lists(tmp_path):
    """M5: a segments or audioTracks that is no list is a ToolError, never a TypeError."""
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    path = run.path / "03_wip" / "edit_v01.props.json"
    for bad in ({"segments": 5}, {"segments": "take.mp4"}, {"audioTracks": {"src": "vo.mp3"}}, {"music": 3}):
        path.write_text(json.dumps({"segments": [], **bad}), encoding="utf-8")
        with pytest.raises(common.ToolError, match=next(iter(bad))):
            render._check_props(run, "OrganicCaptions", path)
    path.write_text(json.dumps({"segments": [], "audioTracks": None, "music": None}), encoding="utf-8")
    assert render._check_props(run, "OrganicCaptions", path)["segments"] == []


@pytest.mark.parametrize("size,refused", [((1080, 1920), False), ((540, 960), False), ((768, 1344), False),
                                          ((1920, 1080), True), ((1080, 1080), True), ((1080, 1350), True)])
def test_finish_never_stretches_a_picture_that_is_not_9_16(ov, capsys, monkeypatch, size, refused):
    """M2: finish scales to 1080×1920, so a render that is not 9:16 is refused (within 2 %: MiniMax H3's 768×1344,
    4:7, is a vertical take); nothing is written."""
    width, height = size
    monkeypatch.setattr(common, "probe", lambda path: {"has_video": True, "has_audio": True, "is_video": True,
                                                        "width": width, "height": height, "fps": 25.0,
                                                        "frames": 150, "duration": 6.0})
    monkeypatch.setattr(deliver, "_first_pass", lambda src, target, *more: {"input_i": -20})
    monkeypatch.setattr(deliver, "_finish", lambda run, src, out, target, m, *more: out.write_bytes(b"the final"))
    monkeypatch.setattr(deliver, "loudness", lambda path: (-14.0, -1.6))
    (ov.path / "03_wip" / "render_v01.mp4").write_bytes(b"render")
    code, out = _tool(capsys, "finish", "--run", str(ov.path), "03_wip/render_v01.mp4", "--id", "M5")
    if refused:
        assert code == 1 and f"{width}×{height}" in out["message"] and "9:16" in out["message"], out
        assert "never stretch" in out["message"] and not (ov.path / "04_final" / "M5_final_v01.mp4").exists()
    else:
        assert (code, out["outputs"]) == (0, ["04_final/M5_final_v01.mp4"]), out


def _cover(run, capsys, monkeypatch, n=1):
    kits = run.path / "04_final" / "kits"
    kits.mkdir(parents=True, exist_ok=True)
    (kits / f"cover_M5_v{n:02d}.png").write_bytes(b"png")
    monkeypatch.setattr(deliver, "_ffmpeg", lambda args: Path(args[-1]).write_bytes(b"jpg"))
    return _tool(capsys, "cover", "--run", str(run.path), f"04_final/kits/cover_M5_v{n:02d}.png")


def test_the_cover_is_tied_to_the_final_it_was_made_for(ov, capsys, monkeypatch):
    """M3: a cover is made for the latest final (its record names it); G1 and the delivery page take the cover only
    for that final, so a cover of v01 never passes a newer v02."""
    monkeypatch.setattr(organic_final, "_probe", lambda path: GOOD)
    code, out = _cover(ov, capsys, monkeypatch)
    assert code == 1 and "make the final first" in out["message"] and "tm tool deliver finish" in out["message"]
    final = _final(ov)
    final.with_name("M5_final_v01_upload.mp4").write_bytes(b"copy")
    code, out = _cover(ov, capsys, monkeypatch)
    assert (code, out["outputs"]) == (0, ["04_final/kits/cover_M5_v01.jpg"]), out
    cover = ov.path / "04_final" / "kits" / "cover_M5_v01.jpg"
    said = json.loads(cover.with_name("cover_M5_v01.jpg.response.json").read_text(encoding="utf-8"))
    assert said["request"]["final"] == "04_final/M5_final_v01.mp4"
    assert organic_final.cover_of(ov, "M5", final) == cover and stepchecks.run("final_checked", ov) is None
    newer = _final(ov, 2)
    newer.with_name("M5_final_v02_upload.mp4").write_bytes(b"copy")
    assert organic_final.cover_of(ov, "M5", newer) is None
    gap = stepchecks.run("final_checked", ov)
    assert "cover_M5_v01.jpg was made for 04_final/M5_final_v01.mp4" in gap and "tm tool deliver cover" in gap
    assert _cover(ov, capsys, monkeypatch, n=2)[0] == 0
    assert organic_final.cover_of(ov, "M5", newer).name == "cover_M5_v02.jpg"
    assert stepchecks.run("final_checked", ov) is None


def test_a_cover_made_by_hand_counts_when_it_is_not_older_than_the_final(ov, monkeypatch):
    """M3: a cover with no record of its final (made by hand) counts for a final it is not older than."""
    final = _final(ov)
    kits = ov.path / "04_final" / "kits"
    kits.mkdir(parents=True)
    cover = kits / "cover_M5_v01.jpg"
    cover.write_bytes(b"jpg")
    os.utime(final, (cover.stat().st_mtime + 60, cover.stat().st_mtime + 60))   # the final made after it
    assert organic_final.cover_of(ov, "M5", final) is None
    os.utime(cover, (final.stat().st_mtime, final.stat().st_mtime))
    assert organic_final.cover_of(ov, "M5", final) == cover


def test_replace_waits_while_windows_holds_the_file(tmp_path, monkeypatch):
    """M1: os.replace is retried on PermissionError (another process holding the file on Windows), then raised."""
    real, calls = os.replace, []

    def held(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError(13, "The process cannot access the file", str(dst))
        real(src, dst)

    monkeypatch.setattr(os, "replace", held)
    part, target = tmp_path / ".x.part", tmp_path / "x.mp4"
    part.write_bytes(b"video")
    common.replace(part, target)
    assert target.read_bytes() == b"video" and len(calls) == 3
    monkeypatch.setattr(common, "REPLACE_WAIT_S", 0.05)
    monkeypatch.setattr(os, "replace", lambda src, dst: (_ for _ in ()).throw(PermissionError(13, "held")))
    with pytest.raises(PermissionError):
        common.replace(part, target)


def test_deliver_writes_through_the_retrying_replace(ov, capsys, monkeypatch):
    """M1: the final (deliver's _write) and the upload copy go through common.replace."""
    used = []
    real = common.replace
    monkeypatch.setattr(common, "replace", lambda src, dst: used.append(Path(dst).name) or real(src, dst))
    _final(ov)
    monkeypatch.setattr(deliver, "_encode_upload", lambda src, part, crf: part.write_bytes(b"copy"))
    monkeypatch.setattr(deliver, "_size", lambda path: 1_000_000)
    assert _tool(capsys, "upload", "--run", str(ov.path), "04_final/M5_final_v01.mp4")[0] == 0
    assert "M5_final_v01_upload.mp4" in used
    _cover(ov, capsys, monkeypatch)
    assert "cover_M5_v01.jpg" in used
