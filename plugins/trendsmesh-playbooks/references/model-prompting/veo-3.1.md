# Veo 3.1 / Veo 3.1 Fast: prompting recipe (checked 2026-11-04)

Sources:
- Google Cloud blog, "The ultimate prompting guide for Veo 3.1" (2025-10-15): https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- Vertex AI, video generation prompt guide: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide

## Rules
- **Formula:** [Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]. Name the shot and the camera move (static, push-in, dolly, tracking, close-up, shallow depth of field).
- **Be specific about the subject** ("an adult Siberian husky", not "a dog").
- **Image-to-video:** the actions described must fit the subjects visible in the start image. Keep change subtle within one short clip (PB1 lesson 13: big changes go across cuts, not inside a clip).
- **Audio:** state whether you want it; audio goes in separate sentences (`SFX: …`, `Ambient noise: …`, dialogue in quotes after "says"). For organic videos with a trending sound attached in the app, we generate **without audio** (`generate_audio: false`): cheaper and no clash.
- **Negative prompt:** list unwanted things as nouns ("text, watermark, extra legs"), not "no …".
- **Timestamps** (`[00:00-00:02] …`) can direct several shots in one generation; not used yet.
- **Reference images (ingredients):** on Replicate only `google/veo-3.1` (not Fast) has `reference_images`, and only for 16:9. For 9:16 we keep consistency through first frames made from one anchor image (GPT Image 2 `input_images`).

## Replicate parameters (`google/veo-3.1-fast`)
`prompt`, `image` (start frame; ideal 720x1280 for 9:16), `last_frame` (end frame), `duration` (4, 6, 8), `resolution` (720p, 1080p), `aspect_ratio` (16:9, 9:16), `generate_audio` (default true), `negative_prompt`, `seed`.

## Cost
Not shown on the Replicate model page. PB1 estimate: about $0.80 per 8 s at 1080p without audio. Confirm in the Replicate dashboard before a gate; record the actual cost in the manifest.

## Alternative
`kwaivgi/kling-v2.5-turbo-pro`: `start_image`, `end_image`, `duration` 5 or 10, `negative_prompt`. Fallback when a Veo shot fails twice.
