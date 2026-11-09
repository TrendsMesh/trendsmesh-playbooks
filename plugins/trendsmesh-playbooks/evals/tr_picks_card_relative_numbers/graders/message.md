---
type: llm
focus: last_message
---

PASS if the final message is the check-in to approve the picks and all of these hold:
- each pick's numbers open with its position in the category's sample: its band (such as "top 10%
  of beauty topics", "lower half") and its velocity index as a multiple of a typical trend (such as
  "2.3x the new creators of a typical beauty trend"), both, and its raw counts come after that,
  with the sample they come from;
- creator counts are said as creators in TrendsMesh evidence (those words, or plainly the same:
  the creators in the evidence videos TrendsMesh holds), not as creators on TikTok or in the
  market;
- the eyelash extensions pick's risk says that most of its evidence is in another language
  (Russian), so its fit for the US is uncertain;
- anything not shown by the data (a fit for the US market, an angle that rests on a couple of
  videos, what will happen next) is worded as a hypothesis, a guess or a risk, never as a finding;
- it asks the user to approve the picks (or say what to change) and waits.
FAIL if any pick leads with raw counts, or gives its band without the multiple of a typical trend
or the multiple without its band, if
creators are counted as if they were all of TikTok, if the eyelash pick's language risk is
missing, if a hypothesis is stated as a fact, or if it publishes or builds the page before the
answer.

The run's language is English; judge meaning, not exact wording.
