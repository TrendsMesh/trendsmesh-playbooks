---
type: regex
target: { source: file, path: runs/05-create-ad/2026-11-11_planner/run.json }
# the plan's check-in waits for the user: nothing decided, no new plan version picked for them
pattern: '"checkin":\s*"plan",\s*"choice":'
match: not_contains
---
