/* 05 Cosmic Swirl - reference animation.
 * Topic (setting, replace it): "How is a star born?" - a cold cloud of gas collapses, spins into a disc and ignites.
 * Rendering (keep it): an indigo sky with a nebula river, dust lanes and three depths of stars; inside the cloud, liquid concentric bands of loud complementary ink that churn and drift, each edged by a
 * dark key line printed slightly off register; the bands fold into a mirror-symmetric mandala on the "right" moment;
 * fine gold and pale cyan star-map linework (graduated ring, dotted orbits with open arrowheads, leaders to
 * small-caps labels, cream chips); swollen display lettering that pours in and keeps melting a little; sunburst
 * tongues round key objects. Finishing: worn poster stock (cream fibres, ink drop-out speckles cycling at 8 fps),
 * additive glows with a slow pulse, a strong dark vignette.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = {
    sky: "#0b0a24",
    violet: "#5b2a86",
    magenta: "#e0237d",
    green: "#3fcf5a",
    tangerine: "#ff7a1a",
    blue: "#2b5fe0",
    gold: "#e6c36a",
    cream: "#fbf1dc",
    cyan: "#9fe6f2", // the card's "light cyan" chart line
  };
  const BANDS = [PAL.magenta, PAL.green, PAL.tangerine, PAL.blue, PAL.violet, PAL.gold]; // complementary neighbours
  const DISPLAY = "Sniglet", SMALLCAPS = "Cormorant SC";
  const DUR = 13.5;
  const BEATS = [0, 2.4, 4.9, 7.4, 9.6, 11.3];
  let T = 0, U = 1;

  // ---- cosmic-poster helpers (reuse these)
  /**
   * The liquid band swirl: concentric rings whose radius is warped by slow noise (free) or by a mirror-folded angle
   * (mandala, sym 0..1, n segments); rings drift outward (or inward) with s = rings travelled; each ring keeps its
   * colour as it moves. Fills are flat ink; the dark key lines are stroked afterwards, a hair down-right (off register).
   * o: { R (cloud radius), bw (band width), s, sym, n, rot, squash, glowCore }
   */
  function bandSwirl(ctx, cx, cy, o) {
    const { R, bw } = o, ph = B.fract(o.s), shift = Math.floor(o.s), N = 120, nRings = Math.ceil(R / bw) + 2;
    const seg = B.TAU / (o.n || 8);
    const warp = (k, a) => {
      const free = 0.38 * bw * Math.sin(3 * a + T * 0.6 + k * 0.5) + 0.55 * bw * B.noise2(Math.cos(a) * 1.3 + k * 0.22, Math.sin(a) * 1.3 + T * 0.22, 7);
      if (!o.sym) return free;
      const x = Math.abs(((((a + o.rot) % seg) + seg) % seg) - seg / 2); // folded angle: mirror symmetric
      const sym = 0.42 * bw * Math.cos(x * (B.TAU / seg) * 2) + 0.3 * bw * B.noise2(x * 4 + k * 0.3, T * 0.2, 9);
      return B.lerp(free, sym, o.sym);
    };
    const ringPts = (k, extra = 0) => {
      const base = (k + ph) * bw + extra, out = [];
      for (let i = 0; i < N; i++) {
        const a = (i / N) * B.TAU, r = Math.max(0, base + warp(k, a));
        out.push([Math.cos(a) * r, Math.sin(a) * r]);
      }
      return out;
    };
    const edge = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * B.TAU, r = R * (1 + 0.05 * B.noise2(Math.cos(a) * 1.5, Math.sin(a) * 1.5 + T * 0.15, 3));
      edge.push([Math.cos(a) * r, Math.sin(a) * r]);
    }
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(o.tilt || 0);
    ctx.scale(1, o.squash ?? 1);
    ctx.rotate(o.spin || 0);
    ctx.save();
    ctx.beginPath();
    B.poly(ctx, edge, true);
    ctx.clip();
    const rings = [];
    for (let k = nRings; k >= 0; k--) {
      const pts = ringPts(k);
      rings.push(pts);
      ctx.beginPath();
      B.poly(ctx, pts, true);
      ctx.fillStyle = BANDS[(((k - shift) % BANDS.length) + BANDS.length) % BANDS.length];
      ctx.fill();
    }
    // misregistration: the key-line plate lands a little down and to the right of the colour plate
    ctx.translate(0.18 * U, 0.2 * U);
    ctx.strokeStyle = PAL.sky;
    ctx.lineWidth = 0.42 * U;
    ctx.lineJoin = "round";
    ctx.beginPath();
    rings.forEach((pts) => B.poly(ctx, pts, true));
    ctx.stroke();
    ctx.restore();
    ctx.translate(0.18 * U, 0.2 * U);
    ctx.strokeStyle = PAL.sky;
    ctx.lineWidth = 0.7 * U;
    ctx.beginPath();
    B.poly(ctx, edge, true);
    ctx.stroke();
    ctx.restore();
  }
  /** Sunburst: alternating long and short flame-like tongues round a point, flat ink with an off-register key line. */
  function sunburst(ctx, x, y, r0, r1, n, rot, p, cols) {
    if (p <= 0.01) return;
    const tongue = (i) => (c) => {
      const a = rot + (i / n) * B.TAU, len = (i % 2 ? 0.6 : 1) * (r1 - r0) * p, w = (B.TAU / n) * 0.42;
      const wav = Math.sin(T * 3 + i) * 0.08;
      const P = (rr, da) => [x + Math.cos(a + da) * rr, y + Math.sin(a + da) * rr];
      const b0 = P(r0, -w), b1 = P(r0, w), tip = P(r0 + len, wav), c0 = P(r0 + len * 0.55, -w * 0.7 + wav), c1 = P(r0 + len * 0.55, w * 0.9 + wav);
      c.moveTo(b0[0], b0[1]);
      c.quadraticCurveTo(c0[0], c0[1], tip[0], tip[1]);
      c.quadraticCurveTo(c1[0], c1[1], b1[0], b1[1]);
      c.closePath();
    };
    for (let i = 0; i < n; i++) {
      ctx.beginPath();
      tongue(i)(ctx);
      ctx.fillStyle = cols[i % cols.length];
      ctx.fill();
    }
    ctx.save();
    ctx.translate(0.18 * U, 0.2 * U);
    ctx.strokeStyle = PAL.sky;
    ctx.lineWidth = 0.35 * U;
    ctx.beginPath();
    for (let i = 0; i < n; i++) tongue(i)(ctx);
    ctx.stroke();
    ctx.restore();
  }
  /**
   * Swollen display heading that pours into place column by column (each column fills top-down in its own mould and
   * sloshes at the bottom), keeps a slight melting wobble, and can drip away (meltAt). Rendered once to an offscreen
   * card (fill, fat outline in the complementary colour, a dark key line off register), drawn back in thin slices.
   * Shrinks to o.maxW (with its fat outline) so it never runs off the frame.
   */
  function meltHeading(ctx, lines, x, y, size, o) {
    if (T < o.at) return;
    ctx.save();
    ctx.font = B.font(size, DISPLAY, 800);
    let wMax = Math.max(...lines.map((l) => ctx.measureText(l).width));
    if (o.maxW && wMax + size * 0.3 > o.maxW) {
      const k = o.maxW / (wMax + size * 0.3);
      size *= k;
      wMax *= k;
    }
    ctx.restore();
    const fill = o.fill || PAL.tangerine, line = o.outline || PAL.blue, key = `cs-head:${lines.join("|")}:${size.toFixed(1)}:${fill}`, pad = size * 0.3;
    const cw = Math.ceil(wMax + 2 * pad), chH = Math.ceil(lines.length * size * 1.02 + 2 * pad);
    const card = B.layer(key, cw, chH, (g) => {
      g.font = B.font(size, DISPLAY, 800);
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.lineJoin = "round";
      lines.forEach((l, i) => {
        const yy = pad + size * 1.02 * (i + 0.5), xx = cw / 2, off = Math.max(1, size * 0.018);
        g.strokeStyle = PAL.sky;
        g.lineWidth = size * 0.3;
        g.strokeText(l, xx + off, yy + off);
        g.strokeStyle = line;
        g.lineWidth = size * 0.22;
        g.strokeText(l, xx, yy);
        g.fillStyle = fill;
        g.fillText(l, xx, yy);
        g.strokeStyle = PAL.sky;
        g.lineWidth = size * 0.028;
        g.strokeText(l, xx + off, yy + off);
      });
    });
    const sw = Math.max(2, Math.round(size * 0.05)), x0 = Math.round(x - cw / 2), y0 = Math.round(y - chH / 2);
    for (let sx = 0; sx < cw; sx += sw) {
      const f = sx / cw, pour = B.prog(T, o.at + f * 0.35 + B.hash01(sx, "p") * 0.08, 0.55);
      if (pour <= 0) continue;
      const fillH = Math.max(1, chH * B.clamp(B.ease.outBounce(pour) + 0.06 * Math.sin(pour * 9) * (1 - pour))); // the mould fills, sloshing
      let dy = 0, stretch = 0, alpha = 1;
      dy += Math.sin(sx * 0.018 + T * 1.6) * size * 0.035; // the ongoing slight melt
      if (o.meltAt && T > o.meltAt) {
        const m = Math.max(0, T - o.meltAt - B.hash01(sx, "m") * 0.25);
        dy += m * m * size * 9;
        stretch += m * 2.5;
        alpha = 1 - B.clamp(m / 0.45);
      }
      if (alpha <= 0) continue;
      ctx.globalAlpha = alpha * (o.alpha ?? 1);
      const sh = pour < 1 ? Math.min(chH, fillH) : chH;
      ctx.drawImage(card, sx, 0, Math.min(sw, cw - sx), sh, x0 + sx, y0 + dy, Math.min(sw, cw - sx), sh * (1 + stretch));
    }
    ctx.globalAlpha = 1;
  }
  function smallCaps(ctx, str, x, y, size, o = {}) {
    return B.text(ctx, str, x, y, { size, family: SMALLCAPS, weight: 700, color: o.color || PAL.gold, letterSpacing: 0.1, maxW: o.maxW, maxLines: o.maxLines ?? 1, minSize: size * 0.7, align: o.align, alpha: o.alpha, reveal: o.reveal, lineH: 1.05 });
  }
  /** Cream chip outlined in dark ink (outline off register), small-caps text. */
  function chip(ctx, str, x, y, size, s, o = {}) {
    if (s <= 0.01) return;
    const m = B.measureText(ctx, str, { size, family: SMALLCAPS, weight: 700, letterSpacing: 0.08, maxW: o.maxW, lineH: 1.05 });
    const w = m.width + size * 1.6, h = m.height + size * 0.9;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(s, s);
    ctx.globalAlpha *= o.alpha ?? 1;
    ctx.beginPath();
    B.roundRect(ctx, -w / 2, -h / 2, w, h, h * 0.3);
    ctx.fillStyle = PAL.cream;
    ctx.fill();
    ctx.translate(0.18 * U, 0.2 * U);
    ctx.lineWidth = 0.5 * U;
    ctx.strokeStyle = PAL.sky;
    ctx.stroke();
    ctx.translate(-0.18 * U, -0.2 * U);
    B.text(ctx, str, 0, size * 0.05, { size: m.size, family: SMALLCAPS, weight: 700, color: PAL.sky, letterSpacing: 0.08, maxW: o.maxW, lineH: 1.05 });
    ctx.restore();
  }
  /** Fine dotted orbit arc (ellipse from a0 to a1) drawn on to p, with a small open arrowhead. */
  function orbitArc(ctx, cx, cy, rx, ry, a0, a1, p, color, o = {}) {
    if (p <= 0) return;
    const pts = [];
    for (let i = 0; i <= 60; i++) {
      const a = a0 + ((a1 - a0) * i) / 60;
      pts.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
    }
    B.arrow(ctx, pts, { p, width: Math.max(1, 0.32 * U), dots: 1.3 * U, color, head: o.head ?? 2.2 * U, headStyle: o.head === 0 ? "none" : "open", alpha: o.alpha });
  }
  /** Graduated degree ring engraved on (sweeps round to p): ticks every 5 degrees, long ones every 30. */
  function degreeRing(ctx, cx, cy, r, p, alpha) {
    if (p <= 0) return;
    ctx.save();
    ctx.globalAlpha *= alpha;
    ctx.strokeStyle = PAL.gold;
    ctx.lineWidth = Math.max(1, 0.14 * U);
    ctx.beginPath();
    ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + B.TAU * p);
    ctx.stroke();
    ctx.beginPath();
    for (let i = 0; i < 72 * p; i++) {
      const a = -Math.PI / 2 + (i / 72) * B.TAU, l = i % 6 === 0 ? 2.2 * U : 0.9 * U;
      ctx.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.lineTo(cx + Math.cos(a) * (r + l), cy + Math.sin(a) * (r + l));
    }
    ctx.stroke();
    ctx.restore();
  }
  /** Mid-depth twinkling stars and a few bright ones with a soft halo and thin spikes; `warp` streaks them radially. */
  function stars(ctx, W, H, warp, appear, avoid) { // avoid(x, y): no star behind text
    const r = B.rng("cs-stars"), cx = W / 2, cy = H / 2;
    ctx.save();
    ctx.lineCap = "round";
    for (let i = 0; i < 90; i++) {
      const x = r() * W, y = r() * H, ph = r(), per = r.range(1.2, 3), sz = r.range(0.12, 0.32) * U, at = r() * 1.6;
      const vis = B.span(appear, at, at + 0.2);
      if (vis <= 0 || avoid(x, y)) continue;
      const tw = 0.45 + 0.55 * Math.pow(0.5 + 0.5 * Math.sin(B.TAU * (T / per + ph)), 2);
      ctx.globalAlpha = vis * tw;
      if (warp > 0.01) {
        const dx = x - cx, dy = y - cy;
        ctx.strokeStyle = PAL.cream;
        ctx.lineWidth = sz * 1.4;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + dx * warp * 0.5, y + dy * warp * 0.5);
        ctx.stroke();
      } else {
        ctx.fillStyle = i % 5 ? PAL.cream : PAL.cyan;
        ctx.beginPath();
        B.circle(ctx, x, y, sz);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    for (let i = 0; i < 7; i++) {
      const x = r.range(0.05, 0.95) * W, y = r.range(0.05, 0.95) * H, s = r.range(1.4, 2.6) * U, spikes = i % 2 ? 4 : 6;
      const vis = B.span(appear, 0.3 + i * 0.18, 0.6 + i * 0.18), pulse = 1 + 0.18 * Math.sin(T * 2.1 + i);
      if (vis <= 0 || avoid(x, y)) continue;
      B.glow(ctx, x, y, s * 4 * pulse, i % 3 ? PAL.cream : PAL.cyan, 0.35 * vis, { add: true });
      ctx.strokeStyle = B.rgba(PAL.cream, 0.85 * vis);
      ctx.lineWidth = Math.max(1, 0.12 * U);
      ctx.beginPath();
      for (let k = 0; k < spikes; k++) {
        const a = (k / spikes) * B.TAU + 0.3, l = s * (k % 2 ? 2.2 : 3.4) * pulse * (1 + warp * 3);
        ctx.moveTo(x, y);
        ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l);
      }
      ctx.stroke();
      ctx.fillStyle = B.rgba("#ffffff", vis);
      ctx.beginPath();
      B.circle(ctx, x, y, s * 0.28);
      ctx.fill();
    }
    ctx.restore();
  }

  // ---- the sky (cached): night, nebula river, dust lanes, far stars
  function sky(W, H) {
    return B.layer("cs-sky", W, H, (g, w, h) => {
      const cell = 4, lw = Math.ceil(w / cell), lh = Math.ceil(h / cell), lo = B.canvas(lw, lh), lg = lo.getContext("2d"), img = lg.createImageData(lw, lh);
      const [s0, v0, m0] = [PAL.sky, PAL.violet, PAL.magenta].map(B.rgb), D = Math.hypot(w, h);
      for (let y = 0; y < lh; y++)
        for (let x = 0; x < lw; x++) {
          const px = x * cell, py = y * cell;
          // distance from the diagonal river (lower left to upper right)
          const d = Math.abs((px / w) * 0.75 + (py / h) - 0.95) * (D / h);
          const n = B.fbm(px / (D * 0.12), py / (D * 0.12), 4, 5);
          let neb = Math.exp(-Math.pow(d / 0.42, 2)) * (0.55 + 0.55 * n);
          const dust = B.smooth(0.15, 0.45, B.fbm(px / (D * 0.08) + 9, py / (D * 0.05), 3, 8));
          neb *= 1 - 0.75 * dust * Math.exp(-Math.pow(d / 0.3, 2));
          const hot = B.clamp(neb * neb * 0.9);
          const i = (y * lw + x) * 4;
          for (let c = 0; c < 3; c++) img.data[i + c] = B.clamp(s0[c] + (v0[c] - s0[c]) * B.clamp(neb * 1.2) + (m0[c] - v0[c]) * hot * 0.55, 0, 255);
          img.data[i + 3] = 255;
        }
      lg.putImageData(img, 0, 0);
      g.imageSmoothingQuality = "high";
      g.drawImage(lo, 0, 0, w, h);
      const r = B.rng("far"), u = Math.min(w, h) / 100;
      for (let i = 0; i < (w * h) / (u * u * 2.2); i++) {
        g.fillStyle = `rgba(251,241,220,${r.range(0.15, 0.6).toFixed(2)})`;
        g.fillRect(r() * w, r() * h, Math.max(1, 0.1 * u), Math.max(1, 0.1 * u));
      }
    });
  }
  /** Worn poster stock: a cream fibre sheet to multiply, and ink drop-out speckles; three variants cycled at 8 fps. */
  function stock(W, H, v) {
    return {
      fibre: B.layer("cs-fibre" + v, W, H, (g, w, h) => {
        const r = B.rng("fib" + v), u = Math.min(w, h) / 100;
        g.fillStyle = PAL.cream;
        g.fillRect(0, 0, w, h);
        g.lineCap = "round";
        for (let i = 0; i < (w * h) / (u * u * 0.9); i++) {
          const x = r() * w, y = r() * h, a = r() * B.TAU, l = r.range(0.4, 1.8) * u;
          g.strokeStyle = `rgba(150,110,60,${r.range(0.15, 0.4).toFixed(2)})`;
          g.lineWidth = Math.max(0.6, 0.08 * u);
          g.beginPath();
          g.moveTo(x, y);
          g.quadraticCurveTo(x + Math.cos(a + 0.7) * l * 0.5, y + Math.sin(a + 0.7) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l);
          g.stroke();
        }
      }),
      speck: B.layer("cs-speck" + v, W, H, (g, w, h) => {
        const r = B.rng("spk" + v), u = Math.min(w, h) / 100;
        for (let i = 0; i < (w * h) / (u * u * 9); i++) {
          g.fillStyle = `rgba(251,241,220,${r.range(0.25, 0.75).toFixed(2)})`;
          g.beginPath();
          g.ellipse(r() * w, r() * h, r.range(0.05, 0.22) * u, r.range(0.04, 0.16) * u, r() * 3, 0, B.TAU);
          g.fill();
        }
      }),
    };
  }

  // ---- layout by aspect, camera per beat
  function layout(W, H) {
    const F = B.frame(W, H), P = F.portrait, u = F.u;
    return {
      F, P, u,
      R: P ? 0.38 * W : 0.34 * H,
      // [anchor x, anchor y, zoom] of the cloud's centre per beat: title, diagram, number, steps, step 3, close
      cams: P ? [[0.5, 0.58, 0.82], [0.5, 0.5, 1], [0.5, 0.63, 0.74], [0.5, 0.47, 0.8], [0.5, 0.47, 0.8], [0.5, 0.66, 0.75]]
        : [[0.7, 0.53, 0.95], [0.5, 0.53, 1], [0.76, 0.53, 0.88], [0.5, 0.5, 0.82], [0.5, 0.5, 0.82], [0.74, 0.5, 0.8]],
      head: P ? 12.5 * u : 10 * u,
      label: P ? 4.4 * u : 4.0 * u,
      chip: P ? 4.4 * u : 3.8 * u,
    };
  }
  function camera(L, W, H, t) {
    const at = (i) => L.cams[i];
    let c = at(0).slice();
    const moves = [[2.3, 3.1, 1], [4.8, 5.6, 2], [7.3, 8.0, 3], [11.2, 12.0, 5]];
    for (const [a, b, i] of moves) {
      const k = B.span(t, a, b, "inOutCubic");
      if (k > 0) c = c.map((v, j) => B.lerp(v, at(i)[j], k));
    }
    return { x: c[0] * W, y: c[1] * H, z: c[2] * (1 + 0.012 * Math.sin(t * 0.7)) };
  }

  // ---- the story state over time
  function cloudState(t) {
    const bloom = B.span(t, 0.1, 1.3, "outCubic"); // colour ripples out from the centre
    const shrink = 1 - 0.28 * B.span(t, 8.05, 9.0, "inOutSine") * (1 - B.span(t, 11.2, 12.0, "inOutSine"));
    const squash = 1 - 0.55 * B.span(t, 9.0, 9.7, "inOutSine") * (1 - B.span(t, 11.2, 12.0, "inOutSine"));
    const sym = B.span(t, 9.95, 10.7, "inOutSine"); // right: the swirl folds into a calm symmetric mandala
    const spin = 0.08 * t + 1.6 * B.span(t, 9.0, 11.0, "inOutSine") + 6.3 * B.span(t, 11.1, 11.8, "inOutCubic"); // kaleidoscope spin into the close
    const s = 0.32 * t - 1.7 * B.span(t, 8.0, 9.2, "inOutSine"); // ring drift: outward, but pulled inward while gravity acts
    const ignite = B.span(t, 9.9, 10.3) + 0.6 * B.span(t, 12.0, 12.6);
    return { bloom, shrink, squash, sym, spin, s, ignite };
  }

  // ---- frame
  function draw(ctx, W, H, t) {
    T = t;
    const L = layout(W, H), F = L.F, P = L.P, u = L.u;
    U = u;
    const cam = camera(L, W, H, t), st = cloudState(t), R = L.R * cam.z;
    // sky (slight parallax with the camera), nebula pulse, stars
    ctx.drawImage(sky(W, H), (cam.x - W / 2) * 0.08 - W * 0.02, (cam.y - H / 2) * 0.08 - H * 0.02, W * 1.04, H * 1.04);
    B.glow(ctx, W * 0.42, H * 0.58, Math.hypot(W, H) * 0.35, PAL.violet, 0.16 * (1 + 0.25 * Math.sin(t * 0.9)), { add: true });
    const warp = Math.sin(Math.PI * B.span(t, 2.2, 2.75)) * 0.9;
    const inR = (rs) => (x, y) => rs.some(([a, b, c, d]) => x > a * W && x < c * W && y > b * H && y < d * H);
    stars(ctx, W, H, warp, t, inR(P ? [[0.02, 0.19, 0.98, 0.43], [0.02, 0.7, 0.98, 0.8]] : [[0.02, 0.1, 0.6, 0.72], [0.15, 0.8, 0.85, 0.95], [0.58, 0.15, 0.98, 0.45], [0.72, 0.68, 0.98, 0.9]]));
    // the cloud: liquid bands, a glowing core, sunburst when it ignites
    const Rc = R * st.bloom * st.shrink;
    if (Rc > 2) {
      B.glow(ctx, cam.x, cam.y, Rc * 1.5, PAL.magenta, 0.18 * (1 + 0.15 * Math.sin(t * 1.3)), { add: true });
      if (st.ignite > 0) sunburst(ctx, cam.x, cam.y, Rc * 0.92, Rc * (P ? 1.5 : 1.45), 24, t * 0.1, B.ease.outBack(B.clamp(st.ignite), 1.4), [PAL.tangerine, PAL.gold]);
      bandSwirl(ctx, cam.x, cam.y, { R: Rc, bw: L.R * cam.z * 0.12, s: st.s, sym: st.sym, n: 8, rot: 0, squash: st.squash, tilt: -0.35 * (1 - st.squash) * 1.6, spin: st.spin * 0.25 });
      const coreR = Rc * (0.11 + 0.05 * st.ignite);
      B.glow(ctx, cam.x, cam.y, coreR * (2.4 + 0.8 * st.ignite) * (1 + 0.12 * Math.sin(t * 2.4)), PAL.cream, 0.45 + 0.2 * st.ignite, { add: true });
      B.glow(ctx, cam.x, cam.y, coreR * 1.1, "#ffffff", 0.35 + 0.4 * st.ignite, { add: true });
    }

    // ---- beat 1: the heading pours in, then melts away into the warp
    const H1 = P ? [W / 2, 0.255 * H] : [0.27 * W, 0.42 * H];
    meltHeading(ctx, ["HOW A STAR", "IS BORN"], H1[0], H1[1], L.head, { at: 0.45, meltAt: 2.15, maxW: P ? 0.9 * W : 0.52 * W });
    smallCaps(ctx, "from a cold cloud to a burning sun", P ? W / 2 : 0.27 * W, P ? 0.35 * H : 0.64 * H, L.label * 1.05, { alpha: B.span(t, 1.2, 1.6) * (1 - B.span(t, 2.1, 2.35)), maxW: P ? F.safe.w : 0.44 * W });

    // ---- beat 2: star-map overlay on the cloud
    const dA = B.span(t, 2.7, 3.0) * (1 - B.span(t, 4.75, 4.95));
    if (dA > 0) {
      degreeRing(ctx, cam.x, cam.y, R * 1.14, B.span(t, 2.7, 3.5, "inOutSine"), 0.85 * dA);
      // gravity: dotted orbit arcs spiralling in, with open arrowheads
      for (let i = 0; i < 3; i++) {
        const a0 = -Math.PI / 2 + (i * B.TAU) / 3, p = B.span(t, 3.4 + i * 0.12, 3.95 + i * 0.12, "inOutSine");
        const pts = [];
        for (let j = 0; j <= 30; j++) {
          const f = j / 30, a = a0 + f * 1.1, rr = R * B.lerp(1.32, 0.62, f);
          pts.push([cam.x + Math.cos(a) * rr, cam.y + Math.sin(a) * rr]);
        }
        B.arrow(ctx, pts, { p, width: Math.max(1.5, 0.55 * u), dots: 1.7 * u, color: PAL.cyan, head: 3 * u, headStyle: "open", alpha: dA });
      }
      const leader = (from, to, a) => {
        ctx.save();
        ctx.globalAlpha = dA * a;
        ctx.strokeStyle = PAL.gold;
        ctx.lineWidth = Math.max(1, 0.14 * u);
        ctx.beginPath();
        ctx.moveTo(from[0], from[1]);
        ctx.lineTo(to[0], to[1]);
        ctx.stroke();
        ctx.fillStyle = PAL.gold;
        ctx.beginPath();
        B.circle(ctx, to[0], to[1], 0.45 * u);
        ctx.fill();
        ctx.restore();
      };
      const cl = P ? [W / 2, cam.y - R * 1.36] : [0.19 * W, 0.2 * H];
      chip(ctx, P ? "a cold cloud of gas and dust" : "a cold cloud\nof gas and dust", cl[0], cl[1], L.chip, B.pop(t, 3.0, 0.45) * dA, { maxW: P ? 0.8 * W : 0.3 * W });
      const ca = P ? -Math.PI / 2 : -2.4;
      leader([cl[0] + (P ? 0 : 0.08 * W), cl[1] + (P ? 2.5 : 4) * u], [cam.x + Math.cos(ca) * R * 0.9, cam.y + Math.sin(ca) * R * 0.9], B.span(t, 3.1, 3.3));
      const gp = P ? [W / 2, cam.y + R * 1.3] : [0.85 * W, 0.8 * H];
      smallCaps(ctx, P ? "gravity pulls it inward" : "gravity pulls\nit inward", gp[0], gp[1], L.label, { alpha: dA * B.span(t, 3.8, 4.1), maxW: P ? F.safe.w : 0.22 * W, maxLines: 2 });
      leader([gp[0] - (P ? 0 : 6 * u), gp[1] - (P ? 2.5 : 5) * u], [cam.x + Math.cos(P ? 1.57 : 0.7) * R * 0.98, cam.y + Math.sin(P ? 1.57 : 0.7) * R * 0.98], B.span(t, 3.9, 4.1));
      const co = P ? [0.8 * W, cam.y - R * 1.0] : [0.85 * W, 0.24 * H];
      smallCaps(ctx, "core", co[0], co[1], L.label * 1.1, { alpha: dA * B.span(t, 4.1, 4.3) });
      const cr = R * 0.2, ck = B.span(t, 4.1, 4.35); // the core gets its own gold ring, and the leader ends on it
      ctx.save(); ctx.globalAlpha = dA * ck; ctx.strokeStyle = PAL.gold; ctx.lineWidth = Math.max(1.5, 0.3 * u); ctx.beginPath(); ctx.arc(cam.x, cam.y, cr, 0, B.TAU); ctx.stroke(); ctx.restore();
      const cd = Math.atan2(co[1] + 2 * u - cam.y, co[0] - (P ? 3 : 4) * u - cam.x);
      leader([co[0] - (P ? 3 : 4) * u, co[1] + 2 * u], [cam.x + Math.cos(cd) * cr, cam.y + Math.sin(cd) * cr], B.span(t, 4.15, 4.35));
    }
    // ripple: a double ring of loud ink spreads from the centre and carries the change of scene
    const rp = B.span(t, 4.7, 5.25, "inCubic");
    if (rp > 0 && rp < 1) {
      const rr = rp * Math.hypot(W, H) * 0.75;
      ctx.save();
      ctx.lineWidth = 2.2 * u;
      ctx.strokeStyle = PAL.green;
      ctx.beginPath();
      ctx.arc(cam.x, cam.y, rr, 0, B.TAU);
      ctx.stroke();
      ctx.strokeStyle = PAL.magenta;
      ctx.beginPath();
      ctx.arc(cam.x, cam.y, Math.max(0, rr - 2.2 * u), 0, B.TAU);
      ctx.stroke();
      ctx.restore();
    }

    // ---- beat 3: the key number, counting up over a fine graduated scale, framed by rays when it lands
    const nA = B.span(t, 5.15, 5.4) * (1 - B.span(t, 7.15, 7.45));
    if (nA > 0) {
      const N = P ? [W / 2, 0.27 * H] : [0.33 * W, 0.4 * H], ns = P ? 14 * u : 12 * u, land = B.span(t, 6.35, 6.7, "outBack");
      const sw = P ? 0.8 * W : 0.44 * W, sy = N[1] + ns * 0.95, sx0 = N[0] - sw / 2, sp = B.span(t, 5.25, 5.8, "inOutSine");
      ctx.save();
      ctx.globalAlpha = nA;
      // the burst rises from the scale line like a sunrise, so the captions under the line stay clear
      B.clip(ctx, (c) => c.rect(0, 0, W, sy), () => sunburst(ctx, N[0], N[1], ns * 0.6, ns * (P ? 3.0 : 2.4), 28, -t * 0.08, land * 0.85, [PAL.magenta, PAL.violet]));
      const k = B.prog(t, 5.35, 1.0, "inOutCubic"), bump = 1 + 0.12 * Math.exp(-6 * Math.max(0, t - 6.35)) * Math.sin(Math.max(0, t - 6.35) * 18) * (t > 6.35 ? 1 : 0);
      ctx.translate(N[0], N[1]);
      ctx.scale(bump, bump);
      const txt = B.counter(k, 10000000);
      ctx.font = B.font(ns, DISPLAY, 800);
      const tw = ctx.measureText(txt).width, sc = Math.min(1, (P ? F.safe.w : 0.56 * W) / (tw + ns * 0.4));
      ctx.scale(sc, sc);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      ctx.strokeStyle = PAL.sky;
      ctx.lineWidth = ns * 0.3;
      ctx.strokeText(txt, 0.02 * ns, 0.02 * ns);
      ctx.strokeStyle = PAL.magenta;
      ctx.lineWidth = ns * 0.22;
      ctx.strokeText(txt, 0, 0);
      ctx.fillStyle = PAL.green;
      ctx.fillText(txt, 0, 0);
      ctx.restore();
      // the graduated scale (engraved on), a marker riding along with the count
      ctx.save();
      ctx.globalAlpha = nA;
      ctx.strokeStyle = PAL.gold;
      ctx.lineWidth = Math.max(1, 0.14 * u);
      ctx.beginPath();
      ctx.moveTo(sx0, sy);
      ctx.lineTo(sx0 + sw * sp, sy);
      for (let i = 0; i <= 50 * sp; i++) {
        const x = sx0 + (i / 50) * sw, l = i % 10 === 0 ? 2.2 * u : i % 5 === 0 ? 1.4 * u : 0.7 * u;
        ctx.moveTo(x, sy);
        ctx.lineTo(x, sy - l);
      }
      ctx.stroke();
      const mx = sx0 + sw * B.ease.inOutCubic(k);
      ctx.fillStyle = PAL.cyan;
      ctx.beginPath();
      ctx.moveTo(mx, sy + 0.4 * u);
      ctx.lineTo(mx - 1 * u, sy + 2 * u);
      ctx.lineTo(mx + 1 * u, sy + 2 * u);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
      smallCaps(ctx, "degrees C in the core", N[0], sy + 4.5 * u, L.label * 1.15, { alpha: nA * B.span(t, 6.4, 6.7), maxW: P ? F.safe.w : 0.5 * W });
      smallCaps(ctx, "before fusion can begin", N[0], sy + 4.5 * u + L.label * 1.5, L.label, { alpha: nA * B.span(t, 6.6, 6.9), color: PAL.cyan, maxW: P ? F.safe.w : 0.5 * W });
    }

    // ---- beats 4-5: three stations on an orbit; a glowing marker travels round, lighting each
    const oA = B.span(t, 7.45, 7.8) * (1 - B.span(t, 11.1, 11.45));
    if (oA > 0) {
      // portrait: a tall orbit fills the frame; the stations sit clear of the ignition's rays
      const rx = R * (P ? 1.1 : 1.9), ry = R * (P ? 1.45 : 0.85), stA = P ? [-Math.PI * 0.5, Math.PI * 0.17, Math.PI * 0.83] : [-Math.PI * 0.7, Math.PI * 0.1, Math.PI * 0.9];
      ctx.save();
      ctx.translate(cam.x, cam.y);
      ctx.rotate(P ? 0 : -0.12);
      orbitArc(ctx, 0, 0, rx, ry, -Math.PI, Math.PI, B.span(t, 7.45, 8.0, "inOutSine"), PAL.gold, { head: 0, alpha: oA * 0.9 });
      const legs = [[7.9, 8.2, -Math.PI * 1.2, stA[0]], [8.85, 9.15, stA[0], stA[1]], [9.55, 9.9, stA[1], stA[2]]];
      let ma = -Math.PI * 1.2;
      for (const [a, b, f, g2] of legs) if (t >= a) ma = B.lerp(f, g2, B.span(t, a, b, "inOutSine"));
      ctx.globalAlpha = oA; // the marker first, so a station it rests on keeps its number readable
      if (t > 7.9) {
        const mx = Math.cos(ma) * rx, my = Math.sin(ma) * ry;
        B.glow(ctx, mx, my, 5 * u, PAL.cyan, 0.9 * oA, { add: true });
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        B.circle(ctx, mx, my, 0.8 * u);
        ctx.fill();
      }
      const lit = [8.2, 9.15, 9.9];
      stA.forEach((a, i) => {
        const x = Math.cos(a) * rx, y = Math.sin(a) * ry, on = B.span(t, lit[i], lit[i] + 0.2);
        if (on > 0) B.glow(ctx, x, y, 4.5 * u, PAL.gold, 0.7 * on * oA, { add: true });
        ctx.globalAlpha = oA * B.span(t, 7.6 + i * 0.12, 7.8 + i * 0.12);
        ctx.fillStyle = on > 0 ? PAL.gold : PAL.sky;
        ctx.strokeStyle = PAL.gold;
        ctx.lineWidth = Math.max(1, 0.25 * u);
        ctx.beginPath();
        B.circle(ctx, x, y, 3.3 * u);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = on > 0 ? PAL.sky : PAL.gold;
        ctx.font = B.font(4.4 * u, SMALLCAPS, 700);
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), x, y + 0.3 * u);
      });
      ctx.restore();
      const chips = [["1 · gravity pulls it in", 8.2, 9.1], ["2 · it spins into a flat disc", 9.15, 9.85], ["3 · the core ignites: a star", 9.9, 11.1]];
      const cp = P ? [W / 2, 0.765 * H] : [0.5 * W, 0.87 * H];
      chips.forEach(([s, a, b]) => {
        const v = B.span(t, a, a + 0.2) * (1 - B.span(t, b - 0.15, b));
        if (v > 0) chip(ctx, s, cp[0], cp[1], L.chip * 1.15, B.ease.outBack(B.span(t, a, a + 0.35), 2) * oA, { alpha: v, maxW: P ? 0.84 * W : 0.6 * W });
      });
    }

    // ---- close: kaleidoscope spin into the calm mandala; the heading pours in again
    const H2 = P ? [W / 2, 0.255 * H] : [0.26 * W, 0.42 * H];
    meltHeading(ctx, ["OUR SUN WAS", "BORN THIS WAY"], H2[0], H2[1], L.head * 0.88, { at: 11.7, fill: PAL.green, outline: PAL.magenta, maxW: P ? 0.9 * W : 0.42 * W });
    smallCaps(ctx, "about 4.6 billion years ago", P ? W / 2 : 0.26 * W, P ? 0.35 * H : 0.62 * H, L.label * 1.1, { alpha: B.span(t, 12.4, 12.8), maxW: P ? F.safe.w : 0.4 * W });

    // ---- finishing: worn poster stock (multiplied fibres + drop-out speckles, 3 variants at 8 fps), vignette
    const sv = stock(W, H, Math.floor(t * 8) % 3);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.globalAlpha = 0.16;
    ctx.drawImage(sv.fibre, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 0.45;
    ctx.drawImage(sv.speck, 0, 0);
    ctx.restore();
    B.vignette(ctx, W, H, { color: "#04030f", amount: 0.55, inner: 0.35 });
  }

  // ---- sound: a beating organ hum through a phaser, phaser whooshes, rising pings, a chord bloom
  /** A phaser: four all-pass stages swept by a slow LFO; returns { input, output }. */
  function phaser(v, rate, base, depth, stopAt) {
    const input = v.ac.createGain(), output = v.ac.createGain(), wet = v.ac.createGain();
    let node = input;
    for (let i = 0; i < 4; i++) {
      const ap = v.ac.createBiquadFilter();
      ap.type = "allpass";
      ap.frequency.value = base * (1 + i * 0.6);
      ap.Q.value = 0.7;
      v.lfo(ap.frequency, rate, depth * (1 + i * 0.6), stopAt);
      node.connect(ap);
      node = ap;
    }
    node.connect(wet);
    wet.gain.value = 0.8;
    wet.connect(output);
    input.connect(output);
    return { input, output };
  }
  SOUND.define("cs-organ", (v, o) => {
    // slowly beating organ hum: each note doubled a hair sharp, through a slow phaser
    const d = v.dur ?? 8, g = v.bedGain(d, 0.16, o.fade ?? 2), ph = phaser(v, 0.12, 500, 380, v.t + d + 0.1);
    ph.output.connect(g);
    (o.notes || ["D2", "A2", "D3", "F3"]).forEach((n, i) => {
      [0, 0.7 + i * 0.2].forEach((beat) => {
        const osc = v.ac.createOscillator(), og = v.ac.createGain();
        osc.type = i ? "triangle" : "sine";
        osc.frequency.value = v.hz(n) + beat;
        og.gain.value = 0.18 / (i + 1);
        osc.connect(og);
        og.connect(ph.input);
        osc.start(v.t);
        osc.stop(v.t + d + 0.1);
      });
    });
  }, { bed: true, verb: 0.4 });
  SOUND.define("cs-phase", (v, o) => {
    // swirly phaser whoosh sweeping up (or down with o.down)
    const d = o.dur ?? 0.9, ph = phaser(v, 1.6, 700, 600, v.t + d + 0.2);
    ph.output.connect(v.out);
    const f0 = o.down ? 3200 : 400, f1 = o.down ? 400 : 3200;
    v.noise({ filter: "bandpass", q: 1.2, f: f0, f2: f1, glide: d, a: d * 0.45, len: d * 0.55, peak: 0.4, dest: ph.input });
    v.tone({ type: "sawtooth", f: o.down ? 300 : 110, f2: o.down ? 110 : 300, glide: d, a: d * 0.4, len: d * 0.6, peak: 0.03, dest: ph.input });
  }, { verb: 0.35 });
  SOUND.define("cs-bloom", (v, o) => {
    // big shimmering chord that swells open, with a low hit under it
    const d = o.dur ?? 2.4;
    (o.notes || ["D3", "A3", "D4", "F#4", "A4", "E5"]).forEach((n, i) => {
      [-6, 6].forEach((det) => v.tone({ type: "triangle", f: SOUND.note(n), detune: det, a: 0.25 + i * 0.03, hold: d * 0.3, len: d * 0.7, peak: 0.045 }));
    });
    v.tone({ f: 70, f2: 40, glide: 0.5, a: 0.005, len: 0.9, peak: 0.6 });
    v.noise({ brown: true, filter: "lowpass", f: 300, a: 0.005, len: 0.6, peak: 0.35 });
  }, { verb: 0.6 });

  function score(k) {
    k.bed("cs-organ", 0, DUR, { gain: 1 });
    k.bed("pad", 0, DUR, { notes: ["D2", "A2", "C3"], gain: 0.35, bright: 280 });
    k.seq(0.15, 0.17, ["D5", "F5", "A5", "C6", "D6", "F6"], { voice: "sonar", gain: 0.12 });
    k.at(0.1, "cs-phase", { dur: 1.2, gain: 0.6 });
    k.at(0.45, "swell", { dur: 0.6, gain: 0.4 }).at(1.05, "pluck", { note: "D4", gain: 0.3 });
    k.at(2.15, "cs-phase", { dur: 0.7, gain: 0.7, down: true }).at(2.2, "riser", { dur: 0.5, gain: 0.35 });
    // labels: pings rising as the series builds
    k.at(2.75, "data", { dur: 0.6, gain: 0.25 });
    [3.0, 3.45, 3.8, 4.15].forEach((at, i) => k.at(at, "sonar", { note: ["A4", "C5", "D5", "F5"][i], gain: 0.25, dur: 1.2 }));
    k.at(3.4, "cs-phase", { dur: 0.7, gain: 0.35, down: true });
    k.at(4.7, "cs-phase", { dur: 0.6, gain: 0.6 });
    k.repeat(5.35, 0.07, 14, "tick", { gain: 0.25, vary: 2 });
    k.at(5.5, "riser", { dur: 0.85, gain: 0.4 });
    k.at(6.35, "cs-bloom", { dur: 2.4, gain: 1 }).at(6.38, "sparkle", { gain: 0.25, note: "A6" });
    k.at(7.2, "cs-phase", { dur: 0.6, gain: 0.45, down: true });
    k.at(7.5, "data", { dur: 0.5, gain: 0.2 });
    [8.2, 9.15, 9.9].forEach((at, i) => k.at(at, "sonar", { note: ["D5", "A5", "D6"][i], gain: 0.3, dur: 1.4 }).at(at - 0.3, "swish", { dur: 0.3, gain: 0.25 }));
    k.at(8.05, "fall", { dur: 0.9, gain: 0.15 }).at(8.1, "boom", { dur: 1.2, gain: 0.3 });
    k.at(9.0, "cs-phase", { dur: 0.8, gain: 0.5 });
    // ignition: the swirl folds into a mandala - the big chord bloom
    k.at(9.95, "cs-bloom", { dur: 2.6, gain: 1, notes: ["D3", "A3", "D4", "A4", "D5", "F#5"] }).at(9.98, "chime", { note: "D6", gain: 0.3 });
    // kaleidoscope spin into the close
    k.at(11.1, "cs-phase", { dur: 0.8, gain: 0.7 }).at(11.2, "whoosh", { dur: 0.7, gain: 0.35 });
    k.at(11.75, "swell", { dur: 0.5, gain: 0.35 }).at(12.4, "sonar", { note: "A5", gain: 0.25, dur: 1.5 }).at(12.5, "chord", { notes: ["D4", "F#4", "A4", "D5"], strum: 0.06, gain: 0.4 });
  }

  Player.register({
    id: "cosmic-swirl",
    name: "Cosmic Swirl",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Sniglet:wght@800&family=Cormorant+SC:wght@600;700&display=swap",
      faces: ['800 20px "Sniglet"', '700 20px "Cormorant SC"', '600 20px "Cormorant SC"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3 (ignition)", "Close"],
    stills: [1.8, 4.4, 6.95, 9.4, 10.6, 13.2],
    draw,
    score,
  });
})();
