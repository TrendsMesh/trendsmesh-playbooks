---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/03_wip/map_review_v01.json }
# the engine sets the dementia trend aside below the best 50 by match (issue #129); the review never brings it back
pattern: '"restore"\s*:\s*\{[^}]*"Dementia in family life and memory"'
match: not_contains
---
