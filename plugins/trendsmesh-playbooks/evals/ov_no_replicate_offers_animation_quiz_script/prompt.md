---
description: "Check-every-step idea run at C1 (research done: the walkthrough's searches, shortlist, cards and videos), English pages, the stack without a Replicate token and without artifacts tools. The user wants ready AI videos. AI footage and talking characters need Replicate, so the proposals hold none of them; the agent says why and offers animation, a quiz or ranking, or a script (VARIANTS 1)."
tags: [organic-video, variants, readiness]
max_turns: 80
timeout_seconds: 2400
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

Carry on with my ExampleEdu ideas run in runs/03-organic-ai-video/. I want ready AI videos, not scripts to film.
