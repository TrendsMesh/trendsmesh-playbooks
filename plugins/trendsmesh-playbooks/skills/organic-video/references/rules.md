# Hard rules OV1 to OV14 (and PB1's R3, and HANDOFF §4's rules)

OV1 to OV14 are copied verbatim from the handoff's `PLAYBOOK.md` (handoff `organic-video_v02`, section
4, "Hard rules", v1.0, 2026-11-06); R3 verbatim from PB1's `PLAYBOOK.md` (handoff
`refresh-ad_v03`), which OV applies unchanged; and the rules from outside the playbook files
verbatim from `HANDOFF.md` §4. They apply in every run, at every level of involvement. The agent
may not skip them. The config changes only their threshold values, never the rule.

How to read the copy in the plugin:

- Where it says "gated" read **Check every step** (and **Just the big calls**, which asks two
  cards per video); where it says "A–Z" read **Hands-off**. Its gates are the plugin's check-ins
  (`checkin-cards.md`), and users only ever see "check-in". The pack and its cost is asked at
  every level, as "Approve the generation pack and its cost".
- Where it names the trend API, `trends_api.py`, `pull_cards.py`, `.claude/skills/trend-source`,
  `TREND_API_KEY` or `.secrets/api_keys.env` (python-dotenv), the plugin reads TrendsMesh through
  its MCP (`flow.md#b1` maps each call), and the collector saves every answer to the run
  (`references/trend-collection.md` at the plugin root): there is no TrendsMesh key, ever, and
  nothing reads that file. The Replicate token and the ElevenLabs key come from the plugin's own
  configuration (`/plugin` → trendsmesh-playbooks → configure), never from a file in the workspace.
- The tools it names are `tm` commands: `trend_shortlist.py` is `tm trends shortlist`;
  `proposals_page.py` and `script_page.py` are `tm organic page proposals` and `tm organic page
  script`; the kit's checks are `tm kit check` (in a script, `tm organic script check`); the
  run folder and its manifest are the engine's (`tm record`). The rest (`replicate_run.py`,
  `replicate_price.py`, `elevenlabs_voices.py`, `build_prompt.py`, `render.mjs`, Remotion,
  `transcribe.py`, `gate_page.py`, `weekly_page.py`, `music_index.py`) are the engine's too
  (its tools under `tm tool`, the pages under `tm organic page`).
- **Not built in this version**, said plainly: the AI video (OV4's production, OV5's packshots,
  OV6 to OV10), the weekly pack, a publishing tool (the user downloads and posts), Higgsfield,
  pages in languages other than English and Polish, the sensitivity filter, measurement.

What the engine checks, so you never do it by hand: the channel profile and its confirmation
(`tm brand check`, `tm brand save --confirmed`: OV1); the shortlist with its anchors, the fit
scores and sound relevance (`tm trends shortlist`: OV2); the used trends and series (`tm organic used`); the
proposals (`tm organic proposals check`: 4 to 6, every trend a saved card, Recreate's two picks,
Inspire's weak link, the nine risk items with mitigations and no percentages, the production
types the stack hides, the product level, used trends, never "no trend found": OV2 to OV5); one
production run per idea, for one channel, once (`tm organic start`: OV1); the script (`tm organic
script check`: a source per fact, the words a second, the hook on screen, the kit: OV7, OV11,
OV14); the posting kit (`tm kit check`: OV11); the pages and the decisions read from them (`tm
organic page`, `tm organic decisions`, `tm page await`: OV12).

## The words fixed by the spec (use them verbatim, on the pages and in messages)

- "Recreate" and "Inspire" (OV3); on a Polish page "Odtworzenie" and "Inspiracja".
- The product levels "not shown", "incidental", "featured", "soft mention", "hero" (OV5); on a
  Polish page only "nie występuje" is accepted so far (the other Polish words wait on the playbook owner).
- Never "no trend found" (OV2): show the best fit.
- Never a bare code for a video in a message: "the ChatGPT age-limit host video", not "M5"
  (HANDOFF §4).
- "organic only" for a trending sound (no licence flag in TrendsMesh yet).
- "check-in", never the spec's other word; the levels **Check every step**, **Just the big
  calls**, **Hands-off**.

## The numbers (copied from PLAYBOOK.md; the config's defaults)

- C1: 4 to 6 proposals per page (`proposals.min`, `proposals.max`).
- OV2: four lists, hooks, topics, formats, sounds; search in the audience language and English;
  the evidence of `research.cards` (12) trends, split by the channel type; recent within
  `research.recent_days` (7); a hook or format fits the channel at 3 of 5 or more.
- OV3: Recreate needs at least 2 evidence videos with the same structure; a style spec is read
  from at least 2 evidence videos.
- OV4: the nine risk items; no percentages.
- OV6: budget `bytedance/seedance-1.5-pro`; default `minimax/h3` (768P, $0.08/s); top
  `bytedance/seedance-2.0` (720p, $0.18/s); premium on request `bytedance/seedance-2.5`.
- OV7: a script sized at 2.8 to 3 words per second (`qa.wps_min`, `qa.wps_max`); at least 1.5 s
  after the last line; a slow take sped up by up to about 1.25×; a voice reference only on
  request, same text, at most 14 s; real narrator voices run 2.5 to 3.8 words a second.
- OV8: 720p (768P on H3), 1080p, or 720p + upscale; the default upscaler
  `prunaai/p-video-upscale` ($0.02/s at 1080p); prices no older than `pricing.max_age_days` (7).
- OV9: a take's transcript at least 90 % of the script; images redone once automatically at
  most; videos never.
- OV10: 9:16, 1080×1920, H.264, AAC 48 kHz, −14 LUFS (ASMR about −16); safe zone x 90–880, y
  260–1540; animation text and key action above y 1260.
- OV11: TikTok line 1 = hook + search phrase, 3 to 5 hashtags, a cover frame with words (the
  engine takes 2 to 7: the handoff's approved kits have 6 and 7), the AI label,
  "Your brand" when the product is shown; Instagram first line at most 125 characters, at most 5
  hashtags; YouTube title at most 100 characters, 1 to 2 sentences and 2 to 3 hashtags, tags at most
  500 characters; Facebook 1 to 3 hashtags; at most one genuine question (the caption's opening hook
  question is not counted: still to be confirmed); no sources in any post text; the sound split original
  100 %, added 10 to 15 %. The AI label by production type: photoreal on, on every platform; a clearly
  animated style off unless the user asks for it. Each limit is in `data/organic-video/platform_rules.yaml`
  with its source and the day it was checked; a kit names the rules' date it was written to
  (`rules_read`); re-check `posting-kit.md` when it is older than about 3 months (`tm kit check` warns).
- OV12: the video as a 1080p upload copy under 15 MB, the cover as JPG, the script as `.md`;
  previews 720p, CRF about 27.
- Config defaults (PLAYBOOK §7): `budget.per_run_usd` 5, `budget.per_week_usd` 5; `generation`
  replicate, default tier, 768p, no upscale; `publishing.tool` none.

## OV1 to OV14 (PLAYBOOK.md section 4, verbatim)

In the plugin, "an Atlas style" below means one of the plugin's own styles (`data/styles/`,
`tm organic atlas-styles`); the third-party catalogue in `resources/ai-style-atlas/` is gone.

The agent may not skip them. The config changes only thresholds and defaults, not the rules. PB1 R3 applies unchanged: every number has a source, and a hypothesis is never presented as a finding.

### OV1. Channel profile first
- The search bubble comes from the channel context, not from the account type.
- One profile per channel; a store with several faceless channels has several profiles sharing one catalog.
- The same video is never reposted across a store's channels; each channel gets its own take.

### OV2. Trend search and shortlist
- Query the trend source (`tools/trends_api.py`, later the TrendsMesh MCP) with the niche anchor terms, the problems the catalog solves and the channel's own formats. Search both the audience language and English.
- Shortlist four types: **hooks, topics, formats, sounds** (CTAs when TrendsMesh adds them). Each comes with evidence videos and numbers: creators, videos, views, status, hook source, view lift.
- A topic's relevance needs an anchor term next to the activity term, to avoid shared-word noise: the subjects the channel covers, from its profile, not only the niche's own words.
- Hooks and formats get no word filter (they say how a video opens and is told, not what it is about): each gets a fit score for this channel, can it carry what the channel films and how it tells it, shown on the shortlist with one line on why (issue #84).
- Sounds need a niche-relevance score from their description and the evidence captions.
- The channel's type (its profile) sets how many trends of each kind are pulled, out of 12 (a news channel 6 topics, a music channel 6 sounds). A trend with a weak fit never takes a place just to keep the split: its places go to the type's leading kind. At least half of the proposals are built on that kind, and the proposals page says why it leads (issue #85).
- Never write "no trend found"; show the best fit.
- Transfer across language or subject is a hypothesis. It lowers expected reach, not feasibility, and the proposal says so.
- Skip trends already used on the channel (used-trends log). Continue running series.
- Save every response to `02_research/trends/` (asset rule).

### OV3. Two approaches; a format is copied with its look
- **Recreate:** take the whole video type (structure, timing, on-screen look, sound) and change the subject. Proposed when a format has at least 2 evidence videos with the same structure.
- **Inspire:** take one or more ingredients (topic, hook, sound, format) and build a format that fits the channel; the proposal states the weaker trend link.
- Reproducing a format means reproducing its **look**: a style spec read from at least 2 evidence videos (layout, font class, colours, number style, extras), shown next to the reference before rendering (lesson 21).
- Logos, characters, watermarks and existing art are never copied. Characters are our own designs.

### OV4. The format decides the production type
| Evidence shows | Production type |
|---|---|
| scenes, reactions, objects | **AI footage** (video model) |
| a person or animal talking to camera | **AI talking character** (OV7) |
| diagrams, explainers, data | **Claude animation** in an Atlas style (`resources/ai-style-atlas/`) |
| quiz, ranking, list with pictures | **stills + Remotion motion graphics** |

- A format that mixes types is made in **sections**, each by its own method, with one video model per section (e.g. footage → animated insert → footage).
- The user may propose another type; the agent states what changes in risk, cost and native look.
- **Risk** is a level (low / medium / high) from a checklist of failure modes:
  - hands on objects;
  - a product that must keep its shape;
  - the same character across takes;
  - fast motion;
  - physics (liquids, fur, food);
  - text drawn by the model;
  - speech;
  - takes over ~10 s;
  - several characters.

  Each risk hit is named with its mitigation. No percentages until about 20 videos per type exist.

### OV5. Product decision and product fidelity
- Every video states its product level:
  - **not shown**;
  - **incidental** (used in the scene, no logo, no mention);
  - **featured** (it does the job on screen);
  - **soft mention** (caption, pinned comment or bio);
  - **hero**.

  The agent suggests a level from the channel's product role, the format, the risk and whether creators in the evidence show products. The user confirms.
- **A product enters a video only from an image, never from words**, and must match the packshot 1:1 (round 20). Routes:
  - H3 **reference mode** (opening frame + packshot as references, opening described, `ratio` set);
  - a first frame made with GPT Image 2 from the packshot.
- Packshots are made once per store and reused by every channel.

### OV6. Model choice: suggest, never impose
- For each component, suggest the best current model available at the user's provider, with the reason. Sources:
  - independent rankings read on the day (Artificial Analysis, Arena), with the date noted;
  - the live price (`tools/replicate_price.py`, `billingConfig`), with the check date.
- **One video model per video**; another model only for a separate section.
- **Quality tiers** (round 28):

  | Tier | Model | Use |
  |---|---|---|
  | budget | Seedance 1.5 Pro | no speech, no precision, sound unimportant; **not** for ASMR or anything sound-led |
  | **default** | **MiniMax H3** (768P, $0.08/s) | most formats |
  | top | Seedance 2.0 (720p, $0.18/s) | — |
  | premium on request | Seedance 2.5 | — |

  Sound-led formats (ASMR) go to H3, Seedance 2.0 or Veo 3.1.
- **A generated person who talks** (round 27):
  - no specific influencer (person from a description) → **Seedance 2.0** with the person in text and product/pet references;
  - a **specific AI influencer** (approved image) → **MiniMax H3 reference mode**.
  - Seedance rejects photoreal faces in input images, synthetic ones included (E005). The BytePlus asset route is not used (round 25).
- **A model the user names** is checked against these criteria, and the agent says which one fails:
  - accepts a photoreal AI person image (when a specific influencer is used);
  - takes the product from an image together with the person;
  - has native speech or fits the lip-sync route;
  - supports 9:16;
  - covers the take length the script needs;
  - is available at the user's provider with a live price.
- Before writing prompts, read the model's recipe in `resources/model-prompting/`. A model without a recipe gets one first.

### OV7. Speech and voice
- **On-screen talking character** (human or animal): **native speech on MiniMax H3**, with the **dialogue written straight into the prompt** inside a timed shot list (round 33).
  - **No ElevenLabs voice reference by default** (round 47; it sounded worse and garbled Polish). A voice reference only on request: same text, ≤ 14 s.
  - Works in English and Polish, word for word (rounds 42, 45).
- **Fit check and pace:**
  - size the script at about **2.8–3 words per second**; ask for "a brisk, energetic TikTok pace, no pauses between sentences";
  - leave ≥ 1.5 s after the last line; avoid whispering;
  - QA measures the pace; a slow take is **sped up in the edit** (up to ~1.25×, pitch kept, lips in sync) before any regeneration is suggested (round 43).
- **Lines that do not fit one take:** propose an **extra shot or take** (split at a line break, same image and voice description) or move a beat to B-roll. The user approves the shot list and its cost.
  - Known risk, not solved yet: two separate H3 takes may give the same host two different voices (round 49).
- **ElevenLabs voice + lip-sync** (Kling Avatar v2, OmniHuman 1.5) is only an alternative: on request, or when wording must be exact or a brand voice must be used. Every lip-sync clip is checked for burned-in text artefacts.
- **Off-screen narrator** (explainers, VO over footage or animation): **ElevenLabs voice by default** (round 45); the H3 narrator from the prompt is the alternative.
  - Time the TTS before sizing the takes, since real voices run 2.5–3.8 words/s.
  - Voice choice: the user's own voice, or 2–3 proposals with previews. The pick is saved in the profile.
  - Voice rules from the project: clone 1:1, rights assumed.

### OV8. Cost, budget and approvals
- While testing, **every paid operation needs the user's approval** (Replicate, ElevenLabs beyond plan credits, any upscale). The pack shows the exact cost with prices and their check dates.
- **Budget guard:** before each paid call, add its cost to the spend; if the sum would pass the run (or week) budget, stop before calling.
- **A video is never regenerated automatically**, in any variant; only on the user's request, with its cost (round 42).
- **Resolution question** at the pack (round 29): 720p (768P on H3), 1080p, or 720p + upscale, each with its cost. **Default upscaler: Pruna** `prunaai/p-video-upscale` ($0.02/s at 1080p, keeps the audio); Topaz and ByteDance on request.
- Money in user-facing pages: USD (state the rate when the account currency differs).

### OV9. Staged production, two variants
- **Stage order:**

  | Production type | Stages |
  |---|---|
  | AI footage | packshots → character anchor → first frames → takes → edit |
  | Talking character | character image (approved first) → speaking take → edit |
  | Animation | style frame or storyboard → full render → edit |
  | Audio | VO → music → mix |

  The cheap stage is the test: first frames or a style frame show most problems before the expensive stage.
- **Gated:** stops at the gates the user keeps:
  - **pack + cost** (always on while testing);
  - images;
  - video;
  - final edit.
- **A–Z:** no stops after the pack.
  - The agent picks against a written rubric per stage:
    - images: realism, consistency, safe zone, no text;
    - takes: transcript ≥ 90% of the script, cuts on time, consistency, no burned-in text, usable loudness.
  - It records each pick and its reason in the manifest. Images may be regenerated once automatically; videos never.
  - The end is **one delivery page**: the final video, cover, kit and downloads, **plus every step** (all images with the pick marked, raw takes, VO, storyboard, QA findings), each with Accept / Redo with a note / Drop.
- **Outputs at each gate are shown side by side** on a gate page (OV12), never only in chat.

### OV10. Edit standards and QA
- **Output format:** 9:16, 1080×1920, H.264, AAC 48 kHz, loudness about **−14 LUFS**. ASMR may stay near −16 to keep its dynamics.
- **Native audio levels vary:** level them per segment, then compressor + limiter + loudnorm.
- **Safe zone** (most restrictive across platforms, at 1080×1920): text and key action inside x 90–880, y 260–1540.
  - Text is centred on the frame, never on the safe zone.
  - An Atlas animation in 9:16 keeps text and key action **above y 1260**, leaving the caption band free (round 32).
- **Captions:**
  - talking: word groups from the transcript;
  - narrated: phrase by phrase from the TTS timestamps;
  - formats with a known caption style: the copied style (OV3).
- **QA per take:**
  - scene detection for cut times;
  - Whisper transcript in the audio language against the script (a hint; the user's listen is final; quiet lines need a level envelope);
  - speech pace;
  - loudness;
  - contact sheet for consistency and artefacts.
- **Model specifics:**
  - H3 in reference mode needs `ratio: "9:16"`;
  - H3 rejects a first frame together with reference media (E006);
  - H3 audio references must be 2–15 s.

### OV11. Posting kit
Written for every final video and script, per the rules in `resources/posting-kit/best_practices_2026-11.md` (re-check when older than ~3 months). Written in the **audience language**.
- **Platforms:** TikTok, Instagram Reels, YouTube Shorts and Facebook Reels, all on by default; the user unticks per video.
- **Per platform:**
  - **TikTok:** hook + search phrase in line 1, 3–5 hashtags, cover frame + 2–4 words, AI label, "Your brand" disclosure when the product is shown.
  - **Instagram:** first line ≤ 125 characters, ≤ 5 hashtags (hard cap), a cover safe for the 3:4 grid crop, AI info.
  - **YouTube:** title ≤ 100 characters, 1–2 sentences + 2–3 hashtags, AI use = Yes for photoreal; links are not clickable in Shorts.
  - **Facebook:** short caption, 1–3 hashtags.
- **Writing rules:**
  - a natural search phrase, not keyword stuffing;
  - **no engagement bait**;
  - at most one genuine question;
  - emoji only with meaning;
  - **no sources in any post text** (round 38);
  - the product is a soft line, never the lead.
- **AI label:** on for any photoreal AI person, animal or scene; mandatory for an AI human host; not required for stylised animation.
- **Cover:** a caption-free frame + 2–4 words, clear of the face, inside the 3:4 crop. A **YouTube thumbnail** is optional (tick on the final gate; only outside the Shorts feed; YPP).
- **Sound hand-off** (no API can attach library sounds):
  - the kit gives the sound name, an evidence link, the in-app steps and the volume split (original 100%, added 10–15% under speech or ASMR);
  - a `_nosound` export when the trending sound replaces the track;
  - business accounts get a commercial-library alternative.

### OV12. Pages, language, decisions
- Every page the user reads uses the **chat language** (UI and content). Post text uses the audience language. The project docs stay in English.
- **Pages:**
  - proposals page;
  - gate pages and the A–Z delivery page;
  - script page;
  - weekly plan page.
- Each is published as a private artifact. Choices save to the artifact `db`; the user writes "ready" / "gotowe" and the agent reads them.
  - **Never republish a page while the user is deciding.** A decision written in chat always counts (round 39).
- **Downloads** (`downloads` capability):
  - the video as a 1080p upload copy under the 15 MB published-file limit;
  - the cover as JPG;
  - the script as .md.
- **Previews** are 720p (CRF ~27). Pages have no horizontal scroll at phone width.
- Refer to videos and decisions by what they are, never by a bare code.

### OV13. Assets, files, progress
- **Run folder:** `runs/03-organic-ai-video/<YYYY-MM-DD>_<name>/` (`00_raw`, `01_base`, `02_research`, `03_wip`, `04_final`, `05_results`, `showcase`, `manifest.md`).
- **Never overwrite** (`_v01`, `_v02`…). Every asset gets a manifest row: file, stage, source, parent, prompt and parameters, model, date, cost.
- Save every tool and MCP response next to the asset it produced.
- Paid predictions write `<name>.pending.json` right after creation (`tools/replicate_run.py`) and survive client errors.
- **Long steps show progress:**
  - a granular task list with time estimates;
  - subagents append their stage to `_progress.txt`;
  - a one-line status at each stage change.

### OV14. Facts
- Every claim in a script or on screen has a source checked before the script is accepted (PB1 R3).
- Sources live in the pack, the script page's fact check and the manifest; never in the post text (OV11).
- Claims stay soft ("often"); there are no medical or diagnostic claims.

## OV7, added after the spec (issue #88)

The verbatim OV7 above stands; these follow from the owner's live run on 0.11.0, and the pack check holds them:
- **Numbers in the voiceover are words.** In an ElevenLabs voiceover's text, numbers, dates and percentages are
  written out as words, in the grammatical case the sentence needs, in the market's language (a year or a count in
  digits was read in the wrong form). On screen they may stay digits. The take is recorded with the run's market
  language as its `language_code`.
- **Eleven v4 is the voice model** unless the user picks another (`../../references/model-prompting/eleven-v4.md`),
  and the voice credits are its characters at that model's rate (0.5 a character for v4).
- **The cuts follow the recorded voice.** After the recording, `tm organic vo-sync` compares the lines' word times
  with `script.lines[].at` and with the take prompt's cuts; a difference of more than about 0.3 s is moved to the
  word times before the paid take. An ElevenLabs voiceover is held to the same pace, `qa.wps_min`.
- **A re-record never stops the run.** Its estimate adds what the run has already spent; when the approved voice
  budget no longer covers it, the user is asked to approve the difference.

## Rules from PB1 that apply here (handoff `refresh-ad_v03`, PLAYBOOK.md, verbatim)

### R3. Every number in the outputs has a source
- Every number in the strategy brief, creative brief, reports and materials (promo too) has a stated source: an MCP call (tool and parameters) or a file in the run.
- **A hypothesis is never presented as a conclusion.** A hypothesis from the ad content (e.g. the target audience) is always marked as a hypothesis and set against the data. In outputs for the recipient, what remains is what the data says.
- Numbers without a source are removed before acceptance.

## Rules from outside the playbook files (HANDOFF.md §4, verbatim)

- **Run folder and manifest:**
  - `runs/03-organic-ai-video/<YYYY-MM-DD>_<name>/` with the standard subfolders;
  - never overwrite (`_v01`, `_v02`…);
  - every asset gets a manifest row with cost;
  - save every tool and MCP response.
- **Keys** in `.secrets/api_keys.env` (python-dotenv): `TREND_API_KEY`, `REPLICATE_API_TOKEN`, `ELEVENLABS_API_KEY`. Never print, log or commit them.
- **Cost rule while testing:** every paid operation is approved first, with prices and their check dates. Failed validations cost $0 (confirm on the dashboard).
- **A video is never regenerated automatically.**
- **Language:**
  - pages and summaries: the chat language;
  - post text and speech: the audience language;
  - project docs: English.
- **Never refer to a video or decision by a bare code** in messages to the user; say what it is.
- **Voice:** clone 1:1 when a brand voice is reused; voice and music rights are assumed (never ask).
- **Money for users:** USD, with the rate stated when the account currency differs.
- **Organic clips are evidence, never footage.** Trending sounds are organic-only.
- **Artifacts:**
  - a new artifact starts private;
  - publish first, then declare capabilities;
  - never republish a page while the user is deciding;
  - a decision written in chat counts.
- **Long steps show progress:** a task list with time estimates and one-line status updates. Subagents write `_progress.txt`.
