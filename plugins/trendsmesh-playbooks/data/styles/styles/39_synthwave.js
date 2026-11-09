/* 39 Synthwave - reference animation.
 * Topic (setting, replace it): "How does a synthesizer make sound?" - oscillator, filter, amplifier.
 * Rendering (keep it): an 80s outrun night poster. A violet-to-magenta-to-orange sky with blinking stars; a striped sun
 * on the horizon (bands cut from its lower half, thicker toward the bottom); wireframe mountains filled with the
 * night colour; a black plane with a magenta perspective grid racing toward the viewer. Everything bright is drawn into
 * one neon layer, which is laid over the sky and then bloomed (a blurred, downsampled copy added on top). Neon tubes
 * are three strokes: a wide halo, the colour, a thin white core. Chrome titles: heavy italic capitals with a light top
 * half, a dark horizon line through the middle and pink/blue bevel edges; a second line in neon tube lettering.
 * Finishing: bloom (strong), fine scanlines (~8 %), a chromatic fringe that grows toward the frame edges (the red and
 * blue channels scaled a hair apart about the centre), vignette.
 * Motion: stars blink on, the horizon appears, the grid races in an endless loop, the sun rises and the mountains grow;
 * chrome titles slam in from large with a white flash and a glint sweeps across; neon flickers on tube by tube with a
 * stutter; scene changes are a bright horizontal flash, or the view panning up into the sky. Driving and rhythmic.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { night: "#1a0b3b", indigo: "#2b1259", magenta: "#ff2bd6", cyan: "#27e8ff", orange: "#ff8a3d", yellow: "#ffd84a", chrome: "#e9f1ff", void: "#07040f" };
  const TECH = "Orbitron", TUBE = "Monoton";
  const DUR = 12.5;
  const BEATS = [0, 2.2, 4.5, 6.7, 9.0, 10.8];
  const FLASHES = [4.5, 6.7, 10.8]; // bright horizontal flash wipes; 2.2 is a pan up into the sky
  let U = 1, T = 0, F = null, N = null;
  const PL = (portrait, landscape) => (F.portrait ? portrait : landscape);

  // ------------------------------------------------------------------ the world: horizon height per beat (the camera pans by moving it)
  function horizon(t) {
    const keys = [PL(0.6, 0.64), PL(0.8, 0.8), PL(0.7, 0.8), PL(0.47, 0.5), PL(0.47, 0.5), PL(0.62, 0.66)];
    let k = 0;
    for (let i = 1; i < BEATS.length; i++) k += B.span(t, BEATS[i] - 0.35, BEATS[i] + 0.25, "inOutCubic") * (keys[i] - keys[i - 1]);
    return F.H * (keys[0] + k);
  }
  function sky(ctx, W, H, hy) {
    ctx.fillStyle = B.linear(ctx, 0, 0, 0, hy, [[0, PAL.void], [0.35, PAL.night], [0.7, PAL.indigo], [0.9, "#8a1f8f"], [1, PAL.orange]]);
    ctx.fillRect(0, 0, W, hy + 1);
    ctx.fillStyle = PAL.void;
    ctx.fillRect(0, hy, W, H - hy);
  }
  function stars(g, W, hy) {
    const r = B.rng(39);
    for (let i = 0; i < 70; i++) {
      const x = r() * W, y = r() * hy * 0.85, on = B.clamp((T - r() * 0.6) / 0.08), tw = 0.55 + 0.45 * Math.sin(T * r.range(2, 5) + i);
      if (on <= 0) continue;
      g.fillStyle = B.rgba(i % 7 ? PAL.chrome : PAL.cyan, on * tw);
      g.fillRect(x, y, r.range(0.15, 0.4) * U, r.range(0.15, 0.4) * U);
    }
  }
  /** The striped sun: a yellow-to-pink disc whose lower half is cut by bands that grow thicker toward the bottom. */
  function sun(g, cx, hy, R, rise) {
    const cy = hy - R * 0.15 + (1 - rise) * R * 1.3;
    B.glow(g, cx, cy, R * 2.2, PAL.magenta, 0.35 * rise, { add: true });
    g.save();
    g.beginPath();
    g.rect(cx - R * 1.2, 0, R * 2.4, hy); // only above the horizon
    g.clip();
    g.beginPath();
    g.rect(cx - R * 1.2, 0, R * 2.4, hy);
    for (let i = 0; i < 7; i++) { // the cut bands (evenodd removes them), thicker toward the bottom
      const y = cy - R * 0.45 + R * (i * 0.085 + i * i * 0.004), h = R * (0.014 + i * 0.013);
      g.rect(cx - R * 1.2, y, R * 2.4, h);
    }
    g.clip("evenodd");
    g.fillStyle = B.linear(g, 0, cy - R, 0, cy + R * 0.4, [[0, PAL.yellow], [0.5, PAL.orange], [1, PAL.magenta]]);
    g.beginPath();
    B.circle(g, cx, cy, R);
    g.fill();
    g.restore();
  }
  /** Wireframe mountains: night-filled peaks with neon outlines and inner wire lines, growing up from the horizon. */
  function mountains(g, W, hy, grow, seed) {
    if (grow <= 0) return;
    const r = B.rng(seed), peaks = [];
    for (let x = -W * 0.1; x < W * 1.1; x += r.range(0.08, 0.16) * W) peaks.push([x, hy - r.range(0.04, 0.12) * F.H * PL(0.55, 1) * grow * (Math.abs(x - W / 2) > W * 0.22 ? 1 : 0.35)]);
    const line = [[-W * 0.1, hy]].concat(peaks, [[W * 1.1, hy]]);
    g.save();
    g.fillStyle = PAL.night;
    g.beginPath();
    B.poly(g, line, true);
    g.fill();
    g.lineJoin = "round";
    peaks.forEach((p, i) => { // wire lines from each peak down to the valleys
      g.strokeStyle = B.rgba(PAL.cyan, 0.45);
      g.lineWidth = 0.15 * U;
      g.beginPath();
      g.moveTo(p[0], p[1]);
      g.lineTo((p[0] + (peaks[i + 1] || p)[0]) / 2, hy);
      g.moveTo(p[0], p[1]);
      g.lineTo((p[0] + (peaks[i - 1] || p)[0]) / 2, hy);
      g.stroke();
    });
    tube(g, line, PAL.magenta, 0.35 * U);
    g.restore();
  }
  /** The ground grid: lines converge on the vanishing point; the cross lines race toward the viewer forever. */
  function grid(g, W, H, hy, alpha = 1) {
    const vx = W / 2, depth = H - hy;
    g.save();
    g.lineWidth = 0.22 * U;
    for (let k = -14; k <= 14; k++) {
      g.strokeStyle = B.linear(g, 0, hy, 0, H, [[0, B.rgba(PAL.magenta, 0)], [0.3, B.rgba(PAL.magenta, 0.7 * alpha)], [1, B.rgba(PAL.magenta, alpha)]]);
      g.beginPath();
      g.moveTo(vx + k * 0.6 * U, hy);
      g.lineTo(vx + k * W * 0.12, H + depth * 0.2);
      g.stroke();
    }
    const ph = B.fract(T * 1.6);
    for (let i = 0; i < 14; i++) {
      const z = 1 + (i - ph) * 0.9; // depth of this cross line; nearer lines spread wider apart
      if (z <= 0.2) continue;
      const y = hy + depth * (0.18 / z) * 3.2;
      if (y > H) continue;
      g.strokeStyle = B.rgba(PAL.magenta, alpha * B.clamp((y - hy) / (depth * 0.25)));
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(W, y);
      g.stroke();
    }
    g.restore();
  }

  // ------------------------------------------------------------------ neon and chrome (reuse these)
  /** A neon tube along a polyline: wide soft halo, the colour, a thin white-hot core. */
  function tube(g, pts, col, w, a = 1) {
    if (a <= 0 || pts.length < 2) return;
    g.save();
    g.globalAlpha *= a;
    g.lineCap = g.lineJoin = "round";
    [[w * 4, B.rgba(col, 0.18)], [w * 1.6, col], [w * 0.5, "#ffffff"]].forEach(([lw, c]) => {
      g.strokeStyle = c;
      g.lineWidth = lw;
      g.beginPath();
      B.poly(g, pts);
      g.stroke();
    });
    g.restore();
  }
  /** Neon arrow: a straight tube with a sharp open head. */
  function neonArrow(g, x0, y0, x1, y1, col, p) {
    if (p <= 0) return;
    const x = B.lerp(x0, x1, p), y = B.lerp(y0, y1, p), a = Math.atan2(y1 - y0, x1 - x0), h = 2.2 * U;
    tube(g, [[x0, y0], [x, y]], col, 0.32 * U);
    tube(g, [[x - Math.cos(a - 0.5) * h, y - Math.sin(a - 0.5) * h], [x, y], [x - Math.cos(a + 0.5) * h, y - Math.sin(a + 0.5) * h]], col, 0.32 * U);
  }
  /** Neon frame (thin tube rectangle), filled dark so text on it reads. */
  function neonBox(g, x, y, w, h, col, a = 1) {
    if (a <= 0) return;
    g.save();
    g.globalAlpha *= a;
    g.fillStyle = B.rgba(PAL.void, 0.75);
    g.beginPath();
    B.roundRect(g, x, y, w, h, 1.2 * U);
    g.fill();
    g.restore();
    tube(g, [[x + 1.2 * U, y], [x + w - 1.2 * U, y]].concat(B.arcPts(x + w - 1.2 * U, y + 1.2 * U, 1.2 * U, -Math.PI / 2, 0, 6), B.arcPts(x + w - 1.2 * U, y + h - 1.2 * U, 1.2 * U, 0, Math.PI / 2, 6), B.arcPts(x + 1.2 * U, y + h - 1.2 * U, 1.2 * U, Math.PI / 2, Math.PI, 6), B.arcPts(x + 1.2 * U, y + 1.2 * U, 1.2 * U, Math.PI, Math.PI * 1.5, 6)), col, 0.22 * U, a);
  }
  /** Glowing text (Orbitron) in a neon colour with a white-hot core. */
  function glowText(g, str, x, y, size, col, o = {}) {
    B.text(g, str, x, y, { size, family: TECH, weight: o.weight ?? 700, color: col, align: o.align, maxW: o.maxW, letterSpacing: o.ls ?? 0.08, alpha: o.alpha, shadow: { x: 0, y: 0, blur: size * 0.5, color: col } });
    B.text(g, str, x, y, { size, family: TECH, weight: o.weight ?? 700, color: "#ffffff", align: o.align, maxW: o.maxW, letterSpacing: o.ls ?? 0.08, alpha: (o.alpha ?? 1) * 0.45 });
  }
  /**
   * Chrome italic title: slams in from large with a white flash at `at`, then a glint sweeps across it.
   * Drawn into its own scratch so the glint stays on the letters (source-atop).
   */
  function chrome(g, str, cx, cy, size, at, key) {
    const dt = T - at;
    if (dt <= 0) return;
    const W = F.W, H = F.H, c = B.scratch("syn-chrome-" + key, W, H);
    c.font = B.font(size, TECH, 900);
    if ("letterSpacing" in c) c.letterSpacing = (size * 0.04).toFixed(1) + "px";
    const tw = c.measureText(str).width, s0 = Math.min(1, (F.safe.w * 0.98) / tw);
    const s = s0 * (dt < 0.18 ? B.lerp(2.6, 1, B.ease.inQuad(dt / 0.18)) : 1 + 0.04 * Math.exp(-(dt - 0.18) * 12) * Math.cos((dt - 0.18) * 40));
    c.save();
    c.translate(cx, cy);
    c.scale(s, s);
    c.transform(1, 0, -0.2, 1, 0, 0); // italic slant
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.lineJoin = "round";
    c.lineWidth = size * 0.12;
    c.strokeStyle = PAL.magenta; // bevel: pink outer edge, blue inner edge
    c.strokeText(str, size * 0.03, size * 0.03);
    c.lineWidth = size * 0.06;
    c.strokeStyle = PAL.cyan;
    c.strokeText(str, -size * 0.015, -size * 0.015);
    c.fillStyle = B.linear(c, 0, -size * 0.42, 0, size * 0.42, [[0, "#ffffff"], [0.44, "#a9c8ff"], [0.5, PAL.indigo], [0.54, "#4b1f7a"], [0.78, "#ff8fd6"], [1, "#fff0fa"]]);
    c.fillText(str, 0, 0);
    c.restore();
    // glint: a narrow bright diagonal band sweeping across the letters once
    const gp = B.prog(T, at + 0.3, 0.7, "inOutSine");
    if (gp > 0 && gp < 1) {
      const gx = cx - tw * 0.7 + gp * tw * 1.4;
      c.save();
      c.globalCompositeOperation = "source-atop";
      c.fillStyle = B.linear(c, gx - size * 0.5, 0, gx + size * 0.5, 0, [[0, "rgba(255,255,255,0)"], [0.5, "rgba(255,255,255,0.95)"], [1, "rgba(255,255,255,0)"]]);
      c.fillRect(gx - size, cy - size, size * 2, size * 2);
      c.restore();
    }
    g.drawImage(c.canvas, 0, 0);
    if (dt < 0.35) B.glow(g, cx, cy, size * 3, "#ffffff", 0.8 * (1 - dt / 0.35), { add: true }); // the slam flash
  }
  /** Neon tube lettering (Monoton), each glyph flickering on with a stutter before it holds. */
  function neonScript(g, str, cx, cy, size, at, col = PAL.magenta, gap = 0.05) {
    g.save();
    g.font = B.font(size, TUBE, 400);
    const tw = Math.min(g.measureText(str).width, F.safe.w), sc = Math.min(1, F.safe.w / g.measureText(str).width);
    g.translate(cx, cy);
    g.scale(sc, sc);
    g.textBaseline = "middle";
    let x = -(g.measureText(str).width + g.measureText(" ").width * 1.2 * (str.split(" ").length - 1)) / 2;
    [...str].forEach((ch, i) => {
      const w = g.measureText(ch).width * (ch === " " ? 2.2 : 1), dt = T - (at + i * gap);
      x += w;
      if (dt <= 0 || ch === " ") return;
      const on = dt > 0.3 ? 1 : B.hash01("flk", i, Math.floor(T * 30)) < 0.35 + dt * 2 ? 1 : 0.1; // stutter, then steady
      g.globalAlpha = on;
      g.shadowColor = col;
      g.shadowBlur = size * 0.4;
      g.fillStyle = col;
      g.fillText(ch, x - w, 0);
      g.shadowBlur = 0;
      g.fillStyle = "rgba(255,240,252,0.9)"; // the white-hot core of the glass tube
      g.fillText(ch, x - w, 0);
    });
    g.restore();
    return tw;
  }
  /** Dashboard odometer: digit windows with glowing digits rolling up (v continuous). */
  function odometer(g, cx, cy, v, digits, size, col) {
    const cw = size * 0.9, ch = size * 1.25, x0 = cx - (digits * cw) / 2;
    for (let d = 0; d < digits; d++) {
      const place = Math.pow(10, digits - 1 - d);
      let pos = Math.floor(v / place);
      pos = place > 1 ? pos + B.clamp((v % place) / (place / 10) - 9) : v;
      const x = x0 + d * cw + cw / 2;
      neonBox(g, x - cw / 2 + 0.5 * U, cy - ch / 2, cw - U, ch, PAL.indigo);
      g.save();
      g.beginPath();
      g.rect(x - cw / 2, cy - ch / 2 + 0.3 * U, cw, ch - 0.6 * U);
      g.clip();
      const f = pos - Math.floor(pos);
      for (let j = -1; j <= 1; j++) glowText(g, String((((Math.floor(pos) + j) % 10) + 10) % 10), x, cy + (j - f) * ch, size, col, { weight: 800, ls: 0 });
      g.restore();
    }
  }
  /** A wave drawn as a neon line: kind "saw" | "soft" (filtered) | "env" (shaped by an envelope). */
  function wavePts(kind, x, y, w, h, cycles, p = 1) {
    const out = [];
    for (let i = 0; i <= 160 * p; i++) {
      const u = i / 160, ph = B.fract(u * cycles + T * 0.8);
      let v = kind === "saw" ? 1 - 2 * ph : Math.sin(ph * B.TAU) * (kind === "soft" ? 0.8 : 1);
      if (kind === "env") v *= Math.min(1, u / 0.12) * (u < 0.3 ? 1 : B.lerp(1, 0.55, B.clamp((u - 0.3) / 0.15))) * (u > 0.8 ? 1 - (u - 0.8) / 0.2 : 1);
      out.push([x + u * w, y - v * h / 2]);
    }
    return out;
  }

  // ------------------------------------------------------------------ scenes (the setting: replace the content)
  const STEPS = [
    { tag: "OSC", title: "1  OSCILLATOR", body: "makes a raw, buzzy wave", wave: "saw" },
    { tag: "FILTER", title: "2  FILTER", body: "cuts the fizz to shape the tone", wave: "soft" },
    { tag: "AMP", title: "3  ENVELOPE + AMP", body: "swells and fades the loudness", wave: "env" },
  ];
  /** The signal chain: three neon boxes centred on pos, joined by neon arrows (down the column when vertical);
   * `hot` switches one tube to hot pink (emphasis). Tags keep one legible size; size the boxes to fit them. */
  function chain(g, pos, bw, bh, at, hot, vertical) {
    STEPS.forEach((s, i) => {
      const a = B.clamp((T - at - i * 0.25) / 0.15) * (B.hash01("chn", i, Math.floor(T * 30)) < 0.3 && T - at - i * 0.25 < 0.18 ? 0.2 : 1);
      const col = hot === i ? PAL.magenta : PAL.cyan, pulse = hot === i ? 1 + 0.06 * Math.sin(T * 12) : 1, [x, y] = pos[i];
      neonBox(g, x - (bw * pulse) / 2, y - (bh * pulse) / 2, bw * pulse, bh * pulse, col, a);
      if (a > 0) glowText(g, s.tag, x, y, Math.min(bh * 0.5, PL(4.4, 4.2) * U), col, { alpha: a, maxW: bw * 0.92 });
      if (i > 1) return;
      const [nx, ny] = pos[i + 1], d = 1.2 * U, pr = B.prog(T, at + i * 0.25 + 0.2, 0.25);
      if (vertical) neonArrow(g, x, y + bh / 2 + d, nx, ny - bh / 2 - d, PAL.yellow, pr);
      else neonArrow(g, x + bw / 2 + d, y, nx - bw / 2 - d, ny, PAL.yellow, pr);
    });
  }
  /** A small chain strip (steps, close): one row of boxes across the frame. */
  const strip = (g, cy, at, hot) => chain(g, [-1, 0, 1].map((k) => [F.W / 2 + k * PL(31, 31) * U, cy]), PL(25, 24) * U, PL(10, 8.5) * U, at, hot);
  function sceneTitle(g, W, H, hy) {
    const S = F.safe;
    sun(g, W / 2, hy, PL(26, 16) * U, B.prog(T, 0.35, 1.2, "outCubic"));
    mountains(g, W, hy, B.prog(T, 0.5, 1.0, "outCubic"), 3);
    tube(g, [[0, hy], [W * B.prog(T, 0.15, 0.4, "outCubic"), hy]], PAL.cyan, 0.25 * U);
    grid(g, W, H, hy, B.prog(T, 0.25, 0.4));
    chrome(g, "SYNTH", W / 2, H * PL(0.3, 0.24), PL(19, 17) * U, 0.9, "t");
    neonScript(g, "how it sings", W / 2, H * PL(0.3, 0.24) + PL(15, 13) * U, PL(8, 6.6) * U, 1.3);
  }
  function sceneDiagram(g, W, H, hy) {
    const S = F.safe, lt = T - BEATS[1], P = F.portrait;
    sun(g, W / 2, hy, PL(20, 11) * U, 1);
    mountains(g, W, hy, 1, 3);
    grid(g, W, H, hy);
    // 16:9: the chain across the sky, waves above, notes below; 9:16: the chain down a column, wave and note beside each box
    const bw = PL(34, 30) * U, bh = PL(12, 12) * U, gap = 14 * U, cy = H * 0.42;
    const pos = P ? [0, 1, 2].map((i) => [S.x + bw / 2, S.y + 20 * U + i * 27 * U]) : [-1, 0, 1].map((k) => [W / 2 + k * (bw + gap), cy]);
    g.save(); // faint chart grid behind the waves
    g.strokeStyle = B.rgba(PAL.cyan, 0.12);
    g.lineWidth = 0.12 * U;
    const gy0 = P ? S.y + 14 * U : cy - 26 * U, gy1 = P ? pos[2][1] + 10 * U : cy - bh;
    for (let x = P ? S.x + bw + 4 * U : S.x; x <= S.r; x += 5 * U) { g.beginPath(); g.moveTo(x, gy0); g.lineTo(x, gy1); g.stroke(); }
    g.restore();
    chain(g, pos, bw, bh, BEATS[1] + 0.15, -1, P);
    const cx0 = S.x + bw + 5 * U, cw = S.r - cx0;
    STEPS.forEach((s, i) => {
      const p = B.prog(lt, 0.6 + i * 0.3, 0.5), [x, y] = pos[i], col = i === 2 ? PAL.magenta : PAL.cyan, o = { size: 4.2 * U, minSize: 3.9 * U, family: TECH, weight: 500, color: PAL.chrome, maxLines: 2, lineH: 1.25, alpha: B.prog(lt, 0.9 + i * 0.2, 0.3) };
      if (P) {
        tube(g, wavePts(s.wave, cx0, y - 3.2 * U, cw, 6 * U, 2.5, p), col, 0.2 * U); // wave level with the box's top half,
        B.text(g, s.body, cx0, y + 1.2 * U, { ...o, align: "left", baseline: "top", maxW: cw }); // the note under it
      } else {
        tube(g, wavePts(s.wave, x - bw / 2, y - bh / 2 - 9 * U, bw, 7 * U, i === 2 ? 3 : 2.5, p), col, 0.2 * U);
        B.text(g, s.body, x, y + bh / 2 + 3 * U, { ...o, size: 4 * U, minSize: 3.8 * U, baseline: "top", maxW: bw + gap * 0.8 });
      }
    });
    glowText(g, "THE SIGNAL CHAIN", W / 2, S.y + PL(5, 3) * U, PL(5, 4.6) * U, PAL.yellow, { alpha: B.prog(lt, 0.1, 0.3), ls: 0.2, maxW: S.w });
  }
  function sceneNumber(g, W, H, hy) {
    const S = F.safe, lt = T - BEATS[2];
    sun(g, W / 2, hy, PL(24, 12) * U, 1);
    mountains(g, W, hy, 1, 5);
    grid(g, W, H, hy);
    const cy = H * PL(0.29, 0.3), size = PL(17, 14) * U;
    // a glowing sine floating in the sky behind the dashboard
    tube(g, wavePts("soft", S.x, cy - PL(19, 17) * U, S.w, PL(7, 6) * U, 6, B.prog(lt, 0.1, 0.8)), PAL.magenta, 0.2 * U, 0.8);
    // the dashboard strip holds the number and both captions, so they read on dark glass, not on the bright sky
    const sw = PL(86, 84) * U, top = cy - 11 * U;
    neonBox(g, W / 2 - sw / 2, top, sw, PL(51, 45) * U, PAL.cyan, B.prog(lt, 0.15, 0.2));
    odometer(g, W / 2 - PL(9, 7) * U, cy + PL(3, 2.5) * U, 440 * B.ease.outCubic(B.prog(lt, 0.3, 1.3)), 3, size, PAL.cyan);
    glowText(g, "Hz", W / 2 + size * 1.55, cy + PL(5, 4) * U, size * 0.45, PAL.magenta, { alpha: B.prog(lt, 0.4, 0.3) });
    glowText(g, "A4 · THE NOTE\nORCHESTRAS TUNE TO", W / 2, cy + PL(22, 20) * U, 4.4 * U, PAL.chrome, { weight: 600, maxW: sw * 0.94, alpha: B.prog(lt, 0.9, 0.3), ls: 0.1 });
    neonScript(g, "440 waves a second", W / 2, cy + PL(33.5, 29.5) * U, PL(6.4, 5.6) * U, BEATS[2] + 0.75, PAL.magenta, 0.035);
  }
  function sceneSteps(g, W, H, hy) {
    const S = F.safe, b3 = BEATS[3];
    sun(g, W / 2, hy, PL(20, 13) * U, 1);
    mountains(g, W, hy, 1, 7);
    grid(g, W, H, hy);
    const arrive = [b3 + 0.1, b3 + 1.25, BEATS[4] + 0.05], i = T < arrive[1] ? 0 : T < arrive[2] ? 1 : 2;
    strip(g, H * PL(0.24, 0.2), b3 - 0.3, i);
    // the card rides down the road from the vanishing point to its stop; the last one rushes past the viewer
    const s = STEPS[i], p = B.prog(T, arrive[i], 0.55, "outCubic"), leave = i < 2 ? B.prog(T, arrive[i + 1] - 0.3, 0.3, "inCubic") : 0;
    const cw = PL(84, 80) * U, chh = PL(38, 30) * U, slotY = H * PL(0.63, 0.69);
    const sc = B.lerp(0.06, 1, p) * (1 + leave * 1.8), y = B.lerp(hy + 1 * U, slotY, p) + leave * H * 0.4;
    g.save();
    g.translate(W / 2, y);
    g.scale(sc, sc);
    g.globalAlpha = 1 - leave;
    const col = i === 2 && T > BEATS[4] + 0.7 ? PAL.magenta : PAL.cyan;
    neonBox(g, -cw / 2, -chh / 2, cw, chh, col);
    glowText(g, s.title, 0, -chh * 0.32, PL(5, 4.6) * U, col, { maxW: cw * 0.9 });
    tube(g, wavePts(s.wave, -cw * 0.4, -chh * 0.06, cw * 0.8, chh * 0.2, 3), PAL.yellow, 0.18 * U);
    B.text(g, s.body, 0, chh * 0.29, { size: PL(4.4, 4.2) * U, minSize: PL(4, 4) * U, family: TECH, weight: 500, color: PAL.chrome, maxW: cw * 0.88, maxLines: 2, lineH: 1.2 });
    g.restore();
  }
  function sceneClose(g, W, H, hy) {
    const lt = T - BEATS[5];
    sun(g, W / 2, hy, PL(26, 16) * U, B.prog(lt, 0, 0.8, "outCubic") * 0.4 + 0.6);
    mountains(g, W, hy, 1, 3);
    grid(g, W, H, hy);
    chrome(g, "SHAPE", W / 2, H * PL(0.3, 0.24), PL(19, 17) * U, BEATS[5] + 0.3, "c");
    neonScript(g, "the wave", W / 2, H * PL(0.3, 0.24) + PL(15, 13) * U, PL(8, 6.6) * U, BEATS[5] + 0.7);
    if (lt > 0.4) strip(g, H * PL(0.72, 0.84), BEATS[5] + 0.4, Math.floor(T * 3) % 3); // all lit well before the end
  }
  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneSteps, sceneClose];

  // ------------------------------------------------------------------ finishing: bloom, scanlines, chromatic fringe, vignette
  function bloom(ctx, W, H) {
    [[4, 3, 0.55], [10, 3, 0.45]].forEach(([div, blur, a], k) => {
      const w = Math.ceil(W / div), h = Math.ceil(H / div), s = B.scratch("syn-bloom-" + k, w, h);
      s.filter = `blur(${blur}px)`;
      s.drawImage(N.canvas, 0, 0, w, h);
      s.filter = "none";
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = a;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(s.canvas, 0, 0, W, H);
      ctx.restore();
    });
  }
  /** Chromatic fringe: keep green, add red scaled up a little more than blue, so colour splits grow toward the edges. */
  function fringe(ctx, W, H) {
    const cp = B.scratch("syn-copy", W, H);
    cp.drawImage(ctx.canvas, 0, 0);
    const chan = (key, col) => {
      const c = B.scratch("syn-ch-" + key, W, H);
      c.drawImage(cp.canvas, 0, 0);
      c.globalCompositeOperation = "multiply";
      c.fillStyle = col;
      c.fillRect(0, 0, W, H);
      return c.canvas;
    };
    const red = chan("r", "#ff0000"), blue = chan("b", "#0000ff");
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = "#00ff00";
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";
    [[red, 1.006], [blue, 1.001]].forEach(([c, s]) => ctx.drawImage(c, (W - W * s) / 2, (H - H * s) / 2, W * s, H * s));
    ctx.restore();
    // the split belongs at the frame edges only: lay the clean picture back over the middle, feathered out
    const k = B.scratch("syn-clean", W, H);
    k.drawImage(cp.canvas, 0, 0);
    k.globalCompositeOperation = "destination-in";
    k.setTransform(W / 2, 0, 0, H / 2, W / 2, H / 2);
    k.fillStyle = B.radial(k, 0, 0, 0.8, 1.25, [[0, "#000"], [1, "rgba(0,0,0,0)"]]);
    k.fillRect(-1, -1, 2, 2);
    k.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(k.canvas, 0, 0);
  }

  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    T = t;
    const hy = horizon(t);
    sky(ctx, W, H, hy);
    N = B.scratch("syn-neon", W, H);
    stars(N, W, hy);
    SCENES[B.beat(t, BEATS, DUR).i](N, W, H, hy);
    ctx.drawImage(N.canvas, 0, 0);
    bloom(ctx, W, H);
    // the flash wipe: a bright horizontal band opening from the horizon to a white-magenta frame flash
    FLASHES.forEach((at) => {
      const d = t - at;
      if (Math.abs(d) > 0.3) return;
      const k = 1 - Math.abs(d) / 0.3, bh = H * B.ease.inQuad(k) * 1.2;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = B.linear(ctx, 0, hy - bh / 2, 0, hy + bh / 2, [[0, "rgba(255,43,214,0)"], [0.5, `rgba(255,240,255,${0.95 * k})`], [1, "rgba(255,43,214,0)"]]);
      ctx.fillRect(0, hy - bh / 2, W, bh);
      ctx.restore();
    });
    B.scanlines(ctx, W, H, { alpha: 0.08 });
    fringe(ctx, W, H);
    B.vignette(ctx, W, H, { amount: 0.55, inner: 0.45 });
  }

  // ------------------------------------------------------------------ sound: detuned pad swells, gated drum slams, arpeggio sweeps, neon buzz-clicks
  SOUND.define("synth-gate", (v) => {
    // punchy gated drum: a big snare-ish burst through a long room, cut off abruptly
    v.noise({ filter: "bandpass", f: 1800, q: 0.7, a: 0.002, hold: 0.16, len: 0.03, peak: 0.5, shape: "lin" });
    v.tone({ f: 190, f2: 70, glide: 0.12, a: 0.002, len: 0.2, peak: 0.55 });
  }, { verb: 0.6 });
  SOUND.define("synth-lead", (v, o) => {
    // bright detuned saw pluck for arpeggio runs
    const f = v.hz(o.note || "A4");
    v.tone({ type: "sawtooth", f, a: 0.003, len: 0.18, peak: 0.07, detune: -8 });
    v.tone({ type: "sawtooth", f, a: 0.003, len: 0.18, peak: 0.07, detune: 8 });
    v.tone({ type: "square", f: f / 2, a: 0.003, len: 0.12, peak: 0.03 });
  }, { verb: 0.4 });
  SOUND.define("synth-buzz", (v) => {
    // neon switching on: a click, then a short electric buzz
    v.noise({ filter: "highpass", f: 3000, a: 0.0005, len: 0.015, peak: 0.3 });
    v.tone({ type: "sawtooth", f: 120, at: 0.01, a: 0.005, hold: 0.08, len: 0.05, peak: 0.06 });
    v.tone({ type: "square", f: 240, at: 0.01, a: 0.005, hold: 0.06, len: 0.04, peak: 0.025 });
  }, { verb: 0.15 });

  function score(k) {
    const am = ["A3", "C4", "E4", "A4", "C5", "E5", "A5", "C6"];
    k.bed("pad", 0, DUR, { notes: ["A2", "E3", "A3", "C4", "E4"], gain: 0.7, bright: 900 });
    k.bed("pulse", 0, DUR, { bpm: 112, gain: 0.6 });
    k.seq(0.25, 0.07, am, { voice: "synth-lead", gain: 0.8 }); // the rising sweep with the sun and grid
    k.at(0.3, "riser", { dur: 0.6, gain: 0.4 });
    k.at(0.9, "synth-gate", { gain: 1 }).at(0.9, "boom", { gain: 0.5 }).at(1.15, "sparkle", { gain: 0.4 });
    [1.3, 1.4, 1.5, 1.6].forEach((at) => k.at(at, "synth-buzz", { gain: 0.6 }));
    // pan up to the chain
    k.at(1.9, "whoosh", { dur: 0.6, gain: 0.5 });
    [2.35, 2.6, 2.85].forEach((at, i) => k.at(at, "synth-buzz").at(at + 0.2, "synth-lead", { note: am[2 + i * 2] }));
    k.at(2.8, "swell", { dur: 1.2, gain: 0.5 });
    // flashes, the odometer, the script
    FLASHES.forEach((at) => k.at(at - 0.3, "riser", { dur: 0.3, gain: 0.5 }).at(at, "synth-gate", { gain: 0.9 }));
    k.repeat(4.8, 0.08, 14, "tick", { gain: 0.35, vary: 1 });
    k.at(6.0, "synth-buzz").at(6.1, "synth-buzz", { pitch: 2 }).at(6.0, "swell", { dur: 0.7, gain: 0.4 });
    // steps: each card arrives on a gated hit with a short run
    [6.8, 7.95, 9.05].forEach((at, i) => k.at(at, "whoosh", { dur: 0.5, gain: 0.4 }).seq(at + 0.3, 0.06, am.slice(i, i + 4), { voice: "synth-lead", gain: 0.6 }).at(at + 0.5, "synth-gate", { gain: 0.6 }));
    k.at(9.7, "synth-buzz", { pitch: 5 }).at(9.75, "chord", { notes: ["A4", "C5", "E5"], gain: 0.4 });
    // close
    k.at(11.1, "synth-gate").at(11.1, "boom", { gain: 0.5 }).at(11.45, "sparkle", { gain: 0.4 });
    [11.5, 11.6, 11.7].forEach((at) => k.at(at, "synth-buzz", { gain: 0.5 }));
    k.seq(11.8, 0.08, am.slice().reverse(), { voice: "synth-lead", gain: 0.5 });
  }

  Player.register({
    id: "synthwave",
    name: "Synthwave",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800;900&family=Monoton&display=swap",
      faces: ['900 20px "Orbitron"', '800 20px "Orbitron"', '700 20px "Orbitron"', '600 20px "Orbitron"', '500 20px "Orbitron"', '400 20px "Monoton"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Oscillator, filter", "Envelope", "Close"],
    stills: [1.9, 4.0, 6.3, 7.6, 10.2, 12.3],
    draw,
    score,
  });
})();
