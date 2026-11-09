/* 08 Clay Stop-Motion. Topic (replace it): "Why do we brush our teeth?".
 * Rendering (keep it): every object a lumpy plasticine lump shaded by implied height (blurred inset copies lit from
 * the top left over a warmer shadow side), dull waxy sheen, fingerprints, tool grooves, contact patches. Letters are
 * rolled-clay glyphs; labels are letters pressed into a cream slab; arrows are clay snakes with a pinched point.
 * Finish: warm soft-light grade, exposure flicker per pose, brown vignette, blurred far edges, grain per pose.
 * Motion: on twos; surface boils per pose; pops squash/stretch/overshoot; exits knocked off or shoved; words letter
 * by letter. Portrait stacks the words big in the wall band above the tooth; landscape uses the width.
 */
(function () {
  "use strict"; const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { wall: "#e7cfa8", table: "#c98f5a", red: "#d6453a", blue: "#3f7cc4", yellow: "#f2c14a",
    green: "#5ea65a", cream: "#f4ead6", brown: "#3b2418" };
  const FONT = "Baloo 2"; const DUR = 12;
  const BEATS = [0, 1.9, 4.0, 6.1, 8.4, 10.3];
  const FPS = 12; // poses per second: on twos at 24 fps

  let U = 1, POSE = 0; // frame unit and the current pose index (for boil)
  const posed = (t) => B.stepTime(t, FPS);

  // ---- clay helpers (reuse these)
  /** Clay tones: the shadow side warmer and richer (light glows through), the lit side paler. */
  function tones(c) {
    return { dark: B.shade(B.mix(c, "#8a2c12", 0.2), -0.2), base: c, light: B.mix(c, "#fff3df", 0.38) };
  }
  const bboxOf = (pts) => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys), x1 = Math.max(...xs), y1 = Math.max(...ys);
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
  };
  /** Lumpy ellipse outline: soft seeded bulges plus a tiny boil that changes on every pose. */
  function lumpPts(cx, cy, rx, ry, seed, o = {}) {
    const n = o.n ?? 22, out = [], bulge = o.bulge ?? 0.06;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU;
      const k = 1 + bulge * B.noise2(Math.cos(a) * 1.4, Math.sin(a) * 1.4, seed) + 0.012 * B.noise2(Math.cos(a) * 3, Math.sin(a) * 3, seed + POSE * 7);
      out.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    return out;
  }
  /** Roll any outline into lumpy clay: densify, push points out by low noise and the per-pose boil. */
  function lumpify(pts, seed, amp = 0.35) {
    const d = B.densify(pts.concat([pts[0]]), 1.6 * U).slice(0, -1);
    const bb = bboxOf(d);
    return d.map(([x, y], i) => {
      const a = Math.atan2(y - bb.cy, x - bb.cx);
      const k = amp * U * B.noise2(x / (5 * U), y / (5 * U), seed) + 0.12 * U * B.noise2(i * 0.7, POSE * 0.9, seed + 3);
      return [x + Math.cos(a) * k, y + Math.sin(a) * k];
    });
  }
  /** Closed Catmull-Rom curve through pts: rounded corners before lumpify. */
  function roundPts(pts, k = 6) {
    const n = pts.length, out = [];
    for (let i = 0; i < n; i++) {
      const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      for (let j = 0; j < k; j++) {
        const t = j / k, t2 = t * t, t3 = t2 * t;
        out.push([0, 1].map((c) => 0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3)));
      }
    }
    return out;
  }
  /** Draw fn at x, y, turned by rot and scaled by the pose ps = [sx, sy]. */
  const placed = (ctx, x, y, rot, ps, fn) => { ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(ps[0], ps[1]); fn(); ctx.restore(); };
  const pathOf = (ctx, pts) => { ctx.beginPath(); B.smoothPath(ctx, pts, true); };
  const fillPts = (ctx, pts, style) => { pathOf(ctx, pts); ctx.fillStyle = style; ctx.fill(); };
  /** Soft brown drop shadow down and to the right, in frame units. */
  const drop = (ctx, a, blur, x, y) => Object.assign(ctx, { shadowColor: B.rgba(PAL.brown, a), shadowBlur: blur * U, shadowOffsetX: x * U, shadowOffsetY: y * U });
  /** Short smeared strokes (thumb smears on the wall, tool drags on the table). */
  function smears(g, r, n, x0, y0, w, h, col, len, lw, curl) {
    for (let i = 0; i < n; i++) {
      const x = x0 + r() * w, y = y0 + r() * h, l = r.range(...len), a = curl ? r.range(-0.5, 0.5) + (r() < 0.5 ? 0 : Math.PI) : r.range(-0.1, 0.1);
      g.strokeStyle = B.rgba(B.shade(col, r() < 0.5 ? -0.13 : 0.15), r.range(0.12, 0.4));
      g.lineWidth = r.range(...lw); g.beginPath(); g.moveTo(x, y);
      g.quadraticCurveTo(x + Math.cos(a + 0.4) * l * 0.5, y + Math.sin(a + 0.4) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l);
      g.stroke();
    }
  }
  const scalePts = (pts, cx, cy, kx, ky, dx, dy) => pts.map(([x, y]) => [cx + (x - cx) * kx + dx, cy + (y - cy) * ky + dy]);
  /** Lumpy noise tile for the clay surface; offset on each pose, so the surface boils. */
  function noiseTile() {
    return B.layer("clay-noise", 256, 256, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(5);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const v = 0.5 + 0.18 * Math.sin((x / w) * B.TAU * 3 + Math.sin((y / h) * B.TAU * 2) * 1.5) * Math.sin((y / h) * B.TAU * 4 + 1) + (r() - 0.5) * 0.35;
          const i = (y * w + x) * 4; d.fill(B.clamp(v) * 255, i, i + 3);
          d[i + 3] = 255;
        }
      g.putImageData(img, 0, 0);
    });
  }
  /** Partial fingerprint: concentric curved ridges (dark groove + light ridge) fading at the edges. */
  function fingerprint(ctx, x, y, r, rot, seed) {
    const rr = B.rng(seed), n = 7, span = rr.range(1.2, 2.0);
    ctx.save(); ctx.lineCap = "round"; ctx.lineWidth = Math.max(1, r * 0.045);
    const jx = (B.hash01(seed, POSE) - 0.5) * 0.15 * U, jy = (B.hash01(seed, POSE, 2) - 0.5) * 0.15 * U;
    for (let i = 0; i < n; i++) {
      const rad = r * (0.25 + (i / n) * 0.8), fade = Math.sin(((i + 0.5) / n) * Math.PI);
      for (const [dx, col, a] of [[0, "#3b2418", 0.11], [r * 0.04, "#ffffff", 0.1]]) {
        ctx.strokeStyle = B.rgba(col, a * fade); ctx.beginPath();
        ctx.ellipse(x + dx + jx, y + dx + jy, rad, rad * 0.78, rot, -span / 2, span / 2);
        ctx.stroke();
      }
    }
    ctx.restore();
  }
  /**
   * The heart of the look: one plasticine lump. o: { table (contact patch), prints, groove, seed, sheen, shadow }.
   * Shading: the richer shadow tone, then an inset copy (even margin, so long slabs shade like round lumps) nudged
   * to the light and blurred in the base colour, a paler key-light copy, a dull sheen, then the boiling surface.
   */
  function clay(ctx, pts, color, o = {}) {
    const bb = bboxOf(pts), m = o.m ?? Math.min(bb.w, bb.h), T = tones(color), seed = o.seed ?? 1;
    if (o.table) {
      // soft dark contact patch where it meets the table
      const base = bb.y + bb.h; ctx.save();
      ctx.fillStyle = B.radial(ctx, bb.cx, base, 0, bb.w * 0.55, [B.rgba(PAL.brown, 0.55), B.rgba(PAL.brown, 0)]);
      ctx.translate(bb.cx, base); ctx.scale(1, 0.22);
      ctx.translate(-bb.cx, -base);
      ctx.fillRect(bb.cx - bb.w * 0.6, base - bb.w * 0.6, bb.w * 1.2, bb.w * 1.2);
      ctx.restore();
    }
    ctx.save();
    if (o.shadow !== false) drop(ctx, 0.42, 1.8, 0.9, 1.2);
    fillPts(ctx, pts, T.dark); ctx.restore(); ctx.save();
    pathOf(ctx, pts); ctx.clip();
    ctx.filter = `blur(${(m * 0.11).toFixed(1)}px)`;
    const ins = (k) => [1 - (m * k) / bb.w, 1 - (m * k) / bb.h];
    fillPts(ctx, scalePts(pts, bb.cx, bb.cy, ...ins(0.16), -m * 0.05, -m * 0.07), T.base);
    ctx.filter = `blur(${(m * 0.16).toFixed(1)}px)`;
    fillPts(ctx, scalePts(pts, bb.cx, bb.cy, ...ins(0.5), -m * 0.12, -m * 0.15), B.rgba(T.light, 0.8));
    // a small dull sheen near the top (waxy, soft-edged)
    ctx.filter = `blur(${(m * 0.06).toFixed(1)}px)`;
    ctx.beginPath();
    ctx.ellipse(bb.x + bb.w * 0.34, bb.y + bb.h * 0.24, m * 0.12, m * 0.07, -0.5, 0, B.TAU);
    ctx.fillStyle = B.rgba("#fffaf0", 0.22 * (o.sheen ?? 1));
    ctx.fill(); ctx.filter = "none";
    // lumpy surface that boils: a noise tile offset on every pose, soft-light
    const pat = ctx.createPattern(noiseTile(), "repeat");
    pat.setTransform(new DOMMatrix([U / 7, 0, 0, U / 7, B.hash01(seed, POSE) * 256, B.hash01(seed, POSE, 1) * 256]));
    Object.assign(ctx, { globalCompositeOperation: "soft-light", globalAlpha: 0.45, fillStyle: pat });
    ctx.fillRect(bb.x, bb.y, bb.w, bb.h);
    Object.assign(ctx, { globalCompositeOperation: "source-over", globalAlpha: 1 });
    const r = B.rng(seed + 11);
    for (let i = 0; i < (o.prints ?? (m > 8 * U ? 1 : 0)); i++) fingerprint(ctx, bb.x + bb.w * r.range(0.25, 0.75), bb.y + bb.h * r.range(0.25, 0.7), m * r.range(0.16, 0.24), r() * B.TAU, seed + i);
    if (o.groove) {
      // shallow tool groove with a slightly raised lip
      const g0 = [bb.x + bb.w * 0.25, bb.y + bb.h * r.range(0.45, 0.7)];
      const g = B.quad(g0[0], g0[1], bb.cx, g0[1] + m * 0.12, bb.x + bb.w * 0.72, g0[1] - m * 0.05);
      B.strokeReveal(ctx, g, 1, { width: Math.max(1, m * 0.025), color: B.rgba(PAL.brown, 0.22) });
      B.strokeReveal(ctx, g.map(([x, y]) => [x + m * 0.012, y + m * 0.018]), 1, { width: Math.max(1, m * 0.018), color: B.rgba("#ffffff", 0.16) });
    }
    ctx.restore();
  }
  /** Rolled-clay glyph (cached): a puffy letter shaded like a lump. */
  function glyph(ch, color, size) {
    size = Math.round(size);
    return B.layer(`clay-glyph:${ch}:${color}:${size}`, size * 1.6, size * 1.6, (g, w, h) => {
      const mk = B.canvas(w, h), m = mk.getContext("2d");
      Object.assign(m, { font: B.font(size, FONT, 800), textAlign: "center", textBaseline: "middle", lineJoin: "round", lineWidth: size * 0.1, fillStyle: "#fff", strokeStyle: "#fff" });
      m.strokeText(ch, w / 2, h / 2 + size * 0.08);
      m.fillText(ch, w / 2, h / 2 + size * 0.08);
      const tint = (col) => {
        const c = B.canvas(w, h), cg = c.getContext("2d");
        cg.drawImage(mk, 0, 0);
        Object.assign(cg, { globalCompositeOperation: "source-in", fillStyle: col });
        cg.fillRect(0, 0, w, h); return c;
      };
      const T = tones(color); g.drawImage(tint(T.dark), 0, 0);
      g.globalCompositeOperation = "source-atop";
      g.filter = `blur(${(size * 0.06).toFixed(1)}px)`;
      g.drawImage(tint(T.base), -size * 0.035, -size * 0.045);
      g.filter = `blur(${(size * 0.09).toFixed(1)}px)`;
      g.globalAlpha = 0.65;
      g.drawImage(tint(T.light), -size * 0.07, -size * 0.09);
      g.filter = "none"; g.globalAlpha = 1;
      // a faint fingerprint pressed into the glyph
      const sv = U; U = size / 12;
      fingerprint(g, w * 0.45, h * 0.42, size * 0.28, B.hash01(ch, color) * B.TAU, B.hash(ch) % 97);
      U = sv;
    });
  }
  /** Pop-on in held poses: flat & wide, tall, overshoot, settled. */
  function popPose(t, at) {
    if (t < at) return null;
    const i = Math.floor((t - at) * FPS + 1e-6);
    return [[1.45, 0.45], [0.78, 1.32], [1.12, 0.9], [0.96, 1.05], [1, 1]][Math.min(i, 4)];
  }
  /** Knocked off: falls with gravity and tumbles out the bottom. */
  function knock(t, at, dir = 1) {
    if (!(t >= at)) return { dx: 0, dy: 0, rot: 0 };
    const d = t - at;
    return { dx: dir * d * 22 * U, dy: -d * 18 * U + 0.5 * 460 * U * d * d, rot: dir * d * 5 };
  }
  /** Shoved off to the side, speeding up. */
  const shove = (t, at, dir = 1) => (t < at ? 0 : dir * 0.5 * 220 * U * (t - at) * (t - at));
  /** Rolled-clay word, one new letter per pose; colours cycle. o: { colors, gone, shift } */
  function clayWord(ctx, word, x, y, size, t, at, o = {}) {
    const cols = o.colors || [PAL.red, PAL.yellow, PAL.blue, PAL.green];
    ctx.save(); ctx.font = B.font(size, FONT, 800);
    const ws = [...word].map((c) => (c === " " ? size * 0.35 : ctx.measureText(c).width + size * 0.1));
    ctx.restore();
    const total = ws.reduce((a, b) => a + b, 0);
    let cx = x - total / 2, k = 0;
    [...word].forEach((c, i) => {
      const w = ws[i];
      if (c !== " ") {
        const ps = popPose(t, at + k / FPS); k++;
        if (ps) {
          const img = glyph(c, cols[(i + (o.shift ?? 0)) % cols.length], size);
          const kn = knock(t, o.gone + i * 0.04, i % 2 ? 1 : -1);
          ctx.save();
          ctx.translate(cx + w / 2 + kn.dx, y + kn.dy);
          ctx.rotate(B.lerp(-0.08, 0.08, B.hash01(c, i, 3)) + kn.rot);
          ctx.scale(ps[0], ps[1]); drop(ctx, 0.45, 1.4, 0.6, 0.9);
          ctx.drawImage(img, -img.width / 2, -img.height * 0.5 - size * 0.42);
          ctx.restore();
        }
      }
      cx += w;
    });
  }
  /** Label: words pressed into a cream slab (cavities: dark floor, lit lower-right wall). */
  function slab(ctx, x, y, text, size, t, at, o = {}) {
    const ps = popPose(t, at); if (!ps) return;
    const kn = knock(t, o.gone, o.dir ?? 1);
    const col = o.color || PAL.cream, sd = o.seed ?? 7;
    placed(ctx, x + kn.dx, y + kn.dy, kn.rot + (o.rot ?? 0), ps, () => {
      ctx.font = B.font(size, FONT, 800);
      const w = ctx.measureText(text).width + size * 1.9, h = size * 1.8;
      const a = w / 2, b = h / 2, r = h * 0.34, Q = Math.PI / 2; // a rounded slab, then rolled lumpy
      const pts = lumpify([[a - r, r - b, -Q], [a - r, b - r, 0], [r - a, b - r, Q], [r - a, r - b, 2 * Q]].flatMap(([x, y, q]) => B.arcPts(x, y, r, q, q + Q, 5)), sd, 0.25);
      clay(ctx, pts, col, { seed: sd, prints: 1, sheen: 0.6 });
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const d = Math.max(1, size * 0.05); ctx.fillStyle = B.rgba("#fffaf0", 0.75);
      ctx.fillText(text, d, size * 0.08 + d);
      ctx.fillStyle = B.mix(col, PAL.brown, 0.88); // dark, so it reads
      ctx.fillText(text, 0, size * 0.08);
    });
  }
  /** Clay snake laid along a path, pinched point at the head; p = how much is laid. */
  function coil(ctx, pts, p, width, color, seed) {
    if (p <= 0.02) return;
    const path = B.densify(B.trim(pts, 0, p), 1.2 * U), n = path.length;
    if (n < 3) return;
    const left = [], right = [], L = B.pathLength(path);
    let s = 0;
    for (let i = 0; i < n; i++) {
      if (i) s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
      const f = s / L, a = path[Math.max(0, i - 1)], b = path[Math.min(n - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0]; const l = Math.hypot(nx, ny) || 1;
      nx /= l; ny /= l;
      // once laid, the end is pinched into a wide head tapering to a point
      const head = p >= 0.99 && f > 0.7 ? Math.max(0.06, (2.4 * (1 - f)) / 0.3) : 1;
      const w = (width / 2) * Math.min(1, f / 0.04 + 0.6) * head * (1 + 0.08 * B.noise1(s / (2 * U), seed));
      left.push([path[i][0] + nx * w, path[i][1] + ny * w]);
      right.push([path[i][0] - nx * w, path[i][1] - ny * w]);
    }
    clay(ctx, left.concat(right.reverse()), color, { seed, prints: 0, sheen: 0.8, m: width * 1.1 });
  }
  /** Gold clay star (the key moment). */
  function star(ctx, x, y, r, t, at, seed) {
    const ps = popPose(t, at); if (!ps) return;
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.5 : r;
      pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
    }
    placed(ctx, x, y, 0.1 * Math.sin(POSE * 0.7), ps, () => clay(ctx, lumpify(pts, seed, 0.2), PAL.yellow, { seed, prints: 1 }));
  }
  /** Red cross (wrong, with a shake) or green tick (right). */
  function mark(ctx, x, y, s, kind, t, at, seed) {
    const ps = popPose(t, at); if (!ps) return;
    const shake = kind === "cross" && t - at < 0.4 ? Math.sin(POSE * 2.6) * 0.8 * U : 0;
    const bar = (x1, y1, x2, y2, sd) => {
      const a = Math.atan2(y2 - y1, x2 - x1), nx = -Math.sin(a) * s / 4, ny = Math.cos(a) * s / 4;
      const pts = [[x1 + nx, y1 + ny], [x2 + nx, y2 + ny], [x2 - nx, y2 - ny], [x1 - nx, y1 - ny]];
      clay(ctx, lumpify(pts, sd, 0.2), kind === "cross" ? PAL.red : PAL.green, { seed: sd, prints: 0 });
    };
    const X = kind === "cross" ? [-1, -1, 1, 1, 1, -1, -1, 1] : [-0.9, 0, -0.2, 0.7, -0.35, 0.7, 1, -0.9];
    placed(ctx, x + shake, y, 0, ps, () => {
      bar(X[0] * s, X[1] * s, X[2] * s, X[3] * s, seed);
      bar(X[4] * s, X[5] * s, X[6] * s, X[7] * s, seed + 1);
    });
  }
  /** Eye: a white clay ball with a glossy black pupil. look = [dx, dy] in -1..1. */
  function eye(ctx, x, y, r, look = [0, 0], seed = 1) {
    clay(ctx, lumpPts(x, y, r, r, seed, { bulge: 0.03, n: 14 }), "#fbf7ef", { seed, prints: 0, shadow: false });
    ctx.beginPath();
    B.circle(ctx, x + look[0] * r * 0.32, y + look[1] * r * 0.32, r * 0.5);
    ctx.fillStyle = "#15100c"; ctx.fill(); ctx.beginPath();
    B.circle(ctx, x + look[0] * r * 0.32 - r * 0.18, y + look[1] * r * 0.32 - r * 0.2, r * 0.15);
    ctx.fillStyle = "#ffffff"; ctx.fill();
  }

  // ---- subjects (the setting: replace these)
  /** Tooth: a cream crown with two roots, clay eyes and a carved smile. y = base. */
  function tooth(ctx, x, y, s, t, o = {}) {
    const raw = [[-0.5, -1.38], [-0.22, -1.5], [0, -1.4], [0.22, -1.5], [0.5, -1.38], [0.66, -1.0], [0.6, -0.5], [0.45, -0.08], [0.32, 0.0], [0.2, -0.28], [0, -0.4], [-0.2, -0.28], [-0.32, 0.0], [-0.45, -0.08], [-0.6, -0.5], [-0.66, -1.0]].map(([a, b]) => [x + a * s, y + b * s]);
    const col = o.color || PAL.cream;
    clay(ctx, lumpify(roundPts(raw, 5), 21, 0.22), col, { table: true, seed: 21, prints: 2, groove: false });
    const look = o.look || [0.2, 0.1];
    eye(ctx, x - s * 0.22, y - s * 1.0, s * 0.13, look, 22);
    eye(ctx, x + s * 0.2, y - s * 1.0, s * 0.13, look, 23);
    // carved mouth: a groove with a light lower lip
    const happy = o.smile ?? 0.6;
    const m = B.quad(x - s * 0.18, y - s * 0.72, x, y - s * (0.72 - 0.16 * happy), x + s * 0.18, y - s * 0.72);
    B.strokeReveal(ctx, m, 1, { width: s * 0.05, color: B.rgba(PAL.brown, 0.6) });
    B.strokeReveal(ctx, m.map(([a, b]) => [a + s * 0.01, b + s * 0.025]), 1, { width: s * 0.025, color: B.rgba("#ffffff", 0.45) });
  }
  /** Germ: a leaf-green lump with little nubs and clay eyes. */
  function germ(ctx, x, y, r, seed, look = [0, 0]) {
    const pts = [];
    for (let i = 0; i < 28; i++) {
      const a = (i / 28) * B.TAU, nub = Math.pow(Math.max(0, Math.cos(a * 7 + seed)), 6) * 0.22;
      pts.push([x + Math.cos(a) * r * (1 + nub), y + Math.sin(a) * r * 0.86 * (1 + nub)]);
    }
    clay(ctx, lumpify(pts, seed, 0.15), PAL.green, { seed, prints: 0 });
    eye(ctx, x - r * 0.3, y - r * 0.15, r * 0.24, look, seed + 1);
    eye(ctx, x + r * 0.28, y - r * 0.15, r * 0.24, look, seed + 2);
  }
  /** Wrapped sweet: a yellow body with twisted red ends. */
  function candy(ctx, x, y, s, seed) {
    const cy = y - s * 0.42;
    [-1, 1].forEach((d, i) => clay(ctx, lumpify(roundPts([[x + d * s * 0.42, cy], [x + d * s * 1.0, cy - s * 0.42], [x + d * s * 1.15, cy], [x + d * s * 1.0, cy + s * 0.42]], 4), seed + i, 0.15), PAL.red, { seed: seed + i, prints: 0, table: true }));
    clay(ctx, lumpPts(x, cy, s * 0.62, s * 0.42, seed + 3), PAL.yellow, { seed: seed + 3, prints: 1, table: true, groove: true });
  }
  /** Toothbrush: cobalt handle, bristle tufts at x, y; paste (0..1) pops a blob on top. */
  function brush(ctx, x, y, s, paste, seed) {
    const hp = [[x - s * 0.45, y - s * 0.08], [x + s * 2.6, y - s * 0.02], [x + s * 2.65, y + s * 0.2], [x - s * 0.45, y + s * 0.2]];
    clay(ctx, lumpify(hp, seed, 0.2), PAL.blue, { seed, prints: 1, groove: true });
    for (let i = 0; i < 5; i++) clay(ctx, lumpPts(x - s * 0.35 + i * s * 0.18, y - s * 0.22, s * 0.085, s * 0.2, seed + 5 + i, { n: 12, bulge: 0.08 }), "#fbf6ea", { seed: seed + 5 + i, prints: 0, shadow: i === 4 });
    if (paste > 0) {
      const ps = [[1.4, 0.4], [0.8, 1.3], [1.1, 0.9], [1, 1]][Math.min(3, Math.floor(paste * 4))];
      placed(ctx, x, y - s * 0.45, 0, ps, () => {
        clay(ctx, lumpPts(0, 0, s * 0.33, s * 0.14, seed + 20), "#e9f5f6", { seed: seed + 20, prints: 0 });
        clay(ctx, lumpPts(s * 0.02, -s * 0.03, s * 0.22, s * 0.05, seed + 21, { n: 12 }), "#5bb8c4", { seed: seed + 21, prints: 0, shadow: false });
      });
    }
  }

  // ---- the set: smeared clay wall, table slab, crumbs (cached)
  function set(ctx, W, H, L) {
    const c = B.layer("clay-set:" + L.P, W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, top = L.tableTop, r = B.rng("set");
      // back wall of smeared clay, out of focus
      const wall = B.canvas(w, top + 6 * u), wg = wall.getContext("2d");
      wg.fillStyle = PAL.wall; wg.fillRect(0, 0, w, wall.height);
      wg.lineCap = "round";
      smears(wg, r, 160, 0, 0, w, wall.height, PAL.wall, [4 * u, 14 * u], [1.5 * u, 4 * u], true);
      g.filter = `blur(${(0.9 * u).toFixed(1)}px)`;
      g.drawImage(wall, 0, 0); g.filter = "none";
      // warm pool of light on the wall
      g.fillStyle = B.radial(g, w * 0.45, top * 0.55, 0, Math.max(w, h) * 0.55, [B.rgba("#fff1d6", 0.55), B.rgba("#fff1d6", 0)]);
      g.fillRect(0, 0, w, top);
      g.fillStyle = B.linear(g, 0, top - 8 * u, 0, top, [B.rgba(PAL.brown, 0), B.rgba(PAL.brown, 0.25)]);
      g.fillRect(0, top - 8 * u, w, 8 * u);
      // the tabletop slab: lumpy back edge, smears, front edge darkening
      const sv = U, svP = POSE; U = u; POSE = 0;
      const slabPts = lumpify([[-4 * u, top], [w + 4 * u, top], [w + 4 * u, h + 8 * u], [-4 * u, h + 8 * u]], 3, 0.6);
      g.save(); pathOf(g, slabPts); g.clip();
      g.fillStyle = B.linear(g, 0, top, 0, h, [B.shade(PAL.table, 0.08), PAL.table, B.shade(PAL.table, -0.1)]);
      g.fillRect(0, top - 4 * u, w, h - top + 8 * u);
      smears(g, r, 90, 0, top, w, h - top, PAL.table, [3 * u, 10 * u], [0.8 * u, 2.4 * u]);
      fingerprint(g, w * 0.2, top + (h - top) * 0.35, 6 * u, 0.4, 3);
      fingerprint(g, w * 0.82, top + (h - top) * 0.5, 7 * u, 2.1, 4);
      const edge = L.tableEdge;
      g.fillStyle = B.linear(g, 0, edge - 4 * u, 0, h, [B.rgba(PAL.brown, 0), B.rgba(PAL.brown, 0.35), B.rgba(PAL.brown, 0.75)]);
      g.fillRect(0, edge - 4 * u, w, h - edge + 4 * u);
      g.fillStyle = B.rgba("#fff4e0", 0.18); g.fillRect(0, top, w, 0.5 * u);
      g.restore();
      // stray crumbs of clay (blurred slightly: they are near the out-of-focus edges)
      [PAL.red, PAL.yellow, PAL.blue, PAL.green, PAL.cream].forEach((col, i) => {
        for (let j = 0; j < 2; j++) {
          const x = (r() < 0.5 ? r.range(0.03, 0.22) : r.range(0.78, 0.97)) * w, y = top + r.range(0.15, 0.85) * (edge - top);
          clay(g, lumpPts(x, y, r.range(0.5, 1.1) * u, r.range(0.4, 0.8) * u, 30 + i * 3 + j, { n: 10 }), col, { seed: 30 + i * 3 + j, prints: 0, table: true });
        }
      });
      U = sv; POSE = svP;
    });
    ctx.drawImage(c, 0, 0);
  }

  // ---- layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    // base: where objects rest on the table
    return { F, u, P, tableTop: H * (P ? 0.47 : 0.55), tableEdge: H * (P ? 0.9 : 0.94), base: H * (P ? 0.75 : 0.8),
      toothS: (P ? 36 : 26) * u, word: (P ? 15 : 13) * u, label: (P ? 6.2 : 5.2) * u };
  }

  // ---- the frame
  function draw(ctx, W, H, tRaw) {
    const t = posed(tRaw); // on twos: nothing moves between poses
    const L = layout(W, H), u = L.u, P = L.P, S = L.F.safe;
    U = u; POSE = Math.floor(tRaw * FPS + 1e-6);
    set(ctx, W, H, L);
    dof(ctx, W, H, u); // only the set goes soft at the edges
    // landscape: the tooth steps right to give the key number the stage, then back
    const sl = (a) => Math.floor(B.prog(t, a, 0.4) * 4) / 4, tx = W / 2 + (P ? 0 : W * 0.17 * sl(4.05) * (1 - sl(5.95))), ts = L.toothS, base = L.base;

    // ---- beat 1: title letters, one per pose; knocked off at 1.75
    if (t < 2.6) {
      if (P) {
        clayWord(ctx, "WHY", W / 2, S.y + 20 * u, L.word * 1.2, t, 0.15, { gone: 1.75 });
        clayWord(ctx, "BRUSH?", W / 2, S.y + 39 * u, L.word * 1.2, t, 0.4, { gone: 1.8, shift: 2 });
      } else clayWord(ctx, "WHY BRUSH?", W / 2, H * 0.3, L.word * 1.15, t, 0.15, { gone: 1.75 });
    }
    // ---- the tooth: pops on at 0.9, stays; swells and brightens when clean
    const tp = popPose(t, 0.9); const clean = t >= 9.2;
    if (tp) {
      const sw = clean && t < 9.6 ? 1.08 : 1;
      const look = t < 2.5 ? [0, 0.2] : t < 4 ? [-0.6, 0.3] : t < 6.1 ? [0, -0.8] : t < 8.4 ? [0.7, 0] : [0, 0.1];
      placed(ctx, tx, base, 0, [tp[0] * sw, tp[1] * sw], () => tooth(ctx, 0, 0, ts, t, { look, smile: t < 2 ? 0.6 : t < 8.4 ? -0.4 : 1, color: clean ? "#fbf6ec" : t > 2 ? B.mix(PAL.cream, PAL.yellow, 0.18) : PAL.cream }));
    }
    // ---- germs on the tooth: pop on at 2.0+, knocked off one by one by the brush
    const gpos = [[-0.38, -1.25, 0.2], [0.35, -1.18, 0.17], [0.05, -0.55, 0.15]];
    gpos.forEach(([gx, gy, gr], i) => {
      const at = 2.0 + i * 0.17, off = 7.55 + i * 0.35;
      const ps = popPose(t, at); if (!ps) return;
      const kn = knock(t, off, i % 2 ? 1 : -1); if (kn.dy > H) return;
      placed(ctx, tx + gx * ts + kn.dx, base + gy * ts + kn.dy, kn.rot, ps, () => germ(ctx, 0, 0, gr * ts, 40 + i * 5, t > off ? [0, -1] : [i % 2 ? -0.6 : 0.6, 0.2]));
    });
    // ---- beat 2: candy, a clay coil to the germs, labels
    const cx = W * 0.2, cs = 10 * u;
    const cps = popPose(t, 2.45), ckn = knock(t, 4.0, -1);
    if (cps && ckn.dy < H) placed(ctx, cx + ckn.dx, base + ckn.dy, ckn.rot, cps, () => candy(ctx, 0, 0, cs, 50));
    slab(ctx, cx + (P ? 4 * u : 0), P ? base + 5 * u : base - cs * 1.9, "SUGAR", L.label * (P ? 0.75 : 1), t, 2.65, { seed: 61, gone: 4.05, dir: -1, rot: -0.05 });
    const coilPts = P ? B.quad(cx + cs * 0.4, base - cs * 1.0, cx - cs * 0.6, base - ts * 1.25, tx - ts * 0.6, base - ts * 1.3) : B.quad(cx + cs * 0.9, base - cs * 1.0, B.lerp(cx, tx, 0.45), base - ts * 1.55, tx - ts * 0.62, base - ts * 1.28);
    if (t < 4.0) coil(ctx, coilPts, Math.floor(B.prog(t, 2.85, 0.5) * 6) / 6, 3.4 * u, PAL.yellow, 70);
    const gx = P ? W * 0.55 : tx + ts * 1.25, gy = P ? S.y + 18 * u : base - ts * 1.25;
    slab(ctx, gx, gy, "GERMS", L.label * (P ? 1.25 : 1), t, 3.1, { seed: 62, gone: 3.95, rot: 0.05 });
    slab(ctx, gx, gy + L.label * (P ? 2.9 : 2.2), "MAKE ACID", L.label * (P ? 1.1 : 0.9), t, 3.4, { seed: 63, gone: 3.95, rot: -0.04, color: B.mix(PAL.red, PAL.cream, 0.55) });
    // ---- beat 3: 30 -> 120 seconds, each freshly sculpted, then "2" MINUTES + gold star
    if (t >= 4.1 && t < 6.4) {
      const ny = P ? S.y + 13 * u : H * 0.27, gone = 5.95, nx = P ? W / 2 : W * 0.3;
      const vals = ["30", "60", "90", "120"], at = [4.15, 4.5, 4.85, 5.2];
      let idx = -1;
      at.forEach((a, i) => (t >= a ? (idx = i) : 0));
      const final = t >= 5.55;
      const str = final ? "2" : vals[Math.max(0, idx)];
      const start = final ? 5.55 : at[Math.max(0, idx)];
      // the hero, bigger than the tooth
      const nz = L.word * (P ? 2.1 : str.length > 2 ? 3 : 4.2);
      clayWord(ctx, str, nx, P ? ny + L.word * 1.15 : H * 0.66, nz, t, start, { gone, colors: [PAL.blue, PAL.red, PAL.green], shift: idx });
      const sy = P ? ny + 29 * u : H * 0.79;
      if (!final) slab(ctx, nx, sy, "SECONDS", L.label * (P ? 1.2 : 1), t, 4.2, { seed: 64, rot: 0.03, gone: 5.5 });
      else {
        slab(ctx, nx, sy, "MINUTES", L.label * (P ? 1.2 : 1), t, 5.6, { seed: 65, rot: -0.04, gone });
        if (t < gone) star(ctx, nx + L.word * (P ? 1.25 : 1.9), P ? ny - L.word * 0.1 : H * 0.2, (P ? 6 : 5) * u, t, 5.7, 66);
      }
    }
    // ---- beat 4: the brush slides in in steps; three step slabs; scrubbing
    if (t >= 6.1 && t < 11.2) {
      const bs = (P ? 9 : 12) * u, bk = P ? 0.52 : 0.62;
      const slideIn = Math.floor(B.prog(t, 6.15, 0.5) * 5) / 5; // five visible steps
      let bx = B.lerp(W + bs * 3, tx + ts * bk, slideIn), by = base - ts * 0.75;
      if (t > 7.5 && t < 8.65) {
        // scrub across the tooth in small held steps (gentle circles)
        const k = (t - 7.5) * 6;
        bx = tx + ts * (bk + 0.08 * Math.cos(k * 1.3)); // beside the face
        by = base - ts * (1.0 + 0.2 * Math.sin(k * 1.3));
      } else if (t >= 8.65) bx = tx + ts * bk + shove(t, 10.15, 1);
      brush(ctx, bx, by, bs, t >= 6.95 ? B.clamp((t - 6.95) * 3) : 0, 80);
      // portrait: a big stacked list above the tooth; landscape: a column left of the tooth
      const steps = [["1 PEA OF PASTE", 6.55], ["2 GENTLE CIRCLES", 7.05], ["3 EVERY SIDE", 7.55]];
      steps.forEach(([txt, a], i) => slab(ctx, P ? W / 2 : W * 0.78, P ? S.y + 10 * u + i * 15.5 * u : H * 0.13 + i * L.label * 2.4, txt, L.label * 1.05, t, a, { seed: 90 + i, rot: [-0.03, 0.02, -0.02][i], gone: 8.4 + i * 0.05, dir: i % 2 ? 1 : -1 }));
    }
    // ---- beat 5: wrong (red cross, shake) and right (green tick, swell)
    if (t >= 8.4 && t < 11.0) {
      const kx = cx;
      const ps = popPose(t, 8.5), kn = { dx: shove(t, 10.1, -1) };
      if (ps) {
        placed(ctx, kx + kn.dx, base, 0, ps, () => candy(ctx, 0, 0, cs, 52));
        mark(ctx, kx + kn.dx, base - cs * 0.45, cs * 0.5, "cross", t, 8.75, 100);
      }
      slab(ctx, kx + kn.dx + (P ? 9 * u : 0), P ? base + 5 * u : base - cs * 1.9, "LESS SUGAR", L.label * (P ? 0.7 : 0.9), t, 8.9, { seed: 101, rot: 0.03, gone: 10.1, dir: -1 });
      mark(ctx, tx + ts * 0.58, base - ts * 1.45, ts * 0.17, "tick", t, 9.2, 102);
      slab(ctx, P ? tx : tx + ts * 1.05, P ? S.y + 26 * u : base - ts * 2.1, "CLEAN!", L.label * (P ? 1.9 : 1.1), t, 9.35, { seed: 103, rot: -0.04, color: B.mix(PAL.green, PAL.cream, 0.55), gone: 10.15 });
    }
    // ---- beat 6: close: "BRUSH 2X A DAY", letter by letter; gold star by the tooth
    if (t >= 10.3) {
      if (P) {
        clayWord(ctx, "BRUSH", W / 2, S.y + 20 * u, L.word * 1.2, t, 10.4);
        clayWord(ctx, "2X A DAY", W / 2, S.y + 39 * u, L.word * 1.05, t, 10.85, { shift: 3 });
      } else clayWord(ctx, "BRUSH 2X A DAY", W / 2, H * 0.28, L.word * 1.0, t, 10.4);
      star(ctx, tx + ts * 0.85, base - ts * 1.55, 4.5 * u, t, 11.4, 110);
    }

    // ---- finishing: warm grade, exposure flicker per pose, vignette, grain
    ctx.save();
    Object.assign(ctx, { globalCompositeOperation: "soft-light", globalAlpha: 0.5, fillStyle: B.linear(ctx, 0, 0, W, H, [[0, "#ffb98a"], [0.55, "#8a7c6e"], [1, "#4f6a8c"]]) });
    ctx.fillRect(0, 0, W, H); ctx.restore();
    const fl = (B.hash01("exposure", POSE) - 0.5) * 2;
    B.cover(ctx, W, H, fl > 0 ? "#fff4e6" : "#1c120b", Math.abs(fl) * 0.035);
    B.vignette(ctx, W, H, { color: PAL.brown, amount: 0.5, inner: 0.45 });
    B.grain(ctx, W, H, { amount: 0.07, t: tRaw, fps: FPS, seed: 8 });
  }
  /** Shallow depth of field: a blurred copy of the frame shows through toward the edges. */
  function dof(ctx, W, H, u) {
    const q = 3, w = Math.ceil(W / q), h = Math.ceil(H / q);
    const g = B.scratch("clay-dof", w, h);
    g.filter = `blur(${(0.8 * u / q).toFixed(2)}px)`;
    g.drawImage(ctx.canvas, 0, 0, w, h); g.filter = "none";
    g.globalCompositeOperation = "destination-in";
    g.fillStyle = B.radial(g, w / 2, h * 0.5, Math.min(w, h) * 0.35, Math.hypot(w, h) * 0.55, [B.rgba("#000", 0), B.rgba("#000", 1)]);
    g.fillRect(0, 0, w, h); ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = true; ctx.drawImage(g.canvas, 0, 0, W, H);
    ctx.restore();
  }

  // ---- sound
  SOUND.define("clay-plop", (v) => {
    v.tone({ f: 330, f2: 120, glide: 0.07, a: 0.002, len: 0.09, peak: 0.32 });
    v.noise({ filter: "lowpass", f: 700, a: 0.002, len: 0.05, peak: 0.12 });
  }, { verb: 0.12 });
  SOUND.define("clay-squelch", (v, o) => {
    const d = o.dur ?? 0.22;
    v.noise({ filter: "bandpass", q: 6, f: 380, fpath: [[d * 0.3, 900], [d * 0.6, 520], [d, 760]], a: 0.01, hold: d * 0.6, len: d * 0.4, peak: 0.3 });
  }, { verb: 0.1 });
  SOUND.define("clay-slap", (v) => {
    v.noise({ filter: "lowpass", f: 1200, a: 0.001, len: 0.06, peak: 0.4 });
    v.tone({ f: 160, f2: 90, glide: 0.05, a: 0.001, len: 0.07, peak: 0.25 });
  }, { verb: 0.12 });
  SOUND.define("clay-smear", (v, o) => {
    const d = o.dur ?? 0.4;
    v.noise({ brown: true, filter: "bandpass", q: 1.5, f: 500, f2: 800, glide: d, a: d * 0.3, hold: d * 0.4, len: d * 0.3, peak: 0.35 });
  }, { verb: 0.1 });

  // toy arp; plops per letter; squelches; slaps for the coil; thuds; smears
  function score(k) {
    k.bed("arp", 0, DUR, { notes: SOUND.scale("C4", "pent", 8), step: 0.25, gain: 0.35, pattern: [0, 2, 4, 2, 3, 1, 4, 2] });
    for (let i = 0; i < 9; i++) k.at(0.15 + i / FPS, "clay-plop", { pitch: (i % 4) * 2, gain: 0.7, pan: -0.5 + i / 9 });
    k.at(0.9, "clay-squelch", { gain: 0.9 }).at(1.15, "clay-plop", { pitch: -5 });
    k.at(1.95, "thud", { gain: 0.5 }).at(2.1, "thud", { gain: 0.4, pitch: -2 });
    [2.0, 2.17, 2.34].forEach((a, i) => k.at(a, "clay-squelch", { pitch: i * 3, dur: 0.18, gain: 0.7 }));
    k.at(2.45, "clay-plop", { pitch: -3 }).at(2.65, "clay-plop", { pitch: 2 });
    [2.85, 2.95, 3.1, 3.25].forEach((a) => k.at(a, "clay-slap", { gain: 0.6 }));
    k.at(3.1, "clay-plop", { pitch: 4 }).at(3.4, "clay-plop", { pitch: 0 }).at(3.45, "clay-squelch", { pitch: -4, gain: 0.5 });
    k.at(4.0, "clay-smear", { dur: 0.3, gain: 0.5 }).at(4.3, "thud", { gain: 0.5 });
    [4.15, 4.5, 4.85, 5.2].forEach((a, i) => k.at(a, "clay-plop", { pitch: i * 2 }).at(a + 1 / FPS, "clay-plop", { pitch: i * 2 + 3, gain: 0.6 }));
    k.at(5.55, "clay-squelch", { gain: 0.9 }).at(5.6, "clay-plop", { pitch: 5 });
    k.at(5.7, "marimba", { note: "G5", gain: 0.6 }).at(5.78, "marimba", { note: "C6", gain: 0.6 });
    k.at(5.95, "thud", { gain: 0.4 });
    k.at(6.15, "clay-smear", { dur: 0.5, gain: 0.7 });
    [6.55, 7.05, 7.55].forEach((a, i) => k.at(a, "clay-plop", { pitch: i * 2 }).at(a, "marimba", { note: ["C5", "E5", "G5"][i], gain: 0.35 }));
    k.at(6.95, "clay-squelch", { pitch: 4, gain: 0.8 });
    k.repeat(7.5, 0.26, 4, "clay-smear", { dur: 0.22, gain: 0.45, vary: 2 });
    [7.55, 7.9, 8.25].forEach((a) => k.at(a, "clay-squelch", { pitch: -2, dur: 0.12, gain: 0.5 }).at(a + 0.45, "thud", { gain: 0.35 }));
    k.at(8.5, "clay-plop").at(8.75, "clay-squelch", { pitch: -6, gain: 0.8 }).at(8.8, "error", { gain: 0.25 });
    k.at(9.2, "clay-squelch", { pitch: 5, gain: 0.8 }).at(9.25, "success", { gain: 0.45 });
    k.at(9.35, "clay-plop", { pitch: 3 });
    k.at(10.1, "clay-smear", { dur: 0.45, gain: 0.6 });
    for (let i = 0; i < 12; i++) k.at(10.4 + i / FPS, "clay-plop", { pitch: (i % 5) * 2, gain: 0.55 });
    k.at(11.4, "clay-squelch", { pitch: 6 }).at(11.45, "marimba", { note: "C6", gain: 0.5 }).at(11.55, "marimba", { note: "G6", gain: 0.45 });
  }

  Player.register({
    id: "clay", name: "Clay Stop-Motion", duration: DUR,
    fonts: { href: "https://fonts.googleapis.com/css2?family=Baloo+2:wght@800&display=swap", faces: ['800 20px "Baloo 2"'] },
    beats: BEATS, beatNames: ["Title", "Sugar and germs", "Key number", "Three steps", "Wrong and right", "Close"],
    stills: [1.4, 3.7, 5.85, 8.0, 9.6, 11.8],
    draw, score,
  });
})();
