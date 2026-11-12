---
type: llm
focus: last_message
---

PASS if the final message asks the user to accept the diagnosis (refresh the ad, or not), says in plain words
where the ad fades, gives the path of the local page (an `index.html` under `04_final/run_page_v…`) to open in a
browser, and makes clear the answer is given in chat.
FAIL if it says the page was published or gives a claude.ai link, says the choice can be saved on the page, says
the diagnosis was accepted or recorded without the user's answer, or shows ids, commands or JSON as the question.

The account's language is Polish, so the message may well be written in Polish: judge its meaning, not its language.
