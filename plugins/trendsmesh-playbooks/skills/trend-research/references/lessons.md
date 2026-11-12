# Lessons from the beauty dry run (1 to 21) and from PB1 and PB2

Copied verbatim from the handoff's `ANALYSIS.md` (handoff `trend-research_v01`, sections 3a, 3c and
4). Read the ones a step names before doing that step. What changed for the plugin:

- Lessons 10 and the "persist every response" line: answers are saved by the collector, not
  transcribed (`references/trend-collection.md` at the plugin root); Ad Library answers too, and
  your reading of them goes to `02_research/ad_library_summary_vNN.json`.
- Lesson 8: there is no language metric (TR2, approved later than this lesson); the language of
  the evidence goes in the pick's risk line only, when you see it.
- Lessons 13 and 18 are about editing the reference scripts: the plugin's engine is not edited during
  a run. JSON you write goes into files in `03_wip/` with the Write tool, never inline.
- Section 4's "decisions on the page" was overruled (TR10: the page is read-only).

## 3a. Lessons from dry run 1 (beauty, 2026-11-04)
1. **The split works:** "beauty" 1 relevant result → 8 sub-categories → 17 second-level searches → 52 trends after review (hair 19, makeup 13, nails 7, beauty haul 5, skincare 5, lashes and brows 3). Thin leaves after two splits (sunscreen, body lotion, self tanning: 0) mean little corpus coverage; stop there.
2. **The match threshold lets off-category trends in** (dementia at 41 via "anti-aging", fashion and fan edits via "makeup" / "k-beauty"): an agent relevance review is part of G1 (`map_review_v01.json`, 8 drops and 7 re-tags with reasons).
3. **PB2's noise list is wrong for PB4:** "holidays" dropped Halloween makeup, which is in-category; "vs" dropped "Curly vs straight hair". Seasonal is now a tag; generic sport tokens are not used.
4. **Acceleration does not predict, velocity does.** Backtest at 3 dates: growth ratio vs later new creators, Spearman 0.03–0.20; new creators in the last 14 days 0.40–0.57; recency 0.33–0.45. TR3 rewritten as rule v2.
5. **Seasonal guard needed:** without it, on 4 Nov all Halloween trends were "act now" (the 14-day window ends at the peak). Event dates were in `growth.py EVENTS` (English words only); since issue #3 the agent names each trend's event and its date in the market language at B3.
6. **Event-bound trends hide their dates in the description** ("Sephora Savings Event … around October 30 to November 2"): caught by the agent at G2, not by the rule. Candidate for the backend: an event end date on the card.
7. **Movement without an audience:** "Fall almond nails" had 7 creators and a 214-view median. A median-views gate (≥ 5,000) for "act now".
8. **Evidence language matters and the card does not say it:** eyelash extensions 71% Russian, "get ready with _ to _" 67% Portuguese. Language share is computed from excerpts; a risk line in the card.
9. **`creator_id` is null in the public videos response**; distinct creators use the `creator` handle.
10. **Meta Ad Library:** matching is very loose ("almond nails" → language-learning ads; "cat eye nails" → fridge shelves), titles only, hooks not checkable. Queries must be the most specific product phrase. Responses come inline; transcribed into `ad_library_summary.json` (PB2 lesson 2 again: the SKILL needs a way to save MCP responses as files).
11. **Hooks path:** of 101 hook trends, 5 have ≥ 2 beauty videos in their evidence; a single matching video is chance.
12. **Survivorship in the backtest:** trends that ended before today are not in the pool, so every bucket looks better than it is. The digest's own snapshots (TR8) remove this from the next run on.
13. **A tool bug cost one iteration:** a regex block lost its `\b` when patched through a shell string (`growth_v04_langbug`). Patch Python sources with the editor, not shell heredocs.

## 3c. Lessons from round 2
14. **Relative velocity and the concentration gate improve the rule:** backtest act-now median new creators after 3.0 / 10 / 8.0 (v3) vs 2.5 / 10 / 3.0 (v2); share with 3+ new 64% / 100% / 90% vs 50% / 100% / 59%. "Act now" shrank from 9 to 7 by the numbers and to 4 after review.
15. **Hooks must be ranked among all hooks:** inside the category pool only 5–6 hooks exist, so their band meant nothing; against 101 rising hooks "day _ of _" and "your sign to _" are top 10%.
16. **Trend ids are not stable across days:** two Halloween / Día de Muertos trends reappeared under new ids within six days. The digest matches names (≥ 60% shared words). Backend request #3.
17. **First call check (rebuilt 29 Oct snapshot, 6 days):** 10 of 12 "act now" calls got new creators afterwards; both "past its peak" calls stayed quiet. Short window and a rebuilt snapshot: indicative only; the real forward test is the digest on 11 Nov against the stored snapshot.
18. **A shell heredoc mangled backslashes again** (a Windows path in an inline script). Keep using the editor for code and file lists.
19. **A trend description can be wrong about dates:** the Sephora trend said "around October 30 to November 2"; an advertiser title in Ad Library said "Ends 11/9". The G2 move was corrected (past its peak → too late, crowded and five days left). Paid titles are a cross-check for event dates.
20. **Paid view result (26 checks):** openings (rising, none in titles): cat-eye nails and its leopard variant, lash lift, keratin salon transformations, wash-day routines, Venom makeup. Rising but crowded: lip combo, lash clusters, braiding hair, lace-front wigs, hair loss. Slowing and crowded: skincare routines.
21. **The local preview is a `data:` page:** hash links do not work there; the views also switch on click so they work in any viewer.

## 4. Lessons carried over from PB1 and PB2
- Every number has a source; a hypothesis is never a conclusion (R3). The user corrected unsourced claims in the PB1 promo.
- Naming: `hook_trend` = hook, `format_trend` = format, `topic_trend` = topic (PB2 CB6).
- Describe a trend's structure from its evidence videos (slot fills, sub-patterns), not from its name (PB1 lesson 10).
- Search is loose; drop noise; never write "no trend in the category", show the best-fitting ones (PB2 lessons 3, 18).
- A trend from another language or market is a hypothesis; rank by creators and growth, not views (PB1 lesson 5, PB2 lesson 4).
- Sound trends: licence for paid (PB2 CB9).
- Persist every API / MCP response to the run (PB2 lesson 2).
- Output is a shareable page with real clips and links, decisions on the page (PB2 lessons 13–16; ExampleEdu asked for a board linking each trend to its videos).
- Freshness matters to the user: ExampleEdu wanted to know whether the trends were recent and when their videos had come in. Show since / last seen / as-of dates.
- Money shown outward in USD at a stated rate.
- Documentation first, in English; the SKILL is built from it.
