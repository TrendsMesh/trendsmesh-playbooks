---
description: "Hands-off run at the funnel diagnosis on Ad 3-shaped data: the hook fades, the retention steps hold (RC1), and the same file runs in 4 ads that are all weakest at p75/p50, 12.07-18.11 s (RC2). With diagnosis.structural_recut false the weakness is reported as an opportunity, never re-cut (RC3)."
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

My refresh run in runs/01-refresh-ad/ is at the funnel diagnosis (Hands-off); the ad is already chosen. Do only the diagnosis for now: work out which part of the ad is fading, check the video file itself too, and tell me what you found and what the run will change. Stop there, before the step that gets the video file.
