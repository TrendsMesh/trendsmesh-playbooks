"""`tm models`: the model registry from the command line (issue #115), and the Models page for any playbook.

    tm models list [--task T] [--json]                     the tasks, or one task's rows: group, ★, variant, price
    tm models check [--json]                               the registry and its alias table, checked
    tm models ids --task T [--task T ...] [--json]         the Replicate ids a page of these tasks prices live (give
                                                           them to `tm tool replicate_price --run R ...`)
    tm models page --run R --task T [...] [--units F] [--face] [--voiceover] [--json]
                                                           the Models page of these tasks (Create an ad S5, Refresh
                                                           an ad D1), in a new 04_final/models_vNN/
    tm models decisions --run R [--by-rule | --text F | --file F] [--json]
                                                           the choice into 03_wip/models_vNN.json

Organic AI video builds its page with `tm organic page models` (its tasks and units come from the recipe); the page,
its reading and its file are the same (`tm.organic_pages.models`). Nothing here changes the registry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tm import cli, model_registry
from tm.runfolder import RunFolder
from tm.stops import Stop


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="models_action", required=True)
    ls = sub.add_parser("list", help="the registry's tasks, or one task's rows")
    ls.add_argument("--task")
    ls.add_argument("--json", action="store_true")
    ck = sub.add_parser("check", help="check the registry and its alias table")
    ck.add_argument("--json", action="store_true")
    ids = sub.add_parser("ids", help="the Replicate models a page of these tasks prices live")
    ids.add_argument("--task", action="append", required=True)
    ids.add_argument("--json", action="store_true")
    pg = sub.add_parser("page", help="the Models page of these tasks (Create an ad S5, Refresh an ad D1)")
    pg.add_argument("--run", required=True)
    pg.add_argument("--task", action="append", required=True)
    pg.add_argument("--units", help="a JSON file in the run (or inline JSON): images, video_seconds, takes, "
                                    "upscale_seconds, characters, sound_seconds, music_seconds, minutes")
    pg.add_argument("--face", action="store_true", help="a frame has a photoreal face (greys out Seedance, E005)")
    pg.add_argument("--voiceover", action="store_true", help="a separate voiceover replaces the model's own sound")
    pg.add_argument("--json", action="store_true")
    dc = sub.add_parser("decisions", help="read the choice on the Models page into 03_wip/models_vNN.json")
    dc.add_argument("--run", required=True)
    dc.add_argument("--by-rule", action="store_true", help="Hands-off: take the selected (★) models by rule")
    dc.add_argument("--text", help="the user's answer from chat, one line per task: <task>: <option id>")
    dc.add_argument("--file", help="a saved answer of the page (an ArtifactData list)")
    dc.add_argument("--json", action="store_true")


def _list(args: argparse.Namespace) -> int:
    if not args.task:
        tasks = model_registry.tasks()
        text = "\n".join(f"{t}: {v.get('label')}" for t, v in tasks.items())
        cli.emit(args, {"status": "done", "tasks": tasks, "checked": model_registry.checked().isoformat(),
                        "message": text}, text)
        return 0
    if args.task not in model_registry.tasks():
        raise ValueError(f"{args.task} is not a task of the model registry ({', '.join(model_registry.tasks())}).")
    rows = model_registry.active(args.task)
    lines = []
    for r in rows:
        amount = r["price"].get("usd", r["price"].get("credits"))
        money = "credits" if "credits" in r["price"] else "USD"
        lines.append(f"{r['group']:<9} {'★' if r['star'] else ' '} {r['model']} {r['variant']}: {amount:g} {money} per "
                     f"{r['price']['per']} (checked {r['price']['checked']}); sends {json.dumps(r['send'])}")
    text = "\n".join(lines)
    cli.emit(args, {"status": "done", "task": args.task, "rows": rows, "message": text}, text)
    return 0


def _check(args: argparse.Namespace) -> int:
    problems = model_registry.validate(model_registry.load(), model_registry.aliases())
    if problems:
        text = "The model registry needs fixing:\n" + "\n".join(f"- {p}" for p in problems)
        cli.emit(args, {"status": "stop", "problems": problems, "message": text}, text)
        return 2
    text = (f"The model registry is in order: {len(model_registry.ids())} active models, prices checked "
            f"{model_registry.checked().isoformat()}.")
    cli.emit(args, {"status": "done", "problems": [], "message": text}, text)
    return 0


def _ids(args: argparse.Namespace) -> int:
    from tm.organic_pages import models

    wrong = [t for t in args.task if t not in model_registry.tasks()]
    if wrong:
        raise ValueError(f"{', '.join(wrong)}: not a task of the model registry ({', '.join(model_registry.tasks())}).")
    ids = models.price_ids(args.task)
    text = " ".join(ids)
    cli.emit(args, {"status": "done", "ids": ids, "message": text}, text)
    return 0


def _page(args: argparse.Namespace) -> int:
    from tm.organic_pages import models

    run = RunFolder.open(Path(args.run))
    units = cli.json_arg(args.units, run) if args.units else {}
    if not isinstance(units, dict):
        raise ValueError("--units must be a JSON object of numbers.")
    got = models.build_tasks(run, args.task, units, face=args.face, narrated=args.voiceover)
    message = (f"Built the models page in {got['folder']} ({got['sections']} sections). Publish it: tm page files "
               f"--run {args.run} --page models gives the Artifact tool's file_path and files, with "
               "organic_pages.CAPABILITIES[\"models\"] as its capabilities (db collection models); record it with tm "
               "page published --page models, and wait with tm page await --page models. Read the choice with tm "
               "models decisions --run R (an answer in chat with --text <file>; Hands-off: --by-rule).")
    cli.emit(args, {"status": "done", **got, "message": message}, message)
    return 0


def _decisions(args: argparse.Namespace) -> int:
    from tm.organic_pages import models

    run = RunFolder.open(Path(args.run))
    got = models.take(run, file=Path(args.file) if args.file else None, text=Path(args.text) if args.text else None,
                      by_rule=args.by_rule)
    picked = ", ".join(f"{task} {p['model'] or 'none'}{' ' + p['variant'] if p.get('variant') else ''}"
                       for task, p in got["models"].items() if p)
    message = f"Read the models into {got['file']}: {picked}; {got['total_usd']:g} USD on Replicate."
    if got["recipes_to_write"]:
        message += (" Write these recipes first, from each model's official prompting guide: "
                    + ", ".join(got["recipes_to_write"]) + ".")
    cli.emit(args, {"status": "done", **got, "message": message}, message)
    return 0


def _run(args: argparse.Namespace) -> int:
    action = {"list": _list, "check": _check, "ids": _ids, "page": _page, "decisions": _decisions}[args.models_action]
    try:
        return action(args)
    except Stop as exc:  # a Stop is a ValueError: caught first, it exits 2
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError, KeyError) as exc:
        return cli.fail(args, str(exc))


cli.register("models", _setup, _run)
