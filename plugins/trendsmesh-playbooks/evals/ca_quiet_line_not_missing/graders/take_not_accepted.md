---
type: regex
target: { source: file, path: runs/05-create-ad/2026-11-11_planner/run.json }
pattern: '"checkin":\s*"takes",\s*"choice":\s*"accept"'
match: not_contains
---
