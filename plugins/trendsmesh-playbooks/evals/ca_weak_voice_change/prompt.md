---
description: "Create an ad, Check every step, at \"Accept the takes\" (G4): the presenter take is made and passes its QA. The user says the words and the timing are right, but the presenter's voice sounds thin and flat. The playbook offers the voice change first (tm tool elevenlabs sts: the take's own audio in another voice, the timing kept, so the lips still match), with its credits, and a voice to pick; it does not lay a new text-to-speech reading under the mouth, and does not make or propose a new take, since the lines are right (issue #95, CA6, CA7)."
tags: [create-ad, ca6, ca7, takes, issue-95]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
append_system_prompt: |
  Test harness notes, not from the user. If you are following the create-ad playbook: the engine command
  `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run `sh ./tm.sh ...` from the
  working directory instead (same arguments, add --json as usual). There is no ElevenLabs key in this sandbox.
  Write final answers for the user in plain words.
---

My ad is in runs/05-create-ad/. I watched the presenter take: the words and the timing are fine, but her voice sounds thin and flat. What do we do?
