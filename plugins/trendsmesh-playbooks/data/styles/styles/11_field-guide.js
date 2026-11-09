/* 11 Field Guide Plate. Topic (replace it): the monarch butterfly - its parts, its 3,000-mile flight, four stages.
 * Rendering (keep it): natural-history plates; engraved specimens (hatching that follows the form, cross-hatch, stipple,
 * outlines heavier away from the light) over a watercolour wash; italic labels on leader lines, engraved arrows.
 */
(function () {
  "use strict"; const B = window.Brush;

  const PAL = { paper: "#efe4cc", ink: "#2a2119", aged: "#b08a55", leaf: "#8fa66b", sky: "#8eaab8", ochre: "#d2a85a", rose: "#c98276", red: "#b33b2e" };
  const WING = B.mix(PAL.ochre, "#e2742a", 0.6); // monarch orange
  const FELL = "IM Fell English", GARA = "EB Garamond", DUR = 12, BEATS = [0, 2.2, 4.4, 6.6, 8.6, 10.4];
  const PLATES = [0, 4.4, 6.6, 10.4], PRESS = 0.75;

  // ---- geometry
  function pip(poly, x, y) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  const smoothClosed = (pts, n = 6) => {
    const out = [], L = pts.length;
    for (let i = 0; i < L; i++) {
      const [p0, p1, p2, p3] = [-1, 0, 1, 2].map((d) => pts[(i + d + L) % L]);
      for (let k = 0; k < n; k++) {
        const t = k / n, t2 = t * t, t3 = t2 * t;
        out.push([0, 1].map((c) => 0.5 * (2 * p1[c] + (p2[c] - p0[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 + (3 * p1[c] - p0[c] - 3 * p2[c] + p3[c]) * t3)));
      }
    }
    return out;
  };
  const bbox = (pts) => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
  };
  const mirror = (pts) => pts.map(([x, y]) => [-x, y]).reverse();
  const area = (pts) => pts.reduce((a, p, i) => a + p[0] * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * p[1], 0) / 2;
  function ribbon(path, pts, ws) {
    if (pts.length < 2) return; const L = [], R = [];
    pts.forEach((p, i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], l = (Math.hypot(b[0] - a[0], b[1] - a[1]) || 1) * 2;
      const nx = (-(b[1] - a[1]) / l) * ws[i], ny = ((b[0] - a[0]) / l) * ws[i];
      L.push([p[0] + nx, p[1] + ny]); R.unshift([p[0] - nx, p[1] - ny]);
    });
    B.poly(path, L.concat(R), true);
  }
  /** A hatch stroke tapering to a hair over te points at each end. */
  function stroke(pts, ws, te) {
    const n = pts.length, p = new Path2D();
    ribbon(p, pts, ws.map((w, i) => Math.max(0.1, w * Math.min(1, (i + 0.5) / te, (n - i - 0.5) / te))));
    return p;
  }
  /** An engraved line: swells, thins to a hair at the ends. */
  function engraved(path, pts, w, o = {}) {
    const n = pts.length, hair = o.hair ?? 0.12;
    const ws = pts.map((_, i) => {
      const k = n > 1 ? i / (n - 1) : 0.5;
      return Math.max(hair, w * Math.min(1, k / (o.tin ?? 0.3), (1 - k) / (o.tout ?? 0.3)));
    });
    ribbon(path, pts, ws);
  }

  // ---- the engraving engine (reuse it)
  /** Engraver's hatching: bowed strokes, width by tone(x, y), broken where light, crossed in the dark. */
  function hatch(poly, o) {
    const out = [], b = bbox(poly), R = Math.hypot(b.w, b.h) / 2 + 2, cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    for (const [ang, thr, gap] of [[o.angle, o.thr ?? 0.2, o.gap]].concat(o.cross ? [[o.cross.angle, o.cross.thr, o.gap * 1.1]] : [])) {
      const ca = Math.cos(B.deg(ang)), sa = Math.sin(B.deg(ang));
      for (let d = -R; d <= R; d += gap) {
        let run = [], ws = [];
        for (let s = -R; s <= R + 0.7; s += 0.7) {
          const e = d + (o.bow || 0) * (1 - (s / R) ** 2) * R * 0.1, x = cx + s * ca - e * sa, y = cy + s * sa + e * ca;
          const tone = s <= R && pip(poly, x, y) && !(o.skip && o.skip(x, y)) ? o.tone(x, y) : -1;
          if (tone > thr) {
            run.push([x, y]);
            ws.push((o.w ?? 0.8) * (0.18 + 0.82 * Math.pow(B.clamp((tone - thr) / (1 - thr)), 0.8)));
          } else {
            if (run.length > 2) out.push(stroke(run, ws, Math.min(4, run.length / 2)));
            run = []; ws = [];
          }
        }
      }
    }
    return out;
  }
  /** Outline heavier on the side away from the light (upper left). */
  function outline(poly, w) {
    const pts = poly.concat([poly[0]]), sg = area(poly) > 0 ? 0.63 : -0.63, n = pts.length;
    const ws = pts.map((_, i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)], l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      return w * (0.3 + 1.1 * B.clamp(((b[1] - a[1] - b[0] + a[0]) / l) * sg + 0.35));
    });
    return { pts, ws };
  }
  /** Stipple: dots whose density follows the tone. */
  function stipple(poly, tone, n, r, seed) {
    const p = new Path2D(), rr = B.rng(seed), b = bbox(poly);
    for (let i = 0; i < n; i++) {
      const x = b.x + rr() * b.w, y = b.y + rr() * b.h; if (!pip(poly, x, y) || rr() > tone(x, y)) continue;
      const rad = r * rr.range(0.6, 1.2); p.moveTo(x + rad, y); p.arc(x, y, rad, 0, B.TAU);
    }
    return p;
  }
  /** Light from the upper left: 0 lit, 1 in shade. */
  const lightTone = (cx, cy, R, base = 0.25, k = 0.75) => (x, y) => B.clamp(base + k * (((x - cx) / R) * 0.55 + ((y - cy) / R) * 0.75) * 0.5 + k * 0.25);

  // ---- specimens (the setting: replace these)
  // a figure { parts: [{ ol, hatch, stip, wash, col }], lines, r }
  const FIG = {}, fig = (name, build) => FIG[name] || (FIG[name] = build());
  /** The adult monarch, wings open. */
  function butterfly() {
    return fig("butterfly", () => {
      const fw = smoothClosed([[3, -6], [18, -30], [44, -52], [74, -64], [93, -63], [99, -55], [95, -40], [86, -22], [76, -9], [58, 0], [32, 4], [10, 3]], 5);
      const hw = smoothClosed([[4, 4], [30, 6], [56, 11], [76, 22], [84, 37], [80, 52], [66, 63], [46, 67], [28, 61], [14, 46], [6, 26]], 5);
      const parts = [], sr = B.rng(17), rings = new Path2D();
      // a wing: hatched by the light; a black border cross-hatched solid, white spots left bare
      const wing = (poly, ang, base, bandW, sg) => {
        const om = poly.filter(([x]) => x > 30), own = [], p2 = sg > 0 ? poly : mirror(poly), light = lightTone(sg * 50, 0, 70, base, 0.7);
        om.forEach(([a, b], i) => i % 3 || own.push([a * 0.93 * sg, b * 0.93 + (b > 0 ? -1 : 1), sr.range(1.0, 1.7)]));
        const tone = (x, y) => (Math.min(...om.map(([a, b]) => Math.hypot(a - x * sg, b - y))) < bandW ? 0.96 : light(x, y));
        const skip = (x, y) => own.some(([sx, sy, r]) => Math.hypot(x - sx, y - sy) < r + 0.5);
        parts.push({ ol: outline(p2, 1.1), hatch: hatch(p2, { angle: ang * sg, gap: 1.55, bow: 0.6, tone, w: 0.95, thr: 0.42, cross: { angle: (ang + 28) * sg, thr: 0.72 }, skip }), wash: p2, col: WING });
        own.forEach(([x, y, r]) => engraved(rings, B.arcPts(x, y, r + 0.3, 0, B.TAU, 16), 0.22, { tin: 0.01, tout: 0.01, hair: 0.22 }));
      };
      for (const sg of [1, -1]) {
        wing(fw, -32, 0.05, 6.5, sg); wing(hw, 28, 0.12, 6, sg);
      }
      const veins = new Path2D();
      const vf = [[93, -60], [97, -50], [92, -36], [84, -22], [72, -8], [52, 1]], vh = [[80, 46], [74, 58], [60, 64], [40, 63], [24, 54], [12, 40], [70, 24]];
      for (const s of [1, -1]) {
        vf.forEach(([x, y], i) => engraved(veins, B.quad(4 * s, -4, (x * 0.45 + 10) * s, y * 0.5 - 8, x * 0.94 * s, y * 0.94, 14), 2.3 - i * 0.1, { tin: 0.05, tout: 0.5 }));
        vh.forEach(([x, y]) => engraved(veins, B.quad(4 * s, 4, x * 0.4 * s, y * 0.4 + 6, x * 0.94 * s, y * 0.94, 14), 2.1, { tin: 0.05, tout: 0.5 }));
        engraved(veins, smoothClosed([[10 * s, -4], [30 * s, -18], [52 * s, -28], [46 * s, -14], [28 * s, -4]], 4).concat([[10 * s, -4]]), 0.8, { tin: 0.1, tout: 0.1 });
      }
      // the body ring-hatched dark, the head stippled
      const body = (q, angle, gap, bow, w) => ((q = smoothClosed(q, 4)), { ol: outline(q, 0.8), hatch: hatch(q, { angle, gap, bow, tone: () => 0.8, w, thr: 0.2 }) });
      const head = smoothClosed([[0, -20], [4, -17], [4, -13], [0, -11], [-4, -13], [-4, -17]], 4);
      parts.push(body([[0, 3], [3.6, 10], [3.4, 26], [2, 38], [0, 42], [-2, 38], [-3.4, 26], [-3.6, 10]], 90, 0.9, 2.2, 0.75), body([[0, -14], [5, -9], [5.5, 0], [3, 5], [-3, 5], [-5.5, 0], [-5, -9]], 80, 0.8, 1.5, 0.7));
      parts.push({ ol: outline(head, 0.6), stip: stipple(head, () => 0.9, 260, 0.45, 5) });
      const ant = new Path2D();
      for (const s of [1, -1]) {
        engraved(ant, B.quad(1.5 * s, -19, 10 * s, -42, 22 * s, -60, 16), 0.65, { tin: 0.1, tout: 0.05 });
        ant.moveTo(22 * s + 1.8, -61); ant.ellipse(22 * s, -61, 1.6, 2.6, 0.5 * s, 0, B.TAU);
      }
      return { parts, lines: [veins, ant, rings], r: 100 };
    });
  }
  /** Milkweed leaf with a single ribbed egg on it. */
  function leafEgg() {
    return fig("leafEgg", () => {
      const leaf = smoothClosed([[-62, 0], [-48, -18], [-15, -27], [25, -24], [55, -12], [70, 0], [55, 10], [22, 22], [-15, 25], [-48, 16]], 5);
      const veins = new Path2D();
      engraved(veins, B.quad(-64, 0, 0, -3, 69, 0, 30), 1.0, { tin: 0.05, tout: 0.6 });
      for (let i = 0; i < 12; i++) {
        const x = -45 + (i >> 1) * 18, g = i & 1 ? 1 : -1, e = 1.5 * Math.abs((i >> 1) - 2.5);
        engraved(veins, B.quad(x, g - 0.5, x + 9, g * 11 - 1, x + 18, g * (17 - e) - 1, 10), 0.52, { tin: 0.1 });
      }
      const egg = smoothClosed([[8, -21], [12, -18], [13, -11], [11, -6], [5, -6], [3, -11], [4, -18]], 4);
      const ribs = new Path2D();
      for (let i = 0; i < 6; i++) {
        const x = 4.5 + i * 1.5;
        engraved(ribs, B.quad(x, -7, x - 0.6 + (i - 2.5) * 0.3, -14, 8 + (i - 2.5) * 0.6, -20.5, 8), 0.28, { tin: 0.2 });
      }
      const parts = [
        { ol: outline(leaf, 1.0), hatch: hatch(leaf, { angle: 35, gap: 1.6, bow: 0.3, tone: lightTone(5, 0, 60, 0.0, 0.85), w: 0.8, thr: 0.45, cross: { angle: 62, thr: 0.8 }, skip: (x, y) => pip(egg, x, y + 1.5) }), wash: leaf, col: PAL.leaf },
        { ol: outline(egg, 0.45), stip: stipple(egg, lightTone(8, -13, 8, 0.0, 0.9), 220, 0.3, 9), wash: egg, col: B.mix(PAL.ochre, PAL.paper, 0.45) },
      ];
      return { parts, lines: [veins, ribs], r: 70, egg: [8, -14] };
    });
  }
  /** The caterpillar: a banded cylinder with filaments. */
  function caterpillar() {
    return fig("caterpillar", () => {
      // an arched cylinder: edge(s, v) is a point across it (v -1..1)
      const A = (s) => [B.lerp(-75, 75, s), -7 * Math.sin(Math.PI * s)], rad = (s) => 11.5 * Math.pow(Math.min(1, s / 0.07, (1 - s) / 0.05), 0.55);
      const tan = (s) => {
        const a = A(s - 0.01), b = A(s + 0.01), l = Math.hypot(b[0] - a[0], b[1] - a[1]);
        return [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
      };
      const edge = (s, v) => {
        const p = A(s), t = tan(s); return [p[0] - t[1] * rad(s) * v, p[1] + t[0] * rad(s) * v];
      };
      const body = [], SEG = 11, rings = [];
      for (let i = 0; i <= 160; i++) body.push(i <= 80 ? edge(i / 80, -1) : edge((160 - i) / 80, 1));
      // ring hatching: bands 0 black (dense), 1 yellow, 2 white; the lower side darker
      const band = (s) => {
        const f = B.fract(s * SEG); return f < 0.28 ? 0 : f < 0.4 || f >= 0.82 ? 2 : 1;
      };
      for (let j = 3; j < 235; j++) {
        const s = j * 0.0042, b = band(s), pts = [], ws = []; if (j % [1, 3, 5][b]) continue;
        for (let v = -1; v <= 1.0001; v += 0.08) {
          const tone = B.clamp([0.85, 0.2, 0.05][b] + 0.65 * Math.max(0, v) * (b ? 1 : 0.3)), t = tan(s), e = edge(s, v * 0.97), c = 1.6 * (1 - v * v);
          if (tone < 0.3 && b) continue; pts.push([e[0] + t[0] * c, e[1] + t[1] * c]);
          ws.push(0.15 + 0.7 * tone);
        }
        if (pts.length > 2) rings.push(stroke(pts, ws, Math.min(3, pts.length / 2)));
      }
      const fil = new Path2D();
      for (const [s, len, dir] of [[0.9, 22, 1], [0.94, 20, 1], [0.12, 14, -1], [0.16, 13, -1]]) {
        const [x, y] = edge(s, -1);
        engraved(fil, B.quad(x, y, x + dir * len * 0.2, y - len * 0.8, x + dir * len * 0.75, y - len, 14), 0.7, { tin: 0.05, tout: 0.6 });
      }
      const head = smoothClosed([[0.985, -0.9], [1, 0], [0.985, 0.9], [0.94, 0.8], [0.94, -0.8]].map(([a, v]) => [edge(a, v)[0] + 2, edge(a, v)[1]]), 3);
      const washes = [], I = [0, 1, 2, 3, 4, 5, 6]; // a wash per yellow band
      for (let k = 0; k < SEG - 1; k++) washes.push(I.map((i) => edge((k + 0.4 + 0.07 * i) / SEG, -1)).concat(I.map((i) => edge((k + 0.82 - 0.07 * i) / SEG, 1))));
      const parts = [
        { ol: outline(body, 1.0), hatch: rings, washList: washes, col: B.mix(PAL.ochre, "#e7c45a", 0.4) },
        { ol: outline(head, 0.6), stip: stipple(head, () => 0.95, 160, 0.42, 4) },
      ];
      return { parts, lines: [fil], r: 80 };
    });
  }
  /** The chrysalis: a jade pod, a black band dotted with gold. */
  function chrysalis() {
    return fig("chrysalis", () => {
      const prof = (s) => 24 * Math.pow(Math.sin(Math.PI * B.clamp(s * 0.94 + 0.03)), 0.62) * (1 - 0.22 * s), Y = (s) => B.lerp(-40, 44, s);
      const pod = [], rings = [], tone = (x, y) => B.clamp(0.1 + (x / 24) * 0.55 + ((y + 40) / 84) * 0.25);
      for (let i = 0; i <= 81; i++) pod.push(i <= 40 ? [prof(i / 40) + 0.8, Y(i / 40)] : [0.8 - prof((81 - i) / 40), Y((81 - i) / 40)]);
      for (let s = 0.04; s < 0.97; s += 0.025) {
        const pts = [], ws = [], r = prof(s);
        for (let v = -1; v <= 1.0001; v += 0.07) {
          const x = v * r + 0.8, y = Y(s) + Math.sqrt(1 - v * v) * r * 0.16, tn = tone(x, y);
          if (tn < 0.35) continue; pts.push([x, y]); ws.push(0.12 + 0.75 * tn);
        }
        if (pts.length > 2) rings.push(stroke(pts, ws, Math.min(3, pts.length / 2)));
      }
      const longi = hatch(pod, { angle: 90, gap: 1.8, bow: -0.8, tone: (x, y) => tone(x, y) * 1.1, w: 0.6, thr: 0.62 });
      const by = Y(0.27), pr = prof(0.27), band = new Path2D(), gold = new Path2D(), twig = new Path2D(), gr = B.rng(31);
      engraved(band, B.quad(-pr + 1.5, by, 0.8, by + 3.5, pr - 0.2, by, 16), 1.6, { tin: 0.15, tout: 0.15 });
      const spots = [[-9, 26], [-4, 32], [3, 34], [9, 28], [-12, 12], [12, 12]];
      const dot = (x, y, r) => {
        gold.moveTo(x + r, y); gold.arc(x, y, r, 0, B.TAU);
      };
      for (let i = 0; i < 7; i++) dot(B.lerp(-pr + 4, pr - 3, i / 6), by - 2.2 + Math.abs(i - 3) * 0.3, 0.9);
      for (const [x, y] of spots) dot(x, y, gr.range(0.7, 1.1));
      engraved(twig, [[-34, -52], [-10, -50.5], [12, -51], [36, -53]], 3.2, { tin: 0.05, tout: 0.15 });
      engraved(twig, [[0.8, -49], [0.6, -44], [0.8, -40]], 1.4, { tin: 0.2 });
      const goldDots = spots.map(([x, y]) => smoothClosed([[x, y - 1.6], [x + 1.6, y], [x, y + 1.6], [x - 1.6, y]], 3));
      return { parts: [{ ol: outline(pod, 1.0), hatch: rings.concat(longi), wash: pod, col: B.mix(PAL.leaf, PAL.sky, 0.35), gold: goldDots }], lines: [band, twig, gold], r: 55 };
    });
  }

  // ---- drawing a figure (ink and wash layers)
  let INK = null, WASH = null, U = 1, F = null, T = 0, TXT = 4;
  /** Italic Garamond, never under TXT (the smallest readable size). */
  const ital = (txt, x, y, o = {}) => B.text(INK, txt, x, y, { size: TXT, minSize: TXT, family: GARA, style: "italic", weight: 400, color: PAL.ink, ...o });
  /** A figure: outline engraves, hatching follows, the wash spreads. */
  function drawFig(f, x, y, s, at, o = {}) {
    const lt = T - at; if (lt <= 0) return;
    const pOl = B.clamp(lt / (o.olDur ?? 0.7)), pH = B.clamp((lt - 0.35) / (o.hDur ?? 1.0)), pW = B.clamp((lt - (o.washAt ?? 0.9)) / 0.9);
    for (const g of [INK, WASH]) {
      g.save(); g.translate(x, y); g.rotate(o.sway ? Math.sin(T * 1.3 + at) * o.sway : 0);
      g.scale(s, s);
    }
    // the wash: a little off the lines, a ragged wet edge, a dried rim
    if (pW > 0) {
      const rr = f.r * 1.35 * B.ease.outCubic(pW), edge = [];
      for (let i = 0; i <= 48; i++) {
        const a = (i / 48) * B.TAU, k = rr * (1 + 0.16 * B.noise1(i * 0.45 + at * 10, 3) + 0.06 * B.noise1(i * 1.7, 4));
        edge.push([Math.cos(a) * k, Math.sin(a) * k * 0.9]);
      }
      B.clip(WASH, () => B.poly(WASH, edge, true), () => {
        WASH.translate(0.9, 0.7); WASH.lineWidth = 0.9;
        for (const part of f.parts.filter((q) => q.col)) {
          for (const poly of part.washList || [part.wash]) {
            WASH.beginPath();
            B.poly(WASH, B.wobble(poly.concat([poly[0]]), { amp: 0.9, freq: 6, seed: 3 }), true);
            WASH.fillStyle = B.rgba(part.col, 0.78); WASH.fill();
            WASH.strokeStyle = B.rgba(B.shade(part.col, -0.25), 0.4); WASH.stroke();
          }
          WASH.fillStyle = B.rgba(PAL.ochre, 0.9);
          for (const poly of part.gold || []) {
            WASH.beginPath(); B.poly(WASH, poly, true); WASH.fill();
          }
        }
      });
    }
    INK.fillStyle = PAL.ink;
    for (const part of f.parts) {
      const k = Math.max(2, Math.floor(part.ol.pts.length * pOl)), h = part.hatch || [];
      if (pOl > 0) {
        const p = new Path2D(); ribbon(p, part.ol.pts.slice(0, k), part.ol.ws.slice(0, k));
        INK.fill(p);
      }
      if (pH > 0) {
        h.slice(0, Math.floor(h.length * pH)).forEach((q) => INK.fill(q));
        INK.globalAlpha = pH; if (part.stip) INK.fill(part.stip); INK.globalAlpha = 1;
      }
    }
    INK.globalAlpha = B.clamp((pOl - 0.5) * 2); for (const l of f.lines) INK.fill(l);
    INK.globalAlpha = 1; for (const g of [INK, WASH]) g.restore();
  }

  // ---- explaining
  /** Italic label on a fine leader line ending in a dot. */
  function label(text, tx, ty, ax, ay, at, o = {}) {
    const lt = T - at; if (lt <= 0) return;
    const p = B.clamp(lt / 0.5), size = TXT, al = o.align || (tx < ax ? "right" : "left");
    const d = al === "right" ? 1 : al === "left" ? -1 : 0, ly = d ? ty : ty + (ay > ty ? 0.6 : -0.6) * size, lx = tx + d * size * 0.35, pr = new Path2D();
    // o.arrow: an engraved arrow to the part; else a leader ending in a dot
    if (o.arrow) engravedArrow(B.quad(lx, ly, ax, ly, ax, ay, 24), at, 0.5, 0.6);
    else engraved(pr, B.trim(B.densify([[lx, ly], [ax, ay]], U), 0, p), 0.28 * U, { tin: 0.02, tout: 0.05, hair: 0.1 * U });
    if (p >= 1 && !o.arrow) {
      pr.moveTo(ax + 0.55 * U, ay); pr.arc(ax, ay, 0.55 * U, 0, B.TAU);
    }
    INK.fillStyle = PAL.ink; INK.fill(pr);
    ital(text, tx - d * size * 0.1, ty, { size, align: al, alpha: B.clamp((lt - 0.2) / 0.4) });
  }
  /** Engraved arrow: tapering shaft, barbed head, feathered tail. */
  function engravedArrow(path, at, dur = 0.7, w = 0.75) {
    const p = B.clamp((T - at) / dur), pts = B.trim(B.densify(path, U), 0, p), pr = new Path2D();
    if (p <= 0 || pts.length < 2) return;
    engraved(pr, pts, w * U, { tin: 0.08, tout: 0.6, hair: 0.15 * U });
    const ta = B.pointAt(path, 0)[2];
    for (let i = 0; i < 6; i++) {
      // feathered tail
      const q = B.pointAt(path, 0.015 + (i >> 1) * 0.03), a = ta + Math.PI + (i & 1 ? 0.6 : -0.6), l = 2.2 * U;
      engraved(pr, [[q[0], q[1]], [q[0] + Math.cos(a) * l, q[1] + Math.sin(a) * l]], 0.32 * U, { tin: 0.05, tout: 0.8 });
    }
    if (p >= 1) {
      const [hx, hy, a] = B.pointAt(path, 1), l = 3.4 * U;
      for (const sg of [-1, 1]) {
        const b = a + Math.PI + sg * 0.32, c = Math.cos(b) * l, d = Math.sin(b) * l;
        engraved(pr, [[hx, hy], [hx + c, hy + d], [hx + c * 0.82 + Math.cos(a) * l * 0.12, hy + d * 0.82 + Math.sin(a) * l * 0.12]], 0.55 * U, { tin: 0.02, tout: 0.3 });
      }
    }
    INK.fillStyle = PAL.ink; INK.fill(pr);
  }
  /** A number in an engraved cartouche; digits roll over. */
  function cartouche(cx, cy, rx, ry, value, unit, at) {
    const lt = T - at; if (lt <= 0) return;
    const p = B.clamp(lt / 0.8), pr = new Path2D(), E = (pts, w, o) => engraved(pr, pts, w * U, o);
    const ring = (k) => B.arcPts(0, 0, 1, -Math.PI / 2, -Math.PI / 2 + B.TAU * p, 90).map(([x, y]) => [cx + x * rx * k, cy + y * ry * k]);
    E(ring(1), 1.0, { tin: 0.02, tout: 0.02 });
    E(ring(0.9), 0.35, { tin: 0.02, tout: 0.02 });
    for (let i = 0; i < Math.floor(70 * p); i++) {
      const a = -Math.PI / 2 + (i / 70) * B.TAU, c = Math.cos(a), s = Math.sin(a);
      E([[cx + c * rx * 0.915, cy + s * ry * 0.915], [cx + c * rx * 0.985, cy + s * ry * 0.985]], 0.22, { tin: 0.3 }); // the ruled edge
    }
    if (p >= 1)
      for (const g of [-1, 1]) E(B.arcPts(cx + g * (rx + 3 * U), cy, 3 * U, g * 2, g * 2 + B.TAU * 0.85, 30), 0.7, { tin: 0.05, tout: 0.6 }); // scroll ends
    INK.fillStyle = PAL.ink; INK.fill(pr); if (p < 0.6) return;

    const v = value * B.ease.outCubic(B.clamp((lt - 0.5) / 1.1)), digits = String(value).length, size = ry * 0.82;
    INK.save(); INK.beginPath(); INK.ellipse(cx, cy, rx * 0.86, ry * 0.86, 0, 0, B.TAU);
    INK.clip();
    Object.assign(INK, { font: B.font(size, FELL, 400), textAlign: "center", textBaseline: "middle" });
    const dw = INK.measureText("0").width * 1.02, comma = INK.measureText(",").width, ny = cy - ry * 0.12;
    let x = cx - (digits * dw + comma) / 2;
    for (let i = 0; i < digits; i++) {
      const pl = digits - 1 - i, dv = v / 10 ** pl, d0 = Math.floor(dv) % 10, fr = pl && B.fract(dv) > 0.85 ? (B.fract(dv) - 0.85) / 0.15 : 0;
      INK.fillText(String(d0), x + dw / 2, ny - fr * size * 1.1);
      if (fr > 0) INK.fillText(String((d0 + 1) % 10), x + dw / 2, ny + (1 - fr) * size * 1.1);
      x += dw;
      if (pl === 3) {
        INK.fillText(",", x + comma / 2, ny); x += comma;
      }
    }
    INK.restore(); ital(unit, cx, cy + ry * 0.52);
  }
  /** The colourist's emphasis: a loose watercolour ring. */
  function washRing(cx, cy, rx, ry, at, color = PAL.red) {
    const p = B.clamp((T - at) / 0.7); if (p <= 0) return; const pts = [];
    for (let i = 0; i <= 80; i++) {
      const a = -2.3 + (i / 80) * B.TAU * 1.06, k = 1 + 0.04 * B.noise1(i * 0.3, 7);
      pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    const part = B.trim(pts, 0, p);
    [[0, 2.2, 0.55, 0, 4], [0.5, 0.8, 0.35, -0.25, 5]].forEach(([o, w, a, sh, seed]) => B.taperStroke(WASH, part.map(([x, y]) => [x + o * U, y + o * 0.6 * U]), { width: w * U, color: B.rgba(B.shade(color, sh), a), taperIn: 0.08, taperOut: 0.25, rough: 0.5, roughScale: 3, seed }));
  }

  // ---- the plate (page furniture)
  const ROMAN = ["XI", "XII", "XIII", "XIV"];
  function frameBox() {
    const W = F.W, H = F.H;
    return F.portrait ? { x: W * 0.05, y: H * 0.06, w: W * 0.9, h: H * 0.78 } : { x: W * 0.045, y: H * 0.085, w: W * 0.91, h: H * 0.815 };
  }
  /** Running heads, the double ruled frame, the caption. */
  function furniture(plate, caption, at) {
    const fb = frameBox(), pr = new Path2D();
    const rect = (d, lw) => {
      const q = B.rectPts(fb.x + d, fb.y + d, fb.w - 2 * d, fb.h - 2 * d);
      for (let i = 0; i < 4; i++) engraved(pr, B.densify([q[i], q[i + 1]], 4 * U), lw, { tin: 0.01, tout: 0.01, hair: lw * 0.8 });
    };
    rect(0, 0.42 * U); rect(U, 0.18 * U); INK.fillStyle = PAL.ink; INK.fill(pr);
    // tiny running heads: texture, not read
    const head = (txt, x, al) => B.text(INK, txt, x, fb.y + 3.6 * U, { size: 2.5 * U, family: FELL, weight: 400, color: PAL.ink, align: al, letterSpacing: 0.22 });
    B.texture(INK, () => {
      head("VOL. III", fb.x + 3 * U, "left");
      head(`PLATE ${ROMAN[plate]}.`, fb.x + fb.w - 3 * U, "right");
    });
    if (caption) ital(caption, fb.x + fb.w / 2, fb.y + fb.h - (F.portrait ? 12 : 4.6) * U, { maxW: fb.w * 0.88, maxLines: 2, lineH: 1.2, alpha: B.clamp((T - at) / 0.6) });
    return fb;
  }
  /** Heading: spaced roman capitals, then an italic line. */
  function heading(cx, y, caps, sub, at, size) {
    const a = B.clamp((T - at) / 0.6); if (a <= 0) return;
    B.text(INK, caps, cx + size * 0.09, y, { size, family: FELL, weight: 400, color: PAL.ink, letterSpacing: 0.18, alpha: a });
    INK.globalAlpha = B.clamp((T - at - 0.3) / 0.6);
    ital(sub, cx, y + size * 1.25); INK.globalAlpha = 1;
  }
  const figNo = (n, x, y, at) => ital(`Fig. ${n}.`, x, y, { alpha: B.clamp((T - at) / 0.5) });

  // ---- the plates
  function plateParts() {
    const fb = frameBox();
    return { fb, P: F.portrait, X: (f) => fb.x + f * fb.w, Y: (f) => fb.y + f * fb.h, hs: (F.portrait ? 5.6 : 5.2) * U, hy: fb.y + fb.h * (F.portrait ? 0.135 : 0.11) };
  }
  /** Plate XI: the adult, its parts named (closing: XIV). */
  function plateAdult(closing) {
    const { fb, P, X, Y, hs, hy } = plateParts(), t0 = closing ? PLATES[3] : 0;
    furniture(closing ? 3 : 0, closing ? "Egg, caterpillar, chrysalis, butterfly." : "The Monarch, Danaus plexippus, wings spread.", t0 + (closing ? 1.0 : 0.9));
    heading(X(0.5), hy, closing ? "EGG TO WING" : "THE MONARCH", closing ? "four stages in about a month" : "its life, from egg to wing", t0 + 0.15, hs);
    const bx = X(0.5), by = Y(P ? 0.5 : 0.55), s = (P ? 0.0041 * F.W : 0.0046 * fb.h) * (closing ? 0.85 : 1);
    drawFig(butterfly(), bx, by, s, t0 + 0.4, closing ? { sway: 0.01, hDur: 0.8, washAt: 0.55 } : { sway: 0.01, hDur: 1.3 });
    figNo(1, bx + (P ? -84 : 100) * s, by + (P ? 74 : 64) * s, t0 + 1.6);
    if (closing) return washRing(bx, by - 2 * s, 108 * s, 80 * s, t0 + 0.75);
    // [text, label x, y, part x, y, align]
    const parts = P ? [["Antenna", -40, -76, -22, -60, "right"], ["Fore-wing", 80, -80, 66, -50, "center"], ["Hind-wing", 72, 82, 58, 46, "center"], ["Abdomen", 6, 84, 1, 34, "center"]]
      : [["Antenna", -64, -74, -22, -60, "right"], ["Fore-wing", 126, 4, 86, -40, "left"], ["Hind-wing", -108, 52, -74, 44, "right"], ["Abdomen", 0, 70, 0, 42, "center"]];
    parts.forEach(([txt, tx, ty, lx, ly, al], i) => label(txt, bx + tx * s, by + ty * s, bx + lx * s, by + ly * s, 2.4 + i * 0.2, { align: al, arrow: i === 1 }));
  }
  /** Plate XII: the flight, the key number in a cartouche. */
  function plateFlight() {
    const { fb, P, X, Y, hs, hy } = plateParts(), t0 = PLATES[1];
    furniture(1, "Fig. 2. Some fly 3,000 miles, Canada to Mexico.", t0 + 0.8);
    heading(X(0.5), hy, "THE AUTUMN FLIGHT", "south for the winter", t0 + 0.15, hs);
    // the route, small butterflies along it
    const path = P ? B.cubic(X(0.14), Y(0.25), X(1.08), Y(0.25), X(1.02), Y(0.8), X(0.3), Y(0.84), 60) : B.cubic(X(0.1), Y(0.32), X(0.22), Y(1.0), X(0.78), Y(1.0), X(0.93), Y(0.32), 60);
    engravedArrow(path, t0 + 0.5, 0.8, 0.6);
    [0.32, 0.55, 0.8].forEach((k, i) => {
      const q = B.pointAt(path, k), s = (P ? 0.0011 : 0.0008) * F.W * (1 - i * 0.15);
      drawFig(butterfly(), q[0], q[1] - 26 * s, s, t0 + 0.6 + i * 0.2, { olDur: 0.4, hDur: 0.5, washAt: 0.5, sway: 0.03 });
    });
    const q0 = path[0], q1 = path[path.length - 1];
    label("from Canada", q0[0] + (P ? 6 * U : 0), q0[1] - 5 * U, q0[0], q0[1] - 0.8 * U, t0 + 0.9, { align: "center" });
    label("to Mexico", q1[0] - (P ? 4 * U : 0), q1[1] - 5 * U, q1[0], q1[1] - 0.8 * U, t0 + 1.2, { align: P ? "right" : "center" });
    cartouche(X(P ? 0.42 : 0.5), Y(P ? 0.52 : 0.44), (P ? 0.27 : 0.19) * fb.w, (P ? 0.11 : 0.2) * fb.h, 3000, "miles, flown south", t0 + 0.4);
  }
  /** Plate XIII: four stages round a circle, engraved arrows between. */
  function plateCycle() {
    const { fb, P, X, Y, hs, hy } = plateParts(), t0 = PLATES[2];
    furniture(2, null, 0);
    heading(X(0.5), hy, "THE LIFE CYCLE", "metamorphosis, stage by stage", t0 + 0.15, hs);
    const cx = X(0.5), cy = Y(P ? 0.56 : 0.6), rx = fb.w * (P ? 0.31 : 0.33), ry = fb.h * 0.25, sc = F.W * (P ? 0.0028 : 0.00165);
    const pos = [0, 1, 2, 3].map((i) => [cx + Math.cos((i - 1) * Math.PI / 2) * rx, cy + Math.sin((i - 1) * Math.PI / 2) * ry]);
    const times = [t0 + 0.3, t0 + 1.0, BEATS[4] + 0.1, BEATS[4] + 0.85], o = { olDur: 0.5, hDur: 0.8, washAt: 0.7 };
    const bs = sc * (P ? 0.5 : 0.55), cpx = pos[1][0] - (P ? 22 * sc : 0), egg = leafEgg().egg;
    drawFig(leafEgg(), pos[0][0], pos[0][1], sc, times[0], o);
    drawFig(caterpillar(), cpx, pos[1][1], sc * (P ? 0.8 : 0.95), times[1], { ...o, sway: 0.01 });
    drawFig(chrysalis(), pos[2][0], pos[2][1] - (P ? 6 : 10) * sc, sc * (P ? 1.0 : 0.72), times[2], { ...o, sway: 0.012 });
    drawFig(butterfly(), pos[3][0], pos[3][1], bs, times[3], { olDur: 0.45, hDur: 0.7, washAt: 0.55, sway: 0.01 });
    label("I. Egg, 4 days", pos[0][0] + 74 * sc, pos[0][1] - (P ? 14 : 10) * sc, pos[0][0] + egg[0] * sc, pos[0][1] + egg[1] * sc, times[0] + 0.55, { align: "left" });
    const cap = (txt, x, y, a, align = "center") => ital(txt, x, y, { align, alpha: B.clamp((T - a) / 0.5) });
    cap("II. Caterpillar, 2 weeks", cpx, pos[1][1] + (P ? 24 : 26) * sc, times[1] + 0.6);
    if (P) cap("III. Chrysalis, 10 days", pos[2][0], pos[2][1] + 52 * sc, times[2] + 0.55);
    else cap("III. Chrysalis, 10 days", pos[2][0] + 24 * sc, pos[2][1] + 4 * sc, times[2] + 0.55, "left");
    cap("IV. Butterfly", pos[3][0], pos[3][1] + 90 * bs, times[3] + 0.5);
    // engraved arrows round the circle, clockwise
    const arc = (a0, a1) => B.arcPts(0, 0, 1, a0, a1, 30).map(([x, y]) => [cx + x * rx * 0.92, cy + y * ry * 0.92]), g = P ? 0.55 : 0.6, Q = Math.PI / 2;
    // the last arrow (butterfly to egg) closes the cycle within the beat
    [times[0] + 0.7, times[2] - 0.15, times[3] - 0.15, times[3] + 0.3].forEach((a, i) => engravedArrow(arc((i - 1) * Q + g * (i > 2 ? 0.8 : 1), i * Q - g * (i > 2 ? 0.75 : 1)), a, 0.5));
  }
  const PLATE_FN = [() => plateAdult(false), plateFlight, plateCycle, () => plateAdult(true)];

  // ---- finishing
  function foxing(W, H) {
    // rust-brown spots, gathered near the margins
    return B.layer("fg-foxing", W, H, (g, w, h) => {
      const r = B.rng(23), u = Math.min(w, h) / 100;
      for (let i = 0; i < 70; i++) {
        const e = r.int(0, 3), d = Math.pow(r(), 2.2) * 0.16, rad = r.range(0.33, 2) * u;
        const x = e === 0 ? d * w : e === 1 ? w - d * w : r() * w, y = e === 2 ? d * h : e === 3 ? h - d * h : r() * h;
        g.fillStyle = B.radial(g, x, y, 0, rad, [[0, B.rgba("#9a5a2a", r.range(0.25, 0.5))], [0.45, B.rgba("#a8703a", 0.18)], [1, B.rgba("#a8703a", 0)]]);
        g.fillRect(x - rad, y - rad, 2 * rad, 2 * rad);
      }
    });
  }
  /** Granulation: clustered noise that makes each wash uneven. */
  function granTile() {
    return B.layer("fg-gran", 256, 256, (g, w, h) => {
      const img = g.createImageData(w, h);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const n = B.noise2(x / 6, y / 6, 11) * 0.5 + B.noise2(x / 2, y / 2, 12) * 0.5;
          img.data[(y * w + x) * 4 + 3] = Math.round(B.clamp(n * 0.6 + 0.25) * 150);
        }
      g.putImageData(img, 0, 0);
    });
  }
  /** One plate: paper, pressed rectangle, wash under the ink. */
  function renderPlate(ctx, i) {
    const W = F.W, H = F.H, fb = frameBox(), m = 2.6 * U, set = (o) => Object.assign(ctx, o);
    INK = B.scratch("fg-ink-" + (i % 2), W, H); WASH = B.scratch("fg-wash-" + (i % 2), W, H);
    PLATE_FN[i]();
    Object.assign(WASH, { globalCompositeOperation: "destination-out", fillStyle: WASH.createPattern(granTile(), "repeat") });
    WASH.fillRect(0, 0, W, H); WASH.globalCompositeOperation = "source-over";
    B.paper(ctx, W, H, { color: PAL.paper, seed: 12, mottle: 0.12, fibers: 0.2, specks: 0.25, tooth: 0.06 });
    // the pressed rectangle, debossed
    ctx.save();
    set({ globalCompositeOperation: "multiply", fillStyle: "rgba(214,196,160,0.35)" });
    ctx.fillRect(fb.x - m, fb.y - m, fb.w + 2 * m, fb.h + 2 * m);
    set({ globalCompositeOperation: "source-over", lineWidth: 0.22 * U, strokeStyle: "rgba(110,84,50,0.45)" });
    ctx.strokeRect(fb.x - m, fb.y - m, fb.w + 2 * m, fb.h + 2 * m);
    set({ strokeStyle: "rgba(255,250,236,0.75)" }).strokeRect(fb.x - m - 0.35 * U, fb.y - m - 0.35 * U, fb.w + 2 * m + 0.7 * U, fb.h + 2 * m + 0.7 * U);
    // the tint off register and softened; the ink with a faint halo
    set({ globalCompositeOperation: "multiply", filter: `blur(${(0.18 * U).toFixed(2)}px)` });
    ctx.drawImage(WASH.canvas, 0.25 * U, 0.2 * U);
    set({ globalCompositeOperation: "source-over", globalAlpha: 0.22, filter: `blur(${(0.35 * U).toFixed(2)}px)` });
    ctx.drawImage(INK.canvas, 0, 0); ctx.restore(); ctx.drawImage(INK.canvas, 0, 0);
    B.vignette(ctx, W, H, { color: PAL.aged, amount: 0.55, inner: 0.5, mode: "multiply" });
    ctx.drawImage(foxing(W, H), 0, 0);
  }

  // ---- frame
  function draw(ctx, W, H, t) {
    F = B.frame(W, H); U = F.u; T = t; TXT = (F.portrait ? 4.1 : 4.0) * U;
    let i = 0; while (i < 3 && t >= PLATES[i + 1]) i++; const pp = i > 0 ? B.clamp((t - PLATES[i]) / PRESS) : 1;
    if (pp < 1) {
      // a fresh plate comes off the press behind a soft shadow band
      T = PLATES[i] - 0.001; renderPlate(ctx, i - 1); T = t;
      const bx = B.lerp(-0.12, 1.12, B.ease.inOutSine(pp)) * W, bw = 0.09 * W;
      B.clip(ctx, () => ctx.rect(0, 0, bx, H), () => renderPlate(ctx, i));
      ctx.save(); ctx.globalCompositeOperation = "multiply";
      ctx.fillStyle = B.linear(ctx, bx - bw, 0, bx + bw * 0.5, 0, [[0, "rgba(90,70,45,0)"], [0.75, "rgba(90,70,45,0.38)"], [1, "rgba(90,70,45,0)"]]);
      ctx.fillRect(bx - bw, 0, bw * 1.5, H); ctx.restore();
    } else renderPlate(ctx, i);
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 6, mode: "multiply", seed: 9 });
  }

  // ---- sound: a scratching tool, the press, a wet brush, ticks

  function score(k) {
    const burin = (a, dur, gain = 1) => k.at(a, "pencil", { dur, gain: gain * 0.8 }), brush = (a, dur, gain = 0.8) => k.at(a, "breath", { dur, gain: gain * 0.5 });
    k.bed("pad", 0, DUR, { gain: 0.38, notes: ["D3", "A3", "D4", "F#4"], bright: 520 });
    burin(0.2, 0.5, 0.6); burin(0.45, 1.6); brush(1.35, 0.8);
    for (let a = 2.4; a < 3.1; a += 0.2) burin(a, 0.35, 0.55);
    PLATES.slice(1).forEach((a) => k.at(a - 0.05, "thud", { gain: 0.5, pitch: -8 }).at(a + 0.4, "paper", { dur: 0.5, gain: 0.6 }));
    burin(PLATES[1] + 0.6, 1.1); brush(PLATES[1] + 1.2, 0.6, 0.6);
    k.repeat(PLATES[1] + 0.95, 0.07, 14, "tick", { gain: 0.45, vary: 1 }).at(PLATES[1] + 2.0, "ding", { note: "A5", gain: 0.2 });
    [PLATES[2] + 0.3, PLATES[2] + 1.0, BEATS[4] + 0.1, BEATS[4] + 0.85].forEach((a) => (burin(a, 0.8), brush(a + 0.7, 0.5, 0.7)));
    brush(BEATS[5] - 0.4, 0.7); burin(PLATES[3] + 0.45, 1.0, 0.6); brush(PLATES[3] + 0.75, 0.7);
    k.at(PLATES[3] + 1.3, "chime", { note: "D6", gain: 0.12 });
  }

  Player.register({
    id: "field-guide", name: "Field Guide Plate", duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&family=EB+Garamond:ital,wght@0,400;1,400&display=swap",
      faces: ['400 20px "IM Fell English"', 'italic 400 20px "EB Garamond"', '400 20px "EB Garamond"'],
    },
    beats: BEATS, beatNames: ["Title", "Diagram", "Key number", "Stages I-II", "Stages III-IV", "Close"],
    stills: [2.0, 4.2, 6.4, 8.5, 10.3, 11.8],
    draw, score,
  });
})();
