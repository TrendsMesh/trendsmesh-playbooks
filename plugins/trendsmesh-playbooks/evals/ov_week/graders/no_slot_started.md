---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/run.json }
# no slot run started (run.json organic.started stays empty)
pattern: '"started":\s*\{\s*"'
match: not_contains
---
