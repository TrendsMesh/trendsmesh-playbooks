/* 47 Manim-Style Math - reference animation.
 * Topic (setting, replace it): "Odd numbers make squares" - 1 + 3 + 5 + ... + (2n - 1) = n^2: each odd number is an
 * L-shaped layer around a square; n^2 + (2n + 1) = (n + 1)^2; on a graph the squares climb by 3, 5, 7, 9.
 * Rendering (keep it): the look of programmatic maths animation. A flat near-black ground; crisp vector strokes in
 * white, blue, yellow, green and a soft red; shapes are "created" (outline traced, then a half-opaque fill fades in);
 * text and equations are "written" glyph by glyph (each outline traced, then filled) in a maths serif with italic
 * variables; equations transform into the next line, matching parts gliding to their new place while the rest fades;
 * braces with labels, a number line, axes with tick labels, a curve traced with a dot and a moving tangent, a
 * surrounding rectangle for the answer. Motion: smooth ease-in-out, nothing bouncy, deliberate pauses. No texture.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    bg: "#121316",
    white: "#f2f2ef",
    grey: "#8b9099",
    blue: "#58c4dd",
    yellow: "#f6d55c",
    green: "#83c167",
    red: "#fc6255",
  };
  const LAYER = [PAL.blue, PAL.yellow, PAL.green, PAL.red, PAL.blue];
  const MATH = "STIX Two Text", SANS = "Fira Sans";
  const DUR = 14;
  const BEATS = [0, 2.0, 4.8, 7.0, 9.6, 12.0];
  const sm = (t, a, d) => B.prog(t, a, d, "inOutCubic"); // the one rate function: smooth in, smooth out
  /** Fade-out envelope with the small upward drift of a FadeOut. */
  const gone = (t, at, d = 0.3) => 1 - sm(t, at, d);

  // ------------------------------------------------------------------ glyph runs: text and equations as positioned glyphs
  /** Lay out plain text as one glyph per character (kerning kept by measuring prefixes). */
  function textRun(ctx, str, cx, cy, size, o = {}) {
    const font = B.font(size, o.family || MATH, o.weight ?? 400, o.italic ? "italic" : "");
    ctx.save();
    ctx.font = font;
    const w = ctx.measureText(str).width, x0 = o.align === "left" ? cx : cx - w / 2, out = [];
    for (let i = 0; i < str.length; i++) {
      if (str[i] === " ") continue;
      out.push({ ch: str[i], x: x0 + ctx.measureText(str.slice(0, i)).width, y: cy + size * 0.33, size, font, color: o.color || PAL.white, key: (o.key || "") + i });
    }
    ctx.restore();
    out.w = w;
    return out;
  }
  /**
   * Lay out an equation. Tokens: [text, colour, key, flags] with flags "i" italic variable, "s" superscript,
   * "b" big (the key number). "..." draws a centred ellipsis. Spacing follows maths typesetting: a medium space round
   * + and -, a thicker one round =, none inside brackets; superscripts sit up and small, tight to their base.
   */
  function eqRun(ctx, toks, cx, cy, size, align = "center") {
    const out = [];
    let x = 0, prevBig = 1;
    ctx.save();
    toks.forEach(([s, color, key, fl = ""]) => {
      const sup = fl.includes("s"), big = fl.includes("b") ? 1.45 : 1, sz = size * (sup ? 0.62 * prevBig : big);
      const font = B.font(sz, MATH, 400, fl.includes("i") ? "italic" : "");
      ctx.font = font;
      const rel = s === "=", bin = s === "+" || s === "−";
      if (!sup && prevBig > 1) x += size * 0.22; // room for a surrounding rectangle round a big token
      if (rel || bin) x += size * (rel ? 0.3 : 0.24);
      if (big > 1) x += size * 0.22;
      let w = s === "..." ? size * 0.9 : ctx.measureText(s).width;
      if (sup) x += size * 0.04;
      out.push({ ch: s, x, y: sup ? -size * 0.44 * prevBig : 0, size: sz, font, color: color || PAL.white, key, w });
      x += w;
      if (rel || bin) x += size * (rel ? 0.3 : 0.24);
      if (!sup) prevBig = big;
    });
    ctx.restore();
    const x0 = align === "left" ? cx : cx - x / 2;
    out.forEach((g) => { g.x += x0; g.y += cy + size * 0.33; });
    out.w = x;
    return out;
  }
  /** One glyph being written: its outline traced (dash grows along every contour), then the fill comes up. */
  function glyph(ctx, g, pc, alpha = 1, dx = 0, dy = 0) {
    if (pc <= 0 || alpha <= 0.002) return;
    ctx.save();
    ctx.font = g.font;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    const x = g.x + dx, y = g.y + dy;
    if (g.ch === "...") {
      ctx.fillStyle = g.color;
      ctx.globalAlpha = alpha * B.smooth(0, 0.6, pc);
      ctx.beginPath();
      for (let i = 0; i < 3; i++) B.circle(ctx, x + g.size * (0.17 + i * 0.28), y - g.size * 0.24, g.size * 0.045);
      ctx.fill();
      ctx.restore();
      return;
    }
    if (pc < 1) {
      ctx.globalAlpha = alpha;
      ctx.setLineDash([pc * g.size * 4.5, 1e5]);
      ctx.lineWidth = Math.max(1, g.size * 0.028);
      ctx.strokeStyle = g.color;
      ctx.strokeText(g.ch, x, y);
    }
    const f = B.smooth(0.5, 1, pc);
    if (f > 0) {
      ctx.setLineDash([]);
      ctx.globalAlpha = alpha * f;
      ctx.fillStyle = g.color;
      ctx.fillText(g.ch, x, y);
    }
    ctx.restore();
  }
  /** Write a run over [a, a + d] with a lag between glyphs; fade it out (with a small rise) from `out`. */
  function write(ctx, run, t, a, d, out = 99, lag = 0.35) {
    const n = run.length, len = 1 / (1 + lag * Math.max(0, n - 1)), p = B.prog(t, a, d, "inOutSine");
    const al = gone(t, out), rise = (1 - al) * -run[0]?.size * 0.25 || 0;
    if (al <= 0) return;
    run.forEach((g, i) => glyph(ctx, g, B.clamp((p - i * lag * len) / len), al, 0, rise));
  }
  /** Transform one run into another: glyphs with the same key glide (size and colour too), the rest cross-fade. */
  function morph(ctx, A, Bn, k, alpha = 1) {
    const keyed = new Map(A.map((g) => [g.key, g]));
    Bn.forEach((g) => {
      const s = keyed.get(g.key);
      if (s) {
        const sz = B.lerp(s.size, g.size, k);
        glyph(ctx, { ...g, x: B.lerp(s.x, g.x, k), y: B.lerp(s.y, g.y, k), size: sz, font: g.font.replace(/[\d.]+px/, sz.toFixed(2) + "px"), color: B.mix(s.color, g.color, k) }, 1, alpha);
      } else glyph(ctx, g, 1, alpha * B.smooth(0.35, 1, k));
    });
    const kept = new Set(Bn.map((g) => g.key));
    A.forEach((g) => { if (!kept.has(g.key)) glyph(ctx, g, 1, alpha * (1 - B.smooth(0, 0.6, k))); });
  }
  function bbox(run) {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    run.forEach((g) => {
      x0 = Math.min(x0, g.x); x1 = Math.max(x1, g.x + (g.w ?? g.size * 0.5));
      y0 = Math.min(y0, g.y - g.size * 0.72); y1 = Math.max(y1, g.y + g.size * 0.2);
    });
    return [x0, y0, x1, y1];
  }

  // ------------------------------------------------------------------ shapes: create (trace, then fill), arrows, braces
  /** Create: the outline is traced in the first 60 %, a half-opaque fill fades in over the last half. */
  function create(ctx, pts, p, color, o = {}) {
    if (p <= 0) return;
    const a = o.alpha ?? 1;
    ctx.save();
    if (o.fill != null) {
      const f = B.smooth(0.45, 1, p) * o.fill * a;
      if (f > 0) { ctx.fillStyle = B.rgba(o.fillColor || color, f); ctx.beginPath(); B.poly(ctx, pts, true); ctx.fill(); }
    }
    B.strokeReveal(ctx, pts, B.clamp(p / 0.6), { width: o.width, color, alpha: a * (o.strokeAlpha ?? 1), join: "miter", cap: "butt" });
    ctx.restore();
  }
  /** A straight arrow that grows from its tail, with a filled triangular tip. */
  function arrow(ctx, x1, y1, x2, y2, p, color, u, alpha = 1) {
    if (p <= 0 || alpha <= 0) return;
    const x = B.lerp(x1, x2, p), y = B.lerp(y1, y2, p), a = Math.atan2(y2 - y1, x2 - x1), hl = 2.6 * u * Math.min(1, p * 3);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = ctx.fillStyle = color;
    ctx.lineWidth = 0.5 * u;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x - Math.cos(a) * hl * 0.8, y - Math.sin(a) * hl * 0.8); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y);
    ctx.lineTo(x - Math.cos(a - 0.38) * hl, y - Math.sin(a - 0.38) * hl);
    ctx.lineTo(x - Math.cos(a + 0.38) * hl, y - Math.sin(a + 0.38) * hl);
    ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  /** A curly brace from p1 to p2, bulging to its left-hand side (as seen walking p1 -> p2), grown from the middle. */
  function brace(ctx, x1, y1, x2, y2, p, color, u, alpha = 1) {
    if (p <= 0 || alpha <= 0) return [0, 0];
    const L = Math.hypot(x2 - x1, y2 - y1), dx = (x2 - x1) / L, dy = (y2 - y1) / L, nx = dy, ny = -dx, depth = 2.4 * u;
    const at = (s) => {
      const e = Math.min(s, 1 - s); // distance from the nearer end, 0..0.5
      const h = depth * (0.5 * B.smooth(0, 0.07, e) + 0.5 * B.smooth(0.43, 0.5, e));
      return [x1 + dx * L * s + nx * h, y1 + dy * L * s + ny * h];
    };
    const half = (a, b) => { const out = []; for (let i = 0; i <= 30; i++) out.push(at(B.lerp(a, b, i / 30))); return out; };
    ctx.save();
    ctx.globalAlpha = alpha;
    const k = B.ease.inOutCubic(B.clamp(p));
    B.taperStroke(ctx, half(0.5, 0.5 - 0.5 * k), { width: 0.55 * u, color, taperIn: 0.04, taperOut: 0.3 });
    B.taperStroke(ctx, half(0.5, 0.5 + 0.5 * k), { width: 0.55 * u, color, taperIn: 0.04, taperOut: 0.3 });
    ctx.restore();
    return [x1 + dx * L * 0.5 + nx * depth, y1 + dy * L * 0.5 + ny * depth];
  }
  /** Surrounding rectangle round a box, traced on. */
  function surround(ctx, box, p, color, u, alpha = 1) {
    const pad = 1.6 * u, [x0, y0, x1, y1] = box;
    create(ctx, B.rectPts(x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), p, color, { width: 0.45 * u, alpha });
  }
  function dot(ctx, x, y, r, color, alpha = 1) {
    if (r <= 0 || alpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath(); B.circle(ctx, x, y, r); ctx.fill();
    ctx.restore();
  }

  // ------------------------------------------------------------------ layout per aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    const pk = (l, p) => (P ? p : l);
    return {
      F, u, P, W, H,
      header: pk([W / 2, H * 0.1, 4.6 * u], [W / 2, H * 0.17, 5.4 * u]),
      title: pk([[W / 2, H * 0.27], [W / 2, H * 0.41]], [[W / 2, H * 0.27], [W / 2, H * 0.32]]), titleSize: pk(8.5 * u, 9 * u),
      titleEq: pk([W / 2, H * 0.575, 7 * u], [W / 2, H * 0.465, 8.5 * u]),
      line: pk({ x0: W * 0.16, x1: W * 0.84, y: H * 0.77 }, { x0: W * 0.1, x1: W * 0.9, y: H * 0.61 }),
      grid: pk({ c: 11 * u, gx: W * 0.17, gy: H * 0.76 }, { c: 14 * u, gx: W / 2 - 28 * u, gy: H * 0.565 }),
      grid3: pk(null, { c: 11.9 * u, gx: W / 2 - 23.8 * u, gy: H * 0.515 }), // portrait: scaled up and away for the steps
      caption: pk([[W * 0.69, H * 0.34], [W * 0.69, H * 0.43]], [[W / 2, H * 0.69], [W / 2, H * 0.725]]), capSize: pk(5 * u, 5.4 * u),
      arrow: pk([W * 0.51, H * 0.48, W * 0.44, H * 0.48], [W * 0.84, H * 0.665, W * 0.84, H * 0.47]),
      keyEq: pk([W * 0.69, H * 0.47, 7.2 * u], [W / 2, H * 0.69, 7.8 * u]),
      steps: pk({ x: W * 0.57, n: W * 0.5, ys: [H * 0.3, H * 0.48, H * 0.66], size: 7 * u }, { x: W * 0.28, n: W * 0.14, ys: [H * 0.64, H * 0.7, H * 0.76], size: 7.5 * u }),
      axes: pk({ ox: W * 0.15, oy: H * 0.84, sx: (W * 0.55) / 5.5, sy: (H * 0.66) / 27 }, { ox: W * 0.17, oy: H * 0.71, sx: (W * 0.7) / 5.5, sy: (H * 0.47) / 27 }),
      graphCap: pk([[W * 0.8, H * 0.56], [W * 0.8, H * 0.64]], [[W / 2, H * 0.775]]),
      close: pk({ cap: [W / 2, H * 0.3], f1: [W / 2, H * 0.5], f2: null, cap2: [W / 2, H * 0.7], size: 7.5 * u },
                { cap: [W / 2, H * 0.23], f1: [W / 2, H * 0.31], f2: [W / 2, H * 0.375], cap2: [W / 2, H * 0.775], size: 7.5 * u, grid: { c: 8 * u, gx: W / 2 - 20 * u, gy: H * 0.73 } }),
    };
  }

  // ------------------------------------------------------------------ the subject: odd numbers as L-shaped layers
  /** Cells of a k x k square grouped into layers: layer k holds the 2k - 1 cells whose larger index is k - 1. */
  function layerCells(k) {
    const out = [];
    for (let i = 0; i < k; i++) out.push([i, k - 1]); // top row of the layer, left to right
    for (let j = k - 2; j >= 0; j--) out.push([k - 1, j]); // then down the right side
    return out;
  }
  function gridAt(L, t) {
    if (!L.P || !L.grid3) return L.grid;
    const k = sm(t, 7.0, 0.5), a = L.grid, b = L.grid3;
    return { c: B.lerp(a.c, b.c, k), gx: B.lerp(a.gx, b.gx, k), gy: B.lerp(a.gy, b.gy, k) };
  }
  const LAYER_AT = [2.15, 2.6, 3.05, 3.5];
  function squares(ctx, L, t) {
    const u = L.u, g = gridAt(L, t), out = gone(t, 9.6);
    if (out <= 0 || t < 2.1) return;
    const recol = sm(t, 7.05, 0.5);
    for (let k = 1; k <= 4; k++) {
      const col = k < 4 ? B.mix(LAYER[k - 1], PAL.blue, recol) : B.mix(PAL.red, PAL.yellow, recol);
      const flash = k === 4 ? Math.sin(Math.PI * B.clamp((t - 8.1) / 0.5)) : 0; // Indicate: a brief swell
      layerCells(k).forEach(([i, j], n) => {
        const p = B.prog(t, LAYER_AT[k - 1] + n * 0.05, 0.42);
        const x = g.gx + i * g.c, y = g.gy - (j + 1) * g.c, s = g.c * (1 + 0.06 * flash), cx = x + g.c / 2, cy = y + g.c / 2;
        create(ctx, B.rectPts(cx - s / 2, cy - s / 2, s, s), p, col, { width: 0.4 * u, fill: 0.55 + 0.25 * flash, alpha: out, strokeAlpha: k < 4 ? 1 - 0.75 * recol : 1 });
      });
    }
    if (recol > 0) create(ctx, B.rectPts(g.gx, g.gy - 3 * g.c, 3 * g.c, 3 * g.c), recol * 1.6, PAL.blue, { width: 0.5 * u, alpha: out });
  }
  /** The odd number written in the corner cell of each layer. */
  function cellLabel(ctx, L, k, size) {
    const g = L.grid;
    return textRun(ctx, String(2 * k - 1), g.gx + (k - 0.5) * g.c, g.gy - (k - 0.5) * g.c, size, { key: "a" + (2 * k - 1) });
  }

  // ------------------------------------------------------------------ beats
  function titleBeat(ctx, L, t) {
    const u = L.u, [l1, l2] = L.title, ts = L.titleSize, [hx, hy, hs] = L.header;
    const A = textRun(ctx, "Odd numbers", l1[0], l1[1], ts, { key: "t" }).concat(textRun(ctx, "make squares", l2[0], l2[1], ts, { key: "u" }));
    const Hd = textRun(ctx, "Odd numbers make squares", hx, hy, hs, { color: PAL.white });
    // the header keys: same letters as the two title lines, so the title glides up into it
    let n = 0;
    "Odd numbers make squares".split("").forEach((ch, i) => { if (ch !== " ") Hd[n++].key = i < 11 ? "t" + i : "u" + (i - 12); });
    if (t < 1.8) write(ctx, A, t, 0.05, 0.75);
    else if (t < 12.3) {
      const k = sm(t, 1.8, 0.6);
      morph(ctx, A, Hd.map((g) => ({ ...g, color: B.mix(PAL.white, PAL.grey, 0.15) })), k, gone(t, 12.0));
    }
    if (t > 2.4) return;
    const [ex, ey, es] = L.titleEq;
    const eq = eqRun(ctx, [["1", PAL.blue], ["+"], ["3", PAL.yellow], ["+"], ["5", PAL.green], ["+"], ["7", PAL.red], ["+"], ["..."]], ex, ey, es);
    write(ctx, eq, t, 0.35, 0.8, 1.85);
    // the number line: drawn on, ticks and labels written, odd numbers marked in their layer colours
    const N = L.line, al = gone(t, 1.85), lp = sm(t, 0.45, 0.5), step = (N.x1 - N.x0) / 10;
    if (al <= 0 || lp <= 0) return;
    ctx.save();
    ctx.globalAlpha = al;
    B.strokeReveal(ctx, [[N.x0, N.y], [N.x1, N.y]], lp, { width: 0.35 * u, color: PAL.white, cap: "butt" });
    for (let i = 0; i <= 9; i++) {
      const x = N.x0 + (i + 0.5) * step, tp = sm(t, 0.5 + i * 0.03, 0.25);
      B.strokeReveal(ctx, [[x, N.y - 1.2 * u], [x, N.y + 1.2 * u]], tp, { width: 0.3 * u, color: PAL.white, cap: "butt" });
      write(ctx, textRun(ctx, String(i), x, N.y + 4.6 * u, 4.4 * u, { key: "nl" + i }), t, 0.6 + i * 0.03, 0.3, 1.85);
      if (i % 2) dot(ctx, x, N.y, 1.3 * u * sm(t, 1.0 + i * 0.05, 0.3), LAYER[((i - 1) / 2) % 5]);
    }
    ctx.restore();
    if (L.P) write(ctx, textRun(ctx, "the odd numbers", W2(L), N.y + 11 * u, 5 * u, { family: SANS, color: PAL.grey }), t, 0.6, 0.5, 1.85);
  }
  const W2 = (L) => L.W / 2;

  function diagramBeat(ctx, L, t) {
    const u = L.u, g = L.grid;
    // the odd number in each layer's corner; it stays until the steps start
    for (let k = 1; k <= 4; k++) write(ctx, cellLabel(ctx, L, k, 5.2 * u), t, LAYER_AT[k - 1] + 0.3, 0.25, 7.0, 0);
    // caption, arrow, brace
    const cs = L.capSize;
    write(ctx, textRun(ctx, "Stack the odd numbers", L.caption[0][0], L.caption[0][1], cs, { family: SANS }), t, 2.15, 0.55, 4.8);
    write(ctx, textRun(ctx, "as L-shaped layers", L.caption[1][0], L.caption[1][1], cs, { family: SANS }), t, 2.4, 0.55, 4.8);
    const [ax1, ay1, ax2, ay2] = L.arrow;
    arrow(ctx, ax1, ay1, ax2, ay2, sm(t, 3.95, 0.4), PAL.white, u, gone(t, 4.8));
    const bp = sm(t, 4.15, 0.4), ba = gone(t, 7.0);
    const [bx, by] = brace(ctx, g.gx + 4 * g.c, g.gy + 1.2 * u, g.gx, g.gy + 1.2 * u, bp, PAL.white, u, ba);
    if (bp > 0) write(ctx, eqRun(ctx, [["n", 0, "n", "i"], ["="], ["4"]], bx, by + 4.2 * u, 5.4 * u), t, 4.35, 0.4, 7.0);
  }

  function keyBeat(ctx, L, t) {
    if (t < 4.85 || t > 7.3) return;
    const u = L.u, g = L.grid, [ex, ey, es] = L.keyEq;
    const toks = [["1", PAL.blue, "a1"], ["+", 0, "p1"], ["3", PAL.yellow, "a3"], ["+", 0, "p2"], ["5", PAL.green, "a5"], ["+", 0, "p3"], ["7", PAL.red, "a7"]];
    const A = eqRun(ctx, toks.concat([["=", 0, "eq"], ["16", PAL.yellow, "k16", "b"]]), ex, ey, es);
    const Bq = eqRun(ctx, toks.concat([["=", 0, "eq"], ["16", PAL.yellow, "k16", "b"], ["=", 0, "eq2"], ["4", PAL.white, "k4", "b"], ["2", PAL.white, "k2", "s"]]), ex, ey, es);
    const al = gone(t, 7.0, 0.25);
    // TransformFromCopy: copies of the corner numbers glide down into the sum
    const src = [1, 2, 3, 4].map((k) => cellLabel(ctx, L, k, 5.2 * u)[0]);
    const kg = sm(t, 4.9, 0.6), sw = sm(t, 6.3, 0.5);
    const cur = A.map((gl) => { const q = Bq.find((h) => h.key === gl.key); return { ...gl, x: B.lerp(gl.x, q.x, sw) }; });
    cur.slice(0, 7).forEach((gl) => {
      const s = src.find((q) => q.key === gl.key);
      if (s) morph(ctx, [s], [gl], kg, al);
      else glyph(ctx, gl, 1, al * sm(t, 5.15, 0.35));
    });
    write(ctx, cur.slice(7), t, 5.5, 0.35, 7.0);
    // then the line makes room and "= 4 squared" is written after it; the rectangle rides with the 16
    if (sw > 0) write(ctx, Bq.slice(9), t, 6.45, 0.4, 7.0);
    surround(ctx, bbox(cur.slice(8)), sm(t, 5.95, 0.4), PAL.yellow, u, al);
    // a second brace up the left side: 4 rows of 4
    const bp = sm(t, 5.55, 0.4);
    const [lx, ly] = brace(ctx, g.gx - 1.2 * u, g.gy, g.gx - 1.2 * u, g.gy - 4 * g.c, bp, PAL.white, u, al);
    if (bp > 0) write(ctx, eqRun(ctx, [["4"]], lx - 3.2 * u, ly, 5.4 * u), t, 5.7, 0.3, 7.0);
  }

  function stepsBeat(ctx, L, t) {
    if (t < 7.2 || t > 9.95) return;
    const u = L.u, g = gridAt(L, t), S = L.steps, out = 9.6, al = gone(t, out);
    const n2 = (pre, col = PAL.blue) => [["n", col, pre + "n", "i"], ["2", col, pre + "2", "s"]];
    const s1 = eqRun(ctx, n2("x"), S.x, S.ys[0], S.size, "left");
    const s2t = n2("x").concat([["+", 0, "p"], ["2", PAL.yellow, "c2"], ["n", PAL.yellow, "cn", "i"], ["+", PAL.yellow, "p2"], ["1", PAL.yellow, "one"]]);
    const s2 = eqRun(ctx, s2t, S.x, S.ys[1], S.size, "left");
    const s3 = eqRun(ctx, [["(", 0, "lp"], ["n", 0, "xn", "i"], ["+", 0, "p"], ["1", 0, "one"], [")", 0, "rp"], ["2", 0, "x2", "s"]], S.x, S.ys[2], S.size, "left");
    ["1.", "2.", "3."].forEach((s, i) => write(ctx, textRun(ctx, s, S.n, S.ys[i], S.size * 0.8, { color: PAL.grey, key: "st" + i }), t, [7.35, 7.95, 8.6][i], 0.25, out));
    write(ctx, s1, t, 7.4, 0.4, out);
    // line 2: a copy of n^2 glides down, the new L's 2n + 1 is written beside it
    const k2 = sm(t, 7.95, 0.45);
    if (k2 > 0) {
      morph(ctx, s1, s2.slice(0, 2), k2, al);
      write(ctx, s2.slice(2), t, 8.05, 0.45, out);
    }
    // line 3: the whole of line 2 transforms into (n + 1)^2
    const k3 = sm(t, 8.6, 0.6);
    if (k3 > 0) morph(ctx, s2, s3, k3, al);
    surround(ctx, bbox(s3), sm(t, 9.2, 0.35), PAL.yellow, u, al);
    // on the picture: n^2 in the blue square, 2n + 1 on the L, braces n and n + 1
    const c = g.c;
    write(ctx, eqRun(ctx, n2("g", PAL.white), g.gx + 1.5 * c, g.gy - 1.5 * c, 8 * u), t, 7.35, 0.4, out);
    write(ctx, eqRun(ctx, [["2", PAL.yellow], ["n", PAL.yellow, 0, "i"], ["+", PAL.yellow], ["1", PAL.yellow]], g.gx + 3.2 * c, g.gy - 4 * c - 3.8 * u, 6.2 * u), t, 8.05, 0.4, out);
    const bn = sm(t, 7.5, 0.35);
    const [nx, ny] = brace(ctx, g.gx + 3 * c, g.gy + 1.2 * u, g.gx, g.gy + 1.2 * u, bn, PAL.white, u, al);
    if (bn > 0) write(ctx, eqRun(ctx, [["n", 0, 0, "i"]], nx, ny + 4 * u, 6 * u), t, 7.6, 0.3, out);
    const bm = sm(t, 8.7, 0.35);
    const [mx, my] = brace(ctx, g.gx - 1.2 * u, g.gy, g.gx - 1.2 * u, g.gy - 4 * c, bm, PAL.white, u, al);
    if (bm > 0) write(ctx, eqRun(ctx, [["n", 0, 0, "i"], ["+"], ["1"]], mx - 8.4 * u, my, 6 * u), t, 8.8, 0.35, out);
  }

  function graphBeat(ctx, L, t) {
    if (t < 9.7 || t > 12.35) return;
    const u = L.u, A = L.axes, al = gone(t, 12.0), X = (x) => A.ox + x * A.sx, Y = (y) => A.oy - y * A.sy;
    ctx.save();
    ctx.globalAlpha = al;
    const ap = sm(t, 9.75, 0.5);
    arrow(ctx, X(0), Y(0), X(5.6), Y(0), ap, PAL.grey, u * 0.8);
    arrow(ctx, X(0), Y(0), X(0), Y(27.5), ap, PAL.grey, u * 0.8);
    ctx.restore();
    for (let i = 1; i <= 5; i++) {
      B.strokeReveal(ctx, [[X(i), Y(0) - u], [X(i), Y(0) + u]], sm(t, 9.9 + i * 0.04, 0.2) * al, { width: 0.3 * u, color: PAL.grey });
      write(ctx, textRun(ctx, String(i), X(i), Y(0) + 4.4 * u, 4.4 * u, { key: "x" + i }), t, 9.95 + i * 0.04, 0.3, 12.0);
      B.strokeReveal(ctx, [[X(0) - u, Y(i * 5)], [X(0) + u, Y(i * 5)]], sm(t, 9.9 + i * 0.04, 0.2) * al, { width: 0.3 * u, color: PAL.grey });
      const yl = textRun(ctx, String(i * 5), 0, Y(i * 5), 4.4 * u, { key: "y" + i });
      const dx = X(0) - 2 * u - yl.w - yl[0].x;
      yl.forEach((q) => (q.x += dx));
      write(ctx, yl, t, 9.95 + i * 0.04, 0.3, 12.0);
    }
    write(ctx, eqRun(ctx, [["n", 0, 0, "i"]], X(5.6) + 3 * u, Y(0), 6.4 * u), t, 10.1, 0.3, 12.0);
    write(ctx, eqRun(ctx, [["n", PAL.blue, 0, "i"], ["2", PAL.blue, 0, "s"]], X(0) + 5.5 * u, Y(27.5), 6.4 * u), t, 10.1, 0.3, 12.0);
    // the jumps between squares: each one is the next odd number
    for (let n = 1; n <= 4; n++) {
      const a = 10.5 + (n - 1) * 0.16, col = LAYER[n % 4];
      B.strokeReveal(ctx, [[X(n), Y(n * n)], [X(n + 1), Y(n * n)]], sm(t, a, 0.25) * al, { width: 0.3 * u, color: PAL.grey, dash: [u, u] });
      B.strokeReveal(ctx, [[X(n + 1), Y(n * n)], [X(n + 1), Y((n + 1) * (n + 1))]], sm(t, a + 0.12, 0.3) * al, { width: 0.55 * u, color: col, cap: "butt" });
      write(ctx, eqRun(ctx, [["+" + (2 * n + 1), col]], X(n + 1) + 4 * u, Y(n * n + n + 0.5), 5 * u), t, a + 0.2, 0.3, 12.0);
    }
    for (let n = 1; n <= 5; n++) dot(ctx, X(n), Y(n * n), 1.1 * u * sm(t, 10.25 + n * 0.07, 0.3), PAL.white, al);
    // y = x^2 traced on, with a dot riding the tip and its tangent turning with it
    const curve = [];
    for (let i = 0; i <= 80; i++) { const x = (5.15 * i) / 80; curve.push([X(x), Y(x * x)]); }
    const cp = sm(t, 10.75, 0.95);
    if (cp > 0) {
      B.strokeReveal(ctx, curve, cp, { width: 0.45 * u, color: PAL.blue, alpha: al });
      const tip = B.pointAt(curve, cp), xd = (tip[0] - A.ox) / A.sx, ta = gone(t, 11.75, 0.3) * al;
      const vx = A.sx, vy = -2 * xd * A.sy, len = Math.hypot(vx, vy), hl = 9 * u;
      B.strokeReveal(ctx, [[tip[0] - (vx / len) * hl, tip[1] - (vy / len) * hl], [tip[0] + (vx / len) * hl, tip[1] + (vy / len) * hl]], 1, { width: 0.35 * u, color: PAL.green, alpha: ta });
      dot(ctx, tip[0], tip[1], 1.25 * u, PAL.yellow, al);
    }
    const gc = L.graphCap, cs = L.capSize * 0.92;
    write(ctx, textRun(ctx, gc.length > 1 ? "each jump is" : "each jump is the next odd number", gc[0][0], gc[0][1], cs, { family: SANS }), t, 10.9, 0.5, 12.0);
    if (gc.length > 1) write(ctx, textRun(ctx, "the next odd number", gc[1][0], gc[1][1], cs, { family: SANS }), t, 11.1, 0.5, 12.0);
  }

  function closeBeat(ctx, L, t) {
    if (t < 12.1) return;
    const u = L.u, C = L.close, sz = C.size;
    const c1 = textRun(ctx, "Add up the first", 0, C.cap[1], L.capSize, { family: SANS, color: PAL.grey, align: "left", key: "c" });
    const cn = eqRun(ctx, [["n", PAL.white, "cn", "i"]], 0, C.cap[1], L.capSize * 1.15, "left");
    const c2 = textRun(ctx, "odd numbers", 0, C.cap[1], L.capSize, { family: SANS, color: PAL.grey, align: "left", key: "d" });
    const sp = L.capSize * 0.3, tot = c1.w + cn.w + c2.w + 2 * sp, x0 = C.cap[0] - tot / 2;
    c1.forEach((q) => (q.x += x0)); cn.forEach((q) => (q.x += x0 + c1.w + sp)); c2.forEach((q) => (q.x += x0 + c1.w + cn.w + 2 * sp));
    write(ctx, c1.concat(cn, c2), t, 12.15, 0.45);
    const left = [["1", PAL.blue], ["+"], ["3", PAL.yellow], ["+"], ["5", PAL.green], ["+"], ["..."], ["+"], ["("], ["2"], ["n", 0, 0, "i"], ["−"], ["1"], [")"]];
    const right = [["="], ["n", PAL.yellow, 0, "i"], ["2", PAL.yellow, 0, "s"]];
    let runs;
    if (C.f2) runs = [eqRun(ctx, left, C.f1[0], C.f1[1], sz), eqRun(ctx, right, C.f2[0], C.f2[1], sz)];
    else runs = [eqRun(ctx, left.concat(right), C.f1[0], C.f1[1], sz)];
    runs.forEach((r, i) => write(ctx, r, t, 12.35 + i * 0.55, i ? 0.35 : 0.75, 99, 0.25));
    surround(ctx, bbox(runs.flat()), sm(t, 13.15, 0.4), PAL.yellow, u);
    write(ctx, textRun(ctx, "and you always get a square", C.cap2[0], C.cap2[1], L.capSize, { family: SANS, color: PAL.grey }), t, 13.3, 0.45);
    if (!C.grid) return;
    const g = C.grid;
    for (let k = 1; k <= 5; k++) layerCells(k).forEach(([i, j], n) => {
      const p = B.prog(t, 12.45 + (k - 1) * 0.13 + n * 0.012, 0.35);
      create(ctx, B.rectPts(g.gx + i * g.c, g.gy - (j + 1) * g.c, g.c, g.c), p, LAYER[k - 1], { width: 0.35 * u, fill: 0.55 });
    });
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    ctx.fillStyle = PAL.bg;
    ctx.fillRect(0, 0, W, H);
    titleBeat(ctx, L, t);
    squares(ctx, L, t);
    if (t > 2.1 && t < 9.95) diagramBeat(ctx, L, t);
    keyBeat(ctx, L, t);
    stepsBeat(ctx, L, t);
    graphBeat(ctx, L, t);
    closeBeat(ctx, L, t);
  }

  // ------------------------------------------------------------------ sound: soft ticks, clean sine blips, a quiet pad
  SOUND.define("manim-blip", (v, o) => {
    const f = v.hz(o.note ?? "E5");
    v.tone({ f, a: 0.006, len: 0.32, peak: 0.13 });
    v.tone({ f: f * 2, a: 0.004, len: 0.12, peak: 0.025 });
  }, { verb: 0.3 });
  SOUND.define("manim-pad", (v, o) => {
    const d = v.dur ?? 8, g = v.bedGain(d, 0.09, o.fade ?? 1.5);
    (o.notes || ["A2", "E3", "A3", "C#4", "E4"]).forEach((n, i) => {
      const osc = v.ac.createOscillator(), og = v.ac.createGain();
      osc.type = "sine";
      osc.frequency.value = v.hz(n);
      og.gain.value = 0.32 / (1 + i * 0.4);
      osc.connect(og); og.connect(g);
      v.lfo(og.gain, 0.07 + i * 0.03, 0.06 / (1 + i), v.t + d);
      osc.start(v.t); osc.stop(v.t + d + 0.1);
    });
  }, { bed: true, verb: 0.5 });

  function score(k) {
    const sc = SOUND.scale("A4", "major", 10);
    k.bed("manim-pad", 0, DUR, { gain: 0.9 });
    k.repeat(0.08, 0.07, 10, "tick", { gain: 0.18, vary: 2 });
    k.at(0.4, "manim-blip", { note: sc[0], gain: 0.7 });
    k.repeat(0.5, 0.04, 10, "tick", { gain: 0.14 });
    [1.05, 1.15, 1.25, 1.35, 1.45].forEach((at, i) => k.at(at, "manim-blip", { note: sc[i], gain: 0.45, pan: -0.4 + i * 0.2 }));
    k.at(1.8, "swish", { dur: 0.6, gain: 0.25 });
    LAYER_AT.forEach((at, i) => {
      k.repeat(at, 0.05, 2 * i + 1, "tick", { gain: 0.2, vary: 1 });
      k.at(at + 0.42, "manim-blip", { note: sc[i * 2], gain: 0.7 });
    });
    k.at(3.95, "manim-blip", { note: sc[4], gain: 0.4 }).at(4.2, "tick", { gain: 0.3 });
    k.at(4.9, "swish", { dur: 0.6, gain: 0.25 });
    [5.0, 5.1, 5.2, 5.3].forEach((at, i) => k.at(at, "tick", { gain: 0.25, pitch: i }));
    k.at(5.55, "manim-blip", { note: sc[2], gain: 0.8 }).at(5.68, "manim-blip", { note: sc[4], gain: 0.8 });
    k.at(5.95, "manim-blip", { note: sc[7], gain: 0.6 });
    k.at(6.4, "swish", { dur: 0.5, gain: 0.2 }).at(6.75, "manim-blip", { note: sc[9], gain: 0.7 });
    [7.4, 8.0, 8.65].forEach((at, i) => k.at(at, "manim-blip", { note: sc[2 + i * 2], gain: 0.6 }).repeat(at + 0.05, 0.06, 4, "tick", { gain: 0.14 }));
    k.at(9.25, "manim-blip", { note: sc[7], gain: 0.7 });
    k.at(9.6, "swish", { dur: 0.5, gain: 0.22 });
    k.repeat(9.9, 0.05, 10, "tick", { gain: 0.16 });
    [1, 2, 3, 4, 5].forEach((n) => k.at(10.25 + n * 0.07, "manim-blip", { note: sc[n - 1], gain: 0.35, pitch: 12 }));
    k.at(10.75, "swell", { dur: 0.95, gain: 0.25 });
    k.at(12.0, "swish", { dur: 0.5, gain: 0.22 });
    k.repeat(12.35, 0.06, 12, "tick", { gain: 0.13 });
    k.at(13.15, "manim-blip", { note: sc[0], gain: 0.6 }).at(13.25, "manim-blip", { note: sc[2], gain: 0.6 }).at(13.35, "manim-blip", { note: sc[4], gain: 0.7 });
  }

  Player.register({
    id: "manim-math",
    name: "Manim-Style Math",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=STIX+Two+Text:ital,wght@0,400;1,400&family=Fira+Sans:wght@400&display=swap",
      faces: ['400 20px "STIX Two Text"', 'italic 400 20px "STIX Two Text"', '400 20px "Fira Sans"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Graph", "Close"],
    stills: [1.7, 4.6, 6.9, 9.5, 11.9, 13.9],
    draw,
    score,
  });
})();
