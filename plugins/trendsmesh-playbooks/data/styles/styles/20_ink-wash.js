/* 20 Ink Wash - reference animation.
 * Topic (setting, replace it): "Why is one side of a mountain dry?" - the rain shadow.
 * Rendering (keep it): black ink only, in many dilutions, on warm rice paper with long faint fibres and stains.
 * Brush strokes are built from a wet core plus bristle hairs: a heavy press where the brush lands, a swelling and
 * thinning body, and a tail that breaks into dry-brush hairs where the brush skips the grain. Washes are pools of
 * grey that bloom outward and dry with a darker rim and a grainy inside; mist bands erase the washes to split near,
 * middle and far. Ink and washes are painted on two layers and printed into the paper (multiply, with a slight
 * bleed); the only colour is one small red seal with a carved glyph that presses down with a soft squash.
 * Motion: strokes painted in real time, washes blooming over a second or two, long still pauses, beats changing
 * by mist drifting across the frame. Nothing bounces.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // --- palette and type (from the card)
  const PAL = { paper: "#f1ebdc", stain: "#e0d6bd", ink: "#16150f", mid: "#6c6a62", pale: "#b9b6a8", seal: "#b3261e" };
  const SERIF = "Cormorant Garamond", JP = "Noto Serif JP";
  const DUR = 14;
  // the canvas never asks for the kanji subset of the face, so ask for it here, before the runtime waits on fonts
  if (document.fonts) for (const w of [500, 700]) document.fonts.load(w + ' 20px "Noto Serif JP"', "山雨風0123456789°C").catch(() => null);
  const BEATS = [0, 2.5, 5.3, 7.5, 10.0, 11.8], STEP_AT = [7.7, 8.6, 10.1];

  // per-frame: the two painting layers, the unit, the current scene's opacity
  let WL = null, KL = null, U = 1, A = 1;

  /** Ink at a density (0 = paper, 1 = full black): the only depth cue in this medium. */
  const inkTone = (d) => B.mix(PAL.paper, PAL.ink, B.clamp(d));

  // --- ink-wash helpers (reuse these)
  /**
   * One brush stroke on the ink layer, revealed to p: a wet core (ragged ribbon) plus a fan of bristle hairs; the
   * core narrows as the brush dries, leaving hairs that skip where the grain is high.
   * o: { w (max width), p, d (density 0..1), seed, dry (tail start, 0.6), press (wet blob at touch-down, 1),
   *      reverse (dry start, pressed end: arrows), hairs (9) }
   */
  function inkStroke(pts, o) {
    const p = B.clamp(o.p ?? 1);
    if (p <= 0.002 || pts.length < 2) return;
    const w = o.w, seed = o.seed ?? 1, dry = o.dry ?? 0.6, rev = !!o.reverse, K = o.hairs ?? 9;
    const path = B.densify(pts, Math.max(1.5, w * 0.22));
    const n = path.length, cum = [0];
    for (let i = 1; i < n; i++) cum.push(cum[i - 1] + Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]));
    const L = cum[n - 1] || 1;
    const col = inkTone(o.d ?? 0.95);
    // ff = distance from where the brush landed, 0..1
    const width = (ff, s) => {
      const land = 0.7 + 0.3 * B.smooth(0, 0.05, ff);
      const press = 1 + 0.32 * (o.press ?? 1) * Math.exp(-ff * 9);
      const tail = 1 - 0.85 * Math.pow(B.smooth(0.55, 1, ff), 1.4);
      return w * land * press * (1 - 0.3 * ff) * tail * (1 + 0.12 * B.noise1(s / (w * 2.5), seed));
    };
    const dryness = (ff) => B.smooth(dry, 1, ff);
    const left = [], right = [], N = [], WD = [];
    let m = 0;
    for (let i = 0; i < n; i++) {
      const f = cum[i] / L;
      if (f > p + 1e-6) break;
      const ff = rev ? 1 - f : f;
      const a = path[Math.max(0, i - 1)], b = path[Math.min(n - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const l = Math.hypot(nx, ny) || 1;
      nx /= l;
      ny /= l;
      const wv = width(ff, cum[i]), core = wv * Math.pow(1 - dryness(ff), 0.8) * 0.92;
      const el = core / 2 * (1 + 0.1 * B.noise1(cum[i] / (w * 0.6), seed + 3)), er = core / 2 * (1 + 0.1 * B.noise1(cum[i] / (w * 0.6), seed + 7));
      left.push([path[i][0] + nx * el, path[i][1] + ny * el]);
      right.push([path[i][0] - nx * er, path[i][1] - ny * er]);
      N.push([nx, ny]);
      WD.push([wv, ff]);
      m = i + 1;
    }
    if (m < 2) return;
    const g = KL;
    g.save();
    g.globalAlpha = A * (o.alpha ?? 1);
    g.fillStyle = col;
    g.beginPath();
    B.poly(g, left.concat(right.reverse()), true);
    g.fill();
    // bristle hairs, broken where the brush skipped the grain
    g.strokeStyle = col;
    g.lineCap = "butt";
    for (let k = 0; k < K; k++) {
      const c = (k + 0.5) / K - 0.5;
      g.lineWidth = Math.max(0.6, (w / K) * 1.15);
      g.globalAlpha = A * (o.alpha ?? 1) * (0.65 + 0.35 * B.hash01(seed, k));
      g.beginPath();
      let on = false;
      for (let i = 0; i < m; i++) {
        const [wv, ff] = WD[i], dz = dryness(ff);
        const gap = B.noise2(cum[i] / (w * 0.7), k * 1.73, seed) * 0.5 + 0.5;
        const draw = dz > 0.02 && gap > 1.05 - dz * 0.95 ? false : true;
        const x = path[i][0] + N[i][0] * c * wv * 0.98, y = path[i][1] + N[i][1] * c * wv * 0.98;
        if (draw) {
          if (on) g.lineTo(x, y);
          else g.moveTo(x, y);
          on = true;
        } else on = false;
      }
      g.stroke();
    }
    // the wet tip while the brush travels
    if (p < 1 && !rev) {
      const q = path[m - 1], wv = WD[m - 1][0];
      g.globalAlpha = A * 0.35 * (1 - dryness(WD[m - 1][1]));
      g.beginPath();
      B.circle(g, q[0], q[1], wv * 0.45);
      g.fill();
    }
    g.restore();
  }
  /** Points of a soft irregular ellipse (for wash pools and blots). */
  function poolPts(cx, cy, rx, ry, seed, wob = 0.16, n = 48) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU, ca = Math.cos(a), sa = Math.sin(a);
      const k = 1 + wob * B.noise2(ca * 1.4 + seed * 3.1, sa * 1.4, seed) + wob * 0.4 * B.noise2(ca * 4 + seed, sa * 4, seed + 1);
      out.push([cx + ca * rx * k, cy + sa * ry * k]);
    }
    return out;
  }
  /** A wash pool: grey that blooms from 60 % to full size, then dries with a darker uneven rim.
   * o: { d (density), p (bloom), seed, alpha, rim } */
  function washPool(cx, cy, rx, ry, o) {
    const p = B.clamp(o.p ?? 1);
    if (p <= 0.002) return;
    const k = B.ease.outCubic(p), sc = 0.6 + 0.4 * k;
    const pts = poolPts(cx, cy, rx * sc, ry * sc, o.seed ?? 1, o.wob ?? 0.16);
    const g = WL;
    g.save();
    g.globalAlpha = A * (o.alpha ?? 0.55) * Math.min(1, p * 1.8);
    g.fillStyle = inkTone(o.d ?? 0.35);
    g.beginPath();
    B.poly(g, pts, true);
    g.fill();
    g.globalAlpha = A * (o.rim ?? 0.8) * B.smooth(0.35, 1, p);
    g.strokeStyle = inkTone((o.d ?? 0.35) + 0.18);
    g.lineJoin = "round";
    g.lineWidth = 0.32 * U;
    g.beginPath();
    B.poly(g, pts, true);
    g.stroke();
    g.restore();
  }
  /** A mountain ridge as points: bumps (peaks [x, height, half width]) above `base`, with crags from noise. */
  function ridgePts(x0, x1, base, peaks, seed) {
    const out = [], step = Math.max(2, (x1 - x0) / 140);
    for (let x = x0; x <= x1 + 0.1; x += step) {
      let h = 0;
      for (const [px, ph, hw] of peaks) {
        const d = Math.abs(x - px) / hw;
        const bump = Math.pow(Math.max(0, 1 - d), 1.35);
        h = Math.max(h, ph * bump * (1 + 0.1 * B.fbm(x / (hw * 0.18), seed, 3, seed)));
      }
      out.push([x, base - h]);
    }
    return out;
  }
  /** Mountain wash: the silhouette bleeds down from the ridge (front moves with p) into mist; a dried rim on top. */
  function mountainWash(ridge, base, o) {
    const p = B.clamp(o.p ?? 1);
    if (p <= 0.002) return;
    let top = Infinity;
    for (const q of ridge) top = Math.min(top, q[1]);
    const g = WL, col = inkTone(o.d ?? 0.3), a = o.alpha ?? 0.8, k = B.ease.outCubic(p);
    const front = top + (base - top) * (0.25 + 0.75 * k); // fully faded by the foot: no hard bottom edge
    g.save();
    g.globalAlpha = A;
    g.fillStyle = B.linear(g, 0, top, 0, front, [[0, B.rgba(col, a)], [0.55, B.rgba(col, a * 0.7)], [1, B.rgba(col, 0)]]);
    g.beginPath();
    B.poly(g, ridge.concat([[ridge[ridge.length - 1][0], base + U], [ridge[0][0], base + U]]), true);
    g.fill();
    g.globalAlpha = A * (o.rim ?? 0.7) * B.smooth(0.2, 0.8, p);
    g.strokeStyle = inkTone((o.d ?? 0.3) + 0.15);
    g.lineWidth = 0.4 * U;
    g.lineJoin = "round";
    g.beginPath();
    B.poly(g, ridge);
    g.stroke();
    g.restore();
  }
  /** A band of mist: soft paper-white wisps that erase what is beneath them (washes and ink) along a line. */
  function mist(y, h, x0, x1, amount, seed) {
    if (amount <= 0.002) return;
    const r = B.rng(seed);
    for (const g of [WL, KL]) {
      g.save();
      g.globalCompositeOperation = "destination-out";
      for (let i = 0; i < 7; i++) {
        const cx = B.lerp(x0, x1, (i + r.range(0.1, 0.9)) / 7), cy = y + r.range(-0.3, 0.3) * h, rx = (x1 - x0) * r.range(0.16, 0.26);
        g.save();
        g.translate(cx, cy);
        g.scale(rx / h, 1);
        g.globalAlpha = amount * (g === KL ? 0.55 : 0.9) * A;
        g.fillStyle = B.radial(g, 0, 0, 0, h, [[0, "rgba(0,0,0,1)"], [0.55, "rgba(0,0,0,0.6)"], [1, "rgba(0,0,0,0)"]]);
        g.fillRect(-h, -h, 2 * h, 2 * h);
        g.restore();
      }
      g.restore();
    }
  }
  /** Small ink dots (moss and far trees): little pressed blobs, each landing at its own moment. */
  function inkDots(cx, cy, spread, n, seed, p, d = 0.9) {
    const r = B.rng(seed), g = KL;
    g.save();
    g.fillStyle = inkTone(d);
    for (let i = 0; i < n; i++) {
      const x = cx + r.range(-1, 1) * spread, y = cy + r.range(-0.35, 0.35) * spread, s = r.range(0.35, 0.8) * U, at = r();
      const k = B.smooth(at * 0.7, at * 0.7 + 0.3, p);
      if (k <= 0) continue;
      g.globalAlpha = A * k * r.range(0.7, 1);
      g.beginPath();
      g.ellipse(x, y, s * 1.3, s * 0.8, r.range(-0.6, 0.6), 0, B.TAU);
      g.fill();
    }
    g.restore();
  }
  /** Fine slanted rain: hairlines of pale wash falling from a cloud, a few at a time. */
  function rainLines(x0, x1, y0, y1, n, seed, p) {
    if (p <= 0) return;
    const r = B.rng(seed), g = WL;
    g.save();
    g.strokeStyle = inkTone(0.45);
    g.lineCap = "round";
    for (let i = 0; i < n; i++) {
      const x = B.lerp(x0, x1, r()), len = (y1 - y0) * r.range(0.25, 0.6), yy = y0 + r() * (y1 - y0 - len), at = r() * 0.6;
      const k = B.smooth(at, at + 0.4, p);
      if (k <= 0) continue;
      g.globalAlpha = A * 0.6 * k;
      g.lineWidth = r.range(0.12, 0.25) * U;
      g.beginPath();
      g.moveTo(x, yy);
      g.lineTo(x - len * 0.18, yy + len * k);
      g.stroke();
    }
    g.restore();
  }
  /** Arrow as one curved brush sweep: a ragged dry tail, a full body and a small pressed-in head. */
  function brushArrow(pts, p, w, seed, d = 0.9) {
    inkStroke(pts, { w, p, d, seed, reverse: true, dry: 0.55, press: 0.4, hairs: 8 });
    const hp = B.smooth(0.88, 1, p);
    if (hp <= 0) return;
    const [x, y, a] = B.pointAt(pts, 1), hl = w * 2.6, g = KL;
    g.save();
    g.globalAlpha = A * hp;
    g.fillStyle = inkTone(d);
    g.translate(x, y);
    g.rotate(a);
    g.beginPath();
    g.moveTo(w * 0.4, 0);
    g.quadraticCurveTo(-hl * 0.5, -hl * 0.18, -hl, -hl * 0.62);
    g.quadraticCurveTo(-hl * 0.62, 0, -hl, hl * 0.62);
    g.quadraticCurveTo(-hl * 0.5, hl * 0.18, w * 0.4, 0);
    g.fill();
    g.restore();
  }
  /** Emphasis: an enso, a circle in one open loop, heavy where the brush lands and dry where it leaves. */
  function enso(cx, cy, r, p, seed) {
    const pts = [];
    for (let i = 0; i <= 80; i++) {
      const a = -2.2 + (i / 80) * B.TAU * 0.9;
      const rr = r * (1 + 0.03 * B.noise1(i * 0.12, seed) - 0.05 * (i / 80));
      pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]);
    }
    inkStroke(pts, { w: r * 0.13, p, d: 0.92, seed, dry: 0.5, hairs: 11 });
  }
  /** Short texture strokes down a slope (the brush marks that model rock), each a little dry stroke. */
  function slopeMarks(ridge, i0, i1, count, len, seed, p, d) {
    const r = B.rng(seed);
    for (let i = 0; i < count; i++) {
      const idx = Math.floor(B.lerp(i0, i1, (i + r.range(0.2, 0.8)) / count)), q = ridge[Math.min(ridge.length - 1, idx)];
      const ang = r.range(1.2, 1.9), l = len * r.range(0.6, 1.2);
      const pts = B.quad(q[0], q[1] + U * 0.6, q[0] + Math.cos(ang) * l * 0.4 + r.range(-1, 1) * U, q[1] + l * 0.5, q[0] + Math.cos(ang) * l, q[1] + Math.sin(ang) * l, 8);
      inkStroke(pts, { w: r.range(0.5, 0.9) * U, p: B.smooth(i / count * 0.7, i / count * 0.7 + 0.3, p), d, seed: seed + i, dry: 0.35, hairs: 5 });
    }
  }
  /** Lettering: slim high-contrast serif in dark ink, small and widely spaced, soaking in as it appears. */
  function letters(str, x, y, size, a, o = {}) {
    if (a <= 0.002) return null;
    return B.text(KL, str, x, y, { size, family: o.family || SERIF, weight: o.weight ?? 600, style: o.italic ? "italic" : "", color: o.color || PAL.ink, align: o.align || "left", baseline: o.baseline || "middle", letterSpacing: o.spacing ?? 0.12, lineH: o.lineH ?? 1.18, maxW: o.maxW, alpha: A * a });
  }
  /** Characters stacked vertically at the edge, one per line. */
  function vertical(chars, x, y, size, a) {
    if (a <= 0.002) return;
    [...chars].forEach((ch, i) => B.text(KL, ch, x, y + i * size * 1.25, { size, family: JP, weight: 500, color: PAL.ink, baseline: "top", alpha: A * B.smooth(i * 0.2, i * 0.2 + 0.6, a) }));
  }
  /** The red seal: a rough vermilion square, uneven coverage, a carved glyph; pressed with a quick soft squash. */
  function seal(ctx, x, y, s, since, alpha = 1) {
    if (since <= 0 || alpha <= 0.002) return;
    const g = B.scratch("ink-seal", Math.ceil(s * 1.4), Math.ceil(s * 1.4)), c = s * 0.7;
    const r = B.rng(77);
    g.fillStyle = PAL.seal;
    g.beginPath();
    B.poly(g, B.densify(B.rectPts(c - s / 2, c - s / 2, s, s), s / 6).map(([x, y]) => [x + r.range(-0.012, 0.012) * s, y + r.range(-0.012, 0.012) * s]), true); // a hand-cut edge
    g.fill();
    // carved glyph (mountain: three uprights on a base), cut out to paper
    g.globalCompositeOperation = "destination-out";
    g.lineCap = "square";
    g.lineWidth = s * 0.085;
    g.beginPath();
    g.moveTo(c - s * 0.26, c - s * 0.12);
    g.lineTo(c - s * 0.26, c + s * 0.24);
    g.lineTo(c + s * 0.26, c + s * 0.24);
    g.lineTo(c + s * 0.26, c - s * 0.12);
    g.moveTo(c, c - s * 0.3);
    g.lineTo(c, c + s * 0.24);
    g.stroke();
    g.lineWidth = s * 0.04; // the carved border inside the edge
    g.strokeRect(c - s * 0.4, c - s * 0.4, s * 0.8, s * 0.8);
    for (let i = 0; i < 70; i++) {
      g.globalAlpha = r.range(0.3, 1);
      g.beginPath();
      B.circle(g, c + r.range(-0.5, 0.5) * s, c + r.range(-0.5, 0.5) * s, r.range(0.004, 0.02) * s);
      g.fill();
    }
    g.globalAlpha = 1;
    g.globalCompositeOperation = "source-over";
    const k = B.clamp(since / 0.18), sq = 1 - 0.1 * Math.sin(Math.PI * k);
    ctx.save();
    ctx.globalAlpha = alpha * B.smooth(0, 0.06, since) * 0.92;
    ctx.globalCompositeOperation = "multiply";
    ctx.translate(x, y);
    ctx.scale(2 - sq, sq);
    ctx.drawImage(g.canvas, -c, -c);
    ctx.restore();
  }
  /** Long faint paper fibres and pale stains, cached: laid over everything so the ink sits in the sheet. */
  function fibres(ctx, W, H) {
    const c = B.layer("ink-fibres", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(31);
      for (let i = 0; i < 26; i++) {
        const x = r() * w, y = r() * h, rad = r.range(6, 20) * u;
        g.fillStyle = B.radial(g, x, y, 0, rad, [[0, B.rgba(PAL.stain, 0.35)], [0.7, B.rgba(PAL.stain, 0.12)], [1, B.rgba(PAL.stain, 0)]]);
        g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
      }
      g.lineCap = "round";
      for (let i = 0; i < 420; i++) {
        const x = r() * w, y = r() * h, a = r.range(-0.5, 0.5) + (r() < 0.5 ? 0 : Math.PI / 2), len = r.range(4, 16) * u;
        g.strokeStyle = r() < 0.6 ? B.rgba("#8a7f66", r.range(0.05, 0.12)) : B.rgba("#ffffff", 0.25);
        g.lineWidth = r.range(0.05, 0.16) * u;
        g.beginPath();
        g.moveTo(x, y);
        g.bezierCurveTo(x + Math.cos(a + 0.3) * len * 0.3, y + Math.sin(a + 0.3) * len * 0.3, x + Math.cos(a - 0.3) * len * 0.7, y + Math.sin(a - 0.3) * len * 0.7, x + Math.cos(a) * len, y + Math.sin(a) * len);
        g.stroke();
      }
    });
    ctx.save(); ctx.globalCompositeOperation = "multiply"; // never pales the ink
    ctx.drawImage(c, 0, 0); ctx.restore();
  }

  // --- layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    return {
      F, u, P, S,
      // the main mountain diagram
      // 9:16 stacks: the lettering above, a taller mountain filling the lower two thirds
      base: P ? H * 0.77 : H * 0.84,
      peak: P ? [W * 0.56, H * 0.37, W * 0.46] : [W * 0.6, H * 0.5, W * 0.25],
      far: P ? [[W * 0.18, H * 0.2, W * 0.32], [W * 0.95, H * 0.25, W * 0.36]] : [[W * 0.37, H * 0.27, W * 0.19], [W * 0.88, H * 0.34, W * 0.22]],
      title: P ? [S.x + 2 * u, S.y + 6 * u] : [S.x + 2 * u, S.y + 15 * u],
      head: P ? 7 * u : 6.4 * u,
      label: P ? 4.2 * u : 4 * u,
    };
  }

  // --- subjects (the setting: replace these)
  /** The windward/leeward mountain, painted progressively from local time lt (s). */
  function bigMountain(L, W, lt, o = {}) {
    const u = L.u, base = L.base, [px, ph, hw] = L.peak;
    // far range first, palest (far = pale and soft)
    L.far.forEach((pk, i) => {
      const ridge = ridgePts(pk[0] - pk[2], pk[0] + pk[2], base - ph * 0.25, [pk], 40 + i);
      mountainWash(ridge, base - ph * 0.25, { d: 0.22, p: B.prog(lt, 0.1 + i * 0.25, 1.6), alpha: 0.55, seed: i });
    });
    mist(base - ph * 0.3, ph * 0.22, 0, W, 0.8 * B.prog(lt, 0.4, 1.4), 9);
    // the near mountain: a wash, then one confident outline stroke over its ridge and a few rock marks
    const ridge = ridgePts(px - hw, px + hw, base, [[px, ph, hw], [px + hw * 0.42, ph * 0.55, hw * 0.45]], 5);
    mountainWash(ridge, base, { d: 0.42, p: B.prog(lt, 0.5, 1.8), alpha: 0.75 });
    const pi = ridge.reduce((bi, q, i) => (q[1] < ridge[bi][1] ? i : bi), 0);
    inkStroke(ridge.slice(Math.floor(pi * 0.25), Math.floor(pi + (ridge.length - pi) * 0.75)), { w: (L.P ? 1.9 : 1.7) * u, p: B.prog(lt, 0.3, 1.1, "inOutSine"), d: 0.95, seed: 12, dry: 0.62 });
    slopeMarks(ridge, pi * 0.45, pi * 0.95, 5, (L.P ? 9 : 7) * u, 20, B.prog(lt, 1.3, 0.9), 0.85);
    inkDots(px - hw * 0.05, ridge[pi][1] + ph * 0.08, hw * 0.12, 9, 3, B.prog(lt, 1.6, 0.6));
    mist(base - ph * 0.04, ph * 0.12, 0, W, 0.9, 10);
    return { ridge, pi };
  }

  // --- the beats
  function sceneTitle(L, W, H, t) {
    const u = L.u, P = L.P, [tx, ty] = L.title;
    bigMountain(L, W, t + 0.2);
    const a = B.smooth(0.7, 1.4, t);
    const r = letters("Why is one side\nof a mountain dry?", tx, ty, L.head, a, { baseline: "top", maxW: L.S.w * (P ? 0.9 : 0.55), spacing: 0.06, weight: 600 });
    letters("on the rain shadow", tx, (r ? r.bottom : ty) + L.label * 1.3, L.label, B.smooth(1.0, 1.6, t), { italic: true, weight: 500, spacing: 0.2 });
    vertical("山雨", L.S.r - L.label * 1.4, P ? L.S.y + 2 * u : L.S.y + 2 * u, L.label * 1.35, B.smooth(0.9, 1.6, t));
  }

  function sceneDiagram(L, W, H, t, lt) {
    const u = L.u, P = L.P, S = L.S, base = L.base, [px, ph, hw] = L.peak;
    const { ridge, pi } = bigMountain(L, W, lt + 2.2);
    // the sea at the windward foot: a few horizontal wave strokes
    for (let i = 0; i < 4; i++) {
      const y = base + (1.6 + i * 1.7) * u, x0 = S.x - 3 * u + i * 2 * u, x1 = P ? W * 0.36 - i * 3 * u : W * 0.3 - i * 3 * u;
      inkStroke(B.wobble(B.densify([[x0, y], [x1, y + u * 0.3]], 8), { amp: 0.4 * u, seed: i }), { w: (0.55 - i * 0.07) * u, p: B.prog(lt, 0.1 + i * 0.12, 0.6), d: 0.75, seed: 60 + i, dry: 0.45, hairs: 5 });
    }
    // rain cloud on the windward slope: pale pools, then rain hairlines
    const cx = px - hw * 0.45, cy = base - ph * (P ? 0.95 : 0.88);
    if (P) letters("the rain shadow", S.x + 2 * u, S.y + 10 * u, L.label * 1.25, B.smooth(0.3, 1.0, lt), { baseline: "top", italic: true, weight: 500, spacing: 0.16 });
    washPool(cx, cy, hw * 0.34, ph * 0.12, { d: 0.32, p: B.prog(lt, 0.5, 1.4), seed: 3, alpha: 0.6 });
    washPool(cx + hw * 0.2, cy + ph * 0.04, hw * 0.24, ph * 0.09, { d: 0.4, p: B.prog(lt, 0.8, 1.3), seed: 4, alpha: 0.55 });
    rainLines(cx - hw * 0.25, cx + hw * 0.3, cy + ph * 0.08, base - ph * 0.2, 26, 8, B.prog(lt, 1.6, 0.9));
    // wind arrow: one sweep from the sea up the windward slope
    const a0 = [S.x + (P ? 4 : 6) * u, base + 1.6 * u], a1 = [px - hw * 0.62, base - ph * 0.72]; // rises off the sea strokes
    brushArrow(B.quad(a0[0], a0[1], px - hw * 1.0, base - ph * 0.15, a1[0], a1[1], 30), B.prog(lt, 0.8, 0.9, "inOutSine"), (P ? 1.5 : 1.3) * u, 70);
    // labels written beside their subjects, never boxed
    const lab = L.label;
    letters("wet sea wind", P ? W * 0.38 : W * 0.3 + 2 * u, base + (P ? 2 : 3) * u, lab, B.smooth(1.4, 2.0, lt), { italic: true }); // at the strokes' end
    letters("rain falls here", P ? S.x + 1 * u : cx - hw * 0.62, cy - ph * (P ? 0.17 : 0.2), lab, B.smooth(1.0, 1.6, lt), { italic: true });
    letters("dry side", P ? S.r - 1 * u : px + hw * 0.62, P ? base - ph * 0.62 : base - ph * 0.42, lab, B.smooth(1.5, 2.0, lt), { italic: true, align: P ? "right" : "left" });
    vertical("風", P ? S.r - lab * 1.4 : S.x + 1 * u, P ? S.y + 2 * u : base - ph * 0.95, lab * 1.3, B.smooth(1.6, 2.4, lt));
  }

  function sceneNumber(L, W, H, t, lt) {
    const u = L.u, P = L.P, S = L.S;
    const [cx, cy, R] = numberAt(L, W, H);
    washPool(cx + R * 0.1, cy + R * 0.05, R * 1.05, R * 0.72, { d: 0.2, p: B.prog(lt, 0.05, 1.4), seed: 21, alpha: 0.45, wob: 0.2 });
    washPool(cx - R * 0.15, cy + R * 0.12, R * 0.6, R * 0.42, { d: 0.26, p: B.prog(lt, 0.35, 1.2), seed: 22, alpha: 0.35 });
    letters("10°C", cx, cy + u, (P ? 16 : 12.5) * u, B.smooth(0.3, 0.9, lt), { align: "center", weight: 700, spacing: 0.02, family: JP }); // lining figures, full black on a pale blot
    enso(cx, cy, R * 1.12, B.prog(lt, 0.55, 0.8, "inOutSine"), 30);
    const tx = P ? S.x + 2 * u : cx + R * 1.35, ty = P ? cy + R * 1.4 : cy - R * 0.25;
    const r = letters("cooler for every\nkilometre the air climbs", tx, ty, L.label * 1.1, B.smooth(0.8, 1.3, lt), { baseline: "top", italic: true, weight: 500 });
    letters(P ? "so its water vapour turns to cloud and rain" : "so its water vapour turns\nto cloud and rain", tx, (r ? r.bottom : ty) + L.label * 0.9, L.label, B.smooth(1.0, 1.5, lt), { baseline: "top", maxW: P ? S.w : W * 0.4, spacing: 0.04, weight: 500, color: inkTone(0.7) });
  }
  /** The key number's blot: centre and radius per aspect (also where its seal goes). */
  function numberAt(L, W, H) {
    return L.P ? [W * 0.46, H * 0.4, 30 * L.u] : [W * 0.4, H * 0.44, 21 * L.u];
  }

  /** The scroll of three small scenes, each painted as its turn comes, mist between them. */
  function stepBoxes(L, W, H) {
    const S = L.S, u = L.u;
    if (L.P) {
      const h = S.h / 3;
      return [0, 1, 2].map((i) => ({ x: S.x, y: S.y + i * h, w: S.w, h }));
    }
    const w = S.w / 3;
    return [0, 1, 2].map((i) => ({ x: S.x + i * w, y: S.y + 6 * u, w, h: S.h - 6 * u }));
  }
  function stepScene(L, box, i, lt, wt) {
    const u = L.u, P = L.P;
    // picture area and caption area inside the box
    const pic = P ? { x: box.x + box.w * 0.38, y: box.y + box.h * 0.1, w: box.w * 0.62, h: box.h * 0.78 } : { x: box.x - 2 * u, y: box.y + box.h * 0.06, w: box.w + 4 * u, h: box.h * 0.56 };
    const base = pic.y + pic.h, x0 = pic.x, x1 = pic.x + pic.w;
    const slopeUp = i < 2;
    const off = P ? 0.12 : 0.24, pk = slopeUp ? [x1 - pic.w * off, pic.h * 0.8, pic.w * 0.75] : [x0 + pic.w * off, pic.h * 0.8, pic.w * 0.75];
    // heights taper to nothing at both ends: the wash bleeds out
    const ridge = ridgePts(x0, x1, base, [pk], 100 + i).map(([x, y]) => [x, base - (base - y) * B.smooth(0, 0.2, Math.min(x - x0, x1 - x) / pic.w)]);
    mountainWash(ridge, base, { d: i === 2 ? 0.18 : 0.36, p: B.prog(wt, 0.0, 1.3), alpha: lt < 0 ? 0.35 : 0.35 + 0.4 * B.smooth(0, 0.5, lt), rim: lt < 0 ? 0.35 : 0.7 });
    // a scroll of numbered scenes: each number stands by its waiting wash; the words come in its turn
    const texts = [["1", "The sea wind\nmeets the slope"], ["2", "It climbs, cools\nand rains"], ["3", "Dry air sinks\ndown the far side"]][i];
    const tx = P ? box.x + 1 * u : box.x + box.w * 0.08, ty = P ? box.y + box.h * 0.3 : base + 5 * u;
    letters(texts[0], tx, ty, L.label * 1.6, B.smooth(0.2, 0.7, wt) * (lt < 0 ? 0.3 : 1), { baseline: "top", weight: 500, family: JP }); // pale like its wash
    if (lt < 0) return;
    const pi = ridge.reduce((bi, q, k) => (q[1] < ridge[bi][1] ? k : bi), 0);
    const seg = slopeUp ? ridge.slice(0, pi + 1) : ridge.slice(pi);
    // a point just above the slope, a fraction f along it: arrows ride it
    const on = (f, dy) => { const q = seg[Math.round((seg.length - 1) * f)]; return [q[0], q[1] - dy * pic.h]; };
    inkStroke(seg, { w: 1.3 * u, p: B.prog(lt, 0.15, 0.8, "inOutSine"), d: i === 2 ? 0.6 : 0.92, seed: 200 + i, dry: 0.6 });
    if (i === 0) {
      for (let k = 0; k < 3; k++) inkStroke([[x0, base - (0.5 - k * 1.3) * u], [x0 + pic.w * (0.4 - k * 0.08), base - (0.4 - k * 1.3) * u]], { w: 0.5 * u, p: B.prog(lt, 0.3 + k * 0.1, 0.5), d: 0.75, seed: 210 + k, dry: 0.4, hairs: 5 });
      brushArrow(B.quad(...on(0.06, 0.07), ...on(0.4, 0.16), ...on(0.8, 0.13), 20), B.prog(lt, 0.6, 0.7, "inOutSine"), 1.1 * u, 220);
    } else if (i === 1) {
      const cx = x0 + pic.w * 0.62, cy = pic.y + pic.h * 0.12;
      washPool(cx, cy, pic.w * 0.24, pic.h * 0.12, { d: 0.34, p: B.prog(lt, 0.4, 1.0), seed: 230, alpha: 0.65 });
      rainLines(cx - pic.w * 0.2, cx + pic.w * 0.15, cy + pic.h * 0.1, base - pic.h * 0.3, 16, 231, B.prog(lt, 0.35, 0.4));
    } else {
      brushArrow(B.quad(...on(0.06, 0.1), ...on(0.4, 0.17), ...on(0.86, 0.07), 20), B.prog(lt, 0.3, 0.5, "inOutSine"), 1.1 * u, 240, 0.75);
      inkDots(x0 + pic.w * 0.78, base - u, pic.w * 0.12, 5, 241, B.prog(lt, 1.0, 0.5), 0.5);
    }
    letters(texts[1], tx, ty + L.label * 2.7, L.label, B.smooth(0.3, 0.8, lt), { baseline: "top", italic: true, weight: 500, spacing: 0.08 });
  }
  function sceneSteps(L, W, H, t) {
    const boxes = stepBoxes(L, W, H), starts = STEP_AT;
    // the three pale washes are laid down first, then each small scene is inked in its turn
    boxes.forEach((bx, i) => stepScene(L, bx, i, t - starts[i], t - BEATS[3] - 0.1 - i * 0.3));
    // mist between the small scenes, the scroll's separators: both neighbours fade out into empty paper
    boxes.slice(0, 2).forEach((bx, i) => {
      if (L.P) return mist(bx.y + bx.h, L.u * 3.2, 0, W, 0.95, 300 + i);
      const x = bx.x + bx.w, hw = 11 * L.u;
      for (const g of [WL, KL]) {
        g.save();
        g.globalCompositeOperation = "destination-out";
        g.globalAlpha = A;
        g.fillStyle = B.linear(g, x - hw, 0, x + hw, 0, [[0, "rgba(0,0,0,0)"], [0.4, "rgba(0,0,0,1)"], [0.6, "rgba(0,0,0,1)"], [1, "rgba(0,0,0,0)"]]);
        g.fillRect(x - hw, 0, 2 * hw, bx.y + bx.h * 0.62 + 2.5 * L.u); // pictures only, the captions stay
        g.restore();
      }
    });
  }

  function sceneClose(L, W, H, t, lt) {
    const u = L.u, P = L.P, S = L.S, base = L.base, [px, ph, hw] = L.peak;
    bigMountain(L, W, lt + 3);
    const cx = px - hw * 0.45, cy = base - ph * 0.88;
    washPool(cx, cy, hw * 0.34, ph * 0.12, { d: 0.32, seed: 3, alpha: 0.6 });
    rainLines(cx - hw * 0.25, cx + hw * 0.3, cy + ph * 0.08, base - ph * 0.2, 22, 8, 1);
    const [tx, ty] = L.title;
    const r = letters("Wet on one side,\ndry on the other.", tx, ty, L.head * 0.95, B.smooth(0.5, 1.3, lt), { baseline: "top", spacing: 0.06, maxW: S.w * (P ? 0.9 : 0.55) });
    letters("the mountain takes the rain first", tx, (r ? r.bottom : ty) + L.label * 1.2, L.label, B.smooth(1.0, 1.6, lt), { italic: true, weight: 500, spacing: 0.16, baseline: "top", maxW: P ? S.w : S.w * 0.34 });
  }

  // --- frame
  const SCENES = [
    { a: 0, b: BEATS[1], fn: (L, W, H, t) => sceneTitle(L, W, H, t) },
    { a: BEATS[1], b: BEATS[2], fn: (L, W, H, t) => sceneDiagram(L, W, H, t, t - BEATS[1]) },
    { a: BEATS[2], b: BEATS[3], fn: (L, W, H, t) => sceneNumber(L, W, H, t, t - BEATS[2]) },
    { a: BEATS[3], b: BEATS[5], fn: (L, W, H, t) => sceneSteps(L, W, H, t) },
    { a: BEATS[5], b: DUR + 1, fn: (L, W, H, t) => sceneClose(L, W, H, t, t - BEATS[5]) },
  ];
  const FADE = 0.45;

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    U = L.u;
    WL = B.scratch("ink-wash", W, H);
    KL = B.scratch("ink-ink", W, H);
    // a very slow drift of the view, never a snap
    const z = 1 + 0.025 * B.wave(t, 28, 0.75) + 0.02;
    for (const g of [WL, KL]) g.setTransform(z, 0, 0, z, (W - W * z) / 2, (H - H * z) / 2 + B.bob(t, U * 0.3, 11));
    SCENES.forEach((s, i) => {
      const win = i === 0 ? 1 : B.smooth(s.a - FADE, s.a + FADE, t), wout = i === SCENES.length - 1 ? 1 : 1 - B.smooth(s.b - FADE, s.b + FADE, t);
      A = Math.min(win, wout);
      if (A > 0.004) s.fn(L, W, H, t);
    });
    A = 1;
    // grainy blotches inside the washes
    B.mottle(WL, W, H, { amount: 0.35, feature: 0.025, seed: 8, mode: "source-atop" });
    // print: paper, washes multiplied in, ink bleeding a hair, then sharp ink
    B.paper(ctx, W, H, { color: PAL.paper, seed: 20, mottle: 0.14, fibers: 0.25, specks: 0.12, tooth: 0.06, fiberColor: "#9c9076" });
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(WL.canvas, 0, 0);
    ctx.globalAlpha = 0.35;
    ctx.filter = `blur(${(0.28 * U).toFixed(1)}px)`;
    ctx.drawImage(KL.canvas, 0, 0);
    ctx.filter = "none";
    ctx.globalAlpha = 1;
    ctx.drawImage(KL.canvas, 0, 0);
    ctx.restore();
    // the seal: one small red stamp beside the title, again at the close
    const S = L.S, sz = (L.P ? 7 : 6.5) * U, [tx, ty] = L.title;
    const sealAt = L.P ? [S.r - sz * 0.9, ty + L.head * 2.9] : [tx + sz * 0.6, ty + L.head * 2.45 + L.label * 4.6];
    const tA = 1 - B.smooth(BEATS[1] - FADE, BEATS[1] + FADE, t);
    seal(ctx, sealAt[0], sealAt[1], sz, t - 1.5, tA);
    seal(ctx, sealAt[0], sealAt[1], sz, t - (BEATS[5] + 1.5), B.smooth(BEATS[5] + 1.4, BEATS[5] + 1.5, t));
    // the number beat gets its seal too, beside the key word
    const nA = Math.min(B.smooth(BEATS[2] + 1.3, BEATS[2] + 1.35, t), 1 - B.smooth(BEATS[3] - FADE, BEATS[3] + FADE, t));
    const [ncx, ncy, nR] = numberAt(L, W, H);
    seal(ctx, ncx + nR * 1.0, ncy + nR * 1.05, sz * 0.8, t - (BEATS[2] + 1.3), nA);
    // beat change: mist drifting across the whole frame
    let m = 0;
    for (const b of BEATS.slice(1)) if (b !== BEATS[4]) m = Math.max(m, 1 - Math.abs(t - b) / 0.7);
    if (m > 0) {
      const r = B.rng(5);
      ctx.save();
      for (let i = 0; i < 6; i++) {
        const cy = H * (0.1 + i * 0.16) + B.bob(t, U * 2, 6, i * 0.2), cx = W * B.fract(r() + t * 0.04 * (i % 2 ? 1 : -1));
        const rx = W * 0.8, ry = H * 0.14;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.scale(rx / ry, 1);
        ctx.globalAlpha = 0.7 * B.ease.inOutSine(B.clamp(m));
        ctx.fillStyle = B.radial(ctx, 0, 0, 0, ry, [[0, B.rgba(PAL.paper, 1)], [1, B.rgba(PAL.paper, 0)]]);
        ctx.fillRect(-ry, -ry, 2 * ry, 2 * ry);
        ctx.restore();
      }
      ctx.restore();
    }
    // finishing: long fibres and stains over everything, a faint warm age at the corners, fine tooth
    fibres(ctx, W, H);
    B.vignette(ctx, W, H, { color: "#a08a5c", amount: 0.22, inner: 0.55, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 8, mode: "soft-light" });
  }

  // --- sound: dry brush swishes, wooden knocks, a distant bell, a damp seal, an airy bed
  SOUND.define("ink-swish", (v, o) => {
    // dry brush: band noise whose pitch follows the brush's speed
    const d = o.dur ?? 0.8;
    v.noise({ filter: "bandpass", q: 0.9, f: 700, fpath: [[d * 0.3, 1900], [d * 0.7, 1400], [d, 600]], a: d * 0.25, hold: d * 0.45, len: d * 0.3, peak: 0.16 });
    v.grains({ span: d, count: d * 26, filter: "highpass", f: 3800, len: 0.01, peak: 0.05 });
  }, { verb: 0.25 });
  SOUND.define("ink-knock", (v) => {
    v.tone({ f: 420, f2: 390, glide: 0.1, a: 0.002, len: 0.16, peak: 0.28 });
    v.tone({ f: 980, a: 0.001, len: 0.05, peak: 0.08 });
    v.noise({ filter: "bandpass", f: 1200, q: 2, a: 0.001, len: 0.03, peak: 0.12 });
  }, { verb: 0.45 });

  function score(k) {
    k.bed("wind", 0, DUR, { gain: 0.22, fade: 2 });
    k.at(0.0, "bell", { note: "D4", gain: 0.25, verb: 0.8 });
    // title: far range, main ridge stroke, rock marks, seal
    k.at(0.5, "ink-swish", { dur: 1.1, gain: 0.9 }).at(1.4, "ink-swish", { dur: 0.6, gain: 0.5, pitch: 3 });
    k.at(1.5, "ink-knock", { gain: 0.5 }).at(1.5, "thud", { gain: 0.35, pitch: 4 });
    // diagram
    k.at(BEATS[1], "ink-knock").at(BEATS[1] + 0.1, "ink-swish", { dur: 0.9, gain: 0.5, pitch: -2 });
    k.at(BEATS[1] + 0.8, "ink-swish", { dur: 0.9, gain: 0.9, pitch: 2 });
    k.at(BEATS[1] + 0.9, "breath", { dur: 1.4, gain: 0.35 });
    k.bed("rain", BEATS[1] + 1.6, BEATS[2] + 0.4, { gain: 0.15, fade: 0.6 });
    // key number: blot blooms, the number soaks in, the enso, the seal
    k.at(BEATS[2], "ink-knock", { pitch: -3 }).at(BEATS[2] + 0.15, "swell", { dur: 1.4, gain: 0.25 });
    k.at(BEATS[2] + 0.3, "bell", { note: "A4", gain: 0.25, verb: 0.9 });
    k.at(BEATS[2] + 0.55, "ink-swish", { dur: 0.8, gain: 1.0, pitch: 1 });
    k.at(BEATS[2] + 1.3, "thud", { gain: 0.35, pitch: 4 });
    // three small scenes
    STEP_AT.forEach((at, i) => {
      k.at(at, "ink-knock", { pitch: [0, 2, -2][i], pan: [-0.3, 0, 0.3][i] });
      k.at(at + 0.15, "ink-swish", { dur: 0.8, gain: 0.7, pitch: i });
      k.at(at + 0.55, "ink-swish", { dur: 0.6, gain: 0.5, pitch: 3 - i });
    });
    // close
    k.at(BEATS[5], "bell", { note: "D4", gain: 0.3, verb: 0.9 });
    k.at(BEATS[5] + 0.3, "ink-swish", { dur: 1.0, gain: 0.7, pitch: -1 });
    k.at(BEATS[5] + 1.5, "thud", { gain: 0.4, pitch: 4 }).at(BEATS[5] + 1.5, "ink-knock", { gain: 0.4 });
  }

  Player.register({
    id: "ink-wash",
    name: "Ink Wash",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500;1,600&family=Noto+Serif+JP:wght@500;700&display=swap",
      faces: ['600 20px "Cormorant Garamond"', '500 20px "Cormorant Garamond"', 'italic 500 20px "Cormorant Garamond"', 'italic 600 20px "Cormorant Garamond"', '500 20px "Noto Serif JP"', '700 20px "Noto Serif JP"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.75, 4.55, 6.75, 9.4, 11.05, 13.6], // clear of the beat-change mist
    draw,
    score,
  });
})();
