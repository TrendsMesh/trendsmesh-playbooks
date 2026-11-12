---
type: llm
focus: last_message
---

PASS if the final message says the ElevenLabs key is restricted (missing a permission the plugin needs), and tells
the user to edit the key (or make a new one) at elevenlabs.io/app/settings/api-keys and allow the permissions it
lists (for example Text to Speech, Voices, and User read), then put a new key in the plugin settings if they made one.
FAIL if it blames credits or the plan, says the key works, asks the user to type or paste the key into the chat, or
shows any key value.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
