/* 48 Y2K Liquid Chrome - reference animation.
 * Topic (setting, replace it): "Why does gallium melt in your hand?" - a metal that melts at 29.8 degC, below the
 * temperature of your skin (about 33 degC): heat flows in, the atoms of its crystal jiggle, slip free and it flows.
 * Rendering (keep it): turn-of-the-millennium tech optimism on a pale silver-blue backdrop (deep blue for the key
 * number). Liquid chrome blobs are metaballs: a Gaussian field from moving balls, evaluated on a coarse grid, its
 * gradient gives a normal, the normal reflects a fake environment (bright sky fading to blue above, a sharp dark navy
 * horizon band, lilac ground brightening below) plus a hard specular from the upper left and a soft pearl tint, so
 * the blobs read as polished liquid metal that melts into itself. Chrome lettering is the same environment as a
 * banded vertical gradient inside a dark navy outline and a lilac-to-ice bevel rim, over a short navy extrusion, with
 * a pearl sheen gliding across. Extras: glossy pill labels (a white gloss strip on the top half), orb icons, rising
 * soap-film bubbles, four-point star flares, a slowly rotating chrome ring.
 * Motion: liquid morphs (balls drifting together until they fuse, a drop dripping off), headlines filling from the
 * top with a wavy liquid edge, springy pill pops, a round ripple wipe with a chrome rim between scenes.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { sky: "#e6eefb", steel: "#a9bbdc", deep: "#0d1d5e", ice: "#8fe3ff", lilac: "#c3a6ff", lime: "#c8ff4d", pearl: "#ffc2ea", white: "#ffffff" };
  const CHROME = "Unbounded", LABEL = "Lexend";
  const DUR = 13;
  const BEATS = [0, 2.2, 4.6, 6.8, 9.0, 11.0];
  let F = null, U = 1, T = 0, P = false;

  // ------------------------------------------------------------------ the fake environment a chrome surface reflects
  // e = the reflection's vertical direction (-1 up/sky .. +1 down/ground). Sharp horizon band at e ~ 0.
  const ENV = (() => {
    const lut = [], sky = (k) => B.mix("#f6fcff", "#4a72cc", k), ground = (k) => B.mix("#4a3f95", "#f4f0ff", k);
    for (let i = 0; i < 512; i++) {
      const e = i / 255.5 - 1;
      let col = e < 0 ? sky(B.clamp(-e / 0.8) ** 0.75) : ground(B.clamp((e - 0.04) / 0.7) ** 1.1);
      col = B.mix(col, "#ffffff", 0.55 * B.smooth(0.05, 0, Math.abs(e + 0.38)));   // a bright cloud band in the sky
      col = B.mix(col, "#6d5fb5", 0.5 * B.smooth(0.05, 0, Math.abs(e - 0.36)));    // a darker band on the ground
      col = B.mix(col, PAL.deep, B.smooth(0.075, 0.035, Math.abs(e - 0.02)));       // the sharp navy horizon
      lut.push(B.rgb(col));
    }
    return lut;
  })();
  const L3 = (() => { const v = [-0.45, -0.65, 0.6], n = Math.hypot(...v); return v.map((x) => x / n); })();

  /**
   * Liquid chrome metaballs. balls: [[x, y, r], ...] in frame px. The field is a sum of Gaussians, cut at 0.5; the
   * normal comes from its gradient (tilting to horizontal at the edge, so each blob reads as a rounded drop) and picks
   * a colour from the environment; overlapping balls fuse with a smooth neck. Drawn on a coarse grid, then scaled up.
   */
  function chromeBlobs(ctx, W, H, balls, o = {}) {
    if (!balls.length) return;
    const cell = Math.max(1.5, Math.min(W, H) / 480), TH = 0.5, alphaAll = o.alpha ?? 1;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y, r] of balls) { x0 = Math.min(x0, x - 2 * r); y0 = Math.min(y0, y - 2 * r); x1 = Math.max(x1, x + 2 * r); y1 = Math.max(y1, y + 2 * r); }
    x0 = Math.max(0, Math.floor(x0 / cell)); y0 = Math.max(0, Math.floor(y0 / cell));
    x1 = Math.min(Math.ceil(W / cell), Math.ceil(x1 / cell)); y1 = Math.min(Math.ceil(H / cell), Math.ceil(y1 / cell));
    const gw = x1 - x0, gh = y1 - y0;
    if (gw <= 0 || gh <= 0) return;
    const g = B.scratch("lc-blob", gw, gh), img = g.createImageData(gw, gh), d = img.data;
    const bl = balls.map(([x, y, r]) => [x, y, 1 / (r * r), r]);
    const sh = o.shift ?? 0;
    for (let j = 0; j < gh; j++) {
      const py = (y0 + j + 0.5) * cell;
      for (let i = 0; i < gw; i++) {
        const px = (x0 + i + 0.5) * cell;
        let f = 0, gx = 0, gy = 0, rs = 0;
        for (let k = 0; k < bl.length; k++) {
          const b = bl[k], dx = px - b[0], dy = py - b[1], q = (dx * dx + dy * dy) * b[2];
          if (q > 6) continue;
          const e = Math.exp(-q), kk = 2 * e * b[2];
          f += e; gx -= kk * dx; gy -= kk * dy; rs += e * b[3];
        }
        if (f < TH * 0.6) continue;
        const gm = Math.hypot(gx, gy), a = B.clamp((f - TH) / (gm * cell * 1.1 + 1e-6) + 0.5);
        if (a <= 0) continue;
        const S = rs / f;
        let nx = -gx * S, ny = -gy * S, nz = Math.max(0, f - TH) * 3.2;
        const nl = Math.hypot(nx, ny, nz) || 1;
        nx /= nl; ny /= nl; nz /= nl;
        const ry = 2 * nz * ny, rx = 2 * nz * nx, rz = 2 * nz * nz - 1;
        const env = ENV[Math.max(0, Math.min(511, Math.round((ry * 0.9 + 0.12 + sh + 1) * 255.5)))];
        const spec = Math.pow(Math.max(0, rx * L3[0] + ry * L3[1] + rz * L3[2]), 30) * 1.3;
        const pearl = 0.16 * (0.5 + 0.5 * Math.sin(rx * 3 + ry * 2 + T * 0.8));
        const rim = B.clamp(1 - nz * 4) * 0.55; // dark navy contour where the surface turns away
        const idx = (j * gw + i) * 4;
        let r = env[0], gg = env[1], bb = env[2];
        r += (255 - r) * pearl * 0.6; bb += (234 - bb) * pearl * 0.4;
        r = r * (1 - rim) + 13 * rim; gg = gg * (1 - rim) + 29 * rim; bb = bb * (1 - rim) + 94 * rim;
        d[idx] = Math.min(255, r + spec * 255); d[idx + 1] = Math.min(255, gg + spec * 255); d[idx + 2] = Math.min(255, bb + spec * 255);
        d[idx + 3] = 255 * a * alphaAll;
      }
    }
    g.putImageData(img, 0, 0);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(g.canvas, x0 * cell, y0 * cell, gw * cell, gh * cell);
    ctx.restore();
  }

  // ------------------------------------------------------------------ chrome lettering
  /** Vertical chrome gradient for one line box: sky, sharp navy horizon, lilac ground brightening to white. */
  function chromeFill(g, top, h) {
    return B.linear(g, 0, top, 0, top + h, [[0, "#ffffff"], [0.2, "#dff1ff"], [0.47, "#7d9fdd"], [0.5, PAL.deep], [0.55, "#5b4fa0"], [0.75, "#d9ccff"], [1, "#ffffff"]]);
  }
  /**
   * Chrome headline: navy extrusion, dark navy outline, lilac-to-ice bevel rim, banded chrome face, pearl sheen
   * gliding across; fill = 0..1 fills the letters from the top with a wavy liquid edge. Returns the text measure.
   */
  function chromeText(ctx, W, H, str, x, y, size, fill = 1, o = {}) {
    const m = B.measureText(ctx, str, { size, family: CHROME, weight: 800, maxW: o.maxW ?? F.safe.w, maxLines: 3, lineH: 1.08, letterSpacing: -0.01 });
    if (fill <= 0) return m;
    const sz = m.size, top = y - m.height / 2, lines = m.lines;
    const g = B.scratch("lc-text", W, H);
    g.setTransform(ctx.getTransform());
    const opt = (extra) => ({ size: sz, family: CHROME, weight: 800, maxLines: 1, letterSpacing: -0.01, align: o.align || "center", ...extra });
    lines.forEach((ln, i) => {
      const ly = top + m.lh * (i + 0.5);
      for (let k = 6; k >= 1; k--) B.text(g, ln, x, ly + k * sz * 0.014, opt({ color: PAL.deep, stroke: PAL.deep, strokeW: sz * 0.16 }));
      B.text(g, ln, x, ly, opt({ color: PAL.deep, stroke: PAL.deep, strokeW: sz * 0.15 }));
      B.text(g, ln, x, ly, opt({ color: PAL.deep, stroke: B.linear(g, 0, ly - sz * 0.5, 0, ly + sz * 0.5, [PAL.ice, PAL.white, PAL.lilac]), strokeW: sz * 0.075 }));
      B.text(g, ln, x, ly, opt({ color: chromeFill(g, ly - sz * 0.42, sz * 0.84) }));
    });
    // pearl sheen: an iridescent band gliding across the letters
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "source-atop";
    const sx = ((T * 0.35 + (o.seed || 0)) % 1.6 - 0.3) * W;
    g.globalAlpha = 0.35;
    g.fillStyle = B.linear(g, sx - W * 0.25, 0, sx + W * 0.25, H * 0.1, [[0, "rgba(255,194,234,0)"], [0.35, PAL.pearl], [0.5, PAL.ice], [0.65, PAL.lime], [1, "rgba(200,255,77,0)"]]);
    g.fillRect(0, 0, W, H);
    // the liquid fill: everything below the wavy level is not there yet
    if (fill < 1) {
      g.globalAlpha = 1;
      g.globalCompositeOperation = "destination-out";
      g.setTransform(ctx.getTransform());
      const lvl = B.lerp(top - sz * 0.3, top + m.height + sz * 0.3, B.ease.inOutSine(fill));
      g.beginPath();
      g.moveTo(x - W, top + m.height + sz);
      for (let k = 0; k <= 40; k++) { const xx = x - W + (2 * W * k) / 40; g.lineTo(xx, lvl + Math.sin(xx / (sz * 0.6) + T * 7) * sz * 0.08); }
      g.lineTo(x + W, top + m.height + sz);
      g.closePath();
      g.fill();
    }
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = o.alpha ?? 1;
    ctx.drawImage(g.canvas, 0, 0);
    ctx.restore();
    return m;
  }

  // ------------------------------------------------------------------ glossy pills, orb icons, bubbles, flares, ring
  /** Glossy pill: candy gradient, a white gloss strip over the top half, a navy rim, springy scale s. */
  function pill(ctx, x, y, str, size, s, col = PAL.white, o = {}) {
    if (s <= 0.001) return 0;
    ctx.save();
    ctx.font = B.font(size, LABEL, 600);
    const dotW = o.num ? size * 1.9 : 0, tw = ctx.measureText(str).width, h = size * 2.1, w = tw + size * 1.8 + dotW;
    const al = o.align || "center", cx = al === "left" ? x + w / 2 : al === "right" ? x - w / 2 : x;
    ctx.translate(cx, y);
    ctx.scale(s, s);
    B.withShadow(ctx, { color: "rgba(13,29,94,0.3)", blur: size * 0.7, y: size * 0.3 }, () => {
      ctx.beginPath();
      B.capsule(ctx, -w / 2, -h / 2, w, h);
      ctx.fillStyle = B.linear(ctx, 0, -h / 2, 0, h / 2, [B.shade(col, 0.35), col, B.shade(col, -0.18)]);
      ctx.fill();
    });
    ctx.strokeStyle = B.rgba(PAL.deep, 0.55);
    ctx.lineWidth = size * 0.08;
    ctx.stroke();
    ctx.beginPath();
    B.capsule(ctx, -w / 2 + h * 0.22, -h / 2 + h * 0.08, w - h * 0.44, h * 0.38);
    ctx.fillStyle = B.linear(ctx, 0, -h / 2, 0, -h * 0.05, ["rgba(255,255,255,0.95)", "rgba(255,255,255,0.15)"]);
    ctx.fill();
    if (o.num) orb(ctx, -w / 2 + h * 0.5, 0, h * 0.44, o.numCol || PAL.ice, o.num);
    ctx.fillStyle = PAL.deep;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = B.font(size, LABEL, 600);
    ctx.fillText(str, dotW / 2, size * 0.06);
    ctx.restore();
    return w;
  }
  /** Orb icon: a glossy sphere with a hard top highlight and a soft bounce light; optional glyph or digit. */
  function orb(ctx, x, y, r, col, glyph) {
    ctx.save();
    ctx.beginPath();
    B.circle(ctx, x, y, r);
    ctx.fillStyle = B.radial(ctx, x - r * 0.3, y - r * 0.35, 0, r * 1.2, [[0, B.shade(col, 0.6)], [0.5, col], [1, B.shade(col, -0.45)]]);
    ctx.fill();
    ctx.strokeStyle = B.rgba(PAL.deep, 0.6);
    ctx.lineWidth = r * 0.08;
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(x - r * 0.05, y - r * 0.5, r * 0.6, r * 0.32, 0, 0, B.TAU);
    ctx.fillStyle = "rgba(255,255,255,0.75)";
    ctx.fill();
    if (typeof glyph === "string") {
      ctx.fillStyle = PAL.deep;
      ctx.font = B.font(r * 1.2, CHROME, 800);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(glyph, x, y + r * 0.1);
    } else if (typeof glyph === "function") glyph(ctx, x, y, r);
    ctx.restore();
  }
  /** Rising soap-film bubbles: a thin white rim, a pearl-tinted film, a small highlight arc. */
  function bubbles(ctx, W, H, seed, n, a = 1) {
    const r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const R = r.range(0.8, 3.2) * U, x = r() * W + Math.sin(T * r.range(0.6, 1.4) + i) * 2 * U;
      const y = H * 1.1 - B.fract(r() + T * r.range(0.03, 0.07)) * H * 1.25;
      ctx.save();
      ctx.globalAlpha *= a;
      ctx.beginPath();
      B.circle(ctx, x, y, R);
      ctx.fillStyle = B.radial(ctx, x, y, R * 0.4, R, [[0, "rgba(255,255,255,0.05)"], [0.8, B.rgba(i % 2 ? PAL.pearl : PAL.ice, 0.25)], [1, "rgba(255,255,255,0.7)"]]);
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.lineWidth = Math.max(1, 0.12 * U);
      ctx.beginPath();
      ctx.arc(x, y, R * 0.68, -2.6, -1.6);
      ctx.stroke();
      ctx.restore();
    }
  }
  /** Four-point star lens flare: a soft glow, a pinched star and long thin cross rays. */
  function flare(ctx, x, y, r, a = 1, col = PAL.white) {
    if (a <= 0.01) return;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    B.glow(ctx, x, y, r * 1.4, col, 0.5 * a);
    ctx.globalAlpha = a;
    ctx.fillStyle = PAL.white;
    ctx.beginPath();
    B.sparkle(ctx, x, y, r, 0.1);
    ctx.fill();
    ctx.fillStyle = B.linear(ctx, x - r * 2.6, 0, x + r * 2.6, 0, ["rgba(255,255,255,0)", "rgba(255,255,255,0.8)", "rgba(255,255,255,0)"]);
    ctx.fillRect(x - r * 2.6, y - 0.08 * U, r * 5.2, 0.16 * U);
    ctx.restore();
  }
  function flares(ctx, W, H, seed, n, area) {
    const r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const x = area.x + r() * area.w, y = area.y + r() * area.h, ph = r(), per = r.range(1.4, 2.6);
      const tw = Math.pow(Math.max(0, Math.sin(B.TAU * (T / per + ph))), 4);
      flare(ctx, x, y, r.range(1.6, 3.2) * U * (0.4 + 0.6 * tw), tw, i % 2 ? PAL.ice : PAL.lilac);
    }
  }
  /** A slowly rotating chrome ring (a torus seen at a changing tilt): banded stroke plus a thin highlight. */
  function ring(ctx, x, y, R, th, a = 1) {
    if (a <= 0) return;
    const tilt = 0.36 + 0.14 * Math.sin(T * 0.7), rot = -0.18 + 0.12 * Math.sin(T * 0.35);
    ctx.save();
    ctx.globalAlpha *= a;
    ctx.translate(x, y);
    ctx.rotate(rot);
    ctx.scale(1, tilt);
    ctx.lineWidth = th / tilt * 0.9;
    ctx.strokeStyle = B.rgba(PAL.deep, 0.9);
    ctx.beginPath(); ctx.arc(0, 0, R, 0, B.TAU); ctx.stroke();
    ctx.lineWidth = th / tilt * 0.65;
    ctx.strokeStyle = B.linear(ctx, 0, -R - th, 0, R + th, [[0, "#ffffff"], [0.3, "#b9d4ff"], [0.48, PAL.deep], [0.53, "#7466c0"], [0.8, "#efe8ff"], [1, "#ffffff"]]);
    ctx.stroke();
    ctx.lineWidth = th * 0.12 / tilt;
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.beginPath(); ctx.arc(0, -th * 0.15, R, Math.PI * 1.1, Math.PI * 1.7); ctx.stroke();
    ctx.restore();
  }

  // ------------------------------------------------------------------ backdrops
  function backdrop(ctx, W, H, dark) {
    const D = Math.hypot(W, H);
    if (!dark) {
      ctx.fillStyle = B.linear(ctx, 0, 0, W * 0.3, H, [[0, "#f6f9ff"], [0.5, PAL.sky], [1, PAL.steel]]);
      ctx.fillRect(0, 0, W, H);
      B.glow(ctx, W * 0.85, H * 0.15, D * 0.35, PAL.lilac, 0.28);
      B.glow(ctx, W * 0.1, H * 0.75, D * 0.35, PAL.ice, 0.25);
    } else {
      ctx.fillStyle = B.linear(ctx, 0, 0, 0, H, [[0, "#1a2f86"], [0.55, PAL.deep], [1, "#060d38"]]);
      ctx.fillRect(0, 0, W, H);
      B.glow(ctx, W * 0.5, H * 0.45, D * 0.4, PAL.ice, 0.18, { add: true });
      B.glow(ctx, W * 0.85, H * 0.85, D * 0.3, PAL.lilac, 0.2, { add: true });
    }
    // faint Y2K concentric ripple rings breathing out from the centre
    ctx.save();
    ctx.strokeStyle = dark ? "rgba(143,227,255,0.10)" : "rgba(255,255,255,0.45)";
    ctx.lineWidth = 0.18 * U;
    for (let i = 0; i < 7; i++) {
      const R = (B.fract(T * 0.12 + i / 7)) * D * 0.6;
      ctx.globalAlpha = 1 - R / (D * 0.6);
      ctx.beginPath();
      B.circle(ctx, W / 2, H * 0.5, R);
      ctx.stroke();
    }
    ctx.restore();
  }
  /** A soft shadow and a short glossy floor reflection under a blob (pale scenes). */
  function puddleShadow(ctx, x, y, rx) { B.contactShadow(ctx, x, y, rx, rx * 0.16, 0.35, PAL.deep); }

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  /** Solid gallium: a chrome crystal block (three faces, each its own banded reflection), bobbing gently. */
  function crystal(ctx, x, y, s, glint) {
    const a = s * 0.5, b = s * 0.29, h = s * 0.55;
    const top = [[x, y - b - h * 0.5], [x + a, y - h * 0.5], [x, y + b - h * 0.5], [x - a, y - h * 0.5]];
    const left = [[x - a, y - h * 0.5], [x, y + b - h * 0.5], [x, y + b + h * 0.5], [x - a, y + h * 0.5]];
    const right = [[x + a, y - h * 0.5], [x, y + b - h * 0.5], [x, y + b + h * 0.5], [x + a, y + h * 0.5]];
    const face = (pts, fill) => { ctx.beginPath(); B.poly(ctx, pts, true); ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = PAL.deep; ctx.lineWidth = 0.35 * U; ctx.lineJoin = "round"; ctx.stroke(); };
    face(top, B.linear(ctx, x, y - b - h * 0.5, x, y + b - h * 0.5, ["#ffffff", "#d8e8ff", "#9fb7e6"]));
    face(left, B.linear(ctx, 0, y - h * 0.5, 0, y + b + h * 0.5, [[0, "#eef5ff"], [0.42, "#8aa7e0"], [0.47, PAL.deep], [0.55, "#6a5db6"], [1, "#f1ebff"]]));
    face(right, B.linear(ctx, 0, y - h * 0.5, 0, y + b + h * 0.5, [[0, "#b8c9f0"], [0.32, "#5c79c8"], [0.37, PAL.deep], [0.47, "#52468f"], [1, "#cdbff7"]]));
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 0.2 * U;
    ctx.beginPath(); B.poly(ctx, [top[3], top[0], top[1]]); ctx.stroke();
    flare(ctx, top[0][0], top[0][1], 3.4 * U, glint);
  }
  /** Body heat as a glyph inside an orb: three rising wavy lines in white. */
  function heatGlyph(ctx, x, y, r) {
    ctx.strokeStyle = "rgba(255,255,255,0.95)";
    ctx.lineWidth = r * 0.13;
    ctx.lineCap = "round";
    for (let i = -1; i <= 1; i++) {
      ctx.beginPath();
      for (let k = 0; k <= 16; k++) {
        const q = k / 16, yy = y + r * 0.5 - q * r * 1.0, xx = x + i * r * 0.36 + Math.sin(q * B.TAU * 1.2 + T * 4 + i) * r * 0.1;
        k ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy);
      }
      ctx.stroke();
    }
  }
  /** Atom positions for the crystal lattice, and the melt: each atom slides down into one fused puddle. */
  function atoms(W, H, cx, cy, sp, jig, melt) {
    const cols = P ? 5 : 6, rows = P ? 4 : 3, out = [];
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
      const n = j * cols + i, gx = cx + (i - (cols - 1) / 2) * sp, gy = cy + (j - (rows - 1) / 2) * sp;
      const jx = B.noise1(T * 7 + n * 3.1, n) * jig * sp, jy = B.noise1(T * 7 + n * 5.3, n + 40) * jig * sp;
      const k = B.ease.inOutCubic(B.clamp(melt * 1.6 - (rows - 1 - j) * 0.12 - B.hash01(n, "m") * 0.25));
      const px = cx + (i - (cols - 1) / 2) * sp * 0.82 + (j % 2 ? 0.3 : -0.3) * sp * 0.4, py = cy + sp * (P ? 0.9 : rows * 0.55) + Math.sin(T * 3 + i) * sp * 0.05;
      out.push([B.lerp(gx + jx, px, k), B.lerp(gy + jy, py, k), sp * B.lerp(0.3, 0.5, k)]);
    }
    return out;
  }

  // ------------------------------------------------------------------ scenes
  function titleScene(ctx, W, H, lt, close) {
    const s = F.safe, ty = P ? H * 0.33 : H * 0.38, cy = P ? H * 0.64 : H * 0.7;
    backdrop(ctx, W, H, false);
    ring(ctx, W / 2, ty, P ? 40 * U : 34 * U, 3.2 * U, B.span(lt, 0.1, 0.8));
    bubbles(ctx, W, H, close ? "lc-b5" : "lc-b0", 18);
    // liquid chrome blobs flowing together into one, a drop dripping off its underside
    const m = B.ease.inOutSine(B.span(lt, 0, 1.8)), R = P ? 9 * U : 7 * U, bx = P ? W / 2 : W * 0.5;
    const balls = [];
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * B.TAU + T * 0.5, far = B.lerp(P ? 34 * U : 50 * U, R * 0.9, m);
      balls.push([bx + Math.cos(a) * far, cy + Math.sin(a) * far * (P ? 0.45 : 0.3), R * (0.8 + 0.25 * Math.sin(T * 1.3 + i))]);
    }
    const drip = B.fract((lt - 1.2) / 1.6);
    if (lt > 1.2) balls.push([bx + R * 0.35, cy + R * 1.0 + drip * drip * R * 2.2, R * 0.42 * (1 - drip * 0.5)]);
    puddleShadow(ctx, bx, cy + R * 2.4, R * 3.4);
    chromeBlobs(ctx, W, H, balls);
    if (!P) chromeBlobs(ctx, W, H, [[W * 0.1, H * 0.25 + B.bob(T, U, 3), 4 * U], [W * 0.9, H * 0.3 + B.bob(T, U, 3.4, 0.5), 5 * U], [W * 0.88 + 5 * U, H * 0.3 + 5 * U, 2.6 * U]]);
    flares(ctx, W, H, close ? "lc-f5" : "lc-f0", 4, { x: s.x, y: s.y, w: s.w, h: s.h * 0.7 });
    const txt = close ? (P ? "MELTS\nIN YOUR\nHAND" : "MELTS IN\nYOUR HAND") : (P ? "LIQUID\nMETAL" : "LIQUID METAL");
    const sz = (P ? 16 : close ? 10 : 12) * U;
    const mm = chromeText(ctx, W, H, txt, W / 2, ty, sz, B.span(lt, 0.15, 1.0), { seed: close ? 0.6 : 0 });
    const sub = close ? "Cool it and it turns solid again" : "Why gallium melts in your hand";
    pill(ctx, W / 2, ty + mm.height / 2 + (P ? 7 : 6) * U, sub, (P ? 4.3 : 3.9) * U, B.pop(lt, 0.9, 0.5, 2.6), PAL.white);
    if (close) pill(ctx, W / 2, P ? H * 0.765 : H * 0.88, "Melts at 29.8 °C", (P ? 4.3 : 3.9) * U, B.pop(lt, 1.3, 0.5, 2.6), PAL.lime);
  }

  function diagramScene(ctx, W, H, lt) {
    const s = F.safe, ls = (P ? 4.2 : 3.9) * U;
    backdrop(ctx, W, H, false);
    bubbles(ctx, W, H, "lc-b1", 14);
    const hand = P ? [W * 0.5, H * 0.24] : [W * 0.24, H * 0.47], cr = P ? [W * 0.5, H * 0.6] : [W * 0.72, H * 0.5];
    const hr = (P ? 11 : 9) * U, cs = (P ? 34 : 24) * U, by = B.bob(T, 0.8 * U, 3.2);
    // the hand orb, warm and glowing
    const hp = B.pop(lt, 0.15, 0.55, 2.4);
    B.glow(ctx, hand[0], hand[1], hr * 2.4, PAL.pearl, 0.6 * hp);
    if (hp > 0.01) { ctx.save(); ctx.translate(hand[0], hand[1]); ctx.scale(hp, hp); orb(ctx, 0, 0, hr, "#ff9fd6", heatGlyph); ctx.restore(); }
    pill(ctx, hand[0], hand[1] + hr + ls * 1.6, "Skin: about 33 °C", ls, B.pop(lt, 0.5, 0.5, 2.6), PAL.pearl);
    // the solid gallium crystal on a small glossy puddle that starts to form as heat arrives
    const cp = B.pop(lt, 0.35, 0.6, 2.2);
    puddleShadow(ctx, cr[0], cr[1] + cs * 0.62, cs * 0.75);
    const pud = B.span(lt, 1.4, 2.4, "inOutSine");
    if (pud > 0) chromeBlobs(ctx, W, H, [[cr[0] - cs * 0.3, cr[1] + cs * 0.5, cs * 0.14 * pud], [cr[0] + cs * 0.25, cr[1] + cs * 0.52, cs * 0.17 * pud], [cr[0] - cs * 0.02, cr[1] + cs * 0.57, cs * 0.12 * pud]]);
    if (cp > 0.01) { ctx.save(); ctx.translate(cr[0], cr[1] + by); ctx.scale(cp, cp); crystal(ctx, 0, 0, cs, B.span(lt, 1.0, 1.3) * (1 - B.span(lt, 1.6, 2.0))); ctx.restore(); }
    pill(ctx, cr[0], cr[1] + cs * 0.62 + ls * 2.2, "Solid gallium", ls, B.pop(lt, 0.7, 0.5, 2.6), PAL.ice);
    // the arrow: a chrome tube carrying heat from the hand to the metal
    const a0 = P ? [hand[0], hand[1] + hr + ls * 3.4] : [hand[0] + hr + 2 * U, hand[1]];
    const a1 = P ? [cr[0], cr[1] - cs * 0.62] : [cr[0] - cs * 0.62, cr[1]];
    const pts = B.densify(P ? [a0, a1] : B.quad(a0[0], a0[1], (a0[0] + a1[0]) / 2, a0[1] - 6 * U, a1[0], a1[1]), U);
    const ap = B.span(lt, 0.6, 1.2, "inOutCubic");
    B.arrow(ctx, pts, { p: ap, width: 2.4 * U, head: 5 * U, color: PAL.deep });
    B.arrow(ctx, pts, { p: ap, width: 1.4 * U, head: 3.6 * U, color: "#ff9fd6" });
    if (ap > 0.05) { const mid = B.pointAt(pts, Math.min(ap, 1) * 0.5); B.glow(ctx, mid[0], mid[1], 4 * U, PAL.pearl, 0.6); }
    const lab = B.pointAt(pts, 0.5);
    pill(ctx, P ? lab[0] + 3 * U : lab[0], P ? lab[1] : lab[1] - 9 * U, "Heat flows in", ls, B.pop(lt, 1.1, 0.5, 2.6), PAL.lime, { align: P ? "left" : "center" });
    flares(ctx, W, H, "lc-f1", 3, { x: s.x, y: s.y, w: s.w, h: s.h });
  }

  function numberScene(ctx, W, H, lt) {
    const s = F.safe, ny = P ? H * 0.46 : H * 0.48;
    backdrop(ctx, W, H, true);
    ring(ctx, W / 2, ny, P ? 40 * U : 36 * U, 3.2 * U, 1);
    // dim chrome blobs drifting in the corners, morphing
    const k = T * 0.6;
    chromeBlobs(ctx, W, H, [[s.x + 6 * U + Math.sin(k) * 3 * U, H * (P ? 0.72 : 0.8), 6 * U], [s.x + 13 * U, H * (P ? 0.72 : 0.8) + Math.cos(k) * 4 * U, 4 * U], [s.r - 6 * U, H * (P ? 0.2 : 0.2) + Math.sin(k * 1.3) * 3 * U, 5 * U], [s.r - 12 * U + Math.cos(k) * 3 * U, H * (P ? 0.22 : 0.24), 3.4 * U]], { shift: 0.1 });
    bubbles(ctx, W, H, "lc-b2", 16, 0.7);
    pill(ctx, W / 2, ny - (P ? 17 : 17) * U, "GALLIUM MELTS AT", (P ? 4.3 : 3.9) * U, B.pop(lt, 0.15, 0.5, 2.6), PAL.lime);
    const c = B.span(lt, 0.3, 1.5);
    chromeText(ctx, W, H, B.counter(c, 29.8, { decimals: 1, ease: "outCubic" }) + " °C", W / 2, ny, (P ? 15 : 15) * U, B.span(lt, 0.1, 0.6), { seed: 0.3 });
    if (lt > 1.5) flare(ctx, W / 2 + (P ? 36 : 32) * U, ny - 7 * U, 5 * U, 1 - B.span(lt, 1.6, 2.1));
    pill(ctx, W / 2, ny + (P ? 17 : 17) * U, "Cooler than your skin", (P ? 4.3 : 3.9) * U, B.pop(lt, 1.4, 0.5, 2.6), PAL.lilac);
    flares(ctx, W, H, "lc-f2", 5, { x: s.x, y: s.y, w: s.w, h: s.h });
  }

  /** Steps: numbered pills and the lattice of chrome atoms; part 2 melts the lattice into one puddle. */
  function stepsScene(ctx, W, H, lt, part) {
    const s = F.safe, ls = (P ? 4.2 : 3.9) * U;
    backdrop(ctx, W, H, false);
    bubbles(ctx, W, H, "lc-b3", 14);
    const cx = P ? W / 2 : W * 0.68, cy = P ? H * 0.52 : H * 0.46, sp = (P ? 17 : 13) * U;
    const t0 = part ? BEATS[4] : BEATS[3];
    const heat = part ? 1 : B.span(T, 7.8, 8.4);
    const jig = part ? 0.18 : B.lerp(0.04, 0.16, heat), melt = part ? B.span(T, 9.3, 10.6) : 0;
    B.glow(ctx, cx, cy + sp * 2.5, sp * 4, PAL.pearl, 0.5 * heat * (1 - melt * 0.5));
    B.glow(ctx, cx, cy + sp * 2.5, sp * 2.5, PAL.lime, 0.25 * heat * (1 - melt));
    if (melt > 0.3) puddleShadow(ctx, cx, cy + sp * (P ? 1.6 : 2.3), sp * 3.6 * melt);
    chromeBlobs(ctx, W, H, atoms(W, H, cx, cy, sp, jig, melt));
    const px = P ? W / 2 : s.x, al = P ? "center" : "left";
    const rows = P ? [H * 0.19, H * 0.255] : [H * 0.3, H * 0.45];
    if (!part) {
      pill(ctx, px, rows[0], "Atoms locked in a crystal", ls, B.pop(T, 6.95, 0.5, 2.6), PAL.white, { num: "1", align: al });
      pill(ctx, px, rows[1], "Heat makes them jiggle", ls, B.pop(T, 7.8, 0.5, 2.6), PAL.white, { num: "2", numCol: "#ff9fd6", align: al });
    } else {
      pill(ctx, px, rows[0], "They slip free", ls, B.pop(T, t0 + 0.1, 0.5, 2.6), PAL.white, { num: "3", numCol: PAL.lime, align: al });
      chromeText(ctx, W, H, "IT FLOWS!", P ? W / 2 : s.x, P ? H * 0.34 : H * 0.52, (P ? 13 : 9) * U, B.span(T, t0 + 0.5, t0 + 1.3), { align: al, maxW: P ? s.w : W * 0.42, seed: 0.9 });
      pill(ctx, P ? W / 2 : cx, P ? H * 0.72 : H * 0.84, "A puddle of liquid metal", ls, B.pop(T, 10.2, 0.5, 2.6), PAL.ice);
    }
    flares(ctx, W, H, "lc-f3", 3, { x: s.x, y: s.y, w: s.w, h: s.h });
  }

  const SCENES = [
    (c, W, H) => titleScene(c, W, H, T, false),
    (c, W, H) => diagramScene(c, W, H, T - BEATS[1]),
    (c, W, H) => numberScene(c, W, H, T - BEATS[2]),
    (c, W, H) => stepsScene(c, W, H, T - BEATS[3], 0),
    (c, W, H) => stepsScene(c, W, H, T - BEATS[4], 1),
    (c, W, H) => titleScene(c, W, H, T - BEATS[5], true),
  ];

  // ------------------------------------------------------------------ frame: scenes, ripple wipe, finishing
  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    P = F.portrait;
    T = t;
    const i = B.beat(t, BEATS, DUR).i;
    const p = i > 0 ? B.span(t, BEATS[i], BEATS[i] + 0.6, "inOutCubic") : 1;
    const ox = W / 2, oy = H * 0.5, D = Math.hypot(W, H) * 0.56;
    if (p < 1) {
      SCENES[i - 1](ctx, W, H);
      // round ripple wipe: the next scene opens inside a growing circle with a wobbling chrome rim
      const R = p * D;
      const edge = (g) => { g.beginPath(); for (let k = 0; k <= 72; k++) { const a = (k / 72) * B.TAU, rr = R * (1 + 0.03 * Math.sin(a * 6 + t * 9) * (1 - p)); k ? g.lineTo(ox + Math.cos(a) * rr, oy + Math.sin(a) * rr) : g.moveTo(ox + Math.cos(a) * rr, oy + Math.sin(a) * rr); } g.closePath(); };
      ctx.save();
      edge(ctx);
      ctx.clip();
      SCENES[i](ctx, W, H);
      ctx.restore();
      ctx.save();
      edge(ctx);
      ctx.lineWidth = 2.6 * U;
      ctx.strokeStyle = PAL.deep;
      ctx.stroke();
      ctx.lineWidth = 1.6 * U;
      ctx.strokeStyle = B.linear(ctx, 0, oy - R, 0, oy + R, [[0, "#ffffff"], [0.45, "#a9c3f2"], [0.5, PAL.deep], [0.56, "#7466c0"], [1, "#ffffff"]]);
      ctx.stroke();
      ctx.restore();
    } else SCENES[i](ctx, W, H);
    B.vignette(ctx, W, H, { amount: 0.22, inner: 0.55, color: PAL.deep });
    B.grain(ctx, W, H, { amount: 0.04, t });
  }

  // ------------------------------------------------------------------ sound: bubbly blips, glassy chimes, shiny swooshes, a trancey arp bed
  SOUND.define("chrome-pop", (v, o) => {
    // springy pill pop: a round sine blip that bends up and wobbles
    const f = v.hz(o.note ?? "E5");
    v.tone({ f: f * 0.7, f2: f, glide: 0.05, a: 0.002, len: 0.16, peak: 0.22 });
    v.tone({ f: f * 2, a: 0.001, len: 0.05, peak: 0.05 });
  }, { verb: 0.3 });
  SOUND.define("chrome-glass", (v, o) => {
    // glassy chime: bright inharmonic partials with a long shimmering tail
    const f = v.hz(o.note ?? "B6");
    [[1, 0.09], [2.76, 0.04], [5.4, 0.02]].forEach(([m, pk]) => v.tone({ f: f * m, a: 0.002, len: 1.4 / m ** 0.3, peak: pk }));
  }, { verb: 0.75 });
  SOUND.define("chrome-swoosh", (v, o) => {
    // shiny swoosh: a bright filtered noise sweep with a sparkly top
    const d = o.dur ?? 0.5;
    v.noise({ filter: "bandpass", f: 900, f2: 7000, q: 1.2, glide: d, a: d * 0.5, len: d * 0.5, peak: 0.28 });
    v.grains({ at: d * 0.4, span: d * 0.6, count: 10, filter: "highpass", f: 6000, len: 0.01, peak: 0.08 });
  }, { verb: 0.4 });

  function score(k) {
    const lyd = ["E4", "F#4", "G#4", "A#4", "B4", "D#5", "E5", "G#5"];
    k.bed("arp", 0, DUR, { notes: lyd, step: 0.125, pattern: [0, 4, 6, 4, 2, 5, 7, 5], gain: 0.9 });
    k.bed("pad", 0, DUR, { notes: ["E3", "B3", "D#4", "G#4"], gain: 0.5, bright: 1300 });
    k.bed("pulse", 0, DUR, { bpm: 120, gain: 0.35 });
    // title: blobs gliding together with bubbly blips, the chrome fill, a pill pop and a glassy chime
    k.repeat(0.1, 0.18, 9, "bubble", { gain: 0.35, vary: 5, jitter: 0.04 });
    k.at(0.15, "chrome-swoosh", { dur: 0.8 });
    k.at(0.9, "chrome-pop", { note: "B5" }).at(1.0, "chrome-glass", { note: "E7" });
    k.at(1.9, "chrome-swoosh", { dur: 0.5 }).at(2.2, "bubble", { gain: 0.5 });
    // diagram: orb, crystal glint, arrow swoosh, pills
    k.at(2.35, "chrome-pop", { note: "E5" }).at(2.55, "chrome-pop", { note: "G#5" });
    k.at(2.7, "chrome-pop", { note: "B5" }).at(2.8, "chrome-swoosh", { dur: 0.5 });
    k.at(3.2, "chrome-glass", { note: "B6" }).at(3.3, "chrome-pop", { note: "E6" });
    k.repeat(3.6, 0.2, 5, "bubble", { gain: 0.3, vary: 4 });
    // key number: swoosh into the dark, blips counting up, a big glassy chord as it lands
    k.at(4.35, "chrome-swoosh", { dur: 0.5 }).at(4.75, "chrome-pop", { note: "D#5" });
    k.repeat(4.9, 0.08, 14, "blip", { gain: 0.25, vary: 1 });
    k.at(6.1, "chrome-glass", { note: "E7" }).at(6.1, "chord", { notes: ["E5", "G#5", "B5", "D#6"], gain: 0.35 }).at(6.0, "chrome-pop", { note: "G#5" });
    // steps: pops, then the melt as a run of bubbles falling in pitch
    k.at(6.55, "chrome-swoosh", { dur: 0.5 });
    k.at(6.95, "chrome-pop", { note: "E5" }).at(7.8, "chrome-pop", { note: "B5" });
    k.repeat(7.9, 0.1, 10, "bubble", { gain: 0.25, vary: 6 });
    k.at(8.75, "chrome-swoosh", { dur: 0.5 }).at(9.1, "chrome-pop", { note: "G#5" }).at(9.5, "chrome-pop", { note: "D#6" });
    k.repeat(9.4, 0.09, 14, "bubble", { gain: 0.4, vary: 3, pitch: -4 });
    k.at(10.2, "chrome-pop", { note: "E6" }).at(10.4, "chrome-glass", { note: "G#6" });
    // close
    k.at(10.75, "chrome-swoosh", { dur: 0.6 }).at(11.9, "chrome-pop", { note: "B5" });
    k.at(12.3, "chrome-pop", { note: "E6" }).at(12.35, "chrome-glass", { note: "E7" }).at(12.35, "chord", { notes: ["E4", "B4", "D#5", "G#5"], strum: 0.05, gain: 0.35 });
  }

  Player.register({
    id: "liquid-chrome",
    name: "Y2K Liquid Chrome",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700;800&family=Lexend:wght@500;600&display=swap",
      faces: ['800 20px "Unbounded"', '700 20px "Unbounded"', '600 20px "Lexend"', '500 20px "Lexend"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.9, 4.2, 6.4, 8.6, 10.7, 12.6],
    draw,
    score,
  });
})();
