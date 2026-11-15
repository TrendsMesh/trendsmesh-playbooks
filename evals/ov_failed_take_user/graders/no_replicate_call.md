---
type: regex
target: trace
# no paid call and no redo request run by the agent: the skill writes these commands as `tm tool ...` and
# `tm organic redo`, the harness note only as `sh ./tm.sh ...`, so only an agent's own call holds `tm.sh tool
# replicate_run` or `tm.sh organic redo` (any `sh`/`bash`/`./` form, with or without --json)
pattern: 'tm\.sh\s+(--\S+\s+)*(tool\s+replicate_run|organic\s+redo)'
match: not_contains
---
