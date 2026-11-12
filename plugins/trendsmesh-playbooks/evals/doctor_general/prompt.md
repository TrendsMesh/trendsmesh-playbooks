---
description: "No run yet, no keys set, TrendsMesh signed in. The user asks to check the plugin without naming a playbook. The doctor runs the general check (tm doctor --general: the base tools, the keys' states, the TrendsMesh sign-in) and never calls or waits for Meta Ads; the result names no playbook's readiness check, reports both keys as missing but not blocking, and says how to check one playbook (issue 76)."
tags: [readiness, doctor]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. The engine command `tm` is not on PATH in this sandbox, so
  wherever the plugin says `tm ...`, run `sh ./tm.sh ...` from the working directory instead (same
  arguments, add --json as usual). Write final answers for the user in plain words.
---

I just installed the TrendsMesh playbooks plugin. Can you check that everything is set up on my computer?
