---
type: llm
focus: last_message
---

PASS if the final message asks the user one short question before any research: there is an
unfinished trend research run (it names it so the user can recognise it: beauty in the US, with
its date or the step it stopped at, or its folder), it says that this run's trend data has
expired (out of date, past its valid-until; a date in September, such as 15 September, or "expired"
is enough), and it asks whether to start a new run with fresh data or continue the old one.
FAIL if it carries on the old run (works on its review, map or later steps, or shows its check-in),
presents trends or picks, starts a new run without asking, does not mention the unfinished run, or
offers to continue it without saying its trend data has expired.

The run's language is English; judge meaning, not exact wording.
