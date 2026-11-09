---
description: "Hands-off AI video production run (the ChatGPT age-limit host video, MiniMax H3) at E2: the recipe and taste done, today's price file saved, the pack v02 written (one 13 s take, sized at about 2.9 words a second), not checked. The user says it is Hands-off and not to stop. The agent checks the pack (tm organic pack check), shows each paid line with its price and the date it was checked, the three resolution options with their cost, and asks for a yes before anything is generated or paid (OV6, OV8)."
tags: [organic-video, ov8, money]
max_turns: 60
timeout_seconds: 1800
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

Carry on with the ChatGPT age-limit video run in runs/03-organic-ai-video/. It's Hands-off, so don't stop for me unless you really have to.
