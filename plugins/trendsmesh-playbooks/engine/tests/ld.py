"""The handoff's LD dry run (handoff/creative-brief_v02/examples/ld-en-dry-run) as a creative brief run.

The LD rebuild tests of PR B and PR C start from this run, and this module is the one loader of
the LD files (PB04's `test_shortlist.py` and `test_voice_themes.py` use it too). Its trend files
are saved through `trends.save_answer` as the collector saves them, so the names are the
collector's:
- `search_*.json` -> `search_trends` with `about` = the original's query label (limit 20, the dry run's);
- `rising_format.json` -> `list_trends`, sort rising, the type from the name (`format`: the golden
  shortlist labels it `rising:format`; a real MCP call says `format_trend`);
- `trend_<id>.json` -> `get_trend`;
- `videos_<id>.json` -> `get_trend_videos`, in two pages (the MCP envelope).

`01_base/meta_adsets_targeting_maximum.json` is copied into the run's `01_base`, and the voice items
come from `02_research/voice/` through `tm voice`: the Reddit archive files by `items_from_archive`
(each file's query read from its `_query_url`), the two Goodreads texts by `import_file` (tier B).
"""

from __future__ import annotations

import functools
import json
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import private
from tm import shortlist, trends, voice
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

REPO = Path(__file__).resolve().parents[4]
LD = REPO / "handoff" / "creative-brief_v02" / "examples" / "ld-en-dry-run"
TRENDS = LD / "02_research" / "trends"
VOICE = LD / "02_research" / "voice"
CREATED = date(2026, 11, 4)
NAME = "ld"
TARGETING = "meta_adsets_targeting_maximum.json"
GOODREADS = {"goodreads_laberge": "goodreads_laberge_exploring_reviews.txt",
             "goodreads_love": "goodreads_love_are_you_dreaming_reviews.txt"}
SEARCH_LIMIT = 20
REDDIT_FILES = 14
BRIEF = LD / "04_final" / "brief_pack_v01.json"
PLUGIN_BLOCKS = Path(__file__).parent / "fixtures" / "creative_brief" / "ld_plugin_blocks.json"


def brief() -> dict:
    """The reference brief, its texts unchanged, with the plugin blocks of `PLUGIN_BLOCKS` merged in."""
    data = private.alias(json.loads(BRIEF.read_text(encoding="utf-8")))
    blocks = json.loads(PLUGIN_BLOCKS.read_text(encoding="utf-8"))
    data["meta"]["plugin"] = blocks["meta"]["plugin"]
    for concept in data["concepts"]:
        concept["plugin"] = blocks["concepts"][concept["id"]]["plugin"]
    return data


AS_OF = "2026-11-04"   # the day the dry run pulled its clips (each Rising hook row: "TrendsMesh trend …, pulled 4 November")


def dated(data: dict, day: str = AS_OF) -> dict:
    """The brief with each evidence clip's `plugin.as_of`, as `tm brief evidence` adds it (CB8).
    The reference brief has none: the reference tool kept no as-of date per clip, and the page never reads it."""
    for concept in data["concepts"]:
        for clip in (concept.get("copy_from_hook") or {}).get("evidence", []):
            clip["plugin"] = {**(clip.get("plugin") or {}), "as_of": day}
    return data


def save_trends(run: RunFolder, *, search_limit: int = SEARCH_LIMIT) -> None:
    """The LD trend files, saved as the collector saves them (`search_limit` goes into each search's
    `_input` only)."""
    for f in sorted(TRENDS.glob("*.json")):
        data = private.alias(json.loads(f.read_text(encoding="utf-8")))
        if f.stem.startswith("search_"):
            trends.save_answer(run, "search_trends", {"about": shortlist.query_label(f), "limit": search_limit}, data)
        elif f.stem.startswith("rising_"):
            trends.save_answer(run, "list_trends", {"sort": "rising", "trend_type": f.stem.split("_", 1)[1]}, data)
        elif f.stem.startswith("trend_"):
            trends.save_answer(run, "get_trend", {"trend_id": f.stem.split("_", 1)[1]}, data)
        elif f.stem.startswith("videos_"):
            tid = f.stem.split("_", 1)[1]
            half = len(data["videos"]) // 2
            trends.save_answer(run, "get_trend_videos", {"trend_id": tid},
                               {"data": data["videos"][:half], "page": 1, "has_more": True})
            trends.save_answer(run, "get_trend_videos", {"trend_id": tid, "page": 2},
                               {"data": data["videos"][half:], "page": 2, "has_more": False})


def _archive_query(raw: dict) -> tuple[str, str]:
    """The kind and the keyword of a saved archive answer, from its `_query_url` ("" for none)."""
    url = urlparse(raw["_query_url"])
    kind = "posts" if url.path.endswith("/posts/search") else "comments"
    qs = parse_qs(url.query)
    return kind, next((qs[k][0] for k in ("title", "selftext", "query", "body") if k in qs), "")


@functools.lru_cache(maxsize=1)
def voice_items() -> tuple[dict, ...]:
    """The LD voice items, in the order `tm voice` logs them."""
    items: list[dict] = []
    files = sorted(VOICE.glob("reddit_*.json"))
    assert len(files) == REDDIT_FILES, f"{len(files)} Reddit archive files in {VOICE}, not {REDDIT_FILES}"
    for f in files:
        raw = private.alias(json.loads(f.read_text(encoding="utf-8")))
        items += voice.items_from_archive(raw, *_archive_query(raw))
    for source, name in GOODREADS.items():
        items += voice.import_file(VOICE / name, "text", source, "B")
    return tuple(items)


def build(workspace: Path) -> RunFolder:
    """A creative brief run `ld` (created 2026-11-04) holding the dry run's trends, voice and targeting read."""
    run = RunFolder.create(Path(workspace), NAME, CREATED, playbook=CREATIVE_BRIEF)
    save_trends(run)
    shutil.copyfile(LD / "01_base" / TARGETING, run.path / "01_base" / TARGETING)
    voice.append_items(run, [dict(it) for it in voice_items()])
    return run
