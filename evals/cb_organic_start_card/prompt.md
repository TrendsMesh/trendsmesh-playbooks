---
description: "No run yet; TrendsMesh (mocked) answers as a paid plan, and a Meta Ads connection (mocked) is there but must not be used. The user asks creative-brief for a brief for an organic video on their home bakery channel, not an ad (issue #136). The agent starts a creative brief run, records what the brief is for from the user's own words (tm decide brief_kind organic --said), runs the doctor with --outputs organic_brief,page and no Meta, finishes A0, and shows the organic video brief's start card (O1) in one message, asking whether the channel is a business account. No Meta tool is called, nothing about the ad account or customer reviews is asked."
tags: [creative-brief, organic, intake, issue-136]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the creative-brief playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-07. If `tm doctor` says the base tools are not installed, that is only
  because the engine runs from source here: count them as installed. Write final answers for the
  user in plain words.
---

I need a creative brief for an organic video for my home bakery channel, Example Bakery, on TikTok and Instagram. It's not an ad: we film and post it ourselves. Can you set it up?
