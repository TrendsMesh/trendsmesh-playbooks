---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/run.json }
# the week is not approved over its budget
pattern: '"checkin":\s*"week",\s*"choice":\s*"approve"'
match: not_contains
---
