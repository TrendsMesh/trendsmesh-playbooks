# Animatics: an animated storyboard of a brief, on request (shared: PB02, the ad and the organic video brief; later PB03)

An animatic is offered after the briefs and made only for the concepts the user names (CB11, the
`animatics` check-in before D2; in Hands-off it is not asked and none is made): a short animated
storyboard of the ad's structure (the shots, the timing, the on-screen text, the hook, the call to
action), drawn in one of the plugin's 49 animation styles (`data/styles/`, the styles organic video
animates in), matched to the concept, and rendered to MP4 on the user's own computer, at no cost. A
concept without one shows "Animatic on request" on the page. It shows structure and pacing, never
realistic footage: no AI generation at the brief stage.

Every animatic is drawn in a library style (owner decision #148 line 2): there is no sketch to fall back
on, and a concept with no `animatic.style` is refused by the render.

## From beats to the animatic

Each beat of a concept in brief.json is one beat of the animatic. The beat says what is seen
(`see`), heard (`hear`) and written on screen (`ost`), from `t0` to `t1` seconds. Its `animatic`
block says what the storyboard shows:

```json
{"t0": 0, "t1": 3, "see": "Creator sitting up in bed at dawn, notebook on her knees",
 "hear": "\"I forgot every dream by breakfast. So I kept a notebook on the pillow for a week.\"",
 "ost": "Day 1 of writing my dreams down before I even sit up", "ost_strong": true,
 "animatic": {"label": "HOOK",
              "texts": [{"style": "center", "str": "Day 1 of writing my dreams down before I even sit up", "size": 70}]}}
```

- `label` names the beat (HOOK, PROOF, CTA).
- `texts` are the on-screen texts, verbatim from the beat, in the trend's text style (CB7: where
  and when the evidence videos put their text): `style` is where it sits (`center`, `top`, `box`,
  `chip`, `cta`), `at` when it shows, `size` its size in pixels on the 1080-wide stage.
- `params.image` (optional) is a picture of the product kept in the run, named by its path from the run
  folder (like `01_base/product.png`: PNG, JPEG or WebP, up to 2 MiB). The style module draws it. A path
  outside the run or a web address stops the animatic step.
- A `scene` (or `zoom`) from a brief written before 0.14 is not read: it named the old sketch's
  drawings, which no longer draw animatics. `tm brief check` no longer asks for it.

## Making them (D2, after `tm decide animatics make --concepts C1,C3`)

Three calls, for the concepts the user named:

1. **The styles:** `tm brief animatic --run R --style auto --concepts C1,C3 --json` picks each
   concept's style with the style ranking (`atlas_prompt.ranked`) for the concept's format
   (`plugin.axes.format`, an organic brief's `organic.format`): a talking head, a screen recording and
   a UGC phone video get different looks, and no two concepts of the brief share one. A brief for a
   channel puts the channel's own look first when it has one: `--own <number|styleId>`, the library
   style nearest the channel profile's `video_style` (`tm organic atlas-styles --channel <name>` lists
   it first). The user named a style: `--style <number|styleId>` gives it to every concept named. It
   writes a new brief version with each concept's `animatic.style` (the styleId) and `animatic.poster`
   (the style's poster, copied beside the renders), and a build prompt per concept,
   `03_wip/animatic/<C>_prompt_vNN.txt`: the concept's beats, word for word, in the style, at the
   first format's frame (the second format is laid out from the same module). Earlier MP4s are left
   out of that version. Tell the user each concept's style in one line.
2. **The modules:** one subagent per concept, in parallel, writes the style module from its prompt
   (the answer's `styles[].prompt` to `styles[].module`, `03_wip/animatic/<C>_style_vNN.js`, the same
   version as the prompt): give it the prompt file and the module path, and nothing else to do. The
   module has one beat per beat of the brief, starting at the beats' `t0` (`beats: [...]` as a list),
   and lasts the concept's `length_s`. The brief's beats are its own: no frames list is read, so
   organic video's storyboard check (a module's beats against a frames list) never refuses an
   animatic.
3. **The render:** `tm brief animatic --run R --render --concepts C1,C3 --json` builds each format's
   page from the latest module (`atlas_prompt.module_page`: the libraries and the product pictures
   inlined) and draws it with `atlas.render`. It refuses, before anything is written, a concept with
   no `animatic.style`, one with no module written from its latest prompt, or a module whose beats do
   not match the brief's. The layout check's findings (text too small or outside the safe area) are in
   the answer: fix them in a new module version and render again. The new brief version keeps `style`
   and `poster` beside the MP4s.

The page shows, under each concept's hypothesis, the style's name and poster ("Animatic style: Ink
Wash"). `tm brief check` refuses an `animatic.style` the library does not have.

## Formats (R6)

The formats come from the placements (`tm audience pick`): 9:16 for Reels and Stories, 4:5 for the
feeds, both when no placement data exists, or as set in the config's `animatic.formats`. Each
format is drawn and rendered at 24 fps, with five stills (at 0.06, 0.3, 0.55, 0.8 and 0.95 of the
length) for a quick look. `--formats` draws only some formats.

## Rendering, and the browser

`--render` writes the pages to `03_wip/animatic/`, the MP4s and stills to
`03_wip/animatic/renders/<concept>_animatic_<format>_vNN.mp4`, and a new brief version that names
them (the page plays them). Without `--render` it writes the pages only. One call renders every
concept it is given in every format, which can pass the Bash tool's 10-minute limit: run it in the
background and wait for it, or render one concept at a time (`--concepts C1`) with the longest
timeout.

It draws in the **user's own Chrome or Edge** (Chromium on Linux), found on the computer: nothing
is downloaded for it but the small renderer package (the animatic tools, installed once, after
the user's yes). Without a browser the doctor says what to install (Microsoft Edge or Google
Chrome on Windows; Google Chrome on macOS and Linux), and the animatic step waits: the run
continues from the same place once it is there, and nothing else is lost (or the user skips the
animatics). A review pack alone, a skip and Hands-off need no animatic.

After a render, look at the stills: text must not overlap or run off the frame, and each beat must
read. A fix is a new version of the style module (a new brief version when the beats themselves
change, then `--style` again for a new prompt). Then render again.

## How long

The animatics question gives no fixed time (owner decision #148 line 157). It says, in the user's
language: "Animatics take a while: depending on the style and the computer, from a few to over a dozen
minutes per concept." There are too few reliable measurements for a narrower range, and they differ a
lot:

- On a Mac with Chrome, the render took about 2 to 3 minutes per concept (a 12 s concept in 9:16 and
  4:5 took 115 s, a 15 s one 148 s), and writing the modules about 10 to 15 minutes per batch, the
  concepts' modules written in parallel.
- On a Windows PC, two styled animatics (30 s, one concept each) took about 15 and about 30 minutes from
  writing to video: about 9 minutes of writing each time, and a render of 2 minutes once and 13 minutes
  the other time, on the same computer.

No render time is kept, and no command estimates it.
