/* 15 Pixel Arcade. Topic (replace it): how a rocket reaches orbit.
 * Rendering (keep it): a console scene on a tiny buffer (short side 180 px) blown up with smoothing off; a locked
 * palette in ramps; Bayer-dither seams for every blend; parallax ridges; 1-px-outlined sprites lit from the left;
 * blue menu windows; 1-bit pixel text with a drop shadow. Finish: palette lock, stepped fades, hard upscale.
 * Motion: a 10 Hz game tick, windows snap open then type out, console transitions (mosaic, ripple, iris). */
(function () {
  "use strict";
  const B = window.Brush;

  // --- palette and type (from the card)
  const C = {
    out: "#0b0719",
    k0: "#140c30", k1: "#1b1240", k2: "#2c1a5c", k3: "#5f2d7a", k4: "#8a3a80", k5: "#b84a78", k6: "#e06070", k7: "#ff8a6a", k8: "#ffab6a", k9: "#ffd479", k10: "#fff0b8",
    w0: "#0e1450", w1: "#1a2580", w2: "#253aa0", w3: "#3550c0", w4: "#5a78e0", w5: "#9ab0ff",
    m0: "#3a3a5c", m1: "#6c6c94", m2: "#b8b8d8", m3: "#f6f6ff",
    r0: "#5a1028", r1: "#a02838", r2: "#e06070",
    l0: "#0f1f2a", l1: "#173a3a", l2: "#235a45", l3: "#3a7a50", l4: "#5aa060",
    s0: "#10306a", s1: "#1e5aa0", s2: "#3a8ad0", s3: "#7ac0f0",
  };
  const LOCK = [...new Set(Object.values(C))].map((h) => B.rgb(h)); const HEAD = "Jersey 10", BODY = "Pixelify Sans";
  const DUR = 12; const BEATS = [0, 2.0, 4.2, 6.4, 8.4, 10.3];
  const TICK = 10; // game logic steps per second
  const T_IGNITE = 4.6, T_LIFT = 4.8, T_SEP = 5.4;
  const SHORT_SIDE = 180; // buffer px across the short side

  let g = null, BW = 0, BH = 0, S = null, P = false;

  // --- pixel helpers (reuse these)
  const tk = (t) => Math.floor(t * TICK + 1e-6) / TICK; const tickN = (t) => Math.floor(t * TICK + 1e-6); const R = Math.round;
  // 4x4 Bayer dither: the only way colours blend
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  const bay = (x, y) => (BAYER[(y & 3) * 4 + (x & 3)] + 0.5) / 16;
  function px(x, y, w, h, c) { g.fillStyle = c; g.fillRect(R(x), R(y), R(w), R(h)); }
  const put = (d, o, c) => { d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2]; d[o + 3] = 255; };
  /** 4x4 tile: `color` where Bayer < a (dithered transparency). */
  function ditherTile(color, a) {
    const lv = R(B.clamp(a) * 16);
    return B.layer(`arc-dith:${color}:${lv}`, 4, 4, (q) => {
      q.fillStyle = color;
      for (let i = 0; i < 16; i++) if (BAYER[i] < lv) q.fillRect(i % 4, (i / 4) | 0, 1, 1);
    });
  }
  function ditherRect(x, y, w, h, color, a) {
    if (a <= 0.03 || w <= 0 || h <= 0) return;
    if (a >= 0.97) return px(x, y, w, h, color);
    g.fillStyle = g.createPattern(ditherTile(color, a), "repeat"); g.fillRect(R(x), R(y), R(w), R(h));
  }
  function disc(cx, cy, r, color, a = 1) {
    cx = R(cx); cy = R(cy);
    for (let dy = -r; dy <= r; dy++) {
      const hw = Math.floor(Math.sqrt(Math.max(0, r * r - dy * dy)) + 0.35);
      ditherRect(cx - hw, cy + dy, hw * 2 + 1, 1, color, a);
    }
  }
  /** Draw fn through a dither mask (pixel-art fade). */
  function ditherFade(a, fn) {
    if (a <= 0.03) return;
    if (a >= 0.97) return fn();
    const keep = g, q = B.scratch("arc-fade", BW, BH); g = q; fn(); g = keep; q.globalCompositeOperation = "destination-in";
    q.fillStyle = q.createPattern(ditherTile("#ffffff", a), "repeat"); q.fillRect(0, 0, BW, BH); g.drawImage(q.canvas, 0, 0);
  }

  // --- pixel text: the web fonts rasterised 1-bit
  const FONT = { head: { fam: HEAD, size: 18, lh: 15 }, body: { fam: BODY, size: 11, lh: 12 }, big: { fam: HEAD, size: 36, lh: 27 } };
  const fontStr = (kind) => B.font(FONT[kind].size, FONT[kind].fam, 400);
  function measure(str, kind) {
    const m = B.scratch("arc-measure", 4, 4); m.font = fontStr(kind);
    return Math.ceil(m.measureText(str).width);
  }
  /** Text as a 1-bit glyph image in one palette colour. */
  function glyphs(str, kind, color) {
    const f = FONT[kind], w = measure(str, kind) + 2, h = Math.ceil(f.size * 1.25) + 2, base = Math.round(f.size * 0.72);
    return B.layer(`arc-txt:${kind}:${color}:${str}`, w, h, (q, cw, ch) => {
      q.font = fontStr(kind); q.fillStyle = "#ffffff";
      if (kind === "body") { q.textBaseline = "top"; q.fillText(str, 1, 1); } else q.fillText(str, 1, base);
      const img = q.getImageData(0, 0, cw, ch), d = img.data, c = B.rgb(color);
      // headings: 2x, reduced 3-of-4 (keeps S, G, I distinct)
      let s2 = null;
      if (kind === "head") { const z = B.scratch("arc-ss", cw * 2, ch * 2); z.font = B.font(f.size * 2, f.fam, 400); z.fillStyle = "#fff"; z.fillText(str, 2, base * 2); s2 = z.getImageData(0, 0, cw * 2, ch * 2).data; }
      for (let i = 0; i < d.length; i += 4) {
        const p = i / 4, x = p % cw, y = (p / cw) | 0, a = (u, v) => (s2[((y * 2 + v) * cw * 2 + x * 2 + u) * 4 + 3] >= 160 ? 1 : 0);
        const on = s2 ? a(0, 0) + a(1, 0) + a(0, 1) + a(1, 1) >= 3 : d[i + 3] >= (kind === "body" ? 110 : 190);
        put(d, i, c); d[i + 3] = on ? 255 : 0;
      }
      q.putImageData(img, 0, 0);
    });
  }
  /** Pixel text with a dark drop shadow (o.outline: full outline). */
  function ptext(str, x, y, kind, color, o = {}) {
    if (!str) return 0;
    const c = glyphs(str, kind, color), w = c.width - 2;
    const xx = R(o.align === "center" ? x - w / 2 : o.align === "right" ? x - w : x) - 1, yy = R(y) - 1;
    const dark = glyphs(str, kind, C.out);
    if (o.outline) {
      for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1], [1, 2], [0, 2], [2, 2], [2, 1]]) g.drawImage(dark, xx + dx, yy + dy);
    } else if (o.shadow !== false) g.drawImage(dark, xx + 1, yy + 1);
    g.drawImage(c, xx, yy);
    return w;
  }
  function wrapLines(str, kind, maxW) {
    const out = []; let line = "";
    for (const word of String(str).split(/\s+/)) {
      const test = line ? line + " " + word : word;
      if (!line || measure(test, kind) <= maxW) line = test;
      else { out.push(line); line = word; }
    }
    if (line) out.push(line);
    return out;
  }

  function winFill(w, h) {
    return B.layer("arc-winfill", w, h, (q, cw, ch) => {
      const ramp = [C.w3, C.w2, C.w1, C.w0].map((x) => B.rgb(x)), img = q.createImageData(cw, ch), d = img.data;
      for (let y = 0; y < ch; y++) {
        const f = (y / Math.max(1, ch - 1)) * (ramp.length - 1), i = Math.min(ramp.length - 2, Math.floor(f)), k = f - i;
        for (let x = 0; x < cw; x++) put(d, (y * cw + x) * 4, bay(x, y) < B.smooth(0.55, 1, k) ? ramp[i + 1] : ramp[i]);
      }
      q.putImageData(img, 0, 0);
    });
  }
  const snap = (p) => (p <= 0 ? 0 : Math.min(1, Math.ceil(p * 4 - 1e-6) / 4));
  /** Console window: dark edge, white border, grey line, dithered fill. */
  function windowBox(x, y, w, h, open = 1) {
    const s = snap(open);
    if (s <= 0) return false;
    const ww = Math.max(8, R(w * s)), hh = Math.max(8, R(h * (s < 1 ? s * 0.8 + 0.2 : 1)));
    const X = R(x + (w - ww) / 2), Y = R(y + (h - hh) / 2); px(X + 1, Y, ww - 2, hh, C.out);
    px(X, Y + 1, ww, hh - 2, C.out); px(X + 2, Y + 1, ww - 4, hh - 2, C.m3); px(X + 1, Y + 2, ww - 2, hh - 4, C.m3);
    px(X + 2, Y + 2, ww - 4, hh - 4, C.m1); g.drawImage(winFill(ww - 6, hh - 6), X + 3, Y + 3);
    return s >= 1;
  }
  function nextArrow(x, y, t) {
    const b = tickN(t) % 4 < 2 ? 0 : 1;
    for (const o of [1, 0]) for (let i = 0; i < 3; i++) px(x - 2 + i + o, y + b + i + o, 5 - 2 * i, 1, o ? C.out : C.k9);
  }
  function cursor(x, y) {
    for (const o of [1, 0]) for (let i = -3; i <= 3; i++) px(x + o, y + i + o, 4 - Math.abs(i), 1, o ? C.out : C.m3);
  }
  function winHeight(w, head, body, o = {}) {
    const lines = body ? wrapLines(body, "body", w - 10) : [];
    return 5 + (head ? FONT[o.headKind || "head"].lh + 1 : 0) + lines.length * FONT.body.lh + 4;
  }
  /** Gold header, white body typed from `typeAt` (null: all). */
  function textWindow(x, y, w, head, body, t, open, typeAt, o = {}) {
    const hk = o.headKind || "head", lines = body ? wrapLines(body, "body", w - 10) : []; const h = winHeight(w, head, body, o);
    if (!windowBox(x, y, w, h, open)) return h;
    let yy = y + 5;
    if (head) {
      if (o.headCenter) ptext(head, x + w / 2, yy, hk, C.k9, { align: "center", outline: true });
      else ptext(head, x + 5, yy, hk, C.k9);
      yy += FONT[hk].lh + 1;
    }
    const total = lines.join("").length;
    let budget = typeAt == null ? total : Math.floor(Math.max(0, tk(t) - typeAt) * (o.cps || 48));
    for (const ln of lines) {
      if (budget <= 0) break;
      ptext(ln.slice(0, budget), x + 5, yy, "body", C.m3); budget -= ln.length; yy += FONT.body.lh;
    }
    if (budget > 0 && o.next !== false && body) nextArrow(x + w - 8, y + h - 8, t);
    return h;
  }
  /** The arcade arrow: marching dots with a chevron head. */
  function dotArrow(pts, p, t, color, o = {}) {
    if (p <= 0) return;
    const L = B.pathLength(pts), step = o.step ?? 3, n = Math.floor(L / step), shown = Math.floor(n * B.clamp(p));
    const phase = tickN(t) % 3;
    for (let i = 0; i <= shown; i++) {
      const q = B.pointAt(pts, Math.min(1, (i * step) / L)), big = (i + 3 - phase) % 3 === 0;
      if (big) px(q[0] - 1, q[1] - 1, 3, 3, C.out);
      px(q[0], q[1], big ? 2 : 1, big ? 2 : 1, color);
    }
    if (p >= 1 && o.head !== false) {
      const q = B.pointAt(pts, 1), ca = Math.cos(q[2]), sa = Math.sin(q[2]);
      for (const [e, c] of [[1, C.out], [0, color]])
        for (let k = 0; k < 5; k++) for (const s of [-1, 1]) px(q[0] - ca * k - sa * k * s - e, q[1] - sa * k + ca * k * s - e, 1 + 2 * e, 1 + 2 * e, c);
    }
  }

  /** Rocket pixel by pixel, lit from the left, 1-px outline; split at the stage seam. */
  const ROCK = { hw: 5, rows: 52, seam: 31 };
  function rocketSprites() {
    const cw = (ROCK.hw + 5) * 2 + 1, chh = ROCK.rows + 2, cx = ROCK.hw + 5;
    const grid = Array.from({ length: chh }, () => new Array(cw).fill(null));
    for (let r = 0; r < ROCK.rows; r++) {
      let hw = r < 11 ? Math.ceil(r / 2) : ROCK.hw; let ramp = [C.m3, C.m3, C.m2, C.m1, C.m0];
      if (r < 11 || r === 17 || r === 18 || r === 27) ramp = [C.r2, C.r2, C.r1, C.r0, C.r0];
      if (r >= 49) { hw = r === 49 ? 3 : 4; ramp = [C.m2, C.m1, C.m1, C.m0, C.m0]; }
      for (let dx = -hw; dx <= hw; dx++) {
        const n = (dx + hw) / Math.max(1, 2 * hw); let col = ramp[Math.min(ramp.length - 1, Math.floor(n * ramp.length))];
        if (r === ROCK.seam) col = C.m0;
        if (r >= 13 && r <= 15 && dx >= -2 && dx <= 0) col = r === 13 && dx === -2 ? C.w5 : C.w3; // porthole
        grid[r + 1][cx + dx] = col;
      }
      if (r >= 40 && r <= 48) {
        const ext = Math.min(3, ((r - 40) >> 1) + 1);
        for (let e = 1; e <= ext; e++) { grid[r + 1][cx - hw - e] = C.r2; grid[r + 1][cx + hw + e] = C.r1; }
      }
    }
    const filled = (y, x) => y >= 0 && y < chh && x >= 0 && x < cw && grid[y][x] && grid[y][x] !== C.out;
    for (let y = 0; y < chh; y++)
      for (let x = 0; x < cw; x++) if (!grid[y][x] && (filled(y - 1, x) || filled(y + 1, x) || filled(y, x - 1) || filled(y, x + 1))) grid[y][x] = C.out;
    const part = (key, y0, y1) => B.layer(key, cw, chh, (q) => {
      for (let y = y0; y < y1; y++) for (let x = 0; x < cw; x++) if (grid[y][x]) { q.fillStyle = grid[y][x]; q.fillRect(x, y, 1, 1); }
    });
    return { upper: part("arc-rk-up", 0, ROCK.seam + 1), booster: part("arc-rk-bo", ROCK.seam + 1, chh), cx, h: chh };
  }
  /** Nozzle at (x, by). o: { booster (false: upper stage), flame 0..1, t } */
  function rocket(x, by, o = {}) {
    const sp = rocketSprites(), X = R(x) - sp.cx, Y = R(by) - sp.h + 1;
    const flameY = o.booster === false ? Y + ROCK.seam + 2 : R(by) + 1;
    if (o.flame > 0) flame(R(x), flameY, o.flame, o.t, o.booster === false ? 0.75 : 1);
    g.drawImage(sp.upper, X, Y);
    if (o.booster !== false) g.drawImage(sp.booster, X, Y);
  }
  function flame(x, y, thrust, t, scale = 1) {
    const f = tickN(t) % 2, L = R((f ? 14 : 10) * thrust * scale), hw0 = 3.5 * scale;
    for (let i = 0; i < L; i++) {
      const k = i / L, hw = Math.max(0, R(hw0 * (1 - k * 0.85) + (f && i < 3 ? 1 : 0)));
      px(x - hw, y + i, hw * 2 + 1, 1, k > 0.75 ? C.k6 : C.k8);
      if (hw >= 1) px(x - hw + 1, y + i, hw * 2 - 1, 1, k > 0.55 ? C.k8 : C.k9);
      if (hw >= 2 && k < 0.4) px(x - 1, y + i, 3, 1, C.k10);
    }
    for (let s = 0; s < 4; s++) {
      const h = B.hash01("spark", tickN(t), s);
      if (h < 0.5) px(x + R((h - 0.25) * 16), y + L + 1 + R(h * 6), 1, 1, s % 2 ? C.k9 : C.k7);
    }
  }
  /** Lattice tower, rose rim; the arm swings off. */
  function tower(x, groundY, armY, armOn, t) {
    const top = groundY - 60; px(x, top, 6, groundY - top, C.m0); px(x + 1, top, 4, groundY - top, C.out); px(x, top, 1, groundY - top, C.k5);
    for (let y = top + 2; y < groundY - 1; y += 6)
      for (let i = 0; i < 5; i++) { px(x + 1 + i, y + i, 1, 1, C.m1); px(x + 5 - i, y + i, 1, 1, C.m1); }
    px(x - 1, top - 2, 8, 2, C.k0); px(x + 2, top - 6, 1, 4, C.k0);
    if (tickN(t) % 6 < 3) px(x + 2, top - 7, 1, 1, C.k6);
    if (armOn) { px(x + 6, armY, 6, 2, C.k0); px(x + 6, armY, 6, 1, C.k4); }
  }
  function smoke(x, y, t) {
    const age = tk(t) - T_IGNITE;
    if (age <= 0) return;
    for (let i = 0; i < 10; i++) {
      const side = i % 2 ? 1 : -1, d = B.hash01("puff", i), grow = B.clamp(age / 1.4);
      const cx = x + side * (5 + grow * (14 + d * 24) * (0.5 + (i / 10) * 0.8)), cy = y - 2 - d * 4 - grow * 3;
      const r = R(2 + grow * (3 + d * 5)), a = B.clamp(1.1 - age / 2.4); disc(cx, cy, r, C.m1, a);
      disc(cx - 1, cy - 1, Math.max(1, r - 1), C.m2, a * 0.9);
    }
  }
  const capsule = (x, y) =>
    B.sprite(g, ["..oo..", ".owmo.", "owcwmo", "owwwmo", "oooooo"], R(x) - 3, R(y) - 2, 1, { o: C.out, c: C.w5, w: C.m3, m: C.m1 });
  const tickMark = (x, y) =>
    B.sprite(g, [".....oo", "....ogo", "o..ogo.", "ogogo..", ".ogo...", "..o...."], R(x), R(y), 1, { o: C.out, g: C.l4 });

  /** Sky: flat stripes, dither seams, stars. */
  function skyTex() {
    return B.layer("arc-sky", BW, BH * 4, (q, w, h) => {
      const stops = [[0, C.out], [0.42, C.k0], [0.6, C.k1], [0.7, C.k2], [0.78, C.k3], [0.84, C.k4], [0.885, C.k5], [0.92, C.k6], [0.95, C.k7], [0.975, C.k8], [1.01, C.k9]].map(([s, c]) => [s, B.rgb(c)]);
      const img = q.createImageData(w, h), d = img.data;
      for (let y = 0; y < h; y++) {
        const f = y / h; let i = 0;
        while (i < stops.length - 2 && f >= stops[i + 1][0]) i++;
        const seam = B.smooth(0.72, 1, (f - stops[i][0]) / (stops[i + 1][0] - stops[i][0]));
        for (let x = 0; x < w; x++) put(d, (y * w + x) * 4, bay(x, y) < seam ? stops[i + 1][1] : stops[i][1]);
      }
      q.putImageData(img, 0, 0); const r = B.rng(15);
      for (let i = 0; i < (w * h) / 260; i++) {
        const y = R(r() * h * 0.8), x = R(r() * w); q.fillStyle = r() < 0.15 ? C.k9 : r() < 0.5 ? C.m2 : C.m3;
        q.fillRect(x, y, 1, 1);
      }
    });
  }
  /** Parallax ridge: silhouette, lit rim facing the sun, dithered haze. */
  function ridge(key, base, amp, freq, body, rim, haze) {
    return B.layer("arc-ridge:" + key + ":" + base, BW, BH, (q, w, h) => {
      const top = (x) => R(base - amp * (0.5 + 0.5 * B.noise1(x * freq, key.length * 7)) - amp * 0.35 * B.noise1(x * freq * 3.7, 11));
      for (let x = 0; x < w; x++) {
        const y = top(x), yl = top(x - 1); q.fillStyle = body; q.fillRect(x, y, 1, h - y); q.fillStyle = rim;
        if (yl > y) q.fillRect(x, y, 1, Math.min(3, yl - y + 1));
        else if (B.hash01(key, x) < 0.25) q.fillRect(x, y, 1, 1);
        if (haze) {
          q.fillStyle = haze;
          for (let yy = y; yy < h; yy++) if (bay(x, yy) < B.smooth(base - amp * 0.2, base + 18, yy) * 0.5) q.fillRect(x, yy, 1, 1);
        }
      }
    });
  }
  /** Planet: dithered ramps, clouds, an air rim. */
  function earthTex(r) {
    return B.layer("arc-earth", 2 * r + 6, 2 * r + 6, (q, w, h) => {
      const img = q.createImageData(w, h), d = img.data, c = r + 3;
      const sea = [C.out, C.s0, C.s1, C.s2, C.s3].map((x) => B.rgb(x)), land = [C.l0, C.l1, C.l2, C.l3, C.l4].map((x) => B.rgb(x));
      const air = B.rgb(C.s3), cloud = B.rgb(C.m3), cl2 = B.rgb(C.m2);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const dx = (x - c) / r, dy = (y - c) / r, dd = dx * dx + dy * dy; let col = null;
          if (dd <= 1) {
            const nz = Math.sqrt(1 - dd), lit = B.clamp(-0.55 * dx - 0.6 * dy + 0.58 * nz + 0.25);
            const isLand = B.fbm(dx * 2.2 + 3, dy * 2.2, 4, 5) > 0.08, isCloud = B.fbm(dx * 3.5, dy * 6, 3, 9) > 0.32;
            const ramp = isLand ? land : sea, f = lit * (ramp.length - 1), i = Math.floor(f);
            col = ramp[Math.min(ramp.length - 1, i + (bay(x, y) < f - i ? 1 : 0))];
            if (isCloud && lit > 0.35) col = lit > 0.6 ? cloud : cl2;
          } else if (dd <= Math.pow(1 + 2.2 / r, 2) && bay(x, y) < B.clamp(0.25 - dx * 0.5 - dy * 0.5)) col = air;
          if (col) put(d, (y * w + x) * 4, col);
        }
      q.putImageData(img, 0, 0);
    });
  }
  const drawEarth = (cx, cy, r) => g.drawImage(earthTex(r), R(cx) - r - 3, R(cy) - r - 3);
  function stars(seed, n, fall, t) {
    for (let i = 0; i < n; i++) {
      const x = R(B.hash01(seed, i, "x") * BW), y = R((B.hash01(seed, i, "y") * BH + fall * (1 + (i % 3))) % BH);
      if (B.hash01(seed, i, tickN(t) >> 1) < 0.12) continue;
      px(x, y, 1, fall ? 2 + (i % 3) : 1, i % 7 === 0 ? C.k9 : i % 3 ? C.m2 : C.m3);
      if (i % 13 === 0 && !fall) { px(x - 1, y, 3, 1, C.m2); px(x, y - 1, 1, 3, C.m2); px(x, y, 1, 1, C.m3); }
    }
  }
  function sparkle(x, y, t, seed) {
    const ph = (tickN(t) + seed) % 4;
    if (ph === 3) return;
    const r = ph === 1 ? 2 : 1; px(x - r, y, 2 * r + 1, 1, C.k9); px(x, y - r, 1, 2 * r + 1, C.k9); px(x, y, 1, 1, C.m3);
  }
  /** Pop-up word: rises a pixel per tick, dithers away. */
  function popWord(str, x, y, t, at, color, dur = 1.0) {
    const age = tk(t) - at;
    if (age < 0 || age > dur) return;
    const a = 1 - B.clamp((age - dur * 0.55) / (dur * 0.45));
    ditherFade(a, () => ptext(str, x, y - Math.min(8, tickN(age)), "head", color, { align: "center", outline: true }));
  }

  // --- layout per aspect (buffer pixels)
  function layout() {
    if (P)
      return {
        ground: 258, horizon: 234, sunX: 140, rx: 42,
        quest: [S.x, S.y, S.r - S.x],
        labs: [[78, 123, S.r - 78], [78, 183, S.r - 78], [78, 221, S.r - 78]], zoom: [50, 250],
        menu: [52, 104, S.r - 52],
        lift: [S.r - 50, 186], drop: [112, 214],
        counter: [S.x, 50, S.r - S.x], cap: [S.x, 204, S.r - S.x], numRocket: [BW / 2, 196], limb: [300, 30],
        orbit: { earth: [BW / 2, 226, 36], r: 54, slow: [S.x, S.y, S.r - S.x], fast: [S.x, S.y + 40, S.r - S.x], miss: [154, 180] },
        close: { earth: [BW / 2, 226, 36], r: 54, banner: [S.x, S.y + 4, S.r - S.x], headKind: "head" },
      };
    return {
      ground: 150, horizon: 130, sunX: 64, rx: 170,
      quest: [S.x, S.y, 134],
      labs: [[206, 38, 100], [206, 95, 100], [206, 134, 100]], zoom: [170, 168],
      menu: [188, S.y, S.r - 188],
      lift: [104, 92], drop: [104, 112],
      counter: [112, 18, S.r - 112], cap: [112, 86, S.r - 112], numRocket: [64, 150], limb: [380, 24],
      orbit: { earth: [226, 98, 36], r: 54, slow: [S.x + 6, S.y + 10, 136], fast: [S.x + 6, S.y + 54, 136], miss: [292, 50] },
      close: { earth: [BW / 2, 124, 28], r: 42, banner: [40, S.y, BW - 80], headKind: "big" },
    };
  }

  function sceneLaunch(t, Lo) {
    // diagram beat: whole-pixel zoom on the rocket (the scene is drawn apart, then scaled in)
    const k = t < 2 || t >= 4.3 ? 1 : t < 2.1 || t >= 4.2 ? 2 : 3, f = (k - 1) / 2, keep = g;
    if (k > 1) g = B.scratch("arc-zoom", BW, BH);
    const tt = tk(t); const lift = tt < T_LIFT ? 0 : 34 * Math.pow(tt - T_LIFT, 2) + 5 * (tt - T_LIFT);
    const camY = R(Math.max(0, lift - 14));
    const rise = (start) => R((1 - B.ease.outCubic(B.prog(t, start, 0.9))) * BH * 0.55);
    const oF = rise(0.0), oM = rise(0.18), oG = rise(0.36); const sky = skyTex();
    g.drawImage(sky, 0, Math.min(0, -(sky.height - BH) + R(camY * 0.7))); const sunY = Lo.horizon - 4 + oF + R(camY * 0.2);
    disc(Lo.sunX, sunY, 24, C.k8, 0.35); disc(Lo.sunX, sunY, 18, C.k9, 0.4); disc(Lo.sunX, sunY, 12, C.k9);
    disc(Lo.sunX - 3, sunY - 3, 6, C.k10);
    g.drawImage(ridge("far", Lo.horizon, 30, 0.035, C.k3, C.k6, C.k4), 0, oF + R(camY * 0.25));
    g.drawImage(ridge("mid", Lo.horizon + 12, 14, 0.06, C.k2, C.k4, null), 0, oM + R(camY * 0.5));
    g.drawImage(ridge("gnd", Lo.ground, 3, 0.15, C.l0, C.l1, null), 0, oG + camY); const gy = Lo.ground + oG + camY;
    // the launch field: a service road and pad lights blinking on the tick
    px(0, gy + 6, BW, 3, C.m0); for (let x = (tickN(t) % 2) * 4; x < BW; x += 8) px(x, gy + 7, 3, 1, C.m2);
    ditherRect(0, gy + 12, BW, BH, C.l1, 0.25);
    for (let r = 0; r < 8; r++) for (let x = 6 + r * 5; x < BW; x += 16 + (r % 4) * 5) if ((tickN(t) + x + r) % 5) px(x, gy + 15 + r * 9, 2, 1, r % 2 ? C.k8 : C.k9);
    px(Lo.rx - 16, gy - 3, 32, 3, C.m1); px(Lo.rx - 16, gy - 3, 32, 1, C.m2); px(Lo.rx - 5, gy - 3, 10, 3, C.out);
    tower(Lo.rx - 16, gy - 3, gy - 46, tt < T_IGNITE, t); smoke(Lo.rx, gy - 3, t);
    const thrust = tt < T_IGNITE ? 0 : tt < T_LIFT ? 0.55 : 1; const by = gy - 4 - R(lift);
    if (tt < T_SEP) rocket(Lo.rx, by, { flame: thrust, t });
    else {
      // staging: the booster falls away, solid long enough to be seen, then dithers out
      const dt = tt - T_SEP, drop = R(30 * dt * dt + 12 * dt);
      ditherFade(1 - B.clamp((dt - 0.7) / 0.5), () => {
        const sp = rocketSprites(); g.drawImage(sp.booster, R(Lo.rx) - sp.cx + R(dt * 12), R(by) - sp.h + 1 + drop);
      });
      rocket(Lo.rx, by, { booster: false, flame: dt > 0.2 ? 1 : 0, t });
    }
    if (tickN(t) === tickN(T_IGNITE)) ditherRect(0, 0, BW, BH, C.k10, 0.5);
    const x0 = R(Lo.rx - B.lerp(Lo.rx, Lo.zoom[0], f) / k), y0 = R(by - B.lerp(by, Lo.zoom[1], f) / k);
    if (k > 1) {
      const w = Math.ceil(BW / k) + 1, h = Math.ceil(BH / k) + 1;
      keep.drawImage(g.canvas, x0, y0, w, h, 0, 0, w * k, h * k); g = keep;
    }
    return { by, Z: (x, y) => [(x - x0) * k, (y - y0) * k] };
  }

  const PARTS = [["CAPSULE", "Holds the crew", 14], ["FUEL TANKS", "Fuel + oxygen", 34], ["ENGINES", "Push gas down", 50]];
  const STEPS = ["LIFT OFF", "DROP STAGE", "GO SIDEWAYS"];
  function uiLaunch(t, Lo, st) {
    const [qx, qy, qw] = Lo.quest;
    textWindow(qx, qy, qw, "QUEST 01", "How does a rocket reach orbit?", t, B.prog(t, 0.7, 0.25), 0.95);
    PARTS.forEach(([name, body, row], i) => {
      const at = 2.15 + i * 0.55, op = B.prog(t, at, 0.25) * (1 - B.prog(t, 4.2, 0.2));
      if (op <= 0) return;
      const [lx, ly, lw] = Lo.labs[i]; textWindow(lx, ly, lw, name, body, t, op, at + 0.2, { next: false });
      if (snap(op) < 1) return;
      const ty = st.by - ROCK.rows + row; const from = [lx - 3, ly + 13];
      const to = st.Z(Lo.rx + ROCK.hw + 1, ty); to[0] += 3;
      dotArrow([from, [from[0] - 3, from[1]], [to[0] + 6, to[1]], to], B.prog(t, at + 0.15, 0.4), t, C.k9);
    });
    if (t >= 4.25) menu(t, Lo.menu, t < T_SEP - 0.1 ? 0 : 1);
    popWord("LIFT OFF!", Lo.lift[0], Lo.lift[1], t, T_LIFT, C.k9, 1.1);
    popWord("STAGE 1 DROPS", Lo.drop[0], Lo.drop[1], t, T_SEP + 0.1, C.k7, 0.9);
  }
  function menu(t, [mx, my, mw], cur) {
    const h = 5 + FONT.head.lh + 1 + STEPS.length * (FONT.head.lh + 1) + 3;
    if (!windowBox(mx, my, mw, h, B.prog(t, 4.25, 0.25))) return;
    ptext("STEPS", mx + 5, my + 5, "head", C.k9);
    STEPS.forEach((s, i) => {
      const y = my + 6 + FONT.head.lh + i * (FONT.head.lh + 1);
      ptext(`${i + 1} ${s}`, mx + 13, y, "head", i === cur ? C.k9 : C.m3);
      if (i === cur) cursor(mx + 6, y + 6);
      if (i < cur) tickMark(mx + mw - 13, y + 1);
    });
  }

  /** Key number: streaming stars, score counter, stepped bar. */
  function sceneNumber(t, Lo) {
    const lt = t - BEATS[3]; const sky = skyTex(); g.drawImage(sky, 0, -R(sky.height * 0.2));
    stars(7, R((BW * BH) / 500), tickN(t) * 3, t); const [er, rise] = Lo.limb; drawEarth(BW * 0.5, BH + er - rise, er);
    const [rx, ry] = Lo.numRocket; rocket(rx, ry + (tickN(t) % 2), { booster: false, flame: 1, t });
    const [cx, cy, cw] = Lo.counter; const k = B.clamp((tk(t) - BEATS[3] - 0.2) / 1.2);
    const val = R(28000 * (1 - Math.pow(1 - k, 2)) / 100) * 100; const h = 5 + FONT.head.lh + FONT.big.lh + 12;
    if (windowBox(cx, cy, cw, h, B.prog(lt, 0.05, 0.2))) {
      ptext("SPEED", cx + 5, cy + 5, "head", C.k9); ptext("KM/H", cx + cw - 6, cy + 5, "head", C.m3, { align: "right" });
      ptext(String(val).padStart(7, "0"), cx + cw / 2, cy + 5 + FONT.head.lh, "big", k >= 1 ? C.k9 : C.m3, { align: "center" });
      const segs = 10, sw = Math.floor((cw - 12) / segs), on = Math.floor(k * segs + 1e-6), by = cy + h - 9;
      for (let i = 0; i < segs; i++) {
        px(cx + 6 + i * sw, by, sw - 1, 5, C.out);
        if (i < on) { px(cx + 6 + i * sw, by, sw - 1, 4, i >= 8 ? C.k9 : C.l4); px(cx + 6 + i * sw, by, sw - 1, 1, i >= 8 ? C.k10 : C.l3); }
      }
      if (k >= 1) for (let i = 0; i < 6; i++) sparkle(R(cx + 8 + B.hash01("sp", i) * (cw - 16)), i % 2 ? cy + h + 3 : cy - 4, t, i);
    }
    const [x2, y2, w2] = Lo.cap;
    textWindow(x2, y2, w2, "ORBIT SPEED", "8 km every second: around Earth in 90 min.", t, B.prog(lt, 0.45, 0.2), BEATS[3] + 0.6);
  }

  /** Step 3 and close: a red trail falls back, a gold orbit keeps missing. */
  function sceneOrbit(t, O, closing) {
    const lt = t - BEATS[4]; g.fillStyle = C.out; g.fillRect(0, 0, BW, BH); stars(3, R((BW * BH) / 420), 0, t);
    const [ex, ey, er] = O.earth; drawEarth(ex, ey, er); const top = [ex, ey - er - 1];
    const land = [ex + Math.sin(0.9) * (er + 1), ey - Math.cos(0.9) * (er + 1)];
    const slow = B.quad(top[0], top[1], top[0] + er * 0.35, top[1] - er * 0.75, land[0], land[1], 40);
    dotArrow(slow, closing ? 1 : B.prog(tk(t), BEATS[4] + 0.3, 0.6), t, C.k6, { step: 3 });
    if (!closing) popWord("MISS!", O.miss[0], O.miss[1], t, BEATS[4] + 0.95, C.k6, 1.0);
    const po = closing ? 1 : B.prog(tk(t), BEATS[4] + 1.05, 0.6);
    if (po > 0) {
      const a0 = -Math.PI / 2, ring = B.arcPts(ex, ey, O.r, a0, a0 + B.TAU * po * 0.999, 120);
      dotArrow(ring, 1, t, C.k9, { step: 4, head: false });
      const ca = a0 + B.TAU * po + Math.max(0, tk(t) - (BEATS[4] + 1.65)) * 0.9;
      capsule(ex + Math.cos(ca) * O.r, ey + Math.sin(ca) * O.r);
    }
    if (closing) return;
    const [sx, sy, sw] = O.slow, [fx, fy, fw] = O.fast;
    textWindow(sx, sy, sw, "TOO SLOW?", "It falls back down.", t, B.prog(lt, 0.2, 0.2), BEATS[4] + 0.35, { next: false });
    textWindow(fx, fy, fw, "3 GO SIDEWAYS", "Fast enough: it falls around Earth.", t, B.prog(lt, 0.75, 0.2), BEATS[4] + 0.9, { cps: 64 });
  }
  const LESSON = "Orbit: falling sideways so fast you keep missing the ground.";
  function uiClose(t, O) {
    const lt = t - BEATS[5]; const [bx, by, bw] = O.banner;
    textWindow(bx, by, bw, "MISSION CLEAR!", LESSON, t, B.prog(lt, 0.25, 0.2), BEATS[5] + 0.4, { headKind: O.headKind, headCenter: true, cps: 62 });
    if (snap(B.prog(lt, 0.25, 0.2)) >= 1) {
      const h = winHeight(bw, "x", LESSON, { headKind: O.headKind });
      for (let i = 0; i < 7; i++) sparkle(R(bx + 6 + B.hash01("cl", i) * (bw - 12)), i % 2 ? by + h + 3 : by - 4, t, i);
    }
  }

  function mosaic(size) {
    if (size <= 1) return;
    const w = Math.ceil(BW / size), h = Math.ceil(BH / size), q = B.scratch("arc-mos", w, h);
    q.imageSmoothingEnabled = false; q.drawImage(g.canvas, 0, 0, w * size, h * size, 0, 0, w, h);
    g.imageSmoothingEnabled = false; g.drawImage(q.canvas, 0, 0, w, h, 0, 0, w * size, h * size);
  }
  function liftBuffer(key) {
    const q = B.scratch(key, BW, BH); q.drawImage(g.canvas, 0, 0); g.fillStyle = C.out; g.fillRect(0, 0, BW, BH);
    return q.canvas;
  }
  function ripple(amp, t) {
    if (amp < 1) return;
    const q = liftBuffer("arc-rip"), ph = tickN(t * 2);
    for (let y = 0; y < BH; y++) g.drawImage(q, 0, y, BW, 1, R(Math.sin(y * 0.15 + ph * 0.9) * amp), y, BW, 1);
  }
  function irisClose(cx, cy, r) {
    g.fillStyle = C.out;
    for (let y = 0; y < BH; y++) {
      const dy = y - cy;
      if (Math.abs(dy) >= r) { g.fillRect(0, y, BW, 1); continue; }
      const hw = Math.floor(Math.sqrt(r * r - dy * dy)); g.fillRect(0, y, R(cx - hw), 1); g.fillRect(R(cx + hw), y, BW, 1);
    }
  }
  function shakeBuffer(dx, dy) {
    if (dx || dy) g.drawImage(liftBuffer("arc-shk"), dx, dy);
  }
  const near = new Map();
  function nearest(r, gg, b) {
    const key = (r << 16) | (gg << 8) | b; let i = near.get(key);
    if (i != null) return i;
    let best = 1e9;
    LOCK.forEach((c, j) => {
      const d = 2 * (c[0] - r) ** 2 + 4 * (c[1] - gg) ** 2 + 3 * (c[2] - b) ** 2;
      if (d < best) { best = d; i = j; }
    });
    near.set(key, i);
    return i;
  }
  const levelMaps = new Map();
  function levelMap(lv) {
    if (!levelMaps.has(lv)) levelMaps.set(lv, LOCK.map((c) => nearest(R(c[0] * lv), R(c[1] * lv), R(c[2] * lv))));
    return levelMaps.get(lv);
  }
  /** Palette lock; fades move in whole palette steps. */
  function lockPalette(level) {
    const lv = Math.round(B.clamp(level) * 4) / 4, map = lv < 1 ? levelMap(lv) : null;
    const img = g.getImageData(0, 0, BW, BH), d = img.data;
    for (let o = 0; o < d.length; o += 4) {
      let i = nearest(d[o], d[o + 1], d[o + 2]);
      if (map) i = map[i];
      put(d, o, LOCK[i]);
    }
    g.putImageData(img, 0, 0);
  }

  function draw(ctx, W, H, t) {
    const F = B.frame(W, H); const cell = Math.max(1, Math.round(Math.min(W, H) / SHORT_SIDE)); BW = Math.ceil(W / cell);
    BH = Math.ceil(H / cell); P = F.portrait;
    S = { x: Math.ceil(F.safe.x / cell), y: Math.ceil(F.safe.y / cell), r: Math.floor(F.safe.r / cell), b: Math.floor(F.safe.b / cell) };
    g = B.scratch("arc-buffer", BW, BH); g.imageSmoothingEnabled = false; const Lo = layout();
    if (t < BEATS[3]) uiLaunch(t, Lo, sceneLaunch(t, Lo));
    else if (t < BEATS[4]) sceneNumber(t, Lo);
    else if (t < BEATS[5]) sceneOrbit(t, Lo.orbit, false);
    else { sceneOrbit(t, Lo.close, true); uiClose(t, Lo.close); }
    const mos = Math.max(0, 1 - Math.abs(t - BEATS[3]) / 0.28);
    if (mos > 0) mosaic(Math.max(1, R(mos * 16)));
    const rip = Math.max(0, 1 - Math.abs(t - BEATS[4]) / 0.3);
    if (rip > 0) ripple(R(rip * 12), t);
    const ir = t < BEATS[5] ? B.prog(t, BEATS[5] - 0.3, 0.3) : 1 - B.prog(t, BEATS[5], 0.3);
    if (ir > 0) irisClose(BW / 2, BH * 0.5, R((1 - ir) * Math.hypot(BW, BH) * 0.6));
    // hits: a short whole-pixel shake
    let sh = 0;
    for (const [at, amp] of [[T_IGNITE, 2], [T_LIFT, 1], [BEATS[4] + 0.95, 2]]) if (t >= at && t < at + 0.35) sh = amp;
    if (sh) shakeBuffer(R((B.hash01("shx", tickN(t * 2)) - 0.5) * 2 * sh), R((B.hash01("shy", tickN(t * 2)) - 0.5) * 2 * sh));
    // finishing: palette lock + stepped brightness, then the hard upscale
    lockPalette(B.prog(t, 0.0, 0.6)); ctx.imageSmoothingEnabled = false; ctx.fillStyle = C.out; ctx.fillRect(0, 0, W, H);
    ctx.drawImage(g.canvas, 0, 0, BW * cell, BH * cell);
  }

  // --- sound: square blips, noise sweeps, a chiptune loop
  SOUND.define("arcade-sweep", (v, o) => {
    const up = !o.down;
    v.noise({ filter: "bandpass", q: 3, f: up ? 300 : 5000, f2: up ? 6000 : 250, glide: 0.4, a: 0.01, hold: 0.15, len: 0.25, peak: 0.28 });
    v.tone({ type: "square", f: up ? 180 : 900, f2: up ? 900 : 120, glide: 0.4, a: 0.005, hold: 0.2, len: 0.15, peak: 0.05, shape: "lin" });
  }, { verb: 0.1 });
  SOUND.define("arcade-rumble", (v, o) => {
    const d = o.dur ?? 1.5;
    v.noise({ brown: true, filter: "lowpass", f: 300, f2: 1100, glide: d, a: 0.08, hold: d - 0.5, len: 0.45, peak: 0.55 });
    v.noise({ filter: "bandpass", q: 0.7, f: 900, a: 0.1, hold: d - 0.6, len: 0.4, peak: 0.07 });
  }, { verb: 0.15 });
  SOUND.define("arcade-chiptune", (v) => {
    const d = v.dur ?? 8, step = 60 / 128 / 2, bus = v.bedGain(d, 1, 0.6);
    const bass = ["A2", "F2", "C3", "G2"], arp = [["A4", "C5", "E5", "C5"], ["F4", "A4", "C5", "A4"], ["C5", "E5", "G5", "E5"], ["G4", "B4", "D5", "B4"]];
    let i = 0;
    for (let at = 0.05; at < d - 0.1; at += step, i++) {
      const bar = Math.floor(i / 8) % 4;
      if (i % 2 === 0) v.tone({ at, type: "triangle", f: v.hz(bass[bar]), a: 0.003, hold: step * 1.4, len: 0.05, peak: 0.16, dest: bus, shape: "lin" });
      v.tone({ at, type: "square", f: v.hz(arp[bar][i % 4]), a: 0.002, hold: step * 0.45, len: 0.04, peak: 0.025, dest: bus, shape: "lin" });
    }
  }, { bed: true, verb: 0.08 });

  function score(k) {
    const blips = (at, n, gain = 0.25, step = 0.04, pitch = 0) => k.repeat(at, step, n, "blip", { gain, vary: 1, pitch });
    k.bed("arcade-chiptune", 0.6, DUR, { gain: 0.7 }); k.at(0.05, "arcade-sweep", { gain: 0.6 });
    k.at(0.7, "blip", { note: "E6", gain: 0.7 }).at(0.8, "blip", { note: "A6", gain: 0.7 }); blips(0.95, 16, 0.35);
    [2.15, 2.7, 3.25].forEach((at, i) => {
      k.at(at, "blip", { note: ["C6", "E6", "G6"][i], gain: 0.7 }); blips(at + 0.22, 7, 0.3, 0.06, -3);
    });
    k.at(4.25, "blip", { note: "C6", gain: 0.7 }).at(4.4, "blip", { note: "A5" });
    k.at(T_IGNITE, "crunch8", { gain: 0.9 }).at(T_IGNITE, "boom", { gain: 0.6 });
    k.at(T_IGNITE + 0.05, "arcade-rumble", { dur: 1.75, gain: 0.8 }); k.at(T_LIFT, "jump", { gain: 0.6 });
    k.at(T_SEP - 0.1, "blip", { note: "C6" }); k.at(T_SEP, "zap", { gain: 0.7 }).at(T_SEP + 0.02, "crunch8", { gain: 0.5 });
    k.at(BEATS[3] - 0.25, "arcade-sweep", { gain: 0.7 });
    for (let i = 0; i < 20; i++) k.at(BEATS[3] + 0.22 + i * 0.06, "blip", { note: 72 + Math.floor(i / 3), gain: 0.55 });
    k.at(BEATS[3] + 1.45, "coin", { gain: 0.7 }); blips(BEATS[3] + 0.75, 22);
    k.at(BEATS[4] - 0.28, "arcade-sweep", { gain: 0.6 }); blips(BEATS[4] + 0.35, 10);
    k.at(BEATS[4] + 0.95, "error", { gain: 0.8 });
    k.seq(BEATS[4] + 1.1, 0.07, ["C5", "E5", "G5", "C6"], { voice: "blip", gain: 0.7 }); blips(BEATS[4] + 0.9, 18);
    k.at(BEATS[5] - 0.3, "arcade-sweep", { down: true, gain: 0.6 });
    k.seq(BEATS[5] + 0.25, 0.075, ["C5", "E5", "G5", "C6", "E6", "G6", "C7"], { voice: "blip", gain: 0.8 });
    k.at(BEATS[5] + 0.95, "powerup", { gain: 0.5 }); blips(BEATS[5] + 0.45, 30, 0.22);
  }

  Player.register({
    id: "pixel-arcade", name: "Pixel Arcade", duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Jersey+10&family=Pixelify+Sans&display=swap",
      faces: ['400 20px "Jersey 10"', '400 20px "Pixelify Sans"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Steps 1-2", "Key number", "Step 3", "Close"],
    stills: [1.95, 3.95, 5.95, 7.95, 9.95, 11.7],
    draw, score,
  });
})();
