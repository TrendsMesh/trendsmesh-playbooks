"""The engine, not the agent, holds money and the launch (final review I1, I2, I4, I5, #17).

- I1: an open stop blocks `tm budget approve`, `tm budget spend` and the launch decision.
- I2: G11 takes only `activate` or `keep_paused`; each sets exactly its state; E3 needs its booking.
- I4: a live test without a feasible R4 plan cannot be designed, approved or launched.
- I5: a budget is approved only after the user's yes at its spending check-in.
- #17: `reject` at a spending check-in skips that output's paid steps, with a "nothing spent" note.
"""

import json
from datetime import date

import pytest
from conftest import trend_steps_ready

from tm import budget, flow, r4, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.runfolder import RunFolder

ALL_OUTPUTS = ["creative_brief", "edited_video", "ai_video", "live_test"]


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy Łódź"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    trend_steps_ready(r)
    return r


def _setup(run, level, outputs, flows=(), budgets=None, plan=True):
    s = state.load(run)
    s.outputs, s.flows = list(outputs), list(flows)
    s.budgets = dict(budgets or {})
    state.save(run, s)
    set_level(run, level)
    if plan:
        _plan(run, per_day=400)


def _control():
    from tm.r1 import Window
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=1350.0, results=30,
                  impressions=100_000, p25=30_000, thruplay=15_000, clicks_est=1_500,
                  frequency=1.5, cpm=20.0, weeks=1)


def _cfg(per_day):
    from tm import config
    c = config.defaults()
    c["budget"]["test_per_day"] = per_day
    return c


def _plan(run, per_day, variants=2):
    p = r4.plan("hook", _control(), variants, _cfg(per_day))
    r4.record(run, p)
    return p


def _cli(run, *args):
    return main([*args, "--run", str(run.path), "--json"])


def _settle(run):
    for _ in range(60):
        nxt = flow.next(run)
        if nxt.action == "ask":
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            decide(run, nxt.checkin.card or nxt.checkin.ids[0], choice, by="user", note=None)
        elif nxt.action == "auto":
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            decide(run, nxt.checkin.ids[0], choice, by="rule", note="test data")
        else:
            return nxt
    raise AssertionError("the engine kept asking")


def _work_to(run, step):
    for _ in range(60):
        nxt = _settle(run)
        assert nxt.action == "work", nxt
        if nxt.step == step:
            return nxt
        if nxt.step == "E3":
            budget.spend(run, "test", 1, "live test")
        complete(run, nxt.step)
    raise AssertionError(f"never reached {step}")


def _at_e2b_check(run):
    """Work through E2b and stop right before its R8 decision."""
    _work_to(run, "E2b")
    complete(run, "E2b")
    nxt = flow.next(run)
    assert (nxt.action, nxt.checkin.ids) == ("auto", ["E2b"])


# --- I1: a stopped run blocks spending, approval and the launch -----------------

def test_red_r8_blocks_spend_approval_and_launch(run, capsys):
    """The review's exact sequence at Just the big calls: nothing gets through the red stop."""
    _setup(run, "big_calls", ["creative_brief", "live_test"])
    _at_e2b_check(run)
    assert state.load(run).budgets == {}                        # the card's yes, no amount yet
    assert _cli(run, "decide", "E2b", "red", "--by", "rule", "--note", "no AI label") == 2
    capsys.readouterr()
    assert _cli(run, "budget", "approve", "test", "100") == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "R8" in out["message"] and "nothing was approved" in out["message"]
    assert _cli(run, "budget", "spend", "test", "100", "--what", "live test") == 2
    assert "nothing was spent" in json.loads(capsys.readouterr().out)["message"]
    assert _cli(run, "decide", "approve_launch", "activate") == 2
    assert _cli(run, "decide", "G11", "activate") == 2
    s = state.load(run)
    assert s.spend == {} and s.budgets == {} and s.measurements_due == []
    assert not any(d["checkin"] == "G11" for d in s.decisions)
    # clearing the stop is the only way on
    decide(run, "E2b", "green", by="rule", note="AI label added", change=True)
    assert state.load(run).status == "active"
    assert _cli(run, "budget", "approve", "test", "100") == 0
    assert _cli(run, "decide", "approve_launch", "activate") == 0
    assert _cli(run, "budget", "spend", "test", "100", "--what", "live test") == 0


def test_a_stop_the_agent_recorded_blocks_money_until_resume(run):
    _setup(run, "every_step", ["creative_brief", "live_test"])
    _at_e2b_check(run)
    decide(run, "E2b", "green", by="rule", note="all green")
    flow.stop(run, "upload_by_hand", "The videos could not be sent to Meta.", "Upload them by hand.")
    with pytest.raises(flow.Held, match="nothing was decided"):
        decide(run, "G11", "activate", by="user", note=None)
    with pytest.raises(flow.Held, match="tm resume"):
        budget.spend(run, "test", 10, "live test")
    flow.resume(run)
    decide(run, "G11", "activate", by="user", note=None)


def test_a_budget_stop_lets_that_budget_be_approved_and_nothing_else(run):
    _setup(run, "every_step", ALL_OUTPUTS, flows=["V"], plan=True)
    s = state.load(run)
    s.decisions = [{"checkin": c, "choice": "approve", "by": "user", "at": "x"} for c in ("VB", "G6")]
    s.budgets = {"ai_usd": 5.0}
    state.save(run, s)
    assert budget.spend(run, "ai_usd", 8, "clip 1") == 2              # over budget: stopped
    with pytest.raises(flow.Held):
        budget.approve(run, "voice_credits", 100)                    # another kind: held
    budget.approve(run, "ai_usd", 10)                                # this kind: the way out
    with pytest.raises(flow.Held):
        budget.spend(run, "ai_usd", 8, "clip 1")                     # still stopped until resume
    flow.resume(run)
    assert budget.spend(run, "ai_usd", 8, "clip 1") == 0


# --- I2: G11's own choices, each setting exactly its state ---------------------

def test_launch_takes_only_its_own_choices(run):
    _setup(run, "every_step", ["live_test"], budgets={"test": 500.0})
    _at_e2b_check(run)
    decide(run, "E2b", "green", by="rule", note="all green")
    for word in ("approve", "yes", "ok"):
        with pytest.raises(ValueError, match="activate, keep_paused"):
            decide(run, "G11", word, by="user", note=None)
    assert state.load(run).measurements_due == []


def test_activate_needs_a_green_r8_first(run):
    _setup(run, "every_step", ["live_test"], budgets={"test": 500.0})
    _at_e2b_check(run)                                  # E2b due, not decided yet
    with pytest.raises(ValueError, match="E2b"):
        decide(run, "G11", "activate", by="user", note=None)


def test_activate_sets_dates_and_e3_needs_its_booking(run):
    _setup(run, "every_step", ["live_test"], budgets={"test": 500.0})
    _at_e2b_check(run)
    decide(run, "E2b", "green", by="rule", note="all green")
    decide(run, "G11", "activate", by="user", note=None, today=date(2026, 11, 10))
    assert state.load(run).measurements_due == ["2026-11-13", "2026-11-15", "2026-11-17"]
    assert (flow.next(run).step, flow.next(run).action) == ("E3", "work")
    with pytest.raises(ValueError, match="tm budget spend"):
        complete(run, "E3")                              # nothing booked: no activation recorded
    budget.spend(run, "test", 500, "live test")
    complete(run, "E3")
    assert flow.next(run, today=date(2026, 11, 13)).step == "E4"


def test_keep_paused_closes_the_test_and_clears_the_dates(run):
    _setup(run, "every_step", ["live_test"], budgets={"test": 500.0})
    _at_e2b_check(run)
    decide(run, "E2b", "green", by="rule", note="all green")
    decide(run, "G11", "activate", by="user", note=None, today=date(2026, 11, 10))
    decide(run, "G11", "keep_paused", by="user", note="not now", change=True)
    s = state.load(run)
    assert s.measurements_due == [] and s.measurements_done == []
    nxt = flow.next(run)
    assert nxt.action == "done" and "paused" in nxt.message and "nothing" in nxt.message
    s = state.load(run)
    assert s.status == "done" and s.spend == {}


# --- I4: no feasible R4 plan, no live test ----------------------------------------

def test_e1_needs_an_r4_plan(run):
    _setup(run, "every_step", ["live_test"], plan=False)
    _work_to(run, "E1")
    with pytest.raises(ValueError, match="tm r4"):
        complete(run, "E1")
    _plan(run, per_day=400)
    complete(run, "E1")


def test_an_unreachable_sample_holds_the_run_with_the_options(run, tmp_path, capsys):
    _setup(run, "every_step", ["creative_brief", "live_test"], plan=False)
    _work_to(run, "E1")
    (run.path / "config.yaml").write_text("budget:\n  test_per_day: 150\n", encoding="utf-8")
    cf = tmp_path / "control.json"
    from tm import r2
    cf.write_text(json.dumps(r2.window_to_json(_control())), encoding="utf-8")
    assert _cli(run, "r4", "--stage", "hook", "--control", str(cf), "--variants", "2") == 2
    s = state.load(run)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "test_plan_infeasible"
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("E1", "stop")
    for option in ("daily budget", "more days", "fewer variants", "skip the live test"):
        assert option in nxt.message
    with pytest.raises(flow.Held):
        complete(run, "E1")
    with pytest.raises(flow.Held):
        decide(run, "G10", "approve", by="user", note=None)
    # raising the daily budget gives a feasible plan, which clears the stop
    capsys.readouterr()
    assert _cli(run, "r4", "--stage", "hook", "--control", str(cf), "--variants", "2",
                "--per-day", "400") == 0
    assert state.load(run).status == "active"
    complete(run, "E1")
    decide(run, "G10", "approve", by="user", note=None)


def test_more_days_also_make_the_plan_feasible(run):
    _setup(run, "every_step", ["live_test"], plan=False)
    tight = r4.plan("hook", _control(), 2, _cfg(150))
    assert not tight.feasible
    loose = r4.plan("hook", _control(), 2, _cfg(150), max_days=tight.days)
    assert loose.feasible and loose.days == tight.days


def test_skipping_the_live_test_clears_the_hold(run):
    _setup(run, "every_step", ["creative_brief", "live_test"], plan=False)
    _work_to(run, "E1")
    _plan(run, per_day=150)
    assert not state.load(run).test_plan["feasible"]
    assert flow.next(run).action == "stop"
    with pytest.raises(flow.Held):
        complete(run, "E1")
    decide(run, "G10", "reject", by="user", note="skip the test")   # the stop's own check-in
    assert state.load(run).status == "active"
    complete(run, "E1")
    nxt = flow.next(run)
    assert nxt.action == "done" and "live test" in nxt.message and "nothing" in nxt.message


def test_launch_without_a_plan_is_refused(run):
    _setup(run, "every_step", ["live_test"], budgets={"test": 500.0})
    _at_e2b_check(run)
    decide(run, "E2b", "green", by="rule", note="all green")
    s = state.load(run)
    s.test_plan = None
    state.save(run, s)
    with pytest.raises(ValueError, match="tm r4"):
        decide(run, "G11", "activate", by="user", note=None)


# --- I5: a budget is approved only after the user's yes ---------------------------

def test_budget_approval_waits_for_the_users_yes(run):
    _setup(run, "every_step", ["live_test"])
    _work_to(run, "E1")
    with pytest.raises(ValueError, match="G10"):
        budget.approve(run, "test", 500)                  # before the check-in
    complete(run, "E1")
    decide(run, "G10", "approve", by="user", note=None)
    budget.approve(run, "test", 500)
    assert state.load(run).budgets == {"test": 500}
    decide(run, "G10", "reject", by="user", note="too much", change=True)
    with pytest.raises(ValueError, match="said no"):
        budget.approve(run, "test", 400)                  # after a reject


def test_card_yes_counts_at_just_the_big_calls(run):
    _setup(run, "big_calls", ["creative_brief", "live_test"])
    _work_to(run, "E1")
    assert _cli(run, "budget", "approve", "test", "500") == 1
    complete(run, "E1")
    decide(run, "approve_spending", "approve", by="user", note=None)
    assert _cli(run, "budget", "approve", "test", "500") == 0


def test_hands_off_approves_only_when_the_run_stops_for_the_budget(run):
    _setup(run, "hands_off", ["live_test"])
    with pytest.raises(ValueError, match="Hands-off"):
        budget.approve(run, "test", 500)
    for _ in range(60):
        nxt = _settle(run)
        if nxt.action == "stop":
            break
        complete(run, nxt.step)
    assert (nxt.step, state.load(run).stops[-1]["reason_id"]) == ("E3", "budget_test")
    budget.approve(run, "test", 500)                      # the stop asked the user
    assert (flow.next(run).step, flow.next(run).action) == ("E3", "work")


def test_a_kind_with_no_check_in_needs_the_users_words(run):
    """VC's ProPainter spends ai_usd in a run without the AI video (no G6)."""
    _setup(run, "every_step", ["edited_video"], flows=["V"])
    with pytest.raises(ValueError, match="--note"):
        budget.approve(run, "ai_usd", 2)
    budget.approve(run, "ai_usd", 2, note="Yes, spend up to 2 dollars on the caption removal")
    s = state.load(run)
    assert s.budgets == {"ai_usd": 2} and s.approvals[-1]["note"].startswith("Yes")
    assert _cli(run, "budget", "approve", "ai_usd", "3", "--note", "ok, 3") == 0


def test_intake_budgets_are_approved_in_hands_off(run):
    from tm import config
    config.write_from_intake(run, {"level": "hands_off", "outputs": ["live_test"],
                                   "budget": {"test_per_day": 50, "test_days": 4}})
    assert state.load(run).budgets == {"test": 200}


# --- #17: a reject skips that output's paid steps -------------------------------

@pytest.mark.parametrize("cid,outputs,flows,skipped", [
    ("G6", ["creative_brief", "ai_video"], [], ["D2", "D3", "D4", "D5"]),
    ("G10", ["creative_brief", "live_test"], [], ["E2", "E2b", "E3", "E4"]),
    ("VB", ["creative_brief", "edited_video"], ["V"], ["V1", "V3", "V4", "V5", "VC", "C2", "C3", "C4"]),
])
def test_reject_skips_the_paid_steps_and_says_nothing_was_spent(run, cid, outputs, flows, skipped):
    _setup(run, "every_step", outputs, flows=flows)
    seen = []
    for _ in range(80):
        nxt = flow.next(run)
        if nxt.action == "ask" and nxt.checkin.ids == [cid]:
            decide(run, cid, "reject", by="user", note="no")
            continue
        if nxt.action in ("ask", "auto"):
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            decide(run, nxt.checkin.ids[0], choice, by="user" if nxt.action == "ask" else "rule",
                   note="x")
            continue
        if nxt.action == "done":
            break
        assert nxt.action == "work", nxt
        seen.append(nxt.step)
        complete(run, nxt.step)
    assert nxt.action == "done" and "nothing" in nxt.message.lower(), nxt
    assert not set(skipped) & set(seen), seen
    assert state.load(run).spend == {}
    with pytest.raises(ValueError, match="said no"):
        budget.approve(run, {"G6": "ai_usd", "G10": "test", "VB": "voice_credits"}[cid], 1)


def test_a_reject_can_be_changed_while_the_skipped_steps_are_ahead(run):
    _setup(run, "every_step", ["creative_brief", "ai_video"])
    _work_to(run, "D1")
    complete(run, "D1")
    decide(run, "G6", "reject", by="user", note="no")
    decide(run, "G6", "approve", by="user", note="ok after all", change=True)
    assert (flow.next(run).step, flow.next(run).action) == ("D2", "work")


# --- #14, #18 -------------------------------------------------------------------

def test_no_fading_ad_at_just_the_big_calls_ends_through_g1a(run):
    """flow.md A1: at Just the big calls G1 is in the later card, so go straight to G1a."""
    _setup(run, "big_calls", ["creative_brief"])
    _work_to(run, "A1")
    complete(run, "A1")
    decide(run, "G1a", "do_not_refresh", by="rule", note="no fading winner")
    assert flow.next(run).action == "done"


def test_e4_title_is_whole():
    assert next(st for st in flow.steps() if st.id == "E4").title == "Measurement on day 3, 5 and 7"


def test_a_rejected_spending_card_names_only_what_this_run_skips(run, capsys):
    _setup(run, "big_calls", ["creative_brief", "ai_video"])
    _work_to(run, "D1")
    complete(run, "D1")                                       # the spending card is due now
    assert flow.next(run).checkin.card == "approve_spending"
    capsys.readouterr()
    assert _cli(run, "decide", "approve_spending", "reject") == 0
    message = json.loads(capsys.readouterr().out)["message"]
    assert "AI video" in message and "voice" not in message and "live test" not in message
