"""tm tool recut: render a checked edit list (port of handoff v03 tools/recut.py)."""

from __future__ import annotations

import json
import subprocess

import pytest
from _media import W, H, ffmpeg, gray_frame, make_clip

from tm.tools import recut

pytest.importorskip("numpy")
pytest.importorskip("soundfile")

FPS = 25
DROP = object()  # _edit(key=DROP) leaves the key out of the edit list
CLICK_AT = 2.0  # the click sits at the first frame of shot B in the source


def _source(folder, name="Źródło wideo.mp4"):
    """4 s: shot A (0-2 s, testsrc2) and shot B (2-4 s, another pattern), a 1 kHz click at 2.0 s."""
    folder.mkdir(parents=True, exist_ok=True)
    a = make_clip(folder / "a.mp4", vf="null", seconds=2, tone=False)
    b = make_clip(folder / "b.mp4", vf="negate,hue=h=120", seconds=2, tone=False)
    out = folder / name
    click = f"aevalsrc='if(between(t,{CLICK_AT},{CLICK_AT + 0.01}),0.8*sin(2*PI*1000*t),0)':s=44100:d=4"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-i", str(a), "-i", str(b), "-f", "lavfi", "-i", click,
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
                   check=True)
    return out


def _teardown(path, video=None):
    td = {"fps": FPS, "width": W, "height": H, "frame_count": 100, "duration_s": 4.0,
          "scenes": [{"start_frame": 0, "start_s": 0.0, "end_frame": 49},
                     {"start_frame": 50, "start_s": 2.0, "end_frame": 99}]}
    if video:
        td["video"] = video
    path.write_text(json.dumps(td), encoding="utf-8")
    return path


def _edit(run, src, **kw):
    """A sync-mode edit list: shot A 0-1.5 s, then shot B from the click, 2.0-3.5 s."""
    folder = run.path / "03_wip" / "recut"
    folder.mkdir(parents=True, exist_ok=True)
    rel = "../../01_base/" + src.name
    edit = {"variant": "tighter", "change_id": "recut_shorter", "level": 0, "cause": "dead air",
            "music_source": "sync", "audio_mode": "sync", "fps": FPS, "width": W, "height": H,
            "video": [{"src": rel, "from": 0.0, "to": 1.5}, {"src": rel, "from": 2.0, "to": 3.5}]}
    edit.update(kw)
    edit = {k: v for k, v in edit.items() if v is not DROP}
    path = folder / "tighter_v01.json"
    path.write_text(json.dumps(edit), encoding="utf-8")
    return path


def _music_edit(run, src, audio=None, **kw):
    """A non-sync edit list: the music is its own `audio` list (the source's sound by default)."""
    audio = audio or [{"src": "../../01_base/" + src.name, "from": 0.0, "to": 3.0}]
    return _edit(run, src, audio_mode=DROP, music_source="original_file", audio=audio, **kw)


def _wav(path, expr, seconds, channels=2):
    """A wav made from an aevalsrc expression (44.1 kHz)."""
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}':s=44100:d={seconds}", "-ac", str(channels), str(path)], check=True)
    return path


def _rms(sig, a, b):
    import numpy as np

    part = sig[int(a * 48000): int(b * 48000)]
    return float(np.sqrt(np.mean(part ** 2))) if len(part) else 0.0


def _onset(sig, level=0.3):
    return next(i for i, v in enumerate(sig) if abs(v) > level) / 48000


def _setup(run, tmp_path):
    base = run.path / "01_base"
    base.mkdir(exist_ok=True)
    src = _source(tmp_path / "media")
    inside = base / src.name
    inside.write_bytes(src.read_bytes())
    return inside, _teardown(tmp_path / "td.json")


def _go(run, edit, td, *extra):
    return recut.main(["--run", str(run.path), str(edit), "--teardown", str(td), "--json", *extra])


def _mono(video):
    import numpy as np

    raw = subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "48000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _duration(video):
    return float(subprocess.run([ffmpeg().replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
                                 "format=duration", "-of", "csv=p=0", str(video)],
                                capture_output=True, text=True, check=True).stdout.strip())


def test_two_shot_cut_at_the_change(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    edit = _music_edit(run, src)
    assert _go(run, edit, td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    assert out.is_file()
    # each 1.5 s segment is 37.5 frames, rendered as 38: the joint lands within a frame of 1.5 s
    assert side["joints_s"] == pytest.approx([1.5], abs=1 / FPS)
    assert side["length_s"] == pytest.approx(3.0, abs=2 / FPS)
    assert side["picture_len_s"] == pytest.approx(3.0, abs=2 / FPS)
    assert side["spec"]["variant"] == "tighter"
    # the picture really changes shot at the joint: frame 37 (shot A) differs from frame 38 (shot B)
    _, _, before = gray_frame(out, 36)
    _, _, after = gray_frame(out, 39)
    diff = sum(abs(x - y) for x, y in zip(before[::97], after[::97])) / len(before[::97])
    assert diff > 20
    rows = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "04_final/tighter_v01.mp4 " in rows and "tighter_v01.mp4.recut.json" in rows
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "done" and printed["outputs"][0] == "04_final/tighter_v01.mp4"


def test_sync_mode_keeps_lips(run, tmp_path):
    src, td = _setup(run, tmp_path)
    assert _go(run, _edit(run, src), td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    sig = _mono(out)
    onset = next(i for i, v in enumerate(sig) if abs(v) > 0.3) / 48000
    # the click is the first thing of segment 2, so it belongs at the joint (1.5 s) in the output
    assert abs(onset - 1.5) <= 1 / FPS
    assert _duration(out) == pytest.approx(3.0, abs=2 / FPS)


def test_audio_tail_l_cut(run, tmp_path):
    src, td = _setup(run, tmp_path)
    # the click (2.0 s) is the tail of segment 1: segment 1 ends at 1.5 s, so let it run on 0.6 s
    rel = "../../01_base/" + src.name
    edit = _edit(run, src, video=[{"src": rel, "from": 0.0, "to": 1.5, "audio_tail": 0.0},
                                  {"src": rel, "from": 2.1, "to": 3.5}])
    # without a tail the click (2.0) is cut away; with segment 1 reading to 2.2 s it plays under shot B
    data = json.loads(edit.read_text())
    data["video"][0]["audio_tail"] = 0.7
    edit.write_text(json.dumps(data))
    assert _go(run, edit, td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    sig = _mono(out)
    onset = next((i for i, v in enumerate(sig) if abs(v) > 0.3), None)
    assert onset is not None  # the tail carried the click across the joint
    assert abs(onset / 48000 - (1.5 + 0.5)) <= 1 / FPS  # source 2.0 s = 0.5 s after segment 1's end


def test_refuses_an_edit_list_that_fails_check(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    edit = _edit(run, src, variant="")
    assert _go(run, edit, td) == 2
    msg = json.loads(capsys.readouterr().out)
    assert msg["status"] == "refused" and "variant" in " ".join(msg["problems"])
    assert "same place" in msg["message"]
    assert not (run.path / "04_final").exists() or not list((run.path / "04_final").glob("*.mp4"))
    assert not list(run.path.rglob("*.recut.json"))


def test_recut_paths_with_spaces_and_non_ascii(run, tmp_path):
    src, td = _setup(run, tmp_path)
    assert " " in src.name and "Ź" in src.name
    assert _go(run, _edit(run, src), td) == 0
    assert (run.path / "04_final" / "tighter_v01.mp4").stat().st_size > 1000


def test_rerender_writes_next_version(run, tmp_path):
    src, td = _setup(run, tmp_path)
    edit = _edit(run, src)
    assert _go(run, edit, td) == 0
    assert _go(run, edit, td) == 0
    final = run.path / "04_final"
    assert (final / "tighter_v01.mp4").is_file() and (final / "tighter_v02.mp4").is_file()
    assert (final / "tighter_v02.mp4.recut.json").is_file()


def _rel(src):
    return "../../01_base/" + src.name


def test_dissolve_seam_overlaps_the_pictures(run, tmp_path):
    src, td = _setup(run, tmp_path)
    edit = _music_edit(run, src, video=[{"src": _rel(src), "from": 0.0, "to": 1.5},
                                        {"src": _rel(src), "from": 2.0, "to": 3.5, "seam": "dissolve",
                                         "seam_frames": 10}])
    assert _go(run, edit, td) == 0
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    # 2 x 1.52 s, minus the 10-frame (0.4 s) overlap; the joint is the middle of the dissolve
    assert side["length_s"] == pytest.approx(2.64, abs=0.001)
    assert side["picture_len_s"] == pytest.approx(2.64, abs=2 / FPS)
    assert side["joints_s"] == pytest.approx([1.32], abs=0.001)
    assert _duration(run.path / "04_final" / "tighter_v01.mp4") == pytest.approx(2.64, abs=3 / FPS)


def test_audio_head_j_cut_plays_the_next_sound_early(run, tmp_path):
    src, td = _setup(run, tmp_path)
    rel = _rel(src)
    # shot B starts at 2.1 s; its sound starts 0.3 s earlier (1.8 s), so the click (2.0 s) is heard
    # 0.2 s into the read, i.e. 0.1 s before the picture joint at 1.52 s
    edit = _edit(run, src, video=[{"src": rel, "from": 0.0, "to": 1.5},
                                  {"src": rel, "from": 2.1, "to": 3.5, "audio_head": 0.3}])
    assert _go(run, edit, td) == 0
    sig = _mono(run.path / "04_final" / "tighter_v01.mp4")
    assert _onset(sig) == pytest.approx(1.52 - 0.3 + 0.2, abs=1 / FPS)


def test_audio_src_takes_the_sound_from_another_file(run, tmp_path):
    src, td = _setup(run, tmp_path)
    other = _wav(run.path / "01_base" / "Inny dźwięk.wav",
                 "if(between(t,0.5,0.51),0.8*sin(2*PI*1000*t),0)", 3)
    rel = _rel(src)
    # shot B from 2.5 s has no click of its own; the other file's click (0.5 s) is 0.1 s into audio_from 0.4
    edit = _edit(run, src, video=[{"src": rel, "from": 0.0, "to": 1.5},
                                  {"src": rel, "from": 2.5, "to": 3.9, "audio_src": _rel(other),
                                   "audio_from": 0.4}])
    assert _go(run, edit, td) == 0
    sig = _mono(run.path / "04_final" / "tighter_v01.mp4")
    assert _onset(sig) == pytest.approx(1.52 + 0.1, abs=1 / FPS)


@pytest.mark.parametrize("channels, peak", [(1, 0.354), (2, 0.25)])  # -6 dB of 0.5, as ffmpeg downmixes it
def test_extra_audio_is_mixed_at_its_time_with_its_gain(run, tmp_path, channels, peak):
    src, td = _setup(run, tmp_path)
    layer = _wav(run.path / "01_base" / f"lektor {channels}.wav", "0.5*sin(2*PI*500*t)", 0.3, channels)
    edit = _music_edit(run, src, extra_audio=[{"src": _rel(layer), "at": 0.5, "gain_db": -6}])
    assert _go(run, edit, td) == 0
    sig = _mono(run.path / "04_final" / "tighter_v01.mp4")
    import numpy as np

    assert _rms(sig, 0.0, 0.4) < 0.01                      # silent before the layer
    assert _rms(sig, 0.6, 0.7) > 0.1                       # audible at `at`
    assert _rms(sig, 1.0, 1.4) < 0.01                      # and only there
    assert float(np.max(np.abs(sig[int(0.55 * 48000): int(0.75 * 48000)]))) == pytest.approx(peak, abs=0.05)


def test_music_longer_than_the_picture_is_trimmed_with_a_tail_fade(run, tmp_path):
    src, td = _setup(run, tmp_path)
    tone = _wav(run.path / "01_base" / "tone.wav", "0.5*sin(2*PI*440*t)", 8)
    edit = _music_edit(run, src, audio=[{"src": _rel(tone), "from": 0.0, "to": 6.0}])
    assert _go(run, edit, td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    assert side["music_len_before_trim_s"] == pytest.approx(6.0, abs=0.01)
    assert _duration(out) == pytest.approx(side["picture_len_s"], abs=3 / FPS)  # trimmed to the picture
    sig = _mono(out)
    assert _rms(sig, 1.0, 1.2) > 0.25
    assert _rms(sig, side["picture_len_s"] - 0.06, side["picture_len_s"] - 0.01) < 0.3 * _rms(sig, 1.0, 1.2)


def test_music_shorter_than_the_picture_is_padded_with_silence(run, tmp_path):
    src, td = _setup(run, tmp_path)
    tone = _wav(run.path / "01_base" / "tone.wav", "0.5*sin(2*PI*440*t)", 8)
    edit = _music_edit(run, src, audio=[{"src": _rel(tone), "from": 0.0, "to": 1.0}])
    assert _go(run, edit, td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    assert side["music_len_before_trim_s"] == pytest.approx(1.0, abs=0.01)
    sig = _mono(out)
    assert _rms(sig, 0.3, 0.6) > 0.25
    assert _rms(sig, 1.3, 2.9) < 0.01
    assert _duration(out) == pytest.approx(side["picture_len_s"], abs=3 / FPS)  # the picture's length stays


def test_single_segment_edit(run, tmp_path):
    src, td = _setup(run, tmp_path)
    edit = _music_edit(run, src, video=[{"src": _rel(src), "from": 0.0, "to": 1.5}],
                       audio=[{"src": _rel(src), "from": 0.0, "to": 1.5}])
    assert _go(run, edit, td) == 0
    out = run.path / "04_final" / "tighter_v01.mp4"
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    assert side["joints_s"] == [] and side["segment_lens_s"] == pytest.approx([1.52])
    assert _duration(out) == pytest.approx(1.52, abs=3 / FPS)
    w, h, raw = gray_frame(out, 10)
    assert (w, h) == (W, H) and len(raw) == W * H


def _set_run(run, **fields):
    from tm import state

    s = state.load(run)
    for key, value in fields.items():
        setattr(s, key, value)
    state.save(run, s)


def _no_outputs(run):
    final = run.path / "04_final"
    return not final.exists() or not list(final.iterdir())


def test_waits_for_a_budget_that_is_not_approved(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    edit = _music_edit(run, src, level=3)
    assert _go(run, edit, td) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "waiting" and "ai_usd" in " ".join(out["problems"])
    assert "same place" in out["message"]
    assert _no_outputs(run)


def test_waits_above_the_level_hands_off_allows(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    _set_run(run, level="hands_off", budgets={"ai_usd": 5})
    edit = _music_edit(run, src, level=3)
    assert _go(run, edit, td) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "waiting" and "recut.max_level" in " ".join(out["problems"])
    assert _no_outputs(run)


def test_never_overwrites_an_existing_sidecar(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    final = run.path / "04_final"
    final.mkdir(exist_ok=True)
    old = final / "mine.mp4.recut.json"
    old.write_text("keep me", encoding="utf-8")
    assert _go(run, _edit(run, src), td, "--out", "04_final/mine.mp4") == 1
    msg = json.loads(capsys.readouterr().out)
    assert "mine.mp4.recut.json" in msg["message"] and "never overwritten" in msg["message"]
    assert old.read_text(encoding="utf-8") == "keep me"
    assert not (final / "mine.mp4").exists()


# --- PR B fix wave --------------------------------------------------------------------------

def _clip(path, seconds, rate, size="160x284"):
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc2=size={size}:rate={rate}:duration={seconds}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.mark.parametrize("a, b, speed", [(0, 11.146, 1), (5.0, 7.777, 1), (3.3, 6.71, 1.5)])
def test_the_render_has_exactly_checks_frames_and_joints(run, tmp_path, a, b, speed):
    """The reviewer's probe: at 29.952 fps ffmpeg's fps filter makes one frame more than check counts."""
    from tm import recut_plan

    base = run.path / "01_base"
    base.mkdir(exist_ok=True)
    _clip(base / "a.mp4", 14, 29.952)
    _clip(base / "veo.mp4", 2, 30)
    music = _wav(base / "m.wav", "0.2*sin(2*PI*440*t)", 14)
    td = tmp_path / "td.json"
    td.write_text(json.dumps({"fps": 29.952, "frame_count": 419, "video": "01_base/a.mp4",
                              "scenes": [{"start_frame": 0, "start_s": 0.0, "end_frame": 418}]}), encoding="utf-8")
    edit = _music_edit(run, base / "a.mp4", width=160, height=284, fps=30, level=4,
                       video=[{"src": "../../01_base/a.mp4", "from": a, "to": b, "speed": speed},
                              {"src": "../../01_base/veo.mp4", "from": 0.0, "to": 1.0}],
                       audio=[{"src": _rel(music), "from": 0.0, "to": 13.0}])
    _set_run(run, budgets={"ai_usd": 1.0})
    assert _go(run, edit, td) == 0
    spec = json.loads(edit.read_text(encoding="utf-8"))
    verdict = recut_plan.check(spec, json.loads(td.read_text()), None, None, mode="hitl", approved={"ai_usd"},
                               base=run.path, edit_dir=edit.parent)
    tl = recut_plan.timeline(spec)
    out = run.path / "04_final" / "tighter_v01.mp4"
    side = json.loads((run.path / "04_final" / "tighter_v01.mp4.recut.json").read_text(encoding="utf-8"))
    assert side["segment_frames"] == tl.frames
    assert recut._frames(out) == sum(tl.frames)  # a cut joint: the segments end to end
    assert side["joints_s"] == verdict.joints_s == tl.joints_s
    assert side["length_s"] == verdict.length_s


def test_a_dissolve_in_sync_mode_is_refused_by_the_tool(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    rel = _rel(src)
    edit = _edit(run, src, video=[{"src": rel, "from": 0.0, "to": 1.5},
                                  {"src": rel, "from": 2.0, "to": 3.5, "seam": "dissolve", "seam_frames": 6}])
    assert _go(run, edit, td) == 2
    assert any("cut instead" in p for p in json.loads(capsys.readouterr().out)["problems"])
    assert _no_outputs(run)


def test_extra_audio_keeps_its_sample_rate(run, tmp_path):
    import numpy as np

    src, td = _setup(run, tmp_path)
    layer = _wav(run.path / "01_base" / "tts 44k.wav", "0.5*sin(2*PI*500*t)", 0.3, 1)  # 44.1 kHz
    edit = _music_edit(run, src, extra_audio=[{"src": _rel(layer), "at": 0.5}])
    assert _go(run, edit, td) == 0
    sig = _mono(run.path / "04_final" / "tighter_v01.mp4")
    part = sig[int(0.3 * 48000): int(1.2 * 48000)]
    loud = np.nonzero(np.abs(part) > 0.2)[0]
    length = (loud[-1] - loud[0]) / 48000
    assert length == pytest.approx(0.3, abs=0.001)
    tone = part[loud[0]: loud[-1]]
    crossings = np.count_nonzero(np.diff(np.signbit(tone)))
    assert crossings / 2 / length == pytest.approx(500, abs=5)


def test_a_backslash_src_renders(run, tmp_path):
    src, td = _setup(run, tmp_path)
    win = "..\\..\\01_base\\" + src.name  # an edit list written on Windows
    edit = _music_edit(run, src, video=[{"src": win, "from": 0.0, "to": 1.5}, {"src": win, "from": 2.0, "to": 3.5}],
                       audio=[{"src": win, "from": 0.0, "to": 3.0}])
    assert _go(run, edit, td) == 0
    assert (run.path / "04_final" / "tighter_v01.mp4").stat().st_size > 1000


def test_a_refused_render_names_the_edit_list_not_its_path(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    edit = _edit(run, src, variant="")
    assert _go(run, edit, td) == 2
    message = json.loads(capsys.readouterr().out)["message"]
    assert message.startswith("03_wip/recut/tighter_v01.json was refused") and str(tmp_path) not in message


def test_the_tool_records_its_check_in_run_json(run, tmp_path, capsys):
    from tm import state

    src, td = _setup(run, tmp_path)
    assert _go(run, _edit(run, src), td) == 0
    assert _go(run, _edit(run, src, variant=""), td) == 2
    checked = state.load(run).recut["checked"]
    assert [(c["edit"], c["status"]) for c in checked] == [("03_wip/recut/tighter_v01.json", "ok"),
                                                           ("03_wip/recut/tighter_v01.json", "refused")]
    assert checked[0]["joints_s"] == [1.52] and checked[0]["audio_mode"] == "sync"


def test_extra_audio_past_the_end_is_refused_before_rendering(run, tmp_path, capsys):
    src, td = _setup(run, tmp_path)
    layer = _wav(run.path / "01_base" / "vo.wav", "0.5*sin(2*PI*500*t)", 0.3)
    edit = _music_edit(run, src, extra_audio=[{"src": _rel(layer), "at": 9.0}])
    assert _go(run, edit, td) == 2
    assert any("extra_audio" in p for p in json.loads(capsys.readouterr().out)["problems"])
    assert _no_outputs(run)


def test_the_recut_tools_share_one_reader():
    import inspect

    from tm import recut_plan
    from tm.tools import recut_qa, segment_map

    for mod in (recut_plan, recut, recut_qa, segment_map):
        text = inspect.getsource(mod)
        for private in ("def _resolve(", "def _read(", "def decode_mono(", "from tm.tools.recut_qa import"):
            assert private not in text, f"{mod.__name__} still has {private}"


# --- PR B fix wave, round 2 -----------------------------------------------------------------

def test_a_done_run_is_neither_checked_nor_rendered(run, tmp_path, capsys):
    from tm import state

    src, td = _setup(run, tmp_path)
    edit = _edit(run, src)
    _set_run(run, status="done")
    assert _go(run, edit, td) == 1
    msg = json.loads(capsys.readouterr().out)
    assert msg["status"] == "error" and "done" in msg["message"]
    assert state.load(run).recut is None or not state.load(run).recut.get("checked")
    assert _no_outputs(run)


def test_the_picture_keeps_the_exact_fps(run, tmp_path, monkeypatch):
    src, td = _setup(run, tmp_path)
    edit = _music_edit(run, src, fps=30000 / 1001)
    seen = []

    def stop(args):
        seen.append(args)
        raise RuntimeError("stop after the first segment")

    monkeypatch.setattr(recut.c, "run_ffmpeg", stop)
    assert _go(run, edit, td) == 1
    vf = seen[0][seen[0].index("-vf") + 1]
    assert f"fps={30000 / 1001:.10g}," in vf and "fps=29.97," not in vf
