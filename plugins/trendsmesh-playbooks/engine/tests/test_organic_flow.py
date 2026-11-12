"""Organic AI video (playbook 03) in the step engine: its steps, its check-ins on the three levels,
and the run kinds (an idea run, a production run, a script run and a week run)."""

import json
import re
from datetime import date

import pytest
import yaml

from exampleedu import PROFILE as EXAMPLEEDU
from tm import (brand, checkins, config, flow, kit, organic, organic_config, organic_final, organic_gates,
                organic_pack, organic_proposals, organic_qa, organic_research, organic_week, organic_week_delivery,
                paths, playbooks, state, stops)
from tm.cli import main
from tm.organic_pages import proposals as proposals_page, script as script_page, week as week_page
from tm.flow import complete, decide, set_level
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

ALL = ["proposals", "script_to_film", "organic_video", "weekly_plan"]
IDEA = ["proposals", "weekly_plan"]
PROD = ["script_to_film", "organic_video"]
TABLE = {  # id: (title, outputs, before, checkins, skip_when, spends, budget), the plan's Task 1
    "A0": ("Stack check, intake and run folder", IDEA, [], [], {}, False, None),
    "A1": ("Channel profile", IDEA, ["reuse_profile"], ["profile"], {"reuse_profile": "reuse"},
           False, None),
    "B1": ("Trend search in the bubble", IDEA, [], [], {}, False, None),
    "B2": ("Shortlist", IDEA, [], [], {}, False, None),
    "B3": ("Cards and evidence", IDEA, [], [], {}, False, None),
    "C1": ("Proposals", ["proposals"], [], [], {}, False, None),
    "C2": ("Proposals page", ["proposals"], [], ["proposals"], {}, False, None),
    "C3": ("Start the picked videos", ["proposals"], [], [], {}, False, None),
    "I2": ("Week plan and page", ["weekly_plan"], [], ["week"], {}, False, None),
    "I3": ("Produce the week", ["weekly_plan"], [], [], {}, False, None),
    "I4": ("Week delivery and posting plan", ["weekly_plan"], [], [], {}, False, None),
    "I5": ("Weekly schedule", ["weekly_plan"], ["schedule"], [], {"schedule": "by_hand"}, False, None),
    "D1": ("Recipe: production type and product", PROD, [], [], {}, False, None),
    "D2": ("Taste picks", ["organic_video"], [], ["taste"], {}, False, None),
    "E1": ("Model and speech route", ["organic_video"], [], [], {}, False, None),
    "E2": ("Generation pack and cost", ["organic_video"], [], ["pack"], {}, False, None),
    "E3": ("Script page", ["script_to_film"], [], ["script"], {}, False, None),
    "F1": ("First stage: images, character or storyboard", ["organic_video"], [], ["images"],
           {"pack": "reject"},
           True, "ai_usd"),
    "F2": ("Second stage: takes, animation or render", ["organic_video"], [], ["video"],
           {"pack": "reject"},
           True, "ai_usd"),
    "G1": ("Edit, mix, captions", ["organic_video"], [], [], {"pack": "reject"}, False, None),
    "G2": ("Cover, upload copy and posting kit", ["organic_video"], [], [], {"pack": "reject"}, False, None),
    "G4": ("Final page", ["organic_video"], [], ["final_edit"], {"pack": "reject"}, False, None),
    "H1": ("Publish (the user posts)", PROD, [], [], {}, False, None),
}
OWN = {"every_step": "own", "big_calls": "own", "hands_off": "own"}
LEVELS = {  # check-in: (route, card, choices), the plan's "Levels" table
    "reuse_profile": ({"every_step": "own", "big_calls": "own", "hands_off": "rule"}, None,
                      ("reuse", "new")),
    "profile": (OWN, None, ("accept",)),
    "proposals": (OWN, None, ("accept",)),
    "week": (OWN, None, ("approve",)),
    "schedule": ({"every_step": "own", "big_calls": "own", "hands_off": "rule"}, None,
                 ("schedule", "by_hand")),
    "taste": ({"every_step": "own", "big_calls": "card", "hands_off": "rule"}, "plan", ("accept",)),
    "pack": ({"every_step": "own", "big_calls": "card", "hands_off": "own"}, "plan",
             ("approve", "reject")),
    "script": ({"every_step": "own", "big_calls": "own", "hands_off": "rule"}, None, ("accept",)),
    "images": ({"every_step": "own", "big_calls": "rule", "hands_off": "rule"}, None,
               ("accept", "redo", "drop")),
    "video": ({"every_step": "own", "big_calls": "rule", "hands_off": "rule"}, None,
              ("accept", "redo", "drop", "fails_qa")),
    "final_edit": ({"every_step": "own", "big_calls": "own", "hands_off": "rule"}, None,
                   ("accept", "redo", "drop")),
}
FAILS_QA = ("The take did not pass QA, and a video is never regenerated automatically.",
            "Look at the QA findings and choose: keep it as is, speed it up in the edit, redo it "
            "with a note (its cost is shown), or drop it.")


REQUIRES = {"A0": ("organic_intake_written", "stack_recorded"), "A1": ("profile_written",),
            "B1": ("profile_written",),   # added by Tasks 3 and 4 (B1: a reused profile, review M3)
            "B2": ("shortlist_written",), "B3": ("evidence_saved",),   # Task 5
            "C1": ("proposals_checked",), "C2": ("proposals_page_built",),   # Tasks 6 and 7
            "C3": ("videos_started",),
            "E3": ("script_checked", "script_page_built"),   # Task 9
            "D1": ("credits_recorded", "recipe_written"), "E2": ("pack_checked",),   # Tasks 18 and 12
            "F1": ("images_picked",), "F2": ("takes_checked",),   # Task 15
            "G1": ("final_checked", "sections_covered", "text_followed"), "G2": ("kit_checked",),   # Tasks 16, 20, issue 89
            "G4": ("final_page_built",),   # Task 17
            "I2": ("week_checked", "week_page_built"), "I3": ("slots_started",), "I4": ("week_delivered",)}   # Task 21


@pytest.fixture(autouse=True)
def research_saved(monkeypatch):
    """The walks here are about the steps and check-ins: B2's and B3's research checks, C1's and C3's
    proposals checks, C2's page check, E3's script checks, D1's and E2's pack checks, F1's and F2's picks, G1's
    and G2's final and kit checks, G4's delivery page check and the week's checks (I2 to I4, the week's approval)
    pass (test_organic_research, test_organic_proposals, test_organic_pages, test_organic_script, test_organic_pack,
    test_organic_qa, test_organic_final, test_organic_gates and test_organic_week prove them on the ExampleEdu
    walkthrough and the pet store)."""
    monkeypatch.setattr(organic_research, "shortlist_gap", lambda run: None)
    monkeypatch.setattr(organic_research, "evidence_gap", lambda run: None)
    monkeypatch.setattr(organic_proposals, "checked_gap", lambda run: None)
    monkeypatch.setattr(organic_proposals, "started_gap", lambda run: None)
    monkeypatch.setattr(proposals_page, "built_gap", lambda run: None)
    monkeypatch.setattr(script_page, "checked_gap", lambda run: None)
    monkeypatch.setattr(script_page, "built_gap", lambda run: None)
    monkeypatch.setattr(organic_pack, "recipe_gap", lambda run: None)
    monkeypatch.setattr(organic_pack, "pack_gap", lambda run: None)
    monkeypatch.setattr(organic_qa, "images_gap", lambda run: None)
    monkeypatch.setattr(organic_qa, "takes_gap", lambda run: None)
    monkeypatch.setattr(organic_final, "final_gap", lambda run: None)
    monkeypatch.setattr(organic_final, "sections_gap", lambda run: None)
    monkeypatch.setattr(kit, "kit_gap", lambda run: None)
    monkeypatch.setattr(organic_gates, "delivery_gap", lambda run: None)
    for name in ("checked_gap", "budget_gap", "started_gap"):   # the week's (test_organic_week)
        monkeypatch.setattr(organic_week, name, lambda run: None)
    monkeypatch.setattr(organic_week_delivery, "delivered_gap", lambda run: None)
    monkeypatch.setattr(organic_week, "covered", lambda run: {"decisions": None})   # what the week's yes binds to
    monkeypatch.setattr(week_page, "built_gap", lambda run: None)


def _organic(tmp_path, level, outputs, confirmed=True):
    """A run whose A0, A1 and B1 checks pass: its config names the ExampleEdu channel, saved in the
    library (confirmed by the user earlier, unless `confirmed` is False)."""
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "exampleedu", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": ["exampleedu"]})
    saved = brand.save(tmp_path / "ws", EXAMPLEEDU, run=None)
    if confirmed:   # what an earlier run's `tm brand save --confirmed` leaves in the library
        saved.write_text(json.dumps({**EXAMPLEEDU, "confirmed": "2026-10-01"}), encoding="utf-8")
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    set_level(run, level)
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="ok")
    return run


def _walk(run, choices=None, until=None):
    """Do each step's work and answer each check-in (by rule when the engine says auto, a card
    member by member) until the run is done or stops, or `until` is the step to work on next.
    Returns the check-ins seen as (step, action, ids, card), the timeline of steps worked and
    check-ins decided, and the last next()."""
    choices = choices or {}
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    seen, timeline = [], []
    for _ in range(100):
        nxt = flow.next(run)
        if nxt.action in ("done", "stop") or (nxt.action == "work" and nxt.step == until):
            return seen, timeline, nxt
        if nxt.action == "work" and FIRST in (nxt.message or ""):   # F1, F2: the check-in, then `tm done`
            action = "auto" if "--by rule" in nxt.message else "ask"
            seen.append((nxt.step, action, nxt.checkin.ids, nxt.checkin.card))
            by, note = ("rule", "test data") if action == "auto" else ("user", None)
            for cid in nxt.checkin.ids:
                decide(run, cid, choices.get(cid, cat.checkins[cid].choices[0]), by=by, note=note)
                timeline.append(cid)
            continue
        if nxt.action == "work":
            timeline.append(nxt.step)
            complete(run, nxt.step)
            continue
        assert nxt.action in ("ask", "auto"), nxt
        seen.append((nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card))
        by, note = ("rule", "test data") if nxt.action == "auto" else ("user", None)
        for cid in nxt.checkin.ids:
            decide(run, cid, choices.get(cid, cat.checkins[cid].choices[0]), by=by, note=note)
            timeline.append(cid)
    raise AssertionError("the run never ended")


FIRST = "comes before the step is closed"


def _worked(timeline):
    return [x for x in timeline if x in TABLE]


# --- the registry, steps and catalogue --------------------------------------------

def test_organic_video_is_registered():
    pb = playbooks.get("organic-video")
    assert (pb.id, pb.name, pb.skill, pb.guess, pb.budgets) == (
        ORGANIC_VIDEO, "Organic AI video", "organic-video", False, ("ai_usd", "voice_credits"))
    assert ORGANIC_VIDEO == "03-organic-ai-video"
    assert pb.data_dir == paths.bundled_data() / "organic-video"
    assert playbooks.get("trend-research").budgets == ()   # no budgets row: none


def test_organic_steps_match_the_plan():
    every = flow.steps(ORGANIC_VIDEO)
    assert flow.output_ids(ORGANIC_VIDEO) == ALL
    assert [st.id for st in every] == list(TABLE)
    assert flow.flows(ORGANIC_VIDEO) == set()
    for st in every:
        title, outputs, before, after, skip_when, spends, budget = TABLE[st.id]
        assert (st.title, list(st.outputs), list(st.before), list(st.checkins), dict(st.skip_when),
                st.spends, st.budget) == (title, outputs, before, after, skip_when, spends, budget), st.id
        assert st.ref == f"skills/organic-video/references/flow.md#{st.id.lower()}"
        assert st.requires == REQUIRES.get(st.id, ()), st.id   # each later task adds its own


def test_organic_catalogue_routes_the_levels_table():
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    assert cat.levels == {"every_step": "Check every step", "big_calls": "Just the big calls",
                          "hands_off": "Hands-off"}
    assert list(cat.checkins) == list(LEVELS)
    assert {c.id: (c.name, c.ask) for c in cat.cards.values()} == {
        "plan": ("Approve the plan for this video", "last")}
    for cid, (route, card, choices) in LEVELS.items():
        c = cat.checkins[cid]
        assert (c.route, c.card, c.choices) == (route, card, choices), cid
        assert (c.money, c.yes_for) == ((True, ("ai_usd", "voice_credits")) if cid == "pack"
                                        else (False, ())), cid
    assert cat.checkins["pack"].on_choice == {"reject": {
        "skips": "Nothing was generated or paid. The idea can still become a script to film."}}
    assert cat.checkins["video"].on_choice == {
        "redo": {"back_to": "F2"}, "fails_qa": {"stop": {"what": FAILS_QA[0], "todo": FAILS_QA[1]}}}
    assert cat.checkins["images"].on_choice == {"redo": {"back_to": "F1"}}   # a redo is asked again (issue #90)
    assert cat.checkins["final_edit"].on_choice == {"redo": {"back_to": "G1"}}
    assert [st.id for st in flow.steps(ORGANIC_VIDEO) if st.checkin_first] == ["F1", "F2"]
    # FLOWS J's A–Z rules, verbatim
    assert "rubric pick (images may be redone once)" in cat.checkins["images"].rule
    assert ("rubric pick; a failed take goes to the user (no automatic video redo)"
            in cat.checkins["video"].rule)
    assert "budget guard; cost confirmed once while testing" in cat.checkins["pack"].rule
    assert "profile defaults or agent pick (logged)" in cat.checkins["taste"].rule
    assert "delivered on the delivery page with every step" in cat.checkins["final_edit"].rule
    # the schedule is trend research's GS, with the weekly pack's sentence
    gs = checkins.load(playbook=playbooks.TREND_RESEARCH).checkins["GS"]
    sched = cat.checkins["schedule"]
    assert (sched.route, sched.rule, sched.choices) == (gs.route, gs.rule, gs.choices)
    assert "plan my week of videos" in sched.on_choice["by_hand"]["skips"]


# --- the levels: a production run (AI video) ------------------------------------------

def test_every_step_asks_each_checkin_in_order(tmp_path):
    run = _organic(tmp_path, "every_step", ["organic_video"])
    seen, timeline, end = _walk(run)
    assert timeline == ["D1", "D2", "taste", "E1", "E2", "pack", "images", "F1", "video", "F2",
                        "G1", "G2", "G4", "final_edit", "H1"]
    assert all(action == "ask" and card is None for _, action, _, card in seen)
    assert end.action == "done"
    assert all(d["by"] == "user" for d in state.load(run).decisions)


def test_big_calls_asks_plan_card_after_e2_and_final_edit_only(tmp_path):
    run = _organic(tmp_path, "big_calls", ["organic_video"])
    seen, timeline, end = _walk(run)
    assert seen == [("E2", "ask", ["taste", "pack"], "plan"), ("F1", "auto", ["images"], None),
                    ("F2", "auto", ["video"], None), ("G4", "ask", ["final_edit"], None)]
    assert _worked(timeline) == ["D1", "D2", "E1", "E2", "F1", "F2", "G1", "G2", "G4", "H1"]
    assert end.action == "done"
    by = {d["checkin"]: d["by"] for d in state.load(run).decisions}
    assert by == {"taste": "user", "pack": "user", "images": "rule", "video": "rule",
                  "final_edit": "user"}


def test_big_calls_plan_card_is_named_and_waits_for_e2(tmp_path):
    run = _organic(tmp_path, "big_calls", ["organic_video"])
    _, _, nxt = _walk(run, until="E1")
    assert nxt.checkin is None   # D2's taste waits for the plan card
    complete(run, "E1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.name) == (
        "E2", "work", ["taste", "pack"], "Approve the plan for this video")
    complete(run, "E2")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.card) == ("E2", "ask", "plan")


def _commands(message):
    """The `tm decide …` commands a message names, in order, as CLI arguments."""
    return [c.split()[1:] for c in re.findall(r"`(tm decide [^`<\[]+)`", message)]


@pytest.mark.parametrize("pack", ["approve", "reject"])
def test_big_calls_plan_card_is_decided_by_its_own_message(tmp_path, capsys, pack):
    """The plan card's members share no answer, so the message names each member's own command
    in order; following it, through the CLI, decides the card and the run goes on."""
    run = _organic(tmp_path, "big_calls", ["organic_video"])
    _walk(run, until="E2")
    complete(run, "E2")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.card) == ("E2", "ask", "plan")
    assert "`tm decide plan" not in nxt.message
    cmds = _commands(nxt.message)
    assert cmds == [["decide", "taste", "accept"], ["decide", "pack", "approve"],
                    ["decide", "pack", "reject"]], nxt.message
    for cid in ("taste", "pack"):   # one command per member, the one with the user's answer
        cmd = next(c for c in cmds if c[1] == cid and (cid != "pack" or c[2] == pack))
        assert main([*cmd, "--run", str(run.path)]) == 0
    capsys.readouterr()
    nxt = flow.next(run)
    if pack == "approve":
        assert (nxt.step, nxt.action) == ("F1", "work")
    else:
        assert (nxt.step, nxt.action) == ("H1", "work")


def test_deciding_the_plan_card_as_one_names_the_member_commands(tmp_path, capsys):
    run = _organic(tmp_path, "big_calls", ["organic_video"])
    _walk(run, until="E2")
    complete(run, "E2")
    capsys.readouterr()
    assert main(["decide", "plan", "approve", "--run", str(run.path)]) == 1
    err = capsys.readouterr()
    text = err.out + err.err
    assert "`tm decide taste accept`, then `tm decide pack approve`" in text, text
    assert not [d for d in state.load(run).decisions if d["checkin"] in ("taste", "pack")]


def test_a_card_with_a_shared_answer_keeps_its_one_command(tmp_path):
    """Refresh-ad's spending card: every member takes approve, so the card is still one command."""
    view = flow.CheckinView(ids=["G6", "G10"], name="Approve the spending", card="approve_spending",
                            rule="", choices=["approve", "reject"])
    message = flow._item_message(view, "ask", None, checkins.load())
    assert "`tm decide approve_spending <choice> [--note ...]`" in message
    assert "`tm decide G6" not in message


def test_hands_off_asks_only_the_pack(tmp_path):
    run = _organic(tmp_path, "hands_off", ["organic_video"])
    seen, timeline, end = _walk(run)
    assert [ids for _, action, ids, _ in seen if action == "ask"] == [["pack"]]
    assert {ids[0]: action for _, action, ids, _ in seen} == {
        "taste": "auto", "pack": "ask", "images": "auto", "video": "auto", "final_edit": "auto"}
    assert _worked(timeline) == ["D1", "D2", "E1", "E2", "F1", "F2", "G1", "G2", "G4", "H1"]
    assert end.action == "done"


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_video_fails_qa_stops_with_options(tmp_path, level):
    run = _organic(tmp_path, level, ["organic_video"])
    seen, timeline, nxt = _walk(run, {"video": "fails_qa", "pack": "approve"})
    assert timeline[-1] == "video" and _worked(timeline)[-1] == "F1"   # F2 stays open: it closes after the user
    assert (nxt.step, nxt.action) == ("F2", "stop")
    for words in FAILS_QA:
        assert words in nxt.message
    assert "continues from the same place" in nxt.message
    assert state.load(run).status == "stopped"
    with pytest.raises(flow.Held):
        complete(run, "G1")
    # the user picks one of the options; the run goes on from the same place
    decide(run, "video", "accept", by="user", note="keep it, speed it up in the edit", change=True)
    seen, timeline, end = _walk(run)
    assert _worked(timeline) == ["F2", "G1", "G2", "G4", "H1"] and end.action == "done"
    assert state.load(run).status == "done"


# --- issue #90: F1 and F2 close after their check-in; a redo goes back -------------------------

@pytest.mark.parametrize("level, by", [("every_step", "user"), ("big_calls", "rule"), ("hands_off", "rule")])
def test_f1_and_f2_are_closed_after_their_checkin(tmp_path, level, by):
    run = _organic(tmp_path, level, ["organic_video"])
    _walk(run, until="F1")
    for step, cid in (("F1", "images"), ("F2", "video")):
        nxt = flow.next(run)
        assert (nxt.step, nxt.action, nxt.checkin.ids) == (step, "work", [cid])
        assert FIRST in nxt.message and f"`tm done {step}`" in nxt.message
        assert ("--by rule" in nxt.message) == (by == "rule")
        with pytest.raises(ValueError, match=f"closed after its check-in .*{cid}"):
            complete(run, step)
        decide(run, cid, "accept", by=by, note="test data")
        nxt = flow.next(run)
        assert (nxt.step, nxt.action) == (step, "work") and FIRST not in nxt.message
        complete(run, step)
    assert flow.next(run).step == "G1"


def test_an_images_redo_keeps_f1_open_and_asks_again(tmp_path):
    run = _organic(tmp_path, "every_step", ["organic_video"])
    _walk(run, until="F1")
    decide(run, "images", "redo", by="user", note="the dog looks wrong")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("F1", "work", ["images"])
    assert "was answered redo" in nxt.message
    with pytest.raises(ValueError, match="closed after its check-in"):
        complete(run, "F1")
    decide(run, "images", "accept", by="user", note="now it is right")   # asked again: no --change needed
    complete(run, "F1")
    assert flow.next(run).step == "F2"


@pytest.mark.parametrize("level", ["every_step", "big_calls"])
def test_final_edit_redo_goes_back_to_the_edit(tmp_path, level):
    """`final_edit redo` takes the run back to G1: the final, the cover, the kit and the delivery page go through
    their steps again, and the final edit is asked again."""
    run = _organic(tmp_path, level, ["organic_video"])
    _walk(run, until="H1")
    assert [d["checkin"] for d in state.load(run).decisions][-1] == "final_edit"
    decide(run, "final_edit", "redo", by="user", note="shorter captions", change=True)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("G1", "work")
    seen, timeline, end = _walk(run)
    assert timeline == ["G1", "G2", "G4", "final_edit", "H1"] and end.action == "done"
    assert [d["choice"] for d in state.load(run).decisions if d["checkin"] == "final_edit"] == [
        "accept", "redo", "accept"]


def test_a_run_past_f1_with_its_checkin_open_is_still_asked(tmp_path):
    """A run the older engine moved past F1 before its check-in (issue #90) is asked it, as before."""
    run = _organic(tmp_path, "every_step", ["organic_video"])
    _walk(run, until="F1")
    s = state.load(run)
    s.step = "F2"
    state.save(run, s)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("F1", "ask", ["images"])


def test_back_to_names_a_step_at_or_before_its_checkin(tmp_path):
    steps_path, _ = _organic_data(tmp_path)
    for target in ("H1", "Z9"):
        def later(c, target=target):
            c["images"]["on_choice"] = {"redo": {"back_to": target}}
        _, path = _organic_data(tmp_path, later)
        with pytest.raises(ValueError, match="back_to"):
            flow._load_steps(steps_path, path, ("ai_usd", "voice_credits"))


def test_the_final_after_a_final_edit_redo_is_a_new_one(tmp_path, monkeypatch):
    run = _organic(tmp_path, "every_step", ["organic_video"])
    monkeypatch.undo()   # the real G1 check
    monkeypatch.setattr(organic_final, "idea_id", lambda run: "m1")
    final = run.path / "04_final" / "m1_final_v01.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"x")
    s = state.load(run)
    s.decisions.append({"checkin": "final_edit", "choice": "redo", "by": "user", "at": "2099-01-01T00:00:00+00:00"})
    state.save(run, s)
    assert "a new final is made after the user asked to redo the final edit" in organic_final.final_gap(run)


# --- the run kinds ------------------------------------------------------------------

@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_reuse_profile_skips_a1(tmp_path, level):
    run = _organic(tmp_path, level, ["proposals"])
    seen, timeline, end = _walk(run, {"reuse_profile": "reuse"})
    assert "A1" not in timeline and "profile" not in timeline
    assert timeline == ["A0", "reuse_profile", "B1", "B2", "B3", "C1", "C2", "proposals", "C3"]
    action = "auto" if level == "hands_off" else "ask"
    assert seen[0] == ("A1", action, ["reuse_profile"], None)   # asked before A1, which it skips
    assert end.action == "done"


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_reuse_needs_a_confirmed_profile(tmp_path, level):
    """A reuse skips A1, where a profile is drafted and confirmed, so it is refused until the saved
    profile is confirmed by the user; new is then the answer, and A1 drafts it."""
    run = _organic(tmp_path, level, ["proposals"], confirmed=False)
    complete(run, "A0")
    assert flow.next(run).checkin.ids == ["reuse_profile"]   # asked before A1
    by, note = ("rule", "a saved profile") if level == "hands_off" else ("user", None)
    with pytest.raises(ValueError) as caught:
        decide(run, "reuse_profile", "reuse", by=by, note=note)
    assert str(caught.value) == ("reuse_profile (Reuse the saved channel profile) can be reuse once the "
                                 "saved channel profile exampleedu is confirmed by the user; nothing was "
                                 "decided. Choose another answer, or fix that first.")
    assert not [d for d in state.load(run).decisions if d["checkin"] == "reuse_profile"]
    decide(run, "reuse_profile", "new", by=by, note=note)
    assert (flow.next(run).step, flow.next(run).action) == ("A1", "work")


def test_b1_checks_the_reused_profile(tmp_path):
    """B1 requires the profile A1 would have checked: a reused profile gone from the library stops it."""
    run = _organic(tmp_path, "every_step", ["proposals"])
    _, timeline, nxt = _walk(run, {"reuse_profile": "reuse"}, until="B1")
    assert timeline == ["A0", "reuse_profile"] and nxt.step == "B1"
    for f in (tmp_path / "ws" / brand.CHANNEL_DIR / "exampleedu").iterdir():
        f.unlink()
    with pytest.raises(stops.Stop) as caught:
        complete(run, "B1")
    said = str(caught.value).replace("\\", "/")
    assert "B1 (Trend search in the bubble) is done once the channel profile exampleedu is saved" in said


def test_a_choice_cannot_require_an_unknown_check(tmp_path):
    def edit(by_id):
        by_id["reuse_profile"]["on_choice"] = {"reuse": {"requires": ["no_such_check"]}}
    with pytest.raises(ValueError, match="reuse_profile: on_choice 'reuse' requires an unknown check: no_such_check"):
        checkins.load(path=_organic_data(tmp_path, edit)[1])


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_new_profile_walks_a1_and_the_profile_is_always_the_users(tmp_path, level):
    run = _organic(tmp_path, level, ["proposals"])
    seen, timeline, end = _walk(run, {"reuse_profile": "new"})
    assert timeline[:5] == ["A0", "reuse_profile", "A1", "profile", "B1"]
    assert ("A1", "ask", ["profile"], None) in seen and ("C2", "ask", ["proposals"], None) in seen
    assert end.action == "done"


@pytest.mark.parametrize("level,action", [("every_step", "ask"), ("big_calls", "ask"),
                                          ("hands_off", "auto")])
def test_script_run_walks_d1_e3_h1(tmp_path, level, action):
    run = _organic(tmp_path, level, ["script_to_film"])
    seen, timeline, end = _walk(run)
    assert timeline == ["D1", "E3", "script", "H1"]
    assert seen == [("E3", action, ["script"], None)]
    assert end.action == "done"


def test_proposals_run_ends_after_c3(tmp_path):
    run = _organic(tmp_path, "every_step", ["proposals"])
    seen, timeline, end = _walk(run, {"reuse_profile": "new"})
    assert _worked(timeline) == ["A0", "A1", "B1", "B2", "B3", "C1", "C2", "C3"]
    assert seen == [("A1", "ask", ["reuse_profile"], None), ("A1", "ask", ["profile"], None),
                    ("C2", "ask", ["proposals"], None)]
    assert (end.action, end.step) == ("done", "C3")
    assert state.load(run).step == flow.END


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
@pytest.mark.parametrize("schedule,worked", [
    ("schedule", ["A0", "A1", "B1", "B2", "B3", "I2", "I3", "I4", "I5"]),
    ("by_hand", ["A0", "A1", "B1", "B2", "B3", "I2", "I3", "I4"])])
def test_week_run_walks_a0_b_i(tmp_path, level, schedule, worked):
    run = _organic(tmp_path, level, ["weekly_plan"])
    seen, timeline, end = _walk(run, {"reuse_profile": "new", "schedule": schedule})
    assert _worked(timeline) == worked
    by_rule = "auto" if level == "hands_off" else "ask"   # week is the user's at every level
    assert [(ids, action) for _, action, ids, _ in seen] == [
        (["reuse_profile"], by_rule), (["profile"], "ask"), (["week"], "ask"), (["schedule"], by_rule)]
    assert seen[-1][0] == "I5"
    assert end.action == "done"
    if schedule == "by_hand":
        assert "plan my week of videos" in end.message


def test_idea_run_never_reaches_production_steps(tmp_path):
    run = _organic(tmp_path, "every_step", ["proposals"])
    _, timeline, _ = _walk(run)
    assert not {"D1", "E2", "F1", "F2", "G4", "H1", "I2"} & set(timeline)


# --- the money check-in and the registry's budgets ----------------------------------------

def _organic_data(tmp_path, edit_checkin=None):
    folder = paths.bundled_data() / "organic-video"
    data = yaml.safe_load((folder / "checkins.yaml").read_text(encoding="utf-8"))
    if edit_checkin:
        edit_checkin({c["id"]: c for c in data["checkins"]})
    path = tmp_path / f"checkins_{len(list(tmp_path.glob('checkins_*')))}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return folder / "steps.yaml", path


def test_yes_for_needs_money_and_a_known_kind(tmp_path):
    budgets = ("ai_usd", "voice_credits")
    steps_path, path = _organic_data(tmp_path)
    flow._load_steps(steps_path, path, budgets)   # the shipped file loads

    def no_money(c):
        c["pack"]["money"] = False
    _, path = _organic_data(tmp_path, no_money)
    with pytest.raises(ValueError, match="pack") as no:
        checkins.load(path)
    assert "money" in str(no.value) and path.name in str(no.value)

    def not_a_list(c):
        c["pack"]["yes_for"] = "ai_usd"
    _, path = _organic_data(tmp_path, not_a_list)
    with pytest.raises(ValueError, match="yes_for"):
        checkins.load(path)

    for kind in ("bitcoin", "test"):   # not a budget kind at all; a kind this playbook has not
        def unknown(c, kind=kind):
            c["pack"]["yes_for"] = ["ai_usd", kind]
        _, path = _organic_data(tmp_path, unknown)
        checkins.load(path)   # the catalogue alone cannot know the kinds (an import cycle)
        with pytest.raises(ValueError, match="pack") as no:
            flow._load_steps(steps_path, path, budgets)
        assert kind in str(no.value) and "yes_for" in str(no.value)


def _registry(tmp_path, monkeypatch, budgets):
    rows = yaml.safe_load((paths.bundled_data() / "playbooks.yaml").read_text(encoding="utf-8"))
    for row in rows["playbooks"]:
        if row["id"] == ORGANIC_VIDEO:
            row["budgets"] = budgets
    registry = tmp_path / f"playbooks_{len(list(tmp_path.glob('playbooks_*')))}.yaml"
    registry.write_text(yaml.safe_dump(rows), encoding="utf-8")
    monkeypatch.setattr(playbooks, "_registry_path", lambda: registry)


def test_registry_budgets_are_known_kinds(tmp_path, monkeypatch):
    _registry(tmp_path, monkeypatch, ["ai_usd", "voice_credits"])
    assert [st.id for st in flow.steps(ORGANIC_VIDEO)][:2] == ["A0", "A1"]
    _registry(tmp_path, monkeypatch, ["ai_usd", "bitcoin"])
    with pytest.raises(ValueError, match=ORGANIC_VIDEO) as no:
        flow.steps(ORGANIC_VIDEO)
    assert "bitcoin" in str(no.value) and "playbooks.yaml" in str(no.value)
    _registry(tmp_path, monkeypatch, ["ai_usd"])   # the pack's yes is for a kind not listed
    with pytest.raises(ValueError, match="voice_credits"):
        flow.steps(ORGANIC_VIDEO)
    for bad in ("ai_usd", [3], [""], {"ai_usd": 1}):
        _registry(tmp_path, monkeypatch, bad)
        with pytest.raises(ValueError, match=ORGANIC_VIDEO) as no:   # its row, wherever it is
            playbooks.get("organic-video")
        assert "budgets" in str(no.value)


# --- the intake at A0 -----------------------------------------------------------------

def _tm(capsys, *argv):
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_reuse_profile_decided_after_a0_intake(tmp_path, monkeypatch, capsys, bundled_skills):
    """Organic video asks its intake at A0 (it is not a late-intake playbook): `tm decide
    reuse_profile` is refused until the level and the outputs are set, and recorded after A0."""
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    code, out = _tm(capsys, "run", "new", "--playbook", "organic-video", "--name", "exampleedu")
    assert code == 0
    run = RunFolder.open(out["path"])
    assert run.path.parent == ws / "runs" / ORGANIC_VIDEO
    assert ORGANIC_VIDEO not in flow._LATE_INTAKE
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A0", "work") and "one batch" in nxt.message
    code, out = _tm(capsys, "decide", "reuse_profile", "reuse", "--run", str(run.path))
    assert code == 1 and "level and the outputs are not set" in out["message"]
    (run.path / "answers.json").write_text(json.dumps(
        {"level": "every_step", "outputs": ["proposals"], "channels": ["ExampleEdu"]}), encoding="utf-8")
    assert _tm(capsys, "config", "write", "--run", str(run.path), "--answers", "answers.json")[0] == 0
    assert (state.load(run).level, state.load(run).outputs) == ("every_step", ["proposals"])
    assert _tm(capsys, "organic", "stack", "--run", str(run.path), "--replicate", "ok", "--elevenlabs", "missing",
               "--artifacts", "ok", "--browser", "ok")[0] == 0
    assert _tm(capsys, "done", "A0", "--run", str(run.path))[0] == 0
    code, out = _tm(capsys, "decide", "reuse_profile", "reuse", "--run", str(run.path))
    assert code == 1 and "exampleedu is saved" in out["message"]   # no profile to reuse yet
    code, out = _tm(capsys, "decide", "reuse_profile", "new", "--run", str(run.path))
    assert code == 0, out
    assert [(d["checkin"], d["choice"], d["by"]) for d in state.load(run).decisions] == [
        ("reuse_profile", "new", "user")]
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A1", "work")   # the profile is drafted at A1


def test_state_holds_organic_planned_and_planned_at(tmp_path):
    run = _organic(tmp_path, "every_step", ["organic_video"])
    s = state.load(run)
    assert (list(s.organic), s.planned, s.planned_at) == (["stack"], {}, None)   # the stack check is recorded
    s.organic = {"parent": "runs/03-organic-ai-video/2026-11-07_ideas", "proposal": "p1"}
    s.planned = {"ai_usd": 2.4, "voice_credits": 900.0}
    s.planned_at = "2026-11-07T10:00:00+00:00"
    state.save(run, s)
    again = state.load(run)
    assert (again.organic["proposal"], again.planned, again.planned_at) == (
        "p1", {"ai_usd": 2.4, "voice_credits": 900.0}, "2026-11-07T10:00:00+00:00")
