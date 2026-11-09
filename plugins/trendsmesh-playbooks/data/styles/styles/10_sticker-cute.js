/* 10 Cute Sticker. Topic (replace it): "How does bread rise?" - yeast eats sugar, makes gas, the dough doubles.
 * Rendering (keep it): flat pastel kawaii; chunky rounded shapes with one plum outline round the whole object, one
 * cel-shade crescent and one white highlight; glossy big-eyed faces with blush; key items are die-cut stickers
 * (white border, soft plum shadow). Backdrop: flat pastel, drifting dot/star/heart pattern, soft clouds. Lettering:
 * rounded, white fill, pink-and-plum outline. No grain or gradients (only inside the eyes); twinkles blink.
 * Motion: on twos; pops overshoot with a squash-and-stretch wobble; letters hop on; heart and star iris wipes.
 */
(function () {
  "use strict"; const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { straw: "#ffd6e3", mint: "#bff0dc", butter: "#fff1a8", lav: "#d9c9ff", sky: "#bfe3ff", pink: "#ff6f9f",
    plum: "#5a3a5e", white: "#ffffff" };
  const LETTER = "Mochiy Pop One", BODY = "M PLUS Rounded 1c", DUR = 12, BEATS = [0, 1.9, 4.0, 6.1, 8.4, 10.3];
  const FPS = 12; // on twos

  let U = 1;
  const set = (c, o) => Object.assign(c, o);
  const oval = (c, x, y, rx, ry, fill, rot = 0) => { c.beginPath(); c.ellipse(x, y, rx, ry, rot, 0, B.TAU); c.fillStyle = fill; c.fill(); };
  const dot = (c, x, y, r, fill) => oval(c, x, y, r, r, fill);

  // ---- sticker helpers (reuse these)
  /** The one cel-shade tone: the same hue, a little deeper and pinker. */
  const shadeOf = (c) => B.mix(B.shade(c, -0.14), PAL.pink, 0.12);
  /**
   * The core of the look. One plum outline round the whole silhouette (pathFn may add overlapping sub-shapes: the
   * outline is stroked at double width, then the fill covers its inner half, so no seams show); the shape in the
   * shade tone with the base shifted up-left inside (a crescent at the bottom right); one white highlight oval.
   * bb = { x, y, w, h }. o: { sticker (white die-cut border + soft shadow), lw, hi (false), shade, shadeColor }
   */
  function cel(ctx, pathFn, bb, color, o = {}) {
    const lw = o.lw ?? 0.75 * U, m = Math.min(bb.w, bb.h), d = m * (o.shade ?? 0.1);
    const path = () => {
      ctx.beginPath(); pathFn(ctx);
    };
    ctx.save();
    ctx.lineJoin = ctx.lineCap = "round";
    if (o.sticker) {
      ctx.save();
      set(ctx, { shadowColor: B.rgba(PAL.plum, 0.28), shadowBlur: 1.4 * U, shadowOffsetY: 0.7 * U, strokeStyle: PAL.white, lineWidth: lw * 2 + 2.6 * U });
      path(); ctx.stroke(); ctx.restore();
    }
    path();
    set(ctx, { strokeStyle: PAL.plum, lineWidth: lw * 2, fillStyle: o.shadeColor || shadeOf(color) });
    ctx.stroke(); ctx.fill(); ctx.save();
    path(); ctx.clip(); ctx.translate(-d, -d);
    path(); ctx.fillStyle = color; ctx.fill();
    ctx.restore();
    if (o.hi !== false) oval(ctx, bb.x + bb.w * 0.27, bb.y + bb.h * 0.22, m * 0.09, m * 0.055, PAL.white, -0.6);
    ctx.restore();
  }
  /** Bouncy pop on twos: grows, overshoots, settles with a squash-and-stretch wobble. */
  function popS(t, at, dur = 0.6) {
    const k = B.prog(B.stepTime(t, FPS), at, dur);
    if (k <= 0) return null;
    const s = 1 - Math.exp(-6 * k) * Math.cos(11 * k), wob = 0.16 * Math.sin(13 * k) * Math.exp(-5 * k);
    return [s * (1 + wob), s * (1 - wob)];
  }
  /** Run fn scaled by a pop about an anchor (the bottom, so landings squash). */
  function popped(ctx, x, y, ps, fn) {
    if (!ps) return; ctx.save(); ctx.translate(x, y);
    ctx.scale(ps[0], ps[1]); ctx.translate(-x, -y);
    fn(); ctx.restore();
  }
  /** Big glossy eye (lid, shaded iris, pupil, two catchlights); mood: happy | spiral | sparkle | closed. */
  function eye(ctx, x, y, r, mood = "happy", t = 0) {
    ctx.save();
    if (mood === "closed") {
      set(ctx, { strokeStyle: PAL.plum, lineWidth: r * 0.28, lineCap: "round" });
      ctx.beginPath();
      ctx.arc(x, y + r * 0.2, r * 0.6, Math.PI * 1.15, Math.PI * 1.85);
      ctx.stroke(); ctx.restore(); return;
    }
    oval(ctx, x, y, r * 0.78, r, PAL.plum);
    if (mood === "spiral") {
      set(ctx, { strokeStyle: PAL.white, lineWidth: r * 0.14 });
      ctx.beginPath();
      for (let i = 0; i < 40; i++) {
        const a = i * 0.45 + t * 6, rr = (i / 40) * r * 0.7;
        ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
      }
      ctx.stroke();
    } else if (mood === "sparkle") {
      ctx.fillStyle = PAL.butter; ctx.beginPath();
      B.sparkle(ctx, x, y, r * 0.7, 0.3);
      ctx.fill();
      dot(ctx, x - r * 0.3, y - r * 0.45, r * 0.16, PAL.white);
    } else {
      // the iris: the one gradient this style allows
      oval(ctx, x, y + r * 0.1, r * 0.62, r * 0.82, B.linear(ctx, 0, y - r, 0, y + r, ["#3a2440", "#8a5aa0", "#d6a6e8"]));
      oval(ctx, x, y + r * 0.12, r * 0.36, r * 0.48, "#2a1730");
      dot(ctx, x - r * 0.28, y - r * 0.35, r * 0.24, PAL.white);
      dot(ctx, x + r * 0.25, y + r * 0.35, r * 0.11, PAL.white);
      set(ctx, { strokeStyle: PAL.plum, lineWidth: r * 0.22, lineCap: "round" }); // dark upper lid
      ctx.beginPath();
      ctx.ellipse(x, y, r * 0.8, r * 1.02, 0, Math.PI * 1.12, Math.PI * 1.88);
      ctx.stroke();
    }
    ctx.restore();
  }
  /** A face: two eyes, pink blush ovals, a tiny mouth ("smile" | "o" | "wobble"). */
  function face(ctx, x, y, s, mood = "happy", t = 0, mouth = "smile") {
    eye(ctx, x - s * 0.42, y, s * 0.24, mood, t);
    eye(ctx, x + s * 0.42, y, s * 0.24, mood, t);
    ctx.save();
    [-1, 1].forEach((d) => oval(ctx, x + d * s * 0.72, y + s * 0.3, s * 0.16, s * 0.09, B.rgba(PAL.pink, 0.55)));
    set(ctx, { strokeStyle: PAL.plum, lineWidth: s * 0.07, lineCap: "round" });
    if (mouth === "o") oval(ctx, x, y + s * 0.32, s * 0.08, s * 0.1, PAL.plum);
    else {
      ctx.beginPath();
      if (mouth === "wobble") for (let i = 0; i <= 4; i++) ctx.lineTo(x - s * 0.16 + i * s * 0.08, y + s * (i % 2 ? 0.29 : 0.34));
      else ctx.arc(x, y + s * 0.2, s * 0.12, 0.25 * Math.PI, 0.75 * Math.PI);
      ctx.stroke();
    }
    ctx.restore();
  }
  /** Lettering: white fill, pink outline inside a plum one, soft shadow; letters hop on one by one. */
  function letters(ctx, text, cx, cy, size, t, at, o = {}) {
    ctx.save();
    ctx.font = B.font(size, LETTER, 400);
    const ws = [...text].map((c) => (c === " " ? size * 0.42 : ctx.measureText(c).width + size * 0.07));
    const total = ws.reduce((a, b) => a + b, 0);
    let x = cx - total / 2; const tp = B.stepTime(t, FPS);
    [...text].forEach((c, i) => {
      const w = ws[i], start = at + i * (o.gap ?? 0.06);
      const ps = c === " " ? null : popS(t, start, 0.55);
      if (ps) {
        const hop = Math.sin(Math.PI * B.clamp((tp - start) / 0.3)) * size * 0.28;
        const bob = o.bob ? B.bob(tp, size * 0.04, 1.6, i * 0.13) : 0;
        const out = o.out != null ? popOut(t, o.out + i * 0.03) : 1;
        if (out > 0) {
          ctx.save();
          ctx.translate(x + w / 2, cy - hop + bob);
          ctx.scale(ps[0] * out, ps[1] * out);
          set(ctx, { textAlign: "center", textBaseline: "middle", lineJoin: "round", fillStyle: B.rgba(PAL.plum, 0.25) });
          ctx.fillText(c, 0, size * 0.1); // soft shadow below
          layered(ctx, c, size, [[PAL.plum, 0.3], [o.outline || [PAL.pink, PAL.pink, "#ff8fb6"][i % 3], 0.19]], o.fill || PAL.white);
          ctx.restore();
        }
      }
      x += w;
    });
    ctx.restore();
  }
  /** Outlined text: strokes [colour, width as a fraction of size] widest first, then the fill. */
  function layered(ctx, str, size, strokes, fill) {
    for (const [c, w] of strokes) {
      set(ctx, { strokeStyle: c, lineWidth: size * w });
      ctx.strokeText(str, 0, 0);
    }
    ctx.fillStyle = fill; ctx.fillText(str, 0, 0);
  }
  /** Quick shrink-out (things pop away rather than fade). */
  const popOut = (t, at) => 1 - B.ease.inBack(B.prog(B.stepTime(t, FPS), at, 0.3), 2);
  /** Sticker pill label; o.dot: a coloured dot. */
  function pill(ctx, x, y, text, size, ps, o = {}) {
    if (!ps) return; ctx.save();
    ctx.font = B.font(size, BODY, 800);
    const tw = ctx.measureText(text).width, dotW = o.dot ? size * 1.2 : 0, h = size * 2, w = tw + size * 1.7 + dotW;
    ctx.translate(x, y); ctx.scale(ps[0], ps[1]);
    cel(ctx, (c) => B.capsule(c, -w / 2, -h / 2, w, h), { x: -w / 2, y: -h / 2, w, h }, o.color || PAL.white, { sticker: true, shade: 0.12, hi: false, shadeColor: o.color ? undefined : "#f3e6f0" });
    if (o.dot) {
      dot(ctx, -w / 2 + size, 0, size * 0.32, o.dot);
      set(ctx, { strokeStyle: PAL.plum, lineWidth: size * 0.1 });
      ctx.stroke();
    }
    set(ctx, { fillStyle: PAL.plum, textAlign: "center", textBaseline: "middle" });
    ctx.fillText(text, dotW / 2, size * 0.05);
    ctx.restore();
  }
  /** Connector: candy dots appear one by one along a curve, then a chunky rounded arrowhead. */
  function candyArrow(ctx, pts, p, size, colors) {
    if (p <= 0) return;
    const L = B.pathLength(pts), n = Math.max(3, Math.floor(L / (size * 2.4)));
    const shown = Math.floor(p * (n + 1) + 1e-6);
    for (let i = 0; i < Math.min(shown, n); i++) {
      const [x, y] = B.pointAt(pts, (i + 0.3) / (n + 0.5));
      const r = size * 0.62;
      cel(ctx, (c) => B.circle(c, x, y, r), { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, colors[i % colors.length], { lw: size * 0.22, shade: 0.16 });
    }
    if (shown > n) {
      const [x, y, a] = B.pointAt(pts, 1), hl = size * 2.3;
      const tri = [[x, y], [x - Math.cos(a - 0.6) * hl, y - Math.sin(a - 0.6) * hl], [x - Math.cos(a + 0.6) * hl, y - Math.sin(a + 0.6) * hl]];
      cel(ctx, (c) => B.smoothPath(c, roundTri(tri, 0.22), true), { x: x - hl, y: y - hl, w: hl * 2, h: hl * 2 }, PAL.pink, { lw: size * 0.25, shade: 0.06 });
    }
  }
  /** Round off a triangle's corners (points for smoothPath). */
  function roundTri(tri, k) {
    const out = [];
    for (let i = 0; i < 3; i++) {
      const a = tri[i], b = tri[(i + 1) % 3];
      out.push([B.lerp(a[0], b[0], k), B.lerp(a[1], b[1], k)], [B.lerp(a[0], b[0], 1 - k), B.lerp(a[1], b[1], 1 - k)]);
    }
    return out;
  }
  /** Four-point twinkle that blinks on and off. */
  function twinkle(ctx, x, y, r, t, phase, color = PAL.white) {
    const k = Math.max(0, Math.sin(B.TAU * (B.stepTime(t, FPS) / 1.4 + phase)));
    if (k < 0.15) return; ctx.save();
    set(ctx, { fillStyle: color, strokeStyle: PAL.plum, lineWidth: r * 0.12 });
    ctx.beginPath();
    B.sparkle(ctx, x, y, r * k, 0.22);
    ctx.fill(); ctx.stroke(); ctx.restore();
  }
  /** Three little hearts floating up from x, y (sp apart), looping from t0. */
  function hearts(ctx, x, y, sp, t0, tp) {
    for (let i = 0; i < 3; i++) {
      const k = B.fract((tp - t0) / 1.15 + i / 3), hx = x + (i - 1) * sp, hy = y - k * 7.5 * U;
      ctx.globalAlpha = 1 - k * k;
      cel(ctx, (c) => heartPath(c, hx, hy, 1.7 * U), { x: hx - 2 * U, y: hy - 2 * U, w: 4 * U, h: 4 * U }, PAL.pink, { lw: 0.4 * U, hi: false });
    }
    ctx.globalAlpha = 1;
  }
  /** Small heart path. */
  function heartPath(c, x, y, s) {
    c.moveTo(x, y + s * 0.85);
    c.bezierCurveTo(x - s * 1.25, y + s * 0.05, x - s * 0.75, y - s * 0.95, x, y - s * 0.38);
    c.bezierCurveTo(x + s * 0.75, y - s * 0.95, x + s * 1.25, y + s * 0.05, x, y + s * 0.85);
    c.closePath();
  }
  /** Bubbly numeral that bounces whenever its value changes (at changedAt). */
  function numeral(ctx, str, x, y, size, t, changedAt, color = PAL.butter) {
    const k = B.stepTime(t, FPS) - changedAt;
    const b = k < 0 ? 1 : 1 + 0.28 * Math.exp(-6 * k) * Math.cos(16 * k);
    ctx.save(); ctx.translate(x, y);
    ctx.scale(b * (2 - Math.min(1.1, b) * 0.95 - 0.05), b);
    set(ctx, { font: B.font(size, LETTER, 400), textAlign: "center", textBaseline: "middle", lineJoin: "round", fillStyle: B.rgba(PAL.plum, 0.25) });
    ctx.fillText(str, 0, size * 0.08);
    layered(ctx, str, size, [[PAL.white, 0.3], [PAL.plum, 0.14]], color);
    oval(ctx, -size * 0.22, -size * 0.22, size * 0.06, size * 0.035, PAL.white, -0.6);
    ctx.restore();
  }

  // ---- backdrops and transitions
  /** Flat pastel, a drifting staggered pattern (dot, star, heart) and big soft clouds. */
  function backdrop(ctx, W, H, t, color, kind) {
    ctx.fillStyle = color; ctx.fillRect(0, 0, W, H);
    const tp = B.stepTime(t, FPS), gap = 9 * U, drift = (tp * 1.4 * U) % (gap * 2), tint = B.shade(color, -0.07);
    ctx.fillStyle = tint; ctx.beginPath();
    let row = 0;
    for (let y = -gap; y < H + gap; y += gap, row++) {
      for (let x = -gap * 2 + (row % 2 ? gap : 0); x < W + gap * 2; x += gap * 2) {
        const px = x + drift, py = y + drift * 0.5;
        if (kind === "star") B.star(ctx, px, py, 5, 1.3 * U, 0.6 * U);
        else if (kind === "heart") heartPath(ctx, px, py, 1.1 * U);
        else B.circle(ctx, px, py, 1.0 * U);
      }
    }
    ctx.fill(); ctx.save();
    ctx.fillStyle = B.rgba(PAL.white, 0.75);
    [[0.15, 0.13, 1], [0.85, 0.24, 0.8], [0.25, 0.9, 1.1], [0.9, 0.85, 0.9]].forEach(([fx, fy, s], i) => {
      const cx = fx * W + Math.sin(tp * 0.25 + i) * 2 * U, cy = fy * H, r = 7 * U * s;
      ctx.beginPath();
      B.circle(ctx, cx - r, cy + r * 0.2, r * 0.75);
      B.circle(ctx, cx, cy - r * 0.15, r);
      B.circle(ctx, cx + r * 1.0, cy + r * 0.15, r * 0.7);
      B.capsule(ctx, cx - r * 1.7, cy + r * 0.05, r * 3.4, r * 0.85);
      ctx.fill();
    });
    ctx.restore();
  }
  /** Heart or star iris wipe (p 0..1) with a candy border; drawInside paints the new scene inside. */
  function iris(ctx, W, H, p, cx, cy, shape, inner, drawInside) {
    if (p <= 0) return;
    const R = Math.hypot(W, H) * 1.25 * B.ease.inOutCubic(p);
    const path = (c) => {
      c.beginPath();
      if (shape === "heart") heartPath(c, cx, cy, R);
      else B.smoothPath(c, starPts(cx, cy, R), true);
    };
    ctx.save(); path(ctx); ctx.clip();
    drawInside(); ctx.restore(); if (p >= 1) return;
    ctx.save(); ctx.lineJoin = "round";
    path(ctx);
    [[PAL.plum, 7], [inner, 4.4], [PAL.white, 0.7]].forEach(([c, w]) => {
      set(ctx, { strokeStyle: c, lineWidth: w * U });
      ctx.stroke();
    });
    ctx.restore();
  }
  function starPts(cx, cy, R) {
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? R * 0.55 : R;
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
    return pts;
  }

  // ---- subjects (the setting: replace these)
  /** Yeast: a butter blob with a bud (yeast multiplies by budding) and a face. */
  function yeast(ctx, x, y, s, t, mood = "happy", mouth = "smile") {
    const bb = { x: x - s, y: y - s, w: s * 2.5, h: s * 2 };
    cel(ctx, (c) => {
      c.ellipse(x, y, s, s * 0.92, 0, 0, B.TAU);
      c.moveTo(x + s * 1.4, y - s * 0.55);
      c.arc(x + s * 1.0, y - s * 0.55, s * 0.4, 0, B.TAU);
    }, bb, PAL.butter, { sticker: true });
    face(ctx, x - s * 0.05, y + s * 0.05, s * 0.75, mood, t, mouth);
  }
  /** Sugar cube sticker. */
  function sugar(ctx, x, y, s) {
    cel(ctx, (c) => B.roundRect(c, x - s, y - s, s * 2, s * 2, s * 0.45), { x: x - s, y: y - s, w: s * 2, h: s * 2 }, "#fbf7ff", { sticker: true, shadeColor: PAL.lav });
    [[-0.4, -0.2], [0.3, 0.35], [0.35, -0.4], [-0.3, 0.45]].forEach(([a, b]) => dot(ctx, x + a * s, y + b * s, s * 0.09, B.rgba(PAL.lav, 0.9)));
  }
  /** Gas bubble. */
  function bubble(ctx, x, y, r) {
    cel(ctx, (c) => B.circle(c, x, y, r), { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, PAL.sky, { shade: 0.14, lw: Math.max(1, r * 0.09) });
  }
  /** Dough: a cream dome with a face, y = bottom; puff 0..1 makes it rounder and taller. */
  function dough(ctx, x, y, s, t, o = {}) {
    const puff = o.puff ?? 0, h = s * (0.75 + 0.45 * puff), w = s * (1.2 + 0.12 * puff);
    const bb = { x: x - w, y: y - h, w: w * 2, h };
    cel(ctx, (c) => {
      c.moveTo(x - w, y);
      c.bezierCurveTo(x - w * 1.05, y - h * 0.9, x - w * 0.45, y - h * 1.05, x, y - h);
      c.bezierCurveTo(x + w * 0.45, y - h * 1.05, x + w * 1.05, y - h * 0.9, x + w, y);
      c.closePath();
    }, bb, o.color || "#fff6dc", { sticker: !!o.sticker, shadeColor: o.shadeColor || "#f6d9a8" });
    face(ctx, x, y - h * 0.48, s * 0.42, o.mood || "happy", t, o.mouth || "smile");
    if (puff > 0.3) {
      const r = B.rng(o.seed ?? 3);
      for (let i = 0; i < 5; i++) {
        const bx = x + r.range(-0.7, 0.7) * w, by = y - r.range(0.12, 0.3) * h;
        ctx.beginPath();
        B.circle(ctx, bx, by, s * r.range(0.04, 0.07));
        ctx.strokeStyle = B.rgba(PAL.plum, 0.5);
        ctx.lineWidth = Math.max(1, s * 0.02);
        ctx.stroke();
      }
    }
  }
  /** Bowl with dough and a spoon (step 1). */
  function bowl(ctx, x, y, s, t) {
    cel(ctx, (c) => B.capsule(c, x + s * 0.2, y - s * 1.25, s * 0.22, s * 1.0), { x: x + s * 0.2, y: y - s * 1.25, w: s * 0.22, h: s }, PAL.sky);
    cel(ctx, (c) => c.ellipse(x, y - s * 0.32, s * 0.85, s * 0.35, 0, 0, B.TAU), { x: x - s * 0.85, y: y - s * 0.67, w: s * 1.7, h: s * 0.7 }, "#fff6dc", { shadeColor: "#f6d9a8" });
    cel(ctx, (c) => {
      c.moveTo(x - s * 1.05, y - s * 0.35);
      c.lineTo(x + s * 1.05, y - s * 0.35);
      c.bezierCurveTo(x + s * 1.0, y + s * 0.55, x - s * 1.0, y + s * 0.55, x - s * 1.05, y - s * 0.35);
      c.closePath();
    }, { x: x - s * 1.05, y: y - s * 0.35, w: s * 2.1, h: s * 0.8 }, PAL.lav);
  }
  /** Alarm clock (step 3). */
  function clock(ctx, x, y, s, t) {
    cel(ctx, (c) => {
      B.circle(c, x, y, s);
      B.circle(c, x - s * 0.7, y - s * 0.8, s * 0.32);
      B.circle(c, x + s * 0.7, y - s * 0.8, s * 0.32);
    }, { x: x - s, y: y - s * 1.1, w: s * 2, h: s * 2.1 }, PAL.butter);
    dot(ctx, x, y, s * 0.72, PAL.white);
    set(ctx, { strokeStyle: PAL.plum, lineWidth: s * 0.1, lineCap: "round" });
    const a = B.stepTime(t, FPS) * 1.5;
    ctx.beginPath(); ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(a) * s * 0.5, y + Math.sin(a) * s * 0.5);
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(-1.2) * s * 0.35, y + Math.sin(-1.2) * s * 0.35);
    ctx.stroke();
  }
  /** Loaf with score marks and a face. */
  function loaf(ctx, x, y, s, t, mood = "happy") {
    const bb = { x: x - s * 1.3, y: y - s * 1.15, w: s * 2.6, h: s * 1.15 };
    cel(ctx, (c) => {
      c.moveTo(x - s * 1.25, y);
      c.lineTo(x - s * 1.25, y - s * 0.6);
      c.bezierCurveTo(x - s * 1.3, y - s * 1.2, x + s * 1.3, y - s * 1.2, x + s * 1.25, y - s * 0.6);
      c.lineTo(x + s * 1.25, y); c.closePath();
    }, bb, "#ffd98a", { sticker: true, shadeColor: "#f2b06a" });
    ctx.save();
    set(ctx, { strokeStyle: B.rgba(PAL.plum, 0.6), lineWidth: s * 0.06, lineCap: "round" });
    [-0.6, 0, 0.6].forEach((d) => {
      ctx.beginPath();
      ctx.moveTo(x + d * s - s * 0.15, y - s * 0.98);
      ctx.lineTo(x + d * s + s * 0.15, y - s * 0.85);
      ctx.stroke();
    });
    ctx.restore();
    face(ctx, x, y - s * 0.42, s * 0.45, mood, t);
  }
  /** Big rounded X stamp (wrong). */
  function xStamp(ctx, x, y, s, t, at) {
    const k = B.prog(B.stepTime(t, FPS), at, 0.35), sc = k < 0.5 ? B.lerp(1.8, 0.85, k / 0.5) : B.lerp(0.85, 1, (k - 0.5) / 0.5);
    if (k <= 0) return; ctx.save(); ctx.translate(x, y);
    ctx.rotate(-0.12);
    ctx.scale(sc * (k < 0.6 ? 1.1 : 1), sc * (k < 0.6 ? 0.9 : 1));
    cel(ctx, (c) => {
      c.save(); c.rotate(Math.PI / 4);
      B.capsule(c, -s, -s * 0.24, s * 2, s * 0.48);
      B.capsule(c, -s * 0.24, -s, s * 0.48, s * 2);
      c.restore();
    }, { x: -s * 0.8, y: -s * 0.8, w: s * 1.6, h: s * 1.6 }, PAL.pink, { sticker: true, shade: 0.06 });
    ctx.restore();
  }

  // ---- layout
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    return { F, u, P, S, head: P ? 8.6 * u : 7.8 * u, label: P ? 4.4 * u : 4.2 * u };
  }

  // ---- scene A: title, diagram, key number (pink, dots)
  function sceneA(ctx, W, H, t, L) {
    const u = L.u, P = L.P, S = L.S, tp = B.stepTime(t, FPS);
    backdrop(ctx, W, H, t, PAL.straw, "dot");
    if (t < 2.2) {
      if (P) {
        letters(ctx, "How bread", W / 2, H * 0.3, L.head * 1.15, t, 0.15, { out: 1.75, bob: true });
        letters(ctx, "rises!", W / 2, H * 0.3 + L.head * 1.4, L.head * 1.15, t, 0.7, { out: 1.8, bob: true });
      } else letters(ctx, "How bread rises!", W / 2, H * 0.28, L.head * 1.15, t, 0.15, { out: 1.75, bob: true, gap: 0.05 });
      const ps = popS(t, 0.9);
      const ly = P ? H * 0.74 : H * 0.84, ls = (P ? 30 : 25) * u;
      const out = popOut(t, 1.8);
      if (ps && out > 0) popped(ctx, W / 2, ly, [ps[0] * out, ps[1] * out], () => loaf(ctx, W / 2, ly + B.bob(tp, u * 0.8, 1.2), ls, t));
    }
    // diagram
    const out = popOut(t, 3.95);
    if (t >= 1.9 && out > 0) B.zoomAt(ctx, W / 2, H / 2, out, () => {
      letters(ctx, "Yeast eats sugar", W / 2, P ? S.y + L.head * 0.9 : S.y + L.head * 0.7, L.head * 0.8, t, 1.95, { gap: 0.04 });
      const sg = P ? [W * 0.22, H * 0.29] : [W * 0.15, H * 0.5], ys = P ? [W * 0.4, H * 0.45] : [W * 0.4, H * 0.52], bs = P ? [W * 0.72, H * 0.65] : [W * 0.78, H * 0.44];
      const ss = (P ? 8 : 6.5) * u, yS = (P ? 15 : 12) * u;
      popped(ctx, sg[0], sg[1], popS(t, 2.2), () => sugar(ctx, sg[0], sg[1] + B.bob(tp, u * 0.4, 1.3), ss));
      pill(ctx, sg[0] + (P ? ss + 17 * u : 0), P ? sg[1] : sg[1] + ss + L.label * 1.7, "sugar", L.label, popS(t, 2.4), { dot: PAL.lav });
      popped(ctx, ys[0], ys[1] + yS, popS(t, 2.35), () => yeast(ctx, ys[0], ys[1] + B.bob(tp, u * 0.6, 1.0, 0.3), yS, t, "happy", tp > 2.8 && tp < 3.2 ? "o" : "smile"));
      pill(ctx, ys[0] - yS * 0.45, ys[1] + yS + L.label * 1.8, "yeast", L.label, popS(t, 2.55), { dot: PAL.butter });
      const a0 = P ? [ys[0] + yS * 0.95, ys[1] + yS * 0.55] : [ys[0] + yS * 1.6, ys[1] + yS * 0.1];
      const a1 = P ? [bs[0] - 11 * u, bs[1] - 10 * u] : [bs[0] - 12 * u, bs[1] + 1 * u];
      const pts = B.quad(a0[0], a0[1], P ? a0[0] + 2 * u : (a0[0] + a1[0]) / 2, P ? (a0[1] + a1[1]) / 2 + 6 * u : a0[1] - 9 * u, a1[0], a1[1]);
      candyArrow(ctx, pts, B.prog(tp, 2.9, 0.6), 1.9 * u, [PAL.pink, PAL.sky, PAL.butter, PAL.mint, PAL.lav]);
      [[0, 0, 4.2], [6.5, -6.5, 2.8], [-5, -9.5, 2.2], [4.5, 6.5, 2.4]].forEach(([dx, dy, r], i) => {
        const ps = popS(t, 3.35 + i * 0.08);
        const bx = bs[0] + dx * u, by = bs[1] + dy * u + B.bob(tp, u * 0.7, 1.4, i * 0.2) - Math.max(0, tp - 3.4) * u * 1.5;
        popped(ctx, bx, by, ps, () => bubble(ctx, bx, by, r * u * (P ? 1.5 : 1.3)));
      });
      pill(ctx, bs[0], bs[1] + (P ? 21 : 19) * u, "gas bubbles", L.label, popS(t, 3.55), { dot: PAL.sky });
    });
    // key number: the dough doubles; the numeral bounces on each change
    if (t >= 4.0) {
      // portrait: number, pill and a big dough fill the column
      const dp = P ? [W * 0.5, H * 0.77] : [W * 0.34, H * 0.84], ds = (P ? 24 : 14) * u;
      const grow = tp < 4.7 ? 0 : tp < 5.2 ? 0.5 : 1;
      popped(ctx, dp[0], dp[1], popS(t, 4.05), () => dough(ctx, dp[0], dp[1], ds * (1 + 0.35 * grow), t, { puff: grow, sticker: true, seed: 5, mood: grow >= 1 ? "sparkle" : "happy" }));
      const np = P ? [W * 0.5, H * 0.3] : [W * 0.7, H * 0.42];
      const val = tp < 4.7 ? "1x" : tp < 5.2 ? "1.5x" : "2x";
      const changed = tp < 4.7 ? 4.25 : tp < 5.2 ? 4.7 : 5.2;
      const ps = popS(t, 4.25);
      if (ps) numeral(ctx, val, np[0], np[1], (P ? 26 : 17) * u, t, changed, val === "2x" ? PAL.pink : PAL.butter);
      pill(ctx, np[0], np[1] + (P ? 26 : 17) * u, "bigger in 1 to 2 hours", L.label, popS(t, 4.5), { dot: PAL.pink });
      if (tp > 5.3) hearts(ctx, dp[0], dp[1] - ds * 1.6, ds * 0.8, 5.3, tp);
    }
    [[0.08, 0.17, 0], [0.92, 0.4, 0.3], [0.1, 0.78, 0.6], [0.88, 0.72, 0.15]].forEach(([fx, fy, ph]) => twinkle(ctx, fx * W, fy * H, 2.2 * u, t, ph));
  }

  // ---- scene B: three steps, then too cold vs just warm (stars)
  function sceneB(ctx, W, H, t, L) {
    const u = L.u, P = L.P, S = L.S, tp = B.stepTime(t, FPS);
    backdrop(ctx, W, H, t, PAL.straw, "star");
    if (t < 8.7) {
      letters(ctx, "3 easy steps", W / 2, P ? S.y + L.head * 0.8 : S.y + L.head * 0.6, L.head * 0.85, t, 6.35, { gap: 0.04, out: 8.3 });
      const cards = P ? [[W * 0.5, H * 0.33], [W * 0.5, H * 0.52], [W * 0.5, H * 0.71]] : [[W * 0.2, H * 0.52], [W * 0.5, H * 0.52], [W * 0.8, H * 0.52]];
      const cw = P ? W * 0.72 : W * 0.22, ch = P ? H * 0.12 : H * 0.4;
      const names = ["Mix", "Knead", "Rest warm"];
      cards.forEach(([cx, cy], i) => {
        const at = 6.45 + i * 0.3, out = popOut(t, 8.3 + i * 0.04);
        const ps = popS(t, at); if (!ps || out <= 0) return;
        popped(ctx, cx, cy + ch / 2, [ps[0] * out, ps[1] * out], () => {
          cel(ctx, (c) => B.roundRect(c, cx - cw / 2, cy - ch / 2, cw, ch, 4 * u), { x: cx - cw / 2, y: cy - ch / 2, w: cw, h: ch }, PAL.white, { sticker: true, shade: 0.04, shadeColor: "#f2e6ef", hi: false });
          const ix = P ? cx - cw * 0.27 : cx, iy = P ? cy + 2 * u : cy - ch * 0.08, is = (P ? 8 : 7) * u;
          const bobY = B.bob(tp, u * 0.4, 1.1, i * 0.3);
          if (i === 0) bowl(ctx, ix, iy + bobY, is, t);
          else if (i === 1) {
            const squish = Math.sin(tp * 9) * 0.12;
            ctx.save();
            ctx.translate(ix, iy + is * 0.6);
            ctx.scale(1 + squish, 1 - squish);
            dough(ctx, 0, 0, is * 0.95, t, { mood: "closed", seed: 8 });
            ctx.restore();
            set(ctx, { strokeStyle: PAL.plum, lineWidth: 0.5 * u, lineCap: "round" }); // motion lines
            [-1, 1].forEach((d) => {
              ctx.beginPath();
              B.poly(ctx, [[ix + d * is * 1.5, iy - is * 0.2], [ix + d * is * 1.85, iy - is * 0.35]]);
              B.poly(ctx, [[ix + d * is * 1.55, iy + is * 0.2], [ix + d * is * 1.95, iy + is * 0.2]]);
              ctx.stroke();
            });
          } else clock(ctx, ix, iy + bobY, is * 0.85, t);
          const br = (P ? 3.8 : 3.3) * u, bx = cx - cw / 2 + br * 1.4, by = cy - ch / 2 + br * 1.4;
          cel(ctx, (c) => B.circle(c, bx, by, br), { x: bx - br, y: by - br, w: br * 2, h: br * 2 }, PAL.pink, { lw: 0.45 * u, hi: false });
          set(ctx, { font: B.font(br * 1.3, LETTER, 400), fillStyle: PAL.white, textAlign: "center", textBaseline: "middle" });
          ctx.fillText(String(i + 1), bx, by + br * 0.08);
          set(ctx, { font: B.font(L.label * (P ? 1.4 : 1.25), BODY, 800), fillStyle: PAL.plum });
          ctx.fillText(names[i], P ? cx + cw * 0.16 : cx, P ? cy : cy + ch * 0.33);
        });
      });
      // candy-dot connectors over the gaps
      for (let i = 0; i < 2 && popOut(t, 8.3) > 0.9; i++) {
        const [cx, cy] = cards[i], [nx, ny] = cards[i + 1];
        const pts = P ? B.quad(cx, cy + ch / 2 + 1.5 * u, cx + 5 * u, (cy + ny) / 2, nx, ny - ch / 2 - 1.5 * u) : B.quad(cx + cw / 2 + 1.5 * u, cy, (cx + nx) / 2, cy - 5 * u, nx - cw / 2 - 1.5 * u, ny);
        candyArrow(ctx, pts, B.prog(tp, 6.75 + i * 0.3, 0.35), 1.5 * u, [PAL.pink, PAL.butter, PAL.sky]);
      }
    }
    // wrong: X stamp, spiral eyes, sweat, ?!; right: sparkle eyes, hearts, confetti, punch-in
    if (t >= 8.4) {
      const punch = B.prog(tp, 9.3, 0.25) * (1 - B.prog(tp, 9.9, 0.4));
      const [sx, sy] = B.shake(tp, punch * 0.8 * u, 4, 18);
      ctx.save();
      ctx.translate(W / 2 + sx, H / 2 + sy);
      ctx.scale(1 + 0.06 * punch, 1 + 0.06 * punch);
      ctx.translate(-W / 2, -H / 2);
      letters(ctx, "Keep it warm", W / 2, P ? S.y + L.head * 0.9 : S.y + L.head * 0.6, L.head * 0.85, t, 8.45, { gap: 0.04 });
      const L0 = P ? [W * 0.5, H * 0.44] : [W * 0.28, H * 0.72], R0 = P ? [W * 0.5, H * 0.74] : [W * 0.72, H * 0.72], ds = (P ? 16 : 12) * u;
      popped(ctx, L0[0], L0[1], popS(t, 8.45), () => dough(ctx, L0[0], L0[1], ds * 1.3, t, { puff: -0.2, mood: tp > 8.85 ? "spiral" : "happy", mouth: tp > 8.85 ? "wobble" : "smile", color: "#f3f7ff", shadeColor: "#cfdcf2" }));
      pill(ctx, L0[0], L0[1] - ds * 1.25 - (P ? 1 : 2) * u, "too cold", L.label, popS(t, 8.55), { dot: PAL.sky });
      if (tp > 8.85) {
        const sw = [L0[0] + ds * 1.0, L0[1] - ds * 0.85 + ((tp - 8.85) % 0.6) * 4 * u];
        cel(ctx, (c) => {
          c.moveTo(sw[0], sw[1] - 2 * u);
          c.quadraticCurveTo(sw[0] + 1.4 * u, sw[1] + 0.2 * u, sw[0], sw[1] + 1.2 * u);
          c.quadraticCurveTo(sw[0] - 1.4 * u, sw[1] + 0.2 * u, sw[0], sw[1] - 2 * u);
        }, { x: sw[0] - 1.4 * u, y: sw[1] - 2 * u, w: 2.8 * u, h: 3.2 * u }, PAL.sky, { lw: 0.35 * u });
        letters(ctx, "?!", L0[0] - ds * 1.95, L0[1] - ds * 0.45, 6.5 * u, t, 8.95, { outline: PAL.sky });
      }
      xStamp(ctx, L0[0] + ds * 0.95, L0[1] - ds * 0.35, 6 * u, t, 8.85);
      popped(ctx, R0[0], R0[1], popS(t, 8.65), () => dough(ctx, R0[0], R0[1], ds * (1 + 0.3 * B.prog(tp, 9.2, 0.3)), t, { puff: tp > 9.2 ? 1 : 0.2, mood: tp > 9.25 ? "sparkle" : "happy", sticker: true, seed: 9 }));
      pill(ctx, R0[0], R0[1] + 3.5 * u, "just warm", L.label, popS(t, 8.75), { dot: PAL.pink });
      if (tp > 9.25) {
        const r = B.rng("confetti");
        for (let i = 0; i < 22; i++) {
          const k = B.clamp((tp - 9.25) / 1.0), a = r.range(-2.6, -0.5), sp = r.range(10, 22) * u;
          const cx = R0[0] + Math.cos(a) * sp * k, cy = R0[1] - ds * 1.4 + Math.sin(a) * sp * k + 14 * u * k * k;
          ctx.save(); ctx.translate(cx, cy);
          ctx.rotate(r() * 6 + tp * 4);
          set(ctx, { fillStyle: [PAL.pink, PAL.butter, PAL.sky, PAL.lav][i % 4], strokeStyle: PAL.plum, lineWidth: 0.25 * u });
          ctx.beginPath();
          B.roundRect(ctx, -0.7 * u, -0.4 * u, 1.4 * u, 0.8 * u, 0.3 * u);
          ctx.fill(); ctx.stroke(); ctx.restore();
        }
        hearts(ctx, R0[0], R0[1] - ds * 1.7, ds * 0.9, 9.25, tp);
      }
      ctx.restore();
    }
    [[0.07, 0.2, 0.2], [0.93, 0.18, 0.5], [0.08, 0.88, 0.8], [0.92, 0.9, 0.1]].forEach(([fx, fy, ph]) => twinkle(ctx, fx * W, fy * H, 2.2 * u, t, ph, PAL.butter));
  }

  // ---- scene C: close (hearts)
  function sceneC(ctx, W, H, t, L) {
    const u = L.u, P = L.P, S = L.S, tp = B.stepTime(t, FPS);
    backdrop(ctx, W, H, t, PAL.straw, "heart");
    const ls = (P ? 30 : 23) * u, ly = P ? H * 0.76 : H * 0.86;
    popped(ctx, W / 2, ly, popS(t, 10.55), () => loaf(ctx, W / 2, ly + B.bob(tp, u * 0.7, 1.1), ls, t, tp > 11.3 ? "sparkle" : "happy"));
    if (P) {
      letters(ctx, "Yeast + time", W / 2, H * 0.27, L.head, t, 10.45, { gap: 0.035, bob: true });
      letters(ctx, "= fluffy", W / 2, H * 0.27 + L.head * 1.5, L.head, t, 10.7, { gap: 0.035, bob: true });
      letters(ctx, "bread!", W / 2, H * 0.27 + L.head * 3.1, L.head * 1.25, t, 10.95, { gap: 0.04, bob: true });
    } else {
      letters(ctx, "Yeast + time =", W / 2, H * 0.25, L.head * 0.95, t, 10.5, { gap: 0.035, bob: true });
      letters(ctx, "fluffy bread!", W / 2, H * 0.25 + L.head * 1.35, L.head * 1.05, t, 10.95, { gap: 0.035, bob: true });
    }
    [[0.1, 0.16, 0], [0.9, 0.2, 0.4], [0.12, 0.62, 0.7], [0.88, 0.58, 0.2]].forEach(([fx, fy, ph]) => twinkle(ctx, fx * W, fy * H, 2.6 * u, t, ph));
  }

  // ---- the frame
  function draw(ctx, W, H, t) {
    const L = layout(W, H), tp = B.stepTime(t, FPS);
    U = L.u;
    if (t < 6.1) sceneA(ctx, W, H, t, L);
    else if (t < 10.3) sceneB(ctx, W, H, t, L);
    else sceneC(ctx, W, H, t, L);
    // heart iris into the steps, star iris into the close
    const p1 = B.prog(tp, 5.75, 0.5);
    if (t < 6.1 && p1 > 0) iris(ctx, W, H, p1, W / 2, H * 0.5, "heart", PAL.pink, () => sceneB(ctx, W, H, 6.1, L));
    const p2 = B.prog(tp, 9.95, 0.5);
    if (t >= 6.1 && t < 10.3 && p2 > 0) iris(ctx, W, H, p2, W / 2, H * 0.55, "star", PAL.butter, () => sceneC(ctx, W, H, 10.3, L));
  }

  // ---- sound: boings, pops, chimes; rising arpeggio (right), falling slide (wrong)
  SOUND.define("cute-boing", (v) => {
    v.tone({ f: 330, fpath: [[0.04, 250], [0.1, 420], [0.18, 360], [0.26, 390]], a: 0.004, len: 0.3, peak: 0.2 });
  }, { verb: 0.2 });
  SOUND.define("cute-pop", (v) => {
    v.tone({ f: 520, f2: 1100, glide: 0.05, a: 0.002, len: 0.07, peak: 0.2 });
  }, { verb: 0.25 });
  SOUND.define("cute-squeak", (v) => {
    const bp = v.ac.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1400 * v.rate;
    bp.Q.value = 3; bp.connect(v.out);
    v.tone({ type: "sawtooth", f: 700, fpath: [[0.08, 1150], [0.2, 820]], a: 0.01, len: 0.24, peak: 0.18, dest: bp });
    v.noise({ filter: "lowpass", f: 400, a: 0.002, len: 0.08, peak: 0.25 });
  }, { verb: 0.15 });

  function score(k) {
    const POP = "cute-pop", BOING = "cute-boing";
    k.bed("arp", 0, DUR, { notes: SOUND.scale("F4", "pent", 8), step: 0.2, gain: 0.3, pattern: [0, 2, 4, 5, 4, 2, 3, 1] });
    for (let i = 0; i < 9; i++) k.at(0.15 + i * 0.06, POP, { pitch: (i % 5) * 2, gain: 0.55, pan: -0.5 + i * 0.12 });
    k.at(0.7, POP, { pitch: 4 }).at(0.9, BOING, { gain: 0.9 }).at(1.0, "sparkle", { gain: 0.25 });
    k.at(1.75, "swish", { dur: 0.25, gain: 0.5 });
    k.repeat(1.95, 0.04, 8, POP, { gain: 0.35, vary: 3 });
    k.at(2.2, BOING, { pitch: 3 }).at(2.35, BOING).at(2.4, POP, { pitch: 5 }).at(2.55, POP, { pitch: 7 });
    k.at(2.85, POP, { pitch: -3, gain: 0.5 }); // munch
    k.repeat(2.9, 0.08, 7, "bubble", { gain: 0.3, vary: 4 });
    [3.35, 3.43, 3.51, 3.59].forEach((at, i) => k.at(at, "bubble", { pitch: i * 2, gain: 0.5 }));
    k.at(3.55, POP, { pitch: 2 }).at(3.95, "swish", { dur: 0.2, gain: 0.4 });
    k.at(4.05, BOING, { pitch: -2 }).at(4.25, POP, { pitch: 0 });
    k.at(4.7, BOING, { pitch: 2 }).at(4.7, POP, { pitch: 3 });
    k.at(5.2, BOING, { pitch: 5 }).at(5.2, "chime", { note: "C7", gain: 0.3 }).at(5.25, "sparkle", { gain: 0.3 });
    k.at(5.35, POP, { pitch: 5 });
    k.at(5.75, "swish", { dur: 0.5, gain: 0.6 }).at(6.2, POP, { pitch: 7 });
    k.repeat(6.35, 0.04, 8, POP, { gain: 0.3, vary: 3 });
    [6.55, 7.0, 7.45].forEach((at, i) => k.at(at, BOING, { pitch: i * 3 }).at(at + 0.3, POP, { pitch: 4 + i * 3, gain: 0.5 }));
    k.at(8.3, "swish", { dur: 0.25, gain: 0.4 });
    k.at(8.45, BOING, { pitch: -4 }).at(8.65, BOING, { pitch: 1 });
    k.at(8.85, "cute-squeak", { gain: 0.9 }).at(8.85, "fall", { dur: 0.5, gain: 0.25 });
    k.seq(9.25, 0.07, ["F5", "A5", "C6", "F6"], { voice: "pluck", gain: 0.45 });
    k.at(9.3, "sparkle", { gain: 0.35 }).at(9.35, "chime", { note: "A6", gain: 0.25 });
    k.at(9.95, "swish", { dur: 0.5, gain: 0.6 });
    k.at(10.55, BOING, { gain: 0.9 });
    for (let i = 0; i < 12; i++) k.at(10.6 + i * 0.05, POP, { pitch: (i % 6) * 2, gain: 0.35 });
    k.at(11.3, "sparkle", { gain: 0.35 }).at(11.35, "chord", { notes: ["F5", "A5", "C6"], gain: 0.4 });
  }

  Player.register({
    id: "sticker-cute", name: "Cute Sticker", duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Mochiy+Pop+One&family=M+PLUS+Rounded+1c:wght@800&display=swap",
      faces: ['400 20px "Mochiy Pop One"', '800 20px "M PLUS Rounded 1c"'],
    },
    beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Three steps", "Cold vs warm", "Close"],
    stills: [1.35, 3.8, 5.6, 8.1, 9.8, 11.7],
    draw, score,
  });
})();
