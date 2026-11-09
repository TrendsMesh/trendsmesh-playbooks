/* 16 Retro Paint Desktop. Topic (replace it): how a screen mixes colour.
 * Rendering (keep it): a 1990s desktop in a small buffer (short side ~360 px), whole-pixel rects only, blown up
 * nearest-neighbour; a paint canvas that is a real pixel array (wobbly strokes, true flood fills, on/off lettering).
 * Chrome text is 16 buffer px and stays in the text-safe box; the taskbar (unsafe band) has icons only. */
(function () {
"use strict";
const B = window.Brush;

// --- palette and type (from the card)
const PAL = { wall: "#0e7c7b", chrome: "#c3c3c3", shadow: "#7d7d7d", title: "#0a1a84", hi: "#fcfcfc", ink: "#0a0a0a", red: "#e8141b", yellow: "#f6e43a", pale: "#dfdfdf" };
const I = PAL.ink, HI = PAL.hi, CH = PAL.chrome; const LIGHT = { r: "#e8141b", g: "#1cc22c", b: "#1f46e8" };
const SWATCH = [
  ["#0a0a0a", "#7d7d7d", "#7d0a0a", "#7d7d0a", "#0a7d0a", "#0a7d7d", "#0a1a84", "#7d0a7d", "#7d7d3a", "#0a3a3a", "#0a7dfc", "#0a3a7d", "#3a0afc", "#7d3a0a"],
  ["#fcfcfc", "#c3c3c3", LIGHT.r, PAL.yellow, LIGHT.g, "#2fe0e0", LIGHT.b, "#e02fe0", "#f6f07d", "#2ffc7d", "#7dfcfc", "#7d7dfc", "#fc0a7d", "#fc7d3a"],
];
const SW = { black: [0, 0], red: [1, 2], yellow: [1, 3], green: [1, 4], blue: [1, 6] };
const UIF = "Pixelify Sans", HAND = "Gaegu", U = 16; // U: Pixelify on its own 16 px grid, so every glyph is crisp
const DUR = 13.5, BEATS = [0, 2.45, 5.5, 7.75, 10.15, 11.45];

// --- the script (and the score): doc jobs paint page pg at page fractions [u, v, dx, dy]; UI jobs move the pointer
const T_WIN = [0.2, 0.36, 99, 99], T_DLG = [5.62, 5.8, 7.52, 7.66], T_MSG = [11.5, 11.66, 13.18, 13.32];
function script(P) {
  const pk = (l, p) => (P ? p : l), J = [], add = (o) => J.push(Object.assign({ c: I, s: 2 }, o));
  const pick = (name, t) => add({ k: "swatch", sw: SW[name], t0: t, t1: t + 0.04 });
  // 1. title: open the window, a box, a bucket fill, typed lettering, a red underline
  add({ k: "dbl", t0: 0.02, t1: 0.16 });
  add({ k: "rect", pg: 0, a: pk([0.06, 0.13], [0.07, 0.06]), b: pk([0.94, 0.85], [0.93, 0.88]), t0: 0.42, t1: 0.62 });
  pick("yellow", 0.64); add({ k: "fill", pg: 0, at: [0.1, 0.5], c: PAL.yellow, t0: 0.7, t1: 0.7 });
  add({ k: "text", pg: 0, at: [0.5, pk(0.45, 0.46)], lines: pk(["How a screen", "mixes colour"], ["How a", "screen mixes", "colour"]), size: pk(40, 36), t0: 0.76, t1: 1.2 });
  pick("red", 1.6);
  add({ k: "brush", pg: 0, pts: pk([[0.3, 0.74], [0.45, 0.765], [0.6, 0.73], [0.72, 0.755]], [[0.2, 0.77], [0.4, 0.795], [0.6, 0.76], [0.8, 0.785]]), c: PAL.red, s: 3, seed: 4, t0: 1.7, t1: 1.9 });
  // 2. diagram: a pixel, a label, stripes filled, an arrow, a ring (dragged up-left: the pointer leaves clear)
  add({ k: "scroll", from: 0, to: 1, t0: 2.5, t1: 2.85 });
  const tri = pk({ a: [0.06, 0.1], b: [0.38, 0.88] }, { a: [0.14, 0.06], b: [0.86, 0.55] }); pick("black", 2.9);
  add({ k: "rect", pg: 1, a: tri.a, b: tri.b, t0: 2.98, t1: 3.22 });
  [1, 2].forEach((i) => {
    const u = B.lerp(tri.a[0], tri.b[0], i / 3);
    add({ k: "pencil", pg: 1, pts: [[u, tri.a[1] - 0.025], [u + 0.004, tri.b[1] + 0.03]], c: I, s: 2, seed: i, t0: 3.76 + (i - 1) * 0.16, t1: 3.86 + (i - 1) * 0.16 });
  });
  ["red", "green", "blue"].forEach((name, i) => {
    pick(name, 4.06 + i * 0.18);
    add({ k: "fill", pg: 1, at: [B.lerp(tri.a[0], tri.b[0], (i + 0.5) / 3), B.lerp(tri.a[1], tri.b[1], 0.5)], c: LIGHT[name[0]], t0: 4.12 + i * 0.18, t1: 4.12 + i * 0.18 });
  });
  pick("black", 4.6);
  add({ k: "text", pg: 1, at: pk([0.71, 0.3], [0.5, 0.79]), lines: ["1 pixel =", "3 tiny lights"], size: 30, t0: 3.28, t1: 3.7 });
  add({ k: "arrow", pg: 1, a: pk([0.54, 0.47], [0.5, 0.68]), b: pk([0.405, 0.52], [0.5, 0.57]), t0: 4.8, t1: 5.02 });
  pick("red", 5.08);
  add({ k: "ellipse", pg: 1, a: pk([0.42, 0.97], [0.95, 0.615]), b: pk([0.025, 0.025], [0.05, 0.015]), c: PAL.red, s: 2, t0: 5.18, t1: 5.4 });
  // 3. key number: the Edit Colours dialog, three trackbars, the counter
  add({ k: "dbl", ui: "cur", t0: 5.5, t1: 5.6 });
  [230, 160, 40].forEach((v1, ch) => add({ k: "drag", ch, v0: 0, v1, t0: 5.9 + ch * 0.27, t1: 6.08 + ch * 0.25 }));
  add({ k: "click", ui: "ok", t0: 7.44, t1: 7.52 });
  // 4-5. steps: three pasted copies of the pixel, lit differently, then each explained
  add({ k: "scroll", from: 1, to: 2, t0: 7.78, t1: 8.1 });
  const steps = [{ lit: [1, 0, 0], fill: "red", label: "red" }, { lit: [1, 1, 0], fill: "yellow", label: "yellow" }, { lit: [1, 1, 1], fill: null, label: "white!" }];
  steps.forEach((st, i) => {
    const m = P ? 0.17 + i * 0.33 : (i + 0.5) / 3, b = [8.76, 9.42, 10.22][i];
    const G = P
      ? { ta: [0.04, m - 0.13], tb: [0.26, m + 0.13], aa: [0.3, m], ab: [0.42, m], c: [0.55, m], ru: 0.09, lab: [0.81, m] }
      : { ta: [m - 0.125, 0.08], tb: [m - 0.025, 0.46], aa: [m - 0.075, 0.5], ab: [m - 0.075, 0.615], c: [m - 0.075, 0.79], ru: 0.054, lab: [m + 0.088, 0.27] };
    add({ k: "stamp", pg: 2, a: G.ta, b: G.tb, lit: st.lit, t0: 8.2 + i * 0.18, t1: 8.32 + i * 0.18 });
    add({ k: "arrow", pg: 2, a: G.aa, b: G.ab, t0: b, t1: b + 0.15 });
    add({ k: "ellipse", pg: 2, a: [G.c[0] - G.ru, G.c[1]], b: [G.c[0] + G.ru + 0.006, G.c[1]], round: true, t0: b + 0.18, t1: b + 0.3 });
    add({ k: "text", pg: 2, at: G.lab, lines: [st.label], size: pk(24, 28), t0: b + 0.33, t1: b + 0.45 });
    if (st.fill) {
      pick(st.fill, b + 0.49);
      add({ k: "fill", pg: 2, at: G.c, c: st.fill === "red" ? LIGHT.r : PAL.yellow, t0: b + 0.55, t1: b + 0.55 });
      pick("black", b + 0.58);
    } else {
      pick("green", b + 0.49);
      add({ k: "brush", pg: 2, pts: [[G.c[0], G.c[1], -12, 1], [G.c[0], G.c[1], -3, 10], [G.c[0], G.c[1], 15, -14]], c: LIGHT.g, s: 3, seed: 9, t0: b + 0.56, t1: b + 0.72 });
    }
  });
  // 6. close: the takeaway box
  add({ k: "click", ui: "msgok", t0: 13.1, t1: 13.18 });
  return J.sort((a, b) => a.t0 - b.t0);
}

// --- the screen buffer: whole-pixel drawing only
let g = null; const rd = Math.round;
// digits in Jersey 10 at 18 / 36 px (crisp there; Pixelify's 5 reads as S)
const jt = (str, x, base, o = {}) => utext(str, x, base, Object.assign({ fam: "Jersey 10", size: 18 }, o));
function R(x, y, w, h, c) {
  if (w <= 0 || h <= 0) return;
  if (c) g.fillStyle = c;
  g.fillRect(rd(x), rd(y), rd(w), rd(h));
}
function bres(x0, y0, x1, y1, plot) {
  x0 = rd(x0); y0 = rd(y0); x1 = rd(x1); y1 = rd(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let err = dx + dy;
  for (let i = 0; i < 5000; i++) {
    plot(x0, y0, i);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}
function gline(x0, y0, x1, y1, c, s = 1, dotted = false) {
  g.fillStyle = c; const o = (s - 1) >> 1;
  bres(x0, y0, x1, y1, (x, y, i) => (!dotted || i % 2 === 0) && g.fillRect(x - o, y - o, s, s));
}
function gpoly(pts, c, s = 1, dotted = false) {
  for (let i = 0; i < pts.length - 1; i++) gline(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c, s, dotted);
}
const ellPts = (cx, cy, rx, ry) => {
  const n = Math.max(16, rd((rx + ry) * 3)), pts = [];
  for (let i = 0; i <= n; i++) pts.push([rd(cx + Math.cos((i / n) * B.TAU) * rx), rd(cy + Math.sin((i / n) * B.TAU) * ry)]);
  return pts;
};
function gellipse(cx, cy, rx, ry, c, fill = false) {
  if (!fill) return gpoly(ellPts(cx, cy, rx, ry), c);
  for (let dy = -ry; dy <= ry; dy++) {
    const hw = rd(rx * Math.sqrt(Math.max(0, 1 - (dy / (ry + 0.5)) ** 2))); R(cx - hw, cy + dy, 2 * hw + 1, 1, c);
  }
}
function bevel(x, y, w, h, sunken = false, fill = CH) {
  if (fill) R(x, y, w, h, fill);
  const [o1, i1, i2, o2] = sunken ? [PAL.shadow, I, PAL.pale, HI] : [PAL.pale, HI, PAL.shadow, I];
  R(x, y, w, 1, o1); R(x, y, 1, h, o1); R(x + 1, y + 1, w - 2, 1, i1); R(x + 1, y + 1, 1, h - 2, i1);
  R(x + 1, y + h - 2, w - 2, 1, i2); R(x + w - 2, y + 1, 1, h - 2, i2); R(x, y + h - 1, w, 1, o2); R(x + w - 1, y, 1, h, o2);
}
// 2x2 dither: the only tone this medium has
function checker(x, y, w, h, c1 = HI, c2 = CH) {
  const tile = B.layer("pd-check:" + c1 + c2, 2, 2, (q) => {
    q.fillStyle = c2; q.fillRect(0, 0, 2, 2); q.fillStyle = c1; q.fillRect(0, 0, 1, 1); q.fillRect(1, 1, 1, 1);
  });
  g.fillStyle = g.createPattern(tile, "repeat"); g.fillRect(rd(x), rd(y), rd(w), rd(h));
}
const box = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]];
const dotRect = (x, y, w, h, c = I) => gpoly(box(x, y, w - 1, h - 1), c, 1, true);

// --- hard-threshold text
/** Glyph image thresholded on/off, plus its mask for the canvas. */
function glyph(str, size, fam, weight, color) {
  const font = B.font(size, fam, weight), m = B.scratch("pd-measure", 4, 4); m.font = font;
  const adv = Math.ceil(m.measureText(str).width);
  const c = B.layer("pd-glyph|" + font + "|" + color + "|" + str, adv + 5, Math.ceil(size * 1.45), (q, cw, ch) => {
    q.font = font; q.fillStyle = "#000"; q.fillText(str, 2, rd(size * 1.05));
    const img = q.getImageData(0, 0, cw, ch), d = img.data, mask = new Uint8Array(cw * ch), [r, gg, b] = B.rgb(color);
    for (let i = 0; i < cw * ch; i++) {
      const on = d[i * 4 + 3] >= 150; mask[i] = on ? 1 : 0;
      d[i * 4] = r; d[i * 4 + 1] = gg; d[i * 4 + 2] = b; d[i * 4 + 3] = on ? 255 : 0;
    }
    q.putImageData(img, 0, 0); q.canvas._mask = mask;
  });
  return Object.assign(c, { _adv: adv });
}
function utext(str, x, base, o = {}) {
  if (!str) return 0;
  const size = o.size ?? U, c = glyph(str, size, o.fam || UIF, o.weight ?? 400, o.color || I);
  const x0 = o.align === "center" ? x - c._adv / 2 : o.align === "right" ? x - c._adv : x;
  g.drawImage(c, rd(x0) - 2, rd(base) - rd(size * 1.05));
  return c._adv;
}
const uw = (str, size = U, weight = 400) => glyph(str, size, UIF, weight, I)._adv;

// --- the paint canvas: a real pixel array (Uint32 ABGR)
const DOC = { w: 0, h: 0, px: null, img: null }; const c32cache = new Map();
function C32(hex) {
  if (!c32cache.has(hex)) { const [r, gg, b] = B.rgb(hex); c32cache.set(hex, ((255 << 24) | (b << 16) | (gg << 8) | r) >>> 0); }
  return c32cache.get(hex);
}
function docReset(w, h) {
  if (DOC.w !== w || DOC.h !== h) {
    DOC.w = w; DOC.h = h; DOC.px = new Uint32Array(w * h); DOC.img = new ImageData(new Uint8ClampedArray(DOC.px.buffer), w, h);
  }
  DOC.px.fill(C32(HI));
}
function dplot(x, y, c, s = 1) {
  const o = (s - 1) >> 1;
  for (let j = 0; j < s; j++)
    for (let i = 0; i < s; i++) {
      const xx = x - o + i, yy = y - o + j;
      if (xx >= 0 && yy >= 0 && xx < DOC.w && yy < DOC.h) DOC.px[yy * DOC.w + xx] = c;
    }
}
const dline = (a, b, c, s) => bres(a[0], a[1], b[0], b[1], (x, y) => dplot(x, y, c, s));
const dpoly = (p, c, s) => { for (let i = 0; i < p.length - 1; i++) dline(p[i], p[i + 1], c, s); };
const drect = (a, b, c, s) => dpoly([a, [b[0], a[1]], b, [a[0], b[1]], a], c, s);
const dellipse = (a, b, c, s) => dpoly(ellPts((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.abs(b[0] - a[0]) / 2, Math.abs(b[1] - a[1]) / 2), c, s);
/** Bucket fill: stops only at a closed edge, leaks through gaps. */
function dflood(x, y, c) {
  const { w, h, px } = DOC; x = rd(x); y = rd(y);
  if (x < 0 || y < 0 || x >= w || y >= h) return;
  const target = px[y * w + x];
  if (target === c) return;
  const stack = [x, y];
  while (stack.length) {
    const y0 = stack.pop(), x0 = stack.pop(); let lx = x0, up = false, down = false;
    while (lx > 0 && px[y0 * w + lx - 1] === target) lx--;
    for (let xx = lx; xx < w && px[y0 * w + xx] === target; xx++) {
      px[y0 * w + xx] = c;
      if (y0 > 0) { const m = px[(y0 - 1) * w + xx] === target; if (m && !up) stack.push(xx, y0 - 1); up = m; }
      if (y0 < h - 1) { const m = px[(y0 + 1) * w + xx] === target; if (m && !down) stack.push(xx, y0 + 1); down = m; }
    }
  }
}
function dtext(str, x, base, size, color) {
  if (!str) return;
  const c = glyph(str, size, HAND, 700, color), mask = c._mask, cw = c.width, col = C32(color);
  const ox = rd(x) - 2, oy = rd(base) - rd(size * 1.05);
  for (let j = 0; j < c.height; j++) for (let i = 0; i < cw; i++) if (mask[j * cw + i]) dplot(ox + i, oy + j, col, 1);
}
function textLayout(j) {
  const lh = rd(j.size * 1.05), total = lh * j.lines.length, top = j.AT[1] - total / 2;
  const rows = j.lines.map((ln, i) => {
    const adv = glyph(ln, j.size, HAND, 700, j.c)._adv;
    return { str: ln, x: rd(j.AT[0] - adv / 2), base: rd(top + (i + 0.8) * lh), adv };
  });
  const x0 = Math.min(...rows.map((r) => r.x)) - 4, x1 = Math.max(...rows.map((r) => r.x + r.adv)) + 5;
  return { rows, box: [x0, rd(top) - 3, x1, rd(top + total) + 4] };
}
/** One pixel as a pasted copy: lit stripes in colour, unlit ones dark. */
function dtriad(a, b, lit) {
  const ink = C32(I), cols = [LIGHT.r, LIGHT.g, LIGHT.b]; drect(a, b, ink, 2);
  for (let k = 1; k < 3; k++) { const x = rd(B.lerp(a[0], b[0], k / 3)); dline([x, a[1]], [x, b[1]], ink, 2); }
  for (let k = 0; k < 3; k++) dflood(B.lerp(a[0], b[0], (k + 0.5) / 3), (a[1] + b[1]) / 2, lit[k] ? C32(cols[k]) : ink);
}
/** Mouse hand: 1-px steps with a slow sideways wobble. */
function mouseTrail(pts, seed) {
  const out = [];
  for (let i = 0, walked = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], dx = x1 - x0, dy = y1 - y0, len = Math.hypot(dx, dy) || 1;
    for (let k = 0; k <= len; k++, walked++) {
      const f = k / len, w = B.noise1(walked * 0.07, seed) * 1.4;
      out.push([rd(x0 + dx * f - (dy / len) * w), rd(y0 + dy * f + (dx / len) * w)]);
    }
  }
  return out;
}

// --- layout per aspect (buffer px) and the resolved script
let SC = null;
function scene(W, H) {
  if (SC && SC.W === W && SC.H === H) return SC;
  const P = H > W, cell = Math.max(2, rd(Math.min(W, H) / 360)); const bw = Math.ceil(W / cell), bh = Math.ceil(H / cell);
  const T = { x: Math.ceil((W * 0.035) / cell), y: Math.ceil((H * (P ? 0.145 : 0.055)) / cell), r: Math.floor((W * 0.965) / cell), b: Math.floor((H * (P ? 0.795 : 0.945)) / cell) };
  // 9:16: icons on top, captions just inside the text-safe box; status bar inside it, colour strip docked below
  const win = P ? { x: T.x - 6, y: T.y + 23, w: bw - 2 * (T.x - 6) } : { x: 84, y: T.y - 2, w: bw - 98 };
  win.h = bh - 26 - win.y; const cy0 = win.y + 46, S = { W, H, P, cell, bw, bh, T, win, tb: P ? 44 : 22, tool: { x: win.x + 4, y: cy0 } };
  const st = (S.status = { x: win.x + 4, y: P ? T.b - 22 : win.y + win.h - 24, w: win.w - 8, h: 20 }), swY = P ? st.y + 24 : st.y - 30;
  if (P) win.h = swY + 30 - win.y;
  S.cur = { x: win.x + 4, y: swY, w: 26, h: 26 }; S.swatch = (sw) => [win.x + 34 + sw[1] * 13, swY + sw[0] * 13];
  S.frame = { x: win.x + 42, y: cy0, w: win.w - 46, h: (P ? st.y : swY) - 3 - cy0 };
  const f = S.frame, view = (S.view = { x: f.x + 2, y: f.y + 2, w: f.w - 4, h: f.h - 17 });
  S.sbar = { x: view.x, y: view.y + view.h, w: view.w, h: 13 };
  Object.assign(S, { VW: view.w, VH: view.h, DW: view.w * 3, rest: [rd(bw * 0.62), rd(bh * 0.6)] });
  S.icons = [0, 1, 2].map((i) => (P ? { x: 30 + i * 70, y: T.y - 34 } : { x: 30, y: T.y + 4 + i * 60 }));
  const dw = P ? T.r - T.x : 420, dh = 266;
  const dx = B.clamp(rd(win.x + win.w / 2 - dw / 2), T.x, T.r - dw), dy = P ? view.y + 36 : rd(win.y + win.h / 2 - dh / 2 + 8);
  const gb = { x: dx + 10, y: dy + 38, w: dw - 20, h: 94 };
  S.dlg = { x: dx, y: dy, w: dw, h: dh, group: gb, num: 36, ok: { x: dx + dw - 86, y: dy + dh - 32, w: 76, h: 24 } };
  S.dlg.track = (ch) => ({ x0: gb.x + 70, x1: gb.x + gb.w - 72, y: gb.y + 24 + ch * 26 });
  S.dlg.thumb = (ch, v) => { const tr = S.dlg.track(ch); return [rd(B.lerp(tr.x0, tr.x1, v / 255)), tr.y]; };
  // the takeaway box covers whole rows of the drawing, never slices one
  const ms = P ? 16 : U, mw = P ? T.r - T.x : view.w + 8, lines = MSG[+P], mh = P ? rd(view.h * 0.5 + 48) : 50 + lines.length * (ms + 5) + 34;
  S.msg = { x: P ? T.x : view.x - 4, y: P ? view.y + 2 : rd(view.y + view.h * 0.47), w: mw, h: mh, lines, ms, pad: (mh - 84 - lines.length * (ms + 5)) / 2 };
  S.msg.ok = { x: S.msg.x + mw / 2 - 38, y: S.msg.y + mh - 32, w: 76, h: 24 };
  S.ui = { cur: [S.cur.x + 8, S.cur.y + 8], ok: [S.dlg.ok.x + 38, S.dlg.ok.y + 12], msgok: [S.msg.ok.x + 38, S.msg.ok.y + 12] };
  S.jobs = script(P).map((j) => {
    const P2 = (q) => [j.pg * S.VW + rd(q[0] * S.VW) + (q[2] || 0), rd(q[1] * S.VH) + (q[3] || 0)];
    const r = Object.assign({}, j, { doc: j.pg != null });
    if (j.a) r.A = P2(j.a);
    if (j.b) r.Bp = P2(j.b);
    if (j.round) { const rx = (r.Bp[0] - r.A[0]) / 2; r.A[1] -= rx; r.Bp[1] += rx; }
    if (j.at) r.AT = P2(j.at);
    if (j.pts) r.trail = mouseTrail(j.pts.map(P2), j.seed || 1);
    if (j.k === "arrow") {
      // crude two-stroke V head, not quite symmetric
      const ang = Math.atan2(r.Bp[1] - r.A[1], r.Bp[0] - r.A[0]);
      [r.h1, r.h2] = [[-0.55, 10], [0.48, 9]].map(([da, l]) => [rd(r.Bp[0] - Math.cos(ang + da) * l), rd(r.Bp[1] - Math.sin(ang + da) * l)]);
    }
    return r;
  });
  return (SC = S);
}
const MSG = [["Every colour on your screen is just red, green", "and blue light, mixed inside each tiny pixel."],
  ["Every colour on your screen is", "just red, green and blue light,", "mixed inside each tiny pixel."]];
const TOOL_OF = { stamp: 0, fill: 1, pencil: 2, brush: 3, text: 4, arrow: 5, rect: 6, ellipse: 7 };

// --- time helpers
function scrollAt(S, t) {
  let off = 0;
  for (const j of S.jobs.filter((q) => q.k === "scroll")) {
    if (t >= j.t1) off = j.to;
    else if (t > j.t0) off = j.from + (j.to - j.from) * (Math.floor(B.ease.inOutQuad((t - j.t0) / (j.t1 - j.t0)) * 6 + 1e-6) / 6);
  }
  return rd(off * S.VW);
}
function thumbRect(S, off) {
  const tx = S.sbar.x + 13, tw = S.sbar.w - 26, w = Math.max(14, rd((tw * S.VW) / S.DW));
  return { x: rd(tx + ((tw - w) * off) / (S.DW - S.VW)), y: S.sbar.y, w, h: S.sbar.h };
}
const inView = (S, [x, y]) => x >= S.view.x && x < S.view.x + S.view.w && y >= S.view.y && y < S.view.y + S.view.h;
const jp = (j, t) => (j.t1 > j.t0 ? B.clamp((t - j.t0) / (j.t1 - j.t0)) : t >= j.t0 ? 1 : 0);
/** Line-tool arrow strokes so far: shaft, then a crude V head. */
const arrowSegs = (j, p) => [[j.A, lerpPt(j.A, j.Bp, B.clamp(p / 0.6))]].concat(p > 0.62 ? [[j.Bp, lerpPt(j.Bp, j.h1, B.clamp((p - 0.62) / 0.16))]] : [], p > 0.82 ? [[j.Bp, lerpPt(j.Bp, j.h2, B.clamp((p - 0.82) / 0.16))]] : []);
const lerpPt = (a, b, p) => [rd(B.lerp(a[0], b[0], p)), rd(B.lerp(a[1], b[1], p))];
function latest(S, t, test, val, v) {
  for (const j of S.jobs) if (test(j) && t >= j.t0) v = val(j);
  return v;
}
const sliderValue = (S, ch, t) => latest(S, t, (j) => j.k === "drag" && j.ch === ch, (j) => rd(B.lerp(j.v0, j.v1, jp(j, t))), 0);
const currentColour = (S, t) => latest(S, t, (j) => j.k === "swatch", (j) => SWATCH[j.sw[0]][j.sw[1]], I);
const activeTool = (S, t) => latest(S, t + 0.12, (j) => j.doc, (j) => TOOL_OF[j.k], 2);
function tip(S, j, p) {
  const at = j.t0 + p * (j.t1 - j.t0), toScreen = (d) => [S.view.x + d[0] - scrollAt(S, at), S.view.y + d[1]];
  switch (j.k) {
    case "dbl": return j.ui ? S.ui[j.ui] : [S.icons[0].x + 16, S.icons[0].y + 14];
    case "swatch": { const [x, y] = S.swatch(j.sw); return [x + 6, y + 6]; }
    case "click": return S.ui[j.ui];
    case "scroll": { const r = thumbRect(S, scrollAt(S, at)); return [r.x + r.w / 2, r.y + 6]; }
    case "drag": return S.dlg.thumb(j.ch, B.lerp(j.v0, j.v1, p));
    case "rect": case "ellipse": return toScreen(lerpPt(j.A, j.Bp, p));
    case "arrow": return toScreen(arrowSegs(j, p).pop()[1]);
    case "pencil": case "brush": return toScreen(j.trail[Math.min(j.trail.length - 1, Math.floor(p * (j.trail.length - 1)))]);
    case "fill": return toScreen(j.AT);
    case "text": { const L = textLayout(j); return toScreen([L.box[0] + 2, L.box[1] + 6]); }
    case "stamp": return toScreen(lerpPt(j.A, j.Bp, 0.5));
  }
  return S.rest;
}
/** The pointer rides the active job's tip, else moves briskly to the next job. */
function pointer(S, t) {
  let prev = null, next = null;
  for (const j of S.jobs) {
    if (t >= j.t0 && t <= j.t1) return tip(S, j, jp(j, t));
    if (j.t1 < t) prev = j;
    else if (j.t0 > t && !next) next = j;
  }
  const from = prev ? tip(S, prev, 1) : S.rest;
  if (!next) return from;
  const to = tip(S, next, 0), start = Math.max(prev ? prev.t1 : 0, next.t0 - 0.26);
  return lerpPt(from, to, B.ease.inOutQuad(B.clamp((t - start) / Math.max(0.01, next.t0 - start))));
}

// --- pixel sprites
const ARROW = ["X", "XX", "XWX", "XWWX", "XWWWX", "XWWWWX", "XWWWWWX", "XWWWWWWX", "XWWWWWWWX",
  "XWWWWWWWWX", "XWWWWWXXXXX", "XWWXWWX", "XWX.XWWX", "XX..XWWX", "X....XWWX", ".....XWWX", "......XX"];
const IBEAM = ["XXX.XXX"].concat(new Array(12).fill("...X..."), ["XXX.XXX"]);
const LETTER_A = ["..XX", ".X..X", "X....X", "XXXXXX", "X....X", "X....X", "X....X"]; const SPR = { X: I, W: HI };
function drawPointer(kind, x, y) {
  if (kind === "cross") { R(x - 7, y, 5, 1, I); R(x + 3, y, 5, 1, I); R(x, y - 7, 1, 5, I); R(x, y + 3, 1, 5, I); }
  else if (kind === "ibeam") B.sprite(g, IBEAM, x - 3, y - 7, 1, SPR);
  else if (kind === "glass") for (let k = 0; k < 7; k++) for (const yy of [y - 7 + k, y + 6 - k]) { R(x - 6 + k, yy, 13 - 2 * k, 1, I); R(x - 5 + k, yy, 11 - 2 * k, 1, k ? HI : I); }
  else B.sprite(g, ARROW, x, y, 1, SPR);
}
function iconArt(i, x, y) {
  if (i === 0) { // easel, folder, bin
    R(x + 4, y + 3, 24, 19, I); R(x + 5, y + 4, 22, 17, HI);
    R(x + 7, y + 6, 6, 5, PAL.red); R(x + 14, y + 10, 6, 5, PAL.yellow); R(x + 8, y + 13, 5, 5, PAL.title);
    gline(x + 9, y + 22, x + 6, y + 30, I, 2); gline(x + 23, y + 22, x + 26, y + 30, I, 2);
    gline(x + 18, y + 19, x + 28, y + 8, PAL.shadow, 2); R(x + 17, y + 19, 3, 3, I);
  } else if (i === 1) {
    R(x + 3, y + 7, 11, 4, I); R(x + 3, y + 10, 26, 18, I); R(x + 4, y + 11, 24, 16, "#f6d33a");
  } else {
    R(x + 7, y + 6, 18, 3, I); R(x + 13, y + 4, 6, 2, I); R(x + 8, y + 9, 16, 19, I); R(x + 9, y + 10, 14, 17, CH);
  }
}
const ICON_NAMES = ["Paint", "Files", "Bin"];
/** Toolbox glyphs: marquee, bucket, pencil, brush, text, line, rect, ellipse. */
function toolGlyph(i, x, y) {
  switch (i) {
    case 0: dotRect(x + 3, y + 3, 10, 9); break;
    case 1: gpoly([[x + 3, y + 7], [x + 8, y + 2], [x + 13, y + 7], [x + 8, y + 12], [x + 3, y + 7]], I); R(x + 2, y + 8, 2, 4, PAL.red); break;
    case 2: gline(x + 4, y + 11, x + 11, y + 4, PAL.yellow, 3); gline(x + 3, y + 12, x + 4, y + 11, I, 2); gline(x + 11, y + 3, x + 12, y + 2, I, 2); break;
    case 3: gline(x + 8, y + 7, x + 12, y + 3, I); R(x + 3, y + 9, 5, 3, I); R(x + 5, y + 8, 3, 1, I); break;
    case 4: B.sprite(g, LETTER_A, x + 5, y + 4, 1, SPR); break;
    case 5: gline(x + 3, y + 12, x + 12, y + 3, I); break;
    case 6: gpoly(box(x + 3, y + 4, 9, 7), I); break;
    case 7: gellipse(x + 7, y + 7, 5, 4, I); break;
  }
}

// --- window chrome
/** Window slab: bevel, title strip (navy when active), bold caption, caption buttons. */
const miniIcon = (x, y) => { R(x, y, 12, 12, I); R(x + 1, y + 1, 10, 10, HI); R(x + 2, y + 2, 4, 3, PAL.red); R(x + 6, y + 5, 4, 4, PAL.yellow); };
function windowFrame(x, y, w, h, title, active = true, icon = false) {
  const bx = x + w - 52, by = y + 6; bevel(x, y, w, h); R(x + 3, y + 3, w - 6, 20, active ? PAL.title : PAL.shadow);
  if (icon) miniIcon(x + 6, y + 7);
  utext(title, x + (icon ? 22 : 7), y + 18, { weight: 700, color: active ? HI : CH });
  bevel(bx, by, 15, 13); R(bx + 4, by + 8, 7, 2, I);
  bevel(bx + 15, by, 15, 13); R(bx + 18, by + 2, 9, 8, I); R(bx + 19, by + 4, 7, 5, CH); bevel(bx + 32, by, 15, 13);
  gline(bx + 36, by + 4, bx + 41, by + 9, I, 2); gline(bx + 41, by + 4, bx + 36, by + 9, I, 2);
}
function button(r, label, o = {}) {
  let { x, y, w, h } = r;
  if (o.isDefault) { R(x, y, w, h, I); x++; y++; w -= 2; h -= 2; }
  if (o.pressed) { R(x, y, w, h, PAL.shadow); R(x + 1, y + 1, w - 2, h - 2, CH); } else bevel(x, y, w, h);
  const d = o.pressed ? 1 : 0; utext(label, x + w / 2 + d, y + h / 2 + 5 + d, { align: "center" });
  if (o.isDefault) dotRect(x + 3 + d, y + 3 + d, w - 6, h - 6);
}
function groupBox(x, y, w, h, label) {
  for (const [c, d] of [[PAL.shadow, 0], [HI, 1]]) { R(x + d, y + d, w - 2, 1, c); R(x + d, y + d, 1, h - 2, c); R(x + d, y + h - 2 + d, w - 1, 1, c); R(x + w - 2 + d, y + d, 1, h - 1, c); }
  R(x + 7, y - 2, uw(label) + 6, 5, CH); utext(label, x + 10, y + 5);
}
/** Zoom-open: grey outlines racing from a source rect to the window. */
function zoomRects(src, dst, p) {
  for (let k = 0; k < 3; k++) {
    const q = B.clamp(p * 1.35 - k * 0.17);
    if (q <= 0 || q >= 1) continue;
    const L = (k) => B.lerp(src[k], dst[k], q); gpoly(box(L("x"), L("y"), L("w"), L("h")), CH);
  }
}

// --- the desktop, the paint window, the dialogs
function desktop(S, t) {
  R(0, 0, S.bw, S.bh, PAL.wall);
  S.icons.forEach((ic, i) => {
    iconArt(i, ic.x, ic.y); const lw = uw(ICON_NAMES[i]);
    if (i === 0 && t >= 0.03) { R(ic.x + 16 - lw / 2 - 2, ic.y + 35, lw + 4, 17, PAL.title); dotRect(ic.x + 16 - lw / 2 - 2, ic.y + 35, lw + 4, 17, HI); }
    utext(ICON_NAMES[i], ic.x + 16, ic.y + 48, { color: HI, align: "center" });
  });
  // taskbar: launcher, task button, a clock face (icons only)
  const ty = S.bh - S.tb; R(0, ty, S.bw, S.tb, CH); R(0, ty + 1, S.bw, 1, HI); bevel(2, ty + 3, 34, 17);
  [PAL.red, LIGHT.g, LIGHT.b, PAL.yellow].forEach((c, k) => R(12 + (k % 2) * 7, ty + 5 + (k >> 1) * 7, 6, 6, c));
  if (t >= T_WIN[1]) {
    bevel(40, ty + 3, 70, 17, true, null); checker(42, ty + 5, 66, 13); miniIcon(68, ty + 6);
  }
  const cx = S.bw - 30; bevel(cx - 6, ty + 3, 33, 17, true);
  gellipse(cx + 10, ty + 11, 6, 6, HI, true); gellipse(cx + 10, ty + 11, 6, 6, I);
  gline(cx + 10, ty + 11, cx + 10, ty + 7, I); gline(cx + 10, ty + 11, cx + 13, ty + 12, I);
}

function paintWindow(S, t, modal) {
  const { win, frame, view, sbar } = S, cur = S.cur;
  windowFrame(win.x, win.y, win.w, win.h, "untitled - Paint", !modal, true); let mx = win.x + 7;
  for (const m of ["File", "Edit", "View", "Image", "Colours", "Help"]) {
    const w = utext(m, mx, win.y + 39); R(mx, win.y + 42, uw(m[0]), 1, I); mx += w + (S.P ? 9 : 14);
  }
  // toolbox: the active tool pressed in with a checker; the swatches
  const tool = activeTool(S, t);
  for (let i = 0; i < 8; i++) {
    const x = S.tool.x + (i % 2) * 16, y = S.tool.y + Math.floor(i / 2) * 16, on = i === tool;
    bevel(x, y, 16, 16, on, on ? null : CH);
    if (on) checker(x + 2, y + 2, 12, 12);
    toolGlyph(i, x + (on ? 1 : 0), y + (on ? 1 : 0));
  }
  bevel(frame.x, frame.y, frame.w, frame.h, true, PAL.shadow); const off = scrollAt(S, t);
  g.drawImage(S.docCanvas, off, 0, S.VW, S.VH, view.x, view.y, S.VW, S.VH); checker(sbar.x, sbar.y, sbar.w, sbar.h);
  bevel(sbar.x, sbar.y, 13, 13); bevel(sbar.x + sbar.w - 13, sbar.y, 13, 13);
  for (let k = 0; k < 4; k++) { R(sbar.x + 4 + k, sbar.y + 6 - k, 1, 2 * k + 1, I); R(sbar.x + sbar.w - 5 - k, sbar.y + 6 - k, 1, 2 * k + 1, I); }
  const th = thumbRect(S, off); bevel(th.x, th.y, th.w, th.h); bevel(cur.x, cur.y, cur.w, cur.h, true, CH);
  checker(cur.x + 2, cur.y + 2, 22, 22); R(cur.x + 11, cur.y + 11, 11, 11, I); R(cur.x + 12, cur.y + 12, 9, 9, HI);
  R(cur.x + 4, cur.y + 4, 11, 11, I); R(cur.x + 5, cur.y + 5, 9, 9, currentColour(S, t));
  SWATCH.forEach((row, j) => row.forEach((c, i) => { const [x, y] = S.swatch([j, i]); bevel(x, y, 13, 13, true, c); R(x + 2, y + 2, 9, 9, c); }));
  // status bar: a help line and the pointer's x,y
  const st = S.status;
  if (!st) return;
  bevel(st.x, st.y, st.w - 94, st.h, true, CH); utext("Click and drag to paint.", st.x + 5, st.y + 15);
  bevel(st.x + st.w - 92, st.y, 92, st.h, true, CH); const pt = S.ptr;
  if (inView(S, pt)) jt(`${pt[0] - view.x + off},${pt[1] - view.y}`, st.x + st.w - 86, st.y + 15);
}

/** Canvas overlay: the dashed text box and its caret. */
function canvasOverlays(S, t) {
  const off = scrollAt(S, t), v = S.view;
  B.clip(g, (c) => c.rect(v.x, v.y, v.w, v.h), () => {
    for (const j of S.jobs.filter((q) => q.k === "text" && t >= q.t0 && t < q.t1 + 0.3)) {
      const L = textLayout(j), [x0, y0, x1, y1] = L.box; dotRect(v.x + x0 - off, v.y + y0, x1 - x0, y1 - y0);
      // the caret blinks once typing stops
      let left = Math.floor(jp(j, t) * j.lines.join("").length + 1e-6), row = L.rows[0], cx = row.x;
      for (const r of L.rows) {
        row = r;
        if (left <= r.str.length) { cx = r.x + (left ? glyph(r.str.slice(0, left), j.size, HAND, 700, j.c)._adv : 0); break; }
        left -= r.str.length;
      }
      if (t <= j.t1 || Math.floor((t - j.t1) * 4) % 2 === 0) R(v.x + cx - off + 1, v.y + row.base - j.size * 0.75, 1, rd(j.size * 0.85), I);
    }
  });
}

function colourDialog(S, t) {
  const d = S.dlg, gb = d.group; windowFrame(d.x, d.y, d.w, d.h, "Edit Colours"); groupBox(gb.x, gb.y, gb.w, gb.h, "Mix one pixel");
  ["Red", "Green", "Blue"].forEach((nm, ch) => {
    const tr = d.track(ch), v = sliderValue(S, ch, t), [tx] = d.thumb(ch, v); utext(nm, gb.x + 10, tr.y + 5);
    bevel(tr.x0 - 4, tr.y - 2, tr.x1 - tr.x0 + 8, 4, true, HI);
    for (let k = 0; k <= 8; k++) R(rd(B.lerp(tr.x0, tr.x1, k / 8)), tr.y + 8, 1, k % 4 === 0 ? 3 : 2, I);
    bevel(tx - 4, tr.y - 7, 9, 13); R(tx - 2, tr.y + 6, 5, 1, CH); R(tx - 1, tr.y + 7, 3, 1, I);
    bevel(gb.x + gb.w - 60, tr.y - 9, 50, 19, true, HI); jt(String(v), gb.x + gb.w - 15, tr.y + 6, { align: "right" });
  });
  const py = gb.y + gb.h + 10, cx = d.x + 84, vals = [0, 1, 2].map((ch) => sliderValue(S, ch, t));
  bevel(d.x + 10, py, 64, 64, true, HI); R(d.x + 12, py + 2, 60, 60, B.toHex(vals));
  // the key number counts up in a sunken field
  utext("Colours a pixel can show:", cx, py + 12); bevel(cx, py + 17, d.w - 94, d.num + 10, true, HI);
  if (t >= 6.62) {
    const p = B.prog(t, 6.62, 0.4), shown = p >= 1 ? 16777216 : rd((Math.pow(p, 2.2) * 16777216) / 997) * 997;
    jt(B.counter(1, shown), d.x + d.w - 18, py + 17 + d.num + 3, { size: d.num, align: "right" });
    jt("= 256 x 256 x 256", cx, py + d.num + 45);
  }
  button(d.ok, "OK", { isDefault: true, pressed: t >= 7.44 && t < 7.52 });
}

function messageBox(S, t) {
  const m = S.msg, x = m.x + 12, y = m.y + 32 + m.pad, blue = "#2050e0"; windowFrame(m.x, m.y, m.w, m.h, "Paint");
  gellipse(x + 12, y + 11, 12, 10, I, true); gellipse(x + 12, y + 11, 11, 9, blue, true);
  gline(x + 5, y + 19, x + 3, y + 25, I, 2); R(x + 11, y + 4, 3, 3, HI); R(x + 10, y + 9, 4, 10, HI);
  m.lines.forEach((ln, i) => utext(ln, m.x + 46, m.y + 44 + m.pad + i * (m.ms + 5), { size: m.ms }));
  button(m.ok, "OK", { isDefault: true, pressed: t >= 13.1 && t < 13.18 });
}

// --- the frame
function draw(ctx, W, H, t) {
  const S = scene(W, H); docReset(S.DW, S.VH);
  for (const j of S.jobs) {
    if (!j.doc || t < j.t0) continue;
    const p = jp(j, t), c = C32(j.c || I);
    switch (j.k) {
      case "rect": case "ellipse": (j.k === "rect" ? drect : dellipse)(j.A, lerpPt(j.A, j.Bp, p), c, j.s); break;
      case "arrow": for (const [a, b] of arrowSegs(j, p)) dline(a, b, c, j.s); break;
      case "pencil": case "brush": dpoly(j.trail.slice(0, Math.floor(p * (j.trail.length - 1)) + 1), c, j.s); break;
      case "fill": dflood(j.AT[0], j.AT[1], c); break;
      case "text": {
        let left = Math.floor(p * j.lines.join("").length + 1e-6);
        for (const r of textLayout(j).rows) {
          if (left <= 0) break;
          dtext(r.str.slice(0, left), r.x, r.base, j.size, j.c); left -= r.str.length;
        }
        break;
      }
      case "stamp": dtriad(j.A, j.Bp, j.lit); break;
    }
  }
  S.docCanvas = B.layer("pd-doc", S.DW, S.VH, () => {}); S.docCanvas.getContext("2d").putImageData(DOC.img, 0, 0);

  g = B.scratch("pd-screen", S.bw, S.bh); g.imageSmoothingEnabled = false; S.ptr = pointer(S, t); desktop(S, t);
  const dlgOpen = t >= T_DLG[1] && t < T_DLG[2], msgOpen = t >= T_MSG[1] && t < T_MSG[2];
  if (t >= T_WIN[1]) { paintWindow(S, t, dlgOpen || msgOpen); canvasOverlays(S, t); }
  const zoom = (src, dst, T4) => {
    if (t >= T4[0] && t < T4[1]) zoomRects(src, dst, B.prog(t, T4[0], T4[1] - T4[0]));
    if (t >= T4[2] && t < T4[3]) zoomRects(src, dst, 1 - B.prog(t, T4[2], T4[3] - T4[2]));
  };
  zoom({ x: S.icons[0].x, y: S.icons[0].y, w: 32, h: 32 }, S.win, T_WIN); zoom(S.cur, S.dlg, T_DLG);
  if (dlgOpen) colourDialog(S, t);
  zoom({ x: 40, y: S.bh - S.tb + 3, w: 70, h: 17 }, S.msg, T_MSG);
  if (msgOpen) messageBox(S, t);

  // 3. the pointer, last; its shape follows the job
  const [px, py] = S.ptr; const busy = (t >= T_WIN[0] - 0.04 && t < T_WIN[1] + 0.06) || (t >= T_DLG[0] - 0.04 && t < T_DLG[1]);
  const overCanvas = t >= T_WIN[1] && !dlgOpen && !msgOpen && inView(S, S.ptr);
  drawPointer(busy ? "glass" : overCanvas ? (activeTool(S, t) === 4 ? "ibeam" : "cross") : "arrow", px, py);

  ctx.imageSmoothingEnabled = false; ctx.drawImage(g.canvas, 0, 0, S.bw * S.cell, S.bh * S.cell);
}

// --- sound: clicks, a desk-mat rub, key taps, bloops, disk chatter, a two-note chime, hum
function score(k) {
  k.bed("room", 0, DUR, { gain: 0.25 }).bed("hum", 0, DUR, { gain: 0.35 });
  const press = (t, gain = 1) => k.at(t, "click", { gain: gain * 0.7 }).at(t + 0.07, "tick", { gain: gain * 0.5 });
  const chime = (t) => k.at(t, "chime", { note: "E5", gain: 0.5, dur: 0.4 }).at(t + 0.11, "chime", { note: "A5", gain: 0.5, dur: 0.6 });
  for (const j of script(false)) {
    const d = Math.max(0.05, j.t1 - j.t0);
    switch (j.k) {
      case "dbl": press(j.t0); press(j.t0 + 0.12); break;
      case "swatch": case "click": press(j.t0, 0.9); break;
      case "fill": press(j.t0); k.at(j.t0 + 0.015, "boop", { pitch: (j.t0 * 7) % 5, gain: 0.5 }); break;
      case "text": // key taps, thinned so fast typing never buzzes
        press(j.t0 - 0.05, 0.8);
        for (let i = 0, n = j.lines.join("").length; i < n; i += d / n < 0.05 ? 2 : 1) k.at(j.t0 + (i * d) / n, "type", { gain: 0.6 });
        break;
      case "stamp": press(j.t0); k.at(j.t0, "data", { dur: 0.16, gain: 0.8 }); break;
      case "scroll": for (let i = 0; i < 6; i++) k.at(j.t0 + (i / 6) * d, "tick", { gain: 0.6 }); break;
      default: k.at(j.t0, "click", { gain: 0.7 }).at(j.t0, "paper", { dur: d, gain: 0.25, pitch: -14 }).at(j.t1, "tick", { gain: 0.5 }); // drags
    }
  }
  k.at(T_WIN[0] - 0.02, "data", { dur: 0.3, gain: 0.7 }); k.at(T_DLG[0], "data", { dur: 0.16, gain: 0.5 });
  chime(T_DLG[1] - 0.04); k.repeat(6.62, 0.05, 10, "type", { gain: 0.35, vary: 2 }).at(7.12, "boop", { pitch: 7, gain: 0.4 });
  chime(T_MSG[0] + 0.05);
}

Player.register({
  id: "paint-desktop", name: "Retro Paint Desktop", duration: DUR,
  fonts: {
    href: "https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@400;700&family=Gaegu:wght@700&family=Jersey+10&display=swap",
    faces: ['400 16px "Pixelify Sans"', '700 16px "Pixelify Sans"', '700 20px "Gaegu"', '400 18px "Jersey 10"'],
  },
  beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
  stills: [2.42, 5.45, 7.2, 10.1, 11.42, 12.9],
  draw, score,
});
})();
