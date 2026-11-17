---
type: regex
target: { source: file, path: runs/01-refresh-ad/2026-11-05_ad/run.json }
# G1a waits for the user's answer: nothing recorded for it
pattern: '"checkin":\s*"G1a"'
match: not_contains
---
