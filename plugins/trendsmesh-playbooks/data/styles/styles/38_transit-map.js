/* 38 Transit Map - reference animation.
 * Topic (setting, replace it): "Where does your recycling go?" - the sorting hub and its three material lines.
 * Rendering (keep it): a metro network diagram on a pale warm ground: a light blue river band and soft park patches
 * as the only background shapes; fat routes of one even width in strong colours, running only horizontal, vertical
 * or at 45 degrees, each bend one clean angle change with a round corner; stations as ticks in the route colour,
 * termini as flat caps, interchanges as white circles with a thick black ring; clean horizontal sans labels beside
 * the stops; a thin white casing wherever lines cross; faint darker zone stripes; a boxed legend and a title block;
 * a departure board with amber dot-matrix figures for the key number. Finish: crisp and flat, a ~3 % print grain.
 * The map is laid out once in landscape grid units; portrait uses the same network transposed (x <-> y), so
 * 45/90-degree geometry survives, and everything is drawn in screen space at fixed sizes (labels stay legible).
 * Motion: routes draw out from their start terminus one after another, stations ticking on as the line passes;
 * interchanges pop with a small bounce; rounded trains glide at an even pace once lines are built; the camera pans
 * and zooms smoothly along the route to the next stop (that is the scene change); the board flips its digits.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { ground: "#f4f2ec", river: "#bcd8ea", park: "#cfe5c4", red: "#d93a35", blue: "#1f5fa8", green: "#2d9a53", amber: "#f1a21b", ink: "#1a1a1a", white: "#ffffff", board: "#1d1c1a" };
  const SANS = "Inter", COND = "Roboto Condensed";
  const DUR = 12.5;
  const BEATS = [0, 2.0, 4.4, 6.6, 8.8, 10.6];
  let U = 1, T = 0, F = null, ctx = null, CAM = null;
  const PL = (portrait, landscape) => (F.portrait ? portrait : landscape);

  // ------------------------------------------------------------------ the network (landscape grid units; transposed for portrait)
  // Routes: grid waypoints (only 0/45/90-degree legs), reveal window [t0, t1], stations { at: [x, y], name, side }.
  // side is where the label sits in landscape ("up" | "down" | "left" | "right"); portrait maps up<->left, down<->right
  // unless ps / pl give its portrait side and text. Once the whole network is in view only `keep` labels stay
  // (keep 1: until the close, keep 2: to the end), so the stops never crowd.
  const ROUTES = [
    { id: "red", label: "Collection", col: PAL.red, pts: [[1, 2], [5, 2], [7, 4]], t: [0.3, 1.6],
      st: [{ at: [1, 2], label: "Your bin", side: "up", end: true, keep: 2 }, { at: [3, 2], label: "Kerbside", side: "up" }, { at: [5, 2], label: "Truck", side: "up" }] },
    { id: "blue", label: "Paper", col: PAL.blue, pts: [[7, 4], [10, 1], [14, 1]], t: [6.7, 7.4],
      st: [{ at: [11.5, 1], label: "Pulper", side: "up" }, { at: [14, 1], label: "New boxes", pl: "New\nboxes", side: "right", ps: "down", end: true, keep: true }] },
    { id: "green", label: "Glass", col: PAL.green, pts: [[7, 4], [14, 4]], t: [7.0, 7.7],
      st: [{ at: [11.5, 4], label: "Furnace", side: "up" }, { at: [14, 4], label: "New jars", pl: "New\njars", side: "right", ps: "down", end: true, keep: true }] },
    { id: "amber", label: "Cans", col: PAL.amber, pts: [[7, 4], [10, 7], [14, 7]], t: [7.3, 8.0],
      st: [{ at: [11.5, 7], label: "Smelter", side: "up" }, { at: [14, 7], label: "New cans", pl: "New\ncans", side: "down", ps: "down", keep: true }] },
    { id: "loop", label: "Cans", col: PAL.amber, pts: [[14, 7], [15.5, 7], [15.5, 9], [3, 9], [1, 7], [1, 2]], t: [10.6, 11.7],
      st: [{ at: [8, 9], label: "Shop shelf", pl: "Shop\nshelf", side: "down", keep: 2 }] },
  ];
  const HUB = [7, 4], BIN = [1, 2];
  // the river winds above the map (clear of every line and zone) and runs off both edges of any view
  const RIVER = [[-40, -2.1], [2, -2.1], [4, -2.6], [8, -2.2], [11, -2.7], [15, -2.3], [50, -2.3]];
  const PARKS = [[2, 3.2, 2.6, 1.9], [16, 2.2, 1.3, 2.6], [3.2, 10.3, 3, 0.9], [10, 1.7, 2.6, 1.2], [-2.6, 6.6, 3, 1.4], [3, 7.2, 3, 1.1]];
  const ZONES = [[6, 8.8, "1 · SORT"], [8.8, 12.6, "2 · PULP & MELT"], [12.6, 15, "3 · MAKE"]];
  const SIDE_T = { up: "left", left: "up", down: "right", right: "down" };

  /** Grid point (landscape units) for this aspect: portrait transposes x and y. */
  const gp = (p) => (F.portrait ? [p[1], p[0]] : [p[0], p[1]]);
  const side = (s) => (F.portrait ? SIDE_T[s] : s);
  /** Grid -> screen through the camera. */
  const sc = (p) => [(p[0] - CAM.x) * CAM.s + F.W / 2, (p[1] - CAM.y) * CAM.s + F.H / 2];

  /**
   * Round each corner of a 0/45/90 polyline with a circular fillet of radius r (grid units): the transit-map bend,
   * one clean angle change with a round corner.
   */
  function roundCorners(pts, r) {
    const out = [pts[0]];
    for (let i = 1; i < pts.length - 1; i++) {
      const [a, b, c] = [pts[i - 1], pts[i], pts[i + 1]];
      const d1 = [b[0] - a[0], b[1] - a[1]], d2 = [c[0] - b[0], c[1] - b[1]];
      const l1 = Math.hypot(...d1), l2 = Math.hypot(...d2), u1 = [d1[0] / l1, d1[1] / l1], u2 = [d2[0] / l2, d2[1] / l2];
      const turn = Math.acos(B.clamp(u1[0] * u2[0] + u1[1] * u2[1], -1, 1)), cut = Math.min(r * Math.tan(turn / 2), l1 / 2, l2 / 2);
      const p0 = [b[0] - u1[0] * cut, b[1] - u1[1] * cut], p1 = [b[0] + u2[0] * cut, b[1] + u2[1] * cut];
      for (let k = 0; k <= 8; k++) { // quadratic through the corner approximates the arc closely for 45/90 turns
        const q = k / 8;
        out.push([(1 - q) * (1 - q) * p0[0] + 2 * q * (1 - q) * b[0] + q * q * p1[0], (1 - q) * (1 - q) * p0[1] + 2 * q * (1 - q) * b[1] + q * q * p1[1]]);
      }
    }
    out.push(pts[pts.length - 1]);
    return B.densify(out, 0.1);
  }
  /** Fraction along a densified path nearest to a grid point (where a station sits on its route). */
  function fracAt(path, p) {
    let best = 0, bd = Infinity, s = 0, at = 0;
    for (let i = 0; i < path.length; i++) {
      if (i) s += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
      const d = Math.hypot(path[i][0] - p[0], path[i][1] - p[1]);
      if (d < bd) (bd = d), (at = s);
    }
    best = at / B.pathLength(path);
    return best;
  }

  // ------------------------------------------------------------------ camera: fit a grid box into a part of the safe area
  // keys: [time, grid box (landscape units) [x0, y0, x1, y1], target (fractions of the safe area) [fx0, fy0, fx1, fy1]]
  const CAMKEYS = [
    [0, [0, 0.6, 8, 5], [0.42, 0.5, 1, 1.5], [0, 0.42, 1, 1], [-0.4, 0.6, 9.4, 7.6]],
    [2.0, [0, 0.6, 8, 5], [0.42, 0.5, 1, 1.5], [0, 0.42, 1, 1], [-0.4, 0.6, 9.4, 7.6]],
    [3.0, [0.5, 0.2, 9.5, 6], [0, 0.08, 1, 1], [0, 0.08, 1, 1]],
    [6.6, [0.5, 0.2, 9.5, 6], [0, 0.08, 1, 1], [0, 0.08, 1, 1]],
    [7.3, [5.4, -1.6, 15.4, 7.9], [0, 0, 1, 1], [0, 0, 1, 1]],
    [8.8, [5.4, -1.6, 15.4, 7.9], [0, 0, 1, 1], [0, 0, 1, 1]],
    [9.4, [-0.5, -1.6, 17.5, 9.6], [0, 0, 0.72, 1], [0, 0, 1, 0.84]],
    [10.6, [-0.5, -1.6, 17.5, 9.6], [0, 0, 0.72, 1], [0, 0, 1, 0.84]],
    [11.2, [-0.5, -1.6, 17.5, 9.6], [0, 0.26, 1, 1], [0, 0.27, 1, 1]],
  ];
  function camera(t) {
    let k = 0;
    while (k < CAMKEYS.length - 1 && t >= CAMKEYS[k + 1][0]) k++;
    const a = CAMKEYS[k], b = CAMKEYS[Math.min(k + 1, CAMKEYS.length - 1)];
    const e = a === b ? 0 : B.ease.inOutCubic(B.clamp((t - a[0]) / (b[0] - a[0])));
    const A = (k) => (!F.portrait && k[4]) || k[1], box = A(a).map((v, i) => B.lerp(v, A(b)[i], e)), // optional 16:9 box
      tg = (F.portrait ? a[3] : a[2]).map((v, i) => B.lerp(v, (F.portrait ? b[3] : b[2])[i], e));
    const [x0, y0] = gp([box[0], box[1]]), [x1, y1] = gp([box[2], box[3]]), S = F.safe;
    const tx0 = S.x + tg[0] * S.w, ty0 = S.y + tg[1] * S.h, tx1 = S.x + tg[2] * S.w, ty1 = S.y + tg[3] * S.h;
    const s = Math.min((tx1 - tx0) / (x1 - x0), (ty1 - ty0) / (y1 - y0));
    // place the box centre on the target centre: solve for the grid point at the frame centre
    return { s, x: (x0 + x1) / 2 - ((tx0 + tx1) / 2 - F.W / 2) / s, y: (y0 + y1) / 2 - ((ty0 + ty1) / 2 - F.H / 2) / s };
  }

  // ------------------------------------------------------------------ map drawing (reuse these)
  const LW = () => PL(1.5, 1.45) * U; // one even route width everywhere
  function background() {
    ctx.fillStyle = PAL.ground;
    ctx.fillRect(0, 0, F.W, F.H);
    // zones: faint darker stripes behind the lines, with their step names
    const zp = B.prog(T, 6.6, 0.5);
    if (zp > 0)
      ZONES.forEach(([a, b, name], i) => {
        const p0 = sc(gp([a, -1.5])), p1 = sc(gp([b, 7.8])), x = Math.min(p0[0], p1[0]), y = Math.min(p0[1], p1[1]);
        ctx.fillStyle = B.rgba("#d9d3c4", (i % 2 ? 0.28 : 0.5) * zp);
        ctx.fillRect(x, y, Math.abs(p1[0] - p0[0]), Math.abs(p1[1] - p0[1]));
        B.text(ctx, name.replace(" & ", "\n& "), x + 1.2 * U, y + 1.2 * U, { lineH: 1.1, size: PL(4.2, 4) * U, family: COND, weight: 700, color: B.rgba("#6c6457", zp * (1 - B.span(T, 8.8, 9.1))), align: "left", baseline: "top", letterSpacing: 0.06 });
      });
    // the river: a wide, smooth, winding pale band (the one thing on the map that may curve freely)
    ctx.beginPath();
    B.smoothPath(ctx, RIVER.map(gp).map(sc));
    ctx.lineWidth = 0.6 * CAM.s;
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.strokeStyle = PAL.river;
    ctx.stroke();
    PARKS.forEach(([x, y, w, h]) => {
      const a = sc(gp([x, y])), b = sc(gp([x + w, y + h]));
      ctx.fillStyle = PAL.park;
      ctx.beginPath();
      B.roundRect(ctx, Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]), 0.4 * CAM.s);
      ctx.fill();
    });
  }
  /** One route at reveal p: white casing first (so it outlines any line it crosses), then the colour. */
  function route(r, p) {
    if (p <= 0) return;
    const path = roundCorners(r.pts.map(gp), 0.7), shown = B.trim(path, 0, p).map(sc);
    B.strokeReveal(ctx, shown, 1, { width: LW() + 0.7 * U, color: PAL.white, cap: "butt" });
    B.strokeReveal(ctx, shown, 1, { width: LW(), color: r.col, cap: "butt" });
    r.path = path;
  }
  /** A station on route r: a tick on the label side (or a flat cap for a terminus), the name beside it. */
  function station(r, st, p) {
    const f = fracAt(r.path || roundCorners(r.pts.map(gp), 0.7), gp(st.at));
    if (p < f - 0.001) return 0;
    const [x, y] = sc(gp(st.at)), sd = F.portrait && st.ps ? st.ps : side(st.side), lw = LW();
    const dir = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[sd];
    const k = B.clamp((T - (r.t[0] + f * (r.t[1] - r.t[0]))) / 0.2);
    ctx.fillStyle = r.col;
    if (st.end) { // terminus: a flat bar across the line end
      const a = B.pointAt(B.trim(r.path, 0, Math.max(0.001, f)).map(sc), 1)[2] + Math.PI / 2;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(a);
      ctx.fillRect(-lw * 1.15, -lw * 0.5, lw * 2.3, lw);
      ctx.restore();
    } else ctx.fillRect(x + (dir[0] ? dir[0] * lw * 0.4 : -lw * 0.3), y + (dir[1] ? dir[1] * lw * 0.4 : -lw * 0.3), dir[0] ? dir[0] * lw * 0.75 : lw * 0.6, dir[1] ? dir[1] * lw * 0.75 : lw * 0.6);
    label((F.portrait && st.pl) || st.label, x + dir[0] * lw * 1.6, y + dir[1] * lw * 1.6, sd, k * (st.keep === 2 ? 1 : 1 - B.span(T, st.keep ? 10.6 : 8.8, st.keep ? 10.9 : 9.1)));
    return k;
  }
  /** A station name; it fades out while any of it would sit outside the frame's safe area (a camera move passing). */
  function label(text, x, y, sd, a, vb) {
    if (a <= 0) return;
    const align = sd === "left" ? "right" : sd === "right" ? "left" : "center", base = vb || (sd === "up" ? "bottom" : sd === "down" ? "top" : "middle");
    const o = { size: PL(4.2, 4) * U, family: SANS, weight: 600, color: PAL.ink, align, baseline: base, lineH: 1.1 };
    const m = B.measureText(ctx, text, o), x0 = align === "left" ? x : align === "right" ? x - m.width : x - m.width / 2, y0 = base === "bottom" ? y - m.height : base === "top" ? y : y - m.height / 2;
    const W = F.W, H = F.H, over = Math.max(0.035 * W - x0, x0 + m.width - 0.965 * W, PL(0.145, 0.055) * H - y0, y0 + m.height - PL(0.795, 0.945) * H);
    B.text(ctx, text, x, y, { ...o, alpha: a * B.clamp(1 - over / (1.5 * U)) });
  }
  /** Interchange: a larger white circle with a thick black ring, popping in with a small bounce. */
  function interchange(p, at, name, sd) {
    const [x, y] = sc(gp(p)), s = B.pop(T, at, 0.4, 2.2), r = LW() * 1.05;
    if (s <= 0) return;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(s, s);
    ctx.beginPath();
    B.circle(ctx, 0, 0, r);
    ctx.fillStyle = PAL.white;
    ctx.fill();
    ctx.lineWidth = r * 0.42;
    ctx.strokeStyle = PAL.ink;
    ctx.stroke();
    ctx.restore();
    if (name) { // sd in landscape terms, like station sides; "dl" / "ur" = below-left / above-right, clear of every line
      const s2 = sd === "dl" || sd === "ur" ? sd : side(sd), a = B.clamp((T - at) / 0.3);
      if (s2 === "dl") label(name, x - r * 1.9, y + r * 1.2, "left", a, "top");
      else if (s2 === "ur") label(name, x + r * 1.4, y - r * 0.9, "right", a, "bottom");
      else label(name, x + (s2 === "left" ? -1 : s2 === "right" ? 1 : 0) * r * 1.8, y + (s2 === "up" ? -1 : s2 === "down" ? 1 : 0) * r * 1.8, s2, a);
    }
  }
  /** A small rounded train gliding along a route at an even pace (phase in 0..1 of the route). */
  function train(r, ph) {
    const pts = r.path.map(sc), q = B.pointAt(pts, ph), lw = LW();
    ctx.save();
    ctx.translate(q[0], q[1]);
    ctx.rotate(q[2]);
    ctx.beginPath();
    B.capsule(ctx, -lw * 1.3, -lw * 0.75, lw * 2.6, lw * 1.5);
    ctx.fillStyle = PAL.white;
    ctx.fill();
    ctx.lineWidth = lw * 0.3;
    ctx.strokeStyle = r.col;
    ctx.stroke();
    ctx.fillStyle = r.col;
    for (let i = -1; i <= 1; i++) ctx.fillRect(i * lw * 0.75 - lw * 0.22, -lw * 0.25, lw * 0.44, lw * 0.5);
    ctx.restore();
  }
  /** Note flag: a small rounded box tied to a point by a short stem. */
  function flag(px, py, dx, dy, lines, a) {
    if (a <= 0) return;
    const size = PL(4.2, 4) * U, pad = size * 0.6;
    ctx.save();
    ctx.globalAlpha = a;
    ctx.font = B.font(size, COND, 500);
    const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 2 * pad, h = lines.length * size * 1.25 + 2 * pad;
    const bx = px + dx - w / 2, by = py + dy - (dy < 0 ? h : 0);
    ctx.strokeStyle = PAL.ink;
    ctx.lineWidth = 0.3 * U;
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.lineTo(px + dx, py + dy);
    ctx.stroke();
    ctx.fillStyle = PAL.white;
    ctx.beginPath();
    B.roundRect(ctx, bx, by, w, h, size * 0.5);
    ctx.fill();
    ctx.stroke();
    lines.forEach((l, i) => B.text(ctx, l, bx + pad, by + pad + size * 1.25 * (i + 0.5), { size, family: COND, weight: 500, color: PAL.ink, align: "left" }));
    ctx.restore();
  }

  // ------------------------------------------------------------------ the departure board: dark strip, amber dot-matrix digits that flip
  const DOTS = {
    0: "01110100011001110101110011000101110", 1: "00100011000010000100001000010001110", 2: "01110100010000100010001000100011111",
    3: "11111000100010000010000011000101110", 4: "00010001100101010010111110001000010", 5: "11111100001111000001000011000101110",
    6: "00110010001000011110100011000101110", 7: "11111000010001000100010000100001000", 8: "01110100011000101110100011000101110",
    9: "01110100011000101111000010001001100", "%": "11000110010001000100010001001100011", " ": "00000000000000000000000000000000000",
  };
  /** One dot-matrix character cell (5 x 7 LEDs): lit dots in amber with a faint unlit grid behind. */
  function dotChar(ch, x, y, d, flipY = 1) {
    const bits = DOTS[ch] || DOTS[" "];
    for (let r = 0; r < 7; r++)
      for (let c = 0; c < 5; c++) {
        const on = bits[r * 5 + c] === "1";
        const rr = d * (on ? 0.44 : 0.3);
        ctx.fillStyle = on ? PAL.amber : "#2c2925";
        ctx.beginPath();
        ctx.ellipse(x + c * d, y + (r - 3) * d * flipY, rr, rr * Math.max(0.15, Math.abs(flipY)), 0, 0, B.TAU);
        ctx.fill();
      }
  }
  /** Split-flap style text: each cell rattles through digits, then flips onto its final character at land[i]. */
  function flipText(str, x, y, d, land) {
    [...str].forEach((ch, i) => {
      const cx = x + i * d * 6.4, dt = T - land[i];
      if (dt < 0) {
        const tick = Math.floor(T / 0.07), f = B.fract(T / 0.07);
        dotChar(String(B.hash(i, tick) % 10), cx, y, d, Math.cos(f * Math.PI));
      } else dotChar(ch, cx, y, d, Math.min(1, Math.cos(B.clamp(1 - dt / 0.08) * Math.PI / 2)));
    });
  }
  function board(a) {
    if (a <= 0) return;
    const S = F.safe, w = PL(88, 78) * U, h = PL(80, 50) * U, x = F.W / 2 - w / 2, y = S.cy - h / 2 - PL(7, -2) * U, lt = T - BEATS[2];
    ctx.save();
    ctx.globalAlpha = a;
    ctx.fillStyle = PAL.ground; // the map gives way to the board
    ctx.fillRect(0, 0, F.W, F.H);
    ctx.translate(0, (1 - B.ease.outCubic(a)) * 4 * U);
    ctx.fillStyle = PAL.board;
    ctx.beginPath();
    B.roundRect(ctx, x, y, w, h, 1.6 * U);
    ctx.fill();
    ctx.fillStyle = "#2a2825";
    [0.16, 0.64].concat(F.portrait ? [] : [0.82]).forEach((k) => ctx.fillRect(x, y + h * k, w, 0.25 * U));
    const hs = PL(4.2, 4) * U;
    B.text(ctx, "RECYCLED ALUMINIUM", x + 2.4 * U, y + h * 0.08, { size: hs, family: COND, weight: 700, color: PAL.amber, align: "left", letterSpacing: 0.08 });
    B.text(ctx, "PLATFORM 3", x + w - 2.4 * U, y + h * 0.08, { size: hs, family: COND, weight: 700, color: B.rgba(PAL.amber, 0.6), align: "right", letterSpacing: 0.08 });
    const d = PL(4.6, 2.4) * U, txt = "95%", tw = (txt.length * 6.4 - 1.4) * d;
    flipText(txt, F.W / 2 - tw / 2 + d * 0.5, y + h * 0.4, d, [BEATS[2] + 0.75, BEATS[2] + 0.95, BEATS[2] + 1.15]);
    if (!F.portrait) B.text(ctx, "CANS LINE: SORT · MELT · MAKE", F.W / 2, y + h * 0.91, { size: 4 * U, family: COND, weight: 700, color: B.rgba(PAL.amber, 0.7), letterSpacing: 0.08, maxW: w * 0.92 });
    else { // 9:16: the cans line as a little route under the board, its three stops ticking on
      const ly = y + h + 16 * U, x0 = x + 6 * U, x1 = x + w - 6 * U, lw = LW();
      B.strokeReveal(ctx, [[x0, ly], [x1, ly]], B.prog(T, BEATS[2] + 0.3, 0.6), { width: lw, color: PAL.amber, cap: "butt" });
      ["SORT", "MELT", "MAKE"].forEach((n, i) => {
        const sx = B.lerp(x0, x1, i / 2), k = B.prog(T, BEATS[2] + 0.35 + i * 0.25, 0.2);
        ctx.fillStyle = PAL.amber;
        if (i % 2) ctx.fillRect(sx - lw * 0.3, ly - lw * 1.2, lw * 0.6, lw * 0.75);
        else ctx.fillRect(sx - lw * 0.5, ly - lw * 1.15, lw, lw * 2.3); // flat caps at the ends
        B.text(ctx, n, sx, ly + lw * 1.6, { size: 4.4 * U, family: SANS, weight: 600, color: PAL.ink, baseline: "top", alpha: k * (1 - B.span(T, 6.35, 6.65)) });
      });
      B.text(ctx, "The cans line", x0, ly - lw * 1.6, { size: 4.4 * U, family: COND, weight: 700, color: "#555048", align: "left", baseline: "bottom", alpha: B.prog(T, BEATS[2] + 0.3, 0.3) * (1 - B.span(T, 6.35, 6.65)) });
    }
    B.text(ctx, "LESS ENERGY THAN MAKING NEW", F.W / 2, y + h * PL(0.82, 0.73), { size: PL(5, 4.4) * U, maxLines: 2, family: COND, weight: 700, color: PAL.amber, letterSpacing: 0.08, alpha: B.clamp((lt - 1.3) / 0.3), maxW: w * 0.92 });
    ctx.restore();
  }
  /** Boxed legend (route colours with short names) and the title block with a small route key. */
  function legend(a) {
    if (a <= 0) return;
    // 16:9: a boxed column in the corner; 9:16: a two-by-two box along the bottom, under the map
    const S = F.safe, rows = ROUTES.slice(0, 4), fs = 4.2 * U, rh = fs * 1.7, cols = PL(2, 1), w = PL(S.w, 42 * U), head = PL(0, fs * 2.6);
    const h = (rows.length / cols) * rh + head + PL(fs * 0.6, 0), x = S.r - w, y = S.b - h;
    ctx.save();
    ctx.globalAlpha = a;
    ctx.fillStyle = PAL.white;
    ctx.strokeStyle = PAL.ink;
    ctx.lineWidth = 0.25 * U;
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
    if (head) B.text(ctx, "LINES", x + fs, y + fs * 1.1, { size: fs, family: COND, weight: 700, color: PAL.ink, align: "left", letterSpacing: 0.12 });
    rows.forEach((r, i) => {
      const rx = x + (i % cols) * (w / cols), ry = y + head + PL(fs * 0.3, -fs * 0.2) + Math.floor(i / cols) * rh + rh / 2;
      ctx.fillStyle = r.col;
      ctx.fillRect(rx + fs, ry - LW() * 0.35, fs * 2.4, LW() * 0.7);
      B.text(ctx, r.label, rx + fs * 4, ry, { size: fs, family: SANS, weight: 600, color: PAL.ink, align: "left" });
    });
    ctx.restore();
  }
  function titleBlock(lines, sub, a, o = {}) {
    if (a <= 0) return;
    const S = F.safe, x = S.x + 2.4 * U, y = (o.y ?? S.y) + 2.4 * U, ts = (o.size ?? PL(7.2, 5.6)) * U, mw = o.maxW ?? PL(S.w, S.w * 0.42);
    ctx.save();
    ctx.globalAlpha = a;
    const lo = { size: ts, family: SANS, weight: 800, align: "left", baseline: "top", maxW: mw, letterSpacing: -0.02 }, so = { size: PL(4.2, 4) * U, family: COND, weight: 500, align: "left", baseline: "top", maxW: mw };
    const ms = lines.map((l) => B.measureText(ctx, l, lo)).concat([B.measureText(ctx, sub, so)]), pad = 2.4 * U;
    const bw = Math.max(...ms.map((m) => m.width)), bh = ms.reduce((s, m) => s + m.height, 0) + ts * 0.35 + ts * 0.4 + LW() * 0.75;
    ctx.fillStyle = PAL.white;
    ctx.strokeStyle = PAL.ink;
    ctx.lineWidth = 0.25 * U;
    ctx.fillRect(x - pad, y - pad, bw + 2 * pad, bh + 2 * pad);
    ctx.strokeRect(x - pad, y - pad, bw + 2 * pad, bh + 2 * pad);
    let yy = y;
    lines.forEach((l) => {
      const m = B.text(ctx, l, x, yy, { size: ts, family: SANS, weight: 800, color: PAL.ink, align: "left", baseline: "top", maxW: mw, letterSpacing: -0.02 });
      yy = m.bottom;
    });
    const m = B.text(ctx, sub, x, yy + ts * 0.35, { size: PL(4.2, 4) * U, family: COND, weight: 500, color: "#555048", align: "left", baseline: "top", maxW: mw });
    ROUTES.slice(0, 4).forEach((r, i) => { // the small route key: colour chips in a row
      ctx.fillStyle = r.col;
      ctx.fillRect(x + i * ts * 0.9, m.bottom + ts * 0.4, ts * 0.75, LW() * 0.75);
    });
    ctx.restore();
  }

  // ------------------------------------------------------------------ the frame
  function draw(c, W, H, t) {
    ctx = c;
    F = B.frame(W, H);
    U = F.u;
    T = t;
    CAM = camera(t);
    background();
    // routes in drawing order, each revealed at an even pace between its times
    ROUTES.forEach((r) => (r.p = B.clamp((t - r.t[0]) / (r.t[1] - r.t[0]))));
    // the network still to come shows from the start as pale dashed "planned" lines, so every view is a full map
    ROUTES.forEach((r, i) => {
      r.path = roundCorners(r.pts.map(gp), 0.7);
      if (i < 4 && r.p < 1) B.strokeReveal(ctx, r.path.map(sc), 1, { width: LW() * 0.7, color: B.mix(r.col, PAL.ground, 0.62), cap: "butt", dash: [LW() * 1.4, LW() * 0.9] });
    });
    ROUTES.forEach((r) => route(r, r.p));
    // a direction arrow beside the collection line, then stations, interchanges, trains
    const red = ROUTES[0];
    if (t > 2.4 && t < 4.6) {
      const a0 = sc(gp([2.2, 2])), a1 = sc(gp([4.3, 2])), off = PL([1, 0], [0, 1]).map((v) => v * LW() * 2.2);
      const ap = B.prog(t, 2.4, 0.5, "inOutCubic"), fade = 1 - B.span(t, 4.2, 4.5);
      B.arrow(ctx, [[a0[0] + off[0], a0[1] + off[1]], [a1[0] + off[0], a1[1] + off[1]]], { p: ap, width: 0.35 * U, head: 1.6 * U, color: PAL.ink, alpha: fade });
      B.text(ctx, "flow", (a0[0] + a1[0]) / 2 + off[0] * 1.6, (a0[1] + a1[1]) / 2 + off[1] * 1.6, { size: PL(4.2, 4) * U, family: COND, weight: 500, color: "#555048", alpha: Math.min(ap, fade), align: PL("left", "center") });
    }
    if (t > 8.75) ROUTES.slice(0, 4).forEach((r, i) => train(r, B.fract((t - 8.75) / 2.6 + i * 0.27) * 0.92 + 0.02));
    ROUTES.forEach((r) => r.st.forEach((st) => station(r, st, r.p)));
    interchange(HUB, 1.65, PL("Sorting\nhub", "Sorting hub"), PL("ur", "dl"));
    interchange(BIN, 11.75, null);
    const hub = sc(gp(HUB));
    flag(hub[0], hub[1], PL(-14, 9) * U, PL(8, 9) * U, ["Everything meets", "at the sorting hub"], B.prog(t, 2.6, 0.3) * (1 - B.span(t, 4.3, 4.5)));
    // overlays in screen space
    board(B.span(t, 4.45, 4.8) * (1 - B.span(t, 6.35, 6.65)));
    legend(B.span(t, 9.0, 9.3) * (1 - B.span(t, 10.6, 10.9)));
    titleBlock(["The", "recycling", "line"], "Where your bin goes after the truck", B.span(t, 0.15, 0.5) * (1 - B.span(t, 1.8, 2.1)), { y: PL(F.safe.y, H * 0.3), size: PL(9, 8) });
    titleBlock(["Sorted, it goes", "round again"], "A can can be back on the shelf in about 60 days", B.span(t, 11.0, 11.4), { maxW: F.safe.w, size: PL(6.4, 5.6) });
    B.grain(ctx, W, H, { amount: 0.03, t, fps: 12, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: platform chimes per station, interchange dings, board clatter, trains passing
  SOUND.define("transit-chime", (v, o) => {
    // soft platform chime: a pure tone and its octave, quick attack, gentle ring
    const f = v.hz(o.note || "E5");
    v.tone({ f, a: 0.004, len: 0.7, peak: 0.16 });
    v.tone({ f: f * 2, a: 0.002, len: 0.25, peak: 0.04 });
  }, { verb: 0.35 });
  SOUND.define("transit-flap", (v, o) => {
    // split-flap clatter: rapid dry plastic clicks
    const n = Math.round((o.dur ?? 0.5) / 0.03);
    for (let i = 0; i < n; i++) v.noise({ at: i * 0.03 + v.rng() * 0.01, filter: "bandpass", f: 2600 + v.rng() * 1200, q: 2.5, a: 0.0005, len: 0.012, peak: 0.22 });
  }, { verb: 0.08 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.6 });
    k.bed("pad", 0, DUR, { notes: ["D3", "A3", "D4", "F#4"], gain: 0.3, bright: 800 });
    k.at(0.15, "swish", { dur: 0.5, gain: 0.4 });
    // the collection line: a chime as it passes each station, the two-tone ding at the hub
    [[0.3, "E5"], [0.69, "G5"], [1.08, "A5"]].forEach(([at, n]) => k.at(at, "transit-chime", { note: n }));
    k.at(2.0, "whoosh", { dur: 0.9, gain: 0.35 });
    k.at(1.65, "ding", { note: "E5" }).at(1.9, "ding", { note: "C5" });
    k.at(2.6, "pop", { gain: 0.4 });
    // the board
    k.at(4.45, "swish", { dur: 0.4, gain: 0.5 }).at(4.5, "transit-flap", { dur: 0.7 }).at(5.25, "transit-flap", { dur: 0.35, gain: 0.8 });
    [5.15, 5.35, 5.55].forEach((at) => k.at(at, "click", { gain: 0.7 }));
    k.at(5.7, "transit-chime", { note: "A5" });
    // the branches: one chime per station on each line as it draws
    k.at(6.6, "whoosh", { dur: 0.8, gain: 0.4 });
    [["blue", 6.7, ["B4", "E5"]], ["green", 7.0, ["C#5", "F#5"]], ["amber", 7.3, ["D5", "A5"]]].forEach(([id, t0, ns]) => {
      k.at(t0 + 0.42, "transit-chime", { note: ns[0], gain: 0.8 }).at(t0 + 0.7, "transit-chime", { note: ns[1], gain: 0.8 });
    });
    // trains: a hum and soft passes
    k.bed("hum", 8.75, 10.7, { gain: 0.4, fade: 0.4 });
    [8.9, 9.6, 10.2].forEach((at, i) => k.at(at, "whoosh", { dur: 0.9, gain: 0.35, pan: i % 2 ? 0.4 : -0.4 }));
    // the loop closes at your bin: an announcement ding-dong
    k.at(10.6, "swish", { dur: 0.6, gain: 0.4 }).at(11.2, "transit-chime", { note: "D5" });
    k.at(11.75, "ding", { note: "A5" }).at(12.0, "ding", { note: "F#5" });
  }

  Player.register({
    id: "transit-map",
    name: "Transit Map",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Inter:wght@600;800&family=Roboto+Condensed:wght@500;700&display=swap",
      faces: ['800 20px "Inter"', '600 20px "Inter"', '700 20px "Roboto Condensed"', '500 20px "Roboto Condensed"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three lines", "Trains", "Close"],
    stills: [1.5, 4.0, 6.0, 8.6, 10.0, 12.3],
    draw,
    score,
  });
})();
