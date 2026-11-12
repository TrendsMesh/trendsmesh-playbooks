"""Trends for a channel (organic video B1–B3): niche anchors and sound relevance in the shortlist, stale
rows, the channel's used trends, series and decision history, `tm organic videos`, the B2 and B3 step
checks on the ExampleEdu walkthrough, and a trend research seed starting an organic run."""

import json
from datetime import date, timedelta

import pytest

import ld
import exampleedu
from tm import (brand, brief_config, brief_research, library, manifest, organic_research, runcmd, seeds, shortlist, state,
                stepchecks, trends)
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO, TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

GOLDEN = ld.REPO / "plugins" / "trendsmesh-playbooks" / "engine" / "tests" / "fixtures" / "shortlist"
ANCHOR_DROP = "no niche anchor next to the activity term"
TODAY = date(2026, 11, 7)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _row(tid, kind, name, what=""):
    label = {"hook_trend": "hook", "topic_trend": "topic", "format_trend": "format", "sound_trend": "sound"}[kind]
    return {"id": tid, "kind": kind, "label": label, "name": name, "what_it_is": what, "reason": "matches groom"}


def _video(published="2026-11-05T10:00:00Z", hook=None, excerpt=None, **kw):
    return {"asset_id": kw.pop("asset_id", f"a-{published}-{hook}-{excerpt}"), "url": "https://www.tiktok.com/@x/video/1",
            "creator": "x", "published": published, "views": 1000, "hook_text": hook, "excerpt": excerpt, **kw}


def _organic_run(ws, name="pets"):
    return RunFolder.create(ws, name, TODAY, playbook=ORGANIC_VIDEO)


# --- niche anchors (ANALYSIS lesson 2) ------------------------------------------------------------

def test_anchor_drops_human_grooming_keeps_dog_grooming():
    rows = [_row("t-hair", "topic_trend", "Curly hair grooming routine", "Brushing and styling curls at home"),
            _row("t-dog", "topic_trend", "Dog grooming ASMR", "Calm brushing sounds"),
            _row("t-bath", "format_trend", "Before and after bath", "A wash, then the reveal"),
            _row("t-brow", "topic_trend", "Eyebrow grooming hacks", "Shaping brows"),
            _row("t-word", "topic_trend", "Hot-dog pasta hack", "A pasta recipe")]   # lesson 2: "hot-dog" is no dog
    cards = {"t-bath": {"examples": [_video(hook="POV: your puppy's first bath")]},       # the anchor in the evidence
             "t-brow": {"examples": [_video(excerpt="petals and brows")]}}               # "pet" is not "petals"
    kept, dropped = shortlist.anchor_filter(rows, cards, ["dog", "pet", "puppy"])
    assert [r["id"] for r in kept] == ["t-dog", "t-bath"]
    assert [r["id"] for r in dropped] == ["t-hair", "t-brow", "t-word"]
    assert all(r["reason"] == ANCHOR_DROP for r in dropped)
    assert rows[0]["reason"] == "matches groom"                       # the caller's rows are untouched
    assert shortlist.anchor_filter(rows, cards, []) == (rows, [])      # no anchors: nothing is dropped


def test_anchor_matches_plain_plurals_not_compounds():
    rows = [_row("t-dogs", "topic_trend", "Two dogs and a ball"),
            _row("t-boxes", "topic_trend", "Subscription boxes unboxing"),          # box + es
            _row("t-hot", "topic_trend", "Hot-dog pasta hack"),                      # a compound stays one word
            _row("t-cafe", "topic_trend", "Dog-friendly cafes"),
            _row("t-sled", "topic_trend", "Dogsled racing"),                         # not a plural: the word goes on
            _row("t-hotdogs", "topic_trend", "Hot-dogs at the stadium")]
    kept, dropped = shortlist.anchor_filter(rows, {}, ["dog", "box"])
    assert [r["id"] for r in kept] == ["t-dogs", "t-boxes"]
    assert [r["id"] for r in dropped] == ["t-hot", "t-cafe", "t-sled", "t-hotdogs"]
    assert shortlist.anchor_regex("grooming kit").search("Two grooming kits")       # the last word's plural


def _topic(tid, name, what, creators=10):
    return {"id": tid, "kind": "topic_trend", "name": name, "what_it_is": what, "status": "confirmed",
            "momentum": "rising", "reach": {"creators": creators, "views": 5000},
            "since": "2026-10-20T00:00:00Z", "active_for_days": 15}


def test_anchors_drop_through_write_before_the_weak_fill(ws, capsys):
    """The anchors run before --min-topics' weak fill: the minimum holds with a weak topic that carries an
    anchor, and one without is never offered. The dropped rows are in the JSON, the page and the manifest.
    A format is never dropped by the anchors (issue #84): it is ranked by its fit for the channel."""
    run = _organic_run(ws)
    cards = [_topic("t-dog", "Dog grooming at home", "Brushing a dog"),
             _topic("t-hair", "Curly hair grooming routine", "Styling curls"),
             _topic("w-pup", "Morning walk with my puppy", "A slow walk", creators=5),
             _topic("w-rain", "Rainy day playlist", "Songs for a grey day", creators=40),
             {**_topic("f-bath", "Before and after bath", "A wash, then the reveal"), "kind": "format_trend"}]
    trends.save_answer(run, "search_trends", {"about": "grooming"}, {"data": cards})
    plain = shortlist.write(run, shortlist.input_files(run, None), ["grooming"], today=TODAY, min_topics=2)
    plain_topics = json.loads((run.path / plain["json"]).read_text(encoding="utf-8"))["topics"]
    assert sorted(r["id"] for r in plain_topics) == ["t-dog", "t-hair"]     # without anchors: both term matches

    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "grooming", "--today",
                     TODAY.isoformat(), "--min-topics", "2", "--anchor-terms", "dog,puppy")
    assert code == 0 and out["anchor_dropped"] == 1, out
    data = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    assert [r["id"] for r in data["topics"]] == ["t-dog", "w-pup"]          # the minimum, with an anchored weak fit
    assert "weak fit (no term match)" in data["topics"][1]["flags"]
    assert [r["id"] for r in data["formats"]] == ["f-bath"]
    assert data["anchor_dropped"] == [
        {"id": "t-hair", "name": "Curly hair grooming routine", "label": "topic", "reason": ANCHOR_DROP}]
    assert data["meta"]["topics_kept"] == 2
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert f"Niche anchors: dog, puppy. Dropped ({ANCHOR_DROP}): `t-hair` Curly hair grooming routine (topic)." in md
    row = next(r for r in manifest.rows(run) if r["file"] == out["json"])
    params = json.loads(row["params"])
    assert (params["anchor_terms"], params["sound_relevance"], params["recent_days"]) == (["dog", "puppy"], False, None)


def test_hooks_exempt_from_anchor():
    rows = [_row("h1", "hook_trend", "POV: _ but it's Monday"), _row("s1", "sound_trend", "Masti Jaan Ke"),
            _row("t1", "topic_trend", "Curly hair grooming routine")]
    kept, dropped = shortlist.anchor_filter(rows, {}, ["dog", "pet", "puppy"])
    assert [r["id"] for r in kept] == ["h1", "s1"] and [r["id"] for r in dropped] == ["t1"]


# --- sound relevance (ANALYSIS lesson 1) ----------------------------------------------------------

def _sound(tid, name, what, creators, captions):
    return {"id": tid, "kind": "sound_trend", "name": name, "what_it_is": what, "status": "confirmed",
            "momentum": "rising", "reach": {"creators": creators, "views": 100000},
            "since": "2026-10-20T00:00:00Z", "active_for_days": 15,
            "examples": [_video(excerpt=c, asset_id=f"{tid}-{i}") for i, c in enumerate(captions)]}


def test_sound_relevance_from_captions(ws, capsys):
    pet = _sound("s-pet", "Masti Jaan Ke", "A Bollywood track used for playful clips", 20,
                 ["my dog doing zoomies", "puppy vs cucumber", "pet tax"])
    news = _sound("s-news", "Breaking news sting", "News audio used for announcements", 222,
                  ["election night", "the market fell today"])
    terms = ["dog", "pet", "puppy"]
    assert shortlist.sound_relevance(pet, pet["examples"], terms) == {"score": 1.0, "matched": ["dog", "pet", "puppy"]}
    assert shortlist.sound_relevance(news, news["examples"], terms) == {"score": 0.0, "matched": []}
    half = shortlist.sound_relevance({"what_it_is": "Pet videos"}, [_video(hook="a dog")], ["dog", "pet", "cat", "bird"])
    assert half == {"score": 0.5, "matched": ["dog", "pet"]}     # what_it_is and the evidence texts

    run = _organic_run(ws)
    trends.save_answer(run, "search_trends", {"about": "dog sounds"}, {"data": [pet, news]})
    plain = shortlist.write(run, shortlist.input_files(run, None), ["sound"], today=TODAY)
    by_usability = json.loads((run.path / plain["json"]).read_text(encoding="utf-8"))["sounds"]
    assert [r["id"] for r in by_usability] == ["s-news", "s-pet"]           # usability alone: the news clip

    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "sound", "--today",
                     TODAY.isoformat(), "--anchor-terms", "dog,pet,puppy", "--sound-relevance")
    assert code == 0, out
    sounds = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))["sounds"]
    assert [r["id"] for r in sounds] == ["s-pet", "s-news"]                 # ranked by niche relevance
    assert sounds[0]["plugin"]["relevance"] == {"score": 1.0, "matched": ["dog", "pet", "puppy"]}
    weak = sounds[1]
    assert weak["plugin"]["relevance"]["score"] == 0.0                       # it stays: never "no trend found"
    assert "weak fit (no niche relevance)" in weak["flags"] and "weak fit (no niche relevance)" in weak["reason"]
    assert [r["rank"] for r in sounds] == [1, 2]
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert "weak fit (no niche relevance)" in md and "no trend found" not in md.lower()

    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "sound,dog", "--today",
                     TODAY.isoformat(), "--sound-relevance")                 # no anchors: the terms
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert md.endswith("## Plugin filters\n\nSounds ranked by their niche relevance to: sound, dog.\n")


@pytest.mark.private_data
def test_pb04_shortlist_golden_unchanged_without_flags(tmp_path, capsys):
    run = RunFolder.create(tmp_path, "ld", TODAY, playbook=ORGANIC_VIDEO)
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms",
                     "lucid dream,dream,sleep,night,journal,wake up,4am,consciousness", "--today", "2026-11-04",
                     "--inputs", str(ld.TRENDS / "*.json"))
    assert code == 0, out
    mine = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    golden = json.loads((GOLDEN / "golden_v02.json").read_text(encoding="utf-8"))
    for payload in (mine, golden):
        payload["meta"]["inputs"] = [p.replace("\\", "/").rsplit("/", 1)[-1] for p in payload["meta"]["inputs"]]
    assert mine == golden                                    # no plugin block, no dropped list, same order
    assert "plugin" not in mine["meta"] and "anchor_dropped" not in mine
    assert not any("plugin" in r for key in ("hooks", "topics", "formats", "sounds") for r in mine[key])
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    want = (GOLDEN / "golden_v02.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert md == want.replace("Generated by `tools/pb2/trend_shortlist.py`.", "Generated by `tm trends shortlist`.")


def test_stale_rows_marked_by_recent_days(ws, capsys):
    run = _organic_run(ws)
    hook = {"kind": "hook_trend", "status": "confirmed", "momentum": "rising", "reach": {"creators": 10}}
    cards = [{**hook, "id": "h-new", "name": "POV: _", "examples": [_video("2026-10-01T00:00:00Z")]},
             {**hook, "id": "h-old", "name": "Nobody: _", "examples": [_video("2026-10-20T00:00:00Z")]},
             {**hook, "id": "h-none", "name": "Wait for it"}]
    trends.save_answer(run, "search_trends", {"about": "hooks"}, {"data": cards})
    trends.save_answer(run, "get_trend_videos", {"trend_id": "h-new"},     # the newest saved evidence counts
                       {"data": [_video("2026-11-04T08:00:00Z", asset_id="v-new")], "page": 1, "has_more": False})
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "pov", "--today",
                     TODAY.isoformat(), "--recent-days", "7")
    assert code == 0, out
    data = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    marks = {r["id"]: {k: v for k, v in r["plugin"].items() if k != "fit"} for r in data["hooks"]}
    # Issue #84: only a trend whose videos are pulled (B3) can be old; before, its evidence is not pulled yet.
    assert marks == {"h-new": {"stale": False, "newest_evidence": "2026-11-04", "videos_pulled": True},
                     "h-old": {"stale": None, "newest_evidence": "2026-10-20", "videos_pulled": False},
                     "h-none": {"stale": None, "newest_evidence": None, "videos_pulled": False}}
    assert data["meta"]["plugin"] == {"anchor_terms": [], "sound_relevance": False, "recent_days": 7,
                                      "fit_file": None, "min_fit": 3.0}
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert "No evidence in the last 7 days: none." in md
    assert "Evidence videos not pulled yet (B3 pulls them): `h-old` Nobody: _; `h-none` Wait for it." in md
    trends.save_answer(run, "get_trend_videos", {"trend_id": "h-old"},
                       {"data": [_video("2026-10-21T08:00:00Z", asset_id="v-old")], "page": 1, "has_more": False})
    trends.save_answer(run, "get_trend_videos", {"trend_id": "h-none"}, {"data": [], "page": 1, "has_more": False})
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "pov", "--today",
                     TODAY.isoformat(), "--recent-days", "7")
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert "No evidence in the last 7 days: `h-old` Nobody: _; `h-none` Wait for it." in md
    assert "not pulled yet" not in md
    assert _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "pov",
                "--recent-days", "0")[0] == 1


# --- issue #84: hooks and formats ranked by fit, an organic video's words -----------------------------------

CB3 = ("brand_fit", "persona_fit", "bridge", "lifecycle", "transfer", "sensitivity", "feasibility")


def _fit(score: int, why: str, **over) -> dict:
    return {**dict.fromkeys(CB3, score), **over, "why": why}


def _explainer_pool(run) -> None:
    """An explainer channel's pool: formats whose words never name the niche, hooks, a topic, a sound."""
    base = {"status": "confirmed", "momentum": "rising", "reach": {"creators": 12, "views": 90000}}
    cards = [{**base, "id": "f-talk", "kind": "format_trend", "name": "Selfie Talking-Head Explainer",
              "what_it_is": "One person explains to the camera"},
             {**base, "id": "f-dance", "kind": "format_trend", "name": "Couple dance challenge",
              "what_it_is": "Two people dance in sync", "reach": {"creators": 40, "views": 900000}},
             {**base, "id": "h-day", "kind": "hook_trend", "name": "day _ of _", "what_it_is": "A counted series"},
             {**base, "id": "h-be", "kind": "hook_trend", "name": "_ be like", "what_it_is": "A skit opener",
              "reach": {"creators": 30, "views": 500000}},
             {**base, "id": "t-ai", "kind": "topic_trend", "name": "New AI tools this week",
              "what_it_is": "News about AI tools"},
             {**base, "id": "s-1", "kind": "sound_trend", "name": "Lo-fi beat", "what_it_is": "A calm beat"}]
    trends.save_answer(run, "search_trends", {"about": "ai"}, {"data": cards})


def _ov_shortlist(capsys, run, *extra):
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "ai,tools", "--anchor-terms",
                     "ai,tools,tech", "--sound-relevance", "--today", TODAY.isoformat(), "--recent-days", "7", *extra)
    return code, out


def test_hooks_and_formats_are_ranked_by_the_channels_fit(ws, capsys):
    """Issue #84: no word filter drops a format; the agent's fit for the channel (Creative brief's CB3
    criteria, as Trend research scores its hooks) ranks hooks and formats, shown with one line on why."""
    run = _organic_run(ws, "explainer")
    _explainer_pool(run)
    code, out = _ov_shortlist(capsys, run)
    assert code == 0 and out["fit_scored"] is False and out["fit_candidates"] == 4, out
    assert "not scored for the channel yet" in out["todo"] and "--fit" in out["todo"]
    first = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    assert {c["id"] for c in first["fit_candidates"]} == {"f-talk", "f-dance", "h-day", "h-be"}
    assert [r["id"] for r in first["formats"]] == ["f-dance", "f-talk"]          # by usability, before the fit
    assert first["formats"][0]["reason"].startswith("fit not scored yet; ")

    fit = {"f-talk": _fit(5, "the channel explains to camera every day"),
           "f-dance": _fit(1, "a dance has nothing to explain", feasibility=2),
           "h-day": _fit(4, "a counted series of explainers"),
           "h-be": _fit(2, "a skit opener, not how the channel talks")}
    (run.path / "03_wip" / "trend_fit_v01.json").write_text(json.dumps(fit), encoding="utf-8")
    code, out = _ov_shortlist(capsys, run, "--fit", "03_wip/trend_fit_v01.json")
    assert code == 0 and out["fit_scored"] is True, out
    data = json.loads((run.path / out["json"]).read_text(encoding="utf-8"))
    assert [r["id"] for r in data["formats"]] == ["f-talk", "f-dance"]
    assert [r["id"] for r in data["hooks"]] == ["h-day", "h-be"]
    talk, dance = data["formats"]
    assert talk["plugin"]["fit"] == {"score": 5.0, "why": "the channel explains to camera every day"}
    assert talk["reason"].startswith("fit 5.0/5: the channel explains to camera every day; ")
    assert dance["plugin"]["fit"]["score"] == 1.14 and "weak fit for this channel" in dance["flags"]
    assert data["meta"]["plugin"]["fit_file"] == "03_wip/trend_fit_v01.json"
    assert [r["id"] for r in data["topics"]] == ["t-ai"]
    md = (run.path / out["md"]).read_text(encoding="utf-8")
    assert "fit 5.0/5: the channel explains to camera every day" in md
    assert "ranked by their fit for this channel" in md


def test_b2_waits_for_the_fit_scores(ws, capsys):
    """B2's check: a shortlist that lists hooks or formats to score is done once they are scored (--fit); one
    written before issue #84 (no fit_candidates) is not asked for them."""
    run = _organic_run(ws, "explainer")
    _explainer_pool(run)
    out = _ov_shortlist(capsys, run)[1]
    assert "scored for the channel" in organic_research.shortlist_gap(run)
    path = run.path / out["json"]
    old = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({k: v for k, v in old.items() if k != "fit_candidates"}), encoding="utf-8")
    assert organic_research.shortlist_gap(run) is None
    fit = {c["id"]: _fit(3, "fits") for c in old["fit_candidates"]}
    (run.path / "03_wip" / "trend_fit_v01.json").write_text(json.dumps(fit), encoding="utf-8")
    assert _ov_shortlist(capsys, run, "--fit", "03_wip/trend_fit_v01.json")[0] == 0
    assert organic_research.shortlist_gap(run) is None


def test_fit_scores_that_do_not_hold_are_refused(ws, capsys):
    run = _organic_run(ws, "explainer")
    _explainer_pool(run)
    bad = {"f-talk": _fit(6, "x"), "h-day": {**_fit(4, ""), "why": " "}, "t-ai": _fit(3, "a topic")}
    (run.path / "03_wip" / "trend_fit_v01.json").write_text(json.dumps(bad), encoding="utf-8")
    code, out = _ov_shortlist(capsys, run, "--fit", "03_wip/trend_fit_v01.json")
    assert code == 1
    said = out["message"]
    assert "brand_fit 6 is outside 1-5" in said and "why is not one line" in said
    assert "t-ai is not a hook or format" in said and "2 hooks and formats are not scored" in said
    assert not list((run.path / "03_wip").glob("trend_shortlist_*"))


def test_fit_is_for_organic_video_only(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    run = RunFolder.create(tmp_path, "ld", TODAY, playbook=TREND_RESEARCH)
    trends.save_answer(run, "search_trends", {"about": "x"}, {"data": []})
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(run.path), "--terms", "x", "--fit", "{}")
    assert code == 1 and "tm research hook-fit" in out["message"]


def test_the_organic_shortlist_speaks_of_organic_videos(ws, tmp_path, capsys, monkeypatch):
    """Issue #84: an organic video's shortlist says how its sounds and formats are used; a creative brief's
    keeps its own ad words."""
    run = _organic_run(ws, "explainer")
    _explainer_pool(run)
    md = (run.path / _ov_shortlist(capsys, run)[1]["md"]).read_text(encoding="utf-8")
    assert "A trending sound is added in the app when you post, for organic videos only." in md
    assert "A format is used only if the video can be made honestly." in md
    assert "ad brief" not in md and "CB9" not in md and "the ad can be made" not in md

    other = tmp_path / "brief"
    other.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(other))
    brief = RunFolder.create(other, "brief", TODAY, playbook=CREATIVE_BRIEF)
    _explainer_pool(brief)
    code, out = _cli(capsys, "trends", "shortlist", "--run", str(brief.path), "--terms", "ai")
    md = (brief.path / out["md"]).read_text(encoding="utf-8")
    assert "get a licensed equivalent in the ad brief (CB9)" in md and "the ad can be made honestly" in md
    assert "fit_candidates" not in json.loads((brief.path / out["json"]).read_text(encoding="utf-8"))


# --- the channel's used trends, series and history --------------------------------------------------

def test_used_trend_listed_and_series_continue(ws, capsys):
    rows = [{"trend_id": "c20bfd6594454889ab50eab2743364b0", "name": "Tung Tung Tung Sahur", "kind": "topic_trend",
             "run": "2026-11-06_exampleedu-m1", "video": "M1", "used": "2026-11-06", "series": "Brainrot decoded"},
            {"trend_id": "0112ede8aaaa", "name": "what sounds in the head of _", "kind": "hook_trend",
             "run": "2026-11-06_exampleedu-m1", "video": "M1", "used": "2026-11-06", "series": None}]
    assert organic_research.record_used(ws, "ExampleEdu", rows) == 2
    path = ws / "library" / "organic" / "exampleedu" / "used_trends.jsonl"
    assert library.read_jsonl(path) == (rows, [])
    assert set(organic_research.used(ws, "exampleedu")) == {"c20bfd6594454889ab50eab2743364b0", "0112ede8aaaa"}

    later = {**rows[0], "trend_id": "9a17a078bbbb", "name": "dad, why is _", "kind": "hook_trend",
             "run": "2026-11-13_exampleedu-m7", "video": "M7", "used": "2026-11-13"}
    assert organic_research.record_used(ws, "exampleedu", [later]) == 1
    assert organic_research.series(ws, "exampleedu") == [
        {"series": "Brainrot decoded", "episodes": 2, "trend_ids": ["c20bfd6594454889ab50eab2743364b0", "9a17a078bbbb"],
         "videos": ["2026-11-06_exampleedu-m1/M1", "2026-11-13_exampleedu-m7/M7"], "last_used": "2026-11-13"}]

    code, out = _cli(capsys, "organic", "used", "--channel", "ExampleEdu")
    assert code == 0 and [r["trend_id"] for r in out["used"]] == ["c20bfd6594454889ab50eab2743364b0", "0112ede8aaaa",
                                                                    "9a17a078bbbb"]
    assert out["series"][0]["episodes"] == 2
    with pytest.raises(ValueError, match="trend_id"):
        organic_research.record_used(ws, "exampleedu", [{**later, "trend_id": ""}])
    for bad in ({"used": "13/11/2026"}, {"used": "2026-13-01"}, {"used": "2026-11-13T10:00"}, {"kind": "meme"},
                {"kind": None}):
        with pytest.raises(ValueError, match="used|kind"):
            organic_research.record_used(ws, "exampleedu", [{**later, **bad}])
    assert len(library.read_jsonl(path)[0]) == 3                     # nothing appended by a refused row

    brand.save(ws, {**exampleedu.PROFILE, "channel": "Cat Corner"}, run=None)   # a profile, no log yet
    code, out = _cli(capsys, "organic", "used", "--channel", "Cat Corner")
    assert code == 0 and out["used"] == [] and out["series"] == []
    assert _cli(capsys, "organic", "history", "--channel", "cat-corner")[1]["history"]["decisions"] == 0
    for action in ("used", "history"):                                # a typo is said, never "nothing yet"
        code, out = _cli(capsys, "organic", action, "--channel", "exampleedo")
        assert code == 1 and "No channel 'exampleedo'" in out["message"] and "cat-corner" in out["message"]

    decisions = ws / "library" / "organic" / "exampleedu" / "decisions.jsonl"
    library.append_jsonl(decisions, [
        {"proposal": "M1", "decision": "produce", "production": "animation", "approach": "inspire"},
        {"proposal": "M2", "decision": "skip", "production": "talking_character", "approach": "recreate"},
        {"proposal": "M4", "decision": "later", "production": "animation", "approach": "recreate"},
        {"proposal": "M1", "decision": "redo", "production": "animation", "approach": "inspire"}])
    assert organic_research.history(ws, "exampleedu") == {
        "decisions": 4,
        "by_production": {"animation": {"produce": 1, "later": 1, "skip": 0, "redo": 1},
                          "talking_character": {"produce": 0, "later": 0, "skip": 1, "redo": 0}},
        "by_approach": {"inspire": {"produce": 1, "later": 0, "skip": 0, "redo": 1},
                        "recreate": {"produce": 0, "later": 1, "skip": 1, "redo": 0}}}
    code, out = _cli(capsys, "organic", "history", "--channel", "exampleedu")
    assert code == 0 and out["history"]["decisions"] == 4

    with open(path, "a", encoding="utf-8") as fh:              # a damaged line is a Stop that names it
        fh.write("{not json\n")
    with pytest.raises(Stop, match="line 4"):
        organic_research.used(ws, "exampleedu")
    code, out = _cli(capsys, "organic", "used", "--channel", "exampleedu")
    assert code == 2 and out["status"] == "stop" and out["message"].endswith(AGAIN + ".")
    assert "library/organic/exampleedu/used_trends.jsonl" in out["message"].replace("\\", "/")


# --- the ExampleEdu walkthrough: B2 and B3 ------------------------------------------------------------

def _shortlist(run, inputs=None):
    files = shortlist.input_files(run, inputs)
    return shortlist.write(run, files, ["roblox", "brainrot", "school", "game", "party", "halloween", "chatgpt",
                                        "adopt me", "tung"], today=TODAY)


@pytest.mark.private_data
def test_exampleedu_run_builds_and_evidence_saved(tmp_path):
    run = exampleedu.build(tmp_path / "ws")
    ids = exampleedu.full_ids()
    assert list(ids) == ["c20bfd65", "0112ede8", "8f8de71e", "e54e5955", "829ecf9b", "9a17a078", "5f1691dd",
                         "abf9ffed", "3abc109a", "7d60086a", "8db205e0", "250013b0"]
    research = run.path / "02_research"
    assert sorted(p.name for p in research.glob("trend_*.json")) == sorted(f"trend_{t}.json" for t in ids.values())
    assert sorted(p.name for p in (research / "videos").iterdir()) == sorted(f"{t}_p01.json" for t in ids.values())
    assert len(list((research / "search").glob("search_*.json"))) == 17
    assert (research / "search" / "search_dzieci_gry.json").is_file()
    assert trends.read(research / "search" / "search_grow_a_garden.json")["_input"]["about"] == "Grow a Garden"
    assert (tmp_path / "ws" / "library" / "channels" / "exampleedu" / "channel_v01.json").is_file()
    copied = (run.path / "03_wip" / "proposals_v02.json").read_text(encoding="utf-8")
    assert copied == exampleedu.PROPOSALS.read_text(encoding="utf-8")

    assert "tm trends shortlist" in organic_research.shortlist_gap(run)
    assert "tm trends shortlist" in organic_research.evidence_gap(run)
    wide = _shortlist(run)                                     # every saved search: top trends without cards
    assert stepchecks.run("shortlist_written", run) is None
    gap = stepchecks.run("evidence_saved", run)
    assert gap.startswith("the card and a video page of each of the shortlist's top 12 trends are saved")
    assert "get_trend" in gap and wide["json"] in gap

    narrow = _shortlist(run, [str(research / "trend_*.json"), str(research / "videos" / "*.json")])
    data = json.loads((run.path / narrow["json"]).read_text(encoding="utf-8"))
    top = organic_research.top_trends(data, 12)
    assert top and {r["id"] for r in top} <= set(ids.values())
    assert stepchecks.run("evidence_saved", run) is None
    s = state.load(run)
    s.created = "2099-01-01"                                   # a shortlist from before the run: B2 again
    state.save(run, s)
    assert "in this run" in organic_research.shortlist_gap(run)


@pytest.mark.private_data
def test_error_answer_is_not_evidence(tmp_path, capsys):
    run = exampleedu.build(tmp_path / "ws")
    research = run.path / "02_research"
    _shortlist(run, [str(research / "trend_*.json"), str(research / "videos" / "*.json")])
    data = json.loads(run.latest("03_wip", "trend_shortlist", "json").read_text(encoding="utf-8"))
    first, second = organic_research.top_trends(data, 12)[:2]
    trends.save_answer(run, "get_trend", {"trend_id": first["id"]}, {"error": "Trend not found"})
    gap = organic_research.evidence_gap(run)
    assert first["id"][:8] in gap and "error answer" in gap and second["id"][:8] not in gap

    for f in trends.video_files(run, second["id"]):
        f.unlink()
    trends.save_answer(run, "get_trend_videos", {"trend_id": second["id"]}, {"error": "rate limited"})
    gap = organic_research.evidence_gap(run)
    assert second["id"][:8] in gap and "get_trend_videos" in gap

    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", first["id"][:8])
    assert code == 2 and "error answer" in out["message"] and out["message"].endswith(AGAIN + ".")

    third = organic_research.top_trends(data, 12)[2]                  # a page that holds no video
    for f in trends.video_files(run, third["id"]):
        f.unlink()
    trends.save_answer(run, "get_trend_videos", {"trend_id": third["id"]}, {"data": [], "page": 1, "has_more": False})
    assert third["id"][:8] in organic_research.evidence_gap(run)
    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", third["id"][:8])
    assert code == 2 and "holds a video" in out["message"]


@pytest.mark.private_data
def test_videos_lists_saved_order_with_hooks(tmp_path, capsys):
    run = exampleedu.build(tmp_path / "ws")
    saved = json.loads((exampleedu.TRENDS / "videos_0112ede8.json").read_text(encoding="utf-8"))["videos"]
    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", "0112ede8")
    assert code == 0, out
    assert out["trend_id"] == exampleedu.full_ids()["0112ede8"] and out["name"] == "what sounds in the head of _"
    assert [v["index"] for v in out["videos"]] == list(range(len(saved)))
    assert [v["url"] for v in out["videos"]] == [v["url"] for v in saved]
    assert out["videos"][2] == {"index": 2, "url": saved[2]["url"], "creator": saved[2]["creator"],
                                "views": saved[2]["views"], "published": saved[2]["published"],
                                "hook_text": saved[2]["hook_text"], "excerpt": saved[2]["excerpt"]}
    assert all(v["hook_text"] for v in out["videos"])         # what the agent picks evidence by
    proposals = json.loads(exampleedu.PROPOSALS.read_text(encoding="utf-8"))
    m1 = next(t for t in proposals["proposals"][0]["trends"] if t["id"] == "0112ede8")
    assert max(m1["pick"]) < len(out["videos"])               # a pick index is into this order

    assert _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", out["trend_id"])[1]["videos"] == out["videos"]
    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", "8")   # 8f8de71e, 829ecf9b, 8db205e0
    assert code == 1 and "8f8de71e" in out["message"] and "829ecf9b" in out["message"]
    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", "ffffffff")
    assert code == 2 and "get_trend" in out["message"]
    code, out = _cli(capsys, "organic", "videos", "--run", str(run.path), "--trend", "../x")
    assert code == 1
    capsys.readouterr()
    assert main(["organic", "videos", "--run", str(run.path), "--trend", "0112ede8"]) == 0
    text = capsys.readouterr().out
    assert text.splitlines()[0].startswith("what sounds in the head of _") and saved[0]["url"] in text


# --- a trend research seed starts an organic run (drift check 8) -------------------------------------

def _seed(**kw):
    base = {"schema": seeds.SCHEMA, "seed_id": "2026-11-04_kids:t1", "source": "pb4", "run": "2026-11-04_kids",
            "created": "2026-11-04", "category": "parenting", "sub_category": "kids gaming", "market": "PL",
            "trend_id": "t1", "kind": "topic_trend", "trend_name": "Brainrot slang", "bucket": "act_now",
            "band": "top 25%", "paid_level": "crowded", "angle": "Decode one word.", "risk": "One account.",
            "valid_until": (TODAY + timedelta(days=10)).isoformat(), "report": None,
            "evidence": "runs/04-trend-research/2026-11-04_kids/02_research/videos/t1*.json"}
    return {**base, **kw}


class _Today(date):
    """`tm run new` dates the run TODAY (runcmd's `date.today()`)."""

    @classmethod
    def today(cls):
        return TODAY


def test_seed_starts_an_organic_run_and_brief_seed_unchanged(ws, bundled_skills, capsys, monkeypatch):
    """Fixed dates throughout: the run is created on TODAY, the seed check reads TODAY, the fresh card is saved on
    TODAY (its `_at` is UTC and the run's date local, so the clock would split them around midnight)."""
    monkeypatch.setattr(runcmd, "date", _Today)
    monkeypatch.setattr(brief_research, "_today", lambda: TODAY)
    seeds.add(ws, _seed())
    seeds.add(ws, _seed(seed_id="2026-11-04_kids:t2", trend_id="t2", valid_until="2026-10-30"))
    code, out = _cli(capsys, "run", "new", "--playbook", "organic-video", "--name", "kids", "--seed", "2026-11-04_kids:t1")
    assert code == 0, out
    run = RunFolder.open(out["path"])
    s = state.load(run)
    assert s.organic == {"seed": "2026-11-04_kids:t1"} and s.brief is None
    assert json.loads((run.path / "00_raw" / "seed.json").read_text(encoding="utf-8")) == _seed()
    assert brief_config.seed_row(run)["trend_id"] == "t1"

    code, out = _cli(capsys, "organic", "seed-check", "--run", str(run.path))
    assert code == 0 and out["seed_check"]["verdict"] == "keep"
    assert state.load(run).organic["seed_check"] == out["seed_check"]
    assert state.load(run).organic["seed"] == "2026-11-04_kids:t1" and state.load(run).brief is None

    code, out = _cli(capsys, "run", "new", "--playbook", "organic-video", "--name", "old", "--seed", "2026-11-04_kids:t2")
    expired = RunFolder.open(out["path"])
    assert _cli(capsys, "organic", "seed-check", "--run", str(expired.path))[1]["seed_check"]["verdict"] == "unknown"
    trends.save_answer(expired, "get_trend", {"trend_id": "t2"}, {"id": "t2", "kind": "topic_trend",
                                                                   "momentum": "rising", "status": "confirmed"},
                       at=f"{TODAY.isoformat()}T12:00:00+00:00")
    code, out = _cli(capsys, "organic", "seed-check", "--run", str(expired.path))
    assert state.load(expired).created == TODAY.isoformat()
    assert out["seed_check"] == {"verdict": "keep", "valid_until": (TODAY + timedelta(days=14)).isoformat(),
                                 "why": out["seed_check"]["why"]}   # brief.valid_days_default, the fallback

    code, out = _cli(capsys, "run", "new", "--playbook", "organic-video", "--name", "plain")
    assert _cli(capsys, "organic", "seed-check", "--run", out["path"])[0] == 1    # no seed: a bad call

    code, out = _cli(capsys, "run", "new", "--playbook", "creative-brief", "--name", "brief", "--seed", "2026-11-04_kids:t1")
    assert code == 0, out
    brief_run = RunFolder.open(out["path"])
    assert state.load(brief_run).brief == {"seed": "2026-11-04_kids:t1", "seed_paid": "competitor_found"}
    assert state.load(brief_run).organic is None and brief_config.seed_row(brief_run)["seed_id"] == "2026-11-04_kids:t1"
    assert _cli(capsys, "organic", "seed-check", "--run", str(brief_run.path))[0] == 1   # not an organic run
    code, out = _cli(capsys, "run", "new", "--playbook", "trend-research", "--name", "t", "--seed", "2026-11-04_kids:t1")
    assert code == 1 and "--seed" in out["message"]

    with open(ws / seeds.FILE, "a", encoding="utf-8") as fh:          # a refusal names the run being started
        fh.write('{"seed_id": "2026-11-04_kids:t9", broken\n')
    code, out = _cli(capsys, "run", "new", "--playbook", "organic-video", "--name", "t9", "--seed", "2026-11-04_kids:t9")
    assert code == 1 and "start the organic video run without --seed" in out["message"]
    assert "the brief" not in out["message"]
    code, out = _cli(capsys, "run", "new", "--playbook", "creative-brief", "--name", "t9", "--seed", "2026-11-04_kids:t9")
    assert code == 1 and "start the brief without --seed" in out["message"]
    monkeypatch.setattr(brief_config, "SEED_KINDS", ("hook_trend",))   # t1 is a topic_trend
    with pytest.raises(ValueError, match="an organic video builds on a hook_trend only"):
        brief_config.find_seed(ws, "2026-11-04_kids:t1", playbook=ORGANIC_VIDEO)

