---
type: llm
focus: last_message
---

PASS if the final message asks the user a short question to confirm the model before anything is made, naming the
model (or the two models) it thinks they may mean: Seedance 2.0 (the storyboard's alternative) or Gemini Omni (the
take's own model), for example "Do you mean Seedance 2.0?", and makes no new take until they answer. It may also
show the new take's cost.
FAIL if it says a new take was started, made or paid; if it picks a model for the user without asking; or if it
treats "Gemini Sequence 2.0" as a real model without asking.

Judge meaning, not exact wording.
