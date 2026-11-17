---
type: regex
target: { source: file, path: fake-inbox/requests.jsonl }
# the user typed no email, so no contact goes with the report
pattern: '"contact"'
match: not_contains
---
