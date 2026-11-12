---
type: regex
target: mock_calls
# the general check never looks at Meta Ads: no Meta Ads tool is called
pattern: 'ads_'
match: not_contains
---
