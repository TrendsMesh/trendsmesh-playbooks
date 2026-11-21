---
type: regex
target: mock_calls
# an organic video brief reads no ad account: no Meta Ads tool is called (issue #136)
pattern: 'ads_'
match: not_contains
---
