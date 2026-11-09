---
type: llm
focus: last_message
---

PASS if the final message gives the local page as the result: the path of its index.html (the
report folder in the run), to open in a browser, and calls the run complete (done, finished);
it may say once that shared page links need Claude Code in the Claude desktop app.
FAIL if it says the run failed, is blocked or is waiting because nothing could be published, asks
the user to add or connect an artifacts or publishing tool, gives a link that was never made, or
gives no index.html path.

The run's language is English; judge meaning, not exact wording.
