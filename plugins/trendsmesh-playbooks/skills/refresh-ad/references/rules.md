# Hard rules R1 to R9

Copied verbatim from the handoff's `PLAYBOOK.md` (handoff v02, section "Hard rules", with v03's
changes of 2026-11-06: R2 amended, R2b added, the sibilant cut in R9). They apply in every run, at
every level of involvement. The agent may not skip them. The config changes only their threshold
values, never the rule. Where the rule says "HITL" read "Check every step" and "Just the big
calls"; where it says "AUTO" read "Hands-off"; "gate" is a check-in.

R1's "90 days of daily metrics for all ads" is fetched as weekly totals for every ad plus
daily rows for the top 5 ads by spend (and the chosen ad), so the data fits the context
(SKILL.md section 6, `flow.md#a1`). The windows are the same 7-day windows, so the ranking is
the same. R2's retention ladder (plays, p25 to p100) comes from the same weekly rows: the peak and
latest windows of the ranking, not daily rows. R2's "the hook holds" is the hook rate (p25 /
impressions) holding within `diagnosis.drop`; its middle reads the three conditional middle steps
only when both windows carry the ladder, and falls back to ThruPlay / p25 otherwise.

What the engine computes for you, so you never compute it by hand: the R1 ranking (`tm r1`), the
R2 diagnosis with its retention ladder (`tm diagnose`), the R2b structural check (`tm
structural`), the R4 plan and its minimum events (`tm r4`, with `--recut-step` or `--shorter` for
a re-cut), the R6 formats (`tm formats`), the R9 audio QA (`tm tool vo_qa`), whether a re-cut's
edit list is legal (`tm recut check`) and, for R8's AI disclosure, what the run made or edited with
generative AI (`tm ai-media`: the facts; the disclosure itself is the user's answer, asked before the
upload, `flow.md#e1`). R3, R5, R7 and R8 are yours to keep, and
the engine holds the run until they are met where it can (the library entry, the R8 check-in).
While the run is stopped, the engine refuses spending, budget approvals and the launch.

### R1. Choosing the fading winner (step 1)
| Parameter | Default value | Why |
|---|---|---|
| event | **result of the campaign objective** (purchase, lead, install), not always purchase | the same criterion works on a sales account, a lead account and an app account |
| history | 90 days of daily metrics for all ads | enough to find the peak and the current state |
| windows | **multiples of 7 days**, extended until each window has **≥ 30 results** | a 5-day window mixes days of the week; a fixed number of purchases does not fit small accounts |
| fresh days | **the last 2 days are always cut out** | attribution adds conversions with a delay; without this every active ad looks like it is fading |
| winner | the best window has ≥ 30 results and cost per result ≤ target CPA | — |
| target CPA | given by the user or the **account's median cost per result over 90 days** | the target depends on the account |
| fading when | cost per result in the last window **≥ +30%** versus the peak **and** the change is **significant (p < 0.1)** for "results per zloty spent", **after subtracting the trend of the whole account** in the same period | the % threshold alone, with a small number of events, falls within noise (30 → 18 purchases is p ≈ 0.09); a drop of the whole account is not creative fatigue |
| supporting signals | drop in CTR, ThruPlay / impressions, rise in frequency | help in the diagnosis (R2), but do not qualify an ad on their own |
| ranking | by **value to recover**: winner's scale at the peak (results or spend) × rise in cost per result | ads where a refresh will give the most come first |
| evidence | ranking saved in the run: `01_base/winner_ranking.json` (all candidates with windows, test and value) + `01_base/<ad>_meta_daily.json` of the selected one | the choice must be verifiable; in the Ad 3 run there was no ranking |

### R2. Funnel diagnosis is a gate (end of step 1, before research)
We choose the creative change **only** according to which funnel stage is fading. The diagnosis is built from the R1 data and saved in `strategy_brief.md` with the numbers.

| Symptom in the data (peak window vs latest) | What is fading | Decision |
|---|---|---|
| the share of people who watch the beginning drops (p25 / impressions at ad level, 3-sec. at ad set level) | hook | we refresh the beginning: hook text, first shot, first VO line |
| the hook holds (p25/play), and a **conditional middle step** drops (p50/p25, p75/p50 or p95/p75, each out of those who reached the previous point) by ≥ `diagnosis.middle_step_drop_pp` (default 3 pp) with p < 0.1 (two-proportion test) | middle | re-cut (step 7c, `FLOWS.md` C-R): pace, shorter cut, scene order, stronger proof |
| retention holds, CTR drops | promise / CTA | promise text card, CTA, offer, VO ending |
| **CTR holds, conversion drops** (results / clicks) | landing page or offer | **do not refresh the creative**; report the problem outside the video |
| **the whole account drops** (account trend similar to the ad trend) | season, pixel, auction | **do not refresh the creative**; report |
| everything proportionally, frequency rises | fatigue with the same image | new aesthetic with the same message (AI video), new creator, new format |
| only CPM rises | auction | no creative change; observation |

In HITL the user accepts the diagnosis (gate G1a). In AUTO the table decides. A "do not refresh" verdict ends the run with a report, without spend.

**Amendment 2026-11-06 (issue TrendsMesh/trendsmesh-playbooks#1 tests):** retention is read as **conditional steps**, not as "p50–p100 / impressions". The latter mixes the hook with the middle: a weaker hook lowers every later point even when the middle holds. Source: `ads_get_ad_entities` with `time_increment=1` (p25, p50, p75, p95, p100, video plays), peak window vs latest window as in R1.

### R2b. Structural check of the file (after R2, always)
R2 answers "what is fading". R2b answers a second question: is a segment of the file **weak by design**? It is not a refresh trigger on its own, but it is reported in the diagnosis as an improvement opportunity.

| Step | Rule |
|---|---|
| same file elsewhere | find the other ads using the same video (`ads_get_creatives` video_id and thumbnail, `ads_get_ad_videos` length) |
| weakest step | the conditional step with the lowest value in each upload (≥ 1,000 plays per upload) |
| structural | the same step is the weakest in **every** upload (≥ 2 uploads): the shape comes from the file, the level from the audience |
| segment map | the step mapped to seconds, with the card on screen, visual change and music loudness (`FLOWS.md` CR1) |
| decision | HITL: the user may choose a re-cut (7c) anyway (G1a). AUTO: re-cut only when R2 says "middle" or `diagnosis.structural_recut: true` |

Example (Ad 3, 2026-11-05): R2 "middle not fading" (steps moved < 1 pp), but 12.1–18.1 s (p75/p50) was the weakest step in all 4 uploads (49.1–61.7%), where visual change fell by 44% and the last new information appeared at 14.2 s.

**Test metric for a re-cut (R4):** a shorter version mechanically raises p100 and ThruPlay (ThruPlay = 15 s or completion), so it is judged by average watch time and cost per result. A same-length variant is judged by the conditional step of the changed window, with cost per result as the guardrail.

### R3. Every number in the outputs has a source
- Every number in the strategy brief, creative brief, reports and materials (promo too) has a stated source: an MCP call (tool and parameters) or a file in the run.
- **A hypothesis is never presented as a conclusion.** A hypothesis from the ad content (e.g. the target audience) is always marked as a hypothesis and set against the data. In outputs for the recipient, what remains is what the data says.
- Numbers without a source are removed before acceptance.

### R4. A live test has thresholds written before the start
The test plan (`04_final/live_test_plan.md`) contains, before activation:
- the **decision metric**, i.e. the metric of the stage we changed (e.g. the share of people who watch the beginning when changing the hook), and cost per result as a **guardrail**;
- **numeric thresholds**: scale, switch off, no verdict;
- the **minimum number of events** per variant before any decision; budget and time follow from this number, not the other way round. For a rate metric (hook rate, ThruPlay rate, CTR) that means the trials the metric needs at the control's cost per impression or play, run for at least `test.min_days` days; cost per result is the guardrail, not a sizing condition: it is checked once a variant has `test.guardrail_min_results` results, and a variant that wins on its metric with fewer is "won on <metric>; cost per result not confirmed yet" (scale step by step). The plan says what its budget is based on;
- **no decisions before the end of the window** (no peeking and no early switch-off), except for the cost guardrail;
- a **Meta A/B test** (`ads_experiment_abtest_*`), not a manual comparison of ads in one ad set;
- the original as the control.

A plan that, at the given budget, will not collect the minimum number of events goes back to the user with a calculation: how many events, what budget, what time. Example: 150 PLN/day for 5–7 days gives 17–50 purchases across 2–3 ads, too few to compare on cost per purchase.

### R5. The learning loop is mandatory
- After each test, an entry in the **results library** `library/results.jsonl` (one row per variant): account, product, market, diagnosis (R2), trend (id, type, status on the test day), change (layer, method), decision metric, result versus control, number of events, decision, link to the run. A run without TrendsMesh data writes `trend: null` with `evidence: guess`: its result counts for the method, not for any trend.
- Every new run starts by reading the library. Trends and methods that lost in the same category go lower in the hook ranking. Those that won go higher.
- Without an entry the run is not closed.

### R6. Format by placement
Output formats follow from the distribution of purchases by placement (breakdown from step A3b). A placement with **≥ 25% of results** gets its own format:
- Facebook and Instagram feed: **4:5**;
- Reels and Stories: **9:16** with safe zones.

Examples: in ExampleTravel the feed was 55% of purchases, in Ad 3 71%, and we made both ads only in 9:16.

### R7. Copy and thumbnail
Every refresh includes a decision on the **primary text, headline and thumbnail (cover)**: either a change with a justification in the data, or an entry in the change register "no change, because…". Nothing carries over from the old ad without a decision. A copy change is a separate item in the change register, so that the test can distinguish what worked.

### R8. Meta quality and policy gate before spending money
Before activation (G11) every variant passes the checklist saved in the run (`04_final/prelaunch_check.md`):
- AI content labeling, if Meta requires it;
- claims: health, financial, "before and after", references to institutions (e.g. the CIA);
- music and voice license;
- text on the image and legibility in the feed preview;
- known visual defects (over time);
- quality assessment against the original (before and after pair).

A red item blocks activation, also in AUTO.

### R9. Voiceover processing (flow with a new VO line)
- A new line that has to fit in a given time is first **regenerated at the right length** (shorter text, TTS tempo parameter).
- Time stretching is a last resort and only with settings that do not smear the phase (rubberband `transients=crisp`, `phase=laminar`, `window=short`). The `smooth` mode produces an audible "reverb".
- **QA** compares the recording with the unprocessed version. Syllable onset steepness (dB / 5 ms) and spectral flatness must stay within ±10% of the original. In HITL an A/B sample goes to acceptance.
- **Cutting words out of a take:** do not trust the TTS word-start timestamp for words that begin with a sibilant (s, sh, z, f), because it lands late. Place the cut in the first silence (< −55 dBFS for 30 ms) after the last kept word, then check that no burst is left after it. On 2026-11-04 a cut before "Sixteen" left the "S" as an audible hiss.
