"""R4: the test plan's decision metric, minimum events, budget, days and thresholds."""

import math
from datetime import date
from statistics import NormalDist

import pytest

from tm import config
from tm.r1 import Window
from tm.r4 import plan

CFG = config.defaults()


def control(results=30, spend=1350.0):
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=spend, results=results,
                  impressions=100_000, p25=30_000, thruplay=15_000, clicks_est=1_500,
                  frequency=1.5, cpm=20.0, weeks=1)


def cfg(per_day):
    c = config.defaults()
    c["budget"]["test_per_day"] = per_day
    return c


def _hook_need(variants=2):
    """What a hook test's trials cost at the control's cost per impression (1350 / 100,000)."""
    z = NormalDist().inv_cdf(0.95) + NormalDist().inv_cdf(0.8)
    trials = math.ceil(z * z * (0.3 * 0.7 + 0.36 * 0.64) / 0.06 ** 2)
    return trials, (variants + 1) * trials * 1350 / 100_000


def test_rate_metric_budget_comes_from_its_trials():
    # issue #23 (option C): a hook test is sized by its impressions, not by 30 results per ad
    trials, need = _hook_need()
    p = plan("hook", control(), 2, cfg(150))
    assert p.trials_per_variant == trials
    assert p.budget_total == pytest.approx(need, abs=0.01)
    assert p.days == 4 and p.feasible is True          # one day of delivery, the 4-day minimum
    assert p.spend_total == pytest.approx(600)          # what the test spends: 150 a day for 4 days
    assert p.min_results_per_variant == 0               # no results quota for a rate metric
    assert f"{trials} impressions per variant and 4 days" in p.basis
    assert "cost per result is watched as a guardrail" in p.basis
    assert p.basis in p.calculation


def test_rate_metric_plan_infeasible_returns_calculation():
    _, need = _hook_need()
    p = plan("hook", control(), 2, cfg(1))
    assert p.days == math.ceil(need) and p.feasible is False
    assert f"{p.days} days" in p.calculation and "more than the 14 days allowed" in p.calculation
    assert str(p.min_events_per_variant) in p.calculation


def test_min_days_is_the_floor_and_comes_from_the_config():
    c = cfg(150)
    c["test"]["min_days"] = 6
    assert plan("hook", control(), 2, c).days == 6
    c["test"]["min_days"] = 20
    with pytest.raises(ValueError, match="min_days"):
        plan("hook", control(), 2, c)                   # longer than the test may run


def test_the_users_days_cap_the_plan():
    c = cfg(1)
    c["budget"]["test_days"] = 40
    assert plan("hook", control(), 2, c).feasible is False   # test.max_days (14) still caps it
    c = cfg(150)
    c["budget"]["test_days"] = 3
    p = plan("hook", control(), 2, c)
    assert p.days == 4 and p.feasible is False               # the 4-day minimum is more than the 3 given
    assert "more than the 3 days allowed" in p.calculation


def test_plan_feasible_when_the_days_fit():
    p = plan("hook", control(), 2, cfg(400))
    assert p.days == 4 and p.feasible is True


def test_signed_off_note_is_gone():
    import tm.r4
    assert "sign-off" not in (tm.r4.__doc__ or "") and "PROPOSAL" not in (tm.r4.__doc__ or "")


def test_decision_metric_follows_the_stage():
    names = {s: plan(s, control(), 1, cfg(500)).decision_metric
             for s in ("hook", "middle", "promise_cta", "fatigue")}
    assert names == {"hook": "hook_rate", "middle": "thruplay_rate", "promise_cta": "ctr",
                     "fatigue": "cost_per_result"}


def test_stages_without_a_test_are_refused():
    with pytest.raises(ValueError, match="landing"):
        plan("landing", control(), 1, cfg(500))


def test_min_events_from_two_proportion_approximation():
    p = plan("hook", control(), 2, cfg(400))
    # p1=0.30, p2=0.36, alpha 0.10 two-sided, power 0.80
    z = 1.6448536 + 0.8416212
    n = z * z * (0.3 * 0.7 + 0.36 * 0.64) / 0.06 ** 2
    assert p.trials_per_variant == math.ceil(n)
    assert p.min_events_per_variant == math.ceil(math.ceil(n) * 0.30)


def test_stricter_alpha_needs_more_events():
    loose = plan("hook", control(), 2, cfg(400))
    c = cfg(400)
    c["test"]["alpha"] = 0.01
    assert plan("hook", control(), 2, c).min_events_per_variant > loose.min_events_per_variant


def test_thresholds_written_before_the_start():
    t = plan("hook", control(), 2, cfg(400)).thresholds
    assert t["scale"]["min_relative_improvement"] == 0.20 and t["scale"]["p_below"] == 0.10
    assert t["scale"]["cpr_at_most"] == pytest.approx(45.0)
    assert t["kill"]["cpr_at_least"] == pytest.approx(58.5)
    assert t["cost_guardrail"]["cpr_at_least"] == pytest.approx(58.5)
    assert t["cost_guardrail"]["min_results"] == 10
    assert t["cost_not_confirmed"] == {
        "results_below": 10, "verdict": "won on hook rate; cost per result not confirmed yet",
        "action": "scale step by step and watch cost per result"}


def test_guardrail_min_results_comes_from_the_config():
    c = cfg(400)
    c["test"]["guardrail_min_results"] = 25
    t = plan("hook", control(), 2, c).thresholds
    assert t["cost_guardrail"]["min_results"] == 25 and t["cost_not_confirmed"]["results_below"] == 25
    assert "won on cost per result" not in str(plan("fatigue", control(), 1, cfg(400)).thresholds)
    assert "cost_not_confirmed" not in plan("fatigue", control(), 1, cfg(400)).thresholds


def test_control_without_results_cannot_be_costed():
    with pytest.raises(ValueError, match="results"):
        plan("hook", control(results=0), 2, cfg(400))


def test_daily_budget_is_required():
    with pytest.raises(ValueError, match="per day"):
        plan("hook", control(), 2, config.defaults())


def test_config_override_of_min_events():
    c = cfg(400)
    c["test"]["min_events_per_variant"] = 500
    assert plan("hook", control(), 2, c).min_events_per_variant == 500


def test_fatigue_events_are_results_and_make_the_plan_infeasible():
    # cost per result: the events are results, so each ad needs max(30, events) results
    p = plan("fatigue", control(), 1, cfg(400))
    assert p.min_results_per_variant == max(30, p.min_events_per_variant) > 30
    assert p.budget_total == pytest.approx(2 * p.min_results_per_variant * 45)
    assert p.feasible is False
    assert "those events are results" in p.calculation


def test_rate_metric_no_longer_needs_the_winner_minimum():
    # winner.min_results keeps its R1 meaning: it does not size a rate metric's test
    c = cfg(400)
    c["winner"]["min_results"] = 300
    assert plan("hook", control(), 1, c).budget_total == plan("hook", control(), 1, cfg(400)).budget_total
    assert "guardrail" in plan("hook", control(), 1, cfg(400)).calculation


def test_override_of_min_events_sets_the_trials():
    c = cfg(400)
    c["test"]["min_events_per_variant"] = 600
    p = plan("hook", control(), 1, c)
    assert p.trials_per_variant == 2000                 # 600 events at the control's 30% hook rate


def ladder_control(**kw):
    c = control()
    return Window(**{**c.__dict__, "plays": 50_000, "p50": 20_000, "p75": 10_000, "p95": 4_000,
                     "p100": 2_000, "avg_time_s": 9.0, **kw})


def test_shorter_version_is_judged_by_cost_per_result():
    p = plan("middle", ladder_control(), 1, cfg(400), shorter=True)
    assert p.decision_metric == "cost_per_result"
    assert p.secondary_metrics == ["avg_watch_time"]
    assert p.min_results_per_variant == max(30, p.min_events_per_variant)
    assert "those events are results" in p.calculation
    assert ("a shorter version mechanically raises completions, so it is judged by cost per "
            "result, with average watch time beside it") in p.calculation
    assert p.to_json()["secondary_metrics"] == ["avg_watch_time"]


def test_same_length_recut_is_judged_by_its_step():
    p = plan("middle", ladder_control(), 2, cfg(500), recut_step="p75/p50")
    assert p.decision_metric == "step:p75/p50"
    assert p.secondary_metrics == []
    # the step's rate in the control is 10000 / 20000
    assert p.trials_per_variant == math.ceil(
        (NormalDist().inv_cdf(0.95) + NormalDist().inv_cdf(0.8)) ** 2
        * (0.25 + 0.6 * 0.4) / (0.1) ** 2)
    assert p.min_events_per_variant == math.ceil(p.trials_per_variant * 0.5)
    assert p.min_results_per_variant == 0
    # the trials are p50 plays, at the control's cost per p50 play (1350 / 20,000)
    assert p.budget_total == pytest.approx(3 * p.trials_per_variant * 1350 / 20_000, abs=0.01)
    assert "p50 play" in p.basis
    assert p.thresholds["scale"]["metric"] == "step:p75/p50"
    assert p.thresholds["cost_guardrail"]["cpr_at_least"] == pytest.approx(58.5)
    assert "p50" in p.calculation


def test_out_of_order_counts_are_clamped():
    # more reached p75 than p50: the rate is clamped to 1, which no sample size can work out
    with pytest.raises(ValueError, match="0 or 1"):
        plan("middle", ladder_control(p75=30_000), 1, cfg(500), recut_step="p75/p50")
    with pytest.raises(ValueError, match="no p50 plays"):
        plan("middle", ladder_control(p50=0, p75=0), 1, cfg(500), recut_step="p75/p50")


def test_shorter_and_step_together_refused():
    with pytest.raises(ValueError, match="either shorter or the same length"):
        plan("middle", ladder_control(), 1, cfg(500), recut_step="p75/p50", shorter=True)


def test_recut_options_need_the_middle_stage_and_a_known_step():
    with pytest.raises(ValueError, match="p50/p25, p75/p50, p95/p75"):
        plan("middle", ladder_control(), 1, cfg(500), recut_step="p100/p95")
    with pytest.raises(ValueError, match="middle"):
        plan("hook", ladder_control(), 1, cfg(500), recut_step="p75/p50")
    with pytest.raises(ValueError, match="middle"):
        plan("fatigue", ladder_control(), 1, cfg(500), shorter=True)


def test_middle_is_sized_from_p25_plays():
    p = plan("middle", control(), 2, cfg(500))
    need = 3 * 303 * 1350 / 30_000           # 303 p25 plays per ad at the control's cost per p25 play
    assert p.__dict__ == {
        "decision_metric": "thruplay_rate", "min_events_per_variant": 152,
        "min_results_per_variant": 0, "budget_total": round(need, 2), "days": 4, "per_day": 500.0,
        "thresholds": {
            "scale": {"metric": "thruplay_rate", "min_relative_improvement": 0.2, "p_below": 0.1,
                      "cpr_at_most": 45.0},
            "kill": {"metric": "thruplay_rate", "worse_with_p_below": 0.1, "cpr_at_least": 58.5},
            "cost_guardrail": {"cpr_at_least": 58.5, "min_results": 10,
                               "note": "checked once a variant has at least 10 results; the only "
                                       "reason to switch off before the window ends"},
            "cost_not_confirmed": {"results_below": 10,
                                   "verdict": "won on thruplay rate; cost per result not confirmed yet",
                                   "action": "scale step by step and watch cost per result"},
            "no_verdict": "anything else"},
        "feasible": True,
        "calculation": (
            "The test needs 152 thruplay rate events per variant (303 trials, counted as p25 plays) "
            "to see a 20% change at 10% significance and 80% power. At the control's cost per p25 "
            "play of 0.045, 2 variants and the control need 40.91 for those trials, which at 500 per "
            "day takes 1 day; the test runs at least the 4-day minimum, so 4 days, within the 14 "
            "allowed, and spends 2000 (500 per day for 4 days). The budget covers the thruplay "
            "rate's 303 p25 plays per variant and 4 days; cost per result is watched as a "
            "guardrail (switch off at 58.5, 1.3 times the control's 45), checked once a variant "
            "has 10 results."),
        "variants": 2, "trials_per_variant": 303, "control_cpr": 45.0, "secondary_metrics": [],
        "spend_total": 2000.0, "min_days": 4,
        "basis": ("the thruplay rate's 303 p25 plays per variant and 4 days; cost per result is "
                  "watched as a guardrail")}


def test_shorter_is_sized_from_results_like_fatigue():
    ctl = ladder_control(thruplay=0)  # a ThruPlay rate of 0 must not matter
    a = plan("middle", ctl, 1, cfg(400), shorter=True)
    b = plan("fatigue", ctl, 1, cfg(400))
    for f in ("min_events_per_variant", "trials_per_variant", "min_results_per_variant", "budget_total"):
        assert getattr(a, f) == getattr(b, f)


def test_recut_step_without_the_ladder_says_so():
    with pytest.raises(ValueError, match="no p50 plays, so a re-cut step cannot be tested; "
                                         "build the window from rows with the retention ladder"):
        plan("middle", control(), 1, cfg(500), recut_step="p75/p50")
    with pytest.raises(ValueError, match="no p25 plays"):
        plan("middle", ladder_control(p25=0), 1, cfg(500), recut_step="p50/p25")


def _cli_plan(tmp_path, *extra):
    import json
    from tm.cli import main
    from tm.r2 import window_to_json
    from tm.runfolder import RunFolder
    ws = tmp_path / "Moje reklamy"
    ws.mkdir()
    run = RunFolder.create(ws, "Ad", date(2026, 11, 6))
    ctl = json.dumps(window_to_json(ladder_control()))
    code = main(["r4", "--run", str(run.path), "--stage", "middle", "--control", ctl,
                 "--variants", "1", "--per-day", "5000", "--json", *extra])
    return code, json.loads((run.path / "04_final" / "test_plan_calc_v01.json").read_text(encoding="utf-8"))


def test_cli_shorter_records_the_secondary_metric(tmp_path):
    code, rec = _cli_plan(tmp_path, "--shorter")
    assert code == 0 and rec["secondary_metrics"] == ["avg_watch_time"]
    assert rec["decision_metric"] == "cost_per_result"


def test_cli_recut_step_records_the_step_metric(tmp_path):
    code, rec = _cli_plan(tmp_path, "--recut-step", "p75/p50")
    assert code == 0 and rec["decision_metric"] == "step:p75/p50" and rec["secondary_metrics"] == []
