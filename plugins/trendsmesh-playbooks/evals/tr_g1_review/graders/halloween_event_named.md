---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/03_wip/map_review_v01.json }
# Issue #3, item 5: the review names each kept seasonal trend's event and its date (the market is the
# US, so in English): the seasonal guard reads it, no list of English holiday words.
pattern: '"events"\s*:\s*\{[\s\S]*"date"\s*:\s*"2026-10-31"'
---
