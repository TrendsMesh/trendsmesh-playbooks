---
description: "Check-every-step trend research run (beauty, US, with the paid view) at the Ad Library step (D2). The Meta Ads MCP (mocked) answers every search with loose, unrelated matches (fridge shelves, fitness apps, novels): no relevant advertiser. The summary says 'none' for the cat-eye nails trend and 'not_checkable' for every hook, the engine checks it, and the message says 'none found in Ad Library titles', never that a trend is not in ads."
tags: [trend-research, tr7]
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

My trend research run for beauty in the US is in runs/04-trend-research/. Carry on from where it is: do the paid vs organic check in the Meta Ad Library, then tell me what you found for the trends, before you write the picks. Stop there.
