/* 37 Memphis Pop - reference animation.
 * Topic (setting, replace it): "Why does popcorn pop?" - steam pressure in a kernel.
 * Rendering (keep it): early-80s Memphis maximalism on a flat pastel ground. Every shape gets a hard offset shadow in
 * a second colour (no blur, ever), a flat fill printed a hair off its outline, and a thick black outline. Stock shapes
 * (half circles, wedges, triangles, arches, cylinders, blobs), pattern fills (stripes, polka dots, checker, squiggles,
 * terrazzo flecks), scattered ornament (squiggles, zigzags, plus signs, dot grids, rings, confetti), clashing colours
 * on purpose, chunky Lilita One words each in its own colour with an offset shadow, small Rubik Mono One labels on
 * stripy banners, numbered stickers, chunky block arrows. Finishing: barely-there paper grain.
 * Motion: on twos (every frame held for two at 24 fps, so moves look stepped and cheerful); pop-ins overshoot with a
 * squash and stretch; squiggles and zigzags trace on; idle shapes jiggle, spin or bob; confetti bursts and falls;
 * scene changes are a wide polka-dot band swiping across with the next scene behind it.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { mint: "#9fe3c8", pink: "#ff5fa2", yellow: "#ffd23f", turq: "#2fc4d9", violet: "#7b4fd0", red: "#f0452e", ink: "#141414", cream: "#fff6e0" };
  const BRIGHT = [PAL.pink, PAL.yellow, PAL.turq, PAL.violet, PAL.red, PAL.mint];
  const CHUNK = "Lilita One", MONO = "Rubik Mono One";
  const DUR = 12;
  const BEATS = [0, 2.0, 4.2, 6.4, 8.6, 10.3];
  const SWIPES = [2.0, 4.2, 6.4, 10.3]; // the band covers the frame centre at these times
  let U = 1, T = 0, F = null, ctx = null;
  const PL = (portrait, landscape) => (F.portrait ? portrait : landscape);

  // ------------------------------------------------------------------ Memphis shape kit (reuse these)
  /**
   * The core of the look: hard shadow (the same path offset down-right, in a second colour), the flat fill shifted a
   * hair off register, an optional pattern clipped inside, then a thick black outline on top.
   * path(c) adds the shape; o: { shadow colour, off (shadow offset), pattern, patColor, line (outline width) }.
   */
  function shape(path, fill, o = {}) {
    const off = o.off ?? 1.1 * U, lw = o.line ?? 0.85 * U;
    ctx.save();
    ctx.translate(off, off);
    ctx.beginPath();
    path(ctx);
    ctx.fillStyle = o.shadow || PAL.ink;
    ctx.fill();
    ctx.restore();
    if (o.union) { // a union of overlapping parts: outline drawn first at double width, the fill hides the inner lines
      ctx.beginPath();
      path(ctx);
      ctx.lineWidth = lw * 2;
      ctx.lineJoin = "round";
      ctx.strokeStyle = PAL.ink;
      ctx.stroke();
    }
    ctx.save();
    ctx.translate(0.3 * U, -0.25 * U); // print offset: the colour lands a little off its line
    ctx.beginPath();
    path(ctx);
    ctx.fillStyle = fill;
    ctx.fill();
    if (o.pattern) {
      ctx.clip();
      pattern(o.pattern, o.patColor || PAL.ink, o.seed || 1, o.patR);
    }
    ctx.restore();
    if (o.union) return;
    ctx.beginPath();
    path(ctx);
    ctx.lineWidth = lw;
    ctx.lineJoin = "round";
    ctx.strokeStyle = PAL.ink;
    ctx.stroke();
  }
  /** Pattern fill over a big area around the origin (call inside a clip). */
  function pattern(kind, col, seed, extent) {
    const R = extent || 60 * U, c = 2.2 * U;
    ctx.fillStyle = ctx.strokeStyle = col;
    if (kind === "stripes") for (let x = -R; x < R; x += c * 1.6) ctx.fillRect(x, -R, c * 0.8, 2 * R);
    else if (kind === "dots") {
      ctx.beginPath();
      for (let y = -R; y < R; y += c * 1.4) for (let x = -R + ((y / (c * 1.4)) & 1) * c * 0.7; x < R; x += c * 1.4) B.circle(ctx, x, y, c * 0.3);
      ctx.fill();
    } else if (kind === "checker") {
      for (let y = -R, j = 0; y < R; y += c, j++) for (let x = -R + (j & 1) * c; x < R; x += c * 2) ctx.fillRect(x, y, c, c);
    } else if (kind === "squiggle") {
      ctx.lineWidth = 0.5 * U;
      for (let y = -R; y < R; y += c * 1.8) {
        ctx.beginPath();
        for (let x = -R; x < R; x += c * 0.25) ctx.lineTo(x, y + Math.sin(x / (c * 0.5)) * c * 0.35);
        ctx.stroke();
      }
    } else if (kind === "terrazzo") {
      const r = B.rng(seed);
      for (let i = 0; i < 260; i++) { // little angular chips of colour
        const x = r.range(-R, R) * 0.5, y = r.range(-R, R) * 0.5, a = r() * B.TAU, z = r.range(0.4, 0.9) * U;
        ctx.fillStyle = r.pick([PAL.ink, PAL.pink, PAL.turq, PAL.violet]);
        ctx.beginPath();
        B.poly(ctx, [0, 2.2, 4.1].map((k) => [x + Math.cos(a + k) * z, y + Math.sin(a + k) * z * 0.8]), true);
        ctx.fill();
      }
    }
  }
  /** Stroke ornament (squiggle, zigzag) as a fat coloured line with a hard black shadow, traced on to p. */
  function fatLine(pts, col, p = 1, w = 1.3 * U) {
    B.strokeReveal(ctx, pts.map(([x, y]) => [x + 0.9 * U, y + 0.9 * U]), p, { width: w, color: PAL.ink });
    B.strokeReveal(ctx, pts, p, { width: w, color: col });
  }
  const squigglePts = (x, y, len, amp, n = 3) => Array.from({ length: 40 }, (_, i) => [x + (i / 39) * len, y + Math.sin((i / 39) * n * B.TAU) * amp]);
  const zigPts = (x, y, len, amp, n = 6) => Array.from({ length: n * 2 + 1 }, (_, i) => [x + (i / (n * 2)) * len, y + (i % 2 ? -amp : amp)]);
  /** Transform helper: translate, rotate and squash/stretch (sq > 0 = wide and short). */
  function place(x, y, rot, s, sq, fn) {
    if (s <= 0.001) return;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot);
    ctx.scale(s * (1 + sq), s * (1 - sq));
    fn();
    ctx.restore();
  }
  /** Pop-in with overshoot plus a squash that settles: returns [scale, squash]. */
  function popIn(at, dur = 0.4) {
    const dt = T - at;
    if (dt <= 0) return [0, 0];
    const s = B.ease.outBack(B.clamp(dt / dur), 2.6), sq = 0.22 * Math.exp(-dt * 7) * Math.sin(dt * 22);
    return [s, sq];
  }
  /**
   * Chunky words: each word its own colour, black outline, hard black shadow; the line tilts and pops in word by word.
   * words: [{ w, c }]. Returns the line width.
   */
  function chunky(words, x, y, size, at, o = {}) {
    ctx.save();
    ctx.font = B.font(size, CHUNK, 400);
    const sp = size * 0.25, ws = words.map((d) => ctx.measureText(d.w).width);
    let total = ws.reduce((a, b) => a + b, 0) + sp * (words.length - 1);
    const maxW = o.maxW ?? F.safe.w;
    if (total > maxW) { // shrink to fit
      size *= maxW / total;
      ctx.font = B.font(size, CHUNK, 400);
      ws.forEach((_, i) => (ws[i] = ctx.measureText(words[i].w).width));
      total = maxW;
    }
    ctx.translate(x, y);
    ctx.rotate(o.rot ?? -0.06);
    let xx = -total / 2;
    words.forEach((d, i) => {
      const [s, sq] = popIn(at + i * (o.gap ?? 0.12), 0.35), cx = xx + ws[i] / 2;
      xx += ws[i] + sp;
      if (s <= 0) return;
      ctx.save();
      ctx.translate(cx, 0);
      ctx.rotate(Math.sin(i * 2.3 + 1) * 0.05);
      ctx.scale(s * (1 + sq), s * (1 - sq));
      ctx.font = B.font(size, CHUNK, 400);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      ctx.fillStyle = PAL.ink;
      ctx.fillText(d.w, size * 0.07, size * 0.08);
      ctx.lineWidth = size * 0.11;
      ctx.strokeStyle = PAL.ink;
      ctx.strokeText(d.w, 0, 0);
      ctx.fillStyle = d.c;
      ctx.fillText(d.w, 0, 0);
      ctx.restore();
    });
    ctx.restore();
    return total;
  }
  /** Stripy banner: a cream label with striped tails, outline and hard shadow, small mono caps on it. */
  function banner(x, y, text, size, at, o = {}) {
    const [s, sq] = popIn(at, 0.35);
    if (s <= 0) return;
    ctx.save();
    ctx.font = B.font(size, MONO, 400);
    const tw = ctx.measureText(text).width, w = tw + size * 1.6, h = size * 2;
    ctx.restore();
    place(x, y, o.rot ?? 0.04, s, sq, () => {
      [-1, 1].forEach((sd) => { // the striped tails
        const tx = sd * (w / 2 + size * 0.6);
        shape((c) => B.poly(c, [[sd * w * 0.42, -h * 0.32], [tx + sd * size * 1.2, -h * 0.32], [tx + sd * size * 0.4, h * 0.18], [tx + sd * size * 1.2, h * 0.68], [sd * w * 0.42, h * 0.68]], true), o.tail || PAL.turq, { pattern: "stripes", patColor: PAL.cream, off: 0.7 * U, line: 0.6 * U });
      });
      shape((c) => c.rect(-w / 2, -h / 2, w, h), PAL.cream, { shadow: o.shadow || PAL.pink, off: 0.8 * U, line: 0.65 * U });
      B.text(ctx, text, 0, size * 0.05, { size, family: MONO, weight: 400, color: PAL.ink });
    });
  }
  /** Numbered sticker: a coloured circle or star, thick outline, hard shadow, chunky number. */
  function sticker(x, y, r, label, col, at, o = {}) {
    const [s, sq] = popIn(at, 0.4);
    place(x, y, o.rot ?? 0.1 * Math.sin(T * 3 + x), s, sq, () => {
      shape((c) => (o.star ? B.star(c, 0, 0, o.points ?? 12, r, r * 0.78) : B.circle(c, 0, 0, r)), col, { shadow: o.shadow || PAL.ink, off: r * 0.12 });
      chunkyText(label, 0, r * 0.04, o.size ?? r * 1.1, o.text || PAL.cream);
    });
  }
  function chunkyText(str, x, y, size, col) {
    ctx.save();
    ctx.font = B.font(size, CHUNK, 400);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    ctx.lineWidth = size * 0.12;
    ctx.strokeStyle = PAL.ink;
    ctx.strokeText(str, x, y);
    ctx.fillStyle = col;
    ctx.fillText(str, x, y);
    ctx.restore();
  }
  /** Chunky block arrow from (x0, y0) to (x1, y1), outlined, hard shadow; grows out from its tail as p goes 0 -> 1. */
  function blockArrow(x0, y0, x1, y1, w, col, p) {
    if (p <= 0) return;
    const a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0) * p, hl = Math.min(w * 1.6, L * 0.6);
    place(x0, y0, a, 1, 0, () => shape((c) => B.poly(c, [[0, -w / 2], [L - hl, -w / 2], [L - hl, -w * 1.1], [L, 0], [L - hl, w * 1.1], [L - hl, w / 2], [0, w / 2]], true), col));
  }
  /** Spinning starburst behind an item (emphasis). */
  function starburst(x, y, r, col, spin) {
    shape((c) => B.star(c, x, y, 16, r, r * 0.72, spin), col, { off: 0.9 * U });
  }

  // ------------------------------------------------------------------ ornaments: scattered loud decoration, kept near the edges
  /** One scene's ornaments, seeded; each jiggles, spins or bobs on twos. Placed around the edges of the frame. */
  function ornaments(seed, n, appear, avoid = []) { // avoid: [x0, y0, x1, y1] frame fractions kept clear for words
    const r = B.rng(seed), W = F.W, H = F.H;
    for (let i = 0; i < n; i++) {
      const edge = i % 4, k = r();
      let x = edge < 2 ? k * W : edge === 2 ? r.range(0.02, 0.14) * W : r.range(0.86, 0.98) * W;
      let y = edge === 0 ? r.range(0.02, PL(0.12, 0.1)) * H : edge === 1 ? r.range(PL(0.83, 0.9), 0.97) * H : k * H;
      const kind = r.int(0, 8), col = r.pick(BRIGHT), col2 = r.pick(BRIGHT.filter((c) => c !== col)), sz = r.range(3.5, 7) * U;
      const rot = r.range(-1, 1) + Math.sin(T * r.range(2, 4) + i) * 0.12, bob = B.bob(T, 0.6 * U, r.range(1.2, 2), r());
      const [s, sq] = popIn(appear + i * 0.04, 0.35);
      if (avoid.some(([a, b, c, d]) => x > a * W && x < c * W && y > b * H && y < d * H)) continue;
      place(x, y + bob, rot, s, sq, () => {
        if (kind === 0) shape((c) => c.arc(0, 0, sz, Math.PI, 0), col, { shadow: col2, pattern: r.chance(0.5) ? "stripes" : null, patColor: PAL.ink });
        else if (kind === 1) shape((c) => B.poly(c, [[-sz, sz * 0.7], [0, -sz], [sz, sz * 0.7]], true), col, { shadow: col2, pattern: "dots", patColor: PAL.cream });
        else if (kind === 2) fatLine(squigglePts(-sz * 1.4, 0, sz * 2.8, sz * 0.3), col, B.prog(T, appear + i * 0.04, 0.5));
        else if (kind === 3) fatLine(zigPts(-sz * 1.4, 0, sz * 2.8, sz * 0.25), col, B.prog(T, appear + i * 0.04, 0.5));
        else if (kind === 4) { // plus sign
          shape((c) => B.poly(c, [[-0.3, -1], [0.3, -1], [0.3, -0.3], [1, -0.3], [1, 0.3], [0.3, 0.3], [0.3, 1], [-0.3, 1], [-0.3, 0.3], [-1, 0.3], [-1, -0.3], [-0.3, -0.3]].map(([a, b]) => [a * sz * 0.7, b * sz * 0.7]), true), col, { shadow: col2 });
        } else if (kind === 5) { // ring
          shape((c) => {
            c.arc(0, 0, sz * 0.8, 0, B.TAU);
            c.moveTo(sz * 0.42, 0);
            c.arc(0, 0, sz * 0.42, 0, B.TAU, true);
          }, col, { shadow: col2 });
        } else if (kind === 6) { // dot grid
          ctx.fillStyle = PAL.ink;
          ctx.beginPath();
          for (let a = 0; a < 4; a++) for (let b = 0; b < 4; b++) B.circle(ctx, (a - 1.5) * sz * 0.45, (b - 1.5) * sz * 0.45, 0.45 * U);
          ctx.fill();
        } else if (kind === 7) shape((c) => { c.moveTo(0, 0); c.arc(0, 0, sz, -0.2, 1.4); c.closePath(); }, col, { shadow: col2, pattern: "checker", patColor: PAL.ink });
        else shape((c) => c.rect(-sz * 0.5, -sz * 0.9, sz, sz * 1.8), col, { shadow: col2, pattern: "squiggle", patColor: PAL.ink });
      });
    }
  }
  /** Confetti burst from (x, y) at `at`: triangles, rings and slips fly out, then fall and flutter. */
  function confetti(x, y, at, n, spread) {
    const dt = T - at;
    if (dt <= 0 || dt > 3) return;
    const r = B.rng(B.hash("conf", at));
    for (let i = 0; i < n; i++) {
      const a = r.range(-Math.PI, 0), v = r.range(0.4, 1) * spread, col = r.pick(BRIGHT);
      const px = x + Math.cos(a) * v * (1 - Math.exp(-dt * 4)) + Math.sin(dt * 5 + i) * U, py = y + Math.sin(a) * v * (1 - Math.exp(-dt * 4)) + dt * dt * 30 * U;
      place(px, py, dt * r.range(-8, 8), 1, 0, () => {
        const sz = r.range(0.9, 1.6) * U, kind = i % 3;
        if (kind === 0) shape((c) => B.poly(c, [[-sz, sz], [0, -sz], [sz, sz]], true), col, { off: 0.4 * U, line: 0.4 * U });
        else if (kind === 1) shape((c) => c.rect(-sz * 0.4, -sz, sz * 0.8, sz * 2), col, { off: 0.4 * U, line: 0.4 * U });
        else shape((c) => { c.arc(0, 0, sz, 0, B.TAU); c.moveTo(sz * 0.45, 0); c.arc(0, 0, sz * 0.45, 0, B.TAU, true); }, col, { off: 0.4 * U, line: 0.4 * U });
      });
    }
  }

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  /** A popcorn kernel, cut open: yellow hull, cream starch with terrazzo flecks, a turquoise drop of water. */
  function kernelPath(r) {
    return (c) => {
      c.moveTo(0, -r);
      c.bezierCurveTo(r * 0.95, -r, r * 1.05, -r * 0.1, r * 0.55, r * 0.6);
      c.quadraticCurveTo(r * 0.2, r * 1.05, 0, r * 1.05);
      c.quadraticCurveTo(-r * 0.2, r * 1.05, -r * 0.55, r * 0.6);
      c.bezierCurveTo(-r * 1.05, -r * 0.1, -r * 0.95, -r, 0, -r);
      c.closePath();
    };
  }
  function kernel(r, cut = true, swell = 0) {
    shape(kernelPath(r * (1 + swell)), PAL.yellow, { shadow: PAL.red, off: r * 0.08 });
    if (!cut) return;
    shape(kernelPath(r * 0.78 * (1 + swell)), PAL.cream, { pattern: "terrazzo", seed: 7, off: 0, line: 0.5 * U });
    shape((c) => { // the drop of water
      const q = r * 0.24 * (1 + swell);
      c.moveTo(0, r * 0.1 - q * 1.6);
      c.quadraticCurveTo(q * 1.1, r * 0.1, 0, r * 0.1 + q);
      c.quadraticCurveTo(-q * 1.1, r * 0.1, 0, r * 0.1 - q * 1.6);
    }, PAL.turq, { shadow: PAL.violet, off: 0.5 * U, line: 0.55 * U });
  }
  /** Popped popcorn: a lumpy cream cloud of puffs with a yellow heart showing. */
  function popcorn(r, seed) {
    shape((c) => {
      const rr = B.rng(seed);
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * B.TAU + rr.range(-0.3, 0.3), d = r * rr.range(0.35, 0.55), pr = r * rr.range(0.42, 0.58);
        c.moveTo(Math.cos(a) * d + pr, Math.sin(a) * d);
        c.arc(Math.cos(a) * d, Math.sin(a) * d, pr, 0, B.TAU);
      }
    }, PAL.cream, { shadow: PAL.yellow, off: r * 0.12, line: 0.6 * U, union: true });
    shape((c) => B.blob(c, r * 0.1, r * 0.15, r * 0.25, { seed, wobble: 0.3 }), PAL.yellow, { off: 0, line: 0.45 * U });
  }
  /** A flat flame: three stacked zigzag tongues in red and yellow. */
  function flame(r) {
    const tongue = (s) => (c) => B.poly(c, [[-r * s, r * 0.5], [-r * s * 0.7, -r * s * 0.5], [-r * s * 0.3, -r * s * 0.1], [0, -r * s * 1.1], [r * s * 0.3, -r * s * 0.1], [r * s * 0.7, -r * s * 0.5], [r * s, r * 0.5]], true);
    shape(tongue(1), PAL.red, { shadow: PAL.violet });
    shape(tongue(0.6), PAL.yellow, { off: 0, line: 0.6 * U });
  }

  // ------------------------------------------------------------------ scenes
  function sceneTitle() {
    const W = F.W, H = F.H, S = F.safe, bg = PAL.mint;
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);
    // big bold background shapes at odd angles
    place(W * PL(0.85, 0.9), H * PL(0.62, 0.3), 0.5 + T * 0.1, 1, 0, () => shape((c) => c.arc(0, 0, PL(30, 26) * U, Math.PI, 0), PAL.pink, { shadow: PAL.violet, pattern: "stripes", patColor: PAL.cream }));
    place(W * PL(0.1, 0.06), H * PL(0.42, 0.75), -0.4, 1, 0, () => shape((c) => c.rect(-14 * U, -14 * U, 28 * U, 28 * U), PAL.yellow, { shadow: PAL.turq, pattern: "checker" }));
    ornaments(11, 14, 0.05, [PL([0, 0.15, 1, 0.5], [0, 0.15, 0.6, 0.8])]);
    const tx = W * PL(0.5, 0.34), ty = H * PL(0.33, 0.42), ts = PL(16, 13) * U;
    banner(tx, ty - ts * 1.3, "THE SCIENCE OF", PL(4.2, 4) * U, 0.2);
    chunky([{ w: "WHY", c: PAL.pink }, { w: "DOES", c: PAL.yellow }], tx, ty, ts, 0.35, { maxW: PL(S.w, W * 0.55) });
    chunky([{ w: "POPCORN", c: PAL.turq }], tx, ty + ts, ts * 1.15, 0.6, { rot: 0.04, maxW: PL(S.w, W * 0.55) });
    chunky([{ w: "POP?", c: PAL.red }], tx, ty + ts * 2.05, ts * 1.2, 0.85, { rot: -0.08 });
    const kx = W * PL(0.5, 0.74), ky = H * PL(0.68, 0.52), kr = PL(13, 14) * U, [s, sq] = popIn(1.0, 0.45);
    starburst(kx, ky, kr * 1.9 * s, PAL.yellow, T * 0.6);
    place(kx, ky, 0.15 + Math.sin(T * 4) * 0.08, s, sq, () => kernel(kr, false));
  }

  function sceneDiagram() {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[1];
    ctx.fillStyle = B.shade(PAL.yellow, 0.62);
    ctx.fillRect(0, 0, W, H);
    place(W * PL(0.12, 0.08), H * PL(0.85, 0.2), -0.3, 1, 0, () => shape((c) => B.poly(c, [[0, 0], [24 * U, -6 * U], [10 * U, 18 * U]], true), PAL.violet, { shadow: PAL.mint, pattern: "dots", patColor: PAL.cream }));
    ornaments(23, 12, BEATS[1] - 0.2);
    const kx = W * PL(0.5, 0.42), ky = H * PL(0.45, 0.47), kr = PL(22, 19) * U, [s, sq] = popIn(BEATS[1] + 0.05, 0.45);
    place(kx, ky, -0.05 + Math.sin(T * 3) * 0.03, s, sq, () => kernel(kr, true));
    // flame below and a chunky arrow carrying the heat up into the kernel
    const fx = kx + PL(18, 26) * U, fy = ky + kr * PL(1.6, 1.25);
    const [fs, fsq] = popIn(BEATS[1] + 0.6, 0.35);
    place(fx, fy, 0, fs, fsq + Math.sin(T * 14) * 0.04, () => flame(PL(6, 5) * U));
    blockArrow(fx - PL(3, 4) * U, fy - PL(6, 5) * U, kx + kr * 0.5, ky + kr * 0.55, PL(3.4, 2.8) * U, PAL.red, B.prog(lt, 0.8, 0.4));
    // labels on stripy banners with fat leader stubs
    const ls = PL(4.2, 4) * U;
    const tag = (x, y, tx, ty, txt, at, tail) => {
      fatLine([[x, y], [tx, ty]], PAL.ink, B.prog(lt, at - BEATS[1] - 0.1, 0.25), 0.9 * U);
      banner(x, y, txt, ls, at, { tail });
    };
    tag(kx - kr * PL(1.05, 1.6), ky - kr * PL(1.4, 0.8), kx - kr * 0.55, ky - kr * 0.7, "HULL", BEATS[1] + 0.5, PAL.pink);
    tag(kx + kr * PL(1.05, 1.7), ky - kr * PL(1.2, 0.3), kx + kr * 0.35, ky - kr * 0.25, "STARCH", BEATS[1] + 0.75, PAL.violet);
    tag(kx - kr * PL(1.05, 1.7), ky + kr * PL(1.0, 0.65), kx - kr * 0.05, ky + kr * 0.15, "WATER", BEATS[1] + 1.0, PAL.turq);
    banner(fx + PL(0, 10) * U, fy + PL(9, 3) * U, "HEAT", ls, BEATS[1] + 1.1, { tail: PAL.red, rot: -0.06 });
  }

  function sceneNumber() {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[2];
    ctx.fillStyle = B.shade(PAL.pink, 0.66);
    ctx.fillRect(0, 0, W, H);
    place(W * 0.5, H * 0.5, T * 0.05, 1, 0, () => shape((c) => c.arc(0, 0, PL(44, 34) * U, 0.3, 0.3 + Math.PI), PAL.turq, { shadow: PAL.violet, pattern: "squiggle", patColor: PAL.cream }));
    ornaments(37, 12, BEATS[2] - 0.2);
    const cx = W * 0.5, cy = H * PL(0.47, 0.5), R = PL(30, 23) * U;
    // the value changes in jumps; the sticker pops again every time it does
    const n = B.clamp(Math.floor((lt - 0.35) / 0.28) + 1, 0, 5), val = [0, 45, 90, 135, 180, 180][n];
    const lastJump = BEATS[2] + 0.35 + (Math.min(n, 4) - 1) * 0.28;
    starburst(cx, cy, R * 1.25, PAL.pink, -T * 0.8);
    if (n > 0) sticker(cx, cy, R, val + "°C", PAL.yellow, lastJump, { star: true, points: 14, size: R * 0.62, text: PAL.red, shadow: PAL.violet, rot: -0.05 });
    if (lt > 1.3) confetti(cx, cy - R * 0.4, BEATS[2] + 1.3, 26, R * 1.6);
    chunky([{ w: "that's", c: PAL.cream }, { w: "356", c: PAL.yellow }, { w: "°F", c: PAL.yellow }], cx, cy + R * 1.5, PL(9, 6.5) * U, BEATS[2] + 1.35, { rot: 0.05 });
    banner(cx, cy - R * 1.25 - 6.7 * U, "THEY POP AT ABOUT", PL(4.2, 4) * U, BEATS[2] + 0.15, { rot: -0.03 });
  }

  function sceneSteps() {
    const W = F.W, H = F.H, S = F.safe, b3 = BEATS[3], b4 = BEATS[4];
    ctx.fillStyle = PAL.cream;
    ctx.fillRect(0, 0, W, H);
    place(W * PL(0.88, 0.99), H * PL(0.9, 0.97), 1.2, 1, 0, () => shape((c) => B.roundRect(c, -8 * U, -40 * U, 16 * U, 80 * U, 8 * U), PAL.mint, { shadow: PAL.pink, pattern: "stripes" }));
    ornaments(53, 12, b3 - 0.2, [PL([0, 0.18, 1, 0.78], [0, 0.2, 1, 0.9])]);
    const steps = [
      { n: "1", cut: 2, col: PAL.turq, words: [{ w: "Water", c: PAL.turq }, { w: "turns", c: PAL.pink }, { w: "to", c: PAL.yellow }, { w: "steam", c: PAL.violet }], at: b3 + 0.2 },
      { n: "2", cut: 1, col: PAL.violet, words: [{ w: "Pressure", c: PAL.red }, { w: "builds", c: PAL.turq }, { w: "up", c: PAL.yellow }], at: b3 + 0.9 },
      { n: "3", cut: 1, col: PAL.red, words: [{ w: "POP!", c: PAL.yellow }, { w: "Starch", c: PAL.pink }, { w: "puffs", c: PAL.turq }], at: b4 + 0.1 },
    ];
    steps.forEach((st, i) => {
      const ix = PL(S.x + 17 * U, W * (0.2 + i * 0.3)), iy = PL(H * (0.28 + i * 0.19), H * 0.36), ir = 9 * U;
      if (i === 2 && T < st.at) { // the third kernel is already waiting, trembling harder, until it pops
        const [s, sq] = popIn(b3 + 1.05, 0.4), shake = B.prog(T, b3 + 1.2, b4 - b3 - 1.2);
        return place(ix + Math.sin(T * 40) * shake * 0.8 * U, iy, 0.2, s, sq, () => kernel(ir * 0.9, false, 0.08 * shake));
      }
      if (T < st.at) return;
      const sx = PL(ix + 10 * U, ix), sy = PL(iy - 9 * U, iy + 17 * U);
      // the icon for the step: steaming kernel, swelling kernel with pressure arrows, burst popcorn
      const [s, sq] = popIn(st.at, 0.4);
      if (i === 0) {
        place(ix, iy, 0.1, s, sq, () => kernel(ir * 0.9, true));
        for (let k = 0; k < 3; k++) fatLine(squigglePts(-2 * U, 0, 5 * U, 0.8 * U, 1.5).map(([x, y]) => [ix + (k - 1) * 3.5 * U + y, iy - ir * 1.3 - x]), PAL.turq, B.prog(T, st.at + 0.2 + k * 0.08, 0.4), 0.8 * U);
      } else if (i === 1) {
        const swell = 0.06 * Math.abs(Math.sin(T * 9));
        place(ix + Math.sin(T * 40) * 0.4 * U, iy, -0.1, s, sq, () => kernel(ir * 0.9, true, swell));
        [0, 1, 2, 3].forEach((k) => {
          const a = (k / 4) * B.TAU + 0.4, p = B.prog(T, st.at + 0.3 + k * 0.06, 0.3);
          blockArrow(ix + Math.cos(a) * ir * 0.4, iy + Math.sin(a) * ir * 0.4, ix + Math.cos(a) * ir * 1.5, iy + Math.sin(a) * ir * 1.5, 1.5 * U, PAL.yellow, p);
        });
      } else {
        starburst(ix, iy, ir * 1.6 * s, PAL.yellow, T * 0.9);
        place(ix, iy, 0.2, s, sq, () => popcorn(ir * 1.25, 4));
        confetti(ix, iy - ir * 0.5, st.at + 0.05, 18, PL(18, 20) * U);
      }
      sticker(sx, sy, PL(4.6, 3.8) * U, st.n, st.col, st.at + 0.15, { shadow: PL(PAL.ink, PAL.ink) });
      const tx = PL(W * 0.66, ix), ty = PL(iy - 3 * U, sy + 9 * U), ts = PL(8, 6.4) * U, mw = PL(W * 0.5, W * 0.28);
      chunky(st.words.slice(0, st.cut), tx, ty, ts, st.at + 0.2, { gap: 0.06, rot: -0.03, maxW: mw });
      chunky(st.words.slice(st.cut), tx, ty + ts * 1.1, ts, st.at + 0.32, { gap: 0.06, rot: 0.03, maxW: mw });
    });
  }

  function sceneClose() {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[5];
    ctx.fillStyle = PAL.mint;
    ctx.fillRect(0, 0, W, H);
    place(W * PL(0.15, 0.1), H * PL(0.6, 0.62), -0.5 + T * 0.08, 1, 0, () => shape((c) => { c.moveTo(0, 0); c.arc(0, 0, 26 * U, 0, 1.6); c.closePath(); }, PAL.violet, { shadow: PAL.yellow, pattern: "dots", patColor: PAL.cream }));
    ornaments(71, 14, BEATS[5] - 0.2, [PL([0, 0.18, 1, 0.45], [0, 0.22, 0.62, 0.62])]);
    // the striped popcorn box, heaped
    const bx = W * PL(0.5, 0.7), by = H * PL(0.63, 0.62), bw = PL(30, 24) * U, bh = PL(30, 26) * U, [s, sq] = popIn(BEATS[5] + 0.1, 0.45);
    place(bx, by, 0.04 + Math.sin(T * 3) * 0.03, s, sq, () => {
      [[-0.5, -0.05, 0.42], [0.45, 0.0, 0.4], [-0.1, -0.35, 0.5], [0.25, -0.5, 0.38], [-0.4, -0.55, 0.36]].forEach(([dx, dy, rr], i) => {
        const [ps] = popIn(BEATS[5] + 0.35 + i * 0.1, 0.3);
        place(dx * bw, dy * bh, i, ps, 0, () => popcorn(bw * rr, 9 + i));
      });
      shape((c) => B.poly(c, [[-bw * 0.62, -bh * 0.05], [bw * 0.62, -bh * 0.05], [bw * 0.48, bh], [-bw * 0.48, bh]], true), PAL.red, { shadow: PAL.violet, pattern: "stripes", patColor: PAL.cream });
      shape((c) => B.roundRect(c, -bw * 0.68, -bh * 0.12, bw * 1.36, bh * 0.16, 0.8 * U), PAL.yellow, { off: 0.6 * U });
    });
    const tx = W * PL(0.5, 0.32), ty = H * PL(0.28, 0.38), ts = PL(12, 10) * U;
    chunky([{ w: "HEAT", c: PAL.red }, { w: "+", c: PAL.ink }, { w: "WATER", c: PAL.turq }], tx, ty, ts, BEATS[5] + 0.3, { maxW: PL(S.w, W * 0.5) });
    chunky([{ w: "=", c: PAL.violet }, { w: "POP!", c: PAL.yellow }], tx, ty + ts * 1.25, ts * 1.3, BEATS[5] + 0.7, { rot: 0.06 });
    if (lt > 0.6) confetti(bx, by - bh * 0.6, BEATS[5] + 0.6, 34, PL(34, 26) * U);
  }
  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneSteps, sceneClose];

  // ------------------------------------------------------------------ the swipe: a wide polka-dot band sweeping across
  function swipe(W, H, t) {
    for (const at of SWIPES) {
      const p = B.span(t, at - 0.35, at + 0.35, "inOutQuad");
      if (p <= 0 || p >= 1) continue;
      const D = Math.hypot(W, H), bw = D * 0.75, x = B.lerp(-bw, W + bw, p);
      ctx.save();
      ctx.translate(x, H / 2);
      ctx.rotate(-0.35);
      shape((c) => c.rect(-bw / 2, -D, bw, 2 * D), PAL.pink, { shadow: PAL.ink, off: 1.6 * U, pattern: "dots", patColor: PAL.cream, patR: D, line: 1.2 * U });
      shape((c) => c.rect(-bw / 2 - 5 * U, -D, 5 * U, 2 * D), PAL.yellow, { off: 0, pattern: "stripes", patR: D });
      shape((c) => c.rect(bw / 2, -D, 5 * U, 2 * D), PAL.turq, { off: 0, pattern: "stripes", patR: D });
      ctx.restore();
    }
  }

  function draw(c, W, H, t) {
    ctx = c;
    F = B.frame(W, H);
    U = F.u;
    T = B.stepTime(t, 12); // on twos: every pose holds for two frames at 24 fps
    const at = SWIPES.find((a) => T > a - 0.35 && T < a + 0.35);
    if (at == null) SCENES[B.beat(T, BEATS, DUR).i]();
    else { // mid-swipe: the old scene ahead of the band, the next one already sitting behind it
      const D = Math.hypot(W, H), x = B.lerp(-D * 0.75, W + D * 0.75, B.span(T, at - 0.35, at + 0.35, "inOutQuad"));
      SCENES[B.beat(at - 0.01, BEATS, DUR).i]();
      ctx.save();
      ctx.translate(x, H / 2);
      ctx.rotate(-0.35);
      ctx.beginPath();
      ctx.rect(-3 * D, -D, 3 * D, 2 * D);
      ctx.rotate(0.35);
      ctx.translate(-x, -H / 2);
      ctx.clip();
      SCENES[B.beat(at, BEATS, DUR).i]();
      ctx.restore();
      swipe(W, H, T);
    }
    B.grain(ctx, W, H, { amount: 0.05, t: T, fps: 12, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: boings for pop-ins, squeaky sticker slaps, xylophone runs for swipes, confetti rattles
  SOUND.define("memphis-boing", (v) => {
    // bouncy boing: a sine that springs up in pitch and wobbles as it settles
    const t = v.tone({ f: 180, fpath: [[0.06, 520], [0.25, 330]], a: 0.004, len: 0.32, peak: 0.3 });
    v.lfo(t.osc.frequency, 18, 40, v.t + 0.4);
  }, { verb: 0.12 });
  SOUND.define("memphis-squeak", (v) => {
    // squeaky blip: a short bright square chirp, like a sticker slapped on vinyl
    v.tone({ type: "square", f: 1400, f2: 2300, glide: 0.06, a: 0.002, len: 0.07, peak: 0.07 });
    v.noise({ filter: "bandpass", f: 3200, q: 2, a: 0.001, len: 0.04, peak: 0.12 });
  }, { verb: 0.1 });
  SOUND.define("memphis-confetti", (v) => {
    // a little party pop with a papery rattle after it
    v.sub("pop", 0, { pitch: 3 });
    v.grains({ at: 0.04, span: 0.5, count: 22, filter: "highpass", f: 4000, len: 0.012, peak: 0.12 });
  }, { verb: 0.2 });

  function score(k) {
    const xyl = SOUND.scale("C5", "major", 10);
    k.bed("arp", 0, DUR, { notes: SOUND.scale("C4", "pent", 8), step: 0.18, gain: 0.7 });
    k.repeat(0.05, 0.04, 10, "memphis-boing", { gain: 0.35, vary: 3 });
    [0.35, 0.47, 0.6, 0.85].forEach((at, i) => k.at(at, "memphis-boing", { pitch: i * 2, gain: 0.7 }));
    k.at(0.2, "memphis-squeak").at(1.0, "memphis-boing", { pitch: -3 }).at(1.05, "pop");
    SWIPES.forEach((s) => k.seq(s - 0.35, 0.05, s === 6.4 ? xyl.slice(0, 8).reverse() : xyl.slice(0, 8), { voice: "marimba", gain: 0.6 }).at(s - 0.3, "swish", { dur: 0.6, gain: 0.5 }));
    // diagram
    k.at(2.05, "memphis-boing", { pitch: -2 });
    [2.5, 2.75, 3.0, 3.1].forEach((at, i) => k.at(at, "memphis-squeak", { pitch: i * 2 }));
    k.at(2.6, "memphis-boing", { pitch: 4, gain: 0.6 }).at(2.8, "whoosh", { dur: 0.4, gain: 0.4 });
    // number: the sticker pops at every jump, confetti at the top
    k.at(4.35, "memphis-squeak");
    [4.55, 4.83, 5.11, 5.39].forEach((at, i) => k.at(at, "memphis-boing", { pitch: i * 3, gain: 0.8 }));
    k.at(5.5, "memphis-confetti", { gain: 1.1 }).at(5.65, "memphis-squeak", { pitch: 3 });
    // steps
    [6.6, 7.3].forEach((at, i) => k.at(at, "memphis-boing", { pitch: i * 2 }).at(at + 0.15, "memphis-squeak", { pitch: i * 2 }));
    k.at(7.45, "memphis-boing", { pitch: -4, gain: 0.5 }).at(6.8, "bubble", { gain: 0.5 }).at(6.9, "bubble", { pitch: 4, gain: 0.4 });
    k.repeat(7.8, 0.12, 6, "knock", { gain: 0.3, vary: 2 });
    k.at(8.7, "impact", { gain: 0.7 }).at(8.7, "memphis-confetti", { gain: 1.2 }).at(8.85, "memphis-squeak", { pitch: 5 });
    k.repeat(8.9, 0.07, 8, "pop", { gain: 0.35, vary: 4, jitter: 0.03 });
    // close
    k.at(10.4, "memphis-boing").repeat(10.65, 0.1, 5, "pop", { gain: 0.45, vary: 3 });
    k.at(10.6, "memphis-squeak").at(11.0, "memphis-boing", { pitch: 5 }).at(10.9, "memphis-confetti", { gain: 1.1 });
    k.seq(11.2, 0.07, xyl.slice(2, 10), { voice: "marimba", gain: 0.5 });
  }

  Player.register({
    id: "memphis",
    name: "Memphis Pop",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Lilita+One&family=Rubik+Mono+One&display=swap",
      faces: ['400 20px "Lilita One"', '400 20px "Rubik Mono One"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Two steps", "Pop!", "Close"],
    stills: [1.6, 3.7, 6.0, 8.2, 9.7, 11.6],
    draw,
    score,
  });
})();
