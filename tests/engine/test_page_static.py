"""The page's fixed parts (issue #129 part 3, tm.run_page.static): the theme, the page scripts, the report's stylesheet
and script and the style catalogue are written beside index.html in assets/static/, byte for byte the plugin's, with the
plugin version in the name; `tm page files` marks them fixed with their sha256, so the agent reads index.html alone."""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from html import unescape

import pytest
import requests

from tm import __version__, atlas, atlas_prompt, page, research_report, run_page
from tm.cli import main
from tm.run_page import static, styles, template


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("offline in tests")
    monkeypatch.setattr(page.requests, "get", no_network)


def _refresh(tmp_path, local=False):
    import test_run_page as rp
    run = rp.run.__wrapped__(tmp_path)
    built = run_page.build(run, rp._ask(run), local=local)
    return run, run.path / built["folder"]


def _report(tmp_path, local=False):
    from test_research_report import _cfg, _uroda
    run, _ = _uroda(tmp_path)
    return run, research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run), local=local)


def _ideas(tmp_path, monkeypatch):
    import test_style_order as so
    from test_run_page_organic import _ask
    run = so.animated.__wrapped__(tmp_path, monkeypatch)
    return run, run.path / run_page.build(run, _ask(run, "proposals"))["folder"]


def test_a_part_is_served_under_the_plugin_version_and_written_as_the_plugin_has_it(tmp_path):
    assert static.served("theme.css") == f"assets/static/theme-{__version__}.css"
    assert static.content("theme.css") == (template.THEME / "theme.css").read_text(encoding="utf-8").encode("utf-8")
    # the plugin's file, in LF on every system (a Windows checkout has CRLF; the page gets the same bytes everywhere)
    assert static.content("trend-report.css") == research_report.CSS_FILE.read_text(encoding="utf-8").encode("utf-8")
    assert static.content("page.js") == template.SCRIPT.encode("utf-8")
    (tmp_path / "index.html").write_text(static.link("theme.css") + static.script("page.js"), encoding="utf-8")
    (tmp_path / "assets" / "static").mkdir(parents=True)
    (tmp_path / "assets" / "static" / "theme-0.0.1.css").write_text("an older build's", encoding="utf-8")
    assert static.put(tmp_path) == [static.served("theme.css"), static.served("page.js")]
    assert sorted(p.name for p in (tmp_path / "assets" / "static").iterdir()) == \
        sorted([f"page-{__version__}.js", f"theme-{__version__}.css"])                       # the older one removed
    theme = tmp_path / static.served("theme.css")
    assert static.check(static.served("theme.css"), theme) == hashlib.sha256(theme.read_bytes()).hexdigest()
    assert static.check("assets/static/theme-0.0.1.css", theme) is None                      # another version's name
    theme.write_text("changed", encoding="utf-8")
    assert static.check(static.served("theme.css"), theme) is None


def test_the_run_page_holds_only_this_runs_data_and_page_files_marks_the_rest_fixed(tmp_path, capsys):
    run, folder = _refresh(tmp_path)
    html = (folder / "index.html").read_text(encoding="utf-8")
    assert "<style>" not in html and template.theme_css() not in html and "detailOf" not in html
    assert f'<link rel="stylesheet" href="assets/static/theme-{__version__}.css">' in html
    assert html.endswith(f'<script src="assets/static/page-{__version__}.js"></script></body></html>')
    assert main(["page", "files", "--run", str(run.path), "--page", run_page.page_name(run), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    fixed = {f["as"]: f for f in out["summary"]["fixed"]}
    assert set(fixed) == {static.served("theme.css"), static.served("page.js")}
    assert all(f["fixed"] is True and f["sha256"] == hashlib.sha256((folder / a).read_bytes()).hexdigest()
               for a, f in fixed.items())
    assert out["summary"]["not_fixed"] == [] and out["summary"]["read"]["as"] == "index.html"
    assert static.served("page.js") in out["artifact"]["files"]                    # published with the page
    (folder / static.served("page.js")).write_text("edited", encoding="utf-8")
    assert main(["page", "files", "--run", str(run.path), "--page", run_page.page_name(run)]) == 0
    assert "build the page again" in capsys.readouterr().out


def test_the_trend_report_holds_no_stylesheet_or_script_of_its_own(tmp_path):
    run, folder = _report(tmp_path)
    html = (folder / "index.html").read_text(encoding="utf-8")
    assert "<style>" not in html and ".report .card" not in html and "views.forEach" not in html
    for name in ("theme.css", "page.js", "trend-report.css", "trend-report.js"):
        assert (folder / static.served(name)).read_bytes() == static.content(name)
    assert html.index(static.served("theme.css")) < html.index(static.served("trend-report.css")) < html.index("</head>")
    parts = json.loads((folder / research_report.REPORT_PARTS).read_text(encoding="utf-8"))
    assert parts["css"] == "" and parts["styles"] == ["trend-report.css"]


def test_a_report_kept_with_its_css_inline_still_shows_it(tmp_path):
    """A report built before its stylesheet was a fixed part: the run page built under it keeps its CSS inline."""
    run, folder = _report(tmp_path)
    parts_file = folder / research_report.REPORT_PARTS
    parts = json.loads(parts_file.read_text(encoding="utf-8"))
    parts_file.write_text(json.dumps({"title": parts["title"], "css": ".report{color:red}", "body": parts["body"]}),
                          encoding="utf-8")
    built = run_page.build(run)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert "<style>.report{color:red}</style>" in html and static.served("trend-report.css") not in html
    assert not (run.path / built["folder"] / static.served("trend-report.css")).exists()     # the carried copy removed


def test_the_ideas_page_loads_the_style_catalogue_once_as_a_script(tmp_path, monkeypatch):
    run, folder = _ideas(tmp_path, monkeypatch)
    html = (folder / "index.html").read_text(encoding="utf-8")
    s = atlas_prompt.styles()[0]
    assert s["description"] not in html and "fetch(" not in (folder / static.served("styles.js")).read_text()
    assert html.count(f'<script src="{static.served("styles.js")}"></script>') == 1
    assert html.index('class="sty-slot"') < html.index(static.served("styles.js")) < html.index(static.served("page.js"))
    js = (folder / static.served("styles.js")).read_text(encoding="utf-8")
    data = json.loads(re.match(r"window\.TM_STYLES = (.*?);\n", js).group(1))
    assert sum(len(g["styles"]) for g in data) == len(atlas_prompt.styles())
    assert all((folder / x[k]).is_file() for g in data for x in g["styles"] for k in ("poster", "loop"))
    assert data == styles.catalogue()


# --- opened as a local file in a real browser ------------------------------------------------------------------

BROWSER = atlas.find_browser()
DRIVE = """<script>setTimeout(() => {
  const css = getComputedStyle(document.body);
  document.body.setAttribute('data-result', JSON.stringify({
    background: css.backgroundColor, tiles: document.querySelectorAll('.sty-tile').length,
    options: document.querySelectorAll('select[data-or] option').length, styles: (window.TM_STYLES || []).length,
    radios: Array.from(document.querySelectorAll('.sty-all input[type=radio]')).map(r => r.value),
    js: document.documentElement.className, reportCss: getComputedStyle(document.querySelector('.report') || document.body).display}));
}, 800);</script>"""


def _open(folder) -> dict:
    """The page opened over file:// in headless Chrome (no flag lets it read other files), measured by DRIVE."""
    html = (folder / "index.html").read_text(encoding="utf-8").replace("</body>", DRIVE + "</body>", 1)
    probe = folder / "probe.html"
    probe.write_text(html, encoding="utf-8")
    with tempfile.TemporaryDirectory() as profile:
        args = [str(BROWSER), "--headless=new", f"--user-data-dir={profile}", "--disable-gpu", "--no-first-run",
                "--virtual-time-budget=5000", "--dump-dom", probe.resolve().as_uri()]
        if atlas.needs_no_sandbox(BROWSER):
            args.insert(1, "--no-sandbox")
        dom = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120).stdout
    probe.unlink()
    m = re.search(r'data-result="([^"]*)"', dom)
    assert m, "the page did not run its scripts"
    return json.loads(unescape(m.group(1)))


@pytest.mark.skipif(BROWSER is None or atlas.is_headless_shell(BROWSER), reason="needs Chrome or Edge")
def test_a_local_build_opened_as_a_file_loads_its_fixed_parts(tmp_path, monkeypatch):
    """Chrome refuses a page opened from a file a fetch() of its own folder, but loads its stylesheets and scripts:
    the theme (the body's cream), the catalogue (49 tiles and the lists), the report's script and stylesheet."""
    _, folder = _refresh(tmp_path / "a", local=True)
    assert _open(folder)["background"] == "rgb(255, 244, 230)"            # theme.css's --cream
    _, folder = _ideas(tmp_path / "b", monkeypatch)
    got = _open(folder)
    assert got["styles"] > 0 and got["tiles"] == len(atlas_prompt.styles())
    assert got["options"] == len(atlas_prompt.styles()) - 2 + 1           # every other style, and "Choose a style"
    assert got["radios"] == []                                             # the gallery drawn once has no radio
    import test_style_order as so
    taste = so.tasting.__wrapped__(tmp_path / "t")
    got = _open(taste.path / so._taste_built(taste)["folder"])             # D2: one picker, the gallery's radios
    assert len(got["radios"]) == len(atlas_prompt.styles()) - 2 and "g-low-poly" in got["radios"]
    _, folder = _report(tmp_path / "c", local=True)
    got = _open(folder)
    assert got["js"] == "js" and got["background"] == "rgb(255, 244, 230)" and got["reportCss"] == "grid"
