# TrendsMesh animation styles

Our own library of animation styles. An animation is one self-contained HTML page that draws every frame on a
canvas as a pure function of time, scores its own synthesized sound, renders to MP4 in the user's Chrome
(`atlas/render.mjs`) and plays for a person in a small built-in player.

```
lib/brush.js      window.Brush   shared drawing helpers (random, noise, easing, colour, textures, lines, text ...)
lib/sound.js      window.SOUND   synthesized effects, the score scheduler, offline render and live playback
lib/player.js     window.Player  the page runtime: registers a style, seek/DURATION/scoreSound, player, storyboard
lib/page.html     page template: {{TITLE}} {{FONTS_LINK}} {{CONFIG}} {{SCRIPTS}}
styles/NN_<id>.js one reference animation per style card (10-14 s), the style guide Claude copies the rendering of
prompt/*.md       the build prompt: build.md, then voiceover.md and/or storyboard.md, then card + code
```

## The page contract

The page sets `window.TM_PAGE = { width, height, mode: "play" | "storyboard", panels, voiceover }` before any script,
then inlines `brush.js`, `sound.js`, `player.js` (unchanged) and one style module, in that order.

- **Play mode**: one `<canvas id="stage">` at `width` x `height` (the largest canvas on the page; every other canvas
  is detached), `window.seek(t)` draws the frame at `t` seconds, `window.DURATION`, `window.scoreSound(k)`,
  `window.SOUND.renderOffline(...)`. A player bar (play/pause, scrub, time, sound, loop, safe-area guides; keys:
  space, arrows, G) sits under the canvas scaled to fit. Headless rendering only calls `seek`; it never needs the player.
- **Storyboard mode**: canvases `p1` ... `pN` at full size, one still per beat, `window.STORYBOARD_READY = true` once
  drawn, `window.makeSheet()` returns a PNG data URL contact sheet.
- Same `t`, same pixels: all randomness is seeded (`Brush.rng`, `Brush.hash01`), never `Math.random` or the clock.
- Fonts: the runtime calls `document.fonts.load` for every face in `fonts.faces` at once (so the font requests are
  part of page load), redraws when they arrive, and clears `Brush.layer` caches. Google Fonts is the only network use.

## A style module

```js
(function () {
  "use strict";
  const B = window.Brush;
  const PAL = { ... };                       // the card's palette
  const DUR = 12, BEATS = [0, 1.9, 4.0, 6.1, 8.4, 10.3];
  // style helpers (only this style needs them): name them clearly, comment what makes the medium read as real
  // subjects (the setting: the topic's things, replaced by Claude for each new topic)
  // layout(W, H): positions per aspect, from Brush.frame(W, H) (portrait vs landscape; never crop one layout)
  function draw(ctx, W, H, t) { /* whole frame at t; finishing passes last */ }
  function score(k) { /* sound */ }
  Player.register({
    id: "flat-explainer", name: "Flat Vector Explainer", duration: DUR,
    fonts: { href: "https://fonts.googleapis.com/css2?family=...&display=swap", faces: ['800 20px "Baloo 2"'] },
    beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three steps", "Rain returns", "Close"],
    // stills: [1.1, 3.2, ...]  optional exact storyboard panel times (default: 60 % into each beat)
    draw, score,
  });
})();
```

- `draw` gets a clean context (identity transform, cleared, alpha 1, source-over) every call; it must paint the
  whole frame. It may use offscreen canvases (`Brush.scratch`, `Brush.layer`); those are never in the DOM.
- Each reference shows: a title beat, a labelled diagram with an arrow, a key number, 2-3 process steps, a close;
  with the card's palette, fonts, finishing passes, motion and transitions. Text and key action stay inside
  `Brush.frame(W, H).safe` (portrait: not in the top 14 % or bottom 20 %). Check it at 1080x1920 and 1280x720.
- Topic: fresh and neutral (no brands, no real people). Facts must be right.
- A style that needs a sound of its own defines it in its module: `SOUND.define("comic-zip", (v, o) => {...})`
  (prefix the name with the style).
- Exemplars to copy the structure of: `styles/01_flat-explainer.js` (one world + a second scene, camera with
  parallax, wipe and whiteout transitions) and `styles/14_halftone-comic.js` (two printing plates drawn in parallel
  and composited, a panel strip with a gliding camera).

## Brush (window.Brush)

All sizes are canvas px; derive them from `F = Brush.frame(W, H)`: `F.u` = min(W, H) / 100, `F.safe` = `{ x, y, w, h,
r, b, cx, cy, top, bottom, side }`, `F.portrait`, `F.pick(landscapeValue, portraitValue)`. Points are `[x, y]`.

- **Numbers**: `clamp(v, a=0, b=1)`, `lerp`, `invLerp`, `map(v, a, b, c, d, clamp=true)`, `smooth(e0, e1, x)`, `fract`,
  `dist`, `deg`, `TAU`.
- **Random**: `rng(seed)` -> `r()` in [0,1) with `r.range(a,b)`, `r.int(a,b)`, `r.pick(arr)`, `r.gauss(m,sd)`,
  `r.chance(p)`, `r.sign()`, `r.shuffle(arr)`; `hash(...values)` (FNV-1a, uint32), `hash01(...values)` in [0,1).
- **Noise**: `noise2(x, y, seed)` and `noise1(x, seed)` in [-1,1] (value noise), `fbm(x, y, octaves=4, seed)`.
- **Time**: `ease.<name>(p)` (linear, in/out/inOut Quad, Cubic, Sine, Expo, outBack(p, s), inBack, outElastic,
  outBounce); `prog(t, start, dur, ease?)` 0..1; `span(t, a, b, ease?)`; `stagger(t, start, i, gap, dur, ease?)`;
  `alive(t, a, b, fin, fout)` fade envelope; `pop(t, start, dur=0.5, s)` overshoot scale; `spring(p, wiggles, damp)`;
  `wave(t, period, phase)`; `bob(t, amp, period, phase)`; `stepTime(t, fps)` held frames; `boil(t, fps)` integer for
  line boil seeds; `beat(t, beats, duration)` -> `{ i, start, end, len, local, p }`.
- **Colour**: `rgb(hex)` -> [r,g,b]; `rgba(hex, a)`; `mix(a, b, k)`; `shade(hex, k)` (+ lighter, - darker); `toHex`;
  `hsl(h,s,l,a)`; `lum(hex)`; `linear(ctx, x1,y1,x2,y2, stops)` / `radial(ctx, x,y, r0,r1, stops)` gradients
  (stops: colours, or `[stop, colour]` pairs).
- **Canvases**: `canvas(w,h)` detached; `layer(key, w, h, paint(g,w,h))` cached static layer; `clearLayers()`;
  `scratch(key, w, h)` -> a cleared per-frame offscreen context; `with(ctx, fn)`; `clip(ctx, pathFn, fn)`.
- **Texture text**: `texture(ctx, fn)`: text drawn inside fn is texture (body copy, tiny title-block cells), not a
  label; the layout check exempts it from the minimum size. Never for anything the viewer must read.
- **Textures and finishing** (screen space): `grain(ctx, W, H, { amount .08, t, fps, mode "overlay", scale, seed })`
  moving grain; `mottle(ctx, W, H, { amount .1, feature .12, seed, mode })` static soft blotches;
  `paper(ctx, W, H, { color, seed, mottle, fibers, specks, tooth })` cached sheet; `vignette(ctx, W, H, { amount,
  color, inner, mode })`; `scanlines(ctx, W, H, { gap, alpha, t })`; `dust(ctx, W, H, t, { count, hairs, scratches })`
  film dirt; `flicker(t, amount, fps, seed)` multiplier.
- **Light**: `glow(ctx, x, y, r, color, alpha, { add })`; `withShadow(ctx, { color, blur, x, y }, fn)`;
  `withFilter(ctx, "blur(4px)", fn)`; `contactShadow(ctx, x, y, rx, ry, alpha)`.
- **Print and pixels**: `halftone(ctx, x, y, w, h, { cell, angle, color, tone: n | fn(x,y), shape: "dot"|"line",
  jitter })`; `dotPattern(ctx, { cell, radius, color, bg, angle })` -> fillStyle; `hatch(ctx, x, y, w, h, { angle, gap,
  width, color, wobble, cross })`; `sprite(ctx, rows, x, y, cell, palette)`; `lowRes(ctx, W, H, cell, paint(g,w,h))`;
  `pixelGrid(ctx, W, H, cell, alpha)`; `iso(gx, gy, gz, unit, ox, oy)` -> [x,y]; `isoBox(ctx, ox, oy, unit, gx, gy,
  gz, sx, sy, sz, { color | top/left/right, edge })` (draw back to front by gx+gy+gz).
- **Shape paths** (add to the current path): `roundRect`, `capsule`, `circle`, `poly(ctx, pts, closed)`,
  `star(ctx, x, y, n, r1, r2, rot)`, `sparkle(ctx, x, y, r, pinch, rot)` four-point star, `smoothPath(ctx, pts, closed)`,
  `blob(ctx, cx, cy, r, { seed, wobble, n, t })`.
- **Point paths**: `pathLength`, `pointAt(pts, p)` -> [x, y, angle], `trim(pts, a, b)`, `densify(pts, step)`,
  `quad(...)`, `cubic(...)`, `arcBetween(x1, y1, x2, y2, bend)`, `arcPts(cx, cy, r, a0, a1, n)`, `rectPts`,
  `wobble(pts, { amp, freq, seed })` hand-drawn.
- **Strokes**: `strokeReveal(ctx, pts, p, { width, color, dash })` write-on; `handLine(ctx, pts, { width, color, amp,
  seed, passes, p })`, `handRect`, `handCircle`; `taperStroke(ctx, pts, { width, color, p, taperIn, taperOut, rough,
  roughScale, seed })` brush ribbon; `arrow(ctx, pts, { p, width, color, head, headStyle: "tri"|"open"|"round"|"none",
  dots, dash, rough, seed })` drawn on tail to head.
- **Text**: `font(size, family, weight, style)`; `wrap(ctx, text, maxW)`; `text(ctx, str, x, y, { size, minSize,
  family, weight, color, align, baseline, maxW, maxLines, lineH, letterSpacing, reveal, shadow: { x, y, blur, color },
  stroke, strokeW, alpha })` wraps and shrinks to fit, returns `{ size, lines, width, height, top, bottom }`;
  `measureText(ctx, str, o)`; `typewriter(str, p)`; `counter(p, to, { from, decimals, sep, prefix, suffix, ease })`.
- **Camera and transitions**: `camera(ctx, W, H, { x, y, zoom, rot }, fn, depth)` (`x, y` = scene point at frame
  centre; `depth` < 1 for parallax backgrounds); `zoomAt(ctx, x, y, zoom, fn)` zoom about a fixed point;
  `shake(t, amp, seed, freq)` -> [dx, dy]; `cover(ctx, W, H, color, alpha)`; `clipReveal(ctx, x, y, w, h, p, dir, fn)`;
  `iris(ctx, W, H, p, cx, cy, color)`.

## SOUND (window.SOUND)

A score is `score(k)`; `k` records events, which are then rendered offline (MP4) or live (player).

- `k.at(time, name, { gain = 1, pitch = 0 (semitones), pan = 0 (-1..1), verb (reverb send 0..1), dur, note })`
- `k.bed(name, start = 0, end = duration, opts)`: a bed; beds are left out with `voiceover: true`
- `k.chord(time, notes, { voice = "keys", strum })`, `k.seq(time, step, notes, { voice = "pluck" })` (notes: "A4",
  MIDI numbers, null = rest), `k.repeat(time, step, count, name, { jitter (s), vary (semitones) })`
- `k.custom(time, (v, o) => {...}, opts)` a one-off sound; `k.duration`, `k.voiceover`, `k.rng()` (seeded)
- Effects: tick click pop boop snap beep success error · pluck marimba keys chime bell ding sparkle chord gong twang
  drum · whoosh swish breath riser swell fall · thud boom impact knock stamp · paper rustle crumple flip marker
  scribble pencil chalk type typing shutter · bubble sonar · blip coin jump powerup crunch8 glitch static zap data
- Beds: pad drone wind room underwater hum crackle projector rain pulse arp (use `k.bed`)
- `SOUND.define(name, fn(v, o), { bed, verb })`: a new effect. The voice `v` has `v.tone({ type, f, f2, glide,
  fpath, at, a, hold, len, peak, shape, detune, dest })`, `v.noise({ filter, f, f2, q, brown, at, a, hold, len, peak })`,
  `v.grains({ at, span, count, len, peak, filter, f, q })`, `v.sub(name, offset, opts)`, `v.lfo(param, rate, depth,
  stopAt)`, `v.bedGain(dur, peak, fade)`, `v.hz(note)`, `v.rng()`, `v.ac`, `v.out`, `v.t`, `v.dur`.
- `SOUND.renderOffline(score, duration, sampleRate, { voiceover })` -> Promise `{ inter, peak, buffer }`;
  `SOUND.play(score, from, duration, { voiceover })` -> `{ stop(), time() }`; `SOUND.note("A4")` -> Hz;
  `SOUND.midi(n)`; `SOUND.scale(root, mode, count)` (modes: major minor dorian phrygian lydian mixolydian
  harmonicMinor pent minorPent blues whole); `SOUND.names()`; `SOUND.events(score, duration)` for debugging.
- `voiceover: true` plays every effect about 8 dB quieter and drops beds, so a narration sits on top.

## Adding a style

1. Write the card (palette, fonts, look, finish, motion, explaining, sound, avoid).
2. Copy the structure of an exemplar into `styles/NN_<styleId>.js` (NN = the card's `order`, two digits), keep
   `"use strict"` and an IIFE, no globals of its own.
3. Fill a page from `lib/page.html` (title, the fonts `<link>`, the config JSON, the four scripts), render it in both
   aspects as a storyboard and as an MP4 with `atlas/render.mjs` / `atlas/storyboard.mjs`, and look at the frames:
   it must read as the medium on the card, with legible text inside the safe area, sound, and no page errors.
