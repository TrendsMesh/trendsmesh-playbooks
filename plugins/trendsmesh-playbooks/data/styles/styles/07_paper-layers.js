/* 07 Layered Paper - reference animation.
 * Topic (setting, replace it): "How do bees make honey?" - from flower to sealed comb.
 * Rendering (keep it): a shadow box of scissor-cut card. Every shape is its own flat matte sheet with its own fibre,
 * a wobbly cut edge, a two-part shadow (wide soft + thin contact line) and light/dark rims; torn edges show a white
 * core. Layers: teal backboard, far and middle hills, grass, the story, a near strip, panned with strong parallax.
 * Cut-letter headlines on a cream backing; folded tags as labels. Finishing: warm desk-lamp soft-light, plum
 * vignette, light 12 fps grain. Pieces pop up, drop in (shadow wide while airborne) or spring out.
 */
(function () {
"use strict";
const B = window.Brush;

// ---- palette and type (from the card)
const PAL = { board: "#1f4e5f", cream: "#f2e8d5", mustard: "#e3b04b", coral: "#e2704f", sage: "#7fa36b",
  blue: "#7fa7c2", core: "#fffaf0" /* torn edges, light rims */, shadow: "#2a1c33" };
const HEAD = "Bowlby One", BODY = "Nunito";
const DUR = 12.5, BEATS = [0, 1.9, 4.1, 6.3, 8.6, 10.4];
let U = 1; // frame unit, set per frame

// ---- cut-paper geometry (reuse these)
/** Scissor-cut polygon: the outline nudged by smooth noise, never straight. */
const cut = (pts, seed, amp = 0.18) => B.wobble(B.densify(pts.concat([pts[0]]), 2.2 * U), { amp: amp * U, freq: 0.9, seed }).slice(0, -1);
/** A circle cut by hand: faceted, uneven snips. */
function cutCircle(cx, cy, r, seed, n) {
  const rr = B.rng(seed), k = n ?? Math.round(B.clamp(r / U, 3, 30) * 0.9 + 9), out = [];
  for (let i = 0; i < k; i++) {
    const a = ((i + rr.range(-0.2, 0.2)) / k) * B.TAU, rad = r * (1 + rr.range(-0.025, 0.025));
    out.push([cx + Math.cos(a) * rad, cy + Math.sin(a) * rad]);
  }
  return out;
}
const cutEllipse = (cx, cy, rx, ry, seed, rot = 0) => cutCircle(0, 0, 1, seed, Math.round(B.clamp(Math.max(rx, ry) / U, 3, 30) * 0.9 + 9)).map(([x, y]) => {
  const X = x * rx, Y = y * ry;
  return [cx + X * Math.cos(rot) - Y * Math.sin(rot), cy + X * Math.sin(rot) + Y * Math.cos(rot)];
});
const cutRect = (x, y, w, h, seed) => cut([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], seed);
/** A ragged torn edge from x0 to x1 around y. */
function tornLine(x0, x1, y, seed, amp, hill) {
  const out = [], n = Math.max(8, Math.round((x1 - x0) / (0.9 * U)));
  for (let i = 0; i <= n; i++) {
    const x = B.lerp(x0, x1, i / n), h = hill ? hill(i / n) : 0;
    out.push([x, y - h + B.noise1(x / (6 * U), seed) * amp * 0.6 + (B.hash01(seed, i) - 0.5) * 0.5 * U]);
  }
  return out;
}
const pathOf = (ctx, pts) => { ctx.beginPath(); B.poly(ctx, pts, true); };
function bboxOf(pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

// ---- paper texture and the sheet
function fibreTile() {
  return B.layer("paper-fibre", 384, 384, (g, w, h) => {
    const r = B.rng("fibre");
    for (let i = 0; i < 26; i++) {
      const x = r() * w, y = r() * h, rad = r.range(20, 70), light = r() < 0.5;
      for (const [ox, oy] of [[0, 0], [w, 0], [-w, 0], [0, h], [0, -h]]) {
        g.fillStyle = B.radial(g, x + ox, y + oy, 0, rad, [B.rgba(light ? "#ffffff" : "#000000", 0.055), B.rgba(light ? "#ffffff" : "#000000", 0)]);
        g.fillRect(x + ox - rad, y + oy - rad, rad * 2, rad * 2);
      }
    }
    for (let i = 0; i < 900; i++) {
      g.fillStyle = r() < 0.55 ? B.rgba("#ffffff", r.range(0.08, 0.22)) : B.rgba("#2a1c33", r.range(0.05, 0.16));
      g.fillRect(r() * w, r() * h, r.range(0.6, 1.6), r.range(0.6, 1.6));
    }
    g.lineCap = "round";
    for (let i = 0; i < 40; i++) {
      const x = r() * w, y = r() * h, a = r() * B.TAU, len = r.range(5, 16);
      g.strokeStyle = r() < 0.6 ? B.rgba("#ffffff", 0.22) : B.rgba("#2a1c33", 0.12); g.lineWidth = r.range(0.5, 1.0);
      g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a + 0.7) * len * 0.5, y + Math.sin(a + 0.7) * len * 0.5, x + Math.cos(a) * len, y + Math.sin(a) * len); g.stroke();
    }
  });
}
/** The fibre at the sheet's own offset and angle, so it never visibly repeats. */
function fibre(ctx, bb, seed, amount = 1) {
  const pat = ctx.createPattern(fibreTile(), "repeat"), r = B.rng(seed);
  ctx.save(); ctx.globalAlpha *= amount;
  ctx.translate(bb.x + bb.w / 2, bb.y + bb.h / 2); ctx.rotate(r() * B.TAU); ctx.translate(r() * 384, r() * 384);
  const s = Math.max(1, U / 10.8), R = Math.hypot(bb.w, bb.h) / s;
  ctx.scale(s, s); ctx.fillStyle = pat; ctx.fillRect(-R - 400, -R - 400, 2 * R + 800, 2 * R + 800); ctx.restore();
}
/** One sheet of card, the heart of the look: a two-part shadow (wider for a higher lift, in u), the face with its
 *  fibre, light and dark rims. o: { lift, seed, core (white core outline behind a torn edge), noRim, fibre } */
function sheet(ctx, pts, color, o = {}) {
  const lift = o.lift ?? 1.2, seed = o.seed ?? 1, base = o.core || pts;
  ctx.save();
  ctx.shadowColor = B.rgba(PAL.shadow, 0.42); ctx.shadowBlur = (0.8 + lift * 1.3) * U; ctx.shadowOffsetX = lift * 0.55 * U; ctx.shadowOffsetY = lift * 0.8 * U;
  pathOf(ctx, base); ctx.fillStyle = o.core ? PAL.core : color; ctx.fill();
  ctx.shadowColor = B.rgba(PAL.shadow, 0.55); ctx.shadowBlur = 0.18 * U; ctx.shadowOffsetX = 0.1 * U; ctx.shadowOffsetY = 0.16 * U;
  ctx.fill(); ctx.restore();
  if (o.core) { // fibres poke out of the torn core
    const r = B.rng(seed + 77);
    ctx.save(); ctx.strokeStyle = B.rgba(PAL.core, 0.8); ctx.lineWidth = Math.max(1, 0.08 * U); ctx.beginPath();
    for (let i = 0; i < base.length; i += 3) {
      if (r() < 0.55) continue;
      const [x, y] = base[i], a = -Math.PI / 2 + r.range(-0.9, 0.9), l = r.range(0.2, 0.6) * U;
      ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l);
    }
    ctx.stroke(); ctx.restore();
    fibreFace(ctx, base, PAL.core, seed + 3, 0.6, true);
  }
  fibreFace(ctx, pts, color, seed, o.fibre ?? 1, o.noRim);
}
function fibreFace(ctx, pts, color, seed, amount, noRim) {
  const bb = bboxOf(pts);
  ctx.save(); pathOf(ctx, pts); ctx.fillStyle = color; ctx.fill(); ctx.clip();
  fibre(ctx, bb, seed, amount);
  if (!noRim) { // rims: the shape minus itself shifted
    const rw = Math.max(1, 0.12 * U), big = [bb.x - 10 * U, bb.y - 10 * U, bb.w + 20 * U, bb.h + 20 * U];
    for (const [d, col] of [[rw, B.rgba(PAL.core, 0.55)], [-rw, B.rgba(PAL.shadow, 0.35)]]) {
      ctx.beginPath(); ctx.rect(...big); B.poly(ctx, pts.map(([x, y]) => [x + d, y + d]), true); ctx.fillStyle = col; ctx.fill("evenodd");
    }
  }
  ctx.restore();
}
function cloudPts(s, seed) {
  const out = [], arc = (cx, cy, r, a0, a1, n) => { for (let i = 0; i <= n; i++) { const a = B.lerp(a0, a1, i / n); out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } };
  arc(-0.7 * s, 0.1 * s, 0.5 * s, Math.PI * 0.95, Math.PI * 1.62, 5);
  arc(0, -0.15 * s, 0.68 * s, Math.PI * 1.2, Math.PI * 1.82, 7);
  arc(0.72 * s, 0.1 * s, 0.45 * s, Math.PI * 1.45, Math.PI * 2.05, 5);
  out.push([1.15 * s, 0.36 * s], [-1.18 * s, 0.36 * s]);
  return cut(out, seed, 0.15);
}
/** A torn strip: the face sits a hair below its white core. */
function tornStrip(x0, x1, y, bottom, seed, amp, hill) {
  const top = tornLine(x0, x1, y, seed, amp, hill), face = top.map(([x, yy], i) => [x, yy + (0.25 + 0.35 * B.hash01(seed, i, 9)) * U]);
  return { core: [...top, [x1, bottom], [x0, bottom]], face: [...face, [x1, bottom], [x0, bottom]] };
}

// ---- paper lettering, tags, arrows, tiles
/** Cut-paper headline: chunky letters, each its own colour and tilt, on a loosely trimmed cream backing; the letters
 *  get fibre on a scratch layer, then their own two-part shadow. */
function paperWord(ctx, word, cx, cy, size, seed, o = {}) {
  ctx.save(); ctx.font = B.font(size, HEAD, 400);
  const widths = [...word].map((ch) => ctx.measureText(ch).width), tw = widths.reduce((a, b) => a + b, 0) + size * 0.04 * (word.length - 1);
  ctx.restore();
  const m = size * 0.32, bw = tw + 2 * m, bh = size * 1.25 + m * 0.6, r = B.rng(seed);
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(r.range(-1.5, 1.5) * (Math.PI / 180));
  const back = cut([[-bw / 2 + r.range(0, 0.6) * U, -bh / 2], [bw / 2 - r.range(0, 0.6) * U, -bh / 2 + r.range(-0.4, 0.4) * U], [bw / 2 + r.range(-0.3, 0.3) * U, bh / 2], [-bw / 2, bh / 2 + r.range(-0.4, 0.4) * U]], seed + 1, 0.25);
  sheet(ctx, back, PAL.cream, { lift: o.lift ?? 1.6, seed: seed + 2 });
  const g = B.scratch("paper-letters", ctx.canvas.width, ctx.canvas.height), cols = [PAL.coral, "#a8761c", PAL.board, "#4c6e3c", "#3f6585"]; // deep enough to read on cream
  g.setTransform(ctx.getTransform()); g.font = B.font(size, HEAD, 400); g.textBaseline = "middle"; g.textAlign = "center";
  let x = -tw / 2;
  [...word].forEach((ch, i) => {
    g.save(); g.translate(x + widths[i] / 2, size * 0.06); g.rotate(r.range(-2.2, 2.2) * (Math.PI / 180));
    g.fillStyle = cols[(i + seed) % cols.length]; g.fillText(ch, 0, 0); g.restore();
    x += widths[i] + size * 0.04;
  });
  g.globalCompositeOperation = "source-atop";
  fibre(g, { x: -bw / 2, y: -bh / 2, w: bw, h: bh }, seed + 5, 1);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.shadowColor = B.rgba(PAL.shadow, 0.4); ctx.shadowBlur = 0.9 * U; ctx.shadowOffsetX = 0.35 * U; ctx.shadowOffsetY = 0.5 * U; ctx.drawImage(g.canvas, 0, 0);
  ctx.shadowColor = B.rgba(PAL.shadow, 0.5); ctx.shadowBlur = 0.12 * U; ctx.shadowOffsetX = 0.08 * U; ctx.shadowOffsetY = 0.12 * U; ctx.drawImage(g.canvas, 0, 0);
  ctx.restore();
}
/** Folded tag: the top strip bends back (darker, dotted fold). flip 0..1 turns it to text2. o.left: cx = left edge. */
function tag(ctx, cx, cy, text, size, o = {}) {
  const s = o.s ?? 1;
  if (s <= 0.001) return;
  const flip = o.flip ?? 0, back = flip > 0.5, txt = back && o.text2 ? o.text2 : text;
  ctx.save(); ctx.font = B.font(size, BODY, 900);
  const tw = Math.max(ctx.measureText(text).width, o.text2 ? ctx.measureText(o.text2).width : 0), w = tw + size * 1.6, h = size * 2.3, fold = size * 0.55;
  ctx.translate(cx + (o.left ? (w * s) / 2 : 0), cy); ctx.rotate(((o.rot ?? 0) * Math.PI) / 180);
  ctx.scale(s * Math.max(0.02, Math.abs(Math.cos(flip * Math.PI))), s);
  const seed = (o.seed ?? 3) + (back ? 50 : 0);
  sheet(ctx, cutRect(-w / 2, -h / 2, w, h, seed), back ? o.color2 || o.color || PAL.cream : o.color || PAL.cream, { lift: 1.1 + 1.5 * Math.sin(flip * Math.PI), seed });
  ctx.fillStyle = B.rgba(PAL.shadow, 0.13); ctx.fillRect(-w / 2 + 1, -h / 2 + 1, w - 2, fold);
  ctx.strokeStyle = B.rgba(PAL.shadow, 0.35); ctx.lineWidth = Math.max(1, 0.1 * U); ctx.setLineDash([0.35 * U, 0.35 * U]);
  ctx.beginPath(); ctx.moveTo(-w / 2 + 0.4 * U, -h / 2 + fold); ctx.lineTo(w / 2 - 0.4 * U, -h / 2 + fold); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = o.ink || PAL.shadow; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(txt, 0, fold / 2 + size * 0.05); ctx.restore();
}
/** Paper strip arrow with a cut head, grown along a curve to p. */
function stripArrow(ctx, pts, p, width, color, seed) {
  if (p <= 0.01) return;
  const path = B.densify(B.trim(pts, 0, p), 1.2 * U), n = path.length, left = [], right = [];
  if (n < 2) return;
  for (let i = 0; i < n; i++) {
    const a = path[Math.max(0, i - 1)], b = path[Math.min(n - 1, i + 1)], l = Math.hypot(b[1] - a[1], b[0] - a[0]) || 1;
    const nx = -(b[1] - a[1]) / l, ny = (b[0] - a[0]) / l, w = width / 2 + (B.hash01(seed, i) - 0.5) * 0.12 * U;
    left.push([path[i][0] + nx * w, path[i][1] + ny * w]); right.push([path[i][0] - nx * w, path[i][1] - ny * w]);
  }
  const tip = B.pointAt(path, 1), ang = tip[2], hl = width * 1.5, hw = width * 1.25, ca = Math.cos(ang + Math.PI / 2), sa = Math.sin(ang + Math.PI / 2);
  const head = [[tip[0] + ca * hw, tip[1] + sa * hw], [tip[0] + Math.cos(ang) * hl, tip[1] + Math.sin(ang) * hl], [tip[0] - ca * hw, tip[1] - sa * hw]];
  sheet(ctx, [...left, head[2], head[1], head[0], ...right.reverse()].reverse(), color, { lift: 1.8, seed });
}
function digitTile(ctx, cx, cy, size, ch, ch2, flip, seed) {
  const nw = flip > 0.5, sd = seed + (nw ? 9 : 0), r = B.rng(sd), w = size * 0.82;
  ctx.save(); ctx.translate(cx, cy - Math.sin(flip * Math.PI) * size * 0.25); ctx.rotate((r.range(-5, 5) * Math.PI) / 180);
  ctx.scale(Math.max(0.02, Math.abs(Math.cos(flip * Math.PI))), 1);
  sheet(ctx, cutRect(-w / 2, -size / 2, w, size, sd), nw ? PAL.mustard : PAL.cream, { lift: 1.6 + 3 * Math.sin(flip * Math.PI), seed: sd });
  ctx.font = B.font(size * 0.68, HEAD, 400); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = nw ? PAL.shadow : PAL.board;
  ctx.fillText(nw ? ch2 : ch, 0, size * 0.05); ctx.restore();
}
/** A cut tick dropping in (drop 0..1), its shadow wide while airborne. */
function cutTick(ctx, x, y, size, drop, seed) {
  if (drop <= 0) return;
  const fall = 1 - B.ease.outBack(B.clamp(drop), 2.5), k = size / 10;
  ctx.save(); ctx.translate(x, y - fall * size * 2.5); ctx.rotate(-0.12 + fall * 0.4);
  sheet(ctx, cut([[-5, 0], [-2, -3], [0, -0.5], [5, -6.5], [8, -3.5], [0, 5]].map(([a, b]) => [a * k, b * k]), seed, 0.12), PAL.sage, { lift: 1.5 + 4 * fall, seed });
  ctx.restore();
}
/** A fan of cut rays popping up behind the key item. */
function rayFan(ctx, x, y, r, p, seed) {
  if (p <= 0) return;
  const n = 14, s = B.ease.outBack(B.clamp(p), 1.6);
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * B.TAU + 0.1, a1 = a0 + (B.TAU / n) * 0.55, R = r * s * (i % 2 ? 0.85 : 1);
    sheet(ctx, [[x + Math.cos(a0) * r * 0.25, y + Math.sin(a0) * r * 0.25], [x + Math.cos(a0) * R, y + Math.sin(a0) * R], [x + Math.cos(a1) * R, y + Math.sin(a1) * R]], i % 2 ? PAL.cream : PAL.mustard, { lift: 0.8, seed: seed + i, noRim: true });
  }
}

// ---- subjects (the setting: replace these)
/** Flower: stands up like a pop-up page; v = cut version (flutter). */
function flower(ctx, x, y, size, color, seed, rise, v = 0) {
  if (rise <= 0.001) return;
  ctx.save(); ctx.translate(x, y); ctx.scale(1, B.ease.outBack(B.clamp(rise), 1.4));
  sheet(ctx, cut([[-size * 0.06, 0], [size * 0.06, 0], [size * 0.05, -size * 1.6], [-size * 0.05, -size * 1.6]], seed), B.shade(PAL.sage, -0.15), { lift: 0.8, seed });
  sheet(ctx, cutEllipse(size * 0.32, -size * 0.65, size * 0.32, size * 0.13, seed + 1, -0.5), PAL.sage, { lift: 1, seed: seed + 1 });
  ctx.translate(0, -size * 1.6); ctx.rotate([0, 0.06, -0.05][v % 3]);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * B.TAU + seed;
    sheet(ctx, cutEllipse(Math.cos(a) * size * 0.42, Math.sin(a) * size * 0.42, size * 0.36, size * 0.24, seed + 10 + i + v * 7, a), color, { lift: 1.3, seed: seed + 10 + i });
  }
  sheet(ctx, cutCircle(0, 0, size * 0.32, seed + 20), PAL.mustard, { lift: 1.6, seed: seed + 20 });
  ctx.restore();
}
/** Bee: wings flutter by swapping three cut shapes about 14 times a second. */
function bee(ctx, x, y, size, t, seed, o = {}) {
  const v = Math.floor(t * 14) % 3, wingA = [-0.35, -0.75, -1.05][v], body = cutEllipse(0, 0, size * 0.62, size * 0.4, seed + 5);
  ctx.save(); ctx.translate(x, y); ctx.rotate(o.rot ?? -0.1); ctx.scale(o.flipX ? -1 : 1, 1);
  sheet(ctx, cutEllipse(-size * 0.15, -size * 0.45, size * 0.42, size * 0.22, seed + v, wingA), B.mix(PAL.cream, PAL.blue, 0.25), { lift: 2.4, seed: seed + 30 + v });
  sheet(ctx, body, PAL.mustard, { lift: 1.8, seed: seed + 5 });
  ctx.save(); pathOf(ctx, body); ctx.clip(); // stripes glued on, trimmed to the body
  [-0.12, 0.18].forEach((sx, i) => sheet(ctx, cutRect(size * sx, -size * 0.5, size * 0.15, size, seed + 40 + i), PAL.shadow, { lift: 0.4, seed: seed + 40 + i, noRim: true }));
  ctx.restore();
  sheet(ctx, cutCircle(-size * 0.62, -size * 0.05, size * 0.24, seed + 6), PAL.shadow, { lift: 1.9, seed: seed + 6 });
  sheet(ctx, cutCircle(-size * 0.68, -size * 0.1, size * 0.07, seed + 7, 8), PAL.core, { lift: 0.3, seed: seed + 7, noRim: true });
  sheet(ctx, [[size * 0.58, -size * 0.06], [size * 0.85, size * 0.02], [size * 0.58, size * 0.1]], PAL.shadow, { lift: 1.2, seed: seed + 8 });
  sheet(ctx, cutEllipse(size * 0.1, -size * 0.5, size * 0.4, size * 0.2, seed + 3 + v, wingA + 0.3), B.mix(PAL.cream, PAL.blue, 0.1), { lift: 2.8, seed: seed + 20 + v });
  ctx.restore();
}
/** Skep hive: stacked card bands and a punched doorway. */
function hive(ctx, x, y, size, seed) {
  for (let i = 0; i < 5; i++) {
    const w = size * (0.55 + 0.5 * Math.sin(0.35 + (i / 4) * 2.4)), h = size * 0.3, yy = y - size * 0.55 + i * size * 0.24;
    sheet(ctx, cut([[x - w / 2 + size * 0.06, yy], [x + w / 2 - size * 0.06, yy], [x + w / 2 + size * 0.04, yy + h], [x - w / 2 - size * 0.04, yy + h]], seed + i), i % 2 ? PAL.mustard : B.shade(PAL.mustard, -0.08), { lift: 1 + i * 0.25, seed: seed + i });
  }
  pathOf(ctx, cutEllipse(x, y + size * 0.42, size * 0.13, size * 0.09, seed + 9)); ctx.fillStyle = B.mix(PAL.shadow, PAL.board, 0.3); ctx.fill();
  ctx.save(); ctx.clip(); ctx.fillStyle = B.rgba(PAL.shadow, 0.6); ctx.fillRect(x - size * 0.2, y + size * 0.33, size * 0.4, size * 0.05); ctx.restore();
}
/** Honeycomb cell; fill "nectar" | "fan" (drying) | "cap" (wax lid). */
function cell(ctx, x, y, r, seed, fill, t, k) {
  const hex = (rr) => Array.from({ length: 6 }, (_, i) => [x + Math.cos(Math.PI / 6 + (i * B.TAU) / 6) * rr, y + Math.sin(Math.PI / 6 + (i * B.TAU) / 6) * rr]);
  sheet(ctx, cut(hex(r), seed, 0.12), PAL.mustard, { lift: 1.4, seed });
  pathOf(ctx, cut(hex(r * 0.74), seed + 1, 0.1)); ctx.fillStyle = B.shade(PAL.mustard, -0.38); ctx.fill();
  ctx.save(); ctx.clip(); ctx.fillStyle = B.rgba(PAL.shadow, 0.35); ctx.fillRect(x - r, y - r * 0.8, 2 * r, r * 0.18); ctx.restore();
  if (fill === "nectar") {
    const s = B.ease.outBack(B.clamp(k), 2);
    if (s > 0) sheet(ctx, cut([[x, y - r * 0.5 * s], [x + r * 0.32 * s, y + r * 0.05 * s], [x + r * 0.22 * s, y + r * 0.35 * s], [x - r * 0.22 * s, y + r * 0.35 * s], [x - r * 0.32 * s, y + r * 0.05 * s]], seed + 4, 0.1), PAL.blue, { lift: 1.2, seed: seed + 4 });
    return;
  }
  sheet(ctx, cut(hex(r * 0.6), seed + 5, 0.1), B.shade(PAL.mustard, -0.18), { lift: 0.5, seed: seed + 5, noRim: true });
  if (fill === "fan" && k > 0) { // steam strips lift off
    const v = Math.floor(t * 6);
    for (let i = 0; i < 3; i++) {
      const ph = B.fract(t * 0.8 + i / 3), yy = y - r * 0.2 - ph * r * 1.4, xx = x + (i - 1) * r * 0.35 + ((v + i) % 2 ? 1 : -1) * 0.25 * U;
      ctx.globalAlpha = Math.sin(ph * Math.PI) * B.clamp(k * 2);
      sheet(ctx, cut([[xx - 0.3 * U, yy], [xx + 0.3 * U, yy], [xx + 0.3 * U, yy + r * 0.35], [xx - 0.3 * U, yy + r * 0.35]], seed + 60 + ((v + i) % 3)), PAL.cream, { lift: 1.6, seed: seed + 60 + i, noRim: true });
      ctx.globalAlpha = 1;
    }
  }
  if (fill === "cap" && k > 0) {
    const fall = 1 - B.ease.outBack(B.clamp(k), 2);
    ctx.save(); ctx.translate(0, -fall * r * 1.4); sheet(ctx, cut(hex(r * 0.78), seed + 7, 0.14), PAL.cream, { lift: 1.2 + 4 * fall, seed: seed + 7 }); ctx.restore();
  }
}
function jar(ctx, x, y, size, seed) {
  const w = size, h = size * 1.1;
  sheet(ctx, cut([[x - w / 2 + size * 0.08, y - h], [x + w / 2 - size * 0.08, y - h], [x + w / 2, y - h + size * 0.15], [x + w / 2, y], [x - w / 2, y], [x - w / 2, y - h + size * 0.15]], seed, 0.2), PAL.mustard, { lift: 1.6, seed });
  sheet(ctx, cutRect(x - w * 0.42, y - h - size * 0.2, w * 0.84, size * 0.24, seed + 1), PAL.coral, { lift: 2, seed: seed + 1 });
  sheet(ctx, cutRect(x - w * 0.4, y - h * 0.62, w * 0.8, h * 0.38, seed + 2), PAL.cream, { lift: 1.2, seed: seed + 2 });
  ctx.save(); ctx.font = B.font(size * 0.18, HEAD, 400); ctx.fillStyle = PAL.coral; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("HONEY", x, y - h * 0.43); ctx.restore();
}

// ---- layout, camera and the diorama layers
function layout(W, H) {
  const F = B.frame(W, H), u = F.u, P = F.portrait, span = W * (P ? 1.0 : 0.95);
  return { F, u, P, span, ground: H * (P ? 0.78 : 0.8), st: [0, 1, 2, 3, 4].map((i) => W / 2 + i * span) /* station centres */, head: 9.5 * u,
    label: 4.0 * u /* tags at this size or larger */ };
}
/** Camera: long sideways pans between stations, a slow push-in on each. */
function camAt(t, L, W, H) {
  let idx = 0;
  for (const [a, b] of [[1.6, 2.4], [3.85, 4.55], [6.0, 6.75], [10.05, 10.85]]) idx += B.span(t, a, b, "inOutCubic");
  const since = [0, 2.4, 4.55, 6.75, 10.85].reduce((acc, s) => (t >= s ? s : acc), 0);
  const zoom = 1 + 0.04 * B.span(t, since, since + 2.5, "inOutSine") + 0.07 * B.span(t, 8.55, 9.1, "inOutCubic") * (1 - B.span(t, 9.9, 10.4, "inOutCubic"));
  return { x: L.st[0] + idx * L.span, y: H / 2, zoom };
}
/** Back layers, each slower than the story. */
function backLayers(ctx, W, H, t, L, cam) {
  const u = L.u, total = L.st[4] + W;
  ctx.drawImage(B.layer("paper-board", W, H, (g, w, h) => {
    g.fillStyle = PAL.board; g.fillRect(0, 0, w, h);
    const sv = U;
    U = Math.min(w, h) / 100; fibre(g, { x: 0, y: 0, w, h }, 4, 1.4); U = sv;
  }), 0, 0);
  sheet(ctx, cutCircle(W * 0.84, H * (L.P ? 0.09 : 0.15), (L.P ? 9 : 7) * u, 31), PAL.mustard, { lift: 1.2, seed: 31 }); // the sun, fixed on the backboard
  B.camera(ctx, W, H, cam, () => {
    const s = tornStrip(-W, total, L.ground - (L.P ? 17 : 19) * u, H * 1.2, 41, 2.2 * u, (f) => (Math.sin(f * 9.5) * 0.5 + 0.5) * 9 * u + Math.sin(f * 23) * 2 * u);
    sheet(ctx, s.face, PAL.blue, { core: s.core, lift: 1.8, seed: 41 });
  }, 0.25);
  B.camera(ctx, W, H, cam, () => { // clouds hanging on wires, swaying
    [[0.18, 0.2], [1.9, 0.22], [2.75, 0.12], [3.6, 0.2], [4.4, 0.14]].forEach(([fx, fy], i) => {
      const cy = (L.P ? fy * 0.85 + 0.03 : fy) * H, s = (L.P ? 7 : 6) * u;
      ctx.save(); ctx.translate(fx * W, -2 * u); ctx.rotate(0.03 * Math.sin(t * 1.3 + i * 2));
      ctx.strokeStyle = B.rgba(PAL.shadow, 0.6); ctx.lineWidth = Math.max(1, 0.1 * u);
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, cy - s * 0.5 + 2 * u); ctx.stroke();
      ctx.translate(0, cy + 2 * u); sheet(ctx, cloudPts(s, 80 + i), PAL.cream, { lift: 1.6, seed: 80 + i }); ctx.restore();
    });
  }, 0.4);
  B.camera(ctx, W, H, cam, () => {
    const s = tornStrip(-W, total, L.ground - 7 * u, H * 1.2, 52, 2 * u, (f) => (Math.sin(f * 13 + 1) * 0.5 + 0.5) * 7 * u);
    sheet(ctx, s.face, B.mix(PAL.sage, PAL.board, 0.35), { core: s.core, lift: 2.2, seed: 52 });
  }, 0.55);
}
function groundLayer(ctx, W, H, L, cam) {
  const u = L.u, total = L.st[4] + W;
  B.camera(ctx, W, H, cam, () => {
    const g = L.ground, pts = [], r = B.rng("snips");
    for (let x = -W; x < total; x += 1.4 * u) {
      const h = r.range(0.6, 1.8) * u;
      pts.push([x, g + r.range(-0.2, 0.2) * u], [x + 0.45 * u, g - h], [x + 0.9 * u, g + r.range(-0.2, 0.2) * u]);
    }
    pts.push([total, H * 1.3], [-W, H * 1.3]);
    sheet(ctx, pts, PAL.sage, { lift: 2.4, seed: 61 });
  }, 0.85);
}
function nearLayer(ctx, W, H, L, cam) {
  B.camera(ctx, W, H, cam, () => {
    const s = tornStrip(-W * 1.2, L.st[4] + W * 1.6, H * (L.P ? 0.88 : 0.92), H * 1.4, 71, 2.5 * L.u, (f) => (Math.sin(f * 31) * 0.5 + 0.5) * 3 * L.u);
    sheet(ctx, s.face, B.shade(PAL.sage, -0.3), { core: s.core, lift: 3.2, seed: 71 });
  }, 1.25);
}

// ---- the stations (story pieces at depth 1)
const popIn = (t, at, d = 0.45, s = 2) => B.ease.outBack(B.prog(t, at, d), s);
function stationTitle(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.st[0], ty = H * (P ? 0.36 : 0.34), sz = L.head;
  if (t > 2.6) return;
  [[-0.38, 7, PAL.coral], [-0.2, 5.5, PAL.blue], [0.22, 6.5, PAL.cream], [0.4, 5, PAL.coral]].forEach(([dx, s, c], i) => flower(ctx, x0 + dx * W, L.ground + 0.5 * u, s * u * (P ? 1.6 : 1.5), c, 3 + i * 17, B.prog(t, 0.15 + i * 0.12, 0.6), Math.floor(t * 3 + i) % 3));
  const fall = (at) => 1 - popIn(t, at, 0.55, 1.8);
  if (t > 0.3) paperWord(ctx, "HOW BEES", x0, ty - sz * 0.75 - fall(0.3) * H * 0.4, sz, 3, { lift: 1.6 + 4 * fall(0.3) });
  if (t > 0.48) paperWord(ctx, "MAKE HONEY", x0, ty + sz * 0.75 - fall(0.48) * H * 0.4, sz, 8, { lift: 1.6 + 4 * fall(0.48) });
  tag(ctx, x0, ty + sz * 2.15, "From flower to jar", L.label, { s: popIn(t, 0.9), rot: -2 });
}
function stationDiagram(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.st[1], g = L.ground, fs = (P ? 25 : 19) * u, fx = P ? x0 - W * 0.08 : x0 - W * 0.14, head = [fx, g - fs * 1.6];
  if (t < 1.2 || t > 4.9) return;
  flower(ctx, fx, g + 0.5 * u, fs, PAL.coral, 101, B.prog(t, 1.9, 0.6), Math.floor(t * 3) % 3);
  const arr = B.ease.outBack(B.prog(t, 2.2, 0.7), 1.4);
  const bx = B.lerp(x0 + W * 0.5, head[0] + fs * 0.25, arr), by = B.lerp(H * 0.12, head[1] - fs * 0.62, arr) + B.bob(t, 0.6 * u, 0.9);
  if (t > 2.2) bee(ctx, bx, by, (P ? 10 : 9) * u, t, 7, { rot: -0.15 });
  tag(ctx, fx + fs * 0.75, g - fs * 0.45, "FLOWER", L.label, { s: popIn(t, 2.55, 0.45, 2.2), rot: 4, seed: 11 });
  const nk = popIn(t, 2.8, 0.45, 2.2), nt = [head[0] - fs * 1.15, head[1] - fs * 0.05]; // a thread to the centre
  if (nk > 0.01) { ctx.strokeStyle = B.rgba(PAL.shadow, 0.8); ctx.lineWidth = Math.max(1.5, 0.25 * u); ctx.beginPath(); ctx.moveTo(nt[0], nt[1]); ctx.lineTo(head[0] - fs * 0.12, head[1]); ctx.stroke(); }
  tag(ctx, nt[0], nt[1], "NECTAR", L.label, { s: nk, rot: -4, seed: 12, color: PAL.blue });
  tag(ctx, bx - fs * 0.05 - (P ? 0 : fs * 0.9), by - fs * 0.55, "WORKER BEE", L.label, { s: popIn(t, 3.0, 0.45, 2.2), rot: 3, seed: 13, color: PAL.mustard });
  const a0 = [head[0] + fs * 0.75, head[1] - fs * 0.15];
  // a little hive: home, where the strip arrow points
  const hs = (P ? 11 : 8) * u, hx = x0 + W * (P ? 0.3 : 0.36), hy = H * (P ? 0.25 : 0.34), e = [hx - hs * 0.3, hy + hs * 0.5];
  if (t > 2.9) hive(ctx, hx, hy, hs * popIn(t, 2.9, 0.5, 1.6), 250);
  const pts = B.quad(a0[0], a0[1], a0[0] + (e[0] - a0[0]) * 0.3, e[1], e[0] - hs * 0.35, e[1]);
  stripArrow(ctx, pts, B.prog(t, 3.1, 0.7, "inOutCubic"), 3.2 * u, PAL.coral, 14);
  const mid = B.pointAt(pts, P ? 0.75 : 0.62);
  tag(ctx, P ? x0 - W * 0.2 : mid[0], P ? H * 0.2 : mid[1] - 8.5 * u, "Sip, then fly home", L.label, { s: popIn(t, 3.5, 0.45, 2.2), rot: -2, seed: 15 });
}
function stationNumber(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.st[2];
  if (t < 3.4 || t > 7.2) return;
  const hx = P ? x0 : x0 - W * 0.08, top = H * (P ? 0.08 : 0.05), hs = (P ? 22 : 24) * u, hy = P ? H * 0.32 : H * 0.48;
  sheet(ctx, cut([[hx - W * 0.2, top + 2 * u], [hx + W * 0.2, top], [hx + W * 0.2, top + 2.2 * u], [hx - W * 0.2, top + 4 * u]], 201), B.shade(PAL.coral, -0.35), { lift: 2, seed: 201 });
  ctx.save(); ctx.translate(hx, top + 3 * u); ctx.rotate(0.05 * Math.sin(t * 1.7));
  ctx.strokeStyle = B.rgba(PAL.shadow, 0.8); ctx.lineWidth = Math.max(1, 0.12 * u); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, hy - top - hs * 0.6); ctx.stroke();
  hive(ctx, 0, hy - top - 3 * u, hs, 210); ctx.restore();
  // the number: cut digit tiles; "80%" water in nectar flicks over to "18%" in honey
  const ds = (P ? 15 : 13) * u, ny = P ? H * 0.56 : H * 0.42, nx = P ? x0 : x0 + W * 0.14, from = "80%", to = "18%";
  [...from].forEach((ch, i) => {
    const k = B.prog(t, 4.45 + i * 0.07, 0.5);
    if (k <= 0) return;
    ctx.save(); ctx.translate(0, -(1 - B.ease.outBack(k, 2)) * ds * 3);
    digitTile(ctx, nx + (i - 1) * ds * 0.92, ny, ds, ch, to[i], B.prog(t, 5.45 + i * 0.06, 0.3, "inOutSine"), 220 + i * 3);
    ctx.restore();
  });
  tag(ctx, nx, ny - ds, "Nectar: up to", L.label, { s: popIn(t, 4.7), rot: -2, seed: 230, flip: B.prog(t, 5.5, 0.45, "inOutSine"), text2: "Honey: about", color: PAL.blue, color2: PAL.mustard });
  tag(ctx, nx, ny + ds * 0.95, "of it is water", L.label, { s: popIn(t, 4.95), rot: 2, seed: 231 });
  B.glow(ctx, nx, ny, ds * 2.4, "#ffd9a0", 0.12, { add: true });
  const k = B.prog(t, 4.1, 1.1, "inOutSine");
  if (k > 0 && k < 1) bee(ctx, B.lerp(x0 - W * 0.6, hx + hs * 0.1, k), B.lerp(H * 0.5, hy + hs * 0.35, k) + Math.sin(k * 9) * 2 * u, 6 * u, t, 240);
}
function stationSteps(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.st[3], r = (P ? 9.5 : 8.5) * u;
  if (t < 5.4 || t > 11.2) return;
  const cells = P ? [0.27, 0.44, 0.61].map((k) => [x0 - W * 0.24, H * k]) : [-0.27, 0, 0.27].map((k) => [x0 + W * k, H * 0.43]);
  const texts = ["Pass it bee to bee", "Fan it dry", "Seal it with wax"], fills = ["nectar", "fan", "cap"], ats = [6.85, 7.45, 8.05];
  cells.forEach(([cx, cy], i) => {
    const k = B.ease.outBack(B.prog(t, 6.5 + i * 0.12, 0.5), 1.7);
    if (k <= 0) return;
    if (i === 2) rayFan(ctx, cx, cy, r * 1.6, B.prog(t, 8.6, 0.5), 300);
    ctx.save(); ctx.translate(cx, cy); ctx.scale(k, k); ctx.translate(-cx, -cy); cell(ctx, cx, cy, r, 310 + i * 5, fills[i], t, B.prog(t, ats[i], 0.5)); ctx.restore();
    const n = popIn(t, ats[i] - 0.1, 0.4);
    if (n > 0) digitTile(ctx, cx - r * 1.0, cy - r * 0.95, 6 * u * n, String(i + 1), String(i + 1), 0, 330 + i);
    tag(ctx, P ? cx + r * 2.15 : cx, P ? cy : cy + r * 1.55, texts[i], L.label, { s: popIn(t, ats[i] + 0.1), rot: [-3, 2, -2][i], seed: 340 + i, left: P, ...(i === 2 ? { flip: B.prog(t, 9.15, 0.45, "inOutSine"), text2: "Honey, ready!", color2: PAL.mustard } : {}) });
    if (i === 1 && t > 7.4) bee(ctx, cx + r * 0.95, cy - r * 0.9, 5 * u, t * 1.6, 350, { rot: 0.3, flipX: true });
  });
  const [c3x, c3y] = cells[2];
  cutTick(ctx, c3x + r * 0.55, c3y + r * 0.1, 6 * u, B.prog(t, 8.9, 0.5), 360);
}
function stationClose(ctx, t, L, W, H) {
  const u = L.u, P = L.P, x0 = L.st[4], g = L.ground, js = (P ? 30 : 23) * u;
  if (t < 9.6) return;
  ctx.save(); ctx.translate(0, (1 - B.ease.outBack(B.prog(t, 10.5, 0.6), 1.5)) * js * 1.6); jar(ctx, P ? x0 : x0 - W * 0.25, g + u, js, 400); ctx.restore();
  [[-0.38, 8, PAL.coral], [0.36, 9, PAL.blue]].forEach(([dx, s, c], i) => flower(ctx, x0 + dx * W, g + 0.5 * u, s * u * (P ? 1.5 : 1), c, 410 + i * 9, B.prog(t, 10.6 + i * 0.12, 0.6), Math.floor(t * 3 + i) % 3));
  const ty = H * (P ? 0.33 : 0.34), cx = P ? x0 : x0 + W * 0.1, sz = L.head * (P ? 0.92 : 0.85), fall = (at) => 1 - popIn(t, at, 0.55, 1.8);
  if (t > 10.9) paperWord(ctx, "HONEY IS", cx, ty - sz * 0.75 - fall(10.9) * H * 0.5, sz, 5, { lift: 1.6 + 4 * fall(10.9) });
  if (t > 11.05) paperWord(ctx, "DRIED NECTAR", cx, ty + sz * 0.75 - fall(11.05) * H * 0.5, sz, 11, { lift: 1.6 + 4 * fall(11.05) });
  tag(ctx, cx, ty + sz * 2.1, "Sealed in wax, it keeps", L.label, { s: popIn(t, 11.4), rot: 2, seed: 420 });
}

// ---- frame and finishing
function draw(ctx, W, H, t) {
  const L = layout(W, H), cam = camAt(t, L, W, H);
  U = L.u;
  backLayers(ctx, W, H, t, L, cam);
  groundLayer(ctx, W, H, L, cam);
  B.camera(ctx, W, H, cam, () => { stationTitle(ctx, t, L, W, H); stationDiagram(ctx, t, L, W, H); stationNumber(ctx, t, L, W, H); stationSteps(ctx, t, L, W, H); stationClose(ctx, t, L, W, H); });
  nearLayer(ctx, W, H, L, cam);
  // warm desk lamp from the top left, cooling to blue-purple corners
  ctx.save(); ctx.globalCompositeOperation = "soft-light"; ctx.globalAlpha = 0.9;
  ctx.fillStyle = B.radial(ctx, W * 0.12, H * 0.02, 0, Math.hypot(W, H) * 0.95, [[0, "#ffe9bf"], [0.4, "#e9b97e"], [0.78, "#5f4f85"], [1, "#2c2550"]]);
  ctx.fillRect(0, 0, W, H); ctx.restore();
  B.glow(ctx, W * 0.12, H * 0.04, Math.hypot(W, H) * 0.45, "#ffd59a", 0.1, { add: true });
  B.vignette(ctx, W, H, { color: PAL.shadow, amount: 0.55, inner: 0.42 });
  B.grain(ctx, W, H, { amount: 0.05, t, fps: 12, mode: "overlay" });
}

// ---- sound: card taps, rubs, slides, flicks, pop-ups, plucks
SOUND.define("paper-tap", (v) => {
  v.tone({ f: 150, f2: 85, glide: 0.06, a: 0.002, len: 0.09, peak: 0.35 }); v.noise({ filter: "bandpass", f: 2600, q: 1.2, a: 0.0006, len: 0.025, peak: 0.22 });
}, { verb: 0.15 });
SOUND.define("paper-rub", (v, o) => { // smooth, no crinkle
  const d = o.dur ?? 0.8;
  v.noise({ brown: true, filter: "lowpass", f: 380, f2: 620, glide: d, a: d * 0.4, hold: d * 0.2, len: d * 0.4, peak: 0.5 });
  v.noise({ filter: "bandpass", f: 900, q: 0.6, a: d * 0.45, hold: d * 0.1, len: d * 0.45, peak: 0.05 });
}, { verb: 0.15 });
SOUND.define("paper-slide", (v, o) => {
  const d = o.dur ?? 0.3;
  v.noise({ filter: "bandpass", f: 1300, q: 0.8, a: d * 0.6, len: d * 0.4, peak: 0.16 }); v.sub("paper-tap", d, {});
}, { verb: 0.12 });
SOUND.define("paper-flick", (v) => { v.noise({ filter: "highpass", f: 2200, a: 0.001, len: 0.035, peak: 0.3 }); v.tone({ f: 520, f2: 300, glide: 0.04, a: 0.001, len: 0.05, peak: 0.08 }); }, { verb: 0.1 });
SOUND.define("paper-popup", (v) => {
  v.tone({ f: 260, fpath: [[0.05, 420], [0.12, 360], [0.2, 400]], a: 0.003, len: 0.3, peak: 0.16 }); v.noise({ filter: "bandpass", f: 1800, q: 1, a: 0.001, len: 0.04, peak: 0.25 });
}, { verb: 0.25 });

function score(k) {
  const notes = SOUND.scale("F3", "pent", 10);
  k.bed("room", 0, DUR, { gain: 0.8 });
  [0.15, 0.27, 0.39, 0.51].forEach((at, i) => k.at(at + 0.3, "paper-popup", { pitch: i * 2, gain: 0.45, pan: [-0.5, -0.2, 0.2, 0.5][i] }));
  k.at(0.75, "paper-tap", { gain: 0.9 }).at(0.93, "paper-tap", { pitch: 2, gain: 0.9 }).at(1.2, "paper-tap", { pitch: 4, gain: 0.6 });
  k.seq(0.4, 0.3, [notes[2], notes[4], notes[5], notes[7]], { voice: "pluck", gain: 0.3 });
  [[1.6, 0.8], [3.85, 0.7], [6.0, 0.75], [10.05, 0.8]].forEach(([at, d]) => k.at(at, "paper-rub", { dur: d, gain: 0.9 }));
  k.at(1.95, "paper-popup", { gain: 0.6 }).at(3.1, "paper-slide", { dur: 0.65, gain: 0.8 });
  k.custom(2.2, (v) => v.tone({ type: "sawtooth", f: 210, fpath: [[0.3, 230], [0.8, 205], [1.6, 220]], a: 0.2, hold: 1.2, len: 0.4, peak: 0.018 }), {});
  [2.6, 2.85, 3.05, 3.55, 4.75, 4.82, 4.89].forEach((at, i) => k.at(at, "paper-tap", { pitch: i % 4, gain: 0.75 }));
  k.at(5.5, "flip", { dur: 0.35, gain: 0.5 }).at(5.95, "pluck", { note: notes[7], gain: 0.4 });
  [5.73, 5.82, 5.91].forEach((at, i) => k.at(at, "paper-flick", { pitch: i * 2 }));
  [6.6, 6.72, 6.84].forEach((at, i) => k.at(at, "paper-popup", { pitch: i * 2, gain: 0.4 }));
  [6.85, 7.45, 8.05].forEach((at, i) => k.at(at, "paper-tap").at(at + 0.05, "pluck", { note: notes[3 + i * 2], gain: 0.4 }));
  k.at(7.5, "rustle", { dur: 0.6, gain: 0.25 }).at(8.6, "paper-popup", { gain: 0.9, pitch: -3 }).at(9.15, "paper-tap", { gain: 1, pitch: -2 });
  k.chord(9.2, [notes[5], notes[7], notes[9]], { voice: "pluck", strum: 0.06, gain: 0.45 });
  k.at(10.5, "paper-popup", { gain: 0.5 }).at(10.65, "paper-popup", { pitch: 3, gain: 0.35 }).at(11.35, "paper-tap").at(11.5, "paper-tap", { pitch: 2 }).at(11.85, "paper-tap", { pitch: 4, gain: 0.6 });
  k.seq(11.5, 0.16, [notes[4], notes[5], notes[7], notes[9]], { voice: "pluck", gain: 0.35 });
}

Player.register({
  id: "paper-layers", name: "Layered Paper", duration: DUR,
  fonts: { href: "https://fonts.googleapis.com/css2?family=Bowlby+One&family=Nunito:wght@800;900&display=swap", faces: ['400 20px "Bowlby One"', '900 20px "Nunito"'] },
  beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three steps", "Sealed", "Close"],
  stills: [1.5, 3.8, 6.0, 8.3, 9.6, 12.2],
  draw, score,
});
})();
