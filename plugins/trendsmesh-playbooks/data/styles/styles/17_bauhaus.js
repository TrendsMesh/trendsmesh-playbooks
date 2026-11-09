/* 17 Bauhaus Geometry - reference animation.
 * Topic (setting, replace it): "How gears trade speed for strength" - an 8-tooth wheel driving a 24-tooth wheel.
 * Rendering (keep it): a 1920s workshop print. One long sheet of worn cream poster paper (edges toward tan, fibres,
 * age spots, two fold creases) holds six panels on a grid; every figure is built only from discs, squares, half-discs,
 * triangles, bars and rings in four flat inks, with bar-built lower-case display letters, black label blocks with words
 * knocked out to bare paper, bar arrows with big solid triangle heads, and a red ring on the key moment.
 * Printing: each ink is drawn on its own plate; a shape in one ink also punches its hole in the other three, then the
 * plates are printed (multiplied) with small different nudges, so slivers overlap dark and thin paper gaps show. Each
 * plate loses coverage in soft cloudy patches with rare pinholes. Grain and a warm vignette on top.
 * Motion: grid rules draw out, shapes drop and settle with a small overshoot like wooden blocks, letters drop one by one,
 * the camera tracks along the sheet and stops firmly, gears ratchet during holds, and at the end the camera pulls out
 * until the whole sheet reads as one diagram. Seen whole, the panels' small type would be unreadable, so the pull-out
 * lifts every label off the sheet and one big caption block drops onto it instead.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { paper: "#f0e6cc", age: "#c4a170", r: "#d8432b", y: "#f4c02e", b: "#24479a", k: "#161514" };
  const KEYS = ["y", "r", "b", "k"]; // the four ink plates
  const SANS = "Jost", HEAVY = "Archivo Black", LBL = 4.1; // LBL: label text size in u (3.8 % of the short side is the floor)
  const DUR = 14;
  const BEATS = [0, 2.3, 4.5, 6.7, 8.7, 10.6];
  const T_PULL = [12.0, 12.9], T_CAP = 12.85;
  // each plate's mis-registration nudge, in units of u (one or two pixels each way at 1080)
  const NUDGE = { y: [-0.16, 0.14], r: [0.15, -0.1], b: [0.1, 0.16], k: [0, 0] };

  // ------------------------------------------------------------------ the four plates and the shared transform stack
  let L = null, LT = 0, U = 1, HIDE = false; // LT: the current panel's local time; HIDE: labels lifted off (pull-out)
  const all = (fn) => KEYS.forEach((k) => fn(L[k], k));
  function push(x, y, s = 1, r = 0) {
    all((g) => {
      g.save();
      g.translate(x, y);
      if (r) g.rotate(r);
      if (s !== 1) g.scale(s, s);
    });
  }
  const pop = () => all((g) => g.restore());
  /** Fill a path in one ink; the same path punches a matching hole in the other three plates (no overprint). */
  function ink(col, path, stroke = 0) {
    all((g, k) => {
      g.save();
      g.beginPath();
      path(g);
      if (k !== col) {
        g.globalCompositeOperation = "destination-out";
        g.fillStyle = g.strokeStyle = "#000";
      } else g.fillStyle = g.strokeStyle = PAL[col];
      if (stroke) {
        g.lineWidth = stroke;
        g.lineCap = "butt";
        g.stroke();
      } else g.fill();
      g.restore();
    });
  }
  /** Knock a path out of every plate: bare paper (reversed words inside solid blocks). */
  function knock(path) {
    all((g) => {
      g.save();
      g.globalCompositeOperation = "destination-out";
      g.beginPath();
      path(g);
      g.fillStyle = "#000";
      g.fill();
      g.restore();
    });
  }
  /** Text in one ink (punching the others), or knocked out to paper with col = null. Returns the layout. */
  function inkText(col, str, x, y, o) {
    let m = null;
    if (HIDE) return m;
    all((g, k) => {
      g.save();
      if (col == null || k !== col) g.globalCompositeOperation = "destination-out";
      m = B.text(g, str, x, y, Object.assign({ family: SANS, weight: 700, align: "left", baseline: "top", lineH: 1.08 }, o, { color: col && k === col ? PAL[col] : "#000" }));
      g.restore();
    });
    return m;
  }

  // ------------------------------------------------------------------ constructed primitives (no outlines, no gradients, no rounding)
  const disc = (col, x, y, r) => ink(col, (g) => g.arc(x, y, r, 0, B.TAU));
  const rect = (col, x, y, w, h) => ink(col, (g) => g.rect(x, y, w, h));
  const half = (col, x, y, r, rot = 0) => ink(col, (g) => g.arc(x, y, r, Math.PI + rot, B.TAU + rot)); // flat side down at rot 0
  const ring = (col, x, y, r, w, a0 = 0, a1 = B.TAU) => ink(col, (g) => g.arc(x, y, r, a0, a1), w);
  function tri(col, cx, cy, s) {
    const h = s * 0.866;
    ink(col, (g) => B.poly(g, [[cx, cy - h * 0.62], [cx + s / 2, cy + h * 0.38], [cx - s / 2, cy + h * 0.38]], true));
  }
  /** A straight bar of width w from (x0, y0) to (x1, y1). */
  function bar(col, x0, y0, x1, y1, w) {
    const a = Math.atan2(y1 - y0, x1 - x0), nx = (-Math.sin(a) * w) / 2, ny = (Math.cos(a) * w) / 2;
    ink(col, (g) => B.poly(g, [[x0 + nx, y0 + ny], [x1 + nx, y1 + ny], [x1 - nx, y1 - ny], [x0 - nx, y0 - ny]], true));
  }
  /** Arrow: a thick black bar extending from its start, ending in a large solid triangle. p: 0..1. */
  function barArrow(x0, y0, x1, y1, p, w) {
    if (p <= 0) return;
    w *= 1.9; // a heavy bar, as the card's arrows are
    const L0 = Math.hypot(x1 - x0, y1 - y0), a = Math.atan2(y1 - y0, x1 - x0), hl = w * 2.6, len = L0 * p;
    const ex = x0 + Math.cos(a) * Math.max(0, len - hl), ey = y0 + Math.sin(a) * Math.max(0, len - hl);
    bar("k", x0, y0, ex, ey, w);
    const tx = x0 + Math.cos(a) * len, ty = y0 + Math.sin(a) * len, nx = -Math.sin(a), ny = Math.cos(a), hw = w * 1.5;
    ink("k", (g) => B.poly(g, [[tx, ty], [ex + nx * hw, ey + ny * hw], [ex - nx * hw, ey - ny * hw]], true));
  }
  /** Wooden-block drop: falls a little, lands with a small overshoot and settles. Returns false before it starts. */
  function drop(t0, x, y, fn, o = {}) {
    if (LT < t0) return false;
    const e = B.ease.outBack(B.prog(LT, t0, o.dur ?? 0.42), o.over ?? 2.2);
    push(x, y - (1 - e) * (o.fall ?? 5) * U, 1 + (1 - e) * (o.grow ?? 0.1));
    fn();
    pop();
    return true;
  }
  /** Black label block with bold words knocked out to paper; drops onto what it names. Returns its size. */
  function tag(x, y, str, at, o = {}) {
    const size = o.size ?? LBL * U, pad = size * 0.45, maxW = o.maxW ?? 40 * U;
    const m = B.measureText(L.k, str, { size, family: SANS, weight: 700, maxW: maxW - 2 * pad, lineH: 1.1 });
    const w = m.width + 2 * pad, h = m.height + 2 * pad * 0.8;
    const ox = o.align === "right" ? -w : o.align === "center" ? -w / 2 : 0;
    if (!HIDE) drop(at, x + ox, y, () => {
      rect(o.fill || "k", 0, 0, w, h);
      inkText(null, str, pad, pad * 0.8 + size * 0.04, { size, maxW: maxW - 2 * pad, lineH: 1.1 });
    }, { fall: 3, grow: 0.06 });
    return { w, h };
  }
  /** A gear: a disc with square teeth round its rim, a paper hole at the hub. Angle in radians. */
  function gear(col, cx, cy, r, n, ang, hub) {
    disc(col, cx, cy, r);
    const s = ((Math.PI * r) / n) * 0.95;
    ink(col, (g) => {
      for (let i = 0; i < n; i++) {
        const a = ang + (i / n) * B.TAU, ca = Math.cos(a), sa = Math.sin(a), rr = r + s * 0.32;
        const px = cx + ca * rr, py = cy + sa * rr, hx = (ca * s) / 2, hy = (sa * s) / 2, tx = (-sa * s) / 2, ty = (ca * s) / 2;
        B.poly(g, [[px - hx - tx, py - hy - ty], [px + hx - tx, py + hy - ty], [px + hx + tx, py + hy + ty], [px - hx + tx, py - hy + ty]], true);
      }
    });
    if (hub) {
      push(cx, cy, 1, ang);
      rect("k", -r * 0.22, -r * 0.22, r * 0.44, r * 0.44);
      bar("k", 0, 0, r * 0.82, 0, r * 0.08);
      pop();
    }
    knock((g) => g.arc(cx, cy, r * 0.09 + 0.6 * U, 0, B.TAU));
  }
  /** Bar-built lower-case letters: stems are bars, bowls full rings, shoulders partial arcs, all one stroke weight. */
  function barWord(word, x, base, h, at, gap = 0.12) {
    const w = h * 0.2, r = h / 2 - w / 2;
    let xx = x;
    [...word].forEach((ch, i) => {
      const adv = (ch === "r" ? 0.78 : 1) * h + gap * h;
      const t0 = at + i * 0.16;
      drop(t0, 0, 0, () => {
        const col = ch === "a" ? "r" : "k";
        const cx = xx + h / 2, cy = base - h / 2;
        if (ch === "g") {
          ring(col, cx, cy, r, w);
          rect(col, xx + h - w, base - h, w, h * 1.15);
          ring(col, cx, base + 0.15 * h, r, w, 0, Math.PI);
        } else if (ch === "e") {
          ring(col, cx, cy, r, w, 0.34 * Math.PI, 2.03 * Math.PI);
          rect(col, xx + w * 0.4, cy - w * 0.42, h - w * 0.8, w * 0.84);
        } else if (ch === "a") {
          ring(col, cx, cy, r, w);
          rect(col, xx + h - w, base - h, w, h);
        } else if (ch === "r") {
          rect(col, xx, base - h, w, h);
          ring(col, xx + w / 2 + r, cy, r, w, Math.PI, 1.72 * Math.PI);
        }
      }, { fall: h / U * 0.5, grow: 0 });
      xx += adv;
    });
    return xx - x;
  }
  /** Thin black grid rule drawn out from its start (p 0..1). */
  function rule(x0, y0, x1, y1, p, w = 0.28 * U) {
    if (p <= 0) return;
    bar("k", x0, y0, B.lerp(x0, x1, p), B.lerp(y0, y1, p), w);
  }
  /** Heavy red ring drawn round the key moment, sweeping on. */
  function redRing(x, y, r, p) {
    if (p <= 0) return;
    ring("r", x, y, r, 1.6 * U, -Math.PI * 0.6, -Math.PI * 0.6 + B.TAU * p);
  }
  /** Right result: a black tick made of two bars. */
  function tick(x, y, s, p) {
    if (p <= 0) return;
    bar("k", x - s * 0.5, y - s * 0.05, B.lerp(x - s * 0.5, x - s * 0.15, B.clamp(p * 2)), B.lerp(y - s * 0.05, y + s * 0.3, B.clamp(p * 2)), s * 0.16);
    if (p > 0.5) bar("k", x - s * 0.21, y + s * 0.3, B.lerp(x - s * 0.21, x + s * 0.55, (p - 0.5) * 2), B.lerp(y + s * 0.3, y - s * 0.5, (p - 0.5) * 2), s * 0.16);
  }
  /** Ratchet angle: advances one tooth every `period` seconds with a snap. */
  function ratchet(lt, start, period, step) {
    if (lt < start) return 0;
    const n = Math.floor((lt - start) / period), f = (lt - start - n * period) / 0.16;
    return (n + B.ease.outBack(B.clamp(f), 2)) * step;
  }
  /** Gear pair meshing: the driven angle from the driver's, so a tooth always meets a gap at the contact line. */
  const meshAngle = (aS, nS, nB, contact) => -(aS - contact) * (nS / nB) + contact + Math.PI + Math.PI / nB;

  // ------------------------------------------------------------------ the panels (panel-local coordinates 0..W, 0..H)
  function panelGrid(F, lt, cols, rows) {
    // the modular grid: a few thin rules, drawn out first
    const { W, H } = F;
    cols.forEach((c, i) => rule(c * W, 0.04 * H, c * W, 0.96 * H, B.prog(lt, -0.45 + i * 0.08, 0.45, "inOutQuad")));
    rows.forEach((r, i) => rule(0.03 * W, r * H, 0.97 * W, r * H, B.prog(lt, -0.4 + i * 0.08, 0.45, "inOutQuad")));
  }

  function pTitle(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.9] : [0.06, 0.93], P ? [0.12, 0.8] : [0.88]);
    rule(P ? 0.02 * W : 0.0, P ? 0.98 * H : 0.98 * H, P ? 0.98 * W : W, P ? 0.08 * H : 0.04 * H, B.prog(lt, 0.15, 0.6, "inOutQuad"), 0.22 * U); // long diagonal construction rule
    const sun = P ? [0.6 * W, 0.37 * H, 0.33 * W] : [0.66 * W, 0.44 * H, 0.36 * H];
    drop(0.3, sun[0], sun[1], () => disc("y", 0, 0, sun[2]), { fall: 4 });
    drop(0.5, sun[0] + sun[2] * (P ? -0.72 : 0.62), sun[1] + sun[2] * (P ? -0.74 : 0.66), () => gear("r", 0, 0, sun[2] * 0.3, 8, ratchet(lt, 1.4, 0.5, B.TAU / 8)), { fall: 4 });
    drop(0.62, sun[0] + sun[2] * 0.95, sun[1] - sun[2] * 0.75, () => rect("b", -sun[2] * 0.14, -sun[2] * 0.14, sun[2] * 0.28, sun[2] * 0.28));
    const h = P ? 0.19 * W : 0.24 * H;
    barWord("gear", 0.08 * W, P ? 0.53 * H : 0.62 * H, h, 0.6);
    tag(P ? 0.08 * W : 0.08 * W, P ? 0.63 * H : 0.75 * H, "how a small wheel turns a big one", 1.15, { size: (P ? 4.4 : 4.2) * U, maxW: P ? 0.84 * W : 0.6 * W });
    // a short label turned 90 degrees and set along a vertical rule at the side
    if (lt > 1.3) {
      push(P ? 0.9 * W + 1.6 * U : 0.93 * W + 1.6 * U, P ? 0.64 * H : 0.62 * H, 1, -Math.PI / 2);
      inkText("k", "workshop sheet 01", 0, 0, { size: LBL * U, weight: 600, letterSpacing: 0.1 });
      pop();
    }
  }

  function gearPair(F, lt, at) {
    const { W, H, portrait: P } = F;
    const rs = P ? 0.105 * W : 0.085 * H, rb = rs * 3;
    const S = P ? [0.3 * W, 0.27 * H] : [0.25 * W, 0.47 * H];
    const contact = P ? 1.05 : 0;
    // rims a tooth's height apart (teeth reach 0.82 of a tooth past the rim, tooth = 0.373 rs): teeth interleave, no overlap
    const d = rs + rb + 0.31 * rs, Bc = [S[0] + Math.cos(contact) * d, S[1] + Math.sin(contact) * d];
    const aS = ratchet(lt, at + 0.55, 0.45, B.TAU / 8);
    drop(at + 0.2, Bc[0], Bc[1], () => gear("b", 0, 0, rb, 24, meshAngle(aS, 8, 24, contact), true));
    drop(at, S[0], S[1], () => gear("r", 0, 0, rs, 8, aS));
    return { S, Bc, rs, rb };
  }

  function pDiagram(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.08] : [0.6], P ? [0.86] : [0.12, 0.88]);
    const G = gearPair(F, lt, 0);
    // the tags and the bar arrows to what they name
    const sz = LBL * U;
    if (P) {
      const t1 = tag(0.53 * W, 0.17 * H, "driver: 8 teeth", 0.7, { size: sz });
      barArrow(0.53 * W + 3 * U, 0.17 * H + t1.h, G.S[0] + G.rs * 0.9, G.S[1] - G.rs * 0.3, B.prog(lt, 0.9, 0.3, "outCubic"), 1.1 * U);
      const t2 = tag(0.12 * W, 0.71 * H, "driven: 24 teeth", 1.0, { size: sz });
      barArrow(0.12 * W + t2.w * 0.7, 0.71 * H, G.Bc[0] - G.rb * 0.55, G.Bc[1] + G.rb * 0.62, B.prog(lt, 1.2, 0.3, "outCubic"), 1.1 * U);
    } else {
      const t1 = tag(0.06 * W, 0.15 * H, "driver: 8 teeth", 0.7, { size: sz });
      barArrow(0.06 * W + t1.w * 0.6, 0.15 * H + t1.h, G.S[0] - G.rs * 0.4, G.S[1] - G.rs * 1.05, B.prog(lt, 0.9, 0.3, "outCubic"), 0.9 * U);
      const t2 = tag(0.66 * W, 0.62 * H, "driven: 24 teeth", 1.0, { size: sz });
      barArrow(0.66 * W, 0.62 * H + t2.h / 2, G.Bc[0] + G.rb * 0.86, G.Bc[1] + G.rb * 0.42, B.prog(lt, 1.2, 0.3, "outCubic"), 0.9 * U);
      tag(0.66 * W, 0.3 * H, "teeth mesh, so both move together", 1.4, { size: LBL * U, maxW: 0.3 * W, fill: "b" });
    }
  }

  function pNumber(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.92] : [0.5, 0.94], P ? [0.525, 0.84] : [0.1]);
    const side = P ? 0.56 * W : 0.6 * H, bx = P ? 0.08 * W : 0.07 * W, by = P ? 0.16 * H : 0.2 * H;
    drop(0, bx + side / 2, by + side / 2, () => rect("y", -side / 2, -side / 2, side, side));
    // the ratio, stamped: the first numeral counts up 1, 2, 3 with a mechanical tick
    const n = lt < 0.35 ? 0 : Math.min(3, 1 + Math.floor((lt - 0.35) / 0.3));
    if (n > 0) {
      const sz = side * 0.42, sStamp = 1 + 0.08 * Math.max(0, 1 - (lt - 0.35 - (n - 1) * 0.3) / 0.08);
      push(bx + side / 2, by + side * 0.52, sStamp);
      inkText("k", n + ":1", 0, 0, { size: sz, family: HEAVY, weight: 400, align: "center", baseline: "middle" });
      pop();
    }
    tag(bx + side * 0.12, by + side * 0.1, "gear ratio", 0.2, { size: LBL * U });
    redRing(bx + side / 2, by + side * 0.52, side * 0.6, B.prog(lt, 1.25, 0.35, "inOutQuad"));
    // during the hold, arcs pulse outward from the ring in two mechanical steps
    if (lt > 1.65) {
      const k = Math.floor(((lt - 1.65) / 0.25)) % 3;
      if (k < 2) ring("k", bx + side / 2, by + side * 0.52, side * (0.72 + k * 0.08), 0.5 * U, -0.35, 0.35);
    }
    // amounts: columns of stacked blocks rising one by one
    const blk = P ? 0.07 * H : 0.13 * H, base = P ? 0.79 * H : 0.8 * H;
    const colX = P ? [0.12 * W, 0.56 * W] : [0.58 * W, 0.78 * W];
    for (let i = 0; i < 3; i++) drop(0.35 + i * 0.3, colX[0] + blk / 2, base - blk * (i + 0.5) - i * 0.3 * U, () => rect("r", -blk / 2, -blk / 2, blk, blk));
    drop(1.05, colX[1] + blk / 2, base - blk / 2, () => disc("b", 0, 0, blk / 2));
    const sz = LBL * U;
    if (P) {
      tag(colX[0], 0.535 * H, "small: 3 turns", 1.1, { size: sz, maxW: 0.42 * W });
      tag(colX[1], base - blk - 9 * U, "big: 1 turn", 1.15, { size: sz, maxW: 0.36 * W }); // right on top of its one disc
    } else {
      tag(colX[0], base + 1.2 * U, "small: 3 turns", 1.1, { size: sz });
      tag(colX[1], base - blk - 7 * U, "big: 1 turn", 1.15, { size: sz });
    }
  }

  /** A process station: one primitive, its number knocked out to paper. */
  function station(kind, col, x, y, s, num, at) {
    return drop(at, x, y, () => {
      if (kind === "circle") disc(col, 0, 0, s / 2);
      else if (kind === "square") rect(col, -s / 2, -s / 2, s, s);
      else tri(col, 0, 0, s * 1.1);
      inkText(null, num, 0, kind === "tri" ? s * 0.06 : 0, { size: s * 0.5, family: HEAVY, weight: 400, align: "center", baseline: "middle" });
    });
  }

  function pSteps(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.08] : [0.05, 0.45], P ? [0.43] : [0.84]);
    const s = P ? 0.2 * H : 0.36 * H, sz = LBL * U;
    const c1 = P ? [0.32 * W, 0.26 * H] : [0.22 * W, 0.42 * H], c2 = P ? [0.32 * W, 0.6 * H] : [0.66 * W, 0.42 * H];
    station("circle", "r", c1[0], c1[1], s, "1", 0);
    // a token keeps circling the first station during the hold
    if (lt > 0.4) {
      const a = (lt - 0.4) * 2.6 - Math.PI / 2;
      ring("k", c1[0], c1[1], s * 0.64, 0.3 * U); // the loop the token keeps circling
      disc("k", c1[0] + Math.cos(a) * s * 0.64, c1[1] + Math.sin(a) * s * 0.64, 1.8 * U);
    }
    if (P) barArrow(c1[0], c1[1] + s * 0.62, c2[0], c2[1] - s * 0.6, B.prog(lt, 0.55, 0.35, "outCubic"), 1.4 * U);
    else barArrow(c1[0] + s * 0.62, c1[1], c2[0] - s * 0.6, c2[1], B.prog(lt, 0.55, 0.35, "outCubic"), 1.2 * U);
    station("square", "b", c2[0], c2[1], s, "2", 0.9);
    if (P) {
      tag(0.58 * W, 0.2 * H, "the small wheel spins fast", 0.3, { size: sz, maxW: 0.36 * W });
      tag(0.58 * W, 0.54 * H, "each tooth pushes one tooth of the big wheel", 1.2, { size: sz, maxW: 0.36 * W });
    } else {
      tag(c1[0] - s / 2, c1[1] + s * 0.7, "the small wheel spins fast", 0.3, { size: sz, maxW: 0.32 * W });
      tag(c2[0] - s / 2, c2[1] + s * 0.7, "each tooth pushes one tooth of the big wheel", 1.2, { size: sz, maxW: 0.3 * W });
    }
  }

  function pStep3(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.92] : [0.4, 0.95], P ? [0.42, 0.8] : [0.12]);
    // the chain of stations continues in from the previous panel
    const s = P ? 0.2 * H : 0.38 * H, c = P ? [0.3 * W, 0.25 * H] : [0.2 * W, 0.46 * H];
    if (!P) barArrow(-0.02 * W, c[1], c[0] - s * 0.62, c[1], B.prog(lt, 0, 0.3, "outCubic"), 1.2 * U);
    station("tri", "y", c[0], c[1], s, "3", 0.2);
    const sz = LBL * U;
    if (P) tag(0.54 * W, 0.15 * H, "the big wheel turns 3x slower with 3x the force", 0.4, { size: sz, maxW: 0.34 * W });
    else tag(c[0] - s / 2, c[1] + s * 0.66, "the big wheel turns 3x slower with 3x the force", 0.4, { size: sz, maxW: 0.34 * W });
    // speed vs force as stacked blocks
    // 9:16: the words sit above their columns
    const blk = P ? 0.085 * H : 0.13 * H, base = P ? 0.785 * H : 0.72 * H, xs = P ? [0.12 * W, 0.42 * W] : [0.52 * W, 0.68 * W];
    drop(0.45, xs[0] + blk / 2, base - blk / 2, () => rect("b", -blk / 2, -blk / 2, blk, blk));
    for (let i = 0; i < 3; i++) drop(0.55 + i * 0.1, xs[1] + blk / 2, base - blk * (i + 0.5) - i * 0.3 * U, () => rect("r", -blk / 2, -blk / 2, blk, blk));
    rule(xs[0] - 2 * U, base + 0.3 * U, xs[1] + blk + 2 * U, base + 0.3 * U, B.prog(lt, 0.35, 0.3), 0.5 * U);
    if (lt > 0.9) {
      inkText("k", "speed", xs[0], P ? base - blk - 6 * U : base + 1.4 * U, { size: sz });
      inkText("k", "force", xs[1], P ? base - 3 * blk - 7 * U : base + 1.4 * U, { size: sz });
    }
    tick(P ? 0.78 * W : 0.86 * W, P ? 0.5 * H : 0.42 * H, (P ? 17 : 13) * U, B.prog(lt, 0.75, 0.25));
  }

  function pClose(F, lt) {
    const { W, H, portrait: P } = F;
    panelGrid(F, lt, P ? [0.08, 0.92] : [0.08], P ? [0.82] : [0.86]);
    const hc = P ? [0.5 * W, 0.78 * H, 0.38 * W] : [0.72 * W, 0.84 * H, 0.34 * H];
    drop(0, hc[0], hc[1], () => half("b", 0, 0, hc[2]));
    drop(0.15, hc[0], hc[1] - hc[2] - hc[2] * 0.36, () => gear("r", 0, 0, hc[2] * 0.3, 8, ratchet(lt, 0.8, 0.4, B.TAU / 8)));
    drop(0.3, hc[0] - hc[2] * 1.15, hc[1] - hc[2] * 0.1, () => rect("k", 0, 0, hc[2] * 2.3, 1.4 * U));
    drop(0.35, hc[0] + hc[2] * 0.75, hc[1] - hc[2] * 1.15, () => tri("y", 0, 0, hc[2] * 0.42));
    const size = (P ? 10 : 9) * U, x = P ? 0.1 * W : 0.08 * W, y = P ? 0.16 * H : 0.2 * H;
    ["slow wheel,", "strong wheel."].forEach((ln, i) => drop(0.5 + i * 0.18, x, y + i * size * 1.08, () => inkText(i ? "r" : "k", ln, 0, 0, { size, weight: 700 }), { fall: 2.5, grow: 0 }));
    tag(x, y + size * 2.4, "fewer turns, more turning force", 0.95, { size: (P ? 4.4 : LBL) * U, maxW: P ? 0.8 * W : 0.5 * W });
  }

  const PANELS = [pTitle, pDiagram, pNumber, pSteps, pStep3, pClose];
  /** Once the whole sheet is in view: one caption block, set in frame space, dropped onto the sheet. */
  /** Once the whole sheet is in view: one caption block drops into the title band left blank above the panels. */
  function caption(S, M, t) {
    LT = t - T_CAP;
    if (LT < 0) return;
    all((g) => g.setTransform(M[0], 0, 0, M[0], M[4], M[5]));
    tag(S.cx, S.capY, "speed traded for strength", 0, { size: S.capS, maxW: S.w * 0.84, align: "center" });
  }

  // ------------------------------------------------------------------ the sheet: panels on a grid, a snake path for the camera
  function sheet(W, H) {
    // three across, two down in both aspects. Seen whole (the last frame) the caption and the six panels sit inside
    // the text-safe band, and the paper runs on past them to every edge of the frame.
    const P = H > W, gap = 0.05 * Math.min(W, H), m = 0.07 * Math.min(W, H);
    const origin = [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]].map(([c, r]) => [c * (W + gap), r * (H + gap)]); // reading order
    const sw = 3 * W + 2 * gap, sh = 2 * H + gap, tY = H * (P ? 0.15 : 0.06), bY = H * (P ? 0.79 : 0.94);
    const scr = (P ? 7 : 6) * U, cb = scr * (1.1 * (P ? 2 : 1) + 0.9) + 2 * U, z = Math.min((bY - tY - cb) / sh, (0.97 * W) / sw);
    const x0 = sw / 2 - W / 2 / z, y0 = -(tY + cb) / z;
    return { P, origin, m, x0, y0, w: W / z, h: H / z, cx: sw / 2, cy: sh / 2, capY: y0 + tY / z, capS: scr / z };
  }
  function camera(S, W, H, t) {
    let [x, y] = [S.origin[0][0] + W / 2, S.origin[0][1] + H / 2];
    for (let i = 1; i < PANELS.length; i++) {
      // track to the next panel and come to a firm stop
      const k = B.span(t, BEATS[i] - 0.55, BEATS[i] - 0.02, "inOutCubic");
      x = B.lerp(x, S.origin[i][0] + W / 2, k);
      y = B.lerp(y, S.origin[i][1] + H / 2, k);
    }
    const k = B.span(t, T_PULL[0], T_PULL[1], "inOutCubic"), zfit = Math.min(W / S.w, H / S.h);
    return { x: B.lerp(x, S.x0 + S.w / 2, k), y: B.lerp(y, S.y0 + S.h / 2, k), z: Math.exp(B.lerp(0, Math.log(zfit), k)) };
  }
  /** The worn poster sheet (cached, half resolution): cream to tan edges, fibre streaks, age spots, mottle. */
  function paperSheet(S, W, H) {
    const ps = 0.5;
    return B.layer("bh-paper:" + W + "x" + H, S.w * ps, S.h * ps, (g, w, h) => {
      g.fillStyle = PAL.paper;
      g.fillRect(0, 0, w, h);
      const e = Math.min(w, h) * 0.06;
      [[0, 0, e, 0], [w, 0, w - e, 0], [0, 0, 0, e], [0, h, 0, h - e]].forEach(([x0, y0, x1, y1]) => {
        g.fillStyle = B.linear(g, x0, y0, x1, y1, [B.rgba(PAL.age, 0.75), B.rgba(PAL.age, 0)]);
        g.fillRect(0, 0, w, h);
      });
      B.mottle(g, w, h, { amount: 0.05, feature: 0.08, seed: 17, mode: "multiply" });
      const r = B.rng(171);
      for (let i = 0; i < (w * h) / 900; i++) {
        // fibre streaks: short faint lines, mostly along the sheet
        const x = r() * w, y = r() * h, l = r.range(4, 18), a = r.gauss(0, 0.35);
        g.strokeStyle = r.chance(0.5) ? "rgba(255,250,235,0.35)" : "rgba(150,120,80,0.16)";
        g.lineWidth = r.range(0.4, 1.1);
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l);
        g.stroke();
      }
      for (let i = 0; i < 70; i++) {
        // small soft brown age spots
        const x = r() * w, y = r() * h, rr = r.range(1, 5);
        g.fillStyle = B.radial(g, x, y, 0, rr, [B.rgba("#9a7040", r.range(0.15, 0.35)), B.rgba("#9a7040", 0)]);
        g.fillRect(x - rr, y - rr, rr * 2, rr * 2);
      }
    });
  }
  /** Value noise that wraps every `period` cells, so a texture tile repeats without seams. */
  function loopNoise(x, y, period, seed) {
    const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
    const v = (i, j) => B.hash01(((i % period) + period) % period, ((j % period) + period) % period, seed);
    const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    return B.lerp(B.lerp(v(xi, yi), v(xi + 1, yi), sx), B.lerp(v(xi, yi + 1), v(xi + 1, yi + 1), sx), sy);
  }
  /** Ink mottle tile: soft cloudy coverage loss (alpha up to ~0.2) plus rare pinholes, used with destination-out. */
  function mottleTile() {
    return B.layer("bh-inkmottle", 256, 256, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(5);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const v = 0.55 * loopNoise((x / w) * 4, (y / h) * 4, 4, 1) + 0.3 * loopNoise((x / w) * 9, (y / h) * 9, 9, 2) + 0.15 * loopNoise((x / w) * 23, (y / h) * 23, 23, 3);
          d[(y * w + x) * 4 + 3] = Math.round(B.clamp((v - 0.35) * 1.6) * 0.2 * 255);
        }
      for (let k = 0; k < 10; k++) {
        const i = (r.int(0, h - 1) * w + r.int(0, w - 1)) * 4;
        d[i + 3] = 255;
      }
      g.putImageData(img, 0, 0);
    });
  }
  /** One vertical and one horizontal fold crease across the sheet: a narrow pale-then-dark band with scuffs. */
  function creases(ctx, S) {
    const cr = [[S.x0 + S.w * 0.47, true], [S.y0 + S.h * 0.53, false]];
    for (const [p, vert] of cr) {
      const w = 0.9 * U;
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      ctx.fillStyle = "rgba(255,248,230,0.28)";
      vert ? ctx.fillRect(p - w, S.y0, w, S.h) : ctx.fillRect(S.x0, p - w, S.w, w);
      ctx.globalCompositeOperation = "multiply";
      ctx.fillStyle = "rgba(120,90,55,0.22)";
      vert ? ctx.fillRect(p, S.y0, w * 0.7, S.h) : ctx.fillRect(S.x0, p, S.w, w * 0.7);
      const r = B.rng(vert ? 3 : 4);
      ctx.globalCompositeOperation = "screen";
      ctx.fillStyle = "rgba(255,248,230,0.45)";
      for (let i = 0; i < 60; i++) {
        const q = r() * (vert ? S.h : S.w), o = r.gauss(0, w * 0.8);
        vert ? ctx.fillRect(p + o, S.y0 + q, r.range(0.5, 2) * U * 0.3, r.range(1, 4) * U * 0.3) : ctx.fillRect(S.x0 + q, p + o, r.range(1, 4) * U * 0.3, r.range(0.5, 2) * U * 0.3);
      }
      ctx.restore();
    }
  }

  // ------------------------------------------------------------------ the frame: four plates, then print them off register
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    U = F.u;
    const S = sheet(W, H), cam = camera(S, W, H, t);
    const M = [cam.z, 0, 0, cam.z, W / 2 - cam.x * cam.z, H / 2 - cam.y * cam.z];
    ctx.fillStyle = PAL.k;
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(...M);
    ctx.drawImage(paperSheet(S, W, H), S.x0, S.y0, S.w, S.h);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    L = {};
    KEYS.forEach((k) => (L[k] = B.scratch("bh-plate-" + k, W, H)));
    HIDE = B.span(t, T_PULL[0], T_PULL[1], "inOutCubic") > 0.5; // the labels lift off halfway through the pull-out
    PANELS.forEach((panel, i) => {
      const [ox, oy] = S.origin[i];
      const sx = M[4] + ox * cam.z, sy = M[5] + oy * cam.z;
      if (sx > W || sy > H || sx + W * cam.z < 0 || sy + H * cam.z < 0) return; // off camera
      all((g) => g.setTransform(cam.z, 0, 0, cam.z, sx, sy));
      push(0, 0);
      LT = t - BEATS[i];
      panel(F, LT);
      pop();
    });
    HIDE = false;
    caption(S, M, t);
    // ink mottle on each plate (sheet space, so it travels with the paper), then print with each plate's nudge
    const tile = mottleTile();
    KEYS.forEach((k, j) => {
      const g = L[k];
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.globalCompositeOperation = "destination-out";
      const pat = g.createPattern(tile, "repeat");
      pat.setTransform(new DOMMatrix([cam.z * 2.2, 0, 0, cam.z * 2.2, M[4] + j * 97 * cam.z, M[5] + j * 61 * cam.z]));
      g.fillStyle = pat;
      g.fillRect(0, 0, W, H);
      g.globalCompositeOperation = "source-over";
    });
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    KEYS.forEach((k) => ctx.drawImage(L[k].canvas, NUDGE[k][0] * U * Math.max(cam.z, 0.5), NUDGE[k][1] * U * Math.max(cam.z, 0.5)));
    ctx.restore();
    ctx.save();
    ctx.setTransform(...M);
    creases(ctx, S);
    ctx.restore();
    B.grain(ctx, W, H, { amount: 0.045, t, fps: 12, mode: "overlay" });
    B.vignette(ctx, W, H, { color: "#8a6238", amount: 0.22, inner: 0.45, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: wooden blocks, type being set, a numbering clack, sheet slides, marimba
  SOUND.define("bauhaus-block", (v) => {
    // a wooden block set down on a table: a hollow knock with a little body
    v.tone({ type: "triangle", f: 620, f2: 380, glide: 0.03, a: 0.001, len: 0.07, peak: 0.45 });
    v.tone({ f: 170, f2: 120, glide: 0.06, a: 0.002, len: 0.12, peak: 0.35 });
    v.noise({ filter: "bandpass", f: 1500, q: 1.5, a: 0.0006, len: 0.025, peak: 0.25 });
  }, { verb: 0.18 });
  SOUND.define("bauhaus-type", (v) => {
    // a dry metal tap of type being set
    v.tone({ type: "square", f: 3100, a: 0.0004, len: 0.012, peak: 0.06 });
    v.noise({ filter: "highpass", f: 3500, a: 0.0004, len: 0.02, peak: 0.3 });
  }, { verb: 0.08 });
  SOUND.define("bauhaus-clack", (v) => {
    // numbering machine: a crisp double clack
    v.noise({ filter: "bandpass", f: 2400, q: 2, a: 0.0005, len: 0.02, peak: 0.5 });
    v.noise({ at: 0.035, filter: "bandpass", f: 1700, q: 2, a: 0.0005, len: 0.03, peak: 0.4 });
    v.tone({ at: 0.035, f: 240, f2: 150, glide: 0.04, a: 0.001, len: 0.05, peak: 0.2 });
  }, { verb: 0.1 });
  SOUND.define("bauhaus-slide", (v, o) => {
    // a large sheet sliding across a drafting table, halting against a wooden stop
    const d = v.dur ?? 0.5;
    v.noise({ filter: "bandpass", f: 900, f2: 1500, glide: d, q: 0.7, a: d * 0.4, hold: d * 0.3, len: d * 0.3, peak: 0.22 });
    v.grains({ span: d, count: 24, filter: "highpass", f: 3000, len: 0.004, peak: 0.05 });
    v.tone({ at: d, f: 140, f2: 95, glide: 0.05, a: 0.001, len: 0.1, peak: 0.35 });
    v.noise({ at: d, filter: "bandpass", f: 900, q: 1.2, a: 0.0005, len: 0.03, peak: 0.3 });
  }, { verb: 0.12 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.5 });
    const blk = (t, p = 0) => k.at(t, "bauhaus-block", { pitch: p, gain: 0.85 });
    BEATS.slice(1).forEach((b) => k.at(b - 0.55, "bauhaus-slide", { dur: 0.53, gain: 0.8 }));
    k.at(T_PULL[0], "bauhaus-slide", { dur: T_PULL[1] - T_PULL[0], gain: 0.6, pitch: -4 });
    // title: rules, disc, gear, square, letters, tag
    k.repeat(0.05, 0.08, 3, "bauhaus-type", { gain: 0.4 });
    blk(0.3, -5); blk(0.5, 2); blk(0.62, 5);
    for (let i = 0; i < 4; i++) k.at(0.6 + i * 0.16, "bauhaus-type", { pitch: i, gain: 0.9 }).at(0.65 + i * 0.16, "bauhaus-block", { pitch: 7 - i, gain: 0.4 });
    blk(1.15, 3);
    k.repeat(1.4, 0.5, 2, "click", { gain: 0.35 });
    // diagram: two gears, ratchet clicks, tags
    let b = BEATS[1];
    blk(b, 4); blk(b + 0.2, -6);
    k.repeat(b + 0.55, 0.45, 4, "click", { gain: 0.4, pitch: -3 });
    blk(b + 0.7, 2); blk(b + 1.0, 1); blk(b + 1.4, 3);
    // key number: block, three clacks with rising blocks, ring, marimba
    b = BEATS[2];
    blk(b, -3);
    for (let i = 0; i < 3; i++) k.at(b + 0.35 + i * 0.3, "bauhaus-clack").at(b + 0.35 + i * 0.3, "bauhaus-block", { pitch: 2 + i * 2, gain: 0.5 });
    blk(b + 1.05, -2); blk(b + 1.1, 4); blk(b + 1.15, 4);
    k.seq(b + 1.25, 0.12, ["C5", "E5", "G5"], { voice: "marimba", gain: 0.6 });
    // steps
    b = BEATS[3];
    blk(b, 0); blk(b + 0.3, 3); k.at(b + 0.55, "swish", { gain: 0.25 }); blk(b + 0.9, -4); blk(b + 1.2, 3);
    b = BEATS[4];
    k.at(b, "swish", { gain: 0.25 }); blk(b + 0.2, 5); blk(b + 0.4, 3); blk(b + 0.6, -3);
    for (let i = 0; i < 3; i++) blk(b + 0.72 + i * 0.12, i * 2);
    k.seq(b + 1.1, 0.1, ["E5", "A5"], { voice: "marimba", gain: 0.55 });
    // close
    b = BEATS[5];
    blk(b, -7); blk(b + 0.15, 2); blk(b + 0.3, -1); blk(b + 0.35, 6);
    k.at(b + 0.5, "bauhaus-type").at(b + 0.68, "bauhaus-type", { pitch: 2 });
    blk(b + 0.95, 3);
    k.chord(T_PULL[1] - 0.2, ["C4", "G4", "E5"], { voice: "marimba", strum: 0.07, gain: 0.6 });
    blk(T_CAP, -4); blk(T_CAP + 0.05, 3);
  }

  Player.register({
    id: "bauhaus",
    name: "Bauhaus Geometry",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Jost:wght@500;600;700&family=Archivo+Black&display=swap",
      faces: ['700 20px "Jost"', '600 20px "Jost"', '400 20px "Archivo Black"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close + whole sheet"],
    stills: [1.7, 3.95, 6.1, 8.1, 10.0, 13.6],
    draw,
    score,
  });
})();
