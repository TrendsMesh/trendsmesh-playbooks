# Variants and edge cases (V1 to V28)

Copied verbatim from the handoff's `VARIANTS.md` (handoff `trend-research_v01`, sections "Category
input" to "Other playbooks"). The flow is `flow.md`; the rules `rules.md`. **What the plugin does
with them:**

- **Built:** V1, V2, V7 and V8 (B1 to B4); V9, V11 to V15 and V17 (C2, D3: the seasonal guard, the
  conditions of rule v3, the review of the picks, the lens); V16 as the risk line only; V19, V20,
  V22 and V22a (D2; V22 is `"checked": false`, and the page says "not checked"); V23 to V26 (F2,
  B4: the stored snapshot, the rebuilt one, re-identification, the map that changed a lot); V27
  (E3: the seeds for the creative brief).
- **Not supported yet**, said plainly with the issue link `tm config check` gives: V3 to V6 (any
  category input but a phrase: ask for a phrase instead, for example the product type), V10 (a
  valid-until at an event ahead: the default 14 days holds), V18 (own results), V21 (Foreplay),
  V28 (PB8).
- The text's approval points (G1 to G3) are check-ins (`checkin-cards.md`); its concentration
  and median-views conditions are part of rule v3. "growth.py" and "category_map.py" are
  `tm research …`.

## Category input (TR1)
| # | Case | What the agent does | Tested |
|---|---|---|---|
| V1 | **Broad phrase** ("beauty": 1 relevant result) | split into 5–8 sub-categories, thin ones once more; agent review | yes (beauty: 26 searches, 52 trends after review) |
| V2 | **Narrow phrase with enough results** ("hairstyle": 18 relevant) | no split; the map is the phrase's results after review | partly (as a sub-category) |
| V3 | **Product or landing-page link** | read the page; seed phrases from product type, use, audience, claims; the page also fills the brand intake and the default focus | no |
| V4 | **Store or brand link / name** | one seed phrase per product line; focus = the brand | no |
| V5 | **Competitors** | their product categories become seed phrases | no |
| V6 | **An existing ad or video** | its topic and format become seed phrases; its hook is matched against hook trends | no |
| V7 | **Thin corpus**: leaves still empty after two splits (sunscreen, body lotion, self tanning: 0) | stop; the map says "little TrendsMesh coverage here"; show the closest trends marked "weak match"; never "no trends" | yes |
| V8 | **Off-category trends inside the match threshold** (dementia via "anti-aging", fashion via "makeup") | agent review drops them with a reason (G1) | yes |

## Stages and picks (TR2–TR6)
| # | Case | What the agent does | Tested |
|---|---|---|---|
| V9 | **Seasonal event passed** (Halloween, Día de Muertos on 4 Nov) | seasonal guard → past its peak; the page says the event is over | yes |
| V10 | **Seasonal event ahead** (Christmas in November) | growth before the event is real: the trend can be "act now"; its valid-until is the event date; after the event the guard moves it | no |
| V11 | **Event-bound trend with dates only in its description** ("Sephora Savings Event … Oct 30 to Nov 2") | moved by review (G2) with the reason; cross-check the dates in ad titles (an ad said "Ends 11/9", so the move was corrected to "too late": crowded, five days left); backend request #5 | yes |
| V12 | **One account drives the views** ("Lip combo" 85% LUMIGLO, "Fall almond nails" 98%) | concentration gate: not "act now"; card says "One account" with the share | yes |
| V13 | **Movement without an audience** (7 new creators, median 214 views) | median-views gate: not "act now" | yes |
| V14 | **General, mature hook** ("day _ of _", 253 days, 3 of 65 videos in the category) | moved by review to still rising; useful as a format, not as an early signal | yes |
| V15 | **No trend reaches "act now"** | the page says so in one line and leads with "still rising" and "watch next" | no |
| V16 | **Non-English market** | no language metric for now (TR2); the agent notes in the risk line when a pick's evidence is mostly in another language; Ad Library in the market country | no |
| V17 | **Focus (lens) given** | lens section: picks for that recipient, one line each (lead / pair / skip / over), lower buckets included when they matter | yes (sample lens "nail brand") |
| V18 | **Own results given** (Meta account or channel stats) | trends close to the best-performing content rank higher; the card says why | no |

## Paid view (TR7)
| # | Case | What the agent does | Tested |
|---|---|---|---|
| V19 | **Ad Library, loose matching** ("cat eye nails" → fridge shelves) | query the most specific product phrase; keep only relevant ads; verdict "competitor found" / "none found in Ad Library titles" | yes |
| V20 | **Hook trends** | "not checkable in titles" without Foreplay | yes |
| V21 | **Foreplay connected** | per hook: paid ads using it, platforms, longest run; only then "rising in organic, not yet in paid" | no |
| V22 | **Ad Library unavailable** (no active ad account for the MCP) | the paid view and the card verdict say "not checked"; the report is otherwise complete | no |
| V22a | **Only some outputs chosen** (e.g. report only) | the page shows only the chosen views; no Ad Library checks beyond the picks' verdicts when the paid view is not chosen | partly (all three chosen in the dry run) |

## Digest (TR8, TR9)
| # | Case | What the agent does | Tested |
|---|---|---|---|
| V23 | **Stored snapshot from last week** | `growth.py diff --prev snapshot.json`; call check | no (forward test planned on or after 2026-11-11) |
| V24 | **No stored snapshot** (first digest) | rebuild the previous state from evidence dates (`compute --as-of`), optionally with a full trend list saved that day; label it "rebuilt" | yes (29 Oct rebuilt) |
| V25 | **Trend id changed** (merge, re-promotion) | names sharing ≥ 60% of words → "same trend under a new id" | yes (2 cases) |
| V26 | **Map changed a lot since last week** (many new sub-categories) | show the new map at G1 again before the digest | no |

## Other playbooks
| # | Case | What the agent does | Tested |
|---|---|---|---|
| V27 | **Picks go to PB2** | a pick becomes a concept seed for PB2 (`PLAYBOOK.md`, contracts) | no |
| V28 | **PB8: one report per client** | PB4's map, growth and page modules run per client with the client's Meta results | no |

## Order of the remaining tests
1. **V23 forward test** (on or after 2026-11-11): the real check that PB4 reaches its goal.
2. **V3 product link** as input (most common real intake).
3. **V18 own results** and **V10 event ahead** (before Christmas).
4. V16 non-English market, V21 Foreplay, V27 hand-off to PB2.
