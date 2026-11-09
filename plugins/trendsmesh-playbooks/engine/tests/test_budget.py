"""Budgets: estimate, approve, spend."""

import json
from datetime import date
from typing import get_args

import pytest

from tm import budget, flow, state
from tm.cli import main
from tm.runfolder import RunFolder


@pytest.fixture
def run(tmp_path):
    """A run whose spending check-ins the user has answered yes (approval needs that yes)."""
    ws = tmp_path / "Moje reklamy Łódź"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.level, s.flows = "every_step", ["V"]
    s.outputs = ["creative_brief", "edited_video", "ai_video", "live_test"]
    s.decisions = [{"checkin": c, "choice": "approve", "by": "user", "at": "2026-11-05T10:00:00+00:00"}
                   for c in ("VB", "G6", "G10")]
    state.save(r, s)
    return r


def test_kinds_match_the_engine():
    assert tuple(get_args(budget.Kind)) == flow.BUDGET_KINDS


def test_estimate_changes_nothing(run):
    est = budget.estimate("ai_usd", 3.2, "first frame, 4 tries")
    assert (est.kind, est.amount, est.what) == ("ai_usd", 3.2, "first frame, 4 tries")
    assert "USD" in est.text and "first frame" in est.text and "Replicate" in est.text
    assert "ElevenLabs" in budget.estimate("voice_credits", 900, "clone").text
    assert state.load(run).spend == {} and state.load(run).budgets == {}
    with pytest.raises(ValueError, match="kind"):
        budget.estimate("gold", 1, "x")
    with pytest.raises(ValueError, match="negative|below"):
        budget.estimate("ai_usd", -1, "x")


def test_approve_then_spend_adds_up(run):
    budget.approve(run, "ai_usd", 10)
    assert budget.spend(run, "ai_usd", 4.0, "first frame") == 0
    assert budget.spend(run, "ai_usd", 5.5, "clip 1") == 0
    s = state.load(run)
    assert s.spend == {"ai_usd": 9.5} and s.budgets == {"ai_usd": 10}
    assert s.status == "active"


def test_overspend_stops(run):
    budget.approve(run, "ai_usd", 10)
    assert budget.spend(run, "ai_usd", 8.0, "clip 1") == 0
    assert budget.spend(run, "ai_usd", 3.0, "clip 2") == 2
    s = state.load(run)
    assert s.spend == {"ai_usd": 8.0}                       # the refused spend is not counted
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "over_budget_ai_usd"
    assert "clip 2" in s.stops[-1]["what"] and s.stops[-1]["todo"]
    assert flow.open_stop(run, ["over_budget_ai_usd"])
    # raising the approved amount and resuming lets the spend through
    budget.approve(run, "ai_usd", 12)
    flow.resume(run)
    assert budget.spend(run, "ai_usd", 3.0, "clip 2") == 0
    assert state.load(run).spend == {"ai_usd": 11.0}


def test_spend_without_an_approved_budget_stops(run):
    assert budget.spend(run, "voice_credits", 100, "clone") == 2
    assert state.load(run).spend == {}


def test_exact_budget_is_allowed_and_approval_cannot_go_below_spend(run):
    budget.approve(run, "test", 100)
    assert budget.spend(run, "test", 100, "day 1 to 5") == 0
    with pytest.raises(ValueError, match="already spent"):
        budget.approve(run, "test", 50)


def test_spent_money_survives_a_level_change(run):
    budget.approve(run, "ai_usd", 10)
    budget.spend(run, "ai_usd", 4, "frame")
    flow.set_level(run, "hands_off")
    flow.set_level(run, "every_step")
    assert state.load(run).spend == {"ai_usd": 4}


def test_cli(run, tmp_path):
    base = ["--run", str(run.path), "--json"]
    assert main(["budget", "estimate", "ai_usd", "2.5", "--what", "frame", "--json"]) == 0
    assert main(["budget", "approve", "ai_usd", "5", *base]) == 0
    assert main(["budget", "spend", "ai_usd", "4", "--what", "frame", *base]) == 0
    assert main(["budget", "spend", "ai_usd", "4", "--what", "clip", *base]) == 2
    assert main(["budget", "spend", "ai_usd", "x", "--what", "clip", *base]) == 1
    assert main(["budget", "spend", "gold", "1", "--what", "clip", *base]) == 1


def test_reconcile_gives_back_what_was_not_used(run):
    budget.approve(run, "voice_credits", 1000)
    assert budget.spend(run, "voice_credits", 600, "isolate") == 0
    assert budget.reconcile(run, "voice_credits", 600, 420, "isolate") == 0
    assert state.load(run).spend == {"voice_credits": 420}


def test_reconcile_overrun_is_recorded_and_stops(run):
    budget.approve(run, "voice_credits", 1000)
    assert budget.spend(run, "voice_credits", 900, "tts") == 0
    assert budget.reconcile(run, "voice_credits", 900, 1100, "tts") == 2
    s = state.load(run)
    assert s.spend == {"voice_credits": 1100}          # the real cost, not hidden
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "over_budget_voice_credits"
    with pytest.raises(flow.Held, match="nothing was spent"):
        budget.spend(run, "voice_credits", 1, "next take")
