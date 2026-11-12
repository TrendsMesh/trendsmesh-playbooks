"""`tm ad`: the commands of Create an ad (playbook 05).

    tm ad check <concepts|claims|board|plan|storyboard> --run R --file F   check what the agent wrote (S1 to G3)
    tm ad check edit --run R --file F                                     check the edit's QA (S7, tm.create_qa)
    tm ad redo --run R --item ITEM --note "<the user's words>"           the user's request for a new video take
    tm ad copy check --run R --file F                                     check the Meta copy draft (S8)
    tm ad copy accept --run R --file F                                    write the accepted copy (S8, after the check-in)
    tm ad upload check --run R --file F                                   check the upload proposal (S10a)
    tm ad upload record --run R --file F                                  check the objects read back from Meta (S10b)

Exit 0 done, 2 a stop (what to fix, the problems listed), 1 an error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tm import cli, create_plan
from tm.runfolder import RunFolder
from tm.stops import Stop

_CHECK = {"concepts": create_plan.CONCEPTS, "claims": create_plan.CLAIMS, "board": create_plan.BOARD,
          "plan": create_plan.PLAN, "storyboard": create_plan.STORYBOARD, "edit": create_plan.EDIT_QA}


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="check a file the agent wrote (S1 to G3, and the edit QA at S7)")
    c.add_argument("what", choices=list(_CHECK))
    c.add_argument("--file", required=True)
    r = sub.add_parser("redo", help="record the user's request for a new take of a video item")
    r.add_argument("--item", required=True)
    r.add_argument("--note", required=True, help="the user's own words")
    cp = sub.add_parser("copy", help="the Meta copy (S8)")
    cp.add_argument("copy_action", choices=["check", "accept"])
    cp.add_argument("--file", required=True)
    up = sub.add_parser("upload", help="the PAUSED Meta upload (S10)")
    up.add_argument("upload_action", choices=["check", "record"])
    up.add_argument("--file", required=True)
    for sp in (c, r, cp, up):
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
        if args.action == "redo":
            entry = create_plan.redo(run, args.item, args.note)
            cli.emit(args, {"status": "done", "redo": entry},
                     f"Recorded the user's request for a new take of {entry['item']}.")
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
