import json
import re
from datetime import date

from tm import cli, manifest, review, state
from tm.runfolder import RunFolder


def _run(tmp_path):
    return RunFolder.create(tmp_path, "x", date(2026, 11, 5))


def _populate(run):
    manifest.record(run, "03_wip/edit v02 Łuk.mp4", "wip", "ffmpeg", "01_base/orig.mp4", None, None, None, None,
                    "after (before: 01_base/orig <1>.mp4)")
    manifest.record(run, "03_wip/qa/a_edges.png", "wip", "ffmpeg", None, None, None, None, None, None)
    (run.path / "03_wip" / "qa").mkdir(exist_ok=True)
    (run.path / "03_wip" / "qa" / "a_edges.png").write_bytes(b"png")
    (run.path / "03_wip" / "breakdown").mkdir()
    (run.path / "03_wip" / "breakdown" / "f&1.png").write_bytes(b"png")
    (run.path / "04_final" / "strategy_brief_v01.md").write_text("old", encoding="utf-8")
    (run.path / "04_final" / "strategy_brief_v02.md").write_text("| a | <script>x</script> |", encoding="utf-8")
    st = state.load(run)
    st.decisions.append({"checkin": "C1", "choice": "ok", "by": "user", "note": "<b>go</b> & \"now\"", "at": "t"})
    state.save(run, st)


def test_page_lists_pairs_and_decisions_and_uses_relative_paths(tmp_path):
    run = _run(tmp_path)
    _populate(run)
    path = review.build(run)
    assert path == run.path / "review" / "index.html"
    page = path.read_text(encoding="utf-8")
    assert "../03_wip/edit%20v02%20%C5%81uk.mp4" in page
    assert "../01_base/orig%20%3C1%3E.mp4" in page
    assert "../03_wip/breakdown/f%261.png" in page and "../03_wip/qa/a_edges.png" in page
    assert str(tmp_path) not in page and "file://" not in page
    assert not re.search(r'(?:src|href)="(?:https?:|/)', page)
    assert "old" not in page and "&lt;script&gt;x&lt;/script&gt;" in page and "<script>x" not in page
    assert "&lt;b&gt;go&lt;/b&gt; &amp; &quot;now&quot;" in page
    assert "C1" in page and "<input class=\"seek\"" in page


def test_empty_run_builds_and_rebuild_overwrites(tmp_path):
    run = _run(tmp_path)
    review.build(run)
    page = review.build(run).read_text(encoding="utf-8")
    assert "No before/after pairs yet" in page and "No decisions yet" in page


def test_cli_prints_path(tmp_path, capsys):
    run = _run(tmp_path)
    assert cli.main(["review", "build", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["path"].endswith("index.html")
    assert cli.main(["review", "build", "--run", str(tmp_path / "nope")]) == 1
