# MiniMax H3: prompting recipe (checked 2026-11-04)

Sources:
- fal, "MiniMax H3 Prompting Guide + 44 Video Examples": https://fal.ai/learn/devs/minimax-h3-prompting-guide (summary of MiniMax's official base-mode guide)
- RunDiffusion, "MiniMax H3 Prompt Guide": https://www.rundiffusion.com/minimax-h3-prompt-guide
- ComfyUI docs, MiniMax H3: https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native

## Rules
- **Mode:** an image that must be the literal opening frame → first-frame mode (`first_frame_image`, optional `last_frame_image`). An image used only for identity or style → reference mode (`reference_image_urls`, up to 9). Do not mix the two jobs in one image.
- **Order of the prompt:** task → job of each input ("Image 1 is the opening frame") → look → **timed shot list** → sound → exclusions.
- **Timed shot list:** one bracket per beat, one action or camera move per block: `[0 to 3 seconds] Medium shot ... [3 to 9 seconds] Close-up ...`. Up to 15 s in one generation: use it to keep a subject consistent across shots.
- **First frame:** describe the motion, not what is already visible.
- **Identity lock:** list the features to keep ("grey-and-white coat, blue eyes, no collar").
- **Camera language:** "slowly push the camera forward", "subtle handheld shake", "keep the camera fixed".
- **Transitions:** describe them as physical events ("hard cut to a close-up"), not effect names.
- **Exclusions are stated directly:** "Do not show subtitles, added text, watermarks or stickers. No morphing or warping."
- **Audio:** H3 always generates native stereo audio; there is no off switch on Replicate. For organic videos with an in-app trending sound, add "No music, no dialogue; only quiet room sound" and **mute the track in the edit**.

## Native speech (tested 2026-11-05, PB3 P4 take_v03: 15 s, 5 lines, 37 words, 4 hard cuts)
- **Works:** lines in quotes inside the timed shot list come out word for word (Whisper: lines 1–4 exact), one consistent voice across hard cuts and off-screen B-roll, cuts land on the bracket times (scene detection 3.1 / 6.1 / 9.2 / 11.3 s against 3 / 6 / 9 / 11), the product described in words is reproduced well.
- **First frame and reference media do not mix:** `first_frame_image` + `reference_image_urls` is rejected (E006 "First/last frames cannot be combined with reference media"; rejected before generating). With a first frame, describe the product in words; the same rule blocks `reference_audio_urls` for a voice match, so a recurring voice needs a take without a first frame or the ElevenLabs route.
- **Last line (half-whisper):** the user listened and the whole line is there ("And the biscuit she hides that I always find"); it is ~10 LU quieter, and Whisper missed the first words because of that. So a quiet delivery fools the automatic transcript check: when Whisper misses words in a quiet passage, boost and re-check, and treat the transcript as a hint, with the user's listen as the final check. Still keep ≥1.5 s slack after the last line and even the loudness in the edit.
- **Product from words is not 1:1:** the lick mat described only in words came out close but wrong (deep tray with high walls instead of a flat mat with a low lip; ridges centred mid-mat instead of on the top edge; runny instead of frozen yogurt; `showcase/P4_mat_ref_vs_take_v01.png`). A product must enter through an image (see PB3 ANALYSIS round 20).
- **Reference mode for a product (tested 2026-11-05, PB3 P4 take_v05):** opening frame and packshot both in `reference_image_urls`, the opening shot described in detail as "starts from Image 1". The mat came out far closer than from words (flat mat, low lip, suction cups, arcs from the top edge, nubs below), lines 1–4 word for word, the opening shot close to Image 1 but not pixel-exact. **Set `ratio` explicitly** (`"9:16"`): without a first frame the ratio is unknown and the take came out 1344x768 (16:9), unusable for a vertical video.
- **Reference mode at 9:16 (PB3 P4 take_v06, 2026-11-05): the default route for a talking take with a product.** Opening shot practically identical to the host frame, the mat close to 1:1 with the packshot (flat, low lip, arcs from the top edge, nubs below), lines 1–4 word for word, cuts on time (3.0 / 6.2 / 9.4 / 11.4 s). Spec: `runs/03-organic-ai-video/2026-11-05_pet-dtc-proposals/03_wip/P4/take_v06_refmode_h3.json`.
- **Native audio levels vary a lot (PB3 2026-11-06):** a half-whispered line came out ~25 dB below the other lines (P4 v06, 12.0–14.1 s), a 4 s prep shot came out at −48 LUFS with one clack (P5 2a), an 11 s ASMR shot peaked at 0 dBFS (P5 2b). The edit always levels the native track: timed gain on quiet lines, then compressor + limiter + loudnorm to about −14 LUFS (ASMR may stay near −16 to keep its dynamics). Measure a per-second level envelope, since Whisper misses quiet lines.
- **Talking animal (PB3 P2, 2026-11-06):** reference mode with the opening frame, the product packshot and an ElevenLabs voice sample in `reference_audio_urls` gave a husky speaking both lines with clear mouth movement across 4 shots in 12 s ($0.96), as good as ElevenLabs + Kling Avatar v2 lip-sync at about half the cost. The words are not guaranteed (Whisper: "I said" for "They said"), so check the transcript at the gate. Default route for speech since round 33.
- **Speech pace (PB3 M5 PL, 2026-11-06):** native Polish speech came out at ~2.3 words/s and the user found it far too slow for TikTok. Fix without regenerating: speed the whole take up 1.2× in the edit (`setpts=PTS/1.2`, `atempo=1.2`), which keeps the pitch and the lip sync. For new takes, ask in the prompt for "a brisk, energetic TikTok pace, no pauses between sentences" and size the script at about 2.8–3 words/s.
- **`reference_audio_urls` length:** each audio reference must be **2–15 s**; a longer file is rejected before generating ("audio duration 24007 ms, expected [2000, 15000] ms"; no charge expected). Trim the voice sample to ≤ 14 s.
- **Default (user, round 47):** dialogue in the prompt only, no `reference_audio_urls`. In the round-46 test a voice reference made Polish worse (garbled words, an extra sentence) and did not clearly improve English.
- **QA at the video gate:** scene detection for cut times, `tools/transcribe.py` (Whisper) against the script, short-term loudness per line (ebur128), face crops at a few speech frames.

## Replicate parameters (`minimax/h3`)
`prompt` (up to 7,000 characters), `first_frame_image`, `last_frame_image`, `reference_image_urls` / `reference_video_urls` / `reference_audio_urls`, `duration` (4–15 s), `resolution` (`768P` or `2K`; 768P is our 720p default), `ratio` (follows the first frame in image-to-video). Price: **$0.08/s at 768P, $0.13/s at 2K** (`tools/replicate_price.py minimax/h3`, 2026-11-04).
