---
description: "Just-the-big-calls week run at I2: the week plan (five slots, $5 for the week) checked, its page built, published as art_mock_5 and awaited. The artifacts tools are mocked: db_list holds the user's choices: Monday swapped for the reserve Switch 2 host video (1080p, $3.26) and every day a video, $6.20, with the page's own approval. The user says approve and start. The agent reads the choices, the approval is refused over the budget, and it names the overrun and the three ways out and asks (weekly pack, I2)."
tags: [organic-video, weekly, money]
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

My week plan for ExampleEdu is on the page (runs/03-organic-ai-video/). I've made my choices there and I'm done: approve the week and start making the videos.
