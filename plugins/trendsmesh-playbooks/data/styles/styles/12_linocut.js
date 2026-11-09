/* 12 Linocut Print. Topic (replace it): "How does a volcano erupt?". Rendering (keep it): two blocks; the black starts
 * solid and the picture is CUT out of it (pointed cuts, teardrops, parallel rows for tone, stray nicks); vermilion
 * prints first, off register; ragged speckled ink, fibrous paper, pencil in the margin. Motion: stop-motion steps,
 * each scene a new proof peeled in along a diagonal. */
(function () {
  "use strict"; const B = window.Brush;

  const PAL = { paper: "#efe6d2", black: "#1d1a19", red: "#c6402b", deep: "#8e2a1f", graphite: "#55545a", fibre: "#d9ccb0" };
  const CUTF = "Bowlby One", PEN = "Nanum Pen Script"; const DUR = 12; const BEATS = [0, 2.0, 4.1, 6.2, 8.3, 10.3];
  const STEP = 8; // stop-motion pulls a second
  const PEEL = 0.6;

  let K = null, Rd = null, BX = null, U = 1, P = false; // black and red block layers, block rect and unit
  const X = (f) => BX.x + f * BX.w, Y = (f) => BX.y + f * BX.h;

  // ---- carving helpers (reuse these)
  function inMode(g, mode, fn) {
    g.save(); g.globalCompositeOperation = mode; fn(); g.restore();
  }
  const fillPoly = (g, pts, mode = "source-over", color = "#000") =>
    inMode(g, mode, () => {
      g.fillStyle = color; g.beginPath(); B.poly(g, pts, true); g.fill();
    });
  const clearPoly = (g, pts) => fillPoly(g, pts, "destination-out");
  /** A knife cut that removes ink: fat in the middle, sharp at both ends (o.tear: a teardrop; o.ink adds ink). */
  function cut(g, pts, w, o = {}) {
    if (pts.length < 2 || w <= 0.2) return;
    inMode(g, o.ink ? "source-over" : "destination-out", () =>
      B.taperStroke(g, pts, { width: w, color: "#000", taperIn: o.tear ? 0.06 : 0.45, taperOut: o.tear ? 0.94 : 0.5, rough: 0.3, roughScale: 2.5, seed: o.seed ?? 1 })
    );
  }
  /** Draw only the first p of a list of cuts: shapes being carved, one stroke at a time. */
  function cutList(g, list, p = 1) {
    const n = Math.floor(B.clamp(p) * list.length + 1e-6);
    for (let i = 0; i < n; i++) cut(g, list[i].pts, list[i].w, list[i]);
  }
  /** Rows of parallel cuts for tone (gap and width may be functions of the point: close cuts read light). */
  function rowCuts(box, o) {
    const r = B.rng(o.seed ?? 3), a = B.deg(o.angle ?? 0), ca = Math.cos(a), sa = Math.sin(a);
    const cx = box.x + box.w / 2, cy = box.y + box.h / 2, R = Math.hypot(box.w, box.h) / 2, out = [];
    const gapF = typeof o.gap === "function" ? o.gap : () => o.gap, wF = typeof o.w === "function" ? o.w : () => o.w;
    for (let d = -R; d <= R; ) {
      let s = -R + r.range(0, o.len[1]);
      while (s < R) {
        const len = r.range(o.len[0], o.len[1]), mid = s + len / 2;
        const mx = cx + mid * ca - d * sa, my = cy + mid * sa + d * ca;
        if (mx > box.x - len && mx < box.x + box.w + len && my > box.y - 2 * U && my < box.y + box.h + 2 * U) {
          const bow = r.range(-0.25, 0.25) * U, wob = o.wave ? Math.sin(mx * o.wave) * U * 0.8 : 0;
          const pts = [0, 0.5, 1].map((k) => {
            const ss = s + k * len, b = k === 0.5 ? bow : 0;
            return [cx + ss * ca - (d + b + wob) * sa, cy + ss * sa + (d + b + wob) * ca];
          });
          const w = wF(mx, my) * r.range(0.75, 1.15);
          if (w > 0.15) out.push({ pts: B.densify(pts, U), w, seed: out.length });
        }
        s += len + r.range(o.space[0], o.space[1]);
      }
      d += Math.max(0.4 * U, gapF(cx - d * sa, cy + d * ca));
    }
    return out;
  }
  /** Concentric ring cuts (a sun, a magma pool): arcs broken into tapered strokes. */
  function ringCuts(cx, cy, r0, r1, gap, w, seed) {
    const r = B.rng(seed), out = [];
    for (let rad = r0; rad <= r1; rad += gap) {
      let a = r.range(0, B.TAU); const end = a + B.TAU;
      while (a < end) {
        const da = Math.min(end - a, r.range(0.5, 1.4) * (2.4 * gap) / Math.max(rad, gap));
        out.push({ pts: B.arcPts(cx, cy, rad, a, a + da, 10), w: w * r.range(0.8, 1.2), seed: out.length });
        a += da + r.range(0.08, 0.35) * (gap / Math.max(rad, gap)) * 3;
      }
    }
    return out;
  }
  /** Stray nicks near a polyline, as if the cutter's hand slipped. */
  function nicks(g, pts, n, seed, len = 1.6) {
    const r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const q = B.pointAt(pts, r()), a = q[2] + Math.PI / 2 + r.range(-0.6, 0.6), d = r.range(0.6, 2.4) * U, l = r.range(0.5, 1) * len * U;
      const x = q[0] + Math.cos(a) * d, y = q[1] + Math.sin(a) * d;
      cut(g, [[x, y], [x + Math.cos(a + r.range(-0.4, 0.4)) * l, y + Math.sin(a + r.range(-0.4, 0.4)) * l]], r.range(0.35, 0.8) * U, { tear: r() < 0.5, seed: i });
    }
  }
  /** A gouged arrow: a white channel through the black that widens from tail to a triangular head. */
  function gougeArrow(g, path, p, w, o = {}) {
    if (p <= 0) return; const shown = B.trim(path, 0, B.clamp(p)); const L = B.pathLength(shown); if (L < w) return;
    const shaft = B.trim(shown, 0, Math.max(0.01, 1 - (w * 2.2) / L));
    inMode(g, o.red ? "source-over" : "destination-out", () => {
      B.taperStroke(g, shaft, { width: w, color: "#000", taperIn: 0.9, taperOut: 0.02, rough: 0.25, roughScale: 3, seed: 5 });
      const tip = B.pointAt(shown, 1), a = tip[2], base = B.pointAt(shown, Math.max(0, 1 - (w * 2.4) / L));
      const nx = -Math.sin(a), ny = Math.cos(a), hw = w * 1.25; g.fillStyle = "#000"; g.beginPath();
      B.poly(g, [[tip[0] + Math.cos(a) * w * 0.3, tip[1] + Math.sin(a) * w * 0.3], [base[0] + nx * hw, base[1] + ny * hw], [base[0] - nx * hw, base[1] - ny * hw]], true);
      g.fill();
    });
  }
  /** Hand-cut letters, each rotated and nudged; mode "cut" (paper letters) or "ink". */
  function cutLetters(g, text, cx, cy, size, mode, p = 1, seed = 1, jitter = 1) {
    g.save(); g.font = B.font(size, CUTF, 400);
    const chars = [...text], ws = chars.map((c) => g.measureText(c).width), track = size * 0.04;
    const total = ws.reduce((a, b) => a + b, 0) + track * (chars.length - 1);
    const shown = Math.floor(B.clamp(p) * chars.length + 1e-6);
    let x = cx - total / 2; g.textAlign = "center"; g.textBaseline = "middle";
    g.globalCompositeOperation = mode === "cut" ? "destination-out" : "source-over";
    g.fillStyle = "#000";
    chars.forEach((c, i) => {
      const r = B.rng(B.hash(seed, i));
      if (i < shown && c !== " ") {
        g.save(); g.translate(x + ws[i] / 2, cy + r.range(-0.07, 0.07) * size * jitter);
        g.rotate(r.range(-0.07, 0.07) * jitter); g.fillText(c, 0, 0); g.restore();
      }
      x += ws[i] + track;
    });
    g.restore(); return total;
  }
  /** Wobbly rectangle (cut by hand), as points. */
  function wobRect(x, y, w, h, amp, seed) {
    return B.wobble(B.densify([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], Math.max(4, U * 2)), { amp, freq: 0.6, seed });
  }
  /** Label: paper letters cut out of a red band. */
  function bandLabel(text, cx, cy, size, p = 1, seed = 1) {
    K.font = B.font(size, CUTF, 400); const tw = K.measureText(text).width + size * 0.04 * text.length;
    const w = tw + size * 0.9, h = size * 1.3, x = cx - w / 2, y = cy - h / 2;
    clearPoly(K, wobRect(x - size * 0.22, y - size * 0.2, w + size * 0.44, h + size * 0.4, U * 0.35, seed));
    fillPoly(Rd, wobRect(x, y, w, h, U * 0.3, seed + 1));
    cutLetters(Rd, text, cx, cy + size * 0.04, size, "cut", p, seed);
    return { x, y, w, h };
  }

  // ---- the block itself
  /** The inked block: a wavy-edged rectangle, a cut line inside it, nicks along the border. */
  function block(seed) {
    const edge = B.wobble(B.densify(B.rectPts(BX.x, BX.y, BX.w, BX.h).slice(0, 4), U * 2), { amp: U * 0.45, freq: 0.5, seed });
    fillPoly(K, edge);
    const inset = 1.6 * U, inner = B.wobble(B.densify(B.rectPts(BX.x + inset, BX.y + inset, BX.w - 2 * inset, BX.h - 2 * inset), U * 1.5), { amp: U * 0.25, freq: 0.8, seed: seed + 3 });
    const L = B.pathLength(inner), segs = Math.round(L / (14 * U));
    for (let i = 0; i < segs; i++) cut(K, B.trim(inner, i / segs + 0.002, (i + 1) / segs - 0.002), 0.55 * U, { seed: i + seed });
    nicks(K, inner, Math.round(L / (9 * U)), seed + 7, 1.4);
  }

  // ---- subjects (the setting: replace these)
  /** Volcano cone outline: concave slopes (flat at the foot, steep near the top) and a notched crater. */
  function conePts(ax, ay, bl, br, by, cw, seed) {
    const left = [], right = [], n = 26;
    for (let i = 0; i <= n; i++) {
      const k = i / n, yk = by - (by - ay) * Math.pow(k, 1.7);
      left.push([B.lerp(bl, ax - cw / 2, k), yk]); right.push([B.lerp(br, ax + cw / 2, k), yk]);
    }
    const crater = [[ax - cw * 0.22, ay + cw * 0.22], [ax + cw * 0.18, ay + cw * 0.2]];
    return B.wobble(left.concat(crater, right.reverse()), { amp: U * 0.5, freq: 0.35, seed });
  }
  /** A broken knife line just outside a shape's top edge, so it reads against black. */
  function silhouetteCut(pts, seed) {
    const L = B.pathLength(pts), n = Math.max(3, Math.round(L / (12 * U))), r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const a = i / n + r.range(0, 0.02), b = (i + 1) / n - r.range(0.005, 0.03);
      const seg = B.trim(pts, a, b).map(([x, y]) => [x, y - 1.1 * U]);
      cut(K, seg, r.range(0.6, 0.95) * U, { seed: i + seed });
    }
  }
  /** Fan of ridge cuts down the cone: closer on the lit left, sparse on the right. */
  function coneCuts(ax, ay, bl, br, by, seed, count = 30) {
    const r = B.rng(seed), out = [];
    for (let i = 0; i <= count; i++) {
      const k = i / count, light = 1 - k; // left is lit
      const top = [ax + (k - 0.5) * (br - bl) * 0.08, ay + (by - ay) * r.range(0.1, 0.22)];
      const bot = [B.lerp(bl, br, k) + r.range(-1, 1) * U, by - r.range(0, 2) * U];
      const line = B.quad(top[0], top[1], B.lerp(top[0], bot[0], 0.5) + (k - 0.5) * 2 * U, B.lerp(top[1], bot[1], 0.62), bot[0], bot[1], 16);
      let s = r.range(0, 0.12);
      while (s < 0.95) {
        const e = Math.min(1, s + r.range(0.15, 0.4));
        if (r() < 0.35 + 0.6 * light) out.push({ pts: B.trim(line, s, e), w: (0.35 + 1.0 * light) * U * r.range(0.7, 1.2), seed: out.length });
        s = e + r.range(0.04, 0.14);
      }
    }
    return out;
  }
  /** Ash cloud: black lobes with swirl cuts. */
  function ashCloud(cx, cy, r, grow, seed, light = false) {
    const rr = B.rng(seed), lobes = [];
    for (let i = 0; i < 9; i++) {
      const a = rr.range(-Math.PI * 0.95, -Math.PI * 0.05), d = rr.range(0.2, 0.75) * r * grow;
      lobes.push([cx + Math.cos(a) * d * 1.25, cy + Math.sin(a) * d * 0.8, rr.range(0.32, 0.5) * r * grow]);
    }
    lobes.push([cx, cy, 0.45 * r * grow]);
    inMode(K, light ? "destination-out" : "source-over", () => {
      K.fillStyle = "#000";
      lobes.forEach(([x, y, rad]) => {
        K.beginPath();
        B.blob(K, x, y, rad, { seed: seed + x, wobble: 0.12, n: 9 });
        K.fill();
      });
    });
    lobes.forEach(([x, y, rad], i) => {
      for (let k = 0; k < 3; k++) {
        const rad2 = rad * (0.35 + k * 0.2), a0 = -Math.PI * (0.9 - k * 0.1) + i;
        cut(K, B.arcPts(x, y, rad2, a0, a0 + 1.6 + k * 0.4, 14), (0.9 - k * 0.15) * U, { seed: i * 3 + k, ink: light });
      }
    });
  }
  /** Lava spray: teardrop drops cleared from the black and printed red underneath. */
  function lavaSpray(cx, cy, h, n, grow, seed) {
    const r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + r.range(-0.75, 0.75), d = r.range(0.25, 1) * h * grow, l = r.range(2.5, 5) * U;
      const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d;
      const tail = [[x, y], [x - Math.cos(a) * l, y - Math.sin(a) * l]]; const w = r.range(1.4, 2.6) * U;
      cut(K, tail, w, { tear: true, seed: i });
      cut(Rd, tail, w * 1.05, { tear: true, ink: true, seed: i });
    }
  }
  /** Sky: rows of slightly wavy horizontal cuts. */
  const skyCuts = (box, seed, dens = 1) => rowCuts(box, { angle: 0, gap: 2.0 * U / dens, w: 0.55 * U, len: [6 * U, 18 * U], space: [1.5 * U, 5 * U], wave: 0.02, seed });
  /** Ground: wavy contour rows plus tufts of teardrop cuts. */
  function ground(y0, seed) {
    const box = { x: BX.x, y: y0, w: BX.w, h: BX.y + BX.h - y0 };
    fillPoly(K, B.wobble([[BX.x, y0], [BX.x + BX.w, y0 - 2 * U], [BX.x + BX.w, BX.y + BX.h], [BX.x, BX.y + BX.h]], { amp: U * 0.6, seed }));
    cutList(K, rowCuts(box, { angle: -2, gap: (x, y) => (2.2 + 2 * B.clamp((y - y0) / box.h)) * U, w: (x, y) => (0.9 - 0.4 * B.clamp((y - y0) / box.h)) * U, len: [4 * U, 12 * U], space: [2 * U, 6 * U], wave: 0.03, seed }));
  }

  // ---- the scenes (each draws one print at step time ts)
  function sceneTitle(ts) {
    block(11);
    const ax = P ? 0.5 : 0.56, ay = P ? 0.5 : 0.4, bl = P ? 0.04 : 0.2, br = P ? 0.96 : 0.94, by = 0.9;
    cutList(K, skyCuts({ x: BX.x, y: Y(0.28), w: BX.w, h: BX.h * 0.62 }, 21));
    const sc = [X(P ? 0.7 : 0.8), Y(P ? 0.47 : 0.5)], sr = P ? 0.2 * BX.w : 0.27 * BX.h;
    inMode(K, "destination-out", () => {
      K.beginPath();
      B.blob(K, sc[0], sc[1], sr * 1.06, { seed: 4, wobble: 0.02, n: 24 });
      K.fill();
    });
    Rd.beginPath();
    B.blob(Rd, sc[0], sc[1], sr, { seed: 5, wobble: 0.02, n: 24 });
    Rd.fill();
    cutList(Rd, ringCuts(sc[0], sc[1], sr * 0.3, sr * 0.9, 2.2 * U, 0.6 * U, 6));
    const cone = conePts(X(ax), Y(ay), X(bl), X(br), Y(by), BX.w * 0.07, 7);
    fillPoly(K, cone); silhouetteCut(cone, 10); cutList(K, coneCuts(X(ax), Y(ay), X(bl), X(br), Y(by), 8));
    nicks(K, cone, 18, 9);
    const cw = BX.w * 0.07, glow = [[X(ax) - cw * 0.4, Y(ay) + 0.4 * U], [X(ax) + cw * 0.4, Y(ay) + 0.4 * U], [X(ax) + cw * 0.25, Y(ay) + cw * 0.35], [X(ax) - cw * 0.25, Y(ay) + cw * 0.35]];
    clearPoly(K, glow); fillPoly(Rd, glow); const lt = ts - BEATS[0];
    ashCloud(X(ax) + U * 2, Y(ay) - (P ? 12 : 9) * U, (P ? 17 : 13) * U, B.clamp(0.55 + lt * 0.25), 12, true);
    ground(Y(0.9), 13); const tp = B.clamp((lt - 0.55) / 0.9);
    if (P) {
      bandLabel("HOW A VOLCANO", X(0.5), Y(0.1), 7.8 * U, tp * 2, 31);
      bandLabel("ERUPTS", X(0.5), Y(0.22), 9.5 * U, tp * 2 - 1, 33);
    } else bandLabel("HOW A VOLCANO ERUPTS", X(0.5), Y(0.13), 8.4 * U, tp, 31);
  }

  function sceneDiagram(ts) {
    block(21); const lt = ts - BEATS[1];
    const gy = P ? 0.42 : 0.4; // ground surface
    const ax = P ? 0.5 : 0.36, ay = P ? 0.16 : 0.1, bl = P ? 0.12 : 0.1, br = P ? 0.88 : 0.62;
    clearPoly(K, wobRect(BX.x + 2.5 * U, BX.y + 2.5 * U, BX.w - 5 * U, Y(gy) - BX.y - 2.5 * U, U * 0.4, 3));
    const cone = conePts(X(ax), Y(ay), X(bl), X(br), Y(gy) + U, BX.w * 0.08, 22);
    fillPoly(K, cone); cutList(K, coneCuts(X(ax), Y(ay), X(bl), X(br), Y(gy), 23, 22));
    cutList(K, rowCuts({ x: BX.x, y: Y(gy) + 2 * U, w: BX.w, h: BX.h * (1 - gy) - 4 * U }, { angle: 1.5, gap: 3.4 * U, w: 0.7 * U, len: [5 * U, 16 * U], space: [2 * U, 7 * U], wave: 0.025, seed: 24 }));
    const ch = [X(ax), Y(P ? 0.8 : 0.78)], cr = [BX.w * (P ? 0.24 : 0.15), BX.h * (P ? 0.1 : 0.14)];
    const chamber = Array.from({ length: 40 }, (_, i) => {
      const a = (i / 40) * B.TAU;
      return [ch[0] + Math.cos(a) * cr[0] * (1 + 0.08 * Math.sin(a * 3)), ch[1] + Math.sin(a) * cr[1]];
    });
    const vent = [[X(ax) - 1.6 * U, Y(ay) + U], [X(ax) + 1.6 * U, Y(ay) + U], [X(ax) + 2.4 * U, ch[1]], [X(ax) - 2.4 * U, ch[1]]];
    const grow = B.clamp((lt - 0.65) / 0.6); // magma rises up the vent in steps
    const ventTop = B.lerp(ch[1], Y(ay) + U, grow);
    clearPoly(K, B.wobble(chamber, { amp: U * 0.5, seed: 25 }));
    clearPoly(K, [[X(ax) - 1.8 * U, Y(ay)], [X(ax) + 1.8 * U, Y(ay)], [X(ax) + 2.6 * U, ch[1]], [X(ax) - 2.6 * U, ch[1]]]);
    fillPoly(Rd, chamber); fillPoly(Rd, vent.map(([x, y]) => [x, Math.max(y, ventTop)]));
    for (let i = 0; i < 9; i++) {
      const r = B.rng(40 + i), bx = ch[0] + r.range(-0.7, 0.7) * cr[0], byy = ch[1] + r.range(-0.5, 0.5) * cr[1];
      cut(Rd, B.arcPts(bx, byy, r.range(0.8, 1.6) * U, 0, B.TAU * 0.85, 10), 0.6 * U, { seed: i });
    }
    const axr = X(ax) + (P ? 12 : 10) * U;
    gougeArrow(K, B.quad(axr + 2 * U, ch[1] - cr[1] * 0.9, axr + 4 * U, B.lerp(ch[1], Y(ay), 0.5), axr - 1.5 * U, Y(ay) + (P ? 20 : 6) * U, 24), B.clamp((lt - 0.7) / 0.6), 3.4 * U); // the head stays on the black
    const lp = (a) => B.clamp((lt - a) / 0.35);
    bandLabel("MAGMA", P ? X(0.5) : X(0.62), P ? Y(0.94) : Y(0.9), (P ? 6 : 7.5) * U, lp(1.0), 41);
    // VENT beside the conduit, a cut leader to it
    const vl = bandLabel("VENT", X(ax) - (P ? 20 : 17) * U, Y(P ? 0.6 : 0.56), (P ? 5.5 : 7) * U, lp(1.2), 42), vy = vl.y + vl.h / 2;
    if (lp(1.2) >= 1) cut(K, [[vl.x + vl.w + 1.2 * U, vy], [X(ax) - 3.4 * U, vy]], 0.9 * U, { seed: 4 });
    // CRATER beside the summit, a short red arrow into the crater
    const cx0 = X(ax) + (P ? 26 : 25) * U, cy0 = Y(ay) + (P ? -2 : 3) * U, cl = bandLabel("CRATER", cx0, cy0, (P ? 5.5 : 7) * U, lp(1.4), 43);
    gougeArrow(Rd, B.quad(cl.x - U, cy0, X(ax) + 6 * U, cy0 - U, X(ax) + 2 * U, Y(ay) + U, 12), B.clamp((lt - 1.5) / 0.3), 1.8 * U, { red: true });
  }

  function sceneNumber(ts) {
    block(31); const lt = ts - BEATS[2];
    cutList(K, skyCuts({ x: BX.x, y: BX.y, w: BX.w, h: BX.h }, 32, 0.85));
    const c = [X(0.5), Y(P ? 0.4 : 0.42)], rr = Math.min(BX.w, BX.h) * (P ? 0.34 : 0.36);
    const disc = (g, k) => { g.beginPath(); B.blob(g, c[0], c[1], rr * k, { seed: 2, wobble: 0.03, n: 24 }); g.fill(); };
    inMode(K, "destination-out", () => disc(K, 1.04));
    disc(Rd, 1);
    cutList(Rd, ringCuts(c[0], c[1], rr * 0.82, rr * 0.95, 1.8 * U, 0.55 * U, 9));
    nicks(K, B.arcPts(c[0], c[1], rr * 1.06, 0, B.TAU, 60), 14, 33);
    const v = Math.round(B.lerp(0, 1200, B.ease.outCubic(B.clamp((lt - 0.2) / 0.9))) / 50) * 50;
    const s = v.toLocaleString("en-US"); const step = Math.floor(ts * STEP + 1e-6);
    cutLetters(K, s, c[0], c[1] - rr * 0.1, (P ? 15.5 : 16) * U, "ink", 1, 100 + step, 1.4);
    cutLetters(K, "°C", c[0], c[1] + rr * 0.38, (P ? 10 : 9) * U, "ink", 1, 200 + step, 1.4);
    bandLabel("LAVA", P ? X(0.5) : X(0.83), P ? Y(0.73) : Y(0.44), (P ? 6 : 6.5) * U, B.clamp((lt - 0.9) / 0.4), 51);
    bandLabel("HOT ENOUGH TO MELT ROCK", X(0.5), Y(P ? 0.87 : 0.9), (P ? 4.6 : 5.6) * U, B.clamp((lt - 1.3) / 0.5), 52);
  }

  /** One carved tile: a paper square with a black-line picture; kind 0 gas, 1 pressure, 2 burst. */
  function tile(cx, cy, s, kind, p) {
    if (p <= 0) return; clearPoly(K, wobRect(cx - s / 2, cy - s / 2, s, s, U * 0.35, 60 + kind));
    const line = (pts, w = 1.3) => cut(K, pts, w * U, { ink: true, seed: pts.length });
    const k = B.clamp(p * 1.3); const n = (a) => k >= a;
    const m = B.arcPts(cx, cy + s * 0.12, s * 0.3, Math.PI * 0.05, Math.PI * 0.95, 20);
    line(m, 1.5);
    line([[cx - s * 0.36, cy + s * 0.22], [cx + s * 0.36, cy + s * 0.22]], 1.0);
    if (kind === 0) {
      [[-0.1, 0.05, 0.06], [0.08, -0.08, 0.05], [-0.02, -0.25, 0.07], [0.15, 0.1, 0.04]].forEach(([dx, dy, r], i) => n(0.25 + i * 0.18) && line(B.arcPts(cx + dx * s, cy + dy * s, r * s, 0, B.TAU * 0.92, 14), 1.0));
    } else if (kind === 1) {
      line(B.arcPts(cx, cy - s * 0.02, s * 0.32, Math.PI * 1.08, Math.PI * 1.92, 20), 2.0);
      [-0.16, 0, 0.16].forEach((dx, i) => {
        if (!n(0.3 + i * 0.2)) return; line([[cx + dx * s, cy + s * 0.18], [cx + dx * s, cy - s * 0.12]], 1.1);
        line([[cx + dx * s - s * 0.05, cy - s * 0.06], [cx + dx * s, cy - s * 0.13], [cx + dx * s + s * 0.05, cy - s * 0.06]], 1.0);
      });
    } else {
      const r = B.rng(70);
      for (let i = 0; i < 9; i++) {
        if (!n(0.2 + i * 0.08)) continue;
        const a = -Math.PI / 2 + r.range(-1.1, 1.1), d0 = s * 0.12, d1 = s * r.range(0.28, 0.42);
        cut(K, [[cx + Math.cos(a) * d1, cy - s * 0.05 + Math.sin(a) * d1], [cx + Math.cos(a) * d0, cy - s * 0.05 + Math.sin(a) * d0]], 1.6 * U, { ink: true, tear: true, seed: i });
      }
    }
  }
  function sceneSteps(ts) {
    block(41); const lt = ts - BEATS[3];
    cutList(K, skyCuts({ x: BX.x, y: BX.y, w: BX.w, h: BX.h }, 44, 0.8));
    const labels = ["GAS", "PRESSURE", "ERUPTION"], starts = [0.3, 0.75, 1.2];
    for (let i = 0; i < 3; i++) {
      const p = B.clamp((lt - starts[i]) / 0.45); const s = P ? BX.h * 0.2 : BX.w * 0.2;
      const cx = P ? X(0.34) : X(0.2 + i * 0.3), cy = P ? Y(0.17 + i * 0.32) : Y(0.42);
      tile(cx, cy, s, i, p);
      if (p > 0) {
        bandLabel(`${i + 1} ${labels[i]}`, P ? X(0.74) : cx, P ? cy : cy + s * 0.68, (P ? 5.2 : 6.4) * U, B.clamp(p * 1.6 - 0.4), 80 + i);
        if (i > 0) {
          const from = P ? [cx, cy - s * 1.02] : [cx - BX.w * 0.3 + s * 0.56, cy];
          const to = P ? [cx, cy - s * 0.58] : [cx - s * 0.56, cy];
          gougeArrow(K, [from, to], B.clamp(p * 2), 2.2 * U);
        }
      }
    }
  }

  function sceneErupt(ts) {
    block(51); const lt = ts - BEATS[4];
    const ax = 0.5, ay = P ? 0.5 : 0.48, bl = P ? 0.02 : 0.14, br = P ? 0.98 : 0.86, by = 0.92;
    cutList(K, skyCuts({ x: BX.x, y: BX.y, w: BX.w, h: BX.h * 0.9 }, 52, 0.9));
    const gc = [X(ax), Y(ay) - BX.h * 0.08], gr = Math.min(BX.w, BX.h) * (P ? 0.36 : 0.42);
    inMode(K, "destination-out", () => {
      K.beginPath();
      B.blob(K, gc[0], gc[1], gr, { seed: 3, wobble: 0.05, n: 20 });
      K.fill();
    });
    Rd.beginPath();
    B.blob(Rd, gc[0], gc[1], gr * 0.97, { seed: 3, wobble: 0.05, n: 20 });
    Rd.fill();
    cutList(Rd, ringCuts(gc[0], gc[1], gr * 0.25, gr * 0.92, 2.6 * U, 0.7 * U, 53));
    const grow = B.clamp(0.35 + lt * 0.45); ashCloud(gc[0], gc[1] - gr * 0.35, gr * 0.75, grow, 54, true);
    const cone = conePts(X(ax), Y(ay), X(bl), X(br), Y(by), BX.w * 0.09, 55);
    fillPoly(K, cone); silhouetteCut(cone, 57); cutList(K, coneCuts(X(ax), Y(ay), X(bl), X(br), Y(by), 56, 34));
    lavaSpray(X(ax), Y(ay), gr * 0.9, 26, B.clamp(0.3 + lt * 0.6), 57);
    for (const side of [-1, 1]) {
      const run = B.clamp((lt - 0.4) / 1.0);
      const path = B.quad(X(ax) + side * 1.5 * U, Y(ay) + U, X(ax) + side * BX.w * 0.12, B.lerp(Y(ay), Y(by), 0.45), X(ax) + side * BX.w * (P ? 0.3 : 0.24), Y(by) - U, 20);
      const seg = B.trim(path, 0, Math.max(0.05, run));
      cut(K, seg, 2.8 * U, { tear: true, seed: side + 3 });
      cut(Rd, seg, 3.0 * U, { tear: true, ink: true, seed: side + 3 });
    }
    ground(Y(0.9), 58);
    bandLabel("3 ERUPTION!", P ? X(0.5) : X(0.5), P ? Y(0.1) : Y(0.12), (P ? 8 : 7.5) * U, B.clamp((lt - 0.55) / 0.5), 59);
  }

  function sceneClose(ts) {
    block(61); const lt = ts - BEATS[5];
    const ax = 0.5, ay = P ? 0.32 : 0.3, bl = P ? 0.03 : 0.16, br = P ? 0.97 : 0.84, by = 0.9;
    cutList(K, skyCuts({ x: BX.x, y: BX.y, w: BX.w, h: BX.h * 0.9 }, 62, 0.9));
    const layers = 5;
    for (let i = 0; i < layers; i++) {
      const k = i / layers, sh = (1 - k) * 0.06;
      const cone = conePts(X(ax), B.lerp(Y(ay), Y(by), k * 0.62), X(bl + k * 0.18), X(br - k * 0.18), Y(by), BX.w * 0.08, 63 + i);
      fillPoly(K, cone);
      if (i < layers - 1) {
        const outline = cone.slice(2, -2);
        cut(K, outline, (0.9 + sh * 6) * U, { seed: i });
      }
    }
    const top = conePts(X(ax), Y(ay), X(bl + 0.02), X(br - 0.02), Y(by), BX.w * 0.08, 63);
    const band = top.filter(([, y]) => y < B.lerp(Y(ay), Y(by), 0.2));
    clearPoly(K, band); fillPoly(Rd, band.map(([x, y]) => [x, y - 0.3 * U]));
    cutList(K, coneCuts(X(ax), Y(ay), X(bl), X(br), Y(by), 64, 24).filter((c) => c.pts[0][1] > B.lerp(Y(ay), Y(by), 0.2)));
    ground(Y(0.9), 65);
    bandLabel(P ? "EACH ERUPTION" : "EACH ERUPTION ADDS A LAYER", X(0.5), Y(P ? 0.08 : 0.1), (P ? 7 : 6.2) * U, B.clamp((lt - 0.45) / 0.6), 66);
    if (P) bandLabel("ADDS A LAYER", X(0.5), Y(0.19), 7 * U, B.clamp((lt - 0.8) / 0.5), 67);
  }
  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneErupt, sceneClose];

  // ---- ink finishing (what makes it a print)
  /** Noise fields: edge raggedness, and where the ink skips (clustered speckle). */
  function fields(W, H) {
    const key = "lino-fields:" + W + "x" + H; if (fields.cache && fields.cache.key === key) return fields.cache;
    const s = 2, w = Math.ceil(W / s), h = Math.ceil(H / s), edge = new Float32Array(w * h), speck = new Float32Array(w * h);
    const u = Math.min(W, H) / 100;
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        const i = y * w + x, fx = x * s, fy = y * s;
        edge[i] = B.noise2(fx / (0.35 * u), fy / (0.35 * u), 1) * 0.6 + B.noise2(fx / (1.2 * u), fy / (1.2 * u), 2) * 0.4;
        const patch = B.noise2(fx / (9 * u), fy / (9 * u), 3) * 0.6 + B.noise2(fx / (3 * u), fy / (3 * u), 4) * 0.4;
        speck[i] = patch * 0.55 + B.hash01(x, y) * 0.6;
      }
    fields.cache = { key, w, h, s, edge, speck };
    return fields.cache;
  }
  /** Finish an ink layer: softened, cut against noise (ragged edges), speckled. */
  function finishInk(src, out, hex, F, speckAmt) {
    const W = src.canvas.width, H = src.canvas.height, f = fields(W, H); const soft = B.scratch("lino-soft", W, H);
    soft.filter = `blur(${(0.09 * F.u).toFixed(2)}px)`;
    soft.drawImage(src.canvas, 0, 0); soft.filter = "none";
    const img = soft.getImageData(0, 0, W, H), d = img.data, [r, g, b] = B.rgb(hex);
    const thrSpeck = 0.86 - speckAmt;
    for (let y = 0; y < H; y++) {
      const row = ((y / f.s) | 0) * f.w;
      for (let x = 0; x < W; x++) {
        const o = (y * W + x) * 4, a = d[o + 3]; let on = false;
        if (a > 8) {
          const i = row + ((x / f.s) | 0); on = a > 128 + f.edge[i] * 70;
          if (on && f.speck[i] > thrSpeck + (255 - a) / 600) on = false;
        }
        d[o] = r; d[o + 1] = g; d[o + 2] = b; d[o + 3] = on ? 255 : 0;
      }
    }
    out.getContext("2d").putImageData(img, 0, 0);
  }
  // a cache of finished prints: (scene, pull) -> { k, r }
  const PRINTS = new Map();
  function printFor(F, scene, step) {
    const key = `${scene}:${step}:${F.W}x${F.H}`;
    if (PRINTS.has(key)) {
      const v = PRINTS.get(key); PRINTS.delete(key); PRINTS.set(key, v); return v;
    }
    let reuse = null;
    if (PRINTS.size >= 4) {
      const old = PRINTS.keys().next().value; reuse = PRINTS.get(old); PRINTS.delete(old);
      if (reuse.k.width !== F.W || reuse.k.height !== F.H) reuse = null;
    }
    const v = reuse || { k: B.canvas(F.W, F.H), r: B.canvas(F.W, F.H) };
    K = B.scratch("lino-k", F.W, F.H); Rd = B.scratch("lino-r", F.W, F.H);
    K.fillStyle = Rd.fillStyle = "#000"; SCENES[scene](BEATS[scene] + step / STEP);
    finishInk(K, v.k, PAL.black, F, 0.06); finishInk(Rd, v.r, PAL.red, F, 0.05);
    PRINTS.set(key, v); return v;
  }

  // ---- the sheet: paper, the two inks, pencil
  /** Long thin pale and tan fibres for the paper (cached). */
  function fibres(W, H) {
    return B.layer("lino-fibres", W, H, (g, w, h) => {
      const r = B.rng(8), u = Math.min(w, h) / 100; g.lineCap = "round";
      for (let i = 0; i < (w * h) / (u * u) * 0.09; i++) {
        const x = r() * w, y = r() * h, a = r() * B.TAU, l = r.range(2.5, 8) * u;
        g.strokeStyle = r() < 0.55 ? B.rgba(PAL.fibre, 0.55) : B.rgba("#fbf6ea", 0.6);
        g.lineWidth = r.range(0.05, 0.12) * u; g.beginPath(); g.moveTo(x, y);
        g.quadraticCurveTo(x + Math.cos(a + 0.4) * l * 0.5, y + Math.sin(a + 0.4) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l);
        g.stroke();
      }
    });
  }
  /** Pencil: grey, grainy, skipping across the tooth. */
  function pencil(ctx, F, scene, t, items) {
    const g = B.scratch("lino-pencil", F.W, F.H); g.fillStyle = g.strokeStyle = PAL.graphite;
    items.forEach((it) => {
      if (it.ring) {
        const p = B.clamp(it.p);
        if (p > 0) B.handCircle(g, it.x, it.y, it.r, { width: 0.45 * F.u, color: PAL.graphite, amp: 0.6 * F.u, seed: it.seed || 3, passes: 2, p, start: -2.2 });
        return;
      }
      g.font = B.font(it.size, PEN, 400); g.textAlign = it.align || "left"; g.textBaseline = "middle";
      g.fillText(B.typewriter(it.text, it.p ?? 1), it.x, it.y);
    });
    const tooth = B.layer("lino-tooth", 256, 256, (q, w, h) => {
      const r = B.rng(91), img = q.createImageData(w, h);
      for (let i = 0; i < w * h; i++) img.data[i * 4 + 3] = r() < 0.26 ? 255 : 0; q.putImageData(img, 0, 0);
    });
    g.globalCompositeOperation = "destination-out"; g.fillStyle = g.createPattern(tooth, "repeat");
    g.fillRect(0, 0, F.W, F.H); g.globalCompositeOperation = "source-over";
    ctx.save(); ctx.globalAlpha = 0.85; ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(g.canvas, 0, 0); ctx.restore();
  }
  function pencilItems(F, scene, t) {
    const S = F.safe, u = F.u, by = BX.y + BX.h, my = by + (P ? 4.6 : 4.4) * u, sz = (P ? 7.6 : 6.4) * u;
    const items = [
      { text: "Eruption", x: BX.x + u, y: my, size: sz },
      { text: "3/20", x: X(P ? 0.55 : 0.6), y: my, size: sz, align: "center" },
      { text: "k. odell  '26", x: BX.x + BX.w - u, y: my, size: sz, align: "right" },
    ]; const lt = t - BEATS[scene];
    return items;
  }
  /** One sheet: paper, pressed outline, red then black (where each peel front has passed), pencil. */
  function sheet(ctx, F, scene, t, frontR, frontK) {
    B.paper(ctx, F.W, F.H, { color: PAL.paper, seed: 6, mottle: 0.1, fibers: 0.25, specks: 0.2, tooth: 0.07 });
    ctx.drawImage(fibres(F.W, F.H), 0, 0); const pad = 1.2 * F.u;
    ctx.save(); ctx.lineWidth = 0.25 * F.u; ctx.strokeStyle = "rgba(120,95,60,0.35)";
    ctx.strokeRect(BX.x - pad, BX.y - pad, BX.w + 2 * pad, BX.h + 2 * pad); ctx.strokeStyle = "rgba(255,252,240,0.7)";
    ctx.strokeRect(BX.x - pad - 0.3 * F.u, BX.y - pad - 0.3 * F.u, BX.w + 2 * pad + 0.6 * F.u, BX.h + 2 * pad + 0.6 * F.u);
    ctx.restore();
    const step = Math.min(Math.floor((t - BEATS[scene]) * STEP + 1e-6), Math.round((DUR - BEATS[scene]) * STEP));
    const pr = printFor(F, scene, Math.max(0, step));
    const layer = (img, front, dx, dy) => {
      if (front <= -0.2) return;
      B.clip(ctx, (g) => diagPath(g, F, front), () => {
        ctx.globalCompositeOperation = "multiply"; ctx.drawImage(img, dx, dy);
      });
    };
    layer(pr.r, frontR, 0.55 * F.u, 0.3 * F.u); // red lands off register
    layer(pr.k, frontK, 0, 0);
    pencil(ctx, F, scene, t, pencilItems(F, scene, t));
  }
  /** The peel front: the region x/W + y/H < 2 * front (a diagonal sweep from the top left). */
  function diagPath(g, F, front) {
    const c = 2 * front, W = F.W, H = F.H; g.beginPath(); g.moveTo((c + 3) * W, -3 * H);
    g.lineTo((c - 3) * W, 3 * H); g.lineTo(-6 * W, -6 * H); g.closePath();
  }

  // ---- frame
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H); const jolt = t > 8.85 && t < 9.1 ? (1 - (t - 8.85) / 0.25) * F.u * 0.7 : 0;
    if (jolt) {
      ctx.fillStyle = PAL.paper; ctx.fillRect(0, 0, W, H); ctx.translate(0, jolt * (Math.floor(t * 24) % 2 ? 1 : -1));
    }
    P = F.portrait;
    BX = P ? { x: W * 0.06, y: H * 0.145, w: W * 0.88, h: H * 0.6 } : { x: W * 0.07, y: H * 0.07, w: W * 0.86, h: H * 0.72 };
    U = Math.min(BX.w, BX.h) / 100; const b = B.beat(t, BEATS, DUR), scene = b.i;
    const pp = B.clamp((t - BEATS[scene]) / PEEL);
    const fR = B.lerp(-0.15, 1.15, B.ease.inOutSine(pp)), fK = B.lerp(-0.15, 1.15, B.ease.inOutSine(B.clamp(pp * 1.25 - 0.25)));
    if (pp < 1) {
      if (scene > 0) sheet(ctx, F, scene - 1, BEATS[scene] - 0.001, 2, 2);
      else B.paper(ctx, W, H, { color: PAL.paper, seed: 6, mottle: 0.1, fibers: 0.25, specks: 0.2, tooth: 0.07 });
      const fP = Math.max(fR, fK) + 0.02;
      B.clip(ctx, (g) => diagPath(g, F, fP), () => sheet(ctx, F, scene, t, fR, fK));
      const c = 2 * fP, n = Math.hypot(1 / W, 1 / H), sw = 4 * F.u;
      const x0 = (c / 2) * W, y0 = (c / 2) * H; // a point on the front line
      const dx = 1 / W / n, dy = 1 / H / n; // unit normal pointing ahead of the front
      ctx.save();
      ctx.fillStyle = B.linear(ctx, x0, y0, x0 + dx * sw, y0 + dy * sw, [[0, "rgba(40,28,20,0.28)"], [1, "rgba(40,28,20,0)"]]);
      ctx.beginPath(); ctx.moveTo((c + 3) * W, -3 * H); ctx.lineTo((c - 3) * W, 3 * H);
      ctx.lineTo((c - 3) * W + dx * sw * 3, 3 * H + dy * sw * 3);
      ctx.lineTo((c + 3) * W + dx * sw * 3, -3 * H + dy * sw * 3); ctx.closePath(); ctx.fill(); ctx.restore();
    } else sheet(ctx, F, scene, t, 2, 2);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    B.vignette(ctx, W, H, { color: "#9c7a52", amount: 0.2, inner: 0.5, mode: "multiply" });
  }

  // ---- sound: v-gouge scrapes, tacky peels, the press, pencil
  SOUND.define("lino-gouge", (v, o) => {
    const d = o.dur ?? 0.35;
    v.grains({ span: d, count: Math.round(d * 70), filter: "bandpass", f: 1900, q: 1.4, len: 0.012, peak: 0.32, vary: 0.6 });
    v.noise({ filter: "bandpass", f: 1200, f2: 2400, glide: d, q: 2.5, a: 0.02, hold: d * 0.6, len: d * 0.4, peak: 0.12 });
  }, { verb: 0.08 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.7 });
    BEATS.forEach((b, i) => k.at(b + 0.02, "paper", { dur: PEEL, gain: i === 0 ? 0.8 : 0.7 }));
    k.at(0.6, "lino-gouge", { dur: 0.9, gain: 0.7 });
    k.at(2.75, "lino-gouge", { dur: 0.6 }).at(3.3, "lino-gouge", { dur: 0.8, gain: 0.8 });
    k.repeat(4.3, 0.125, 8, "knock", { gain: 0.35, vary: 3 });
    k.at(5.2, "pencil", { dur: 0.6, gain: 0.8 }).at(5.45, "scribble", { dur: 0.55, gain: 0.5 });
    [6.55, 7.15, 7.7].forEach((a) => k.at(a, "lino-gouge", { dur: 0.45, gain: 0.8 }));
    k.at(8.85, "stamp", { gain: 1 }).at(8.85, "thud", { gain: 0.7 }).at(8.9, "boom", { gain: 0.35 });
    k.at(9.0, "lino-gouge", { dur: 0.8, gain: 0.6 });
    k.at(10.8, "lino-gouge", { dur: 0.6, gain: 0.6 }).at(11.2, "pencil", { dur: 0.5, gain: 0.8 }).at(11.35, "scribble", { dur: 0.6, gain: 0.5 });
    k.at(1.2, "pencil", { dur: 0.4, gain: 0.4 });
  }

  Player.register({
    id: "linocut", name: "Linocut Print", duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Bowlby+One&family=Nanum+Pen+Script&display=swap",
      faces: ['400 20px "Bowlby One"', '400 20px "Nanum Pen Script"'],
    },
    beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Steps", "Eruption", "Close"],
    stills: [1.8, 3.9, 6.0, 8.1, 10.1, 11.8],
    draw, score,
  });
})();
