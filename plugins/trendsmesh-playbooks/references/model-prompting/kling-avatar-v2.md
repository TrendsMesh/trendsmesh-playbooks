# Kling Avatar v2: prompting recipe (checked 2026-11-06)

Written for the plugin from the handoff's pet-store research and test (handoff `organic-video_v02`). Each finding keeps
the date it was made.

Sources:
- PB3 pet-store research, `handoff/organic-video_v02/examples/pet-store-proposals/02_research/models/speech_models_v01.md`
  in the repository (2026-11-05): the speech and lip-sync shortlist, inputs, prices from Replicate's `billingConfig`
  read that day, rankings (Artificial Analysis image-to-video and text-to-video with audio, as shown 2026-11-05; Arena
  image-to-video and text-to-video, updated 2026-09-21).
- The tested route B of the bath-day skit (pet store P2, 2026-11-06, round 32): the spec
  `examples/pet-store-proposals/03_wip/P2/take_b_v01.json`, its record `take_b_v01.run.json`, the pack
  `03_wip/packs/packs_v03.md` and the manifest rows (`examples/pet-store-proposals/manifest.md`).
- PB3 `PLAYBOOK.md` OV7 and `VARIANTS.md` §3 and §5, and `ANALYSIS.md` round 33 (2026-11-06): the speech-route rule.

## When the plugin uses it
- **Only as the alternative speech route** (`speech.route: elevenlabs_lipsync`, OV7): on the user's request, or
  when the wording must be exact or a brand voice must be used. The default for every talking character, human or
  animal, is native speech on MiniMax H3 (`minimax-h3.md`): in the P2 comparison H3 looked as good at about half the
  cost (A $1.05 against A + B about $1.87, round 33). The pack names the reason in `speech.alternative_reason`.
- It needs ElevenLabs in the run's stack (the line is read there first) and a Replicate key.
- There is no independent lip-sync or talking-head ranking (2026-11-05): the ranking line of the pack names the
  research above and its date.

## Rules
- **Inputs:** `image` (the talking frame), `audio` (the ElevenLabs line, made with `tm tool elevenlabs tts`), `prompt`,
  `mode` (`std` or `pro`). The clip lasts as long as the audio. It documents both humans and **animals**.
- **The frame:** a close-up made for the talking shot (GPT Image 2 from the approved anchor, `gpt-image-2.md`), the
  mouth and face clear, as in P2's `closeup_v01` made from the tub frame.
- **The audio:** the lines as the voice reads them, joined with short pauses where the cut falls (P2: line 1 + 0.5 s
  + line 2, 7.4 s). The ElevenLabs master is the voice of the video: lay it over the clip in the edit and check the
  sync.
- **The prompt** describes how the face moves, not the words: "his mouth and jaw move clearly with every word,
  eyebrows raise on 'FORTY', then he leans back slightly and speaks dead seriously; small natural head movements,
  water dripping from his ears, the camera stays still" (P2).
- **Mode:** `pro` was tested; `std` costs about half.

## What the test found (pet store P2 route B, 2026-11-06, $0.82)
- Kling Avatar v2 pro, 7.47 s, 1072×1920: clear mouth movement and expressions on a husky.
- **A burned-in text artefact:** "1010" near the bottom of the frame at about 5.9 to 7.0 s. It was cropped out in
  the edit by a 1.13 zoom from the top. **Every lip-sync clip is checked for burned-in text** on its QA contact sheet
  (`tm tool take_qa`) before it is picked, and a hit is shown to the user with the fix (a crop or zoom in the edit,
  or a redo with its cost).
- The frame is 1072 wide, not 1080: the edit renders at 1080×1920 and fits it there (a segment `zoom`).

## Prices (Replicate `billingConfig`, 2026-11-05)
`std` $0.056 per second, `pro` $0.11 per second (P2's 7.47 s pro clip cost $0.82). Read the price again with
`tm tool replicate_price --run R kwaivgi/kling-avatar-v2` before a pack: a price older than `pricing.max_age_days` is refused.
