"""tm tool recut_qa: automatic QA of a rendered re-cut (port of handoff v03 tools/recut_qa.py).

The media is generated here with ffmpeg and numpy (HANDOFF 9b-2); whisper is replaced by a
word-timing fixture, so no model is ever downloaded.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from _media import ffmpeg

from tm import config
from tm.runfolder import slug
from tm.tools import recut_qa

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")

FPS = 25
SR = 22050


# ---- media -------------------------------------------------------------------------------

def _mux(path, video_args, wav=None, vf=None):
    argv = [ffmpeg(), "-nostdin", "-v", "error", "-y", *video_args]
    if wav is not None:
        argv += ["-i", str(wav)]
    if vf:
        argv += ["-vf", vf]
    argv += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p"]
    argv += (["-c:a", "aac", "-b:a", "192k", "-shortest"] if wav is not None else ["-an"])
    argv += [str(path)]
    subprocess.run(argv, check=True)
    return path


def _clicks(path, beats, seconds, fade_db=0.0, fade_s=4.0, step_db=0.0, step_at=None):
    """A pad (220 Hz) with a click on every beat time; the whole mix fades by fade_db over the last fade_s."""
    t = np.arange(int(seconds * SR)) / SR
    y = 0.1 * np.sin(2 * np.pi * 220 * t)
    for b in beats:
        i = int(b * SR)
        n = int(0.03 * SR)
        k = np.arange(min(n, len(y) - i))
        y[i:i + len(k)] += 0.8 * np.sin(2 * np.pi * 1500 * k / SR) * np.exp(-k / (0.006 * SR))
    ramp = np.clip((t - (seconds - fade_s)) / fade_s, 0, 1)
    y *= 10 ** (-fade_db * ramp / 20)
    if step_at is not None:
        y *= np.where(t >= step_at, 10 ** (-step_db / 20), 1.0)
    sf.write(str(path), y.astype(np.float32), SR)
    return path


def _music_video(tmp_path, name, beats, seconds, fade_db=0.0, **step):
    wav = _clicks(tmp_path / f"{name}.wav", beats, seconds, fade_db, **step)
    video = ["-f", "lavfi", "-i", f"testsrc2=size=180x320:rate={FPS}:duration={seconds}"]
    return _mux(tmp_path / f"{name}.mp4", video, wav)


def _beats(bpm, a, b):
    step = 60 / bpm
    return list(np.arange(a, b, step))


def _shots(tmp_path, name, plan):
    """Shots of testsrc2 in different looks, `plan` = [(look, frames)]; one video, 180x320 at 25 fps."""
    looks = {"A": "null", "B": "negate", "C": "hue=h=120", "D": "negate,hue=h=200"}
    parts = ";".join(f"[0:v]trim=start_frame=0:end_frame={n},setpts=PTS-STARTPTS,{looks[k]}[s{i}]"
                     for i, (k, n) in enumerate(plan))
    chain = "".join(f"[s{i}]" for i in range(len(plan))) + f"concat=n={len(plan)}:v=1:a=0[v]"
    out = tmp_path / f"{name}.mp4"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc2=size=180x320:rate={FPS}:duration=4", "-filter_complex", f"{parts};{chain}",
                    "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p",
                    "-an", str(out)], check=True)
    return out


def _sidecar(video, joints, length, audio_mode=None, video_spec=None, music_joints=None):
    spec = {"variant": "tighter", "video": video_spec or [{}, {}]}
    if audio_mode:
        spec["audio_mode"] = audio_mode
    side = {"spec": spec, "joints_s": joints, "length_s": length,
            "music_joints_s": joints if music_joints is None else music_joints}
    path = type(video)(str(video) + ".recut.json")
    path.write_text(json.dumps(side), encoding="utf-8")
    return path


def _qa(run, video, *extra, code=0):
    assert recut_qa.main(["--run", str(run.path), str(video), "--json", *extra]) == code


def _result(run, video, n=1):
    name = slug(video.stem)
    path = run.path / "03_wip" / "qa" / f"{name}_qa_v{n:02d}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _checks(result):
    return [f["check"] for f in result["flags"]]


def _words(monkeypatch, words):
    monkeypatch.setattr(recut_qa, "_words", lambda video, lang: words)


# ---- the checks --------------------------------------------------------------------------

def test_rc14_fade_before_end_flagged(run, tmp_path):
    video = _music_video(tmp_path, "fades", _beats(86, 0.2, 19.8), 20, fade_db=12)
    _qa(run, video)
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "fade_before_end")
    assert flag["at_s"] is None and "dB" in flag["detail"]
    assert res["measures"]["tail_vs_body_db"] < -6
    assert res["pass"] is False


def test_steady_music_passes(run, tmp_path):
    video = _music_video(tmp_path, "steady", _beats(86, 0.2, 19.8), 20)
    _qa(run, video)
    res = _result(run, video)
    assert res["flags"] == [] and res["pass"] is True
    assert res["measures"]["tail_vs_body_db"] > -6
    assert res["measures"]["tempo_bpm"] > 0


def test_tempo_drift_over_4_percent_flagged(run, tmp_path, monkeypatch):
    # librosa's tracker follows one tempo and smooths a change into a single grid (measured here:
    # drift 0.0 on this very track), so the beat times the clicks really have are given to the check
    beats = _beats(80, 0.2, 10.0) + _beats(100, 10.2, 19.9)
    monkeypatch.setattr(recut_qa, "beat_times", lambda y, sr: (90.0, np.array(beats)))
    video = _music_video(tmp_path, "drifts", beats, 20)
    _qa(run, video)
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "tempo_drift")
    assert "between the halves" in flag["detail"]
    assert res["measures"]["tempo_drift"] > 0.04


def test_thresholds_come_from_config(run, tmp_path):
    video = _music_video(tmp_path, "fades_a_little", _beats(86, 0.2, 19.8), 20, fade_db=12)
    y = recut_qa.c.decode_mono(video, SR)
    qa = {k: config.value(None, f"recut.qa.{k}") for k in
          ("music_joint_db", "beat_interval", "tempo_drift", "tail_db", "caption_flash_s")}
    flags, measures = recut_qa.music_checks(y, SR, [], qa)
    assert "fade_before_end" in [f["check"] for f in flags]
    # the same measure against a looser tail_db passes
    flags, _ = recut_qa.music_checks(y, SR, [], {**qa, "tail_db": -30})
    assert "fade_before_end" not in [f["check"] for f in flags]
    assert measures["tail_vs_body_db"] < -6


# the joint sits between two clicks (clicks at 0.2 + k * 0.6977 s), so the click itself is not the jump
J = 10.316


def test_music_joint_level_step_flagged(run, tmp_path):
    video = _music_video(tmp_path, "steps", _beats(86, 0.2, 19.8), 20, step_db=9, step_at=J)
    _sidecar(video, [], 20.0, music_joints=[J])
    _qa(run, video)
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "music_joint")
    assert flag["at_s"] == pytest.approx(J, abs=0.1) and "level jump" in flag["detail"]
    assert res["measures"]["music_joints"][0]["level_jump_db"] > 3


def test_music_joint_steady_music_passes(run, tmp_path):
    video = _music_video(tmp_path, "smooth", _beats(86, 0.2, 19.8), 20)
    _sidecar(video, [], 20.0, music_joints=[J])
    _qa(run, video)
    res = _result(run, video)
    assert "music_joint" not in _checks(res)
    assert res["measures"]["music_joints"][0]["flag"] is False


def test_music_joint_beat_interval_flagged(run, tmp_path, monkeypatch):
    # steady level, but the beat after the joint comes 0.4 s late: an interval 57 % over the median
    beats = [b for b in _beats(86, 0.2, J - 0.4)] + [J + 0.4 + k * 60 / 86 for k in range(14)]
    monkeypatch.setattr(recut_qa, "beat_times", lambda y, sr: (86.0, np.array(beats)))
    video = _music_video(tmp_path, "skips", _beats(86, 0.2, 19.8), 20)
    _sidecar(video, [], 20.0, music_joints=[J])
    _qa(run, video)
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "music_joint")
    assert "beat interval" in flag["detail"] and flag["at_s"] == pytest.approx(J, abs=0.1)
    assert res["measures"]["music_joints"][0]["level_jump_db"] < 3
    assert res["measures"]["music_joints"][0]["beat_interval_dev"] > 0.15


def test_audio_missing_flagged_when_the_edit_list_has_sound(run, tmp_path):
    video = _shots(tmp_path, "mute", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 4.0, video_spec=[{}, {}])
    side = json.loads(Path(str(video) + ".recut.json").read_text(encoding="utf-8"))
    side["spec"]["audio"] = [{"src": "music.wav", "from": 0, "to": 4}]
    Path(str(video) + ".recut.json").write_text(json.dumps(side), encoding="utf-8")
    _qa(run, video)
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "audio_missing")
    assert flag["at_s"] is None and res["pass"] is False


def test_audio_missing_not_flagged_when_the_edit_list_has_no_sound(run, tmp_path):
    video = _shots(tmp_path, "silent_by_design", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 4.0)  # spec: video only
    _qa(run, video)
    res = _result(run, video)
    assert "audio_missing" not in _checks(res) and res["pass"] is True


def test_script_not_checked_in_music_mode(run, tmp_path):
    video = _music_video(tmp_path, "musical", _beats(86, 0.2, 5.8), 6)
    _sidecar(video, [], 6.0)  # music mode: the sidecar has no audio_mode
    _qa(run, video, "--expected", "kup teraz", "--lang", "pl")
    res = _result(run, video)
    assert res["measures"]["script"] == "not checked: music mode"
    assert "script" not in _checks(res)
    _qa(run, video)
    assert "script" not in _result(run, video, 2)["measures"]


def test_rc15_one_frame_flash_flagged_and_fixed(run, tmp_path):
    # shot A, one frame of shot B, then shot C: the segment ended one frame after the change
    bad = _shots(tmp_path, "j1_v04", [("A", 50), ("B", 1), ("C", 50)])
    _sidecar(bad, [2.0], 4.04)
    _qa(run, bad)
    res = _result(run, bad)
    flag = next(f for f in res["flags"] if f["check"] == "one_frame_flash")
    assert flag["at_s"] == pytest.approx(2.0, abs=2 / FPS)
    assert res["pass"] is False and "length" not in _checks(res)
    # ended two frames earlier: a clean cut A -> C
    good = _shots(tmp_path, "j1_v05", [("A", 50), ("C", 50)])
    _sidecar(good, [2.0], 4.0)
    _qa(run, good)
    ok = _result(run, good)
    assert "one_frame_flash" not in _checks(ok)
    assert ok["pass"] is True


def test_strips_are_written_per_joint_and_versioned(run, tmp_path):
    video = _shots(tmp_path, "strips", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 4.0)
    _qa(run, video)
    _qa(run, video)
    folder = run.path / "03_wip" / "qa"
    assert (folder / "strips_strips_v01" / "joint1.png").stat().st_size > 0
    assert (folder / "strips_strips_v02" / "joint1.png").is_file()
    assert (folder / "strips_qa_v01.json").is_file() and (folder / "strips_qa_v02.json").is_file()
    rows = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "03_wip/qa/strips_qa_v02.json" in rows


def test_length_flagged_when_it_differs_from_the_sidecar(run, tmp_path):
    video = _shots(tmp_path, "short", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 5.0)
    _qa(run, video)
    flag = next(f for f in _result(run, video)["flags"] if f["check"] == "length")
    assert "5" in flag["detail"] and "4" in flag["detail"]


def _captioned(tmp_path, name):
    """Black picture with a white box per 'word' in a band: A 0-1.00 s, B 1.00-1.12 s (3 frames), C 1.12-2 s."""
    box = ("drawbox=x=40:y=240:w=100:h=40:color=white:t=fill:enable='between(t,0,0.999)',"
           "drawbox=x=40:y=240:w=50:h=40:color=white:t=fill:enable='between(t,1.0,1.119)',"
           "drawbox=x=40:y=240:w=130:h=40:color=white:t=fill:enable='gte(t,1.12)'")
    wav = tmp_path / f"{name}.wav"
    t = np.arange(2 * SR) / SR
    sf.write(str(wav), (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32), SR)
    video = ["-f", "lavfi", "-i", f"color=c=black:size=180x320:rate={FPS}:duration=2"]
    return _mux(tmp_path / f"{name}.mp4", video, wav, vf=box)


def test_caption_flash_flagged(run, tmp_path, monkeypatch):
    _words(monkeypatch, [])
    video = _captioned(tmp_path, "captions")
    _sidecar(video, [1.0], 2.0, audio_mode="sync")
    _qa(run, video, "--caption-band", "0,230,180,290")
    res = _result(run, video)
    flag = next(f for f in res["flags"] if f["check"] == "caption_flash")
    assert flag["at_s"] == pytest.approx(1.0, abs=0.1)
    assert res["measures"]["caption_switches"] == 2


def test_caption_flash_needs_a_short_caption(run, tmp_path, monkeypatch):
    _words(monkeypatch, [])
    video = _captioned(tmp_path, "captions_ok")
    _sidecar(video, [1.5], 2.0, audio_mode="sync")  # the joint is far from the 3-frame word
    _qa(run, video, "--caption-band", "0,230,180,290")
    assert "caption_flash" not in _checks(_result(run, video))


def _speech_clip(tmp_path, name, audio_tail=None):
    path = _shots(tmp_path, name, [("A", 25), ("C", 25)])
    segs = [{"audio_tail": audio_tail} if audio_tail else {}, {}]
    _sidecar(path, [1.0], 2.0, audio_mode="sync", video_spec=segs)
    return path


def test_word_across_fade_flagged_and_tail_passes(run, tmp_path, monkeypatch):
    # the word "dzień" runs from 0.90 to 1.20 s over the joint at 1.0 s
    _words(monkeypatch, [{"w": "dzień", "s": 0.9, "e": 1.2}, {"w": "dobry", "s": 1.4, "e": 1.7}])
    cut = _speech_clip(tmp_path, "cuts_a_word")
    _qa(run, cut)
    res = _result(run, cut)
    flag = next(f for f in res["flags"] if f["check"] == "word_across_fade")
    assert "dzień" in flag["detail"] and flag["at_s"] == pytest.approx(1.0, abs=0.05)
    # an audio_tail (L-cut) that covers the word lets it run on: no flag
    kept = _speech_clip(tmp_path, "keeps_the_word", audio_tail=0.4)
    _qa(run, kept)
    assert "word_across_fade" not in _checks(_result(run, kept))


def test_script_flags_only_above_ten_percent_missing(run, tmp_path, monkeypatch):
    video = _speech_clip(tmp_path, "script")
    said = "kup teraz nasz nowy ebook o zimie dziś dla was".split()
    _words(monkeypatch, [{"w": w, "s": 0.1 * i, "e": 0.1 * i + 0.05} for i, w in enumerate(said)])
    # 1 of 11 expected words is missing: 9 %, no flag
    _qa(run, video, "--expected", " ".join(said) + " link")
    one = _result(run, video, 1)
    assert "script" not in _checks(one) and one["measures"]["missing_words"] == ["link"]
    # 2 of 12: 17 %, flagged
    _qa(run, video, "--expected", " ".join(said) + " link bonus")
    two = _result(run, video, 2)
    flag = next(f for f in two["flags"] if f["check"] == "script")
    assert flag["at_s"] is None and "2" in flag["detail"]
    # everything heard: nothing missing or extra
    _qa(run, video, "--expected", " ".join(said))
    three = _result(run, video, 3)
    assert three["measures"]["missing_words"] == [] and three["measures"]["extra_words"] == []


def test_loudness_against_the_original(run, tmp_path):
    loud = _music_video(tmp_path, "loud", _beats(86, 0.2, 5.8), 6)
    quiet = tmp_path / "quiet.mp4"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-i", str(loud), "-af", "volume=-9dB",
                    "-c:v", "copy", str(quiet)], check=True)
    _qa(run, quiet, "--original", str(loud))
    res = _result(run, quiet)
    flag = next(f for f in res["flags"] if f["check"] == "loudness")
    assert "LU" in flag["detail"]
    assert res["measures"]["loudness_lufs"] < res["measures"]["original_loudness_lufs"] - 5
    _qa(run, loud, "--original", str(loud))
    assert "loudness" not in _checks(_result(run, loud))


# ---- the tool's contract -----------------------------------------------------------------

def test_output_shape_and_json_answer(run, tmp_path, capsys):
    video = _shots(tmp_path, "shape", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 4.0)
    _qa(run, video)
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "done" and printed["pass"] is True
    assert printed["outputs"][0] == "03_wip/qa/shape_qa_v01.json"
    res = _result(run, video)
    assert set(res) == {"pass", "flags", "measures"}
    assert res["measures"]["duration_s"] == pytest.approx(4.0, abs=0.1)
    assert res["measures"]["picture_joints"] == [2.0]


def test_explicit_sidecar_and_missing_files(run, tmp_path, capsys):
    video = _shots(tmp_path, "lonely", [("A", 50), ("C", 50)])
    side = tmp_path / "elsewhere.recut.json"
    side.write_text(json.dumps({"joints_s": [2.0], "length_s": 4.0}), encoding="utf-8")
    _qa(run, video, "--sidecar", str(side))
    assert _result(run, video)["measures"]["picture_joints"] == [2.0]
    capsys.readouterr()
    assert recut_qa.main(["--run", str(run.path), str(tmp_path / "nope.mp4"), "--json"]) == 1
    assert "nope.mp4" in json.loads(capsys.readouterr().out)["message"]
    assert recut_qa.main(["--run", str(run.path), str(video), "--sidecar", str(tmp_path / "x.json"),
                          "--json"]) == 1


def test_never_overwrites_an_existing_strips_folder(run, tmp_path, capsys):
    video = _shots(tmp_path, "keep", [("A", 50), ("C", 50)])
    _sidecar(video, [2.0], 4.0)
    folder = run.path / "03_wip" / "qa" / "keep_strips_v01"
    folder.mkdir(parents=True)
    (folder / "mine.txt").write_text("mine", encoding="utf-8")
    assert recut_qa.main(["--run", str(run.path), str(video), "--json"]) == 1
    assert "never overwritten" in json.loads(capsys.readouterr().out)["message"]
    assert (folder / "mine.txt").read_text(encoding="utf-8") == "mine"
    assert not (run.path / "03_wip" / "qa" / "keep_qa_v01.json").exists()


def test_importing_the_module_runs_nothing():
    # the handoff script parsed its arguments at import time; the port has main() only
    assert callable(recut_qa.main) and callable(recut_qa.music_checks)
