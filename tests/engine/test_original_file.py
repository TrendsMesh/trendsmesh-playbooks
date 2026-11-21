"""Issue #143 item 7: the original video from any path (a folder outside the brand assets, a file dropped in the chat)
is copied to 01_base/<ad_id>_original.<ext> and recorded with its path as the source (`tm record --copy-from`)."""

import json
from datetime import date

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


def test_record_still_needs_a_source_without_a_copy(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    (run.path / "01_base" / "x.json").write_text("{}", encoding="utf-8")
    assert main(["record", "--run", str(run.path), "--file", "01_base/x.json", "--stage", "01_base", "--json"]) == 1
    assert "--source" in json.loads(capsys.readouterr().out)["message"]
