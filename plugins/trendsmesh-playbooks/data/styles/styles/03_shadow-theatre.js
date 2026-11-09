/* 03 Shadow Theatre - reference animation.
 * Topic (setting, replace it): "How does a lever lift a heavy stone?" - effort arm, pivot and load.
 * Rendering (keep it): a cloth screen lit warm from behind by one flickering lamp; near-black cut-outs in strict
 * profile with punched lace and jewel gels; limbs on rivets; soft control rods; hanging plaques with punched serif
 * letters; vine arrows; gels over the lamp for wrong and right; a lace valance and drapes framing the stage.
 * Finishing: cloth weave, a light-bleed in screen mode, coarse 12 fps grain, a strong warm vignette.
 */
(function () {
"use strict"; const B = window.Brush;

// ---- palette and type (from the card)
const PAL = { core: "#ffd27a", amber: "#e79a3e", edge: "#6e2a14", ink: "#140806", teal: "#2fa39a", ruby: "#c22a3a", gold: "#f2c14e" };
const SERIF = "Cinzel", BOOK = "Spectral";
const DUR = 14, BEATS = [0, 2.3, 4.8, 7.0, 8.7, 12.1];
let T = 0, K = 1, G = 0, CX = 0, U = 1, WW = 0, HH = 0; // time, stage unit, ground y, stage centre x, frame unit, W, H

// ---- cut-out helpers (reuse these)
const S = (x, y) => [CX + x * K, G + y * K]; // stage units -> px (y up is negative)
function card(g, pathFn) {
  g.beginPath(); pathFn(g); g.fillStyle = PAL.ink; g.fill();
}
/** Punch holes: the screen light shows through. */
function punch(g, pathFn) {
  g.save(); g.globalCompositeOperation = "destination-out"; g.beginPath(); pathFn(g); g.fill(); g.restore();
}
/** A coloured gel behind a piece's holes. */
function gel(g, pieceFn, color, fillFn) {
  g.save(); g.beginPath(); pieceFn(g); g.clip(); g.globalCompositeOperation = "destination-over"; g.fillStyle = color;
  g.beginPath(); fillFn(g); g.fill(); g.restore();
}
function rivet(g, x, y, r) {
  g.save(); g.globalCompositeOperation = "destination-out"; g.lineWidth = r * 0.42; g.beginPath();
  g.arc(x, y, r, 0, B.TAU); g.stroke(); g.restore();
}
const limb = (a, b, w) => (g) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, nx = (-dy / l) * w * 0.5, ny = (dx / l) * w * 0.5;
  g.moveTo(a[0] + nx, a[1] + ny); g.lineTo(b[0] + nx, b[1] + ny);
  g.arc(b[0], b[1], w / 2, Math.atan2(ny, nx), Math.atan2(ny, nx) + Math.PI, true); g.lineTo(a[0] - nx, a[1] - ny);
  g.arc(a[0], a[1], w / 2, Math.atan2(-ny, -nx), Math.atan2(-ny, -nx) + Math.PI, true); g.closePath();
};
/** Punched dots along a polyline (lace), every gap px. */
function laceDots(pts, gap, r) {
  return (g) => {
    const L = B.pathLength(pts), n = Math.max(1, Math.floor(L / gap)); for (let i = 0; i <= n; i++) {
      const q = B.pointAt(pts, i / n); g.moveTo(q[0] + r, q[1]); g.arc(q[0], q[1], r, 0, B.TAU);
    }
  };
}
function teardrop(g, x, y, r, a) {
  const ca = Math.cos(a), sa = Math.sin(a), P = (px, py) => [x + px * ca - py * sa, y + px * sa + py * ca];
  const tip = P(r * 2.2, 0); g.moveTo(...tip);
  const c1 = P(r * 0.9, -r * 1.1), c2 = P(-r, -r), e = P(-r, 0), c3 = P(-r, r), c4 = P(r * 0.9, r * 1.1);
  g.bezierCurveTo(c1[0], c1[1], c2[0], c2[1], e[0], e[1]); g.bezierCurveTo(c3[0], c3[1], c4[0], c4[1], tip[0], tip[1]);
  g.closePath();
}
/** Two-bone IK; bend +1 / -1 picks the elbow side. */
function ik(root, target, a, b, bend) {
  const dx = target[0] - root[0], dy = target[1] - root[1];
  const d = B.clamp(Math.hypot(dx, dy), Math.abs(a - b) + 1e-3, a + b - 1e-3), base = Math.atan2(dy, dx);
  const ang = base + bend * Math.acos(B.clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1));
  const j = [root[0] + Math.cos(ang) * a, root[1] + Math.sin(ang) * a];
  const ea = Math.atan2(target[1] - j[1], target[0] - j[0]);
  return [j, [j[0] + Math.cos(ea) * b, j[1] + Math.sin(ea) * b]];
}
/** Control rod down out of the frame, off the screen so soft. */
function rod(ctx, from, dx) {
  const to = [from[0] + dx, HH + 20]; [[1.3, 0.16], [0.75, 0.32], [0.32, 0.85]].forEach(([w, a]) => {
    ctx.strokeStyle = B.rgba(PAL.ink, a); ctx.lineWidth = Math.max(1, w * U); ctx.beginPath();
    ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); ctx.stroke();
  });
}
/** Hanging plaque with punched letters: drops in, bounces, sways, settles; pulled up at o.up. o.swing: [times] */
function plaque(g, o) {
  const dp = B.prog(T, o.at, 0.75); if (dp <= 0) return; const up = o.up ? B.prog(T, o.up, 0.55, "inBack") : 0;
  if (up >= 1) return; const pad = 1.6 * U, gap = 0.25;
  const ms = o.lines.map((l) => B.measureText(g, l.text, { size: l.size, family: l.font || SERIF, weight: l.weight ?? 700, maxW: o.w - 4 * pad, maxLines: 1, letterSpacing: l.track ?? 0.06, style: l.style || "" }));
  const R = o.w / 2, h = o.round ? o.w : ms.reduce((a, m) => a + m.size * (1 + gap), 0) + 2.4 * pad; // o.round: a disc
  const y = B.lerp(-h - 0.1 * HH, o.y, B.ease.outBack(dp, 1.3)) - up * (o.y + h + 0.15 * HH);
  let sway = 0.004 * Math.sin(T * 1.3 + (o.seed || 0)); const tau = T - o.at - 0.55;
  if (tau > 0) sway += 0.05 * Math.exp(-2.6 * tau) * Math.sin(7.2 * tau);
  for (const s of o.swing || []) if (T > s) sway += 0.045 * Math.exp(-3.5 * (T - s)) * Math.sin(9 * (T - s)); g.save();
  g.translate(o.x, 0); g.rotate(sway); g.translate(0, y); const w = o.w;
  g.strokeStyle = PAL.ink; g.lineWidth = Math.max(1, 0.16 * U); g.beginPath(); g.moveTo(-w * 0.36, o.round ? R * 0.31 : 2);
  g.lineTo(-w * 0.3, -y - 0.1 * HH); g.moveTo(w * 0.36, o.round ? R * 0.31 : 2); g.lineTo(w * 0.3, -y - 0.1 * HH); g.stroke();
  // the card: notched corners, a scalloped lower edge
  const shape = o.round ? (c) => B.circle(c, 0, R, R) : (c) => {
    const n = 1.2 * U; c.moveTo(-w / 2 + n, 0); c.lineTo(w / 2 - n, 0); c.lineTo(w / 2, n); c.lineTo(w / 2, h - n);
    const sc = Math.max(4, Math.round(w / (3.2 * U))); for (let i = 0; i < sc; i++) {
      const x0 = w / 2 - (i * w) / sc, x1 = w / 2 - ((i + 1) * w) / sc;
      c.quadraticCurveTo((x0 + x1) / 2, h + 1.1 * U, x1, h - (i === sc - 1 ? n : 0));
    }
    c.lineTo(-w / 2, n); c.closePath();
  };
  card(g, shape); punch(g, (c) => {
    const r = 0.32 * U, inset = 0.8 * U;
    if (o.round) { // a lace rim and a ring of punched rays round the number
      laceDots(B.arcPts(0, R, R * 0.92, 0, B.TAU, 60), 1.5 * U, r)(c);
      for (let i = 0; i < 24; i++) {
        const a = (i / 24) * B.TAU + T * 0.15, r1 = R * (i % 2 ? 0.78 : 0.88), r0 = R * 0.64, da = 0.06;
        c.moveTo(Math.cos(a - da) * r0, R + Math.sin(a - da) * r0); c.lineTo(Math.cos(a) * r1, R + Math.sin(a) * r1); c.lineTo(Math.cos(a + da) * r0, R + Math.sin(a + da) * r0); c.closePath();
      }
      return;
    }
    laceDots([[-w / 2 + inset * 1.6, inset], [w / 2 - inset * 1.6, inset]], 1.5 * U, r)(c);
    laceDots([[-w / 2 + inset * 1.6, h - inset * 1.4], [w / 2 - inset * 1.6, h - inset * 1.4]], 1.5 * U, r)(c);
  });
  let yy = o.round ? R - ms[0].size * 0.55 : 1.2 * pad; g.save(); g.globalCompositeOperation = "destination-out"; o.lines.forEach((l, i) => {
    const m = ms[i];
    B.text(g, l.text, 0, yy + m.size * 0.55, { size: m.size, family: l.font || SERIF, weight: l.weight ?? 700, color: "#000", style: l.style || "", letterSpacing: l.track ?? 0.06 });
    yy += m.size * (1 + gap);
  });
  g.restore(); if (o.gel) gel(g, shape, o.gel, (c) => c.rect(-w / 2, 0, w, h + 2 * U)); g.restore();
}
/** Vine growing along a path to p: leaves sprout as it passes, a spade head. */
function vine(g, pts, p, width) {
  if (p <= 0) return; const part = B.trim(pts, 0, p), L = B.pathLength(pts); if (part.length < 2) return; g.save();
  g.strokeStyle = PAL.ink; g.fillStyle = PAL.ink; g.lineWidth = width; g.lineCap = "round"; g.beginPath();
  B.poly(g, part); g.stroke(); const n = Math.floor((L * p) / (width * 6)); for (let i = 1; i <= n; i++) {
    const q = B.pointAt(pts, (i * width * 6) / L), side = i % 2 ? 1 : -1, s = B.clamp((L * p - i * width * 6) / (width * 6));
    const a = q[2] + side * 0.9, len = width * 3.2 * s; g.save(); g.translate(q[0], q[1]); g.rotate(a); g.beginPath();
    g.ellipse(len * 0.55, 0, len * 0.55, len * 0.24, 0, 0, B.TAU); g.fill(); g.restore();
  }
  const tip = B.pointAt(pts, p), hw = width * 3.2; g.translate(tip[0], tip[1]); g.rotate(tip[2]);
  g.beginPath(); // the spade head
  g.moveTo(hw * 0.9, 0); g.bezierCurveTo(hw * 0.2, -hw * 0.3, -hw * 0.6, -hw * 1.0, -hw * 0.75, -hw * 0.35);
  g.quadraticCurveTo(-hw * 0.8, 0, -hw * 0.4, 0); g.quadraticCurveTo(-hw * 0.8, 0, -hw * 0.75, hw * 0.35);
  g.bezierCurveTo(-hw * 0.6, hw * 1.0, hw * 0.2, hw * 0.3, hw * 0.9, 0); g.fill();
  g.globalCompositeOperation = "destination-out"; g.beginPath(); g.arc(-hw * 0.1, 0, hw * 0.16, 0, B.TAU); g.fill();
  g.restore();
}
// ---- subjects (the setting: replace these)
// The lever in stage units (ground 0, up negative); the plank's tip sits under the stone.
const LP = 36, FH = 7.5, STONE = [27, -8.7], SR = 9, TIP = [19.5, -1.1];
const FAR = TIP[0] - LP / 2, NEAR = TIP[0] - LP / 6; // pivot positions: equal arms, then 5 : 1
/** The lever's pose for a pivot x and a push angle. */
function lever(fx, push) {
  const A = [fx, -FH], dx = TIP[0] - fx, dy = TIP[1] + FH, rest = Math.atan2(dy, dx);
  const ang = rest - push, rTip = Math.hypot(dx, dy);
  const tip = [A[0] + Math.cos(ang) * rTip, A[1] + Math.sin(ang) * rTip], dir = [Math.cos(ang), Math.sin(ang)];
  const end = [tip[0] - dir[0] * LP, tip[1] - dir[1] * LP];
  return { A, tip, end, ang, lift: Math.max(0, TIP[1] - tip[1]) };
}
function drawLever(g, lv) {
  const a = S(...lv.end), b = S(...lv.tip), w = 1.5 * K; const plank = limb(a, b, w);
  const ap = S(...lv.A), base = 5.2 * K; const block = (c) => {
    c.moveTo(ap[0], ap[1] - 0.4 * K); c.lineTo(ap[0] + base * 0.55, G); c.lineTo(ap[0] - base * 0.55, G); c.closePath();
  };
  card(g, block); punch(g, (c) => {
    c.moveTo(ap[0] + 0.9 * K, G - 1.4 * K); c.arc(ap[0], G - 1.4 * K, 0.9 * K, 0, B.TAU);
  });
  gel(g, block, PAL.ruby, (c) => B.circle(c, ap[0], G - 1.4 * K, 1.0 * K)); card(g, plank);
  const inner = [B.pointAt([a, b], 0.04), B.pointAt([a, b], 0.9)].map((q) => [q[0], q[1]]);
  punch(g, laceDots(inner, 1.6 * K, 0.28 * K)); rivet(g, ap[0], ap[1], 0.6 * K);
}
function drawStone(g, lift, t) {
  const c = S(STONE[0], STONE[1] - lift), r = SR * K, pts = []; for (let i = 0; i < 22; i++) {
    const a = (i / 22) * B.TAU, k = 1 + 0.07 * Math.sin(a * 3 + 1) + 0.05 * Math.sin(a * 5 + 2);
    pts.push([c[0] + Math.cos(a) * r * k * 1.08, c[1] + Math.sin(a) * r * k * (Math.sin(a) > 0 ? 0.92 : 1)]);
  }
  const shape = (cc) => B.smoothPath(cc, pts, true); card(g, shape); punch(g, (cc) => {
    laceDots(B.arcPts(c[0], c[1], r * 0.74, 0, B.TAU, 40), 1.3 * K, 0.3 * K)(cc);
    for (let i = 0; i < 6; i++) teardrop(cc, c[0] + Math.cos((i / 6) * B.TAU + 0.3) * r * 0.5, c[1] + Math.sin((i / 6) * B.TAU + 0.3) * r * 0.5, 0.5 * K, (i / 6) * B.TAU + 0.3 + Math.PI);
    B.star(cc, c[0], c[1], 8, r * 0.26, r * 0.12, t * 0.2);
  });
  gel(g, shape, PAL.gold, (cc) => B.circle(cc, c[0], c[1], r * 0.32));
  gel(g, shape, PAL.teal, (cc) => B.circle(cc, c[0], c[1], r * 0.62)); return c;
}
/** The figure in strict profile: pinned pieces posed by IK; o.hang (0..1) lets the arms swing loose. */
function drawFigure(g, feet, hands, o) {
  const off = [o.dx || 0, o.dy || 0], P = (x, y) => { const q = S(x, y); return [q[0] + off[0], q[1] + off[1]]; };
  const hip = P(feet, -16 + (o.crouch || 0)), lean = o.lean || 0.12, torso = 12.5 * K;
  const sh = [hip[0] + Math.sin(lean) * torso, hip[1] - Math.cos(lean) * torso];
  const neck = [sh[0] + Math.sin(lean) * 1.6 * K, sh[1] - Math.cos(lean) * 1.6 * K];
  const head = [neck[0] + Math.sin(lean) * 3 * K, neck[1] - Math.cos(lean) * 3 * K];
  const fFront = P(feet + 3.5, 0), fBack = P(feet - 3.2, 0);
  const legA = ik(hip, [fBack[0], fBack[1] - 1.2 * K], 8.6 * K, 8.4 * K, -1), legB = ik(hip, [fFront[0], fFront[1] - 1.2 * K], 8.6 * K, 8.4 * K, -1);
  const hang = [sh[0] + Math.sin(o.swing || 0) * 15 * K, sh[1] + Math.cos(o.swing || 0) * 15 * K];
  const tgt = [B.lerp(hands[0], hang[0], o.hang || 0), B.lerp(hands[1], hang[1], o.hang || 0)];
  const armA = ik(sh, [tgt[0] - 0.8 * K, tgt[1] + 0.3 * K], 8 * K, 7.6 * K, 1), armB = ik(sh, tgt, 8 * K, 7.6 * K, 1);
  const foot = (k) => (c) => {
    c.moveTo(k[0] - 1.6 * K, k[1]); c.quadraticCurveTo(k[0] + 1 * K, k[1] - 2.2 * K, k[0] + 3.4 * K, k[1] - 0.2 * K);
    c.lineTo(k[0] + 3.4 * K, k[1]); c.closePath();
  };
  // back limbs first
  card(g, limb(hip, legA[0], 2.4 * K)); card(g, limb(legA[0], legA[1], 2.0 * K)); card(g, foot(legA[1]));
  card(g, limb(sh, armA[0], 1.9 * K)); card(g, limb(armA[0], armA[1], 1.6 * K));
  const nx = Math.cos(lean), ny = Math.sin(lean); const tunicPts = [
    [sh[0] - nx * 2.4 * K, sh[1] - ny * 2.4 * K], [sh[0] + nx * 2.6 * K, sh[1] + ny * 2.6 * K],
    [hip[0] + nx * 4.6 * K + 0.8 * K, hip[1] + 3.6 * K], [hip[0] - nx * 4.4 * K - 0.6 * K, hip[1] + 3.4 * K],
  ];
  const tunic = (c) => B.poly(c, tunicPts, true); card(g, tunic);
  const mid = [(sh[0] + hip[0]) / 2, (sh[1] + hip[1]) / 2]; punch(g, (c) => {
    laceDots([[tunicPts[3][0] + 0.9 * K, tunicPts[3][1] - 1 * K], [tunicPts[2][0] - 0.9 * K, tunicPts[2][1] - 1 * K]], 1.15 * K, 0.3 * K)(c);
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 2; j++) {
        const x = mid[0] + (j - 0.5) * 1.9 * K + (i - 1) * Math.sin(lean) * 2 * K, y = mid[1] + (i - 1) * 2.2 * K;
        c.moveTo(x, y - 0.8 * K); c.lineTo(x + 0.45 * K, y); c.lineTo(x, y + 0.8 * K); c.lineTo(x - 0.45 * K, y);
        c.closePath();
      }
    teardrop(c, sh[0] - nx * 0.4 * K + ny * 1.4 * K, sh[1] - ny * 0.4 * K + nx * 1.4 * K, 0.45 * K, Math.PI / 2 + lean);
  });
  gel(g, tunic, PAL.teal, (c) => c.rect(mid[0] - 2.6 * K, mid[1] - 3.6 * K, 5.2 * K, 7.2 * K));
  // head in profile: a nose, a cap, one punched eye, no drawn face
  const hd = (c) => {
    B.circle(c, head[0], head[1], 2.6 * K); c.moveTo(head[0] + 2.3 * K, head[1] - 0.3 * K);
    c.lineTo(head[0] + 3.4 * K, head[1] + 0.5 * K); c.lineTo(head[0] + 2.2 * K, head[1] + 0.9 * K); c.closePath();
    c.moveTo(head[0] - 3 * K, head[1] - 1.2 * K);
    c.quadraticCurveTo(head[0] - 1 * K, head[1] - 5.6 * K, head[0] + 2.8 * K, head[1] - 1.5 * K); c.closePath();
  };
  card(g, hd); card(g, limb(neck, sh, 1.8 * K)); punch(g, (c) => {
    c.ellipse(head[0] + 1.2 * K, head[1] - 0.2 * K, 0.42 * K, 0.22 * K, 0, 0, B.TAU);
    laceDots([[head[0] - 2.2 * K, head[1] - 1.9 * K], [head[0] + 1.6 * K, head[1] - 2.3 * K]], 0.9 * K, 0.22 * K)(c);
  });
  // front limbs
  card(g, limb(hip, legB[0], 2.4 * K)); card(g, limb(legB[0], legB[1], 2.0 * K)); card(g, foot(legB[1]));
  card(g, limb(sh, armB[0], 1.9 * K)); card(g, limb(armB[0], armB[1], 1.6 * K));
  card(g, (c) => B.circle(c, armB[1][0], armB[1][1], 1.05 * K));
  [hip, legB[0], sh, armB[0]].forEach((j) => rivet(g, j[0], j[1], 0.5 * K)); return { hand: armB[1], body: mid };
}
/** The stage floor: grass lace on top, a punched lace frieze below. */
function floor(g) {
  const top = (c) => {
    c.moveTo(-10, HH + 10); c.lineTo(-10, G); const n = Math.ceil(WW / (2.2 * K)); for (let i = 0; i <= n; i++) {
      const x = (i / n) * (WW + 20) - 10, h = (0.9 + 0.8 * B.hash01(i, "grass")) * K; c.lineTo(x - 0.5 * K, G);
      c.lineTo(x + 0.3 * K, G - h); c.lineTo(x + 0.8 * K, G);
    }
    c.lineTo(WW + 10, HH + 10); c.closePath();
  };
  card(g, top); punch(g, (c) => {
    for (let y = G + 2.2 * K, r = 0; y < HH + K; y += 4.6 * K, r++) {
      laceDots([[(r % 2) * 1.2 * K, y], [WW, y]], 2.4 * K, (r ? 0.5 : 0.42) * K)(c);
      for (let i = 0; i < Math.ceil(WW / (4.8 * K)); i++) teardrop(c, i * 4.8 * K + (r % 2 ? 3.6 : 1.2) * K, y + 2.4 * K, (r ? 0.6 : 0.45) * K, r % 2 ? Math.PI / 2 : -Math.PI / 2);
    }
  });
}
/** The title's turning lace rosette. */
function medallion(g, x, y, R, rot, s) {
  if (s <= 0.01) return; R *= s; const disc = (c) => {
    for (let i = 0; i < 16; i++) {
      const a = rot + (i / 16) * B.TAU, r = i % 2 ? R : R * 0.9;
      i ? c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r) : c.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
    }
    c.closePath();
  };
  card(g, disc); punch(g, (c) => {
    for (let i = 0; i < 8; i++) teardrop(c, x + Math.cos(rot + (i / 8) * B.TAU) * R * 0.55, y + Math.sin(rot + (i / 8) * B.TAU) * R * 0.55, R * 0.09, rot + (i / 8) * B.TAU + Math.PI);
    laceDots(B.arcPts(x, y, R * 0.8, 0, B.TAU, 48), R * 0.11, R * 0.035)(c); B.star(c, x, y, 8, R * 0.3, R * 0.14, rot);
  });
  gel(g, disc, PAL.ruby, (c) => B.circle(c, x, y, R * 0.66));
  gel(g, disc, PAL.gold, (c) => B.circle(c, x, y, R * 0.34));
}
/** The valance across the top (the plaques hang from behind it). */
function valance(g, h) {
  const n = Math.max(6, Math.round(WW / (9 * U))), shape = (c) => {
    c.moveTo(-10, -10); c.lineTo(WW + 10, -10); c.lineTo(WW + 10, h);
    for (let i = n; i > 0; i--) c.quadraticCurveTo(((i - 0.5) / n) * WW, h + 3.2 * U, ((i - 1) / n) * WW, h);
    c.closePath();
  };
  card(g, shape); punch(g, (c) => {
    laceDots([[0, h - 1.4 * U], [WW, h - 1.4 * U]], 1.6 * U, 0.38 * U)(c); for (let i = 0; i < n; i++) {
      const x = ((i + 0.5) / n) * WW; teardrop(c, x, h + 0.6 * U, 0.6 * U, Math.PI / 2);
      if (h > 12 * U) for (let k = 0; k < 6; k++) teardrop(c, x + Math.cos((k / 6) * B.TAU) * 2.2 * U, h * 0.55 + Math.sin((k / 6) * B.TAU) * 2.2 * U, 0.5 * U, (k / 6) * B.TAU);
    }
    if (h > 12 * U) laceDots([[0, h * 0.25], [WW, h * 0.25]], 2.2 * U, 0.45 * U)(c);
  });
  if (h > 12 * U) gel(g, shape, PAL.ruby, (c) => { for (let i = 0; i < n; i++) B.circle(c, ((i + 0.5) / n) * WW, h * 0.55, 1.2 * U); });
}
/** Lace drape with its inner edge at x; side -1 = left. */
function drape(g, x, side) {
  const shape = (c) => {
    const outer = side < 0 ? -20 : WW + 20; c.moveTo(outer, -20); c.lineTo(x, -20); const n = 14;
    for (let i = 0; i < n; i++) {
      const y0 = (i / n) * (HH + 40) - 20, y1 = ((i + 1) / n) * (HH + 40) - 20;
      c.quadraticCurveTo(x - side * 2.2 * U, (y0 + y1) / 2, x, y1);
    }
    c.lineTo(outer, HH + 20); c.closePath();
  };
  card(g, shape); punch(g, (c) => {
    for (let col = 1; col <= 3; col++) {
      const xx = x + side * col * 7 * U; laceDots([[xx, 0], [xx, HH]], 3.4 * U, 0.55 * U)(c);
      for (let i = 0; i < 12; i++) teardrop(c, xx + side * 3.5 * U, ((i + 0.5) / 12) * HH, 0.7 * U, Math.PI / 2);
    }
  });
  gel(g, shape, PAL.ruby, (c) => c.rect(x + side * 8 * U - 3 * U, 0, 6 * U, HH));
}

// ---- the screen, the lamp and the cloth
function lampBright(t) {
  // the oil lamp catches (sputters, rises), then breathes and flickers; it flares on key moments
  const catchUp = B.span(t, 0.1, 0.75, "outCubic") * (t < 0.75 ? 0.75 + 0.25 * B.hash01("sput", Math.floor(t * 18)) : 1);
  const breathe = 1 + 0.035 * B.noise1(t * 1.7, 3) + 0.03 * (B.hash01("flk", Math.floor(t * 12)) - 0.5);
  const flare = [[6.05, 0.3], [11.3, 0.35], [12.7, 0.25]].reduce((a, [at, amt]) => a + amt * Math.exp(-Math.pow((t - at - 0.25) / 0.35, 2)), 0);
  return (0.06 + 0.94 * catchUp) * breathe + flare;
}
function screen(ctx, W, H, L, b, tint) {
  const D = Math.hypot(W, H) * (0.62 + 0.06 * (b - 1));
  const tone = (c) => (b <= 1 ? B.mix(c, "#000000", 1 - b) : B.mix(c, "#fff3cf", Math.min(0.6, (b - 1) * 0.8)));
  ctx.fillStyle = B.radial(ctx, L.lamp[0], L.lamp[1], 0, D, [[0, tone(PAL.core)], [0.2, tone(B.mix(PAL.core, PAL.amber, 0.45))], [0.48, tone(PAL.amber)], [0.8, tone(B.mix(PAL.amber, PAL.edge, 0.7))], [1, tone(PAL.edge)]]);
  ctx.fillRect(0, 0, W, H);
  // gels over the lamp: red for wrong, gold for right
  if (tint.red > 0) B.with(ctx, () => {
    ctx.globalCompositeOperation = "multiply"; ctx.globalAlpha = tint.red; ctx.fillStyle = "#ff3b32";
    ctx.fillRect(0, 0, W, H);
  });
  if (tint.gold > 0) B.with(ctx, () => {
    ctx.globalCompositeOperation = "multiply"; ctx.globalAlpha = tint.gold * 0.6; ctx.fillStyle = "#ffcf4a";
    ctx.fillRect(0, 0, W, H); ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = tint.gold * 0.22;
    ctx.fillStyle = B.radial(ctx, L.lamp[0], L.lamp[1], 0, D * 0.6, ["#ffd27a", "rgba(255,210,122,0)"]);
    ctx.fillRect(0, 0, W, H);
  });
}
/** Cloth (cached, multiplied): thread weave, slubs, soft folds, a faint seam. */
function cloth(W, H) {
  return B.layer("st-cloth", W, H, (g, w, h) => {
    g.fillStyle = "#ffffff"; g.fillRect(0, 0, w, h);
    const u = Math.min(w, h) / 100, step = Math.max(3, Math.round(0.34 * u));
    const tile = B.canvas(step, step), tg = tile.getContext("2d"); tg.fillStyle = "#fff"; tg.fillRect(0, 0, step, step);
    tg.fillStyle = "rgba(60,30,10,0.55)"; tg.fillRect(0, 0, step, 1); tg.fillRect(0, 0, 1, step); g.globalAlpha = 0.14;
    g.fillStyle = g.createPattern(tile, "repeat"); g.fillRect(0, 0, w, h); const r = B.rng("slubs"); g.globalAlpha = 1;
    for (let i = 0; i < (w * h) / (u * u * 6); i++) {
      g.fillStyle = `rgba(70,35,10,${r.range(0.04, 0.1)})`;
      g.fillRect(r() * w, Math.round(r() * h / step) * step, r.range(1, 4) * u, Math.max(1, step * 0.5));
    }
    for (let x = 0; x < w; x += 2) {
      const v = B.fbm(x / (14 * u), 0.5, 3, 4) * 0.5 + 0.5; g.fillStyle = `rgba(60,25,8,${(0.1 * v * v).toFixed(3)})`;
      g.fillRect(x, 0, 2, h);
    }
    g.fillStyle = "rgba(60,25,8,0.12)"; // the seam
    g.fillRect(w * 0.64, 0, Math.max(1, 0.22 * u), h); g.fillStyle = "rgba(60,25,8,0.05)";
    g.fillRect(w * 0.64 + 0.5 * u, 0, Math.max(1, 0.5 * u), h);
  });
}

// ---- layout by aspect
function layout(W, H) {
  const F = B.frame(W, H), P = F.portrait;
  // portrait: the stage fills the width, framed by the valance and the floor; the step plaques hang just above it
  return { F, P, K: P ? W * 0.013 : Math.min(W * 0.94, H * 1.4) / 100, G: P ? 0.74 * H : 0.82 * H, CX: W * (P ? 0.44 : 0.5),
    lamp: P ? [W * 0.5, H * 0.4] : [W * 0.5, H * 0.26], plaqueW: P ? 0.88 * W : 0.44 * W, plaqueY: P ? 0.27 * H : 0.09 * H,
    big: P ? 7.6 * F.u : 6.8 * F.u, small: P ? 4.4 * F.u : 4.0 * F.u };
}

// ---- the play
function story(t) {
  const fx = t < 7.0 ? NEAR : t < 8.7 ? B.lerp(NEAR, FAR, B.span(t, 7.05, 7.55, "inOutSine")) : B.lerp(FAR, NEAR, B.span(t, 8.8, 9.4, "inOutSine"));
  let push = 0, strain = 0; if (t > 7.55 && t < 8.7) {
    push = 0.012 * B.span(t, 7.6, 7.9) * (1 - B.span(t, 8.3, 8.6)); // pushes hard: the stone barely shivers
    strain = B.span(t, 7.65, 7.85) * (1 - B.span(t, 8.3, 8.55));
  }
  if (t > 10.6) push = B.deg(44) * B.span(t, 10.8, 11.5, "inOutSine"); // the long arm goes down, the stone visibly rises
  const red = 0.42 * B.span(t, 7.95, 8.2) * (1 - B.span(t, 8.6, 8.95));
  const gold = 0.75 * B.span(t, 11.25, 11.5) * (1 - B.span(t, 11.9, 12.2)) + 0.5 * B.span(t, 12.6, 13.1);
  return { fx, push, strain, red, gold };
}

function draw(ctx, W, H, t) {
  T = t; const L = layout(W, H), F = L.F, P = L.P; K = L.K; G = L.G; CX = L.CX; U = F.u; WW = W; HH = H;
  const st = story(t), b = lampBright(t); screen(ctx, W, H, L, b, st); const g = B.scratch("st-puppets", W, H);

  // ---- title medallion and plaques
  const medS = B.span(t, 0.2, 0.9, "outBack") * (1 - B.span(t, 2.1, 2.5, "inBack"));
  medallion(g, L.lamp[0], P ? 0.5 * H : 0.6 * H, P ? 0.24 * W : 0.16 * H, t * 0.12, medS);
  // ---- the stage slides in on its sticks
  const inP = B.span(t, 2.15, 3.0, "outCubic"), hop = t > 2.15 && t < 3.0 ? Math.abs(Math.sin((t - 2.15) * 11)) * (1 - inP) * 3 * K : 0;
  const arrive = t - 3.0; floor(g); const lv = lever(st.fx, st.push); if (t > 2.15) {
    const sx = (1 - inP) * 0.7 * W; g.save(); g.translate(sx, -hop * 0.5); drawLever(g, lv); drawStone(g, lv.lift, t);
    g.restore();
  }
  let fig = null; if (t > 2.15) {
    const hands = S(...lv.end), eh = -lv.end[1]; const crouch = B.clamp((20 - eh) * 0.3, 0, 5.5) + st.strain * 0.8;
    const lean = 0.16 + B.clamp((20 - eh) * 0.022, 0, 0.32) + st.strain * 0.08;
    const shake = st.strain ? B.shake(t, 0.35 * K * st.strain, 7, 18) : [0, 0];
    const swing = arrive < 0 ? -0.6 * (1 - inP) : 0.5 * Math.exp(-3 * arrive) * Math.sin(arrive * 9);
    const hang = arrive < 0 ? 1 : 1 - B.span(arrive, 0.05, 0.45, "inOutSine");
    fig = drawFigure(g, lv.end[0] - 10, [hands[0], hands[1]], { crouch, lean, dx: -(1 - inP) * 0.6 * W + shake[0], dy: -hop + shake[1], hang, swing });
  }
  const pw = L.plaqueW, py = L.plaqueY, big = L.big, small = L.small, it = { font: BOOK, weight: 500, style: "italic", track: 0.01 };
  // the subtitle first, so its strings pass behind the title plaque
  plaque(g, { x: W / 2, y: P ? 0.3 * H : 0.33 * H, w: P ? 0.74 * W : 0.46 * W, lines: [{ text: "how a small push lifts a stone", size: small * 1.1, ...it }], at: 0.9, up: 2.05, seed: 2 });
  plaque(g, { x: W / 2, y: P ? 0.18 * H : 0.13 * H, w: P ? 0.84 * W : 0.56 * W, lines: [{ text: "THE LEVER", size: big * 1.5, weight: 900 }], gel: PAL.gold, at: 0.45, up: 2.0, seed: 1 });
  const lab = (text, x, y, at, seed, gelc) => plaque(g, { x, y, w: (P ? 6.2 : 6.8) * small, lines: [{ text, size: small }], gel: gelc, at, up: 4.6, seed });
  if (P) plaque(g, { x: W / 2, y: 0.2 * H, w: 0.8 * W, lines: [{ text: "THREE PARTS", size: big }], gel: PAL.gold, at: 2.6, up: 4.6, seed: 8 });
  if (t > 2.8 && t < 5.2) { // each label hangs clear of the plank and of the others; PIVOT glows with the bare lamp
    const st0 = S(STONE[0], STONE[1] - SR), ap = S(...lv.A), en = S(...lv.end);
    lab("LOAD", st0[0], st0[1] - (P ? 22 : 18) * K, 3.0, 3, PAL.gold);
    lab("PIVOT", ap[0], ap[1] - (P ? 21.5 : 17) * K, 3.25, 4);
    lab("EFFORT", en[0] + (P ? 8 : 3) * K, en[1] - (P ? 24 : 18) * K, 3.5, 5, PAL.teal);
    const vp = B.prog(t, 3.75, 0.7, "inOutSine") * (1 - B.span(t, 4.45, 4.65)), from = [en[0] + (P ? 11 : 6) * K, en[1] - (P ? 13 : 9) * K];
    vine(g, B.quad(from[0], from[1], from[0] + 4 * K, en[1] - 2 * K, en[0] + 1.5 * K, en[1] - 1.8 * K), vp, 0.55 * K);
  }
  // key number: a round counter with punched rays drops on its strings; digits swap 1 -> 5
  const nAt = 4.7, nUp = 6.8; if (t > nAt && t < nUp + 0.6) {
    const swaps = [5.3, 5.55, 5.8, 6.05], n = 1 + swaps.filter((s) => t >= s).length, R = P ? 0.2 * W : 0.2 * H;
    plaque(g, { x: P ? W / 2 : 0.62 * W, y: (P ? 0.28 : 0.27) * H - R, w: 2 * R, round: true, lines: [{ text: "×" + n, size: big * 2, weight: 900, track: 0.02 }], gel: PAL.gold, at: nAt, up: nUp, swing: swaps, seed: 6 });
    plaque(g, { x: P ? 0.64 * W : 0.2 * W, y: P ? 0.41 * H : 0.13 * H, w: P ? 0.56 * W : 0.3 * W, lines: [{ text: "an arm 5 times longer", size: small * 1.1, ...it }, { text: "lifts 5 times the weight", size: small * 1.1, ...it }], at: 6.15, up: nUp, seed: 7 });
  }
  const stepPlaque = (i, text, sub, at, up, gelc) => plaque(g, { x: W / 2, y: py, w: pw, lines: [{ text, size: big * (P ? 1 : 0.82) }, { text: sub, size: small * (P ? 1.15 : 1), ...it }], gel: gelc, at, up, seed: 10 + i });
  stepPlaque(1, "1 · PIVOT IN THE MIDDLE", "push hard: the stone won't budge", 7.05, 8.45);
  stepPlaque(2, "2 · SLIDE THE PIVOT CLOSE", "now one arm is 5 times longer", 8.5, 10.6);
  stepPlaque(3, "3 · PUSH DOWN", "pivot close: the stone rises", 10.65, 12.0, PAL.gold);
  // close
  plaque(g, { x: W / 2, y: P ? 0.27 * H : 0.1 * H, w: P ? 0.86 * W : 0.58 * W, lines: [{ text: "A LONG ARM", size: big * 1.15, weight: 900 }, { text: "MAKES LIGHT WORK", size: big * 1.0, weight: 900 }], gel: PAL.gold, at: 12.65, seed: 20 });
  valance(g, P ? 0.15 * H : 0.035 * H);
  // the drapes meet and part for the change into the close
  const dc = B.span(t, 11.95, 12.4, "inOutCubic") * (1 - B.span(t, 12.7, 13.3, "inOutCubic")); if (dc > 0) {
    drape(g, B.lerp(-6 * U, W / 2 + 1, dc), -1); drape(g, B.lerp(W + 6 * U, W / 2 - 1, dc), 1);
  }
  // light rays round the risen stone
  const c = S(STONE[0], STONE[1] - lv.lift), k = B.span(t, 11.25, 11.5) * (1 - B.span(t, 11.9, 12.2)) + B.span(t, 12.7, 13.1) * 0.6;
  if (k > 0) {
    ctx.save(); ctx.globalCompositeOperation = "screen"; ctx.lineWidth = 0.8 * K; ctx.lineCap = "round"; ctx.strokeStyle = B.rgba("#ffe7a6", 0.5 * k);
    for (let i = 0; i < 18; i++) {
      const a = (i / 18) * B.TAU + t * 0.1, r0 = SR * K * 1.25, r1 = SR * K * (i % 2 ? 1.9 : 2.5) * (0.8 + 0.2 * k);
      ctx.beginPath(); ctx.moveTo(c[0] + Math.cos(a) * r0, c[1] + Math.sin(a) * r0); ctx.lineTo(c[0] + Math.cos(a) * r1, c[1] + Math.sin(a) * r1); ctx.stroke();
    }
    ctx.restore();
  }
  ctx.drawImage(g.canvas, 0, 0);
  if (t > 2.15 && dc < 0.98) {
    ctx.save(); ctx.globalAlpha = 1 - dc; if (fig) {
      rod(ctx, fig.hand, -6 * K); rod(ctx, fig.body, -2 * K);
    }
    rod(ctx, [c[0] + (1 - inP) * 0.7 * W + 2 * K, c[1] + 4 * K], 9 * K); ctx.restore();
  }

  // ---- finishing: cloth, light bleed, grain, vignette
  ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.drawImage(cloth(W, H), 0, 0); ctx.restore();
  const dw = Math.ceil(W / 8), dh = Math.ceil(H / 8), dg = B.scratch("st-diffuse", dw, dh); dg.filter = "blur(2px)";
  dg.drawImage(ctx.canvas, 0, 0, dw, dh); dg.filter = "none"; ctx.save(); ctx.globalCompositeOperation = "screen";
  ctx.globalAlpha = 0.14; ctx.imageSmoothingQuality = "high"; ctx.drawImage(dg.canvas, 0, 0, W, H); ctx.restore();
  B.grain(ctx, W, H, { amount: 0.09, t, fps: 12, mode: "overlay", scale: Math.max(1.5, U / 5) });
  B.vignette(ctx, W, H, { color: "#1c0703", amount: 0.36 * (1.1 - 0.1 * Math.min(1.5, b)), inner: 0.38 });
}

// ---- sound: bronze, wood, the oil lamp, a gong
SOUND.define("st-bronze", (v, o) => { // struck bronze (gamelan-like): inharmonic partials, doubled a few Hz apart so they beat
  const f = SOUND.note(o.note ?? "D4") * v.rate, d = o.dur ?? 1.6;
  [[1, 0.2, d], [2.76, 0.07, d * 0.6], [5.1, 0.03, d * 0.3]].forEach(([m, pk, len]) => {
    v.tone({ f: f * m, a: 0.002, len, peak: pk, noPitch: true }); v.tone({ f: f * m + 3.2, a: 0.002, len, peak: pk * 0.8, noPitch: true });
  });
  v.noise({ filter: "bandpass", f: f * 3, q: 2, a: 0.0006, len: 0.025, peak: 0.06 });
}, { verb: 0.4 });
SOUND.define("st-clack", (v) => { // wooden rod / joint
  v.tone({ type: "triangle", f: 980, f2: 760, glide: 0.04, a: 0.0006, len: 0.05, peak: 0.28 }); v.noise({ filter: "bandpass", f: 1800, q: 3, a: 0.0005, len: 0.03, peak: 0.18 });
}, { verb: 0.15 });
SOUND.define("st-lamp", (v) => { // an oil lamp catching: a soft whump, then a sputter
  v.noise({ brown: true, filter: "lowpass", f: 180, f2: 600, glide: 0.25, a: 0.03, len: 0.45, peak: 0.45 }); v.tone({ f: 70, f2: 48, glide: 0.3, a: 0.01, len: 0.35, peak: 0.25 });
  for (let i = 0; i < 7; i++) v.noise({ at: 0.15 + v.rng() * 0.6, filter: "bandpass", f: 900 + v.rng() * 1500, q: 1, a: 0.001, len: 0.02 + v.rng() * 0.03, peak: 0.12 });
}, { verb: 0.2 });
SOUND.define("st-flame", (v, o) => { // a low steady flame: breathy brown noise with a slow wobble, rare crackles
  const d = v.dur ?? 8, g = v.bedGain(d, 0.5, o.fade ?? 1), src = v.ac.createBufferSource(), lp = v.ac.createBiquadFilter();
  src.buffer = v.noiseBufs.brown; src.loop = true; lp.type = "lowpass"; lp.frequency.value = 240; src.connect(lp); lp.connect(g);
  v.lfo(lp.frequency, 0.4, 70, v.t + d + 0.1); src.start(v.t); src.stop(v.t + d + 0.1);
  for (let at = 0.4; at < d - 0.2; at += 0.25 + v.rng() * 0.9) v.noise({ at, filter: "highpass", f: 1800 + v.rng() * 2500, a: 0.0004, len: 0.006 + v.rng() * 0.01, peak: 0.05 + v.rng() * 0.08 });
}, { bed: true, verb: 0.1 });

function score(k) {
  k.bed("st-flame", 0, DUR, { gain: 0.9 }).at(0.1, "st-lamp", { gain: 0.9 });
  k.at(0.3, "st-bronze", { note: "D4", gain: 0.6 }).at(0.55, "st-clack", { gain: 0.6 }).at(0.6, "st-bronze", { note: "A4", gain: 0.5 });
  k.at(1.0, "st-clack", { gain: 0.5, pitch: 3 }).at(1.05, "st-bronze", { note: "F4", gain: 0.4 }).at(2.0, "swish", { dur: 0.4, gain: 0.5 }).at(2.05, "swish", { dur: 0.35, gain: 0.4 });
  k.repeat(2.2, 0.28, 3, "st-clack", { gain: 0.6, vary: 2 }).at(2.2, "whoosh", { dur: 0.7, gain: 0.35, pan: -0.4 }).at(2.25, "whoosh", { dur: 0.7, gain: 0.3, pan: 0.4 });
  k.at(3.0, "knock", { gain: 0.5 }).repeat(3.05, 0.09, 3, "tick", { gain: 0.35 });
  ["A4", "C5", "D5"].forEach((note, i) => k.at(3.4 + i * 0.25, "st-bronze", { note, gain: 0.45, pan: [0.4, 0, -0.3][i] }).at(3.38 + i * 0.25, "st-clack", { gain: 0.35 }));
  k.at(3.75, "rustle", { dur: 0.6, gain: 0.5 }).at(4.6, "swish", { dur: 0.4, gain: 0.5 }).at(5.1, "st-clack", { gain: 0.6 });
  [5.3, 5.55, 5.8, 6.05].forEach((t0, i) => k.at(t0, "st-clack", { pitch: i * 2, gain: 0.6 }).repeat(t0 + 0.03, 0.03, 3, "tick", { gain: 0.25 }));
  k.at(6.1, "gong", { note: "D2", gain: 0.8 }).at(6.12, "st-bronze", { note: "D5", gain: 0.5, dur: 2.2 }).at(6.15, "st-bronze", { note: "A4", gain: 0.4, dur: 2.2 }).at(6.8, "swish", { dur: 0.45, gain: 0.5 });
  // step 1 is wrong (red gel): a sour bronze cluster; step 2 slides the pivot back
  k.at(7.05, "st-clack").at(7.1, "rustle", { dur: 0.5, gain: 0.4 }).at(7.55, "st-clack", { pitch: -2 }).repeat(7.65, 0.11, 6, "knock", { gain: 0.25, vary: 1.5 });
  k.at(7.95, "st-bronze", { note: "D4", gain: 0.55 }).at(7.96, "st-bronze", { note: "Eb4", gain: 0.5 }).at(8.0, "boom", { dur: 0.8, gain: 0.35 });
  k.at(8.6, "st-clack").at(8.85, "rustle", { dur: 0.6, gain: 0.4 }).at(9.4, "st-clack", { pitch: 2 });
  k.repeat(10.8, 0.12, 6, "st-clack", { gain: 0.35, vary: 1 }).seq(10.8, 0.13, ["D4", "F4", "G4", "A4", "C5"], { voice: "st-bronze", gain: 0.4 });
  k.at(11.35, "st-bronze", { note: "D5", gain: 0.6, dur: 2 }).at(11.37, "st-bronze", { note: "A5", gain: 0.4, dur: 2 }).at(11.35, "sparkle", { gain: 0.25 }).at(11.3, "st-lamp", { gain: 0.35 });
  k.at(11.9, "whoosh", { dur: 0.55, gain: 0.5, pan: -0.3 }).at(11.95, "rustle", { dur: 0.5, gain: 0.5 }).at(12.65, "whoosh", { dur: 0.65, gain: 0.45, pan: 0.3 }).at(12.7, "rustle", { dur: 0.6, gain: 0.45 });
  k.at(13.0, "st-clack", { gain: 0.5 }).at(13.05, "gong", { note: "D2", gain: 0.6 }).at(13.1, "st-bronze", { note: "D5", gain: 0.45, dur: 2 }).at(13.15, "st-bronze", { note: "F5", gain: 0.35, dur: 2 }).at(13.2, "st-bronze", { note: "A4", gain: 0.35, dur: 2 });
}

Player.register({
  id: "shadow-theatre", name: "Shadow Theatre", duration: DUR,
  fonts: {
    href: "https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Spectral:ital,wght@0,500;1,500&display=swap",
    faces: ['700 20px "Cinzel"', '900 20px "Cinzel"', '500 20px "Spectral"', 'italic 500 20px "Spectral"'],
  },
  beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Step 1 (wrong)", "Steps 2-3 (right)", "Close"],
  stills: [1.7, 4.3, 6.5, 8.2, 9.9, 13.7], // step 2 shown; the close shows the risen stone
  draw, score,
});
})();
