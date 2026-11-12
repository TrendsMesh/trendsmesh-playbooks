---
type: regex
target: { source: file, path: runs/03-organic-ai-video/2026-11-06_exampleedu/03_wip/proposals_v01.json }
# the first proposals written, with an animation or stills idea among them, none AI footage or a talking character.
# The first file on purpose: the stack's hidden types are known before C1 (the A0 stack answer, the user's
# request), so a first draft that proposes them is the miss under test, which the engine's refusal would hide
pattern: '^(?![\s\S]*"production":\s*"(ai_footage|talking_character)")[\s\S]*"production":\s*"(animation|stills_motion)"'
---
