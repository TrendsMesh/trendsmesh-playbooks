---
description: "Issue #7. A trend research run (beauty, US, Check every step) is unfinished at the relevance review (B3), and the user asks for trend research on another category without mentioning it. The agent asks one short question first, naming the unfinished run (what it is about, its date or step): continue it, or start a new one. It neither resumes the beauty run nor starts a new run, and calls no TrendsMesh tool before the answer."
tags: [trend-research, resume]
max_turns: 20
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. Write final answers for the user in plain words.
---

I'd like trend research for pet food in the UK: which trends to act on now.
