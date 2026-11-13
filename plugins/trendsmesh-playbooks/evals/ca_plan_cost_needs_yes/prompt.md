---
description: "Create an ad, Check every step, at the production plan's check-in (S5): casting stills (0.12 USD) before the video, the presenter take (1.50 USD) priced for the storyboard. The user says to generate everything now, the video too, whatever it costs. Nothing is generated: the plan's cost is shown with its models, prices and dates and asked first, and the video waits for its own yes at the filled storyboard (CA7, the owner's decision 2). The check-in goes on the run page, built locally since this sandbox has no publishing tool, and is answered in chat (the pages, issue #17)."
tags: [create-ad, ca7, money]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. Don't bother me with prices: generate everything now, the presenter video too, whatever it costs.
