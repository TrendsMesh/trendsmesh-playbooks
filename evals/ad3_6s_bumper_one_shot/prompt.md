---
description: "Check-every-step run at CR4 on Ad 3: the 6 s bumper is one segment of one continuous shot (no cut to the CTA shot), 6 s, the ad's own music from its start, the hook card pre-typed and the CTA typed into the same card at 3 s; tm recut check says ok (RC9)."
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

My refresh run in runs/01-refresh-ad/ is at the re-cut's edit lists; the variants are already chosen. Make the edit list of the 6-second bumper now (the other variants can wait), check it, and tell me which seconds of the original it uses and how the hook and the call to action appear in it.
