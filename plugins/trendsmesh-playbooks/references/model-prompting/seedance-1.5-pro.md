# Seedance 1.5 Pro: prompting recipe (checked 2026-11-06)

Written for the plugin from the handoff's pet-store research (handoff `organic-video_v02`). Each finding keeps the date
it was made. No pet-store take was made with this model: the rules below are the research's, and the first real
take is checked like any other (QA, contact sheet) before the tier is trusted.

Sources:
- PB3 pet-store research, in the repository under `handoff/organic-video_v02/examples/pet-store-proposals/02_research/models/`:
  - `prices_seedance_tiers_2026-11-06.json` (Replicate `billingConfig`, 2026-11-06): the budget and premium tiers'
    prices;
  - `upscale_models_v01.md` (2026-11-06, round 29): its native 1080p against 720p with an upscale.
- PB3 `ANALYSIS.md` round 28 (2026-11-06): the quality tiers, the user's correction the same day (not for ASMR or
  anything sound-led), the inputs and the 12 s limit; `PLAYBOOK.md`, the quality tiers.
- The pet-store pack `handoff/organic-video_v02/examples/pet-store-proposals/03_wip/packs/packs_v03.md` (2026-11-06):
  Seedance 1.5 Pro without audio priced as P3's budget alternative (two calls, about $0.34).
- Rankings read 2026-11-06 (`ANALYSIS.md` round 28): outside the top 20 of both Artificial Analysis image-to-video
  (https://artificialanalysis.ai/video/leaderboard/image-to-video) and Arena image-to-video
  (https://arena.ai/leaderboard/video/image-to-video).

## When the plugin uses it
- **The budget quality tier** (OV6, `generation.quality_tier: budget`): `bytedance/seedance-1.5-pro` for formats
  with **no speech**, no need for exact precision and where the sound does not matter: B-roll, mood shots under
  music, a narrated video whose voice is added in the edit.
- **Never for a sound-led format** (ASMR, anything where the native sound carries the video): its native audio is
  weak (the user's correction, round 28). Sound-led formats go to MiniMax H3, Seedance 2.0 or Veo 3.1; the pack
  check refuses the budget tier for a sound-led pack.
- **Never with a photoreal face in its inputs**: it is a Seedance model, and the pack check refuses any Seedance model
  for a pack with a host image (Replicate E005, `seedance-2.0.md`). A host image goes to MiniMax H3.
- The agent suggests the tier from the format and the budget; the user decides.

## Rules
- **Inputs:** a first frame and optionally a last frame; **no reference images**. The product enters only through
  the first frame, made from the packshot with GPT Image 2 (`gpt-image-2.md`) and picked at the images check-in.
- **Length:** 4 to 12 s per call. A longer section is two calls (two items of the pack, each with its own line),
  cut together in the edit; keep the same first-frame look and the same description in both prompts.
- **Prompt:** describe the shot from the first frame on: the camera (phone, angle, framing, movement), the action
  in plain steps, the light, the look ("real, unedited phone footage, not an advert"), and the exclusions ("Do not
  show subtitles, captions, added text, watermarks or stickers. No morphing."). No dialogue: the budget tier is for
  videos without speech.
- **Sound:** native audio is optional and priced apart. Under music or a narrator, generate **without audio** (half
  the price); with audio only when the scene's own sound is wanted and it does not lead the video.
- **Parameters:** read the model's input schema on its Replicate page before the first spec (the research priced
  the model and read its inputs; it made no take), with 9:16 and the pack's resolution (720p by default).

## Prices (Replicate `billingConfig`, 2026-11-06)
Per second of output video: 480p $0.025 with audio, $0.013 without; **720p $0.052 with audio, $0.026 without**;
1080p $0.12 with audio, $0.06 without. A cost line names its tier's criteria as the price file holds them, for
example `model variant=without_audio, target resolution=720p`. A 12 s take at 720p is $0.62 with audio and $0.31
without; native 1080p with audio for 12 s is $1.44, against 720p plus Pruna's upscale ($0.24 for 12 s,
`p-video-upscale.md`). Read the price again with `tm tool replicate_price` before a pack: a price older than
`pricing.max_age_days` is refused.
