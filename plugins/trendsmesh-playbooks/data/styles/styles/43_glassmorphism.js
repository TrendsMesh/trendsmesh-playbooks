/* 43 Glassmorphism UI - reference animation.
 * Topic (setting, replace it): "How does tap-to-pay work?" - a short-range radio link (NFC, about 4 cm), a one-time
 * code instead of the card number, the bank's yes.
 * Rendering (keep it): a modern app interface. A deep indigo backdrop with big glossy gradient orbs drifting slowly
 * (lit from the upper left, crisp rims, a soft halo). Frosted glass cards that really blur what lies behind them
 * (see frost); on top a faint dark tint, a white diagonal sheen, a thin light border brighter at the top-left and an
 * inner highlight on that corner; under it a soft large shadow. UI widgets carry the explaining:
 * a ring gauge, a line chart, a bar chart, toggles, a progress bar, notification toasts and a touch cursor that
 * presses and ripples. Type: Plus Jakarta Sans (headings, numbers) and Inter (labels).
 * Motion: springs (slide in, overshoot, settle), cards stacking with a small parallax nudge, a gentle tilt while
 * moving, the orb layer drifting at 0.4 depth; a light sheen sweeps across the glass at every beat change.
 */
(function () {
"use strict";
const B = window.Brush;

// ---------------- palette and type (from the card)
const PAL = { deep: "#0b0d2b", mid: "#1d1f5c", violet: "#7b61ff", cyan: "#3fd4ff", pink: "#ff5fa2", amber: "#ffb547", glass: "#ffffff", mint: "#3ee6a8" };
const HEAD = "Plus Jakarta Sans", BODY = "Inter";
const DUR = 12;
const BEATS = [0, 2.0, 4.2, 6.4, 8.6, 10.4];
const W8 = (a) => B.rgba(PAL.glass, a);
let MIN = 30; // smallest legible label for this frame (set in draw from the frame size)

// ---------------- the frosted backdrop copy
/** What makes the glass real: the frame as drawn so far, copied to 1/8 size through blur + saturate. Every glass card
 * drawn after this shows that copy (scaled back up, so the blur softens further), clipped to its own shape. */
let FROST = null;
function frost(ctx, W, H, key) {
  const sw = Math.ceil(W / 8), sh = Math.ceil(H / 8), g = B.scratch("glass-frost" + key, sw, sh);
  g.filter = "blur(2.6px) saturate(1.55)"; g.drawImage(ctx.canvas, 0, 0, sw, sh); g.filter = "none";
  FROST = g.canvas;
}

// ---------------- glass helpers (reuse these)
/**
 * One frosted glass card. b = { cx, cy, w, h }; o = { alpha, dx, dy, s (scale), tilt (-1..1), r (corner) };
 * content(ctx, x, y, w, h) draws in the card's own coordinates (centred, x = -w/2), clipped to the card.
 */
function glass(ctx, L, b, o, content) {
  const a = o.alpha ?? 1;
  if (a <= 0.004) return;
  const u = L.u, r = o.r ?? 3.4 * u;
  const x = -b.w / 2, y = -b.h / 2, w = b.w, h = b.h;
  ctx.save(); ctx.globalAlpha = a; ctx.translate(b.cx + (o.dx || 0), b.cy + (o.dy || 0));
  const s = o.s ?? 1;
  ctx.scale(s, s);
  if (o.tilt) ctx.transform(1, o.tilt * 0.035, -o.tilt * 0.05, 1, 0, 0); // a gentle tilt, as if seen a little turned
  const path = () => {
    ctx.beginPath(); B.roundRect(ctx, x, y, w, h, r);
  };
  // soft, large, low shadow (hidden inside by the frosted fill, so only the halo shows)
  B.withShadow(ctx, { color: B.rgba("#03041a", 0.55), blur: 8 * u, y: 3.6 * u }, () => {
    path(); ctx.fillStyle = PAL.deep; ctx.fill();
  }); ctx.save(); path(); ctx.clip();
  if (FROST) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0); // the copy is in frame space: the backdrop stays put as the card moves
    ctx.imageSmoothingQuality = "high"; ctx.drawImage(FROST, 0, 0, L.W, L.H); ctx.restore();
  }
  ctx.fillStyle = B.rgba(PAL.deep, 0.26); // a faint dark tint keeps white type legible over bright orbs
  ctx.fillRect(x, y, w, h); ctx.fillStyle = B.linear(ctx, x, y, x + w, y + h, [[0, W8(0.24)], [0.45, W8(0.08)], [1, W8(0.13)]]);
  ctx.fillRect(x, y, w, h); ctx.fillStyle = B.radial(ctx, x + w * 0.12, y, 0, Math.max(w, h) * 0.7, [[0, W8(0.12)], [1, W8(0)]]);
  ctx.fillRect(x, y, w, h); if (content) content(ctx, x, y, w, h); ctx.restore();
  // thin light border, brightest at the top-left, plus an inner highlight hugging the top-left corner
  path(); ctx.lineWidth = Math.max(1.2, 0.2 * u);
  ctx.strokeStyle = B.linear(ctx, x, y, x + w, y + h, [[0, W8(0.85)], [0.3, W8(0.25)], [0.7, W8(0.08)], [1, W8(0.32)]]); ctx.stroke();
  ctx.beginPath(); B.roundRect(ctx, x + 0.45 * u, y + 0.45 * u, w - 0.9 * u, h - 0.9 * u, r - 0.45 * u);
  ctx.lineWidth = Math.max(1, 0.14 * u); ctx.strokeStyle = B.linear(ctx, x, y, x + w * 0.45, y + h * 0.45, [[0, W8(0.6)], [1, W8(0)]]);
  ctx.stroke(); ctx.restore();
}
/** Type: headlines in Plus Jakarta Sans 800, labels in Inter 600; white, a faint cool shadow underneath. */
function type(ctx, str, x, y, size, o, fam, wt) {
  return B.text(ctx, str, x, y, { size, minSize: Math.min(size, Math.max(size * 0.6, MIN)), family: fam, weight: o.weight ?? wt, color: o.color || W8(0.94),
    maxW: o.maxW, maxLines: o.maxLines ?? 2, lineH: 1.1, align: o.align, letterSpacing: o.spacing ?? 0, alpha: o.alpha,
    shadow: { y: size * 0.05, blur: size * 0.3, color: B.rgba("#05061f", 0.42) } });
}
const head = (ctx, str, x, y, size, o = {}) => type(ctx, str, x, y, size, { spacing: -0.015, color: PAL.glass, ...o }, HEAD, 800);
const label = (ctx, str, x, y, size, o = {}) => type(ctx, str, x, y, size, o, BODY, 600);
/** Brand-free accent gradient used on every active widget (cyan -> violet -> pink). */
function accent(ctx, x0, y0, x1, y1) {
  return B.linear(ctx, x0, y0, x1, y1, [PAL.cyan, PAL.violet, PAL.pink]);
}
/** Ring gauge: pale glass track, conic gradient fill with round caps and a glowing head dot. */
function ring(ctx, x, y, R, lw, p, u) {
  ctx.save(); ctx.lineCap = "round"; ctx.lineWidth = lw; ctx.strokeStyle = W8(0.12); ctx.beginPath(); ctx.arc(x, y, R, 0, B.TAU); ctx.stroke();
  if (p > 0.003) {
    const a0 = -Math.PI / 2, a1 = a0 + B.TAU * p;
    const g = ctx.createConicGradient(a0, x, y);
    g.addColorStop(0, PAL.cyan); g.addColorStop(0.5, PAL.violet); g.addColorStop(1, PAL.pink); ctx.strokeStyle = g; ctx.beginPath();
    ctx.arc(x, y, R, a0, a1); ctx.stroke();
    const hx = x + Math.cos(a1) * R, hy = y + Math.sin(a1) * R;
    B.glow(ctx, hx, hy, lw * 2.2, PAL.pink, 0.7, { add: true }); ctx.beginPath(); B.circle(ctx, hx, hy, lw * 0.32); ctx.fillStyle = PAL.glass; ctx.fill();
  }
  ctx.restore();
}
/** Phone-style toggle: a glass track that fills with the mint gradient, a white knob with a shadow. */
function toggle(ctx, x, y, h, on) {
  const w = h * 1.75, kr = h * 0.4, kx = B.lerp(x - w / 2 + h / 2, x + w / 2 - h / 2, on);
  ctx.save(); ctx.beginPath(); B.capsule(ctx, x - w / 2, y - h / 2, w, h); ctx.fillStyle = W8(0.14); ctx.fill(); ctx.strokeStyle = W8(0.35);
  ctx.lineWidth = Math.max(1, h * 0.04); ctx.stroke();
  if (on > 0.01) {
    ctx.globalAlpha *= B.clamp(on); ctx.fillStyle = B.linear(ctx, x - w / 2, y, x + w / 2, y, [PAL.mint, PAL.cyan]); ctx.beginPath();
    B.capsule(ctx, x - w / 2, y - h / 2, w, h); ctx.fill(); ctx.globalAlpha /= B.clamp(on);
  }
  B.withShadow(ctx, { color: B.rgba("#03041a", 0.45), blur: h * 0.3, y: h * 0.08 }, () => {
    ctx.beginPath(); B.circle(ctx, kx, y, kr); ctx.fillStyle = PAL.glass; ctx.fill();
  }); ctx.restore();
}
/** Capsule progress bar: glass track, accent fill, a soft glow at its head. */
function progress(ctx, x, y, w, h, p) {
  ctx.save(); ctx.beginPath(); B.capsule(ctx, x, y - h / 2, w, h); ctx.fillStyle = W8(0.13); ctx.fill();
  if (p > 0.005) {
    const fw = Math.max(h, w * p);
    ctx.beginPath(); B.capsule(ctx, x, y - h / 2, fw, h); ctx.fillStyle = accent(ctx, x, y, x + w, y); ctx.fill();
    B.glow(ctx, x + fw - h / 2, y, h * 2.4, PAL.pink, 0.5, { add: true });
  }
  ctx.restore();
}
/** Round icon disc with an accent or mint gradient and a white glyph: "check", "wave", or a numeral. */
function disc(ctx, x, y, r, glyph, col, u) {
  ctx.save(); ctx.beginPath(); B.circle(ctx, x, y, r);
  ctx.fillStyle = col === "mint" ? B.linear(ctx, x - r, y - r, x + r, y + r, [PAL.mint, "#21b98a"]) : accent(ctx, x - r, y - r, x + r, y + r); ctx.fill();
  ctx.beginPath(); // a glossy top lip
  ctx.ellipse(x, y - r * 0.45, r * 0.62, r * 0.3, 0, 0, B.TAU); ctx.fillStyle = W8(0.22); ctx.fill(); ctx.strokeStyle = PAL.glass;
  ctx.lineCap = ctx.lineJoin = "round"; ctx.lineWidth = r * 0.16;
  if (glyph === "check") {
    ctx.beginPath(); ctx.moveTo(x - r * 0.4, y + r * 0.02); ctx.lineTo(x - r * 0.1, y + r * 0.32); ctx.lineTo(x + r * 0.42, y - r * 0.3); ctx.stroke();
  } else if (glyph === "wave") wavesIcon(ctx, x - r * 0.35, y, r * 0.75, r * 0.12, 1);
  else head(ctx, glyph, x, y + r * 0.04, r * 1.05, { maxLines: 1 }); ctx.restore();
}
/** The generic contactless mark: a dot and three widening arcs opening to the right (no brand). */
function wavesIcon(ctx, x, y, s, lw, p) {
  ctx.save(); ctx.strokeStyle = PAL.glass; ctx.fillStyle = PAL.glass; ctx.lineWidth = lw; ctx.lineCap = "round"; ctx.beginPath();
  B.circle(ctx, x, y, lw * 0.75); ctx.fill();
  for (let i = 1; i <= 3; i++) {
    const k = B.clamp(p * 3 - (i - 1));
    if (k <= 0) continue; ctx.globalAlpha *= k; ctx.beginPath(); ctx.arc(x, y, (s * i) / 3, -0.75, 0.75); ctx.stroke(); ctx.globalAlpha /= k;
  }
  ctx.restore();
}
/** Touch cursor: a frosted finger dot that dips when it presses, and a ripple ring that spreads and fades. */
function touch(ctx, x, y, u, press, ripple, alpha) {
  if (alpha <= 0.01) return; ctx.save(); ctx.globalAlpha = alpha;
  if (ripple > 0 && ripple < 1) {
    for (let i = 0; i < 2; i++) {
      const q = B.clamp(ripple * 1.2 - i * 0.2);
      if (q <= 0) continue; ctx.beginPath(); B.circle(ctx, x, y, 3 * u + q * 9 * u); ctx.strokeStyle = W8(0.7 * (1 - q));
      ctx.lineWidth = 0.5 * u * (1 - q) + 1; ctx.stroke();
    }
  }
  const r = 3 * u * (1 - 0.16 * press);
  B.withShadow(ctx, { color: B.rgba("#03041a", 0.4), blur: 2.5 * u * (1 - press * 0.6), y: 1.2 * u * (1 - press * 0.7) }, () => {
    ctx.beginPath(); B.circle(ctx, x, y, r); ctx.fillStyle = W8(0.42 + 0.2 * press); ctx.fill();
  }); ctx.beginPath(); B.circle(ctx, x, y, r); ctx.strokeStyle = W8(0.9); ctx.lineWidth = 0.3 * u; ctx.stroke(); ctx.restore();
}
/** Envelope for a group: spring in from `a`, slide up and fade out ending at `b`. */
function group(t, a, b, inDur = 0.9) {
  const pin = B.prog(t, a, inDur), out = B.span(t, b - 0.32, b, "inCubic");
  return { show: t >= a && t < b, inP: B.spring(pin, 1.1, 5.5), lin: pin, out, alpha: Math.min(B.smooth(0, 0.35, pin), 1 - out) };
}
/** Card motion from an envelope: rise in from below with a tilt that dies out, lift away on the way out. */
function moveIn(g, u, from = [0, 16]) {
  const k = 1 - g.inP;
  return { alpha: g.alpha, dx: from[0] * u * k, dy: from[1] * u * k - 8 * u * g.out, s: 1 - 0.04 * g.out, tilt: (1 - g.lin) * 0.9 };
}

// ---------------- backdrop: deep gradient + drifting glossy orbs
const ORBS = [
  // [x, y (frame fractions), radius (u), colour, light tint, drift phase]
  [0.2, 0.22, 20, PAL.violet, "#c9bcff", 0.1],
  [0.86, 0.3, 15, PAL.pink, "#ffd0e4", 0.4],
  [0.72, 0.82, 26, PAL.cyan, "#d3f6ff", 0.7],
  [0.12, 0.78, 13, PAL.amber, "#ffe6bd", 0.25],
  [0.93, 0.6, 7, PAL.mint, "#d0fff0", 0.55],
];
function backdrop(ctx, W, H, t, L) {
  const c = B.layer("glass-backdrop", W, H, (g, w, h) => {
    g.fillStyle = B.linear(g, 0, 0, w * 0.6, h, [PAL.mid, "#14164a", PAL.deep]); g.fillRect(0, 0, w, h);
  }); ctx.drawImage(c, 0, 0);
  const u = L.u, P = L.P;
  // camera drift per beat (orbs at 0.4 depth: they move less than the cards)
  const bi = B.beat(t, BEATS, DUR);
  const pan = (bi.i + B.ease.inOutCubic(B.smooth(0.0, 0.35, bi.p))) * (P ? 2.2 : 3.2) * u;
  ORBS.forEach(([fx, fy, rr, col, tint, ph], i) => {
    const R = rr * u * (P ? 1.35 : 1);
    const x = fx * W + B.noise1(t * 0.12 + ph * 10, i) * 6 * u - pan * (0.6 + i * 0.12);
    const y = (P ? fy : 0.5 + (fy - 0.5) * 0.9) * H + B.noise1(t * 0.1 + ph * 7, i + 9) * 5 * u;
    B.glow(ctx, x, y, R * 2.1, col, 0.32, {}); // soft halo
    ctx.beginPath(); B.circle(ctx, x, y, R);
    ctx.fillStyle = B.radial(ctx, x - R * 0.35, y - R * 0.4, R * 0.05, R * 1.35, [[0, tint], [0.35, col], [1, B.mix(col, PAL.deep, 0.55)]]); ctx.fill();
  });
  // a faint dot grid: crisp detail that shows how much the glass blurs
  const gap = 6 * u;
  ctx.fillStyle = W8(0.07); ctx.beginPath();
  for (let gx = gap / 2; gx < W; gx += gap) for (let gy = gap / 2; gy < H; gy += gap) B.circle(ctx, gx, gy, 0.22 * u); ctx.fill();
}

// ---------------- layout by aspect
function layout(W, H) {
  const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
  const L = { F, u, P, S, W, H };
  L.lab = P ? 4.3 * u : 4.3 * u; L.h1 = P ? 8.2 * u : 7.2 * u; L.pad = P ? 5 * u : 4.4 * u;
  const box = (cx, cy, w, h) => ({ cx, cy, w, h });
  L.title = P ? box(W / 2, H * 0.47, S.w, H * 0.33) : box(W / 2, H * 0.5, W * 0.62, H * 0.62);
  L.chip = box(W / 2, H * 0.215, 52 * u, 10 * u); // portrait only
  // diagram
  L.phone = P ? box(W / 2, H * 0.285, 27 * u, 46 * u) : box(W * 0.24, H * 0.46, 22 * u, 40 * u);
  L.reader = P ? box(W / 2, H * 0.655, 44 * u, 30 * u) : box(W * 0.76, H * 0.46, 34 * u, 27 * u);
  L.radio = P ? box(W * 0.7, H * 0.497, 46 * u, 9.5 * u) : box(W / 2, H * 0.27, 46 * u, 9.5 * u);
  // key number
  L.ringCard = P ? box(W / 2, H * 0.36, S.w, H * 0.375) : box(W * 0.31, H * 0.5, W * 0.4, H * 0.76);
  L.chart = P ? box(W / 2, H * 0.68, S.w, H * 0.2) : box(W * 0.73, H * 0.5, W * 0.4, H * 0.76);
  // steps
  L.stepHead = P ? [W / 2, H * 0.19] : [S.x + W * 0.15, H * 0.34];
  L.bar = P ? box(W / 2, H * 0.265, S.w, 9 * u) : box(S.x + W * 0.15, H * 0.6, W * 0.3, 14 * u);
  L.steps = [0, 1, 2].map((i) => (P ? box(W / 2, H * (0.385 + i * 0.137), S.w, H * 0.117) : box(W * 0.65, H * (0.27 + i * 0.235), W * 0.56, H * 0.195)));
  // approved
  L.toast = P ? box(W / 2, H * 0.205, S.w, 15 * u) : box(W / 2, H * 0.19, W * 0.5, 17 * u);
  L.switches = P ? box(W / 2, H * 0.43, S.w, H * 0.19) : box(W * 0.3, H * 0.62, W * 0.42, H * 0.44);
  L.bars = P ? box(W / 2, H * 0.665, S.w, H * 0.2) : box(W * 0.73, H * 0.62, W * 0.4, H * 0.44);
  return L;
}

// ---------------- the subjects (the setting: replace these)
/** The phone as a glass slab with a soft screen showing a generic payment card and the contactless mark. */
function phoneContent(ctx, L, t, x, y, w, h, link) {
  const u = L.u, m = w * 0.09;
  ctx.beginPath(); B.roundRect(ctx, x + m, y + m, w - 2 * m, h - 2 * m, 2.4 * u); ctx.fillStyle = B.rgba(PAL.deep, 0.35); ctx.fill();
  // the card on the screen
  const cw = w - 4 * m, ch = cw * 0.63, cy = y + h * 0.36;
  ctx.save(); ctx.translate(0, cy); ctx.beginPath(); B.roundRect(ctx, -cw / 2, -ch / 2, cw, ch, 1.6 * u);
  ctx.fillStyle = B.linear(ctx, -cw / 2, -ch / 2, cw / 2, ch / 2, [PAL.violet, PAL.pink, PAL.amber]); ctx.fill(); ctx.beginPath();
  B.roundRect(ctx, -cw * 0.38, -ch * 0.18, cw * 0.18, ch * 0.24, 0.5 * u); // chip
  ctx.fillStyle = W8(0.55); ctx.fill(); ctx.fillStyle = W8(0.6);
  ctx.restore(); wavesIcon(ctx, -w * 0.16, y + h * 0.7, w * 0.36, 0.7 * u, 1);
  // pulse rings showing the link is live
  if (link > 0) for (let i = 0; i < 2; i++) {
    const q = B.fract(t / 1.2 + i * 0.5);
    ctx.beginPath(); B.circle(ctx, -w * 0.16, y + h * 0.7, w * 0.1 + q * w * 0.4); ctx.strokeStyle = B.rgba(PAL.cyan, 0.5 * (1 - q) * link);
    ctx.lineWidth = 0.4 * u; ctx.stroke();
  }
}
/** The card reader: a glass block with a big contactless target and three status lights. */
function readerContent(ctx, L, t, x, y, w, h, lit) {
  const u = L.u;
  ctx.beginPath(); B.roundRect(ctx, x + w * 0.1, y + h * 0.14, w * 0.8, h * 0.5, 2 * u); ctx.fillStyle = B.rgba(PAL.deep, 0.32); ctx.fill();
  wavesIcon(ctx, x + w * 0.38, y + h * 0.39, h * 0.33, 0.8 * u, 1);
  for (let i = 0; i < 3; i++) {
    const on = B.clamp(lit * 3 - i);
    ctx.beginPath(); B.circle(ctx, x + w * (0.36 + i * 0.14), y + h * 0.8, 1.2 * u); ctx.fillStyle = B.mix("#5d6190", PAL.mint, on);
    ctx.fill(); if (on > 0) B.glow(ctx, x + w * (0.36 + i * 0.14), y + h * 0.8, 4 * u, PAL.mint, 0.5 * on, { add: true });
  }
}
/** Glass pill label straddling a card edge. */
function pill(ctx, L, x, y, str, g, extra = {}) {
  ctx.save(); ctx.font = B.font(L.lab, BODY, 600);
  const w = ctx.measureText(str).width + L.lab * 2.2, h = L.lab * 2.1;
  ctx.restore(); glass(ctx, L, { cx: x, cy: y, w, h }, { ...g, r: h / 2 }, () => label(ctx, str, 0, L.lab * 0.04, L.lab, { maxLines: 1, ...extra }));
}

// ---------------- beats
function titleBeat(ctx, t, L, a, b, close) {
  const g = group(t, a, b), u = L.u, P = L.P;
  if (!g.show) return;
  const tb = L.title;
  glass(ctx, L, tb, moveIn(g, u), (c, x, y, w, h) => {
    label(c, close ? "THE TAKEAWAY" : "HOW IT WORKS", 0, y + h * (P ? 0.16 : 0.15), L.lab * 0.95, { spacing: 0.16, color: B.rgba(PAL.cyan, 1), weight: 700 });
    head(c, close ? "A tap sends a code,\nnot your card" : "How does\ntap-to-pay work?", 0, y + h * 0.44, L.h1, { maxW: w - 2 * L.pad, maxLines: 2 });
    // a settings row: label + toggle, divided by a hairline
    const ry = y + h * 0.8;
    c.fillStyle = W8(0.15); c.fillRect(x + L.pad, ry - h * 0.11, w - 2 * L.pad, Math.max(1, 0.15 * u));
    label(c, "Contactless", x + L.pad, ry, L.lab * 1.05, { align: "left", maxLines: 1 });
    const tx = x + w - L.pad - L.lab * 1.75 * 1.05;
    const on = close ? 1 : B.ease.inOutCubic(B.prog(t, 1.0, 0.3));
    toggle(c, tx, ry, L.lab * 2.1, on);
  });
  if (P) {
    // portrait: a status chip above and a pill below fill the tall frame
    const gc = group(t, a + 0.15, b), gd = group(t, a + 0.3, b);
    glass(ctx, L, L.chip, { ...moveIn(gc, u, [0, -10]), r: L.chip.h / 2 }, (c, x, y, w, h) => {
      disc(c, x + h * 0.5, 0, h * 0.34, "wave", null, u);
      label(c, close ? "Paid. Done." : "Tap. Pay. Done.", x + h * 0.98, 0, L.lab, { align: "left", maxLines: 1 });
    });
    pill(ctx, L, L.W / 2, L.H * 0.73, close ? "Works within about 4 cm" : "Three quick steps", moveIn(gd, u, [0, 12]));
  } else if (close && t > a + 0.35) pill(ctx, L, L.W / 2, tb.cy + tb.h / 2 + 1.2 * u, "Works within about 4 cm", moveIn(group(t, a + 0.35, b), u, [0, 8]));
}

function diagramBeat(ctx, t, L) {
  const a = BEATS[1], b = BEATS[2], u = L.u, P = L.P;
  const g1 = group(t, a, b), g2 = group(t, a + 0.25, b);
  if (!g1.show) return;
  const link = B.span(t, a + 0.9, a + 1.3);
  glass(ctx, L, L.phone, { ...moveIn(g1, u, P ? [0, -14] : [-18, 0]), r: 4.2 * u }, (c, x, y, w, h) => phoneContent(c, L, t, x, y, w, h, link));
  glass(ctx, L, L.reader, { ...moveIn(g2, u, P ? [0, 14] : [18, 0]), r: 3.4 * u }, (c, x, y, w, h) => readerContent(c, L, t, x, y, w, h, B.span(t, a + 1.2, a + 1.7)));
  // the arrow: a gradient capsule stroke drawn on from phone to reader, with radio arcs travelling along it
  const ph = L.phone, rd = L.reader;
  const p0 = P ? [L.W / 2 - 9 * u, ph.cy + ph.h / 2 + 5.5 * u] : [ph.cx + ph.w / 2 + 3 * u, ph.cy - 2 * u];
  const p1 = P ? [L.W / 2 - 9 * u, rd.cy - rd.h / 2 - 2.5 * u] : [rd.cx - rd.w / 2 - 3 * u, rd.cy - 2 * u];
  const pts = P ? B.quad(p0[0], p0[1], L.W / 2 - 24 * u, (p0[1] + p1[1]) / 2, p1[0], p1[1]) : B.quad(p0[0], p0[1], L.W / 2, p0[1] - 7 * u, p1[0], p1[1]);
  const ap = B.prog(t, a + 0.55, 0.6, "inOutCubic") * (1 - g1.out);
  if (ap > 0) {
    ctx.save(); ctx.globalAlpha = 1 - g1.out;
    B.arrow(ctx, pts, { p: ap, width: 0.75 * u, head: 3 * u, color: PAL.glass, headStyle: "tri", dash: [0.2 * u, 1.8 * u] }); ctx.restore();
    for (let i = 0; i < 3; i++) {
      const q = B.fract((t - a) / 1.1 + i / 3);
      if (q > ap) continue;
      const [qx, qy, ang] = B.pointAt(pts, q);
      ctx.save(); ctx.translate(qx, qy); ctx.rotate(ang); ctx.strokeStyle = B.rgba(PAL.cyan, 0.9 * Math.sin(q * Math.PI) * (1 - g1.out));
      ctx.lineWidth = 0.5 * u; ctx.lineCap = "round"; ctx.beginPath(); ctx.arc(-2 * u, 0, 3 * u, -0.7, 0.7); ctx.stroke(); ctx.restore();
    }
  }
  pill(ctx, L, ph.cx, ph.cy + ph.h / 2, "Your phone", moveIn(group(t, a + 0.45, b), u, [0, 6]));
  pill(ctx, L, rd.cx, rd.cy + rd.h / 2, "Card reader", moveIn(group(t, a + 0.6, b), u, [0, 6]));
  const gr = group(t, a + 0.85, b);
  glass(ctx, L, L.radio, { ...moveIn(gr, u, [0, 6]), r: L.radio.h / 2 }, (c, x, y, w, h) => {
    disc(c, x + h * 0.5, 0, h * 0.34, "wave", null, u); label(c, "NFC radio link", x + h * 0.98, 0, L.lab, { align: "left", maxLines: 1 });
  }); if (!P) pill(ctx, L, L.W / 2, L.H * 0.8, "They talk over a weak, short-range radio field", moveIn(group(t, a + 1.1, b), u, [0, 8]));
}

function numberBeat(ctx, t, L) {
  const a = BEATS[2], b = BEATS[3], u = L.u, P = L.P;
  const g1 = group(t, a, b), g2 = group(t, a + 0.25, b);
  if (!g1.show) return;
  const k = B.prog(t, a + 0.3, 1.1, "inOutCubic"); // the phone comes closer: 20 cm -> 4 cm
  const fall = (dd) => 1 / (1 + Math.pow(dd / 4, 3)); // signal vs distance (0.5 at 4 cm)
  const d = B.lerp(20, 4, k), sig = 2 * fall(d);
  const conn = t > a + 1.42;
  const land = t - (a + 1.42), bounce = land > 0 ? 1 + 0.08 * Math.exp(-7 * land) * Math.sin(land * 18) : 1;
  glass(ctx, L, L.ringCard, moveIn(g1, u), (c, x, y, w, h) => {
    label(c, "Distance to reader", 0, y + h * 0.1, L.lab, { maxLines: 1, maxW: w - 2 * L.pad });
    const R = P ? 21 * u : 17 * u, cy = y + h * (P ? 0.47 : 0.45);
    ring(c, 0, cy, R, (P ? 2.4 : 2.6) * u, B.clamp(sig) * 0.999, u); c.save(); c.translate(0, cy); c.scale(bounce, bounce);
    head(c, Math.round(d) + " cm", 0, 0, (P ? 10.5 : 9) * u, { maxLines: 1, color: conn ? PAL.glass : W8(0.92) }); c.restore();
    label(c, "NFC only reaches about 4 cm", 0, y + h * (P ? 0.86 : 0.87), L.lab, { maxW: w - 2 * L.pad, maxLines: 2, weight: 700 });
  });
  glass(ctx, L, L.chart, moveIn(g2, u, P ? [0, 16] : [16, 0]), (c, x, y, w, h) => {
    label(c, "Signal strength", x + L.pad, y + L.pad + L.lab * 0.5, L.lab, { align: "left", maxLines: 1 });
    // a small line chart: signal falls off steeply with distance (x: 0 -> 20 cm)
    const cx0 = x + L.pad, cx1 = x + w - L.pad, cyT = y + h * (P ? 0.34 : 0.24), cyB = y + h * (P ? 0.86 : 0.7);
    const X = (dd) => B.lerp(cx0, cx1, dd / 20), Y = (s) => B.lerp(cyB, cyT, s);
    const curve = [];
    for (let i = 0; i <= 40; i++) { const dd = i / 2; curve.push([X(dd), Y(fall(dd))]); }
    c.fillStyle = B.rgba(PAL.mint, 0.14); // the zone where a tap works
    c.fillRect(cx0, cyT, X(4) - cx0, cyB - cyT); c.fillStyle = W8(0.1);
    for (let i = 0; i <= 3; i++) c.fillRect(cx0, B.lerp(cyT, cyB, i / 3), cx1 - cx0, Math.max(1, 0.1 * u));
    const shown = B.trim(curve, 0, B.prog(t, a + 0.35, 0.7, "outCubic"));
    if (shown.length > 1) {
      c.beginPath(); B.poly(c, [...shown, [shown[shown.length - 1][0], cyB], [cx0, cyB]], true);
      c.fillStyle = B.linear(c, 0, cyT, 0, cyB, [B.rgba(PAL.violet, 0.45), B.rgba(PAL.violet, 0)]); c.fill(); c.beginPath();
      B.poly(c, shown, false); c.strokeStyle = accent(c, cx0, 0, cx1, 0); c.lineWidth = 0.7 * u; c.lineJoin = c.lineCap = "round"; c.stroke();
    }
    if (k > 0) {
      const px = X(d), py = Y(fall(d));
      B.glow(c, px, py, 5 * u, PAL.pink, 0.7, { add: true }); c.beginPath(); B.circle(c, px, py, 1.2 * u); c.fillStyle = PAL.glass; c.fill();
    }
  });
  // the "Connected" toast springs down over the chart (a second frost pass: it blurs the card under it)
  if (conn) {
    const gt = group(t, a + 1.42, b, 0.7);
    const tb = P ? { cx: L.S.r - 25 * u, cy: L.chart.cy - L.chart.h / 2 - u, w: 46 * u, h: 10 * u } : { cx: L.chart.cx + 2 * u, cy: L.chart.cy + L.chart.h * 0.36, w: 34 * u, h: 10 * u };
    frost(ctx, L.W, L.H, "b");
    glass(ctx, L, tb, { ...moveIn(gt, u, [0, -10]), r: tb.h / 2 }, (c, x, y, w, h) => {
      disc(c, x + h * 0.5, 0, h * 0.34, "check", "mint", u); label(c, "Connected", x + h * 0.98, 0, L.lab, { align: "left", maxLines: 1, weight: 700 });
    });
  }
}

function stepsBeat(ctx, t, L) {
  const a = BEATS[3], b = BEATS[4], u = L.u, P = L.P;
  const g = group(t, a, b);
  if (!g.show) return;
  head(ctx, "Three steps", L.stepHead[0], L.stepHead[1], L.h1 * (P ? 0.78 : 0.72), { alpha: g.alpha, maxW: P ? L.S.w : L.W * 0.3, align: "center" });
  const T = [a + 0.15, a + 0.7, a + 1.25]; // each card lands here
  const done = T.reduce((n, tt) => n + B.span(t, tt + 0.3, tt + 0.6), 0) / 3;
  glass(ctx, L, L.bar, { ...moveIn(group(t, a + 0.05, b), u, [0, 8]), r: L.bar.h / 2 }, (c, x, y, w, h) => {
    const n = Math.max(1, T.filter((tt) => t >= tt + 0.1).length);
    if (P) {
      label(c, "Step " + n + " of 3", x + L.pad * 0.8, 0, L.lab, { align: "left", maxLines: 1, weight: 700 });
      progress(c, x + w * 0.42, 0, w * 0.52, h * 0.3, done);
    } else {
      label(c, "Step " + n + " of 3", 0, y + h * 0.3, L.lab, { maxLines: 1, weight: 700 }); progress(c, x + L.pad, y + h * 0.68, w - 2 * L.pad, h * 0.17, done);
    }
  });
  const texts = ["Hold your phone near the reader", "It sends a one-time code, not your card number", "Your bank checks the code and says yes"];
  L.steps.forEach((sb, i) => {
    const gi = group(t, T[i] - 0.1, b, 0.8);
    if (!gi.show) return;
    const m = moveIn(gi, u, P ? [70, 0] : [60, 0]);
    // stacking with parallax: earlier cards nudge back a hair as each new one lands
    const later = T.filter((tt, j) => j > i).reduce((n, tt) => n + B.span(t, tt, tt + 0.4, "outCubic"), 0);
    m.s *= 1 - 0.012 * later; m.dx -= later * 0.8 * u;
    glass(ctx, L, sb, m, (c, x, y, w, h) => {
      const r = Math.min(h * 0.3, 6 * u), dx = x + L.pad * 0.8 + r;
      const ok = B.span(t, T[i] + 0.35, T[i] + 0.5);
      disc(c, dx, 0, r, ok > 0.5 ? "check" : String(i + 1), ok > 0.5 ? "mint" : null, u);
      head(c, texts[i], dx + r + L.pad * 0.7, 0, L.lab * (P ? 1.08 : 1.12), { align: "left", maxW: w - (r * 2 + L.pad * 2.4), maxLines: 2 });
    });
  });
}

function approvedBeat(ctx, t, L) {
  const a = BEATS[4], b = BEATS[5], u = L.u, P = L.P;
  const g1 = group(t, a + 0.05, b), g2 = group(t, a + 0.25, b);
  if (!g1.show) return;
  const codeOn = B.ease.inOutCubic(B.prog(t, a + 0.75, 0.3));
  glass(ctx, L, L.switches, moveIn(g1, u, P ? [0, 14] : [-14, 0]), (c, x, y, w, h) => {
    const rows = [["Card number sent", 0], ["One-time code sent", codeOn]];
    rows.forEach(([txt, on], i) => {
      const ry = y + h * (0.3 + i * 0.42);
      label(c, txt, x + L.pad, ry, L.lab * 1.02, { align: "left", maxLines: 1, maxW: w * 0.66 }); toggle(c, x + w - L.pad - L.lab * 1.9, ry, L.lab * 2.1, on);
      if (i === 0) {
        c.fillStyle = W8(0.15); c.fillRect(x + L.pad, y + h * 0.51, w - 2 * L.pad, Math.max(1, 0.15 * u));
      }
    });
  });
  glass(ctx, L, L.bars, moveIn(g2, u, P ? [0, 16] : [14, 0]), (c, x, y, w, h) => {
    label(c, "Added to your activity", x + L.pad, y + L.pad + L.lab * 0.5, L.lab, { align: "left", maxLines: 1, maxW: w - 2 * L.pad });
    const vals = [0.35, 0.6, 0.28, 0.5, 0.42, 0.7, 0.55], n = vals.length;
    const bx0 = x + L.pad, bx1 = x + w - L.pad, by1 = y + h - L.pad * 0.9, by0 = y + h * (P ? 0.42 : 0.36);
    const bw = ((bx1 - bx0) / n) * 0.56;
    vals.forEach((v, i) => {
      const last = i === n - 1;
      const grow = last ? B.spring(B.prog(t, a + 0.6, 0.7), 1, 5) : B.ease.outCubic(B.prog(t, a + 0.35 + i * 0.05, 0.5));
      const bh = (by1 - by0) * v * grow, bx = bx0 + ((bx1 - bx0) / n) * (i + 0.22);
      if (bh < 1) return; c.beginPath(); B.roundRect(c, bx, by1 - bh, bw, bh, bw * 0.35);
      c.fillStyle = last ? accent(c, bx, by1 - bh, bx + bw, by1) : W8(0.26); c.fill();
      if (last) B.glow(c, bx + bw / 2, by1 - bh, bw * 1.6, PAL.pink, 0.45, { add: true });
    });
  });
  // the notification toast slides down from the top over everything (second frost pass)
  const gt = group(t, a + 0.35, b, 0.8);
  frost(ctx, L.W, L.H, "b");
  glass(ctx, L, L.toast, moveIn(gt, u, [0, -22]), (c, x, y, w, h) => {
    const r = h * 0.3;
    disc(c, x + L.pad * 0.7 + r, 0, r, "check", "mint", u);
    const tx = x + L.pad * 0.7 + r * 2 + L.pad * 0.6;
    head(c, "Payment approved", tx, -h * 0.17, L.lab * 1.1, { align: "left", maxLines: 1, maxW: w - (tx - x) - L.pad });
    label(c, "Your card number stayed private", tx, h * 0.2, L.lab * 0.95, { align: "left", maxLines: 1, maxW: w - (tx - x) - L.pad * 0.5, color: W8(0.82) });
  });
}

// ---------------- the touch cursor (one continuous path of taps)
function cursor(ctx, t, L) {
  const u = L.u, tb = L.title, P = L.P;
  const tog = [tb.cx + tb.w / 2 - L.pad - L.lab * 1.75 * 1.05 + L.lab * 0.9, tb.cy + tb.h * 0.3];
  const st = L.steps.map((s) => [s.cx - s.w / 2 + L.pad * 0.8 + Math.min(s.h * 0.3, 6 * u), s.cy]);
  const sw = L.switches, cod = [sw.cx + sw.w / 2 - L.pad - L.lab * 1.9 + L.lab * 0.9, sw.cy - sw.h / 2 + sw.h * 0.72];
  // taps: { t, p, appear (the finger shows up), hide (it leaves) }; between taps of one run it glides on an arc
  const taps = [
    { t: 0.98, p: tog, appear: 0.5, hide: 1.6 },
    { t: 6.88, p: st[0], appear: 6.45 }, { t: 7.43, p: st[1] }, { t: 7.98, p: st[2], hide: 8.45 },
    { t: 9.33, p: cod, appear: 8.95, hide: 9.95 },
  ];
  const startOf = (i) => (taps[i].appear != null ? taps[i].appear : taps[i - 1].t + 0.12);
  let cur = -1;
  for (let i = 0; i < taps.length; i++) if (t >= startOf(i)) cur = i; if (cur < 0) return;
  let r0 = cur, r1 = cur;
  while (taps[r0].appear == null) r0--; while (taps[r1].hide == null) r1++;
  const alpha = B.span(t, taps[r0].appear, taps[r0].appear + 0.2) * (1 - B.span(t, taps[r1].hide - 0.25, taps[r1].hide));
  const tp = taps[cur], s0 = startOf(cur);
  const from = tp.appear != null ? [tp.p[0] + 14 * u, tp.p[1] + 18 * u] : taps[cur - 1].p;
  const k = B.ease.inOutCubic(B.prog(t, s0, Math.max(0.2, tp.t - 0.08 - s0)));
  const x = B.lerp(from[0], tp.p[0], k), y = B.lerp(from[1], tp.p[1], k) - Math.sin(k * Math.PI) * 4 * u;
  const press = Math.max(0, 1 - Math.abs(t - tp.t) / 0.1), ripple = B.prog(t, tp.t, 0.6);
  touch(ctx, x, y, u, press, ripple, alpha);
}

// ---------------- transitions and finishing
/** A diagonal band of light sweeping across the frame at each beat change, like light catching a glass sheet. */
function sheen(ctx, W, H, t) {
  for (const at of BEATS.slice(1)) {
    const p = B.span(t, at - 0.2, at + 0.5, "inOutSine");
    if (p <= 0 || p >= 1) continue;
    const D = Math.hypot(W, H), x = B.lerp(-D * 0.3, W + D * 0.3, p);
    ctx.save(); ctx.globalCompositeOperation = "soft-light"; ctx.translate(x, H / 2); ctx.rotate(0.35);
    ctx.fillStyle = B.linear(ctx, -D * 0.12, 0, D * 0.12, 0, [W8(0), W8(0.5), W8(0)]); ctx.fillRect(-D * 0.12, -D, D * 0.24, 2 * D); ctx.restore();
  }
}

function draw(ctx, W, H, t) {
  const L = layout(W, H);
  FROST = null; MIN = L.u * 3.9; backdrop(ctx, W, H, t, L);
  frost(ctx, W, H, "a"); // everything behind the first glass layer is the backdrop
  const A = FROST;
  titleBeat(ctx, t, L, 0, BEATS[1], false); diagramBeat(ctx, t, L); numberBeat(ctx, t, L); FROST = A; stepsBeat(ctx, t, L); approvedBeat(ctx, t, L);
  if (t >= BEATS[5] - 0.05) {
    frost(ctx, W, H, "a"); titleBeat(ctx, t, L, BEATS[5], DUR + 1, true);
  }
  cursor(ctx, t, L); sheen(ctx, W, H, t);
  // finishing: a very light vignette and fine moving grain (glass UIs stay clean: grain only to stop banding)
  B.vignette(ctx, W, H, { amount: 0.32, inner: 0.55, color: "#03041a" }); B.grain(ctx, W, H, { amount: 0.035, t });
}

// ---------------- sound: soft taps, glassy ticks, notification chimes, airy pad
SOUND.define("glass-tap", (v) => {
  // a soft fingertip on glass: a muted click and a tiny hollow body
  v.noise({ filter: "bandpass", f: 2600, q: 1.4, a: 0.0006, len: 0.025, peak: 0.28 });
  v.tone({ f: 900, f2: 520, glide: 0.04, a: 0.001, len: 0.06, peak: 0.22 });
}, { verb: 0.18 });
SOUND.define("glass-tick", (v, o) => {
  // a thin glassy tick: high sine with an inharmonic partial that rings briefly
  const f = o.note ? v.hz(o.note) : 3400 * v.rate;
  v.tone({ f, a: 0.0006, len: 0.09, peak: 0.12, noPitch: true }); v.tone({ f: f * 2.71, a: 0.0005, len: 0.05, peak: 0.04, noPitch: true });
}, { verb: 0.4 });
SOUND.define("glass-chime", (v) => {
  // notification: two soft rounded bell notes a fifth apart, the second a touch louder
  [["E6", 0, 0.2], ["B6", 0.11, 0.22]].forEach(([n, at, pk]) => {
    const f = v.hz(n);
    v.tone({ f, at, a: 0.004, len: 0.9, peak: pk }); v.tone({ f: f * 2.01, at, a: 0.003, len: 0.3, peak: pk * 0.25 });
    v.tone({ f: f * 3.98, at, a: 0.002, len: 0.12, peak: pk * 0.08 });
  });
}, { verb: 0.5 });
SOUND.define("glass-slide", (v, o) => {
  // a card gliding in: airy band-passed noise that sweeps up and fades
  v.noise({ filter: "bandpass", f: 900, f2: 3600, q: 0.9, a: 0.06, len: o.dur ?? 0.35, peak: 0.16 });
}, { verb: 0.3 });

function score(k) {
  const tick = (at, note, gain = 1) => k.at(at, "glass-tick", { note, gain });
  k.bed("pad", 0, DUR, { notes: ["D3", "A3", "E4", "F#4", "C#5"], gain: 0.45, bright: 1500 });
  [0.05, 1.75, 2.05, 4.15, 6.35, 8.55, 10.35].forEach((at) => k.at(at, "glass-slide", { dur: 0.45 })); // every card group gliding in or out
  tick(0.2, "A6"); tick(0.35, "E7", 0.6); tick(2.2, "D7"); tick(2.45, "A6"); tick(3.0, "C#7");
  k.at(0.98, "glass-tap").at(1.02, "boop", { gain: 0.4, pitch: 5 }); tick(1.15, "F#7", 0.6);
  k.at(2.55, "swish", { gain: 0.35 }).at(2.75, "pop", { gain: 0.35 }); k.repeat(2.9, 0.37, 4, "sonar", { gain: 0.16, vary: 2 });
  k.seq(3.4, 0.12, ["D6", "F#6", "A6"], { voice: "glass-tick", gain: 0.7 });
  k.repeat(4.5, 0.075, 15, "glass-tick", { gain: 0.45, vary: 1 }); // the distance counting down
  k.at(5.62, "glass-chime").at(5.62, "chord", { notes: ["D5", "F#5", "A5", "E6"], gain: 0.5 }).at(5.62, "glass-tap", { gain: 0.7 });
  [6.55, 7.1, 7.65].forEach((at, i) => { k.at(at, "glass-slide", { dur: 0.3, gain: 0.6, pan: 0.4 }).at(at + 0.33, "glass-tap", { gain: 0.8 }); tick(at + 0.35, ["A6", "C#7", "E7"][i]); });
  k.at(9.0, "glass-chime", { gain: 0.9 }).at(9.33, "glass-tap").at(9.65, "boop", { gain: 0.35, pitch: 7 }); tick(9.38, "F#7", 0.7);
  k.at(10.55, "chord", { notes: ["D4", "A4", "E5", "F#5"], strum: 0.06, gain: 0.55 }).at(11.1, "chime", { note: "A6", gain: 0.3 }); tick(10.8, "D7");
}

Player.register({
  id: "glassmorphism", name: "Glassmorphism UI", duration: DUR,
  fonts: {
    href: "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@500;600;700&display=swap",
    faces: ['800 20px "Plus Jakarta Sans"', '700 20px "Plus Jakarta Sans"', '600 20px "Inter"', '700 20px "Inter"'],
  },
  beats: BEATS,
  beatNames: ["Title", "Diagram", "Key number: 4 cm", "Three steps", "Approved", "Close"],
  stills: [1.3, 3.6, 5.95, 8.2, 10.0, 11.6],
  draw, score,
});
})();
