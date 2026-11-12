# Gemini Omni 1.2 Flash: prompting recipe (checked 2026-11-12)

Google's video model with native sound, on Replicate as `google/gemini-omni-1.2-flash`. Create an ad's presenter
table (`skills/create-ad/references/rules.md` CA5) picks it when the exact wording matters. Written for the plugin
from the sources below (issue #95); each finding keeps the date it was made.

Sources:
- The Replicate model page, https://replicate.com/google/gemini-omni-1.2-flash (read 2026-11-12): its README ("What
  you can do", "Inputs that work together", "Usage") and the OpenAPI input schema the page embeds.
- Its price, Replicate's `billingConfig` on the same page, read with `tm tool replicate_price` on 2026-11-12.
- Google DeepMind's prompt guide, linked from the README: https://deepmind.google/models/gemini-omni/prompt-guide/
  (read 2026-11-12; parts of it are written for Omni 1.1).
- The owner's live run of Create an ad on 0.12.0, reported in issue #95 (2026-11-12): two whispered Gemini takes of
  one creator; the native voice came out weak.

## When the plugin uses it
- **The exact wording is needed** (CA5's table): the lines go into the prompt as text and come out as written. Its
  voice is the model's own (native): Replicate's inputs take no audio, so a library voice or a voice sample cannot
  drive its lips. A brand voice or the user's own voice is a MiniMax H3 job (`minimax-h3.md`, `reference_audio_urls`).
- **The casting face as a reference:** the approved casting still goes into `reference_images` ("a character …
  to keep consistent, not as literal frames"), so the face is close to the still, not pixel-exact.
- **A weak native voice** (issue #95): keep the take when the lines and their timing are right, and change only the
  voice with the Voice Changer (`tm tool elevenlabs sts`, CA6), which keeps the timing, so the lips still match.
  A new take, on this model or another, is for wrong lines only.

## Inputs (Replicate's schema, 2026-11-12)
- `prompt` (required, text).
- `image`: a first frame to animate; with `last_frame`, an ending image ("Requires image, up to 10 seconds").
- `reference_images`: up to 6 images "of characters, products, or styles to keep consistent".
- `video`: a video of up to 15 s to edit, the change described in the prompt (`duration` and `aspect_ratio` are then
  ignored).
- `image` (and `last_frame`) cannot be combined with `reference_images` or `video`; `video` takes no image input.
- `duration`: whole seconds, **3 to 15** (default 10). It wins over a length written in the prompt.
- `aspect_ratio`: `16:9` (the default) or `9:16`: set `"9:16"` for a vertical ad.
- `resolution`: `360p`, `720p` (the default), `1080p`, `4k`; 1080p and 4k are upscaled from the base render.
- **No audio input** of any kind, and no `negative_prompt` or `seed`. The output is one video file (24 fps) with its
  sound track.

## Rules
- **Dialogue:** put each line in quotes and name who says it ("The creator says, whispering: \"…\""), and describe
  the ambient sound and music; write "no music" (or "no dialogue") to leave it out (the README).
- **One speaker, one take** (CA4, issue #95): all of one person's lines in one take of up to 15 s, the cuts between
  places written into the prompt as physical events ("selfie at arm's length, then a hard cut to a whispered
  close-up"). Two takes of one person give two slightly different faces, voices and light. When the lines do not fit
  15 s, the next take uses the same reference image and the same voice description, word for word.
- **Cuts:** the model cuts on its own; ask for "one continuous shot" (or "oner") when a shot must not cut.
- **The person:** describe them in words as well (age, hair, clothes, mood), and the voice ("a warm, low, casual
  voice, recorded by the phone's microphone"); never name a real person (CA9).
- **Safety filters:** Google's filters apply to the prompt, the input media and the generated video; a blocked one
  fails with a content error. Every video carries an invisible SynthID watermark.

## What the live run found (issue #95, 2026-11-12)
- The native voice of the whispered takes came out weak (about −22 LUFS). Local Whisper then missed a whispered word
  that was in the take (issue #94): check a quiet take with Scribe before calling a line missing.
- The run's two takes of one creator (a corner window and a whispered close-up) were two generations: plan them as
  one take with the cut in the prompt.

## Prices (Replicate `billingConfig`, 2026-11-12)
Per second of output video: 360p $0.035, **720p $0.105** ($1.58 for 15 s), 1080p $0.155, 4k $0.31. A cost line
names its tier as the price file holds it (`target resolution=720p`). Read the price again with `tm tool
replicate_price` before a plan: a price older than `pricing.max_age_days` is refused.
