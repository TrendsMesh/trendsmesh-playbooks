# Pruna P-Video Upscale: prompting recipe (checked 2026-11-06)

Written for the plugin from the handoff's pet-store research and test (handoff `organic-video_v02`). Each finding keeps
the date it was made.

Sources:
- PB3 pet-store research, in the repository under `handoff/organic-video_v02/examples/pet-store-proposals/02_research/models/`:
  - `upscale_models_v01.md` (2026-11-06, round 29): the upscalers on Replicate, their prices and inputs, when an
    upscale pays off, and the user's decision of round 30 (Pruna is the default);
  - `prices_upscale_2026-11-06.json` (Replicate `billingConfig`, 2026-11-06): the raw prices.
- The tested upscale: `handoff/organic-video_v02/examples/pet-store-proposals/03_wip/P4/upscale_v06_pruna.json`, its
  record `upscale_v06_pruna.run.json` (2026-11-06, prediction `36emn62kgdrmw0d1nxpr8nrtyw`) and its manifest row.
- PB3 `PLAYBOOK.md` (the resolution question at the pack, round 29) and `ANALYSIS.md` rounds 29 and 30 (2026-11-06).

## When the plugin uses it
- **Only for the "720p + upscale" answer to the resolution question** (OV8, the pack's `resolution.choice`
  `768p_pruna`): the picked take is upscaled to 1080p as the one item of the pack's upscale stage, priced on its own
  cost line. 720p (768P on MiniMax H3) and native 1080p are the other two answers; each is shown with its cost.
- `prunaai/p-video-upscale` is the suggested upscaler (the user's decision, round 30, 2026-11-06). Topaz
  (`topazlabs/video-upscale`) and ByteDance (`bytedance/video-upscaler`, `scene: aigc`) only when the user asks;
  each needs its own recipe first.
- There is no independent ranking of video upscalers (2026-11-06): the pack's ranking line names the research above
  and its date.

## Rules
- **No prompt.** The input is the take itself: `video` (the picked take, a file in the run) and `target` (`"1080p"`;
  the model also offers `720p`, `2k` and `4k`). Nothing else was needed in the test.
- **The source frame rate is kept** (24 fps in, 24 fps out in the test). The price tier follows it: up to 30 fps is
  the plugin's case; a 60 fps source costs twice as much.
- **The aspect ratio is kept**: a 768×1344 H3 take came out 1088×1904 (still 9:16); the edit renders it at 1080×1920.
- **The sound is copied unchanged** (the test, 2026-11-06). Upscaling must never change the sound: if a take's audio
  is ever lost or re-encoded, mux the original track back with ffmpeg before the edit.
- **Upscale the picked take, never a take that is still to be judged**: the take's QA and pick come first, and the
  upscale is the pack's item with its own line, so a second upscale is a redo like any other.

## What the test found (pet store P4 take v06, 2026-11-06, $0.30)
- 15.1 s of 768P H3 footage to 1080p in about 43 s of predict time (61 s wall), one output, the audio copied.
- The upscaled take then needed a level fix on its quiet last line in the edit (a timed volume and light
  compression): an upscale does not fix the sound, and the take's QA still applies.

## Prices (Replicate `billingConfig`, 2026-11-06)
Per second of output video, `model variant=up_to_30fps`: 720p $0.01, **1080p $0.02**, 2k $0.04, 4k $0.08; with
`up_to_60fps` each is double (1080p $0.04). A cost line names the tier's criteria as the price file holds them, for
example `model variant=up_to_30fps, target resolution=1080p`: 15 s at 1080p is $0.30. Read the price again with
`tm tool replicate_price` before a pack: a price older than `pricing.max_age_days` is refused.
