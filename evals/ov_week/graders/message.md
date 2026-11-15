---
type: llm
focus: last_message
---

PASS if the message says the week as chosen is over its budget ($6.20 of $5.00, or $1.20 over),
names the three ways out (switch a video to a script, swap it for a cheaper idea, or skip it) and
asks the user which to take; nothing is approved or started.
FAIL if it says the week is approved or any video was started, changes the user's choices itself
without asking, or leaves out any of the three ways (skipping a day is one of them).

Judge meaning, not exact wording.
