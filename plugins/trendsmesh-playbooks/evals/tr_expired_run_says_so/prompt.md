---
description: "Issue 59. A trend research run (beauty, US, Check every step) made on 1 September is unfinished at the relevance review (B3); its trend data was fetched that day and expired on 15 September. The user asks for beauty trend research without saying to continue it. The agent asks one short question first, naming the unfinished run, and says that its trend data has expired: start a new run with fresh data, or continue on the old data. It resumes nothing and calls no TrendsMesh tool before the answer."
tags: [trend-research, resume]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. If `tm doctor` says the base tools are not installed, that is only
  because the engine runs from source here: count them as installed. Write final answers for the user
  in plain words.
---

What's trending in beauty in the US right now? Which trends should we act on?
