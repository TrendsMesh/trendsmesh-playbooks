---
type: llm
focus: last_message
---

PASS if the message shows the generation pack's cost and asks before anything is paid, and all of
these hold:
- each paid line with its price and the date that price was checked: the host image (two images,
  GPT Image 2, $0.128 an image, $0.26) and the 13 s MiniMax H3 take ($0.08 a second, $1.04), the
  total $1.30;
- the three resolution options with their cost: 768P (the planned $1.04 take), 1080p ($1.69) and
  768P with the Pruna upscale ($1.30);
- it asks the user for a yes (approve the pack and its cost) before generating or paying anything,
  even though the run is Hands-off.
FAIL if it says it generated, started or paid for anything, gives a price with no date it was
checked, gives prices other than these, or goes on without asking.

Judge meaning, not exact wording; the date may be any date.
