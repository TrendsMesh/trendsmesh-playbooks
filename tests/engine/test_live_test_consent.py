"""Spending consent in Refresh an ad: the live test is opt-in and its launch always the user's (issue #22),
its budget estimated early (#22), and caption removal's few cents approved at VC (#21)."""

import json
from datetime import date

import pytest
import yaml
from conftest import trend_steps_ready

from tm import budget, checkins, config, flow, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.r2 import window_to_json
from tm.runfolder import RunFolder
from test_flow import _control, _reset, _settle, _to_e3, run  # noqa: F401  (run is a fixture)

BASE = {
    "account": {"id": "12345678", "market": "PL", "language": "Polish"},
    "product": {"name": "Lucid Dreaming", "landing_url": "https://example.com/e-book"},
    "brand": {"assets_dir": "Desktop/Moje reklamy"},
}


@pytest.fixture
def fresh(tmp_path):
    ws = tmp_path / "Moje reklamy"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    trend_steps_ready(r)
    return r


def _cli(r, *args):
    return main([*args, "--run", str(r.path), "--json"])


def _write(r, **answers):
    config.write_from_intake(r, {**BASE, **answers})


# --- #22: the live test is never a default ------------------------------------------------------

def test_default_outputs_leave_the_live_test_out(fresh):
    assert "live_test" not in config.defaults()["outputs"]
    _write(fresh, level="hands_off")                     # "go with the defaults"
    assert state.load(fresh).outputs == ["creative_brief", "edited_video", "ai_video"]
    assert "live_test" not in config.load(fresh)["outputs"]
    assert "test" not in state.load(fresh).budgets


def test_live_test_picked_needs_its_budget_at_every_level(fresh):
    for level in ("every_step", "big_calls", "hands_off"):
        _write(fresh, level=level, outputs=["creative_brief", "live_test"])
        fields = [p.field for p in config.validate(fresh)]
        assert fields == ["budget.test_per_day", "budget.test_days"], level
    _write(fresh, level="every_step", outputs=["creative_brief", "live_test"],
           budget={"test_per_day": 50, "test_days": 7})
    assert config.validate(fresh) == []


def test_an_older_config_with_the_live_test_still_loads(fresh):
    # a 0.9/0.10 config: the live test among its outputs, no test.min_days or test.guardrail_min_results
    _write(fresh, level="big_calls", outputs=["creative_brief", "edited_video", "ai_video", "live_test"],
           budget={"test_per_day": 150, "test_days": 7})
    path = fresh.path / config.FILE
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("min_days", "guardrail_min_results"):
        cfg["test"].pop(key)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    assert config.validate(fresh) == []
    assert state.load(fresh).outputs[-1] == "live_test"
    from tm import r4
    assert r4.plan("hook", _control(), 1, config.load(fresh)).min_days == 4


# --- #22: the launch is always asked ------------------------------------------------------------

def test_launch_is_never_decided_by_rule():
    g11 = checkins.load().checkins["G11"]
    assert set(g11.route.values()) <= {"own", "card"}
    assert "budget in the config" not in g11.rule


def test_hands_off_stops_at_paused_ads_and_asks_the_launch(run):  # noqa: F811
    _reset(run, "hands_off")
    nxt = _to_e3(run)                       # paused ads, a green pre-launch check
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("E3", "ask", ["G11"])
    assert nxt.checkin.choices == ["activate", "keep_paused"]
    with pytest.raises(ValueError, match="ask the user"):
        decide(run, "G11", "activate", by="rule", note="budget in the config, E2b green")
    with pytest.raises(ValueError, match="G11"):
        complete(run, "E3")
    decide(run, "G11", "keep_paused", by="user", note="not now")
    assert flow.next(run).action == "done"
    assert state.load(run).spend.get("test") is None


# --- #22: adding the live test later ------------------------------------------------------------

def _to_the_end(r):
    for _ in range(60):
        nxt = _settle(r)
        if nxt.action != "work":
            return nxt
        complete(r, nxt.step)
    raise AssertionError("never finished")


def test_the_final_report_offers_the_live_test_and_it_can_be_added(fresh):
    _write(fresh, level="every_step", outputs=["creative_brief", "edited_video"])
    done = _to_the_end(fresh)
    assert done.action == "done" and state.load(fresh).status == "done"
    assert "test this against the original" in done.message and "tm live-test add" in done.message
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7") == 0
    s = state.load(fresh)
    assert s.outputs[-1] == "live_test" and s.status == "active" and s.step == "E1"
    b = config.load(fresh)["budget"]
    assert (b["test_per_day"], b["test_days"]) == (40, 7) and config.validate(fresh) == []
    assert "test" not in s.budgets                      # G10 asks for it, then the launch (G11)
    nxt = flow.next(fresh)
    assert (nxt.step, nxt.action) == ("E1", "work")


def test_adding_the_live_test_in_hands_off_approves_the_users_amount(fresh):
    _write(fresh, level="hands_off", outputs=["edited_video"])
    s = state.load(fresh)
    s.step = "C4"
    state.save(fresh, s)
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "5") == 1   # needs their words
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "5",
                "--note", "yes, test it for 5 days at 40 a day") == 0
    s = state.load(fresh)
    assert s.budgets["test"] == 200 and s.approvals[-1]["note"] == "yes, test it for 5 days at 40 a day"
    assert s.step == "C4"                                 # the run goes on from where it was


def test_the_live_test_offer_needs_a_video(fresh):
    _write(fresh, level="every_step", outputs=["creative_brief"])
    done = _to_the_end(fresh)
    assert "tm live-test add" not in done.message
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7") == 1


def test_adding_is_refused_when_the_run_ended_early_or_already_tests(fresh):
    _write(fresh, level="every_step", outputs=["edited_video", "live_test"],
           budget={"test_per_day": 40, "test_days": 7})
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7") == 1
    _write(fresh, level="every_step", outputs=["edited_video"])
    s = state.load(fresh)
    s.status, s.ended = "done", "The diagnosis says this ad should not be refreshed."
    state.save(fresh, s)
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7") == 1


def test_adding_needs_the_landing_page(fresh, capsys):
    _write(fresh, level="every_step", outputs=["edited_video"], product={"name": "E-book"})
    s = state.load(fresh)
    s.step = "C4"
    state.save(fresh, s)
    capsys.readouterr()
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7") == 1
    assert "landing page" in json.loads(capsys.readouterr().out)["message"]
    assert _cli(fresh, "live-test", "add", "--per-day", "40", "--days", "7",
                "--landing-url", "https://example.com/e-book") == 0
    assert config.load(fresh)["product"]["landing_url"] == "https://example.com/e-book"


# --- #22: the test budget estimated early -------------------------------------------------------

def _account_rows(tmp_path):
    rows = [{"date_start": f"2026-10-{d:02d}", "date_stop": f"2026-10-{d + 6:02d}", "spend": 1350,
             "results": 30, "impressions": 100000, "video_p25_watched_actions": 30000,
             "video_thruplay_watched_actions": 15000, "unique_link_clicks_ctr": 1.5, "frequency": 1.5,
             "cpm": 13.5} for d in (1, 8, 15)]
    f = tmp_path / "account.json"
    f.write_text(json.dumps({"data": rows}), encoding="utf-8")
    return f


def _control_file(tmp_path):
    f = tmp_path / "control.json"
    f.write_text(json.dumps(window_to_json(_control())), encoding="utf-8")
    return f


def _picked(fresh, per_day=150, days=7):
    _write(fresh, level="every_step", outputs=["creative_brief", "edited_video", "live_test"],
           budget={"test_per_day": per_day, "test_days": days})


def test_rough_estimate_at_intake_from_the_account(fresh, tmp_path, capsys):
    _picked(fresh, per_day=5)
    capsys.readouterr()
    assert _cli(fresh, "r4", "--estimate", "--account", str(_account_rows(tmp_path))) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["basis"] == "account" and set(out["plans"]) == {"hook", "middle", "promise_cta", "fatigue"}
    s = state.load(fresh)
    assert s.test_estimate["basis"] == "account" and s.test_plan is None
    assert s.status == "active"                          # rough: the ad is not chosen yet
    assert out["plans"]["fatigue"]["feasible"] is False and "fatigue" in out["message"]


def test_estimate_on_the_chosen_ad_stops_an_infeasible_test(fresh, tmp_path):
    _picked(fresh, per_day=1)
    s = state.load(fresh)
    s.step = "A2"                                        # right after "Accept the diagnosis" (G1a)
    state.save(fresh, s)
    ctl = str(_control_file(tmp_path))
    assert _cli(fresh, "r4", "--estimate", "--stage", "hook", "--control", ctl) == 2
    s = state.load(fresh)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == flow.ESTIMATE_STOP
    nxt = flow.next(fresh)
    assert nxt.action == "stop" and "tm live-test budget" in nxt.message and "tm live-test drop" in nxt.message
    with pytest.raises(flow.Held):
        complete(fresh, "A2")
    # a higher daily budget, then the estimate again, clears it
    assert _cli(fresh, "live-test", "budget", "--per-day", "150", "--days", "7") == 0
    assert config.load(fresh)["budget"]["test_per_day"] == 150
    assert _cli(fresh, "r4", "--estimate", "--stage", "hook", "--control", ctl) == 0
    assert state.load(fresh).status == "active" and flow.next(fresh).action != "stop"


def test_skipping_the_test_after_an_infeasible_estimate(fresh, tmp_path):
    _picked(fresh, per_day=1)
    s = state.load(fresh)
    s.step = "A2"
    state.save(fresh, s)
    assert _cli(fresh, "r4", "--estimate", "--stage", "hook", "--control", str(_control_file(tmp_path))) == 2
    assert _cli(fresh, "live-test", "drop", "--note", "skip the test") == 0
    s = state.load(fresh)
    assert "live_test" not in s.outputs and "live_test" not in config.load(fresh)["outputs"]
    assert s.status == "active" and flow.next(fresh).action != "stop"


def test_dropping_or_rebudgeting_is_refused_once_the_plan_is_approved(fresh):
    _picked(fresh)
    s = state.load(fresh)
    s.step = "E2"
    s.decisions.append({"checkin": "G10", "choice": "approve", "by": "user", "at": "2026-11-05T10:00:00+00:00"})
    state.save(fresh, s)
    assert _cli(fresh, "live-test", "budget", "--per-day", "300", "--days", "7") == 1
    assert _cli(fresh, "live-test", "drop") == 1


# --- #21: caption removal approved at VC --------------------------------------------------------

@pytest.fixture
def at_vc(fresh):
    s = state.load(fresh)
    s.level, s.flows, s.outputs, s.step = "every_step", ["V"], ["edited_video", "ai_video"], "VC"
    s.decisions = [{"checkin": "VB", "choice": "approve", "by": "user", "at": "2026-11-05T10:00:00+00:00"}]
    state.save(fresh, s)
    return fresh


def test_caption_removal_is_approved_at_vc_before_g6(at_vc):
    with pytest.raises(ValueError, match="--for VC"):
        budget.approve(at_vc, "ai_usd", 0.15, note="ok, use ProPainter")      # G6 comes later
    budget.approve(at_vc, "ai_usd", 0.15, note="ok, use ProPainter", for_step="VC")
    s = state.load(at_vc)
    assert s.budgets["ai_usd"] == 0.15
    assert s.approvals[-1] == {**s.approvals[-1], "for": "VC", "note": "ok, use ProPainter", "amount": 0.15}
    assert "G6" not in {d["checkin"] for d in s.decisions}      # the AI video's plan is not approved early
    assert budget.spend(at_vc, "ai_usd", 0.15, "ProPainter caption removal") == 0


def test_the_vc_approval_needs_the_users_words_and_the_run_at_vc(at_vc):
    with pytest.raises(ValueError, match="their words"):
        budget.approve(at_vc, "ai_usd", 0.15, for_step="VC")
    with pytest.raises(ValueError, match="ai_usd"):
        budget.approve(at_vc, "voice_credits", 100, note="yes", for_step="VC")
    s = state.load(at_vc)
    s.step = "D1"
    state.save(at_vc, s)
    with pytest.raises(ValueError, match="at VC"):
        budget.approve(at_vc, "ai_usd", 0.15, note="yes", for_step="VC")


def test_g6_later_approves_the_running_total(at_vc):
    budget.approve(at_vc, "ai_usd", 0.15, note="ok", for_step="VC")
    budget.spend(at_vc, "ai_usd", 0.15, "ProPainter caption removal")
    s = state.load(at_vc)
    s.step = "D2"
    s.decisions.append({"checkin": "G6", "choice": "approve", "by": "user", "at": "2026-11-06T10:00:00+00:00"})
    state.save(at_vc, s)
    budget.approve(at_vc, "ai_usd", 5.15)
    assert state.load(at_vc).budgets["ai_usd"] == 5.15


def test_hands_off_vc_uses_the_intake_budget_only(at_vc):
    set_level(at_vc, "hands_off")
    with pytest.raises(ValueError, match="intake"):
        budget.approve(at_vc, "ai_usd", 0.15, note="ok", for_step="VC")


def test_cli_budget_approve_for_vc(at_vc):
    assert _cli(at_vc, "budget", "approve", "ai_usd", "0.15", "--note", "ok") == 1
    assert _cli(at_vc, "budget", "approve", "ai_usd", "0.15", "--note", "ok", "--for", "VC") == 0
