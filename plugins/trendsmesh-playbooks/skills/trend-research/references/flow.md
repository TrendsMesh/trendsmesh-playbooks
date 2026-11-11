# The run, step by step

One section per step of `data/trend-research/steps.yaml` (the engine's `ref` points here:
`flow.md#<step id in lower case>`). Source: the handoff's `FLOWS.md` sections A to F and
`VARIANTS.md` (handoff `trend-research_v01`), with the plugin's changes from the trend research
plan. `R` below is the run folder. Rules: `rules.md`; check-ins: `checkin-cards.md`. The shared
references (`pages.md`, `trend-collection.md`, `schedule.md`) sit in the plugin's own
`references/` folder, two folders up from this skill (`../../references/`).

- **Every TrendsMesh and Ad Library answer is saved by the collector** (`trend-collection.md`):
  `tm trends collect on --run R` runs right before the first `search_trends` (B1, step 1), and
  again at every resume, right before the first TrendsMesh or Ad Library call after it (a session
  that resumes at D2 calls `ads_library_search` first). The marker it writes is this session's
  own: only this session's answers are saved to the run. If an answer comes with "This answer was not saved…", save it with `tm trends ingest`
  as it says.
- **JSON you write goes into a file** in `03_wip/` (or `02_research/` for the Ad Library summary)
  with the Write tool, a new `_vNN` for every change, never inline: inline JSON breaks on Windows.
  Record each file you write with `tm record --run R --file <path> --stage <stage> --source
  "<what it rests on>"`; the `tm research` tools record their own.
- Every number you write has its source next to it (R3), and creator counts are "creators in
  TrendsMesh evidence". Write outputs in the run's language.
- After each step's work: `tm done <step> --run R`, then `tm next`. A check-in after a step comes
  in `tm next` once the step is done: prepare what its card needs while you work.
- **A `tm` exit 2 is a stop**: tell the user what happened, what to do, and that the run continues
  from the same place (the message says so); fix the cause (a file, a fetch), then run the same
  command again. A wait you start yourself (a TrendsMesh limit, an answer you need from the user
  outside a check-in) is recorded: `tm stop --run R --reason <id> --what "<what>" --todo
  "<todo>"`, then `tm resume --run R` once it is cleared.

## The weekly run, in order

A weekly digest is a new run that follows the last one (decision 9). It walks the same steps;
what each does in a weekly run is under the step. In order:

| # | What | Step |
|---|---|---|
| 1 | `cd` into the workspace, `tm run new --playbook trend-research --name <name> --after <last run>`, `tm config write --from-previous`, then the level if the user asked for one | A0 |
| 2 | `tm research previous` (the snapshot, map, split and config of last week) | A2 |
| 3 | `tm trends collect on`, the searches of last week's split, and the `list_trends sort=updated` list (unfiltered, from page 1 back to last week's date) | B1 |
| 4 | the map (with last week's review carried over) | B2, B3 |
| 5 | the rising hooks, then `tm research map-change` | B4 |
| 5b | the hooks' fit scores, then `tm research hook-fit` (the shortlist) | B4 |
| 6 | `tm research fetch-plan` (tell the user how many minutes the fetch takes) | B4 |
| 7 | `tm research reuse` | B4 |
| 8 | fetch the plan's videos (every page) and the `get_trend` cards of its `check` list: the shortlisted hooks' first (B4), the rest after the map check-in (C1) | B4, C1 |
| 9 | `tm research hooks` | B4 |
| 10 | `tm research growth` | C2 |
| 11 | `tm research digest` (it stops until every called trend has videos) | F2 |
| 12 | the picks, with `digest_reading` (it needs the digest) | D1 to D3 |
| 13 | `tm research report` | E1 |
| 14 | publish to the same slug (`tm page link`) | E2 |
| 15 | the schedule kept or offered, then `tm research seeds` and `tm trends collect off` | F5, E3 |

---

<a id="a0"></a>
## A0 Intake and setup

**A new category (first run).**

- Readiness first (SKILL.md section 1). Then `tm run new --playbook trend-research --name
  <category, short> --json`: it gives the run folder `runs/04-trend-research/<date>_<name>/`.
- Ask the intake in **one batch**, each question with its default:
  - **"How involved do you want to be?"**: **Check every step** (each check-in on its own),
    **Just the big calls** (two: the category map, then the picks and the page; plus the weekly
    schedule question), **Hands-off** (none: I decide by the playbook's rules and report; I still
    stop when I can't go on without you, or when the map changed a lot since last week);
  - **the category**: a short phrase ("beauty", "nail art"). A product or landing-page link, a
    store or brand, competitors, or an ad as the input are not supported yet: say so in one line
    and ask for the phrase (for example the product type);
  - **market and language** (US / English; PL / Polish);
  - **focus (optional)**: who reads the report, a brand or sub-category ("a nail brand"); the data
    stays the category's, the page adds a section for them;
  - **outputs**: the category report (always), the weekly digest (the same page next week, with
    what changed and whether this week's calls held), the paid vs organic view (Meta Ad Library);
    default all three;
  - **currency** for any money on the page: USD at a stated rate, unless the context shows the
    client works in another currency.
- Answers JSON (`03_wip/intake_answers_v01.json`), the config's shape plus `level`:

  ```json
  {"level": "big_calls",
   "category": {"inputs": ["beauty"], "phrase": "beauty", "seeds": []},
   "market": "US", "language": "English", "market_lang": "en",
   "focus": "a nail brand", "currency": "USD",
   "outputs": ["category_report", "weekly_digest", "paid_view"]}
  ```

  `category.seeds`: more phrases the user gave for the same category (each a seed phrase). Then
  `tm config write --run R --answers 03_wip/intake_answers_v01.json` and `tm config check --run R
  --json`; each problem it lists has what and what to do: ask, write `_v02`, write again (allowed
  until A0 is done). The config changes thresholds only, never a rule.

**A weekly run** ("update my trend report", a scheduled task, or `tm due`'s reminder).

- First `cd` into <workspace> (the folder that holds `runs/`), and stay there for every `tm` call.
- Find the last run of this category: in `runs/04-trend-research/`, the trend research runs whose
  config has the same `category.phrase` and `market`; take the one no other run follows (the
  newest). When two are left from the same day, take the one furthest along: a done run before
  an unfinished one. The scheduled task's prompt names the category, market and workspace folder.
  - If it is not done, it is not a weekly run: resume it (`tm next`).
  - If there is none, it is a first run: ask the intake.
- `tm run new --playbook trend-research --name <the same name> --after <that run's folder>
  --json`, then `tm config write --run R --from-previous` (it copies the config and sets
  **Hands-off**), then `tm config check --run R --json`. **Only after the copy**, if the user asked
  for another level, `tm level <every_step|big_calls|hands_off> --run R`: a level set before the
  copy is replaced by Hands-off. Ask no intake questions.

**Both.** `tm done A0 --run R`. Collection is turned on later, right before the first search (B1).

<a id="a1"></a>
## A1 Category input and seed phrases

- The seed phrases are the category phrase and `category.seeds`, each with its source ("your
  phrase"). In a weekly run they are the previous run's (copied with the config).
- Prepare the G0 card: the seed phrases, the market and language, the currency, the focus, the
  outputs (`checkin-cards.md`). At Check every step it is asked after this step; at Just the big
  calls it joins the map card after B4; in Hands-off it is logged by rule.
- `tm done A1 --run R`.

<a id="a2"></a>
## A2 Previous run

- `tm research previous --run R --json`. In a weekly run it copies the previous run's latest
  snapshot, category map, split file and config into `00_raw/` (`prev_snapshot.json`,
  `prev_category_map.json`, `prev_split.json`, `prev_config.yaml`; read-only, never overwritten:
  a second call copies nothing and says so), and says where its page was published: this week's
  page goes to the same link. A first run copies nothing (exit 0).
- If it says the previous run has no snapshot (its growth step never ran), F2 rebuilds the
  previous week (V24).
- `tm done A2 --run R`.

<a id="b1"></a>
## B1 Search and split

TR1. The engine counts; you choose the phrases.

1. **Turn collection on**: `tm trends collect on --run R --json`, then at once the first search.
   **Search every seed phrase**: `search_trends` with `about` = the phrase and `limit` 50 (no
   `trend_type`, no `min_match`: the engine counts relevant results at `match ≥ 40` itself). If the
   answer has `has_more` and fewer than 50 results came back, ask for the next `page`, up to 50
   results per phrase. The summary shows each card's `match`.
2. **Write the split file** `03_wip/split_v01.json`: the seeds and, for every phrase with fewer than
   10 relevant results (cards with `match ≥ 40`), **5 to 8 sub-categories**:

   ```json
   {"root": "beauty",
    "queries": [
      {"query": "beauty", "parent": null, "depth": 0, "source": "seed"},
      {"query": "hairstyle", "parent": "beauty", "depth": 1, "source": "common_sub_areas"},
      {"query": "nail art", "parent": "beauty", "depth": 1, "source": "closest_names"}]}
   ```

   The sources, in this order: `closest_names` (the names of the closest results: how the data
   names the category), `common_sub_areas` (the category's usual sub-areas: beauty → hairstyle,
   nails, makeup, skincare, fragrance), `list_topics` (TrendsMesh's top-level topics, the
   vocabulary of `search_trends`: one `list_topics` call). Topic-graph neighbours are not used (no
   MCP tool).
3. **`tm research search-status --run R --json`**. Its `to_search` lists the split's queries not
   searched yet: that is your to-do, not a problem. Search them (as in 1), then run it again.
4. A sub-category still marked `SPLIT` (fewer than 10 relevant) at depth 1 may be split **once
   more** (depth 2): add its 5 to 8 children to a new `split_v02.json`, search them, check again.
   **Never split below depth 2**: a thin leaf there means TrendsMesh has little there ("thin leaf
   at depth 2: not split again"), not a badly worded query. Exit 2 lists what is wrong with the
   split file: fix it as a new version.
5. **A weekly run** searches what last week searched: its `split_v01.json` starts from
   `00_raw/prev_split.json`, the same `root` and the same queries with the same names (parents,
   depths and sources as they were), and every query in it is searched again (step 1's search for
   each; `search-status`'s `to_search` lists them). Add a sub-category only when this week's
   searches show a new one (a group of new relevant results the old queries do not name), as a new
   row with its source. A thin leaf stays a leaf; depth 2 is still the limit.
6. **A weekly run** also saves the updated list: `list_trends` with `sort` `updated` and **no
   filter** (no `trend_type`, `q` or `feed`), `limit` 50, from **page 1**, then the next `page`
   while `has_more`, and stop once a page's summary gives an `oldest_updated_at` on or before the
   previous run's reference date (its run date minus `growth.lag_days`, 2 days: the fetch plan's
   `since`). When `oldest_updated_at` is null (the cards carry no `updated_at`), keep paging while
   `has_more`. Without a list that reaches back that far, the fetch plan cannot tell what is
   unchanged and fetches everything (its `note` says so: then list more pages).
7. `tm done B1 --run R` once `to_search` is empty.

<a id="b2"></a>
## B2 Build the map

- `tm research map --run R --split 03_wip/split_vNN.json --json` (the latest split). It merges the
  searches, tags each trend with its sub-category, drops noise (news, sport, politics, names) and
  contradicted trends, and tags seasonal trends (they stay: TR3's seasonal guard decides). Output:
  `02_research/category_map_vNN.json` and `.md`.
- When the map stays thin after the last split, its closest trends are listed as **"weak match"**
  (V7). Never say there are no trends in the category.
- `tm done B2 --run R`.

<a id="b3"></a>
## B3 Relevance review

- Read every kept trend in `category_map_vNN.md` (its name and what it is). Drop the
  off-category ones and re-tag wrong sub-categories, each with a reason (lesson 2: dementia via
  "anti-aging", fan edits via "k-beauty"). Seasonal trends inside the category are not noise.
  A seasonal trend whose card shows the category's own craft is inside it, even when it is framed
  as a costume, a cosplay or a skit (for beauty: makeup, face paint, skin, hair or nails done for
  the look); drop a seasonal trend only when its card shows none of it (a mask, food, crafts).
- Write `03_wip/map_review_vNN.json`, names copied exactly from the map:

  ```json
  {"drop": {"Dementia in family life and memory": "off-category: matched 'anti-aging' on ageing, not beauty"},
   "retag": {"Glazed donut nails": "nails"}}
  ```

  Then `tm research map --run R --split 03_wip/split_vNN.json --review 03_wip/map_review_vNN.json
  --json`.
- **A weekly run** starts from last week's review (the previous run's latest
  `03_wip/map_review_vNN.json`): copy its drops and re-tags into this run's `map_review_v01.json`,
  then review the new trends. If the map stops because the review names a trend no search returned,
  that name was carried over from last week and its trend has left the searches: remove it from the
  review file (a new version) and build again, at every level. At Check every step and Just the big
  calls, list the names removed on the G1 card; in Hands-off log them in G1's rule note and the
  final report.
- `tm done B3 --run R`.

<a id="b4"></a>
## B4 Hooks path

Hooks are opening structures for any subject and score low on topic phrases, so they have their
own path (TR1).

1. **Rising hooks:** `list_trends` with `sort` `rising`, `trend_type` `hook_trend`, `limit` 50,
   pages 1 and 2 (pass page 1's `as_of`, if it gives one, to page 2 so both read one ranking).
2. **A weekly run:** `tm research map-change --run R --json`. When it says the map changed a lot
   (V26: at least 25 % of the mapped trends are new, or a group is new), G1 is `changed_a_lot` in
   Hands-off, and the run stops there. **To clear it:** show the new map as the G1 card
   (`checkin-cards.md`); when the user says to go on (after any review changes they ask for and the
   map rebuilt), record `tm decide G1 accept --change --run R --note "<their words, and what
   changed>"`. `tm resume` does not clear it: only that decision does. Then `tm next`.
3. **Rank the hooks by fit, from their cards** (no video is fetched for this). A hook is a structure
   that can carry almost any subject, so the question is which few fit this category best, not
   whether the category uses them already. Read every hook card of the rising lists and the
   searches (its name, `what_it_is`, `reach`, `momentum`, `active_for_days`, `status`) and score it
   1–5 on Creative brief's seven criteria (CB3, `../../creative-brief/references/rules.md`), read for
   this category, its market and the focus:
   - `brand_fit`: the category's tone (and the focus brand's, if one is given);
   - `persona_fit`: the category's audience, its age and culture;
   - `bridge`: the structure carries a story of this category (a "day _ of _" log of a routine, a
     "step 3 of N" for a product with steps);
   - `lifecycle`: early or tired, from `momentum` and `active_for_days`;
   - `transfer`: it survives the market language (no English-only wordplay or sound-alike) and the
     subject change: a hook no category video uses yet is a hypothesis (Organic AI video's transfer
     rule), not a reason to drop it;
   - `sensitivity`: `sensitivity_level`, and anything the category should not touch;
   - `feasibility`: it can be made in the category (a face on camera, a setting, a prop).

   Write `03_wip/hook_fit_v01.json`, every hook candidate, a `why` (one sentence) for the ones that
   score best:

   ```json
   {"c2173b6a4e7f496093804bb8efb3e785": {"brand_fit": 4, "persona_fit": 5, "bridge": 5,
     "lifecycle": 3, "transfer": 4, "sensitivity": 5, "feasibility": 5,
     "why": "a numbered daily log fits a 30-day skincare routine"}}
   ```

   Record it, then **`tm research hook-fit --run R --file 03_wip/hook_fit_v01.json --json`**: it ranks
   the hooks by their mean score (ties keep TrendsMesh's rising order) and keeps the best
   `hooks.shortlist` (8) that fit at least `hooks.min_fit` (a mean of 3), never a contradicted one,
   in `02_research/hooks_shortlist_vNN.json`. Exit 2 lists each problem (a hook not scored, a score
   outside 1–5): fix it as a new version.
4. **The fetch plan:** `tm research fetch-plan --run R --json`. `fetch` = this map's trends and the
   shortlisted hooks (in a weekly run minus `reuse`, plus every previous "act now", "still rising"
   and "past its peak" trend); `check` = last week's trends not in this week's map (C1 gets their
   cards); `calls_estimate` = about how many `get_trend_videos` pages; `minutes_estimate` = about
   how long they take. It stops while the hooks are saved but not ranked (step 3 first). A weekly
   run then copies the unchanged ones: `tm research reuse --run R --json`.
5. **`get_usage`** and compare with `calls_estimate` (`trend-collection.md`, pacing). Short: say so,
   record the stop, wait for the reset. **Before a fetch of minutes** (`minutes_estimate` 2 or more,
   here and at C1), tell the user in one line, at every level: "Fetching the evidence videos: about
   N minutes." It is a notice, not a question; then go on.
6. **The shortlisted hooks' videos:** for each shortlisted hook in `fetch`, `get_trend_videos` as in
   C1. Only these hooks are fetched. After the first trend's pages, **`tm trends check-fields --run R
   --json`**: exit 2 names the fields the answers lack (the run needs `creator` or a handle in `url`,
   `published`, `views`, `thumbnail_url`, `url`, and `match` on search cards): tell the user and wait.
7. **`tm research hooks --run R --terms "<the category's words>" --json`**: the words a category
   video would carry in its excerpt, hook text or slot fill (the phrase, the sub-categories and
   their common words). Words match whole, never inside another word ("art" is not in "start"), so
   give each in the forms the videos use: "beauty,makeup,hair,nail,nails,lash,lashes,brow,brows,
   skin,lip,lips", and phrases as they are written ("nail art"). It keeps every shortlisted hook,
   in fit order, and counts its videos in the category as information, never as a gate: a hook with
   at least one is **used in the category**, one with none is a **transfer** (it fits, nobody in the
   category uses it yet). A stop names the shortlisted hooks with no saved videos (fetch them), or
   hooks saved after the fit scores (score them in a new version, `hook-fit` again).
8. Prepare the G1 card (`checkin-cards.md`): the sub-categories with counts, what was kept and
   dropped and why, the weak matches, the shortlisted hooks in two lists (used in the category, with
   "used in your category: N videos", and transfers), each with its fit. `tm done B4 --run R`.

<a id="c1"></a>
## C1 Evidence videos

- **When G1 changed the map** (the user asked for drops or re-tags and it was rebuilt after B4),
  run `tm research fetch-plan --run R --json` again (and `reuse` in a weekly run): the list to
  fetch follows the new map.
- **Fetch the rest of the plan's `fetch` list** (the map's trends, and in a weekly run last week's
  calls), every trend whose videos are not saved yet. Before the pull, `get_usage` again if B4's
  check was more than a few minutes ago; short: stop and wait for the reset, then continue from
  the same place (on resuming, `collect on` again right before the next call).
- Per trend: `get_trend_videos` with `trend_id`, `order` `recent` and the largest `limit` the tool
  takes, page 1, then the next `page` while `has_more`, **at most 1,000 videos per trend**. The
  summary says `videos`, `has_more`, `newest`, `oldest`; nothing else needs reading now.
- If `check-fields` has not run yet (no hook was fetched at B4), run it after the first trend.
- **A weekly run:** `get_trend` for each trend in the fetch plan's `check` list (last week's trends
  that left this week's map): without its card the digest counts it as ended.
- Without the collector (the answers reach you whole): `trend-collection.md`, the fallback
  (subagents in batches of ten trends, each page saved with `tm trends ingest`).
- `tm done C1 --run R`.

<a id="c2"></a>
## C2 Growth, stages and snapshot

- `tm research growth --run R --json` (as of the run's date). It computes, per trend, the new
  creators in the last 14 days (ending 2 days before the run) against the 28 days before, the
  velocity index against the category's typical trend, the band, spread, median views, freshness,
  confidence and the stage by rule v3, and writes `02_research/growth_vNN.json/.md` and the
  snapshot for next week.
- A stop names a trend with no saved video page (fetch it, run again) or a trend whose videos carry
  no creator (`tm trends check-fields`, tell the user, tell the TrendsMesh team; it continues from
  the same place once fresh videos carry one). Hook candidates without creator data count as 0
  new creators in the hooks ranking and are listed: say so in the final report.
- Never compute a growth number, a band or a stage yourself.
- `tm done C2 --run R`.

<a id="c3"></a>
## C3 Backtest

- **A new category** (no previous run of it): `tm research backtest --run R --as-of <date> --json`
  at three past dates, 42, 28 and 14 days before the run (the beauty dry run's spacing). Each
  writes `03_wip/backtest_<date>_rule_v3_vNN.json/.md`: the stages then and the new creators in the
  14 days after. Read the summary: does "act now" gain more new creators than "past its peak"? Say
  it in "How sure are we" (the page shows the files you pass at E1); small samples are indicative
  only.
- **A weekly run** (same category, same rule): no backtest; the call check (F2) measures the
  calls. `tm done C3 --run R`.

<a id="f2"></a>
## F2 Digest and call check

Only when the weekly digest is an output (the engine skips it otherwise). TR8 and TR9.

- **The previous state.** A weekly run has `00_raw/prev_snapshot.json` from A2. Without it (a first
  run with the weekly digest, or a previous run that never reached growth), rebuild it from the
  evidence dates: `tm research rebuild-previous --run R --as-of <the previous run's date; in a
  first run, the run's date − 7 days> --json` (V24). The page then says last week is rebuilt, and
  "ended" is left out.
- `tm research digest --run R --json`: new trends, trends under a new id (≥ 60 % shared words),
  moved up, moved down, ended, and the call check of last time's "act now" and "past its peak"
  calls, appended to `library/trend_calls.jsonl`. **It stops until every called trend has a saved
  video page** and names them: fetch each (`get_trend_videos`, every page), then run it again. A
  call whose saved videos have no dated video with a creator is `unknown`, never dropped: say
  which.
- The digest's numbers feed the picks' `digest_reading` (D3): the week in one minute and what to
  do this week.
- `tm done F2 --run R`.

<a id="d1"></a>
## D1 Read the evidence

- For every "act now" trend and the top "still rising" ones (by the latest growth): `tm research
  evidence --run R --trend <id> --json` (the top 5 videos of the last 45 days by views, added to
  `03_wip/evidence_dump_vNN.txt`). Read: the structure (formula, slot fills, where the text
  appears), who drives the views (one account?), dates in the description (an event: `get_trend`
  for its card when the growth row lacks it), the language when it is obvious.
- Describe a trend from its evidence videos, not from its name (CB7).
- `tm done D1 --run R`.

<a id="d2"></a>
## D2 Paid vs organic (Ad Library)

TR7. Through the Meta Ads MCP's `ads_library_search`.

- **Scope.** With the paid view: every "act now" and "still rising" trend, plus every "too late"
  trend with ≥ 30 creators. Without it: only your picks get a verdict, so write the draft picks
  first (`03_wip/picks_v01.json`, D3's file: the moves and the picks) and check those.
- **Collection** (a resume, a new session): `tm trends collect on --run R` right before the first
  `ads_library_search`, so its answers are saved: the check below needs one per query.
- **Per topic trend:** `ads_library_search` in the market's country, active ads, with the **most
  specific product phrase** of the trend ("cat eye nails", "lash clusters", a brand), not the
  trend's name. Keep only the relevant advertisers (matching is loose: "cat eye nails" returns
  fridge shelves); note each with an example ad id. Cross-check event dates in the ad titles (an
  ad "Ends 11/9" corrects a description's dates). **Hooks are not searched**: they are
  `not_checkable`, "Not checkable without Foreplay".
- **Levels:** `none` (no relevant advertiser: say **"none found in Ad Library titles"**, never that
  it is not in ads; the Ad Library returns titles only), `found` (1–3 relevant advertisers),
  `crowded` (4 or more, or a very large estimated count with relevant top results),
  `not_checkable` (hooks).
- Write `02_research/ad_library_summary_v01.json`:

  ```json
  {"checked": true,
   "checks": [
     {"trend_id": "<id>", "trend": "<name>", "query": "cat eye nails", "level": "found", "estimated": 120,
      "advertisers": ["Glamnetic (4 ads)"], "example_id": "1117172174349445", "note": "<what the titles show>"},
     {"trend_id": "<hook id>", "trend": "<name>", "query": null, "level": "not_checkable", "estimated": null,
      "advertisers": [], "example_id": null, "note": "Not checkable without Foreplay"}]}
  ```

  Record it (`tm record`, source "your reading of the Meta Ads MCP ads_library_search answers in
  02_research/ad_library/"). **When Meta fails** (not connected, signed out, refused): `"checked":
  false` for the whole run, with only the hooks' `not_checkable` rows: the paid view and the card
  verdicts say "not checked"; the report is otherwise complete (V22).
- **`tm research paid check --run R --file 02_research/ad_library_summary_vNN.json --json`**: with
  the paid view, right after the Ad Library searches; without it, after the draft picks. Exit 2
  lists what to fix (a trend in scope with no row, a level the advertisers don't support, a query
  with no saved answer, a forbidden phrase): fix it as a new version and check again.
- `tm done D2 --run R`.

<a id="d3"></a>
## D3 Review of the picks

TR3's review, TR4 to TR6. Start from D2's draft picks when it wrote one (the latest
`03_wip/picks_vNN.json`, copied to the next version with the paid verdicts in mind); otherwise copy
`templates/picks_template.json` to `03_wip/picks_v01.json`. Fill it:

- **Moves** (only from "act now", each with a reason of a sentence or two, shown on the page as
  "Moved by review"): an event-bound trend whose dates are in its description → past its peak (or
  too late, when ad titles show it still runs); a trend crowded in paid → too late; a general,
  mature hook → still rising.
- **Picks**: the top 5 "act now" and top 5 "still rising" after the moves (`picks.act_now`,
  `picks.still_rising`), each with `what` (the structure from the evidence), `how` (angle and
  format for this category or brand: a seed for the creative brief) and `risk` (status,
  concentration, the evidence's language when it is mostly another, licence for sounds, paid
  crowding, seasonality; a pick whose evidence is flagged sensitive says so in its risk).
  `act_now_other`: "act now" by the numbers but not recommended yet, with why.
- **`scores`** (required, TR5): every pick, each criterion a whole number 1–5: growth, earliness,
  spread, confidence, fit, transfer, feasibility.
- `lens` only with a focus; `watch_next` as a hypothesis; `paid_reading` (3–4 lines) only with the
  paid view; `digest_reading` (`summary` 4–5 sentences, `todo` 3–4 actions) only when F2 wrote a
  digest; `outputs` in the page's words (`report`, `digest`, `paid`) for the run's outputs;
  `as_of`, `market`, `category`.
- Never write a hypothesis as a finding (R3), and use the fixed words (`rules.md`). What the
  evidence shows (the structure, the counts, who posts it, the language) is said plainly; what it
  does not show is worded as a suggestion or a guess: `how` is advice ("try it as a weekly
  series", "could pair with another pick"), and a claim about fit, effect or who it helps ("it
  mainly helps big brands", "it works for any product") is a hypothesis ("may", "probably", "my
  guess").
  Name the evidence's language when it is mostly another ("mostly Portuguese"), not only "not in
  English".
- **`tm research picks check --run R --file 03_wip/picks_vNN.json --json`**. Exit 2 lists each
  problem: fix it as a new version and check again. Exit 0 gives the weighted totals: order the
  picks by them. Record the file.
- `tm done D3 --run R`. G2 follows (`checkin-cards.md`): on its own at Check every step, in the
  report card at Just the big calls, by rule in Hands-off.

<a id="e1"></a>
## E1 Build the page

- `tm research report --run R --picks 03_wip/picks_vNN.json [--backtest
  03_wip/backtest_<date>_rule_v3_vNN.json ...] --json` (the Ad Library summary and the digest's
  previous snapshot are found by themselves). It writes `04_final/report_vNN/` with `index.html`,
  `report.json` and the evidence thumbnails in `assets/`, and one view per chosen output
  (`#report`, `#digest`, `#paid`). A first run without a digest says the digest view comes next
  week.
- Look at the page's text once (the act now cards, the sample line): numbers relative to the
  sample first, raw counts under "Raw counts in the sample".
- `tm done E1 --run R`. G3 follows: on its own at Check every step (the local path and the views);
  at Just the big calls the card **"Approve the picks and the page"** is shown once, here, for G2
  and G3 together, and each is recorded on its own: `tm decide G2 accept --run R`, then `tm
  decide G3 publish --run R` or `tm decide G3 keep_local --run R` (their choices differ, so the
  card's own id is not used). Hands-off: G3 by rule, `keep_local` when neither `Artifact` nor
  `publish_files` is in the session, otherwise `publish`.

<a id="e2"></a>
## E2 Publish

- Follow `references/pages.md` (plugin root) with the page `report`: `tm page link --run R --page
  report --json` for an earlier link and `tm page files --run R --page report --json` for the
  `Artifact` tool's `file_path` and `files`; the first page is a new private artifact, a weekly
  page goes to the same `url` from `tm page link` (its files listed first, the ones this week's
  page lacks removed with `null`); then `tm page published --run R --page report --url <url>
  --version <the version id> --json`. With the older `publish_files`: the same slug and
  `base_version`, `--slug` in the record. Never republish while the user is still deciding on the
  page.
- Skipped when G3 is `keep_local`: give the local `index.html` path instead.
- When the tool refuses the files: `references/pages.md`, "A refused publish" (the local
  page, said plainly, nothing recorded as published).
- Delivery is the link only: no message is sent to anyone (TR8).
- `tm done E2 --run R`.

<a id="f5"></a>
## F5 Weekly schedule

Only with the weekly digest. GS comes first; `by_hand` skips this step.

- Follow `references/schedule.md` (plugin root): with `create_scheduled_task` in the session and
  the user's yes, a weekly task on the config's `digest.schedule` day (`weekly_monday` by default)
  at 09:00 local, recorded with `tm research schedule --run R --how desktop_task --id <taskId>
  --cron "<cron>"`. A task that already exists for this category (last week's, or found with
  `list_scheduled_tasks`) is kept and recorded again: never a second one. On `by_hand`, record `tm research schedule --run R --how
  by_hand` when GS is decided and say the one sentence.
- `tm done F5 --run R`.

<a id="e3"></a>
## E3 Hand the picks on (seeds)

- `tm research seeds --run R --json`: one seed per accepted "act now" and "still rising" pick in
  `<workspace>/library/seeds.jsonl`, for the creative brief (PB2) and organic video (PB3, `tm run new
  --playbook organic-video --seed`). A seed is never rewritten.
- `tm done E3 --run R`, then `tm trends collect off --run R`.
- `tm next` says `done`: the final report (SKILL.md section 3).
