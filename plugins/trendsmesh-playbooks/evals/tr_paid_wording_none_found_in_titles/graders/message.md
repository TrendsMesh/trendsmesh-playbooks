---
type: llm
focus: last_message
---

PASS if the final message tells the user what the Ad Library check found, and says of the trends
with no relevant advertiser that none was found in Ad Library titles (or the same in other plain
words: the Ad Library search returns ad titles only, so this is about titles), and says the hooks
(opening structures such as "day _ of _", "your sign to _", "get ready with _ to _") cannot be
checked there (for example "Not checkable without Foreplay").
FAIL if it says or implies that a trend is "not in ads", "not advertised", "no one runs ads on
it" or "free of paid competition" as a fact about all ads, or treats the unrelated matches
(fridge shelves, fitness apps, novels) as advertisers of a trend, or gives a hook a paid level
from the titles.

The run's language is English; judge meaning, not exact wording.
