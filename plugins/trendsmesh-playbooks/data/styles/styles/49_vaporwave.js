/* 49 Vaporwave - reference animation.
 * Topic (setting, replace it): "How does a cassette store sound?" - a head turns the signal into magnetism, the
 * tape's particles keep the pattern at 4.76 cm/s, and the moving pattern is read back as sound.
 * Rendering (keep it): a 1990s mall / early-web daydream in daylight pastels. A pink-to-cyan sky with soft streak
 * clouds, a big low sun cut by horizontal gaps that widen toward the horizon, a pastel perspective checkerboard
 * floor creeping toward the viewer, a white fluted marble column with drifting veins that turns slowly, plum palm
 * silhouettes, one decorative 夢 ("dream"). Content lives in bevelled grey old-OS-style windows (generic: no logos
 * or names) that open with zoom outlines, with a pink-to-cyan title bar. Headings in DM Serif Display with a
 * pink + cyan offset shadow, UI text in Chakra Petch. Finishing: the frame is split into red and cyan channels drawn a
 * little apart (chromatic aberration) in horizontal strips that wobble like tape, a VHS tracking band, fine
 * scanlines, glitter sparkles, a soft vignette. Motion is slow and floaty; scanline wipes between beats.
 */
(function () {
"use strict";
const B = window.Brush;

// ---------------- palette and type (from the card)
const PAL = { pink: "#ff9ad5", cyan: "#8ff0ff", sun: "#ffe08a", hot: "#ff4fa3", teal: "#35c2bc", marble: "#f6f2f8", grey: "#c4c2d0", plum: "#2b1747" };
const HEAD = "DM Serif Display", UI = "Chakra Petch", JP = "Noto Serif JP";
const DUR = 13, BEATS = [0, 2.3, 4.8, 7.2, 9.4, 11.0];
if (document.fonts) document.fonts.load('600 20px "Noto Serif JP"', "夢").catch(() => null); // the one CJK glyph
let MIN = 30; // smallest legible text for this frame

// ---------------- type helpers
/** Heading: DM Serif Display in plum, a hot-pink and a cyan offset copy behind it (a printed-retro double shadow). */
function heading(ctx, str, x, y, size, o = {}) {
  const base = { size, minSize: Math.min(size, Math.max(size * 0.6, MIN)), family: HEAD, weight: 400, maxW: o.maxW, maxLines: o.maxLines ?? 3, lineH: 1.05, align: o.align, alpha: o.alpha, style: o.italic ? "italic" : "" };
  const d = size * 0.045;
  B.texture(ctx, () => { // the coloured offset copies are decoration, the plum one is what you read
    B.text(ctx, str, x + d * 2, y + d * 2, { ...base, color: PAL.cyan });
    B.text(ctx, str, x + d, y + d, { ...base, color: PAL.hot });
  });
  return B.text(ctx, str, x, y, { ...base, color: o.color || PAL.plum });
}
function ui(ctx, str, x, y, size, o = {}) {
  return B.text(ctx, str, x, y, { size, minSize: Math.min(size, Math.max(size * 0.6, MIN)), family: UI, weight: o.weight ?? 600, color: o.color || PAL.plum, maxW: o.maxW, maxLines: o.maxLines ?? 2, lineH: 1.12, align: o.align, alpha: o.alpha, letterSpacing: o.sp ?? 0.01 });
}

// ---------------- the dream world: sky, sun, floor, column, palms
function layout(W, H) {
  const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
  const L = { F, u, P, S, W, H, lab: 4.3 * u, small: 3.95 * u };
  const box = (cx, cy, w, h) => ({ cx, cy, w, h });
  L.hz = H * (P ? 0.57 : 0.6);
  L.sunR = P ? 34 * u : 27 * u;
  L.sunX = P ? W * 0.68 : W / 2;
  L.col = P ? { x: W * 0.13, top: H * 0.33, bot: H * 0.93, w: 17 * u } : { x: W * 0.085, top: H * 0.16, bot: H * 0.96, w: 12 * u };
  L.palms = P ? [[W * 0.9, H * 0.9, H * 0.42, -0.18], [W * 0.74, H * 0.66, H * 0.2, 0.15]] : [[W * 0.93, H * 0.98, H * 0.66, -0.2], [W * 0.8, H * 0.7, H * 0.3, 0.16]];
  L.kanji = P ? [W * 0.5, H * 0.205, 11 * u] : [W * 0.86, H * 0.2, 13 * u];
  L.title = P ? box(W / 2, H * 0.385, S.w, H * 0.23) : box(W * 0.4, H * 0.42, W * 0.52, H * 0.5);
  L.tape = P ? box(W * 0.4, H * 0.665, 60 * u, 38 * u) : box(W * 0.76, H * 0.66, W * 0.3, H * 0.44);
  L.diagram = P ? box(W / 2, H * 0.46, S.w, H * 0.6) : box(W * 0.52, H * 0.5, W * 0.66, H * 0.8);
  L.speed = P ? box(W / 2, H * 0.37, S.w, H * 0.36) : box(W * 0.42, H * 0.45, W * 0.52, H * 0.66);
  L.inch = P ? box(W / 2, H * 0.68, S.w * 0.9, 17 * u) : box(W * 0.72, H * 0.8, W * 0.42, 17 * u);
  L.steps = [0, 1, 2].map((i) => (P ? box(W * 0.47 + i * 2.4 * u, H * (0.29 + i * 0.165), S.w * 0.92, H * 0.15) : box(W * (0.38 + i * 0.1), H * (0.26 + i * 0.245), W * 0.54, H * 0.21)));
  L.play = L.diagram;
  return L;
}
function sky(ctx, W, H, L, t) {
  ctx.drawImage(B.layer("vw-sky", W, H, (g, w, h) => {
    g.fillStyle = B.linear(g, 0, 0, 0, L.hz, [[0, PAL.pink], [0.45, "#e2a8f5"], [0.8, "#b7d4ff"], [1, PAL.cyan]]);
    g.fillRect(0, 0, w, h);
  }), 0, 0);
  // soft streak clouds drifting very slowly
  const r = B.rng("vw-clouds");
  for (let i = 0; i < 6; i++) {
    const y = L.hz * r.range(0.12, 0.8), cw = W * r.range(0.25, 0.5), x = B.fract(r() + t * 0.006 * (1 + i * 0.3)) * (W + cw) - cw;
    ctx.beginPath();
    B.capsule(ctx, x, y, cw, L.u * r.range(1.2, 2.6));
    ctx.fillStyle = B.rgba(PAL.marble, 0.35);
    ctx.fill();
  }
}
/** The big low sun: a yellow-to-hot-pink disc on the horizon, its lower half cut by gaps that widen and drift down. */
function sun(ctx, W, L, t) {
  const R = L.sunR, x = L.sunX, y = L.hz, g = B.scratch("vw-sun", 2 * R + 4, R + 4);
  g.translate(R + 2, R + 2);
  g.fillStyle = B.linear(g, 0, -R, 0, 0, [PAL.sun, "#ffb07a", PAL.hot]);
  g.beginPath();
  g.arc(0, 0, R, Math.PI, 0);
  g.fill();
  g.globalCompositeOperation = "destination-out";
  for (let i = 0; i < 7; i++) {
    const k = B.fract(i / 7 + t * 0.03), gy = -R * 0.55 + k * R * 0.55;
    g.fillRect(-R - 2, gy, 2 * R + 4, 0.2 * L.u + k * k * 2.4 * L.u);
  }
  B.glow(ctx, x, y - R * 0.4, R * 1.8, PAL.sun, 0.35);
  ctx.drawImage(g.canvas, x - R - 2, y - R - 2);
}
/** Perspective checkerboard: rows spaced by 1/z, columns converging to the centre, fading into the haze. */
function floor(ctx, W, H, L, t) {
  const hz = L.hz, cx = W / 2, depth = (H - hz) * 1.1, cell = W * 0.16;
  ctx.fillStyle = PAL.teal;
  ctx.fillRect(0, hz, W, H - hz);
  const off = B.fract(t * 0.35), rows = 34;
  for (let pass = 0; pass < 2; pass++) {
    ctx.beginPath();
    for (let j = 0; j < rows; j++) {
      const z0 = 0.8 + (j - off) * 0.45, z1 = z0 + 0.45;
      if (z1 <= 0.3) continue;
      const y0 = hz + depth / Math.max(z0, 0.3), y1 = hz + depth / z1;
      if (y1 > H) continue;
      for (let m = -14; m < 14; m++) {
        if (((m + j + 100) & 1) !== pass) continue;
        const xa = (X, y) => cx + ((X * cell) / depth) * (y - hz);
        B.poly(ctx, [[xa(m, y0), y0], [xa(m + 1, y0), y0], [xa(m + 1, y1), y1], [xa(m, y1), y1]], true);
      }
    }
    ctx.fillStyle = pass ? PAL.marble : "#7fd9e8";
    ctx.fill();
  }
  // haze where the floor meets the sky
  ctx.fillStyle = B.linear(ctx, 0, hz, 0, hz + (H - hz) * 0.45, [B.rgba(PAL.cyan, 0.95), B.rgba(PAL.pink, 0.25), B.rgba(PAL.pink, 0)]);
  ctx.fillRect(0, hz, W, (H - hz) * 0.45);
}
/** Marble veins: a cached grey-lilac vein texture (folded fbm), scrolled across the shaft as the column turns. */
function veins() {
  return B.layer("vw-veins", 160, 320, (g, w, h) => {
    const img = g.createImageData(w, h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const n = B.fbm(x / 60, y / 90, 4, 3), v = Math.abs(Math.sin(x / 9 + y / 31 + n * 7));
      const a = Math.pow(1 - B.clamp(v * 3), 3) * 0.75 + Math.pow(1 - B.clamp(v * 9), 2) * 0.25, i = (y * w + x) * 4;
      img.data[i] = 120; img.data[i + 1] = 104; img.data[i + 2] = 150; img.data[i + 3] = a * 150;
    }
    g.putImageData(img, 0, 0);
  });
}
/** A fluted Doric column turning slowly: flutes slide around the shaft, the veins scroll with them, a soft side light. */
function column(ctx, L, t) {
  const { x, top, bot, w } = L.col, u = L.u, R = w / 2, rot = t * 0.22;
  const capH = w * 0.42, baseH = w * 0.5, sy0 = top + capH, sy1 = bot - baseH;
  B.contactShadow(ctx, x + w * 0.3, bot, w * 1.4, w * 0.22, 0.25, PAL.plum);
  const shaft = (c) => B.poly(c, [[x - R * 0.88, sy0], [x + R * 0.88, sy0], [x + R, sy1], [x - R, sy1]], true);
  B.clip(ctx, shaft, () => {
    ctx.fillStyle = B.linear(ctx, x - R, 0, x + R, 0, [PAL.marble, "#ffffff", "#e6dff0", "#bfb2d6"]);
    ctx.fillRect(x - R, sy0, w, sy1 - sy0);
    const tex = veins(), tw = w * 2, th = sy1 - sy0, ox = -((rot * R) % tw);
    for (let k = 0; k < 3; k++) ctx.drawImage(tex, x - R + ox + k * tw, sy0, tw, th);
    for (let i = 0; i < 18; i++) { // flutes: dark grooves that crowd together toward the edges
      const a = B.fract(i / 18 + rot / B.TAU) * B.TAU, s = Math.sin(a), c = Math.cos(a);
      if (c < 0.05) continue;
      ctx.fillStyle = B.rgba("#8d7fae", 0.18 + 0.25 * (s > 0 ? s : 0));
      ctx.fillRect(x + s * R - c * 0.35 * u, sy0, c * 0.7 * u + 1, sy1 - sy0);
    }
  });
  const block = (bx, by, bw, bh, k) => {
    ctx.fillStyle = B.linear(ctx, bx, 0, bx + bw, 0, [PAL.marble, "#ffffff", B.mix("#cfc4e2", PAL.marble, k)]);
    ctx.fillRect(bx, by, bw, bh);
  };
  block(x - R * 1.35, top, R * 2.7, capH * 0.4, 0.3); // abacus
  ctx.beginPath(); // echinus
  B.poly(ctx, [[x - R * 1.25, top + capH * 0.4], [x + R * 1.25, top + capH * 0.4], [x + R * 0.9, sy0], [x - R * 0.9, sy0]], true);
  ctx.fillStyle = B.linear(ctx, x - R, 0, x + R, 0, [PAL.marble, "#ffffff", "#cbbfe0"]);
  ctx.fill();
  block(x - R * 1.2, sy1, R * 2.4, baseH * 0.45, 0.4);
  block(x - R * 1.45, sy1 + baseH * 0.45, R * 2.9, baseH * 0.55, 0.2);
}
/** Palm silhouette in plum: a curved tapering trunk and drooping fronds that sway a little. */
function palm(ctx, x, y, h, lean, t, u, i) {
  const sw = Math.sin(t * 0.7 + i * 2) * 0.02, tx = x + (lean + sw) * h, ty = y - h;
  ctx.globalAlpha = 0.86;
  B.taperStroke(ctx, B.quad(x, y, x + lean * h * 0.2, y - h * 0.55, tx, ty), { width: h * 0.05, color: PAL.plum, taperIn: 0, taperOut: 0.6 });
  for (let k = 0; k < 8; k++) {
    const a = -Math.PI / 2 + (k - 3.5) * 0.42 + sw * 3, len = h * (0.42 + 0.06 * Math.cos(k * 1.7));
    const ex = tx + Math.cos(a) * len, ey = ty + Math.sin(a) * len * 0.35 + len * 0.42;
    B.taperStroke(ctx, B.quad(tx, ty, tx + Math.cos(a) * len * 0.6, ty + Math.sin(a) * len * 0.55 - len * 0.05, ex, ey), { width: h * 0.045, color: PAL.plum, taperIn: 0.1, taperOut: 1 });
  }
  ctx.globalAlpha = 1;
}
function world(ctx, W, H, L, t) {
  sky(ctx, W, H, L, t);
  sun(ctx, W, L, t);
  floor(ctx, W, H, L, t);
  L.palms.forEach(([x, y, h, lean], i) => palm(ctx, x, y, h, lean, t, L.u, i));
  column(ctx, L, t);
}

// ---------------- the old-OS window (generic: bevels, a gradient title bar, three box buttons)
/** Bevelled box: light on the top and left, dark on the bottom and right (sunken swaps them). */
function bevel(ctx, x, y, w, h, d, sunken) {
  const lt = sunken ? "#6c6880" : "#ffffff", dk = sunken ? "#ffffff" : "#5d5a70";
  ctx.fillStyle = lt; ctx.fillRect(x, y, w, d); ctx.fillRect(x, y, d, h);
  ctx.fillStyle = dk; ctx.fillRect(x, y + h - d, w, d); ctx.fillRect(x + w - d, y, d, h);
}
/**
 * One window. Opening: three dotted outlines zoom out from the centre, then the window lands with a slow overshoot.
 * Closing: it squashes to a line and vanishes. content(ctx, x, y, w, h) is clipped to the sunken client area.
 */
function win(ctx, L, b, title, t, a, e, content) {
  if (t < a || t > e) return;
  const u = L.u, op = B.prog(t, a, 0.7), cl = B.span(t, e - 0.35, e, "inCubic");
  ctx.save();
  ctx.translate(b.cx, b.cy + B.bob(t, 0.35 * u, 4.2, b.cx / 997));
  const zk = op / 0.45;
  if (zk < 1.3) for (let i = 0; i < 3; i++) { // zoom outlines
    const k = B.clamp(zk - i * 0.18);
    if (k <= 0 || k >= 1) continue;
    ctx.setLineDash([u * 0.8, u * 0.6]);
    ctx.strokeStyle = B.rgba(PAL.plum, 0.7);
    ctx.lineWidth = 0.3 * u;
    ctx.strokeRect((-b.w / 2) * k, (-b.h / 2) * k, b.w * k, b.h * k);
    ctx.setLineDash([]);
  }
  const k = B.prog(t, a + 0.3, 0.55);
  if (k <= 0) return ctx.restore();
  ctx.scale(B.ease.outBack(k, 1.2) * (1 + cl * 0.05), 1 - cl * 0.97);
  ctx.globalAlpha = Math.min(1, k * 3) * (1 - cl * 0.6);
  const x = -b.w / 2, y = -b.h / 2, w = b.w, h = b.h, d = Math.max(1.5, 0.3 * u), tb = L.small * 1.6;
  ctx.fillStyle = B.rgba(PAL.plum, 0.3);
  ctx.fillRect(x + 1.4 * u, y + 1.4 * u, w, h); // hard offset shadow
  ctx.fillStyle = PAL.grey;
  ctx.fillRect(x, y, w, h);
  bevel(ctx, x, y, w, h, d);
  bevel(ctx, x + d, y + d, w - 2 * d, h - 2 * d, d * 0.6);
  const ix = x + 3 * d, iy = y + 3 * d, iw = w - 6 * d;
  ctx.fillStyle = B.linear(ctx, ix, 0, ix + iw, 0, [PAL.hot, "#c98bff", "#5fc8ff"]);
  ctx.fillRect(ix, iy, iw, tb);
  ui(ctx, title, ix + 1.4 * u, iy + tb / 2, L.small, { align: "left", color: "#ffffff", maxLines: 1, maxW: iw - tb * 3.4 });
  for (let i = 0; i < 3; i++) { // minimise / maximise / close boxes, glyphs drawn as lines
    const s = tb * 0.72, bx = ix + iw - (3 - i) * (s + 0.5 * u) - 0.3 * u, by = iy + (tb - s) / 2;
    ctx.fillStyle = PAL.grey; ctx.fillRect(bx, by, s, s);
    bevel(ctx, bx, by, s, s, d * 0.6);
    ctx.strokeStyle = PAL.plum; ctx.lineWidth = Math.max(1.5, s * 0.1);
    ctx.beginPath();
    if (i === 0) { ctx.moveTo(bx + s * 0.28, by + s * 0.7); ctx.lineTo(bx + s * 0.62, by + s * 0.7); }
    else if (i === 1) ctx.rect(bx + s * 0.27, by + s * 0.27, s * 0.46, s * 0.42);
    else { ctx.moveTo(bx + s * 0.3, by + s * 0.3); ctx.lineTo(bx + s * 0.7, by + s * 0.7); ctx.moveTo(bx + s * 0.7, by + s * 0.3); ctx.lineTo(bx + s * 0.3, by + s * 0.7); }
    ctx.stroke();
  }
  const cx = ix, cy = iy + tb + 2 * d, cw = iw, ch = h - (cy - y) - 3 * d;
  ctx.fillStyle = "#fbf6ff";
  ctx.fillRect(cx, cy, cw, ch);
  bevel(ctx, cx, cy, cw, ch, d * 0.7, true);
  if (content) B.clip(ctx, (c) => c.rect(cx + d, cy + d, cw - 2 * d, ch - 2 * d), () => content(ctx, cx, cy, cw, ch));
  ctx.restore();
}

// ---------------- subjects (the setting: replace these)
/** A clear pink cassette: label strip, a window onto two turning reels with tape wound on them. */
function cassette(ctx, x, y, w, t, u) {
  const h = w * 0.62, r = w * 0.05;
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath(); B.roundRect(ctx, -w / 2, -h / 2, w, h, r);
  ctx.fillStyle = B.linear(ctx, -w / 2, -h / 2, w / 2, h / 2, [B.rgba(PAL.hot, 0.75), B.rgba(PAL.pink, 0.85), B.rgba("#c98bff", 0.8)]);
  ctx.fill();
  ctx.strokeStyle = PAL.plum; ctx.lineWidth = 0.35 * u; ctx.stroke();
  ctx.fillStyle = PAL.marble; ctx.fillRect(-w * 0.42, -h * 0.4, w * 0.84, h * 0.5); // label
  ctx.fillStyle = B.rgba(PAL.teal, 0.8); ctx.fillRect(-w * 0.42, -h * 0.4, w * 0.84, h * 0.08);
  B.texture(ctx, () => B.text(ctx, "SIDE A", -w * 0.36, -h * 0.25, { size: h * 0.08, family: UI, weight: 600, color: PAL.plum, align: "left" }));
  ctx.fillStyle = "#3a2440"; ctx.beginPath(); B.roundRect(ctx, -w * 0.28, -h * 0.17, w * 0.56, h * 0.22, h * 0.05); ctx.fill(); // reel window
  [[-0.17, 0.11], [0.17, 0.07]].forEach(([fx, tr], i) => {
    const rx = w * fx, ry = -h * 0.06;
    ctx.beginPath(); B.circle(ctx, rx, ry, w * tr); ctx.fillStyle = "#6b4a52"; ctx.fill(); // wound tape
    ctx.beginPath(); B.circle(ctx, rx, ry, w * 0.045); ctx.fillStyle = PAL.marble; ctx.fill();
    ctx.save(); ctx.translate(rx, ry); ctx.rotate(t * 1.6 * (i ? 1.4 : 1)); ctx.fillStyle = "#3a2440";
    for (let k = 0; k < 6; k++) { ctx.rotate(B.TAU / 6); ctx.fillRect(w * 0.02, -w * 0.006, w * 0.02, w * 0.012); }
    ctx.restore();
  });
  for (const fx of [-0.3, 0.3]) { ctx.beginPath(); B.circle(ctx, w * fx, h * 0.34, w * 0.025); ctx.fillStyle = "#3a2440"; ctx.fill(); }
  ctx.restore();
}
/**
 * The tape passing a head, seen up close. mode "rec": particles left of the head lie every which way, right of it they
 * line up in the pattern of the signal. mode "play": the whole tape carries the pattern and the head reads it out.
 * Tiny magnets are capsules: hot pink for one pole, cyan for the other, longer where the signal was stronger.
 */
function tapeHead(ctx, x, y, w, h, t, mode, u, lab) {
  const play = mode === "play", ty = y + h * 0.3, th = h * 0.12, hx = x + w * (play ? 0.36 : 0.52), sp = 3.4 * u, shift = (t * 5.5 * u) % sp;
  ctx.fillStyle = B.linear(ctx, 0, ty - th / 2, 0, ty + th / 2, ["#8a5b68", "#5a3644", "#7a4c5c"]);
  ctx.fillRect(x, ty - th / 2, w, th);
  const pat = (s) => Math.sin(s / (7 * u)) * 0.6 + Math.sin(s / (2.9 * u)) * 0.4;
  for (let px = x - sp + shift; px < x + w + sp; px += sp) {
    const s = px - t * 5.5 * u, on = play || px > hx, r = B.hash01(Math.round(s / sp), 7);
    const v = on ? pat(s) : 0, ang = on ? (v > 0 ? 0 : Math.PI) : r * B.TAU, len = on ? (1 + 1.6 * Math.abs(v)) * u : 1.4 * u;
    ctx.save(); ctx.translate(px, ty); ctx.rotate(ang);
    ctx.fillStyle = on ? (v > 0 ? PAL.hot : PAL.cyan) : B.rgba(PAL.marble, 0.55);
    ctx.beginPath(); B.capsule(ctx, -len / 2, -0.45 * u, len, 0.9 * u); ctx.fill();
    ctx.restore();
  }
  // the head: a ring-shaped core with a tiny gap at the top that touches the tape, a pink coil wound round its foot
  const cw = Math.min(w * 0.16, 16 * u), cy0 = ty + th / 2, R = cw * 0.42, ch = R * 2 + 2 * u, rcy = cy0 + R + 0.2 * u;
  ctx.lineWidth = cw * 0.2;
  ctx.strokeStyle = B.linear(ctx, hx - R, 0, hx + R, 0, ["#9a97ad", "#f2f0f8", "#7d7a92"]);
  ctx.beginPath(); ctx.arc(hx, rcy, R, -Math.PI / 2 + 0.12, Math.PI * 1.5 - 0.12); ctx.stroke();
  ctx.strokeStyle = PAL.hot; ctx.lineWidth = 0.45 * u;
  for (let i = 0; i < 6; i++) { const yy = rcy + R * 0.7 + i * 0.75 * u; ctx.beginPath(); ctx.ellipse(hx, yy, R * 0.75, 0.5 * u, 0, 0, B.TAU); ctx.stroke(); }
  const gl = 0.5 + 0.5 * Math.sin(t * 6); // the gap glows where the field leaks out
  B.glow(ctx, hx, cy0, 4 * u, play ? PAL.cyan : PAL.hot, 0.5 + 0.3 * gl);
  // the signal: a wave flowing into the coil (rec) or out of it to a speaker (play)
  const wy = y + h * 0.82, wx0 = play ? hx + cw * 0.7 : x + 3 * u, wx1 = play ? x + w * 0.78 : hx - cw * 0.7, pts = [];
  for (let i = 0; i <= 60; i++) { const xx = B.lerp(wx0, wx1, i / 60); pts.push([xx, wy + pat(xx - t * 9 * u) * h * 0.08]); }
  ctx.strokeStyle = PAL.hot; ctx.lineWidth = 0.7 * u;
  ctx.beginPath(); B.poly(ctx, pts, false); ctx.stroke();
  ctx.strokeStyle = B.rgba(PAL.plum, 0.6); ctx.lineWidth = 0.3 * u;
  ctx.beginPath(); ctx.moveTo(play ? wx0 : wx1, wy); ctx.lineTo(hx, wy); ctx.lineTo(hx, rcy + R * 0.7 + 4 * u); ctx.stroke();
  if (play) { // speaker with sound arcs
    const sx = x + w * 0.86;
    ctx.fillStyle = PAL.plum;
    ctx.beginPath(); B.poly(ctx, [[sx - 2 * u, wy - 1.6 * u], [sx, wy - 1.6 * u], [sx + 2.4 * u, wy - 3.6 * u], [sx + 2.4 * u, wy + 3.6 * u], [sx, wy + 1.6 * u], [sx - 2 * u, wy + 1.6 * u]], true); ctx.fill();
    for (let i = 0; i < 3; i++) { const q = B.fract(t * 0.8 + i / 3); ctx.strokeStyle = B.rgba(PAL.hot, 1 - q); ctx.lineWidth = 0.45 * u; ctx.beginPath(); ctx.arc(sx + 3 * u, wy, 2 * u + q * 5 * u, -0.8, 0.8); ctx.stroke(); }
  }
  return { hx, ty, th, cw, cy0, ch, wy };
}

// ---------------- beats
function titleBeat(ctx, t, L, a, e, close) {
  const u = L.u, P = L.P;
  win(ctx, L, L.title, close ? "tape_dream_end" : "tape_dream", t, a, e, (c, x, y, w, h) => {
    heading(c, close ? "Sound, saved\nas magnetism" : "How does a cassette\nstore sound?", x + w / 2, y + h * 0.42, P ? 8.6 * u : 7.4 * u, { maxW: w * 0.9, maxLines: 3 });
    ui(c, close ? "Read back at 4.76 cm a second" : "A slow dream in magnetic tape", x + w / 2, y + h * 0.83, L.lab, { maxW: w * 0.9, maxLines: 1, weight: 500 });
  });
  win(ctx, L, L.tape, "side_a", t, a + 0.35, e, (c, x, y, w, h) => cassette(c, x + w / 2, y + h / 2, Math.min(w * 0.82, h * 1.25), t, u));
}
function diagramBeat(ctx, t, L) {
  const a = BEATS[1], e = BEATS[2], u = L.u;
  win(ctx, L, L.diagram, "how_tape_works", t, a, e, (c, x, y, w, h) => {
    const g = tapeHead(c, x, y + h * 0.08, w, h * 0.84, t, "rec", u);
    const al = (k) => B.span(t, a + k, a + k + 0.4);
    ui(c, "Magnetic tape", x + 2.5 * u, g.ty + g.th / 2 + L.lab * 1.1, L.lab, { align: "left", maxLines: 1, alpha: al(0.8) });
    ui(c, "Tape head", g.hx + g.cw * 0.75, g.cy0 + g.ch * 0.62, L.lab, { align: "left", maxLines: 1, alpha: al(1.0) });
    ui(c, "Signal in", x + 2.5 * u, g.wy + L.lab * 1.6, L.lab, { align: "left", maxLines: 1, alpha: al(1.2) });
    const ay = g.ty - g.th / 2 - L.lab * 1.9, pts = [[x + w * 0.42, ay], [x + w - 4 * u, ay]];
    B.arrow(c, pts, { p: B.prog(t, a + 0.7, 0.8, "inOutSine"), width: 0.55 * u, head: 2.6 * u, color: PAL.hot, headStyle: "tri" });
    ui(c, "Tape moves", x + w * 0.42, ay - L.lab * 1.1, L.lab, { align: "left", maxLines: 1, alpha: al(1.1) });
    ui(c, "Lined up = sound stored", x + w - 2.5 * u, g.wy + L.lab * 0.3, L.lab, { align: "right", maxLines: 2, maxW: w * 0.4, alpha: al(1.4), color: PAL.hot });
  });
}
function numberBeat(ctx, t, L) {
  const a = BEATS[2], e = BEATS[3], u = L.u, P = L.P;
  win(ctx, L, L.speed, "tape_speed.txt", t, a, e, (c, x, y, w, h) => {
    ui(c, "Cassette tape runs at", x + w / 2, y + h * 0.14, L.lab, { maxLines: 1, weight: 500 });
    const k = B.prog(t, a + 0.55, 1.3, "outCubic"), land = t - (a + 1.85), s = land > 0 ? 1 + 0.06 * Math.exp(-5 * land) * Math.sin(land * 12) : 1;
    c.save(); c.translate(x + w / 2, y + h * 0.43); c.scale(s, s);
    heading(c, B.counter(k, 4.76, { decimals: 2 }), 0, 0, (P ? 21 : 15) * u, { maxLines: 1, italic: true });
    c.restore();
    ui(c, "centimetres every second", x + w / 2, y + h * 0.66, L.lab * 1.05, { maxLines: 1 });
    // the tape itself, sliding past a ruler at its real pace
    const ry = y + h * 0.85, cm = w / 12;
    c.fillStyle = "#6b4a52"; c.fillRect(x, ry - 1.1 * u, w, 2.2 * u);
    c.fillStyle = PAL.plum;
    for (let i = -1; i < 14; i++) { const px = x + i * cm + ((t * 4.76 * cm) % cm); c.fillRect(px, ry - 3 * u, Math.max(1.5, 0.25 * u), 1.6 * u); }
  });
  win(ctx, L, L.inch, "convert", t, a + 0.9, e, (c, x, y, w, h) => ui(c, "= 1.875 inches every second", x + w / 2, y + h / 2, L.lab, { maxLines: 1, maxW: w * 0.92 }));
}
function stepsBeat(ctx, t, L) {
  const a = BEATS[3], e = BEATS[4], u = L.u, P = L.P;
  const texts = ["Your sound becomes an electric signal", "The head turns that signal into magnetism", "Particles on the tape keep the pattern"];
  L.steps.forEach((b, i) => win(ctx, L, b, "step_" + (i + 1), t, a + i * 0.45, e, (c, x, y, w, h) => {
    const s = Math.min(h * 0.62, 13 * u), bx = x + 2.2 * u, by = y + (h - s) / 2;
    c.fillStyle = PAL.grey; c.fillRect(bx, by, s, s);
    bevel(c, bx, by, s, s, Math.max(1.5, 0.3 * u));
    heading(c, String(i + 1), bx + s / 2, by + s / 2, s * 0.7, { maxLines: 1 });
    ui(c, texts[i], bx + s + 2.4 * u, y + h / 2, L.lab * (P ? 1.05 : 1.08), { align: "left", maxW: w - s - 6 * u, maxLines: 2 });
  }));
}
function playBeat(ctx, t, L) {
  const a = BEATS[4], e = BEATS[5], u = L.u;
  win(ctx, L, L.play, "play_back", t, a, e, (c, x, y, w, h) => {
    const g = tapeHead(c, x, y + h * 0.1, w, h * 0.66, t, "play", u);
    ui(c, "Head reads the pattern", g.hx - g.cw * 0.2, y + h * 0.07, L.lab, { align: "left", maxLines: 1, maxW: w * 0.6 });
    const bw = 15 * u, bh = 8 * u, bx = x + 2.5 * u, by = y + h * 0.83, pr = Math.abs(t - (a + 0.6)) < 0.12;
    c.fillStyle = PAL.grey; c.fillRect(bx, by - bh / 2, bw, bh); // the PLAY button, pressed in once
    bevel(c, bx, by - bh / 2, bw, bh, Math.max(1.5, 0.3 * u), pr);
    c.fillStyle = PAL.hot; c.beginPath(); B.poly(c, [[bx + bw * 0.4, by - bh * 0.25], [bx + bw * 0.62, by], [bx + bw * 0.4, by + bh * 0.25]], true); c.fill();
    ui(c, "The moving pattern makes the signal again", bx + bw + 2.5 * u, by, L.lab, { align: "left", maxW: w - bw - 7 * u, maxLines: 2, alpha: B.span(t, a + 0.7, a + 1.1) });
  });
}

// ---------------- finishing: chromatic split + tape wobble, tracking band, scanlines, glitter
/**
 * VHS look in one pass: copy the frame, split it into a red copy and a cyan copy (multiply), then add them back in
 * horizontal strips, each shifted by a slow tape wobble, red a little left and cyan a little right.
 */
function vhs(ctx, W, H, t, u, glitch) {
  const src = B.scratch("vw-src", W, H); src.drawImage(ctx.canvas, 0, 0);
  const split = (key, col) => {
    const g = B.scratch(key, W, H); g.drawImage(src.canvas, 0, 0);
    g.globalCompositeOperation = "multiply"; g.fillStyle = col; g.fillRect(0, 0, W, H);
    return g.canvas;
  };
  const red = split("vw-red", "#ff0000"), cyn = split("vw-cyn", "#00ffff");
  ctx.save();
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
  ctx.globalCompositeOperation = "lighter";
  const n = 30, sh = H / n, d = (0.28 + 1.2 * glitch) * u;
  for (let i = 0; i < n; i++) {
    const y = i * sh, wob = (Math.sin(i * 0.5 + t * 1.3) * 0.18 + B.noise1(t * 3 + i * 0.4, 5) * (0.12 + 1.5 * glitch)) * u;
    ctx.drawImage(red, 0, y, W, sh, wob - d, y, W, sh);
    ctx.drawImage(cyn, 0, y, W, sh, wob + d, y, W, sh);
  }
  ctx.restore();
}
/** A VHS tracking band: a soft bright bar of broken white lines that rolls down the frame now and then. */
function tracking(ctx, W, H, t, u, y, amt) {
  if (amt <= 0) return;
  const r = B.rng("trk" + Math.floor(t * 24)), bh = H * 0.05;
  ctx.save();
  ctx.fillStyle = B.linear(ctx, 0, y - bh, 0, y + bh, [B.rgba("#ffffff", 0), B.rgba("#ffffff", 0.18 * amt), B.rgba("#ffffff", 0)]);
  ctx.fillRect(0, y - bh, W, 2 * bh);
  ctx.fillStyle = B.rgba("#ffffff", 0.7 * amt);
  for (let i = 0; i < 14; i++) ctx.fillRect(r() * W - W * 0.2, y + r.range(-bh, bh), r.range(0.1, 0.5) * W, r.range(0.15, 0.4) * u);
  ctx.restore();
}
function glitter(ctx, W, H, t, u, n) {
  const r = B.rng("vw-glitter");
  for (let i = 0; i < n; i++) {
    const x = r() * W, y = r() * H * 0.95, per = r.range(1.8, 3.6), ph = r(), s = r.range(0.8, 2.2) * u;
    const tw = Math.pow(Math.max(0, Math.sin(B.TAU * (t / per + ph))), 4);
    if (tw < 0.03) continue;
    ctx.beginPath(); B.sparkle(ctx, x, y, s * tw, 0.12);
    ctx.fillStyle = i % 3 ? "#ffffff" : PAL.sun; ctx.fill();
  }
}

function draw(ctx, W, H, t) {
  const L = layout(W, H), u = L.u;
  MIN = 3.9 * u;
  world(ctx, W, H, L, t);
  // 夢 ("dream") floats in the sky on the title and the close
  const ka = Math.max(B.span(t, 0.6, 1.4) * (1 - B.span(t, 2.0, 2.3)), B.span(t, 11.4, 12.2));
  if (ka > 0) {
    const [kx, ky, ks] = L.kanji;
    ctx.save();
    ctx.globalAlpha = ka * 0.92;
    ctx.font = `600 ${ks}px "${JP}", "Yu Mincho", "Hiragino Mincho ProN", serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = PAL.hot; ctx.fillText("夢", kx + ks * 0.05, ky + B.bob(t, u * 0.6, 5) + ks * 0.05);
    ctx.fillStyle = "#ffffff"; ctx.fillText("夢", kx, ky + B.bob(t, u * 0.6, 5));
    ctx.restore();
  }
  titleBeat(ctx, t, L, 0.1, BEATS[1], false);
  diagramBeat(ctx, t, L);
  numberBeat(ctx, t, L);
  stepsBeat(ctx, t, L);
  playBeat(ctx, t, L);
  titleBeat(ctx, t, L, BEATS[5] + 0.05, DUR + 1, true);
  glitter(ctx, W, H, t, u, L.P ? 26 : 22);
  // scanline wipe at each beat change: a tracking band sweeps down while the windows swap
  let glitch = 0, ty = -H, amt = 0;
  for (const at of BEATS.slice(1)) {
    const p = B.span(t, at - 0.35, at + 0.35);
    if (p > 0 && p < 1) { glitch = Math.sin(p * Math.PI); ty = B.lerp(-H * 0.1, H * 1.1, p); amt = glitch; }
  }
  if (amt === 0) { const p = B.fract(t / 6.5); ty = B.lerp(H * 1.1, -H * 0.1, p); amt = 0.35; } // the idle roll
  vhs(ctx, W, H, t, u, glitch * 0.8);
  tracking(ctx, W, H, t, u, ty, amt);
  B.scanlines(ctx, W, H, { gap: Math.max(3, Math.round(0.45 * u)), alpha: 0.1 });
  B.vignette(ctx, W, H, { amount: 0.3, inner: 0.55, color: PAL.plum });
  B.grain(ctx, W, H, { amount: 0.05, t, fps: 15 });
}

// ---------------- sound: detuned slow electric piano with tape wow, reverb-washed snaps, hiss, a mellow bed
SOUND.define("vw-ep", (v, o) => {
  const f = v.hz(o.note || "A4"), len = o.dur ?? 2.6, end = v.t + len + 0.2;
  const a = v.tone({ f, a: 0.012, len, peak: 0.13 }), b = v.tone({ f: f * 1.005, a: 0.015, len: len * 0.9, peak: 0.09 });
  v.tone({ type: "triangle", f: f * 2.002, a: 0.006, len: 0.7, peak: 0.03 });
  [a, b].forEach((x) => v.lfo(x.osc.frequency, 0.5, f * 0.006, end)); // tape wow: the pitch sags and swells
}, { verb: 0.6 });
SOUND.define("vw-hiss", (v) => {
  const d = v.dur ?? 8, g = v.bedGain(d, 0.05, 1);
  v.noise({ filter: "highpass", f: 4200, a: 0.4, hold: Math.max(0, d - 0.8), len: 0.4, peak: 0.5, dest: g });
}, { bed: true, verb: 0 });
SOUND.define("vw-pop", (v) => { // a window opening: a soft slowed-down blip
  v.tone({ f: 440, f2: 660, glide: 0.18, a: 0.01, len: 0.35, peak: 0.16 });
  v.tone({ type: "triangle", f: 880, f2: 1320, glide: 0.18, a: 0.01, len: 0.2, peak: 0.03 });
}, { verb: 0.55 });

function score(k) {
  k.bed("pad", 0, DUR, { notes: ["F2", "C3", "E3", "A3"], gain: 0.55, bright: 520 });
  k.bed("vw-hiss", 0, DUR);
  const chords = [["F3", "A3", "C4", "E4"], ["E3", "G3", "B3", "D4"], ["D3", "F3", "A3", "C4", "E4"], ["C3", "E3", "G3", "B3"], ["F3", "A3", "C4", "E4"], ["A#2", "D3", "F3", "A3"]];
  BEATS.forEach((at, i) => k.chord(at + 0.05, chords[i], { voice: "vw-ep", strum: 0.07, dur: i === 5 ? 2.0 : 2.6 }));
  for (let at = 0.86; at < DUR - 0.5; at += 1.72) k.at(at, "snap", { verb: 0.9, gain: 0.45 }); // slow beats 2 and 4
  for (let at = 0; at < DUR - 0.5; at += 1.72) k.at(at, "thud", { gain: 0.35, pitch: -5 });
  [0.4, 0.75, 2.6, 5.1, 6.0, 7.5, 7.95, 8.4, 9.7, 11.35, 11.7].forEach((at, i) => k.at(at, "vw-pop", { pitch: [0, 3, 5, 7, 2, 0, 3, 7, 5, 0, 3][i] }));
  BEATS.slice(1).forEach((at) => k.at(at - 0.3, "static", { gain: 0.25, dur: 0.6 }).at(at - 0.2, "swish", { gain: 0.3 }));
  k.seq(3.2, 0.3, ["C5", "E5", "G5", "B5"], { voice: "vw-ep", gain: 0.6, dur: 1.2 });
  k.at(6.65, "chime", { note: "E6", gain: 0.45 }).at(6.65, "vw-ep", { note: "C5", dur: 2 });
  k.at(10.0, "click", { gain: 0.6 }).at(10.05, "sparkle", { gain: 0.35 });
  k.at(11.1, "sparkle", { gain: 0.4 }).at(12.0, "vw-ep", { note: "A5", dur: 1.0, gain: 0.7 });
}

Player.register({
  id: "vaporwave", name: "Vaporwave", duration: DUR,
  fonts: {
    href: "https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Chakra+Petch:wght@500;600&family=Noto+Serif+JP:wght@600&display=swap",
    faces: ['400 20px "DM Serif Display"', 'italic 400 20px "DM Serif Display"', '600 20px "Chakra Petch"', '500 20px "Chakra Petch"', '600 20px "Noto Serif JP"'],
  },
  beats: BEATS,
  beatNames: ["Title", "Diagram", "Key number: 4.76 cm/s", "Three steps", "Play back", "Close"],
  stills: [1.6, 4.0, 6.6, 8.9, 10.6, 12.6],
  draw, score,
});
})();
