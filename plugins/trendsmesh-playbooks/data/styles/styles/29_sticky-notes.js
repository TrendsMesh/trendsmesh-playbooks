/* 29 Sticky Notes - reference animation.
 * Topic (setting, replace it): "How do bees make honey?" - nectar in, water out.
 * Rendering (keep it): a warm cork board (speckle, pinholes, a wooden frame at the edges) covered in pastel paper
 * notes and taped index cards, each slightly tilted with a darker glued strip, a curled lower corner and a soft shadow
 * down and right; thick felt-tip lettering with uneven baselines; round push-pins with a highlight and a cast shadow;
 * red string pulled taut from pin to pin with a marker arrow beside it; red marker circles, stars and underlines.
 * Motion: notes slap on from above, larger, and settle with a bounce and a tilt; string unspools and twangs tight;
 * the view glides across the board to each cluster; a note peels off and flicks away to show a change; a pull back.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { cork: "#b98a58", corkDark: "#8a6238", yellow: "#ffe66b", pink: "#ff9fc4", mint: "#a6ebc2", blue: "#9fd0ff", orange: "#ffc27a", ink: "#1d2330", string: "#d02f2f" };
  const HAND = "Caveat", MARK = "Permanent Marker";
  const DUR = 13;
  const BEATS = [0, 2.2, 4.8, 7.0, 9.0, 11.0];

  // ------------------------------------------------------------------ board helpers (reuse these)
  let U = 1, T = 0;
  /** Slap-on: from above and larger, shrinking with a small bounce, the tilt settling. Returns { s, dy, rot, k }. */
  function slap(at, tilt) {
    const k = B.prog(T, at, 0.32);
    if (k <= 0) return null;
    const e = B.ease.outBack(k, 2.2);
    return { s: B.lerp(1.3, 1, e), dy: -(1 - e) * 6 * U, rot: tilt + (1 - B.ease.outCubic(k)) * 0.12, k };
  }
  /**
   * A sticky note of side s centred at (x, y): soft shadow down-right, pastel paper with a faint fold sheen, a darker
   * glued strip across the top, the lower-right corner curled up. content(g, s) draws on it in note space (0..s).
   * o: { peel (0..1: peels off from the bottom and flicks away) }
   */
  function note(g, x, y, s, col, tilt, at, content, o = {}) {
    const m = slap(at, tilt);
    if (!m) return;
    const peel = o.peel ?? 0;
    if (peel >= 1) return;
    g.save();
    g.translate(x + peel * peel * 40 * U, y + m.dy - peel * 12 * U);
    g.rotate(m.rot + peel * 1.2);
    g.scale(m.s * (1 - peel * 0.3), m.s * (1 - peel * 0.3));
    g.translate(-s / 2, -s / 2);
    const curl = s * (0.09 + 0.25 * peel), lift = (m.s - 1) * 4 + peel;
    const body = (c) => {
      c.beginPath();
      c.moveTo(0, 0);
      c.lineTo(s, 0);
      c.lineTo(s, s - curl);
      c.quadraticCurveTo(s - curl * 0.35, s - curl * 0.2, s - curl, s);
      c.lineTo(0, s);
      c.closePath();
    };
    B.withShadow(g, { color: "rgba(40,20,5,0.42)", blur: (1.2 + lift * 2.5) * U, x: (0.6 + lift * 1.5) * U, y: (0.9 + lift * 2.2) * U }, () => {
      body(g);
      g.fillStyle = col;
      g.fill();
    });
    g.save();
    body(g);
    g.clip();
    g.fillStyle = B.linear(g, 0, 0, s, s, ["rgba(255,255,255,0.22)", "rgba(255,255,255,0)", "rgba(0,0,0,0.06)"]);
    g.fillRect(0, 0, s, s);
    g.fillStyle = B.rgba(B.shade(col, -0.25), 0.35); // the glued strip
    g.fillRect(0, 0, s, s * 0.16);
    content(g, s);
    g.restore();
    // the curled corner: the paper's underside, lit along its fold
    g.beginPath();
    g.moveTo(s, s - curl);
    g.quadraticCurveTo(s - curl * 0.35, s - curl * 0.2, s - curl, s);
    g.quadraticCurveTo(s - curl * 0.75, s - curl * 0.75, s, s - curl);
    g.fillStyle = B.linear(g, s - curl, s, s, s - curl, [B.shade(col, -0.18), B.shade(col, 0.35)]);
    g.fill();
    g.restore();
  }
  /** Index card (white, blue rules, one red top rule), held by a strip of tape or a pin. content in card space. */
  function card(g, x, y, w, h, tilt, at, content, o = {}) {
    const m = slap(at, tilt);
    if (!m) return;
    g.save();
    g.translate(x, y + m.dy);
    g.rotate(m.rot);
    g.scale(m.s, m.s);
    g.translate(-w / 2, -h / 2);
    B.withShadow(g, { color: "rgba(40,20,5,0.4)", blur: 1.6 * U, x: 0.8 * U, y: 1.2 * U }, () => {
      g.fillStyle = "#fbf8f0";
      g.fillRect(0, 0, w, h);
    });
    g.strokeStyle = "rgba(90,140,200,0.35)";
    g.lineWidth = 0.15 * U;
    for (let yy = h * 0.3; yy < h - 1; yy += h * 0.13) {
      g.beginPath();
      g.moveTo(0, yy);
      g.lineTo(w, yy);
      g.stroke();
    }
    g.strokeStyle = "rgba(208,47,47,0.45)";
    g.beginPath();
    g.moveTo(0, h * 0.2);
    g.lineTo(w, h * 0.2);
    g.stroke();
    content(g, w, h);
    if (o.tape !== false) tape(g, w / 2, -0.4 * U, w * 0.32, -0.04);
    g.restore();
  }
  /** Translucent tape strip with torn ends. */
  function tape(g, x, y, w, rot) {
    g.save();
    g.translate(x, y);
    g.rotate(rot);
    const h = 4.2 * U, r = B.rng(B.hash(w, x));
    g.beginPath();
    g.moveTo(-w / 2, -h / 2);
    for (let i = 0; i <= 6; i++) g.lineTo(-w / 2 + r.range(-0.4, 0.4) * U, -h / 2 + (i / 6) * h);
    for (let i = 6; i >= 0; i--) g.lineTo(w / 2 + r.range(-0.4, 0.4) * U, -h / 2 + (i / 6) * h);
    g.closePath();
    g.fillStyle = "rgba(245,240,215,0.62)";
    g.fill();
    g.strokeStyle = "rgba(255,255,255,0.4)";
    g.lineWidth = 0.15 * U;
    g.stroke();
    g.restore();
  }
  /** Round push-pin: cast shadow, domed head with a highlight; pops in at `at`. */
  function pin(g, x, y, col, at) {
    const k = B.prog(T, at, 0.18);
    if (k <= 0) return;
    const r = 1.5 * U * B.ease.outBack(k, 3);
    g.fillStyle = "rgba(30,15,5,0.35)";
    g.beginPath();
    g.ellipse(x + r * 0.8, y + r * 0.9, r * 1.05, r * 0.75, 0.6, 0, B.TAU);
    g.fill();
    g.fillStyle = B.radial(g, x - r * 0.35, y - r * 0.4, r * 0.1, r * 1.2, [B.shade(col, 0.45), col, B.shade(col, -0.35)]);
    g.beginPath();
    B.circle(g, x, y, r);
    g.fill();
    g.fillStyle = "rgba(255,255,255,0.75)";
    g.beginPath();
    B.circle(g, x - r * 0.35, y - r * 0.38, r * 0.25);
    g.fill();
  }
  /**
   * Red string from pin a to pin b: it unspools from a, reaches b, then pulls tight with a decaying bounce in its sag.
   * A marker arrow is drawn beside it to show direction once it is tight.
   */
  function string(g, a, b, at, o = {}) {
    const k = B.prog(T, at, 0.35, "outCubic");
    if (k <= 0) return;
    const end = [B.lerp(a[0], b[0], k), B.lerp(a[1], b[1], k)], L = B.dist(a[0], a[1], end[0], end[1]);
    const settle = T - at - 0.35, sag = (settle < 0 ? 0.18 : 0.04 + 0.12 * Math.exp(-7 * settle) * Math.cos(settle * 26)) * L;
    g.save();
    g.strokeStyle = "rgba(40,15,5,0.3)";
    g.lineWidth = 0.4 * U;
    g.beginPath();
    g.moveTo(a[0] + 0.6 * U, a[1] + 0.8 * U);
    g.quadraticCurveTo((a[0] + end[0]) / 2 + 0.6 * U, (a[1] + end[1]) / 2 + sag + 1.4 * U, end[0] + 0.6 * U, end[1] + 0.8 * U);
    g.stroke();
    g.strokeStyle = PAL.string;
    g.lineWidth = 0.38 * U;
    g.beginPath();
    g.moveTo(a[0], a[1]);
    g.quadraticCurveTo((a[0] + end[0]) / 2, (a[1] + end[1]) / 2 + sag, end[0], end[1]);
    g.stroke();
    g.restore();
    if (o.arrow !== false && settle > 0.05) {
      // the marker arrow beside the string, offset to one side, drawn on in the direction of the link
      const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy), nx = -dy / l, ny = dx / l, off = (o.side ?? 1) * 4 * U;
      const p0 = [a[0] + dx * 0.32 + nx * off, a[1] + dy * 0.32 + ny * off + 2 * U], p1 = [a[0] + dx * 0.68 + nx * off, a[1] + dy * 0.68 + ny * off + 2 * U];
      B.arrow(g, B.wobble(B.densify([p0, p1], U), { amp: 0.3 * U, seed: 3 }), { p: B.prog(settle, 0.05, 0.3), width: 0.55 * U, head: 2.4 * U, headStyle: "open", color: PAL.ink });
    }
  }
  /** Felt-tip handwriting: wraps to maxW, each word on its own slight slant and baseline, written on as p grows. */
  function write(g, text, x, y, size, maxW, p, o = {}) {
    if (p <= 0) return;
    g.save();
    const fam = o.family || HAND;
    g.font = B.font(size, fam, o.family === MARK ? 400 : 700);
    g.fillStyle = o.color || PAL.ink;
    g.textBaseline = "middle";
    const lines = B.wrap(g, text, maxW), lh = size * (o.lineH ?? 1.0), total = lines.join(" ").length + 1;
    let budget = Math.floor(B.clamp(p) * total + 1e-6);
    lines.forEach((line, li) => {
      const lw = g.measureText(line).width, sp = g.measureText(" ").width;
      let xx = o.align === "left" ? x : x - lw / 2;
      const ly = y + (li - (lines.length - 1) / 2) * lh;
      line.split(" ").forEach((w, wi) => {
        const r = B.rng(B.hash(w, li, wi, o.seed ?? 0)), shown = w.slice(0, Math.max(0, budget));
        budget -= w.length + 1;
        if (shown) {
          g.save();
          g.translate(xx, ly + r.range(-0.06, 0.06) * size);
          g.rotate(r.range(-0.05, 0.04));
          g.fillText(shown, 0, 0);
          g.restore();
        }
        xx += g.measureText(w).width + sp;
      });
    });
    g.restore();
  }
  /** Marker stroke (underline, cross, circle) along pts, written on. */
  function marker(g, pts, p, o = {}) {
    if (p <= 0) return;
    B.handLine(g, pts, { width: (o.w ?? 0.75) * U, color: o.color || PAL.ink, amp: 0.35 * U, seed: o.seed ?? 5, p, passes: o.passes ?? 1 });
  }
  const loop = (cx, cy, rx, ry, turns = 1.15) => Array.from({ length: 60 }, (_, i) => {
    const a = -2.2 + (i / 59) * B.TAU * turns;
    return [cx + Math.cos(a) * rx * (1 + 0.05 * i / 59), cy + Math.sin(a) * ry];
  });

  // ------------------------------------------------------------------ the board: cork, pinholes, wooden frame
  function corkTile(W, H) {
    return B.layer("sticky-cork", W, H, (g, w, h) => {
      const u = Math.min(w, h) / 100, r = B.rng(29);
      g.fillStyle = PAL.cork;
      g.fillRect(0, 0, w, h);
      B.mottle(g, w, h, { amount: 0.35, feature: 0.08, seed: 30, mode: "soft-light" });
      const n = Math.round((w * h) / (u * u) * 2.2);
      for (let i = 0; i < n; i++) {
        // granules: dark and light chips of cork
        const d = r() < 0.6;
        g.fillStyle = d ? B.rgba(PAL.corkDark, r.range(0.25, 0.7)) : B.rgba("#e2bb88", r.range(0.2, 0.55));
        g.beginPath();
        g.ellipse(r() * w, r() * h, r.range(0.08, 0.32) * u, r.range(0.06, 0.22) * u, r() * B.TAU, 0, B.TAU);
        g.fill();
      }
      for (let i = 0; i < 18; i++) {
        g.fillStyle = "rgba(40,20,5,0.55)"; // old pinholes
        g.beginPath();
        B.circle(g, r() * w, r() * h, 0.22 * u);
        g.fill();
      }
      B.grain(g, w, h, { amount: 0.15, seed: 31, mode: "overlay" });
    });
  }
  function board(g, L) {
    const { W, H } = L, tile = corkTile(W, H), bx = L.board;
    g.fillStyle = "#3b2c22";
    g.fillRect(bx.x - W, bx.y - H, bx.w + 2 * W, bx.h + 2 * H);
    const fw = 4 * U; // the wooden frame
    g.fillStyle = B.linear(g, bx.x - fw, bx.y - fw, bx.x + fw * 3, bx.y + fw * 3, ["#c99b62", "#8f6234"]);
    g.fillRect(bx.x - fw, bx.y - fw, bx.w + 2 * fw, bx.h + 2 * fw);
    g.strokeStyle = "rgba(60,30,10,0.35)";
    g.lineWidth = 0.15 * U;
    for (let i = 0; i < 5; i++) {
      g.strokeRect(bx.x - fw * (0.2 + i * 0.17), bx.y - fw * (0.2 + i * 0.17), bx.w + fw * (0.4 + i * 0.34), bx.h + fw * (0.4 + i * 0.34));
    }
    g.save();
    g.beginPath();
    g.rect(bx.x, bx.y, bx.w, bx.h);
    g.clip();
    // mirrored tiling: every other tile is flipped, so the cork runs on across the seams
    for (let iy = 0; bx.y + iy * H < bx.y + bx.h; iy++)
      for (let ix = 0; bx.x + ix * W < bx.x + bx.w; ix++) {
        g.save();
        g.translate(bx.x + ix * W + (ix % 2 ? W : 0), bx.y + iy * H + (iy % 2 ? H : 0));
        g.scale(ix % 2 ? -1 : 1, iy % 2 ? -1 : 1);
        g.drawImage(tile, 0, 0);
        g.restore();
      }
    g.fillStyle = B.linear(g, 0, bx.y, 0, bx.y + 2 * U, ["rgba(40,20,5,0.4)", "rgba(40,20,5,0)"]);
    g.fillRect(bx.x, bx.y, bx.w, 2 * U);
    g.restore();
  }

  // ------------------------------------------------------------------ subjects: clusters of notes (the setting: replace these)
  function layout(W, H) {
    const F = B.frame(W, H), P = F.portrait, u = F.u;
    // clusters snake across a 3 x 2 board: title, diagram, number / steps, step 3, close
    const gx = W * 0.98, gy = H * 0.92, pos = [[0, 0], [1, 0], [2, 0], [2, 1], [1, 1], [0, 1]].map(([c, r]) => [c * gx, r * gy]);
    const pad = P ? 0.56 : 0.58;
    return { F, P, u, W, H, pos, ns: P ? 40 * u : 40 * u, txt: P ? 7 * u : 7 * u, board: { x: -W * pad, y: -H * pad, w: 2 * gx + 2 * W * pad, h: gy + 2 * H * pad } };
  }
  const CLUSTERS = [
    // title: a taped index card, two notes with doodles
    (g, L) => {
      const P = L.P, u = L.u, w = P ? 78 * u : 74 * u, h = P ? 42 * u : 34 * u;
      card(g, 0, P ? -12 * u : -4 * u, w, h, -0.03, 0.1, (c, cw, ch) => {
        write(c, "How do bees make honey?", cw / 2, ch * 0.58, (P ? 10 : 8.4) * u, cw * 0.88, B.prog(T, 0.35, 0.7), { family: MARK, lineH: 1.15 });
        marker(c, [[cw * 0.18, ch * 0.88], [cw * 0.82, ch * 0.86]], B.prog(T, 1.1, 0.25), { color: PAL.string, w: 0.9, seed: 7 });
      });
      // written by 1.45 s, so both notes hold finished for most of a second before the view moves on
      note(g, P ? -20 * u : -46 * u, P ? 32 * u : 22 * u, L.ns * 0.8, PAL.yellow, -0.08, 0.85, (c, s) => {
        write(c, "bzz!", s * 0.68, s * 0.3, L.txt * 1.1, s, B.prog(T, 1.0, 0.2));
        bee(c, s * 0.3, s * 0.68, s * 0.14, B.prog(T, 1.05, 0.4));
      });
      note(g, P ? 22 * u : 46 * u, P ? 36 * u : 24 * u, L.ns * 0.8, PAL.pink, 0.07, 1.0, (c, s) => {
        write(c, "a sweet job", s / 2, s * 0.55, L.txt * 0.95, s * 0.84, B.prog(T, 1.1, 0.35));
      });
      pin(g, P ? 22 * u : 46 * u, (P ? 36 : 24) * u - L.ns * 0.34, "#3d6fd0", 1.15);
    },
    // diagram: who does what, linked with red string and marker arrows
    (g, L) => {
      const P = L.P, u = L.u, a = BEATS[1] + 0.35, s = L.ns * (P ? 0.82 : 0.8);
      const spots = P ? [[-18, -30], [18, -6], [-18, 18], [18, 42]] : [[-54, 0], [-18, 6], [18, -2], [54, 5]];
      const items = [["flower: nectar", PAL.yellow], ["forager bee", PAL.pink], ["house bee", PAL.mint], ["honeycomb", PAL.blue]];
      card(g, P ? 0 : 0, P ? -50 * u : -30 * u, P ? 54 * u : 46 * u, P ? 13 * u : 11 * u, 0.02, a - 0.15, (c, cw, ch) => write(c, "WHO DOES WHAT", cw / 2, ch * 0.6, (P ? 5.4 : 5.2) * u, cw, B.prog(T, a, 0.35), { family: MARK }), { tape: true });
      // a string must never cross writing: side by side, pins at the top; stacked, the string leaves from a second
      // pin at the bottom corner nearest the next note and arrives at the next note's top pin
      const pins = spots.map(([x, y]) => [x * u, y * u - s * 0.36]);
      const outs = spots.map(([x, y], i) => (P && i < 3 ? [x * u + Math.sign(spots[i + 1][0] - x) * s * 0.26, y * u + s * 0.36] : pins[i]));
      items.forEach(([txt, col], i) => {
        note(g, spots[i][0] * u, spots[i][1] * u, s, col, [-0.06, 0.05, -0.04, 0.07][i], a + 0.12 + i * 0.22, (c, ss) => write(c, txt, ss / 2, ss * 0.56, L.txt * 0.92, ss * 0.86, B.prog(T, a + 0.25 + i * 0.22, 0.3)));
      });
      items.forEach((_, i) => {
        const col = [PAL.string, "#3d6fd0", "#f2c230", PAL.string][i];
        if (!P || i > 0) pin(g, pins[i][0], pins[i][1], col, a + 0.3 + i * 0.22);
        if (P && i < 3) pin(g, outs[i][0], outs[i][1], col, a + 0.35 + i * 0.22);
      });
      for (let i = 0; i < 3; i++) string(g, outs[i], pins[i + 1], a + 0.8 + i * 0.2, { side: P ? 1 : -1 }); // every link's arrow is drawn before the view moves on
    },
    // key number: water in nectar, crossed out with one marker line (still readable), the honey figure below, circled
    (g, L) => {
      const P = L.P, u = L.u, a = BEATS[2] + 0.35, w = P ? 74 * u : 84 * u, h = P ? 80 * u : 66 * u;
      card(g, 0, 0, w, h, -0.025, a, (c, cw, ch) => {
        write(c, "WATER IN IT", cw / 2, ch * 0.1, (P ? 7 : 6.5) * u, cw, B.prog(T, a + 0.15, 0.3), { family: MARK });
        write(c, "nectar:", cw * 0.07, ch * 0.36, (P ? 8 : 7.5) * u, cw, B.prog(T, a + 0.4, 0.2), { align: "left" });
        write(c, "~80%", cw * 0.64, ch * 0.36, (P ? 15 : 14) * u, cw, B.prog(T, a + 0.55, 0.3), { family: MARK });
        marker(c, [[cw * 0.4, ch * 0.37], [cw * 0.88, ch * 0.35]], B.prog(T, a + 0.9, 0.15), { w: 0.55, seed: 3 });
        write(c, "honey:", cw * 0.07, ch * 0.72, (P ? 8 : 7.5) * u, cw, B.prog(T, a + 1.05, 0.15), { align: "left" });
        write(c, "~18%", cw * 0.6, ch * 0.72, (P ? 17 : 16) * u, cw, B.prog(T, a + 1.18, 0.25), { family: MARK });
        marker(c, loop(cw * 0.6, ch * 0.72, cw * 0.27, ch * 0.14), B.prog(T, a + 1.45, 0.25), { color: PAL.string, w: 0.8, seed: 9 });
      });
    },
    // steps 1-2: a heading card, two numbered notes linked by string
    (g, L) => {
      const P = L.P, u = L.u, a = BEATS[3] + 0.35, s = L.ns, [p1, p2] = stepSpots(L);
      heading(g, L, "HOW BEES DO IT", a - 0.2);
      stepNote(g, L, p1, s, PAL.yellow, -0.05, a, "1", "fly out and sip nectar");
      stepNote(g, L, p2, s, PAL.pink, 0.06, a + 0.5, "2", "bee to bee: enzymes split sugar");
      const o1 = P ? [p1[0] + s * 0.26, p1[1] + s * 0.36] : [p1[0], p1[1] - s * 0.36]; // stacked: pinned below the writing
      pin(g, o1[0], o1[1], PAL.string, a + 0.3);
      pin(g, p2[0], p2[1] - s * 0.36, "#3d6fd0", a + 0.8);
      string(g, o1, [p2[0], p2[1] - s * 0.36], a + 0.9, { side: -1 });
    },
    // step 3: fan it dry; the "runny" note peels off and "thick honey" replaces it, with a star badge
    (g, L) => {
      const P = L.P, u = L.u, a = BEATS[4] + 0.35, s = L.ns, [p3, p4] = stepSpots(L);
      heading(g, L, "LAST STEP", a - 0.2);
      stepNote(g, L, p3, s, PAL.blue, -0.04, a, "3", "fan wings: the water dries off");
      pin(g, p3[0], p3[1] - s * 0.36, "#f2c230", a + 0.3);
      note(g, p4[0], p4[1], s * 0.9, PAL.mint, 0.05, a + 0.8, (c, ss) => write(c, "thick honey, capped with wax", ss / 2, ss * 0.56, L.txt, ss * 0.88, B.prog(T, a + 0.9, 0.35)));
      note(g, p4[0], p4[1], s * 0.9, PAL.orange, -0.07, a + 0.4, (c, ss) => write(c, "still runny...", ss / 2, ss * 0.55, L.txt, ss * 0.88, B.prog(T, a + 0.5, 0.3)), { peel: B.prog(T, a + 0.62, 0.3, "inCubic") });
      badge(g, p4[0] + s * 0.5, p4[1] - s * 0.5, 7 * u, a + 1.25);
      if (P) doodle(g, -22 * u, 62 * u, 26 * u, PAL.yellow, -0.06, a + 0.55);
    },
    // close: the summary card, circled, with a star badge; the view pulls back over the whole board
    (g, L) => {
      const P = L.P, u = L.u, a = BEATS[5] + 0.3, w = P ? 80 * u : 92 * u, h = P ? 56 * u : 50 * u;
      card(g, 0, 0, w, h, 0.02, a, (c, cw, ch) => {
        write(c, "nectar in, water out", cw / 2, ch * (P ? 0.3 : 0.37), 7 * u, cw * (P ? 0.62 : 0.84), B.prog(T, a + 0.2, 0.45), { family: MARK });
        write(c, "= HONEY", cw / 2, ch * 0.72, (P ? 12 : 11) * u, cw, B.prog(T, a + 0.7, 0.25), { family: MARK });
        marker(c, loop(cw / 2, ch * 0.72, cw * 0.38, ch * 0.2), B.prog(T, a + 1.0, 0.3), { color: PAL.string, w: 0.85, seed: 11 });
      });
      badge(g, w * (P ? 0.4 : 0.45), -h * 0.5 - 4 * u, 11 * u, a + 1.2, "yum");
      // portrait: the three steps, recapped as a row of small notes under the card
      if (P) [["1 sip", PAL.yellow], ["2 split", PAL.pink], ["3 dry", PAL.blue]].forEach(([str, col], i) =>
        note(g, (i - 1) * 27 * u, 46 * u, 24 * u, col, [-0.06, 0.04, -0.03][i], a + 0.5 + i * 0.12, (c, ss) => write(c, str, ss / 2, ss * 0.58, L.txt, ss * 0.9, B.prog(T, a + 0.6 + i * 0.12, 0.2))));
      if (P) doodle(g, 20 * u, 73 * u, 26 * u, PAL.mint, 0.07, a + 0.9);
    },
  ];
  const stepSpots = (L) => (L.P ? [[-12 * L.u, -14 * L.u], [12 * L.u, 31 * L.u]] : [[-26 * L.u, 8 * L.u], [26 * L.u, 10 * L.u]]);
  /** A note with only a marker bee doodle on it (no words): fills the board's foot in portrait. */
  const doodle = (g, x, y, s, col, tilt, at) => note(g, x, y, s, col, tilt, at, (c, ss) => bee(c, ss * 0.45, ss * 0.62, ss * 0.17, B.prog(T, at + 0.1, 0.35)));
  /** Taped heading card over a cluster. */
  const heading = (g, L, str, at) => card(g, 0, (L.P ? -50 : -30) * L.u, (L.P ? 60 : 56) * L.u, (L.P ? 14 : 12) * L.u, 0.02, at, (c, cw, ch) => write(c, str, cw / 2, ch * 0.6, (L.P ? 6.2 : 6) * L.u, cw, B.prog(T, at + 0.12, 0.3), { family: MARK }));
  /** Star badge: a yellow paper star outlined in marker, popping in, with an optional word. */
  function badge(g, x, y, r, at, word) {
    if (T <= at) return;
    const k = B.ease.outBack(B.prog(T, at, 0.3), 2.5);
    g.save();
    g.translate(x, y);
    g.scale(k, k);
    g.rotate(0.2);
    B.withShadow(g, { color: "rgba(40,20,5,0.35)", blur: U, x: 0.5 * U, y: 0.8 * U }, () => {
      g.beginPath();
      B.star(g, 0, 0, 5, r, r * 0.52);
      g.fillStyle = PAL.yellow;
      g.fill();
    });
    g.strokeStyle = PAL.string;
    g.lineWidth = 0.6 * U;
    g.stroke();
    if (word) write(g, word, 0, r * 0.06, r * 0.44, r * 2, 1, { family: MARK });
    g.restore();
  }
  /** A step note: a big marker numeral, then the step in handwriting. */
  function stepNote(g, L, p, s, col, tilt, at, num, text) {
    note(g, p[0], p[1], s, col, tilt, at, (c, ss) => {
      write(c, num, ss * 0.13, ss * 0.27, ss * 0.2, ss, B.prog(T, at + 0.15, 0.1), { family: MARK });
      marker(c, [[ss * 0.05, ss * 0.37], [ss * 0.22, ss * 0.36]], B.prog(T, at + 0.25, 0.1), { w: 0.6 });
      write(c, text, ss * 0.53, ss * 0.66, L.txt, ss * 0.86, B.prog(T, at + 0.22, 0.36));
    });
  }
  /** Quick marker doodle of a bee: striped body, two wing loops, drawn on with p. */
  function bee(g, x, y, r, p) {
    if (p <= 0) return;
    marker(g, loop(x, y, r * 1.2, r * 0.8, 1.05), B.clamp(p * 2), { w: 0.55 });
    marker(g, [[x - r * 0.2, y - r * 0.75], [x - r * 0.2, y + r * 0.75]], B.clamp(p * 2 - 0.8), { w: 0.55 });
    marker(g, [[x + r * 0.35, y - r * 0.7], [x + r * 0.35, y + r * 0.7]], B.clamp(p * 2 - 0.9), { w: 0.55 });
    marker(g, loop(x - r * 0.1, y - r * 1.25, r * 0.5, r * 0.55, 1.05), B.clamp(p * 2 - 1), { w: 0.45 });
    marker(g, loop(x + r * 0.5, y - r * 1.2, r * 0.45, r * 0.5, 1.05), B.clamp(p * 2 - 1), { w: 0.45 });
  }

  // ------------------------------------------------------------------ camera: glide across the board, pull back at the end
  function camera(L, t) {
    let x = L.pos[0][0], y = L.pos[0][1], dip = 0;
    for (let i = 1; i < BEATS.length; i++) {
      const k = B.span(t, BEATS[i] - 0.25, BEATS[i] + 0.5, "inOutCubic");
      x += (L.pos[i][0] - L.pos[i - 1][0]) * k;
      y += (L.pos[i][1] - L.pos[i - 1][1]) * k;
      dip = Math.max(dip, Math.sin(Math.PI * k));
    }
    // a short pull back that lands and holds: never so far that the writing gets small; the board's wooden
    // frame corner slides into view at the lower left
    const back = B.span(t, BEATS[5] + 0.9, BEATS[5] + 1.5, "inOutSine");
    const zoom = (1 - 0.14 * dip) * B.lerp(1, 0.9, back);
    y += L.H * 0.03 * back;
    return { x, y: y + B.bob(t, 0.3 * L.u, 5), zoom };
  }

  function draw(ctx, W, H, t) {
    const L = layout(W, H), F = L.F;
    U = L.u;
    T = t;
    const cam = camera(L, t);
    ctx.save();
    ctx.translate(W / 2, F.safe.cy);
    ctx.scale(cam.zoom, cam.zoom);
    ctx.translate(-cam.x, -cam.y);
    board(ctx, L);
    CLUSTERS.forEach((fn, i) => {
      const [px, py] = L.pos[i];
      if (Math.abs(px - cam.x) > W * 1.4 / cam.zoom || Math.abs(py - cam.y) > H * 1.3 / cam.zoom) return;
      ctx.save();
      ctx.translate(px, py);
      fn(ctx, L);
      ctx.restore();
    });
    ctx.restore();
    // finishing: a gentle spotlight falloff to the corners, light paper grain
    B.vignette(ctx, W, H, { amount: 0.38, inner: 0.42, color: "#1e1006", cy: F.safe.cy });
    B.grain(ctx, W, H, { amount: 0.04, t, fps: 12, mode: "overlay", seed: 29 });
  }

  // ------------------------------------------------------------------ sound: paper slaps, pin pops, string twangs, marker squeaks
  SOUND.define("sticky-slap", (v) => {
    // a paper note landing: a soft slap with a faint tacky stick
    v.noise({ filter: "bandpass", f: 1400, q: 0.7, a: 0.002, len: 0.06, peak: 0.45 });
    v.tone({ f: 160, f2: 90, glide: 0.05, a: 0.002, len: 0.07, peak: 0.25 });
    v.noise({ at: 0.05, filter: "highpass", f: 4000, a: 0.004, len: 0.03, peak: 0.06 });
  }, { verb: 0.1 });
  SOUND.define("sticky-pin", (v) => v.tone({ type: "triangle", f: 1300, f2: 700, glide: 0.03, a: 0.001, len: 0.05, peak: 0.25 }), { verb: 0.1 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.5 });
    // title
    k.at(0.1, "sticky-slap", { gain: 1 }).at(0.35, "marker", { dur: 0.7 }).at(1.1, "marker", { dur: 0.25, pitch: 2 });
    k.at(0.85, "sticky-slap").at(1.0, "sticky-slap", { pitch: 2 }).at(1.05, "marker", { dur: 0.4 }).at(1.15, "sticky-pin");
    BEATS.slice(1).forEach((b) => k.at(b - 0.25, "swish", { dur: 0.8, gain: 0.35 }));
    // diagram: notes, pins, strings
    const a1 = BEATS[1] + 0.35;
    k.at(a1 - 0.15, "sticky-slap").at(a1, "marker", { dur: 0.35 });
    for (let i = 0; i < 4; i++) k.at(a1 + 0.12 + i * 0.22, "sticky-slap", { pitch: i }).at(a1 + 0.3 + i * 0.22, "sticky-pin", { pitch: i * 2 });
    for (let i = 0; i < 3; i++) k.at(a1 + 0.8 + i * 0.2, "rustle", { dur: 0.3, gain: 0.4 }).at(a1 + 1.15 + i * 0.2, "twang", { gain: 0.45, pitch: i * 3 });
    // number: card, writing, cross-out, the new figure, a red circle
    const a2 = BEATS[2] + 0.35;
    k.at(a2, "sticky-slap", { gain: 1 }).at(a2 + 0.15, "marker", { dur: 0.3 }).at(a2 + 0.55, "marker", { dur: 0.3 });
    k.at(a2 + 0.85, "scribble", { dur: 0.22 }).at(a2 + 1.05, "marker", { dur: 0.4 }).at(a2 + 1.45, "marker", { dur: 0.25, pitch: 3 });
    k.at(a2 + 1.7, "ding", { gain: 0.3 });
    // steps
    const a3 = BEATS[3] + 0.35, a4 = BEATS[4] + 0.35;
    k.at(a3, "sticky-slap").at(a3 + 0.25, "marker", { dur: 0.45 }).at(a3 + 0.3, "sticky-pin");
    k.at(a3 - 0.2, "sticky-slap", { gain: 0.6 }).at(a3 + 0.5, "sticky-slap", { pitch: 2 }).at(a3 + 0.72, "marker", { dur: 0.36 }).at(a3 + 0.8, "sticky-pin", { pitch: 3 });
    k.at(a3 + 0.9, "rustle", { dur: 0.3 }).at(a3 + 1.25, "twang", { gain: 0.5 });
    k.at(a4, "sticky-slap").at(a4 + 0.25, "marker", { dur: 0.45 }).at(a4 + 0.3, "sticky-pin").at(a4 + 0.4, "sticky-slap", { pitch: -2 });
    k.at(a4 + 0.62, "paper", { dur: 0.3 }).at(a4 + 0.72, "swish", { dur: 0.3, gain: 0.5 }).at(a4 + 0.8, "sticky-slap", { pitch: 3 }).at(a4 + 0.9, "marker", { dur: 0.35 });
    k.at(a4 - 0.2, "sticky-slap", { gain: 0.6 }).at(a4 + 1.25, "pop").at(a4 + 1.3, "success", { gain: 0.5 });
    // close
    const a5 = BEATS[5] + 0.3;
    k.at(a5, "sticky-slap", { gain: 1 }).at(a5 + 0.2, "marker", { dur: 0.45 }).at(a5 + 0.7, "marker", { dur: 0.25 }).at(a5 + 1.0, "marker", { dur: 0.3, pitch: 3 });
    k.at(a5 + 1.2, "pop").at(a5 + 1.25, "chord", { notes: ["G4", "B4", "D5", "G5"], strum: 0.05, gain: 0.5 });
  }

  Player.register({
    id: "sticky-notes",
    name: "Sticky Notes",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Caveat:wght@700&family=Permanent+Marker&display=swap",
      faces: ['700 20px "Caveat"', '400 20px "Permanent Marker"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.9, 4.6, 6.7, 8.65, 10.7, 12.9],
    draw,
    score,
  });
})();
