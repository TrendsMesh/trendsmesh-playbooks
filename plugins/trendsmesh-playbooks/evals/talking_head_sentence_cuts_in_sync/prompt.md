---
description: "Check-every-step run at CR4 on ad_2 (talking head, word captions): the sentence and pause cuts and the cold open are cut in sync mode at caption switches and speech gaps, the cold open starts with the ten-minute practice line and drops its set-up question; tm recut check says ok for both (RC10, RC11)."
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

My refresh run in runs/01-refresh-ad/ is at the re-cut's edit lists; the variants are already chosen. Make both edit lists: for the shorter one, cut the slow sentences and the 1.38-second pause; for the cold open, start with the strongest line. Check them and tell me what each one keeps.
