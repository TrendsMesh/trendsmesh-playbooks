/* 09 X-Ray Lightbox. Topic (replace it): "How does a broken bone heal?" - a forearm fracture, three healing stages.
 * Rendering (keep it): negative films on a glowing box in a dark room; density adds up (bright rims round hollow
 * canals, faint tissue haze, white lead markers); grey-blue border, typed ID patch, edge printing, wear, chrome
 * clips. Words are only grease pencil (waxy, broken, doubled), typed ID or marker on torn masking tape.
 * Finish: halation, mottle, grain, glass bleeding over film edges, vignette. Motion: tubes flicker on, films
 * develop top to bottom, are tugged off and slapped up; a slow push-in.
 */
(function () {
  "use strict"; const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { room: "#070b12", base: "#0e2236", border: "#8fa6b8", dense: "#dbe8f2", glow: "#eaf4ff", yellow: "#ffe27a",
    red: "#e0392e", green: "#7fe08a", tape: "#e6d9b0", ink: "#23252b" };
  const MONO = "IBM Plex Mono", HAND = "Kalam", DUR = 12, BEATS = [0, 1.9, 4.0, 6.1, 8.4, 10.3];

  let U = 1;
  const fillPoly = (g, pts, closed = true) => { g.beginPath(); B.poly(g, pts, closed); g.fill(); };

  // ---- the subject in arm coordinates (the setting: replace these)
  /**
   * Arm coordinates into a film rectangle: s runs elbow (0) to wrist (1), n across in half-widths A (aFrac of the
   * short side); s0..s1 fills the rectangle (a crop zooms in); centre = the axis across it (0..1).
   */
  function armMapper(r, vertical, s0, s1, aFrac = 0.27, centre = 0.4) {
    const len = vertical ? r.h : r.w, A = (vertical ? r.w : r.h) * aFrac;
    const k = (s) => ((s - s0) / (s1 - s0)) * len;
    return { A, at: (s, n) => (vertical ? [r.x + r.w * centre + n * A, r.y + r.h - k(s)] : [r.x + k(s), r.y + r.h * centre + n * A]) };
  }
  /** Film B crop: the top 28 % stays bare for the pencil. */
  const cropRect = (r, pv) => ({ x: r.x, y: r.y + r.h * 0.28, w: r.w, h: r.h * (pv ? 0.5 : 0.72) });
  function cropMapper(r, panelVertical) {
    const a = cropRect(r, panelVertical);
    return panelVertical ? armMapper(a, true, 0.44, 0.68, 0.7, 0.5) : armMapper(a, false, 0.44, 0.68, 2.2, -0.24);
  }
  // bone profiles: centre n(s) and half-width w(s), in A
  const ULNA = { c: (s) => -0.42 + 0.05 * s, w: (s) => 0.1 + 0.13 * Math.exp(-Math.pow(s / 0.07, 2)) + 0.04 * Math.exp(-Math.pow((s - 0.96) / 0.03, 2)) + 0.02 * (1 - s) };
  const RADIUS = { c: (s) => 0.28 + 0.1 * s, w: (s) => 0.09 + 0.04 * Math.exp(-Math.pow(s / 0.03, 2)) + 0.03 * s + 0.2 * Math.pow(B.clamp((s - 0.78) / 0.2), 2) };
  const BREAK_S = 0.56;
  /** Outline of a bone between s0 and s1 as display points. */
  function boneOutline(M, bone, s0, s1, scale = 1) {
    const left = [], right = [], n = 60;
    for (let i = 0; i <= n; i++) {
      const s = B.lerp(s0, s1, i / n), c = bone.c(s), w = bone.w(s) * scale;
      left.push(M.at(s, c - w)); right.push(M.at(s, c + w));
    }
    // rounded ends
    const capA = B.arcPts(0, 0, 1, 0, Math.PI, 8).map(([x, y]) => [s0 - Math.abs(y) * 0.012, bone.c(s0) + x * bone.w(s0) * scale]);
    const capB = B.arcPts(0, 0, 1, 0, Math.PI, 8).map(([x, y]) => [s1 + Math.abs(y) * 0.012, bone.c(s1) - x * bone.w(s1) * scale]);
    return [...capA.map(([s, nn]) => M.at(s, nn)), ...right, ...capB.map(([s, nn]) => M.at(s, nn)), ...left.reverse()];
  }
  /** A bone as density: cortex, canal cut back, spongy ends; fracture stage 0-2. */
  function paintBone(g, M, bone, o = {}) {
    const W = g.canvas.width, H = g.canvas.height, lay = B.scratch("xray-bone", W, H);
    const s0 = o.s0 ?? -0.02, s1 = o.s1 ?? 1.0; lay.fillStyle = "#ffffff";
    fillPoly(lay, boneOutline(M, bone, s0, s1));
    Object.assign(lay, { globalCompositeOperation: "destination-out", globalAlpha: 0.095 });
    for (let i = 0; i < 10; i++) fillPoly(lay, boneOutline(M, bone, Math.max(s0, B.lerp(0.12, 0.5, i / 9)), Math.min(s1, B.lerp(0.88, 0.62, i / 9)), 0.58));
    const r = B.rng(o.seed ?? 3); lay.globalAlpha = 0.25;
    for (let i = 0; i < 260; i++) {
      const s = r() < 0.5 ? r.range(s0, 0.12) : r.range(0.86, s1), nn = bone.c(s) + r.range(-0.8, 0.8) * bone.w(s);
      const [x, y] = M.at(s, nn); lay.beginPath(); B.circle(lay, x, y, r.range(0.15, 0.45) * U);
      lay.fill();
    }
    lay.globalAlpha = 1;
    if (o.fracture != null) {
      // the break: an open gap, half filled, then bridged
      const st = o.fracture, gap = [];
      for (let i = 0; i <= 12; i++) {
        const k = i / 12, nn = bone.c(BREAK_S) + B.lerp(-1.6, 1.6, k) * bone.w(BREAK_S);
        gap.push(M.at(BREAK_S + (k - 0.5) * 0.05 + (i % 2 ? 0.006 : -0.006), nn));
      }
      Object.assign(lay, { globalAlpha: [1, 0.5, 0][st], lineWidth: Math.max(1.5, (st ? 0.05 : 0.075) * M.A), lineJoin: "round" });
      lay.beginPath(); B.poly(lay, gap); lay.stroke();
      Object.assign(lay, { globalAlpha: 1, globalCompositeOperation: "source-over" });
    }
    lay.globalCompositeOperation = "source-over";
    // density adds up: each bone is added onto the film
    g.save();
    Object.assign(g, { globalCompositeOperation: "lighter", globalAlpha: o.alpha ?? 0.46, filter: `blur(${(0.12 * U).toFixed(2)}px)` });
    g.drawImage(lay.canvas, 0, 0); g.restore();
    const st = o.fracture;
    if (st == null) return;
    // healing: faint haze, fuzzy bulge, firm spindle
    const [cx, cy] = M.at(BREAK_S, bone.c(BREAK_S)), rr = bone.w(BREAK_S) * M.A * [3.2, 2.5, 1.6][st];
    const a = M.at(BREAK_S - 0.05, bone.c(BREAK_S - 0.05)), b = M.at(BREAK_S + 0.05, bone.c(BREAK_S + 0.05));
    g.save();
    Object.assign(g, { globalCompositeOperation: "lighter", globalAlpha: [0.3, 0.62, 0.5][st] });
    g.translate(cx, cy);
    g.rotate(Math.atan2(b[1] - a[1], b[0] - a[0]));
    g.scale([1.3, 2.1, 1.5][st], 1);
    g.fillStyle = B.radial(g, 0, 0, 0, rr, [B.rgba(PAL.dense, st ? 1 : 0.6), B.rgba(PAL.dense, st === 2 ? 0.9 : 0.45), B.rgba(PAL.dense, 0)]);
    g.fillRect(-rr, -rr, rr * 2, rr * 2);
    g.restore();
  }
  /** Carpal bones and the hand bones' bases. */
  function paintHand(g, M, seed) {
    const r = B.rng(seed), W = g.canvas.width, H = g.canvas.height, lay = B.scratch("xray-bone", W, H);
    g.save(); g.globalCompositeOperation = "lighter";
    for (let i = 0; i < 8; i++) {
      lay.clearRect(0, 0, W, H);
      const s = 1.04 + (i % 2) * 0.07 + r.range(-0.01, 0.01), nn = -0.55 + Math.floor(i / 2) * 0.36 + r.range(-0.04, 0.04);
      const [x, y] = M.at(s, nn), rad = M.A * r.range(0.13, 0.18);
      const oval = (k, rot) => { lay.beginPath(); lay.ellipse(x, y, rad * k, rad * k * 0.75, rot, 0, B.TAU); lay.fill(); };
      lay.fillStyle = "#fff"; oval(1, r() * 3);
      Object.assign(lay, { globalCompositeOperation: "destination-out", globalAlpha: 0.22 });
      oval(0.55, 0);
      Object.assign(lay, { globalCompositeOperation: "source-over", globalAlpha: 1 });
      g.globalAlpha = 0.4; g.drawImage(lay.canvas, 0, 0);
    }
    g.restore();
    for (let i = 0; i < 5; i++) {
      const nn = -0.62 + i * 0.3;
      const meta = { c: () => nn + 0.04 * (i - 2), w: (s) => 0.07 + 0.03 * Math.exp(-Math.pow((s - 1.22) / 0.02, 2)) };
      paintBone(g, M, meta, { s0: 1.21, s1: 1.45, alpha: 0.5, seed: 70 + i });
    }
  }
  /** Soft tissue: a faint grey haze of the forearm's outline. */
  function paintTissue(g, M, s0, s1, alpha) {
    const pts = [], back = [];
    for (let i = 0; i <= 40; i++) {
      const s = B.lerp(s0, s1, i / 40), hw = 1.05 - 0.28 * B.clamp(s) + 0.1 * Math.exp(-Math.pow((s - 1.2) / 0.15, 2));
      pts.push(M.at(s, -hw)); back.push(M.at(s, hw * 0.98));
    }
    g.save();
    Object.assign(g, { globalCompositeOperation: "lighter", filter: `blur(${(1.2 * U).toFixed(1)}px)`, fillStyle: B.rgba(PAL.dense, alpha) });
    fillPoly(g, [...pts, ...back.reverse()]); g.restore();
  }

  // ---- x-ray film helpers (reuse these)
  /** The exposed field: blue-black base with broad mottle. */
  function paintBase(g, r, seed) {
    g.fillStyle = B.linear(g, r.x, r.y, r.x + r.w, r.y + r.h, [B.shade(PAL.base, 0.05), PAL.base, B.shade(PAL.base, -0.25)]);
    g.fillRect(r.x, r.y, r.w, r.h);
    B.clip(g, () => g.rect(r.x, r.y, r.w, r.h), () => B.mottle(g, g.canvas.width, g.canvas.height, { amount: 0.18, feature: 0.18, seed, mode: "soft-light" }));
  }
  /** Halation: a wide soft glow from the brightest dense parts. */
  function halation(g, amount = 0.2) {
    const w = g.canvas.width, h = g.canvas.height, q = 4, s = B.scratch("xray-halo", Math.ceil(w / q), Math.ceil(h / q));
    s.filter = "brightness(0.9) contrast(2.2)";
    s.drawImage(g.canvas, 0, 0, s.canvas.width, s.canvas.height);
    s.filter = "none";
    const b = B.scratch("xray-halo2", s.canvas.width, s.canvas.height);
    b.filter = `blur(${(1.6 * U / q).toFixed(2)}px)`;
    b.drawImage(s.canvas, 0, 0); g.save();
    Object.assign(g, { globalCompositeOperation: "lighter", globalAlpha: amount });
    g.drawImage(b.canvas, 0, 0, w, h); g.restore();
  }
  /** Wear: faint scratches, dust specks, pinholes. */
  function wear(g, r, seed) {
    const rr = B.rng(seed); g.save(); g.lineCap = "round";
    for (let i = 0; i < 6; i++) {
      const x = r.x + rr() * r.w, y = r.y + rr() * r.h * 0.5, len = rr.range(0.2, 0.7) * r.h;
      g.strokeStyle = B.rgba(PAL.dense, rr.range(0.05, 0.14));
      g.lineWidth = Math.max(0.6, rr.range(0.05, 0.12) * U);
      g.beginPath(); g.moveTo(x, y);
      g.quadraticCurveTo(x + rr.range(-1, 1) * U, y + len / 2, x + rr.range(-1.5, 1.5) * U, y + len);
      g.stroke();
    }
    for (let i = 0; i < 40; i++) {
      g.fillStyle = B.rgba("#000000", rr.range(0.25, 0.6));
      fillPoly(g, B.arcPts(r.x + rr() * r.w, r.y + rr() * r.h, rr.range(0.06, 0.2) * U, 0, B.TAU, 8));
    }
    for (let i = 0; i < 7; i++) {
      const x = r.x + rr() * r.w, y = r.y + rr() * r.h;
      B.glow(g, x, y, 0.6 * U, "#ffffff", 0.5, { add: true });
      g.fillStyle = "#ffffff"; g.fillRect(x - 0.5, y - 0.5, 1.2, 1.2);
    }
    g.restore();
  }
  /** Lead marker: a blocky letter, pure white. */
  function leadMarker(g, ch, x, y, size) {
    g.save();
    Object.assign(g, { font: B.font(size, MONO, 700), textAlign: "center", textBaseline: "middle", fillStyle: "#ffffff" });
    g.fillRect(x - size * 0.45, y - size * 0.55, size * 0.9, size * 1.1);
    g.fillStyle = B.mix(PAL.base, "#000000", 0.2);
    g.fillText(ch, x, y + size * 0.05); g.restore();
  }
  /**
   * ID patch of typed lines: the small ID lines are texture (title-block cells); the counter line `big` (size bs)
   * is what the viewer reads, so it is typed big. up: y is the patch's bottom edge.
   */
  function idPatch(g, x, y, up, size, lines, big, bs) {
    g.save();
    const fs = (z, wt) => (g.font = B.font(z, MONO, wt));
    fs(size, 500);
    let w = Math.max(...lines.map((l) => g.measureText(l).width));
    if (big) w = Math.max(w, (fs(bs, 700), g.measureText(big).width));
    w += size * 1.4;
    const h = lines.length * size * 1.3 + (big ? bs * 1.3 : 0) + size * 0.9;
    if (up) y -= h; g.fillStyle = "#e2e6e3"; g.fillRect(x, y, w, h);
    g.fillStyle = B.rgba("#9aa3a6", 0.4);
    g.fillRect(x, y + h - size * 0.25, w, size * 0.25);
    g.fillStyle = PAL.ink; g.textBaseline = "middle";
    fs(size, 500);
    B.texture(g, () => lines.forEach((l, i) => g.fillText(l, x + size * 0.7, y + size * 0.45 + size * 1.3 * (i + 0.5))));
    if (big) {
      fs(bs, 700);
      g.fillText(big, x + size * 0.7, y + size * 0.45 + size * 1.3 * lines.length + bs * 0.65);
    }
    g.restore();
  }
  /** Tiny edge printing along the unexposed margin (texture). */
  function edgePrint(g, x, y, len, size) {
    g.save(); g.translate(x, y); g.font = B.font(size, MONO, 500);
    g.fillStyle = B.rgba("#2c3b47", 0.6); g.textBaseline = "middle";
    let xx = 0, i = 0;
    B.texture(g, () => {
      while (xx < len) {
        const s = ["SAFETY FILM", "7", "BLUE BASE", "24"][i++ % 4];
        g.fillText(s, xx, 0); xx += g.measureText(s).width + size * 3;
      }
    });
    g.restore();
  }
  /** A whole film (cached): border, field, halation, wear, edge print. */
  function filmLayer(key, fw, fh, paintField) {
    return B.layer("xray-film:" + key, fw, fh, (g, w, h) => {
      const b = Math.round(Math.min(w, h) * 0.045), field = { x: b, y: b, w: w - 2 * b, h: h - 2 * b };
      g.fillStyle = PAL.border; g.fillRect(0, 0, w, h);
      g.fillStyle = B.linear(g, 0, 0, w, h, [B.rgba("#ffffff", 0.08), B.rgba("#000000", 0.06)]);
      g.fillRect(0, 0, w, h); paintField(g, field); halation(g, 0.22);
      wear(g, field, B.hash(key) % 1000);
      edgePrint(g, b * 1.2, b * 0.5, w - b * 2.4, b * 0.38);
    });
  }

  // ---- grease pencil, tape, lightbox
  /** Grease pencil on the glass: broken, doubled, revealed to p. */
  function wax(g, pts, p, color, width, seed) {
    if (p <= 0) return;
    const part = B.trim(B.wobble(B.densify(pts, 2 * U), { amp: 0.25 * U, freq: 1.5, seed }), 0, p);
    if (part.length < 2) return; const r = B.rng(seed), dash = [];
    for (let i = 0; i < 12; i++) dash.push(r.range(2.5, 9) * U, r.range(0.15, 0.6) * U);
    const pass = (a, lw) => { g.globalAlpha *= a; g.lineWidth = lw; g.beginPath(); B.poly(g, part); g.stroke(); };
    g.save();
    Object.assign(g, { strokeStyle: color, lineCap: "round", lineJoin: "round" });
    g.setLineDash(dash); pass(1, width);
    g.lineDashOffset = 3 * U; // doubled pass
    g.translate(width * 0.35, width * 0.25); pass(0.6, width * 0.6);
    g.restore();
  }
  /** Loose ring that overshoots where it started. */
  function waxRing(g, cx, cy, rx, ry, p, color, width, seed, rot = -0.2) {
    const pts = [];
    for (let i = 0; i <= 48; i++) {
      const a = -2.2 + (i / 48) * (B.TAU * 1.12), k = 1 + 0.06 * Math.sin(a * 2 + seed);
      pts.push([cx + Math.cos(a + rot) * rx * k, cy + Math.sin(a + rot) * ry * k * (1 + 0.05 * (i / 48))]);
    }
    wax(g, pts, p, color, width, seed);
  }
  /** Curved arrow stroke, then two quick head strokes. */
  function waxArrow(g, pts, p, color, width, seed) {
    wax(g, pts, B.clamp(p / 0.75), color, width, seed);
    const hp = B.clamp((p - 0.75) / 0.25); if (hp <= 0) return;
    const [x, y, a] = B.pointAt(pts, 1), hl = 3 * U;
    wax(g, [[x - Math.cos(a - 0.5) * hl, y - Math.sin(a - 0.5) * hl], [x, y]], B.clamp(hp * 2), color, width, seed + 1);
    wax(g, [[x - Math.cos(a + 0.5) * hl, y - Math.sin(a + 0.5) * hl], [x, y]], B.clamp(hp * 2 - 1), color, width, seed + 2);
  }
  /** Grease pencil handwriting, written left to right. */
  function waxText(g, text, x, y, size, p, color, o = {}) {
    if (p <= 0) return 0; g.save(); g.font = B.font(size, HAND, 700);
    const w = g.measureText(text).width, x0 = o.align === "left" ? x : x - w / 2;
    g.beginPath();
    g.rect(x0 - size, y - size * 1.2, (w + size * 1.2) * B.clamp(p) + size, size * 2.4);
    g.clip();
    Object.assign(g, { fillStyle: color, textAlign: "left", textBaseline: "middle" });
    g.translate(x0, y); g.rotate(o.rot ?? -0.03); g.fillText(text, 0, 0);
    g.globalAlpha *= 0.45;
    g.fillText(text, size * 0.04, size * 0.03); // doubled
    g.restore(); return w;
  }
  /** Masking tape, zigzag torn ends, marker capitals. */
  function tape(ctx, cx, cy, text, size, press, seed, o = {}) {
    if (press <= 0) return; ctx.save(); ctx.font = B.font(size, HAND, 700);
    const tw = Math.min(ctx.measureText(text).width, o.maxW ?? Infinity), w = tw + size * 2.2, h = size * 1.75;
    const k = B.ease.outBack(B.clamp(press), 2.5);
    ctx.translate(cx, cy); ctx.rotate(o.rot ?? -0.015);
    ctx.scale(0.94 + 0.06 * k, 0.94 + 0.06 * k); ctx.globalAlpha *= B.clamp(press * 3);
    const r = B.rng(seed), pts = [];
    // zigzag torn ends: down the right end, back up the left
    for (let j = 0; j < 18; j++) {
      const i = j < 9 ? j : 17 - j, sd = j < 9 ? 1 : -1;
      pts.push([sd * (w / 2 + (i % 2 ? 0.28 : 0) * size) + r.range(-0.1, 0.1) * size, -h / 2 + (h * i) / 8]);
    }
    ctx.beginPath(); B.poly(ctx, pts, true);
    B.withShadow(ctx, { color: "rgba(0,0,0,0.45)", blur: 0.8 * U, y: 0.3 * U }, () => {
      ctx.fillStyle = B.rgba(PAL.tape, 0.94); ctx.fill();
    });
    ctx.save(); ctx.clip();
    for (let i = 0; i < 26; i++) {
      ctx.fillStyle = B.rgba(i % 2 ? "#ffffff" : "#8a7b52", r.range(0.04, 0.1));
      ctx.fillRect(-w, -h / 2 + r() * h, w * 2, r.range(0.05, 0.2) * size);
    }
    ctx.restore();
    Object.assign(ctx, { fillStyle: PAL.ink, textAlign: "center", textBaseline: "middle" });
    ctx.beginPath();
    ctx.rect(-w / 2, -h, w * B.clamp((press - 0.25) / 0.75), h * 2);
    ctx.clip(); ctx.fillText(text, 0, size * 0.1, o.maxW);
    ctx.restore();
  }
  /** The viewing box: glass, brighter over each tube, banding, fall-off. */
  function lightbox(ctx, box, tubes) {
    const n = tubes.length, V = box.h > box.w, a0 = V ? box.y : box.x, len = V ? box.h : box.w;
    const lit = tubes.reduce((a, b) => a + b, 0) / n;
    // strips across the box's long axis
    const strip = (p, l) => (V ? ctx.fillRect(box.x, p, box.w, l) : ctx.fillRect(p, box.y, l, box.h));
    ctx.save();
    ctx.fillStyle = B.mix("#1a222c", PAL.glow, 0.92 * lit);
    ctx.fillRect(box.x, box.y, box.w, box.h); ctx.globalCompositeOperation = "lighter";
    tubes.forEach((v, i) => {
      const c = a0 + ((i + 0.5) / n) * len, hh = len / n, st = [B.rgba("#ffffff", 0), B.rgba("#ffffff", 0.22 * v), B.rgba("#ffffff", 0)];
      ctx.fillStyle = V ? B.linear(ctx, 0, c - hh, 0, c + hh, st) : B.linear(ctx, c - hh, 0, c + hh, 0, st);
      strip(c - hh, hh * 2);
    });
    ctx.globalCompositeOperation = "source-over";
    for (let i = 0; i < 18; i++) {
      ctx.fillStyle = B.rgba(i % 2 ? "#ffffff" : "#9fb4c8", 0.035 * lit);
      strip(a0 + (i / 18) * len, len / 36);
    }
    ctx.fillStyle = B.radial(ctx, box.x + box.w / 2, box.y + box.h / 2, Math.min(box.w, box.h) * 0.3, Math.hypot(box.w, box.h) * 0.6, [B.rgba("#2a3644", 0), B.rgba("#2a3644", 0.4)]);
    ctx.fillRect(box.x, box.y, box.w, box.h); ctx.strokeStyle = "#1b2027";
    ctx.lineWidth = 1.4 * U; ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.restore();
  }
  /** Chrome spring clip: a metallic block with a dark pivot. */
  function clip(ctx, x, y, s) {
    ctx.save();
    B.withShadow(ctx, { color: "rgba(0,0,0,0.5)", blur: s * 0.4, y: s * 0.15 }, () => {
      ctx.fillStyle = B.linear(ctx, x - s, y - s * 0.6, x + s, y + s * 0.6, ["#f4f7fa", "#8e98a3", "#d5dde4", "#5e6873"]);
      ctx.beginPath();
      B.roundRect(ctx, x - s, y - s * 0.7, s * 2, s * 1.4, s * 0.25);
      ctx.fill();
    });
    ctx.fillStyle = "#1a1d22"; ctx.beginPath(); B.circle(ctx, x, y - s * 0.15, s * 0.22);
    ctx.fill(); ctx.fillStyle = B.rgba("#ffffff", 0.6);
    ctx.fillRect(x - s * 0.8, y - s * 0.6, s * 1.6, s * 0.12);
    ctx.restore();
  }

  // ---- the two films
  /** Film A's arm, clear of the ID patch. */
  const mapA = (f, vertical) => (vertical ? armMapper({ ...f, h: f.h * 0.84 }, true, -0.08, 1.32, 0.27, 0.36) : armMapper(f, false, -0.08, 1.32, 0.27, 0.4));
  function filmA(fw, fh, vertical) {
    return filmLayer(`A:${vertical}`, fw, fh, (g, field) => {
      paintBase(g, field, 12); const M = mapA(field, vertical);
      paintTissue(g, M, -0.3, 1.6, 0.3);
      paintBone(g, M, ULNA, { seed: 4 });
      paintBone(g, M, RADIUS, { seed: 5, fracture: 0 });
      paintHand(g, M, 9); const ms = Math.min(field.w, field.h) * 0.07;
      leadMarker(g, "L", field.x + field.w - ms * 1.2, vertical ? field.y + field.h - ms * 1.2 : field.y + ms * 1.2, ms);
    });
  }
  function filmB(fw, fh, vertical) {
    return filmLayer(`B:${vertical}`, fw, fh, (g, field) => {
      panels(field, vertical).forEach((r, i) => {
        paintBase(g, r, 20 + i); const c = cropRect(r, !vertical);
        g.save(); g.beginPath(); g.rect(c.x, c.y, c.w, c.h);
        g.clip(); const M = cropMapper(r, !vertical);
        paintTissue(g, M, 0.3, 0.8, 0.18 + (i === 0 ? 0.08 : 0));
        paintBone(g, M, ULNA, { seed: 30 + i });
        paintBone(g, M, RADIUS, { seed: 40 + i, fracture: i });
        g.restore();
        const ms = Math.max(Math.min(r.w, r.h) * 0.12, 4.4 * U);
        leadMarker(g, String(i + 1), r.x + ms * 0.9, r.y + ms * 0.9, ms);
      });
    });
  }
  /** Film B's three exposures, divided by unexposed strips. */
  function panels(f, vertical) {
    const gap = Math.min(f.w, f.h) * 0.03;
    return [0, 1, 2].map((i) => (vertical ? { x: f.x, y: f.y + i * ((f.h + gap) / 3), w: f.w, h: (f.h - gap * 2) / 3 } : { x: f.x + i * ((f.w + gap) / 3), y: f.y, w: (f.w - gap * 2) / 3, h: f.h }));
  }
  /** The exposed field of a film at x, y. */
  function fieldOf(L, x, y) {
    const b = Math.round(Math.min(L.fw, L.fh) * 0.045);
    return { x: x + b, y: y + b, w: L.fw - 2 * b, h: L.fh - 2 * b };
  }

  // ---- layout and timing
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    const box = P ? { x: W * 0.04, y: H * 0.075, w: W * 0.92, h: H * 0.79 } : { x: W * 0.03, y: H * 0.05, w: W * 0.94, h: H * 0.9 };
    // portrait: tapes stay safe through the push-in
    const fw = Math.round(P ? W * 0.8 : W * 0.7), fh = Math.round(P ? H * 0.5 : H * 0.64);
    return { F, u, P, box, fw, fh, fx: W / 2, fy: P ? H * 0.225 : H * 0.19, tapeTop: P ? H * 0.19 : H * 0.115, tapeBottom: P ? H * 0.75 : H * 0.885, hand: P ? 4.6 * u : 4.4 * u, tapeSize: P ? 4.3 * u : 4.6 * u };
  }
  /** Film placement: slapped up with a bounce; tugged off and dropped. */
  function hang(t, inAt, outAt, H) {
    if (t < inAt) return null;
    const k = B.prog(t, inAt, 0.5), d = outAt == null ? -1 : t - outAt, f = Math.max(0, d - 0.12);
    let dy = -(1 - B.ease.outBounce(k)) * H * 0.9;
    if (d > 0) dy += d < 0.12 ? Math.sin((d / 0.12) * Math.PI) * 1.2 * U : 210 * U * f * f;
    return { dy, flex: 1 + 0.035 * Math.sin(k * Math.PI * 3) * (1 - k), rot: f * 0.6 };
  }

  // ---- the frame
  function draw(ctx, W, H, t) {
    const L = layout(W, H), u = L.u, P = L.P; U = u;
    ctx.fillStyle = PAL.room; ctx.fillRect(0, 0, W, H);
    const zoom = 1 + 0.06 * B.span(t, 0, DUR, "inOutSine"); // slow push-in
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(zoom, zoom); ctx.translate(-W / 2, -H / 2);
    // tubes flicker on one at a time
    const tubes = [0, 1, 2, 3].map((i) => {
      const k = t - 0.12 - i * 0.16;
      return k < 0 ? 0 : k > 0.3 ? 1 : B.hash01("tube", i, Math.floor(t * 30)) > 0.45 ? 0.9 : 0.1;
    });
    const lit = tubes.reduce((a, b) => a + b, 0) / 4;
    B.glow(ctx, W / 2, H / 2, Math.hypot(W, H) * 0.7, "#6d88a6", 0.22 * lit, { add: true });
    lightbox(ctx, L.box, tubes); const waxG = B.scratch("xray-wax", W, H);
    const ID = "ID 0417-B  L FOREARM", films = [
      { img: filmA(L.fw, L.fh, P), h: hang(t, 0.75, 5.95, H), dev: B.prog(t, 0.95, 0.8), rot: -0.012, id: [ID, "DAY 1   AP VIEW"], big: "EST. WEEKS: " + String(Math.min(6, Math.floor(B.prog(t, 4.25, 0.9) * 6 + 1e-6))).padStart(2, "0") },
      { img: filmB(L.fw, L.fh, P), h: hang(t, 6.35, null, H), dev: B.prog(t, 6.6, 0.75), rot: 0.01, id: [ID, "SERIES  DAY 2 / WK 3 / WK 6"] },
    ];
    films.forEach((f, i) => {
      if (!f.h || f.h.dy > H * 1.2) return; const x = L.fx - L.fw / 2, y = L.fy + f.h.dy;
      ctx.save(); ctx.translate(L.fx, y); ctx.rotate(f.rot + f.h.rot);
      ctx.scale(1, f.h.flex); ctx.translate(-L.fx, -y);
      B.withShadow(ctx, { color: "rgba(0,0,0,0.35)", blur: 1.2 * u, y: 0.4 * u }, () => ctx.drawImage(f.img, x, y));
      // develop: milky fog until a ragged front sweeps down
      if (f.dev < 1) {
        const front = y + f.dev * (L.fh + 6 * u) - 3 * u;
        ctx.save(); ctx.beginPath(); ctx.moveTo(x, y + L.fh);
        for (let xx = 0; xx <= L.fw; xx += 1.5 * u) ctx.lineTo(x + xx, front + B.noise1(xx / (3 * u), 7 + i) * 2.2 * u + B.noise1(xx / (0.8 * u), 9) * 0.6 * u);
        ctx.lineTo(x + L.fw, y + L.fh); ctx.closePath();
        ctx.clip(); ctx.fillStyle = "#a7b3bb"; ctx.fillRect(x, y, L.fw, L.fh);
        B.mottle(ctx, W, H, { amount: 0.3, feature: 0.08, seed: 31 + i, mode: "soft-light" });
        ctx.restore();
      }
      // grain (shows most in thin areas); dims with the tubes
      B.clip(ctx, () => ctx.rect(x, y, L.fw, L.fh), () => {
        B.grain(ctx, W, H, { amount: 0.07, t, fps: 24, mode: "lighter", seed: 3 + i });
        ctx.fillStyle = B.rgba("#000000", 0.65 * (1 - lit));
        ctx.fillRect(x, y, L.fw, L.fh);
      });
      const m = L.fw * 0.035, low = P || i === 1;
      idPatch(ctx, x + m, low ? y + L.fh - m : y + L.fh * 0.055, low, Math.max(9, (P ? 1.6 : 1.4) * u), f.id, f.big, (P ? 4.2 : 4) * u);
      [0.22, 0.78].forEach((cx) => clip(ctx, x + cx * L.fw, y + 0.4 * u, 2.4 * u));
      // annotations ride with the film
      waxG.setTransform(ctx.getTransform());
      (i ? annotateB : annotateA)(waxG, t, L, x, y, P);
      ctx.restore();
    });
    // lightbox bleed over the film edges
    ctx.save();
    Object.assign(ctx, { globalCompositeOperation: "screen", filter: `blur(${(1.6 * u).toFixed(1)}px)`, strokeStyle: B.rgba(PAL.glow, 0.55 * lit), lineWidth: 2.2 * u });
    ctx.strokeRect(L.fx - L.fw / 2, L.fy, L.fw, L.fh);
    ctx.restore();
    // grease pencil: waxy breakup, then onto the glass
    waxG.setTransform(1, 0, 0, 1, 0, 0);
    Object.assign(waxG, { globalCompositeOperation: "destination-out", fillStyle: waxG.createPattern(waxBreakup(), "repeat") });
    waxG.fillRect(0, 0, W, H);
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(waxG.canvas, 0, 0); ctx.restore();
    // tapes on the glass: the header, then the takeaway
    ctx.globalAlpha = 1 - B.span(t, 10.0, 10.25);
    tape(ctx, W / 2, L.tapeTop, "HOW A BROKEN BONE HEALS", L.tapeSize, B.prog(t, 1.25, 0.6), 5, { maxW: L.F.safe.w * 0.9 });
    ctx.globalAlpha = 1;
    tape(ctx, W / 2, L.tapeBottom, "BONE REBUILDS ITSELF", L.tapeSize * 1.05, B.prog(t, 10.4, 0.7), 8, { rot: 0.02, maxW: L.F.safe.w * 0.9 });
    ctx.restore();
    B.vignette(ctx, W, H, { amount: 0.4, inner: 0.55 });
  }
  /** Tile of tiny holes: the pencil skips on the glass. */
  function waxBreakup() {
    return B.layer("xray-wax-breakup", 128, 128, (g, w, h) => {
      const r = B.rng(77);
      for (let i = 0; i < 520; i++) {
        g.fillStyle = B.rgba("#000", r.range(0.25, 0.9));
        g.beginPath();
        g.ellipse(r() * w, r() * h, r.range(0.4, 1.4), r.range(0.3, 0.9), r() * 3, 0, B.TAU);
        g.fill();
      }
    });
  }

  // ---- annotations (grease pencil)
  function annotateA(g, t, L, x, y, vertical) {
    const u = L.u, field = fieldOf(L, x, y), M = mapA(field, vertical);
    const fade = 1 - B.span(t, 5.75, 5.95); if (fade <= 0) return;
    g.save(); g.globalAlpha = fade; const hs = L.hand, ww = 0.6 * u, Y = PAL.yellow;
    const rad = M.at(vertical ? 0.26 : 0.36, RADIUS.c(0.3) + RADIUS.w(0.3)), uln = M.at(vertical ? 0.1 : 0.12, ULNA.c(0.12));
    const zx = vertical ? field.x + field.w * 0.66 : 0, zy = vertical ? 0 : field.y + field.h * 0.84;
    // a label, its arrow curving to the bone point p
    const lab = (name, p, at, sd, d, e) => {
      const s0 = vertical ? [zx, p[1] - 3 * u] : [p[0] + d * u, zy - 3 * u], c = vertical ? [B.lerp(zx, p[0], 0.5), p[1] + d * u] : [p[0] + d * u, B.lerp(zy, p[1], 0.5)];
      waxArrow(g, B.quad(s0[0], s0[1], c[0], c[1], p[0] + (vertical ? u : 0), p[1] + e * u), B.prog(t, at, 0.45), Y, ww, sd);
      waxText(g, name, s0[0] + (vertical ? u : 0), s0[1] + 4.5 * u, hs, B.prog(t, at + 0.35, 0.45), Y, { align: vertical ? "left" : "" });
    };
    g.globalAlpha = fade * (vertical ? 1 : 1 - B.span(t, 4.0, 4.3));
    lab("RADIUS", rad, 2.0, 11, vertical ? -5 : 4, vertical ? 0 : 1);
    lab("ULNA", uln, 2.6, 12, vertical ? 6 : -3, 1);
    g.globalAlpha = fade;
    // wrong: red ring and slash on the break, labelled
    const br = M.at(BREAK_S, RADIUS.c(BREAK_S));
    waxRing(g, br[0], br[1], (vertical ? 9 : 6) * u, (vertical ? 6 : 8) * u, B.prog(t, 3.0, 0.45), PAL.red, ww * 1.15, 13);
    wax(g, [[br[0] - 4.5 * u, br[1] + 4.5 * u], [br[0] + 4.5 * u, br[1] - 4.5 * u]], B.prog(t, 3.45, 0.18), PAL.red, ww * 1.15, 14);
    const bk = vertical ? [zx + 2 * u, br[1] + 3 * u] : [br[0] + 7 * u, br[1] - 5.5 * u];
    waxText(g, "BREAK", bk[0], bk[1], hs * 1.05, B.prog(t, 3.55, 0.4), PAL.red, { align: "left" });
    if (vertical) wax(g, [[bk[0] - 0.5 * u, bk[1]], [br[0] + 8.5 * u, br[1] + 1.5 * u]], B.prog(t, 3.55, 0.15), PAL.red, ww, 17);
    // key number written big, two quick red rings
    const kx = vertical ? field.x + field.w * 0.77 : field.x + field.w * 0.45, ky = vertical ? field.y + field.h * 0.13 : field.y + field.h * 0.8;
    const big = hs * (vertical ? 2.2 : 2.7);
    let c, rx, ry; // the rings' centre and radii
    if (vertical) {
      waxText(g, "~6", kx, ky, big, B.prog(t, 4.5, 0.3), Y);
      rx = waxText(g, "WEEKS", kx, ky + big * 0.85, hs * 1.15, B.prog(t, 4.75, 0.35), Y) * 0.5 + 2 * u;
      waxText(g, "to heal", kx, ky + big * 0.85 + hs * 2.1, hs * 0.9, B.prog(t, 5.05, 0.3), Y);
      [c, ry] = [[kx, ky + big * 0.35], big * 0.95];
    } else {
      // rings round the number; WEEKS and "to heal" follow
      const x0 = kx - 25 * u, L = { align: "left" }, w6 = waxText(g, "~6", x0, ky, big, B.prog(t, 4.5, 0.25), Y, L), x1 = x0 + w6 + 4 * u;
      waxText(g, "to heal", x1 + waxText(g, "WEEKS", x1, ky, big, B.prog(t, 4.7, 0.4), Y, L) + 2 * u, ky + big * 0.15, hs * 0.85, B.prog(t, 5.05, 0.3), Y, L);
      [c, rx, ry] = [[x0 + w6 / 2, ky], w6 * 0.8, big * 0.62];
    }
    waxRing(g, c[0], c[1], rx, ry, B.prog(t, 5.15, 0.22), PAL.red, ww, 15, -0.1);
    waxRing(g, c[0] + 0.5 * u, c[1] + 0.3 * u, rx * 1.08, ry * 1.1, B.prog(t, 5.4, 0.22), PAL.red, ww * 0.8, 16, 0.15);
    g.restore();
  }
  function annotateB(g, t, L, x, y, vertical) {
    const u = L.u, rects = panels(fieldOf(L, x, y), vertical);
    const hs = L.hand, ww = 0.6 * u, Y = PAL.yellow;
    const steps = [["CLOT", "day 2"], ["SOFT CALLUS", "week 3"], ["HARD BONE", "week 6"]];
    rects.forEach((r, i) => {
      const at = 6.95 + i * 0.4;
      if (vertical) {
        const lx = r.x + r.w * 0.04 + 9 * u, ly = r.y + r.h * 0.13;
        const w0 = waxText(g, steps[i][0], lx, ly, hs, B.prog(t, at, 0.4), Y, { align: "left" });
        waxText(g, "(" + steps[i][1] + ")", lx + w0 + 2 * u, ly + hs * 0.05, hs * 0.85, B.prog(t, at + 0.25, 0.25), Y, { align: "left" });
      } else {
        const lx = r.x + r.w * 0.57, ly = r.y + r.h * 0.1;
        waxText(g, steps[i][0], lx, ly, hs * 0.95, B.prog(t, at, 0.4), Y);
        waxText(g, steps[i][1], lx, ly + hs * 1.2, hs * 0.85, B.prog(t, at + 0.25, 0.25), Y);
      }
      if (i < 2) {
        const r2 = rects[i + 1];
        const a = vertical ? [r.x + r.w * 0.92, r.y + r.h * 0.75] : [r.x + r.w * 0.88, r.y + r.h * 0.53];
        const b = vertical ? [r2.x + r2.w * 0.92, r2.y + r2.h * 0.25] : [r2.x + r2.w * 0.06, r2.y + r2.h * 0.53];
        const mid = vertical ? [a[0] + 5 * u, (a[1] + b[1]) / 2] : [(a[0] + b[0]) / 2, a[1] + 4 * u];
        waxArrow(g, B.quad(a[0], a[1], mid[0], mid[1], b[0], b[1]), B.prog(t, at + 0.3, 0.3), Y, ww * 0.9, 20 + i);
      }
    });
    const r3 = rects[2], M3 = cropMapper(r3, !vertical), c3 = M3.at(BREAK_S, RADIUS.c(BREAK_S));
    waxRing(g, c3[0], c3[1], (vertical ? 8 : 5) * u, (vertical ? 4.5 : 8) * u, B.prog(t, 8.55, 0.4), PAL.green, ww * 1.1, 31);
    // right: green ring, tick, HEALED
    const hz = hs * (vertical ? 1.1 : 0.95); g.font = B.font(hz, HAND, 700);
    const hw = g.measureText("HEALED").width, tk = vertical ? [Math.min(c3[0] + 12 * u, r3.x + r3.w - hw - 9 * u), c3[1] - 3 * u] : [r3.x + (r3.w - hw) / 2 - 4 * u, r3.y + r3.h * 0.89];
    wax(g, [[tk[0] - 2.5 * u, tk[1]], [tk[0], tk[1] + 2.5 * u], [tk[0] + 5 * u, tk[1] - 4 * u]], B.prog(t, 9.0, 0.25), PAL.green, ww * 1.3, 32);
    waxText(g, "HEALED", tk[0] + 6 * u, tk[1], hz, B.prog(t, 9.25, 0.45), PAL.green, { align: "left" });
  }

  // ---- sound: tube tinks, hum, wax, clips, film flex, tape, knocks
  SOUND.define("xray-tube", (v) => {
    v.tone({ f: 3100, a: 0.001, len: 0.12, peak: 0.08 });
    v.tone({ type: "sawtooth", f: 100, a: 0.005, hold: 0.12, len: 0.08, peak: 0.05 });
    v.noise({ filter: "bandpass", f: 2400, q: 3, a: 0.002, len: 0.04, peak: 0.08 });
  }, { verb: 0.25 });
  SOUND.define("xray-wax", (v, o) => {
    const d = o.dur ?? 0.4;
    v.grains({ span: d, count: Math.round(d * 70), filter: "bandpass", f: 1150, q: 1.4, len: 0.025, peak: 0.16 });
    v.noise({ filter: "bandpass", f: 700, q: 2, a: 0.02, hold: d * 0.85, len: 0.04, peak: 0.03 });
  }, { verb: 0.08 });
  SOUND.define("xray-clip", (v) => {
    v.tone({ f: 2350, a: 0.0005, len: 0.06, peak: 0.12 });
    v.tone({ f: 3720, a: 0.0005, len: 0.04, peak: 0.07 });
    v.noise({ filter: "highpass", f: 3000, a: 0.0005, len: 0.02, peak: 0.3 });
  }, { verb: 0.2 });
  SOUND.define("xray-flex", (v) => {
    v.tone({ type: "triangle", f: 120, fpath: [[0.06, 175], [0.12, 105], [0.18, 150], [0.26, 115], [0.36, 130]], a: 0.01, len: 0.38, peak: 0.12 });
    v.noise({ filter: "lowpass", f: 900, a: 0.01, len: 0.25, peak: 0.08 });
  }, { verb: 0.2 });
  SOUND.define("xray-tape", (v) => {
    v.grains({ span: 0.28, count: 30, filter: "highpass", f: 2600, len: 0.012, peak: 0.22 });
    v.noise({ at: 0.32, filter: "lowpass", f: 600, a: 0.002, len: 0.07, peak: 0.25 });
  }, { verb: 0.12 });

  function score(k) {
    [0.12, 0.28, 0.44, 0.6].forEach((at, i) => k.at(at, "xray-tube", { pitch: i * 0.7, pan: -0.45 + i * 0.3 }));
    k.bed("hum", 0.2, DUR, { gain: 0.9 });
    k.at(0.75, "xray-flex", { gain: 0.9 }).at(0.82, "xray-clip").at(0.9, "xray-clip", { pitch: 2 });
    k.at(1.2, "xray-tape", { gain: 0.9 });
    // each wax sound lasts as long as its stroke
    [[2.0, 0.34], [2.35, 0.5], [2.6, 0.34], [2.95, 0.4], [3.0, 0.45], [3.45, 0.18], [3.55, 0.4], [4.5, 0.6], [5.05, 0.35], [5.15, 0.22], [5.4, 0.22]].forEach(([at, d], i) => k.at(at, "xray-wax", { dur: d, pan: (i % 3) * 0.3 - 0.3 }));
    k.at(3.45, "knock", { gain: 0.8 });
    for (let i = 1; i <= 6; i++) k.at(4.25 + (i / 6) * 0.9 - 0.02, "type", { gain: 0.9 });
    k.at(5.35, "knock", { gain: 0.9, pitch: -2 });
    k.at(5.95, "xray-clip", { pitch: -2 }).at(6.0, "xray-flex", { pitch: -3 }).at(6.25, "thud", { gain: 0.35 });
    k.at(6.35, "xray-flex").at(6.42, "xray-clip").at(6.5, "xray-clip", { pitch: 1 });
    [[6.95, 0.4], [7.2, 0.25], [7.25, 0.3], [7.35, 0.4], [7.6, 0.25], [7.65, 0.3], [7.75, 0.4], [8.0, 0.25], [8.55, 0.4], [9.0, 0.25], [9.25, 0.45]].forEach(([at, d]) => k.at(at, "xray-wax", { dur: d }));
    k.at(9.0, "type", { gain: 0.8 }).at(9.05, "chime", { note: "E6", gain: 0.12 });
    k.at(10.4, "xray-tape", { gain: 1 });
  }

  Player.register({
    id: "xray-scan", name: "X-Ray Lightbox", duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;700&family=Kalam:wght@700&display=swap",
      faces: ['500 20px "IBM Plex Mono"', '700 20px "IBM Plex Mono"', '700 20px "Kalam"'],
    },
    beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three stages", "Healed", "Close"],
    stills: [1.85, 3.85, 5.7, 8.3, 9.9, 11.6],
    draw, score,
  });
})();
