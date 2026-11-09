/* brush.js - shared drawing helpers for TrendsMesh style pages.
 *
 * Everything lives on window.Brush. Nothing here keeps per-frame state: every helper that varies over time takes `t`
 * (seconds) or a progress value, and every random choice comes from a seed, so a frame is a pure function of `t`.
 *
 * Units: helpers take canvas pixels. To stay resolution independent, size things from the frame:
 *   const F = Brush.frame(W, H);   // F.u = min(W, H) / 100, F.safe = the safe area, F.portrait ...
 *   ctx.lineWidth = 0.6 * F.u;
 *
 * Points are arrays [x, y]. A "path" (polyline) is an array of points.
 */
(function () {
  "use strict";
  const B = {};
  const TAU = Math.PI * 2;
  B.TAU = TAU;

  // ------------------------------------------------------------------ numbers
  B.clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  B.lerp = (a, b, k) => a + (b - a) * k;
  B.invLerp = (a, b, v) => B.clamp((v - a) / (b - a));
  /** Map v from [a, b] to [c, d]; clamped unless clamp is false. */
  B.map = (v, a, b, c, d, clamp = true) => {
    let k = (v - a) / (b - a);
    if (clamp) k = B.clamp(k);
    return c + (d - c) * k;
  };
  B.smooth = (e0, e1, x) => {
    const k = B.clamp((x - e0) / (e1 - e0));
    return k * k * (3 - 2 * k);
  };
  B.fract = (x) => x - Math.floor(x);
  B.dist = (x1, y1, x2, y2) => Math.hypot(x2 - x1, y2 - y1);
  B.deg = (d) => (d * Math.PI) / 180;

  // ------------------------------------------------------------------ seeded randomness
  /** FNV-1a hash of any values (numbers or strings) -> unsigned 32-bit int. */
  B.hash = function (...parts) {
    let h = 0x811c9dc5;
    for (const part of parts) {
      const s = String(part);
      for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 0x01000193);
      }
      h ^= 0x1f; // separator, so ("ab","c") differs from ("a","bc")
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  };
  /** Deterministic float in [0, 1) from any values: per-item jitter without keeping a generator. */
  B.hash01 = (...parts) => B.hash(...parts) / 4294967296;

  /**
   * Seeded generator (mulberry32). seed: integer or string.
   *   const r = Brush.rng("stars");  r() in [0,1), r.range(a,b), r.int(a,b) inclusive, r.pick(arr),
   *   r.gauss(mean, sd), r.chance(p), r.sign(), r.shuffle(arr) (returns a copy)
   * Make a fresh generator inside draw() (or per item) so the same t always gives the same numbers.
   */
  B.rng = function (seed = 1) {
    let a = typeof seed === "number" && Number.isFinite(seed) ? (Math.floor(seed) ^ 0x9e3779b9) >>> 0 : B.hash(seed);
    const r = function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    r.range = (lo, hi) => lo + (hi - lo) * r();
    r.int = (lo, hi) => Math.floor(lo + (hi - lo + 1) * r());
    r.pick = (arr) => arr[Math.floor(r() * arr.length)];
    r.chance = (p = 0.5) => r() < p;
    r.sign = () => (r() < 0.5 ? -1 : 1);
    r.gauss = (mean = 0, sd = 1) => {
      let u = 0;
      while (u === 0) u = r();
      return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * r());
    };
    r.shuffle = (arr) => {
      const out = arr.slice();
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(r() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
      }
      return out;
    };
    return r;
  };

  // ------------------------------------------------------------------ noise
  // Integer lattice hash for noise (fast path, no strings).
  function ih(x, y, s) {
    let h = (Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1) ^ Math.imul(s | 0, 0x9e3779b1)) | 0;
    h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
    h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  /** 2D value noise, smooth, in [-1, 1]. One feature per unit of x and y. */
  B.noise2 = function (x, y, seed = 0) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = ih(xi, yi, seed), b = ih(xi + 1, yi, seed), c = ih(xi, yi + 1, seed), d = ih(xi + 1, yi + 1, seed);
    return (a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v) * 2 - 1;
  };
  /** 1D value noise in [-1, 1]. */
  B.noise1 = (x, seed = 0) => B.noise2(x, 0, seed);
  /** Fractal (layered) value noise in about [-1, 1]. */
  B.fbm = function (x, y, octaves = 4, seed = 0) {
    let sum = 0, amp = 0.5, f = 1, norm = 0;
    for (let o = 0; o < octaves; o++) {
      sum += amp * B.noise2(x * f, y * f, seed + o * 131);
      norm += amp;
      amp *= 0.5;
      f *= 2.03;
    }
    return sum / norm;
  };

  // ------------------------------------------------------------------ easing and timing
  const E = (B.ease = {
    linear: (p) => p,
    inQuad: (p) => p * p,
    outQuad: (p) => 1 - (1 - p) * (1 - p),
    inOutQuad: (p) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2),
    inCubic: (p) => p * p * p,
    outCubic: (p) => 1 - Math.pow(1 - p, 3),
    inOutCubic: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    inSine: (p) => 1 - Math.cos((p * Math.PI) / 2),
    outSine: (p) => Math.sin((p * Math.PI) / 2),
    inOutSine: (p) => -(Math.cos(Math.PI * p) - 1) / 2,
    inExpo: (p) => (p === 0 ? 0 : Math.pow(2, 10 * p - 10)),
    outExpo: (p) => (p === 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    inOutExpo: (p) => (p === 0 ? 0 : p === 1 ? 1 : p < 0.5 ? Math.pow(2, 20 * p - 10) / 2 : (2 - Math.pow(2, -20 * p + 10)) / 2),
    /** Overshoots then settles. s = 1.70158 gives about 10 % overshoot; bigger s, bigger overshoot. */
    outBack: (p, s = 1.70158) => 1 + (s + 1) * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2),
    inBack: (p, s = 1.70158) => (s + 1) * p * p * p - s * p * p,
    outElastic: (p) => (p === 0 ? 0 : p === 1 ? 1 : Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * (TAU / 3)) + 1),
    outBounce: (p) => {
      const n = 7.5625, d = 2.75;
      if (p < 1 / d) return n * p * p;
      if (p < 2 / d) return n * (p -= 1.5 / d) * p + 0.75;
      if (p < 2.5 / d) return n * (p -= 2.25 / d) * p + 0.9375;
      return n * (p -= 2.625 / d) * p + 0.984375;
    },
  });
  const easeFn = (e) => (typeof e === "function" ? e : E[e] || E.linear);

  /** Progress 0..1 of t inside the window [start, start + dur], optionally eased (function or name in Brush.ease). */
  B.prog = (t, start, dur, ease) => {
    const p = dur <= 0 ? (t >= start ? 1 : 0) : B.clamp((t - start) / dur);
    return ease ? easeFn(ease)(p) : p;
  };
  /** Same as prog but between two times a and b. */
  B.span = (t, a, b, ease) => B.prog(t, a, b - a, ease);
  /** Progress of item i when items start `gap` seconds apart from `start`, each taking `dur`. */
  B.stagger = (t, start, i, gap, dur, ease) => B.prog(t, start + i * gap, dur, ease);
  /** Visibility envelope: fades in at a (over fin), holds, fades out to end at b (over fout). 0..1. */
  B.alive = (t, a, b, fin = 0.3, fout = 0.3) => Math.min(B.prog(t, a, fin, "inOutSine"), 1 - B.prog(t, b - fout, fout, "inOutSine"));
  /** Pop-in scale: 0 before start, overshoots ~10 % (s = 1.70158), settles at 1 after dur. */
  B.pop = (t, start, dur = 0.5, s = 1.70158) => (t <= start ? 0 : E.outBack(B.prog(t, start, dur), s));
  /** Damped spring on a progress p (0..1): rises, overshoots, wobbles `wiggles` times, settles at 1. */
  B.spring = (p, wiggles = 1.5, damp = 5) => (p <= 0 ? 0 : p >= 1 ? 1 : 1 - Math.exp(-damp * p) * Math.cos(wiggles * TAU * p * 0.5));
  /** Sine wave in [-1, 1] with a period in seconds. */
  B.wave = (t, period = 2, phase = 0) => Math.sin(TAU * (t / period + phase));
  /** Idle bob: amp * sine; give each object its own phase so they do not move in lockstep. */
  B.bob = (t, amp, period = 2.4, phase = 0) => amp * Math.sin(TAU * (t / period + phase));
  /** Hold time on a lower frame rate (stop-motion "on twos" = fps 12). */
  B.stepTime = (t, fps = 12) => Math.floor(t * fps + 1e-6) / fps;
  /** Integer that changes `fps` times a second: use as a seed for hand-drawn line boil. */
  B.boil = (t, fps = 8) => Math.floor(t * fps + 1e-6);
  /**
   * Where t falls among beat start times: { i, start, end, local (seconds into the beat), p (0..1), len }.
   * end of the last beat is `duration`.
   */
  B.beat = function (t, beats, duration) {
    let i = 0;
    while (i + 1 < beats.length && t >= beats[i + 1]) i++;
    const start = beats[i], end = i + 1 < beats.length ? beats[i + 1] : duration;
    const len = Math.max(1e-6, end - start);
    return { i, start, end, len, local: t - start, p: B.clamp((t - start) / len) };
  };

  // ------------------------------------------------------------------ colour
  const colourCache = new Map();
  /** "#rgb" | "#rrggbb" | "#rrggbbaa" | [r,g,b] -> [r, g, b] (0..255). */
  B.rgb = function (c) {
    if (Array.isArray(c)) return c;
    let v = colourCache.get(c);
    if (v) return v;
    let h = String(c).trim().replace("#", "");
    if (h.length === 3 || h.length === 4) h = h.split("").map((x) => x + x).join("");
    v = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    if (v.some((n) => Number.isNaN(n))) v = [255, 0, 255];
    colourCache.set(c, v);
    return v;
  };
  B.toHex = (rgb) => "#" + rgb.map((n) => Math.round(B.clamp(n, 0, 255)).toString(16).padStart(2, "0")).join("");
  /** Hex colour with alpha -> "rgba(...)". */
  B.rgba = (c, a = 1) => {
    const [r, g, b] = B.rgb(c);
    return `rgba(${r},${g},${b},${B.clamp(a)})`;
  };
  /** Mix two colours (k = 0 gives a, 1 gives b) -> hex. */
  B.mix = (a, b, k) => {
    const x = B.rgb(a), y = B.rgb(b);
    return B.toHex([B.lerp(x[0], y[0], k), B.lerp(x[1], y[1], k), B.lerp(x[2], y[2], k)]);
  };
  /** Lighten (k > 0, towards white) or darken (k < 0, towards black) -> hex. */
  B.shade = (c, k) => (k >= 0 ? B.mix(c, "#ffffff", k) : B.mix(c, "#000000", -k));
  B.hsl = (h, s, l, a = 1) => `hsla(${h},${s}%,${l}%,${a})`;
  /** Relative luminance 0..1 (pick dark or light text over a colour). */
  B.lum = (c) => {
    const [r, g, b] = B.rgb(c).map((n) => {
      n /= 255;
      return n <= 0.03928 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  /** Linear gradient between two points from a list of colours (evenly spaced) or [[stop, colour], ...]. */
  B.linear = (ctx, x1, y1, x2, y2, stops) => {
    const g = ctx.createLinearGradient(x1, y1, x2, y2);
    stops.forEach((s, i) => (Array.isArray(s) ? g.addColorStop(s[0], s[1]) : g.addColorStop(stops.length === 1 ? 0 : i / (stops.length - 1), s)));
    return g;
  };
  B.radial = (ctx, x, y, r0, r1, stops) => {
    const g = ctx.createRadialGradient(x, y, r0, x, y, r1);
    stops.forEach((s, i) => (Array.isArray(s) ? g.addColorStop(s[0], s[1]) : g.addColorStop(stops.length === 1 ? 0 : i / (stops.length - 1), s)));
    return g;
  };

  // ------------------------------------------------------------------ frame layout
  /**
   * Layout facts for a W x H frame:
   *   { W, H, u, portrait, aspect, cx, cy, safe: { x, y, w, h, top, bottom, side, cx, cy, r, b }, pick(landscape, portrait) }
   * The safe area keeps text and key action clear of platform UI: portrait 14 % top, 20 % bottom, 6 % sides;
   * landscape 8 % top, 10 % bottom, 5 % sides. Lay out by aspect (use F.pick), never by cropping one layout.
   */
  B.frame = function (W, H) {
    const portrait = H > W;
    const top = Math.round(H * (portrait ? 0.14 : 0.08));
    const bottom = Math.round(H * (portrait ? 0.2 : 0.1));
    const side = Math.round(W * (portrait ? 0.06 : 0.05));
    const safe = { x: side, y: top, w: W - 2 * side, h: H - top - bottom, top, bottom, side };
    safe.cx = safe.x + safe.w / 2;
    safe.cy = safe.y + safe.h / 2;
    safe.r = safe.x + safe.w;
    safe.b = safe.y + safe.h;
    return { W, H, u: Math.min(W, H) / 100, portrait, aspect: W / H, cx: W / 2, cy: H / 2, safe, pick: (land, port) => (portrait ? port : land) };
  };

  // ------------------------------------------------------------------ offscreen canvases and cached layers
  /** A detached canvas (never in the DOM, so it is never mistaken for the frame). */
  B.canvas = (w, h) => {
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w));
    c.height = Math.max(1, Math.round(h));
    return c;
  };
  const layers = new Map();
  /**
   * Cached static layer: paint(ctx, w, h) runs once per (key, w, h); later calls return the same canvas.
   * Put everything that does not change over time here (paper, backdrops, textures). Keep text out of cached
   * layers, or include the font in the key; the runtime clears the cache once web fonts have loaded.
   */
  B.layer = function (key, w, h, paint) {
    w = Math.max(1, Math.round(w));
    h = Math.max(1, Math.round(h));
    const k = key + "@" + w + "x" + h;
    let c = layers.get(k);
    if (!c) {
      c = B.canvas(w, h);
      paint(c.getContext("2d"), w, h);
      layers.set(k, c);
    }
    return c;
  };
  B.clearLayers = () => layers.clear();
  /** A reusable scratch canvas of a size (cleared on each call): for per-frame offscreen work. */
  B.scratch = function (key, w, h) {
    const c = B.layer("scratch:" + key, w, h, () => {});
    const g = c.getContext("2d");
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha = 1;
    g.globalCompositeOperation = "source-over";
    g.clearRect(0, 0, c.width, c.height);
    return g;
  };
  /** Run fn with ctx saved and restored. */
  B.with = (ctx, fn) => {
    ctx.save();
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };
  /**
   * Text drawn inside fn is texture, not a label: newspaper body copy, the tiny cells of a title block, a
   * wall of code. The layout check (atlas/layout_check.mjs) exempts it from the minimum text size and lists
   * how much there is. Never use it for anything the viewer has to read to follow the story.
   */
  B.texture = (ctx, fn) => {
    const was = ctx.__tmTexture;
    ctx.__tmTexture = true;
    try {
      return fn(ctx);
    } finally {
      ctx.__tmTexture = was;
    }
  };
  /** Clip to the path that pathFn adds, then run fn. */
  B.clip = (ctx, pathFn, fn) => {
    ctx.save();
    ctx.beginPath();
    pathFn(ctx);
    ctx.clip();
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };

  // ------------------------------------------------------------------ textures and finishing passes
  // Finishing passes (grain, mottle, vignette, scanlines, dust) work in screen space: they reset the transform.

  function noiseTile(seed, size, mono) {
    return B.layer("grainTile:" + seed + ":" + mono, size, size, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(seed);
      for (let i = 0; i < w * h; i++) {
        const v = r() * 255;
        d[i * 4] = v;
        d[i * 4 + 1] = mono ? v : r() * 255;
        d[i * 4 + 2] = mono ? v : r() * 255;
        d[i * 4 + 3] = 255;
      }
      g.putImageData(img, 0, 0);
    });
  }
  /**
   * Fine film/print grain over the whole frame. Moving grain: pass t (the grain re-offsets every frame at fps).
   * o: { amount 0.08, t, fps 24, mode "overlay", scale (grain size; default grows with frame size), seed, mono true }
   */
  B.grain = function (ctx, W, H, o = {}) {
    const amount = o.amount ?? 0.08;
    if (amount <= 0) return;
    const seed = o.seed ?? 7, size = 256;
    const scale = o.scale ?? Math.max(1, Math.min(W, H) / 720);
    const tile = noiseTile(seed, size, o.mono !== false);
    const f = o.t == null ? 0 : Math.floor(o.t * (o.fps ?? 24) + 1e-6);
    const ox = B.hash01(f, "gx", seed) * size, oy = B.hash01(f, "gy", seed) * size;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = o.mode || "overlay";
    ctx.globalAlpha = amount;
    const pat = ctx.createPattern(tile, "repeat");
    pat.setTransform(new DOMMatrix([scale, 0, 0, scale, -ox * scale, -oy * scale]));
    ctx.fillStyle = pat;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  };

  /** Low-resolution soft cloud field (grey), cached. feature: blob size as a fraction of min(W, H). */
  function mottleLayer(W, H, feature, octaves, seed) {
    const cell = Math.max(2, Math.round(Math.min(W, H) / 160));
    return B.layer(`mottle:${feature}:${octaves}:${seed}`, Math.ceil(W / cell), Math.ceil(H / cell), (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data;
      const s = 1 / ((feature * Math.min(W, H)) / cell);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const v = 0.5 + 0.5 * B.clamp(B.fbm(x * s, y * s, octaves, seed) * 1.7, -1, 1);
          const i = (y * w + x) * 4;
          d[i] = d[i + 1] = d[i + 2] = v * 255;
          d[i + 3] = 255;
        }
      g.putImageData(img, 0, 0);
    });
  }
  /**
   * Static large-scale soft mottle so big flat areas feel printed or painted rather than digital.
   * o: { amount 0.1, feature 0.12, octaves 4, seed 11, mode "overlay" }
   */
  B.mottle = function (ctx, W, H, o = {}) {
    const amount = o.amount ?? 0.1;
    if (amount <= 0) return;
    const m = mottleLayer(W, H, o.feature ?? 0.12, o.octaves ?? 4, o.seed ?? 11);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = o.mode || "overlay";
    ctx.globalAlpha = amount;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(m, 0, 0, W, H);
    ctx.restore();
  };

  /**
   * Paper sheet filling the frame (cached): base colour, cloudy mottle, fibres, specks and fine tooth.
   * o: { color "#f3ead8", seed 3, mottle 0.12, fibers 0.35, specks 0.3, tooth 0.08, fiberColor }
   */
  B.paper = function (ctx, W, H, o = {}) {
    const color = o.color || "#f3ead8", seed = o.seed ?? 3;
    const key = `paper:${color}:${seed}:${o.mottle}:${o.fibers}:${o.specks}:${o.tooth}:${o.fiberColor}`;
    const c = B.layer(key, W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(seed);
      g.fillStyle = color;
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: o.mottle ?? 0.12, feature: 0.2, seed: seed + 1, mode: "soft-light" });
      B.mottle(g, w, h, { amount: (o.mottle ?? 0.12) * 0.6, feature: 0.04, seed: seed + 2, mode: "soft-light" });
      const fib = o.fiberColor || B.shade(color, -0.35);
      const nf = Math.round(((w * h) / (u * u)) * 0.12 * (o.fibers ?? 0.35));
      g.lineCap = "round";
      for (let i = 0; i < nf; i++) {
        const x = r() * w, y = r() * h, a = r() * TAU, len = r.range(0.4, 2.2) * u;
        g.strokeStyle = r() < 0.5 ? B.rgba(fib, 0.12) : B.rgba("#ffffff", 0.18);
        g.lineWidth = r.range(0.04, 0.12) * u;
        g.beginPath();
        g.moveTo(x, y);
        g.quadraticCurveTo(x + Math.cos(a + 0.6) * len * 0.5, y + Math.sin(a + 0.6) * len * 0.5, x + Math.cos(a) * len, y + Math.sin(a) * len);
        g.stroke();
      }
      const ns = Math.round(((w * h) / (u * u)) * 0.05 * (o.specks ?? 0.3));
      for (let i = 0; i < ns; i++) {
        g.fillStyle = B.rgba(fib, r.range(0.1, 0.35));
        g.beginPath();
        g.arc(r() * w, r() * h, r.range(0.03, 0.12) * u, 0, TAU);
        g.fill();
      }
      B.grain(g, w, h, { amount: o.tooth ?? 0.08, seed: seed + 5, mode: "soft-light" });
    });
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(c, 0, 0);
    ctx.restore();
  };

  /** Darken (or tint) the frame edges. o: { amount 0.45, color "#000", inner 0.45, cx, cy, mode } */
  B.vignette = function (ctx, W, H, o = {}) {
    const amount = o.amount ?? 0.45, color = o.color || "#000000";
    const cx = o.cx ?? W / 2, cy = o.cy ?? H / 2, R = Math.hypot(W, H) / 2;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (o.mode) ctx.globalCompositeOperation = o.mode;
    ctx.fillStyle = B.radial(ctx, cx, cy, R * (o.inner ?? 0.45), R, [[0, B.rgba(color, 0)], [1, B.rgba(color, amount)]]);
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  };

  /** Soft radial glow sprite (in scene space). o: { add: true uses additive "lighter" blending, core 0.35 } */
  B.glow = function (ctx, x, y, r, color, alpha = 1, o = {}) {
    if (r <= 0 || alpha <= 0) return;
    ctx.save();
    if (o.add) ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = B.radial(ctx, x, y, 0, r, [[0, B.rgba(color, alpha)], [o.core ?? 0.35, B.rgba(color, alpha * 0.45)], [1, B.rgba(color, 0)]]);
    ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
    ctx.restore();
  };
  /** Run fn with a canvas shadow set. o: { color, blur (px), x, y }. Neon glow = bright colour, x = y = 0. */
  B.withShadow = function (ctx, o, fn) {
    ctx.save();
    ctx.shadowColor = o.color || "rgba(0,0,0,0.35)";
    ctx.shadowBlur = o.blur ?? 0;
    ctx.shadowOffsetX = o.x ?? 0;
    ctx.shadowOffsetY = o.y ?? 0;
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };
  /** Run fn with a CSS filter (e.g. "blur(6px)"); costs time at large sizes, use on small areas or sparingly. */
  B.withFilter = function (ctx, filter, fn) {
    ctx.save();
    ctx.filter = filter;
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };
  /** Soft elliptical contact shadow under an object resting at (x, y). */
  B.contactShadow = function (ctx, x, y, rx, ry, alpha = 0.3, color = "#000000") {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(1, ry / rx);
    ctx.fillStyle = B.radial(ctx, 0, 0, 0, rx, [[0, B.rgba(color, alpha)], [0.6, B.rgba(color, alpha * 0.5)], [1, B.rgba(color, 0)]]);
    ctx.fillRect(-rx, -rx, 2 * rx, 2 * rx);
    ctx.restore();
  };

  /** Horizontal CRT scanlines. o: { gap (px, default ~0.4u), alpha 0.18, color "#000", t (rolls a bright band when given) } */
  B.scanlines = function (ctx, W, H, o = {}) {
    const gap = Math.max(2, Math.round(o.gap ?? Math.min(W, H) / 250));
    const tile = B.layer("scan:" + gap + ":" + (o.color || "#000"), 4, gap, (g, w, h) => {
      g.fillStyle = o.color || "#000";
      g.fillRect(0, 0, w, Math.max(1, Math.round(h / 2)));
    });
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = o.alpha ?? 0.18;
    ctx.fillStyle = ctx.createPattern(tile, "repeat");
    ctx.fillRect(0, 0, W, H);
    if (o.t != null) {
      const y = B.fract(o.t / (o.period ?? 6)) * (H * 1.4) - H * 0.2;
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = B.linear(ctx, 0, y - H * 0.08, 0, y + H * 0.08, ["rgba(255,255,255,0)", "rgba(255,255,255,0.05)", "rgba(255,255,255,0)"]);
      ctx.fillRect(0, y - H * 0.08, W, H * 0.16);
    }
    ctx.restore();
  };

  /**
   * Old-film dirt: specks, hairs and the odd vertical scratch, new every frame (at fps).
   * o: { fps 24, count 10, hairs 1, scratches 0.4 (chance per frame), color "#000", alpha 0.55, seed 0 }
   */
  B.dust = function (ctx, W, H, t, o = {}) {
    const f = Math.floor(t * (o.fps ?? 24) + 1e-6), r = B.rng(B.hash("dust", f, o.seed ?? 0));
    const u = Math.min(W, H) / 100, col = o.color || "#000000", al = o.alpha ?? 0.55;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const n = Math.round((o.count ?? 10) * r.range(0.3, 1.2));
    for (let i = 0; i < n; i++) {
      ctx.fillStyle = B.rgba(col, al * r.range(0.4, 1));
      ctx.beginPath();
      ctx.ellipse(r() * W, r() * H, r.range(0.05, 0.35) * u, r.range(0.05, 0.3) * u, r() * TAU, 0, TAU);
      ctx.fill();
    }
    ctx.lineCap = "round";
    for (let i = 0; i < (o.hairs ?? 1); i++) {
      if (!r.chance(0.5)) continue;
      const x = r() * W, y = r() * H, len = r.range(2, 6) * u, a = r() * TAU;
      ctx.strokeStyle = B.rgba(col, al * 0.7);
      ctx.lineWidth = 0.12 * u;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.bezierCurveTo(x + r.gauss(0, len), y + r.gauss(0, len), x + r.gauss(0, len), y + r.gauss(0, len), x + Math.cos(a) * len, y + Math.sin(a) * len);
      ctx.stroke();
    }
    if (r.chance(o.scratches ?? 0.4)) {
      const x = r() * W;
      ctx.strokeStyle = B.rgba(o.scratchColor || "#ffffff", al * 0.5);
      ctx.lineWidth = r.range(0.06, 0.18) * u;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + r.gauss(0, u), H);
      ctx.stroke();
    }
    ctx.restore();
  };
  /** Brightness flicker multiplier around 1 (old projectors, candles, neon). */
  B.flicker = (t, amount = 0.05, fps = 24, seed = 0) => 1 + (B.hash01("flk", Math.floor(t * fps + 1e-6), seed) - 0.5) * 2 * amount;

  // ------------------------------------------------------------------ print screens: halftone, hatching
  /**
   * Halftone dots over a rectangle on a rotated grid; dot area follows tone (0 = paper, 1 = solid).
   * tone: a number, or fn(x, y) -> 0..1 in canvas coordinates (a shading gradient, a light direction ...).
   * Clip first to fill a shape. o: { cell (px), angle (deg) 45, color, tone, shape "dot" | "line", jitter 0 }
   */
  B.halftone = function (ctx, x, y, w, h, o = {}) {
    const cell = Math.max(1.5, o.cell ?? 10), ang = B.deg(o.angle ?? 45), tone = o.tone ?? 0.5;
    const ca = Math.cos(ang), sa = Math.sin(ang);
    const cx = x + w / 2, cy = y + h / 2, n = Math.ceil(Math.hypot(w, h) / 2 / cell) + 1;
    const fnTone = typeof tone === "function";
    ctx.save();
    ctx.fillStyle = o.color || "#000";
    ctx.beginPath();
    for (let i = -n; i <= n; i++)
      for (let j = -n; j <= n; j++) {
        const gx = i * cell, gy = j * cell;
        const px = cx + gx * ca - gy * sa, py = cy + gx * sa + gy * ca;
        if (px < x - cell || px > x + w + cell || py < y - cell || py > y + h + cell) continue;
        const v = B.clamp(fnTone ? tone(px, py) : tone);
        if (v <= 0.005) continue;
        if (o.shape === "line") {
          // line screen: bars along the grid direction, thickness follows tone
          const th = v * cell;
          ctx.save();
          ctx.translate(px, py);
          ctx.rotate(ang);
          ctx.rect(-cell / 2, -th / 2, cell + 0.5, th);
          ctx.restore();
        } else {
          const rr = Math.min(cell * 0.72, cell * Math.sqrt(v / Math.PI) * 1.04);
          const jx = o.jitter ? (B.hash01(i, j, "hx") - 0.5) * o.jitter * cell : 0;
          const jy = o.jitter ? (B.hash01(i, j, "hy") - 0.5) * o.jitter * cell : 0;
          ctx.moveTo(px + jx + rr, py + jy);
          ctx.arc(px + jx, py + jy, rr, 0, TAU);
        }
      }
    ctx.fill();
    ctx.restore();
  };
  /**
   * A repeating pattern of even dots (one flat tone), fast to fill any path with: ctx.fillStyle = Brush.dotPattern(...).
   * o: { cell, radius (px), color, bg (null = transparent), angle (deg) 45 }
   */
  B.dotPattern = function (ctx, o = {}) {
    const cell = Math.max(2, Math.round(o.cell ?? 10)), rad = o.radius ?? cell * 0.3;
    const tile = B.layer(`dots:${cell}:${rad}:${o.color}:${o.bg}`, cell, cell, (g, w, h) => {
      if (o.bg) {
        g.fillStyle = o.bg;
        g.fillRect(0, 0, w, h);
      }
      g.fillStyle = o.color || "#000";
      g.beginPath();
      g.arc(w / 2, h / 2, rad, 0, TAU);
      g.fill();
    });
    const pat = ctx.createPattern(tile, "repeat");
    pat.setTransform(new DOMMatrix().rotate(o.angle ?? 45));
    return pat;
  };
  /**
   * Parallel hatching lines over a rectangle (clip to a shape first). For pencil, engraving, ink shading.
   * o: { angle (deg) 45, gap (px), width (px), color, wobble (px) 0, seed, cross false (adds a second set at +90) }
   */
  B.hatch = function (ctx, x, y, w, h, o = {}) {
    const gap = Math.max(1, o.gap ?? 6), ang = B.deg(o.angle ?? 45), wob = o.wobble ?? 0, seed = o.seed ?? 1;
    const sets = o.cross ? [ang, ang + Math.PI / 2] : [ang];
    ctx.save();
    ctx.strokeStyle = o.color || "#000";
    ctx.lineWidth = o.width ?? 1;
    ctx.lineCap = "round";
    const cx = x + w / 2, cy = y + h / 2, R = Math.hypot(w, h) / 2;
    sets.forEach((a, si) => {
      const ca = Math.cos(a), sa = Math.sin(a);
      ctx.beginPath();
      for (let d = -R, k = 0; d <= R; d += gap, k++) {
        const steps = wob ? 12 : 1;
        for (let s = 0; s <= steps; s++) {
          const along = -R + (2 * R * s) / steps;
          const off = wob ? B.noise2(k * 0.37, s * 0.5, seed + si) * wob : 0;
          const px = cx + along * ca - (d + off) * sa, py = cy + along * sa + (d + off) * ca;
          if (s === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
      }
      ctx.stroke();
    });
    ctx.restore();
  };

  // ------------------------------------------------------------------ pixels and voxels
  /**
   * Pixel-art sprite from strings: rows like ["..aa..", ".abba."], palette { a: "#f00", b: "#fff" }.
   * "." and " " are transparent. (x, y) is the top-left; cell is the size of one pixel.
   */
  B.sprite = function (ctx, rows, x, y, cell, palette) {
    for (let j = 0; j < rows.length; j++) {
      const row = rows[j];
      for (let i = 0; i < row.length; i++) {
        const ch = row[i];
        if (ch === "." || ch === " " || !palette[ch]) continue;
        ctx.fillStyle = palette[ch];
        ctx.fillRect(Math.round(x + i * cell), Math.round(y + j * cell), Math.ceil(cell), Math.ceil(cell));
      }
    }
  };
  /**
   * Draw at low resolution and blow it up with hard pixels: paint(lctx, w, h) draws into a canvas
   * of ceil(W / cell) x ceil(H / cell); the result covers the frame. True chunky pixels for 8-bit looks.
   */
  B.lowRes = function (ctx, W, H, cell, paint) {
    const w = Math.ceil(W / cell), h = Math.ceil(H / cell);
    const g = B.scratch("lowres", w, h);
    g.imageSmoothingEnabled = false;
    paint(g, w, h);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(g.canvas, 0, 0, w * cell, h * cell);
    ctx.restore();
  };
  /** Faint pixel grid lines over the frame (LCD / graph paper). */
  B.pixelGrid = function (ctx, W, H, cell, alpha = 0.12, color = "#000000") {
    const c = Math.max(2, Math.round(cell));
    const tile = B.layer("pgrid:" + c + color, c, c, (g, w, h) => {
      g.fillStyle = color;
      g.fillRect(0, 0, w, 1);
      g.fillRect(0, 0, 1, h);
    });
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = ctx.createPattern(tile, "repeat");
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  };
  /**
   * Isometric projection of grid point (gx, gy, gz) -> [x, y]. x runs right-down, y left-down, z up.
   * unit is the length of one grid step in px; (ox, oy) is where grid (0, 0, 0) lands.
   */
  B.iso = (gx, gy, gz, unit, ox = 0, oy = 0) => [ox + (gx - gy) * unit * 0.866, oy + (gx + gy) * unit * 0.5 - gz * unit];
  /**
   * Isometric box with its three visible faces. Box spans gx..gx+sx, gy..gy+sy, gz..gz+sz.
   * o: { color (base) or top / left / right colours, edge (stroke colour or null), edgeW }
   * Draw several boxes back to front: sort by gx + gy + gz ascending.
   */
  B.isoBox = function (ctx, ox, oy, unit, gx, gy, gz, sx, sy, sz, o = {}) {
    const P = (x, y, z) => B.iso(x, y, z, unit, ox, oy);
    const base = o.color || "#8899aa";
    const faces = [
      [o.left || base, [P(gx, gy + sy, gz), P(gx + sx, gy + sy, gz), P(gx + sx, gy + sy, gz + sz), P(gx, gy + sy, gz + sz)]],
      [o.right || B.shade(base, -0.25), [P(gx + sx, gy, gz), P(gx + sx, gy + sy, gz), P(gx + sx, gy + sy, gz + sz), P(gx + sx, gy, gz + sz)]],
      [o.top || B.shade(base, 0.2), [P(gx, gy, gz + sz), P(gx + sx, gy, gz + sz), P(gx + sx, gy + sy, gz + sz), P(gx, gy + sy, gz + sz)]],
    ];
    ctx.save();
    ctx.lineJoin = "round";
    for (const [col, pts] of faces) {
      ctx.beginPath();
      B.poly(ctx, pts, true);
      ctx.fillStyle = col;
      ctx.fill();
      if (o.edge) {
        ctx.strokeStyle = o.edge;
        ctx.lineWidth = o.edgeW ?? 1;
        ctx.stroke();
      }
    }
    ctx.restore();
  };

  // ------------------------------------------------------------------ shape paths (add to the current path; you fill/stroke)
  B.roundRect = function (ctx, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  };
  /** Pill / capsule: fully rounded ends. */
  B.capsule = (ctx, x, y, w, h) => B.roundRect(ctx, x, y, w, h, Math.min(w, h) / 2);
  B.circle = (ctx, x, y, r) => {
    ctx.moveTo(x + r, y);
    ctx.arc(x, y, Math.max(0, r), 0, TAU);
  };
  /** Polygon or polyline through points. */
  B.poly = function (ctx, pts, closed = false) {
    pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
    if (closed) ctx.closePath();
  };
  /** Regular star: n points, outer radius r1, inner r2, rotation rot (rad). */
  B.star = function (ctx, x, y, n, r1, r2, rot = -Math.PI / 2) {
    for (let i = 0; i < n * 2; i++) {
      const a = rot + (i * Math.PI) / n, r = i % 2 ? r2 : r1;
      i ? ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r) : ctx.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
    }
    ctx.closePath();
  };
  /** Four-point sparkle with pinched, concave sides. pinch 0..1: smaller = thinner rays. */
  B.sparkle = function (ctx, x, y, r, pinch = 0.18, rot = 0) {
    const tips = [0, 1, 2, 3].map((i) => rot - Math.PI / 2 + (i * Math.PI) / 2);
    ctx.moveTo(x + Math.cos(tips[0]) * r, y + Math.sin(tips[0]) * r);
    for (let i = 0; i < 4; i++) {
      const a1 = tips[(i + 1) % 4], mid = tips[i] + Math.PI / 4;
      ctx.quadraticCurveTo(x + Math.cos(mid) * r * pinch, y + Math.sin(mid) * r * pinch, x + Math.cos(a1) * r, y + Math.sin(a1) * r);
    }
    ctx.closePath();
  };
  /** Smooth curve through points (Catmull-Rom as Beziers). tension 0.5 is standard. */
  B.smoothPath = function (ctx, pts, closed = false, tension = 0.5) {
    const n = pts.length;
    if (n < 2) return;
    const P = (i) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
    ctx.moveTo(pts[0][0], pts[0][1]);
    const last = closed ? n : n - 1;
    for (let i = 0; i < last; i++) {
      const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2), k = tension / 3;
      ctx.bezierCurveTo(p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k, p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k, p2[0], p2[1]);
    }
    if (closed) ctx.closePath();
  };
  /** Organic closed blob around (cx, cy). o: { seed, wobble 0.15 (fraction of r), n 9, t (animates), speed 0.3 } */
  B.blob = function (ctx, cx, cy, r, o = {}) {
    const n = o.n ?? 9, wob = o.wobble ?? 0.15, seed = o.seed ?? 1, tt = (o.t ?? 0) * (o.speed ?? 0.3);
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * TAU, k = 1 + wob * B.noise2(Math.cos(a) * 1.3 + tt, Math.sin(a) * 1.3 - tt, seed);
      pts.push([cx + Math.cos(a) * r * k, cy + Math.sin(a) * r * k]);
    }
    B.smoothPath(ctx, pts, true);
  };

  // ------------------------------------------------------------------ point paths (polylines)
  B.pathLength = function (pts) {
    let L = 0;
    for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    return L;
  };
  /** Point at fraction p of a polyline's length -> [x, y, angle]. */
  B.pointAt = function (pts, p) {
    const L = B.pathLength(pts);
    let want = B.clamp(p) * L;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i], seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (want <= seg || i === pts.length - 1) {
        const k = seg > 0 ? B.clamp(want / seg) : 0;
        return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, Math.atan2(b[1] - a[1], b[0] - a[0])];
      }
      want -= seg;
    }
    const q = pts[pts.length - 1] || [0, 0];
    return [q[0], q[1], 0];
  };
  /** The part of a polyline between fractions a and b of its length (for write-on reveals). */
  B.trim = function (pts, a, b) {
    if (pts.length < 2) return pts.slice();
    a = B.clamp(a);
    b = B.clamp(b);
    if (b <= a) return [];
    const L = B.pathLength(pts), A = a * L, Bv = b * L, out = [];
    let acc = 0;
    for (let i = 1; i < pts.length; i++) {
      const p = pts[i - 1], q = pts[i], seg = Math.hypot(q[0] - p[0], q[1] - p[1]);
      const s0 = acc, s1 = acc + seg;
      if (s1 >= A && s0 <= Bv && seg > 0) {
        const k0 = B.clamp((A - s0) / seg), k1 = B.clamp((Bv - s0) / seg);
        if (!out.length) out.push([p[0] + (q[0] - p[0]) * k0, p[1] + (q[1] - p[1]) * k0]);
        out.push([p[0] + (q[0] - p[0]) * k1, p[1] + (q[1] - p[1]) * k1]);
      }
      acc = s1;
      if (acc > Bv) break;
    }
    return out;
  };
  /** Add points so no segment is longer than step px (so wobble has somewhere to act). */
  B.densify = function (pts, step) {
    const out = [];
    for (let i = 0; i < pts.length; i++) {
      if (i) {
        const a = pts[i - 1], b = pts[i], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / step));
        for (let k = 1; k < n; k++) out.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]);
      }
      out.push(pts[i].slice(0, 2));
    }
    return out;
  };
  /** Points along a quadratic curve. */
  B.quad = function (x1, y1, cx, cy, x2, y2, n = 32) {
    const out = [];
    for (let i = 0; i <= n; i++) {
      const s = i / n, m = 1 - s;
      out.push([m * m * x1 + 2 * m * s * cx + s * s * x2, m * m * y1 + 2 * m * s * cy + s * s * y2]);
    }
    return out;
  };
  /** Points along a cubic Bezier. */
  B.cubic = function (x1, y1, c1x, c1y, c2x, c2y, x2, y2, n = 40) {
    const out = [];
    for (let i = 0; i <= n; i++) {
      const s = i / n, m = 1 - s;
      out.push([m * m * m * x1 + 3 * m * m * s * c1x + 3 * m * s * s * c2x + s * s * s * x2, m * m * m * y1 + 3 * m * m * s * c1y + 3 * m * s * s * c2y + s * s * s * y2]);
    }
    return out;
  };
  /** A gently bent path from (x1, y1) to (x2, y2): bend is the sideways bulge as a fraction of the distance. */
  B.arcBetween = function (x1, y1, x2, y2, bend = 0.2, n = 36) {
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
    return B.quad(x1, y1, mx - dy * bend, my + dx * bend, x2, y2, n);
  };
  /** Points around a circle arc. */
  B.arcPts = function (cx, cy, r, a0 = 0, a1 = TAU, n = 64) {
    const out = [];
    for (let i = 0; i <= n; i++) {
      const a = a0 + ((a1 - a0) * i) / n;
      out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
    return out;
  };
  /** Closed rectangle as points (clockwise from top-left). */
  B.rectPts = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]];
  /**
   * Hand-drawn wobble: push each point sideways by smooth noise along the path's length.
   * o: { amp (px), freq (wiggles per 100 px, 1.2), seed }. For "boil", change the seed with Brush.boil(t).
   */
  B.wobble = function (pts, o = {}) {
    const amp = o.amp ?? 2, f = (o.freq ?? 1.2) / 100, seed = o.seed ?? 1;
    const out = [];
    let s = 0;
    for (let i = 0; i < pts.length; i++) {
      if (i) s += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const l = Math.hypot(nx, ny) || 1;
      nx /= l;
      ny /= l;
      const d = B.noise2(s * f, 0.5, seed) * amp;
      out.push([pts[i][0] + nx * d, pts[i][1] + ny * d]);
    }
    return out;
  };

  // ------------------------------------------------------------------ strokes, write-on, arrows
  /** Stroke a polyline, revealed from 0 to p of its length (write-on). o: { width, color, cap "round", join, dash, alpha } */
  B.strokeReveal = function (ctx, pts, p = 1, o = {}) {
    const part = p >= 1 ? pts : B.trim(pts, 0, p);
    if (part.length < 2) return;
    ctx.save();
    ctx.strokeStyle = o.color || "#000";
    ctx.lineWidth = o.width ?? 2;
    ctx.lineCap = o.cap || "round";
    ctx.lineJoin = o.join || "round";
    if (o.alpha != null) ctx.globalAlpha *= o.alpha;
    if (o.dash) ctx.setLineDash(o.dash);
    ctx.beginPath();
    B.poly(ctx, part);
    ctx.stroke();
    ctx.restore();
  };
  /**
   * Hand-drawn line along a path: wobbled, optionally doubled (a second, offset pass like a marker going over twice),
   * revealed to p. o: { width, color, amp (px), freq, seed, passes 1, p 1, alpha }
   */
  B.handLine = function (ctx, pts, o = {}) {
    const width = o.width ?? 2, dense = B.densify(pts, Math.max(3, width * 1.5));
    const passes = o.passes ?? 1;
    for (let k = 0; k < passes; k++) {
      const w = B.wobble(dense, { amp: o.amp ?? width * 0.8, freq: o.freq, seed: (o.seed ?? 1) + k * 101 });
      B.strokeReveal(ctx, w, o.p ?? 1, { width: width * (k ? 0.7 : 1), color: o.color, alpha: (o.alpha ?? 1) * (k ? 0.55 : 1) });
    }
  };
  /** Hand-drawn closed shapes. */
  B.handRect = (ctx, x, y, w, h, o = {}) => B.handLine(ctx, [...B.rectPts(x, y, w, h), [x + w * 0.04, y + h * 0.01]], o);
  B.handCircle = (ctx, cx, cy, r, o = {}) => B.handLine(ctx, B.arcPts(cx, cy, r, (o.start ?? -1.9), (o.start ?? -1.9) + TAU * 1.04, 72), o);
  /**
   * Tapered brush stroke: a filled ribbon whose width swells and thins (ink, paint, calligraphy).
   * o: { width (max, px), color, p (reveal), taperIn 0.2, taperOut 0.35, rough 0 (width swell as a fraction of width),
   *      roughScale 4 (length of one swell, in widths), seed }. For a closed outline use taperIn = taperOut = 0.
   */
  B.taperStroke = function (ctx, pts, o = {}) {
    let path = (o.p ?? 1) >= 1 ? pts : B.trim(pts, 0, o.p);
    if (path.length < 2) return;
    path = B.densify(path, Math.max(2, (o.width ?? 6) * 0.5));
    const n = path.length, wMax = o.width ?? 6, tin = o.taperIn ?? 0.2, tout = o.taperOut ?? 0.35, rough = o.rough ?? 0, seed = o.seed ?? 1;
    const L = B.pathLength(path);
    const left = [], right = [];
    let s = 0;
    for (let i = 0; i < n; i++) {
      if (i) s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
      const f = L > 0 ? s / L : 0;
      let wv = wMax * Math.min(1, tin > 0 ? B.ease.outSine(B.clamp(f / tin)) : 1, tout > 0 ? B.ease.outSine(B.clamp((1 - f) / tout)) : 1);
      wv = Math.max(wMax * 0.06, wv * (1 + rough * B.noise2(s / (wMax * (o.roughScale ?? 4)), 0, seed)));
      const a = path[Math.max(0, i - 1)], b = path[Math.min(n - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const l = Math.hypot(nx, ny) || 1;
      nx /= l;
      ny /= l;
      left.push([path[i][0] + (nx * wv) / 2, path[i][1] + (ny * wv) / 2]);
      right.push([path[i][0] - (nx * wv) / 2, path[i][1] - (ny * wv) / 2]);
    }
    ctx.save();
    ctx.fillStyle = o.color || "#000";
    ctx.beginPath();
    B.poly(ctx, left.concat(right.reverse()), true);
    ctx.fill();
    ctx.restore();
  };

  /**
   * Arrow along a path, drawn on from tail to head as p goes 0 -> 1; the head rides the tip.
   * o: {
   *   p 1, width (px) 4, color, head (head length px, default 3.4 x width),
   *   headStyle "tri" (filled, rounded) | "open" (two strokes) | "round" (dot) | "none",
   *   dots (gap in px: a dotted line of round dots), dash ([on, off] px),
   *   rough (wobble px, hand-drawn), seed, alpha
   * }
   */
  B.arrow = function (ctx, pts, o = {}) {
    const p = o.p ?? 1;
    if (p <= 0 || pts.length < 2) return;
    const width = o.width ?? 4, color = o.color || "#000";
    let path = pts;
    if (o.rough) path = B.wobble(B.densify(pts, Math.max(4, width * 2)), { amp: o.rough, seed: o.seed ?? 3 });
    const L = B.pathLength(path), shown = L * p;
    const headLen = Math.min(o.head ?? width * 3.4, shown * 0.6);
    const tip = B.pointAt(path, p);
    const style = o.headStyle || "tri";
    // stop the shaft a little short of the tip so a filled head covers its end cleanly
    const cut = style === "tri" ? headLen * 0.6 : style === "round" ? headLen * 0.3 : 0;
    const shaft = B.trim(path, 0, Math.max(0, (shown - cut) / L));
    ctx.save();
    if (o.alpha != null) ctx.globalAlpha *= o.alpha;
    ctx.strokeStyle = ctx.fillStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (o.dots) {
      const gap = o.dots, nd = Math.floor(B.pathLength(shaft) / gap);
      ctx.beginPath();
      for (let i = 0; i <= nd; i++) {
        const q = B.pointAt(shaft, nd ? i / nd : 0);
        B.circle(ctx, q[0], q[1], width / 2);
      }
      ctx.fill();
    } else if (shaft.length > 1) {
      if (o.dash) ctx.setLineDash(o.dash);
      ctx.beginPath();
      B.poly(ctx, shaft);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (style !== "none" && headLen > 0.5) {
      const a = tip[2], x = tip[0], y = tip[1], hw = headLen * 0.62;
      const bx = x - Math.cos(a) * headLen, by = y - Math.sin(a) * headLen;
      const lx = bx + Math.cos(a + Math.PI / 2) * hw, ly = by + Math.sin(a + Math.PI / 2) * hw;
      const rx = bx - Math.cos(a + Math.PI / 2) * hw, ry = by - Math.sin(a + Math.PI / 2) * hw;
      ctx.beginPath();
      if (style === "open") {
        ctx.moveTo(lx, ly);
        ctx.lineTo(x, y);
        ctx.lineTo(rx, ry);
        ctx.stroke();
      } else if (style === "round") {
        B.circle(ctx, x, y, headLen * 0.45);
        ctx.fill();
      } else {
        ctx.moveTo(x, y);
        ctx.lineTo(lx, ly);
        ctx.lineTo(rx, ry);
        ctx.closePath();
        ctx.lineWidth = Math.max(1, width * 0.6); // rounds the corners
        ctx.fill();
        ctx.stroke();
      }
    }
    ctx.restore();
  };

  // ------------------------------------------------------------------ text
  /** CSS font string. family "Baloo 2" gets quoted and a sans-serif fallback; pass a full list to control it. */
  B.font = (size, family = "sans-serif", weight = 400, style = "") => {
    const fam = /[,"']/.test(family) || /^(serif|sans-serif|monospace|cursive|system-ui)$/.test(family) ? family : `"${family}", sans-serif`;
    return `${style} ${weight} ${Math.max(1, size).toFixed(1)}px ${fam}`.trim();
  };
  /** Split text into lines no wider than maxW with the ctx's current font. "\n" forces a break. */
  B.wrap = function (ctx, text, maxW) {
    const out = [];
    for (const para of String(text).split("\n")) {
      const words = para.split(/\s+/).filter(Boolean);
      let line = "";
      for (const w of words) {
        const test = line ? line + " " + w : w;
        if (!line || ctx.measureText(test).width <= maxW) line = test;
        else {
          out.push(line);
          line = w;
        }
      }
      out.push(line);
    }
    return out;
  };
  function layoutText(ctx, str, o) {
    let size = o.size ?? 40;
    const min = o.minSize ?? size * 0.6, maxW = o.maxW ?? Infinity, maxLines = o.maxLines ?? Infinity;
    const fam = o.family || "sans-serif", weight = o.weight ?? 700, style = o.style || "";
    let lines;
    for (let guard = 0; guard < 40; guard++) {
      ctx.font = B.font(size, fam, weight, style);
      if ("letterSpacing" in ctx) ctx.letterSpacing = ((o.letterSpacing ?? 0) * size).toFixed(2) + "px";
      lines = Number.isFinite(maxW) ? B.wrap(ctx, str, maxW) : String(str).split("\n");
      const widest = Math.max(...lines.map((l) => ctx.measureText(l).width));
      if ((lines.length <= maxLines && widest <= maxW) || size <= min) break;
      size = Math.max(min, size * 0.94);
    }
    const lh = size * (o.lineH ?? 1.15);
    const width = Math.max(...lines.map((l) => ctx.measureText(l).width));
    return { size, lines, lh, width, height: lh * lines.length };
  }
  /**
   * Draw text that wraps to maxW and shrinks (down to minSize) to fit maxLines.
   * o: { size 40, minSize, family, weight 700, style, color "#fff", align "center", baseline "middle" (of the
   *      whole block) | "top" | "bottom", maxW, maxLines, lineH 1.15, letterSpacing (em), reveal 0..1 (typewriter),
   *      shadow { x, y, blur, color }, stroke (colour), strokeW (px), alpha }
   * Returns { size, lines, width, height, top, bottom, lh } so you can place things around it.
   * Brush.measureText(ctx, str, o) returns the same without drawing.
   */
  B.text = function (ctx, str, x, y, o = {}) {
    ctx.save();
    const L = layoutText(ctx, str, o);
    const base = o.baseline || "middle";
    const top = base === "top" ? y : base === "bottom" ? y - L.height : y - L.height / 2;
    ctx.textAlign = o.align || "center";
    ctx.textBaseline = "middle";
    if (o.alpha != null) ctx.globalAlpha *= o.alpha;
    let budget = o.reveal == null ? Infinity : Math.floor(B.clamp(o.reveal) * L.lines.join("").length + 1e-6);
    if (!o.measureOnly) {
      L.lines.forEach((line, i) => {
        if (budget <= 0) return;
        const s = line.slice(0, budget);
        budget -= line.length;
        const ly = top + L.lh * (i + 0.5);
        if (o.shadow) {
          ctx.save();
          ctx.fillStyle = o.shadow.color || "rgba(0,0,0,0.35)";
          if (o.shadow.blur) {
            ctx.shadowColor = o.shadow.color || "rgba(0,0,0,0.35)";
            ctx.shadowBlur = o.shadow.blur;
          }
          ctx.fillText(s, x + (o.shadow.x ?? 0), ly + (o.shadow.y ?? 0));
          ctx.restore();
        }
        if (o.stroke) {
          ctx.strokeStyle = o.stroke;
          ctx.lineWidth = o.strokeW ?? L.size * 0.08;
          ctx.lineJoin = "round";
          ctx.strokeText(s, x, ly);
        }
        ctx.fillStyle = o.color || "#ffffff";
        ctx.fillText(s, x, ly);
      });
    }
    ctx.restore();
    return { ...L, top, bottom: top + L.height };
  };
  B.measureText = (ctx, str, o = {}) => B.text(ctx, str, 0, 0, { ...o, measureOnly: true });
  /** Typewriter: the first p of the characters. */
  B.typewriter = (str, p) => String(str).slice(0, Math.floor(B.clamp(p) * String(str).length + 1e-6));
  /**
   * Number counter text at progress p: Brush.counter(0.5, 1200) -> "600".
   * o: { from 0, decimals 0, sep "," (thousands), prefix, suffix, ease "outCubic" }
   */
  B.counter = function (p, to, o = {}) {
    const k = easeFn(o.ease || "outCubic")(B.clamp(p));
    const v = B.lerp(o.from ?? 0, to, k);
    let s = v.toFixed(o.decimals ?? 0);
    const sep = o.sep ?? ",";
    if (sep) {
      const [i, d] = s.split(".");
      s = i.replace(/\B(?=(\d{3})+(?!\d))/g, sep) + (d ? "." + d : "");
    }
    return (o.prefix || "") + s + (o.suffix || "");
  };

  // ------------------------------------------------------------------ camera and transitions
  /**
   * Run fn inside a camera: cam { x, y (scene point at the frame centre; default centre), zoom 1, rot 0 (rad) }.
   * depth (default 1) scales the move for parallax: background layers 0.3-0.6, foreground 1-1.3.
   */
  B.camera = function (ctx, W, H, cam, fn, depth = 1) {
    const x = cam.x ?? W / 2, y = cam.y ?? H / 2, z = 1 + ((cam.zoom ?? 1) - 1) * depth;
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(z, z);
    if (cam.rot) ctx.rotate(cam.rot * depth);
    ctx.translate(-(W / 2 + (x - W / 2) * depth), -(H / 2 + (y - H / 2) * depth));
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };
  /** Run fn scaled by zoom about the fixed point (x, y): that point stays where it is (push-ins, dives). */
  B.zoomAt = function (ctx, x, y, zoom, fn) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(zoom, zoom);
    ctx.translate(-x, -y);
    try {
      fn(ctx);
    } finally {
      ctx.restore();
    }
  };
  /** Smooth camera shake offset [dx, dy] (px). Scale amp with an envelope to start and stop it. */
  B.shake = (t, amp, seed = 0, freq = 9) => [B.noise2(t * freq, 0.3, seed) * amp, B.noise2(t * freq, 7.7, seed + 1) * amp];
  /** Fill the whole frame with a colour at alpha (fades, flashes). */
  B.cover = function (ctx, W, H, color, alpha = 1) {
    if (alpha <= 0) return;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = B.clamp(alpha);
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  };
  /** Run fn clipped to a rectangle that grows from one side as p goes 0 -> 1. dir: "right" | "left" | "down" | "up". */
  B.clipReveal = function (ctx, x, y, w, h, p, dir, fn) {
    if (p <= 0) return;
    const r = dir === "left" ? [x + w * (1 - p), y, w * p, h] : dir === "down" ? [x, y, w, h * p] : dir === "up" ? [x, y + h * (1 - p), w, h * p] : [x, y, w * p, h];
    B.clip(ctx, (c) => c.rect(...r), fn);
  };
  /** Circle transition: draws `color` everywhere outside a circle of radius p x (frame diagonal) at (cx, cy). */
  B.iris = function (ctx, W, H, p, cx = W / 2, cy = H / 2, color = "#000") {
    if (p >= 1) return;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.rect(0, 0, W, H);
    ctx.arc(cx, cy, Math.max(0, p) * Math.hypot(W, H), 0, TAU, true);
    ctx.fill("evenodd");
    ctx.restore();
  };

  window.Brush = B;
})();
