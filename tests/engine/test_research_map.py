"""tm.research_map: the category map (TR1), the handoff's tools/pb4/category_map.py `build` ported.

The beauty run (beauty.py) is rebuilt from the reference category_map.json: the port must give the same
`kept` and `dropped`, with the reference split and agent review (map_review_v01.json).
"""

import json
from datetime import date

import pytest

import beauty
from tm import research_config, research_map, trends
from tm.cli import main
from tm.playbooks import REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import Stop


def _cfg(**trend_settings) -> dict:
    cfg = research_config.defaults()
    cfg["category"]["phrase"] = beauty.ROOT
    cfg["trends"].update(trend_settings)
    return cfg


def _write_json(path, data) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def handoff_map():
    return beauty.handoff("02_research/category_map.json")


@pytest.mark.private_data
def test_map_rebuilds_beauty_kept_and_dropped(tmp_path, capsys, handoff_map):
    run = beauty.make_run(tmp_path)
    review = beauty.handoff("03_wip/map_review_v01.json")
    out = research_map.build(run, beauty.split_of(handoff_map), review, _cfg())

    assert out["kept"] == handoff_map["kept"]
    assert out["dropped"] == handoff_map["dropped"]
    assert (out["root"], out["min_match"], out["min_relevant"]) == ("beauty", 40, 10)
    # every relevant result is in kept or dropped, so the counts rebuild; `results` needs the raw 50
    assert [{k: q[k] for k in ("query", "parent", "relevant", "file")} for q in out["queries"]] == \
        [{k: q[k] for k in ("query", "parent", "relevant", "file")} for q in handoff_map["queries"]]
    assert sorted(out["pool_ids"]) == sorted(r["id"] for r in handoff_map["kept"] + handoff_map["dropped"])
    assert out["below_threshold"] == 0 and out["weak_match"] == []          # not a thin map

    written = run.path / "02_research" / "category_map_v01.json"
    assert json.loads(written.read_text(encoding="utf-8")) == out
    md = (run.path / "02_research" / "category_map_v01.md").read_text(encoding="utf-8")
    assert md.startswith("# Category map: beauty\n") and "| makeup tutorial | makeup | 37 / " in md
    assert "Dementia in family life and memory" in md.split("## Dropped")[1]

    # the command: the same map again, as _v02 beside the first
    copied = beauty.copy_input(run, "03_wip/map_review_v01.json")
    split = _write_json(run.path / "03_wip" / "split_v01.json", beauty.split_of(handoff_map))
    assert main(["research", "map", "--run", str(run.path), "--split", split, "--review", str(copied),
                 "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["json"] == "02_research/category_map_v02.json"
    assert (payload["kept"], payload["dropped"], payload["below_threshold"]) == (52, 12, 0)
    again = json.loads((run.path / payload["json"]).read_text(encoding="utf-8"))
    assert again["kept"] == handoff_map["kept"] and again["dropped"] == handoff_map["dropped"]
    assert (run.path / "02_research" / "category_map_v02.md").is_file()


@pytest.mark.private_data
def test_map_without_review_and_with_exclude_terms(tmp_path, handoff_map):
    run = beauty.make_run(tmp_path)
    out = research_map.build(run, beauty.split_of(handoff_map), None, _cfg(exclude_terms=["Sephora"]))
    names = {r["name"]: r for r in out["dropped"]}
    assert "Dementia in family life and memory" in {r["name"] for r in out["kept"]}     # no review: kept
    sephora = [r for r in out["dropped"] if "excluded term: Sephora" in r["dropped_because"]]
    assert sephora and all("sephora" in (r["name"] + r["what_it_is"]).lower() for r in sephora)
    assert not any(r["dropped_because"][0].startswith("agent review") for r in names.values())


@pytest.mark.private_data
def test_review_with_unknown_names_is_refused_before_writing(tmp_path, handoff_map):
    run = beauty.make_run(tmp_path)
    review = {"drop": {"Dementia in family life": "off-category"}, "retag": {}}
    with pytest.raises(ValueError, match="Dementia in family life") as refused:
        research_map.build(run, beauty.split_of(handoff_map), review, _cfg())
    assert "carried over from last week" in str(refused.value)
    assert "can be removed from the review file" in str(refused.value)
    assert run.latest("02_research", "category_map", "json") is None


@pytest.mark.private_data
def test_search_status_flags_beauty_for_split(tmp_path, capsys, handoff_map):
    run = beauty.make_run(tmp_path)
    cfg = _cfg()
    rows = {r["query"]: r for r in research_map.search_status(run, cfg)}
    assert rows["beauty"] == {"query": "beauty", "results": rows["beauty"]["results"], "relevant": 1,
                              "split": True, "depth": 0}           # before the split file: the phrase is 0
    assert rows["makeup"]["depth"] is None                         # not in a split file yet

    _write_json(run.path / "03_wip" / "split_v01.json", beauty.split_of(handoff_map))
    rows = {r["query"]: r for r in research_map.search_status(run, cfg)}
    assert set(rows) == {q["query"] for q in handoff_map["queries"]}
    assert (rows["beauty"]["relevant"], rows["beauty"]["split"], rows["beauty"]["depth"]) == (1, True, 0)
    assert (rows["makeup"]["relevant"], rows["makeup"]["split"], rows["makeup"]["depth"]) == (23, False, 1)
    assert (rows["hairstyle"]["relevant"], rows["hairstyle"]["depth"]) == (18, 2)       # under "hair", not searched
    assert (rows["makeup tutorial"]["relevant"], rows["makeup tutorial"]["depth"]) == (37, 2)
    assert (rows["sunscreen"]["relevant"], rows["sunscreen"]["split"], rows["sunscreen"]["depth"]) == (0, True, 2)
    assert research_map.search_problems(run, cfg) == []

    assert main(["research", "search-status", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["problems"] == []
    assert next(r for r in payload["searches"] if r["query"] == "beauty")["split"] is True
    assert main(["research", "search-status", "--run", str(run.path)]) == 0
    text = capsys.readouterr().out
    assert "'beauty'" in text and "[SPLIT]" in text and "thin leaf at depth 2" in text
    assert payload["message"] == text.rstrip("\n")                  # --json says what the text says


def test_search_status_finds_answers_by_their_input_not_file_name(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "uroda", date(2026, 11, 7), playbook=TREND_RESEARCH)
    long = "pielęgnacja skóry wrażliwej po zabiegach kosmetycznych na twarz"
    path = trends.save_answer(run, "search_trends", {"about": long}, {"data": [
        {"id": "a", "kind": "topic_trend", "name": "A", "match": {"score": 55}}]})
    trends.save_answer(run, "search_trends", {"about": long, "page": 2}, {"data": [
        {"id": "b", "kind": "topic_trend", "name": "B", "match": {"score": 41}},
        {"id": "a", "kind": "topic_trend", "name": "A", "match": {"score": 12}}]})
    assert len(path.stem) <= len("search_") + trends.NAME_PART_MAX         # capped and hashed
    cfg = _cfg()
    cfg["category"]["phrase"] = "uroda"
    assert research_map.to_search(run, cfg) == ["uroda"]                   # before the split: the phrase
    split = {"root": "uroda", "queries": [
        {"query": "uroda", "parent": None, "depth": 0, "source": "seed"},
        {"query": long, "parent": "uroda", "depth": 1, "source": "common_sub_areas"},
        {"query": "włosy", "parent": "uroda", "depth": 1, "source": "common_sub_areas"}]}
    _write_json(run.path / "03_wip" / "split_v01.json", split)
    rows = {r["query"]: r for r in research_map.search_status(run, cfg)}
    assert rows[long] == {"query": long, "results": 2, "relevant": 2, "split": True, "depth": 1}
    # not searched yet is what to do next, not a problem; the map still waits for them
    assert research_map.search_problems(run, cfg) == []
    assert research_map.to_search(run, cfg) == ["uroda", "włosy"]
    with pytest.raises(ValueError, match="'włosy' is in the split file but has no saved search"):
        research_map.build(run, split, None, cfg)

    (run.path / "config.yaml").write_text("category: {phrase: uroda}\nmarket: PL\nlanguage: pl\n", encoding="utf-8")
    assert main(["research", "search-status", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["problems"] == []
    assert payload["to_search"] == ["uroda", "włosy"]
    assert main(["research", "search-status", "--run", str(run.path)]) == 0
    assert "Still to search: 'uroda', 'włosy'." in capsys.readouterr().out


def test_split_queries_match_their_searches_loosely(tmp_path, capsys):
    """"Nail art" in the split is the saved "nail art": capitals and spaces around do not matter."""
    run = RunFolder.create(tmp_path / "ws", "nails", date(2026, 11, 7), playbook=TREND_RESEARCH)

    def card(tid, score):
        return {"id": tid, "kind": "topic_trend", "name": tid.upper(), "status": "confirmed", "match": {"score": score}}

    trends.save_answer(run, "search_trends", {"about": "nails"}, {"data": [card("r", 70), card("a", 60)]})
    trends.save_answer(run, "search_trends", {"about": "nail art"}, {"data": [card("a", 45), card("b", 50)]})
    trends.save_answer(run, "search_trends", {"about": "Press-On"}, {"data": [card("c", 55)]})
    split = {"root": "Nails", "queries": [
        {"query": "Nails", "parent": None, "depth": 0, "source": "seed"},
        {"query": "Nail art ", "parent": "NAILS", "depth": 1, "source": "common_sub_areas"},
        {"query": "press-on", "parent": "Nail art", "depth": 1, "source": "closest_names"}]}
    _write_json(run.path / "03_wip" / "split_v01.json", split)
    cfg = _cfg()
    assert research_map.to_search(run, cfg) == [] and research_map.search_problems(run, cfg) == []
    rows = {r["query"]: r["depth"] for r in research_map.search_status(run, cfg)}
    assert rows == {"nails": 0, "nail art": 1, "Press-On": 2}       # press-on: below "Nail art", so 2

    out = research_map.build(run, split, None, cfg)
    by_id = {r["id"]: (r["sub_category"], r["group"]) for r in out["kept"]}
    # "a": the sub-category wins over the root even at a lower score, as in the original rule
    assert by_id == {"r": ("nails", "nails"), "a": ("nail art", "nail art"), "b": ("nail art", "nail art"),
                     "c": ("Press-On", "Nail art")}
    assert {q["query"]: q["parent"] for q in out["queries"]} == {"nails": None, "nail art": "NAILS",
                                                                 "Press-On": "Nail art"}


@pytest.mark.private_data
def test_split_deeper_than_two_is_refused(tmp_path, capsys, handoff_map):
    run = beauty.make_run(tmp_path)
    split = beauty.split_of(handoff_map)
    split["queries"].append({"query": "nail art", "parent": "manicure", "depth": 3, "source": "closest_names"})
    split["queries"] = [q for q in split["queries"] if not (q["query"] == "nail art" and q["depth"] == 2)]
    with pytest.raises(ValueError, match="TR1 stops splitting at depth 2: a thin leaf means little coverage"):
        research_map.build(run, split, None, _cfg())
    assert run.latest("02_research", "category_map", "json") is None
    # a depth written too low is read from its parent's: under a depth-2 query it is 3
    split["queries"][-1]["depth"] = 2
    with pytest.raises(ValueError, match="'nail art' is at depth 3"):
        research_map.build(run, split, None, _cfg())

    path = _write_json(run.path / "03_wip" / "split_v01.json", split)
    assert main(["research", "search-status", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop"
    assert any("TR1 stops splitting at depth 2" in p for p in payload["problems"])
    assert main(["research", "map", "--run", str(run.path), "--split", path, "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "TR1 stops splitting at depth 2" in payload["message"]
    assert "Fix the split file" in payload["message"] and "same place" in payload["message"]
    # a deeper split is allowed only when the config allows it
    assert research_map.build(run, split, None, _cfg(max_split_depth=3))["kept"]


@pytest.mark.private_data
def test_split_file_must_have_its_shape(tmp_path, handoff_map):
    run = beauty.make_run(tmp_path)
    for broken, says in (({"queries": []}, "root"),
                         ({"root": "beauty", "queries": [{"query": "beauty", "depth": 0, "source": "guess"}]},
                          "source"),
                         ({"root": "beauty", "queries": [{"query": "", "depth": 0, "source": "seed"}]}, "query"),
                         ({"root": "beauty", "queries": [{"query": "beauty", "depth": "0", "source": "seed"}]},
                          "depth"),
                         ({"root": "beauty", "queries": [
                             {"query": "beauty", "parent": None, "depth": 0, "source": "seed"},
                             {"query": "Nail art", "parent": "beauty", "depth": 1, "source": "seed"},
                             {"query": "nail art ", "parent": "beauty", "depth": 1, "source": "seed"}]},
                          "'nail art ' is in the split file twice")):
        with pytest.raises(ValueError, match=says):
            research_map.build(run, broken, None, _cfg())


def _thin_run(tmp_path, *, nothing_relevant: bool = False) -> tuple[RunFolder, dict]:
    """"body care" split twice: every leaf thin at depth 2 (the reference run: sunscreen, body lotion and self
    tanning returned 0 relevant)."""
    run = RunFolder.create(tmp_path / "ws", "body", date(2026, 11, 7), playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "body care"}, "market": "US", "language": "en"})

    def card(tid, name, score, **extra):
        return {"id": tid, "kind": "topic_trend", "name": name, "status": "confirmed",
                "what_it_is": f"{name} videos", "match": {"score": score}, **extra}

    answers = {
        "body care": [card("k1", "Body oil glow routine", 30 if nothing_relevant else 44), card("w1", "Dry brushing", 38),
                      card("n1", "Senator election body language", 39)],
        "body lotion": [card("w2", "Lotion layering", 36), card("w3", "Shea butter whips", 31),
                        card("c1", "Fake lotion claims", 37, status="contradicted")],
        "self tanning": [card("w4", "Tan line checks", 33), card("w5", "Gradual tan mousse", 29),
                         card("w6", "Self tan fails", 12)],
        "sunscreen": [card("z1", "Sunscreen myths", 0)],                # score 0: no match at all
    }
    for query, cards in answers.items():
        trends.save_answer(run, "search_trends", {"about": query}, {"data": cards})
    split = {"root": "body care", "queries": [
        {"query": "body care", "parent": None, "depth": 0, "source": "seed"},
        {"query": "body moisture", "parent": "body care", "depth": 1, "source": "common_sub_areas"},
        {"query": "body lotion", "parent": "body moisture", "depth": 2, "source": "closest_names"},
        {"query": "self tanning", "parent": "body moisture", "depth": 2, "source": "closest_names"},
        {"query": "sunscreen", "parent": "body moisture", "depth": 2, "source": "list_topics"}]}
    trends.save_answer(run, "search_trends", {"about": "body moisture"}, {"data": [card("w2", "Lotion layering", 20)]})
    return run, split


def test_map_files_resolve_inside_the_run_from_the_workspace(tmp_path, capsys, monkeypatch):
    """`--split` and `--review` given relative to the run folder, run from the workspace (as the skill
    does), like every other file flag of tm research."""
    run, split = _thin_run(tmp_path)
    _write_json(run.path / "03_wip" / "split_v01.json", split)
    _write_json(run.path / "03_wip" / "map_review_v01.json", {"drop": {"Dry brushing": "off-category"}, "retag": {}})
    ws = run.path.parents[2]
    monkeypatch.chdir(ws)
    assert not (ws / "03_wip").exists()
    rel = run.path.relative_to(ws).as_posix()
    capsys.readouterr()
    assert main(["research", "map", "--run", rel, "--split", "03_wip/split_v01.json",
                 "--review", "03_wip/map_review_v01.json", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["json"] == "02_research/category_map_v01.json"
    built = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    assert [r["id"] for r in built["weak_match"]][:1] == ["w2"]        # the review read: w1 dropped


def test_review_names_each_trends_event_in_the_market_language(tmp_path, capsys):
    """Issue #3, item 5: the agent names a kept trend's dated event in the review, in any language, with the
    date of the occurrence; every kept row then carries its `event` (None: none), which growth's seasonal
    guard reads. A review written before has no `events`, and its rows no `event` key."""
    run, split = _thin_run(tmp_path)
    review = {"drop": {}, "retag": {}, "events": {"Body oil glow routine": {"name": "Wszystkich Świętych",
                                                                           "date": "2026-11-01"}}}
    out = research_map.build(run, split, review, _cfg())
    assert {r["id"]: r["event"] for r in out["kept"]} == {"k1": review["events"]["Body oil glow routine"]}
    md = run.latest("02_research", "category_map", "md").read_text(encoding="utf-8")
    assert "| Wszystkich Świętych (2026-11-01) |" in md
    out = research_map.build(run, split, {"drop": {}, "retag": {}, "events": {}}, _cfg())
    assert [r["event"] for r in out["kept"]] == [None]
    out = research_map.build(run, split, {"drop": {}, "retag": {}}, _cfg())     # written before issue #3
    assert all("event" not in r for r in out["kept"])
    nn = run.latest("02_research", "category_map", "json")
    for events, said in [({"Body oil glow routine": {"name": "Andrzejki", "date": "30 Nov"}}, "not YYYY-MM-DD"),
                         ({"Body oil glow routine": {"name": " ", "date": "2026-11-30"}}, "name is empty"),
                         ({"Body oil glow routine": None}, "names no event"),
                         (["Andrzejki"], "not one table"),
                         ({"Nobody returned this": {"name": "Andrzejki", "date": "2026-11-30"}},
                          "which no saved search returned")]:
        with pytest.raises(Stop, match=said):
            research_map.build(run, split, {"drop": {}, "retag": {}, "events": events}, _cfg())
    assert run.latest("02_research", "category_map", "json") == nn                  # nothing written


def test_map_stops_on_files_to_fix(tmp_path, capsys):
    """Every input to fetch or file to fix is a stop (exit 2) that says what to do and that the run
    continues; a split file that is not one object too."""
    run, split = _thin_run(tmp_path)
    cases = [
        ({**split, "queries": [*split["queries"], {"query": "tanning drops", "parent": "body moisture", "depth": 2,
                                                   "source": "closest_names"}]}, None, "has no saved search"),
        (split, {"drop": ["Self tan fails"]}, "The review file is"),
        (split, {"drop": {"Nobody returned this": "x"}, "retag": {}}, "which no saved search returned"),
        ([split], None, "must hold one JSON object"),
    ]
    for i, (sp, review, said) in enumerate(cases, 1):
        args = ["research", "map", "--run", str(run.path), "--split",
                _write_json(run.path / "03_wip" / f"split_v{i:02d}.json", sp), "--json"]
        if review is not None:
            args += ["--review", _write_json(run.path / "03_wip" / f"map_review_v{i:02d}.json", review)]
        capsys.readouterr()
        assert main(args) == 2, said
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "stop" and said in out["message"] and "same place" in out["message"], out["message"]
    assert run.latest("02_research", "category_map", "json") is None


def test_thin_map_lists_weak_matches_never_empty(tmp_path, capsys):
    run, split = _thin_run(tmp_path)
    review = {"drop": {"Shea butter whips": "off-category", "Self tan fails": "off-category"}, "retag": {}}
    out = research_map.build(run, split, review, _cfg())
    assert [r["id"] for r in out["kept"]] == ["k1"]
    weak = out["weak_match"]
    # the closest below the threshold, at most five; noise, contradicted, review drops and score 0
    # are never weak matches
    assert [r["id"] for r in weak] == ["w1", "w2", "w4", "w5"]
    assert all(r["label"] == "weak match" for r in weak)
    assert [r["match"] for r in weak] == [38, 36, 33, 29]
    assert weak[1]["sub_category"] == "body lotion" and weak[1]["group"] == "body moisture"
    md = (run.path / "02_research" / "category_map_v01.md").read_text(encoding="utf-8")
    assert "## Weak match" in md and "| Dry brushing |" in md
    assert "no trends in the category" not in md.lower()

    run, split = _thin_run(tmp_path / "none", nothing_relevant=True)
    out = research_map.build(run, split, None, _cfg())
    assert out["kept"] == [] and len(out["weak_match"]) == 5 and out["weak_match"][0]["id"] == "w1"
    assert main(["research", "map", "--run", str(run.path), "--split",
                 _write_json(run.path / "03_wip" / "split_v01.json", split), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["weak_match"] == 5 and "weak match" in payload["message"]

    # a leaf that is not thin, or one that may still be split, means no weak matches
    run, split = _thin_run(tmp_path / "shallow")
    split["queries"][-1]["depth"] = 1
    split["queries"][-1]["parent"] = "body care"
    assert research_map.build(run, split, None, _cfg())["weak_match"] == []


def _map(run: RunFolder, kept: list[tuple[str, str]], *, previous: bool = False) -> None:
    rows = [{"id": tid, "name": tid.upper(), "group": group, "sub_category": group} for tid, group in kept]
    data = {"root": "beauty", "kept": rows, "dropped": [], "queries": []}
    target = run.path / "00_raw" / "prev_category_map.json" if previous else run.next_version(
        "02_research", "category_map", "json")
    _write_json(target, data)


def test_map_change_flags_a_quarter_new(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "week", date(2026, 11, 11), playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "beauty"}, "market": "US", "language": "en"})
    cfg = _cfg()
    with pytest.raises(ValueError, match="no category map"):
        research_map.map_change(run, cfg)
    _map(run, [("a", "nails"), ("b", "nails"), ("c", "makeup"), ("d", "makeup")])
    assert research_map.map_change(run, cfg) == {"new_share": None, "new_groups": [], "changed_a_lot": False}

    _map(run, [("a", "nails"), ("b", "nails"), ("c", "makeup"), ("x", "makeup")], previous=True)
    assert research_map.map_change(run, cfg) == {"new_share": 0.25, "new_groups": [], "changed_a_lot": True}
    assert research_map.map_change(run, {**cfg, "digest": {"map_change_share": 0.3}})["changed_a_lot"] is False

    _map(run, [("a", "nails"), ("b", "nails"), ("c", "makeup"), ("x", "makeup"), ("e", "makeup")])
    assert research_map.map_change(run, cfg) == {"new_share": 0.2, "new_groups": [], "changed_a_lot": False}

    _map(run, [("a", "nails"), ("y", "nails"), ("z", "makeup")])            # 2 of 3 new: 0.666… shown 0.6667
    assert research_map.map_change(run, {"digest": {"map_change_share": 0.66669}}) == {
        "new_share": 0.6667, "new_groups": [], "changed_a_lot": True}           # decided on the share shown

    _map(run, [("a", "nails"), ("b", "nails"), ("c", "makeup"), ("x", "hair")])
    assert research_map.map_change(run, cfg) == {"new_share": 0.0, "new_groups": ["hair"], "changed_a_lot": True}

    assert main(["research", "map-change", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "new_share": 0.0, "new_groups": ["hair"],
                                                   "changed_a_lot": True,
                                                   "message": "0% of the mapped trends are new since the previous run; "
                                                              "new groups: hair. The map changed a lot (V26): show it "
                                                              "at G1 again."}
    assert main(["research", "map-change", "--run", str(run.path)]) == 0
    assert "changed a lot" in capsys.readouterr().out


def test_research_commands_are_for_trend_research_runs(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "ad", date(2026, 11, 7), playbook=REFRESH_AD)
    assert main(["research", "map-change", "--run", str(run.path), "--json"]) == 1
    assert "trend research" in json.loads(capsys.readouterr().out)["message"].lower()
