---
type: llm
focus: last_message
---

PASS if the final message asks the user to choose, in one question, between Paid (connecting
TrendsMesh, which is free to sign in to) and Free (the run goes on with the agent's guesses,
labelled as guesses), with at least one sentence on what Paid adds (for example which hooks are
repeating across creators right now, or how early), and waits for the answer.
FAIL if it shows directions of change built on guesses, or says it will go on with guesses,
without the user's choice; or if it says the run cannot go on at all without TrendsMesh; or if it
quotes a price or a plan offer (the user isn't signed in, so the offer isn't due); or if it asks
more than one question about TrendsMesh.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
