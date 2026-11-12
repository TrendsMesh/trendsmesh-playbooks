"""tm tool deliver on clips made here with ffmpeg: the final at the run's loudness target (−14 LUFS, −16 for ASMR)
from a quiet 540×960 render, then its upload copy, preview, cover, no-sound export, a sped-up take and the
measures, and the `final_checked` step check on the real files."""

from __future__ import annotations

import json
import subprocess
from datetime import date

import pytest
from _media import ffmpeg

from tm import config, manifest, organic_config, organic_final, state, stepchecks
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import _common as c
from tm.tools import deliver, take_qa

SECONDS = 6.0


def _quiet_render(path, seconds=SECONDS):
    """A 540×960 render at about −30 LUFS: testsrc2 and a 440 Hz tone 8 dB under lavfi's default."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc2=size=540x960:rate=25:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={seconds}",
                    "-af", "volume=-8dB", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


@pytest.fixture
def ov(tmp_path):
    run = RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "exampleedu m5", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.organic = {"proposal": "M5", "channel": "exampleedu"}
    state.save(run, s)
    config.save(run, organic_config.defaults())
    return run


def _tool(capsys, *argv):
    code = deliver.main([*argv, "--json"])
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return code, json.loads(out)


def _finish(capsys, run, *extra):
    render = _quiet_render(run.path / "03_wip" / "M5" / "edit_v01_render.mp4")
    lufs, _ = take_qa.loudness(render)
    assert -32 < lufs < -28, lufs   # the synthetic clip starts far from the target
    code, out = _tool(capsys, "finish", "--run", str(run.path), "03_wip/M5/edit_v01_render.mp4", "--id", "M5", *extra)
    assert code == 0, out
    return out


@pytest.mark.tools
def test_finish_hits_minus_14_lufs(ov, capsys):
    out = _finish(capsys, ov)
    assert out["outputs"] == ["04_final/M5_final_v01.mp4"]
    final = ov.path / "04_final" / "M5_final_v01.mp4"
    found = organic_final._probe(final)
    assert {k: found[k] for k in ("width", "height", "vcodec", "acodec", "sample_rate")} == {
        "width": 1080, "height": 1920, "vcodec": "h264", "acodec": "aac", "sample_rate": 48000}
    assert abs(found["lufs"] - (-14)) <= 1 and abs(out["lufs"] - found["lufs"]) < 0.2
    assert out["lufs_target"] == -14
    assert abs(c.probe(final)["duration"] - SECONDS) < 0.2
    # a second finish is the next version; the first is never touched
    before = stepchecks.sha256(final)
    code, again = _tool(capsys, "finish", "--run", str(ov.path), "03_wip/M5/edit_v01_render.mp4", "--id", "M5")
    assert (code, again["outputs"]) == (0, ["04_final/M5_final_v02.mp4"])
    assert stepchecks.sha256(final) == before


@pytest.mark.tools
def test_asmr_target_minus_16(ov, capsys):
    out = _finish(capsys, ov, "--asmr")
    assert out["lufs_target"] == -16 and abs(out["lufs"] - (-16)) <= 1
    final = "04_final/M5_final_v01.mp4"
    gap = stepchecks.run("final_checked", ov)
    assert "upload copy" in gap and "cover JPG" in gap and "LUFS" not in gap   # −16 is this final's target
    assert _tool(capsys, "upload", "--run", str(ov.path), final)[0] == 0
    cover = ov.path / "04_final" / "kits" / "cover_M5_v01.png"
    cover.parent.mkdir(parents=True)
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920",
                    "-frames:v", "1", str(cover)], check=True)
    code, out = _tool(capsys, "cover", "--run", str(ov.path), "04_final/kits/cover_M5_v01.png")
    assert (code, out["outputs"]) == (0, ["04_final/kits/cover_M5_v01.jpg"])
    assert stepchecks.run("final_checked", ov) is None


@pytest.mark.tools
def test_upload_preview_and_nosound(ov, capsys):
    _finish(capsys, ov)
    final = "04_final/M5_final_v01.mp4"
    code, out = _tool(capsys, "upload", "--run", str(ov.path), final)
    upload = ov.path / "04_final" / "M5_final_v01_upload.mp4"
    assert (code, out["outputs"], out["crf"]) == (0, ["04_final/M5_final_v01_upload.mp4"], 26)
    assert upload.stat().st_size < 15_000_000
    assert b"moov" in upload.read_bytes()[:4096]   # faststart: the index before the picture
    code, out = _tool(capsys, "preview", "--run", str(ov.path), final)
    info = c.probe(ov.path / "showcase" / "M5_final_v01_720p.mp4")
    assert (code, info["width"], info["height"], info["has_audio"]) == (0, 720, 1280, True)
    code, out = _tool(capsys, "nosound", "--run", str(ov.path), final)
    info = c.probe(ov.path / "04_final" / "M5_final_v01_nosound.mp4")
    assert (code, info["width"], info["has_audio"]) == (0, 1080, False)


@pytest.mark.tools
def test_speed_keeps_the_sound_and_shortens_the_take(ov, capsys):
    take = _quiet_render(ov.path / "03_wip" / "take_v01_0.mp4")
    code, out = _tool(capsys, "speed", "--run", str(ov.path), "03_wip/take_v01_0.mp4", "--factor", "1.2")
    assert (code, out["outputs"]) == (0, ["03_wip/take_v01_0_speed120.mp4"])
    info = c.probe(take.with_name("take_v01_0_speed120.mp4"))
    assert info["has_audio"] and abs(info["duration"] - SECONDS / 1.2) < 0.2


@pytest.mark.tools
def test_measure_gives_lufs_and_peak_per_file(ov, capsys):
    loud = _quiet_render(ov.path / "03_wip" / "a.mp4")
    code, out = _tool(capsys, "measure", "--run", str(ov.path), "03_wip/a.mp4", str(loud))
    assert code == 0 and [m["file"] for m in out["files"]] == ["03_wip/a.mp4", "03_wip/a.mp4"]
    assert all(-32 < m["lufs"] < -28 and m["peak"] < 0 for m in out["files"])


@pytest.mark.tools
def test_finish_refuses_a_render_without_sound(ov, capsys):
    silent = ov.path / "03_wip" / "mute.mp4"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=540x960:duration=2",
                    "-pix_fmt", "yuv420p", str(silent)], check=True)
    code, out = _tool(capsys, "finish", "--run", str(ov.path), "03_wip/mute.mp4", "--id", "M5")
    assert code == 1 and "no sound" in out["message"] and "nosound" in out["message"]
    assert not (ov.path / "04_final" / "M5_final_v01.mp4").exists()


# --- Create an ad's finish (issue 96): the loudness pass of the edit goes through the plugin ----------------

@pytest.fixture
def ad(tmp_path):
    from tm import create_config
    from tm.playbooks import CREATE_AD

    run = RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "rising ad", date(2026, 11, 12), playbook=CREATE_AD)
    config.save(run, create_config.defaults())
    return run


def _whisper_render(path, seconds=SECONDS):
    """A 540×960 render whose sound is loud for 3 s, then a whisper 20 dB under it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc2=size=540x960:rate=25:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={seconds}",
                    "-af", "volume=-8dB,volume=-20dB:enable='gte(t,3)'", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def _loudness_between(path, start, end):
    cut = path.with_name(f"cut_{start:g}_{end:g}.wav")
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-ss", str(start), "-t", str(end - start),
                    "-i", str(path), "-vn", str(cut)], check=True)
    return take_qa.loudness(cut)[0]


@pytest.mark.tools
def test_create_ad_finish_writes_the_next_edit_version(ad, capsys):
    _quiet_render(ad.path / "03_wip" / "edit_mix_v01.mp4")
    code, out = _tool(capsys, "finish", "--run", str(ad.path), "03_wip/edit_mix_v01.mp4")
    assert code == 0, out
    assert out["outputs"] == ["03_wip/edit_v01.mp4"] and abs(out["lufs"] - (-14)) <= 1 and out["peak"] <= -1.5
    assert out["lufs_target"] == -14
    rows = [r for r in manifest.rows(ad) if r["file"] == "03_wip/edit_v01.mp4"]
    assert rows and rows[-1]["source"] == "tm tool deliver finish"
    code, again = _tool(capsys, "finish", "--run", str(ad.path), "03_wip/edit_mix_v01.mp4")
    assert (code, again["outputs"]) == (0, ["03_wip/edit_v02.mp4"])


@pytest.mark.tools
def test_create_ad_finish_lifts_a_quiet_line(ad, capsys):
    """A timed gain brings a whisper up before the level is set: the quiet part ends far closer to the loud one."""
    render = _whisper_render(ad.path / "03_wip" / "edit_mix_v01.mp4")
    gap_before = _loudness_between(render, 0.2, 2.8) - _loudness_between(render, 3.2, 5.8)
    code, out = _tool(capsys, "finish", "--run", str(ad.path), "03_wip/edit_mix_v01.mp4", "--gain", "3-6:+18",
                      "--compress")
    assert code == 0, out
    edit = ad.path / "03_wip" / "edit_v01.mp4"
    gap_after = _loudness_between(edit, 0.2, 2.8) - _loudness_between(edit, 3.2, 5.8)
    assert gap_before > 18 and gap_after < 6, (gap_before, gap_after)
    assert out["gains"] == [{"start": 3.0, "end": 6.0, "db": 18.0}] and out["compress"] is True


def test_finish_gain_is_start_end_and_decibels():
    assert deliver.parse_gain("1.5-3.25:+9") == (1.5, 3.25, 9.0)
    assert deliver.parse_gain("0-2:-3") == (0.0, 2.0, -3.0)
    for bad in ("3-1:+9", "1-2", "a-b:+3", "1-2:+40"):
        with pytest.raises(c.ToolError):
            deliver.parse_gain(bad)


@pytest.mark.tools
def test_finish_needs_the_idea_in_organic_video_and_refuses_it_in_create_ad(ov, ad, capsys):
    _quiet_render(ov.path / "03_wip" / "M5" / "edit_v01_render.mp4")
    code, out = _tool(capsys, "finish", "--run", str(ov.path), "03_wip/M5/edit_v01_render.mp4")
    assert code == 1 and "--id" in out["message"]
    _quiet_render(ad.path / "03_wip" / "edit_mix_v01.mp4")
    code, out = _tool(capsys, "finish", "--run", str(ad.path), "03_wip/edit_mix_v01.mp4", "--id", "M5")
    assert code == 1 and "--id" in out["message"] and not (ad.path / "03_wip" / "edit_v01.mp4").exists()
