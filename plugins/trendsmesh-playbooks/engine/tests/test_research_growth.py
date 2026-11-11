"""tm.research_growth: the hooks path (TR1), growth (TR2), the four stages (TR3, rule v3), the TR4
flags and the snapshot (TR8), the handoff's tools/pb4/growth.py ported.

The beauty run (beauty.py) goes through the same steps as the reference dry run: the category map from
the derived searches and the reference review, the hooks path from the derived rising hook list, then growth as of
4 Nov 2026. The port must rebuild the reference hooks_in_category.json, growth.json and snapshot.json exactly;
it may add only a row key `plugin` and a top-level `pool_ids`, which are stripped here (decision 5).
"""

import json
from datetime import date, timedelta

import pytest

import beauty
from tm import brief_config, research_config, research_growth, research_map, state, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.research_growth import Thresholds
from tm.runfolder import RunFolder
from tm.stops import Stop

AS_OF = date(2026, 11, 4)
REF = AS_OF - timedelta(days=2)


_cfg = beauty.cfg
_terms = beauty.terms
_mapped = beauty.mapped_run


@pytest.fixture(scope="module")
def beauty_run(tmp_path_factory):
    """One mapped beauty run for the tests that only evaluate (nothing is written into it)."""
    return _mapped(tmp_path_factory.mktemp("beauty"))


def _strip(data: dict) -> dict:
    """Without what the port may add: top-level `pool_ids`, a row's `plugin`."""
    out = {k: v for k, v in data.items() if k != "pool_ids"}
    rows = out["trends"]
    if isinstance(rows, list):
        out["trends"] = [{k: v for k, v in r.items() if k != "plugin"} for r in rows]
    return out


def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def no_confidence(rows) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("confidence")} for r in rows]


def _by_name(rows: list[dict], name: str) -> dict:
    return next(r for r in rows if r["name"] == name)


# --- hooks path (TR1) -------------------------------------------------------------------------

@pytest.mark.private_data
def test_hooks_path_keeps_the_shortlist_with_its_category_counts(tmp_path, capsys):
    """Issue #8: the fit scores shortlist the reference's five kept hooks; the hooks path keeps all five,
    in fit order, with the reference's category counts on whole words (beauty.WHOLE_WORDS)."""
    run = beauty.make_run(tmp_path)
    reference = beauty.handoff("02_research/hooks_in_category.json")
    research_growth.hook_fit(run, beauty.fit_scores(reference), _cfg(hooks={"shortlist": 5}))
    path = research_growth.hooks(run, _terms(), _cfg())
    assert path == run.path / "02_research" / "hooks_in_category_v01.json"
    out = _read(path)
    assert [r["id"] for r in out["kept"]] == [r["id"] for r in reference["kept"]]
    assert [r["plugin"]["fit_rank"] for r in out["kept"]] == [1, 2, 3, 4, 5]
    assert {r["plugin"]["use"] for r in out["kept"]} == {"in_category"}      # each has category videos
    for mine, his in zip(out["kept"], reference["kept"]):
        same = {k: v for k, v in his.items() if k not in beauty.CATEGORY_KEYS}
        assert {k: mine[k] for k in same} == same
        if mine["name"] not in beauty.WHOLE_WORDS:
            assert {k: mine[k] for k in beauty.CATEGORY_KEYS} == {k: his[k] for k in beauty.CATEGORY_KEYS}
    assert {r["name"]: r["category_videos"] for r in out["kept"]}["day _ of _"] == 2
    assert len(out["not_shortlisted"]) == 96
    candidates = _read(run.path / "02_research" / "hooks_candidates_v01.json")
    # the rising hooks (the derived list), then the searches' hooks, de-duplicated by id: the searches'
    # one hook, "this is ur sign to _" (kept in the map under "sephora haul"), is in the list already
    assert [c["id"] for c in candidates] == [c["id"] for c in beauty.hook_cards(reference)]
    assert all(c["kind"] == "hook_trend" for c in candidates) and len(candidates) == 101

    # the command: the same files again as _v02, never over the first
    assert main(["research", "hooks", "--run", str(run.path), "--terms", ",".join(_terms()), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["json"] == "02_research/hooks_in_category_v02.json"
    assert payload["candidates"] == "02_research/hooks_candidates_v02.json"
    assert (payload["kept"], payload["in_category"], payload["checked"]) == (5, 5, 101)
    assert _read(run.path / payload["json"]) == _read(path)
    assert main(["research", "hooks", "--run", str(run.path), "--terms", " , ", "--json"]) == 1

    # a hook only a search found is a candidate too, after the listed ones: it needs a fit score first
    card = {"id": "hnew", "kind": "hook_trend", "name": "glow check _", "status": "confirmed"}
    trends.save_answer(run, "search_trends", {"about": "glow"}, {"data": [card, {**card, "id": "t", "kind": "topic_trend"}]})
    with pytest.raises(Stop, match="glow check _"):
        research_growth.hooks(run, _terms(), _cfg())
    videos = [{"asset_id": f"tiktok:{i}", "creator": f"c{i}", "excerpt": "glow serum", "published": "2026-10-30T10:00:00Z"}
              for i in range(3)]
    (run.path / "02_research" / "videos" / "hnew_p01.json").write_text(json.dumps({"data": videos}), encoding="utf-8")
    scores = {**beauty.fit_scores(reference), "hnew": {k: 5 for k in brief_config.CRITERIA}}
    research_growth.hook_fit(run, scores, _cfg(hooks={"shortlist": 6}))
    third = _read(research_growth.hooks(run, _terms(), _cfg()))
    assert third["kept"][0]["id"] == "hnew" and third["kept"][0]["category_videos"] == 3
    assert [c["id"] for c in _read(run.path / "02_research" / "hooks_candidates_v03.json")][-1] == "hnew"


@pytest.mark.private_data
def test_hooks_need_the_shortlisted_videos_only(tmp_path, capsys):
    run = _mapped(tmp_path)
    reference = beauty.handoff("02_research/hooks_in_category.json")
    for row in reference["not_in_category"]:          # never shortlisted: never fetched
        for f in trends.video_files(run, row["id"]):
            f.unlink()
    assert main(["research", "hooks", "--run", str(run.path), "--terms", "makeup", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["json"] == "02_research/hooks_in_category_v02.json"
    missing = reference["kept"][2]["id"]
    for f in trends.video_files(run, missing):
        f.unlink()
    assert main(["research", "hooks", "--run", str(run.path), "--terms", "makeup", "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and missing in payload["message"]
    assert "continues from the same place" in payload["message"]
    assert not (run.path / "02_research" / "hooks_in_category_v03.json").exists()


# --- growth, stages, snapshot (TR2, TR3, TR4, TR8) ----------------------------------------------

@pytest.mark.private_data
def test_growth_rebuilds_beauty_growth_and_snapshot(tmp_path, capsys):
    run = _mapped(tmp_path)
    path = research_growth.compute(run, AS_OF, _cfg())
    assert path == run.path / "02_research" / "growth_v01.json"
    growth, snapshot = _read(path), _read(run.path / "02_research" / "snapshot_v01.json")

    expected, changed = beauty.as_whole_words(beauty.handoff("02_research/growth.json"), run)
    assert _strip(growth) == expected and changed == beauty.WHOLE_WORDS   # issue #8: whole words
    assert _strip(snapshot) == beauty.handoff("02_research/snapshot.json")
    md = (run.path / "02_research" / "growth_v01.md").read_text(encoding="utf-8")
    assert md == (beauty.BEAUTY / "02_research" / "growth.md").read_text(encoding="utf-8").replace("\r\n", "\n")

    buckets = [r["bucket"] for r in growth["trends"]]
    assert [buckets.count(b) for b in research_growth.BUCKETS] == [7, 19, 19, 12]
    assert growth["params"]["category"] == {"median_new": 3, "trends_active": 51, "creators_active": 249,
                                            "trends": 57, "hooks_pool": 101}
    # TR4: every row carries its sensitive videos and level (no beauty video is flagged); every beauty
    # video has a creator
    assert all(r["plugin"] == {"sensitive_videos": 0, "unattributed_videos": 0,
                               "sensitivity_level": r.get("sensitivity_level")}
               for r in growth["trends"] if r["sub_category"] != "hooks")
    assert {r["plugin"]["sensitive_videos"] for r in growth["trends"]} == {0}
    assert {r["plugin"]["unattributed_videos"] for r in growth["trends"]} == {0}
    assert "plugin" not in growth and "No creator data" not in md        # every hook candidate has creators
    # TR8: the snapshot keeps every id the searches and the hook lists returned
    handoff_map = beauty.handoff("02_research/category_map.json")
    hook_ids = [c["id"] for c in beauty.hook_cards(beauty.handoff("02_research/hooks_in_category.json"))]
    assert snapshot["pool_ids"] == sorted({r["id"] for r in handoff_map["kept"] + handoff_map["dropped"]}
                                          | set(hook_ids))
    assert "rebuilt" not in snapshot

    # a rebuilt previous week (F9): its own stem, marked rebuilt when first written. The reference
    # 29 Oct file was written while confidence still read the evidence language (its reasons say "in the market
    # language"), so all but the confidence is the reference's again
    prev = research_growth.compute(run, date(2026, 10, 29), _cfg(), stem="growth_2026-10-29_rebuilt",
                                   snapshot_extra={"rebuilt": True})
    assert prev.name == "growth_2026-10-29_rebuilt_v01.json"
    prev_snap = _read(run.path / "02_research" / "snapshot_growth_2026-10-29_rebuilt_v01.json")
    assert prev_snap["rebuilt"] is True
    original, changed = beauty.as_whole_words(beauty.handoff("02_research/growth_2026-10-29_reconstructed.json"), run)
    assert changed == beauty.WHOLE_WORDS
    assert _strip(_read(prev))["params"] == original["params"]
    assert no_confidence(_strip(_read(prev))["trends"]) == no_confidence(original["trends"])
    original_snap = beauty.handoff("02_research/snapshot_growth_2026-10-29_reconstructed.json")
    assert no_confidence(prev_snap["trends"].values()) == no_confidence(original_snap["trends"].values())

    # the command: as of the run's created date (4 Nov) by default, the next version beside the first
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["json"] == "02_research/growth_v02.json"
    assert payload["snapshot"] == "02_research/snapshot_v02.json" and payload["md"] == "02_research/growth_v02.md"
    assert payload["buckets"] == {"act_now": 7, "still_rising": 19, "too_late": 19, "past_peak": 12}
    assert payload["no_creator_data"] == [] and "no creator data" not in payload["message"]
    assert _read(run.path / payload["json"]) == growth
    assert main(["research", "growth", "--run", str(run.path), "--as-of", "2026-10-29"]) == 0
    assert "growth_v03.json" in capsys.readouterr().out
    assert _read(run.path / "02_research" / "growth_v03.json")["trends"] == _read(prev)["trends"]
    assert main(["research", "growth", "--run", str(run.path), "--stem", "../x", "--json"]) == 1
    # another stem never takes another file's name (category_map_vNN.json would be read as the map)
    capsys.readouterr()
    for stem in ("category_map", "growthx", "snapshot"):
        assert main(["research", "growth", "--run", str(run.path), "--stem", stem, "--json"]) == 1
        assert "must start with growth_" in json.loads(capsys.readouterr().out)["message"]
    assert not (run.path / "02_research" / "category_map_v02.json").exists()


@pytest.mark.private_data
def test_halloween_past_peak_on_4_nov(beauty_run):
    rows, _ = research_growth.evaluate(beauty_run, REF, _cfg())
    halloween = _by_name(rows, "Halloween makeup and costume transformations")
    assert halloween["seasonal_over"] == "seasonal: halloween (2026-10-31) is over"
    assert halloween["bucket"] == "past_peak"
    assert halloween["relative"]["velocity_index"] >= 1.3 and halloween["growth"]["new_recent"] >= 3
    assert _by_name(rows, "Día de los Muertos Catrina makeup and costumes")["bucket"] == "past_peak"
    seasonal = [r for r in rows if r["seasonal_over"]]
    assert seasonal and all(r["bucket"] == "past_peak" for r in seasonal)

    # without the guard its growth alone would say "act now"
    t = {"name": halloween["name"], "what_it_is": halloween["what_it_is"]}
    assert research_growth.event_passed(t, REF, research_growth.SEASON_AFTER) == halloween["seasonal_over"]
    assert research_growth.event_passed(t, REF, 1) is None                   # 2 days after, guard of 1 day
    th = Thresholds.from_config(_cfg())
    assert research_growth.bucket(halloween["growth"], halloween["status"], None, halloween["relative"], th) == "act_now"
    # an event still ahead is not over: Halloween seen on 20 Oct counts from last year's, 354 days ago
    assert research_growth.event_passed(t, date(2026, 10, 20), 60) is None
    assert research_growth.event_passed({"name": "Christmas glam"}, date(2027, 1, 5), 60) == \
        "seasonal: christmas (2026-12-25) is over"


@pytest.mark.private_data
def test_lip_combo_not_act_now_concentrated(beauty_run):
    rows, _ = research_growth.evaluate(beauty_run, REF, _cfg())
    lip = _by_name(rows, "Lip combo liner and gloss routine")
    g = lip["growth"]
    assert g["top_creator_share"] == 0.85 and lip["relative"]["velocity_index"] >= 1.3 and g["new_recent"] >= 3
    assert g["median_views"] >= 5000 and g["last_seen_days"] <= 5
    assert lip["bucket"] == "still_rising"                                   # the concentration gate
    assert (lip["confidence"], lip["confidence_why"]) == ("low", "views come mostly from one account")
    loose = Thresholds.from_config(_cfg(buckets={"concentrated": 0.9}))
    assert research_growth.bucket(g, lip["status"], None, lip["relative"], loose) == "act_now"
    # "Fall almond nails": one creator too, and a median of 214 views
    almond = _by_name(rows, "Fall almond nail art designs")
    assert almond["growth"]["median_views"] == 214 and almond["bucket"] != "act_now"


@pytest.mark.private_data
def test_thresholds_come_from_config(beauty_run):
    th = Thresholds.from_config(_cfg())
    assert (th.act_index, th.act_min_new, th.act_last_days, th.act_median_views, th.concentrated) == \
        (1.3, 3, 5, 5000, 0.6)
    assert (th.rise_index, th.rise_min_new, th.rise_last_days) == (0.6, 2, 7)
    assert (th.crowded_creators, th.crowded_age_days, th.active_days, th.season_after_days) == (100, 90, 14, 60)
    assert (th.low_creators, th.low_top_share, th.high_creators, th.high_top_share) == (8, 0.6, 15, 0.4)
    assert Thresholds.from_config({}) == th                                  # defaults fill a bare config
    with pytest.raises(AttributeError):
        th.act_index = 2                                                     # frozen

    def counts(cfg):
        rows, _ = research_growth.evaluate(beauty_run, REF, cfg)
        return {b: sum(r["bucket"] == b for r in rows) for b in research_growth.BUCKETS}, rows

    base, _ = counts(_cfg())
    strict, _ = counts(_cfg(buckets={"act_index": 50}))
    assert base["act_now"] == 7 and strict["act_now"] == 0
    assert strict["still_rising"] > base["still_rising"]
    later, _ = counts(_cfg(buckets={"active_days": 60}))
    assert later["past_peak"] < base["past_peak"]
    _, rows = counts(_cfg(confidence={"high_creators": 10_000}))
    assert "high" not in {r["confidence"] for r in rows}
    _, rows = counts(_cfg(confidence={"low_creators": 10_000}))
    assert {r["confidence"] for r in rows} == {"low"}
    assert research_growth.confidence({"creators": 9, "top_creator_share": 0.1}, "confirmed", th) == \
        ("medium", "some limits: see the risk line")
    assert research_growth.confidence({"creators": 7}, "confirmed", th) == ("low", "only 7 creators in evidence")


def test_no_creator_field_stops_with_message(tmp_path, capsys):
    run = RunFolder.create(tmp_path / "ws", "nails", date(2026, 11, 4), playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    research = run.path / "02_research"
    (research / "category_map_v01.json").write_text(json.dumps({"root": "nails", "kept": [
        {"id": "t1", "kind": "topic_trend", "name": "Chrome nails", "group": "nails", "sub_category": "nails",
         "status": "confirmed"}], "dropped": [], "pool_ids": ["t1"]}), encoding="utf-8")
    (research / "videos").mkdir()
    no_creator = [{"asset_id": f"tiktok:{i}", "url": f"https://www.tiktok.com/video/{i}", "creator": " ",
                   "creator_id": None, "published": f"2026-10-{20 + i}T10:00:00Z", "views": 9000} for i in range(4)]
    (research / "videos" / "t1.json").write_text(json.dumps({"trend_id": "t1", "videos": no_creator}), encoding="utf-8")

    with pytest.raises(ValueError, match="^TrendsMesh's videos for t1 carry no creator, so new creators can't be "
                                         "counted.$"):
        research_growth.growth_of(no_creator, REF, 14, 28, trend_id="t1")
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop"
    assert payload["message"].startswith("TrendsMesh's videos for t1 carry no creator, so new creators can't be counted.")
    assert "tm trends check-fields" in payload["message"] and "continues from the same place" in payload["message"]
    assert not list(research.glob("growth_*")) and not list(research.glob("snapshot_*"))

    # the creator falls back to creator_id, then the @handle in the url; a video with none is not a creator
    mixed = [{**no_creator[0], "creator_id": "c9"},
             {**no_creator[1], "url": "https://www.tiktok.com/@ana/video/1"},
             {**no_creator[2], "url": "https://www.tiktok.com/@ana/video/2"}, no_creator[3]]
    g = research_growth.growth_of(mixed, REF, 14, 28)
    assert g["creators"] == 2 and g["new_recent"] == 2 and g["videos_known"] == 4
    assert g["recent_creators"] == ["ana", "c9"] and g["top_creator"] == "ana"
    assert research_growth.growth_of([], REF, 14, 28) == {"creators": 0}     # no evidence is not an error


def _rewrite_videos(run: RunFolder, trend_id: str, change) -> None:
    """Replace the saved videos of `trend_id` (the legacy `<id>.json` of the beauty run) by `change(videos)`."""
    path = run.path / "02_research" / "videos" / f"{trend_id}.json"
    data = _read(path)
    data["videos"] = change(data["videos"])
    path.write_text(json.dumps(data), encoding="utf-8")


def _no_creator(videos: list[dict]) -> list[dict]:
    return [{k: v for k, v in video.items() if k not in ("creator", "creator_id", "url")} for video in videos]


@pytest.mark.private_data
def test_pool_only_hook_without_creators_never_stops_growth(tmp_path, capsys):
    run = _mapped(tmp_path)
    hooks_file = beauty.handoff("02_research/hooks_in_category.json")
    pool_only = hooks_file["not_in_category"][3]["id"]      # ranks hooks only: never evaluated
    _rewrite_videos(run, pool_only, _no_creator)

    path = research_growth.compute(run, AS_OF, _cfg())
    growth = _read(path)
    assert growth["plugin"] == {"no_creator_data": [pool_only]}
    assert growth["params"]["category"]["hooks_pool"] == 101                 # still in the pool, as 0 new
    assert pool_only not in {r["id"] for r in growth["trends"]}
    md = path.with_suffix(".md").read_text(encoding="utf-8")
    assert f"No creator data (counted as 0 new creators, used only to rank hooks): {pool_only}" in md
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["no_creator_data"] == [pool_only] and pool_only in payload["message"]
    assert "no creator data" in payload["message"]
    backtest = research_growth.backtest(run, date(2026, 10, 21), _cfg())          # listed there too
    assert f"No creator data (counted as 0 new creators, used only to rank hooks): {pool_only}." in \
        backtest.with_suffix(".md").read_text(encoding="utf-8")
    assert _read(backtest)["plugin"] == {"no_creator_data": [pool_only]}

    # a kept hook is evaluated, so without creators it still stops, and nothing is written
    kept = hooks_file["kept"][0]["id"]
    _rewrite_videos(run, kept, _no_creator)
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and f"videos for {kept} carry no creator" in payload["message"]
    assert not (run.path / "02_research" / "growth_v03.json").exists()


@pytest.mark.private_data
def test_growth_stops_before_the_hooks_path(tmp_path, capsys):
    """Saved rising hook lists but no hooks_in_category yet: growth would leave the hooks out."""
    run = beauty.make_run(tmp_path)
    handoff_map = beauty.handoff("02_research/category_map.json")
    research_map.build(run, beauty.split_of(handoff_map), beauty.handoff("03_wip/map_review_v01.json"), _cfg())
    with pytest.raises(Stop, match="tm research hooks"):
        research_growth.compute(run, AS_OF, _cfg())
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "no hooks path yet" in payload["message"]
    assert "continues from the same place" in payload["message"]
    assert not list((run.path / "02_research").glob("growth_v*"))


@pytest.mark.private_data
def test_weekly_run_missing_videos_names_the_fetch_plan_first(tmp_path, capsys):
    run = _mapped(tmp_path)
    trend = beauty.handoff("02_research/category_map.json")["kept"][4]
    (run.path / "02_research" / "videos" / f"{trend['id']}.json").unlink()
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    first = json.loads(capsys.readouterr().out)["message"]
    assert "fetch-plan" not in first and "Fetch their videos" in first
    s = state.load(run)
    s.previous_run = "runs/04-trend-research/2026-10-28_beauty"
    state.save(run, s)
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    weekly = json.loads(capsys.readouterr().out)["message"]
    assert weekly.index("tm research fetch-plan") < weekly.index("tm research reuse") < weekly.index("fetch the rest")
    assert trend["id"] in weekly and "continues from the same place" in weekly


@pytest.mark.private_data
def test_compute_stops_on_a_trend_without_a_saved_page(tmp_path, capsys):
    run = _mapped(tmp_path)
    trend = beauty.handoff("02_research/category_map.json")["kept"][4]
    (run.path / "02_research" / "videos" / f"{trend['id']}.json").unlink()
    with pytest.raises(research_growth.Stop, match=trend["id"]):
        research_growth.compute(run, AS_OF, _cfg())
    assert main(["research", "growth", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "continues from the same place" in payload["message"]
    assert not list((run.path / "02_research").glob("growth_v*")) and not list((run.path / "02_research").glob("snapshot_v*"))

    # a page saved under another case, or as a later page, counts as saved (the reader's own matcher)
    videos = beauty.BEAUTY / "02_research" / "videos" / f"{trend['id']}.json"
    (run.path / "02_research" / "videos" / f"{trend['id'].upper()}_p01.json").write_bytes(videos.read_bytes())
    assert research_growth.compute(run, AS_OF, _cfg()).name == "growth_v01.json"


@pytest.mark.private_data
def test_snapshot_extra_never_replaces_snapshot_data(beauty_run):
    for key in ("params", "trends", "pool_ids"):
        with pytest.raises(ValueError, match=key):
            research_growth.compute(beauty_run, AS_OF, _cfg(), snapshot_extra={key: []})
    assert not list((beauty_run.path / "02_research").glob("growth_v*"))


@pytest.mark.private_data
def test_rows_count_sensitive_and_unattributed_videos(tmp_path):
    run = _mapped(tmp_path)
    trend = beauty.handoff("02_research/category_map.json")["kept"][0]

    def flag(videos):
        videos[0]["is_sensitive"] = True
        videos[1]["is_sensitive"] = True
        return [videos[0], videos[1], *_no_creator(videos[2:3]), *videos[3:]]

    _rewrite_videos(run, trend["id"], flag)
    rows, _ = research_growth.evaluate(run, REF, _cfg())
    plugin = _by_name(rows, trend["name"])["plugin"]
    assert plugin["sensitive_videos"] == 2 and plugin["unattributed_videos"] == 1
