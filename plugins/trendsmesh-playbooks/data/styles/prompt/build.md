# Build a {{STYLE_NAME}} animation

You are making a short animated explainer in the **{{STYLE_NAME}}** style: one self-contained HTML page that draws
every frame on a canvas and scores its own sound. It will be rendered to an MP4 frame by frame, and a person can
also open it and play it. You write one file, the style module; the page is built from it.

## The topic

{{CONTENT}}

## What to build

- A {{WIDTH}}x{{HEIGHT}} frame ({{ASPECT}}). Compose for this frame: place things for its shape. Never take a
  layout made for another shape and crop it.
- Write **only your style module**: one `.js` file shaped like the reference module below (an IIFE, `"use strict"`,
  no globals of its own). Do not copy the libraries into it and do not write the HTML: the page is built from your
  module with `brush.js`, `sound.js` and `player.js` inlined unchanged, the frame size, the mode and the fonts
  `<link>` (the command that builds it is in your brief). The libraries' API is below; the files are in the
  plugin's `data/styles/lib/` if you need a detail.
- Your module ends with `Player.register({ id, name, duration, fonts, beats, beatNames, draw, score })`:
  - `duration`: seconds (10 to 60, as the topic needs).
  - `fonts`: `{ href: "<Google Fonts css2 URL>", faces: ['800 20px "Font Name"', ...] }`, one face per weight you use.
    Write the URL out in full: the page's `<link>` is taken from it.
  - `beats`: the start time of each beat (5 or 6 of them); `beatNames`: a short name for each.
  - `draw(ctx, W, H, t)`: draws the whole frame at `t` seconds.
  - `score(k)`: the sound, with `k.at(time, "effect", { gain, pitch, pan, dur })`, `k.bed(...)`, `k.seq(...)` and
    the rest of the scheduler in `sound.js`.
- `player.js` then gives the page `window.seek(t)`, `window.DURATION`, `window.scoreSound` and a small player
  (play/pause, scrub, time, sound on/off, loop). Do not write your own player and do not change the libraries.

## Use the reference module as your style guide

The reference module below is a finished animation in this style on another topic. Keep its **rendering**; replace
its **setting**.

- Keep: the palette, the line and edge quality, the textures and finishing passes (at the same strength), the
  lettering and type sizes, how labels, arrows and numbers are drawn, the transitions, the camera, the pace and the
  kind of sound. Reuse its helper functions as they are.
- Replace: the topic, the subjects and props, the backdrop and the words, with ones that fit the topic above.
- Draw the subjects accurately: a heart, an engine or a leaf should look like one, with its parts in the right
  places. Check every fact and number you show; if you are not sure of one, leave it out.
- Show the same kinds of beats as the reference: a title, a labelled diagram with an arrow, a key number, two or
  three steps of a process, and a closing beat. Change the order or add beats when the topic needs it.

## Rules

- Every frame is a pure function of `t`. All randomness comes from `Brush.rng(seed)` or `Brush.hash01(...)`, never
  `Math.random()` or the clock. The same `t` must give the same pixels. Caching static layers with `Brush.layer` is fine.
- Fonts load before the first frame matters: list every face in `fonts.faces`. Keep text out of cached layers.
- Text sizes: {{TEXT_SIZES}} These are the sizes as seen in the frame, after any zoom or scaling. Text that is
  only texture (a newspaper's body copy, the tiny cells of a title block) goes inside `Brush.texture(ctx, fn)`;
  anything the viewer has to read is a label and meets the sizes.
- Safe area: keep all text and the key action at least {{SAFE_TOP}} px below the top and {{SAFE_BOTTOM}} px above
  the bottom of the frame (`Brush.frame(W, H).safe` gives this area). Backgrounds may fill the whole frame.
- Fill the frame. In every beat the subject, its labels and the action spread over the whole safe area; no band of
  a quarter of its height or more is left as bare backdrop. In a vertical frame, stack and enlarge rather than
  shrink a landscape layout into the middle.
- Beats flow into each other. Carry subjects, colours or the camera from one beat into the next; use the
  reference's transitions. It should feel like one continuous piece, not a slideshow.
- Something always moves: idle objects drift, bob or breathe, as in the reference.
- Sound comes only from `sound.js` (synthesized, no audio files). Put a sound on each arrival and transition, as the
  reference does, and keep it sparse enough to stay pleasant.
{{EXTRA_RULES}}

## Before you hand it over

- Build the page and open it: the first frame is not blank, and nothing logs an error.
- Scrub through: text fits its boxes, nothing important leaves the safe area, every beat reads at a glance.
- Building the page runs the layout check (the command says what it found): labels too small, text outside the
  safe area, empty bands. Fix every finding in a new version of the module before anything is drawn.
- Seek to the same time twice: the frame is identical.
- The look matches the reference: put a frame of each side by side in your mind; the medium should be unmistakable.
