/* 35 Woodblock Print - reference animation.
 * Topic (setting, replace it): "How do salmon find their way home?" - the salmon run.
 * Rendering (keep it): an Edo print on washi. One plate per ink, pressed in multiply a hair off register; one
 * bokashi fade per print; a key block whose carved line swells, thins and chips; waves as repeated carved curves;
 * cartouches; seals. Pad patches and grain knocked out of every plate; fibres, chain lines, yellowed edges.
 * Motion: key first, then inks light to dark, each a quick fade and settle; waves re-print on a slow beat; a scene
 * change peels the old sheet off from the corner, its back showing the print through.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // --- palette and type (from the card)
  const PAL = { paper: "#efe3c8", key: "#1d1a1a", indigo: "#1c3557", blue: "#4a7a9e", sky: "#cfe0df", ochre: "#d9a441", red: "#c8372d", moss: "#6b7f4e", board: "#6d5a43" };
  const SERIF = "Shippori Mincho", BRUSHF = "Yuji Syuku";
  const DUR = 13;
  const BEATS = [0, 2.2, 4.6, 7.1, 9.5, 11.1];
  // one sheet per print; the pressing starts at `at`, the peel to it ends at `from`
  const PEEL = 0.6; // the peel runs from (from - PEEL) to from; the next print is already being pressed under it
  const PRINTS = [0, 2.2, 4.6, 7.1, 11.1].map((from, i) => ({ from, at: i ? from - PEEL * 0.75 : 0.05 }));

  // --- the blocks: one offscreen plate per ink
  // printing order, lightest first: the composite order and the pressing order
  const ORDER = ["sky", "ochre", "moss", "blue", "red", "indigo"];
  const DELAY = { key: 0, sky: 0.16, ochre: 0.3, moss: 0.44, blue: 0.58, red: 0.72, indigo: 0.86 };
  const REG = { sky: [0.22, -0.16], ochre: [-0.2, 0.24], moss: [0.26, 0.18], blue: [-0.24, -0.2], red: [0.18, 0.26], indigo: [-0.12, 0.3], key: [0, 0] };
  let G = {}, U = 1, T = 0, F = null, SPD = 1; // SPD < 1: a quick re-print, the inks close together

  /** Ink fn(g) onto a plate at `at` + its delay: quick fade, small settle. */
  function ink(plate, at, fn) {
    const dt = T - at - DELAY[plate] * SPD;
    if (dt <= 0) return;
    const k = B.clamp(dt / 0.12), g = G[plate], settle = (1 - B.ease.outCubic(B.clamp(dt / 0.22))) * 0.7 * U;
    g.save();
    g.globalAlpha *= k;
    g.translate(settle * 0.6, -settle);
    fn(g);
    g.restore();
  }
  /** A flat block of colour with its carved key outline. */
  function block(plate, pts, at, o = {}) {
    if (o.knock) cut(ORDER.filter((p) => p !== plate), (g) => B.poly(g, pts, true), at); // carved so inks never overlap
    ink(plate, at, (g) => {
      g.beginPath();
      B.poly(g, pts, true);
      g.fillStyle = PAL[plate];
      if (o.alpha) g.globalAlpha *= o.alpha;
      g.fill();
    });
    if (o.line !== false) ink("key", at, (g) => carve(g, pts, o.w ?? 0.42 * U, o.seed ?? 1, true));
  }
  /** Bokashi: an ink wiped from full at (x0, y0) to none at (x1, y1). */
  function bokashi(plate, pts, at, x0, y0, x1, y1, peak = 1) {
    ink(plate, at, (g) => {
      g.beginPath();
      B.poly(g, pts, true);
      g.fillStyle = B.linear(g, x0, y0, x1, y1, [[0, B.rgba(PAL[plate], peak)], [0.55, B.rgba(PAL[plate], peak * 0.35)], [1, B.rgba(PAL[plate], 0)]]);
      g.fill();
    });
  }
  /** Leave paper: cut a shape out of the given plates. */
  function cut(plates, pathFn, at, alpha = 1) {
    plates.forEach((p) => {
      const g = G[p];
      if (T < at) return;
      g.save();
      g.globalCompositeOperation = "destination-out";
      g.globalAlpha = alpha * B.clamp((T - at) / 0.12);
      g.beginPath();
      pathFn(g);
      g.fill();
      g.restore();
    });
  }
  /** Carved key line: tapered ribbons that swell and thin, with chips where the knife lifted. */
  function carve(g, pts, w, seed, closed) {
    let path = closed ? pts.concat([pts[0]]) : pts;
    path = B.densify(path, Math.max(1.5, w * 0.9));
    const r = B.rng(seed * 131 + 7);
    let s = 0, gap = false, next = r.range(14, 40) * w, piece = [path[0]];
    const pieces = [];
    for (let i = 1; i < path.length; i++) {
      s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
      if (s > next) {
        if (!gap) pieces.push(piece);
        gap = !gap;
        piece = [path[i]];
        next = s + (gap ? r.range(0.6, 1.5) * w : r.range(14, 46) * w);
      } else if (!gap) piece.push(path[i]);
    }
    if (!gap) pieces.push(piece);
    pieces.forEach((pc, i) => {
      if (pc.length > 1) B.taperStroke(g, pc, { width: w, color: PAL.key, taperIn: 0.05, taperOut: 0.05, rough: 0.5, roughScale: 2.2, seed: seed + i });
    });
  }
  /** Value by aspect: (portrait, landscape). */
  const PL = (portrait, landscape) => (F.portrait ? portrait : landscape);
  /** The path d to the side of a centre line (for arrows that follow a river). */
  const beside = (pts, d) => pts.map((q, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    return [q[0] - ((b[1] - a[1]) / l) * d, q[1] + ((b[0] - a[0]) / l) * d];
  });
  const rect = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  const xf = (x0, y0, rot, s) => (p) => [x0 + (p[0] * Math.cos(rot) - p[1] * Math.sin(rot)) * s, y0 + (p[0] * Math.sin(rot) + p[1] * Math.cos(rot)) * s];

  // --- the paper (cached) and press textures
  /** Washi sheet with a deckled edge over the board, fibres and faint chain lines. */
  function sheet(W, H) {
    return B.layer("wb-sheet", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(35);
      g.fillStyle = PAL.board;
      g.fillRect(0, 0, w, h);
      const m = 1.1 * u, edge = [];
      const side = (x0, y0, x1, y1) => {
        const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / (0.6 * u));
        for (let i = 0; i < n; i++) edge.push([B.lerp(x0, x1, i / n) + r.range(-0.25, 0.25) * u, B.lerp(y0, y1, i / n) + r.range(-0.25, 0.25) * u]);
      };
      const cs = [[m, m], [w - m, m], [w - m, h - m], [m, h - m]];
      cs.forEach((c, i) => side(...c, ...cs[(i + 1) % 4]));
      g.save();
      g.beginPath();
      B.poly(g, edge, true);
      g.clip();
      B.paper(g, w, h, { color: PAL.paper, seed: 35, mottle: 0.1, fibers: 0.25, specks: 0.15, tooth: 0.05 });
      g.strokeStyle = B.rgba("#8a6d3f", 0.05); // chain lines from the papermaker's screen
      g.lineWidth = 0.35 * u;
      for (let x = r.range(2, 5) * u; x < w; x += 6.5 * u) {
        g.beginPath();
        g.moveTo(x, 0);
        g.lineTo(x + r.range(-0.5, 0.5) * u, h);
        g.stroke();
      }
      g.restore();
    });
  }
  /** Long kozo fibres, a little lighter than the paper. */
  function fibres(W, H) {
    return B.layer("wb-fibres", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(9);
      g.lineCap = "round";
      g.filter = `blur(${(0.06 * u).toFixed(2)}px)`; // soft kozo fibres, not scratches
      for (let i = 0; i < (w * h) / (u * u) * 0.05; i++) {
        const x = r() * w, y = r() * h, a = r() * B.TAU, len = r.range(1.5, 6) * u, bend = r.range(-0.9, 0.9);
        g.strokeStyle = r() < 0.7 ? B.rgba("#f6eedb", r.range(0.2, 0.4)) : B.rgba("#b59a6c", 0.12);
        g.lineWidth = r.range(0.05, 0.11) * u;
        g.beginPath();
        g.moveTo(x, y);
        g.quadraticCurveTo(x + Math.cos(a + bend) * len * 0.5, y + Math.sin(a + bend) * len * 0.5, x + Math.cos(a) * len, y + Math.sin(a) * len);
        g.stroke();
      }
    });
  }
  /** Alpha texture: pad patches or wood-grain streaks. */
  function alphaTex(kind, W, H) {
    const cell = kind === "grain" ? 2 : 6;
    return B.layer("wb-" + kind, Math.ceil(W / cell) + 40, Math.ceil(H / cell) + 40, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, u = Math.min(W, H) / 100 / cell;
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          let a;
          if (kind === "grain") {
            const v = Math.sin((y + B.noise2(x / (40 * u), y / (12 * u), 3) * 9 * u) / (0.55 * u) + B.noise2(x / (90 * u), 0, 5) * 3);
            a = B.smooth(0.55, 0.95, v) * (0.5 + 0.5 * B.noise2(x / (25 * u), y / (4 * u), 8));
          } else a = B.smooth(0.05, 0.55, B.fbm(x / (14 * u), y / (14 * u), 3, 21));
          d[(y * w + x) * 4 + 3] = B.clamp(a) * 255;
        }
      g.putImageData(img, 0, 0);
    });
  }
  /** Press a plate unevenly: patches and grain knocked out of the colour. */
  function pressTexture(g, W, H, i, isKey) {
    const pad = alphaTex("pad", W, H), grain = alphaTex("grain", W, H), o = (i * 37) % 40;
    g.save();
    g.globalCompositeOperation = "destination-out";
    g.globalAlpha = isKey ? 0.1 : 0.15;
    g.drawImage(pad, -o * 6, -((i * 23) % 40) * 6, pad.width * 6, pad.height * 6);
    if (!isKey) {
      g.globalAlpha = 0.18;
      g.drawImage(grain, -o * 2, -((i * 11) % 40) * 2, grain.width * 2, grain.height * 2);
    }
    g.restore();
  }

  // --- print furniture (reuse these)
  /** A tall cartouche: pale panel, thin double border, short brush lines stacked. */
  function cartouche(x, y, lines, at, o = {}) {
    const size = o.size ?? 4 * U, lh = size * 1.22, g = G.key;
    g.save();
    g.font = B.font(size, BRUSHF, 400);
    const tw = Math.max(...lines.map((l) => g.measureText(l).width));
    g.restore();
    const num = o.num != null, w = tw + size * 1.3, h = lines.length * lh + size * 0.9 + (num ? size * 1.85 : 0);
    const x0 = o.align === "center" ? x - w / 2 : o.align === "right" ? x - w : x, box = rect(x0, y, w, h);
    cut(ORDER.concat("key"), (c) => c.rect(x0, y, w, h), at); // the panel is paper: no block prints there
    block(o.tint || "ochre", box, at, { alpha: o.tintAlpha ?? 0.32, w: 0.3 * U, seed: 70 + lines.length });
    ink("key", at, (c) => carve(c, rect(x0 + size * 0.22, y + size * 0.22, w - size * 0.44, h - size * 0.44), 0.16 * U, 77, true));
    let ty = y + size * 0.45;
    if (num) {
      const s = size * 1.4;
      seal(x0 + w / 2, ty + s / 2 + size * 0.05, s, at + 0.25, String(o.num));
      ty += size * 1.85;
    }
    ink("key", at, (c) => lines.forEach((l, i) => B.text(c, l, x0 + w / 2, ty + lh * (i + 0.5), { size, family: BRUSHF, weight: 400, color: PAL.key })));
    return { x: x0, y, w, h };
  }
  /** Vermilion seal, stamped big then pressed down, with paper-white marks. */
  function seal(cx, cy, s, at, label) {
    if (T < at) return;
    const k = B.clamp((T - at) / 0.16), sc = 1 + 0.18 * (1 - B.ease.outCubic(k));
    const g = G.red, r = B.rng(B.hash("seal", cx | 0, cy | 0));
    const h = (s * sc) / 2, pts = [[-h, -h], [h, -h], [h, h], [-h, h]].map(([x, y]) => [cx + x + r.range(-0.03, 0.03) * s, cy + y + r.range(-0.03, 0.03) * s]);
    g.save();
    g.globalAlpha = k;
    g.fillStyle = PAL.red;
    g.beginPath();
    B.poly(g, pts, true);
    g.fill();
    g.globalCompositeOperation = "destination-out"; // the carved marks print as paper
    const m = s * 0.13;
    B.taperStroke(g, (([a, ...r]) => [a, ...r, a])(rect(cx - h + m, cy - h + m, 2 * (h - m), 2 * (h - m))), { width: s * 0.06, taperIn: 0, taperOut: 0, rough: 0.6, seed: 3 });
    if (label) B.text(g, label, cx, cy + s * 0.04, { size: s * 0.78, family: SERIF, weight: 800, color: "#000" });
    else {
      for (let i = 0; i < 3; i++) B.taperStroke(g, [[cx - s * 0.22, cy - s * 0.2 + i * s * 0.2], [cx + s * 0.22, cy - s * 0.24 + i * s * 0.2]], { width: s * 0.08, rough: 0.5, seed: 9 + i });
      B.taperStroke(g, [[cx, cy - s * 0.3], [cx + s * 0.02, cy + s * 0.32]], { width: s * 0.08, rough: 0.5, seed: 14 });
    }
    g.restore();
  }
  /** Carved arrow: a vermilion band with a key outline along a path, pressed whole. */
  function carvedArrow(path, at, w) {
    const sh = B.densify(B.trim(path, 0, 1 - (w * 1.6) / B.pathLength(path)), w * 0.4), L = [], R = [];
    sh.forEach((q, i) => {
      const a = sh[Math.max(0, i - 1)], b = sh[Math.min(sh.length - 1, i + 1)];
      const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / l, ny = (b[0] - a[0]) / l, hw = w * 0.5 * (0.55 + 0.45 * (i / sh.length));
      L.push([q[0] + nx * hw, q[1] + ny * hw]);
      R.push([q[0] - nx * hw, q[1] - ny * hw]);
    });
    const tip = B.pointAt(path, 1), base = sh[sh.length - 1], nx = -Math.sin(tip[2]), ny = Math.cos(tip[2]), hw = w * 1.15;
    block("red", L.concat([[base[0] + nx * hw, base[1] + ny * hw], [tip[0], tip[1]], [base[0] - nx * hw, base[1] - ny * hw]], R.reverse()), at, { w: 0.38 * U, seed: 41, knock: true });
  }
  /** Rolling sea: blue block, rows of indigo crests with carved scallops and paper foam curls. */
  function sea(top, bottom, at, step, o = {}) {
    const W = F.W, pw = (o.pw ?? 13) * U, rows = o.rows ?? 4, gapY = (bottom - top) / (rows + 0.3);
    block("blue", rect(-2 * U, top, W + 4 * U, bottom - top + 2 * U), at, { line: false });
    ink("key", at, (g) => carve(g, [[-2 * U, top], [W + 2 * U, top]], 0.45 * U, 5, false));
    for (let r = 0; r < rows; r++) {
      const y = top + gapY * (r + 0.55), shift = ((step * 0.37 + r * 0.5) % 1) * pw, crest = [], band = [];
      for (let x = -pw * 2 + shift; x < W + pw * 2; x += pw) {
        for (let i = 0; i <= 10; i++) {
          const a = i / 10, px = x + a * pw, py = y - Math.sin(a * Math.PI) * gapY * 0.32 * (0.7 + 0.3 * Math.sin(r + x / pw));
          crest.push([px, py]);
        }
      }
      crest.forEach((p) => band.push([p[0], p[1] + gapY * 0.28]));
      block("indigo", crest.concat(band.reverse()), at, { line: false, alpha: 0.85 });
      ink("key", at, (g) => {
        carve(g, crest, 0.38 * U, 11 + r, false);
        carve(g, crest.map((p) => [p[0], p[1] + gapY * 0.13]), 0.16 * U, 21 + r, false);
      });
      // foam: claw-like curls cut back to paper at each crest
      cut(["indigo", "blue"], (g) => {
        for (let x = -pw * 2 + shift, j = 0; x < W + pw * 2; x += pw, j++) {
          const cx = x + pw * 0.55, cy = y - gapY * 0.2;
          for (let f = 0; f < 3; f++) {
            const a0 = -2.4 + f * 0.5, r0 = (0.7 + f * 0.35) * U;
            g.moveTo(cx + Math.cos(a0) * r0 + f * 1.1 * U, cy + Math.sin(a0) * r0);
            g.arc(cx + f * 1.1 * U, cy, r0, a0, a0 + 1.6);
            g.arc(cx + f * 1.1 * U, cy, r0 * 0.55, a0 + 1.6, a0 + 0.2, true);
          }
        }
      }, at + DELAY.indigo);
    }
  }
  /** Mountain: blue block, paper snow cap, indigo bokashi from the peak. */
  function mountain(cx, base, hgt, half, at) {
    const M = (a) => a.map(([x, y]) => [cx + half * x, base - hgt * y]), pts = M([[-1, 0], [-0.35, 0.78], [-0.1, 1], [0.12, 0.97], [0.45, 0.62], [1, 0]]);
    block("blue", pts, at, { seed: 61, alpha: 0.75 });
    bokashi("indigo", pts, at, cx, base - hgt, cx, base - hgt * 0.35, 0.8);
    const snow = M([[-0.3, 0.72], [-0.1, 1], [0.12, 0.97], [0.32, 0.72], [0.18, 0.76], [0.08, 0.68], [-0.03, 0.79], [-0.16, 0.69]]);
    cut(["blue", "indigo"], (g) => B.poly(g, snow, true), at + DELAY.indigo);
    ink("key", at, (g) => carve(g, snow.slice(3).concat([snow[0]]), 0.28 * U, 62, false));
  }
  /** Kasumi cloud: a short rounded band riding on a long one, one carved outline; re-printed shifted. */
  function cloudBand(x, y, w, h, at, step) {
    const X = x + ((step % 3) - 1) * 0.8 * U, yT = y + h * 0.46, ru = h * 0.24, rl = (y + h - yT) / 2, cyU = y + ru, cyL = yT + rl;
    const a = X + w * 0.1, b = X + w * 0.58, th = Math.asin((yT - cyU) / ru), PI = Math.PI;
    const pts = [].concat(B.arcPts(a + ru, cyU, ru, PI - th, 1.5 * PI, 10), B.arcPts(b - ru, cyU, ru, 1.5 * PI, 2 * PI + th, 10),
      B.arcPts(X + w - rl, cyL, rl, -PI / 2, PI / 2, 12), B.arcPts(X + rl, cyL, rl, PI / 2, 1.5 * PI, 12));
    block("ochre", pts, at, { alpha: 0.55, w: 0.32 * U, seed: 80 + (x | 0) % 7, knock: true });
    ink("key", at, (g) => carve(g, [[X + w * 0.66, cyL], [X + w - rl * 1.6, cyL]], 0.14 * U, 88, false)); // one carved streak
  }
  function sky(top, bottom, at) {
    const pts = rect(-2 * U, top - 2 * U, F.W + 4 * U, bottom - top + 2 * U);
    block("sky", pts, at, { line: false });
    bokashi("indigo", pts, at, 0, top, 0, B.lerp(top, bottom, 0.55), 0.95); // the wiped band of deep blue at the top
  }

  // --- subjects (the setting: replace these)
  /** A spawning sockeye salmon: vermilion body, moss head, carved scales. */
  function salmon(x, y, s, rot, at, o = {}) {
    const tf = xf(x, y, rot, s);
    const top = B.quad(-0.8, -0.06, 0.05, -0.62, 1.05, 0.02, 20), bot = B.quad(1.05, 0.06, 0.05, 0.5, -0.8, 0.07, 20);
    const tail = [[-1.28, 0.42], [-1.08, 0.02], [-1.28, -0.4]];
    const body = top.concat(bot, tail).map(tf);
    const head = top.filter((p) => p[0] > 0.5).concat(bot.filter((p) => p[0] > 0.5)).map(tf);
    block("red", body, at, { w: 0.42 * U, seed: 90, knock: true });
    cut(["red"], (g) => B.poly(g, head, true), at + DELAY.red * SPD);
    block("moss", head, at, { line: false });
    block("red", [[-0.2, -0.36], [0.18, -0.62], [0.32, -0.4]].map(tf), at, { w: 0.3 * U, seed: 91 }); // dorsal fin
    ink("key", at, (g) => {
      carve(g, B.quad(0.5, -0.36, 0.38, 0.0, 0.52, 0.32, 10).map(tf), 0.3 * U, 92, false); // gill
      g.fillStyle = PAL.key;
      g.beginPath();
      const e = tf([0.8, -0.1]);
      B.circle(g, e[0], e[1], 0.06 * s);
      g.fill();
      if (s < 4 * U) return;
      for (let i = 0; i < 5; i++) // scales: rows of small carved arcs
        for (let j = -1; j <= 1; j++) {
          const sx = -0.55 + i * 0.2 + (j & 1) * 0.1, sy = j * 0.14;
          carve(g, B.arcPts(sx, sy, 0.09, -1.1, 1.1, 6).map(tf), 0.12 * U, 100 + i * 3 + j, false);
        }
    });
  }
  /** A river along a centreline, widening downstream, with fine carved flow strokes. */
  function river(center, w0, w1, at, step) {
    const c = B.densify(center, 1.5 * U), L = [], R = [];
    c.forEach((q, i) => {
      const a = c[Math.max(0, i - 1)], b = c[Math.min(c.length - 1, i + 1)], l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const nx = -(b[1] - a[1]) / l, ny = (b[0] - a[0]) / l, hw = B.lerp(w0, w1, i / (c.length - 1)) / 2;
      L.push([q[0] + nx * hw, q[1] + ny * hw, nx, ny, hw]);
      R.push([q[0] - nx * hw, q[1] - ny * hw]);
    });
    const poly = L.map((p) => [p[0], p[1]]).concat(R.slice().reverse());
    cut(["moss", "ochre"], (g) => B.poly(g, poly, true), at);
    block("blue", poly, at, { line: false });
    ink("key", at, (g) => {
      carve(g, L.map((p) => [p[0], p[1]]), 0.4 * U, 31, false);
      carve(g, R, 0.4 * U, 32, false);
      for (let k = -1; k <= 1; k++) { // flow strokes: short parallel cuts, re-printed shifted each beat
        const pts = L.map((p) => [p[0] - p[2] * p[4] * (1 - k * 0.5), p[1] - p[3] * p[4] * (1 - k * 0.5)]);
        const n = 7, off = ((step * 0.29 + k * 0.33) % 1) / n;
        for (let i = 0; i < n; i++) {
          const a = i / n + off;
          if (a + 0.06 < 1) carve(g, B.trim(pts, a, a + 0.055), 0.16 * U, 40 + i + k * 9, false);
        }
      }
    });
    return poly;
  }
  function land(top, bottom, at) {
    block("moss", rect(-2 * U, top, F.W + 4 * U, bottom - top), at, { line: false, alpha: 0.85 });
    ink("key", at, (g) => carve(g, [[-2 * U, top], [F.W + 2 * U, top]], 0.4 * U, 33, false));
  }
  function sun(cx, cy, r, at, plate = "red") {
    block(plate, B.arcPts(cx, cy, r, 0, B.TAU, 56).slice(0, -1), at, { w: 0.36 * U, seed: 50, knock: true });
  }

  // --- the prints (positions per aspect)
  const step = (t, per = 0.8) => Math.floor(t / per + 1e-6);

  function printTitle(at) {
    const W = F.W, H = F.H, S = F.safe, hy = H * PL(0.66, 0.6), st = step(T);
    sky(0, hy, at);
    cloudBand(PL(-4 * U, -6 * U), H * PL(0.15, 0.11), W * PL(0.5, 0.42), PL(8, 10) * U, at + 0.1, st);
    sun(W * PL(0.2, 0.22), H * PL(0.36, 0.31), PL(10, 11) * U, at);
    mountain(W * PL(0.43, 0.42), hy, PL(32, 26) * U, PL(38, 34) * U, at);
    cloudBand(W * PL(0.08, 0.06), hy - PL(12, 11) * U, W * PL(0.5, 0.42), PL(8, 9) * U, at + 0.2, st + 1);
    sea(hy, H + 2 * U, at, st, { rows: PL(4, 5) });
    salmon(W * PL(0.36, 0.5), hy + PL(9, 12) * U, PL(9, 11) * U, -0.42, at + 0.5);
    const c = cartouche(W * PL(0.78, 0.79), S.y + PL(2, 1) * U, ["How", "salmon", "find", "home"], at + 0.2, { size: PL(6.6, 7) * U, align: "center", tint: "sky", tintAlpha: 0.6 });
    seal(c.x - PL(4.5, 4) * U, c.y + c.h - 4 * U, 6.5 * U, at + 1.45);
    cartouche(c.x + c.w / 2, c.y + c.h + 2 * U, ["the salmon run"], at + 1.2, { size: PL(4.4, 4.2) * U, align: "center" });
  }

  function printDiagram(at) {
    const W = F.W, H = F.H, S = F.safe, hy = H * PL(0.3, 0.31), seaTop = H * PL(0.71, 0.72), st = step(T);
    sky(0, hy, at);
    mountain(W * PL(0.28, 0.32), hy, PL(18, 13) * U, PL(26, 22) * U, at);
    land(hy, seaTop, at);
    const src = [W * PL(0.3, 0.14), hy + 1 * U];
    const mouth = [W * PL(0.52, 0.86), seaTop + 1 * U];
    const centre = B.cubic(src[0], src[1], W * PL(0.75, 0.14), H * PL(0.42, 0.7), W * PL(0.12, 0.55), H * PL(0.6, 0.5), mouth[0], mouth[1], 48);
    river(centre, PL(2.5, 2.2) * U, PL(11, 10) * U, at, st);
    sea(seaTop, H + 2 * U, at, st, { rows: 3, pw: 11 });
    const fq = B.pointAt(centre, 0.45); // the salmon swims up the middle of the river
    salmon(fq[0], fq[1], PL(3.4, 3.2) * U, fq[2] + Math.PI, at + 0.45);
    cartouche(src[0] + PL(-4, 5) * U, hy + PL(3, 2) * U, ["Home", "stream"], at + 0.9, { size: PL(4.4, 4.2) * U, align: PL("right", "left") });
    cartouche(PL(S.x + U, W * 0.3), seaTop + PL(1.5, 3) * U, ["The", "ocean"], at + 1.1, { size: PL(4.4, 4.2) * U });
    // the arrow runs upstream alongside the river
    const up = B.trim(centre, PL(0.3, 0.45), PL(0.72, 0.9)).reverse(), am = B.pointAt(beside(up, PL(-21, 19) * U), 0.55);
    carvedArrow(beside(up, PL(-9, 7) * U), at + 1.35, PL(3.2, 3) * U);
    cartouche(am[0], am[1] - PL(6, 5) * U, ["Up", "river"], at + 1.6, { size: PL(4.4, 4.2) * U, align: "center" });
  }

  function printNumber(at) {
    const W = F.W, H = F.H, S = F.safe, st = step(T, 0.6);
    const fx = W * PL(0.5, 0.75), cliffB = H * PL(0.42, 0.62);
    sky(0, H * PL(0.2, 0.3), at);
    // cliffs, the falls left as paper with cut strokes, the pool below
    block("moss", [[-2 * U, H * PL(0.16, 0.22)], [fx - 14 * U, H * PL(0.2, 0.26)], [fx - 11 * U, cliffB], [-2 * U, cliffB]], at, { seed: 3 });
    block("moss", [[fx + 13 * U, H * PL(0.18, 0.24)], [W + 2 * U, H * PL(0.15, 0.2)], [W + 2 * U, cliffB], [fx + 11 * U, cliffB]], at, { seed: 4 });
    bokashi("indigo", rect(-2 * U, H * 0.15, W + 4 * U, cliffB - H * 0.15), at, 0, cliffB, 0, H * 0.18, 0.55);
    cut(["indigo"], (g) => g.rect(fx - 12 * U, H * PL(0.19, 0.25), 24 * U, cliffB), at + DELAY.indigo);
    ink("key", at, (g) => {
      for (let i = 0; i < 9; i++) {
        const x = fx - 11 * U + i * 2.7 * U, y0 = H * PL(0.19, 0.25) + ((st + i) % 3) * 1.5 * U;
        carve(g, [[x, y0], [x + 0.3 * U, cliffB - 2 * U]], 0.18 * U, 120 + i, false);
      }
    });
    sea(cliffB, H + 2 * U, at, st, { rows: 4, pw: 10 });
    // the salmon leaps: re-printed higher on each slow beat
    const lp = Math.min(3, Math.floor((T - at - 0.6) / 0.45));
    if (lp >= 0) {
      const pos = [[0.15, 1.0], [0.05, 0.75], [-0.02, 0.5], [0.0, 0.3]][lp];
      salmon(fx + pos[0] * 60 * U, cliffB - (1 - pos[1]) * PL(28, 26) * U + 4 * U, PL(6, 5.5) * U, -1.1 - lp * 0.12, at + 0.6 + lp * 0.45 - DELAY.red);
    }
    // the number, in a pale paper panel, with a vermilion seal beside it
    const pw = PL(76, 54) * U, ph = PL(36, 34) * U, px = PL(W / 2, W * 0.3) - pw / 2, py = PL(H * 0.5, H * 0.57) - ph / 2;
    cut(ORDER.concat("key"), (g) => g.rect(px, py, pw, ph), at + 0.7);
    block("sky", rect(px, py, pw, ph), at + 0.7, { alpha: 0.35, w: 0.32 * U, seed: 140 });
    ink("key", at + 0.7, (g) => carve(g, rect(px + 1.2 * U, py + 1.2 * U, pw - 2.4 * U, ph - 2.4 * U), 0.18 * U, 141, true));
    const n = Math.min(4, Math.max(0, Math.floor((T - at - 0.95) / 0.32) + 1)), val = [0, 800, 1600, 2400, 3000][n];
    if (n > 0) ink("key", T - 0.3, (g) => B.text(g, val.toLocaleString("en-US"), px + pw * 0.44, py + ph * 0.43, { size: PL(17, 15) * U, family: SERIF, weight: 800, color: PAL.key, maxW: pw * 0.75 }));
    ink("key", at + 0.9, (g) => B.text(g, "kilometres upriver", px + pw * 0.44, py + ph * 0.79, { size: PL(4.2, 3.9) * U, family: BRUSHF, color: PAL.key, maxW: pw * 0.8 }));
    seal(px + pw * 0.88, py + ph * 0.36, PL(8.5, 7.5) * U, at + 2.3);
    cartouche(PL(W / 2, W * 0.3), py + ph + 3 * U, ["some salmon swim", "this far to spawn"], at + 1.25, { size: PL(4.4, 4.2) * U, align: "center", tint: "sky", tintAlpha: 0.5 });
  }

  function printJourney(at) {
    const W = F.W, H = F.H, S = F.safe, hy = H * PL(0.19, 0.18), seaTop = H * PL(0.7, 0.74), st = step(T);
    sky(0, hy, at);
    mountain(W * PL(0.22, 0.18), hy, PL(10, 9) * U, PL(18, 16) * U, at);
    land(hy, seaTop, at);
    const src = [W * PL(0.3, 0.13), hy + 0.5 * U], mouth = [W * PL(0.6, 0.62), seaTop + 0.5 * U];
    const centre = B.cubic(src[0], src[1], W * PL(0.95, 0.12), H * PL(0.32, 0.7), W * PL(0.0, 0.45), H * PL(0.5, 0.6), mouth[0], mouth[1], 60);
    river(centre, 2.2 * U, PL(10, 9) * U, at, st);
    sea(seaTop, H + 2 * U, at, st, { rows: 3, pw: 12 });
    // the stops: cartouches clear of the river
    const b0 = BEATS[3], b1 = BEATS[4], cs = PL(4.4, 4.2) * U;
    cartouche(PL(S.x + 2 * U, W * 0.2), PL(hy + 8 * U, hy + 3 * U), ["Hatch in", "gravel"], b0 + 0.25, { size: cs, num: 1, tintAlpha: 0.35 });
    cartouche(PL(S.x + 2 * U, W * 0.7), PL(seaTop - 4 * U, seaTop - 30 * U), ["Grow at", "sea"], b0 + 1.25, { size: cs, num: 2, tintAlpha: 0.35 });
    const c3 = cartouche(W * PL(0.66, 0.36), H * PL(0.42, 0.22), ["Smell", "the way", "home"], b1 + 0.15, { size: cs, num: 3, tint: "sky", tintAlpha: 0.7 });
    ink("ochre", b0 + 0.25, (g) => {
      const q = B.pointAt(centre, 0.03), r = B.rng(5);
      g.fillStyle = PAL.ochre;
      for (let i = 0; i < 14; i++) {
        g.beginPath();
        B.circle(g, q[0] + r.range(-4, 4) * U, q[1] + r.range(1, 4) * U, r.range(0.4, 0.7) * U);
        g.fill();
      }
    });
    // the fish: re-printed whole at each stop
    const at2s = [b0 + 0.35, b0 + 1.25, b1 + 0.15, b1 + 0.6], where = at2s.filter((a, i) => !i || T >= a).length - 1, at2 = at2s[where];
    const fp = [0.08, 0.96, 0.52, 0.12][where], fq = B.pointAt(centre, fp), size = [2.2, 4.4, 3.6, 3.6][where];
    const ang = where === 1 ? 0 : fq[2] + Math.PI;
    SPD = 0.25;
    salmon(fq[0], fq[1] - (where === 1 ? 3 * U : 0), size * U, ang, at2);
    SPD = 1;
    if (T > b1 + 0.05) carvedArrow(beside(B.trim(centre, 0.55, 0.85).reverse(), PL(-8, 7.5) * U), b1 + 0.05, 2.6 * U);
    seal(c3.x + c3.w + PL(-1, 5) * U, c3.y + c3.h + PL(5, 1) * U, 6 * U, b1 + 1.0, null); // emphasis: the seal pressed beside it
  }

  function printClose(at) {
    const W = F.W, H = F.H, S = F.safe, hy = H * PL(0.64, 0.66), st = step(T);
    sky(0, hy, at);
    sun(W * PL(0.42, 0.36), H * PL(0.52, 0.42), PL(24, 22) * U, at, "ochre"); // gold, so the red fish reads on it
    cloudBand(W * PL(0.05, 0.06), H * PL(0.25, 0.2), W * PL(0.5, 0.34), PL(8, 9) * U, at + 0.1, st);
    cloudBand(W * PL(0.42, 0.04), hy - PL(12, 11) * U, W * PL(0.6, 0.3), PL(8, 9) * U, at + 0.2, st + 2);
    sea(hy, H + 2 * U, at, st, { rows: 4 });
    salmon(W * PL(0.42, 0.36), H * PL(0.56, 0.43), 13 * U, -0.35, at + 0.35);
    const c = cartouche(W * PL(0.78, 0.75), S.y + PL(1, 3) * U, ["Home,", "by", "scent"], at + 0.6, { size: PL(6.4, 6.8) * U, align: "center", tint: "sky", tintAlpha: 0.6 });
    seal(c.x - 4 * U, c.y + c.h - 4 * U, PL(6.5, 6) * U, at + 1.35);
    cartouche(PL(c.x + c.w, c.x + c.w / 2), c.y + c.h + 2 * U, PL(["they return", "where they", "hatched"], ["they return", "where they hatched"]), at + 1.0, { size: PL(4.4, 4.2) * U, align: PL("right", "center") }); // under the title
  }
  const PRINT_FNS = [printTitle, printDiagram, printNumber, printJourney, printClose];

  // --- pressing a whole print onto a context
  function renderPrint(ctx, W, H, i) {
    ["key"].concat(ORDER).forEach((p) => (G[p] = B.scratch("wb-plate-" + p, W, H)));
    PRINT_FNS[i](PRINTS[i].at);
    ctx.drawImage(sheet(W, H), 0, 0);
    ctx.save();
    ctx.beginPath();
    ctx.rect(1.2 * U, 1.2 * U, W - 2.4 * U, H - 2.4 * U); // ink stays on the sheet
    ctx.clip();
    ctx.globalCompositeOperation = "multiply";
    ORDER.concat(["key"]).forEach((p, k) => {
      pressTexture(G[p], W, H, k + i * 3, p === "key");
      ctx.drawImage(G[p].canvas, REG[p][0] * U, REG[p][1] * U);
    });
    ctx.restore();
  }
  /** Clip a polygon by the half-plane n.(X - C) <= d. */
  function halfPlane(poly, C, n, d, keepBelow) {
    const f = (p) => (n[0] * (p[0] - C[0]) + n[1] * (p[1] - C[1]) - d) * (keepBelow ? 1 : -1);
    const out = [];
    poly.forEach((p, i) => {
      const q = poly[(i + 1) % poly.length], fp = f(p), fq = f(q);
      if (fp <= 0) out.push(p);
      if (fp * fq < 0) out.push([p[0] + ((q[0] - p[0]) * fp) / (fp - fq), p[1] + ((q[1] - p[1]) * fp) / (fp - fq)]);
    });
    return out;
  }
  /** The old sheet peels off from the top-right corner; the flap shows the paper's back. */
  function peel(ctx, W, H, oldCanvas, p) {
    const C = [W, 0], D = [-W, H], len = Math.hypot(W, H), n = [D[0] / len, D[1] / len], d = p * len * 1.02;
    const frame = [[0, 0], [W, 0], [W, H], [0, H]];
    const stay = halfPlane(frame, C, n, d, false), flap = halfPlane(frame, C, n, d, true);
    if (stay.length > 2) {
      ctx.save();
      ctx.beginPath();
      B.poly(ctx, stay, true);
      ctx.clip();
      ctx.drawImage(oldCanvas, 0, 0);
      ctx.restore();
    }
    if (flap.length > 2) {
      const refl = flap.map(([x, y]) => {
        const s = n[0] * (x - C[0]) + n[1] * (y - C[1]) - d;
        return [x - 2 * s * n[0], y - 2 * s * n[1]];
      });
      B.withShadow(ctx, { color: "rgba(40,25,10,0.35)", blur: 3 * U, x: -1 * U, y: 1.2 * U }, () => {
        ctx.beginPath();
        B.poly(ctx, refl, true);
        ctx.fillStyle = B.shade(PAL.paper, -0.04);
        ctx.fill();
        const fx = C[0] + n[0] * d, fy = C[1] + n[1] * d; // the back of the sheet: lit at the fold, shadowed at the tip
        ctx.shadowColor = "rgba(0,0,0,0)";
        ctx.fillStyle = B.linear(ctx, fx, fy, fx - n[0] * d, fy - n[1] * d, [[0, "rgba(255,250,235,0.35)"], [1, "rgba(120,90,50,0.18)"]]);
        ctx.fill();
      });
      ctx.save();
      ctx.beginPath();
      B.poly(ctx, refl, true);
      ctx.clip();
      // the sheet's back: the print shows through, mirrored
      const k = 2 * (n[0] * C[0] + n[1] * C[1] + d);
      ctx.globalAlpha = 0.2;
      ctx.globalCompositeOperation = "multiply";
      ctx.setTransform(1 - 2 * n[0] * n[0], -2 * n[0] * n[1], -2 * n[0] * n[1], 1 - 2 * n[1] * n[1], k * n[0], k * n[1]);
      ctx.drawImage(oldCanvas, 0, 0);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.5;
      ctx.drawImage(fibres(W, H), 0, 0);
      ctx.restore();
    }
  }

  function printIndex(t) {
    let i = 0;
    PRINTS.forEach((p, k) => (t >= p.from ? (i = k) : 0));
    return i;
  }

  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    const i = printIndex(t), nxt = PRINTS[i + 1], peelP = nxt ? B.span(t, nxt.from - PEEL, nxt.from, "inOutSine") : 0;
    if (peelP > 0) {
      T = t;
      renderPrint(ctx, W, H, i + 1); // the next print, being pressed underneath
      const old = B.scratch("wb-old", W, H);
      T = Math.min(t, nxt.from - PEEL);
      renderPrint(old, W, H, i);
      peel(ctx, W, H, old.canvas, peelP);
    } else {
      T = t;
      renderPrint(ctx, W, H, i);
    }
    // finishing: fibres, yellowed edges
    ctx.save();
    ctx.globalAlpha = 0.28;
    ctx.drawImage(fibres(W, H), 0, 0);
    ctx.restore();
    B.vignette(ctx, W, H, { color: "#a9813f", amount: 0.22, inner: 0.5, mode: "multiply" });
    B.mottle(ctx, W, H, { amount: 0.06, feature: 0.3, seed: 35, mode: "multiply" });
  }

  // --- sound: block thumps, paper rubs, koto for seals, bamboo knocks
  SOUND.define("woodblock-press", (v) => {
    v.tone({ f: 150, f2: 70, glide: 0.08, a: 0.002, len: 0.14, peak: 0.42 });
    v.noise({ filter: "lowpass", f: 700, a: 0.002, len: 0.08, peak: 0.22, brown: true });
  }, { verb: 0.12 });
  SOUND.define("woodblock-bamboo", (v) => {
    v.tone({ f: 620, a: 0.001, len: 0.16, peak: 0.28 });
    v.tone({ f: 1240 * 1.02, a: 0.001, len: 0.06, peak: 0.08 });
    v.noise({ filter: "bandpass", f: 1500, q: 3, a: 0.0005, len: 0.03, peak: 0.25 });
  }, { verb: 0.3 });
  SOUND.define("woodblock-koto", (v, o) => {
    // one plucked string: bright attack, sharp partials, long decay
    const f = v.hz(o.note || "D5");
    v.tone({ type: "triangle", f, a: 0.002, len: 1.6, peak: 0.22 });
    v.tone({ f: f * 2.01, a: 0.001, len: 0.5, peak: 0.08 });
    v.tone({ f: f * 3.02, a: 0.001, len: 0.15, peak: 0.04 });
    v.noise({ filter: "highpass", f: 3000, a: 0.0005, len: 0.02, peak: 0.1 });
  }, { verb: 0.45 });

  function score(k) {
    const WP = "woodblock-press", KO = "woodblock-koto";
    const miyako = ["D4", "Eb4", "G4", "A4", "Bb4", "D5", "Eb5", "G5"];
    k.bed("wind", 0, DUR, { gain: 0.35 });
    k.bed("room", 0, DUR, { gain: 0.5 });
    PRINTS.forEach((p, i) => {
      ["key"].concat(ORDER).forEach((pl, j) => k.at(p.at + DELAY[pl] + 0.02, WP, { gain: j ? 0.55 : 0.8, pitch: -j * 0.7 }));
      if (i) {
        k.at(p.from - PEEL, "paper", { dur: PEEL, gain: 0.8 });
        k.at(p.from - PEEL * 0.5, "rustle", { dur: 0.3, gain: 0.5 });
        k.at(p.from + 0.05, "woodblock-bamboo", { gain: 0.8 });
      }
    });
    k.at(0.3, WP, { gain: 0.5 }).at(1.5, KO, { note: miyako[5] });
    k.at(1.3, WP, { gain: 0.4, pitch: 2 });
    [2.9, 3.1, 3.35, 3.6].forEach((at, i) => k.at(at, WP, { gain: 0.5, pitch: i }));
    k.at(3.4, KO, { note: miyako[2], gain: 0.6 });
    // the count: four re-prints, then the seal
    [5.35, 5.67, 5.99, 6.31].forEach((at, i) => k.at(at, WP, { gain: 0.6 + i * 0.1 }).at(at, "knock", { gain: 0.25, pitch: i * 2 }));
    k.at(6.7, KO, { note: miyako[6] }).at(6.75, KO, { note: miyako[3], gain: 0.6 });
    // stops, fish, seal
    [7.25, 8.25, 9.55].forEach((at, i) => k.at(at, WP, { gain: 0.7 }).at(at + 0.25, KO, { note: miyako[2 + i * 2], gain: 0.55 }));
    k.at(9.85, WP, { gain: 0.6 }).at(10.4, KO, { note: miyako[7] });
    k.at(11.6, WP, { gain: 0.5 }).at(12.05, KO, { note: miyako[5] }).at(12.1, KO, { note: miyako[0], gain: 0.6 });
  }

  Player.register({
    id: "woodblock",
    name: "Woodblock Print",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;800&family=Yuji+Syuku&display=swap",
      faces: ['800 20px "Shippori Mincho"', '600 20px "Shippori Mincho"', '400 20px "Yuji Syuku"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three stops", "Home by smell", "Close"],
    stills: [1.45, 3.9, 6.25, 8.9, 10.45, 12.6],
    draw,
    score,
  });
})();
