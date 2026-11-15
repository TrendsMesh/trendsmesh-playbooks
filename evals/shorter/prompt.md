---
description: "Check-every-step run at E1 (test design); the accepted re-cut is a 15 s version of a 24 s ad. R4 judges it by cost per result with the average watch time beside it, never by ThruPlay or completions (RC18)."
tags: [recut]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05, so add `--today 2026-11-05` to `tm r1`. Write final answers for the
  user in plain words. This sandbox has no media files: the video and music files in the
  run folder are placeholders, and the run already holds what the media tools made from the real
  files (the teardown, the transcript, the segment map).
---

My refresh run in runs/01-refresh-ad/ is at the live test design; the 15-second re-cut is accepted. Carry on with the test design, then ask me to approve the test plan. Tell me how the test will judge the shorter version.
