# Template: live test plan (`04_final/live_test_plan_vNN.md`, R4)

Written before anything goes live, in the run's language. The numbers come from `tm r4`
(`04_final/test_plan_calc_vNN.json`) and the run's data, each with its source. Nothing in this plan
is done on the account until the user approves it ("Approve the live test plan") and, later,
the launch ("Approve the launch").

---

## 1. What the test answers
- The fading stage (from the diagnosis) and the change tested in each variant.
- **Decision metric:** the metric of the changed stage (e.g. 25% plays / impressions for a new
  opening). **Guardrail:** cost per result, checked once a variant has the plan's minimum results
  for it (`cost_guardrail.min_results`).

## 2. Structure (a Meta A/B test, not a manual comparison)
- Campaign (existing or new), objective and event, pixel.
- Ad set: targeting copied from the original's ad set (name it), placements, optimisation.
- Ads, **all created PAUSED**: the control (a new creative of the original's files, with or
  without a 4:5 version below, never the original's creative id; the one exception is under "The
  original ad during the test") and each variant (file, copy, headline, thumbnail).
- **Files and placements per ad** (R6, from `tm formats`). The ads differ only in the change
  under test, so the control and the variants carry the same formats on the same placements
  (placement asset customization when an ad has two files):

  | Ad | Reels and Stories (9:16) | Feed (4:5) |
  |---|---|---|
  | Control | the original's video | the 4:5 version of the original (`tm tool reframe`, QA), or "9:16 only" |
  | Variant 1 | the edited video, 9:16 | the edited video, 4:5 |

  When R6 asks for 4:5 and the original has none, the 4:5 version of the original is made with
  `tm tool reframe` and QA (free). Only if it fails its QA: "test in 9:16 only; 4:5 after the
  test", and why; the control is then still a new creative, 9:16 only like the variants. The
  upload (E2) builds exactly this table; any change is asked first.
- **AI disclosure** (Meta's `self_ai_disclosure`, set only when a creative is created): what the
  run made or edited with generative AI, per ad (`tm ai-media`: voice lines, music, frames
  inpainted by a model such as ProPainter, AI shots or video; the free OpenCV caption plate isn't AI media), what is known about the original, and the user's answer: both,
  neither or only the variant (the last one makes the "AI info" label a second difference).
  Never decided for the user.
- **The original ad during the test:** it keeps running, untouched, in its own campaign (name it
  and its ad set); the run never pauses, edits or moves it. Say plainly that it reaches the same
  people as the test (the audiences overlap), so it competes with the test in the same auctions
  and may slow the test's delivery. Both test ads are new, the control included, so the test
  changes one thing only. **The one exception:** when a new creative can't match the original
  (for example a partnership ad run from a creator's account), the control is the original's
  creative: say so here, with the reason, and that the control then carries the original post's
  likes, comments and shares, a second difference next to the change under test.
- `ads_experiment_check_eligibility` result.

## 3. Thresholds, written now
| | Rule |
|---|---|
| Scale | the decision metric better by at least the minimum effect, p below alpha, cost per result not above the control's |
| Switch off | worse with p below alpha, or cost per result at or above the guardrail |
| No verdict | anything else at the end of the window |
| Guardrail | cost per result above N × the control's, once a variant has the minimum results for it (the only rule allowed to act early) |
| Won, cost not confirmed | a rate metric won but the variant has fewer results than that minimum: "won on <metric>; cost per result not confirmed yet", scale step by step |

## 4. Size, budget and time
- **Minimum events per variant** before any decision, and why (R4).
- **What the budget is based on**, in one sentence from the plan's `basis`: for a rate metric the
  trials it needs and the minimum run time (e.g. "the budget covers the hook rate's 1,170
  impressions per variant and 4 days; cost per result is watched as a guardrail"), for cost per
  result the results each ad needs.
- From it: the budget per day, the number of days, the total the test spends. A plan that cannot
  reach the minimum goes back to the user with the calculation (events, budget, time).
- No decisions before the end of the window: no peeking, no early switch-off except the
  guardrail.

## 5. Steps on the account (Meta Ads MCP)
1. Upload the media in one round: every file the table above names, and the thumbnail (or the user
   uploads it by hand to the media library; never a public host).
2. Create the ad set and the ads, PAUSED; previews.
3. The quality and policy check (R8, `04_final/prelaunch_check_vNN.md`).
4. Only after the launch check-in: the A/B test, then activation (spend starts here).
5. Measurements on day 3, 5 and 7, saved in `05_results/`; then the decision and one results
   library row per variant (R5).
6. If the variant wins (G12 `scale`), and only with your yes: a new ad set in the original's
   campaign, **PAUSED**, with an ad from the test ad's post (its likes, comments and shares come
   along), never inside the original's ad set (that would restart its learning); its preview.
   Nothing is switched on: switching it on, moving the budget and switching the original off are
   yours, step by step in the final report.

## Sources
- `04_final/test_plan_calc_vNN.json`, the control's latest window (`01_base/winner_ranking_vNN.json`),
  the budget from the config or the user's approval.
