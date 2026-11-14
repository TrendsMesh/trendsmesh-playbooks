---
type: llm
focus: last_message
---

PASS if the final message says that the user's TrendsMesh plan does not include trend data, and asks
them to choose, in one question: Paid (the Agent plan, with its current offer: the first month $0,
then $99 a month, or the link to it) or Free (ideas built on the agent's guesses, each labelled a
guess), with at least one sentence on what Paid adds (for example trends repeating across creators
right now, how early, real videos to learn from); and waits for the answer.
FAIL if it makes ideas, proposals or a list of trends before the user chose;
names specific current trends as findings; invents a price or an offer other than "first month $0,
then $99 a month"; asks for payment details in chat; or pushes the offer more than once.

Judge meaning, not exact wording.
