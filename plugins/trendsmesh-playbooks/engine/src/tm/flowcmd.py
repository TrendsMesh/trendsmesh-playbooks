"""Subcommands of the step engine: next, decide, level, done, flow, stop, resume, status and due."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from pathlib import Path

from tm import checkins, cli, flow, paths, state, stops
from tm.runfolder import RunFolder

STOP = 2


def _with_run(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--json", action="store_true")
    return p


def _open(args: argparse.Namespace) -> RunFolder:
    return RunFolder.open(Path(args.run))


def _guard(fn):
    def wrapped(args: argparse.Namespace) -> int:
        try:
            return fn(args)
        except (flow.Held, stops.Stop) as exc:  # stopped, or a gap a step's check found (exit 2)
            cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
            return STOP
        except (OSError, ValueError) as exc:
            return cli.fail(args, str(exc))
    return wrapped


@_guard
def _next(args: argparse.Namespace) -> int:
    nxt = flow.next(_open(args))
    lines = [f"{nxt.action}: {nxt.step} {nxt.title}", f"ref: {nxt.ref}"]
    if nxt.checkin:
        lines.append(f"check-in: {nxt.checkin.name} ({', '.join(nxt.checkin.ids)})")
    if nxt.message:
        lines.append(nxt.message)
    cli.emit(args, asdict(nxt), "\n".join(lines))
    return STOP if nxt.action == "stop" else 0


def _setup_decide(p: argparse.ArgumentParser) -> None:
    p.add_argument("checkin", help="a check-in id (G3) or a card id (pick_the_ad)")
    p.add_argument("choice")
    p.add_argument("--note")
    p.add_argument("--by", choices=("user", "rule"), default="user")
    p.add_argument("--change", action="store_true", help="change a decision already taken")
    _with_run(p)


@_guard
def _decide(args: argparse.Namespace) -> int:
    run = _open(args)
    before = len(state.load(run).decisions)
    flow.decide(run, args.checkin, args.choice, by=args.by, note=args.note, change=args.change)
    s = state.load(run)
    payload = {"status": "done", "checkin": args.checkin, "choice": args.choice,
               "run_status": s.status}
    caused = flow.open_stop(run, [args.checkin])
    if caused:
        cli.emit(args, {**payload, "status": "stop", "message": caused}, caused)
        return STOP
    if s.status == "done":
        message = flow.next(run).message
        cli.emit(args, {**payload, "message": message}, message)
        return 0
    cat = checkins.load(playbook=s.playbook)
    recorded = [cat.checkins[d["checkin"]] for d in s.decisions[before:]]  # what this call decided
    notes = list(dict.fromkeys(n for c in recorded
                               if (n := c.on_choice.get(args.choice, {}).get("skips"))))
    text = " ".join([f"Recorded {args.checkin}: {args.choice}.", *notes])
    cli.emit(args, {**payload, **({"message": text} if notes else {})}, text)
    return 0


def _setup_level(p: argparse.ArgumentParser) -> None:
    p.add_argument("level")
    _with_run(p)


@_guard
def _level(args: argparse.Namespace) -> int:
    flow.set_level(_open(args), args.level)
    cli.emit(args, {"status": "done", "level": args.level}, f"Level set to {args.level}")
    return 0


def _setup_done(p: argparse.ArgumentParser) -> None:
    p.add_argument("step")
    p.add_argument("--measured", help="ISO date of the measurement just taken (E4)")
    _with_run(p)


@_guard
def _done(args: argparse.Namespace) -> int:
    run = _open(args)
    flow.complete(run, args.step, measured=args.measured)
    cli.emit(args, {"status": "done", "step": args.step, "next_step": state.load(run).step},
             f"{args.step} done")
    return 0


def _setup_flow(p: argparse.ArgumentParser) -> None:
    p.add_argument("flow", help="a variant flow from VARIANTS.md, e.g. V")
    _with_run(p)


@_guard
def _flow(args: argparse.Namespace) -> int:
    run = _open(args)
    flow.use_flow(run, args.flow)
    cli.emit(args, {"status": "done", "flows": state.load(run).flows}, f"Flow {args.flow} in use")
    return 0


def _setup_stop(p: argparse.ArgumentParser) -> None:
    p.add_argument("--reason", required=True, help="a stable id, e.g. missing_video")
    p.add_argument("--what", required=True, help="what happened, in plain words")
    p.add_argument("--todo", required=True, help="what the user does next, in plain words")
    _with_run(p)


@_guard
def _stop(args: argparse.Namespace) -> int:
    """A stop Claude found itself (no video file, a file to upload by hand): held until `tm resume`."""
    if not (args.reason.strip() and args.what.strip() and args.todo.strip()):
        raise ValueError("A stop needs --reason, --what and --todo, none of them empty.")
    run = _open(args)
    flow.stop(run, args.reason.strip(), args.what.strip(), args.todo.strip())
    message = flow.open_stop(run, [args.reason.strip()]) or args.what
    cli.emit(args, {"status": "stop", "message": message}, message)
    return STOP


@_guard
def _resume(args: argparse.Namespace) -> int:
    flow.resume(_open(args))
    cli.emit(args, {"status": "done"}, "Resumed. Run `tm next`.")
    return 0


@_guard
def _status(args: argparse.Namespace) -> int:
    run = _open(args)
    s = asdict(state.load(run))
    cli.emit(args, {**s, "path": str(run.path)},
             "\n".join(f"{k}: {v}" for k, v in s.items()))
    return 0


def _setup_due(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true",
                   help="one plain line per thing due (a measurement, a weekly trend report), nothing when none "
                        "(the session-start hook)")


@_guard
def _due(args: argparse.Namespace) -> int:
    items = flow.due(paths.workspace(), date.today())
    if args.quiet and not args.json:
        for i in items:
            print(i["message"])
        return 0
    cli.emit(args, {"due": items}, "\n".join(i["message"] for i in items) or "Nothing is due.")
    return 0


cli.register("next", _with_run, _next)
cli.register("decide", _setup_decide, _decide)
cli.register("level", _setup_level, _level)
cli.register("done", _setup_done, _done)
cli.register("flow", _setup_flow, _flow)
cli.register("stop", _setup_stop, _stop)
cli.register("resume", _with_run, _resume)
cli.register("status", _with_run, _status)
cli.register("due", _setup_due, _due)
