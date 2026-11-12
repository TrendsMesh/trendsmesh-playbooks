---
description: "Check-every-step refresh run at the \"Accept the diagnosis\" check-in (G1a), with the check-in on the run page, published as art_mock_7. The artifacts tools are mocked: db_list holds the choice saved on the page (refresh, with the note \"Tylko nie ruszajcie logo na końcu\"). Refresh an ad has no collector (issue #54), so the agent reads the decisions with one unfiltered db_list, saves that read with tm trends ingest, records the choice with tm page decision --record, quotes the note back, and never republishes the page."
tags: [refresh-ad, pages, issue-54]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write]
env:
  EVAL_TM_SOURCE_ENGINE: "1"   # the collector hook runs the plugin's engine source with python3 (bootstrap/collect-mcp.sh)
append_system_prompt: |
  Test harness notes, not from the user. If you are following the refresh-ad playbook: the
  engine command `tm` is not on PATH in this sandbox, so wherever the playbook says `tm ...`, run
  `sh ./tm.sh ...` from the working directory instead (same arguments, add --json as usual). This
  sandbox has no Meta connection: the run already holds the ranking and the diagnosis. Write final
  answers for the user in plain words.
---
My refresh run in runs/01-refresh-ad/ has the diagnosis on its page. I chose there and left a note. Carry on.
