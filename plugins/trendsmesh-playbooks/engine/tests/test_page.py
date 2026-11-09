"""tm.page: versioned local page folders, their media, and the artifact each was published to.
Shared by PB02, PB03 and PB04."""

import json
import time
from datetime import date
from pathlib import Path

import pytest
import requests

from tm import manifest, page, state
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder


def _run(workspace, name="week-1", day=7, after: RunFolder | None = None) -> RunFolder:
    run = RunFolder.create(workspace, name, date(2026, 11, day), playbook=TREND_RESEARCH)
    if after is not None:                       # as `tm run new --after` stores it
        s = state.load(run)
        s.previous_run = after.path.relative_to(workspace).as_posix()
        state.save(run, s)
    return run


def _built(run: RunFolder, name="report") -> Path:
    folder = page.new_folder(run, name)
    (folder / "index.html").write_text("<!DOCTYPE html><title>t</title>", encoding="utf-8")
    return folder


class _Answer:
    def __init__(self, body: bytes, content_type: str, status: int = 200, chunks: int = 1, pause: float = 0):
        self.body, self.headers, self.status_code = body, {"Content-Type": content_type}, status
        self.chunks, self.pause = chunks, pause

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def iter_content(self, chunk_size=1):
        for _ in range(self.chunks):                 # a slow server: each read within its timeout
            time.sleep(self.pause)
            yield self.body

    def close(self):
        pass


@pytest.fixture
def web(monkeypatch):
    """requests.get replaced: each call is recorded and answered from `answers` by URL."""
    calls, answers = [], {}

    def get(url, **kw):
        calls.append((url, kw))
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(requests, "get", get)
    return calls, answers


def test_new_folder_never_reuses_a_version(tmp_path):
    run = _run(tmp_path)
    first, second = page.new_folder(run, "report"), page.new_folder(run, "report")
    assert [first.name, second.name] == ["report_v01", "report_v02"]
    assert first.parent == run.path / "04_final"
    assert (first / "assets").is_dir() and (second / "assets").is_dir()
    (run.path / "04_final" / "report_v07").mkdir()                    # a gap is never filled
    (run.path / "04_final" / "report-old_v20").mkdir()                # another page's name
    assert page.new_folder(run, "report").name == "report_v08"
    assert page.new_folder(run, "brief-pack").name == "brief-pack_v01"
    assert page.latest_folder(run, "report").name == "report_v08"
    assert page.latest_folder(run, "proposals") is None
    for bad in ("../x", "", "a/b", "report v2"):
        with pytest.raises(ValueError, match="page name"):
            page.new_folder(run, bad)


def test_fetch_image_offline_returns_false(tmp_path, web):
    calls, answers = web
    url = "https://cdn.example.com/p/1.jpg"
    answers[url] = requests.ConnectionError("offline")
    dest = tmp_path / "assets" / "1.jpg"
    assert page.fetch_image(url, dest) is False
    assert not dest.exists() and list(tmp_path.rglob("*.jpg")) == []
    assert calls[0][1]["timeout"] == 30
    answers[url] = _Answer(b"", "image/jpeg", status=404)
    assert page.fetch_image(url, dest, timeout=5) is False and not dest.exists()
    assert calls[1][1]["timeout"] == 5
    assert page.fetch_image(None, dest) is False and len(calls) == 2


def test_fetch_image_refuses_non_http(tmp_path, web, monkeypatch):
    calls, answers = web
    dest = tmp_path / "assets" / "x.jpg"
    for url in ("file:///etc/passwd", "ftp://example.com/x.jpg", "data:image/png;base64,iVBOR",
                "//cdn.example.com/x.jpg", "x.jpg", "http://[::1", "", 42):
        assert page.fetch_image(url, dest) is False
    assert calls == [] and not dest.exists()

    answers["https://example.com/page"] = _Answer(b"<html>", "text/html; charset=utf-8")
    assert page.fetch_image("https://example.com/page", dest) is False and not dest.exists()
    answers["http://cdn.example.com/x.jpg"] = _Answer(b"\xff\xd8jpeg", "image/jpeg")
    assert page.fetch_image("http://cdn.example.com/x.jpg", dest) is True
    assert dest.read_bytes() == b"\xff\xd8jpeg"
    assert list(dest.parent.iterdir()) == [dest]                      # no temp file left behind
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 3)                  # more than publish_files takes
    big = tmp_path / "assets" / "big.jpg"
    answers["https://cdn.example.com/big.jpg"] = _Answer(b"\xff\xd8jpeg", "image/jpeg")
    assert page.fetch_image("https://cdn.example.com/big.jpg", big) is False
    assert list(dest.parent.iterdir()) == [dest]
    count = len(calls)
    assert page.fetch_image("https://elsewhere.example.com/y.jpg", dest) is True   # reused, not fetched
    assert len(calls) == count and dest.read_bytes() == b"\xff\xd8jpeg"


def test_files_lists_index_and_assets_for_publish(tmp_path, capsys):
    run = _run(tmp_path)
    folder = _built(run)
    for name in ("b.jpg", "a.png", ".DS_Store"):
        (folder / "assets" / name).write_bytes(b"x")
    (folder / "assets" / ".a.png.123.tmp").write_bytes(b"x")
    (folder / "data.json").write_text("{}", encoding="utf-8")
    listed = page.files(folder)
    assert [f["as"] for f in listed] == ["index.html", "assets/a.png", "assets/b.jpg", "data.json"]
    assert all(f["path"] == str((folder / f["as"]).resolve()) for f in listed)
    assert set(listed[0]) == {"as", "path"}

    empty = page.new_folder(run, "report")
    with pytest.raises(ValueError, match="index.html"):
        page.files(empty)
    (empty / "index.html").write_text("<!DOCTYPE html>", encoding="utf-8")
    assert main(["page", "files", "--run", str(run.path), "--page", "report", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "done", "folder": "04_final/report_v02", "files": page.files(empty)}
    assert main(["page", "files", "--run", str(run.path), "--page", "brief", "--json"]) == 1
    message = json.loads(capsys.readouterr().out)["message"]
    assert "04_final/brief_vNN" in message and "continues from the same place" in message


def test_published_slug_found_along_previous_runs(tmp_path, capsys):
    """Run 3 follows run 2, which follows run 1: run 1's slug is found, and run 3's own record
    wins once it publishes (Review Focus 5)."""
    first = _run(tmp_path, "week-1", 1)
    _built(first)
    record = page.record_published(first, "report", "art_1", "ver_a", "https://claude.ai/a/art_1")
    assert {k: record[k] for k in ("slug", "version", "url", "folder")} == {
        "slug": "art_1", "version": "ver_a", "url": "https://claude.ai/a/art_1", "folder": "04_final/report_v01"}
    assert record["published_at"].endswith("+00:00")
    assert state.load(first).pages == {"report": record}
    row = manifest.rows(first)[-1]
    assert (row["file"], row["stage"], row["source"]) == ("04_final/report_v01", "04_final",
                                                         "artifacts MCP publish_files")
    assert json.loads(row["params"]) == {"slug": "art_1", "version": "ver_a", "url": "https://claude.ai/a/art_1"}

    second = _run(tmp_path, "week-2", 8, after=first)
    third = _run(tmp_path, "week-3", 15, after=second)
    assert page.published(third, "report") == record
    assert page.published(third, "brief") is None
    assert page.published(first, "report") == record

    _built(third)
    again = page.record_published(third, "report", "art_1", "ver_b")
    assert again["url"] is None and again["folder"] == "04_final/report_v01"
    assert page.published(third, "report") == again
    assert page.published(second, "report") == record                 # a later run never changes an earlier one

    assert main(["page", "link", "--run", str(third.path), "--page", "report", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", **again}
    assert main(["page", "link", "--run", str(third.path), "--page", "brief", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "none"}
    assert main(["page", "link", "--run", str(second.path), "--page", "report"]) == 0
    assert "art_1" in capsys.readouterr().out


def test_published_command_records_and_refuses(tmp_path, capsys):
    run = _run(tmp_path)
    assert main(["page", "published", "--run", str(run.path), "--page", "report", "--slug", "art_1",
                 "--version", "v1", "--json"]) == 1
    assert "build the page first" in json.loads(capsys.readouterr().out)["message"]
    _built(run)
    for slug, version in (("", "v1"), ("art_1", " ")):
        with pytest.raises(ValueError, match="slug and version"):
            page.record_published(run, "report", slug, version)
    assert main(["page", "published", "--run", str(run.path), "--page", "report", "--slug", "art_1",
                 "--version", "v1", "--url", "https://claude.ai/a/art_1", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["slug"] == "art_1" and out["url"] == "https://claude.ai/a/art_1"
    assert state.load(run).pages["report"]["version"] == "v1"


def test_published_chain_says_a_missing_run(tmp_path, capsys):
    """A run whose previous run is gone is told so, never handed a new link in silence; a loop in
    the chain ends the walk."""
    first = _run(tmp_path, "week-1", 1)
    second = _run(tmp_path, "week-2", 8, after=first)
    (first.path / "manifest.md").unlink()
    with pytest.raises(ValueError, match="2026-11-01_week-1"):
        page.published(second, "report")
    assert main(["page", "link", "--run", str(second.path), "--page", "report", "--json"]) == 1
    assert "continues from the same place" in json.loads(capsys.readouterr().out)["message"]

    a = _run(tmp_path, "loop-a", 2)
    b = _run(tmp_path, "loop-b", 3, after=a)
    s = state.load(a)
    s.previous_run = b.path.relative_to(tmp_path).as_posix()
    state.save(a, s)
    assert page.published(b, "report") is None


def test_fetch_image_gives_up_after_the_whole_timeout(tmp_path, web):
    _, answers = web
    url = "https://cdn.example.com/slow.jpg"
    answers[url] = _Answer(b"x", "image/jpeg", chunks=5, pause=0.03)
    dest = tmp_path / "assets" / "slow.jpg"
    assert page.fetch_image(url, dest, timeout=0.05) is False
    assert list(dest.parent.iterdir()) == []
    assert page.fetch_image(url, dest, timeout=5) is True and dest.read_bytes() == b"xxxxx"


def test_asset_names_are_safe_on_every_os(tmp_path, web):
    assert page.asset_name("tiktok:123.jpg") == "tiktok_123.jpg"
    assert page.asset_name('a<b>c"d|e?f*g/h\\i\x01.png') == "a_b_c_d_e_f_g_h_i_.png"
    assert page.asset_name("plain-name_01.webp") == "plain-name_01.webp"
    _, answers = web
    answers["https://cdn.example.com/t.jpg"] = _Answer(b"img", "image/jpeg")
    assert page.fetch_image("https://cdn.example.com/t.jpg", tmp_path / "assets" / "tiktok:123.jpg") is True
    assert [f.name for f in (tmp_path / "assets").iterdir()] == ["tiktok_123.jpg"]


def test_files_refuses_a_page_over_publish_limits(tmp_path, monkeypatch):
    run = _run(tmp_path)
    folder = _built(run)
    for i in range(3):
        (folder / "assets" / f"{i}.jpg").write_bytes(b"12345")
    assert len(page.files(folder)) == 4
    monkeypatch.setattr(page, "MAX_FILES", 3)
    with pytest.raises(ValueError, match="4 files and publish_files takes at most 3"):
        page.files(folder)
    monkeypatch.setattr(page, "MAX_FILES", 256)
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 4)
    with pytest.raises(ValueError, match=r"assets/0.jpg, assets/1.jpg, assets/2.jpg are over .* a file"):
        page.files(folder)
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 100)
    monkeypatch.setattr(page, "MAX_TOTAL_BYTES", 40)
    with pytest.raises(ValueError, match="in all.*continues from the same place"):
        page.files(folder)


def test_link_from_inside_the_run_folder(tmp_path, monkeypatch, capsys):
    """`--run .` (or the run's name from runs/<playbook>/) is resolved before the chain is walked."""
    first = _run(tmp_path, "week-1", 1)
    _built(first)
    page.record_published(first, "report", "art_1", "ver_a")
    second = _run(tmp_path, "week-2", 8, after=first)
    monkeypatch.chdir(second.path)
    assert main(["page", "link", "--run", ".", "--page", "report", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["slug"] == "art_1"
    monkeypatch.chdir(second.path.parent)
    assert main(["page", "link", "--run", second.path.name, "--page", "report", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["slug"] == "art_1"


def test_earlier_decisions_wants_its_callers_shape(tmp_path):
    """Task 7 Minor 7: each caller names the shape its decisions file keeps (PB02's `docs` a list,
    organic video's `decisions` a dict); a file of the other shape is not that command's, and stops."""
    run = _run(tmp_path)
    wip = run.path / "03_wip"
    wip.mkdir(exist_ok=True)
    brief = wip / "decisions_G1_v01.json"
    brief.write_text(json.dumps({"page": "b1", "docs": {"C1": {"decision": "keep"}}}), encoding="utf-8")
    with pytest.raises(page.Stop, match="not a decisions file of tm brief decisions"):
        page.earlier_decisions(run, [brief], "b2", built="page", rows="docs", command="tm brief decisions", shape=list)
    brief.write_text(json.dumps({"page": "b1", "docs": [{"id": "C1"}]}), encoding="utf-8")
    assert page.earlier_decisions(run, [brief], "b2", built="page", rows="docs", command="tm brief decisions",
                                  shape=list) == [{"id": "C1"}]
    organic = wip / "decisions_proposals_v01.json"
    organic.write_text(json.dumps({"folder": "f1", "decisions": [{"m1": {}}]}), encoding="utf-8")
    with pytest.raises(page.Stop, match="not a decisions file of tm organic decisions"):
        page.earlier_decisions(run, [organic], "f2", built="folder", rows="decisions",
                               command="tm organic decisions", shape=dict)
