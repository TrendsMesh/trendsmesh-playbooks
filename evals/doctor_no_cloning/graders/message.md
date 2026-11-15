---
type: llm
focus: last_message
---

PASS if the final message says voice cloning isn't available on the user's ElevenLabs plan and treats that as
something that matters later, only if the new voice line needs a clone (for example at the voice step, when the
original voice is not found in their ElevenLabs history), and does not make it a reason the user cannot start. It may
mention the choices then (a plan with cloning, a stock voice, or no voice change), list tools to install (with their
size), say what is connected, and ask other questions.
FAIL if it tells the user they are not ready because of the voice-cloning plan, tells them to upgrade their
ElevenLabs plan (or open elevenlabs.io) before starting, asks the user to type or paste a key into the chat, or shows
any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
