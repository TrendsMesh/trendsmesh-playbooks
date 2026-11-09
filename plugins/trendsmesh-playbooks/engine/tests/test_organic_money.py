"""Money for a playbook other than refresh-ad: organic video declares ai_usd and voice_credits, the
pack check-in's yes approves them, and a planned amount waits at every level."""

import json
from datetime import date

import pytest

from tm import budget, flow, organic, organic_pack, organic_qa, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

PACK_NAME = "Approve the generation pack and its cost"   # the pack check-in's name (Task 1)
LONG_AGO = "2026-01-01T00:00:00+00:00"


@pytest.fixture(autouse=True)
def pack_checked(monkeypatch):
    """The walks here are about money: D1's credits and recipe and E2's pack checks pass (test_organic_doctor and
    test_organic_pack prove them, and that the pack check sets planned and planned_at, on the ExampleEdu and pet-store
    packs), and so do F1's and F2's picks (test_organic_qa)."""
    monkeypatch.setattr(organic, "credits_gap", lambda run: None)
    monkeypatch.setattr(organic_pack, "recipe_gap", lambda run: None)
    monkeypatch.setattr(organic_pack, "pack_gap", lambda run: None)
    monkeypatch.setattr(organic_qa, "images_gap", lambda run: None)
    monkeypatch.setattr(organic_qa, "takes_gap", lambda run: None)


def _run(tmp_path, level="every_step", planned=None, planned_at=LONG_AGO):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "exampleedu", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.outputs = ["organic_video"]
    if planned:
        s.planned, s.planned_at = dict(planned), planned_at
    state.save(run, s)
    set_level(run, level)
    return run


def _to_pack(run):
    """Work D1 to E2, deciding taste, so the pack is the next question."""
    for _ in range(20):
        nxt = flow.next(run)
        if nxt.action == "work":
            complete(run, nxt.step)
        elif nxt.action == "ask" and nxt.checkin.ids == ["pack"]:
            return nxt
        else:
            decide(run, nxt.checkin.ids[0], "accept", by="user", note=None)
    raise AssertionError("the pack was never asked")


def _approve(run, kind, amount, capsys):
    capsys.readouterr()
    code = main(["budget", "approve", kind, str(amount), "--run", str(run.path), "--json"])
    out = capsys.readouterr()
    return code, out.out + out.err


def _spending_step(run, step):
    """Walk to `step` (answering everything else by the user) and return the next()."""
    for _ in range(40):
        nxt = flow.next(run)
        if nxt.step == step and nxt.action in ("work", "stop"):
            return nxt
        if nxt.action == "work":
            complete(run, nxt.step)
        elif nxt.action in ("ask", "auto"):
            for cid in nxt.checkin.ids:
                decide(run, cid, flow.checkins.load(playbook=ORGANIC_VIDEO).checkins[cid].choices[0],
                       by="user" if nxt.action == "ask" else "rule", note=None if nxt.action == "ask" else "t")
        else:
            return nxt
    raise AssertionError("never reached " + step)


def test_organic_approve_waits_for_pack_yes(tmp_path, capsys):
    run = _run(tmp_path, planned={"ai_usd": 1.46})
    _to_pack(run)
    code, text = _approve(run, "ai_usd", 1.46, capsys)
    assert code == 1 and PACK_NAME in text and "tm decide pack approve" in text
    decide(run, "pack", "approve", by="user", note=None)
    code, _ = _approve(run, "ai_usd", 1.46, capsys)
    assert code == 0
    assert state.load(run).budgets == {"ai_usd": 1.46}


def test_same_pack_yes_approves_voice_credits(tmp_path, capsys):
    run = _run(tmp_path, planned={"ai_usd": 1.46, "voice_credits": 3000})
    _to_pack(run)
    assert _approve(run, "voice_credits", 3000, capsys)[0] == 1
    decide(run, "pack", "approve", by="user", note=None)
    assert _approve(run, "ai_usd", 1.46, capsys)[0] == 0
    assert _approve(run, "voice_credits", 3000, capsys)[0] == 0
    assert state.load(run).budgets == {"ai_usd": 1.46, "voice_credits": 3000}


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_spending_step_waits_at_every_level_for_organic(tmp_path, level):
    run = _run(tmp_path, level=level, planned={"ai_usd": 1.46})
    nxt = _spending_step(run, "F1")
    assert nxt.action == "stop" and "AI generation cost is not approved yet" in nxt.message
    assert PACK_NAME in nxt.message
    assert [x["reason_id"] for x in state.load(run).stops if "resumed_at" not in x] == ["budget_ai_usd"]
    # the stop lets the pack's yes be recorded again and the amount approved, then F1 is work
    s = state.load(run)
    s.budgets["ai_usd"] = 1.46
    state.save(run, s)
    assert flow.next(run).action == "work"


def test_nothing_planned_means_no_wait(tmp_path):
    run = _run(tmp_path, planned={"ai_usd": 0})   # an Atlas video costs $0
    nxt = _spending_step(run, "F1")
    assert (nxt.step, nxt.action) == ("F1", "work")


def test_pack_reject_skips_spending_and_refuses_approval(tmp_path, capsys):
    run = _run(tmp_path, planned={"ai_usd": 1.46})
    _to_pack(run)
    decide(run, "pack", "reject", by="user", note=None)
    code, text = _approve(run, "ai_usd", 1.46, capsys)
    assert code == 1 and "said no" in text and "tm decide pack approve --change" in text
    assert state.load(run).budgets == {}
    walked = []
    for _ in range(10):   # the spending steps and the edit are never offered, nor their check-ins
        nxt = flow.next(run)
        assert nxt.action != "stop"
        if nxt.step == "H1":
            break
        walked.append(nxt.step)
        assert nxt.action == "work"
        complete(run, nxt.step)
    assert nxt.step == "H1" and walked == []   # E2 was worked before the pack was asked
    s = state.load(run)
    assert {d["checkin"] for d in s.decisions} == {"taste", "pack"}
    assert s.spend == {} and s.budgets == {}


def test_pack_reject_after_approval_withdraws_the_budget(tmp_path, capsys):
    """The review's probe: a no given after the amount was approved takes the money back, so a paid
    call through the budget guard is refused."""
    run = _run(tmp_path, planned={"ai_usd": 1.46, "voice_credits": 3000})
    _to_pack(run)
    decide(run, "pack", "approve", by="user", note=None)
    assert _approve(run, "ai_usd", 1.46, capsys)[0] == 0
    assert _approve(run, "voice_credits", 3000, capsys)[0] == 0
    capsys.readouterr()
    assert main(["decide", "pack", "reject", "--change", "--run", str(run.path)]) == 0
    assert state.load(run).budgets == {}
    assert budget.spend(run, "ai_usd", 1.00, "first stage") == 2
    s = state.load(run)
    assert s.spend == {} and any(x["reason_id"] == "over_budget_ai_usd" for x in s.stops)


def test_pack_reject_keeps_a_budget_already_spent(tmp_path, capsys):
    """PB01's rule: an approved amount that is already being spent stays (its record stays true)."""
    run = _run(tmp_path, planned={"ai_usd": 1.46, "voice_credits": 3000})
    _to_pack(run)
    decide(run, "pack", "approve", by="user", note=None)
    assert _approve(run, "ai_usd", 1.46, capsys)[0] == 0
    assert _approve(run, "voice_credits", 3000, capsys)[0] == 0
    assert budget.spend(run, "voice_credits", 500, "voiceover") == 0
    decide(run, "pack", "reject", by="user", note=None, change=True)
    assert state.load(run).budgets == {"voice_credits": 3000}


def test_replanned_pack_needs_a_new_yes(tmp_path, capsys):
    run = _run(tmp_path, planned={"ai_usd": 1.46})
    _to_pack(run)
    decide(run, "pack", "approve", by="user", note=None)
    assert _approve(run, "ai_usd", 1.46, capsys)[0] == 0
    s = state.load(run)
    s.decisions[-1]["at"] = LONG_AGO   # the first yes, given before the re-plan below
    s.planned, s.planned_at = {"ai_usd": 1.76}, flow._now()   # re-checked: a real re-plan time
    state.save(run, s)
    nxt = _spending_step(run, "F1")
    assert nxt.action == "stop"
    assert any(x["reason_id"] == "budget_ai_usd" for x in state.load(run).stops if "resumed_at" not in x)
    code, text = _approve(run, "ai_usd", 1.76, capsys)   # the old yes and the open stop do not approve
    assert code == 1 and "--change" in text and "tm decide pack approve" in text
    assert state.load(run).budgets == {"ai_usd": 1.46}
    decide(run, "pack", "approve", by="user", note=None, change=True)   # the stop lets it be recorded
    assert state.load(run).decisions[-1]["at"] >= state.load(run).planned_at
    assert _approve(run, "ai_usd", 1.76, capsys)[0] == 0
    assert state.load(run).budgets == {"ai_usd": 1.76}


def test_a_kind_without_stop_words_still_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(flow, "PLANNED_STOP", {})
    run = _run(tmp_path, planned={"ai_usd": 1.46})
    nxt = _spending_step(run, "F1")
    assert nxt.action == "stop" and "ai_usd amount is not approved yet" in nxt.message


def test_refresh_ad_money_unchanged(tmp_path):
    """test_money_holds.py and test_budget.py stay green unchanged; the G6 approval text, literally."""
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    s = state.load(run)
    s.level, s.outputs = "every_step", ["creative_brief", "ai_video"]
    gap = flow.approval_gap(s, "ai_usd", None)
    assert gap == ('Ask "Approve the AI video plan and budget" (G6) first and record the user\'s yes with '
                   '`tm decide G6 approve`; then approve the amount they agreed to.'), gap


@pytest.mark.parametrize("planned_at,approves", [("2026-01-01T00:00:00", True), ("2999-01-01T00:00:00", False)])
def test_a_naive_plan_time_is_read_as_utc(tmp_path, capsys, planned_at, approves):
    """A planned_at without a time zone is compared with the decision's aware time as UTC, never a crash."""
    run = _run(tmp_path, planned={"ai_usd": 1.46}, planned_at=planned_at)
    _to_pack(run)
    decide(run, "pack", "approve", by="user", note=None)
    code, text = _approve(run, "ai_usd", 1.46, capsys)
    assert code == (0 if approves else 1), text
    if not approves:
        assert "tm decide pack approve --change" in text
