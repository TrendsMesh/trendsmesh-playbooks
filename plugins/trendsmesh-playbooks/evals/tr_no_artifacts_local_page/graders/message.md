---
type: llm
focus: last_message
---

PASS if the final message gives the local page as the result: the path of its index.html (the
report folder in the run), to open in a browser, and calls the run complete (done, finished);
it may say once that this session can't publish claude.ai pages (no artifacts tool).
FAIL if it tells the user that shared links need the Claude desktop app or another app (issue #2:
the user may be in it already), if it says the run failed, is blocked or is waiting because
nothing could be published, asks the user to add or connect an artifacts or publishing tool, gives
a link that was never made, or gives no index.html path.

The run's language is English; judge meaning, not exact wording.
