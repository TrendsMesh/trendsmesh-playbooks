---
type: regex
target: { source: file, path: library/trend_calls.jsonl }
pattern: '^.*"checked_in_run":\s*"2026-11-04_beauty".*$'
flags: m
match: count:14
---
