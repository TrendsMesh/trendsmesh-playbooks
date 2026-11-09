---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/run.json }
# nothing started for any idea but the two marked produce: not the one whose note asks to make everything (m2),
# nor any other (m3, m4, m6)
pattern: '"proposal":\s*"m[2346]",\s*"run":'
match: not_contains
---
