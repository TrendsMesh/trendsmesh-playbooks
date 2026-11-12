---
description: "Check-every-step idea run at B2 (the walkthrough's 17 searches saved), English pages. Issue #84: the shortlist ranks hooks and formats by their fit for the channel, not by niche words. The agent runs the shortlist, scores every hook of fit_candidates on the seven CB3 criteria with a why, runs the shortlist again with --fit, and stops before pulling cards (no TrendsMesh tools here)."
tags: [organic-video, ov2, shortlist]
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

My ExampleEdu ideas run in runs/03-organic-ai-video/ has its trend searches saved. Make the shortlist now, and stop there: I'll pull the cards in a later session.
