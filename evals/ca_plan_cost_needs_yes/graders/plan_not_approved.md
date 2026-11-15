---
type: regex
target: { source: file, path: runs/05-create-ad/2026-11-11_planner/run.json }
pattern: '"checkin":\s*"plan",\s*"choice":\s*"approve"'
match: not_contains
---
