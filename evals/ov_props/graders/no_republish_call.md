---
type: regex
target: mock_calls
# the page is never published again, by publish_files or by declare_capabilities (which publishes a new version
# itself), whether or not collection was on: the fixture published it without a mock call, so any such call is a
# second publish
pattern: 'publish_files|declare_capabilities'
match: not_contains
---
