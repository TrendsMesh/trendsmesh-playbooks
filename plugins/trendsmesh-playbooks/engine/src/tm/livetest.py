"""`tm live-test`: the live test of a Refresh an ad run after the intake (issue #22).

The live test is the one output that spends ad money and publishes ads, so it is never a default: the user
picks it by name, with their own daily budget and days. Once A0 is done the config is fixed, so these three
changes go through here, each on the user's word:

- `add`: the user said yes to "Do you want to test this against the original?" (the final report offers it
  when the run made a video without a test). The live test joins the outputs with its budget, and a run that
  had finished reopens at the test design (E1). At Hands-off their words approve the test budget, as the
  intake's would; at the other levels the test plan (G10) asks for it. The launch (G11) is always asked.
- `budget`: a higher daily budget or more days, the way out of an estimate that cannot reach the minimum
  events (`tm r4 --estimate`); refused once the test plan is approved (G10) or the spend is booked.
- `drop`: skip the live test before its design (E1) is done; afterwards, G10 `reject` skips it.
- `move check|approve|decline|record|report`: after G12 `scale`, the winning ad into the original's campaign, in a
  new ad set, PAUSED, on the user's yes (issue #64, `tm.livetest_move`).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tm import budget, cli, config, flow, state
from tm.runfolder import RunFolder
from tm.stops import Stop

LIVE_TEST = "live_test"


def _positive(per_day: float, days: int) -> None:
    if not (per_day and per_day > 0) or not (isinstance(days, int) and days >= 1):
        raise ValueError("Give the daily budget (above 0) and the number of days (1 or more) the user chose; no "
                         "amount is assumed.")


def _hands_off_yes(s: state.RunState, note: str | None) -> None:
    if s.level == "hands_off" and not (note and note.strip()):
        raise ValueError("At Hands-off the user's words are the yes to this budget: pass them with "
                         "`--note \"<their words>\"`.")


def _approve(run: RunFolder, s: state.RunState, per_day: float, days: int, note: str | None) -> None:
    if s.level == "hands_off":
        budget.approve_from_intake(run, "test", round(per_day * days, 6), note.strip())


def add(run: RunFolder, per_day: float, days: int, *, landing_url: str | None = None,
        note: str | None = None) -> state.RunState:
    s = state.load(run)
    gap = flow.live_test_gap(s)
    if gap:
        raise ValueError(gap)
    if s.step in (None, "A0"):
        raise ValueError("The intake is not done yet: add the live test to the intake answers instead, with its "
                         "daily budget and days, and write the config again.")
    _positive(per_day, days)
    _hands_off_yes(s, note)
    cfg = config.load(run)
    product = cfg.setdefault("product", {})
    if landing_url:
        product["landing_url"] = landing_url
    if not (product.get("landing_url") or "").strip():
        raise ValueError("The live test needs the product's landing page link: ask the user and pass it with "
                         "`--landing-url`.")
    cfg["outputs"] = [*cfg.get("outputs", []), LIVE_TEST]
    cfg.setdefault("budget", {}).update(test_per_day=per_day, test_days=days)
    config.save(run, cfg)
    s.outputs = [*s.outputs, LIVE_TEST]
    if s.step == flow.END:
        s.step = flow.DESIGN_STEP          # every other step is done: the test design comes next
    if s.status == "done":
        s.status = "active"
    state.save(run, s)
    _approve(run, s, per_day, days, note)
    return state.load(run)


def _before_plan_yes(s: state.RunState, what: str) -> None:
    if not flow._pb01(s) or LIVE_TEST not in s.outputs:
        raise ValueError("The live test is not part of this run.")
    if any(d.get("checkin") == flow.SPENDING_CHECKIN["test"] for d in s.decisions) or s.spend.get("test"):
        raise ValueError(f"The test plan is already decided (G10), so {what} goes through it: change it with "
                         "`tm decide G10 <choice> --change`, then approve the amount with `tm budget approve`.")


def set_budget(run: RunFolder, per_day: float, days: int, note: str | None = None) -> state.RunState:
    s = state.load(run)
    _before_plan_yes(s, "a new budget")
    _positive(per_day, days)
    _hands_off_yes(s, note)
    cfg = config.load(run)
    cfg.setdefault("budget", {}).update(test_per_day=per_day, test_days=days)
    config.save(run, cfg)
    _approve(run, s, per_day, days, note)
    return state.load(run)


def drop(run: RunFolder) -> state.RunState:
    s = state.load(run)
    _before_plan_yes(s, "skipping the test")
    order = [st.id for st in flow.steps()]
    at = len(order) if s.step == flow.END else (order.index(s.step) if s.step in order else 0)
    if at > order.index(flow.DESIGN_STEP):
        raise ValueError("The test design (E1) is done, so the live test is skipped with `tm decide G10 reject`.")
    if s.outputs == [LIVE_TEST]:
        raise ValueError("The live test is this run's only output, so there is nothing left to make without it. "
                         "Start a new run for the outputs the user wants instead.")
    cfg = config.load(run)
    cfg["outputs"] = [o for o in cfg.get("outputs", []) if o != LIVE_TEST]
    config.save(run, cfg)
    s.outputs = [o for o in s.outputs if o != LIVE_TEST]
    if not s.spend.get("test"):
        s.budgets.pop("test", None)
    state.save(run, s)
    flow.estimate_recorded(run)          # an estimate stop for the test is gone with it
    return state.load(run)


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("add", help="add the live test after the intake, with the user's daily budget and days")
    b = sub.add_parser("budget", help="a new daily budget or number of days, before the test plan is approved")
    d = sub.add_parser("drop", help="skip the live test before its design (E1) is done")
    mv = sub.add_parser("move", help="after G12 scale: the winning ad into the original's campaign, PAUSED")
    mv.add_argument("move_action", choices=["check", "approve", "decline", "record", "report"])
    mv.add_argument("--file", help="the proposal (check) or the objects read back (record)")
    mv.add_argument("--run", required=True, help="the run folder")
    mv.add_argument("--note", help="the user's own words (approve, decline)")
    mv.add_argument("--json", action="store_true")
    for sp in (a, b):
        sp.add_argument("--per-day", type=float, required=True, help="the daily test budget the user gave")
        sp.add_argument("--days", type=int, required=True, help="the number of days the user gave")
    a.add_argument("--landing-url", help="the link the ads point to, when the config lacks it")
    for sp in (a, b, d):
        sp.add_argument("--note", help="the user's own words (required in Hands-off, where they approve the budget)")
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.action == "move":
            return _move(args, run)
        if args.action == "add":
            s = add(run, args.per_day, args.days, landing_url=args.landing_url, note=args.note)
            text = (f"The live test is added: {args.per_day:g} per day for {args.days} days. Run `tm next`: the "
                    "test design (E1) comes after the run's other steps; the plan and the launch are asked.")
        elif args.action == "budget":
            s = set_budget(run, args.per_day, args.days, note=args.note)
            text = (f"The live test's budget is now {args.per_day:g} per day for {args.days} days. Estimate it "
                    "again with `tm r4 --estimate` (or plan it with `tm r4` at E1), then `tm next`.")
        else:
            s = drop(run)
            text = "The live test is skipped: nothing goes live and nothing is spent on ads. Run `tm next`."
        cli.emit(args, {"status": "done", "outputs": s.outputs, "step": s.step, "run_status": s.status,
                        "budget": {"test_per_day": getattr(args, "per_day", None),
                                   "test_days": getattr(args, "days", None)}}, text)
        return 0
    except Stop as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


def _move(args: argparse.Namespace, run: RunFolder) -> int:
    from tm import livetest_move as mv
    action = args.move_action
    if action in ("check", "record") and not args.file:
        raise ValueError(f"tm live-test move {action} needs --file.")
    if action == "check":
        rel, problems = mv.check(run, args.file)
        if problems:
            return cli.refuse_problems(args, rel, problems)
        card = mv.card(run)
        cli.emit(args, {"status": "done", "file": rel, "card": card, "language_warning": card["language_warning"]},
                 f"{rel} passed the check. Show the user the proposal in full and ask for their yes; nothing is "
                 "created before it." + (f" {card['language_warning']}" if card["language_warning"] else ""))
        return 0
    if action == "approve":
        rel = mv.approve(run, args.note)
        cli.emit(args, {"status": "done", "file": rel},
                 f"Recorded the user's yes to {rel}. Create the ad set and the ad PAUSED, read them back with the "
                 "preview, then tm live-test move record.")
        return 0
    if action == "decline":
        mv.decline(run, args.note)
        cli.emit(args, {"status": "done"}, "Recorded the user's no: nothing is created in Meta.")
        return 0
    if action == "record":
        rel, problems = mv.record(run, args.file)
        if problems:
            return cli.refuse_problems(args, rel, problems)
        out = mv.report(run)
        cli.emit(args, {"status": "done", "file": rel, **out}, out["text"])
        return 0
    out = mv.report(run)
    cli.emit(args, {"status": "done", **out}, out["text"])
    return 0


cli.register("live-test", _setup, _run)
