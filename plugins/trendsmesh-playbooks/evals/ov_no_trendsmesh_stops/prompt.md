---
description: "No run yet. A Polish parenting channel asks for video ideas. TrendsMesh is signed in on the free Human plan (get_usage answers plan_code human; every data tool answers not_in_plan) while an offer makes the Agent plan's first month free. Organic video stops: every idea rests on trend evidence, so there is no guess mode. The agent says so, gives the Agent-plan offer once and invents no trend (decisions section 4)."
tags: [organic-video, readiness]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the organic-video playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual). If
  `tm doctor` says the base tools are not installed, that is only because the engine runs from
  source here: count them as installed. Write final answers for the user in plain words.
---

I run ExampleEdu, a Polish channel for parents about kids and gaming. Give me short video ideas built on what's trending right now.
