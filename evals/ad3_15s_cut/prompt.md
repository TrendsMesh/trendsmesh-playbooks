---
description: "Check-every-step run at CR4 (edit lists) on Ad 3. The cut points are handed to the agent (the G3r note and the skill's worked example): the case proves a legal level-0 edit list at the reference joint (11.146 s -> 20.735 s, about 14.5 s), the saved take looked up with tm recut music and reused, and the music as one segment, not a beat-cut edit (RC5, RC17). It does not prove that the agent finds the cut points."
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

My refresh run in runs/01-refresh-ad/ is at the re-cut's edit lists; the variants are already chosen. Make the edit list of the 15-second version now (the other variants can wait), check it, and tell me whether it is ready to render and where its music comes from.
