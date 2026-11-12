"""The product's site for the edit (Create an ad's S0 and G3, issue 96): sharp captures, and its font and logo.

    tm tool site capture --run RUN URL [--width 540] [--height 960] [--scale 2] [--clip X,Y,W,H] [--name STEM]
                         [--wait SEC] [--json]
    tm tool site brand   --run RUN URL [--brand NAME] [--json]

- **capture**: the page drawn in the user's own Chrome or Edge (`tm.atlas.find_browser`, headless, a profile of its
  own that is deleted after) at a device scale of 2 or 3 (`--scale`), so a 540×960 view is a 1080×1920 picture and a
  card is never scaled up in the edit. `--clip` takes the element's own box (CSS px of the page, as the browser's
  `getBoundingClientRect()` plus the scroll gives it): the view grows to hold it and the picture is cut to it, at the
  same scale. Writes the next `03_wip/site_<STEM>_vNN.png`.
- **brand**: the page (in the browser when there is one, else as the server sends it), its style sheets and the
  Google Fonts it links, read for the font and the logo. **Fonts**: the families the style sheets use most (the
  generic and system ones left out), each weight's file from the site's own `@font-face` (TTF, OTF or WOFF: the
  plugin's ffmpeg cannot draw WOFF2) or from Google Fonts by its name; each file is drawn once with ffmpeg and kept
  only when it draws. **Logos**: the images and inline SVGs the page marks as a logo, those that name the brand (its
  address's name, or `--brand`) first (`names_brand`: another may be a customer's), its icons
  (`apple-touch-icon`, `icon`) and its share image, each with a PNG for the edit (an SVG drawn 1024 px wide). Files go
  into `02_research/brand/`, and `02_research/brand_vNN.json` lists them: {"url", "read_with" (browser, server),
  "fonts": [{"family", "google_family" (its name there), "uses", "source" (site, google_fonts), "licence", "files":
  [{"file", "weight", "style", "url"}]}], "logos": [{"file", "png", "kind" (logo, svg_logo, icon, share_image),
  "names_brand", "width", "height", "url"}],
  "missing": [...], "message"}. What is missing goes into the asset list's question (S0): the user's own files.

Only http and https addresses are read. Free and local (the base tools and the user's browser).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from tm import __version__, atlas
from tm.tools import _common as c

USER_AGENT = f"trendsmesh-playbooks/{__version__} (the product's font and logo for its own ad)"
TIMEOUT = 30
CHROME_TIMEOUT = 120
GRACE_S = 10
SCALES = (2, 3)
MAX_VIEW = 8000            # CSS px a view may grow to for a clip
MAX_SHEETS, MAX_CSS = 40, 2_000_000
MAX_FONT, MAX_IMAGE = 10_000_000, 5_000_000
FAMILIES, WEIGHTS, LOGOS = 2, 4, 8
BRAND_DIR = "02_research/brand"
GOOGLE_CSS = "https://fonts.googleapis.com/css2?family={family}:wght@{weight}"
DRAWABLE = (".ttf", ".otf", ".woff")
FORMAT_RANK = {"truetype": 0, "ttf": 0, "opentype": 1, "otf": 1, "woff": 2}
GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif",
           "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "segoe ui", "helvetica neue",
           "helvetica", "arial", "noto color emoji", "apple color emoji", "segoe ui emoji", "segoe ui symbol",
           "emoji", "math", "inherit", "initial", "unset", "revert", "revert-layer", "times new roman", "courier new",
           "menlo", "monaco", "consolas", "liberation mono", "sfmono-regular", "sf mono", "georgia", "verdana",
           "tahoma", "ubuntu", "cantarell", "fira sans", "droid sans", "oxygen", "icons", "fontawesome"}
GOOGLE_LICENCE = "Google Fonts: an open licence (SIL Open Font License or Apache 2.0), free in ads"
NOT_FAMILY = re.compile(r"weight|size|feature|variation|style|stretch|smooth|display|leading|line|letter|tracking|"
                        r"optical|synthesis|kerning|scale", re.I)
SITE_LICENCE = ("the brand's own font, served by its site: a font bought for the web may not cover video, so the "
                "user confirms the brand's licence covers its ads")


# --- the browser --------------------------------------------------------------------------------

def _browser() -> Path:
    found = atlas.find_browser()
    if found is None:
        raise c.ToolStop("This needs Google Chrome or Microsoft Edge on this computer (Chromium on Linux), and none "
                         "was found. Nothing was read. Ask the user for the screenshots, the logo and the font "
                         "files instead (the asset list), or to install Chrome and say continue.")
    return found


def chrome(args: list[str], url: str, *, browser: Path | None = None) -> subprocess.CompletedProcess:
    """The browser, headless, on `url`, with a profile of its own deleted after; stopped with all it started after
    CHROME_TIMEOUT."""
    browser = browser or _browser()
    profile = Path(tempfile.mkdtemp(prefix="tm-site-"))
    argv = [str(browser), "--headless" if atlas.is_headless_shell(browser) else "--headless=new", "--disable-gpu",
            "--hide-scrollbars", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
            "--mute-audio", f"--user-data-dir={profile}",
            *(["--no-sandbox"] if atlas.needs_no_sandbox(browser) else []), *args, url]
    group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
             else {"start_new_session": True})
    try:
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    encoding="utf-8", errors="replace", **group)
        except OSError as exc:
            raise c.ToolError(f"Could not start the browser: {exc}") from None
        try:
            out, err = proc.communicate(timeout=CHROME_TIMEOUT)
        except subprocess.TimeoutExpired:
            atlas._kill_tree(proc)
            raise c.ToolError(f"The browser did not finish {url} in {CHROME_TIMEOUT} s and was stopped.") from None
        except BaseException:
            atlas._kill_tree(proc)
            raise
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _url(text: str) -> str:
    parts = urlsplit(text.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise c.ToolError(f"{text} is not a web address (http or https). Nothing was read.")
    return text.strip()


# --- capture ------------------------------------------------------------------------------------

def parse_clip(text: str) -> tuple[int, int, int, int]:
    try:
        x, y, w, h = (int(round(float(v))) for v in text.split(","))
    except ValueError:
        raise c.ToolError(f"--clip {text} must be X,Y,W,H in CSS px of the page (e.g. 40,880,460,300).") from None
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise c.ToolError(f"--clip {text} needs X and Y of 0 or more and a width and a height above 0.")
    return x, y, w, h


def view_for(width: int, height: int, clip: tuple | None) -> tuple[int, int]:
    """The view (CSS px) that holds the clip."""
    if clip is None:
        return width, height
    x, y, w, h = clip
    need_w, need_h = max(width, x + w), max(height, y + h)
    if need_w > MAX_VIEW or need_h > MAX_VIEW:
        raise c.ToolError(f"--clip reaches {need_w}×{need_h} CSS px; a view holds at most {MAX_VIEW} px each way.")
    return need_w, need_h


def capture(run, a) -> tuple[dict, str]:
    url = _url(a.url)
    if a.scale not in SCALES:
        raise c.ToolError(f"--scale is {' or '.join(map(str, SCALES))}: a capture at 1 is scaled up in the edit.")
    if not (200 <= a.width <= 4000 and 200 <= a.height <= 4000):
        raise c.ToolError("--width and --height are CSS px of the view, 200 to 4000.")
    clip = parse_clip(a.clip) if a.clip else None
    view = view_for(a.width, a.height, clip)
    stem = _slug(a.name or "home")
    out = run.next_version("03_wip", f"site_{stem}", "png")
    scratch = Path(tempfile.mkdtemp(prefix="tm-shot-"))
    try:
        shot = scratch / "shot.png"
        proc = chrome([f"--force-device-scale-factor={a.scale}", f"--window-size={view[0]},{view[1]}",
                       f"--virtual-time-budget={int(a.wait * 1000)}", f"--screenshot={shot}"], url)
        if not shot.is_file():
            tail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
            raise c.ToolError(f"The browser drew no picture of {url}: {tail}")
        part = out.with_name(f".{out.stem}.part.png")
        crop = []
        if clip:
            x, y, w, h = (v * a.scale for v in clip)
            crop = ["-vf", f"crop={w}:{h}:{x}:{y}"]
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", "-i", c.media(shot), *crop,
                        "-frames:v", "1", "-update", "1", c.media(part)], capture_output=True, check=True)
        c.replace(part, out)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    found = c.probe(out)
    size = [found.get("width"), found.get("height")]
    params = {"url": url, "view": list(view), "scale": a.scale, "clip": list(clip) if clip else None, "size": size}
    c.record(run, out, "tm tool site capture", None, params=params, model="the user's browser, headless",
             cost="0 (local)")
    rel = c.rel(run, out)
    return ({"outputs": [rel], **params},
            f"Wrote {rel}: {size[0]}×{size[1]} px of {url} at {a.scale}× (draw it at most that size in the edit).")


# --- brand: reading the page --------------------------------------------------------------------

class _Page(HTMLParser):
    """Links, images, metas and style blocks of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.images: list[dict] = []
        self.metas: list[dict] = []
        self.styles: list[str] = []
        self._style = False

    def handle_starttag(self, tag, attrs):
        d = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link":
            self.links.append(d)
        elif tag == "img":
            self.images.append(d)
        elif tag == "meta":
            self.metas.append(d)
        elif tag == "style":
            self._style = True
            self.styles.append("")

    def handle_endtag(self, tag):
        if tag == "style":
            self._style = False

    def handle_data(self, data):
        if self._style:
            self.styles[-1] += data


def _get(url: str, *, limit: int, binary: bool = False):
    import requests

    with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True) as answer:
        if answer.status_code != 200:
            raise c.ToolError(f"{url} answered {answer.status_code}.")
        got = b""
        for chunk in answer.iter_content(1 << 16):
            got += chunk
            if len(got) > limit:
                raise c.ToolError(f"{url} is over {limit // 1_000_000} MB.")
        kind = answer.headers.get("Content-Type", "")
    return (got, kind) if binary else (got.decode(answer.encoding or "utf-8", "replace"), kind)


def read_page(url: str) -> tuple[str, str]:
    """(the page's HTML, how it was read: browser or server)."""
    browser = atlas.find_browser()
    if browser is not None:
        proc = chrome(["--virtual-time-budget=5000", "--dump-dom"], url, browser=browser)
        if proc.returncode == 0 and "<" in (proc.stdout or ""):
            return proc.stdout, "browser"
    return _get(url, limit=MAX_CSS * 5)[0], "server"


def _family(text: str) -> str:
    """A family name as written (quotes off; next/font's `__Inter_a1b2c3` is Inter)."""
    name = text.strip().strip("'\"").strip()
    name = re.sub(r"^_+", "", name)
    name = re.sub(r"_[0-9a-f]{6,}$", "", name)
    return name.replace("_", " ").strip()


def _first_family(value: str, variables: dict[str, str]) -> str | None:
    """The first family a `font-family` value names (through a font variable), None when it is generic."""
    for part in value.split(","):
        part = part.strip()
        ref = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)", part)
        if ref:
            if ref.group(1) in variables:
                return variables[ref.group(1)]
            continue
        name = _family(part)
        if (not name or "fallback" in name.lower() or "(" in name
                or re.fullmatch(r"[\d.]+\s*(px|rem|em|%|pt)?", name.lower())):
            continue
        return None if name.lower() in GENERIC else name
    return None


def families_used(css: str) -> dict[str, int]:
    """Each family named first in a `font-family`, counted (a font variable's family each time it is used, and once
    for its definition); generic and system ones left out."""
    css = re.sub(r"@font-face\s*\{[^}]*\}", "", css, flags=re.I)
    variables: dict[str, str] = {}
    counts: dict[str, int] = {}
    for prop, value in re.findall(r"(--[\w-]*font[\w-]*)\s*:\s*([^;{}]+)", css, re.I):
        if not NOT_FAMILY.search(prop):
            name = _first_family(value, variables)
            if name:
                variables.setdefault(prop, name)
                counts[name] = counts.get(name, 0) + 1
    for value in re.findall(r"font-family\s*:\s*([^;{}]+)", css, re.I):
        name = _first_family(value, variables)
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def font_faces(css: str, base: str) -> list[dict]:
    """The `@font-face` rules: {family, weight, style, srcs: [(url, format)]}."""
    out = []
    for body in re.findall(r"@font-face\s*\{([^}]*)\}", css, re.I):
        fam = re.search(r"font-family\s*:\s*([^;]+)", body, re.I)
        if not fam:
            continue
        weight = re.search(r"font-weight\s*:\s*([^;]+)", body, re.I)
        style = re.search(r"font-style\s*:\s*([^;]+)", body, re.I)
        srcs = []
        for src in re.findall(r"src\s*:\s*([^;]+)", body, re.I):
            for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)\s*"
                                 r"(?:format\(\s*['\"]?([\w-]+)['\"]?\s*\))?", src):
                link, fmt = m.group(1), (m.group(2) or "").lower()
                if not fmt:
                    fmt = Path(urlsplit(link).path).suffix.lower().lstrip(".")
                srcs.append((urljoin(base, link), fmt))
        out.append({"family": _family(fam.group(1)), "weight": _weight(weight.group(1) if weight else "400"),
                    "style": (style.group(1).strip().lower() if style else "normal"), "srcs": srcs})
    return out


def _weight(text: str) -> str:
    """A face's weight: `400`, or a variable font's range `100 900`."""
    text = " ".join(text.strip().lower().split())
    return {"normal": "400", "bold": "700"}.get(text, text or "400")


def _weights(faces: list[dict]) -> list[str]:
    """The weights to ask Google Fonts for: each face's, a range as its 400 and 700."""
    out: set[str] = set()
    for face in faces:
        parts = [int(x) for x in face["weight"].split() if x.isdigit()]
        if len(parts) == 2:
            out |= {str(w) for w in (400, 700) if parts[0] <= w <= parts[1]}
        elif parts:
            out.add(str(parts[0]))
    return sorted(out)[:WEIGHTS] or ["400", "700"]


def google_families(links: list[str]) -> dict[str, list[str]]:
    """The families a page's Google Fonts links ask for, each with its weights (`Work Sans:wght@400;800`,
    `ital,wght@0,400;1,700`, `Lora:400,700i`)."""
    out: dict[str, list[str]] = {}
    for link in links:
        parts = urlsplit(link)
        if parts.netloc != "fonts.googleapis.com":
            continue
        for value in parse_qs(parts.query).get("family", []):
            for one in value.split("|"):
                name, _, spec = unquote(one).partition(":")
                name = name.replace("+", " ").strip()
                if not name:
                    continue
                spec = spec.split("@", 1)[-1]
                weights = [m for part in re.split(r"[;,]", spec) for m in re.findall(r"\d{3}", part)[-1:]]
                known = out.setdefault(name, [])
                known += [w for w in weights if w not in known]
    return out


def _sheets(page: _Page, url: str) -> tuple[str, list[str]]:
    """All the page's CSS (its style blocks, its linked sheets and their imports, as far as MAX_SHEETS) and its
    Google Fonts links."""
    css = "\n".join(page.styles)
    hrefs = [urljoin(url, d["href"]) for d in page.links
             if "stylesheet" in d.get("rel", "").lower().split() and d.get("href")]
    google = [h for h in hrefs if urlsplit(h).netloc == "fonts.googleapis.com"]
    queue, seen = [h for h in hrefs if h not in google], set()
    while queue and len(seen) < MAX_SHEETS:
        href = queue.pop(0)
        if href in seen or urlsplit(href).scheme not in ("http", "https"):
            continue
        seen.add(href)
        try:
            text = _get(href, limit=MAX_CSS)[0]
        except (c.ToolError, OSError, ValueError):
            continue
        css += f"\n/* {href} */\n" + _absolute(text, href)
        for imp in re.findall(r"@import\s+(?:url\()?\s*['\"]?([^'\")\s;]+)", text):
            full = urljoin(href, imp)
            (google if urlsplit(full).netloc == "fonts.googleapis.com" else queue).append(full)
    return css, google


def _absolute(css: str, base: str) -> str:
    """The CSS with its url()s made absolute (a font's address is from its own sheet)."""
    return re.sub(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)",
                  lambda m: f"url({m.group(1)}{urljoin(base, m.group(2))}{m.group(1)})", css)


# --- brand: fonts -------------------------------------------------------------------------------

def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "font"


def drawable(font: Path) -> bool:
    """ffmpeg draws text with this file (a font it cannot read, WOFF2 here, silently falls back to another). The
    file is copied under a plain name into a folder of its own, so no path needs escaping in the filter."""
    folder = Path(tempfile.mkdtemp(prefix="tm-font-"))
    try:
        shutil.copyfile(font, folder / f"font{font.suffix.lower()}")

        def draw(fontfile: str | None) -> bytes | None:
            text = "drawtext=text='Hamburgefonstiv 0123':fontsize=48:fontcolor=white:x=10:y=10"
            text += f":fontfile={fontfile}" if fontfile else ""
            proc = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                                   "color=black:s=640x80", "-frames:v", "1", "-vf", text, "-f", "rawvideo",
                                   "-pix_fmt", "gray", "-"], capture_output=True, cwd=folder)
            return proc.stdout if proc.returncode == 0 and proc.stdout else None

        mine = draw(f"font{font.suffix.lower()}")
        if mine is None or not any(mine):
            return False
        return mine != draw(None)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _keep_font(run, url: str, family: str, weight: str, style: str, ext: str) -> Path | None:
    name = f"{_slug(family)}-{weight}{'-italic' if style == 'italic' else ''}{ext}"
    dest = run.path / BRAND_DIR / name
    if dest.is_file():
        return dest
    try:
        data, _ = _get(url, limit=MAX_FONT, binary=True)
    except (c.ToolError, OSError, ValueError):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f".{dest.name}.part{ext}")
    part.write_bytes(data)
    if not drawable(part):
        part.unlink(missing_ok=True)
        return None
    c.replace(part, dest)
    return dest


def _best(srcs: list[tuple[str, str]]) -> tuple[str, str] | None:
    """The source ffmpeg can draw, TTF first; WOFF2 never."""
    ranked = []
    for link, fmt in srcs:
        fmt = {"woff2": "woff2", "truetype": "truetype", "opentype": "opentype"}.get(fmt, fmt)
        if fmt in FORMAT_RANK and not link.startswith("data:"):
            ext = {"truetype": ".ttf", "ttf": ".ttf", "opentype": ".otf", "otf": ".otf", "woff": ".woff"}[fmt]
            ranked.append((FORMAT_RANK[fmt], link, ext))
    return min(ranked)[1:] if ranked else None


def _google(family: str, weights: list[str]) -> list[dict]:
    """The family's files from Google Fonts (TTF, what it serves a client that is not a browser), by weight."""
    out = []
    for weight in weights:
        url = GOOGLE_CSS.format(family=family.replace(" ", "+"), weight=weight)
        try:
            css = _get(url, limit=MAX_CSS)[0]
        except (c.ToolError, OSError, ValueError):
            continue
        for face in font_faces(css, url):
            if face["style"] == "normal":
                out.append({**face, "weight": weight})
                break
    return out


def _google_names(family: str) -> list[str]:
    """The family's name, and without a self-hosting suffix (`Inter Variable`, `InterVariable` and `Inter VF` are
    Inter on Google Fonts)."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", family.replace("-", " ").replace("_", " "))
    plain = re.sub(r"\s*(variable|var|vf|web|webfont)$", "", spaced, flags=re.I).strip()
    out = [family]
    for name in (spaced, plain, re.sub(r"\s+Sans$", "", plain)):
        if name and name not in out:
            out.append(name)
    return out[:4]


def fonts(run, css: str, google: dict[str, list[str]]) -> tuple[list[dict], list[str]]:
    """(the brand's fonts with their files in the run, what is missing): the families used most, one with a file
    (its own `@font-face` or a Google Fonts link) before one without at the same count."""
    used = families_used(css)
    faces = font_faces(css, "")
    for name in google:
        used.setdefault(name, 0)
    for face in faces:
        if face["family"].lower() not in GENERIC and "fallback" not in face["family"].lower():
            used.setdefault(face["family"], 0)
    sourced = {f["family"].lower() for f in faces} | {n.lower() for n in google}
    ranked = sorted(used, key=lambda f: (-used[f], f.lower() not in sourced, f))[:FAMILIES]
    out, missing = [], []
    for family in ranked:
        own = [f for f in faces if f["family"].lower() == family.lower() and f["style"] in ("normal", "italic")]
        files, source, done, google_name = [], "site", set(), None
        for face in sorted(own, key=lambda f: (f["style"] != "normal", f["weight"])):
            best = _best(face["srcs"])
            key = (face["weight"], face["style"])
            if not best or key in done or len(done) >= WEIGHTS:
                continue
            kept = _keep_font(run, best[0], family, face["weight"].replace(" ", "-"), face["style"], best[1])
            if kept:
                done.add(key)
                files.append({"file": c.rel(run, kept), "weight": face["weight"], "style": face["style"],
                              "url": best[0]})
        if not files:
            source = "google_fonts"
            for name in _google_names(family):
                linked = next((w for n, w in google.items() if n.lower() == name.lower() and w), None)
                for face in _google(name, _weights(own) if own else (linked or ["400", "700"])[:WEIGHTS]):
                    best = _best(face["srcs"])
                    kept = _keep_font(run, best[0], name, face["weight"], "normal", best[1]) if best else None
                    if kept:
                        files.append({"file": c.rel(run, kept), "weight": face["weight"], "style": "normal",
                                      "url": best[0]})
                if files:
                    google_name = name
                    break
        if files:
            out.append({"family": family, "google_family": google_name, "uses": used[family], "source": source,
                        "licence": GOOGLE_LICENCE if source == "google_fonts" else SITE_LICENCE, "files": files})
        else:
            missing.append(f"the font {family}: the site serves no file the edit can draw (TTF, OTF or WOFF) and "
                           "Google Fonts has none by that name: ask the user for its TTF or OTF")
    if not ranked:
        missing.append("the font: the site's style sheets name none of their own: ask the user which font the brand "
                       "uses, and for its file")
    return out, missing


# --- brand: logos -------------------------------------------------------------------------------

def _attrs(tag: str) -> dict:
    return {k.lower(): html.unescape(v1 or v2) for k, v1, v2 in
            re.findall(r"([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", tag)}


def brand_name(url: str) -> str:
    """The site's own name from its address: linear.app is linear, shop.example.co.uk is example."""
    labels = [x for x in urlsplit(url).netloc.lower().split(":")[0].split(".") if x and x != "www"]
    if len(labels) >= 3 and labels[-2] in ("co", "com", "org", "net", "ac", "gov"):
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else (labels[0] if labels else "")


def logo_candidates(page: _Page, raw: str, url: str, name: str = "") -> list[dict]:
    """[{url | svg, kind, names_brand}], the likeliest first: the images and inline SVGs marked as a logo that name
    the brand (the site's name, or `name`), then those that do not (a customer's logo may be one), each in page
    order; then the icons, largest first, and the share image."""
    names = {v for n in (name, brand_name(url)) if n and len(n) > 1
             for v in (n.lower(), n.lower().replace("-", " "), n.lower().replace("-", ""))}
    found: list[tuple[int, int, dict]] = []
    for m in re.finditer(r"<img\b[^>]*>", raw, re.I):
        d = _attrs(m.group(0))
        src = d.get("src") or (d.get("srcset", "").split(",")[0].split() or [""])[0]
        own = urlsplit(src).path.rsplit("/", 1)[-1]        # the file's own name, not the folders it sits in
        text = " ".join([own, *(d.get(k, "") for k in ("alt", "class", "id", "title", "aria-label"))]).lower()
        if src and "logo" in text:
            found.append((0 if any(n in text for n in names) else 1, m.start(),
                          {"url": urljoin(url, src), "kind": "logo"}))
    for m in re.finditer(r"<svg\b[^>]*>.*?</svg>", raw, re.S | re.I):
        # its own attributes or title, or the link or box it sits in (`<a class="logo">`, `aria-label="Linear"`)
        text = (m.group(0)[:400] + raw[max(0, m.start() - 200):m.start()]).lower()
        if "logo" in text or any(f'"{n}' in text for n in names):
            found.append((0 if any(n in text for n in names) else 1, m.start(),
                          {"svg": m.group(0), "kind": "svg_logo"}))
    out = [dict(cand, names_brand=rank == 0) for rank, _, cand in sorted(found, key=lambda x: x[:2])]
    named = [x for x in out if x["names_brand"]]
    out = (named + [x for x in out if not x["names_brand"]][:max(0, 3 - len(named))])[:LOGOS - 3]
    icons = []
    for d in page.links:
        rel = d.get("rel", "").lower().split()
        if d.get("href") and ({"apple-touch-icon", "icon", "mask-icon"} & set(rel)):
            size = max((int(n) for n in re.findall(r"(\d+)x\d+", d.get("sizes", ""))), default=0)
            icons.append((-(size or (180 if "apple-touch-icon" in rel else 0)), urljoin(url, d["href"])))
    out += [{"url": u, "kind": "icon", "names_brand": False} for _, u in sorted(icons)[:2]]
    for d in page.metas:
        if d.get("property", d.get("name", "")).lower() in ("og:image", "twitter:image") and d.get("content"):
            out.append({"url": urljoin(url, d["content"]), "kind": "share_image", "names_brand": False})
            break
    seen, unique = set(), []
    for cand in out:
        key = cand.get("url") or cand.get("svg")
        if key not in seen:
            seen.add(key)
            unique.append(cand)
    return unique[:LOGOS]


def _image_ext(data: bytes, kind: str, link: str) -> str | None:
    head = data[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2048].lower()) or "svg" in kind:
        return ".svg"
    for magic, ext in ((b"\x89png", ".png"), (b"\xff\xd8", ".jpg"), (b"gif8", ".gif"), (b"riff", ".webp"),
                       (b"\x00\x00\x01\x00", ".ico")):
        if data[:4].lower().startswith(magic):
            return ext
    suffix = Path(urlsplit(link).path).suffix.lower()
    return suffix if suffix in (".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif", ".svg") else None


def _fetch_image(link: str) -> tuple[bytes, str] | None:
    if link.startswith("data:"):
        m = re.match(r"data:([\w/+.-]+)?(;base64)?,(.*)", link, re.S)
        if not m:
            return None
        try:
            data = base64.b64decode(m.group(3)) if m.group(2) else unquote(m.group(3)).encode("utf-8")
        except (binascii.Error, ValueError):
            return None
        return data, m.group(1) or ""
    if urlsplit(link).scheme not in ("http", "https"):
        return None
    try:
        return _get(link, limit=MAX_IMAGE, binary=True)
    except (c.ToolError, OSError, ValueError):
        return None


def _png(src: Path, dest: Path) -> bool:
    """A PNG of the logo for the edit (an SVG drawn 1024 px wide), with its transparency."""
    first = ["-width", "1024", "-keep_ar", "1"] if src.suffix == ".svg" else []
    proc = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", *first, "-i", c.media(src),
                           "-frames:v", "1", "-update", "1", "-pix_fmt", "rgba", c.media(dest)], capture_output=True)
    return proc.returncode == 0 and dest.is_file()


def logos(run, page: _Page, raw: str, url: str, name: str = "") -> tuple[list[dict], list[str]]:
    out, kept = [], set()
    for n, cand in enumerate(logo_candidates(page, raw, url, name), 1):
        if "svg" in cand:
            data, link = cand["svg"].encode("utf-8"), None
            if b"xmlns" not in data[:400]:
                data = data.replace(b"<svg", b'<svg xmlns="http://www.w3.org/2000/svg"', 1)
            ext = ".svg"
        else:
            got = _fetch_image(cand["url"])
            if got is None:
                continue
            data, kind = got
            link = cand["url"] if not cand["url"].startswith("data:") else "data: (in the page)"
            ext = _image_ext(data, kind, cand["url"])
            if ext is None:
                continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in kept:      # the same picture twice (a light and a dark copy of one file)
            continue
        kept.add(digest)
        dest = run.unique_path(run.path / BRAND_DIR / f"{cand['kind']}_{n:02d}{ext}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        png = dest if ext == ".png" else dest.with_suffix(".png")
        if png is not dest and not _png(dest, png):
            png = None
        size = c.probe(png) if png else {}
        out.append({"file": c.rel(run, dest), "png": c.rel(run, png) if png else None, "kind": cand["kind"],
                    "names_brand": cand["names_brand"], "width": size.get("width"), "height": size.get("height"),
                    "url": link})
    if any(x["names_brand"] and x["png"] for x in out):
        missing = []
    elif any(x["kind"] in ("logo", "svg_logo") and x["png"] for x in out):
        missing = ["the logo: the page's logos do not name the brand (they may be its customers'): show them and "
                   "ask which is the brand's, or for the logo file"]
    else:
        missing = ["the logo: the page marks no image as its logo" + (" (only its icons were found)" if out else "") +
                   ": ask the user for the logo file (SVG or a PNG with transparency)"]
    return out, missing


def _said_font(font: dict) -> str:
    weights = ", ".join(x["weight"] + (" italic" if x["style"] == "italic" else "") for x in font["files"])
    return f"{font['family']} ({weights}; {font['licence']})"


def brand(run, a) -> tuple[dict, str]:
    url = _url(a.url)
    raw, how = read_page(url)
    page = _Page()
    page.feed(raw)
    css, google = _sheets(page, url)
    css = _absolute(css, url)
    google += [h for h in re.findall(r"https://fonts\.googleapis\.com/css2?\?[^'\")\s]+", raw) if h not in google]
    found_fonts, no_font = fonts(run, css, google_families([html.unescape(g) for g in google]))
    found_logos, no_logo = logos(run, page, raw, url, a.brand or "")
    missing = no_font + no_logo
    out = run.next_version("02_research", "brand", "json")
    said = (f"Fonts: {'; '.join(_said_font(f) for f in found_fonts) or 'none'}. Logos: "
            + ("; ".join(f"{x['png'] or x['file']} ({x['kind']}, {x['width']}×{x['height']})" for x in found_logos)
               or "none") + "." + (" Missing: " + "; ".join(missing) + "." if missing else ""))
    data = {"url": url, "read_with": how, "fonts": found_fonts, "logos": found_logos, "missing": missing,
            "message": said}
    c.write_json(out, data, newline="\n")
    for f in found_fonts:
        for x in f["files"]:
            c.record(run, run.path / x["file"], "tm tool site brand", None, params={"url": x["url"],
                     "family": f["family"], "licence": f["licence"]}, cost="free")
    for x in found_logos:
        for rel in {x["file"], x["png"]} - {None}:
            c.record(run, run.path / rel, "tm tool site brand", None, params={"url": x["url"], "kind": x["kind"]},
                     cost="free")
    c.record(run, out, "tm tool site brand", None, params={"url": url, "read_with": how}, cost="0 (local)")
    rel = c.rel(run, out)
    return {"outputs": [rel], **data}, f"Wrote {rel}. {said}"


ACTIONS = {"capture": capture, "brand": brand}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="tm tool site", allow_abbrev=False,
                                description="The product's site for the edit: sharp captures, its font and logo.")
    sub = p.add_subparsers(dest="action", required=True)
    for name, help_ in (("capture", "a capture at a device scale of 2 or 3, or of one element"),
                        ("brand", "the site's font and logo files")):
        s = sub.add_parser(name, help=help_, allow_abbrev=False)
        s.add_argument("--run", required=True, help="the run folder")
        s.add_argument("--json", action="store_true", help="print one JSON object")
        s.add_argument("url", help="the page's address (http or https)")
        if name == "capture":
            s.add_argument("--width", type=int, default=540, help="the view's width in CSS px (default 540)")
            s.add_argument("--height", type=int, default=960, help="the view's height in CSS px (default 960)")
            s.add_argument("--scale", type=int, default=2, help="the device scale, 2 or 3 (default 2)")
            s.add_argument("--clip", help="X,Y,W,H of the element in CSS px of the page")
            s.add_argument("--name", help="what the capture shows, for its file name (default home)")
            s.add_argument("--wait", type=float, default=5.0, help="seconds the page gets to draw (default 5)")
        else:
            s.add_argument("--brand", help="the brand's name, when the address does not say it (the config's)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    payload, text = ACTIONS[a.action](run, a)
    return c.finish(a, {"tool": "site", "action": a.action, **payload}, text)


if __name__ == "__main__":
    raise SystemExit(main())
