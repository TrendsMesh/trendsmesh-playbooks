"""B3 and B4 of a creative brief run: the seed re-check, the trends step check, fit scores and the
Ad Library saturation checks (CB2, CB3, CB4).

    seed_check        a PB4 seed against a fresh trend card: keep, drop or unknown (B3)
    trends_gap        the `trends_or_guess` step check (B3)
    check_scores      03_wip/scores_vNN.json, the seven CB3 criteria per candidate (B4)
    totals            each candidate's weighted mean (`scoring.weights`), for the pick
    check_saturation  02_research/saturation_vNN.json, one Ad Library check per candidate (B4)
    scoring_gap       the `scores_and_saturation` step check (B4)

The scores file is `{"<candidate>": {"brand_fit": 1-5, "persona_fit", "bridge", "lifecycle",
"transfer", "sensitivity", "feasibility"}}`. A candidate is a trend id with a saved card
(`02_research/trend_<id>.json`), or `guess:<slug>` in a guess run only.

The saturation file is `{"checks": [{"candidate", "query", "country", "verdict":
"competitor_found"|"none_found", "advertisers": [], "own_ads": true|false, "note"}]}`. Every scored
candidate has a check (CB4 is mandatory: a seed's `seed_paid` is a hint for the card, never a
check). Each query's saved Ad Library answer is found by the query in its `_input`
(`trends.ad_terms`), never by the file name. The words are the spec's: "competitor found" and
"none found in Ad Library titles", never "unused" or "not in ads".

`tm brief scores` and `tm brief saturation` mark the file they passed on (`stepchecks.mark`);
B4's step check asks that the latest of each is that file, unchanged.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path

from tm import brief_config, config, json_schema, research_checks, shortlist, state, stepchecks, trends
from tm.config import Problem
from tm.evidence import GUESS, TRENDSMESH
from tm.runfolder import RunFolder

WIP = "03_wip"
SCORES, SCORES_KEY = "scores", "scores"
SATURATION, SATURATION_KEY = "saturation", "saturation"
SCORES_NAME = re.compile(rf"^{WIP}/{SCORES}_v\d+\.json$")
SATURATION_NAME = re.compile(rf"^{trends.RESEARCH}/{SATURATION}_v\d+\.json$")
GUESS_PREFIX = "guess:"
_GUESS = re.compile(r"^guess:[a-z0-9]+(?:[-_][a-z0-9]+)*$")
VERDICTS = ("competitor_found", "none_found")
MIN_QUERIES = 3          # CB2: below `trends.min_relevant`, the searches cover at least three queries
KEEP_MOMENTUM = ("rising", "holding")
WEAK = "weak fit"        # the shortlist's flag on a topic filled in without a term match
_TITLES = ("an Ad Library search reads ad titles, so it tells what it found, never that no one uses an "
           "idea (CB4)")
SATURATION_WORDS = {phrase: (research_checks.NONE_FOUND, _TITLES)
                    for phrase in ("unused", "not in ads", "no one advertises", "fresh in paid")}

SATURATION_SCHEMA: dict = {
    "type": "object",
    "required": ["checks"],
    "properties": {"checks": {"type": "array", "items": {
        "type": "object",
        "required": ["candidate", "query", "country", "verdict", "advertisers", "own_ads", "note"],
        "properties": {"candidate": {"type": "string"}, "query": {"type": "string"},
                       "country": {"type": "string"}, "verdict": {"enum": list(VERDICTS)},
                       "advertisers": {"type": "array", "items": {"type": "string"}},
                       "own_ads": {"type": "boolean"}, "note": {"type": ["string", "null"]}}}}},
}


def _today() -> date:
    return date.today()


def _setting(cfg: dict, path: str):
    """A setting of the run's config, else the creative brief default."""
    found = config.get(cfg or {}, path)
    return config.get(brief_config.DEFAULTS, path) if found is None else found


def run_config(run: RunFolder, *, strict: bool = True) -> dict:
    """The run's config ({} while there is none, so the defaults hold). A broken config.yaml is a
    ValueError for a command (`strict`, the user is told), and the defaults for a step check (A1's
    `intake_written` has the say on the config, so a gap here never hides behind it)."""
    try:
        return config.load(run) if (run.path / config.FILE).is_file() else {}
    except ValueError:
        if strict:
            raise
        return {}


def _zone() -> tzinfo | None:
    """The computer's own time zone, the one the run's `created` day is dated in (None: the local zone)."""
    return None


def _local_day(value: object) -> date | None:
    """The day, on the run's clock (`_zone`), of a saved answer's `_at` (an ISO time, UTC when it names no zone);
    a bare `YYYY-MM-DD` is that day. Compared with the run's local `created` day, a card fetched just after local
    midnight is that day's card, never the day before's (part 3 ruling 2)."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _date(value)
    if len(value) <= 10:
        return moment.date()
    moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_zone()).date()


def _date(value: object) -> date | None:
    """The date of a `YYYY-MM-DD...` text, else None."""
    try:
        return date.fromisoformat(value[:10]) if isinstance(value, str) else None
    except ValueError:
        return None


# --- the seed re-check (B3) ---------------------------------------------------------------------

def card_file(run: RunFolder, trend_id: str) -> Path | None:
    """The latest saved card of a trend, `02_research/trend_<id>[_vNN].json`; None for no card, or
    for an id that is not a TrendsMesh trend id."""
    if not (isinstance(trend_id, str) and trends.TREND_ID.fullmatch(trend_id)):
        return None
    return run.latest(trends.RESEARCH, f"trend_{trend_id}", "json")


def card_of(path: Path) -> tuple[dict | None, str | None]:
    """(the trend card a saved get_trend file holds, None), or (None, why it holds none). An answer
    that is not an object, an error (`{"error": ...}`, the collector's isError) or not JSON
    (`{"raw": ...}`) is no card: PB04's rule (`research_digest.ended_by_answer`), and its `data`
    wrapper is read the same way."""
    rel = f"{trends.RESEARCH}/{path.name}"
    try:
        answer = trends.answer_of(path)
    except (OSError, ValueError) as exc:
        return None, f"{rel} cannot be read ({exc})"
    if not isinstance(answer, dict) or "error" in answer or "raw" in answer:
        said = answer.get("error", answer.get("raw")) if isinstance(answer, dict) else answer
        text = " ".join(str(said).split())
        return None, f"{rel} is an error answer, not a card ({text[:120]})"
    return (answer["data"] if isinstance(answer.get("data"), dict) else answer), None


def _fresh_card(run: RunFolder, trend_id: str) -> tuple[dict | None, str]:
    """(the latest card of the trend, the day it was saved) when it was saved on or after the day
    the run was created; else (None, why there is no fresh card)."""
    path = card_file(run, trend_id)
    if path is None:
        return None, "this run has no fresh card of it"
    card, wrong = card_of(path)
    if card is None:
        return None, f"its latest saved card {wrong}"
    try:
        data = trends.read(path)
    except (OSError, ValueError):            # card_of read it a moment ago
        return None, f"its latest saved card {trends.RESEARCH}/{path.name} cannot be read"
    saved = _local_day(data.get("_at")) if isinstance(data, dict) else None
    if saved is None or saved < date.fromisoformat(state.load(run).created):
        return None, "this run has no fresh card of it"
    return card, saved.isoformat()


def is_expired(row: dict, today: date) -> bool:
    """A seed is expired once its `valid_until` is before today (a seed without a readable date too)."""
    until = _date(row.get("valid_until"))
    return until is None or until < today


def seed_verdict(run: RunFolder, cfg: dict, *, today: date | None = None) -> dict:
    """The run's seed (00_raw/seed.json) against the latest card of its trend saved since the run
    was created; nothing is written (`seed_check` stores it):

    - keep: the seed is not expired, or its fresh card's momentum is rising or holding and its
      status is not contradicted; `valid_until` is the seed's own while it is not expired, else the
      card's `visible_until`, else `brief.valid_days_default` days from the run (CB8);
    - drop: an expired seed whose fresh card says otherwise;
    - unknown: an expired seed with no fresh card (fetch it with get_trend first).

    ValueError for a run not started from a seed (a bad call)."""
    today = today or _today()
    row = brief_config.seed_row(run)
    if row is None:
        raise ValueError(f"{run.path.name} was not started from a seed (tm run new --seed), so there is no seed "
                         "to re-check.")
    tid, until = row.get("trend_id"), row.get("valid_until")
    name = f"{row.get('trend_name') or tid} ({tid})"
    if not is_expired(row, today):
        result = {"verdict": "keep", "why": f"The seed {name} is not expired: it is valid until {until}.",
                  "valid_until": until}
    else:
        card, saved = _fresh_card(run, tid)
        if card is None:
            result = {"verdict": "unknown",
                      "why": f"The seed {name} expired on {until}, and {saved}. Fetch it again with get_trend "
                             f"(trend_id {tid}), then re-check.",
                      "valid_until": until}
        else:
            momentum, status = card.get("momentum"), card.get("status")
            seen = f"momentum {momentum or 'not given'}, status {status or 'not given'}"
            if momentum in KEEP_MOMENTUM and status != "contradicted":
                visible = _date(card.get("visible_until"))
                created = date.fromisoformat(state.load(run).created)
                new_until = visible or created + timedelta(days=_setting(cfg, "brief.valid_days_default"))
                result = {"verdict": "keep",
                          "why": f"The seed {name} expired on {until}; its card of {saved} still says {seen}.",
                          "valid_until": new_until.isoformat()}
            else:
                result = {"verdict": "drop",
                          "why": f"The seed {name} expired on {until}, and its card of {saved} says {seen}: a "
                                 f"seed is kept only while rising or holding, and not contradicted.",
                          "valid_until": until}
    return result


SEED_STATES = ("brief", "organic")   # the run.json fields a seed check is stored in


def seed_check(run: RunFolder, cfg: dict, *, today: date | None = None, key: str = "brief") -> dict:
    """`seed_verdict`, stored in run.json `<key>.seed_check`: `brief` for a creative brief (`tm brief
    seed-check`), `organic` for organic video (`tm organic seed-check`)."""
    if key not in SEED_STATES:
        raise ValueError(f"A seed check is stored in {' or '.join(SEED_STATES)}, not {key!r}.")
    result = seed_verdict(run, cfg, today=today)
    s = state.load(run)
    setattr(s, key, {**(getattr(s, key) or {}), "seed_check": result})
    state.save(run, s)
    return result


def _seed_gap(run: RunFolder, s: state.RunState, cfg: dict) -> str | None:
    """An expired seed is re-checked before B3 closes. In a TrendsMesh run the verdict is worked out
    again here (read only): it must be known (the fresh card fetched) and the stored one, so a check
    run before get_trend, or before a newer card, is run again. A guess run cannot fetch a card, so a
    stored check of any verdict passes."""
    row = brief_config.seed_row(run)
    if row is None or not is_expired(row, _today()):
        return None
    stored = (s.brief or {}).get("seed_check")
    seed, tid = row.get("seed_id"), row.get("trend_id")
    if s.evidence != TRENDSMESH:
        return None if stored else (f"the expired seed {seed} is re-checked (tm brief seed-check --run R; get_trend "
                                    "of it first when TrendsMesh answers)")
    now = seed_verdict(run, cfg)
    if now["verdict"] == "unknown":
        why = _fresh_card(run, tid)[1]
        return (f"the expired seed {seed} is re-checked against a fresh card ({why}): fetch get_trend of {tid} "
                "again, then run tm brief seed-check --run R")
    if not stored or (stored.get("verdict"), stored.get("valid_until")) != (now["verdict"], now["valid_until"]):
        return (f"the expired seed {seed} is re-checked on its latest card (it now says {now['verdict']}): run "
                "tm brief seed-check --run R again")
    return None


# --- B3: trends_or_guess --------------------------------------------------------------------------

def _relevant(path: Path) -> int | None:
    """The shortlist's entries that are not a weak fit; None when the file cannot be read."""
    try:
        data = trends.read(path)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    rows = [r for key in ("hooks", "topics", "formats", "sounds") for r in data.get(key) or []
            if isinstance(r, dict)]
    return sum(1 for r in rows if not any(WEAK in str(f) for f in r.get("flags") or []))


def searched_queries(run: RunFolder) -> set[str]:
    """The distinct queries of the saved searches, read from each file (never its name)."""
    return _searches(run)[0]


def _searches(run: RunFolder) -> tuple[set[str], list[str]]:
    """The distinct queries of the saved searches, and the search files that cannot be read."""
    out, damaged = set(), []
    for f in trends.search_files(run):
        try:
            out.add(research_checks.key(trends.query_of(trends.read(f), f)))
        except (OSError, ValueError):
            damaged.append(f.relative_to(run.path).as_posix())
    return out, damaged


def _unranked(run: RunFolder, shortlist_file: Path) -> list[str]:
    """The saved search files the shortlist did not read (its `meta.inputs`, run-relative)."""
    try:
        data = trends.read(shortlist_file)
    except ValueError:
        return []
    meta = data.get("meta") if isinstance(data, dict) else None
    inputs = set(meta.get("inputs") or []) if isinstance(meta, dict) else set()
    return [rel for rel in (f.relative_to(run.path).as_posix() for f in trends.search_files(run)) if rel not in inputs]


def trends_gap(run: RunFolder) -> str | None:
    """B3 is done once the evidence is recorded; in a TrendsMesh run, once the shortlist and at least
    one trend card are saved and, when the shortlist has fewer than `trends.min_relevant` entries
    that are not a weak fit, the searches cover at least three distinct queries (CB2's expansion)
    and the shortlist ranks every saved search; and an expired seed is re-checked (`_seed_gap`).
    The gaps, or None."""
    s = state.load(run)
    cfg = run_config(run, strict=False)
    if s.evidence is None:
        return ("the evidence is recorded: tm evidence trendsmesh --run R --why <reason> when TrendsMesh answers, "
                "or tm evidence guess --run R --why <reason> without it")
    gaps = []
    if s.evidence == TRENDSMESH:
        shortlist_file = run.latest(WIP, shortlist.STEM, "json")
        if shortlist_file is None:
            gaps.append(f"the shortlist is written ({WIP}/{shortlist.STEM}_vNN.json, tm trends shortlist)")
        saved = sorted(f for f in (run.path / trends.RESEARCH).glob("trend_*.json") if f.is_file())
        wrong = [why for why in (card_of(f)[1] for f in saved) if why]
        if len(wrong) == len(saved):
            fix = f" (fetch them again: {'; '.join(wrong)})" if wrong else ""
            gaps.append(f"at least one trend card is saved ({trends.RESEARCH}/trend_<id>.json, get_trend){fix}")
        if shortlist_file is not None:
            least = _setting(cfg, "trends.min_relevant")
            relevant = _relevant(shortlist_file)
            if relevant is None:
                gaps.append(f"the latest shortlist {shortlist_file.name} is readable JSON (run tm trends shortlist "
                            "again)")
            elif relevant < least:
                found, damaged = _searches(run)
                queries = len(found)
                unranked = _unranked(run, shortlist_file)
                if queries < MIN_QUERIES:
                    gaps.append(f"the searches are widened (CB2): the shortlist has {relevant} relevant entries, "
                                f"fewer than trends.min_relevant {least}, and the saved searches cover {queries} "
                                f"distinct queries; search at least {MIN_QUERIES} (persona topics, angle themes), "
                                "then run tm trends shortlist again"
                                + (f" (not read, damaged: {', '.join(damaged)}; search those again)" if damaged else ""))
                elif unranked:
                    gaps.append(f"the shortlist ranks the widened searches: {shortlist_file.name} was built before "
                                f"{', '.join(unranked)}; run tm trends shortlist again")
    seed_gap = _seed_gap(run, s, cfg)
    if seed_gap:
        gaps.append(seed_gap)
    return ", and ".join(gaps) or None


# --- B4: scores (CB3) ---------------------------------------------------------------------------

def _score_problems(row: object) -> list[str]:
    if not isinstance(row, dict):
        return ["are not a table of criteria"]
    crit = brief_config.CRITERIA
    out = [f"lack {c}" for c in crit if c not in row]
    out += [f"{c} {row[c]!r} is outside 1-5" for c in crit
            if c in row and not (isinstance(row[c], int) and not isinstance(row[c], bool) and 1 <= row[c] <= 5)]
    out += [f"{k} is not a criterion" for k in row if k not in crit]
    return out


def _candidate_problem(run: RunFolder, candidate: str, evidence: str | None) -> Problem | None:
    if candidate.startswith(GUESS_PREFIX):
        if evidence is None:
            return Problem(candidate, f"{candidate} is a guess, and this run has not recorded its evidence yet.",
                           "Record it first (tm evidence guess --run R --why <reason> when TrendsMesh is not "
                           "there), then check again.")
        if evidence != GUESS:
            return Problem(candidate, f"{candidate} is a guess, and this run rests on TrendsMesh data.",
                           "Score the trends the run found (their ids, with saved cards); a guess candidate is for "
                           "a guess run only.")
        if not _GUESS.fullmatch(candidate):
            return Problem(candidate, f"{candidate!r} is not a guess candidate.",
                           "Name it guess:<slug>, the slug in lowercase letters and digits, its words joined by "
                           "hyphens or underscores.")
        return None
    path = card_file(run, candidate)
    if path is None:
        return Problem(candidate, f"{candidate} has no saved trend card in {trends.RESEARCH}/.",
                       "Score trends by the id of a card the run saved (get_trend), or fetch its card first.")
    wrong = card_of(path)[1]
    if wrong:
        return Problem(candidate, f"{candidate} has no trend card: {wrong}.",
                       "Fetch its card again with get_trend (an error is often passing), then check again.")
    return None


def check_scores(run: RunFolder, data: object, cfg: dict) -> list[Problem]:
    """Everything wrong in the scores file (CB3); empty when it holds."""
    criteria = ", ".join(brief_config.CRITERIA)
    if not isinstance(data, dict):
        return [Problem(SCORES, "The scores must be one table {\"<candidate>\": {criterion: 1-5}}.",
                        f"Write a row per candidate with {criteria}.")]
    if not data:
        return [Problem(SCORES, "No candidate is scored.", f"Score each candidate 1-5 on {criteria}.")]
    evidence = state.load(run).evidence
    out = []
    for candidate, row in data.items():
        found = _candidate_problem(run, candidate, evidence)
        if found:
            out.append(found)
        wrong = _score_problems(row)
        if wrong:
            out.append(Problem(candidate, f"{candidate}'s scores {'; '.join(wrong)}.",
                               f"Score it 1-5, as a whole number, on {criteria}."))
    return out


def totals(data: dict, weights: dict) -> dict[str, float]:
    """Each candidate's weighted mean of its seven scores; rows that are wrong are left out."""
    total = sum(weights[c] for c in brief_config.CRITERIA)
    if not total:                     # all weights 0: tm config check refuses it
        return {}
    return {cid: round(sum(weights[c] * row[c] for c in brief_config.CRITERIA) / total, 2)
            for cid, row in data.items() if not _score_problems(row)}


def _latest_scores(run: RunFolder) -> tuple[dict | None, str | None]:
    """The latest scores table, or None with what is wrong."""
    path = run.latest(WIP, SCORES, "json")
    if path is None:
        return None, f"This run has no scores yet ({WIP}/{SCORES}_vNN.json), so it is unknown what to check."
    try:
        data = trends.read(path)
    except ValueError:
        return None, f"The latest scores, {path.name}, are not valid JSON."
    if not isinstance(data, dict):
        return None, f"The latest scores, {path.name}, are not a table of candidates."
    return data, None


# --- B4: saturation (CB4) -----------------------------------------------------------------------

def check_saturation(run: RunFolder, data: object, cfg: dict) -> list[Problem]:
    """Everything wrong in the saturation file (CB4); empty when it holds. A file not in its shape
    gives its shape problems alone."""
    shape = [Problem(line.split(" ", 1)[0].removeprefix(SATURATION + "."), line,
                     'Write {"checks": [{"candidate", "query", "country", "verdict", "advertisers", "own_ads", '
                     '"note"}]}, one row per candidate, then check again.')
             for line in json_schema.problems(data, SATURATION_SCHEMA, name=SATURATION)]
    if shape:
        return shape
    out: list[Problem] = []
    answered, unreadable = research_checks.saved_queries(run)
    out += unreadable
    for i, c in enumerate(data["checks"]):
        field, label = f"checks[{i}]", c["candidate"] or "A check"
        if not c["query"].strip():
            out.append(Problem(field, f"{label} has no query.", "Give the query the Ad Library was searched with."))
        elif research_checks.key(c["query"]) not in answered:
            out.append(Problem(field, f"The query {c['query']!r} of {label} has no saved answer in "
                                      f"{trends.RESEARCH}/ad_library/.",
                               "Search it again with collection on (tm trends collect on), so the answer is "
                               "saved, then check again."))
        if c["verdict"] == "competitor_found" and not any(a.strip() for a in c["advertisers"]):
            out.append(Problem(field, f"{label} is competitor_found but names no advertiser.",
                               "Name the advertisers found, or set the verdict to none_found."))
    scores, missing = _latest_scores(run)
    if scores is None:
        out.append(Problem(SCORES, missing, f"Score the candidates first ({WIP}/{SCORES}_vNN.json, tm brief "
                                            "scores), then check the saturation."))
    else:
        have = {c["candidate"] for c in data["checks"]}
        unchecked = [cid for cid in scores if cid not in have]
        if unchecked:
            out.append(Problem("checks", f"{', '.join(unchecked)} {'has' if len(unchecked) == 1 else 'have'} no "
                                         "saturation check. CB4 checks every candidate (a seed's Ad Library level "
                                         "is a hint, never a check).",
                               "Search the Ad Library for each (its most specific product phrase) and add its row."))
    notes = {"checks": [{"note": c["note"]} for c in data["checks"]]}   # the agent's words, not copied data
    return out + research_checks.wording(notes, SATURATION_WORDS)


# --- B4: scores_and_saturation ------------------------------------------------------------------

def scores_seen(run: RunFolder) -> dict | None:
    """The latest scores file as a saturation check sees it: {file, sha256}, run-relative; None
    without one. `tm brief saturation` records it in its mark."""
    path = run.latest(WIP, SCORES, "json")
    if path is None:
        return None
    return {"file": path.relative_to(run.path).as_posix(), "sha256": stepchecks.sha256(path)}


def scoring_gap(run: RunFolder) -> str | None:
    """B4 is done once the latest scores and the latest saturation file each passed their check,
    unchanged since, and the saturation was checked against those same scores. The gaps, or None."""
    gaps = [stepchecks.fresh(run, SCORES_KEY, WIP, SCORES, "json"),
            stepchecks.fresh(run, SATURATION_KEY, trends.RESEARCH, SATURATION, "json")]
    mark = state.load(run).checked.get(SATURATION_KEY)
    if not any(gaps) and (mark or {}).get("scores") != scores_seen(run):
        gaps.append("the saturation is checked against the latest scores (they changed after tm brief saturation "
                    "passed): run tm brief saturation again")
    return ", and ".join(g for g in gaps if g) or None


def weights(cfg: dict) -> dict:
    """`scoring.weights`, every criterion filled from the defaults."""
    given = _setting(cfg, "scoring.weights")
    return {c: given.get(c, brief_config.DEFAULTS["scoring"]["weights"][c]) for c in brief_config.CRITERIA}
