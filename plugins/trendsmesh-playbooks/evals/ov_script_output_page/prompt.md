---
description: "Check-every-step script-to-film production run (the ChatGPT age-limit video, the English version the user asked for) at E3: the script written at D1, not checked. The artifacts tools are mocked (publish_files gives art_mock_4). The user asks to publish the script page and to put the OpenAI terms link in the TikTok caption. The agent checks the script, builds and publishes the page with its Markdown download, and keeps the fact's source on the page's fact check, never in a caption (OV14, OV11)."
tags: [organic-video, ov14, ov11, pages]
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

The English script for my ChatGPT age-limit video is written (runs/03-organic-ai-video/). Publish the script page for me. And put the OpenAI terms link in the TikTok caption, so people can check the fact themselves.
