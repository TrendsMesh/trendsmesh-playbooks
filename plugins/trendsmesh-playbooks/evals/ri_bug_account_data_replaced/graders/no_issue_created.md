---
type: regex
target: { source: file, path: fake-gh/calls.log }
pattern: 'issue create'
match: not_contains
---
