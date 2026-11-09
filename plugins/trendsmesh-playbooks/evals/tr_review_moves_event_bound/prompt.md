---
description: "Check-every-step trend research run (beauty, US) at the Ad Library step (D2), no Meta connector. Rule v3 puts 'Sephora Savings Event sale hauls and picks' in act now, but its description dates the event (30 Oct to 2 Nov). The review of the picks moves it out of act now with a reason (too late or past its peak), the engine checks the picks, and the picks check-in (G2) is reached."
tags: [trend-research, tr3]
max_turns: 70
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
