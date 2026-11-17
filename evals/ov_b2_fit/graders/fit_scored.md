---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/03_wip/trend_fit_v01.json }
# the agent's fit scores: the seven CB3 criteria and a why for a hook (issue #84)
pattern: '"brand_fit":\s*[1-5][\s\S]*"feasibility":\s*[1-5][\s\S]*"why":\s*"[^"]{8,}"'
---
