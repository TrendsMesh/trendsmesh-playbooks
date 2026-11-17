---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/03_wip/map_review_v01.json }
# Every seasonal trend inside the category is guarded (makeup, face paint, costume looks, nails):
# Catrina, Joker, Deer, the general Halloween makeup trend, Art the Clown (white face paint), Corpse
# Bride (blue-grey skin) and Halloween nails. Only Ghostface (a mask, cupcakes and crafts: no makeup
# in its card) may be dropped as off-category, with a reason (controller's ruling, fix round 1).
pattern: '"drop"\s*:\s*\{[^}]*(Catrina makeup|Joker Halloween makeup|Deer Halloween makeup|Halloween makeup and costume transformations|Art the Clown|Corpse Bride|Halloween nail art)'
match: not_contains
---
