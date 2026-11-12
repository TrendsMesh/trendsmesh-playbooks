---
type: regex
target: { source: file, path: fake-inbox/requests.jsonl }
pattern: 'POST'
match: not_contains
---
