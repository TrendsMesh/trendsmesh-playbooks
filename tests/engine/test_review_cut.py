"""Issue #129, part 1: the engine sets the obvious cases aside, so the agent reviews at most 50 mapped trends (B3)
and scores at most 50 hooks (B4); everything above the cut is listed as set aside and can be restored."""

import json
from datetime import date

import pytest

from tm import brief_config, research_config, research_growth, research_map, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop

SPLIT = {"root": "nails", "queries": [{"query": "nails", "parent": None, "depth": 0, "source": "seed"}]}


def _card(i: int, score: float, **extra) -> dict:
    return {"id": f"t{i:03d}", "kind": "topic_trend", "name": f"Trend {i:03d}", "status": "confirmed",
            "what_it_is": f"nail video {i}", "match": {"score": score}, "reach": {"creators": extra.pop("creators", 5)},
            **extra}


def _run(tmp_path, n: int = 70, *, previous: dict | None = None) -> RunFolder:
    """A run whose one search returned `n` relevant trends, t001 the best match (99) down to t0NN."""
    run = RunFolder.create(tmp_path / "ws", "nails", date(2026, 11, 7), playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    cards = [_card(i, 99 - i // 2) for i in range(1, n + 1)]
    trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": cards})
    if previous is not None:
        path = run.path / research_map.PREVIOUS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(previous), encoding="utf-8")
    return run


def _cfg(**review) -> dict:
    cfg = research_config.defaults()
    cfg["category"]["phrase"] = "nails"
    cfg["review"].update(review)
    return cfg


def test_the_map_keeps_the_best_50_by_match_and_sets_the_rest_aside(tmp_path, capsys):
    run = _run(tmp_path)
    out = research_map.build(run, SPLIT, None, _cfg())
    assert len(out["kept"]) == 50 and {r["id"] for r in out["kept"]} == {f"t{i:03d}" for i in range(1, 51)}
    assert [r["id"] for r in out["set_aside"]] == [f"t{i:03d}" for i in range(51, 71)]
    assert out["set_aside"][0]["set_aside_because"] == "rank 51 by match (74)"
    assert out["max_trends"] == 50 and out["dropped"] == []
    md = run.latest("02_research", "category_map", "md").read_text(encoding="utf-8")
    review, aside = md.split("## To review")[1].split("## Set aside by the engine (restore on request)")
    assert "| Trend 050 |" in review and "| Trend 051 |" not in review
    assert "| Trend 051 | nails | rank 51 by match (74) |" in aside and "nail video 1 " in review
    split = run.path / "03_wip" / "split_v01.json"
    split.parent.mkdir(parents=True, exist_ok=True)
    split.write_text(json.dumps(SPLIT), encoding="utf-8")
    assert main(["research", "map", "--run", str(run.path), "--split", str(split), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert (payload["kept"], payload["set_aside"]) == (50, 20) and "Set aside" in payload["message"]


def test_ties_go_to_more_creators_and_a_small_map_is_not_cut(tmp_path):
    run = _run(tmp_path, n=3)
    trends.save_answer(run, "search_trends", {"about": "nails"},
                       {"data": [_card(9, 98, creators=50), _card(8, 97, creators=1)]})
    out = research_map.build(run, SPLIT, None, _cfg(max_trends=3))
    assert {r["id"] for r in out["kept"]} == {"t001", "t002", "t009"}       # t009 ties t002, t003 at 98 with more creators
    assert [r["id"] for r in out["set_aside"]] == ["t003", "t008"]
    assert research_map.build(run, SPLIT, None, _cfg(max_trends=50))["set_aside"] == []


def test_the_review_drops_never_move_the_cut_and_restore_brings_one_back(tmp_path):
    run = _run(tmp_path)
    review = {"drop": {"Trend 001": "off-category", "Trend 060": "off-category"}, "retag": {},
              "restore": {"Trend 065": "the user asked for it"}}
    out = research_map.build(run, SPLIT, review, _cfg())
    kept = {r["id"]: r for r in out["kept"]}
    assert "t001" not in kept and "t051" not in kept and len(kept) == 50         # 49 of the 50, and the restored
    assert kept["t065"]["restored"] == "the user asked for it"
    assert {r["id"] for r in out["set_aside"]} == {f"t{i:03d}" for i in range(51, 71)} - {"t060", "t065"}
    assert {r["id"]: r["dropped_because"] for r in out["dropped"]} == {
        "t060": ["agent review: off-category"], "t001": ["agent review: off-category"]}
    assert "set_aside_because" not in next(r for r in out["dropped"] if r["id"] == "t060")
    md = run.latest("02_research", "category_map", "md").read_text(encoding="utf-8")
    assert "| Trend 065 (restored) |" in md


def test_restore_is_refused_for_unknown_contradicted_or_dropped_names(tmp_path):
    run = _run(tmp_path, n=5)
    trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": [_card(9, 80, status="contradicted")]})
    for review, said in [({"drop": {}, "retag": {}, "restore": {"Nobody": "x"}}, "which no saved search returned"),
                         ({"drop": {}, "retag": {}, "restore": {"Trend 009": "x"}}, "contradicted"),
                         ({"drop": {"Trend 002": "x"}, "retag": {}, "restore": {"Trend 002": "x"}}, "both drops and"),
                         ({"drop": {}, "retag": {}, "restore": ["Trend 002"]}, "The review file is")]:
        with pytest.raises(Stop, match=said):
            research_map.build(run, SPLIT, review, _cfg())
    assert run.latest("02_research", "category_map", "json") is None


def test_a_weekly_run_carries_last_weeks_review_drops_over(tmp_path):
    previous = {"root": "nails", "kept": [], "queries": [], "dropped": [
        {"id": "t002", "name": "Trend 002", "dropped_because": ["agent review: off-category: hair"]},
        {"id": "gone", "name": "Trend 003", "dropped_because": ["last week's review: a bakery"]},   # carried twice
        {"id": "t004", "name": "Trend 004", "dropped_because": ["noise: sport"]}]}                  # noise: not carried
    run = _run(tmp_path, n=52, previous=previous)
    out = research_map.build(run, SPLIT, None, _cfg())
    dropped = {r["id"]: r for r in out["dropped"]}
    assert dropped["t002"]["dropped_because"] == ["last week's review: off-category: hair"]
    assert dropped["t003"]["dropped_because"] == ["last week's review: a bakery"] and dropped["t003"]["carried_over"]
    assert "t004" not in dropped and len(out["kept"]) == 50 and out["set_aside"] == []   # the drops come before the cut
    # this week's map, read as next week's previous one, carries them on; restore brings one back
    out = research_map.build(run, SPLIT, {"drop": {}, "retag": {}, "restore": {"Trend 002": "back in season"}}, _cfg())
    assert {r["id"] for r in out["dropped"]} == {"t003"} and "t002" in {r["id"] for r in out["kept"]}
    run.path.joinpath(research_map.PREVIOUS).chmod(0o644)
    run.path.joinpath(research_map.PREVIOUS).write_text(json.dumps(out), encoding="utf-8")
    assert research_map.carried(run) == {"t003": "a bakery", "Trend 003": "a bakery"}


def test_the_cuts_are_whole_numbers_from_1_in_the_config():
    for key in ("review.max_trends", "hooks.max_candidates"):
        assert research_config.NUMBERS[key][:2] == (True, 1)


# --- B4: the hooks to score ---------------------------------------------------------------------

def _hook(i: int, **extra) -> dict:
    return {"id": f"h{i:03d}", "kind": "hook_trend", "name": f"hook {i:03d} _", "status": "confirmed",
            "what_it_is": f"opening {i}", "reach": {"creators": 10, "videos": 20}, "momentum": "rising",
            "active_for_days": 9, "sensitivity_level": "low", **extra}


def _row(score: int) -> dict:
    return {c: score for c in brief_config.CRITERIA}


def _hook_run(tmp_path, n_listed: int = 60, searched: tuple = ()) -> RunFolder:
    run = RunFolder.create(tmp_path / "ws", "nails", date(2026, 11, 7), playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    listed = [_hook(i) for i in range(1, n_listed + 1)]
    for page in range(0, len(listed), 50):
        trends.save_answer(run, "list_trends", {"sort": "rising", "trend_type": "hook_trend", "page": page // 50 + 1},
                           {"data": listed[page:page + 50]})
    if searched:
        trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": list(searched)})
    return run


def test_b4_scores_the_first_50_hooks_in_the_rising_order(tmp_path, capsys):
    searched = (_hook(901, match={"score": 40}), _hook(902, match={"score": 70}), _hook(3))   # h003 is listed already
    run = _hook_run(tmp_path, 48, searched)
    trends.save_answer(run, "list_trends", {"sort": "rising", "trend_type": "hook_trend", "page": 3},
                       {"data": [_hook(990, status="contradicted"), _hook(991)]})
    to_score, rest = research_growth.hook_candidates(run, research_config.defaults())
    # the 48 listed, h991, then the searches' hooks by match: 902 makes 50, 901 is below the cut
    assert [c["id"] for c in to_score][-3:] == ["h048", "h991", "h902"] and len(to_score) == 50
    assert [(r["id"], r["reason"]) for r in rest] == [("h990", "contradicted (TR4)"),
                                                       ("h901", "below the engine's cut (rank 51)")]
    assert main(["research", "hook-candidates", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["file"] == "02_research/hooks_to_score_v01.json"
    assert payload["to_score"] == 50 and payload["not_scored"] == 2
    data = json.loads((run.path / payload["file"]).read_text(encoding="utf-8"))
    assert set(data["rows"][0]) == {"id", "name", "what_it_is", "reach", "momentum", "active_for_days", "status",
                                    "sensitivity_level"}
    assert data["rows"][0]["id"] == "h001" and len(data["rows"]) == 50 and data["max_candidates"] == 50


def test_b4_leaves_out_the_hooks_the_map_dropped(tmp_path):
    run = _hook_run(tmp_path, 5)
    cmap = {"root": "nails", "kept": [], "queries": [], "set_aside": [],
            "dropped": [{"id": "h002", "name": "hook 002 _", "dropped_because": ["agent review: a pet video"]}]}
    path = run.path / "02_research" / "category_map_v01.json"
    path.write_text(json.dumps(cmap), encoding="utf-8")
    to_score, rest = research_growth.hook_candidates(run, research_config.defaults())
    assert "h002" not in {c["id"] for c in to_score}
    assert rest == [{"id": "h002", "name": "hook 002 _", "reason": "dropped from the category map: agent review: "
                                                                     "a pet video"}]


def test_hook_fit_needs_only_the_rows_to_score_and_lists_the_rest(tmp_path, capsys):
    run = _hook_run(tmp_path, 60)
    cfg = research_config.defaults()
    first = {f"h{i:03d}": _row(3) for i in range(1, 51)}
    assert research_growth.check_hook_fit(run, {k: v for k, v in first.items() if k != "h050"}, cfg)[0].what.startswith(
        "1 hook candidates are not scored")
    assert research_growth.check_hook_fit(run, first, cfg) == []
    out = json.loads(research_growth.hook_fit(run, {**first, "h002": _row(5)}, cfg).read_text(encoding="utf-8"))
    assert out["shortlist"][0]["id"] == "h002" and out["max_candidates"] == 50
    assert [r["id"] for r in out["not_scored"]] == [f"h{i:03d}" for i in range(51, 61)]
    assert out["not_scored"][0]["reason"] == "below the engine's cut (rank 51)"
    # a hook below the cut may be scored too (restored on request): it is ranked with the others
    out = json.loads(research_growth.hook_fit(run, {**first, "h055": _row(5)}, cfg).read_text(encoding="utf-8"))
    assert out["shortlist"][0]["id"] == "h055" and "h055" not in {r["id"] for r in out["not_scored"]}
    # #148 line 7.3: B4's set-aside list (the report's) is the latest shortlist's cut, without the restored one
    assert [r["id"] for r in research_growth.set_aside(run)] == [f"h{i:03d}" for i in range(51, 61) if i != 55]
    # the shortlist's next steps do not ask for the unscored ones
    (run.path / "03_wip" / "hook_fit_v01.json").write_text(json.dumps(first), encoding="utf-8")
    assert main(["research", "hook-fit", "--run", str(run.path), "--file", "03_wip/hook_fit_v01.json", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["scored"] == 50


# --- organic video: the fit candidates ----------------------------------------------------------

def _ov_pool(hooks: int = 40, formats: int = 30, topics: int = 25, sounds: int = 10) -> dict:
    pool = {f"h{i:02d}": {"kind": "hook_trend", "name": f"hook {i}"} for i in range(hooks)}
    pool.update({f"f{i:02d}": {"kind": "format_trend", "name": f"format {i}"} for i in range(formats)})
    pool.update({f"t{i:02d}": {"kind": "topic_trend", "name": f"topic {i}"} for i in range(topics)})
    pool.update({f"s{i:02d}": {"kind": "sound_trend", "name": f"sound {i}"} for i in range(sounds)})
    pool["hx"] = {"kind": "hook_trend", "name": "contradicted", "status": "contradicted"}
    return pool


def _fit_row(n: int) -> dict:
    return {**_row(n), "why": "a line"}


def _ranked() -> list[str]:
    """The engine's score, best first, every kind mixed: a sound, a topic, a format, a hook, round after round."""
    out = []
    for i in range(40):
        out += [f"{k}{i:02d}" for k, n in (("s", 10), ("t", 25), ("f", 30), ("h", 40)) if i < n]
    return out


def test_organic_scores_at_most_50_trends_of_every_kind_together():
    """#148 line 7.4: at most 50 candidates in all, topics, formats, hooks and sounds together, not 50 per kind (nor
    20 topics of their own): the best by the engine's score, which weighs growth and the fit to the terms."""
    from tm import shortlist
    pool, ranked = _ov_pool(), _ranked()
    found = shortlist.fit_candidates(pool, ranked)
    assert [c["id"] for c in found] == ranked[:50] and shortlist.FIT_CAP == 50
    assert {c["label"] for c in found} == {"hook", "format", "topic", "sound"}
    assert not hasattr(shortlist, "TOPIC_FIT_CAP")
    aside = shortlist.fit_set_aside(pool, ranked)
    assert [r["id"] for r in aside] == ranked[50:] and aside[0]["reason"] == "set aside: below the engine's cut (rank 51)"
    assert {r["label"] for r in aside} == {"hook", "format", "topic"}               # the 10 sounds all made the cut
    data = {c["id"]: _fit_row(3) for c in found}
    assert shortlist.check_fit(data, pool, ranked) == []
    wrong = shortlist.check_fit({k: v for k, v in data.items() if k != "s00"}, pool, ranked)
    assert len(wrong) == 1 and wrong[0].startswith("1 trends to score are not scored: 'sound 0' (s00)")
    restored = next(r["id"] for r in aside if r["label"] == "topic")
    assert shortlist.check_fit({**data, restored: _fit_row(5)}, pool, ranked) == []   # restored on request
    assert "not a trend to score" in shortlist.check_fit({**data, "hx": _fit_row(5)}, pool, ranked)[0]


def test_organic_ranks_the_candidates_of_every_list_by_the_engines_score():
    from tm import shortlist
    def row(tid, score, creators=1):
        return {"id": tid, "score": score, "creators": creators, "views": 1}
    scored = {"hooks": [row("h1", 60), row("h2", 20)], "topics": [row("t1", 70), row("t2", 20, creators=9)],
              "formats": [row("f1", 40)], "sounds": [row("s1", 50)]}
    assert shortlist.fit_ranked(scored) == ["t1", "h1", "s1", "f1", "t2", "h2"]   # ties: more creators first


def test_organic_a_sound_is_scored_like_a_topic_and_a_set_aside_one_keeps_its_place():
    """A sound (ranked by its niche relevance) and a topic keep their order: a weak fit goes last and never takes a
    place, one with no row (below the cut) is marked set aside where it stands."""
    from tm import shortlist
    rows = [{"id": f"s{i}", "name": f"sound {i}", "label": "sound", "flags": [], "score": 50 - i, "creators": 1,
             "views": 1} for i in range(3)]
    scored = {"hooks": [], "formats": [], "topics": [], "sounds": rows}
    shortlist.apply_fit(scored, {"s1": _fit_row(2), "s2": _fit_row(4)})
    assert [r["id"] for r in scored["sounds"]] == ["s0", "s2", "s1"]
    s0, s2, s1 = scored["sounds"]
    assert s0["plugin"]["fit"] is None and s0["flags"] == [shortlist.FIT_SET_ASIDE]
    assert s2["plugin"]["fit"]["score"] == 4 and shortlist.WEAK_FIT in s1["flags"] and shortlist.weak(s1)
    assert not shortlist.weak(s0)


def test_organic_unscored_hooks_below_the_cut_come_last():
    from tm import shortlist
    rows = [{"id": f"h{i}", "name": f"hook {i}", "label": "hook", "flags": [], "score": 90 - i, "creators": 1,
             "views": 1, "plugin": {}, "status": "confirmed", "momentum": None, "median_view_lift": None,
             "days_since_last_seen": None, "youtube_hook_rate_pct": None, "languages": [], "languages_inferred": False,
             "matched_terms": []} for i in range(3)]
    scored = {"hooks": rows, "formats": [], "sounds": [], "topics": []}
    shortlist.apply_fit(scored, {"h1": _fit_row(4), "h2": _fit_row(2)})
    assert [r["id"] for r in scored["hooks"]] == ["h1", "h2", "h0"]
    h0 = scored["hooks"][-1]
    assert h0["plugin"]["fit"] is None and shortlist.FIT_SET_ASIDE in h0["flags"]
    assert h0["reason"].startswith("set aside: below the engine's cut, fit not scored")
