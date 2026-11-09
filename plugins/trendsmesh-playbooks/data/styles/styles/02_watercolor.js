/* 02 Watercolour Bloom - reference animation.
 * Topic (setting, replace it): "How is a rainbow made?" - sunlight bending and bouncing inside raindrops.
 * Rendering (keep it): paper with a tooth; pencil first; see-through jagged washes with a dried darker rim, mottle and
 * granulation; blooms, back-runs, bare-paper highlights; brush strokes and lettering; splatter; slow pans.
 */
(function () {
"use strict";
const B = window.Brush;

// ---- palette and type (from the card)
const PAL = { paper: "#f7f1e3", pencil: "#8a8580", ultra: "#3b5ba9", sky: "#6fa8d6", green: "#5d8a3a", ochre: "#e8b84a", red: "#c0283a", grey: "#4a5363" };
const HEAD = "Caveat Brush";
const DUR = 14, BEATS = [0, 2.5, 5.2, 7.7, 10.0, 11.6];
const PANS = [[2.2, 3.5], [4.9, 6.2], [7.4, 8.6], [11.2, 12.4]]; // the pans between stations
let T = 0; // the frame time

// ---- seamless noise tiles: the paper tooth and the pigment load
function ihash(x, y, s) {
  let h = (Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1) ^ Math.imul(s | 0, 0x9e3779b1)) | 0;
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
function pnoise(x, y, period, seed) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, m = (n) => ((n % period) + period) % period;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = ihash(m(xi), m(yi), seed), b = ihash(m(xi + 1), m(yi), seed), c = ihash(m(xi), m(yi + 1), seed), d = ihash(m(xi + 1), m(yi + 1), seed);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
const TS = 256;
let TOOTH = null, TOOTH_TILE = null, LOAD_TILE = null;
/** The paper tooth's height (0 = pit, 1 = bump), bumps of 2-5 px. */
function toothField() {
  if (TOOTH) return TOOTH;
  TOOTH = new Float32Array(TS * TS);
  for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) TOOTH[y * TS + x] = 0.6 * pnoise(x / 4, y / 4, TS / 4, 5) + 0.4 * pnoise(x / 2, y / 2, TS / 2, 6);
  return TOOTH;
}
function greyTile(N, fn) {
  const c = B.canvas(N, N), g = c.getContext("2d"), img = g.createImageData(N, N);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { const i = (y * N + x) * 4; img.data[i] = img.data[i + 1] = img.data[i + 2] = fn(x, y); img.data[i + 3] = 255; }
  g.putImageData(img, 0, 0);
  return c;
}
/** The tooth lit from the upper left, grey round 128 for overlay. */
const toothTile = () => TOOTH_TILE || (TOOTH_TILE = greyTile(TS, (x, y) => {
  const h = toothField(), s = h[y * TS + x] - h[((y + 1) % TS) * TS + ((x + 1) % TS)];
  return B.clamp(128 + s * 300 + (h[y * TS + x] - 0.5) * 50, 0, 255);
}));
const loadTile = () => LOAD_TILE || (LOAD_TILE = greyTile(128, (x, y) => B.clamp((0.65 * pnoise(x / 16, y / 16, 8, 21) + 0.35 * pnoise(x / 8, y / 8, 16, 22) - 0.5) * 1.6 + 0.5) * 255));

// ---- the wash (the heart of the look; reuse it)
/** Jag a polygon: jittered midpoints, depth times. */
function deform(pts, depth, amp, r) {
  let cur = pts;
  for (let d = 0; d < depth; d++) {
    const out = [];
    for (let i = 0; i < cur.length; i++) {
      const a = cur[i], b = cur[(i + 1) % cur.length], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
      const k = B.clamp(r.gauss(0, amp), -0.7 * l, 0.7 * l);
      out.push(a, [(a[0] + b[0]) / 2 - (dy / l) * k, (a[1] + b[1]) / 2 + (dx / l) * k]);
    }
    cur = out;
    amp *= 0.55;
  }
  return cur;
}
const washCache = new Map();
/** Rasterise a wash once: faint jagged copies stacked into a ragged alpha, holes for bare-paper highlights; per pixel
 *  body = alpha x pigment load x granulation, rim = alpha - blurred alpha (pigment dried at the edge). */
function washRaster(w, L) {
  const key = w.id + "@" + L.W + "x" + L.H;
  let R = washCache.get(key);
  if (R) return R;
  const u = L.u, pad = 5 * u, x0 = Math.floor(w.bbox.x - pad), y0 = Math.floor(w.bbox.y - pad);
  const cw = Math.ceil(w.bbox.w + 2 * pad), ch = Math.ceil(w.bbox.h + 2 * pad), body = B.canvas(cw, ch), g = body.getContext("2d");
  g.translate(-x0, -y0);
  const r = B.rng("wash:" + w.id), amp = (w.jag ?? 1) * u, n = w.layers ?? 14, base = deform(w.pts, 2, amp * 1.3, r);
  g.fillStyle = "#000";
  for (let i = 0; i < n; i++) { g.globalAlpha = 1.9 / n; g.beginPath(); B.poly(g, deform(base, 3, amp, r), true); g.fill(); }
  g.globalAlpha = 1;
  if (w.holes) { // highlights are never painted: the paper is left bare
    g.globalCompositeOperation = "destination-out";
    for (const h of w.holes) { g.beginPath(); B.poly(g, deform(h, 2, amp * 0.3, r), true); g.fill(); }
  }
  const A = g.getImageData(0, 0, cw, ch).data, rim = B.canvas(cw, ch), g2 = rim.getContext("2d");
  g2.filter = `blur(${(1.2 * u).toFixed(1)}px)`; g2.drawImage(body, 0, 0); g2.filter = "none";
  const Ab = g2.getImageData(0, 0, cw, ch).data, mc = B.canvas(cw, ch), g3 = mc.getContext("2d"), pat = g3.createPattern(loadTile(), "repeat");
  const ms = 0.55 * u;
  pat.setTransform(new DOMMatrix([ms, 0, 0, ms, -B.hash01(w.id, "mx") * 128 * ms, -B.hash01(w.id, "my") * 128 * ms]));
  g3.fillStyle = pat; g3.fillRect(0, 0, cw, ch);
  const M = g3.getImageData(0, 0, cw, ch).data, TH = toothField(), o1 = g.createImageData(cw, ch), o2 = g2.createImageData(cw, ch), d1 = o1.data, d2 = o2.data;
  const [cr, cg, cb] = B.rgb(w.color), [dr, dg, db] = B.rgb(B.shade(w.color, -0.32));
  const bodyA = w.alpha ?? 0.5, rimK = w.rim ?? 2.6, gran = 0.28, br = w.backrun, brPh = br ? [1, 2, 3, 4].map((j) => B.hash01(w.id, j) * 6.283) : null;
  for (let y = 0; y < ch; y++)
    for (let x = 0; x < cw; x++) {
      const i = (y * cw + x) * 4, a = A[i + 3] / 255;
      if (a < 0.004) continue;
      const ab = Ab[i + 3] / 255, m = 0.5 + M[i] / 255, wx = x + x0, wy = y + y0, h = TH[((wy & 255) << 8) | (wx & 255)];
      const gr = 1 + gran * (0.5 - h) * 2; // granulation: pigment settles in the pits of the tooth
      let b = a * bodyA * m * gr, rr = Math.max(0, a - ab) * rimK * gr;
      if (br) { // back-run: a frilly cauliflower edge
        const dx = wx - br.x, dy = wy - br.y, ang = Math.atan2(dy, dx);
        const frill = 1 + 0.09 * Math.sin(ang * 3 + brPh[0]) + 0.07 * Math.sin(ang * 8 + brPh[1]) + 0.05 * Math.abs(Math.sin(ang * 13 + brPh[2])) + 0.035 * Math.abs(Math.sin(ang * 29 + brPh[3]));
        const d = Math.hypot(dx, dy) / (br.r * frill), e = Math.abs(d - 0.98);
        if (d < 1) b *= 0.42 + 0.58 * d * d * d;
        if (e < 0.1) rr += a * 0.55 * (1 - e / 0.1) * (1 - e / 0.1);
      }
      d1[i] = cr; d1[i + 1] = cg; d1[i + 2] = cb; d1[i + 3] = B.clamp(b) * 255;
      d2[i] = dr; d2[i + 1] = dg; d2[i + 2] = db; d2[i + 3] = B.clamp(rr) * 255;
    }
  g.putImageData(o1, 0, 0); g2.putImageData(o2, 0, 0);
  R = { x: x0, y: y0, w: cw, h: ch, body, rim };
  washCache.set(key, R);
  return R;
}
/** A wash floods out from w.from behind a soft wet front; its rim darkens as it settles; multiplied, so it glazes. */
function drawWash(ctx, w, L) {
  const dur = w.dur, p = B.prog(T, w.at, dur, "outCubic");
  if (p <= 0) return;
  const R = washRaster(w, L), settle = B.prog(T, w.at + dur * 0.5, 1.1, "inOutSine");
  ctx.save(); ctx.globalCompositeOperation = "multiply";
  if (p >= 1) {
    ctx.drawImage(R.body, R.x, R.y); ctx.globalAlpha = 0.3 + 0.7 * settle; ctx.drawImage(R.rim, R.x, R.y);
  } else {
    const fx = w.from[0] - R.x, fy = w.from[1] - R.y, rad = Math.max(Math.hypot(fx, fy), Math.hypot(R.w - fx, fy), Math.hypot(fx, R.h - fy), Math.hypot(R.w - fx, R.h - fy)) * p + 1;
    [[R.body, 1, "wcf-b"], [R.rim, 0.3 * p, "wcf-r"]].forEach(([src, al, k]) => {
      const g = B.scratch(k, R.w, R.h);
      g.drawImage(src, 0, 0); g.globalCompositeOperation = "destination-in";
      g.fillStyle = B.radial(g, fx, fy, rad * 0.72, rad, ["rgba(0,0,0,1)", "rgba(0,0,0,0)"]);
      g.beginPath(); B.blob(g, fx, fy, rad, { seed: B.hash(w.id) % 997, wobble: 0.2, n: 11 }); g.fill();
      ctx.globalAlpha = al; ctx.drawImage(g.canvas, R.x, R.y);
    });
  }
  ctx.restore();
}
/** Wet-in-wet bloom: a second colour creeping inside the damp wash. */
function drawBloom(ctx, w, L) {
  const b = w.bloom, p = B.prog(T, b.at, 1.5, "outSine");
  if (!b || p <= 0) return;
  const R = washRaster(w, L), g = B.scratch("wc-bloom", R.w, R.h), bx = b.x - R.x, by = b.y - R.y;
  const rad = b.r * (0.3 + 0.7 * p + 0.05 * Math.max(0, T - b.at - 1.5));
  g.fillStyle = B.radial(g, bx, by, 0, rad, [[0, B.rgba(b.color, 1)], [0.7, B.rgba(b.color, 0.8)], [0.9, B.rgba(b.color, 1)], [1, B.rgba(b.color, 0)]]);
  g.beginPath(); B.blob(g, bx, by, rad, { seed: 7 + (B.hash(w.id) % 50), wobble: 0.24, n: 13 }); g.fill();
  g.globalCompositeOperation = "destination-in"; // only where the wash already is
  g.drawImage(R.body, 0, 0); g.drawImage(R.body, 0, 0);
  ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.drawImage(g.canvas, R.x, R.y); ctx.restore();
}

// ---- brush, pencil, lettering, splatter
/** A loaded round-brush stroke as a ribbon: thickest near the start, thinning as it runs out of paint, tapering at the
 *  lift; see-through with a darker pooled edge. o: { width, color, p, alpha, thin, seed, head, tin } */
function brushStroke(ctx, pts, o) {
  const p = o.p ?? 1;
  if (p <= 0) return;
  const wMax = o.width, path = B.densify(pts, Math.max(2, wMax * 0.35)), n = path.length, Ltot = B.pathLength(path), cut = Ltot * p, thin = o.thin ?? 0.6, seed = o.seed ?? 1;
  const left = [], right = [];
  let s = 0;
  for (let i = 0; i < n; i++) {
    if (i) s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
    if (s > cut) break;
    const f = s / (Ltot || 1);
    let wv = wMax * (1 - thin * f) * Math.min(1, Math.sqrt(f / (o.tin ?? 0.05))) * Math.min(1, Math.pow((1 - f) / 0.22, 0.7));
    wv *= Math.min(1, (cut - s) / (wMax * 1.6) + 0.15);
    wv *= 1 + 0.18 * B.noise1(s / (wMax * 2.5), seed);
    wv = Math.max(0.5, wv);
    const a = path[Math.max(0, i - 1)], b = path[Math.min(n - 1, i + 1)];
    const l = Math.hypot(-(b[1] - a[1]), b[0] - a[0]) || 1, nx = -(b[1] - a[1]) / l, ny = (b[0] - a[0]) / l;
    left.push([path[i][0] + (nx * wv) / 2, path[i][1] + (ny * wv) / 2]); right.push([path[i][0] - (nx * wv) / 2, path[i][1] - (ny * wv) / 2]);
  }
  if (left.length < 2) return;
  ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.beginPath(); B.poly(ctx, left.concat(right.reverse()), true);
  ctx.globalAlpha = o.alpha ?? 0.72; ctx.fillStyle = o.color; ctx.fill();
  ctx.globalAlpha = (o.alpha ?? 0.72) * 0.6; ctx.strokeStyle = B.shade(o.color, -0.3); ctx.lineWidth = Math.max(0.8, wMax * 0.08); ctx.lineJoin = "round"; ctx.stroke();
  ctx.restore();
  if (o.head && p > 0.88) { // a brushed arrowhead
    const hp = B.clamp((p - 0.88) / 0.12), tip = B.pointAt(path, 1), a = tip[2], hl = wMax * 3.2;
    [-1, 1].forEach((sgn) => {
      const ang = a + Math.PI + sgn * 0.55, end = [tip[0] + Math.cos(ang) * hl, tip[1] + Math.sin(ang) * hl];
      brushStroke(ctx, [end, [B.lerp(end[0], tip[0], 0.5) + sgn * wMax * 0.2, B.lerp(end[1], tip[1], 0.5)], [tip[0], tip[1]]], { width: wMax * 0.85, color: o.color, alpha: o.alpha, thin: -0.2, p: hp, seed: seed + sgn });
    });
  }
}
/** Faint graphite underdrawing, gone over twice. */
function pencil(ctx, it, u) {
  const p = B.prog(T, it.at, it.dur, "inOutSine");
  if (p > 0) B.handLine(ctx, it.pts, { width: Math.max(1, 0.16 * u), color: PAL.pencil, amp: 0.3 * u, seed: it.seed, passes: 2, p, alpha: 0.6 });
}
/** Brush lettering, word by word; letters wander in size, angle and baseline; a darker pooled rim. */
function brushWords(ctx, it) {
  let alpha = 1;
  if (it.fin) alpha *= B.span(T, it.fin[0], it.fin[1]);
  if (it.out) alpha *= 1 - B.span(T, it.out[0], it.out[1]);
  if (T < it.at || alpha <= 0.002) return;
  const fam = it.font || HEAD, gap = it.gap ?? 0.2, lineH = 1.02, lines = it.str.split("\n");
  let size = it.size;
  ctx.save(); ctx.font = B.font(size, fam, 400);
  if (it.maxW) {
    const widest = Math.max(...lines.map((l) => ctx.measureText(l).width));
    if (widest > it.maxW) size *= it.maxW / widest;
    ctx.font = B.font(size, fam, 400);
  }
  ctx.globalCompositeOperation = "multiply"; ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  const body = B.mix(it.color, "#ffffff", 0.28), dark = B.shade(it.color, -0.5), sp = ctx.measureText(" ").width; // pigment pools at the edge
  let wi = 0;
  lines.forEach((line, li) => {
    const words = line.split(" "), ww = words.map((w) => ctx.measureText(w).width), lw = ww.reduce((a, b) => a + b, 0) + sp * (words.length - 1);
    let xx = it.align === "left" ? it.x : it.align === "right" ? it.x - lw : it.x - lw / 2;
    const by = it.y + (li - (lines.length - 1) / 2) * size * lineH + size * 0.3;
    words.forEach((w, k) => {
      const p = B.prog(T, it.at + wi * gap, Math.max(0.12, gap * 1.4), "outSine");
      wi++;
      if (p > 0) {
        ctx.save(); ctx.beginPath(); ctx.rect(xx - size * 0.3, by - size * 1.3, (ww[k] + size * 0.6) * p, size * 2); ctx.clip();
        let cx = xx;
        for (let ci = 0; ci < w.length; ci++) {
          const chW = ctx.measureText(w[ci]).width, h1 = B.hash01(it.seed ?? 1, li, k, ci), h2 = B.hash01(ci, k, li, "r"), h3 = B.hash01(k, ci, "s");
          ctx.save(); ctx.translate(cx + chW / 2, by + (h1 - 0.5) * size * 0.12); ctx.rotate((h2 - 0.5) * 0.16); ctx.scale(0.92 + h3 * 0.16, 0.92 + h3 * 0.16);
          ctx.globalAlpha = alpha * 0.85; ctx.fillStyle = body; ctx.fillText(w[ci], -chW / 2, 0);
          ctx.globalAlpha = alpha * 0.75; ctx.strokeStyle = dark; ctx.lineWidth = Math.max(1.5, size * 0.06); ctx.strokeText(w[ci], -chW / 2, 0);
          ctx.restore();
          cx += chW;
        }
        ctx.restore();
      }
      xx += ww[k] + sp;
    });
  });
  ctx.restore();
}
/** A light flick of droplets with darker dried rims. */
function splatter(ctx, it, u) {
  if (T < it.at) return;
  const r = B.rng("splat:" + it.seed), k = B.prog(T, it.at, 0.15);
  ctx.save(); ctx.globalCompositeOperation = "multiply";
  for (let i = 0; i < it.n; i++) {
    if (r() > k) continue;
    const a = r() * B.TAU, d = Math.abs(r.gauss(0, it.spread)), x = it.x + Math.cos(a) * d, y = it.y + Math.sin(a) * d * 0.7;
    const rad = r.range(0.12, 0.6) * u * (r() < 0.15 ? 1.8 : 1), stretch = r() < 0.25 ? r.range(1.4, 2.4) : 1;
    ctx.save(); ctx.translate(x, y); ctx.rotate(a); ctx.scale(stretch, 1); ctx.beginPath(); B.circle(ctx, 0, 0, rad);
    ctx.fillStyle = B.rgba(it.color, 0.5); ctx.fill();
    ctx.strokeStyle = B.rgba(B.shade(it.color, -0.3), 0.55); ctx.lineWidth = Math.max(0.6, rad * 0.22); ctx.stroke(); ctx.restore();
  }
  ctx.restore();
}

// ---- shapes (the setting)
function bboxOf(pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
const bandPts = (c, r0, r1, a0, a1, n = 36) => B.arcPts(c[0], c[1], r1, a0, a1, n).concat(B.arcPts(c[0], c[1], r0, a1, a0, n));
const circlePts = (c, r, n = 28) => B.arcPts(c[0], c[1], r, 0, B.TAU * (1 - 1 / n), n - 1);
function cloudPts(c, w, h, seed) {
  const out = [], ph = B.hash01(seed) * 6;
  for (let i = 0; i < 30; i++) {
    const a = (i / 30) * B.TAU, top = Math.sin(a) < 0, k = top ? 1 + 0.16 * Math.abs(Math.sin(a * 2.5 + ph)) : 0.85;
    out.push([c[0] + Math.cos(a) * w * 0.5 * k, c[1] + Math.sin(a) * h * (top ? 0.62 : 0.3) * k]);
  }
  return out;
}
/** The bare-paper highlight crescent of a drop. */
const crescent = (c, r, a0, a1) => B.arcPts(c[0], c[1], r * 0.84, a0, a1, 16).concat(B.arcPts(c[0] + r * 0.07, c[1] + r * 0.07, r * 0.78, a1 + 0.12, a0 - 0.12, 16));
/** A ray through a drop (index n), entering at incidence i. */
function dropRay(c, R, n, i) {
  const r = Math.asin(Math.sin(i) / n), at = (a) => [c[0] + Math.cos(a) * R, c[1] + Math.sin(a) * R];
  return { P1: at(Math.PI + i), P2: at(i - 2 * r), P3: at(Math.PI + i - 4 * r), exit: Math.PI + 2 * i - 4 * r };
}
const N_RED = 1.331, I_RAINBOW = Math.acos(Math.sqrt((N_RED * N_RED - 1) / 3)); // the ray that makes the bow
const FAN = [PAL.red, "#ee8a3a", "#f2cd48", PAL.green, PAL.ultra]; // spectral bands

// ---- the sheet (world coordinates)
const sceneCache = new Map();
function scene(W, H) {
  const key = W + "x" + H;
  if (sceneCache.has(key)) return sceneCache.get(key);
  const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
  // station origins on the one long sheet (portrait scrolls down; landscape across, then down to the close)
  const ST = P ? [[0, 0], [-0.05 * W, 0.93 * H], [0.04 * W, 1.86 * H], [-0.03 * W, 2.79 * H], [0.02 * W, 3.72 * H]]
    : [[0, 0], [1.02 * W, 0.08 * H], [2.04 * W, -0.04 * H], [3.06 * W, 0.06 * H], [3.1 * W, 1.12 * H]];
  const sc = { F, u, P, W, H, ST, washes: [], pencil: [], strokes: [], words: [], splats: [] };
  const at = (k) => (x, y) => [x + ST[k][0], y + ST[k][1]];
  const wash = (o) => { o.bbox = bboxOf(o.pts); o.from = o.from || [o.bbox.x + o.bbox.w / 2, o.bbox.y + o.bbox.h / 2]; sc.washes.push(o); return o; };
  const pen = (pts, t0, dur, seed) => sc.pencil.push({ pts, at: t0, dur, seed });
  const words = (o) => sc.words.push(o), splat = (x, y, spread, n, color, at, seed) => sc.splats.push({ x, y, spread, n, color, at, seed });
  const st = (pts, at, dur, width, color, alpha, seed, o) => sc.strokes.push({ pts, at, dur, width, color, alpha, seed, ...o });
  const wa = (id, color, pts, at, dur, alpha, o) => wash({ id, color, pts, at, dur, alpha, ...o });
  const head = (str, k, x, y, size, t0, o = {}, [X, Y] = at(k)(x, y)) => words({ str, x: X, y: Y, size, color: o.color || PAL.ultra, at: t0, gap: o.gap ?? 0.2, maxW: o.maxW ?? S.w, align: o.align, font: o.font, seed: k * 10 + 1 });

  { // ---- 0. title: a small rainbow over two clouds, the title brushed word by word
    const A = at(0), hz = P ? 0.53 * H : 0.6 * H, c = A(W / 2, hz), rOut = P ? 0.42 * W : 0.44 * H, bw = P ? 0.04 * W : 0.042 * H;
    pen(B.arcPts(c[0], c[1], rOut + bw * 0.5, Math.PI * 0.97, Math.PI * 2.03, 50), 0.05, 0.55, 1);
    pen(B.arcPts(c[0], c[1], rOut - bw * 5.3, Math.PI * 0.98, Math.PI * 2.02, 40), 0.15, 0.5, 2);
    pen([A(S.x - 3 * u, c[1] - c[1] + hz + 0.5 * u), A(S.r + 3 * u, hz - 0.4 * u)], 0.1, 0.45, 3); // the horizon
    FAN.forEach((col, i) => {
      const r1 = rOut - i * bw, r0 = r1 - bw * 1.3;
      wa("t-band" + i, col, bandPts(c, r0, r1, Math.PI, B.TAU, 40), 0.3 + i * 0.14, 1.1, 0.6, { from: [c[0] - r1 * 0.2, c[1] - r1], layers: 12, jag: 0.5, rim: 1.6 });
    });
    const ty = P ? 0.64 * H : 0.75 * H, ts = P ? 12.5 * u : 11 * u;
    head(P ? "How a rainbow\nis made" : "How a rainbow is made", 0, W / 2, ty, ts, 0.95, { gap: 0.2 });
    (P ? [[-0.15, 0.62], [0.87, 0.36]] : [[0.36, 0.62]]).forEach(([dy, w], i) => pen([A(W * (0.5 - w / 2), ty + ts * dy), A(W * (0.5 + w / 2) + 2 * u, ty + ts * dy + 0.3 * u)], 0.4 + i * 0.1, 0.35, 77)); // guides under the lettering
    head("light, water and one special angle", 0, W / 2, P ? 0.755 * H : 0.87 * H, P ? 6 * u : 5 * u, 1.6, { color: PAL.grey, gap: 0.08 });
  }
  { // ---- 1. diagram: one big drop; sunlight in, bent, bounced, fanned out as colours
    const A = at(1), c = P ? A(0.55 * W, 0.45 * H) : A(0.64 * W, 0.4 * H), R = P ? 0.3 * W : 0.2 * H;
    pen(circlePts(c, R * 1.01, 40).concat([[c[0] + R * 1.02, c[1] - R * 0.08]]), 2.85, 0.5, 11);
    pen([[c[0] - R * 1.15, c[1]], [c[0] + R * 1.15, c[1]]], 2.95, 0.3, 12);
    pen([[c[0], c[1] - R * 1.15], [c[0], c[1] + R * 1.15]], 3.0, 0.3, 13);
    wa("d-drop", PAL.sky, circlePts(c, R), 3.05, 1.0, 0.55, { from: [c[0] + R * 0.25, c[1] + R * 0.2], rim: 2.8, jag: 0.7, holes: [crescent(c, R, Math.PI * 1.05, Math.PI * 1.45)], bloom: { color: PAL.ultra, x: c[0] + R * 0.45, y: c[1] + R * 0.45, r: R * 0.55, at: 3.7 } });
    st(B.arcPts(c[0], c[1], R * 0.97, 0.05, 1.45, 20), 4.0, 0.45, 1.4 * u, PAL.ultra, 0.55, 5, { thin: 0.8 });
    const ray = dropRay(c, R, N_RED, I_RAINBOW), len = P ? 0.36 * W : 0.2 * W, fe = [ray.P3[0] + Math.cos(ray.exit) * len - ST[1][0], ray.P3[1] + Math.sin(ray.exit) * len - ST[1][1]];
    st([[c[0] - (P ? 0.52 * W : 0.6 * W), ray.P1[1]], ray.P1], 3.5, 0.55, 2.4 * u, PAL.ochre, 0.85, 6, { head: true, thin: 0.35 });
    st([ray.P1, ray.P2, ray.P3], 4.05, 0.45, 1.0 * u, PAL.ochre, 0.9, 7, { thin: 0.1 });
    FAN.forEach((col, i) => {
      const a = ray.exit - B.deg(4) + B.deg(2) * i; // the fan's spread is exaggerated
      st([ray.P3, [ray.P3[0] + Math.cos(a) * len, ray.P3[1] + Math.sin(a) * len]], 4.4 + i * 0.07, 0.5, 1.8 * u, col, 0.62, 20 + i, { head: i === 0 || i === 4, thin: -0.2, tin: 0.45 });
    });
    head(P ? "Inside one raindrop" : "Inside one\nraindrop", 1, P ? W / 2 : 0.25 * W, P ? 0.19 * H : 0.52 * H, P ? 9.5 * u : 8 * u, 2.9, { maxW: P ? S.w : 0.36 * W });
    const lab = (str, x, y, t0, o = {}) => head(str, 1, x, y, P ? 5.6 * u : 5.2 * u, t0, { color: PAL.grey, gap: 0.12, ...o });
    lab("sunlight", P ? 0.22 * W : 0.17 * W, P ? 0.28 * H : 0.17 * H, 3.75, { color: B.shade(PAL.ochre, -0.35) });
    lab("raindrop", P ? 0.84 * W : 0.9 * W, P ? 0.68 * H : 0.27 * H, 4.15);
    pen(P ? [A(0.82 * W, 0.66 * H), [c[0] + R * 0.6, c[1] + R * 0.85]] : [A(0.88 * W, 0.3 * H), [c[0] + R * 0.88, c[1] - R * 0.35]], 4.1, 0.3, 14);
    lab("colours fan out", fe[0] + (P ? 0.21 : 0.13) * W, fe[1] + 2 * u, 4.45);
    splat(c[0] + R * 0.9, c[1] + R * 0.7, 5 * u, 26, PAL.ultra, 3.9, 2);
  }
  { // ---- 2. key number: the 42 degree angle, repainted from violet's 40
    const A = at(2), V = P ? A(0.08 * W, 0.73 * H) : A(0.07 * W, 0.8 * H), len = P ? 0.74 * W : 0.54 * W, ang = B.deg(-42), bl = P ? 0.86 * W : 0.6 * W, wr = len * 0.62;
    pen([V, [V[0] + bl, V[1] + 0.3 * u]], 5.55, 0.4, 21);
    head("toward your head's shadow", 2, V[0] - ST[2][0] + bl, V[1] - ST[2][1] + 4.5 * u, P ? 5.4 * u : 4.8 * u, 6.3, { color: PAL.grey, gap: 0.08, align: "right" });
    pen([V, [V[0] + Math.cos(ang) * len, V[1] + Math.sin(ang) * len]], 5.7, 0.4, 22);
    wa("n-wedge", PAL.sky, [V].concat(B.arcPts(V[0], V[1], wr, ang, 0, 20)), 5.85, 0.9, 0.42, { from: V, jag: 0.7 });
    st(B.arcPts(V[0], V[1], len * 0.32, -0.02, ang - 0.05, 18), 6.2, 0.35, 1.2 * u, PAL.red, 0.7, 31, { head: true, thin: 0.3 });
    st([V, [V[0] + Math.cos(ang) * len * 0.9, V[1] + Math.sin(ang) * len * 0.9]], 6.0, 0.5, 1.6 * u, PAL.red, 0.6, 32, { thin: 0.6 });
    const N = P ? A(0.56 * W, 0.255 * H) : A(0.76 * W, 0.36 * H), ns = P ? 26 * u : 28 * u, er = [ns * 1.05, ns * 0.62], ep = [];
    words({ str: "40°", x: N[0], y: N[1], size: ns, color: PAL.ultra, at: 6.0, gap: 0.08, out: [6.55, 6.85], seed: 41 });
    words({ str: "42°", x: N[0], y: N[1], size: ns, color: PAL.red, at: 6.55, gap: 0.05, fin: [6.55, 6.85], seed: 42 });
    for (let i = 0; i <= 40; i++) { // a loose red swash round the number
      const a = -2.3 + (i / 40) * B.TAU * 0.96;
      ep.push([N[0] + Math.cos(a) * er[0] * (1 + 0.04 * i / 40), N[1] - ns * 0.05 + Math.sin(a) * er[1]]);
    }
    st(ep, 7.0, 0.45, 1.3 * u, PAL.red, 0.7, 43, { thin: 0.5 });
    head("the angle of every rainbow", 2, N[0] - ST[2][0], P ? 0.355 * H : 0.6 * H, P ? 6 * u : 5.4 * u, 6.75, { color: PAL.grey, gap: 0.1, maxW: P ? S.w : 0.42 * W });
    head("red at 42°,\nviolet at 40°", 2, P ? 0.74 * W : 0.76 * W, P ? 0.56 * H : 0.71 * H, P ? 6 * u : 5 * u, 6.9, { color: PAL.grey, gap: 0.07 });
    splat(N[0] + ns * 0.9, N[1] - ns * 0.4, 4.5 * u, 24, PAL.red, 7.0, 3);
  }
  { // ---- 3. three steps as separate vignettes, linked by brushed arrows
    const A = at(3), rv = P ? 0.14 * W : 0.13 * H, t0s = [7.9, 8.4, 8.9];
    const cs = P ? [0.25, 0.44, 0.63].map((y) => A(0.28 * W, y * H)) : [0.2, 0.5, 0.8].map((x) => A(x * W, 0.4 * H));
    const labels = ["1  Light enters\nand bends", "2  It bounces off\nthe back", "3  It bends out,\nsplit into colours"];
    cs.forEach((c, k) => {
      const t0 = t0s[k], ray = dropRay(c, rv, N_RED, I_RAINBOW);
      pen(circlePts(c, rv * 1.02, 30).concat([[c[0] + rv * 1.04, c[1] - rv * 0.1]]), t0 - 0.2, 0.35, 50 + k);
      wa("s-drop" + k, PAL.sky, circlePts(c, rv, 22), t0, 0.8, 0.5, { rim: 2.8, jag: 0.45, holes: [crescent(c, rv, Math.PI * 1.05, Math.PI * 1.45)] });
      st(B.arcPts(c[0], c[1], rv * 0.96, 0.1, 1.4, 14), t0 + 0.55, 0.3, 0.9 * u, PAL.ultra, 0.5, 60 + k, { thin: 0.8 });
      const inLen = P ? 0.18 * W : 0.12 * W, entry = [[ray.P1[0] - inLen, ray.P1[1]], ray.P1];
      if (k === 0) {
        st(entry, t0 + 0.3, 0.35, 1.5 * u, PAL.ochre, 0.85, 70, { thin: 0.3 });
        st([ray.P1, B.pointAt([ray.P1, ray.P2], 0.75)], t0 + 0.6, 0.3, 0.9 * u, PAL.ochre, 0.9, 71, { thin: 0.2, head: true });
      } else {
        pen(entry, t0 + 0.1, 0.25, 80 + k); pen([ray.P1, ray.P2], t0 + 0.2, 0.2, 90 + k);
      }
      if (k === 1) {
        st([ray.P1, ray.P2, ray.P3], t0 + 0.35, 0.45, 1.0 * u, PAL.ochre, 0.95, 72, { thin: 0.1, head: true });
        st(B.arcPts(ray.P2[0], ray.P2[1], rv * 0.22, 1.9, 4.4, 10), t0 + 0.6, 0.25, 0.8 * u, PAL.red, 0.7, 73, { thin: 0.4 });
      }
      if (k === 2) {
        st([ray.P1, ray.P2, ray.P3], t0 + 0.25, 0.4, 1.0 * u, PAL.ochre, 0.9, 99, { thin: 0.1 });
        FAN.forEach((col, i) => {
          const a = ray.exit - B.deg(10) + B.deg(5) * i, l = rv * (P ? 1.6 : 0.95);
          st([ray.P3, [ray.P3[0] + Math.cos(a) * l, ray.P3[1] + Math.sin(a) * l]], t0 + 0.4 + i * 0.04, 0.3, 1.3 * u, col, 0.65, 74 + i, { thin: -0.2, tin: 0.45 });
        });
      }
      const lp = P ? [c[0] + rv + 0.05 * W, c[1]] : [c[0], c[1] + 0.29 * H];
      words({ str: labels[k], x: lp[0], y: lp[1], size: P ? 6.4 * u : 4.6 * u, color: PAL.grey, at: t0 + 0.25, gap: 0.08, align: P ? "left" : "center", seed: 100 + k, maxW: P ? 0.5 * W : 0.27 * W });
      if (k < 2) {
        const n = cs[k + 1];
        const pts = P ? B.quad(c[0] - rv * 1.15, c[1] + rv * 0.4, c[0] - rv * 1.9, (c[1] + n[1]) / 2, n[0] - rv * 1.1, n[1] - rv * 0.55) : B.quad(c[0] + rv * 0.6, c[1] - rv * 1.15, (c[0] + n[0]) / 2, c[1] - rv * 2.2, n[0] - rv * 0.6, n[1] - rv * 1.15);
        st(pts, t0s[k + 1] - 0.3, 0.45, 1.6 * u, PAL.grey, 0.6, 110 + k, { head: true, thin: 0.55 });
      }
    });
    // emphasis: a loose red swash round the last drop and its fan, and the point of it brushed beside
    const c3 = cs[2], er = rv * 1.22, ep = [];
    for (let i = 0; i <= 40; i++) { const a = -2.3 + (i / 40) * B.TAU * 0.96; ep.push([c3[0] + Math.cos(a) * er, c3[1] + Math.sin(a) * er]); }
    st(ep, 10.15, 0.45, 1.3 * u, PAL.red, 0.7, 120, { thin: 0.5 });
    head(P ? "each drop sends\nyou one colour" : "each drop sends you one colour", 3, P ? 0.66 * W : W / 2, P ? 0.755 * H : 0.86 * H, P ? 6 * u : 5 * u, 10.5, { color: PAL.red, gap: 0.1 });
  }
  { // ---- 4. close: the bow over the hills, rain falling from a grey cloud
    const A = at(4), c = P ? A(W / 2, 0.71 * H) : A(0.63 * W, 0.86 * H), rOut = P ? 0.43 * W : 0.52 * H, bw = P ? 0.034 * W : 0.045 * H, hy = P ? 0.7 * H : 0.8 * H;
    const hill = (y0, amp, ph) => {
      const pts = [];
      for (let i = 0; i <= 16; i++) pts.push(A(-0.05 * W + (i / 16) * 1.1 * W, y0 - amp * (0.6 + 0.4 * Math.sin((i / 16) * 5 + ph)) * Math.sin((i / 16) * Math.PI)));
      return pts.concat([A(1.05 * W, H * 1.06), A(-0.05 * W, H * 1.06)]);
    };
    pen([A(-0.02 * W, hy), A(1.02 * W, hy - u)], 11.75, 0.4, 120);
    FAN.forEach((col, i) => {
      const r1 = rOut - i * bw, r0 = r1 - bw * 1.3;
      wa("c-band" + i, col, bandPts(c, r0, r1, Math.PI, B.TAU, 44), 12.05 + i * 0.13, 1.1, 0.55, { from: [c[0], c[1] - r1], layers: 12, jag: 0.5, rim: 1.6 });
    });
    wa("c-hill-back", PAL.ultra, hill(hy, 0.07 * H, 1), 11.85, 1.0, 0.3, { from: A(0.3 * W, hy + 0.1 * H), jag: 1.4 });
    wa("c-hill", PAL.green, hill(hy + 0.06 * H, 0.06 * H, 3.5), 12.0, 1.0, 0.55, { from: A(0.6 * W, H), jag: 1.4, backrun: { x: A(0.7 * W, 0)[0], y: A(0, hy + 0.08 * H)[1], r: 0.06 * W } });
    wa("c-field", PAL.ochre, hill(hy + 0.15 * H, 0.04 * H, 2), 12.3, 1.0, 0.45, { from: A(0.3 * W, H), jag: 1.4 });
    const cc = P ? A(0.73 * W, 0.4 * H) : A(0.84 * W, 0.24 * H), cw = P ? 0.42 * W : 0.26 * W, rr = B.rng("rain");
    wa("c-cloud", PAL.grey, cloudPts(cc, cw, cw * 0.42, 12), 11.9, 1.0, 0.42, { rim: 2.6, jag: 1.3, backrun: { x: cc[0] - cw * 0.1, y: cc[1] - cw * 0.05, r: cw * 0.12 } });
    for (let i = 0; i < 6; i++) { // rain: broken dry-brush drags
      const x = cc[0] - cw * 0.34 + (i / 5) * cw * 0.66 + rr.range(-1.5, 1.5) * u, y = cc[1] + cw * rr.range(0.1, 0.18), l = (P ? 0.15 * H : 0.26 * H) * rr.range(0.55, 1);
      st([[x, y], [x - l * rr.range(0.2, 0.32), y + l]], 12.45 + i * 0.07, 0.4, rr.range(0.6, 1.1) * u, PAL.grey, rr.range(0.22, 0.38), 130 + i, { thin: 0.9 });
    }
    const tp = P ? [W / 2, 0.215 * H] : [0.26 * W, 0.3 * H], ts = P ? 10.5 * u : 9 * u;
    head("Sun at your back,\nrain in front", 4, tp[0], tp[1], ts, 12.2, { maxW: P ? S.w : 0.42 * W });
    const ul = [A(tp[0] - (P ? 0.3 : 0.17) * W, tp[1] + ts * 1.3), A(tp[0] + (P ? 0.32 : 0.18) * W, tp[1] + ts * 1.18)];
    st(B.quad(ul[0][0], ul[0][1], (ul[0][0] + ul[1][0]) / 2, ul[0][1] + ts * 0.2, ul[1][0], ul[1][1]), 13.05, 0.4, 1.6 * u, PAL.red, 0.7, 150, { thin: 0.7 });
  }

  sceneCache.set(key, sc);
  return sc;
}

// ---- camera: slow pans along the sheet
function camera(sc, t) {
  let k = 0;
  for (const [a, b] of PANS) k += B.span(t, a, b, "inOutSine");
  const i = Math.min(sc.ST.length - 2, Math.floor(k)), f = k - i, A = sc.ST[i], Bp = sc.ST[i + 1];
  // a hand-held pan: a slight sideways lift mid-move, a slow drift
  const dx = Bp[0] - A[0], dy = Bp[1] - A[1], dl = Math.hypot(dx, dy) || 1, lift = Math.sin(Math.PI * f) * 0.03 * Math.min(sc.W, sc.H);
  return [B.lerp(A[0], Bp[0], f) + (dy / dl) * lift + B.noise1(t * 0.13, 4) * 0.8 * sc.u, B.lerp(A[1], Bp[1], f) - (dx / dl) * lift + B.noise1(t * 0.11, 9) * 0.8 * sc.u];
}

// ---- frame
function draw(ctx, W, H, t) {
  T = t;
  const sc = scene(W, H), u = sc.u, [vx, vy] = camera(sc, t), view = { x: vx - 4 * u, y: vy - 4 * u, r: vx + W + 4 * u, b: vy + H + 4 * u };
  const seen = (bb) => bb.x < view.r && bb.x + bb.w > view.x && bb.y < view.b && bb.y + bb.h > view.y, tooth = ctx.createPattern(toothTile(), "repeat");
  ctx.save(); ctx.translate(-vx, -vy);
  ctx.fillStyle = PAL.paper; ctx.fillRect(vx, vy, W, H);
  const mottle = ctx.createPattern(loadTile(), "repeat"); // the sheet's large soft mottle, anchored to the paper
  mottle.setTransform(new DOMMatrix([2 * u, 0, 0, 2 * u, 0, 0]));
  ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.globalAlpha = 0.1; ctx.fillStyle = mottle; ctx.fillRect(vx, vy, W, H); ctx.restore();
  ctx.save(); ctx.globalCompositeOperation = "overlay"; ctx.globalAlpha = 0.5; ctx.fillStyle = tooth; ctx.fillRect(vx, vy, W, H); ctx.restore();
  // pencil first, then the paint over it
  for (const it of sc.pencil) if (seen(bboxOf(it.pts))) pencil(ctx, it, u);
  for (const w of sc.washes) if (seen(w.bbox)) drawWash(ctx, w, sc);
  for (const w of sc.washes) if (w.bloom && seen(w.bbox)) drawBloom(ctx, w, sc);
  for (const s of sc.strokes) if (seen(bboxOf(s.pts))) brushStroke(ctx, s.pts, { ...s, p: B.prog(t, s.at, s.dur, "inOutSine") });
  for (const it of sc.words) if (it.x > view.x - W && it.x < view.r + W && it.y > view.y - H * 0.3 && it.y < view.b + H * 0.3) brushWords(ctx, it);
  for (const it of sc.splats) splatter(ctx, it, u);
  // finishing: the tooth again over the paint, a soft warm vignette
  ctx.save(); ctx.globalCompositeOperation = "overlay"; ctx.globalAlpha = 0.28; ctx.fillStyle = tooth; ctx.fillRect(vx, vy, W, H); ctx.restore();
  ctx.restore();
  B.vignette(ctx, W, H, { color: "#d2b07a", amount: 0.24, inner: 0.5, mode: "multiply" });
}

// ---- sound: wet brush, water swells, a jar swirl and knocks, a bell chord
SOUND.define("wc-brush", (v, o) => { // a wet touch-down, then the hairs dragging
  const d = o.dur ?? 0.5;
  v.noise({ filter: "lowpass", f: 650, a: 0.004, len: 0.09, peak: 0.22 }); v.tone({ f: 150, f2: 95, glide: 0.07, a: 0.003, len: 0.09, peak: 0.08 });
  v.noise({ at: 0.03, filter: "bandpass", f: 3000, f2: 2100, glide: d, q: 0.8, a: 0.05, hold: d * 0.65, len: d * 0.3, peak: 0.08 });
  v.grains({ at: 0.03, span: d, count: d * 40, filter: "highpass", f: 4200, len: 0.006, peak: 0.04 });
}, { verb: 0.15 });
SOUND.define("wc-flood", (v, o) => {
  const d = o.dur ?? 1.0;
  v.noise({ brown: true, filter: "lowpass", f: 260, f2: 650, glide: d, a: d * 0.55, len: d * 0.6, peak: 0.22 }); // a low swell of water
}, { verb: 0.3 });
SOUND.define("wc-swirl", (v, o) => { // a brush swirled in the water jar
  const d = o.dur ?? 0.7, n = v.noise({ brown: true, filter: "bandpass", f: 520, q: 1.4, a: 0.12, hold: d * 0.5, len: d * 0.4, peak: 0.16 });
  v.lfo(n.filter.frequency, 5.5, 260, v.t + d + 0.2);
  for (let i = 0; i < 9; i++) { const f = 300 + v.rng() * 500; v.tone({ at: v.rng() * d, f, f2: f * 1.9, glide: 0.05, a: 0.003, len: 0.06, peak: 0.05 }); }
}, { verb: 0.3 });

function score(k) {
  const sc = scene(1080, 1920), pan = (i) => (B.hash01(i, "pan") - 0.5) * 0.6;
  k.bed("room", 0, DUR, { gain: 0.55 }).bed("pad", 0, DUR, { notes: ["F2", "C3", "A3", "E4"], gain: 0.4, bright: 480 });
  // the sound follows the painting: pencil, each wash floods in, each stroke and word is brushed
  sc.pencil.forEach((it, i) => k.at(it.at, "pencil", { dur: it.dur, gain: 0.35, pan: pan(i) }));
  sc.washes.forEach((w, i) => k.at(w.at, "wc-flood", { dur: w.dur + 0.4, gain: 0.45, pitch: -(i % 4), pan: pan(i + 50) }));
  sc.strokes.forEach((s, i) => k.at(s.at, "wc-brush", { dur: s.dur, gain: 0.55, pitch: i % 3 - 1, pan: pan(i + 100) }));
  sc.words.forEach((w, i) => k.at(w.at, "wc-brush", { dur: 0.3, gain: 0.5, pan: pan(i + 200) }));
  // scene changes: swirl the brush in the jar, knock it twice
  PANS.forEach(([a]) => k.at(a, "wc-swirl", { dur: 0.7, gain: 0.8 }).at(a + 0.78, "knock", { pitch: 9, gain: 0.6 }).at(a + 0.95, "knock", { pitch: 8, gain: 0.5 }).at(a + 0.1, "breath", { dur: 1.2, gain: 0.45 }));
  [1.6, 3.7, 7.0, 12.6, 12.85].forEach((t, i) => k.at(t, "bubble", { gain: 0.4, pitch: i - 6 })); // single soft drops
  // the key moment: a soft bell chord as 40 is repainted 42
  k.at(6.62, "bell", { note: "F4", gain: 0.45 }).at(6.64, "bell", { note: "A4", gain: 0.35 }).at(6.66, "bell", { note: "C5", gain: 0.35 }).at(6.7, "chime", { note: "E6", gain: 0.25 });
  ["A4", "C5", "E5"].forEach((note, i) => k.at([8.3, 8.8, 9.3][i], "marimba", { note, gain: 0.3 }));
  k.at(13.1, "chord", { notes: ["F4", "A4", "C5", "E5"], strum: 0.06, gain: 0.5 }).at(13.2, "chime", { note: "C6", gain: 0.3 });
}

Player.register({
  id: "watercolor", name: "Watercolour Bloom", duration: DUR,
  fonts: { href: "https://fonts.googleapis.com/css2?family=Caveat+Brush&display=swap", faces: ['400 20px "Caveat Brush"'] },
  beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three steps", "One colour each", "Close"],
  stills: [2.3, 4.95, 7.45, 9.9, 11.15, 13.8],
  draw, score,
});
})();
