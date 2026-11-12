---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/03_wip/proposals_v01.json }
# the first proposals written: a look in words on the proposals, and an animation's suggested styles, each with
# its why. The first file on purpose: the skill asks for both in the first draft, which the check does not force
pattern: '^(?=[\s\S]*"aesthetic":\s*"[^"\s][^"]*")(?=[\s\S]*"production":\s*"animation")(?=[\s\S]*"styles":\s*\[\s*\{[^\]]*"why":\s*"[^"\s])'
---
