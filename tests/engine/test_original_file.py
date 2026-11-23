"""Issue #143 item 7: the original video from any path (a folder outside the brand assets, a file dropped in the chat)
is copied to 01_base/<ad_id>_original.<ext> and recorded with its path as the source (`tm record --copy-from`)."""

import json
import shutil
import subprocess
from datetime import date

import pytest

from tm import manifest
from tm.cli import main
from tm.runfolder import RunFolder


def test_the_original_is_copied_in_from_anywhere_and_recorded(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    drop = tmp_path / "Downloads" / "Ad 3 final.mp4"
    drop.parent.mkdir()
    drop.write_bytes(b"\x00video")
    code = main(["record", "--run", str(run.path), "--file", "01_base/120001_original.mp4", "--stage", "01_base",
                 "--copy-from", str(drop), "--json"])
    assert code == 0, capsys.readouterr().out
    assert (run.path / "01_base" / "120001_original.mp4").read_bytes() == b"\x00video"
    row = next(r for r in manifest.rows(run) if r["file"] == "01_base/120001_original.mp4")
    assert row["source"] == str(drop.resolve())
    capsys.readouterr()
    again = main(["record", "--run", str(run.path), "--file", "01_base/120001_original.mp4", "--stage", "01_base",
                  "--copy-from", str(tmp_path / "Downloads" / "other.mp4"), "--json"])
    assert again == 1 and "not a file" in json.loads(capsys.readouterr().out)["message"]


def _video(path, seconds):
    exe = shutil.which("ffmpeg")
    if not exe or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg is not on PATH (run the tests through pixi)")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=64x64:d={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def _record(run, src, length, capsys, name="120001_original.mp4"):
    capsys.readouterr()
    code = main(["record", "--run", str(run.path), "--file", f"01_base/{name}", "--stage", "01_base",
                 "--copy-from", str(src), "--length-s", str(length), "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_an_original_of_another_length_than_the_ad_is_refused_and_not_copied(tmp_path, capsys):
    """Issue #171 item 3: a 26.9 s file was taken for a 52.9 s ad. With the ad's length, tm record refuses a file more
    than 1 s or 5 % off it, naming both lengths, and copies nothing."""
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    short = _video(tmp_path / "Downloads" / "short.mp4", 3)
    code, out = _record(run, short, 52.9, capsys)
    assert code == 1 and "3.0 s" in out["message"] and "52.9 s" in out["message"], out
    assert not (run.path / "01_base" / "120001_original.mp4").exists()
    assert not any(r["file"] == "01_base/120001_original.mp4" for r in manifest.rows(run))


def test_an_original_within_the_slack_is_taken(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    clip = _video(tmp_path / "Downloads" / "ad.mp4", 3)
    code, out = _record(run, clip, 3.8, capsys)              # 0.8 s off: within 1 s
    assert code == 0, out
    assert (run.path / "01_base" / "120001_original.mp4").is_file()


def test_the_length_is_checked_only_for_an_original(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    clip = _video(tmp_path / "Downloads" / "ad.mp4", 3)
    code, out = _record(run, clip, 52.9, capsys, name="120001_lower_quality.mp4")
    assert code == 0, out


def test_record_still_needs_a_source_without_a_copy(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    (run.path / "01_base" / "x.json").write_text("{}", encoding="utf-8")
    assert main(["record", "--run", str(run.path), "--file", "01_base/x.json", "--stage", "01_base", "--json"]) == 1
    assert "--source" in json.loads(capsys.readouterr().out)["message"]
