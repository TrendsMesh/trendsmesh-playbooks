# Hard rules CB1 to CB13 (and PB1's R3, R6 and R7)

CB1 to CB13 are copied verbatim from the reference playbook's `PLAYBOOK.md` (reference playbook `creative-brief_v02`,
section "Hard rules", approved 2026-11-04); R3, R6 and R7 verbatim from PB1's `PLAYBOOK.md`
(handoff `refresh-ad_v03`), which CB applies unchanged. They apply in every run, at every level
of involvement. The agent may not skip them. The config changes only their threshold values,
never the rule.

How to read the copy in the plugin:

- Where it says "HITL" read **Check every step** and **Just the big calls**; where it says "AUTO"
  read **Hands-off**. Its approval points (G1 to G4) are check-ins, with the plugin's G0 for the
  intake card (`checkin-cards.md`).
- Where it names the trend API, `trends_api.py` or a file holding a key, the plugin reads
  TrendsMesh through its MCP, and the collector saves every answer to the run
  (`references/trend-collection.md` at the plugin root): there is no TrendsMesh key, ever.
- The tools it names are `tm` commands: `trend_shortlist.py` is `tm trends shortlist`;
  `voice_mine.py` is `tm voice reddit-posts` and `tm voice reddit-comments` (the Reddit archive)
  and `tm voice import` (reviews and exports); `build_animatic.py` and `render.mjs` are `tm brief
  animatic --render`; `build_brief_pack.py` is `tm brief page` (`flow.md`).
- **Not built in this version**, said plainly as "not supported yet": Foreplay (CB4: `tm config
  check` refuses `benchmark.source: foreplay` with the issues link; saturation is always the Meta
  Ad Library), Goodreads reviews (CB5: its terms forbid scrapers; `references/voice.md` says
  why), the Shopify connector and Notion or Drive brand guides as connectors (an export or a file
  the user has works), organic-only use (the media-buyer view off, an organic KPI), and comment
  texts under ads (the Meta connection gives counts only).
- **Decisions on the page** (CB12): the plugin reads them with `db_list` (one unfiltered read) and
  records them with `tm brief decisions` and `tm brief choose`; a decision written in chat always
  counts (`references/pages.md`, "Pages that take decisions").

What the engine computes or checks, so you never do it by hand: the persona pick and the formats
(`tm audience pick`: CB1, R6), that the hypothesis came before the data (`tm audience
hypothesis`), the voice file against the raw items (`tm voice check`: CB5), the trend shortlist
(`tm trends shortlist`: CB2), the seed re-check (`tm brief seed-check`), the fit scores and their
weighted totals (`tm brief scores`: CB3), the saturation checks against the saved Ad Library
answers (`tm brief saturation`: CB4), brief.json against CB1 to CB13 at each stage (`tm brief
check`), the Hands-off pick (`tm brief pick`: CB6), the page (`tm brief page`: CB12, CB13), the
decisions read from it (`tm brief decisions`), the animatics (`tm brief animatic --render`: CB11),
the clips' thumbnails and as-of dates (`tm brief evidence`: CB8) and the hand-off (`tm brief
handoff`). Yours to keep: the product pick list and the card, the brand draft, the hypothesis,
the theme coding and the language bank, the search phrases, the scores, the Ad Library reading,
the concepts and every sentence of the brief, with its source (R3).

## The words fixed by the spec (use them verbatim, on the page and in messages)

- "Rising hook", "Rising topic", "Rising format", "Rising sound": the first glance row names the
  trend's kind. A `hook_trend` is a hook, never a format (CB6).
- "competitor found" and "none found in Ad Library titles" (CB4): never "this hook is unused" or
  "not in ads". The Ad Library returns titles only.
- Never "no category trend" (CB2): show the trends that fit best.
- "organic only" (CB9): a sound not licensed for ads.
- "directional" (CB1): a persona from thin data, in every output.
- "to set": an optional intake value nobody gave (budget, deadline, approver, rights, fee); never
  invented.
- "Hook (agent's guess)": the first glance row in a run without TrendsMesh data, with no "Rising"
  anywhere.

## The numbers (copied from PLAYBOOK.md "Config" and the rules; the config's defaults)

- CB1: `persona.min_results_per_segment` 10; below it the thin-data fallback, marked
  **directional**.
- CB2: `trends.min_relevant` 5 (below it, expand through related topics); `trends.kinds` hook,
  topic, format, sound.
- CB3: seven criteria scored 1–5 (brand fit, persona fit, credible bridge, lifecycle stage,
  transferability, sensitivity, production feasibility); `scoring.weights` equal.
- CB5: a language bank of 20–40 phrases; `voice.min_phrases_per_concept` 1; tiers own customers,
  category, brand, and tier C never counted.
- CB6: `concepts.count` 3; `concepts.min_axes_diff` 2, over angle, hook type, format, persona and
  awareness stage.
- CB8: `brief.valid_days_default` 14 (the LD dry run: prepared 2026-11-04, valid until
  2026-11-18).
- CB9: `music.require_ads_license` false.
- CB10: 2–3 hook variants (`hooks_to_test`).
- CB13: recipients decision, strategy, creator, editor, media-buyer; `brief.currency` USD with
  the rate stated (`fx_note` like "1 USD = 3.70 PLN").
- R6: `formats.placement_share_min` 0.25; animatic formats 9x16 and 4x5; rendered at 24 fps with
  stills at 0.06, 0.3, 0.55, 0.8 and 0.95 of the length.

## Rules from outside the playbook files (HANDOFF.md section 4, verbatim)

- **Run folder and manifest:** `runs/02-creative-brief/<YYYY-MM-DD>_<name>/` with `00_raw`, `01_base`, `02_research`, `03_wip`, `04_final`, `05_results`, `showcase` and `manifest.md`. Never overwrite (`_v01`, `_v02`…). Every asset has a manifest row (file, stage, source, parent, parameters, model, date, cost). **Save every MCP response to a file** (in the dry run several came back inline and had to be transcribed).
- **Keys** in `.secrets/api_keys.env` (python-dotenv); never print, log or commit them.
- **Meta:** official Meta Ads MCP. Verify field names with `ads_get_field_context` first. Ad Library returns titles only and matches loosely: filter by hand, and word saturation as "competitor found / none found in titles".
- **Target audience** from two sources, hypothesis first; a hypothesis is never stated as a finding (R3).
- **Money for recipients in USD** at a stated rate; run files keep the account currency.
- **Organic clips** are evidence, never footage; trending sounds are not licensed for paid ads unless the data says so.
- **Artifacts:** a new artifact starts private; the user shares it. To store decisions: publish the page, then `declare_capabilities` with `db` rules `[{path:"decisions",read:"view",write:"owner"},{path:"decisions/{self}",read:"view",write:"interact"}]` and `user` with `scopes:["profile"]`, then republish. Viewers below Contributor cannot save.

**Changed for the plugin:** the collector saves every MCP answer of the run (TrendsMesh, Meta and
the page tools), so nothing is transcribed. There are no keys: TrendsMesh and Meta are signed in
through `/mcp`, and nothing reads `.secrets/api_keys.env`. `declare_capabilities` publishes the
new version itself, so there is no separate republish after it (`references/pages.md`). The
saturation words are the full ones above ("none found in Ad Library titles").

## Hard rules (CB1–CB13, approved by the user on 2026-11-04)
The agent may not skip them. The config can change only the threshold values, not the rule itself.
Rules from PB1 that apply here unchanged: **R3** (every number has a source, a hypothesis is never presented as a conclusion), **R6** (format by placement), **R7** (decision on primary text, headline, thumbnail). The PB1 lessons on hook fidelity (10) and hook-to-image consistency (11) are part of CB7.

### CB1. Account context through Meta MCP (base stack)
- Read the ads of the product: spend, results, cost per result, hook and retention metrics; mark winners and losers.
- Target audience from two sources (project rule): hypothesis from the product and the ads **before** reading data, then Meta targeting and who actually bought. A divergence is a finding.
- Formats follow the placement split (R6).
- **Thin data (G1 fallback):** when no segment reaches ≥ 10 results, the persona is the largest directional cluster, cross-checked with the same product in another market or campaign if one exists, and marked **directional** in every output. AUTO uses this fallback instead of the ≥ 10 rule.
- Read the copy of the ads already running (`ads_get_creatives`): it is the baseline for the near-duplicate check (CB6).
- If a results library exists (`library/results.jsonl`), read it: trends and angles that lost in this category rank lower.

### CB2. Trend pull
- `search_trends` from the category phrase, then persona topics and angle themes. When fewer than 5 relevant trends come back, expand through related topics.
- **Show the best-fitting trends** (user, 2026-11-04): a relevance-ranked shortlist (`trend_shortlist.py`) in **four lists**: (a) **hooks** that fit the concepts (opening structures usable for any subject: confirmed, holding or rising, many creators, good view lift, recent, evidence in the market's language); (b) **topics** related to the category or the persona; (c) **formats**, how a video is told (e.g. a story over clips, before and after), scored like hooks and used only if the ad can be made honestly; (d) **sounds**, scored like hooks, with their licence (CB9). Search noise (news, sport, holidays) is dropped. Outputs never say "no category trend"; they show the trends that fit best.
- **TrendsMesh is adding formats and the sound licence** (user, 2026-11-04): formats arrive as a trend type like hooks and topics; sounds get a marker for commercial use (ads) or organic use only. The SKILL is built for both now: any concept may be led by a hook, a topic, a format or a sound, and the shortlist and Evidence at a glance show whichever leads ("Rising hook", "Rising topic", "Rising format", "Rising sound").
- Keep only trends that are still rising (status and momentum), not past their peak.
- **Transferability:** a trend from another language or market is a hypothesis; rank by number of creators and view lift, not by views alone (PB1 lesson 5).

### CB3. Fit scoring
**Short brand intake** (when there is no brand guide, asked once at the start): (1) what the brand stands for in one sentence; (2) tone of voice in three words; (3) topics and imagery that are off-limits; (4) claims the brand may make and the wording to use (usually from the landing page); (5) competitors to watch. The answers feed brand fit, tone and mandatories (CB13). This intake is shared by all playbooks.

Each trend is scored 1–5 on: brand fit, persona fit, credible bridge to the product, lifecycle stage, transferability to the market, sensitivity (`sensitivity_level`), production feasibility (can it be filmed by a creator or generated?). Weights are in the config. The score table is saved in the run.

### CB4. Saturation is mandatory
- Every candidate hook or angle is checked in Meta Ad Library for the market country. A heavily used hook goes lower or out.
- **Foreplay, when connected, widens the benchmark:** TikTok, YouTube and LinkedIn ads, transcripts, long-running competitor ads, boards. Absence in Foreplay never proves freshness; saturation always uses Meta Ad Library.
- **Saturation verdict without Foreplay:** the Meta Ad Library API returns ad titles only, so the verdict is worded "competitor found" (a relevant advertiser appears) or "none found in Ad Library titles". It is never worded "this hook is unused", because titles cannot show which hook a video uses.
- **Foreplay plan (planned for PB2, user, 2026-11-04):** the dry run showed that the Meta Ad Library API returns titles only, so a hook cannot be checked in paid ads. With Foreplay (MCP, transcripts and on-screen text of ads) step 4 adds, per candidate hook: how many paid ads in the category already use this hook structure, on which platforms, and how long the longest one has run (a long run = proven in paid). The result goes into the "Competition" row of Evidence at a glance ("in paid: N ads, longest running D days" or "not found in paid"). Cost: Foreplay plan from $59/month (1 ad = 1 credit). Status: no account yet; the user creates the account and connects the MCP.

### CB5. Customer voice is the source of the angle
**Intake (part of the confirmation card; the agent searches the sources itself):**
- the landing URL comes from the product's ads (asked only for a product without ads, see Inputs);
- optional: links to where customers leave reviews (store, Amazon, Trustpilot, Google, App Store), any export (reviews, support tickets, surveys, DMs), social profiles, competitor names or URLs;
- if the client has none, the agent says what it will use instead (tiers B and C) and continues; missing reviews never block the run.

**Three tiers, always labeled in the outputs:**
| Tier | What | Examples | Role |
|---|---|---|---|
| A. Own customers | what the product's buyers say | reviews, support, surveys, comments under the brand's posts and ads | strongest evidence for an angle |
| B. Category voice | what people in the category say, not about this product | Reddit and forums, comments under evidence videos and category YouTube, reviews of comparable products and of competitors | evidence for an angle when tier A is thin or missing |
| C. Brand voice | how the brand talks to customers | landing page, brand guide, existing ads | tone, claims and the brand's **hypothesis** about its customers; never counted as customer evidence |

**Processing:**
- Cluster tiers A and B into themes (aspect of the product, pain, desire, objection, outcome) with **frequency** and verbatim quotes with their source.
- A theme that recurs is an **angle candidate**: it tells us which aspect of the product to lead with.
- Tier C is set against A and B, like the audience hypothesis against Meta data: a brand claim that customers also repeat is a strong angle; a brand claim nobody repeats, or a customer theme the brand never mentions, is a finding.
- **Language bank:** 20–40 short verbatim phrases with source. **Every concept uses at least one of them** in the hook, on-screen text, a spoken line or the primary text, verbatim or minimally adapted, where it sounds natural, and the brief marks which phrase and its source (the presentation's "Topic + Phrase + clips").
- Testimonials appear in an ad only when the concept calls for it; the main job of customer voice is context for the angle.
- Comment texts under ads: the Meta MCP tools in this project return comment counts only, not texts (to verify); texts come from an export or the page.

### CB6. Distinct concepts
- **Naming:** a `hook_trend` from TrendsMesh is called a **hook** in every output ("Rising hook"), not a format; `format_trend` is a format, `topic_trend` a topic, `sound_trend` a sound (user, 2026-11-04).
- Every two concepts in the review pack differ on **at least 2 axes**: angle, hook type, format, persona, awareness stage.
- No concept may be a near-duplicate of an ad already running on the account (checked against CB1).

### CB7. Trend fidelity and hook-to-image consistency
- Before writing a hook, the agent analyzes the trend's evidence videos (slot_fill, sub-patterns, where and when text appears) and reproduces the structure as closely as possible.
- What the viewer sees during the hook is written down; the text-to-image relation is one of: consistent / setup and payoff / deliberate contradiction with a justification (PB1 lesson 11).

### CB8. Evidence that lasts
- Every evidence clip is saved in the run with link, thumbnail and "as of" date (organic videos disappear).
- Every brief has a **valid-until date** derived from the trends' `visible_until`; while the trend data leaves it empty, the default is **14 days** from the run date.
- Every number has a source (R3).

### CB9. Sound trends and organic clips
- **Target state:** only music trends licensed for paid ads are suggested for ads. TrendsMesh is adding a marker per sound: **commercial** (usable in ads) or **organic** (organic posts only). `trend_shortlist.py` already reads it (`licence`: commercial / organic / unknown); with `music.require_ads_license: true` (tool flag `--sounds-commercial-only`) only commercial sounds reach ad concepts.
- **Until the marker is in the data (or when it says organic / is missing):** the sound is shown with the flag "organic only" and is used only when the concept needs it. For paid, the brief names a licensed equivalent (Meta Sound Collection or licensed music) that keeps the same feel, or marks the concept "organic only".
- Organic clips are evidence and inspiration, never footage.

### CB10. Production-ready brief, one data source
The brief is written once as **`brief.json`** (schema: `schema/brief.schema.json`); every view, the page and the animatic are generated from it. Its content: concept, angle with the customer evidence, trend with clips and numbers, hook (2–3 variants for testing), structure by seconds, formats (R6), primary text, headline, thumbnail (R7), why it should work (data), valid-until date, `brief_id` and a one-sentence test hypothesis ("this concept tests whether angle X works"), so a later test can be linked back to the brief. PB2 itself has no measurement step.
The creator part (rendered as the creator view, the former shot list): role, casting (age, look, persona), setting and props, shot by shot (framing, action, takes), lines to say (key points + sample lines, natural, not read out), hook versions as extra takes, deliverables: **raw footage without burned-in captions, separate VO / audio track**, both formats. (Clean sources make a later PB1 refresh much easier.) The editor and media-buyer parts follow CB13.

### CB11. Animatic in every brief
- Each brief includes an **animatic**: an animated storyboard of the structure (shots, timing, on-screen text, hook, CTA), rendered from HTML to MP4 in the target formats. No API cost.
- It shows structure and pacing, not realistic footage. No AI generation at the brief stage.

### CB12. Delivery: one shareable page (user decision, 2026-11-04)
- The recipient (growth lead, creator, client) gets **one page**, not a folder of markdown files: the review pack and the briefs with the animatics playing, each concept opening with **Evidence at a glance** (trend: name, ID, status, momentum, creators, views, median view lift, active since / last seen, language; customer theme with frequency; the account number; saturation), details after.
- **Default channel: a private Artifact** (claude.ai link; works on a phone; videos and evidence thumbnails uploaded with the page). It starts private; the user shares it from claude.ai (people, organization or public). Decisions for G2/G3 are made **on the page**: per concept Approve / Ask for changes plus a note, saved to the artifact's shared database (`db` capability), visible to everyone who opens the link with their name, and read back by the agent (`db_query`). A static "leave a comment" note is not enough (user, 2026-11-04).
- **Fallback:** one self-contained HTML file (videos embedded) when the recipient has no claude.ai access.
- `brief.json` in the run is the source of truth; the page is generated from it (`build_brief_pack.py`) and republished on every change.

### CB13. One brief, a view per recipient (user decision, 2026-11-04)
- At intake the user ticks **one or more recipients**; the brief is written once (one data source) and the page shows one view per ticked recipient, each with its own link (`#decision`, `#strategy`, `#creator`, `#editor`, `#media-buyer`).

| View | Recipient | Shows | Never shows |
|---|---|---|---|
| Decision | growth lead, founder, client | idea in one sentence, key message, Evidence at a glance, what it tests + KPI, production effort, budget / deadline / approver, main risk, animatic, decision buttons | beat sheets, casting, QA |
| Strategy | creative strategist, copywriter | everything: evidence, quotes, scoring, hooks, copy, tone and mandatories | — |
| Creator | UGC creator, on-camera talent | the product in plain words, their role, what to say (key points + sample lines), shots, props, look, do / don't, deliverables and deadline, usage rights and fee | **account data, results, competitors, customer research** (confidential) |
| Editor | video editor | animatic, timeline with verbatim on-screen text, timings and text style, captions, music and licence, formats and safe zones, hook versions to cut, file specs, QA | evidence and strategy |
| Media buyer | the person who runs the ads | hypothesis, decision metric, KPI vs the account baseline, minimum events and estimated test spend, variants (hooks, copy), placements and formats, audience, control ad | production details |

- **Standard brief fields** (agency creative brief + UGC creator brief), present in the data source and routed to the views above: single-minded **key message**; **tone of voice and mandatories / don'ts**; **KPI** in business terms (decision metric vs baseline, minimum events, R4); **budget, deadline, approver**; **usage rights and creator fee**.
- Money shown to recipients is in USD at a stated rate (account data in PLN is converted; project rule for outward communication).

## Rules from PB1 that apply here (handoff `refresh-ad_v03`, PLAYBOOK.md, verbatim)

### R3. Every number in the outputs has a source
- Every number in the strategy brief, creative brief, reports and materials (promo too) has a stated source: an MCP call (tool and parameters) or a file in the run.
- **A hypothesis is never presented as a conclusion.** A hypothesis from the ad content (e.g. the target audience) is always marked as a hypothesis and set against the data. In outputs for the recipient, what remains is what the data says.
- Numbers without a source are removed before acceptance.

### R6. Format by placement
Output formats follow from the distribution of purchases by placement (breakdown from step A3b). A placement with **≥ 25% of results** gets its own format:
- Facebook and Instagram feed: **4:5**;
- Reels and Stories: **9:16** with safe zones.

Examples: in ExampleTravel the feed was 55% of purchases, in Ad 3 71%, and we made both ads only in 9:16.

### R7. Copy and thumbnail
Every refresh includes a decision on the **primary text, headline and thumbnail (cover)**: either a change with a justification in the data, or an entry in the change register "no change, because…". Nothing carries over from the old ad without a decision. A copy change is a separate item in the change register, so that the test can distinguish what worked.


**How R6 and R7 read in a brief** (there is no old ad and no change register): R6's breakdown is
B1's placement read, and `tm audience pick` gives the formats; R7 means every brief writes its
primary text, headline and thumbnail (`ad_copy.primary`, `ad_copy.headline`, `plugin.thumbnail`),
which `tm brief check --stage brief` requires.
