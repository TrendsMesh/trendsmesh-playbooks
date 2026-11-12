---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-07_exampleedu-m5/run.json }
# run.json checked.kit: a kit passed tm kit check (none at the start), whichever version. The check refuses a kit
# whose language is not the audience's (pl) and one with the AI label off for this AI host (both tried on the
# fixture), so a recorded check is the kit in Polish with the AI label on. It also refuses a kit without rules_read
# (posting-kit.md's date) or without the search phrase leading TikTok's first line (issue #91).
pattern: '"kit":\s*\{\s*"file":\s*"04_final/kits/m5_kit_v\d+\.json"'
---
