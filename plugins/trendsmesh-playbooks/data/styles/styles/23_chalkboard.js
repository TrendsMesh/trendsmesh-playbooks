/* 23 Chalkboard Lesson - reference animation.
 * Topic (setting, replace it): "Why do we have leap years?" - one orbit takes about 365 1/4 days.
 * Rendering (keep it): a dark green-black slate in a wooden frame with a chalk ledge, cloudy wiper marks and faint
 * ghosts of old lessons. Everything chalk is drawn on one layer in flat chalk colours, then that layer is cut by a
 * fixed board-grain speckle mask (destination-in), so strokes break up where the stick skipped over the board; a
 * blurred copy of the layer is screened under it as dust haze. Lines wobble, are drawn twice with overshoot; fills
 * are diagonal hatching; letters are written one by one in a teacher's hand, each leaning and wandering off the
 * baseline. A felt eraser wipes sections away and leaves a ghost and a smear on the board.
 * Motion: strokes advance at hand speed with a pause between lines; marks come after the thing they mark; a section
 * is wiped (a steady sweep, leaving a ghost) before the next is written there. Nothing bounces.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { board: "#1f2b27", cloud: "#33423c", white: "#f1f0e6", yellow: "#f3d96b", pink: "#ee9db1", blue: "#8cc3e6", wood: "#7a5434" };
  const HAND = "Kalam", PRINT = "Patrick Hand";
  const DUR = 15;
  const BEATS = [0, 2.65, 5.4, 8.8, 11.75, 12.9];

  let CH = null, U = 1, T = 0; // the chalk layer, frame unit, time

  // ------------------------------------------------------------------ chalk helpers (reuse these)
  /**
   * A chalk line along pts, written on from its start to p: the path wobbles a little by hand; a broad faint pass
   * gives the dusty edge and a thin offset pass breaks it up. o: { w, color, p, seed, amp, alpha }
   */
  function chalkLine(pts, o) {
    const p = B.clamp(o.p ?? 1);
    if (p <= 0.003) return;
    const w = o.w ?? 0.55 * U;
    const path = B.wobble(B.densify(pts, Math.max(3, w * 1.2)), { amp: o.amp ?? w * 0.45, freq: 1.6, seed: o.seed ?? 1 });
    const a = o.alpha ?? 1;
    B.strokeReveal(CH, path, p, { width: w * 2.1, color: o.color || PAL.white, alpha: 0.16 * a });
    B.strokeReveal(CH, path, p, { width: w, color: o.color || PAL.white, alpha: 0.95 * a });
    CH.save();
    CH.translate(w * 0.35, -w * 0.25);
    B.strokeReveal(CH, path, p, { width: w * 0.45, color: o.color || PAL.white, alpha: 0.5 * a });
    CH.restore();
  }
  /** A line drawn twice: the second pass a hair off, starting as the first one ends (underlines, boxes). */
  function twice(pts, p, o) {
    chalkLine(pts, { ...o, p: B.clamp(p * 2) });
    const off = pts.map(([x, y], i) => [x + U * 0.25 * Math.sin(i * 1.7), y + U * 0.45]);
    chalkLine(off, { ...o, p: B.clamp(p * 2 - 1), seed: (o.seed ?? 1) + 5, w: (o.w ?? 0.55 * U) * 0.85 });
  }
  /** Loose circle or ellipse in one quick stroke that overshoots where it meets itself. */
  function chalkRing(cx, cy, rx, ry, p, o = {}) {
    const a0 = o.start ?? -2.2, pts = [];
    for (let i = 0; i <= 60; i++) {
      const a = a0 + (i / 60) * B.TAU * 1.1, k = 1 + 0.05 * Math.sin(i * 0.25) + 0.04 * (i / 60);
      pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    chalkLine(pts, { ...o, p });
  }
  /** Diagonal hatching inside a circle (chalk shading is never solid), stroke by stroke as p grows. */
  function hatchCircle(cx, cy, r, p, o = {}) {
    const n = Math.round((2 * r) / (o.gap ?? 1.3 * U));
    for (let i = 0; i < n; i++) {
      const d = -r + ((i + 0.5) / n) * 2 * r, h = Math.sqrt(Math.max(0, r * r - d * d)) * 0.92;
      const k = B.clamp(p * n - i);
      if (k <= 0) break;
      const c = Math.SQRT1_2;
      chalkLine([[cx + d * c - h * c, cy + d * c + h * c], [cx + d * c + h * c, cy + d * c - h * c]], { w: 0.28 * U, color: o.color, p: k, seed: 70 + i, alpha: 0.75 });
    }
  }
  /** Loose arrow: a line, then a head of two quick strokes. */
  function chalkArrow(pts, p, o = {}) {
    chalkLine(pts, { ...o, p: B.clamp(p * 1.25) });
    const hp = B.clamp(p * 5 - 4);
    if (hp <= 0) return;
    const [x, y, a] = B.pointAt(pts, 1), hl = o.head ?? 2.6 * U;
    chalkLine([[x, y], [x - Math.cos(a - 0.5) * hl, y - Math.sin(a - 0.5) * hl]], { ...o, p: B.clamp(hp * 2), seed: 91 });
    chalkLine([[x, y], [x - Math.cos(a + 0.5) * hl, y - Math.sin(a + 0.5) * hl]], { ...o, p: B.clamp(hp * 2 - 1), seed: 92 });
  }
  /** A tick in two strokes. */
  function tick(x, y, s, p, color = PAL.yellow) {
    chalkLine([[x - s * 0.5, y], [x - s * 0.1, y + s * 0.45]], { w: 0.6 * U, color, p: B.clamp(p * 2.5), seed: 31 });
    chalkLine([[x - s * 0.1, y + s * 0.45], [x + s * 0.6, y - s * 0.6]], { w: 0.6 * U, color, p: B.clamp(p * 1.7 - 0.7), seed: 32 });
  }
  /** Five-point star in one stroke (a teacher's margin star). */
  function star(cx, cy, r, p, color) {
    const pts = [];
    for (let i = 0; i <= 5; i++) {
      const a = -Math.PI / 2 + (i * 4 * Math.PI) / 5;
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
    chalkLine(pts, { w: 0.6 * U, color, p, seed: 44 });
  }
  /** How long writing str takes at rate chars/s, with a pause between lines. */
  const writeTime = (str, rate = 16, pause = 0.22) => {
    const lines = str.split("\n");
    return lines.reduce((a, l) => a + l.length / rate, 0) + pause * (lines.length - 1);
  };
  /**
   * Write chalk text live from t0: letters appear one by one at hand speed, each leaning a little and wandering off
   * the baseline; a faint wide stroke gives the dusty edge. Returns rows [{ x, y, w }] for underlines and circles.
   * o: { color, rate (chars/s, 16), font, align "left" | "center", lh (line height, 1.18), seed, pause }
   */
  function chalkWrite(str, x, y, size, t0, o = {}) {
    const g = CH, rate = o.rate ?? 16, seed = o.seed ?? 3, rows = [];
    g.save();
    g.font = B.font(size, o.font || HAND, o.weight ?? 700);
    g.textBaseline = "middle";
    g.textAlign = "left";
    let tc = t0;
    str.split("\n").forEach((line, li) => {
      const lw = g.measureText(line).width, x0 = o.align === "center" ? x - lw / 2 : x, ly = y + li * size * (o.lh ?? 1.18);
      const drift = (B.hash01(seed, li) - 0.5) * size * 0.14;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === " ") continue;
        const ta = tc + i / rate + B.hash01(seed, li, i) * 0.02, k = B.clamp((T - ta) / 0.06);
        if (k <= 0) break;
        const xi = g.measureText(line.slice(0, i)).width, dy = B.noise1(i * 0.45 + li * 9, seed) * size * 0.05 + (xi / Math.max(1, lw)) * drift;
        g.save();
        g.translate(x0 + xi, ly + dy);
        g.rotate(-0.03 + B.noise1(i * 0.7, seed + 1) * 0.035);
        g.globalAlpha = k;
        g.fillStyle = o.color || PAL.white;
        g.fillText(ch, 0, 0);
        g.restore();
      }
      rows.push({ x: x0, y: ly, w: lw, end: tc + line.length / rate });
      tc += line.length / rate + (o.pause ?? 0.22);
    });
    g.restore();
    return rows;
  }
  /** Width of a prefix of a string in the chalk hand (to circle or underline one word). */
  function prefixW(str, size, o = {}) {
    CH.save();
    CH.font = B.font(size, o.font || HAND, o.weight ?? 700);
    const w = CH.measureText(str).width;
    CH.restore();
    return w;
  }
  /**
   * The felt eraser's wipe over a rectangle: a zigzag of broad strokes rubbing the chalk layer out up to p, leaving
   * `keep` of it as a ghost. Returns the eraser's position (to draw the eraser) or null.
   */
  function wipe(r, p, keep = 0.12) {
    if (p <= 0) return null;
    const rows = Math.max(2, Math.round(r.h / (10 * U))), pts = [];
    for (let i = 0; i <= rows; i++) {
      const y = r.y + (i / rows) * r.h; // back and forth in rows, like an arm rubbing a board clean
      pts.push(...(i % 2 ? [[r.x + r.w, y], [r.x, y]] : [[r.x, y], [r.x + r.w, y]]));
    }
    const path = B.densify(pts, 2 * U), part = p >= 1 ? path : B.trim(path, 0, p);
    CH.save();
    CH.globalCompositeOperation = "destination-out";
    CH.strokeStyle = `rgba(0,0,0,${1 - keep})`;
    CH.lineWidth = (r.h / rows) * 1.6;
    CH.lineCap = CH.lineJoin = "round";
    CH.beginPath();
    B.poly(CH, part);
    CH.stroke();
    CH.restore();
    return p < 1 ? { at: B.pointAt(path, p), path: part, width: (r.h / rows) * 1.6 } : { path: part, width: (r.h / rows) * 1.6 };
  }
  /** The board's wiper smear left behind by a wipe (lighter cloudy streaks), on the board under the chalk. */
  function smear(ctx, w) {
    if (!w || w.path.length < 2) return;
    ctx.save();
    ctx.strokeStyle = B.rgba(PAL.cloud, 0.42);
    ctx.lineWidth = w.width * 0.85;
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.filter = `blur(${(3.2 * U).toFixed(1)}px)`;
    ctx.beginPath();
    B.poly(ctx, w.path);
    ctx.stroke();
    ctx.restore();
  }
  /** The felt eraser itself, mid-wipe: wooden back, grey felt edge, a puff of dust behind. */
  function eraser(ctx, w) {
    if (!w || !w.at) return;
    const [x, y] = w.at, ew = 22 * U, eh = 9 * U;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(-0.12);
    B.glow(ctx, -ew * 0.4, eh * 0.2, ew * 0.7, PAL.white, 0.12);
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.fillRect(-ew / 2 + U, -eh / 2 + U * 1.2, ew, eh);
    ctx.fillStyle = "#8d8a84";
    ctx.fillRect(-ew / 2, eh * 0.15, ew, eh * 0.35);
    ctx.fillStyle = B.linear(ctx, 0, -eh / 2, 0, eh * 0.15, [B.shade(PAL.wood, 0.25), PAL.wood]);
    ctx.fillRect(-ew / 2, -eh / 2, ew, eh * 0.65);
    ctx.restore();
  }

  // ------------------------------------------------------------------ the board (cached): slate, clouds, ghosts, frame, ledge
  function board(ctx, W, H, L) {
    const c = B.layer("chalk-board", W, H, (g, w, h) => {
      const u = L.u, r = B.rng(9), fr = L.frame;
      g.fillStyle = PAL.board;
      g.fillRect(0, 0, w, h);
      // wiper clouds: broad soft arcs of lighter slate
      for (let i = 0; i < 9; i++) {
        const x = r() * w, y = r() * h, rx = r.range(20, 45) * u, ry = r.range(6, 14) * u;
        g.save();
        g.translate(x, y);
        g.rotate(r.range(-0.25, 0.25));
        g.scale(rx / ry, 1);
        g.fillStyle = B.radial(g, 0, 0, 0, ry, [[0, B.rgba(PAL.cloud, 0.55)], [1, B.rgba(PAL.cloud, 0)]]);
        g.fillRect(-ry, -ry, 2 * ry, 2 * ry);
        g.restore();
      }
      // ghosts of old lessons, rubbed almost away
      g.save();
      g.filter = `blur(${(0.5 * u).toFixed(1)}px)`;
      g.fillStyle = B.rgba(PAL.white, 0.06);
      // texture, not labels: old writing nobody is meant to read
      B.texture(g, () => ["7 × 8 = 56", "a + b = c", "1/2 + 1/4", "rivers flow", "x = 12", "noun, verb"].forEach((s) => {
        g.font = B.font(r.range(4, 7) * u, HAND, 700);
        g.save();
        g.translate(r.range(0.1, 0.7) * w, r.range(0.15, 0.85) * h);
        g.rotate(r.range(-0.06, 0.06));
        g.fillText(s, 0, 0);
        g.restore();
      }));
      g.restore();
      // uneven top lighting, brighter in the middle
      g.fillStyle = B.radial(g, w * 0.5, h * 0.3, 0, Math.hypot(w, h) * 0.6, [[0, "rgba(255,255,255,0.07)"], [1, "rgba(0,0,0,0.25)"]]);
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: 0.2, feature: 0.05, seed: 4, mode: "soft-light" });
      B.grain(g, w, h, { amount: 0.07, seed: 2, mode: "soft-light" });
      // wooden frame with grain, and the ledge with chalk sticks and dust
      const wood = (x, y, ww, hh, vert) => {
        g.fillStyle = B.linear(g, x, y, vert ? x + ww : x, vert ? y : y + hh, [B.shade(PAL.wood, 0.15), PAL.wood, B.shade(PAL.wood, -0.3)]);
        g.fillRect(x, y, ww, hh);
        g.strokeStyle = B.rgba("#3b2414", 0.35);
        g.lineWidth = 0.15 * u;
        for (let k = 0; k < 6; k++) {
          g.beginPath();
          for (let s = 0; s <= 20; s++) {
            const f = s / 20, a = vert ? x + ww * (0.15 + k * 0.14) + Math.sin(f * 9 + k) * u * 0.3 : x + f * ww, b = vert ? y + f * hh : y + hh * (0.15 + k * 0.14) + Math.sin(f * 9 + k) * u * 0.3;
            if (s) g.lineTo(a, b);
            else g.moveTo(a, b);
          }
          g.stroke();
        }
      };
      wood(0, 0, w, fr, false);
      wood(0, 0, fr, h, true);
      wood(w - fr, 0, fr, h, true);
      wood(0, h - fr * 1.6, w, fr * 1.6, false);
      g.fillStyle = "rgba(0,0,0,0.35)";
      g.fillRect(fr, h - fr * 1.6 - 0.8 * u, w - 2 * fr, 0.8 * u);
      g.fillStyle = B.rgba(PAL.white, 0.25);
      for (let i = 0; i < 160; i++) g.fillRect(fr + r() * (w - 2 * fr), h - fr * 1.6 + r() * fr * 0.4, r.range(0.1, 0.5) * u, r.range(0.1, 0.3) * u);
      [[0.62, PAL.white, 7], [0.7, PAL.yellow, 4.5], [0.75, PAL.pink, 3.5]].forEach(([fx, col, len]) => {
        g.fillStyle = col;
        g.save();
        g.translate(w * fx, h - fr * 1.25);
        g.rotate(-0.08);
        B.roundRect(g, 0, 0, len * u, 1.3 * u, 0.6 * u);
        g.fill();
        g.restore();
      });
      g.fillStyle = PAL.wood;
      g.fillRect(w * 0.18, h - fr * 1.45, 12 * u, 2.4 * u);
      g.fillStyle = "#8d8a84";
      g.fillRect(w * 0.18, h - fr * 1.45 + 2.4 * u, 12 * u, 1.0 * u);
    });
    ctx.drawImage(c, 0, 0);
  }
  /** Dust blotches (cached, low-res): soft irregular patches of alpha. */
  const blotches = (W, H) => B.layer("chalk-blotch", 96, Math.round((96 * H) / W), (g, w, h) => {
    const img = g.createImageData(w, h);
    for (let i = 0; i < w * h; i++) img.data[i * 4 + 3] = 255 * B.clamp(B.fbm((i % w) * 0.09, Math.floor(i / w) * 0.09, 3, 31) * 2.2 - 0.1) ** 1.5;
    g.putImageData(img, 0, 0);
  });
  /** Board-grain speckle mask (cached tile): mostly opaque, with fine holes and horizontal skips. */
  function speckle(ctx) {
    const tile = B.layer("chalk-speckle", 256, 256, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(5);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const streak = B.noise2(x * 0.02, y * 0.45, 3) * 0.5 + B.noise2(x * 0.08, y * 0.08, 8) * 0.3;
          const a = B.clamp(0.72 + (r() - 0.5) * 0.9 + streak * 0.6);
          const i = (y * w + x) * 4;
          d[i] = d[i + 1] = d[i + 2] = 255;
          d[i + 3] = Math.pow(a, 1.4) * 255;
        }
      g.putImageData(img, 0, 0);
    });
    const pat = ctx.createPattern(tile, "repeat"), s = Math.max(1, U / 7);
    pat.setTransform(new DOMMatrix([s, 0, 0, s, 0, 0]));
    return pat;
  }

  // ------------------------------------------------------------------ layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    return {
      F, u, P, S,
      frame: 2.6 * u,
      title: [S.x + 2 * u, S.y + 4 * u],
      head: P ? 11 * u : 10 * u,
      lab: P ? 5.2 * u : 4.8 * u,
      sun: P ? [W * 0.45, H * 0.54, 10 * u] : [W * 0.6, H * 0.6, 10 * u],
      cal: P ? { x: W / 2 - 18 * u, y: H * 0.36, w: 36 * u, h: 38 * u } : { x: S.x + 6 * u, y: H * 0.43, w: 34 * u, h: 38 * u },
      q: P ? [W / 2, H * 0.36 + 49 * u] : [S.x + S.w * 0.6, H * 0.6],
      orbit: P ? [42 * u, 20 * u] : [42 * u, 18 * u],
      num: P ? [W / 2, H * 0.36, 26 * u] : [S.x + S.w * 0.27, H * 0.52, 34 * u],
      sum: P ? [S.x + 6 * u, H * 0.6, 8.5 * u] : [S.x + S.w * 0.57, H * 0.62, 9.5 * u],
      step: P ? 6.6 * u : 6.4 * u, stepGap: 24 * u,
      // the board's sections: the sum stays up (bottom in portrait, right in landscape) while the steps are written
      top: P ? { x: S.x - 2 * u, y: S.y - 3 * u, w: S.w + 4 * u, h: H * 0.555 - S.y - 8 * u } : { x: S.x - 2 * u, y: S.y - 3 * u, w: S.w * 0.52, h: S.h + 4 * u },
      side: P ? { x: S.x - 2 * u, y: H * 0.555, w: S.w + 4 * u, h: H * 0.245 } : { x: S.x + S.w * 0.53, y: S.y - 3 * u, w: S.w * 0.49, h: S.h + 4 * u },
    };
  }

  // ------------------------------------------------------------------ the lesson (the setting: replace it)
  const TITLE = "Why do we have\nleap years?";
  const SUM = "¼ day × 4 years\n= 1 day";
  const QUESTION = "365 days\n... or 366?";
  const ORBIT_NOTE = "1 orbit = 365¼ days";
  const STEPS = ["Calendar year:\n365 days", "¼ day left over\neach year", "Every 4th year:\nadd   Feb 29"];
  const CLOSE = "So the seasons\nstay in step!";
  const STEP_AT = [9.8, 10.65, 11.75]; // each step's text (its number is written down the margin first)
  const STEP_RATE = 52;
  const WIPES = [[5.2, 1.0], [8.8, 0.9], [12.9, 0.65]]; // start, duration: a steady sweep, not a flick

  function lessonTitle(L) {
    const [tx, ty] = L.title, rows = chalkWrite(TITLE, tx, ty + L.head * 0.5, L.head, 0.15, { rate: 24, seed: 3 });
    const r = rows[1];
    if (r) twice([[r.x - U, r.y + L.head * 0.62], [r.x + r.w + 2 * U, r.y + L.head * 0.66]], B.prog(T, 1.45, 0.35), { color: PAL.yellow, w: 0.65 * U, seed: 6 });
    // the day in question and the puzzle (the puzzle, and in portrait the calendar, are rubbed out cleanly)
    const { x, y, w, h } = L.cal, p = (a, d) => B.prog(T, a, d), [qx, qy] = L.q;
    chalkLine(B.rectPts(x, y, w, h), { w: 0.55 * U, p: p(1.6, 0.15), seed: 7 });
    chalkLine([[x, y + h * 0.3], [x + w, y + h * 0.3]], { w: 0.45 * U, p: p(1.75, 0.04), seed: 8 });
    chalkWrite("FEB", x + w / 2, y + h * 0.16, L.lab * 1.1, 1.79, { rate: 30, seed: 9, align: "center", color: PAL.pink });
    chalkWrite("29?", x + w / 2, y + h * 0.66, h * 0.42, 1.88, { rate: 24, seed: 11, align: "center", color: PAL.yellow });
    chalkWrite(QUESTION, qx, qy, L.lab * (L.P ? 1.3 : 2), 2.0, { rate: 48, seed: 12, align: "center", pause: 0.05 });
  }

  function lessonDiagram(L) {
    const u = L.u, P = L.P, [sx, sy, sr] = L.sun, [orx, ory] = L.orbit;
    chalkRing(sx, sy, sr, sr, B.prog(T, 3.0, 0.35), { color: PAL.yellow, w: 0.65 * u, seed: 10 });
    hatchCircle(sx, sy, sr * 0.88, B.prog(T, 3.3, 0.4), { color: PAL.yellow });
    // the orbit: a dashed chalk ellipse, written round
    const orbit = B.arcPts(0, 0, 1, Math.PI * 0.9, Math.PI * 0.9 + B.TAU, 90).map(([x, y]) => [sx + x * orx, sy + y * ory]);
    const op = B.prog(T, 3.45, 0.7);
    for (let i = 0; i < 30; i++) {
      const a = i / 30, b = a + 1 / 60;
      if (a > op) break;
      chalkLine(B.trim(orbit, a, Math.min(b, op)), { w: 0.4 * u, p: 1, seed: 20 + i, alpha: 0.85 });
    }
    // the earth on its orbit, with an arrow showing which way it goes
    const ea = 0.75, ex = sx + Math.cos(ea) * orx, ey = sy + Math.sin(ea) * ory, er = 3.2 * u;
    chalkRing(ex, ey, er, er, B.prog(T, 3.95, 0.25), { color: PAL.blue, w: 0.55 * u, seed: 12 });
    hatchCircle(ex, ey, er * 0.85, B.prog(T, 4.15, 0.25), { color: PAL.blue, gap: 0.9 * u });
    const arc = B.arcPts(0, 0, 1, -1.25, -0.55, 20).map(([x, y]) => [sx + x * orx * 1.12, sy + y * ory * 1.3]);
    chalkArrow(arc, B.prog(T, 4.3, 0.4), { color: PAL.white, w: 0.5 * u, seed: 13 });
    // labels next to their things, in a different colour, joined by short lines
    chalkWrite("Sun", sx - sr - 2 * u - prefixW("Sun", L.lab), sy, L.lab, 3.65, { color: PAL.yellow, rate: 14, seed: 14 });
    chalkWrite("Earth", ex + er + 2.5 * u, ey + 3 * u, L.lab, 4.2, { color: PAL.blue, rate: 14, seed: 15 });
    const lx = P ? L.S.x + 4 * u : sx - orx * 0.6, ly = sy + ory + (P ? 9 : 7) * u;
    chalkWrite(ORBIT_NOTE, lx, ly, L.lab * 1.05, 4.35, { color: PAL.pink, rate: 32, seed: 16 });
    chalkLine([[lx + 12 * u, ly - L.lab * 0.75], [sx + Math.cos(1.95) * orx * 0.97, sy + Math.sin(1.95) * ory * 1.02]], { w: 0.35 * u, p: B.prog(T, 4.2, 0.2), color: PAL.pink, seed: 17 });
  }

  function lessonNumber(L) {
    const u = L.u, [nx, ny, ns] = L.num;
    chalkWrite("365¼", nx, ny, ns, 6.25, { rate: 9, seed: 21, align: "center", color: PAL.white });
    chalkWrite("days in one orbit", nx, ny + ns * 0.74, L.lab * 1.2, 6.7, { rate: 24, seed: 22, align: "center", color: PAL.blue });
    const [sx, sy, ss] = L.sum, rows = chalkWrite(SUM, sx, sy, ss, 7.0, { rate: 24, seed: 23, pause: 0.15 });
    const a = rows[1];
    if (a) {
      const x0 = a.x + prefixW("= ", ss) - u, x1 = a.x + a.w + 2 * u;
      twice([[x0, a.y + ss * 0.6], [x1, a.y + ss * 0.62]], B.prog(T, 8.05, 0.22), { color: PAL.pink, w: 0.6 * u, seed: 24 });
      twice([[x0 + u, a.y + ss * 0.82], [x1 - u, a.y + ss * 0.85]], B.prog(T, 8.22, 0.2), { color: PAL.pink, w: 0.55 * u, seed: 25 });
    }
  }

  /** Steps down the left side like a worked lesson: the numbers go down first, then each line is written and ticked. */
  const stepY = (L, i) => L.S.y + (L.P ? 6 : 4) * L.u + i * L.stepGap;
  function lessonSteps(L) {
    const u = L.u, S = L.S, size = L.step;
    STEPS.forEach((txt, i) => {
      const y = stepY(L, i), x = S.x + 3 * u;
      chalkWrite(`${i + 1}.`, x, y, size, 9.7 + i * 0.1, { rate: 12, seed: 40 + i, color: PAL.yellow });
      const rows = chalkWrite(txt, x + size * 1.3, y, size, STEP_AT[i] + 0.2, { rate: STEP_RATE, seed: 50 + i, pause: 0.12 });
      const r = rows[0], td = writeTime(txt, STEP_RATE, 0.12);
      if (r) tick(r.x + r.w + 4 * u, y, size * 0.7, B.prog(T, STEP_AT[i] + 0.2 + td + 0.05, 0.2));
    });
  }

  function lessonClose(L) {
    const u = L.u, P = L.P, S = L.S, size = L.step;
    // circle "Feb 29" in step 3, then the conclusion where the sum was, then a star in the margin
    const y3 = stepY(L, 2) + size * 1.18, x3 = S.x + 3 * u + size * 1.3, pre = prefixW("add   ", size), fw = prefixW("Feb 29", size);
    chalkRing(x3 + pre + fw / 2, y3, fw * 0.7, size * 0.84, B.prog(T, 12.95, 0.35), { color: PAL.yellow, w: 0.6 * u, seed: 60 });
    const cs = P ? 8.2 * u : 8 * u, cx = P ? S.x + 12 * u : L.side.x + 9 * u, cy = P ? L.F.H * 0.64 : S.y + S.h * 0.4;
    chalkWrite(CLOSE, cx, cy, cs, 13.58, { rate: 34, seed: 61, color: PAL.white, pause: 0.15 });
    star(cx - (P ? 6.5 : 5.5) * u, cy + u, (P ? 3.6 : 2.8) * u, B.prog(T, 14.58, 0.3), PAL.pink);
  }

  // ------------------------------------------------------------------ frame
  function draw(ctx, W, H, t) {
    const L = layout(W, H), S = L.S;
    U = L.u;
    T = t;
    board(ctx, W, H, L);
    CH = B.scratch("chalk-layer", W, H);
    // a section stays on the board until it is wiped (leaving a ghost); later writing goes on after its wipe
    const wp = (i) => B.prog(t, WIPES[i][0], WIPES[i][1], "inOutSine"), wipes = [];
    let rub = null;
    if (t < WIPES[0][0] + WIPES[0][1]) {
      lessonTitle(L);
      const c = L.cal, r = L.P ? { x: c.x - 12 * U, y: c.y + 5 * U, w: c.w + 24 * U, h: c.h + 25 * U } : { x: L.S.x + L.S.w * 0.4, y: c.y + 5 * U, w: L.S.w * 0.6, h: c.h - 3 * U };
      rub = wipe(r, B.prog(t, 2.67, 0.3, "inOutSine"), 0); // rubbed clean: no ghost, no smear
      if (t >= BEATS[1]) lessonDiagram(L);
    }
    wipes.push(wipe({ x: S.x - 2 * U, y: S.y - 3 * U, w: S.w + 4 * U, h: S.h + 5 * U }, wp(0), 0.06));
    if (t >= BEATS[2] && t < WIPES[2][0] + WIPES[2][1]) lessonNumber(L);
    wipes.push(wipe(L.top, wp(1), 0.012)); // rubbed hard: list text goes over this patch
    if (t >= BEATS[3]) lessonSteps(L);
    wipes.push(wipe(L.side, wp(2), 0.05));
    if (t >= BEATS[5]) lessonClose(L);
    // the board shows the wiper's smear; the chalk breaks up on the board grain; dust hazes round heavy strokes
    wipes.forEach((w) => smear(ctx, w));
    CH.save();
    CH.globalCompositeOperation = "destination-in";
    CH.fillStyle = speckle(CH);
    CH.fillRect(0, 0, W, H);
    CH.restore();
    // dust: a wide blurred copy of the chalk kept only in irregular blotches, so it smudges unevenly, never as an outline
    const D = B.scratch("chalk-dust", W, H);
    D.filter = `blur(${(2.2 * U).toFixed(1)}px)`;
    D.drawImage(CH.canvas, 0, 0);
    D.filter = "none";
    D.globalCompositeOperation = "destination-in";
    D.drawImage(blotches(W, H), 0, 0, W, H);
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    ctx.globalAlpha = 0.6;
    ctx.drawImage(D.canvas, 0, 0);
    ctx.restore();
    ctx.globalAlpha = 0.93;
    ctx.drawImage(CH.canvas, 0, 0);
    ctx.globalAlpha = 1;
    wipes.concat(rub).forEach((w) => eraser(ctx, w));
    B.vignette(ctx, W, H, { amount: 0.35, inner: 0.5 });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12 });
  }

  // ------------------------------------------------------------------ sound: scratchy chalk at hand speed, taps, felt wipes, a knock for the answer
  SOUND.define("chalk-tap", (v) => {
    // the stick tapping the board: a dry, hard little knock
    v.noise({ filter: "bandpass", f: 1900, q: 3, a: 0.0005, len: 0.025, peak: 0.4 });
    v.tone({ f: 420, f2: 300, glide: 0.03, a: 0.0008, len: 0.04, peak: 0.12 });
  }, { verb: 0.2 });
  SOUND.define("chalk-wipe", (v, o) => {
    // felt eraser: soft broadband rub that swells and fades with each pass
    const d = o.dur ?? 0.4;
    v.noise({ filter: "bandpass", f: 700, f2: 1100, glide: d, q: 0.6, a: d * 0.3, hold: d * 0.4, len: d * 0.3, peak: 0.22, brown: true });
    v.noise({ filter: "highpass", f: 2500, a: d * 0.3, hold: d * 0.3, len: d * 0.3, peak: 0.04 });
  }, { verb: 0.15 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.7 });
    const write = (at, str, rate, o = {}) => k.at(at, "chalk", { dur: writeTime(str, rate), gain: o.gain ?? 0.9, pitch: o.pitch ?? 0 });
    k.at(0.1, "chalk-tap", { gain: 0.6 });
    write(0.15, TITLE, 24);
    k.at(1.45, "chalk", { dur: 0.35, gain: 0.8, pitch: 3 });
    k.at(1.6, "chalk", { dur: 0.4, gain: 0.7, pitch: 1 });
    write(2.0, QUESTION, 48, { gain: 0.6, pitch: 2 });
    k.at(2.67, "chalk-wipe", { dur: 0.3 });
    k.at(3.0, "chalk", { dur: 0.35, pitch: -2 }).at(3.3, "chalk", { dur: 0.4, gain: 0.6, pitch: 4 });
    k.at(3.45, "chalk", { dur: 0.7, gain: 0.6, pitch: 1 });
    k.at(3.65, "chalk", { dur: 0.25, gain: 0.7, pitch: 2 }).at(3.95, "chalk", { dur: 0.45, pitch: 3 });
    k.at(4.2, "chalk", { dur: 0.35, gain: 0.7 }).at(4.3, "chalk", { dur: 0.4, gain: 0.6, pitch: -1 });
    write(4.35, ORBIT_NOTE, 32, { gain: 0.7, pitch: 2 });
    WIPES.forEach(([a, d]) => { for (let i = 0; i < 3; i++) k.at(a + (i * d) / 3, "chalk-wipe", { dur: d / 3 + 0.08, gain: 1.0, pitch: i % 2 }); });
    write(6.25, "365¼", 9, { pitch: -3 });
    write(6.7, "days in one orbit", 24, { gain: 0.6, pitch: 3 });
    write(7.0, SUM, 24);
    k.at(8.05, "chalk", { dur: 0.22, pitch: 5 }).at(8.22, "chalk", { dur: 0.2, pitch: 6 }).at(8.3, "knock", { gain: 0.6 });
    [0, 1, 2].forEach((i) => k.at(9.7 + i * 0.1, "chalk-tap", { gain: 0.5, pitch: i }));
    STEPS.forEach((s, i) => {
      write(STEP_AT[i] + 0.2, s, STEP_RATE, { gain: 0.8, pitch: i });
      k.at(STEP_AT[i] + 0.2 + writeTime(s, STEP_RATE, 0.12) + 0.05, "chalk", { dur: 0.2, pitch: 7, gain: 0.8 });
    });
    k.at(12.95, "chalk", { dur: 0.35, pitch: 4 });
    write(13.58, CLOSE, 34, { gain: 0.8 });
    k.at(14.58, "chalk", { dur: 0.3, pitch: 6 }).at(14.88, "chalk-tap").at(14.9, "knock", { gain: 0.5 });
  }

  Player.register({
    id: "chalkboard",
    name: "Chalkboard Lesson",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Kalam:wght@700&family=Patrick+Hand&display=swap",
      faces: ['700 20px "Kalam"', '400 20px "Patrick Hand"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [2.62, 5.1, 8.6, 11.72, 12.88, 14.95],
    draw,
    score,
  });
})();
