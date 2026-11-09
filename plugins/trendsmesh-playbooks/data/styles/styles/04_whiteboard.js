/* 04 Marker Whiteboard - reference animation.
 * Topic (setting, replace it): "How does a heat pump heat a home?" - moving heat in from cold outside air.
 * Rendering (keep it): one big glossy board the camera glides across (four areas, an aluminium frame and a marker
 * tray at its edges); faint ghosts of old lessons left in streaks by an eraser; chisel-tip marker strokes whose width
 * follows their direction, with a lighter wet middle, darker edges, ink density that drifts, dry streaks where the
 * tip skipped and small pools where it lands and lifts; wobbly boxes traced twice, quick open arrowheads, hand
 * printing written letter by letter; four marker colours with fixed meanings (black structure, blue headings, red
 * loops and problems, green results); a hand holding the marker follows the tip; a felt eraser scrubs to clear.
 * Finishing: soft ceiling-light reflections over everything, ink included, and a dimmer lower board.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    board: "#f8f9fb",
    black: "#1f2226",
    blue: "#1f4fb5",
    red: "#d1302f",
    green: "#1f8f4a",
    ghost: "#c9ccd2",
    frame: "#b8bcc2",
  };
  const PRINT = "Gochi Hand", NEAT = "Architects Daughter";
  const DUR = 14;
  const BEATS = [0, 2.25, 5.35, 8.15, 10.6, 11.95];
  const GLIDES = [[2.25, 2.9, 0, 1], [5.35, 6.0, 1, 2], [8.15, 8.8, 2, 3]]; // camera moves between board areas
  const ERASE = [11.95, 12.5];
  let T = 0;

  // ------------------------------------------------------------------ marker helpers (reuse these)
  /**
   * One chisel-tip marker stroke along pts, revealed to p. The ribbon's width follows the stroke's direction
   * against the tilted chisel; its middle is a touch lighter (wet) and its edges darker (ink gathers); it pools
   * where the tip lands and lifts; some strokes skip, leaving thin dry streaks along their length.
   */
  function markerStroke(g, pts, p, color, w, seed) {
    if (p <= 0 || pts.length < 2) return;
    const dense = B.densify(pts, Math.max(2, w * 0.6)), part = p >= 1 ? dense : B.trim(dense, 0, p);
    if (part.length < 2) return;
    const chisel = B.deg(-38), left = [], right = [];
    for (let i = 0; i < part.length; i++) {
      const a = part[Math.max(0, i - 1)], b = part[Math.min(part.length - 1, i + 1)], ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      const wv = w * (0.5 + 0.5 * Math.abs(Math.sin(ang - chisel)));
      const nx = -Math.sin(ang), ny = Math.cos(ang);
      left.push([part[i][0] + (nx * wv) / 2, part[i][1] + (ny * wv) / 2]);
      right.push([part[i][0] - (nx * wv) / 2, part[i][1] - (ny * wv) / 2]);
    }
    g.save();
    g.lineJoin = "round";
    g.beginPath();
    B.poly(g, left.concat(right.reverse()), true);
    g.fillStyle = B.mix(color, "#ffffff", 0.2);
    g.fill();
    g.strokeStyle = B.shade(color, -0.12);
    g.lineWidth = Math.max(1, w * 0.24);
    g.stroke();
    g.fillStyle = B.rgba(B.shade(color, -0.25), 0.55); // pools at landing and lifting
    g.beginPath();
    B.circle(g, part[0][0], part[0][1], w * 0.42);
    if (p >= 1) B.circle(g, part[part.length - 1][0], part[part.length - 1][1], w * 0.38);
    g.fill();
    if (B.hash01(seed, "dry") < 0.45 && B.pathLength(part) > w * 12) {
      // the tip skipped: two thin dry streaks along a stretch of the stroke
      const a0 = 0.25 + 0.4 * B.hash01(seed, "a"), seg = B.trim(part, a0, a0 + 0.25);
      g.globalCompositeOperation = "destination-out";
      g.lineWidth = Math.max(0.8, w * 0.1);
      g.setLineDash([w * 1.4, w * 0.6]);
      [-0.22, 0.2].forEach((off) => {
        g.beginPath();
        B.poly(g, B.wobble(seg, { amp: w * 0.05, seed }).map((q, i, arr) => {
          const b = arr[Math.min(arr.length - 1, i + 1)], a = arr[Math.max(0, i - 1)], ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
          return [q[0] - Math.sin(ang) * off * w, q[1] + Math.cos(ang) * off * w];
        }));
        g.strokeStyle = "rgba(0,0,0,0.75)";
        g.stroke();
      });
    }
    g.restore();
  }
  /** Hand printing written letter by letter: each letter wanders a little in size, angle and baseline. */
  function markerText(g, it, p) {
    const n = it.str.replace(/\n/g, "").length, shown = Math.floor(p * n + 1e-6);
    if (shown <= 0) return null;
    const lines = it.str.split("\n");
    g.save();
    g.font = B.font(it.size, it.font || PRINT, 400);
    g.textBaseline = "alphabetic";
    g.textAlign = "left";
    g.lineJoin = "round";
    let k = 0, tip = null;
    lines.forEach((line, li) => {
      const lw = g.measureText(line).width;
      let x = it.align === "left" ? it.x : it.x - lw / 2;
      const y = it.y + (li - (lines.length - 1) / 2) * it.size * 1.12 + it.size * 0.32;
      for (let i = 0; i < line.length; i++, k++) {
        const ch = line[i], cw = g.measureText(ch).width;
        if (k < shown) {
          const h1 = B.hash01(it.seed, k, "y"), h2 = B.hash01(it.seed, k, "r"), h3 = B.hash01(it.seed, k, "s");
          g.save();
          g.translate(x + cw / 2, y + (h1 - 0.5) * it.size * 0.09);
          g.rotate((h2 - 0.5) * 0.12);
          g.scale(0.93 + h3 * 0.14, 0.93 + h3 * 0.14);
          g.fillStyle = B.mix(it.color, "#ffffff", 0.12);
          g.fillText(ch, -cw / 2, 0);
          g.strokeStyle = it.color;
          g.lineWidth = Math.max(1, it.size * 0.035);
          g.strokeText(ch, -cw / 2, 0);
          g.restore();
          tip = [x + cw, y - it.size * 0.2];
        }
        x += cw;
      }
    });
    g.restore();
    return tip;
  }
  /** Wobbly hand-drawn box: corners overshoot, the start and end don't quite meet. */
  function boxPts(x, y, w, h, seed) {
    const r = B.rng("box" + seed), o = Math.min(w, h) * 0.06;
    const pts = [[x - o * r.range(0.3, 1), y + o * 0.2], [x + w + o * r.range(0.4, 1.2), y - o * 0.25], [x + w - o * 0.1, y + h + o * r.range(0.3, 1)], [x - o * 0.3, y + h + o * 0.1], [x + o * 0.2, y - o * r.range(0.6, 1.2)]];
    return B.wobble(B.densify(pts, Math.max(w, h) / 12), { amp: o * 0.35, freq: 0.6, seed });
  }
  /** Hand-drawn ellipse that overshoots its start. */
  function ringPts(cx, cy, rx, ry, seed, turns = 1.1) {
    const out = [], a0 = -2.2;
    for (let i = 0; i <= 64; i++) {
      const a = a0 + (i / 64) * B.TAU * turns, k = 1 + 0.04 * B.noise1(i * 0.2, seed) + 0.03 * (i / 64);
      out.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    return out;
  }
  /** Arrow: one slightly curved stroke, then a quick open head of two short strokes. */
  function arrowPolys(pts, head) {
    const tip = B.pointAt(pts, 1), a = tip[2];
    const h1 = [[tip[0] + Math.cos(a + 2.55) * head, tip[1] + Math.sin(a + 2.55) * head], [tip[0], tip[1]]];
    const h2 = [[tip[0], tip[1]], [tip[0] + Math.cos(a - 2.6) * head * 0.9, tip[1] + Math.sin(a - 2.6) * head * 0.9]];
    return [pts, h1, h2];
  }
  
  // ------------------------------------------------------------------ the board: four areas of one big board
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    return { F, u, P, W, H, area: [[0, 0], [W, 0], [W, H], [0, H]], world: [2 * W, 2 * H], stroke: (P ? 1.0 : 0.85) * u };
  }
  /** The lesson as a list of timed marker items (times depend only on the script, not the frame size). */
  const planCache = new Map();
  function plan(L) {
    const key = L.W + "x" + L.H;
    if (planCache.has(key)) return planCache.get(key);
    const { W, H, P, u } = L, items = [];
    let t = 0;
    const at = (k) => (x, y) => [x + L.area[k][0], y + L.area[k][1]];
    const draw = (k, polys, color, dur, o = {}) => {
      const it = { kind: "draw", polys: polys.map((pp) => pp.map((q) => at(k)(q[0], q[1]))), color, dur, w: (o.w ?? 1) * L.stroke, seed: items.length + 1, layer: o.layer ?? 0 };
      it.at = o.at ?? t;
      t = it.at + dur + (o.gap ?? 0.07);
      items.push(it);
      return it;
    };
    const write = (k, str, x, y, size, color, o = {}) => {
      const [wx, wy] = at(k)(x, y), dur = str.replace(/\n/g, "").length * (o.cps ?? 0.022);
      const it = { kind: "text", str, x: wx, y: wy, size, color, font: o.font, align: o.align, dur, seed: items.length + 7, layer: o.layer ?? 0 };
      it.at = o.at ?? t;
      t = it.at + dur + (o.gap ?? 0.07);
      items.push(it);
      return it;
    };

    // ---- A. title, a little house doodle with heat inside, then the title underlined twice
    t = 0.05;
    {
      const ts = P ? 10.5 * u : 8.5 * u, cx = P ? W / 2 : 0.36 * W, y1 = P ? 0.24 * H : 0.38 * H, y2 = y1 + ts * 1.1;
      write(0, "How a heat pump", cx, y1, ts, PAL.blue);
      write(0, "heats your home", cx, y2, ts, PAL.blue);
      const hx = P ? W / 2 : 0.8 * W, hy = P ? 0.62 * H : 0.56 * H, hw = P ? 0.27 * W : 0.11 * W, hh = P ? 0.15 * H : 0.15 * H;
      draw(0, [boxPts(hx - hw, hy - hh, 2 * hw, 2 * hh, 5)], PAL.black, 0.3);
      draw(0, [[[hx - hw * 1.2, hy - hh + 0.5 * u], [hx, hy - hh - hw * (P ? 0.6 : 0.85)], [hx + hw * 1.22, hy - hh + 0.3 * u]]], PAL.black, 0.18);
      draw(0, [-0.45, 0, 0.45].map((k) => Array.from({ length: 9 }, (_, i) => [hx + k * hw + Math.sin(i * 1.4) * 1.1 * u, hy + hh * 0.6 - (i / 8) * hh * 1.1])), PAL.red, 0.2);
      const uy = y2 + ts * 0.75, uw = P ? 0.36 * W : 0.27 * W;
      draw(0, [B.wobble(B.densify([[cx - uw, uy], [cx + uw, uy - 0.3 * u]], 20), { amp: 0.25 * u, seed: 3 })], PAL.black, 0.2, { gap: 0.03 });
      draw(0, [B.wobble(B.densify([[cx - uw * 0.9, uy + 1.3 * u], [cx + uw * 0.95, uy + 1.1 * u]], 20), { amp: 0.25 * u, seed: 4 })], PAL.black, 0.15);
    }
    // ---- B. diagram: outdoor unit -> house, labelled, the heat arrow traced twice
    t = 2.85;
    {
      const unit = P ? [0.3 * W, 0.66 * H, 0.2 * W, 0.065 * H] : [0.22 * W, 0.6 * H, 0.12 * W, 0.13 * H]; // cx, cy, half w, half h
      const house = P ? [0.62 * W, 0.37 * H, 0.24 * W, 0.075 * H] : [0.72 * W, 0.56 * H, 0.15 * W, 0.15 * H];
      draw(1, [boxPts(unit[0] - unit[2], unit[1] - unit[3], 2 * unit[2], 2 * unit[3], 11)], PAL.black, 0.22);
      const fr = unit[3] * 0.62, fc = [unit[0] - unit[2] * 0.35, unit[1]];
      draw(1, [ringPts(fc[0], fc[1], fr, fr, 12, 1.05), [[fc[0] - fr * 0.7, fc[1] - fr * 0.3], [fc[0] + fr * 0.7, fc[1] + fr * 0.3]], [[fc[0] - fr * 0.3, fc[1] + fr * 0.7], [fc[0] + fr * 0.3, fc[1] - fr * 0.7]]], PAL.black, 0.15);
      write(1, "outside 0°C", unit[0], unit[1] + unit[3] + (P ? 5 : 6) * u, P ? 6 * u : 5 * u, PAL.black, { font: NEAT });
      draw(1, [boxPts(house[0] - house[2], house[1] - house[3], 2 * house[2], 2 * house[3], 13), [[house[0] - house[2] * 1.18, house[1] - house[3] + 0.4 * u], [house[0], house[1] - house[3] - house[2] * 0.75], [house[0] + house[2] * 1.2, house[1] - house[3] + 0.2 * u]]], PAL.black, 0.32);
      write(1, "inside 21°C", house[0], house[1] + (P ? 0.5 : 1) * u, P ? 6 * u : 5 * u, PAL.black, { font: NEAT });
      const a0 = P ? [unit[0] + unit[2] * 0.7, unit[1] - unit[3] - 2 * u] : [unit[0] + unit[2] + 2.5 * u, unit[1] - 2 * u];
      const a1 = P ? [house[0] - house[2] * 0.4, house[1] + house[3] + 3 * u] : [house[0] - house[2] - 2.5 * u, house[1] - 1 * u];
      const shaft = B.arcBetween(a0[0], a0[1], a1[0], a1[1], P ? -0.18 : -0.2, 30);
      draw(1, arrowPolys(shaft, 3.4 * u), PAL.blue, 0.28, { w: 1.25, gap: 0.03 });
      draw(1, [B.wobble(shaft, { amp: 0.5 * u, seed: 9 }).slice(4)], PAL.blue, 0.14, { w: 1.1 });
      const mid = B.pointAt(shaft, 0.5);
      write(1, "heat", mid[0] + (P ? 11 : 0) * u, mid[1] + (P ? 1 : -6) * u, P ? 7.5 * u : 6 * u, PAL.blue);
      const sf = [unit[0] + unit[2] + 5 * u, unit[1] - unit[3] - 3 * u], sr = 3.2 * u; // the cold outside, by the unit
      draw(1, [0, 1, 2].map((i) => { const a = (i * Math.PI) / 3 + 0.2; return [[sf[0] - Math.cos(a) * sr, sf[1] - Math.sin(a) * sr], [sf[0] + Math.cos(a) * sr, sf[1] + Math.sin(a) * sr]]; }), PAL.blue, 0.15, { w: 0.7 });
    }
    // ---- C. the key number: a guess of x1 scribbled out, rewritten as x3, circled in green
    t = 5.95;
    {
      write(2, "1 kWh of power gives", W / 2, P ? 0.21 * H : 0.17 * H, P ? 6.4 * u : 5.4 * u, PAL.black, { font: NEAT, cps: 0.012 });
      const g1 = P ? [0.24 * W, 0.68 * H] : [0.24 * W, 0.47 * H], gs = P ? 12 * u : 10 * u;
      write(2, "×1?", g1[0], g1[1], gs, PAL.blue);
      // wrong: two hard red slashes, the guess still readable under them
      draw(2, [-0.12, 0.14].map((d) => [[g1[0] - gs * 0.75, g1[1] + gs * (0.25 + d)], [g1[0] + gs * 0.8, g1[1] - gs * (0.55 - d)]]), PAL.red, 0.2, { w: 1.3 });
      const n3 = P ? [W / 2, 0.42 * H] : [0.58 * W, 0.47 * H], ns = P ? 30 * u : 28 * u;
      write(2, "×3", n3[0], n3[1], ns, PAL.blue, { gap: 0.05 });
      L.n3 = n3;
      L.ns = ns;
      draw(2, [ringPts(n3[0], n3[1] - ns * 0.05, ns * 0.85, ns * 0.62, 21, 1.12)], PAL.green, 0.3, { w: 1.2 });
      write(2, P ? "about 3 kWh\nof heat!" : "about 3 kWh of heat!", P ? 0.66 * W : W / 2, P ? 0.68 * H : 0.82 * H, P ? 8 * u : 5.6 * u, PAL.green);
    }
    // ---- D. the cycle: three boxed steps on a red looped arrow
    t = 8.75;
    {
      const bs = P ? [[W / 2, 0.24 * H, 0.3 * W, 0.055 * H], [0.73 * W, 0.6 * H, 0.19 * W, 0.055 * H], [0.27 * W, 0.6 * H, 0.19 * W, 0.055 * H]]
        : [[W / 2, 0.21 * H, 0.17 * W, 0.1 * H], [0.79 * W, 0.62 * H, 0.15 * W, 0.1 * H], [0.21 * W, 0.62 * H, 0.15 * W, 0.1 * H]];
      const texts = ["1 Soak up\noutside heat", "2 Squeeze it:\nit gets hot", "3 Let the heat\nout inside"];
      const arcs = P ? [
        B.quad(bs[0][0] + bs[0][2] + 1 * u, bs[0][1], 0.92 * W, 0.4 * H, bs[1][0] + 4 * u, bs[1][1] - bs[1][3] - 2 * u),
        B.quad(bs[1][0], bs[1][1] + bs[1][3] + 2 * u, W / 2, 0.76 * H, bs[2][0], bs[2][1] + bs[2][3] + 2 * u),
        B.quad(bs[2][0] - 4 * u, bs[2][1] - bs[2][3] - 2 * u, 0.08 * W, 0.4 * H, bs[0][0] - bs[0][2] - 1 * u, bs[0][1]),
      ] : [
        B.quad(bs[0][0] + bs[0][2] + 1 * u, bs[0][1], 0.79 * W, 0.22 * H, bs[1][0], bs[1][1] - bs[1][3] - 2 * u),
        B.quad(bs[1][0] - bs[1][2] - 1 * u, bs[1][1] + 2 * u, W / 2, 0.88 * H, bs[2][0] + bs[2][2] + 1 * u, bs[2][1] + 2 * u),
        B.quad(bs[2][0], bs[2][1] - bs[2][3] - 2 * u, 0.21 * W, 0.22 * H, bs[0][0] - bs[0][2] - 1 * u, bs[0][1]),
      ];
      // the three boxes first (the layout of the board), then each step written in and looped on
      bs.forEach((b, i) => draw(3, [boxPts(b[0] - b[2], b[1] - b[3], 2 * b[2], 2 * b[3], 30 + i)], PAL.black, 0.14, { gap: 0.05 }));
      bs.forEach((b, i) => {
        write(3, texts[i], b[0], b[1], P ? 5 * u : 4.6 * u, i === 0 ? PAL.blue : PAL.black, { font: NEAT, gap: 0.05, cps: 0.016 });
        draw(3, arrowPolys(arcs[i], 3 * u), PAL.red, 0.18, { w: 1.15, gap: 0.05 });
      });
      write(3, "and round\nagain", W / 2, P ? 0.44 * H : 0.5 * H, P ? 6 * u : 5 * u, PAL.red, { gap: 0.05 });
    }
    // ---- close (after the eraser): the one line to remember, and a green check
    t = 12.55;
    {
      write(3, P ? "It moves heat,\nit doesn't\nmake it" : "It moves heat,\nit doesn't make it", W / 2, P ? 0.36 * H : 0.4 * H, P ? 11 * u : 8 * u, PAL.blue, { layer: 1 });
      const c = [W / 2, P ? 0.6 * H : 0.72 * H], s = P ? 10 * u : 6 * u;
      draw(3, [[[c[0] - s, c[1] - s * 0.1], [c[0] - s * 0.3, c[1] + s * 0.6], [c[0] + s * 1.1, c[1] - s * 0.9]]], PAL.green, 0.16, { w: 1.4, layer: 1 });
    }
    // the eraser's passes over area D (rows, back and forth)
    const er = [], rows = 6, top = P ? 0.17 * H : 0.1 * H, bot = P ? 0.8 * H : 0.9 * H;
    for (let i = 0; i < rows; i++) {
      const y = B.lerp(top, bot, (i + 0.5) / rows), dir = i % 2 ? -1 : 1;
      er.push({ y: y + L.area[3][1], x0: (dir > 0 ? 0.08 * W : 0.92 * W) + L.area[3][0], x1: (dir > 0 ? 0.92 * W : 0.08 * W) + L.area[3][0], at: B.lerp(ERASE[0], ERASE[1], i / rows), dur: (ERASE[1] - ERASE[0]) / rows });
    }
    const res = { items, erase: { passes: er, h: ((bot - top) / rows) * 1.25 }, n3: L.n3, ns: L.ns };
    planCache.set(key, res);
    return res;
  }

  // ------------------------------------------------------------------ board textures (cached, world space at half resolution)
  function boardLayer(L) {
    const [ww, wh] = L.world, s = 0.5;
    return B.layer("wb-board", ww * s, wh * s, (g, w, h) => {
      const u = L.u * s;
      g.fillStyle = PAL.board;
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: 0.05, feature: 0.35, seed: 4, mode: "multiply" }); // old cleaner, very faint
      // ghosts of earlier lessons: words, boxes, arrows; then broken up by streaky eraser passes. The words are
      // texture (nobody is meant to read them), and the places today's lesson goes were wiped clean first.
      const gc = B.canvas(w, h), gg = gc.getContext("2d"), r = B.rng("ghosts");
      gg.strokeStyle = gg.fillStyle = PAL.ghost;
      gg.lineCap = "round";
      const words = ["Q2 targets", "x = 4", "budget", "phase 1", "f(x)", "team", "ideas!", "ratio 2:1", "step 3", "why?", "launch", "notes"];
      for (let i = 0; i < 26; i++) {
        const x = r() * w, y = r() * h;
        gg.lineWidth = r.range(0.4, 0.8) * u;
        if (i % 3 === 0) {
          gg.font = B.font(r.range(4, 8) * u, PRINT, 400);
          const word = r.pick(words);
          B.texture(gg, () => gg.fillText(word, x, y));
        } else if (i % 3 === 1) {
          gg.beginPath();
          B.poly(gg, boxPts(x, y, r.range(15, 35) * u, r.range(8, 16) * u, i), false);
          gg.stroke();
        } else {
          gg.beginPath();
          B.poly(gg, B.arcBetween(x, y, x + r.range(-30, 30) * u, y + r.range(-20, 20) * u, 0.2), false);
          gg.stroke();
        }
      }
      gg.globalCompositeOperation = "destination-out";
      for (let i = 0; i < 40; i++) {
        const y = r() * h, x = r() * w;
        gg.fillStyle = `rgba(0,0,0,${r.range(0.55, 1)})`;
        gg.save();
        gg.translate(x, y);
        gg.rotate(r.range(-0.15, 0.15));
        gg.fillRect(-r.range(20, 60) * u, -r.range(3, 7) * u, r.range(40, 120) * u, r.range(6, 14) * u);
        gg.restore();
      }
      gg.fillStyle = "#000";
      for (const it of plan(L).items) {
        let bx;
        if (it.kind === "text") {
          gg.font = B.font(it.size * s, it.font || PRINT, 400);
          const ls = it.str.split("\n"), tw = Math.max(...ls.map((l) => gg.measureText(l).width)), th = ls.length * it.size * 1.12 * s;
          bx = [it.align === "left" ? it.x * s : it.x * s - tw / 2, it.y * s - th / 2, tw, th];
        } else {
          const xs = it.polys.flat().map((q) => q[0] * s), ys = it.polys.flat().map((q) => q[1] * s);
          bx = [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)];
        }
        gg.fillRect(bx[0] - 3 * u, bx[1] - 3 * u, bx[2] + 6 * u, bx[3] + 6 * u);
      }
      g.globalAlpha = 0.13; // the ghosts darken the board by only about 3 %
      g.drawImage(gc, 0, 0);
      g.globalAlpha = 1;
      // the lower part of the board sits in shadow (about 10 %)
      g.fillStyle = B.linear(g, 0, 0, 0, h, [[0, "rgba(40,45,60,0)"], [0.55, "rgba(40,45,60,0.02)"], [1, "rgba(40,45,60,0.1)"]]);
      g.fillRect(0, 0, w, h);
    });
  }
  /** Ink density drift and eraser streaks: two small tiles used as destination-out patterns. */
  function densityTile() {
    return B.layer("wb-density", 96, 96, (g, w, h) => {
      const img = g.createImageData(w, h);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const v = 0.5 + 0.5 * Math.sin((x / w) * B.TAU * 2 + Math.sin((y / h) * B.TAU) * 1.5) * Math.cos((y / h) * B.TAU * 3 + Math.sin((x / w) * B.TAU * 2));
          img.data[(y * w + x) * 4 + 3] = v * v * 70;
        }
      g.putImageData(img, 0, 0);
    });
  }
  function streakTile() {
    return B.layer("wb-streak", 64, 64, (g, w, h) => {
      const r = B.rng("streak");
      for (let y = 0; y < h; y++) {
        g.fillStyle = `rgba(0,0,0,${(0.985 + 0.015 * r()).toFixed(3)})`;
        g.fillRect(0, y, w, 1);
      }
    });
  }
  /** Aluminium frame inside the world edge, and the marker tray along the bottom (with two markers lying in it). */
  function frameAndTray(ctx, L) {
    const [ww, wh] = L.world, f = 1.5 * L.u;
    ctx.save();
    ctx.lineWidth = f;
    ctx.strokeStyle = B.linear(ctx, 0, 0, 0, wh, [PAL.frame, "#d9dce0", PAL.frame, "#9da2a9"]);
    ctx.strokeRect(f / 2, f / 2, ww - f, wh - f);
    ctx.lineWidth = Math.max(1, 0.15 * L.u);
    ctx.strokeStyle = "rgba(255,255,255,0.8)";
    ctx.strokeRect(f * 0.25, f * 0.25, ww - f * 0.5, wh - f * 0.5);
    const ty = wh - 3.2 * L.u;
    ctx.fillStyle = B.linear(ctx, 0, ty, 0, wh, ["#d6d9dd", PAL.frame, "#8f949b"]);
    ctx.fillRect(0, ty, ww, 3.2 * L.u);
    [[0.18, PAL.red], [0.24, PAL.green]].forEach(([x, c]) => {
      ctx.fillStyle = "#e9ebee";
      ctx.beginPath();
      B.roundRect(ctx, x * ww, ty - 1.6 * L.u, 12 * L.u, 1.8 * L.u, 0.9 * L.u);
      ctx.fill();
      ctx.fillStyle = c;
      ctx.beginPath();
      B.roundRect(ctx, x * ww + 9.5 * L.u, ty - 1.7 * L.u, 3.2 * L.u, 2 * L.u, 0.8 * L.u);
      ctx.fill();
    });
    ctx.restore();
  }

  // ------------------------------------------------------------------ the hand, the marker, the eraser (objects on the board)
  /** A right hand holding a marker whose tip is at (x, y): drawn offscreen, then cast a soft shadow on the board. */
  function handWithMarker(ctx, x, y, color, u, lift) {
    const size = Math.ceil(46 * u), g = B.scratch("wb-hand", size, size), o = 6 * u;
    const ang = B.deg(52), dx = Math.cos(ang), dy = Math.sin(ang), px = -dy, py = dx;
    const P = (a, b) => [o + (dx * a + px * b) * u, o + (dy * a + py * b) * u];
    g.lineCap = "round";
    // sleeve and wrist
    g.fillStyle = "#e6b493"; // wrist
    g.beginPath();
    B.poly(g, [P(11, -3.2), P(11, 4.6), P(19, 4.2), P(19, -2.6)], true);
    g.fill();
    g.fillStyle = "#56657c"; // sleeve, with a darker cuff
    g.beginPath();
    B.poly(g, [P(18, -3.6), P(18, 5), P(48, 8), P(48, -5.5)], true);
    g.fill();
    g.fillStyle = "#46536a";
    g.beginPath();
    B.poly(g, [P(18, -3.6), P(18, 5), P(20.5, 5.2), P(20.5, -3.8)], true);
    g.fill();
    // marker barrel: white body, coloured cap at the back, coloured tip
    g.fillStyle = "#eef0f2";
    g.beginPath();
    B.poly(g, [P(1.6, -1.1), P(1.6, 1.1), P(15, 1.35), P(15, -1.35)], true);
    g.fill();
    g.strokeStyle = "#b9bdc4";
    g.lineWidth = 0.25 * u;
    g.stroke();
    g.fillStyle = color;
    g.beginPath();
    B.poly(g, [P(0, -0.45), P(0, 0.45), P(1.7, 0.8), P(1.7, -0.8)], true);
    g.fill();
    g.beginPath();
    B.poly(g, [P(13.2, -1.45), P(13.2, 1.45), P(17, 1.45), P(17, -1.45)], true);
    g.fill();
    // the hand: palm, three fingers wrapped round the barrel, the thumb along its top
    const skin = "#e6b493", fold = "#cf9776";
    g.fillStyle = skin;
    g.beginPath();
    const pc = P(9.4, 1.6);
    g.ellipse(pc[0], pc[1], 5.2 * u, 4.4 * u, ang, 0, B.TAU);
    g.fill();
    for (let i = 0; i < 3; i++) {
      const a = P(4.6 + i * 2.1, -1.9), b = P(5.4 + i * 2.1, 2.8);
      g.strokeStyle = skin;
      g.lineWidth = 2.3 * u;
      g.beginPath();
      g.moveTo(a[0], a[1]);
      g.lineTo(b[0], b[1]);
      g.stroke();
      g.strokeStyle = fold;
      g.lineWidth = 0.25 * u;
      g.beginPath();
      const m = P(5.75 + i * 2.1, 0.6), n = P(6.1 + i * 2.1, 3.0);
      g.moveTo(m[0], m[1]);
      g.lineTo(n[0], n[1]);
      g.stroke();
    }
    g.strokeStyle = skin;
    g.lineWidth = 1.9 * u;
    g.beginPath();
    const t0 = P(3.8, -1.9), t1 = P(10.5, -3.6);
    g.moveTo(t0[0], t0[1]);
    g.lineTo(t1[0], t1[1]);
    g.stroke();
    ctx.save();
    ctx.shadowColor = "rgba(20,25,40,0.22)";
    ctx.shadowBlur = 2.5 * u * (1 + lift);
    ctx.shadowOffsetX = (1.6 + 2 * lift) * u;
    ctx.shadowOffsetY = (2.4 + 3 * lift) * u;
    ctx.drawImage(g.canvas, x - o - lift * 0.6 * u, y - o - lift * 1.2 * u);
    ctx.restore();
  }
  function eraserBlock(ctx, x, y, u) {
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowColor = "rgba(20,25,40,0.25)";
    ctx.shadowBlur = 3 * u;
    ctx.shadowOffsetX = 1.5 * u;
    ctx.shadowOffsetY = 2.5 * u;
    ctx.fillStyle = "#3b4049";
    ctx.beginPath();
    B.roundRect(ctx, -5.5 * u, -12 * u, 11 * u, 24 * u, 2 * u);
    ctx.fill();
    ctx.shadowColor = "rgba(0,0,0,0)";
    ctx.fillStyle = "#5a616d";
    ctx.beginPath();
    B.roundRect(ctx, -4.2 * u, -10.5 * u, 8.4 * u, 21 * u, 1.6 * u);
    ctx.fill();
    ctx.fillStyle = PAL.blue;
    ctx.fillRect(-4.2 * u, -2 * u, 8.4 * u, 4 * u);
    ctx.restore();
  }

  // ------------------------------------------------------------------ camera
  function camera(L, t) {
    let k = 0;
    for (const [a, b] of GLIDES) k += B.span(t, a, b, "inOutSine");
    const i = Math.min(2, Math.floor(k)), f = k - i, A = L.area[i], Bq = L.area[i + 1];
    const cx = B.lerp(A[0], Bq[0], f) + L.W / 2 + B.noise1(t * 0.2, 1) * 0.6 * L.u, cy = B.lerp(A[1], Bq[1], f) + L.H / 2 + B.noise1(t * 0.17, 2) * 0.6 * L.u;
    // a slight push-in on the key number; a pull-back at the end that shows the frame and the tray
    const zoom = 1 + 0.04 * B.span(t, 7.2, 8.0, "inOutSine") * (1 - B.span(t, 8.1, 8.6)) + 0.03 * B.span(t, 13.0, 14, "inOutSine");
    return { cx, cy, zoom };
  }
  const camMatrix = (L, cam) => [cam.zoom, 0, 0, cam.zoom, L.W / 2 - cam.cx * cam.zoom, L.H / 2 - cam.cy * cam.zoom];

  // ------------------------------------------------------------------ frame
  function draw(ctx, W, H, t) {
    T = t;
    const L = layout(W, H), pl = plan(L), u = L.u, cam = camera(L, t), M = camMatrix(L, cam);
    const view = { x: cam.cx - W / (2 * cam.zoom), y: cam.cy - H / (2 * cam.zoom), w: W / cam.zoom, h: H / cam.zoom };
    // board, ghosts, frame and tray (world space)
    ctx.fillStyle = "#cfccc4"; // the wall round the board (seen when the camera pulls back)
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(...M);
    ctx.save();
    ctx.shadowColor = "rgba(30,30,30,0.35)";
    ctx.shadowBlur = 3 * u;
    ctx.shadowOffsetY = 1.5 * u;
    ctx.fillStyle = PAL.board;
    ctx.fillRect(0, 0, L.world[0], L.world[1]);
    ctx.restore();
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(boardLayer(L), 0, 0, L.world[0], L.world[1]);
    frameAndTray(ctx, L);
    // live ink on its own layer: items before the eraser, the eraser's streaky clearing, then items after it
    const I = B.scratch("wb-ink", W, H);
    I.setTransform(...M);
    let tip = null, active = null, last = null, next = null;
    const near = (it) => {
      const x = it.kind === "text" ? it.x : it.polys[0][0][0], y = it.kind === "text" ? it.y : it.polys[0][0][1];
      return x > view.x - W && x < view.x + view.w + W && y > view.y - H && y < view.y + view.h + H;
    };
    const drawItem = (it) => {
      const p = B.prog(t, it.at, it.dur);
      if (p <= 0) {
        if (!next || it.at < next.at) next = it;
        return;
      }
      if (p >= 1 && (!last || it.at > last.at)) last = it;
      if (!near(it)) return;
      if (it.kind === "text") {
        // wiped words are only faint smears (texture)
        const tp = t > ERASE[1] && it.layer === 0 && it.x < W && it.y > H ? B.texture(I, () => markerText(I, it, p)) : markerText(I, it, p);
        if (p < 1) (active = it), (tip = tp);
      } else {
        const lens = it.polys.map((pp) => B.pathLength(pp)), tot = lens.reduce((a, b) => a + b, 0);
        let rem = p * tot;
        it.polys.forEach((pp, j) => {
          const q = B.clamp(rem / (lens[j] || 1));
          rem -= lens[j];
          if (q > 0) {
            markerStroke(I, pp, q, it.color, it.w, it.seed * 10 + j);
            if (p < 1 && q < 1) {
              active = it;
              tip = B.pointAt(pp, q);
            }
          }
        });
      }
    };
    pl.items.filter((it) => it.layer === 0).forEach(drawItem);
    const E = pl.erase;
    if (t > ERASE[0]) {
      I.save();
      I.globalCompositeOperation = "destination-out";
      const pat = I.createPattern(streakTile(), "repeat");
      pat.setTransform(new DOMMatrix([u * 0.4, 0, 0, u * 0.4, 0, 0]));
      I.fillStyle = pat;
      for (const ps of E.passes) {
        const k = B.prog(t, ps.at, ps.dur, "inOutSine");
        if (k <= 0) continue;
        const xe = B.lerp(ps.x0, ps.x1, k), x0 = Math.min(ps.x0, xe) - 0.1 * W, x1 = Math.max(ps.x0, xe) + 0.1 * W;
        I.fillRect(x0, ps.y - E.h / 2, x1 - x0, E.h);
      }
      I.restore();
    }
    pl.items.filter((it) => it.layer === 1).forEach(drawItem);
    // ink density drifts across the strokes (anchored to the board, so it does not swim)
    I.save();
    I.globalCompositeOperation = "destination-out";
    const dp = I.createPattern(densityTile(), "repeat");
    dp.setTransform(new DOMMatrix([u * 0.3, 0, 0, u * 0.3, 0, 0]));
    I.fillStyle = dp;
    I.fillRect(view.x, view.y, view.w, view.h);
    I.restore();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(I.canvas, 0, 0);
    ctx.restore();
    // the eraser block scrubbing back and forth
    const toScreen = (q) => [M[0] * q[0] + M[4], M[3] * q[1] + M[5]];
    if (t > ERASE[0] - 0.25 && t < ERASE[1] + 0.3) {
      let pos = null;
      for (const ps of E.passes) if (t >= ps.at - 0.001) pos = [B.lerp(ps.x0, ps.x1, B.prog(t, ps.at, ps.dur, "inOutSine")), ps.y];
      const first = E.passes[0], lastP = E.passes[E.passes.length - 1];
      if (t < ERASE[0]) pos = [B.lerp(first.x0 - 0.3 * W, first.x0, B.span(t, ERASE[0] - 0.25, ERASE[0], "outCubic")), first.y];
      if (t > ERASE[1]) pos = [B.lerp(lastP.x1, lastP.x1 - 0.4 * W, B.span(t, ERASE[1], ERASE[1] + 0.3, "inCubic")), lastP.y];
      const sp = toScreen(pos);
      eraserBlock(ctx, sp[0], sp[1] + Math.sin(t * 40) * 0.6 * u, u * cam.zoom * (E.h / (24 * u)));
    }
    // the hand follows the tip; between items it lifts and travels to the next start
    const markerColor = (active || next || last || { color: PAL.black }).color;
    let hp = tip, lift = 0;
    if (!hp) {
      const startOf = (it) => (it.kind === "text" ? [it.x - (it.align === "left" ? 0 : it.size * it.str.split("\n")[0].length * 0.24), it.y] : it.polys[0][0]);
      const endOf = (it) => (it.kind === "text" ? [it.x + it.size * it.str.split("\n").pop().length * (it.align === "left" ? 0.5 : 0.25), it.y + it.size * 0.3] : it.polys[it.polys.length - 1][it.polys[it.polys.length - 1].length - 1]);
      // on a long pause the hand rests just below what it wrote, then travels to the next item; at the end it leaves
      const a = last ? endOf(last) : [view.x + view.w * 1.1, view.y + view.h * 1.1];
      const b = next ? startOf(next) : [a[0] + 1.5 * W, a[1] + 1.5 * H];
      const t0 = last ? last.at + last.dur : 0, t1 = next ? next.at : t0 + 0.35;
      const k = B.span(t, t0, t1, "inOutSine"), farGap = t1 - t0 > 0.5;
      if (farGap) {
        const m = [a[0] + 0.04 * W, a[1] + 0.06 * H], k1 = B.span(t, t0, t0 + 0.35, "outCubic"), k2 = B.span(t, Math.max(t0 + 0.35, t1 - 0.4), t1, "inOutSine");
        hp = k2 > 0 ? [B.lerp(m[0], b[0], k2), B.lerp(m[1], b[1], k2)] : [B.lerp(a[0], m[0], k1), B.lerp(a[1], m[1], k1)];
        lift = k2 > 0 ? 1 - k2 : k1;
      } else {
        hp = [B.lerp(a[0], b[0], k), B.lerp(a[1], b[1], k)];
        lift = Math.sin(Math.PI * k) * 0.5;
      }
      if (t > ERASE[0] - 0.3 && t < ERASE[1]) hp = [view.x + view.w * 1.3, view.y + view.h * 1.2];
    }
    const hs = toScreen(hp);
    if (hs[0] > -20 * u && hs[0] < W + 5 * u && hs[1] > -20 * u && hs[1] < H + 5 * u) handWithMarker(ctx, hs[0], hs[1], markerColor, u * cam.zoom, lift);
    // finishing: soft reflections of ceiling lights over everything (they drift a little as the camera glides)
    const drift = [(cam.cx % W) / W, (cam.cy % H) / H];
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    [[0.28, 0.13, 0.42, 0.045, 0.2], [0.74, 0.09, 0.3, 0.035, 0.16], [0.56, 0.66, 0.5, 0.06, 0.1]].forEach(([x, y, rx, ry, a], i) => {
      const gx = (x - 0.12 * drift[0]) * W, gy = (y - 0.06 * drift[1]) * H;
      ctx.save();
      ctx.translate(gx, gy);
      ctx.rotate(-0.08 + i * 0.05);
      ctx.scale(1, (ry * H) / (rx * W));
      ctx.fillStyle = B.radial(ctx, 0, 0, 0, rx * W, [[0, B.rgba("#ffffff", a)], [0.5, B.rgba("#ffffff", a * 0.45)], [1, "rgba(255,255,255,0)"]]);
      ctx.fillRect(-rx * W, -rx * W, 2 * rx * W, 2 * rx * W);
      ctx.restore();
    });
    ctx.restore();
    B.grain(ctx, W, H, { amount: 0.025, t, fps: 24, mode: "overlay" });
  }

  // ------------------------------------------------------------------ sound: marker squeaks matched to strokes, scribbles for writing, cap clicks, eraser scrubs
  SOUND.define("wb-cap", (v) => {
    // marker cap snapped off / on
    v.noise({ filter: "bandpass", f: 3400, q: 2.5, a: 0.0005, len: 0.018, peak: 0.3 });
    v.tone({ type: "triangle", f: 1400, f2: 1100, glide: 0.02, a: 0.0006, len: 0.03, peak: 0.08 });
    v.noise({ at: 0.045, filter: "bandpass", f: 2600, q: 3, a: 0.0005, len: 0.015, peak: 0.18 });
  }, { verb: 0.1 });
  SOUND.define("wb-erase", (v, o) => {
    // one pass of a felt eraser: a rough, soft, broadband scrub
    const d = o.dur ?? 0.1;
    v.noise({ filter: "bandpass", f: 1100, q: 0.5, a: d * 0.2, hold: d * 0.6, len: d * 0.3, peak: 0.28 });
    v.grains({ span: d, count: 14, filter: "bandpass", f: 2200, q: 0.8, len: 0.012, peak: 0.12 });
  }, { verb: 0.08 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.7 });
    const pl = plan(layout(1080, 1920));
    let prev = null;
    pl.items.forEach((it, i) => {
      if (prev && prev.color !== it.color) k.at(Math.max(prev.at + prev.dur + 0.01, it.at - 0.08), "wb-cap", { gain: 0.6, pan: 0.3 });
      const pan = (B.hash01(i, "pan") - 0.5) * 0.6;
      if (it.kind === "text") k.at(it.at, "scribble", { dur: it.dur, gain: 0.45, pan, pitch: it.size > 150 ? -3 : 0 });
      else k.at(it.at, "marker", { dur: it.dur, gain: 0.55, pan, pitch: (B.hash01(i) - 0.5) * 3 });
      prev = it;
    });
    GLIDES.forEach(([a, b]) => k.at(a, "breath", { dur: b - a + 0.2, gain: 0.35 }));
    // the key moment: a soft classroom bell as the green circle lands
    k.at(7.35, "bell", { note: "E5", gain: 0.35, dur: 1.4 }).at(7.37, "bell", { note: "B5", gain: 0.2, dur: 1.2 });
    pl.erase.passes.forEach((ps) => k.at(ps.at, "wb-erase", { dur: ps.dur, gain: 0.8 }));
    k.at(13.5, "ding", { note: "E6", gain: 0.22 });
  }

  Player.register({
    id: "whiteboard",
    name: "Marker Whiteboard",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Gochi+Hand&family=Architects+Daughter&display=swap",
      faces: ['400 20px "Gochi Hand"', '400 20px "Architects Daughter"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Cycle steps 1-2", "Step 3 + loop", "Erase + close"],
    stills: [2.2, 5.3, 8.1, 10.4, 11.68, 13.9],
    draw,
    score,
  });
})();
