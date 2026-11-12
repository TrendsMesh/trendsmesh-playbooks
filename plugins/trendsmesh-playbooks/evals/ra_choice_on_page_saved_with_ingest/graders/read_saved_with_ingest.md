---
type: tool_used
# a Refresh an ad run has no collector: the page's read reaches the run with ingest (issue #54)
tool: Bash
input_match: 'tm\.sh\s+trends\s+ingest\b[^\n]*db_list'
min: 1
---
