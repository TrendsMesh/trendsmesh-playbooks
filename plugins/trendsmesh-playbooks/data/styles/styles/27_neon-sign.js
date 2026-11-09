/* 27 Neon Sign - reference animation.
 * Topic (setting, replace it): "How does a neon sign glow?" - gas, glass and high voltage.
 * Rendering (keep it): a long wall of near-black bricks at night, one sign per point, the view whip-panning along it.
 * Every drawn thing is one bent glass tube: a white-hot core, a tinted colour band and a soft halo; unlit glass and
 * painted-out runs are dull grey; clips, end caps and cables hold it to the wall. The tubes are drawn three times:
 * dull glass (always), a colour copy blurred twice (small and wide) and added over the wall, then the crisp band and
 * core. The same light, blurred wider and multiplied by the brick texture, washes the wall; a wet pavement strip
 * mirrors everything, blurred and rippling, with drops landing in it.
 * Motion: tubes ignite with a stuttering buzz (dark, weak flash, dark, full); one letter keeps failing; a compared
 * value buzzes on below the first; chase-light arrows; whip pans with blur and an overshoot.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { brick: "#1a0f14", mortar: "#2c1c22", pink: "#ff3d9a", cyan: "#35e6ff", amber: "#ffb347", red: "#ff2a2a", core: "#fff8f0" };
  const SANS = "Poiret One", SCRIPT = "Gloria Hallelujah";
  const DUR = 13.5;
  const BEATS = [0, 2.2, 4.8, 7.0, 9.6, 11.5];
  const PANS = [2.2, 4.8, 7.0, 8.3, 9.6, 11.5]; // the view moves to sign i + 1 at PANS[i]
  const GLASS = "#2e2529", PAINT = "#1c1518";

  // ------------------------------------------------------------------ neon helpers (reuse these)
  let U = 1, MODE = "crisp", T = 0;
  /**
   * Ignition with a stuttering buzz: dark, a weak flash, dark, a stronger flash, then full light with a slight hum.
   * Returns brightness 0..1 for a tube switched on at `at` (and off again at `off`, snapping dark like a relay).
   */
  function ignite(t, at, off = 1e9, seed = 0) {
    if (t < at || t >= off) return 0;
    const d = t - at;
    const b = d < 0.05 ? 0.35 : d < 0.12 ? 0 : d < 0.17 ? 0.75 : d < 0.22 ? 0.08 : 1;
    return b * (1 + 0.035 * B.noise1(t * 9, seed));
  }
  /** A letter that keeps failing: mostly lit, dropping out in short random bursts. */
  function failing(t, seed) {
    const f = Math.floor(t * 14), r = B.hash01("fail", f, seed), r2 = B.hash01("fail", Math.floor(t * 2.3), seed);
    return r2 < 0.45 && r < 0.6 ? (r < 0.25 ? 0.05 : 0.35) : 1;
  }
  /**
   * One glass tube along pts in colour col at brightness b. In "glass" mode: the dull tube (and "painted-out" runs);
   * "glow": the colour copy that gets blurred and added; "crisp": the colour band and the white-hot core.
   */
  function tube(g, pts, col, b, o = {}) {
    const tw = (o.w ?? 1.1) * U;
    g.save();
    g.lineCap = "round";
    g.lineJoin = "round";
    g.beginPath();
    B.poly(g, pts, o.closed);
    if (o.closed) g.closePath();
    if (MODE === "glass") {
      g.strokeStyle = o.painted ? PAINT : GLASS;
      g.lineWidth = tw * (o.painted ? 1.15 : 1);
      g.stroke();
      g.strokeStyle = "rgba(255,255,255,0.08)";
      g.lineWidth = tw * 0.3;
      g.stroke();
    } else if (b > 0 && !o.painted) {
      if (MODE === "glow") {
        g.globalAlpha = Math.min(1, b);
        g.strokeStyle = col;
        g.lineWidth = tw * 2.4;
        g.stroke();
      } else {
        g.globalAlpha = Math.min(1, b);
        g.strokeStyle = B.mix(col, PAL.core, 0.15);
        g.lineWidth = tw * 1.15;
        g.stroke();
        g.strokeStyle = PAL.core;
        g.lineWidth = tw * 0.42;
        g.stroke();
      }
    }
    g.restore();
  }
  /**
   * Neon lettering, one glyph at a time so each letter can ignite or fail on its own. bright(i) -> 0..1.
   * The font's own thin strokes are the glass: tinted rim around them, a narrower white core inside.
   */
  function tubeText(g, str, x, y, size, family, col, bright, o = {}) {
    g.save();
    g.font = B.font(size, family, 400);
    g.textBaseline = "middle";
    g.textAlign = "left";
    const ls = (o.spacing ?? 0.04) * size, chars = [...str];
    const ws = chars.map((c) => g.measureText(c).width), total = ws.reduce((a, b) => a + b, 0) + ls * (chars.length - 1);
    const x0 = o.align === "left" ? x : x - total / 2, xs = [];
    chars.reduce((acc, c, i) => (xs.push(acc), acc + ws[i] + ls), x0);
    if (o.joins && MODE === "glass") {
      // painted-out glass: the one tube runs on along the baseline into the next letter, painted out so it does
      // not light: dull grey glass, as thin as the letters, that the signs' light washes over like the wall
      g.lineCap = "round";
      chars.forEach((c, i) => {
        if (c === " " || i === chars.length - 1 || chars[i + 1] === " ") return;
        const a = xs[i] + ws[i] * 0.9, e = xs[i + 1] + ws[i + 1] * 0.1, yb = y + size * 0.2;
        g.beginPath();
        g.moveTo(a, yb);
        g.quadraticCurveTo((a + e) / 2, yb + size * 0.03, e, yb);
        g.strokeStyle = "#3d3438";
        g.lineWidth = size * (o.w ?? 1) * 0.05;
        g.stroke();
        g.strokeStyle = "rgba(255,240,235,0.16)";
        g.lineWidth = size * 0.014;
        g.stroke();
      });
    }
    chars.forEach((c, i) => {
      const b = typeof bright === "function" ? bright(i) : bright, xx = xs[i];
      if (c === " ") return;
      if (MODE === "glass") {
        g.fillStyle = GLASS;
        g.fillText(c, xx, y);
      } else if (b > 0) {
        g.globalAlpha = Math.min(1, b);
        g.fillStyle = g.strokeStyle = MODE === "glow" ? col : B.mix(col, PAL.core, 0.15);
        g.lineJoin = "round";
        const wk = o.w ?? 1; // tube weight: numerals and small type use a heavier tube so they glow as bright
        g.lineWidth = size * (MODE === "glow" ? 0.12 : 0.07) * wk;
        g.strokeText(c, xx, y);
        g.fillText(c, xx, y);
        if (MODE === "crisp") {
          g.fillStyle = PAL.core;
          g.fillText(c, xx, y);
          // the white-hot core: a heavier tube gets a thicker core line; a light one a thin tinted rim
          g.strokeStyle = wk > 1 ? PAL.core : B.mix(col, PAL.core, 0.3);
          g.lineWidth = size * (wk > 1 ? 0.018 * wk : 0.03);
          g.strokeText(c, xx, y);
        }
      }
    });
    g.restore();
    return { x0, w: total };
  }
  function tubeWidth(g, str, size) {
    g.save();
    g.font = B.font(size, SCRIPT, 400);
    const w = [...str].reduce((a, c) => a + g.measureText(c).width + 0.04 * size, -0.04 * size);
    g.restore();
    return w;
  }
  /** Metal clips holding a tube to the bricks, with a short cast shadow (glass mode only). */
  function clips(g, pts) {
    if (MODE !== "glass") return;
    for (const [x, y] of pts) {
      g.fillStyle = "rgba(0,0,0,0.6)";
      g.fillRect(x - 0.5 * U, y + 0.2 * U, 1.4 * U, 2.2 * U);
      g.fillStyle = "#6d6468";
      g.fillRect(x - 0.7 * U, y - 0.9 * U, 1.4 * U, 1.8 * U);
      g.fillStyle = "#a59ca0";
      g.fillRect(x - 0.7 * U, y - 0.9 * U, 1.4 * U, 0.4 * U);
    }
  }
  /** Electrode end cap plus the cable running off it (glass mode only). */
  function endCap(g, x, y, dx, dy, cable) {
    if (MODE !== "glass") return;
    g.save();
    g.lineCap = "round";
    g.strokeStyle = "#0a0809";
    g.lineWidth = 2.4 * U;
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x + dx * 2.4 * U, y + dy * 2.4 * U);
    g.stroke();
    if (cable) {
      g.strokeStyle = "#050405";
      g.lineWidth = 0.6 * U;
      g.beginPath();
      g.moveTo(x + dx * 2.4 * U, y + dy * 2.4 * U);
      g.quadraticCurveTo(cable[0], y + dy * 6 * U, cable[0], cable[1]);
      g.stroke();
    }
    g.restore();
  }
  /** Matt black backing plate with a thin lit outline tube. */
  function plate(g, x, y, w, h, col, b) {
    if (MODE === "crisp") {
      g.fillStyle = "rgba(10,8,9,0.72)"; // the matt black plate in front of the wall: the brick's light wash stops at it
      g.fillRect(x + 0.6 * U, y + 0.6 * U, w - 1.2 * U, h - 1.2 * U);
    }
    if (MODE === "glass") {
      B.withShadow(g, { color: "rgba(0,0,0,0.8)", blur: 3 * U, x: U, y: 1.5 * U }, () => {
        g.fillStyle = "#0d0b0c";
        g.fillRect(x, y, w, h);
      });
    }
    const i = 1.4 * U;
    tube(g, [[x + i, y + i], [x + w - i, y + i], [x + w - i, y + h - i], [x + i, y + h - i]], col, b, { closed: true, w: 0.6 });
  }
  /** Chase-light arrow: short tube segments lighting one after another toward the target, a two-segment head. */
  function chaseArrow(g, pts, col, p, t) {
    const dense = B.densify(pts, U), L = B.pathLength(dense), seg = 2.6 * U, n = Math.max(2, Math.floor(L / seg));
    for (let i = 0; i < n; i++) {
      const a = i / n, b = (i + 0.62) / n;
      const lit = p * n > i ? 0.4 + 0.6 * (B.fract(i / 5 - t * 2.2) < 0.4 ? 1 : 0) : 0;
      tube(g, B.trim(dense, a, b), col, lit, { w: 0.8 });
    }
    const tip = B.pointAt(dense, 1), an = tip[2], hl = 3 * U, hb = p >= 1 ? 1 : 0;
    for (const s of [-1, 1]) tube(g, [[tip[0] - Math.cos(an + s * 0.6) * hl, tip[1] - Math.sin(an + s * 0.6) * hl], [tip[0], tip[1]]], col, hb, { w: 0.8 });
  }
  /** Ring of short rays around a point (emphasis burst), each its own tube. */
  function rays(g, x, y, r1, r2, n, col, b) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU + 0.2;
      tube(g, [[x + Math.cos(a) * r1, y + Math.sin(a) * r1], [x + Math.cos(a) * r2, y + Math.sin(a) * r2]], col, b, { w: 0.8 });
    }
  }

  // ------------------------------------------------------------------ the wall, its light wash and the wet pavement
  function brickTile(W, H, albedo) {
    return B.layer("neon-bricks:" + albedo, W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, bh = 3.4 * u, bw = w / Math.round(w / (9.6 * u)), r = B.rng(27); // whole bricks per tile: no seam
      g.fillStyle = albedo ? "#3c3537" : PAL.mortar;
      g.fillRect(0, 0, w, h);
      for (let row = 0, y = 0; y < h; row++, y += bh) {
        for (let x = -(row % 2) * bw * 0.5; x < w; x += bw) {
          const v = r.range(-1, 1), k = r();
          g.fillStyle = albedo ? B.shade("#a4979a", v * 0.18) : B.mix(PAL.brick, k < 0.15 ? "#2a1820" : "#130a0e", r() * 0.6);
          g.fillRect(x + 0.35 * u, y + 0.35 * u, bw - 0.7 * u, bh - 0.7 * u);
          g.fillStyle = albedo ? "rgba(0,0,0,0.25)" : "rgba(0,0,0,0.3)";
          g.fillRect(x + 0.35 * u, y + bh - 0.9 * u, bw - 0.7 * u, 0.55 * u);
        }
      }
      B.mottle(g, w, h, { amount: albedo ? 0.25 : 0.2, feature: 0.05, seed: albedo ? 3 : 4, mode: "overlay" });
      B.grain(g, w, h, { amount: 0.12, seed: 9, mode: "overlay" });
    });
  }
  function wallTiles(g, W, H, camX, albedo, hor) {
    const tile = brickTile(W, H, albedo), off = -(((camX % W) + W) % W);
    g.save();
    g.beginPath();
    g.rect(0, 0, W, hor);
    g.clip();
    for (const k of [0, 1]) g.drawImage(tile, off + k * W, 0);
    g.restore();
  }

  // ------------------------------------------------------------------ subjects: the signs (the setting: replace these)
  // each sign is drawn in its own screen-sized space; `a` = the time the view arrives on it
  function layout(W, H) {
    const F = B.frame(W, H), P = F.portrait, S = F.safe;
    const hor = P ? H * 0.79 : H * 0.83;
    return { F, P, S, W, H, hor, cx: W / 2, cy: P ? S.y + (hor - S.y) * 0.45 : S.y + (hor - S.y) * 0.48, u: F.u };
  }
  const SIGNS = [
    // 0 title: "how a / NEON SIGN / glows", one letter failing all through
    (g, t, L) => {
      const P = L.P, u = L.u, big = P ? Math.min(19 * u, L.S.w / 3.4) : 15 * u;
      tubeText(g, "how a", L.cx - (P ? 18 : 30) * u, L.cy - (P ? big * 1.5 : big * 0.95), (P ? 8 : 6.5) * u, SCRIPT, PAL.amber, ignite(t, 0.15, 1e9, 1), { joins: true });
      const lines = P ? ["NEON", "SIGN"] : ["NEON SIGN"];
      lines.forEach((ln, li) => {
        const y = L.cy + (P ? (li - 0.5) * big * 1.08 : 0);
        tubeText(g, ln, L.cx, y, big, SANS, PAL.pink, (i) => ignite(t, 0.45 + (li * 4 + i) * 0.07, 1e9, i) * (ln === "SIGN" && i === 2 ? failing(t, 7) : 1), { spacing: 0.08 });
        clips(g, [[L.cx - big * 1.2, y + big * 0.45], [L.cx + big * 1.1, y + big * 0.45]]);
      });
      tubeText(g, "glows", L.cx + (P ? 12 : 26) * u, L.cy + (P ? big * 1.55 : big * 0.95), (P ? 9 : 7.5) * u, SCRIPT, PAL.cyan, ignite(t, 1.25, 1e9, 3), { joins: true });
    },
    // 1 diagram: a tube with electrodes, a transformer, labels and chase arrows
    (g, t, L) => {
      const P = L.P, u = L.u, a = PANS[0] + 0.3, S = L.S;
      const x0 = S.x + (P ? 6 : 10) * u, x1 = S.r - (P ? 6 : 10) * u, yT = L.cy - (P ? 6 : 4) * u, dn = (P ? 10 : 8) * u;
      const path = [[x0, yT + dn], ...B.arcPts(x0 + 3 * u, yT + 3 * u, 3 * u, Math.PI, Math.PI * 1.5, 6), ...B.arcPts(x1 - 3 * u, yT + 3 * u, 3 * u, -Math.PI / 2, 0, 6), [x1, yT + dn]];
      const on = ignite(t, a + 0.15, 1e9, 11);
      tube(g, path, PAL.red, on, { w: 1.4 });
      clips(g, [[L.cx - 20 * u, yT], [L.cx + 20 * u, yT]]);
      // the transformer sits under the tube; a cable runs from it to the electrode at each end of the tube, and
      // chase lights run along both cables: the high voltage reaching the gas
      const tb = [L.cx, yT + (P ? 44 : 30) * u], bw = (P ? 46 : 40) * u, capY = yT + dn + 2.4 * u;
      endCap(g, x0, yT + dn, 0, 1);
      endCap(g, x1, yT + dn, 0, 1);
      const cable = (s) => B.quad(L.cx + s * bw / 2, tb[1], L.cx + s * (L.cx - x0), tb[1], L.cx + s * (L.cx - x0), capY, 14);
      if (MODE === "glass") for (const sd of [-1, 1]) {
        g.save();
        g.lineCap = "round";
        g.beginPath();
        B.poly(g, cable(sd));
        g.strokeStyle = "#4a4045";
        g.lineWidth = 0.9 * u;
        g.stroke();
        g.restore();
      }
      for (const sd of [-1, 1]) chaseArrow(g, cable(sd), PAL.amber, B.prog(t, a + 1.0, 0.45), t);
      plate(g, tb[0] - bw / 2, tb[1] - 5 * u, bw, 10 * u, PAL.amber, ignite(t, a + 0.9, 1e9, 12) * 0.8);
      const ls = (P ? 5.8 : 5) * u;
      tubeText(g, "glass tube + neon gas", L.cx, yT - (P ? 9 : 7) * u, ls * 1.1, SCRIPT, PAL.cyan, ignite(t, a + 0.45, 1e9, 13), { joins: true });
      tubeText(g, "transformer", tb[0], tb[1], ls * 0.95, SCRIPT, PAL.cyan, ignite(t, a + 0.95, 1e9, 14), { w: 1.3 });
      const ey = yT + dn + (P ? 7 : 6) * u;
      tubeText(g, "electrode", x0 + 5 * u, ey, ls, SCRIPT, PAL.cyan, ignite(t, a + 1.3, 1e9, 15), { align: "left", w: 1.3 });
      tubeText(g, "electrode", x1 - 5 * u - tubeWidth(g, "electrode", ls), ey, ls, SCRIPT, PAL.cyan, ignite(t, a + 1.4, 1e9, 16), { align: "left", w: 1.3 });
    },
    // 2 key number: two values on one sign, 230 V from the wall against 15,000 V in the tube, which blinks
    (g, t, L) => {
      const P = L.P, u = L.u, a = PANS[1] + 0.3, S = L.S;
      const pw = P ? S.w : S.w * 0.7, ph = P ? 74 * u : 48 * u, py = L.cy - ph / 2;
      plate(g, L.cx - pw / 2, py, pw, ph, PAL.amber, ignite(t, a + 0.05, 1e9, 20) * 0.8);
      const sw = a + 0.85, size = Math.min(P ? 17 * u : 15 * u, pw / 6.2), ls = (P ? 6 : 4.8) * u;
      tubeText(g, "from the wall:", L.cx, py + ph * 0.13, ls, SCRIPT, PAL.cyan, ignite(t, a + 0.2, 1e9, 21), { joins: true, w: 1.3 });
      tubeText(g, "230 V", L.cx, py + ph * (P ? 0.3 : 0.32), size * 0.72, SANS, PAL.amber, (i) => ignite(t, a + 0.3 + i * 0.06, 1e9, i), { w: 1.6, spacing: 0.08 });
      tubeText(g, "in the tube, up to:", L.cx, py + ph * (P ? 0.52 : 0.53), ls, SCRIPT, PAL.cyan, ignite(t, sw + 0.12, 1e9, 22), { joins: true, w: 1.3 });
      const blink = t > sw + 1.0 && B.fract(t * 1.6) < 0.25 ? 0.15 : 1;
      tubeText(g, "15,000 V", L.cx, py + ph * (P ? 0.75 : 0.76), size, SANS, PAL.red, (i) => ignite(t, sw + 0.12 + i * 0.035, 1e9, 30 + i) * blink, { w: 1.6, spacing: 0.06 });
    },
    // 3 step 1
    (g, t, L) => stepSign(g, t, L, PANS[2] + 0.3, "1", "volts push electrons", PAL.cyan, (cx, cy, r, b) => {
      for (let i = 0; i < 6; i++) {
        const x = cx - r * 1.6 + B.fract(i / 6 + t * 0.9) * r * 3.2;
        tube(g, [[x, cy], [x + 0.2 * U, cy]], PAL.cyan, b, { w: 1.8 });
      }
      tube(g, [[cx - r * 1.7, cy - r * 0.5], [cx + r * 1.7, cy - r * 0.5]], PAL.cyan, b * 0.6, { w: 0.6 });
      tube(g, [[cx - r * 1.7, cy + r * 0.5], [cx + r * 1.7, cy + r * 0.5]], PAL.cyan, b * 0.6, { w: 0.6 });
    }),
    // 4 step 2
    (g, t, L) => stepSign(g, t, L, PANS[3] + 0.3, "2", "they hit neon atoms", PAL.pink, (cx, cy, r, b) => {
      for (let k = 0; k < 3; k++) {
        const pts = Array.from({ length: 33 }, (_, i) => {
          const an = (i / 32) * B.TAU, rot = (k * Math.PI) / 3;
          const ex = Math.cos(an) * r * 1.3, ey = Math.sin(an) * r * 0.45;
          return [cx + ex * Math.cos(rot) - ey * Math.sin(rot), cy + ex * Math.sin(rot) + ey * Math.cos(rot)];
        });
        tube(g, pts, PAL.pink, b, { w: 0.7 });
      }
      tube(g, B.arcPts(cx, cy, r * 0.22, 0, B.TAU, 16), PAL.pink, b, { w: 1.2 });
    }),
    // 5 step 3 with the comparison: two gases, two colours, side by side
    (g, t, L) => {
      const a = PANS[4] + 0.3, P = L.P, u = L.u;
      stepSign(g, t, L, a, "3", "atoms give off light", PAL.amber, (cx, cy, r, b) => rays(g, cx, cy, r * 0.5, r * 1.2, 10, PAL.amber, b * (0.7 + 0.3 * Math.sin(t * 12))), -1);
      // the comparison, two gases in two colours (blue tubes are argon with a drop of mercury)
      const x = P ? L.cx : L.S.x + L.S.w * 0.58, y = L.cy + (P ? 28 : 21) * u, dy = (P ? 9.5 : 8.5) * u, sz = (P ? 6.6 : 5.6) * u;
      tubeText(g, "neon = red-orange", x, y, sz, SCRIPT, PAL.red, ignite(t, a + 0.9, 1e9, 40), { joins: true });
      tubeText(g, "argon + mercury = blue", x, y + dy, sz, SCRIPT, PAL.cyan, ignite(t, a + 1.1, 1e9, 41), { joins: true });
    },
    // 6 close
    (g, t, L) => {
      const a = PANS[5] + 0.3, P = L.P, u = L.u, size = Math.min(P ? 10 * u : 9 * u, L.S.w / 11);
      tubeText(g, "glass + gas + volts", L.cx, L.cy - (P ? 16 : 13) * u, size, SANS, PAL.cyan, (i) => ignite(t, a + i * 0.035, 1e9, 50 + i), { spacing: 0.06 });
      const gy = L.cy + (P ? 9 : 7) * u, gs = (P ? 22 : 17) * u, on = ignite(t, a + 0.9, 1e9, 60);
      const rb = ignite(t, a + 0.6, 1e9, 61) * (t > a + 1.2 && B.fract(t * 1.4) < 0.3 ? 0.25 : 1), rx = gs * 1.75, ry = gs * 0.75;
      for (let i = 0; i < 14; i++) {
        const an = (i / 14) * B.TAU + 0.1;
        if (Math.sin(an) < -0.35) continue; // no rays up into "glass + gas + volts"
        const c = Math.cos(an), sn = Math.sin(an);
        tube(g, [[L.cx + c * rx, gy + sn * ry], [L.cx + c * rx * 1.22, gy + sn * ry * 1.4]], PAL.red, rb, { w: 1.1 });
      }
      tubeText(g, "= glow", L.cx, gy, gs, SCRIPT, PAL.pink, (i) => on * (i === 3 ? failing(t + 3, 9) : 1), { joins: true });
    },
  ];
  /** A step sign: a numeral in a tube circle, the words in script, and a small neon icon. */
  function stepSign(g, t, L, a, num, words, col, icon, iconSide) {
    const P = L.P, u = L.u, r = (P ? 11 : 7.5) * u; // portrait: stacked and enlarged
    const nc = P ? [L.cx, L.cy - 27 * u] : [L.S.x + L.S.w * 0.18, L.cy - 4 * u];
    const ring = B.arcPts(nc[0], nc[1], r, -Math.PI / 2 + 0.3, Math.PI * 1.5 - 0.3, 40);
    tube(g, ring, col, ignite(t, a + 0.05, 1e9, 70), { w: 1.0 });
    endCap(g, ring[0][0], ring[0][1], 0.3, -1);
    tubeText(g, num, nc[0], nc[1] + 0.5 * u, r * 1.3, SANS, col, ignite(t, a + 0.12, 1e9, 71), { w: 2.4 });
    const wx = P ? L.cx : L.S.x + L.S.w * 0.58, wy = P ? L.cy - 2 * u : L.cy - 4 * u;
    tubeText(g, words, wx, wy, (P ? 7.8 : 6.6) * u, SCRIPT, col, (i) => ignite(t, a + 0.2 + i * 0.015, 1e9, 72 + i), { joins: true });
    const ic = P ? [L.cx, L.cy + (iconSide ? 11 : 16) * u] : [wx, L.cy + (iconSide ? 7 : 11) * u];
    icon(ic[0], ic[1], (P ? 7.5 : 5) * u, ignite(t, a + 0.55, 1e9, 79));
  }

  // ------------------------------------------------------------------ camera: whip pans along the wall
  function camIndex(t) {
    let x = 0, speed = 0;
    for (const at of PANS) {
      const p = B.prog(t, at - 0.22, 0.5);
      x += B.ease.outBack(p, 1.3);
      speed += Math.sin(Math.PI * B.clamp(p * 1.4)) * (p < 0.7 ? 1 : 0);
    }
    return { x, speed };
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H);
    U = L.u;
    T = t;
    const cam = camIndex(t), camX = cam.x * W;
    // wall
    ctx.fillStyle = "#070405";
    ctx.fillRect(0, 0, W, H);
    wallTiles(ctx, W, H, camX, false, L.hor);
    const visible = SIGNS.map((fn, i) => i).filter((i) => Math.abs(i - cam.x) < 1.15);
    const each = (g, mode) => {
      MODE = mode;
      for (const i of visible) {
        g.save();
        g.translate(i * W - camX, 0);
        SIGNS[i](g, t, L);
        g.restore();
      }
    };
    each(ctx, "glass");
    // glow pass at quarter size, blurred twice and added; the wide one also washes the bricks
    const q = 4, gw = Math.ceil(W / q), gh = Math.ceil(H / q);
    const gl = B.scratch("neon-glow", gw, gh);
    gl.scale(1 / q, 1 / q);
    each(gl, "glow");
    const near = B.scratch("neon-near", gw, gh), wide = B.scratch("neon-wide", gw, gh);
    near.filter = `blur(${(U * 0.5).toFixed(1)}px)`;
    near.drawImage(gl.canvas, 0, 0);
    wide.filter = `blur(${(U * 2.6).toFixed(1)}px)`;
    wide.drawImage(gl.canvas, 0, 0);
    wide.drawImage(gl.canvas, 0, 0);
    const wash = B.scratch("neon-wash", W, H);
    wash.fillStyle = "#000"; // opaque black first: multiply over transparency would just paint the bricks
    wash.fillRect(0, 0, W, H);
    wash.drawImage(wide.canvas, 0, 0, W, H);
    wash.drawImage(wide.canvas, 0, 0, W, H);
    wash.globalCompositeOperation = "multiply";
    wallTiles(wash, W, H, camX, true, L.hor);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.9;
    ctx.drawImage(wash.canvas, 0, 0, W, L.hor, 0, 0, W, L.hor);
    ctx.globalAlpha = 0.75;
    ctx.drawImage(wide.canvas, 0, 0, W, H);
    ctx.globalAlpha = 1;
    ctx.drawImage(near.canvas, 0, 0, W, H);
    ctx.restore();
    each(ctx, "crisp");
    // kerb and wet pavement: a flipped, blurred, rippling copy of the wall and signs
    const refH = H - L.hor;
    const snap = B.scratch("neon-snap", W, H);
    snap.drawImage(ctx.canvas, 0, 0);
    ctx.fillStyle = "#0a0708";
    ctx.fillRect(0, L.hor, W, refH);
    const rf = B.scratch("neon-reflect", W, Math.ceil(refH));
    const strips = 36, sh = refH / strips;
    for (let i = 0; i < strips; i++) {
      const y = i * sh, sq = 2.6, src = L.hor - (y + sh) * sq, off = Math.sin(y * 0.09 / U + t * 5) * U * (0.4 + i * 0.06) + B.noise1(i * 0.7 + t * 3, 8) * U * 0.6;
      rf.save();
      rf.translate(off, y + sh);
      rf.scale(1, -1);
      rf.drawImage(snap.canvas, 0, Math.max(0, src), W, sh * sq + 1, 0, 0, W, sh + 1);
      rf.restore();
    }
    ctx.save();
    ctx.globalAlpha = 0.6;
    ctx.filter = `blur(${(U * 0.35).toFixed(1)}px)`;
    ctx.drawImage(rf.canvas, 0, L.hor);
    ctx.filter = "none";
    ctx.globalAlpha = 1;
    ctx.fillStyle = B.linear(ctx, 0, L.hor, 0, H, ["rgba(10,7,8,0.1)", "rgba(10,7,8,0.75)"]);
    ctx.fillRect(0, L.hor, W, refH);
    ctx.fillStyle = "#1f1619";
    ctx.fillRect(0, L.hor - 0.5 * U, W, 1.1 * U);
    // drops landing: rings spreading through the reflection
    for (let k = Math.floor((t - 1) / 0.23); k <= Math.floor(t / 0.23); k++) {
      const age = t - k * 0.23;
      if (age < 0 || age > 1) continue;
      const x = B.hash01("drop", k) * W, y = L.hor + (0.15 + 0.75 * B.hash01("dy", k)) * refH, r = age * 7 * U;
      ctx.strokeStyle = B.rgba(PAL.core, 0.28 * (1 - age));
      ctx.lineWidth = 0.25 * U;
      ctx.beginPath();
      ctx.ellipse(x, y, r, r * 0.28, 0, 0, B.TAU);
      ctx.stroke();
    }
    ctx.restore();
    // whip-pan smear
    if (cam.speed > 0.05) {
      const sm = B.scratch("neon-smear", W, H);
      sm.drawImage(ctx.canvas, 0, 0);
      ctx.save();
      ctx.globalAlpha = 0.22;
      for (let k = 1; k <= 4; k++) ctx.drawImage(sm.canvas, -k * cam.speed * 4 * U, 0);
      ctx.restore();
    }
    B.vignette(ctx, W, H, { amount: 0.45, inner: 0.5 });
    B.grain(ctx, W, H, { amount: 0.06, t, fps: 24 });
  }

  // ------------------------------------------------------------------ sound: hum bed, buzz + zap ignitions, rain drips, relay clack, chimes
  SOUND.define("neon-buzz", (v, o) => {
    // an ignition: crackle, a short mains buzz and a zap
    v.grains({ span: 0.12, count: 9, filter: "highpass", f: 3000, len: 0.006, peak: 0.25 });
    v.tone({ type: "sawtooth", f: 100, a: 0.004, hold: 0.06, len: 0.08, peak: 0.07 });
    v.tone({ type: "square", f: 200, at: 0.15, a: 0.003, hold: 0.04, len: 0.06, peak: 0.03 });
    v.noise({ filter: "bandpass", f: 2400, f2: 600, glide: 0.1, q: 2, at: 0.14, a: 0.002, len: 0.1, peak: 0.2 });
  }, { verb: 0.15 });
  SOUND.define("neon-drip", (v) => {
    const f = 900 + v.rng() * 700;
    v.tone({ f, f2: f * 0.55, glide: 0.05, a: 0.002, len: 0.07, peak: 0.12 });
  }, { verb: 0.5 });

  function score(k) {
    k.bed("hum", 0, DUR, { gain: 0.6 });
    k.bed("hum", 4.8, DUR, { gain: 0.35 });
    k.bed("rain", 0, DUR, { gain: 0.28 });
    k.repeat(0.2, 0.23, 58, "neon-drip", { gain: 0.35, jitter: 0.08, vary: 3 });
    // title: letters buzz on
    k.at(0.15, "neon-buzz").repeat(0.45, 0.07, 9, "neon-buzz", { gain: 0.45, vary: 2 }).at(1.25, "neon-buzz", { pitch: 3 });
    PANS.forEach((at) => k.at(at - 0.22, "whoosh", { dur: 0.45, gain: 0.55 }));
    // diagram
    k.at(2.65, "neon-buzz").at(2.95, "neon-buzz", { pitch: 2 }).at(3.4, "neon-buzz", { pitch: -2 }).at(3.75, "neon-buzz");
    k.repeat(3.5, 0.06, 10, "tick", { gain: 0.25, pitch: 5 });
    // number: relay clack, the old value snaps dark, the new one buzzes on, emphasis
    k.at(5.15, "neon-buzz").at(5.4, "neon-buzz", { pitch: 1 });
    k.at(6.25, "knock", { gain: 0.9, pitch: -6 }).at(6.26, "click", { gain: 0.8 });
    k.repeat(6.4, 0.05, 8, "neon-buzz", { gain: 0.5, vary: 2 }).at(6.45, "zap", { gain: 0.6 });
    k.at(6.9, "chime", { note: "E6", gain: 0.3 });
    // steps
    [7.3, 8.6, 9.9].forEach((a, i) => k.at(a, "neon-buzz", { pitch: i * 2 }).at(a + 0.3, "neon-buzz", { gain: 0.6 }).at(a + 0.8, "neon-buzz", { gain: 0.5, pitch: 4 }));
    k.at(10.8, "neon-buzz", { pitch: -3 }).at(11.0, "neon-buzz", { pitch: 5 });
    // close: everything on, a bright chime to resolve
    k.repeat(11.8, 0.035, 12, "neon-buzz", { gain: 0.35, vary: 3 });
    k.at(12.7, "neon-buzz", { gain: 0.9 }).at(12.75, "zap", { gain: 0.5 });
    k.at(13.0, "chord", { notes: ["E5", "G#5", "B5", "E6"], strum: 0.04, gain: 0.5 }).at(13.05, "chime", { note: "B6", gain: 0.35 });
  }

  Player.register({
    id: "neon-sign",
    name: "Neon Sign",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Poiret+One&family=Gloria+Hallelujah&display=swap",
      faces: ['400 20px "Poiret One"', '400 20px "Gloria Hallelujah"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.9, 4.45, 6.65, 9.3, 11.15, 13.3],
    draw,
    score,
  });
})();
