"""tm tool segment_map: retention steps mapped to seconds of the ad's file (step CR1).

The media is generated here with ffmpeg; no model is used (the transcript is a fixture file).
"""

from __future__ import annotations

import json
import subprocess

import pytest
from _media import ffmpeg

from tm import state
from tm.tools import segment_map

pytest.importorskip("numpy")

LADDER = {"peak": {"p25/play": 0.7, "p50/p25": 0.8, "p75/p50": 0.9, "p95/p75": 0.8, "p100/p95": 0.9},
          "latest": {"p25/play": 0.7, "p50/p25": 0.7, "p75/p50": 0.5, "p95/p75": 0.6, "p100/p95": 0.9},
          "dropped": ["p75/p50"]}


def _video(path, seconds, still_from=None, tone=True):
    """Moving testsrc2; from still_from on, one frozen frame. A 440 Hz tone for the first half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if still_from is None:
        src = f"testsrc2=size=320x568:rate=10:duration={seconds}"
        graph = []
    else:
        src = f"testsrc2=size=320x568:rate=10:duration={still_from}"
        graph = ["-vf", f"tpad=stop_mode=clone:stop_duration={seconds - still_from}"]
    argv = [ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", src]
    if tone:
        argv += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={seconds}"]
    argv += [*graph, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    argv += (["-c:a", "aac", "-t", str(seconds)] if tone else ["-an", "-t", str(seconds)])
    argv += [str(path)]
    subprocess.run(argv, check=True)
    return path


def _teardown(path, overlays, video="01_base/ad.mp4"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"video": video, "overlays": [
        {"start_s": s, "end_s": e} for s, e in overlays]}), encoding="utf-8")
    return path


def _transcript(path, starts):
    path.parent.mkdir(parents=True, exist_ok=True)
    words = [{"start": s, "end": s + 0.2, "word": "x", "probability": 1.0} for s in starts]
    path.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": "x", "words": words}]}),
                    encoding="utf-8")
    return path


def _diagnose(run, ladder=LADDER, structural=None):
    st = state.load(run)
    st.diagnosis = {"ladder": ladder, **({"structural": structural} if structural else {})}
    state.save(run, st)


def _go(run, video, teardown, transcript=None, capsys=None):
    argv = ["--run", str(run.path), str(video), "--teardown", str(teardown), "--json"]
    if transcript:
        argv += ["--transcript", str(transcript)]
    assert segment_map.main(argv) == 0
    return json.loads(capsys.readouterr().out)


def test_steps_map_to_seconds(run, tmp_path, monkeypatch, capsys):
    video = _video(tmp_path / "ad.mp4", 4)
    monkeypatch.setattr(segment_map.c, "probe", lambda p: {"is_video": True, "has_audio": True, "fps": 10.0,
                                                          "width": 320, "height": 568, "duration": 24.149})
    monkeypatch.setattr(segment_map, "_visual", lambda *a, **k: [])
    monkeypatch.setattr(segment_map, "_loudness", lambda *a, **k: [])
    teardown = _teardown(tmp_path / "t.json", [])
    _diagnose(run)
    out = _go(run, video, teardown, capsys=capsys)
    steps = {s["step"]: s for s in out["steps"]}
    assert (steps["p75/p50"]["from_s"], steps["p75/p50"]["to_s"]) == (12.07, 18.11)
    assert (steps["p25/play"]["from_s"], steps["p100/p95"]["to_s"]) == (0.0, 24.15)
    assert steps["p75/p50"]["latest"] == 0.5 and steps["p75/p50"]["peak"] == 0.9
    assert out["weakest"] == "p75/p50"


def test_visual_change_drops_on_a_still_segment(run, tmp_path, capsys):
    video = _video(tmp_path / "ad.mp4", 24, still_from=12)
    teardown = _teardown(tmp_path / "t.json", [])
    out = _go(run, video, teardown, capsys=capsys)
    steps = {s["step"]: s for s in out["steps"]}
    moving = steps["p25/play"]["visual_change"]
    still = steps["p75/p50"]["visual_change"]  # 12.0 to 18.0: all still
    assert moving > 1 and still < 0.1 * moving
    assert len(out["visual_change_0p5s"]) >= 40 and out["visual_change_0p5s"][0][0] == 0.0
    assert steps["p25/play"]["peak"] is None and out["weakest"] is None  # no diagnosis
    assert steps["p25/play"]["loudness_db"] > -30 and steps["p25/play"]["speech_words"] is None


def test_last_new_info_is_the_last_card(run, tmp_path, capsys):
    video = _video(tmp_path / "ad.mp4", 8, tone=False)
    teardown = _teardown(tmp_path / "t.json", [(0.5, 2.0), (3.0, 3.5), (6.0, 7.0)])
    transcript = _transcript(tmp_path / "x.json", [0.4, 5.0, 5.5])
    out = _go(run, video, teardown, transcript, capsys)
    assert out["last_new_info_s"] == 6.0
    steps = {s["step"]: s for s in out["steps"]}
    assert steps["p25/play"]["cards"] == [0] and steps["p50/p25"]["cards"] == [1]  # 0-2, 2-4
    assert steps["p95/p75"]["cards"] == [2] and steps["p25/play"]["speech_words"] == 1
    assert steps["p25/play"]["loudness_db"] == -90.0  # no audio track: silence floor


def test_weakest_falls_back_to_structural_then_null(run, tmp_path, capsys):
    video = _video(tmp_path / "ad.mp4", 4)
    teardown = _teardown(tmp_path / "t.json", [])
    _diagnose(run, ladder={}, structural={"step": "p95/p75", "segment_s": [3.0, 3.8]})
    out = _go(run, video, teardown, capsys=capsys)
    assert out["weakest"] == "p95/p75" and out["steps"][2]["latest"] is None


def test_weakest_follows_the_diagnosis_dropped_step_then_structural_then_the_rate():
    lowest_late = {**LADDER["latest"], "p95/p75": 0.4}  # the lowest rate is p95/p75
    dropped = segment_map.build(24.0, {"ladder": {**LADDER, "latest": lowest_late,
                                                  "dropped": ["p25/play", "p75/p50"]}}, [], None, [], [])
    assert dropped["weakest"] == "p75/p50" and dropped["dropped"] == ["p25/play", "p75/p50"]
    structural = segment_map.build(24.0, {"ladder": {**LADDER, "latest": lowest_late, "dropped": []},
                                          "structural": {"step": "p50/p25"}}, [], None, [], [])
    assert structural["weakest"] == "p50/p25" and structural["dropped"] == []
    rate = segment_map.build(24.0, {"ladder": {**LADDER, "latest": lowest_late, "dropped": ["p100/p95"]}},
                             [], None, [], [])
    assert rate["weakest"] == "p95/p75"
    assert segment_map.build(24.0, None, [], None, [], [])["dropped"] == []


def test_visual_change_keeps_only_the_frames_it_needs(monkeypatch):
    import tracemalloc

    import numpy as np

    def frames(*a, **k):  # 600 frames of 180x320, each one grey level brighter than the last
        for i in range(600):
            yield np.full((320, 180), i % 200, np.uint8)

    monkeypatch.setattr(segment_map.c, "decode", frames)
    tracemalloc.start()
    out = segment_map._visual("x.mp4", 10.0, 180, 320)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert out[:2] == [[0.0, 5.0], [0.5, 5.0]] and len(out) == 119
    assert peak < 5_000_000, f"{peak} bytes: every frame was kept"
