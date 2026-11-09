/* 21 Stained Glass - reference animation.
 * Topic (setting, replace it): "How old is sunlight?" - light takes about 8 minutes from the Sun to Earth.
 * Rendering (keep it): a pointed-arch window in a dark stone wall (flatter and wider in landscape). The field is cut
 * into irregular glass pieces, each one flat jewel colour, bright at its centre and deeper toward its lead; subjects
 * are pieces of their own laid over the field, so their lead cuts the field's lead. Three layers per frame: glass,
 * lead, paint; mottled glass texture, then a blurred copy added back as back-light glow. Coloured light falls on
 * the floor and soft shafts cross the room. Lettering: dark paint on pale glass banners, blackletter and serif.
 * Motion: lead draws on over dark glass, panes light in a ripple; beats change by dimming to black and relighting.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { lead: "#14110f", ruby: "#b3192b", sapphire: "#1f48a8", emerald: "#1f8a54", amber: "#e8a317", violet: "#6a2a9a", pale: "#f1e6c4", stone: "#4a443d", paint: "#24170d" };
  const GOTH = "UnifrakturMaguntia", SERIF = "Cormorant Garamond";
  const DUR = 13;
  const BEATS = [0, 2.3, 4.8, 7.0, 9.4, 10.9];
  // the windows shown one after another (the steps window spans two beats)
  const WINDOWS = [[0, 2.3], [2.3, 4.8], [4.8, 7.0], [7.0, 10.9], [10.9, DUR + 1]];

  // per-frame state: glass, lead and paint layers, frame unit, the current window's light
  let G = null, LD = null, PT = null, U = 1, LIGHT = null;

  // ---- window geometry
  /** Pointed arch: jambs from yb up to the springing line ys, two arcs of radius r (squashed by k) meeting at the apex. */
  function archPath(ctx, x0, x1, ys, yb, r, k = 1) {
    const w = x1 - x0, d = r - w / 2, h = Math.sqrt(Math.max(0, r * r - d * d)), a = Math.atan2(h, d);
    ctx.moveTo(x0, yb);
    ctx.lineTo(x0, ys);
    ctx.ellipse(x0 + r, ys, r, r * k, 0, Math.PI, Math.PI + a);
    ctx.ellipse(x1 - r, ys, r, r * k, 0, 2 * Math.PI - a, 2 * Math.PI);
    ctx.lineTo(x1, yb);
    ctx.closePath();
  }
  function geo(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    // landscape: a wide great window under a flatter arch (k squashes it), so the scene gets the width
    const x0 = P ? W * 0.07 : W * 0.165, x1 = P ? W * 0.93 : W * 0.835, w = x1 - x0, r = w * 0.62, k = P ? 1 : 0.4;
    const top = P ? H * 0.045 : H * 0.03, rise = Math.sqrt(r * r - (r - w / 2) ** 2) * k, ys = top + rise, yb = P ? H * 0.8 : H * 0.86;
    const band = 3.2 * u;
    // squash for a concentric arch with its apex at ay (keeps the band's thickness at the apex)
    const kAt = (dx, ay) => (P ? 1 : (ys - ay) / Math.sqrt((r - dx) ** 2 - (r - dx - (w - 2 * dx) / 2) ** 2));
    const inner = { x0: x0 + band, x1: x1 - band, ys, yb: yb - band, r: r - band, k: kAt(band, top + band) };
    inner.top = ys - Math.sqrt(inner.r ** 2 - (inner.r - (inner.x1 - inner.x0) / 2) ** 2) * inner.k;
    const fld = { x: inner.x0, y: inner.top, w: inner.x1 - inner.x0, h: inner.yb - inner.top };
    fld.cx = fld.x + fld.w / 2;
    return { F, u, P, x0, x1, ys, yb, r, k, kAt, top, band, inner, fld, floor: yb + 2.5 * u };
  }
  /** Is a point inside the inner field of the arch? */
  function inField(g, x, y) {
    const I = g.inner;
    if (x < I.x0 || x > I.x1 || y > I.yb || y < I.top) return false;
    if (y >= I.ys) return true;
    const cl = I.x0 + I.r, cr = I.x1 - I.r, yy = I.ys - (I.ys - y) / I.k;
    return Math.hypot(x - cl, yy - I.ys) <= I.r && Math.hypot(x - cr, yy - I.ys) <= I.r;
  }

  // ---- stained-glass helpers (reuse these)
  /** Light of a pane at (x, y), 0 = dark, 1 = lit: a ripple from LIGHT's origin, then the dim before the next window. */
  function lightAt(x, y, t) {
    const L = LIGHT, d = Math.hypot(x - L.ox, y - L.oy) / L.reach;
    const on = B.smooth(L.a + 0.55 + d * 0.75, L.a + 0.9 + d * 0.75, t);
    return on * (1 - B.smooth(L.b - 0.4, L.b - 0.05, t)) * (L.k ?? 1);
  }
  /** Lead draw-on progress for a piece near (x, y): lead grows first, over dark glass. */
  function leadAt(x, y, t) {
    const L = LIGHT, d = (Math.hypot(x - L.ox, y - L.oy) / L.reach) * 0.45;
    return B.smooth(L.a + 0.05 + d, L.a + 0.45 + d, t) * (1 - B.smooth(L.b - 0.12, L.b, t));
  }
  const centroid = (pts) => pts.reduce((a, q) => [a[0] + q[0] / pts.length, a[1] + q[1] / pts.length], [0, 0]);
  const circlePts = (cx, cy, r, n = 40, a0 = 0) => Array.from({ length: n }, (_, i) => [cx + Math.cos(a0 + (i / n) * B.TAU) * r, cy + Math.sin(a0 + (i / n) * B.TAU) * r]);
  /**
   * One glass piece: flat jewel colour, bright at its centre, deeper at its lead, dark when unlit; its lead outline
   * grows to lp on the lead layer (with cut, after clearing the field lead under it).
   * o: { lf (light 0..1), lp (lead 0..1), lw (lead width), seed (tone variation), boost (extra brightness) }
   */
  function piece(pts, col, o) {
    const [cx, cy] = o.c || centroid(pts);
    let rad = 0;
    for (const q of pts) rad = Math.max(rad, Math.hypot(q[0] - cx, q[1] - cy));
    const v = ((o.seed != null ? B.hash01("pane", o.seed) : 0.5) - 0.5) * 0.22 + (o.boost ?? 0);
    const dark = B.mix(col, "#060404", 0.9), lf = B.clamp(o.lf ?? 1);
    const hi = B.mix(dark, B.shade(col, B.clamp(0.3 + v, -0.5, 0.75)), lf), lo = B.mix(dark, B.shade(col, -0.28 + v * 0.6), lf);
    G.fillStyle = B.radial(G, cx - rad * 0.15, cy - rad * 0.2, 0, rad * 1.1, [hi, B.mix(hi, lo, 0.45), lo]);
    G.beginPath();
    B.poly(G, pts, true);
    G.fill();
    if (o.cut) {
      LD.save();
      LD.globalCompositeOperation = "destination-out";
      LD.beginPath();
      B.poly(LD, pts, true);
      LD.fill();
      LD.restore();
    }
    const lp = o.lp ?? 1;
    if (lp > 0.01) {
      const ring = pts.concat([pts[0]]);
      LD.strokeStyle = PAL.lead;
      LD.lineWidth = Math.min(o.lw ?? 1.15 * U, Math.max(0.35 * U, rad * 0.22)); // small panes get thinner came
      LD.lineJoin = LD.lineCap = "round";
      LD.beginPath();
      B.poly(LD, lp >= 1 ? ring : B.trim(ring, 0, lp));
      LD.stroke();
    }
  }
  /** A subject piece: cuts the field lead, heavier lead, lit by the window's ripple. */
  function sub(pts, col, t, o = {}) {
    const [cx, cy] = o.c || centroid(pts);
    piece(pts, col, { ...o, c: [cx, cy], cut: true, lw: o.lw ?? 1.5 * U, lf: (o.lf ?? lightAt(cx, cy, t)) * (o.k ?? 1), lp: o.lp ?? leadAt(cx, cy, t) });
  }
  /** Fine dark paint lines on the glass (hatching for form, folds, shading); fades with the light. */
  function paint(lines, a, w) {
    if (a <= 0.01) return;
    PT.save();
    PT.strokeStyle = B.rgba(PAL.paint, 0.75 * a);
    PT.lineWidth = w;
    PT.lineCap = "round";
    PT.beginPath();
    for (const l of lines) B.poly(PT, l);
    PT.stroke();
    PT.restore();
  }
  const PIECES = new Map();
  /** The field: a jittered grid of irregular quads, some split into triangles (cached). */
  function fieldPieces(g, W, H) {
    const key = `${W}x${H}`;
    if (PIECES.has(key)) return PIECES.get(key);
    const f = g.fld, s = (g.P ? 8.6 : 7.4) * g.u, nx = Math.ceil(f.w / s) + 1, ny = Math.ceil(f.h / s) + 1, r = B.rng(7);
    const sx = f.w / (nx - 1), sy = f.h / (ny - 1);
    const pt = [];
    for (let j = 0; j < ny; j++)
      for (let i = 0; i < nx; i++) {
        const edge = i === 0 || j === 0 || i === nx - 1 || j === ny - 1;
        pt.push([f.x + i * sx + (edge ? 0 : r.range(-0.32, 0.32) * sx), f.y + j * sy + (edge ? 0 : r.range(-0.32, 0.32) * sy)]);
      }
    const out = [];
    for (let j = 0; j < ny - 1; j++)
      for (let i = 0; i < nx - 1; i++) {
        const a = pt[j * nx + i], b = pt[j * nx + i + 1], c = pt[(j + 1) * nx + i + 1], d = pt[(j + 1) * nx + i];
        if (![a, b, c, d].some((q) => inField(g, q[0], q[1])) && !inField(g, (a[0] + c[0]) / 2, (a[1] + c[1]) / 2)) continue;
        const split = r();
        if (split < 0.22) out.push([a, b, c], [a, c, d]);
        else if (split < 0.4) out.push([a, b, d], [b, c, d]);
        else out.push([a, b, c, d]);
      }
    PIECES.set(key, out.map((pts, k) => ({ pts, c: centroid(pts), k })));
    return PIECES.get(key);
  }
  /** Draw the field: every piece coloured by colourAt(x, y) and lit by the ripple; clipped to the arch. */
  function field(g, W, H, t, colourAt) {
    const ps = fieldPieces(g, W, H);
    for (const ctx of [G, LD]) {
      ctx.save();
      ctx.beginPath();
      archPath(ctx, g.inner.x0, g.inner.x1, g.inner.ys, g.inner.yb, g.inner.r, g.inner.k);
      ctx.clip();
    }
    for (const p of ps) piece(p.pts, colourAt(p.c[0], p.c[1], p.k), { lf: lightAt(p.c[0], p.c[1], t), lp: leadAt(p.c[0], p.c[1], t), seed: p.k });
    G.restore();
    LD.restore();
  }
  /** The window's frame: a band of small repeating panes round the arch. */
  function borderBand(g, t) {
    const n = g.P ? 46 : 40;
    // walk the outline of the arch at mid-band and cut it into short pieces
    const b2 = g.band / 2, x0 = g.x0 + b2, x1 = g.x1 - b2, r = g.r - b2, ys = g.ys, yb = g.yb - b2;
    const d = r - (x1 - x0) / 2, a = Math.atan2(Math.sqrt(r * r - d * d), d);
    const kb = g.kAt(b2, g.top + b2), sq = ([x, y]) => [x, ys + (y - ys) * kb];
    const path = [[x0, yb], ...B.arcPts(x0 + r, ys, r, Math.PI, Math.PI + a, 24).map(sq), ...B.arcPts(x1 - r, ys, r, 2 * Math.PI - a, 2 * Math.PI, 24).map(sq), [x1, yb]];
    const cols = [PAL.ruby, PAL.amber, PAL.sapphire, PAL.amber];
    for (let i = 0; i < n; i++) {
      const p0 = B.pointAt(path, i / n), p1 = B.pointAt(path, (i + 1) / n);
      const nx0 = -Math.sin(p0[2]) * b2, ny0 = Math.cos(p0[2]) * b2, nx1 = -Math.sin(p1[2]) * b2, ny1 = Math.cos(p1[2]) * b2;
      const quad = [[p0[0] - nx0, p0[1] - ny0], [p1[0] - nx1, p1[1] - ny1], [p1[0] + nx1, p1[1] + ny1], [p0[0] + nx0, p0[1] + ny0]];
      const c = centroid(quad);
      piece(quad, cols[i % 4], { lf: 0.25 + 0.75 * lightAt(c[0], c[1], t), lp: 1, seed: 900 + i, lw: 0.9 * U });
    }
  }
  /** Pale glass banner curling across the scene, with folded-back tails; returns its centre line for lettering. */
  function banner(cx, cy, w, h, t, o = {}) {
    const n = 16, top = [], bot = [], curl = h * (o.curl ?? 0.18);
    for (let i = 0; i <= n; i++) {
      const x = cx - w / 2 + (w * i) / n, s = Math.sin((i / n) * Math.PI * 2 + 0.6) * curl;
      top.push([x, cy - h / 2 + s]);
      bot.push([x, cy + h / 2 + s]);
    }
    const lf = o.lf ?? lightAt(cx, cy, t), lp = o.lp ?? leadAt(cx, cy, t);
    // tails: folded ends in a deeper amber, forked
    const tw = h * 0.42, tl = [top[0], [top[0][0] - tw, top[0][1] + h * 0.05], [top[0][0] - tw * 0.55, cy + h * 0.1 + curl * 0.6], [bot[0][0] - tw, bot[0][1] + h * 0.15], bot[0]];
    const e = top[n], eb = bot[n];
    const tr = [e, [e[0] + tw, e[1] + h * 0.05], [e[0] + tw * 0.55, cy + h * 0.1 + curl * 0.2], [eb[0] + tw, eb[1] + h * 0.15], eb];
    sub(tl, B.mix(PAL.amber, PAL.pale, 0.35), t, { lf, lp, seed: 11 });
    sub(tr, B.mix(PAL.amber, PAL.pale, 0.35), t, { lf, lp, seed: 12 });
    sub(top.concat(bot.reverse()), PAL.pale, t, { lf, lp, c: [cx, cy], seed: 13, boost: 0.05 });
    return lf;
  }
  /** Dark paint lettering on a banner (blackletter for headings, serif for small words), fading with the light. */
  function lettering(ctx, str, x, y, size, a, o = {}) {
    if (a <= 0.01) return;
    B.text(ctx, str, x, y, { size, minSize: Math.min(size, 3.95 * U), family: o.serif ? SERIF : GOTH, weight: o.serif ? 700 : 400, color: PAL.paint, maxW: o.maxW, maxLines: o.maxLines ?? 2, lineH: o.lineH ?? 1.05, alpha: a, letterSpacing: o.serif ? 0.04 : 0.01 });
  }
  /** Round medallion: a ring of small bead panes round a disc of glass. Returns the disc's light. */
  function medallion(cx, cy, r, inner, t, o = {}) {
    const lf = o.lf ?? lightAt(cx, cy, t), lp = o.lp ?? leadAt(cx, cy, t), nb = Math.max(14, Math.round((B.TAU * r * 1.12) / (r * 0.2)));
    sub(circlePts(cx, cy, r * 1.25, 48), PAL.violet, t, { lf, lp, seed: 30 });
    for (let i = 0; i < nb; i++) {
      const a = (i / nb) * B.TAU, bx = cx + Math.cos(a) * r * 1.12, by = cy + Math.sin(a) * r * 1.12;
      sub(circlePts(bx, by, r * 0.085, 10), i % 2 ? PAL.amber : PAL.pale, t, { lf, lp, lw: 0.8 * U, seed: 40 + i });
    }
    sub(circlePts(cx, cy, r, 48), inner, t, { lf, lp, seed: 31, boost: o.boost ?? 0, k: o.k });
    return lf;
  }
  /** The sun: an amber disc with a ring of wedge rays, alternating amber and ruby; paint swirls on the disc. */
  function sunPanes(cx, cy, r, t, o = {}) {
    const n = 16;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU + (o.rot ?? 0), dA = Math.PI / n, r2 = r * (i % 2 ? 1.55 : 1.95);
      sub([[cx + Math.cos(a - dA) * r * 1.04, cy + Math.sin(a - dA) * r * 1.04], [cx + Math.cos(a) * r2, cy + Math.sin(a) * r2], [cx + Math.cos(a + dA) * r * 1.04, cy + Math.sin(a + dA) * r * 1.04]], i % 2 ? PAL.ruby : PAL.amber, t, { seed: 50 + i, k: o.k });
    }
    sub(circlePts(cx, cy, r, 48), PAL.amber, t, { seed: 49, boost: 0.12, k: o.k });
    const sw = [];
    for (let k = 0; k < 3; k++) sw.push(B.arcPts(cx, cy, r * (0.35 + k * 0.2), 0.4 + k, 0.4 + k + 2.2, 16));
    paint(sw, lightAt(cx, cy, t), 0.35 * U);
  }
  /** The earth: a sapphire disc with emerald land pieces and paint hatching on its night side. */
  function earthPanes(cx, cy, r, t, o = {}) {
    sub(circlePts(cx, cy, r, 44), PAL.sapphire, t, { seed: 60, k: o.k });
    const land = [[-0.3, -0.25, 0.42, 3], [0.35, 0.3, 0.36, 4], [0.25, -0.45, 0.2, 5]];
    for (const [dx, dy, s, sd] of land) {
      const pts = [];
      for (let i = 0; i < 14; i++) {
        const a = (i / 14) * B.TAU, k = 1 + 0.28 * B.noise1(i * 0.7, sd);
        pts.push([cx + (dx + Math.cos(a) * s * k) * r, cy + (dy + Math.sin(a) * s * k * 0.8) * r]);
      }
      sub(pts.map(([x, y]) => {
        const d = Math.hypot(x - cx, y - cy), m = Math.min(1, (r * 0.9) / d);
        return [cx + (x - cx) * m, cy + (y - cy) * m];
      }), PAL.emerald, t, { seed: 61 + sd, k: o.k });
    }
    const hl = [];
    for (let k = 0; k < 7; k++) {
      const a = 0.2 + k * 0.17;
      hl.push([[cx + Math.cos(a) * r * 0.55, cy + Math.sin(a) * r * 0.55], [cx + Math.cos(a) * r * 0.93, cy + Math.sin(a) * r * 0.93]]);
    }
    paint(hl, lightAt(cx, cy, t), 0.3 * U);
  }
  /** A pointed strip of amber glass as an arrow, led round, from (x0, y0) to (x1, y1); drawn on by p. */
  function leadArrow(x0, y0, x1, y1, w, p, t) {
    if (p <= 0.01) return;
    const a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0) * p, hl = w * 2.2;
    const ex = x0 + Math.cos(a) * L, ey = y0 + Math.sin(a) * L, bx = ex - Math.cos(a) * hl, by = ey - Math.sin(a) * hl;
    const nx = -Math.sin(a), ny = Math.cos(a);
    const shaft = [[x0 + nx * w / 2, y0 + ny * w / 2], [bx + nx * w / 2, by + ny * w / 2], [bx - nx * w / 2, by - ny * w / 2], [x0 - nx * w / 2, y0 - ny * w / 2]];
    const head = [[bx + nx * w * 1.4, by + ny * w * 1.4], [ex, ey], [bx - nx * w * 1.4, by - ny * w * 1.4]];
    if (L > hl) sub(shaft, PAL.amber, t, { lf: 1, lp: 1, seed: 70, boost: 0.1 });
    sub(head, PAL.ruby, t, { lf: 1, lp: 1, seed: 71 });
  }

  // ---- the windows (the setting: replace these)
  /** Field colours: sapphire sky with violet patches and a few amber or ruby sparks, emerald ground at the foot. */
  function skyField(g, seed, ground = 0.78) {
    return (x, y, k) => {
      const ny = (y - g.fld.y) / g.fld.h, n = B.fbm(x / (g.u * 30), y / (g.u * 30), 3, seed), h = B.hash01(seed, k);
      if (ny > ground + 0.05 * B.noise1(x / (g.u * 20), seed)) return h < 0.12 ? PAL.amber : PAL.emerald;
      if (h < 0.05) return PAL.amber;
      if (h < 0.08) return PAL.ruby;
      return n > 0.18 ? PAL.violet : PAL.sapphire;
    };
  }

  function winTitle(g, W, H, t, out) {
    const u = g.u, P = g.P, f = g.fld, sc = [f.cx, f.y + f.h * (P ? 0.27 : 0.26)], sr = (P ? 12 : 8.5) * u;
    LIGHT = { a: 0, b: WINDOWS[0][1], ox: sc[0], oy: sc[1], reach: f.h, k: 1 };
    field(g, W, H, t, skyField(g, 3));
    sunPanes(sc[0], sc[1], sr, t);
    const by = f.y + f.h * (P ? 0.63 : 0.6), bw = f.w * (P ? 0.74 : 0.7), bh = (P ? 25 : 23) * u;
    const lf = banner(f.cx, by, bw, bh, t, { curl: 0.1 });
    out.push(() => (ctx) => lettering(ctx, "How old is\nsunlight?", f.cx, by - bh * 0.03, (P ? 9.6 : 8.6) * u, lf, { maxW: bw * 0.86 }));
    const sb = by + bh * 0.98, sw = f.w * (P ? 0.88 : 0.66), sh = (P ? 7.5 : 7) * u, lf2 = banner(f.cx, sb, sw, sh, t, { curl: 0.1 });
    out.push(() => (ctx) => lettering(ctx, "a window on the speed of light", f.cx, sb + sh * 0.04, (P ? 4.2 : 4.6) * u, lf2, { serif: true, maxW: sw * 0.9, maxLines: 1 }));
  }

  function winDiagram(g, W, H, t, out) {
    const u = g.u, P = g.P, f = g.fld, lt = t - WINDOWS[1][0];
    const sc = P ? [f.cx, f.y + f.h * 0.26] : [f.x + f.w * 0.2, f.y + f.h * 0.52], sr = (P ? 9.5 : 9) * u;
    const ec = P ? [f.cx, f.y + f.h * 0.83] : [f.x + f.w * 0.81, f.y + f.h * 0.52], er = (P ? 9 : 8) * u;
    LIGHT = { a: WINDOWS[1][0], b: WINDOWS[1][1], ox: sc[0], oy: sc[1], reach: f.h * 1.1 };
    field(g, W, H, t, skyField(g, 9, 2));
    sunPanes(sc[0], sc[1], sr, t);
    earthPanes(ec[0], ec[1], er, t);
    // arrow: a led strip of light from the sun to the earth, after the window is lit
    const ap = B.prog(lt, 1.2, 0.6, "inOutSine");
    const s0 = P ? [sc[0], sc[1] + sr * 2.15] : [sc[0] + sr * 2.15, sc[1]], s1 = P ? [ec[0], ec[1] - er * 1.45] : [ec[0] - er * 1.5, ec[1]];
    leadArrow(s0[0], s0[1], s1[0], s1[1], (P ? 2.4 : 2.2) * u, ap, t);
    if (ap > 0.05) out.push(() => (ctx) => {
      // a ray of light travelling along the strip
      const k = B.fract((lt - 1.2) / 0.9), x = B.lerp(s0[0], s1[0], k), y = B.lerp(s0[1], s1[1], k);
      B.glow(ctx, x, y, 7 * u, "#ffd98a", 0.65 * B.smooth(0, 0.3, ap), { add: true });
    });
    // labels on small banners beside their subjects, the distance on a banner across the strip
    const lab = (P ? 4.2 : 4.6) * u, tag = (txt, x, y, w2, at) => {
      const lf = Math.min(lightAt(x, y, t), B.smooth(at, at + 0.3, lt));
      banner(x, y, w2, lab * 1.9, t, { lf, curl: 0.1 });
      out.push(() => (ctx) => lettering(ctx, txt, x, y + lab * 0.05, lab, lf, { serif: true, maxW: w2 * 0.9, maxLines: 1 }));
    };
    if (P) {
      tag("The Sun", f.x + f.w * 0.78, sc[1] + sr * 1.9, f.w * 0.32, 1.0);
      tag("Earth", f.x + f.w * 0.2, ec[1] - er * 0.2, f.w * 0.24, 1.1);
      tag("150 million km", f.x + f.w * 0.62, B.lerp(s0[1], s1[1], 0.5), f.w * 0.52, 1.6);
    } else {
      tag("The Sun", sc[0], sc[1] + sr * 2.55, f.w * 0.27, 1.0);
      tag("Earth", ec[0], ec[1] + er * 2.2, f.w * 0.22, 1.1);
      tag("150 million km", f.x + f.w * 0.505, sc[1] - 9 * u, f.w * 0.4, 1.6);
    }
  }

  function winNumber(g, W, H, t, out) {
    const u = g.u, P = g.P, f = g.fld, lt = t - WINDOWS[2][0];
    const mc = P ? [f.cx, f.y + f.h * 0.46] : [f.x + f.w * 0.31, f.y + f.h * 0.55], mr = (P ? 22 : 16) * u;
    LIGHT = { a: WINDOWS[2][0], b: WINDOWS[2][1], ox: mc[0], oy: mc[1], reach: f.h };
    field(g, W, H, t, (x, y, k) => {
      const d = Math.hypot(x - mc[0], y - mc[1]) / (mr * 3), h = B.hash01(5, k);
      return h < 0.06 ? PAL.amber : d < 0.62 ? (h < 0.5 ? PAL.ruby : PAL.violet) : h < 0.6 ? PAL.sapphire : PAL.violet;
    });
    // emphasis: the medallion lit far brighter than its neighbours
    const em = B.smooth(1.0, 1.4, lt);
    const lf = medallion(mc[0], mc[1], mr, PAL.amber, t, { boost: 0.18 * em });
    out.push(() => (ctx) => {
      if (em > 0) halo(ctx, mc[0], mc[1], mr, em * lf, t);
      lettering(ctx, "8", mc[0], mc[1] - mr * 0.12, mr * 1.15, lf, { maxLines: 1 });
      lettering(ctx, "minutes", mc[0], mc[1] + mr * 0.62, mr * 0.26, lf, { serif: true, maxLines: 1 });
    });
    const bx = P ? f.cx : f.x + f.w * 0.73, by = P ? mc[1] + mr * 1.75 : mc[1], bw = f.w * (P ? 0.84 : 0.42), bh = (P ? 15 : 19) * u;
    const lb = banner(bx, by, bw, bh, t, { lf: Math.min(lightAt(bx, by, t), B.smooth(0.9, 1.3, lt)), curl: 0.12 });
    out.push(() => (ctx) => lettering(ctx, "from the Sun's\nsurface to Earth", bx, by + bh * 0.03, (P ? 4.6 : 6) * u, lb, { serif: true, maxW: bw * 0.86, lineH: 1.1 }));
  }
  /** Halo of rays round the emphasised pane: thin warm beams, additive. */
  function halo(ctx, cx, cy, r, a, t) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < 24; i++) {
      const ang = (i / 24) * B.TAU + t * 0.08, len = r * (1.9 + 0.5 * B.hash01("h", i) + 0.15 * B.wave(t, 1.7, i * 0.13));
      ctx.strokeStyle = B.linear(ctx, cx, cy, cx + Math.cos(ang) * len, cy + Math.sin(ang) * len, [[0, B.rgba("#ffe7a3", 0)], [0.55, B.rgba("#ffe7a3", 0.32 * a)], [1, B.rgba("#ffe7a3", 0)]]);
      ctx.lineWidth = r * 0.06;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(ang) * r * 1.3, cy + Math.sin(ang) * r * 1.3);
      ctx.lineTo(cx + Math.cos(ang) * len, cy + Math.sin(ang) * len);
      ctx.stroke();
    }
    ctx.restore();
    B.glow(ctx, cx, cy, r * 1.8, "#ffd477", 0.4 * a, { add: true });
  }

  /** Steps: one tall window of three panels, read top to bottom, each with its own medallion; unlit ones wait dim. */
  function winSteps(g, W, H, t, out) {
    const u = g.u, P = g.P, f = g.fld, lt = t - WINDOWS[3][0];
    LIGHT = { a: WINDOWS[3][0], b: WINDOWS[3][1], ox: f.cx, oy: f.y, reach: f.h };
    const y0 = P ? g.ys - 16 * u : f.y + f.h * 0.24, ph = (f.y + f.h - y0) / 3;
    field(g, W, H, t, (x, y, k) => {
      const h = B.hash01(8, k), band = Math.floor((y - y0) / ph);
      if (y < y0) return h < 0.3 ? PAL.amber : PAL.violet;
      if (h < 0.07) return PAL.amber;
      const pair = [[PAL.violet, PAL.ruby], [PAL.emerald, PAL.sapphire], [PAL.sapphire, PAL.violet]][B.clamp(band, 0, 2)];
      return h < 0.58 ? pair[0] : pair[1];
    });
    // the bars between panels: thick lead, inside the arch
    LD.save();
    LD.beginPath();
    archPath(LD, g.inner.x0, g.inner.x1, g.inner.ys, g.inner.yb, g.inner.r, g.inner.k);
    LD.clip();
    LD.fillStyle = PAL.lead;
    for (let i = 0; i < 3; i++) LD.fillRect(f.x, y0 + i * ph - 0.9 * u, f.w * leadAt(f.cx, y0 + i * ph, t), 1.8 * u);
    LD.restore();
    const steps = [["Light leaves the\nSun's surface", 0.7], ["It races out\nat 300,000 km/s", 1.6], ["Earth is lit\n8 minutes later", 2.6]];
    steps.forEach(([txt, at], i) => {
      const cy = y0 + (i + 0.5) * ph, mr = Math.min(ph * (P ? 0.26 : 0.34), (P ? 10 : 7.5) * u), mx = f.x + f.w * (P ? 0.2 : 0.21);
      const on = B.smooth(at, at + 0.35, lt), active = on * (1 - B.smooth(at + 0.9, at + 1.2, lt) * (i < 2 ? 1 : 0));
      const lf = Math.min(lightAt(mx, cy, t), 0.58 + 0.42 * on);
      medallion(mx, cy, mr, [PAL.ruby, PAL.amber, PAL.sapphire][i], t, { lf, boost: 0.2 * active });
      if (i === 0) {
        sub(circlePts(mx, cy, mr * 0.55, 30), PAL.amber, t, { lf, seed: 81, boost: 0.25 });
        sub(circlePts(mx, cy, mr * 0.25, 20), PAL.pale, t, { lf, seed: 82, boost: 0.3 });
      } else if (i === 1) {
        const ray = [[-0.7, -0.06], [0.35, -0.06], [0.35, -0.18], [0.75, 0], [0.35, 0.18], [0.35, 0.06], [-0.7, 0.06]];
        for (let k = 0; k < 3; k++) sub(ray.map(([a, b]) => [mx + a * mr, cy + (k - 1 + b) * mr * 0.42 + b * mr * 0.58]), PAL.pale, t, { lf, seed: 83 + k, lw: 0.9 * U });
      } else earthPanes(mx, cy, mr * 0.8, t, { k: lf / Math.max(0.01, lightAt(mx, cy, t)) });
      const bx = f.x + f.w * (P ? 0.7 : 0.62), bw = f.w * (P ? 0.48 : 0.56), bh = Math.min(ph * 0.8, (P ? 13 : 13.5) * u);
      const lb = banner(bx, cy, bw, bh, t, { lf: Math.min(lightAt(bx, cy, t), 0.55 + 0.45 * on), curl: 0.08 });
      // the step number on a small pale roundel at the medallion's upper left (left of it in landscape), inside the pane
      const nx = P ? mx - mr * 0.95 : mx - mr * 1.25 - 4.2 * u, ny = P ? cy - mr * 0.95 : cy, ln = Math.min(lightAt(nx, ny, t), 0.58 + 0.42 * on);
      sub(circlePts(nx, ny, (P ? 3.6 : 3.4) * u, 24), PAL.pale, t, { lf: ln, seed: 90 + i });
      out.push(() => (ctx) => {
        if (active > 0.01) halo(ctx, mx, cy, mr, active * 0.8, t);
        lettering(ctx, txt, bx, cy - bh * 0.02, (P ? 4.4 : 4.1) * u, Math.min(lb, on), { serif: true, maxW: bw * 0.84, lineH: 1.08 });
        lettering(ctx, String(i + 1), nx, ny - 0.2 * u, (P ? 5 : 4.6) * u, Math.min(ln, on), { serif: true, maxLines: 1 });
      });
    });
  }

  function winClose(g, W, H, t, out) {
    const u = g.u, P = g.P, f = g.fld, lt = t - WINDOWS[4][0];
    const sc = [f.cx, f.y + f.h * (P ? 0.27 : 0.26)], sr = (P ? 11 : 8) * u;
    LIGHT = { a: WINDOWS[4][0], b: DUR + 5, ox: sc[0], oy: sc[1], reach: f.h };
    field(g, W, H, t, skyField(g, 21, 0.8));
    sunPanes(sc[0], sc[1], sr, t, { rot: Math.PI / 16 });
    const by = f.y + f.h * (P ? 0.63 : 0.6), bw = f.w * (P ? 0.76 : 0.72), bh = (P ? 25 : 23) * u;
    const lf = banner(f.cx, by, bw, bh, t, { curl: 0.1 });
    out.push(() => (ctx) => {
      halo(ctx, sc[0], sc[1], sr * 1.3, B.smooth(1.2, 1.7, lt) * lf, t);
      lettering(ctx, "Sunlight is\neight minutes old", f.cx, by - bh * 0.03, (P ? 8.4 : 7.8) * u, lf, { maxW: bw * 0.86 });
    });
    const sb = by + bh * 0.98, sw = f.w * (P ? 0.94 : 0.74), sh = (P ? 7.5 : 7) * u, lf2 = banner(f.cx, sb, sw, sh, t, { curl: 0.1 });
    out.push(() => (ctx) => lettering(ctx, "counted from the Sun's surface", f.cx, sb + sh * 0.04, (P ? 3.95 : 4.4) * u, lf2, { serif: true, maxW: sw * 0.9, maxLines: 1 }));
  }
  const WIN_FNS = [winTitle, winDiagram, winNumber, winSteps, winClose];

  // ---- the room: stone wall, sill, floor, side lancets
  function stoneRoom(ctx, g, W, H) {
    const c = B.layer("sg-room", W, H, (r2, w, h) => {
      const u = g.u, r = B.rng(4);
      r2.fillStyle = B.shade(PAL.stone, -0.45);
      r2.fillRect(0, 0, w, h);
      // ashlar blocks
      const bh = 9 * u;
      for (let y = 0, row = 0; y < g.floor; y += bh, row++) {
        for (let x = -((row % 2) * 7 * u); x < w; x += 14 * u) {
          r2.fillStyle = B.shade(PAL.stone, -0.32 + r.range(-0.08, 0.08));
          r2.fillRect(x + 0.35 * u, y + 0.35 * u, 14 * u - 0.7 * u, bh - 0.7 * u);
        }
      }
      r2.fillStyle = B.shade(PAL.stone, -0.55); // the floor, darker
      r2.fillRect(0, g.floor, w, h - g.floor);
      B.mottle(r2, w, h, { amount: 0.4, feature: 0.05, seed: 6 });
      // the window's stone surround: a lighter moulded frame and a deep sill
      r2.save();
      r2.beginPath();
      archPath(r2, g.x0 - 3 * u, g.x1 + 3 * u, g.ys, g.yb + 2.5 * u, g.r + 3 * u, g.kAt(-3 * u, g.top - 3 * u));
      r2.fillStyle = B.linear(r2, g.x0, 0, g.x1, 0, [B.shade(PAL.stone, 0.05), B.shade(PAL.stone, -0.15), B.shade(PAL.stone, 0.0)]);
      r2.fill();
      r2.restore();
      r2.fillStyle = B.shade(PAL.stone, 0.12);
      r2.fillRect(g.x0 - 5 * u, g.yb, g.x1 - g.x0 + 10 * u, 2.5 * u);
      B.mottle(r2, w, h, { amount: 0.25, feature: 0.015, seed: 9, mode: "soft-light" });
    });
    ctx.drawImage(c, 0, 0);
  }
  /** Two side lancets (landscape only), lit with the main window. */
  function sideLancets(g, W, H, t) {
    if (g.P) return;
    const u = g.u;
    for (const side of [0, 1]) {
      const x0 = side ? W * 0.887 : W * 0.033, x1 = x0 + W * 0.08, ys = H * 0.24, yb = H * 0.82, r = (x1 - x0) / 2;
      const rows = 9, cols = 2, hh = (yb - ys) / rows;
      for (let j = -1; j < rows; j++)
        for (let i = 0; i < cols; i++) {
          const xa = x0 + (i * (x1 - x0)) / cols, xb = x0 + ((i + 1) * (x1 - x0)) / cols, ya = j < 0 ? ys - r : ys + j * hh, yb2 = j < 0 ? ys : ys + (j + 1) * hh;
          const pts = j < 0 ? B.arcPts(x0 + r, ys, r, Math.PI * (1 + i / 2), Math.PI * (1.5 + i / 2), 10).concat([[x0 + r, ys]]) : [[xa, ya], [xb, ya], [xb, yb2], [xa, yb2]];
          const c = centroid(pts);
          piece(pts, [PAL.ruby, PAL.sapphire, PAL.violet, PAL.amber][(i + j + 8 + side) % 4], { lf: 0.3 + 0.55 * lightAt(c[0], c[1], t), lp: 1, seed: 300 + j * 2 + i + side * 40, lw: 0.9 * u });
        }
      LD.strokeStyle = PAL.lead;
      LD.lineWidth = 1.6 * u;
      LD.beginPath();
      archPath(LD, x0, x1, ys, yb, r);
      LD.stroke();
    }
  }
  /** Mottled glass: swirls, streaks, seed bubbles (cached, greyscale, laid on in overlay). */
  function glassTexture(W, H, u) {
    return B.layer("sg-texture", W, H, (g2, w, h) => {
      const r = B.rng(12);
      B.mottle(g2, w, h, { amount: 1, feature: 0.03, seed: 14, mode: "source-over" });
      g2.lineCap = "round";
      for (let i = 0; i < 260; i++) {
        const x = r() * w, y = r() * h, a = r.range(-0.3, 0.3) + Math.PI / 2, l = r.range(2, 7) * u;
        g2.strokeStyle = r() < 0.5 ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.3)";
        g2.lineWidth = r.range(0.08, 0.25) * u;
        g2.beginPath();
        g2.moveTo(x, y);
        g2.quadraticCurveTo(x + Math.cos(a + 0.5) * l * 0.5, y + Math.sin(a + 0.5) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l);
        g2.stroke();
      }
      for (let i = 0; i < 700; i++) {
        g2.fillStyle = `rgba(255,255,255,${r.range(0.25, 0.6)})`;
        g2.beginPath();
        B.circle(g2, r() * w, r() * h, r.range(0.06, 0.22) * u);
        g2.fill();
      }
    });
  }

  // ---- frame
  function draw(ctx, W, H, t) {
    const g = geo(W, H);
    U = g.u;
    G = B.scratch("sg-glass", W, H);
    LD = B.scratch("sg-lead", W, H);
    PT = B.scratch("sg-paint", W, H);
    const wi = WINDOWS.findIndex(([a, b]) => t >= a && t < b), late = [];
    WIN_FNS[Math.max(0, wi)](g, W, H, t, late);
    borderBand(g, t);
    sideLancets(g, W, H, t);
    // glass texture, inside the glass only, in overlay so dark glass stays dark
    const TX = B.scratch("sg-tex", W, H);
    TX.drawImage(glassTexture(W, H, U), 0, 0);
    TX.globalCompositeOperation = "destination-in";
    TX.drawImage(G.canvas, 0, 0);
    G.save();
    G.globalCompositeOperation = "overlay";
    G.globalAlpha = 0.32;
    G.drawImage(TX.canvas, 0, 0);
    G.restore();
    G.drawImage(PT.canvas, 0, 0);
    // print the window into the room
    stoneRoom(ctx, g, W, H);
    ctx.drawImage(G.canvas, 0, 0);
    ctx.drawImage(LD.canvas, 0, 0);
    ctx.save(); // back-light glow bleeding a little over the lead
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.32;
    ctx.filter = `blur(${(1.1 * U).toFixed(1)}px)`;
    ctx.drawImage(G.canvas, 0, 0);
    ctx.globalAlpha = 0.18;
    ctx.filter = `blur(${(4 * U).toFixed(1)}px)`;
    ctx.drawImage(G.canvas, 0, 0);
    ctx.restore();
    late.forEach((mk) => mk()(ctx));
    // finishing: dark corners of a dim room, a fine grain
    B.vignette(ctx, W, H, { amount: 0.6, inner: 0.4 });
    // the light falls on the floor: shafts slant down from the sill and the leaded glass lands as a skewed pool
    const f = g.fld, fh = H - g.floor, sk = 0.55 + 0.05 * B.wave(t, 9), lit = lightAt(f.cx, f.y + f.h * 0.6, t);
    const m = [1.05, 0, sk * (fh / f.h) * 1.2, (fh * 1.1) / f.h, -f.x * 0.05 + W * 0.04 - sk * (fh / f.h) * 1.2 * f.y, g.floor - (f.y * fh * 1.1) / f.h];
    const pr = (x, y) => [m[0] * x + m[2] * y + m[4], m[3] * y + m[5]];
    const FL = B.scratch("sg-floor", W, H);
    FL.drawImage(G.canvas, 0, 0);
    FL.globalCompositeOperation = "destination-out";
    FL.drawImage(LD.canvas, 0, 0);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    [PAL.amber, PAL.ruby, PAL.sapphire, PAL.emerald, PAL.violet, PAL.amber].forEach((c, i) => {
      const k0 = i / 6, k1 = (i + 0.7) / 6, xa = B.lerp(f.x, f.x + f.w, k0), xb = B.lerp(f.x, f.x + f.w, k1);
      const ys = g.yb, pa = pr(xa, f.y + f.h * 0.5), pb = pr(xb, f.y + f.h * 0.5);
      ctx.fillStyle = B.linear(ctx, 0, ys, 0, pa[1], [[0, B.rgba(c, 0.05 * lit)], [1, B.rgba(c, 0.2 * lit)]]);
      ctx.beginPath();
      B.poly(ctx, [[xa, ys], [xb, ys], pb, pa], true);
      ctx.fill();
    });
    ctx.beginPath();
    ctx.rect(0, g.floor, W, H);
    ctx.clip();
    ctx.globalAlpha = 0.72 * B.clamp(0.25 + lit);
    ctx.filter = `blur(${(0.5 * U).toFixed(1)}px)`;
    ctx.setTransform(...m);
    ctx.drawImage(FL.canvas, 0, 0);
    ctx.restore();
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12 });
  }

  // ---- sound: organ drone, crystal pings as panes light, glass tinkles
  SOUND.define("glass-ping", (v, o) => {
    // a crystal ping: a pure high tone with an inharmonic partial, long ringing tail
    const f = v.hz(o.note ?? "E6");
    v.tone({ f, a: 0.002, len: 1.4, peak: 0.12 });
    v.tone({ f: f * 2.76, a: 0.001, len: 0.5, peak: 0.04 });
    v.tone({ f: f * 5.4, a: 0.001, len: 0.15, peak: 0.02 });
  }, { verb: 0.6 });
  SOUND.define("glass-organ", (v, o) => {
    // organ-like bed: stacked sines and a soft square at the octave, a slow swell
    const d = v.dur ?? 8, g = v.bedGain(d, 0.11, o.fade ?? 2);
    (o.notes || ["D2", "A2", "D3", "F3"]).forEach((n, i) => {
      for (const [m, type, pk] of [[1, "sine", 0.5], [2, "sine", 0.25], [4, "triangle", 0.06]]) v.tone({ type, f: v.hz(n) * m, detune: (i - 1.5) * 3, a: 0.01, hold: d, len: 0.1, peak: pk / 4, dest: g, noPitch: true });
    });
  }, { bed: true, verb: 0.6 });

  function score(k) {
    k.bed("glass-organ", 0, DUR, { notes: ["D2", "A2", "D3", "F3"], gain: 0.9 });
    const sc = SOUND.scale("D5", "pent", 10);
    // each window: lead draws (soft tinkle), then a ripple of pings as the panes light from the centre
    WINDOWS.forEach(([a], i) => {
      k.at(a + 0.05, "rustle", { dur: 0.4, gain: 0.25, pitch: 8 });
      k.seq(a + 0.6, 0.075, [0, 2, 4, 3, 5, 7, 6, 9].map((j) => sc[(j + i) % 10]), { voice: "glass-ping", gain: 0.55 });
      if (i > 0) k.at(a - 0.35, "fall", { dur: 0.35, gain: 0.12 });
    });
    k.at(0.0, "swell", { dur: 1.2, gain: 0.2 });
    // the arrow of light and its labels
    k.at(BEATS[1] + 1.2, "riser", { dur: 0.6, gain: 0.2 }).at(BEATS[1] + 1.8, "glass-ping", { note: "A6", gain: 0.6 });
    // key number: the medallion flares
    k.at(BEATS[2] + 1.0, "bell", { note: "D5", gain: 0.45 }).at(BEATS[2] + 1.0, "glass-ping", { note: "D7", gain: 0.5 });
    k.at(BEATS[2] + 1.05, "chord", { notes: ["D4", "F#4", "A4", "D5"], gain: 0.35 });
    // three panels light in turn
    [0.7, 1.6, 2.6].forEach((at, i) => {
      k.at(WINDOWS[3][0] + at, "glass-ping", { note: ["A5", "D6", "F#6"][i], gain: 0.8 });
      k.at(WINDOWS[3][0] + at + 0.05, "chime", { note: ["A5", "D6", "F#6"][i], gain: 0.25 });
    });
    // close
    k.at(BEATS[5] + 1.2, "bell", { note: "D4", gain: 0.45 }).at(BEATS[5] + 1.25, "chord", { notes: ["D4", "A4", "D5", "F#5"], strum: 0.06, gain: 0.35 });
  }

  Player.register({
    id: "stained-glass",
    name: "Stained Glass",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&family=Cormorant+Garamond:wght@600;700&display=swap",
      faces: ['400 20px "UnifrakturMaguntia"', '700 20px "Cormorant Garamond"', '600 20px "Cormorant Garamond"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.95, 4.4, 6.6, 9.1, 10.5, 12.8],
    draw,
    score,
  });
})();
