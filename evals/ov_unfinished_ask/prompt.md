---
description: "An idea run of the ExampleEdu channel from 2026-11-06 is unfinished: its proposals page is published and waits for the user's choices (C2). The user asks for video ideas for the same channel without naming that run. The agent asks one short question first, whether to continue that run or start a new one, naming the run by its date and where it stopped, before any intake or trend search (issue 90: `tm run new` lists `unfinished_runs`)."
tags: [organic-video, runs]
max_turns: 30
timeout_seconds: 900
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

Give me some new short video ideas for the ExampleEdu channel, built on what's trending.
