"""A web page's literal text, saved in the run (`tm page fetch`; page.py adds the parser).

    tm page fetch --run R --url URL --name SHORT [--kind landing|voice] [--found-in ad|pixel|library|user] [--json]

WebFetch does not give a page's text: a smaller model answers a prompt about the page, so what comes
back is a summary, which may rephrase, merge sentences or add a claim the page does not make. A quote
the brief takes from the landing page must be the page's own words (R3), so the page is saved here:

* The HTML is downloaded (an honest user agent; a site that refuses it, HTTP 401/403/429, is a Stop:
  never worked around) and turned into its text: scripts, styles, navigation, `noscript`, SVG and
  hidden parts dropped; the title, headings, paragraphs, list items, buttons and prices kept, one
  block a line, a blank line between blocks.
* When that text is nearly empty (fewer than `MIN_WORDS` words: a page built by JavaScript), the page
  is rendered with the user's own Chrome or Edge, headless (`atlas.find_browser`, the browser the
  animatic step drives), and the rendered DOM is read the same way. No browser, or still nearly empty,
  is a Stop.
* It is written to `00_raw/<kind>_<name>.txt` (never over a saved one: `_v02`, ...; `landing` at A1,
  `voice` for a review or discussion page at B2), with a first line naming the URL and the day, and
  recorded in the manifest with the URL, the day, how it was read and, for a landing page, where the
  URL was found (`--found-in`: the ad, the Pixel, the Ad Library, the user).

WebFetch stays a last resort. Its file is a summary: `00_raw/landing_<name>.summary.txt`, recorded with
a source that starts "WebFetch summary". `landing_texts(run)` tells the literal landing files from the
summaries (by that name, or by a manifest source naming WebFetch), and `tm brief check` reads a
quote given as the landing page's against the literal ones only (`brief_checks.landing_quotes`).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

import requests

from tm import __version__, cli, manifest
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

USER_AGENT = f"trendsmesh-playbooks/{__version__} (page text for a brief; read-only; https://trendsmesh.com)"
TIMEOUT = 30
RENDER_TIMEOUT_S = 90
RENDER_WAIT_MS = 15000           # the page's own scripts run this long (virtual time) before the DOM is read
MIN_WORDS = 40                   # fewer: the page is built by JavaScript, so it is rendered
RAW = "00_raw"
KINDS = ("landing", "voice")
FOUND_IN = ("ad", "pixel", "library", "user")
SUMMARY_SUFFIX = ".summary.txt"
TEXT_SUFFIXES = (".txt", ".md")
BLOCKED = (401, 403, 429)
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?([A-Za-z0-9._-]+)""", re.I)

# Parts of a page that are not its text.
SKIP = {"script", "style", "noscript", "template", "svg", "nav", "iframe", "canvas", "object", "embed", "head"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track",
        "wbr"}
BLOCKS = {"address", "article", "aside", "blockquote", "body", "br", "button", "caption", "dd", "details", "dialog",
          "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
          "h6", "header", "hr", "label", "legend", "li", "main", "nav", "ol", "option", "p", "pre", "section",
          "summary", "table", "tbody", "tfoot", "thead", "tr", "ul"}
CELLS = {"td", "th"}


class _Text(HTMLParser):
    """The page's text, one block a line. A stack of open elements keeps what is skipped: an end tag
    closes up to its own element (an unclosed `<p>` or `<li>` is closed with its parent), a stray one
    is ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []    # (tag, skipped)
        self.lines: list[str] = []
        self.line: list[str] = []
        self.title: list[str] = []
        self.in_title = False

    def _skipping(self) -> bool:
        return any(skipped for _, skipped in self.stack)

    def _flush(self) -> None:
        text = " ".join("".join(self.line).split())
        if text:
            self.lines.append(text)
        self.line = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title" and not any(t == "svg" for t, _ in self.stack):   # an icon's <title> is not the page's
            self.in_title = True
        if tag == "body":                         # a page that never closed its <head>
            self.stack = [(t, skipped) for t, skipped in self.stack if t != "head"]
        if tag in VOID:
            if tag in BLOCKS and not self._skipping():
                self._flush()
            return
        hidden = ("hidden" in a or a.get("aria-hidden", "").lower() == "true"
                  or a.get("role", "").lower() == "navigation")
        if tag in BLOCKS and not self._skipping():
            self._flush()
        elif tag in CELLS and not self._skipping():
            self.line.append(" ")
        self.stack.append((tag, tag in SKIP or hidden))

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCKS and not self._skipping():
            self._flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if not any(t == tag for t, _ in self.stack):
            return
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break
        if (tag in BLOCKS or tag in CELLS) and not self._skipping():
            if tag in CELLS:
                self.line.append(" ")
            else:
                self._flush()

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        elif not self._skipping():
            self.line.append(data)

    def text(self) -> str:
        self._flush()
        lines, out = self.lines, []
        title = " ".join("".join(self.title).split())
        if title:
            out.append(title)
        for line in lines:
            if not out or line != out[-1]:
                out.append(line)
        return "\n\n".join(out)


def html_to_text(html: str) -> str:
    """The literal text of an HTML page: its title first, then every block on a line of its own,
    separated by blank lines; spaces (and non-breaking spaces) in a line made one."""
    parser = _Text()
    parser.feed(html)
    parser.close()
    return parser.text()


def decode(body: bytes, content_type: str) -> str:
    """The page's characters: the charset of its Content-Type, else of its `<meta charset>`, else UTF-8."""
    m = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9._-]+)", content_type or "", re.I)
    name = m.group(1) if m else None
    if name is None:
        found = _CHARSET.search(body[:4096])
        name = found.group(1).decode("ascii") if found else "utf-8"
    try:
        return body.decode(name, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text))


LAST_RESORT = ("As a last resort, WebFetch it and save the answer as 00_raw/landing_<name>.summary.txt "
               "(recorded with the source \"WebFetch summary of <url>\"): a summary, from which no quote may be "
               "taken; or ask the user to save the page's text and give you the file")


def download(url: str) -> tuple[str, str]:
    """(the page's HTML, the URL it ended at). A failure is a Stop that says what to do."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                         timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        raise Stop(f"{url} could not be downloaded ({exc.__class__.__name__}). Check the link and run this again. "
                   f"{LAST_RESORT}; {AGAIN}.") from None
    status = r.status_code
    if status in BLOCKED:
        raise Stop(f"{url} refuses to be read by a program (HTTP {status}); this is not worked around. "
                   f"{LAST_RESORT}; {AGAIN}.")
    if status >= 400:
        raise Stop(f"{url} answered HTTP {status}. Check the link (the product page itself). {LAST_RESORT}; "
                   f"{AGAIN}.")
    ctype = (r.headers.get("Content-Type") or "").lower()
    if ctype and not any(t in ctype for t in ("html", "xml", "text/plain")):
        raise Stop(f"{url} is not a web page ({ctype.split(';')[0]}). Give the product's page itself; {AGAIN}.")
    return decode(r.content, ctype), getattr(r, "url", None) or url


def render(url: str) -> str:
    """The page's DOM after its scripts ran, from the user's Chrome or Edge, headless, in a fresh
    profile (`--dump-dom`). No browser, or the browser failing, is a Stop."""
    from tm import atlas   # it loads the animatic tier's paths: only when a page needs rendering
    browser = atlas.find_browser()
    if browser is None:
        raise Stop(f"{url} is built by JavaScript, so its text needs a browser to read it: install Google Chrome "
                   f"(or Microsoft Edge), then run this again. {LAST_RESORT}; {AGAIN}.")
    headless = "--headless" if atlas.is_headless_shell(browser) else "--headless=new"
    with tempfile.TemporaryDirectory(prefix="tm-page-") as profile:
        argv = [str(browser), headless, "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--mute-audio", f"--user-data-dir={profile}",
                f"--virtual-time-budget={RENDER_WAIT_MS}", "--dump-dom", url]
        if atlas.needs_no_sandbox(browser):
            argv.insert(1, "--no-sandbox")
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=RENDER_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Stop(f"The browser could not render {url} ({exc.__class__.__name__}). {LAST_RESORT}; "
                       f"{AGAIN}.") from None
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()[-1:] or ["no output"]
        raise Stop(f"The browser could not render {url} ({detail[0][:200]}). {LAST_RESORT}; {AGAIN}.")
    return proc.stdout.decode("utf-8", errors="replace")


def _check(url: str, name: str, kind: str, found_in: str | None) -> None:
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"--url must be an http(s) link, not {url!r}.")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError(f"--name {name!r} is not a short name: use letters, digits, '-' and '_' (e.g. duvet).")
    if kind not in KINDS:
        raise ValueError(f"--kind is {' or '.join(KINDS)}, not {kind!r}.")
    if found_in is not None and found_in not in FOUND_IN:
        raise ValueError(f"--found-in is one of {', '.join(FOUND_IN)}, not {found_in!r}.")


def save(run: RunFolder, url: str, name: str, kind: str = "landing", found_in: str | None = None) -> dict:
    """Download (or render) the page and save its text as `00_raw/<kind>_<name>.txt`, recorded."""
    _check(url, name, kind, found_in)
    html, final = download(url)
    text, how = html_to_text(html), "downloaded"
    if _words(text) < MIN_WORDS:
        text, how = html_to_text(render(final)), "rendered"
        if _words(text) < MIN_WORDS:
            raise Stop(f"{url} has almost no text, even rendered in the browser ({_words(text)} words): it may be "
                       f"a sign-in page or a page that blocks programs. Check the link. {LAST_RESORT}; {AGAIN}.")
    today = date.today().isoformat()
    target = run.unique_path(f"{RAW}/{kind}_{name}.txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    way = "downloaded" if how == "downloaded" else "rendered in a headless browser"
    target.write_text(f"{url} (saved {today} by tm page fetch, {way}: the page's own text)\n\n{text}\n",
                      encoding="utf-8")
    rel = target.relative_to(run.path).as_posix()
    params = {"url": url, "saved": today, "how": how, "words": _words(text)}
    if final != url:
        params["final_url"] = final
    if found_in:
        params["found_in"] = found_in
    manifest.record(run, rel, RAW, f"tm page fetch {url} ({way})", params=params)
    return {"file": rel, "url": url, "final_url": final, "how": how, "words": params["words"],
            "found_in": found_in, "saved": today}


# --- literal or summary --------------------------------------------------------------------------

def _params(row: dict) -> dict:
    try:
        got = json.loads(row.get("params") or "{}")
    except ValueError:
        return {}
    return got if isinstance(got, dict) else {}


def landing_texts(run: RunFolder) -> tuple[list[tuple[str, str, str | None]], list[str]]:
    """The landing pages saved in 00_raw: ([(file, text, its URL or None)] of the literal ones,
    [file] of the summaries). A summary is a `*.summary.txt`, or a file the manifest records from
    WebFetch. Only text files (`.txt`, `.md`) are read."""
    rows = manifest.rows(run)
    literal, summaries = [], []
    for path in sorted((run.path / RAW).glob("landing_*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(run.path).as_posix()
        mine = [r for r in rows if r.get("file") == rel]
        if rel.endswith(SUMMARY_SUFFIX) or any("webfetch" in (r.get("source") or "").lower() for r in mine):
            summaries.append(rel)
            continue
        url = next((_params(r).get("url") for r in mine if _params(r).get("url")), None)
        literal.append((rel, path.read_text(encoding="utf-8", errors="replace"), url))
    return literal, summaries


# --- command line (page.py adds the parser and calls `run_fetch`) ------------------------------------

def add_parser(sub: argparse._SubParsersAction) -> None:
    f = sub.add_parser("fetch", help="save a web page's literal text in 00_raw (not a summary)")
    f.add_argument("--run", required=True, help="the run folder")
    f.add_argument("--url", required=True, help="the page's http(s) link")
    f.add_argument("--name", required=True, help="a short name: the file is 00_raw/<kind>_<name>.txt")
    f.add_argument("--kind", default="landing", choices=KINDS,
                   help="landing (the product's page, A1; default) or voice (a review or discussion page, B2)")
    f.add_argument("--found-in", choices=FOUND_IN,
                   help="where the landing link was found: the ad, the Pixel, the Ad Library or the user")
    f.add_argument("--json", action="store_true")


def run_fetch(args: argparse.Namespace, run: RunFolder) -> int:
    got = save(run, args.url, args.name, args.kind, args.found_in)
    how = "downloaded" if got["how"] == "downloaded" else "rendered in a headless browser"
    message = f"Saved {got['file']}: the text of {got['url']} ({got['words']} words, {how}), recorded."
    cli.emit(args, {"status": "done", **got, "message": message}, message)
    return 0
