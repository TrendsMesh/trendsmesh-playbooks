/* 44 Soft 3D Clay - reference animation.
 * Topic (setting, replace it): "How a hot-air balloon flies" - burner, hot air about 100 C, lift, vent to land.
 * Rendering (keep it): inflated, rounded soft-plastic objects. Every object is painted flat into an offscreen
 * mask, then shaded there: a broad key light from the upper left, a soft core-shadow band hugging the lower right,
 * a thin bounce-light rim right at that edge and a matte-glossy specular blob plus a small glint. Objects sit on a
 * pastel studio sweep (wall curving into floor) with large soft contact shadows and tight ambient occlusion where
 * they touch. Chubby 3D letters and digits are layered offset fills (extrusion) with a light lip, a gradient
 * face and a clipped glint. Motion is bouncy: springy pops, squash and stretch on landings, slow fake turns by
 * sliding the balloon's gores and its highlight, a puffy cloud bank as the wipe.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = {
    peach: "#ffd8c6", // backdrop peach
    lilac: "#d9ccf8", // backdrop lilac
    mint: "#c6efdd", // backdrop mint
    sky: "#c9e3ff", // backdrop sky
    coral: "#ff7f8e", // hero coral
    butter: "#ffcf63", // butter yellow (warmth, flame, key number)
    plum: "#4b3b6e", // text and tinted shadows
    cream: "#fff8f0", // pills, clouds, stripes
  };
  const HEAD = "Fredoka", BODY = "Nunito";
  const DUR = 12;
  const BEATS = [0, 2.0, 4.2, 6.4, 8.6, 10.4];
  const BG = [PAL.peach, PAL.sky, PAL.lilac, PAL.mint, PAL.sky, PAL.peach];

  // ------------------------------------------------------------------ soft 3D helpers (reuse these)
  /** Tones for one hue: tint for the lit face, deeper shades for extrusion, a pale rim. */
  function tones(hex) {
    return { light: B.shade(hex, 0.42), base: hex, base2: B.shade(hex, -0.08), shade: B.shade(hex, -0.22), deep: B.shade(hex, -0.4), rim: B.shade(hex, 0.62) };
  }
  /** Two offscreen canvases at frame size, reused for every object (only the used corner is touched). */
  function poolCtx(key, W, H) {
    return B.layer("s3d-pool-" + key, W, H, () => {}).getContext("2d");
  }
  function resetCtx(g, w, h) {
    g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = "source-over"; g.filter = "none";
    g.clearRect(0, 0, w + 4, h + 4);
  }
  /**
   * The core of the look. paint(g) fills the silhouette in flat colours (ctx coordinates) inside bb {x, y, w, h};
   * it is shaded offscreen at the real pixel scale, then drawn in place: (1) a broad key light from the upper left
   * with a tinted falloff (inflated volume), (2) a soft core-shadow band hugging the lower right = the silhouette
   * minus a blurred copy shifted up-left, (3) a thin bounce-light rim at that edge, the same trick with a small shift,
   * (4) a matte-glossy specular blob and glint (o.lx / o.ly move them: a fake slow turn).
   * o: { dark, shadeA, rim, rimA, spec, lx, ly }
   */
  function puff(ctx, bb, paint, o = {}) {
    const m = ctx.getTransform(), CW = ctx.canvas.width, CH = ctx.canvas.height;
    const mn = Math.min(bb.w, bb.h), pad = mn * 0.06 + 2;
    const lw = bb.w + 2 * pad, lh = bb.h + 2 * pad;
    let sc = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)) || 1;
    sc = Math.min(sc, (CW - 4) / lw, (CH - 4) / lh);
    const w = Math.ceil(lw * sc), h = Math.ceil(lh * sc);
    if (w < 3 || h < 3) return;
    const S = poolCtx("S", CW, CH), D = poolCtx("D", CW, CH);
    const ox = bb.x - pad, oy = bb.y - pad;
    const local = (g) => g.setTransform(sc, 0, 0, sc, -ox * sc, -oy * sc);
    resetCtx(S, w, h);
    S.save(); // paint may clip; never let that leak into the next object
    local(S); paint(S); S.restore(); local(S); S.globalCompositeOperation = "source-atop";
    const lx = bb.x + bb.w * (o.lx ?? 0.32), ly = bb.y + bb.h * (o.ly ?? 0.26), R = Math.hypot(bb.w, bb.h) * 0.82;
    const dark = o.dark || PAL.plum;
    S.fillStyle = B.radial(S, lx, ly, 0, R, [[0, "rgba(255,255,255,0.4)"], [0.3, "rgba(255,255,255,0.1)"], [0.56, "rgba(255,255,255,0)"], [1, B.rgba(dark, 0.3)]]);
    S.fillRect(ox, oy, lw, lh);
    const band = (col, alpha, off, blur) => {
      resetCtx(D, w, h); D.fillStyle = col; D.fillRect(0, 0, w, h); D.globalCompositeOperation = "destination-out";
      D.filter = `blur(${Math.max(0.6, blur * sc).toFixed(1)}px)`;
      D.drawImage(S.canvas, 0, 0, w, h, -off * sc, -off * sc * 1.2, w, h); D.filter = "none";
      S.setTransform(1, 0, 0, 1, 0, 0); S.globalCompositeOperation = "source-atop"; S.globalAlpha = alpha;
      S.drawImage(D.canvas, 0, 0, w, h, 0, 0, w, h); S.globalAlpha = 1;
    };
    band(dark, o.shadeA ?? 0.34, mn * 0.075, mn * 0.085); // core shadow, soft and wide
    band(o.rim || "#ffffff", o.rimA ?? 0.5, mn * 0.02, mn * 0.018); // bounce light right at the edge
    local(S); S.globalCompositeOperation = "source-atop";
    const spec = o.spec ?? 1;
    if (spec > 0) {
      const sx = bb.x + bb.w * ((o.lx ?? 0.32) - 0.02), sy = bb.y + bb.h * ((o.ly ?? 0.26) - 0.07);
      S.save(); S.translate(sx, sy); S.rotate(-0.55); S.scale(1, 0.62);
      S.fillStyle = B.radial(S, 0, 0, 0, mn * 0.2, [[0, `rgba(255,255,255,${0.55 * spec})`], [0.5, `rgba(255,255,255,${0.22 * spec})`], [1, "rgba(255,255,255,0)"]]);
      S.fillRect(-mn * 0.2, -mn * 0.2, mn * 0.4, mn * 0.4); S.beginPath();
      S.ellipse(-mn * 0.02, -mn * 0.02, mn * 0.055, mn * 0.032, 0, 0, B.TAU);
      S.fillStyle = `rgba(255,255,255,${0.8 * spec})`;
      S.fill(); S.restore();
    }
    ctx.drawImage(S.canvas, 0, 0, w, h, ox, oy, w / sc, h / sc);
  }
  /** Soft contact shadow on the floor: a wide faint pool plus a tight dark core (ambient occlusion). */
  function floorShadow(ctx, x, y, rx, lift, u) {
    const k = B.clamp(1 - lift);
    B.contactShadow(ctx, x, y, rx * (1.25 + 0.6 * (1 - k)), rx * 0.22 * (1.2 + 0.4 * (1 - k)), 0.22 * (0.35 + 0.65 * k), PAL.plum);
    if (k > 0.6) B.contactShadow(ctx, x, y, rx * 0.62, rx * 0.09, 0.45 * (k - 0.6) / 0.4, PAL.plum);
  }
  /**
   * Chubby 3D word: each glyph is a stack of offset fills (extrusion, deep to mid shade), a pale lip (rim light),
   * a gradient face, a soft top gloss and a glint clipped to the glyph. o.pop(i) scale and o.squash(i) [sx, sy]
   * per letter make them spring in one by one.
   */
  function text3d(ctx, str, x, y, size, hex, o = {}) {
    ctx.save(); ctx.font = B.font(size, HEAD, 700); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const chars = [...str], ws = chars.map((c) => ctx.measureText(c).width), sp = size * 0.03;
    const total = ws.reduce((a, b) => a + b, 0) + sp * (chars.length - 1);
    const tone = tones(hex), depth = size * 0.09, N = 8, fat = size * 0.075;
    ctx.lineJoin = "round"; ctx.lineWidth = fat;
    B.contactShadow(ctx, x + size * 0.05, y + size * 0.52, total * 0.5, size * 0.12, 0.16 * Math.min(1, o.pop ? o.pop(0) : 1), PAL.plum);
    let cx = x - total / 2;
    chars.forEach((ch, i) => {
      const w = ws[i], px = cx + w / 2;
      cx += w + sp; if (ch === " ") return;
      const s = o.pop ? o.pop(i) : 1;
      if (s <= 0.01) return;
      const [qx, qy] = o.squash ? o.squash(i) : [1, 1];
      ctx.save(); ctx.translate(px, y + size * 0.34); ctx.scale(s * qx, s * qy); ctx.translate(0, -size * 0.34);
      for (let j = N; j >= 1; j--) {
        const k = j / N;
        ctx.fillStyle = ctx.strokeStyle = B.mix(tone.shade, tone.deep, k);
        if (j === N) { ctx.shadowColor = B.rgba(PAL.plum, 0.28); ctx.shadowBlur = size * 0.16; ctx.shadowOffsetY = size * 0.07; }
        ctx.strokeText(ch, depth * k * 0.32, depth * k); ctx.fillText(ch, depth * k * 0.32, depth * k);
        ctx.shadowColor = "transparent";
      }
      ctx.fillStyle = ctx.strokeStyle = tone.rim; // the soft rim lip between face and extrusion
      ctx.strokeText(ch, size * 0.012, size * 0.022);
      ctx.fillStyle = ctx.strokeStyle = B.linear(ctx, 0, -size * 0.42, 0, size * 0.36, [tone.light, hex, tone.base2]);
      ctx.strokeText(ch, 0, 0); ctx.fillText(ch, 0, 0);
      ctx.fillStyle = B.linear(ctx, 0, -size * 0.44, 0, size * 0.02, ["rgba(255,255,255,0.5)", "rgba(255,255,255,0)"]);
      ctx.fillText(ch, 0, 0); ctx.save(); ctx.beginPath();
      ctx.ellipse(-w * 0.18, -size * 0.22, Math.max(w * 0.17, size * 0.07), size * 0.085, -0.5, 0, B.TAU); ctx.clip();
      ctx.fillStyle = "rgba(255,255,255,0.62)"; ctx.fillText(ch, 0, 0); ctx.restore(); ctx.restore();
    }); ctx.restore();
    return total;
  }
  /** Springy letter pops: staggered overshoot in, a squash wobble as each lands, a quick inBack shrink out. */
  function letterAnim(t, at, gap, out) {
    const o = (i) => {
      const end = out == null ? 1 : 1 - Math.max(0, B.ease.inBack(B.prog(t, out + i * 0.03, 0.28)));
      return B.pop(t, at + i * gap, 0.5, 2.4) * Math.max(0, end);
    };
    const q = (i) => squashAt(t, at + i * gap + 0.22, 0.14);
    return { pop: o, squash: q };
  }
  /** Damped squash and stretch after an event: wide and short first, then tall, then settled. */
  function squashAt(t, at, amp = 0.08) {
    const d = t - at;
    if (d <= 0) return [1, 1];
    const a = amp * Math.exp(-5.5 * d) * Math.sin(15 * d);
    return [1 + a, 1 - a];
  }
  /** Pop scale with exit: springs in at a, swells then shrinks out (inBack) to end at b. */
  function life(t, a, b, d = 0.45) {
    const out = b == null ? 1 : 1 - B.ease.inBack(B.prog(t, b - 0.28, 0.28));
    return Math.max(0, B.pop(t, a, d, 2.2) * out);
  }
  /** Width of a pill (to place it inside the safe area). */
  function pillW(ctx, text, size, num) {
    ctx.save(); ctx.font = B.font(size, BODY, 800);
    const w = ctx.measureText(text).width + size * 1.8 + (num ? size * 1.6 : 0);
    ctx.restore();
    return w;
  }
  /** Puffy cream capsule label with plum text; optional numbered ball (o.num, o.color) on the left. */
  function pill(ctx, x, y, text, size, s, o = {}) {
    if (s <= 0.01) return;
    const w = pillW(ctx, text, size, o.num), h = size * 2.1;
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    B.contactShadow(ctx, size * 0.2, h * 0.62, w * 0.52, h * 0.3, 0.2, PAL.plum);
    puff(ctx, { x: -w / 2, y: -h / 2, w, h }, (g) => {
      g.beginPath(); B.capsule(g, -w / 2, -h / 2, w, h); g.fillStyle = o.fill || PAL.cream; g.fill();
    }, { dark: "#8f7fc0", shadeA: 0.28, ly: 0.2 });
    let tx = 0;
    if (o.num) {
      const r = h * 0.36, bx = -w / 2 + h * 0.52;
      ball(ctx, bx, 0, r, o.color || PAL.coral, { spec: 0.9 }); ctx.font = B.font(size * 1.05, HEAD, 700);
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = B.shade(o.color || PAL.coral, -0.35);
      ctx.fillText(o.num, bx + size * 0.05, size * 0.12); ctx.fillStyle = "#ffffff"; ctx.fillText(o.num, bx, size * 0.04);
      tx = size * 0.8;
    }
    ctx.font = B.font(size, BODY, 800); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = PAL.plum;
    ctx.fillText(text, tx, size * 0.06); ctx.restore();
  }
  /** A glossy inflated ball. */
  function ball(ctx, x, y, r, col, o = {}) {
    puff(ctx, { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, (g) => {
      g.beginPath(); B.circle(g, x, y, r); g.fillStyle = col; g.fill();
    }, { dark: B.shade(col, -0.55), shadeA: 0.4, ...o });
  }
  /** Leader: a soft plum stick ending in a small ball, from a label to what it names. */
  function leader(ctx, a, b, p, u) {
    if (p <= 0.01) return;
    const e = [B.lerp(a[0], b[0], p), B.lerp(a[1], b[1], p)];
    ctx.save(); ctx.lineCap = "round"; ctx.strokeStyle = B.rgba(PAL.plum, 0.55); ctx.lineWidth = 0.7 * u; ctx.beginPath();
    ctx.moveTo(a[0], a[1]); ctx.lineTo(e[0], e[1]); ctx.stroke(); ctx.restore();
    ball(ctx, e[0], e[1], 1.3 * u, PAL.cream, { dark: "#7d6db0" });
  }
  /** Puffy cloud: a union of circles shaded as one inflated pillow. */
  function cloud(ctx, x, y, s, col = PAL.cream) {
    puff(ctx, { x: x - s, y: y - s * 0.72, w: 2 * s, h: s * 1.16 }, (g) => {
      g.beginPath(); B.circle(g, x - s * 0.5, y, s * 0.42); B.circle(g, x - s * 0.05, y - s * 0.26, s * 0.46);
      B.circle(g, x + s * 0.5, y + s * 0.02, s * 0.38); B.capsule(g, x - s * 0.95, y - s * 0.05, s * 1.88, s * 0.48);
      g.fillStyle = col; g.fill();
    }, { dark: "#8e80c8", shadeA: 0.32, spec: 0.5 });
  }
  /** Puffy four-point sparkle, twinkling (scale tw 0..1). */
  function sparkle(ctx, x, y, r, tw) {
    if (tw <= 0.03) return;
    const rr = r * tw;
    puff(ctx, { x: x - rr, y: y - rr, w: 2 * rr, h: 2 * rr }, (g) => {
      g.beginPath(); B.sparkle(g, x, y, rr, 0.3); g.fillStyle = PAL.butter; g.fill();
    }, { dark: "#c9711f", shadeA: 0.35, spec: 0.7 });
  }
  function heart(ctx, x, y, r) {
    puff(ctx, { x: x - r, y: y - r * 0.85, w: 2 * r, h: r * 1.85 }, (g) => {
      g.beginPath(); g.moveTo(x, y + r);
      g.bezierCurveTo(x - r * 1.25, y + r * 0.1, x - r * 0.95, y - r * 0.95, x, y - r * 0.35);
      g.bezierCurveTo(x + r * 0.95, y - r * 0.95, x + r * 1.25, y + r * 0.1, x, y + r); g.fillStyle = PAL.coral; g.fill();
    }, { dark: "#a3243e", shadeA: 0.38 });
  }
  /** Fat inflated arrow along pts, grown to p: a round tube and a rounded head, shaded as one object. */
  function arrow3d(ctx, pts, p, width, col) {
    if (p <= 0.01) return;
    const shown = B.trim(pts, 0, p), tip = B.pointAt(pts, p);
    const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]), hw = width * 1.6;
    const bb = { x: Math.min(...xs) - hw, y: Math.min(...ys) - hw, w: Math.max(...xs) - Math.min(...xs) + 2 * hw, h: Math.max(...ys) - Math.min(...ys) + 2 * hw };
    puff(ctx, bb, (g) => {
      g.lineCap = g.lineJoin = "round"; g.strokeStyle = g.fillStyle = col; g.lineWidth = width;
      const body = B.trim(shown, 0, Math.max(0, 1 - (width * 1.2) / Math.max(1, B.pathLength(shown))));
      g.beginPath(); body.forEach((q, i) => (i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.stroke();
      const a = tip[2], L = width * 1.7;
      g.beginPath(); g.moveTo(tip[0] + Math.cos(a) * L * 0.25, tip[1] + Math.sin(a) * L * 0.25);
      g.lineTo(tip[0] - Math.cos(a) * L + Math.cos(a + Math.PI / 2) * L * 0.75, tip[1] - Math.sin(a) * L + Math.sin(a + Math.PI / 2) * L * 0.75);
      g.lineTo(tip[0] - Math.cos(a) * L - Math.cos(a + Math.PI / 2) * L * 0.75, tip[1] - Math.sin(a) * L - Math.sin(a + Math.PI / 2) * L * 0.75);
      g.closePath(); g.lineWidth = width * 0.45; g.fill(); g.stroke();
    }, { dark: "#b8601c", shadeA: 0.42, spec: 0.8 });
  }

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  const TOP = 1.05, MOUTH = 1.22, BASK0 = 1.5, BASK1 = 1.86; // balloon proportions in envelope radii
  /** Envelope half width at height v (in radii from the envelope centre, -TOP top .. MOUTH mouth). */
  function hw(v) {
    if (v <= 0) return Math.sqrt(Math.max(0, 1 - (v / TOP) * (v / TOP)));
    return 0.24 + 0.76 * Math.pow(Math.cos((v / MOUTH) * Math.PI * 0.5), 1.15);
  }
  function envelopePts(x, y, R) {
    const L = [], Rt = [];
    for (let i = 0; i <= 36; i++) {
      // dense near the crown (angle steps over the top dome), even down the taper
      const v = i <= 16 ? -TOP * Math.cos((i / 16) * Math.PI * 0.5) : ((i - 16) / 20) * MOUTH;
      L.push([x - hw(v) * R, y + v * R]); Rt.push([x + hw(v) * R, y + v * R]);
    }
    return L.concat(Rt.reverse());
  }
  /**
   * The balloon: envelope with gores that slide past as it slowly turns (rot), a vent cap that lifts (vent),
   * the burner flame (heat), ropes and a woven basket. b = { x, y, R, heat, vent, rot, q: [sx, sy] }.
   */
  function balloon(ctx, b, t) {
    const { x, y, R } = b, ay = y + BASK1 * R;
    ctx.save(); ctx.translate(x, ay); ctx.scale(b.q[0], b.q[1]); ctx.translate(-x, -ay);
    // warm glow from the flame inside the mouth
    if (b.heat > 0.05) B.glow(ctx, x, y + 1.2 * R, R * 0.55, PAL.butter, 0.3 * b.heat);
    // envelope
    const env = envelopePts(x, y, R);
    puff(ctx, { x: x - R, y: y - TOP * R, w: 2 * R, h: (TOP + MOUTH) * R }, (g) => {
      g.beginPath(); B.poly(g, env, true); g.fillStyle = PAL.coral; g.fill(); g.save(); g.clip();
      const n = 12;
      for (let k = 0; k < n; k += 2) {
        let a0 = ((k / n) * B.TAU + b.rot) % B.TAU, a1 = a0 + B.TAU / n;
        // only the front half shows; map the angle to [-pi, pi]
        const wrap = (a) => (((a + Math.PI) % B.TAU) + B.TAU) % B.TAU - Math.PI;
        a0 = wrap(a0); a1 = a0 + B.TAU / n;
        const lo = Math.max(a0, -Math.PI / 2), hi = Math.min(a1, Math.PI / 2);
        if (hi <= lo) continue;
        const left = [], right = [];
        for (let i = 0; i <= 30; i++) {
          const v = i <= 12 ? -TOP * Math.cos((i / 12) * Math.PI * 0.5) : ((i - 12) / 18) * MOUTH, w = hw(v) * R;
          left.push([x + Math.sin(lo) * w, y + v * R]); right.push([x + Math.sin(hi) * w, y + v * R]);
        }
        g.beginPath(); B.poly(g, left.concat(right.reverse()), true); g.fillStyle = PAL.cream; g.fill();
      }
      g.restore();
      g.globalCompositeOperation = "source-atop"; // everything else stays inside the envelope
      // a butter band around the equator, following the same turn
      g.fillStyle = B.rgba(PAL.butter, 0.95); g.beginPath();
      const ring = (v, i) => { const a = B.lerp(-Math.PI / 2, Math.PI / 2, i / 30); g.lineTo(x + Math.sin(a) * hw(v) * R, y + v * R + Math.cos(a) * R * 0.06); };
      for (let i = 0; i <= 30; i++) ring(0.42, i); for (let i = 30; i >= 0; i--) ring(0.56, i); g.fill();
      // heated air: the envelope warms from inside
      if (b.heat > 0.4) {
        g.fillStyle = B.radial(g, x, y + 0.6 * R, 0, R * 1.3, [[0, B.rgba(PAL.butter, (b.heat - 0.4) * 0.55)], [1, B.rgba(PAL.butter, 0)]]);
        g.fillRect(x - R, y - R * TOP, 2 * R, R * (TOP + MOUTH));
      }
      // open vent: a dark hole at the crown
      if (b.vent > 0.02) {
        g.beginPath(); g.ellipse(x, y - TOP * R + R * 0.1, R * 0.26 * b.vent, R * 0.07 * b.vent, 0, 0, B.TAU);
        g.fillStyle = B.shade(PAL.plum, -0.2); g.fill();
      }
      // mouth opening
      g.beginPath(); g.ellipse(x, y + MOUTH * R - R * 0.01, R * 0.23, R * 0.045, 0, 0, B.TAU);
      g.fillStyle = B.shade(PAL.plum, 0.1); g.fill();
    }, { dark: "#8a2c55", shadeA: 0.46, rim: "#ffe2d6", lx: 0.3 + 0.025 * Math.sin(b.rot * 2), ly: 0.2 });
    // vent cap (the parachute) lifted off the crown
    const capY = y - TOP * R + R * 0.06 - b.vent * R * 0.2;
    if (b.vent > 0.02) {
      puff(ctx, { x: x - R * 0.3, y: capY - R * 0.06, w: R * 0.6, h: R * 0.14 }, (g) => {
        g.beginPath(); g.ellipse(x, capY + R * 0.01, R * 0.3, R * 0.07, 0, Math.PI, 0);
        g.ellipse(x, capY + R * 0.01, R * 0.3, R * 0.025, 0, 0, Math.PI); g.fillStyle = PAL.coral; g.fill();
      }, { dark: "#8a2c55", shadeA: 0.3 });
    }
    // ropes
    ctx.strokeStyle = B.mix(PAL.plum, "#ffffff", 0.25); ctx.lineWidth = Math.max(1.5, R * 0.014); ctx.lineCap = "round";
    ctx.beginPath();
    [-1, -0.35, 0.35, 1].forEach((s) => {
      ctx.moveTo(x + s * 0.22 * R, y + MOUTH * R); ctx.lineTo(x + s * 0.19 * R, y + BASK0 * R + R * 0.02);
    }); ctx.stroke();
    // flame, flickering
    const fl = b.heat * (1 + 0.16 * B.noise1(t * 9, 3)), fy = y + 1.36 * R;
    if (fl > 0.04) {
      B.glow(ctx, x, fy - R * 0.12, R * 0.28 * (0.6 + fl), "#ffb347", 0.35);
      const fh = R * 0.34 * fl, fw = R * 0.075 * (0.7 + 0.5 * fl);
      puff(ctx, { x: x - fw * 1.2, y: fy - fh, w: fw * 2.4, h: fh + fw }, (g) => {
        g.beginPath(); g.moveTo(x, fy - fh);
        g.bezierCurveTo(x + fw * 0.5, fy - fh * 0.55, x + fw * 1.2, fy - fh * 0.2, x + fw, fy - fw * 0.1);
        g.arc(x, fy - fw * 0.1, fw, 0, Math.PI);
        g.bezierCurveTo(x - fw * 1.2, fy - fh * 0.2, x - fw * 0.5, fy - fh * 0.55, x, fy - fh);
        g.fillStyle = B.linear(g, 0, fy - fh, 0, fy, [PAL.butter, "#ffb347", PAL.coral]); g.fill();
      }, { dark: "#c2421f", shadeA: 0.25, rim: "#fff3c4", spec: 0.6 });
    }
    // burner: a small lilac-grey frame
    puff(ctx, { x: x - R * 0.13, y: y + 1.37 * R, w: R * 0.26, h: R * 0.09 }, (g) => {
      g.beginPath(); B.roundRect(g, x - R * 0.13, y + 1.37 * R, R * 0.26, R * 0.09, R * 0.04); g.fillStyle = "#a99cc9";
      g.fill();
    }, { dark: "#3a2d5a", shadeA: 0.4, spec: 0.9 });
    // basket: woven caramel tub, slightly tapered, with a round padded rim
    const bt = y + BASK0 * R, bh = (BASK1 - BASK0) * R, caramel = B.mix(PAL.butter, "#c9814a", 0.55);
    puff(ctx, { x: x - R * 0.23, y: bt, w: R * 0.46, h: bh }, (g) => {
      g.beginPath(); g.moveTo(x - R * 0.22, bt); g.lineTo(x + R * 0.22, bt); g.lineTo(x + R * 0.185, bt + bh - R * 0.05);
      g.quadraticCurveTo(x + R * 0.18, bt + bh, x + R * 0.13, bt + bh); g.lineTo(x - R * 0.13, bt + bh);
      g.quadraticCurveTo(x - R * 0.18, bt + bh, x - R * 0.185, bt + bh - R * 0.05); g.closePath(); g.fillStyle = caramel;
      g.fill(); g.strokeStyle = B.rgba("#7a4320", 0.22); g.lineWidth = R * 0.012;
      for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(x - R * 0.22, bt + bh * i / 4); g.lineTo(x + R * 0.22, bt + bh * i / 4); g.stroke(); }
    }, { dark: "#6b3415", shadeA: 0.4, spec: 0.6 });
    puff(ctx, { x: x - R * 0.25, y: bt - R * 0.035, w: R * 0.5, h: R * 0.07 }, (g) => {
      g.beginPath(); B.capsule(g, x - R * 0.25, bt - R * 0.035, R * 0.5, R * 0.07); g.fillStyle = B.shade(caramel, -0.12);
      g.fill();
    }, { dark: "#5a2a10", shadeA: 0.4 }); ctx.restore();
  }
  /** Rising soft puffs: warm (butter) from the flame into the envelope, or cool (sky) out of the vent. */
  function airPuffs(ctx, t, x, y0, y1, spread, r, col, amt, seed) {
    if (amt <= 0.02) return;
    const rr = B.rng(seed);
    for (let i = 0; i < 7; i++) {
      const ph = B.fract(t / 1.6 + rr()), dx = rr.range(-1, 1) * spread;
      const px = x + dx * (0.4 + ph) + Math.sin(ph * 7 + i) * r * 0.4, py = B.lerp(y0, y1, ph);
      const s = r * (0.6 + 0.6 * ph) * Math.sin(Math.PI * Math.min(1, ph * 1.2)) * amt;
      if (s > 1) ball(ctx, px, py, s, col, { spec: 0.6, shadeA: 0.25, dark: B.shade(col, -0.5) });
    }
  }
  /** Puffy thermometer: cream tube, coral column rising to level p, coral bulb. */
  function thermometer(ctx, x, y, h, p) {
    const w = h * 0.2;
    puff(ctx, { x: x - w / 2, y: y - h, w, h: h * 1.02 }, (g) => {
      g.beginPath(); B.capsule(g, x - w / 2, y - h, w, h); g.fillStyle = PAL.cream; g.fill(); g.beginPath();
      B.capsule(g, x - w * 0.22, y - h * (0.12 + 0.78 * p), w * 0.44, h * (0.12 + 0.78 * p)); g.fillStyle = PAL.coral;
      g.fill();
    }, { dark: "#8f7fc0", shadeA: 0.3 }); ball(ctx, x, y, w * 0.95, PAL.coral);
  }

  // ------------------------------------------------------------------ layout by aspect
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait, S = F.safe;
    const floorY = P ? H * 0.8 : H * 0.83, cY = floorY + (H - floorY) * (P ? 0.36 : 0.4);
    const landed = (x, R) => [x, cY - BASK1 * R, R];
    const col = P ? W / 2 : W * 0.34; // the text column
    const L = { F, u, P, S, W, H, floorY, cY, col, lab: P ? 4.5 * u : 4.3 * u };
    // balloon keyframes [time, x, y (envelope centre), R]
    const k = P
      ? { title: landed(W / 2, 24 * u), diag: [W / 2, H * 0.415, 28 * u], key: landed(W / 2, 21 * u), low: landed(W / 2, 22 * u), high: [W / 2, H * 0.5, 22 * u], close: [W / 2, H * 0.56, 22 * u] }
      : { title: landed(W * 0.72, 15 * u), diag: [W * 0.5, H * 0.36, 19 * u], key: landed(W * 0.76, 16 * u), low: landed(W * 0.75, 16 * u), high: [W * 0.75, H * 0.34, 16 * u], close: [W * 0.73, H * 0.4, 17 * u] };
    L.keys = [[0, ...k.title], [2.0, ...k.title], [2.65, ...k.diag], [4.15, ...k.diag], [4.75, ...k.key], [6.4, ...k.key], [6.41, ...k.low], [7.35, ...k.low], [8.2, ...k.high], [9.0, ...k.high], [10.0, ...k.low], [10.45, ...k.low], [11.15, ...k.close], [12, ...k.close]];
    L.lands = [0.62, 2.65, 4.75, 8.2, 10.0, 11.15]; L.title = P ? [W / 2, H * 0.22] : [col, H * 0.4];
    L.headSize = P ? 17 * u : 14 * u; L.num = P ? [W / 2, H * 0.26] : [col, H * 0.34]; L.numSize = P ? 22 * u : 21 * u;
    L.therm = P ? [W * 0.17, H * 0.66, 15 * u] : [W * 0.6, H * 0.6, 17 * u];
    L.steps = P ? [H * 0.185, H * 0.25, H * 0.315].map((y) => [W / 2, y]) : [H * 0.3, H * 0.47, H * 0.64].map((y) => [col, y]);
    L.close = P ? [[W / 2, H * 0.19], [W / 2, H * 0.29], [W / 2, H * 0.38]] : [[col, H * 0.3], [col, H * 0.47], [col, H * 0.65]];
    // floating props: [x, y, size, kind]
    L.props = P
      ? [[W * 0.16, H * 0.43, 9 * u, "cloud"], [W * 0.86, H * 0.47, 7 * u, "cloud"], [W * 0.85, H * 0.36, 2.6 * u, "ball"], [W * 0.12, H * 0.56, 2 * u, "ball2"], [W * 0.82, H * 0.6, 3 * u, "spark"], [W * 0.22, H * 0.36, 2.4 * u, "spark"]]
      : [[W * 0.12, H * 0.2, 6 * u, "cloud"], [W * 0.93, H * 0.22, 5 * u, "cloud"], [W * 0.56, H * 0.17, 2.2 * u, "ball"], [W * 0.95, H * 0.62, 1.8 * u, "ball2"], [W * 0.6, H * 0.8, 2.6 * u, "spark"], [W * 0.07, H * 0.7, 2.2 * u, "spark"]];
    return L;
  }

  // ------------------------------------------------------------------ the balloon's state over time
  function balloonAt(t, L) {
    const K = L.keys;
    let i = 0;
    while (i < K.length - 2 && t >= K[i + 1][0]) i++;
    const a = K[i], c = K[i + 1], p = B.ease.inOutCubic(B.clamp((t - a[0]) / Math.max(1e-6, c[0] - a[0])));
    let x = B.lerp(a[1], c[1], p), y = B.lerp(a[2], c[2], p), R = B.lerp(a[3], c[3], p);
    // the title drop: falls in from above and lands with a squash
    if (t < 0.62) y -= (1 - B.ease.inQuad(B.prog(t, 0.05, 0.57))) * L.H * 0.55;
    const landedY = L.cY - BASK1 * R, lift = B.clamp((landedY - y) / (L.H * 0.35));
    if (lift > 0.02) y += B.bob(t, L.u * 0.9, 3.4) * Math.min(1, lift * 4);
    let q = [1, 1];
    for (const at of L.lands) { const s = squashAt(t, at, 0.075); q = [q[0] * s[0], q[1] * s[1]]; }
    const heat = B.clamp(0.22 + 0.55 * B.alive(t, 2.5, 4.1) + 0.2 * B.alive(t, 4.3, 6.3) + 0.78 * B.alive(t, 6.9, 8.6, 0.25, 0.4) - 0.17 * B.alive(t, 8.7, 10.2) + 0.25 * B.alive(t, 10.6, 12.2));
    return { x, y, R, q, lift, heat, vent: B.alive(t, 8.95, 10.05, 0.25, 0.35), rot: t * 0.32 };
  }

  // ------------------------------------------------------------------ backdrop: pastel studio sweep
  function sweep(ctx, L, col, alpha) {
    if (alpha <= 0.002) return;
    const { W, H, floorY } = L, f = floorY / H;
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.fillStyle = B.linear(ctx, 0, 0, 0, H, [[0, B.shade(col, -0.07)], [f - 0.12, B.shade(col, 0.06)], [f, B.shade(col, 0.22)], [Math.min(1, f + 0.08), B.shade(col, 0.12)], [1, B.shade(col, -0.06)]]);
    ctx.fillRect(0, 0, W, H); ctx.restore();
  }
  function backdrop(ctx, L, t) {
    const { W, H } = L;
    let i = 0;
    while (i < BEATS.length - 1 && t >= BEATS[i + 1]) i++; sweep(ctx, L, BG[i], 1);
    if (i > 0 && i !== 3) sweep(ctx, L, BG[i - 1], 1 - B.span(t, BEATS[i], BEATS[i] + 0.55, "inOutSine")); // beat 3 is uncovered by the cloud wipe
    // key light pool from the upper left and a soft spot on the floor
    B.glow(ctx, W * 0.2, H * 0.12, Math.hypot(W, H) * 0.55, "#ffffff", 0.22);
    B.contactShadow(ctx, W * 0.55, L.cY, W * 0.5, (H - L.floorY) * 0.45, 0.25, "#ffffff");
  }
  function props(ctx, L, t, fade) {
    if (fade <= 0.01) return;
    L.props.forEach(([x, y, s, kind], i) => {
      const bx = x + B.bob(t, L.u * 0.8, 4.4, i * 0.17), by = y + B.bob(t, L.u * 1.4, 3.1, i * 0.29);
      ctx.save(); ctx.translate(bx, by); ctx.scale(fade, fade); if (kind === "cloud") cloud(ctx, 0, 0, s);
      else if (kind === "ball") ball(ctx, 0, 0, s, B.shade(PAL.lilac, -0.12));
      else if (kind === "ball2") ball(ctx, 0, 0, s, B.shade(PAL.mint, -0.15));
      else sparkle(ctx, 0, 0, s, 0.55 + 0.45 * Math.max(0, Math.sin(B.TAU * (t / 1.7 + i * 0.3)))); ctx.restore();
    });
  }

  // ------------------------------------------------------------------ overlays per beat
  function overlays(ctx, L, t, b) {
    const { u, P, S, W, H, lab } = L;
    // beat 1: title - chubby 3D letters spring in one by one, a pill under them
    if (t < 2.1) {
      const [tx, ty] = L.title;
      text3d(ctx, "Hot air", tx, ty, L.headSize, PAL.coral, letterAnim(t, 0.35, 0.07, 1.72));
      pill(ctx, tx, ty + L.headSize * (P ? 0.95 : 1.05), "How a balloon flies", lab * 1.05, life(t, 0.95, 1.98));
    }
    // beat 2: labelled diagram with a fat 3D arrow of hot air rising from the burner
    if (t > 2.4 && t < 4.3) {
      const { x, y, R } = b, out = 4.18;
      const pts = B.cubic(x, y + 1.3 * R, x + R * 0.16, y + 0.8 * R, x - R * 0.16, y + 0.1 * R, x, y - 0.6 * R);
      arrow3d(ctx, pts, B.prog(t, 2.75, 0.8, "outCubic") * (1 - B.span(t, 4.0, 4.2)), R * 0.13, PAL.butter);
      const items = P
        ? [["Envelope", [S.x + pillW(ctx, "Envelope", lab) / 2, y - 0.98 * R], [x - 0.5 * R, y - 0.62 * R], 2.85],
           ["Hot air rises", [S.r - pillW(ctx, "Hot air rises", lab) / 2, y - 0.1 * R], [x + 0.1 * R, y + 0.05 * R], 3.15],
           ["Burner", [x + 0.68 * R, y + 1.27 * R], [x + 0.12 * R, y + 1.38 * R], 3.4],
           ["Basket", [x - 0.68 * R, y + 1.72 * R], [x - 0.2 * R, y + 1.68 * R], 3.6]]
        : [["Envelope", [x - 1.75 * R, y - 0.62 * R], [x - 0.78 * R, y - 0.45 * R], 2.85],
           ["Hot air rises", [x + 1.95 * R, y - 0.1 * R], [x + 0.1 * R, y + 0.05 * R], 3.15],
           ["Burner", [x + 1.4 * R, y + 1.33 * R], [x + 0.12 * R, y + 1.38 * R], 3.4],
           ["Basket", [x - 1.4 * R, y + 1.7 * R], [x - 0.2 * R, y + 1.68 * R], 3.6]];
      items.forEach(([txt, at, to, t0]) => {
        const s = life(t, t0, out);
        leader(ctx, at, to, B.prog(t, t0 + 0.1, 0.35, "outCubic") * Math.min(1, s), u);
        pill(ctx, at[0], at[1], txt, lab, s);
      });
    }
    // beat 3: key number - chubby digits stepping up 20 -> 100, each new value springs in
    if (t > 4.3 && t < 6.45) {
      const [nx, ny] = L.num, vals = [20, 40, 60, 80, 100], step = Math.min(4, Math.floor(B.clamp((t - 4.55) / 0.2) * 4.999));
      const changed = 4.55 + step * 0.2, out = 6.05;
      const sIn = t < 4.55 ? 0 : 1, ex = 1 - Math.max(0, B.ease.inBack(B.prog(t, out, 0.3)));
      const sq = squashAt(t, changed, step === 4 ? 0.16 : 0.08);
      ctx.save(); ctx.translate(nx, ny);
      ctx.scale(sIn * Math.max(0, ex) * (0.9 + 0.1 * B.pop(t, changed, 0.3, 3)), sIn * Math.max(0, ex) * (0.9 + 0.1 * B.pop(t, changed, 0.3, 3)));
      if (step === 4) B.glow(ctx, 0, 0, L.numSize * 1.6, PAL.butter, 0.4 * (1 + 0.15 * B.wave(t, 1.4)), { add: true });
      text3d(ctx, vals[step] + "°C", 0, 0, L.numSize, step === 4 ? PAL.coral : B.mix(PAL.butter, PAL.coral, step / 4), { squash: () => sq });
      ctx.restore();
      const py = ny + L.numSize * (P ? 0.92 : 0.98);
      pill(ctx, nx, py, "Air inside the envelope", lab, life(t, 5.0, out + 0.3));
      pill(ctx, nx, py + lab * 2.7, "A fifth lighter than cool air", lab * 0.98, life(t, 5.35, out + 0.3), { fill: "#fff3d6" });
      const [hx, hy, hh] = L.therm, ts = life(t, 4.5, out + 0.3);
      if (ts > 0.01) {
        ctx.save(); ctx.translate(hx, hy); ctx.scale(ts, ts);
        thermometer(ctx, 0, 0, hh, 0.15 + 0.8 * B.ease.outCubic(B.prog(t, 4.55, 0.9))); ctx.restore();
      }
    }
    // beats 4-5: three numbered steps
    if (t > 6.5 && t < 10.45) {
      const steps = [["Burner heats the air", PAL.coral, 6.75], ["Light air lifts it up", B.shade(PAL.butter, -0.1), 7.45], ["Let it cool to land", "#7fb6ee", 8.75]];
      steps.forEach(([txt, c, t0], i) => {
        const [sx, sy] = L.steps[i];
        const dim = i < 2 ? 1 - 0.4 * B.span(t, 8.7, 9.0) : 1; // done steps step back a little
        ctx.save(); ctx.globalAlpha = dim; pill(ctx, sx, sy, txt, lab, life(t, t0, 10.3), { num: String(i + 1), color: c });
        ctx.restore();
      });
    }
    // beat 6: close
    if (t > 10.6) {
      const [a, c, d] = L.close;
      text3d(ctx, "Warm air", a[0], a[1], L.headSize * 0.86, PAL.coral, letterAnim(t, 10.7, 0.06));
      text3d(ctx, "lifts!", c[0], c[1], L.headSize * 0.86, B.shade(PAL.butter, -0.14), letterAnim(t, 11.05, 0.07));
      pill(ctx, d[0], d[1], "Cool it to come down", lab, life(t, 11.35));
      [[-1, 0.3], [1, 0.8]].forEach(([side, ph], i) => { // two hearts float up beside the balloon
        const hs = life(t, 11.2 + i * 0.25) * (P ? 3.4 : 2.6) * u, hy = b.y - b.R * (0.2 + 0.25 * B.fract((t - 11.2) / 3 + ph));
        if (hs > 0.5) heart(ctx, b.x + side * b.R * 1.25 + B.bob(t, u, 1.8, ph), hy, hs);
      });
    }
  }

  // ------------------------------------------------------------------ transitions
  /** A puffy cloud bank sweeping right to left over the whole frame; the scene swaps while it covers it. */
  function cloudWipe(ctx, L, t, at) {
    const p = B.span(t, at - 0.42, at + 0.42, "inOutCubic");
    if (p <= 0 || p >= 1) return;
    const { W, H } = L, bw = W * 1.7, x0 = B.lerp(W * 1.05, -bw - W * 0.05, p);
    const rr = Math.max(W, H) * 0.16;
    puff(ctx, { x: x0 - rr, y: -rr * 0.3, w: bw + 2 * rr, h: H + rr * 0.6 }, (g) => {
      g.beginPath(); g.rect(x0, -rr, bw, H + 2 * rr);
      for (let k = 0; k <= 7; k++) {
        const yy = (k / 7) * H;
        B.circle(g, x0 + B.hash01(k, 1) * rr * 0.3, yy, rr * (0.8 + 0.4 * B.hash01(k, 2)));
        B.circle(g, x0 + bw - B.hash01(k, 3) * rr * 0.3, yy, rr * (0.8 + 0.4 * B.hash01(k, 4)));
      }
      g.fillStyle = PAL.cream; g.fill();
    }, { dark: "#9a8bd0", shadeA: 0.3, spec: 0.4 });
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H), b = balloonAt(t, L);
    backdrop(ctx, L, t); props(ctx, L, t, life(t, 0.5)); floorShadow(ctx, b.x, L.cY, b.R * 0.3 * b.q[0], b.lift, L.u);
    // hot air rising inside while the burner works, cool air out of the vent in step 3
    balloon(ctx, b, t);
    airPuffs(ctx, t, b.x, b.y + 1.0 * b.R, b.y - 0.3 * b.R, b.R * 0.25, b.R * 0.07, PAL.butter, B.alive(t, 6.9, 8.5, 0.3, 0.4) * 0.9, "warm");
    airPuffs(ctx, t, b.x, b.y - TOP * b.R - b.R * 0.1, b.y - TOP * b.R - b.R * 0.75, b.R * 0.2, b.R * 0.08, "#a9d2ff", b.vent, "cool");
    overlays(ctx, L, t, b); cloudWipe(ctx, L, t, BEATS[3]);
    // finishing: a soft warm vignette and very light grain so the gradients never band
    B.vignette(ctx, W, H, { color: PAL.plum, amount: 0.12, inner: 0.55 }); B.grain(ctx, W, H, { amount: 0.035, t });
  }

  // ------------------------------------------------------------------ sound: soft boops, bubbly pops, marimba, a cosy pad
  SOUND.define("s3d-boing", (v, o) => { // a springy rubbery boing for squash landings
    const f = v.hz(o.note || "C4");
    const tn = v.tone({ type: "sine", f: f * 0.8, f2: f * 1.25, glide: 0.08, a: 0.004, len: 0.32, peak: 0.32 });
    v.lfo(tn.osc.frequency, 14, f * 0.06, v.t + 0.4);
    v.tone({ type: "triangle", f: f * 2, f2: f * 2.5, glide: 0.06, a: 0.002, len: 0.12, peak: 0.06 });
  }, { verb: 0.25 });
  SOUND.define("s3d-burner", (v, o) => { // a soft round roar of the burner, cosy not harsh
    const d = o.dur ?? 1.2;
    v.noise({ brown: true, filter: "lowpass", f: 260, f2: 520, glide: d * 0.4, a: 0.12, hold: d * 0.55, len: d * 0.4, peak: 0.3 });
    v.noise({ filter: "bandpass", f: 900, q: 0.7, a: 0.08, hold: d * 0.5, len: d * 0.4, peak: 0.05 });
  }, { verb: 0.2 });

  function score(k) {
    const sc = SOUND.scale("F3", "major", 12), at = (t, n, o) => k.at(t, n, o);
    k.bed("pad", 0, DUR, { notes: ["F2", "C3", "A3", "E4"], gain: 0.5, bright: 520 });
    // title: the balloon drops in and boings, the letters bubble-pop in one by one
    at(0.05, "fall", { dur: 0.5, gain: 0.35 }); at(0.62, "s3d-boing", { note: "F3", gain: 0.9 }); at(0.62, "thud", { gain: 0.3 });
    [0, 1, 2, 4, 5, 6].forEach((i) => { at(0.35 + i * 0.07, "bubble", { gain: 0.35, pitch: i * 2 }); at(0.4 + i * 0.07, "marimba", { note: sc[i + 2], gain: 0.4 }); });
    at(0.95, "pop", { gain: 0.6 }); at(1.72, "swish", { dur: 0.4, gain: 0.4 });
    // diagram: lift-off, the arrow grows on a riser, labels boop up the scale
    at(2.0, "breath", { dur: 0.7, gain: 0.5 }); at(2.5, "s3d-burner", { dur: 1.2, gain: 0.6 }); at(2.65, "s3d-boing", { note: "A3", gain: 0.6 });
    at(2.75, "riser", { dur: 0.8, gain: 0.35 }); at(4.0, "swish", { dur: 0.4, gain: 0.4 });
    [2.85, 3.15, 3.4, 3.6].forEach((t, i) => { at(t, "boop", { pitch: i * 2, pan: [-0.4, 0.4, 0.3, -0.3][i], gain: 0.7 }); at(t, "marimba", { note: sc[4 + i], gain: 0.5 }); });
    // key number: a marimba climb 20 -> 100, then a big boing and a bright chord
    at(4.3, "pop", { gain: 0.5 }); at(4.75, "s3d-boing", { note: "C3", gain: 0.5 });
    [0, 1, 2, 3].forEach((i) => { at(4.55 + i * 0.2, "marimba", { note: sc[i * 2], gain: 0.55 }); at(4.55 + i * 0.2, "tick", { gain: 0.3 }); });
    at(5.0, "pop", { gain: 0.5, pan: -0.2 }); at(5.35, "s3d-boing", { note: "F4", gain: 0.8 }); at(5.35, "chord", { notes: ["F4", "A4", "C5", "F5"], gain: 0.7 });
    at(5.35, "sparkle", { gain: 0.4 }); at(6.0, "whoosh", { dur: 0.8, gain: 0.55 }); // the cloud wipe
    // steps: burner roar and bubbles, the lift, the vent breathing out, a soft landing
    [[6.75, 0, 4], [7.45, 2, 6], [8.75, 4, 8]].forEach(([t, p, n]) => { at(t, "boop", { pitch: p, gain: 0.7 }); at(t, "marimba", { note: sc[n], gain: 0.5 }); });
    at(6.9, "s3d-burner", { dur: 1.6, gain: 0.9 }); k.repeat(7.0, 0.22, 6, "bubble", { gain: 0.2, vary: 3, pitch: 2, jitter: 0.03 });
    at(7.35, "swell", { dur: 0.85, gain: 0.4 }); at(8.2, "s3d-boing", { note: "C4", gain: 0.5 }); at(8.95, "breath", { dur: 1.0, gain: 0.45 });
    k.repeat(9.05, 0.18, 6, "bubble", { gain: 0.25, vary: 3, pitch: -3, jitter: 0.03 });
    at(9.2, "fall", { dur: 0.8, gain: 0.2 }); at(10.0, "s3d-boing", { note: "F3", gain: 0.8 }); at(10.0, "thud", { gain: 0.25 });
    // close: lift-off, letters pop, a warm chord and a chime
    at(10.45, "swell", { dur: 0.7, gain: 0.35 }); at(11.15, "s3d-boing", { note: "A3", gain: 0.5 });
    for (let i = 0; i < 6; i++) { at(10.7 + i * 0.06, "bubble", { gain: 0.3, pitch: i * 2 }); at(11.05 + i * 0.07, "marimba", { note: sc[i + 4], gain: 0.4 }); }
    at(11.35, "pop", { gain: 0.6 }); at(11.4, "chord", { notes: ["F4", "A4", "C5", "E5"], strum: 0.05, gain: 0.65 }); at(11.5, "chime", { note: "C6", gain: 0.45 });
  }

  Player.register({
    id: "soft-3d",
    name: "Soft 3D Clay",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@700;800;900&display=swap",
      faces: ['700 20px "Fredoka"', '600 20px "Fredoka"', '800 20px "Nunito"', '900 20px "Nunito"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.55, 3.85, 5.9, 8.3, 9.6, 11.85],
    draw,
    score,
  });
})();
