"""The weekly digest (TR8) and the call check (TR9): the handoff's tools/pb4/growth.py `diff`, ported to
the run's saved TrendsMesh answers, with what a weekly run needs around it.

    load_previous     A2: the previous run's latest snapshot, category map and config, copied once
                      into 00_raw/ (prev_snapshot.json, prev_category_map.json, prev_config.yaml)
    rebuild_previous  V24: no stored snapshot, so the previous week is rebuilt from evidence dates
                      (snapshot_growth_<date>_rebuilt_vNN.json, marked "rebuilt": true when written)
    fetch_plan        TR8: which trends' videos to fetch again, which to copy from the previous run
    reuse             TR8: copies those videos, one manifest row each
    diff              TR8 + TR9: 02_research/digest_vNN.json, and the calls into the library
    add_calls         TR9: <workspace>/library/trend_calls.jsonl, one row per call, never twice (a
                      known verdict may follow an unknown one); refused while a line is damaged
    calls_summary     TR9: the hit rate per call, and the damaged lines

A weekly run is a new run linked by `previous_run` (the plan's decision 9). New and ended trends
come from the snapshots' `pool_ids`, every id last week's searches and hook lists returned
(decision 10): "new" is not in the previous pool; "ended" was in the previous snapshot, is not in
this one, and its `get_trend` answer is missing, an error or `momentum: over`. A previous state
without a pool (the reference run's own snapshots) or marked rebuilt (V24: its pool is this week's) is
"rebuilt": new follows the original rule (no creators then) and ended is left out, which the page says.

The call check covers every "act now" and "past its peak" call of the previous snapshot, also when
the trend left this week's map (Review Focus 2): its own fresh videos, else those of the trend it
came back as (names sharing >= 60 % of their words, V25). A call with no saved video page stops the
digest (nothing written) until its videos are fetched, so `verdict: "unknown"` means only that
TrendsMesh had no dated video with a creator, never that nobody fetched them. A creator is
`trends.creator_of` (F17). Added to the original digest: `plugin` on each call and re-identified row
and a top-level `plugin`; the original keys keep their meaning.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from datetime import date
from pathlib import Path

from tm import config, library, manifest, page, research_growth, research_map, state, trend_spool, trends
from tm.research_growth import BUCKETS, d
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

RAW = "00_raw"
WIP = "03_wip"
PREV_SNAPSHOT = Path(RAW) / "prev_snapshot.json"
PREV_MAP = research_map.PREVIOUS
PREV_CONFIG = Path(RAW) / "prev_config.yaml"
PREV_SPLIT = Path(RAW) / "prev_split.json"
PAGE = "report"
STEM = "digest"
REBUILT = re.compile(r"^snapshot_growth_(.+)_rebuilt_v(\d+)\.json$")
CALLED = ("act_now", "past_peak")                    # TR9: the calls checked a week later
REFETCH = ("act_now", "still_rising", "past_peak")   # TR8: fetched again whether updated or not
SECONDS_PER_CALL = 2.5   # issue #8: 142 get_trend_videos calls took about 6 minutes, rate limits included
UPDATED_LISTS = "list_updated_*.json"
DEFAULT_FEED = "global"                              # list_trends' feed when none is given
COVER_INPUTS = ("sort", "trend_type", "page", "limit")   # what may be given to a list that counts as cover
CALLS = Path("library") / "trend_calls.jsonl"
SCHEMA = "pb4-call/1"
VERDICTS = ("held", "missed", "unknown")
SOURCE = "tm research digest"
_STOP_WORDS = {"and", "the", "with", "videos", "content"}


_workspace = trend_spool.workspace_of


def _previous(run: RunFolder) -> tuple[str | None, RunFolder | None]:
    """`previous_run` (workspace-relative) and its folder, or (None, None) for a first run. Stops when
    the folder is not there (moved or deleted)."""
    rel = state.load(run).previous_run
    if not rel:
        return None, None
    try:
        return rel, RunFolder.open(_workspace(run) / rel)
    except OSError:
        raise Stop(f"This run follows {rel}, but that run folder is not there (moved or deleted?), so last week's "
                   "snapshot, map and videos cannot be read. Put the folder back at that path, then run this again; "
                   "the run continues from the same place.") from None


def _snapshot(path: Path) -> dict:
    data = trends.read(path)
    if not isinstance(data, dict) or not isinstance(data.get("trends"), dict) or not isinstance(data.get("params"), dict):
        raise Stop(f"{path.name} is not a growth snapshot (it needs params and trends). Give a snapshot_vNN.json "
                   "written by tm research growth (or 00_raw/prev_snapshot.json from tm research previous), or rebuild "
                   "the previous week with tm research rebuild-previous --as-of <its date>; the run continues from the "
                   "same place.")
    return data


# --- the previous run (A2, V24) ---------------------------------------------------------------

def _place(tmp: Path, dest: Path) -> bool:
    """Put the copy `tmp` at `dest`, never over a file already there; False when `dest` exists. It
    is linked into place; on a filesystem without hard links (FAT, some network shares) `dest` is
    created exclusively and written, and removed again if the write fails."""
    try:
        os.link(tmp, dest)
        return True
    except FileExistsError:
        return False
    except OSError:
        pass
    try:
        out = open(dest, "xb")
    except FileExistsError:
        return False
    try:
        with out, open(tmp, "rb") as src:
            shutil.copyfileobj(src, out)
    except OSError:
        dest.unlink(missing_ok=True)
        raise
    return True


def load_previous(run: RunFolder) -> dict:
    """Copy the previous run's latest snapshot, category map, split file and config into 00_raw/ (read-only):
    a file already there is never replaced (the copy is linked, or created exclusively, into place:
    both fail on an existing file), so a second call copies nothing. Returns `{previous_run, snapshot, page, copied,
    already, missing}`: `snapshot` is 00_raw/prev_snapshot.json or None (the previous run has none:
    rebuild it, V24), `page` the publish record of the report page along the previous runs, or None;
    `copied` the files copied now, `already` those 00_raw held already, `missing` those the previous
    run has none of. A first run returns `{previous_run: None}`."""
    rel, prev = _previous(run)
    if prev is None:
        return {"previous_run": None}
    plain_config = prev.path / config.FILE
    sources = [(PREV_SNAPSHOT, prev.latest(trends.RESEARCH, research_growth.snapshot_stem(research_growth.STEM), "json")),
               (PREV_MAP, prev.latest(trends.RESEARCH, research_map.STEM, "json")),
               (PREV_SPLIT, prev.latest(WIP, research_map.SPLIT_STEM, "json")),
               (PREV_CONFIG, plain_config if plain_config.is_file() else None)]
    copied, already, missing = [], [], []
    for target, source in sources:
        if source is None:
            missing.append(target.as_posix())
            continue
        dest = run.path / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")      # whole or not at all
        shutil.copyfile(source, tmp)
        try:
            if not _place(tmp, dest):
                already.append(target.as_posix())
                continue
        finally:
            tmp.unlink()
        manifest.record(run, target.as_posix(), RAW, f"copied from {Path(rel).name}",
                        params={"from": f"{rel}/{source.relative_to(prev.path).as_posix()}"})
        copied.append(target.as_posix())
    snapshot = PREV_SNAPSHOT.as_posix() if (run.path / PREV_SNAPSHOT).is_file() else None
    return {"previous_run": rel, "snapshot": snapshot, "page": page.published(run, PAGE), "copied": copied,
            "already": already, "missing": missing}


def rebuild_previous(run: RunFolder, as_of: date, cfg: dict) -> Path:
    """V24: the previous week rebuilt from this run's evidence dates, `compute` as of `as_of` with
    the stem growth_<as_of>_rebuilt, its snapshot marked rebuilt when written (F9). Returns the
    snapshot."""
    stem = f"growth_{as_of.isoformat()}_rebuilt"
    growth = research_growth.compute(run, as_of, cfg, stem=stem, snapshot_extra={"rebuilt": True})
    return research_growth.snapshot_of(growth, stem)


def rebuilt_snapshot(run: RunFolder) -> Path | None:
    """The latest rebuilt snapshot, 02_research/snapshot_growth_<date>_rebuilt_vNN.json: the latest
    date, then the highest NN (F9)."""
    folder = run.path / trends.RESEARCH
    found = [(m.group(1), int(m.group(2)), f) for f in folder.glob("snapshot_growth_*_rebuilt_v*.json")
             if f.is_file() and (m := REBUILT.match(f.name))] if folder.is_dir() else []
    return max(found, key=lambda t: (t[0], t[1]))[2] if found else None


def default_prev(run: RunFolder) -> Path | None:
    """The digest's previous state: 00_raw/prev_snapshot.json, else the latest rebuilt snapshot."""
    stored = run.path / PREV_SNAPSHOT
    return stored if stored.is_file() else rebuilt_snapshot(run)


# --- the fetch plan (TR8) ---------------------------------------------------------------------

def _hooks_to_fetch(run: RunFolder) -> list[str]:
    """The hooks whose videos this week needs: the shortlist (issue #8); in a run whose hooks path ran
    before the shortlist, every hook card (that path read all of them). Stops when hooks are listed but
    not ranked yet: fetching every one of them is what the shortlist avoids."""
    short = research_growth.shortlist(run)
    if short is not None:
        return [r["id"] for r in short["shortlist"]]
    cards = [c["id"] for c in research_growth.hook_cards(run)]
    if cards and run.latest(trends.RESEARCH, research_growth.HOOKS_STEM, "json") is None:
        raise Stop(f"The {len(set(cards))} saved hook candidates are not ranked yet, so the plan can't tell which "
                   "hooks to fetch. Score every one for fit (03_wip/hook_fit_vNN.json) and run tm research hook-fit "
                   f"first: only its shortlist is fetched. Then run this again; {AGAIN}.")
    return cards


def minutes(calls: int) -> int:
    """About how many minutes `calls` get_trend_videos calls take (a niche run: 142 in about 6)."""
    return math.ceil(calls * SECONDS_PER_CALL / 60)


def _current(run: RunFolder) -> tuple[dict[str, str | None], set[str]]:
    """This week's trends that need videos, id -> kind: the map's kept trends, then the shortlisted
    hooks (`_hooks_to_fetch`); and the ids growth evaluates, the map's kept trends and the hooks
    path's kept hooks (this week's snapshot)."""
    kept = research_growth.category_map(run).get("kept") or []
    out: dict[str, str | None] = {r["id"]: r.get("kind") for r in kept if r.get("id")}
    for hid in _hooks_to_fetch(run):
        out.setdefault(hid, "hook_trend")
    hooks = run.latest(trends.RESEARCH, research_growth.HOOKS_STEM, "json")
    kept_hooks = (trends.read(hooks).get("kept") or []) if hooks else []
    return out, {r["id"] for r in [*kept, *kept_hooks] if r.get("id")}


_LIST_NAME = re.compile(r"^list_updated_(.+)_p(\d+)(?:_v(\d+))?$")


def _no_next_page(answer: object) -> bool:
    """Whether a list page says no page follows (`has_more: false`, or page >= pages)."""
    if not isinstance(answer, dict):
        return False
    if "has_more" in answer:
        return answer["has_more"] is False
    page_no, pages = answer.get("page"), answer.get("pages")
    return isinstance(page_no, int) and isinstance(pages, int) and page_no >= pages


def _on_or_before(when: object, since: date) -> bool:
    try:
        return isinstance(when, str) and d(when) <= since
    except ValueError:
        return False                                   # an unreadable date proves nothing


def _narrowed(tool_input: dict | None) -> bool:
    """Whether a saved list may not list every updated trend: an input other than `sort`,
    `trend_type`, `page` and `limit` (a `q` text, another feed, `include_general`, `as_of` ...) is
    given. An empty value, or the default feed, is no narrowing."""
    if tool_input is None:
        return False
    return any(k not in COVER_INPUTS and v not in (None, "") and not (k == "feed" and v == DEFAULT_FEED)
               for k, v in tool_input.items())


def updated_lists(run: RunFolder, since: date) -> tuple[set[str], set[str], bool]:
    """This run's `lists/list_updated_*` answers (TrendsMesh list_trends sort=updated): the ids
    updated after `since` (a card without a readable `updated_at` counts as updated), the trend
    types whose list is known to reach back to `since` ("all" for a list of every type), and whether
    any list is saved. A list reaches back when every page from page 1 to its last saved page is
    saved, and that last page says no page follows or its oldest card was updated on or before
    `since` (`trends.oldest_updated_at`), and its pages were asked with one `limit`. A list given any other input (`q`, another
    `feed`, `include_general` ...) adds its updated ids but never reaches back: it may not list
    every trend."""
    folder = run.path / trends.RESEARCH / "lists"
    files = sorted(folder.glob(UPDATED_LISTS)) if folder.is_dir() else []
    ids: set[str] = set()
    last: dict[str, tuple[int, int, object]] = {}
    pages: dict[str, set[int]] = {}
    limits: dict[str, set[object]] = {}
    for order, f in enumerate(files):
        data = trends.read(f)
        answer = trends.unwrap(data)
        tool_input = data.get("_input") if isinstance(data, dict) and isinstance(data.get("_input"), dict) else None
        m = _LIST_NAME.match(f.stem)
        if tool_input is not None:
            kind, page_no = tool_input.get("trend_type") or "all", tool_input.get("page") or 1
        else:
            kind, page_no = (m.group(1), int(m.group(2))) if m else ("all", 1)
        cards = [c for c in trends.items(answer) if isinstance(c, dict) and c.get("id")]
        ids |= {c["id"] for c in cards if not _on_or_before(c.get("updated_at"), since)}
        if _narrowed(tool_input):
            continue
        pages.setdefault(kind, set()).add(page_no)
        limits.setdefault(kind, set()).add((tool_input or {}).get("limit"))
        if kind not in last or (page_no, order) > last[kind][:2]:
            last[kind] = (page_no, order, answer)
    covered = set()
    for kind, (last_page, _, answer) in last.items():
        cards = [c for c in trends.items(answer) if isinstance(c, dict)]
        every_page = pages[kind] >= set(range(1, last_page + 1)) and len(limits[kind]) == 1
        if every_page and (_no_next_page(answer) or _on_or_before(trends.oldest_updated_at(cards), since)):
            covered.add(kind)
    return ids, covered, bool(files)


def _pages(run: RunFolder, trend_id: str) -> int:
    """How many pages of the trend's videos the run saved (a page saved twice counts once)."""
    return len({re.sub(r"_v\d+$", "", f.stem).lower() for f in trends.video_files(run, trend_id)})


def _plan(run: RunFolder) -> dict:
    rel, prev = _previous(run)
    current, evaluated = _current(run)
    stored = run.path / PREV_SNAPSHOT
    if prev is None or not stored.is_file():
        note = ("there is no previous snapshot in 00_raw (a first run, or run tm research previous first), so "
                "every trend is fetched")
        return {"fetch": sorted(current), "reuse": [], "check": [], "calls_estimate": len(current),
                "minutes_estimate": minutes(len(current)), "since": None, "previous_run": rel, "note": note}
    snap = _snapshot(stored)
    since = date.fromisoformat(snap["params"]["ref"])
    updated, covered, listed = updated_lists(run, since)
    again = {tid for tid, t in snap["trends"].items() if t.get("bucket") in REFETCH}

    def known_not_updated(tid: str) -> bool:
        return ("all" in covered or current[tid] in covered) and tid not in updated

    reuse = sorted(t for t in current if known_not_updated(t) and t not in again and _pages(prev, t))
    fetch = sorted((set(current) | again) - set(reuse))
    if not listed:
        note = ("no list of updated trends is saved (TrendsMesh list_trends, sort updated), so nothing is known to "
                "be unchanged and every trend is fetched")
    elif not covered:
        note = (f"the saved list of updated trends does not reach back to {since.isoformat()} (its last page has "
                "more, and its last card is newer), so every trend is fetched; list more pages to reuse some")
    elif "all" not in covered:
        note = (f"the lists of updated trends reach back to {since.isoformat()} only for {', '.join(sorted(covered))}, "
                "so other trends are fetched")
    else:
        note = None
    calls = sum(_pages(prev, t) or 1 for t in fetch)
    return {"fetch": fetch, "reuse": reuse, "check": sorted(t for t in snap["trends"] if t not in evaluated),
            "calls_estimate": calls, "minutes_estimate": minutes(calls), "since": since.isoformat(),
            "previous_run": rel, "note": note}


def fetch_plan(run: RunFolder, cfg: dict) -> dict:
    """`{fetch, reuse, check, calls_estimate, minutes_estimate, since, previous_run, note}`.
    - fetch = this map and the shortlisted hooks (issue #8), minus `reuse`, plus every previous "act
      now", "still rising" and "past its peak" trend (on the map or not); Stops when hooks are saved
      but not ranked yet (tm research hook-fit);
    - reuse = the trends the previous run has videos for, not updated since its reference date
      (`since`), and not among those three stages. A trend is known not updated only when a saved
      list of updated trends of its type (or of every type) reaches back to `since`: with no such
      list nothing is reused, and `note` says why;
    - check = the previous snapshot's trends that are not in this week's (the map's kept trends and
      the hooks path's kept hooks): each needs a get_trend answer, or the digest counts it as ended;
    - calls_estimate counts get_trend_videos pages: the previous run's pages of a trend, else 1;
      minutes_estimate is about how long they take, to tell the user before a long fetch.
    Before load_previous (or in a first run) everything is fetched. `cfg` is the run's config; no
    threshold of it changes the plan today."""
    return _plan(run)


def reuse(run: RunFolder) -> list[Path]:
    """Copy the videos of the plan's `reuse` trends from the previous run into 02_research/videos/,
    with a manifest row each ("copied from <run>: not updated since <date> (TR8)"). A trend this run
    has videos for already is left as it is, so a second call copies nothing."""
    plan = _plan(run)
    rel, prev = _previous(run)
    copied = []
    for tid in plan["reuse"]:
        if trends.video_files(run, tid):
            continue
        for f in trends.video_files(prev, tid):
            dest = run.unique_path(Path(trends.RESEARCH) / "videos" / f.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dest)
            manifest.record(run, dest.relative_to(run.path).as_posix(), trends.RESEARCH,
                            f"copied from {Path(rel).name}: not updated since {plan['since']} (TR8)",
                            params={"from": f"{rel}/{f.relative_to(prev.path).as_posix()}"})
            copied.append(dest)
    return copied


# --- the digest (TR8) and the call check (TR9) ------------------------------------------------

def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in _STOP_WORDS}


def _share(a: str, b: str) -> float:
    return len(_words(a) & _words(b)) / max(1, len(_words(a) | _words(b)))


def ended_by_answer(run: RunFolder, trend_id: str) -> bool:
    """Whether the latest saved get_trend answer of a trend says it ended: missing, an error (or not
    JSON), or `momentum: over`."""
    path = run.latest(trends.RESEARCH, f"trend_{trend_id}", "json")
    if path is None:
        return True
    answer = trends.answer_of(path)
    if not isinstance(answer, dict) or "error" in answer or "raw" in answer:
        return True
    card = answer.get("data") if isinstance(answer.get("data"), dict) else answer
    return card.get("momentum") == "over"


def _joined(videos: list[dict], then: date, now: date) -> int | None:
    """New creators after `then` up to `now` (creators first seen in the window); None when no
    dated video carries a creator, so nothing can be said."""
    dated = [(trends.creator_of(v), d(v["published"])) for v in videos if v.get("published")]
    dated = [(who, p) for who, p in dated if who]
    if not dated:
        return None
    before = {who for who, p in dated if p <= then}
    return len({who for who, p in dated if then < p <= now} - before)


def _rate(calls: list[dict], call: str) -> tuple[float | None, int]:
    """(held / checked, checked) of one call; unknown calls are not counted."""
    known = [c for c in calls if c["call"] == call and c["held"] is not None]
    return (round(sum(c["held"] for c in known) / len(known), 2) if known else None), len(known)


def _call_run(run: RunFolder, prev: dict, prev_path: Path, rebuilt: bool) -> str:
    """The run whose calls these are: the previous run; a rebuilt state is this run's own rebuild
    of that date, so its calls never share a key with the previous run's real ones."""
    s = state.load(run)
    if rebuilt:
        return f"{s.run_id}:rebuilt:{prev['params'].get('as_of')}"
    return Path(s.previous_run).name if s.previous_run else f"{s.run_id}:{prev_path.name}"


def diff(run: RunFolder, prev_snapshot: Path, cfg: dict) -> Path:
    """The original's `cmd_diff` (TR8 + TR9) of this run's latest snapshot against `prev_snapshot`, with
    the changes in the module docstring. Writes 02_research/digest_vNN.json, appends the calls to
    <workspace>/library/trend_calls.jsonl (never one twice) and returns the digest. Stops when this
    run has no snapshot yet."""
    cfg = research_map.settings(cfg)
    now_path = run.latest(trends.RESEARCH, research_growth.snapshot_stem(research_growth.STEM), "json")
    if now_path is None:
        raise Stop("This run has no snapshot yet, so there is nothing to compare. Run tm research growth "
                   "first; the run continues from the same place.")
    prev_snapshot = Path(prev_snapshot)
    now, prev = _snapshot(now_path), _snapshot(prev_snapshot)
    nt, pt = now["trends"], prev["trends"]
    rebuilt = prev.get("rebuilt") is True or not isinstance(prev.get("pool_ids"), list)
    pool = None if rebuilt else set(prev["pool_ids"])
    order = {b: i for i, b in enumerate(BUCKETS)}
    new, up, down = [], [], []
    for tid, t in nt.items():
        p = pt.get(tid)
        is_new = tid not in pool if pool is not None else bool(p and not (p.get("growth") or {}).get("creators"))
        if is_new:
            new.append({"id": tid, "name": t["name"], "bucket": t["bucket"]})
            continue
        if not p:
            continue
        if order[t["bucket"]] < order[p["bucket"]]:
            up.append({"id": tid, "name": t["name"], "from": p["bucket"], "to": t["bucket"]})
        elif order[t["bucket"]] > order[p["bucket"]]:
            down.append({"id": tid, "name": t["name"], "from": p["bucket"], "to": t["bucket"]})
    ended = [] if rebuilt else [{"id": tid, "name": p["name"], "kind": p.get("kind")} for tid, p in pt.items()
                                if tid not in nt and ended_by_answer(run, tid)]
    # Trend ids are not stable across days (merges, re-promotion, V25): a new and an ended trend whose
    # names share most words are one trend under a new id.
    reidentified, renamed = [], {}
    for n_ in list(new):
        best = max(ended, key=lambda e: _share(e["name"], n_["name"]), default=None)
        if best and _share(best["name"], n_["name"]) >= 0.6:
            reidentified.append({"id": n_["id"], "name": n_["name"], "was": best["name"], "bucket": n_["bucket"],
                                 "plugin": {"was_id": best["id"]}})
            renamed[best["id"]] = n_["id"]
            new.remove(n_)
            ended.remove(best)
    current_names = {t["name"].lower() for t in nt.values()}
    ended = [e for e in ended if e["name"].lower() not in current_names]   # same name lives on under another id

    then, now_ref = date.fromisoformat(prev["params"]["ref"]), date.fromisoformat(now["params"]["ref"])
    called = [(tid, p) for tid, p in pt.items() if p.get("bucket") in CALLED]
    unfetched = [(tid, p) for tid, p in called if not trends.video_files(run, tid)
                 and not (renamed.get(tid) and trends.video_files(run, renamed[tid]))]
    if unfetched:
        shown = ", ".join(f"{p['name']!r} ({tid})" for tid, p in unfetched)
        raise Stop(f"The call check needs this week's videos of every call of the previous run, and these have none "
                   f"saved ({len(unfetched)}): {shown}. Fetch their videos (TrendsMesh get_trend_videos, every page) "
                   "with collection on, then run the digest again. Nothing was written; the run continues from the "
                   "same place.")
    calls, rows = [], []
    call_run = _call_run(run, prev, prev_snapshot, rebuilt)
    s = state.load(run)
    for tid, p in called:
        as_now = renamed.get(tid)
        videos = trends.load_videos(run, tid) or (trends.load_videos(run, as_now) if as_now else [])
        joined = _joined(videos, then, now_ref)        # None: TrendsMesh had no dated video with a creator
        held = None if joined is None else (joined > 0 if p["bucket"] == "act_now" else joined == 0)
        verdict = "unknown" if held is None else "held" if held else "missed"
        calls.append({"id": tid, "name": p["name"], "call": p["bucket"], "new_creators_since": joined, "held": held,
                      "plugin": {"verdict": verdict, "in_map": tid in nt, "reidentified_as": as_now}})
        t_now = nt.get(tid) or nt.get(as_now) or {}
        g_then = p.get("growth") or {}
        rows.append({"schema": SCHEMA, "call_run": call_run, "checked_in_run": s.run_id,
                     "category": cfg["category"].get("phrase"), "market": cfg.get("market"), "trend_id": tid,
                     "trend_name": p["name"], "call": p["bucket"], "ref_then": then.isoformat(),
                     "ref_now": now_ref.isoformat(),
                     "metrics_then": {"new_recent": g_then.get("new_recent"), "creators": g_then.get("creators"),
                                      "last_seen_days": g_then.get("last_seen_days"),
                                      "velocity_index": (p.get("relative") or {}).get("velocity_index")},
                     "metrics_now": {"new_creators_since": joined, "bucket_now": t_now.get("bucket"),
                                     "velocity_index": (t_now.get("relative") or {}).get("velocity_index")},
                     "held": held, "verdict": verdict, "reidentified_as": as_now})
    workspace = _workspace(run)
    pending = _pending(workspace, rows)                 # a damaged library stops here, before anything is written
    try:
        prev_name = prev_snapshot.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        prev_name = str(prev_snapshot)
    out = {"prev": prev["params"], "now": now["params"], "new": new, "reidentified": reidentified, "up": up,
           "down": down, "ended": ended, "calls": calls, "hit_rate": {b: _rate(calls, b) for b in CALLED},
           "plugin": {"prev_snapshot": prev_name, "now_snapshot": now_path.name, "prev_rebuilt": rebuilt,
                      "ended_checked": not rebuilt,
                      "unknown_calls": {b: sum(c["call"] == b and c["held"] is None for c in calls) for b in CALLED},
                      "call_run": call_run, "calls_file": CALLS.as_posix(), "calls_added": len(pending)}}
    target = run.next_version(trends.RESEARCH, STEM, "json")
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.record(run, f"{trends.RESEARCH}/{target.name}", trends.RESEARCH, SOURCE,
                    params={"prev": prev_name, "now": now_path.name})
    _append(workspace, pending)                         # the digest first, then the library (M10)
    return target


# --- the calls library (TR9) ------------------------------------------------------------------

class DamagedCalls(Stop):
    """library/trend_calls.jsonl has lines that are not JSON rows: nothing is added until they are fixed."""


def _read_calls(workspace: Path) -> tuple[list[dict], list[int]]:
    """The rows of <workspace>/library/trend_calls.jsonl and the numbers (from 1) of its damaged lines."""
    return library.read_jsonl(Path(workspace) / CALLS)


def call_rows(workspace: Path) -> list[dict]:
    """Every readable row of <workspace>/library/trend_calls.jsonl (`calls_summary` names damaged lines)."""
    return _read_calls(workspace)[0]


def _known(row: dict) -> bool:
    return row.get("verdict") in ("held", "missed")


def _key(row: dict) -> tuple:
    return row.get("call_run"), row.get("trend_id")


def _pending(workspace: Path, rows: list[dict]) -> list[dict]:
    """The rows `add_calls` would append: a (call_run, trend_id) not in the library yet, or a known
    verdict for a call the library holds only as unknown. Refuses (DamagedCalls) while the library
    has damaged lines."""
    for row in rows:
        if not isinstance(row, dict) or not row.get("call_run") or not row.get("trend_id"):
            raise ValueError("A call row needs its call_run and trend_id.")
    existing, damaged = _read_calls(workspace)
    if damaged:
        raise DamagedCalls(f"{CALLS.as_posix()} has damaged lines (not JSON rows): {', '.join(map(str, damaged))}. No "
                           "call is added while they are there, so the hit rate never counts a call twice. Fix or "
                           "delete those lines, then run this again; the run continues from the same place.")
    present = {_key(r) for r in existing}
    known = {_key(r) for r in existing if _known(r)}
    fresh = []
    for row in rows:
        key = _key(row)
        if key in known or (key in present and not _known(row)):
            continue
        fresh.append(row)
        present.add(key)
        if _known(row):
            known.add(key)
    return fresh


def _append(workspace: Path, rows: list[dict]) -> None:
    library.append_jsonl(Path(workspace) / CALLS, rows)


def add_calls(workspace: Path, rows: list[dict]) -> int:
    """Append the rows whose (call_run, trend_id) is not in the library yet, or that give a known
    verdict to a call held only as unknown; returns how many. Refuses (DamagedCalls, a ValueError)
    while the library has damaged lines, naming them."""
    fresh = _pending(workspace, rows)
    _append(workspace, fresh)
    return len(fresh)


def calls_summary(workspace: Path, category: str | None = None, *, include_rebuilt: bool = False) -> dict:
    """`{"calls": {call: {held, missed, unknown, checked, hit_rate}}, "damaged": [line numbers]}`.
    Each (call_run, trend_id) counts once: its last known row, else its last row. checked = held +
    missed; hit_rate = held / checked, None when nothing was checked. `category` keeps one category,
    whatever its case. Calls of a rebuilt previous state (`call_run` with ":rebuilt:") are left out
    unless `include_rebuilt`: no run made them."""
    rows, damaged = _read_calls(workspace)
    latest: dict[tuple, dict] = {}
    for r in rows:
        if not include_rebuilt and ":rebuilt:" in str(r.get("call_run")):
            continue
        if category is not None and str(r.get("category") or "").casefold() != category.casefold():
            continue
        key = _key(r)
        if key in latest and _known(latest[key]) and not _known(r):
            continue
        latest[key] = r
    out: dict[str, dict] = {}
    for r in latest.values():
        counts = out.setdefault(str(r.get("call")), {"held": 0, "missed": 0, "unknown": 0})
        counts[r.get("verdict") if r.get("verdict") in VERDICTS else "unknown"] += 1
    for counts in out.values():
        counts["checked"] = counts["held"] + counts["missed"]
        counts["hit_rate"] = round(counts["held"] / counts["checked"], 2) if counts["checked"] else None
    return {"calls": out, "damaged": damaged}
