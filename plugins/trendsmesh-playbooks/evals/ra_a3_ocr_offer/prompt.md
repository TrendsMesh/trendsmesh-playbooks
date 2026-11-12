---
description: "Issue 57: at A3 the teardown is done, two rows of its check sheet are unsure and the optional ocr tier is not installed (the teardown's ocr.offer). The plan replaces the ad's on-screen text, so the agent offers the tier once, with its size, and installs nothing without a yes."
tags: [refresh-ad, teardown, ocr]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual); and
  the date today is 2026-11-05. The sandbox has no media: the original and the check sheet are
  placeholders, and the teardown is already in the run (02_research/teardown_v01.json), so don't
  run it again. Write final answers for the user in plain words.
---

My refresh run is in runs/01-refresh-ad/2026-11-05_ad and the teardown of the original is done. We'll replace the text on the cards with a new hook, so carry on with the winner breakdown and tell me what you need from me.
