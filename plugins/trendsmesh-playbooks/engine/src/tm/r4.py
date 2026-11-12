"""R4: the live test's plan, written before the start.

Decision metric by stage: hook -> hook rate, middle -> thruplay rate, promise_cta -> CTR,
fatigue -> cost per result. Other stages are not tested (they end the run or are not creative).

Minimum events per variant: the two-proportion normal approximation for a relative improvement
of `test.min_effect` over the control's rate p1 (p2 = p1 (1 + effect)), two-sided `test.alpha`,
power `test.power`:
    n = (z(1 - alpha/2) + z(power))^2 (p1 q1 + p2 q2) / (p2 - p1)^2
n is the number of trials (impressions for hook rate, p25 plays for the thruplay rate, the
previous mark's plays for a re-cut step, impressions for CTR and for the results rate behind cost
per result); events = ceil(n p1), the successes the variant must collect.
`test.min_events_per_variant` in the config overrides the events (the trials are then events / p1).

The decision metric sets the budget (the playbook owner's ruling on issue #23, option C):
    rate metrics (hook, thruplay, CTR, a re-cut step):
        need = (variants + 1) * trials * the control's cost per trial (spend / impressions, or per play)
    cost per result (fatigue, a shorter re-cut), whose events ARE results:
        need = (variants + 1) * max(winner.min_results, events) * control CPR
    days = max(test.min_days, ceil(need / per_day)); the test spends per_day * days.
For a rate metric, cost per result is a guardrail, not a sizing condition: the kill switch at
GUARDRAIL x the control's cost per result is checked once a variant has
`test.guardrail_min_results` results, and a variant that wins on its metric with fewer results is
"won on <metric>; cost per result not confirmed yet" (scale step by step).
The plan is infeasible when days are more than the days allowed: `budget.test_days` when the user
gave it (at most `test.max_days`), else `test.max_days`.

`--estimate` works the plan out early, without making it the test's plan: at the intake from the
account's totals over the history window (every stage, the ad not chosen yet), and right after
the diagnosis (G1a) from the chosen ad's latest window for its target stage. That second estimate,
when it cannot reach the minimum events, stops the run the way an R4 plan does.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

from tm import changes, cli, config, flow, ladder, manifest, state
from tm.r1 import Window, _answer, aggregate, load_ads
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
    spend_total: float = 0.0  # what the test spends: per_day x days, the amount the launch books
    min_days: int = 0  # test.min_days: the shortest run, so delivery settles and weekdays are covered
    basis: str = ""  # what the budget is based on, in words for the plan

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


_TRIAL = {"hook": "impression", "promise_cta": "impression", "middle": "p25 play"}


def _trial_count(stage: str, c: Window, recut_step: str | None) -> tuple[float, str]:
    """A rate metric's trials in the control window, and what one trial is called."""
    if recut_step:
        prev = recut_step.split("/")[1]
        return ladder.counts(c)[recut_step][1], f"{prev} play"
    unit = _TRIAL[stage]
    return (c.p25 if stage == "middle" else c.impressions), unit


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
    guard_min = int(get("test.guardrail_min_results"))
    min_days = int(get("test.min_days"))
    if recut_step:
        prev = recut_step.split("/")[1]
        if ladder.counts(control)[recut_step][1] <= 0:
            raise ValueError(f"The control window has no {prev} plays, so a re-cut step cannot be "
                             "tested; build the window from rows with the retention ladder.")
    p1 = _base_rate(stage, control, recut_step, shorter)
    trials = trials_needed(p1, effect, alpha, power)
    override = get("test.min_events_per_variant")
    events = int(override) if override else math.ceil(trials * p1)
    if override:
        trials = math.ceil(events / p1)
    cpr = control.cpr
    metric = ("cost_per_result" if shorter else f"step:{recut_step}" if recut_step
              else METRICS[stage])
    label = (f"{recut_step} step" if recut_step else metric.replace("_", " "))
    events_are_results = stage == "fatigue" or shorter
    if events_are_results:
        # cost per result: its events are results, so every ad needs at least that many (signed off)
        per_ad = max(min_results, events)
        need = (variants + 1) * per_ad * cpr
        basis = (f"{per_ad} results per ad and the days they take; cost per result is the decision "
                 "metric itself")
    else:
        count, unit = _trial_count(stage, control, recut_step)
        per_trial = control.spend / count
        per_ad = 0
        need = (variants + 1) * trials * per_trial
    if max_days is None:
        max_days = int(get("test.max_days"))
        given = get("budget.test_days")
        if isinstance(given, (int, float)) and not isinstance(given, bool) and given > 0:
            max_days = min(max_days, int(given))
    max_days = int(max_days)
    if max_days < 1:
        raise ValueError("The test needs at least 1 day (--max-days).")
    if min_days > int(get("test.max_days")):
        raise ValueError(f"test.min_days ({min_days}) is more than test.max_days "
                         f"({get('test.max_days')}): a test cannot run that long. Lower test.min_days.")
    need_days = max(1, math.ceil(need / per_day - 1e-9))
    days = max(min_days, need_days)
    feasible = days <= max_days
    spend = round(per_day * days, 2)
    secondary = ["avg_watch_time"] if shorter else []
    guard = round(GUARDRAIL * cpr, 4)
    thresholds = {
        "scale": {"metric": metric, "min_relative_improvement": effect, "p_below": alpha,
                  "cpr_at_most": round(cpr, 4)},
        "kill": {"metric": metric, "worse_with_p_below": alpha, "cpr_at_least": guard},
        "cost_guardrail": {"cpr_at_least": guard, "min_results": guard_min,
                           "note": f"checked once a variant has at least {guard_min} results; the only "
                                   "reason to switch off before the window ends"},
    }
    if not events_are_results:
        thresholds["cost_not_confirmed"] = {
            "results_below": guard_min,
            "verdict": f"won on {label}; cost per result not confirmed yet",
            "action": "scale step by step and watch cost per result"}
    thresholds["no_verdict"] = "anything else"
    prev = recut_step.split("/")[1] if recut_step else None
    counted = f", counted as {prev} plays" if prev else (", counted as p25 plays" if stage == "middle"
                                                          and not shorter else "")
    calc = (f"The test needs {events} {label} events per variant ({trials} trials{counted}) to see a "
            f"{effect:.0%} change at {alpha:.0%} significance and {power:.0%} power")
    many = f"{variants} variant{'s' if variants != 1 else ''} and the control"
    if events_are_results:
        calc += (f"; for cost per result those events are results, so each ad needs {per_ad} results "
                 f"(the larger of the {min_results} winner minimum and {events} events)"
                 + ("; a shorter version mechanically raises completions, so it is judged by cost per "
                    "result, with average watch time beside it" if shorter else "")
                 + f". With {many} at a cost per result of {cpr:g}, that is {round(need, 2):g}")
    else:
        basis = (f"the {label}'s {trials} {unit}s per variant and {days} days; cost per result is "
                 "watched as a guardrail")
        calc += (f". At the control's cost per {unit} of {per_trial:.4g}, {many} need {round(need, 2):g} for "
                 "those trials")
    calc += f", which at {per_day:g} per day takes {need_days} day{'s' if need_days != 1 else ''}"
    if days > need_days:
        calc += f"; the test runs at least the {min_days}-day minimum, so {days} days"
    if feasible:
        calc += (f", within the {max_days} allowed, and spends {spend:g} ({per_day:g} per day for "
                 f"{days} days). The budget covers {basis}")
        if not events_are_results:
            calc += (f" (switch off at {guard:g}, 1.3 times the control's {cpr:g}), checked once a "
                     f"variant has {guard_min} results")
        calc += "."
    else:
        calc += (f", more than the {max_days} days allowed. Raise the daily budget, allow more "
                 "days, test fewer variants, or skip the live test.")
    return TestPlan(decision_metric=metric, min_events_per_variant=events,
                    min_results_per_variant=per_ad, budget_total=round(need, 2), days=days,
                    per_day=float(per_day), thresholds=thresholds, feasible=feasible,
                    calculation=calc, variants=variants, trials_per_variant=trials,
                    control_cpr=round(cpr, 4), secondary_metrics=secondary,
                    spend_total=spend, min_days=min_days, basis=basis)


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


def account_window(files: list[str]) -> Window:
    """The account's totals over its rows (A1's account-level answer over the history window): the
    rough control of an estimate made before the ad is chosen."""
    rows = [r for f in files for rs in load_ads(_answer(f)).values() for r in rs]
    if not rows:
        raise ValueError("The account file has no rows: save the account-level answer over the history "
                         "window (`ads_get_ad_entities`, level account) and pass that file.")
    return aggregate(rows, min(r.stop for r in rows), max(r.stop for r in rows))


def estimate(run: RunFolder, control: Window, variants: int, cfg: dict | None, stage: str | None = None,
             per_day: float | None = None, max_days: int | None = None, *,
             recut_step: str | None = None, shorter: bool = False) -> dict:
    """R4 worked out early (issue #22), kept in run state as `test_estimate` and as
    03_wip/test_estimate_vNN.json; never the test's plan. Without `stage` (the intake: the account's
    totals, the ad not chosen yet) every testable stage is worked out and nothing stops; with it (right
    after G1a: the chosen ad's latest window) an estimate that cannot reach the minimum events stops the
    run until the budget, the days or the live test change (`flow.estimate_recorded`)."""
    stages = [stage] if stage else list(METRICS)
    plans: dict[str, dict] = {}
    for st in stages:
        try:
            plans[st] = plan(st, control, variants, cfg, per_day, max_days, recut_step=recut_step,
                             shorter=shorter).to_json()
        except ValueError as exc:
            if stage:
                raise
            plans[st] = {"feasible": False, "error": str(exc)}
    feasible = all(p.get("feasible") for p in plans.values())
    if stage:
        calc = plans[stage]["calculation"]
    else:
        calc = " ".join(f"Testing {changes.STAGES[st]}: {p.get('calculation') or p['error']}"
                        for st, p in plans.items())
    s = state.load(run)
    est = {"basis": "ad" if stage else "account", "stage": stage, "variants": variants,
           "feasible": feasible, "calculation": calc, "plans": plans, "at": flow._now(), "at_step": s.step}
    target = run.next_version("03_wip", "test_estimate", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(est, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest.record(run, f"03_wip/{target.name}", "03_wip", "tm r4 --estimate",
                    params={"variants": variants, "stage": stage or "every stage"})
    s = state.load(run)
    s.test_estimate = est
    state.save(run, s)
    flow.estimate_recorded(run)
    return {**est, "file": f"03_wip/{target.name}"}


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--stage", choices=sorted(METRICS),
                   help="the diagnosis' target stage; with --estimate it may be left out (the intake: every stage)")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--control", help="the control's latest window: a JSON file or object")
    source.add_argument("--account", nargs="+",
                        help="with --estimate at the intake: the account-level rows over the history window "
                             "(raw Meta answers), summed into the rough control")
    p.add_argument("--variants", type=int, help="variants besides the control (with --estimate, default 1)")
    p.add_argument("--estimate", action="store_true",
                   help="work the plan out early (the intake, right after G1a); it is not the test's plan")
    p.add_argument("--per-day", type=float, help="daily test budget; default budget.test_per_day")
    p.add_argument("--max-days", type=int,
                   help="the most days the test may run; default budget.test_days (at most test.max_days), "
                        "else test.max_days")
    p.add_argument("--recut-step", help="a same-length middle re-cut: the step it fixes, one of "
                   + ", ".join(ladder.MIDDLE))
    p.add_argument("--shorter", action="store_true",
                   help="a shorter middle re-cut: judged by cost per result")
    p.add_argument("--json", action="store_true")


def _control(args: argparse.Namespace, run: RunFolder) -> Window:
    if args.account:
        return account_window([str(run.given(f)) for f in args.account])   # run-relative, whatever the cwd
    text = args.control.strip()
    raw = text if text.startswith("{") else run.given(text).read_text(encoding="utf-8")
    return window_from_json(json.loads(raw))


def _run_estimate(args: argparse.Namespace, run: RunFolder) -> int:
    est = estimate(run, _control(args, run), args.variants or 1, run_config(run), args.stage, args.per_day,
                   args.max_days, recut_step=args.recut_step, shorter=args.shorter)
    s = state.load(run)
    held = any(x["reason_id"] == flow.ESTIMATE_STOP and "resumed_at" not in x for x in s.stops)
    if held:
        msg = (f"This test cannot collect enough results at the budget the user gave. {est['calculation']} The "
               "run is stopped here, at the start, before the work for the test is done. Tell the user and ask "
               "which way to go: a higher daily budget or more days (`tm live-test budget --run R --per-day "
               "<amount> --days <days>`, then `tm r4 --estimate` again), or skip the live test (`tm live-test "
               "drop --run R`). The other outputs are not affected; the run continues from the same place.")
        cli.emit(args, {"status": "stop", "message": msg, **est}, msg)
        return 2
    if est["basis"] == "account":
        short = [st for st, p in est["plans"].items() if not p.get("feasible")]
        msg = (f"Wrote {est['file']}: a rough estimate from the account's numbers (the ad is not chosen yet). "
               f"{est['calculation']} Tell the user what the test needs per kind of change"
               + (f"; at this budget it cannot test {', '.join(changes.STAGES[st] + f' ({st})' for st in short)}"
                  if short else "")
               + ". It is worked out again on the chosen ad's numbers right after the diagnosis.")
    else:
        msg = f"Wrote {est['file']}. {est['calculation']}"
    cli.emit(args, {"status": "done", "message": msg, **est}, msg)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.estimate:
            return _run_estimate(args, run)
        if not args.stage or args.control is None or args.variants is None:
            raise ValueError("The test plan needs --stage, --control and --variants (only --estimate works "
                             "from the account's rows).")
        p = plan(args.stage, _control(args, run), args.variants, run_config(run),
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
