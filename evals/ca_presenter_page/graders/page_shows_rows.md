---
type: regex
target: { source: file, path: runs/05-create-ad/2026-11-11_planner/04_final/run_page_v01/index.html }
# the engine's page shows CA5's rows, the plan's situation (exact wording, Gemini Omni) first, each priced for 15 s
pattern: 'The talking person: which model makes it[\s\S]*Exact wording needed[\s\S]*1\.58 USD for 15 s[\s\S]*A person generated from a description[\s\S]*2\.70 USD for 15 s'
---
