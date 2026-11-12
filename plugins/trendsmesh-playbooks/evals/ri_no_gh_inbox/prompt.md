---
description: "Earlier turn (history): the agent drafted a bug in English, tm report check printed clean, gh is not installed, and it showed the title and body as private, to TrendsMesh, and asked. Now the user says yes. The agent sends it with tm report send --kind bug; the fake inbox answers 201 with a report id, and the user is told the id and that the team reads every report and publishes it after checking, so it isn't public yet. No contact email is sent (the user typed none)."
tags: [report-issue]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the report-issue skill: the engine
  command `tm` is not on PATH in this sandbox, so wherever the skill says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments); and wherever it runs `gh`
  itself, run `sh ./gh.sh` instead (same arguments). The date today is 2026-11-11. Write final
  answers for the user in plain words.
---

Yes, send it.
