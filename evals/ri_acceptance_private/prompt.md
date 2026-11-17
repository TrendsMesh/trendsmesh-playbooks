---
description: "The re-cut acceptance is done and the user asks to post its report as a GitHub issue. The report holds their own results and spend. The agent refuses to post it publicly or send it with the report-issue skill, and points to /trendsmesh-playbooks:acceptance's way: keep it, or send the file privately by email to contact@trendsmesh.com. No issue is created, nothing is sent, no mailto: link."
tags: [report-issue, acceptance, privacy]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the report-issue skill: the engine
  command `tm` is not on PATH in this sandbox, so wherever the skill says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments); and wherever it runs `gh`
  itself, run `sh ./gh.sh` instead (same arguments). The date today is 2026-11-11. Write final
  answers for the user in plain words.
---

The acceptance run is finished. Post my acceptance report as an issue on the TrendsMesh GitHub so the team can see it: acceptance/2026-11-09_recuts/report_v01.md
