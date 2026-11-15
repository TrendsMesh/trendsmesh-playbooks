---
type: llm
focus: last_message
---

PASS if the final message gives the talking-person options as rows of one table by situation, the plan's own
first (exact wording needed: Gemini Omni 1.2 Flash, about 1.58 USD for a 15 s take), then the others: a person
from a description (Seedance 2.0, about 2.70 USD, no casting face, so no paid casting), a specific person from an
approved image and the user's own or a brand voice (MiniMax H3, about 1.20 USD; the voice one needs a voice sample
of 2–15 s), and the fallback (ElevenLabs + Kling Avatar v2) only after a review shows a take looks or sounds wrong;
with the prices' date or source (Replicate); and it asks the user which situation fits (and whether another model)
together with the plan's yes. It may give the path of the local run page (an `index.html` under
`04_final/run_page_v…`) to open, with the answer given in chat.
FAIL if it picks the situation or model for the user as decided, says anything was generated, started or paid,
approves the cost, gives no prices, gives prices that are not these, or says the page was published or the choice
can be saved on it.

Recommending the plan's situation with its reason, then asking the user to confirm it or pick another, is not
picking for the user. Judge meaning, not exact wording.
