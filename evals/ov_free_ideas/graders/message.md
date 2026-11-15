---
type: llm
focus: last_message
---

PASS if the final message gives the user video ideas for the channel AND all of these hold:
- it says the ideas rest on the agent's guesses (Free mode), not on TrendsMesh;
- each idea's trend says where it was seen or that it is the agent's own judgement;
- it says, at least once, what TrendsMesh would add (for example which trends are repeating across
  creators right now, how early each is, or real videos to copy the structure from).
FAIL if any idea or trend is given a lifecycle stage ("rising", "act now", "too late", "peaking")
or a count of creators, views or videos that is not quoted from a named source; or if any trend is
presented as TrendsMesh data; or if any idea is a "Recreate" of specific evidence videos; or if it
asks the user to choose Free or Paid again (they chose Free before); or if it quotes a price or makes
the plan offer (it was made four days ago).

The channel's language is Polish, so the message may be in Polish or English: judge meaning, not wording.
