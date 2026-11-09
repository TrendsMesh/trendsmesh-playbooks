import sys

from tm.cli import main

# Windows writes piped output in the ANSI code page (cp1252 and the like), where printing a path
# such as "Moje reklamy Łódź" raises UnicodeEncodeError and the command fails. Always speak UTF-8.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace" if stream is sys.stderr else "strict")

sys.exit(main())
