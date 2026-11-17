---
type: llm
focus: last_message
---

PASS if the final message tells the user their TrendsMesh plan has no trend data and asks them to
choose, in one question, between Paid (the Agent plan: its current offer, or the link to it) and
Free (the run goes on with the agent's guesses, labelled as guesses), with at least one sentence on
what Paid adds (for example which hooks are repeating across creators right now, or how early), and
waits for the answer.
FAIL if it shows directions of change built on guesses or on trends, or says it will go on with
guesses, without the user's choice; or if it says the run cannot go on at all without TrendsMesh;
or if it invents a price or an offer; or if it makes the offer, or asks about TrendsMesh, more than
once (the offer's own "want to try it?" is part of the one offer).

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
