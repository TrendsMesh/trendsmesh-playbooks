---
type: regex
target: trace
# the kit check must not be given the override flags: --audience-language en or --ai-label not_required would make a
# kit in the chat language, or without the AI label, pass the engine's check. The profile and the pack decide both.
pattern: 'tm\.sh[^\n]*kit\s+check[^\n]*--(audience-language\s+en|ai-label\s+not_required)'
match: not_contains
---
