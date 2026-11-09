# Seedance 2.5: prompting recipe (checked 2026-11-06)

Written for the plugin from the handoff's pet-store research (handoff `organic-video_v02`). Each finding keeps the date
it was made. No pet-store take was made with this model: it is prompted as Seedance 2.0 (`seedance-2.0.md`), whose
take passed, and its first real take is checked like any other (QA, contact sheet).

Sources:
- PB3 pet-store research, in the repository under `handoff/organic-video_v02/examples/pet-store-proposals/02_research/models/`:
  - `prices_seedance_tiers_2026-11-06.json` (Replicate `billingConfig`, 2026-11-06): the premium tier's prices;
  - `host_frame_models_v01.md` (2026-11-06, round 26): its rankings and "Seedance 2.5 has the same face block as
    2.0";
  - `seedance_faces_v01.md` (2026-11-05, round 24): BytePlus' asset route names Seedance 2.0 and 2.5 alike.
- PB3 `ANALYSIS.md` round 28 (2026-11-06): the quality tiers (premium only on request) and the price against 2.0;
  `PLAYBOOK.md`, the quality tiers.
- Rankings read 2026-11-06: Artificial Analysis image-to-video with audio
  (https://artificialanalysis.ai/video/leaderboard/image-to-video), Seedance 2.5 1159 (#1); Arena image-to-video
  (https://arena.ai/leaderboard/video/image-to-video, updated 2026-11-05), Seedance 2.5 1488 (#3).

## When the plugin uses it
- **The premium quality tier, only when the user asks for it** (OV6): `bytedance/seedance-2.5`, 720p. It is never
  suggested on its own and is not a `generation.quality_tier` setting: the pack names it as the user's model
  (`user_named: true`, the six criteria answered). At 720p with image inputs it costs about 28 % more than
  Seedance 2.0 ($3.47 against $2.70 per 15 s); with a video input it is about four times as much, so it is given no
  video input.
- **Never with a photoreal face in its inputs**: the same face block as Seedance 2.0 (Replicate E005, `seedance-2.0.md`).
  A host image goes to MiniMax H3 reference mode (`minimax-h3.md`); a person from a description is written in the
  prompt, as for Seedance 2.0. The tricks that hide a face from the check are never used.

## Rules
- **Prompt it as Seedance 2.0** (`seedance-2.0.md`): each reference named by its job and its look locked, the person
  in words, the timed shot list in brackets with each line in quotes inside its bracket, the sound, the look, the
  exclusions. The research found no prompting difference between the two; a finding from the first 2.5 take goes
  here, dated.
- **Inputs:** image inputs only (a first frame or reference images, never both, as for 2.0); no video input.
- **Parameters:** as Seedance 2.0 (`prompt`, `reference_images` or `image`, `duration` up to 15, `resolution`,
  `aspect_ratio: "9:16"`, `generate_audio: true`); read the model's input schema on its Replicate page before the
  first spec, since no 2.5 spec was run.

## Prices (Replicate `billingConfig`, 2026-11-06)
Per second of output video: with image inputs (`model variant=non_video_in`) 480p $0.1028, **720p $0.2312**; with a
video input (`video_in`) 480p $0.4304, 720p $0.9676. A cost line names its tier's criteria as the price file holds
them, for example `model variant=non_video_in, target resolution=720p`: 15 s is $3.47. Read the price again with
`tm tool replicate_price` before a pack: a price older than `pricing.max_age_days` is refused.
