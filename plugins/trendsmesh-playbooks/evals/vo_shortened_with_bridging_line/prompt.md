---
description: "Check-every-step run at CR3 (variants) on ExampleTravel (voiceover, captions, music). The user asks for about 18 s with a bridging line and approves that variant: the picture and the voiceover are cut together at sentence gaps, flow V is turned on for the new line, and the edit list is checked as recut_new_vo_line; the new line connects the kept sentences (RC13)."
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

My refresh run in runs/01-refresh-ad/ is at the re-cut variants. Shorten the ad to about 18 seconds, cutting the picture and the voiceover together at the gaps between sentences. Where the shortened script no longer connects, add one new line in the original voice to bridge it. I approve that variant now, so you don't need to ask me about the variants again. Make its edit list and tell me the new line.
