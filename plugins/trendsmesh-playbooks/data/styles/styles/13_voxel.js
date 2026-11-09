/* 13 Voxel Blocks - reference animation.
 * Topic (setting, replace it): "How does a water tower work?" - pump fills the tank, gravity pushes it to the taps,
 * every 10 m of height gives about 1 bar of pressure.
 * Rendering (keep it): one long toy world of unit cubes on a floating base slab (grass top, stepped soil underside
 * darkening with depth), seen in a fixed orthographic three-quarter view; every cube shows three tones (warm light top,
 * cool mid front-left, darkest purple-leaning right), a little colour variation per cube, soft crease darkening on
 * every face edge that touches a neighbour (ambient occlusion), ray-marched cast shadows from a light high at the back
 * left, glowing cubes with additive halos, cube-built pixel lettering, cream floating tags with an extruded edge.
 * Motion: cubes drop in course by course with a small ease-out landing, things move in whole-cube hops, the camera
 * turns a few degrees while something builds and trucks sideways along the one scene instead of cutting.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { backdrop: "#ffe3c6", grass: "#9ccc58", soil: "#c47e4a", deep: "#7f4f3e", water: "#63c4d8", orange: "#ff8a3a", tag: "#fff2df", text: "#6e3f2a" };
  const MAT = { stone: "#c9bfb6", cream: "#f6e7cf", roof: "#e5603a", pipe: "#a9b3bd", sand: "#f2d39a", glass: "#3d5a80", glow: "#fff4c2", leaf: "#6fb04a" };
  const PIX = "Tiny5", BODY = "Baloo 2";
  const DUR = 12;
  const BEATS = [0, 2.0, 4.0, 6.2, 8.4, 10.3];
  const FALL = 0.32; // seconds a cube takes to drop into place

  // ------------------------------------------------------------------ voxel renderer (reuse this)
  // World: x runs right-down, y left-down, z up. A cube at (x, y, z) fills x..x+1, y..y+1, z..z+1.
  const key = (x, y, z) => ((x + 64) * 128 + (y + 64)) * 128 + (z + 64);
  let OCC = new Set(); // landed cubes this frame (for creases and shadows)
  let CAM = null; // { unit, yaw, ox, oy } per frame
  /** Orthographic three-quarter projection, with a small yaw for the "camera turns a few degrees" move. */
  function proj(x, y, z) {
    const c = Math.cos(CAM.yaw), s = Math.sin(CAM.yaw), xr = x * c - y * s, yr = x * s + y * c;
    return [CAM.ox + (xr - yr) * 0.866 * CAM.unit, CAM.oy + (xr + yr) * 0.5 * CAM.unit - z * CAM.unit];
  }
  const occ = (x, y, z) => OCC.has(key(x, y, z));
  /** Face tones from one material colour: warm light top, cool mid front-left, darker purple-leaning right. */
  function tones(hex, vary) {
    const base = B.shade(hex, vary);
    return { top: B.mix(B.shade(base, 0.1), "#fff1d6", 0.16), left: B.mix(B.shade(base, -0.1), "#a7b8ff", 0.08), right: B.mix(B.shade(base, -0.3), "#7656b0", 0.14) };
  }
  const SHADOW_TINT = "#5b3d7a";
  /** Light from high at the back left: march from the face toward it; any landed cube on the way casts shadow. */
  const LIGHT = (() => {
    const v = [-0.7, -0.35, 1.0], l = Math.hypot(...v);
    return v.map((a) => a / l);
  })();
  function inShadow(px, py, pz) {
    for (let s = 0.55; s < 11; s += 0.55) if (occ(Math.floor(px + LIGHT[0] * s), Math.floor(py + LIGHT[1] * s), Math.floor(pz + LIGHT[2] * s))) return true;
    return false;
  }
  let AO = null; // crease gradients in unit-square space, made once per frame
  function makeAO(ctx) {
    const st = [[0, "rgba(70,34,48,0.34)"], [1, "rgba(70,34,48,0)"]];
    const lin = (x1, y1, x2, y2) => {
      const gr = ctx.createLinearGradient(x1, y1, x2, y2);
      st.forEach(([o, c]) => gr.addColorStop(o, c));
      return gr;
    };
    AO = { u0: lin(0, 0, 0.42, 0), u1: lin(1, 0, 0.58, 0), v0: lin(0, 0, 0, 0.42), v1: lin(0, 1, 0, 0.58) };
  }
  /**
   * One face: the unit square mapped onto the parallelogram O + u*U + v*V, filled, then darkened along each edge
   * that meets another cube (edges: [u0, u1, v0, v1] booleans). This crease pass is what sells the toy-block look.
   */
  function face(ctx, O, U, V, color, edges, alpha = 1) {
    ctx.setTransform(U[0] - O[0], U[1] - O[1], V[0] - O[0], V[1] - O[1], O[0], O[1]);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.fillRect(-0.004, -0.004, 1.008, 1.008);
    if (edges) {
      if (edges[0]) (ctx.fillStyle = AO.u0), ctx.fillRect(0, 0, 0.42, 1);
      if (edges[1]) (ctx.fillStyle = AO.u1), ctx.fillRect(0.58, 0, 0.42, 1);
      if (edges[2]) (ctx.fillStyle = AO.v0), ctx.fillRect(0, 0, 1, 0.42);
      if (edges[3]) (ctx.fillStyle = AO.v1), ctx.fillRect(0, 0.58, 1, 0.42);
    }
  }
  /**
   * Draw one cube item { x, y, z, col, s (size, 1 = unit), dz (drop offset), glow, landed }. Hidden faces (a landed
   * neighbour on that side) are skipped; landed cubes get creases and cast shadows.
   */
  function cube(ctx, c) {
    const s = c.s ?? 1, x = c.x + (1 - s) / 2, y = c.y + (1 - s) / 2, z = c.z + (c.dz || 0) + (s < 1 ? 0.05 : 0);
    const T = tones(c.col, c.vary || 0), full = s === 1 && c.landed, alpha = c.alpha ?? 1;
    if (c.glow) T.top = T.left = T.right = B.mix(c.col, "#ffffff", 0.35);
    // +y face (front-left, mid tone)
    if (!(full && occ(c.x, c.y + 1, c.z))) {
      let col = c.glow ? T.left : T.left;
      if (full && !c.glow && inShadow(c.x + 0.5, c.y + 1.02, c.z + 0.5)) col = B.mix(col, SHADOW_TINT, 0.3);
      face(ctx, proj(x, y + s, z + s), proj(x + s, y + s, z + s), proj(x, y + s, z), col, full && !c.glow ? [occ(c.x - 1, c.y + 1, c.z), occ(c.x + 1, c.y + 1, c.z), occ(c.x, c.y + 1, c.z + 1), occ(c.x, c.y + 1, c.z - 1)] : null, alpha);
    }
    // +x face (front-right, darkest: it faces away from the light)
    if (!(full && occ(c.x + 1, c.y, c.z))) {
      face(ctx, proj(x + s, y, z + s), proj(x + s, y + s, z + s), proj(x + s, y, z), c.glow ? B.mix(T.right, "#ffffff", 0.1) : T.right, full && !c.glow ? [occ(c.x + 1, c.y - 1, c.z), occ(c.x + 1, c.y + 1, c.z), occ(c.x + 1, c.y, c.z + 1), occ(c.x + 1, c.y, c.z - 1)] : null, alpha);
    }
    // top (lightest, warm)
    if (!(full && occ(c.x, c.y, c.z + 1))) {
      let col = T.top;
      if (full && !c.glow && inShadow(c.x + 0.5, c.y + 0.5, c.z + 1.02)) col = B.mix(col, SHADOW_TINT, 0.32);
      face(ctx, proj(x, y, z + s), proj(x + s, y, z + s), proj(x, y + s, z + s), col, full && !c.glow ? [occ(c.x - 1, c.y, c.z + 1), occ(c.x + 1, c.y, c.z + 1), occ(c.x, c.y - 1, c.z + 1), occ(c.x, c.y + 1, c.z + 1)] : null, alpha);
    }
  }
  /** Drop-in: a cube falls from a few blocks up and lands with a small ease-out. Returns null before it starts. */
  function dropOffset(t, land) {
    if (t >= land) return 0;
    if (t < land - FALL) return null;
    return (1 - B.ease.outQuad(B.prog(t, land - FALL, FALL))) * 6;
  }

  // ------------------------------------------------------------------ cube lettering (3x5 pixel font, reuse it)
  // 4x6 cells (W, A 5x6): open counters, a pointed A
  const GLYPH = {
    W: ["X...X", "X...X", "X...X", "X.X.X", "XX.XX", "X...X"], A: ["..X..", ".X.X.", "X...X", "XXXXX", "X...X", "X...X"],
    T: ["XXXX", ".XX.", ".XX.", ".XX.", ".XX.", ".XX."], E: ["XXXX", "X...", "XXX.", "X...", "X...", "XXXX"],
    R: ["XXX.", "X..X", "X..X", "XXX.", "X.X.", "X..X"], O: [".XX.", "X..X", "X..X", "X..X", "X..X", ".XX."],
  };
  /** Letters standing upright in the x-z plane at depth y: returns cube cells with their row (0 = bottom). */
  function wordCubes(word, x0, y, z0) {
    const out = [];
    let x = x0;
    for (const ch of word) {
      const g = GLYPH[ch];
      g.forEach((row, r) => [...row].forEach((c, i) => c === "X" && out.push({ x: x + i, y, z: z0 + 5 - r })));
      x += g[0].length + 1;
    }
    return out;
  }

  // ------------------------------------------------------------------ the world (the setting: replace it)
  const SLAB = { w: 60, d: 10 };
  const TOWER = { x0: 33, x1: 37, y0: 3, y1: 7 };
  const HOUSE = { x: 42, y: 4 };
  const CHART = [{ x: 4, h: 3, bar: 1 }, { x: 7, h: 6, bar: 2 }, { x: 10, h: 9, bar: 3 }]; // on the open ground the title left
  const T_TOWER = 2.15; // tower build start
  const T_CHART = 8.7; // chart columns start rising
  const T_TICK = 10.75; // closing tick icon drops in
  function grassCol(x, y) {
    if (x >= 25 && x <= 28 && y >= 3 && y <= 7) return { col: PAL.water, water: true };
    if (y === 8 && x >= 4) return { col: MAT.sand }; // a sandy path along the front
    return { col: PAL.grass };
  }
  /** Every cube in the world with its landing time (static: built once). */
  const WORLD = (() => {
    const L = [], r = B.rng(13), add = (x, y, z, col, land, o = {}) => L.push({ x, y, z, col, land: land + (!o.slab && !o.title && x > 23 && land < 2 ? 1.05 : 0), vary: (r() - 0.5) * 0.09, ...o }); // beyond the title, objects land after it
    // the base slab: soil courses first, from the bottom up, then the grass top showers in
    const layers = [[-3, 2, PAL.deep], [-2, 1, B.mix(PAL.soil, PAL.deep, 0.5)], [-1, 0, PAL.soil]];
    layers.forEach(([z, inset, col], li) => {
      for (let x = inset; x < SLAB.w - inset; x++)
        for (let y = inset; y < SLAB.d - inset; y++) {
          if (x !== SLAB.w - inset - 1 && y !== SLAB.d - inset - 1) continue; // only the exposed front rim is ever seen
          add(x, y, z, col, 0.1 + li * 0.12 + (x + y) * 0.004 + r() * 0.05, { slab: true });
        }
    });
    for (let x = 0; x < SLAB.w; x++)
      for (let y = 0; y < SLAB.d; y++) {
        const gc = grassCol(x, y);
        add(x, y, 0, gc.col, 0.45 + (x + y) * 0.006 + r() * 0.12, { slab: true, water: gc.water });
      }
    // title letters: WATER over TOWER, standing at the back of the first area
    wordCubes("WATER", 1, 1, 9).forEach((c) => add(c.x, c.y, c.z, PAL.water, 0.75 + (c.z - 9) * 0.09 + r() * 0.12, { title: true }));
    wordCubes("TOWER", 1, 1, 1).forEach((c) => add(c.x, c.y, c.z, PAL.orange, 0.55 + (c.z - 1) * 0.09 + r() * 0.12, { title: true }));
    // a few trees (trunk + leaf block) for the toy-world feel
    [[24, 8], [31, 1], [47, 8], [39, 1], [60 - 3, 1]].forEach(([x, y], i) => {
      add(x, y, 1, PAL.deep, 0.9 + i * 0.05);
      add(x, y, 2, MAT.leaf, 0.95 + i * 0.05);
      add(x, y, 3, MAT.leaf, 1.0 + i * 0.05);
    });
    // pump house by the pond
    for (let z = 1; z <= 2; z++) for (let x = 29; x <= 30; x++) for (let y = 5; y <= 6; y++) add(x, y, z, MAT.cream, 1.0 + z * 0.08 + r() * 0.05);
    for (let x = 29; x <= 30; x++) for (let y = 5; y <= 6; y++) add(x, y, 3, MAT.roof, 1.2 + r() * 0.05);
    // pipes: pump -> tower base, tower base -> house
    for (let x = 31; x <= 33; x++) add(x, 6, 1, MAT.pipe, 1.25 + (x - 31) * 0.05);
    for (let x = 37; x <= 41; x++) add(x, 6, 1, MAT.pipe, 1.3 + (x - 37) * 0.05);
    // the house with a lit window and a tap at the front
    for (let z = 1; z <= 2; z++)
      for (let x = HOUSE.x; x <= HOUSE.x + 2; x++)
        for (let y = HOUSE.y; y <= HOUSE.y + 2; y++) add(x, y, z, x === HOUSE.x + 1 && y === HOUSE.y + 2 && z === 2 ? MAT.glass : MAT.cream, 1.1 + z * 0.08 + r() * 0.05, { window: x === HOUSE.x + 1 && y === HOUSE.y + 2 && z === 2 });
    for (let x = HOUSE.x - 1; x <= HOUSE.x + 3; x++) for (let y = HOUSE.y; y <= HOUSE.y + 2; y++) add(x, y, 3, MAT.roof, 1.3 + r() * 0.05);
    for (let x = HOUSE.x; x <= HOUSE.x + 2; x++) add(x, HOUSE.y + 1, 4, MAT.roof, 1.38 + r() * 0.05);
    add(HOUSE.x + 1, HOUSE.y + 3, 2, MAT.pipe, 1.4, { s: 0.8, tap: true });
    // the water tower: legs and riser, then the tank course by course, then the cap (the diagram beat builds it)
    let k = 0;
    for (let z = 1; z <= 6; z++) {
      for (const [x, y] of [[34, 4], [36, 4], [34, 6], [36, 6], [35, 5]]) add(x, y, z, x === 35 ? MAT.pipe : MAT.stone, T_TOWER + (z - 1) * 0.1 + (k++ % 5) * 0.015);
    }
    for (let z = 7; z <= 9; z++)
      for (let x = TOWER.x0; x <= TOWER.x1; x++)
        for (let y = TOWER.y0; y <= TOWER.y1; y++) {
          const gauge = y === TOWER.y1 && x >= 34 && x <= 36;
          add(x, y, z, gauge ? MAT.glass : PAL.orange, T_TOWER + 0.6 + (z - 7) * 0.13 + r() * 0.08, { gauge });
        }
    for (let x = 34; x <= 36; x++) for (let y = 4; y <= 6; y++) add(x, y, 10, MAT.cream, T_TOWER + 1.05 + r() * 0.05);
    add(35, 5, 11, MAT.cream, T_TOWER + 1.15);
    // chart columns (key number beat) rise block by block
    CHART.forEach((c, i) => {
      for (let z = 1; z <= c.h; z++) add(c.x, 5, z, PAL.water, T_CHART + i * 0.12 + (z - 1) * 0.11, { chart: true });
    });
    // closing tick, pixel art of green cubes standing upright above the house
    ["......X", ".....X.", "X...X..", ".X.X...", "..X...."].forEach((row, rr) => [...row].forEach((ch, i) => ch === "X" && add(HOUSE.x - 2 + i, HOUSE.y + 1, 9 - rr, "#59b84a", T_TICK + (4 - rr) * 0.06 + i * 0.02, { icon: true })));
    return L;
  })();
  const ALL_LAND = WORLD.map((c) => c.land);

  /** Small water cubes hopping along a path, one whole cube per hop (flow, and the dotted-cube arrow). */
  function hopTrain(path, t, start, rate, n, gap, col, size = 0.45) {
    const out = [];
    const head = Math.floor((t - start) * rate);
    if (head < 0) return out;
    for (let i = 0; i < n; i++) {
      const idx = head - i * gap;
      if (idx < 0 || idx >= path.length) continue;
      const [x, y, z] = path[idx];
      out.push({ x, y, z, col, s: size, small: true });
    }
    return out;
  }
  // flow paths (cube cells): pump -> along the pipe -> up the riser -> into the tank; tank -> down -> to the house tap
  const PATH_UP = [[30, 6, 2], [31, 6, 2], [32, 6, 2], [33, 6, 2], [34, 6, 2], [35, 6, 3], [35, 6, 4], [35, 6, 5], [35, 6, 6], [35, 6, 7], [35, 6, 8]];
  const PATH_DOWN = [[35, 7, 7], [35, 7, 6], [35, 7, 5], [35, 7, 4], [35, 7, 3], [36, 7, 2], [37, 6, 2], [38, 6, 2], [39, 6, 2], [40, 6, 2], [41, 6, 2], [42, 7, 1]];
  /** The diagram arrow: a gentle arc of small orange cubes from the pump up to the tank, appearing one at a time. */
  const ARC = (() => {
    const pts = [];
    for (let i = 0; i <= 9; i++) {
      const k = i / 9;
      pts.push([B.lerp(30.0, 32.5, k), B.lerp(6.2, 6.6, k), B.lerp(4.4, 8.4, k) + Math.sin(k * Math.PI) * 2.2]);
    }
    return pts;
  })();
  /** Water level in the tank gauge (0..3 cubes) over time. */
  const gaugeLevel = (t) => (t < 4.3 ? 1 : B.lerp(1, 3, B.prog(t, 4.3, 1.1))) * (t > 5.6 ? B.lerp(1, 0.67, B.prog(t, 5.6, 1.4)) : 1);

  // ------------------------------------------------------------------ camera: turn a few degrees while building, truck sideways between areas
  function cameraAt(t, F) {
    const P = F.portrait;
    // [time, focus x, y, z, zoom (landscape, portrait), yaw (rad)]
    const K = [
      [0.0, 14, 2, 6, 0.6, 0.39, -0.55], // turned to face the title, so its letters read square on
      [1.95, 14, 2, 6, 0.64, 0.41, -0.48],
      [2.55, 35, 5, 5, 0.92, 0.8, -0.08],
      [3.85, 35, 5, 5, 0.96, 0.84, 0.02],
      [4.35, 32, 5, 4, 1.12, 0.98, 0.02],
      [5.0, 32, 5, 4, 1.12, 0.98, 0.02],
      [5.55, 37, 5, 5.5, 1.0, 0.8, 0.03],
      [6.15, 39, 5, 5, 1.0, 0.8, 0.03],
      [6.7, 37.5, 6, 5, 0.85, 0.8, 0.0],
      [8.05, 37.5, 6, 5, 0.87, 0.83, 0.0],
      [8.75, 6, 5, 3.4, 1.5, 1.05, -0.02],
      [10.05, 6, 5, 3.6, 1.55, 1.08, 0.02],
      [10.85, 39, 5, 5, 0.72, 0.66, 0.05],
      [12.0, 39, 5, 5, 0.76, 0.7, 0.07],
    ];
    let i = 0;
    while (i < K.length - 2 && t >= K[i + 1][0]) i++;
    const a = K[i], b = K[i + 1], k = B.ease.inOutCubic(B.clamp((t - a[0]) / (b[0] - a[0])));
    const L = (j) => B.lerp(a[j], b[j], k);
    return { fx: L(1), fy: L(2), fz: L(3) - (P ? 3.5 * (1 - B.clamp((t - 1.95) / 0.6)) + 1.8 * B.clamp((t - 6.15) / 0.55) * (1 - B.clamp((t - 8.05) / 0.7)) : 0), zoom: P ? L(5) : L(4), yaw: L(6) }; // portrait title sits higher
  }

  // ------------------------------------------------------------------ tags, brackets, bursts (screen space)
  /**
   * Floating tag: a cream card with a darker extruded side and bottom edge and a soft drop shadow; a pixel-font
   * header and an optional body line in text brown. (x, y) = where its pointer touches; s = pop scale (overshoot).
   */
  function tag(ctx, F, x, y, head, body, s, o = {}) {
    if (s <= 0.01) return null;
    const u = F.u, hs = (o.big ? 8.5 : 4.8) * u * (o.scale || 1), bs = 4.1 * u * (o.scale || 1), pad = 1.5 * u;
    ctx.save();
    ctx.font = B.font(hs, PIX, 400);
    const hw = ctx.measureText(head).width;
    ctx.font = B.font(bs, BODY, 800);
    const bw = body ? ctx.measureText(body).width : 0;
    const w = Math.max(hw, bw) + pad * 2, h = hs * 0.95 + (body ? bs * 1.15 : 0) + pad * 1.6, ex = 0.7 * u;
    let tx = x - w / 2, ty = y - h - (o.below ? -2.2 * u - h : 2.2 * u);
    const S = F.safe;
    tx = B.clamp(tx, S.x, S.r - w - ex);
    ty = B.clamp(ty, S.y, S.b - h - ex);
    ctx.translate(tx + w / 2, ty + h / 2);
    ctx.scale(s, s);
    ctx.translate(-w / 2, -h / 2);
    B.withShadow(ctx, { color: "rgba(110,63,42,0.28)", blur: 2.2 * u, y: 1.2 * u }, (g) => {
      g.fillStyle = B.shade(PAL.tag, -0.16);
      g.fillRect(ex, ex, w, h);
    });
    ctx.fillStyle = B.shade(PAL.tag, -0.16); // the extruded side and bottom edge
    ctx.beginPath();
    B.poly(ctx, [[w, 0], [w + ex, ex], [w + ex, h + ex], [ex, h + ex], [0, h], [w, h]], true);
    ctx.fill();
    ctx.fillStyle = PAL.tag;
    ctx.fillRect(0, 0, w, h);
    // pointer: a small stepped (pixel) notch toward the subject
    const px = B.clamp(x - tx, 2 * u, w - 2 * u);
    if (!o.below) {
      ctx.fillStyle = PAL.tag;
      ctx.fillRect(px - 1.2 * u, h - 0.1, 2.4 * u, 0.9 * u);
      ctx.fillRect(px - 0.5 * u, h + 0.8 * u, 1.0 * u, 0.8 * u);
    }
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillStyle = o.headColor || PAL.text;
    ctx.font = B.font(hs, PIX, 400);
    ctx.fillText(head, pad, pad * 0.8);
    if (body) {
      ctx.fillStyle = PAL.text;
      ctx.font = B.font(bs, BODY, 800);
      ctx.fillText(body, pad, pad * 0.8 + hs * 0.98);
    }
    ctx.restore();
    return { x: tx, y: ty, w, h };
  }
  /** Tag pop envelope: in with a small overshoot, out by shrinking away. */
  const tagPop = (t, a, b) => (t < a || t > b + 0.25 ? 0 : t < b ? B.ease.outBack(B.prog(t, a, 0.3), 2.2) : 1 - B.ease.inBack(B.prog(t, b, 0.25), 1.6));
  /** Blocky corner brackets that snap in around a screen rect and blink twice. */
  function brackets(ctx, F, x, y, w, h, t, at) {
    const lt = t - at;
    if (lt < 0 || lt > 1.6) return;
    if (lt > 0.35 && lt < 0.75 && Math.floor(lt * 10) % 2 === 1) return; // blink
    const u = F.u, inset = B.lerp(3 * u, 0, B.ease.outBack(B.prog(lt, 0, 0.2), 2)), c = 1.1 * u, L = 3 * u;
    ctx.save();
    ctx.fillStyle = PAL.orange;
    for (const [sx, sy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
      const cx = x - inset + sx * (w + 2 * inset) - (sx ? c : 0), cy = y - inset + sy * (h + 2 * inset) - (sy ? c : 0);
      ctx.fillRect(cx - (sx ? L - c : 0), cy, L, c);
      ctx.fillRect(cx, cy - (sy ? L - c : 0), c, L);
    }
    ctx.restore();
  }
  /** Ring of little square blocks thrown out from a point (the key number's celebration). */
  function blockRing(ctx, F, cx, cy, t, at) {
    const lt = t - at;
    if (lt < 0 || lt > 1.0) return;
    const r = B.rng(77), n = 18;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * B.TAU + r.range(-0.1, 0.1), sp = r.range(14, 24) * F.u, d = sp * B.ease.outCubic(B.clamp(lt / 0.8));
      const s = F.u * r.range(1.0, 1.8) * (1 - B.clamp((lt - 0.5) / 0.5));
      if (s <= 0) continue;
      const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d * 0.8 + lt * lt * 8 * F.u;
      if (y < 3 * F.u || y > F.H - 3 * F.u) continue; // never cut by the frame edge
      const col = [PAL.orange, PAL.water, PAL.grass, MAT.glow][i % 4];
      ctx.fillStyle = B.shade(col, 0.15);
      ctx.fillRect(x - s / 2, y - s / 2, s, s * 0.6);
      ctx.fillStyle = B.shade(col, -0.2);
      ctx.fillRect(x - s / 2, y + s * 0.1, s, s * 0.4);
    }
  }

  // ------------------------------------------------------------------ frame
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    // backdrop: warm peach studio sweep, lighter toward the middle
    ctx.fillStyle = B.radial(ctx, W / 2, H * 0.48, 0, Math.hypot(W, H) * 0.62, [[0, B.shade(PAL.backdrop, 0.45)], [0.55, PAL.backdrop], [1, B.shade(PAL.backdrop, -0.08)]]);
    ctx.fillRect(0, 0, W, H);
    const cam = cameraAt(t, F);
    CAM = { unit: u * (P ? 6.2 : 4.6) * cam.zoom, yaw: cam.yaw, ox: 0, oy: 0 };
    const f = proj(cam.fx, cam.fy, cam.fz);
    CAM.ox = W / 2 - f[0];
    CAM.oy = F.safe.cy + 2 * u - f[1];
    // cubes present this frame (falling ones carry a drop offset); occupancy from landed ones
    OCC = new Set();
    const items = [];
    const glowOn = B.prog(t, 10.6, 0.4);
    for (const c of WORLD) {
      const dz = dropOffset(t, c.land);
      if (dz == null) continue;
      if (dz === 0 && !(c.s < 1)) OCC.add(key(c.x, c.y, c.z));
      let col = c.col;
      if (c.gauge) col = c.z - 7 < gaugeLevel(t) - 0.01 ? PAL.water : MAT.glass;
      const glow = (c.gauge && col === PAL.water) || (c.window && glowOn > 0.5);
      if (c.window && glow) col = MAT.glow;
      if (c.water) col = B.shade(PAL.water, 0.06 * Math.sin(t * 3 + c.x * 1.3 + c.y * 0.7));
      // the title hops up and shrinks away in whole steps before the camera trucks off
      let sz = c.s, hop = 0;
      if (c.title || c.chart) { // (the chart goes the same way before the close)
        const k = Math.floor(B.prog(t, (c.title ? 1.86 : 10.45) + c.x * 0.004, 0.22) * 4) / 4;
        if (k >= 1) continue;
        [sz, hop] = [k ? 1 - k * 0.8 : c.s, k * 3];
      }
      items.push({ ...c, col, dz: dz + hop, landed: dz === 0 && !hop, glow, s: sz });
    }
    // water hopping through the pipes (steps 1 and 2), the drip at the tap (step 3), the diagram's cube arrow
    items.push(...hopTrain(PATH_UP, t, 4.35, 9, 5, 2, PAL.water));
    items.push(...hopTrain(PATH_DOWN, t, 5.6, 9, 6, 2, PAL.water));
    // the tap gushes: a jet of water cubes hopping out and down in whole steps, and a puddle that spreads
    if (t > 6.8 && t < 8.6) for (let i = 0; i < 12; i++) {
      const q = Math.floor(B.fract((t - 6.8) * 2.5 + i / 12) * 8) / 8;
      items.push({ x: HOUSE.x + 1.2, y: HOUSE.y + 3.4 + q * 2.2, z: 2.1 - q * q * 1.15, col: PAL.water, s: 0.5, small: true });
    }
    for (let i = 0; i < Math.min(6, (t - 7) * 5); i++) items.push({ x: HOUSE.x + 0.4 + (i % 3) * 0.5, y: HOUSE.y + 5.3 + (i > 2 ? 0.5 : 0), z: 0.95, col: PAL.water, s: 0.5, small: true });
    const arcShown = Math.floor(B.clamp((t - 3.1) / 0.5) * ARC.length);
    const arcFade = 1 - B.prog(t, 4.05, 0.25);
    if (arcFade > 0) for (let i = 0; i < arcShown; i++) items.push({ x: ARC[i][0] - 0.5, y: ARC[i][1] - 0.5, z: ARC[i][2] - 0.5, col: PAL.orange, s: i === ARC.length - 1 ? 0.7 : 0.5, small: true, alpha: arcFade });
    // painter's order: back to front by x + y + z (falling cubes sort by where they will land)
    items.sort((a, b) => a.x + a.y + a.z - (b.x + b.y + b.z) || a.z - b.z);
    // blurred contact shadow of the floating slab on the backdrop
    const sc = [proj(1, 1, -9), proj(SLAB.w - 1, 1, -9), proj(SLAB.w - 1, SLAB.d - 1, -9), proj(1, SLAB.d - 1, -9)];
    B.withFilter(ctx, `blur(${(2.4 * u * cam.zoom).toFixed(1)}px)`, (g) => {
      g.fillStyle = "rgba(170,96,62,0.34)";
      g.beginPath();
      B.poly(g, sc, true);
      g.fill();
    });
    makeAO(ctx);
    ctx.save();
    const m = 2 * CAM.unit;
    for (const c of items) {
      const p = proj(c.x + 0.5, c.y + 0.5, c.z + (c.dz || 0));
      if (p[0] < -m || p[0] > W + m || p[1] < -m * 2 || p[1] > H + m) continue;
      cube(ctx, c);
    }
    ctx.restore();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    // additive halos around glowing cubes (gauge water, lit window)
    for (const c of items)
      if (c.glow && c.landed) {
        const p = proj(c.x + 0.5, c.y + 1, c.z + 0.5);
        B.glow(ctx, p[0], p[1], CAM.unit * (c.window ? 1.6 : 1.0), c.window ? "#ffd27a" : "#9ef0ff", c.window ? 0.4 : 0.14, { add: true });
      }
    // ------------------------------------------------ labels and numbers on floating tags
    const at = (x, y, z) => proj(x, y, z);
    tag(ctx, F, ...at(14, 9, 0), "How does it work?", null, tagPop(t, 1.3, 1.9), { below: true, scale: 1.1 });
    const dTag = (p, head, body, a) => tag(ctx, F, p[0], p[1], head, body, tagPop(t, a, 3.95));
    dTag(at(35, 5, 11.5), "TANK", "stores water up high", 3.05);
    tag(ctx, F, ...at(28, 9, 0), "PUMP", "lifts water in", tagPop(t, 3.25, 3.95), { below: true });
    tag(ctx, F, ...at(37, 8, 0.2), "LEGS", "hold it 30 m up", tagPop(t, 3.45, 3.95), { below: true });
    // steps
    tag(ctx, F, ...at(31, 6, 4.5), "1  PUMP IT UP", "at night, when power is cheap", tagPop(t, 4.2, 5.4));
    tag(ctx, F, ...at(37, 8, 0.2), "2  GRAVITY", "pushes it down the pipes", tagPop(t, 5.55, 6.35), { below: true });
    tag(ctx, F, ...at(HOUSE.x + 1.5, HOUSE.y + 6.2, 0.9), "3  OPEN A TAP", "water rushes out, no pump", tagPop(t, 6.75, 8.2), { below: true });
    const tap = proj(HOUSE.x + 1.5, HOUSE.y + 3.5, 2.6);
    brackets(ctx, F, tap[0] - 2.4 * CAM.unit * 0.5, tap[1] - 1.6 * CAM.unit * 0.5, 2.4 * CAM.unit * 0.5, 2.4 * CAM.unit * 0.5, t, 7.0);
    // key number: column tags ride on top, ticking up as each column rises; then the key tag swells
    // (portrait: above the columns; landscape: hanging below the slab, clear of the column tags)
    const kp = P ? proj(7.5, 2, 16.5) : proj(-2, 5, 9); // clear of the column tags and bases
    const swell = t < 9.75 ? 0 : t < 10.2 ? B.ease.outBack(B.prog(t, 9.75, 0.35), 2.6) : 1 - B.ease.inBack(B.prog(t, 10.2, 0.25), 1.6);
    if (swell > 0) blockRing(ctx, F, kp[0], kp[1] - 12 * u, t, 9.85); // thrown out from behind the tag
    CHART.forEach((c, i) => {
      const risen = WORLD.filter((w) => w.chart && w.x === c.x && t >= w.land).length;
      if (risen === 0) return;
      const p = proj(c.x + 0.5, 5.5, risen + 0.4);
      const m = Math.round((risen / c.h) * c.bar * 10);
      tag(ctx, F, p[0], p[1], `${m} m`, `${(m / 10).toFixed(1)} bar`, tagPop(t, T_CHART + i * 0.12, 10.4), { scale: 0.95 });
    });
    tag(ctx, F, kp[0], kp[1], "+1 bar", "for every 10 m of height", swell, { big: true, scale: P ? 1.4 : 1.25, headColor: PAL.orange });
    // close
    const cp = proj(HOUSE.x - 1, HOUSE.y + 1, 15); // above the tank, clear of it
    tag(ctx, F, cp[0], cp[1], "HIGH TANK = STRONG TAP", "height does the pushing", tagPop(t, 10.8, 13));
    // finishing: warm edge vignette and a very fine static grain
    B.vignette(ctx, W, H, { color: "#c46a3a", amount: 0.22, inner: 0.55, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.035, mode: "overlay", seed: 4 });
  }

  // ------------------------------------------------------------------ sound: plastic clicks, patter, thunks, toy chimes
  SOUND.define("voxel-click", (v) => {
    // hollow plastic snap: a short resonant knock plus a tiny bright tick
    v.tone({ f: 1350, f2: 900, glide: 0.03, a: 0.0008, len: 0.05, peak: 0.16 });
    v.noise({ filter: "bandpass", f: 3200, q: 3, a: 0.0005, len: 0.025, peak: 0.25 });
    v.tone({ f: 420, a: 0.001, len: 0.06, peak: 0.1 });
  }, { verb: 0.12 });
  SOUND.define("voxel-thunk", (v) => {
    v.tone({ f: 160, f2: 85, glide: 0.08, a: 0.002, len: 0.16, peak: 0.45 });
    v.noise({ filter: "lowpass", f: 900, a: 0.001, len: 0.06, peak: 0.25 });
    v.sub("voxel-click", 0, { pitch: -7 });
  }, { verb: 0.18 });

  function score(k) {
    k.bed("arp", 0.5, DUR, { gain: 0.45, step: 0.25, notes: SOUND.scale("C4", "major", 8) });
    // the patter of the builds follows the actual landing times of the cubes (thinned)
    ALL_LAND.filter((_, i) => i % 9 === 0).forEach((t0) => k.at(t0, "voxel-click", { gain: 0.32, pitch: k.rng() * 6 - 3, pan: k.rng() * 0.6 - 0.3 }));
    k.at(0.62, "voxel-thunk", { gain: 0.6 }).at(1.25, "voxel-thunk", { gain: 0.5 });
    k.at(1.4, "pop", { gain: 0.5 });
    k.at(1.9, "swish", { gain: 0.35 }).at(T_TOWER + 1.15, "voxel-thunk", { gain: 0.7 });
    [3.05, 3.25, 3.45].forEach((a) => k.at(a, "pop", { gain: 0.45, pitch: 2 }));
    k.repeat(3.35, 0.06, 9, "voxel-click", { gain: 0.28, pitch: 5, vary: 1 });
    k.at(4.2, "pop").at(4.35, "bubble", { gain: 0.4 }).repeat(4.4, 0.111, 9, "voxel-click", { gain: 0.22, pitch: 8, vary: 1 });
    k.at(5.55, "pop").at(5.6, "bubble", { gain: 0.4 }).repeat(5.65, 0.111, 10, "voxel-click", { gain: 0.22, pitch: 6, vary: 1 });
    k.at(6.2, "swish", { gain: 0.3 }).at(6.75, "pop").repeat(6.65, 0.25, 6, "bubble", { gain: 0.3, vary: 2 });
    k.at(7.0, "chime", { note: "E6", gain: 0.25 }).at(7.1, "chime", { note: "G6", gain: 0.2 });
    k.at(8.4, "swish", { gain: 0.35 });
    k.at(T_CHART + 0.95, "voxel-thunk", { gain: 0.6 });
    k.at(9.75, "success", { gain: 0.5 }).at(9.85, "sparkle", { gain: 0.35 }).repeat(9.85, 0.03, 8, "voxel-click", { gain: 0.25, pitch: 9, vary: 3 });
    k.at(10.2, "swish", { gain: 0.35 });
    k.at(10.6, "chime", { note: "C6", gain: 0.3 }).at(10.75, "chime", { note: "E6", gain: 0.25 }).at(11.1, "chime", { note: "G6", gain: 0.3 });
    k.at(11.05, "pop", { gain: 0.5 });
  }

  Player.register({
    id: "voxel",
    name: "Voxel Blocks",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Tiny5&family=Baloo+2:wght@800&display=swap",
      faces: ['400 20px "Tiny5"', '800 20px "Baloo 2"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Steps 1-2", "Step 3", "Key number", "Close"],
    stills: [1.6, 3.75, 5.9, 7.7, 10.05, 11.7],
    draw,
    score,
  });
})();
