/* 14 Halftone Comic - reference animation.
 * Topic (setting, replace it): "How does a lock know your key?" - the pin tumbler lock.
 * Rendering (keep it): a strip of comic panels on yellowed newsprint; flat yellow / red / blue / orange fills with
 * staggered dot fields, heavy brush-inked outlines that swell and taper (inked twice), white shine streaks and solid
 * black form, all-caps lettering on a white knockout, caption boxes, balloons, jagged bursts, fat yellow arrows.
 * Printing: colour (fills + dots) and black line are drawn on two separate plates; the colour plate lands a few
 * pixels off register and the black is multiplied over it, then the paper ages toward the edges.
 * Motion: spring-in with overshoot, dot fields arriving as a wave, words slamming in one at a time, the view gliding
 * along the strip (widening mid-glide to show gutters), shake + slow push-in on big moments.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { paper: "#f7f0de", ink: "#161311", yellow: "#fdd426", red: "#d92b22", blue: "#2457b8", orange: "#f07a26", white: "#ffffff" };
  const LET = "Luckiest Guy", CAP = "Comic Neue";
  const DUR = 12;
  const BEATS = [0, 2.0, 4.1, 6.2, 8.4, 10.3];

  // ------------------------------------------------------------------ the two printing plates
  // C = colour plate (flat fills, dot fields, white knockouts), I = ink plate (black line, lettering, solid blacks).
  // Every element draws its fill on C and its line on I with the same transform; draw() prints them at the end.
  let C = null, I = null, U = 1, T = 0;
  const both = (fn) => {
    fn(C);
    fn(I);
  };
  function push(x, y, s = 1, r = 0) {
    both((g) => {
      g.save();
      g.translate(x, y);
      if (r) g.rotate(r);
      if (s !== 1) g.scale(s, s);
    });
  }
  const pop = () => both((g) => g.restore());

  // fast integer hash for per-dot wobble (no strings in the hot loop)
  function hh(i, j, s) {
    let h = (Math.imul(i | 0, 0x27d4eb2d) ^ Math.imul(j | 0, 0x165667b1) ^ Math.imul(s | 0, 0x9e3779b1)) | 0;
    h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
    h ^= h >>> 13;
    return (h >>> 0) / 4294967296;
  }
  const bbox = (pts) => {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of pts) {
      x0 = Math.min(x0, x);
      y0 = Math.min(y0, y);
      x1 = Math.max(x1, x);
      y1 = Math.max(y1, y);
    }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  };
  const closed = (pts) => pts.concat([pts[0]]);
  const rectPts = (x, y, w, h) => B.densify([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], Math.max(4, Math.min(w, h) / 6));
  const ellPts = (cx, cy, rx, ry, n = 48) => Array.from({ length: n }, (_, i) => [cx + Math.cos((i / n) * B.TAU) * rx, cy + Math.sin((i / n) * B.TAU) * ry]);

  // ------------------------------------------------------------------ comic-print helpers (reuse these)
  /**
   * Brush ink line: a filled ribbon whose width swells and thins along its length, then a thinner second pass a
   * hair down-right, as if inked twice. pts: a polyline (closed shapes: repeat the first point).
   */
  function inkLine(pts, w, o = {}) {
    const isClosed = !!o.closed;
    B.taperStroke(I, pts, { width: w, color: PAL.ink, taperIn: isClosed ? 0 : 0.12, taperOut: isClosed ? 0 : 0.2, rough: 0.5, roughScale: 5, seed: o.seed ?? 1, p: o.p });
    if (o.twice !== false) {
      I.save();
      I.translate(w * 0.28, w * 0.2);
      B.taperStroke(I, pts, { width: w * 0.42, color: PAL.ink, taperIn: 0.25, taperOut: 0.35, rough: 0.8, roughScale: 4, seed: (o.seed ?? 1) + 9, p: o.p });
      I.restore();
    }
  }
  /**
   * Staggered-grid dot field (every other row shifted half a step), one colour, the screen of the comic page.
   * o: { cell, color, tone (0..1 or fn(x, y)), wave (0..1: dots pop on as a front sweeps across), from ("left" |
   *      "center" | "top"), seed }. Each dot wobbles a hair in size and place so it reads printed, not computed.
   */
  function dotField(g, bx, o) {
    const cell = o.cell ?? 2.1 * U, rowH = cell * 0.866, seed = o.seed ?? 3, toneFn = typeof o.tone === "function" ? o.tone : null;
    const cx = bx.x + bx.w / 2, cy = bx.y + bx.h / 2, maxR = Math.hypot(bx.w, bx.h) / 2;
    g.save();
    g.fillStyle = o.color;
    g.beginPath();
    const rows = Math.ceil(bx.h / rowH) + 2;
    for (let r = -1; r < rows; r++) {
      const y = bx.y + r * rowH, off = r & 1 ? cell / 2 : 0;
      let c = 0;
      for (let x = bx.x - cell + off; x < bx.x + bx.w + cell; x += cell, c++) {
        let tone = toneFn ? toneFn(x, y) : o.tone ?? 0.4;
        if (o.wave != null) {
          const d = o.from === "center" ? Math.hypot(x - cx, y - cy) / maxR : o.from === "top" ? (y - bx.y) / bx.h : (x - bx.x) / bx.w;
          const k = B.clamp((o.wave * 1.35 - d) / 0.35);
          tone *= k <= 0 ? 0 : B.ease.outBack(k, 3);
        }
        if (tone <= 0.02) continue;
        const h1 = hh(c, r, seed), h2 = hh(r, c, seed + 1), h3 = hh(c + 7, r - 3, seed + 2);
        const rad = Math.min(cell * 0.62, cell * 0.5 * Math.sqrt(tone) * (0.9 + 0.2 * h1));
        const px = x + (h2 - 0.5) * cell * 0.12, py = y + (h3 - 0.5) * cell * 0.12;
        g.moveTo(px + rad, py);
        g.arc(px, py, rad, 0, B.TAU);
      }
    }
    g.fill();
    g.restore();
  }
  /** A flat-filled shape with ink outline and optional dot shading clipped inside it. */
  function shape(pts, fill, o = {}) {
    if (fill) {
      C.beginPath();
      B.poly(C, pts, true);
      C.fillStyle = fill;
      C.fill();
    }
    if (o.dots) {
      C.save();
      C.beginPath();
      B.poly(C, pts, true);
      C.clip();
      dotField(C, bbox(pts), o.dots);
      C.restore();
    }
    if (o.ink !== 0) inkLine(closed(pts), o.ink ?? 0.9 * U, { closed: true, seed: o.seed, twice: o.twice });
  }
  /** Sharp white shine streak (a slanted sliver) on the colour plate: comic shine is never a gradient. */
  function shine(x, y, w, h, slant = 0.4) {
    C.beginPath();
    B.poly(C, [[x + slant * h, y], [x + w + slant * h, y], [x + w, y + h], [x, y + h]], true);
    C.fillStyle = PAL.white;
    C.fill();
  }
  /**
   * Comic lettering: all caps, black ink on a thick white knockout that breaks the dots behind. lines: [{ text, size }].
   * Words slam in one at a time from o.at, o.gap apart (big, then hit their place with a small rebound).
   * o: { at, gap 0.12, rot (rad), fill (colour letters for sound effects, e.g. yellow), knock 0.24 (of size) }
   */
  function letters(lines, x, y, o = {}) {
    const gap = o.gap ?? 0.12, at = o.at ?? 0;
    let n = 0, total = lines.reduce((a, l) => a + l.size * 1.02, 0), yy = -total / 2;
    push(x, y, 1, o.rot || 0);
    for (const line of lines) {
      const font = B.font(line.size, LET, 400);
      C.font = I.font = font;
      const words = line.text.toUpperCase().split(" ");
      const ws = words.map((w) => I.measureText(w).width), sp = line.size * 0.28;
      const lw = ws.reduce((a, b) => a + b, 0) + sp * (words.length - 1);
      let xx = o.align === "left" ? 0 : -lw / 2;
      const ly = yy + line.size * 0.55;
      words.forEach((w, i) => {
        const dt = T - (at + n * gap);
        n++;
        const wx = xx + ws[i] / 2;
        xx += ws[i] + sp;
        if (dt < 0) return;
        const s = dt < 0.1 ? B.lerp(1.9, 0.93, Math.pow(dt / 0.1, 2)) : 1 - 0.07 * Math.exp(-14 * (dt - 0.1)) * Math.cos(28 * (dt - 0.1));
        push(wx, ly, s);
        both((g) => {
          g.font = font;
          g.textAlign = "center";
          g.textBaseline = "middle";
          g.lineJoin = "round";
        });
        C.strokeStyle = PAL.white; // the knockout: white outline on the colour plate
        C.lineWidth = line.size * (o.knock ?? 0.24);
        C.strokeText(w, 0, line.size * 0.06);
        C.fillStyle = o.fill || PAL.white;
        C.fillText(w, 0, line.size * 0.06);
        if (o.fill) {
          I.strokeStyle = PAL.ink;
          I.lineWidth = line.size * 0.09;
          I.strokeText(w, 0, line.size * 0.06);
        } else {
          I.fillStyle = PAL.ink;
          I.fillText(w, 0, line.size * 0.06);
        }
        pop();
      });
      yy += line.size * 1.02;
    }
    pop();
  }
  /**
   * Yellow caption box (top-left at x, y), ink border, hand-lettered caps thickened with an ink stroke; the words
   * before a colon are the head, set bigger in the display face. s: pop 0..1. Returns its height.
   */
  function caption(x, y, w, text, size, s = 1, o = {}) {
    if (s <= 0.01) return 0;
    const pad = size * 0.55, c = text.indexOf(":"), head = c > 0 ? text.slice(0, c + 1) : "", body = text.slice(c + 1).trim().toUpperCase();
    const opt = { size, family: CAP, weight: 700, maxW: w - 2 * pad, lineH: 1.12, align: "left", baseline: "top", color: PAL.ink, stroke: PAL.ink, strokeW: size * 0.07 };
    const hh = head ? size * 1.45 : 0, h = hh + B.measureText(I, body, opt).height + 2 * pad;
    push(x + w / 2, y + h / 2, Math.min(s, 1), o.rot || 0); // pops about its centre, never past full size
    shape(rectPts(-w / 2, -h / 2, w, h), o.fill || PAL.yellow, { ink: 0.75 * U, seed: 31 });
    if (head) B.text(I, head.toUpperCase(), pad - w / 2, pad - h / 2, { ...opt, size: size * 1.3, family: LET, weight: 400, stroke: null });
    B.text(I, body, pad - w / 2, pad + hh - h / 2, opt);
    pop();
    return h;
  }
  /** White oval speech balloon with a pointed tail toward (tx, ty); text centred. s: pop scale about the centre. */
  function balloon(cx, cy, rx, ry, tx, ty, text, size, s = 1) {
    if (s <= 0.01) return;
    push(cx, cy, s);
    const a = Math.atan2(ty - cy, tx - cx), n = 56, pts = [];
    for (let i = 0; i <= n; i++) {
      const th = a + 0.22 + (i / n) * (B.TAU - 0.44);
      pts.push([Math.cos(th) * rx, Math.sin(th) * ry]);
    }
    pts.push([(tx - cx) / s, (ty - cy) / s]);
    shape(pts, PAL.white, { ink: 0.85 * U, seed: 41 });
    B.text(I, text.toUpperCase(), 0, 0, { size, family: CAP, weight: 700, maxW: rx * 1.45, lineH: 1.1, color: PAL.ink, stroke: PAL.ink, strokeW: size * 0.07 });
    pop();
  }
  /** Jagged explosion burst (outer fill + inner fill), ink outline. */
  function burst(cx, cy, r, fill, inner, seed, s = 1, spikes = 15) {
    if (s <= 0.01) return;
    const rr = B.rng(seed), pts = [], ins = [];
    for (let i = 0; i < spikes * 2; i++) {
      const a = (i / (spikes * 2)) * B.TAU + rr.range(-0.06, 0.06);
      const k = i % 2 ? rr.range(0.62, 0.74) : rr.range(0.92, 1.12);
      pts.push([Math.cos(a) * r * k, Math.sin(a) * r * k * 0.86]);
      ins.push([Math.cos(a) * r * k * 0.72, Math.sin(a) * r * k * 0.62]);
    }
    push(cx, cy, s);
    shape(pts, fill, { ink: 1.0 * U, seed });
    if (inner) shape(ins, inner, { ink: 0 });
    pop();
  }
  /** Ray sunburst behind a winner, on the colour plate. */
  function sunburst(cx, cy, R, n, color, rot) {
    C.save();
    C.fillStyle = color;
    C.beginPath();
    for (let i = 0; i < n; i++) {
      const a0 = rot + (i / n) * B.TAU, a1 = a0 + (0.5 / n) * B.TAU;
      C.moveTo(cx, cy);
      C.lineTo(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R);
      C.lineTo(cx + Math.cos(a1) * R, cy + Math.sin(a1) * R);
      C.closePath();
    }
    C.fill();
    C.restore();
  }
  /** Short shock / motion lines radiating around a point (ink). */
  function shockLines(cx, cy, r1, r2, n, seed, p = 1) {
    const rr = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU + rr.range(-0.15, 0.15), k = rr.range(0.9, 1.15);
      if (Math.sin(a) > 0.55) continue; // none below the burst, where the caption sits
      inkLine([[cx + Math.cos(a) * r1 * k, cy + Math.sin(a) * r1 * k], [cx + Math.cos(a) * r2 * k, cy + Math.sin(a) * r2 * k]], 0.7 * U, { twice: false, seed: i, p });
    }
  }
  /** Fat curved arrow filled yellow with a heavy ink outline, drawn on tail to head as p goes 0 -> 1. */
  function comicArrow(path, p, w) {
    if (p <= 0.01) return;
    const L = B.pathLength(path), shown = L * p, hl = Math.min(w * 1.7, shown * 0.6);
    const shaft = B.densify(B.trim(path, 0, Math.max(0.001, (shown - hl) / L)), w * 0.5);
    if (shaft.length < 2) return;
    const left = [], right = [];
    shaft.forEach((q, i) => {
      const a = shaft[Math.max(0, i - 1)], b = shaft[Math.min(shaft.length - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const l = Math.hypot(nx, ny) || 1, hw = (w / 2) * (0.6 + 0.4 * Math.min(1, i / 6));
      left.push([q[0] + (nx / l) * hw, q[1] + (ny / l) * hw]);
      right.push([q[0] - (nx / l) * hw, q[1] - (ny / l) * hw]);
    });
    const tip = B.pointAt(path, p), base = shaft[shaft.length - 1], a = tip[2], hw = w * 1.15;
    const nx = -Math.sin(a), ny = Math.cos(a);
    const poly = left.concat([[base[0] + nx * hw, base[1] + ny * hw], [tip[0], tip[1]], [base[0] - nx * hw, base[1] - ny * hw]], right.reverse());
    shape(poly, PAL.yellow, { ink: 0.8 * U, seed: 51, twice: false });
  }
  /** Spring-in scale with a fast overshoot. */
  const spring = (t, at, dur = 0.35) => (t <= at ? 0 : B.ease.outBack(B.prog(t, at, dur), 2.6));

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  /** The hero key: brass-yellow bow and blade, red dot shading on the shadow side, white shine, black form. */
  function heroKey(cx, cy, s, rot, sc = 1) {
    if (sc <= 0.01) return;
    push(cx, cy, sc, rot);
    const blade = [[-1.2 * s, -0.36 * s], [2.6 * s, -0.36 * s], [3.1 * s, 0], [2.6 * s, 0.36 * s], [2.3 * s, 0.36 * s], [2.05 * s, 0.7 * s], [1.8 * s, 0.36 * s],
      [1.45 * s, 0.36 * s], [1.2 * s, 0.62 * s], [0.95 * s, 0.36 * s], [0.6 * s, 0.36 * s], [0.4 * s, 0.75 * s], [0.15 * s, 0.36 * s], [-1.2 * s, 0.36 * s]];
    shape(blade, PAL.yellow, { dots: { color: PAL.red, cell: 1.5 * U, tone: (x, y) => B.clamp((y + 0.05 * s) / (0.6 * s)) * 0.55, seed: 5 }, ink: 1.0 * U, seed: 3 });
    I.fillStyle = PAL.ink; // solid black form under the blade's top edge
    I.fillRect(-0.9 * s, 0.2 * s, 3.3 * s, 0.07 * s);
    shine(-0.8 * s, -0.24 * s, 2.6 * s, 0.1 * s, 0.6);
    const bow = ellPts(-2.1 * s, 0, 1.15 * s, 1.15 * s, 60);
    shape(bow, PAL.yellow, { dots: { color: PAL.red, cell: 1.5 * U, tone: (x, y) => B.clamp((y + 0.2 * s) / (1.2 * s)) * 0.65, seed: 6 }, ink: 1.1 * U, seed: 4 });
    shape(ellPts(-2.45 * s, 0, 0.36 * s, 0.36 * s, 30), PAL.paper, { ink: 0.8 * U, seed: 7, twice: false });
    C.save(); // shine on the bow: a sharp white crescent streak
    C.strokeStyle = PAL.white;
    C.lineWidth = 0.14 * s;
    C.lineCap = "round";
    C.beginPath();
    C.arc(-2.1 * s, 0, 0.85 * s, Math.PI * 1.1, Math.PI * 1.45);
    C.stroke();
    C.restore();
    pop();
  }

  // pin tumbler geometry, in lock units (1 = s px). Shear line at y = 0, keyway from 0.95 to 2.1.
  const PIN_X = [-3, -1, 1, 3], KEY_PIN = [1.2, 1.5, 1.05, 1.35], DRIVER = 1.3, REST = 1.95, TIP_IN = 4.4;
  const RIGHT = KEY_PIN.map((k) => REST - k); // lifts that put every gap exactly on the shear line
  const WRONG = [0.95, 0.2, 0.55, 0.85];
  /** Blade top height (lift) at distance d behind the tip, for a key whose cuts give `lifts` under the pins. */
  function keyLift(d, lifts) {
    if (d > 0 || d < -10.6) return 0;
    let h = Math.min(1.0, -d * 0.9);
    PIN_X.forEach((px, j) => (h = Math.min(h, lifts[j] + 0.9 * Math.abs(d - (px - TIP_IN)))));
    return Math.max(0, h);
  }
  /**
   * Side cutaway of a pin tumbler lock at (cx, cy), unit s. st: { tip (key tip x, null = no key), lifts, line (0..1
   * yellow highlight on the shear line), wiggle (key rotation jitter) }.
   */
  function lockCutaway(cx, cy, s, st) {
    push(cx, cy, 1);
    const R = (x, y, w, h) => rectPts(x * s, y * s, w * s, h * s);
    // housing: orange with red dot shading growing toward the lower right
    shape(R(-5.4, -4.4, 10.8, 7.6), PAL.orange, { dots: { color: PAL.red, cell: 1.6 * U, tone: (x, y) => B.clamp(0.15 + (x / s + y / s + 6) / 20) * 0.6, seed: 8 }, ink: 1.1 * U, seed: 11 });
    // plug, with the shear line along its top
    shape(R(-5.4, 0, 10.2, 2.6), PAL.yellow, { dots: { color: PAL.red, cell: 1.5 * U, tone: (x, y) => B.clamp((y / s - 1.6) / 1.5) * 0.5, seed: 9 }, ink: 0.9 * U, seed: 12 });
    if (st.line > 0) {
      C.fillStyle = B.rgba(PAL.yellow, st.line);
      C.fillRect(-5.4 * s, -0.22 * s, 10.2 * s, 0.44 * s);
    }
    // keyway slot and pin chambers are cut-away cavities: paper with light blue dots
    shape(R(-5.4, 0.95, 10, 1.15), PAL.paper, { dots: { color: PAL.blue, cell: 1.3 * U, tone: 0.18, seed: 10 }, ink: 0.6 * U, seed: 13, twice: false });
    PIN_X.forEach((px, j) => shape(R(px - 0.6, -4.0, 1.2, 4.95), PAL.paper, { dots: { color: PAL.blue, cell: 1.3 * U, tone: 0.18, seed: 20 + j }, ink: 0.6 * U, seed: 14 + j, twice: false }));
    // the key: blade with cuts riding under the pins
    const lifts = PIN_X.map((px) => (st.tip == null ? 0 : keyLift(px - st.tip, st.lifts)));
    if (st.tip != null) {
      push(0, 0, 1, st.wiggle || 0);
      const top = [];
      for (let d = -10.6; d <= 0.0001; d += 0.12) top.push([(st.tip + d) * s, (REST - keyLift(d, st.lifts)) * s]);
      const blade = top.concat([[st.tip * s, 2.08 * s], [(st.tip - 10.6) * s, 2.08 * s]]);
      shape(blade, PAL.yellow, { dots: { color: PAL.red, cell: 1.3 * U, tone: 0.35, seed: 15 }, ink: 0.8 * U, seed: 16 });
      shape(rectPts((st.tip - 12.4) * s, 0.4 * s, 1.9 * s, 2.3 * s), PAL.yellow, { dots: { color: PAL.red, cell: 1.5 * U, tone: 0.45, seed: 17 }, ink: 1.0 * U, seed: 18 });
      pop();
    }
    // pins: key pin (red, pointed foot) and driver pin (blue), with the spring above
    PIN_X.forEach((px, j) => {
      const foot = REST - lifts[j], gapY = foot - KEY_PIN[j], top = gapY - DRIVER;
      const kp = [[(px - 0.45) * s, gapY * s], [(px + 0.45) * s, gapY * s], [(px + 0.45) * s, (foot - 0.3) * s], [px * s, foot * s], [(px - 0.45) * s, (foot - 0.3) * s]];
      shape(kp, PAL.red, { ink: 0.6 * U, seed: 60 + j, twice: false });
      shape(rectPts((px - 0.45) * s, top * s, 0.9 * s, DRIVER * s), PAL.blue, { ink: 0.6 * U, seed: 70 + j, twice: false });
      shine((px - 0.32) * s, (top + 0.12) * s, 0.12 * s, (DRIVER - 0.3) * s, 0);
      const coil = [];
      for (let k = 0; k <= 12; k++) coil.push([(px + (k % 2 ? 0.38 : -0.38)) * s, B.lerp(-4.0, top, k / 12) * s]);
      inkLine(coil, 0.45 * U, { twice: false, seed: 80 + j });
    });
    // the shear line itself
    I.save();
    I.strokeStyle = PAL.ink;
    I.lineWidth = 0.45 * U;
    I.setLineDash([1.2 * U, 0.9 * U]);
    I.beginPath();
    I.moveTo(-5.4 * s, 0);
    I.lineTo(4.8 * s, 0);
    I.stroke();
    I.restore();
    pop();
    return lifts;
  }
  /** End view inset: housing ring, plug turning by angle, a driver pin that blocks or clears. */
  function endView(cx, cy, r, angle, blocked) {
    shape(ellPts(cx, cy, r, r, 56), PAL.orange, { dots: { color: PAL.red, cell: 1.5 * U, tone: 0.4, seed: 90 }, ink: 1.0 * U, seed: 91 });
    push(cx, cy, 1, angle);
    shape(ellPts(0, 0, r * 0.66, r * 0.66, 48), PAL.yellow, { ink: 0.9 * U, seed: 92 });
    shape(rectPts(-r * 0.08, -r * 0.1, r * 0.16, r * 0.6), PAL.paper, { ink: 0.5 * U, seed: 93, twice: false });
    pop();
    // driver pin: dips into the plug when blocked, sits above the line when clear
    const py = blocked ? -r * 0.84 : -r * 1.02;
    shape(rectPts(cx - r * 0.1, cy + py, r * 0.2, r * 0.3), PAL.blue, { ink: 0.5 * U, seed: 94, twice: false });
  }

  // ------------------------------------------------------------------ the panels (each drawn in frame coordinates)
  function panelBox(F, bg, dots) {
    const x = F.W * 0.03, y = F.H * 0.03, w = F.W * 0.94, h = F.H * 0.94;
    C.fillStyle = bg;
    C.fillRect(x, y, w, h);
    if (dots) {
      C.save();
      C.beginPath();
      C.rect(x, y, w, h);
      C.clip();
      dotField(C, { x, y, w, h }, dots);
      C.restore();
    }
    return { x, y, w, h };
  }
  function panelBorder(box) {
    inkLine(closed(rectPts(box.x, box.y, box.w, box.h)), 1.5 * U, { closed: true, seed: 99, twice: false });
  }

  function panelTitle(F, t) {
    const P = F.portrait, S = F.safe;
    const box = panelBox(F, PAL.paper, { color: PAL.blue, tone: (x, y) => 0.12 + 0.5 * B.clamp((y - S.y) / (F.H * 0.9)), wave: B.prog(t, 0, 0.7), seed: 1 });
    const kc = P ? [F.W * 0.5, F.H * 0.62] : [F.W * 0.71, F.H * 0.58];
    sunburst(kc[0], kc[1], P ? F.H * 0.36 : F.W * 0.4, 18, B.rgba(PAL.yellow, 0.9), t * 0.12);
    heroKey(kc[0], kc[1], P ? 9.5 * U : 7.2 * U, -0.32 + B.bob(t, 0.03, 2.4), spring(t, 0.15, 0.45));
    letters([{ text: "How does a lock", size: P ? 7 * U : 6 * U }, { text: "know your key?", size: P ? 10.5 * U : 8.6 * U }], P ? F.W * 0.5 : F.W * 0.33, P ? F.H * 0.34 : F.H * 0.48, { at: 0.35, gap: 0.12, rot: -0.06 });
    caption(S.x, S.y, P ? F.W * 0.62 : F.W * 0.34, "This issue: the pin tumbler lock", P ? 4 * U : 3.9 * U, spring(t, 0.15));
  }

  function lockLayout(F) {
    const P = F.portrait;
    return P ? { cx: F.W * 0.47, cy: F.H * 0.5, s: 6.0 * U } : { cx: F.W * 0.44, cy: F.H * 0.56, s: 6.6 * U };
  }

  function panelDiagram(F, t) {
    const P = F.portrait, S = F.safe, lt = t - BEATS[1];
    const box = panelBox(F, PAL.paper, { color: PAL.blue, tone: 0.1, seed: 2 });
    const L = lockLayout(F);
    push(L.cx, L.cy, spring(lt, 0.0, 0.4) || 0.0001);
    lockCutaway(0, 0, L.s, { tip: null, lifts: RIGHT, line: 0 });
    pop();
    caption(S.x, S.y, P ? F.W * 0.88 : F.W * 0.42, "Inside: springs push stacks of pins down", P ? 4 * U : 3.9 * U, spring(lt, 0.25));
    // tags for the two kinds of pin, each with an ink leader to the first pin stack
    const tag = (x, y, txt, fill, at, py) => {
      const tw = (P ? 30 : 28) * U, h = caption(x, y, tw, txt, P ? 4 * U : 3.9 * U, spring(lt, at), { fill });
      if (!h || lt < at + 0.2) return;
      const a = P ? [x + tw * 0.6, y + (y < py ? h : 0)] : [x + tw, y + h / 2], b = [L.cx - 3 * L.s, py];
      I.strokeStyle = PAL.ink;
      I.lineWidth = 0.6 * U;
      I.beginPath();
      B.poly(I, P ? [a, [L.cx - 4.2 * L.s, a[1]], [L.cx - 4.2 * L.s, py], b] : [a, b]); // portrait: down beside the chamber, not through the spring
      I.stroke();
      I.beginPath();
      B.circle(I, b[0], b[1], 0.9 * U);
      I.fill();
    };
    tag(P ? S.x : S.x + U, P ? F.H * 0.235 : F.H * 0.3, "Driver pins", "#cfdcf5", 0.55, L.cy + 0.1 * L.s);
    tag(P ? S.x : S.x + U, P ? F.H * 0.67 : F.H * 0.66, "Key pins", "#f6cdc5", 0.7, L.cy + 1.35 * L.s);
    // fat yellow arrow from its caption to the shear line (the plug's top edge), landing just outside the lock
    const cw = (P ? 36 : 26) * U, lx = S.r - 3 * U - cw / 2, ly = P ? F.H * 0.735 : F.H * 0.74;
    const tx = L.cx + 5.8 * L.s, ty = L.cy;
    comicArrow(B.quad(lx, ly, tx + (P ? 10 : 7) * U, P ? B.lerp(ly, ty, 0.5) : ty + 3 * U, tx, ty), B.prog(lt, 0.8, 0.45, "outCubic"), (P ? 3.6 : 3.4) * U);
    caption(lx - cw / 2, ly, cw, "The shear line!", P ? 4 * U : 3.9 * U, spring(lt, 1.15));
  }

  function panelNumber(F, t) {
    const P = F.portrait, S = F.safe, lt = t - BEATS[2];
    const box = panelBox(F, PAL.yellow, { color: PAL.red, tone: (x, y) => 0.15 + 0.5 * B.clamp(Math.hypot(x - F.cx, y - F.cy) / (F.H * 0.55)), wave: B.prog(lt, 0, 0.6), from: "center", seed: 4 });
    const bc = [F.W * 0.5, P ? F.H * 0.45 : F.H * 0.42], r = P ? 36 * U : 25 * U;
    sunburst(bc[0], bc[1], r * 2.2, 22, B.rgba(PAL.orange, 0.85), -t * 0.08);
    burst(bc[0], bc[1], r, PAL.red, PAL.yellow, 7, spring(lt, 0.1, 0.4));
    if (lt > 0.12) shockLines(bc[0], bc[1], r * (P ? 1.04 : 1.12), r * (P ? 1.16 : 1.3), 14, 3, B.prog(lt, 0.15, 0.2));
    const k = B.prog(lt, 0.25, 0.75);
    if (lt > 0.2) letters([{ text: B.counter(k, 4000), size: P ? 16 * U : 12.5 * U }], bc[0], bc[1] - (P ? 2 : 1.5) * U, { at: BEATS[2] + 0.2, rot: -0.07 });
    letters([{ text: "years!", size: P ? 8 * U : 6 * U }], bc[0] + 4 * U, bc[1] + (P ? 13 : 10) * U, { at: BEATS[2] + 1.05, rot: -0.07 });
    const ch = P ? F.W * 0.68 : F.W * 0.62; // portrait: two even lines
    caption(F.W * 0.5 - ch / 2, P ? F.H * 0.685 : S.b - 13 * U, ch, "Pin locks are that old: ancient Egypt made them from wood", P ? 4 * U : 3.9 * U, spring(lt, 1.1));
  }

  function panelWrong(F, t) {
    const P = F.portrait, S = F.safe, lt = t - BEATS[3];
    const box = panelBox(F, PAL.paper, { color: PAL.blue, tone: 0.16, wave: B.prog(lt, -0.2, 0.5), seed: 5 });
    const L = lockLayout(F);
    const tip = B.lerp(-16, TIP_IN, B.prog(lt, 0.2, 0.9, "outCubic"));
    const jam = lt > 1.25 ? Math.sin((lt - 1.25) * 40) * 0.012 * Math.exp(-(lt - 1.25) * 4) : 0;
    push(P ? F.W * 0.57 : L.cx, L.cy, P ? 0.88 : 1); // portrait: smaller, so the key's bow stays inside the panel
    lockCutaway(0, 0, L.s, { tip, lifts: WRONG, line: 0, wiggle: jam });
    pop();
    caption(S.x, S.y, P ? F.W * 0.6 : F.W * 0.45, "1. Wrong key: the pins stop at the wrong heights", P ? 4 * U : 3.9 * U, spring(lt, 0.1));
    const bc = P ? [F.W * 0.5, F.H * 0.71] : [L.cx + 7.2 * L.s, L.cy - 4.6 * L.s];
    burst(bc[0], bc[1], (P ? 24 : 20) * U, PAL.red, PAL.yellow, 12, spring(lt, 1.2, 0.3));
    letters([{ text: "Stuck!", size: P ? 7.5 * U : 5.2 * U }], bc[0], bc[1], { at: BEATS[3] + 1.25, rot: 0.08 });
  }

  function panelRight(F, t) {
    const P = F.portrait, S = F.safe, lt = t - BEATS[4];
    const box = panelBox(F, PAL.paper, { color: PAL.blue, tone: 0.16, wave: B.prog(lt, -0.2, 0.5), seed: 6 });
    const L = lockLayout(F);
    const Ly = P ? F.H * 0.43 : L.cy, Lx = P ? F.W * 0.57 : F.W * 0.38;
    const tip = B.lerp(-16, TIP_IN, B.prog(lt, 0.1, 0.7, "inOutCubic"));
    const aligned = B.prog(lt, 0.8, 0.2);
    push(Lx, Ly, P ? 0.88 : 0.82);
    lockCutaway(0, 0, L.s, { tip, lifts: RIGHT, line: aligned });
    pop();
    caption(S.x, S.y, P ? F.W * 0.8 : F.W * 0.48, "2. Right key: every gap meets the shear line", P ? 4 * U : 3.9 * U, spring(lt, 0.1));
    letters([{ text: "Zip!", size: (P ? 9 : 7) * U }], Lx - (P ? 7.7 : 7) * L.s * (P ? 0.88 : 0.82), Ly + 4.4 * L.s * (P ? 0.88 : 0.82), { at: BEATS[4] + 0.3, rot: -0.12, fill: PAL.yellow });
    // 3. the plug turns: end view inset with a winner's sunburst and a CLICK
    const ec = P ? [F.W * 0.64, F.H * 0.68] : [F.W * 0.82, F.H * 0.56], er = (P ? 14 : 10) * U;
    const turn = B.prog(lt, 1.1, 0.35, "outBack");
    if (lt > 0.9) {
      sunburst(ec[0], ec[1], er * 2.6, 16, B.rgba(PAL.yellow, B.prog(lt, 1.1, 0.2)), t * 0.2);
      push(ec[0], ec[1], spring(lt, 0.9, 0.3));
      endView(0, 0, er, turn * Math.PI * 0.5, false);
      pop();
      caption(P ? S.x : S.r - F.W * 0.28 - 4 * U, P ? F.H * 0.7 : S.b - 16 * U, F.W * (P ? 0.37 : 0.28), "3. Unlocked: the plug turns", P ? 4 * U : 3.9 * U, spring(lt, 1.0));
      letters([{ text: "Click!", size: P ? 8 * U : 6 * U }], ec[0] + er * 0.9, ec[1] - er * 1.25, { at: BEATS[4] + 1.15, rot: 0.1, fill: PAL.red });
    }
  }

  function panelClose(F, t) {
    const P = F.portrait, S = F.safe, lt = t - BEATS[5];
    const box = panelBox(F, PAL.yellow, { color: PAL.red, tone: (x, y) => 0.12 + 0.45 * B.clamp(Math.hypot(x - F.cx, y - F.cy) / (F.H * 0.6)), seed: 8 });
    const kc = P ? [F.W * 0.5, F.H * 0.6] : [F.W * 0.66, F.H * 0.58];
    sunburst(kc[0], kc[1], F.H * (P ? 0.4 : 0.8), 20, B.rgba(PAL.orange, 0.9), t * 0.1);
    heroKey(kc[0], kc[1], P ? 8.5 * U : 6.5 * U, -0.25, spring(lt, 0.05, 0.4));
    const bx = P ? F.W * 0.5 : F.W * 0.3, by = P ? F.H * 0.33 : F.H * 0.36;
    balloon(bx, by, (P ? 36 : 27) * U, (P ? 10 : 9) * U, kc[0] - (P ? 6 : 10) * U, kc[1] - 8 * U, "Right heights, right key. That's the whole secret!", P ? 4.2 * U : 3.9 * U, spring(lt, 0.3));
    caption(S.r - F.W * (P ? 0.34 : 0.2), P ? F.H * 0.71 : S.b - 9 * U, F.W * (P ? 0.28 : 0.16), "The end", P ? 4 * U : 3.9 * U, spring(lt, 0.9));
  }

  const PANELS = [panelTitle, panelDiagram, panelNumber, panelWrong, panelRight, panelClose];

  // ------------------------------------------------------------------ camera along the strip
  function camera(F, t) {
    let idx = 0, dip = 0;
    for (let i = 1; i < BEATS.length; i++) {
      const g = B.span(t, BEATS[i] - 0.4, BEATS[i] + 0.3, "inOutCubic");
      idx += g;
      dip = Math.max(dip, Math.sin(Math.PI * g));
    }
    // widen mid-glide so gutters and neighbouring panels show; slow push-ins on the big moments
    let zoom = 1 - 0.17 * dip;
    zoom += 0.06 * B.span(t, 4.2, 6.0, "inOutSine") * (1 - B.span(t, 5.85, 6.2));
    zoom += 0.05 * B.span(t, 9.5, 10.0, "inOutSine") * (1 - B.span(t, 10.0, 10.3));
    // short shakes
    let sh = 0;
    for (const [at, amp] of [[4.25, 1.6], [7.45, 1.2], [9.55, 1.0]]) sh += amp * Math.max(0, 1 - Math.abs(t - at - 0.12) / 0.25);
    const [dx, dy] = B.shake(t, sh * F.u, 5, 22);
    return { idx, zoom, dx, dy };
  }

  // ------------------------------------------------------------------ frame: draw both plates, then print them
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    U = F.u;
    T = t;
    C = B.scratch("comic-colour", W, H);
    I = B.scratch("comic-ink", W, H);
    const cam = camera(F, t);
    const step = F.portrait ? [0, H] : [W, 0];
    const vx = cam.idx * step[0] + W / 2, vy = cam.idx * step[1] + H / 2;
    both((g) => g.setTransform(cam.zoom, 0, 0, cam.zoom, W / 2 + cam.dx - vx * cam.zoom, H / 2 + cam.dy - vy * cam.zoom));
    PANELS.forEach((panel, i) => {
      if (Math.abs(i - cam.idx) > 1.25) return;
      push(i * step[0], i * step[1]);
      const bx = [W * 0.03, H * 0.03, W * 0.94, H * 0.94];
      both((g) => {
        g.save();
        g.beginPath();
        g.rect(...bx);
        g.clip(); // nothing spills out of a panel into the gutter
      });
      panel(F, t);
      pop();
      panelBorder({ x: bx[0], y: bx[1], w: bx[2], h: bx[3] });
      pop();
    });
    // print: newsprint, then the colour plate a few px off register, then the black multiplied over it
    B.paper(ctx, W, H, { color: PAL.paper, seed: 14, mottle: 0.1, fibers: 0.5, specks: 0.25, tooth: 0.07 });
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.drawImage(C.canvas, 0.6 * U, -0.4 * U);
    ctx.drawImage(I.canvas, 0, 0);
    ctx.restore();
    // ageing: yellower and darker toward the edges, a faint broad blotchy tone, fine fibre noise
    B.vignette(ctx, W, H, { color: "#b9893a", amount: 0.32, inner: 0.35, mode: "multiply" });
    B.mottle(ctx, W, H, { amount: 0.12, feature: 0.3, seed: 21, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.06, t, fps: 12, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: thwacks for lettering, thud + crash for bursts, zips, page slides, dry clicks
  SOUND.define("comic-thwack", (v) => {
    // short punchy slap: a low knock with a bright crack on top
    v.tone({ f: 190, f2: 90, glide: 0.06, a: 0.001, len: 0.09, peak: 0.55 });
    v.noise({ filter: "bandpass", f: 1800, q: 0.9, a: 0.0006, len: 0.05, peak: 0.45 });
  }, { verb: 0.12 });
  SOUND.define("comic-zip", (v) => {
    // quick low zip for things whipping on
    v.noise({ filter: "bandpass", q: 4, f: 260, f2: 1400, glide: 0.16, a: 0.01, len: 0.15, peak: 0.45 });
    v.tone({ type: "sawtooth", f: 90, f2: 260, glide: 0.16, a: 0.01, len: 0.14, peak: 0.05 });
  }, { verb: 0.1 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.6 });
    // title: dots wave in, key springs, words slam
    k.at(0.0, "comic-zip", { gain: 0.6 }).at(0.15, "comic-zip", { pitch: 3 });
    k.repeat(0.35, 0.12, 6, "comic-thwack", { vary: 1.5, gain: 0.8 });
    k.at(0.15, "pop", { gain: 0.5 });
    // glides along the strip: a soft paper slide
    BEATS.slice(1).forEach((b) => k.at(b - 0.4, "paper", { dur: 0.7, gain: 0.7 }));
    // diagram
    k.at(2.0, "thud", { gain: 0.5 }).at(2.25, "comic-thwack", { gain: 0.6 }).at(2.55, "pop").at(2.7, "pop", { pitch: 2 });
    k.at(2.8, "comic-zip").at(3.15, "comic-thwack", { pitch: 2 });
    // the number: thud + crash, flipping counter clicks, a thwack on "YEARS!"
    k.at(4.2, "impact", { gain: 0.9 }).at(4.2, "crumple", { dur: 0.3, gain: 0.5 });
    k.repeat(4.35, 0.06, 12, "tick", { gain: 0.5, vary: 1 });
    k.at(5.15, "comic-thwack", { gain: 0.9 }).at(5.4, "pop");
    // wrong key: slides in, rattles, STUCK burst
    k.at(6.4, "comic-zip", { pitch: -3 }).repeat(6.55, 0.17, 4, "knock", { gain: 0.35, vary: 2 });
    k.at(7.4, "impact").at(7.45, "error", { gain: 0.5 }).repeat(7.45, 0.05, 4, "comic-thwack", { gain: 0.35, pitch: -4 });
    // right key: zip in, pins click to the line, plug turns: CLICK
    k.at(8.5, "comic-zip", { pitch: 2 }).repeat(8.6, 0.14, 4, "tick", { gain: 0.6, pitch: -6, vary: 1 });
    k.at(9.2, "chime", { note: "A5", gain: 0.25 }).at(9.3, "pop").at(9.4, "comic-thwack");
    k.at(9.5, "click", { gain: 1 }).at(9.55, "thud", { gain: 0.7 }).at(9.55, "comic-thwack", { pitch: 3 }).at(9.6, "sparkle", { gain: 0.3 });
    // close
    k.at(10.35, "pop").at(10.6, "comic-thwack", { pitch: 1 }).at(11.2, "comic-thwack", { pitch: -1, gain: 0.7 });
  }

  Player.register({
    id: "halftone-comic",
    name: "Halftone Comic",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Luckiest+Guy&family=Comic+Neue:wght@700&display=swap",
      faces: ['400 20px "Luckiest Guy"', '700 20px "Comic Neue"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Wrong key", "Right key", "Close"],
    draw,
    score,
  });
})();
