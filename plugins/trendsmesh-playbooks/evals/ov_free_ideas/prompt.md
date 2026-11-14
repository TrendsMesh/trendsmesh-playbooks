---
description: "No run yet. The user chose Free earlier (the workspace's tm mode is free) and asks for video ideas for a Polish parenting channel. The run goes on Free (issue #106): it records evidence guess, writes and checks its guessed trends (tm organic guesses check), and its ideas name where each trend was seen, are labelled guesses, are Inspire only, say what TrendsMesh would add, and never give a lifecycle stage or a count of their own."
tags: [organic-video, free-paid]
max_turns: 90
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the organic-video playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual). If
  `tm doctor` says the base tools are not installed, that is only because the engine runs from
  source here: count them as installed. There is no web access in this sandbox. The date today is
  2026-11-14. Write final answers for the user in plain words.
---

I run ExampleEdu, a Polish channel for parents about kids and gaming (TikTok and Instagram, short videos, we film ourselves, no store). Give me 4 short video ideas for this week. Just show me the ideas here in chat when you have them; skip any page and stop there.
