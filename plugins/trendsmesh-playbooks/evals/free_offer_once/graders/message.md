---
type: llm
focus: last_message
---

PASS if the final message tells the user all of these:
- TrendsMesh is connected, but their plan doesn't include trend data;
- they choose, in one question: Paid (the Agent plan, which right now has its first month at $0:
  they add a card, nothing is charged for the first month, then $99 a month; or the link to it)
  or Free (the playbook goes on with the new hook as a guess, labelled as one);
- with one sentence on what Paid adds (for example hooks repeating across creators right now).
Other missing pieces, such as tools to install, may still be listed as needed.

FAIL if any of these:
- it says the run can't start without TrendsMesh, or that they must buy the plan first;
- it says the run will go on with guesses (or starts it) without asking them to choose;
- it invents a price, a number of free months or a discount other than "first month $0, then
  $99 a month";
- it asks for payment details in chat;
- it repeats the offer or pushes it more than once.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
