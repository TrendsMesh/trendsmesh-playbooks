/* 46 ISOTYPE Pictograms - reference animation.
 * Topic (setting, replace it): world population, one figure per billion people. UN milestones: 1 billion about
 * 1804, 2 in 1927, 3 in 1960, 4 in 1974, 5 in 1987, 6 in 1999, 7 in 2011, 8 in 2022; UN projection for 2050:
 * about 9.7 billion.
 * Rendering (keep it): the 1920s-30s picture-statistics method. Identical flat pictograms in rows, each figure a
 * fixed quantity, so amounts are COUNTED, never scaled; a cut figure for a remainder; a legend; a few flat colours
 * on off-white paper; a clean geometric sans; big clear titles. All ink goes on one plate that is then worn by a
 * fixed speckle mask (light paper showing through, as in old letterpress), over a fibrous paper sheet.
 * Motion: figures stamp in one at a time, left to right, in rhythm; rows slide to compare; scenes slide sideways.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    paper: "#f1eadb",
    ink: "#1f1d1b",
    red: "#b2392b", // brick red: the highlight
    ochre: "#cf9a2e",
    blue: "#3c5a7f", // slate blue: the main series
    green: "#5f7f4f",
    grey: "#9b958a", // projections, rules
  };
  const HEAD = "Jost", NUM = "Work Sans";
  const DUR = 13;
  const BEATS = [0, 1.8, 4.0, 7.2, 8.9, 11.0];
  const YEARS = [[1804, 1], [1927, 2], [1960, 3], [1974, 4], [1987, 5], [1999, 6], [2011, 7], [2022, 8]];

  // ------------------------------------------------------------------ timing (shared by draw and score)
  const T = {
    title: (r, i) => 0.55 + (i * 2 + r) * 0.1, // 8 figures on the title, the two rows in turn
    legend: 2.15, half: 3.3, arrow: 2.55,
    row: (r, i) => 4.45 + r * 0.3 + i * 0.045, // chart rows build one figure at a time
    num: 7.6,
    step: (k, i) => 9.05 + k * 0.35 + 0.12 + i * 0.09,
    now: (i) => 11.35 + i * 0.045, // 2022 again
    proj: (i) => 11.75 + i * 0.07, // 2050, the tenth figure is cut at 0.7
  };

  // ------------------------------------------------------------------ isotype helpers (reuse these)
  /**
   * The basic pictogram: a standing person, flat, no outline, built from a round head, a block torso that
   * carries the arms, and two legs. (x, y) = feet centre, h = full height; width is 0.42 h. kind: "adult",
   * "child" (bigger head, shorter), "elder" (stooped, with a stick). Every figure of one kind is identical.
   */
  function person(g, x, y, h, kind = "adult") {
    const c = kind === "child", e = kind === "elder";
    const hh = c ? h * 0.8 : h, w = hh * 0.42, lean = e ? hh * 0.05 : 0;
    const head = c ? hh * 0.135 : hh * 0.11;
    g.beginPath();
    B.circle(g, x + lean * 1.4, y - hh + head + (e ? hh * 0.05 : 0), head);
    const sy = y - hh * (c ? 0.69 : 0.73) + (e ? hh * 0.05 : 0), hy = y - hh * 0.37;
    g.moveTo(x - w / 2 + lean, sy + w * 0.12);
    g.quadraticCurveTo(x - w / 2 + lean, sy, x - w / 2 + w * 0.14 + lean, sy);
    g.lineTo(x + w / 2 - w * 0.14 + lean, sy);
    g.quadraticCurveTo(x + w / 2 + lean, sy, x + w / 2 + lean, sy + w * 0.12);
    g.lineTo(x + w * 0.42, y - hh * 0.3);
    g.lineTo(x + w * 0.3, y - hh * 0.3);
    g.lineTo(x + w * 0.3, hy);
    g.lineTo(x - w * 0.3, hy);
    g.lineTo(x - w * 0.3, y - hh * 0.3);
    g.lineTo(x - w * 0.42, y - hh * 0.3);
    g.closePath();
    g.rect(x - w * 0.29, hy - 1, w * 0.26, y - hy + 1);
    g.rect(x + w * 0.03, hy - 1, w * 0.26, y - hy + 1);
    g.fill();
    if (e) { // walking stick
      g.beginPath();
      g.rect(x + w * 0.62, y - hh * 0.5, Math.max(1.5, hh * 0.035), hh * 0.5);
      g.rect(x + w * 0.42, y - hh * 0.5, w * 0.22, Math.max(1.5, hh * 0.035));
      g.fill();
    }
  }
  /** House pictogram: block, pitched roof, door cut out in paper colour. (x, y) = base centre, h = height. */
  function house(g, x, y, h, col) {
    const w = h * 0.9;
    g.fillStyle = col;
    g.beginPath();
    g.rect(x - w / 2, y - h * 0.58, w, h * 0.58);
    g.moveTo(x - w * 0.62, y - h * 0.56);
    g.lineTo(x, y - h);
    g.lineTo(x + w * 0.62, y - h * 0.56);
    g.closePath();
    g.fill();
    g.fillStyle = PAL.paper;
    g.fillRect(x - w * 0.11, y - h * 0.32, w * 0.22, h * 0.32);
  }
  /**
   * One stamped figure: it lands from a little above at 115 % and settles to 100 % in 0.1 s, with a faint ink
   * squeeze ring at the moment of contact. frac < 1 cuts the figure at that share of its width (a remainder).
   */
  function stamp(g, t, at, x, y, h, col, frac = 1, kind) {
    if (t < at) return;
    const k = B.clamp((t - at) / 0.1), s = 1 + 0.15 * (1 - B.ease.outCubic(k)), w = h * 0.42;
    g.save();
    g.globalAlpha *= 0.35 + 0.65 * k;
    g.translate(x, y);
    g.scale(s, s);
    g.translate(-x, -y - (1 - k) * h * 0.06);
    if (frac < 1) { g.beginPath(); g.rect(x - w, y - h * 1.1, w * 0.5 + w * frac, h * 1.2); g.clip(); }
    g.fillStyle = col;
    person(g, x, y, h, kind);
    g.restore();
    if (t - at < 0.25) { // ink squeeze: a quick pale ring of pressure around the feet
      const q = B.clamp((t - at) / 0.25);
      g.save();
      g.strokeStyle = B.rgba(col, 0.25 * (1 - q));
      g.lineWidth = h * 0.02;
      g.beginPath();
      g.ellipse(x, y, w * (0.6 + 0.6 * q), h * 0.06 * (1 + q), 0, 0, B.TAU);
      g.stroke();
      g.restore();
    }
  }
  /** A row of n figures (n may be fractional), stamped one by one with times at(i). Returns the row's right end. */
  function row(g, t, x0, y, n, h, slot, col, at, kind) {
    const full = Math.floor(n + 1e-6), rem = n - full;
    for (let i = 0; i < full; i++) stamp(g, t, at(i), x0 + slot * (i + 0.5), y, h, col, 1, kind);
    if (rem > 0.01) stamp(g, t, at(full), x0 + slot * (full + 0.5), y, h, col, rem, kind);
    return x0 + slot * Math.ceil(n);
  }
  /** Geometric sans text on the ink plate. */
  function label(g, str, x, y, size, o = {}) {
    return B.text(g, str, x, y, { size, family: o.family || HEAD, weight: o.weight || 500, color: o.color || PAL.ink, align: o.align || "left", maxW: o.maxW, maxLines: o.maxLines || 1, lineH: o.lineH || 1.05, alpha: o.alpha, letterSpacing: o.ls });
  }
  /** Big clear title with a short thick brick-red rule over it, as on the old charts. */
  function title(g, str, x, y, size, o = {}) {
    const p = o.p ?? 1, align = o.align || "left", m = B.measureText(g, str, { size, family: HEAD, weight: 700, maxW: o.maxW, maxLines: o.maxLines || 2, lineH: 1.02 });
    const rw = Math.min(m.width, size * 3.2) * B.ease.outCubic(B.clamp(p * 1.6));
    const rx = align === "center" ? x - m.width / 2 : x;
    g.fillStyle = o.rule || PAL.red;
    g.fillRect(rx, y - m.height / 2 - size * 0.42, rw, size * 0.13);
    const a = B.clamp((p - 0.25) * 2);
    return B.text(g, str, x, y + (1 - a) * size * 0.15, { size, family: HEAD, weight: 700, color: PAL.ink, align, maxW: o.maxW, maxLines: o.maxLines || 2, lineH: 1.02, alpha: a });
  }
  /** Small solid ink disc with a white step number. */
  function disc(g, x, y, r, n, s) {
    if (s <= 0.01) return;
    g.save();
    g.translate(x, y);
    g.scale(s, s);
    g.fillStyle = PAL.ink;
    g.beginPath();
    B.circle(g, 0, 0, r);
    g.fill();
    label(g, String(n), 0, r * 0.04, r * 1.35, { align: "center", weight: 600, color: PAL.paper });
    g.restore();
  }

  // ------------------------------------------------------------------ layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    const L = { F, u, P, S, W, H, txt: P ? 4.6 * u : 4.2 * u };
    if (P) {
      L.title = { x: W / 2, y: H * 0.225, size: 12.5 * u, sub: H * 0.33, figs: [H * 0.545, H * 0.745], h: 21 * u, slot: 19 * u, x0: W / 2 - 38 * u };
      L.legend = { head: [S.x, H * 0.19], fx: W * 0.29, fy: H * 0.65, fh: 44 * u, lx: W * 0.56, ly: H * 0.33, hx: W * 0.29, hy: H * 0.775, hh: 20 * u, hl: [W * 0.47, H * 0.735] };
      L.chart = { head: [S.x, H * 0.18], sub: H * 0.222, y0: H * 0.305, dy: H * 0.0635, h: 10 * u, slot: 9 * u, lx: S.x, x0: S.x + 14 * u };
      L.cmp = { y: [H * 0.56, H * 0.71], h: 12.5 * u, slot: 9.2 * u, num: [W / 2, H * 0.3], numSize: 21 * u, cap: H * 0.385, x0: S.x + 14 * u };
      L.steps = { head: [S.x, H * 0.18], blocks: [0, 1, 2].map((k) => [S.x, H * (0.28 + k * 0.165)]), h: 13 * u, slot: 11.5 * u };
      L.close = { head: [S.x, H * 0.19], y: [H * 0.4, H * 0.56], h: 9.5 * u, slot: 7.8 * u, lx: S.x, x0: S.x + 14 * u, note: H * 0.64, src: H * 0.7 };
    } else {
      const colW = W * 0.3;
      L.title = { x: S.x, y: H * 0.4, size: 9 * u, sub: H * 0.56, figs: [H * 0.44, H * 0.82], h: 18 * u, slot: 12 * u, x0: W * 0.6, maxW: W * 0.46 };
      L.legend = { head: [S.x, H * 0.2], fx: W * 0.33, fy: H * 0.86, fh: 56 * u, lx: W * 0.55, ly: H * 0.38, hx: W * 0.6, hy: H * 0.86, hh: 20 * u, hl: [W * 0.66, H * 0.76], colW };
      L.chart = { head: [S.x, H * 0.3], sub: H * 0.44, y0: H * 0.24, dy: H * 0.091, h: 7.4 * u, slot: 6.4 * u, lx: W * 0.38, x0: W * 0.46, colW };
      L.cmp = { y: [H * 0.46, H * 0.76], h: 11 * u, slot: 8.5 * u, num: [S.x, H * 0.4], numSize: 13 * u, cap: H * 0.58, x0: W * 0.46, colW, numAlign: "left" };
      L.steps = { head: [S.x, H * 0.2], blocks: [0, 1, 2].map((k) => [S.x + k * W * 0.31, H * 0.42]), h: 16 * u, slot: 10.4 * u, colW: W * 0.28 };
      L.close = { head: [S.x, H * 0.3], y: [H * 0.42, H * 0.66], h: 9 * u, slot: 6.2 * u, lx: W * 0.38, x0: W * 0.46, note: H * 0.7, src: H * 0.86, colW };
    }
    return L;
  }

  // ------------------------------------------------------------------ the five scenes (each drawn on the ink plate)
  function sceneTitle(g, L, t) {
    const T0 = L.title, u = L.u, P = L.P;
    title(g, P ? "How many\nof us?" : "How many of us?", T0.x, T0.y, T0.size, { p: B.prog(t, 0.1, 0.6), align: P ? "center" : "left", maxW: T0.maxW || L.S.w });
    label(g, "World population, 1804 to 2050", T0.x, T0.sub, L.txt * 1.05, { align: P ? "center" : "left", alpha: B.span(t, 0.4, 0.7), maxW: T0.maxW || L.S.w });
    for (let r = 0; r < 2; r++) row(g, t, T0.x0, T0.figs[r], 4, T0.h, T0.slot, r ? PAL.blue : PAL.ink, (i) => T.title(r, i));
    // a ground rule under each row, like a printed baseline
    g.fillStyle = PAL.grey;
    for (let r = 0; r < 2; r++) g.fillRect(T0.x0, T0.figs[r] + u * 0.8, T0.slot * 4 * B.ease.outCubic(B.span(t, 0.4, 1.0)), u * 0.35);
  }
  function sceneLegend(g, L, t) {
    const G = L.legend, u = L.u, P = L.P;
    title(g, "How to read it", G.head[0], G.head[1], (P ? 7.5 : 6.5) * u, { p: B.prog(t, 1.95, 0.6) });
    stamp(g, t, T.legend, G.fx, G.fy, G.fh, PAL.blue);
    // the legend text and an ink arrow pointing at the figure
    const lx = G.lx, ly = G.ly, a = B.span(t, 2.4, 2.7);
    label(g, "1 figure", lx, ly, (P ? 8.5 : 7.5) * u, { weight: 700, alpha: a });
    label(g, "= 1 billion", lx, ly + (P ? 8.5 : 7.5) * u * 1.05, (P ? 5.6 : 5) * u, { alpha: B.span(t, 2.5, 2.8) });
    label(g, "people", lx, ly + (P ? 8.5 : 7.5) * u * 1.75, (P ? 5.6 : 5) * u, { alpha: B.span(t, 2.55, 2.85) });
    const ax = lx - u * 2, ay = ly + (P ? 14 : 13) * u * 0.5, tx = G.fx + G.fh * 0.27, ty = G.fy - G.fh * 0.6;
    B.arrow(g, B.arcBetween(ax, ay, tx, ty, P ? 0.25 : -0.2), { p: B.prog(t, T.arrow, 0.45, "inOutCubic"), width: 1.1 * u, head: 4 * u, color: PAL.ink, headStyle: "tri" });
    // half a figure = half the amount
    stamp(g, t, T.half, G.hx, G.hy, G.hh, PAL.blue, 0.5);
    label(g, P ? "half a figure\n= half a billion" : "half a figure = half a billion", G.hl[0], G.hl[1], L.txt, { alpha: B.span(t, 3.4, 3.7), maxLines: 2, maxW: P ? L.S.r - G.hl[0] : L.W * 0.32 });
  }
  function sceneChart(g, L, t) {
    const C = L.chart, M = L.cmp, u = L.u, P = L.P;
    const cmpK = B.span(t, 7.25, 7.8, "inOutCubic"); // rows slide to compare 1804 with 2022
    const headA = 1 - B.span(t, 7.2, 7.45);
    g.save();
    g.globalAlpha *= 1 - B.span(t, 7.25, 7.5);
    title(g, "World population", C.head[0], C.head[1], (P ? 7.5 : 6) * u, { p: B.prog(t, 4.1, 0.6), maxW: P ? L.S.w : C.colW, maxLines: P ? 1 : 2, rule: PAL.blue });
    g.restore();
    if (headA > 0) label(g, "1 figure = 1 billion people", C.head[0], C.sub, L.txt, { alpha: Math.min(headA, B.span(t, 4.3, 4.6)), maxW: P ? L.S.w : C.colW, maxLines: 2 });
    YEARS.forEach(([yr, n], r) => {
      const key = r === 0 || r === 7, ci = r === 0 ? 0 : 1;
      const a = key ? 1 : 1 - B.span(t, 7.2 + (7 - r) * 0.03, 7.45 + (7 - r) * 0.03);
      if (a <= 0.01) return;
      const y = key ? B.lerp(C.y0 + r * C.dy, M.y[ci], cmpK) : C.y0 + r * C.dy - u * 3 * (1 - a);
      const h = key ? B.lerp(C.h, M.h, cmpK) : C.h, slot = key ? B.lerp(C.slot, M.slot, cmpK) : C.slot;
      const x0 = key ? B.lerp(C.x0, M.x0, cmpK) : C.x0 - (1 - a) * u * 8;
      g.save();
      g.globalAlpha = a;
      // year labels and pale baselines go down first, in a quick stagger, then the figures stamp onto them
      const la = B.span(t, 4.15 + r * 0.04, 4.35 + r * 0.04);
      label(g, String(yr), C.lx, y - h * 0.42, L.txt * (key ? B.lerp(1, 1.1, cmpK) : 1), { family: NUM, weight: 600, alpha: la });
      g.fillStyle = B.rgba(PAL.grey, 0.55);
      g.fillRect(x0, y + u * 0.5, slot * 8 * B.ease.outCubic(la) * (1 - cmpK), u * 0.25);
      row(g, t, x0, y, n, h, slot, r === 7 && t > 7.3 ? B.mix(PAL.blue, PAL.red, B.span(t, 7.3, 7.6)) : PAL.blue, (i) => T.row(r, i));
      g.restore();
    });
    // key number: 8 billion, eight times 1804
    if (t > T.num) {
      const s = B.pop(t, T.num, 0.4, 1.4), [nx, ny] = M.num, al = M.numAlign || "center";
      g.save();
      g.translate(nx, ny);
      g.scale(s, s);
      label(g, "8 billion", 0, 0, M.numSize, { weight: 700, color: PAL.red, align: al, family: HEAD });
      g.restore();
      label(g, "in 2022: eight times 1804", nx, M.cap, L.txt * 1.05, { align: al, alpha: B.span(t, 7.95, 8.25), maxW: P ? L.S.w : M.colW, maxLines: 2 });
    }
  }
  function sceneSteps(g, L, t) {
    const Sx = L.steps, u = L.u, P = L.P;
    title(g, "Why it grew, and why it slows", Sx.head[0], Sx.head[1], (P ? 6.4 : 6) * u, { p: B.prog(t, 9.0, 0.6), maxW: P ? L.S.w : L.S.w * 0.7, maxLines: P ? 2 : 1, rule: PAL.green });
    const steps = [["Fewer children die young", "child", PAL.green, 4], ["People live longer", "elder", PAL.ochre, 3], ["Then families get smaller", "house", PAL.blue, 2]];
    steps.forEach(([txt, kind, col, n], k) => {
      const [bx, by] = Sx.blocks[k], t0 = 9.05 + k * 0.35, r = (P ? 3.3 : 3) * u;
      disc(g, bx + r, by, r, k + 1, B.pop(t, t0, 0.3, 1.6));
      label(g, txt, bx + r * 2.6, by + u * 0.2, L.txt, { alpha: B.span(t, t0 + 0.05, t0 + 0.3), maxW: P ? L.S.w - r * 2.6 : Sx.colW - r * 2.6, maxLines: 2 });
      const fy = by + r + u * 2.5 + Sx.h, fx = bx + r * 2.6;
      if (kind === "house") {
        if (t > T.step(k, 0)) { g.save(); g.globalAlpha *= B.clamp((t - T.step(k, 0)) / 0.1); house(g, fx + Sx.h * 0.45, fy, Sx.h * 1.05, col); g.restore(); }
        row(g, t, fx + Sx.h * 1.05, fy, n, Sx.h, Sx.slot * 0.8, PAL.ink, (i) => T.step(k, i + 1), "adult");
      } else row(g, t, fx, fy, n, Sx.h, Sx.slot, col, (i) => T.step(k, i), kind);
    });
  }
  function sceneClose(g, L, t) {
    const C = L.close, u = L.u, P = L.P;
    title(g, "Still growing, but slower", C.head[0], C.head[1], (P ? 7 : 6) * u, { p: B.prog(t, 11.1, 0.6), maxW: P ? L.S.w : C.colW, maxLines: 2, rule: PAL.ochre });
    label(g, "2022", C.lx, C.y[0] - C.h * 0.42, L.txt, { family: NUM, weight: 600, alpha: B.span(t, 11.2, 11.4) });
    row(g, t, C.x0, C.y[0], 8, C.h, C.slot, PAL.red, T.now);
    label(g, "2050", C.lx, C.y[1] - C.h * 0.42, L.txt, { family: NUM, weight: 600, alpha: B.span(t, 11.6, 11.8) });
    row(g, t, C.x0, C.y[1], 9.7, C.h, C.slot, B.mix(PAL.blue, PAL.paper, 0.35), T.proj);
    label(g, "2050 (projected): about 9.7 billion", P ? C.lx : L.S.x, C.note, L.txt * 1.05, { weight: 600, alpha: B.span(t, 11.5, 11.75), maxW: P ? L.S.w : C.colW, maxLines: 2 });
    label(g, "Source: United Nations estimates", P ? C.lx : L.S.x, C.src, Math.max(L.txt * 0.85, 3.95 * u), { color: B.mix(PAL.ink, PAL.grey, 0.5), alpha: B.span(t, 11.6, 11.85), maxW: P ? L.S.w : C.colW, maxLines: 2 });
  }

  // ------------------------------------------------------------------ plates, paper and finishing
  /** Fixed worn-ink mask: tiny pale specks and short scuffs where the paper shows through the ink. */
  function wearMask(W, H) {
    return B.layer("iso-wear", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(46);
      const n = Math.round((w * h) / (u * u) * 0.9);
      for (let i = 0; i < n; i++) {
        g.fillStyle = `rgba(0,0,0,${r.range(0.25, 0.7).toFixed(2)})`;
        const x = r() * w, y = r() * h, s = r.range(0.06, 0.22) * u;
        if (r() < 0.85) { g.beginPath(); g.arc(x, y, s, 0, B.TAU); g.fill(); } else g.fillRect(x, y, s * r.range(3, 8), s * 0.6);
      }
      B.mottle(g, w, h, { amount: 0.18, feature: 0.05, seed: 9, mode: "source-over" });
    });
  }
  /** Scenes slide sideways: the outgoing one leaves left as the next arrives from the right. */
  function slide(t, a, b) {
    const pin = a <= 0 ? 1 : B.span(t, a - 0.2, a + 0.25, "inOutCubic"), pout = B.span(t, b - 0.2, b + 0.25, "inOutCubic");
    return { show: pin > 0 && pout < 1, dx: (1 - pin) - pout };
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    B.paper(ctx, W, H, { color: PAL.paper, seed: 46, mottle: 0.1, fibers: 0.45, specks: 0.35, tooth: 0.07 });
    // the ink plate: every pictogram, rule and word, worn by the fixed speckle mask, printed with multiply
    const g = B.scratch("iso-ink", W, H);
    const scenes = [[sceneTitle, 0, 1.8], [sceneLegend, 1.8, 4.0], [sceneChart, 4.0, 8.9], [sceneSteps, 8.9, 11.0], [sceneClose, 11.0, 99]];
    scenes.forEach(([fn, a, b]) => {
      const s = slide(t, a, b);
      if (!s.show) return;
      g.save();
      g.translate(s.dx * W, 0);
      fn(g, L, t);
      g.restore();
    });
    g.save();
    g.globalCompositeOperation = "destination-out";
    g.globalAlpha = 0.55;
    g.drawImage(wearMask(W, H), 0, 0);
    g.restore();
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(g.canvas, 0, 0);
    ctx.restore();
    // finishing: soft paper grain and a faint warm edge, like an old printed sheet
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 8, mode: "multiply" });
    B.vignette(ctx, W, H, { color: "#8a6f45", amount: 0.16, inner: 0.6, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: a soft stamp per figure, woodblock line, a calm bed
  SOUND.define("iso-stamp", (v, o) => { // rubber stamp on paper: a soft low thump and a dry paper tick
    v.tone({ f: 150, f2: 70, glide: 0.06, a: 0.002, len: 0.09, peak: 0.32 });
    v.noise({ filter: "bandpass", f: 2200, q: 0.9, a: 0.001, len: 0.035, peak: 0.12 });
  }, { verb: 0.08 });
  SOUND.define("iso-block", (v, o) => { // woodblock
    const f = v.hz(o.note || "C5");
    v.tone({ type: "triangle", f, f2: f * 0.97, glide: 0.05, a: 0.001, len: 0.11, peak: 0.28 });
    v.tone({ f: f * 2.76, a: 0.001, len: 0.03, peak: 0.06 });
  }, { verb: 0.18 });

  function score(k) {
    const sc = SOUND.scale("D4", "dorian", 10), at = (t, n, o) => k.at(t, n, o);
    k.bed("room", 0, DUR, { gain: 0.5 });
    k.bed("pad", 0, DUR, { notes: ["D3", "A3", "C4", "F4"], gain: 0.32, bright: 420 });
    // a calm woodblock line on the beats
    [0.1, 1.85, 4.05, 7.25, 8.95, 11.05].forEach((t, i) => at(t, "iso-block", { note: ["D5", "A4", "C5", "F5", "E5", "D5"][i], gain: 0.7 }));
    at(0.1, "paper", { gain: 0.35 });
    for (let i = 0; i < 8; i++) at(T.title(i % 2, i >> 1), "iso-stamp", { gain: 0.55, pitch: (i % 2) * 2, pan: (i >> 1) * 0.2 - 0.3 });
    // legend: one big stamp, the arrow, the half figure
    at(1.8, "swish", { dur: 0.45, gain: 0.35 }); at(T.legend, "iso-stamp", { gain: 0.9, pitch: -4 }); at(T.legend, "thud", { gain: 0.25 });
    at(T.arrow, "marker", { dur: 0.45, gain: 0.35 }); at(2.45, "marimba", { note: sc[4], gain: 0.4 });
    at(T.half, "iso-stamp", { gain: 0.6, pitch: 3 }); at(T.half + 0.02, "tick", { gain: 0.35 });
    // chart: rows build in rhythm, a marimba note per row
    at(4.0, "swish", { dur: 0.45, gain: 0.35 });
    YEARS.forEach(([, n], r) => {
      at(T.row(r, 0), "marimba", { note: sc[r % 8], gain: 0.35 });
      for (let i = 0; i < n; i++) at(T.row(r, i), "iso-stamp", { gain: 0.4, pitch: r * 0.4, pan: i * 0.08 - 0.3 });
    });
    // key number
    at(7.25, "swish", { dur: 0.5, gain: 0.3 }); at(T.num, "iso-block", { note: "D4", gain: 0.9 }); at(T.num, "chord", { notes: ["D4", "F4", "A4", "C5"], gain: 0.5 });
    at(7.95, "marimba", { note: sc[7], gain: 0.4 });
    // steps
    at(8.9, "swish", { dur: 0.45, gain: 0.35 });
    [4, 3, 3].forEach((n, k2) => {
      at(9.05 + k2 * 0.35, "iso-block", { note: sc[2 + k2 * 2], gain: 0.6 });
      for (let i = 0; i < n; i++) at(T.step(k2, i), "iso-stamp", { gain: 0.4, pitch: k2 });
    });
    // close: 2022, then 2050 with the cut figure on a tick
    at(11.0, "swish", { dur: 0.45, gain: 0.35 });
    for (let i = 0; i < 8; i++) at(T.now(i), "iso-stamp", { gain: 0.35 });
    for (let i = 0; i < 9; i++) at(T.proj(i), "iso-stamp", { gain: 0.35, pitch: 2 });
    at(T.proj(9), "tick", { gain: 0.5 }); at(T.proj(9), "iso-stamp", { gain: 0.25, pitch: 5 });
    at(12.4, "marimba", { note: sc[4], gain: 0.4 }); at(12.55, "iso-block", { note: "D5", gain: 0.6 }); at(12.6, "chord", { notes: ["D4", "A4", "D5"], gain: 0.4 });
  }

  Player.register({
    id: "isotype",
    name: "ISOTYPE Pictograms",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Jost:wght@500;600;700&family=Work+Sans:wght@500;600&display=swap",
      faces: ['700 20px "Jost"', '600 20px "Jost"', '500 20px "Jost"', '600 20px "Work Sans"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Rows by year", "Key number", "Why: steps 1-3", "Close"],
    stills: [1.5, 3.85, 6.95, 8.6, 10.75, 12.85],
    draw,
    score,
  });
})();
