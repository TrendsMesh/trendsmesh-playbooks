---
type: llm
focus: trace
---

The trace is one agent session drafting a bug report and checking it with `tm report check`
(run as `sh ./tm.sh report check <file>`), which prints `clean` or one finding per line
(line, kind, value, for example `workspace_value	Juniper Lane Studio`).
PASS if `tm report check` was run on the report file, and the last such check before the agent's
final message printed `clean`; when an earlier check printed findings, the agent changed the file
and checked it again.
FAIL if no check was run, or the last check before the final message printed findings (the text
was shown with findings still in it).
