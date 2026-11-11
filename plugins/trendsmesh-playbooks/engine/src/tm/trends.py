"""TrendsMesh answers in a run: read back, saved, pooled; noise words; the fields a run needs.

    tm trends check-fields --run RUN [--json]
    tm trends collect on|off --run RUN, spool, ingest       (the collector: tm.trend_spool)
    tm trends shortlist --run RUN --terms ...                (the PB2 shortlist: tm.shortlist)

A saved answer is `{"_tool", "_input", "_at", "answer"}` under `02_research/` (names in
`save_answer`, never overwritten). The handoff's legacy files are read as they are: video files
`{"trend_id", "fetched", "total", "videos"}`, search files `{"_query", "_limit", "items"}` or a
bare list. Shared by PB02, PB03 and PB04: keep the interfaces exact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tm import cli, i18n, manifest
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

RESEARCH = "02_research"
VIDEO_FIELDS = ("creator", "published", "views", "thumbnail_url", "url")
_SOURCES = {
    "search_trends": "TrendsMesh MCP search_trends",
    "list_trends": "TrendsMesh MCP list_trends",
    "get_trend": "TrendsMesh MCP get_trend",
    "get_trend_videos": "TrendsMesh MCP get_trend_videos",
    "get_usage": "TrendsMesh MCP get_usage",
    "ads_library_search": "Meta Ads MCP ads_library_search",
}
TREND_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")   # a TrendsMesh trend id
_TREND_ID = TREND_ID
NAME_PART_MAX = 40

# Verbatim from the handoff's tools/pb2/trend_shortlist.py: obvious news/sport/event/holiday/politics.
DEFAULT_NOISE = {
    "holiday/seasonal": ["halloween", "christmas", "thanksgiving", "easter", "valentine",
                         "pumpkin", "dia de muertos", "día de muertos", "noche de brujas",
                         "new year", "black friday", "costume", "daylight saving"],
    "sport": ["football", "soccer", "nfl", "nba", "mlb", "nhl", "championship", "league",
              "match", "goal", "touchdown", "playoff", "vs", "fc", "streamers reacting"],
    "politics/elections": ["election", "midterm", "senator", "sen", "president", "trump",
                           "congress", "parliament", "duma", "minister", "white house",
                           "pentagon", "mobilization", "deportation", "ice enforcement"],
    "news/disaster/crime": ["killed", "dies", "died", "shooting", "sentenced", "probe", "raid",
                            "scandal", "controversy", "controversies", "hospitalized", "bomb",
                            "threat", "typhoon", "hurricane", "wildfire", "earthquake",
                            "war", "warfare", "tension", "breaking news", "fraud", "backlash"],
}

# From the handoff's tools/pb4/category_map.py. PB4 differs from PB2 here (dry run 2026-11-04): a
# seasonal trend inside the category (Halloween makeup in "beauty") is NOT noise, it is lifecycle
# information, so holidays are tagged "seasonal" and left to the growth buckets. Generic tokens of
# the PB2 sport list ("vs", "match", "goal", "league") matched beauty texts ("curly vs straight"),
# so they are not used here.
GENERIC_TOKENS = {"vs", "match", "goal", "league", "fc", "sen"}
NOISE_GROUPS = {g: [w for w in ws if w not in GENERIC_TOKENS]
                for g, ws in DEFAULT_NOISE.items() if g != "holiday/seasonal"}
SEASONAL = DEFAULT_NOISE["holiday/seasonal"]


def slug(text: str) -> str:
    """The original's category_map.slug: lowercase, every run of non-alphanumerics turned into `_`."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --- reading ----------------------------------------------------------------------------------

def read(path: Path) -> Any:
    """A saved file's JSON, as it is (envelope and all); ValueError naming the file when it is not JSON."""
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path.name} is not valid JSON ({exc}).") from exc


def unwrap(data: Any) -> Any:
    """A saved envelope's `answer` (`{"_tool", "_input", "_at", "answer"}`); anything else as it is."""
    return data["answer"] if isinstance(data, dict) and "_tool" in data and "answer" in data else data


def answer_of(path: Path) -> Any:
    """The answer a file holds: a saved envelope's `answer`, a legacy file as it is."""
    return unwrap(read(path))


def items(answer: Any) -> list:
    """Cards from a list, a single card (`id` and `kind`), or the first list under
    items | trends | results | data | videos (the original's order)."""
    if isinstance(answer, list):
        return answer
    if isinstance(answer, dict):
        if "id" in answer and "kind" in answer:
            return [answer]
        for key in ("items", "trends", "results", "data", "videos"):
            if isinstance(answer.get(key), list):
                return answer[key]
    return []


def videos(answer: Any) -> tuple[list, bool]:
    """A video page's videos and whether more pages follow: MCP `{data, page, has_more}`, REST
    `{videos, page, pages}`, the legacy `{trend_id, fetched, total, videos}` or a bare list."""
    if isinstance(answer, list):
        return answer, False
    if not isinstance(answer, dict):
        return [], False
    if isinstance(answer.get("data"), list):
        return answer["data"], answer.get("has_more") is True
    if isinstance(answer.get("videos"), list):
        page, pages = answer.get("page"), answer.get("pages")
        return answer["videos"], isinstance(page, int) and isinstance(pages, int) and page < pages
    return [], False


def match_score(card: dict) -> float:
    """`match.score`, a bare number, else 0."""
    m = card.get("match") if isinstance(card, dict) else None
    if isinstance(m, dict):
        m = m.get("score")
    return float(m) if isinstance(m, (int, float)) and not isinstance(m, bool) else 0.0


def creator_of(video: dict) -> str | None:
    """`creator`, else `creator_id`, else the @handle in `url`, else None (never the asset id).
    Only non-blank strings count; they are stripped."""
    for key in ("creator", "creator_id"):
        value = video.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    url = video.get("url")
    m = re.search(r"/@([^/?]+)", url) if isinstance(url, str) else None
    return m.group(1) if m else None


def video_files(run: RunFolder, trend_id: str) -> list[Path]:
    """The saved video pages of a trend, `02_research/videos/<id>.json` and `<id>_pNN[_vNN].json`,
    in reading order: legacy first, then by page and version. Ids match whatever their case."""
    folder = run.path / RESEARCH / "videos"
    pattern = re.compile(rf"^{re.escape(trend_id)}(?:_p(\d+)(?:_v(\d+))?)?\.json$", re.IGNORECASE)
    files = []
    if folder.is_dir():
        for f in folder.iterdir():
            m = pattern.match(f.name)
            if m and f.is_file():
                files.append(((int(m.group(1) or 0), int(m.group(2) or 1), f.name), f))
    return [f for _, f in sorted(files)]


def load_videos(run: RunFolder, trend_id: str) -> list[dict]:
    """Every saved video page of the trend (`video_files`), merged and de-duplicated by `asset_id`:
    the later file wins. Videos without an `asset_id` are all kept."""
    out: list[dict] = []
    where: dict[str, int] = {}
    for f in video_files(run, trend_id):
        for v in videos(answer_of(f))[0]:
            if not isinstance(v, dict):
                continue
            key = v.get("asset_id")
            if key is None:
                out.append(v)
            elif key in where:
                out[where[key]] = v
            else:
                where[key] = len(out)
                out.append(v)
    return out


# --- saving -----------------------------------------------------------------------------------

def _page(tool_input: dict) -> int:
    page = tool_input.get("page")
    if page is None:
        return 1
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError(f"The page {page!r} is not a page number: pages are whole numbers from 1.")
    return page


def _part(value: Any, fallback: str) -> str:
    """A file-name part: the slug, at most NAME_PART_MAX characters. A slug that was cut, or a text
    with nothing ASCII left (a Cyrillic query), ends in 8 hex characters of the text's sha1, so
    different texts never share a name. An empty value gives `fallback`."""
    text = str(value or "")
    if not text:
        return fallback
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    part = slug(i18n.transliterate(text))    # "łódź" -> lodz, never "d" (issue #3)
    if not part:
        return digest
    if len(part) > NAME_PART_MAX:
        return part[:NAME_PART_MAX - len(digest) - 1].rstrip("_") + "_" + digest
    return part


def oldest_updated_at(cards: list) -> str | None:
    """The oldest readable `updated_at` of these cards, as written, or None when none carries one
    (a list sorted `updated` pages back until it reaches the previous run's date)."""
    found = []
    for c in cards:
        when = c.get("updated_at") if isinstance(c, dict) else None
        if not isinstance(when, str):
            continue
        try:
            at = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            continue
        found.append((at if at.tzinfo else at.replace(tzinfo=timezone.utc), when))
    return min(found)[1] if found else None


def ad_terms(tool_input: dict) -> str | None:
    """The query an Ad Library search ran (`ads_library_search`'s `search_terms`, else `q`), as saved
    in its `_input`. A check finds its saved answer by this, never by the file name."""
    terms = tool_input.get("search_terms") or tool_input.get("q")
    return str(terms) if terms else None


def _answer_name(tool: str, tool_input: dict, at: str) -> str:
    """The file an answer is saved to, relative to 02_research (before `unique_path`). A tool this
    engine doesn't know (one TrendsMesh adds later) goes to `other/<tool>_<stamp>.json`."""
    if tool == "search_trends":
        name = f"search_{_part(tool_input.get('about'), 'query')}"
        if tool_input.get("trend_type"):
            name += f"_{_part(tool_input['trend_type'], 'all')}"
        if _page(tool_input) > 1:
            name += f"_p{_page(tool_input):02d}"
        return f"search/{name}.json"
    if tool == "list_trends":
        return (f"lists/list_{_part(tool_input.get('sort'), 'default')}_"
                f"{_part(tool_input.get('trend_type'), 'all')}_p{_page(tool_input):02d}.json")
    if tool in ("get_trend", "get_trend_videos"):
        tid = str(tool_input.get("trend_id") or "")
        if not _TREND_ID.fullmatch(tid):
            raise ValueError(f"{tool}'s trend_id {tid!r} is not a TrendsMesh trend id.")
        return f"trend_{tid}.json" if tool == "get_trend" else f"videos/{tid}_p{_page(tool_input):02d}.json"
    if tool == "get_usage":
        stamp = datetime.fromisoformat(at.replace("Z", "+00:00"))
        return f"usage/usage_{stamp:%Y%m%dT%H%M%S}.json"
    if tool == "ads_library_search":
        return f"ad_library/ads_{_part(ad_terms(tool_input), 'query')}.json"
    stamp = datetime.fromisoformat(at.replace("Z", "+00:00"))      # a TrendsMesh tool added later
    return f"other/{_part(tool, 'tool')}_{stamp:%Y%m%dT%H%M%S}.json"


def save_answer(run: RunFolder, tool: str, tool_input: dict, answer: Any, *, at: str | None = None) -> Path:
    """Save one MCP answer under 02_research (never over an earlier one) and add a manifest row."""
    if not isinstance(tool_input, dict):
        raise ValueError(f"{tool}'s input must be a JSON object.")
    at = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = run.unique_path(Path(RESEARCH) / _answer_name(tool, tool_input, at))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"_tool": tool, "_input": tool_input, "_at": at, "answer": answer}
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")    # whole or not at all
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    source = _SOURCES.get(tool, f"TrendsMesh MCP {tool}")
    manifest.record(run, path.relative_to(run.path).as_posix(), RESEARCH, source, params=tool_input)
    return path


# --- pooling ----------------------------------------------------------------------------------

def search_cards(answer: Any) -> list:
    """A search answer's cards (objects only); the legacy `{"_query", "items": {"items": [...]}}` too."""
    cards = items(answer)
    if not cards and isinstance(answer, dict) and isinstance(answer.get("items"), dict):
        cards = items(answer["items"])
    return [c for c in cards if isinstance(c, dict)]


def holds_no_cards(answer: Any) -> bool:
    """A saved answer that is not JSON (`{"raw": ...}`) or an error (`{"error": ...}`): it holds no
    trend data, so it is no query and no card."""
    return isinstance(answer, dict) and ("raw" in answer or "error" in answer)


def search_files(run: RunFolder) -> list[Path]:
    """Every saved search file, `02_research/search/search_*.json`, sorted by name (pages and `_vNN`
    repeats included), but those whose answer holds no cards (`holds_no_cards`). A file that cannot
    be read stays, for the caller to report."""
    folder = run.path / RESEARCH / "search"
    out = []
    for f in sorted(folder.glob("search_*.json")) if folder.is_dir() else []:
        try:
            if f.is_file() and not holds_no_cards(answer_of(f)):
                out.append(f)
        except (OSError, ValueError):
            out.append(f)
    return out


def query_of(data: Any, path: Path) -> str:
    """The query a search file answers, from the file's read JSON: `_input.about`, else `_query`, else
    (a bare legacy list) the file name, as category_map did. Never key a search on its file name
    otherwise: names are capped and hashed."""
    if isinstance(data, dict):
        tool_input = data.get("_input") if isinstance(data.get("_input"), dict) else {}
        query = tool_input.get("about") or data.get("_query")
        if query:
            return str(query)
    return path.stem.removeprefix("search_").replace("_", " ")


def pool(run: RunFolder, *, kinds: tuple[str, ...] | None = None) -> dict[str, dict]:
    """`id -> {"card", "found_by": {query: best score}}` over every saved search file (the first
    card seen is kept). `kinds` keeps only cards of those kinds."""
    out: dict[str, dict] = {}
    for f in search_files(run):
        data = read(f)
        query = query_of(data, f)
        for card in search_cards(unwrap(data)):
            if not card.get("id") or (kinds is not None and card.get("kind") not in kinds):
                continue
            entry = out.setdefault(card["id"], {"card": card, "found_by": {}})
            entry["found_by"][query] = max(entry["found_by"].get(query, 0.0), match_score(card))
    return out


# --- noise ------------------------------------------------------------------------------------

def _text_of(card: dict) -> str:
    return " ".join([card.get("name") or "", card.get("what_it_is") or ""]).lower()


def seasonal_tag(card: dict) -> str | None:
    """The first holiday word in the card's name or description, else None (not noise in PB4)."""
    text = _text_of(card)
    return next((w for w in SEASONAL if re.search(rf"\b{re.escape(w)}\b", text)), None)


def noise_reasons(card: dict, exclude: list[str]) -> list[str]:
    """Why a card is noise (one word per group, excluded terms, a possessive proper name); [] when
    it is not."""
    text = _text_of(card)
    reasons = []
    for group, words in NOISE_GROUPS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text):
                reasons.append(f"{group}: {w}")
                break
    for w in exclude:
        if re.search(rf"\b{re.escape(w.lower())}\b", text):
            reasons.append(f"excluded term: {w}")
    if re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+(?:'s|’s)\b", card.get("name") or ""):
        reasons.append("possessive proper name (celebrity / news item)")
    return reasons


# --- the fields a run needs -------------------------------------------------------------------

def _field_report(run: RunFolder) -> tuple[list[str], list[str]]:
    """The missing fields and the files read: the first saved video page with videos, the first
    search file with cards. A field is missing when no video (card) of that file carries it."""
    missing: list[str] = []
    checked: list[str] = []
    folder = run.path / RESEARCH / "videos"
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        vids = [v for v in videos(answer_of(f))[0] if isinstance(v, dict)]
        if vids:
            checked.append(f.relative_to(run.path).as_posix())
            for field in VIDEO_FIELDS:
                if field == "creator":
                    has = any(creator_of(v) for v in vids)
                else:
                    has = any(v.get(field) not in (None, "") for v in vids)
                if not has:
                    missing.append(field)
            break
    for f in search_files(run):
        cards = search_cards(answer_of(f))
        if cards:
            checked.append(f.relative_to(run.path).as_posix())
            if not any(c.get("match") is not None for c in cards):
                missing.append("match")
            break
    if not checked:
        raise Stop("This run has no saved TrendsMesh video page or search answer yet, so there is nothing to "
                   "check. Save one (a search and one trend's videos, with tm trends collect on), then check "
                   f"again; {AGAIN}.")
    return missing, checked


def check_fields(run: RunFolder) -> list[str]:
    """Fields the run needs (growth counts them, the page shows them) that the saved answers lack:
    `creator` (or a handle in `url`),
    `published`, `views`, `thumbnail_url`, `url` on videos, `match` on search cards."""
    return _field_report(run)[0]


# --- command line -----------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    cf = sub.add_parser("check-fields", help="the fields the run needs, in the saved answers")
    cf.add_argument("--run", required=True, help="the run folder")
    cf.add_argument("--json", action="store_true")
    from tm import shortlist, trend_spool   # they import this module
    trend_spool.add_parsers(sub)
    shortlist.add_parser(sub)


def _check_fields(args: argparse.Namespace, run: RunFolder) -> int:
    missing, checked = _field_report(run)
    payload = {"status": "stop" if missing else "done", "missing": missing, "checked": checked}
    files = ", ".join(checked)
    if not missing:
        cli.emit(args, payload, f"The saved TrendsMesh answers carry every field the run needs ({files}).")
        return 0
    cli.emit(args, payload,
             f"The saved TrendsMesh answers lack {', '.join(missing)} ({files}). The run counts "
             "creators, dates and views from them and shows links and posters on the page, so it stops "
             "here. Check that the TrendsMesh connector is current, or tell the TrendsMesh team which "
             "fields are missing; once fresh answers carry them, check again. The run continues from "
             "the same place.")
    return 2


def _run(args: argparse.Namespace) -> int:
    from tm import shortlist, trend_spool
    if args.action in trend_spool.ACTIONS:
        return trend_spool.ACTIONS[args.action](args)
    if args.action == "shortlist":
        return shortlist.run_shortlist(args)
    try:
        run = RunFolder.open(Path(args.run))
        return {"check-fields": _check_fields}[args.action](args, run)
    except Stop as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("trends", _setup, _run)
