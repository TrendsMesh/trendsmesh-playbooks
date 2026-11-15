---
description: "No run yet. The Replicate token is set but Replicate refuses it (401): the doctor shows it as connected but unusable, and the user hears that it is wrong or revoked, where to make a new one and where to put it, without being asked for the key in chat."
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

Before I start: am I ready to make AI videos with the refresh-ad playbook? My Meta ad account is 9990000001. I set my Replicate token in the plugin settings yesterday. Check my setup and tell me what is missing, if anything.
