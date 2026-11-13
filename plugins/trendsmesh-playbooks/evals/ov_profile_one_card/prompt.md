---
description: "No run yet. A Polish parenting channel about kids and gaming asks for video ideas. TrendsMesh is on the Agent plan (the shared mock); no artifacts tools. The agent makes the run, reads the stack, and asks the A0 intake in one batch (the output, the resolution, the budget and how involved among them), its assumptions marked, nothing about the voice or the music, and offers the content-rules line for a children's niche (OV1, A1)."
tags: [organic-video, ov1, intake]
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

I run ExampleEdu, a Polish channel for parents about kids and gaming: screen time, Roblox, staying safe online. I'd like short videos built on what's trending right now. Can you set that up for me?
