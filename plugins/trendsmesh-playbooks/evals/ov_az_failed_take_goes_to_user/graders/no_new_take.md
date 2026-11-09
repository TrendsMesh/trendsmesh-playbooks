---
type: regex
target: files
# no second take (a take_v02 record or output) and no re-planned pack for a redo (pack_v03) among the changed files
pattern: 'take_v02|pack_v03'
match: not_contains
---
