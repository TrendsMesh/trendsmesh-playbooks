"""The hooks path ranks rising hooks by fit, fetches videos only for the shortlist (issue #8).

A small "nails" run built here: a category map of two topics, one saved rising hook list of five hooks
(one contradicted), and videos for the hooks the tests fetch. `tm research hook-fit` checks the agent's
fit scores (Creative brief's seven CB3 criteria, from the cards) and writes the shortlist; the fetch
plan then names only the shortlisted hooks; `tm research hooks` counts each shortlisted hook's videos in
the category (whole words, any match) as information, never as a gate.
"""

import json
from datetime import date

import pytest

from tm import brief_config, config, research_config, research_digest, research_growth, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop

AS_OF = date(2026, 11, 4)
HOOKS = [  # rising order: TrendsMesh's own ranking of the list
    {"id": "h1", "name": "day _ of _", "status": "confirmed"},
    {"id": "h2", "name": "pov _", "status": "confirmed"},
    {"id": "h3", "name": "start your _ with _", "status": "unconfirmed"},
    {"id": "h4", "name": "nobody talks about _", "status": "contradicted"},
    {"id": "h5", "name": "rate my _", "status": "confirmed"},
]
LIST = "02_research/lists/list_rising_hook_trend_all_p01.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _run(tmp_path, hooks=HOOKS) -> RunFolder:
    run = RunFolder.create(tmp_path / "ws", "nails", AS_OF, playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    kept = [{"id": tid, "name": name, "kind": "topic_trend", "group": "nails", "sub_category": "nails",
             "status": "confirmed"} for tid, name in (("t1", "Chrome nails"), ("t2", "Velvet nails"))]
    (run.path / "02_research" / "category_map_v01.json").write_text(json.dumps(
        {"root": "nails", "kept": kept, "dropped": [], "pool_ids": ["t1", "t2"]}), encoding="utf-8")
    lists = run.path / LIST
    lists.parent.mkdir(parents=True)
    cards = [{"kind": "hook_trend", "what_it_is": f"{h['name']}: an opener", **h} for h in hooks]
    lists.write_text(json.dumps({"_tool": "list_trends", "_input": {"sort": "rising", "trend_type": "hook_trend"},
                                 "answer": {"data": cards, "page": 1, "has_more": False}}), encoding="utf-8")
    return run


def _videos(run: RunFolder, trend_id: str, texts: list[str], day: str = "2026-10-28") -> None:
    folder = run.path / "02_research" / "videos"
    folder.mkdir(parents=True, exist_ok=True)
    vids = [{"asset_id": f"tiktok:{trend_id}{i}", "creator": f"{trend_id}c{i}", "published": f"{day}T10:00:00Z",
             "views": 9000, "excerpt": text, "url": f"https://www.tiktok.com/@{trend_id}c{i}/video/{i}"}
            for i, text in enumerate(texts)]
    (folder / f"{trend_id}_p01.json").write_text(json.dumps({"data": vids, "page": 1}), encoding="utf-8")


def _row(score: int, **over) -> dict:
    return {**{c: score for c in brief_config.CRITERIA}, **over}


def _fit(run: RunFolder, rows: dict, nn: int = 1) -> str:
    rel = f"03_wip/hook_fit_v{nn:02d}.json"
    (run.path / rel).write_text(json.dumps(rows), encoding="utf-8")
    return rel


FIT = {"h1": _row(3), "h2": _row(5), "h3": _row(4, why="the blank takes a nail step"), "h4": _row(5), "h5": _row(2)}


def _cfg(shortlist: int = 2) -> dict:
    cfg = research_config.defaults()
    cfg["hooks"]["shortlist"] = shortlist
    return cfg


# --- tm research hook-fit ---------------------------------------------------------------------

def test_hook_fit_ranks_by_fit_and_caps_the_shortlist(tmp_path, capsys):
    run = _run(tmp_path)
    path = research_growth.hook_fit(run, FIT, _cfg(2), fit_file="03_wip/hook_fit_v01.json")
    assert path == run.path / "02_research" / "hooks_shortlist_v01.json"
    out = _read(path)
    # h4 scores highest but is contradicted: never shortlisted; h2 (5) then h3 (4); h1 (3) and h5 (2) wait
    assert [r["id"] for r in out["shortlist"]] == ["h2", "h3"]
    assert [r["rank"] for r in out["shortlist"]] == [1, 2]
    assert out["shortlist"][1] == {"rank": 2, "id": "h3", "name": "start your _ with _", "fit": 4.0,
                                   "scores": {c: 4 for c in brief_config.CRITERIA},
                                   "why": "the blank takes a nail step"}
    assert [r["id"] for r in out["not_shortlisted"]] == ["h1", "h5"]
    assert [r["id"] for r in out["contradicted"]] == ["h4"]
    assert out["shortlist_size"] == 2 and out["min_fit"] == 3 and out["fit_file"] == "03_wip/hook_fit_v01.json"
    assert "02_research/hooks_shortlist_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")


def test_hook_fit_ties_keep_the_rising_order(tmp_path):
    run = _run(tmp_path)
    out = _read(research_growth.hook_fit(run, {h["id"]: _row(3) for h in HOOKS}, _cfg(3)))
    assert [r["id"] for r in out["shortlist"]] == ["h1", "h2", "h3"]


def test_hook_fit_needs_every_candidate_scored_on_the_seven_criteria(tmp_path, capsys):
    run = _run(tmp_path)
    rows = {"h1": _row(3), "h2": _row(6), "h3": {**_row(4), "virality": 5}, "h4": _row(1), "zz": _row(3)}
    problems = research_growth.check_hook_fit(run, rows)
    text = " ".join(f"{p.field}: {p.what} {p.todo}" for p in problems)
    assert "h5" in text and "not scored" in text                       # a candidate left out
    assert "zz" in text and "not a hook candidate" in text             # an id that is not one
    assert "brand_fit 6 is outside 1-5" in text and "virality is not a criterion" in text
    with pytest.raises(Stop):
        research_growth.hook_fit(run, rows, _cfg())
    assert not (run.path / "02_research" / "hooks_shortlist_v01.json").exists()

    # the command: exit 2 with each problem, then 0 once the file holds
    rel = _fit(run, rows)
    assert main(["research", "hook-fit", "--run", str(run.path), "--file", rel, "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and {p["field"] for p in payload["problems"]} == {"hook_fit", "zz", "h2", "h3"}
    rel = _fit(run, FIT, nn=2)
    assert main(["research", "hook-fit", "--run", str(run.path), "--file", rel, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["json"] == "02_research/hooks_shortlist_v01.json"
    assert payload["shortlist"] == ["h2", "h3", "h1"]                      # h5 (2.0) fits below the floor, 3
    assert "pov _" in payload["message"]


def test_hook_fit_needs_saved_hooks(tmp_path):
    run = _run(tmp_path, hooks=[])
    with pytest.raises(Stop, match="list_trends"):
        research_growth.hook_fit(run, {}, _cfg())


# --- the fetch plan: only the shortlisted hooks -------------------------------------------------

def test_fetch_plan_fetches_only_the_shortlisted_hooks(tmp_path, capsys):
    run = _run(tmp_path)
    with pytest.raises(Stop, match="hook-fit"):           # the rising hooks are saved but not ranked yet
        research_digest.fetch_plan(run, {})
    research_growth.hook_fit(run, FIT, _cfg(2))
    plan = research_digest.fetch_plan(run, {})
    assert plan["fetch"] == ["h2", "h3", "t1", "t2"] and plan["calls_estimate"] == 4
    assert plan["minutes_estimate"] == 1

    assert main(["research", "fetch-plan", "--run", str(run.path)]) == 0
    assert "about 1 minute" in capsys.readouterr().out


def test_fetch_plan_tells_the_minutes_of_a_long_fetch(tmp_path, capsys):
    many = [{"id": f"h{i}", "name": f"hook {i} _", "status": "confirmed"} for i in range(60)]
    run = _run(tmp_path, hooks=many)
    research_growth.hook_fit(run, {h["id"]: _row(3) for h in many}, _cfg(20))
    plan = research_digest.fetch_plan(run, {})
    assert len(plan["fetch"]) == 22 and plan["minutes_estimate"] == 1
    assert research_digest.minutes(142) == 6                    # the issue's run: 142 calls, about 6 minutes
    assert research_digest.minutes(0) == 0


def test_fetch_plan_of_a_run_whose_hooks_path_read_every_hook(tmp_path):
    """A run from before the shortlist (its hooks path ran over every hook card) keeps its plan."""
    run = _run(tmp_path)
    (run.path / "02_research" / "hooks_in_category_v01.json").write_text(json.dumps(
        {"terms": ["nail"], "kept": [], "not_in_category": []}), encoding="utf-8")
    assert research_digest.fetch_plan(run, {})["fetch"] == ["h1", "h2", "h3", "h4", "h5", "t1", "t2"]


# --- tm research hooks: the shortlist's category presence, whole words -----------------------

def test_hooks_count_whole_words_and_keep_every_shortlisted_hook(tmp_path, capsys):
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(3))       # h2, h3, h1
    _videos(run, "h2", ["start the day", "my artist friend", "smart move"])          # "art" in parts only
    _videos(run, "h3", ["nail art in 5 minutes", "NAILS done", "a nail-polish haul", "unrelated"])
    _videos(run, "h1", ["day 3 of my nails"])
    # the hooks not shortlisted have no videos: nothing asks for them
    path = research_growth.hooks(run, ["art", "nail", "nail art"], _cfg())
    out = _read(path)
    kept = {r["id"]: r for r in out["kept"]}
    assert [r["id"] for r in out["kept"]] == ["h2", "h3", "h1"]          # in fit order, none dropped
    assert kept["h2"]["category_videos"] == 0 and kept["h2"]["plugin"]["use"] == "transfer"
    assert kept["h3"]["category_videos"] == 2 and kept["h3"]["videos_checked"] == 4   # "nails" is another word
    assert kept["h3"]["plugin"] == {"fit": 4.0, "fit_rank": 2, "in_category": True, "use": "in_category",
                                    "why": "the blank takes a nail step", "ad_library": None}
    assert kept["h1"]["category_videos"] == 0                               # "nails" is not "nail"
    assert [r["id"] for r in out["not_shortlisted"]] == ["h5"]
    assert out["shortlist"] == "02_research/hooks_shortlist_v01.json"
    assert [c["id"] for c in _read(research_growth.candidates_of(path))] == ["h1", "h2", "h3", "h4", "h5"]

    assert main(["research", "hooks", "--run", str(run.path), "--terms", "nail,nails", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kept"] == 3 and payload["in_category"] == 2 and payload["transfer"] == 1
    assert "start your _ with _" in payload["message"]


def test_hooks_stop_without_a_shortlist_or_with_a_stale_one(tmp_path):
    run = _run(tmp_path)
    with pytest.raises(Stop, match="hook-fit"):
        research_growth.hooks(run, ["nail"], _cfg())
    research_growth.hook_fit(run, FIT, _cfg(2))
    with pytest.raises(Stop, match="no saved evidence videos"):           # the shortlist needs its videos
        research_growth.hooks(run, ["nail"], _cfg())
    trends.save_answer(run, "list_trends", {"sort": "rising", "trend_type": "hook_trend", "page": 2},
                       {"data": [{"id": "h9", "kind": "hook_trend", "name": "new _"}], "has_more": False})
    with pytest.raises(Stop, match="h9"):                                  # a hook listed after the fit
        research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", ["nail"])
    _videos(run, "h3", ["nail"])
    with pytest.raises(Stop, match="new _"):
        research_growth.hooks(run, ["nail"], _cfg())


def test_matcher_is_whole_word_and_case_blind():
    match = research_growth.term_matcher(["art", "nail art", "make-up", "ślub"])
    assert match("Nail Art tips") and match("ART!") and match("my make-up") and match("ŚLUB w maju")
    assert not match("start") and not match("artist") and not match("smart") and not match("ślubny")


# --- growth: the hooks' pool is the hooks with videos ---------------------------------------------

def test_growth_ranks_hooks_among_those_read_and_never_stops_on_the_rest(tmp_path):
    run = _run(tmp_path)
    for tid in ("t1", "t2"):
        _videos(run, tid, ["nails"] * 3)
    research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", ["nail"] * 4)
    _videos(run, "h3", ["nail"] * 2)
    research_growth.hooks(run, ["nail"], _cfg())
    path = research_growth.compute(run, AS_OF, _cfg())
    out = _read(path)
    assert out["params"]["category"]["hooks_pool"] == 2
    hooks = [r for r in out["trends"] if r["kind"] == "hook_trend"]
    assert sorted(r["id"] for r in hooks) == ["h2", "h3"]
    assert {r["id"]: r["plugin"]["use"] for r in hooks} == {"h2": "in_category", "h3": "in_category"}
    assert out["plugin"]["hooks_not_read"] == ["h1", "h4", "h5"]  # listed, never fetched: not in the pool
    assert sorted(_read(run.path / "02_research" / "snapshot_v01.json")["pool_ids"]) == \
        ["h1", "h2", "h3", "h4", "h5", "t1", "t2"]


# --- the config ---------------------------------------------------------------------------------

def test_config_takes_the_shortlist_and_still_reads_old_hook_keys(tmp_path):
    run = _run(tmp_path)
    assert research_config.defaults()["hooks"] == {"shortlist": 8, "min_fit": 3}
    cfg = config.load(run)
    cfg["hooks"] = {"min_share": 0.2, "min_hits": 3, "min_share_hits": 2}     # a config written before 0.11
    config.save(run, cfg)
    assert research_config.validate(run) == []
    cfg["hooks"] = {"shortlist": 0}
    config.save(run, cfg)
    assert [p.field for p in research_config.validate(run)] == ["hooks.shortlist"]
    cfg["hooks"] = {"shortlist": 25, "min_fit": 5.5}
    config.save(run, cfg)
    assert [p.field for p in research_config.validate(run)] == ["hooks.shortlist", "hooks.min_fit"]


def test_hook_fit_never_shortlists_a_poor_fit(tmp_path):
    """A hook fitting below `hooks.min_fit` (a mean of 3, neutral) is not adapted, whatever room is left."""
    run = _run(tmp_path)
    rows = {"h1": _row(2), "h2": _row(3, brand_fit=2), "h3": _row(3), "h4": _row(5), "h5": _row(1)}
    out = _read(research_growth.hook_fit(run, rows, _cfg(8)))
    assert [r["id"] for r in out["shortlist"]] == ["h3"]
    assert [r["id"] for r in out["not_shortlisted"]] == ["h2", "h1", "h5"]
    cfg = _cfg(8)
    cfg["hooks"]["min_fit"] = 1
    assert len(_read(research_growth.hook_fit(run, rows, cfg))["shortlist"]) == 4


# --- issue #58: the band is the hook's place in the rising list -------------------------------

def _grown_hooks(tmp_path, shortlist: int = 3) -> RunFolder:
    """The nails run with a hook only a search found (h6), the shortlist h2, h3, h6, their videos, the
    hooks path and the topics' videos: ready for growth."""
    run = _run(tmp_path)
    for tid in ("t1", "t2"):
        _videos(run, tid, ["nails"] * 3)
    card = {"id": "h6", "kind": "hook_trend", "name": "glow check _", "status": "confirmed"}
    trends.save_answer(run, "search_trends", {"about": "glow"}, {"data": [card]})
    research_growth.hook_fit(run, {**FIT, "h6": _row(4)}, _cfg(shortlist))      # h2, h3, then h6 (a tie)
    _videos(run, "h2", ["nail"] * 4)
    _videos(run, "h3", ["nail"] * 2)
    _videos(run, "h6", ["nail"] * 2)
    research_growth.hooks(run, ["nail"], _cfg())
    return run


def test_growth_bands_a_hook_by_its_place_among_all_the_rising_hooks(tmp_path):
    """The owner's choice on issue #58: a hook's band compares it with every hook of TrendsMesh's rising
    list (its place there), not with the few shortlisted hooks whose videos were read. The velocity
    index, and so the stage, still comes from its new creators against the category."""
    run = _grown_hooks(tmp_path)
    out = _read(research_growth.compute(run, AS_OF, _cfg()))
    rows = {r["id"]: r for r in out["trends"]}
    assert out["params"]["category"]["hooks_rising"] == 5               # h1-h5 listed, h6 from a search
    assert rows["h2"]["relative"] == {"velocity_index": 1.3, "rising_position": 2, "rising_of": 5,
                                      "percentile": 0.6, "band": "top half"}
    assert rows["h3"]["relative"] == {"velocity_index": 0.7, "rising_position": 3, "rising_of": 5,
                                      "percentile": 0.4, "band": "lower half"}
    # a hook not in the rising list has no place there, so no band; it still has its stage
    assert rows["h6"]["relative"] == {"velocity_index": 0.7, "rising_position": None, "rising_of": 5}
    assert rows["h6"]["bucket"] in research_growth.BUCKETS
    # topics are still ranked among the category's topics
    assert rows["t1"]["relative"] == {"velocity_index": 1.0, "percentile": 0.0, "band": "lower half"}
    md = (run.path / "02_research" / "growth_v01.md").read_text(encoding="utf-8")
    assert "| hooks | pov _ | hook | top half |" in md and "| hooks | glow check _ | hook | — |" in md


def test_growth_without_a_saved_rising_list_ranks_hooks_among_those_read(tmp_path):
    """A run whose hooks came from searches only has no rising list to place them in: as before."""
    run = _grown_hooks(tmp_path)
    (run.path / LIST).unlink()
    out = _read(research_growth.compute(run, AS_OF, _cfg()))
    rel = {r["id"]: r["relative"] for r in out["trends"] if r["kind"] == "hook_trend"}
    assert "hooks_rising" not in out["params"]["category"]
    assert all("rising_of" not in r for r in rel.values())
    assert rel["h2"]["band"] == "top half"                                # 2 of the 3 hooks read below it


# --- issue #58: the shortlisted hooks in the market's Ad Library --------------------------------

def _ads(run: RunFolder, query: str, answer: list | None = None) -> None:
    trends.save_answer(run, "ads_library_search", {"search_terms": query, "ad_reached_countries": ["US"]},
                       {"data": answer or []})


def _hook_ads(run: RunFolder, data: dict, nn: int = 1) -> str:
    rel = f"02_research/hooks_ad_library_v{nn:02d}.json"
    (run.path / rel).write_text(json.dumps(data), encoding="utf-8")
    return rel


HOOK_ADS = {"checked": True, "checks": [
    {"hook_id": "h2", "hook": "pov _", "query": "pov nail salon", "verdict": "competitor_found",
     "advertisers": ["Salon A (2 ads)"], "note": "a salon's POV booking ad"},
    {"hook_id": "h3", "hook": "start your _ with _", "query": "start your manicure with", "verdict": "none_found",
     "advertisers": [], "note": "titles show coffee and fitness ads"}]}


def test_hook_ads_need_every_shortlisted_hook_checked_with_a_saved_answer(tmp_path, capsys):
    from tm import research_checks
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(2))                           # h2, h3
    _ads(run, "pov nail salon", [{"page_name": "Salon A"}])
    _ads(run, "start your manicure with")
    assert research_checks.check_hook_ads(run, HOOK_ADS) == []
    rel = _hook_ads(run, HOOK_ADS)
    assert main(["research", "hook-ads", "--run", str(run.path), "--file", rel, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and "2 shortlisted hooks" in payload["message"]

    def problems(**change):
        data = json.loads(json.dumps(HOOK_ADS))
        for i, row in change.items():
            data["checks"][int(i[1:])].update(row)
        return research_checks.check_hook_ads(run, data)

    assert "competitor found" in problems(c1={"verdict": "competitor_found"})[0].what      # names none
    assert "none_found" in problems(c0={"verdict": "none_found"})[0].what                 # names one
    assert "unused" in problems(c1={"note": "this hook is unused in ads"})[0].what
    assert "no saved answer" in problems(c1={"query": "start your nails"})[0].what
    assert "the hook's name" in problems(c1={"query": "start your _ with _"})[0].what
    assert "not shortlisted" in problems(c1={"hook_id": "h5"})[0].what or \
        any("not shortlisted" in p.what for p in problems(c1={"hook_id": "h5"}))
    missing = research_checks.check_hook_ads(run, {"checked": True, "checks": HOOK_ADS["checks"][:1]})
    assert len(missing) == 1 and "start your _ with _" in missing[0].what
    # Meta unavailable: nothing to check, every hook says "not checked"
    assert research_checks.check_hook_ads(run, {"checked": False, "checks": []}) == []
    assert research_checks.check_hook_ads(run, {"checked": False, "checks": HOOK_ADS["checks"]})


def test_hooks_carry_their_ad_library_verdict(tmp_path):
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", ["nail"])
    _videos(run, "h3", ["nail"])
    out = _read(research_growth.hooks(run, ["nail"], _cfg()))
    assert {r["plugin"]["ad_library"] for r in out["kept"]} == {None} and out["ad_library"] is None  # not checked
    _ads(run, "pov nail salon", [{"page_name": "Salon A"}])
    _ads(run, "start your manicure with")
    _hook_ads(run, HOOK_ADS)
    out = _read(research_growth.hooks(run, ["nail"], _cfg()))
    kept = {r["id"]: r["plugin"]["ad_library"] for r in out["kept"]}
    assert kept["h2"] == {"verdict": "competitor_found", "query": "pov nail salon", "advertisers": ["Salon A (2 ads)"]}
    assert kept["h3"] == {"verdict": "none_found", "query": "start your manicure with", "advertisers": []}
    assert out["ad_library"] == "02_research/hooks_ad_library_v01.json"
    # a check that no longer covers the shortlist stops the hooks path, writing nothing
    research_growth.hook_fit(run, FIT, _cfg(3))                           # h1 is shortlisted now
    _videos(run, "h1", ["nail"])
    with pytest.raises(Stop, match="day _ of _"):
        research_growth.hooks(run, ["nail"], _cfg())
    assert not (run.path / "02_research" / "hooks_in_category_v03.json").exists()
    _hook_ads(run, {"checked": False, "checks": []}, nn=2)                # Meta went away: not checked
    out = _read(research_growth.hooks(run, ["nail"], _cfg()))
    assert {r["plugin"]["ad_library"] for r in out["kept"]} == {None}


def test_a_shortlisted_hook_on_the_map_keeps_its_use_and_fit(tmp_path):
    """A hook a search kept on the map is listed once, the map's row: it still carries the hooks path's
    fit, use and Ad Library verdict, so the report's two lists hold it (issue #58)."""
    run = _grown_hooks(tmp_path)
    cmap = _read(run.path / "02_research" / "category_map_v01.json")
    cmap["kept"].append({"id": "h2", "name": "pov _", "kind": "hook_trend", "group": "nails",
                         "sub_category": "nails", "status": "confirmed"})
    (run.path / "02_research" / "category_map_v02.json").write_text(json.dumps(cmap), encoding="utf-8")
    rows = [r for r in _read(research_growth.compute(run, AS_OF, _cfg()))["trends"] if r["id"] == "h2"]
    assert len(rows) == 1 and rows[0]["group"] == "nails"                  # the map's row
    plugin = rows[0]["plugin"]
    assert (plugin["use"], plugin["fit_rank"], plugin["category_videos"], plugin["videos_checked"]) == \
        ("in_category", 1, 4, 4)
