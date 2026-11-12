---
description: "Issue 3. A new Organic AI video run at the intake (A1), no artifacts tools. The user writes in English about a Polish channel and wants to read everything in English. The agent asks the setup questions in one batch (on the intake page or in one message), with both languages as defaults to confirm: English for what the user reads, Polish for the audience's post text, captions and speech. No ideas or trends before the answers."
tags: [organic-video, languages, intake]
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

I run ExampleEdu, a channel for Polish parents about kids and gaming: screen time, Roblox, staying safe online. The videos are in Polish, but I'd rather read everything you send me in English. Can you set up short videos built on what's trending right now?
