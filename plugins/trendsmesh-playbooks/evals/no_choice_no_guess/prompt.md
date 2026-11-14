---
description: "Check-every-step run at A5 (trends). TrendsMesh is signed in on the free plan, with no trend data (get_usage answers plan_code human), and the user has said nothing about it (no Free/Paid choice in the workspace). The run must not start guessing on its own (issue #106): it asks one question, Free or Paid, with what Paid adds, and records no evidence before the answer."
tags: [whole-run, guess-mode, free-paid]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05. Write final answers for the user in plain words.
---

My refresh run for ad account 9990000001 is already set up in runs/01-refresh-ad/ and the fading part is the opening of the ad. Carry on with the run up to the point where I choose the direction of the changes, and show me that choice.
