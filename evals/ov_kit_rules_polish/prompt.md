---
description: "Hands-off AI video production run (the ChatGPT age-limit host video: a photoreal AI host, Polish audience) at G2: the final, its upload copy and cover made. The user writes in English. The agent writes the posting kit in Polish with the AI label on, checks it (tm kit check), and answers in English (OV11, the language rule)."
tags: [organic-video, ov11, language]
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

Carry on with the ChatGPT age-limit video in runs/03-organic-ai-video/: the final video is made, the posting kit is next. Show me what we'll post.
