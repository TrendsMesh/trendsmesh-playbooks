# Hard rules TR1 to TR10 (and the rules from PB1 and PB2 that apply)

Copied verbatim from the handoff's `PLAYBOOK.md` (handoff `trend-research_v01`, section "Hard rules",
approved 2026-11-04). They apply in every run, at every level of involvement. The agent may not
skip them. The config changes only their threshold values, never the rule.

How to read the copy in the plugin:

- Where it says "HITL" read **Check every step** and **Just the big calls**; where it says "AUTO"
  read **Hands-off**. The quoted text's approval points (✋, G1 to G3) are check-ins (G0, G1, G2,
  G3, GS: `checkin-cards.md`); its concentration and median-views conditions are part of rule v3,
  which `tm research growth` applies.
- Where it names the reference API client, the REST API or a file holding an API key, the plugin
  uses the TrendsMesh MCP through the collector (`references/trend-collection.md` at the plugin
  root): there is no TrendsMesh key, ever. The tools it names (`category_map.py`, `growth.py`,
  `build_report.py`) are `tm research …` (`flow.md`).
- **Scheduling (TR8)** follows the plugin's `references/schedule.md`: a desktop scheduled task in
  the Claude desktop app, or the weekly run started by hand. There is no cloud routine (it cannot
  reach the workspace or the user's sign-ins) and no key in its environment.
- **Rule v3 is the only bucket rule.** TR3's rule v2 table is kept for its reasoning; rule v3's
  changes (velocity index, at least 3 new creators, the 60 % concentration condition, bands,
  confidence) win where they differ.
- Not built in this version, said plainly as "not supported yet": category inputs other than a
  phrase (TR1's links, stores, competitors, ads: VARIANTS V3–V6), own results (TR5, V18), Foreplay
  (TR7, V21), an event-ahead valid-until (V10). `tm config check` refuses them with an issue link.

What the engine computes, so you never compute it by hand: relevant counts, the split rule and
the depth (`tm research search-status`), the map with noise, seasonal tags and the review
(`tm research map`), the hooks' ranking and shortlist (`tm research hook-fit`), their category
videos (`tm research hooks`), growth, stages, bands, confidence and the snapshot (`tm research
growth`), the backtest (`tm research backtest`), the fetch plan and the digest with the call check
(`tm research fetch-plan`, `digest`), the checks of your Ad Library reading and your picks (`tm
research paid check`, `picks check`), the page (`tm research report`) and the seeds (`tm research
seeds`). Yours to keep: the seed phrases and the split, the relevance review, the hooks' fit
scores, the review of the picks and their write-ups, the Ad Library reading, the digest text, and
every sentence's source (R3).

## The words fixed by the spec (use them verbatim, on the page and in messages)

- "creators in TrendsMesh evidence": every creator count is the collected sample, not platform
  totals.
- "none found in Ad Library titles": never "not in ads" (the Ad Library returns titles only).
- "Not checkable without Foreplay": hooks in the paid check.
- "weak match": never "no trends in the category"; a thin map shows its closest trends so marked.
- "Moved by review": a trend the review of the picks moved, with its reason.

## The numbers (copied from PLAYBOOK.md; the config's defaults)

- TR1: `min_match` 40, `min_relevant` 10, split into 5–8 sub-categories, max depth 2.
- Hooks path: every hook scored 1–5 on Creative brief's seven CB3 criteria, equal weights; the best
  `hooks.shortlist` 8 with a mean fit of at least `hooks.min_fit` 3 are fetched and kept; category
  videos counted on whole words, any match (issue #8; until 0.10 a hook was kept only at ≥ 2
  matching videos and ≥ 20 %, or ≥ 3).
- TR2: window 14 days, baseline 28 days, lag 2 days; baseline floor 1 creator per window.
- TR3 rule v3: act now index ≥ 1.3 and ≥ 3 new creators, last new ≤ 5 days, median views ≥ 5,000,
  top account ≤ 60 %, not crowded; still rising index ≥ 0.6 and ≥ 2, ≤ 7 days; crowded ≥ 100
  creators and ≥ 90 days; too late = active ≤ 14 days; seasonal guard 60 days.
- Confidence: low < 8 creators or top account > 60 %; high ≥ 15 creators, top ≤ 40 %, confirmed.
- Bands: top 10 % / top 25 % / top half / lower half.
- TR6: top 5 act now, top 5 still rising; valid-until 14 days.
- TR7: the paid scope adds "too late" trends with ≥ 30 creators; levels none / found (1–3) /
  crowded (≥ 4) / not_checkable.
- TR8: re-identification at ≥ 60 % shared words.
- V26: the map changed a lot when ≥ 25 % of this week's mapped trends were not in last week's, or a
  group is new.

## Rules from outside the playbook files (HANDOFF.md section 4, verbatim)

- **Run folder and manifest:** `runs/04-trend-research/<YYYY-MM-DD>_<name>/` with `00_raw`, `01_base`, `02_research`, `03_wip`, `04_final`, `05_results`, `showcase`, `manifest.md`. Never overwrite (`_vNN`, `report_vNN`). Every asset has a manifest row. **Save every MCP response to a file**: Ad Library answers come back inline and must be transcribed (`ad_library_summary_vNN.json`).
- **Keys** in `.secrets/api_keys.env` (python-dotenv); never print, log or commit them.
- **Every number has a source; a hypothesis is never stated as a finding** (R3). Numbers are shown relative to the sample first; raw counts are "creators in TrendsMesh evidence", a collected sample.
- **Naming:** `hook_trend` = hook, `format_trend` = format, `topic_trend` = topic.
- **Organic clips** are evidence, never footage; trending sounds are not licensed for paid ads unless the data says so.
- **Money** in USD at a stated rate, unless the context shows the client's own currency.
- **Artifacts:** a new artifact starts private; the user shares it. Republish to the same URL with the `Artifact` tool (with the older `publish_files`, the same slug and `base_version`), never a new link (`references/pages.md`).
- **Asking the user for decisions:** always restate the full content of every point (rule, option) in the same message.

## Hard rules (TR1–TR10, approved by the user 2026-11-04 with the changes noted in TR1, TR2 and TR10)
Rules from PB1 and PB2 that apply unchanged: **R3** (every number has a source; a hypothesis is never a conclusion), **CB6 naming** (hook / format / topic), **CB7 trend fidelity** (structure from evidence videos), **CB8** (evidence that lasts), **CB9** (sound trends), persisting every API / MCP response to the run.

### TR1. Category map: any category input, expanded underneath (user decisions, 2026-11-04)
- **Category input is not only a phrase** (user, 2026-11-04). The user may give one or more of:
  - a short phrase ("beauty");
  - a **product or landing-page link**: the agent reads the page and extracts the product type, use, audience and main claims, and turns them into seed phrases (a magnetic cat-eye gel polish → "cat eye nails", "nail art", "gel manicure", "nails"); the page also fills the brand intake (TR5) and, unless the user says otherwise, the focus (lens);
  - a **store or brand link or name**: the product range gives several seed phrases, one per product line;
  - **competitor names or links**: their product categories become seed phrases;
  - an **existing ad or video**: its topic and format become seed phrases.
  The seed phrases, each with its source, are shown at G1 and go through the same search, split and review as a single phrase. Raw inputs (pages, texts) are saved to `00_raw/`.
- Each seed phrase is searched (`search_trends`) and counts **relevant** results: `match.score ≥ trends.min_match` (default 40; search always returns the closest trends, so the raw count means nothing).
- **Expansion:** when relevant results are fewer than `trends.min_relevant` (default 10), the agent splits the phrase into 5–8 sub-categories and searches each. Sources for the split, in order: the names of the closest results (they show how the data names the category), the category's common sub-areas (beauty → hairstyle, nails, makeup, skincare, fragrance), and neighbours in the topic graph (`/topics/graph`). A sub-category that is still thin may be split once more (max depth 2). Results are merged and de-duplicated by trend id; each trend keeps its sub-category tag.
- Example (data 2026-11-04): "beauty" has 1 relevant result; "hairstyle" 18, "nails" 6.
- **Noise:** results matching `trends.exclude_terms` (news, sport, politics, celebrities unless the category is about them) are dropped and listed in the map, so the user can restore them. **Seasonal trends inside the category are not noise** (Halloween makeup in "beauty"): they are tagged and the seasonal guard in TR3 decides (dry run 2026-11-04).
- **Agent relevance review (part of G1, also in AUTO):** the match threshold alone lets off-category trends in (dry run: "Dementia in family life" matched "anti-aging" at 41; fashion and fan-edit topics matched "makeup" and "k-beauty"). The agent reads every kept trend and records drops and re-tags with a reason in `03_wip/map_review_vNN.json`; the map is rebuilt from it.
- **Stop splitting** at depth 2 even when leaves stay thin: a thin leaf after two splits means the corpus has little there (dry run: sunscreen, body lotion, self tanning returned 0 relevant), not that the query is badly worded.
- **Hooks have their own path:** hook trends are opening structures for any subject and score low on topic phrases. The SKILL lists rising hooks (`sort=rising`, `trend_type=hook_trend`) and **ranks them by fit, not by use** (issue #8, as Creative brief's CB3 and Organic AI video's transfers do): each hook is scored from its card on Creative brief's seven criteria for this category, market and focus, and only the best-fitting few (`hooks.shortlist`, 8) have their videos fetched. Whether the category already uses a hook (its evidence videos' `excerpt` / `hook_text` / `slot_fill` hold category words, as whole words) is shown next to it, never a gate: a hook with no category video yet is a **transfer**, labelled so (a hypothesis, R3). In a niche category the old gate ("used by ≥ 2 category videos") kept none of 138 rising hooks after a fetch of minutes.
- **Never write "no trends in the category":** when the map stays thin after expansion, show the closest trends marked "weak match".
- HITL: the map (sub-categories, counts, dropped items) is gate G1.

### TR2. Growth computed from evidence (today's replacement for `momentum`)
- For every trend in the map: all evidence videos (`/trends/{id}/videos`, all pages). Count distinct creators by the `creator` handle (`creator_id` is null in the public API) and the date each creator first appeared.
- **Windows:** recent = the last `growth.window_days` (default 14) days, ending `growth.lag_days` (default 2) days before the run, because collection lags (to verify in the backtest); baseline = the `growth.baseline_days` (default 28) days before it. **Growth ratio** = new creators per day in the recent window ÷ per day in the baseline (baseline floor 1 creator per window).
- Also recorded: total creators, platforms, **median views of the evidence videos**, **the top account's share of views**, `since`, active days, **last seen** (newest video), and the API's `momentum` when it is not null (shown beside ours, never instead of it in v1).
- **No evidence-language metric for now** (user, 2026-11-04): the share guessed from excerpts is too rough to show or to score. It returns when the API fills `languages` (`BACKEND_REQUESTS.md` #7).
- Numbers are worded as **"creators in TrendsMesh evidence"**: the evidence is the system's collected sample, not platform totals (R3).
- Every response and the computed table are saved: `02_research/videos/<trend_id>.json`, `02_research/growth.json`.

### TR3. Buckets (the slide's four stages): rule v2 after the backtest, rule v3 current (2026-11-04)
The draft rule v1 led with acceleration (growth ratio ≥ 1.5). The backtest on the beauty dry run (3 reference dates, 47–56 trends each) showed the **ratio does not predict later new creators** (Spearman 0.03–0.20), while **velocity** (new creators in the last 14 days, 0.40–0.57) and **recency** (0.33–0.45) do. Rule v2 therefore decides on velocity and recency; the ratio is shown, not used.

Checked in this order (first match wins):

| Bucket | Rule v2 |
|---|---|
| **Past its peak** (seasonal) | the trend belongs to a dated event that has passed within 60 days (Halloween, Día de Muertos, Thanksgiving, Black Friday, Christmas, …; `growth.py EVENTS`). A creator window always lags the event: on 4 Nov every Halloween trend still looked "act now" |
| **Act now** (early and spreading) | ≥ 4 new creators in the last 14 days; last new video ≤ 5 days before the reference date; median views of the evidence ≥ 5,000 (dry run: 7 new creators at a 214-view median is movement without an audience); not crowded (crowded = ≥ 100 creators and ≥ 90 days old); status not contradicted |
| **Still rising** | ≥ 2 new creators in the last 14 days and last new video ≤ 7 days (crowded trends go to "too late") |
| **Too late — leave out** | crowded, or active (last new video ≤ 14 days) with fewer new creators; or, in the paid view, crowded in ads (TR7) |
| **Past its peak** | otherwise: no new creator for 14 days, or ended (`include_expired`), or API momentum `cooling` / `over` |

**Review of the picks (part of G2, also in AUTO):** the agent reads each "act now" trend's description and evidence and may move it, with a written reason shown on the page ("Moved by review"). Moves in the dry run: an **event-bound** trend whose dates are in its description (Sephora Savings Event, 30 Oct – 2 Nov) → past its peak; a trend **crowded in paid** (hair extensions) → too late; a **general, mature hook** (`day _ of _`, 253 days, 3 of 65 videos about beauty) → still rising. Evidence mostly in another language than the market stays in the bucket but carries the risk in its card (TR4).

Backtest result of rule v2 (median new creators in the next 14 days, act now vs past its peak): 2.5 vs 1, 10 vs 2, 3 vs 2. Directionally right, small samples; recalibrate on every new category (TR9). The report shows every bucket, so the reader sees what to skip and why.

**Rule v3 (current, 2026-11-04, after the user's review of the first report):**
- **Velocity is read against the category, not as a raw count.** Velocity index = new creators in the last 14 days ÷ new creators of the typical active trend in the same category at the same date (median). A raw count grows when TrendsMesh simply collects more videos; the index does not. Act now: index ≥ 1.3 (and ≥ 3 new creators); still rising: index ≥ 0.6 (and ≥ 2).
- **Concentration gate:** a trend whose evidence views come more than 60% from one account is not spreading and cannot be "act now" (dry run: "Lip combo" 85% from the brand's own account, "Fall almond nails" 98% from one creator).
- **Band:** a topic is ranked among the category's topics, a hook among the rising hooks whose videos were read (hooks are cross-category; ranking the 5 beauty hooks that the category used among themselves meant nothing). Since issue #8 only the shortlisted hooks are read, so the page says "among the N rising hooks whose videos were read (the shortlist; M listed)"; the stage still comes from the velocity index against the category's typical trend.
- **Confidence** per trend: low when < 8 creators or one account > 60% of views; high when ≥ 15 creators, no account above 40% and status confirmed; otherwise medium. (Evidence language is not part of it for now, see TR2.)
- Other conditions of v2 stay (recency, median views ≥ 5,000, crowded, seasonal guard, review of the picks).
- Backtest v3 vs v2, same dates (median new creators after / share with 3+ new, act now): 3.0 / 64% vs 2.5 / 50%; 10 / 100% vs 10 / 100%; 8.0 / 90% vs 3.0 / 59%. A smaller and sharper "act now".

### TR4. Evidence check
- `status = contradicted` → out (listed at the end); `unconfirmed` → kept, labeled.
- **Language and market:** a trend from another language is a **hypothesis** for this market. There is no computed language metric for now (TR2); when the agent sees in the evidence it reads that a pick lives mostly in another language, it says so in the pick's risk line.
- `sensitivity_level` and `is_sensitive` videos are flagged.
- Every clip shown is saved with link, thumbnail, views and an **as-of date**; the brief-style **valid-until** date defaults to 14 days from the run while `visible_until` is empty.

### TR5. Fit and ranking
- Inside "act now" and "still rising", each trend is scored 1–5 on: growth ratio, earliness (age), spread (creators, platforms), confidence and status, fit to the category and the brand intake, transferability to the market, production feasibility. Weights in the config; the score table is saved.
- With own results (if approved): trends close to the user's best-performing content rank higher (the ExampleEdu lesson: the pattern of the channel's best short beat generic topics).
- **With a focus (lens):** the picks relevant to that recipient are re-ranked and each gets one line written for them (lead with / pair with / skip / over), including trends from lower buckets when they matter to the recipient (dry run lens "nail brand": cat-eye lead, leopard cat-eye next, the "your sign to" hook as opener, fall almond skipped, Halloween nails over).

### TR6. What to act on
For each pick (default top 5 in "act now", top 5 in "still rising"):
- **what it is:** name, type (hook / format / topic / sound), the structure taken from the evidence videos (formula, slot fills, where the text appears);
- **why now:** growth ratio, new creators, last seen, total creators and views, all with their source;
- **how to use it:** one or two sentences: angle and format for this category or brand (a seed for PB2);
- **window:** valid-until date; **risk:** language transfer, sensitivity, licence, saturation.
A hypothesis is never written as a conclusion (R3).

### TR7. Paid vs organic view
- **Scope:** every trend in "act now" and "still rising", plus the largest "too late" trends (≥ 30 creators), so the view can show where paid is already there while organic slows. A pick card shows the same verdict.
- **Check:** Meta Ad Library in the market country (free), active ads, query = the most specific product phrase of the trend. The agent keeps only relevant advertisers and records them with an example ad id (`02_research/ad_library_summary_vNN.json`).
- **Paid level per trend:** `none` (no relevant advertiser in the top results, worded **"none found in Ad Library titles"**, never "not in ads": the API returns titles only, PB2 lesson 5); `found` (1–3 relevant advertisers); `crowded` (4 or more, or a very large estimated count with relevant top results); `not_checkable` (hooks).
- **The view** is a matrix: organic stage (rising / slowing) × paid level (none / a few advertisers / crowded), each trend with its band and the advertisers found, plus a short agent reading (3–4 lines: the openings, the crowded ones, the saturated ones, what cannot be checked). "Rising in organic, none in paid titles" is the opening the slide promises.
- **Cross-check event dates in paid:** advertiser titles can correct a trend's description (dry run: an ad title said the Sephora Savings Event "Ends 11/9", the trend description said 30 Oct – 2 Nov).
- **With Foreplay connected:** per hook, how many paid ads use the structure, on which platforms, the longest run in days. Only then may the page say "rising in organic, not yet in paid".
- **Hooks are "not checkable in titles"** without Foreplay (dry run: "get ready with me" returned fitness and novel ads). The query for a topic is its most specific product phrase ("cat eye nails", "lash clusters", a brand name), not the trend name. The MCP answers inline: the agent transcribes the relevant ads (page, title, id, estimated count) into `02_research/ad_library_summary.json`.

### TR8. Snapshot and weekly digest
- Every run saves `02_research/snapshot.json`: per trend, the card fields used, the growth table and the bucket.
- **Digest** = diff against the previous run's snapshot: new trends, trends that entered "act now", trends that moved down, ended trends; plus TR9. To save calls, it re-fetches videos only for trends updated since the last run (`sort=updated`) and for every trend in "act now" or "still rising".
- Scheduling: an agent routine (local scheduled task or cloud routine; the API key lives in `.secrets/api_keys.env`).
- **Delivery: the link only** (user decision, 2026-11-04): the page is republished under the same link; no message is sent on the client's behalf.
- **Built (`growth.py diff`, dry run 2026-11-04):** `compute` writes `02_research/snapshot.json` on every run; `diff --prev <snapshot>` lists new, moved up, moved down and ended trends and checks the previous calls. Lessons built in:
  - **trend ids are not stable** across days (merges, re-promotion): a new and an ended trend whose names share ≥ 60% of their words are reported as one trend under a new id;
  - "ended" uses names only, whole words (otherwise "lip" matched "lip-sync"), and skips names that live on under another id;
  - a first digest without a stored snapshot can use one **rebuilt** from the evidence dates plus a full trend list saved that day (`--prev-cards`), labelled as rebuilt on the page.
- The digest is a section of the same page ("Since <date>"), republished under the same link.

### TR9. Calls are checked
- Each run re-checks the previous run's "act now" and "past its peak" calls: did new creators keep coming? Hit rate per bucket goes to `library/trend_calls.jsonl` (run, category, trend id, bucket, metrics then and now, verdict).
- **Before the first release: backtest** on saved snapshots (ExampleEdu dumps 2026-10-29, 10-30, 11-03, 11-04): bucket the trends as of the first date, compare with the last, tune the TR3 thresholds.

### TR10. Delivery: one shareable page
- Same pattern as PB2 CB12: a private Artifact (link works on a phone), republished on every run under the same URL; fallback a self-contained HTML file.
- **Read-only page, no decision buttons** (user decision, 2026-11-04): what the team does with a pick is decided outside the report. Gates G1–G3 happen in the chat with the agent (HITL) or by rule (AUTO).
- **One data source:** the page is generated from `04_final/report_vNN.json` (schema `schema/report.schema.json`), which the page builder assembles from the tool outputs and the agent's `picks_vNN.json` (template `templates/picks_template.json`).
- **One page, one view per chosen output** (user decision, 2026-11-04): a sticky switch at the top and a link per view: `#report` (category report, always), `#digest` (weekly digest, when chosen and a previous snapshot exists), `#paid` (paid vs organic, when chosen). Views switch on click and on the link's hash.
- **Report view:** the things to act on (as many as pass, not a fixed five), the lens section (if a focus was given), still rising, watch next, moved by review, the four buckets, the category map and "how sure are we".
- **Digest view** (v02 after the user's review, 2026-11-04: "very little information, show video examples"), in this order:
  1. a line on what it compares with (dates, rebuilt or stored snapshot) and a numbers strip (calls that held, moved up, new and rising, seasonal now over, slowing, ended);
  2. **the week in one minute**: 4–5 sentences written by the agent;
  3. **what to do this week**: 3–4 actions written by the agent;
  4. **moved up** and **new on the radar** as cards: stage, band, type, paid level, what it is, and **thumbnails of evidence videos published since the previous run** (linking to the videos);
  5. **last week's calls**: one card per "act now" call with ✓ / ✗, its stage now, this fortnight's velocity, and this week's videos;
  6. **cooling down**, grouped by reason (seasonal event over / slowing), and **ended or merged** (with re-identified trends).
  The agent's text lives in `picks_vNN.json` → `digest_reading` (`summary`, `todo`).
- **Paid view:** the matrix of TR7.
- **Position in the sample first, raw counts second (user decision, 2026-11-04).** "3 creators" says nothing to a reader; "3 creators in a sample where a typical trend gets 3" does. Each trend opens with **evidence at a glance**: momentum band ("top 25% of beauty topics", hooks "of all rising hooks") and the velocity index ("2.3× the new creators of a typical beauty trend"); spread (broad / a few accounts / one account, with the top account's share); reach of the evidence (total views, real platform numbers); freshness; confidence with its reason; Ad Library verdict (no evidence-language cell for now, TR2). Raw counts sit under "Raw counts in the sample", next to the denominator. Bands are coarse (top 10% / top 25% / top half / lower half) because a pool of ~50 trends does not support exact percentiles.
- Under the counts, one line states **the sample**: how many creators joined any mapped trend in the window, how many trends, which platforms (beauty dry run: 249 creators, 57 trends, TikTok only), and what "typical" means.
- Then clips (thumbnails with links), then the structure and the suggestion.
- Money shown in **USD at a stated rate, unless the context shows the client works in another currency** (account currency, store prices, market), then in that currency (user, 2026-11-04).
