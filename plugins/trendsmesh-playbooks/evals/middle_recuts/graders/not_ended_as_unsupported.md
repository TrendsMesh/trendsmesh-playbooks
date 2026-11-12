---
type: regex
target: { source: file, path: runs/01-refresh-ad/2026-11-05_ad/run.json }
pattern: '"choice":\s*"do_not_refresh"'
match: not_contains
---
