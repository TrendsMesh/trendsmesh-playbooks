# GPT Image 2: prompting recipe (checked 2026-11-04)

Source: OpenAI Cookbook, "Image generation models prompting guide" (gpt-image-2): https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
Community (unverified starting points): Atlas Cloud, "GPT Image 2.5 JSON prompts for UGC selfies": https://www.atlascloud.ai/blog/tips/gpt-image-2.5-json-prompts-ugc-selfies; YouMind prompt gallery: https://youmind.com/prompts/authentic-smartphone-selfie-closeup-portrait-28787

## Rules
- **Order:** background/scene → subject → key details → constraints. State the intended use ("first frame for a short social video", "product reference photo").
- **Photorealism:** write "photorealistic"; "like an iPhone photo" helps; ask for real texture (fur strands, fabric wear, imperfections); avoid words that suggest studio polish unless it is a packshot.
- **Creator / UGC frames (people talking to a phone; added 2026-11-05 after PB3 P4 host v02 looked staged):** the cookbook rules above are not enough on their own; v02 named "photorealistic, iPhone front-camera frame" but still came out like a stock photo (even studio-soft light, clean empty kitchen, centred symmetric pose, big open-mouth grin, small face in a hips-up shot). Do this instead:
  1. **Copy the look of the trend's evidence first** (PB3 lesson 21): open 2 evidence frames and copy framing (usually chest-up, face fills the middle), camera position (phone propped on a counter or held at arm's length, slightly below or above eye level), light and setting.
  2. **Frame it as a paused frame of a real creator video**, "not a photo shoot and not a stock photo"; the phone is the camera, so no phone in the image.
  3. **Phone optics:** front camera ~24 mm, slight wide-angle distortion at the edges, deep focus, mild sensor noise in the shadows, slightly uneven exposure, a blown-out window.
  4. **Lived-in setting:** name 4–6 everyday objects (dishes, a towel, a treat jar, a sticky note); mixed light sources.
  5. **Imperfections on the person:** loose strands, worn clothes, real skin texture, pores, faint under-eye shadows; "no make-up look".
  6. **Caught mid-action:** mid-word, half-smile, leaning on something; the pet doing something of its own.
  7. **Exclusions:** "No glamorization, no beauty filter, no heavy retouching, no studio lighting, no cinematic lighting or colour grading, no symmetrical posed composition."
  8. Avoid polish words: "bright", "warm smile", "friendly", "natural make-up", "beautiful".
  Community prompt galleries suggest the same levers (phone optics, no beauty filter, a spontaneous moment); none of them tests the levers against each other, so treat them as a starting point and check at the image gate.
- **Reference images:** label each input ("Image 1: product reference… Image 2: …") and say how they combine. For edits: "change only X, keep everything else the same", and repeat the preserve list every iteration.
- **Series consistency:** make one anchor image (character, product), pass it as input for every later frame, restate the key traits each time and add "do not redesign the dog/character".
- **Text in images:** put literal text in quotes, ask for it verbatim and once. For video first frames we keep text out of the image (captions are added in the edit).
- **Quality:** `medium` for frames and packshots (proven in PB1); `high` for dense text or close-up identity work (the cookbook: compare medium and high for close-up portraits before shipping; PB3 P4 host v03: at the same prompt, medium came out over-sharpened with an HDR look and exaggerated skin texture, high looked like a real phone frame, so a person's first frame for a talking video uses `high`, $0.128); `low` for drafts.
- **Sizes:** edges multiples of 16, long:short ≤ 3:1; 9:16 frames at `1152x2048` (Replicate enum), which also suits Veo's 9:16 input.

## Replicate parameters (`openai/gpt-image-2`)
`prompt`, `quality` (low/medium/high/auto), `aspect_ratio` (incl. `9:16`, `1152x2048`, `1024x1536`), `input_images` (list), `background`, `output_format`, `number_of_images` (1–10). Price is not shown on the model page; record actual cost from the dashboard.
