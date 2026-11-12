# Model prompting recipes and model choice

Before writing prompts for a model, the agent reads that model's recipe here (PB3 decision 5: prompts follow the target model's own guide). Each recipe records its sources and the date it was checked. A model without a recipe gets one before its first use: in Organic AI video, a model chosen on the Models page gets its recipe written into the workspace's `library/model-prompting/<owner>-<name>.md` (the title line `(checked YYYY-MM-DD)`, its `Sources:`, the input fields from Replicate's API). The recipes here are a head start, not a list of allowed models.

| Model | Recipe | Used for |
|---|---|---|
| `openai/gpt-image-2` (Replicate) | [gpt-image-2.md](gpt-image-2.md) | packshots, character anchors, first frames |
| `minimax/h3` (Replicate; also on Higgsfield) | [minimax-h3.md](minimax-h3.md) | image-to-video, multi-shot up to 15 s |
| `google/veo-3.1-fast`, `google/veo-3.1` (Replicate) | [veo-3.1.md](veo-3.1.md) | image-to-video clips (4/6/8 s) |

## Choosing a model (PB3, user decisions round 5)
1. **Suggest, do not impose.** For each task (product image, first frame, video, edit) the agent suggests one model with a reason; the user may change it. Defaults: **720p** (or the model's nearest resolution) and **9:16**; both can be changed by the user.
2. **Candidates:** models available to the user's provider: Replicate (`tools/replicate_price.py --collection image-to-video` / `text-to-video`) and Higgsfield (`models_list` in the Higgsfield MCP).
3. **Quality:** independent rankings for the task, read on the day: Artificial Analysis (https://artificialanalysis.ai/video/leaderboard/image-to-video) and Arena (https://arena.ai/leaderboard/video/image-to-video, https://arena.ai/leaderboard/image-edit). Note the snapshot date.
4. **Fit:** the inputs the shot plan needs (first frame, last frame, reference images, duration, aspect ratio, audio on/off).
5. **Price:** live price from the model page (`tools/replicate_price.py <owner/model>`) or the Higgsfield credit cost; cite the price and the check date in the estimate.
6. **One video model per video.** All clips of a video come from one model; another model only for a separate section (e.g. a Claude animation insert). A failed shot is regenerated on the same model; if the model fails the whole video, the whole video moves to another model.


## Seedance 2.0 and people (checked 2026-11-05)
On the API (Replicate, BytePlus) Seedance 2.0 rejects input images with a photorealistic human face, synthetic ones included (Replicate error E005 "flagged as sensitive", within ~5 s, no output); a retry with the same input fails the same way. The official route for a real face is a liveness check of that person and a verified asset, which does not apply to an AI host. So Seedance cannot take a realistic AI host as a first frame or reference; use MiniMax H3 for talking-host formats. Sources: ComfyUI Seedance 2.0 docs (https://docs.comfy.org/tutorials/partner-nodes/bytedance/seedance-2-0), laozhang.ai (https://blog.laozhang.ai/en/posts/seedance-2-api-real-people.md), APIYI face-asset FAQ (https://docs.apiyi.com/en/faq/seedance2-face-asset-whitelist.md). Bypass tricks (grids, resizing) are not used.

**Person described in text instead (tested 2026-11-05, PB3 P4 take_v07):** with no human photo in the inputs (references: product packshot + dog anchor only) Seedance 2.0 passes and gives a strong result: the product closest to 1:1 of all tests (arcs from the top edge, nub grid, suction cups), all 5 lines spoken incl. the quiet last line, a consistent creator across cuts, very natural phone look. Limits: the person is new each generation (a recurring host cannot be locked, since her frame cannot be fed back as a reference), cut times drift ±1.3 s from the brackets, extra product placement may appear (the mat on the counter in the opening shot), audio quieter (−18.6 LUFS, normalise in the edit). Price 720p $0.18/s.

**Official route for an AI host as a reference (researched 2026-11-05):** BytePlus ModelArk *Private virtual portrait library*: upload the AI portrait as a virtual-portrait asset (must not resemble a real person; security review), then pass `asset://<Asset_Id>` as `reference_image` (or first frame) in the Seedance 2.0 / 2.5 request. Needs a direct ModelArk account and Advanced Creation Rights (Entry tier free: 50 assets, 3 QPM); not available via Replicate. A real creator goes through the real-human portrait library (liveness + authorisation). Details and sources: `runs/03-organic-ai-video/2026-11-05_pet-dtc-proposals/02_research/models/seedance_faces_v01.md`. Detector-evasion tricks (grids, banners, crops) are not used.

**Confirmed by other users (2026-11-06):** the block is reported independently on GitHub (ComfyUI issue #13524, AI portrait rejected), Adobe Community (Firefly; an Adobe employee confirms Seedance 2.0 takes no human faces in references) and Reddit r/generativeAI. The user decided not to open a BytePlus account, so the asset route is not used; use the creator-in-text route or H3 reference mode. Evidence: `runs/03-organic-ai-video/2026-11-05_pet-dtc-proposals/02_research/models/seedance_faces_v02.md`.

## Talking AI person: which model (PB3 rounds 26–27, decided 2026-11-06)
Applies to formats where a person who talks must be generated.
- **No specific influencer** (person generated from a description): suggest **Seedance 2.0** first, with the creator described in text and the product/pet as reference images (the face block does not apply).
- **A specific AI influencer** (fixed look from an approved image): suggest **MiniMax H3 reference mode** (proven in P4 v06; $1.20 per 15 s).
- **H3 dialogue (round 47):** write the dialogue straight into the prompt; **no ElevenLabs voice reference by default** (it sounded worse and, in Polish, garbled words).
- **Off-screen narrator (round 45):** ElevenLabs voice by default (it sounds better than the H3 narrator); H3 narrator from the prompt is the alternative.
- **Speech route (round 33):** native speech on MiniMax H3 is the default for every talking character, human or animal (P2 test: same look as ElevenLabs + Kling lip-sync at about half the cost). Lines that do not fit one take → propose an extra shot or take (split at a line break; keep the same host image and voice description in the prompt). ElevenLabs + lip-sync (Kling Avatar v2, OmniHuman 1.5) only as an alternative: on request, or when exact wording or a brand voice is required.
- **The user names another model:** check it against these criteria and say which one fails: photoreal AI person image accepted (only when a specific influencer is used); product enters from an image together with the person; native speech with lip sync (or the ElevenLabs + lip-sync route); 9:16; take length for the script (~2.5 words/s); available at the user's provider with a live price. Known alternatives: Gemini Omni 1.2 Flash (same reference mode, faces untested), Kling 3.0 Omni (exact first frame + product reference + speech).
Comparison and prices: `runs/03-organic-ai-video/2026-11-05_pet-dtc-proposals/02_research/models/host_frame_models_v01.md`.

## Video quality tiers (PB3 round 28, 2026-11-06; prices from Replicate that day)
| Tier | Model | Price 720p | For |
|---|---|---|---|
| Budget | `bytedance/seedance-1.5-pro` | $0.052/s with audio, $0.026/s without (12 s max per call) | formats with no speech, no need for exact precision and where sound does not matter (B-roll, mood shots under music); **not ASMR** (weak native audio: sound-led formats go to Veo 3.1, Seedance 2.0 or MiniMax H3); product only through the first frame (no reference input) |
| Default (medium) | `minimax/h3` | $0.08/s at 768P ($1.20 per 15 s) | most formats, incl. a talking specific AI influencer (reference mode) |
| Top | `bytedance/seedance-2.0` | $0.18/s ($2.70 per 15 s) | best quality; no photoreal person images (face block) |
| Premium | `bytedance/seedance-2.5` | $0.2312/s ($3.47 per 15 s); $0.97/s with a video input | AA #1; same face block; only when the user asks for it |
The agent suggests a tier from the format (speech, precision) and the budget; the user decides. Inside a tier the talking-person rule above still applies.

## Resolution and upscaling (PB3 round 29, 2026-11-06)
- At the start of every generation (pack/cost gate) ask: **720p, 1080p, or 720p + upscale**, with the cost of each option for the chosen model.
- Suggested (default) upscaler, user decision round 30: **`prunaai/p-video-upscale`** (`target: 1080p`, keep the source fps; $0.02/s at 1080p, keeps the audio). Alternatives on request: `topazlabs/video-upscale` ($0.08 per unit, probably per second), `bytedance/video-upscaler` with `scene: aigc` (`pro` for faces).
- MiniMax H3 has a native 2K tier ($0.13/s), often cheaper than 768P + Topaz. Seedance 2.0 at 720p + upscale is about half the price of native 1080p.
- Upscaling must not change the sound; mux the original audio back with ffmpeg if needed. Comparison: `runs/03-organic-ai-video/2026-11-05_pet-dtc-proposals/02_research/models/upscale_models_v01.md`.
