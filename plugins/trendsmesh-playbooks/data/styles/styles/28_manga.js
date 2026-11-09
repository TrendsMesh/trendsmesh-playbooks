/* 28 Manga Panel - reference animation.
 * Topic (setting, replace it): "How does a volcano erupt?" - rising magma, growing gas, the rock giving way.
 * Rendering (keep it): a black-and-white comic page on off-white paper filling the frame; slanted panels with thick
 * borders and even gutters; brush-ink lines tapered at both ends, heavier on the shadow side; screentone dots fixed
 * to the page (never smooth fills); solid black for deep shadow; boiling focus lines; huge jagged sound effects
 * knocked out in white across panel edges; square narration boxes, oval balloons, emotion marks; one red spot.
 * Motion: panels drop in with a quick zoom and the page shakes; sound effects pop in oversized then tremble; a fresh
 * page slides over the last; the big beat gets a full-width panel and a flash. Text stays in the safe area.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { paper: "#fbfbf8", ink: "#0d0d0f", tone: "#8e8e92", light: "#d7d7da", red: "#d9322b" };
  const HAND = "Patrick Hand", SFX = "Archivo Black";
  const DUR = 13;
  const BEATS = [0, 2.2, 4.6, 6.8, 9.0, 11.0], LANDS = [0.05, 0.4, 2.38, 4.78, 5.35, 6.98, 7.55, 9.1, 9.18, 11.18, 11.55]; // panels landing

  // ---- manga ink helpers (reuse these)
  let U = 1, T = 0, PAGE_M = null, FR = null; // PAGE_M: the page transform, so screentone stays fixed to the paper
  /** Brush-ink line, tapered at both ends with a hair of wobble. w = max width in u. */
  function ink(g, pts, w, o = {}) {
    B.taperStroke(g, B.wobble(B.densify(pts, U), { amp: 0.12 * U, freq: 1.5, seed: o.seed ?? 1 }), {
      width: w * U, color: o.color || PAL.ink, taperIn: o.tin ?? 0.18, taperOut: o.tout ?? 0.22, rough: 0.3, roughScale: 6, seed: o.seed ?? 1, p: o.p,
    });
  }
  /** Closed contour: fill, then an ink outline, heavier on the shadow side. */
  function shape(g, pts, fill, w = 0.7, o = {}) {
    if (fill) {
      g.beginPath();
      B.poly(g, pts, true);
      g.fillStyle = fill;
      g.fill();
    }
    if (o.tone) toneIn(g, (c) => B.poly(c, pts, true), o.tone, bbox(pts));
    if (w > 0) {
      const ring = pts.concat([pts[0]]), n = ring.length;
      B.taperStroke(g, B.wobble(B.densify(ring, U), { amp: 0.1 * U, seed: o.seed ?? 3 }), { width: w * U, color: PAL.ink, taperIn: 0, taperOut: 0, rough: 0.35, seed: o.seed ?? 3 });
      const heavy = ring.filter((p, i) => i > n * 0.25 && i < n * 0.75);
      if (heavy.length > 2) ink(g, heavy, w * 1.9, { seed: (o.seed ?? 3) + 5, tin: 0.3, tout: 0.3 });
    }
  }
  /**
   * Screentone: a 45-degree dot grid fixed to the page, clipped to a path. o: { density 0..1 or fn(x, y), cell (u),
   * color }; bigger dots = denser tone. bb: the path's bounds (speed).
   */
  function toneIn(g, pathFn, o, bb) {
    const cell = (o.cell ?? 1.15) * U, dens = o.density ?? 0.4, fn = typeof dens === "function";
    g.save();
    g.beginPath();
    pathFn(g);
    g.clip();
    const M = g.getTransform(), W = g.canvas.width, H = g.canvas.height, R = Math.hypot(W, H);
    let xa = -R / 2, xb = R / 2, ya = -R / 2, yb = R / 2;
    if (bb) {
      const inv = PAGE_M.inverse(), xs = [], ys = [];
      for (const [px, py] of [[bb.x, bb.y], [bb.x + bb.w, bb.y], [bb.x, bb.y + bb.h], [bb.x + bb.w, bb.y + bb.h]]) {
        const d = M.transformPoint(new DOMPoint(px, py)), q = inv.transformPoint(new DOMPoint(B.clamp(d.x, 0, W), B.clamp(d.y, 0, H)));
        xs.push((q.x - W / 2 + q.y - H / 2) * Math.SQRT1_2);
        ys.push((q.y - H / 2 - q.x + W / 2) * Math.SQRT1_2);
      }
      const snap = (v) => -R / 2 + Math.floor((v + R / 2) / cell - 2) * cell;
      [xa, xb, ya, yb] = [snap(Math.min(...xs)), Math.max(...xs) + 2 * cell, snap(Math.min(...ys)), Math.max(...ys) + 2 * cell];
    }
    g.setTransform(PAGE_M);
    g.fillStyle = o.color || PAL.ink;
    g.translate(W / 2, H / 2);
    g.rotate(Math.PI / 4);
    g.beginPath();
    for (let y = ya; y < yb; y += cell)
      for (let x = xa; x < xb; x += cell) {
        let d = dens;
        if (fn) {
          const px = W / 2 + (x - y) * Math.SQRT1_2, py = H / 2 + (x + y) * Math.SQRT1_2;
          if (px < -cell || py < -cell || px > W + cell || py > H + cell) continue;
          d = dens(px, py);
        }
        if (d <= 0.03) continue;
        const r = cell * 0.56 * Math.sqrt(Math.min(1, d));
        g.moveTo(x + r, y);
        g.arc(x, y, r, 0, B.TAU);
      }
    g.fill();
    g.restore();
  }
  /** Focus lines converging on (cx, cy), redrawn every couple of frames (they boil). */
  function focusLines(g, cx, cy, rIn, rOut, n, seed, col = PAL.ink) {
    const r = B.rng(B.hash("focus", seed, B.boil(T, 12)));
    g.fillStyle = col;
    for (let i = 0; i < n; i++) {
      const a = r() * B.TAU, w = r.range(0.004, 0.02), ri = rIn * r.range(0.85, 1.35);
      g.beginPath();
      g.moveTo(cx + Math.cos(a - w) * rOut, cy + Math.sin(a - w) * rOut);
      g.lineTo(cx + Math.cos(a) * ri, cy + Math.sin(a) * ri);
      g.lineTo(cx + Math.cos(a + w) * rOut, cy + Math.sin(a + w) * rOut);
      g.fill();
    }
  }
  /**
   * Sound effect: huge jagged letters, each tilted and scaled differently, black in a white knockout with a thin
   * black edge; pops in oversized, then trembles.
   */
  function sfx(g, text, x, y, size, at, o = {}) {
    const dt = T - at;
    if (dt < 0) return;
    const s = dt < 0.12 ? B.lerp(1.7, 0.94, dt / 0.12) : 1 - 0.06 * Math.exp(-10 * (dt - 0.12)) * Math.cos(30 * (dt - 0.12));
    g.save();
    g.translate(x, y);
    g.rotate(o.rot ?? -0.12);
    g.scale(s, s);
    g.font = B.font(size, SFX, 400);
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.lineJoin = "miter";
    const chars = [...text], ws = chars.map((c) => g.measureText(c).width * 0.92), tot = ws.reduce((a, b) => a + b, 0);
    let xx = -tot / 2;
    chars.forEach((c, i) => {
      const r = B.rng(B.hash(text, i)), sh = B.shake(T, size * 0.025, i + (o.seed ?? 0), 14);
      g.save();
      g.translate(xx + ws[i] / 2 + sh[0], r.range(-0.12, 0.12) * size + sh[1]);
      g.rotate(r.range(-0.2, 0.2));
      const k = r.range(0.85, 1.2);
      g.scale(k, k * r.range(1.0, 1.25));
      g.strokeStyle = PAL.ink;
      g.lineWidth = size * 0.34;
      g.strokeText(c, 0, 0);
      g.strokeStyle = PAL.paper;
      g.lineWidth = size * 0.24;
      g.strokeText(c, 0, 0);
      g.fillStyle = o.color || PAL.ink;
      g.fillText(c, 0, 0);
      g.restore();
      xx += ws[i];
    });
    g.restore();
  }
  /** Square narration box: inked border, hand lettering in capitals. Returns its height. */
  function narration(g, x, y, w, text, size, p, o = {}) {
    if (p <= 0) return 0;
    const m = B.measureText(g, text.toUpperCase(), { size, minSize: size, family: o.family || HAND, weight: 400, maxW: w - size * 1.2, lineH: 1.05 });
    const h = m.height + size * 1.0;
    g.save();
    g.translate(x, y);
    g.scale(B.ease.outBack(B.clamp(p), 2), B.ease.outBack(B.clamp(p), 2));
    g.fillStyle = PAL.paper;
    g.fillRect(-w / 2, -h / 2, w, h);
    const e = [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2], [-w / 2, -h / 2]];
    for (let i = 0; i < 4; i++) ink(g, [e[i], e[i + 1]], i % 3 ? 1 : 0.55, { seed: 70 + i, tin: 0.05, tout: 0.05 }); // brush border, heavy in shadow
    B.text(g, text.toUpperCase(), 0, 0, { size, minSize: size, family: o.family || HAND, weight: 400, color: o.color || PAL.ink, maxW: w - size * 1.2, lineH: 1.05 });
    g.restore();
    return h;
  }
  /** Hand-drawn oval speech balloon with a small tail toward (tx, ty). */
  function balloon(g, cx, cy, rx, ry, tx, ty, text, size, p) {
    if (p <= 0) return;
    const s = B.ease.outBack(B.clamp(p), 2.2), a = Math.atan2(ty - cy, tx - cx), pts = [];
    for (let i = 0; i <= 40; i++) {
      const th = a + 0.25 + (i / 40) * (B.TAU - 0.5);
      pts.push([cx + Math.cos(th) * rx * s, cy + Math.sin(th) * ry * s]);
    }
    pts.push([B.lerp(cx, tx, s), B.lerp(cy, ty, s)]);
    shape(g, pts, PAL.paper, 0.5, { seed: 9 });
    B.text(g, text, cx, cy, { size: size * s, minSize: size * s, family: HAND, weight: 400, color: PAL.ink, maxW: rx * 1.6 * s, lineH: 1.05 });
  }
  /** Heavy arrow a -> b, drawn on to p: black body, white inner stroke. */
  function boldArrow(g, [a, b], w, p) {
    if (p <= 0.02) return;
    const L = B.dist(a[0], a[1], b[0], b[1]) * p, hl = Math.min(w * 1.6, L * 0.5);
    const poly = [[0, -w / 2], [L - hl, -w / 2], [L - hl, -w * 1.1], [L, 0], [L - hl, w * 1.1], [L - hl, w / 2], [0, w / 2]];
    const path = () => {
      g.beginPath();
      B.poly(g, poly, true);
    };
    g.save();
    g.translate(a[0], a[1]);
    g.rotate(Math.atan2(b[1] - a[1], b[0] - a[0]));
    path();
    g.fillStyle = PAL.ink;
    g.fill();
    g.save();
    g.clip();
    g.strokeStyle = PAL.paper;
    g.lineWidth = w * 0.42;
    path();
    g.stroke();
    g.restore();
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.35 * U;
    path();
    g.stroke();
    g.restore();
  }
  function vein(g, x, y, r) {
    g.strokeStyle = PAL.ink;
    g.lineWidth = r * 0.28;
    g.lineCap = "round";
    for (let i = 0; i < 4; i++) {
      const a = (i * Math.PI) / 2 + Math.PI / 4;
      g.beginPath();
      g.arc(x + Math.cos(a) * r, y + Math.sin(a) * r, r * 0.7, a + Math.PI * 0.75, a + Math.PI * 1.25);
      g.stroke();
    }
  }
  function sweat(g, x, y, r) {
    const pts = [[x, y - r * 1.8], ...B.arcPts(x, y, r, -0.35, Math.PI + 0.35, 14)];
    shape(g, pts, PAL.paper, 0.35, { seed: 4 });
  }
  /** Step number in a safe panel corner. */
  function cornerNum(g, poly, n, size, bl) {
    const tr = poly[1], br = poly[2], [x, y] = bl ? [poly[3][0], poly[3][1] - size] : tr[1] >= FR.safe.y ? [tr[0] - size, tr[1]] : [br[0] - size, br[1] - size];
    g.fillStyle = PAL.ink;
    g.fillRect(x, y, size, size);
    g.strokeStyle = PAL.paper;
    g.lineWidth = 0.5 * U;
    g.strokeRect(x + 0.6 * U, y + 0.6 * U, size - 1.2 * U, size - 1.2 * U);
    B.text(g, n, x + size / 2, y + size * 0.53, { size: size * 0.8, family: SFX, weight: 400, color: PAL.paper });
  }
  const bbox = (pts) => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    const w = Math.max(...xs) - x, h = Math.max(...ys) - y;
    return { x, y, w, h, cx: x + w / 2, cy: y + h / 2, d: Math.hypot(w, h) };
  };
  const wx = (port, land) => FR.W * (FR.portrait ? port : land), hy = (port, land) => FR.H * (FR.portrait ? port : land);
  const pu = (port, land) => (FR.portrait ? port : land) * U;
  const circ = (x, y, r, n = 26) => B.arcPts(x, y, r, 0, B.TAU, n).slice(0, -1);

  // ---- subjects (the setting: replace these)
  // volcano c: { cx, peak, ground, base and cw (half widths), chY, rx, ry (chamber) }
  /** Flank height at x: concave, steep under the summit. */
  function flankY(c, x) {
    const d = Math.abs(x - c.cx), h = c.ground - c.peak;
    if (d <= c.cw) return c.peak + h * 0.05 * (1 - (d / c.cw) ** 2);
    return c.ground - h * Math.pow(B.clamp(1 - (d - c.cw) / (c.base - c.cw)), 1.7);
  }
  const vol = (cx, peak, ground, base, cw, chY, rx, ry) => ({ cx, peak, ground, base, cw, chY, rx, ry });
  const conePts = (c) => Array.from({ length: 91 }, (_, i) => {
    const x = c.cx - c.base + (i / 90) * 2 * c.base;
    return [x, flankY(c, x)];
  });
  /** Outside view: toned flanks and gullies, smoke, lava runs. */
  function volcanoOut(g, c, smoke = 0, lava = 0) {
    const cone = conePts(c), h = c.ground - c.peak;
    if (smoke > 0) puff(g, c.cx + c.cw * 0.4, c.peak - h * 0.28 * smoke, c.base * 0.34 * smoke, 23);
    // erupting: a black silhouette so the white-hot lava blazes
    shape(g, cone, lava > 0 ? PAL.ink : PAL.paper, 0.8, { seed: 21, tone: lava > 0 ? null : { density: (x, y) => (x < c.cx - c.cw ? 0.08 + 0.14 * B.clamp((y - c.peak) / h) : B.clamp(0.4 + 0.5 * (x - c.cx) / c.base)), cell: 1.15 } });
    B.clip(g, (q) => B.poly(q, cone, true), () => {
      for (let i = 0; i < 13; i++) {
        const k = (i / 12) * 2 - 1, x0 = c.cx + k * c.cw * 0.8, x1 = c.cx + k * c.base * 0.8;
        ink(g, B.quad(x0, c.peak + h * 0.06, B.lerp(x0, x1, 0.25), c.peak + h * 0.55, x1, c.ground, 12), lava > 0 ? 0.3 : k > 0 ? 0.75 : 0.35, { seed: 30 + i, tin: 0.4, tout: 0.1, color: lava > 0 ? PAL.tone : PAL.ink });
      }
    });
    // white-hot lava running down the flanks: paper-white streams with an ink edge
    if (lava > 0) [[-0.5, -0.4], [0.1, 0.06], [0.7, 0.42]].forEach(([a, b], i) => {
      const x0 = c.cx + a * c.cw, x1 = c.cx + b * c.base;
      const path = B.wobble(B.quad(x0, flankY(c, x0) + U, B.lerp(x0, x1, 0.3), c.peak + h * 0.5, x1, c.ground - h * 0.04, 20), { amp: 0.7 * U, seed: 70 + i });
      ink(g, path, 4.6, { p: B.clamp(lava * (1.15 - i * 0.12)), seed: 70 + i, tin: 0.02, tout: 0.45 });
      ink(g, path, 2.9, { p: B.clamp(lava * (1.15 - i * 0.12)), seed: 80 + i, color: PAL.paper, tin: 0.02, tout: 0.55 });
    });
  }
  function puff(g, cx, cy, r, seed) {
    const rr = B.rng(seed);
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * B.TAU, x = cx + Math.cos(a) * r * 0.55, y = cy + Math.sin(a) * r * 0.3, rad = r * rr.range(0.32, 0.48);
      shape(g, circ(x, y, rad, 24), PAL.paper, 0.45, { seed: seed + i, tone: { density: (px, py) => B.clamp(((py - cy) / r) * 0.7 + 0.15), cell: 1 } });
    }
  }
  /**
   * Eruption column: cauliflower lobes of ash, toned darkest underneath, black at the vent. k: how far it has risen.
   */
  function plume(g, x, y, hgt, wid, k, t) {
    if (k <= 0) return;
    const n = 22, lobes = [];
    for (let i = 0; i < n; i++) {
      const f = i / (n - 1), grow = B.clamp((k * 1.08 - f) * 5);
      if (grow <= 0) continue;
      const r = wid * (0.13 + 0.27 * f) * (0.4 + 0.6 * grow), side = [0, -1, 1, -0.5, 0.5][i % 5];
      const lx = x + B.noise1(i * 0.9 + t * 0.5, 6) * wid * 0.1 * f + side * r * (0.45 + f * 0.9);
      const ly = y - hgt * f * B.ease.outCubic(B.clamp(k)) - Math.sin(t * 2.4 + i) * r * 0.05;
      lobes.push([lx, ly, r, f]);
    }
    lobes.reverse().forEach(([lx, ly, r, f], i) => {
      const pts = circ(lx, ly, r, 40).map(([px, py], j) => { const k = 1 + 0.07 * Math.sin(j * 0.94 + i * 2.1); return [lx + (px - lx) * k, ly + (py - ly) * k]; });
      if (f < 0.12) shape(g, pts, PAL.ink, 0.5, { seed: i });
      else shape(g, pts, PAL.paper, 0.7, { seed: i, tone: { density: (px, py) => B.clamp(0.75 * ((py - ly) / r + 0.15) + 0.35 * ((px - lx) / r)), cell: 1.05 } });
    });
  }
  /** Rocks flung out on arcs, with speed lines. */
  function bombs(g, x, y, sp, lt, seed) {
    const r = B.rng(seed);
    for (let i = 0; i < 14; i++) {
      const an = -Math.PI / 2 + r.range(-1.15, 1.15), v = r.range(0.45, 1) * sp, d = r(), rs = r.range(0.9, 2.2) * U;
      const ph = B.clamp((lt - 0.35 - d * 0.35) / 1.3);
      if (ph <= 0) continue;
      const pos = (q) => [x + Math.cos(an) * v * q, y + Math.sin(an) * v * q + 0.55 * sp * q * q];
      const [px, py] = pos(ph), [qx, qy] = pos(Math.max(0, ph - 0.08));
      for (const o of [-0.5, 0.5]) ink(g, [[qx + o * rs, qy], [px + o * rs * 0.6, py]], 0.3, { seed: i });
      shape(g, circ(px, py, rs, 6), PAL.ink, 0.2, { seed: i });
    }
  }
  /**
   * Cutaway: the cone sliced over toned strata, chamber, winding vent. level: magma in the vent; bubbles: gas in
   * the chamber; pressure: strain lines and cracks (all 0..1).
   */
  function cutaway(g, c, level, bubbles, pressure = 0) {
    const h = c.ground - c.peak, X0 = Math.max(c.cx - c.base * 1.6, -0.05 * FR.W), X1 = Math.min(c.cx + c.base * 1.6, 1.05 * FR.W), bot = c.chY + c.ry * 6;
    const bandH = c.ry * 0.85, wav = (x) => Math.sin(x / (9 * U)) * 1.3 * U;
    const dens = [0.16, 0.38, 0.24, 0.5, 0.3, 0.44];
    shape(g, [[X0, c.ground], [X1, c.ground], [X1, bot], [X0, bot]], PAL.paper, 0, { tone: { density: (x, y) => dens[(Math.floor((y - c.ground + wav(x)) / bandH) % 6 + 6) % 6], cell: 1.1 } });
    // strata in brush ink: broken, tapered strokes of varied weight
    for (let i = 1; i < 9; i++)
      for (let k = 0; k < 4; k++) {
        const a = B.lerp(X0, X1, (k + 0.04 * B.hash01("sa", i, k)) / 4), b = B.lerp(X0, X1, (k + 0.92 + 0.06 * B.hash01("sb", i, k)) / 4);
        ink(g, B.densify([[a, 0], [b, 0]], 3 * U).map(([x]) => [x, c.ground + i * bandH - wav(x)]), 0.45 + 0.8 * B.hash01("sw", i, k), { seed: 50 + i * 4 + k, tin: 0.3, tout: 0.3 });
      }
    ink(g, [[X0, c.ground], [X1, c.ground]], 0.6, { seed: 49 });
    // the cone, sliced: old lava and ash layers run parallel to the flanks
    const cone = conePts(c), layerH = h * 0.11;
    if (c.base < FR.W * 2) shape(g, cone, PAL.paper, 0.8, { seed: 41, tone: { density: (x, y) => (Math.floor((y - flankY(c, x)) / layerH) % 2 ? 0.3 : 0.1), cell: 1.1 } });
    if (c.base < FR.W * 2) B.clip(g, (q) => B.poly(q, cone, true), () => {
      for (let k = 1; k < 10; k++) ink(g, cone.map(([x, y]) => [x, y + k * layerH]), 0.35 + 0.35 * (k % 3), { seed: 60 + k, tin: 0.35, tout: 0.35 });
    });
    // the vent: winding up from the chamber, wider low down
    const top = flankY(c, c.cx), vx = (y) => c.cx + Math.sin(((y - top) / (c.chY - top)) * 5.5) * c.cw * 0.3;
    const vw = (y) => c.cw * (0.4 + 0.3 * B.clamp((y - top) / (c.chY - top)));
    const side = (s, y0 = top) => Array.from({ length: 31 }, (_, i) => {
      const y = B.lerp(y0, c.chY, i / 30);
      return [vx(y) + s * vw(y), y];
    });
    shape(g, side(-1).concat(side(1).reverse()), PAL.paper, 0.5, { seed: 42, tone: { density: 0.12, cell: 0.9 } });
    const ly = B.lerp(c.chY - c.ry * 0.5, top, level);
    if (level > 0) {
      shape(g, side(-1, ly).concat(side(1, ly).reverse()), PAL.ink, 0.4, { seed: 43 });
      ink(g, [[vx(ly) - vw(ly) * 0.6, ly + 0.7 * U], [vx(ly) + vw(ly) * 0.6, ly + 0.7 * U]], 0.45, { color: PAL.paper, seed: 46 });
    }
    if (pressure > 0) {
      // strain lines (boiling) and cracks
      const r = B.rng(B.hash("strain", B.boil(T, 12)));
      for (let i = 0; i < 20; i++) {
        const a = (i / 20) * B.TAU + r.range(-0.1, 0.1), k1 = 1.12 + r.range(0.15, 0.4) * pressure;
        ink(g, [[c.cx + Math.cos(a) * c.rx * 1.1, c.chY + Math.sin(a) * c.ry * 1.1], [c.cx + Math.cos(a) * c.rx * k1, c.chY + Math.sin(a) * c.ry * k1]], 0.55, { seed: i });
      }
      for (let i = 0; i < 4; i++) {
        const a = -Math.PI / 2 + (i - 1.5) * 0.7, pts = [];
        let x = c.cx + Math.cos(a) * c.rx * 0.9, y = c.chY + Math.sin(a) * c.ry * 0.9;
        for (let q = 0; q < 6; q++) {
          pts.push([x, y]);
          x += Math.cos(a) * c.rx * 0.13 + (B.hash01("ck", i, q) - 0.5) * 4 * U;
          y += Math.sin(a) * c.ry * 0.3 + (B.hash01("cy", i, q) - 0.5) * 2 * U;
        }
        ink(g, pts, 0.6, { p: pressure, seed: 90 + i, tin: 0.05, tout: 0.6 });
      }
    }
    // the chamber: black melt, white gloss, gas bubbles
    const ch = Array.from({ length: 40 }, (_, i) => {
      const a = (i / 40) * B.TAU;
      return [c.cx + Math.cos(a) * c.rx * (1 + 0.08 * B.noise1(i * 0.6, 2)), c.chY + Math.sin(a) * c.ry * (1 + 0.1 * B.noise1(i * 0.6, 3))];
    });
    shape(g, ch, PAL.ink, 0.9, { seed: 44 });
    ink(g, B.arcPts(c.cx, c.chY, 1, Math.PI * 1.08, Math.PI * 1.42, 10).map(([x, y]) => [c.cx + (x - c.cx) * c.rx * 0.82, c.chY + (y - c.chY) * c.ry * 0.68]), 0.7, { color: PAL.paper, seed: 45 });
    if (bubbles > 0) {
      const rr = B.rng(45);
      g.fillStyle = PAL.paper;
      for (let i = 0; i < 13; i++) {
        const bx = c.cx + rr.range(-0.72, 0.72) * c.rx, by = c.chY + rr.range(-0.35, 0.5) * c.ry - bubbles * rr() * c.ry * 0.25;
        const br = Math.min(c.ry * 0.42, (0.35 + rr() * 0.6) * U * (0.6 + 2.6 * bubbles) * (c.ry / (7 * U)));
        g.beginPath();
        B.circle(g, bx, by, br);
        g.fill();
      }
      for (let i = 0; i < 4 && level > 0.2; i++) {
        const y = B.lerp(ly, c.chY - c.ry, 0.2 + i * 0.22);
        g.beginPath();
        B.circle(g, vx(y) + (i % 2 ? 0.3 : -0.3) * vw(y), y, vw(y) * 0.3 * (0.5 + bubbles));
        g.fill();
      }
    }
    return { top, ly, vx, vw };
  }

  // ---- pages and panels
  /** Panel polygons; gutters come from insetting each side of a slanted cut. */
  const quad = (a, b, c, d) => [a, b, c, d];
  function pages(F) {
    const W = F.W, H = F.H, P = F.portrait, u = F.u;
    const L = wx(0.04, 0.035), R = W - L, t0 = hy(0.045, 0.06), b0 = hy(0.955, 0.94);
    const g = pu(1.6, 1.4), sl = pu(3, 4);
    const hcut = (y) => [quad([L, t0], [R, t0], [R, y - sl - g], [L, y + sl - g]), quad([L, y + sl + g], [R, y - sl + g], [R, b0], [L, b0])];
    const vcut = (x) => [quad([L, t0], [x + sl - g, t0], [x - sl - g, b0], [L, b0]), quad([x + sl + g, t0], [R, t0], [R, b0], [x - sl + g, b0])];
    return { title: P ? hcut(H * 0.56) : vcut(L + (R - L) * 0.6), full: [quad([L, t0], [R, t0], [R, b0], [L, b0])], two: P ? hcut(H * 0.5) : vcut(W * 0.5), strip: hcut(H * 0.25) };
  }
  /** A panel: quick zoom-in drop, content clipped to it, then the thick border. */
  function panel(g, poly, at, t, paint) {
    const k = B.prog(t, at, 0.22, "outCubic");
    if (k <= 0) return;
    const bb = bbox(poly), s = B.lerp(1.12, 1, k);
    g.save();
    g.globalAlpha = Math.min(1, k * 1.6);
    g.translate(bb.cx, bb.cy);
    g.scale(s, s);
    g.translate(-bb.cx, -bb.cy);
    g.save();
    g.beginPath();
    B.poly(g, poly, true);
    g.fillStyle = PAL.paper;
    g.fill();
    g.clip();
    paint(bb);
    g.restore();
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.75 * U;
    g.lineJoin = "miter";
    g.beginPath();
    B.poly(g, poly, true);
    g.stroke();
    g.restore();
  }
  const bgTone = (bb, density, cell = 1.2) => (g) => toneIn(g, (c) => c.rect(bb.x, bb.y, bb.w, bb.h), { density, cell }, bb);
  /** Hand-lettered caption, knocked out. */
  const caption = (g, text, x, y, size, a) => B.text(g, text, x, y, { size, minSize: size, family: HAND, color: PAL.ink, stroke: PAL.paper, strokeW: 1.4 * U, alpha: a });
  /** Narration label with an inked leader line. */
  function label(g, x, y, w, text, size, lt, at, to) {
    if (lt < at) return;
    const p = B.prog(lt, at, 0.2);
    ink(g, [[x, y], to], 0.65, { seed: 60, p, tin: 0, tout: 0 });
    if (p >= 1) shape(g, circ(to[0], to[1], 1.3 * U, 12), PAL.paper, 0.5); // the leader ends on a ringed dot, on the thing it names
    narration(g, x, y, w, text, size, B.prog(lt, at + 0.1, 0.25));
  }

  /** Each page paints its panels; lt = time since the page arrived. */
  const PAGES = [
    // title
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, S = F.safe, W = F.W, H = F.H, [a, b] = pg.title;
      panel(g, a, 0.05, t, (bb) => {
        bgTone(bb, (x, y) => B.clamp(0.55 - ((y - bb.y) / bb.h) * 0.5))(g);
        const c = vol(bb.cx, bb.y + bb.h * (P ? 0.42 : 0.5), bb.y + bb.h + 2 * u, bb.w * (P ? 0.6 : 0.5), bb.w * 0.065);
        focusLines(g, c.cx, c.peak - bb.h * 0.08, bb.w * 0.12, bb.d, 70, 1);
        volcanoOut(g, c, 1 + 0.06 * Math.sin(t * 3));
        sweat(g, c.cx + bb.w * 0.17, c.peak + bb.h * 0.06, 1.8 * u);
      });
      panel(g, b, 0.4, t, (bb) => {
        const cy = P ? H * 0.66 : bb.cy - 6 * u, sz = pu(7.2, 6.4);
        focusLines(g, bb.cx, cy, Math.min(bb.w, bb.h) * 0.4, bb.d, 80, 4);
        const nh = narration(g, bb.cx, cy, bb.w * 0.84, "How does a volcano erupt?", sz, B.prog(t, 0.55, 0.3), { family: SFX });
        caption(g, "A short story of heat and pressure", bb.cx, cy + nh / 2 + pu(5, 5.5), pu(5, 4.8), B.prog(t, 0.9, 0.3));
      });
      const sz = pu(13, 11);
      sfx(g, "RUMBLE", P ? W * 0.44 : W * 0.3, S.y + sz * 1.1, sz, 1.25, { rot: -0.1 });
    },
    // diagram: the cutaway with labels and a bold arrow up the vent
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, W = F.W, H = F.H, lt = t - BEATS[1];
      panel(g, pg.full[0], BEATS[1] + 0.18, t, (bb) => {
        bgTone(bb, 0.1)(g);
        const c = P ? vol(W * 0.5, H * 0.2, H * 0.43, W * 0.62, W * 0.06, H * 0.645, W * 0.3, H * 0.06)
          : vol(W * 0.42, H * 0.17, H * 0.5, W * 0.38, W * 0.035, H * 0.76, W * 0.2, H * 0.1);
        const v = cutaway(g, c, 0.4, 0.3), sz = pu(5.2, 4.8), lw = pu(36, 31);
        const ay = [c.chY - c.ry * 1.3, c.ground - (c.ground - c.peak) * 0.35], ax = c.cx + (P ? -0.1 : 0.08) * W;
        boldArrow(g, [[ax, ay[0]], [ax, ay[1]]], pu(4.2, 3.4), B.prog(lt, 1.5, 0.4, "outCubic"));
        label(g, wx(0.24, 0.17), hy(0.175, 0.16), lw, "Crater", sz, lt, 1.25, [c.cx - c.cw * 0.6, flankY(c, c.cx - c.cw * 0.6)]);
        const vy = hy(0.33, 0.32);
        label(g, wx(0.78, 0.72), vy, lw, "Vent", sz, lt, 1.0, [v.vx(vy), vy]); // on the conduit itself
        label(g, wx(0.5, 0.86), hy(0.765, 0.8), pu(48, 31), "Magma chamber", sz, lt, 0.7, P ? [c.cx, c.chY + c.ry] : [c.cx + c.rx, c.chY]);
        if (lt > 1.6) narration(g, P ? W * 0.2 : W * 0.72, hy(0.5, 0.55), lw, "Magma rises", sz, B.prog(lt, 1.7, 0.25));
      });
    },
    // key number: lava close-up, a counter in red
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, S = F.safe, W = F.W, H = F.H, [a, b] = pg.two, lt = t - BEATS[2];
      panel(g, a, BEATS[2] + 0.18, t, (bb) => {
        g.fillStyle = PAL.ink;
        g.fillRect(bb.x, bb.y, bb.w, bb.h);
        // cracked crust: a jittered grid of plates whose seams glow white-hot
        const cs = pu(9, 7), pt = (i, j) => [bb.x + i * cs + (B.hash01("cx", i, j) - 0.5) * cs * 0.8, bb.y + j * cs + (B.hash01("cy", i, j) - 0.5) * cs * 0.8];
        for (let i = -1; i < bb.w / cs + 1; i++)
          for (let j = -1; j < bb.h / cs + 1; j++) {
            const p0 = pt(i, j), w = 0.25 + 0.6 * B.hash01("cw", i, j), o = { color: PAL.paper, seed: i * 31 + j, tin: 0.3, tout: 0.3 };
            ink(g, [p0, pt(i + 1, j)], w, o);
            if (B.hash01("cv", i, j) < 0.7) ink(g, [p0, pt(i, j + 1)], w, o);
          }
        bgTone(bb, (x, y) => B.clamp(0.6 - Math.hypot(x - bb.cx, y - bb.cy) / bb.w), 1.3)(g);
      });
      panel(g, b, BEATS[2] + 0.75, t, (bb) => {
        const cy = P ? H * 0.62 : bb.cy - 4 * u;
        focusLines(g, bb.cx, cy, Math.min(bb.w, bb.h) * 0.42, bb.d, 90, 2);
        const v = B.counter(B.prog(lt, 0.95, 0.9), 1200, { ease: "outCubic" });
        narration(g, bb.cx, cy, pu(80, 56), v + "°C", pu(13, 10), B.prog(lt, 0.85, 0.2), { family: SFX, color: PAL.red });
        caption(g, "Lava can be this hot", bb.cx, cy + pu(17, 14), pu(5.2, 4.4), B.prog(lt, 1.6, 0.3));
      });
      const sz = pu(10, 8);
      sfx(g, "HISSS", P ? W * 0.6 : W * 0.33, P ? S.y + sz * 1.15 : H * 0.28, sz, BEATS[2] + 0.5, { rot: 0.12, seed: 3 });
    },
    // steps 1-2: two panels, a sound effect crossing between them
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, W = F.W, H = F.H, [a, b] = pg.two, lt = t - BEATS[3], sz = pu(5.2, 4.8), ns = pu(11, 9);
      panel(g, a, BEATS[3] + 0.18, t, (bb) => {
        bgTone(bb, 0.1)(g);
        const c = P ? vol(W * 0.5, H * 0.19, H * 0.31, W * 0.5, W * 0.05, H * 0.41, W * 0.24, H * 0.035)
          : vol(W * 0.25, H * 0.3, H * 0.5, W * 0.3, W * 0.03, H * 0.76, W * 0.15, H * 0.08);
        cutaway(g, c, B.prog(lt, 0.4, 0.9, "outCubic") * 0.85, 0.2);
        const ax = c.cx + (P ? 0.1 : 0.09) * W;
        boldArrow(g, [[ax, c.chY - c.ry * 1.2], [ax, c.peak + (c.ground - c.peak) * 0.25]], pu(3.8, 3), B.prog(lt, 0.5, 0.4));
        narration(g, wx(0.25, 0.21), hy(0.2, 0.15), pu(40, 38), "Hot magma rises" /* clear of the crater */, sz, B.prog(lt, 0.45, 0.25));
        cornerNum(g, a, "1", ns, P); // portrait: bottom left, away from step 2's number
      });
      panel(g, b, BEATS[3] + 0.75, t, (bb) => {
        // close-up on the chamber: bubbles swell, the rock strains and cracks
        const k = B.prog(lt, 0.85, 0.9);
        bgTone(bb, 0.12)(g);
        const c = P ? vol(W * 0.68, bb.y - H, bb.y - 4 * u, W * 3, W * 0.07, H * 0.72, W * 0.36, H * 0.085)
          : vol(W * 0.81, -H, bb.y - 4 * u, W * 3, W * 0.04, H * 0.66, W * 0.17, H * 0.15);
        cutaway(g, c, 0.85, 0.3 + 0.7 * k, k);
        if (k > 0.5) vein(g, c.cx - c.rx * 0.55, c.chY - c.ry * 1.45, 2.2 * u);
        if (k > 0.7) sweat(g, c.cx + c.rx * 0.6, c.chY - c.ry * 1.35, 1.8 * u);
        narration(g, wx(0.29, 0.64), hy(0.61, 0.18), pu(52, 42), "Gas bubbles swell: pressure builds", sz, B.prog(lt, 0.9, 0.25));
        cornerNum(g, b, "2", ns);
      });
      sfx(g, "RUMBLE", W * 0.5, H * 0.5, pu(12, 10), BEATS[3] + 1.0, { rot: P ? -0.08 : -0.3, seed: 5 });
    },
    // step 3, the key moment: big panel, focus lines, eruption, flash
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, W = F.W, H = F.H, lt = t - BEATS[4], ns = pu(11, 9);
      const [sa, sb] = pg.strip, big = P ? sb : pg.full[0];
      if (P) panel(g, sa, BEATS[4] + 0.1, t, (bb) => {
        // the summit rock splitting: white cracks in black, white speed lines
        g.fillStyle = PAL.ink;
        g.fillRect(bb.x, bb.y, bb.w, bb.h);
        focusLines(g, bb.cx, bb.cy + bb.h * 0.2, bb.w * 0.16, bb.d, 60, 8, PAL.paper);
        const pts = Array.from({ length: 12 }, (_, i) => [bb.x + (i / 11) * bb.w, bb.cy + bb.h * 0.2 + (B.hash01("crk", i) - 0.5) * bb.h * 0.35]);
        ink(g, pts, 2.2, { color: PAL.paper, seed: 3, tin: 0.1, tout: 0.1 });
        [2, 5, 8].forEach((i, k) => ink(g, [pts[i], [pts[i][0] + (k - 1) * 6 * u, pts[i][1] - bb.h * 0.3]], 1, { color: PAL.paper, seed: 4 + k }));
        cornerNum(g, sa, "3", ns);
      });
      panel(g, big, BEATS[4] + 0.18, t, (bb) => {
        const c = P ? vol(W * 0.5, H * 0.6, bb.y + bb.h + 2 * u, W * 0.62, W * 0.07) : vol(W * 0.5, H * 0.6, bb.y + bb.h + 2 * u, W * 0.36, W * 0.04);
        const top = flankY(c, c.cx);
        focusLines(g, c.cx, top - bb.h * 0.15, bb.w * 0.1, bb.d, 120, 3);
        plume(g, c.cx, top, top - hy(0.31, 0.2), wx(0.42, 0.21), B.prog(lt, 0.3, 0.8, "outCubic"), t);
        bombs(g, c.cx, top, bb.h * 0.5, lt, 81);
        volcanoOut(g, c, 0, B.prog(lt, 0.6, 1.2));
        if (!P) cornerNum(g, big, "3", ns);
        narration(g, wx(0.32, 0.2), hy(0.74, 0.8), pu(54, 44), "The rock gives way: eruption!", pu(5.2, 4.8), B.prog(lt, 1.0, 0.25));
      });
      sfx(g, "KA-BOOM!", wx(0.45, 0.3), hy(0.255, 0.3), pu(13, 11), BEATS[4] + 0.45, { rot: -0.1, seed: 7 });
    },
    // close: calm page, the volcano smoking, a summing-up box and a balloon
    (g, F, t, pg) => {
      const P = F.portrait, u = F.u, H = F.H, [a, b] = pg.title, lt = t - BEATS[5];
      panel(g, a, BEATS[5] + 0.18, t, (bb) => {
        bgTone(bb, (x, y) => B.clamp(0.1 + ((y - bb.y) / bb.h) * 0.4), 1.3)(g);
        const c = vol(bb.cx + bb.w * 0.08, bb.y + bb.h * (P ? 0.5 : 0.55), bb.y + bb.h + 2 * u, bb.w * (P ? 0.55 : 0.45), bb.w * 0.06);
        volcanoOut(g, c, 0.9 + 0.1 * Math.sin(t * 2));
        balloon(g, bb.x + bb.w * 0.3, P ? H * 0.21 : bb.y + bb.h * 0.22, pu(20, 15), pu(7.5, 6.5), c.cx - c.cw, c.peak - 2 * u, "Phew...", pu(5.2, 4.4), B.prog(lt, 0.7, 0.25));
      });
      panel(g, b, BEATS[5] + 0.55, t, (bb) => {
        const cy = P ? H * 0.655 : bb.cy - 8 * u;
        bgTone(bb, (x, y) => B.clamp(((y - cy) / bb.h) * 1.2), 1.3)(g);
        const nh = narration(g, bb.cx, cy, bb.w * 0.84, "Rising magma + growing gas = eruption", pu(6, 4.6), B.prog(lt, 0.7, 0.3), { family: SFX });
        caption(g, "- the end -", bb.cx, cy + nh / 2 + pu(6, 6.5), pu(5.8, 5), B.prog(lt, 1.2, 0.3));
      });
    },
  ];

  // ---- frame: pages slide over each other, landings shake, flashes
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    U = F.u;
    T = t;
    FR = F;
    const pg = pages(F);
    let amp = 0;
    for (const at of LANDS) amp += Math.max(0, 1 - (t - at - 0.2) / 0.25) * (t > at + 0.2 ? 1 : 0);
    amp += 2.5 * Math.max(0, 1 - Math.abs(t - 9.75) / 0.35);
    const [sx, sy] = B.shake(t, amp * 0.6 * U, 11, 25);
    const paper = () => B.paper(ctx, W, H, { color: PAL.paper, seed: 28, mottle: 0.05, fibers: 0.2, specks: 0.15, tooth: 0.05 });
    paper();
    const i = Math.max(0, BEATS.filter((b) => t >= b).length - 1);
    const slide = i > 0 ? B.prog(t, BEATS[i], 0.32, "inOutCubic") : 1;
    const paintPage = (k, dx) => {
      ctx.save();
      ctx.translate(dx + sx, sy);
      PAGE_M = new DOMMatrix([1, 0, 0, 1, 0, 0]).translate(dx, 0); // tone is fixed to the paper, not to the shake
      PAGES[k](ctx, F, t, pg);
      ctx.restore();
    };
    if (slide < 1) paintPage(i - 1, 0);
    // the fresh page slides over the last
    const dx = -(1 - slide) * W;
    if (slide < 1) {
      ctx.save();
      ctx.fillStyle = B.linear(ctx, dx + W, 0, dx + W + 4 * U, 0, ["rgba(0,0,0,0.35)", "rgba(0,0,0,0)"]);
      ctx.fillRect(dx + W, 0, 4 * U, H);
      ctx.beginPath();
      ctx.rect(dx, 0, W, H);
      ctx.clip();
      paper();
      paintPage(i, dx);
      ctx.restore();
    } else paintPage(i, 0);
    // impact flashes: white on the eruption, black snap on the number's landing
    B.cover(ctx, W, H, "#ffffff", 0.9 * Math.max(0, 1 - Math.abs(t - 9.72) / 0.12));
    B.cover(ctx, W, H, PAL.ink, 0.6 * Math.max(0, 1 - Math.abs(t - 5.4) / 0.06));
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12, mode: "multiply", seed: 28 });
  }

  // ---- sound
  SOUND.define("manga-slam", (v) => {
    // a panel slamming in: air whoosh into a low thump
    v.noise({ filter: "bandpass", f: 600, f2: 2400, glide: 0.1, q: 0.8, a: 0.06, len: 0.04, peak: 0.25 });
    v.tone({ f: 120, f2: 55, glide: 0.15, at: 0.1, a: 0.002, len: 0.2, peak: 0.6 });
  }, { verb: 0.15 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.4 });
    LANDS.forEach((at, i) => k.at(at, "manga-slam", { gain: 0.8, pitch: (i % 3) - 1 }));
    BEATS.slice(1).forEach((b) => k.at(b, "snap", { gain: 0.8 }).at(b + 0.02, "paper", { dur: 0.25, gain: 0.5 }));
    k.at(1.2, "boom", { dur: 1.0, gain: 0.5 }).at(1.25, "ding", { gain: 0.4 }).repeat(1.3, 0.05, 14, "drum", { gain: 0.18, vary: 1 });
    k.at(3.0, "pop").at(3.3, "pop", { pitch: 2 }).at(3.55, "pop", { pitch: 4 }).at(3.75, "whoosh", { dur: 0.4, gain: 0.5 });
    k.at(5.1, "breath", { dur: 0.6, gain: 0.5 }).repeat(5.55, 0.05, 16, "tick", { gain: 0.35, vary: 1 }).at(6.45, "chime", { note: "A5", gain: 0.3 });
    k.at(7.0, "riser", { dur: 0.7, gain: 0.4 }).at(7.8, "boom", { dur: 1.2, gain: 0.6 }).repeat(7.8, 0.045, 18, "drum", { gain: 0.2, vary: 2 });
    k.at(9.0, "powerup", { gain: 0.35 }).at(9.7, "impact").at(9.7, "boom", { dur: 1.6, gain: 0.9 }).at(9.72, "crumple", { dur: 0.6, gain: 0.5 });
    k.at(11.75, "pop", { gain: 0.5 }).at(12.0, "breath", { dur: 0.8, gain: 0.4 }).at(12.4, "chord", { notes: ["C5", "E5", "G5", "C6"], strum: 0.05, gain: 0.45 });
  }

  Player.register({
    id: "manga",
    name: "Manga Panel",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Patrick+Hand&family=Archivo+Black&display=swap",
      faces: ['400 20px "Patrick Hand"', '400 20px "Archivo Black"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.9, 4.3, 6.6, 8.75, 10.6, 12.8],
    draw,
    score,
  });
})();
