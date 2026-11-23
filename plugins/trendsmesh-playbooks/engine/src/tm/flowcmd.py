"""Subcommands of the step engine: next, decide, level, done, flow, stop, resume, status and due."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from pathlib import Path

from tm import checkins, cli, flow, forced, i18n, paths, state, stops, trend_age
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
    if nxt.notice:
        lines.append(f"notice: {nxt.notice}")
    if nxt.free_box:
        lines.append(f"free_box: {nxt.free_box}")
    if nxt.forced:
        lines.append(f"forced: {nxt.forced['command']} ({nxt.forced['words']})")
    cli.emit(args, asdict(nxt), "\n".join(lines))
    return STOP if nxt.action == "stop" else 0


SAID_NEEDED = "A decision by the user needs --said with their own words from the chat."


def _setup_decide(p: argparse.ArgumentParser) -> None:
    p.add_argument("checkin", help="a check-in id (G3) or a card id (pick_the_ad)")
    p.add_argument("choice")
    p.add_argument("--note", help="context: the data behind a rule's decision, or what the answer rests on")
    p.add_argument("--said", help="the user's own words from the chat, verbatim (needed with --by user)")
    p.add_argument("--said-file", metavar="PATH", help="the user's own words in a UTF-8 file (a BOM is fine), when "
                                                       "quotes or line breaks would not survive the command line")
    p.add_argument("--by", choices=("user", "rule", forced.FORCED), default="user",
                   help="user (the default: needs --said), rule (needs --note) or forced: the one possible answer "
                        "the run's data leaves (issue #148 line 30), no --said")
    p.add_argument("--change", action="store_true", help="change a decision already taken")
    p.add_argument("--concepts", nargs="+",
                   help="the concepts a choice is for, e.g. C1,C3 (creative brief: animatics make)")
    p.add_argument("--stage", help="refresh-ad G1a override: the part of the ad the user wants refreshed against "
                                   "the diagnosis (hook, middle, promise_cta or fatigue)")
    _with_run(p)


def _said(args: argparse.Namespace, run: RunFolder) -> str | None:
    """The user's words for a decision by the user (issue #125): `--said`, or `--said-file` read as UTF-8 (BOM
    accepted, the file's last line break dropped), kept verbatim. Required with --by user, refused with --by rule
    and with --by forced (the situation's answer, not the user's: issue #148 line 30).
    Page decisions (`tm page decision --record`) call `flow.decide` with their own record and need none."""
    if args.said is not None and args.said_file is not None:
        raise ValueError("Give the user's words once: --said or --said-file, not both.")
    if args.by == "rule":
        if args.said is not None or args.said_file is not None:
            raise ValueError("--said holds the user's own words; a decision by rule has none: put the data behind "
                             "it in --note.")
        return None
    if args.by == forced.FORCED:
        if args.said is not None or args.said_file is not None:
            raise ValueError(flow.FORCED_NO_SAID)
        return None
    said = args.said
    if args.said_file is not None:
        path = run.given(args.said_file)
        try:
            said = path.read_text(encoding="utf-8-sig").removesuffix("\n").removesuffix("\r")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"Could not read --said-file {path}: {exc}. Give the user's words in a UTF-8 text "
                             "file, or with --said.") from None
    if said is None or not said.strip():
        raise ValueError(f"{SAID_NEEDED} Pass them with --said \"<their words>\", or --said-file <path> for long words "
                         "(UTF-8). A decision Claude takes by the check-in's rule is --by rule --note <the data>.")
    return said


@_guard
def _decide(args: argparse.Namespace) -> int:
    run = _open(args)
    said = _said(args, run)
    before = len(state.load(run).decisions)
    wrote = flow.decide(run, args.checkin, args.choice, by=args.by, note=args.note, change=args.change, said=said,
                        concepts=cli.ids_arg(args.concepts) or None, stage=args.stage)
    s = state.load(run)
    payload = {"status": "done", "checkin": args.checkin, "choice": args.choice,
               "run_status": s.status}
    caused = flow.open_stop(run, [args.checkin])
    if caused:
        cli.emit(args, {**payload, "status": "stop", "message": caused}, caused)
        return STOP
    from tm import run_page   # it loads every playbook's page code
    rebuilt = None if (wrote or {}).get("page") else run_page.after_decision(run, args.checkin, args.by)
    if rebuilt:
        payload["run_page"] = rebuilt
    if s.status == "done":
        message = flow.next(run).message
        if wrote:   # G1a do_not_refresh (issue #143): the diagnosis report, and the run page built again
            payload.update(wrote)
            built = wrote.get("page")
            if built:
                message += (f" The run page was built again ({built['folder']}), with the diagnosis settled and "
                            + ("its \"Done\" stage: give the user the path of its index.html."
                               if built["local"] else
                               "its \"Done\" stage: publish it to the same URL with the Artifact tool (its `artifact` "
                               "arguments)."))
            if wrote.get("warning"):   # the report is in English: the working language's table lacks its words
                message += " " + wrote["warning"]
        message += _rebuilt_words(rebuilt)
        cli.emit(args, {**payload, "message": message}, message)
        return 0
    cat = checkins.load(playbook=s.playbook)
    recorded = [cat.checkins[d["checkin"]] for d in s.decisions[before:]]  # what this call decided
    notes = list(dict.fromkeys(n for c in recorded
                               if (n := c.on_choice.get(args.choice, {}).get("skips"))))
    by_situation = _forced_words(s.decisions[-1])     # issue #148 line 30: never shown as the user's decision
    text = i18n.offered(" ".join([f"Recorded {args.checkin}: {args.choice}{by_situation}.", *notes]),
                        i18n.run_languages(run).working)    # the weekly phrase in the user's language
    text += _rebuilt_words(rebuilt)
    cli.emit(args, {**payload, **({"message": text} if notes or rebuilt or by_situation else {})}, text)
    return 0


FORCED_WORDS = "forced by the situation"


def _forced_words(d: dict) -> str:
    """`, forced by the situation (<the reason>)` for a decision the situation answered, else nothing."""
    if d.get("by") != forced.FORCED or not d.get("forced"):
        return ""
    return f", {FORCED_WORDS} ({forced.words(d['forced'])})"


def decision_line(d: dict) -> str:
    """One decision of the run log (`tm status`): `<check-in> <choice>: <who>`, the situation's shown as forced by
    it, never as the user's."""
    who = {"user": "the user's", "rule": "by rule"}.get(d.get("by"), d.get("by") or "")
    if d.get("by") == forced.FORCED:
        who = _forced_words(d).removeprefix(", ") or FORCED_WORDS
    return f"{d.get('checkin')} {d.get('choice')}: {who}" + (f" ({d['at']})" if d.get("at") else "")


def _rebuilt_words(rebuilt: dict | None) -> str:
    """What `tm decide` says when it built the run page again (issue #131 items 5 and 6, #134)."""
    if not rebuilt:
        return ""
    if rebuilt.get("brief"):
        return (" Build the brief's page again (tm brief page: it shows this check-in settled) and republish it to "
                "the same link (tm page link --page brief_pack).")
    if rebuilt.get("error"):
        return (f" The run page could not be built again ({rebuilt['error']}); the decision is recorded. Fix that, "
                "then build it with tm page build and republish it to the same link.")
    if rebuilt["local"]:
        return (f" The run page was built again ({rebuilt['folder']}) with this check-in settled: give the user the "
                f"path of its index.html.")
    return (f" The run page was built again ({rebuilt['folder']}) with this check-in settled"
            + (" and nothing open" if not rebuilt["open"] else "")
            + f": republish it to the same link (tm page link --page {rebuilt['page']}), its files listed first, with "
              "its capabilities, and record it with tm page published.")


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
    s = {**asdict(state.load(run)), "trend_data": trend_age.of(run)}   # the resume question says when it expired
    text = "\n".join(f"{k}: {v}" for k, v in s.items() if k not in ("trend_data", "decisions"))
    text += "\ndecisions:" + "".join(f"\n  {decision_line(d)}" for d in s["decisions"] if isinstance(d, dict))
    if s["trend_data"]:
        text += f"\ntrend_data: {s['trend_data']['message']}"
    cli.emit(args, {**s, "path": str(run.path)}, text)
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
