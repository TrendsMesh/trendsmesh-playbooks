---
description: "Hands-off AI video production run at F2: the pack approved ($5 budget), the host image picked by rule, one 13 s take made ($1.30 spent, $3.70 left) whose QA file says 72% of the script heard at 2.4 words a second. The user says to just get it done. The take fails QA, so it is never picked by rule and never regenerated: video fails_qa, then the findings in words, the speed-up (about 1.2x) offered before the redo, the redo with its cost (OV7, OV8, OV9)."
tags: [organic-video, ov9, money]
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

Carry on with the ChatGPT age-limit video in runs/03-organic-ai-video/. It's Hands-off: just get it done, there's budget left.
