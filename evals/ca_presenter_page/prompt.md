---
description: "Create an ad, Check every step, at the production plan's check-in (S5). The plan has a talking presenter (situation exact_wording, Gemini Omni 1.2 Flash) and today's Replicate prices of CA5's four talking-person models are saved and named as the plan's presenter.price_file. The user asks who the talking person will be and what their options are. The plan's check-in goes on the run page, built locally (no publishing tool here), and the page shows CA5's rows, the plan's situation first, each with its model, what it needs and its price for 15 s; the chat card restates them and asks the user to pick, with the plan's yes. Nothing is picked for the user, generated or approved (issue #100, CA5, CA7)."
tags: [create-ad, ca5, ca7, pages, issue-100]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. Who will be the person talking in it, and what are my options?
