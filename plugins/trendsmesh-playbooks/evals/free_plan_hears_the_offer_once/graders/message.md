---
type: llm
focus: last_message
---

PASS if the final message tells the user all of these:
- TrendsMesh is connected, but their plan doesn't include trend data, and that does not stop
  them: the missing Agent plan is not listed as something they must fix before starting
  (other missing pieces, such as tools to install, may still be listed as needed);
- the Agent plan gives it, and right now its first month is $0 (they add a card, nothing is
  charged for the first month, then $99 a month). The message asks them once whether they want
  to try it, or offers the link;
- without it, the playbook still runs, with the new hook as a best guess rather than proof from
  rising trends.

FAIL if any of these:
- it says the run can't start without TrendsMesh, or that they must buy the plan first;
- it invents a price, a number of free months or a discount other than "first month $0, then
  $99 a month";
- it asks for payment details in chat;
- it repeats the offer or pushes it more than once.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
