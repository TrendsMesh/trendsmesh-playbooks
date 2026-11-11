---
type: llm
focus: last_message
---

PASS if the message asks the setup questions in one batch (one message, a list), each with a default or a choice,
and among them it states both languages of the run as defaults for the user to confirm or correct in the same
reply: the language the user reads in (the pages, summaries, cards) is English, and the language of the audience
(post text, captions, voiceover or speech) is Polish.
FAIL if it gives only one language for everything; makes the pages or what the user reads Polish; makes the post
text, captions or speech English; asks about languages in a separate message before the rest of the batch; or
proposes video ideas or names trends before the questions are answered.

Judge meaning, not exact wording.
