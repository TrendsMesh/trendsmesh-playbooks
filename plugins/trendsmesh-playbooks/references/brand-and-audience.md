# Brand profile, channel profile and audience: who the brand is, who watches, and who buys (shared: PB02, PB03)

Two inputs every brief rests on, built once and kept for later runs: the **brand profile**
(CB3's short brand intake) and the **audience from two sources** (CB1). PB03 (organic video)
adds the **channel profile** (OV1), which names a store's brand profile for its catalogue.

## The brand profile

Drafted by you, confirmed by the user, saved in the workspace library:
`<workspace>/library/brands/<brand>/brand_vNN.json`. A later run of the same brand starts from the
latest saved version (`tm brand show --name <brand> --json`): show it on the card and ask only
what may have changed.

- **Draft it** from the landing page (saved in `00_raw/`) and the running ads' copy; when the user
  points to a brand guide (a file, a link), read it and set `guide`. The short brand intake's five
  points: what the brand stands for in **one sentence**; the tone in **exactly three words**; the
  topics and imagery that are **off-limits**; the **claims** it may make, each with its wording and
  its source (usually the landing page); the **competitors** to watch.
- The shape (`brand/1`), written as `03_wip/brand_vNN.json`:

  ```json
  {"schema": "brand/1", "kind": "brand", "brand": "Night School e-book",
   "stands_for": "A plain-language course in dream recall and lucid dreaming, built on published research.",
   "tone": ["plain", "curious", "practical"], "off_limits": ["medical claims"], "off_limits_asked": true,
   "claims": [{"claim": "the sleep study", "wording": "a published sleep-lab study on dream recall",
               "source": "00_raw/landing_nightschool_2026-11-04.txt"}],
   "competitors": [], "guide": {"source": "none", "where": null},
   "drafted_from": ["landing", "ads", "user"], "confirmed": "2026-11-04"}
  ```

- **One question only:** "Anything off-limits?", asked on the intake card. Everything else is
  drafted and shown for the user to correct. `off_limits_asked` is true only once you asked it;
  `confirmed` is the date the user confirmed the card (null until then).
- `tm brand check --run R --file 03_wip/brand_vNN.json --json` (exit 2 lists what to fix), then
  `tm brand save --run R --file 03_wip/brand_vNN.json --json`: it writes the next library version,
  never over an earlier one, and gives its path for the config's `brand.profile`. A file named
  this way is found from the workspace, where you work: from there first, else in the run.
- Word every claim precisely, as the source says it (R3): a landing page can word a study more
  strongly than the study does ("proven" for "observed"); the brief keeps the source's own wording.
- `kind` is `brand`. A store's brand profile may also hold its **catalogue** (`catalog.products`:
  `{name, packshot, problems}`), which every channel naming that store shares (below).

## Channel profile

Organic video's first step (OV1): who the channel is and what bubble its trend search starts from.
One profile per channel, drafted by you from the intake's answers (organic video asks them in one
batch at A0), confirmed by the user, saved in the workspace library:
`<workspace>/library/channels/<slug>/channel_vNN.json`, where the slug is the channel's name in
lower case with dashes ("Cat Corner" → `cat-corner`), as the run's config names it (`channels`).
A later run starts from the latest saved version (`tm brand show --name <channel> --kind channel
--json`) after the "Reuse the saved channel profile" check-in.

- The shape (`channel/1`), written as `03_wip/channel_<slug>_vNN.json`:

  ```json
  {"schema": "channel/1", "kind": "channel", "channel": "ExampleEdu", "store": null,
   "platforms": ["tiktok", "instagram", "youtube", "facebook"], "account_type": "creator",
   "audience_language": "pl",
   "context": {"films": "short advice videos", "topic": "kids and video games",
               "audience": "parents of children aged 7 to 14", "style": "calm, factual",
               "performed_links": []},
   "product_role": "not_shown", "content_rules": ["no real children's faces", "a source for every claim"],
   "voice": {"narrator_elevenlabs_id": null, "host_description": null, "host_image": null},
   "music": {"folder": null, "index": null}, "assumptions": ["the audience's age band"],
   "confirmed": null}
  ```

- `context.films`, `topic` and `audience` are **the bubble** the trend search starts from (OV1):
  not the account type. `account_type` is `creator` or `business` (a business account gets a
  commercial-library alternative to trending sounds in every posting kit). `audience_language` is
  the captions' and the speech's; pages follow the chat language.
- **A store with several channels** (a brand's faceless channels): one profile per channel, each
  naming the store in `store`; the store's brand profile (above) holds the one catalogue they
  share, saved first. `product_role` is per channel, from `not_shown` to `hero` (OV5). A channel
  that sells nothing has `store: null`, and its videos show no product. The same video is never
  posted on two of the store's channels: each gets its own take.
- **Content rules** for a sensitive niche (children, health, money): offered at the intake, kept
  in `content_rules` (no real children's faces, a source for every claim, no medical claims).
- The voice and the music folder are asked when first needed, then saved in a new version.
- `assumptions` lists what you assumed rather than heard; the card marks each one.
- `tm brand check --run R --file 03_wip/channel_<slug>_vNN.json --json` (exit 2 lists what to fix),
  then `tm brand save --run R --file 03_wip/channel_<slug>_vNN.json --json`, with `confirmed:
  null`. **The confirmation is the user's**: after their yes at the profile check-in (`tm decide
  profile accept`; in a run of several channels one decision per channel, its note naming the
  slug), `tm brand save --run R --file 03_wip/channel_<slug>_vNN.json --confirmed --json` sets the
  date. A draft that brings a date of its own is refused, and so is a reuse of a profile nobody
  confirmed.

## The audience: the hypothesis first, then the data

The project rule (CB1, R3): **write who you think buys before you read who did.** A divergence
between the two is a finding, and a hypothesis is never said as a fact.

1. **The hypothesis**, from the product, the landing page (its "this is for you if" lines are the
   brand's own hypothesis, tier C) and the ads: age, gender, the situation they are in, what they
   tried before, what they want. Write it to `02_research/audience/hypothesis_v01.md` and record
   it: `tm audience hypothesis --run R --file 02_research/audience/hypothesis_v01.md --json`.
   **Before any read broken down by age or gender**: the engine refuses a hypothesis recorded
   after one. (A read of the ad sets' targeting for the market, at A1, is not audience data.)
2. **The data** (the Meta Ads connection, `audience/1` source `meta_ads`): the results broken down
   by age and gender, then by `publisher_platform` and `platform_position`. The collector saves
   each read in `01_base/meta/`.
3. **The pick:** `tm audience pick --run R --breakdown <age × gender file> --placements
   <placements file> --json`. **The CB1 rule:** the segment with the lowest cost per result among
   those with at least `persona.min_results_per_segment` (10) results. When none reaches 10, the
   thin-data fallback: the largest directional cluster (the age band with the most results), and
   the persona is marked **directional** in every output (the brief, the page, the cards).
   Cross-check it with the same product in another market or campaign when one exists. The
   placement split gives the formats (R6: a placement with at least 25 % of results gets its own:
   feed 4:5, Reels and Stories 9:16). A product with no ad history: `tm audience pick --run R
   --no-data` (the hypothesis alone, directional, both formats).
4. **Say both, side by side**: the hypothesis, what the data shows, the divergence ("the
   hypothesis said 25–34; the cheapest results came from 55–64, 9 of 28").

The audience module takes any source: Meta ads now; channel analytics come later (measurement is
out of scope for organic video's first version), read the same way (the hypothesis first).
