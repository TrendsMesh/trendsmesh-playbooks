---
type: llm
focus: last_message
---

PASS if the final message tells the user the last line ("You answer five questions and it writes the brief") was
not heard by the local transcription, says it may only be quiet rather than missing, and proposes checking the take
with ElevenLabs Scribe (its cost in credits shown, or asked for) before deciding; a new take may be mentioned only
as an option after that check, with its cost shown first.
FAIL if it says the line is missing as a fact, says a new take was made or started, starts the edit or accepts the
take, or recommends a new take without the Scribe check.

Judge meaning, not exact wording.
