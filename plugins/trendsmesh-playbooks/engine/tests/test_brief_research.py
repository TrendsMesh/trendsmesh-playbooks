"""tm brief seed-check, scores and saturation, and the B3/B4 step checks (CB2, CB3, CB4)."""

import json
from datetime import date, timedelta, timezone
from pathlib import Path

import pytest

import ld
import test_shortlist
from tm import brief_config, brief_research, research_checks, seeds, state, stepchecks, trend_spool, trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

GOLDEN = Path(__file__).parent / "fixtures" / "shortlist" / "golden_v02.json"
CREATED = date(2026, 11, 4)
TODAY = date(2026, 11, 7)
SEVEN = {c: 3 for c in brief_config.CRITERIA}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "ld", CREATED, playbook=CREATIVE_BRIEF)


def _seed_row(**kw) -> dict:
    base = {"schema": seeds.SCHEMA, "seed_id": "2026-10-20_sleep:t1", "source": "pb4", "run": "2026-10-20_sleep",
            "created": "2026-10-20", "category": "sleep", "sub_category": "lucid dreaming", "market": "US",
            "trend_id": "t1", "kind": "hook_trend", "trend_name": "Day _ of _", "bucket": "act_now",
            "band": "top 10%", "paid_level": "none", "angle": "A diary log.", "risk": "One language.",
            "valid_until": "2026-11-01", "report": None,
            "evidence": "runs/04-trend-research/2026-10-20_sleep/02_research/videos/t1*.json"}
    return {**base, **kw}


def _seeded(run: RunFolder, **kw) -> RunFolder:
    brief_config.start_from_seed(run, _seed_row(**kw))
    return run


def _card(run: RunFolder, tid: str = "t1", *, at: str | None = None, **kw) -> Path:
    card = {"id": tid, "kind": "hook_trend", "name": "Day _ of _", "status": "confirmed", "momentum": "rising",
            "visible_until": None, **kw}
    return trends.save_answer(run, "get_trend", {"trend_id": tid}, card, at=at)


def _evidence(run: RunFolder, value: str | None) -> None:
    s = state.load(run)
    s.evidence = value
    state.save(run, s)


def _write(run: RunFolder, stage: str, stem: str, data, version: int = 1) -> Path:
    path = run.path / stage / f"{stem}_v{version:02d}.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _ads(run: RunFolder, terms: str, advertisers=("Acme Sleep",)) -> Path:
    return trends.save_answer(run, "ads_library_search", {"search_terms": terms, "ad_reached_countries": ["US"]},
                              {"data": [{"page_name": a, "ad_creative_link_titles": [terms]} for a in advertisers]})


def _check(candidate: str, query: str, **kw) -> dict:
    return {"candidate": candidate, "query": query, "country": "US", "verdict": "competitor_found",
            "advertisers": ["Acme Sleep"], "own_ads": False, "note": "", **kw}


def _fields(problems) -> list[str]:
    return [p.field for p in problems]


def _text(problems) -> str:
    return "\n".join(f"{p.field}: {p.what} {p.todo}" for p in problems)


# --- the seed re-check (B3) ---------------------------------------------------------------------

@pytest.mark.parametrize("card", [{"momentum": "falling"}, {"momentum": "rising", "status": "contradicted"},
                                  {"momentum": None}])
def test_expired_seed_falling_is_dropped(run, card):
    _seeded(run)
    _card(run, **card)
    got = brief_research.seed_check(run, {}, today=TODAY)
    assert got["verdict"] == "drop"
    assert "2026-11-01" in got["why"] and "t1" in got["why"]
    assert state.load(run).brief["seed_check"] == got
    assert state.load(run).brief["seed"] == "2026-10-20_sleep:t1"        # the seed itself is kept


def test_expired_seed_holding_is_kept(run, capsys):
    _seeded(run)
    _card(run, momentum="rising", status="confirmed")
    _card(run, momentum="holding", status="unconfirmed")                 # the latest card counts: trend_t1_v02
    got = brief_research.seed_check(run, {}, today=TODAY)
    assert got == {"verdict": "keep", "why": got["why"], "valid_until": "2026-11-18"}   # 14 days from the run (CB8)
    assert "holding" in got["why"]
    _card(run, momentum="holding", visible_until="2026-12-01T00:00:00Z")
    assert brief_research.seed_check(run, {"brief": {"valid_days_default": 7}}, today=TODAY)["valid_until"] == "2026-12-01"

    # Not expired: kept as it is, no re-check needed.
    fresh = RunFolder.create(run.path.parents[2], "later", CREATED, playbook=CREATIVE_BRIEF)
    _seeded(fresh, valid_until="2026-11-30")
    got = brief_research.seed_check(fresh, {}, today=TODAY)
    assert (got["verdict"], got["valid_until"]) == ("keep", "2026-11-30") and "not expired" in got["why"]

    assert main(["brief", "seed-check", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["verdict"] == "keep"


def test_seed_without_fresh_card_is_unknown(run, capsys):
    _seeded(run)
    got = brief_research.seed_check(run, {}, today=TODAY)
    assert got["verdict"] == "unknown" and got["valid_until"] == "2026-11-01"
    assert "get_trend" in got["why"]
    # A card saved before the run was created is not a fresh one.
    _card(run, at="2026-10-21T09:00:00+00:00", momentum="rising")
    assert brief_research.seed_check(run, {}, today=TODAY)["verdict"] == "unknown"
    assert state.load(run).brief["seed_check"]["verdict"] == "unknown"

    assert main(["brief", "seed-check", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "unknown"

    plain = RunFolder.create(run.path.parents[2], "plain", CREATED, playbook=CREATIVE_BRIEF)
    assert main(["brief", "seed-check", "--run", str(plain.path), "--json"]) == 1   # no seed: a bad call
    assert "not started from a seed" in json.loads(capsys.readouterr().out)["message"]


def _warsaw():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Warsaw")
    except Exception:            # no tz database (Windows without tzdata): Warsaw is CET (UTC+1) in November
        return timezone(timedelta(hours=1), "CET")


def test_a_card_saved_after_local_midnight_is_fresh(ws, capsys, monkeypatch):
    """Part 3 ruling 2: the card's saved time and the run's created day are read on one clock. A run created on
    2026-11-08 in Warsaw and a card fetched there at 00:30 (2026-11-07T23:30Z) is a fresh card, never "unknown"."""
    monkeypatch.setattr(brief_research, "_zone", _warsaw)
    run = RunFolder.create(ws, "night", date(2026, 11, 8), playbook=CREATIVE_BRIEF)
    _seeded(run)
    _card(run, at="2026-11-07T23:30:00+00:00", momentum="rising")
    got = brief_research.seed_check(run, {}, today=date(2026, 11, 8))
    assert got["verdict"] == "keep", got
    assert "card of 2026-11-08" in got["why"]
    _card(run, at="2026-11-07T22:30:00+00:00", momentum="rising")   # 23:30 in Warsaw: the day before the run
    assert brief_research.seed_check(run, {}, today=date(2026, 11, 8))["verdict"] == "unknown"


# --- B3: trends_or_guess ------------------------------------------------------------------------

def _shortlist(run: RunFolder, entries: int, *, weak: int = 0, version: int = 1) -> Path:
    """A shortlist built now: its meta.inputs are the search files saved so far."""
    rows = [{"id": f"h{i}", "flags": []} for i in range(entries)]
    rows += [{"id": f"w{i}", "flags": ["weak fit (no term match)"]} for i in range(weak)]
    inputs = [f.relative_to(run.path).as_posix() for f in trends.search_files(run)]
    return _write(run, "03_wip", "trend_shortlist", {"meta": {"inputs": inputs}, "hooks": rows[:2],
                                                     "topics": rows[2:], "formats": [], "sounds": []}, version)


def _search(run: RunFolder, about: str, page: int = 1) -> Path:
    given = {"about": about, "limit": 20, **({"page": page} if page > 1 else {})}
    return trends.save_answer(run, "search_trends", given, {"data": [{"id": "h0", "kind": "hook_trend"}]})


def test_trends_gap_needs_shortlist_or_guess(run, monkeypatch):
    gap = brief_research.trends_gap(run)
    assert "tm evidence" in gap
    _evidence(run, "guess")
    assert brief_research.trends_gap(run) is None                         # guess mode: no trend slot to fill
    _evidence(run, "trendsmesh")
    gap = brief_research.trends_gap(run)
    assert "trend_shortlist" in gap and "trend_" in gap

    _shortlist(run, 2, weak=4)                                            # 2 relevant of 6: below min_relevant 5
    _card(run, "h0")
    _search(run, "lucid dreaming")
    _search(run, "lucid dreaming", page=2)                                # a second page: the same query
    old = trends.save_answer(run, "search_trends", {"about": "lucid dreaming"}, {"data": []})   # a repeat, _v02
    old.rename(old.with_name("search_dream_journal.json"))                # a name never counts as a query
    _search(run, "sleep tips")
    gap = brief_research.trends_gap(run)
    assert "2 distinct" in gap and "3" in gap
    _search(run, "Dream journal")
    gap = brief_research.trends_gap(run)                                  # three queries, but not ranked yet
    assert "shortlist ranks the widened searches" in gap and "search_dream_journal_v02.json" in gap
    _shortlist(run, 2, weak=4, version=2)
    assert brief_research.trends_gap(run) is None                         # three queries, ranked: CB2's expansion done
    _shortlist(run, 5, version=3)
    for f in trends.search_files(run)[1:]:
        f.unlink()
    assert brief_research.trends_gap(run) is None                         # 5 relevant: no expansion needed

    _seeded(run)                                                          # expired on 2026-11-01
    monkeypatch.setattr(brief_research, "_today", lambda: TODAY)
    assert "fetch get_trend of t1" in brief_research.trends_gap(run)
    brief_research.seed_check(run, {}, today=TODAY)                       # unknown: not a re-check yet
    assert "fetch get_trend of t1" in brief_research.trends_gap(run)
    _card(run, "t1", momentum="holding")
    assert "seed-check --run R again" in brief_research.trends_gap(run)
    brief_research.seed_check(run, {}, today=TODAY)
    assert brief_research.trends_gap(run) is None
    assert stepchecks.run("trends_or_guess", run) is None                 # through tm done's resolver too


def test_a_search_answer_that_holds_no_cards_is_no_query(run):
    """A saved search whose answer is not JSON (`{"raw": ...}`: a "too large" notice saved before the
    collector refused them, or by hand) or an error is not a query: not counted toward CB2's three, not
    unranked, not read by the shortlist."""
    _evidence(run, "trendsmesh")
    _card(run, "h0")
    _search(run, "lucid dreaming")
    trends.save_answer(run, "search_trends", {"about": "sleep tips"}, {"raw": "Error: result exceeds maximum..."})
    trends.save_answer(run, "search_trends", {"about": "dream journal"}, {"error": {"code": 429}})
    assert [f.name for f in trends.search_files(run)] == ["search_lucid_dreaming.json"]
    assert brief_research.searched_queries(run) == {research_checks.key("lucid dreaming")}
    _shortlist(run, 2, weak=4)
    gap = brief_research.trends_gap(run)
    assert "1 distinct" in gap and "sleep" not in gap and "dream_journal" not in gap
    from tm import shortlist
    research = run.path / trends.RESEARCH / "search"
    pool, found_by = shortlist.load_pool(sorted(research.glob("*.json")))
    assert list(pool) == ["h0"] and found_by == {"h0": ["lucid dreaming"]}


def test_seed_checked_before_its_falling_card_reopens_b3(run, monkeypatch):
    """The review's probe: seed-check before get_trend stores unknown; a falling card saved after it
    must not let B3 close on that unknown."""
    monkeypatch.setattr(brief_research, "_today", lambda: TODAY)
    _seeded(run)
    _evidence(run, "trendsmesh")
    _shortlist(run, 5)
    assert brief_research.seed_check(run, {}, today=TODAY)["verdict"] == "unknown"
    _card(run, "t1", momentum="falling")
    gap = brief_research.trends_gap(run)
    assert "now says drop" in gap and "tm brief seed-check" in gap
    assert state.load(run).brief["seed_check"]["verdict"] == "unknown"     # the gap only reads
    assert brief_research.seed_check(run, {}, today=TODAY)["verdict"] == "drop"
    assert brief_research.trends_gap(run) is None


def test_guess_run_accepts_any_stored_seed_check(run, monkeypatch):
    monkeypatch.setattr(brief_research, "_today", lambda: TODAY)
    _seeded(run)
    _evidence(run, "guess")
    gap = brief_research.trends_gap(run)
    assert "tm brief seed-check" in gap and "when TrendsMesh answers" in gap
    brief_research.seed_check(run, {}, today=TODAY)                       # unknown: no card can be fetched
    assert brief_research.trends_gap(run) is None


def _error_card(run: RunFolder, tid: str = "t1") -> Path:
    """get_trend failing as the collector saves it: an isError result becomes {"error": ...}."""
    answer, _ = trend_spool.parse_answer({"isError": True, "content": [{"type": "text", "text": "Trend not found"}]})
    assert answer == {"error": {"raw": "Trend not found"}}
    return trends.save_answer(run, "get_trend", {"trend_id": tid}, answer)


def test_error_answer_is_not_a_trend_card(run, monkeypatch):
    """The whole-PR review's reproduction: an expired seed and a saved get_trend error. It once gave
    drop ("momentum not given"), counted as B3's card and passed as a B4 candidate."""
    monkeypatch.setattr(brief_research, "_today", lambda: TODAY)
    _seeded(run)
    _evidence(run, "trendsmesh")
    _shortlist(run, 5)
    _error_card(run)
    got = brief_research.seed_verdict(run, {}, today=TODAY)
    assert got["verdict"] == "unknown"
    assert "error answer" in got["why"] and "Trend not found" in got["why"] and "again" in got["why"]
    gap = brief_research.trends_gap(run)
    assert "at least one trend card is saved" in gap and "fetch them again" in gap
    assert "error answer" in gap and "get_trend of t1 again" in gap
    text = _text(brief_research.check_scores(run, {"t1": SEVEN}, {}))
    assert "t1 has no trend card" in text and "error answer" in text and "again" in text
    damaged = run.path / "02_research" / "trend_t1_v02.json"
    damaged.write_text("{cut sh", encoding="utf-8")                      # a damaged card is named, not hidden
    assert "cannot be read" in brief_research.seed_verdict(run, {}, today=TODAY)["why"]

    # Fetched again: a card in PB04's `data` wrapper counts, its momentum read inside it.
    trends.save_answer(run, "get_trend", {"trend_id": "t1"},
                       {"data": {"id": "t1", "kind": "hook_trend", "status": "confirmed", "momentum": "falling"}})
    assert brief_research.seed_verdict(run, {}, today=TODAY)["verdict"] == "drop"
    assert brief_research.check_scores(run, {"t1": SEVEN}, {}) == []
    brief_research.seed_check(run, {}, today=TODAY)
    assert brief_research.trends_gap(run) is None


@pytest.mark.private_data
def test_ld_shortlist_runs_on_built_run(ws, capsys):
    run = ld.build(ws)
    assert (run.path / "01_base" / ld.TARGETING).is_file()
    assert (run.path / "02_research" / "voice" / "items.jsonl").is_file()
    assert main(["trends", "shortlist", "--run", str(run.path), "--terms", test_shortlist.TERMS,
                 "--today", "2026-11-04", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    mine = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    def by_id(payload):
        return {r["id"]: {**r, "found_by": sorted(r["found_by"])}
                for key in ("hooks", "topics", "formats", "sounds") for r in payload[key]}
    assert by_id(mine) == by_id(golden)
    top = [r["id"] for r in mine["hooks"]]
    assert any(i.startswith("c2173b6a") for i in top) and any(i.startswith("11bfc2ef") for i in top)
    _evidence(run, "trendsmesh")
    assert brief_research.trends_gap(run) is None


# --- B4: scores ---------------------------------------------------------------------------------

def test_scores_need_all_seven_in_range(run):
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _card(run, "t2")
    assert brief_research.check_scores(run, {"t1": SEVEN, "t2": {**SEVEN, "bridge": 5}}, {}) == []
    wrong = {"t1": {**SEVEN, "bridge": 6}, "t2": {k: v for k, v in SEVEN.items() if k != "feasibility"}}
    text = _text(brief_research.check_scores(run, wrong, {}))
    assert "bridge 6 is outside 1-5" in text and "lack feasibility" in text
    for bad in (0, 2.5, True, "3", None):
        assert brief_research.check_scores(run, {"t1": {**SEVEN, "transfer": bad}}, {}), bad
    assert "growth is not a criterion" in _text(brief_research.check_scores(run, {"t1": {**SEVEN, "growth": 3}}, {}))
    assert brief_research.check_scores(run, {}, {})                       # nothing scored
    assert brief_research.check_scores(run, [SEVEN], {})                  # not a table

    weights = {**{c: 1 for c in brief_config.CRITERIA}, "bridge": 3}
    assert brief_research.totals({"t1": SEVEN, "t2": {**SEVEN, "bridge": 5}, "bad": {"bridge": 9}}, weights) == {
        "t1": 3.0, "t2": round((6 * 3 + 3 * 5) / 9, 2)}


def test_guess_candidate_refused_in_trendsmesh_run(run):
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    text = _text(brief_research.check_scores(run, {"t1": SEVEN, "guess:diary-log": SEVEN}, {}))
    assert "guess:diary-log" in text and "guess" in text
    assert "t9" in _text(brief_research.check_scores(run, {"t9": SEVEN}, {}))          # no saved card
    assert brief_research.check_scores(run, {"../t1": SEVEN}, {})                     # not a trend id
    _evidence(run, None)
    assert "has not recorded its evidence" in _text(brief_research.check_scores(run, {"guess:diary-log": SEVEN}, {}))
    _evidence(run, "guess")
    assert brief_research.check_scores(run, {"guess:diary-log": SEVEN}, {}) == []
    assert brief_research.check_scores(run, {"guess:": SEVEN}, {})                    # no slug
    assert brief_research.check_scores(run, {"guess:Diary Log": SEVEN}, {})           # not a slug


# --- B4: saturation (CB4) -----------------------------------------------------------------------

def test_saturation_finds_answer_by_saved_input_not_name(run):
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _write(run, "03_wip", "scores", {"t1": SEVEN})
    saved = _ads(run, "lucid dream mask")
    saved.rename(saved.with_name("ads_something_else.json"))              # the name does not matter
    data = {"checks": [_check("t1", "lucid dream mask")]}
    assert brief_research.check_saturation(run, data, {}) == []
    # A file named after the query whose _input ran another one is not its answer.
    other = run.path / "02_research" / "ad_library" / "ads_dream_journal.json"
    other.write_text(json.dumps({"_tool": "ads_library_search", "_input": {"search_terms": "sleep mask"},
                                 "_at": "2026-11-04T10:00:00+00:00", "answer": {"data": []}}), encoding="utf-8")
    text = _text(brief_research.check_saturation(run, {"checks": [_check("t1", "dream journal")]}, {}))
    assert "'dream journal'" in text and "ad_library" in text


@pytest.mark.parametrize("level", seeds.PAID_LEVELS)
def test_saturation_needs_every_candidate_and_saved_answers(run, level):
    _seeded(run, trend_id="t1", paid_level=level)                         # seed_paid is a hint, never a check
    assert state.load(run).brief["seed_paid"] == brief_config.SEED_PAID[level]
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _card(run, "t2")
    assert "scores" in _text(brief_research.check_saturation(run, {"checks": []}, {}))     # nothing scored yet
    _write(run, "03_wip", "scores", {"t1": SEVEN, "t2": SEVEN})
    _ads(run, "dream journal")
    text = _text(brief_research.check_saturation(run, {"checks": [_check("t2", "dream journal")]}, {}))
    assert "t1" in text and "no saturation check" in text                 # the seed's hint is not a check
    rows = [_check("t1", "lucid dream mask"), _check("t2", "dream journal", advertisers=[])]
    text = _text(brief_research.check_saturation(run, {"checks": rows}, {}))
    assert "'lucid dream mask'" in text                                   # searched, but never saved
    assert "names no advertiser" in text
    _ads(run, "lucid dream mask")
    rows = [_check("t1", "lucid dream mask", verdict="none_found", advertisers=[]),
            _check("t2", "Dream  Journal")]                               # case and spacing aside
    assert brief_research.check_saturation(run, {"checks": rows}, {}) == []
    for broken in ({"checks": [{**rows[0], "verdict": "unused"}]}, {"checks": [{**rows[0], "own_ads": "no"}]},
                   {"checks": "none"}, {"rows": []}, []):
        assert brief_research.check_saturation(run, broken, {}), broken


def test_unused_wording_refused(run):
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _write(run, "03_wip", "scores", {"t1": SEVEN})
    _ads(run, "dream journal")
    for phrase in ("This hook is unused", "Not in ads yet", "No one advertises this", "Fresh in paid"):
        data = {"checks": [_check("t1", "dream journal", verdict="none_found", advertisers=[], note=phrase)]}
        problems = brief_research.check_saturation(run, data, {})
        assert _fields(problems) == ["checks[0].note"], phrase
        assert research_checks.NONE_FOUND in problems[0].todo
    # Copied Ad Library data is not the agent's claim, and words only count whole.
    _ads(run, "unused planner", advertisers=("Unusedgoods", "Unused Media"))
    data = {"checks": [_check("t1", "unused planner", advertisers=["Unusedgoods", "Unused Media"],
                              note="Not in adsets yet; the titles name planners.")]}
    assert brief_research.check_saturation(run, data, {}) == []
    data["checks"][0]["note"] = "unused"
    assert _fields(brief_research.check_saturation(run, data, {})) == ["checks[0].note"]
    words = {"not in ads": ("x", "y")}
    texts = {"a": "Not in adsets", "b": "kept not in ads.", "c": "(Not in ads)", "d": "notin ads"}
    assert [p.field for p in research_checks.wording(texts, words)] == ["b", "c"]
    assert research_checks.wording is research_checks._wording and research_checks.strings is research_checks._strings


def test_commands_mark_the_files_and_scoring_gap_needs_both_fresh(run, capsys):
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _ads(run, "dream journal")
    gap = brief_research.scoring_gap(run)
    assert "scores" in gap and "saturation" in gap
    scores = _write(run, "03_wip", "scores", {"t1": {**SEVEN, "bridge": 9}})
    assert main(["brief", "scores", "--run", str(run.path), "--file", str(scores), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and out["problems"]
    scores = _write(run, "03_wip", "scores", {"t1": SEVEN}, version=2)
    assert main(["brief", "scores", "--run", str(run.path), "--file", "03_wip/scores_v02.json", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["totals"] == {"t1": 3.0}
    sat = _write(run, "02_research", "saturation",
                 {"checks": [_check("t1", "dream journal", verdict="none_found", advertisers=[])]})
    assert main(["brief", "saturation", "--run", str(run.path), "--file", str(sat), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
    assert brief_research.scoring_gap(run) is None
    assert stepchecks.run("scores_and_saturation", run) is None
    scores.write_text(json.dumps({"t1": {**SEVEN, "bridge": 4}}), encoding="utf-8")   # changed after the check
    assert "changed after it was checked" in brief_research.scoring_gap(run)

    # Scores re-checked after the saturation check: the saturation is stale, though its file is not.
    _card(run, "t2")
    _ads(run, "sleep mask")
    _write(run, "03_wip", "scores", {"t1": SEVEN, "t2": SEVEN}, version=3)
    assert main(["brief", "scores", "--run", str(run.path), "--file", "03_wip/scores_v03.json", "--json"]) == 0
    capsys.readouterr()
    gap = brief_research.scoring_gap(run)
    assert "checked against the latest scores" in gap and "tm brief saturation" in gap
    assert main(["brief", "saturation", "--run", str(run.path), "--file", str(sat), "--json"]) == 2   # t2 unchecked
    capsys.readouterr()
    sat = _write(run, "02_research", "saturation",
                 {"checks": [_check("t1", "dream journal", verdict="none_found", advertisers=[]),
                             _check("t2", "sleep mask")]}, version=2)
    assert main(["brief", "saturation", "--run", str(run.path), "--file", str(sat), "--json"]) == 0
    capsys.readouterr()
    assert state.load(run).checked["saturation"]["scores"]["file"] == "03_wip/scores_v03.json"
    assert brief_research.scoring_gap(run) is None

    assert main(["brief", "scores", "--run", str(run.path), "--file", str(sat), "--json"]) == 1   # wrong name
    capsys.readouterr()
    broken = _write(run, "03_wip", "scores", "{not json", version=4)
    assert main(["brief", "scores", "--run", str(run.path), "--file", str(broken), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"


def test_check_commands_take_a_file_relative_to_the_working_folder(ws, run, capsys, monkeypatch):
    """Run from the workspace with relative --run and --file (the way PB04's map --split reads it):
    checked and marked as the same file."""
    _evidence(run, "trendsmesh")
    _card(run, "t1")
    _ads(run, "dream journal")
    _write(run, "03_wip", "scores", {"t1": SEVEN})
    _write(run, "02_research", "saturation",
           {"checks": [_check("t1", "dream journal", verdict="none_found", advertisers=[])]})
    monkeypatch.chdir(ws)
    rel_run = run.path.relative_to(ws).as_posix()
    for action, file in (("scores", "03_wip/scores_v01.json"), ("saturation", "02_research/saturation_v01.json")):
        assert main(["brief", action, "--run", rel_run, "--file", f"{rel_run}/{file}", "--json"]) == 0, action
        out = json.loads(capsys.readouterr().out)
        assert (out["status"], out["file"]) == ("done", file)
        assert state.load(run).checked[action]["file"] == file
    assert brief_research.scoring_gap(run) is None
