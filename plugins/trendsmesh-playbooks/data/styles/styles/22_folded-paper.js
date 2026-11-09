/* 22 Folded Paper - reference animation.
 * Topic (setting, replace it): "How far does an Arctic tern fly?" - pole to pole and back, about 70,000 km a year.
 * Rendering (keep it): every model is a set of flat paper facets in 3D (a tiny renderer: rotate, light, sort, fill).
 * Each facet takes its tone from how it faces a light at the upper left (Lambert), shows the sheet's other colour
 * when it turns its back, and gets a faint dark crease line on its edges and a hairline highlight on the lit edge.
 * Folds are real: a flap turns about its crease line (Rodrigues rotation), so it squashes in perspective as it goes.
 * Models sit on a warm light-grey backdrop lit from the top left, with soft contact shadows that widen as they lift;
 * a very light paper grain lies on every facet. Labels are flat paper tabs with a dog-ear, joined by dotted fold
 * lines; the number is printed on a white card that folds out from behind; steps are numbered origami squares.
 * Motion: deliberate folds with a small settle, slow few-degree turns; between beats a model presses flat, folds in
 * half over a crease and tucks away, and the next one unfolds the same way.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { back: "#e9e6e0", shadow: "#b8b3aa", coral: "#ee5d4b", teal: "#1f9aa3", mustard: "#f0b429", navy: "#1f2a44", white: "#fbfaf6" };
  const SANS = "Space Grotesk", MONO = "Space Mono";
  const DUR = 13;
  const BEATS = [0, 3.0, 5.2, 7.4, 9.4, 10.9];

  let M = null, U = 1; // the model layer (paper facets; grain is laid over it), frame unit

  // ---- folded-paper helpers (reuse these)
  const LIGHT = (() => {
    const v = [-0.55, 0.62, 0.56], l = Math.hypot(...v);
    return v.map((c) => c / l);
  })(); // from the upper left, a little toward the viewer (model space: y up, z toward the viewer)
  /** Rotate a model point: spin (z), yaw (y), pitch (x), roll (z). */
  function rot([x, y, z], yaw, pitch, roll, spin = 0) {
    let c = Math.cos(spin), s = Math.sin(spin);
    [x, y] = [x * c - y * s, x * s + y * c];
    c = Math.cos(yaw);
    s = Math.sin(yaw);
    [x, z] = [x * c + z * s, -x * s + z * c];
    c = Math.cos(pitch);
    s = Math.sin(pitch);
    [y, z] = [y * c - z * s, y * s + z * c];
    c = Math.cos(roll);
    s = Math.sin(roll);
    [x, y] = [x * c - y * s, x * s + y * c];
    return [x, y, z];
  }
  /** Rotate p about the line through a along unit k by th (Rodrigues): a flap folding. */
  function turnAbout(p, a, k, th) {
    const v = [p[0] - a[0], p[1] - a[1], p[2] - a[2]], c = Math.cos(th), s = Math.sin(th);
    const d = k[0] * v[0] + k[1] * v[1] + k[2] * v[2];
    const cr = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]];
    return [0, 1, 2].map((i) => a[i] + v[i] * c + cr[i] * s + k[i] * d * (1 - c));
  }
  const unit = (a, b) => {
    const v = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], l = Math.hypot(...v) || 1;
    return v.map((c) => c / l);
  };
  /** A model's hand-off, e: 0 = full form, 1 = gone: presses flat, folds in half, tucks away. */
  const stages = (e) => ({ flat: B.smooth(0, 0.45, e), fold: B.ease.inOutCubic(B.smooth(0.3, 0.88, e)), gone: B.smooth(0.84, 1, e) });
  /** e for a model shown from a to b: unfolds in over din, folds out over dout. */
  const handoff = (t, a, b, din = 0.5, dout = 0.28) => 0.8 * Math.max(1 - B.smooth(a, a + din, t), B.smooth(b - dout, b, t));
  const shown = (e) => 1 - B.smooth(0.5, 0.78, e); // labels leave as the model folds
  /**
   * Draw paper facets. faces: [{ v: [p, p, p], c: front colour, b: back colour }] in model units.
   * o: { x, y (screen centre), s (px per unit), yaw, pitch, roll, spin, e (hand-off, see stages), alpha }
   * Each facet is lit by LIGHT (front or back, whichever faces the viewer), sorted far to near, projected with a
   * slight perspective, filled with a seam stroke of its own colour, then given a faint crease line and a hairline
   * highlight on edges facing the light. Returns the screen bounding box (for the contact shadow).
   */
  function paperModel(ctx, faces, o) {
    const s = o.s, st = stages(o.e ?? 0), dz = 1 - st.flat, th = Math.PI * st.fold, fc = Math.cos(th), fs = Math.sin(th);
    const out = [];
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const f of faces) {
      const P = f.v.map((p) => {
        let [x, y, z] = rot(p, o.yaw ?? 0, o.pitch ?? 0, o.roll ?? 0, o.spin ?? 0);
        z *= dz; // pressed flat
        if (th > 0 && x > 0) [x, z] = [x * fc - z * fs, x * fs + z * fc]; // the right half swings over the crease
        return [x, y, z];
      });
      const e1 = [P[1][0] - P[0][0], P[1][1] - P[0][1], P[1][2] - P[0][2]], e2 = [P[2][0] - P[0][0], P[2][1] - P[0][1], P[2][2] - P[0][2]];
      let n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
      const nl = Math.hypot(...n) || 1;
      n = n.map((c) => c / nl);
      const front = n[2] >= 0;
      if (!front) n = n.map((c) => -c);
      const lam = Math.max(0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]);
      const col = front ? f.c : f.b ?? f.c;
      const tone = B.shade(col, -0.34 + 0.52 * lam + (f.lift ?? 0));
      const pts = P.map((p) => {
        const k = 1 / (1 - p[2] * 0.09); // slight perspective: nearer facets a little larger
        return [o.x + p[0] * s * k, o.y - p[1] * s * k];
      });
      for (const q of pts) {
        x0 = Math.min(x0, q[0]);
        x1 = Math.max(x1, q[0]);
        y0 = Math.min(y0, q[1]);
        y1 = Math.max(y1, q[1]);
      }
      out.push({ pts, z: (P[0][2] + P[1][2] + P[2][2]) / 3 + (f.zb ?? 0), tone, lam });
    }
    out.sort((a, b) => a.z - b.z);
    ctx.save();
    ctx.globalAlpha *= (o.alpha ?? 1) * (1 - st.gone);
    ctx.lineJoin = "round";
    for (const f of out) {
      ctx.beginPath();
      B.poly(ctx, f.pts, true);
      ctx.fillStyle = f.tone;
      ctx.fill();
      ctx.strokeStyle = f.tone; // close anti-alias seams between facets
      ctx.lineWidth = 0.08 * U;
      ctx.stroke();
      const cx = (f.pts[0][0] + f.pts[1][0] + f.pts[2][0]) / 3, cy = (f.pts[0][1] + f.pts[1][1] + f.pts[2][1]) / 3;
      for (let i = 0; i < 3; i++) {
        const a = f.pts[i], b = f.pts[(i + 1) % 3];
        let nx = b[1] - a[1], ny = a[0] - b[0];
        const l = Math.hypot(nx, ny) || 1;
        nx /= l;
        ny /= l;
        if (nx * ((a[0] + b[0]) / 2 - cx) + ny * ((a[1] + b[1]) / 2 - cy) < 0) [nx, ny] = [-nx, -ny];
        const lit = nx * -0.6 + ny * -0.8 > 0.45;
        ctx.strokeStyle = lit ? "rgba(255,255,255,0.55)" : "rgba(40,30,20,0.16)";
        ctx.lineWidth = (lit ? 0.12 : 0.16) * U;
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
      }
    }
    ctx.restore();
    return { x0, x1, y0, y1, a: 1 - st.gone };
  }
  /** Soft contact shadow; lift (0..1) pools it wider and fainter. */
  function shadowUnder(ctx, box, ground, lift) {
    if (!box || !isFinite(box.x0) || box.a <= 0) return;
    const cx = (box.x0 + box.x1) / 2 + lift * 3 * U, w = (box.x1 - box.x0) * (0.5 + 0.3 * lift);
    const r = B.radial(ctx, 0, 0, 0, 1, [[0, B.rgba(PAL.shadow, 0.75 - 0.35 * lift)], [0.6, B.rgba(PAL.shadow, 0.3 - 0.12 * lift)], [1, B.rgba(PAL.shadow, 0)]]);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.globalAlpha = box.a;
    ctx.translate(cx, ground);
    ctx.scale(w, w * 0.16 * (1 + lift));
    ctx.fillStyle = r;
    ctx.beginPath();
    B.circle(ctx, 0, 0, 1);
    ctx.fill();
    ctx.restore();
  }
  /**
   * A square sheet with its four corners folding to the centre (a blintz fold). folds: [p0..p3] 0..1 each corner.
   * Front colour c, back colour b: a folded corner shows the back of the paper.
   */
  function blintzSheet(folds, c, b) {
    const C = [[-1, 1, 0], [1, 1, 0], [1, -1, 0], [-1, -1, 0]], Mi = [[0, 1, 0], [1, 0, 0], [0, -1, 0], [-1, 0, 0]];
    const faces = [{ v: [Mi[0], Mi[2], Mi[1]], c, b }, { v: [Mi[0], Mi[3], Mi[2]], c, b }]; // wound to face the viewer
    C.forEach((corner, i) => {
      const a = Mi[(i + 3) % 4], e = Mi[i], k = unit(a, e), p = folds[i];
      const settle = p >= 1 ? 1 : B.ease.inOutCubic(p) + 0.04 * Math.sin(Math.PI * B.smooth(0.85, 1, p)); // small settle
      let tip = turnAbout(corner, a, k, Math.PI * B.clamp(settle, 0, 1.03));
      tip = [tip[0], tip[1], tip[2] + 0.02 * p];
      faces.push({ v: [a, e, tip], c, b, zb: 0.02 * (i + 1) * p });
    });
    return faces;
  }
  /** The tern, in model units (x toward the head, y up, z toward the viewer); flap raises the long swept wings. */
  function ternFaces(flap) {
    const W = PAL.white, G = "#e4e1da", Gw = "#c7ccd3", Dk = "#4a5468", N = PAL.navy, R = PAL.coral;
    const nose = [1.0, 0.05, 0], tail = [-1.0, 0.05, 0], top = [0.0, 0.26, 0], bot = [0.15, -0.22, 0], zf = [0.05, 0.02, 0.26], zb = [0.05, 0.02, -0.26];
    const head = [1.15, 0.16, 0], beak = [1.75, 0.02, 0], cap = [0.75, 0.3, 0];
    // each wing: a broad inner panel and a narrow hand swept back to a sharp tip (a tern's long pointed wing)
    const ky = 0.14 + flap * 0.3, ty = 0.05 + flap * 0.6;
    const wing = (sz) => {
      const a = [0.3, 0.15, 0.1 * sz], b = [-0.16, 0.16, 0.1 * sz], c = [-0.5, ky * 0.9, 0.8 * sz], d = [-0.02, ky, 0.86 * sz], tip = [-1.45, ty, 1.75 * sz];
      const q = [-0.62, ky * 0.92 + (ty - ky) * 0.3, 1.1 * sz]; // the dark outer primaries, as on a real tern
      return [{ v: [a, b, c], c: Gw, b: G, lift: 0.08 }, { v: [a, c, d], c: Gw, b: G, lift: 0.08 }, { v: [d, c, q], c: Gw, b: G, lift: 0.1 }, { v: [d, q, tip], c: Dk, b: Dk, lift: 0.1 }, { v: [q, c, tip], c: Gw, b: G, lift: 0.1 }];
    };
    return [
      ...wing(-1),
      { v: [nose, top, zb], c: G, b: G }, { v: [tail, top, zb], c: G, b: G }, { v: [nose, bot, zb], c: G, b: G }, { v: [tail, bot, zb], c: G, b: G },
      { v: [nose, top, zf], c: W, b: W }, { v: [tail, top, zf], c: W, b: W }, { v: [nose, bot, zf], c: W, b: W }, { v: [tail, bot, zf], c: W, b: W },
      { v: [tail, [-1.75, 0.18, 0.18], [-1.25, 0.05, 0.05]], c: W, b: G }, { v: [tail, [-1.7, -0.02, -0.2], [-1.25, 0.04, -0.03]], c: G, b: G },
      { v: [nose, cap, [0.8, 0.1, 0.16]], c: N, b: N }, { v: [nose, head, cap], c: N, b: N, zb: 0.05 },
      { v: [head, beak, [1.12, 0.02, 0.06]], c: R, b: R, zb: 0.1 }, { v: [head, beak, [1.1, 0.0, -0.06]], c: B.shade(R, -0.2), b: R },
      ...wing(1),
    ];
  }
  // A low-poly Earth: teal sea, mustard land from rough continent outlines (lon lat pairs), white ice at the poles,
  // a navy axis rod; drawn with roll: GT (the 23° tilt), the Atlantic facing the viewer.
  const GT = 0.41, LAND = ["-165 62 -160 70 -120 72 -95 72 -80 65 -62 58 -55 50 -66 44 -76 38 -80 31 -80 25 -90 30 -97 26 -97 18 -88 15 -83 9 -78 8 -86 13 -96 16 -106 22 -118 34 -124 41 -125 49 -133 56 -147 61",
    "-55 60 -42 60 -20 70 -18 80 -40 84 -62 82 -72 77", "-80 10 -62 11 -50 0 -35 -6 -40 -22 -48 -28 -58 -38 -65 -55 -72 -50 -72 -30 -71 -18 -80 -5",
    "-17 15 -17 21 -10 30 -5 36 10 37 32 31 43 12 51 12 40 -15 35 -25 20 -35 12 -15 9 0 -8 5 -15 10",
    "-10 36 -9 43 5 52 10 57 5 62 20 70 60 70 110 77 180 68 160 55 135 43 122 30 106 10 98 8 90 22 80 10 66 25 57 25 50 30 43 13 35 30 22 40 10 44 3 42",
    "114 -22 130 -12 142 -11 153 -28 150 -37 140 -38 115 -34"].map((q) => q.split(" ").map(Number));
  const onLand = (lo, la) => LAND.some((c) => {
    let inside = false;
    for (let i = 0, j = c.length - 2; i < c.length; j = i, i += 2)
      if (c[i + 1] > la !== c[j + 1] > la && lo < ((c[j] - c[i]) * (la - c[i + 1])) / (c[j + 1] - c[i + 1]) + c[i]) inside = !inside;
    return inside;
  });
  function globeFaces(lit) {
    const out = [], NL = 16, NM = 32, ax = 0.035;
    const P = (i, j) => {
      const th = (i / NL) * Math.PI, ph = (j / NM) * B.TAU;
      return [Math.sin(th) * Math.cos(ph), Math.cos(th), Math.sin(th) * Math.sin(ph)];
    };
    for (let i = 0; i < NL; i++)
      for (let j = 0; j < NM; j++) {
        const a = P(i, j), b = P(i, j + 1), c = P(i + 1, j + 1), d = P(i + 1, j);
        const lat = 90 - ((i + 0.5) / NL) * 180, lon = 94 - ((j + 0.5) / NM) * 360, lo = lon < -180 ? lon + 360 : lon;
        const col = Math.abs(lat) > 70 ? PAL.white : onLand(lo, lat) ? PAL.mustard : PAL.teal;
        const lf = lat > 70 ? lit.north ?? 0 : lat < -70 ? lit.south ?? 0 : 0;
        if (i > 0) out.push({ v: [a, d, c], c: col, b: col, lift: lf });
        if (i < NL - 1) out.push({ v: [a, c, b], c: col, b: col, lift: lf });
      }
    // the axis: two crossed thin strips, hidden inside the ball, poking out at both poles
    for (const [x, z] of [[ax, 0], [0, ax]]) {
      const n = [-x, 1.32, -z], s2 = [x, 1.32, z], m1 = [x, -1.32, z], m2 = [-x, -1.32, -z];
      out.push({ v: [n, s2, m1], c: PAL.navy, b: PAL.navy }, { v: [n, m1, m2], c: PAL.navy, b: PAL.navy });
    }
    return out;
  }
  /** A faceted sun: a fan of triangles round the centre, every other one a shade deeper. */
  function sunFaces() {
    const out = [], n = 10;
    for (let i = 0; i < n; i++) {
      const a0 = (i / n) * B.TAU, a1 = ((i + 1) / n) * B.TAU;
      out.push({ v: [[0, 0, 0.25], [Math.cos(a0), Math.sin(a0), 0], [Math.cos(a1), Math.sin(a1), 0]], c: PAL.mustard, b: PAL.mustard });
    }
    return out;
  }
  /** Flat paper tab, dog-eared, with sans lettering; unfolds from its edge by p. */
  function tab(ctx, x, y, text, size, p, o = {}) {
    if (p <= 0.01) return null;
    ctx.save();
    ctx.font = B.font(size, o.mono ? MONO : SANS, o.mono ? 700 : 600);
    const w = ctx.measureText(text).width + size * 1.5, h = size * 2.0, k = B.ease.outCubic(B.clamp(p));
    const x0 = o.align === "right" ? x - w : o.align === "center" ? x - w / 2 : x;
    ctx.translate(x0, y);
    ctx.scale(k, 1);
    ctx.globalAlpha *= B.smooth(0, 0.3, p); // a tab folding away fades with its text, never a bare stub
    ctx.fillStyle = B.rgba(PAL.shadow, 0.55);
    ctx.fillRect(0.5 * U, -h / 2 + 0.7 * U, w, h);
    const fill = o.fill || PAL.white, ear = h * 0.38;
    ctx.fillStyle = B.shade(fill, -0.03 + 0.06 * k);
    ctx.beginPath();
    B.poly(ctx, [[0, -h / 2], [w - ear, -h / 2], [w, -h / 2 + ear], [w, h / 2], [0, h / 2]], true);
    ctx.fill();
    ctx.fillStyle = B.shade(fill, -0.16); // the dog-ear folded over shows its shaded back
    ctx.beginPath();
    B.poly(ctx, [[w - ear, -h / 2], [w - ear, -h / 2 + ear], [w, -h / 2 + ear]], true);
    ctx.fill();
    ctx.globalAlpha *= B.smooth(0.15, 0.5, p);
    ctx.fillStyle = o.ink || PAL.navy;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(text, size * 0.75, size * 0.05);
    ctx.restore();
    return { x: x0, y, w, h };
  }
  /** Dotted fold line from a to b, drawn on by p, with a round end at the target. */
  function foldLine(ctx, a, b, p, color = PAL.navy) {
    if (p <= 0.01) return;
    const e = [B.lerp(a[0], b[0], p), B.lerp(a[1], b[1], p)];
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.32 * U;
    ctx.setLineDash([0.9 * U, 0.8 * U]);
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(e[0], e[1]);
    ctx.stroke();
    ctx.setLineDash([]);
    if (p > 0.95) {
      ctx.fillStyle = color;
      ctx.beginPath();
      B.circle(ctx, b[0], b[1], 0.6 * U);
      ctx.fill();
    }
    ctx.restore();
  }
  /** Dashed fold-line path with a small open arrow head. */
  function foldArrow(ctx, pts, p, color = PAL.navy, w = 0.4) {
    if (p <= 0.01) return;
    B.arrow(ctx, pts, { p, width: w * U, color, dash: [1.4 * U, 0.9 * U], head: 2.6 * U, headStyle: "open" });
  }
  /** Flat paper arrow with a crease down its middle: the upper half lit, the lower half in shade. */
  function paperArrow(ctx, x, y, len, wd, ang, p, col) {
    if (p <= 0.01) return;
    const L = len * B.ease.outCubic(p), hl = Math.min(wd * 1.3, L * 0.5);
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(ang);
    ctx.fillStyle = B.rgba(PAL.shadow, 0.5);
    ctx.beginPath();
    B.poly(ctx, [[0, -wd / 2 + U], [L - hl, -wd / 2 + U], [L - hl, -wd + U], [L, U], [L - hl, wd + U], [L - hl, wd / 2 + U], [0, wd / 2 + U]], true);
    ctx.fill();
    ctx.fillStyle = B.shade(col, 0.12);
    ctx.beginPath();
    B.poly(ctx, [[0, -wd / 2], [L - hl, -wd / 2], [L - hl, -wd], [L, 0], [0, 0]], true);
    ctx.fill();
    ctx.fillStyle = B.shade(col, -0.18);
    ctx.beginPath();
    B.poly(ctx, [[0, 0], [L, 0], [L - hl, wd], [L - hl, wd / 2], [0, wd / 2]], true);
    ctx.fill();
    ctx.restore();
  }
  /** Lettering on the backdrop: clean geometric sans in ink navy. */
  function words(ctx, str, x, y, size, a, o = {}) {
    if (a <= 0.01) return null;
    return B.text(ctx, str, x, y, { size, family: o.mono ? MONO : SANS, weight: o.weight ?? 700, color: o.color || PAL.navy, align: o.align || "left", baseline: o.baseline || "top", maxW: o.maxW, lineH: o.lineH ?? 1.05, letterSpacing: o.ls ?? -0.01, alpha: a });
  }
  // ---- layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    return {
      F, u, P, S,
      hero: P ? [W * 0.5, H * 0.5] : [W * 0.68, H * 0.56],
      heroS: P ? 27 * u : 21 * u,
      globe: P ? [W * 0.43, H * 0.47, 26 * u] : [W * 0.56, H * 0.52, 24 * u],
      title: P ? [S.x + 1 * u, S.y + 2 * u] : [S.x + 1 * u, S.y + 6 * u],
      head: P ? 9 * u : 7.4 * u,
      lab: 3.95 * u, // every label at least 3.8 % of the short side
    };
  }
  const tern = (t, period) => ternFaces(0.5 + 0.5 * B.wave(t, period));

  // ---- the beats
  function sceneTitle(ctx, L, t) {
    let [hx, hy] = L.hero;
    const s = L.heroS, P = L.P;
    if (t < 1.85) {
      // a flat square sheet lands, its four corners fold to the centre one after another, then it folds away
      const folds = [0, 1, 2, 3].map((i) => B.prog(t, 0.3 + i * 0.22, 0.38));
      const box = paperModel(M, blintzSheet(folds, PAL.coral, PAL.white), { x: hx, y: hy, s: s * (P ? 1.15 : 0.95), spin: Math.PI / 4 + 0.05 * B.wave(t, 6), yaw: 0.06, pitch: L.P ? -0.62 : -0.85, e: Math.max(1 - B.smooth(0, 0.3, t), 0.8 * B.smooth(1.45, 1.85, t)) });
      shadowUnder(ctx, box, box.y1 + s * 0.08, 0.05);
    } else {
      // ... and unfolds again as the tern
      const e = handoff(t, 1.85, BEATS[1], 0.45);
      if (P) hy += L.F.H * 0.06; // the bird sits a little lower than the sheet, over its flight line
      const box = paperModel(M, tern(t, 1.3), { x: hx, y: hy, s: s * 0.8, yaw: 0.25 + 0.08 * B.wave(t, 6), pitch: -0.5, roll: 0.08, e });
      shadowUnder(ctx, box, hy + s * 0.9, 0.25);
      // its flight so far: a dashed fold line rising from the lower left
      const fp = B.prog(t, 2.0, 0.6, "inOutSine") * shown(e);
      foldArrow(ctx, B.quad(L.S.x + 3 * L.u, P ? L.F.H * 0.93 : L.S.b - 2 * L.u, hx - s * 0.9, hy + s * 0.75, hx - s * 1.3, hy + s * 0.05), fp, PAL.coral, 0.45);
    }
    const [tx, ty] = L.title, gone = 1 - B.smooth(BEATS[1] - 0.2, BEATS[1] - 0.02, t);
    const r = words(ctx, "How far does\nan Arctic tern fly?", tx, ty, L.head, B.smooth(0.2, 0.7, t) * gone, { maxW: P ? L.S.w : L.S.w * 0.48 });
    // the tab: under the title in landscape, at the foot in portrait
    if (r) tab(ctx, P ? L.S.r : tx, P ? L.S.b - L.lab * 1.6 : r.bottom + L.lab * 2.2, "a migration in folds", L.lab, B.prog(t, 0.9, 0.5) * gone, { fill: PAL.mustard, mono: true, align: P ? "right" : "left" });
  }

  function sceneDiagram(ctx, L, t, lt) {
    const u = L.u, P = L.P, S = L.S, [gx, gy, gr] = L.globe;
    const e = handoff(t, BEATS[1], BEATS[2]), on = shown(e);
    const lit = { north: 0.25 * B.smooth(0.5, 0.8, lt), south: 0.25 * B.smooth(1.0, 1.3, lt) };
    const box = paperModel(M, globeFaces(lit), { x: gx, y: gy, s: gr, yaw: 0.3 + lt * 0.2, pitch: 0.16, roll: GT, e });
    shadowUnder(ctx, box, gy + gr * 1.18, 0.15);
    // the route: a dashed fold line from pole to pole round the globe's lit side, with the bird riding it
    const route = B.arcPts(gx, gy, gr * 1.24, -Math.PI * 0.44 - GT, Math.PI * 0.44 - GT, 40);
    const rp = B.prog(lt, 0.5, 0.9, "inOutSine");
    foldArrow(ctx, route, rp * on, PAL.coral, 0.5);
    if (rp > 0.02) {
      // the bird flies just outside the route, clear of the globe and its shadow
      const q = B.pointAt(route, Math.min(0.8, rp)), d = Math.hypot(q[0] - gx, q[1] - gy), o = 1 + (0.3 * gr + (P ? 4 : 6) * u) / d;
      paperModel(M, tern(t, 0.8), { x: gx + (q[0] - gx) * o, y: gy + (q[1] - gy) * o, s: (P ? 7 : 5.5) * u, yaw: 0.3, pitch: -0.5, roll: -0.3, e });
    }
    // tabs joined to their subjects by dotted fold lines
    const pole = (k) => [gx + k * Math.sin(GT) * gr * 1.2, gy + k * Math.cos(GT) * gr * 1.2], north = pole(-1), south = pole(1);
    const t1 = P ? [S.x, gy - gr * 1.4] : [S.x + 2 * u, gy - gr * 0.95], t2 = P ? [S.x, gy + gr * 1.4] : [S.x + 2 * u, gy + gr * 1.15];
    const a1 = tab(ctx, t1[0], t1[1], "Arctic", L.lab, B.prog(lt, 0.35, 0.4) * on);
    if (a1) foldLine(M, [a1.x + a1.w, a1.y], north, B.prog(lt, 0.5, 0.35) * on);
    const a2 = tab(ctx, t2[0], t2[1], "Antarctic", L.lab, B.prog(lt, 0.8, 0.4) * on);
    if (a2) foldLine(M, [a2.x + a2.w, a2.y], south, B.prog(lt, 0.95, 0.35) * on);
    const rq = B.pointAt(route, 0.5);
    tab(ctx, P ? S.r : rq[0] + 4 * u, P ? gy + gr * 1.7 : rq[1], "Arctic tern route", L.lab, B.prog(lt, 1.1, 0.4) * on, { fill: PAL.coral, ink: PAL.white, align: P ? "right" : "left" });
  }

  function sceneNumber(ctx, L, t, lt) {
    const u = L.u, P = L.P, S = L.S, W = L.F.W, H = L.F.H;
    const e = handoff(t, BEATS[2], BEATS[3]), on = shown(e);
    const lift = B.smooth(0.3, 0.8, lt);
    const bx = P ? W * 0.5 : W * 0.25, by = (P ? H * 0.385 : H * 0.5) - lift * 3 * u, bs = P ? 17 * u : 14 * u;
    // a white card folds out from behind the bird, the number printed inside
    const open = B.prog(lt, 0.45, 0.7, "inOutCubic"), settle = open >= 1 ? 1 : open + 0.03 * Math.sin(Math.PI * B.smooth(0.8, 1, open));
    const ang = Math.PI * 0.5 * (1 - settle) + B.smooth(BEATS[3] - 0.3, BEATS[3] - 0.04, t) * Math.PI * 0.5; // swings down from edge-on, and back
    const cw = P ? S.w * 0.92 : S.w * 0.5, ch = P ? 33 * u : 30 * u;
    const hinge = P ? [W / 2 - cw / 2, by + bs * 0.6] : [bx + bs * 2.0, H * 0.5 - ch / 2];
    const cs = Math.cos(ang);
    if (Math.abs(cs) > 0.02) {
      ctx.save();
      if (P) ctx.transform(1, 0, 0, cs, 0, hinge[1] * (1 - cs));
      else ctx.transform(cs, 0, 0, 1, hinge[0] * (1 - cs), 0);
      ctx.fillStyle = B.rgba(PAL.shadow, 0.45);
      ctx.fillRect(hinge[0] + 1.2 * u, hinge[1] + 1.4 * u, cw, ch);
      ctx.fillStyle = cs > 0 ? B.shade(PAL.white, -0.06 + 0.06 * cs) : B.shade(PAL.mustard, -0.25 + 0.2 * -cs);
      ctx.fillRect(hinge[0], hinge[1], cw, ch);
      if (cs > 0) {
        const k = B.prog(lt, 0.6, 0.7);
        const cx = hinge[0] + cw / 2, cy = hinge[1] + ch * 0.42;
        words(ctx, B.counter(k, 70000) + " km", cx, cy, (P ? 12 : 9) * u, B.smooth(0.2, 0.45, open), { align: "center", baseline: "middle", mono: true, color: PAL.coral, maxW: cw * 0.9 });
        words(ctx, "flown every year", cx, hinge[1] + ch * 0.78, L.lab * 1.2, B.smooth(0.6, 1, open), { align: "center", baseline: "middle", weight: 600 });
      }
      ctx.restore();
    }
    // emphasis: the bird lifts off the table, its shadow pooling wider and fainter
    const box = paperModel(M, tern(t, 1.1), { x: bx, y: by, s: bs, yaw: 0.3 + 0.08 * B.wave(t, 5), pitch: -0.5, roll: 0.06, e });
    shadowUnder(ctx, box, by + bs * 0.75 + lift * 3 * u, lift);
    // a second fact on a tab under the card: 70,000 / 40,075 km is about 1.75 times round the Earth
    tab(ctx, P ? W / 2 : hinge[0] + cw / 2, hinge[1] + ch + 6 * u, "nearly twice round the Earth", L.lab, B.prog(lt, 1.0, 0.4) * on, { align: "center", fill: PAL.teal, ink: PAL.white, mono: true });
    {
      // the journey itself, round a small globe: down one side and back up the other
      const [gx, gy, gr] = P ? [W / 2, H * 0.745, 7 * u] : [W * 0.25, H * 0.8, 8 * u];
      shadowUnder(ctx, paperModel(M, globeFaces({ north: 0.25, south: 0.25 }), { x: gx, y: gy, s: gr, yaw: 0.3 + lt * 0.15, pitch: 0.16, roll: GT, e }), gy + gr * 1.2, 0.1);
      const rp = B.prog(lt, 0.9, 1.0, "inOutSine") * on;
      foldArrow(ctx, B.arcPts(gx, gy, gr * 1.3, -Math.PI * 0.44 - GT, Math.PI * 0.44 - GT, 30), B.clamp(rp * 2), PAL.coral, 0.45);
      foldArrow(ctx, B.arcPts(gx, gy, gr * 1.3, Math.PI * 0.56 - GT, Math.PI * 1.44 - GT, 30), B.clamp(rp * 2 - 1), PAL.coral, 0.45);
    }
    words(ctx, "pole to pole and back", S.x + u, P ? S.y + 1 * u : S.y + 2 * u, L.lab * 1.2, B.smooth(0.3, 0.7, lt) * on, { mono: true, weight: 700, color: PAL.teal });
  }

  /** Origami-diagram squares: three numbered slots, then each square unfolds into its slot. */
  function sceneSteps(ctx, L, t) {
    const u = L.u, P = L.P, S = L.S;
    const bt = t - BEATS[3], off = B.smooth(BEATS[5] - 0.35, BEATS[5] - 0.02, t), on = 1 - off;
    const steps = [["Arctic summer ends", 0.15], ["Fly south over the oceans", 1.1], ["Arrive for a second summer", 2.05]];
    const side = P ? 31 * u : 48 * u, cap = L.lab * (P ? 1.15 : 1.3), y0L = S.y + 2 * u;
    // landscape: the year's route along the foot of the row
    if (!P) foldArrow(ctx, [[S.x + S.w * 0.08, S.b - 6 * u], [S.cx, S.b - 2 * u], [S.r - S.w * 0.08, S.b - 6 * u]], B.prog(bt, 0.3, 2.3) * on, PAL.coral, 0.5);
    steps.forEach(([txt, at], i) => {
      const lt = bt - at;
      const x = P ? S.x + 1 * u : S.x + i * (S.w / 3) + (S.w / 3 - side) / 2, y = P ? S.y + 4 * u + i * (side + 8 * u) : y0L;
      // the empty slot: a dashed fold outline and the step number, marked as the beat opens
      const mark = B.prog(bt, i * 0.05, 0.1) * on;
      if (mark > 0.01) {
        ctx.save();
        ctx.globalAlpha *= mark;
        ctx.strokeStyle = B.rgba(PAL.navy, 0.4);
        ctx.lineWidth = 0.3 * u;
        ctx.setLineDash([1.2 * u, 0.9 * u]);
        ctx.strokeRect(x, y, side, side);
        ctx.restore();
      }
      // the square: folded down over its bottom edge (its teal back showing), it swings up into the slot
      const k = B.prog(lt, 0, 0.6, "inOutCubic"), settle = k >= 1 ? 1 : k + 0.03 * Math.sin(Math.PI * B.smooth(0.8, 1, k));
      const cs = Math.cos(Math.PI * (1 - settle) + Math.PI * 0.4 * off), hy = y + side; // at the end they start to swing away
      if (lt > 0 && Math.abs(cs) > 0.02) {
        ctx.save();
        ctx.globalAlpha *= B.smooth(0, 0.08, lt);
        ctx.transform(1, 0, 0, cs, 0, hy * (1 - cs));
        ctx.fillStyle = B.rgba(PAL.shadow, 0.5);
        ctx.fillRect(x + 0.9 * u, y + 1.1 * u, side, side);
        ctx.fillStyle = cs > 0 ? PAL.white : B.shade(PAL.teal, 0.1 * cs);
        ctx.fillRect(x, y, side, side);
        if (cs > 0) {
          ctx.strokeStyle = B.rgba(PAL.navy, 0.35);
          ctx.lineWidth = 0.2 * u;
          ctx.strokeRect(x + 1.2 * u, y + 1.2 * u, side - 2.4 * u, side - 2.4 * u);
          const cx = x + side / 2, cy = y + side * 0.56, s2 = side * 0.3, m = B.prog(lt, 0.4, 0.6);
          if (i === 0) {
            // the sun sinks to the Arctic horizon, a folded strip of white
            const sy = cy - s2 * 0.5 + m * s2 * 0.7;
            ctx.save();
            ctx.beginPath();
            ctx.rect(x, y, side, cy + s2 * 0.35 - y);
            ctx.clip();
            paperModel(ctx, sunFaces(), { x: cx, y: sy, s: s2 * 0.7, yaw: 0.2 * B.wave(t, 4) });
            ctx.restore();
            paperArrow(ctx, x + side * 0.1, cy + s2 * 0.45, side * 0.8, 1.6 * u, 0, 1, PAL.white);
            ctx.fillStyle = B.rgba(PAL.teal, 0.9);
            ctx.fillRect(x + side * 0.1, cy + s2 * 0.62, side * 0.8, 1.2 * u);
            foldArrow(ctx, [[cx + s2 * 0.95, cy - s2 * 0.75], [cx + s2 * 1.05, cy - s2 * 0.25], [cx + s2 * 0.85, cy + s2 * 0.15]], m, PAL.coral, 0.35);
          } else if (i === 1) {
            ctx.fillStyle = B.rgba(PAL.teal, 0.25);
            ctx.fillRect(x + 1.2 * u, cy + s2 * 0.2, side - 2.4 * u, side * 0.25);
            foldArrow(ctx, B.quad(cx - s2 * 1.2, cy - s2 * 0.6, cx, cy - s2 * 0.4, cx + s2 * 0.6, cy + s2 * 0.9), m, PAL.coral, 0.35);
            paperModel(ctx, tern(t, 0.9), { x: cx - s2 * 0.15, y: cy - s2 * 0.25, s: s2 * 0.5, yaw: 0.3, pitch: -0.5, roll: -0.35 });
          } else {
            paperModel(ctx, globeFaces({ south: 0.28 * m }), { x: cx, y: cy, s: s2 * 0.85, yaw: 0.3 + m * 0.3, pitch: -0.35, roll: GT });
            paperModel(ctx, sunFaces(), { x: cx + s2 * 1.0, y: cy + s2 * 0.75, s: s2 * 0.32 });
          }
        }
        ctx.restore();
      }
      // the step number in a navy disc on the slot's corner (on top of the square)
      if (mark > 0.01) {
        ctx.save();
        ctx.globalAlpha *= mark;
        ctx.fillStyle = PAL.navy;
        ctx.beginPath();
        B.circle(ctx, x + 4.6 * u, y + 4.6 * u, 3.4 * u);
        ctx.fill();
        ctx.restore();
        words(ctx, String(i + 1), x + 4.6 * u, y + 4.7 * u, 4.2 * u, mark, { align: "center", baseline: "middle", mono: true, color: PAL.white });
      }
      // caption beside (portrait) or under (landscape) the square
      const tx = P ? x + side + 4 * u : x, ty = P ? y + side * 0.36 : y + side + 4 * u;
      words(ctx, txt, tx, ty, cap, B.smooth(0.35, 0.65, lt) * on, { maxW: P ? S.r - tx : side + 6 * u, weight: 600 });
    });
  }

  function sceneClose(ctx, L, t, lt) {
    const u = L.u, P = L.P, S = L.S, s = L.heroS;
    const e = 0.8 * (1 - B.smooth(0, 0.5, lt)), rise = B.smooth(0.6, 1.4, lt) * 2 * u;
    // the tern over a small folded globe: two summers, pole to pole
    const [gx, gy, gr] = P ? [L.F.W * 0.5, L.F.H * 0.69, 14 * u] : [S.x + S.w * 0.24, L.F.H * 0.71, 13 * u];
    const gb = paperModel(M, globeFaces({ north: 0.25, south: 0.25 }), { x: gx, y: gy, s: gr, yaw: 0.3 + lt * 0.15, pitch: 0.16, roll: GT, e: 0.8 * (1 - B.smooth(0.2, 0.7, lt)) });
    shadowUnder(ctx, gb, gy + gr * 1.2, 0.1);
    const hx = P ? L.F.W * 0.5 : L.F.W * 0.68, hy = (P ? L.F.H * 0.52 : L.F.H * 0.38) - rise, ts = P ? s * 0.7 : s * 0.66;
    const box = paperModel(M, tern(t, 1.2), { x: hx, y: hy, s: ts, yaw: 0.3 + 0.1 * B.wave(t, 6), pitch: -0.5, roll: 0.06, e });
    shadowUnder(ctx, box, P ? gy - gr * 1.25 : hy + ts * 0.9, 0.6);
    const [tx, ty] = L.title;
    const r = words(ctx, "Two summers,\nevery year.", tx, ty, L.head, B.smooth(0, 0.4, lt), { maxW: P ? S.w : S.w * 0.48 });
    if (r) tab(ctx, tx, r.bottom + L.lab * 2.2, "the longest known migration", L.lab, B.prog(lt, 0.6, 0.5), { fill: PAL.teal, ink: PAL.white, mono: true });
    // landscape: the year's route leaves the globe and climbs to the bird
    if (!P) foldArrow(ctx, B.quad(gx + gr * 1.3, gy - gr * 0.4, hx - ts * 1.6, gy - gr * 0.2, hx - ts * 1.35, hy + ts * 0.3), B.prog(lt, 0.9, 0.7, "inOutSine"), PAL.coral, 0.5);
  }

  // ---- frame
  function backdrop(ctx, W, H, u) {
    const c = B.layer("fp-backdrop", W, H, (g, w, h) => {
      g.fillStyle = PAL.back;
      g.fillRect(0, 0, w, h);
      // a gentle top-left light wash, nothing dramatic
      g.fillStyle = B.radial(g, w * 0.1, h * 0.05, 0, Math.hypot(w, h) * 0.9, [[0, "rgba(255,255,255,0.55)"], [0.5, "rgba(255,255,255,0.12)"], [1, "rgba(120,110,95,0.12)"]]);
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: 0.06, feature: 0.2, seed: 3, mode: "soft-light" });
    });
    ctx.drawImage(c, 0, 0);
    void u;
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    U = L.u;
    backdrop(ctx, W, H, U);
    M = B.scratch("fp-models", W, H);
    if (t < BEATS[1]) sceneTitle(ctx, L, t);
    else if (t < BEATS[2]) sceneDiagram(ctx, L, t, t - BEATS[1]);
    else if (t < BEATS[3]) sceneNumber(ctx, L, t, t - BEATS[2]);
    else if (t < BEATS[5]) sceneSteps(ctx, L, t);
    else sceneClose(ctx, L, t, t - BEATS[5]);
    // very light paper grain on every facet, then the models land on the backdrop over their shadows
    B.grain(M, W, H, { amount: 0.07, mode: "source-atop", seed: 4, scale: Math.max(1, U / 7) });
    ctx.drawImage(M.canvas, 0, 0);
    B.grain(ctx, W, H, { amount: 0.035, t, fps: 12, mode: "soft-light" });
  }

  // ---- sound: crisp fold snaps, dry paper slides, airy ticks, a quiet tone bed
  SOUND.define("paper-fold", (v) => {
    // a crease being pressed: a dry papery crack and a tiny low thump
    v.noise({ filter: "bandpass", f: 2600, q: 1.4, a: 0.001, len: 0.05, peak: 0.45 });
    v.noise({ at: 0.012, filter: "highpass", f: 4200, a: 0.001, len: 0.03, peak: 0.2 });
    v.tone({ f: 160, f2: 90, glide: 0.05, a: 0.001, len: 0.06, peak: 0.12 });
  }, { verb: 0.12 });

  function score(k) {
    k.bed("pad", 0, DUR, { notes: ["D3", "A3", "E4"], gain: 0.28, bright: 900 });
    // title: the sheet lands, four corners fold, it folds into a bird
    k.at(0.05, "paper", { dur: 0.4, gain: 0.6 });
    [0, 1, 2, 3].forEach((i) => k.at(0.3 + i * 0.22 + 0.36, "paper-fold", { pitch: i, gain: 0.8 }));
    k.at(1.45, "flip", { dur: 0.4, gain: 0.6 }).at(2.25, "paper-fold", { pitch: 3 }).at(2.3, "pluck", { note: "A4", gain: 0.4 });
    k.at(0.9, "tick", { gain: 0.4 });
    // diagram: globe folds in, tabs unfold, route drawn
    k.at(BEATS[1], "flip", { dur: 0.4, gain: 0.5 }).at(BEATS[1] + 0.4, "paper-fold");
    [0.35, 0.8, 1.1].forEach((a, i) => k.at(BEATS[1] + a, "tick", { gain: 0.5, pitch: i * 2 }).at(BEATS[1] + a + 0.05, "rustle", { dur: 0.2, gain: 0.4 }));
    k.at(BEATS[1] + 0.5, "paper", { dur: 0.9, gain: 0.4 });
    // number: the card folds out, the count ticks, it settles
    k.at(BEATS[2], "flip", { dur: 0.4, gain: 0.5 }).at(BEATS[2] + 0.3, "swish", { dur: 0.5, gain: 0.3 });
    k.at(BEATS[2] + 0.45, "paper", { dur: 0.7, gain: 0.6 }).at(BEATS[2] + 1.15, "paper-fold", { gain: 1 });
    k.repeat(BEATS[2] + 0.8, 0.07, 11, "tick", { gain: 0.35, vary: 1 });
    k.at(BEATS[2] + 1.65, "chord", { notes: ["D4", "F#4", "A4", "E5"], strum: 0.04, gain: 0.35 });
    // three origami squares flip in
    [0.15, 1.1, 2.05].forEach((a, i) => {
      k.at(BEATS[3] + a, "flip", { dur: 0.3, gain: 0.5, pitch: i }).at(BEATS[3] + a + 0.35, "paper-fold", { pitch: i * 2 });
      k.at(BEATS[3] + a + 0.45, "tick", { gain: 0.45, pitch: 5 + i * 2 }).at(BEATS[3] + a + 0.45, "pluck", { note: ["D5", "F#5", "A5"][i], gain: 0.35 });
    });
    // close
    k.at(BEATS[5], "flip", { dur: 0.45, gain: 0.5 }).at(BEATS[5] + 0.45, "paper-fold", { pitch: -2 });
    k.at(BEATS[5] + 0.9, "tick", { gain: 0.4 }).at(BEATS[5] + 1.0, "chime", { note: "A5", gain: 0.3 });
  }

  Player.register({
    id: "folded-paper",
    name: "Folded Paper",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Space+Mono:wght@700&display=swap",
      faces: ['700 20px "Space Grotesk"', '600 20px "Space Grotesk"', '700 20px "Space Mono"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [2.45, 4.4, 6.7, 9.2, 10.5, 12.6],
    draw,
    score,
  });
})();
