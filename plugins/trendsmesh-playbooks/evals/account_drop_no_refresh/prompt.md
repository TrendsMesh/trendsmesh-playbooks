---
description: "Hands-off run at the fetch of the fading winners. The whole account falls, so the ad is not fading by itself: the run must end with 'do not refresh' and no spend."
tags: [whole-run]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05, so add `--today 2026-11-05` to `tm r1`. Write final answers for the
  user in plain words.
---

Our Meta ads on ad account 9990000001 have been getting worse lately. My refresh run is already set up in runs/01-refresh-ad/ (Hands-off, creative brief only). Carry it on from the start: find the winner that is fading and decide what we do about it. When you are done tell me what you did and what happens next.
