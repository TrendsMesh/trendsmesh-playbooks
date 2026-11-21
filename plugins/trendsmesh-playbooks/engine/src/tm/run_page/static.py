"""The page's fixed parts (issue #129 part 3): what is the same in every run, written beside the page instead of
inside it, so the agent reads only this run's `index.html` before publishing.

    link(name), script(name)    the tag that loads a part, by its served path (`assets/static/<stem>-<version>.<ext>`)
    put(folder)                 write the parts `index.html` names into the page's folder (and nothing else there)
    check(served, path)         the file's sha256 when it is the plugin's own copy of a part, else None

The parts (`PARTS`): the theme's stylesheet (assets/page/theme.css), the run page's script, the trend report's
stylesheet (research_report.css) and script, Organic AI video's stylesheets and scripts, and the style catalogue (our
49 styles and the script that draws their gallery, `styles.catalogue_js`). Each one's bytes are the plugin's: the
file it is kept in, or the text the plugin's code holds; the plugin version in the name keeps an older build's copy
from being taken for this one's. A script is loaded with `<script src>` and the catalogue sets a global
(`window.TM_STYLES`): a page opened as a local file (`file://`) may load a sibling script, but Chrome refuses it a
`fetch()` of one.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from functools import lru_cache
from pathlib import Path

from tm import __version__

DIR = "assets/static"
# name -> (module, attribute): the attribute is the text, or a function giving it (loaded when first needed, so this
# module imports none of the page code)
PARTS = {
    "theme.css": ("tm.run_page.template", "theme_css"),
    "page.js": ("tm.run_page.template", "SCRIPT"),
    "trend-report.css": ("tm.research_report", "report_css"),
    "trend-report.js": ("tm.research_report", "SCRIPT"),
    "styles.css": ("tm.run_page.styles", "CSS"),
    "styles.js": ("tm.run_page.styles", "catalogue_js"),
    "organic-plan.css": ("tm.run_page.organic_plan", "CSS"),
    "organic-plan.js": ("tm.run_page.organic_plan", "SCRIPT"),
    "organic-video.css": ("tm.run_page.organic_video", "CSS"),
    "organic-video.js": ("tm.run_page.organic_video", "SCRIPT"),
}


def served(name: str) -> str:
    """The part's path inside the page: `assets/static/theme-0.14.0.css`."""
    stem, ext = name.rsplit(".", 1)
    return f"{DIR}/{stem}-{__version__}.{ext}"


@lru_cache(maxsize=None)
def content(name: str) -> bytes:
    module, attr = PARTS[name]
    value = getattr(importlib.import_module(module), attr)
    return (value() if callable(value) else value).encode("utf-8")


@lru_cache(maxsize=None)
def _by_served() -> dict[str, str]:
    return {served(n): n for n in PARTS}


def link(name: str) -> str:
    return f'<link rel="stylesheet" href="{served(name)}">'


def script(name: str) -> str:
    return f'<script src="{served(name)}"></script>'


def put(folder: Path) -> list[str]:
    """Write every part the folder's `index.html` names into `assets/static/`, and remove any other file there (an
    earlier build's, carried over with its assets). The served paths written."""
    folder = Path(folder)
    text = (folder / "index.html").read_text(encoding="utf-8")
    wanted = [p for p in _by_served() if re.search(rf'(?:href|src)="{re.escape(p)}"', text)]
    target = folder / DIR
    if target.is_dir():
        for f in target.iterdir():
            if f.is_file() and f"{DIR}/{f.name}" not in wanted:
                f.unlink()
    for p in wanted:
        out = folder / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content(_by_served()[p]))
    return wanted


def check(served_path: str, path: Path) -> str | None:
    """The sha256 of `path` when it is this plugin version's copy of the part served at `served_path`, else None."""
    name = _by_served().get(served_path)
    if name is None:
        return None
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest() if data == content(name) else None
