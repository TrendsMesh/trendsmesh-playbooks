"""`python -m tm.toolrun <tool> [args]`: run `tm.tools.<tool>` as its main, as `python -m tm.tools.<tool>` would.

`tm tool` starts every tool this way (`tm.tools.child_argv`). A tool's own failures are its `_common.guarded`'s to
answer, but an import that fails before the tool's main starts (the `tm` package, a module the tool imports at the
top) ends in a raw traceback. When that is a compiled file Windows Smart App Control blocked (#148 line 154), this
says so with tm's message instead, as the tool would: one line, or one JSON object with --json, and exit 2 (a stop).
Any other failure is raised as before.

Only the standard library and tm.winblock are imported before the tool."""
from __future__ import annotations

import json
import runpy
import sys


def run(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        print("Use: python -m tm.toolrun TOOL [ARGS...]", file=sys.stderr)
        return 1
    name, rest = args[0], args[1:]
    sys.argv = [sys.argv[0], *rest]   # run_module puts the tool's own file in sys.argv[0]
    try:
        runpy.run_module(f"tm.tools.{name}", run_name="__main__", alter_sys=True)
    except (ImportError, OSError) as exc:
        from tm import winblock

        said = winblock.tool_message(exc)
        if not said:
            raise
        print(json.dumps({"status": "stop", "message": said}, ensure_ascii=False) if "--json" in rest else said)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(run())
