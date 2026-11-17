---
description: "No run yet. The user wants a fading ad refreshed with a new voiceover line and says their ElevenLabs plan has no voice cloning: the doctor runs with --voice and elevenlabs_plan=no_cloning, and the missing cloning is a note that matters only at the voice step, not a reason to stop or to send the user to upgrade now."
tags: [whole-run]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05, so add `--today 2026-11-05` to `tm r1`. Write final answers for the
  user in plain words.
---

Before I start: am I ready to refresh my fading ad with the refresh-ad playbook, including a new voiceover line in the same voice? My Meta ad account is 9990000001. My ElevenLabs key is set; my ElevenLabs plan is the cheap one, without voice cloning. Check my setup and tell me what is missing, if anything.
