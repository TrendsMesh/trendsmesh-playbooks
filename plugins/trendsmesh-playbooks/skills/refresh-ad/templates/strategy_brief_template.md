# Template: strategy brief (`04_final/strategy_brief_vNN.md`)

## For Claude (not part of the brief)

The strategy brief says why the ad changes and what changes, with the data behind it. It is
written in the run's language, for the user, and grows during the run. Each update is a new
version. Models: `examples/ad3-dry-run/04_final/strategy_brief.md` and
`examples/<voiceover run>/04_final/strategy_brief.md` in the handoff.

Where each section comes from:

| Section | Step | Data and rule |
|---|---|---|
| 1. Diagnosis | A1a | `01_base/winner_ranking_vNN.json` (`tm r1`), `04_final/diagnosis_vNN.json` (`tm diagnose`); R1, R2 |
| 2. Audience | A3b | `02_research/audience/`; the formats from `tm formats` (R6) |
| 3. Earlier results | A0b | `tm library summary` (R5) |
| 4. Trends | A5 | `02_research/trend_*.json`, `videos_*` |
| 5. Saturation | A6 | `02_research/ad_library_summary_vNN.md` |
| 6. Hooks | A7 | lessons 10 and 11 |
| 7. Change register | A7 | only what `tm changes` lists; copy and thumbnail (R7); formats (R6) |

**Every number has its source next to it**, in words the user can follow ("Meta Ads, ad level,
weekly totals 5 Aug to 3 Nov", or the file name). A hypothesis is marked as one and set against
the data. Numbers without a source are removed before the check-in (R3). No step ids, rule
numbers or commands in the brief itself.

---

## 1. Diagnosis
- The ad, the account, the result counted (the campaign's objective: purchase, lead, install).
- Table: window (dates) · spend · cost per result · share who watch the first quarter · share of
  those who watch to the end · clicks / impressions · results / clicks · frequency · CPM, for the
  best period and the latest one. Source under the table.
- The rise in cost per result and how sure it is; the whole account's trend over the same period.
- **What is fading** and the decision: the part of the ad to change, or "do not refresh" with the
  reason outside the video. Other signals seen.

## 2. Audience
- **Hypothesis from the content**, written before the data: who, problem, promise, style.
- **Meta data:** targeting; who it sold to (age × gender, placements) with results and cost per
  result; only groups with at least 10 results count.
- Match or divergence. The working persona. The formats needed (9:16, and 4:5 when the feed
  brings at least a quarter of the results).

## 3. Earlier results
- What won and lost before in this category and market, and how it moved the choice below.

## 4. Trends
| Trend | Type | Status | Creators · views · view lift | How it is used (structure, sub-pattern, when and where) | Fits? |
|---|---|---|---|---|---|
- Evidence videos (links), marked "reference only".

## 5. Saturation
- Each candidate in the Meta Ad Library (market, search): fresh or saturated, with the count.

## 6. Hooks
For each candidate: the text in the market's language (and a translation), the trend and its
structure, what the viewer sees during and after the hook, how the text relates to the image
(consistent · setup and payoff · deliberate contradiction, with its reason), saturation, the rank
and why.

## 7. Change register
| # | Change | Basis | Data (with source) | Expected effect |
|---|---|---|---|---|
- Basis: **proof** (a saved TrendsMesh answer of this run backs it) or **guess** (the account's
  own winners, the Ad Library, the agent's judgement). Same as `04_final/change_register_vNN.json`.
- In a run without TrendsMesh data, open this section with the notice in the reader's words:
  without live trend data, every change here is a best guess, not proof from what is rising now.
- Copy and thumbnail: primary text, headline, thumbnail: each a change with its data, or
  "no change, because…", as separate items.
- Formats: 9:16, and 4:5 when the feed brings at least a quarter of the results.
- What stays as it is (the parts of the winner that work).

## 8. Compliance
- The brand rules and compliance rules from the intake; claims to avoid; music and voice licence.

## Sources
- Every file and Meta or TrendsMesh call the numbers above come from.
