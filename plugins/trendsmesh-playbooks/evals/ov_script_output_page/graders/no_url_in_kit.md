---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-07_exampleedu-m5/04_final/m5_script_en_v01/m5_script_v01.md }
# nothing of a source anywhere in the posting kit's captions, titles and descriptions: no link, no bare domain, no
# "Source" or "Źródło" (the engine's script check refuses all three; the fact check after the kit keeps its
# source). No \b around Źródło: without the u flag a JS \b takes Ź for a non-word character.
pattern: '## Posting kit(?:(?!## Fact check)[\s\S])*(https?://|\b[\w-]+\.(com|org|net|pl|io|ai)\b|\bSources?\b|Źródło)'
match: not_contains
---
