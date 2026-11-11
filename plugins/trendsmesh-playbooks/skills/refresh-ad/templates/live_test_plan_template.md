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
- Ads, **all created PAUSED**: the control (the original ad, its creative id) and each variant
  (file, copy, headline, thumbnail).
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
1. Upload the media (or the user uploads it by hand to the media library; never a public host).
2. Create the ad set and the ads, PAUSED; previews.
3. The quality and policy check (R8, `04_final/prelaunch_check_vNN.md`).
4. Only after the launch check-in: the A/B test, then activation (spend starts here).
5. Measurements on day 3, 5 and 7, saved in `05_results/`; then the decision and one results
   library row per variant (R5).

## Sources
- `04_final/test_plan_calc_vNN.json`, the control's latest window (`01_base/winner_ranking_vNN.json`),
  the budget from the config or the user's approval.
