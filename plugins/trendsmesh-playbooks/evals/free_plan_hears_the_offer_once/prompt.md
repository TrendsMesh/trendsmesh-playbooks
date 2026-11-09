---
description: "No run yet. TrendsMesh is signed in on the free plan (get_usage answers plan_code human) while an offer makes the Agent plan's first month free. Readiness says the playbook can go on, and makes the offer once."
tags: [readiness, sign-in]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05. Write final answers for the user in plain words.
---

Before I start: am I ready to refresh my fading ad with the refresh-ad playbook? I only want the creative brief for now. My Meta ad account is 9990000001. Check my setup and tell me where I stand.
