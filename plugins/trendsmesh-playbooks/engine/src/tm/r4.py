"""R4: the live test's plan, written before the start.

Decision metric by stage: hook -> hook rate, middle -> thruplay rate, promise_cta -> CTR,
fatigue -> cost per result. Other stages are not tested (they end the run or are not creative).

Minimum events per variant (a proposal, awaiting the playbook owner's sign-off): the two-proportion normal
approximation for a relative improvement of `test.min_effect` over the control's rate p1
(p2 = p1 (1 + effect)), two-sided `test.alpha`, power `test.power`:
    n = (z(1 - alpha/2) + z(power))^2 (p1 q1 + p2 q2) / (p2 - p1)^2
n is the number of trials (impressions for hook rate, p25 plays for the thruplay rate, impressions
for CTR and for the results rate behind cost per result); events = ceil(n p1), the successes the
variant must collect. `test.min_events_per_variant` in the config overrides the events.

Budget and time follow from the results each ad must collect:
    budget_total = (variants + 1) * results_per_ad * control CPR;  days = ceil(budget / per_day)
    results_per_ad = winner.min_results                       for rate metrics (hook, thruplay, CTR),
                                                              where it is the cost guardrail's sample
    results_per_ad = max(winner.min_results, min events)      for cost per result, whose events ARE results
(PROPOSAL, awaiting the playbook owner's sign-off: the second line is the controller's ruling for cost per result.)
The plan is infeasible when days > `test.max_days`.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

from tm import cli, config, flow, ladder, manifest, state
from tm.r1 import Window
from tm.r2 import run_config, window_from_json
from tm.runfolder import ReadOnlyError, RunFolder

METRICS = {"hook": "hook_rate", "middle": "thruplay_rate", "promise_cta": "ctr",
           "fatigue": "cost_per_result"}
GUARDRAIL = 1.3  # kill when cost per result reaches 1.3 x the control's


@dataclass
class TestPlan:
    __test__ = False  # not a pytest class
    decision_metric: str
    min_events_per_variant: int
    min_results_per_variant: int
    budget_total: float
    days: int
    per_day: float
    thresholds: dict
    feasible: bool
    calculation: str
    variants: int = 0
    trials_per_variant: int = 0
    control_cpr: float = 0.0
    secondary_metrics: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return dict(self.__dict__)


def _step_rate(step: str, c: Window) -> float:
    """The step's rate in the control, reached clamped to the count it is out of."""
    reached, out_of = ladder.counts(c)[step]
    return min(reached, out_of) / out_of if out_of > 0 else 0.0


def _base_rate(stage: str, c: Window, recut_step: str | None = None,
               shorter: bool = False) -> float:
    if recut_step:
        return _step_rate(recut_step, c)
    if shorter:  # judged by cost per result: the rate behind it, results per impression
        return c.results / c.impressions if c.impressions else 0.0
    if stage == "hook":
        return c.hook_rate
    if stage == "middle":
        return c.middle_rate
    if stage == "promise_cta":
        return c.ctr
    return c.results / c.impressions if c.impressions else 0.0  # fatigue: results per impression


def trials_needed(p1: float, effect: float, alpha: float, power: float) -> int:
    if not 0 < p1 < 1:
        raise ValueError("The control's rate is 0 or 1, so a sample size cannot be worked out.")
    p2 = min(p1 * (1 + effect), 0.999999)
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return math.ceil(z * z * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def plan(stage: str, control: Window, variants: int, cfg: dict | None,
         per_day: float | None = None, max_days: int | None = None, *,
         recut_step: str | None = None, shorter: bool = False) -> TestPlan:
    if stage not in METRICS:
        raise ValueError(f"A {stage} diagnosis has no creative test: R4 plans tests for "
                         f"{', '.join(METRICS)}.")
    if recut_step and shorter:
        raise ValueError("A variant is either shorter or the same length: give --shorter or "
                         "--recut-step, not both.")
    if recut_step and recut_step not in ladder.MIDDLE:
        raise ValueError(f"--recut-step {recut_step} is not a middle step: use one of "
                         f"{', '.join(ladder.MIDDLE)}.")
    if (recut_step or shorter) and stage != "middle":
        raise ValueError(f"--recut-step and --shorter apply to a middle re-cut, not to a {stage} test.")
    if variants < 1:
        raise ValueError("A test needs at least one variant besides the control.")
    if control.results <= 0 or control.spend <= 0:
        raise ValueError("The control has no results in its window, so a cost per result cannot be worked out.")
    get = lambda path: config.value(cfg, path)  # noqa: E731
    per_day = per_day if per_day is not None else get("budget.test_per_day")
    if not per_day or per_day <= 0:
        raise ValueError("The daily test budget (budget.test_per_day) is not set: tell Claude how much per day the test may spend.")
    effect, alpha, power = float(get("test.min_effect")), float(get("test.alpha")), float(get("test.power"))
    min_results = int(get("winner.min_results"))
    if recut_step:
        prev = recut_step.split("/")[1]
        if ladder.counts(control)[recut_step][1] <= 0:
            raise ValueError(f"The control window has no {prev} plays, so a re-cut step cannot be "
                             "tested; build the window from rows with the retention ladder.")
    p1 = _base_rate(stage, control, recut_step, shorter)
    trials = trials_needed(p1, effect, alpha, power)
    override = get("test.min_events_per_variant")
    events = int(override) if override else math.ceil(trials * p1)
    cpr = control.cpr
    # A proposal, awaiting the playbook owner's sign-off: when the decision metric is cost per result, its events are
    # results, so every ad needs at least that many; rate metrics keep winner.min_results.
    events_are_results = stage == "fatigue" or shorter
    per_ad = max(min_results, events) if events_are_results else min_results
    budget = (variants + 1) * per_ad * cpr
    days = math.ceil(budget / per_day - 1e-9)
    max_days = int(max_days if max_days is not None else get("test.max_days"))
    if max_days < 1:
        raise ValueError("The test needs at least 1 day (--max-days).")
    feasible = days <= max_days
    metric = ("cost_per_result" if shorter else f"step:{recut_step}" if recut_step
              else METRICS[stage])
    secondary = ["avg_watch_time"] if shorter else []
    guard = round(GUARDRAIL * cpr, 4)
    thresholds = {
        "scale": {"metric": metric, "min_relative_improvement": effect, "p_below": alpha,
                  "cpr_at_most": round(cpr, 4)},
        "kill": {"metric": metric, "worse_with_p_below": alpha, "cpr_at_least": guard},
        "cost_guardrail": {"cpr_at_least": guard,
                           "note": "the only reason to switch off before the window ends"},
        "no_verdict": "anything else",
    }
    label = (f"{recut_step} step" if recut_step else metric.replace("_", " "))
    prev = recut_step.split("/")[1] if recut_step else None
    calc = (f"The test needs {events} {label} events per variant "
            f"({trials} trials" + (f", counted as {prev} plays" if prev else "") + f") to see a {effect:.0%} change at {alpha:.0%} significance and "
            f"{power:.0%} power; "
            + (f"for cost per result those events are results, so each ad needs {per_ad} results "
               f"(the larger of the {min_results} winner minimum and {events} events)"
               if events_are_results else
               f"for this rate metric each ad also needs {per_ad} results as the cost guardrail's sample")
            + ("; a shorter version mechanically raises completions, so it is judged by cost per "
               "result, with average watch time beside it" if shorter else "")
            + f". With "
            f"{variants} variant{'s' if variants != 1 else ''} and the control at a cost per result of "
            f"{cpr:g}, that is a budget of {budget:g}, which at {per_day:g} per day takes {days} days")
    calc += (f", within the {max_days} allowed." if feasible
             else f", more than the {max_days} days allowed. Raise the daily budget, allow more "
                  "days, test fewer variants, or skip the live test.")
    return TestPlan(decision_metric=metric, min_events_per_variant=events,
                    min_results_per_variant=per_ad, budget_total=round(budget, 2), days=days,
                    per_day=float(per_day), thresholds=thresholds, feasible=feasible,
                    calculation=calc, variants=variants, trials_per_variant=trials,
                    control_cpr=round(cpr, 4), secondary_metrics=secondary)


def record(run: RunFolder, p: TestPlan) -> Path:
    """Keep the plan in run state (the closing step reads `variants`) and as
    04_final/test_plan_calc_vNN.json. A plan that cannot reach the minimum events stops the run
    (the engine holds the live test); a feasible one clears that stop."""
    target = run.next_version("04_final", "test_plan_calc", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(p.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest.record(run, f"04_final/{target.name}", "04_final", "tm r4",
                    params={"variants": p.variants, "per_day": p.per_day})
    s = state.load(run)
    s.test_plan = p.to_json()
    state.save(run, s)
    flow.plan_recorded(run)
    return target


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--stage", required=True, choices=sorted(METRICS))
    p.add_argument("--control", required=True, help="the control's latest window: a JSON file or object")
    p.add_argument("--variants", required=True, type=int, help="variants besides the control")
    p.add_argument("--per-day", type=float, help="daily test budget; default budget.test_per_day")
    p.add_argument("--max-days", type=int, help="the most days the test may run; default test.max_days")
    p.add_argument("--recut-step", help="a same-length middle re-cut: the step it fixes, one of "
                   + ", ".join(ladder.MIDDLE))
    p.add_argument("--shorter", action="store_true",
                   help="a shorter middle re-cut: judged by cost per result")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        text = args.control.strip()
        raw = text if text.startswith("{") else Path(text).read_text(encoding="utf-8")
        p = plan(args.stage, window_from_json(json.loads(raw)), args.variants, run_config(run),
                 args.per_day, args.max_days, recut_step=args.recut_step, shorter=args.shorter)
        target = record(run, p)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))
    if p.feasible:
        cli.emit(args, {"status": "done", "file": f"04_final/{target.name}", **p.to_json()},
                 f"Wrote 04_final/{target.name}. {p.calculation}")
        return 0
    msg = (f"This test cannot collect enough results at this budget. {p.calculation} The run is "
           "stopped: nothing is approved or launched for the live test. Tell the user and ask which "
           "way to go: a higher daily budget (`--per-day`), more days (`--max-days`) or fewer "
           "variants, then run `tm r4` again; or skip the live test (`tm decide G10 reject`). The "
           "run continues from the same place.")
    cli.emit(args, {"status": "stop", "file": f"04_final/{target.name}", "message": msg, **p.to_json()}, msg)
    return 2


cli.register("r4", _setup, _run)
