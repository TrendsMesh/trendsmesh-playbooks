# The run, step by step

One section per step of `data/steps.yaml` (the engine's `ref` points here: `flow.md#<step id in
lower case>`). Source: the handoff's `FLOWS.md` sections A to E and path C-R (the re-cut, handoff
v03) and `VARIANTS.md`, with the plugin's changes from the design. `R` below is the run folder. Tools record their own outputs; every file you
create yourself is recorded with `tm record` (SKILL.md section 5); raw MCP answers are saved verbatim next to what they feed.
Every number you write has its source next to it (R3). Write outputs in the run's language.
**JSON arguments are files, never inline** (`--peak`, `--latest`, `--control`, `--params`,
`--settings`): write the JSON to a file in `03_wip/` and pass its path. On Windows inline JSON
loses its quotes on the way to `tm`, and a file is also the trail R3 asks for.

After each step's work: `tm done <step> --run R`, then `tm next`. The check-in after a step is
named in `tm next`'s `checkin` while you work, so prepare what its card needs
(`checkin-cards.md`). Tools that need a tier not installed stop with exit 2: ask the user's yes
with the size, then `tm env install <tier> --yes`, run with the 10-minute timeout or in the
background (SKILL.md section 1: long commands).

---

<a id="a0"></a>
## A0 Intake and setup

- Readiness (SKILL.md section 1) comes first; then `tm run new --name <name> --json`.
- Ask the intake batch (SKILL.md section 2). Answers JSON, the config's shape plus `level` and
  `flows` (leave out what the user did not change; defaults come from the engine):

  ```json
  {"level": "big_calls",
   "account": {"id": "1234567890", "market": "PL"},
   "languages": {"working": "pl", "market": "pl"},
   "product": {"name": "...", "landing_url": "https://..."},
   "brand": {"assets_dir": "C:/Users/.../Moje reklamy", "rules": "...", "compliance": "..."},
   "outputs": ["creative_brief", "edited_video", "ai_video"],
   "budget": {"ai_usd": 15, "voice_credits": 20000},
   "intake": {"voice_rights_confirmed": true}}
  ```

- **The live test only when the user picks it by name** (never a default, at any level: it is the
  one output that spends ad money and publishes ads). Then add `"live_test"` to `outputs` and the
  daily budget and days they give, `"budget": {..., "test_per_day": <theirs>, "test_days": <theirs>}`:
  no amount is suggested or assumed, and `tm config check` asks for both when they are missing.
  Once the config is written, **estimate it from the account's numbers**: the account's totals
  over the history window (`ads_get_ad_entities`, level account, `time_increment=7`, the last
  `winner.history_days` days, the same fields as A1; save the answer verbatim as
  `01_base/account_history_v01.json` and record it), then `tm r4 --estimate --run R --account
  01_base/account_history_v01.json --json`. The ad isn't chosen yet, so this is rough: one line
  per kind of change (opening, middle, promise and call to action, fatigue), each with what it
  needs and whether the budget given reaches it. Tell the user in plain words, and that it is
  worked out again on the chosen ad's numbers right after the diagnosis.

- Write it to `03_wip/intake_answers_v01.json`, then `tm config write --run R --answers <file>`
  and `tm config check --run R --json`. Exit 2 lists problems, each with what and what to do:
  ask the user, write `_v02`, write again (allowed until A0 is done). The config changes
  thresholds only; never put a rule change in it.
- Hands-off: the budgets given here are approved by the intake itself (the live test's too, when
  picked; its launch is still asked, `#e3`). An output whose budget is
  missing waits at its first paid step, and every later step waits with it. One budget per kind
  serves the whole run: `ai_usd` covers ProPainter, Veo and the AI video together,
  `voice_credits` the voiceover lines and the music takes together; size them for all of it.
  With the edited video,
  also ask the two re-cut limits (the config is fixed once A0 is done): how far a re-cut may go,
  `"recut": {"max_level": 2}` (0 to 5; unset means 2, the free levels; 3 or more needs
  `budget.ai_usd`, 5 needs `budget.voice_credits`), and whether a segment weak by design may be
  re-cut when the middle is not fading, `"diagnosis": {"structural_recut": false}` (`references/recut.md`
  section 1). The re-cut budget never stops a Hands-off run: what has no budget waits.
- Run `tm doctor` again for the chosen outputs if they differ from the first check.
- `tm done A0`.

<a id="a0b"></a>
## A0b Results library (R5)

- `tm library summary --category "<product category>" --market <market> --json`; save the
  answer as `02_research/library_summary_v01.json` and record it (source `tm library summary`).
- What won in this category and market goes higher in A5's ranking; what lost goes lower. An
  empty library is fine: say "no earlier results" in the strategy brief.

<a id="a1"></a>
## A1 Fading winners (R1)

Read `rules.md` first. The fetch must fit your context (`meta-mcp.md` has the tool's quirks):

1. Dates: `last` = today − 2 (R1 cuts the last two days), `first` = last − 90 days. That is 13
   whole weeks ending on `last`, the same 7-day windows the engine uses.
2. **Weekly totals for every ad:** `ads_get_ad_entities`, ad level, the user's account,
   `time_increment=7`, `first`..`last`, fields only: id, name, spend (`amount_spent`),
   impressions, frequency, cpm, `unique_link_clicks_ctr`, `video_p25_watched_actions`,
   `video_thruplay_watched_actions`, results, `cost_per_result`, and the retention ladder R2
   reads: `video_play_actions`, `video_p50_watched_actions`, `video_p75_watched_actions`,
   `video_p95_watched_actions`, `video_p100_watched_actions`, `video_avg_time_watched_actions`.
   Without the ladder `tm diagnose` falls back to the old ThruPlay rule and can't see which part
   of the middle fades. Save each page verbatim as
   `01_base/meta_weekly_ads_p01.json`, `_p02` ... and record each (source: the tool and its
   parameters).
3. **Account weekly totals:** the same call at account level → `01_base/meta_weekly_account.json`.
   If the account level gives nothing, pass the ad files as the account too: the engine sums them.
4. **Daily rows for the top 5 ads by spend only** (`time_increment=1`, same dates, R1's fields
   from step 2 without the ladder: R2 reads the weekly windows, and the daily rows are the bulk of
   the fetch) → `01_base/<ad_id>_meta_daily.json`. They are the evidence for the chosen ad (R1) and its daily
   chart. Do not pass them to `tm r1` beside the weekly rows of the same ad: they would count
   twice. If the ad chosen at G1 is not in the top 5, fetch its daily rows the same way before
   A1a.
5. `tm r1 --run R --ads 01_base/meta_weekly_ads_p01.json [more pages] --account
   01_base/meta_weekly_account.json --json` writes `01_base/winner_ranking_vNN.json`.
6. Prepare "Pick the ad" (G1): the fading ads by rank (spend, cost per result peak → now, the
   rise, p-value, account trend, value to recover, fatigue signals CTR, ThruPlay, frequency),
   then the stable ones, then "not enough data" (never ranked). Every figure from the ranking
   file. The choice is the ad id. Hands-off: #1 by rule.
7. No ad is fading: say so plainly with the ranking, record `tm decide G1 none --note "<ranking
   file>: no fading ad"` (at Just the big calls skip this: G1 belongs to the "Pick the ad" card,
   which never comes, and the engine refuses it at A1), `tm done A1`, then at A1a `tm decide G1a
   do_not_refresh --by rule --note "no fading winner"`: the run ends with no spend.

<a id="a1a"></a>
## A1a Funnel diagnosis (R2)

- From the ranking, take the chosen ad's `peak` and `latest` windows into
  `03_wip/diagnosis_windows/peak_v01.json` and `latest_v01.json` (record them; source: the ranking
  file), and its `account_ratio`, then run `tm diagnose --run R --peak <peak file> --latest
  <latest file> --account-ratio <x> --json` (writes `04_final/diagnosis_vNN.json`). When both
  windows carry the retention ladder (plays and p50 to p100, from A1's weekly fields), R2 reads the
  middle from its conditional steps (p50/p25, p75/p50, p95/p75: a drop of 3 points or more with
  p < 0.1); the diagnosis' `ladder` holds the peak, the latest and the steps that dropped.
- **Then the structural check (R2b), always** (`rules.md`). The other ads that use the same video:
  `ads_get_creatives` across the account (each creative's video id and thumbnail), and
  `ads_get_ad_videos` for the length. The same video id is the same file; a re-upload of the file
  gets a new id, so a match of thumbnail and length counts too (look at both thumbnails). For each
  of those ads and the chosen ad: `ads_get_ad_entities`, ad level, the ad's whole life (one total
  row, or its rows), the fields `video_play_actions`, `video_p25_watched_actions` to
  `video_p100_watched_actions` (p25, p50, p75, p95, p100), with `date_start` and `date_stop`.
  Save every answer verbatim in `01_base/` and record it. Then write `03_wip/retention/uploads_v01.json`, one object of ad id to
  that ad's Meta rows, copied unchanged from the saved answers (where Meta wraps the rows in a
  string, the decoded list): `{"<ad id>": [{"date_start": "...", "date_stop": "...",
  "video_play_actions": "...", ...}], "<ad id>": [...]}`. Record it (source: the files it is
  copied from) and run `tm structural --run R --uploads 03_wip/retention/uploads_v01.json
  --length-s <the video's length from ads_get_ad_videos> --json` (writes
  `04_final/structural_vNN.json` and adds `structural` to the diagnosis). An upload under 1,000
  plays is skipped; weak by design needs the same weakest step in every counted upload, at least
  two. With no other upload, run it on the chosen ad alone: it records "not structural".
  **Then `tm next`.**
- If `tm next` offers only `do_not_refresh`: relay the message (landing page or offer, the whole
  account, the auction, an unclear cause, or a stage the plugin cannot refresh for this ad),
  record it, and the run ends with the diagnosis report and no spend. An `unclear` stage is shown
  to the user as it is. A structural weakness found in such a run is reported as an opportunity
  in the same report.
- Otherwise write the "Diagnosis" section of `04_final/strategy_brief_v01.md`
  (`templates/strategy_brief_template.md`): funnel metrics peak → now, the retention steps, the
  account trend, the verdict, the `target_stage` and why, with the numbers and their file.
  `also_seen` stages are supporting signals; the structural check is reported beside them, as an
  improvement opportunity, never as what is fading.
- **The re-cut (flow R).** A `middle` target turns it on by itself. A structural weakness
  (`structural.structural` true) under another target: at Check every step and Just the big calls,
  offer the re-cut on the diagnosis card as an option next to the refresh ("the file is weakest at
  12.1–18.1 s in all 4 ads that use it"); if the user takes it, `tm flow R --run R` before you
  record the diagnosis. In Hands-off, run `tm flow R --run R` yourself only when the run's
  `config.yaml` has `diagnosis.structural_recut: true`; otherwise the weakness stays a reported
  opportunity (no re-cut, no spend) and the run goes on with its target. `tm flow R` refuses
  (exit 1, with the reason) a diagnosis that allows no re-cut, Hands-off without that setting, and
  a run past C1: that refusal is the answer, never something to work around. It is decided here.
- "Accept the diagnosis" (G1a): `refresh` (note: the target stage, and "plus the re-cut of the
  structural weakness" when flow R was turned on) or `do_not_refresh`. When the refresh is a
  re-cut (a middle target, or the re-cut offered for a structural weakness), the card says what it
  can offer before the breakdown: the kinds of variant `tm changes --stage middle` lists for the ad,
  each one change, **each with its level** in plain words ("level 0, a pure edit, free"; "level 4,
  a new AI shot, paid": `recut.md` sections 2 and 3), and that the exact variants are chosen after
  the breakdown, at the variants check-in.
- **The live test's estimate on the chosen ad**, right after G1a `refresh` when the live test is in
  the run (`tm next` reminds you at A2): the ad's latest window from the ranking as
  `03_wip/test_control_v01.json` (record it; source: the ranking file), then `tm r4 --estimate
  --run R --stage <target_stage> --control 03_wip/test_control_v01.json --variants <n> --json`
  (`<n>`: the variants you expect, 1 when unsure; a re-cut adds `--recut-step` or `--shorter` as
  at E1). Tell the user what it needs. Exit 2: the budget given cannot reach the minimum events,
  and the run stops here, at the start, not at E1 after the work. Give the calculation and the
  same choices as the R4 stop: a higher daily budget or more days (`tm live-test budget --run R
  --per-day <amount> --days <days>`, in Hands-off with `--note "<their words>"`, then `tm r4
  --estimate` again), or skip the live test (`tm live-test drop --run R`); the other outputs go on.

<a id="a2"></a>
## A2 Winner source file

- Find the chosen ad's video in the brand assets folder (name, length and look matching the ad's
  creative from `ads_get_creatives` / `ads_get_ad_videos`). Copy it to
  `01_base/<ad_id>_original.<ext>` and record it (source: the brand folder path). Ask whether a
  better source exists: the editing project, clean clips without captions, a higher resolution,
  language versions, separate voice and music tracks.
- Not there: the stop in SKILL.md section 7, recorded with `tm stop`, then wait. Once the user
  has put it there: `tm resume`, `tm next`, copy and record it.
- Last resort, only when the user cannot get the file: the low-quality preview, recorded with
  "low-quality preview, not the original" in the manifest, and said in every output that uses it.

<a id="a3"></a>
## A3 Winner breakdown

- The first teardown on a computer downloads the speech model (about 1.6 GB, a few minutes): say
  so first, and run it with the 10-minute timeout or in the background.
- `tm tool teardown --run R 01_base/<ad_id>_original.<ext> --lang <code> --json` →
  `02_research/teardown_vNN.json`, frame sheets in `02_research/teardown_vNN_frames/`, and a
  transcript (no speech is normal for text-card ads, lesson 3).
- **Look before you trust it.** Overlay detection is tuned on synthetic clips. Each overlay has a
  `kind` (`word_captions`, `text`, `full_frame` for an end card or full-frame title, `graphic` for
  edges with no text found), a `confidence` and a `check` (why to look at it, or null). Read the
  frame sheets (open several PNGs) and check every overlay box, its start and end,
  `touches_edge`, `semi_transparent`, every `possible_whole_shot_overlays` note and every
  `check_frames` region against what you see, the ones with a `check` first. Word-by-word
  captions are one `word_captions` overlay: `spans_s` says when words are on screen and
  `transcript.aligned` whether they follow the speech; open frames inside its spans to confirm
  the box. Semi-transparent bars and shadows count (lesson 12). Write the corrected list to
  `03_wip/breakdown/overlays_checked_v01.json` (the teardown's overlay fields, `kind` and
  `spans_s` included, with what you changed and why) and plan covering cards and caption removal
  from it, never from unchecked boxes.
- The ad's copy: `ads_get_creatives` (primary text, headline, call to action, thumbnail) →
  `02_research/creative_copy_v01.json`.
- Material: `tm material --run R --teardown <file> --json`, or `tm material <text_cards |
  vo_captions | talking_head | static> --run R` when your look disagrees (say why in the
  manifest). **Then `tm next`**: statics end the run here with the plain message, before any
  spend, and so do talking heads unless the target is the middle (a talking head gets the
  re-cuts only: sentence and pause cuts, a reorder, an insert; never lip-sync or new speech on
  camera).

<a id="a3b"></a>
## A3b Target audience

1. **Hypothesis first**, before reading any audience data: age, gender of the protagonist,
   problem, promise, style, language → `02_research/audience/hypothesis_from_content.md`.
2. Meta data: the ad set's `targeting` (country, age, gender, interests, Advantage+ audience),
   then the chosen ad's breakdowns age × gender and `publisher_platform` × `platform_position`
   (spend, results, cost per result, ThruPlay), for the R1 history. Save verbatim in
   `02_research/audience/`.
3. Hypothesis against data: match or divergence (a divergence is a finding). Conclusions only
   from groups with at least 10 results. In outputs, the hypothesis is always marked as one (R3).
4. Formats (R6): `tm formats --run R --breakdown 02_research/audience/<placements file> --json`.
5. `02_research/audience/audience_profile.md`: the working persona and the inputs to A5 (topics,
   phrases), A7 (hook tone) and D1 (protagonist, setting).
- "Accept the persona" (G1b): hypothesis next to data, the age × gender grid with cost per
  result, placements, divergences. Choice `accept` (note: the segment). Hands-off: the segment
  with the lowest cost per result at ≥ 10 results.

<a id="a4"></a>
## A4 Category benchmark

- `ads_library_search` in the market (and supporting markets), category phrases; keyword search
  is loose, so filter for relevance. `ad_delivery_start_time` tells how long each has run.
  Results → `02_research/ad_library_summary_v01.md` (competitors, run time, preview links).
  The API gives mostly texts (lesson 4): say so where structure matters.

<a id="a5"></a>
## A5 Trends (TrendsMesh)

- **First, what the run rests on.** TrendsMesh answers with trend data (the Agent plan, signed
  in): `tm evidence trendsmesh --run R --why "Agent plan"`, and do the pulls below. It does not
  (no Agent plan, not signed in, or the user said no at readiness): `tm evidence guess --run R
  --why "<reason>"`, and go to **Without TrendsMesh** below. If TrendsMesh was ready at readiness
  and a pull now refuses (`not_in_plan`: the plan lapsed; or a sign-in that expired), say so and
  wait: record `guess` only after the user says yes to going on without it. `tm done
  A5` is refused until one is recorded, and a TrendsMesh run needs its trends saved
  (`02_research/trend_<id>.json`).
- Tools: `trendsmesh-mcp.md`. Check `get_usage` before pulling many pages.
- `search_trends` with the product's phrases and the persona's interests (hook and topic
  trends); `list_trends` with `sort` rising and updated (take candidates from these rankings,
  not from a list you invent); `get_trend` for each candidate; `get_trend_videos` for the
  evidence, **every page** for the hook trends you may use (50 per page).
- Hook structure across all examples (lesson 10): sub-patterns, `slot_fill`, `hook_text`,
  `hook_source` (speech or on screen), `appears_at_s`, caption position →
  `02_research/hook_<name>_analysis_v01.md`. Rank by creators and view lift, not views alone;
  EN TikTok trends in another market are a hypothesis (lesson 5). Library results move ranks.
- Save every answer: `02_research/trend_<id>.json`, `videos_<id>_pNN.json`.
- No matching trend: fall back to evergreen hook structures from the Ad Library and the
  account's own winners, and say so. Those hooks are guesses in the change register.
- **Without TrendsMesh (a guess run):** the candidates are evergreen hook structures from the
  account's own past winners (the R1 ranking and the teardowns) and from the Meta Ad Library
  (the category in the market). Save what each one rests on, as you would a trend answer:
  `02_research/guess_<name>_v01.md` with the ads, links and numbers it comes from, recorded in
  the manifest. Never invent a trend, a trend id or trend numbers. Show the `notice` from
  `tm next` with the direction card.
- "Choose the direction of changes" (G2): only directions that `tm changes` lists for the target
  stage. Trend cards: status, creators, views, view lift, rising or not, 3 to 5 evidence videos
  (links); in a guess run, the winner or Ad Library ads each candidate comes from, marked as a
  guess. Hands-off: the rule `tm next` gives (the strongest confirmed and rising trend; in a
  guess run, the strongest evergreen structure from the account's own winners that is not
  saturated in the Ad Library; in a middle run, `recut`). Organic clips are evidence only,
  never footage; trending sounds are not licensed for ads.
- **A middle run** (`diagnosis.target_stage` is `middle`): A5 and A6 still run, as above. The
  trends feed CR2's cause "a faded trend in the middle" and any idea for a new shot or a proof
  insert; A6 checks those candidates the same way. There are no hook candidates. The direction
  (G2) is the re-cut: record `tm decide G2 recut --run R --note "re-cut the middle: <the weak
  step and its seconds>; trends read: <ids, or none>"` (Hands-off: the same, `--by rule`). The
  variants themselves are chosen later, at CR3.

<a id="a6"></a>
## A6 Saturation

- **Always**, at every level: every candidate is checked in the Meta Ad Library
  (`ads_library_search`, the market, the category plus the trend's phrase), whatever the
  benchmark source. Mark each "fresh" or "saturated" in a new version of
  `02_research/ad_library_summary`. A saturated candidate drops out before A7. Being in a hurry
  never skips this step: make it quick (one search per candidate), not absent.

<a id="a7"></a>
## A7 Concept and change register

Write `04_final/strategy_brief_vNN.md` from `templates/strategy_brief_template.md`:

- Hook candidates faithful to the trend's structure (lesson 10), in the market's language, text
  from the first frame (lesson 6).
- **Consistency with the image** for each (lesson 11): what the viewer sees during the hook and
  after it; one of consistent, setup and payoff, deliberate contradiction (with its reason).
  Future-tense text over a shot that already shows the result is rejected.
- The change register: change → data → expected effect, every number with its source (R3),
  only supported changes (SKILL.md section 4). Each item has a **basis**: `proof` when a saved
  TrendsMesh answer of this run backs it, `guess` otherwise (the account's winners, the Ad
  Library, your judgement). Write it as JSON too, `04_final/change_register_vNN.json`:
  `{"items": [{"change": "...", "basis": "proof", "sources": ["02_research/trend_<id>.json"]},
  {"change": "...", "basis": "guess", "sources": ["02_research/guess_<name>_v01.md"],
  "because": "..."}]}`, record it, and check it with `tm register check --run R --file <it>`. It
  refuses a proof without a saved TrendsMesh answer, and any proof in a guess run. `tm done A7`
  waits for a checked register. The strategy brief shows the basis of every change.
- R7: primary text, headline and thumbnail: a change with its data, or "no change, because…",
  as separate register items. R6: the formats from `tm formats`. Compliance with the brand rules.
- A preview of each hook on a frame of the video, when the video tier is installed: HookSwap
  props (C2) and `tm render still`. Shown on the review page (`tm review build --run R`).
- **A middle run:** no hook candidates and no hook preview. The strategy brief and the change
  register hold the diagnosed fading (the step that dropped, or the segment weak by design, with
  its seconds and the diagnosis file), the re-cut direction and its reason, and the R7 and R6
  items; each item `guess` (they rest on this ad's own data, not on a trend) with the diagnosis
  files as sources, checked with `tm register check`. The 11 causes come at CR2 and the variants at
  CR3, which adds them to a new version of the register.
- "Approve the hooks and the change register" (G3): `approve` (note: the kept hooks; in a middle
  run, "the re-cut register") or the user's corrections, redone before you record. Hands-off: the
  top 1 to 2 consistent with the image; in a middle run, the register of the diagnosed causes and
  the re-cut direction.

<a id="b1"></a>
## B1 Creative brief from the change register

- `04_final/creative_brief_vNN.md` from `templates/creative_brief_template.md`: one card per
  register item with its executor, times and positions measured in `03_wip/breakdown/` and
  `03_wip/qa/` (not by eye), the "no changes" list, references (evidence videos, marked
  "reference only"), deliverables, QA checklist.

<a id="b2"></a>
## B2 Brief acceptance

- "Approve the creative brief" (G4): the brief, shown before it goes to anyone. Choice `approve`;
  corrections are made first, as a new version. Hands-off: sent as it is.

<a id="b3"></a>
## B3 Handover to executors

- Ask who executes and by when, if the brief goes outside. Give the user the file and the assets
  list. You never send messages on the user's behalf.

<a id="c1"></a>
## C1 Method selection (edited video)

- For each changed overlay, the ladder (lesson 12): clean footage (asked in A2) → caption removal
  (inpainting) → a covering text card (static, the old overlay's whole life cycle plus a margin
  of a few frames and pixels; edge to edge, `fullBleed`, when the overlay comes within about
  24 px of the frame edge) → reframing. Use `overlays_checked`, not the raw teardown.
- Change only the captions that change. Opening text card and ending card: HookSwap (C2).
- A new first voiceover line (vo_captions material): `tm flow V --run R`, then `tm next`: the
  voice steps come before C2.
- A re-cut run (flow R on): the re-cut steps CR1 to CR7 come next; their methods are chosen at
  CR3 (`recut.md`). In a middle run there is no new opening or ending card: note here only the
  clean sources and the original music file the user has (A2), which CR4 and CR5 use.

<a id="cr1"></a>
## CR1 Segment map (re-cut)

Path C-R (`FLOWS.md`), for a fading middle or a segment weak by design. Read `recut.md` first.

- `tm tool segment_map --run R 01_base/<ad_id>_original.<ext> --teardown
  02_research/teardown_vNN.json [--transcript 02_research/transcript_vNN.json] --json` (free) →
  `03_wip/retention/segment_map_vNN.json`: each retention step mapped to seconds of the file, with
  its peak and latest rates, the cards on screen (indices into the teardown's overlays: read their
  text from `overlays_checked`), the visual change (mean frame difference 0.5 s apart), the
  loudness and the words spoken; `last_new_info_s` (the last new card or word) and `weakest` (the
  step that dropped, else the structural step, else the lowest).
- Look at the weak segment yourself: the teardown's frame sheets, or a strip of it
  (`tm tool ffmpeg --run R --name weak_segment_strip --ext png --parent 01_base/<original> -- -ss
  <from> -to <to> -i 01_base/<original> -vf fps=1,scale=240:-2,tile=6x1 -frames:v 1`). Note what
  happens on screen, in the sound and in the speech.
- Write sections 1 to 3 of `04_final/middle_diagnosis_v01.md` from
  `templates/middle_diagnosis_template.md` and record it. The steps over the frames, the weakest
  highlighted, is what the user sees at the variants check-in.

<a id="cr2"></a>
## CR2 Causes (re-cut)

- Check the 11 causes against the map, each with a verdict (yes, no, hypothesis) and its evidence
  with the source (R3); write section 4 of the middle diagnosis as a new version:
  1. the hook promises, the middle does not deliver: when the promise arrives against the weak step;
  2. pacing, dead air: the visual change falling, long speech gaps (`tm recut points`);
  3. the ad longer than its content: `last_new_info_s` against the length, and what follows it;
  4. fatigue of the middle: the ladder's peak against latest (a step that dropped);
  5. no proof: the product or proof never shown (from the frames; usually a hypothesis);
  6. visual monotony: near-identical frames, a low visual change;
  7. sound: a loudness drop or drop-out in the weak step;
  8. placement: the same weak step in every placement (a hypothesis without the placement data);
  9. audience shift: the uploads (R2b) and the audience data (A3b) change the level, not the shape;
  10. a faded trend in the middle: only when the middle carries a trend element;
  11. a "this is an ad" moment: a call to action or price reveal inside the weak step.

<a id="cr3"></a>
## CR3 Variants and level (re-cut)

- The candidates are what `tm changes --stage middle --material <material> --json` lists (their
  ids are the edit lists' `change_id`), built as `recut.md` section 3 says. One change per
  variant, each aimed at a cause marked "yes", at the **lowest level that removes it** (0 pure
  edit, 1 graphics layer, 2 own assets, 3 repair AI, 4 generative AI, 5 audio). Say what is not
  offered and why (a reorder in an ad of one or two continuous shots, lip-sync, a speed-up of a
  talking head).
- Price the paid ones with `tm budget estimate ai_usd <USD> --what "<variant: ProPainter, Veo>"
  --json` or `tm budget estimate voice_credits <credits> --what "<variant: music take, new line>"
  --json`. A shorter version of a music-only ad needs music for its new length: `tm recut music
  --run R --target-s <length> --json` says whether a saved take fits (free) before you price a new
  one.
- Write section 5 of the middle diagnosis and a new version of the strategy brief with the
  variants, and a new version of the creative brief (B1's file) with the chosen variants when the
  creative brief is an output. Add each to a new version of the change register, basis `guess` (the variants rest on
  this ad's retention data, not on a trend) with the middle diagnosis and the segment map as
  sources, and check it with `tm register check --run R --file <it>`.
- "Choose the re-cut variants" (G3r), asked on its own at Check every step and Just the big calls:
  one card per variant with the change, the cause it removes, the level and the cost; the weak
  segment's frames on the review page. Record `tm decide G3r approve --note "<the variants kept,
  each with its change id and level>"`. Hands-off: the variants for the causes marked "yes", L0 to
  L2 first (by rule; L3 to L5 only within `recut.max_level`), and never a `recut_new_vo_line`
  variant: flow V's voice match (V1c) needs a person, so that variant waits, flow V stays off, and
  the final report lists it.
- A chosen `recut_new_vo_line` variant (Check every step, Just the big calls): `tm flow V --run R`
  now; flow V's steps come after CR4.

<a id="cr4"></a>
## CR4 Edit lists (re-cut)

- `tm recut points --run R --teardown 02_research/teardown_vNN.json [--transcript
  02_research/transcript_vNN.json] --json`: the shot changes (frame and seconds at the source's
  fps), the card switches and the speech gaps. Take every cut point from it.
- One edit list per variant, `03_wip/recut/<variant>_v01.json` (`recut.md` section 5: header,
  segments, sound; `src` relative to `03_wip/recut/`), recorded with `tm record`. Cut points:
  the picture at shot changes or caption switches, ending at least 2 frames before a shot change;
  speech audio in the speech gaps, never mid-word; never inside one continuous shot (regenerate
  it, L4). Speech (talking head, voiceover): `"audio_mode": "sync"`; captions that switch before or
  after the speech: cut the picture at the switch and let the audio run on (`audio_tail` L-cut,
  `audio_head` J-cut). Music: the chain in `recut.md` section 6, never a beat-cut edit as final.
- **Before you render anything, and whatever the frames look like:** `tm recut check --run R
  03_wip/recut/<variant>_v01.json --teardown <the teardown of the file being cut> [--transcript
  <its transcript>] --json`. Exit 0 (`ok`): legal, with its length and joints. Exit 2: `status`
  `refused` (fix it in a new version, `_v02`, and check again) or `waiting` (an L3 to L5 variant
  without its budget yet, or above `recut.max_level` in Hands-off: leave it waiting and go on with
  the others; it is checked again before it renders). In Hands-off a waiting variant stays waiting
  to the end and is listed in the final report.
- An edit list that needs a file CR5 makes (a cleaned plate, a Veo clip, a music take, a new
  line) gets that file in a new version once it exists (the tool names it), and is checked again.

<a id="v0"></a>
## V0 Audio breakdown (flow V)

- From the teardown and transcript: number of speakers, pace (words per second), VO loudness,
  whether the speaker is on screen (`speech_on_camera`: a new line spoken on camera needs
  lip-sync, which isn't supported yet; stop and say so). The slot the new line must fit: for a
  re-cut's bridging line, the gap the edit list leaves between the kept sentences.

<a id="v1"></a>
## V1 Find the original voice (isolation and match)

The voice budget check-in (VB) comes first (spending card): `approve`, then `tm budget approve
--run R voice_credits <total>` (the kind's running total: what is approved already, e.g. by the
re-cut budget, plus this amount; SKILL.md section 5); or `reject`, which skips the new line and the rest of the edited
video (nothing is spent on them). Then, `variants.md` section 4, V1:
- (a) `tm tool elevenlabs history-search --run R "<the original line>" --json` (free): a match is
  the original voice, settings included.
- (b) ask the user for a voice id or ElevenLabs project.
- (c) isolate the voice from the ad: cut the audio with `tm tool ffmpeg`, then `tm tool
  elevenlabs isolate --run R <audio> --cost <credits>` (always Voice Isolator, never Demucs).
  Candidate voices must come from the user (voice ids): this version cannot list the account's
  or the library's voices. Compare with `tm tool speaker_sim --run R <isolated> <candidates...>`
  (rules of use in `variants.md`: equal quality, 100 Hz to 4 kHz).
- "Confirm the voice match after listening" (V1c): `voice_matches` (note: the voice id),
  `none_matches` or `original_voice_found`. A person listens: Hands-off stops here.

<a id="v3"></a>
## V3 Clone the voice and check the clone

- Skipped when V1c found the original voice.
- **The cloning plan first**, before any material is made, when the readiness card left it unknown (its
  warning `elevenlabs_cloning_plan`; this is the only place it is checked): `tm tool elevenlabs credits --run R
  --json` (free). `instant_cloning` true: go on. False: stop and wait; the plan has no voice cloning (the stop
  below). Null (ElevenLabs did not say): ask the user whether their plan includes voice cloning (elevenlabs.io,
  Profile, Subscription); a no is the same stop. Nothing is spent before the answer.
- **No cloning on the plan** (the card's `no_cloning` warning, or the check above): the ad needs a clone here,
  so stop and wait, and let the user choose: upgrade to a plan with voice cloning (elevenlabs.io, Subscription;
  then read the plan again), a stock voice for the new line (a voice id they give; V4 with it), or no voice
  change (the new line is left out and the other changes go on). Nothing is spent before the answer.
- Material: this ad plus other ads with the same
  voice (≥ 0.65 similarity after equal quality), isolated, cut into clean sentences at the
  transcript's word times (`tm tool ffmpeg`), best voice-to-music ratio first.
- `tm tool elevenlabs clone-ivc --run R --name <name> <files...> --cost <credits> --json`.
  `requires_verification` means a protected library voice: search the library, do not work
  around it.
- QA: the original line from the clone (`tts`), similarity to the original not below the
  original fragments' own median.
- "Blind listening test of the voice clone" (GV): two files with neutral names, the user does not
  know which is which. Choices `pass` (could not tell) or `fail`. Hands-off stops here. A failed
  clone is never patched into one line: more material first, else a whole new consistent VO.

<a id="v4"></a>
## V4 Generate the new line (R9)

- `tm tool elevenlabs tts --run R --voice-id <id> --text "<line>" [--speed 0.7-1.2] --cost
  <credits> --json`, several takes (PCM 44.1 kHz). Fit the slot by **regenerating** (shorter
  text, speed) before any time stretching (R9). With a clone, `similarity_boost` ≤ 0.75
  (`--settings <a JSON file in 03_wip>`).
- Pick in two steps: the quality gate (noise between words ≤ −55 dB, brightness ≥ −10 dB, the
  length fits), then the highest similarity among those that pass.

<a id="v5"></a>
## V5 Paste in the new line and QA

- Cut in the pause between words (transcript times), match loudness (LUFS) and timbre to the
  neighbouring sentences in both directions, with `tm tool ffmpeg`. The music under the line
  needs a separate music track: ask for the project's stems in A2; without them, say what the
  mix can and cannot do before going on.
- QA: `tm tool vo_qa --run R <processed> <unprocessed> --json` (R9, within ±10%),
  `speaker_sim`, a transcript of the new line equal to the intended text (`tm tool transcribe`),
  no loudness jump at the splice. At every level but Hands-off an A/B sample goes to the user.

<a id="vc"></a>
## VC Remove and recreate the captions

- `variants.md` section 4a. A clean source first. Otherwise the free plate always comes first:
  `tm tool inpaint --run R <video> --teardown <teardown.json> [--from S --to S] --json` (free, no
  approval: OpenCV Telea on the old captions, from the teardown's overlay boxes and the times their
  words are on screen, held and averaged over neighbouring frames so the patch does not flicker; a
  caption the teardown missed goes in with `--box X0 Y0 X1 Y1`). It writes the plate and its mask.
  Render the new captions over the plate, then decide the mode:
  `tm tool inpaint_mode --run R <mask> <composite> --crop <the plate's crop> --json` (a mode set in
  the config wins). With no AI budget approved it answers `budget` with `pro_wanted` when ProPainter
  would do better: then ask, as below. Pro is ProPainter through `tm tool replicate_run` (paid:
  estimate, approval, `--cost`). No check-in asks for that money at VC, so ask it here, the same
  way whether or not the AI video is in the run: show the estimate with a sample frame next to the free way and its
  known defect (`variants.md` 4a: a patch on texture such as sand or water), and record the user's
  yes for this amount alone: `tm budget approve --run R ai_usd <total> --for VC --note "<their
  words>"` (`<total>`: the `ai_usd` already approved plus this amount). It approves nothing for
  the AI video: its plan and budget (G6) come later and approve the running total, this spend
  included. Hands-off: the intake's AI budget; without one, take the free way and list its defect
  in the final report. Budget is the free plate from `tm tool inpaint`.
- New captions in the original's style: WordCaptions props (word times from the transcript,
  style matched with comparison stills), `tm render still|video --comp WordCaptions`. QA as in
  section 4a.

<a id="cr5a"></a>
## CR5a Repairs and new shots: ProPainter, Veo (re-cut)

- The re-cut budget check-in (RB) comes first, at Just the big calls inside the spending card:
  each paid variant with what it buys and its estimate (ProPainter cents; Veo 3.1 Fast first +
  last frame $0.80 per 8 s; ElevenLabs Music about 220 credits per take, plus a one-off upload of
  about 366 credits per track), the total per kind. Run `tm r4` first (and write the AI video's
  D1 plan when the AI video is an output), so the spending card shows real amounts for every
  member. `approve`, then `tm budget approve --run R ai_usd <total>` and `tm budget approve --run R
  voice_credits <total>` for what it covers, each `<total>` the kind's running total: `tm status
  --run R --json` → `budgets[kind]` (already approved, e.g. by the voice budget or the AI video
  plan) plus the re-cut's amount;
  `reject` skips CR5a and CR5b: the L3 to L5 variants are not made, the L0 to L2 ones still are.
  When no chosen variant is paid, say the re-cut costs nothing and record `approve` with the note
  "no paid step" (no amount to approve). Hands-off, by rule, in this order: (1) no chosen variant
  is paid: `approve`, note "no paid step"; (2) the intake set either budget kind a chosen variant
  needs: `approve`, and `tm recut check` keeps the rest waiting; (3) otherwise `reject`. It never
  stops the run. While RB's latest answer is `reject`, `tm recut check` counts no budget as
  approved for a re-cut, even one approved for the AI video or a voice line: its paid variants
  wait.
- At Check every step, when a `recut_new_vo_line` variant was chosen: the voice budget (VB, before
  V1) pays for the new line, and an RB `reject` later skips CR5b, where the line goes into the edit
  list, leaving a line already paid for unused. RB is best decided right after VB, but the engine
  records it only when `tm next` reaches it ("not reached yet" before that): so at VB, tell the
  user the re-cut budget comes next and ask both together, then record RB with that answer when
  it is asked.
- The paid repairs and shots of the chosen L3 and L4 variants (`recut.md` section 7), each through
  `tm tool replicate_run --run R <spec> --name <name> --cost <USD> --json` after the estimate and
  the approval (Replicate's prices confirmed by the user first, lesson 7): ProPainter for the image
  under a removed card, Veo for a new or regenerated shot. Look at every output's frames before
  you use it. A run that stopped part way: `--resume 03_wip/<name>_vNN.run.json`, free. A variant
  still waiting for its budget is skipped here and stays waiting.
- Rebuilt cards (L1) and inserts (L2) are free and are made over the render in CR6, so they are
  made even when the budget is declined.

<a id="cr5b"></a>
## CR5b Music and new lines: ElevenLabs (re-cut)

- For every variant whose music changes length, first `tm recut music --run R --target-s <the
  picture length tm recut check gave> --json`: `reuse` a saved take (0 credits), `resume` a paid
  take whose file was not saved (`tm tool elevenlabs music-compose --run R --resume <record>
  --json`, free), or `generate` one by method E (`recut.md` section 6: `music-upload` once per
  track, then `music-compose --plan <file> --cost 220`). Never a beat-cut edit of the track as the
  final music; a voiceover ad's music is never extracted from under the voice.
- A new voiceover line was made in flow V (V1 to VC, before this step); here it goes into the edit
  list as `extra_audio` at its time.
- Each edit list that now has its take, plate, clip or line: a new version, and `tm recut check`
  again until it says `ok`.

<a id="cr6"></a>
## CR6 Render and QA (re-cut)

- `tm tool recut --run R 03_wip/recut/<variant>_vNN.json --teardown <the teardown of the file being
  cut> [--transcript <its transcript>] --json` (free). It runs the same check first and renders
  only an `ok` edit list (exit 2 with `refused` or `waiting` otherwise, nothing written) →
  `04_final/<variant>_vNN.mp4` (the variant's name, any character but letters, digits and hyphens
  made a hyphen; take the path from the tool's answer) and its sidecar `<same>.mp4.recut.json`
  (the joints, the length).
- Cards (L1) and inserts (L2) over it: HookSwap props with `base` = that render (`recut.md`
  section 7), `tm render still` at the key frames next to the burned card, then `tm render video
  --run R --comp HookSwap --props <props> --json`; rebuilt captions with WordCaptions over that.
- QA on the final render: `tm tool recut_qa --run R <render> [--sidecar
  04_final/<variant>_vNN.mp4.recut.json] [--caption-band x0,y0,x1,y1] [--expected "<the kept
  script>"] [--lang <code>] [--original 01_base/<original>] --json` → `03_wip/qa/<name>_qa_vNN.json`
  and joint strips (frames −3 to +3 around each joint) in `03_wip/qa/<name>_strips_vNN/`. It checks
  the length, a one-frame flash at a joint, music joints (a jump above 3 dB, a beat interval off by
  more than 15 %), tempo drift above 4 %, a fade before the end (last 3 s more than 6 dB below the
  body), a word across an audio fade point, the transcript against `--expected`, a caption shown
  less than 0.2 s next to a joint (with `--caption-band`), and the loudness against the original.
  Look at every joint strip yourself. Give `--sidecar` when the render is a HookSwap or WordCaptions
  render made over the re-cut; `--caption-band` and `--expected` whenever the ad has captions or
  speech.
- `pass` false: back to CR4, a new version of the edit list that removes the cause (a one-frame
  flash: end the segment at least 2 frames earlier), then render and QA again. Never patch a
  render. In a voiceover ad, a tempo or tail flag from the speech ending is a known limit
  (`recut.md` section 8): say so, don't chase it.
- The master and the phone preview as in C3 when the final is a HookSwap render; record each with
  `--before-after "before: 01_base/<original>"`.

<a id="cr7"></a>
## CR7 Acceptance (re-cut)

- Review copies at 540 px with a timecode and the variant's name, one per variant: `tm tool ffmpeg
  --run R --out showcase/review_tc/<variant>_v01.mp4 --parent <the final> -- -i <the final> -vf
  "scale=540:-2,drawtext=text='<variant> %{pts\:hms}':x=16:y=16:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6"
  -c:a copy`. Open one frame to check the timecode shows.
- "Approve each re-cut variant (listen to it)" (G5r): before and after, timecoded; for each
  variant one question, what to judge and at which second (the joints with their seconds, the
  music at its end). Music is accepted by ear: the measurements don't catch every audible skip.
  Record `tm decide G5r approve --note "<each variant: kept or dropped, and why>"`. A variant the
  user doesn't accept goes back to CR4 with their words (a new version), or is dropped from the
  test. Just the big calls asks it too; Hands-off decides by rule (QA green), and the final report
  says no one has listened to it yet.
- The live test (E1) takes the re-cut's test options of R4 (`flow.md#e1`).

<a id="c2"></a>
## C2 Props and control frames

- HookSwap props in `03_wip/edit_<variant>_v01.props.json` (record it): `base` (the original in
  `01_base`), `width`, `height`, `durationSec`, `cards` (`from`, `to`, `top`, `height`,
  `fullBleed`, `fontSize`, `typeCharsPerSec` ≥ 1000 for no typewriter, `lines` with `at` and
  `text`), `inserts` (`src`, `from`, `to`, `trimStart`). Paths are relative to the run folder.
  An ending card is a card in the last seconds. Example:
  `handoff`'s Ad 3 v05: one `fullBleed` card from 0 to 6.45 s at top 190, height 113.
- `tm render still --run R --comp HookSwap --props <props> --frame <N> --json` at the key frames:
  the first frame, the old overlay's first and last frames (± a few), the first frame after the
  card leaves. Look at every still.

<a id="c3"></a>
## C3 Full render and QA

- `tm render video --run R --comp HookSwap --props <props> --json` → `03_wip/..._vNN.mp4`.
- QA (🔍): text from the first frame; the card covers the old overlay's outline in every frame
  (geometry, not colour); enlarged strips of the card's left and right edges for the first and
  last frames of the overlay cycle (`tm tool ffmpeg` crop and tile → `03_wip/qa/*_edges_vNN.png`);
  a clean frame after the card leaves; audio and length unchanged (teardown of the render).
- The final: `tm tool ffmpeg` to `04_final/<name>_edited_vNN.mp4` (H.264, CRF 19, at most
  14 Mb/s) and a phone preview under 30 MB; record each with
  `--before-after "before: 01_base/<original>"` (`tm record` for files you name yourself).
- `tm review build --run R`: give the user the path of `review/index.html` (before and after side
  by side, frame grids, QA strips).

<a id="c4"></a>
## C4 Render acceptance

- "Approve the edited video" (G5): the review page and the QA strips. Choice `approve`; a redo is
  a new version first. Just the big calls and Hands-off: by rule when the QA is green (say so at
  the next check-in).

<a id="d1"></a>
## D1 Visual decision and shot plan (AI video)

- From A5 to A7 (a new setting or a topic swap, `variants.md` 4b is the model): target length
  (the original's), model limits (Veo 3.1 Fast: 4, 6 or 8 s clips), the chain (lesson 13), what
  happens in each clip (mirroring the original's structure), text cards on a clean image, the
  prompts, models (`openai/gpt-image-2` medium for the first frame, `google/veo-3.1-fast` for
  clips), parameters, attempts allowed, and the cost of each call and in total
  (`tm budget estimate ai_usd ...`). → `03_wip/ai/ai_video_plan_v01.md`.
- Ask the user to confirm Replicate's current prices before the first run (lesson 7).
- "Approve the AI video plan and budget" (G6), in the spending card at Just the big calls:
  `approve`, then `tm budget approve --run R ai_usd <total>` (the kind's running total: the
  `ai_usd` already approved, e.g. by the re-cut budget or the caption removal at VC, plus this
  plan's amount; show what is already spent on the card; SKILL.md section 5); or `reject`, which
  skips the AI video (nothing is spent on it).

<a id="d2"></a>
## D2 First frame

- A spec `03_wip/ai/frame1_v01.json`: `{"model": "openai/gpt-image-2", "input": {...}}` with the
  original frame (clean of captions) as the character and composition reference. Record it.
- `tm tool replicate_run --run R 03_wip/ai/frame1_v01.json --name frame1 --cost <USD> --json`.
  A run that stopped part way is finished, free, with `--resume 03_wip/<name>_vNN.run.json`.
- "Choose the first frame" (G7): the variants next to the original frame on the review page.
  Choice: the file. By rule: character consistency, the first one on a tie.

<a id="d3"></a>
## D3 Clips

- Clip k starts from the **exact last frame** of clip k−1:
  `tm tool ffmpeg --run R --name clip<k-1>_last_frame --ext png --parent <clip> -- -sseof -0.1 -i
  <clip> -frames:v 1 -update 1`. Use `last_frame` only when the end frame is close (same scene,
  light, elements); change the setting with a camera move in the prompt (lesson 13).
- Each clip: `tm tool replicate_run ... --cost <USD>`. Join QA: frame strips of the last 4 frames
  of k−1 and the first 4 of k (`tm tool ffmpeg`, tile), and a look for jumps and appearing
  objects; this version has no numeric join check, so say that the check is by eye.
- "Accept the clip or regenerate it" (G8): `accept` or regenerate with a note (each attempt
  costs). By rule: QA green, at most 2 attempts within the budget.

<a id="d4"></a>
## D4 Assembly

- HookSwap with `base` = the original (its music) and the clips as `inserts` (`trimStart` drops a
  repeated first frame), the text cards on top; `tm render video`. Then the master and the preview
  with `tm tool ffmpeg` (as C3). Length matches the original.

<a id="d5"></a>
## D5 AI video acceptance

- "Approve the AI video" (G9): before and after on the review page, the known defects with their
  time and a fix proposal (with or without cost). By rule: QA green, defects in the report.

<a id="e1"></a>
## E1 Test design (R4)

- Write the chosen ad's latest window to `03_wip/test_control_v01.json` (record it; source: the
  ranking file), then `tm r4 --run R --stage <target_stage> --control <that file> --variants <n>
  [--per-day <budget>] [--max-days <days>] --json`: the decision metric, the cost
  guardrail, the thresholds, the minimum events per variant and the days and budget they need.
  The decision metric sets the budget: for a rate (hook rate, ThruPlay rate, CTR, a re-cut step)
  the trials it needs at the control's cost per impression or play, and at least `test.min_days`
  days; cost per result is only the guardrail, checked once a variant has
  `test.guardrail_min_results` results. The plan says what the budget is based on (`basis`).
  The days allowed are the user's (`budget.test_days`, at most `test.max_days`).
  At Just the big calls run it before the spending card, which shows it. `tm done E1`, G10's
  `approve` and the launch are refused without a feasible plan.
- **A re-cut variant** is tested as `--stage middle` with one of two options (FLOWS.md CR8). A
  shorter version mechanically raises completions and ThruPlay, so: `--shorter` (judged by cost
  per result, with the average watch time beside it). A same-length version: `--recut-step
  <p50/p25 | p75/p50 | p95/p75>`, the step of the window it changed (judged by that step, cost per
  result the guardrail). A variant is one or the other: one plan has one decision metric, so when
  the chosen variants are of both kinds, or a hook variant runs beside a re-cut, ask the user which
  goes into this test (Hands-off: a middle run tests the kind of its first kept variant, a run with
  another target tests that target; the variants left out are listed in the final report as not
  tested). Meta's average watch time is whole seconds per day: show it as "about 6 s", never as a
  precise figure.
- Exit 2: the plan cannot reach the minimum events, and the engine stops the run. Give the user
  the calculation (events, budget, time) and the choices: a higher daily budget (`--per-day`),
  more days (`--max-days`), fewer variants (then `tm r4` again; a feasible plan clears the stop),
  or skip the live test (`tm decide G10 reject`). In Hands-off a higher amount is also approved
  while the stop is open: `tm budget approve --run R test <per day × days>` first, then `tm r4`.
- **Formats per ad (R6).** The plan names the files and placements per ad: for the control and
  each variant, the file in Reels and Stories (9:16) and the file in feed (4:5), so that the ads
  differ only in the change under test and feed gets the format R6 asks for. When `tm formats`
  asks for 4:5 and the original has no 4:5 version (its creative has one video and no placement
  asset customization: A3's `ads_get_creatives`), make a 4:5 version of the original too, as for
  the variant: `tm tool reframe --run R <the original's video> --teardown <its teardown from A3>`,
  then the same QA (its frames against the teardown's frame sheets: no text, face, product or
  logo cut, the safe zones kept; the result's `method`, crop or pad). It is free and local, so
  it needs no check-in of its own: make it at E1 at the latest. Both ads then carry 9:16 and 4:5
  on the same placements (placement asset customization), and the control is a new creative
  made of the original's files (its video, its 4:5 version, its copy, headline, call to action
  and thumbnail), PAUSED like the rest. Only when the original's 4:5 version fails its QA and no
  free fix helps, the plan says "test in 9:16 only; 4:5 after the test" and why, and the card
  says so.
- **AI disclosure (Meta's `self_ai_disclosure`).** Meta sets it only when a creative is created
  and leaves it to the advertiser: never decide or infer it for the user. Before the card, run
  `tm ai-media --run R --file <each file the plan's ads use> --json`. For each file it lists the
  media this run created or edited with generative AI (a cloned or synthetic voice line,
  generated music, inpainted frames, an AI shot, the AI video), from the run's own records, and
  the files it can't trace, the original's always among them. A file not made yet (at Just the
  big calls the spending card can come before the renders): list what the approved changes and
  generation plans will make. The plan and the G10 card show those facts and ask one question,
  "Do these ads contain media created or edited with generative AI?", with three choices:
  **both** (`OPT_IN` on the control and every variant), **neither** (`OPT_OUT` on all) or **only
  the variant** (`OPT_IN` on the variants only; say that the "AI info" label is then a second
  difference between control and variant, next to the change under test). It covers the
  original too: the user knows whether it already holds AI media, the run's records can't tell
  (unless the user said so earlier in this run). This question carries no recommendation. Write
  the answer in the plan and in G10's note (`--note "... AI disclosure: <answer>"`).
- **Hands-off:** G10 goes by rule, the AI disclosure never does. Unless the user already
  answered it in this run, record a stop after G10, before E2 creates anything: `tm stop --run R
  --reason ai_disclosure --what "<the facts>" --todo "<the one question>"`. On the answer, write
  the plan as a new version with it (record it), then `tm resume --run R`.
- **Offered at the end.** When the run made a video without the live test, the final report ends
  with one question (`tm next` says so with `done`): "Do you want to test this against the
  original?" On a yes, ask for the daily budget and the days, then `tm live-test add --run R
  --per-day <amount> --days <days>` (Hands-off: with `--note "<their words>"`; the landing page
  with `--landing-url` if the config lacks it): the run reopens here, at E1.
- `ads_experiment_check_eligibility`. Write `04_final/live_test_plan_vNN.md`
  (`templates/live_test_plan_template.md`): a Meta A/B test with the original as control, the
  numbers from `tm r4`, no decisions before the end of the window (except the cost guardrail), and
  the objects it creates, all PAUSED.
- "Approve the live test plan" (G10), in the spending card: `approve`, then
  `tm budget approve --run R test <per day × days>`; or `reject`, which skips the live test.

<a id="e2"></a>
## E2 Media upload and paused ads

- **Build exactly the approved plan:** its files per ad and placement, copy, headline,
  thumbnail and AI disclosure. Before creating anything, run `tm ai-media` again on the final
  files. If anything has to differ from the approved plan (a file, a format, a placement, the
  thumbnail, or AI media the plan didn't list), stop and ask, with the change and the reason,
  before creating the objects: `tm stop --run R --reason plan_changed --what "<the change and
  why>" --todo "<approve it or say what to do>"`, at every level. On the user's yes, write the
  plan as a new version with the change (record it), then `tm resume --run R`. Never build
  something else and report it afterwards.
- **Upload in one round** (SKILL.md section 7): prepare every file first, each video in each
  format and the thumbnail when the plan changes or shares it (R7), then `ads_creative_upload_media`
  with the local files, all of them in one call when the tool takes several. In the Claude
  desktop app the tool opens an upload window in the chat: that is an upload the user finishes,
  not a failure. Send them the files first with the file-sending tool (SendUserFile), name them,
  say to pick all of them in the window at once; the ids come back in the chat. When no upload
  tool works at all, the stop in SKILL.md section 7.
- Then the ad set and the ads, **PAUSED**, as in the plan: an ad with 9:16 and 4:5 gets both
  through placement asset customization, the control the same way as the variants. Pass
  `self_ai_disclosure` on every creative (`OPT_IN` or `OPT_OUT`, from the plan's answer): it
  can't be set later (no update tool sets it), so a creative created without it is created
  again. Previews with `ads_get_ad_preview`. Save every answer and the object ids in
  `05_results/meta_objects_v01.json`.

<a id="e2b"></a>
## E2b Quality and policy check (R8)

- Every variant through the checklist in `04_final/prelaunch_check_vNN.md`
  (`templates/prelaunch_check_template.md`): the AI disclosure, claims, music and voice licence,
  text in the feed preview, known defects, quality against the original, and the formats and
  placements of the ads built against the approved plan's. Each item green or red, with its
  evidence.
- The AI disclosure is checked here; E2b never asks it (the question was asked before E2, `#e1`).
  Read `self_ai_disclosure` on each creative (`05_results/meta_objects_v01.json`, or
  `ads_get_creatives`) against the plan's answer and `tm ai-media` on the final files. Red when a
  creative differs from the answer, or was created without it while the run used generative AI;
  the fix is a new creative and ad with the plan's answer, PAUSED (the old ones deleted or left
  paused, as the user prefers).
- Record it at every level by rule: `tm decide E2b green|red --by rule --note
  "04_final/prelaunch_check_vNN.md: ..."`. Red stops the run at every level: say which items and
  what fixes them; after the fix, check again and record `--change`.

<a id="e3"></a>
## E3 Activation

- "Approve the launch" (G11) comes first, **at every level**: Hands-off runs up to the paused ads
  and a green R8 check, then asks this one question (it is never decided by rule). The final
  videos, the R8 result, the amount per day × days. The only choices are `activate` (refused
  before a green E2b) and `keep_paused`.
  `activate` sets the measurement days 3, 5 and 7; `keep_paused` leaves everything paused and
  skips E3 and E4: nothing goes live and the run closes.
- On `activate`, **book the spend first**: `tm budget spend --run R test <per day × days> --what
  "live test" --json`. Only on exit 0: create the A/B test (`ads_experiment_abtest_create_test`)
  and activate (`ads_activate_entity`). On exit 2 nothing goes live: tell the user what the stop
  says and wait. Never above the approved budget without asking. `tm done E3` is refused until
  the spend is booked.
- Optional: offer a reminder for the measurement days (the session start also lists them).

<a id="e4"></a>
## E4 Measurement on day 3, 5 and 7

- `tm next` stops until a date is due. On each date: results per variant and control from the
  test start (`ads_get_ad_entities` and the test's own results), saved as
  `05_results/measurement_<date>_v01.json`; compare with the plan's thresholds; only the cost
  guardrail may act before the last date. Then `tm done E4 --measured <date> --run R`.
- After the last date, "Act on the results" (G12): `scale`, `kill` or `keep` (no verdict), from
  the plan's thresholds. Never raise spend above the approved budget without asking. A variant
  that wins on its rate metric with fewer results than the plan's `cost_not_confirmed`
  (`test.guardrail_min_results`) is said as the plan's verdict, e.g. "won on hook rate; cost per
  result not confirmed yet": recommend scaling step by step while watching cost per result, not
  a full scale.
- R5 closes the run: one row per variant, `tm library add --run R --row <file>`, the row with
  account, product, market, diagnosis, trend {id, type, status_on_test_day}, change {layer,
  method}, decision_metric, result_vs_control, events, decision and a distinct `variant`. In a
  guess run (no TrendsMesh data) the row has `"trend": null` and `"evidence": "guess"`, and the
  engine fills both from the run: never write a trend into it. Then
  `tm next` until `done`, and the final report.
