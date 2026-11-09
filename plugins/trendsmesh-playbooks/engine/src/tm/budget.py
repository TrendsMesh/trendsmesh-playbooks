"""Budgets that guard every paid step.

Three kinds, each with its own approved amount in run.json (`budgets`) and its own running
total (`spend`):

- `ai_usd`: Replicate (image and video generation, ProPainter caption removal), in US dollars;
- `voice_credits`: ElevenLabs (Voice Isolator, the clone, new takes), in credits;
- `test`: Meta spend for the live test, `budget.test_per_day` x `budget.test_days`.

`approve` records what the user accepted, and only after their yes (`flow.approval_gap`): the
spending check-in's answer, a stop that asked them for the budget, or their own words when no
check-in asks for it. Hands-off's intake budgets are approved by the intake (`approve_from_intake`).
`spend` records money as it is spent and refuses what would go over. Both refuse while the run is
stopped for another reason (`flow.Held`, exit 2): nothing is spent or approved then.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from tm import cli, flow, state
from tm.runfolder import RunFolder

Kind = Literal["ai_usd", "voice_credits", "test"]

_WORDS = {
    "ai_usd": ("USD", "Replicate (AI image and video generation)"),
    "voice_credits": ("ElevenLabs credits", "ElevenLabs (the voice)"),
    "test": ("in the ad account's currency", "Meta (the live test's ad spend)"),
}


@dataclass(frozen=True)
class Estimate:
    kind: str
    amount: float
    what: str
    unit: str
    text: str


def _kind(kind: str) -> str:
    if kind not in flow.BUDGET_KINDS:
        raise ValueError(f"{kind!r} is not a budget kind. Pick one of: {', '.join(flow.BUDGET_KINDS)}.")
    return kind


def _amount(amount: float, *, allow_zero: bool = False) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"{amount!r} is not an amount.") from None
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"The amount must be above zero, not {amount!r} (negative amounts are not allowed).")
    return round(value, 6)


def _fmt(kind: str, value: float) -> str:
    unit = _WORDS[kind][0]
    return f"{value:g} {unit}" if kind != "test" else f"{value:g} ({unit})"


def estimate(kind: Kind, amount: float, what: str) -> Estimate:
    """Words for the user before anything is approved. Changes nothing."""
    _kind(kind)
    value = _amount(amount, allow_zero=True)
    unit, service = _WORDS[kind]
    text = (f"About {_fmt(kind, value)} on {service} for: {what}. "
            "Nothing is spent until you approve it.")
    return Estimate(kind=kind, amount=value, what=what, unit=unit, text=text)


def configured(cfg: dict, kind: str) -> float | None:
    """The amount a config.yaml sets for `kind`, or None when it is missing or not a positive number."""
    b = cfg.get("budget") or {}
    if kind == "test":
        per_day, days = b.get("test_per_day"), b.get("test_days")
        ok = all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
                 for v in (per_day, days))
        return round(per_day * days, 6) if ok else None
    value = b.get(kind)
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
    return round(float(value), 6) if ok else None


def approve(run: RunFolder, kind: Kind, amount: float, note: str | None = None) -> None:
    """Set the approved total for `kind` after the user's yes. It can be raised or lowered, never
    below what is spent. Raises flow.Held while the run is stopped for anything but this budget."""
    _kind(kind)
    value = _amount(amount)
    s = state.load(run)
    flow.refuse_if_held(s, "nothing was approved", kind=kind)
    gap = flow.approval_gap(s, kind, note)
    if gap:
        raise ValueError(gap)
    if kind == "ai_usd":
        _week_cap(run, s, value)
    _set(run, s, kind, value, note)


def _week_left(run: RunFolder, s: state.RunState) -> tuple[float, float, float] | None:
    """An organic video week slot's (week budget, what its other videos may spend, what is left), else None."""
    if not (isinstance(s.organic, dict) and s.organic.get("week")):
        return None
    from tm import organic_week   # the playbook imports the engine: imported where it is used

    return organic_week.week_left(run)


def _week_raise(s: state.RunState) -> str:
    return (f"tm organic week budget --run {s.organic['week']} --usd <amount> --note \"<their words>\"; their yes to "
            "the week is asked again")


def _week_cap(run: RunFolder, s: state.RunState, value: float) -> None:
    """PR E re-review N1: a week slot's whole `ai_usd` approval (what it already spent included) is at most what the
    week has left for it, `organic_week.week_left`'s remainder (the week's budget less what its other videos planned,
    approved or spent). A ValueError above it."""
    week = _week_left(run, s)
    if week is None or value <= week[2] + 1e-9:
        return
    raise ValueError(f"{_fmt('ai_usd', value)} is more than this week's video may have: the week's budget is "
                     f"{_fmt('ai_usd', week[0])} and its other videos planned, approved or spent "
                     f"{_fmt('ai_usd', week[1])}, so the week's remainder for this one is {_fmt('ai_usd', week[2])} "
                     "(what it already spent included). Approve that or less, choose a cheaper way, or, on the "
                     f"user's word, raise the week's budget ({_week_raise(s)}). Nothing was approved.")


def _higher_todo(run: RunFolder, kind: str, base: str) -> str:
    """The over-budget stop's todo; in a week slot (ai_usd) it names the week's remainder and how the week's budget
    is raised (N1)."""
    if kind != "ai_usd":
        return base
    try:
        s = state.load(run)
        week = _week_left(run, s)
    except (OSError, ValueError):
        return base
    if week is None:
        return base
    return (f"{base} This video is part of a week: a higher budget is approved only within the week's remainder for "
            f"it, {_fmt('ai_usd', week[2])}; more needs the week's budget raised on the user's word "
            f"({_week_raise(s)}).")


def approve_from_intake(run: RunFolder, kind: Kind, amount: float) -> None:
    """Hands-off: the budgets the user gave at intake are their yes."""
    _kind(kind)
    _set(run, state.load(run), kind, _amount(amount), "the budget given at intake (Hands-off)")


def _set(run: RunFolder, s: state.RunState, kind: str, value: float, note: str | None) -> None:
    spent = s.spend.get(kind, 0.0)
    if value < spent:
        raise ValueError(f"{_fmt(kind, spent)} is already spent, so the budget cannot go below it.")
    s.budgets[kind] = value
    entry = {"kind": kind, "amount": value, "at": flow._now()}
    if note and note.strip():
        entry["note"] = note.strip()
    s.approvals.append(entry)
    state.save(run, s)


def spend(run: RunFolder, kind: Kind, amount: float, what: str) -> int:
    """Record a spend. Returns 0, or 2 (and stops the run) when it would go over the approved
    budget. Raises flow.Held, recording nothing, while the run is stopped."""
    _kind(kind)
    value = _amount(amount)
    s = state.load(run)
    flow.refuse_if_held(s, "nothing was spent")
    approved = s.budgets.get(kind, 0.0)
    spent = s.spend.get(kind, 0.0)
    if spent + value > approved + 1e-9:
        left = max(approved - spent, 0.0)
        if approved:
            said = (f"{what} would cost {_fmt(kind, value)}, but only {_fmt(kind, left)} is left "
                    f"of the approved {_fmt(kind, approved)}.")
        else:
            said = f"{what} would cost {_fmt(kind, value)}, but no budget is approved for it yet."
        return flow.stop(run, f"over_budget_{kind}", said + " Nothing was spent.",
                         _higher_todo(run, kind, "Tell Claude whether to approve a higher budget or to choose a "
                                                 "cheaper way."))
    s.spend[kind] = round(spent + value, 6)
    state.save(run, s)
    return 0


def reconcile(run: RunFolder, kind: Kind, estimated: float, actual: float, what: str) -> int:
    """Replace a recorded estimate with the actual cost once it is known.

    Less than estimated gives the difference back. More is recorded as it is, even past the
    approved total (the money is already spent); then the run stops (exit 2) so the next spend
    waits for the user, and nothing is hidden.
    """
    _kind(kind)
    est, act = _amount(estimated, allow_zero=True), _amount(actual, allow_zero=True)
    s = state.load(run)
    spent = round(max(0.0, s.spend.get(kind, 0.0) - est + act), 6)
    s.spend[kind] = spent
    state.save(run, s)
    approved = s.budgets.get(kind, 0.0)
    if spent > approved + 1e-9:
        return flow.stop(
            run, f"over_budget_{kind}",
            f"{what} cost {_fmt(kind, act)}, more than the estimated {_fmt(kind, est)}, so "
            f"{_fmt(kind, spent)} is now spent of the approved {_fmt(kind, approved)}.",
            _higher_todo(run, kind, "Tell Claude whether to approve a higher budget before anything else is spent."))
    return 0


# --- command line ---------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    e = sub.add_parser("estimate", help="words for the user; changes nothing")
    e.add_argument("kind")
    e.add_argument("amount", type=float)
    e.add_argument("--what", required=True)
    a = sub.add_parser("approve", help="record the approved total for a kind, after the user's yes")
    a.add_argument("kind")
    a.add_argument("amount", type=float)
    a.add_argument("--note", help="the user's own words, when no check-in in the run asks for this budget")
    s = sub.add_parser("spend", help="record money spent; refuses what would go over")
    s.add_argument("kind")
    s.add_argument("amount", type=float)
    s.add_argument("--what", required=True)
    for sp in (e, a, s):
        sp.add_argument("--json", action="store_true")
        if sp is not e:
            sp.add_argument("--run", required=True, help="the run folder")


def _run(args: argparse.Namespace) -> int:
    try:
        if args.action == "estimate":
            est = estimate(args.kind, args.amount, args.what)
            cli.emit(args, {"status": "done", **asdict(est)}, est.text)
            return 0
        run = RunFolder.open(Path(args.run))
        if args.action == "approve":
            approve(run, args.kind, args.amount, note=args.note)
            text = f"Approved {_fmt(args.kind, args.amount)} for {args.kind}."
            if flow.open_stop(run, [f"over_budget_{args.kind}"]):
                text += " The run is stopped for this budget: once the user agrees, run `tm resume`."
            cli.emit(args, {"status": "done", "kind": args.kind, "approved": float(args.amount)}, text)
            return 0
        code = spend(run, args.kind, args.amount, args.what)
        if code:
            message = flow.open_stop(run, [f"over_budget_{args.kind}"]) or "Over budget."
            cli.emit(args, {"status": "stop", "message": message}, message)
            return code
        s = state.load(run)
        total, approved = s.spend[args.kind], s.budgets[args.kind]
        cli.emit(args, {"status": "done", "kind": args.kind, "spent": total, "approved": approved,
                        "left": round(approved - total, 6)},
                 f"Recorded. {_fmt(args.kind, total)} spent of {_fmt(args.kind, approved)}.")
        return 0
    except flow.Held as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("budget", _setup, _run)
