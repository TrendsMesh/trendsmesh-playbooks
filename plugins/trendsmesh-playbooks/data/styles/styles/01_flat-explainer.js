/* 01 Flat Vector Explainer - reference animation.
 * Topic (setting, replace it): "Where does rain come from?" - the water cycle.
 * Rendering (keep it): outline-free round shapes with diagonal gradients lit from the upper left, hard crescent
 * shading and a pale rim, white label pills, heavy rounded headings with a short offset shadow, twinkling sparkles,
 * soft breathing glows, overlay grain + static mottle, pop-in overshoot, camera push/pull with parallax,
 * a big-disc wipe and a dive-into-glow whiteout between scenes.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    deep: "#1a1f4e", // backdrop deep
    light: "#4b3a8f", // backdrop light
    teal: "#37c4d6",
    orange: "#ff9445",
    yellow: "#ffd447",
    pink: "#ff4f6d",
    green: "#3ddc91",
    white: "#fbfbff",
  };
  const HEAD = "Baloo 2", BODY = "Nunito Sans";
  const DUR = 12;
  const BEATS = [0, 1.9, 4.0, 6.1, 8.4, 10.3];

  // ------------------------------------------------------------------ flat-vector helpers (reuse these)
  /** Tones for one hue: a light tint for the lit side, deeper shades for the crescents, a pale rim. */
  function tones(hex) {
    return { light: B.shade(hex, 0.38), base: hex, base2: B.shade(hex, -0.1), shade: B.shade(hex, -0.24), deep: B.shade(hex, -0.42), rim: B.shade(hex, 0.7) };
  }
  /**
   * The core of the look: fill a shape with no outline, a diagonal gradient (light from the upper left),
   * two hard-edged crescents of darker tone hugging the lower-right edge and a thin pale crescent rim on the lit edge.
   * The crescents come from filling the same shape shifted diagonally inside nested clips, so they always hug
   * the silhouette, whatever it is (circles, clouds, waves). pathFn(ctx) adds the shape; bb = { x, y, w, h }.
   */
  function flatFill(ctx, pathFn, bb, tone, o = {}) {
    const m = Math.min(bb.w, bb.h);
    const sh = (o.shade ?? 0.11) * m, dp = (o.deep ?? 0.035) * m, rim = (o.rim ?? 0.03) * m;
    const big = [bb.x - m, bb.y - m, bb.w + 2 * m, bb.h + 2 * m];
    const shifted = (dx, dy) => {
      ctx.beginPath();
      ctx.save();
      ctx.translate(dx, dy);
      pathFn(ctx);
      ctx.restore();
    };
    ctx.save();
    ctx.beginPath();
    pathFn(ctx);
    ctx.clip();
    ctx.fillStyle = tone.rim; // pale rim = the shape minus itself moved down-right
    ctx.fillRect(...big);
    shifted(rim, rim);
    ctx.clip();
    ctx.fillStyle = tone.deep; // deepest crescent at the very edge
    ctx.fillRect(...big);
    shifted(-dp, -dp);
    ctx.fillStyle = tone.shade;
    ctx.fill();
    shifted(-sh, -sh); // the body covers all but the crescents
    ctx.fillStyle = B.linear(ctx, bb.x, bb.y, bb.x + bb.w, bb.y + bb.h, [tone.light, tone.base, tone.base2]);
    ctx.fill();
    ctx.restore();
  }
  /** Heavy rounded heading in white with a short dark offset shadow down-right. */
  function heading(ctx, text, x, y, size, o = {}) {
    return B.text(ctx, text, x, y, {
      size, family: HEAD, weight: 800, color: o.color || PAL.white, maxW: o.maxW, maxLines: o.maxLines ?? 2, lineH: 1.02,
      shadow: { x: size * 0.045, y: size * 0.06, color: B.rgba(PAL.deep, 0.75) }, alpha: o.alpha, align: o.align, reveal: o.reveal,
    });
  }
  /**
   * White capsule label: soft dark drop shadow beneath, faint glossy strip along the top, optional pointer
   * triangle ("up" | "down") aiming at the subject. s = pop scale. o.dot: a coloured number disc on the left.
   */
  function pill(ctx, x, y, text, size, s = 1, o = {}) {
    if (s <= 0.001) return;
    ctx.save();
    ctx.font = B.font(size, BODY, 800);
    const dotW = o.dot ? size * 1.5 : 0;
    const tw = ctx.measureText(text).width, h = size * 1.9, w = tw + size * 1.6 + dotW;
    ctx.translate(x, y);
    ctx.scale(s, s);
    if (o.alpha != null) ctx.globalAlpha *= o.alpha;
    const path = (c) => {
      B.capsule(c, -w / 2, -h / 2, w, h);
      if (o.pointer) {
        const d = o.pointer === "up" ? -1 : 1, py = (d * h) / 2;
        c.moveTo(-size * 0.45, py - d * 2);
        c.quadraticCurveTo(0, py + d * size * 0.75, size * 0.45, py - d * 2);
        c.closePath();
      }
    };
    B.withShadow(ctx, { color: B.rgba("#0b0c26", 0.45), blur: size * 0.5, y: size * 0.22 }, () => {
      ctx.beginPath();
      path(ctx);
      ctx.fillStyle = B.linear(ctx, 0, -h / 2, 0, h / 2, [PAL.white, "#e3e2f2"]);
      ctx.fill();
    });
    ctx.beginPath(); // glossy highlight strip
    B.capsule(ctx, -w / 2 + h * 0.28, -h / 2 + h * 0.1, w - h * 0.56, h * 0.26);
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fill();
    if (o.dot) {
      ctx.beginPath();
      B.circle(ctx, -w / 2 + h * 0.5, 0, h * 0.34);
      ctx.fillStyle = o.dot;
      ctx.fill();
      ctx.fillStyle = PAL.white;
      ctx.font = B.font(size, HEAD, 800);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(o.num, -w / 2 + h * 0.5, size * 0.06);
    }
    ctx.font = B.font(size, BODY, 800);
    ctx.fillStyle = PAL.deep;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, dotW / 2, size * 0.04);
    ctx.restore();
    return w;
  }
  /** Width a pill will take (to place things beside it). */
  function pillWidth(ctx, text, size) {
    ctx.save();
    ctx.font = B.font(size, BODY, 800);
    const w = ctx.measureText(text).width + size * 1.6;
    ctx.restore();
    return w;
  }
  /** Four-point pinched sparkles and tiny light dots, sparse, each twinkling on its own phase. */
  function sparkles(ctx, t, seed, x, y, w, h, n, u) {
    const r = B.rng(seed);
    for (let i = 0; i < n; i++) {
      const px = x + r() * w, py = y + r() * h, size = r.range(0.8, 1.9) * u, ph = r(), per = r.range(1.6, 3.2);
      const tw = Math.pow(Math.max(0, Math.sin(B.TAU * (t / per + ph))), 3);
      if (tw < 0.02) continue;
      ctx.beginPath();
      if (i % 3 === 2) B.circle(ctx, px, py, size * 0.22 * (0.5 + tw));
      else B.sparkle(ctx, px, py, size * tw, 0.16);
      ctx.fillStyle = i % 4 === 0 ? B.rgba(PAL.yellow, 0.9) : B.rgba(PAL.white, 0.9);
      ctx.fill();
    }
  }
  /** Thick rounded dotted arrow drawn on tail to head, ending in a small rounded triangle. */
  function flatArrow(ctx, pts, p, u, color = PAL.white) {
    B.arrow(ctx, pts, { p, width: 1.5 * u, dots: 2.6 * u, head: 4.2 * u, color, headStyle: "tri" });
  }
  /** Round badge: green check or red cross, flat-shaded, popping on with scale s. */
  function badge(ctx, x, y, r, kind, s) {
    if (s <= 0.001) return;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(s, s);
    const col = kind === "check" ? PAL.green : PAL.pink;
    flatFill(ctx, (c) => B.circle(c, 0, 0, r), { x: -r, y: -r, w: 2 * r, h: 2 * r }, tones(col));
    ctx.strokeStyle = PAL.white;
    ctx.lineWidth = r * 0.24;
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.beginPath();
    if (kind === "check") {
      ctx.moveTo(-r * 0.42, r * 0.02);
      ctx.lineTo(-r * 0.1, r * 0.33);
      ctx.lineTo(r * 0.45, -r * 0.3);
    } else {
      ctx.moveTo(-r * 0.35, -r * 0.35);
      ctx.lineTo(r * 0.35, r * 0.35);
      ctx.moveTo(r * 0.35, -r * 0.35);
      ctx.lineTo(-r * 0.35, r * 0.35);
    }
    ctx.stroke();
    ctx.restore();
  }
  /** Ring gauge: pale track and a bright gradient fill that grows to p. */
  function ringGauge(ctx, x, y, r, width, p, colA, colB) {
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineWidth = width;
    ctx.strokeStyle = B.rgba(PAL.white, 0.14);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, B.TAU);
    ctx.stroke();
    if (p > 0.002) {
      ctx.strokeStyle = B.linear(ctx, x - r, y - r, x + r, y + r, [colA, colB]);
      ctx.beginPath();
      ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + B.TAU * p);
      ctx.stroke();
    }
    ctx.restore();
  }
  /** The 0..1 pop-in scale with the card's ~10 % overshoot. */
  const pop = (t, at, dur = 0.45) => B.pop(t, at, dur, 1.9);

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  function sun(ctx, x, y, r, t, glow) {
    B.glow(ctx, x, y, r * 3.2, PAL.yellow, 0.32 * glow * (1 + 0.15 * B.wave(t, 2.6)), { add: true });
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(t * 0.15);
    for (let i = 0; i < 10; i++) {
      // chunky rounded rays, each a capsule with its own flat fill
      ctx.save();
      ctx.rotate((i / 10) * B.TAU);
      const len = r * (i % 2 ? 0.34 : 0.5);
      ctx.beginPath();
      B.capsule(ctx, r * 1.18, -r * 0.1, len, r * 0.2);
      ctx.fillStyle = i % 2 ? PAL.orange : PAL.yellow;
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
    flatFill(ctx, (c) => B.circle(c, x, y, r), { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, { ...tones(PAL.yellow), shade: "#ffb23e", deep: PAL.orange, base2: "#ffc23f" });
  }
  /** A cloud is a union of circles; flatFill shades the whole silhouette at once. */
  function cloudPath(x, y, s) {
    return (c) => {
      B.circle(c, x - s * 0.55, y + s * 0.12, s * 0.38);
      B.circle(c, x - s * 0.1, y - s * 0.12, s * 0.52);
      B.circle(c, x + s * 0.45, y + s * 0.02, s * 0.42);
      B.roundRect(c, x - s * 0.9, y + s * 0.02, s * 1.75, s * 0.48, s * 0.24);
    };
  }
  function cloud(ctx, x, y, s, storm) {
    const base = B.mix("#e9e7fb", "#7f87c4", storm);
    flatFill(ctx, cloudPath(x, y, s), { x: x - s * 0.95, y: y - s * 0.65, w: s * 1.9, h: s * 1.15 }, { ...tones(base), light: B.mix("#ffffff", "#b7bde6", storm), shade: B.mix("#b9b4ea", "#5a619f", storm), deep: B.mix("#958fd8", "#454b86", storm) }, { shade: 0.13 });
  }
  function seaPath(W, H, top, t, u) {
    return (c) => {
      c.moveTo(-W * 0.3, H * 1.3);
      c.lineTo(-W * 0.3, top);
      for (let x = -W * 0.3; x <= W * 1.3; x += u * 2) c.lineTo(x, top + Math.sin(x / (u * 9) + t * 1.4) * u * 1.1);
      c.lineTo(W * 1.3, H * 1.3);
      c.closePath();
    };
  }
  /** A little flat sailboat bobbing on the sea (portrait title and close: it fills the tall frame). */
  function boat(ctx, x, y, s, t) {
    ctx.save(); ctx.translate(x, y + B.bob(t, s * 0.04, 2.6)); ctx.rotate(0.05 * B.wave(t, 3.1));
    flatFill(ctx, (c) => B.poly(c, [[-s, -s * 0.25], [s, -s * 0.25], [s * 0.7, s * 0.15], [-s * 0.7, s * 0.15]], true), { x: -s, y: -s * 0.25, w: 2 * s, h: s * 0.4 }, tones(PAL.orange), { shade: 0.2 });
    flatFill(ctx, (c) => B.poly(c, [[0, -s * 1.5], [s * 0.75, -s * 0.35], [0, -s * 0.35]], true), { x: 0, y: -s * 1.5, w: s * 0.75, h: s * 1.15 }, tones("#eeeefa"), { shade: 0.14 });
    flatFill(ctx, (c) => B.poly(c, [[-s * 0.1, -s * 1.2], [-s * 0.6, -s * 0.35], [-s * 0.1, -s * 0.35]], true), { x: -s * 0.6, y: -s * 1.2, w: s * 0.5, h: s * 0.85 }, tones(PAL.pink), { shade: 0.14 });
    ctx.restore();
  }
  function sea(ctx, W, H, top, t, u) {
    flatFill(ctx, seaPath(W, H, top, t, u), { x: 0, y: top, w: W, h: H - top }, { ...tones(PAL.teal), light: "#6fe3ee", base: "#2aa9c9", base2: "#1f6fa3" }, { shade: 0.0, deep: 0.0, rim: 0.012 });
    // a few lighter wave capsules riding the surface
    const r = B.rng("waves");
    for (let i = 0; i < 9; i++) {
      const wx = B.fract(r() + t * 0.02 * (i % 2 ? 1 : -1)) * W * 1.2 - W * 0.1, wy = top + (0.08 + r() * 0.5) * (H - top) * 0.6;
      ctx.beginPath();
      B.capsule(ctx, wx, wy + B.bob(t, u * 0.4, 2.2, r()), r.range(5, 11) * u, 0.9 * u);
      ctx.fillStyle = B.rgba("#9bf0f4", 0.35);
      ctx.fill();
    }
  }
  function dropPath(x, y, r) {
    return (c) => {
      c.moveTo(x, y - r * 1.8);
      c.bezierCurveTo(x + r * 0.3, y - r * 1.25, x + r, y - r * 0.65, x + r, y);
      c.arc(x, y, r, 0, Math.PI);
      c.bezierCurveTo(x - r, y - r * 0.65, x - r * 0.3, y - r * 1.25, x, y - r * 1.8);
      c.closePath();
    };
  }
  function drop(ctx, x, y, r) {
    flatFill(ctx, dropPath(x, y, r), { x: x - r, y: y - r * 1.8, w: 2 * r, h: r * 2.8 }, { ...tones(PAL.teal), light: "#a8f2f7" }, { shade: 0.16 });
  }

  // ------------------------------------------------------------------ layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    return {
      F, u, P,
      // portrait: a bigger sun and cloud and a lower sea, so the world fills the tall frame
      sun: P ? [W * 0.26, H * 0.24, 12.5 * u] : [W * 0.17, H * 0.27, 8.5 * u],
      cloud: P ? [W * 0.68, H * 0.245, 27 * u] : [W * 0.76, H * 0.26, 16 * u],
      seaTop: P ? H * 0.7 : H * 0.72,
      title: P ? [W / 2, H * 0.465] : [W / 2, H * 0.5],
      headSize: P ? 9.2 * u : 8.6 * u,
      label: 4.1 * u,
      number: P ? [W / 2, H * 0.45] : [W / 2, H * 0.4],
    };
  }

  // ------------------------------------------------------------------ backdrop (cached) and parallax layers
  function backdrop(ctx, W, H) {
    const c = B.layer("flat-backdrop", W, H, (g, w, h) => {
      // wide three-stop diagonal gradient in one cool hue family
      g.fillStyle = B.linear(g, 0, 0, w * 0.7, h, [PAL.light, "#2f2d78", PAL.deep]);
      g.fillRect(0, 0, w, h);
    });
    ctx.drawImage(c, 0, 0);
  }
  function bigGlows(ctx, W, H, t) {
    // two or three huge, very faint radial glows keep the backdrop from looking flat
    const D = Math.hypot(W, H);
    B.glow(ctx, W * 0.15, H * 0.15, D * 0.55, "#8d6bff", 0.16 * (1 + 0.1 * B.wave(t, 7)), { add: true });
    B.glow(ctx, W * 0.9, H * 0.55, D * 0.45, PAL.teal, 0.1, { add: true });
    B.glow(ctx, W * 0.4, H * 1.0, D * 0.4, PAL.pink, 0.07, { add: true });
  }
  function hills(ctx, W, H, top, u) {
    // muted, blur-free background shapes in dimmed palette colours
    ctx.fillStyle = B.mix(PAL.teal, PAL.deep, 0.72);
    ctx.beginPath();
    B.circle(ctx, W * 0.12, top + 10 * u, 22 * u);
    B.circle(ctx, W * 0.42, top + 14 * u, 26 * u);
    ctx.fill();
    ctx.fillStyle = B.mix(PAL.light, PAL.deep, 0.35);
    ctx.beginPath();
    B.circle(ctx, W * 0.78, top + 12 * u, 30 * u);
    B.circle(ctx, W * 1.02, top + 6 * u, 18 * u);
    ctx.fill();
  }

  // ------------------------------------------------------------------ scene A: the world (sun, cloud, sea)
  function worldCam(t, L, W, H) {
    const [nx, ny] = L.number;
    if (t < BEATS[1]) return { zoom: B.lerp(1.16, 1, B.prog(t, 0, 1.9, "inOutCubic")) }; // pull back off the title
    if (t < BEATS[2]) return { zoom: 1 };
    if (t < BEATS[3]) {
      const k = B.prog(t, 4.0, 1.4, "inOutCubic"); // push in on the key number
      return { zoom: 1 + 0.12 * k, x: B.lerp(W / 2, nx, k), y: B.lerp(H / 2, ny, k) };
    }
    if (t < BEATS[5]) {
      const k = B.prog(t, 8.4, 1.6, "outCubic"); // arrive from the dive, settle on the rain
      return { zoom: B.lerp(1.3, 1.08, k), y: H / 2 + L.u * 3 };
    }
    const k = B.prog(t, 10.3, 1.7, "inOutCubic"); // long pull-back to close
    return { zoom: B.lerp(1.08, 0.94, k), y: H / 2 + L.u * 3 * (1 - k) };
  }

  function world(ctx, W, H, t, L) {
    const u = L.u, cam = worldCam(t, L, W, H);
    const [sx, sy, sr] = L.sun, [cx, cy, cs] = L.cloud, top = L.seaTop;
    const rain = B.span(t, 8.45, 8.9) * (1 - B.span(t, 10.3, 10.9));
    const storm = 0.8 * B.span(t, 8.3, 8.9, "inOutSine") * (1 - B.span(t, 10.2, 11.2, "inOutSine"));
    backdrop(ctx, W, H);
    B.camera(ctx, W, H, cam, () => bigGlows(ctx, W, H, t), 0.3);
    B.camera(ctx, W, H, cam, () => hills(ctx, W, H, top, u), 0.55);
    B.camera(ctx, W, H, cam, () => {
      sparkles(ctx, t, "sky", W * 0.05, H * (L.P ? 0.13 : 0.08), W * 0.9, H * 0.22, 16, u); // high in the sky, clear of the labels
      sun(ctx, sx, sy + B.bob(t, u * 0.6, 3.1), sr, t, 1 - storm * 0.6 + 0.3 * B.span(t, 10.4, 11.4));
      // vapour: small soft wisps always rising off the sea toward the cloud (idle motion, never frozen)
      const r = B.rng("vapour");
      for (let i = 0; i < 14; i++) {
        const ph = B.fract(t / 3.2 + r()), x0 = B.lerp(W * 0.28, W * 0.62, r());
        const px = B.lerp(x0, cx - cs * 0.2, ph * ph) + Math.sin(ph * 9 + i) * u * 1.2, py = B.lerp(top - u, cy + cs * 0.4, ph);
        const a = Math.sin(ph * Math.PI) * 0.4 * (1 - rain) * B.span(t, 1.8, 2.1) * (1 - B.span(t, 10.2, 10.5)); // not over the headings
        ctx.beginPath();
        B.circle(ctx, px, py, u * (0.6 + 0.6 * (1 - ph)));
        ctx.fillStyle = B.rgba("#c9f6fa", a);
        ctx.fill();
      }
      // rain: flat teardrops falling from the cloud into the sea
      if (rain > 0) {
        const rr = B.rng("rain");
        for (let i = 0; i < 26; i++) {
          const ph = B.fract((t - 8.4) / 0.9 + rr()), dx = rr.range(-0.6, 0.6) * cs;
          const y = B.lerp(cy + cs * 0.4, top + u, ph);
          ctx.globalAlpha = rain * B.smooth(0, 0.1, ph);
          drop(ctx, cx + dx - ph * u * 3, y, u * 1.1);
          ctx.globalAlpha = 1;
        }
      }
      cloud(ctx, cx + B.bob(t, u * 1.2, 4.2, 0.3), cy + B.bob(t, u * 0.7, 3.3, 0.1), cs * (1 + 0.12 * storm), storm);
      sea(ctx, W, H, top, t, u);
      const bv = L.P ? pop(t, 0.6) * (1 - B.span(t, 1.6, 1.85)) + pop(t, 10.7) : 0; // only for the title and close
      if (bv > 0.01) { ctx.globalAlpha = Math.min(1, bv); boat(ctx, W * (0.24 + 0.006 * t), top + (H - top) * 0.22, 10 * u * bv, t); ctx.globalAlpha = 1; }
    }, 1);
    // labels, arrows and numbers ride with the foreground (no extra parallax), drawn after the scene
    B.camera(ctx, W, H, cam, () => overlays(ctx, W, H, t, L), 1);
  }

  function overlays(ctx, W, H, t, L) {
    const u = L.u, F = L.F, [sx, sy, sr] = L.sun, [cx, cy, cs] = L.cloud, top = L.seaTop, [tx, ty] = L.title;
    // beat 1: title
    const tIn = pop(t, 0.25, 0.55), tOut = 1 - B.span(t, 1.65, 1.95);
    if (tOut > 0 && tIn > 0.01) {
      ctx.save();
      ctx.translate(tx, ty);
      ctx.scale(tIn, tIn);
      heading(ctx, "Where does rain\ncome from?", 0, 0, L.headSize, { maxW: F.safe.w, alpha: tOut });
      ctx.restore();
      pill(ctx, tx, ty + L.headSize * 1.55, "The water cycle", L.label, pop(t, 0.7) * tOut);
    }
    // beat 2: labelled diagram with a dotted arrow
    const dOut = 1 - B.span(t, 3.85, 4.2);
    if (t > 1.9 && dOut > 0) {
      pill(ctx, sx, sy + sr * 2.5, "SUN", L.label, pop(t, 2.05) * dOut, { pointer: "up" });
      pill(ctx, cx, cy + cs * 0.82, "CLOUD", L.label, pop(t, 2.35) * dOut, { pointer: "up" });
      pill(ctx, W * 0.5, top + (H - top) * (L.P ? 0.2 : 0.32), "SEA", L.label, pop(t, 2.65) * dOut);
      // the arrow rises beside the cloud's pill, the vapour pill sits clear of it on the open side
      const a0 = [W * (L.P ? 0.8 : 0.66), top - u * 2], a1 = L.P ? [cx + cs * 0.55, cy + cs * 0.55] : [cx - cs * 0.95, cy + cs * 0.25];
      const pts = B.quad(a0[0], a0[1], W * (L.P ? 0.86 : 0.6), B.lerp(a0[1], a1[1], 0.45), a1[0], a1[1]);
      ctx.globalAlpha = dOut;
      flatArrow(ctx, pts, B.prog(t, 2.5, 0.7, "inOutCubic"), u);
      ctx.globalAlpha = 1;
      const mid = B.pointAt(pts, 0.5), vw = pillWidth(ctx, "Warm water rises as vapour", L.label);
      pill(ctx, Math.max(F.safe.x + vw / 2, mid[0] - 9 * u - vw / 2), mid[1] + (L.P ? 0 : 6 * u), "Warm water rises as vapour", L.label, pop(t, 2.95) * dOut);
    }
    // beat 3: the key number, counting up, landing with a bounce on a ring gauge
    const nOut = 1 - B.span(t, 5.75, 6.05);
    if (t > 4.0 && nOut > 0) {
      const [nx, ny] = L.number, R = L.P ? 19 * u : 14 * u;
      const k = B.prog(t, 4.2, 0.9), land = t - 5.1;
      const bounce = land > 0 ? 1 + 0.09 * Math.exp(-7 * land) * Math.sin(land * 17) : 0.86 + 0.14 * B.ease.outCubic(k);
      const s = pop(t, 4.05, 0.4) * nOut;
      ctx.save();
      ctx.translate(nx, ny);
      ctx.scale(s, s);
      B.glow(ctx, 0, 0, R * 1.9, PAL.yellow, 0.3 * (1 + 0.15 * B.wave(t, 1.6)), { add: true });
      ringGauge(ctx, 0, 0, R, 2.6 * u, 0.97 * B.ease.outCubic(k), PAL.teal, PAL.green);
      ctx.scale(bounce, bounce);
      heading(ctx, B.counter(k, 97, { suffix: "%" }), 0, u * 0.6, (L.P ? 15 : 12.5) * u, { color: PAL.yellow, maxLines: 1 });
      ctx.restore();
      pill(ctx, nx, ny + R + L.label * 2.4, "of Earth's water is in the oceans", L.label, pop(t, 5.15) * nOut);
    }
    // beat 5: the rain returns it - arrow down, green check, a brief green flash of the frame edge
    const rOut = 1 - B.span(t, 10.1, 10.45);
    if (t > 8.6 && rOut > 0) {
      const x0 = cx + cs * (L.P ? 0.68 : 0.95), pts = B.quad(x0, cy + cs * 0.4, x0 + u * (L.P ? 3 : 6), B.lerp(cy, top, 0.5), x0 - u * 2, top + u * 3); // it lands in the sea
      ctx.globalAlpha = rOut;
      flatArrow(ctx, pts, B.prog(t, 8.8, 0.6, "inOutCubic"), u);
      ctx.globalAlpha = 1;
      // the check badge and its pill as one centred group on the sea
      const by = top + (H - top) * (L.P ? 0.2 : 0.4), br = 3.4 * u, pw = pillWidth(ctx, "Rain falls back to the sea", L.label);
      const gx = W / 2 - (pw + br * 2.6) / 2;
      badge(ctx, gx + br, by, br, "check", pop(t, 9.3) * rOut);
      pill(ctx, gx + br * 2.6 + pw / 2, by, "Rain falls back to the sea", L.label, pop(t, 9.4) * rOut);
      heading(ctx, L.P ? "Cool vapour\nturns to\ndrops" : "Cool vapour\nturns to drops", L.P ? W * 0.27 : W * 0.36, L.P ? H * 0.47 : H * 0.5, L.headSize * 0.72, { maxW: W * (L.P ? 0.42 : 0.5), maxLines: 3, alpha: Math.min(B.span(t, 8.9, 9.2), rOut) });
    }
    // beat 6: close
    if (t > 10.56) {
      const s = pop(t, 10.55, 0.55);
      ctx.save();
      ctx.translate(tx, ty);
      ctx.scale(s, s);
      heading(ctx, "Rain is the sea,\nrecycled", 0, 0, L.headSize, { maxW: F.safe.w });
      ctx.restore();
      pill(ctx, tx, ty + L.headSize * 1.55, "And the cycle starts again", L.label, pop(t, 11.0));
    }
  }

  // ------------------------------------------------------------------ scene B: the cycle (3 steps on a dotted loop)
  function cycle(ctx, W, H, t, L) {
    const u = L.u, F = L.F, P = L.P;
    const C = P ? [W / 2, H * 0.45] : [W * 0.63, H * 0.44], R = P ? W * 0.36 : H * 0.25;
    const lt = t - BEATS[3];
    const dive = B.span(t, 8.0, 8.4, "inExpo");
    backdrop(ctx, W, H);
    bigGlows(ctx, W, H, t);
    B.zoomAt(ctx, C[0], C[1], 1 + 0.04 * B.prog(lt, 0, 2.3) + 5 * dive, () => {
      hills(ctx, W, H, P ? L.seaTop : H * 0.86, u); // the same world: the loop turns over the sea
      sea(ctx, W, H, P ? L.seaTop : H * 0.86, t, u);
      sparkles(ctx, t, "cyc", W * 0.82, F.safe.y, W * 0.13, H * 0.1, 6, u); // a corner, clear of the heading and pills
      heading(ctx, "The water cycle", P ? W / 2 : W * 0.24, P ? F.safe.y + 6 * u : H * 0.44, L.headSize * 0.9, { maxW: P ? F.safe.w : W * 0.36, alpha: B.span(lt, 0.25, 0.5) });
      if (!P) pill(ctx, W * 0.24, H * 0.44 + L.headSize * 1.4, "round and round", L.label, pop(lt, 0.5));
      // dotted loop, drawn on, with a travelling glowing dot showing the flow
      const loop = B.arcPts(C[0], C[1], R, -Math.PI / 2, Math.PI * 1.5, 120);
      const lp = B.prog(lt, 0.15, 0.6, "inOutCubic");
      const shown = B.trim(loop, 0, lp), nd = Math.floor(B.pathLength(shown) / (2.8 * u));
      ctx.fillStyle = B.rgba(PAL.white, 0.5);
      ctx.beginPath();
      for (let i = 0; i <= nd; i++) {
        const q = B.pointAt(shown, nd ? i / nd : 0);
        B.circle(ctx, q[0], q[1], 0.7 * u);
      }
      ctx.fill();
      const ang = -Math.PI / 2 + Math.max(0, lt - 0.3) * ((B.TAU / 3) / 0.3); // the dot reaches each step as it pops
      if (lt > 0.3) {
        const dx = C[0] + Math.cos(ang) * R, dy = C[1] + Math.sin(ang) * R;
        B.glow(ctx, dx, dy, 6 * u, PAL.yellow, 0.8, { add: true });
        ctx.beginPath();
        B.circle(ctx, dx, dy, 1.4 * u);
        ctx.fillStyle = "#fff6c8";
        ctx.fill();
      }
      // centre icon follows the current step
      const step = lt < 0.6 ? 0 : lt < 0.9 ? 1 : 2;
      const ic = pop(lt, [0.35, 0.6, 0.9][step], 0.4), ir = R * 0.36;
      ctx.save();
      ctx.translate(C[0], C[1]);
      ctx.scale(ic, ic);
      if (step === 0) sun(ctx, 0, 0, ir * 0.8, t, 0.7);
      else if (step === 1) cloud(ctx, 0, ir * 0.1, ir * 1.5, 0);
      else drop(ctx, 0, ir * 0.35, ir * 0.7);
      ctx.restore();
      // the three steps, as numbered pills around the loop
      const steps = [["Sun heats the sea", PAL.orange], ["Vapour cools to cloud", PAL.teal], ["Drops fall as rain", PAL.pink]];
      steps.forEach(([txt, col], i) => {
        const a = -Math.PI / 2 + (i * B.TAU) / 3;
        // steps 2 and 3 sit at the same height on the loop: step 3 drops a row so the pills never collide
        let px = C[0] + Math.cos(a) * R, py = C[1] + Math.sin(a) * R + (i ? 1 : -1) * L.label * 0.2 + (i === 2 ? L.label * 2.6 : 0);
        const halfW = (txt.length * L.label * 0.56 + L.label * 3.1) / 2;
        px = B.clamp(px, F.safe.x + halfW, F.safe.r - halfW);
        pill(ctx, px, py, txt, L.label, pop(lt, 0.3 + i * 0.3), { dot: col, num: String(i + 1) });
      });
    });
    // the dive into the glowing centre whites out, then opens on the rain
    B.cover(ctx, W, H, "#ffffff", B.span(t, 8.15, 8.4));
  }

  // ------------------------------------------------------------------ transitions and finishing
  /** A huge flat-shaded disc sweeping across the frame as a wipe; the scene swaps when it covers everything. */
  function discWipe(ctx, W, H, t, at, col) {
    const p = B.span(t, at - 0.4, at + 0.4, "inOutCubic");
    if (p <= 0 || p >= 1) return;
    const R = Math.hypot(W, H) * 0.62, x = B.lerp(-R, W + R, p), y = H * 0.5;
    const R2 = R * 0.55, x2 = x - R * 1.15;
    flatFill(ctx, (c) => B.circle(c, x2, y + H * 0.12, R2), { x: x2 - R2, y: y - R2, w: 2 * R2, h: 2 * R2 }, tones(PAL.orange), { shade: 0.05, deep: 0.015, rim: 0.01 });
    flatFill(ctx, (c) => B.circle(c, x, y, R), { x: x - R, y: y - R, w: 2 * R, h: 2 * R }, tones(PAL.teal), { shade: 0.05, deep: 0.015, rim: 0.01 });
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    const inCycle = t >= BEATS[3] && t < BEATS[4];
    if (inCycle) cycle(ctx, W, H, t, L);
    else world(ctx, W, H, t, L);
    discWipe(ctx, W, H, t, BEATS[3], PAL.teal);
    if (t >= BEATS[4]) B.cover(ctx, W, H, "#ffffff", 1 - B.span(t, 8.4, 8.75)); // whiteout opening on the rain
    // green edge flash for "right"
    const flash = Math.max(0, 1 - Math.abs(t - 9.35) / 0.25);
    if (flash > 0) B.vignette(ctx, W, H, { color: PAL.green, amount: 0.55 * flash, inner: 0.6 });
    // finishing: fine moving grain (overlay ~9 %) and a static large-scale mottle (overlay ~11 %)
    B.mottle(ctx, W, H, { amount: 0.11, feature: 0.22, seed: 5 });
    B.grain(ctx, W, H, { amount: 0.09, t });
  }

  // ------------------------------------------------------------------ sound: marimba plucks in A minor, boops, airy breaths, a boom + chord on the number
  function score(k) {
    const sc = SOUND.scale("A3", "minor", 10); // A B C D E F G A B C
    k.bed("pad", 0, DUR, { notes: ["A2", "E3", "A3", "C4"], gain: 0.55 });
    k.at(0.05, "breath", { dur: 1.6, gain: 0.7 });
    k.at(0.25, "boop", { pitch: -2 }).at(0.28, "pluck", { note: sc[4] }).at(0.7, "pop", { gain: 0.6 });
    k.at(0.9, "sparkle", { gain: 0.35 });
    k.at(1.65, "breath", { dur: 0.6, gain: 0.5 });
    [2.05, 2.35, 2.65].forEach((at, i) => k.at(at, "boop", { pitch: i * 2, pan: [-0.4, 0.4, 0][i] }).at(at, "pluck", { note: sc[2 + i * 2], gain: 0.6 }));
    k.at(2.5, "swish", { dur: 0.7, gain: 0.7 });
    k.seq(2.55, 0.13, [sc[0], sc[2], sc[4], sc[7]], { gain: 0.45 });
    k.at(2.95, "pop", { pan: 0.2 });
    k.at(4.0, "breath", { dur: 1.3, gain: 0.6 });
    k.at(4.05, "boop", { pitch: -5 });
    k.repeat(4.2, 0.075, 12, "tick", { gain: 0.45, vary: 1 });
    k.at(5.1, "boom", { gain: 0.8 }).at(5.1, "chord", { notes: ["A4", "C5", "E5", "A5"], gain: 0.8 });
    k.at(5.15, "pop", { gain: 0.6 });
    k.at(5.7, "whoosh", { dur: 0.8 });
    [6.4, 6.7, 7.0].forEach((at, i) => k.at(at, "pluck", { note: sc[4 + i * 2] }).at(at, "boop", { pitch: i * 3, gain: 0.7, pan: [0, 0.4, -0.4][i] }));
    k.at(7.95, "riser", { dur: 0.45, gain: 0.6 });
    k.at(8.4, "breath", { dur: 1.0, gain: 0.8 });
    k.bed("rain", 8.45, 10.7, { gain: 0.5, fade: 0.4 });
    k.repeat(8.6, 0.16, 9, "bubble", { gain: 0.25, vary: 4, pitch: 7, jitter: 0.04 });
    k.at(8.8, "swish", { dur: 0.6, gain: 0.6 });
    k.at(9.3, "success", { gain: 0.9 }).at(9.4, "pop");
    k.at(10.3, "breath", { dur: 1.7, gain: 0.7 });
    k.at(10.55, "boop", { pitch: -2 }).at(10.6, "chord", { notes: ["F4", "A4", "C5", "E5"], strum: 0.05, gain: 0.7 });
    k.at(11.0, "pop", { gain: 0.6 }).at(11.05, "chime", { note: "E6", gain: 0.5 });
  }

  Player.register({
    id: "flat-explainer",
    name: "Flat Vector Explainer",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Nunito+Sans:wght@600;700;800;900&display=swap",
      faces: ['800 20px "Baloo 2"', '700 20px "Baloo 2"', '800 20px "Nunito Sans"', '700 20px "Nunito Sans"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Rain returns", "Close"],
    draw,
    score,
  });
})();
