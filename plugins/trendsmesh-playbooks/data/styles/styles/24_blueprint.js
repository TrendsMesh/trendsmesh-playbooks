/* 24 Blueprint - reference animation.
 * Topic (setting, replace it): "How does a water tower make pressure?" - about 1 bar for every 10 m of height.
 * Rendering (keep it): deep cyan-blue sheets (lighter centre, darker corners, faint mottling and fold creases) with a
 * fine pale grid, every fifth line stronger, and a thin border with tick marks and grid references. All drawing is
 * thin pale line work in model units (metres) on a line layer: outlines, dashed hidden lines, long-short centre
 * lines, diagonal hatching on cut surfaces, dimension lines with extension ticks and narrow closed arrow heads,
 * circled part tags on leader lines, a ruled quantity table and a boxed title block, all lettered in wide-spaced
 * monospaced capitals. The line layer is printed with a hair of bleed. Yellow is used once per idea, for emphasis
 * only: a revision cloud, a bracket, the approval stamp.
 * Motion: a plotter pen draws every line end to end at a steady speed, group by group; dimension arrows slide out
 * from the middle and their value types in; sheets change by a new sheet sliding over the old.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { deep: "#0f3a78", light: "#1a58a6", grid: "#3f7cc4", line: "#e8f1ff", dim: "#9fc2ee", yellow: "#ffd95a" };
  const MONO = "IBM Plex Mono", MONO2 = "Space Mono";
  const DUR = 13;
  const BEATS = [0, 2.3, 4.9, 7.5, 9.7, 11.3];

  const STEP_AT = [7.9, 8.7, 9.75];
  let G = null, U = 1, T = 0; // the current sheet's line layer, frame unit, time

  // ------------------------------------------------------------------ drafting helpers (reuse these)
  /**
   * Plot strokes like a pen plotter: each stroke is drawn end to end at a steady speed (px/s), one after another
   * from t0. stroke: { pts, w (px), c (colour), dash ([on, off] px) }. Returns the time the pen lifts.
   */
  function plot(strokes, t0, speed) {
    let at = t0;
    for (const s of strokes) {
      const len = B.pathLength(s.pts), d = len / speed, p = B.clamp((T - at) / Math.max(1e-3, d));
      if (p > 0) {
        // a tiny line-weight wobble so the ink looks printed, not computed
        const w = (s.w ?? 0.22 * U) * (1 + 0.08 * B.noise1(len * 0.01 + at, 3));
        B.strokeReveal(G, s.pts, p, { width: w, color: s.c || PAL.line, dash: s.dash, cap: "butt", join: "miter" });
      }
      at += d;
    }
    return at;
  }
  /** Diagonal hatch strokes for a cut surface inside a rectangle (as plot strokes). */
  function hatchStrokes(x, y, w, h, gap, c = PAL.dim) {
    const out = [];
    for (let k = -h; k < w; k += gap) {
      const x0 = x + Math.max(0, k), y0 = y + h - Math.max(0, -k), x1 = x + Math.min(w, k + h), y1 = y + h - Math.min(h, k + h);
      if (x1 > x0) out.push({ pts: [[x0, y0], [x1, y1]], w: 0.14 * U, c });
    }
    return out;
  }
  /** Narrow closed arrow head at (x, y) pointing along angle a. */
  function head(x, y, a, len, c = PAL.line) {
    G.fillStyle = c;
    G.beginPath();
    G.moveTo(x, y);
    G.lineTo(x - Math.cos(a - 0.2) * len, y - Math.sin(a - 0.2) * len);
    G.lineTo(x - Math.cos(a + 0.2) * len, y - Math.sin(a + 0.2) * len);
    G.closePath();
    G.fill();
  }
  /** Monospaced capitals, widely spaced, typed in as p goes 0 -> 1. o: { size, italic (notes), align, weight, color } */
  function type(str, x, y, size, p, o = {}) {
    if (p <= 0) return null;
    return B.text(G, String(str).toUpperCase(), x, y, { size, family: o.family || MONO, weight: o.weight ?? 500, style: o.italic ? "italic" : "", color: o.color || PAL.line, align: o.align || "left", baseline: o.baseline || "middle", letterSpacing: o.ls ?? 0.14, reveal: p, lineH: 1.35, maxW: o.maxW });
  }
  /**
   * Dimension line between a and b (screen points), offset sideways: extension ticks from the object, then the
   * dimension line sliding out from the middle to both ends (p), closed arrow heads, and the value typed in (pv)
   * in a gap at the middle. o: { off (px, perpendicular), size, color }
   */
  function dimension(a, b, label, p, pv, o = {}) {
    if (p <= 0) return;
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), nx = -Math.sin(ang), ny = Math.cos(ang), off = o.off ?? 4 * U;
    const A = [a[0] + nx * off, a[1] + ny * off], Bp = [b[0] + nx * off, b[1] + ny * off], c = o.color || PAL.line;
    for (const [q, Q] of [[a, A], [b, Bp]]) B.strokeReveal(G, [[q[0] + nx * U * 0.8, q[1] + ny * U * 0.8], [Q[0] + nx * U * 1.2, Q[1] + ny * U * 1.2]], B.clamp(p * 3), { width: 0.14 * U, color: PAL.dim, cap: "butt" });
    const k = B.ease.outCubic(B.clamp(p * 1.4 - 0.2)), mid = [(A[0] + Bp[0]) / 2, (A[1] + Bp[1]) / 2];
    const e1 = [B.lerp(mid[0], A[0], k), B.lerp(mid[1], A[1], k)], e2 = [B.lerp(mid[0], Bp[0], k), B.lerp(mid[1], Bp[1], k)];
    const gap = (o.size ?? 3 * U) * 0.9;
    const cut = (from, to) => {
      const d = Math.hypot(to[0] - from[0], to[1] - from[1]);
      if (d <= gap) return;
      const f = gap / d;
      B.strokeReveal(G, [[B.lerp(from[0], to[0], f), B.lerp(from[1], to[1], f)], to], 1, { width: 0.18 * U, color: c, cap: "butt" });
    };
    cut(mid, e1);
    cut(mid, e2);
    if (k > 0.05) {
      head(e1[0], e1[1], ang + Math.PI, 2.2 * U, c);
      head(e2[0], e2[1], ang, 2.2 * U, c);
    }
    G.save();
    G.translate(mid[0], mid[1]);
    G.rotate(Math.abs(ang) > Math.PI / 2 ? ang + Math.PI : ang);
    type(label, 0, 0, o.size ?? 3 * U, pv, { align: "center", weight: 600, color: c });
    G.restore();
  }
  /** Circled part number on a leader line ending in a dot at the target. */
  function tag(n, at, target, p) {
    if (p <= 0) return;
    const r = 3.3 * U;
    B.strokeReveal(G, [target, at], B.clamp(p * 2), { width: 0.16 * U, color: PAL.line, cap: "butt" });
    G.fillStyle = PAL.line;
    G.beginPath();
    B.circle(G, target[0], target[1], 0.45 * U);
    G.fill();
    const k = B.clamp(p * 2 - 0.6);
    if (k <= 0) return;
    G.strokeStyle = PAL.line;
    G.lineWidth = 0.2 * U;
    G.beginPath();
    G.arc(at[0], at[1], r, -Math.PI / 2, -Math.PI / 2 + B.TAU * k);
    G.stroke();
    G.fillStyle = B.mix(PAL.deep, PAL.light, 0.6);
    G.beginPath();
    B.circle(G, at[0], at[1], r - 0.15 * U);
    G.fill();
    type(String(n), at[0], at[1] + 0.1 * U, 4 * U, B.clamp(k * 2), { align: "center", ls: 0, weight: 600 });
  }
  /** Revision cloud: a ring of scalloped arcs round a rectangle, in the one accent colour, drawn on by p. */
  function revCloud(x, y, w, h, p) {
    if (p <= 0) return;
    const r = 1.6 * U, pts = B.densify(B.rectPts(x, y, w, h), r * 1.8), n = pts.length - 1, upto = Math.floor(n * B.clamp(p));
    G.save();
    G.strokeStyle = PAL.yellow;
    G.lineWidth = 0.32 * U;
    G.beginPath();
    for (let i = 0; i < upto; i++) {
      const a = pts[i], b = pts[i + 1], mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      const rr = Math.hypot(b[0] - a[0], b[1] - a[1]) / 2;
      G.moveTo(a[0], a[1]);
      G.arc(mx, my, rr, ang + Math.PI, ang + B.TAU, false);
    }
    G.stroke();
    G.restore();
  }

  // ------------------------------------------------------------------ the sheet (paper, grid, border, title block)
  function paper(ctx, W, H, ox) {
    const c = B.layer("bp-paper", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100;
      g.fillStyle = B.radial(g, w * 0.5, h * 0.45, 0, Math.hypot(w, h) * 0.62, [PAL.light, B.mix(PAL.light, PAL.deep, 0.55), PAL.deep]);
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: 0.12, feature: 0.08, seed: 6, mode: "soft-light" });
      // two faint fold creases: a light ridge beside a dark valley
      for (const [x0, y0, x1, y1] of [[w * 0.5, 0, w * 0.5, h], [0, h * 0.5, w, h * 0.5]]) {
        g.strokeStyle = "rgba(255,255,255,0.05)";
        g.lineWidth = 0.6 * u;
        g.beginPath();
        g.moveTo(x0, y0);
        g.lineTo(x1, y1);
        g.stroke();
        g.strokeStyle = "rgba(0,0,30,0.12)";
        g.lineWidth = 0.25 * u;
        g.beginPath();
        g.moveTo(x0 + (x0 === x1 ? 0.5 * u : 0), y0 + (y0 === y1 ? 0.5 * u : 0));
        g.lineTo(x1 + (x0 === x1 ? 0.5 * u : 0), y1 + (y0 === y1 ? 0.5 * u : 0));
        g.stroke();
      }
    });
    const gr = B.layer("bp-grid", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, step = 2.4 * u;
      for (let i = 0, x = 0; x <= w; x += step, i++) {
        g.fillStyle = B.rgba(PAL.grid, i % 5 ? 0.35 : 0.7);
        g.fillRect(Math.round(x), 0, i % 5 ? 1 : Math.max(1, 0.18 * u), h);
      }
      for (let i = 0, y = 0; y <= h; y += step, i++) {
        g.fillStyle = B.rgba(PAL.grid, i % 5 ? 0.35 : 0.7);
        g.fillRect(0, Math.round(y), w, i % 5 ? 1 : Math.max(1, 0.18 * u));
      }
    });
    ctx.drawImage(c, ox, 0);
    return gr;
  }
  /** Border frame with ticks and grid references (letters kept where text is safe). */
  function borderStrokes(L) {
    const { W, H } = L.F, m = 2.6 * L.u, out = [{ pts: B.rectPts(m, m, W - 2 * m, H - 2 * m), w: 0.3 * L.u }, { pts: B.rectPts(m + 0.9 * L.u, m + 0.9 * L.u, W - 2 * m - 1.8 * L.u, H - 2 * m - 1.8 * L.u), w: 0.14 * L.u, c: PAL.dim }];
    const n = L.P ? [4, 8] : [8, 4];
    for (let i = 1; i < n[0]; i++) {
      const x = m + ((W - 2 * m) * i) / n[0];
      out.push({ pts: [[x, m], [x, m + 0.9 * L.u]], w: 0.14 * L.u }, { pts: [[x, H - m], [x, H - m - 0.9 * L.u]], w: 0.14 * L.u });
    }
    for (let i = 1; i < n[1]; i++) {
      const y = m + ((H - 2 * m) * i) / n[1];
      out.push({ pts: [[m, y], [m + 0.9 * L.u, y]], w: 0.14 * L.u }, { pts: [[W - m, y], [W - m - 0.9 * L.u, y]], w: 0.14 * L.u });
    }
    return out;
  }
  /** Grid references on the border: texture (nobody reads them), so they stay small. */
  function borderLetters(L, p) {
    B.texture(G, () => borderRefs(L, p));
  }
  function borderRefs(L, p) {
    const { W, H } = L.F, m = 2.6 * L.u, n = L.P ? [4, 8] : [8, 4], s = 1.5 * L.u;
    for (let i = 0; i < n[1]; i++) {
      const y = m + ((H - 2 * m) * (i + 0.5)) / n[1];
      if (y < L.S.y || y > L.S.b) continue;
      type(String.fromCharCode(65 + i), m + 0.45 * L.u, y, s, p, { align: "center", ls: 0, color: PAL.dim });
      type(String.fromCharCode(65 + i), W - m - 0.45 * L.u, y, s, p, { align: "center", ls: 0, color: PAL.dim });
    }
    if (L.P) return;
    for (let i = 0; i < n[0]; i++) {
      const x = m + ((W - 2 * m) * (i + 0.5)) / n[0];
      type(String(i + 1), x, m + 0.5 * L.u, s, p, { align: "center", ls: 0, color: PAL.dim });
      type(String(i + 1), x, H - m - 0.5 * L.u, s, p, { align: "center", ls: 0, color: PAL.dim });
    }
  }
  /** Title block in the lower right: boxed cells with sheet name, scale, date and a revision list. */
  function titleBlock(L, sheetName, t0) {
    const u = L.u, S = L.S, w = L.P ? 50 * u : 44 * u, h = L.P ? 11 * u : 13 * u, x = S.r - w, y = L.P ? L.F.H * 0.835 : S.b - h; // portrait: in the sheet's foot (its cells are texture)
    G.fillStyle = B.mix(PAL.deep, PAL.light, 0.5);
    G.globalAlpha = B.smooth(t0, t0 + 0.2, T);
    G.fillRect(x, y, w, h);
    G.globalAlpha = 1;
    const st = [{ pts: B.rectPts(x, y, w, h), w: 0.3 * u }, { pts: [[x, y + h * 0.42], [x + w, y + h * 0.42]] }, { pts: [[x + w * 0.5, y + h * 0.42], [x + w * 0.5, y + h]] }, { pts: [[x, y + h * 0.71], [x + w, y + h * 0.71]] }];
    const end = plot(st, t0, 260 * u);
    // the cells' tiny capitals are texture: the title block is there to make the sheet real, not to be read
    const s = (L.P ? 1.85 : 1.6) * u, pt = (a) => B.prog(T, end + a, 0.35);
    B.texture(G, () => {
      type(sheetName, x + 1.2 * u, y + h * 0.21, s * 1.25, pt(0), { weight: 600 });
      type("Scale 1:500", x + 1.2 * u, y + h * 0.565, s, pt(0.1));
      type("Date 11.2026", x + w * 0.5 + 1.2 * u, y + h * 0.565, s, pt(0.15));
      type("Rev A  issued", x + 1.2 * u, y + h * 0.855, s, pt(0.2), { color: PAL.dim });
      type("Drawn  TM", x + w * 0.5 + 1.2 * u, y + h * 0.855, s, pt(0.25), { color: PAL.dim });
    });
  }

  // ------------------------------------------------------------------ layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    const pm = P ? 1.25 * u : 1.2 * u; // px per metre at the drawing's scale
    const ox = P ? S.x + 19 * u : S.x + 19.5 * u, gy = P ? S.b - 28.5 * u : S.b - 4 * u;
    // dx: the tap and house sit closer in portrait; dimX: where the height is dimensioned (beside the tower in portrait)
    const dx = P ? -4 : 0, dimX = P ? 12 : 37;
    return { F, u, P, S, pm, ox, gy, dx, dimX, M: (x, y) => [ox + x * pm, gy - y * pm], head: P ? 5.4 * u : 5 * u, lab: 3.95 * u };
  }

  // ------------------------------------------------------------------ the water tower (the setting: replace it)
  function towerStrokes(L) {
    const u = L.u, thick = 0.36 * u, thin = 0.2 * u, A = [], Bk = [];
    const M = (x, y) => L.M(x > 12 ? x + L.dx : x, y); // the site beyond the tower moves with dx
    const line = (arr, pts, w = thin, c, dash) => arr.push({ pts: pts.map(([x, y]) => M(x, y)), w, c, dash });
    // group A: ground, legs, tank, roof
    line(A, [[-12, 0], [35, 0]], thick);
    line(A, [[-7, 32], [-10, 0]], thick);
    line(A, [[7, 32], [10, 0]], thick);
    line(A, [[-7, 32], [7, 32], [7, 42], [-7, 42], [-7, 32]], thick);
    line(A, [[-7.6, 42], [0, 45.5], [7.6, 42]], thick);
    // group B: bracing, riser, main, house, tap, water level, centre line, ground hatching
    [[0, 10.5], [10.5, 21], [21, 32]].forEach(([a, b]) => {
      const xa = (y) => -10 + (3 * y) / 32;
      line(Bk, [[xa(a), a], [-xa(b), b]]);
      line(Bk, [[-xa(a), a], [xa(b), b]]);
      line(Bk, [[xa(b), b], [-xa(b), b]]);
    });
    line(Bk, [[-0.7, 32], [-0.7, 0]]);
    line(Bk, [[0.7, 32], [0.7, 0]]);
    line(Bk, [[-0.7, 0], [-0.7, -2.6], [24.3, -2.6], [24.3, 1]], thin, PAL.dim, [1.2 * u, 0.7 * u]);
    line(Bk, [[0.7, 0], [0.7, -1.4], [23.1, -1.4], [23.1, 1]], thin, PAL.dim, [1.2 * u, 0.7 * u]);
    line(Bk, [[23.1, 1], [23.1, 2.2], [21.6, 2.2]], thick);
    line(Bk, [[24.3, 1], [24.3, 3.4], [21.6, 3.4]], thick);
    line(Bk, [[23.7, 3.4], [23.7, 5.2]], thin);
    line(Bk, [[22.4, 5.2], [25, 5.2]], thick);
    line(Bk, [[26, 0], [26, 7], [34, 7], [34, 0]], thick);
    line(Bk, [[25.4, 7], [30, 11], [34.6, 7]], thick);
    line(Bk, [[28.5, 0], [28.5, 4], [31, 4], [31, 0]]);
    line(Bk, [[-6.8, 40], [6.8, 40]], thin, PAL.dim, [1.6 * u, 0.6 * u]);
    line(Bk, [[0, -4], [0, 48]], 0.14 * u, PAL.dim, [2.6 * u, 0.6 * u, 0.5 * u, 0.6 * u]);
    const [gx0, gy0] = M(-12, 0), [gx1, gy1] = M(35, -4.5);
    return { A, Bk, hatch: hatchStrokes(gx0, gy0, gx1 - gx0, gy1 - gy0, 1.3 * u) };
  }
  /** Water-level symbol: a small inverted triangle on the surface with two short lines under it. */
  function waterMark(L, p) {
    if (p <= 0) return;
    const [x, y] = L.M(4, 40), s = 1.3 * L.u;
    G.globalAlpha = p;
    G.strokeStyle = PAL.line;
    G.lineWidth = 0.16 * L.u;
    G.beginPath();
    G.moveTo(x - s, y - s * 1.2);
    G.lineTo(x + s, y - s * 1.2);
    G.lineTo(x, y);
    G.closePath();
    G.moveTo(x - s * 0.7, y + s * 0.5);
    G.lineTo(x + s * 0.7, y + s * 0.5);
    G.moveTo(x - s * 0.35, y + s * 0.9);
    G.lineTo(x + s * 0.35, y + s * 0.9);
    G.stroke();
    G.globalAlpha = 1;
  }
  /** Flow arrows (thin line, narrow closed head) along the riser, the main and up to the tap. */
  function flow(L, p) {
    const M = L.M, u = L.u;
    [[[2.2, 30], [2.2, 6]], [[3, -4.2], [20 + L.dx, -4.2]], [[26.5 + L.dx, -1.2], [26.5 + L.dx, 2.5]]].forEach((seg, i) => {
      const k = B.clamp(p * 3 - i);
      if (k <= 0) return;
      const pts = seg.map(([x, y]) => M(x, y)), e = B.pointAt(pts, k);
      B.strokeReveal(G, pts, k, { width: 0.2 * u, color: PAL.line, cap: "butt" });
      head(e[0], e[1], e[2], 2 * u);
    });
  }

  function sheetOne(L, W, H) {
    const u = L.u, P = L.P, S = L.S, M = L.M, sx = (x) => (x > 12 ? x + L.dx : x);
    // border first, then the title, the tower in two pen groups, notes and tags
    const bEnd = plot(borderStrokes(L), 0.0, 900 * u);
    borderLetters(L, B.prog(T, bEnd, 0.4));
    type("How a water tower\nmakes pressure", S.x + 1.5 * u, S.y + 1 * u, L.head, B.prog(T, 0.3, 0.9), { baseline: "top", weight: 600, family: MONO2, ls: 0.06 });
    type("Sheet 1 / elevation", S.x + 1.5 * u, S.y + 2 * u + L.head * 2.75, L.lab, B.prog(T, 1.2, 0.5), { baseline: "top", color: PAL.dim, ls: 0.08 });
    titleBlock(L, "Water tower", 1.0);
    const tw = towerStrokes(L);
    // the whole elevation is drafted in the title beat; the table's frame and the parts list follow
    const aEnd = plot(tw.A, 0.7, 520 * u);
    const bEndT = plot(tw.Bk, aEnd, 900 * u);
    plot(tw.hatch, aEnd + 0.1, 1400 * u);
    if (P) {
      // a graphic scale bar under the ground: 5 m blocks, alternately inked
      const sb = (x) => M(x * 0.5 - 2, -12)[0], y = M(0, -12)[1], bh = 1.4 * u, k = B.prog(T, 1.5, 0.5);
      for (let i = 0; i < 4; i++) {
        if (k * 4 <= i) break;
        G.fillStyle = PAL.line;
        G.strokeStyle = PAL.line;
        G.lineWidth = 0.18 * u;
        if (i % 2 === 0) G.fillRect(sb(-10 + i * 10), y, sb(0) - sb(-10), bh);
        else G.strokeRect(sb(-10 + i * 10), y, sb(0) - sb(-10), bh);
      }
      [0, 10, 20].forEach((m, i) => type(m + (i === 2 ? " m" : ""), sb(m * 2 - 10), y + bh + 3 * u, L.lab, B.prog(T, 1.6 + i * 0.07, 0.15), { align: "center", ls: 0, color: PAL.dim }));
    }
    waterMark(L, B.prog(T, bEndT, 0.3));
    // circled part tags on leaders, and the parts list in the margin (two columns in portrait)
    const tl = P ? -13.5 : -15, tags = [[M(-7, 37), M(tl, 35)], [M(0.7, 18), M(tl - 0.5, 22)], [M(12, -2.6), P ? M(5, -7.4) : M(15.5, 5)], [M(sx(22.5), 5.2), P ? M(sx(25), -7.4) : M(19.5, 13)]];
    const names = ["Tank", "Riser pipe", "Main", "Tap"];
    tags.forEach(([target, at], i) => tag(i + 1, at, target, B.prog(T, BEATS[1] + 0.5 + i * 0.25, 0.45)));
    const lx = P ? M(16, 0)[0] : S.x + S.w * 0.47, ly = P ? S.y + L.head * 3 + 14 * u : S.y + 12 * u, rowH = L.lab * 1.6;
    const ph = type("Parts", lx, ly, L.lab, B.prog(T, 1.4, 0.25), { weight: 600 });
    if (ph) plot([{ pts: [[lx, ly + L.lab * 0.75], [lx + ph.width, ly + L.lab * 0.75]], w: 0.22 * u }], 1.6, 400 * u); // the list's own heading rule
    names.forEach((nm, i) => {
      const cx = P ? lx + (i % 2) * S.w * 0.27 : lx, cy = ly + (P ? 1 + Math.floor(i / 2) : i + 1) * rowH;
      type(`${i + 1} ${P ? nm.split(" ")[0] : " " + nm}`, cx, cy, L.lab, B.prog(T, 1.5 + i * 0.08, 0.2), { color: PAL.dim, ls: 0.08 });
    });
    flow(L, B.prog(T, BEATS[1] + 1.4, 1.0));
    // a ruled quantity table, its frame drafted early and filled at the key number
    const nt = BEATS[2], cw = P ? [19 * u, 22 * u] : [18 * u, 23 * u], rh = 5.4 * u;
    const tx = P ? lx : S.r - cw[0] - cw[1] - 3 * u, ty = P ? ly + 3 * rowH + 1.5 * u : ly - L.lab * 0.5;
    // the head row is drafted with its column heads now; the body rows draw on with their numbers
    const tw2 = cw[0] + cw[1], head = [{ pts: [[tx, ty + rh], [tx, ty], [tx + tw2, ty], [tx + tw2, ty + rh]], w: 0.26 * u }, { pts: [[tx, ty + rh], [tx + tw2, ty + rh]], w: 0.26 * u }, { pts: [[tx + cw[0], ty], [tx + cw[0], ty + rh]] }];
    const hEnd = plot(head, 1.5, 1200 * u);
    ["Height", "Pressure"].forEach((c, j) => type(c, tx + j * cw[0] + 1.2 * u, ty + rh * 0.5, L.lab, B.prog(T, hEnd + j * 0.04, 0.14), { color: PAL.dim, ls: 0.02 }));
    // key number: 40 m of water above the tap, the rule, the table filled in
    if (T > nt) {
      const ext = (y) => ({ pts: [M(7.5, y), M(L.dimX + 0.5, y)], w: 0.12 * u, c: PAL.dim, dash: [0.8 * u, 0.6 * u] });
      plot([ext(40)], nt + 0.05, 600 * u);
      dimension(M(L.dimX, 0), M(L.dimX, 40), "40 m", B.prog(T, nt + 0.3, 0.6), B.prog(T, nt + 0.8, 0.4), { off: 0, size: 3.95 * u });
      const body = [{ pts: [[tx, ty + rh], [tx, ty + rh * 4], [tx + tw2, ty + rh * 4], [tx + tw2, ty + rh]], w: 0.26 * u }, { pts: [[tx + cw[0], ty + rh], [tx + cw[0], ty + rh * 4]] }];
      for (let i = 2; i < 4; i++) body.push({ pts: [[tx, ty + rh * i], [tx + tw2, ty + rh * i]], w: 0.14 * u });
      const te = plot(body, nt + 0.6, 900 * u), rows = [[], ["10 m", "~1 bar"], ["20 m", "~2 bar"], ["40 m", "~4 bar"]];
      rows.forEach((row, i) => row.forEach((cell, j) => type(cell, tx + j * cw[0] + 1.2 * u, ty + rh * (i + 0.5), L.lab, B.prog(T, te + i * 0.12 + j * 0.05, 0.22), { weight: i ? 600 : 500, color: i ? PAL.line : PAL.dim, family: i ? MONO2 : MONO, ls: 0.02 })));
      // the one accent: a bracket on the answer row and a revision cloud round the tap
      const bx = tx + cw[0] + cw[1], bp = B.prog(T, te + 0.55, 0.3);
      if (bp > 0) B.strokeReveal(G, [[bx + 1.2 * u, ty + rh * 3 + 0.6 * u], [bx + 2.2 * u, ty + rh * 3 + 0.6 * u], [bx + 2.2 * u, ty + rh * 4 - 0.6 * u], [bx + 1.2 * u, ty + rh * 4 - 0.6 * u]], bp, { width: 0.32 * u, color: PAL.yellow, cap: "butt" });
      const [cx0, cy0] = M(sx(20.8), 6.6), [cx1, cy1] = M(sx(25.6), -0.6);
      revCloud(cx0, cy0, cx1 - cx0, cy1 - cy0, B.prog(T, te + 0.65, 0.4));
      // a slanted note: beside the house in portrait, under the parts list in landscape
      const nx = P ? M(sx(34), 0)[0] + 3.5 * u : lx, ny = P ? ty + rh * 4 + 3 * u : ly + 5 * rowH + 2 * u;
      type(P ? "Every 10 m\nadds ~1 bar" : "Every 10 m of height\nadds about 1 bar", nx, ny, L.lab, B.prog(T, te + 0.6, 0.4), { baseline: "top", italic: true, ls: 0.04, maxW: S.r - nx });
    }
  }

  function sheetTwo(L, W, H) {
    const u = L.u, P = L.P, S = L.S, t0 = BEATS[3];
    plot(borderStrokes(L), -10, 900 * u);
    borderLetters(L, 1);
    titleBlock(L, "Operation", -10);
    type("Sheet 2 / operating sequence", S.x + 1.5 * u, S.y + 1 * u, L.lab * 1.05, B.prog(T, t0 + 0.4, 0.6), { baseline: "top", weight: 600, family: MONO2, ls: 0.06 });
    const notes = ["Pump lifts water\nup to the tank", "Gravity pushes it\ndown the main", "Every tap gets\nsteady pressure"];
    const at = STEP_AT, n = 3;
    for (let i = 0; i < n; i++) {
      const bw = P ? S.w : (S.w - 4 * u) / 3, bh = P ? 28 * u : 54 * u;
      const x = P ? S.x : S.x + i * (bw + 2 * u), y = P ? S.y + 8 * u + i * (bh + 3 * u) : S.y + 10 * u;
      const lt = T - at[i];
      // every slot is marked first as a dashed frame, so the sheet shows the sequence still to come
      plot([{ pts: B.rectPts(x, y, bw, bh), w: 0.14 * u, c: PAL.dim, dash: [1.2 * u, 0.8 * u] }], t0 + 0.5 + i * 0.12, 1400 * u);
      if (lt < 0) continue;
      const pic = P ? { x: x + 2 * u, y: y + 2 * u, w: bw * 0.42, h: bh - 4 * u } : { x: x + 2 * u, y: y + 2 * u, w: bw - 4 * u, h: bh * 0.6 };
      const e0 = plot([{ pts: B.rectPts(x, y, bw, bh), w: 0.26 * u }, { pts: B.rectPts(pic.x, pic.y, pic.w, pic.h), w: 0.12 * u, c: PAL.dim }], at[i], 700 * u);
      tag(i + 1, [x + bw - 3.4 * u, y + 3.4 * u], [x + bw - 3.4 * u, y + 3.4 * u], B.prog(T, at[i] + 0.1, 0.3));
      const s = Math.min(pic.w, pic.h) / 10, cx = pic.x + pic.w / 2 - (i === 2 ? (P ? 3.4 : 2) * s : 0), base = pic.y + pic.h - 3 * u;
      const st = [];
      if (i === 0) {
        // pump symbol (circle with a triangle) on the ground, pipe up to a tank, flow arrow upward
        st.push({ pts: B.arcPts(cx - 2.5 * s, base - 1.6 * s, 1.6 * s, 0, B.TAU, 28) }, { pts: [[cx - 3.6 * s, base - 0.6 * s], [cx - 2.5 * s, base - 3.1 * s], [cx - 1.4 * s, base - 0.6 * s]] });
        st.push({ pts: [[cx - 0.9 * s, base - 1.6 * s], [cx + 1.5 * s, base - 1.6 * s], [cx + 1.5 * s, base - 6.2 * s]] }, { pts: B.rectPts(cx - 0.2 * s, base - 8.6 * s, 3.4 * s, 2.4 * s), w: 0.3 * u });
        st.push({ pts: [[-5, 0], [5, 0]].map(([a]) => [cx + a * s, base]), w: 0.3 * u });
      } else if (i === 1) {
        st.push({ pts: B.rectPts(cx - 4 * s, base - 8.6 * s, 3.4 * s, 2.4 * s), w: 0.3 * u }, { pts: [[cx - 2.3 * s, base - 6.2 * s], [cx - 2.3 * s, base - 0.8 * s], [cx + 4 * s, base - 0.8 * s]] });
        st.push({ pts: [[cx - 5, base], [cx + 5 * s, base]], w: 0.3 * u });
      } else {
        st.push({ pts: [[cx - 4.5 * s, base - 2 * s], [cx + 0.5 * s, base - 2 * s], [cx + 0.5 * s, base - 1 * s]], w: 0.3 * u }, { pts: [[cx - 1.5 * s, base - 2 * s], [cx - 1.5 * s, base - 3.4 * s]] }, { pts: [[cx - 2.6 * s, base - 3.4 * s], [cx - 0.4 * s, base - 3.4 * s]], w: 0.3 * u });
        st.push({ pts: B.arcPts(cx + 2.6 * s, base - 6 * s, 2.2 * s, 0, B.TAU, 36) }, { pts: [[cx - 1.5 * s, base - 3.4 * s], [cx - 1.5 * s, base - 6 * s], [cx + 0.4 * s, base - 6 * s]] });
      }
      plot(st, e0, 420 * u);
      // flow arrow / gauge needle for each detail
      const fp = B.prog(T, at[i] + 0.55, 0.45);
      if (i === 0 && fp > 0) {
        const pts = [[cx + 2.6 * s, base - 1.8 * s], [cx + 2.6 * s, base - 5.6 * s]], e = B.pointAt(pts, fp);
        B.strokeReveal(G, pts, fp, { width: 0.2 * u, color: PAL.line, cap: "butt" });
        head(e[0], e[1], e[2], 1.6 * u);
      } else if (i === 1 && fp > 0) {
        const pts = [[cx - 1.2 * s, base - 5.8 * s], [cx - 1.2 * s, base - 1.9 * s], [cx + 3.6 * s, base - 1.9 * s]], e = B.pointAt(pts, fp);
        B.strokeReveal(G, pts, fp, { width: 0.2 * u, color: PAL.line, cap: "butt" });
        head(e[0], e[1], e[2], 1.6 * u);
      } else if (i === 2 && fp > 0) {
        const gx = cx + 2.6 * s, gy = base - 6 * s, a = -Math.PI * 0.75 + Math.PI * 1.5 * (4 / 6) * B.ease.outCubic(fp);
        for (let k = 0; k <= 6; k++) {
          const ta = -Math.PI * 0.75 + (Math.PI * 1.5 * k) / 6 - Math.PI / 2;
          B.strokeReveal(G, [[gx + Math.cos(ta) * 1.7 * s, gy + Math.sin(ta) * 1.7 * s], [gx + Math.cos(ta) * 2.1 * s, gy + Math.sin(ta) * 2.1 * s]], 1, { width: 0.12 * u, color: PAL.dim });
        }
        B.strokeReveal(G, [[gx, gy], [gx + Math.cos(a - Math.PI / 2) * 1.8 * s, gy + Math.sin(a - Math.PI / 2) * 1.8 * s]], 1, { width: 0.26 * u, color: PAL.yellow });
        type("4 bar", gx + 2.2 * s + 1.2 * u, gy, 3.95 * u, fp, { ls: 0.02, weight: 600, color: PAL.yellow });
      }
      const nx = P ? x + bw * 0.49 : x + 2 * u, ny = P ? y + bh * 0.5 : y + bh * 0.64 + 3 * u;
      type(notes[i], nx, ny, L.lab, B.prog(T, at[i] + 0.45, 0.5), { baseline: P ? "middle" : "top", weight: 500, italic: true, ls: 0.04, maxW: P ? bw * 0.5 : bw - 4 * u });
    }
  }

  // ------------------------------------------------------------------ frame: sheets slide over each other
  function drawSheet(ctx, L, key, ox, fn, gridP) {
    const W = L.F.W, H = L.F.H;
    if (ox >= W || ox <= -W) return;
    G = B.scratch(key, W, H);
    fn(L, W, H);
    ctx.save();
    ctx.beginPath();
    ctx.rect(ox, 0, W, H);
    ctx.clip();
    const grid = paper(ctx, W, H, ox);
    B.clipReveal(ctx, ox, 0, W, H, gridP, "right", (c) => c.drawImage(grid, ox, 0));
    ctx.globalAlpha = 0.28; // a slight bleed so thick lines feel printed
    ctx.filter = `blur(${(0.16 * L.u).toFixed(1)}px)`;
    ctx.drawImage(G.canvas, ox, 0);
    ctx.filter = "none";
    ctx.globalAlpha = 1;
    ctx.drawImage(G.canvas, ox, 0);
    if (ox > 0) {
      ctx.fillStyle = "rgba(0,10,40,0.35)"; // the sliding sheet's edge casts a thin shadow on the one below
      ctx.fillRect(ox - 1.2 * L.u, 0, 1.2 * L.u, H);
    }
    ctx.restore();
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    U = L.u;
    T = t;
    const slideIn = B.prog(t, BEATS[3] - 0.15, 0.55, "inOutCubic"), slideOut = B.prog(t, BEATS[5], 0.6, "inOutCubic");
    const two = slideIn > 0 && slideOut < 1;
    if (!two || slideIn < 1 || slideOut > 0) drawSheet(ctx, L, "bp-one", 0, sheetOne, B.prog(t, 0, 0.45, "inOutSine"));
    if (two) drawSheet(ctx, L, "bp-two", slideOut > 0 ? -W * slideOut : W * (1 - slideIn), sheetTwo, 1);
    // close: the approval stamp on sheet one, in the accent colour
    const sp = t - (BEATS[5] + 0.9);
    // (the stamp lands in the clear band under the drawing in portrait, between the note and the title block in landscape)
    if (sp > 0) {
      const S = L.S, u = L.u, k = 1 + 0.12 * (1 - B.smooth(0, 0.1, sp));
      const P = L.P, sx = P ? S.r - 18 * u : S.x + S.w * 0.6, sy = P ? S.b - 8 * u : L.F.H * 0.72, sw = (P ? 34 : 57) * u, sh = (P ? 15 : 9) * u;
      ctx.save();
      ctx.translate(sx, sy);
      ctx.rotate(P ? -0.05 : -0.12);
      ctx.scale(k, k);
      ctx.globalAlpha = B.smooth(0, 0.06, sp) * 0.92;
      ctx.strokeStyle = PAL.yellow;
      ctx.lineWidth = 0.5 * u;
      ctx.strokeRect(-sw / 2, -sh / 2, sw, sh);
      ctx.lineWidth = 0.2 * u;
      ctx.strokeRect(-sw / 2 + u, -sh / 2 + u, sw - 2 * u, sh - 2 * u);
      B.text(ctx, P ? "HEIGHT MAKES\nPRESSURE" : "HEIGHT = PRESSURE", 0, 0.2 * u, { size: 4 * u, minSize: 3.9 * u, family: MONO2, weight: 700, color: PAL.yellow, letterSpacing: 0, lineH: 1.1, maxW: sw - 4 * u });
      ctx.restore();
    }
    B.vignette(ctx, W, H, { amount: 0.3, color: "#03122e", inner: 0.55 });
    B.grain(ctx, W, H, { amount: 0.04, t, fps: 12 });
  }

  // ------------------------------------------------------------------ sound: fast plotter ticks, type blips for text, a low hum, a stamp
  SOUND.define("bp-pen", (v, o) => {
    // a plotter pen moving: a thin fast ticking (stepper motor) over a faint scrape
    const d = o.dur ?? 0.6;
    for (let at = 0; at < d; at += 0.022 + v.rng() * 0.01) v.noise({ at, filter: "bandpass", f: 3800 + v.rng() * 900, q: 4, a: 0.0005, len: 0.008, peak: 0.08 });
    v.noise({ filter: "highpass", f: 5000, a: 0.02, hold: d * 0.9, len: 0.05, peak: 0.02 });
  }, { verb: 0.05 });

  function score(k) {
    k.bed("hum", 0, DUR, { gain: 0.5 });
    const pen = (at, dur, gain = 1) => k.at(at, "bp-pen", { dur, gain });
    pen(0.0, 0.45, 0.8);
    k.at(0.3, "typing", { dur: 0.9, gain: 0.35 });
    pen(0.9, 1.4);
    k.at(1.2, "typing", { dur: 0.5, gain: 0.25 }).at(1.5, "typing", { dur: 0.6, gain: 0.25 });
    pen(BEATS[1] + 0.05, 1.2);
    [0, 1, 2, 3].forEach((i) => k.at(BEATS[1] + 1.2 + i * 0.25, "blip", { note: ["E6", "G6", "A6", "C7"][i], gain: 0.25 }));
    k.at(BEATS[1] + 1.6, "typing", { dur: 0.7, gain: 0.25 });
    pen(BEATS[1] + 1.4, 1.0, 0.7);
    // key number: the dimension slides out, the value types in, the table is ruled and filled
    k.at(BEATS[2] + 0.3, "swish", { dur: 0.4, gain: 0.25 }).at(BEATS[2] + 0.8, "typing", { dur: 0.25, gain: 0.4 });
    k.at(BEATS[2] + 1.1, "beep", { note: "A5", gain: 0.3 });
    pen(BEATS[2] + 0.8, 0.5);
    k.at(BEATS[2] + 1.25, "typing", { dur: 0.7, gain: 0.3 });
    k.at(BEATS[2] + 1.75, "pencil", { dur: 0.45, gain: 0.5 }).at(BEATS[2] + 1.85, "blip", { note: "E6", gain: 0.3 });
    // a new sheet slides in; three details plotted in order
    k.at(BEATS[3] - 0.15, "paper", { dur: 0.55, gain: 0.7 });
    STEP_AT.forEach((at, i) => {
      pen(at, 0.6);
      k.at(at + 0.1, "blip", { note: ["E6", "G6", "B6"][i], gain: 0.3 }).at(at + 0.45, "typing", { dur: 0.5, gain: 0.3 });
    });
    k.at(10.5, "tick", { gain: 0.4 });
    // close: the sheet slides away, the stamp comes down
    k.at(BEATS[5], "paper", { dur: 0.6, gain: 0.7 });
    k.at(BEATS[5] + 0.9, "stamp", { gain: 1 }).at(BEATS[5] + 0.92, "thud", { gain: 0.4 });
  }

  Player.register({
    id: "blueprint",
    name: "Blueprint",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,500;0,600;1,500&family=Space+Mono:wght@700&display=swap",
      faces: ['500 20px "IBM Plex Mono"', '600 20px "IBM Plex Mono"', 'italic 500 20px "IBM Plex Mono"', '700 20px "Space Mono"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [2.1, 4.7, 7.3, 9.68, 10.9, 12.8],
    draw,
    score,
  });
})();
