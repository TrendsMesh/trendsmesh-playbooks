"""Organic AI video's proposals (C2) and week (I2) check-ins as stages of the shared run page (issue #60): built
from made-up run files, the answer saved there read back by `tm page decision --record` and written as the
decisions files `tm organic start` and the week's production read. No private data."""

import json
import re
from datetime import date

import pytest

from tm import checkins, flow, manifest, organic_proposals, organic_week, page, run_page, state, stepchecks
from tm.cli import main
from tm.organic_pages import proposals as proposals_page, week as week_page
from tm.playbooks import ORGANIC_VIDEO
from tm.run_page import organic_plan
from tm.runfolder import RunFolder
from tm.stops import Stop

from test_run_page import _publish, _read
from test_run_page_organic import _ask, _built, _doc, _html, _paths


@pytest.fixture(autouse=True)
def no_downloads(monkeypatch):
    monkeypatch.setattr(page, "fetch_image", lambda url, dest, timeout=30: False)


def _to(run, checkin):
    """Walk the flow (every step check passing) up to `checkin`'s ask; a check-in asked before its step (reuse_profile
    before A1) is decided once the step before it is done."""
    real = stepchecks.run
    stepchecks.run = lambda name, folder: None
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    try:
        for _ in range(80):
            nxt = flow.next(run)
            if nxt.checkin and checkin in nxt.checkin.ids:
                return
            if nxt.checkin:
                for cid in nxt.checkin.ids:
                    try:
                        flow.decide(run, cid, cat.checkins[cid].choices[0], by="user", note=None)
                    except ValueError:
                        flow.complete(run, nxt.step)
                        flow.decide(run, cid, cat.checkins[cid].choices[0], by="user", note=None)
            elif nxt.action == "work":
                flow.complete(run, nxt.step)
            else:
                raise AssertionError(nxt)
    finally:
        stepchecks.run = real
    raise AssertionError("never reached " + checkin)


def _run(tmp_path, output, lang=None):
    run = RunFolder.create(tmp_path / "ws", "zq", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.level, s.outputs = "every_step", [output]
    state.save(run, s)
    if lang:
        (run.path / "config.yaml").write_text(f"languages:\n  working: {lang}\n  market: {lang}\n", encoding="utf-8")
    return run


# --- the proposals (C2) ---------------------------------------------------------------------------------

def _proposals(lang="en"):
    def one(pid, risk, trend, **plugin):
        return {"id": pid, "channel": "c1", "video_type": "Explainer", "title": f"Made-up idea {pid}",
                "approach": "Inspire", "risk": {"level": risk, "items": ["a made-up risk"]},
                "product": {"level": "hero", "note": "pq"}, "cost": {"low": 1.0, "high": 2.5, "note": "cq"},
                "length": "15 s", "why": "Made-up why", "beats": ["Beat one", "Beat two"],
                "recipe": {"production": "prq", "voice": "vq", "music": "mq", "text": "tq"},
                "taste": ["Which colour?"], "facts": "fq", "trends": [{"id": trend, "role": "roq", "pick": [0]}],
                **({"plugin": plugin} if plugin else {})}
    return {"lang": lang, "title": "Made-up ideas", "date": "2026-11-11", "store": {"name": "Zorbo", "note": "nq"},
            "already_made": ["aq"], "data_note": "dq", "run": "runs/x/zq", "default_output": "video",
            "channels": [{"id": "c1", "name": "Zorbo", "niche": "kq"}],
            "proposals": [one("m1", "low", "t1", aesthetic="warm 1990s camcorder"), one("m2", "high", "t2")]}


def _trends(run, data):
    card = {"kind": "hook_trend", "name": "A made-up trend", "reach": {"creators": 12, "videos": 3400, "views": 5600000},
            "status": "confirmed"}
    video = {"url": "https://example.com/v", "creator": "someone", "views": 1200, "hook_text": "made-up hook",
             "platform": "tiktok", "asset_id": "a1", "thumbnail_url": "https://example.com/t.jpg"}
    return {t["id"]: (card, [video]) for p in data["proposals"] for t in p["trends"]}


def _checked(run, name, data):
    path = run.path / "03_wip" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    stepchecks.mark(run, name.split("_v")[0], path)
    return path


@pytest.fixture
def ideas(tmp_path, monkeypatch):
    """An idea run at Check every step at its proposals check-in, the proposals checked."""
    monkeypatch.setattr(proposals_page, "_trends", _trends)
    run = _run(tmp_path, "proposals")
    _checked(run, "proposals_v01.json", _proposals())
    _to(run, "proposals")
    return run


def test_the_proposals_check_in_is_a_stage_of_the_run_page(ideas):
    built = run_page.build(ideas, _ask(ideas, "proposals"))
    html = _html(ideas, built)
    assert built["open"] == ["proposals"] and 'class="top"' in html
    now = html.split('<section class="decision"')[0]
    assert "Made-up idea m1" in now and "Made-up idea m2" in now and "Beat two" in now and "A made-up trend" in now
    assert "warm 1990s camcorder" in now and "Which colour?" in now and "Produce all" in now
    assert {"decision", "level", "output", "platforms", "answers", "notes", "looks"} <= _paths(html)
    offer = _built(ideas, built)["offer"]["proposals"]
    assert offer["decision"] == {"type": "each", "keys": ["m1", "m2"], "values": ["produce", "later", "skip"]}
    assert offer["level"]["defaults"] == {"m1": "every_step", "m2": "every_step"}
    assert offer["output"]["values"] == ["video", "script"] and "m1~tiktok" in offer["platforms"]["keys"]
    assert offer["answers"] == {"type": "notes", "keys": ["m1~0", "m2~0"]} and offer["looks"]["keys"] == ["m1"]


def test_the_build_is_the_proposals_pages_build_for_its_step_check(ideas):
    built = run_page.build(ideas, _ask(ideas, "proposals"))
    rows = [r for r in manifest.rows(ideas) if r["source"] == proposals_page.SOURCE]
    assert [r["file"] for r in rows] == [built["folder"]] and rows[0]["parent"] == "03_wip/proposals_v01.json"
    assert proposals_page.built_gap(ideas) is None
    assert proposals_page.decided_page(ideas, built["folder"])["proposals"] == "03_wip/proposals_v01.json"


def test_a_local_proposals_page_has_no_inputs(ideas):
    html = _html(ideas, run_page.build(ideas, _ask(ideas, "proposals"), local=True))
    assert "Made-up idea m1" in html and 'data-detail="' not in html and 'class="ovp-all' not in html


def _answer(run, checkin, ask, choice, **detail):
    _publish(run)
    _read(run, _doc(checkin, ask, choice, **detail))


def test_the_ideas_picked_on_the_page_are_the_decisions_file_tm_organic_start_reads(ideas, capsys):
    run_page.build(ideas, _ask(ideas, "proposals"))
    _answer(ideas, "proposals", "proposals_v01", "accept",
            decision={"m1": "produce", "m2": "skip"}, level={"m1": "big_calls"}, output={"m1": "script"},
            platforms={"m1~tiktok": True, "m1~instagram": False, "m1~youtube": True, "m1~facebook": False},
            answers={"m1~0": "teal"}, notes={"m1": "a golden retriever, please"}, looks={"m1": "clean studio"})
    page.await_(ideas, run_page.PAGE, "1700000001-abcd")
    assert main(["page", "decision", "proposals", "--run", str(ideas.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["files"]["decisions"] == "03_wip/decisions_proposals_v01.json" and "tm organic start" in out["message"]
    note = out["recorded_note"]
    assert "M1 Made-up idea m1: Produce" in note and "a golden retriever, please" in note and "Skip" in note
    body = json.loads((ideas.path / out["files"]["decisions"]).read_text(encoding="utf-8"))
    assert body["source"] == "page" and body["carried"] == [] and body["folder"].startswith("04_final/run_page_v")
    assert body["proposals"] == "03_wip/proposals_v01.json" and body["from"].startswith("03_wip/")
    m1 = body["decisions"]["m1"]
    assert (m1["decision"], m1["level"], m1["output"], m1["platforms"]) == ("produce", "big_calls", "script",
                                                                             ["tiktok", "youtube"])
    assert (m1["answers"], m1["note"], m1["aesthetic"]) == ({"0": "teal"}, "a golden retriever, please", "clean studio")
    assert body["decisions"]["m2"]["decision"] == "skip" and body["decisions"]["m2"]["aesthetic"] is None
    rel, rows, _ = organic_proposals._decisions_file(ideas)                  # C3 reads it as the page's file
    assert rel == out["files"]["decisions"] and rows["m1"]["decision"] == "produce"
    assert page.awaiting(ideas, run_page.PAGE) is None
    last = state.load(ideas).decisions[-1]
    assert (last["checkin"], last["choice"], last["by"]) == ("proposals", "accept", "user")


def test_an_untouched_idea_takes_what_the_page_ticked_in_advance(ideas):
    run_page.build(ideas, _ask(ideas, "proposals"))
    _answer(ideas, "proposals", "proposals_v01", "accept", decision={"m1": "produce"})
    got = run_page.record(ideas, "proposals")
    m1 = json.loads((ideas.path / got["files"]["decisions"]).read_text(encoding="utf-8"))["decisions"]["m1"]
    assert (m1["level"], m1["output"], m1["aesthetic"]) == ("every_step", "video", "warm 1990s camcorder")


def test_nothing_decided_on_the_page_is_refused_before_anything_is_recorded(ideas):
    run_page.build(ideas, _ask(ideas, "proposals"))
    _answer(ideas, "proposals", "proposals_v01", "accept", notes={"m1": "hm"})
    with pytest.raises(Stop, match="No idea is marked"):
        run_page.record(ideas, "proposals")
    assert all(d["checkin"] != "proposals" for d in state.load(ideas).decisions)
    assert not list((ideas.path / "03_wip").glob("decisions_proposals_v*.json"))


def test_the_settled_proposals_stage_shows_what_was_decided_read_only(ideas):
    run_page.build(ideas, _ask(ideas, "proposals"))
    _answer(ideas, "proposals", "proposals_v01", "accept", decision={"m1": "produce", "m2": "later"})
    run_page.record(ideas, "proposals")
    html = _html(ideas, run_page.build(ideas))
    settled = html.split('<section class="settled">')[1]
    assert "Made-up idea m1" in settled and "Produce" in settled and "Maybe later" in settled
    assert 'data-detail="' not in html and "decisions_proposals_v01.json" in settled


def test_a_polish_run_asks_the_proposals_in_polish(tmp_path, monkeypatch):
    monkeypatch.setattr(proposals_page, "_trends", _trends)
    run = _run(tmp_path, "proposals", lang="pl")
    _checked(run, "proposals_v01.json", _proposals("pl"))
    _to(run, "proposals")
    html = _html(run, run_page.build(run, _ask(run, "proposals")))
    assert 'lang="pl"' in html and "Produkuj" in html and "Może później" in html and "Produce all" not in html


# --- the week (I2) --------------------------------------------------------------------------------------

def _idea(i, day, cost=2.0, output="video"):
    return {"id": i, "day": day, "title": f"Made-up {i}", "format": "Explainer", "why": "Made-up why",
            "trend": "A made-up trend", "evidence": "https://example.com/e", "cost_video": cost, "cost_script": 0,
            "production": "AI footage", "risk": "low", "time": "18:00", "date": "2026-11-16", "output": output,
            "plugin": {"trends": [], "production": "ai_footage", "approach": "Inspire", "product_level": "hero",
                       "series": None, "flexible": False}}


def _week(lang="en", budget=5.0):
    return {"lang": lang, "week": "2026-11-16/2026-11-22", "title": "A made-up week", "channel": "Zorbo",
            "budget": budget, "rhythm": "two a week", "platforms": ["tiktok", "youtube"], "note": "nq",
            "run": "runs/x/wq", "slots": [_idea("w1", "mon"), _idea("w2", "wed")],
            "reserves": [{**_idea("r1", "sun", cost=4.0), "day": None}]}


@pytest.fixture
def week_run(tmp_path):
    """A week run at Check every step at its week check-in, the week checked."""
    run = _run(tmp_path, "weekly_plan")
    _checked(run, "week_v01.json", _week())
    _to(run, "week")
    return run


def test_the_week_check_in_is_a_stage_with_the_calendar_and_the_budget_bar(week_run):
    built = run_page.build(week_run, _ask(week_run, "week"))
    html = _html(week_run, built)
    now = html.split('<section class="decision"')[0]
    assert "Made-up w1" in now and "Made-up r1" in now and "Monday" in now and "Wednesday" in now
    assert 'class="ovw-meter"' in now and "The plan is over budget" in now and "2 videos this week" in now
    assert {"output", "decision", "idea", "notes"} <= _paths(html)
    assert now.count("<select") == 2 and now.count('value="r1"') == 2
    offer = _built(week_run, built)["offer"]["week"]
    assert offer["idea"] == {"type": "each", "keys": ["mon", "wed"], "values": ["w1", "w2", "r1"],
                             "defaults": {"mon": "w1", "wed": "w2"}}
    assert offer["decision"]["defaults"] == {"mon": "ok", "wed": "ok"}
    assert offer["output"]["defaults"] == {"mon": "video", "wed": "video"}
    assert week_page.built_gap(week_run) is None


def test_the_week_approved_on_the_page_is_the_decisions_file_and_the_yes(week_run, capsys):
    run_page.build(week_run, _ask(week_run, "week"))
    _answer(week_run, "week", "week_v01", "approve", idea={"wed": "r1"}, output={"wed": "script"},
            decision={"mon": "ok", "wed": "ok"}, notes={"mon": "shorter, please"})
    assert main(["page", "decision", "week", "--run", str(week_run.path), "--record", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["files"]["decisions"] == "03_wip/decisions_week_v01.json" and "tm organic start" in out["message"]
    assert "Monday" in out["recorded_note"] and "shorter, please" in out["recorded_note"]
    body = json.loads((week_run.path / out["files"]["decisions"]).read_text(encoding="utf-8"))
    assert body["source"] == "page" and body["carried"] == [] and body["approved"] is True and body["total"] == 2.0
    assert body["decisions"]["wed"]["idea"] == "r1" and body["decisions"]["wed"]["output"] == "script"
    assert body["decisions"]["mon"]["note"] == "shorter, please"
    assert organic_week.budget_gap(week_run) is None
    yes = organic_week.approval(week_run)
    assert yes and yes["covers"]["decisions"] == out["files"]["decisions"]


def test_a_week_over_its_budget_is_refused_before_anything_is_recorded(week_run):
    run_page.build(week_run, _ask(week_run, "week"))
    _answer(week_run, "week", "week_v01", "approve", idea={"wed": "r1"})        # 2 + 4 over 5
    with pytest.raises(Stop, match="over its budget"):
        run_page.record(week_run, "week")
    assert organic_week.approval(week_run) is None
    assert not list((week_run.path / "03_wip").glob("decisions_week_v*.json"))


def test_one_idea_on_two_days_is_refused(week_run):
    run_page.build(week_run, _ask(week_run, "week"))
    _answer(week_run, "week", "week_v01", "approve", idea={"wed": "w1"})
    with pytest.raises(Stop, match="two days"):
        run_page.record(week_run, "week")
    assert organic_week.approval(week_run) is None


def test_the_settled_week_shows_each_day_read_only(week_run):
    run_page.build(week_run, _ask(week_run, "week"))
    _answer(week_run, "week", "week_v01", "approve", decision={"wed": "skip"})
    run_page.record(week_run, "week")
    html = _html(week_run, run_page.build(week_run))
    settled = html.split('<section class="settled">')[1]
    assert "Made-up w1" in settled and "Skip" in settled and "$2.00" in settled
    assert 'data-detail="' not in html and "<select" not in html


def test_every_word_the_plan_stages_read_is_in_both_tables():
    from tm import i18n
    en, pl = i18n.table("en"), i18n.table("pl")
    for key in organic_plan.keys():          # a count's key has its forms (one / other; Polish one / few / many)
        assert (key in en or f"{key}.other" in en) and (key in pl or f"{key}.many" in pl), key
    src = (organic_plan.__file__)
    literal = set(re.findall(r'"(organic\.[a-z_]+\.[a-z_]+)"', open(src, encoding="utf-8").read()))
    assert literal <= organic_plan.keys() | {k for k in literal if k.endswith(".")}


# --- an answer in chat, after a run page build -------------------------------------------------------------

def test_ideas_answered_in_chat_are_read_against_the_run_pages_build(ideas, capsys):
    built = run_page.build(ideas, _ask(ideas, "proposals"))
    text = ideas.path / "03_wip" / "decisions_text_v01.txt"
    text.write_text("M1 Made-up idea m1: produce, Check every step; output: script; platforms: tiktok\n", encoding="utf-8")
    assert main(["organic", "decisions", "--run", str(ideas.path), "--page", "proposals", "--text", str(text),
                 "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["folder"] == built["folder"] and out["decisions"]["m1"]["output"] == "script"


def test_a_week_answered_in_chat_is_read_against_the_run_pages_build(week_run, capsys):
    built = run_page.build(week_run, _ask(week_run, "week"))
    text = week_run.path / "03_wip" / "decisions_text_v01.txt"
    text.write_text("mon: ok; output: script\nwed: skip\napproved: yes\n", encoding="utf-8")
    assert main(["organic", "decisions", "--run", str(week_run.path), "--page", "week", "--text", str(text),
                 "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["folder"] == built["folder"] and out["total"] == 0.0
    assert organic_week.budget_gap(week_run) is None
