/* 30 Riso Print - reference animation.
 * Topic (setting, replace it): "How do bees make honey?"
 * Rendering (keep it): a stencil-duplicator print on cream paper. Four ink drums (yellow, fluoro pink, riso blue and a
 * dark blue-violet for small text), each drawn on its own plate in one flat ink, then printed by multiply so overlaps
 * darken into new colours (pink + blue = violet, yellow + blue = green, pink + yellow = red-orange). Every plate lands
 * a few px off register, has pinholes, speckle and a roller streak, and thins toward the sheet edge. Mid-tones are
 * rough random stipple in one ink, never a tidy screen. Huge Rubik Mono headlines are printed twice in two inks;
 * small text is Space Mono in dark ink on flat colour tags, with scribbled underlines and loose hand-drawn circles.
 * Motion: each scene arrives as separate colour passes sliding down one drum at a time and leaves the same way in
 * reverse; held shots boil at 4 fps (grain and register redrawn); objects hop like cut-outs nudged by hand.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { paper: "#f3ead7", pink: "#ff4f9a", blue: "#2f6fe0", yellow: "#ffd23a", violet: "#5a3fa8", green: "#1f9d6b", dark: "#26225a" };
  const HEAD = "Rubik Mono One", MONO = "Space Mono";
  const DUR = 12.5;
  const BEATS = [0, 2.0, 4.3, 6.4, 8.7, 10.6];

  // ------------------------------------------------------------------ the ink drums (plates), in print order
  // off = misregistration in u (each ink nudged a different way, under a letter-stroke wide)
  const INKS = [
    { k: "Y", col: PAL.yellow, off: [0.32, 0.5] },
    { k: "P", col: PAL.pink, off: [0.55, -0.3] },
    { k: "C", col: PAL.blue, off: [-0.48, 0.26] },
    { k: "D", col: PAL.dark, off: [-0.1, -0.14] },
  ];
  const COL = { Y: PAL.yellow, P: PAL.pink, C: PAL.blue, D: PAL.dark };
  let G = null, U = 1, T = 0; // G = { Y, P, C, D }: this frame's plate contexts

  // fast integer hash for per-dot randomness (no strings in hot loops)
  function ih(a, b, s) {
    let h = (Math.imul(a | 0, 374761393) + Math.imul(b | 0, 668265263) + Math.imul(s | 0, 1274126177)) | 0;
    h = Math.imul(h ^ (h >>> 13), 1103515245);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }

  // ------------------------------------------------------------------ riso helpers (reuse these)
  /** Fill / stroke a path on one plate, always in that plate's single ink. */
  function fill(k, pathFn) {
    const g = G[k];
    g.beginPath();
    pathFn(g);
    g.fillStyle = COL[k];
    g.fill();
  }
  function stroke(k, pathFn, w) {
    const g = G[k];
    g.beginPath();
    pathFn(g);
    g.strokeStyle = COL[k];
    g.lineWidth = w;
    g.lineCap = g.lineJoin = "round";
    g.stroke();
  }
  const ell = (x, y, rx, ry, rot = 0) => (g) => {
    g.moveTo(x + Math.cos(rot) * rx, y + Math.sin(rot) * rx);
    g.ellipse(x, y, rx, ry, rot, 0, B.TAU);
  };
  const wob = (x, y, r, seed, w = 0.07) => (g) => B.blob(g, x, y, r, { seed, wobble: w, n: 11 });
  /**
   * Rough stipple: the riso mid-tone. Jittered random dots of uneven size in one ink, density = tone(x, y) 0..1,
   * clipped to a path. Irregular on purpose (a tidy dot screen is a different style).
   */
  function stipple(k, pathFn, bx, tone, cell, seed = 1) {
    const g = G[k], tf = typeof tone === "function" ? tone : () => tone;
    g.save();
    g.beginPath();
    pathFn(g);
    g.clip();
    g.fillStyle = COL[k];
    g.beginPath();
    const i0 = Math.floor(bx.x / cell) - 1, j0 = Math.floor(bx.y / cell) - 1;
    const i1 = Math.ceil((bx.x + bx.w) / cell) + 1, j1 = Math.ceil((bx.y + bx.h) / cell) + 1;
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++) {
        const px = (i + ih(i, j, seed)) * cell, py = (j + ih(j, i, seed + 7)) * cell;
        if (ih(i, j, seed + 3) > tf(px, py)) continue;
        const r = cell * (0.2 + 0.34 * ih(i + 5, j, seed + 9));
        g.moveTo(px + r, py);
        g.arc(px, py, r, 0, B.TAU);
      }
    g.fill();
    g.restore();
  }
  /** Huge heavy headline on one plate. */
  function head(k, str, x, y, size, o = {}) {
    return B.text(G[k], str, x, y, { size, family: HEAD, weight: 400, color: COL[k], maxW: o.maxW, maxLines: o.maxLines ?? 3, lineH: 1.02, align: o.align, baseline: o.baseline, minSize: size * 0.4 });
  }
  /** The same headline in two inks, a little apart, so the letters show both fringes and an overlap colour inside. */
  function twoInk(str, x, y, size, a, b, o = {}) {
    const d = size * 0.055;
    head(a, str, x - d * 0.6, y - d * 0.35, size, o);
    return head(b, str, x + d * 0.4, y + d * 0.3, size, o);
  }
  /** Plain typewriter-like small text in dark ink (never shrunk below its size). */
  function mono(str, x, y, size, o = {}) {
    return B.text(G[o.ink || "D"], str, x, y, { size, minSize: size, family: MONO, weight: 700, color: COL[o.ink || "D"], maxW: o.maxW, maxLines: o.maxLines ?? 3, lineH: 1.2, align: o.align, baseline: o.baseline });
  }
  /** Scribbled zigzag underline in one ink. */
  function scribble(k, x0, x1, y, h, p = 1, seed = 1) {
    const n = Math.max(4, Math.round((x1 - x0) / (h * 0.9))), pts = [];
    for (let i = 0; i <= n; i++) pts.push([B.lerp(x0, x1, i / n), y + (i % 2 ? h * 0.5 : -h * 0.3) * (0.7 + 0.6 * ih(i, seed, 2))]);
    B.handLine(G[k], pts, { width: h * 0.32, color: COL[k], amp: h * 0.15, seed, p });
  }
  /** Loose hand-drawn ring (emphasis) in a second ink: a bit more than one turn, never closed neatly. */
  function ring(k, cx, cy, rx, ry, p, seed = 1) {
    const pts = [];
    for (let i = 0; i <= 80; i++) {
      const a = -2.2 + (i / 80) * B.TAU * 1.1, rr = 1 + 0.06 * Math.sin(i * 0.21 + seed) + 0.05 * (i / 80);
      pts.push([cx + Math.cos(a) * rx * rr, cy + Math.sin(a) * ry * rr]);
    }
    B.handLine(G[k], pts, { width: 0.9 * U, color: COL[k], amp: 0.35 * U, seed, p });
  }
  /**
   * Flat colour tag: an irregular cut-paper quad in one ink with dark-ink text ("\n" for two lines). s = hop scale.
   * o: { under: ink for a scribbled underline, align "center" | "left" }
   */
  function tag(x, y, str, size, ink, s = 1, o = {}) {
    if (s <= 0.01) return 0;
    G.D.font = B.font(size, MONO, 700);
    const ls = str.split("\n"), tw = Math.max(...ls.map((l) => G.D.measureText(l).width)), w = tw + size * 1.3, h = size * (1.9 + 1.2 * (ls.length - 1));
    const cx = o.align === "left" ? x + w / 2 : x;
    const j = (i) => (ih(i, o.seed ?? 3, 11) - 0.5) * size * 0.3;
    const pts = [[-w / 2 + j(1), -h / 2 + j(2)], [w / 2 + j(3), -h / 2 + j(4)], [w / 2 + j(5), h / 2 + j(6)], [-w / 2 + j(7), h / 2 + j(8)]];
    [ink, "D"].forEach((k) => {
      G[k].save();
      G[k].translate(cx, y);
      G[k].scale(s, s);
      G[k].rotate(o.rot ?? (ih(9, o.seed ?? 3, 1) - 0.5) * 0.05);
    });
    fill(ink, (g) => B.poly(g, pts, true));
    mono(str, 0, size * 0.05, size);
    G[ink].restore();
    G.D.restore();
    if (o.under) scribble(o.under, cx - w * 0.42, cx + w * 0.42, y + h * 0.72, size * 0.55, B.clamp((s - 0.5) * 2), o.seed ?? 3);
    return w;
  }
  /** Stop-motion arrival: a cut-out nudged into place by hand in three quick hops. 0 before `at`. */
  function hopIn(t, at) {
    if (t < at) return 0;
    return [0.55, 0.9, 1.08, 1][Math.min(3, Math.floor((t - at) / 0.07))];
  }
  /** Thick dashed arrow in one ink (blue for flow, pink for problems), with a rough wobble. */
  function inkArrow(k, pts, p, w) {
    B.arrow(G[k], pts, { p, width: w, color: COL[k], dash: [w * 1.7, w * 1.1], head: w * 3.4, headStyle: "tri", rough: w * 0.18, seed: 5 });
  }
  /** Held progress: moves only in hops (fps steps), never a smooth glide. */
  const hops = (t, fps = 6) => B.stepTime(t, fps);

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  function sun(x, y, r) {
    fill("Y", wob(x, y, r, 4, 0.05));
    stipple("P", wob(x, y, r, 4, 0.05), { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, (px, py) => B.clamp(((px - x) + (py - y)) / (2.2 * r) + 0.15) * 0.55, 0.75 * U, 4);
  }
  /** Bee: pink wings that flap on alternate frames, yellow body with blue stripes (they print green), blue head. */
  function bee(x, y, s, seed = 1, flip = false) {
    const f = Math.floor(T * 9 + seed) % 2, wy = f ? -0.12 * s : 0.06 * s, d = flip ? -1 : 1;
    fill("P", ell(x - 0.2 * s * d, y - 0.72 * s + wy, 0.4 * s, 0.62 * s, -0.5 * d));
    fill("P", ell(x + 0.3 * s * d, y - 0.66 * s + wy, 0.34 * s, 0.5 * s, 0.45 * d));
    const body = ell(x, y, 0.95 * s, 0.62 * s);
    fill("Y", body);
    G.C.save();
    G.C.beginPath();
    body(G.C);
    G.C.clip();
    G.C.fillStyle = COL.C;
    [-0.42, 0.04].forEach((o) => G.C.fillRect(x + o * s * d - 0.13 * s, y - s, 0.26 * s, 2 * s));
    G.C.restore();
    fill("C", (g) => B.circle(g, x + 0.95 * s * d, y - 0.08 * s, 0.42 * s));
    fill("D", (g) => B.circle(g, x + 1.08 * s * d, y - 0.16 * s, 0.11 * s));
    fill("D", (g) => B.poly(g, [[x - 0.9 * s * d, y - 0.12 * s], [x - 1.32 * s * d, y + 0.02 * s], [x - 0.9 * s * d, y + 0.16 * s]], true));
    stroke("D", (g) => {
      g.moveTo(x + 1.15 * s * d, y - 0.45 * s);
      g.quadraticCurveTo(x + 1.3 * s * d, y - 0.95 * s, x + 1.55 * s * d, y - 0.9 * s);
    }, 0.09 * s);
  }
  /** Flower: blue stem, leaves in yellow + blue (green overlap), pink petals, yellow centre with pink stipple. */
  function flower(x, y, r, seed = 2) {
    stroke("C", (g) => {
      g.moveTo(x, y);
      g.quadraticCurveTo(x - r * 0.3, y + r * 1.6, x + r * 0.1, y + r * 3);
    }, r * 0.26);
    [[-1, 1.7], [1, 2.2]].forEach(([sd, yy]) => {
      const lf = ell(x + sd * r * 0.55, y + r * yy, r * 0.6, r * 0.26, sd * -0.5);
      fill("Y", lf);
      fill("C", lf);
    });
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * B.TAU + seed;
      fill("P", wob(x + Math.cos(a) * r * 0.72, y + Math.sin(a) * r * 0.72, r * 0.5, seed * 10 + i, 0.12));
    }
    fill("Y", wob(x, y, r * 0.48, seed + 3));
    stipple("P", (g) => B.circle(g, x, y, r * 0.48), { x: x - r, y: y - r, w: 2 * r, h: 2 * r }, 0.42, 0.55 * U, seed);
  }
  /** Honeycomb: chunky yellow hexagons with thick blue walls; some full of honey (pink stipple), some capped (pink). */
  function comb(cx, cy, R, cols, rows, capped = -1) {
    const hex = (x, y, r) => (g) => {
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * B.TAU + Math.PI / 6;
        i ? g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r) : g.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
      }
      g.closePath();
    };
    const dx = R * 1.732, dy = R * 1.5;
    let n = 0;
    for (let j = 0; j < rows; j++)
      for (let i = 0; i < cols; i++) {
        const x = cx + (i - (cols - 1) / 2) * dx + (j % 2 ? dx / 2 : 0), y = cy + (j - (rows - 1) / 2) * dy;
        const p = hex(x, y, R * 0.97);
        fill("Y", p);
        const kind = ih(i, j, 21);
        if (n < capped || kind > 0.72) fill("P", hex(x, y, R * 0.7));
        else if (kind > 0.3) stipple("P", p, { x: x - R, y: y - R, w: 2 * R, h: 2 * R }, (px, py) => B.clamp((py - y + R) / (2 * R)) * 0.7, 0.55 * U, i * 9 + j);
        stroke("C", p, R * 0.17);
        n++;
      }
  }
  /** Honey jar: blue lid and outline, honey in yellow + pink (it prints red-orange where they overlap). */
  function jar(x, y, w, h) {
    const body = (g) => B.roundRect(g, x - w / 2, y - h / 2, w, h, w * 0.18);
    fill("Y", body);
    G.P.save();
    G.P.beginPath();
    body(G.P);
    G.P.clip();
    fill("P", (g) => g.rect(x - w, y - h * 0.18 + Math.sin(T * 3) * 0, w * 2, h));
    G.P.restore();
    stipple("P", body, { x: x - w / 2, y: y - h / 2, w, h: h * 0.35 }, 0.3, 0.7 * U, 31);
    stroke("C", body, w * 0.06);
    fill("C", (g) => B.roundRect(g, x - w * 0.42, y - h / 2 - h * 0.14, w * 0.84, h * 0.16, w * 0.04));
  }

  // ---- scenes (each drawn on all plates; frame coordinates). Portrait stacks and enlarges; landscape uses the width.
  // Small text is never under TS (5u portrait, 5.2u landscape): readable on a phone.
  // Portrait: a printed field band fills the foot of every scene (yellow, with a stipple of a second ink).
  let TS = 4.4;
  const pk = (F, port, land) => (F.portrait ? port : land);
  function footer(F, k, seed) {
    if (!F.portrait) return;
    const W = F.W, H = F.H, gy = H * 0.8, wv = (g) => {
      g.moveTo(0, H);
      for (let i = 0; i <= 12; i++) g.lineTo((i / 12) * W, gy + Math.sin(i * 1.7 + seed) * 1.2 * U);
      g.lineTo(W, H);
      g.closePath();
    };
    fill("Y", wv);
    stipple(k, wv, { x: 0, y: gy - 2 * U, w: W, h: H - gy + 2 * U }, (x, y) => 0.2 + 0.5 * B.clamp((y - gy) / (H * 0.14)), 0.8 * U, seed);
  }
  function header(F, str, a, b) {
    const S = F.safe, P = F.portrait;
    twoInk(str, P ? F.W / 2 : S.x, S.y + pk(F, 5, 4.5) * U, pk(F, 7, 6.5) * U, a, b, { align: P ? "center" : "left", maxW: S.w, maxLines: 1 });
  }
  function sceneTitle(F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    sun(W * pk(F, 0.8, 0.86), H * pk(F, 0.1, 0.22), pk(F, 16, 13) * U);
    // a bold field stripe: yellow under blue prints green, with pink stipple flowers in it
    const gy = H * pk(F, 0.77, 0.84);
    fill("Y", (g) => g.rect(0, gy, W, H - gy));
    stipple("C", (g) => g.rect(0, gy, W, H - gy), { x: 0, y: gy, w: W, h: H - gy }, (x, y) => 0.25 + 0.5 * B.clamp((y - gy) / (H * 0.12)), 0.8 * U, 8);
    const tx = P ? W / 2 : S.x + W * 0.27, ty = H * pk(F, 0.3, 0.36);
    const r = twoInk("HOW BEES\nMAKE\nHONEY", tx, ty, pk(F, 13, 11.5) * U, "P", "C", { maxW: P ? S.w : W * 0.52 });
    tag(tx, r.bottom + 6 * U, "a zine about a sweet job", TS, "Y", hopIn(lt, 0.75), { under: "P", seed: 4 });
    const fx = W * pk(F, 0.64, 0.76), fy = H * pk(F, 0.58, 0.48), fr = pk(F, 9, 8) * U;
    flower(fx, fy, fr, 2);
    if (P) flower(W * 0.24, H * 0.66, 6 * U, 6);
    const k = B.ease.outCubic(B.prog(hops(lt), 0.3, 1.1));
    const bx = B.lerp(P ? -W * 0.1 : W * 0.5, fx - fr * (P ? 2.2 : 1.9), k), by = B.lerp(fy - fr * (P ? 0.2 : 3), fy - fr * (P ? 0.6 : 1.6), k) - Math.abs(Math.sin(hops(lt) * 18)) * U;
    bee(bx, by, pk(F, 6, 5) * U, 1);
  }

  function sceneDiagram(F, lt) {
    const P = F.portrait, W = F.W, H = F.H;
    header(F, "THE NECTAR RUN", "Y", "P");
    footer(F, "C", 21);
    const fx = W * pk(F, 0.3, 0.2), fy = H * pk(F, 0.62, 0.47), fr = pk(F, 9, 10) * U;
    const hx = W * pk(F, 0.66, 0.78), hy = H * pk(F, 0.34, 0.42), hr = pk(F, 6.5, 8) * U;
    comb(hx, hy, hr, 3, 3, 0);
    flower(fx, fy, fr, 5);
    // flow arrow: blue, dashed, flower -> hive
    const a0 = P ? [fx + fr * 0.6, fy - fr * 1.5] : [fx + fr * 1.5, fy - fr * 0.7], a1 = [hx - hr * 2.9, hy + hr * (P ? 0.9 : 0)];
    const path = B.quad(a0[0], a0[1], P ? fx + fr * 0.2 : B.lerp(a0[0], a1[0], 0.5), P ? hy + hr * 0.6 : hy - 16 * U, a1[0], a1[1]);
    inkArrow("C", path, B.prog(lt, 0.35, 0.6, "outCubic"), 1.6 * U);
    // the bee hops along it carrying a pink drop of nectar
    const q = B.pointAt(path, B.prog(hops(lt, 5), 0.6, 1.3));
    if (lt > 0.6) {
      bee(q[0], q[1] - 3.5 * U, pk(F, 4.4, 4) * U, 3);
      fill("P", (g) => B.circle(g, q[0], q[1] + 0.4 * U, 1.3 * U));
    }
    tag(P ? fx + fr * 2.9 : fx, P ? fy + fr * 1.9 : fy + fr * 3.5, "FLOWER", TS, "Y", hopIn(lt, 0.25), { seed: 6 });
    tag(P ? hx + hr * 1.5 : hx, hy + hr * 3.3, "HIVE", TS, "Y", hopIn(lt, 0.45), { seed: 7 });
    // what the flower gives: the tag is tied to the flower by a dark-ink leader ending in a dot
    const nt = [W * pk(F, 0.7, 0.47), H * pk(F, 0.56, 0.71)], tw = tag(nt[0], nt[1], P ? "nectar:\nsugar + water" : "nectar: sugar + water", TS, "P", hopIn(lt, 1.05), { under: "C", seed: 8 });
    if (lt > 1.15) {
      const e = [fx + fr * 1.15, fy + fr * (P ? 0.5 : 0.3)];
      stroke("D", (g) => B.poly(g, B.wobble(B.densify([[nt[0] - tw / 2 - U, nt[1]], e], 2 * U), { amp: 0.4 * U, seed: 3 })), 0.45 * U);
      fill("D", (g) => B.circle(g, e[0], e[1], 0.9 * U));
    }
    ring("C", fx, fy, fr * 1.45, fr * 1.3, B.prog(lt, 1.35, 0.45), 9);
  }

  function sceneNumber(F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    footer(F, "P", 22);
    const nx = W * pk(F, 0.5, 0.3), ny = H * pk(F, 0.25, 0.36), R = pk(F, 30, 24) * U;
    // a big rough-stippled yellow disc behind the figure: a mid-tone, not a gradient
    stipple("Y", wob(nx, ny, R, 12, 0.06), { x: nx - R, y: ny - R, w: 2 * R, h: 2 * R }, (x, y) => 0.75 - 0.45 * B.clamp(Math.hypot(x - nx, y - ny) / R), 0.9 * U, 12);
    const r = twoInk("1/12", nx, ny, pk(F, 26, 22) * U, "C", "P", { maxW: P ? S.w : W * 0.5, maxLines: 1 });
    mono("TEASPOON OF HONEY", nx, r.bottom + 5 * U, TS * 1.15, { maxW: P ? S.w : W * 0.5 });
    tag(nx, r.bottom + 14 * U, "a bee's whole life's work", TS, "Y", hopIn(lt, 0.55), { under: "P", seed: 13 });
    // twelve bees hop in, one by one: that is one teaspoon
    const gx = W * pk(F, 0.5, 0.745), gy = H * pk(F, 0.61, 0.4), sp = pk(F, 14, 14) * U, cols = 4;
    let shown = 0;
    for (let i = 0; i < 12; i++) {
      const s = hopIn(lt, 0.6 + i * 0.06);
      if (!s) continue;
      shown++;
      bee(gx + ((i % cols) - 1.5) * sp, gy + (Math.floor(i / cols) - 1) * sp * 0.8, pk(F, 4.4, 4) * U * s, 20 + i);
    }
    mono(shown + " bees = 1 teaspoon", gx, gy + sp * pk(F, 2.2, 2.35), TS * 1.05, { maxW: P ? S.w : W * 0.42 });
    if (shown === 12) ring("P", gx, gy, sp * pk(F, 2.75, 2.6), sp * pk(F, 1.75, 1.85), B.prog(lt, 1.4, 0.35), 14); // clear of the wings, inside the side margins // around the bees, clear of every wing
  }

  function sceneSteps(F, lt) {
    const P = F.portrait, W = F.W, H = F.H;
    header(F, "NECTAR TO HONEY", "Y", "P");
    footer(F, "C", 23);
    const steps = [["SIP", "Sip nectar from flowers"], ["FAN", "Fan wings to dry it out"], ["CAP", "Seal each cell with wax"]];
    const pos = (i) => (P ? [W * 0.17, H * (0.33 + i * 0.18)] : [W * (0.2 + i * 0.3), H * 0.36]);
    const dr = pk(F, 8, 7.5) * U;
    steps.forEach(([word, line], i) => {
      const at = 0.25 + i * 0.4, s = hopIn(lt, at), [x, y] = pos(i);
      if (i > 0) {
        const [px, py] = pos(i - 1);
        inkArrow("C", P ? [[px, py + dr * 1.25], [x, y - dr * 1.25]] : [[px + dr * 1.3, py], [x - dr * 1.3, y]], B.prog(lt, at - 0.25, 0.25), 1.4 * U);
      }
      if (!s) return;
      ["Y", "P"].forEach((k) => {
        G[k].save();
        G[k].translate(x, y);
        G[k].scale(s, s);
      });
      fill("Y", wob(0, 0, dr, 40 + i));
      stipple("P", wob(0, 0, dr, 40 + i), { x: -dr, y: -dr, w: 2 * dr, h: 2 * dr }, (px, py) => B.clamp((px + py) / (2 * dr) + 0.2) * 0.5, 0.7 * U, i);
      G.Y.restore();
      G.P.restore();
      twoInk(String(i + 1), x, y + U * 0.4, dr * 1.15, "C", "P", { maxLines: 1 });
      const tx = P ? W * 0.31 : x, ty = P ? y - 3.8 * U : y + dr + 7 * U, al = P ? "left" : "center";
      const hw = twoInk(word, tx, ty, pk(F, 7, 6) * U, "P", "C", { align: al, maxLines: 1 });
      if (s >= 1) scribble("Y", P ? tx : tx - hw.width / 2, P ? tx + hw.width : tx + hw.width / 2, ty + hw.height * 0.62, 1.6 * U, B.prog(lt, at + 0.2, 0.3), i + 3);
      mono(line, tx, ty + pk(F, 8, 9.5) * U, TS, { align: al, maxW: W * pk(F, 0.64, 0.27), maxLines: 2, baseline: "top" });
    });
    // step 2 comes alive: a bee fanning its wings beside it
    if (lt > 0.8) {
      const [x, y] = pos(1);
      bee(P ? W * 0.84 : x + dr * 1.7, P ? y - 4 * U : y - dr * 1.3, pk(F, 4.6, 4) * U, 7, true);
    }
  }

  function sceneChart(F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    header(F, "WATER INSIDE", "Y", "P");
    footer(F, "C", 24);
    const base = H * pk(F, 0.7, 0.78), maxH = H * pk(F, 0.38, 0.5), bw = pk(F, 24, 18) * U;
    const bars = [["NECTAR", 80, "C", W * pk(F, 0.3, 0.38)], ["HONEY", 18, "P", W * pk(F, 0.72, 0.64)]];
    bars.forEach(([name, v, k, x], i) => {
      const g = hops(B.prog(lt, 0.2 + i * 0.35, 0.5, "outCubic"), 7); // grows in hops
      const h = (maxH * v * g) / 80;
      fill(k, (c) => c.rect(x - bw / 2, base - h, bw, h));
      stipple(k === "C" ? "P" : "Y", (c) => c.rect(x - bw / 2, base - h, bw, h), { x: x - bw / 2, y: base - h, w: bw, h }, 0.18, 0.8 * U, 50 + i);
      if (g > 0) twoInk(Math.round(v * g) + "%", x, base - h - 6 * U, pk(F, 8, 6.5) * U, k, k === "C" ? "Y" : "C", { maxLines: 1 });
      tag(x, base + 6 * U, name, TS, "Y", hopIn(lt, 0.2 + i * 0.5), { seed: 51 + i });
    });
    stroke("D", (c) => {
      c.moveTo(S.x + 2 * U, base);
      c.lineTo(S.r - 2 * U, base);
    }, 0.6 * U);
    const x0 = bars[0][3] + bw * 0.6, x1 = bars[1][3], yy = base - maxH * 0.72, y1 = base - (maxH * 18) / 80 - 13 * U;
    inkArrow("C", B.quad(x0, yy, x1, yy, x1, y1), B.prog(lt, 0.85, 0.45, "outCubic"), 1.4 * U);
    tag(P ? W * 0.66 : x1 + 6 * U, yy - 8 * U, "fanning dries it", TS, "Y", hopIn(lt, 1.1), { under: "P", seed: 53 });
  }

  function sceneClose(F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    sun(W * pk(F, 0.2, 0.1), H * pk(F, 0.11, 0.2), pk(F, 15, 13) * U);
    footer(F, "P", 25);
    const tx = W * pk(F, 0.5, 0.33), ty = H * pk(F, 0.27, 0.36);
    const r = twoInk("SWEET!", tx, ty, pk(F, 17, 15) * U, "P", "Y", { maxW: P ? S.w : W * 0.55, maxLines: 1 });
    mono("nectar in, water out", tx, r.bottom + 5 * U, TS * 1.1);
    tag(tx, r.bottom + 15 * U, "thank a bee", TS * 1.1, "C", hopIn(lt, 0.6), { under: "P", seed: 61 });
    const jx = W * pk(F, 0.5, 0.74), jy = H * pk(F, 0.62, 0.52), jw = pk(F, 34, 28) * U;
    jar(jx, jy, jw, jw * 1.15);
    tag(jx, jy + jw * 0.12, "HONEY", TS * 1.2, "Y", hopIn(lt, 0.3), { seed: 62, rot: -0.04 });
    const a = hops(lt, 5) * 1.6;
    bee(jx + Math.cos(a) * jw * 0.85, jy - jw * 0.55 + Math.sin(a) * jw * 0.25, pk(F, 5, 4.4) * U, 9, Math.sin(a) > 0);
  }

  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneChart, sceneClose];

  // ------------------------------------------------------------------ colour passes: ink by ink, never all at once
  const passIn = (b, i) => BEATS[b] + (b ? -0.12 : 0.04) + i * 0.12; // when plate i of scene b starts sliding down
  const passOut = (b, i) => BEATS[b + 1] - 0.3 + (3 - i) * 0.07; // leaves in reverse order, back up (the next scene's
  // first inks are already sliding in, so the sheet is never blank)
  function slide(b, i, t, H) {
    const pIn = B.prog(t, passIn(b, i), 0.3);
    let y = -(1 - B.ease.outBack(pIn, 1.3)) * H * 1.08;
    if (b + 1 < BEATS.length) y -= B.prog(t, passOut(b, i), 0.2, "inCubic") * H * 1.08;
    return y;
  }

  // ------------------------------------------------------------------ ink texture (cached tiles) and the print
  /** Pinholes and speckle: where the stencil let too little ink through. Tile of transparent-to-solid specks. */
  function holeTile() {
    return B.layer("riso-holes", 256, 256, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(301);
      for (let i = 0; i < w * h; i++) {
        const v = r();
        d[i * 4 + 3] = v < 0.06 ? 255 : v < 0.2 ? 90 : v < 0.4 ? 30 : 0;
      }
      g.putImageData(img, 0, 0);
      g.fillStyle = "#000";
      for (let i = 0; i < 70; i++) {
        g.globalAlpha = r.range(0.5, 1);
        g.beginPath();
        g.arc(r() * w, r() * h, r.range(0.6, 2.2), 0, B.TAU);
        g.fill();
      }
    });
  }
  /** Roller streak: soft vertical bands where the drum laid down less ink (per plate, static). */
  function streak(k, W, H) {
    return B.layer("riso-streak-" + k, 256, 32, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, seed = k.charCodeAt(0);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const n = B.noise2(x / 9, y / 14, seed) * 0.6 + B.noise2(x / 40, 0.5, seed + 1) * 0.6;
          d[(y * w + x) * 4 + 3] = B.clamp(n - 0.15) * 200;
        }
      g.putImageData(img, 0, 0);
    });
  }
  function inkTexture(g, k, W, H, f, i) {
    g.save();
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "destination-out";
    const pat = g.createPattern(holeTile(), "repeat"), sc = Math.max(1, U / 6.5);
    pat.setTransform(new DOMMatrix([sc, 0, 0, sc, ih(f, i, 1) * 256 * sc, ih(f, i, 2) * 256 * sc]));
    g.fillStyle = pat;
    g.globalAlpha = 0.85;
    g.fillRect(0, 0, W, H);
    g.globalAlpha = 0.55;
    g.imageSmoothingEnabled = true;
    g.drawImage(streak(k, W, H), 0, 0, W, H);
    // the ink thins toward the sheet edges
    g.globalAlpha = 1;
    g.fillStyle = B.radial(g, W / 2, H / 2, Math.hypot(W, H) * 0.3, Math.hypot(W, H) * 0.58, [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0.3)"]]);
    g.fillRect(0, 0, W, H);
    g.restore();
  }

  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    U = F.u;
    T = t;
    TS = (F.portrait ? 5 : 5.2) * U;
    G = {};
    INKS.forEach((p) => (G[p.k] = B.scratch("riso-" + p.k, W, H)));
    const bt = B.beat(t, BEATS, DUR), scene = (b) => {
      INKS.forEach((p, i) => G[p.k].setTransform(1, 0, 0, 1, 0, slide(b, i, t, H)));
      SCENES[b](F, t - BEATS[b]);
    };
    if (bt.i > 0 && t < BEATS[bt.i] + 0.12) scene(bt.i - 1); // still leaving
    if (bt.i + 1 < BEATS.length && t > BEATS[bt.i + 1] - 0.12) scene(bt.i + 1); // already arriving
    scene(bt.i);
    const f = B.boil(t, 4); // held shots boil: grain and register redrawn 4 times a second
    INKS.forEach((p, i) => inkTexture(G[p.k], p.k, W, H, f, i));
    // print: cream sheet, then each drum multiplied on, each a hair out of register
    B.paper(ctx, W, H, { color: PAL.paper, seed: 30, mottle: 0.1, fibers: 0.5, specks: 0.55, tooth: 0.1 });
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    INKS.forEach((p, i) => {
      ctx.globalAlpha = p.k === "D" ? 0.95 : 0.9;
      ctx.drawImage(G[p.k].canvas, (p.off[0] + (ih(f, i, 5) - 0.5) * 0.3) * U, (p.off[1] + (ih(f, i, 6) - 0.5) * 0.3) * U);
    });
    ctx.restore();
    B.mottle(ctx, W, H, { amount: 0.08, feature: 0.25, seed: 31, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.08, t, fps: 4, mode: "overlay" });
  }

  // ------------------------------------------------------------------ sound: drum roll + thump per ink, rustle + stamp per tag, rubbery blips
  SOUND.define("riso-drum", (v) => {
    // the duplicator drum turning: a dry rattle of tiny clicks, then the flat thump of the sheet landing
    v.grains({ span: 0.24, count: 26, filter: "bandpass", f: 1100, q: 1.4, len: 0.01, peak: 0.28 });
    v.noise({ filter: "lowpass", f: 600, brown: true, a: 0.02, hold: 0.14, len: 0.08, peak: 0.14 });
    v.tone({ at: 0.26, f: 130, f2: 52, glide: 0.09, a: 0.002, len: 0.13, peak: 0.5 });
    v.noise({ at: 0.26, filter: "bandpass", f: 700, q: 0.8, a: 0.001, len: 0.05, peak: 0.25 });
  }, { verb: 0.06 });
  SOUND.define("riso-blip", (v) => {
    // rubbery: a sine that bends down fast, with a soft square edge
    v.tone({ f: 780, f2: 380, glide: 0.07, a: 0.002, len: 0.09, peak: 0.24 });
    v.tone({ type: "square", f: 390, f2: 190, glide: 0.07, a: 0.002, len: 0.05, peak: 0.03 });
  }, { verb: 0.1 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.8 });
    const sc = SOUND.scale("D4", "pent", 10);
    BEATS.forEach((b, s) => {
      for (let i = 0; i < 4; i++) k.at(passIn(s, i), "riso-drum", { gain: i === 3 ? 0.4 : 0.65, pitch: i * 1.5 - 2, pan: [-0.3, 0.3, -0.1, 0.1][i] });
      if (s + 1 < BEATS.length) k.at(passOut(s, 3), "swish", { dur: 0.35, gain: 0.35 });
    });
    const tagAt = (at, i = 0) => k.at(at, "rustle", { dur: 0.18, gain: 0.6 }).at(at + 0.05, "stamp", { gain: 0.4, pitch: i });
    tagAt(0.75);
    k.seq(0.35, 0.18, [sc[2], sc[4], sc[5], sc[7]], { voice: "pluck", gain: 0.35 });
    tagAt(2.25, 1);
    tagAt(2.45, 2);
    k.at(2.4, "scribble", { dur: 0.5, gain: 0.4 });
    tagAt(3.05, -1);
    k.at(3.35, "pencil", { dur: 0.4, gain: 0.45 });
    tagAt(4.85);
    for (let i = 0; i < 12; i++) k.at(4.3 + 0.6 + i * 0.06, "riso-blip", { pitch: i, gain: 0.7 });
    k.at(6.15, "pencil", { dur: 0.35, gain: 0.4 });
    [0.25, 0.65, 1.05].forEach((a, i) => {
      tagAt(6.4 + a, i);
      k.at(6.4 + a, "pluck", { note: sc[3 + i * 2], gain: 0.4 });
    });
    for (let i = 0; i < 7; i++) {
      k.at(8.7 + 0.2 + i * 0.07, "riso-blip", { pitch: 12 - i, gain: 0.5 });
      k.at(8.7 + 0.55 + i * 0.07, "riso-blip", { pitch: 5 + i, gain: 0.5 });
    }
    tagAt(8.9);
    tagAt(9.4, 1);
    tagAt(9.8, 2);
    k.at(9.55, "swish", { dur: 0.4, gain: 0.4 });
    tagAt(10.9);
    tagAt(11.2, 2);
    k.chord(11.0, ["D4", "F#4", "A4", "D5"], { voice: "keys", strum: 0.04 });
  }

  Player.register({
    id: "riso",
    name: "Riso Print",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Rubik+Mono+One&family=Space+Mono:wght@400;700&display=swap",
      faces: ['400 20px "Rubik Mono One"', '700 20px "Space Mono"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Chart", "Close"],
    stills: [1.5, 3.7, 5.8, 8.1, 9.9, 12.2],
    draw,
    score,
  });
})();
