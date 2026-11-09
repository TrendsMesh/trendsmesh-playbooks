# Seedance 2.0: prompting recipe (checked 2026-11-06)

Written for the plugin from the handoff's pet-store research and tests (handoff `organic-video_v02`), which
read the sources below. Each finding keeps the date it was made.

Sources:
- PB3 pet-store research, in the repository under `handoff/organic-video_v02/examples/pet-store-proposals/02_research/models/`:
  - `seedance_faces_v01.md` (2026-11-05, round 24): the face check and BytePlus' asset route;
  - `seedance_faces_v02.md` (2026-11-06, round 25): the block confirmed by other users;
  - `speech_models_v01.md` (2026-11-05): inputs, the 15 s limit, price and rankings;
  - `host_frame_models_v01.md` (2026-11-06, round 26): rankings and prices beside MiniMax H3;
  - `prices_2026-11-06.json`, `prices_seedance_tiers_2026-11-06.json` (Replicate `billingConfig`, 2026-11-06).
- The tested spec: `handoff/organic-video_v02/examples/pet-store-proposals/03_wip/P4/take_v07_seedance_textcreator.json`
  (2026-11-05, round 23), and its manifest rows.
- BytePlus ModelArk, Seedance 2.0 and real or virtual portraits: https://docs.byteplus.com/en/docs/ModelArk/2333565
  (read 2026-11-05).
- ComfyUI docs, Seedance 2.0: https://docs.comfy.org/tutorials/partner-nodes/bytedance/seedance-2-0 ; ComfyUI issue
  #13524: https://github.com/Comfy-Org/ComfyUI/issues/13524 ; Adobe Community (an Adobe employee's accepted answer):
  https://community.adobe.com/questions-404/reference-content-can-t-include-real-human-faces-when-using-seedance-2-0-and-seedance-2-0-fast-1631867
  (all read 2026-11-06).
- Rankings read 2026-11-06: Artificial Analysis image-to-video with audio
  (https://artificialanalysis.ai/video/leaderboard/image-to-video), Seedance 2.0 1135 (#3); Arena image-to-video
  (https://arena.ai/leaderboard/video/image-to-video), Seedance 2.0 1478.

## When the plugin uses it
- **The top quality tier** (OV6): `bytedance/seedance-2.0`, 720p, $0.18/s ($2.70 per 15 s).
- **A person generated from a description** (no specific influencer, OV6 round 27): Seedance 2.0 first, with the
  person written in the prompt and the product (and a pet) as reference images.
- **Never with a photoreal face in its inputs.** Seedance 2.0 (and 2.5) checks every input image for a realistic
  human face before it reads the prompt, and refuses one, an AI-made face included: Replicate error E005 "flagged as
  sensitive", in about 5 s, no output (pet store P4 take_v05 and v05b, 2026-11-05; the same input fails again). A
  host image goes to MiniMax H3 reference mode instead (`minimax-h3.md`). The BytePlus asset library is the
  official route for a portrait and is not used (round 25); the tricks that hide a face from the check (grids,
  banners, crops) are never used.

## Rules
- **Inputs:** a first frame (`image`) **or** reference images (`reference_images`, up to 9), never both; up to 3
  `reference_audios` (at most 15 s in all) to lip-sync to a given voice (2026-11-05). With references, describe the
  opening shot in words, as "starts from [Image 1]" or as a full description.
- **Name each reference by its job** in the prompt: "[Image1] is the product, a lick mat; reproduce it exactly as in
  [Image1] in every frame", "[Image2] is the dog: keep him exactly as in [Image2]". Then lock its look: shape,
  proportions, pattern, colour, "do not change …".
- **The person in words:** age, skin, eyes, hair, clothes, mood, "a real person, not a model", and "described in
  words only (no photo of her is given)". The person is new in each generation: a recurring host cannot be locked
  (her frame cannot go back in as a reference), so a recurring host is an H3 job.
- **Order of the prompt** (the take that passed, 2026-11-05): the task ("a vertical '…' video; a woman talks
  straight to the camera like a creator filming herself") → the person in words → the opening shot (phone, angle,
  framing, setting with everyday objects, light) → each reference's job and its identity lock → a **timed shot
  list** in brackets (`[0 to 3 seconds] … [3 to 6 seconds] Hard cut to …`), each line of speech in quotes inside its
  bracket → sound → the look ("real, unedited phone footage, not an advert") → exclusions ("Keep the frame clear of
  subtitles, on-screen text, logos and stickers. Faces, hands, the dog and the mat keep their shape.").
- **Speech:** lines in quotes inside the brackets came out all spoken, the quiet last line included, in one voice
  across the cuts (take v07: 5 lines, 15 s). Size the script as for any take (2.8 to 3 words a second, 1.5 s after
  the last line).
- **Sound:** "one natural, casual speaking voice recorded by the phone's own microphone, the same voice throughout …
  not a voiceover", the scene's own sounds under it, "No music" when a trending sound is added in the app.
- **Parameters:** `prompt`, `reference_images` or `image`, `duration` (up to 15), `resolution` (`480p`, `720p`,
  `1080p`, `4k`; 720p is the plugin's default), `aspect_ratio: "9:16"`, `generate_audio: true`.

## What the test found (pet store P4 take_v07, 2026-11-05, $2.70)
- Passed the face check with no human photo in the inputs (the lick-mat packshot and the husky anchor only).
- The product closest to 1:1 of every test (arcs from the top edge, the nub grid, the suction cups), all 5 lines
  spoken, a consistent creator across the cuts, a natural phone look.
- Limits, to check at the video check-in: cut times drift by up to about 1.3 s from the brackets (2.7 / 6.4 / 10.3 /
  12.3 s against 3 / 6 / 9 / 11); an extra product may appear (the mat on the counter in the opening shot); the
  audio is quieter (−18.6 LUFS: the edit levels it); the take came out 720×1280 (9:16; the edit renders it at 1080×1920).

## Prices (Replicate `billingConfig`, 2026-11-06)
Image inputs (`model variant=non_video_in`): 480p $0.08/s, **720p $0.18/s**, 1080p $0.45/s, 4k $1/s; with a video
input (`video_in`) 480p $0.10/s, 720p $0.22/s, 1080p $0.55/s, 4k $1.25/s. A cost line names its tier's criteria as
the price file holds them, for example `model variant=non_video_in, target resolution=720p`. Seedance 2.5 (the premium tier, only on request): $0.2312/s at 720p, with the same face block. Read the price again
with `tm tool replicate_price` before a pack: a price older than `pricing.max_age_days` is refused.
