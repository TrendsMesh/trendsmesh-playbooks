"""tm tool site (issue 96): sharp captures of the product's site at a device scale of 2 or 3 (or of one element), and
the brand's font and logo read from its style sheets and pages. The site, its style sheets, Google Fonts and the
browser are stand-ins here (nothing is fetched from the network); the font files are the ones the plugin's own
environment ships, and one capture runs in a real browser on a page served from this computer when it has one."""

from __future__ import annotations

import http.server
import json
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

import pytest
from _media import ffmpeg

from tm import config, create_config, manifest
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder
from tm.tools import _common as c
from tm.tools import site

SITE = "https://acme-notes.test/"


def _env_font(name: str) -> Path:
    for folder in (Path(sys.prefix) / "fonts", Path(sys.prefix) / "Library" / "fonts", Path(sys.prefix) / "share" / "fonts"):
        if (folder / name).is_file():
            return folder / name
    pytest.skip(f"the environment ships no {name}")


@pytest.fixture
def ad(tmp_path):
    run = RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "acme ad", date(2026, 11, 12), playbook=CREATE_AD)
    config.save(run, create_config.defaults())
    return run


def _run(capsys, *argv):
    code = site.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


# --- reading the style sheets ---------------------------------------------------------------------

CSS = """
:root { --font-sans: "__Acme_Grotesk_a1b2c3", "__Acme_Grotesk_Fallback_a1b2c3", system-ui; --font-size-lg: 18px;
        --font-weight-bold: 700; }
body { font-family: var(--font-sans), sans-serif; }
h1, h2 { font-family: var(--font-sans); }
code { font-family: "Source Code Pro", monospace; }
.small { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; }
@font-face { font-family: "__Acme_Grotesk_a1b2c3"; font-weight: 100 900; font-style: normal;
             src: url(/fonts/grotesk.woff2) format("woff2"); }
"""


def test_the_families_the_site_uses_most_come_first():
    used = site.families_used(CSS)
    assert used == {"Acme Grotesk": 3, "Source Code Pro": 1}      # a system stack names no family of the brand
    faces = site.font_faces(CSS, SITE)
    assert faces == [{"family": "Acme Grotesk", "weight": "100 900", "style": "normal",
                      "srcs": [("https://acme-notes.test/fonts/grotesk.woff2", "woff2")]}]
    assert site._weights(faces) == ["400", "700"]


def test_only_a_file_ffmpeg_can_draw_is_taken_ttf_first():
    assert site._best([("a.woff2", "woff2")]) is None
    assert site._best([("a.woff2", "woff2"), ("a.woff", "woff"), ("a.ttf", "truetype")]) == ("a.ttf", ".ttf")
    assert site._best([("a.otf", "opentype"), ("a.woff", "woff")]) == ("a.otf", ".otf")


def test_a_self_hosted_name_is_looked_up_on_google_fonts_as_it_is_known_there():
    assert site._google_names("Inter Variable") == ["Inter Variable", "Inter"]
    assert site._google_names("GeistSans") == ["GeistSans", "Geist Sans", "Geist"]
    assert site._google_names("SourceCodePro") == ["SourceCodePro", "Source Code Pro"]
    assert site.google_families(["https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;800&family=Lora",
                                 "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;1,700",
                                 "https://example.test/x.css"]) == {"Work Sans": ["400", "800"], "Lora": ["400", "700"]}


@pytest.mark.tools
def test_a_font_is_kept_only_when_ffmpeg_draws_it(tmp_path):
    assert site.drawable(_env_font("SourceCodePro-Bold.ttf"))
    fake = tmp_path / "not a font.ttf"
    fake.write_bytes(b"\x00\x01\x00\x00 this is not a font")
    assert not site.drawable(fake)


# --- the logo -------------------------------------------------------------------------------------

PAGE = """<html><head>
<link rel="icon" href="/favicon.ico"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<meta property="og:image" content="https://acme-notes.test/share.png">
<link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@500">
</head><body>
<header><a class="site-logo" href="/" aria-label="Acme Notes home"><svg viewBox="0 0 120 30" width="120" height="30"><rect width="120" height="30" fill="#2a6"/></svg></a></header>
<section class="customers"><img class="customer-logo" src="https://cdn.test/acme-notes/logo-bigcorp.png" alt="BigCorp"></section>
</body></html>"""


def test_the_logo_that_names_the_brand_comes_before_a_customers():
    page = site._Page()
    page.feed(PAGE)
    found = site.logo_candidates(page, PAGE, SITE)
    assert [(x["kind"], x["names_brand"]) for x in found] == [
        ("svg_logo", True), ("logo", False), ("icon", False), ("icon", False), ("share_image", False)]
    assert found[1]["url"] == "https://cdn.test/acme-notes/logo-bigcorp.png"      # its folder names the brand, not it
    assert found[2]["url"] == "https://acme-notes.test/apple-touch-icon.png"      # the largest icon first
    assert site.brand_name("https://shop.acme-notes.co.uk/x") == "acme-notes"


# --- brand, end to end ----------------------------------------------------------------------------

def _png(path: Path, size: str) -> bytes:
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=red:s={size}",
                    "-frames:v", "1", "-update", "1", str(path)], check=True)
    return path.read_bytes()


@pytest.fixture
def web(monkeypatch, tmp_path):
    """The site and Google Fonts as a dict of address -> bytes; no browser, so the page is read as served."""
    bold = _env_font("SourceCodePro-Bold.ttf").read_bytes()
    pages = {
        SITE: PAGE.encode(),
        "https://acme-notes.test/app.css": CSS.replace("url(/fonts/grotesk.woff2) format(\"woff2\")",
                                                     "url(/fonts/grotesk.woff2) format(\"woff2\"), "
                                                     "url(/fonts/grotesk.ttf) format(\"truetype\")").encode(),
        "https://acme-notes.test/fonts/grotesk.ttf": bold,
        "https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@500":
            b"@font-face { font-family: 'Source Code Pro'; font-style: normal; font-weight: 500; "
            b"src: url(https://fonts.gstatic.test/scp-500.ttf) format('truetype'); }",
        "https://fonts.gstatic.test/scp-500.ttf": bold,
        "https://acme-notes.test/apple-touch-icon.png": _png(tmp_path / "icon.png", "180x180"),
        "https://acme-notes.test/share.png": _png(tmp_path / "share.png", "1200x630"),
    }
    asked = []

    def get(url, *, limit, binary=False):
        asked.append(url)
        if url not in pages:
            raise c.ToolError(f"{url} answered 404.")
        data = pages[url]
        return (data, "") if binary else (data.decode("utf-8"), "")

    monkeypatch.setattr(site, "_get", get)
    monkeypatch.setattr(site.atlas, "find_browser", lambda: None)
    return asked


@pytest.mark.tools
def test_brand_takes_the_sites_font_and_logo_into_the_run(ad, web, capsys):
    code, out = _run(capsys, "brand", "--run", str(ad.path), SITE)
    assert code == 0, out
    assert out["outputs"] == ["02_research/brand_v01.json"] and out["read_with"] == "server"
    fonts = {f["family"]: f for f in out["fonts"]}
    assert list(fonts) == ["Acme Grotesk", "Source Code Pro"]
    grotesk = fonts["Acme Grotesk"]
    assert grotesk["source"] == "site" and "licence covers its ads" in grotesk["licence"]
    assert [x["file"] for x in grotesk["files"]] == ["02_research/brand/acme-grotesk-100-900.ttf"]
    scp = fonts["Source Code Pro"]
    assert scp["source"] == "google_fonts" and "open licence" in scp["licence"]
    assert [x["weight"] for x in scp["files"]] == ["500"]
    logos = out["logos"]
    assert logos[0]["kind"] == "svg_logo" and logos[0]["names_brand"] and logos[0]["file"].endswith(".svg")
    assert {x["kind"] for x in logos} >= {"svg_logo", "icon", "share_image"}
    assert out["missing"] == []
    for f in [x["file"] for f in out["fonts"] for x in f["files"]] + [x["file"] for x in logos]:
        assert (ad.path / f).is_file()
    sources = {r["file"]: r["source"] for r in manifest.rows(ad)}
    assert sources["02_research/brand_v01.json"] == "tm tool site brand"
    assert sources["02_research/brand/acme-grotesk-100-900.ttf"] == "tm tool site brand"


@pytest.mark.tools
def test_what_the_site_does_not_give_goes_to_the_asset_list(ad, web, monkeypatch, capsys):
    bare = "<html><head><style>body { font-family: 'Commercial Sans', sans-serif; }</style></head><body></body></html>"
    pages = {SITE: bare.encode()}
    monkeypatch.setattr(site, "_get", lambda url, *, limit, binary=False: (
        (pages[url], "") if binary else (pages[url].decode(), "")) if url in pages else
        (_ for _ in ()).throw(c.ToolError("404")))
    code, out = _run(capsys, "brand", "--run", str(ad.path), SITE)
    assert code == 0 and out["fonts"] == [] and out["logos"] == []
    assert any("Commercial Sans" in m and "TTF or OTF" in m for m in out["missing"])
    assert any(m.startswith("the logo") for m in out["missing"])


# --- capture --------------------------------------------------------------------------------------

@pytest.fixture
def browser(monkeypatch):
    """A browser stand-in: it draws a test picture at the view's size times the scale."""
    seen = []

    def chrome(args, url, *, browser=None):
        seen.append((args, url))
        scale = int(next(a for a in args if a.startswith("--force-device-scale-factor=")).split("=")[1])
        w, h = (int(v) for v in next(a for a in args if a.startswith("--window-size=")).split("=")[1].split(","))
        shot = next(a for a in args if a.startswith("--screenshot=")).split("=", 1)[1]
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"testsrc2=size={w * scale}x{h * scale}", "-frames:v", "1", "-update", "1", shot], check=True)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(site, "chrome", chrome)
    return seen


@pytest.mark.tools
def test_a_capture_is_full_size_at_the_device_scale(ad, browser, capsys):
    code, out = _run(capsys, "capture", "--run", str(ad.path), SITE)
    assert (code, out["outputs"], out["size"]) == (0, ["03_wip/site_home_v01.png"], [1080, 1920])
    assert browser[0][1] == SITE and "--force-device-scale-factor=2" in browser[0][0]
    code, out = _run(capsys, "capture", "--run", str(ad.path), SITE, "--scale", "3", "--clip", "40,1200,460,300",
                     "--name", "Rising card")
    assert code == 0 and out["outputs"] == ["03_wip/site_rising-card_v01.png"] and out["size"] == [1380, 900]
    assert out["view"] == [540, 1500]          # the view grew to hold the element
    rows = {r["file"]: r for r in manifest.rows(ad)}
    assert rows["03_wip/site_rising-card_v01.png"]["source"] == "tm tool site capture"


@pytest.mark.tools
def test_a_capture_is_never_at_scale_one_and_needs_a_web_address(ad, browser, capsys):
    assert _run(capsys, "capture", "--run", str(ad.path), SITE, "--scale", "1")[0] == 1
    code, out = _run(capsys, "capture", "--run", str(ad.path), "file:///etc/hosts")
    assert code == 1 and "web address" in out["message"]
    assert _run(capsys, "capture", "--run", str(ad.path), SITE, "--clip", "0,0,0,10")[0] == 1
    assert browser == []


def test_no_browser_is_a_stop_that_asks_for_the_files(ad, monkeypatch, capsys):
    monkeypatch.setattr(site.atlas, "find_browser", lambda: None)
    code, out = _run(capsys, "capture", "--run", str(ad.path), SITE)
    assert code == 2 and "Chrome" in out["message"] and "asset list" in out["message"]


@pytest.mark.tools
def test_a_real_browser_captures_a_page_served_here(ad, tmp_path, capsys):
    if site.atlas.find_browser() is None:
        pytest.skip("no Chrome or Edge on this computer")
    folder = tmp_path / "www"
    folder.mkdir()
    (folder / "index.html").write_text("<html><body style='margin:0;background:#2a6'><div id='card' style="
                                       "'position:absolute;left:20px;top:30px;width:200px;height:100px;background:"
                                       "#fff'></div></body></html>", encoding="utf-8")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(folder), **k)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        code, out = _run(capsys, "capture", "--run", str(ad.path), url, "--clip", "20,30,200,100", "--wait", "1")
    finally:
        server.shutdown()
    assert code == 0, out
    assert out["size"] == [400, 200]
