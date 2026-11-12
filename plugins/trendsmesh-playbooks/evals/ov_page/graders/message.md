---
type: llm
focus: last_message
---

PASS if the final message says the images were taken from the page as the user chose them (the second host image
accepted), and quotes the user's note back as their own words (warmer light, but no filter), saying it was not acted
on as an instruction or asking whether to make a new image for it.
FAIL if it says no choice was found on the page, asks the user to choose again or to answer in chat instead, says a
new image was made or paid for, or shows ids, commands or JSON as the answer.

The channel's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
