# Create an ad: every step

Each step's work, the files it writes and the check that holds it. `R` is the run folder. Every file is a new
version (`_vNN`), never overwritten, and recorded with `tm record` (paid calls record themselves). Each check-in is
put on the run page with what `pages.md` lists for it, and asked with its question card in chat; a decision on the
page and one in chat count the same. Rules: `rules.md`.

<a id="s0"></a>
## S0 Intake and asset inventory (CA1)

- Readiness first (SKILL.md section 1), then `tm evidence` is not recorded yet: that is S1's.
- **Pre-fill** from the product site (its "who is it for" block gives the persona options), the config and earlier
  runs of the brand under `runs/05-create-ad/` (language, ad account, CTA, generation budget, music). Show it as one
  card and ask **only the four questions**, each with options:
  1. who the ad is for **and what they make or do** (`brand.persona.who`, `brand.persona.makes`);
  2. what the ad sells: the product, one feature, the process or an offer (`intake.sells.kind`, `intake.sells.what`);
  3. the length and the placements, e.g. 15–20 s Reels/Stories or 30–45 s Feed (`intake.length_s`,
     `intake.placements`: reels, stories, feed, advantage_plus);
  4. existing materials: music, a voice-over recording, footage or B-roll, product shots, logo, brand guide, past
     ads, and files from earlier runs of the brand.
  Add the level, and for Hands-off the generation budget in USD (`budget.generation_usd`; ElevenLabs credits
  `budget.voice_credits` when the plan will use ElevenLabs). The ad budget is **not** asked here: it is asked in the
  upload proposal, in the user's words.
- **Not live yet** (early access, a waitlist): warn now; `intake.live: false` and `intake.not_live` say what it is.
- **The two languages** on the same card, filled from the defaults ("Working language: Polish · Market language:
  Polish"): `languages: {working, market}` as tags (`pl`, `pt-BR`). The working language is for the cards and
  pages, the market language for the ad's copy, voice-over, captions and on-screen text.
- Write the answers file (the config's shape, plus `level`), `tm config write --run R --answers <file>`, `tm config
  check --run R`.
- **The asset inventory**, `03_wip/assets_vNN.json`: `{"earlier_runs_checked": true, "assets": [{"file", "kind"
  (music, voiceover, footage, broll, product_shot, logo, brand_guide, past_ad, earlier_run), "usable": true|false,
  "replaces": <asset type or null>}]}`. Each usable file removes a generation step (say which); a voice-over
  recording fixes the voice route. Then `tm done S0`; the intake card is the check-in after it.

<a id="s1"></a>
## S1 Concepts (CA2)

- First `tm evidence trendsmesh --run R --why <reason>` (TrendsMesh answers with data) or `tm evidence guess --run R
  --why <reason>` (no Agent plan, not signed in, or the user said no).
- **Model ads (about 5):** ask first whether the user wants suggestions or has one. TrendsMesh paid (`origin=ad`)
  first. When it has no ads in the niche, say so and offer a Meta Ad Library search (`ads_library_search`), filtered
  for relevance; its keyword search is loose and covers commercial ads mainly for EU delivery, so outside the EU it
  is often empty. A guess run: Ad Library results where there are any, else formats you know, each marked
  `"source": "guess"`.
- **Trends:** any type that fits product, persona and model ad; the default recipe one hook, one format, one topic.
  Sound trends only with a licence for ads (`licence: ads`), otherwise as inspiration. Organic clips are evidence,
  never footage. Save each MCP answer in `02_research/` (`trend_<id>.json` for `get_trend`) and summarise large
  answers with a script, never read them whole.
- Write `03_wip/concepts_vNN.json`: `{"model_ads": [{"id", "name", "source" (trendsmesh, ad_library, user, guess),
  "why" (what to take from it), "saved" (the saved answer, for trendsmesh and ad_library), "run_days", "clip" (its
  first ~15 s saved in the run, for the page)}], "trends": [{"id", "type" (hook, format, topic, sound, hashtag,
  visual), "source" (trendsmesh, guess), "name", "evidence" (2 videos for a TrendsMesh trend), "thumbs" (2 evidence
  thumbnails saved in the run, for the page), "licence" (a sound)}], "concepts": [{"key", "name", "model_ad", "trends": [ids], "combine",
  "beats": [{"t", "picture", "line"}], "length_s" (inside the chosen length), "length_why", "cost_usd": [low,
  high]}]}` with 2–3 concepts, your recommendation first (the page selects it). The model ad gives the structure of its first seconds, not its length.
- `tm ad clips --run R --file <it>` saves each model ad's thumbnail and first ~15 s from its saved Ad Library (or
  TrendsMesh) answer into `02_research/clips/`, so they play on the concepts page by themselves; it says which ad
  has no video file (an image ad), whose card shows its thumbnail.
- `tm ad check concepts --run R --file <it>`, then `tm done S1`. The concept check-in is the concepts page
  (`pages.md`) and its card, with the guess notice `tm next` gives; a concept picked on the page comes back with
  `tm page decision`. **Feedback loop:** notes or results are analysed and the
  concepts presented again with the changes worked in (a new version, checked again), asking only what is unclear;
  never jump to production on a note. Record the pick (or the mix note) with `tm decide concept accept --note`.

<a id="s3"></a>
## S3 Sources and claims (CA3)

- `03_wip/claims_vNN.json`: `{"claims": [{"id", "text", "source" (site, user, trend), "ref" (the page, the user's
  words, the trend)}], "not_live_said"}`. Staged data inside the story (a mock-up screen, a trend card) is allowed;
  the copy never invents numbers, results or availability. When what is sold is not live, `not_live_said` is how
  the ad says so. `tm ad check claims`, `tm done S3`.

<a id="s4"></a>
## S4 Script-board (CA4)

- `03_wip/board_vNN.json`: `{"model_ad_wpm", "scenes": [{"n", "start", "end", "name", "picture", "on_screen_text",
  "line", "speaker", "sound", "source" (generate, site, asset:<file>), "claims": [ids]}]}`. Scenes follow each
  other from 0 s to the ad's length, inside the chosen length; the hook has on-screen text from 0 s.
- The word budget is seconds × the model ad's words per minute; one speaker's lines fit one take (about 45 words,
  15 s). Avoid the openers that failed (rules.md CA4). `tm ad check board`, `tm done S4`.

<a id="s5"></a>
## S5 Production plan and its cost (CA5 to CA7)

- Read each model's prompting guide first (`../../references/model-prompting/`; a model without one: find its
  current guide, save it with its date, and keep the rules next to the prompt). Live prices: `tm tool
  replicate_price`, saved in `02_research/` with the date.
- `03_wip/production_plan_vNN.json`: `{"voice_route" (native, elevenlabs_voice, user_vo, clone_take), "lines":
  [{"item", "type" (an asset type: presenter, hook_scene, product_shot, still, slide, animation, music, sfx, voice,
  upscale, transcription), "stage" (pre_video, or video for the takes, priced again at G3), "model", "alternative",
  "cost", "budget" (ai_usd for Replicate, voice_credits for ElevenLabs), "price_file", "checked" (the price's
  date)}]}`. A type the user's own file replaces has no line: say what the file replaces. A `voice` line is the
  ElevenLabs model (`eleven_v4` unless the user picks another, `../../references/model-prompting/eleven-v4.md`)
  and its cost the lines' characters at that model's rate (0.5 credits a character for v4, 1 for
  `eleven_multilingual_v2`); the lines write numbers, dates and percentages out as words in the market's
  language, which the take is recorded in (`language_code`).
- `tm ad check plan` re-plans the money: its pre-video lines. `tm done S5`. The check-in is "Confirm the
  production plan and its cost" (at Just the big calls on one card with the script-board): the user confirms once
  per asset type; a new type or a model change later is a new plan version and asks again. After the yes, `tm
  budget approve --run R ai_usd <the pre-video ai_usd total>` (and `voice_credits`). Hands-off: the intake's budget
  is the yes; a plan above it waits for the user.

<a id="g1"></a>
## G1 First visual output (CA8, CA9)

- What the ad type needs first: presenter casting (2–3 visibly different, non-identifiable people; the CA9 guard in
  the prompt when a model ad's look is reused), stills or slides, or a test frame. Each paid call: `tm tool
  replicate_run --run R <spec> --name <the plan's item> --cost <its line>` (the gate page shows the outputs of the
  item's latest run). Show the batch raw, side by side, on the gate (`pages.md` "Gate"); never only as images in chat. `tm done
  G1`, then the check-in.

<a id="g2"></a>
## G2 Audio

- Music (the user's, the config's `audio.music_source`, or generated), SFX takes and the transition sound (a small
  library, swappable). ElevenLabs calls through `tm tool elevenlabs ... --cost <credits> --out
  03_wip/audio/<the plan's item>_vNN.mp3`. The gate shows each take to listen to. `tm done G2`.

<a id="g3"></a>
## G3 Filled storyboard and the paid video (CA7, CA8)

- Build the edit's screens before any paid video: a real frame per scene, the chosen audio, and **a placeholder
  take** (the creator still with a slow zoom), rendered whole (`tm render`). Check the stills: text-heavy screens
  must not sit small inside a card.
- `03_wip/storyboard_vNN.json`: `{"frames": [{"scene", "file"}], "placeholder_render", "audio": {...}, "videos":
  [{"item", "model", "prompt" (exact), "params", "prompt_rules" (the guide used), "cost", "budget", "price_file",
  "checked", "speaks" (optional: true when the take says the lines, false when its voice comes in the edit; left
  out, it follows the voice route: native and clone_take speak)}]}`; an ad without video: `"videos": []` with
  `no_video_reason`. One character = one take.
- `tm ad check storyboard` re-plans the money with the videos, so the plan's yes no longer covers it. `tm done G3`.
  The check-in "Approve the filled storyboard and the paid video" shows the storyboard scene by scene with the exact
  prompt and price; on the yes, `tm budget approve --run R ai_usd <the new total>`.

<a id="g4"></a>
## G4 Takes (CA7, CA8, CA11)

- Each take: `tm tool replicate_run --run R <spec> --name <the storyboard's item> --cost <its line>`; an unfinished
  take is resumed for free (`--resume`), never run again. The engine refuses a video before the storyboard's yes and
  a second take of an item the user did not ask for.
- **Every take goes back raw** on the gate with its transcript and QA notes: `tm tool take_qa --run R <take> --lang
  <market language> --script <its lines>` (cuts, the transcript, pace, loudness, contact sheet; leave `--script` out
  for a take that does not speak) and ElevenLabs Scribe word timestamps (verbatim, keeps repeats; Whisper hid a
  repeat and ran early). `tm done G4` needs every take of the storyboard made and QA'd (`ad_takes_checked`).
- The engine judges each take (`tm.create_qa`, the gate's QA notes): it **fails** on a transcript under the
  threshold, a loudness outside the usable range, or a word heard twice in a row that the lines say once (a
  stutter); its **findings** are a word lasting about 2× its expected length (a possible hidden repeat: listen
  there), internal cuts (keep each line's picture inside its own shot) and a slow pace.
- **A failed take is never regenerated automatically**: `takes accept` is refused while a take fails, until
  `fails_qa` was recorded after its latest QA (the stop for the user). The options: a precise cut of the original
  (Scribe times), a voice clone of the line (only when it must change), a new take (its cost first; on their yes
  `tm ad redo --run R --item <item> --note "<their words>"`), or accept it as is (`tm decide takes accept --change`
  on their word).

<a id="s6"></a>
## S6 Edit (CA10)

- A data-driven edit: a timeline (scenes, take segments with a time map, overlays, captions, sound cues) turned
  into the composition's props, rendered (`tm render`), then the loudness pass (`tm tool deliver`). Overlays are
  those proposed on the storyboard. Write each version as `03_wip/edit_vNN.mp4`. `tm done S6`.

<a id="s7"></a>
## S7 Edit QA (CA11)

- Before every showing: motion at every cut, scene detection inside generated takes, stills after every layout
  change, caption collisions, Scribe on the take and the edit (compare the two to tell an edit bug from a model
  stutter), ~80 ms of pause at speech joins, generated logos and text letter by letter, −14 LUFS integrated and true
  peak ≤ −1.5 dBFS.
- Measure the latest edit like a take: `tm tool take_qa --run R 03_wip/edit_vNN.mp4 --lang <market language>
  --script <the board's lines>`. Write what was checked next to the version, `03_wip/edit_qa_vNN.json`: `{"edit"
  (the latest edit), "qa" (its latest take_qa file), "checked": [{"check" (cuts, take_scenes, stills, captions,
  speech, joins, overlay_ends, text), "result" (ok, not_applicable, problem), "note" (what you looked at)}]}`, one
  row per check. `tm ad check edit --run R --file <it>` refuses a loudness more than 1 LU off the target, a true
  peak above the limit, a transcript under the threshold or a stutter in an edit with lines, a check left out, and
  a `problem` (fix it in a new version, S6, and QA that). `tm done S7`; `review accept` needs the same check on the
  latest version, so a fix after the review is QA'd again before it is shown.

<a id="g5"></a>
## G5 Review (CA12)

- Versions side by side, each labelled, with a pick; notes pinned to the playing version's time (`pages.md`
  "Review"). Fixes (`fix`) go back through S6 and S7 as a new version; audio-only fixes under screen-only beats cut
  the speech track and keep the picture. `tm done G5`.

<a id="s8"></a>
## S8 Meta copy (CA13)

- `03_wip/copy_vNN.json`, per ad (the main cut, and the short and long cuts when there are any): `{"ads": [{"key"
  (the ad key, also `utm_content`), "ad_name", "video_title", "cta" (Meta's type, e.g. LEARN_MORE), "display_link",
  "url" (with utm_source, utm_medium, utm_campaign, utm_content), "primary_texts", "headlines", "descriptions"
  (5 each, `{"text", "claims": [ids]}`)}]}`, in the ad language. Limits 125 / 40 / 30 characters; any number in a
  text comes from one of its named claims, and so does any promise of results or availability ("guaranteed", "in
  stock", "results in"): the check reads the market language's promise phrases, and when that language has none
  it says so (`promise_warning`): then read every text for promises yourself.
- `tm ad copy check` (its answer carries the copy page's data), `tm done S8`. The copy page shows each text editable
  with its live count and a keep tick, and asks "Do you want to change anything?". Choices made on the page:
  `tm page decision --run R copy --record` writes them as `03_wip/copy_decisions_vNN.json`; choices given in chat:
  write that file yourself (`{"ads": [{"key", "primary_texts": [{"n", "text", "keep"}], ...}], "note"}`). Then
  `tm ad copy accept --run R --file <it>`: the accepted copy is `04_final/copy_vNN.json`. Never only a file: the
  copy goes back to the user.

<a id="s9"></a>
## S9 Deliver

- The final files in `04_final/`: per ad key `<key>_vNN.mp4` (9:16, 1080×1920) and `<key>_thumb_vNN.jpg` (a frame
  with the hook text and the person facing the camera, when there is one), each recorded with `tm record`; copies in
  the user's downloads folder. `tm done S9` needs the accepted copy and those files in the manifest.

<a id="s10a"></a>
## S10a Upload checks and proposal (CA14)

- "Offer the Meta upload" is asked first, at every level. On `skip`, nothing is created: the files and the copy are
  the result.
- **Checks before proposing**, each answer saved in `02_research/`: the Pages the ad account can use; the pixel
  (dataset) of the site: which one, whether it fires, whether the business event arrives.
- **Objective and optimisation event**, 1–2 options with reasons, asked: the business goal, the events the pixel
  really sends, the expected events per week at the budget (about 50 per ad set per week to leave learning). No
  pixel or a silent one: say what it costs and offer to wait. Under Engagement, link-click optimisation with the
  destination "website" was refused ("Performance goal isn't available"); without the destination it was accepted.
- **The ad budget**: ask for the amount and the cadence; never inferred, never taken from an earlier run unasked.
  **The AI disclosure**: show what in the ad is generated (`tm ai-media` lists what the run made) and ask "Do these
  ads contain media created or edited with generative AI?", without a recommendation.
- `05_results/upload_proposal_vNN.json`: `{"ad_account_id", "page_id", "copy" (the accepted copy), "checks": {"pages":
  {"saved", "ids"}, "pixel": {"dataset_id", "fires", "events", "saved"}}, "objective": {"options": [{"objective",
  "event", "why"}], "chosen", "said"}, "budget": {"amount", "cadence" (daily, lifetime), "currency", "said"},
  "country": ["PL"], "audience": "advantage_plus", "placements": "advantage_plus", "names": {"campaign", "adset",
  "ads": {<key>: name}}, "ads": [{"key", "video", "thumbnail"}], "ai_disclosure": {"value" (OPT_IN, OPT_OUT),
  "said"}, "status": "PAUSED"}`. Names say product, test, audience and concept.
- `tm ad upload check` (its answer is the card: the proposal in full, the placement facts, the pixel's cost, the
  paused note), `tm done S10a`. The go-ahead "Go ahead with the PAUSED upload" is asked at every level; `create` is
  refused without the checked proposal. The upload page shows the proposal read-only and records only "go ahead" or
  "skip"; it never creates or activates anything.

<a id="s10b"></a>
## S10b Create the PAUSED ad and read it back (CA14)

- **One upload round:** the Meta MCP cannot read a local file by path. Put the video and the thumbnail in the
  downloads folder, send them to the user (SendUserFile), and call `ads_creative_upload_media`: in the Claude desktop
  app it opens an upload window where the user picks the files; the ids come back in the chat. Create the campaign
  and the ad set while they upload. Use the video only once its status is `ready`.
- Create campaign → ad set → creative → ad, **every one PAUSED** (`status: PAUSED`), or as a draft where the account
  supports drafts. Each creative gets `self_ai_disclosure` from the proposal (it can't be set later). **Never call
  `ads_activate_entity` or any other activation, and never set another status.** Meta has created the objects PAUSED,
  not as drafts, before: say which happened.
- Read every object back, get each ad's preview (`ads_get_ad_preview`), save Meta's answers in `05_results/`, and
  write `05_results/meta_objects_vNN.json`: `{"created_as" (paused, draft), "proposal", "campaign": {"id", "name",
  "status"}, "adset": {...}, "videos": [{"key", "id", "status"}], "creatives": [{"key", "id", "self_ai_disclosure"}],
  "ads": [{"key", "id", "name", "status", "preview_url"}], "answers"}`. `tm ad upload record`: an object that is not
  paused is a stop (pause it now, then record again). `tm done S10b`.

<a id="done"></a>
## Final report

- The ad and its cuts, the thumbnail and the copy (where they are), what was spent against what was approved, every
  decision taken by rule with its data, what was not checked, and the guess notice in a run without TrendsMesh.
- After an upload: how it was created (PAUSED or draft), every id, the preview links, and **how to switch it on in
  Ads Manager** (`tm ad upload record` gives the words). Nothing in this playbook switches it on.
