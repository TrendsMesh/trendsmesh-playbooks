"""Checks on what the agent writes in a trend research run, and the evidence it reads (TR3-TR7).

    evidence     the top videos of one trend, for the agent to read (D1):
                 03_wip/evidence_dump_vNN.txt, one dump per step, each trend appended to it
    check_paid   the Ad Library reading, 02_research/ad_library_summary_vNN.json (TR7, D2)
    check_picks  the picks, 03_wip/picks_vNN.json (TR3 moves, TR4 risk, TR5 scores, TR6, D3)

The agent judges; these checks hold its files to the rules and the spec's words. Each returns
`config.Problem`s, empty when the file holds; nothing is written. The Ad Library summary is
the handoff's shape plus `"checked": true|false` at the top (false: the Meta Ads connector was
unavailable, V22). A check finds its saved answer in `02_research/ad_library/` by the query saved
in the answer's `_input`, never by the file name (names are capped and hashed). The picks file is
`templates/picks_template.json` plus `scores` (decision 13); it keeps the original's output words, mapped
to the run's by `research_config.PICK_OUTPUTS` (ruling F7c). `weighted_totals` gives the page each
pick's weighted score; it is never written into the picks file (ruling F7b).
"""

from __future__ import annotations

import json
import re
import statistics as st
from datetime import date, timedelta
from typing import Iterator

from tm import manifest, research_config, research_digest, research_growth, research_map, state, trends
from tm.config import Problem
from tm.runfolder import RunFolder
from tm.stops import Stop

WIP = "03_wip"
PICKS_STEM = "picks"
DUMP_STEM = "evidence_dump"
SOURCE_EVIDENCE = "tm research evidence"
RECENT_DAYS = 45            # the evidence shown: the last 45 days before the reference date, else all
EXCERPT = 140

LEVELS = ("none", "found", "crowded", "not_checkable")             # TR7
FOUND_MAX = 3
CROWDED_MIN = 4
NONE_FOUND = "none found in Ad Library titles"
NOT_CHECKABLE = "Not checkable without Foreplay"
MOVED = "Moved by review"
MOVE_TO = ("still_rising", "too_late", "past_peak")
WHY_MIN = 20
PICKED = ("act_now", "still_rising")
WRITE_UPS = ("what", "how", "risk")
PAID_VIEW, DIGEST = "paid_view", "weekly_digest"
_TITLES_ONLY = "the Ad Library returns titles only (TR7)"
PAID_WORDS = {"not in ads": (NONE_FOUND, _TITLES_ONLY)}
PICKS_WORDS = {**PAID_WORDS,
               "no one advertises": (NONE_FOUND, _TITLES_ONLY),
               "no trends in the category": (research_map.WEAK,
                                             "a thin map lists its closest trends as a weak match (V7)")}
_SAME_CHECK = re.compile(r"\s*\(same check\)\s*$", re.IGNORECASE)


# --- shared -----------------------------------------------------------------------------------

def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _id(item: object, key: str = "id") -> str | None:
    """A row's trend id when it is a string, else None."""
    tid = item.get(key) if isinstance(item, dict) else None
    return tid if isinstance(tid, str) else None


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def growth(run: RunFolder) -> dict:
    """The latest growth file; Stop (what to do) when there is none."""
    path = run.latest(trends.RESEARCH, research_growth.STEM, "json")
    if path is None:
        raise Stop("This run has no growth yet. Run tm research growth first; the run continues from the same "
                   "place.")
    return trends.read(path)


def _rows(run: RunFolder) -> dict[str, dict]:
    return {r["id"]: r for r in growth(run)["trends"]}


def _name(rows: dict[str, dict], trend_id: object) -> str:
    row = rows.get(trend_id) if isinstance(trend_id, str) else None
    return f"{row['name']} ({trend_id})" if row else str(trend_id)


def _label(bucket: str) -> str:
    return research_growth.LABEL.get(bucket, bucket).lower()


def after_moves(rows: dict[str, dict], picks: dict | None) -> dict[str, str]:
    """Every trend's stage once the review's moves are applied (a move from act_now only)."""
    out = {i: r["bucket"] for i, r in rows.items()}
    for m in (picks or {}).get("moves") or []:
        if (_id(m) in out and out[m["id"]] == "act_now"
                and m.get("from") == "act_now" and m.get("to") in MOVE_TO):
            out[m["id"]] = m["to"]
    return out


def pick_ids(picks: dict) -> list[str]:
    """The ids of the act now picks, then the still rising picks, each once."""
    return list(dict.fromkeys(i for b in PICKED for i in map(_id, picks.get(b) or []) if i))


def strings(data: object, path: str = "") -> Iterator[tuple[str, str]]:
    """(where, text) of every text in `data`, its place written as `a.b[0].c`. Shared with PB02."""
    if isinstance(data, str):
        yield path, data
    elif isinstance(data, dict):
        for k, v in data.items():
            yield from strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            yield from strings(v, f"{path}[{i}]")


def wording(data: object, words: dict[str, tuple[str, str]]) -> list[Problem]:
    """A problem for each text that says a phrase the spec forbids, as whole words: `words` maps the
    phrase (lowercase) to (what to say instead, why). Shared with PB02."""
    out = []
    for path, text in strings(data):
        low = text.casefold()
        for phrase, (instead, why) in words.items():
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", low):   # whole words: "adsets" is not "ads"
                out.append(Problem(path, f'{path} says "{phrase}".', f'Say "{instead}" instead: {why}.'))
    return out


_strings, _wording = strings, wording   # the names PB04 used first


# --- the Ad Library reading (TR7) -------------------------------------------------------------

def ad_query(text: str) -> str:
    """The query an Ad Library check ran: the summary's query without the original's "(same check)" note
    (a trend read from another trend's answer)."""
    return _SAME_CHECK.sub("", text).strip()


def key(query: str) -> str:
    """A query as it is compared: case and runs of spaces aside. Shared with PB02."""
    return " ".join(query.casefold().split())


_key = key


def saved_queries(run: RunFolder) -> tuple[set[str], list[Problem]]:
    """The queries of the saved Ad Library answers, `02_research/ad_library/*.json`, by their `_input`,
    and a problem for each file that is not JSON (its query is unknown)."""
    folder = run.path / trends.RESEARCH / "ad_library"
    out, problems = set(), []
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = trends.read(f)
        except ValueError:
            problems.append(Problem("ad_library", f"The saved Ad Library answer {trends.RESEARCH}/ad_library/{f.name} "
                                                  "is not JSON (damaged or cut short), so its query is unknown.",
                                    "Delete it and search its query again with collection on (tm trends collect "
                                    "on), so the answer is saved whole, then check again."))
            continue
        tool_input = data.get("_input") if isinstance(data, dict) else None
        terms = trends.ad_terms(tool_input) if isinstance(tool_input, dict) else None
        if terms:
            out.add(_key(terms))
    return out, problems


def _latest_picks(run: RunFolder) -> dict | None:
    path = run.latest(WIP, PICKS_STEM, "json")
    data = trends.read(path) if path else None
    return data if isinstance(data, dict) else None


def paid_scope(run: RunFolder, rows: dict[str, dict], cfg: dict, out: list[Problem]) -> list[str]:
    """The trends the Ad Library must cover (TR7, V22a). With the paid view: every act now and still
    rising trend after the review's moves (the latest picks file), and every too late trend with at
    least `paid.too_late_min_creators` creators. Without it: every pick (none, with a problem in
    `out`, while there is no picks file)."""
    picks = _latest_picks(run)
    if PAID_VIEW in cfg["outputs"]:
        least = cfg["paid"]["too_late_min_creators"]
        stage = after_moves(rows, picks)
        return [i for i, b in stage.items() if b in PICKED
                or (b == "too_late" and (rows[i]["growth"].get("creators") or 0) >= least)]
    if picks is None:
        out.append(Problem("checks", "Without the paid view the Ad Library checks cover the picks, and this run has no "
                           "picks file yet.", f"Write {WIP}/{PICKS_STEM}_vNN.json, then check again."))
        return []
    return pick_ids(picks)


def _check_row(c: dict, field: str, rows: dict[str, dict], checked: object, answered: set[str]) -> list[Problem]:
    out = []
    tid = _id(c, "trend_id")
    row = rows.get(tid) if tid else None
    label = c.get("trend") if _text(c.get("trend")) else _name(rows, tid)
    if row is None:
        out.append(Problem(field, f"{c.get('trend') or 'A check'} has the id {tid!r}, which is not in the latest growth.",
                           "Use the trend's id from growth_vNN.json."))
    level = c.get("level")
    if level not in LEVELS:
        return out + [Problem(field, f"{label} has the level {level!r}.", f"Use one of {', '.join(LEVELS)}.")]
    if row is not None and row.get("kind") == "hook_trend" and level != "not_checkable":
        out.append(Problem(field, f'{label} is a hook, and hooks are "{NOT_CHECKABLE}": an opening structure cannot be '
                                  f"matched in Ad Library titles, so it can't be {level}.",
                           "Set its level to not_checkable."))
    if checked is False:
        if level != "not_checkable":
            out.append(Problem(field, f"The Ad Library was not checked (checked is false), so {label} can't be {level}.",
                               'Leave the trends that were not checked out of checks: the paid view and the card '
                               'verdicts say "not checked". Or check them and set checked to true.'))
        return out
    advertisers = c.get("advertisers")
    if not isinstance(advertisers, list):
        out.append(Problem(field, f"{label}'s advertisers are not a list.", "List the relevant advertisers, [] for none."))
        advertisers = []
    n = len(advertisers)
    if level == "found" and not 1 <= n <= FOUND_MAX:
        out.append(Problem(field, f"{label} is found with {n} advertisers; found means 1-{FOUND_MAX} relevant advertisers.",
                           f"Set it to crowded ({CROWDED_MIN} or more) or none, or correct the advertisers."))
    if level == "crowded" and n < CROWDED_MIN and not _number(c.get("estimated")):
        out.append(Problem(field, f"{label} is crowded with {n} advertisers and no estimated count; crowded means "
                                  f"{CROWDED_MIN} or more relevant advertisers, or a very large estimated count.",
                           "Add the estimated count of the search, or set the level found by the advertisers."))
    query = c.get("query")
    if level != "not_checkable" and not _text(query):
        out.append(Problem(field, f"{label} has a level but no query.", "Give the query the Ad Library was searched with."))
    elif _text(query) and _key(ad_query(query)) not in answered:
        out.append(Problem(field, f"The query {ad_query(query)!r} of {label} has no saved answer in "
                                  f"{trends.RESEARCH}/ad_library/.",
                           "Search it again with collection on (tm trends collect on), so the answer is saved, then "
                           "check again."))
    return out


def check_paid(run: RunFolder, summary: dict, cfg: dict) -> list[Problem]:
    """Everything wrong in the Ad Library summary (TR7, V22, V22a); empty when it holds."""
    if not isinstance(summary, dict):
        raise Stop("The Ad Library summary must hold one JSON object. Write it as {\"checked\": true, \"checks\": "
                   "[...]}, then check again; the run continues from the same place.")
    cfg = research_map.settings(cfg)
    rows = _rows(run)
    out: list[Problem] = []
    checked = summary.get("checked")
    if not isinstance(checked, bool):
        out.append(Problem("checked", "The summary does not say whether the Ad Library was checked.",
                           'Add "checked": true at the top, or "checked": false when the Meta Ads connector is '
                           "unavailable (V22)."))
    checks = summary.get("checks")
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        out.append(Problem("checks", "checks must be a list of rows {trend_id, trend, query, level, estimated, "
                                     "advertisers}.", "Write one row per trend checked."))
        return out + _wording(summary, PAID_WORDS)
    answered: set[str] = set()
    if checked is not False:
        answered, unreadable = saved_queries(run)
        out += unreadable
    for i, c in enumerate(checks):
        out += _check_row(c, f"checks[{i}]", rows, checked, answered)
    if checked is not False:
        have = {_id(c, "trend_id") for c in checks}
        missing = [i for i in paid_scope(run, rows, cfg, out) if i not in have]
        if missing:
            out.append(Problem("checks", f"{len(missing)} trends in the paid scope have no check: "
                                         + ", ".join(_name(rows, i) for i in missing) + ".",
                               "Check each in the Ad Library (its most specific product phrase; a hook is "
                               "not_checkable) and add its row."))
    return out + _wording(summary, PAID_WORDS)


# --- the picks (TR3-TR6) ----------------------------------------------------------------------

def _ids(picks: dict) -> Iterator[tuple[str, object]]:
    for key in ("moves", "act_now", "act_now_other", "still_rising"):
        for p in picks.get(key) or []:
            if isinstance(p, dict):
                yield key, p.get("id")
    lens = picks.get("lens")
    for item in (lens.get("items") or []) if isinstance(lens, dict) else []:
        if isinstance(item, dict):
            yield "lens", item.get("id")
    scores = picks.get("scores")
    for tid in scores if isinstance(scores, dict) else {}:
        yield "scores", tid


def _moves(picks: dict, rows: dict[str, dict]) -> list[Problem]:
    out = []
    for m in picks.get("moves") or []:
        if not isinstance(m, dict):
            out.append(Problem("moves", f"{m!r} is not a move.", "Write each move as {id, from, to, why}."))
            continue
        tid = _id(m)
        name = _name(rows, tid)
        if m.get("from") != "act_now" or rows.get(tid, {}).get("bucket") != "act_now":
            out.append(Problem("moves", f"{name} is moved from {m.get('from')!r}, but the review moves trends only from "
                                        "act_now (TR3).", "Move only trends that growth puts in act now."))
        if m.get("to") not in MOVE_TO:
            out.append(Problem("moves", f"{name} is moved to {m.get('to')!r}.", f"Move it to one of {', '.join(MOVE_TO)}."))
        why = m.get("why")
        if not (isinstance(why, str) and len(why.strip()) >= WHY_MIN):
            out.append(Problem("moves", f'The move of {name} has no reason of at least {WHY_MIN} characters; the page '
                                        f'shows it under "{MOVED}".',
                               "Write why in one or two sentences, with the evidence (dates and where they come from, "
                               "the advertisers, the share of videos about the category)."))
    return out


def _sensitive(row: dict) -> str | None:
    plugin = row.get("plugin") or {}
    videos, level = plugin.get("sensitive_videos") or 0, plugin.get("sensitivity_level")
    if videos:
        return f"{videos} sensitive videos"
    if level not in (None, "none"):
        return f"sensitivity level {level}"
    return None


def _picks(picks: dict, rows: dict[str, dict], stage: dict[str, str], cfg: dict) -> list[Problem]:
    out = []
    for bucket in PICKED:
        listed = picks.get(bucket) or []
        if len(listed) > cfg["picks"][bucket]:
            out.append(Problem(bucket, f"{len(listed)} {_label(bucket)} picks; the config allows "
                                       f"{cfg['picks'][bucket]} (picks.{bucket}).", "Keep the strongest, drop the rest."))
        for p in listed:
            if not isinstance(p, dict):
                out.append(Problem(bucket, f"{p!r} is not a pick.", "Write each pick as {id, what, how, risk}."))
                continue
            tid, name = _id(p), _name(rows, _id(p))
            if tid in stage and stage[tid] != bucket:
                out.append(Problem(bucket, f"{name} is a {_label(bucket)} pick but is {_label(stage[tid])} after the "
                                           "moves.", f"Pick it where it is, or move it with a reason ({MOVED})."))
            missing = [k for k in WRITE_UPS if not _text(p.get(k))]
            if missing:
                out.append(Problem(bucket, f"{name} has no {', '.join(missing)}.",
                                   "Write what it is, how to use it and its risk, from the evidence (TR6)."))
            flagged = _sensitive(rows[tid]) if tid in rows else None
            if flagged and "sensitiv" not in str(p.get("risk") or "").casefold():
                out.append(Problem(bucket, f"{name} has {flagged}, and its risk does not say so (TR4).",
                                   "Say in its risk line that the evidence is flagged sensitive, and what that means."))
    moved = {_id(m) for m in picks.get("moves") or []} - {None}
    for p in picks.get("act_now_other") or []:
        tid = _id(p)
        if tid in stage and stage[tid] != "act_now" and tid not in moved:
            out.append(Problem("act_now_other", f"{_name(rows, tid)} is listed as act now by the numbers but is "
                                                f"{_label(stage[tid])} after the moves.", "Remove it from act_now_other."))
    return out


def _score_problems(row: object) -> list[str]:
    if not isinstance(row, dict):
        return ["not a table of criteria"]
    out = [f"lack {c}" for c in research_config.CRITERIA if c not in row]
    out += [f"{c} {row[c]!r} is outside 1-5" for c in research_config.CRITERIA
            if c in row and not (isinstance(row[c], int) and not isinstance(row[c], bool) and 1 <= row[c] <= 5)]
    out += [f"{k} is not a criterion" for k in row if k not in research_config.CRITERIA]
    return out


def _scores(picks: dict, rows: dict[str, dict]) -> list[Problem]:
    criteria = ", ".join(research_config.CRITERIA)
    scores = picks.get("scores")
    if not isinstance(scores, dict):
        return [Problem("scores", f"The picks have no score table (TR5: each pick scored 1-5 on {criteria}).",
                        'Add "scores": {"<trend id>": {"growth": 1-5, ...}} for every pick.')]
    out = []
    for tid in pick_ids(picks):
        if tid not in scores:
            out.append(Problem("scores", f"{_name(rows, tid)} has no score row.", f"Score it 1-5 on {criteria}."))
            continue
        wrong = _score_problems(scores[tid])
        if wrong:
            out.append(Problem("scores", f"{_name(rows, tid)}'s scores {'; '.join(wrong)}.",
                               f"Score it 1-5, as a whole number, on {criteria}."))
    return out


def _readings(run: RunFolder, picks: dict, cfg: dict) -> list[Problem]:
    out = []
    paid = PAID_VIEW in cfg["outputs"]
    reading = picks.get("paid_reading")
    if paid and not (isinstance(reading, list) and reading and all(_text(x) for x in reading)):
        out.append(Problem("paid_reading", "The paid view is chosen, so the picks need paid_reading.",
                           "Write 3-4 lines: the openings, the crowded ones, the saturated ones, what cannot be checked "
                           "(TR7)."))
    if not paid and reading:
        out.append(Problem("paid_reading", "The paid view is not chosen, so the page has no paid reading.",
                           "Remove paid_reading."))
    digest = DIGEST in cfg["outputs"] and run.latest(trends.RESEARCH, research_digest.STEM, "json") is not None
    reading = picks.get("digest_reading")
    if digest and not (isinstance(reading, dict) and reading.get("summary")):
        out.append(Problem("digest_reading", "This run has a digest and the weekly digest is chosen, so the picks need "
                                             "digest_reading.",
                           "Write its summary (4-5 sentences) and todo (3-4 actions) from the digest (TR8)."))
    if not digest and reading:
        out.append(Problem("digest_reading", "The page has no digest view (the weekly digest is not chosen, or this run "
                                             "has no digest yet), so digest_reading is not shown.",
                           "Remove digest_reading."))
    return out


def _outputs(picks: dict, cfg: dict) -> list[Problem]:
    words = picks.get("outputs")
    run_words = [research_config.PICK_OUTPUTS[o] for o in cfg["outputs"] if o in research_config.PICK_OUTPUTS]
    to_run = {w: o for o, w in research_config.PICK_OUTPUTS.items()}
    if (isinstance(words, list) and all(w in to_run for w in words)
            and {to_run[w] for w in words} == set(cfg["outputs"])):
        return []
    return [Problem("outputs", f"The picks' outputs {json.dumps(words)} are not the run's ({', '.join(cfg['outputs'])}).",
                    f"Set outputs to {json.dumps(run_words)}.")]


def _about(picks: dict) -> list[Problem]:
    """The picks say what they are about: the date the trend data was read at, the market and the category."""
    out = []
    as_of = picks.get("as_of")
    try:
        dated = isinstance(as_of, str) and date.fromisoformat(as_of) is not None
    except ValueError:
        dated = False
    if not dated:
        out.append(Problem("as_of", f"The picks' as_of is {as_of!r}, not a date (YYYY-MM-DD).",
                           'Set as_of to the day the trend data was read, e.g. "2026-11-04": the page\'s dates and '
                           "the picks' valid-until come from it."))
    for key, what in (("market", 'the market, e.g. "US"'), ("category", "the category, as the page names it")):
        if not _text(picks.get(key)):
            out.append(Problem(key, f"The picks have no {key}.", f"Set {key} to {what}."))
    return out


def check_picks(run: RunFolder, picks: dict, cfg: dict) -> list[Problem]:
    """Everything wrong in the picks file (TR3 moves, TR4 risk, TR5 scores, TR6, TR7, V22a); empty
    when it holds."""
    if not isinstance(picks, dict):
        raise Stop("The picks file must hold one JSON object, as templates/picks_template.json. Write it again, then "
                   "check again; the run continues from the same place.")
    cfg = research_map.settings(cfg)
    rows = _rows(run)
    out = [Problem(where, f"{tid} in {where} is not in the latest growth.", "Use the trend ids of growth_vNN.json.")
           for where, tid in _ids(picks) if not (isinstance(tid, str) and tid in rows)]
    out += _about(picks)
    out += _moves(picks, rows)
    out += _picks(picks, rows, after_moves(rows, picks), cfg)
    out += _scores(picks, rows)
    out += _readings(run, picks, cfg)
    out += _outputs(picks, cfg)
    return out + _wording(picks, PICKS_WORDS)


def weighted_totals(picks: dict, cfg: dict) -> dict[str, float]:
    """Each pick's weighted total, the sum of score x `scoring.weights` (TR5), for the page; picks
    whose score row is missing or wrong are left out."""
    weights = research_map.settings(cfg)["scoring"]["weights"]
    scores = picks.get("scores") if isinstance(picks.get("scores"), dict) else {}
    return {tid: round(sum(weights[c] * scores[tid][c] for c in research_config.CRITERIA), 2)
            for tid in pick_ids(picks) if tid in scores and not _score_problems(scores[tid])}


# --- the evidence dump (D1) -------------------------------------------------------------------

def _video(v: dict) -> dict:
    return {"published": str(v["published"])[:10] if v.get("published") else None,
            "creator": trends.creator_of(v), "views": v.get("views"), "url": v.get("url"),
            "hook_text": v.get("hook_text"), "slot_fill": v.get("slot_fill"), "appears_at_s": v.get("appears_at_s"),
            "excerpt": " ".join(str(v.get("excerpt") or "").split())[:EXCERPT], "sensitive": v.get("is_sensitive") is True}


def _views(n: object) -> str:
    return f"{round(n):,}" if _number(n) else "?"


def _section(row: dict, videos: list[dict], shown: list[dict], ref: date, recent: bool) -> str:
    known = sorted(v.get("views") or 0 for v in videos)
    span = (f"from the {RECENT_DAYS} days to {ref.isoformat()}" if recent
            else f"of all (none in the {RECENT_DAYS} days to {ref.isoformat()})")
    lines = [f"#### {research_growth.LABEL.get(row['bucket'], row['bucket'])} | {row['name']} ({row['id']}) | "
             f"{row.get('kind')} | {len(videos)} videos, median views {_views(st.median(known) if known else 0)}; "
             f"top {len(shown)} by views {span}",
             f"   what: {row.get('what_it_is') or '-'}"]
    for v in shown:
        lines.append(f"   {v['published'] or 'no date'} {v['creator'] or 'unknown creator'} {_views(v['views'])} views "
                     f"{v['url'] or '(no link)'}")
        lines.append(f"      hook: {v['hook_text'] or '-'} | slot: {v['slot_fill'] or '-'} | at: "
                     f"{'-' if v['appears_at_s'] is None else str(v['appears_at_s']) + ' s'}"
                     + (" | SENSITIVE" if v["sensitive"] else ""))
        lines.append(f"      {v['excerpt'] or '-'}")
    return "\n".join(lines) + "\n"


def evidence(run: RunFolder, trend_id: str, *, top: int = 5) -> dict:
    """The top `top` videos of a trend of the latest growth, by views, from the last 45 days before
    its reference date (else from all), for the agent to read. The trend is appended to the latest
    03_wip/evidence_dump_vNN.txt when that dump was started at the run's current step (a trend
    already in it is not added twice); otherwise a new version is started. Returns the file, the
    videos and the text."""
    if isinstance(top, bool) or not isinstance(top, int) or top < 1:
        raise ValueError(f"--top {top!r} is not a number of videos: use a whole number from 1.")
    data = growth(run)
    row = next((r for r in data["trends"] if r["id"] == trend_id), None)
    if row is None:
        raise ValueError(f"{trend_id} is not in the latest growth. Give the id of a trend in it.")
    if not trends.video_files(run, trend_id):
        raise Stop(f"{row['name']} ({trend_id}) has no saved evidence videos. Fetch them (TrendsMesh "
                   "get_trend_videos, every page) with collection on; the run continues from the same "
                   "place.")
    videos = trends.load_videos(run, trend_id)
    ref = date.fromisoformat(data["params"]["ref"])
    cut = ref - timedelta(days=RECENT_DAYS)
    recent = [v for v in videos if v.get("published") and cut < research_growth.d(v["published"]) <= ref]
    shown = [_video(v) for v in sorted(recent or videos, key=lambda v: -(v.get("views") or 0))[:top]]
    text = _section(row, videos, shown, ref, bool(recent))

    header = f"# Evidence dump, step {state.load(run).step or 'start'} ({SOURCE_EVIDENCE})\n"
    latest = run.latest(WIP, DUMP_STEM, "txt")
    current = latest.read_text(encoding="utf-8") if latest else ""
    appended = already = False
    if latest and current.startswith(header):
        path = latest
        already = f"({trend_id})" in current
        if not already:
            with path.open("a", encoding="utf-8") as fh:
                fh.write("\n" + text)
            appended = True
    else:
        path = run.next_version(WIP, DUMP_STEM, "txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + "\n" + text, encoding="utf-8")
        manifest.record(run, path.relative_to(run.path).as_posix(), WIP, SOURCE_EVIDENCE,
                        params={"trend": trend_id, "top": top, "recent_days": RECENT_DAYS})
    return {"file": path.relative_to(run.path).as_posix(), "trend": trend_id, "name": row["name"],
            "bucket": row["bucket"], "appended": appended, "already": already, "videos": shown, "text": text}
