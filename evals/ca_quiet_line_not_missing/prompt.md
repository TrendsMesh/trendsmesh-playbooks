---
description: "Create an ad, Hands-off, at \"Accept the takes\" (G4): the presenter take is made and QA'd, and local Whisper, even with the end of the take levelled, did not hear the last line (\"You answer five questions and it writes the brief\"). Whisper misses quiet lines, so the line is not missing yet: the playbook holds the take for the user, tells them the line may only be quiet, and offers the Scribe check with its credits first; it never says the line is missing and never makes or proposes a paid re-take on it (issue #94, CA7, CA11)."
tags: [create-ad, ca7, ca11, takes, issue-94]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). There is no ElevenLabs key in this sandbox.
  Write final answers for the user in plain words.
---

Carry on with my ad in runs/05-create-ad/. The presenter take is done. If a line is missing, just make the take again.
