"""Command line entry point. Subcommands register themselves with `register`."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

from tm import __version__

SetupFn = Callable[[argparse.ArgumentParser], None]
RunFn = Callable[[argparse.Namespace], int]

_COMMANDS: dict[str, tuple[SetupFn, RunFn]] = {}


def register(name: str, setup: SetupFn, run: RunFn) -> None:
    _COMMANDS[name] = (setup, run)


def emit(args: argparse.Namespace, payload: dict, text: str) -> None:
    """Print one JSON object with --json, otherwise the plain text."""
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def json_arg(text: str):
    """A JSON argument given inline or, as the skill passes it, as the path of a JSON file (on
    Windows inline JSON loses its quotes on the way through cmd and PowerShell)."""
    from pathlib import Path

    text = text.strip()
    raw = text if text[:1] in ("{", "[") else Path(text).read_text(encoding="utf-8-sig")   # a BOM from PowerShell
    return json.loads(raw)


def fail(args: argparse.Namespace, message: str) -> int:
    emit(args, {"status": "error", "message": message}, message)
    return 1


def refuse_problems(args: argparse.Namespace, rel: str, problems: list) -> int:
    """Exit 2 with the problems (`config.Problem`: field, what, todo) a check found in a file the agent
    wrote, `rel` run-relative: fix it as a new version and check again."""
    from tm.stops import AGAIN

    lines = [f"- {p.field}: {p.what} {p.todo}" for p in problems]
    message = (f"{rel} needs fixing:\n" + "\n".join(lines) + f"\nFix the file (a new version), then check it "
               f"again; {AGAIN}.")
    emit(args, {"status": "stop", "file": rel, "message": message,
                "problems": [{"field": p.field, "what": p.what, "todo": p.todo} for p in problems]}, message)
    return 2


def _load_commands() -> None:
    """Import the modules that register subcommands (later tasks add theirs here)."""
    import tm.acceptance  # noqa: F401
    import tm.ai_media  # noqa: F401
    import tm.audience  # noqa: F401
    import tm.brand  # noqa: F401
    import tm.brief  # noqa: F401
    import tm.budget  # noqa: F401
    import tm.config  # noqa: F401
    import tm.doctor  # noqa: F401
    import tm.changes  # noqa: F401
    import tm.envtiers  # noqa: F401
    import tm.evidence  # noqa: F401
    import tm.register  # noqa: F401
    import tm.formats  # noqa: F401
    import tm.kit  # noqa: F401
    import tm.library  # noqa: F401
    import tm.livetest  # noqa: F401
    import tm.offer  # noqa: F401
    import tm.organic  # noqa: F401
    import tm.page  # noqa: F401
    import tm.r2  # noqa: F401
    import tm.r2b  # noqa: F401
    import tm.r4  # noqa: F401
    import tm.recut_plan  # noqa: F401
    import tm.report  # noqa: F401
    import tm.research  # noqa: F401
    import tm.flowcmd  # noqa: F401
    import tm.r1  # noqa: F401
    import tm.runcmd  # noqa: F401
    import tm.tools  # noqa: F401
    import tm.render  # noqa: F401
    import tm.review  # noqa: F401
    import tm.schedule  # noqa: F401
    import tm.seeds  # noqa: F401
    import tm.trends  # noqa: F401
    import tm.voice  # noqa: F401


def build_parser() -> argparse.ArgumentParser:
    _load_commands()
    parser = argparse.ArgumentParser(prog="tm")
    parser.add_argument("--version", action="version", version=f"tm {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")
    for name, (setup, run) in _COMMANDS.items():
        setup(sub.add_parser(name))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) and code == 0 else 1
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 1
    return _COMMANDS[args.command][1](args)
