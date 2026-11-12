---
description: "Check-every-step idea run at the profile check-in, English pages: the ExampleEdu profile v01 drafted and saved, its type How-to and education. Issue #85: the card shows the channel type, says it sets how many trends of each kind are pulled, and asks for corrections; nothing is searched before the user's yes."
tags: [organic-video, ov1, ov2, profile]
max_turns: 40
timeout_seconds: 1200
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

Carry on with my ExampleEdu ideas run in runs/03-organic-ai-video/.
