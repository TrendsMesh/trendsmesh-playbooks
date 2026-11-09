---
description: "Check-every-step run at the AI video's first paid step; the user switches to Hands-off with no AI budget: the brief stays, nothing is spent, and the run stops at the budget with a plain message."
tags: [whole-run]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05, so add `--today 2026-11-05` to `tm r1`. Write final answers for the
  user in plain words.
---

I don't want to be asked anything any more: switch my run in runs/01-refresh-ad/ to Hands-off and run it to the end. I haven't set any AI budget, and I'm not going to.
