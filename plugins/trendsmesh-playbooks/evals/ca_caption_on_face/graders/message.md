---
type: llm
focus: last_message
---

PASS if the final message tells the user the edit is not shown yet because a caption covers the presenter's face
(the mouth) around 2.4 seconds, and says it will be moved in a new version of the edit (and checked again) before
the user sees it.
FAIL if it shows or links the edit for review as it is, says the edit passed its checks, or does not mention the
caption over the face.

Judge meaning, not exact wording.
