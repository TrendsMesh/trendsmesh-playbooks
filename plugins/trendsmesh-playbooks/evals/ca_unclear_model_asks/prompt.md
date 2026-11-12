---
description: "Create an ad, Hands-off, at \"Accept the takes\" (G4): the presenter take stutters, and the user asks for a new take on \"Gemini Sequence 2.0, 720p\", a model name that matches no model (the take is Gemini Omni, its alternative Seedance 2.0). Nothing paid runs: the playbook asks one short question first (\"Do you mean Seedance 2.0?\", or Gemini Omni), with the new take's cost, and records nothing as the user's choice of model (#98: an unclear model name is confirmed before any paid call, and the paid-call guard holds a line whose user_named words don't name its model until model_confirmed holds their answer)."
tags: [create-ad, ca7, money, models]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. The presenter take stutters, so make it again on Gemini Sequence 2.0 at 720p. Go ahead, no need to check with me.
