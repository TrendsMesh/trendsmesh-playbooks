/* 19 Kinetic Type - reference animation.
 * Topic (setting, replace it): "Count the thunder" - light arrives at once, sound at about 343 m/s, so every 3 seconds
 * between flash and boom is about 1 km.
 * Rendering (keep it): a music video made of words. Near-black ground, one acid-yellow ink. Huge condensed capitals
 * fitted to their boxes and stacked so lines touch; in a stack one word solid, one outline only, one stretched unevenly
 * and filled with a 45-degree dot screen picture (dot size follows brightness) inside a thin outline. Tab blocks are
 * yellow with black letters. Filled words carry speed lines cut out of their lower third and a band shoved sideways
 * with thin rule ticks. Small labels are bold mono in yellow tags.
 * Finish: light moving video grain; a jolt of the whole frame on every slam; a flash-frame ink/ground inversion on the
 * three biggest hits; faint outline echoes fanning behind moving words.
 * Motion: locked to a beat grid (2 beats a second): words punch in with a two-frame squash, whip in with echoes, tab
 * blocks wipe up, the dot picture develops dot by dot; scene changes are a slice-glitch tear or a whip-pan; the opening
 * stack shrinks into a small corner header that stays.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { ground: "#0e0e0d", ink: "#e2fb36", echo: "#3a4214", shadow: "#6b7a1e" };
  const DISP = "Big Shoulders Display", MONO = "JetBrains Mono";
  const DUR = 12, BPS = 2; // two beats a second
  const BEATS = [0, 2.5, 5.0, 7.0, 9.25, 10.0];
  const SCENE_AT = [0, 2.5, 5.0, 7.0, 10.0];
  const TRANS = [{ at: 2.5, kind: "tear" }, { at: 5.0, kind: "whip", dir: 1 }, { at: 7.0, kind: "tear" }, { at: 10.0, kind: "whip", dir: -1 }];
  const TR_LEN = 0.32; // a little past the next scene's first slam (0.25 s in), so no frame is ever bare
  // hits (for the shake and the score): word slams, labels, chart bars, and the three biggest (inversion flash)
  const SLAMS = [0.25, 0.75, 1.25, 2.75, 3.75, 4.25, 5.25, 5.5, 5.75, 6.0, 7.25, 7.75, 9.5, 10.25, 10.37, 10.5, 10.62, 10.75];
  const TAGS = [1.75, 3.0, 4.0, 4.5, 6.25, 7.4, 7.9, 9.5, 11.25];
  const BARS = [7.95, 8.2, 8.45, 8.7, 8.95, 9.2];
  const KEY = [5.75, 9.5, 10.75];
  const HDR_AT = 2.1, HDR_IN = 0.3; // the title stack shrinks into the corner header

  let T = 0, U = 1, F = null, MEASURE = false; // MEASURE: lay out only, draw nothing

  // ------------------------------------------------------------------ fitted type (reuse these)
  const meas = () => B.scratch("kt-measure", 4, 4);
  /** Ink bounds of a word at 100 px. */
  function measure(str, weight) {
    const g = meas();
    g.font = B.font(100, DISP, weight);
    g.textAlign = "left";
    g.textBaseline = "alphabetic";
    const m = g.measureText(str);
    const l = m.actualBoundingBoxLeft, r = m.actualBoundingBoxRight, a = m.actualBoundingBoxAscent, d = m.actualBoundingBoxDescent;
    return { l, a, w: Math.max(1, l + r), h: Math.max(1, a + d) };
  }
  /** Fit a word's ink to a box: uniformly (as large as fits), or stretched unevenly to fill it exactly. */
  function fitBox(str, weight, box, stretch = false, align = "left") {
    const m = measure(str, weight);
    let sx = box.w / m.w, sy = box.h / m.h;
    if (!stretch) sx = sy = Math.min(sx, sy);
    const w = m.w * sx, h = m.h * sy;
    const x = align === "center" ? box.x + (box.w - w) / 2 : align === "right" ? box.x + box.w - w : box.x;
    return { x, y: box.y, w, h, sx, sy, m, str, weight };
  }
  /** Lay several words on one row at a common height so their ink spans the row. gap: px, or per-gap fractions of the row height. */
  function rowFit(items, box, gap) {
    const ms = items.map((it) => measure(it.str, it.weight)), ratio = ms.reduce((a, m) => a + m.w / m.h, 0);
    const fr = Array.isArray(gap), ga = fr ? 0 : gap, gs = fr ? gap.reduce((a, b) => a + b, 0) : 0;
    const h = Math.min(box.h, (box.w - ga * (items.length - 1)) / (ratio + gs));
    let x = box.x;
    return items.map((it, i) => {
      const w = (ms[i].w / ms[i].h) * h, b = { x, y: box.y, w, h };
      x += w + (fr ? (gap[i] || 0) * h : ga);
      return b;
    });
  }
  function paintText(g, f, mode, color, lw) {
    g.save();
    g.translate(f.x, f.y);
    g.scale(f.sx, f.sy);
    g.translate(f.m.l, f.m.a);
    g.font = B.font(100, DISP, f.weight);
    g.textAlign = "left";
    g.textBaseline = "alphabetic";
    if (mode === "fill") {
      g.fillStyle = color;
      g.fillText(f.str, 0, 0);
    } else {
      g.strokeStyle = color;
      g.lineWidth = lw / Math.sqrt(f.sx * f.sy);
      g.lineJoin = "miter";
      g.strokeText(f.str, 0, 0);
    }
    g.restore();
  }
  /** Entry at time `at`: "slam" (two-frame squash, then held), "whipR"/"whipL" (in from the side), else instant. */
  function entry(at, kind = "slam") {
    const dt = T - at;
    if (dt < 0) return null;
    if (kind === "slam") {
      if (dt < 1 / 24) return { s: 1.28, sy: 0.74, dx: 0, echo: 1 };
      if (dt < 2 / 24) return { s: 1.07, sy: 0.92, dx: 0, echo: 0.8 };
      return { s: 1, sy: 1, dx: 0, echo: B.clamp(1 - (dt - 2 / 24) / 0.2) * 0.6 };
    }
    if (kind === "whipR" || kind === "whipL") {
      const p = B.clamp(dt / 0.14), dir = kind === "whipR" ? 1 : -1;
      return { s: 1, sy: 1, dx: dir * (1 - B.ease.outExpo(p)) * F.W * 0.9, echo: B.clamp(1 - dt / 0.16), dir }; // echoes only while it travels
    }
    return { s: 1, sy: 1, dx: 0, echo: 0 };
  }
  /** Apply an entry to a fitted word: scale about its centre, shift sideways. */
  function moved(f, e, extra = 1) {
    const cx = f.x + f.w / 2, cy = f.y + f.h / 2, s = e.s * extra, sy = e.sy;
    return { ...f, x: cx + (f.x - cx) * s + e.dx, y: cy + (f.y - cy) * s * sy, w: f.w * s, h: f.h * s * sy, sx: f.sx * s, sy: f.sy * s * sy };
  }
  /** The picture inside the dot-screen word: a storm cloud lit by a jagged bolt (brightness 0..1, box coords u, v). */
  const BOLT = [[0, 0.55], [0.28, 0.44], [0.4, 0.57], [0.66, 0.46], [0.8, 0.53], [1, 0.48]];
  function stormPicture(u, v) {
    let bx = BOLT[0][1];
    for (let i = 1; i < BOLT.length; i++) if (v <= BOLT[i][0]) { bx = B.lerp(BOLT[i - 1][1], BOLT[i][1], (v - BOLT[i - 1][0]) / (BOLT[i][0] - BOLT[i - 1][0])); break; }
    const d = (u - bx) * 3.2;
    const cloud = 0.2 + 0.5 * B.clamp(B.fbm(u * 5 + 2, v * 2.5, 3, 4) * 0.5 + 0.55) * (1.15 - v * 0.9);
    return B.clamp(cloud + 0.95 * Math.exp(-(d * d) / 0.0016) + 0.3 * Math.exp(-(d * d) / 0.02));
  }
  /** Dot-screen word: a 45-degree screen of the picture, dot size by brightness, developing dot by dot, clipped to the
   * letters, with a thin outline keeping them readable. */
  function dotsWord(g, f, develop, seed = 1) {
    const sc = B.scratch("kt-dots", F.W, F.H), cell = 1.55 * U, ang = Math.PI / 4, ca = Math.cos(ang), sa = Math.sin(ang);
    const cx = f.x + f.w / 2, cy = f.y + f.h / 2, n = Math.ceil(Math.hypot(f.w, f.h) / 2 / cell) + 1;
    const ink = [], dim = [];
    for (let i = -n; i <= n; i++)
      for (let j = -n; j <= n; j++) {
        const px = cx + (i * ca - j * sa) * cell, py = cy + (i * sa + j * ca) * cell;
        if (px < f.x - cell || px > f.x + f.w + cell || py < f.y - cell || py > f.y + f.h + cell) continue;
        if (B.hash01(i, j, seed) > develop * 1.25 - 0.05) continue; // not developed yet
        const tone = stormPicture((px - f.x) / f.w, (py - f.y) / f.h);
        const r = cell * 0.62 * Math.sqrt(tone);
        if (r < 0.15 * U) continue;
        (tone > 0.36 ? ink : dim).push(px, py, r);
      }
    for (const [list, col] of [[dim, PAL.shadow], [ink, PAL.ink]]) {
      sc.fillStyle = col;
      sc.beginPath();
      for (let k = 0; k < list.length; k += 3) {
        sc.moveTo(list[k] + list[k + 2], list[k + 1]);
        sc.arc(list[k], list[k + 1], list[k + 2], 0, B.TAU);
      }
      sc.fill();
    }
    sc.globalCompositeOperation = "destination-in";
    paintText(sc, f, "fill", "#000");
    sc.globalCompositeOperation = "source-over";
    g.drawImage(sc.canvas, 0, 0);
    paintText(g, f, "stroke", PAL.ink, 0.22 * U);
  }
  /** Speed lines cut out of a filled word's lower third (thin ground-colour rules across it). */
  function speedLines(g, f) {
    g.fillStyle = PAL.ground;
    [0.7, 0.78, 0.85, 0.91].forEach((k, i) => g.fillRect(f.x - U, f.y + f.h * k, f.w + 2 * U, (0.18 + i * 0.08) * U));
  }
  /**
   * A word, entering at o.at. o: { style "solid" | "outline" | "dots", weight 900, enter "slam", stretch, align, speed
   * (speed lines), slice { at, v0, v1, dx } (band shoved sideways), develop (dots: seconds to develop) }.
   */
  function word(g, str, box, o = {}) {
    const f0 = fitBox(str, o.weight ?? 900, box, !!o.stretch, o.align);
    const e = entry(o.at ?? 0, o.enter ?? "slam");
    if (!e || MEASURE) return f0;
    const f = moved(f0, e);
    // strobe echoes: faint outline copies fanning out behind the word, fading as it settles
    if (e.echo > 0.02) {
      for (let k = 1; k <= 3; k++) {
        const fe = e.dir ? { ...f, x: f.x + e.dir * k * 3.5 * U * (0.3 + e.echo) } : moved(f0, e, 1 + k * 0.06 * e.echo);
        paintText(g, fe, "stroke", PAL.echo, 0.3 * U);
      }
    }
    const style = o.style ?? "solid";
    const sliced = o.slice && T >= o.slice.at;
    const target = sliced ? B.scratch("kt-slice", F.W, F.H) : g;
    if (style === "solid") {
      paintText(target, f, "fill", PAL.ink);
      if (o.speed) speedLines(target, f);
    } else if (style === "outline") paintText(target, f, "stroke", PAL.ink, (o.lw ?? 0.45) * U);
    else dotsWord(target, f, B.prog(T, (o.at ?? 0) + 0.05, o.develop ?? 0.7), o.seed);
    if (sliced) {
      // a band sliced out and shoved sideways, with short thin rule ticks beside the cut
      const y0 = f.y + f.h * o.slice.v0, y1 = f.y + f.h * o.slice.v1, dx = o.slice.dx * U;
      g.save();
      g.beginPath();
      g.rect(0, 0, F.W, y0);
      g.rect(0, y1, F.W, F.H - y1);
      g.clip();
      g.drawImage(target.canvas, 0, 0);
      g.restore();
      g.save();
      g.beginPath();
      g.rect(0, y0, F.W, y1 - y0);
      g.clip();
      g.drawImage(target.canvas, dx, 0);
      g.restore();
      g.fillStyle = PAL.ink;
      const tx = dx > 0 ? f.x - 1.5 * U : f.x + f.w + 0.5 * U;
      for (let k = 0; k < 3; k++) g.fillRect(tx - (dx > 0 ? k * 1.4 * U : -k * 1.4 * U), y0 - 0.9 * U, 0.18 * U, 0.7 * U);
      for (let k = 0; k < 3; k++) g.fillRect(tx - (dx > 0 ? k * 1.4 * U : -k * 1.4 * U) + dx, y1 + 0.2 * U, 0.18 * U, 0.7 * U);
    }
    return f;
  }
  /** Small mono label: yellow tag, black text, falling onto its target. Returns its size. */
  function tag(g, str, x, y, at, o = {}) {
    const dt = T - at;
    if (dt < 0) return { w: 0, h: 0 };
    const size = o.size ?? (F.portrait ? 4.2 : 4.0) * U, pad = size * 0.45; // never under 3.8 % of the short side
    g.save();
    g.font = B.font(size, MONO, 800);
    const w = g.measureText(str).width + 2 * pad, h = size * 1.5;
    const dy = dt < 0.1 ? -Math.pow(1 - dt / 0.1, 2) * 6 * U : 0;
    const ox = o.align === "right" ? -w : 0;
    g.translate(x + ox + w / 2, y + dy + h / 2);
    if (o.rot) g.rotate(o.rot);
    g.fillStyle = PAL.ink;
    g.fillRect(-w / 2, -h / 2, w, h);
    g.fillStyle = PAL.ground;
    g.textBaseline = "middle";
    g.textAlign = "center";
    g.fillText(str, 0, size * 0.06);
    g.restore();
    return { w, h };
  }
  /** Tab block: a solid yellow rectangle with black letters, wiped up from below, often tilted a few degrees. */
  function tab(g, str, box, at, rot = 0) {
    const dt = T - at;
    if (dt < 0 || MEASURE) return;
    const p = B.clamp(dt / 0.1);
    g.save();
    g.font = B.font(100, MONO, 800);
    const size = Math.min(box.h * 0.6, (box.w * 0.9 * 100) / g.measureText(str).width);
    g.translate(box.x + box.w / 2, box.y + box.h / 2);
    g.rotate(rot);
    g.beginPath();
    g.rect(-box.w / 2, box.h / 2 - box.h * p, box.w, box.h * p);
    g.clip();
    g.fillStyle = PAL.ink;
    g.fillRect(-box.w / 2, -box.h / 2, box.w, box.h);
    g.fillStyle = PAL.ground;
    g.font = B.font(size, MONO, 800);
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(str, 0, size * 0.05);
    g.restore();
  }
  /** Heavy straight rule with a solid chevron head, drawn out from its start (p 0..1). */
  function heavyArrow(g, x0, y0, x1, y1, p, w) {
    if (p <= 0) return;
    const a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0) * p, hl = w * 2.4;
    g.save();
    g.translate(x0, y0);
    g.rotate(a);
    g.fillStyle = PAL.ink;
    g.fillRect(0, -w / 2, Math.max(0, L - hl * 0.6), w);
    g.beginPath();
    B.poly(g, [[L, 0], [L - hl, -hl * 0.85], [L - hl * 0.6, 0], [L - hl, hl * 0.85]], true);
    g.fill();
    g.restore();
  }

  // ------------------------------------------------------------------ layout
  function area() {
    const S = F.safe, top = S.y + hdrH() + 2.5 * U;
    return { x: S.x, y: top, w: S.w, h: S.b - top };
  }
  const hdrH = () => (F.portrait ? 19 : 8.5) * U; // tall enough that the header's smallest word stays readable
  const GAP = () => 0.7 * U; // stacked lines touch

  // ------------------------------------------------------------------ scene 0: the opening stack (also the corner header)
  function titleStack(g, map, done) {
    const S = F.safe, P = F.portrait, gp = GAP();
    const M = (b) => map(b);
    const at = (x) => (done ? -10 : x);
    if (P) {
      const f1 = fitBox("COUNT", 900, { x: S.x, y: S.y + 0.03 * S.h, w: S.w, h: 0.38 * S.h });
      word(g, "COUNT", M({ x: f1.x, y: f1.y, w: f1.w, h: f1.h }), { at: at(0.25), speed: !done }); // the header: plain solid words
      const r2y = f1.y + f1.h + gp;
      const f2 = fitBox("THE", 900, { x: S.x, y: r2y, w: S.w * 0.5, h: 0.19 * S.h });
      word(g, "THE", M({ x: f2.x, y: f2.y, w: f2.w, h: f2.h }), { at: at(0.75), style: done ? "solid" : "outline" });
      const r3y = f2.y + f2.h + gp;
      const h3 = S.b - r3y - 0.5 * U; // the stretched word takes all the height that is left
      word(g, "THUNDER", M({ x: S.x, y: r3y, w: S.w, h: h3 }), { at: at(1.25), style: done ? "solid" : "dots", stretch: true, develop: 0.75 });
      if (!done) tab(g, "A 3-SECOND RULE", { x: f2.x + f2.w + 3 * U, y: r2y + f2.h * 0.25, w: S.r - (f2.x + f2.w + 3 * U), h: f2.h * 0.5 }, 1.75, -0.05);
      return { x: S.x, y: S.y + 0.03 * S.h, w: S.w, h: r3y + h3 - (S.y + 0.03 * S.h) };
    }
    // a real word space between COUNT and THE (it scales with the stack, so the corner header keeps one too)
    const row = rowFit([{ str: "COUNT", weight: 900 }, { str: "THE", weight: 900 }], { x: S.x, y: S.y + 0.02 * S.h, w: S.w, h: 0.5 * S.h }, 0.12 * S.h);
    word(g, "COUNT", M(row[0]), { at: at(0.25), speed: !done });
    word(g, "THE", M(row[1]), { at: at(0.75), style: done ? "solid" : "outline" });
    const r2y = row[0].y + row[0].h + gp;
    word(g, "THUNDER", M({ x: S.x, y: r2y, w: S.w, h: 0.42 * S.h }), { at: at(1.25), style: done ? "solid" : "dots", stretch: true, develop: 0.75 });
    // the tab gets its own line under the stack, filling the frame's foot and covering no letter
    const ty = r2y + 0.42 * S.h + 2 * gp;
    if (!done) tab(g, "A 3-SECOND RULE", { x: S.x + 0.5 * S.w, y: ty, w: 0.5 * S.w, h: Math.min(0.13 * S.h, S.b - ty) }, 1.75, -0.03);
    return { x: S.x, y: S.y + 0.02 * S.h, w: S.w, h: r2y + 0.42 * S.h - (S.y + 0.02 * S.h) };
  }
  let STACK = null; // the stack's full bounds, measured on the first draw of a frame
  function headerMap(k) {
    // map the full stack into a small corner header (k = 0 full size .. 1 header)
    const S = F.safe, b = STACK, sc = B.lerp(1, hdrH() / b.h, k);
    const ox = B.lerp(b.x, S.x, k), oy = B.lerp(b.y, S.y, k);
    return (r) => ({ x: ox + (r.x - b.x) * sc, y: oy + (r.y - b.y) * sc, w: r.w * sc, h: r.h * sc });
  }
  function sceneTitle(g) {
    const k = B.ease.inExpo(B.prog(T, HDR_AT, HDR_IN));
    titleStack(g, headerMap(k), false);
  }

  // ------------------------------------------------------------------ scene 1: flash and boom (labelled diagram with an arrow)
  function sceneDiagram(g) {
    const A = area(), P = F.portrait;
    const fb = P ? { x: A.x, y: A.y, w: A.w, h: 0.34 * A.h } : { x: A.x, y: A.y, w: 0.55 * A.w, h: 0.45 * A.h };
    const bb = P ? { x: A.x, y: A.y + 0.6 * A.h, w: 0.94 * A.w, h: 0.3 * A.h } : { x: A.x + 0.45 * A.w, y: A.y + 0.5 * A.h, w: 0.55 * A.w, h: 0.45 * A.h };
    const ff = word(g, "FLASH", fb, { at: 2.75, speed: true });
    tag(g, "LIGHT: INSTANT", ff.x, ff.y + ff.h + 1.5 * U, 3.0);
    const bf = fitBox("BOOM", 900, bb, false, P ? "left" : "right");
    if (T < 4.25) word(g, "BOOM", bb, { at: 3.75, style: "outline", align: P ? "left" : "right" });
    else word(g, "BOOM", bb, { at: 4.25, align: P ? "left" : "right", speed: true, slice: { at: 4.5, v0: 0.4, v1: 0.56, dx: P ? 3 : -3 } }); // shoved inward, never off the frame
    if (P) tag(g, "SOUND: 343 M/S", bf.x, bf.y + bf.h + 1.5 * U, 4.0);
    else tag(g, "SOUND: 343 M/S", bf.x + bf.w, bf.y - 7.5 * U, 4.0, { align: "right" });
    // the delay between them: a heavy arrow, labelled
    const p = B.prog(T, 3.25, 0.25);
    if (P) {
      const x = A.x + 0.72 * A.w, y0 = ff.y + ff.h + 2 * U, y1 = bf.y - 2 * U;
      heavyArrow(g, x, y0, x, y1, p, 2.2 * U);
      tag(g, "DELAY", x - 4 * U, (y0 + y1) / 2 - 2 * U, 4.5, { align: "right" });
    } else {
      const x0 = ff.x + ff.w * 0.75, y0 = ff.y + ff.h + 7 * U, x1 = bf.x - 3 * U, y1 = bf.y + bf.h * 0.5;
      heavyArrow(g, x0, y0, x1, y1, p, 1.8 * U);
      tag(g, "DELAY", x0 - 16 * U, (y0 + y1) / 2 + 2 * U, 4.5);
    }
  }

  // ------------------------------------------------------------------ scene 2: the key number
  function sceneNumber(g) {
    const A = area(), P = F.portrait;
    const digit = T >= 5.75 ? "3" : T >= 5.5 ? "2" : "1";
    const at = T >= 5.75 ? 5.75 : T >= 5.5 ? 5.5 : 5.25;
    const nb = P ? { x: A.x, y: A.y, w: A.w * 0.72, h: 0.64 * A.h } : { x: A.x, y: A.y, w: 0.36 * A.w, h: A.h * 0.95 };
    const nf = word(g, digit, nb, { at, speed: digit === "3", slice: digit === "3" ? { at: 6.5, v0: 0.3, v1: 0.42, dx: 5 } : null });
    const sb = P ? { x: A.x, y: nf.y + nf.h + GAP(), w: A.w, h: A.y + A.h - nf.y - nf.h - GAP() } : { x: nf.x + nf.w + 3 * U, y: A.y + 0.08 * A.h, w: A.x + A.w - (nf.x + nf.w + 3 * U), h: 0.42 * A.h };
    word(g, "SECONDS", sb, { at: 6.0, enter: "whipR", style: "outline" });
    const tb = P ? { x: A.x + 0.5 * A.w, y: A.y + 0.36 * A.h, w: 0.5 * A.w, h: 0.12 * A.h } : { x: sb.x + 2 * U, y: A.y + 0.6 * A.h, w: sb.w * 0.8, h: 0.2 * A.h };
    tab(g, "= 1 KM", tb, 6.25, -0.07);
  }

  // ------------------------------------------------------------------ scene 3: three steps, bars rising one per half beat
  function sceneSteps(g) {
    const A = area(), P = F.portrait, gp = GAP();
    let r1, r2, r3, bars, D = 0;
    // step 3 makes room for its answer: 9:16 whips the column up (rows 1-2 leave the top), 16:9 shortens the bars
    const k3 = B.ease.inOutCubic(B.prog(T, 9.3, 0.17));
    if (P) {
      r1 = { x: A.x, y: A.y + 7.5 * U, w: 0.62 * A.w, h: 0.16 * A.h };
      r2 = { x: A.x, y: r1.y + r1.h + gp + 7.5 * U, w: 0.8 * A.w, h: 0.16 * A.h };
      bars = { x: A.x, y: r2.y + r2.h + 3 * U, w: A.w };
      bars.h = A.y + A.h - bars.y - 2 * U;
      const Dmax = bars.y - A.y, y3 = bars.y + bars.h + 10 * U;
      r3 = { x: A.x, y: y3, w: A.w, h: A.y + A.h - (y3 - Dmax) };
      D = Dmax * k3;
    } else {
      r1 = { x: A.x, y: A.y + 7 * U, w: 0.3 * A.w, h: 0.24 * A.h };
      r2 = { x: A.x, y: r1.y + r1.h + gp + 7 * U, w: 0.4 * A.w, h: 0.24 * A.h };
      r3 = { x: A.x + 0.52 * A.w, y: A.y + 0.66 * A.h, w: 0.48 * A.w, h: 0.34 * A.h };
      bars = { x: A.x + 0.52 * A.w, y: A.y + 4 * U, w: 0.48 * A.w, h: (0.9 - 0.48 * k3) * A.h };
    }
    g.save();
    g.translate(0, -D);
    if (!P || T < 9.47) {
    tag(g, "01", r1.x, r1.y - 7 * U, 7.25);
    const f1 = word(g, "SEE", r1, { at: 7.25, speed: true });
    tag(g, "THE FLASH", f1.x + f1.w + 2 * U, f1.y + f1.h - 6.5 * U, 7.4);
    tag(g, "02", r2.x, r2.y - 7 * U, 7.75);
    const f2 = word(g, "COUNT", r2, { at: 7.75, style: "outline" });
    tag(g, "SECONDS", f2.x + f2.w + 2 * U, f2.y + f2.h - 6.5 * U, 7.9);
    }
    // the chart: solid yellow bars, one per count, rising hard
    const n = BARS.length, bw = bars.w / n;
    // the six empty slots, outlined, wait from the moment counting starts; each fills solid on its count
    if (T >= 7.75) {
      g.strokeStyle = PAL.ink;
      g.fillStyle = PAL.echo;
      g.lineWidth = 0.5 * U;
      for (let i = 0; i < n; i++) {
        const r = [bars.x + i * bw, bars.y + bars.h * (1 - (i + 1) / n), bw - 1.2 * U, bars.h * ((i + 1) / n)];
        g.fillRect(...r);
        g.strokeRect(...r);
      }
    }
    BARS.forEach((bt, i) => {
      const dt = T - bt;
      if (dt < 0) return;
      const h = bars.h * ((i + 1) / n) * B.ease.outExpo(B.clamp(dt / 0.08));
      g.fillStyle = PAL.ink;
      g.fillRect(bars.x + i * bw, bars.y + bars.h - h, bw - 1.2 * U, h);
      g.fillStyle = PAL.ground;
      g.font = B.font(bw * 0.38, MONO, 800);
      g.textAlign = "center";
      g.textBaseline = "top";
      const inside = h > bw * 0.5;
      g.fillStyle = inside ? PAL.ground : PAL.ink;
      g.fillText(String(i + 1), bars.x + i * bw + (bw - 1.2 * U) / 2, bars.y + bars.h - h + (inside ? bw * 0.08 : -bw * 0.48));
    });
    const t3 = tag(g, "03", r3.x, r3.y - 7 * U, 9.5);
    tag(g, "6 S ÷ 3 =", r3.x + t3.w + 1.5 * U, r3.y - 7 * U, 9.5);
    word(g, "2 KM", r3, { at: 9.5, speed: true });
    g.restore();
  }

  // ------------------------------------------------------------------ scene 4: the close
  function sceneClose(g) {
    const A = area(), P = F.portrait, gp = GAP();
    if (P) {
      const r1 = rowFit([{ str: "SEE", weight: 900 }, { str: "IT.", weight: 300 }], { x: A.x, y: A.y, w: A.w, h: 0.27 * A.h }, [0.3]);
      word(g, "SEE", r1[0], { at: 10.25, enter: "whipL" });
      word(g, "IT.", r1[1], { at: 10.37, weight: 300 });
      const y2 = r1[0].y + r1[0].h + gp;
      const r2 = rowFit([{ str: "COUNT", weight: 900 }, { str: "IT.", weight: 300 }], { x: A.x, y: y2, w: A.w, h: 0.27 * A.h }, [0.3]);
      word(g, "COUNT", r2[0], { at: 10.5, style: "outline", enter: "whipR" });
      word(g, "IT.", r2[1], { at: 10.62, weight: 300 });
      const y3 = r2[0].y + r2[0].h + gp;
      const f3 = word(g, "÷3", { x: A.x, y: y3, w: A.w, h: A.y + A.h - y3 - 9 * U }, { at: 10.75, style: "dots", stretch: true, develop: 0.6, seed: 3 });
      tag(g, "EVERY 3 S = 1 KM", A.x, f3.y + f3.h + 2.5 * U, 11.25);
    } else {
      const r1 = rowFit([{ str: "SEE", weight: 900 }, { str: "IT.", weight: 300 }, { str: "COUNT", weight: 900 }, { str: "IT.", weight: 300 }], { x: A.x, y: A.y, w: A.w, h: 0.45 * A.h }, [0.3, 0.55, 0.3]);
      word(g, "SEE", r1[0], { at: 10.25, enter: "whipL" });
      word(g, "IT.", r1[1], { at: 10.37, weight: 300 });
      word(g, "COUNT", r1[2], { at: 10.5, style: "outline", enter: "whipR" });
      word(g, "IT.", r1[3], { at: 10.62, weight: 300 });
      const y2 = r1[0].y + r1[0].h + gp;
      const f3 = word(g, "÷3", { x: A.x, y: y2, w: A.w * 0.62, h: A.y + A.h - y2 - 2 * U }, { at: 10.75, style: "dots", stretch: true, develop: 0.6, seed: 3 });
      tag(g, "EVERY 3 S = 1 KM", f3.x + f3.w + 3 * U, f3.y + f3.h * 0.4, 11.25);
    }
  }

  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneClose];

  // ------------------------------------------------------------------ frame: scenes, transitions, header, finish
  function renderScene(i, g, t) {
    const keep = T;
    T = t;
    g.fillStyle = PAL.ground;
    g.fillRect(0, 0, F.W, F.H);
    SCENES[i](g);
    T = keep;
  }
  function shakeAt(t) {
    // impact shake: a jolt in a random direction on every slam, settled within a tenth of a second
    let dx = 0, dy = 0;
    for (const s of SLAMS) {
      const d = t - s;
      if (d < 0 || d >= 0.1) continue;
      const a = B.hash01("shk", s) * B.TAU, amp = (KEY.includes(s) ? 2.2 : 1.1) * U * (1 - d / 0.1);
      dx += Math.cos(a) * amp;
      dy += Math.sin(a) * amp;
    }
    return [dx, dy];
  }
  function invertFrame(ctx, W, H) {
    // single-frame inversion: ink and ground swap (two-colour image: p -> ink + ground - p)
    const img = ctx.getImageData(0, 0, W, H), d = img.data, a = B.rgb(PAL.ink), b = B.rgb(PAL.ground);
    const s = [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
    for (let i = 0; i < d.length; i += 4) {
      d[i] = s[0] - d[i];
      d[i + 1] = s[1] - d[i + 1];
      d[i + 2] = s[2] - d[i + 2];
    }
    ctx.putImageData(img, 0, 0);
  }

  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    T = t;
    // measure the full title stack (for the header) without drawing it
    MEASURE = true;
    STACK = titleStack(null, (r) => r, true);
    MEASURE = false;
    const si = SCENE_AT.reduce((a, s, i) => (t >= s ? i : a), 0);
    const tr = TRANS.find((x) => t >= x.at && t < x.at + TR_LEN);
    const [sx, sy] = shakeAt(t);
    ctx.fillStyle = PAL.ground;
    ctx.fillRect(0, 0, W, H);
    if (!tr) {
      const g = B.scratch("kt-scene", W, H);
      renderScene(si, g, t);
      ctx.drawImage(g.canvas, sx, sy);
    } else {
      const p = (t - tr.at) / TR_LEN;
      const out = B.scratch("kt-out", W, H), inn = B.scratch("kt-in", W, H);
      renderScene(si - 1, out, tr.at - 0.001);
      renderScene(si, inn, t);
      if (tr.kind === "tear") {
        // slice-glitch tear: the old frame splits into bands flying off alternately left and right
        ctx.drawImage(inn.canvas, sx, sy);
        const r = B.rng(Math.round(tr.at * 10));
        let y = 0, k = 0;
        while (y < H) {
          const bh = Math.min(H - y, H * r.range(0.04, 0.13)), dir = k % 2 ? 1 : -1;
          const off = dir * Math.pow(p, 1.6) * W * r.range(1.0, 1.5);
          ctx.drawImage(out.canvas, 0, y, W, bh, off + sx, y, W, bh);
          if (p > 0.05 && p < 0.8) {
            ctx.fillStyle = PAL.ink;
            ctx.fillRect(off + (dir > 0 ? -0.6 * U : W), y, 0.6 * U, bh);
          }
          y += bh;
          k++;
        }
      } else {
        // whip-pan: the old scene smears off one side with echo copies, the new one arrives from the other
        const e = B.ease.inOutQuad(p), d = tr.dir;
        ctx.save();
        for (let k = 3; k >= 0; k--) {
          ctx.globalAlpha = k ? 0.22 : 1;
          ctx.drawImage(out.canvas, -d * (e * W * 1.1 - k * 0.05 * W * Math.sin(Math.PI * p)), 0);
          ctx.drawImage(inn.canvas, d * ((1 - e) * W * 1.1 + k * 0.05 * W * Math.sin(Math.PI * p)), 0);
        }
        ctx.restore();
      }
    }
    // the corner header: the opening stack, shrunk, staying for the rest of the piece
    if (t >= HDR_AT + HDR_IN) {
      const hg = B.scratch("kt-hdr", W, H);
      titleStack(hg, headerMap(1), true);
      ctx.drawImage(hg.canvas, 0, 0);
    }
    B.grain(ctx, W, H, { amount: 0.04, t, fps: 24, mode: "overlay" });
    // two frames at 24 fps: one frame is too brief to catch in live playback at a lower frame rate
    if (KEY.some((k) => t >= k && t < k + 2 / 24)) invertFrame(ctx, W, H);
  }

  // ------------------------------------------------------------------ sound: a pulse on the grid, kick + snap slams, stabs, tears, whooshes, blips, plucks
  SOUND.define("kinetic-kick", (v) => {
    v.tone({ f: 150, f2: 48, glide: 0.09, a: 0.001, len: 0.22, peak: 0.85 });
    v.noise({ filter: "highpass", f: 2800, a: 0.0005, len: 0.06, peak: 0.42 }); // the bright snap
    v.noise({ filter: "bandpass", f: 1300, q: 1.2, a: 0.0005, len: 0.03, peak: 0.25 });
  }, { verb: 0.08 });
  SOUND.define("kinetic-stab", (v) => {
    // detuned synth stab for the key hits
    [0, 7, 12].forEach((st, i) => {
      const f = v.hz("A3") * Math.pow(2, st / 12);
      v.tone({ type: "sawtooth", f, detune: -9, a: 0.004, hold: 0.06, len: 0.28, peak: 0.07 });
      v.tone({ type: "sawtooth", f, detune: 11, a: 0.004, hold: 0.06, len: 0.28, peak: 0.07 });
    });
  }, { verb: 0.3 });
  SOUND.define("kinetic-pulse", (v) => {
    v.tone({ type: "square", f: v.hz("A1"), a: 0.004, len: 0.16, peak: 0.08 });
    v.tone({ f: v.hz("A1"), a: 0.004, len: 0.22, peak: 0.18 });
  }, { verb: 0.05 });
  SOUND.define("kinetic-tear", (v) => {
    // crunchy digital tear: bit-crushed noise chopped into rapid slices
    for (let i = 0; i < 9; i++) {
      v.noise({ at: i * 0.022, filter: "bandpass", f: 600 + v.rng() * 4000, q: 3, a: 0.0005, len: 0.016, peak: 0.35 });
      v.tone({ at: i * 0.022, type: "square", f: 80 + v.rng() * 900, a: 0.0005, len: 0.014, peak: 0.05 });
    }
  }, { verb: 0.06 });
  SOUND.define("kinetic-blip", (v, o) => v.tone({ type: "square", f: v.hz(o.note ?? "E6"), a: 0.001, hold: 0.025, len: 0.02, peak: 0.07, shape: "lin" }), { verb: 0.04 });

  function score(k) {
    // the pulse on every beat, falling silent at each hard cut
    for (let b = 0; b < DUR * BPS; b++) {
      const t = b / BPS;
      if (TRANS.some((x) => Math.abs(x.at - t) < 0.01)) continue;
      k.at(t, "kinetic-pulse", { gain: 0.9 });
    }
    SLAMS.forEach((s) => k.at(s, "kinetic-kick", { gain: KEY.includes(s) ? 1 : 0.8, pitch: (s * 3) % 3 - 1 }));
    KEY.forEach((s) => k.at(s, "kinetic-stab", { gain: 1 }));
    TAGS.forEach((s) => k.at(s, "snap", { gain: 0.45 }));
    TRANS.forEach((x) => (x.kind === "tear" ? k.at(x.at, "kinetic-tear") : k.at(x.at, "whoosh", { dur: 0.25, gain: 0.8 })));
    k.at(6.0, "swish", { gain: 0.5 }).at(10.25, "swish", { gain: 0.4 }).at(10.5, "swish", { gain: 0.4, pitch: 3 });
    // counter ticks and the dot screen developing
    [5.25, 5.5].forEach((s) => k.at(s + 0.05, "kinetic-blip", { note: "E6" }));
    k.repeat(1.3, 0.05, 12, "kinetic-blip", { note: "A6", gain: 0.25, vary: 3 });
    k.repeat(10.8, 0.05, 10, "kinetic-blip", { note: "A6", gain: 0.2, vary: 3 });
    // chart bars: rising pitched plucks
    BARS.forEach((s, i) => k.at(s, "pluck", { note: ["A4", "C5", "D5", "E5", "G5", "A5"][i], gain: 0.55 }));
  }

  Player.register({
    id: "kinetic-type",
    name: "Kinetic Type",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@300;900&family=JetBrains+Mono:wght@800&display=swap",
      faces: ['900 100px "Big Shoulders Display"', '300 100px "Big Shoulders Display"', '800 20px "JetBrains Mono"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Flash and boom", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [2.05, 4.9, 6.9, 9.29, 9.95, 11.8],
    draw,
    score,
  });
})();
