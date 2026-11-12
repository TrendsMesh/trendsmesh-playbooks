---
description: "Run at the winner's source file with an empty brand folder: the run stops (missing_video) and gives the Ads Manager link of the ad."
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

Continue my refresh run in runs/01-refresh-ad/. My brand assets folder is the brand/ folder in this directory.
