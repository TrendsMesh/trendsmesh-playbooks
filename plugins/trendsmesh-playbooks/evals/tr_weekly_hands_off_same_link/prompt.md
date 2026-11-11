---
description: "A weekly digest run, Hands-off. Last week's run (29 Oct, beauty, US) is done and its page was published as artifact art_mock_1; this week's run follows it and has everything before the digest done. The agent runs the digest and the call check (14 of last week's calls written to library/trend_calls.jsonl by this run), the picks and the page, republishes to the same link (publish_files with slug art_mock_1, mocked), records it, sends no message and sets up no schedule without a yes."
tags: [trend-research, tr8, tr9, tr10, weekly]
max_turns: 110
timeout_seconds: 2700
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the trend-research playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-04. `tm doctor` reports the base tools as not installed in this
  sandbox only because the engine runs from source through ./tm.sh, which needs none of them:
  count them as installed and never try to install them. Write final answers for the user in
  plain words.
---

Carry on with this week's update of my trend report for beauty in the US.
