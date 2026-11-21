import os
import sys


def run() -> int:
    # Windows writes piped output in the ANSI code page (cp1252 and the like), where printing a path
    # such as "Moje reklamy Łódź" raises UnicodeEncodeError and the command fails. Always speak UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace" if stream is sys.stderr else "strict")
    try:
        from tm.cli import main
        return main()
    except (ImportError, OSError) as exc:
        # Windows Smart App Control blocked a file of the plugin's Python (issue #123): say so and what to do,
        # with no traceback. The launchers set TM_BLOCK_EXIT to tell this from any other failure.
        from tm import winblock
        if not winblock.blocked(exc):
            raise
        print(winblock.message(winblock.blocked_file(exc)), file=sys.stderr)
        code = os.environ.get("TM_BLOCK_EXIT", "")
        return int(code) if code.isdigit() else 1


if __name__ == "__main__":
    sys.exit(run())
