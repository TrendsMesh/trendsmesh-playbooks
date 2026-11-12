---
type: regex
target: { source: file, path: runs/05-create-ad/2026-11-11_planner/03_wip/page/ask_plan_v01.json }
# the engine saved the agent's ask for the plan's check-in, with its options
pattern: '"checkin":\s*"plan"[\s\S]*"options":\s*\['
---
