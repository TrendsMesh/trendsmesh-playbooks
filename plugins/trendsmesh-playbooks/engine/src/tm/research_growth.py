"""Growth and stages (TR1 hooks path, TR2, TR3, TR4 flags, TR8 snapshot, TR3's backtest): the handoff's
tools/pb4/growth.py `hooks`, `compute` and `backtest`, ported to the run's saved TrendsMesh answers (`tm.trends`)
instead of the original's REST calls.

    hook_fit the hook trends of the saved rising hook lists and searches, ranked by the agent's fit
             scores (Creative brief's CB3 criteria, read from the cards), and the top `hooks.shortlist`
             of them: 02_research/hooks_shortlist_vNN.json (issue #8)
    hook_captions  the shortlisted hooks' captions, for the agent to judge: 03_wip/hook_captions_vNN.md
    hooks    the shortlisted hooks, each with the agent's judgement of whether its videos are in the
             category (information, not a gate): 02_research/hooks_candidates_vNN.json and
             hooks_in_category_vNN.json
    compute  growth, position in the sample, bucket and confidence of every mapped trend and kept
             hook, read at one date: 02_research/<stem>_vNN.json/.md and the snapshot for the next
             digest, snapshot_vNN.json (snapshot_<stem>_vNN.json for another stem)
    backtest the stages as of an earlier date, then the new creators in the days after it (rule v3):
             03_wip/backtest_<as_of>_rule_v3_vNN.json/.md, to calibrate TR3 on each category

Definitions (TR2): ref = as-of - lag; recent = (ref - window, ref]; baseline = (ref - window -
baseline, ref - window]; new_recent = creators whose first video is in recent, new_base likewise;
ratio = (new_recent / window) / max(new_base / baseline, 1 / baseline). Numbers are "creators in
TrendsMesh evidence" (a collected sample, not platform totals). A creator is `trends.creator_of`
(ruling F17): a video without one is not counted as a creator, and a trend whose videos carry none
stops growth instead of counting every video as its own creator.

Rule v3 is the only bucket rule (v1 and v2 are not ported); its numbers come from `buckets.*` and
`confidence.*` of the config (`Thresholds`). USE_LANGUAGE is False: `lang_share` is still written
(the original growth rows carry it), but nothing decides on it.

Added to the original files: each growth row's `plugin` (TR4: `sensitive_videos`, the evidence videos
flagged `is_sensitive`; `unattributed_videos`, those with no creator; the trend's `sensitivity_level`),
the growth file's top-level `plugin.no_creator_data` when a hook candidate used only to rank hooks
has no creator data (it counts as 0 new creators and never stops growth; an evaluated trend does
stop), and the snapshot's `pool_ids` (every id the map's searches and the hook candidates returned,
for the weekly digest).

The hooks path differs from the original (issue #8): the original kept a hook only when enough of
its videos carried a category word (matched on word starts), so it fetched every rising hook's
videos and, in a niche, kept none. Here the agent scores every hook candidate for fit from its card,
`hook_fit` keeps the top `hooks.shortlist`, only those are fetched, and `hooks` records the agent's
judgement of their captions as information (issue #3, item 5: no word matching, so any language; a
kept hook's `plugin.use`: `in_category` or `transfer`, with `plugin.use_why`), with its Ad Library verdict from the shortlisted hooks' checks (issue #58,
`research_checks.check_hook_ads`; `plugin.ad_library`, None when not checked). A hook's band and
percentile are its place in the saved rising hook lists (`relative.rising_position` of
`relative.rising_of`, the owner's choice on issue #58: it compares a hook with every rising hook,
where the videos read are only the shortlist's); a hook only a search found has no place and no band.
A run without a saved rising list ranks hooks against the hook candidates whose videos are saved, as
before; those without are listed in the growth file's `plugin.hooks_not_read`. `snapshot_extra` adds keys to the snapshot when it is first written (ruling
F9: `{"rebuilt": true}`), never replaces one; no file is rewritten.
"""

from __future__ import annotations

import json
import re
import statistics as st
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from pathlib import Path

from tm import i18n, manifest, research_map, state, trends
from tm.config import Problem
from tm.stops import AGAIN, Stop
from tm.runfolder import RunFolder

BUCKETS = ["act_now", "still_rising", "too_late", "past_peak"]
LABEL = {"act_now": "Act now", "still_rising": "Still rising", "too_late": "Too late", "past_peak": "Past its peak"}
RULE = "v3"
USE_LANGUAGE = False  # user, 2026-11-04: no evidence-language metric until the API fills `languages`
STEM = "growth"
HOOKS_STEM = "hooks_in_category"
CANDIDATES_STEM = "hooks_candidates"
SHORTLIST_STEM = "hooks_shortlist"
SOURCE_FIT = "tm research hook-fit"
HOOK_LISTS = "list_rising_hook_trend_*.json"
SOURCE_HOOKS = "tm research hooks"
SOURCE_GROWTH = "tm research growth"
SNAPSHOT_KEYS = ("params", "trends", "pool_ids")
NO_CREATOR_LINE = "No creator data (counted as 0 new creators, used only to rank hooks)"
_STEM_OK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


class NoCreators(Stop):
    """A trend's videos carry no creator (F17): growth never counts every video as its own creator."""


def d(s: str) -> date:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


# --- thresholds -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Thresholds:
    """Rule v3's numbers: `buckets.*` and `confidence.*` of the config."""
    act_index: float
    act_min_new: int
    act_last_days: int
    act_median_views: float
    concentrated: float
    rise_index: float
    rise_min_new: int
    rise_last_days: int
    crowded_creators: int
    crowded_age_days: int
    active_days: int
    season_after_days: int
    low_creators: int
    low_top_share: float
    high_creators: int
    high_top_share: float

    @classmethod
    def from_config(cls, cfg: dict) -> "Thresholds":
        cfg = research_map.settings(cfg)
        values = {**cfg["buckets"], **cfg["confidence"]}
        return cls(**{f.name: values[f.name] for f in fields(cls)})


# --- saved files ------------------------------------------------------------------------------

def _versioned(run: RunFolder, names: list[tuple[str, str]], stage: str = trends.RESEARCH) -> int:
    """One NN above every existing version of each (stem, ext), so files written together share it."""
    return max(int(run.next_version(stage, stem, ext).stem.rsplit("_v", 1)[1]) for stem, ext in names)


def _write(run: RunFolder, path: Path, text: str, params: dict, source: str) -> None:
    """Write a file of a stage folder (02_research, 03_wip) and its manifest row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    rel = path.relative_to(run.path)
    manifest.record(run, rel.as_posix(), rel.parts[0], source, params=params)


def snapshot_stem(stem: str) -> str:
    """The snapshot written beside <stem>_vNN.json: snapshot for growth, else snapshot_<stem>."""
    return "snapshot" if stem == STEM else f"snapshot_{stem}"


def snapshot_of(growth: Path, stem: str = STEM) -> Path:
    """The snapshot `compute` wrote with the growth file `growth` (the same NN)."""
    return growth.with_name(snapshot_stem(stem) + growth.name[len(stem):])


def candidates_of(hooks_in_category: Path) -> Path:
    """The hooks_candidates file `hooks` wrote with `hooks_in_category` (the same NN)."""
    return hooks_in_category.with_name(CANDIDATES_STEM + hooks_in_category.name[len(HOOKS_STEM):])


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def category_map(run: RunFolder) -> dict:
    """The latest category map; Stop (what to do) when there is none."""
    path = run.latest(trends.RESEARCH, research_map.STEM, "json")
    if path is None:
        raise Stop("This run has no category map yet. Build it with tm research map first (growth reads "
                   "it); the run continues from the same place.")
    return trends.read(path)


def _need_videos(run: RunFolder, cards: list[dict], what: str) -> None:
    """Stops when a card has no saved video page (an empty answer counts: TrendsMesh had none). On a
    weekly run the fetch plan and the reuse come first (TR8): most videos are copied, not fetched."""
    missing = [c for c in cards if not trends.video_files(run, c["id"])]
    if missing:
        shown = ", ".join(f"{c.get('name')!r} ({c['id']})" for c in missing[:10])
        more = f" and {len(missing) - 10} more" if len(missing) > 10 else ""
        weekly = ("This is a weekly run: run tm research fetch-plan to see which trends to fetch again, and tm "
                  "research reuse to copy the others from the previous run. Then fetch the rest"
                  if state.load(run).previous_run else "Fetch their videos")
        raise Stop(f"These {what} have no saved evidence videos ({len(missing)}): {shown}{more}. {weekly} "
                   "(TrendsMesh get_trend_videos, every page) with collection on, then run this again; the run "
                   "continues from the same place.")


# --- hooks path (TR1) -------------------------------------------------------------------------

def _is_hook(card: object) -> bool:
    return isinstance(card, dict) and card.get("kind") == "hook_trend" and bool(card.get("id"))


def _list_cards(run: RunFolder) -> list[dict]:
    """The cards of the saved rising hook lists, page by page (by file name), as TrendsMesh ranked them."""
    lists = run.path / trends.RESEARCH / "lists"
    files = sorted(f for f in lists.glob(HOOK_LISTS) if f.is_file()) if lists.is_dir() else []
    cards = []
    for f in files:
        cards += trends.items(trends.unwrap(trends.read(f)))
    return cards


def rising_order(run: RunFolder) -> dict[str, int]:
    """Each hook of the saved rising hook lists and its place there, from 0 (the first time it is listed
    counts): TrendsMesh's own ranking of every rising hook, which the hooks' band reads (issue #58)."""
    out: dict[str, int] = {}
    for c in _list_cards(run):
        if _is_hook(c) and c["id"] not in out:
            out[c["id"]] = len(out)
    return out


def hook_cards(run: RunFolder) -> list[dict]:
    """Hook cards of the saved rising hook lists, then of the searches, by file name."""
    cards = _list_cards(run)
    for f in trends.search_files(run):
        cards += trends.search_cards(trends.unwrap(trends.read(f)))
    return [c for c in cards if _is_hook(c)]


def _candidates(run: RunFolder) -> list[dict]:
    """The hook cards, de-duplicated by id (the later card wins, in the first one's place)."""
    return list({c["id"]: c for c in hook_cards(run)}.values())


def _no_hooks() -> Stop:
    return Stop("No hook trend is saved yet. List the rising hooks (TrendsMesh list_trends, sort rising, "
                f"trend_type hook_trend) with collection on, then run the hooks path again; {AGAIN}.")


def _criteria() -> tuple[tuple[str, ...], dict]:
    """Creative brief's CB3 criteria and their default (equal) weights. Imported here: brief_config
    imports seeds, which imports this module."""
    from tm import brief_config
    return brief_config.CRITERIA, dict(brief_config.DEFAULTS["scoring"]["weights"])


def check_hook_fit(run: RunFolder, data: object) -> list[Problem]:
    """Everything wrong in the agent's hook fit scores (issue #8); empty when they hold. One row per
    hook candidate, `{"<id>": {<the seven CB3 criteria>: 1-5, "why": "..."}}`, `why` optional."""
    from tm import brief_research
    criteria, _ = _criteria()
    names = ", ".join(criteria)
    cards = {c["id"]: c for c in _candidates(run)}
    if not cards:
        raise _no_hooks()
    if not isinstance(data, dict) or not data:
        return [Problem("hook_fit", "The fit scores must be one table {\"<hook id>\": {criterion: 1-5}}.",
                        f"Write a row per hook candidate with {names}, then check again.")]
    out = []
    for hid, row in data.items():
        if hid not in cards:
            out.append(Problem(hid, f"{hid} is not a hook candidate of this run (no saved rising hook list or "
                                    "search holds it).", "Score the hooks of the saved lists and searches only."))
            continue
        scores = {k: v for k, v in row.items() if k != "why"} if isinstance(row, dict) else row
        wrong = brief_research.score_problems(scores)
        if isinstance(row, dict) and not isinstance(row.get("why", ""), (str, type(None))):
            wrong.append("why is not a sentence")
        if wrong:
            out.append(Problem(hid, f"{hid} ({cards[hid].get('name')!r}): its scores {'; '.join(wrong)}.",
                               f"Score it 1-5, as a whole number, on {names}; why, if given, is a sentence."))
    missing = [c for hid, c in cards.items() if hid not in data]
    if missing:
        shown = ", ".join(f"{c.get('name')!r} ({c['id']})" for c in missing[:10])
        more = f" and {len(missing) - 10} more" if len(missing) > 10 else ""
        out.append(Problem("hook_fit", f"{len(missing)} hook candidates are not scored: {shown}{more}.",
                           "Score every hook candidate from its card (a hook that fits badly scores low, it is "
                           "never left out)."))
    return out


def hook_fit(run: RunFolder, data: object, cfg: dict, *, fit_file: str | None = None) -> Path:
    """Rank every hook candidate by its weighted fit (Creative brief's CB3 criteria, equal weights) and
    keep the top `hooks.shortlist` as the shortlist, the only hooks whose videos are fetched (issue
    #8). Ties keep the candidates' order (the rising list first: TrendsMesh's own ranking). A
    contradicted hook, or one whose fit is below `hooks.min_fit` (3, neutral), is never shortlisted.
    Writes 02_research/hooks_shortlist_vNN.json and returns it; Stops, writing nothing, when no hook is
    saved or a score is wrong."""
    from tm import brief_research
    cfg = research_map.settings(cfg)
    cards = _candidates(run)
    problems = check_hook_fit(run, data)          # Stops first when no hook is saved
    if problems:
        raise Stop(" ".join(f"{p.what} {p.todo}" for p in problems)
                   + f" Fix the file, save it as a new version and run this again; {AGAIN}.")
    criteria, weights = _criteria()
    totals = brief_research.totals({hid: {c: row[c] for c in criteria} for hid, row in data.items()}, weights)
    order = {c["id"]: i for i, c in enumerate(cards)}
    ranked = sorted(cards, key=lambda c: (-totals[c["id"]], order[c["id"]]))
    size, floor = cfg["hooks"]["shortlist"], cfg["hooks"]["min_fit"]
    live = [c for c in ranked if c.get("status") != "contradicted"]
    short = [c for c in live if totals[c["id"]] >= floor][:size]
    rest = [c for c in live if c not in short]
    out = {"fit_file": fit_file, "criteria": list(criteria), "weights": weights, "shortlist_size": size,
           "min_fit": floor,
           "shortlist": [{"rank": i, "id": c["id"], "name": c.get("name"), "fit": totals[c["id"]],
                          "scores": {k: data[c["id"]][k] for k in criteria}, "why": data[c["id"]].get("why")}
                         for i, c in enumerate(short, 1)],
           "not_shortlisted": [{"id": c["id"], "name": c.get("name"), "fit": totals[c["id"]]} for c in rest],
           "contradicted": [{"id": c["id"], "name": c.get("name"), "fit": totals[c["id"]]}
                            for c in ranked if c.get("status") == "contradicted"]}
    target = run.next_version(trends.RESEARCH, SHORTLIST_STEM, "json")
    _write(run, target, _dump(out), {"shortlist": size, "min_fit": floor, **({"fit_file": fit_file} if fit_file else {})},
           SOURCE_FIT)
    return target


def shortlist(run: RunFolder) -> dict | None:
    """The latest hook shortlist (`hook_fit`), with its run-relative path as `path`; None before one."""
    path = run.latest(trends.RESEARCH, SHORTLIST_STEM, "json")
    return None if path is None else {**trends.read(path), "path": path.relative_to(run.path).as_posix()}


# The agent's judgement of each shortlisted hook (issue #3, item 5, the owner's option b): no word matching,
# which misses inflected words ("makijażu") and languages without spaces. `hook_captions` writes a sheet of
# each shortlisted hook's captions; the agent reads it and records, per hook, whether its videos are about
# the category, how many of the captions read are, and one line on why (03_wip/hook_use_vNN.json, checked
# by `check_hook_use`), and may name a dated event the hook is tied to, in the market language.

CAPTIONS = 40            # the captions of a shortlisted hook the agent reads: its most-viewed videos
CAPTION_CHARS = 200
USE_STEM = "hook_use"
CAPTIONS_STEM = "hook_captions"
SOURCE_CAPTIONS = "tm research hook-captions"
USE_SHAPE = ('{"<hook id>": {"in_category": true|false, "category_videos": <how many of the captions read>, '
             '"why": "<one line>", "event": null|{"name": "<the event, in the market language>", '
             '"date": "YYYY-MM-DD"}}}')


def _shortlisted(run: RunFolder) -> tuple[dict, list[tuple[dict, dict]], list[dict]]:
    """The latest shortlist, its hooks in fit order as (shortlist row, card) and every hook card. Stops
    without a saved hook, without a shortlist, with one made before a hook candidate was saved, or when a
    shortlisted hook has no saved videos."""
    cards = _candidates(run)
    if not cards:
        raise _no_hooks()
    short = shortlist(run)
    if short is None:
        raise Stop("The rising hooks are not ranked yet. Score every hook candidate for fit (03_wip/hook_fit_vNN.json) "
                   f"and run tm research hook-fit, then fetch the shortlist's videos and run this again; {AGAIN}.")
    scored = {r["id"] for r in short["shortlist"] + short["not_shortlisted"] + short["contradicted"]}
    new = [c for c in cards if c["id"] not in scored]
    if new:
        shown = ", ".join(f"{c.get('name')!r} ({c['id']})" for c in new[:10])
        raise Stop(f"{len(new)} hook candidates were saved after the fit scores ({short['path']}): {shown}. Score "
                   f"them too (a new version of the fit file), run tm research hook-fit again, then this; {AGAIN}.")
    by_id = {c["id"]: c for c in cards}
    picked = [(r, by_id[r["id"]]) for r in short["shortlist"] if r["id"] in by_id]
    _need_videos(run, [c for _, c in picked], "shortlisted hooks")
    return short, picked, cards


def caption(video: dict) -> str:
    """A video's caption as the agent reads it: its excerpt, hook text and slot fill, each once, on one line."""
    parts: list[str] = []
    for k in ("excerpt", "hook_text", "slot_fill"):
        text = " ".join(str(video.get(k) or "").split())
        if text and not any(text in p for p in parts):
            parts.append(text)
    out = " · ".join(parts)
    return out if len(out) <= CAPTION_CHARS else out[:CAPTION_CHARS - 1] + "…"


def captions_read(videos: list[dict]) -> list[dict]:
    """The videos of a hook whose captions the agent reads: up to CAPTIONS with a caption, most-viewed first,
    one per caption (a repost of the same words counts once)."""
    out, seen = [], set()
    for v in sorted(videos, key=lambda v: -(v.get("views") or 0)):
        text = caption(v)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(v)
        if len(out) == CAPTIONS:
            break
    return out


def hook_captions(run: RunFolder) -> tuple[Path, dict[str, int]]:
    """03_wip/hook_captions_vNN.md: each shortlisted hook (fit order), its card, and the captions of the
    videos `captions_read` picks, numbered, for the agent's judgement. Returns the file and each hook's
    number of captions. Stops as `hooks` does."""
    short, picked, _ = _shortlisted(run)
    lines = [f"# The shortlisted hooks' captions ({SOURCE_CAPTIONS})", "",
             f"Shortlist: {short['path']}. Up to {CAPTIONS} captions per hook, its most-viewed videos. For each "
             f"hook, record whether its videos are about the category, how many of these captions are, and one "
             f"line on why: 03_wip/{USE_STEM}_vNN.json = {USE_SHAPE}.", ""]
    counts = {}
    for r, c in picked:
        shown = captions_read(trends.load_videos(run, c["id"]))
        counts[c["id"]] = len(shown)
        lines += [f"## {r['rank']}. {c.get('name')} (`{c['id']}`)", "", f"{c.get('what_it_is') or ''}".strip(), "",
                  f"{len(shown)} captions:", ""]
        lines += [f"{i}. {caption(v)}" for i, v in enumerate(shown, 1)] + [""]
    target = run.next_version(WIP, CAPTIONS_STEM, "md")
    _write(run, target, "\n".join(lines), {"shortlist": short["path"], "captions": CAPTIONS}, SOURCE_CAPTIONS)
    return target, counts


def event_problems(event: object) -> list[str]:
    """What is wrong with an event the agent named: null, or {"name": <in the market language>, "date":
    "YYYY-MM-DD", the day of the occurrence the trend is about}."""
    if event is None:
        return []
    if not isinstance(event, dict) or set(event) != {"name", "date"}:
        return ['event is null or {"name": "<the event, in the market language>", "date": "YYYY-MM-DD"}']
    out = []
    if not (isinstance(event["name"], str) and event["name"].strip()):
        out.append("the event's name is empty")
    try:
        date.fromisoformat(event["date"])
    except (TypeError, ValueError):
        out.append(f"the event's date {event['date']!r} is not YYYY-MM-DD")
    return out


def check_hook_use(run: RunFolder, data: object) -> list[Problem]:
    """Everything wrong in the agent's judgement of the shortlisted hooks (`USE_SHAPE`); empty when every
    shortlisted hook has one that holds. Stops as `hooks` does."""
    _, picked, _ = _shortlisted(run)
    wanted = {c["id"]: c for _, c in picked}
    if not isinstance(data, dict) or not data:
        return [Problem("hook_use", f"The judgement must be one table {USE_SHAPE}.",
                        "Read the captions (tm research hook-captions), write a row per shortlisted hook, then "
                        "check again.")]
    out = []
    for hid, row in data.items():
        if hid not in wanted:
            out.append(Problem(hid, f"{hid} is not a hook of the latest shortlist.",
                               "Judge the shortlisted hooks only (tm research hook-captions lists them)."))
            continue
        name = wanted[hid].get("name")
        if not isinstance(row, dict):
            out.append(Problem(hid, f"{hid} ({name!r}) is not {USE_SHAPE}.", "Write it as one object."))
            continue
        read = len(captions_read(trends.load_videos(run, hid)))
        wrong = []
        used, n = row.get("in_category"), row.get("category_videos")
        if not isinstance(used, bool):
            wrong.append("in_category is not true or false")
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= read:
            wrong.append(f"category_videos is not a whole number from 0 to {read} (the captions read)")
        elif isinstance(used, bool) and used != (n > 0):
            wrong.append("in_category is true exactly when at least one caption read is about the category")
        if not (isinstance(row.get("why"), str) and row["why"].strip()):
            wrong.append("why is not one line on why")
        wrong += event_problems(row.get("event"))
        unknown = sorted(set(row) - {"in_category", "category_videos", "why", "event"})
        if unknown:
            wrong.append(f"{', '.join(unknown)} is not a field of the judgement")
        if wrong:
            out.append(Problem(hid, f"{hid} ({name!r}): {'; '.join(wrong)}.", f"Write it as {USE_SHAPE}."))
    missing = [c for hid, c in wanted.items() if hid not in data]
    if missing:
        shown = ", ".join(f"{c.get('name')!r} ({c['id']})" for c in missing)
        out.append(Problem("hook_use", f"{len(missing)} shortlisted hooks have no judgement: {shown}.",
                           "Read each one's captions (tm research hook-captions) and judge it: a hook no category "
                           "video uses is a transfer, never left out."))
    return out


def hooks(run: RunFolder, use: object, cfg: dict, *, use_file: str | None = None) -> Path:
    """The shortlisted hooks (the latest `hook_fit`), in fit order, each with the agent's judgement of its
    videos (`use`, checked by `check_hook_use`): `in_category` marks the hook used in the category, else it
    is a `transfer`; no hook is dropped for it (issue #8). `category_videos` of `videos_checked` are the
    captions the agent read (`captions_read`) and found about the category. Writes hooks_candidates_vNN.json
    (every hook card) and hooks_in_category_vNN.json with one NN; returns the latter. Stops, writing nothing,
    as `_shortlisted` does, when the judgement does not hold, or when the Ad Library checks no longer cover
    the shortlist."""
    short, picked, cards = _shortlisted(run)
    problems = check_hook_use(run, use)
    if problems:
        raise Stop(" ".join(f"{p.what} {p.todo}" for p in problems)
                   + f" Fix the file, save it as a new version and run this again; {AGAIN}.")
    from tm import research_checks                # it imports this module
    verdicts, ads_file = research_checks.hook_verdicts(run)     # issue #58; None: not checked
    kept = []
    for r, c in picked:
        j = use[c["id"]]
        read = len(captions_read(trends.load_videos(run, c["id"])))
        kept.append({"id": c["id"], "kind": "hook_trend", "name": c["name"], "sub_category": "hooks",
                     "group": "hooks", "status": c.get("status"), "reach": c.get("reach"), "since": c.get("since"),
                     "active_for_days": c.get("active_for_days"), "momentum": c.get("momentum"),
                     "what_it_is": c.get("what_it_is"), "category_videos": j["category_videos"],
                     "videos_checked": read,
                     "category_share": round(j["category_videos"] / read, 2) if read else 0,
                     "event": j.get("event"),
                     "plugin": {"fit": r["fit"], "fit_rank": r["rank"], "in_category": j["in_category"],
                                "use": "in_category" if j["in_category"] else "transfer", "why": r.get("why"),
                                "use_why": j["why"].strip(), "ad_library": (verdicts or {}).get(c["id"])}})
    out = {"judgement": use_file, "shortlist": short["path"], "ad_library": ads_file, "kept": kept,
           "not_shortlisted": [{k: r[k] for k in ("id", "name", "fit")} for r in short["not_shortlisted"]]}
    nn = _versioned(run, [(CANDIDATES_STEM, "json"), (HOOKS_STEM, "json")])
    target = run.path / trends.RESEARCH / f"{HOOKS_STEM}_v{nn:02d}.json"
    params = {"shortlist": short["path"], **({"judgement": use_file} if use_file else {}),
              **({"ad_library": ads_file} if ads_file else {})}
    _write(run, candidates_of(target), _dump(cards), params, SOURCE_HOOKS)
    _write(run, target, _dump(out), params, SOURCE_HOOKS)
    return target


# --- growth (TR2) -----------------------------------------------------------------------------

def growth_of(videos: list[dict], ref: date, window: int, baseline: int, *, trend_id: str | None = None) -> dict:
    """The original's `growth_of`, with `trends.creator_of` as the creator in both lookups (F17). Raises
    NoCreators (a ValueError) when the trend has videos and none of them carries a creator."""
    if videos and not any(trends.creator_of(v) for v in videos):
        raise NoCreators(f"TrendsMesh's videos for {trend_id or 'this trend'} carry no creator, so new creators "
                   "can't be counted.")
    first: dict[str, date] = {}
    for v in videos:
        if not v.get("published"):
            continue
        p = d(v["published"])
        if p > ref:
            continue
        who = trends.creator_of(v)
        if who is None:
            continue
        if who not in first or p < first[who]:
            first[who] = p
    if not first:
        return {"creators": 0}
    r0, b0 = ref - timedelta(days=window), ref - timedelta(days=window + baseline)
    new_recent = sum(1 for x in first.values() if r0 < x <= ref)
    new_base = sum(1 for x in first.values() if b0 < x <= r0)
    ratio = (new_recent / window) / max(new_base / baseline, 1 / baseline)
    pub = [d(v["published"]) for v in videos if v.get("published") and d(v["published"]) <= ref]
    known = [v for v in videos if v.get("published") and d(v["published"]) <= ref]
    views = sorted(v.get("views") or 0 for v in known)
    langs = [script_language(v.get("excerpt") or v.get("hook_text") or "") for v in known]
    tagged = [x for x in langs if x]
    # Concentration (v3): share of the evidence views that belong to the single biggest account.
    # Dry run: "Lip combo" 85% from the brand's own account, "Fall almond nails" 98% from one creator.
    by_creator: dict[str, int] = {}
    for v in known:
        who = trends.creator_of(v)
        if who is None:
            continue
        by_creator[who] = by_creator.get(who, 0) + (v.get("views") or 0)
    total_views = sum(by_creator.values())
    top_creator, top_views = max(by_creator.items(), key=lambda kv: kv[1]) if by_creator else (None, 0)
    return {"creators": len(first), "new_recent": new_recent, "new_base": new_base, "ratio": round(ratio, 2),
            "last_seen_days": (ref - max(pub)).days, "age_days": (ref - min(first.values())).days,
            "videos_known": len(pub), "median_views": views[len(views) // 2] if views else 0,
            "views_total": total_views, "top_creator": top_creator,
            "top_creator_share": round(top_views / total_views, 2) if total_views else 0,
            "recent_creators": sorted(c for c, x in first.items() if r0 < x <= ref),
            "lang_share": {k: round(tagged.count(k) / len(tagged), 2) for k in sorted(set(tagged))} if tagged else {}}


_LANG_HINTS = {
    "ru": re.compile(r"[Ѐ-ӿ]"), "ko": re.compile(r"[가-힯]"), "ar": re.compile(r"[؀-ۿ]"),
    "pt": re.compile(r"\b(arrume|comigo|minha|meu|você|não|pra|uma|com a gente)\b", re.I),
    "es": re.compile(r"\b(mi|para|con|que|una|aquí|cómo|hacer|les)\b", re.I),
    "pl": re.compile(r"[ąęłńśźż]|\b(jak|się|nie|już)\b", re.I),
    "en": re.compile(r"\b(the|and|my|your|this|with|for|you|is|it|i)\b", re.I),
}


def script_language(text: str) -> str | None:
    """Rough language of one excerpt (hashtag-only texts return None). Written, never used (USE_LANGUAGE)."""
    text = re.sub(r"[#@]\S+", " ", text)
    for lang, rx in _LANG_HINTS.items():
        if rx.search(text):
            return lang
    return None


# --- stages (TR3, rule v3) --------------------------------------------------------------------

# Seasonal guard (dry run 2026-11-04): a creator-growth window always lags a dated event, so on
# 4 Nov every Halloween trend still looked "act now". A trend tied to an event whose date has passed
# (within `SEASON_AFTER` days) is past its peak whatever its growth says. The agent names a trend's
# event, in the market language and with the date of the occurrence the trend is about, in the map
# review (B3) or a hook's judgement (B4): a row's `event` (issue #3, item 5), in any language.
# EVENTS, English words and their month-day (movable feasts by their earliest date), is read only for
# a row written before that: one without an `event` key, from an older map or hooks file.
EVENTS = {
    "halloween": (10, 31), "costume": (10, 31), "día de los muertos": (11, 2), "dia de los muertos": (11, 2),
    "día de muertos": (11, 2), "dia de muertos": (11, 2), "catrina": (11, 2), "thanksgiving": (11, 22),
    "black friday": (11, 23), "christmas": (12, 25), "new year": (1, 1), "valentine": (2, 14),
    "easter": (3, 22),
}
SEASON_AFTER = 60


def _over(name: str, ev: date, ref: date, season_after: int) -> str | None:
    return f"seasonal: {name} ({ev.isoformat()}) is over" if 0 <= (ref - ev).days <= season_after else None


def event_passed(t: dict, ref: date, season_after: int = SEASON_AFTER) -> str | None:
    """"seasonal: <event> (<date>) is over" when the trend's event passed within `season_after` days of
    `ref`, else None. The event is the row's `event` the agent named ({"name", "date"}, or None: no event);
    a row from before issue #3 has no `event` key and is read against EVENTS."""
    if "event" in t:
        ev = t["event"]
        return _over(ev["name"], date.fromisoformat(ev["date"]), ref, season_after) if ev else None
    text = " ".join([t.get("name") or "", t.get("what_it_is") or ""]).lower()
    for word, (m, day) in EVENTS.items():
        if re.search(rf"\b{re.escape(word)}", text):
            ev = date(ref.year, m, day)
            if ev > ref:
                ev = date(ref.year - 1, m, day)
            over = _over(word, ev, ref, season_after)
            if over:
                return over
    return None


def category_context(rows: list[dict]) -> dict:
    """The sample's own scale (v3): velocity is read against the category, not as a raw count.

    A raw count grows when TrendsMesh simply collects more videos; the index against the
    category's typical trend at the same date does not.
    """
    active = [r["growth"].get("new_recent", 0) for r in rows if r["growth"].get("new_recent", 0) > 0]
    creators = set()
    for r in rows:
        creators |= set(r["growth"].get("recent_creators", []))
    return {"median_new": st.median(active) if active else 1, "trends_active": len(active),
            "creators_active": len(creators), "trends": len(rows)}


def _band(pct: float) -> str:
    return "top 10%" if pct >= 0.9 else "top 25%" if pct >= 0.75 else "top half" if pct >= 0.5 else "lower half"


def relative(g: dict, ctx: dict, pool: list[int]) -> dict:
    n = g.get("new_recent", 0)
    below = sum(1 for x in pool if x < n)
    pct = below / len(pool) if pool else 0
    return {"velocity_index": round(n / ctx["median_new"], 1) if ctx["median_new"] else 0,
            "percentile": round(pct, 2), "band": _band(pct)}


def rising_place(rel: dict, trend_id: str, order: dict[str, int]) -> dict:
    """`rel` with a hook's band and percentile read from its place among every rising hook TrendsMesh
    lists (`order`, from `rising_order`), not among the hooks whose videos were read: the owner's choice
    on issue #58. `rising_position` counts from 1; a hook the lists don't hold (a search found it) has
    None and no band. The velocity index, which the stage reads, is kept."""
    n, pos = len(order), order.get(trend_id)
    out = {"velocity_index": rel["velocity_index"], "rising_position": None if pos is None else pos + 1,
           "rising_of": n}
    if pos is not None:
        pct = (n - 1 - pos) / n                 # the share of the listed hooks below it, as `relative`
        out |= {"percentile": round(pct, 2), "band": _band(pct)}
    return out


def confidence(g: dict, status: str | None, th: Thresholds) -> tuple[str, str]:
    if g.get("creators", 0) < th.low_creators:
        return "low", f"only {g.get('creators', 0)} creators in evidence"
    if g.get("top_creator_share", 0) > th.low_top_share:
        return "low", "views come mostly from one account"
    if g["creators"] >= th.high_creators and g.get("top_creator_share", 1) <= th.high_top_share and status == "confirmed":
        return "high", "broad creator base, no dominant account, confirmed"
    return "medium", "some limits: see the risk line"


def bucket(g: dict, status: str | None, seasonal_over: str | None, rel: dict | None, th: Thresholds) -> str:
    """TR3 rule v3: velocity read against the category (index vs the typical active trend at the same
    date) and a concentration gate (one account above `concentrated` of the evidence views is not
    spreading). `rel` is None only for a trend without creators, which is past its peak."""
    if not g.get("creators") or seasonal_over or rel is None:
        return "past_peak"
    crowded = g["creators"] >= th.crowded_creators and g["age_days"] >= th.crowded_age_days
    concentrated = g.get("top_creator_share", 0) > th.concentrated
    if (rel["velocity_index"] >= th.act_index and g["new_recent"] >= th.act_min_new
            and g["last_seen_days"] <= th.act_last_days and g.get("median_views", 0) >= th.act_median_views
            and not crowded and not concentrated and status != "contradicted"):
        return "act_now"
    if rel["velocity_index"] >= th.rise_index and g["new_recent"] >= th.rise_min_new and g["last_seen_days"] <= th.rise_last_days:
        return "too_late" if crowded else "still_rising"
    return "too_late" if g["last_seen_days"] <= th.active_days else "past_peak"


# --- evaluate and compute ---------------------------------------------------------------------

def _inputs(run: RunFolder) -> tuple[dict, list[dict], list[dict] | None]:
    """The latest map, the trends to evaluate (map kept, then kept hooks), the hook candidates."""
    cmap = category_map(run)
    rows = list(cmap.get("kept") or [])
    path = run.latest(trends.RESEARCH, HOOKS_STEM, "json")
    lists = run.path / trends.RESEARCH / "lists"
    if path is None and lists.is_dir() and any(f.is_file() for f in lists.glob(HOOK_LISTS)):
        raise Stop("This run has saved rising hook lists but no hooks path yet, so its hooks would be left out. Run "
                   "the hooks path (tm research hook-captions, then tm research hooks --file) first, then this "
                   "again; the run continues from the same place.")
    if path is not None:              # a hook the map already keeps is not listed twice
        kept = {r.get("id"): r for r in trends.read(path)["kept"]}
        mapped = {r.get("id") for r in rows}
        # ... but the map's row carries the hooks path's fit, use and category videos (issue #58)
        rows = [{**r, "plugin": {**(r.get("plugin") or {}), **(kept[r["id"]].get("plugin") or {}),
                                 "category_videos": kept[r["id"]].get("category_videos"),
                                 "videos_checked": kept[r["id"]].get("videos_checked")},
                 **({"event": kept[r["id"]]["event"]} if kept[r["id"]].get("event") and not r.get("event") else {})}
                if r.get("id") in kept else r for r in rows]
        rows += [r for hid, r in kept.items() if hid not in mapped]
    path = run.latest(trends.RESEARCH, CANDIDATES_STEM, "json")
    candidates = None if path is None else [c for c in trends.items(trends.read(path))
                                            if isinstance(c, dict) and c.get("kind") == "hook_trend"]
    return cmap, rows, candidates


def _pool_new(run: RunFolder, card: dict, ref: date, window: int, baseline: int, no_creator: list[str]) -> int:
    """A hook candidate's new creators for the hooks pool. A candidate used only to rank hooks whose
    videos carry no creator counts as 0 and is listed in `no_creator` (ruling, Task 9 review): one
    TrendsMesh data gap never blocks the category. An evaluated trend still stops (in `_evaluate`)."""
    try:
        return growth_of(trends.load_videos(run, card["id"]), ref, window, baseline,
                         trend_id=card["id"]).get("new_recent", 0)
    except NoCreators:
        no_creator.append(card["id"])
        return 0


def _evaluate(run: RunFolder, ref: date, cfg: dict) -> tuple[list[dict], dict, dict, list[dict] | None, list[str]]:
    """Rows, category context, the map, the hook candidates, and the pool-only hook candidates whose
    videos carry no creator."""
    cfg = research_map.settings(cfg)
    th = Thresholds.from_config(cfg)
    window, baseline = cfg["growth"]["window_days"], cfg["growth"]["baseline_days"]
    cmap, trend_rows, candidates = _inputs(run)
    _need_videos(run, trend_rows, "trends of the map and the hooks path")
    levels = {c["id"]: c.get("sensitivity_level") for c in candidates or []}
    rows = []
    for t in trend_rows:
        vids = trends.load_videos(run, t["id"])
        rows.append({**t, "growth": growth_of(vids, ref, window, baseline, trend_id=t["id"]),
                     "seasonal_over": event_passed(t, ref, th.season_after_days),
                     "platforms": sorted({v.get("platform") for v in vids if v.get("platform")}),
                     "plugin": {**(t.get("plugin") or {}), "sensitive_videos": sum(v.get("is_sensitive") is True for v in vids),
                                "unattributed_videos": sum(trends.creator_of(v) is None for v in vids),
                                "sensitivity_level": t.get("sensitivity_level", levels.get(t["id"]))}})
    ctx = category_context(rows)
    pools: dict[bool, list[int]] = {}
    for r in rows:
        pools.setdefault(r.get("kind") == "hook_trend", []).append(r["growth"].get("new_recent", 0))
    # Hooks are opening structures used across categories, so a hook is ranked against the rising
    # hooks (the hook candidates), not against the few that reach this category (dry run: 5 of 101).
    # Only the shortlisted hooks' videos are fetched (issue #8): the pool is the candidates read.
    no_creator: list[str] = []
    if candidates is not None:    # an evaluated hook without creators has stopped above already
        pools[True] = [_pool_new(run, c, ref, window, baseline, no_creator) for c in candidates
                       if trends.video_files(run, c["id"])]
        ctx["hooks_pool"] = len(pools[True])
    # Issue #58: with a saved rising list, a hook's band is its place there, among every rising hook.
    order = rising_order(run)
    if order:
        ctx["hooks_rising"] = len(order)
    for r in rows:
        g = r["growth"]
        hook = r.get("kind") == "hook_trend"
        r["relative"] = relative(g, ctx, pools[hook]) if g.get("creators") else None
        if hook and order and r["relative"] is not None:
            r["relative"] = rising_place(r["relative"], r["id"], order)
        r["bucket"] = bucket(g, r.get("status"), r["seasonal_over"], r["relative"], th)
        r["confidence"], r["confidence_why"] = confidence(g, r.get("status"), th) if g.get("creators") else ("low", "no evidence")
    return rows, ctx, cmap, candidates, no_creator


def evaluate(run: RunFolder, ref: date, cfg: dict) -> tuple[list[dict], dict]:
    """Growth, relative position, bucket and confidence for every trend, all read at `ref`."""
    rows, ctx, _, _, _ = _evaluate(run, ref, cfg)
    return rows, ctx


def _markdown(rows: list[dict], ctx: dict, as_of: str, ref: date, window: int, baseline: int,
              no_creator: list[str]) -> str:
    lines = [f"# Growth and buckets, rule {RULE} (as of {as_of}, reference {ref}, window {window} d vs {baseline} d before)", "",
             f"Category sample in the window: {ctx['creators_active']} creators active across {ctx['trends_active']} of {ctx['trends']} trends; "
             f"typical active trend = {ctx['median_new']} new creators. Index = new creators ÷ typical.", ""]
    if no_creator:
        lines += [f"{NO_CREATOR_LINE}: {', '.join(no_creator)}.", ""]
    for b in BUCKETS:
        sel = [r for r in rows if r["bucket"] == b]
        lines += [f"## {LABEL[b]} ({len(sel)})", "", "| Group | Trend | Kind | Band | Index | New / base | Last (d) | Top account share | Median views | Confidence | Note |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sel:
            g, rel = r["growth"], r.get("relative") or {}
            lines.append(f"| {r.get('group')} | {r['name']} | {r['kind'].replace('_trend', '')} | {rel.get('band', '—')} | {rel.get('velocity_index', '—')} | "
                         f"{g.get('new_recent', 0)} / {g.get('new_base', 0)} | {g.get('last_seen_days', '—')} | {g.get('top_creator_share', '—')} | {g.get('median_views', '—')} | {r['confidence']} | {r.get('seasonal_over') or ''} |")
        lines.append("")
    return "\n".join(lines)


def _pool_ids(cmap: dict, candidates: list[dict] | None) -> list[str]:
    ids = cmap.get("pool_ids")
    if not isinstance(ids, list):           # a map written before pool_ids: its kept and dropped
        ids = [r.get("id") for r in (cmap.get("kept") or []) + (cmap.get("dropped") or [])]
    return sorted({i for i in ids if i} | {c["id"] for c in candidates or []})


def compute(run: RunFolder, as_of: date, cfg: dict, *, stem: str = STEM, snapshot_extra: dict | None = None) -> Path:
    """The original's `cmd_compute`: the growth table of every trend as of `as_of` (ref = as_of -
    `growth.lag_days`), sorted by bucket then index, written as <stem>_vNN.json/.md, and its snapshot
    as snapshot_vNN.json (snapshot_<stem>_vNN.json for another stem), all with one NN. Returns the
    growth JSON. Stops, writing nothing, on an evaluated trend (the map's, the kept hooks) without saved
    videos or whose videos carry no creator; a hook candidate without videos is left out of the hooks'
    pool and listed in `plugin.hooks_not_read`."""
    if not _STEM_OK.fullmatch(stem):
        raise ValueError(f"{stem!r} is not a file name stem: use letters, digits, '_', '-' and '.'.")
    if stem != STEM and not stem.startswith(STEM + "_"):
        raise ValueError(f"{stem!r} must start with {STEM}_ (or be {STEM}), so it never takes another file's name.")
    clash = sorted(set(snapshot_extra or {}) & set(SNAPSHOT_KEYS))
    if clash:
        raise ValueError(f"snapshot_extra may only add keys, never replace the snapshot's {', '.join(clash)}.")
    cfg = research_map.settings(cfg)
    lag, window, baseline = (cfg["growth"][k] for k in ("lag_days", "window_days", "baseline_days"))
    ref = as_of - timedelta(days=lag)
    rows, ctx, cmap, candidates, no_creator = _evaluate(run, ref, cfg)
    order = {b: i for i, b in enumerate(BUCKETS)}
    rows.sort(key=lambda r: (order[r["bucket"]], -((r.get("relative") or {}).get("velocity_index") or 0)))
    meta = {"as_of": as_of.isoformat(), "ref": ref.isoformat(), "lag": lag, "window": window, "baseline": baseline,
            "rule": RULE, "market_lang": i18n.languages_of(cfg).market, "category": ctx}
    # TR8: every run keeps a compact snapshot for the next digest.
    snap = {"params": meta, "trends": {r["id"]: {"name": r["name"], "kind": r.get("kind"), "group": r.get("group"),
                                                 "bucket": r["bucket"], "confidence": r["confidence"],
                                                 "growth": {k: r["growth"].get(k) for k in ("creators", "new_recent", "last_seen_days", "median_views", "views_total", "top_creator_share")},
                                                 "relative": r.get("relative")} for r in rows},
            "pool_ids": _pool_ids(cmap, candidates), **(snapshot_extra or {})}
    nn = _versioned(run, [(stem, "json"), (stem, "md"), (snapshot_stem(stem), "json")])
    params = {"as_of": meta["as_of"], "lag": lag, "window": window, "baseline": baseline, "rule": RULE}
    target = run.path / trends.RESEARCH / f"{stem}_v{nn:02d}.json"
    not_read = [c["id"] for c in candidates or [] if not trends.video_files(run, c["id"])]
    plugin = {**({"no_creator_data": no_creator} if no_creator else {}),
              **({"hooks_not_read": not_read} if not_read else {})}
    out = {"params": meta, "trends": rows, **({"plugin": plugin} if plugin else {})}
    _write(run, target, _dump(out), params, SOURCE_GROWTH)
    _write(run, snapshot_of(target, stem), _dump(snap), params, SOURCE_GROWTH)
    _write(run, target.with_suffix(".md"), _markdown(rows, ctx, meta["as_of"], ref, window, baseline, no_creator),
           params, SOURCE_GROWTH)
    return target


# --- backtest (TR3 calibration, TR9) ----------------------------------------------------------

WIP = "03_wip"
SOURCE_BACKTEST = "tm research backtest"


def backtest_stem(as_of: date) -> str:
    return f"backtest_{as_of.isoformat()}_rule_{RULE}"


def backtest(run: RunFolder, as_of: date, cfg: dict, *, horizon: int = 14) -> Path:
    """The original's `cmd_backtest` with rule v3: the stages computed with the videos known by the
    reference date (as_of - `growth.lag_days`), then the outcome, the new creators in the next
    `horizon` days, per stage. A creator is `trends.creator_of` (F17); hook candidates without
    creator data are listed as in `compute`. Writes
    03_wip/backtest_<as_of>_rule_v3_vNN.json and .md with one NN; returns the JSON."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError(f"The horizon {horizon!r} is not a number of days: use a whole number from 1.")
    cfg = research_map.settings(cfg)
    lag, window, baseline = (cfg["growth"][k] for k in ("lag_days", "window_days", "baseline_days"))
    ref = as_of - timedelta(days=lag)
    evaluated, _, _, _, no_creator = _evaluate(run, ref, cfg)
    rows = []
    for t in evaluated:
        g = t["growth"]
        if not g.get("creators"):
            continue
        dated = [(trends.creator_of(v), d(v["published"])) for v in trends.load_videos(run, t["id"]) if v.get("published")]
        known_before = {who for who, p in dated if who and p <= ref}
        new_after = len({who for who, p in dated if who and ref < p <= ref + timedelta(days=horizon)} - known_before)
        rows.append({"id": t["id"], "name": t["name"], "bucket": t["bucket"], "growth_then": g, "relative_then": t["relative"],
                     "new_creators_after": new_after})
    summary = {}
    for b in BUCKETS:
        sel = [r["new_creators_after"] for r in rows if r["bucket"] == b]
        summary[b] = {"n": len(sel), "share_with_new_creators": round(sum(x > 0 for x in sel) / len(sel), 2) if sel else None,
                      "share_with_3plus": round(sum(x >= 3 for x in sel) / len(sel), 2) if sel else None,
                      "median_new": st.median(sel) if sel else None, "mean_new": round(st.mean(sel), 1) if sel else None}
    md = [f"# Backtest rule {RULE}: buckets as of {ref} (videos known by then), outcome = new creators in the next {horizon} days", "",
          "| Bucket then | Trends | Share with ≥1 new creator after | Share with ≥3 | Median new | Mean new |", "|---|---|---|---|---|---|"]
    for b in BUCKETS:
        s = summary[b]
        md.append(f"| {LABEL[b]} | {s['n']} | {s['share_with_new_creators']} | {s['share_with_3plus']} | {s['median_new']} | {s['mean_new']} |")
    if no_creator:
        md += ["", f"{NO_CREATOR_LINE}: {', '.join(no_creator)}."]
    md += ["", "Caveat: evidence is a collected sample; videos collected after the reference date but published before it are counted as known then (no collection timestamps in the public API)."]
    stem = backtest_stem(as_of)
    nn = _versioned(run, [(stem, "json"), (stem, "md")], WIP)
    target = run.path / WIP / f"{stem}_v{nn:02d}.json"
    params = {"as_of": as_of.isoformat(), "horizon": horizon, "lag": lag, "window": window, "baseline": baseline, "rule": RULE}
    _write(run, target, _dump({"as_of": as_of.isoformat(), "ref": ref.isoformat(), "horizon": horizon, "rule": RULE,
                               "summary": summary, "rows": rows,
                               **({"plugin": {"no_creator_data": no_creator}} if no_creator else {})}),
           params, SOURCE_BACKTEST)
    _write(run, target.with_suffix(".md"), "\n".join(md) + "\n", params, SOURCE_BACKTEST)
    return target
