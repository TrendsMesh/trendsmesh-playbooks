---
type: llm
focus: last_message
---

PASS if the final message is the check-in to accept the category map and gives all of these: the
sub-categories (or groups) of the map, each with its number of trends; what was dropped and why,
the dementia trend among them as off-category (it matched "anti-aging" on ageing, not beauty), so
the user can restore any; the Halloween trends kept (seasonal trends inside the category are not
noise); the hooks shortlisted by fit, saying which are already used in the category and which are
transfers (they fit, but no category video uses them yet), each with a short reason read from its
videos' captions and with what the Ad Library showed
for it (none found in Ad Library titles: the mocked search returns only unrelated ads); and it asks the user to accept the map
(or say what to change) and waits.
FAIL if it drops a shortlisted hook only because no category video uses it yet, says a hook is
unused or not in ads, if it drops the
Halloween trends as off-category or noise, keeps the dementia trend without a
word, gives no counts, says there are no trends in the category, or goes past the map check-in
(fetches every trend's evidence videos or computes growth) without the user's answer.

The run's language is English; judge meaning, not exact wording.
