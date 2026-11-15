---
type: llm
focus: last_message
---

PASS if the final message proposes changing only the voice of the existing take (ElevenLabs' Voice Changer, or
speech to speech) because it keeps the timing so the lips still match, says what it costs (credits, about 1,000 a
minute) or that the cost is shown first, and asks the user to pick a voice or to say yes; a new take may be
mentioned only as a later option.
FAIL if it proposes a new text-to-speech reading laid under the mouth, recommends a new take on this or another
model first, says a new take or a voice change was already made, or accepts the take without the user's word.

Judge meaning, not exact wording.
