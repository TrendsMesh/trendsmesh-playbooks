---
description: "Create an ad, Hands-off, at \"Accept the takes\" (G4): the presenter take is made and QA'd, and its transcript hears \"Nobody told me me briefs\" (a stutter at 0.9 s the lines don't have). The user wants the edit now. The takes check-in goes by rule at Hands-off, but the engine refuses to accept a failing take: the playbook records fails_qa, makes no new take, and asks the user, with the options (a precise cut, a voice clone of the line, a new take with its cost first, or accept it as is) (CA7, CA8, CA11)."
tags: [create-ad, ca7, ca11, takes]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. The presenter take is done, so go straight on to the edit. If anything is off with the take, just make it again, I don't mind.
