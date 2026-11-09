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


def test_plan_infeasible_returns_calculation():
    # R4's example: 150/day, 3 ads (2 variants and the control), CPR 45
    p = plan("hook", control(), 2, cfg(150))
    assert p.budget_total == pytest.approx(4050)
    assert p.days == 27 and p.feasible is False
    assert "4050" in p.calculation and "27 days" in p.calculation
    assert str(p.min_events_per_variant) in p.calculation


def test_plan_feasible_when_the_days_fit():
    p = plan("hook", control(), 2, cfg(400))
    assert p.days == 11 and p.feasible is True
    assert p.min_results_per_variant == 30


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


def test_rate_metric_keeps_the_winner_minimum_as_guardrail():
    p = plan("hook", control(), 1, cfg(400))
    assert p.min_results_per_variant == 30
    assert "cost guardrail" in p.calculation


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
    assert p.min_results_per_variant == 30
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


def test_middle_without_options_is_unchanged():
    p = plan("middle", control(), 2, cfg(500))
    assert p.__dict__ == {
        "decision_metric": "thruplay_rate", "min_events_per_variant": 152,
        "min_results_per_variant": 30, "budget_total": 4050.0, "days": 9, "per_day": 500.0,
        "thresholds": {
            "scale": {"metric": "thruplay_rate", "min_relative_improvement": 0.2, "p_below": 0.1,
                      "cpr_at_most": 45.0},
            "kill": {"metric": "thruplay_rate", "worse_with_p_below": 0.1, "cpr_at_least": 58.5},
            "cost_guardrail": {"cpr_at_least": 58.5,
                               "note": "the only reason to switch off before the window ends"},
            "no_verdict": "anything else"},
        "feasible": True,
        "calculation": ("The test needs 152 thruplay rate events per variant (303 trials) to see a "
                        "20% change at 10% significance and 80% power; for this rate metric each "
                        "ad also needs 30 results as the cost guardrail's sample. With 2 variants "
                        "and the control at a cost per result of 45, that is a budget of 4050, "
                        "which at 500 per day takes 9 days, within the 14 allowed."),
        "variants": 2, "trials_per_variant": 303, "control_cpr": 45.0, "secondary_metrics": []}


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
