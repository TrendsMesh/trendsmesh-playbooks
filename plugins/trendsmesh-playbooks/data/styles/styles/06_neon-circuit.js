/* 06 Neon Circuit - reference animation.
 * Topic (setting, replace it): "How does a message cross the internet?" - packets hopping between routers.
 * Rendering (keep it): a navy-indigo void, wandering colour clouds, a scrolling perspective floor grid; dark glass
 * cards with a hairline rim bright cyan at one corner; line icons traced on in glowing tiles; thin wires carrying
 * white-headed sparks; gradient headlines built word by word; capsule pills; a huge gradient numeral. Everything
 * bright is additive, then a two-radius bloom and a dark vignette; no grain. One continuous camera that pushes in and
 * pans between regions; a dive through a hub with radial streaks and a white flash.
 */
(function () {
"use strict";
const B = window.Brush;

// ---- palette and type (from the card)
const PAL = { void: "#060a24", indigo: "#1a1352", cyan: "#34e2f7", blue: "#4f82ff", violet: "#9a62ff", coral: "#ff5a7e",
  mint: "#42efb0", ice: "#eef1ff", pink: "#ff7ad9" /* only a touch, in one backdrop cloud */ };
const HEAD = "Sora", BODY = "Manrope";
const DUR = 12, BEATS = [0, 1.8, 4.0, 6.0, 8.2, 10.3];

// ---- neon helpers (reuse these)
/** Rounded-rectangle outline as points (for traced icons). */
function rrPts(x, y, w, h, r, n = 5) {
  const out = [], corner = (cx, cy, a0) => { for (let i = 0; i <= n; i++) { const a = a0 + (i / n) * (Math.PI / 2); out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } };
  corner(x + w - r, y + r, -Math.PI / 2); corner(x + w - r, y + h - r, 0); corner(x + r, y + h - r, Math.PI / 2); corner(x + r, y + r, Math.PI);
  out.push(out[0]);
  return out;
}
const lighter = (ctx, fn) => { ctx.save(); ctx.globalCompositeOperation = "lighter"; fn(); ctx.restore(); };
/** Entrance: fade up while growing from 85 % with a small overshoot. Returns { s, a }. */
function enter(t, at, dur = 0.5) {
  const p = B.prog(t, at, dur);
  return { s: p <= 0 ? 0.85 : 0.85 + 0.15 * B.ease.outBack(p, 2.2), a: B.ease.outCubic(p) };
}
/** Glass card, centred: dark see-through fill, big soft shadow, faint inner glows at opposite corners, a hairline rim
 *  bright cyan at the top left fading away, a short white highlight on the top edge. */
function glassCard(ctx, cx, cy, w, h, u, o = {}) {
  const a = o.alpha ?? 1, s = o.s ?? 1;
  if (a <= 0.001) return;
  const r = o.r ?? 3.2 * u, x = -w / 2, y = -h / 2;
  ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s); ctx.globalAlpha *= a;
  B.withShadow(ctx, { color: "rgba(0,0,8,0.7)", blur: 7 * u, y: 3 * u }, () => {
    ctx.beginPath(); B.roundRect(ctx, x, y, w, h, r);
    ctx.fillStyle = B.linear(ctx, x, y, x + w, y + h, [B.rgba(PAL.indigo, 0.62), B.rgba("#0c0f36", 0.72)]); ctx.fill();
  });
  B.clip(ctx, (c) => B.roundRect(c, x, y, w, h, r), () => {
    B.glow(ctx, x, y, Math.max(w, h) * 0.65, o.glowA || PAL.cyan, 0.14, { add: true });
    B.glow(ctx, x + w, y + h, Math.max(w, h) * 0.6, o.glowB || PAL.violet, 0.16, { add: true });
  });
  ctx.beginPath(); B.roundRect(ctx, x, y, w, h, r); ctx.lineWidth = Math.max(1, 0.16 * u);
  ctx.strokeStyle = B.linear(ctx, x, y, x + w, y + h, [[0, B.rgba(PAL.cyan, 0.95)], [0.45, B.rgba(PAL.blue, 0.35)], [1, B.rgba(PAL.violet, 0.12)]]);
  ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + r, y + 0.6); ctx.lineTo(x + w * 0.45, y + 0.6); ctx.lineWidth = Math.max(1, 0.22 * u);
  ctx.strokeStyle = B.linear(ctx, x + r, 0, x + w * 0.45, 0, [B.rgba("#ffffff", 0.8), B.rgba("#ffffff", 0)]);
  ctx.stroke(); ctx.restore();
}
/** Icon tile in a soft halo; a line icon in one cyan-to-violet gradient, traced stroke by stroke as p goes 0 -> 1. */
function iconTile(ctx, cx, cy, size, strokes, u, o = {}) {
  const a = o.a ?? 1, s = o.s ?? 1, lit = o.lit ?? 0;
  if (a <= 0.001) return;
  const half = size / 2, k = size * 0.3, n = strokes.length, p = o.p ?? 1;
  ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s); ctx.globalAlpha *= a;
  B.glow(ctx, 0, 0, size * (1.15 + 0.25 * lit), o.halo || PAL.blue, 0.28 + 0.35 * lit, { add: true });
  ctx.beginPath(); B.roundRect(ctx, -half, -half, size, size, size * 0.24);
  ctx.fillStyle = B.linear(ctx, -half, -half, half, half, [B.mix(PAL.indigo, "#2a2a7a", 0.4 + 0.4 * lit), "#0b0e33"]); ctx.fill();
  ctx.lineWidth = Math.max(1, size * 0.018 * (1 + lit));
  ctx.strokeStyle = B.linear(ctx, -half, -half, half, half, [B.rgba(PAL.cyan, 0.9), B.rgba(PAL.violet, 0.35 + 0.4 * lit)]); ctx.stroke();
  const grad = B.linear(ctx, -k, -k, k, k, [PAL.cyan, PAL.blue, PAL.violet]);
  strokes.forEach((st, i) => {
    const sp = B.clamp(p * n - i);
    if (sp > 0) B.strokeReveal(ctx, st.map(([px, py]) => [px * k, py * k]), sp, { width: size * 0.055, color: grad });
  });
  ctx.restore();
}
/** Wire: a thin dim curve drawn on to p, with a faint additive halo; optional arrowhead. */
function wire(ctx, pts, p, u, o = {}) {
  if (p <= 0) return;
  const shown = B.trim(pts, 0, p);
  ctx.save(); ctx.globalAlpha *= o.alpha ?? 1;
  B.strokeReveal(ctx, shown, 1, { width: Math.max(1, 0.28 * u), color: B.rgba(o.color || PAL.blue, 0.55) });
  lighter(ctx, () => B.strokeReveal(ctx, shown, 1, { width: Math.max(1, 0.9 * u), color: B.rgba(o.color || PAL.blue, 0.1) }));
  if (o.head && p > 0.98) {
    const tip = B.pointAt(pts, 1), hl = 1.6 * u, a = tip[2];
    ctx.beginPath(); ctx.moveTo(tip[0] - Math.cos(a - 0.5) * hl, tip[1] - Math.sin(a - 0.5) * hl); ctx.lineTo(tip[0], tip[1]);
    ctx.lineTo(tip[0] - Math.cos(a + 0.5) * hl, tip[1] - Math.sin(a + 0.5) * hl);
    ctx.strokeStyle = B.rgba(o.color || PAL.cyan, 0.9); ctx.lineWidth = Math.max(1, 0.35 * u); ctx.lineCap = ctx.lineJoin = "round"; ctx.stroke();
  }
  ctx.restore();
}
/** Spark at s (0..1) along a wire: white head, fading coloured tail, additive; o.dir -1 runs it backward. */
function spark(ctx, pts, s, u, color = PAL.cyan, o = {}) {
  if (s < 0 || s > 1) return;
  const tail = o.tail ?? 0.16, n = 14, dir = o.dir ?? 1;
  lighter(ctx, () => {
    for (let i = n; i >= 0; i--) {
      const pt = B.pointAt(pts, B.clamp(s - dir * (tail * i) / n)), k = 1 - i / n;
      ctx.beginPath(); B.circle(ctx, pt[0], pt[1], (0.25 + 0.55 * k) * u);
      ctx.fillStyle = B.rgba(i < 2 ? "#ffffff" : color, 0.08 + 0.55 * k * k); ctx.fill();
    }
    const h = B.pointAt(pts, s);
    B.glow(ctx, h[0], h[1], 4 * u, color, 0.55); B.glow(ctx, h[0], h[1], 1.4 * u, "#ffffff", 0.9);
  });
}
/** Expanding ring (arrivals, emphasis); k = 0..1 of its life. */
function ring(ctx, x, y, r0, r1, k, color, u) {
  if (k <= 0 || k >= 1) return;
  lighter(ctx, () => {
    ctx.beginPath(); ctx.arc(x, y, B.lerp(r0, r1, B.ease.outCubic(k)), 0, B.TAU);
    ctx.strokeStyle = B.rgba(color, 0.85 * (1 - k)); ctx.lineWidth = Math.max(1, 0.4 * u * (1 - k) + 0.1 * u); ctx.stroke();
  });
}
function hub(ctx, x, y, r, t, u, a = 1, color = PAL.cyan) {
  if (a <= 0.001) return;
  ctx.save(); ctx.globalAlpha *= a;
  lighter(ctx, () => { B.glow(ctx, x, y, r * 3.2, color, 0.35 * (1 + 0.2 * B.wave(t, 1.8))); B.glow(ctx, x, y, r * 0.9, "#ffffff", 0.95); });
  ctx.lineWidth = Math.max(1, 0.15 * u);
  [1.5, 2.3].forEach((m, i) => {
    ctx.beginPath(); ctx.arc(x, y, r * m * (1 + 0.04 * B.wave(t, 2.4, i * 0.3)), 0, B.TAU);
    ctx.strokeStyle = B.rgba(i ? PAL.violet : color, i ? 0.4 : 0.7); ctx.stroke();
  });
  ctx.restore();
}
/** Eyebrow: wide-spaced capitals after a glowing dot. */
function eyebrow(ctx, text, x, y, size, o = {}) {
  const a = o.alpha ?? 1;
  if (a <= 0.001) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.font = B.font(size, BODY, 800); ctx.letterSpacing = (size * 0.28).toFixed(1) + "px";
  const tw = ctx.measureText(text).width, dot = size * 1.3, x0 = o.align === "left" ? x : x - (tw + dot) / 2;
  lighter(ctx, () => { B.glow(ctx, x0 + size * 0.3, y, size * 1.3, o.color || PAL.cyan, 0.55); B.glow(ctx, x0 + size * 0.3, y, size * 0.32, "#ffffff", 1); });
  ctx.fillStyle = B.rgba(PAL.ice, 0.85); ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText(text, x0 + dot, y + size * 0.04); ctx.restore();
}
function headLayout(ctx, text, size, maxW) {
  ctx.save(); ctx.font = B.font(size, HEAD, 700); ctx.letterSpacing = (-size * 0.02).toFixed(1) + "px";
  const space = ctx.measureText(" ").width, lines = [];
  text.split("\n").forEach((para) => {
    let cur = [], w = 0;
    for (const word of para.split(" ")) {
      const ww = ctx.measureText(word).width;
      if (cur.length && w + space + ww > maxW) { lines.push({ words: cur, w }); cur = []; w = 0; }
      cur.push({ word, x: cur.length ? w + space : 0, w: ww });
      w = cur.length > 1 ? w + space + ww : ww;
    }
    if (cur.length) lines.push({ words: cur, w });
  });
  ctx.restore();
  return { lines, size, lh: size * 1.12, width: Math.max(...lines.map((l) => l.w)) };
}
/** Gradient headline: ONE gradient across each line (white -> ice -> violet); words build one by one, lifting in.
 *  o: { at, gap, align, leftK (0..1: centred -> flush left), alpha } */
function headline(ctx, text, x, y, size, maxW, t, o = {}) {
  const Lh = headLayout(ctx, text, size, maxW), a = o.alpha ?? 1;
  if (a <= 0.001) return Lh;
  ctx.save(); ctx.globalAlpha *= a; ctx.font = B.font(size, HEAD, 700); ctx.letterSpacing = (-size * 0.02).toFixed(1) + "px";
  ctx.textAlign = "left"; ctx.textBaseline = "middle";
  let wi = 0;
  const top = y - (Lh.lh * Lh.lines.length) / 2;
  Lh.lines.forEach((line, li) => {
    const lx = o.align === "left" ? x : B.lerp(x - line.w / 2, x - Lh.width / 2, o.leftK ?? 0), ly = top + Lh.lh * (li + 0.5);
    const grad = B.linear(ctx, lx, 0, lx + line.w, 0, [[0, "#ffffff"], [0.5, "#bfe3ff"], [1, "#b59bff"]]);
    for (const wd of line.words) {
      const p = o.at == null ? 1 : B.prog(t, o.at + wi * (o.gap ?? 0.12), 0.45, "outCubic");
      wi++;
      if (p <= 0) continue;
      ctx.globalAlpha = a * p; ctx.fillStyle = grad; ctx.fillText(wd.word, lx + wd.x, ly + (1 - p) * size * 0.35);
    }
  });
  ctx.restore();
  return Lh;
}
/** Capsule pill: dark fill, gradient outline, optional status dot. o.left: cx is the left edge. */
function pill(ctx, cx, cy, text, size, o = {}) {
  const a = o.a ?? 1, s = o.s ?? 1;
  if (a <= 0.001) return 0;
  ctx.save(); ctx.font = B.font(size, BODY, 600);
  const dotW = o.dot ? size * 1.15 : 0, h = size * 2.05, w = ctx.measureText(text).width + size * 1.9 + dotW;
  ctx.translate(cx + (o.left ? (w * s) / 2 : 0), cy); ctx.scale(s, s); ctx.globalAlpha *= a;
  ctx.beginPath(); B.capsule(ctx, -w / 2, -h / 2, w, h); ctx.fillStyle = B.rgba("#080b2c", 0.88); ctx.fill();
  ctx.lineWidth = Math.max(1, size * 0.07);
  ctx.strokeStyle = B.linear(ctx, -w / 2, 0, w / 2, 0, [B.rgba(o.rimA || PAL.cyan, 0.9), B.rgba(o.rimB || PAL.violet, 0.7)]); ctx.stroke();
  if (o.dot) {
    const dx = -w / 2 + size * 1.05;
    lighter(ctx, () => B.glow(ctx, dx, 0, size * 0.9, o.dot, 0.6));
    ctx.beginPath(); B.circle(ctx, dx, 0, size * 0.26); ctx.fillStyle = o.dot; ctx.fill();
  }
  ctx.fillStyle = PAL.ice; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, dotW / 2, size * 0.05); ctx.restore();
  return w;
}
/** Huge gradient numeral; flash 0..1 adds an additive burst. */
function numeral(ctx, str, x, y, size, flash) {
  ctx.save(); ctx.font = B.font(size, HEAD, 800); ctx.letterSpacing = (-size * 0.03).toFixed(1) + "px";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  const w = ctx.measureText(str).width;
  ctx.fillStyle = B.linear(ctx, x - w / 2, y - size / 2, x + w / 2, y + size / 2, [[0, "#ffffff"], [0.45, "#a8e9ff"], [1, PAL.violet]]);
  ctx.fillText(str, x, y);
  if (flash > 0) {
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = flash * 0.55; ctx.fillText(str, x, y);
    B.glow(ctx, x, y, w * 0.75, PAL.cyan, 0.4 * flash);
  }
  ctx.restore();
}
/** Check badge: a glowing mint ring with a line tick. */
function badge(ctx, x, y, r, s) {
  if (s <= 0.001) return;
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  lighter(ctx, () => B.glow(ctx, 0, 0, r * 2.4, PAL.mint, 0.45));
  ctx.beginPath(); B.circle(ctx, 0, 0, r); ctx.fillStyle = "#07122a"; ctx.fill();
  ctx.lineWidth = Math.max(1, r * 0.1); ctx.strokeStyle = PAL.mint; ctx.stroke();
  ctx.lineWidth = r * 0.16; ctx.lineCap = ctx.lineJoin = "round";
  ctx.beginPath(); ctx.moveTo(-r * 0.42, 0); ctx.lineTo(-r * 0.1, r * 0.32); ctx.lineTo(r * 0.45, -r * 0.3); ctx.stroke();
  ctx.restore();
}

// ---- icons (the setting: replace these), strokes in -1..1
const ICON = {
  laptop: [rrPts(-0.8, -0.75, 1.6, 1.05, 0.12), [[-1.05, 0.6], [1.05, 0.6], [0.85, 0.85], [-0.85, 0.85], [-1.05, 0.6]], [[-0.2, 0.72], [0.2, 0.72]]],
  router: [rrPts(-1, 0.05, 2, 0.75, 0.2), [[-0.6, 0.05], [-0.85, -0.85]], [[0.6, 0.05], [0.85, -0.85]], B.arcPts(0, 0.05, 0.42, -2.4, -0.74, 12), [[-0.55, 0.42], [-0.45, 0.42]], [[-0.15, 0.42], [-0.05, 0.42]]],
  server: [rrPts(-0.8, -0.95, 1.6, 0.55, 0.12), rrPts(-0.8, -0.25, 1.6, 0.55, 0.12), rrPts(-0.8, 0.45, 1.6, 0.55, 0.12), [[-0.5, -0.67], [-0.45, -0.67]], [[-0.5, 0.03], [-0.45, 0.03]], [[-0.5, 0.73], [-0.45, 0.73]], [[0.05, -0.67], [0.5, -0.67]], [[0.05, 0.03], [0.5, 0.03]]],
  split: [rrPts(-0.95, -0.95, 0.8, 0.8, 0.12), rrPts(0.15, -0.95, 0.8, 0.8, 0.12), rrPts(-0.95, 0.15, 0.8, 0.8, 0.12), rrPts(0.15, 0.15, 0.8, 0.8, 0.12)],
  hop: [[[-0.9, 0.7], [-0.3, 0.1], [0.3, 0.5], [0.9, -0.5]], B.arcPts(-0.9, 0.7, 0.16, 0, B.TAU, 12), B.arcPts(-0.3, 0.1, 0.16, 0, B.TAU, 12), B.arcPts(0.3, 0.5, 0.16, 0, B.TAU, 12), [[0.5, -0.55], [0.9, -0.5], [0.85, -0.1]]],
  rebuild: [rrPts(-0.85, 0.35, 1.7, 0.55, 0.1), rrPts(-0.6, -0.25, 1.2, 0.5, 0.1), rrPts(-0.35, -0.85, 0.7, 0.5, 0.1)],
};

// ---- layout by aspect and the camera
function layout(W, H) {
  const F = B.frame(W, H), u = F.u, P = F.portrait, span = W * 1.5; // span: distance between regions of the one board
  return {
    F, u, P, S: F.safe, span, horizon: P ? H * 0.81 : H * 0.69, head: P ? 6.4 * u : 6.6 * u,
    label: P ? 4.3 * u : 4.0 * u, // every label, pill and eyebrow at this size or larger
    tile: P ? 15 * u : 13 * u,
    rx: [W / 2, W / 2 + span, W / 2 + 2 * span, W / 2 + 3 * span], // region centres: diagram, number, steps, close
    cy: P ? H * 0.5 : H * 0.53,
  };
}
const hubPos = (L, W, H) => (L.P ? [L.rx[1], H * 0.79] : [L.rx[1] + W * 0.33, L.cy]);
function camAt(t, L, W, H) {
  const [r0, r1, r2, r3] = L.rx;
  let x = r0, y = H / 2, zoom = 1.0 + 0.035 * B.span(t, 0, 4.0, "inOutSine");
  const pan1 = B.span(t, 3.8, 4.35, "inOutCubic");
  x = B.lerp(x, r1, pan1);
  if (t >= 3.8) zoom = B.lerp(zoom, 1 + 0.05 * B.span(t, 4.2, 5.5, "inOutSine"), pan1);
  const hubP = hubPos(L, W, H), dive = B.span(t, 5.5, 6.0, "inExpo");
  if (t < 6.0) {
    x = B.lerp(x, hubP[0], B.span(t, 5.4, 5.85, "inOutCubic"));
    y = B.lerp(y, hubP[1], B.span(t, 5.4, 5.85, "inOutCubic"));
    zoom *= 1 + 9 * dive;
    return { x, y, zoom, dive };
  }
  const arrive = B.prog(t, 6.0, 0.7, "outCubic"), pan3 = B.span(t, 10.05, 10.6, "inOutCubic");
  zoom = B.lerp(1.35, 1.0, arrive) + 0.05 * B.span(t, 6.6, 10.0, "inOutSine");
  x = B.lerp(r2, r3, pan3);
  zoom = B.lerp(zoom, 1.0 + 0.04 * B.span(t, 10.5, 12, "inOutSine"), pan3);
  return { x, y, zoom, dive: 0, arrive: 1 - arrive };
}

// ---- backdrop: void, clouds, lattice, floor grid, specks
function backdrop(ctx, W, H, t, L, cam) {
  const u = L.u, px = (cam.x - W / 2) * 0.12, hz = L.horizon, D = Math.hypot(W, H); // the backdrop moves much slower
  ctx.drawImage(B.layer("neon-void", W, H, (g, w, h) => { g.fillStyle = B.linear(g, 0, 0, w * 0.8, h, [PAL.void, "#0d0f3a", PAL.indigo]); g.fillRect(0, 0, w, h); }), 0, 0);
  // huge, very soft colour clouds that wander and breathe
  [[PAL.blue, 0.2, 0.25, 0.5, 0.085], [PAL.violet, 0.8, 0.35, 0.45, 0.09], [PAL.cyan, 0.3, 0.72, 0.35, 0.045], [PAL.violet, 0.6, 0.92, 0.5, 0.07], [PAL.pink, 0.95, 0.08, 0.3, 0.04]].forEach(([c, cx, cy, r, a], i) => {
    const wx = cx * W + B.noise1(t * 0.12 + i * 3, 11) * W * 0.12 - px * (0.5 + i * 0.1), wy = cy * H + B.noise1(t * 0.1 + i * 7, 17) * H * 0.06;
    B.glow(ctx, wx, wy, D * r * (1 + 0.12 * B.wave(t, 6 + i, i * 0.2)), c, a, { add: true });
  });
  // upper lattice of tiny dots, fading out toward the top
  const gap = 4.2 * u, lat = B.layer("neon-lattice", W + gap, hz + gap, (g, w, h) => {
    for (let y = gap / 2; y < h; y += gap)
      for (let x = gap / 2; x < w; x += gap) { g.fillStyle = B.rgba("#9fb4ff", 0.05 + 0.13 * Math.pow(y / h, 1.5)); g.fillRect(x - 0.6, y - 0.6, 1.4, 1.4); }
  });
  ctx.drawImage(lat, -(((px * 0.6) % gap) + gap) % gap, 0);
  // floor grid in perspective: fan lines from a vanishing point, cross lines scrolling toward the viewer
  const vx = W / 2, depth = H - hz, fanGap = W * (L.P ? 0.16 : 0.09), off = ((px * 1.4) % fanGap + fanGap) % fanGap, scroll = B.fract(t * 0.55);
  ctx.save(); ctx.beginPath(); ctx.rect(0, hz, W, H - hz); ctx.clip(); ctx.lineWidth = Math.max(1, 0.12 * u);
  for (let i = -18; i <= 18; i++) {
    const bx = vx + i * fanGap - off;
    ctx.strokeStyle = B.linear(ctx, 0, hz, 0, H, [[0, B.rgba(PAL.violet, 0)], [0.35, B.rgba(PAL.violet, 0.18)], [1, B.rgba(PAL.cyan, 0.32)]]);
    ctx.beginPath(); ctx.moveTo(vx + (bx - vx) * 0.02, hz); ctx.lineTo(vx + (bx - vx) * 1.6, H + depth * 0.6); ctx.stroke();
  }
  for (let i = 0; i < 16; i++) {
    const y = hz + depth / (0.6 + (i + 1 - scroll) * 0.55), k = (y - hz) / depth;
    if (y < hz || y > H + 2) continue;
    ctx.strokeStyle = B.rgba(k > 0.5 ? PAL.cyan : PAL.violet, 0.04 + 0.26 * Math.pow(k, 1.2));
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
  ctx.restore();
  lighter(ctx, () => { // thin bright haze line on the horizon
    ctx.fillStyle = B.linear(ctx, 0, hz - 3 * u, 0, hz + 3 * u, [[0, B.rgba(PAL.violet, 0)], [0.5, B.rgba(PAL.blue, 0.22)], [1, B.rgba(PAL.violet, 0)]]);
    ctx.fillRect(0, hz - 3 * u, W, 6 * u);
    ctx.fillStyle = B.linear(ctx, 0, 0, W, 0, [B.rgba(PAL.cyan, 0), B.rgba("#bdf6ff", 0.75), B.rgba(PAL.cyan, 0)]);
    ctx.fillRect(0, hz - Math.max(1, 0.1 * u), W, Math.max(1.5, 0.2 * u));
  });
  const r = B.rng("neon-specks"); // drifting, twinkling specks
  lighter(ctx, () => {
    for (let i = 0; i < 46; i++) {
      const x = B.fract(r() - (px * (0.3 + r() * 0.4)) / W + t * 0.004 * (r() - 0.5)) * W, y = r() * hz * 0.95 + B.bob(t, u * 0.6, r.range(5, 9), r());
      const tw = 0.35 + 0.65 * Math.pow(0.5 + 0.5 * Math.sin(B.TAU * (t / r.range(1.4, 3.6) + r())), 2), big = i % 7 === 0;
      if (big) B.glow(ctx, x, y, 2.4 * u, PAL.cyan, 0.3 * tw);
      ctx.fillStyle = B.rgba("#dfe8ff", 0.55 * tw); ctx.fillRect(x - 0.6, y - 0.6, big ? 2.2 : 1.4, big ? 2.2 : 1.4);
    }
  });
}

// ---- regions of the board
/** Region 0: one packet's trip, device -> router -> server, in a glass card. */
function regionDiagram(ctx, t, L) {
  const u = L.u, P = L.P, x0 = L.rx[0], cy = L.cy;
  if (t < BEATS[1] - 0.2 || t > 4.6) return;
  const cw = L.F.W * (P ? 0.86 : 0.8), ch = L.F.H * (P ? 0.52 : 0.5), e = enter(t, 1.8, 0.55);
  glassCard(ctx, x0, cy, cw, ch, u, { s: e.s, alpha: e.a });
  if (e.a <= 0) return;
  eyebrow(ctx, "ONE PACKET'S TRIP", P ? x0 : x0 - cw / 2 + 3 * u, cy - ch / 2 + (P ? 5 : 4.5) * u, L.label, { align: P ? undefined : "left", alpha: B.prog(t, 2.0, 0.4) });
  const nodes = P ? [-0.29, 0, 0.29].map((k) => [x0 - cw * 0.2, cy + ch * k]) : [-0.33, 0, 0.33].map((k) => [x0 + cw * k, cy - ch * 0.04]);
  const icons = [ICON.laptop, ICON.router, ICON.server], names = ["Your device", "Router", "Server"], ts = L.tile * (P ? 0.78 : 0.95);
  const wires = [0, 1].map((i) => {
    const [ax, ay] = nodes[i], [bx, by] = nodes[i + 1];
    return P ? B.cubic(ax, ay + ts * 0.62, ax + ts * 0.7, ay + ts * 1.1, bx + ts * 0.7, by - ts * 1.1, bx, by - ts * 0.62) : B.cubic(ax + ts * 0.62, ay, ax + ts * 1.1, ay - ts * 0.55, bx - ts * 1.1, by - ts * 0.55, bx - ts * 0.62, by);
  });
  wires.forEach((w, i) => wire(ctx, w, B.prog(t, 2.45 + i * 0.35, 0.45, "inOutCubic"), u, { head: true, color: PAL.cyan }));
  const per = 1.6, t0 = 3.0, arrival = (i) => t0 + Math.floor((t - t0 - 0.8 * i) / per) * per + 0.8 * i;
  if (t > t0) {
    const c = (t - t0) % per;
    spark(ctx, wires[c < 0.8 ? 0 : 1], B.ease.inOutSine((c % 0.8) / 0.8), u, PAL.cyan);
    for (let i = 1; i < 3; i++) {
      const arr = arrival(i);
      if (arr <= t && arr > t0) ring(ctx, nodes[i][0], nodes[i][1], ts * 0.5, ts * 1.05, (t - arr) / 0.55, PAL.cyan, u);
    }
  }
  nodes.forEach(([nx, ny], i) => {
    const ee = enter(t, 2.0 + i * 0.25, 0.45), pe = enter(t, 2.5 + i * 0.25, 0.4), arr = arrival(i);
    const lit = t > t0 && i > 0 && arr <= t && arr > t0 ? Math.max(0, 1 - (t - arr) / 0.4) : 0;
    iconTile(ctx, nx, ny, ts, icons[i], u, { s: ee.s, a: ee.a, p: B.prog(t, 2.15 + i * 0.25, 0.6, "inOutSine"), lit });
    const po = { s: pe.s, a: pe.a, dot: i === 1 ? PAL.mint : null, left: P };
    if (P) pill(ctx, nx + ts * 0.62 + 3 * u, ny, names[i], L.label, po);
    else pill(ctx, nx, ny + ts * 0.85, names[i], L.label, po);
  });
  const ce = enter(t, 3.1, 0.45);
  pill(ctx, x0, cy + ch * (P ? 0.43 : 0.36), "Each spark is one packet", L.label, { s: ce.s, a: ce.a, dot: PAL.cyan });
}

/** Region 1: the key number, and the hub the camera dives through. */
function regionNumber(ctx, t, L, W, H) {
  const u = L.u, P = L.P, cy = L.cy;
  if (t < 3.7 || t > 6.05) return;
  const cw = P ? W * 0.84 : W * 0.5, ch = P ? H * 0.46 : H * 0.56, ccy = cy, ccx = P ? L.rx[1] : L.rx[1] - W * 0.06;
  const e = enter(t, 3.95, 0.5), pe = enter(t, 4.4, 0.4), nsz = P ? 24 * u : 17 * u;
  glassCard(ctx, ccx, ccy, cw, ch, u, { s: e.s, alpha: e.a, glowA: PAL.blue });
  eyebrow(ctx, "TYPICAL MAX PACKET", ccx, ccy - ch / 2 + 5 * u, L.label, { alpha: B.prog(t, 4.15, 0.4) });
  const val = B.counter(B.prog(t, 4.25, 1.15), 1500, { ease: "outExpo" }), flash = Math.max(0, 1 - Math.abs(t - 5.45) / 0.3) * (t > 5.3 ? 1 : 0);
  ctx.save(); ctx.globalAlpha *= e.a; numeral(ctx, val, ccx, ccy + u, nsz * (1 + 0.04 * flash), flash); ctx.restore();
  pill(ctx, ccx, ccy + nsz * 0.62 + L.label * 1.4, "bytes per packet", L.label, { s: pe.s, a: pe.a, dot: PAL.cyan });
  const [hx, hy] = hubPos(L, W, H);
  const wpts = P ? B.cubic(ccx, ccy + ch / 2, ccx, ccy + ch / 2 + 6 * u, hx, hy - 10 * u, hx, hy - 2.5 * u) : B.cubic(ccx + cw / 2, ccy, ccx + cw / 2 + 6 * u, ccy - 6 * u, hx - 8 * u, hy, hx - 2.5 * u, hy);
  wire(ctx, wpts, B.prog(t, 4.5, 0.5, "inOutCubic"), u);
  if (t > 5.0) spark(ctx, wpts, B.ease.inOutSine(B.fract((t - 5.0) / 0.7)), u, PAL.violet);
  hub(ctx, hx, hy, 1.4 * u, t, u, enter(t, 4.6, 0.5).a);
}

/** Region 2: three steps as chips joined by wires; a lost packet and a resend. */
function regionSteps(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.rx[2], cy = L.cy;
  if (t < 5.9 || t > 10.7) return;
  const ts = L.tile * (P ? 0.92 : 0.95), icons = [ICON.split, ICON.hop, ICON.rebuild], names = ["Split into packets", "Router to router", "Rebuild in order"];
  const chips = P ? [-0.185, 0.01, 0.205].map((k) => [x0 - W * 0.27, cy + H * k]) : [-0.32, 0, 0.32].map((k) => [x0 + W * k, cy - H * 0.04]);
  const wires = [0, 1].map((i) => {
    const [ax, ay] = chips[i], [bx, by] = chips[i + 1];
    return P ? B.cubic(ax, ay + ts * 0.6, ax + ts * 0.35, ay + ts * 1.2, bx + ts * 0.35, by - ts * 1.2, bx, by - ts * 0.6) : B.cubic(ax + ts * 0.6, ay, ax + ts * 1.2, ay + ts * 0.5, bx - ts * 1.2, by + ts * 0.5, bx - ts * 0.6, by);
  });
  wires.forEach((w, i) => wire(ctx, w, B.prog(t - 6.0, 0.5 + i * 0.25, 0.45, "inOutCubic"), u, { head: true, color: PAL.cyan }));
  [7.0, 7.8].forEach((at, i) => spark(ctx, wires[i], B.ease.inOutSine(B.prog(t, at, 0.65)), u, PAL.cyan));
  const arrive = [6.45, 7.65, 8.45];
  // wrong: a coral spark runs BACKWARD (a packet lost); a coral return wire: resend it; a mint spark
  if (t > 8.6 && t < 9.25) spark(ctx, wires[1], 1 - B.prog(t, 8.6, 0.6, "inOutSine"), u, PAL.coral, { dir: -1 });
  const [c2x, c2y] = chips[1], [c3x, c3y] = chips[2];
  const loop = P ? B.cubic(c3x - ts * 0.6, c3y, c3x - ts * 1.4, c3y - ts * 0.2, c2x - ts * 1.4, c2y + ts * 0.2, c2x - ts * 0.6, c2y) : B.cubic(c3x, c3y - ts * 0.62, c3x - ts * 0.2, c3y - ts * 2.0, c2x + ts * 0.2, c2y - ts * 2.0, c2x, c2y - ts * 0.62);
  wire(ctx, loop, B.prog(t, 9.15, 0.45, "inOutCubic"), u, { head: true, color: PAL.coral });
  if (t > 9.55 && t < 10.2) spark(ctx, wires[1], B.prog(t, 9.55, 0.6, "inOutSine"), u, PAL.mint);
  chips.forEach(([cx, cyy], i) => {
    const ee = enter(t, 6.15 + i * 0.25, 0.45), pe = enter(t, 6.35 + i * 0.25, 0.4), label = i + 1 + "  " + names[i];
    let lit = Math.max(0, 1 - Math.abs(t - arrive[i] - 0.15) / 0.5);
    if (t > arrive[i]) lit = Math.max(lit, 0.35);
    iconTile(ctx, cx, cyy, ts, icons[i], u, { s: ee.s * (1 + 0.06 * Math.max(0, 1 - Math.abs(t - arrive[i]) / 0.2)), a: ee.a, p: B.prog(t, 6.3 + i * 0.25, 0.6), lit, halo: i === 2 && t > 8.6 && t < 9.6 ? PAL.coral : PAL.blue });
    if (t > arrive[i]) ring(ctx, cx, cyy, ts * 0.5, ts * 1.1, (t - arrive[i]) / 0.6, PAL.cyan, u);
    if (P) pill(ctx, cx + ts * 0.65 + 3 * u, cyy, label, L.label, { s: pe.s, a: pe.a, left: true });
    else pill(ctx, cx, cyy + ts * 0.9, label, L.label, { s: pe.s, a: pe.a });
  });
  const tag = P ? [c3x + ts * 0.65 + 3 * u, c3y + ts * 0.8] : [c3x, c3y + ts * 1.65], mid = B.pointAt(loop, 0.5), re = enter(t, 9.3, 0.4), de = enter(t, 10.15, 0.35);
  pill(ctx, tag[0], tag[1], "Packet lost", L.label, { a: B.prog(t, 8.75, 0.35) * (1 - B.prog(t, 9.55, 0.3)), s: 0.9 + 0.1 * B.ease.outBack(B.prog(t, 8.75, 0.35)), dot: PAL.coral, rimA: PAL.coral, rimB: PAL.violet, left: P });
  if (t > 8.65 && t < 9.6) ring(ctx, c3x, c3y, ts * 0.5, ts * 1.3, B.prog(t, 8.65, 0.6), PAL.coral, u);
  pill(ctx, P ? c2x + ts * 0.65 + 3 * u : mid[0], P ? (c2y + c3y) / 2 : mid[1] - L.label * 1.6, "Resend lost packet", L.label, { s: re.s, a: re.a, dot: PAL.coral, rimA: PAL.coral, left: P });
  badge(ctx, c3x + ts * 0.5, c3y - ts * 0.5, 2.6 * u, B.pop(t, 10.1, 0.4, 2.2));
  pill(ctx, tag[0], tag[1], "Delivered", L.label, { s: de.s, a: de.a, dot: PAL.mint, rimA: PAL.mint, left: P });
}

/** Region 3: the takeaway headline, an underline sweeping in. */
function regionClose(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.rx[3], cy = L.cy;
  if (t < 9.9) return;
  const r = B.rng("close-net"), pts = []; // a faint network round the takeaway
  for (let i = 0; i < 7; i++) pts.push([x0 + Math.cos((i / 7) * B.TAU + 0.4) * W * 0.36, cy + Math.sin((i / 7) * B.TAU + 0.4) * H * (P ? 0.28 : 0.32)]);
  for (let i = 0; i < 7; i++) {
    const a = pts[i], b = pts[(i + 1) % 7], w = B.quad(a[0], a[1], x0 + (a[0] + b[0] - 2 * x0) * 0.62, cy + (a[1] + b[1] - 2 * cy) * 0.62, b[0], b[1]);
    wire(ctx, w, B.prog(t, 10.4 + i * 0.06, 0.5), u, { alpha: 0.6 });
    if (t > 10.9) spark(ctx, w, B.fract((t - 10.9) / 1.1 + r()), u, i % 3 ? PAL.cyan : PAL.violet, { tail: 0.1 });
  }
  pts.forEach(([hx, hy], i) => hub(ctx, hx, hy, 0.9 * u, t, u, B.prog(t, 10.4 + i * 0.05, 0.4) * 0.8));
  const txt = P ? "Small packets,\nmany paths,\none message" : "Small packets, many paths,\none message", mw = W * (P ? 0.84 : 0.8);
  const pre = headLayout(ctx, txt, L.head * 1.05, mw);
  eyebrow(ctx, "THE TAKEAWAY", x0, cy - (pre.lh * pre.lines.length) / 2 - 4 * u, L.label, { alpha: B.prog(t, 10.45, 0.4) });
  const Lh = headline(ctx, txt, x0, cy, L.head * 1.05, mw, t, { at: 10.5, gap: 0.1 });
  const k = B.prog(t, 11.0, 0.55, "inOutCubic");
  if (k > 0) {
    const y = cy + (Lh.lh * Lh.lines.length) / 2 + 2.2 * u, w = Lh.width * 0.7, xs = x0 - w / 2;
    lighter(ctx, () => {
      ctx.fillStyle = B.linear(ctx, xs, 0, xs + w, 0, [PAL.cyan, PAL.blue, PAL.violet]); ctx.fillRect(xs, y - 0.25 * u, w * k, 0.5 * u);
      B.glow(ctx, xs + w * k, y, 3 * u, "#ffffff", 0.7);
    });
  }
}

/** The title builds word by word, then shrinks and flies to the top-left corner as a header. */
function title(ctx, t, L, W, H) {
  const u = L.u, P = L.P, S = L.S;
  if (t > 10.2) return;
  const fly = B.span(t, 1.45, 2.05, "inOutCubic"), size = (P ? 9.5 : 8.5) * u, cy = H * (P ? 0.38 : 0.5);
  const text = P ? "How a message\ncrosses the\ninternet" : "How a message crosses\nthe internet";
  const Lh = headLayout(ctx, text, size, W * (P ? 0.86 : 0.8)), blockH = Lh.lh * Lh.lines.length;
  const sc = B.lerp(1, (4.1 * u) / size, fly); // the corner header still reads at label size
  const tx = B.lerp(W / 2, S.x + (Lh.width * sc) / 2, fly), ty = B.lerp(cy, S.y + (blockH * sc) / 2 + (P ? 1.5 : 0.5) * u, fly);
  if (fly < 1) {
    const hp = enter(t, 0.15, 0.6), hy = cy + blockH * 0.5 + 7 * u, a = (1 - fly) * hp.a;
    hub(ctx, W / 2, hy, 1.3 * u, t, u, a);
    // a small network fans out under the title
    [[0.14 * W, hy + (P ? 22 : 12) * u], [W / 2, hy + (P ? 34 : 18) * u], [0.86 * W, hy + (P ? 22 : 12) * u]].forEach(([ex, ey], i) => {
      const w = B.cubic(W / 2, hy, W / 2 + (i - 1) * 12 * u, hy + (i === 1 ? 10 : 0) * u, ex, ey - 10 * u, ex, ey);
      wire(ctx, w, B.prog(t, 0.25, 0.5, "inOutCubic"), u, { alpha: a });
      if (t > 0.75) spark(ctx, w, B.fract((t - 0.75) / 1.1 + i * 0.33), u, i === 2 ? PAL.violet : PAL.cyan, { tail: 0.12 });
      hub(ctx, ex, ey, 1.0 * u, t, u, a * B.prog(t, 0.55, 0.35));
    });
    eyebrow(ctx, "NETWORKS 101", W / 2, cy - blockH * 0.5 - 5 * u, L.label, { alpha: B.prog(t, 0.1, 0.4) * (1 - fly) });
  }
  ctx.save(); ctx.translate(tx, ty); ctx.scale(sc, sc);
  headline(ctx, text, 0, 0, size, W * (P ? 0.86 : 0.8), t, { at: 0.2, gap: 0.11, alpha: 1 - B.span(t, 9.9, 10.2), leftK: fly });
  ctx.restore();
}

// ---- finishing: bloom, dive streaks
/** Bloom: a quarter-size copy with darks crushed, blurred small and wide, added back. */
function bloom(ctx, W, H, u) {
  const q = 4, w = Math.ceil(W / q), h = Math.ceil(H / q), src = B.scratch("neon-bloom-src", w, h);
  src.filter = "brightness(0.8) contrast(3.4)"; src.drawImage(ctx.canvas, 0, 0, w, h); src.filter = "none";
  [[0.9 * u / q, 0.6], [3.8 * u / q, 0.55]].forEach(([r, a], i) => {
    const g = B.scratch("neon-bloom-" + i, w, h);
    g.filter = `blur(${r.toFixed(2)}px)`; g.drawImage(src.canvas, 0, 0);
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = a;
    ctx.imageSmoothingEnabled = true; ctx.drawImage(g.canvas, 0, 0, W, H); ctx.restore();
  });
}
function streaks(ctx, W, H, x, y, k, u) {
  if (k <= 0) return;
  const r = B.rng("streaks"), D = Math.hypot(W, H);
  lighter(ctx, () => {
    ctx.lineCap = "round";
    for (let i = 0; i < 70; i++) {
      const a = r() * B.TAU, r0 = D * (0.02 + r() * 0.25) * (1 + 2 * k), len = D * (0.08 + r() * 0.3) * k;
      ctx.strokeStyle = B.rgba(r() < 0.5 ? PAL.cyan : "#ffffff", 0.25 + 0.5 * k); ctx.lineWidth = Math.max(1, r.range(0.1, 0.45) * u);
      ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * r0, y + Math.sin(a) * r0); ctx.lineTo(x + Math.cos(a) * (r0 + len), y + Math.sin(a) * (r0 + len)); ctx.stroke();
    }
  });
}

function draw(ctx, W, H, t) {
  const L = layout(W, H), u = L.u, cam = camAt(t, L, W, H);
  backdrop(ctx, W, H, t, L, cam);
  B.camera(ctx, W, H, cam, () => { regionDiagram(ctx, t, L); regionNumber(ctx, t, L, W, H); regionSteps(ctx, t, L, W, H); regionClose(ctx, t, L, W, H); });
  title(ctx, t, L, W, H);
  streaks(ctx, W, H, W / 2, H / 2, t < 6 ? B.span(t, 5.45, 6.0, "inQuad") : 1 - B.span(t, 6.0, 6.45), u);
  bloom(ctx, W, H, u);
  B.vignette(ctx, W, H, { amount: 0.55, inner: 0.5, color: "#02030c" });
  B.cover(ctx, W, H, "#ffffff", t < 6 ? B.span(t, 5.8, 6.0) * 0.95 : 0.95 * (1 - B.span(t, 6.0, 6.3)));
}

// ---- sound: dull air, glassy blips, digital ticks, spark glides, sub + shimmer, pad -> major
SOUND.define("neon-air", (v, o) => {
  const d = o.dur ?? 0.6;
  v.noise({ filter: "lowpass", q: 0.7, f: 260, fpath: [[d * 0.5, 900], [d, 300]], a: d * 0.5, len: d * 0.5, peak: 0.32 });
}, { verb: 0.3 });
SOUND.define("neon-blip", (v, o) => {
  const f = SOUND.note(o.note ?? "E6");
  v.tone({ f, a: 0.002, len: 0.16, peak: 0.13 }); v.tone({ f: f * 2.76, a: 0.001, len: 0.07, peak: 0.03 });
}, { verb: 0.45 });
SOUND.define("neon-tick", (v) => v.tone({ type: "square", f: 3200, a: 0.0005, len: 0.012, peak: 0.035, shape: "lin" }), { verb: 0.1 });
SOUND.define("neon-glide", (v, o) => {
  const d = o.dur ?? 0.6;
  v.tone({ f: 420, f2: 1260, glide: d, a: d * 0.3, hold: d * 0.4, len: d * 0.3, peak: 0.05 });
}, { verb: 0.4 });
SOUND.define("neon-sub", (v) => {
  v.tone({ f: 82, f2: 38, glide: 0.5, a: 0.004, len: 0.9, peak: 0.6 });
  v.noise({ filter: "highpass", f: 7000, a: 0.01, len: 0.9, peak: 0.05 }); v.sub("sparkle", 0.02, { note: "B6" });
}, { verb: 0.5 });

function score(k) {
  k.bed("pad", 0, 10.6, { notes: ["D2", "A2", "D3", "F3"], gain: 0.6, bright: 520 });
  k.at(0.1, "neon-air", { dur: 0.9, gain: 0.6 }).at(1.45, "neon-air", { dur: 0.6, gain: 0.7 });
  ["D6", "F6", "A6", "C7", "D7"].forEach((note, i) => k.at(0.2 + i * 0.11, "neon-blip", { note, gain: 0.55 }));
  k.at(1.8, "neon-air", { dur: 0.5, gain: 0.5 });
  ["A5", "D6", "F6"].forEach((note, i) => k.at(2.0 + i * 0.25, "neon-blip", { note, pan: (i - 1) * 0.4 }));
  [3.0, 3.8, 4.6].forEach((at) => k.at(at, "neon-glide", { dur: 0.8, gain: 0.8 }));
  // ticks spaced like the outExpo count (p = -log2(1 - k) / 10); the sub on the flash
  k.at(3.8, "neon-air", { dur: 0.6, gain: 0.8 });
  for (let i = 1; i < 14; i++) k.at(4.25 + 1.15 * (-Math.log2(1 - i / 14) / 10), "neon-tick", { gain: 0.9, pitch: i * 0.4 });
  k.at(5.42, "neon-sub", { gain: 0.9 }).at(5.45, "riser", { dur: 0.55, gain: 0.45 }).at(5.95, "neon-air", { dur: 0.7, gain: 1 });
  ["D6", "F6", "A6"].forEach((note, i) => k.at(6.15 + i * 0.25, "neon-blip", { note }));
  k.at(7.0, "neon-glide", { dur: 0.65 }).at(7.65, "neon-blip", { note: "C7", gain: 0.7 });
  k.at(7.8, "neon-glide", { dur: 0.65, pitch: 2 }).at(8.45, "neon-blip", { note: "D7", gain: 0.7 });
  k.at(8.6, "fall", { dur: 0.6, gain: 0.25 }).at(8.75, "neon-blip", { note: "C#6", gain: 0.6 }).at(9.15, "neon-air", { dur: 0.5, gain: 0.5 });
  k.at(9.55, "neon-glide", { dur: 0.6, pitch: 4 }).at(10.1, "chime", { note: "A6", gain: 0.35 });
  // the takeaway resolves the pad to a bright major chord
  k.at(10.05, "neon-air", { dur: 0.6, gain: 0.8 }).at(10.5, "chord", { notes: ["D4", "F#4", "A4", "D5", "F#5"], dur: 2.2, gain: 0.7 });
  k.bed("pad", 10.4, DUR, { notes: ["D3", "F#3", "A3", "D4"], gain: 0.5, bright: 900, fade: 0.4 });
  k.at(11.0, "neon-air", { dur: 0.6, gain: 0.4 }).at(11.05, "sparkle", { note: "D7", gain: 0.25 });
}

Player.register({
  id: "neon-circuit", name: "Neon Circuit", duration: DUR,
  fonts: {
    href: "https://fonts.googleapis.com/css2?family=Sora:wght@700;800&family=Manrope:wght@600;800&display=swap",
    faces: ['700 20px "Sora"', '800 20px "Sora"', '600 20px "Manrope"', '800 20px "Manrope"'],
  },
  beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three steps", "Lost and resent", "Takeaway"],
  stills: [1.2, 3.6, 5.5, 8.1, 9.9, 11.6],
  draw, score,
});
})();
