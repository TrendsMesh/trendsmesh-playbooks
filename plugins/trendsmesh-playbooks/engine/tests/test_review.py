"""`tm review build`: the local review page is now the run page (tm.run_page, issue #19), built locally."""

import json
import re
from datetime import date
from pathlib import Path

from tm import cli, manifest, review, state
from tm.runfolder import RunFolder


def _run(tmp_path):
    return RunFolder.create(tmp_path, "x", date(2026, 11, 5))


def test_pairs_come_from_the_manifest(tmp_path):
    run = _run(tmp_path)
    manifest.record(run, "03_wip/edit v02 Łuk.mp4", "wip", "ffmpeg", "01_base/orig.mp4", None, None, None, None,
                    "after (before: 01_base/orig <1>.mp4)")
    manifest.record(run, "03_wip/x.mp4", "wip", "ffmpeg", None, None, None, None, None,
                    "before: 01_base/a.mp4 / after: 03_wip/b.mp4")
    assert review.pairs(run) == [("01_base/orig <1>.mp4", "03_wip/edit v02 Łuk.mp4"), ("01_base/a.mp4", "03_wip/b.mp4")]


def test_build_makes_the_local_run_page_and_escapes_the_decisions(tmp_path):
    run = _run(tmp_path)
    st = state.load(run)
    st.decisions.append({"checkin": "G4", "choice": "approve", "by": "user", "note": "<b>go</b> & \"now\"",
                         "at": "2026-11-05T10:00:00+00:00"})
    state.save(run, st)
    path = review.build(run)
    assert path == run.path / "04_final" / "run_page_v01" / "index.html"
    page = path.read_text(encoding="utf-8")
    assert "&lt;b&gt;go&lt;/b&gt; &amp; &quot;now&quot;" in page and "<b>go</b>" not in page
    assert str(tmp_path) not in page and "file://" not in page
    assert not re.search(r'(?:src|href)="(?:/|file:)', page)
    assert "<input" not in page                       # built locally: decisions are answered in chat
    assert review.build(run).parent.name == "run_page_v02"      # a new version each time, never overwritten


def test_cli_prints_path_and_says_it_is_the_run_page(tmp_path, capsys):
    run = _run(tmp_path)
    assert cli.main(["review", "build", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["path"].endswith("index.html") and Path(out["path"]).is_file()
    assert "tm page build" in out["message"]
    assert cli.main(["review", "build", "--run", str(tmp_path / "nope")]) == 1
