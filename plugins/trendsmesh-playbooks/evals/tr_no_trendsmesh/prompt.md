---
description: "No run yet. The user asks for trend research on beauty in the US. TrendsMesh is signed in on the free Human plan (get_usage answers plan_code human; every data tool answers not_in_plan) while an offer makes the Agent plan's first month free. Trend research stops: it reads every number from TrendsMesh, so there is no guess mode. The agent says so, gives the Agent-plan offer once and makes no report."
tags: [trend-research, readiness]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. Write final answers for the user in plain words.
---

I'd like trend research for beauty in the US: which trends to act on now. Set it up and run it.
