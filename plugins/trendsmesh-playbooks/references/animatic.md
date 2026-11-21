# Animatics: an animated storyboard of a brief, on request (shared: PB02, the ad and the organic video brief; later PB03)

An animatic is offered after the briefs and made only for the concepts the user names (CB11, the
`animatics` check-in before D2): a pencil storyboard of the ad's structure (the shots, the
timing, the on-screen text, the hook, the call to action), rendered to MP4 on the user's own
computer, at no cost. A concept without one shows "Animatic on request" on the page. It shows structure and pacing, never realistic footage: no AI generation at
the brief stage.

The quick sketch (`scenes.js`, below) is the default: `tm brief animatic --render` with no style draws
it. An animatic in one of the plugin's 49 animation styles is an option, made only when the user asks
for one (section "In a library style", at the end).

## From beats to scenes

Each beat of a concept in brief.json is one scene of the animatic. The beat says what is seen
(`see`), heard (`hear`, shown as subtitles; a quoted line becomes "VO: …") and written on screen
(`ost`), from `t0` to `t1` seconds. Its `animatic` block says how to draw it:

```json
{"t0": 0, "t1": 3, "see": "Creator sitting up in bed at dawn, notebook on her knees",
 "hear": "\"I forgot every dream by breakfast. So I kept a notebook on the pillow for a week.\"",
 "ost": "Day 1 of writing my dreams down before I even sit up", "ost_strong": true,
 "animatic": {"scene": "bed_writing", "label": "HOOK", "zoom": [1, 1.06],
              "texts": [{"style": "center", "str": "Day 1 of writing my dreams down before I even sit up", "size": 70}]}}
```

- `scene` is a name from the scene library below; a name it does not have is refused by `tm brief
  check` (stage brief).
- `label` names the beat on the storyboard (HOOK, PROOF, CTA); `params` set what a scene draws
  (a time on a phone, the text of a note); `zoom` is a slow push-in from and to (default 1 to
  1.04).
- `texts` are the on-screen texts, verbatim from the beat, in the trend's text style (CB7: where
  and when the evidence videos put their text).

## The scene library (`scenes.js`)

| Scene | What the viewer sees |
|---|---|
| `bed_writing` | the creator in bed at night, lamp on, writing in a notebook |
| `notebook_closeup` | a notebook close-up being written; `lights_off` darkens the end of the beat |
| `lie_whisper` | lying in bed, eyes closed, whispering a sentence |
| `phone_alarm` | a phone alarm lights the face; sits up, then lies back; `time` |
| `morning_talk` | morning daylight, sitting up with a notebook, talking to camera |
| `product_phone` | the product on a phone: `product` (its name), `screen` (what is on the screen: a short text, or a list of up to 7 lines), `image` (a picture of it in the run, optional), `highlight` (a line, 0–6) or `cycle` |
| `desk_sticky_write` | top-down: a hand writing a sticky note; `note` |
| `sticky_to_phone` | the finished note moves onto a phone; `note` |
| `phone_dark_wake` | a phone with the note in the dark; the screen wakes; `note`, `time` |
| `finger_tap` | a finger taps the note on the phone; `note` |
| `proof_card` | a plain proof card frame (its lines come from the beat's texts) |
| `selfie_talk` | a front-camera selfie at night; `clock`, `eyes_closed` |
| `backcam_notebook` | the back camera: a notebook on the duvet, writing by phone light |
| `back_to_sleep` | the phone face down, back to sleep, fade to black |
| `morning_then_product` | the morning notebook, then the product on a phone; the params of `product_phone` |

The product scenes draw the brief's own product: give them `product` (the name, as
`meta.product.name` says it) and `screen` (what the viewer reads on it). `image` is the file's path
from the run folder (like `01_base/product.png`: PNG, JPG, WebP or GIF, up to 2 MiB), drawn into the
storyboard itself; a path outside the run or a web address stops the animatic step. Without these
params the screen is a plain placeholder. (`fixture: "book"` draws the dry run's book: a test
fixture, never a product shot.) `tm brief check` warns about a product scene with no `product`: the
brief still holds, but fix it in a new version before the animatics are made.

The library comes from the dry run (a product used at night). Pick the scene closest to
what the beat shows; a beat no scene fits is drawn with the nearest one and its `label` says what
the real shot is. A new kind of shot is a new scene in the library: a later plugin version, not a
run's work.

## Text styles

| `style` | How it looks | Use |
|---|---|---|
| `center` | big white text with a black outline, in the middle of the frame | the hook text of most trends |
| `top` | the same, in the upper part (`y`, a share of the height) | text that must clear the face |
| `box` | dark text in a light box | a caption or a quote |
| `chip` | white text on a small dark rounded label | labels ("Night 3") |
| `cta` | the closing call to action (`color` optional) | the end card |

`size` is the text size in pixels on the 1080-wide stage.

## Formats (R6)

The formats come from the placements (`tm audience pick`): 9:16 for Reels and Stories, 4:5 for the
feeds, both when no placement data exists, or as set in the config's `animatic.formats`. Each
format is drawn and rendered at 24 fps, with five stills (at 0.06, 0.3, 0.55, 0.8 and 0.95 of the
length) for a quick look.

## Rendering, and the browser

`tm brief animatic --run R --render --json` writes the storyboard files to `03_wip/animatic/`, the
MP4s and stills to `03_wip/animatic/renders/<concept>_animatic_<format>_vNN.mp4`, and a new brief
version that names them (the page plays them). Without `--render` it writes the storyboard files
only. Up to 15 minutes per animatic, and one call renders every concept it is given (`--concepts
C1,C3`: the ones the user named) in every format, which
passes the Bash tool's 10-minute limit: run it in the background and wait for it, or render one
concept at a time (`--concepts C1`) with the longest timeout. `--formats` draws only some
formats.

It draws in the **user's own Chrome or Edge** (Chromium on Linux), found on the computer: nothing
is downloaded for it but the small renderer package (the animatic tools, installed once, after
the user's yes). Without a browser the doctor says what to install (Microsoft Edge or Google
Chrome on Windows; Google Chrome on macOS and Linux), and the animatic step waits: the run
continues from the same place once it is there, and nothing else is lost (or the user skips the
animatics). A review pack alone, a skip and Hands-off need no animatic.

After a render, look at the stills: text must not overlap or run off the frame, and each beat must
read. A fix to a styled animatic is a new version of its style module (a new brief version when the
beats themselves change, then `--style` again for a new prompt); a fix to a sketch is a change to
the beats in a new brief version. Then render again.

## In a library style (issue #138 item 4)

An option, made only when the user asks for it: the animatic drawn in a library style
(`data/styles/`, the styles organic video animates in) instead of the sketch. Without it nothing
changes: a concept with no `animatic.style` is drawn as the sketch. Three calls, after `tm decide
animatics make --concepts C1,C3`, for the concepts the user wants styled:

1. `tm brief animatic --run R --style auto --concepts C1,C3 --json` picks each concept's style with
   the style ranking (`atlas_prompt.ranked`) for the concept's format (`plugin.axes.format`, an
   organic brief's `organic.format`): a talking head, a screen recording and a UGC phone video get
   different looks, and no two concepts of the brief share one. A brief for a channel with its own
   look puts that first: `--own <number|styleId>`, the library style nearest the channel's
   `video_style` (`tm organic atlas-styles --channel <name>` lists it first). `--style <number|styleId>`
   gives every named concept the style the user asked for. It writes a new brief version with each
   concept's `animatic.style` (the styleId) and `animatic.poster` (the style's poster, copied beside
   the renders), and a build prompt per concept, `03_wip/animatic/<C>_prompt_vNN.txt`: the
   concept's beats, word for word, in the style, at the first format's frame (the second format is
   laid out from the same module). An earlier sketch's MP4s are left out of that version.
2. A subagent per concept writes the style module from its prompt:
   `03_wip/animatic/<C>_style_vNN.js`, the same version as the prompt. The module has one beat per
   beat of the brief, starting at the beats' `t0` (`beats: [...]` as a list), and lasts the concept's
   `length_s`. The brief's beats are its own: no frames list is read, so organic video's storyboard
   check (a module's beats against a frames list) never refuses an animatic.
3. `tm brief animatic --run R --render --concepts C1,C3 --json` builds each format's page from the
   latest module (`atlas_prompt.module_page`: the libraries and the product pictures inlined) and
   draws it with `atlas.render` (the call's other concepts stay sketches). It refuses, before
   anything is written, a concept with no module
   written from its latest prompt, or a module whose beats do not match the brief's; the layout
   check's findings (text too small or outside the safe area) are in the answer: fix them in a new
   module version and render again. The new brief version keeps `style` and `poster` beside the MP4s.

The page shows, under each styled concept's hypothesis, the style's name and poster ("Animatic
style: Ink Wash"). `tm brief check` refuses an `animatic.style` the library does not have.

**How long:** a styled animatic takes longer than the sketch (about a minute per concept and
format). Measured on a Mac with Chrome: a 12 s concept in 9:16 and 4:5 took 115 s, a 15 s one 148 s,
so the animatics question says "about 3 minutes per concept". Each styled render's time is kept on
this computer (the plugin data folder, `animatic_timing.json`); `tm brief animatic --run R --estimate
--json` gives `minutes_per_concept`, the last styled render's time per concept (its formats, layout
checks and renders together) rounded up, or 3 before there is one. The subagent writing the module
takes longer still, about 10 to 15 minutes, while the concepts' modules are written in parallel.

A beat's `params.image` is one of the pictures the page holds: the prompt names it (`beat2`), and the
module draws it with `Player.picture`. A PNG, JPEG or WebP only. Each beat's `animatic` block is read
by the styled prompt too: its `label`, its `texts` (where and when each text shows) and its
`params.image`; its `scene` is the sketch's alone.
