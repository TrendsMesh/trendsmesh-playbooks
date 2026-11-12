---
description: "Check-every-step refresh run at the \"Accept the diagnosis\" check-in (G1a), the ranking and the diagnosis done, in a session with no tool to publish artifacts. The agent puts the check-in on the run page built by the engine (an ask in the run's language, then `tm page build --local`, issue #19), never writes the page by hand, gives the local page's path, asks the check-in in chat and records nothing before the user answers."
tags: [refresh-ad, pages, issue-19]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual). This
  sandbox has no Meta connection: the run already holds the ranking and the diagnosis. Write final
  answers for the user in plain words.
---

My run in runs/01-refresh-ad/ is waiting for me. Carry on from where it stopped.
