---
description: "Check-every-step trend research run (beauty, US, with the paid view) at the review of the picks (D3): growth and the evidence dumps are in; Meta was not connected at the Ad Library step, so the summary says not checked (only the hooks' not_checkable rows). The agent writes and checks the picks and shows the picks check-in (G2): each pick's position in the sample first (band, x typical), raw counts second, 'creators in TrendsMesh evidence', the eyelash pick's risk naming the evidence's language (mostly Russian), no hypothesis said as a finding."
tags: [trend-research, tr10, r3, tr4]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. Write final answers for the user in plain words.
---

My trend research run for beauty in the US is in runs/04-trend-research/. Carry on from where it is, up to the check-in where I approve the picks. Show me the picks and wait for my answer.
