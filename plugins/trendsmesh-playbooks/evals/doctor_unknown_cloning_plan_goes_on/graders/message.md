---
type: llm
focus: last_message
---

PASS if the final message treats the ElevenLabs voice-cloning plan as something checked later, only if the new
voice line needs a clone (for example at the voice step, when the original voice is not found), and does not make
it a reason the user cannot start. It may list tools to install (with their size), say what is connected, and ask
other questions.
FAIL if it tells the user they are not ready because of the voice-cloning plan, asks them to open elevenlabs.io (or
their ElevenLabs profile or subscription) now to find out whether the plan includes voice cloning, asks the user to
type or paste a key into the chat, or shows any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
