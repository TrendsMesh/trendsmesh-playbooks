"""Category voice (CB5), shared by the playbooks: the Reddit archive, and reviews the user has.

    tm voice reddit-posts --run R --subreddit S --query Q [--field title|selftext|query] [--limit N]
                          [--after D|all] [--before D] [--skip-removed] [--json]
    tm voice reddit-comments --run R --subreddit S --query Q [--limit N] [--after D|all] [--before D] [--json]
    tm voice import --run R --file F --format csv|jsonl|text --source LABEL --tier A|B [--text-column C] [--json]
    tm voice check --run R --file 02_research/voice/voice_themes_vNN.json [--json]   (tm.voice_themes)

The Reddit part is the handoff's `tools/pb2/voice_mine.py`, ported: the Arctic Shift archive
(arctic-shift.photon-reddit.com, a volunteer-run read-only mirror of public posts and comments, not
Reddit's own API). Its limits, from the original's notes:

* The archive gives the NEWEST matches for the keyword (by created_utc), at most 100 a call, never
  "top of the year" by score. Theme counts are frequencies within keyword samples, so the query is
  kept with every item.
* Comments carry no thread title in the compact field set. AutoModerator items are dropped.
* Removed or deleted bodies are counted. Comments with a removed body are skipped; posts keep their
  title (the author's own words) with an empty text, unless --skip-removed.
* A heavy query is answered HTTP 422 "Timeout. Maybe slow down a bit", and a keyword call can give
  fewer items than exist. So the window is walked from the newest end: after each call it goes on
  just below the oldest item returned; on a timeout it does one warm-up retry, then halves the chunk.
  It stops at --limit items, when the window is covered, or after 25 calls, and keeps what it got
  with `_stats.partial` saying why. Default window: the last 730 days (--after all: from 2005).

The raw answer is saved as `02_research/voice/reddit_<sub>_<kind>_<query>_vNN.json` with a manifest
row, and its items are appended to `02_research/voice/items.jsonl` (a log: de-duplicated by id,
never rewritten). The archive not answering is a Stop with reason `source_unavailable`: customer
voice is then a missing input, and the skill asks for reviews or another source.

Goodreads is not ported (the plan's Decision 7): `tm voice import` takes review text, CSV or JSONL
the user has, or that the agent saved from a page the user named. Tier A is the user's own
customers, tier B the category; tier C (the brand's own words) is never customer evidence.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal

import requests

from tm import __version__, cli, library, manifest, trends
from tm.runfolder import ReadOnlyError, RunFolder
from tm.stops import AGAIN, Stop

USER_AGENT = f"trendsmesh-playbooks/{__version__} (category voice research; read-only; https://trendsmesh.com)"
# Verbatim from voice_mine.py.
TIMEOUT = 30
RETRIES = 3
BACKOFF = [2, 5, 10]
MAX_RATE_WAIT = 90
ARCTIC = "https://arctic-shift.photon-reddit.com/api/"
BOT_AUTHORS = {"automoderator"}
REMOVED = {"[removed]", "[deleted]", "[ Removed by Reddit ]", "[removed by reddit]"}
DEFAULT_WINDOW_DAYS = 730
WARMUP_WAIT = 8
MIN_CHUNK_DAYS = 2
MAX_CALLS = 25
ARCHIVE_START = dt.date(2005, 6, 1)  # Reddit launch; lower bound for --after all
# Fields requested by default (smaller, faster responses; all_fields returns full records).
# author is requested only to drop AutoModerator; it is never copied into the items.
POST_FIELDS = "id,title,selftext,score,num_comments,created_utc,subreddit,author,link_flair_text"
COMMENT_FIELDS = "id,body,score,link_id,parent_id,created_utc,subreddit,author"

STAGE = "02_research/voice"
ITEMS = f"{STAGE}/items.jsonl"
SOURCE = "Arctic Shift Reddit archive (arctic-shift.photon-reddit.com), not Reddit's own API"
TIER_C = "brand voice is a hypothesis, never customer evidence (CB5)"
TIERS = {"A": "own customers", "B": "category"}
KINDS = ("posts", "comments")
FIELDS = ("title", "selftext", "query")
FORMATS = ("csv", "jsonl", "text")

_sleep = time.sleep   # every wait goes through here (the tests record them)


class ArchiveTimeout(Exception):
    """Arctic Shift answered 422 'Timeout': the query was too heavy for the server."""


class SourceUnavailable(Stop):
    """The archive did not answer usably: a missing input, the skill asks for another source."""

    reason = "source_unavailable"

    def __init__(self, detail: str):
        super().__init__(
            f"The Reddit archive (Arctic Shift) did not answer: {detail}. Customer voice is a missing input: "
            "ask the user for reviews or other customer texts (tm voice import) or another source, or try the "
            f"archive later. Nothing was saved; {AGAIN}.")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# --- HTTP -----------------------------------------------------------------------------------------

def http_get(url: str, params: dict | None = None) -> requests.Response:
    """GET with retries on timeouts, connection errors, 429 and 5xx (429 honours Retry-After /
    x-ratelimit-reset). Other 4xx fail at once. An HTTP 422 'Timeout' raises ArchiveTimeout so the
    caller can retry or narrow the date window; every other failure is SourceUnavailable."""
    session_headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"}
    last = ""
    for attempt in range(RETRIES + 1):
        wait = BACKOFF[min(attempt, len(BACKOFF) - 1)]
        try:
            r = requests.get(url, params=params, headers=session_headers, timeout=TIMEOUT)
        except requests.Timeout:
            last = f"timeout after {TIMEOUT}s"
            _log(f"[warn] {last} ({url})")
        except requests.ConnectionError as e:
            last = f"connection error: {e.__class__.__name__}"
            _log(f"[warn] {last} ({url})")
        except requests.RequestException as e:
            raise SourceUnavailable(f"{e.__class__.__name__} ({url})") from e
        else:
            if r.status_code == 422:
                try:
                    body = r.json()
                except ValueError:
                    body = None
                err = (body.get("error") or "") if isinstance(body, dict) else ""
                if "timeout" in str(err).lower():
                    raise ArchiveTimeout(err)
                raise SourceUnavailable(f"HTTP 422 from {r.url}: {err or r.text[:200]}")
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                ra = r.headers.get("Retry-After") or r.headers.get("x-ratelimit-reset")
                if ra and ra.isdigit():
                    wait = min(int(ra) + 1, MAX_RATE_WAIT)
                _log(f"[warn] {last} from {r.url}")
            elif 400 <= r.status_code < 500:
                detail = r.text[:200].replace("\n", " ")
                raise SourceUnavailable(f"HTTP {r.status_code} (client error) from {r.url}: {detail}")
            else:
                return r
        if attempt < RETRIES:
            _log(f"[info] retry {attempt + 1}/{RETRIES} in {wait}s")
            _sleep(wait)
    raise SourceUnavailable(f"giving up after {RETRIES} retries: {last} ({url})")


# --- Reddit ---------------------------------------------------------------------------------------

def _date(s: str, what: str) -> str:
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Bad {what} date {s!r}, expected YYYY-MM-DD.") from None
    return s


def _to_ts(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def _fmt_ts(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def _clean_md(s: str | None) -> str:
    return html.unescape(s or "").replace("\r\n", "\n").strip()


def _is_bot(d: dict) -> bool:
    return (d.get("author") or "").lower() in BOT_AUTHORS


def _items(records: list[dict], kind: str, query: str, subreddit: str,
           skip_removed: bool) -> tuple[list[dict], int, int, int]:
    """voice_mine.py's item rows (plus tier B) and the removed, skipped and bot counts."""
    items, removed, skipped, bots = [], 0, 0, 0
    for d in records:
        sub = d.get("subreddit") or subreddit
        if _is_bot(d):
            bots += 1
            continue
        if kind == "posts":
            body = _clean_md(d.get("selftext"))
            is_removed = body in REMOVED or (d.get("removed_by_category") is not None and not body)
            if body in REMOVED:
                body = ""
            if is_removed:
                removed += 1
                if skip_removed:
                    skipped += 1
                    continue
            items.append({
                "id": f"t3_{d['id']}",
                "source": "reddit_post",
                "community": f"r/{sub}",
                "url": "https://www.reddit.com" + (d.get("permalink") or f"/r/{sub}/comments/{d['id']}/"),
                "title": _clean_md(d.get("title")),
                "text": body,
                "score": d.get("score"),
                "created_utc": d.get("created_utc"),
                "query": query or "",
                "tier": "B",
            })
        else:
            body = _clean_md(d.get("body"))
            if body in REMOVED or not body:
                removed += 1
                skipped += 1
                continue
            link = (d.get("link_id") or "").removeprefix("t3_")
            permalink = d.get("permalink") or f"/r/{sub}/comments/{link}/_/{d['id']}/"
            items.append({
                "id": f"t1_{d['id']}",
                "source": "reddit_comment",
                "community": f"r/{sub}",
                "url": "https://www.reddit.com" + permalink,
                "title": _clean_md(d.get("link_title")),
                "text": body,
                "score": d.get("score"),
                "created_utc": d.get("created_utc"),
                "query": query,
                "tier": "B",
            })
    return items, removed, skipped, bots


def items_from_archive(payload: dict, kind: str, query: str, *, skip_removed: bool = False) -> list[dict]:
    """The items of a saved archive answer (`fetch_reddit`'s, or voice_mine.py's raw file):
    id, source, community, url, title, text, score, created_utc, query and tier "B"."""
    if kind not in KINDS:
        raise ValueError(f"The kind is posts or comments, not {kind!r}.")
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError("The archive answer has no data list.")
    if not all(isinstance(d, dict) and d.get("id") for d in records):
        raise ValueError("The archive answer has a record that is not an object with an id.")
    subreddit = (payload.get("_params") or {}).get("subreddit") or ""
    return _items(records, kind, query, subreddit, skip_removed)[0]


def fetch_reddit(kind: Literal["posts", "comments"], subreddit: str, query: str, *, field: str = "title",
                 limit: int = 100, after: str | None = None, before: str | None = None,
                 skip_removed: bool = False, all_fields: bool = False, get=http_get) -> dict:
    """voice_mine.py's reddit_fetch (newest first): the archive's answer with `_query_url`,
    `_source`, `_fetched_at`, `_params`, `_stats` (with `partial`), `_tool`, `data` (bots kept) and
    `_chunks`. A bad argument is a ValueError; the archive not answering is SourceUnavailable."""
    if kind not in KINDS:
        raise ValueError(f"The kind is posts or comments, not {kind!r}.")
    if kind == "posts" and field not in FIELDS:
        raise ValueError(f"--field is title, selftext or query, not {field!r}.")
    if kind == "comments" and not (query or "").strip():
        raise ValueError("A comment search needs --query (the archive matches comment bodies).")
    window_start = _date(after, "--after") if after not in (None, "all") else None
    if after is None:
        window_start = (dt.date.today() - dt.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
    window_end = _date(before, "--before") if before else None
    if not 1 <= limit <= 100:
        raise ValueError("--limit must be between 1 and 100 (archive maximum).")

    params: dict = {"subreddit": subreddit, "limit": limit, "sort": "desc"}
    if kind == "posts":
        if query:
            params[field] = query
        path = "posts/search"
    else:
        params["body"] = query
        path = "comments/search"
    if not all_fields:
        params["fields"] = POST_FIELDS if kind == "posts" else COMMENT_FIELDS
    # The window is walked in pieces from the newest end, with epoch-second bounds:
    #   * success with new items  -> continue just below the oldest item returned;
    #   * success with no new item -> that chunk is empty, step over it;
    #   * timeout (after one warm-up retry) -> halve the chunk.
    # It stops at `limit` items, when the window is covered, or after MAX_CALLS calls.
    lo = _to_ts(dt.date.fromisoformat(window_start) if window_start else ARCHIVE_START)
    hi = _to_ts(dt.date.fromisoformat(window_end) if window_end else dt.date.today() + dt.timedelta(days=1))
    if lo >= hi:
        raise ValueError("--after must be earlier than --before.")
    chunk = hi - lo
    min_chunk = MIN_CHUNK_DAYS * 86400
    collected: dict[str, dict] = {}   # usable records (bots excluded), counted toward the limit
    bot_recs: dict[str, dict] = {}    # AutoModerator records, kept in the raw file only
    chunks: list[dict] = []
    calls = timeouts = 0
    incomplete = None
    while lo < hi and len(collected) < limit:
        c_lo, c_hi = max(lo, hi - chunk), hi
        params["after"], params["before"] = c_lo, c_hi
        params["limit"] = limit - len(collected)
        r = None
        for warm in range(2):
            if calls >= MAX_CALLS:
                break
            calls += 1
            try:
                r = get(ARCTIC + path, params)
                break
            except ArchiveTimeout as e:
                timeouts += 1
                _log(f"[warn] archive query timed out (HTTP 422 '{e}'), window {_fmt_ts(c_lo)}..{_fmt_ts(c_hi)}")
                if warm == 0:
                    _log(f"[info] warm-up retry in {WARMUP_WAIT}s")
                    _sleep(WARMUP_WAIT)
        if r is None:
            if calls >= MAX_CALLS:
                incomplete = f"stopped after {MAX_CALLS} archive calls"
                break
            chunk //= 2
            if chunk < min_chunk:
                incomplete = f"archive kept timing out even on {MIN_CHUNK_DAYS}-day windows"
                break
            _log(f"[info] splitting the window: chunks of {chunk / 86400:.1f} days")
            _sleep(WARMUP_WAIT)
            continue
        try:
            answer = r.json()
        except ValueError:
            raise SourceUnavailable(f"the archive did not return JSON ({r.url})") from None
        if isinstance(answer, dict) and answer.get("error"):
            raise SourceUnavailable(f"archive error: {answer['error']} ({r.url})")
        part = answer.get("data") if isinstance(answer, dict) else None
        if not isinstance(part, list):
            raise SourceUnavailable(f"unexpected archive response shape ({r.url})")
        if not all(isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"] for d in part):
            raise SourceUnavailable(f"unexpected archive response shape, a record without an id ({r.url})")
        new = [d for d in part if d.get("id") not in collected and d.get("id") not in bot_recs]
        for d in new:
            if _is_bot(d):
                bot_recs[d["id"]] = d
            else:
                collected[d["id"]] = d
        chunks.append({"url": r.url, "after": _fmt_ts(c_lo), "before": _fmt_ts(c_hi),
                       "returned": len(part), "new": len(new)})
        # bounds are exclusive past the last item seen (an item posted in the very same second as
        # the boundary item could be missed; rare, accepted)
        stamps = [d["created_utc"] for d in new if isinstance(d.get("created_utc"), (int, float))]
        hi = int(min(stamps)) if stamps else c_lo
        chunk = max(chunk, min(chunk * 2, hi - lo))  # grow back after a success
        if lo < hi and len(collected) < limit:
            _sleep(1)  # polite gap between calls

    if not chunks:
        raise SourceUnavailable(f"no data: {incomplete}. Try later, a narrower --after/--before, a smaller "
                                "--limit, or a more specific --query")
    if incomplete:
        _log(f"[warn] partial result ({incomplete}); the oldest part of the window was not covered")

    def order(recs):
        return sorted(recs, key=lambda d: d.get("created_utc") or 0, reverse=True)

    data = order(collected.values())[:limit]
    raw_data = order(list(collected.values()) + list(bot_recs.values()))
    params["after"], params["before"] = window_start or "all", window_end or "now"
    params["limit"] = limit
    query_url = chunks[0]["url"] if len(chunks) == 1 else [c["url"] for c in chunks]

    items, removed, skipped, bots = _items(data, kind, query, subreddit, skip_removed)
    bots += len(bot_recs)
    stats = {"fetched": len(raw_data), "removed_bodies": removed, "skipped": skipped, "bot_skipped": bots,
             "items": len(items), "window": [window_start or "all", window_end or "now"],
             "archive_calls": calls, "archive_timeouts": timeouts, "chunks": len(chunks), "partial": incomplete}
    ts = [d.get("created_utc") for d in data if d.get("created_utc")]
    if ts:
        def day(t):
            return dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
        stats["date_range"] = [day(min(ts)), day(max(ts))]
    return {"_query_url": query_url, "_source": f"arctic_shift_{kind}", "_fetched_at": _now_iso(),
            "_params": params, "_stats": stats, "_tool": "tm voice", "data": raw_data, "_chunks": chunks}


# --- imports --------------------------------------------------------------------------------------

def _lines(numbers: list[int]) -> str:
    return ("line " if len(numbers) == 1 else "lines ") + ", ".join(map(str, numbers))


def _texts(path: Path, fmt: str, text_column: str) -> list[tuple[int, str]]:
    """(n, text) of each record of the file, n counting from 1 in file order; empty texts left out.
    A missing file, one that is not UTF-8, and one with no text at all are Stops naming it."""
    if not path.is_file():
        raise Stop(f"{path} is not there: check the path of the file the user gave (or saved), then import it "
                   f"again; nothing was imported; {AGAIN}.")
    try:
        texts = _read_texts(path, fmt, text_column)
    except UnicodeDecodeError:
        raise Stop(f"{path.name} is not UTF-8 text: save it as UTF-8 (in Excel: CSV UTF-8), then import it again; "
                   f"nothing was imported; {AGAIN}.") from None
    if not texts:
        what = "it is empty" if fmt == "text" else f"it is empty, or so is every {text_column!r}"
        raise Stop(f"{path.name} has no texts to import ({what}). Check the file the user gave, or ask for another; "
                   f"nothing was imported; {AGAIN}.")
    return texts


def _delimiter(text: str) -> str:
    """The separator of a CSV: the one of `,` `;` and tab that is most often in its header line (Excel in
    Poland and much of Europe writes `;`); `,` when none is."""
    header = next((line for line in text.split("\n") if line.strip()), "")
    best = max(",;\t", key=lambda d: (header.count(d), d == ","))
    return best if header.count(best) else ","


def _read_texts(path: Path, fmt: str, text_column: str) -> list[tuple[int, str]]:
    if fmt == "jsonl":
        rows, damaged = library.read_jsonl(path)
        if damaged:
            raise Stop(f"{path.name} has damaged lines (not JSON objects): {_lines(damaged)}. Fix or delete them, "
                       f"then import it again; nothing was imported; {AGAIN}.")
        values = [(n, row.get(text_column)) for n, row in enumerate(rows, 1)]
    else:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if fmt == "text":
            return [(n, block.strip()) for n, block in
                    enumerate((b for b in re.split(r"\n\s*\n", text) if b.strip()), 1)]
        if not text.strip():
            return []
        reader = csv.DictReader(io.StringIO(text), delimiter=_delimiter(text))
        if text_column not in (reader.fieldnames or []):
            raise ValueError(f"{path.name} has no column {text_column!r} (its columns: "
                             f"{', '.join(reader.fieldnames or []) or 'none'}). Name it with --text-column.")
        values = [(n, row.get(text_column)) for n, row in enumerate(reader, 1)]
    out = []
    for n, value in values:
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise ValueError(f"{path.name}: record {n}'s {text_column!r} is not text.")
        if value.strip():
            out.append((n, value.strip()))
    return out


def import_file(path: Path, fmt: Literal["csv", "jsonl", "text"], source: str, tier: Literal["A", "B"], *,
                text_column: str = "text") -> list[dict]:
    """Items from review text the user has: `text` is split on blank lines, `csv` and `jsonl` give
    one item per record (`text_column`). Ids are `<source>:<n>`, n the record's place in the file."""
    if str(tier).upper() == "C":
        raise ValueError(f"Tier C is the brand's own words: {TIER_C}. Import customers' texts as tier A "
                         "(own customers) or B (category).")
    if tier not in TIERS:
        raise ValueError(f"The tier is A (own customers) or B (category), not {tier!r}.")
    if fmt not in FORMATS:
        raise ValueError(f"The format is csv, jsonl or text, not {fmt!r}.")
    source = (source or "").strip()
    if not source:
        raise ValueError("Give --source, a short label for where the texts come from (e.g. amazon, survey).")
    path = Path(path)
    return [{"id": f"{source}:{n}", "source": source, "community": source, "url": "", "title": "", "text": text,
             "score": None, "created_utc": None, "query": path.name, "tier": tier}
            for n, text in _texts(path, fmt, text_column)]


# --- the items log --------------------------------------------------------------------------------

def _logged(run: RunFolder) -> list[dict]:
    """The rows of items.jsonl; a Stop naming the damaged lines, so nothing is appended past them."""
    try:
        rows, damaged = library.read_jsonl(run.path / ITEMS)
    except UnicodeDecodeError:
        raise Stop(f"{ITEMS} is not UTF-8 text, so it cannot be read. Nothing was added. Open it and save it as "
                   f"UTF-8, or delete it to collect the voice items again; then run this again; {AGAIN}.") from None
    if damaged:
        raise Stop(f"{ITEMS} has damaged lines (not JSON rows): {_lines(damaged)}. Nothing was added, so an item "
                   f"is never written twice. Fix or delete those lines, then run this again; {AGAIN}.")
    return rows


def append_items(run: RunFolder, items: list[dict]) -> tuple[int, int]:
    """Append the items whose id is not in items.jsonl yet (nor earlier in `items`): (added, duplicates)."""
    seen = {r.get("id") for r in _logged(run)}
    fresh, dup = [], 0
    for it in items:
        if it["id"] in seen:
            dup += 1
            continue
        seen.add(it["id"])
        fresh.append(it)
    library.append_jsonl(run.path / ITEMS, fresh)
    return len(fresh), dup


def _refuse_relabel(run: RunFolder, items: list[dict]) -> None:
    """An imported id (`<source>:<n>`) already logged with another text means a second file came under
    the same --source label: its texts would be dropped as duplicates, so it is a Stop. The same file
    imported again, unchanged, passes (its items are duplicates)."""
    logged = {r.get("id"): r for r in _logged(run)}
    for it in items:
        row = logged.get(it["id"])
        if row is not None and row.get("text") != it["text"]:
            raise Stop(f"{it['id']} is already in {ITEMS} with another text (from {row.get('query') or 'another file'}"
                       f"), so the texts of {it['query']} would be dropped. Import it under its own --source label "
                       f"(e.g. {it['source']}-2); nothing was imported; {AGAIN}.")


def _save(run: RunFolder, kind: str, subreddit: str, query: str, payload: dict) -> str:
    stem = f"reddit_{trends.slug(subreddit)}_{kind}_{trends.slug(query) or 'recent'}"
    target = run.next_version(STAGE, stem, "json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")   # whole or not at all
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, target)
    rel = target.relative_to(run.path).as_posix()
    manifest.record(run, rel, STAGE.split("/", 1)[0], SOURCE, params=payload["_params"])
    return rel


# --- command line ---------------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    for kind in KINDS:
        r = sub.add_parser(f"reddit-{kind}", help=f"{kind} from the Arctic Shift Reddit archive (newest first)")
        r.add_argument("--run", required=True, help="the run folder")
        r.add_argument("--subreddit", required=True, help="the subreddit, without r/")
        r.add_argument("--query", required=True, help="keyword or phrase (space = AND, \"quotes\" = phrase, OR, -term)")
        if kind == "posts":
            r.add_argument("--field", choices=FIELDS, default="title",
                           help="where to match: title (default), selftext (body), query (title and body)")
        r.add_argument("--limit", type=int, default=100, help="1-100 (archive maximum), default 100")
        r.add_argument("--after", help=f"YYYY-MM-DD; default today - {DEFAULT_WINDOW_DAYS} days; all = from 2005")
        r.add_argument("--before", help="YYYY-MM-DD upper bound")
        if kind == "posts":
            r.add_argument("--skip-removed", action="store_true",
                           help="also drop posts whose body was removed (default keeps the title)")
        r.add_argument("--json", action="store_true")
    i = sub.add_parser("import", help="review text, CSV or JSONL the user has (tier A or B)")
    i.add_argument("--run", required=True, help="the run folder")
    i.add_argument("--file", required=True, help="the file to import (from here first, else in the run)")
    i.add_argument("--format", required=True, choices=FORMATS, help="text: one item per blank-line block")
    i.add_argument("--source", required=True, help="a short label, e.g. amazon or survey: ids are <source>:<n>")
    i.add_argument("--tier", required=True, help="A (own customers) or B (category)")
    i.add_argument("--text-column", default="text", help="the column (csv) or key (jsonl) with the text")
    i.add_argument("--json", action="store_true")
    from tm import voice_themes   # it imports this module
    voice_themes.add_parser(sub)


def _reddit(args: argparse.Namespace, run: RunFolder) -> int:
    kind = args.action.removeprefix("reddit-")
    _logged(run)   # a damaged items log stops before any archive call
    skip_removed = getattr(args, "skip_removed", False)
    payload = fetch_reddit(kind, args.subreddit, args.query, field=getattr(args, "field", "title"),
                           limit=args.limit, after=args.after, before=args.before, skip_removed=skip_removed,
                           get=http_get)
    rel = _save(run, kind, args.subreddit, args.query, payload)
    items = items_from_archive(payload, kind, args.query, skip_removed=skip_removed)
    added, dup = append_items(run, items)
    stats = payload["_stats"]
    message = (f"Saved {rel}: {len(items)} items from r/{args.subreddit} ({added} new in {ITEMS}, {dup} already "
               f"there; {stats['removed_bodies']} removed bodies, {stats['bot_skipped']} AutoModerator).")
    if stats["partial"]:
        message += f" Partial: {stats['partial']}; the oldest part of the window was not covered."
    cli.emit(args, {"status": "done", "file": rel, "items": len(items), "items_added": added,
                    "items_duplicate": dup, "partial": bool(stats["partial"]), "stats": stats,
                    "message": message}, message)
    return 0


def _import(args: argparse.Namespace, run: RunFolder) -> int:
    name = Path(args.file).name
    items = import_file(run.given(args.file), args.format, args.source, args.tier, text_column=args.text_column)
    _refuse_relabel(run, items)
    added, dup = append_items(run, items)
    manifest.record(run, ITEMS, STAGE.split("/", 1)[0], f"tm voice import ({args.source.strip()}, tier {args.tier})",
                    params={"file": name, "format": args.format, "items": len(items), "added": added})
    message = f"Imported {len(items)} texts from {name} as tier {args.tier} ({added} new, {dup} already there)."
    cli.emit(args, {"status": "done", "file": ITEMS, "items": len(items), "items_added": added,
                    "items_duplicate": dup, "message": message}, message)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.action == "check":
            from tm import voice_themes   # it imports this module
            return voice_themes.run_check(args, run)
        return _import(args, run) if args.action == "import" else _reddit(args, run)
    except Stop as exc:
        payload = {"status": "stop", "message": str(exc)}
        if isinstance(exc, SourceUnavailable):
            payload = {"status": "stop", "reason": exc.reason, "message": str(exc)}
        cli.emit(args, payload, str(exc))
        return 2
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))


cli.register("voice", _setup, _run)
