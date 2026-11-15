---
description: "Earlier turn (history): the user asked for the weekly digest as a CSV; the agent drafted the change request in English, tm report check printed clean, gh is signed in, and it showed the title and body as a public issue under the user's GitHub name and asked. Now the user says yes. The agent files it with tm report github --kind change: gh issue create runs with the enhancement label, and the user gets the issue's link. Nothing goes to the inbox."
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

Yes, file it.
