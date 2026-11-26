"""ffprobe's JSON answer read again when it comes back cut short: on the CI's Windows runner ffprobe now and then
exits 0 without its closing brace, and `probe` stopped with "Expecting ',' delimiter" (the layer_check tests, 1 run
in about 60)."""

from __future__ import annotations

import json
import subprocess

import pytest

from tm.tools import _common as c

ANSWER = json.dumps({"streams": [{"codec_type": "video", "width": 540, "height": 960, "avg_frame_rate": "25/1",
                                  "duration": "4.000000", "nb_frames": "100"}],
                     "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "4.000000"}}, indent=4)
CUT = ANSWER.rsplit("}", 1)[0]          # the answer without its closing brace


def _ffprobe(monkeypatch, answers):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        out = answers[min(len(calls), len(answers)) - 1]
        return subprocess.CompletedProcess(argv, 0, stdout=out.encode(), stderr=b"")

    monkeypatch.setattr(c.subprocess, "run", run)
    return calls


def test_an_answer_cut_short_is_read_again(monkeypatch, tmp_path):
    calls = _ffprobe(monkeypatch, [CUT, ANSWER])
    got = c.probe(tmp_path / "edit_v01.mp4")
    assert len(calls) == 2
    assert got["width"] == 540 and got["duration"] == 4.0 and got["is_video"]


def test_an_answer_cut_short_every_time_stops_with_a_plain_error(monkeypatch, tmp_path):
    calls = _ffprobe(monkeypatch, [CUT])
    with pytest.raises(c.ToolError, match=r"edit_v01\.mp4 could not be read 3 times in a row"):
        c.probe(tmp_path / "edit_v01.mp4")
    assert len(calls) == c.PROBE_TRIES == 3


def test_a_whole_answer_is_read_once(monkeypatch, tmp_path):
    calls = _ffprobe(monkeypatch, [ANSWER])
    assert c.ffprobe_json(tmp_path / "edit_v01.mp4", "-show_streams")["format"]["duration"] == "4.000000"
    assert len(calls) == 1 and calls[0][-3:-1] == ["-of", "json"]
