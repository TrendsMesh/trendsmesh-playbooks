---
description: "No run yet, TrendsMesh not signed in. The user says up front they don't want TrendsMesh. The agent records the skip (tm signin skip), doesn't ask them to sign in or pitch the plan, and says the playbook runs without it with its changes as best guesses."
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

Before I start: am I ready to refresh my fading ad with the refresh-ad playbook? Creative brief only. My Meta ad account is 9990000001. I don't want to sign in to TrendsMesh or hear about its plans, so leave it out. Check my setup and tell me where I stand.
