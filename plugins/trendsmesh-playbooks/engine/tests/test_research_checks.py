"""tm.research_checks: the checks of what the agent writes (TR3-TR7) and the evidence dump (D1).

The beauty run (beauty.py) is mapped and grown as of 4 Nov 2026 with all three outputs chosen, and
gets the reference picks_v04 and digest. The reference Ad Library answers came back inline and were never saved
(ruling F7a), so the passing paid test saves one stub answer per query, the way the collector does,
and sets `checked: true`. The reference picks have no score table (decision 13): the tests add one.
"""

import copy
import json
import shutil
from datetime import date, timedelta

import pytest

import beauty
from tm import config, research_checks, research_config, research_growth, research_map, state, trends
from tm.cli import main
from tm.runfolder import RunFolder

pytestmark = pytest.mark.private_data

AS_OF = date(2026, 11, 4)
ALL = ["category_report", "weekly_digest", "paid_view"]
CAT_EYE = "d8c752a4308f426a9bea2278f872a118"
YOUR_SIGN = "0bae5424d00e4bbb809e9cbc511dea9a"
GRWM = "ca3e4c080b7a4b42a55af31d5072bc43"
SEPHORA = "10686ae92ed740c08d9f6a1fa73023dd"
SKINCARE = "2460b8b9d3d44c44a4de778788f07ce3"   # too late with 32 creators: in the paid scope
CURLY_VS_STRAIGHT = "8bc7decd020f46d69266275f59327a70"


def _summary() -> dict:
    return beauty.handoff("02_research/ad_library_summary_v02.json")


def _picks() -> dict:
    return beauty.handoff("03_wip/picks_v04.json")


def _scores(picks: dict) -> dict:
    """A score table for every pick: 3 everywhere, 5 for the first pick's growth."""
    ids = [p["id"] for p in picks["act_now"] + picks["still_rising"]]
    table = {i: {c: 3 for c in research_config.CRITERIA} for i in ids}
    table[ids[0]]["growth"] = 5
    return table


def _scored() -> dict:
    picks = _picks()
    picks["scores"] = _scores(picks)
    return picks


def _cfg(run: RunFolder) -> dict:
    return research_map.settings(config.load(run))


def _stubs(run: RunFolder, summary: dict) -> None:
    """One saved Ad Library answer per query of the summary, as the collector saves them."""
    queries = {research_checks.ad_query(c["query"]) for c in summary["checks"] if c.get("query")}
    for q in sorted(queries):
        trends.save_answer(run, "ads_library_search", {"search_terms": q, "ad_reached_countries": ["US"]},
                           {"data": []}, at=beauty.AT)


@pytest.fixture(scope="module")
def grown(tmp_path_factory):
    """The beauty run with all three outputs, grown as of 4 Nov, with the reference picks_v04 and digest."""
    run = beauty.mapped_run(tmp_path_factory.mktemp("beauty"))
    research_config.write_from_intake(run, {"category": {"inputs": [beauty.ROOT], "phrase": beauty.ROOT, "seeds": []},
                                            "market": "US", "language": "en", "outputs": ALL})
    research_growth.compute(run, AS_OF, _cfg(run))
    beauty.copy_input(run, "02_research/digest.json")
    beauty.copy_input(run, "03_wip/picks_v04.json")
    return run


@pytest.fixture(scope="module")
def stubbed(grown, tmp_path_factory):
    """`grown` copied, with one saved Ad Library answer per query of the reference summary."""
    ws = tmp_path_factory.mktemp("stubbed") / "ws"
    shutil.copytree(grown.path.parents[2], ws)
    run = RunFolder.open(ws / grown.path.relative_to(grown.path.parents[2]))
    _stubs(run, _summary())
    return run


def _copy(run: RunFolder, tmp_path) -> RunFolder:
    ws = tmp_path / "ws"
    shutil.copytree(run.path.parents[2], ws)
    return RunFolder.open(ws / run.path.relative_to(run.path.parents[2]))


def _row(summary: dict, trend_id: str) -> dict:
    return next(c for c in summary["checks"] if c["trend_id"] == trend_id)


def _texts(problems) -> str:
    return "\n".join(f"{p.field}: {p.what} {p.todo}" for p in problems)


# --- the Ad Library reading (TR7) -------------------------------------------------------------

def test_beauty_paid_summary_v02_passes(stubbed, tmp_path, capsys):
    summary = {**_summary(), "checked": True}
    assert research_checks.check_paid(stubbed, summary, _cfg(stubbed)) == []

    # "Hair loss remedies" is crowded with 2 advertisers and a very large estimate (F7a)
    hair_loss = _row(summary, "2c9fede033614811b0933f9680b6849f")
    assert hair_loss["level"] == "crowded" and len(hair_loss["advertisers"]) == 2

    # a saved answer is found by its saved query, never by its file name
    folder = stubbed.path / "02_research" / "ad_library"
    sephora = next(f for f in folder.iterdir() if trends.read(f)["_input"]["search_terms"] == "Sephora Savings Event")
    other = _copy(stubbed, tmp_path)
    (other.path / "02_research" / "ad_library" / sephora.name).rename(other.path / "02_research" / "ad_library" / "ads_x.json")
    assert research_checks.check_paid(other, summary, _cfg(other)) == []

    file = tmp_path / "ad_library_summary_v01.json"
    file.write_text(json.dumps(summary), encoding="utf-8")
    assert main(["research", "paid", "check", "--run", str(stubbed.path), "--file", str(file), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "problems": [],
                                                    "message": "The Ad Library reading holds: 30 checks, all in "
                                                               "scope, each with its saved answer."}


def test_hook_with_a_level_other_than_not_checkable_fails(stubbed):
    summary = {**_summary(), "checked": True}
    _row(summary, GRWM)["level"] = "none"
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1
    assert "get ready with _ to _" in problems[0].what and "Not checkable without Foreplay" in problems[0].what
    assert "not_checkable" in problems[0].todo


def test_found_with_five_advertisers_fails(stubbed):
    summary = {**_summary(), "checked": True}
    _row(summary, CURLY_VS_STRAIGHT)["advertisers"] = ["A", "B", "C", "D", "E"]
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1
    assert "Curly vs straight hair content" in problems[0].what and "5 advertisers" in problems[0].what
    assert "crowded" in problems[0].todo

    # crowded needs 4 advertisers or a numeric estimate
    summary = {**_summary(), "checked": True}
    hair_loss = _row(summary, "2c9fede033614811b0933f9680b6849f")
    hair_loss["estimated"] = None
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1 and "Hair loss remedies" in problems[0].what


def test_not_in_ads_wording_fails(stubbed):
    summary = {**_summary(), "checked": True}
    _row(summary, CAT_EYE)["note"] = "Cat-eye is Not in ads yet"
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1
    assert '"none found in Ad Library titles"' in problems[0].todo


def test_meta_unavailable_needs_no_saved_answers(grown):
    hooks = [c for c in _summary()["checks"] if c["level"] == "not_checkable"]
    summary = {**_summary(), "checked": False, "checks": hooks}
    assert not (grown.path / "02_research" / "ad_library").exists()
    assert research_checks.check_paid(grown, summary, _cfg(grown)) == []

    # checked, the same rows need their answers and the scope
    problems = research_checks.check_paid(grown, {**summary, "checked": True}, _cfg(grown))
    assert any("get ready with me" in p.what and "02_research/ad_library" in p.what for p in problems)
    assert any(p.field == "checks" and "Cat-eye magnetic nail art manicures" in p.what for p in problems)

    # unchecked, nothing can have a level read from the Ad Library
    summary = {**_summary(), "checked": False}
    problems = research_checks.check_paid(grown, summary, _cfg(grown))
    assert problems and all("checked is false" in p.what for p in problems)

    # checked must be said
    problems = research_checks.check_paid(grown, {k: v for k, v in _summary().items()}, _cfg(grown))
    assert [p.field for p in problems if p.field == "checked"] == ["checked"]


def test_paid_scope_follows_the_paid_view(stubbed):
    summary = {**_summary(), "checked": True}
    summary["checks"] = [c for c in summary["checks"] if c["trend_id"] != SKINCARE]
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1 and "Skincare routines and product demos" in problems[0].what

    # without the paid view, the scope is the picks only (skincare is not one)
    cfg = {**_cfg(stubbed), "outputs": ["category_report", "weekly_digest"]}
    assert research_checks.check_paid(stubbed, summary, cfg) == []
    picks = _picks()
    summary["checks"] = [c for c in summary["checks"] if c["trend_id"] != CAT_EYE]
    problems = research_checks.check_paid(stubbed, summary, cfg)
    assert len(problems) == 1 and "Cat-eye magnetic nail art manicures" in problems[0].what
    assert CAT_EYE in [p["id"] for p in picks["act_now"]]


# --- the picks (TR3-TR6) ----------------------------------------------------------------------

def test_beauty_picks_v04_with_scores_passes(grown, tmp_path, capsys):
    picks = _scored()
    before = copy.deepcopy(picks)
    files = sorted(p.name for p in (grown.path / "03_wip").iterdir())
    assert research_checks.check_picks(grown, picks, _cfg(grown)) == []
    assert picks == before and sorted(p.name for p in (grown.path / "03_wip").iterdir()) == files

    # TR5: the weighted total of each pick, by scoring.weights (default: every criterion 1)
    totals = research_checks.weighted_totals(picks, _cfg(grown))
    assert totals[CAT_EYE] == 23 and totals[CURLY_VS_STRAIGHT] == 21 and len(totals) == 9
    cfg = _cfg(grown)
    cfg["scoring"]["weights"] = {**cfg["scoring"]["weights"], "growth": 2, "fit": 0}
    assert research_checks.weighted_totals(picks, cfg)[CAT_EYE] == 25

    file = tmp_path / "picks_v05.json"
    file.write_text(json.dumps(picks), encoding="utf-8")
    assert main(["research", "picks", "check", "--run", str(grown.path), "--file", str(file), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["problems"] == [] and out["totals"][CAT_EYE] == 23


def test_picks_outputs_map_to_the_runs(grown):
    picks = _scored()
    picks["outputs"] = ["report", "paid"]
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["outputs"]
    assert research_config.PICK_OUTPUTS == {"category_report": "report", "weekly_digest": "digest",
                                            "paid_view": "paid"}

    # report only: no paid reading and no digest reading
    cfg = {**_cfg(grown), "outputs": ["category_report"]}
    picks = _scored()
    picks["outputs"] = ["report"]
    fields = sorted(p.field for p in research_checks.check_picks(grown, picks, cfg))
    assert fields == ["digest_reading", "paid_reading"]
    del picks["digest_reading"], picks["paid_reading"]
    assert research_checks.check_picks(grown, picks, cfg) == []


def test_move_without_reason_fails(grown, tmp_path, capsys):
    picks = _scored()
    picks["moves"][0]["why"] = "Event-bound."
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert len(problems) == 1
    assert "Sephora Savings Event sale hauls and picks" in problems[0].what and "Moved by review" in problems[0].what

    picks = _scored()
    picks["moves"].append({"id": CURLY_VS_STRAIGHT, "from": "still_rising", "to": "too_late",
                           "why": "Crowded in paid with straightener ads in every top title."})
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert any("only from act_now" in p.what for p in problems)

    picks = _scored()
    del picks["moves"][1]["why"]
    file = tmp_path / "picks_v05.json"
    file.write_text(json.dumps(picks), encoding="utf-8")
    assert main(["research", "picks", "check", "--run", str(grown.path), "--file", str(file), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and [p["field"] for p in out["problems"]] == ["moves"]
    assert "the run continues from the same place" in out["message"]


def test_pick_outside_its_bucket_fails(grown):
    picks = _scored()
    picks["act_now"].append({"id": SEPHORA, "what": "Sale hauls.", "how": "Post a haul.", "risk": "Ends 9 Nov."})
    picks["scores"][SEPHORA] = {c: 2 for c in research_config.CRITERIA}
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert len(problems) == 1
    assert "Sephora Savings Event sale hauls and picks" in problems[0].what and "too late" in problems[0].what

    # counts at most picks.*, and every pick says what, how and risk
    cfg = _cfg(grown)
    cfg["picks"] = {**cfg["picks"], "act_now": 3}
    picks = _scored()
    picks["still_rising"][0]["risk"] = " "
    fields = sorted(p.field for p in research_checks.check_picks(grown, picks, cfg))
    assert fields == ["act_now", "still_rising"]


def test_sensitive_pick_needs_the_word_in_its_risk(grown, tmp_path):
    run = _copy(grown, tmp_path)
    growth = run.latest("02_research", "growth", "json")
    data = json.loads(growth.read_text(encoding="utf-8"))
    next(r for r in data["trends"] if r["id"] == CAT_EYE)["plugin"]["sensitive_videos"] = 2
    growth.with_name("growth_v02.json").write_text(json.dumps(data), encoding="utf-8")
    picks = _scored()
    problems = research_checks.check_picks(run, picks, _cfg(run))
    assert len(problems) == 1 and "2 sensitive videos" in problems[0].what
    picks["act_now"][0]["risk"] += " Two evidence videos are flagged sensitive."
    assert research_checks.check_picks(run, picks, _cfg(run)) == []


def test_missing_scores_fail(grown):
    picks = _picks()
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["scores"]
    assert "TR5" in problems[0].what

    picks = _scored()
    del picks["scores"][CURLY_VS_STRAIGHT]
    picks["scores"][CAT_EYE]["fit"] = 6
    picks["scores"][YOUR_SIGN].pop("feasibility")
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    text = _texts(problems)
    assert len(problems) == 3
    assert "Curly vs straight hair content" in text and "fit 6" in text and "feasibility" in text


def test_picks_say_their_date_market_and_category(grown, tmp_path, capsys):
    picks = _scored()
    picks["as_of"] = "4 Nov 2026"
    del picks["market"]
    picks["category"] = "  "
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["as_of", "market", "category"]
    text = _texts(problems)
    assert "not a date (YYYY-MM-DD)" in text and "The picks have no market." in text
    assert "The picks have no category." in text
    picks["as_of"] = None
    assert [p.field for p in research_checks.check_picks(grown, picks, _cfg(grown))][:1] == ["as_of"]


def test_checks_stop_on_a_run_without_growth(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "nails", AS_OF, playbook=beauty.TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    picks = tmp_path / "picks_v01.json"
    picks.write_text(json.dumps(_scored()), encoding="utf-8")
    for args in (["picks", "check", "--file", str(picks)], ["evidence", "--trend", CAT_EYE],
                 ["report", "--picks", str(picks)]):
        capsys.readouterr()
        assert main(["research", *args, "--run", str(run.path), "--json"]) == 2, args
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "stop" and "no growth yet" in out["message"], out
        assert "same place" in out["message"]


def test_picks_wording_and_ids(grown):
    picks = _scored()
    picks["watch_next"] = "There are no trends in the category for holidays yet."
    picks["paid_reading"][0] = "Cat-eye nails: no one advertises it."
    picks["lens"]["items"].append({"id": "ffffffffffffffffffffffffffffffff", "line": "Lead with this."})
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    text = _texts(problems)
    assert len(problems) == 3
    assert '"weak match"' in text and '"none found in Ad Library titles"' in text
    assert "ffffffffffffffffffffffffffffffff" in text and "lens" in text


# --- the evidence dump (D1) -------------------------------------------------------------------

def _top(run: RunFolder, trend_id: str, ref: date, n: int) -> list[dict]:
    vids = trends.load_videos(run, trend_id)
    recent = [v for v in vids if v.get("published")
              and ref - timedelta(days=45) < research_growth.d(v["published"]) <= ref]
    return sorted(recent or vids, key=lambda v: -(v.get("views") or 0))[:n]


def test_evidence_dump_lists_top_videos_with_links(grown, tmp_path, capsys):
    run = _copy(grown, tmp_path)
    ref = AS_OF - timedelta(days=2)
    assert main(["research", "evidence", "--run", str(run.path), "--trend", CAT_EYE, "--top", "3", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    dump = run.path / "03_wip" / "evidence_dump_v01.txt"
    assert out["file"] == "03_wip/evidence_dump_v01.txt" and out["appended"] is False
    top = _top(run, CAT_EYE, ref, 3)
    assert [v["url"] for v in out["videos"]] == [v["url"] for v in top]
    first = out["videos"][0]
    assert set(first) == {"published", "creator", "views", "url", "hook_text", "slot_fill", "appears_at_s",
                          "excerpt", "sensitive"}
    assert first["creator"] == trends.creator_of(top[0]) and first["views"] == top[0]["views"]
    assert len(first["excerpt"]) <= 140
    text = dump.read_text(encoding="utf-8")
    assert "Cat-eye magnetic nail art manicures" in text and all(v["url"] in text for v in top)

    # the same step: the next trend is appended to the same dump, its text printed
    assert main(["research", "evidence", "--run", str(run.path), "--trend", YOUR_SIGN]) == 0
    printed = capsys.readouterr().out
    assert "your sign to _" in printed and all(v["url"] in printed for v in _top(run, YOUR_SIGN, ref, 5))
    assert sorted(p.name for p in (run.path / "03_wip").glob("evidence_dump_v*.txt")) == ["evidence_dump_v01.txt"]
    text = dump.read_text(encoding="utf-8")
    assert "Cat-eye magnetic nail art manicures" in text and "your sign to _" in text

    # another step starts a new dump, never rewriting the first
    s = state.load(run)
    s.step = "D3"
    state.save(run, s)
    assert main(["research", "evidence", "--run", str(run.path), "--trend", CAT_EYE, "--top", "1"]) == 0
    capsys.readouterr()
    assert dump.read_text(encoding="utf-8") == text
    assert (run.path / "03_wip" / "evidence_dump_v02.txt").is_file()

    # a trend not in the latest growth is refused
    assert main(["research", "evidence", "--run", str(run.path), "--trend", "nope"]) == 1
    assert "not in the latest growth" in capsys.readouterr().out


# --- carried review follow-ups (Task 11) ------------------------------------------------------

def test_act_now_other_accepts_moved_and_act_now_ids(grown):
    picks = _scored()
    picks["act_now_other"] = [{"id": SEPHORA, "note": "Event-bound: the sale ends 9 Nov."}]      # moved by review
    assert research_checks.check_picks(grown, picks, _cfg(grown)) == []
    picks["act_now_other"].append({"id": SKINCARE, "note": "Crowded."})                             # too late, not moved
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["act_now_other"]
    assert "Skincare routines and product demos" in problems[0].what


def test_move_to_outside_the_allowed_stages_fails(grown):
    picks = _scored()
    picks["moves"][0]["to"] = "gone"
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert any(p.field == "moves" and "moved to 'gone'" in p.what for p in problems)
    assert "still_rising, too_late, past_peak" in _texts(problems)


def test_readings_are_needed_by_the_views_they_feed(grown):
    picks = _scored()
    del picks["paid_reading"]
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["paid_reading"] and "paid view is chosen" in problems[0].what

    picks = _scored()
    del picks["digest_reading"]
    assert grown.latest("02_research", "digest", "json") is not None                 # this run has a digest
    problems = research_checks.check_picks(grown, picks, _cfg(grown))
    assert [p.field for p in problems] == ["digest_reading"] and "has a digest" in problems[0].what


def test_checkable_row_without_a_query_fails(stubbed):
    summary = {**_summary(), "checked": True}
    del _row(summary, CAT_EYE)["query"]
    problems = research_checks.check_paid(stubbed, summary, _cfg(stubbed))
    assert len(problems) == 1
    assert "Cat-eye magnetic nail art manicures has a level but no query" in problems[0].what


def test_saved_query_by_q_and_a_damaged_answer(stubbed, tmp_path):
    summary = {**_summary(), "checked": True}
    run = _copy(stubbed, tmp_path)
    folder = run.path / "02_research" / "ad_library"
    sephora = next(f for f in folder.iterdir() if trends.read(f)["_input"]["search_terms"] == "Sephora Savings Event")
    data = trends.read(sephora)
    data["_input"] = {"q": "Sephora Savings Event"}                       # the q fallback of ad_terms
    sephora.write_text(json.dumps(data), encoding="utf-8")
    assert research_checks.check_paid(run, summary, _cfg(run)) == []

    (folder / "ads_cut_short.json").write_text('{"_tool": "ads_library_search", "_in', encoding="utf-8")
    problems = research_checks.check_paid(run, summary, _cfg(run))
    assert [p.field for p in problems] == ["ad_library"]
    assert "02_research/ad_library/ads_cut_short.json" in problems[0].what
