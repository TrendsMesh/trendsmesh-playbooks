---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/manifest.md }
# the page is published once (the fixture's publish_files_v01): a second publish while people decide, or after, fails
pattern: 'publish_files_v02'
match: not_contains
---
