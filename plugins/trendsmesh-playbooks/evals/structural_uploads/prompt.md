---
description: "Check-every-step run at the funnel diagnosis; Meta (mocked) has the chosen ad's file in 4 ads and another ad with a different file. The structural check reads every ad that uses the same video id and only those (RC19), finds p75/p50 weakest in all 4, and the diagnosis check-in offers the re-cut as an option."
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

My refresh run in runs/01-refresh-ad/ is at the funnel diagnosis; the ad is already chosen. Carry on with the diagnosis, then ask me to accept it.
