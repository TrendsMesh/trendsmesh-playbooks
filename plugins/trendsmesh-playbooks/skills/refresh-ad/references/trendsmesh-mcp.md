# TrendsMesh MCP

Bundled with the plugin (`.mcp.json`, server `trendsmesh`). The user chooses Free or Paid and, on
Paid, signs in from `/mcp` (`trendsmesh-sign-in.md`). **Trend data needs the paid Agent plan.** A
free account can sign in, but its data tools answer `not_in_plan` (with `plan_code` and
`upgrade_url`). Until free accounts can finish connecting, the sign-in page refuses them and
says their plan doesn't include agents. The plans page is `https://trendsmesh.com/plans`.

Read each tool's own schema for the exact arguments; these are the ones as of 2026-11-05.

| Tool | What it gives | Main arguments |
|---|---|---|
| `get_usage` | your plan (`plan_code`) and its limits: for each meter and window, the limit and the calls left | none. The readiness check (it answers on every plan), and before pulling many pages |
| `search_trends` | trend cards closest in meaning to what you describe, with a `match` score | `about` (your words, any language), `trend_type` (`hook_trend` or `topic_trend`; omit for both), `min_match`, `feed` (default `global`), `limit` (20), `page` |
| `list_trends` | one feed's current trends as ranked cards | `sort` (`rising`, `updated`, `score`, `recent`, `decay`), `trend_type`, `q` (literal text), `feed`, `include_general`, `as_of` (rising: keep later pages on the same ranking), `limit` (50), `page` |
| `get_trend` | one full card: why it popped, reach, momentum, confidence, lifecycle stage | `trend_id` |
| `get_trend_videos` | a trend's videos, one page at a time, with platform links and views | `trend_id`, `order` (`views` or `recent`), `limit` (50), `page` |
| `list_hooks` | hook formats (reusable opening lines), ranked by confidence | `limit` |
| `get_hook` | one hook format | `hook_cluster_id` |
| `list_topics` | top-level topics, most active in the last 7 days first; the vocabulary for `search_trends` | `limit`, `cursor` |
| `list_sounds`, `get_sound`, `get_sound_videos` | reused sounds and their videos | `cursor` / `group_id`, `limit`, `page` |

Trend types: `hook_trend`, `topic_trend`, `sound_trend`, `format_trend`, `meme_trend`,
`theme_trend`, `product_trend`, `event_trend`, `controversy_trend`, `viral_asset`. A trend card
carries name, what it is, why it popped, formula, original phrase, examples, proof, momentum,
reach, confidence, status, since, active for days, visible until, languages and
`sensitivity_level`.

## How a run uses it (A5, A6, D1)

- Candidates come from `search_trends` (the product's phrases, the persona's interests) and from
  `list_trends` sorted `rising` and `updated`, not from a list you invent.
- **Hook fidelity (lesson 10):** before writing a hook, read the trend's example videos, every
  page of `get_trend_videos` for a hook trend you may use (the Ad 3 run read 64 videos for one
  hook trend). Use what each video carries: `hook_text`, `hook_source` (speech or on screen),
  `appears_at_s`, `slot_fill`, the caption position. Reproduce the structure; otherwise the test
  checks your interpretation, not the trend.
- Rank by creators and view lift, not by views alone. Trends mostly come from EN TikTok: moving
  one to another market is a hypothesis (lesson 5), said as one.
- Topic trends for a topic swap (`variants.md` section 4b, not copied here): confirmed, rising,
  `sensitivity_level` none, outside politics and news, fitting the season, with a one-sentence
  bridge to the product's promise. TrendsMesh gives languages, not demographics.
- **Every answer is saved by the collector** (on since A1) into `02_research/` (`trend_<id>.json`,
  `videos/<id>_pNN.json`, `search/`, `lists/`) with a manifest row; searches, lists and video pages
  come back as a short summary with `saved_to`. Only an answer the hook says was not saved is
  saved by hand (`tm trends ingest`).
- Organic clips are evidence and inspiration only, never footage for the ad. Trending sounds are
  usually not licensed for paid ads.
- The internal "why" route of the old trend API is not used: clients cannot reach it.
- Rate limits: check `get_usage` before a long pull; if a meter runs out, say so plainly and
  continue when it resets, from the same place.

## Without TrendsMesh (Free, the user's choice)

The playbook runs without TrendsMesh only on Free: the user chose it at readiness
(`trendsmesh-sign-in.md`). Without that choice it never starts guessing on its own, and the engine
refuses `tm evidence guess`. Then:

- At A5 record `tm evidence guess --run R --why "the user chose Free"`. The candidates come from the
  account's own winners and the Meta Ad Library (`flow.md#a5`), never from a trend you invent.
- Every change is a **guess** in the change register (`tm register check` refuses a proof).
- Say the `notice` from `tm next` when it comes (the direction of changes, the launch, the final
  report): the new hook is a guess, and what TrendsMesh would have shown. Say it as a statement,
  once per card; don't ask about it and don't repeat it in between. End the final report with the
  `free_box` `tm next` gives.
- A data tool refused with `not_in_plan` mid-run (the plan lapsed): say what stopped, give the way
  back (the `upgrade_url`) and wait; switch to Free for this run only after the user says yes, and
  only until the change register (A7) is done (`trendsmesh-sign-in.md`, section 6). After it the
  changes are decided: tell the user, and write what you have (a trend status you can't fetch is
  `unknown`). A rate limit: wait for the reset, as above.
