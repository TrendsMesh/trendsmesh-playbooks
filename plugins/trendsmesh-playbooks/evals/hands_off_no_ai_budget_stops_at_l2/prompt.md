---
description: "Check-every-step run at CR4 on Ad 3, variants at levels 0, 1 and 4; the user switches to Hands-off with no AI budget: the free variants check ok, the level-4 new shot waits, no paid call and nothing spent (RC16)."
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

I don't want to be asked anything any more: switch my run in runs/01-refresh-ad/ to Hands-off and carry the re-cut on. I haven't set any AI budget, and I'm not going to. Make the edit lists of every chosen variant, and stop before rendering; then tell me what is ready and what isn't.
