"""The category map (TR1): the handoff's tools/pb4/category_map.py `build`, ported to the run's saved
TrendsMesh searches (`tm.trends`) instead of the original's REST calls.

    search_status  per saved search: results, relevant (match >= trends.min_match), split
                   (relevant < trends.min_relevant), depth (from the split file)
    build          one map from every saved search, the split file and the agent's review:
                   02_research/category_map_vNN.json and .md
    map_change     how much of the map is new since the previous run's (V26)

The split is the agent's (B1): `03_wip/split_vNN.json` = `{"root", "queries": [{"query", "parent",
"depth", "source"}]}`. A search belongs to a query by the `_input.about` saved with it, never by its
file name (names are capped and hashed). The agent's relevance review (G1) is `03_wip/map_review_vNN.json`
= `{"drop": {name: reason}, "retag": {name: sub_category}, "events": {name: {"name", "date"}}}`. `events`
(issue #3, item 5) names each kept trend's dated event in the market language, with the date of the
occurrence the trend is about; a review with it gives every kept row an `event` (None: no event), which
growth's seasonal guard reads. A review without it (written before) leaves the rows without one.

Added to the original map: `pool_ids` (every trend id the searches returned, for the weekly digest) and
`weak_match` (V7: when the map stays thin after the last split, the five closest trends below the
threshold, marked "weak match", so the page never says there are no trends in the category).
"""

from __future__ import annotations

import json
from pathlib import Path

from tm import config, manifest, research_config, trends
from tm.runfolder import RunFolder
from tm.stops import Stop

STEM = "category_map"
SPLIT_STEM = "split"
PREVIOUS = Path("00_raw") / "prev_category_map.json"
SOURCES = ("seed", "closest_names", "common_sub_areas", "list_topics")
WEAK = "weak match"
WEAK_COUNT = 5
SOURCE = "tm research map"


def settings(cfg: dict) -> dict:
    """The config with every default filled in (a test or an old config may leave keys out)."""
    return config._merge(research_config.defaults(), cfg or {})


def _depth_rule(max_depth: int) -> str:
    return f"TR1 stops splitting at depth {max_depth}: a thin leaf means little coverage"


# --- saved searches ---------------------------------------------------------------------------

def key(query: str) -> str:
    """How a query is matched between the split file, the saved searches and the review: "Nail art "
    in the split is the saved "nail art"."""
    return query.strip().casefold()


def searches(run: RunFolder) -> dict[str, dict]:
    """query -> {"file": its first file's name, "scores": {id: best match}}, in file order. A query
    searched again, or over more pages, or spelt with other capitals, is one query (as first saved):
    its cards are merged by id."""
    out: dict[str, dict] = {}
    names: dict[str, str] = {}
    for f in trends.search_files(run):
        data = trends.read(f)
        query = trends.query_of(data, f)
        entry = out.setdefault(names.setdefault(key(query), query), {"file": f.name, "scores": {}})
        for card in trends.search_cards(trends.unwrap(data)):
            if card.get("id"):
                entry["scores"][card["id"]] = max(entry["scores"].get(card["id"], 0.0), trends.match_score(card))
    return out


def latest_split(run: RunFolder) -> dict | None:
    """The latest 03_wip/split_vNN.json, else None (before the first split)."""
    path = run.latest("03_wip", SPLIT_STEM, "json")
    return trends.read(path) if path else None


# --- the split file ---------------------------------------------------------------------------

def split_problems(split: object, cfg: dict) -> list[str]:
    """What is wrong with a split file: its shape, a query listed twice, and a query deeper than
    `trends.max_split_depth`. A query's depth is its parent's plus one when the parent is in the
    split, else as written."""
    max_depth = settings(cfg)["trends"]["max_split_depth"]
    if not isinstance(split, dict) or not isinstance(split.get("root"), str) or not split["root"].strip():
        return ["The split file names no root: it is {\"root\": <the category phrase>, \"queries\": [...]}."]
    rows = split.get("queries")
    if not isinstance(rows, list):
        return ["The split file's queries must be a list of {query, parent, depth, source}."]
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("query"), str) or not row["query"].strip():
            out.append(f"{row!r} in the split file has no query.")
        elif key(row["query"]) in seen:
            out.append(f"{row['query']!r} is in the split file twice: keep one row for it.")
        elif not (row.get("parent") is None or isinstance(row["parent"], str)):
            out.append(f"{row['query']!r} in the split file has a parent that is not a query: {row['parent']!r}.")
        elif isinstance(row.get("depth"), bool) or not isinstance(row.get("depth"), int) or row["depth"] < 0:
            out.append(f"{row['query']!r} in the split file has no depth (0 for a seed, 1 or 2 below it).")
        elif row.get("source") not in SOURCES:
            out.append(f"{row['query']!r} in the split file has the source {row.get('source')!r}; it is one of "
                       f"{', '.join(SOURCES)}.")
        if isinstance(row, dict) and isinstance(row.get("query"), str):
            seen.add(key(row["query"]))
    if out:
        return out
    found = depths(split)
    for row in rows:
        depth = found[key(row["query"])]
        if depth is None:
            out.append(f"{row['query']!r} in the split file is its own ancestor: correct its parent.")
        elif depth > max_depth:
            out.append(f"{row['query']!r} is at depth {depth}, below {row.get('parent')!r}. {_depth_rule(max_depth)}. "
                       "Leave it out of the split file; its parent stays a thin leaf.")
    return out


def depths(split: dict) -> dict[str, int | None]:
    """key(query) -> depth: the parent's depth plus one when the parent is in the split, else the
    depth written (a parent that was not searched itself, the reference run's "hair"). None in a parent cycle."""
    rows = {key(r["query"]): r for r in split["queries"]}
    out: dict[str, int | None] = {}

    def depth(query: str, seen: tuple[str, ...]) -> int | None:
        if query in out:
            return out[query]
        if query in seen:
            return None
        parent = rows[query].get("parent")
        if parent is not None and key(parent) in rows:
            above = depth(key(parent), (*seen, query))
            return None if above is None else above + 1
        return rows[query]["depth"]

    for query in rows:
        out[query] = depth(query, ())
    return out


def search_problems(run: RunFolder, cfg: dict) -> list[str]:
    """The latest split file's problems (none before the first split). Queries not searched yet are
    not problems: `to_search` lists them."""
    split = latest_split(run)
    return [] if split is None else split_problems(split, cfg)


def to_search(run: RunFolder, cfg: dict) -> list[str]:
    """The queries still to search: those of the latest split file with no saved search (matched by
    `_input.about`, see `key`), else, before the first split, the category phrase and seeds."""
    split = latest_split(run)
    if split is not None and not split_problems(split, cfg):
        wanted = [r["query"] for r in split["queries"]]
    else:
        wanted = _seeds(settings(cfg))
    saved = {key(q) for q in searches(run)}
    return [q for q in wanted if key(q) not in saved]


def _seeds(cfg: dict) -> list[str]:
    category = cfg.get("category") or {}
    return [q for q in [category.get("phrase"), *(category.get("seeds") or [])] if isinstance(q, str) and q.strip()]


def _unsearched(split: dict, saved: dict[str, dict]) -> list[str]:
    keys = {key(q) for q in saved}
    return [f"{row['query']!r} is in the split file but has no saved search. Search it with collection on "
            "(tm trends collect on), or take it out of the split file." for row in split["queries"]
            if key(row["query"]) not in keys]


# --- search status ----------------------------------------------------------------------------

def search_status(run: RunFolder, cfg: dict) -> list[dict]:
    """Per saved search: `{query, results, relevant, split, depth}`. Relevant = match >=
    `trends.min_match`; split = relevant < `trends.min_relevant` (TR1). The depth comes from the
    latest split file; before one exists, the category phrase and seeds are at 0, others None."""
    cfg = settings(cfg)
    min_match, min_relevant = cfg["trends"]["min_match"], cfg["trends"]["min_relevant"]
    split = latest_split(run)
    if split is not None and not split_problems(split, cfg):
        known = depths(split)
    else:
        known = {key(q): 0 for q in _seeds(cfg)}
    rows = []
    for query, entry in searches(run).items():
        relevant = sum(score >= min_match for score in entry["scores"].values())
        rows.append({"query": query, "results": len(entry["scores"]), "relevant": relevant,
                     "split": relevant < min_relevant, "depth": known.get(key(query))})
    return rows


# --- the map ----------------------------------------------------------------------------------

def _record(tid: str, entry: dict, query: str) -> dict:
    """The original's row for one trend, its sub-category being `query`."""
    card = entry["card"]
    return {"id": tid, "kind": card.get("kind"), "name": card.get("name"), "sub_category": query,
            "match": entry["found_by"][query], "found_by": entry["found_by"], "status": card.get("status"),
            "reach": card.get("reach"), "since": card.get("since"),
            "active_for_days": card.get("active_for_days"), "momentum": card.get("momentum"),
            "sensitivity_level": card.get("sensitivity_level"), "what_it_is": card.get("what_it_is"),
            "seasonal": trends.seasonal_tag(card)}


def _reasons(card: dict, exclude: list[str]) -> list[str]:
    reasons = trends.noise_reasons(card, exclude)
    if card.get("status") == "contradicted":
        reasons.append("status contradicted (TR4)")
    return reasons


def _review(review: object) -> tuple[dict, dict, dict | None]:
    """The review's drops, re-tags and events (None: a review without `events`, written before issue #3)."""
    if review is None:
        return {}, {}, None
    drops = review.get("drop", {}) if isinstance(review, dict) else None
    retags = review.get("retag", {}) if isinstance(review, dict) else None
    for part in (drops, retags):
        if not isinstance(part, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in part.items()):
            raise Stop("The review file is {\"drop\": {trend name: reason}, \"retag\": {trend name: "
                       "sub-category}, \"events\": {trend name: {\"name\": event, \"date\": YYYY-MM-DD}}}; correct "
                       "it, save it as a new map_review_vNN.json and build the map again. The run continues from the "
                       "same place.")
    events = review.get("events")
    if events is None:
        return drops, retags, None
    from tm import research_growth            # it imports this module
    wrong = ([] if isinstance(events, dict) else ["events is not one table {trend name: event}"]) or [
        f"{name!r}: {'; '.join(p)}" for name, ev in events.items()
        if (p := (["it names no event: leave the trend out of events"] if ev is None
                  else research_growth.event_problems(ev)))]
    if wrong:
        raise Stop("The review's events do not hold: " + "; ".join(wrong) + ". Each is {\"name\": <the event, in "
                   "the market language>, \"date\": \"YYYY-MM-DD\", the day of the occurrence the trend is about}. "
                   "Correct it, save it as a new map_review_vNN.json and build the map again. The run continues "
                   "from the same place.")
    return drops, retags, events


def _thin(split: dict, saved: dict[str, dict], cfg: dict) -> bool:
    """Every leaf of the split (a query no other query names as parent) is thin and may not be split
    again: the expansion is spent (TR1, V7)."""
    min_match, min_relevant = cfg["trends"]["min_match"], cfg["trends"]["min_relevant"]
    parents = {key(r["parent"]) for r in split["queries"] if r.get("parent") is not None}
    depth = depths(split)
    scores = {key(q): entry["scores"] for q, entry in saved.items()}
    leaves = [key(r["query"]) for r in split["queries"] if key(r["query"]) not in parents]
    return bool(leaves) and all(
        depth[q] >= cfg["trends"]["max_split_depth"]
        and sum(s >= min_match for s in scores[q].values()) < min_relevant for q in leaves)


def build(run: RunFolder, split: dict, review: dict | None, cfg: dict) -> dict:
    """The original's `cmd_build` over the run's saved searches: writes 02_research/category_map_vNN.json
    and .md (the same NN) and returns the map. Refuses, writing nothing, a split file with problems,
    a split query with no saved search, and review names no saved search returned."""
    cfg = settings(cfg)
    problems = split_problems(split, cfg)
    if problems:
        raise Stop(" ".join(problems) + " Fix the split file, save it as a new split_vNN.json and build the map again; "
                   "the run continues from the same place.")
    saved = searches(run)
    if not saved:
        raise Stop("This run has no saved TrendsMesh search yet, so there is nothing to map. Search the "
                   "category phrase with collection on, then build the map; the run continues from the "
                   "same place.")
    problems = _unsearched(split, saved)
    if problems:
        raise Stop(" ".join(problems) + " The run continues from the same place.")
    drops, retags, events = _review(review)
    root = split["root"]
    rk = key(root)
    min_match, min_relevant = cfg["trends"]["min_match"], cfg["trends"]["min_relevant"]
    exclude = [w.strip() for w in cfg["trends"]["exclude_terms"] if w.strip()]
    parents = {key(r["query"]): r.get("parent") for r in split["queries"]}
    pool = trends.pool(run)
    missing = [n for n in [*drops, *retags, *(events or {})] if n not in {e["card"].get("name") for e in pool.values()}]
    if missing:
        raise Stop(f"The review names {', '.join(map(repr, missing))}, which no saved search returned, so "
                   "the map was not built. Copy the names exactly from the map, write the review again as "
                   "a new map_review_vNN.json, and build the map again. A name carried over from last week "
                   "whose trend has left the searches can be removed from the review file. The run "
                   "continues from the same place.")

    queries = []
    for query, entry in saved.items():
        queries.append({"query": query, "parent": parents.get(key(query), None if key(query) == rk else root),
                        "results": len(entry["scores"]),
                        "relevant": sum(s >= min_match for s in entry["scores"].values()), "file": entry["file"]})
    kept, dropped, below = [], [], []
    for tid, entry in pool.items():
        best_q, _ = max(entry["found_by"].items(),
                        key=lambda kv: (key(kv[0]) != rk, kv[1]) if kv[1] >= min_match else (False, -1))
        if entry["found_by"][best_q] < min_match:
            below.append((tid, entry))
            continue
        rec = _record(tid, entry, best_q)
        reasons = _reasons(entry["card"], exclude)
        (dropped if reasons else kept).append({**rec, **({"dropped_because": reasons} if reasons else {})})
    # Agent relevance review (G1): the match threshold alone lets off-category trends in (dry run
    # 2026-11-04: "Dementia in family life" matched "anti-aging" at 41).
    still = []
    for r in kept:
        if r["name"] in drops:
            dropped.append({**r, "dropped_because": [f"agent review: {drops[r['name']]}"]})
            continue
        if r["name"] in retags:
            r["sub_category_search"] = r["sub_category"]
            r["sub_category"] = retags[r["name"]]
        if events is not None:                 # issue #3: the event the agent named, in any language
            r["event"] = events.get(r["name"])
        still.append(r)
    kept = still

    def group(sub_category: str) -> str:
        parent = parents.get(key(sub_category))
        return parent if parent and key(parent) != rk else sub_category

    for r in kept:
        r["group"] = group(r["sub_category"])
    kept.sort(key=lambda r: (r["group"], r["sub_category"], -r["match"]))

    weak = []
    if not kept or _thin(split, saved, cfg):
        for tid, entry in below:
            if (max(entry["found_by"].values()) <= 0 or entry["card"].get("name") in drops
                    or _reasons(entry["card"], exclude)):
                continue                       # score 0 is no match at all; noise is never a weak match
            best_q, _ = max(entry["found_by"].items(), key=lambda kv: (kv[1], key(kv[0]) != rk))
            weak.append({**_record(tid, entry, best_q), "group": group(best_q), "label": WEAK})
        weak = sorted(weak, key=lambda r: -r["match"])[:WEAK_COUNT]

    out = {"root": root, "min_match": min_match, "min_relevant": min_relevant, "queries": queries,
           "kept": kept, "dropped": dropped, "below_threshold": len(below), "weak_match": weak,
           "pool_ids": sorted(pool)}
    _write(run, out, {"root": root, "min_match": min_match, "min_relevant": min_relevant,
                      "exclude_terms": exclude, "reviewed": review is not None})
    return out


def _seasonal(r: dict) -> str:
    """A kept row's Seasonal cell: the event the review named with its date, else the card's seasonal tag."""
    ev = r.get("event")
    return f"{ev['name']} ({ev['date']})" if ev else r.get("seasonal") or ""


def _markdown(m: dict) -> str:
    """The original's category_map.md, plus the weak matches of a thin map."""
    kept, dropped = m["kept"], m["dropped"]
    lines = [f"# Category map: {m['root']}", "",
             f"Relevant = match score >= {m['min_match']:g}. Split rule: fewer than {m['min_relevant']} relevant "
             "-> split (TR1).", "",
             "| Query | Parent | Relevant / results | Kept in map (primary sub-category) |", "|---|---|---|---|"]
    for q in m["queries"]:
        n = sum(1 for r in kept if r["sub_category"] == q["query"])
        lines.append(f"| {q['query']} | {q['parent'] or '—'} | {q['relevant']} / {q['results']} | {n} |")
    lines += ["", f"**Kept:** {len(kept)} trends. **Dropped (noise, contradicted):** {len(dropped)}. "
              f"**Below the match threshold everywhere:** {m['below_threshold']}.", "", "## Kept", "",
              "| Group | Sub-category | Kind | Trend | Match | Creators | Videos | Status | Seasonal |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in kept:
        rc = r.get("reach") or {}
        lines.append(f"| {r['group']} | {r['sub_category']} | {r['kind']} | {r['name']} | {r['match']:.0f} | "
                     f"{rc.get('creators', '?')} | {rc.get('videos', '?')} | {r['status']} | {_seasonal(r)} |")
    if m["weak_match"]:
        lines += ["", "## Weak match", "",
                  "The map stayed thin after the last split, so these are the closest trends below the match "
                  "threshold, each a weak match.", "",
                  "| Group | Sub-category | Kind | Trend | Match | Creators | Status |", "|---|---|---|---|---|---|---|"]
        for r in m["weak_match"]:
            rc = r.get("reach") or {}
            lines.append(f"| {r['group']} | {r['sub_category']} | {r['kind']} | {r['name']} | {r['match']:.0f} | "
                         f"{rc.get('creators', '?')} | {r['status']} |")
    lines += ["", "## Dropped (restore on request)", "", "| Trend | Sub-category | Why |", "|---|---|---|"]
    for r in dropped:
        lines.append(f"| {r['name']} | {r['sub_category']} | {'; '.join(r['dropped_because'])} |")
    return "\n".join(lines) + "\n"


def _write(run: RunFolder, m: dict, params: dict) -> Path:
    """category_map_vNN.json and .md with the same NN, above every earlier one of either."""
    target = max(run.next_version(trends.RESEARCH, STEM, "json"),
                 run.next_version(trends.RESEARCH, STEM, "md").with_suffix(".json"),
                 key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    page = target.with_suffix(".md")
    page.write_text(_markdown(m), encoding="utf-8")
    for f in (target, page):
        manifest.record(run, f"{trends.RESEARCH}/{f.name}", trends.RESEARCH, SOURCE, params=params)
    return target


# --- what changed since the previous run (V26) -----------------------------------------------

def map_change(run: RunFolder, cfg: dict) -> dict:
    """`{new_share, new_groups, changed_a_lot}` of the latest map against the previous run's
    (`00_raw/prev_category_map.json`): the share of kept trends whose id was not kept there, the
    groups that were not there, and whether the share reaches `digest.map_change_share` or a group is
    new (the plan's decision 8). With no previous map nothing changed a lot."""
    cfg = settings(cfg)
    current = run.latest(trends.RESEARCH, STEM, "json")
    if current is None:
        raise Stop("This run has no category map yet, so there is nothing to compare. Build it with "
                   "tm research map first; the run continues from the same place.")
    previous = run.path / PREVIOUS
    if not previous.is_file():
        return {"new_share": None, "new_groups": [], "changed_a_lot": False}
    now, before = trends.read(current), trends.read(previous)

    def groups(m: dict) -> list[str]:
        return list(dict.fromkeys(r.get("group") or r.get("sub_category") for r in m.get("kept") or []))

    known = {r.get("id") for r in before.get("kept") or []}
    kept = now.get("kept") or []
    share = round(sum(r.get("id") not in known for r in kept) / len(kept), 4) if kept else 0.0
    new_groups = [g for g in groups(now) if g not in set(groups(before))]
    return {"new_share": share, "new_groups": new_groups,                 # decided on the share shown
            "changed_a_lot": share >= cfg["digest"]["map_change_share"] or bool(new_groups)}
