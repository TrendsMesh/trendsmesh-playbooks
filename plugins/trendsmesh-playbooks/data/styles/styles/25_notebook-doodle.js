/* 25 Notebook Doodle - reference animation.
 * Topic (setting, replace it): "How is a rainbow made?" - light bending through a raindrop.
 * Rendering (keep it): one long ruled sheet the view slides down; one blue ballpoint line (pressure swell, start
 * blob, end flick); hatching, then cross-hatching; bubble headings with a hatched shadow; handwriting on the rules;
 * margin doodles traced until furry; red pen only for judgment.
 * Motion: strokes drawn one by one by a visible pen at the line's end; the notebook slides to each piece of work.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { paper: "#f6f3e8", rule: "#b9d3e8", margin: "#e29a9a", blue: "#1f3fa8", deep: "#0f1f66", red: "#d6332c", pencil: "#8a8a8a" };
  const HAND = "Gloria Hallelujah", BUBBLE = "Fredoka";
  const DUR = 14;
  const BEATS = [0, 2.2, 5.55, 8.05, 9.65, 11.6];
  const INK = { blue: PAL.blue, red: PAL.red, pencil: PAL.pencil };

  // ---- the script: every pen stroke in drawing order
  // [id, start, duration, ink]; geometry comes from work()
  const SCRIPT = [
    ["title", 0.06, 0.44, "blue"], ["titleH1", 0.52, 0.14, "blue"], ["titleH2", 0.68, 0.1, "blue"],
    ["sub", 0.8, 0.38, "blue"], ["star1", 1.2, 0.16, "blue"], ["cloud", 1.38, 0.14, "blue"], ["foot0", 1.53, 0.13, "blue"],
    ["sketch", 2.42, 0.2, "pencil"], ["drop", 2.64, 0.3, "blue"], ["dropLab", 2.96, 0.34, "blue"],
    ["sun", 3.32, 0.22, "blue"], ["sunLab", 3.56, 0.22, "blue"], ["ray", 3.8, 0.55, "blue"],
    ["eye", 4.37, 0.16, "blue"], ["eyeLab", 4.55, 0.2, "blue"], ["dropH1", 4.77, 0.11, "blue"], ["dropH2", 4.89, 0.11, "blue"],
    ["numLine", 5.85, 0.34, "blue"], ["n45", 6.2, 0.22, "blue"], ["n45H1", 6.43, 0.06, "blue"], ["strike", 6.5, 0.1, "red"],
    ["n42", 6.61, 0.22, "blue"], ["n42H1", 6.84, 0.06, "blue"], ["ring", 6.91, 0.17, "red"], ["angle", 7.09, 0.22, "blue"], ["foot2", 7.32, 0.13, "blue"],
    ["nums", 8.4, 0.2, "blue"], ["fanSk", 8.61, 0.2, "pencil"], ["foot3", 8.82, 0.1, "blue"], ["s1", 8.93, 0.27, "blue"], ["tick1", 9.21, 0.07, "red"], ["s2", 9.29, 0.27, "blue"], ["tick2", 9.57, 0.07, "red"],
    ["s3", 9.7, 0.4, "blue"], ["s3b", 10.12, 0.4, "blue"], ["fan", 10.54, 0.26, "blue"], ["under", 10.82, 0.18, "red"],
    ["box", 12.02, 0.28, "blue"], ["boxH", 12.31, 0.1, "blue"], ["answer", 12.42, 0.46, "blue"], ["bow", 12.89, 0.34, "blue"],
    ["stars", 13.24, 0.12, "red"], ["you", 13.37, 0.24, "blue"], ["foot4", 13.62, 0.13, "blue"],
  ];
  // the page section the view rests on in each beat
  const CAM_STOPS = [0, 1, 2, 3, 3, 4];

  // ---- ballpoint helpers (reuse these)
  let U = 1;
  /** One ballpoint stroke (jitter, swell, flick, blob). Returns the tip. */
  function penStroke(g, pts, o = {}) {
    const p = o.p ?? 1;
    if (p <= 0 || pts.length < 2) return null;
    const line = B.wobble(B.densify(pts, 1.2 * U), { amp: (o.amp ?? 0.22) * U, freq: o.freq ?? 0.7, seed: o.seed ?? 1 });
    const w = (o.w ?? 0.42) * U, col = o.color || PAL.blue;
    g.save();
    g.globalAlpha = o.alpha ?? 0.9;
    B.taperStroke(g, line, { width: w, color: col, p, taperIn: 0.03, taperOut: o.flick ?? 0.22, rough: 0.5, roughScale: 7, seed: o.seed ?? 1 });
    if (o.blob !== false) {
      g.fillStyle = col === PAL.blue ? PAL.deep : B.shade(col, -0.3);
      g.beginPath();
      B.circle(g, line[0][0], line[0][1], w * 0.62);
      g.fill();
    }
    g.restore();
    return B.pointAt(line, p);
  }
  /** Several strokes in sequence sharing one reveal p. */
  function penStrokes(g, list, p, o = {}) {
    const lens = list.map((pts) => B.pathLength(pts)), tot = lens.reduce((a, b) => a + b, 0) || 1;
    let acc = 0, tip = null;
    list.forEach((pts, i) => {
      const a = acc / tot, b = (acc + lens[i]) / tot;
      acc += lens[i];
      const q = B.clamp((p - a) / (b - a));
      if (q > 0) tip = penStroke(g, pts, { ...o, p: q, seed: (o.seed ?? 1) + i * 17 }) || tip;
    });
    return tip;
  }
  /** A doodle traced again and again until furry. */
  function traced(g, pts, p, o = {}) {
    const passes = o.passes ?? 3;
    let tip = null;
    for (let k = 0; k < passes; k++) {
      const q = B.clamp(p * passes - k);
      if (q > 0) tip = penStroke(g, pts, { ...o, p: q, seed: (o.seed ?? 1) + k * 31, amp: (o.amp ?? 0.35) * (1 + k * 0.4), w: (o.w ?? 0.38) * (k ? 0.8 : 1), blob: k === 0 });
    }
    return tip;
  }
  /** Hatching in a shape: bowed, uneven lines laid in as p grows. */
  function hatchFill(g, pathFn, bb, o = {}) {
    const p = o.p ?? 1;
    if (p <= 0) return null;
    const gap = (o.gap ?? 1.05) * U, a = B.deg(o.angle ?? 40), ca = Math.cos(a), sa = Math.sin(a);
    const cx = bb.x + bb.w / 2, cy = bb.y + bb.h / 2, R = Math.hypot(bb.w, bb.h) / 2;
    const n = Math.floor((2 * R) / gap), shown = Math.floor(n * p);
    let tip = null;
    g.save();
    g.beginPath();
    pathFn(g);
    g.clip();
    g.strokeStyle = o.color || PAL.blue;
    g.lineCap = "round";
    for (let i = 0; i <= shown; i++) {
      const d = -R + i * gap, h1 = B.hash01("h", i, o.seed ?? 1), h2 = B.hash01("k", i, o.seed ?? 1);
      const x0 = cx - R * ca - d * sa, y0 = cy - R * sa + d * ca, x1 = cx + R * ca - d * sa, y1 = cy + R * sa + d * ca;
      const mx = (x0 + x1) / 2 + (h1 - 0.5) * gap * 0.8, my = (y0 + y1) / 2 + (h2 - 0.5) * gap * 0.8;
      g.globalAlpha = 0.55 + 0.35 * h1;
      g.lineWidth = (0.17 + 0.12 * h2) * U;
      g.beginPath();
      g.moveTo(x0, y0);
      g.quadraticCurveTo(mx, my, x1, y1);
      g.stroke();
      tip = [cx - d * sa + ca * R * 0.2 * (i % 2 ? 1 : -1), cy + d * ca + sa * R * 0.2 * (i % 2 ? 1 : -1)];
    }
    g.restore();
    return tip;
  }
  /** Handwriting, revealed left to right, each word on its own slant. */
  function handText(g, lines, x, y, size, lineGap, p, o = {}) {
    if (p <= 0) return null;
    g.save();
    g.font = B.font(size, HAND, 400);
    g.textBaseline = "alphabetic";
    const widths = lines.map((l) => g.measureText(l).width), tot = widths.reduce((a, b) => a + b, 0);
    let budget = tot * p, tip = null;
    lines.forEach((line, li) => {
      if (budget <= 0) return;
      const lw = widths[li], show = Math.min(lw, budget);
      budget -= lw;
      const lx = o.align === "center" ? x - lw / 2 : x, ly = y + li * lineGap;
      g.save();
      g.beginPath();
      g.rect(lx - size, ly - size * 1.6, show + size, size * 2.4);
      g.clip();
      g.fillStyle = o.color || PAL.blue;
      g.globalAlpha = 0.92;
      let wx = lx;
      const sp = g.measureText(" ").width;
      line.split(" ").forEach((word, wi) => {
        const ww = g.measureText(word).width, r = B.rng(B.hash(word, wi, li, o.seed ?? 0));
        g.save();
        g.translate(wx, ly + r.range(-0.07, 0.07) * size);
        g.rotate(r.range(-0.035, 0.03));
        g.fillText(word, 0, 0);
        g.restore();
        wx += ww + sp;
      });
      g.restore();
      tip = [lx + show, ly - size * (0.25 + 0.2 * Math.sin(show * 0.08))];
    });
    g.restore();
    return tip;
  }
  /** Bubble letters, hollow, with a hatched shadow. ph: { outline, hatch, cross } 0..1. */
  function bubble(g, str, x, y, size, ph, o = {}) {
    if (ph.outline <= 0) return null;
    g.save();
    g.font = B.font(size, BUBBLE, 700);
    const w = g.measureText(str).width, h = size * 1.15, x0 = o.align === "left" ? x : x - w / 2;
    const off = size * 0.075, top = y - size * 0.82;
    if (ph.hatch > 0) {
      // the shadow, hatched, the letters knocked out
      const pad = size * 0.3, sw = Math.ceil(w + 2 * pad), sh = Math.ceil(h + 2 * pad);
      const s = B.scratch("nb-bubble:" + (o.key || str), sw, sh), hs = B.scratch("nb-bubble-hatch", sw, sh);
      const box = { x: 0, y: 0, w: sw, h: sh };
      hatchFill(hs, (c) => c.rect(0, 0, sw, sh), box, { p: ph.hatch, angle: 42, gap: (size * 0.035) / U, seed: 3 });
      if (ph.cross > 0) hatchFill(hs, (c) => c.rect(0, 0, sw, sh), box, { p: ph.cross, angle: -48, gap: (size * 0.05) / U, seed: 4 });
      s.font = g.font;
      s.textBaseline = "alphabetic";
      s.fillStyle = "#000";
      s.fillText(str, pad + off, pad + size * 0.82 + off);
      s.globalCompositeOperation = "source-in";
      s.drawImage(hs.canvas, 0, 0);
      s.globalCompositeOperation = "destination-out";
      s.fillText(str, pad, pad + size * 0.82);
      g.drawImage(s.canvas, x0 - pad, top - pad);
    }
    // outline: inked twice, with a faint pressed-in groove
    g.beginPath();
    g.rect(x0 - size * 0.2, top - size * 0.3, (w + size * 0.4) * ph.outline, h + size * 0.6);
    g.clip();
    g.lineJoin = "round";
    g.strokeStyle = B.rgba("#ffffff", 0.55);
    g.lineWidth = size * 0.02;
    g.strokeText(str, x0 + size * 0.03, y + size * 0.03);
    g.strokeStyle = PAL.blue;
    g.globalAlpha = 0.92;
    g.lineWidth = size * 0.045;
    g.strokeText(str, x0, y);
    g.globalAlpha = 0.6;
    g.lineWidth = size * 0.022;
    g.strokeText(str, x0 + size * 0.012, y - size * 0.01);
    g.restore();
    const q = ph.outline;
    return [x0 + w * q, y - size * (0.35 + 0.35 * Math.sin(q * 38))];
  }
  /** Hand-drawn arrow: shaft, then a two-stroke head. */
  function penArrow(g, pts, p, o = {}) {
    const shaftP = B.clamp(p / 0.82), headP = B.clamp((p - 0.82) / 0.18);
    let tip = penStroke(g, pts, { p: shaftP, w: o.w ?? 0.46, seed: o.seed ?? 5, flick: 0.05 });
    if (headP > 0) {
      const end = B.pointAt(pts, 1), a = end[2], L = (o.head ?? 3.2) * U;
      const left = [end[0] - Math.cos(a - 0.5) * L, end[1] - Math.sin(a - 0.5) * L];
      const right = [end[0] - Math.cos(a + 0.5) * L, end[1] - Math.sin(a + 0.5) * L];
      tip = penStrokes(g, [[left, [end[0], end[1]]], [[end[0], end[1]], right]], headP, { w: o.w ?? 0.46, seed: 77 }) || tip;
    }
    return tip;
  }
  const circlePts = (cx, cy, rx, ry, a0 = -1.9, turns = 1.06, n = 64) => Array.from({ length: n + 1 }, (_, i) => {
    const a = a0 + (i / n) * B.TAU * turns;
    return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry];
  });
  const starPts = (cx, cy, r) => Array.from({ length: 6 }, (_, i) => {
    const a = -Math.PI / 2 + i * (B.TAU * 2) / 5;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  });
  const spiralPts = (cx, cy, r, turns = 2.6) => Array.from({ length: 70 }, (_, i) => {
    const k = i / 69, a = k * turns * B.TAU;
    return [cx + Math.cos(a) * r * k, cy + Math.sin(a) * r * k];
  });

  // ---- the sheet (scene space, y down the page)
  function layoutPage(W, H) {
    const F = B.frame(W, H), P = F.portrait, u = F.u;
    const rule = P ? 5.6 * u : 4.6 * u, margin = P ? W * 0.15 : W * 0.115;
    const secH = P ? H * 0.82 : H * 0.9; // tall enough that old work has left the frame when the view rests
    const snap = (y) => Math.round(y / rule) * rule;
    return { F, P, u, rule, margin, secH, snap, left: margin + 2.4 * u, right: F.safe.r, top: (i) => i * secH };
  }
  function sheet(ctx, L, y0, y1) {
    const { F, u, rule, margin } = L, W = F.W, H = F.H;
    const tile = B.layer("nb-paper", W, H, (g, w, h) => B.paper(g, w, h, { color: PAL.paper, seed: 25, mottle: 0.06, fibers: 0.45, specks: 0.35, tooth: 0.05 }));
    for (let k = Math.floor(y0 / H); k * H < y1; k++) ctx.drawImage(tile, 0, k * H);
    // printed rules, the ink uneven along each one
    ctx.strokeStyle = PAL.rule;
    for (let y = Math.ceil(y0 / rule) * rule; y < y1; y += rule) {
      const ri = Math.round(y / rule);
      for (let s = 0; s < 12; s++) {
        const xa = (s / 12) * W, xb = ((s + 1) / 12) * W;
        ctx.globalAlpha = 0.75 + 0.25 * B.noise1(ri * 3.1 + s * 0.7, 9);
        ctx.lineWidth = (0.2 + 0.04 * B.noise1(ri + s, 4)) * u;
        ctx.beginPath();
        ctx.moveTo(xa, y + B.noise1(ri * 7 + s * 0.4, 2) * 0.12 * u);
        ctx.lineTo(xb, y + B.noise1(ri * 7 + (s + 1) * 0.4, 2) * 0.12 * u);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 0.8;
    ctx.strokeStyle = PAL.margin;
    ctx.lineWidth = 0.26 * u;
    ctx.beginPath();
    ctx.moveTo(margin, y0);
    ctx.lineTo(margin + 0.15 * u, y1);
    ctx.stroke();
    ctx.globalAlpha = 1;
    // spiral binding
    const gap = 4.6 * u, hx = Math.min(margin * 0.42, 6.5 * u);
    const wire = (y, col, w, d) => {
      ctx.strokeStyle = col;
      ctx.lineWidth = w * u;
      ctx.beginPath();
      ctx.moveTo(hx + (0.2 - d) * u, y + (0.2 - d) * u);
      ctx.quadraticCurveTo(hx * 0.3, y - (1.7 + d) * u, -u, y - (0.6 + d) * u);
      ctx.stroke();
    };
    ctx.lineCap = "round";
    for (let y = Math.ceil(y0 / gap) * gap; y < y1; y += gap) {
      ctx.fillStyle = "#5c5a55";
      ctx.beginPath();
      B.circle(ctx, hx, y, 0.85 * u);
      ctx.fill();
      wire(y, "#4a4a4a", 0.9, 0);
      wire(y, "#c9c9c4", 0.32, 0.25);
    }
  }

  // ---- subjects: the page's work (the setting: replace these)
  /** Every stroke's geometry, keyed by script id: (g, p) -> tip */
  function work(L) {
    const { F, P, u, rule, snap, left, right } = L, W = F.W;
    const cw = right - left, T = L.top, sec = L.secH;
    const hand = P ? 5.6 * u : 4.6 * u, bigLab = P ? 5.2 * u : 4.6 * u;
    // portrait: work placed by its screen y in section i
    const at = (i, sy) => T(i) + sec * 0.42 + (sy - F.safe.cy);
    const items = {};
    const add = (id, fn) => (items[id] = fn);

    // --- 0 title
    const tSize = Math.min(P ? 17 * u : 16 * u, cw * 0.19), tY = snap(P ? at(0, 760) : T(0) + sec * 0.46);
    const titleX = P ? left + cw / 2 : left + cw * 0.42;
    // a bubble heading in passes: outline, hatch, cross-hatch
    const bub = (id, str, x, y, size, o) => [id, id + "H1", id + "H2"].forEach((k, i) => add(k, (g, p) => bubble(g, str, x, y, size, { outline: i ? 1 : p, hatch: i > 1 ? 1 : i ? p : 0, cross: i > 1 ? p : 0 }, o)));
    bub("title", "RAINBOWS", titleX, tY, tSize, { key: "t" });
    const subY = tY + rule * (P ? 2 : 2);
    const subLines = P ? ["how do sunlight", "+ rain make one?"] : ["how do sunlight + rain make one?"];
    add("sub", (g, p) => handText(g, subLines, titleX, subY, hand * 1.05, rule, p, { align: "center", seed: 1 }));
    add("star1", (g, p) => {
      // margin doodles: a star, a spiral, a zigzag
      const st = P ? [right - 6 * u, tY - tSize * 1.25] : [left + cw * 0.88, tY - 2 * u];
      const zz = Array.from({ length: 9 }, (_, i) => [left + (P ? 2 : cw * 0.02) * u + i * 2.2 * u, (P ? subY + rule * 4.5 : tY - tSize * 1.1) + (i % 2 ? -1.4 : 1.4) * u]);
      const q = (i) => B.clamp(p * 3 - i);
      const tips = [
        traced(g, starPts(st[0], st[1], (P ? 4.2 : 3.6) * u), q(0), { passes: 3, seed: 8 }),
        traced(g, spiralPts(st[0] - (P ? 50 : 0) * u, st[1] + (P ? 1 : 11) * u, (P ? 3.4 : 3) * u), q(1), { passes: 2, seed: 9 }),
        traced(g, zz, q(2), { passes: 2, seed: 10 }),
      ];
      return tips.reduce((a, b) => b || a, null);
    });
    // a rain cloud doodle, traced twice
    const cc = P ? [left + cw * 0.32, at(0, 1330)] : [left + cw * 0.62, subY + rule * 2.6], cs = (P ? 1 : 0.7) * u;
    add("cloud", (g, p) => {
      const bumps = [[-9, 0, 5], [-3, -4, 6.5], [4.5, -3, 5.5], [10, 0.5, 4.5]], pts = [];
      bumps.forEach(([bx, by, r], i) => pts.push(...B.arcPts(cc[0] + bx * cs, cc[1] + by * cs, r * cs, Math.PI * (i ? 1.05 : 0.6), Math.PI * (i === 3 ? 2.4 : 1.95), 14)));
      pts.push([cc[0] - 9 * cs + 5 * cs * Math.cos(Math.PI * 0.6), cc[1] + 5 * cs * Math.sin(Math.PI * 0.6)]);
      const a = traced(g, pts, B.clamp(p * 1.4), { passes: 2, seed: 13 });
      const rain = [-7, -2, 3, 8].map((x, i) => [[cc[0] + x * cs, cc[1] + (7 + (i % 2) * 2) * cs], [cc[0] + (x - 1.6) * cs, cc[1] + (12 + (i % 2) * 2) * cs]]);
      return penStrokes(g, rain, B.clamp((p * 1.4 - 0.4) / 0.6), { w: 0.36, seed: 14 }) || a;
    });

    // --- 1 diagram: a ray bends in, bounces, bends out to the eye
    const R = P ? 16.5 * u : 14.5 * u;
    const dc = P ? [left + cw * 0.55, at(1, 930)] : [left + cw * 0.46, T(1) + sec * 0.47];
    const dropPts = (() => {
      const pts = [[dc[0], dc[1] - R * 1.75]];
      pts.push(...B.cubic(dc[0], dc[1] - R * 1.75, dc[0] + R * 0.35, dc[1] - R * 1.2, dc[0] + R, dc[1] - R * 0.62, dc[0] + R, dc[1], 16).slice(1));
      pts.push(...B.arcPts(dc[0], dc[1], R, 0, Math.PI, 28).slice(1));
      pts.push(...B.cubic(dc[0] - R, dc[1], dc[0] - R, dc[1] - R * 0.62, dc[0] - R * 0.35, dc[1] - R * 1.2, dc[0], dc[1] - R * 1.75, 16).slice(1));
      return pts;
    })();
    add("sketch", (g, p) => penStroke(g, circlePts(dc[0] + 0.4 * u, dc[1] - R * 0.3, R * 1.08, R * 1.3, -2.2, 1.1), { p, color: PAL.pencil, w: 0.3, amp: 0.6, alpha: 0.5, blob: false, seed: 4 }));
    add("drop", (g, p) => penStroke(g, dropPts, { p, w: 0.5, seed: 11, flick: 0.08 }));
    const onDrop = (a) => [dc[0] + Math.cos(a) * R, dc[1] + Math.sin(a) * R];
    const E = onDrop(Math.PI + 0.5), Bk = onDrop(0.15), X = onDrop(Math.PI - 0.55);
    const sunC = P ? [left + 7 * u, dc[1] - R * 2.15] : [left + 7 * u, dc[1] - R * 2.2]; // steep enough that each surface visibly bends the ray
    const eyeC = P ? [left + 9 * u, dc[1] + R * 2.3] : [left + 8 * u, dc[1] + R * 2.0];
    const ray = [[sunC[0] + 5 * u, sunC[1] + 3.5 * u], E, Bk, X, [eyeC[0] + 5.5 * u, eyeC[1] - 2.2 * u]];
    const leader = (from, to, txt, tx, ty, p, o = {}) => {
      const a = penStroke(g0, [from, to], { p: B.clamp(p / 0.3), w: 0.34, amp: 0.3, seed: o.seed ?? 21 });
      const b = handText(g0, [txt], tx, ty, o.size ?? bigLab, rule, B.clamp((p - 0.3) / 0.7), { align: o.align, seed: o.seed ?? 2 });
      return b || a;
    };
    let g0 = null; // the context the leader helper draws on (set by drawWork)
    const labX = P ? Math.min(dc[0] + R * 0.9, right - 26 * u) : dc[0] + R * 1.6;
    add("dropLab", (g, p) => {
      g0 = g;
      return leader([dc[0] + R * 0.95, dc[1] - R * 0.9], [labX + 1 * u, dc[1] - R * 1.55], "raindrop", labX, snap(dc[1] - R * 1.62), p, { align: "left" });
    });
    add("sun", (g, p) => {
      const a = traced(g, circlePts(sunC[0], sunC[1], 3.6 * u, 3.6 * u, 0, 1.05, 40), B.clamp(p * 1.6), { passes: 2, seed: 30 });
      const rays = Array.from({ length: 8 }, (_, i) => {
        const an = (i / 8) * B.TAU;
        return [[sunC[0] + Math.cos(an) * 4.8 * u, sunC[1] + Math.sin(an) * 4.8 * u], [sunC[0] + Math.cos(an) * 7 * u, sunC[1] + Math.sin(an) * 7 * u]];
      });
      return penStrokes(g, rays, B.clamp(p * 1.6 - 0.6), { w: 0.36, seed: 31 }) || a;
    });
    add("sunLab", (g, p) => handText(g, ["sunlight"], sunC[0] + 9 * u, snap(sunC[1] - 0.4 * u), bigLab, rule, p, { seed: 3 }));
    add("ray", (g, p) => penArrow(g, ray, p, { w: 0.5, seed: 40 }));
    add("eye", (g, p) => {
      const ex = eyeC[0], ey = eyeC[1], ew = 4.4 * u;
      const lid1 = B.quad(ex - ew, ey, ex, ey - ew * 0.75, ex + ew, ey, 16), lid2 = B.quad(ex + ew, ey, ex, ey + ew * 0.7, ex - ew, ey, 16);
      const a = penStrokes(g, [lid1, lid2], B.clamp(p * 1.5), { w: 0.4, seed: 50 });
      const b = traced(g, circlePts(ex + 0.5 * u, ey, 1.5 * u, 1.5 * u, 0, 1.05, 24), B.clamp(p * 1.5 - 0.5), { passes: 3, w: 0.5, seed: 52 });
      return b || a;
    });
    add("eyeLab", (g, p) => handText(g, ["your eye"], eyeC[0] + 7 * u, snap(eyeC[1] + 2.4 * u), bigLab, rule, p, { seed: 4 }));
    // shade the drop's lower right
    const dropBB = { x: dc[0] - R, y: dc[1] - R * 1.75, w: 2 * R, h: R * 2.75 };
    const shade = (k, r, a, gap, seed) => (g, p) => hatchFill(g, (c) => (c.arc(dc[0] + R * k, dc[1] + R * (k - 0.4), R * r, 0, B.TAU), c.clip(), c.beginPath(), B.poly(c, dropPts, true)), dropBB, { p, angle: a, gap, seed });
    add("dropH1", shade(0.95, 1.05, 35, 1.0, 61));
    add("dropH2", shade(1.25, 0.85, -50, 1.1, 62));

    // --- 2 key number: a wrong guess struck out, the right one ringed
    const nY = snap(P ? at(2, 400) : T(2) + sec * 0.24);
    add("numLine", (g, p) => handText(g, P ? ["angle from the shadow", "of your head:"] : ["angle from the shadow of your head:"], left, nY, hand, rule, p, { seed: 5 }));
    const nSize = P ? 23 * u : 19 * u, nBase = snap(nY + rule * (P ? 2 : 1.4) + nSize * 0.95), nBase2 = P ? snap(nBase + nSize * 1.2) : nBase;
    const n1x = P ? left + cw * 0.02 : left + cw * 0.06, n2x = P ? left + cw * 0.4 : left + cw * 0.5;
    bub("n45", "45°", n1x, nBase, nSize, { align: "left", key: "45" });
    const n45w = nSize * 1.6;
    add("strike", (g, p) => penStrokes(g, [[[n1x - 1.5 * u, nBase - nSize * 0.2], [n1x + n45w, nBase - nSize * 0.55]], [[n1x - u, nBase - nSize * 0.62], [n1x + n45w - 2 * u, nBase - nSize * 0.12]]], p, { color: PAL.red, w: 0.7, seed: 70 }));
    bub("n42", "42°", n2x, nBase2, nSize, { align: "left", key: "42" });
    add("ring", (g, p) => traced(g, circlePts(n2x + nSize * 0.8, nBase2 - nSize * 0.38, nSize * 1.05, nSize * 0.68, -2.6, 1.15), p, { passes: 2, color: PAL.red, w: 0.6, amp: 0.8, seed: 80 }));
    // the angle: your eye, your head's shadow, the bow 42° up (pointing at the 42°)
    const O = P ? [left + 6 * u, at(2, 1360)] : [n2x - cw * 0.1, nBase + rule * 3.4], aL = cw * (P ? 0.6 : 0.36), upL = aL * (P ? 0.62 : 0.3), d8 = B.deg(8), d42 = B.deg(42);
    const sh = [O[0] + Math.cos(d8) * aL, O[1] + Math.sin(d8) * aL], up = [O[0] + Math.cos(d8 - d42) * upL, O[1] + Math.sin(d8 - d42) * upL];
    add("angle", (g, p) => {
      g0 = g;
      const a = penStrokes(g, [[O, sh], [O, up], B.arcPts(O[0], O[1], upL * 0.7, d8, d8 - d42, 14)], B.clamp(p * 1.5), { w: 0.4, seed: 85 });
      const b = handText(g, ["shadow"], sh[0] + 2 * u, sh[1] + 1.2 * u, bigLab, rule, B.clamp(p * 3 - 1.8), { seed: 86 });
      traced(g, circlePts(O[0], O[1], 1.3 * u, 0.9 * u, 0, 1.05, 18), B.clamp(p * 3), { passes: 2, w: 0.45, seed: 87 });
      return b || a;
    });

    // margin doodles at the foot of each piece of work
    [0, 2, 3, 4].forEach((i) => add("foot" + i, (g, p) => {
      const y = P ? at(i, 1670) : T(i) + sec * 0.42 + F.H * 0.38, q = (k) => B.clamp(p * 3 - k), x = (k) => left + cw * ((k + i) % 3) * 0.36;
      const zz = Array.from({ length: 10 }, (_, k) => [x(0) + k * 2.4 * u, y + (k % 2 ? -1.3 : 1.3) * u]);
      return [traced(g, zz, q(0), { passes: 2, seed: 20 + i }), traced(g, starPts(x(1) + 4 * u, y, 3 * u), q(1), { passes: 2, seed: 30 + i }), traced(g, spiralPts(x(2) + 4 * u, y, 3 * u), q(2), { passes: 2, seed: 40 + i })].reduce((a, b) => b || a, null);
    }));

    // --- 3 steps
    const sY = snap(P ? at(3, 420) : T(3) + sec * 0.1), sGap = rule * (P ? 4 : 3);
    const stepLine = (i) => sY + sGap * i;
    const tick = (x, y, p, seed) => penStrokes(g0, [[[x, y], [x + 1.4 * u, y + 1.6 * u], [x + 4.6 * u, y - 2.6 * u]]], p, { color: PAL.red, w: 0.62, seed });
    // numbers down the margin first, then each line
    const nw = hand * 1.3;
    add("nums", (g, p) => [0, 1, 2].reduce((tip, i) => handText(g, [i + 1 + "."], left, stepLine(i), hand, rule, B.clamp(p * 3 - i), { seed: 5 }) || tip, null));
    add("s1", (g, p) => handText(g, ["light bends going in"], left + nw, stepLine(0), hand, rule, p, { seed: 6 }));
    add("tick1", (g, p) => ((g0 = g), tick(P ? right - 4.2 * u : left + 0.62 * cw, stepLine(0) - 1.2 * u, p, 90)));
    add("s2", (g, p) => handText(g, ["it bounces off the back"], left + nw, stepLine(1), hand * 0.95, rule, p, { seed: 7 }));
    add("tick2", (g, p) => ((g0 = g), tick(P ? right - 4.2 * u : left + 0.62 * cw, stepLine(1) - 1.2 * u, p, 91)));
    add("s3", (g, p) => handText(g, ["bends again coming out:"], left + nw, stepLine(2), hand, rule, p, { seed: 8 }));
    add("s3b", (g, p) => handText(g, P ? ["each colour by its own", "amount, so they fan out"] : ["each colour by its own amount, so they fan out"], left + nw, stepLine(2) + rule, hand * 0.95, rule, p, { seed: 9 }));
    const fanO = [left + cw * (P ? 0.3 : 0.16), stepLine(2) + rule * (P ? 5.3 : 3.6)];
    const fanL = P ? 36 * u : 30 * u;
    // the fan leaves a drop: pencilled first, inked later
    const dR = (P ? 7 : 3.5) * u, dX = fanO[0] - dR * 0.9;
    const drop = [[dX, fanO[1] - dR * 1.8], ...B.arcPts(dX, fanO[1], dR, -0.8, Math.PI + 0.8, 24), [dX, fanO[1] - dR * 1.8]];
    const fanLs = [drop, [[dX - dR * 3, fanO[1] - dR * 1.6], [dX - dR * 0.8, fanO[1] - dR * 0.45]], ...[-0.08, 0.02, 0.12].map((a) => [fanO, [fanO[0] + Math.cos(a) * fanL, fanO[1] + Math.sin(a) * fanL]])];
    add("fanSk", (g, p) => penStrokes(g, fanLs, p, { color: PAL.pencil, w: 0.34, amp: 0.7, alpha: 0.75, blob: false, seed: 94 }));
    add("fan", (g, p) => {
      const a = penStrokes(g, fanLs, B.clamp(p * 1.4), { w: 0.42, seed: 95 });
      const b = handText(g, ["red"], fanO[0] + fanL + 1.5 * u, fanO[1] - fanL * 0.06, bigLab, rule, B.clamp(p * 3 - 1.6), { seed: 10 });
      const c = handText(g, ["violet"], fanO[0] + fanL + 1.5 * u, fanO[1] + fanL * 0.2, bigLab, rule, B.clamp(p * 3 - 2), { seed: 11 });
      return c || b || a;
    });
    add("under", (g, p) => {
      // under the note's last line, three marks at its end
      const m = B.scratch("nb-m", 4, 4);
      m.font = B.font(hand * 0.95, HAND, 400);
      const y = stepLine(2) + rule * (P ? 2 : 1) + 1.6 * u, x1 = left + nw + m.measureText(P ? "amount, so they fan out" : "each colour by its own amount, so they fan out").width + 2 * u;
      const ticks = [-1, 0, 1].map((i) => [[x1 + 1.5 * u, y + i * 1.2 * u], [x1 + 4.5 * u, y + i * 2.6 * u]]);
      return penStrokes(g, [[[left + nw, y], [x1, y - 0.3 * u]], [[left + nw + u, y + 0.9 * u], [x1 - 3 * u, y + 0.6 * u]], ...ticks], p, { color: PAL.red, w: 0.55, seed: 96 });
    });

    // --- 4 close: the answer in a ruled box, a hatched rainbow
    const bx = left + (P ? 0 : cw * 0.02), by = snap(P ? at(4, 440) : T(4) + sec * 0.26) - rule * 0.8, bw = P ? cw * 0.98 : cw * 0.6, bh = rule * 3;
    const boxSides = [[[bx, by], [bx + bw, by + 0.3 * u]], [[bx + bw, by], [bx + bw - 0.4 * u, by + bh]], [[bx + bw, by + bh], [bx, by + bh - 0.2 * u]], [[bx, by + bh], [bx + 0.3 * u, by - 0.6 * u]]];
    add("box", (g, p) => penStrokes(g, boxSides, p, { w: 0.55, seed: 100, amp: 0.3 }));
    const shadow = (c) => {
      c.moveTo(bx + bw + 0.4 * u, by + 1.6 * u);
      c.lineTo(bx + bw + 1.8 * u, by + 1.6 * u);
      c.lineTo(bx + bw + 1.8 * u, by + bh + 1.6 * u);
      c.lineTo(bx + 1.6 * u, by + bh + 1.6 * u);
      c.lineTo(bx + 1.6 * u, by + bh + 0.4 * u);
      c.lineTo(bx + bw + 0.4 * u, by + bh + 0.4 * u);
      c.closePath();
    };
    add("boxH", (g, p) => hatchFill(g, shadow, { x: bx, y: by, w: bw + 2 * u, h: bh + 2 * u }, { p, angle: 45, gap: 0.7, seed: 101 }));
    add("answer", (g, p) => handText(g, P ? ["sun behind you,", "rain in front = rainbow!"] : ["sun behind you,", "rain in front = rainbow!"], bx + 2.5 * u, by + rule * 1.25, hand * 1.05, rule, p, { seed: 12 }));
    const bowC = P ? [left + cw * 0.5, by + bh + rule * 9.6] : [left + cw * 0.83, by + bh + rule * 0.2], bowR = P ? 30 * u : 22 * u;
    add("bow", (g, p) => {
      let tip = null;
      [1, 0.8, 0.6].forEach((k, i) => (tip = penStroke(g, B.arcPts(bowC[0], bowC[1], bowR * k, Math.PI, B.TAU, 40), { p: B.clamp(p * 3 - i * 0.9), w: 0.45, seed: 110 + i }) || tip));
      const band = (c) => {
        c.arc(bowC[0], bowC[1], bowR * 0.8, Math.PI, B.TAU);
        c.arc(bowC[0], bowC[1], bowR * 0.6, B.TAU, Math.PI, true);
        c.closePath();
      };
      hatchFill(g, band, { x: bowC[0] - bowR, y: bowC[1] - bowR, w: 2 * bowR, h: bowR }, { p: B.clamp(p * 2 - 1), angle: 70, gap: 0.9, seed: 115 });
      return tip;
    });
    add("stars", (g, p) => {
      const s1 = [bowC[0] - bowR * 0.95, bowC[1] - bowR * 1.05], s2 = [bowC[0] + bowR * 0.95, bowC[1] - bowR * 1.0];
      const a = traced(g, starPts(s1[0], s1[1], 2.4 * u), B.clamp(p * 2), { passes: 1, color: PAL.red, w: 0.5, seed: 120 });
      return traced(g, starPts(s2[0], s2[1], 2 * u), B.clamp(p * 2 - 1), { passes: 1, color: PAL.red, w: 0.5, seed: 121 }) || a;
    });
    // you, from behind, looking through the rain
    const yc = [bowC[0] - bowR * (P ? 0.1 : 0.05), bowC[1] + (P ? 6 : 3) * u], ys = (P ? 1 : 0.6) * u;
    add("you", (g, p) => {
      const a = traced(g, circlePts(yc[0], yc[1] + 3 * ys, 3 * ys, 3.2 * ys, -1.6, 1.05, 22), B.clamp(p * 2.5), { passes: 2, w: 0.42, seed: 125 });
      const body = [[[yc[0], yc[1] + 6.3 * ys], [yc[0], yc[1] + 15 * ys]], [[yc[0] - 5 * ys, yc[1] + 10.5 * ys], [yc[0], yc[1] + 8 * ys], [yc[0] + 5 * ys, yc[1] + 10.5 * ys]], [[yc[0] - 3.5 * ys, yc[1] + 22 * ys], [yc[0], yc[1] + 15 * ys], [yc[0] + 3.5 * ys, yc[1] + 22 * ys]]];
      const b = penStrokes(g, body, B.clamp((p * 2.5 - 0.6) / 1.4), { w: 0.42, seed: 126 });
      const rain = Array.from({ length: 7 }, (_, i) => { const x = bowC[0] - bowR * 0.55 + i * bowR * 0.18, y = bowC[1] - bowR * (0.42 - (i % 3) * 0.1); return [[x, y], [x - 1.2 * ys, y + 4 * ys]]; });
      return penStrokes(g, rain, B.clamp((p * 2.5 - 1.6) / 0.9), { w: 0.32, seed: 127 }) || b || a;
    });
    return { items, dc, R };
  }

  /** The ballpoint: steel tip, ribbed grip, clear barrel, end plug. */
  function penTool(ctx, x, y, lift, ink) {
    const u = U, col = INK[ink] || PAL.blue;
    ctx.save();
    ctx.translate(x + lift * 1.5 * u, y - lift * 2.5 * u);
    B.contactShadow(ctx, 5 * u + lift * 3 * u, 4 * u + lift * 4 * u, 6 * u, 2.2 * u, 0.18 - lift * 0.08);
    ctx.rotate(-0.95); // the barrel points up and right (a right hand)
    const bar = (x0, x1, h, stops) => {
      ctx.fillStyle = B.linear(ctx, 0, -h, 0, h, stops);
      ctx.fillRect(x0, -h, x1 - x0, 2 * h);
    };
    ctx.fillStyle = B.linear(ctx, 0, -1.2 * u, 0, 1.2 * u, ["#e2e2de", "#9a9a96", "#5f5f5c"]);
    ctx.beginPath();
    B.poly(ctx, [[0, 0], [4.5 * u, -1.15 * u], [4.5 * u, 1.15 * u]], true);
    ctx.fill();
    ctx.fillStyle = "#222";
    ctx.beginPath();
    B.circle(ctx, 0.25 * u, 0, 0.3 * u);
    ctx.fill();
    bar(4.5 * u, 14 * u, 1.55 * u, ["rgba(90,96,110,0.55)", "rgba(40,44,56,0.7)", "rgba(20,22,30,0.8)"]); // grip
    ctx.fillStyle = "rgba(255,255,255,0.18)";
    for (let k = 5.5; k < 14; k += 1.1) ctx.fillRect(k * u, -1.55 * u, 0.35 * u, 3.1 * u);
    bar(14 * u, 62 * u, 1.65 * u, ["rgba(255,255,255,0.8)", "rgba(220,226,232,0.55)", "rgba(190,196,204,0.65)", "rgba(150,156,166,0.8)"]);
    ctx.fillStyle = B.rgba(col, 0.85);
    ctx.fillRect(4.5 * u, -0.38 * u, 56 * u, 0.76 * u); // the refill
    ctx.fillStyle = "rgba(255,255,255,0.5)"; // a facet edge
    ctx.fillRect(14 * u, -1.05 * u, 48 * u, 0.22 * u);
    bar(62 * u, 66 * u, 1.35 * u, [B.shade(col, 0.25), col, B.shade(col, -0.35)]); // end plug
    ctx.restore();
  }

  // ---- camera: the notebook slides under the hand
  function camera(L, t) {
    let stop = 0, slide = 0;
    for (let i = 1; i < BEATS.length; i++) {
      const g = B.span(t, BEATS[i] - 0.32, BEATS[i] + 0.4, "inOutCubic");
      stop += (CAM_STOPS[i] - CAM_STOPS[i - 1]) * g;
      slide = Math.max(slide, Math.sin(Math.PI * g));
    }
    const y = L.top(stop) + L.secH * 0.42; // the work sits a little above each section centre
    const dx = B.noise1(t * 0.35, 3) * 1.2 * L.u + slide * 2.5 * L.u;
    const rot = B.deg(0.6 * B.noise1(t * 0.25, 7) - 0.8 * slide);
    return { y, dx, rot };
  }

  function draw(ctx, W, H, t) {
    const L = layoutPage(W, H), F = L.F;
    U = L.u;
    const cam = camera(L, t);
    ctx.fillStyle = "#4b4740";
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2 + cam.dx, F.safe.cy);
    ctx.rotate(cam.rot);
    ctx.translate(-W / 2, -cam.y);
    const y0 = cam.y - F.safe.cy - H * 0.1, y1 = cam.y + (H - F.safe.cy) + H * 0.1;
    sheet(ctx, L, y0, y1);
    const { items } = work(L);
    let active = null, last = null, next = null;
    for (const [id, at, dur, ink] of SCRIPT) {
      const fn = items[id];
      if (!fn) continue;
      const p = B.prog(t, at, dur);
      if (t < at) {
        if (!next) next = { id, at, ink };
        continue;
      }
      const tip = fn(ctx, p);
      if (p < 1) active = { tip, ink };
      else last = { tip, end: at + dur, ink };
    }
    // the pen: on the active stroke, else lifted
    let pen = null;
    if (active && active.tip) pen = { x: active.tip[0], y: active.tip[1], lift: 0, ink: active.ink };
    else if (last && last.tip) {
      // between pieces it leaves the page
      const gap = next ? next.at - last.end : 99, q = B.clamp((t - last.end) / Math.max(0.05, gap)), long = gap > 0.5;
      const nt = next ? items[next.id](B.scratch("nb-probe", 4, 4), 0.002) : null;
      const out = long ? B.smooth(0, 0.12, t - last.end) * (next ? 1 - B.smooth(next.at - 0.25, next.at, t) : 1) : 0;
      const b = nt && (!long || q > 0.5) ? (long ? nt : [B.lerp(last.tip[0], nt[0], B.ease.inOutSine(q)), B.lerp(last.tip[1], nt[1], B.ease.inOutSine(q))]) : last.tip;
      if (out < 0.98) pen = { x: b[0] + out * W * 0.8, y: b[1] + out * H * 0.5, lift: Math.max(0.25, out, 0.6 * Math.sin(Math.PI * q)), ink: q > 0.5 && next ? next.ink : last.ink };
    }
    if (pen) penTool(ctx, pen.x, pen.y, pen.lift, pen.ink);
    ctx.restore();
    // finishing: edge shading, warm grain
    ctx.fillStyle = B.linear(ctx, 0, 0, L.margin * 0.9, 0, ["rgba(60,50,30,0.28)", "rgba(60,50,30,0)"]);
    ctx.fillRect(0, 0, L.margin, H);
    B.vignette(ctx, W, H, { color: "#6b5a3a", amount: 0.22, inner: 0.55, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12, mode: "multiply", seed: 25 });
  }

  // ---- sound: pen scratches, paper slides, chimes
  SOUND.define("doodle-pen", (v, o) => {
    // ballpoint scratch, rising over the stroke
    const d = o.dur ?? 0.3;
    v.noise({ filter: "bandpass", q: 3, f: 1700, f2: 2900, glide: d, a: 0.01, hold: d * 0.85, len: 0.04, peak: 0.16 });
    v.grains({ span: d, count: Math.max(3, d * 70), filter: "bandpass", f: 3600, q: 2, len: 0.007, peak: 0.12 });
  }, { verb: 0.06 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.45 });
    for (const [id, at, dur, ink] of SCRIPT) {
      if (ink === "red") k.at(at - 0.02, "click", { gain: 0.35, pitch: 4 });
      k.at(at, ink === "pencil" ? "pencil" : "doodle-pen", { dur: Math.max(0.08, dur), gain: ink === "pencil" ? 0.7 : 0.75, pitch: Math.min(4, dur * 4) - 1, pan: k.rng() * 0.4 - 0.2 });
    }
    BEATS.slice(1).forEach((b) => k.at(b - 0.32, "paper", { dur: 0.7, gain: 0.8 }));
    k.at(6.5, "scribble", { dur: 0.14, pitch: -7, gain: 0.6 }); // the red cross: a low scrape
    k.at(7.08, "chime", { note: "E6", gain: 0.3 });
    [9.21, 9.57].forEach((at, i) => k.at(at, "chime", { note: i ? "B6" : "G6", gain: 0.28 }));
    k.at(11.0, "chime", { note: "E6", gain: 0.25 });
    k.at(12.31, "thud", { gain: 0.45 });
    k.at(13.37, "chime", { note: "G6", gain: 0.3 }).at(13.42, "sparkle", { gain: 0.15 });
  }

  Player.register({
    id: "notebook-doodle",
    name: "Notebook Doodle",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Gloria+Hallelujah&family=Fredoka:wght@700&display=swap",
      faces: ['400 20px "Gloria Hallelujah"', '700 20px "Fredoka"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.86, 5.22, 7.72, 9.61, 11.25, 13.9],
    draw,
    score,
  });
})();
