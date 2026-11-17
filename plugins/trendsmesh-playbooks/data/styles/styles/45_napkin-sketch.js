/* 45 Napkin Sketch - reference animation.
 * Topic (setting, replace it): "When does a coffee cart break even?" - $3,000 of costs a month; $4 a cup minus $1.50
 * of ingredients leaves $2.50, so 3,000 / 2.50 = 1,200 cups a month, about 40 a day.
 * Rendering (keep it): a soft white napkin on a café table, seen close; the camera slides patch to patch as the sketch
 * fills it. Embossed quilt dots, a dotted border, fold creases, wrinkles, a crumpled edge, coffee rings. One blue
 * ballpoint: pressure-varied line, tissue bleed, pale skips, blobs at both ends, slight boil; quick boxes, open loops,
 * two-stroke arrow heads, zigzag shading, a first try struck out. Caveat handwriting, Nanum Pen Script notes, a pen
 * riding the line being drawn.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    napkin: "#fbfaf6",
    emboss: "#d6d1c4",
    ink: "#2443b5",
    deep: "#14266f", // ink blobs and the densest line
    stain: "#a8784a",
    table: "#4e3426",
    grain: "#6e4a35",
  };
  const HAND = "Caveat", NOTE = "Nanum Pen Script";
  const DUR = 14;
  const BEATS = [0, 2.2, 4.6, 7.0, 9.9, 11.9];
  // [column, row] patch of the napkin for each beat, walked as a snake
  const ORDER = { land: [[0, 0], [1, 0], [1, 1], [0, 1], [0, 2], [1, 2]], port: [[0, 0], [1, 0], [2, 0], [2, 1], [1, 1], [0, 1]] };

  // ------------------------------------------------------------------ pen-shape generators (local px around a patch centre)
  /** n + 1 points from f(k, i), k = 0..1. */
  const seq = (n, f) => Array.from({ length: n + 1 }, (_, i) => f(i / n, i));
  /** A quick box in one go: corners overshoot, it ends past where it began. */
  function quickBox(x, y, w, h, u) {
    return [[x - 0.9 * u, y + 0.5 * u], [x + w + 0.8 * u, y - 0.4 * u], [x + w - 0.3 * u, y + h + 0.7 * u], [x - 0.4 * u, y + h - 0.2 * u], [x + 0.4 * u, y - 1.4 * u]];
  }
  /** A loop: a bit more than one turn, tilted, the ends never meeting. */
  function loop(cx, cy, rx, ry, tilt = -0.08, turns = 1.12) {
    const c = Math.cos(tilt), s = Math.sin(tilt);
    return seq(90, (k) => {
      const a = -2.4 + k * turns * B.TAU, r = 0.97 + 0.06 * k, x = Math.cos(a) * rx * r, y = Math.sin(a) * ry * r;
      return [cx + x * c - y * s, cy + x * s + y * c];
    });
  }
  /** An underline that sags and flicks up at the end. */
  const underline = (x1, x2, y, u) => B.quad(x1, y, (x1 + x2) / 2, y + 0.9 * u, x2, y - 0.3 * u, 20).concat([[x2 + 1.6 * u, y - 1.5 * u]]);
  /** An arrow as one pen movement: the shaft, then tip -> barb -> tip -> other barb. */
  function arrowPts(shaft, u, head = 3.2) {
    const tip = shaft[shaft.length - 1], from = shaft[Math.max(0, shaft.length - 4)];
    const a = Math.atan2(tip[1] - from[1], tip[0] - from[0]), hl = head * u;
    return shaft.concat([[tip[0] - Math.cos(a - 0.5) * hl, tip[1] - Math.sin(a - 0.5) * hl], tip, [tip[0] - Math.cos(a + 0.45) * hl * 0.9, tip[1] - Math.sin(a + 0.45) * hl * 0.9]]);
  }
  /** Scribbled shading: one slanted zigzag stroke across a box. */
  const zigzag = (x, y, w, h, n, slant = 0.35) => seq(n, (k, i) => (i % 2 ? [x + k * w + h * slant, y] : [x + k * w, y + h]));
  const star = (cx, cy, r) => seq(5, (k, i) => [cx + Math.cos(-Math.PI / 2 + i * 0.8 * Math.PI) * r, cy + Math.sin(-Math.PI / 2 + i * 0.8 * Math.PI) * r]);
  const squiggle = (x, y, len, amp) => seq(16, (k, i) => [x + Math.sin(i * 0.8) * amp, y - k * len]);
  /** A takeaway cup doodle: body, lid, sleeve, optional shading and steam. */
  function cupPaths(cx, cy, h, u, o = {}) {
    const tw = 0.34 * h, bw = 0.25 * h, top = cy - 0.3 * h, bot = cy + 0.42 * h, y1 = cy - 0.02 * h, y2 = cy + 0.2 * h;
    const xAt = (y) => B.lerp(tw, bw, (y - top) / (bot - top));
    const paths = [
      [[cx - tw, top], [cx - bw, bot], [cx + bw, bot + 0.01 * h], [cx + tw, top]],
      quickBox(cx - tw - 0.05 * h, top - 0.11 * h, 2 * tw + 0.1 * h, 0.11 * h, u * 0.6),
      B.quad(cx - tw * 0.8, top - 0.11 * h, cx, top - 0.24 * h, cx + tw * 0.8, top - 0.11 * h, 16),
      [[cx - xAt(y1), y1], [cx + xAt(y1), y1 - 0.01 * h]],
      [[cx - xAt(y2), y2], [cx + xAt(y2), y2 + 0.005 * h]],
    ];
    if (o.hatch) paths.push(zigzag(cx - xAt(y1) + 0.03 * h, y1 + 0.02 * h, 2 * xAt(y1) - 0.14 * h, y2 - y1 - 0.04 * h, 12, 0.3));
    if (o.steam) paths.push(squiggle(cx - 0.1 * h, top - 0.27 * h, o.steam * h, 0.05 * h), squiggle(cx + 0.12 * h, top - 0.25 * h, o.steam * h * 0.8, 0.045 * h));
    return paths;
  }
  /** A coffee cart doodle: counter, wheels, a scalloped awning on poles. */
  function cartPaths(cx, cy, s, u) {
    const S = (a, b) => [cx + a * s, cy + b * s];
    const aw = [S(-1.12, -0.95)];
    for (let i = 0; i < 5; i++) aw.push(...B.quad(...S(-1.12 + i * 0.448, -0.95), ...S(-0.896 + i * 0.448, -0.72), ...S(-0.672 + i * 0.448, -0.95), 8).slice(1));
    aw.push(S(0.9, -1.25), S(-0.9, -1.25), S(-1.12, -0.95));
    return [quickBox(cx - s, cy - 0.25 * s, 2 * s, 0.75 * s, u * 0.7), loop(...S(-0.6, 0.68), 0.19 * s, 0.19 * s, 0, 1.05), loop(...S(0.6, 0.68), 0.19 * s, 0.19 * s, 0, 1.05),
      [S(-0.92, -0.25), S(-0.92, -0.95)], [S(0.92, -0.25), S(0.92, -0.95)], aw, zigzag(...S(-0.85, -1.18), 1.7 * s, 0.2 * s, 14, 0.4)];
  }

  // ------------------------------------------------------------------ the timeline: every stroke and word, in writing order
  const cache = new Map();
  /** Positions per aspect, and the start/duration of every pen item (the score reads the same list). */
  function build(W, H) {
    const key = W + "x" + H;
    if (cache.has(key)) return cache.get(key);
    const F = B.frame(W, H), u = F.u, P = F.portrait, hw = W / 2, hh = H / 2;
    const SX = W * 1.14, SY = H * 1.14;
    const centers = (P ? ORDER.port : ORDER.land).map(([c, r]) => [hw + c * SX, hh + r * SY]);
    const cols = P ? 3 : 2, rows = P ? 2 : 3, ex = W * 0.035, ey = H * (P ? 0.05 : 0.045);
    const nap = { x: ex, y: ey, r: W + (cols - 1) * SX - ex, b: H + (rows - 1) * SY - ey };
    const LW = (P ? 0.5 : 0.52) * u;
    const items = [];
    let R = 0, T = 0, beatFirst = 0;
    const C = () => centers[R];
    function path(pts, dur, o = {}) {
      const [cx, cy] = C();
      let w = B.densify(pts.map(([x, y]) => [cx + x, cy + y]), Math.max(2, u * 0.8));
      w = B.wobble(w, { amp: u * (o.shake ?? 0.3), freq: 100 / (26 * u), seed: items.length * 13 + 5 });
      items.push({ k: "path", pts: w, len: B.pathLength(w), start: T, dur, width: (o.w ?? 1) * LW, seed: items.length + 1, tap: o.tap });
      T += dur + (o.gap ?? 0.05);
    }
    function text(str, x, y, size, o = {}) {
      const [cx, cy] = C();
      const it = { k: "text", str, x: cx + x, y: cy + y, size, align: o.align || "center", family: o.note ? NOTE : HAND, weight: o.note ? 400 : o.weight ?? 600, maxW: o.maxW ?? F.safe.w, start: T, dur: o.dur ?? 0.08 + str.length * 0.021, seed: items.length + 1 };
      items.push(it);
      T += it.dur + (o.gap ?? 0.07);
      return it;
    }
    function scratch(ref, dur) {
      items.push({ k: "scratch", ref, start: T, dur, width: LW * 1.1, seed: items.length + 1 });
      T += dur + 0.06;
    }
    /** Start a beat on its patch; fit() squeezes its items into the writing window. */
    function beat(i, region) {
      R = region;
      beatFirst = items.length;
      T = BEATS[i] + (i ? 0.42 : 0.4);
    }
    function fit(endAt) {
      const list = items.slice(beatFirst);
      if (!list.length) return;
      const t0 = list[0].start, last = list[list.length - 1], end = last.start + last.dur;
      if (end <= endAt) return;
      const k = (endAt - t0) / (end - t0);
      list.forEach((it) => { it.start = t0 + (it.start - t0) * k; it.dur *= k; });
    }
    const L = (land, port) => (P ? port : land);

    const LA = L({ align: "left" }, {}), head = { ...LA, weight: 700 };

    // ---- beat 1: the question, double underlined, and a cup
    beat(0, 0);
    if (P) ["When does a", "coffee cart"].forEach((s, i) => text(s, 0, (-0.58 + i * 0.15) * hh, 13 * u, head));
    else text("When does a coffee cart", -0.86 * hw, -0.42 * hh, 10.5 * u, { ...head, maxW: 0.98 * hw });
    text("break even?", L(-0.86, 0) * hw, L(-0.08, -0.28) * hh, L(13, 14) * u, head);
    path(underline(L(-0.88, -0.62) * hw, L(-0.2, 0.6) * hw, L(0.08, -0.19) * hh, u), 0.12, { w: 1.2 });
    path(underline(L(-0.84, -0.5) * hw, L(-0.26, 0.66) * hw, L(0.13, -0.165) * hh, u), 0.1);
    cupPaths(L(0.6, 0) * hw, L(0.14, 0.17) * hh, L(40, 38) * u, u, { hatch: true, steam: L(0.3, 0.22) }).forEach((p) => path(p, 0.07, { gap: 0.02 }));
    text("a quick sum on a napkin", L(-0.86, 0) * hw, L(0.42, 0.5) * hh, L(8.5, 10) * u, { ...LA, note: true });
    fit(BEATS[1] - 0.25);

    // ---- beat 2: where the $4 goes - a cup, an arrow fork, two boxes
    beat(1, 1);
    text("Where the $4 goes", L(-0.86, 0) * hw, L(-0.74, -0.64) * hh, 8 * u, head);
    path(underline(L(-0.87, -0.45) * hw, L(-0.2, 0.45) * hw, L(-0.6, -0.58) * hh, u), 0.1);
    const cupX = L(-0.55, 0) * hw, cupY = L(0.14, -0.36) * hh;
    cupPaths(cupX, cupY, L(34, 30) * u, u).forEach((p) => path(p, 0.06, { gap: 0.02 }));
    text("$4", cupX, cupY + L(0.01, 0.025) * hh, L(9.5, 10) * u, { weight: 700 });
    const boxes = L([[0, -0.62, 0.88, 0.5], [0, 0.14, 0.88, 0.5]], [[-0.82, -0.06, 1.36, 0.25], [-0.55, 0.31, 1.37, 0.25]]);
    const forks = P
      ? [B.quad(-0.22 * hw, -0.22 * hh, -0.42 * hw, -0.18 * hh, -0.46 * hw, -0.1 * hh, 16), B.cubic(0.24 * hw, -0.24 * hh, 0.75 * hw, -0.2 * hh, 0.9 * hw, 0.05 * hh, 0.7 * hw, 0.28 * hh, 24)]
      : [B.quad(-0.33 * hw, -0.06 * hh, -0.15 * hw, -0.35 * hh, -0.03 * hw, -0.38 * hh, 16), B.quad(-0.33 * hw, 0.2 * hh, -0.15 * hw, 0.42 * hh, -0.03 * hw, 0.4 * hh, 16)];
    [["$1.50 cost", "beans, milk, cup"], ["$2.50 margin", "pays the rent"]].forEach(([a, b], i) => {
      const [bx, by, bw, bh] = boxes[i], tx = (bx + L(0.06, 0.08)) * hw;
      path(arrowPts(forks[i], u), 0.16);
      path(quickBox(bx * hw, by * hh, bw * hw, bh * hh, u), 0.21);
      text(a, tx, (by + L(0.14, 0.075)) * hh, L(7, 7.5) * u, { align: "left", weight: 700 });
      text(b, tx, (by + L(0.35, 0.18)) * hh, L(5.8, 6) * u, { align: "left" });
    });
    path(zigzag(L(0.04, -0.5) * hw, L(0.67, 0.57) * hh, L(0.86, 1.33) * hw, L(0.04, 0.015) * hh, L(24, 26), 0.6), 0.12, { w: 0.8 });
    fit(BEATS[2] - 0.25);

    // ---- beat 3: the key number - a wrong first try struck out, then 1,200 looped
    beat(2, 2);
    const kx = L(-0.86, 0) * hw, nx = L(-0.42, 0) * hw, ny = L(0.4, 0.08) * hh, dx = L(-0.08, 0.72) * hw, dy = L(0.18, -0.06) * hh;
    text("Costs: $3,000 a month", kx, L(-0.74, -0.64) * hh, L(6.5, 7) * u, LA);
    scratch(text("3,000 ÷ 4 = 750?", kx, L(-0.42, -0.45) * hh, L(7, 8) * u, head), 0.2);
    text("no! use the margin", L(0.02, 0) * hw, L(-0.42, -0.33) * hh, L(8.5, 9.5) * u, { ...LA, note: true });
    text("3,000 ÷ 2.50 =", kx, L(-0.1, -0.19) * hh, L(7, 8) * u, head);
    text("1,200", nx, ny, L(19, 25) * u, { weight: 700, dur: 0.3 });
    path(loop(nx, ny + 0.008 * hh, L(0.36, 0.74) * hw, L(0.3, 0.17) * hh, L(-0.05, -0.06), 1.18), 0.2, { w: 1.15 });
    path([[dx, dy], [dx + 0.001 * hw, dy + 0.001 * hh]], 0.04, { w: 1.6, tap: true });
    text("cups a month", L(0.04, 0) * hw, L(0.42, 0.4) * hh, L(8, 8.5) * u, head);
    fit(BEATS[3] - 0.25);

    // ---- beat 4: three steps, each number looped and ticked
    beat(3, 3);
    text("How to work it out", L(-0.86, 0) * hw, L(-0.74, -0.64) * hh, 8 * u, head);
    path(underline(L(-0.87, -0.5) * hw, L(-0.22, 0.5) * hw, L(-0.6, -0.58) * hh, u), 0.1);
    L([["Add up monthly costs"], ["Price - cost = margin"], ["Costs ÷ margin"]], [["Add up the", "monthly costs"], ["Price - cost", "= margin"], ["Costs ÷", "margin"]]).forEach((lines, i) => {
      const y = L(-0.3 + i * 0.36, -0.45 + i * 0.27) * hh, sx = L(-0.79, -0.76) * hw, sy = y + L(0, 0.04) * hh;
      text(String(i + 1), sx, sy, L(7, 8) * u, { weight: 700, dur: 0.08, gap: 0.02 });
      path(loop(sx, sy + L(0.01, 0.005) * hh, L(0.065, 0.12) * hw, L(0.11, 0.055) * hh, 0, 1.08), 0.1);
      lines.forEach((s, j) => text(s, L(-0.66, -0.6) * hw, y + j * 0.09 * hh, 7 * u, { align: "left" }));
      path(L([[0.3, 0.02], [0.34, 0.1], [0.44, -0.1]], [[0.6, 0.06], [0.66, 0.1], [0.8, -0.01]]).map(([a, b]) => [a * hw, y + b * hh]), 0.07, { w: 1.2 });
    });
    text("= break-even", L(0.5, 0) * hw, L(0.72, 0.45) * hh, L(7.5, 9) * u, { weight: 700 });
    if (P) path(quickBox(-0.56 * hw, 0.38 * hh, 1.12 * hw, 0.14 * hh, u), 0.16);
    fit(BEATS[4] - 0.25);

    // ---- beat 5: per day - 1,200 / 30 = 40, with a scribble-shaded shadow and a cart
    beat(4, 4);
    const fx = L(-0.55, 0) * hw;
    text("1,200 ÷ 30 days", L(-0.86, 0) * hw, L(-0.74, -0.63) * hh, L(7.5, 8) * u, head);
    text("about", fx, L(-0.4, -0.5) * hh, L(8, 9) * u, { note: true });
    text("40", fx, L(0, -0.3) * hh, L(22, 26) * u, { weight: 700, dur: 0.16 });
    path(zigzag(fx - L(0.2, 0.3) * hw, L(0.26, -0.165) * hh, L(0.4, 0.62) * hw, L(0.05, 0.03) * hh, L(16, 18), 0.5), 0.1, { w: 0.8 });
    text("cups a day", fx, L(0.48, -0.08) * hh, L(8, 9) * u, { weight: 700 });
    cartPaths(L(0.45, 0) * hw, L(0.14, 0.34) * hh, L(0.3, 0.42) * hw, u).forEach((p) => path(p, 0.06, { gap: 0.015 }));
    fit(BEATS[5] - 0.25);

    // ---- beat 6: close - from cup 41 it is profit, rising scribbled bars
    beat(5, 5);
    const cx6 = L(-0.22, 0) * hw;
    if (P) ["From cup 41", "each day,"].forEach((s, i) => text(s, 0, (-0.62 + i * 0.14) * hh, 11 * u, { weight: 700 }));
    else text("From cup 41 each day,", cx6, -0.5 * hh, 9.5 * u, { weight: 700, maxW: 1.2 * hw });
    text("it's profit!", cx6, L(-0.12, -0.31) * hh, L(13, 14) * u, { weight: 700 });
    path(underline(L(-0.6, -0.55) * hw, L(0.14, 0.55) * hw, L(0.1, -0.2) * hh, u), 0.1, { w: 1.2 });
    path(underline(L(-0.52, -0.45) * hw, L(0.2, 0.62) * hw, L(0.15, -0.175) * hh, u), 0.08);
    text("+$2.50 a cup", cx6, L(0.42, -0.05) * hh, L(9, 11) * u, { note: true });
    path(star(L(-0.66, -0.7) * hw, L(0.42, -0.05) * hh, L(2.8, 3.4) * u), 0.08);
    path(star(L(0.22, 0.7) * hw, L(0.4, -0.06) * hh, L(2.4, 3) * u), 0.08);
    const bw = L(0.11, 0.26) * hw, base = L(0.62, 0.5) * hh;
    L([0.25, 0.5, 0.8], [0.12, 0.22, 0.34]).forEach((f, i) => {
      const x = L(0.42, -0.5) * hw + i * (bw + L(0.05, 0.11) * hw), hgt = f * hh;
      path(quickBox(x, base - hgt, bw, hgt, u * 0.7), 0.08, { gap: 0.02 });
      path(zigzag(x + bw * 0.12, base - hgt * 0.92, bw * 0.7, hgt * 0.86, Math.max(4, Math.round(hgt / (2.4 * u))), 0.2), 0.08, { w: 0.75, gap: 0.02 });
    });
    const q = L([0.36, 0.3, 0.5, -0.3, 0.88, -0.42], [-0.62, 0.3, -0.1, 0.2, 0.56, 0.06]).map((v, i) => v * (i % 2 ? hh : hw));
    path(arrowPts(B.quad(...q, 18), u, L(3.2, 3.6)), 0.12);
    fit(DUR - 0.75);

    items.sort((a, b) => a.start - b.start);
    // napkin details: crumpled edge, wrinkles, coffee rings (world px)
    const edge = [], rr = B.rng("napkin-edge");
    const corners = [[nap.x, nap.y], [nap.r, nap.y], [nap.r, nap.b], [nap.x, nap.b], [nap.x, nap.y]];
    for (let c = 0; c < 4; c++) {
      const [x1, y1] = corners[c], [x2, y2] = corners[c + 1], l = Math.hypot(x2 - x1, y2 - y1), n = Math.ceil(l / (2 * u));
      for (let i = 0; i < n; i++) {
        const s = edge.length, d = (B.noise1(s * 0.09, 3) * 1.1 + B.noise1(s * 0.6, 9) * 0.35) * u;
        edge.push([B.lerp(x1, x2, i / n) + ((y2 - y1) / l) * d, B.lerp(y1, y2, i / n) - ((x2 - x1) / l) * d]);
      }
    }
    const wrinkles = [];
    for (let i = 0; i < 26; i++) {
      const x = rr.range(nap.x, nap.r), y = rr.range(nap.y, nap.b), a = rr.range(0, Math.PI), l = rr.range(8, 26) * u;
      wrinkles.push(B.arcBetween(x, y, x + Math.cos(a) * l, y + Math.sin(a) * l, rr.range(-0.12, 0.12), 14));
    }
    const ringAt = (reg, lx, ly, r) => [centers[reg][0] + lx, centers[reg][1] + ly, r];
    const rings = P ? [ringAt(0, 0.6 * hw, -0.8 * hh, 14 * u), ringAt(3, 0.62 * hw, 0.78 * hh, 12 * u)] : [ringAt(0, 0.76 * hw, -0.66 * hh, 11 * u), ringAt(3, 0.74 * hw, 0.12 * hh, 12 * u)];
    const G = { F, u, P, W, H, hw, hh, centers, nap, items, edge, wrinkles, rings };
    cache.set(key, G);
    return G;
  }

  // ------------------------------------------------------------------ napkin and table
  /** The quilt: a diamond lattice of embossed dots and faint seams, as a tile. */
  function quiltPattern(ctx, u) {
    const c = Math.round(4.4 * u);
    const tile = B.layer("napkin-quilt", c, c, (g, w) => {
      g.fillStyle = PAL.napkin;
      g.fillRect(0, 0, w, w);
      g.lineWidth = 0.14 * u;
      g.strokeStyle = B.rgba(PAL.emboss, 0.35);
      g.beginPath();
      g.moveTo(0, 0); g.lineTo(w, w); g.moveTo(w, 0); g.lineTo(0, w);
      g.stroke();
      for (const [px, py] of [[w / 2, w / 2], [0, 0], [w, 0], [0, w], [w, w]]) {
        [[0.12, 0.14, 0.36, B.rgba("#b9b2a2", 0.42)], [-0.1, -0.1, 0.3, "rgba(255,255,255,0.95)"], [0, 0, 0.22, B.mix(PAL.napkin, PAL.emboss, 0.35)]].forEach(([dx, dy, r, c]) => {
          g.fillStyle = c;
          g.beginPath(); B.circle(g, px + dx * u, py + dy * u, r * u); g.fill();
        });
      }
    });
    return ctx.createPattern(tile, "repeat");
  }
  function woodPattern(ctx, u) {
    const tw = Math.round(90 * u), th = Math.round(36 * u);
    const tile = B.layer("napkin-wood", tw, th, (g, w, h) => {
      g.fillStyle = PAL.table;
      g.fillRect(0, 0, w, h);
      const r = B.rng("wood");
      for (let i = 0; i < 46; i++) {
        const y0 = r() * h, k = r.int(1, 3), amp = r.range(0.3, 1.6) * u, ph = r() * B.TAU;
        g.strokeStyle = i % 3 ? B.rgba(PAL.grain, r.range(0.25, 0.6)) : B.rgba("#2c1d14", r.range(0.25, 0.5));
        g.lineWidth = r.range(0.15, 0.9) * u;
        for (const oy of [-h, 0, h]) {
          g.beginPath();
          for (let x = 0; x <= w; x += u * 2) {
            const y = y0 + oy + Math.sin((x / w) * B.TAU * k + ph) * amp;
            x ? g.lineTo(x, y) : g.moveTo(x, y);
          }
          g.stroke();
        }
      }
    });
    return ctx.createPattern(tile, "repeat");
  }
  function napkinPath(ctx, G) {
    ctx.beginPath();
    B.poly(ctx, G.edge, true);
  }
  /** A fold crease: soft shade on one side, a dark line and a bright ridge. */
  function crease(ctx, G, vertical, at, s) {
    const u = G.u, N = G.nap;
    const a0 = vertical ? N.y : N.x, a1 = vertical ? N.b : N.r;
    const pts = seq(Math.ceil((a1 - a0) / (6 * u)), (k) => {
      const a = B.lerp(a0, a1, k), d = B.noise1(a / (60 * u), at * 0.01) * 0.8 * u;
      return vertical ? [at + d, a] : [a, at + d];
    });
    ctx.save();
    ctx.fillStyle = B.linear(ctx, ...(vertical ? [at - 9 * u, 0, at, 0] : [0, at - 9 * u, 0, at]), ["rgba(90,80,60,0)", B.rgba("#5a503c", 0.06 * s)]);
    if (vertical) ctx.fillRect(at - 9 * u, N.y, 9 * u, N.b - N.y);
    else ctx.fillRect(N.x, at - 9 * u, N.r - N.x, 9 * u);
    ctx.lineCap = "round";
    B.strokeReveal(ctx, pts, 1, { width: 0.32 * u, color: B.rgba("#8a806a", 0.32 * s) });
    B.strokeReveal(ctx, pts.map(([x, y]) => (vertical ? [x + 0.38 * u, y] : [x, y + 0.38 * u])), 1, { width: 0.4 * u, color: B.rgba("#ffffff", 0.9 * s) });
    ctx.restore();
  }
  function coffeeRing(ctx, x, y, r, u, seed) {
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const ring = seq(80, (k, i) => {
      const a = k * B.TAU, rad = r * (1 + 0.025 * B.noise1(i * 0.3, seed) + 0.012 * Math.sin(a * 3));
      return [x + Math.cos(a) * rad, y + Math.sin(a) * rad];
    });
    ctx.fillStyle = B.rgba(PAL.stain, 0.07); // the faint wash inside
    ctx.beginPath(); B.poly(ctx, ring, true); ctx.fill();
    ctx.lineCap = "round";
    for (let i = 1; i < ring.length; i++) {
      const k = 0.5 + 0.5 * Math.sin((i / 80) * B.TAU + seed) , a = 0.12 + 0.4 * k * (0.7 + 0.3 * B.noise1(i * 0.5, seed + 4));
      ctx.strokeStyle = B.rgba(PAL.stain, a);
      ctx.lineWidth = (0.35 + 0.75 * k) * u;
      ctx.beginPath(); ctx.moveTo(ring[i - 1][0], ring[i - 1][1]); ctx.lineTo(ring[i][0], ring[i][1]); ctx.stroke();
    }
    ctx.strokeStyle = B.rgba(PAL.stain, 0.16); // put down again
    ctx.lineWidth = 0.4 * u;
    ctx.beginPath(); ctx.arc(x + r * 0.22, y - r * 0.12, r * 0.97, 0.4, 3.6); ctx.stroke();
    ctx.fillStyle = B.rgba(PAL.stain, 0.22);
    ctx.beginPath(); B.circle(ctx, x - r * 1.2, y + r * 0.5, 0.7 * u); B.circle(ctx, x - r * 1.32, y + r * 0.62, 0.35 * u); ctx.fill();
    ctx.restore();
  }
  function napkin(ctx, G) {
    const u = G.u, N = G.nap;
    ctx.save();
    B.withShadow(ctx, { color: "rgba(10,5,0,0.45)", blur: 4 * u, x: 0.8 * u, y: 1.4 * u }, () => {
      napkinPath(ctx, G);
      ctx.fillStyle = PAL.napkin;
      ctx.fill();
    });
    napkinPath(ctx, G);
    ctx.clip();
    ctx.fillStyle = quiltPattern(ctx, u);
    ctx.fillRect(N.x - 4 * u, N.y - 4 * u, N.r - N.x + 8 * u, N.b - N.y + 8 * u);
    // soft cloudy unevenness of the tissue
    const mr = B.rng("napkin-cloud");
    for (let i = 0; i < 18; i++) {
      const x = mr.range(N.x, N.r), y = mr.range(N.y, N.b), r = mr.range(25, 60) * u;
      ctx.fillStyle = B.radial(ctx, x, y, 0, r, [B.rgba(mr.chance(0.5) ? "#ffffff" : "#ebe8e1", 0.3), "rgba(255,255,255,0)"]);
      ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
    // the embossed dotted border, inset from the edge
    for (const [ins, a] of [[2.6, 1], [4.6, 0.7]]) {
      for (const [o, col] of [[0.14, B.rgba("#a99f88", 0.45 * a)], [-0.1, B.rgba("#ffffff", a)]]) {
        const p = B.rectPts(N.x + (ins + o) * u, N.y + (ins + o) * u, N.r - N.x - 2 * ins * u, N.b - N.y - 2 * ins * u);
        B.strokeReveal(ctx, p, 1, { width: 0.55 * u, color: col, dash: [0.01, 1.5 * u] });
      }
    }
    // fold creases (folded in four, then again) and small wrinkles
    const w = N.r - N.x, h = N.b - N.y;
    [[0.25, 0.45], [0.5, 1], [0.75, 0.45]].forEach(([f, s]) => { crease(ctx, G, true, N.x + w * f, s); crease(ctx, G, false, N.y + h * f, s); });
    ctx.lineCap = "round";
    G.wrinkles.forEach((pts) => {
      B.strokeReveal(ctx, pts, 1, { width: 0.3 * u, color: B.rgba("#9a907a", 0.18) });
      B.strokeReveal(ctx, pts.map(([x, y]) => [x - 0.3 * u, y - 0.3 * u]), 1, { width: 0.3 * u, color: "rgba(255,255,255,0.75)" });
    });
    G.rings.forEach(([x, y, r], i) => coffeeRing(ctx, x, y, r, u, i * 2.3 + 1));
    ctx.restore();
    // a faint darker rim where the tissue edge lifts
    napkinPath(ctx, G);
    B.with(ctx, () => { ctx.strokeStyle = "rgba(120,105,80,0.25)"; ctx.lineWidth = 0.3 * u; ctx.stroke(); });
  }

  // ------------------------------------------------------------------ ballpoint ink
  const fontOf = (it, size) => B.font(size, it.family, it.weight);
  /** Measured size (shrunk to maxW) and left edge of a text item. */
  function measure(ctx, it) {
    ctx.save();
    ctx.font = fontOf(it, it.size);
    let w = ctx.measureText(it.str).width, size = it.size;
    if (w > it.maxW) { size *= it.maxW / w; w = it.maxW; }
    ctx.restore();
    return { w, size, left: it.align === "left" ? it.x : it.x - w / 2 };
  }
  /** Two quick strikes through a first try, so it stays readable. */
  function scratchPts(ctx, it, G) {
    const m = measure(ctx, it.ref), u = G.u, y = it.ref.y, a = m.left - u, b = m.left + m.w + u;
    const pts = [[a, y + 0.06 * m.size], [b, y - 0.1 * m.size], [b - 2 * u, y + 0.02 * m.size], [a + u, y + 0.18 * m.size]];
    return B.wobble(B.densify(pts, u), { amp: 0.25 * u, seed: 77 });
  }
  /** A ballpoint stroke to p: bleed, pressure-varied core, pale skips, end blobs. */
  function ink(ctx, pts, p, width, seed, t, u, len) {
    if (p <= 0) return;
    const boiled = B.wobble(pts, { amp: u * 0.1, freq: 100 / (16 * u), seed: seed * 7 + B.boil(t, 8) });
    const shown = p >= 1 ? boiled : B.trim(boiled, 0, p);
    if (shown.length < 2) return;
    const total = len || B.pathLength(pts);
    ctx.save();
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.strokeStyle = B.rgba(PAL.ink, 0.08); // the tissue drinks a little ink around the line
    ctx.lineWidth = width * 2.3;
    ctx.beginPath(); B.poly(ctx, shown); ctx.stroke();
    let s = 0;
    for (let i = 1; i < shown.length; i++) {
      const a = shown[i - 1], b = shown[i];
      s += Math.hypot(b[0] - a[0], b[1] - a[1]);
      const f = s / total;
      const press = 0.8 + 0.34 * B.noise1(s / (12 * u), seed);
      const taper = Math.min(1, 0.6 + f * 5, 0.5 + (1 - f) * 4);
      const skip = B.noise1(s / (7 * u), seed + 50) > 0.58;
      ctx.strokeStyle = skip ? B.mix(PAL.ink, PAL.napkin, 0.42) : press > 1.02 ? PAL.deep : PAL.ink;
      ctx.lineWidth = width * press * taper;
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    }
    ctx.fillStyle = B.rgba(PAL.deep, 0.92); // ink gathered where the ball touched down and lifted
    ctx.beginPath(); B.circle(ctx, shown[0][0], shown[0][1], width * 0.78);
    if (p >= 1) { const e = shown[shown.length - 1]; B.circle(ctx, e[0], e[1], width * 0.62); }
    ctx.fill();
    ctx.restore();
  }
  /** Handwriting revealed behind the pen, with ink bleed and boil. */
  function inkText(ctx, it, p, t, u) {
    if (p <= 0) return;
    const m = measure(ctx, it), j = B.boil(t, 8);
    const dx = B.noise1(j * 1.3, it.seed) * 0.12 * u, dy = B.noise1(j * 1.7, it.seed + 3) * 0.12 * u;
    ctx.save();
    ctx.beginPath();
    ctx.rect(m.left - m.size * 0.3, it.y - m.size * 1.1, m.size * 0.3 + m.w * p + (p >= 1 ? m.size * 0.6 : m.size * 0.05), m.size * 2.2);
    ctx.clip();
    ctx.font = fontOf(it, m.size);
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.shadowColor = B.rgba(PAL.ink, 0.5);
    ctx.shadowBlur = Math.max(1, m.size * 0.05);
    ctx.fillStyle = PAL.ink;
    ctx.fillText(it.str, m.left + dx, it.y + dy);
    ctx.restore();
  }
  function tipOf(ctx, it, p, G) {
    if (it.k === "text") {
      const m = measure(ctx, it);
      return [m.left + m.w * p, it.y + m.size * 0.12 + Math.sin(p * m.w / (m.size * 0.16)) * m.size * 0.16];
    }
    const pts = it.k === "scratch" ? scratchPts(ctx, it, G) : it.pts;
    return B.pointAt(pts, B.clamp(p)).slice(0, 2);
  }
  const prog = (it, t) => B.clamp((t - it.start) / it.dur);

  // ------------------------------------------------------------------ camera: glide between patches, nudges of the napkin
  function camAt(t, G) {
    const b = B.beat(t, BEATS, DUR), i = b.i;
    let [x, y] = G.centers[i], zoom = 1 + 0.012 * B.clamp((t - BEATS[i]) / (b.end - BEATS[i]));
    if (i > 0) {
      const k = B.prog(t, BEATS[i] - 0.3, 0.62, "inOutCubic");
      if (k < 1) [x, y, zoom] = [B.lerp(G.centers[i - 1][0], x, k), B.lerp(G.centers[i - 1][1], y, k), 1 - 0.08 * Math.sin(Math.PI * k)];
    }
    // the napkin slides in at the start, and gets pushed a little now and then
    const intro = 1 - B.prog(t, 0, 0.55, "outCubic");
    y += intro * G.u * 10;
    let rot = -0.035 * intro;
    [[4.6, 0.008], [7.0, -0.006], [9.9, 0.01], [11.9, -0.004], [13.2, 0.005]].forEach(([at, a]) => (rot += a * B.prog(t, at - 0.2, 0.45, "outBack")));
    return { x, y, zoom, rot };
  }

  // ------------------------------------------------------------------ the pen
  function penPose(ctx, t, G, cam) {
    const items = G.items, P = G.P;
    let act = null, prev = null, next = null;
    for (const it of items) {
      const end = it.start + it.dur;
      if (t >= it.start && t <= end) act = it;
      else if (end < t) { if (!prev || end > prev.start + prev.dur) prev = it; }
      else if (!next || it.start < next.start) next = it;
    }
    const rest = [cam.x + G.W * (P ? 0.3 : 0.36), cam.y + G.H * (P ? 0.27 : 0.3)];
    if (!prev && !next) return { pos: rest, lift: 1 };
    if (act) return { pos: tipOf(ctx, act, prog(act, t), G), lift: 0 };
    const off = [cam.x + G.W * 0.75, cam.y + G.H * 0.75], mixP = (a, b, k) => [B.lerp(a[0], b[0], k), B.lerp(a[1], b[1], k)];
    const pEnd = prev ? prev.start + prev.dur : -9, from = prev ? tipOf(ctx, prev, 1, G) : off, to = next ? tipOf(ctx, next, 0, G) : rest;
    const gap = (next ? next.start : 99) - pEnd, home = prev ? rest : off, k = (v) => B.ease.inOutSine(B.clamp(v));
    if (prev && next && gap < 0.8) return { pos: mixP(from, to, k((t - pEnd) / gap)), lift: Math.sin(Math.PI * k((t - pEnd) / gap)) * Math.min(1, 0.4 + gap * 2) };
    if (prev && t - pEnd < 0.45) return { pos: mixP(from, home, k((t - pEnd) / 0.45)), lift: k((t - pEnd) / 0.45) };
    if (next && next.start - t < 0.45) return { pos: mixP(home, to, k(1 - (next.start - t) / 0.45)), lift: 1 - k(1 - (next.start - t) / 0.45) };
    return { pos: home, lift: 1 };
  }
  /** A clear-barrel ballpoint from above, held in a right hand, with its shadow. */
  function pen(ctx, x, y, lift, t, G) {
    const u = G.u, L = (G.P ? 44 : 54) * u, d = 1.5 * u, ang = 0.98 + 0.04 * B.noise1(t * 0.7, 4);
    const body = (g) => { g.save(); g.translate(x, y); g.rotate(ang); };
    ctx.save();
    const so = (0.7 + 2.6 * lift) * u;
    ctx.translate(so * 0.7, so * 1.1);
    body(ctx);
    ctx.fillStyle = `rgba(30,25,15,${0.22 - 0.07 * lift})`;
    ctx.filter = `blur(${(0.5 + lift) * u}px)`;
    ctx.beginPath(); B.poly(ctx, [[0, 0], [6 * u, -d], [L, -d], [L, d], [6 * u, d]], true); ctx.fill();
    ctx.restore();
    ctx.restore();
    body(ctx);
    ctx.fillStyle = "#9aa1a8"; // the metal point
    ctx.beginPath(); B.poly(ctx, [[0, 0], [2.6 * u, -0.6 * u], [2.6 * u, 0.6 * u]], true); ctx.fill();
    ctx.fillStyle = B.linear(ctx, 0, -d, 0, d, ["#3a5ccc", "#1d3290"]); // the tinted grip cone
    ctx.beginPath(); B.poly(ctx, [[2.6 * u, -0.6 * u], [7 * u, -d], [7 * u, d], [2.6 * u, 0.6 * u]], true); ctx.fill();
    ctx.fillStyle = B.linear(ctx, 0, -d, 0, d, ["rgba(255,255,255,0.95)", "rgba(222,230,238,0.92)", "rgba(170,182,196,0.95)"]); // clear barrel
    ctx.fillRect(7 * u, -d, L - 11 * u, 2 * d);
    // ink tube, end plug, clip, a highlight along the barrel
    [[B.rgba(PAL.ink, 0.75), 7 * u, -0.25 * u, L - 15 * u, 0.5 * u], [PAL.ink, L - 4 * u, -d * 1.05, 4 * u, 2.1 * d], [PAL.ink, L - 14 * u, -d - 0.55 * u, 11 * u, 0.6 * u], ["rgba(255,255,255,0.7)", 8 * u, -d * 0.7, L - 13 * u, 0.3 * u]].forEach(([c, ...r]) => {
      ctx.fillStyle = c;
      ctx.fillRect(...r);
    });
    ctx.restore();
  }

  // ------------------------------------------------------------------ frame
  function draw(ctx, W, H, t) {
    const G = build(W, H), u = G.u, cam = camAt(t, G);
    B.camera(ctx, W, H, cam, () => {
      ctx.fillStyle = woodPattern(ctx, u);
      ctx.fillRect(cam.x - W * 1.2, cam.y - H * 1.2, W * 2.4, H * 2.4);
      napkin(ctx, G);
      // ink: only what is written by now, on patches near the view
      const vx = W * 1.05 / cam.zoom, vy = H * 1.05 / cam.zoom;
      for (const it of G.items) {
        if (t < it.start) continue;
        const [ax, ay] = it.k === "path" ? it.pts[0] : [(it.ref || it).x, (it.ref || it).y];
        if (Math.abs(ax - cam.x) > vx || Math.abs(ay - cam.y) > vy) continue;
        const p = prog(it, t);
        if (it.k === "text") inkText(ctx, it, p, t, u);
        else if (it.k === "path") ink(ctx, it.pts, p, it.width, it.seed, t, u, it.len);
        else ink(ctx, scratchPts(ctx, it, G), p, it.width, it.seed, t, u);
      }
      const pose = penPose(ctx, t, G, cam);
      pen(ctx, pose.pos[0], pose.pos[1], pose.lift, t, G);
    });
    // finishing: warm café light from the upper left, falling off at the edges, and fine grain
    B.with(ctx, () => {
      ctx.globalCompositeOperation = "multiply";
      ctx.fillStyle = B.radial(ctx, W * 0.3, H * 0.2, 0, Math.hypot(W, H) * 0.85, ["#ffffff", "#ffffff", "#e9e2d6"]);
      ctx.fillRect(0, 0, W, H);
    });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12 });
  }

  // ------------------------------------------------------------------ sound: pen scratch per stroke, rustles, café murmur, taps
  SOUND.define("napkin-scratch", (v, o) => {
    // a muffled, grainy scratch; words get gaps between letters
    const d = o.dur ?? 0.3;
    v.noise({ filter: "bandpass", f: 1700, q: 0.9, a: 0.01, hold: d * 0.85, len: 0.04, peak: 0.08 });
    if (o.letters) {
      const n = Math.max(2, Math.round(d * 16));
      for (let i = 0; i < n; i++) v.grains({ at: (i / n) * d, span: (d / n) * 0.7, count: 6, filter: "bandpass", f: 2600, q: 1.3, len: 0.012, peak: 0.24 });
    } else v.grains({ span: d, count: Math.max(4, d * 70), filter: "bandpass", f: 2900, q: 1.2, len: 0.011, peak: 0.22 });
  }, { verb: 0.06 });
  SOUND.define("napkin-tap", (v) => {
    v.noise({ filter: "lowpass", f: 1100, a: 0.001, len: 0.05, peak: 0.45 });
    v.tone({ f: 190, f2: 120, glide: 0.06, a: 0.001, len: 0.08, peak: 0.22 });
    v.noise({ filter: "highpass", f: 3500, a: 0.0005, len: 0.012, peak: 0.12 });
  }, { verb: 0.12 });
  SOUND.define("napkin-cafe", (v, o) => {
    // a quiet café: room rumble, far voices (noise puffs), the odd cup clink
    const d = v.dur ?? 8, g = v.bedGain(d, 0.8, o.fade ?? 1);
    v.noise({ filter: "lowpass", f: 420, a: 0.8, hold: d - 1.6, len: 0.8, peak: 0.16, brown: true, dest: g });
    for (let at = 0.1; at < d - 0.3; at += 0.07 + v.rng() * 0.16) {
      v.noise({ at, filter: "bandpass", f: 320 + v.rng() * 800, q: 5, a: 0.04, hold: 0.04 + v.rng() * 0.12, len: 0.1, peak: 0.035 + v.rng() * 0.03, dest: g });
    }
    for (const at of [1.7, 6.3, 11.1]) {
      if (at > d - 0.5) continue;
      v.tone({ at, f: 2950 + v.rng() * 300, a: 0.001, len: 0.35, peak: 0.018, dest: g });
      v.tone({ at, f: 4600 + v.rng() * 500, a: 0.001, len: 0.2, peak: 0.01, dest: g });
    }
  }, { bed: true, verb: 0.25 });

  function score(k) {
    const cfg = window.TM_PAGE || {};
    const G = build(cfg.width || 1280, cfg.height || 720);
    k.bed("napkin-cafe", 0, DUR, { gain: 0.8 });
    k.at(0.02, "paper", { gain: 0.5 }).at(0.05, "rustle", { dur: 0.45, gain: 0.55 });
    G.items.forEach((it, i) => {
      const pan = ((i * 37) % 9) / 9 - 0.45;
      if (it.k === "text") k.at(it.start, "napkin-scratch", { dur: it.dur, letters: true, gain: 0.8, pitch: ((i * 5) % 5) - 2, pan });
      else k.at(it.start, "napkin-scratch", { dur: Math.max(0.05, it.dur), gain: it.k === "scratch" ? 1.1 : 0.75, pitch: ((i * 3) % 7) - 3, pan });
      if (it.tap) k.at(it.start + 0.01, "napkin-tap", { gain: 0.9 }).at(it.start + 0.16, "napkin-tap", { gain: 0.6, pitch: 1 });
    });
    BEATS.slice(1).forEach((at, i) => k.at(at - 0.32, "rustle", { dur: 0.5, gain: 0.45 + 0.1 * (i % 2), pan: i % 2 ? 0.3 : -0.3 }));
    k.at(DUR - 0.6, "napkin-tap", { gain: 0.7 });
  }

  Player.register({
    id: "napkin-sketch",
    name: "Napkin Sketch",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Nanum+Pen+Script&display=swap",
      faces: ['600 20px "Caveat"', '700 20px "Caveat"', '400 20px "Nanum Pen Script"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Per day", "Close"],
    stills: [2.0, 4.4, 6.8, 9.7, 11.7, 13.8],
    draw,
    score,
  });
})();
