# Animation in one of our styles (shared: PB03)

An animation is a self-contained HTML page Claude writes in one of the plugin's own **animation styles**,
drawn frame by frame in the user's own Chrome or Edge and rendered to MP4 on their computer. It costs no
generation money, only Claude usage. The order is OV9's: a storyboard first (the cheap stage: the look and the
order are judged on still panels), then the full animation, then the edit.

The style library ships with the plugin (`data/styles/`) and is ours, written from scratch: one
card per style in `styles.json` (name, family, what it looks like, what it suits, palette, fonts, finishing
passes, motion, how it explains, its sound, what to avoid), the shared drawing helpers, the sound kit and the
page runtime in `lib/`, one short reference animation per style in `styles/`, and the build prompt's parts in
`prompt/`. `data/styles/README.md` says how the pieces fit and how to add a style. It replaced a third-party
catalogue whose licence did not allow shipping it. **No style posters are in the package**: a style is offered
in words.

## The taste card: 2 to 3 styles in words

At D2, for an animation, offer **2 to 3 styles by number, name and description**: `tm organic atlas-styles
--json` lists them (`order`, `styleId`, `name`, `category` (the family), `description`, `suits`: what topics
and tones it explains well). Pick the ones whose look fits the channel and the topic, each with a one-line
why, your pick first. Never a poster, a preview link or a picture from the web: the look is judged on the
storyboard (F1), where a style that does not fit is changed for free. The pick goes into the pack's
`taste.style` as `<number> <name>` (for example `14 Halftone Comic`).

## The build prompt

1. **The voiceover comes first, timed** (F1): the picked voice's ElevenLabs take with its word times
   (`tm tool elevenlabs tts` with `--timestamps`, as the organic-video skill's F1 says). The
   animation is **timed from the word SRT** (`<stem>.words.srt`), never from the script's own `at`
   times: real voices run 2.5 to 3.8 words a second.
2. **The content file** (`03_wip/<item>/content_vNN.txt`, in English, the on-screen text in the
   audience language): the format (vertical 9:16, 1080×1920), the length (exactly the voiceover),
   each line with its time from the SRT and what is seen on it, the only on-screen text allowed
   (short, verbatim), and the sound effects (they play quieter under the voiceover). It says:
   - **which parts of the style are setting and which are rendering** (lesson 17): the setting
     (the reference animation's topic, its places, its props, its subjects) is replaced by the topic's;
     the rendering (the palette, the line, the textures, the lettering, the transitions, the
     finishing passes) is kept. Name the reference's setting elements that must not appear;
   - **text and the key action stay above y 1260** in 9:16 (and below y 269, the prompt's top 269 px of
     1920): the band below is the captions' and the platform's (OV10);
   - captions and the narration are not drawn: the edit adds them.
3. **The prompt**: `tm organic atlas-prompt --run R --item <item> --style <number> --voiceover
   --storyboard --aspect 9:16 --content 03_wip/<item>/content_vNN.txt --srt <the word SRT> --json`
   writes `03_wip/<item>/prompt_vNN.txt`: the build prompt in its voiceover and storyboard modes, for the
   9:16 frame, with the content and the SRT filled in, then the style's card, the shared libraries' API and
   the style's reference animation (50,000 to 72,000 characters). `<item>` is the pack's id for a whole
   animation (an animation section's id in a video in sections).
4. **The page**: Claude writes only a **style module** (a `.js` file); `tm organic atlas-page --run R --item
   <item> --module 03_wip/<item>/<name>_vNN.js [--storyboard] --json` builds `<name>_vNN.html` beside it,
   with the shared libraries inlined, at the prompt's frame (free; never over an earlier page). So neither
   the prompt nor the subagent's answer carries the libraries' code.
   Building the page also runs the **layout check** in the user's browser (free): every label at least the
   prompt's size as seen, nothing to read outside the safe area, no empty band of a quarter of the safe
   area's height. Its findings come back in `layout.problems` and the message: the subagent fixes every one
   in a new version of the module and the page is built again before anything is drawn.

## The storyboard (F1)

A subagent builds the storyboard from the prompt (about 15 minutes, FLOWS K). Its brief:
read `03_wip/<item>/prompt_vNN.txt` whole and follow its storyboard mode; write the style module
`03_wip/<item>/storyboard_vNN.js` with **5 to 6 beats**, one per beat of the voiceover; build its page
with `tm organic atlas-page --run R --item <item> --module 03_wip/<item>/storyboard_vNN.js --storyboard
--json` (the page draws each panel of 1080×1920 on a canvas with the id `p1` to `p6`, sets
`window.STORYBOARD_READY = true` once they are drawn, and gives the contact sheet as a PNG data URL from
`window.makeSheet()`), open it and fix what is wrong in a new module version; append its stage to
`03_wip/<item>/_progress.txt` as it goes (one line per stage). Then draw it: `tm organic storyboard --run R --item <item> --page
03_wip/<item>/storyboard_vNN.html --json` writes `03_wip/<item>/storyboard_vNN/panel_01.png` …
and `sheet.png` (free, in the user's browser; never over an earlier one). Look at the sheet
against the rubric: the style kept, the same characters in every panel, text and key action above
y 1260, a panel per beat.

The storyboard is the images check-in of an animation: on the images page (with the voiceover
beside it to listen to), or by rule where that check-in goes by rule (`tm organic pick --run R
--stage storyboard --name <item> --file 03_wip/<item>/storyboard_vNN/sheet.png --reason "<against
the rubric>" --json`). A redo with a note is a new storyboard version (free): the subagent fixes
what the note says, and it is drawn and shown again. Only the latest storyboard, accepted after
the pack check that last changed its script, style or section, counts.

## The animation (F2)

A subagent builds the animation from the same prompt and the accepted storyboard's module, with the
user's notes on it (about 15 minutes, and about 2.5 minutes to render 750 frames): the module
`03_wip/<item>/explainer_vNN.js`, then its page with `tm organic atlas-page --run R --item <item> --module
03_wip/<item>/explainer_vNN.js --json`: `03_wip/<item>/explainer_vNN.html`, a page whose every frame is a
pure function of `t` (`window.seek(t)`, `window.DURATION`, one canvas, the sound score in
`window.scoreSound` with the library's `SOUND` kit), appending its stage to `03_wip/<item>/_progress.txt`. Then `tm organic animate --run R --item
<item> --page 03_wip/<item>/explainer_vNN.html --json` renders it at the config's
`animation.fps` (30) into `03_wip/<item>/renders/anim_vNN.mp4` with its stills; it is refused
until the storyboard is accepted. Look at the stills (text inside the safe zone, the fixes from the
storyboard's notes, no page errors), then the video check-in shows the render. The edit (G1) lays
the voiceover, the music and the captions over it.
