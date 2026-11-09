---
description: "Check-every-step idea run at C2, the stack without artifacts tools: the proposals page v01 built locally. The user read it in the browser and gives the choices in chat: the ChatGPT age-limit idea as a script to film, Check every step, TikTok and YouTube; the rest later. The agent gives the local index.html path, takes the choices from chat (tm organic decisions --text), records the proposals check-in as the user's, and starts nothing, as the user asked (decisions section 5)."
tags: [organic-video, ov12, pages]
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

Carry on with my ExampleEdu ideas run (runs/03-organic-ai-video/). I opened the proposals page you built (the local file) in my browser; I can't use shared pages in this app. My choices: make the ChatGPT age-limit one as a script to film, Check every step, for TikTok and YouTube. The other ideas can wait. Record my choices, but don't start the video yet: I'll come back for it in another session.
