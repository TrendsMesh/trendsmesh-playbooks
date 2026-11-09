---
description: "Check-every-step trend research run (beauty, US) at the relevance review (B3): the map is built from the searches and holds an off-category trend (dementia, matched through 'anti-aging') and seven Halloween trends (seasonal, inside the category). The agent drops the off-category ones with their reasons, keeps the seasonal ones, does the hooks path and shows the map check-in (G1)."
tags: [trend-research, tr1]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. Write final answers for the user in plain words.
---

My trend research run for beauty in the US is already set up in runs/04-trend-research/. Carry on from where it is, up to the check-in where I accept the category map. Show me that check-in and wait for my answer.
