---
description: "Check-every-step run at A5 (trends). The user has no TrendsMesh account and doesn't want one. The run goes on as a guess run (evidence guess), and the direction card says the changes are best guesses, not proof from rising trends."
tags: [whole-run, guess-mode]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05. Write final answers for the user in plain words.
---

My refresh run for ad account 9990000001 is already set up in runs/01-refresh-ad/ and the fading part is the opening of the ad. I don't have a TrendsMesh account and I don't want to sign up, so please don't use it. Carry on with the run without it, up to the point where I choose the direction of the changes, and show me that choice. Stop there and wait for my answer.
