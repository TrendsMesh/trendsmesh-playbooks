"""The hooks path ranks rising hooks by fit, fetches videos only for the shortlist (issue #8).

A small "nails" run built here: a category map of two topics, one saved rising hook list of five hooks
(one contradicted), and videos for the hooks the tests fetch. `tm research hook-fit` checks the agent's
fit scores (Creative brief's seven CB3 criteria, from the cards) and writes the shortlist; the fetch
plan then names only the shortlisted hooks; `tm research hook-captions` lists their captions and `tm research
hooks` records the agent's judgement of each one (issue #3: in the category or a transfer, never word
matching) as information, never as a gate.
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


def _judge(run: RunFolder, counts: dict | None = None, **events) -> dict:
    """The agent's judgement of every shortlisted hook: `counts` (hook id -> its captions about the category,
    by default every caption read), each with a made-up line on why, and `events` by hook id."""
    out = {}
    for r in research_growth.shortlist(run)["shortlist"]:
        read = len(research_growth.captions_read(trends.load_videos(run, r["id"])))
        n = (counts or {}).get(r["id"], read)
        out[r["id"]] = {"in_category": n > 0, "category_videos": n, "why": f"{n} of {read} are nail videos",
                        "event": events.get(r["id"])}
    return out


def _texts(word: str, n: int) -> list[str]:
    return [f"{word} {i}" for i in range(n)]


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


# --- tm research hooks: the agent's judgement of each shortlisted hook (issue #3, item 5) ----------

def _views(run: RunFolder, trend_id: str, rows: list[tuple[str, int]]) -> None:
    """Videos of `trend_id` with these (excerpt, views)."""
    _videos(run, trend_id, [t for t, _ in rows])
    path = run.path / "02_research" / "videos" / f"{trend_id}_p01.json"
    data = _read(path)
    for v, (_, views) in zip(data["data"], rows):
        v["views"] = views
    path.write_text(json.dumps(data), encoding="utf-8")


def test_hook_captions_list_each_shortlisted_hooks_most_viewed_captions(tmp_path, capsys, monkeypatch):
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(2))                          # h2, h3
    _views(run, "h2", [("pov: twój manicure", 10), ("POV: robię paznokcie", 900), ("pov: twój manicure", 50),
                       ("", 5000)])
    _videos(run, "h3", _texts("start your day with nails", 5))
    monkeypatch.setattr(research_growth, "CAPTIONS", 3)
    path, counts = research_growth.hook_captions(run)
    assert path == run.path / "03_wip" / "hook_captions_v01.md" and counts == {"h2": 2, "h3": 3}
    text = path.read_text(encoding="utf-8")
    # most-viewed first, the same words once, a video without a caption left out; capped at CAPTIONS
    assert "1. POV: robię paznokcie\n2. pov: twój manicure\n\n" in text
    assert text.index("pov _") < text.index("start your _ with _")         # fit order
    assert "start your day with nails 2" in text and "start your day with nails 3" not in text
    assert "hooks_shortlist_v01.json" in text and '"in_category"' in text   # what to write next
    v = {"excerpt": "  nail\nart ", "hook_text": "nail art", "slot_fill": "chrome"}
    assert research_growth.caption(v) == "nail art · chrome"
    assert len(research_growth.caption({"excerpt": "x" * 500})) == research_growth.CAPTION_CHARS

    assert main(["research", "hook-captions", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["file"] == "03_wip/hook_captions_v02.md" and payload["captions"] == {"h2": 2, "h3": 3}
    assert "tm research hooks --file" in payload["message"]


def test_hooks_keep_every_shortlisted_hook_with_the_agents_judgement(tmp_path, capsys):
    """A Polish category ("makijaż") whose captions inflect the word: whole-word matching found no
    category video in "makijażu" or "makijażem" and called the hook a transfer. The agent's judgement
    says it is used in the category, in any language."""
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(3))                          # h2, h3, h1
    _videos(run, "h2", ["pov: mój codzienny makijażu krok", "pov: z makijażem do pracy", "pov: mój pies"])
    _videos(run, "h3", ["朝のメイクを始めよう", "start your day with coffee"])
    _videos(run, "h1", ["day 3 of my car build"])
    use = _judge(run, {"h2": 2, "h3": 1, "h1": 0})
    use["h2"]["why"] = "two of three captions are makeup (makijaż in its forms), one is a dog"
    path = research_growth.hooks(run, use, _cfg())
    out = _read(path)
    kept = {r["id"]: r for r in out["kept"]}
    assert [r["id"] for r in out["kept"]] == ["h2", "h3", "h1"]          # in fit order, none dropped
    assert (kept["h2"]["category_videos"], kept["h2"]["videos_checked"]) == (2, 3)
    assert kept["h2"]["plugin"] == {"fit": 5.0, "fit_rank": 1, "in_category": True, "use": "in_category",
                                    "why": None, "use_why": use["h2"]["why"], "ad_library": None}
    assert kept["h3"]["plugin"]["use"] == "in_category" and kept["h3"]["category_share"] == 0.5
    assert kept["h1"]["plugin"]["use"] == "transfer" and kept["h1"]["category_videos"] == 0
    assert all(r["event"] is None for r in out["kept"]) and out["judgement"] is None
    assert "terms" not in out
    assert [r["id"] for r in out["not_shortlisted"]] == ["h5"]
    assert out["shortlist"] == "02_research/hooks_shortlist_v01.json"
    assert [c["id"] for c in _read(research_growth.candidates_of(path))] == ["h1", "h2", "h3", "h4", "h5"]

    (run.path / "03_wip" / "hook_use_v01.json").write_text(json.dumps(use), encoding="utf-8")
    assert main(["research", "hooks", "--run", str(run.path), "--file", "03_wip/hook_use_v01.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kept"] == 3 and payload["in_category"] == 2 and payload["transfer"] == 1
    assert "start your _ with _" in payload["message"]
    assert _read(run.path / payload["json"])["judgement"] == "03_wip/hook_use_v01.json"
    long = {hid: {**row, "why": row["why"] + " " + "x" * 400} for hid, row in use.items()}   # the JSON itself
    assert main(["research", "hooks", "--run", str(run.path), "--file", json.dumps(long), "--json"]) == 0
    assert _read(run.path / json.loads(capsys.readouterr().out)["json"])["judgement"] is None


def test_hooks_need_a_judgement_of_every_shortlisted_hook_that_holds(tmp_path, capsys):
    run = _run(tmp_path)
    research_growth.hook_fit(run, FIT, _cfg(2))                          # h2, h3
    _videos(run, "h2", _texts("nail", 3))
    _videos(run, "h3", _texts("nail", 2))
    good = _judge(run)

    def problems(**rows):
        return " ".join(p.what for p in research_growth.check_hook_use(
            run, {k: v for k, v in ({**good, **rows}).items() if v is not None}))

    assert problems() == ""
    assert "no judgement" in problems(h3=None) and "start your _ with _" in problems(h3=None)
    assert "not a hook of the latest shortlist" in problems(h5=good["h2"])
    assert "from 0 to 3" in problems(h2={**good["h2"], "category_videos": 4})        # above the captions read
    assert "from 0 to 3" in problems(h2={**good["h2"], "category_videos": True})
    assert "exactly when" in problems(h2={**good["h2"], "in_category": False})
    assert "true or false" in problems(h2={**good["h2"], "in_category": "yes"})
    assert "why" in problems(h2={**good["h2"], "why": " "})
    assert "not YYYY-MM-DD" in problems(h2={**good["h2"], "event": {"name": "Andrzejki", "date": "30.11"}})
    assert "name is empty" in problems(h2={**good["h2"], "event": {"name": "", "date": "2026-11-30"}})
    assert "event is null or" in problems(h2={**good["h2"], "event": "Andrzejki"})
    assert "matches is not a field" in problems(h2={**good["h2"], "matches": 3})
    assert research_growth.check_hook_use(run, {})[0].field == "hook_use"
    # the command: exit 2 with each problem, nothing written
    bad = json.dumps({"h2": good["h2"]})
    assert main(["research", "hooks", "--run", str(run.path), "--file", bad, "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "start your _ with _" in payload["message"]
    assert not list((run.path / "02_research").glob("hooks_in_category_v*.json"))
    with pytest.raises(Stop, match="no judgement"):
        research_growth.hooks(run, {"h2": good["h2"]}, _cfg())


def test_hooks_stop_without_a_shortlist_or_with_a_stale_one(tmp_path):
    run = _run(tmp_path)
    with pytest.raises(Stop, match="hook-fit"):
        research_growth.hooks(run, {}, _cfg())
    with pytest.raises(Stop, match="hook-fit"):
        research_growth.hook_captions(run)
    research_growth.hook_fit(run, FIT, _cfg(2))
    with pytest.raises(Stop, match="no saved evidence videos"):           # the shortlist needs its videos
        research_growth.hooks(run, {}, _cfg())
    with pytest.raises(Stop, match="no saved evidence videos"):
        research_growth.hook_captions(run)
    trends.save_answer(run, "list_trends", {"sort": "rising", "trend_type": "hook_trend", "page": 2},
                       {"data": [{"id": "h9", "kind": "hook_trend", "name": "new _"}], "has_more": False})
    with pytest.raises(Stop, match="h9"):                                  # a hook listed after the fit
        research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", ["nail"])
    _videos(run, "h3", ["nail"])
    with pytest.raises(Stop, match="new _"):
        research_growth.hooks(run, {}, _cfg())


# --- growth: the hooks' pool is the hooks with videos ---------------------------------------------

def test_growth_ranks_hooks_among_those_read_and_never_stops_on_the_rest(tmp_path):
    run = _run(tmp_path)
    for tid in ("t1", "t2"):
        _videos(run, tid, ["nails"] * 3)
    research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", _texts("nail", 4))
    _videos(run, "h3", _texts("nail", 2))
    research_growth.hooks(run, _judge(run), _cfg())
    path = research_growth.compute(run, AS_OF, _cfg())
    out = _read(path)
    assert out["params"]["category"]["hooks_pool"] == 2
    hooks = [r for r in out["trends"] if r["kind"] == "hook_trend"]
    assert sorted(r["id"] for r in hooks) == ["h2", "h3"]
    assert {r["id"]: r["plugin"]["use"] for r in hooks} == {"h2": "in_category", "h3": "in_category"}
    assert out["plugin"]["hooks_not_read"] == ["h1", "h4", "h5"]  # listed, never fetched: not in the pool
    assert sorted(_read(run.path / "02_research" / "snapshot_v01.json")["pool_ids"]) == \
        ["h1", "h2", "h3", "h4", "h5", "t1", "t2"]


# --- the seasonal guard reads the event the agent named (issue #3, item 5) ---------------------

def test_growth_puts_a_trend_past_its_peak_by_the_event_the_agent_named(tmp_path):
    """The agent names each trend's event in the market language (the map review, a hook's judgement), so
    the guard works in any language; a row from before (no `event` key) still reads the English list."""
    run = _run(tmp_path)
    cmap = _read(run.path / "02_research" / "category_map_v01.json")
    cmap["kept"][0] |= {"name": "Paznokcie na Wszystkich Świętych",
                        "event": {"name": "Wszystkich Świętych", "date": "2026-11-01"}}
    cmap["kept"][1] |= {"name": "Halloween velvet nails", "event": None}        # the agent: no dated event
    cmap["kept"].append({"id": "t3", "name": "Halloween chrome nails", "kind": "topic_trend", "group": "nails",
                         "sub_category": "nails", "status": "confirmed"})       # a map from before: no key
    cmap["kept"].append({"id": "t4", "name": "Andrzejki nails", "kind": "topic_trend", "group": "nails",
                         "sub_category": "nails", "status": "confirmed",
                         "event": {"name": "Andrzejki", "date": "2026-11-29"}})  # still ahead
    (run.path / "02_research" / "category_map_v01.json").write_text(json.dumps(cmap), encoding="utf-8")
    for tid in ("t1", "t2", "t3", "t4"):
        _videos(run, tid, _texts("nails", 3))
    research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", _texts("ネイル", 2))
    _videos(run, "h3", _texts("nails", 2))
    research_growth.hooks(run, _judge(run, h2={"name": "ハロウィン", "date": "2026-10-31"}), _cfg())
    rows = {r["id"]: r for r in _read(research_growth.compute(run, AS_OF, _cfg()))["trends"]}
    assert rows["t1"]["seasonal_over"] == "seasonal: Wszystkich Świętych (2026-11-01) is over"
    assert rows["h2"]["seasonal_over"] == "seasonal: ハロウィン (2026-10-31) is over"
    assert rows["t1"]["bucket"] == rows["h2"]["bucket"] == "past_peak"
    assert rows["t2"]["seasonal_over"] is None and rows["t4"]["seasonal_over"] is None
    assert rows["h3"]["seasonal_over"] is None
    assert rows["t3"]["seasonal_over"] == "seasonal: halloween (2026-10-31) is over"   # the English list
    ref = date(2026, 11, 2)
    assert research_growth.event_passed({"event": {"name": "Ōmisoka", "date": "2026-12-31"}}, date(2027, 1, 5)) \
        == "seasonal: Ōmisoka (2026-12-31) is over"
    assert research_growth.event_passed({"event": {"name": "x", "date": "2026-11-01"}}, ref, 0) is None
    assert research_growth.event_passed({"name": "Halloween nails", "event": None}, ref) is None


def test_growth_of_a_hooks_file_from_before_the_judgement(tmp_path):
    """A run whose hooks path matched words (before issue #3) still computes: its hook rows have no `event`
    key, so the English list guards them, and their use stays as written."""
    run = _run(tmp_path)
    for tid in ("t1", "t2"):
        _videos(run, tid, _texts("nails", 3))
    research_growth.hook_fit(run, FIT, _cfg(2))
    _videos(run, "h2", _texts("nail", 2))
    _videos(run, "h3", _texts("nail", 2))
    path = research_growth.hooks(run, _judge(run, {"h3": 0}), _cfg())
    old = _read(path)
    old["terms"] = ["nail"]
    for r in old["kept"]:
        r.pop("event")
        r["plugin"].pop("use_why")
        r["name"] = "pov: halloween " + r["name"]
    path.write_text(json.dumps(old), encoding="utf-8")
    rows = {r["id"]: r for r in _read(research_growth.compute(run, AS_OF, _cfg()))["trends"]}
    assert rows["h2"]["seasonal_over"] == "seasonal: halloween (2026-10-31) is over"
    assert (rows["h2"]["plugin"]["use"], rows["h3"]["plugin"]["use"]) == ("in_category", "transfer")


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
    _videos(run, "h2", _texts("nail", 4))
    _videos(run, "h3", _texts("nail", 2))
    _videos(run, "h6", _texts("nail", 2))
    research_growth.hooks(run, _judge(run), _cfg())
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
    out = _read(research_growth.hooks(run, _judge(run), _cfg()))
    assert {r["plugin"]["ad_library"] for r in out["kept"]} == {None} and out["ad_library"] is None  # not checked
    _ads(run, "pov nail salon", [{"page_name": "Salon A"}])
    _ads(run, "start your manicure with")
    _hook_ads(run, HOOK_ADS)
    out = _read(research_growth.hooks(run, _judge(run), _cfg()))
    kept = {r["id"]: r["plugin"]["ad_library"] for r in out["kept"]}
    assert kept["h2"] == {"verdict": "competitor_found", "query": "pov nail salon", "advertisers": ["Salon A (2 ads)"]}
    assert kept["h3"] == {"verdict": "none_found", "query": "start your manicure with", "advertisers": []}
    assert out["ad_library"] == "02_research/hooks_ad_library_v01.json"
    # a check that no longer covers the shortlist stops the hooks path, writing nothing
    research_growth.hook_fit(run, FIT, _cfg(3))                           # h1 is shortlisted now
    _videos(run, "h1", ["nail"])
    with pytest.raises(Stop, match="day _ of _"):
        research_growth.hooks(run, _judge(run), _cfg())
    assert not (run.path / "02_research" / "hooks_in_category_v03.json").exists()
    _hook_ads(run, {"checked": False, "checks": []}, nn=2)                # Meta went away: not checked
    out = _read(research_growth.hooks(run, _judge(run), _cfg()))
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
