---
type: regex
target: mock_calls
# the page is not published again to read a choice: the fixture published it without a mock call
pattern: 'publish_files|declare_capabilities'
match: not_contains
---
