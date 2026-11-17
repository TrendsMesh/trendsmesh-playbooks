---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-07_exampleedu-m5/manifest.md }
# no Replicate call: the guard writes this row for every paid run (the fixture's own records are rows of another source)
pattern: 'Replicate run record'
match: not_contains
---
