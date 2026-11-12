---
description: "Check-every-step AI video production run (the ChatGPT age-limit host video) at F1, its images check-in on the run page (issue #60), published as art_mock_8 and awaited. The artifacts tools are mocked: db_list holds the choice saved on the page: images accept, the second host image picked and accepted, with the note \"cieplejsze światło, ale bez filtra\". The agent reads the decisions with one unfiltered db_list, records them with tm page decision images --record (never the old images page's tm organic decisions), quotes the note back as the user's words, and never republishes the page."
tags: [organic-video, pages, issue-60]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the organic-video playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual). If
  `tm doctor` says the base tools are not installed, that is only because the engine runs from
  source here: count them as installed. Write final answers for the user in plain words.
---

The images for the ChatGPT age-limit video are on its page in runs/03-organic-ai-video/. I picked there and left a note. Read it and carry on.
