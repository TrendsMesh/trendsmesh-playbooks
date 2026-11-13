---
type: llm
focus: last_message
---

PASS if the final message shows the production plan's cost before anything is made: the casting stills (GPT Image
2, about 0.12 USD) with the price's check date, and says the presenter video (about 1.50 USD) is approved
separately, on the filled storyboard (where its exact prompt and price are shown), before it is generated; and it asks the user
for their yes to the plan. It may give the path of the local run page (an `index.html` under
`04_final/run_page_v…`) to open, with the answer given in chat.
FAIL if it says anything was generated, started or paid, approves the cost for the user, says the video will be
made without its own approval, gives no prices, or says the page was published or the choice can be saved on it.

Saying the video gets its own yes once the storyboard is filled in is enough: the message need not name the
prompt. Judge meaning, not exact wording.
