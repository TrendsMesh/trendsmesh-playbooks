/* 32 Isometric Diorama - reference animation.
 * Topic (setting, replace it): "How does a recycling plant sort cans?" - belt, magnet, eddy current.
 * Rendering (keep it): a tidy miniature world on one thick floating slab in true isometric projection (vertical
 * edges upright, the other two at the same tilt, never a vanishing point). Every block has three flat faces (light
 * top, mid left, darker right) in soft pastels, thin white highlights on its top edges, a faint dimming where it
 * meets the floor, and a long soft pale shadow falling one way across the tile (drawn at low resolution so it is
 * soft). The slab is cut to show its layers and casts a soft shadow onto the quiet backdrop. One coral accent marks
 * the thing that matters. White rounded tags on short stems, dashed arrows lying on the ground plane that bend at
 * right angles, a billboard standing on the tile with the number on its face, block towers as the chart.
 * Motion: the slab rises in, blocks pop up from the floor one by one with a springy overshoot, small things stay
 * alive (belt, cans, magnet, fan, blinking lights, strolling people), the camera slides across the tile between
 * beats without ever changing angle, and pieces leave by sinking back into the slab.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { back: "#eaf1f6", top: "#f7f3ea", left: "#cdd9e6", right: "#a9bbd0", mint: "#9fd8c2", butter: "#f5de9a", coral: "#f26b5b", shadow: "#c3cfdb" };
  const INK = "#4f5d70"; // label and title text: the right face, much deeper
  const ROUND = "Nunito", SANS = "DM Sans";
  const DUR = 12.5;
  const BEATS = [0, 2.0, 4.3, 6.3, 9.0, 10.8];
  const GW = 14, GH = 10; // the tile, in grid units
  let SLAB = 1.5; // its thickness: portrait cuts a deeper cross-section of earth, filling the tall frame

  // ------------------------------------------------------------------ projection and camera
  let UN = 40, OX = 0, OY = 0, CAM = { x: 0, y: 0, z: 1 }, Fr = null, T = 0, TS = 30; // TS: label text size (4.4u / 4.2u)
  /** Grid point (x right-down, y left-down, z up) -> scene px. */
  const pr = (x, y, z = 0) => [OX + (x - y) * UN * 0.866, OY + (x + y) * UN * 0.5 - z * UN];
  /** Scene px -> screen px under the camera (labels are set in screen space so they keep their size). */
  const scr = (p) => [Fr.W / 2 + (p[0] - CAM.x) * CAM.z, Fr.H / 2 + (p[1] - CAM.y) * CAM.z];
  const tones = (c) => ({ top: B.mix(c, "#ffffff", 0.42), left: c, right: B.shade(c, -0.13) });
  const NEUTRAL = { top: PAL.top, left: PAL.left, right: PAL.right };

  // ------------------------------------------------------------------ diorama helpers (reuse these)
  function face(g, pts, col) {
    g.beginPath();
    B.poly(g, pts, true);
    g.fillStyle = col;
    g.fill();
  }
  /** Ambient dimming: a faint darker band at the foot of a side face where it touches the floor. */
  function footDim(g, a, b, z) {
    const p0 = pr(...a, z), p1 = pr(...b, z), h = 0.32 * UN;
    g.fillStyle = B.linear(g, 0, p0[1], 0, p0[1] - h, [B.rgba("#3a4a60", 0.13), B.rgba("#3a4a60", 0)]);
    g.beginPath();
    B.poly(g, [p0, p1, [p1[0], p1[1] - h], [p0[0], p0[1] - h]], true);
    g.fill();
  }
  /** Box with three flat faces, white highlights along its top front edges, dimmed feet. c = { top, left, right }. */
  function block(g, x, y, z, sx, sy, sz, c, o = {}) {
    if (sz <= 0.002) return;
    face(g, [pr(x, y + sy, z), pr(x + sx, y + sy, z), pr(x + sx, y + sy, z + sz), pr(x, y + sy, z + sz)], c.left);
    face(g, [pr(x + sx, y, z), pr(x + sx, y + sy, z), pr(x + sx, y + sy, z + sz), pr(x + sx, y, z + sz)], c.right);
    face(g, [pr(x, y, z + sz), pr(x + sx, y, z + sz), pr(x + sx, y + sy, z + sz), pr(x, y + sy, z + sz)], c.top);
    if (o.foot !== false && z < 0.01 && sz > 0.3) {
      footDim(g, [x, y + sy], [x + sx, y + sy], z);
      footDim(g, [x + sx, y], [x + sx, y + sy], z);
    }
    g.save();
    g.strokeStyle = "rgba(255,255,255,0.95)";
    g.lineWidth = Math.max(1, 0.045 * UN);
    g.lineJoin = g.lineCap = "round";
    g.beginPath();
    B.poly(g, [pr(x, y + sy, z + sz), pr(x + sx, y + sy, z + sz), pr(x + sx, y, z + sz)]);
    g.stroke();
    g.globalAlpha = 0.45;
    g.beginPath();
    B.poly(g, [pr(x + sx, y + sy, z + sz), pr(x + sx, y + sy, z)]);
    g.stroke();
    g.restore();
  }
  /** Upright cylinder: split side (lit left half, darker right half), flat top, white rim on its front. */
  function cyl(g, x, y, z, r, h, c) {
    if (h <= 0.002) return;
    const rx = r * UN * 1.2247, ry = r * UN * 0.7071, b = pr(x, y, z), t = pr(x, y, z + h);
    const side = (x0, x1, col) => {
      g.save();
      g.beginPath();
      g.rect(x0, t[1] - ry - 2, x1 - x0, b[1] - t[1] + 2 * ry + 4);
      g.clip();
      g.beginPath();
      g.moveTo(t[0] - rx, t[1]);
      g.lineTo(b[0] - rx, b[1]);
      g.ellipse(b[0], b[1], rx, ry, 0, Math.PI, 0, true);
      g.lineTo(t[0] + rx, t[1]);
      g.closePath();
      g.fillStyle = col;
      g.fill();
      g.restore();
    };
    side(b[0] - rx - 1, b[0], c.left);
    side(b[0], b[0] + rx + 1, c.right);
    g.beginPath();
    g.ellipse(t[0], t[1], rx, ry, 0, 0, B.TAU);
    g.fillStyle = c.top;
    g.fill();
    g.strokeStyle = "rgba(255,255,255,0.9)";
    g.lineWidth = Math.max(1, 0.04 * UN);
    g.beginPath();
    g.ellipse(t[0], t[1], rx, ry, 0, 0.15, Math.PI - 0.15);
    g.stroke();
  }
  /** Long shadow on the floor: the footprint swept along the light (falls toward +x, a little +y). */
  function shadow(sg, x, y, sx, sy, h) {
    if (h <= 0.01) return;
    const dx = h * 1.05, dy = h * 0.32;
    sg.beginPath();
    B.poly(sg, [pr(x, y), pr(x + sx, y), pr(x + sx + dx, y + dy), pr(x + sx + dx, y + sy + dy), pr(x + dx, y + sy + dy), pr(x, y + sy)], true);
    sg.fill();
  }
  /** Iso circle lying on the floor (radius in grid units). */
  function floorRing(g, x, y, r, z = 0) {
    const c = pr(x, y, z);
    g.ellipse(c[0], c[1], r * UN * 1.2247, r * UN * 0.7071, 0, 0, B.TAU);
  }
  /** Dashed arrow lying on the ground plane: grid waypoints, right-angle bends, drawn on to p. */
  function groundArrow(g, pts, p, col = INK) {
    B.arrow(g, pts.map((q) => pr(q[0], q[1], q[2] || 0.02)), { p, width: 0.09 * UN, color: col, dash: [0.28 * UN, 0.2 * UN], head: 0.42 * UN, headStyle: "tri", alpha: 0.85 });
  }
  /** Springy pop from the floor (height scale), and sinking back. */
  const rise = (t, at, out = 99) => (t < at ? 0 : B.ease.outBack(B.prog(t, at, 0.45), 2.4)) * (1 - B.prog(t, out, 0.45, "inBack"));
  /**
   * White rounded tag pinned to a scene point by a stem, the tag set in free space beside the slab so it covers
   * nothing. q: { y (row centre) and f (where the stem leaves the tag's width, 0..1: a vertical stem) } or { x, y }
   * (tag centre; the stem leaves its nearest edge). Text may hold "\n"; o.num puts a coral step number first.
   */
  function tag(ctx, pin, text, s, q, o = {}) {
    if (s <= 0.01) return;
    const u = Fr.u, size = TS, [px, py] = scr(pin);
    ctx.font = B.font(size, ROUND, 800);
    const ls = text.split("\n"), dw = o.num ? size * 1.6 : 0, w = Math.max(...ls.map((l) => ctx.measureText(l).width)) + size * 1.5 + dw, h = size * (1.9 + 1.2 * (ls.length - 1));
    const cx = q.f != null ? px - q.f * w + w / 2 : q.x, cy = q.y, sx = B.clamp(px, cx - w / 2 + h * 0.4, cx + w / 2 - h * 0.4), sy = py > cy ? cy + h / 2 : cy - h / 2;
    ctx.save();
    ctx.globalAlpha = Math.min(1, s);
    ctx.strokeStyle = B.rgba(INK, 0.6);
    ctx.lineWidth = 0.32 * u;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(B.lerp(sx, px, Math.min(1, s)), B.lerp(sy, py, Math.min(1, s)));
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    B.circle(ctx, px, py, 0.7 * u);
    ctx.fill();
    ctx.stroke();
    ctx.translate(cx, cy);
    ctx.scale(s, s);
    B.withShadow(ctx, { color: B.rgba("#506480", 0.18), blur: u * 1.2, y: u * 0.3 }, () => {
      ctx.beginPath();
      B.roundRect(ctx, -w / 2, -h / 2, w, h, size * 0.85);
      ctx.fill();
    });
    if (o.num) {
      ctx.fillStyle = PAL.coral;
      ctx.beginPath();
      B.circle(ctx, -w / 2 + size * 0.95, 0, size * 0.68);
      ctx.fill();
      B.text(ctx, String(o.num), -w / 2 + size * 0.95, size * 0.04, { size, minSize: size, family: ROUND, weight: 900, color: "#ffffff" });
    }
    B.text(ctx, text, dw / 2, size * 0.04, { size, minSize: size, family: ROUND, weight: 800, color: INK, lineH: 1.2 });
    ctx.restore();
  }

  // ------------------------------------------------------------------ the plant (the setting: replace these)
  // can stream: spawn every 0.62 s at the hopper, ride the belt; steel ones get lifted by the magnet, aluminium
  // ones are flung by the eddy current into the coral bin.
  const SPEED = 1.7, PERIOD = 0.62, KINDS = "SASSAASA";
  function cans(t) {
    const out = [];
    for (let i = -14; i < 30; i++) {
      const born = i * PERIOD, a = t - born, steel = KINDS[((i % 8) + 8) % 8] === "S";
      if (a < 0) continue;
      let x = 2.9 + a * SPEED, y = 4.5, z = 0.62, gone = false;
      if (steel && x > 6.1) {
        const k = a - (6.1 - 2.9) / SPEED;
        x = 6.1;
        z = 0.62 + 0.8 * B.ease.outCubic(B.clamp(k / 0.3)); // lifted up to the magnet's face, carried over the bin
        y = 4.5 + 2.0 * B.ease.inOutSine(B.clamp((k - 0.3) / 0.5));
        if (k > 0.8) z = 1.42 - 1.2 * B.clamp((k - 0.8) / 0.25);
        if (k > 1.05) gone = true;
      } else if (!steel && x > 11.1) {
        const k = B.clamp((a - (11.1 - 2.9) / SPEED) / 0.55);
        x = B.lerp(11.1, 12.95, k);
        y = B.lerp(4.5, 2.65, k);
        z = 0.62 + Math.sin(k * Math.PI) * 1.6 + k * 0.2;
        if (k >= 1) gone = true;
      }
      if (!gone) out.push({ x, y, z, steel });
    }
    return out;
  }
  function can(g, c) {
    cyl(g, c.x, c.y, c.z, 0.3, 0.6, c.steel ? tones("#b9c6d6") : tones(PAL.coral));
  }
  /** Tree: two stacked cones, lit half and shade half. */
  function tree(g, x, y, s) {
    if (s <= 0.01) return;
    cyl(g, x, y, 0, 0.07, 0.35 * s, tones("#c9b79a"));
    [[0.3, 0.9, 0.42], [0.85, 0.75, 0.32]].forEach(([z0, h, r]) => {
      const b = pr(x, y, z0 * s), tp = pr(x, y, (z0 + h) * s), rx = r * UN * 1.2247 * s;
      face(g, [[b[0] - rx, b[1]], [b[0], b[1] + r * UN * 0.5 * s], tp], B.mix(PAL.mint, "#ffffff", 0.15));
      face(g, [[b[0], b[1] + r * UN * 0.5 * s], [b[0] + rx, b[1]], tp], B.shade(PAL.mint, -0.16));
    });
  }
  /** Faceless little person: capsule body and round head, bobbing as they stroll. */
  function person(g, x, y, col, phase) {
    const bob = Math.abs(Math.sin((T + phase) * 7)) * 0.05, p = pr(x, y, bob), s = UN * 0.16;
    g.fillStyle = col;
    g.beginPath();
    B.capsule(g, p[0] - s * 0.55, p[1] - s * 2.6, s * 1.1, s * 2.4);
    g.fill();
    g.fillStyle = PAL.top;
    g.beginPath();
    B.circle(g, p[0], p[1] - s * 3.2, s * 0.62);
    g.fill();
  }
  const walk = (path, k) => {
    const q = B.pointAt(path, B.fract(k));
    return [q[0], q[1]];
  };
  const PATHS = [[[2, 7.2], [7.4, 7.2], [7.4, 9.2], [2, 9.2], [2, 7.2]], [[4.2, 1.2], [4.2, 3.0], [9.8, 3.0], [9.8, 1.2], [4.2, 1.2]]];

  /** Everything standing on the tile, as depth-sorted draw jobs (plus their shadows). */
  function objects(t, L) {
    const J = [], S = [];
    const add = (key, f, sh) => {
      J.push([key, f]);
      if (sh) S.push(sh);
    };
    const bx = (x, y, z, sx, sy, sz, c, at, out, o) => {
      const h = sz * rise(t, at, out);
      add(x + sx / 2 + y + sy / 2 + (o && o.k ? o.k : 0), (g) => block(g, x, y, z, sx, sy, h, c, o), [x, y, sx, sy, h + z]);
      return h;
    };
    // control house with strip windows, a turning fan and a blinking light
    const hh = bx(0.6, 0.6, 0, 3, 2, 1.5, NEUTRAL, 0.35);
    add(5.2, (g) => {
      if (hh < 0.3) return;
      for (let i = 0; i < 4; i++) face(g, [pr(0.8 + i * 0.7, 2.6, hh * 0.45), pr(1.25 + i * 0.7, 2.6, hh * 0.45), pr(1.25 + i * 0.7, 2.6, hh * 0.72), pr(0.8 + i * 0.7, 2.6, hh * 0.72)], B.shade(PAL.right, -0.15));
      const f = pr(1.6, 1.4, hh + 0.02), a = t * 9;
      g.save();
      g.translate(f[0], f[1]);
      g.scale(1, 0.577);
      g.fillStyle = PAL.right;
      g.beginPath();
      B.circle(g, 0, 0, 0.42 * UN * 1.22);
      g.fill();
      g.fillStyle = PAL.top;
      for (let i = 0; i < 3; i++) {
        g.beginPath();
        g.ellipse(Math.cos(a + i * 2.094) * 0.22 * UN, Math.sin(a + i * 2.094) * 0.22 * UN, 0.2 * UN, 0.07 * UN, a + i * 2.094, 0, B.TAU);
        g.fill();
      }
      g.restore();
      const lp = pr(3.3, 1.0, hh + 0.12);
      g.fillStyle = Math.floor(t * 2.5) % 2 ? PAL.coral : B.mix(PAL.coral, PAL.top, 0.6);
      g.beginPath();
      B.circle(g, lp[0], lp[1], 0.09 * UN);
      g.fill();
    });
    // hopper, belt (with its cans), magnet, bins, eddy-current drum
    bx(1.2, 3.8, 0, 1.5, 1.6, 1.9, tones(PAL.butter), 0.45);
    const beltH = bx(2.8, 4.05, 0, 8.4, 0.9, 0.62, NEUTRAL, 0.55, 99, { foot: false });
    const cs = cans(t);
    add(9.6, (g) => {
      if (beltH < 0.6) return;
      for (let i = 0; i < 26; i++) {
        const x = 2.9 + B.fract(i / 26 + t * SPEED / 8.4) * 8.2;
        face(g, [pr(x, 4.1, 0.625), pr(x + 0.05, 4.1, 0.625), pr(x + 0.05, 4.9, 0.625), pr(x, 4.9, 0.625)], B.rgba(PAL.right, 0.6));
      }
      cs.filter((c) => c.z < 0.7 && c.x <= 11.1).forEach((c) => can(g, c));
    });
    const mh = rise(t, 0.75);
    add(11.4, (g) => {
      block(g, 5.55, 3.55, 0, 0.18, 0.18, 2.1 * mh, NEUTRAL);
      block(g, 5.55, 6.85, 0, 0.18, 0.18, 2.1 * mh, NEUTRAL);
      cs.filter((c) => c.steel && c.z >= 0.7).forEach((c) => can(g, c));
      if (mh > 0.5) block(g, 5.5, 3.5, 2.1 * mh - 0.05, 1.2, 3.6, 0.42, tones(PAL.mint));
    }, [5.5, 3.5, 1.2, 3.6, 2.4 * mh]);
    bx(5.45, 6.1, 0, 1.3, 1.3, 0.85, tones(PAL.mint), 0.85, 99, { k: 0.5 });
    bx(11.2, 3.95, 0, 1.0, 1.0, 0.7, tones(PAL.butter), 0.9);
    add(16.1, (g) => cyl(g, 11.7, 4.45, 0.7 * rise(t, 0.9), 0.38, 0.22 * rise(t, 0.9), tones(PAL.mint)));
    const coralH = bx(12.3, 2.0, 0, 1.3, 1.3, 1.0, tones(PAL.coral), 1.0);
    bx(12.4, 5.7, 0, 1.1, 1.1, 0.7, NEUTRAL, 1.05);
    add(16, (g) => cs.filter((c) => !c.steel && c.x > 11.1).forEach((c) => can(g, c)));
    // billboard standing on the tile (its face is drawn later, with the number)
    // the billboard stands for the title, the key number and the close; it sinks while the parts are labelled
    const bb = Math.max(rise(t, 1.1, BEATS[1] - 0.4), rise(t, BEATS[2] + 0.05, 6.3), rise(t, BEATS[5] + 0.2));
    for (const px of [7.7, 11.2]) add(px + 1.6, (g) => block(g, px, 1.5, 0, 0.16, 0.16, 1.35 * bb, NEUTRAL), [px, 1.5, 0.16, 0.16, 1.35 * bb]);
    add(13, (g) => block(g, 7.2, 1.45, 1.3 * bb, 4.6, 0.2, 4 * bb, { top: PAL.top, left: "#ffffff", right: PAL.left }), [7.2, 1.45, 4.6, 0.2, 5.3 * bb]);
    // bales waiting to ship, trees, strolling people
    [[2.3, 6.1, 0], [3.3, 6.1, 0], [2.3, 6.1, 0.7]].forEach(([x, y, z], i) => bx(x, y, z, 0.9, 0.9, 0.7, tones(PAL.butter), 1.2 + i * 0.1));
    [[0.7, 8.6, 1.1], [1.6, 9.2, 0.9], [13.1, 8.9, 1.2], [13.2, 0.8, 1], [4.6, 0.6, 0.8]].forEach(([x, y, s], i) => {
      const k = rise(t, 1.25 + i * 0.07);
      add(x + y, (g) => tree(g, x, y, s * k), [x - 0.2, y - 0.2, 0.4, 0.4, 1.4 * s * k]);
    });
    const pc = [PAL.coral, PAL.mint, PAL.butter];
    [[0, 0.0, 0.035], [0, 0.45, 0.03], [1, 0.2, 0.025]].forEach(([pi, ph, sp], i) => {
      if (t < 1.4) return;
      const [x, y] = walk(PATHS[pi], ph + t * sp);
      add(x + y, (g) => person(g, x, y, pc[i], i), [x - 0.1, y - 0.1, 0.2, 0.2, 0.5]);
    });
    // chart: two towers of thin blocks (energy for one can), the tallest in coral
    const tw = [[8.6, 7.6, 20, tones(PAL.coral)], [10.1, 7.6, 1, tones(PAL.mint)]]; // side by side, nothing in front of either
    tw.forEach(([x, y, n, c]) => {
      let k = 0;
      for (let i = 0; i < n; i++) k += rise(t, L.chartAt + 0.3 + i * 0.045, L.sinkAt);
      add(x + y + 1, (g) => {
        for (let i = 0; i < Math.ceil(k); i++) block(g, x, y, i * 0.3, 1, 1, 0.3 * B.clamp(k - i), c, { foot: i === 0 });
      }, [x, y, 1, 1, k * 0.3]);
    });
    return { J: J.sort((a, b) => a[0] - b[0]), S, coralH, bb };
  }

  // ------------------------------------------------------------------ the slab
  function slab(g, rise01) {
    const z0 = -SLAB, c = [pr(0, 0), pr(GW, 0), pr(GW, GH), pr(0, GH)];
    // it floats: its footprint's soft shadow lies on the backdrop well below it
    B.withFilter(g, `blur(${(1.6 * UN * CAM.z).toFixed(1)}px)`, () => {
      g.globalAlpha = 0.16 * rise01;
      face(g, [pr(0.8, 0.8, -SLAB - 3.2), pr(GW - 0.8, 0.8, -SLAB - 3.2), pr(GW - 0.8, GH - 0.8, -SLAB - 3.2), pr(0.8, GH - 0.8, -SLAB - 3.2)], "#5a7090");
      g.globalAlpha = 1;
    });
    // soft drop shadow on the backdrop
    B.withShadow(g, { color: B.rgba("#5a7090", 0.28 * rise01), blur: 3.5 * UN, y: 1.4 * UN }, () => face(g, [c[0], c[1], pr(GW, 0, z0), pr(GW, GH, z0), pr(0, GH, z0), c[3]], PAL.right));
    // cross-section: floor plate, packed sand, bands of earth (deeper ones darker, sand and clay between)
    const sand = B.mix(PAL.butter, PAL.top, 0.3), lay = [[0.22, PAL.top], [0.6, sand], [1.05, PAL.left], [1.5, B.shade(PAL.left, -0.08)], [2.1, B.mix(sand, PAL.left, 0.4)], [2.9, B.shade(PAL.left, -0.12)], [3.3, B.mix(PAL.mint, PAL.left, 0.6)], [9, B.shade(PAL.left, -0.16)]];
    const bands = lay.map(([b, col], i) => [i ? lay[i - 1][0] : 0, Math.min(b, SLAB), col, B.shade(col, -0.12)]).filter(([a, b]) => a < SLAB);
    bands.forEach(([a, b, l, r]) => {
      face(g, [pr(0, GH, -a), pr(GW, GH, -a), pr(GW, GH, -b), pr(0, GH, -b)], l);
      face(g, [pr(GW, 0, -a), pr(GW, GH, -a), pr(GW, GH, -b), pr(GW, 0, -b)], r);
    });
    const rr = B.rng(32);
    for (let i = 0; i < 40; i++) {
      const onLeft = i % 2, k = rr(), d = rr.range(0.7, SLAB - 0.1);
      const p = onLeft ? pr(k * GW, GH, -d) : pr(GW, k * GH, -d);
      g.fillStyle = B.rgba("#ffffff", 0.35);
      g.beginPath();
      g.ellipse(p[0], p[1], 0.07 * UN, 0.045 * UN, 0, 0, B.TAU);
      g.fill();
    }
    face(g, c, PAL.top);
    // faint floor tiles
    g.strokeStyle = B.rgba(PAL.left, 0.5);
    g.lineWidth = 1;
    g.beginPath();
    for (let i = 1; i < GW; i++) B.poly(g, [pr(i, 0, 0), pr(i, GH, 0)]);
    for (let j = 1; j < GH; j++) B.poly(g, [pr(0, j, 0), pr(GW, j, 0)]);
    g.stroke();
    g.strokeStyle = "rgba(255,255,255,0.95)";
    g.lineWidth = Math.max(1, 0.05 * UN);
    g.beginPath();
    B.poly(g, [c[3], c[2], c[1]]);
    g.stroke();
  }

  // ------------------------------------------------------------------ layout and camera
  function layout(W, H) {
    const F = B.frame(W, H), P = F.portrait;
    SLAB = P ? 4 : 1.5;
    UN = P ? (W * 1.0) / ((GW + GH) * 0.866) : (H * 0.74) / ((GW + GH) * 0.5 + SLAB + 2);
    OX = W / 2 - (GW - GH) * 0.5 * UN * 0.866;
    OY = H / 2 - (GW + GH) * 0.25 * UN + (P ? 0.04 * H : 0.02 * H);
    return { F, P, chartAt: BEATS[4], sinkAt: BEATS[5] + 0.3 };
  }
  function camAt(t, L) {
    const P = L.P, sc = (x, y, z, zoom, dx = 0, dy = 0) => {
      const p = pr(x, y, z);
      return { x: p[0] + dx * UN, y: p[1] + dy * UN, z: zoom };
    };
    // the whole floating slab is always in view: portrait low in the frame (heading and tags in the band above it),
    // landscape a little right of centre (heading and tags in the free corners around it); between beats the camera
    // only slides a little along the tile
    const base = P ? sc(7, 5, 0, 0.96, 0, -4.83) : sc(7, 5, 0, 1.08, -1.62, -0.68), d = (k) => ({ ...base, x: base.x + k * UN });
    const keys = [[0, d(-0.25)], [BEATS[1] + 0.3, d(-0.25)], [BEATS[2] + 0.3, d(0)], [BEATS[3] + 0.3, d(0.25)], [BEATS[4] + 0.3, d(0)], [BEATS[5] + 0.3, d(-0.25)], [DUR, d(-0.25)]];
    for (let i = 1; i < keys.length; i++)
      if (t <= keys[i][0]) {
        const [t0, a] = keys[i - 1], [t1, b] = keys[i], k = B.ease.inOutSine(B.prog(t, t0, t1 - t0));
        return { x: B.lerp(a.x, b.x, k), y: B.lerp(a.y, b.y, k), z: B.lerp(a.z, b.z, k) };
      }
    return keys[keys.length - 1][1];
  }
  const camApply = (g, F, s = 1) => {
    g.setTransform(s, 0, 0, s, 0, 0);
    g.translate(F.W / 2, F.H / 2);
    g.scale(CAM.z, CAM.z);
    g.translate(-CAM.x, -CAM.y);
  };

  // ------------------------------------------------------------------ the frame
  function draw(ctx, W, H, t) {
    const L = layout(W, H), F = L.F, u = F.u, P = L.P;
    Fr = F;
    T = t;
    TS = (P ? 4.4 : 4.2) * u;
    CAM = camAt(t, L);
    const up = B.ease.outBack(B.prog(t, 0, 0.8), 1.3); // the slab rises into frame
    OY += (1 - up) * H * 0.7;
    ctx.fillStyle = PAL.back;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = B.radial(ctx, W / 2, H * 0.45, 0, Math.hypot(W, H) * 0.6, [[0, "rgba(255,255,255,0.7)"], [1, "rgba(255,255,255,0)"]]);
    ctx.fillRect(0, 0, W, H);
    const O = objects(t, L);
    ctx.save();
    camApply(ctx, F);
    slab(ctx, up);
    ctx.restore();
    // soft long shadows: painted at third resolution, then laid on the floor
    const sg = B.scratch("iso-shadow", Math.ceil(W / 3), Math.ceil(H / 3));
    camApply(sg, F, 1 / 3);
    sg.fillStyle = B.shade(PAL.shadow, -0.08);
    O.S.forEach((s) => shadow(sg, ...s));
    ctx.save();
    camApply(ctx, F);
    ctx.beginPath();
    B.poly(ctx, [pr(0, 0), pr(GW, 0), pr(GW, GH), pr(0, GH)], true);
    ctx.clip();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 0.6;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(sg.canvas, 0, 0, W, H);
    ctx.restore();
    // ground marks: flow arrows and pulse rings lie flat on the floor
    ctx.save();
    camApply(ctx, F);
    const dP = B.prog(t, 2.35, 0.9, "inOutSine") * (1 - B.prog(t, 4.1, 0.3));
    if (dP > 0) {
      groundArrow(ctx, [[3.0, 5.55], [11.4, 5.55], [11.4, 3.4]], dP);
      groundArrow(ctx, [[6.15, 5.4], [6.15, 6.0]], B.prog(t, 3.0, 0.3) * (1 - B.prog(t, 4.1, 0.3)), PAL.coral);
    }
    const pulse = (x, y, r, at, until) => {
      if (t < at || t > until) return;
      for (let k = 0; k < 2; k++) {
        const p = B.fract((t - at) / 1.1 + k * 0.5);
        ctx.strokeStyle = B.rgba(PAL.coral, (1 - p) * 0.8);
        ctx.lineWidth = 0.07 * UN;
        ctx.beginPath();
        floorRing(ctx, x, y, r * (0.6 + p * 0.9));
        ctx.stroke();
      }
    };
    pulse(12.95, 2.65, 1.0, 3.0, 4.2);
    pulse(9.5, 1.6, 1.8, 4.5, 6.2);
    [[2.0, 4.6, 6.6], [6.1, 4.6, 7.25], [12.0, 3.4, 7.9]].forEach(([x, y, at]) => pulse(x, y, 1.1, at, at + 1.0));
    pulse(9.1, 8.1, 1.2, 9.9, 10.8);
    O.J.forEach(([, f]) => f(ctx));
    // the billboard's face: the number counts up, set in the plane of the sign
    if (O.bb > 0.15) {
      // set in the plane of the sign (1 grid unit = UN), big enough to read in the widest shot
      const o = pr(7.2, 1.65, 5.3 * O.bb), num = t > 4.4, f = (str, y, size, color, a = 1) => B.text(ctx, str, 2.3 * UN, y * UN, { size: size * UN, minSize: size * UN, family: ROUND, weight: 900, color, alpha: a, maxW: 4.3 * UN });
      ctx.save();
      ctx.transform(0.866, 0.5, 0, 1, o[0], o[1]);
      ctx.scale(1, Math.min(1, O.bb)); // the lettering squashes with the face as the sign rises or sinks
      if (!num) f("RECYCLE", 2, 1, INK);
      else {
        f(B.counter(B.prog(t, 4.6, 1.0), 95, { suffix: "%" }), 1.2, 1.7, PAL.coral);
        f("LESS", 2.6, 1, INK, B.prog(t, 4.9, 0.3));
        f("ENERGY", 3.55, 1, INK, B.prog(t, 4.9, 0.3));
      }
      ctx.restore();
    }
    ctx.restore();

    // ---------------- labels, in screen space: a heading, and tags on stems in the free space around the slab
    const S = F.safe, tIn = (at) => B.pop(t, at, 0.4, 2);
    const out = (b) => 1 - B.prog(t, b - 0.25, 0.25);
    const head = (str, sub, at, until, o = {}) => {
      const a = B.prog(t, at, 0.35) * out(until);
      if (a <= 0) return;
      const x = P ? W / 2 : S.x, al = P ? "center" : "left", sz = (P ? o.size ?? 7 : 6) * u;
      // portrait: the text block sits centred in the band between the safe top and the scene, so no band is bare
      const r = B.text(ctx, str, x, S.y + (P ? o.y : 2) * u, { size: sz, minSize: sz, family: ROUND, weight: 900, color: INK, align: al, baseline: P ? "middle" : "top", maxW: P ? S.w : W * 0.4, lineH: 1.05, alpha: a });
      if (sub) B.text(ctx, sub, x, r.bottom + 3.4 * u, { size: TS, minSize: TS, family: SANS, weight: 500, color: B.mix(INK, PAL.back, 0.2), align: al, maxW: P ? S.w : W * 0.4, alpha: a });
    };
    // tags: [pin, words, portrait place, landscape place]; portrait rows are stacked so no stem crosses a tag below
    const tags = (items, at, gap, until, num) => {
      const o = out(until);
      items.forEach(([pin, text, qp, ql], i) => tag(ctx, pin, P || ql.keep ? text : text.replace("\n", " "), tIn(at + i * gap) * o, P ? qp : ql, { num: num ? i + 1 : 0 }));
    };
    const Y = (k) => k * H, X = (k) => k * W;
    head(P ? "How cans\nget sorted" : "How cans get sorted", "A small tour of a recycling plant", 0.6, BEATS[1], { size: 9, y: 22.3 });
    if (t > BEATS[1] && t < BEATS[2]) tags([[pr(4.4, 5.0, 0.7), "Belt", { y: Y(0.393), f: 0.75 }, { x: X(0.26), y: Y(0.28) }],
      [pr(6.1, 5.3, 2.6), "Magnet", { y: Y(0.323), f: 0.8 }, { x: X(0.33), y: Y(0.165) }],
      [pr(11.7, 4.45, 0.95), "Eddy current", { y: Y(0.253), f: 0.88 }, { x: X(0.84), y: Y(0.83) }],
      [pr(12.95, 2.65, O.coralH), "Aluminium bin", { y: Y(0.182), f: 0.73 }, { x: X(0.865), y: Y(0.35) }]], 2.2, 0.25, BEATS[2]);
    head(P ? "Recycling a can\ninstead of making\na new one saves:" : "Recycling a can instead of making a new one saves:", null, BEATS[2] + 0.2, BEATS[3], { y: 27, size: 7.5 });
    if (t > BEATS[3] && t < BEATS[4]) tags([[pr(2.9, 4.5, 0.62), "Mixed cans\nride the belt", { y: Y(0.395), f: 0.67 }, { x: X(0.235), y: Y(0.78) }],
      [pr(6.1, 3.6, 2.6), "A magnet lifts out steel", { y: Y(0.312), f: 0.645 }, { x: X(0.26), y: Y(0.24) }],
      [pr(12.95, 2.65, O.coralH), "Aluminium is\nflung aside", { y: Y(0.245), f: 0.86 }, { x: X(0.86), y: Y(0.3), keep: 1 }]], 6.55, 0.65, BEATS[4], true);
    head("Three steps to sorted", null, BEATS[3] + 0.2, BEATS[4], { y: 7 });
    if (t > BEATS[4] && t < BEATS[5] + 0.3) tags([[pr(9.1, 8.1, 6.05), "New from ore", { y: Y(0.335), f: 0.85 }, { x: X(0.26), y: Y(0.27) }],
      [pr(10.6, 8.1, 0.3), "Recycled: 1/20", { y: Y(0.4), f: 0.05 }, { x: X(0.83), y: Y(0.83) }]], 9.75, 0.25, BEATS[5] + 0.3);
    head("Energy per can", null, BEATS[4] + 0.2, BEATS[5] + 0.3, { y: 24 });
    head("Sorted, baled,\nmade new again", "Cans recycle again and again", BEATS[5] + 0.5, DUR + 1, { size: 9, y: 22.3 });
  }

  // ------------------------------------------------------------------ sound: wooden pops, machine hum and clicks, a chime for results
  SOUND.define("iso-pop", (v) => {
    // soft wooden block pop: a short hollow tone with a click on top
    v.tone({ type: "triangle", f: 520, f2: 330, glide: 0.05, a: 0.002, len: 0.09, peak: 0.32 });
    v.noise({ filter: "bandpass", f: 2400, q: 2, a: 0.0005, len: 0.015, peak: 0.12 });
  }, { verb: 0.18 });

  function score(k) {
    k.bed("hum", 0.6, DUR, { gain: 0.5, fade: 1 });
    k.bed("room", 0, DUR, { gain: 0.7 });
    k.at(0.0, "swell", { dur: 0.8, gain: 0.5 }).at(0.75, "thud", { gain: 0.35 });
    [0.35, 0.45, 0.55, 0.75, 0.85, 0.9, 1.0, 1.05, 1.1, 1.2, 1.3].forEach((at, i) => k.at(at + 0.12, "iso-pop", { pitch: (i % 5) * 2, gain: 0.55, pan: ((i % 3) - 1) * 0.3 }));
    k.repeat(1.6, PERIOD, 17, "click", { gain: 0.12, vary: 2 });
    k.at(2.2, "pop", { gain: 0.35 }).at(2.45, "pop", { gain: 0.35, pitch: 2 }).at(2.7, "pop", { gain: 0.35, pitch: 4 }).at(3.0, "pop", { gain: 0.35, pitch: 5 });
    k.at(2.35, "swish", { dur: 0.8, gain: 0.3 });
    k.at(4.4, "swish", { dur: 0.6, gain: 0.3 });
    k.repeat(4.6, 0.08, 12, "tick", { gain: 0.35, vary: 1 });
    k.at(5.6, "chime", { note: "E6", gain: 0.6 }).at(5.65, "bell", { note: "B5", gain: 0.3 });
    [6.55, 7.2, 7.85].forEach((at, i) => k.at(at, "pop", { gain: 0.45, pitch: i * 2 }).at(at, "marimba", { note: ["C5", "E5", "G5"][i], gain: 0.4 }));
    k.at(7.35, "knock", { gain: 0.3 }).at(8.0, "whoosh", { dur: 0.35, gain: 0.25 });
    for (let i = 0; i < 21; i++) k.at(BEATS[4] + 0.3 + i * 0.045 + 0.08, "iso-pop", { pitch: Math.min(i, 14), gain: 0.35 });
    k.at(9.75, "chime", { note: "G5", gain: 0.45 }).at(10.0, "chime", { note: "C6", gain: 0.55 });
    k.at(BEATS[5] + 0.3, "fall", { dur: 0.45, gain: 0.25 });
    k.at(11.3, "chord", { notes: ["C5", "E5", "G5", "C6"], strum: 0.05, gain: 0.6 }).at(11.35, "chime", { note: "E6", gain: 0.4 });
  }

  Player.register({
    id: "isometric",
    name: "Isometric Diorama",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=DM+Sans:wght@500;700&display=swap",
      faces: ['900 20px "Nunito"', '800 20px "Nunito"', '500 20px "DM Sans"', '700 20px "DM Sans"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three steps", "Chart", "Close"],
    stills: [1.8, 3.8, 6.0, 8.4, 10.5, 12.3],
    draw,
    score,
  });
})();
