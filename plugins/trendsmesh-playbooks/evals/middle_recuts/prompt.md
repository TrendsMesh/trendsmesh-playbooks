---
description: "Check-every-step run at the funnel diagnosis. The hook holds and the retention step p75/p50 drops 6 points (RC4): the diagnosis is middle, the re-cut path is on by itself, and the agent offers re-cut variants, each one change with its level, before anything is rendered or bought."
tags: [recut]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05, so add `--today 2026-11-05` to `tm r1`. Write final answers for the
  user in plain words.
---

My refresh run in runs/01-refresh-ad/ is at the funnel diagnosis; the ad is already chosen. Carry on with the diagnosis. Before I answer the diagnosis question, tell me which part of the ad is fading and what kinds of change you would offer me for it.
