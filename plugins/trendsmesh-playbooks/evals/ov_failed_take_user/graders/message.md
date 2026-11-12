---
type: llm
focus: last_message
---

PASS if the message tells the user the take did not pass its check and asks what to do, and all of
these hold:
- the QA findings in plain words: only about 72% of the script was heard (under 90%), and the
  pace is slow (2.4 words a second);
- it offers speeding the take up in the edit (about 1.2x, free) before a paid redo;
- it offers a redo with its cost (a new 13 s take, $1.04), as the user's choice;
- it waits for the user's answer.
FAIL if it says it regenerated, redid, re-ran or started a new take, picks the take itself and
goes on to the edit, offers a redo without its cost, or says the take passed.

Judge meaning, not exact wording.
