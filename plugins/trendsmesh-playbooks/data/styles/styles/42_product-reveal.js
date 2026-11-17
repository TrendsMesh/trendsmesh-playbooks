/* 42 Product Launch Reveal - reference animation.
 * Topic (setting, replace it): "How do noise-cancelling earbuds make quiet?" - an invented, unbranded product ("Quiet
 * One"): the outer mic hears the hum, the chip makes the same wave flipped by 180 degrees, the speaker plays it, the
 * waves cancel. Works best on steady, low sounds.
 * Rendering (keep it): a keynote stage - near-black backdrop, one soft overhead pool of light, a dark floor mirroring
 * the product (a flipped copy masked to fade), dust motes, bokeh discs behind and in front (shallow depth of field).
 * The product is gradients only: a metal body whose horizontal gradient carries a specular stripe that slides as it
 * turns (front face narrows with cos, side face widens with sin), vertical shading, ice and warm rim lights, light
 * sweeps clipped to its silhouette. Clean sans headlines rise out of a mask (light eyebrow, bold name) with a sheen;
 * spec callouts are dot + ring, hairline leader, label. The key number counts up while its weight grows.
 * Motion: slow dollies with an orbit drift, the product turning slowly, dips through black; no overshoot or bounce.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // -------------------- palette and type (from the card)
  const PAL = { stage: "#060608", floor: "#15161b", graphite: "#2b2d34", silver: "#b9bdc5", white: "#f6f7f9", mist: "#8c9099", ice: "#86c9ff", warm: "#ffcf9e" };
  const HEAD = "Inter Tight", BODY = "Inter";
  const DUR = 13;
  const BEATS = [0, 2.3, 4.6, 6.8, 9.0, 11.0];
  let F = null, U = 1, T = 0, P = false;

  /** Visibility of beat i: a slow fade up from black and a slow fade down into black (a dip between beats). */
  function vis(i) {
    const a = BEATS[i], b = i + 1 < BEATS.length ? BEATS[i + 1] : DUR + 1;
    const fin = i === 0 ? 1 : B.span(T, a - 0.05, a + 0.5, "inOutSine");
    const fout = 1 - B.span(T, b - 0.42, b + 0.02, "inOutSine");
    return Math.min(fin, fout);
  }
  /** Per-beat camera: a slow dolly in plus an orbit-like sideways drift (alternating direction). */
  function cam(i, W, H) {
    const a = BEATS[i], b = i + 1 < BEATS.length ? BEATS[i + 1] : DUR;
    const p = B.span(T, a - 0.4, b + 0.4, "inOutSine"), dir = i % 2 ? -1 : 1;
    return { zoom: 1 + 0.06 * p, x: W / 2 + dir * (p - 0.5) * 4 * U, y: H / 2 };
  }

  // -------------------- stage: backdrop, floor, light pool, motes, bokeh
  function stage(ctx, W, H, floorY, cx) {
    ctx.fillStyle = PAL.stage;
    ctx.fillRect(0, 0, W, H);
    const D = Math.hypot(W, H);
    // the overhead soft box: a tall elliptical pool of grey-blue light falling on the product
    ctx.save();
    ctx.translate(cx, floorY - H * 0.18);
    ctx.scale(1, 1.5);
    ctx.fillStyle = B.radial(ctx, 0, 0, 0, D * 0.42, [[0, "rgba(58,64,80,0.55)"], [0.45, "rgba(30,33,44,0.35)"], [1, "rgba(6,6,8,0)"]]);
    ctx.fillRect(-D, -D, 2 * D, 2 * D);
    ctx.restore();
    // floor: a slightly lifted dark plane with a soft horizon band
    ctx.fillStyle = B.linear(ctx, 0, floorY, 0, H, [[0, "rgba(21,22,27,0.9)"], [1, "rgba(8,8,10,1)"]]);
    ctx.fillRect(0, floorY, W, H - floorY);
    ctx.fillStyle = B.linear(ctx, 0, floorY - 3 * U, 0, floorY + 3 * U, [[0, "rgba(140,150,170,0)"], [0.5, "rgba(140,150,170,0.07)"], [1, "rgba(140,150,170,0)"]]);
    ctx.fillRect(0, floorY - 3 * U, W, 6 * U);
  }
  function floorPool(ctx, x, floorY, rx) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.translate(x, floorY);
    ctx.scale(1, 0.12);
    ctx.fillStyle = B.radial(ctx, 0, 0, 0, rx, [[0, "rgba(120,130,150,0.22)"], [1, "rgba(120,130,150,0)"]]);
    ctx.fillRect(-rx, -rx, 2 * rx, 2 * rx);
    ctx.restore();
  }
  /** Dust motes drifting slowly up through the light: tiny specks, a few out-of-focus soft dots. */
  function motes(ctx, W, H, cx, seed) {
    const r = B.rng(seed);
    for (let i = 0; i < 46; i++) {
      const x = cx + r.range(-0.48, 0.48) * W + B.noise1(T * 0.15 + i, i) * 3 * U;
      const y = B.fract(r() - T * r.range(0.008, 0.02)) * H;
      const soft = i % 9 === 0, rad = soft ? r.range(1.2, 2.4) * U : r.range(0.12, 0.3) * U;
      const a = (soft ? 0.08 : 0.5) * (0.5 + 0.5 * Math.sin(T * r.range(0.8, 2) + i)) * (1 - Math.abs(x - cx) / W);
      if (a <= 0.01) continue;
      if (soft) B.glow(ctx, x, y, rad, PAL.silver, a, { add: true });
      else { ctx.fillStyle = B.rgba(PAL.white, a); ctx.fillRect(x, y, rad, rad); }
    }
  }
  /** Out-of-focus bokeh discs: flat discs with a slightly brighter rim and soft edge (a lens wide open). */
  function bokeh(ctx, W, H, seed, n, rMin, rMax, alpha) {
    const r = B.rng(seed);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < n; i++) {
      const x = r() * W, y = r.range(0.05, 0.95) * H, R = r.range(rMin, rMax) * U, col = r.pick([PAL.ice, PAL.warm, PAL.silver, PAL.silver]);
      const a = alpha * (0.6 + 0.4 * Math.sin(T * 0.4 + i * 1.7));
      ctx.fillStyle = B.radial(ctx, x, y, 0, R, [[0, B.rgba(col, a * 0.55)], [0.82, B.rgba(col, a * 0.8)], [0.9, B.rgba(col, a)], [1, B.rgba(col, 0)]]);
      ctx.fillRect(x - R, y - R, 2 * R, 2 * R);
    }
    ctx.restore();
  }

  // -------------------- type: mask-wipe headlines and the sheen
  /** A line of type rising out of a mask (its own line box clips it), eased; returns its measure. */
  function maskLine(ctx, str, x, y, size, weight, p, o = {}) {
    const fam = o.family || HEAD, align = o.align || "center";
    const m = B.measureText(ctx, str, { size, family: fam, weight, maxW: o.maxW, maxLines: o.maxLines || 1, letterSpacing: o.ls, lineH: o.lineH || 1.1 });
    if (p <= 0) return m;
    const sz = m.size, w = m.width, e = B.ease.outCubic(B.clamp(p));
    const x0 = align === "center" ? x - w / 2 : align === "left" ? x : x - w;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x0 - sz, y - m.height / 2 - sz * 0.15, w + 2 * sz, m.height + sz * 0.3);
    ctx.clip();
    const yy = y + (1 - e) * m.height * 1.05;
    const fill = o.color || B.linear(ctx, 0, yy - m.height / 2, 0, yy + m.height / 2, [[0, PAL.white], [0.6, "#dfe2e8"], [1, PAL.silver]]);
    B.text(ctx, str, x, yy, { size: sz, family: fam, weight, color: fill, align, maxW: o.maxW, maxLines: o.maxLines || 1, letterSpacing: o.ls, lineH: o.lineH || 1.1, alpha: (o.alpha ?? 1) * B.clamp(p * 1.5) });
    ctx.restore();
    return m;
  }
  /** Light sweep across something already drawn (text or product): draw it again into a scratch, keep only a
   *  moving diagonal band of it, add it back. drawFn(g) draws in the same transform as ctx. */
  function sheen(ctx, W, H, p, drawFn, strength = 0.75) {
    if (p <= 0 || p >= 1) return;
    const g = B.scratch("pr-sheen", W, H);
    g.setTransform(ctx.getTransform());
    g.globalAlpha = 1;
    drawFn(g);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "source-in";
    const x = B.lerp(-0.3 * W, 1.3 * W, B.ease.inOutSine(p)), bw = 0.16 * Math.max(W, H);
    g.fillStyle = B.linear(g, x - bw, 0, x + bw, bw * 0.5, [[0, "rgba(255,255,255,0)"], [0.5, `rgba(255,255,255,${strength})`], [1, "rgba(255,255,255,0)"]]);
    g.fillRect(0, 0, W, H);
    g.globalCompositeOperation = "source-over";
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = "lighter";
    ctx.drawImage(g.canvas, 0, 0);
    ctx.restore();
  }

  // -------------------- the hero product (the setting: replace it)
  /** Horizontal metal gradient for a turning body: falloff at both edges, a specular stripe at sp, a hard edge
   *  highlight then shadow at the face junction j (front face 0..j, side face j..1). Mirrored when flip. */
  function metalStops(j, sp, flip) {
    const st = [[0, "#1c1d22"], [0.05, "#575b63"], [Math.max(0.06, sp - 0.14), "#9fa4ad"], [sp, "#f1f3f6"], [Math.min(j - 0.03, sp + 0.1), "#aab0b8"], [j - 0.012, "#8b9098"], [j + 0.006, "#3a3d44"], [Math.min(0.97, j + (1 - j) * 0.5), "#25272d"], [0.975, "#3e4149"], [1, "#141518"]];
    st.forEach((e) => (e[0] = B.clamp(e[0])));
    st.sort((a, b) => a[0] - b[0]);
    return flip ? st.map(([k, c]) => [1 - k, c]).reverse() : st;
  }
  /** The charging case: a rounded box turning about its vertical axis. o: { lit 0..1, led, sweep 0..1 } */
  function caseShape(ctx, x, y, s, th, o = {}) {
    const c = Math.cos(th), sn = Math.sin(th);
    const fw = s * Math.abs(c), sw = s * 0.5 * Math.abs(sn), tw = fw + sw, h = s * 0.58, r = h * 0.5; // a capsule-shaped case
    const x0 = x - tw / 2, y0 = y - h / 2, flip = sn < 0;
    const j = fw / tw, sp = B.lerp(0.16, Math.max(0.2, j - 0.16), 0.5 + 0.5 * Math.sin(th * 2.4 + 0.4));
    const path = (g) => { g.beginPath(); B.roundRect(g, x0, y0, tw, h, r); };
    const lit = o.lit ?? 1;
    ctx.save();
    path(ctx);
    ctx.fillStyle = B.linear(ctx, x0, 0, x0 + tw, 0, metalStops(j, sp, flip));
    ctx.fill();
    ctx.clip();
    // vertical shading: the top catches the soft box, the base falls into shadow
    ctx.fillStyle = B.linear(ctx, 0, y0, 0, y0 + h, [[0, "rgba(255,255,255,0.18)"], [0.3, "rgba(255,255,255,0)"], [0.62, "rgba(0,0,0,0.12)"], [1, "rgba(0,0,0,0.62)"]]);
    ctx.fillRect(x0, y0, tw, h);
    // the lid seam runs across the front and the side
    const sy = y0 + h * 0.33;
    ctx.fillStyle = "rgba(8,8,10,0.75)";
    ctx.fillRect(x0, sy, tw, Math.max(1, 0.18 * U));
    ctx.fillStyle = "rgba(255,255,255,0.16)";
    ctx.fillRect(x0, sy + 0.2 * U, tw, Math.max(1, 0.1 * U));
    // status light on the front face
    const fx = flip ? x0 + sw + fw / 2 : x0 + fw / 2, ly = y0 + h * 0.74;
    if (o.led) B.glow(ctx, fx, ly, 3 * U, PAL.ice, 0.55 * o.led, { add: true });
    ctx.beginPath();
    B.circle(ctx, fx, ly, Math.max(1.5, 0.012 * s * Math.abs(c)));
    ctx.fillStyle = o.led ? B.mix("#3a3d44", "#e8f6ff", o.led) : "#3a3d44";
    ctx.fill();
    // darkness before the body is lit: the rim light arrives first
    if (lit < 1) { ctx.fillStyle = B.rgba(PAL.stage, 0.94 * (1 - lit)); ctx.fillRect(x0, y0, tw, h); }
    // rim lights: ice on the top edge, warm on the far lower edge (inner half of a stroke, clipped)
    ctx.lineWidth = 1.1 * U;
    ctx.strokeStyle = B.linear(ctx, x0 + tw * (flip ? 0 : 1), y0, x0 + tw * (flip ? 0.6 : 0.4), y0 + h * 0.7, [[0, B.rgba(PAL.ice, 0.95)], [0.45, B.rgba(PAL.ice, 0.15)], [1, B.rgba(PAL.ice, 0)]]);
    path(ctx);
    ctx.stroke();
    ctx.strokeStyle = B.linear(ctx, x0 + tw * (flip ? 1 : 0), y0 + h, x0 + tw * 0.5, y0 + h * 0.4, [[0, B.rgba(PAL.warm, 0.5)], [1, B.rgba(PAL.warm, 0)]]);
    path(ctx);
    ctx.stroke();
    // a light sweep gliding across inside the silhouette
    if (o.sweep > 0 && o.sweep < 1) {
      const bx = B.lerp(x0 - tw * 0.6, x0 + tw * 1.6, B.ease.inOutSine(o.sweep));
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = B.linear(ctx, bx - tw * 0.22, y0, bx + tw * 0.22, y0 + h * 0.4, [[0, "rgba(255,255,255,0)"], [0.5, "rgba(255,255,255,0.32)"], [1, "rgba(255,255,255,0)"]]);
      ctx.fillRect(x0, y0, tw, h);
    }
    ctx.restore();
    return { x0, y0, w: tw, h, bottom: y0 + h };
  }
  /** One earbud in a three-quarter view: matte ear tip, silver nozzle, metal body, glossy black outer face with the
   *  mic grille. Turning narrows the face disc and slides the specular. Returns the callout anchors. */
  function bud(ctx, x, y, s, th, o = {}) {
    const ct = Math.cos(th), st = Math.sin(th), k = 0.86 + 0.14 * ct;
    const nb = [x - 0.28 * s * k, y + 0.24 * s], ne = [x - 0.5 * s * k, y + 0.42 * s], tc = [x - 0.6 * s * k, y + 0.5 * s];
    const ang = Math.atan2(ne[1] - nb[1], ne[0] - nb[0]);
    ctx.save();
    // nozzle
    ctx.save();
    ctx.translate(nb[0], nb[1]);
    ctx.rotate(ang);
    const nl = Math.hypot(ne[0] - nb[0], ne[1] - nb[1]) + 0.06 * s;
    ctx.beginPath();
    B.capsule(ctx, -0.04 * s, -0.11 * s, nl, 0.22 * s);
    ctx.fillStyle = B.linear(ctx, 0, -0.11 * s, 0, 0.11 * s, ["#d9dce2", "#7d828b", "#2a2c32"]);
    ctx.fill();
    ctx.restore();
    // soft ear tip: matte graphite dome
    ctx.save();
    ctx.translate(tc[0], tc[1]);
    ctx.rotate(ang);
    ctx.beginPath();
    ctx.ellipse(0, 0, 0.15 * s, 0.2 * s, 0, 0, B.TAU);
    ctx.fillStyle = B.radial(ctx, -0.04 * s, -0.08 * s, 0, 0.24 * s, [[0, "#6a6e77"], [0.5, PAL.graphite], [1, "#101114"]]);
    ctx.fill();
    ctx.restore();
    // body
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, 0.5 * s * k, 0.43 * s, -0.18, 0, B.TAU);
    const hx = x - 0.2 * s + 0.14 * s * st, hy = y - 0.2 * s;
    ctx.fillStyle = B.radial(ctx, hx, hy, 0, 0.78 * s, [[0, "#f5f6f8"], [0.22, "#c3c7ce"], [0.55, "#6b7078"], [0.85, "#2a2c32"], [1, "#16171b"]]);
    ctx.fill();
    ctx.clip();
    ctx.lineWidth = 1.2 * U;
    ctx.strokeStyle = B.linear(ctx, x + 0.4 * s, y - 0.4 * s, x - 0.1 * s, y + 0.1 * s, [[0, B.rgba(PAL.ice, 0.9)], [1, B.rgba(PAL.ice, 0)]]);
    ctx.beginPath();
    ctx.ellipse(x, y, 0.5 * s * k, 0.43 * s, -0.18, 0, B.TAU);
    ctx.stroke();
    if (o.chip) { // the chip inside, glimpsed as a glowing outline
      const cx = x - 0.12 * s, cy = y + 0.02 * s, cw = 0.16 * s;
      B.glow(ctx, cx, cy, cw * 1.3, PAL.ice, 0.5 * o.chip, { add: true });
      ctx.strokeStyle = B.rgba(PAL.white, 0.8 * o.chip);
      ctx.lineWidth = 0.18 * U;
      ctx.beginPath();
      B.roundRect(ctx, cx - cw / 2, cy - cw / 2, cw, cw, cw * 0.18);
      ctx.stroke();
    }
    if (o.sweep > 0 && o.sweep < 1) {
      const bx = B.lerp(x - s, x + s, B.ease.inOutSine(o.sweep));
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = B.linear(ctx, bx - 0.2 * s, y - s, bx + 0.2 * s, y - 0.6 * s, [[0, "rgba(255,255,255,0)"], [0.5, "rgba(255,255,255,0.35)"], [1, "rgba(255,255,255,0)"]]);
      ctx.fillRect(x - s, y - s, 2 * s, 2 * s);
    }
    ctx.restore();
    // glossy black outer face with a hairline ice ring and the mic grille
    const fx = x + 0.17 * s * k + 0.05 * s * st, fy = y - 0.04 * s, frx = 0.27 * s * (0.6 + 0.25 * ct), fry = 0.31 * s;
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(fx, fy, frx, fry, -0.18, 0, B.TAU);
    ctx.fillStyle = B.linear(ctx, fx, fy - fry, fx, fy + fry, [[0, "#3a3d45"], [0.45, "#0b0c0f"], [1, "#1b1c21"]]);
    ctx.fill();
    ctx.strokeStyle = B.rgba(PAL.ice, 0.45);
    ctx.lineWidth = 0.22 * U;
    ctx.stroke();
    ctx.clip();
    ctx.beginPath(); // the reflection of the soft box on the glass
    ctx.ellipse(fx - frx * 0.15, fy - fry * 0.62, frx * 0.9, fry * 0.38, -0.18, 0, B.TAU);
    ctx.fillStyle = "rgba(255,255,255,0.13)";
    ctx.fill();
    const gx = fx + frx * 0.1, gy = fy - fry * 0.42;
    ctx.fillStyle = "rgba(150,156,166,0.65)";
    for (let i = -3; i <= 3; i++) for (let jj = -1; jj <= 1; jj++) {
      if (Math.abs(i) + Math.abs(jj) * 2 > 4) continue;
      ctx.beginPath();
      B.circle(ctx, gx + i * frx * 0.09, gy + jj * fry * 0.08, Math.max(1, 0.012 * s));
      ctx.fill();
    }
    ctx.restore();
    ctx.restore();
    return { mic: [gx, gy], chip: [x - 0.12 * s, y + 0.02 * s], speaker: [(nb[0] + ne[0]) / 2, (nb[1] + ne[1]) / 2], tip: tc, bottom: tc[1] + 0.2 * s, right: x + 0.5 * s * k };
  }
  /** Draw something with its floor reflection: a flipped copy masked to fade out below the floor line. */
  function reflected(ctx, W, H, floorY, depth, drawFn) {
    const g = B.scratch("pr-refl", W, H);
    g.setTransform(ctx.getTransform());
    g.translate(0, 2 * floorY);
    g.scale(1, -1);
    drawFn(g);
    g.setTransform(ctx.getTransform());
    g.globalCompositeOperation = "destination-in";
    g.fillStyle = B.linear(g, 0, floorY, 0, floorY + depth, [[0, "rgba(0,0,0,0.3)"], [1, "rgba(0,0,0,0)"]]);
    g.fillRect(-W, floorY, 3 * W, depth);
    g.fillStyle = "rgba(0,0,0,0)";
    g.globalCompositeOperation = "destination-out";
    g.fillRect(-W, -H, 3 * W, H + floorY); // nothing above the floor
    g.globalCompositeOperation = "source-over";
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(g.canvas, 0, 0);
    ctx.restore();
    drawFn(ctx);
  }
  /** A product drawn small and blurred (the background of a shot with shallow depth of field). */
  function blurred(ctx, x, y, s, blurU, drawFn) {
    const k = 0.25, size = Math.ceil(s * 2.4 * k), g = B.scratch("pr-dof", size, size);
    g.save();
    g.translate(size / 2, size / 2);
    g.scale(k, k);
    drawFn(g, 0, 0, s);
    g.restore();
    ctx.save();
    ctx.filter = `blur(${(blurU * U * k).toFixed(1)}px)`;
    ctx.drawImage(g.canvas, x - size / (2 * k), y - size / (2 * k), size / k, size / k);
    ctx.restore();
  }

  // -------------------- spec callouts and waves
  /** Dot + hairline ring on the product, a hairline leader with one elbow drawn on, the label rising at its end. */
  function callout(ctx, a, elbow, endX, label, p, size) {
    if (p <= 0) return;
    const e = B.ease.inOutCubic(B.clamp(p / 0.6)), right = endX > elbow[0];
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    B.glow(ctx, a[0], a[1], 2.6 * U, PAL.ice, 0.35 * e);
    ctx.restore();
    ctx.fillStyle = PAL.white;
    ctx.beginPath();
    B.circle(ctx, a[0], a[1], 0.55 * U * e);
    ctx.fill();
    ctx.strokeStyle = B.rgba(PAL.white, 0.7 * e);
    ctx.lineWidth = 0.16 * U;
    ctx.beginPath();
    B.circle(ctx, a[0], a[1], (1.2 + 0.6 * (1 - e)) * U);
    ctx.stroke();
    B.strokeReveal(ctx, [a, elbow, [endX, elbow[1]]], e, { width: 0.17 * U, color: B.rgba(PAL.white, 0.75), cap: "butt" });
    if (e >= 1) { ctx.fillStyle = PAL.white; ctx.beginPath(); B.circle(ctx, endX, elbow[1], 0.35 * U); ctx.fill(); }
    maskLine(ctx, label, endX, elbow[1] - size * 0.9, size, 500, B.clamp((p - 0.45) / 0.5), { family: BODY, align: right ? "right" : "left", color: PAL.white });
  }
  /** A steady hum as a waveform (a fundamental and a little second harmonic); sign -1 flips it. */
  function wavePts(x0, x1, y, amp, cycles, sign, phase, n = 140) {
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const q = i / n, a = B.TAU * cycles * q + phase, env = Math.sin(Math.PI * q) ** 0.4;
      pts.push([B.lerp(x0, x1, q), y + sign * amp * env * (Math.sin(a) + 0.22 * Math.sin(2 * a + 0.6))]);
    }
    return pts;
  }
  function drawWave(ctx, pts, col, p = 1, alpha = 1) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    B.strokeReveal(ctx, pts, p, { width: 1.6 * U, color: B.rgba(col, 0.12 * alpha) });
    B.strokeReveal(ctx, pts, p, { width: 0.6 * U, color: B.rgba(col, 0.3 * alpha) });
    ctx.restore();
    B.strokeReveal(ctx, pts, p, { width: 0.24 * U, color: B.rgba(col, alpha) });
  }

  // -------------------- layout by aspect
  function layout(W, H) {
    const s = F.safe;
    return P ? {
      titleCase: [W / 2, H * 0.5, 60 * U], titleText: [W / 2, H * 0.25], floorT: H * 0.5 + 60 * U * 0.29,
      bud: [W * 0.47, H * 0.5, 46 * U], numY: H * 0.46, steps: [H * 0.185, H * 0.44], closeCase: [W / 2, H * 0.52, 60 * U],
    } : {
      titleCase: [W * 0.68, H * 0.52, 40 * U], titleText: [s.x + 2 * U, H * 0.47], floorT: H * 0.52 + 40 * U * 0.29,
      bud: [W * 0.5, H * 0.56, 33 * U], numY: H * 0.47, steps: [H * 0.2, H * 0.56], closeCase: [W / 2, H * 0.58, 36 * U],
    };
  }

  // -------------------- beats
  function titleBeat(ctx, W, H, L, a) {
    const [cx, cy, cs] = L.titleCase, floorY = L.floorT, c = cam(0, W, H);
    const th = B.lerp(-0.75, 0.3, B.prog(T, 0, 2.6, "inOutSine"));
    const lit = B.span(T, 0.35, 1.3, "inOutSine"), rim = B.span(T, 0.05, 0.6);
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, floorY, cx);
    B.camera(ctx, W, H, c, () => bokeh(ctx, W, H, "pr-bk0", 7, 5, 13, 0.07 * lit), 0.35);
    B.camera(ctx, W, H, c, () => {
      floorPool(ctx, cx, floorY, cs * 1.1);
      B.contactShadow(ctx, cx, floorY, cs * 0.5, cs * 0.05, 0.7);
      ctx.globalAlpha = a * rim;
      reflected(ctx, W, H, floorY, cs * 0.45, (g) => caseShape(g, cx, cy, cs, th, { lit, led: B.span(T, 1.4, 1.8), sweep: B.span(T, 1.0, 2.0) }));
      ctx.globalAlpha = a;
      motes(ctx, W, H, cx, "pr-m0");
      const [tx, ty] = L.titleText, al = P ? "center" : "left";
      const ey = P ? ty - 9 * U : ty - 10 * U, sub = P ? H * 0.7 : ty + 10 * U;
      maskLine(ctx, "Introducing", tx, ey, (P ? 5.2 : 4.6) * U, 200, B.span(T, 0.5, 1.2), { align: al, ls: 0.12 });
      const nm = (g) => maskLine(g, "Quiet One", tx, ty, (P ? 14 : 12) * U, 700, B.span(T, 0.8, 1.6), { align: al, ls: -0.02 });
      nm(ctx);
      sheen(ctx, W, H, B.span(T, 1.5, 2.25), nm);
      maskLine(ctx, "Noise-cancelling earbuds", tx, sub, (P ? 4.6 : 4.0) * U, 400, B.span(T, 1.2, 1.9), { family: BODY, align: al, color: PAL.mist });
    });
    ctx.restore();
  }

  function diagramBeat(ctx, W, H, L, a) {
    const [bx, by, bs] = L.bud, c = cam(1, W, H), lt = T - BEATS[1], s = F.safe;
    const th = 0.35 * Math.sin(lt * 0.5 + 0.2);
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, by + bs * 0.75, bx);
    B.camera(ctx, W, H, c, () => bokeh(ctx, W, H, "pr-bk1", 8, 4, 12, 0.06), 0.35);
    B.camera(ctx, W, H, c, () => {
      floorPool(ctx, bx, by + bs * 0.75, bs * 1.2);
      motes(ctx, W, H, bx, "pr-m1");
      const A = bud(ctx, bx, by, bs, th, { chip: B.span(lt, 0.9, 1.4), sweep: B.span(lt, 0.2, 1.3) });
      maskLine(ctx, "Inside each bud", W / 2, P ? H * 0.175 : H * 0.15, (P ? 6.4 : 5.6) * U, 300, B.span(lt, 0.05, 0.6), {});
      const ls = (P ? 4.2 : 4.0) * U;
      // the arrow: outside noise travels in as a waveform and lands on the outer mic
      const wx0 = P ? s.r - 3 * U : Math.min(s.r, bx + bs * 1.45), wx1 = A.mic[0] + 2.5 * U;
      const wy = A.mic[1] + (P ? 0 : 0);
      const wp = B.span(lt, 0.3, 1.1, "inOutSine");
      const wave = wavePts(wx0, wx1, wy, 1.6 * U, 3.5, 1, -lt * 6, 80);
      drawWave(ctx, wave, PAL.mist, wp);
      if (wp > 0.97) {
        ctx.fillStyle = PAL.mist;
        ctx.beginPath();
        B.poly(ctx, [[wx1 - 0.3 * U, wy], [wx1 + 1.8 * U, wy - 1.1 * U], [wx1 + 1.8 * U, wy + 1.1 * U]], true);
        ctx.fill();
      }
      maskLine(ctx, "Outside noise", wx0, wy - (P ? 5.5 : 5) * U, ls, 500, B.span(lt, 0.6, 1.1), { family: BODY, align: "right", color: PAL.mist });
      // spec callouts
      const lx = s.x + 3 * U, rx = s.r - 3 * U;
      if (P) {
        callout(ctx, A.mic, [A.mic[0] + 4 * U, H * 0.33], rx, "Outer mic", B.span(lt, 0.5, 1.3), ls);
        callout(ctx, A.chip, [A.chip[0] - 10 * U, H * 0.37], lx, "Noise chip", B.span(lt, 0.8, 1.6), ls);
        callout(ctx, A.speaker, [A.speaker[0] - 4 * U, H * 0.64], lx, "Speaker", B.span(lt, 1.1, 1.9), ls);
        callout(ctx, A.tip, [A.tip[0] + 6 * U, H * 0.7], rx, "Soft ear tip", B.span(lt, 1.3, 2.1), ls);
      } else {
        callout(ctx, A.mic, [A.mic[0] + 4 * U, H * 0.3], s.x + s.w * 0.84, "Outer mic", B.span(lt, 0.5, 1.3), ls);
        callout(ctx, A.chip, [A.chip[0] - 10 * U, H * 0.36], lx + 6 * U, "Noise chip", B.span(lt, 0.8, 1.6), ls);
        callout(ctx, A.speaker, [A.speaker[0] - 6 * U, H * 0.74], lx + 6 * U, "Speaker", B.span(lt, 1.1, 1.9), ls);
        callout(ctx, A.tip, [A.tip[0] + 8 * U, H * 0.86], s.x + s.w * 0.84, "Soft ear tip", B.span(lt, 1.3, 2.1), ls);
      }
    });
    ctx.restore();
  }

  function numberBeat(ctx, W, H, L, a) {
    const c = cam(2, W, H), lt = T - BEATS[2], ny = L.numY, [bx, , bs] = L.bud;
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, H * 0.86, W / 2);
    // shallow depth of field: the bud big and out of focus behind the number, turning slowly
    B.camera(ctx, W, H, c, () => {
      ctx.globalAlpha = a * 0.55;
      blurred(ctx, W * (P ? 0.68 : 0.72), ny + (P ? 10 : 6) * U, bs * 1.5, 3.2, (g, x, y, s) => bud(g, x, y, s, 0.3 * Math.sin(lt * 0.4)));
      ctx.globalAlpha = a;
      bokeh(ctx, W, H, "pr-bk2", 9, 5, 14, 0.06);
    }, 0.5);
    B.camera(ctx, W, H, c, () => {
      motes(ctx, W, H, W / 2, "pr-m2");
      // a hairline half dial: a dot travels from 0 to 180 degrees as the number counts
      const k = B.span(lt, 0.35, 1.55, "inOutSine"), R = (P ? 40 : 38) * U, dy = ny + (P ? 8 : 12) * U;
      const arc = B.arcPts(W / 2, dy, R, Math.PI, Math.PI * 2, 90);
      B.strokeReveal(ctx, arc, 1, { width: 0.14 * U, color: B.rgba(PAL.white, 0.18 * B.span(lt, 0.1, 0.5)) });
      B.strokeReveal(ctx, arc, k, { width: 0.3 * U, color: B.rgba(PAL.ice, 0.9) });
      const d = B.pointAt(arc, k);
      if (lt > 0.35) { B.glow(ctx, d[0], d[1], 3 * U, PAL.ice, 0.7, { add: true }); ctx.fillStyle = PAL.white; ctx.beginPath(); B.circle(ctx, d[0], d[1], 0.6 * U); ctx.fill(); }
      [0, 1].forEach((e) => { ctx.fillStyle = B.rgba(PAL.white, 0.5 * B.span(lt, 0.2, 0.6)); ctx.beginPath(); B.circle(ctx, W / 2 + (e ? R : -R), dy, 0.4 * U); ctx.fill(); });
      maskLine(ctx, "PHASE FLIP", W / 2, ny - (P ? 22 : 14) * U, (P ? 4.4 : 4.0) * U, 300, B.span(lt, 0.1, 0.6), { family: BODY, ls: 0.3, color: PAL.ice });
      const weight = 200 + 100 * Math.round(5 * B.span(lt, 0.4, 1.6, "inOutSine"));
      const num = (g) => maskLine(g, B.counter(k, 180, { ease: "linear" }) + "°", W / 2, ny, (P ? 30 : 26) * U, weight, B.span(lt, 0.15, 0.7), { ls: -0.03 });
      num(ctx);
      sheen(ctx, W, H, B.span(lt, 1.5, 2.15), num, 0.9);
      if (lt > 1.45) B.glow(ctx, W / 2, ny, 30 * U, PAL.ice, 0.12 * Math.max(0, 1 - (lt - 1.45) / 0.8), { add: true });
      maskLine(ctx, P ? "The anti-noise wave is the hum\nturned upside down" : "The anti-noise wave is the hum turned upside down", W / 2, ny + (P ? 21 : 17) * U, (P ? 4.4 : 4.0) * U, 400, B.span(lt, 1.0, 1.6), { family: BODY, color: PAL.mist, maxLines: 2, lineH: 1.3 });
    });
    ctx.restore();
  }

  /** One numbered step: light number, bold title, grey caption, then its waveform. */
  function stepBlock(ctx, W, H, y, num, title, cap, lt0, waveFn) {
    const s = F.safe, x = s.x + 2 * U, ls = (P ? 4.3 : 4.0) * U;
    maskLine(ctx, num, x, y, (P ? 5 : 4.4) * U, 200, B.span(T, lt0, lt0 + 0.5), { align: "left", color: PAL.ice, ls: 0.1 });
    maskLine(ctx, title, x, y + (P ? 6.8 : 6.6) * U, (P ? 8.5 : 7.5) * U, 700, B.span(T, lt0 + 0.1, lt0 + 0.7), { align: "left" });
    maskLine(ctx, cap, x, y + (P ? 13.5 : 13) * U, ls, 400, B.span(T, lt0 + 0.3, lt0 + 0.9), { family: BODY, align: "left", color: PAL.mist, maxW: P ? s.w : W * 0.38 });
    waveFn(B.span(T, lt0 + 0.15, lt0 + 0.75, "inOutSine"));
  }

  function stepsBeat(ctx, W, H, L, a) {
    const c = cam(3, W, H), s = F.safe, [y1, y2] = L.steps;
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, P ? H * 0.78 : H * 0.88, W * 0.5);
    B.camera(ctx, W, H, c, () => bokeh(ctx, W, H, "pr-bk3", 8, 4, 12, 0.05), 0.35);
    B.camera(ctx, W, H, c, () => {
      motes(ctx, W, H, W / 2, "pr-m3");
      const wx0 = P ? s.x + 2 * U : W * 0.47, wx1 = s.r - 2 * U, off = P ? 30 * U : 7 * U, amp = (P ? 7 : 5) * U, ph = -T * 3;
      stepBlock(ctx, W, H, y1, "01", "Listen", "The outer mic hears the hum", 6.95, (p) => drawWave(ctx, wavePts(wx0, wx1, y1 + off, amp, 4, 1, ph), PAL.silver, p));
      stepBlock(ctx, W, H, y2, "02", "Flip", "The chip makes its mirror image", 7.35, (p) => {
        drawWave(ctx, wavePts(wx0, wx1, y2 + off, amp, 4, 1, ph), PAL.mist, p, 0.28);
        drawWave(ctx, wavePts(wx0, wx1, y2 + off, amp, 4, -1, ph), PAL.ice, B.clamp(p * 1.1 - 0.1));
      });
    });
    ctx.restore();
  }

  function cancelBeat(ctx, W, H, L, a) {
    const c = cam(4, W, H), s = F.safe, y = L.steps[0], lt = T - BEATS[4];
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, P ? H * 0.78 : H * 0.88, W * 0.5);
    B.camera(ctx, W, H, c, () => bokeh(ctx, W, H, "pr-bk4", 8, 4, 12, 0.05 * (1 - 0.6 * B.span(lt, 0.9, 1.4))), 0.35);
    B.camera(ctx, W, H, c, () => {
      motes(ctx, W, H, W / 2, "pr-m4");
      const gy = P ? H * 0.42 : H * 0.48, wx0 = P ? s.x + 2 * U : W * 0.47, wx1 = s.r - 2 * U, amp = (P ? 6 : 5) * U, ph = -T * 3;
      stepBlock(ctx, W, H, y, "03", "Cancel", P ? "Played together, the two waves cancel out" : "Together, the waves cancel out", 9.05, () => {});
      const meet = B.span(lt, 0.4, 1.0, "inOutSine"), flat = B.span(lt, 0.95, 1.4, "inOutSine"), gap = (P ? 16 : 9) * U * (1 - meet);
      const amp2 = amp * (1 - flat);
      drawWave(ctx, wavePts(wx0, wx1, gy - gap, amp2, 4, 1, ph), PAL.silver, B.span(lt, 0.1, 0.5), 1 - flat * 0.8);
      drawWave(ctx, wavePts(wx0, wx1, gy + gap, amp2, 4, -1, ph), PAL.ice, B.span(lt, 0.1, 0.5), 1 - flat * 0.8);
      if (flat > 0) { // the sum: a calm flat line, brightening, with a light sweep along it
        const line = [[wx0, gy], [wx1, gy]];
        drawWave(ctx, line, PAL.white, flat, 1);
        const sx = B.lerp(wx0, wx1, B.span(lt, 1.2, 1.9, "inOutSine"));
        if (lt > 1.2 && lt < 1.9) B.glow(ctx, sx, gy, 8 * U, PAL.ice, 0.6, { add: true });
      }
      const qx = P ? W / 2 : (wx0 + wx1) / 2;
      maskLine(ctx, "Quiet.", qx, P ? H * 0.6 : H * 0.72, (P ? 13 : 11) * U, 200, B.span(lt, 0.8, 1.4), {});
    });
    ctx.restore();
  }

  function closeBeat(ctx, W, H, L, a) {
    const [cx, cy, cs] = L.closeCase, c = cam(5, W, H), lt = T - BEATS[5], floorY = cy + cs * 0.29;
    const th = B.lerp(0.55, -0.2, B.prog(lt, 0, 2.2, "inOutSine"));
    ctx.save();
    ctx.globalAlpha = a;
    stage(ctx, W, H, floorY, cx);
    B.camera(ctx, W, H, c, () => bokeh(ctx, W, H, "pr-bk5", 8, 5, 13, 0.07), 0.35);
    B.camera(ctx, W, H, c, () => {
      floorPool(ctx, cx, floorY, cs * 1.1);
      B.contactShadow(ctx, cx, floorY, cs * 0.5, cs * 0.05, 0.7);
      reflected(ctx, W, H, floorY, cs * 0.45, (g) => caseShape(g, cx, cy, cs, th, { led: B.span(lt, 0.6, 1.0), sweep: B.span(lt, 0.8, 1.8) }));
      motes(ctx, W, H, cx, "pr-m5");
      const ty = P ? H * 0.22 : H * 0.17;
      const nm = (g) => maskLine(g, "Quiet One", W / 2, ty, (P ? 14 : 10.5) * U, 700, B.span(lt, 0.2, 0.9), { ls: -0.02 });
      nm(ctx);
      sheen(ctx, W, H, B.span(lt, 1.0, 1.7), nm);
      maskLine(ctx, "Hear the music, not the hum.", W / 2, ty + (P ? 10 : 9) * U, (P ? 5 : 4.6) * U, 300, B.span(lt, 0.6, 1.3), {});
      maskLine(ctx, "Works best on steady, low sounds", W / 2, P ? H * 0.745 : H * 0.865, (P ? 4.0 : 3.9) * U, 400, B.span(lt, 1.1, 1.7), { family: BODY, color: PAL.mist });
    });
    ctx.restore();
  }
  const SCENES = [titleBeat, diagramBeat, numberBeat, stepsBeat, cancelBeat, closeBeat];

  // -------------------- frame and finishing
  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    P = F.portrait;
    T = t;
    const L = layout(W, H);
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, W, H);
    // beats are drawn while visible; the overlap of two fades is a dip through black
    for (let i = 0; i < SCENES.length; i++) {
      const a = vis(i);
      if (a > 0.002) SCENES[i](ctx, W, H, L, a);
    }
    // fade up from black at the very start
    B.cover(ctx, W, H, "#000000", 1 - B.span(t, 0, 0.35));
    B.vignette(ctx, W, H, { amount: 0.6, inner: 0.5 });
    B.grain(ctx, W, H, { amount: 0.035, t });
  }

  // -------------------- sound: low swells, soft sub hits, shimmer, a calm pulsing bed
  SOUND.define("reveal-sub", (v, o) => {
    // soft sub hit: a deep sine dropping slowly, with a felt (not heard) attack
    v.tone({ f: 62, f2: 38, glide: 1.1, a: 0.02, len: o.dur ?? 1.4, peak: 0.7 });
    v.tone({ type: "triangle", f: 124, f2: 76, glide: 0.6, a: 0.01, len: 0.5, peak: 0.08 });
  }, { verb: 0.25 });
  SOUND.define("reveal-shimmer", (v, o) => {
    // airy glassy shimmer: high partials fading in slowly and out long, into a big room
    const root = v.hz(o.note ?? "D6");
    [1, 1.5, 2.01, 3].forEach((m, i) => v.tone({ f: root * m, at: i * 0.05, a: 0.25, len: 1.3, peak: 0.035 / (1 + i * 0.4) }));
  }, { verb: 0.85 });
  SOUND.define("reveal-hum", (v, o) => {
    // the noise being cancelled: a steady low hum that fades when the waves cancel
    const d = o.dur ?? 1;
    v.tone({ type: "sawtooth", f: 110, a: 0.3, hold: d - 0.6, len: 0.3, peak: 0.035 });
    v.tone({ f: 220, a: 0.3, hold: d - 0.6, len: 0.3, peak: 0.03 });
  }, { verb: 0.1 });

  function score(k) {
    k.bed("pad", 0, DUR, { notes: ["D2", "A2", "D3", "F#3", "A3"], gain: 0.55, bright: 480 });
    k.bed("pulse", 0, DUR, { bpm: 64, gain: 0.45 });
    // title: a long low swell lands on the light, a sub hit on the name, shimmer on the sweep
    k.at(0.0, "swell", { dur: 0.8, gain: 0.35 });
    k.at(0.8, "reveal-sub").at(0.85, "breath", { dur: 1.2, gain: 0.3 });
    k.at(1.5, "reveal-shimmer", { note: "D6" });
    k.at(2.05, "breath", { dur: 0.8, gain: 0.25 });
    // diagram: the hum outside, soft ticks as callouts land
    k.at(2.7, "reveal-hum", { dur: 1.5, gain: 0.7 });
    [2.9, 3.2, 3.5, 3.7].forEach((at, i) => k.at(at, "sonar", { note: ["A5", "D6", "F#6", "A6"][i], dur: 0.6, gain: 0.25 }));
    // key number: a swell into a sub hit and shimmer as the count lands
    k.at(4.4, "breath", { dur: 1.0, gain: 0.3 });
    k.at(4.95, "riser", { dur: 1.2, gain: 0.18 });
    k.at(6.15, "reveal-sub", { dur: 1.6 }).at(6.15, "reveal-shimmer", { note: "A6" }).at(6.2, "chord", { notes: ["D4", "A4", "F#5"], gain: 0.35 });
    // steps: the hum, then its mirror
    k.at(7.05, "reveal-hum", { dur: 1.9, gain: 0.8 });
    k.at(7.1, "sonar", { note: "D6", dur: 0.7, gain: 0.25 }).at(7.8, "sonar", { note: "A6", dur: 0.7, gain: 0.25 });
    k.at(8.6, "breath", { dur: 0.8, gain: 0.25 });
    // cancel: the hum stops dead as the waves meet; a soft sub and a long shimmer in the quiet
    k.at(9.05, "reveal-hum", { dur: 1.0, gain: 0.9 });
    k.at(10.0, "reveal-sub", { dur: 1.2, gain: 0.6 }).at(10.2, "reveal-shimmer", { note: "F#6" });
    // close: swell, sub hit on the name, a resolving chord with shimmer
    k.at(10.4, "swell", { dur: 0.8, gain: 0.35 });
    k.at(11.2, "reveal-sub", { dur: 1.6 }).at(11.25, "chord", { notes: ["D4", "F#4", "A4", "D5"], strum: 0.06, gain: 0.4 });
    k.at(12.0, "reveal-shimmer", { note: "D6" });
  }

  Player.register({
    id: "product-reveal",
    name: "Product Launch Reveal",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@200..800&family=Inter:wght@300;400;500;600&display=swap",
      faces: ['200 20px "Inter Tight"', '300 20px "Inter Tight"', '400 20px "Inter Tight"', '500 20px "Inter Tight"', '600 20px "Inter Tight"', '700 20px "Inter Tight"', '400 20px "Inter"', '500 20px "Inter"', '300 20px "Inter"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [2.0, 4.35, 6.5, 8.7, 10.7, 12.6],
    draw,
    score,
  });
})();
