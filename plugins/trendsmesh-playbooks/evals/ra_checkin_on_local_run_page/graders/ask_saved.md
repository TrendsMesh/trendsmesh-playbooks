---
type: regex
target: { source: file, path: runs/01-refresh-ad/2026-11-05_ad/03_wip/page/ask_G1a_v01.json }
# the engine saved the agent's ask for the diagnosis check-in, with its options
pattern: '"checkin":\s*"G1a"[\s\S]*"options":\s*\['
---
