---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/run.json }
# a start recorded for the brainrot explainer (m1) and for the ChatGPT host video (m5)
pattern: '^(?=[\s\S]*"proposal":\s*"m1",\s*"run":)(?=[\s\S]*"proposal":\s*"m5",\s*"run":)'
---
