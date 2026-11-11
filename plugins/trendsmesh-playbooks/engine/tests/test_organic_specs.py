"""The generation guard of organic video (OV5, OV6, OV8, OV9, OV10): `organic_specs.check` on Replicate
specs typed from the handoff's examples (ExampleEdu M5 and its voice-reference test), and `organic_specs.guard`
through `tm tool replicate_run`: never an automatic video redo, one automatic image redo at a rule level,
an unfinished paid take resumed and never run again, and nothing spent on a refusal. Refresh-ad has no
pre-check. No network, no spend: the tool's child process is faked, ffprobe is monkeypatched."""

import copy
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import tm.tools as tools
from tm import organic_pack, organic_specs, state
from tm.cli import main
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO, REFRESH_AD
from tm.runfolder import RunFolder
from tm.tools import _common

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "organic"
TOKEN = "r8_TEST_token_never_printed_0123456789"
PNG = b"\x89PNG\r\n\x1a\n fake image bytes"
# ExampleEdu M5 PL: the host image (03_wip/M5_pl/host_v01.json) and the take (take_v01.json), typed, the prompts made up.
HOST = {"model": "openai/gpt-image-2",
        "input": {"prompt": "Natural light, no filter. A still that looks like a selfie video, caught mid-sentence …",
                  "quality": "high", "aspect_ratio": "1152x2048", "output_format": "png", "number_of_images": 2}}
TAKE = {"model": "minimax/h3",
        "input": {"prompt": "Task: a phone-shot clip in which a dad chats to the lens at the kitchen table …",
                  "first_frame_image": "host_v01_0.png", "duration": 15, "resolution": "768P"}}
# ExampleEdu's voice-reference test (03_wip/voiceref/vref_pl_v01.json): reference mode, host image + voice sample.
VREF = {"model": "minimax/h3",
        "input": {"prompt": "Task: a phone-shot clip in which the same dad chats to the lens at the kitchen table …",
                  "reference_image_urls": ["host_v01_0.png"], "reference_audio_urls": ["audio/m1_vo_v01.mp3"],
                  "ratio": "9:16", "duration": 15, "resolution": "768P"}}


def _norm(text):
    return text.replace("\\", "/")


def _pack():
    return json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))


def _check_pack(run, pack, n=1, *, yes=True):
    """Write pack_vNN.json and record it as `tm organic pack check --stage pack` does after a pass; with `yes`, the
    user's yes at the pack check-in is recorded after it (a re-plan's `--change`)."""
    path = run.path / "03_wip" / f"pack_v{n:02d}.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="pack")
    if yes:
        _yes(run)
    return path


def _replanned(run, pack, n):
    """`_check_pack`, dated a minute on, so the re-check is strictly after every earlier pick (never a same-second
    tie): a pick counts only when made after the pack check that last changed its item, so a re-plan that prices a
    redo stales only the redone item's picks (part 3's ruling). Returns a time after the re-check, for picks made
    again."""
    _check_pack(run, pack, n=n)
    s = state.load(run)
    later = datetime.now(timezone.utc) + timedelta(minutes=1)
    s.checked["pack"]["at"] = later.isoformat(timespec="seconds")
    state.save(run, s)
    return (later + timedelta(minutes=1)).isoformat(timespec="seconds")


def _with_redo(pack, item, n=1):
    """The pack with `n` redo lines of `item`, each priced like the item's own line, in its total (PR C review I4)."""
    pack = copy.deepcopy(pack)
    line = next(x for x in pack["cost"]["lines"] if x["item"] == item and not x.get("redo"))
    for _ in range(n):
        pack["cost"]["lines"].append({**line, "what": f"{line['what']} (redo)", "redo": True})
        pack["cost"]["totals"]["ai_usd"] = round(pack["cost"]["totals"]["ai_usd"] + line["cost"], 2)
    return pack


def _yes(run):
    """The user's yes at "Approve the generation pack and its cost", now (as `tm decide pack approve` records it)."""
    s = state.load(run)
    s.decisions.append({"checkin": "pack", "choice": "approve", "by": "user",
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    state.save(run, s)


@pytest.fixture
def ov(tmp_path):
    """An organic-video production run at Hands-off with M5's checked pack, the user's yes to it, its host image file
    and $5 approved."""
    run = RunFolder.create(tmp_path / "ws", "m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.level, s.outputs, s.budgets = "hands_off", ["organic_video"], {"ai_usd": 5.0}
    state.save(run, s)
    _check_pack(run, _pack())
    (run.path / "03_wip" / "host_v01_0.png").write_bytes(PNG)
    return run


def _level(run, level):
    s = state.load(run)
    s.level = level
    state.save(run, s)


def _spec(run, name, spec):
    path = run.path / "03_wip" / f"{name}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return path


def _record(run, stem, n, *, status="done", prediction_id="p1"):
    path = run.path / "03_wip" / f"{stem}_v{n:02d}.run.json"
    path.write_text(json.dumps({"model": "m", "status": status, "prediction_id": prediction_id, "outputs": []}),
                    encoding="utf-8")
    return path


def _pick(run, file, name="host", at=None):
    """One images-stage row of 03_wip/az_log.jsonl, as Task 15's `tm organic pick` writes it, made now (after the pack
    check) unless `at` says when; the file is an output of the item's first Replicate record, as a pick's must be."""
    record = run.path / "03_wip" / f"{name}_v01.run.json"
    made = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {
        "model": "openai/gpt-image-2", "status": "done", "prediction_id": "p0", "outputs": []}
    if Path(file).name not in made["outputs"]:
        made["outputs"].append(Path(file).name)
        record.write_text(json.dumps(made), encoding="utf-8")
    row = {"stage": "images", "name": name, "file": file, "rubric": {"face": 5, "frame": 4},
           "reason": "the sharper face, the phone frame", "by": "rule",
           "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(run.path / organic_specs.AZ_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _probe(seconds):
    return lambda path: {"has_video": False, "has_audio": True, "is_video": False, "duration": seconds}


class Child(list):
    """The fake child's calls, the status of the record it reserves, and what it reports about money."""
    status = "done"
    report = {"spent": True, "actual": None}   # Replicate: the actual cost is not known


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """`tm tool` with its child faked: the child reserves its record as replicate_run does (status done)."""
    root, data = tmp_path / "plugin root", tmp_path / "plugin data"
    (root / "env").mkdir(parents=True)
    data.mkdir()
    (data / "secrets.env").write_text(f"REPLICATE_API_TOKEN={TOKEN}\n")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setattr(tools.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(tools.paths, "pixi_env", lambda: {"PIXI_HOME": "h"})
    monkeypatch.setattr(tools.envtiers, "installed", lambda tier: True)
    calls = Child()

    def fake_run(argv, **kw):
        calls.append(argv)
        args = argv[argv.index("-m") + 2:]
        if "--resume" not in args:
            run = RunFolder.open(Path(args[args.index("--run") + 1]))
            stem = _common.stem_of(args[args.index("--name") + 1])
            run.next_version("wip", stem, "run.json").write_text(
                json.dumps({"model": "m", "status": calls.status, "prediction_id": f"p{len(calls)}", "outputs": []}),
                encoding="utf-8")
        Path(kw["env"]["TM_COST_REPORT"]).write_text(json.dumps(calls.report))
        return subprocess.CompletedProcess(argv, 0 if calls.status == "done" else 1, stdout="{}\n")

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    return calls


def _tool(capsys, run, spec, name, cost="1.04"):
    capsys.readouterr()
    code = main(["tool", "replicate_run", "--run", str(run.path), str(spec), "--name", name, "--cost", cost, "--json"])
    out = capsys.readouterr().out.strip().splitlines()
    return code, (json.loads(out[-1]) if out else None)


# --- the specs ------------------------------------------------------------------------------------

def _voice_ref(pack):
    """The pack with the user's request for a voice reference (OV7: on request only)."""
    pack = copy.deepcopy(pack)
    pack["speech"]["voice_reference"] = {"user_words": "Użyj mojego głosu z nagrania", "sample_s": 14}
    return pack


def test_h3_first_frame_with_reference_refused_e006(ov, monkeypatch):
    monkeypatch.setattr(_common, "probe", _probe(14.0))
    _pick(ov, "03_wip/host_v01_0.png", at=_replanned(ov, _voice_ref(_pack()), n=2))
    (ov.path / "03_wip" / "audio").mkdir()
    (ov.path / "03_wip" / "audio" / "m1_vo_v01.mp3").write_bytes(b"ID3 fake")
    path = _spec(ov, "vref", VREF)
    assert organic_specs.check(ov, VREF, path, name="take") == []        # ExampleEdu's reference mode passes
    spec = copy.deepcopy(VREF)
    spec["input"]["first_frame_image"] = "host_v01_0.png"
    problems = organic_specs.check(ov, spec, _spec(ov, "vref_ff", spec), name="take")
    assert "H3 refuses a first frame with reference media (E006)" in problems
    spec = copy.deepcopy(VREF)
    del spec["input"]["ratio"]
    problems = organic_specs.check(ov, spec, _spec(ov, "vref_ratio", spec), name="take")
    assert any('ratio: "9:16"' in p for p in problems), problems


def test_h3_audio_ref_over_15s_refused(ov, monkeypatch):
    """ExampleEdu vref_pl_v01: the voice sample was 24 s, and H3 takes 2–15 s."""
    seen = []
    monkeypatch.setattr(_common, "probe", lambda p: seen.append(Path(p).name) or _probe(24.0)(p))
    _pick(ov, "03_wip/host_v01_0.png")
    (ov.path / "03_wip" / "audio").mkdir()
    (ov.path / "03_wip" / "audio" / "m1_vo_v01.mp3").write_bytes(b"ID3 fake")
    problems = organic_specs.check(ov, VREF, _spec(ov, "vref", VREF), name="take")
    assert seen == ["m1_vo_v01.mp3"]
    assert any("m1_vo_v01.mp3" in p and "24" in p and "2–15 s" in p for p in problems), problems


def test_a_voice_reference_only_when_the_pack_holds_the_users_request(ov, monkeypatch):
    """PR C review Minor 2 (OV7): a voice reference is sent only when the checked pack's speech.voice_reference holds
    the user's words; M5's pack has none."""
    monkeypatch.setattr(_common, "probe", _probe(14.0))
    _pick(ov, "03_wip/host_v01_0.png")
    (ov.path / "03_wip" / "audio").mkdir()
    (ov.path / "03_wip" / "audio" / "m1_vo_v01.mp3").write_bytes(b"ID3 fake")
    problems = organic_specs.check(ov, VREF, _spec(ov, "vref", VREF), name="take")
    assert len(problems) == 1 and "reference_audio_urls is a voice reference" in problems[0], problems
    assert "speech.voice_reference" in problems[0] and "only when the user asks" in problems[0]
    _pick(ov, "03_wip/host_v01_0.png", at=_replanned(ov, _voice_ref(_pack()), n=2))   # the user asked; re-planned
    assert organic_specs.check(ov, VREF, _spec(ov, "vref", VREF), name="take") == []


def test_an_items_local_inputs_are_the_runs_or_the_packs_packshots(ov, tmp_path):
    """PR C review Minor 2: an image item's inputs are checked too: a file outside the run is refused unless it is a
    packshot the checked pack names."""
    outside = tmp_path / "Downloads" / "someone.png"
    outside.parent.mkdir()
    outside.write_bytes(PNG)
    spec = copy.deepcopy(HOST)
    spec["input"]["input_images"] = [str(outside)]
    problems = organic_specs.check(ov, spec, _spec(ov, "host", spec))
    assert len(problems) == 1 and "input_images is" in problems[0] and "outside this run" in problems[0], problems
    assert "someone.png" in _norm(problems[0])
    (ov.path / "03_wip" / "anchor_v01_0.png").write_bytes(PNG)
    spec["input"]["input_images"] = ["anchor_v01_0.png", str(ov.path / "03_wip" / "host_v01_0.png")]
    assert organic_specs.check(ov, spec, _spec(ov, "host", spec)) == []   # the run's own files
    shot = ov.path.parents[2] / "library" / "brands" / "store" / "packshot_mug_v01.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(PNG)
    spec["input"]["input_images"] = [str(shot)]
    assert organic_specs.check(ov, spec, _spec(ov, "host", spec)) != []   # not named by the pack yet
    pack = _pack()
    pack["product"] = {"level": "incidental", "packshots": ["library/brands/store/packshot_mug_v01.png"]}
    _check_pack(ov, pack, n=2)
    assert organic_specs.check(ov, spec, _spec(ov, "host", spec)) == []


def test_h3_duration_and_resolution_are_the_packs(ov):
    _pick(ov, "03_wip/host_v01_0.png")
    spec = copy.deepcopy(TAKE)
    assert organic_specs.check(ov, spec, _spec(ov, "take", spec)) == []
    spec["input"].update(duration=20, resolution="1080P")
    problems = organic_specs.check(ov, spec, _spec(ov, "take", spec))
    assert any("duration" in p and "15" in p for p in problems), problems
    assert any("1080P" in p and "768p" in p for p in problems), problems


def test_png_required_for_gpt_image_2(ov):
    assert organic_specs.check(ov, HOST, _spec(ov, "host", HOST)) == []
    spec = copy.deepcopy(HOST)
    spec["input"]["output_format"] = "webp"
    spec["input"]["quality"] = "medium"
    problems = organic_specs.check(ov, spec, _spec(ov, "host", spec))
    assert any('output_format: "png"' in p for p in problems), problems
    assert any('quality: "high"' in p and "face" in p for p in problems), problems   # the M5 host item is a face


def test_evidence_clip_as_input_refused(ov):
    _pick(ov, "03_wip/host_v01_0.png")
    clip = ov.path / "02_research" / "videos" / "7514_clip.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake mp4")
    spec = copy.deepcopy(TAKE)
    spec["input"].pop("first_frame_image")
    spec["input"]["reference_video_urls"] = ["../02_research/videos/7514_clip.mp4"]
    spec["input"]["ratio"] = "9:16"
    problems = organic_specs.check(ov, spec, _spec(ov, "take", spec))
    assert any("organic clips are evidence, never footage" in p and "02_research/videos/7514_clip.mp4" in _norm(p)
               for p in problems), problems


def test_video_input_must_be_a_picked_image(ov):
    path = _spec(ov, "take", TAKE)
    problems = organic_specs.check(ov, TAKE, path)
    assert any("03_wip/host_v01_0.png" in _norm(p) and "picked" in p for p in problems), problems
    _pick(ov, "03_wip/host_v01_0.png")
    assert organic_specs.check(ov, TAKE, path) == []
    # a row of the video stage, or of another file, is not a pick of this image
    (ov.path / organic_specs.AZ_LOG).unlink()
    _pick(ov, "03_wip/host_v01_1.png")
    with open(ov.path / organic_specs.AZ_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"stage": "video", "name": "take", "file": "03_wip/host_v01_0.png"}) + "\n")
    assert organic_specs.check(ov, TAKE, path) != []


def test_the_guard_reads_only_current_picks(ov):
    """Task 15's ruling, on the guard: a frame counts as picked only while its pick is the item's latest, was made after
    the latest pack check and names an output of the item's latest take."""
    path = _spec(ov, "take", TAKE)
    _pick(ov, "03_wip/host_v01_0.png", at="2020-01-01T00:00:00+00:00")   # before the pack was checked
    assert any("picked" in p for p in organic_specs.check(ov, TAKE, path))
    _pick(ov, "03_wip/host_v01_0.png")
    assert organic_specs.check(ov, TAKE, path) == []
    (ov.path / "03_wip" / "host_v02.run.json").write_text(json.dumps(          # made again since: a new take
        {"model": "openai/gpt-image-2", "status": "done", "prediction_id": "p2", "outputs": ["host_v02_0.png"]}),
        encoding="utf-8")
    assert any("picked" in p for p in organic_specs.check(ov, TAKE, path))
    assert organic_specs.picked(ov) == set()


def test_model_and_item_are_the_packs(ov):
    _pick(ov, "03_wip/host_v01_0.png")
    spec = copy.deepcopy(TAKE)
    spec["model"] = "google/veo-3.1"
    problems = organic_specs.check(ov, spec, _spec(ov, "take", spec))
    assert any("google/veo-3.1" in p and "pack" in p for p in problems), problems
    problems = organic_specs.check(ov, TAKE, _spec(ov, "take", TAKE), name="take2")
    assert any("take2" in p and "host, take" in p for p in problems), problems
    problems = organic_specs.check(ov, TAKE, _spec(ov, "take", TAKE), name="host")   # H3 for the image item
    assert any("openai/gpt-image-2" in p for p in problems), problems


def test_seedance_never_takes_the_host_image_e005(ov):
    pack = _pack()
    pack["models"].append({**pack["models"][1], "model": "bytedance/seedance-2.0"})
    pack["stages"][1]["items"].append({"name": "broll", "model": "bytedance/seedance-2.0", "seconds": 5})
    _check_pack(ov, pack, n=2)
    _pick(ov, "03_wip/host_v01_0.png")
    spec = {"model": "bytedance/seedance-2.0", "input": {"prompt": "the kitchen", "image": "host_v01_0.png"}}
    problems = organic_specs.check(ov, spec, _spec(ov, "broll", spec))
    assert any("E005" in p and "03_wip/host_v01_0.png" in _norm(p) for p in problems), problems


def test_featured_product_item_names_a_packshot(ov):
    shot = organic_specs.trend_spool.workspace_of(ov) / "library" / "brands" / "pets" / "packshots" / "mat_v01.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(PNG)
    pack = _pack()
    pack["product"] = {"level": "featured", "packshots": ["library/brands/pets/packshots/mat_v01.png"]}
    _check_pack(ov, pack, n=2)
    problems = organic_specs.check(ov, HOST, _spec(ov, "host", HOST))
    assert any("packshot" in p and "featured" in p for p in problems), problems
    spec = copy.deepcopy(HOST)
    spec["input"]["input_images"] = [str(shot)]
    assert organic_specs.check(ov, spec, _spec(ov, "host", spec)) == []
    _pick(ov, "03_wip/host_v01_0.png")   # the take carries the product through its picked frame
    assert organic_specs.check(ov, TAKE, _spec(ov, "take", TAKE)) == []


def test_a_newer_unchecked_pack_is_never_used(ov, engine, capsys):
    """Task 12's review M3: the guard reads only the latest checked pack; a newer, unchecked version stops it."""
    _pick(ov, "03_wip/host_v01_0.png")
    pack = _pack()
    pack["resolution"]["choice"] = "1080p"
    (ov.path / "03_wip" / "pack_v02.json").write_text(json.dumps(pack), encoding="utf-8")
    spec = _spec(ov, "take", TAKE)
    problems = organic_specs.check(ov, TAKE, spec)
    assert len(problems) == 1 and "tm organic pack check" in problems[0], problems
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop") and "tm organic pack check" in out["message"]
    assert engine == [] and state.load(ov).spend == {}


# --- the guard, through tm tool ------------------------------------------------------------------

def test_second_take_without_user_request_refused_and_nothing_spent(ov, engine, capsys):
    _pick(ov, "03_wip/host_v01_0.png")
    spec = _spec(ov, "take", TAKE)
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 0 and len(engine) == 1 and state.load(ov).spend == {"ai_usd": 1.04}
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop")
    assert ("A video is never regenerated automatically. Ask the user; if they want a redo, record their words "
            "with `tm organic redo` and show its cost.") in out["message"]
    assert "continues from the same place" in out["message"]
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 1.04}   # nothing more spent


def test_a_spec_problem_stops_before_anything_is_spent(ov, engine, capsys):
    spec = _spec(ov, "take", TAKE)   # its first frame was never picked
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop") and "picked" in out["message"]
    assert engine == [] and state.load(ov).spend == {}


def test_redo_request_allows_one_take_then_is_used_up(ov, engine, capsys):
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1)
    spec = _spec(ov, "take", TAKE)
    capsys.readouterr()
    assert main(["organic", "redo", "--run", str(ov.path), "--name", "take", "--note",
                 "Zrób to jeszcze raz, ale wolniej", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["stem"] == "take"
    (req,) = state.load(ov).organic["redos"]["take"]
    assert (req["kind"], req["note"], req["after"]) == ("request", "Zrób to jeszcze raz, ale wolniej", "take_v01.run.json")
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop") and '"redo": true' in out["message"]   # not priced yet (I4)
    assert engine == []
    _replanned(ov, _with_redo(_pack(), "take"), n=2)          # re-planned with the redo, and the user's yes again
    code, out = _tool(capsys, ov, spec, "take")                 # the frame's pick still counts: host is unchanged
    assert code == 0 and len(engine) == 1                       # the one redo the user asked for
    assert (ov.path / "03_wip" / "take_v02.run.json").is_file()
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop") and "never regenerated automatically" in out["message"]
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 1.04}


def test_a_spend_names_its_spec_and_item(ov, engine, capsys):
    """PR C review Minor 3: with --run written first, as both skills write it, the spend and the over-budget stop name
    the spec and the item, never "--run"; refresh-ad's spec-first call and elevenlabs' action read as before."""
    _pick(ov, "03_wip/host_v01_0.png")
    spec = _spec(ov, "take", TAKE)
    s = state.load(ov)
    s.spend = {"ai_usd": 4.5}                                    # $1.04 more is over the $5 approved
    state.save(ov, s)
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 2 and engine == []
    assert f"tm tool replicate_run {spec} (take) would cost" in out["message"], out["message"]
    assert tools._label("replicate_run", ["03_wip/take_v01.json", "--run", "R", "--cost", "1.2"]) == \
        "tm tool replicate_run 03_wip/take_v01.json"
    assert tools._label("replicate_run", ["--run", "R", "--resume", "03_wip/take_v01.run.json"]) == \
        "tm tool replicate_run 03_wip/take_v01.run.json"
    assert tools._label("elevenlabs", ["tts", "--run", "R", "--voice-id", "v", "--cost", "40"]) == \
        "tm tool elevenlabs tts"


def test_a_request_stays_open_until_the_call_starts(ov, engine, capsys):
    """A refusal after the guard (the budget) runs nothing, so the user's request is still there."""
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1)
    spec = _spec(ov, "take", TAKE)
    organic_specs.redo(ov, "take", "Once more, please")
    _replanned(ov, _with_redo(_pack(), "take"), n=2)          # the frame's pick still counts (host unchanged)
    s = state.load(ov)
    s.spend = {"ai_usd": 4.5}                                    # $1.04 more is over the $5 approved
    state.save(ov, s)
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 2 and engine == []
    s = state.load(ov)
    s.status, s.stops = "active", []                             # the user approves more
    s.budgets["ai_usd"] = 20.0
    state.save(ov, s)
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 0 and len(engine) == 1


def test_unfinished_paid_take_resumes_never_reruns(ov, engine, capsys):
    """Review Focus 1: Replicate accepted the H3 take, the client died; "try again" pays nothing twice."""
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1, status="processing", prediction_id="r3xd631w9nrmy0d1p0pvvpg96w")
    spec = _spec(ov, "take", TAKE)
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop")
    assert ("This take was paid for and is still on Replicate. Finish it for free with `--resume "
            "03_wip/take_v01.run.json`; it is never run again.") in out["message"]
    assert engine == [] and state.load(ov).spend == {}
    capsys.readouterr()
    assert main(["organic", "redo", "--run", str(ov.path), "--name", "take", "--note", "try again", "--json"]) == 2
    assert "--resume 03_wip/take_v01.run.json" in json.loads(capsys.readouterr().out)["message"]
    assert main(["tool", "replicate_run", "--run", str(ov.path), "--resume", "03_wip/take_v01.run.json"]) == 0
    assert len(engine) == 1 and state.load(ov).spend == {}      # the free resume of the same prediction


def test_a_failed_take_with_nothing_on_replicate_may_run_again(ov, engine, capsys):
    """A prediction that failed before any output is not "still on Replicate" (nothing to resume), and no
    video was made, so the take may run again; the failure was recorded as $0."""
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1, status="failed")
    code, out = _tool(capsys, ov, _spec(ov, "take", TAKE), "take")
    assert code == 0 and len(engine) == 1


def test_hands_off_image_redo_once_then_refused(ov, engine, capsys):
    _record(ov, "host", 1)
    spec = _spec(ov, "host", HOST)
    code, out = _tool(capsys, ov, spec, "host", cost="0.26")
    assert code == 0 and len(engine) == 1                       # the images check-in goes by rule: one redo
    (auto,) = state.load(ov).organic["redos"]["host"]
    assert (auto["kind"], auto["after"]) == ("auto_redo", "host_v01.run.json")
    code, out = _tool(capsys, ov, spec, "host", cost="0.26")
    assert (code, out["status"]) == (2, "stop") and "tm organic redo" in out["message"]
    assert len(engine) == 1


def test_every_step_image_redo_needs_the_user(ov, engine, capsys):
    _level(ov, "every_step")
    _record(ov, "host", 1)
    code, out = _tool(capsys, ov, _spec(ov, "host", HOST), "host", cost="0.26")
    assert (code, out["status"]) == (2, "stop") and "tm organic redo" in out["message"]
    assert engine == [] and "redos" not in (state.load(ov).organic or {})


def test_redo_needs_a_finished_take_and_the_users_words(ov, capsys):
    for argv, code in ((["--name", "take", "--note", "again"], 2),            # nothing made yet
                       (["--name", "nope", "--note", "again"], 1),            # not an item of the pack
                       (["--name", "take", "--note", "  "], 1)):               # no words
        capsys.readouterr()
        assert main(["organic", "redo", "--run", str(ov.path), *argv, "--json"]) == code
        assert json.loads(capsys.readouterr().out)["status"] == ("stop" if code == 2 else "error")
    assert "redos" not in (state.load(ov).organic or {})


def test_refresh_ad_has_no_precheck(tmp_path, engine, capsys, monkeypatch):
    assert set(tools.PRECHECK) == {ORGANIC_VIDEO, CREATE_AD} and set(tools.PRECHECK[ORGANIC_VIDEO]) == {"replicate_run"}

    def never(*a, **k):
        raise AssertionError("the organic guard ran for refresh-ad")

    monkeypatch.setattr(organic_specs, "guard", never)
    run = RunFolder.create(tmp_path / "ads", "ad", date(2026, 11, 7), playbook=REFRESH_AD)
    s = state.load(run)
    s.budgets = {"ai_usd": 5.0}
    state.save(run, s)
    _record(run, "hook", 1)
    spec = _spec(run, "hook card", HOST | {"input": {"prompt": "A snowy street", "output_format": "webp"}})
    assert _tool(capsys, run, spec, "hook", cost="0.04")[0] == 0
    assert _tool(capsys, run, spec, "hook", cost="0.04")[0] == 0
    assert len(engine) == 2 and state.load(run).spend == {"ai_usd": 0.08}


# --- fix round 1 ---------------------------------------------------------------------------------

def test_a_model_less_item_never_hosts_a_take(ov, engine, capsys):
    """Review I1: an item the pack makes with no model (a user's own photo) is never generated, so a second
    H3 take cannot run under its name as a "first take"."""
    pack = _pack()
    pack["stages"][0]["items"].append({"name": "photo", "model": None})
    _check_pack(ov, pack, n=2)
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1)
    spec = _spec(ov, "take", TAKE)
    problems = organic_specs.check(ov, TAKE, spec, name="photo")
    assert any("photo" in p and "no model" in p for p in problems), problems
    code, out = _tool(capsys, ov, spec, "photo")
    assert (code, out["status"]) == (2, "stop") and "no model" in out["message"]
    assert engine == [] and state.load(ov).spend == {}


def test_video_rules_follow_the_model_not_the_stage(ov, engine, capsys):
    """Review M1: an H3 item placed in the images stage is still a video: picked frames, never an automatic redo."""
    pack = _pack()
    pack["stages"][0]["items"].append({"name": "clip", "model": "minimax/h3"})
    pack["cost"]["lines"].append({**pack["cost"]["lines"][1], "item": "clip"})   # priced like the take
    _check_pack(ov, pack, n=2)
    spec = _spec(ov, "take", TAKE)
    assert any("picked" in p for p in organic_specs.check(ov, TAKE, spec, name="clip"))
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "clip", 1)
    code, out = _tool(capsys, ov, spec, "clip")
    assert (code, out["status"]) == (2, "stop") and "never regenerated automatically" in out["message"]
    assert engine == [] and "redos" not in (state.load(ov).organic or {})


def test_paths_are_compared_without_case(ov):
    """Review M2: 02_Research is the evidence folder on a case-blind disk too, and Host_v01_0.png is the host."""
    _pick(ov, "03_wip/host_v01_0.png")
    clip = ov.path / "02_Research" / "clip.mp4"
    clip.parent.mkdir(exist_ok=True)
    clip.write_bytes(b"fake mp4")
    spec = copy.deepcopy(TAKE)
    spec["input"].pop("first_frame_image")
    spec["input"].update(reference_video_urls=["../02_Research/clip.mp4"], ratio="9:16")
    problems = organic_specs.check(ov, spec, _spec(ov, "take", spec))
    assert any(organic_specs.CLIPS in p for p in problems), problems

    pack = _pack()
    pack["models"].append({**pack["models"][1], "model": "bytedance/seedance-2.0"})
    pack["stages"][1]["items"].append({"name": "broll", "model": "bytedance/seedance-2.0", "seconds": 5})
    _check_pack(ov, pack, n=2)
    (ov.path / "03_wip" / "Host_v01_0.png").write_bytes(PNG)   # the same file where the disk ignores case
    _pick(ov, "03_wip/Host_v01_0.png")
    spec = {"model": "bytedance/seedance-2.0", "input": {"prompt": "the kitchen", "image": "Host_v01_0.png"}}
    problems = organic_specs.check(ov, spec, _spec(ov, "broll", spec))
    assert any("E005" in p for p in problems), problems


@pytest.mark.parametrize("status", ["unknown", "not started"])
def test_a_take_that_may_be_running_blocks_until_the_dashboard_is_checked(ov, engine, capsys, status):
    """Queued ruling and review M3: a start that lost its answer (unknown), or a process killed before
    Replicate's answer (not started), may be running and charging on Replicate: nothing runs again until the
    user has looked at the dashboard."""
    _pick(ov, "03_wip/host_v01_0.png")
    _record(ov, "take", 1, status=status, prediction_id=None)
    spec = _spec(ov, "take", TAKE)
    code, out = _tool(capsys, ov, spec, "take")
    assert (code, out["status"]) == (2, "stop")
    assert organic_specs.DASHBOARD.format(record="03_wip/take_v01.run.json") in out["message"]
    assert "tm organic dashboard-checked" in out["message"]
    assert engine == [] and state.load(ov).spend == {}
    capsys.readouterr()
    assert main(["organic", "redo", "--run", str(ov.path), "--name", "take", "--note", "again", "--json"]) == 2
    assert "Replicate dashboard" in json.loads(capsys.readouterr().out)["message"]
    assert main(["organic", "dashboard-checked", "--run", str(ov.path), "--name", "take", "--note",
                 "Nie ma tego ujęcia na Replicate", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["record"] == "03_wip/take_v01.run.json"
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 0 and len(engine) == 1                       # still the item's first take
    capsys.readouterr()
    assert main(["organic", "dashboard-checked", "--run", str(ov.path), "--name", "take", "--note", "x", "--json"]) == 2


def test_a_failed_take_costs_nothing_end_to_end(ov, engine, capsys):
    """Review M5: through tm tool, a prediction that failed before any output leaves the spend at 0."""
    _pick(ov, "03_wip/host_v01_0.png")
    spec = _spec(ov, "take", TAKE)
    engine.status, engine.report = "failed", {"spent": True, "actual": 0.0}
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 1 and state.load(ov).spend == {"ai_usd": 0.0}
    engine.status, engine.report = "done", {"spent": True, "actual": None}
    code, out = _tool(capsys, ov, spec, "take")
    assert code == 0 and len(engine) == 2 and state.load(ov).spend == {"ai_usd": 1.04}


def test_a_stopped_run_is_not_changed_by_the_guard(ov, engine, capsys):
    """Review M6: the stopped-run check comes first, so not even the automatic image redo is written."""
    from tm import flow

    _record(ov, "host", 1)
    flow.stop(ov, "upload_by_hand", "The take could not be saved.", "Save it by hand.")
    before = (ov.path / "run.json").read_text(encoding="utf-8")
    code, out = _tool(capsys, ov, _spec(ov, "host", HOST), "host", cost="0.26")
    assert (code, out["status"]) == (2, "stop") and "nothing was spent" in out["message"]
    assert engine == [] and (ov.path / "run.json").read_text(encoding="utf-8") == before


# --- the PR C fix wave -----------------------------------------------------------------------------

def test_a_run_relative_spec_is_read_from_the_workspace(ov, engine, capsys, monkeypatch):
    """PR C review I3: from the workspace, as the skill works, `tm tool replicate_run --run R 03_wip/host_v01.json`
    reads the run's spec (the working folder first, then the run), and the child is given the same name."""
    _spec(ov, "host_v01", HOST)
    monkeypatch.chdir(organic_specs.trend_spool.workspace_of(ov))
    code, out = _tool(capsys, ov, "03_wip/host_v01.json", "host", cost="0.26")
    assert code == 0, out
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 0.26}
    assert "03_wip/host_v01.json" in engine[0]


def _to_pack(run, monkeypatch):
    """Walk D1 to E2 (its step checks passing: test_organic_doctor and test_organic_pack prove them), the taste
    decided as the level routes it, until the pack check-in is asked. Nothing is approved before."""
    from tm import flow, organic, organic_qa

    for gap in ((organic, "credits_gap"), (organic_pack, "recipe_gap"), (organic_pack, "pack_gap"),
                (organic_qa, "images_gap"), (organic_qa, "takes_gap")):
        monkeypatch.setattr(*gap, lambda run: None)
    s = state.load(run)
    s.budgets, s.decisions = {}, []
    state.save(run, s)
    for _ in range(20):
        nxt = flow.next(run)
        if nxt.action == "work":
            flow.complete(run, nxt.step)
        elif nxt.checkin and "pack" in nxt.checkin.ids:   # Just the big calls: the plan card, taste and pack
            return nxt
        else:
            for cid in nxt.checkin.ids:
                flow.decide(run, cid, "accept", by="rule" if nxt.action == "auto" else "user",
                            note="the profile's taste" if nxt.action == "auto" else None)
    raise AssertionError("the pack was never asked")


def _cli(capsys, run, *argv):
    capsys.readouterr()
    code = main([*argv, "--run", str(run.path), "--json"])
    return code, json.loads(capsys.readouterr().out)


def _open_stops(run):
    return [x["reason_id"] for x in state.load(run).stops if "resumed_at" not in x]


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_a_paid_call_needs_the_current_yes_and_the_approved_amount(ov, engine, capsys, monkeypatch, level):
    """PR C review I2 and Minor 1: nothing is paid before the pack's yes (and no stop is opened that would hold the yes
    itself); after a re-plan at a higher total the take is refused, nothing spent, until `tm decide pack approve
    --change` and `tm budget approve` for the new total."""
    _level(ov, level)
    asked = _to_pack(ov, monkeypatch)
    host = _spec(ov, "host_v01", HOST)
    code, out = _tool(capsys, ov, host, "host", cost="0.26")
    assert (code, out["status"]) == (2, "stop") and "tm decide pack approve" in out["message"], out
    assert engine == [] and state.load(ov).spend == {} and _open_stops(ov) == []
    if "taste" in asked.checkin.ids:                             # the plan card, decided member by member
        assert _cli(capsys, ov, "decide", "taste", "accept", "--note", "tak")[0] == 0
    assert _cli(capsys, ov, "decide", "pack", "approve", "--note", "tak, 1,46 USD")[0] == 0
    code, out = _tool(capsys, ov, host, "host", cost="0.26")      # the yes, and no amount approved yet
    assert (code, out["status"]) == (2, "stop") and "tm budget approve" in out["message"], out
    assert engine == [] and state.load(ov).spend == {}
    assert _cli(capsys, ov, "budget", "approve", "ai_usd", "1.3", "--note", "tak")[0] == 0
    code, out = _tool(capsys, ov, host, "host", cost="0.26")
    assert code == 0 and state.load(ov).spend == {"ai_usd": 0.26}
    _pick(ov, "03_wip/host_v01_0.png")
    take = _spec(ov, "take", TAKE)
    # re-planned at a higher total: host ×3 ($1.42)
    pack = _pack()
    pack["stages"][0]["items"][0]["images"] = 3
    line = pack["cost"]["lines"][0]
    line["units"], line["cost"] = 3, round(line["unit_price"] * 3, 2)
    pack["cost"]["totals"]["ai_usd"] = round(line["cost"] + pack["cost"]["lines"][1]["cost"], 2)
    s = state.load(ov)
    for d in s.decisions:
        d["at"] = "2026-11-07T09:00:00+00:00"                    # given before the re-plan (a tie in one second counts)
    state.save(ov, s)
    _check_pack(ov, pack, n=2, yes=False)
    assert state.load(ov).planned == {"ai_usd": 1.42, "voice_credits": 0.0}
    _pick(ov, "03_wip/host_v01_0.png")                           # picked again after the re-plan
    code, out = _tool(capsys, ov, take, "take")
    assert (code, out["status"]) == (2, "stop") and "tm decide pack approve --change" in out["message"], out
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 0.26} and _open_stops(ov) == []
    assert _cli(capsys, ov, "decide", "pack", "approve", "--change", "--note", "tak, 1,42 USD")[0] == 0
    code, out = _tool(capsys, ov, take, "take")                   # the new yes; $1.30 approved of $1.42 planned
    assert (code, out["status"]) == (2, "stop") and "tm budget approve" in out["message"], out
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 0.26}
    assert _cli(capsys, ov, "budget", "approve", "ai_usd", "1.42", "--note", "tak")[0] == 0
    code, out = _tool(capsys, ov, take, "take")
    assert code == 0 and len(engine) == 2 and state.load(ov).spend == {"ai_usd": 1.3}


def test_cost_must_be_the_items_priced_line(ov, engine, capsys):
    """PR C review I2: `--cost 0.01` for host's $0.26 line (or a copied take's 1.04) is refused, nothing spent; the
    message names the line and its price file."""
    host = _spec(ov, "host_v01", HOST)
    for cost in ("0.01", "1.04", "0.27"):
        code, out = _tool(capsys, ov, host, "host", cost=cost)
        assert (code, out["status"]) == (2, "stop"), out
        assert "--cost 0.26" in out["message"] and "prices_2026-11-04_v01.json" in out["message"]
    assert engine == [] and state.load(ov).spend == {}
    code, out = _tool(capsys, ov, host, "host", cost="0.26")
    assert code == 0 and state.load(ov).spend == {"ai_usd": 0.26}


def _approved(ov, capsys, monkeypatch, level, amount="1.3"):
    """The run walked to the pack at `level`, the user's yes (the plan card member by member) and `amount` approved."""
    _level(ov, level)
    asked = _to_pack(ov, monkeypatch)
    if "taste" in asked.checkin.ids:
        assert _cli(capsys, ov, "decide", "taste", "accept", "--note", "tak")[0] == 0
    assert _cli(capsys, ov, "decide", "pack", "approve", "--note", "tak")[0] == 0
    assert _cli(capsys, ov, "budget", "approve", "ai_usd", amount, "--note", "tak")[0] == 0


def test_a_week_slots_approval_is_held_to_the_weeks_remainder(ov, capsys, monkeypatch):
    """PR E re-review N1: in a slot of a $5 week whose other video planned, approved and spent $3.70, the slot's whole
    ai_usd approval (what it already spent included) may be at most the week's remainder, 5.00 - 3.70 = $1.30, as
    `week_left` gives it. `tm budget approve ai_usd 1.3` passes, a cent over is refused, and so is the re-review's
    $4.00; each refusal names the remainder and `tm organic week budget`. An over-budget stop's todo there says the
    same."""
    from tm import budget, config, flow, organic_config, organic_week, trend_spool
    ws = trend_spool.workspace_of(ov)
    week = RunFolder.create(ws, "wk", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    config.save(week, {**organic_config.defaults(), "channels": ["x"]})
    ref = week.path.relative_to(ws).as_posix()
    other = RunFolder.create(ws, "w1", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(other)
    s.outputs, s.organic = ["organic_video"], {"week": ref, "parent": ref, "proposal": "w1"}
    s.planned, s.budgets, s.spend = {"ai_usd": 3.70}, {"ai_usd": 3.70}, {"ai_usd": 3.70}
    state.save(other, s)
    s = state.load(ov)
    s.organic = {**(s.organic or {}), "week": ref}
    s.budgets = {}
    state.save(ov, s)
    assert organic_week.week_left(ov) == (5.0, 3.7, 1.3)
    _approved(ov, capsys, monkeypatch, "every_step", amount="1.3")             # at the remainder: passes
    for amount in ("1.31", "4.0"):
        code, out = _cli(capsys, ov, "budget", "approve", "ai_usd", amount, "--note", "tak, więcej")
        assert code == 1 and "remainder for this one is 1.3 USD" in out["message"], (amount, out)
        assert f"tm organic week budget --run {ref} --usd" in out["message"] and "Nothing was approved" in out["message"]
        assert state.load(ov).budgets["ai_usd"] == 1.3
    assert budget.spend(ov, "ai_usd", 1.4, "a take") == 2
    todo = flow.open_stop(ov, ["over_budget_ai_usd"])
    assert "week's remainder for it, 1.3 USD" in todo and "tm organic week budget" in todo


def _replan(ov, capsys, pack, n, total):
    """A new pack checked at a higher total after the yes, the user's yes again (--change) and the new total approved."""
    s = state.load(ov)
    for d in s.decisions:
        d["at"] = "2026-11-07T09:00:00+00:00"                    # given before this re-plan
    state.save(ov, s)
    _check_pack(ov, pack, n=n, yes=False)
    assert abs(state.load(ov).planned["ai_usd"] - total) < 1e-9
    return pack


@pytest.mark.parametrize("level", ["big_calls", "hands_off"])
def test_a_requested_redo_is_paid_only_once_priced(ov, engine, capsys, monkeypatch, level):
    """PR C review I4 and Task 18 I1: the user's redo of the take is never paid from another item's money: it waits
    for a re-planned pack with its redo line, the yes again (--change) and the new total approved; then it runs once."""
    _approved(ov, capsys, monkeypatch, level)
    assert _tool(capsys, ov, _spec(ov, "host_v01", HOST), "host", cost="0.26")[0] == 0
    _pick(ov, "03_wip/host_v01_0.png")
    take = _spec(ov, "take", TAKE)
    assert _tool(capsys, ov, take, "take")[0] == 0 and state.load(ov).spend == {"ai_usd": 1.3}
    assert _cli(capsys, ov, "organic", "redo", "--name", "take", "--note", "zrób to jeszcze raz, szybciej")[0] == 0
    code, out = _tool(capsys, ov, take, "take")
    assert (code, out["status"]) == (2, "stop") and "The redo of take is not priced yet" in out["message"], out
    assert "tm decide pack approve --change" in out["message"] and _open_stops(ov) == []
    assert len(engine) == 2 and state.load(ov).spend == {"ai_usd": 1.3}
    _replan(ov, capsys, _with_redo(_pack(), "take"), 2, 2.34)
    _pick(ov, "03_wip/host_v01_0.png")                           # picked again after the re-plan
    code, out = _tool(capsys, ov, take, "take")
    assert code == 2 and "--change" in out["message"] and len(engine) == 2
    assert _cli(capsys, ov, "decide", "pack", "approve", "--change", "--note", "tak, 2,66 USD")[0] == 0
    assert _cli(capsys, ov, "budget", "approve", "ai_usd", "2.34", "--note", "tak")[0] == 0
    code, out = _tool(capsys, ov, take, "take")
    assert code == 0 and len(engine) == 3 and state.load(ov).spend == {"ai_usd": 2.34}
    code, out = _tool(capsys, ov, take, "take")                   # the request is used up
    assert code == 2 and "never regenerated automatically" in out["message"] and len(engine) == 3


@pytest.mark.parametrize("level", ["big_calls", "hands_off"])
def test_the_automatic_image_redo_fits_the_budget_or_becomes_a_priced_request(ov, engine, capsys, monkeypatch,
                                                                               level):
    """PR C review I4: at a rule level the one automatic image redo runs only while the approved budget still covers it
    and the take's line; with only the pack's $1.30 approved it is recorded as a request and priced like any redo, so
    the take never runs over budget."""
    _approved(ov, capsys, monkeypatch, level)
    host = _spec(ov, "host_v01", HOST)
    assert _tool(capsys, ov, host, "host", cost="0.26")[0] == 0
    for tried in range(2):                                        # recorded once, however often it is tried
        code, out = _tool(capsys, ov, host, "host", cost="0.26")
        assert (code, out["status"]) == (2, "stop"), out
        assert ("does not fit the approved budget" in out["message"] and "(1.04 USD; 1.04 USD is left)" in
                out["message"]) is (tried == 0), out
        assert "The redo of host is not priced yet" in out["message"]
    (asked,) = state.load(ov).organic["redos"]["host"]
    assert (asked["kind"], asked["by"], asked["after"]) == ("request", "rule", "host_v01.run.json")
    assert len(engine) == 1 and state.load(ov).spend == {"ai_usd": 0.26} and _open_stops(ov) == []
    _replan(ov, capsys, _with_redo(_pack(), "host"), 2, 1.56)
    assert _cli(capsys, ov, "decide", "pack", "approve", "--change", "--note", "tak, 1,56 USD")[0] == 0
    assert _cli(capsys, ov, "budget", "approve", "ai_usd", "1.56", "--note", "tak")[0] == 0
    assert _tool(capsys, ov, host, "host", cost="0.26")[0] == 0 and state.load(ov).spend == {"ai_usd": 0.52}
    code, out = _tool(capsys, ov, host, "host", cost="0.26")      # the one redo is used
    assert code == 2 and "already made again once automatically" in out["message"] and len(engine) == 2
    record = ov.path / "03_wip" / "host_v02.run.json"             # the redo made host_v02_0.png: it is picked
    record.write_text(json.dumps(json.loads(record.read_text(encoding="utf-8")) | {"outputs": ["host_v02_0.png"]}),
                      encoding="utf-8")
    (ov.path / "03_wip" / "host_v02_0.png").write_bytes(PNG)
    with open(ov.path / organic_specs.AZ_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"stage": "images", "name": "host", "file": "03_wip/host_v02_0.png", "rubric": {},
                             "reason": "the redo's face", "by": "rule",
                             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")
    take = copy.deepcopy(TAKE)
    take["input"]["first_frame_image"] = "host_v02_0.png"
    code, out = _tool(capsys, ov, _spec(ov, "take", take), "take")
    assert code == 0, out
    assert state.load(ov).spend == {"ai_usd": 1.56} and _open_stops(ov) == []


@pytest.mark.parametrize("level", ["big_calls", "hands_off"])
def test_the_automatic_image_redo_runs_within_the_approved_budget(ov, engine, capsys, monkeypatch, level):
    """With more approved than the pack plans (the user's own amount), the automatic redo fits beside the take's line,
    so it runs at once and is recorded as the one automatic redo."""
    _approved(ov, capsys, monkeypatch, level, amount="1.56")
    host = _spec(ov, "host_v01", HOST)
    assert _tool(capsys, ov, host, "host", cost="0.26")[0] == 0
    assert _tool(capsys, ov, host, "host", cost="0.26")[0] == 0
    (auto,) = state.load(ov).organic["redos"]["host"]
    assert (auto["kind"], auto["after"]) == ("auto_redo", "host_v01.run.json")
    assert len(engine) == 2 and state.load(ov).spend == {"ai_usd": 0.52}
