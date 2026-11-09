/* 33 Low Poly - reference animation.
 * Topic (setting, replace it): "How do migrating birds find their way?" - the Arctic tern's long trip south.
 * Rendering (keep it): a real 3D height field seen through a simple perspective camera, cut into irregular flat
 * triangles: each facet is one colour from one low sun (facing it: warm and light; away: cool and dark), rock on the
 * heights, a triangulated lake that mirrors the sky in lighter flat tones, then depth fog that melts each facet into
 * the haze, layer after layer of far ridges. Trees are stacked pyramids, gems are few-sided crystals, pillars are
 * faceted prisms; the sky is the only smooth thing. Labels are cut-corner tags on thin straight stems, arrows are
 * two-tone ribbons in straight segments along the ground, the number sits on a floating panel with a triangle shadow.
 * Motion: facets flip up in a wave from near to far, trees and objects pop up after the ground, the camera glides
 * forward with parallax, things leave by folding down facet by facet. No grain, no outlines.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { skyTop: "#5b5fb0", peach: "#ffc29b", haze: "#e9d5e6", light: "#79c3a0", shade: "#2f7a78", rock: "#7d6f93", warm: "#ffe08a", accent: "#ff6f61" };
  const TXT = "#2c2a52"; // tag text: the sky's indigo, deepened
  const HEAD = "Space Grotesk", LAB = "Exo 2";
  const DUR = 12.5;
  const BEATS = [0, 2.2, 4.4, 6.5, 9.0, 10.8];
  const C = Object.fromEntries(Object.entries(PAL).map(([k, v]) => [k, B.rgb(v)]));
  const SUN = (() => { const v = [0.78, 0.3, 0.55], l = Math.hypot(...v); return v.map((a) => a / l); })(); // toward the low sun, right of centre
  const LAKE = [-1.8, 14, 3.0, 2.4], PLAT = [4.2, 20, 2.8, 1.8]; // lake: x, z, rx, rz; plateau: x, z, r, height
  const ROUTE = [[0.2, 11.5], [2.4, 21], [2.8, 33], [6, 46]]; // straight legs from the lake toward the far hills
  const STEPS = [[-2.4, 14.5, 6.8, 1.6], [-1.5, 20, 7.4, 3.2], [-10.5, 36, 8.0, 0]]; // beacons left of the route: x, z, when, float height (each clears the tag below it)

  // ------------------------------------------------------------------ the land (built once, world units)
  const mixc = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  const css = (c) => `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
  function height(x, z) {
    let h = (1.0 + 1.5 * B.fbm(x * 0.1, z * 0.1, 3, 5)) * (0.75 + z * 0.035);
    h -= 1.1 * Math.exp(-Math.pow((x - B.lerp(-0.5, 1, B.clamp((z - 15) / 35))) / 4, 2)) * B.smooth(14, 22, z); // the valley the route follows
    h += 9 * B.smooth(40, 64, z) * (0.55 + 0.45 * B.noise2(x * 0.07, 3.3, 7));
    const pl = Math.hypot(x - PLAT[0], z - PLAT[1]) / PLAT[2];
    h = B.lerp(PLAT[3], h, B.smooth(1.0, 1.7, pl));
    const lk = Math.hypot((x - LAKE[0]) / LAKE[2], (z - LAKE[1]) / LAKE[3]);
    h = B.lerp(0.02, h, B.smooth(0.8, 1.5, lk));
    return Math.max(0.05, h);
  }
  const isLake = (x, z) => Math.hypot((x - LAKE[0]) / LAKE[2], (z - LAKE[1]) / LAKE[3]) < 1;
  /** Flat facet colour from the light: cool shade -> light -> warm, rock on the heights. */
  function facetColour(n, y, water, seed) {
    if (water) return mixc(C.haze, C.skyTop, 0.12 + 0.22 * seed); // the lake mirrors the sky in lighter flat tones
    // relative to flat ground (mid tone): turned to the sun -> light and warm, turned away -> cool and dark
    const k = B.clamp(0.5 + 2.4 * (n[0] * SUN[0] + n[1] * SUN[1] + n[2] * SUN[2] - SUN[1]));
    let c = mixc(C.shade, C.light, B.smooth(0.05, 0.95, k));
    if (y > 3.5) c = mixc(c, mixc(C.rock, C.haze, k * 0.5), B.smooth(3.5, 6.5, y));
    if (k > 0.7) c = mixc(c, C.warm, (k - 0.7) * 1.5);
    return mixc(c, C.light, (seed - 0.5) * 0.08);
  }
  let WORLD = null;
  function build() {
    const V = [], T = [], NR = 40, NC = 36, rows = [];
    for (let r = 0; r < NR; r++) {
      const z0 = 2.5 * Math.pow(1.088, r), row = [];
      for (let c = 0; c < NC; c++) {
        const hs = 0.8 * z0 + 4, dx = (2 * hs) / (NC - 1);
        let x = -hs + c * dx + (B.hash01(r, c, 1) - 0.5) * dx * 0.55, z = z0 * (1 + (B.hash01(r, c, 2) - 0.5) * 0.06);
        const water = isLake(x, z);
        row.push(V.length);
        V.push([x, water ? 0 : height(x, z), z, water]);
      }
      rows.push(row);
    }
    const tri = (a, b, c, far) => {
      const A = V[a], Bv = V[b], Cv = V[c];
      const u = [Bv[0] - A[0], Bv[1] - A[1], Bv[2] - A[2]], w = [Cv[0] - A[0], Cv[1] - A[1], Cv[2] - A[2]];
      let n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
      const l = Math.hypot(...n) || 1;
      n = n.map((q) => q / l);
      if (n[1] < 0) n = n.map((q) => -q);
      const water = A[3] && Bv[3] && Cv[3], cz = (A[2] + Bv[2] + Cv[2]) / 3, cy = (A[1] + Bv[1] + Cv[1]) / 3;
      T.push({ v: [a, b, c], col: facetColour(n, cy, water, B.hash01(a, b, c)), z: cz, far });
    };
    for (let r = 0; r < NR - 1; r++)
      for (let c = 0; c < NC - 1; c++) {
        const a = rows[r][c], b = rows[r][c + 1], d = rows[r + 1][c], e = rows[r + 1][c + 1];
        if (B.hash01(r, c, 9) < 0.5) {
          tri(a, b, e);
          tri(a, e, d);
        } else {
          tri(a, b, d);
          tri(b, e, d);
        }
      }
    // far ridges: three faceted strips, each sloping toward us, lost further in the haze
    [[95, 17, 11], [135, 25, 23], [190, 34, 37]].forEach(([zr, hm, seed]) => {
      const top = [], mid = [], base = [];
      for (let i = 0; i <= 30; i++) {
        const x = -150 + i * 10 + (B.hash01(i, seed) - 0.5) * 6, hp = hm * (0.45 + 0.55 * Math.abs(B.noise1(i * 0.37, seed)));
        top.push(V.length);
        V.push([x, hp, zr, false]);
        mid.push(V.length);
        V.push([x + 4, hp * (0.35 + 0.3 * B.hash01(i, seed, 3)), zr - 6, false]);
        base.push(V.length);
        V.push([x, 0, zr - 12, false]);
      }
      for (let i = 0; i < 30; i++) {
        tri(top[i], top[i + 1], mid[i], true);
        tri(top[i + 1], mid[i + 1], mid[i], true);
        tri(mid[i], mid[i + 1], base[i], true);
        tri(mid[i + 1], base[i + 1], base[i], true);
      }
    });
    const trees = [], tr = B.rng(33);
    for (let i = 0; i < 120 && trees.length < 30; i++) {
      const x = tr.range(-12, 12), z = tr.range(5, 34);
      if (Math.hypot((x - LAKE[0]) / (LAKE[2] + 1), (z - LAKE[1]) / (LAKE[3] + 1)) < 1.1 || Math.hypot(x - PLAT[0], z - PLAT[1]) < PLAT[2] + 1 || (z < PLAT[1] && Math.abs(x - PLAT[0]) < 4.5) || Math.abs(x - B.lerp(-0.5, 1, B.clamp((z - 15) / 35))) < 1.6 || STEPS.some((q) => Math.hypot(x - q[0], z - q[1]) < 2)) continue;
      trees.push([x, z, tr.range(0.8, 1.35)]);
    }
    WORLD = { V, T, trees };
  }

  // ------------------------------------------------------------------ camera and projection
  let CAM = null, Fr = null, FOC = 1, HY = 0;
  function camAt(t) {
    // glide forward; for the chart, slide over to face the plateau (closer in 9:16); at the close, rise to look out
    const chart = B.span(t, 8.8, 9.8, "inOutSine"), close = B.span(t, 10.8, 12.5, "inOutSine"), P = Fr && Fr.portrait;
    return { x: 0.6 * Math.sin(t * 0.22) + (P ? 3.8 : 3.4) * chart, y: (P ? 7.4 : 4.2) + 0.15 * Math.sin(t * 0.5) + (P ? 0.6 : 1.2) * chart + 2.2 * close, z: 0.62 * t + (P ? 5.4 : 1.0) * chart };
  }
  /** World -> [screen x, screen y, depth]; null behind the near plane. */
  function proj(x, y, z) {
    const zp = z - CAM.z;
    if (zp < 0.9) return null;
    return [Fr.W / 2 + (FOC * (x - CAM.x)) / zp, HY - (FOC * (y - CAM.y)) / zp, zp];
  }
  const hazeAt = (zp) => 1 - Math.exp(-zp / 58); // depth fog
  function fogged(col, zp, extra = 0) {
    const f = B.clamp(hazeAt(zp) + extra);
    return mixc(col, mixc(C.haze, C.peach, 0.3 + 0.45 * f), f * 0.9);
  }

  // ------------------------------------------------------------------ low-poly helpers (reuse these)
  /** One flat facet, its own colour as a hairline stroke so neighbours meet without seams (never an outline). */
  function facet(g, pts, col) {
    const s = typeof col === "string" ? col : css(col);
    g.beginPath();
    B.poly(g, pts, true);
    g.fillStyle = s;
    g.strokeStyle = s;
    g.lineWidth = 1;
    g.fill();
    g.stroke();
  }
  /** Shade a world-space facet by the light (n = outward normal) and the fog. */
  const lit = (base, n, zp, lift = 0) => fogged(mixc(mixc(B.rgb(base), C.shade, 0.35).map((q) => q * 0.7), mixc(B.rgb(base), C.warm, 0.35), B.smooth(-0.35, 0.75, n[0] * SUN[0] + n[1] * SUN[1] + n[2] * SUN[2] + lift)), zp);
  /** Faceted prism (pillar, tree tier) standing on the ground: n sides, visible side faces back to front, then the top. */
  function prism(g, x, y0, z, r, h, n, base, o = {}) {
    if (h <= 0.01) return;
    const ring = (yy, rr) => Array.from({ length: n }, (_, i) => {
      const a = (i / n) * B.TAU + (o.rot ?? 0.3);
      return [x + Math.cos(a) * rr, yy, z + Math.sin(a) * rr];
    });
    const lo = ring(y0, r), hi = ring(y0 + h, r * (o.taper ?? 1)), faces = [];
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n, a = ((i + 0.5) / n) * B.TAU + (o.rot ?? 0.3), nx = Math.cos(a), nz = Math.sin(a);
      const fx = x + nx * r, fz = z + nz * r;
      if (nx * (CAM.x - fx) + nz * (CAM.z - fz) <= 0) continue; // faces turned away
      const P = [lo[i], lo[j], hi[j], hi[i]].map((q) => proj(...q));
      if (P.some((q) => !q)) continue;
      faces.push([fz, P, lit(base, [nx, 0.25, nz], P[0][2], o.lift ?? 0)]);
    }
    faces.sort((a, b) => b[0] - a[0]).forEach((f) => facet(g, f[1], f[2]));
    if ((o.taper ?? 1) > 0.05) {
      const top = hi.map((q) => proj(...q));
      if (top.every(Boolean)) {
        facet(g, top, o.topCol || lit(base, [0, 1, 0], top[0][2], 0.3));
      }
    }
  }
  /** Stacked-pyramid tree. s = pop scale. */
  function tree(g, x, z, s) {
    if (s <= 0.01) return;
    const y = height(x, z);
    prism(g, x, y, z, 0.12 * s, 0.5 * s, 4, "#8a6f5a");
    prism(g, x, y + 0.4 * s, z, 0.85 * s, 1.5 * s, 5, PAL.light, { taper: 0 });
    prism(g, x, y + 1.25 * s, z, 0.6 * s, 1.2 * s, 5, B.mix(PAL.light, PAL.shade, 0.15), { taper: 0, rot: 0.9 });
  }
  /** Floating crystal (emphasis): an eight-faced gem that turns slowly, with a faint shaft of light under it. */
  function crystal(g, x, y, z, r, t, col = PAL.accent) {
    const c = proj(x, y, z);
    if (!c) return;
    const s = (FOC * r) / c[2], a = t * 1.2;
    g.save();
    g.globalAlpha = 0.18;
    facet(g, [[c[0] - s * 0.25, c[1]], [c[0] + s * 0.25, c[1]], [c[0], c[1] + s * 6]], PAL.warm);
    g.restore();
    const pts = [0, 1, 2, 3].map((i) => [c[0] + Math.cos(a + i * 1.571) * s, c[1] + Math.sin(a + i * 1.571) * s * 0.28]);
    const topP = [c[0], c[1] - s * 1.5], botP = [c[0], c[1] + s * 1.1];
    const order = [0, 1, 2, 3].sort((i, j) => pts[i][1] + pts[(i + 1) % 4][1] - pts[j][1] - pts[(j + 1) % 4][1]);
    order.forEach((i) => {
      const j = (i + 1) % 4, side = Math.cos(a + i * 1.571 + 0.785);
      facet(g, [pts[i], pts[j], topP], B.mix(col, "#ffffff", 0.25 + 0.35 * side));
      facet(g, [pts[i], pts[j], botP], B.mix(col, "#3a2f6a", 0.2 - 0.15 * side));
    });
  }
  /** A low-poly bird seen from behind, flying away: an M of four wing facets and a small body; the wings beat. */
  function bird(g, x, y, z, t, ph, big = 1) {
    const c = proj(x, y, z);
    if (!c) return;
    const s = (FOC * 0.5 * big) / c[2], f = Math.sin(t * 7 + ph), [X, Y] = c, zf = c[2] * 0.5;
    const dark = css(fogged(mixc(C.skyTop, [40, 34, 80], 0.55), zf)), lite = css(fogged(mixc(C.skyTop, C.rock, 0.4), zf));
    const tipY = Y - s * (0.12 + 0.42 * f), elbY = Y - s * (0.06 + 0.2 * f);
    [-1, 1].forEach((d) => {
      facet(g, [[X, Y - s * 0.06], [X + d * s * 0.5, elbY], [X + d * s * 0.44, elbY + s * 0.17], [X + d * s * 0.08, Y + s * 0.1]], d < 0 ? dark : lite);
      facet(g, [[X + d * s * 0.5, elbY], [X + d * s * 1.05, tipY], [X + d * s * 0.44, elbY + s * 0.17]], d < 0 ? lite : dark);
    });
    facet(g, [[X, Y - s * 0.13], [X + s * 0.1, Y + s * 0.05], [X, Y + s * 0.34], [X - s * 0.1, Y + s * 0.05]], dark);
  }
  /** A V of n birds, the lead at (x, y, z) farthest away, the rest trailing nearer, sp apart (wider than a wingspan). */
  function flock(job, x, y, z, n, sp, t, big = 1) {
    for (let i = 0; i < n; i++) {
      const row = Math.ceil(i / 2), d = i % 2 ? 1 : -1, bx = x + d * row * sp, by = y - row * sp * 0.12, bz = z - row * sp * 0.7;
      job(bz, (g) => bird(g, bx, by, bz, t, i * 1.7, big));
    }
  }
  /** Cut-corner tag on a thin straight stem from an anchor (screen space). s = pop/fold 0..1. */
  function tag(g, anchor, text, s, o = {}) {
    if (!anchor || s <= 0.01) return;
    const u = Fr.u, S = Fr.safe, size = o.size ?? 4.7 * u, up = (o.up ?? 9) * u;
    g.save();
    g.font = B.font(size, LAB, 700);
    const ls = text.split("\n"), nw = o.num ? size * 1.5 : 0, w = Math.max(...ls.map((l) => g.measureText(l).width)) + size * 1.6 + nw, h = size * (0.8 + 1.2 * ls.length), ch = size * 0.64;
    const tx = B.clamp(anchor[0] + (o.side ?? 0) * (w / 2 + (o.gap ?? -3) * u), S.x + w / 2, S.r - w / 2), ty = B.clamp(anchor[1] - up - h / 2, S.y + h / 2, S.b - h / 2); // up: gap from anchor to the tag's foot
    g.strokeStyle = "rgba(255,255,255,0.9)";
    g.lineWidth = 0.25 * u;
    g.beginPath();
    g.moveTo(anchor[0], anchor[1]);
    g.lineTo(tx, ty + (h / 2) * s);
    g.stroke();
    g.translate(tx, ty + h / 2);
    g.scale(1, s); // folds down to its bottom edge
    g.translate(0, -h / 2);
    const shape = (x0, x1) => [[x0 + ch, -h / 2], [x1, -h / 2], [x1, h / 2 - ch], [x1 - ch, h / 2], [x0, h / 2], [x0, -h / 2 + ch]];
    facet(g, shape(-w / 2, w / 2), "#fbf6f2");
    facet(g, [[-w / 2, h * 0.18], [w / 2, h * 0.18], [w / 2, h / 2 - ch], [w / 2 - ch, h / 2], [-w / 2, h / 2]], "#efe3ea");
    if (o.num) {
      facet(g, [[-w / 2 + ch, -h / 2], [-w / 2 + nw + size * 0.3, -h / 2], [-w / 2 + nw, h / 2], [-w / 2, h / 2], [-w / 2, -h / 2 + ch]], PAL.accent);
      B.text(g, String(o.num), -w / 2 + nw * 0.55, 0, { size, family: HEAD, weight: 700, color: "#ffffff" });
    }
    B.text(g, text, nw / 2, size * 0.04, { size, minSize: size, family: LAB, weight: 700, color: TXT, lineH: 1.2 });
    g.restore();
  }
  /** Two-tone ribbon arrow along ground waypoints, in straight segments, swallowtail at the tail, point at the head. */
  function ribbon(g, pts, p, wide) {
    // each waypoint floats just above the highest ground on its two legs, so every leg is one straight 3D segment
    const top = (a, b) => Math.max(...Array.from({ length: 9 }, (_, k) => height(B.lerp(a[0], b[0], k / 8), B.lerp(a[1], b[1], k / 8))));
    const ys = pts.map((q, i) => 0.45 + Math.max(i ? top(pts[i - 1], q) : 0, i < pts.length - 1 ? top(q, pts[i + 1]) : 0));
    const sp = [];
    pts.forEach((q, i) => {
      if (i) for (let k = 1; k <= 8; k++) {
        const a = pts[i - 1], P = proj(B.lerp(a[0], q[0], k / 8), B.lerp(ys[i - 1], ys[i], k / 8), B.lerp(a[1], q[1], k / 8));
        if (P) sp.push(P);
      }
    });
    if (sp.length < 3 || p <= 0) return;
    const path = B.trim(sp, 0, p);
    if (path.length < 2) return;
    const wAt = (i) => (wide * FOC) / sp[Math.min(sp.length - 1, Math.round((i / (path.length - 1)) * (sp.length - 1) * p))][2];
    const L = [], R = [], M = [];
    path.forEach((q, i) => {
      const a = path[Math.max(0, i - 1)], b = path[Math.min(path.length - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const l = Math.hypot(nx, ny) || 1, w = wAt(i) / 2;
      nx /= l;
      ny /= l;
      L.push([q[0] + nx * w, q[1] + ny * w]);
      R.push([q[0] - nx * w, q[1] - ny * w]);
      M.push([q[0], q[1]]);
    });
    const n = path.length - 1, end = path[n], prev = path[Math.max(0, n - 2)], ang = Math.atan2(end[1] - prev[1], end[0] - prev[0]), hw = wAt(n) * 1.5;
    const tip = [end[0] + Math.cos(ang) * hw * 1.7, end[1] + Math.sin(ang) * hw * 1.7];
    const tail = [B.lerp(L[0][0], R[0][0], 0.5) + Math.cos(ang) * wAt(0) * 0.7, B.lerp(L[0][1], R[0][1], 0.5) + Math.sin(ang) * wAt(0) * 0.7];
    const hl = [end[0] - Math.sin(ang) * hw, end[1] + Math.cos(ang) * hw], hr = [end[0] + Math.sin(ang) * hw, end[1] - Math.cos(ang) * hw];
    facet(g, [tail].concat(L, [hl, tip], M.slice().reverse()), PAL.accent);
    facet(g, [tail].concat(M, [tip, hr], R.slice().reverse()), B.shade(PAL.accent, -0.28));
  }

  // ------------------------------------------------------------------ the frame
  function draw(ctx, W, H, t) {
    if (!WORLD) build();
    const F = (Fr = B.frame(W, H)), u = F.u, P = F.portrait;
    FOC = P ? 1.08 * W : 0.95 * W;
    HY = H * (P ? 0.3 : 0.43);
    CAM = camAt(t);
    // sky: the only smooth thing; a faint warm glow on the sun side of the horizon
    ctx.fillStyle = B.linear(ctx, 0, 0, 0, HY, [[0, PAL.skyTop], [0.55, B.mix(PAL.skyTop, PAL.haze, 0.6)], [0.85, PAL.haze], [1, PAL.peach]]);
    ctx.fillRect(0, 0, W, H);
    B.glow(ctx, W * 0.78, HY, Math.max(W, H) * 0.45, PAL.peach, 0.55);
    B.glow(ctx, W * 0.78, HY, Math.max(W, H) * 0.12, PAL.warm, 0.5);
    // project the land, then paint facets and objects back to front
    const PV = WORLD.V.map((v) => proj(v[0], v[1], v[2]));
    const jobs = [];
    const wave = (z, far) => (far ? B.prog(t, 1.3 + (z - 95) / 300, 0.4, "outBack") : B.prog(t, 0.1 + (z - 2.5) * 0.02, 0.38, "outBack"));
    WORLD.T.forEach((tr) => {
      const a = PV[tr.v[0]], b = PV[tr.v[1]], c = PV[tr.v[2]];
      if (!a || !b || !c) return;
      const p = wave(tr.z, tr.far);
      if (p <= 0.01) return;
      jobs.push([(a[2] + b[2] + c[2]) / 3, 0, tr, [a, b, c], p]);
    });
    const job = (zw, fn) => jobs.push([zw - CAM.z, 1, fn]);
    WORLD.trees.forEach(([x, z, s], i) => {
      const k = B.ease.outBack(B.prog(t, 0.9 + (z - 5) * 0.025 + (i % 4) * 0.03, 0.4), 2.5);
      job(z, (g) => tree(g, x, z, s * k));
    });
    // emphasis crystal over the lake, the steps' beacons, the chart's pillars, the flocks
    const cr = B.pop(t, 2.5, 0.5) * (1 - B.prog(t, 6.3, 0.3)), lakeY = 2.6 + B.bob(t, 0.15, 2);
    if (cr > 0) job(LAKE[1], (g) => crystal(g, LAKE[0], lakeY, LAKE[1], 0.45 * cr, t));
    const stepR = (z) => Math.pow(z / 14.5, 1.1); // far beacons drawn bigger so all three read
    const stepY = (x, z, lift) => height(x, z) + (lift || (P ? 5.6 : 4)) + B.bob(t, 0.12, 2, x); // 0: the far beacon, lower in 16:9 so its tag fits above
    STEPS.forEach(([x, z, at, lift]) => {
      const s = B.pop(t, at, 0.45) * (1 - B.prog(t, 9.0, 0.3));
      if (s > 0) job(z - 9, (g) => crystal(g, x, stepY(x, z, lift), z, 0.38 * s * stepR(z), t + z, PAL.warm));
    });
    const fold = (at) => 1 - B.prog(t, at, 0.5, "inCubic");
    const PH = [2.4, 4.2].map((h) => h * (P ? 1.5 : 1)); // pillar heights 40,000 : 70,000 (taller in 9:16)
    [[PLAT[0] + 1.6, PH[0], "#b6a9d8"], [PLAT[0] - 1.6, PH[1], "#ffc0a6"]].forEach(([x, h, base], i) => {
      const k = B.ease.outBack(B.prog(t, 9.2 + i * 0.35, 0.6), 1.4) * fold(11.0 + i * 0.1);
      const hh = k < 1 && t > 11 ? Math.floor(k * 6) / 6 : k; // folding down facet by facet
      if (hh > 0) job(PLAT[1], (g) => prism(g, x, PLAT[3], PLAT[1], 1.05, h * hh, 6, base, { topCol: i ? PAL.accent : null, lift: 0.25 }));
    });
    // the flock glides low in front of us at the title, then flies off ahead and on toward the far hills
    const fe = B.ease.inOutSine(B.prog(t, 1.9, 1.6)), ft = Math.max(0, t - 3.5);
    flock(job, B.lerp(0.4, -3.2, fe) + ft * 0.9, B.lerp(P ? 3.6 : 3.4, 6.8, fe) + ft * 0.25, Math.min(t, 3.5) * 0.62 + B.lerp(6.5, 22, fe) + ft * 3.2, 5, 1.15, t);
    // the close: a second flock overtakes us low in the frame and leads on
    const fc = B.ease.outCubic(B.prog(t, 10.8, 1.3));
    if (fc > 0) flock(job, CAM.x + 0.3, CAM.y - (P ? 4.2 : 1.2), CAM.z + B.lerp(1.6, 6.5, fc) + Math.max(0, t - 12.1) * 2, 5, 1.3, t, 1.2);
    const np = B.pop(t, 4.55, 0.5) * (1 - B.prog(t, 6.3, 0.35)); // the number panel
    jobs.sort((a, b) => b[0] - a[0]);
    jobs.forEach((j) => {
      if (j[1]) return j[2](ctx);
      const [zp, , tr, pts, p] = j;
      let q = pts;
      if (p < 1) {
        // flip into place about the facet's centre, with a bright flash as it lands
        const cx = (q[0][0] + q[1][0] + q[2][0]) / 3, cy = (q[0][1] + q[1][1] + q[2][1]) / 3;
        q = q.map((v) => [cx + (v[0] - cx) * Math.min(1, p * 1.2), cy + (v[1] - cy) * p]);
      }
      let col = fogged(tr.col, zp);
      if (p < 1) col = mixc(col, C.warm, (1 - p) * 0.6);
      facet(ctx, q, col);
    });
    // ribbon route (lies on the ground; drawn over it), with a slow sinking fold at the chart
    const rp = B.prog(t, 2.6, 1.0, "inOutSine") * (1 - B.prog(t, 9.0, 0.5));
    if (rp > 0) ribbon(ctx, ROUTE, rp, 0.8);
    // finishing: soft vignette toward the corners
    B.vignette(ctx, W, H, { amount: 0.22, inner: 0.55, color: "#2c2a52" });

    // ---------------- words (screen space)
    const S = F.safe, at = (x, y, z) => proj(x, y, z);
    const title = (str, sub, a0, a1) => {
      const a = B.prog(t, a0, 0.4) * (1 - B.prog(t, a1 - 0.3, 0.3));
      if (a <= 0) return;
      const y = P ? S.y + 5 * u : S.y + 7 * u, dy = (1 - B.ease.outCubic(B.prog(t, a0, 0.5))) * 3 * u;
      const r = B.text(ctx, str, W / 2, y + dy, { size: P ? 9 * u : 8 * u, family: HEAD, weight: 700, color: "#ffffff", maxW: S.w, maxLines: 2, lineH: 1.02, alpha: a, shadow: { x: 0, y: 0.5 * u, color: B.rgba(PAL.skyTop, 0.5) } });
      if (sub) B.text(ctx, sub, W / 2, r.bottom + 3.5 * u, { size: 4.8 * u, minSize: 4.6 * u, family: LAB, weight: 600, color: "#fff6ee", maxW: S.w, maxLines: 2, alpha: a, shadow: { x: 0, y: 0.2 * u, blur: 1.2 * u, color: B.rgba("#2c2a52", 0.85) } });
    };
    title("The long way south", "How migrating birds find their way", 0.6, BEATS[1]);
    const fade = (a, b) => B.pop(t, a, 0.4, 1.6) * (1 - B.prog(t, b - 0.3, 0.3));
    tag(ctx, at(LAKE[0], lakeY + 0.8, LAKE[1]), "Summer home:\nfar north", fade(2.45, BEATS[2]), { up: 3 });
    tag(ctx, at(ROUTE[3][0], height(ROUTE[3][0], ROUTE[3][1]) + 0.5, ROUTE[3][1]), "Heading south", fade(3.3, BEATS[2]), { up: 2.5 });
    if (np > 0) {
      // the key number on a floating cut-corner panel, counting up
      const cx = P ? W / 2 : W * 0.3, cy = (P ? 0.235 : 0.25) * H + B.bob(t, 0.8 * u, 2.4), pw = (P ? 86 : 80) * u, ph = 30 * u, cc = 4 * u;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(np, np);
      facet(ctx, [[-pw / 2 + cc, -ph / 2], [pw / 2, -ph / 2], [pw / 2, ph / 2 - cc], [pw / 2 - cc, ph / 2], [-pw / 2, ph / 2], [-pw / 2, -ph / 2 + cc]], "#fbf6f2");
      facet(ctx, [[-pw / 2, ph * 0.1], [pw / 2, ph * 0.1], [pw / 2, ph / 2 - cc], [pw / 2 - cc, ph / 2], [-pw / 2, ph / 2]], "#f1e6ee");
      const b = 2.6 * u; // an accent band down the left edge, its top cut parallel to the corner
      facet(ctx, [[-pw / 2, -ph / 2 + cc], [-pw / 2 + cc, -ph / 2], [-pw / 2 + cc + b, -ph / 2], [-pw / 2 + b, -ph / 2 + cc], [-pw / 2 + b, ph / 2], [-pw / 2, ph / 2]], PAL.accent);
      B.text(ctx, B.counter(B.prog(t, 4.7, 1.1), 70000, { suffix: " km" }), 0, -ph * 0.12, { size: (P ? 14 : 11) * u, family: HEAD, weight: 700, color: TXT, maxW: pw - 6 * u, maxLines: 1 });
      B.text(ctx, "flown by one Arctic tern a year", 0, ph * 0.3, { size: 4.7 * u, minSize: 4.5 * u, family: LAB, weight: 600, color: B.mix(TXT, "#ffffff", 0.2), maxW: pw - 6 * u, maxLines: 2, alpha: B.prog(t, 5.3, 0.3) });
      ctx.restore();
    }
    // each step's tag stands above its beacon, clear of the beacon and of the route
    const sl = ["Days get\nshorter", "Fuel up\non fat", "Steer by\nsun & stars"];
    STEPS.forEach(([x, z, a0, lift], i) => tag(ctx, at(x, stepY(x, z, lift) + 0.38 * 1.5 * stepR(z), z), sl[i], fade(a0 + 0.1, BEATS[4]), { num: i + 1, up: i === 2 && !P ? 6 : 3 }));
    tag(ctx, at(PLAT[0] + 1.6, PLAT[3] + PH[0] + 0.1, PLAT[1]), P ? "Once round Earth\n40,000 km" : "Once round Earth: 40,000 km", fade(9.6, BEATS[5] + 0.3), { up: 2.5 });
    tag(ctx, at(PLAT[0] - 1.6, PLAT[3] + PH[1] + 0.1, PLAT[1]), P ? "A tern's year\n70,000 km" : "A tern's year: 70,000 km", fade(9.95, BEATS[5] + 0.3), { up: 2.5 });
    title("See you in spring", "Twice a year, pole to pole", BEATS[5] + 0.4, DUR + 1);
  }

  // ------------------------------------------------------------------ sound: wind bed, glassy pings as facets settle, soft chimes for numbers
  SOUND.define("poly-ping", (v, o) => {
    // a glassy crystal ping: a pure high tone with a slightly inharmonic overtone, quick bright decay
    const f = v.hz(o.note ?? "E6");
    v.tone({ f, a: 0.002, len: 0.5, peak: 0.12 });
    v.tone({ f: f * 2.76, a: 0.001, len: 0.18, peak: 0.04 });
  }, { verb: 0.55 });

  function score(k) {
    k.bed("wind", 0, DUR, { gain: 0.7 });
    k.bed("pad", 0, DUR, { notes: ["D3", "A3", "E4", "F#4"], gain: 0.35, bright: 900 });
    const sc = SOUND.scale("D5", "lydian", 12);
    for (let i = 0; i < 16; i++) k.at(0.2 + i * 0.09 + k.rng() * 0.04, "poly-ping", { note: sc[(i * 3) % 12], gain: 0.5 - i * 0.015, pan: k.rng() * 1.6 - 0.8 });
    k.at(0.6, "breath", { dur: 1.2, gain: 0.5 });
    for (let i = 0; i < 6; i++) k.at(0.95 + i * 0.12, "pop", { gain: 0.25, pitch: i });
    k.at(2.45, "poly-ping", { note: "A5", gain: 0.7 }).at(2.5, "sparkle", { gain: 0.4 });
    k.at(2.6, "swish", { dur: 1.0, gain: 0.35 });
    k.at(3.3, "poly-ping", { note: "E6", gain: 0.5 });
    k.at(4.55, "swell", { dur: 0.6, gain: 0.35 });
    k.repeat(4.7, 0.09, 12, "poly-ping", { gain: 0.25, vary: 2, pitch: 0 });
    k.at(5.8, "chime", { note: "D6", gain: 0.6 }).at(5.85, "chime", { note: "A6", gain: 0.35 });
    [6.8, 7.4, 8.0].forEach((a, i) => k.at(a, "poly-ping", { note: sc[2 + i * 2], gain: 0.7 }).at(a + 0.1, "chime", { note: ["F#5", "A5", "C#6"][i], gain: 0.35 }));
    k.at(9.2, "riser", { dur: 0.8, gain: 0.25 });
    k.at(9.6, "chime", { note: "A5", gain: 0.45 }).at(9.95, "chime", { note: "D6", gain: 0.55 });
    for (let i = 0; i < 6; i++) k.at(11.0 + i * 0.08, "poly-ping", { note: sc[11 - i], gain: 0.3 });
    k.at(11.2, "chord", { notes: ["D5", "F#5", "A5", "E6"], strum: 0.06, gain: 0.55 });
  }

  Player.register({
    id: "low-poly",
    name: "Low Poly",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Exo+2:wght@600;700&display=swap",
      faces: ['700 20px "Space Grotesk"', '600 20px "Exo 2"', '700 20px "Exo 2"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Chart", "Close"],
    stills: [1.9, 3.9, 6.0, 8.6, 10.5, 12.3],
    draw,
    score,
  });
})();
