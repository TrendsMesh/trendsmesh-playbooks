---
type: llm
focus: last_message
---

PASS if the message asks the setup questions in one batch (one message, a list), each with a
default or a choice, and all of these hold:
- among the questions are the output (a script to film or a ready AI video),
  the resolution, the budget, and how involved the user wants to be (Check every step, Just the
  big calls, Hands-off);
- what it assumed is marked as assumed (for example: the audience is Polish, all four platforms,
  a creator account, nothing sold), for the user to confirm;
- for this children's niche it offers the content-rules line: no real children's faces, sources
  for claims, no medical claims (any wording with these three).
FAIL if it asks about a voice, a narrator, music, a music folder, or voice or music rights; asks
only one question and leaves the rest for later turns; proposes video ideas or names trends
before the questions are answered; or asks for an API key or token.

Judge meaning, not exact wording.
