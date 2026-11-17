# Topaz Video Upscale: prompting recipe (checked 2026-11-17)

Written for the plugin from Replicate's model page and the owner's blind test of the upscalers (issue #115). The
model registry (`data/models/registry.yaml`) selects it in advance for the upscale to 1080p.

Sources:
- Replicate, `topazlabs/video-upscale`: https://replicate.com/topazlabs/video-upscale (the API schema: `video`,
  `target_resolution` 720p, 1080p or 4k, default 1080p; `target_fps` 15 to 60, default 30; and the pricing guide in
  its `billingConfig`), read 2026-11-17.
- The owner's blind test of 2026-11-17 (issue #115, section 4): Topaz at 1080p and the source frame rate is the
  suggested upscale, about $0.28 per 15 s; Pruna's standard upscale ($0.30) the other suggested one, Pruna's turbo
  (about $0.10) and no upscale the budget ones.

## When the plugin uses it
- The upscale task (Organic AI video's 768P + upscale answer, OV8; any playbook's upscale to 1080p): the picked take
  is upscaled as the one item of the upscale stage, priced on its own line. It is the registry's selected upscaler;
  the Models page offers the others.

## Rules
- **No prompt.** The input is the take itself: `video` (the picked take, a file in the run).
- **Always send the variant**: `target_resolution: "1080p"` and `target_fps` set to the take's own frame rate (24 for
  MiniMax H3's takes). Replicate's default is 30 fps: a higher rate than the take's adds frames and cost, and 60 fps
  doubles the price.
- **The sound and the shape are the take's**: check them as Pruna's upscale is checked (`tm organic upscale`: 1080p
  in the same shape, the same frame rate, the sound there, as long and as loud). An upscale never fixes the sound.
- **Upscale the picked take only**, after its QA and pick; a second upscale is a redo like any other.

## Price (Replicate, 2026-11-17)
Replicate bills Topaz in units of $0.08 ("around 12 units for $1"), counted from the output's resolution and frame
rate. Its pricing guide gives, per 5 s of output from a 720p source: 1080p/30 fps $0.093, 1080p/60 fps $0.187,
720p/30 fps $0.027, 4K/30 fps $0.373. So 1080p at up to 30 fps is about $0.0186 a second, 0.2325 units a second, and
15 s about $0.28. The price file (`tm tool replicate_price`) shows only "$0.08 per unit": the registry's `live.factor`
turns it into the price a second. It is never "$0.08 a second".
