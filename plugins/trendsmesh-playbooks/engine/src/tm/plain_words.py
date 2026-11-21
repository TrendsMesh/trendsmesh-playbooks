"""The run's codes and files, which a page for people never shows in its visible text (issue #132).

    codes(run)            the run's own codes: the first characters of each trend id it saved a card for, and the
                          theme ids of its latest voice themes
    found(text, codes)    the first code or file in `text`, as (what it is, the value), else None

What is looked for:
- a trend id: 32 hex characters, or the first `PREFIX` characters of a trend id the run saved a card for
  (`02_research/trend_<id>[_vNN].json`; an id shorter than that is not looked for: it would match ordinary words);
- a run file: a stage folder followed by `/` (`00_raw/` to `05_results/`), or a file name ending in `.json`, `.jsonl`,
  `.md` or `.csv`;
- a theme id of the run's latest `02_research/voice/voice_themes_vNN.json` (`T01`, `T02` ...), as a whole word.

The checks that use it (`tm brief check`, `tm page build`'s ask check) say the field it is in; the page shows such
things only in its folded "Technical details" (a brief's `source_ref`, a run page block's source).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from tm.runfolder import RunFolder

PREFIX = 8                              # the first characters of a trend id that name it (as R3 used to ask)
RESEARCH = "02_research"
VOICE = "02_research/voice"
TREND_ID = "a trend id"
RUN_FILE = "a run file"
THEME_ID = "a theme id"
_HEX = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{32}(?![0-9A-Za-z])")
_STAGE_PATH = re.compile(r"(?<![\w/.-])[\w./-]*\b0[0-5]_(?:raw|base|research|wip|final|results)/[\w./<>*-]*")
_FILE = re.compile(r"(?<![\w/.-])[\w.-]*\w\.(?:jsonl|json|md|csv)(?![\w-])", re.I)
_CARD = re.compile(r"^trend_(.+?)(?:_v\d+)?\.json$")


@dataclass(frozen=True)
class Codes:
    trends: tuple[str, ...] = ()        # the first PREFIX characters of each saved card's trend id
    themes: tuple[str, ...] = ()        # the latest voice themes' ids


def _theme_ids(run: RunFolder) -> tuple[str, ...]:
    path = run.latest(VOICE, "voice_themes", "json")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path else None
    except (OSError, ValueError):
        return ()
    themes = data.get("themes") if isinstance(data, dict) else None
    return tuple(sorted({t["id"] for t in themes or [] if isinstance(t, dict) and isinstance(t.get("id"), str)
                         and t["id"].strip()}))


def codes(run: RunFolder | None) -> Codes:
    """The run's own codes (none without a run)."""
    if run is None:
        return Codes()
    folder = run.path / RESEARCH
    ids = {m.group(1) for f in (folder.glob("trend_*.json") if folder.is_dir() else ()) if (m := _CARD.match(f.name))}
    return Codes(tuple(sorted({i[:PREFIX] for i in ids if len(i) >= PREFIX})), _theme_ids(run))


def _clean(value: str) -> str:
    return value.rstrip(".,;:)")


def found(text: object, have: Codes) -> tuple[str, str] | None:
    """The first trend id, run file or theme id in `text`, as (what it is, the value); None for plain text."""
    if not isinstance(text, str) or not text:
        return None
    if m := _HEX.search(text):
        return TREND_ID, m.group(0)
    low = text.casefold()
    for prefix in have.trends:
        at = low.find(prefix.casefold())
        while at >= 0:
            if at == 0 or not low[at - 1].isalnum():
                return TREND_ID, text[at:at + len(prefix)]
            at = low.find(prefix.casefold(), at + 1)
    if m := _STAGE_PATH.search(text):
        return RUN_FILE, _clean(m.group(0))
    if m := _FILE.search(text):
        return RUN_FILE, _clean(m.group(0))
    for theme in have.themes:
        if m := re.search(rf"(?<!\w){re.escape(theme)}(?!\w)", text):
            return THEME_ID, m.group(0)
    return None
