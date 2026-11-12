"""Trends for a channel (organic video, FLOWS.md B1 to B3).

- B2's check `shortlist_written` (`shortlist_gap`): a `03_wip/trend_shortlist_vNN.json` written by
  `tm trends shortlist` in this run (its manifest row is dated on or after the run's creation), its
  hooks and formats ranked by the agent's fit for the channel (`--fit`, issue #84) when it lists any to score.
- B3's check `evidence_saved` (`evidence_gap`): each of the shortlist's top `research.cards` trends
  (`top_trends`: the lists taken in turn, hooks, topics, formats, sounds) has a saved card (an error
  answer is none, `brief_research.card_of`) and saved video pages holding at least one video.
- `tm organic videos --run R --trend ID`: the collector shows Claude only a summary of each video page,
  so this lists a trend's saved videos in `trends.load_videos` order, the order a proposal's `pick`
  indexes. An id may be an 8-character prefix (`resolve`, the plan's drift check 21).
- The channel's library, `<workspace>/library/organic/<channel key>/`, both files append-only:
  - `used_trends.jsonl`, one row per trend a video was made from: `{trend_id, name, kind, run, video,
    used, series}` (`record_used`, `used`, `series`; `tm organic used --channel C`);
  - `decisions.jsonl`, one row per proposal decided (Task 6's `tm organic start`), read by `history`
    for its `decision`, `production` and `approach` (`tm organic history --channel C`).
- `tm organic seed-check --run R`: a run started from a trend research seed re-checks it
  (`brief_research.seed_verdict`), stored in run.json `organic.seed_check`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tm import brand, brief_research, config, library, manifest, organic_config, shortlist, state, trends
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

WIP = "03_wip"
ORGANIC_DIR = Path("library") / "organic"
USED = "used_trends.jsonl"
DECISIONS = "decisions.jsonl"
USED_FIELDS = ("trend_id", "name", "kind", "run", "video", "used", "series")
TREND_KINDS = ("hook_trend", "topic_trend", "format_trend", "sound_trend")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECISION_KINDS = ("produce", "later", "skip", "redo")
LISTS = ("hooks", "topics", "formats", "sounds")   # the shortlist's lists, the order `top_trends` takes them in
VIDEO_FIELDS = ("url", "creator", "views", "published", "hook_text", "excerpt")
SHORTLIST_SOURCE = "tm trends shortlist"
_TREND_FILE = re.compile(r"^trend_(?P<id>.+?)(?:_v\d+)?\.json$")


# --- trend ids and cards ----------------------------------------------------------------------------

def _full_ids(run: RunFolder, prefix: str) -> list[str]:
    """The full ids of the saved trend files whose id starts with `prefix`."""
    folder = run.path / trends.RESEARCH
    found = {m["id"] for f in folder.glob(f"trend_{prefix}*.json") if f.is_file()
             for m in [_TREND_FILE.match(f.name)] if m and m["id"].startswith(prefix)}
    return sorted(found)


def card(run: RunFolder, trend_id: str) -> tuple[dict | None, str | None]:
    """(the latest saved card of a full trend id, None) or (None, why there is none)."""
    path = brief_research.card_file(run, trend_id)
    if path is None:
        return None, "no card is saved (get_trend)"
    found, why = brief_research.card_of(path)
    return (found, None) if found is not None else (None, f"{why}; fetch it again with get_trend")


def resolve(run: RunFolder, given: str) -> tuple[str, dict]:
    """(the full id, its card) of a trend id or 8-character prefix: the saved `trend_<prefix>*.json`
    files, each read at its latest version. An error answer is no card. A Stop when no card matches
    (fetch it), a ValueError when the id is not a trend id or the prefix matches several cards."""
    if not (isinstance(given, str) and trends.TREND_ID.fullmatch(given)):
        raise ValueError(f"{given!r} is not a TrendsMesh trend id (letters, digits, - and _).")
    ids = _full_ids(run, given)
    if given in ids:
        ids = [given]
    cards, wrong = {}, []
    for tid in ids:
        found, why = card(run, tid)
        if found is None:
            wrong.append(f"{tid}: {why}")
        else:
            cards[tid] = found
    if len(cards) == 1:
        return next(iter(cards.items()))
    if cards:
        raise ValueError(f"The trend id {given} matches {len(cards)} saved cards ({', '.join(cards)}): give more of "
                         "the id.")
    said = f" ({'; '.join(wrong)})" if wrong else ""
    raise Stop(f"No saved card of the trend {given} in this run{said}. Fetch it with get_trend while collection is "
               f"on, then run this again; {AGAIN}.")


def videos(run: RunFolder, given: str) -> tuple[str, dict, list[dict]]:
    """(the full id, its card, its saved videos) for `tm organic videos`: `trends.load_videos` order, each
    `{index, url, creator, views, published, hook_text, excerpt}`. A Stop when no saved video page holds a video."""
    tid, found = resolve(run, given)
    try:
        saved = trends.load_videos(run, tid)
    except ValueError as exc:
        raise Stop(f"A saved video page of {tid} cannot be read ({exc}). Fetch it again with get_trend_videos, "
                   f"then run this again; {AGAIN}.") from None
    if not saved:
        raise Stop(f"No saved video page of {found.get('name') or tid} ({tid}) holds a video in this run. Fetch it with "
                   f"get_trend_videos (trend_id {tid}) while collection is on, then run this again; {AGAIN}.")
    return tid, found, [{"index": i, **{k: trends.creator_of(v) if k == "creator" else v.get(k) for k in VIDEO_FIELDS}}
                        for i, v in enumerate(saved)]


# --- B2 and B3 ------------------------------------------------------------------------------------

def _shortlist(run: RunFolder) -> tuple[Path | None, dict | None]:
    latest = run.latest(WIP, shortlist.STEM, "json")
    if latest is None:
        return None, None
    try:
        data = trends.read(latest)
    except (OSError, ValueError):
        return latest, None
    ok = isinstance(data, dict) and all(isinstance(data.get(k), list) for k in LISTS)
    return latest, data if ok else None


def shortlist_gap(run: RunFolder) -> str | None:
    """The `shortlist_written` step check: B2 is done once `tm trends shortlist` wrote the latest
    03_wip/trend_shortlist_vNN.json in this run (its manifest row is dated on or after the run's
    creation). Reads only."""
    latest, data = _shortlist(run)
    if latest is None:
        return f"the shortlist is written in this run ({WIP}/{shortlist.STEM}_vNN.json, tm trends shortlist)"
    if data is None:
        return f"the latest shortlist {latest.name} is readable JSON (run tm trends shortlist again)"
    created = state.load(run).created
    rel = f"{WIP}/{latest.name}"
    if not any(r["file"] == rel and r["source"] == SHORTLIST_SOURCE and r["date"] >= created
               for r in manifest.rows(run)):
        return f"the latest shortlist {latest.name} is written by tm trends shortlist in this run (run it again)"
    plugin = (data.get("meta") or {}).get("plugin") or {}
    if data.get("fit_candidates") and not plugin.get("fit_file"):   # a shortlist from before issue #84 has none
        return (f"the hooks and formats of the latest shortlist {latest.name} are scored for the channel: each of its "
                f"fit_candidates in {WIP}/trend_fit_vNN.json, then tm trends shortlist again with --fit")
    return None


def top_trends(data: dict, n: int) -> list[dict]:
    """The shortlist's first `n` distinct trends, its lists taken in turn (hooks, topics, formats,
    sounds: the first of each, then the second ...), as `{id, name, label}`."""
    lists = [[r for r in data.get(k) or [] if isinstance(r, dict) and r.get("id")] for k in LISTS]
    out: dict[str, dict] = {}
    for i in range(max(map(len, lists), default=0)):
        for rows in lists:
            if i < len(rows) and rows[i]["id"] not in out and len(out) < n:
                out[rows[i]["id"]] = {"id": rows[i]["id"], "name": rows[i].get("name"), "label": rows[i].get("label")}
    return list(out.values())


def _has_videos(run: RunFolder, trend_id: str) -> bool:
    """The trend's saved video pages hold at least one video (`tm organic videos` lists them); error
    answers hold none, and an unreadable page counts as none."""
    try:
        return bool(trends.load_videos(run, trend_id))
    except (OSError, ValueError):
        return False


def _cards_wanted(run: RunFolder) -> int:
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = {}
    n = config.get(cfg, "research.cards")
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else organic_config.DEFAULTS["research"]["cards"]


def evidence_gap(run: RunFolder) -> str | None:
    """The `evidence_saved` step check: B3 is done once each of the latest shortlist's top
    `research.cards` trends (`top_trends`) has a saved card (an error answer is none) and saved video
    pages holding at least one video. Reads only."""
    latest, data = _shortlist(run)
    if data is None:
        return (f"the shortlist is written ({WIP}/{shortlist.STEM}_vNN.json, tm trends shortlist), then the cards "
                "and video pages of its top trends are saved")
    n = _cards_wanted(run)
    top = top_trends(data, n)
    if not top:
        return (f"the shortlist {latest.name} ranks at least one trend (search the channel's bubble more widely, "
                "then run tm trends shortlist again)")
    missing = []
    for row in top:
        what = f"{row['name'] or row['id']} ({row['id'][:8]})"
        found, why = card(run, row["id"])
        if found is None:
            missing.append(f"{what}: {why}")
        if not _has_videos(run, row["id"]):
            missing.append(f"{what}: no saved video page holds a video (get_trend_videos)")
    if not missing:
        return None
    return (f"the card and a video page of each of the shortlist's top {len(top)} trends are saved "
            f"({WIP}/{latest.name}): " + "; ".join(missing))


# --- the channel's used trends, series and decisions ------------------------------------------------

def _folder(workspace: Path, channel: str) -> Path:
    key = brand.channel_key(channel or "")
    if not key:
        raise ValueError("Give the channel's name or key, for example --channel exampleedu.")
    return Path(workspace) / ORGANIC_DIR / key


def known_channel(workspace: Path, channel: str) -> str:
    """The channel's key, once the library has its channel profile or its organic folder; else a
    ValueError naming the channels it has (a typo would hide the used log, OV2)."""
    folder = _folder(workspace, channel)
    if folder.is_dir() or brand.latest(workspace, channel, kind="channel") is not None:
        return folder.name
    root = Path(workspace) / brand.CHANNEL_DIR
    names = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    have = f"The channels with a profile are: {', '.join(names)}." if names else "No channel profile is saved yet."
    raise ValueError(f"No channel {folder.name!r}: it has no channel profile ({brand.CHANNEL_DIR.as_posix()}/"
                     f"{folder.name}/) and no log ({ORGANIC_DIR.as_posix()}/{folder.name}/). {have} Give the key "
                     "config.yaml channels names.")


def _rows(workspace: Path, path: Path) -> list[dict]:
    """The rows of an append-only file of the channel; a damaged line is a Stop that names it."""
    rows, damaged = library.read_jsonl(path)
    if damaged:
        rel = path.relative_to(Path(workspace)).as_posix()
        lines = ", ".join(map(str, damaged))
        raise Stop(f"{rel} has a damaged line (line {lines}: not one JSON row), so it cannot be read. Fix or delete "
                   f"that line, then run this again; {AGAIN}.")
    return rows


def used(workspace: Path, channel: str) -> dict[str, dict]:
    """The trends this channel has made videos from: trend id -> its latest row in used_trends.jsonl."""
    out: dict[str, dict] = {}
    for row in _rows(workspace, _folder(workspace, channel) / USED):
        if isinstance(row.get("trend_id"), str) and row["trend_id"]:
            out[row["trend_id"]] = row
    return out


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _day(value: object) -> bool:
    if not (isinstance(value, str) and _DAY.fullmatch(value)):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def used_rows(rows: list[dict]) -> list[dict]:
    """The rows `record_used` appends (only USED_FIELDS kept; `used` defaults to today), checked
    without writing anything, so a caller can check them before it makes what they name. ValueError
    for a row without a trend id, a trend kind, a run or a video, or whose `used` is not a day
    (YYYY-MM-DD)."""
    out = []
    for row in rows:
        if not (isinstance(row, dict) and _text(row.get("trend_id")) and trends.TREND_ID.fullmatch(row["trend_id"])):
            raise ValueError(f"A used trend needs its trend_id (a TrendsMesh trend id): {row!r}.")
        if not (_text(row.get("run")) and _text(row.get("video"))):
            raise ValueError(f"A used trend names the run and the video made from it: {row!r}.")
        if row.get("series") is not None and not _text(row["series"]):
            raise ValueError(f"A used trend's series is its name, or null: {row!r}.")
        if row.get("kind") not in TREND_KINDS:
            raise ValueError(f"A used trend's kind is one of {', '.join(TREND_KINDS)}: {row!r}.")
        day = row.get("used") or date.today().isoformat()
        if not _day(day):
            raise ValueError(f"A used trend's used is the day it was used, YYYY-MM-DD: {row!r}.")
        out.append({**{k: row.get(k) for k in USED_FIELDS}, "used": day})
    return out


def record_used(workspace: Path, channel: str, rows: list[dict]) -> int:
    """Append `rows` (`used_rows`) to the channel's used_trends.jsonl; the number appended."""
    out = used_rows(rows)
    library.append_jsonl(_folder(workspace, channel) / USED, out)
    return len(out)


def series(workspace: Path, channel: str) -> list[dict]:
    """The channel's series, in the order they began: `{series, episodes, trend_ids, videos, last_used}`,
    where each video is `<run>/<video>` and the episodes are its videos so far."""
    out: dict[str, dict] = {}
    for row in _rows(workspace, _folder(workspace, channel) / USED):
        name = row.get("series")
        if not _text(name):
            continue
        entry = out.setdefault(name, {"series": name, "episodes": 0, "trend_ids": [], "videos": [], "last_used": None})
        video = f"{row.get('run')}/{row.get('video')}"
        if video not in entry["videos"]:
            entry["videos"].append(video)
            entry["episodes"] = len(entry["videos"])
        if row.get("trend_id") not in entry["trend_ids"]:
            entry["trend_ids"].append(row.get("trend_id"))
        if isinstance(row.get("used"), str) and (entry["last_used"] is None or row["used"] > entry["last_used"]):
            entry["last_used"] = row["used"]
    return list(out.values())


def history(workspace: Path, channel: str) -> dict:
    """The channel's decisions so far (decisions.jsonl): how many, and produce / later / skip / redo per
    production type and per approach (a row without one counts under "unknown")."""
    rows = [r for r in _rows(workspace, _folder(workspace, channel) / DECISIONS) if r.get("decision") in DECISION_KINDS]
    out: dict = {"decisions": len(rows), "by_production": {}, "by_approach": {}}
    for row in rows:
        for group, key in (("by_production", "production"), ("by_approach", "approach")):
            name = row.get(key) if _text(row.get(key)) else "unknown"
            counts = out[group].setdefault(name, dict.fromkeys(DECISION_KINDS, 0))
            counts[row["decision"]] += 1
    return out


# --- the seed --------------------------------------------------------------------------------------

def seed_check(run: RunFolder) -> dict:
    """`brief_research.seed_verdict` for an organic video run started from a seed, stored in run.json
    `organic.seed_check` (C1 needs `keep` for the seeded trend). ValueError for another run."""
    if state.load(run).playbook != ORGANIC_VIDEO:
        raise ValueError(f"{run.path.name} is not an organic video run: a creative brief re-checks its seed with "
                         "tm brief seed-check.")
    return brief_research.seed_check(run, brief_research.run_config(run), key="organic")
