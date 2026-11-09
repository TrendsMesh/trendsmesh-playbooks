---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/run.json }
# the user asked to record the choices and start nothing yet: no production run started (run.json organic.started)
pattern: '"started":\s*\{\s*"'
match: not_contains
---
