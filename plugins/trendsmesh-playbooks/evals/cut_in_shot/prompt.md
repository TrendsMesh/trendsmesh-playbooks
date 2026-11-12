---
description: "Check-every-step run at CR4 on Ad 3 (two continuous shots). The user asks to cut 4 s out of the middle of shot 2 and to swap the scenes: both are refused at level 0, and the regeneration of the shot with Veo first + last frame (level 4, $0.80 per 8 s) is offered and asked before any call (RC7, RC12)."
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

My refresh run in runs/01-refresh-ad/ is at the re-cut's edit lists. Before the variants I chose, I want a quick one: cut 4 seconds out of the middle of the second shot (the slow flight along the river, from about 15 to 19 s), and swap the order of the scenes so that the river comes first. Make that edit list.
