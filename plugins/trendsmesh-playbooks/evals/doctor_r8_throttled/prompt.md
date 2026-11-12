---
description: "No run yet. Replicate throttles the account (429, as it does for an account with no payment method): the user hears to wait, or to add a payment method at the billing page, not that the token is wrong."
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
