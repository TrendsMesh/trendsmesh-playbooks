# Template: middle diagnosis (`04_final/middle_diagnosis_vNN.md`)

## For Claude (not part of the document)

The middle diagnosis says where in the video viewers leave, why, and which re-cuts could fix it.
It is written in the run's language, for the user, at CR1 (sections 1 to 3), CR2 (section 4) and
CR3 (sections 5 and 6); each update is a new version. Model:
`examples/ad3-middle-recut/04_final/middle_diagnosis.md` in the handoff.

Where each section comes from:

| Section | Step | Data and rule |
|---|---|---|
| 1. Is the middle fading? | A1a | `04_final/diagnosis_vNN.json` (`tm diagnose`: its `ladder`, peak and latest); R2 |
| 2. The same file in other ads | A1a | `04_final/structural_vNN.json` (`tm structural`); R2b |
| 3. What is on screen when viewers leave | CR1 | `03_wip/retention/segment_map_vNN.json` (`tm tool segment_map`), the teardown's frame sheets, `overlays_checked` |
| 4. The 11 causes | CR2 | sections 1 to 3, the audience data (A3b), the trends (A5); R3 |
| 5. Proposed re-cuts | CR3 | `tm changes --stage middle --material <material>`; `references/recut.md` |
| 6. How the test judges them | CR3, E1 | `tm r4` with `--recut-step` or `--shorter` |

**Every number has its source next to it** (R3), in words the user can follow ("Meta Ads, ad
level, weekly totals 5 Aug to 3 Nov", or the file name). Never compute a step, a p-value or the
structural verdict yourself: copy them from the engine's files. A difference you state (e.g. visual
change −44 % from one segment to the next) is worked out from two numbers of the segment map: name
both. A hypothesis is marked as one. No step ids, rule numbers or commands in the document itself.
The average watch time is whole seconds per day from Meta: write "about 6 s", never "6.04 s".

---

# <Ad name>: middle diagnosis (<date>)

One or two sentences: the ad, the account, what this document answers.

## 1. Is the middle fading?

Conditional retention: each step is the share of viewers who reach the next point out of those
who reached the previous one. Peak window against the latest one. Source: <the windows and their
file>.

| Window | Cost per result | p25/play (0–25 %) | p50/p25 (25–50 %) | p75/p50 (50–75 %) | p95/p75 (75–95 %) | p100/p95 | Average watch |
|---|---|---|---|---|---|---|---|
| Peak <dates> | | | | | | | about <n> s |
| Latest <dates> | | | | | | | about <n> s |

Give each step's seconds of this video in its header (e.g. "p75/p50 (12.1–18.1 s)").

- The verdict in one line: the middle is fading (which step dropped, by how many points, how sure),
  or it is not (the steps moved less than 3 points), and what is fading instead.

## 2. The same file in other ads

The same video in <n> ads (same video or same thumbnail and length). The file is constant, the
audience changes: the shape comes from the file, the level from the audience. Source: <files>.

| Ad (campaign, start, optimisation) | Plays | p25/play | p50/p25 | p75/p50 | p95/p75 | p100/p95 |
|---|---|---|---|---|---|---|
| | | | | | | |

Bold the weakest middle step in each row. Uploads under 1,000 plays are listed as skipped, with
their plays.

- **Weak by design** (the same step weakest in every upload, at least two uploads): name the step
  and its seconds. It is an opportunity to improve, not a sign the ad is fading. Or: not by design,
  and why (different weakest steps, or too few uploads).
- What the audience changes (level, not shape), if the data shows it; a hypothesis otherwise.

## 3. What is on screen when viewers leave

Source: the segment map, the frame sheet, the overlay list.

| Segment (s) | Retention step (peak → latest) | Text card on screen | Visual change | Loudness | Words spoken |
|---|---|---|---|---|---|
| 0–<a> | p25/play | | | | |
| <a>–<b> | p50/p25 | | | | |
| <b>–<c> | p75/p50 | | | | |
| <c>–<d> | p95/p75 | | | | |

Mark the weakest step. Then, in plain words: what happens on screen in the weak segment (motion,
cards, sound, speech), when the **last new piece of information** appears (second), and how much
of the runtime comes after it.

## 4. The 11 causes checked against the data

| # | Cause | Verdict | Evidence (with source) |
|---|---|---|---|
| 1 | The hook promises, the middle does not deliver | | |
| 2 | Pacing, dead air | | |
| 3 | The ad is longer than its content | | |
| 4 | Fatigue of the middle | | |
| 5 | No proof | | |
| 6 | Visual monotony | | |
| 7 | Sound | | |
| 8 | Placement | | |
| 9 | Audience shift | | |
| 10 | A faded trend in the middle | | |
| 11 | A "this is an ad" moment | | |

Verdicts: **yes**, **no**, **hypothesis** (plausible, not measurable from these data), or "not
applicable"; a short qualifier is fine ("not the main one", "affects the level, not the shape").
Every "yes" names the number that shows it.

## 5. Proposed re-cuts

Each variant changes one thing against the original, so the test can tell what worked.

| Variant | Change | Cause it removes | Data behind it | Level | Cost (estimate) |
|---|---|---|---|---|---|
| | | | | 0 · pure edit | free |

Levels: 0 pure edit, 1 graphics layer, 2 own assets, 3 repair AI, 4 generative AI, 5 audio (the
lowest that removes the cause). Paid levels give the estimate and what it buys ("Veo 3.1 Fast,
8 s, about $0.80"; "a new music take, about 220 ElevenLabs credits"); a saved take that fits is
free. What is not offered, and why (e.g. "no reorder: the ad is two continuous shots").

## 6. How the test judges them

- A shorter version mechanically raises completions and ThruPlay, so it is judged by cost per
  result, with the average watch time next to it.
- A same-length version is judged by the step of the changed window (e.g. p75/p50), with cost per
  result as the guardrail.

## Sources

- Every file and Meta call the numbers above come from.
