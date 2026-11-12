---
type: llm
focus: trace
---

The trace is one agent session writing the live test plan of a Refresh an ad run
(`04_final/live_test_plan_v01.md`, written with the Write tool).
PASS if the plan the agent wrote says all three: (1) the original ad keeps running, untouched, in its own campaign
during the test (the run does not pause, edit or move it); (2) the original reaches the same people as the test
(the audiences overlap) and may slow the test's delivery; (3) the control is a new ad made of the original's files,
not the running original ad.
FAIL if no plan was written, if any of the three is missing, or if the plan says the original ad is paused, edited
or moved for the test, or that the running original ad itself is the test's control.

The account's language is Polish, so the plan may well be written in Polish: judge its meaning, not its language.
