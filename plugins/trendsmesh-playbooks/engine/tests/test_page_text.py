"""tm page fetch: a page's literal text saved in the run (issue #14), and the landing-page quote
check `tm brief check` runs on it. Nothing here touches the network or starts a browser."""

import json
from datetime import date
from pathlib import Path

import pytest
import requests

from tm import brief_checks, manifest, page_text
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder
from tm.stops import Stop

PAGE = """<!DOCTYPE html><html><head><title>Linen duvet | Example</title>
<style>.hero{color:red}</style><script>window.track("visit")</script></head>
<body>
<nav><a href="/">Home</a> <a href="/shop">Shop</a> <a href="/about">About us</a></nav>
<header class="hero"><h1>Sleep cool all summer</h1></header>
<main>
  <p>Our linen duvet keeps you <b>cool</b> on hot nights,
     washed in soft water.</p>
  <ul><li>100&nbsp;% French flax</li><li>Oeko-Tex certified</li></ul>
  <div class="price">Now <span>129,00&nbsp;zł</span></div>
  <div role="navigation">Next page Previous page</div>
  <noscript>Please enable JavaScript</noscript>
  <svg><title>Cart icon</title><text>logo</text></svg>
  <button>Add to cart</button>
  <p>Reviewed by 1,240 sleepers. """ + " ".join(f"word{i}" for i in range(40)) + """</p>
</main>
<footer><p>Free returns within 30 days.</p></footer>
</body></html>"""

SHELL = """<!DOCTYPE html><html><head><title>Shop</title><script src="/app.js"></script></head>
<body><div id="root"></div><noscript>You need to enable JavaScript to run this app.</noscript></body></html>"""


@pytest.fixture
def run(tmp_path, monkeypatch) -> RunFolder:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(workspace))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return RunFolder.create(workspace, "duvet", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


class _Answer:
    def __init__(self, body: str | bytes, content_type: str = "text/html; charset=utf-8", status: int = 200,
                 url: str = "https://example.com/duvet"):
        self.content = body.encode("utf-8") if isinstance(body, str) else body
        self.headers, self.status_code, self.url = {"Content-Type": content_type}, status, url


@pytest.fixture
def web(monkeypatch):
    """requests.get replaced by a fake answering `answer[0]`; each call recorded."""
    calls, answer = [], [_Answer(PAGE)]

    def get(url, **kw):
        calls.append((url, kw))
        if isinstance(answer[0], Exception):
            raise answer[0]
        return answer[0]
    monkeypatch.setattr(page_text.requests, "get", get)
    return calls, answer


@pytest.fixture
def no_browser(monkeypatch):
    """Rendering refuses: a test that needs it gives its own renderer."""
    def refuse(url):
        raise AssertionError("this test must not render")
    monkeypatch.setattr(page_text, "render", refuse)


# --- the text ------------------------------------------------------------------------------------

def test_text_keeps_headings_paragraphs_and_prices_and_drops_scripts_and_navigation():
    text = page_text.html_to_text(PAGE)
    lines = text.split("\n")
    assert "Sleep cool all summer" in lines
    assert "Our linen duvet keeps you cool on hot nights, washed in soft water." in lines
    assert "100 % French flax" in lines and "Oeko-Tex certified" in lines
    assert "Now 129,00 zł" in lines
    assert "Add to cart" in lines and "Free returns within 30 days." in lines
    assert lines[0] == "Linen duvet | Example"               # the title first
    for gone in ("window.track", "color:red", "Home", "About us", "Next page", "enable JavaScript", "logo",
                 "Cart icon"):
        assert gone not in text, gone
    assert "\n\n\n" not in text


def test_text_survives_unclosed_and_stray_tags():
    text = page_text.html_to_text("<body><p>one<p>two</span><li>three<nav>menu</div></nav><p>four")
    assert [line for line in text.split("\n") if line] == ["one", "two", "three", "four"]


def test_decodes_the_declared_charset():
    body = "<html><head><meta charset='iso-8859-2'></head><body><p>Zażółć gęślą jaźń</p></body></html>"
    assert "Zażółć gęślą jaźń" in page_text.html_to_text(page_text.decode(body.encode("iso-8859-2"), "text/html"))
    assert page_text.decode("<p>é</p>".encode("utf-8"), "text/html; charset=utf-8") == "<p>é</p>"


# --- tm page fetch -------------------------------------------------------------------------------

def test_fetch_saves_the_literal_text_and_records_url_and_date(run, web, no_browser, capsys):
    calls, _ = web
    code = main(["page", "fetch", "--run", str(run.path), "--url", "https://example.com/duvet", "--name", "duvet",
                 "--found-in", "pixel", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "done", out
    assert out["file"] == "00_raw/landing_duvet.txt" and out["how"] == "downloaded"
    saved = (run.path / out["file"]).read_text(encoding="utf-8")
    assert "Our linen duvet keeps you cool on hot nights" in saved and "window.track" not in saved
    assert "https://example.com/duvet" in saved.split("\n")[0]
    assert calls[0][0] == "https://example.com/duvet" and "trendsmesh" in calls[0][1]["headers"]["User-Agent"]
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert row["stage"] == "00_raw" and row["source"].startswith("tm page fetch https://example.com/duvet")
    assert row["date"] == date.today().isoformat()
    params = json.loads(row["params"])
    assert params["url"] == "https://example.com/duvet" and params["found_in"] == "pixel"
    assert params["saved"] == date.today().isoformat()


def test_fetch_never_overwrites_and_saves_voice_pages_under_their_own_name(run, web, no_browser, capsys):
    for _ in range(2):
        assert main(["page", "fetch", "--run", str(run.path), "--url", "https://example.com/duvet",
                     "--name", "duvet", "--json"]) == 0
    assert main(["page", "fetch", "--run", str(run.path), "--url", "https://example.com/duvet",
                 "--name", "rival-reviews", "--kind", "voice", "--json"]) == 0
    files = [json.loads(line)["file"] for line in capsys.readouterr().out.strip().split("\n")]
    assert files == ["00_raw/landing_duvet.txt", "00_raw/landing_duvet_v02.txt", "00_raw/voice_rival-reviews.txt"]


def test_a_page_built_by_javascript_is_rendered_in_the_browser(run, web, monkeypatch):
    _, answer = web
    answer[0] = _Answer(SHELL)
    rendered = []

    def render(url):
        rendered.append(url)
        return PAGE
    monkeypatch.setattr(page_text, "render", render)
    got = page_text.save(run, "https://example.com/duvet", "duvet")
    assert rendered == ["https://example.com/duvet"] and got["how"] == "rendered"
    assert "Sleep cool all summer" in (run.path / got["file"]).read_text(encoding="utf-8")
    row = next(r for r in manifest.rows(run) if r["file"] == got["file"])
    assert "headless" in row["source"]


def test_a_page_empty_even_rendered_is_a_stop_and_saves_nothing(run, web, monkeypatch):
    _, answer = web
    answer[0] = _Answer(SHELL)
    monkeypatch.setattr(page_text, "render", lambda url: SHELL)
    with pytest.raises(Stop, match="almost no text") as exc:
        page_text.save(run, "https://example.com/duvet", "duvet")
    assert "summary" in str(exc.value)                         # names the last resort
    assert not list((run.path / "00_raw").glob("landing_*"))


def test_render_without_a_browser_is_a_stop(monkeypatch):
    from tm import atlas
    monkeypatch.setattr(atlas, "find_browser", lambda: None)
    with pytest.raises(Stop, match="Chrome"):
        page_text.render("https://example.com/duvet")


def test_render_runs_the_browser_headless_and_reads_its_dom(monkeypatch, tmp_path):
    from tm import atlas
    browser = tmp_path / "Google Chrome"
    monkeypatch.setattr(atlas, "find_browser", lambda: browser)
    monkeypatch.setattr(atlas, "needs_no_sandbox", lambda b: False)
    seen = []

    class Done:
        returncode, stdout, stderr = 0, PAGE.encode("utf-8"), b""

    def fake_run(argv, **kw):
        seen.append((argv, kw))
        return Done()
    monkeypatch.setattr(page_text.subprocess, "run", fake_run)
    assert page_text.render("https://example.com/duvet") == PAGE
    argv, kw = seen[0]
    assert argv[0] == str(browser) and argv[-1] == "https://example.com/duvet"
    assert "--dump-dom" in argv and any(a.startswith("--headless") for a in argv)
    assert any(a.startswith("--user-data-dir=") for a in argv) and kw["timeout"] > 0


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_site_refusing_automated_reading_is_a_stop_not_worked_around(run, web, no_browser, status):
    _, answer = web
    answer[0] = _Answer("denied", status=status)
    with pytest.raises(Stop, match=f"HTTP {status}") as exc:
        page_text.save(run, "https://example.com/duvet", "duvet")
    assert "summary" in str(exc.value)


def test_other_failures_are_stops(run, web, no_browser):
    _, answer = web
    answer[0] = requests.ConnectionError("down")
    with pytest.raises(Stop, match="could not be downloaded"):
        page_text.save(run, "https://example.com/duvet", "duvet")
    answer[0] = _Answer(b"%PDF-1.7", content_type="application/pdf")
    with pytest.raises(Stop, match="not a web page"):
        page_text.save(run, "https://example.com/duvet", "duvet")
    answer[0] = _Answer("gone", status=404)
    with pytest.raises(Stop, match="HTTP 404"):
        page_text.save(run, "https://example.com/duvet", "duvet")


def test_bad_arguments_are_errors(run, web, no_browser, capsys):
    for url, name in (("ftp://example.com", "duvet"), ("https://example.com", "a/b"), ("https://example.com", "x.y")):
        with pytest.raises(ValueError):
            page_text.save(run, url, name)
    assert main(["page", "fetch", "--run", str(run.path), "--url", "example.com", "--name", "duvet", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_the_stop_exits_2(run, web, no_browser, capsys):
    _, answer = web
    answer[0] = _Answer("denied", status=403)
    assert main(["page", "fetch", "--run", str(run.path), "--url", "https://example.com/duvet", "--name", "duvet",
                 "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"


# --- literal or summary --------------------------------------------------------------------------

def _place(run: RunFolder, name: str, text: str, source: str, url: str | None = None) -> str:
    rel = f"00_raw/{name}"
    (run.path / rel).write_text(text, encoding="utf-8")
    manifest.record(run, rel, "00_raw", source, params={"url": url} if url else None)
    return rel


def test_a_webfetch_file_is_a_summary_by_name_or_by_its_source(run):
    lit = _place(run, "landing_a.txt", "page text", "tm page fetch https://example.com/a (downloaded)",
                 "https://example.com/a")
    by_name = _place(run, "landing_b.summary.txt", "summary", "WebFetch summary of https://example.com/b")
    by_source = _place(run, "landing_c.txt", "summary", "WebFetch https://example.com/c")
    (run.path / "00_raw" / "landing_d.html").write_text("<p>x</p>", encoding="utf-8")   # not text: not read
    literal, summaries = page_text.landing_texts(run)
    assert [(rel, text, url) for rel, text, url in literal] == [(lit, "page text", "https://example.com/a")]
    assert summaries == [by_name, by_source]


# --- the landing-page quote check (tm brief check) -----------------------------------------------

def _brief(*why: dict, landing: str = "https://www.example.com/duvet/") -> dict:
    return {"meta": {"product": {"name": "Linen duvet", "landing_url": landing}},
            "concepts": [{"id": "C1", "why": list(why)}]}


def test_a_landing_quote_must_be_in_the_saved_page_text(run):
    _place(run, "landing_duvet.txt", page_text.html_to_text(PAGE), "tm page fetch https://example.com/duvet",
           "https://example.com/duvet")
    ok = {"quote": "keeps you COOL on hot  nights", "url": "https://example.com/duvet", "source_label": "Landing page"}
    made_up = {"quote": "clinically proven to cool", "url": "https://example.com/duvet?utm=x"}
    by_label = {"quote": "Sleep better than ever", "source_label": "00_raw/landing_duvet.txt"}
    customer = {"quote": "my duvet is too hot", "url": "https://www.reddit.com/r/sleep/comments/x/"}
    got = brief_checks.landing_quotes(run, _brief(ok, made_up, by_label, customer))
    assert [p.field for p in got] == ["concepts[0].why[1]", "concepts[0].why[2]"]
    assert "clinically proven to cool" in got[0].what and "00_raw/landing_duvet.txt" in got[0].what
    assert "tm page fetch" not in got[0].todo and "word for word" in got[0].todo


def test_a_quote_from_another_saved_page_of_the_site_is_checked_against_that_page(run):
    _place(run, "landing_duvet.txt", "Sleep cool all summer", "tm page fetch https://example.com/duvet",
           "https://example.com/duvet")
    _place(run, "landing_about.txt", "Founded by two sleepers in 2019", "tm page fetch https://example.com/about",
           "https://example.com/about")
    found = {"quote": "Founded by two sleepers", "url": "https://example.com/about"}
    assert brief_checks.landing_quotes(run, _brief(found)) == []
    other_site = {"quote": "Founded by two sleepers", "url": "https://shop.example.org/about"}
    assert brief_checks.landing_quotes(run, _brief(other_site)) == []        # not given as the landing page's


def test_a_summary_is_never_quoted_from(run):
    _place(run, "landing_duvet.summary.txt", "The page says the duvet keeps you cool on hot nights.",
           "WebFetch summary of https://example.com/duvet")
    quote = {"quote": "keeps you cool on hot nights", "url": "https://example.com/duvet"}
    got = brief_checks.landing_quotes(run, _brief(quote))
    assert [p.field for p in got] == ["concepts[0].why[0]"]
    assert "summary" in got[0].what and "tm page fetch" in got[0].todo


def test_no_saved_landing_page_leaves_the_check_to_a1(run):
    quote = {"quote": "anything", "url": "https://example.com/duvet"}
    assert brief_checks.landing_quotes(run, _brief(quote)) == []


def test_the_brief_stage_runs_the_landing_quote_check():
    import inspect
    assert "landing_quotes(" in inspect.getsource(brief_checks._brief_checks)
