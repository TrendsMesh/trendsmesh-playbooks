"""tm tool music_index: the index of a music folder, written into the run, never into the folder."""

from __future__ import annotations

import csv
import json
import subprocess

import pytest
from _media import ffmpeg

from tm.tools import music_index

pytest.importorskip("numpy")

COLUMNS = ["file", "title", "duration_s", "lufs", "bpm_est", "mood", "licence", "source", "author"]


def _sine(path, seconds=15):
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:sample_rate=44100:duration={seconds}",
                    "-metadata", "title=Sinus", "-metadata", "genre=calm", str(path)], check=True)


@pytest.mark.tools
def test_music_index_columns_and_never_writes_in_user_folder(run, tmp_path, capsys):
    music = tmp_path / "Moja muzyka Łukasz"
    music.mkdir()
    _sine(music / "a sine.mp3")
    _sine(music / "b sine.mp3", seconds=12)
    (music / "notes.txt").write_text("not audio", encoding="utf-8")
    (music / "moods.json").write_text(json.dumps({"b sine.mp3": {"mood": "warm", "licence": "CC0", "source": "me"}}),
                                      encoding="utf-8")
    before = sorted(p.name for p in music.iterdir())
    assert music_index.main(["--run", str(run.path), str(music), "--moods", str(music / "moods.json"),
                             "--json"]) == 0
    assert sorted(p.name for p in music.iterdir()) == before  # nothing written in the user's folder
    out = run.path / "02_research" / "music_index_v01.csv"
    rows = list(csv.DictReader(out.open(encoding="utf-8", newline="")))
    assert list(rows[0]) == COLUMNS
    assert [r["file"] for r in rows] == ["a sine.mp3", "b sine.mp3"]
    a, b = rows
    assert a["title"] == "Sinus" and a["mood"] == "calm"  # tags are the fallback
    assert abs(float(a["duration_s"]) - 15.0) < 0.3 and float(a["lufs"]) < 0
    assert 60 <= float(a["bpm_est"]) <= 180
    assert (b["mood"], b["licence"], b["source"]) == ("warm", "CC0", "me")  # moods.json wins
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["outputs"] == ["02_research/music_index_v01.csv"] and result["files"] == 2
    # a second run is a new version
    assert music_index.main(["--run", str(run.path), str(music)]) == 0
    assert (run.path / "02_research" / "music_index_v02.csv").is_file() and out.is_file()
    assert "music_index_v01.csv" in (run.path / "manifest.md").read_text(encoding="utf-8")


@pytest.mark.tools
def test_music_index_refuses_a_folder_without_audio(run, tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    assert music_index.main(["--run", str(run.path), str(tmp_path / "empty"), "--json"]) == 1
    assert "no audio" in json.loads(capsys.readouterr().out)["message"]
    assert not list((run.path / "02_research").glob("music_index_*"))
