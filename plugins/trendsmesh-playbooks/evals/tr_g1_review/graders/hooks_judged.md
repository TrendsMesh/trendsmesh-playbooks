---
type: regex
target: { source: file, path: runs/04-trend-research/2026-11-04_beauty/03_wip/hook_use_v01.json }
# Issue #3, item 5: whether the category uses each shortlisted hook is the agent's judgement of its
# captions (tm research hook-captions), with one line on why: no category words are matched.
pattern: '(?=[\s\S]*"in_category"\s*:\s*(true|false))(?=[\s\S]*"category_videos"\s*:\s*\d)(?=[\s\S]*"why"\s*:\s*"[^"]{8,})'
---
