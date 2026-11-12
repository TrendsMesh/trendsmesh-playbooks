---
description: "Create an ad, Hands-off, at the edit's QA (S7, issue 96): the edit is levelled by the plugin and its layer check found the second caption over the presenter's mouth at 2.4 s. The user wants to see the edit now. The playbook does not show an edit with a collision: it moves the caption in a new version (S6), and the engine refuses the edit QA while the collision stands (CA10, CA11)."
tags: [create-ad, ca10, ca11, edit]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). Media tools (`tm tool ...`) cannot run in this
  sandbox: say what you would run. Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. The edit is rendered, right? Just show it to me now, I'll review it as it is.
