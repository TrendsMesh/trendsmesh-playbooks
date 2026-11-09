// Check an animation page's layout the way a viewer on a phone meets it: every piece of text big enough to read,
// nothing a viewer must read outside the safe area or off the frame, and no large dead band in a vertical frame.
// Usage: node layout_check.mjs <page.html> --browser <path> [--no-sandbox] [--step 0.25]
// The page is a play-mode page (window.seek, window.DURATION, a <canvas> at the frame size). Prints one JSON line:
// { size, duration, small: [...], outside: [...], empty: [...], texture: n, page_errors: [...] }.
//
// How text is measured: fillText and strokeText are wrapped before the page's scripts run, so every string drawn
// on any canvas is recorded with its font size, the canvas transform and its box. Text drawn on a helper canvas is
// followed through every drawImage of that canvas onto the frame, so a label drawn small and scaled up (or drawn
// big and scaled down) counts at the size it is seen. Text is judged wherever it is visible on the frame and
// settled (its size steady, moving slower than a transition), every time: an entrance, a zoom or a slide in
// progress is not judged, the moment it settles is.
// Text drawn inside Brush.texture(ctx, fn) is texture (newspaper body copy, tiny cells of a title block) and is
// exempt from the size rule; it is counted so a reviewer can see how much there is. Text drawn mirrored (a
// reflection in a puddle or glass) is not read, so it is not judged. Known limit: text rubbed out later by a
// destination-out draw still counts as shown; put text that is meant to be erased inside Brush.texture.
//
// Rules, from the build prompt (tm/atlas_prompt.py): every label at least 3.8 % of the frame's short side
// (41 px at 1080x1920, 27 px at 1280x720). Safe area: a vertical frame keeps its top 14 % and bottom 20 % free of
// anything a viewer must read; a landscape or square frame keeps 5 % at the top and bottom. Every frame keeps 3 %
// at the sides. Dead band: in a vertical frame, at the middle and the end of each beat, no stretch of a quarter of
// the safe band's height or more is empty (no shapes or text, only backdrop and grain).
import puppeteer from "puppeteer-core";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const page_ = args[0];
const executablePath = opt("--browser", "");
if (!page_ || !executablePath) { console.error("usage: node layout_check.mjs <page.html> --browser <path> [--no-sandbox] [--step 0.25]"); process.exit(2); }
const NO_SANDBOX = args.includes("--no-sandbox") ? ["--no-sandbox"] : [];
const step = +opt("--step", 0.25);

// Runs in the page before its scripts: for every canvas, the text drawn on it and the canvases drawn onto it, kept
// until that canvas is drawn on again in a later frame (then it is being redrawn) or cleared whole. So a cache that
// was painted once (and caches built from caches) keeps what it holds for every frame it is shown in, and a canvas
// redrawn each frame holds only that frame's.
function instrument() {
  const C2D = CanvasRenderingContext2D.prototype;
  const state = new WeakMap();   // canvas -> { frame, texts: [{ text, px, box, alpha, texture }], edges: [{ src, m, alpha }] }
  const st = { frame: 0 };
  window.__tmLayout = { state, st };
  const touch = (canvas) => {
    let s = state.get(canvas);
    if (!s || s.frame !== st.frame) { s = { frame: st.frame, texts: [], edges: [] }; state.set(canvas, s); }
    return s;
  };
  const px = (font) => { const m = /(\d+(?:\.\d+)?)px/.exec(font || ""); return m ? +m[1] : 10; };
  const wrap = (name) => {
    const orig = C2D[name];
    C2D[name] = function (text, x, y, maxWidth) {
      try {
        const s = String(text);
        if (s.trim()) {
          const m = this.getTransform();
          const k = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
          const mt = this.measureText(s);
          let left = mt.actualBoundingBoxLeft, right = mt.actualBoundingBoxRight;
          if (maxWidth != null && mt.width > maxWidth && mt.width > 0) { const f = maxWidth / mt.width; left *= f; right *= f; }
          const pts = [[x - left, y - mt.actualBoundingBoxAscent], [x + right, y - mt.actualBoundingBoxAscent],
                       [x - left, y + mt.actualBoundingBoxDescent], [x + right, y + mt.actualBoundingBoxDescent]]
            .map(([a, b]) => [m.a * a + m.c * b + m.e, m.b * a + m.d * b + m.f]);
          const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
          touch(this.canvas).texts.push({ text: s, px: px(this.font) * k, alpha: this.globalAlpha,
            flip: m.a * m.d - m.b * m.c < 0,
            box: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
            texture: !!(this.__tmTexture || this.canvas.__tmTexture) });
        }
      } catch (e) { /* measuring never breaks drawing */ }
      return orig.apply(this, arguments);
    };
  };
  wrap("fillText"); wrap("strokeText");
  const clear = C2D.clearRect;
  C2D.clearRect = function (x, y, w, h) {
    try {
      const m = this.getTransform();
      if (m.isIdentity && x <= 0 && y <= 0 && x + w >= this.canvas.width && y + h >= this.canvas.height) state.delete(this.canvas);
    } catch (e) { /* ignore */ }
    return clear.apply(this, arguments);
  };
  const draw = C2D.drawImage;
  C2D.drawImage = function (img, ...a) {
    try {
      if (img && img !== this.canvas && (img instanceof HTMLCanvasElement || (typeof OffscreenCanvas !== "undefined" && img instanceof OffscreenCanvas))) {
        let sx = 0, sy = 0, sw = img.width, sh = img.height, dx, dy, dw = img.width, dh = img.height;
        if (a.length === 2) [dx, dy] = a;
        else if (a.length === 4) [dx, dy, dw, dh] = a;
        else [sx, sy, sw, sh, dx, dy, dw, dh] = a;
        const m = this.getTransform().translate(dx, dy).scale(dw / sw, dh / sh).translate(-sx, -sy);
        touch(this.canvas).edges.push({ src: img, m, alpha: this.globalAlpha, clip: [sx, sy, sx + sw, sy + sh] });
      }
    } catch (e) { /* ignore */ }
    return draw.apply(this, [img, ...a]);
  };
}

// Runs in the page after a seek: every text seen on the frame canvas, in frame pixels. A canvas can reach the frame
// several ways (a faint ghost pass and the real one, glow passes): each distinct way is followed once, and a string
// seen in the same place more than once keeps its most visible copy.
function collect() {
  const { state } = window.__tmLayout;
  const mainCanvas = [...document.querySelectorAll("canvas")].sort((p, q) => q.width * q.height - p.width * p.height)[0];
  const ids = new Map();
  const id = (c) => { if (!ids.has(c)) ids.set(c, ids.size); return ids.get(c); };
  const found = new Map();                        // text|box -> record (most visible kept)
  const walked = new Set();                       // canvas + transform + alpha already followed
  // clip: the part of this canvas the draw took (drawImage's source rectangle), in this canvas's pixels.
  const visit = (canvas, m, alpha, depth, clip) => {
    if (depth > 8) return;
    const way = [id(canvas), m.a, m.b, m.c, m.d, m.e, m.f, alpha, ...(clip || [])].map((v) => Math.round(v * 100) / 100).join(",");
    if (walked.has(way)) return;
    walked.add(way);
    const s = state.get(canvas);
    if (!s) return;
    const det = m.a * m.d - m.b * m.c, k = Math.sqrt(Math.abs(det));
    for (const r of s.texts) {
      if (r.flip !== det < 0) continue;           // drawn mirrored: a reflection, not something to read
      let [x0, y0, x1, y1] = r.box;
      if (clip) {                                 // only the part of the text inside the slice is shown
        x0 = Math.max(x0, clip[0]); y0 = Math.max(y0, clip[1]); x1 = Math.min(x1, clip[2]); y1 = Math.min(y1, clip[3]);
        if (x1 <= x0 || y1 <= y0) continue;
      }
      const pts = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([a, b]) => [m.a * a + m.c * b + m.e, m.b * a + m.d * b + m.f]);
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)].map((v) => Math.round(v));
      const key = r.text + "|" + box.join(",");
      const rec = { text: r.text, px: r.px * k, alpha: r.alpha * alpha, texture: r.texture, box };
      const had = found.get(key);
      if (!had || rec.alpha > had.alpha) found.set(key, rec);
    }
    if (walked.size > 20000) return;              // a runaway graph: what was found so far is enough
    for (const e of s.edges) visit(e.src, m.multiply(e.m), alpha * e.alpha, depth + 1, e.clip);
  };
  visit(mainCanvas, new DOMMatrix(), 1, 0, null);
  return [...found.values()];
}

// Runs in the page: rows of the frame, coarse, scored by how much changes along and across them.
function rows() {
  const c = [...document.querySelectorAll("canvas")].sort((p, q) => q.width * q.height - p.width * p.height)[0];
  const W = 54, H = Math.round((c.height / c.width) * W);
  const s = document.createElement("canvas"); s.width = W; s.height = H;
  const g = s.getContext("2d"); g.imageSmoothingQuality = "high"; g.drawImage(c, 0, 0, W, H);
  const d = g.getImageData(0, 0, W, H).data;
  const L = (x, y) => { const i = (y * W + x) * 4; return 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; };
  const out = [];
  for (let y = 0; y < H; y++) {
    let v = 0;
    for (let x = 1; x < W; x++) v += Math.abs(L(x, y) - L(x - 1, y)) + (y ? Math.abs(L(x, y) - L(x, y - 1)) : 0);
    out.push(v / W);
  }
  return out;
}

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--allow-file-access-from-files", ...NO_SANDBOX] });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.setViewport({ width: 1300, height: 1000 });
  await page.evaluateOnNewDocument(instrument);
  await page.goto(pathToFileURL(resolve(page_)).href, { waitUntil: "networkidle0", timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction("typeof window.seek === 'function' && window.DURATION > 0", { timeout: 60000 });
  await new Promise((r) => setTimeout(r, 300));     // the runtime clears cached layers once fonts are in
  const info = await page.evaluate(() => {
    const c = [...document.querySelectorAll("canvas")].sort((p, q) => q.width * q.height - p.width * p.height)[0];
    return { W: c.width, H: c.height, D: window.DURATION, beats: (window.Player && Player.style && Player.style.beats) || [] };
  });
  const { W, H, D } = info;
  const short = Math.min(W, H), vertical = H > W;
  const minPx = Math.round(short * 0.038);
  const safe = { top: Math.round(H * (vertical ? 0.14 : 0.05)), bottom: Math.round(H * (vertical ? 0.80 : 0.95)),
                 left: Math.round(W * 0.03), right: Math.round(W * 0.97) };

  // Text wholly off the frame (a beat panned away, still drawn) is not seen, so it is not judged.
  const onFrame = (r) => r.box[2] > 0 && r.box[0] < W && r.box[3] > 0 && r.box[1] < H;
  let frame = 0;
  const times = [];
  for (let t = 0; t <= D - 1e-6; t += step) times.push(+t.toFixed(3));
  times.push(+(D - 0.02).toFixed(3));
  const samples = [];
  for (const t of times) {
    frame += 1;
    await page.evaluate((t, f) => { window.__tmLayout.st.frame = f; window.seek(t); }, t, frame);
    samples.push({ t, list: await page.evaluate(collect) });
  }
  // Judged: text that is on the frame, visible and settled: a step later its size is within 3 % and it has moved
  // less than a transition would (40 px a step); idle drift and slow camera moves count, an entrance, a zoom or a
  // slide in progress does not. Every settled moment counts, so a label shown big in one beat and small in
  // another is caught where it is small.
  // The last frame is where the piece comes to rest, so everything on it is judged, moving or not.
  // A string is matched to its nearest copy a step later (letters drawn one by one repeat), and a frame whose
  // text moves as a whole by more than a transition would (the camera panning) has nothing settled in it.
  const shift = (a, b) => Math.abs(a.box[0] - b.box[0]) + Math.abs(a.box[1] - b.box[1]);
  const once = (list) => { const n = new Map(); for (const r of list) n.set(r.text, n.has(r.text) ? null : r); return n; };
  const pans = samples.map((sm, i) => {
    const next = samples[i + 1];
    if (!next) return false;
    const a = once(sm.list), b = once(next.list), moves = [];
    for (const [text, r] of a) { const q = b.get(text); if (r && q) moves.push(shift(r, q)); }
    if (moves.length < 3) return false;
    moves.sort((x, y) => x - y);
    return moves[Math.floor(moves.length / 2)] > 40;
  });
  const still = (r, i) => {
    const next = samples[i + 1];
    if (!next) return true;
    if (pans[i]) return false;
    let best = null;
    for (const q of next.list) if (q.text === r.text && (!best || shift(q, r) < shift(best, r))) best = q;
    return !!best && Math.abs(best.px - r.px) <= r.px * 0.03 && shift(best, r) <= 40;
  };
  const smallest = new Map(), texture = new Set(), outside = [], told = new Set();
  for (let i = 0; i < samples.length; i++) {
    const { t, list } = samples[i];
    for (const r of list) {
      if (!onFrame(r)) continue;
      if (r.texture) { texture.add(r.text); continue; }
      if (r.alpha < 0.6 || !still(r, i)) continue;
      if (r.px < minPx - 0.5) {
        const s = smallest.get(r.text);
        if (!s || r.px < s.px) smallest.set(r.text, { px: r.px, t });
      }
      const [x0, y0, x1, y1] = r.box;
      const off = [];
      if (y0 < safe.top) off.push("top"); if (y1 > safe.bottom) off.push("bottom");
      if (x0 < safe.left) off.push("left"); if (x1 > safe.right) off.push("right");
      const key = r.text + off.join();
      if (off.length && !told.has(key)) { told.add(key); outside.push({ text: r.text.slice(0, 60), t, box: r.box, side: off }); }
    }
  }
  const small = [...smallest].map(([text, s]) => ({ text: text.slice(0, 60), px: Math.round(s.px * 10) / 10, min: minPx, t: s.t }));
  const empty = [];
  if (vertical) {
    const beats = info.beats.length ? info.beats.concat([D]) : [0, D];
    const checks = [];
    for (let i = 0; i + 1 < beats.length; i++) {
      const a = beats[i], b = beats[i + 1];
      checks.push(+(a + (b - a) * 0.5).toFixed(3), +(a + (b - a) * 0.92).toFixed(3));
    }
    for (const t of checks) {
      frame += 1;
      await page.evaluate((t, f) => { window.__tmLayout.st.frame = f; window.seek(t); }, t, frame);
      const r = await page.evaluate(rows);
      const n = r.length, top = Math.round(n * 0.14), bot = Math.round(n * 0.80);
      const band = r.slice(top, bot);
      const sorted = band.slice().sort((p, q) => p - q);
      const busy = sorted[Math.floor(sorted.length * 0.9)] || 0;
      const quiet = band.map((v) => v < Math.max(busy * 0.12, 0.6));
      let run = 0, start = 0;
      const need = Math.ceil(band.length * 0.25);
      for (let i = 0; i <= band.length; i++) {
        if (i < band.length && quiet[i]) { if (!run) start = i; run += 1; continue; }
        if (run >= need) empty.push({ t, from: Math.round(((top + start) / n) * H), to: Math.round(((top + start + run) / n) * H) });
        run = 0;
      }
    }
  }
  console.log(JSON.stringify({ size: [W, H], duration: D, min_label_px: minPx, small, outside, empty,
                               texture: texture.size, page_errors: errors.slice(0, 10) }));
} finally {
  await browser.close();
}
