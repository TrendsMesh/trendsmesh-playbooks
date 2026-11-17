"""Create an ad (playbook 05): its steps and check-ins, walked at each level (the owner's decision 3), the money
check-ins (decision 2), the upload offer, and the skips."""

from datetime import date

import pytest

from tm import checkins, flow, state, stepchecks
from tm.flow import complete, decide, set_level
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder

STEPS = ["S0", "S1", "S3", "S4", "S5", "G1", "G2", "G3", "G4", "S6", "S7", "G5", "S8", "S9", "S10a", "S10b"]
ASKED = {   # check-ins asked of the user at each level, in order (the card at Just the big calls is one ask)
    "every_step": [["intake"], ["concept"], ["board"], ["plan"], ["visual"], ["audio"], ["storyboard"], ["takes"],
                   ["review"], ["copy"], ["upload_offer"], ["upload"]],
    "big_calls": [["intake"], ["concept"], ["board", "plan"], ["visual"], ["storyboard"], ["review"], ["copy"],
                  ["upload_offer"], ["upload"]],
    "hands_off": [["intake"], ["upload_offer"], ["upload"]],
}


@pytest.fixture(autouse=True)
def checks_pass(monkeypatch):
    """The walks are about the flow: every create-ad step check passes (their own tests prove them)."""
    real = stepchecks.run
    monkeypatch.setattr(stepchecks, "run", lambda name, folder: None if name.startswith("ad_") else real(name, folder))


def _run(tmp_path, level):
    (tmp_path / "w").mkdir()
    run = RunFolder.create(tmp_path / "w", "planner", date(2026, 11, 11), playbook=CREATE_AD)
    s = state.load(run)
    s.outputs = ["video_ad"]
    state.save(run, s)
    set_level(run, level)
    return run


def _first(cid):
    return checkins.load(playbook=CREATE_AD).checkins[cid].choices[0]


def _walk(run, answer=None, limit=80):
    """Walk to the end; the user answers each ask with its first choice (or `answer[cid]`). Returns (asked, ruled,
    steps worked, the last next())."""
    answer = answer or {}
    asked, ruled, worked = [], [], []
    for _ in range(limit):
        nxt = flow.next(run)
        if nxt.action == "work":
            worked.append(nxt.step)
            complete(run, nxt.step)
        elif nxt.action == "ask":
            asked.append(nxt.checkin.ids)
            for cid in nxt.checkin.ids:
                decide(run, cid, answer.get(cid, _first(cid)), by="user", note=None)
        elif nxt.action == "auto":
            ruled.extend(nxt.checkin.ids)
            for cid in nxt.checkin.ids:
                decide(run, cid, _first(cid), by="rule", note="the rule's data")
        else:
            return asked, ruled, worked, nxt
    raise AssertionError("the walk did not end")


def test_the_steps_follow_the_spec():
    every = flow.steps(CREATE_AD)
    assert [st.id for st in every] == STEPS
    assert {st.id for st in every if st.spends} == {"G1", "G2", "G4"}   # the paid stages
    assert all(st.ref == f"skills/create-ad/references/flow.md#{st.id.lower()}" for st in every)
    cat = checkins.load(playbook=CREATE_AD)
    assert {cid for cid, c in cat.checkins.items() if c.money} == {"plan", "storyboard", "upload"}
    assert cat.checkins["plan"].yes_for == ("ai_usd", "voice_credits")
    assert cat.checkins["storyboard"].yes_for == ("ai_usd", "voice_credits")
    assert not any("activate" in (c.choices or ()) for c in cat.checkins.values())   # nothing activates (#46)


@pytest.mark.parametrize("level", list(ASKED))
def test_each_level_asks_its_check_ins(tmp_path, level):
    run = _run(tmp_path, level)
    asked, ruled, worked, last = _walk(run)
    assert last.action == "done", last
    assert asked == ASKED[level]
    every = {c for ids in ASKED["every_step"] for c in ids}
    assert set(ruled) == every - {c for ids in asked for c in ids}
    assert worked == STEPS


def test_the_upload_offer_and_go_ahead_are_asked_even_hands_off(tmp_path):
    run = _run(tmp_path, "hands_off")
    asked, _, worked, last = _walk(run, {"upload_offer": "skip"})
    assert asked == [["intake"], ["upload_offer"]] and last.action == "done"
    assert "S10a" not in worked and "S10b" not in worked


def test_a_no_to_the_plan_skips_every_paid_step(tmp_path):
    run = _run(tmp_path, "every_step")
    asked, _, worked, last = _walk(run, {"plan": "reject"})
    assert last.action == "done"
    assert worked == ["S0", "S1", "S3", "S4", "S5"]
    assert asked == [["intake"], ["concept"], ["board"], ["plan"]]


def test_a_take_failing_qa_stops_for_the_user(tmp_path):
    run = _run(tmp_path, "every_step")
    _, _, _, last = _walk(run, {"takes": "fails_qa"})
    assert last.action == "stop" and "never regenerated automatically" in last.message


def test_a_paid_step_waits_for_its_planned_amount(tmp_path):
    run = _run(tmp_path, "every_step")
    s = state.load(run)
    s.planned, s.planned_at = {"ai_usd": 1.2}, "2026-11-11T10:00:00+00:00"
    state.save(run, s)
    for _ in range(30):
        nxt = flow.next(run)
        if nxt.step == "G1":
            break
        if nxt.action == "work":
            complete(run, nxt.step)
        else:
            for cid in nxt.checkin.ids:
                decide(run, cid, _first(cid), by="user", note=None)
    assert (nxt.step, nxt.action) == ("G1", "stop")   # the plan said yes, the budget is not approved yet


def test_every_step_ref_has_its_section():
    from tm import paths
    root = paths.bundled_data().parent
    text = (root / "skills" / "create-ad" / "references" / "flow.md").read_text(encoding="utf-8")
    for st in flow.steps(CREATE_AD):
        anchor = st.ref.split("#", 1)[1]
        assert f'<a id="{anchor}"></a>' in text, st.id
    skill = (root / "skills" / "create-ad" / "SKILL.md").read_text(encoding="utf-8")
    for ref in ("references/flow.md", "references/rules.md", "references/pages.md", "PLAN.md"):
        assert ref in skill and (root / "skills" / "create-ad" / ref).is_file(), ref
