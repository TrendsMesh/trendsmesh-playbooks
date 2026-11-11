# Rules CA1–CA15 (spec v0.1, issue #17)

Read before S1 and keep in force to the end. Where the engine enforces a rule, the check is named.

**CA1. Intake confirms persona and output type before any research.** The persona includes what they make.
Length and placements are explicit. Existing assets remove generation steps. Rights to the user's voice and music
are assumed. Nothing that is not live is promised. (`ad_intake_written`)

**CA2. Concepts = model ad + trends, on one page, with a feedback loop.** About 5 model ads (ask first whether the
user wants suggestions or has one; TrendsMesh paid, `origin=ad`, first; else the Meta Ad Library, filtered for
relevance, run time a signal of staying power); trends of any type that fit product, persona and model ad (a good
default: one hook, one format, one topic); sound trends only with a licence for ads, otherwise as inspiration;
organic clips are evidence, never footage. 2–3 concepts, each with its model ad, matched trends (2 evidence videos
each), how they combine, beats, length and why, cost range. The model ad gives the structure of its first seconds,
not its length. On notes: analyse, present again with the changes worked in, ask only what is unclear; never jump
to production on a note. Without TrendsMesh, every model ad and trend is labelled as a guess. (`ad_concepts_checked`)

**CA3. Claims come from the site and the user.** Sources: the product site, the user's context, trend data for trend
facts. Staged data inside the story (a mock-up screen, a trend card) is allowed. The ad copy never invents numbers,
never promises results, and never promises availability. (`ad_claims_checked`, `ad_copy_checked`)

**CA4. The script is a board, sized to the takes.** Scene by scene: time, picture, on-screen text, spoken line,
sound, where the picture comes from. Word budget = seconds × the model ad's words per minute. One take carries all
speech when there is one speaker (15 s ≈ 45 words). Openers that failed: non-visual (desk + laptop), "breaking
news", literal product-category lines, outputs that do not match the persona. (`ad_board_checked`)

**CA5. Models per asset type: suggest, never impose.** Read the model's current prompting guide before writing a
prompt and keep the rules used next to the prompt. Default talking presenter: Gemini Omni (lines as text in the
prompt, a reference image, native voice, up to 15 s per take); alternative: Seedance 2.0. Stills: GPT Image 2.
Generation stays provider-neutral. (`ad_plan_checked`)

**CA6. The voice route is decided in S5.** Native voice of the video model, an ElevenLabs voice (library or the
user's), a 1:1 clone of the user's VO recording, or a clone of a native take for extra VO. When a take has a flaw:
original take > a precise cut of the original (Scribe word times) > a voice clone; the clone only when the line must
change. A clone patched into a phone or street take needs its ambience and a phone-mic colour, and sits better on a
scene cut. The agent cannot hear: syllable-level cuts are confirmed by the user before they ship. (`ad_plan_checked`)

**CA7. Cost and approvals.** Every paid step shows prompt, parameters and price (with the check date) first. The
plan's yes covers the pre-video amount, the storyboard's the video; Hands-off spends only inside the budget given
at intake. **A video is never regenerated automatically**: failed QA goes to the user with options (cut, re-take,
clone, accept). Money in USD, with the rate when the account currency differs. (`plan`, `storyboard`, the paid
guard)

**CA8. Staged gates; raw assets are always shown raw.** Every generated batch goes back as a gate (a page, or in
chat until the pages exist), never only as images in chat without the check-in. Every generated video goes back raw
with its transcript and QA notes and is accepted before the edit uses it.

**CA9. Generation craft.** One character = one take. Describe people in text; never name real people. Anti-slop
camera: handheld, phone look, natural light. Silent reactions keep the mouth closed. Stills agree the look; they are
references for video only when the user says so. Reusing a model ad's creator look: a frame may serve for framing,
light, camera, wardrobe style and setting only; the person must be a different, non-identifiable person (new face,
hair, build), logos and signage replaced; write the guard into the prompt and offer 2–3 visibly different people.

**CA10. Edit standards.** Overlays chosen to fit the ad's style and proposed on the storyboard (not a fixed set). A
present person is full frame; screen beats full frame, the person absent or voice only; text-heavy screens never in
a small card. Windows cover neither face nor chin and never collide with the captions. Hook text at the top in the
first second. Captions in one fixed band, 3 words at most, timed from Scribe words, brand words spelled right. Brand
elements match the site (logo, font, colours); tool icons where tools are named. Screen beats on a blurred, slowly
scrolling view of the product's site. A ~2 s logo sting with the music ringing out. The picture ends at or before the
take's last frame. Shots at least ~1.5 s; a short dissolve between clips of the same presenter; each line's picture
inside its own shot. Transition sounds from a small library, a cue list mixed after the render.

**CA11. Edit QA before every showing.** Motion at every cut, scene detection inside generated takes. Stills after
every layout change; caption collisions with every overlay. Scribe on the take and on the edit; a word about 2× its
expected length is a possible hidden repeat; never clear a repeat on a re-transcribed slice; compare the edit's audio
with the take. ~80 ms of natural pause at every speech join; overlays end one frame before a cut. Generated logos
and text checked letter by letter. Loudness: −14 LUFS integrated, true peak ≤ −1.5 dBFS.

**CA12. Review.** Versions side by side, each labelled with a pick; notes pinned to the playing version's time.
Audio-only fixes (a stutter, a long pause) are free under screen-only beats: cut the speech track, keep the picture,
map take time to edit time.

**CA13. Meta copy goes to a check-in.** Per ad: 5 primary texts (≤ 125 characters), 5 headlines (≤ 40), 5
descriptions (≤ 30), CTA, display link, URL with UTM (`utm_content` = the ad key), ad name, video title. Claims follow
CA3. Nothing is uploaded before the copy is accepted. (`ad_copy_checked`)

**CA14. The Meta upload is offered, proposed in full, and created PAUSED.** Checks before proposing: the Pages the
ad account can use; the pixel (dataset) of the site, whether it fires, whether the business event arrives. Objective
and optimisation event decided per campaign, 1–2 options with reasons, asked (no fixed default): the business goal,
the events the pixel sends, the expected events per week at the budget (about 50 per ad set per week to leave
learning; a shallower event with volume, the deeper one tracked from day one, is the usual way). No pixel or a silent
one: say what it costs (clicks + UTM only) and offer to wait. Two to five text variants need Awareness, Engagement,
Leads or Sales; Traffic takes one. The proposal lists everything in full (ad account, Page, names, objective, event,
budget, country, audience, placements, video, thumbnail, all copy, CTA, URL, AI disclosure). The budget is never
inferred; the AI disclosure is the advertiser's decision. Placement facts go into the proposal. After the go-ahead:
create PAUSED (or a draft, and say which), read back, preview, record every ID. **Activation and spend are not part
of this playbook** (issue #46). Names stay readable. (`ad_upload_proposed`, `ad_upload_recorded`)

**CA15. Pages, language, assets, progress.** Pages and summaries in the chat language; ad text and speech in the ad
language. Never an asset by a bare code. Never overwrite (`_vNN`). Every asset in the manifest with source, prompt,
model and cost (`tm record`; paid calls record themselves), every user decision through `tm decide`. Long steps
show progress.
