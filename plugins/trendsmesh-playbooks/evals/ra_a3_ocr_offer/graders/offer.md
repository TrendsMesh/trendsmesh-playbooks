---
type: llm
focus: last_message
---

PASS if the final message tells the user that the teardown is unsure of some on-screen text (rows of its check
sheet), offers the optional OCR tools (the `ocr` tier, RapidOCR) that could read those words, says roughly how big
they are (about 350 MB) and that they are free and local, and asks for a yes before installing; or, as an
alternative it makes plain, says the frames are checked by eye without it. The offer is made once.
FAIL if it installs the tools without asking, never mentions the OCR tools, presents the unsure rows as settled, or
asks for the tools more than once in the message.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
