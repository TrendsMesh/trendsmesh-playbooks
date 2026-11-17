---
type: regex
target: trace
# the images check-in is a stage of the run page now: never read with the old images page's reader
pattern: 'tm\.sh\s+(--\S+\s+)*organic\s+decisions\b[^\n]*gate_images'
match: not_contains
---
