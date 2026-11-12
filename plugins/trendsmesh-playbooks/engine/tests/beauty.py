"""The handoff's beauty dry run (handoff/trend-research_v01/examples/beauty-dry-run) as a PB04 run.

Every port in PR C is checked by rebuilding the reference files from this run. The raw searches and lists are
left out of the handoff, so they are derived from the reference outputs:
- videos are copied as `02_research/videos/<id>.json`;
- one saved search answer per query of `category_map.json` (`_input.about` = the query, `limit` 50),
  holding one card per trend whose `found_by` names that query, with that query's score as its
  `match`. `below_threshold` is a count, not cards, so these files rebuild `kept` and `dropped` only;
- the hook cards of `hooks_in_category.json` (`kept`, then `not_in_category`, kind `hook_trend`) as
  one saved rising hook list, `02_research/lists/list_rising_hook_trend_all_p01.json` (ruling F8);
- other inputs are copied with `copy_input`: `_v01` is added unless the name already has a version.
`mapped_run` then builds the map (the reference split and review) and runs the hooks path, as the reference dry run did,
with a judgement of the hooks made from the reference's counts (`hook_use`).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from tm import research_config, research_growth, research_map, trends
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

REPO = Path(__file__).resolve().parents[4]
BEAUTY = REPO / "handoff" / "trend-research_v01" / "examples" / "beauty-dry-run"
CREATED = date(2026, 11, 4)
AT = "2026-11-04T10:00:00+00:00"
ROOT = "beauty"
CARD_FIELDS = ("id", "kind", "name", "status", "reach", "since", "active_for_days", "momentum",
               "sensitivity_level", "what_it_is")
HOOK_LIST = Path(trends.RESEARCH) / "lists" / "list_rising_hook_trend_all_p01.json"


def handoff(rel: str) -> Any:
    """A JSON file of the beauty dry run, by its path inside the example folder."""
    return json.loads((BEAUTY / rel).read_text(encoding="utf-8"))


def search_answers(category_map: dict) -> dict[str, list[dict]]:
    """query -> the cards of its derived search answer, closest first (ties in map order)."""
    rows = category_map["kept"] + category_map["dropped"]
    found: dict[str, list[tuple[float, int, dict]]] = {q["query"]: [] for q in category_map["queries"]}
    for i, row in enumerate(rows):
        for query, score in row["found_by"].items():
            card = {k: row.get(k) for k in CARD_FIELDS}
            found[query].append((score, i, {**card, "match": {"score": score}}))
    return {q: [card for _, _, card in sorted(cards, key=lambda t: (-t[0], t[1]))]
            for q, cards in found.items()}


def split_of(category_map: dict) -> dict:
    """The split file the agent would have written for these queries: depth 0 for the root, 1 under
    the root or under a group that was not searched itself ("hair"), else one below its parent."""
    parents = {q["query"]: q["parent"] for q in category_map["queries"]}

    def depth(query: str) -> int:
        parent = parents.get(query)
        if parent is None:
            return 0
        return depth(parent) + 1 if parent in parents else 2

    return {"root": category_map["root"],
            "queries": [{"query": q, "parent": p, "depth": depth(q),
                         "source": "seed" if p is None else "common_sub_areas"} for q, p in parents.items()]}


def hook_cards(hooks_in_category: dict) -> list[dict]:
    """The hook cards the original's `hooks` read: kept, then not in category, each of kind hook_trend."""
    return [{**{k: row[k] for k in CARD_FIELDS if k in row}, "kind": "hook_trend"}
            for row in hooks_in_category["kept"] + hooks_in_category["not_in_category"]]


def make_run(tmp_path: Path) -> RunFolder:
    """A trend research run for "beauty, US" in `tmp_path/ws`, built as the module docstring says."""
    run = RunFolder.create(tmp_path / "ws", ROOT, CREATED, playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"inputs": [ROOT], "phrase": ROOT, "seeds": []},
                                            "market": "US", "language": "en"})
    videos = run.path / trends.RESEARCH / "videos"
    videos.mkdir(parents=True)
    for f in sorted((BEAUTY / "02_research" / "videos").glob("*.json")):
        shutil.copyfile(f, videos / f.name)
    for query, cards in search_answers(handoff("02_research/category_map.json")).items():
        trends.save_answer(run, "search_trends", {"about": query, "limit": 50}, {"data": cards}, at=AT)
    hooks = run.path / HOOK_LIST
    hooks.parent.mkdir(parents=True)
    hooks.write_text(json.dumps({"_tool": "list_trends", "_input": {"sort": "rising", "trend_type": "hook_trend"},
                                 "_at": AT, "answer": {"data": hook_cards(handoff("02_research/hooks_in_category.json")),
                                                       "page": 1, "has_more": False}},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def copy_input(run: RunFolder, rel: str) -> Path:
    """Copy a file of the dry run into the same stage of `run`; `x.json` becomes `x_v01.json`, a name
    that already has a version (`picks_v04.json`) is kept."""
    src = BEAUTY / rel
    name = src.name if re.search(r"_v\d+$", src.stem) else f"{src.stem}_v01{src.suffix}"
    dest = run.path / Path(rel).parent / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest


def cfg(**sections) -> dict:
    """The default config for "beauty, US", with `sections` updated (`buckets={"act_index": 2}`)."""
    out = research_config.defaults()
    out["category"]["phrase"] = ROOT
    out["market"], out["language"] = "US", "en"
    for name, values in sections.items():
        out[name].update(values)
    return out


# Issue #3, item 5: whether the category uses a shortlisted hook is the agent's judgement of its captions,
# no longer the reference's word matching, so a hook row's category counts are this run's own.
JUDGED_KEYS = ("category_videos", "category_share", "videos_checked", "event")
OLD_ONLY = ("category_examples",)          # the matched videos, which the judgement does not list


def hook_use(run: RunFolder) -> dict:
    """The agent's judgement of the run's shortlisted hooks (`tm research hooks --file`), made from the
    reference: a hook has as many category videos as the reference counted, at most the captions read."""
    counts = {r["id"]: r["category_videos"] for r in handoff("02_research/hooks_in_category.json")["kept"]}
    out = {}
    for r in research_growth.shortlist(run)["shortlist"]:
        read = len(research_growth.captions_read(trends.load_videos(run, r["id"])))
        n = min(counts.get(r["id"], 0), read)
        out[r["id"]] = {"in_category": n > 0, "category_videos": n, "why": "the dry run's category videos",
                        "event": None}
    return out


def as_judged(reference: Any, run: RunFolder) -> Any:
    """`reference` (a growth file, a report) with every hook row's category counts and event as this run's
    latest hooks path gives them (`JUDGED_KEYS`), without the keys only word matching wrote (`OLD_ONLY`)."""
    path = run.latest(trends.RESEARCH, research_growth.HOOKS_STEM, "json")
    ours = {r["id"]: r for r in trends.read(path)["kept"]}

    def walk(x: Any) -> Any:
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        out = {k: walk(v) for k, v in x.items()}
        mine = ours.get(out.get("id"))
        if out.get("kind") == "hook_trend" and mine and "category_videos" in out:
            out = {k: v for k, v in out.items() if k not in OLD_ONLY} | {k: mine[k] for k in JUDGED_KEYS}
        return out

    return walk(reference)


def as_rising_bands(reference: Any, run: RunFolder) -> Any:
    """`reference` (a growth file, a snapshot, a backtest, a report, a digest) with every hook's band read
    from its place in this run's rising hook list, as growth reads it since issue #58 (the owner's choice:
    among every rising hook TrendsMesh lists, not among the hooks whose videos were read), and the list's
    length (`hooks_rising`) beside each `hooks_pool`. The dry run ranked hooks among the hooks read; all
    else, the velocity index and the stages too, must still be the reference's. A hook is found by its
    `id`, or by its key in a dict of rows (the snapshot's `trends`)."""
    order = research_growth.rising_order(run)
    hooks = {c["id"] for c in research_growth.hook_cards(run)}

    def walk(x: Any, key: str | None = None) -> Any:
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        out = {k: walk(v, k) for k, v in x.items()}
        tid = out.get("id") or key
        if order and tid in hooks:
            for k in ("relative", "relative_then"):
                if isinstance(out.get(k), dict) and "velocity_index" in out[k]:
                    out[k] = research_growth.rising_place(out[k], tid, order)
        if order and "hooks_pool" in out:
            out["hooks_rising"] = len(order)
        return out

    return walk(reference)


def md_rising_bands(md: str, rows: list[dict]) -> str:
    """A growth .md with each hook row's Band cell as `rows` (a growth file's trends) give it: the
    markdown side of `as_rising_bands`."""
    band = {r["name"]: (r.get("relative") or {}).get("band", "—") for r in rows if r.get("kind") == "hook_trend"}
    out = []
    for line in md.split("\n"):
        cells = line.split(" | ")
        if line.startswith("| ") and len(cells) > 4 and cells[2] == "hook" and cells[1] in band:
            cells[3] = band[cells[1]]
            line = " | ".join(cells)
        out.append(line)
    return "\n".join(out)


def fit_scores(hooks_in_category: dict) -> dict:
    """Fit scores (issue #8) that rank the reference's kept hooks first, in their order, and every other
    hook card last: the shortlist of `len(kept)` is then the hooks the reference dry run kept."""
    from tm import brief_config
    kept = [r["id"] for r in hooks_in_category["kept"]]
    rows = {c["id"]: {k: 1 for k in brief_config.CRITERIA} for c in hook_cards(hooks_in_category)}
    for i, hid in enumerate(kept):
        rows[hid] = {k: 5 if j > i else 4 for j, k in enumerate(brief_config.CRITERIA)}
    return rows


def mapped_run(tmp_path: Path) -> RunFolder:
    """`make_run`, then the category map from the reference split and review, then the hooks path: the
    fit scores of `fit_scores`, a shortlist as long as the reference's kept hooks, and their videos."""
    run = make_run(tmp_path)
    handoff_map = handoff("02_research/category_map.json")
    research_map.build(run, split_of(handoff_map), handoff("03_wip/map_review_v01.json"), cfg())
    reference = handoff("02_research/hooks_in_category.json")
    research_growth.hook_fit(run, fit_scores(reference), cfg(hooks={"shortlist": len(reference["kept"])}))
    research_growth.hooks(run, hook_use(run), cfg())
    return run
