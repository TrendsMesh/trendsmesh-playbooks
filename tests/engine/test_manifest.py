from datetime import date

import pytest

from tm import manifest
from tm.runfolder import RunFolder


def _run(tmp_path):
    return RunFolder.create(tmp_path, "x", date(2026, 11, 5))


def test_record_appends_rows(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/a_v01.mp4", "wip", "Veo", None, "a cat | dancing", {"seconds": 8},
                    "veo-3.1", "$0.80", "before: x / after: y")
    manifest.record(run, "03_wip/a_v02.mp4", "wip", "Veo", "03_wip/a_v01.mp4", None, None, None, None, None)
    text = (run.path / "manifest.md").read_text(encoding="utf-8")
    rows = [l for l in text.splitlines() if l.startswith("| 03_wip")]
    assert len(rows) == 2
    assert "a_v01.mp4" in rows[1]
    assert text.count("| file |") == 1
    assert "\\|" in rows[0]  # pipe in prompt is escaped


def test_prompt_and_raw_saved_next_to_asset(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/a_v01.mp4", "wip", "Veo", None, "full prompt text", {"k": 1},
                    None, None, None, raw_response='{"id": 1}')
    wip = run.path / "03_wip"
    assert (wip / "a_v01.mp4.prompt.txt").read_text(encoding="utf-8") == "full prompt text"
    assert (wip / "a_v01.mp4.response.json").read_text(encoding="utf-8") == '{"id": 1}'


def test_sidecars_do_not_collide_across_extensions_or_dots(tmp_path):
    run = _run(tmp_path)
    for f, p in (("03_wip/a_v01.mp4", "video"), ("03_wip/a_v01.png", "image"), ("03_wip/clip.v2", "dots")):
        manifest.record(run, f, "wip", "x", None, p, None, None, None, None)
    wip = run.path / "03_wip"
    assert (wip / "a_v01.mp4.prompt.txt").read_text(encoding="utf-8") == "video"
    assert (wip / "a_v01.png.prompt.txt").read_text(encoding="utf-8") == "image"
    assert (wip / "clip.v2.prompt.txt").read_text(encoding="utf-8") == "dots"


def test_rerecord_never_overwrites_sidecars(tmp_path):
    run = _run(tmp_path)
    for p in ("first", "second"):
        manifest.record(run, "03_wip/a.mp4", "wip", "x", None, p, None, None, None, None, raw_response=p)
    wip = run.path / "03_wip"
    assert (wip / "a.mp4.prompt.txt").read_text(encoding="utf-8") == "first"
    assert (wip / "a.mp4.prompt_v02.txt").read_text(encoding="utf-8") == "second"
    assert (wip / "a.mp4.response.json").read_text(encoding="utf-8") == "first"
    assert (wip / "a.mp4.response_v02.json").read_text(encoding="utf-8") == "second"


def test_file_is_posix_and_cannot_escape(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip\\a.mp4", "wip", "x", None, None, None, None, None, None)
    assert "| 03_wip/a.mp4 |" in (run.path / "manifest.md").read_text(encoding="utf-8")
    for bad in ("../x.mp4", "/etc/x", "03_wip/../../x", "C:\\x.mp4"):
        with pytest.raises(ValueError):
            manifest.record(run, bad, "wip", "x", None, None, None, None, None, None)
    with pytest.raises(ValueError):
        manifest.record(run, "03_wip/a.mp4", "../wip", "x", None, None, None, None, None, None)


def test_rows_round_trip_escaping(tmp_path):
    run = _run(tmp_path)
    tricky = r"a | b \ c \| d <x> & ""q"""
    manifest.record(run, "03_wip/a_v01.mp4", "wip", "Veo", None, tricky, {"k": "v|w"}, None, None, "after (before: 01_base/o.mp4)")
    manifest.record(run, "03_wip/b.mp4", "wip", "ffmpeg", "03_wip/a_v01.mp4", None, None, None, None, None)
    got = manifest.rows(run)
    assert [r["file"] for r in got] == ["03_wip/a_v01.mp4", "03_wip/b.mp4"]
    assert got[0]["prompt"] == tricky
    assert got[0]["params"] == '{"k": "v|w"}'
    assert got[0]["before/after"] == "after (before: 01_base/o.mp4)"
    assert got[1]["prompt"] == "" and got[1]["parent"] == "03_wip/a_v01.mp4"
