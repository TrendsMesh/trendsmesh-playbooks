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
- **The brand's font and logo** from the product's site, before the card: `tm tool site brand --run R <the site>`
  (`--brand <name>` when the address does not say it) reads its style sheets and pages in the user's browser and
  keeps, in `02_research/brand/`, the files the edit can draw: the fonts it uses most (its own files, or the same
  family from Google Fonts) and its logo (images and SVGs marked as a logo, those that name the brand first:
  `names_brand`; another may be a customer's), with a PNG of each. `02_research/brand_vNN.json` lists them. Show the
  font's name and the logo on the card and say where each came from; a font the site serves itself may be licensed
  for the web only, so ask whether the brand's licence covers its ads. What it could not take (`missing`) is asked
  in question 4: the logo (SVG, or a PNG with transparency) and the font's TTF or OTF.
- **Not live yet** (early access, a waitlist): warn now; `intake.live: false` and `intake.not_live` say what it is.
- **The two languages** on the same card, filled from the defaults ("Working language: Polish · Market language:
  Polish"): `languages: {working, market}` as tags (`pl`, `pt-BR`). The working language is for the cards and
  pages, the market language for the ad's copy, voice-over, captions and on-screen text.
- Write the answers file (the config's shape, plus `level`), `tm config write --run R --answers <file>`, `tm config
  check --run R`.
- **The asset inventory**, `03_wip/assets_vNN.json`: `{"earlier_runs_checked": true, "assets": [{"file", "kind"
  (music, voiceover, footage, broll, product_shot, logo, font, brand_guide, past_ad, earlier_run), "usable":
  true|false, "replaces": <asset type or null>}]}`. Each usable file removes a generation step (say which); a
  voice-over recording fixes the voice route. The brand's logo and font are always listed (the files from the site
  or the user's; `usable: false` when there is none after asking). Then `tm done S0`; the intake card is the
  check-in after it.

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
  never footage. Save each MCP answer in `02_research/` and summarise large answers with a script, never read them
  whole. **Each TrendsMesh trend a concept uses has its card saved before the check**: its `get_trend` answer, with
  `tm trends ingest --run R --tool get_trend --input '{"trend_id": "<id>"}' --file <the answer>`, which writes
  `02_research/trend_<id>.json` (this run does not save answers by itself); `tm ad check concepts` names each card
  that is missing.
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
  15 s), also when the speaker is in two places: the cut between them goes into the take's prompt. Avoid the
  openers that failed (rules.md CA4). `tm ad check board`, `tm done S4`.

<a id="s5"></a>
## S5 Production plan and its cost (CA5 to CA7)

- Read each model's prompting guide first (`../../references/model-prompting/`; a model without one: find its
  current guide, save it with its date, and keep the rules next to the prompt). Live prices: `tm tool
  replicate_price`, saved in `02_research/` with the date.
- `03_wip/production_plan_vNN.json`: `{"voice_route" (native, elevenlabs_voice, user_vo, clone_take), "lines":
  [{"item", "type" (an asset type: presenter, hook_scene, product_shot, still, slide, animation, music, sfx, voice,
  upscale, transcription), "stage" (pre_video, or video for the takes, priced again at G3), "model", "alternative",
  "cost", "budget" (ai_usd for Replicate, voice_credits for ElevenLabs), "price_file", "checked" (the price's
  date), "calls" and "cost_per_call" (a line of several paid calls), "seconds" (a music take's length)}]}`. A type
  the user's own file replaces has no line: say what the file replaces.
- **A line of several calls:** `"calls": N, "cost_per_call"` runs N calls under the line's one yes, each with its
  own prompt (casting: one prompt per person), and `cost` is their total; each call runs at `--cost <cost_per_call>`,
  and the engine refuses call N + 1. Without `calls` a line is one call.
- **Music from ElevenLabs is priced by the second:** `tm ad prices --run R` saves ElevenLabs' dated price table as
  the line's price file; the line gives `seconds` (one take's length) and costs at least the seconds at the model's
  rate (`music_v2_5` was billed about 77.5 credits a second, five times the docs' "900 a minute"), a take a call.
  Never take Refresh an ad's 220 credits a take: that was a different job. A `voice` line is the
  ElevenLabs model (`eleven_v4` unless the user picks another, `../../references/model-prompting/eleven-v4.md`)
  and its cost the lines' characters at that model's rate (0.5 credits a character for v4, 1 for
  `eleven_multilingual_v2`); the lines write numbers, dates and percentages out as words in the market's
  language, which the take is recorded in (`language_code`).
- **A model the user names is their choice only when it is plain:** a line made from the user's own words for a
  model (a pick, a change, a new take) keeps those words in `user_named`. When they don't name one model exactly
  ("Gemini Sequence 2.0" when no such model exists), ask one short question before any paid call ("Do you mean
  Seedance 2.0?") and keep their answer in `model_confirmed`; the paid-call guard refuses the line until then, and
  refuses a call whose model (the spec's, or ElevenLabs' `--model`) is not the line's.
- **The talking person** (lines of type `presenter`: the casting at `pre_video`, the take at `video`) comes from CA5's
  table, by situation: ask the user which applies before any casting, and write `"presenter": {"situation"
  (described, specific_person, own_voice, exact_wording, fallback), "user_choice" (true when the user picked another
  model than the row's), "why" (the fallback only: what the review showed)}`. Each take line may name its `speaker`
  (the board's). With **Seedance** (a person from a description), say before the casting that a casting face can't
  be used: the person is cast from a description in the prompt, and the plan has no casting line. One take per
  speaker whose lines fit one take (CA4).
- **The talking person is chosen on the plan's page** (issue #100), not only in chat. Before the plan's check-in,
  read today's price of each row's model: `tm tool replicate_price --run R bytedance/seedance-2.0 minimax/h3
  google/gemini-omni-1.2-flash kwaivgi/kling-avatar-v2` (free), and name the file as `presenter.price_file`. Write
  the situation that fits best as `presenter.situation`. The page shows CA5's rows, your situation first, each with
  its model, what it needs (a description, a face, a voice sample, the lines as text) and its price for a 15 s take,
  and the user picks the situation and the model (the row's own, or another of the table's; the fallback only once a
  review asked for it). `tm page decision --run R plan --record` (or `board_and_plan`) writes a pick that changes the
  plan as the next `production_plan_vNN.json` (`files.plan` in its answer): `presenter.situation`, and
  `"user_choice": true` with `model` when the model is not the row's. Rewrite the take lines (and the casting: none
  for Seedance) to the pick in that version, `tm ad check plan` it, and ask the plan's yes again (`tm decide plan
  approve --change` after the user's yes, on the rebuilt page or in chat). A pick left as the plan has it writes
  nothing. Without a page, the chat card lists the same rows with their prices.
- `tm ad check plan` re-plans the money: its pre-video lines; it refuses a talking person without its situation, a
  take on another model than the row's (unless the user chose it), the fallback without what the review showed, a
  casting for Seedance, and two takes of one speaker whose lines fit one. `tm done S5`. The check-in is "Confirm the
  production plan and its cost" (at Just the big calls on one card with the script-board), on the run page like
  every check-in: its ask written (`pages.md`, `03_wip/ask_plan.json`), `tm page build --run R --ask <it>`, then its
  card in chat with each line's cost and the price's date, even when the user says not to ask: the user confirms once
  per asset type; a new type or a model change later is a new plan version and asks again. After the yes, `tm
  budget approve --run R ai_usd <the pre-video ai_usd total>` (and `voice_credits`). Hands-off: the intake's budget
  is the yes; a plan above it waits for the user.

<a id="g1"></a>
## G1 First visual output (CA8, CA9)

- What the ad type needs first: presenter casting (2–3 visibly different, non-identifiable people, one prompt each
  under one line of `calls`; the CA9 guard in the prompt when a model ad's look is reused; none for Seedance, which
  cannot use the face: the plan said so), stills or slides, or a test frame. Each paid call: `tm tool replicate_run
  --run R <spec> --name <the plan's item> --cost <its line's cost a call>` (the gate page shows the outputs of the
  item's latest run). Show the batch raw, side by side, on the gate (`pages.md` "Gate"); never only as images in chat.
  `tm done G1`, then the check-in.

<a id="g2"></a>
## G2 Audio

- Music (the user's, the config's `audio.music_source`, or generated), SFX takes and the transition sound.
  ElevenLabs calls through `tm tool elevenlabs ... --cost <credits> --out 03_wip/audio/<the plan's item>_vNN.mp3`:
  the engine runs a music or voice take only as a line of the checked plan, at its cost a call. A `music_v2_5` (or
  `music_v2`) plan is chunks, `{"chunks": [{"text": "[Intro] warm, bright", "duration_ms": 10000, "positive_styles":
  ["upbeat pop", "no vocals", ...]}]}`, never music_v1's `positive_global_styles` and `sections`; its seconds at the
  rate must fit the line, or nothing is sent. A take whose cost ElevenLabs does not report is booked at its length
  at the rate, and a take over the approved amount stops the run for the user. The gate shows each take to listen
  to. `tm done G2`.
- **Sound effects come from the plugin's small set**, never made up in ffmpeg (no pink-noise whoosh, no sine click):
  `tm tool sfx_fetch --run R --list` shows it (whoosh, sweep, click, pop, notification) with its licence, the Mixkit
  Sound Effects Free License (free in ads, no credit). `--effect <name>` (again for each, or `--all`) says what it
  fetches, and stops; after the user's yes, `--yes` fetches them into the workspace's `library/sfx/` once and copies
  them into `02_research/sfx/`, where the edit's sound cues name them. Another Mixkit effect: `--search <words>`,
  then `--mixkit <number> --page <its page>`. One Mixkit does not have: ElevenLabs Sound Effects, `tm tool
  elevenlabs sound-effect --run R --text "<what it sounds like>" --seconds <s> --cost <credits>`, for credits: a plan
  line of type `sfx` (its price from ElevenLabs' price page, saved with its date), after the yes.

<a id="g3"></a>
## G3 Filled storyboard and the paid video (CA7, CA8)

- Build the edit's screens before any paid video: a real frame per scene, the chosen audio, and **a placeholder
  take** (the creator still with a slow zoom), rendered whole with `tm tool ffmpeg`, as the edit is (S6). Check the
  stills: text-heavy screens must not sit small inside a card.
- **A screen of the product's site is the plugin's capture**: `tm tool site capture --run R <page> --name <what it
  shows>`, 1080×1920 at a device scale of 2 by default (`--scale 3` for a small element), or the element itself
  (`--clip X,Y,W,H`, its box in CSS px from the browser: `getBoundingClientRect()` plus the scroll): the next
  `03_wip/site_<what>_vNN.png`. Draw it at most at its own size, never scaled up.
- `03_wip/storyboard_vNN.json`: `{"frames": [{"scene", "file"}], "placeholder_render", "audio": {...}, "videos":
  [{"item", "model", "prompt" (exact), "params", "prompt_rules" (the guide used), "cost", "budget", "price_file",
  "checked", "speaks" (optional: true when the take says the lines, false when its voice comes in the edit; left
  out, it follows the voice route: native and clone_take speak)}]}`; an ad without video: `"videos": []` with
  `no_video_reason`. One character = one take: one speaker's lines in one take, the cuts between places written into
  its prompt ("selfie, then a hard cut to a whispered close-up"); lines over the model's length go on in a next take
  with the same image and the same voice description, word for word.
- `tm ad check storyboard` re-plans the money with the videos, so the plan's yes no longer covers it. `tm done G3`.
  The check-in "Approve the filled storyboard and the paid video" shows the storyboard scene by scene with the exact
  prompt and price; on the yes, `tm budget approve --run R ai_usd <the new total>`.

<a id="g4"></a>
## G4 Takes (CA7, CA8, CA11)

- Each take: `tm tool replicate_run --run R <spec> --name <the storyboard's item> --cost <its line>`; an unfinished
  take is resumed for free (`--resume`), never run again. The engine refuses a video before the storyboard's yes and
  a second take of an item the user did not ask for.
- **Every take goes back raw** on the gate with its transcript and QA notes: `tm tool take_qa --run R <take> --lang
  <market language> --script <its lines, one a line> --brackets <the board's cut times>` (cuts, the transcript,
  pace, loudness, contact sheet; leave `--script` out for a take that does not speak) and ElevenLabs Scribe word
  timestamps (verbatim, keeps repeats; Whisper hid a repeat and ran early): `tm tool elevenlabs scribe --run R
  <take> --cost <credits>` (about 330 credits a minute, from the `voice_credits` budget), then the QA again with
  `--scribe <its file>`. `tm done G4` needs every take of the storyboard made and QA'd (`ad_takes_checked`).
- **A line is missing only when Scribe says so** (issue #94). Whisper's silence filter drops a quiet or whispered
  line, so `take_qa` hears a line it missed again, that part levelled to the take's speech level and without the
  filter; a line still not heard is "not missing yet", and the answer names the Scribe call and its credits. Never
  tell the user a line is missing, or propose a paid re-take for it, before Scribe's words are in the QA.
  `cut_offsets` gives each cut against its nearest board mark, then the marks with no cut.
- The engine judges each take (`tm.create_qa`, the gate's QA notes): it **fails** on a transcript under the
  threshold, a loudness outside the usable range, or a word heard twice in a row that the lines say once (a
  stutter); its **findings** are a word lasting about 2× its expected length (a possible hidden repeat: listen
  there), internal cuts (keep each line's picture inside its own shot) and a slow pace.
- **A failed take is never regenerated automatically**: `takes accept` is refused while a take fails, until
  `fails_qa` was recorded after its latest QA (the stop for the user). The options: a precise cut of the original
  (Scribe times), a voice clone of the line (only when it must change), **a voice change when only the voice is
  weak** and the lines and timing are right (`tm tool elevenlabs sts --run R <take> --voice-id <a voice from tm tool
  elevenlabs voices> --cost <credits>`, about 1,000 credits a minute: the take's own audio in another voice, timing
  kept, so the lips still match; the edit lays it under the take's picture with the take's sound muted; never a new
  text-to-speech reading under the mouth), a new take (only when the lines are wrong; its cost first; on their yes
  `tm ad redo --run R --item <item> --note "<their words>"`), or accept it as is (`tm decide takes accept --change`
  on their word).
- **Rejected spend is kept apart:** `tm ad redo` books the take it replaces as rejected; a take the user turns down
  that is not made again under its item (a new line replaces it, or it is dropped) is booked with `tm ad reject --run
  R --item <item> --note "<their words>"`.

<a id="s6"></a>
## S6 Edit (CA10)

- A data-driven edit built with `tm tool ffmpeg` (never Remotion): a timeline (scenes, take segments with a time
  map, overlays, captions, sound cues) turned into one ffmpeg run. Overlays are those proposed on the storyboard.
- **The text is two layers**, as in organic video's edit: **captions** under the speech (groups of 2 to 4 words from
  its word times, at the bottom) and **overlays** (the hook at the top from 0 s, a number, a tag, a code chip, the
  logo on the end card). Both in the brand's font (`drawtext` with `fontfile=` one of its files in the inventory),
  the end card with the brand's logo (its PNG), never a system font or the name as plain text unless the inventory
  says there is none. Keep them off the faces, off the windows and off each other (CA10).
- **Write what the edit draws**, bottom to top, beside it: `03_wip/edit_layers_vNN.json` (the edit's NN), `{"layers":
  [{"id", "kind" (picture, caption, overlay), "start", "end", "box": [x, y, w, h], "src", "from", "crop", "on"}]}`
  in seconds of the edit and px of its frame: each picture (a take, a window, a scene card, a capture) with its
  `src`, the second of it shown at `start` (`from`) and the part of it shown (`crop`, px of the source; a picture
  with no `box` fills the frame), each caption and overlay with the box it is drawn in, and `on` naming the layer
  it is drawn on on purpose (a chip on its card).
- Render it as `03_wip/edit_mix_vNN.mp4` (`tm tool ffmpeg --run R --name edit_mix --ext mp4 -- ...`), then **the
  loudness pass through the plugin**: `tm tool deliver finish --run R 03_wip/edit_mix_vNN.mp4`, with `--gain
  START-END:+DB` on a quiet line (a whisper) and `--compress` to even the speech: it limits, levels to the run's
  −14 LUFS with the true peak under −1.5 dBFS, and writes the edit's next version, `03_wip/edit_vNN.mp4`. Never set
  the level by hand. `tm done S6`.

<a id="s7"></a>
## S7 Edit QA (CA11)

- Before every showing: motion at every cut, scene detection inside generated takes, stills after every layout
  change, caption collisions, Scribe on the take and the edit (compare the two to tell an edit bug from a model
  stutter), ~80 ms of pause at speech joins, generated logos and text letter by letter, −14 LUFS integrated and true
  peak ≤ −1.5 dBFS.
- Measure the latest edit like a take: `tm tool take_qa --run R 03_wip/edit_vNN.mp4 --lang <market language>
  --script <the board's lines>`, and its layers: `tm tool layer_check --run R 03_wip/edit_vNN.mp4 --layers
  03_wip/edit_layers_vNN.json` finds a caption or an overlay over a face (in the take's own frames, through the
  window's crop and box), two layers over each other, and a still scaled up. A collision is moved in a new version
  (S6) before anything is shown: the user never sees it. Write what was checked next to the version,
  `03_wip/edit_qa_vNN.json`: `{"edit"
  (the latest edit), "qa" (its latest take_qa file), "checked": [{"check" (cuts, take_scenes, stills, captions,
  speech, joins, overlay_ends, text), "result" (ok, not_applicable, problem), "note" (what you looked at)}]}`, one
  row per check (`captions`: what the layer check found; `text`: the brand's font and logo, letter by letter).
  `tm ad check edit --run R --file <it>` refuses an edit no `tm tool deliver finish` wrote, one whose latest layer
  check found a collision, a loudness more than 1 LU off the target, a true peak above the limit, a transcript under
  the threshold or a stutter in an edit with lines, a check left out, and a `problem` (fix it in a new version, S6,
  and QA that). `tm done S7`; `review accept` needs the same check on the
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

- The ad and its cuts, the thumbnail and the copy (where they are), what was spent against what was approved (`tm ad
  costs`: per budget, and the spend on rejected takes on its own line), every
  decision taken by rule with its data, what was not checked, and the guess notice in a run without TrendsMesh.
- After an upload: how it was created (PAUSED or draft), every id, the preview links, and **how to switch it on in
  Ads Manager** (`tm ad upload record` gives the words). Nothing in this playbook switches it on.
