---
description: "No run yet. The ElevenLabs key works but the account has used all its credits this month: the doctor shows it as connected but unusable, and the user hears to add credits or pick a bigger plan, with the link."
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

Before I start: am I ready to refresh my fading ad with the refresh-ad playbook, including a new voiceover line in the same voice? My Meta ad account is 9990000001. My ElevenLabs key is set in the plugin settings. Check my setup and tell me what is missing, if anything.
