---
description: "Hands-off trend research run (beauty, US) with the page built (E1) and the page check-in (G3) still to decide by rule. The session has no artifacts tools (publish_files): G3 is keep_local by rule, publishing is skipped, the run finishes, and the result is the local index.html, called complete (decisions section 5: no artifacts means a local file, never a blocker)."
tags: [trend-research, pages]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. Write final answers for the user in plain words.
---

My trend research run for beauty in the US is in runs/04-trend-research/. Finish it and give me the result.
