"""`tm ad`: the commands of Create an ad (playbook 05).

    tm ad check <concepts|claims|board|plan|storyboard> --run R --file F   check what the agent wrote (S1 to G3)
    tm ad check edit --run R --file F                                     check the edit's QA (S7, tm.create_qa)
    tm ad clips --run R --file F                                          the model ads' clips for the concepts page (S1)
    tm ad redo --run R --item ITEM --note "<the user's words>"           the user's request for a new video take
    tm ad reject --run R --item ITEM --note "<the user's words>"         book an item's turned-down takes as rejected
    tm ad costs --run R                                                   approved, planned, spent, and rejected apart
    tm ad prices --run R                                                  save ElevenLabs' dated prices (a price file)
    tm ad copy check --run R --file F                                     check the Meta copy draft (S8)
    tm ad copy accept --run R --file F                                    write the accepted copy (S8, after the check-in)
    tm ad upload check --run R --file F                                   check the upload proposal (S10a)
    tm ad upload record --run R --file F                                  check the objects read back from Meta (S10b)

Exit 0 done, 2 a stop (what to fix, the problems listed), 1 an error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tm import cli, create_plan, i18n
from tm.runfolder import RunFolder
from tm.stops import Stop

_CHECK = {"concepts": create_plan.CONCEPTS, "claims": create_plan.CLAIMS, "board": create_plan.BOARD,
          "plan": create_plan.PLAN, "storyboard": create_plan.STORYBOARD, "edit": create_plan.EDIT_QA}


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="check a file the agent wrote (S1 to G3, and the edit QA at S7)")
    c.add_argument("what", choices=list(_CHECK))
    c.add_argument("--file", required=True)
    cl = sub.add_parser("clips", help="save each model ad's thumbnail and first ~15 s from its saved answer (S1)")
    cl.add_argument("--file", required=True, help="the concepts file")
    r = sub.add_parser("redo", help="record the user's request for a new take of a video item")
    r.add_argument("--item", required=True)
    r.add_argument("--note", required=True, help="the user's own words")
    rj = sub.add_parser("reject", help="book the takes of an item the user turned down as rejected spend")
    rj.add_argument("--item", required=True)
    rj.add_argument("--note", required=True, help="the user's own words")
    co = sub.add_parser("costs", help="what each budget approved, planned and spent, rejected takes apart")
    pr = sub.add_parser("prices", help="save ElevenLabs' dated price table in 02_research (free)")
    cp = sub.add_parser("copy", help="the Meta copy (S8)")
    cp.add_argument("copy_action", choices=["check", "accept"])
    cp.add_argument("--file", required=True)
    up = sub.add_parser("upload", help="the PAUSED Meta upload (S10)")
    up.add_argument("upload_action", choices=["check", "record"])
    up.add_argument("--file", required=True)
    for sp in (c, cl, r, rj, co, pr, cp, up):
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.action == "check":
            rel, problems = create_plan.check(run, _CHECK[args.what], args.file)
            if problems:
                return cli.refuse_problems(args, rel, problems)
            cli.emit(args, {"status": "done", "file": rel}, f"{rel} passed the check.")
            return 0
        if args.action == "clips":
            from tm import create_clips
            got = create_clips.fetch(run, args.file)
            cli.emit(args, {"status": "done", **got}, create_clips.words(got))
            return 0
        if args.action == "redo":
            entry = create_plan.redo(run, args.item, args.note)
            cli.emit(args, {"status": "done", "redo": entry},
                     f"Recorded the user's request for a new take of {entry['item']}."
                     + (f" {entry['rejected']:g} spent on the take it replaces is booked as rejected (tm ad costs)."
                        if entry["rejected"] else ""))
            return 0
        if args.action == "reject":
            booked = create_plan.reject(run, args.item, args.note)
            cli.emit(args, {"status": "done", "rejected": booked},
                     i18n.t("ad.costs.booked", n=len(booked), item=args.item,
                            amount=f"{sum(b['amount'] for b in booked):g}"))
            return 0
        if args.action == "costs":
            data = create_plan.costs(run)
            cli.emit(args, {"status": "done", **data}, create_plan.costs_text(data))
            return 0
        if args.action == "prices":
            rel, today = create_plan.prices(run)
            from tm import music_models
            cli.emit(args, {"status": "done", "file": rel, "checked": today},
                     i18n.t("ad.costs.prices", file=rel, checked=today, rates=music_models.CHECKED))
            return 0
        if args.action == "copy":
            from tm import create_copy
            if args.copy_action == "check":
                rel, problems = create_copy.check(run, args.file)
                if problems:
                    return cli.refuse_problems(args, rel, problems)
                page = create_copy.page_data(run)
                promise = create_copy.promise_note(run)
                cli.emit(args, {"status": "done", "file": rel, "page": page,
                                "language_warning": page["language_warning"], "promise_warning": promise},
                         f"{rel} passed the check. Show the copy to the user and ask whether to change anything."
                         + (f" {page['language_warning']}" if page["language_warning"] else "")
                         + (f" {promise}" if promise else ""))
                return 0
            rel, problems = create_copy.accept(run, args.file)
            if problems:
                return cli.refuse_problems(args, rel, problems)
            cli.emit(args, {"status": "done", "file": rel}, f"Wrote the accepted copy, {rel}.")
            return 0
        from tm import create_upload
        if args.upload_action == "check":
            rel, problems = create_upload.check(run, args.file)
            if problems:
                return cli.refuse_problems(args, rel, problems)
            card = create_upload.card(run)
            cli.emit(args, {"status": "done", "file": rel, "card": card, "language_warning": card["language_warning"]},
                     f"{rel} passed the check. Show the user the proposal in full and ask for the go-ahead."
                     + (f" {card['language_warning']}" if card["language_warning"] else ""))
            return 0
        rel, problems = create_upload.record(run, args.file)
        if problems:
            return cli.refuse_problems(args, rel, problems)
        outcome = create_upload.outcome(run)
        cli.emit(args, {"status": "done", "file": rel, **outcome}, outcome["text"])
        return 0
    except Stop as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("ad", _setup, _run)
