/* 41 Punk Zine Collage - reference animation.
 * Topic (setting, replace it): "How does a speaker make noise?" - current in the coil, magnet push-pull, the cone
 * shoves the air; ears top out at about 20,000 vibrations a second.
 * Rendering (keep it): a photocopied black-and-white zine page: harsh threshold "xerox" cut-outs with toner grit,
 * ransom-note letters (each its own scrap, font, size and tilt), typewriter text, staples and safety pins, black marker
 * arrows and cross-outs, crooked scissor-stepped scraps; ONE fluorescent spot colour on its own plate, multiplied a
 * little off register; toner specks, drum streaks and grey copier-glass shadows at the edges.
 * Motion: everything on held frames (10 fps); letters land one per frame; jump cuts inside a shot; shots change with a
 * copier light-bar sweep or a one-frame black copy.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type
  // SPOT: the one fluorescent ink. Hot pink here; acid yellow (#e4ff1a) works the same way. Never both.
  const PAL = { paper: "#f3f1ea", white: "#fbfaf5", ink: "#121212", grey: "#8d8b85", light: "#cfccc4", glass: "#d6d4cc", spot: "#ff2e88" };
  const TYPE = "Special Elite", SCRAWL = "Rock Salt";
  const RANSOM = ["Archivo Black", "Abril Fatface", "Special Elite", "Bungee"]; // letters are cut from mixed sources
  const DUR = 12, BEATS = [0, 1.9, 4.0, 6.2, 8.4, 10.3], FPS = 10;
  const SWEEP = { 0: 1, 1: 1, 3: 1, 5: 1 }; // shots that arrive under the copier light bar; the others after a black copy
  const JUMPS = [1.05, 1.25, 1.2, 1.0, 1.1, 0.95]; // a jump cut inside each shot (local time)

  let U = 1, T = 0, SP = null; // T: held time; SP: the spot-colour plate of the page being drawn

  // ------------------------------------------------------------------ zine helpers (reuse these)
  const count = (lt, at) => (lt < at ? 0 : Math.floor((lt - at) * FPS + 1e-6) + 1); // one more per held frame
  /** Scissor-cut polygon centred on 0,0: straight snips at slightly different angles, the odd step notch. */
  function snip(w, h, seed, amt = 1) {
    const r = B.rng(seed), out = [];
    const c = [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]].map(([x, y]) => [x + r.range(-0.6, 0.6) * U * amt, y + r.range(-0.6, 0.6) * U * amt]);
    for (let i = 0; i < 4; i++) {
      const a = c[i], b = c[(i + 1) % 4], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / L, ny = (b[0] - a[0]) / L;
      out.push(a);
      for (let k = 1, n = r.int(1, 2); k <= n; k++) {
        const f = k / (n + 1) + r.range(-0.08, 0.08), off = r.range(-0.45, 0.45) * U * amt;
        const p = [a[0] + (b[0] - a[0]) * f + nx * off, a[1] + (b[1] - a[1]) * f + ny * off];
        out.push(p);
        if (r.chance(0.3)) out.push([p[0] + nx * 0.6 * U * amt, p[1] + ny * 0.6 * U * amt]); // scissor step
      }
    }
    return out;
  }
  /** A paper scrap as the copier sees it: hard grey shadow, flat fill, a dark line where the cut edge sat. */
  function scrap(g, pts, fill, o = {}) {
    g.save();
    g.translate(0.5 * U, 0.55 * U);
    g.beginPath();
    B.poly(g, pts, true);
    g.fillStyle = "rgba(18,18,18,0.28)";
    g.fill();
    g.restore();
    g.beginPath();
    B.poly(g, pts, true);
    if (fill) {
      g.fillStyle = fill;
      g.fill();
    }
    g.strokeStyle = PAL.ink;
    g.lineWidth = (o.edge ?? 0.22) * U;
    g.stroke();
  }
  /** Draw onto the spot plate with the main plate's current transform. */
  function onSpot(g, fn) {
    SP.save();
    SP.setTransform(g.getTransform());
    SP.fillStyle = PAL.spot;
    fn(SP);
    SP.restore();
  }
  /** A big spot-colour block (scissor cut or round), with pale pinholes where the ink skipped. */
  function spotBlock(g, x, y, w, h, rot, seed, round) {
    onSpot(g, (s) => {
      s.translate(x, y);
      s.rotate(rot);
      s.beginPath();
      if (round) s.ellipse(0, 0, w / 2, h / 2, 0, 0, B.TAU);
      else B.poly(s, snip(w, h, seed, 2), true);
      s.fill();
      const r = B.rng(seed + 7);
      s.globalCompositeOperation = "destination-out";
      for (let i = 0; i < 26; i++) {
        s.beginPath();
        B.circle(s, r.range(-0.45, 0.45) * w, r.range(-0.45, 0.45) * h, r.range(0.1, 0.35) * U);
        s.fill();
      }
    });
  }
  /**
   * Ransom-note word: every letter cut from a different source - its own scrap (white, newsprint grey, black with a
   * white letter, or spot colour), font, size, tilt and baseline. o: { n letters shown, align "left" | "center" }
   */
  function ransom(g, text, x, y, size, seed, o = {}) {
    const r = B.rng(seed), items = [];
    let total = 0;
    for (const ch of text) {
      if (ch === " ") {
        items.push({ space: size * 0.4 });
        total += size * 0.4;
        continue;
      }
      const face = r.pick(RANSOM), sz = size * r.range(0.84, 1.14), kind = r(), lower = face === "Abril Fatface" && r.chance(0.4);
      const st = kind < 0.2 ? "black" : kind < 0.36 ? "spot" : kind < 0.55 ? "grey" : "white";
      g.font = B.font(sz, face, 400);
      const c = lower ? ch.toLowerCase() : ch, pad = sz * r.range(0.12, 0.2), w = g.measureText(c).width + 2 * pad;
      items.push({ c, face, sz, st, w, h: sz * 1.22, rot: r.range(-0.13, 0.13), dy: r.range(-0.07, 0.07) * size, seed: r.int(1, 9999) });
      total += w + size * 0.05;
    }
    let xx = o.align === "center" ? x - total / 2 : x, shown = o.n ?? 99;
    for (const it of items) {
      if (it.space) {
        xx += it.space;
        continue;
      }
      if (shown-- > 0) {
        g.save();
        g.translate(xx + it.w / 2, y + it.dy);
        g.rotate(it.rot);
        const pts = snip(it.w, it.h, it.seed, 0.5);
        if (it.st === "spot") onSpot(g, (s) => (s.beginPath(), B.poly(s, pts, true), s.fill()));
        scrap(g, pts, it.st === "black" ? PAL.ink : it.st === "grey" ? PAL.light : it.st === "white" ? PAL.white : null, { edge: 0.18 });
        g.font = B.font(it.sz, it.face, 400);
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillStyle = it.st === "black" ? PAL.white : PAL.ink;
        g.fillText(it.c, 0, it.sz * 0.05);
        g.restore();
      }
      xx += it.w + size * 0.05;
    }
    return { w: total, l: o.align === "center" ? x - total / 2 : x };
  }
  /** Typewriter text: struck one character per held frame of reveal, each strike a little lighter or heavier. */
  function typed(g, text, x, y, size, o = {}) {
    g.save();
    g.font = B.font(size, TYPE, 400);
    g.textAlign = "left";
    g.textBaseline = "middle";
    const lines = o.maxW ? B.wrap(g, text, o.maxW) : [text], lh = size * 1.32;
    let shown = Math.floor((o.p ?? 1) * text.length + 1e-6);
    lines.forEach((line, li) => {
      let xx = o.align === "center" ? x - g.measureText(line).width / 2 : x;
      for (const ch of line) {
        if (shown-- <= 0) return;
        const h = B.hash01(li, Math.round(xx), o.seed || 1);
        g.globalAlpha = 0.7 + 0.3 * h;
        g.fillStyle = PAL.ink;
        if (ch !== " ") g.fillText(ch, xx, y + li * lh + (h - 0.5) * size * 0.07);
        xx += g.measureText(ch).width;
      }
    });
    g.restore();
    return { lines, bottom: y + lines.length * lh };
  }
  /** Black marker scrawl (drawn on as p goes 0 -> 1), marker arrow, and a zigzag cross-out. */
  function scrawl(g, pts, p, w = 1.1, seed = 1) {
    if (p > 0) B.taperStroke(g, pts, { width: w * U, color: PAL.ink, p, taperIn: 0.04, taperOut: 0.25, rough: 0.35, roughScale: 4, seed });
  }
  function scrawlArrow(g, pts, p, seed = 2) {
    if (p > 0) B.arrow(g, pts, { p, width: 1.15 * U, color: PAL.ink, head: 3.2 * U, headStyle: "open", rough: 0.45 * U, seed });
  }
  function crossOut(g, x0, x1, y, h, p, seed = 3) {
    const pts = [];
    for (let i = 0; i <= 7; i++) pts.push([B.lerp(x0, x1, i / 7), y + (i % 2 ? -h : h) * 0.4]);
    scrawl(g, pts, p, 0.9, seed);
  }
  /** Hand-scrawled words in a rough marker hand. */
  function scrawlText(g, text, x, y, size, p, rot = -0.04) {
    if (p <= 0) return;
    g.save();
    g.translate(x, y);
    g.rotate(rot);
    g.font = B.font(size, SCRAWL, 400);
    g.textAlign = "left";
    g.textBaseline = "middle";
    g.fillStyle = PAL.ink;
    g.fillText(B.typewriter(text, p), 0, 0);
    g.restore();
  }
  /** Staple: a bright crown with dark ends and a hard shadow. */
  function staple(g, x, y, rot) {
    g.save();
    g.translate(x, y);
    g.rotate(rot);
    g.fillStyle = "rgba(18,18,18,0.4)";
    g.fillRect(-2.6 * U, -0.1 * U, 5.6 * U, 0.75 * U);
    g.fillStyle = "#4a4a48";
    g.fillRect(-3 * U, -0.38 * U, 6 * U, 0.76 * U);
    g.fillStyle = "#e9e8e2";
    g.fillRect(-2.7 * U, -0.3 * U, 5.4 * U, 0.2 * U);
    g.fillStyle = PAL.ink;
    g.fillRect(-3 * U, -0.38 * U, 0.6 * U, 0.76 * U);
    g.fillRect(2.4 * U, -0.38 * U, 0.6 * U, 0.76 * U);
    g.restore();
  }
  /** Safety pin: coil at one end, clasp at the other, the pin shaft through the paper. */
  function safetyPin(g, x, y, rot, L) {
    g.save();
    g.translate(x, y);
    g.rotate(rot);
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.45 * U;
    g.lineCap = "round";
    g.beginPath();
    g.moveTo(-L / 2 + 1.2 * U, -0.9 * U);
    g.lineTo(L / 2 - 1 * U, -0.9 * U);
    g.moveTo(-L / 2 + 1.2 * U, 0.9 * U);
    g.lineTo(L / 2 - 1 * U, 0.4 * U);
    g.stroke();
    g.beginPath();
    g.arc(-L / 2 + 1.2 * U, 0, 0.9 * U, Math.PI / 2, Math.PI * 1.5);
    g.stroke();
    g.beginPath();
    B.circle(g, -L / 2 + 1.2 * U, 0, 0.45 * U);
    g.stroke();
    g.fillStyle = PAL.ink;
    g.beginPath();
    B.roundRect(g, L / 2 - 2.4 * U, -1.4 * U, 2.6 * U, 2.2 * U, 0.6 * U);
    g.fill();
    g.restore();
  }

  // ------------------------------------------------------------------ xerox cut-outs (reuse these)
  function hh(i, j, s) {
    let h = (Math.imul(i | 0, 0x27d4eb2d) ^ Math.imul(j | 0, 0x165667b1) ^ Math.imul(s | 0, 0x9e3779b1)) | 0;
    h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
    h ^= h >>> 13;
    return (h >>> 0) / 4294967296;
  }
  /**
   * Bake a photocopied cut-out (cached): paint a grey picture on white, then threshold it with coarse toner grit
   * (mid greys break into speckle, darks go solid, lights blow out), add a drum streak, cut the sheet out with
   * scissor steps and an edge line.
   */
  function xerox(key, w, h, paint, seed) {
    return B.layer(`pz:${key}`, w, h, (g, cw, ch) => {
      const m = B.canvas(cw, ch).getContext("2d");
      m.fillStyle = "#ffffff";
      m.fillRect(0, 0, cw, ch);
      paint(m, cw, ch);
      const d = m.getImageData(0, 0, cw, ch).data, out = g.createImageData(cw, ch), o = out.data;
      const blk = Math.max(1, Math.round(U * 0.28)), sx = Math.round(cw * (0.25 + 0.5 * hh(seed, 1, 2)));
      for (let y = 0; y < ch; y++)
        for (let x = 0; x < cw; x++) {
          const i = (y * cw + x) * 4, n = hh((x / blk) | 0, (y / blk) | 0, seed);
          const v = d[i] / 255 + (n - 0.5) * 0.55 - (Math.abs(x - sx) < U * 0.25 ? 0.35 : 0) + 0.04;
          const ink = v < 0.5;
          o[i] = ink ? 18 : 251;
          o[i + 1] = ink ? 18 : 250;
          o[i + 2] = ink ? 18 : 245;
          o[i + 3] = 255;
        }
      g.putImageData(out, 0, 0);
      const pts = snip(cw - 2 * U, ch - 2 * U, seed, 1.4).map(([x, y]) => [x + cw / 2, y + ch / 2]);
      g.globalCompositeOperation = "destination-in";
      g.beginPath();
      B.poly(g, pts, true);
      g.fill();
      g.globalCompositeOperation = "source-over";
      g.strokeStyle = PAL.ink;
      g.lineWidth = 0.3 * U;
      g.stroke();
    });
  }
  /** Place a cut-out centred at (cx, cy), scale k, tilt rot (hard copier shadow); returns subject fraction -> frame. */
  function placeX(g, img, cx, cy, k, rot) {
    g.save();
    g.translate(cx, cy);
    g.rotate(rot);
    g.scale(k, k);
    g.shadowColor = "rgba(18,18,18,0.35)";
    g.shadowOffsetX = 0.6 * U;
    g.shadowOffsetY = 0.7 * U;
    g.drawImage(img, -img.width / 2, -img.height / 2);
    g.restore();
    return (fx, fy) => {
      const x = (fx - 0.5) * img.width * k, y = (fy - 0.5) * img.height * k;
      return [cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)];
    };
  }

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  /** Speaker driver, front: frame ring with screw holes, surround, ribbed cone, domed dust cap. */
  function paintFront(g, w) {
    const c = w / 2, R = w * 0.44;
    g.fillStyle = "#2b2b2b";
    g.beginPath();
    B.circle(g, c, c, R);
    g.fill();
    g.fillStyle = B.radial(g, c - R * 0.3, c - R * 0.3, 0, R * 1.3, ["#c8c8c8", "#6a6a6a", "#2e2e2e"]);
    g.beginPath();
    B.circle(g, c, c, R * 0.86);
    g.fill();
    g.fillStyle = B.radial(g, c, c, R * 0.12, R * 0.74, ["#4a4a4a", "#a8a8a8", "#5a5a5a"]);
    g.beginPath();
    B.circle(g, c, c, R * 0.72);
    g.fill();
    g.strokeStyle = "#2a2a2a";
    g.lineWidth = w * 0.012;
    for (const k of [0.36, 0.5, 0.62]) {
      g.beginPath();
      B.circle(g, c, c, R * k);
      g.stroke();
    }
    g.fillStyle = B.radial(g, c - R * 0.06, c - R * 0.06, 0, R * 0.22, ["#f0f0f0", "#8a8a8a", "#333333"]);
    g.beginPath();
    B.circle(g, c, c, R * 0.2);
    g.fill();
    g.fillStyle = "#ffffff";
    for (let i = 0; i < 4; i++) {
      g.beginPath();
      B.circle(g, c + Math.cos(i * 1.571 + 0.785) * R * 0.93, c + Math.sin(i * 1.571 + 0.785) * R * 0.93, w * 0.018);
      g.fill();
    }
  }
  /** Speaker cut in half, cone opening to the right: plates and ring magnet, pole, coil windings, cone, cap. */
  function paintSection(g, w, h) {
    const R = (x, y, ww, hh2, c) => ((g.fillStyle = c), g.fillRect(x * w, y * h, ww * w, hh2 * h));
    g.fillStyle = "#d4d4d4";
    g.beginPath();
    B.poly(g, [[0.4 * w, 0.42 * h], [0.92 * w, 0.06 * h], [0.92 * w, 0.94 * h], [0.4 * w, 0.58 * h]], true);
    g.fill();
    R(0.04, 0.2, 0.08, 0.6, "#1e1e1e");
    R(0.12, 0.2, 0.14, 0.2, "#4a4a4a");
    R(0.12, 0.6, 0.14, 0.2, "#4a4a4a");
    R(0.26, 0.2, 0.05, 0.2, "#1e1e1e");
    R(0.26, 0.6, 0.05, 0.2, "#1e1e1e");
    R(0.12, 0.45, 0.24, 0.1, "#333333");
    for (let i = 0; i < 6; i++) {
      R(0.32 + i * 0.014, 0.4, 0.008, 0.045, "#111111");
      R(0.32 + i * 0.014, 0.555, 0.008, 0.045, "#111111");
    }
    g.strokeStyle = "#1e1e1e";
    g.lineWidth = w * 0.022;
    g.beginPath();
    g.moveTo(0.38 * w, 0.41 * h);
    g.lineTo(0.92 * w, 0.06 * h);
    g.moveTo(0.38 * w, 0.59 * h);
    g.lineTo(0.92 * w, 0.94 * h);
    g.stroke();
    g.beginPath();
    g.arc(0.4 * w, 0.5 * h, 0.1 * h, -1.2, 1.2);
    g.stroke();
    g.lineWidth = w * 0.01;
    g.strokeStyle = "#666666";
    g.beginPath();
    g.moveTo(0.31 * w, 0.2 * h);
    g.lineTo(0.95 * w, 0.02 * h);
    g.moveTo(0.31 * w, 0.8 * h);
    g.lineTo(0.95 * w, 0.98 * h);
    g.stroke();
  }
  /** A coil of wire with its two leads. */
  function paintCoil(g, w, h) {
    g.lineWidth = w * 0.03;
    for (let i = 0; i < 12; i++) {
      const x = w * (0.18 + i * 0.058);
      g.strokeStyle = "#1c1c1c";
      g.beginPath();
      g.ellipse(x, h * 0.5, w * 0.035, h * 0.3, 0, 0, B.TAU);
      g.stroke();
      g.strokeStyle = "#9a9a9a";
      g.beginPath();
      g.ellipse(x - w * 0.008, h * 0.47, w * 0.02, h * 0.22, 0, 3.6, 5.2);
      g.stroke();
    }
    g.strokeStyle = "#1c1c1c";
    g.beginPath();
    g.moveTo(w * 0.18, h * 0.8);
    g.lineTo(w * 0.04, h * 0.95);
    g.moveTo(w * 0.82, h * 0.8);
    g.lineTo(w * 0.96, h * 0.95);
    g.stroke();
  }
  const frontCut = () => xerox("front", Math.round(50 * U), Math.round(50 * U), (g, w) => paintFront(g, w), 31);
  const sectionCut = () => xerox("section", Math.round(80 * U), Math.round(56 * U), paintSection, 32);
  const coilCut = () => xerox("coil", Math.round(30 * U), Math.round(20 * U), paintCoil, 33);
  const PARTS = { magnet: [0.18, 0.3], coil: [0.36, 0.43], cone: [0.68, 0.27], mouth: [0.97, 0.5] };

  // ------------------------------------------------------------------ the shots (page coordinates)
  /** A label: typewriter word on a white snipped scrap, with a marker arrow to (px, py). */
  function label(g, text, x, y, px, py, lt, at, seed) {
    if (lt < at) return;
    g.save();
    g.translate(x, y);
    g.rotate((B.hash01(seed, 1) - 0.5) * 0.12);
    g.font = B.font(4.4 * U, TYPE, 400);
    const w = g.measureText(text).width + 2.4 * U;
    scrap(g, snip(w, 6.2 * U, seed, 0.5), PAL.white);
    typed(g, text, -w / 2 + 1.2 * U, 0, 4.4 * U, { seed });
    g.restore();
    const a = Math.atan2(py - y, px - x), d = Math.hypot(px - x, py - y), s = Math.min(d * 0.45, w * 0.5 + 2 * U);
    scrawlArrow(g, [[x + Math.cos(a) * s, y + Math.sin(a) * s], [B.lerp(x, px, 0.6) + 2 * U, B.lerp(y, py, 0.6)], [px - Math.cos(a) * 1.5 * U, py - Math.sin(a) * 1.5 * U]], B.prog(lt, at + 0.1, 0.3), seed);
  }
  function issue(g, F, lt) {
    typed(g, "SPEAKER ZINE #3 · FREE", F.safe.x + 3 * U, F.safe.y + 6 * U, 4 * U, { p: B.prog(lt, 0, 0.3), seed: 5 });
  }

  function shotTitle(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H, k = F.pick, x0 = S.x + 3 * U;
    issue(g, F, lt);
    spotBlock(g, k(W * 0.33, W * 0.5), H * k(0.55, 0.555), k(100, 86) * U, k(46, 42) * U, -0.04, 11);
    const sc = k([W * 0.77, H * 0.52], [W * 0.64, H * 0.325]), sz = k(1.12, 0.88);
    placeX(g, frontCut(), sc[0], sc[1], sz, 0.06);
    staple(g, sc[0] - 17 * U * sz, sc[1] - 20 * U * sz, -0.6);
    typed(g, "HOW DOES A", x0, H * k(0.3, 0.47), 5 * U, { p: B.prog(lt, 0.1, 0.25) });
    ransom(g, "SPEAKER", x0, H * k(0.43, 0.535), k(11, 10) * U, 21, { n: count(lt, 0.25) });
    typed(g, "MAKE", x0, H * k(0.56, 0.605), 5 * U, { p: B.prog(lt, 0.85, 0.1) });
    const r = ransom(g, "NOISE?", x0, H * k(0.7, 0.68), k(13, 12) * U, 22, { n: count(lt, 0.95) });
    scrawlArrow(g, P ? [[r.l + r.w + 1.5 * U, H * 0.675], [W * 0.88, H * 0.56], [sc[0] + 12 * U * sz, sc[1] + 25 * U * sz]] : [[r.l + r.w + 3 * U, H * 0.7], [sc[0] - 12 * U, H * 0.68], [sc[0] - 14 * U, sc[1] + 24 * U * sz]], B.prog(lt, 1.15, 0.3), 23);
  }

  function shotDiagram(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H, k = F.pick;
    ransom(g, "INSIDE", S.x + 3 * U, S.y + 9 * U, 8 * U, 41, { n: count(lt, 0.05) });
    const cx = k(W * 0.48, W * 0.5), cy = k(H * 0.54, H * 0.52), map = placeX(g, sectionCut(), cx, cy, k(1.05, 1), k(0.015, -Math.PI / 2 + 0.02));
    const [mx, my] = map(...PARTS.magnet), [qx, qy] = map(...PARTS.coil), [nx, ny] = map(...PARTS.cone), [ax, ay] = map(...PARTS.mouth);
    if (lt > 0.5) spotBlock(g, qx, qy, 11 * U, 11 * U, 0, 42, true);
    label(g, "MAGNET", k(S.x + 16 * U, S.x + 13 * U), k(H * 0.4, H * 0.75), mx, my, lt, 0.35, 43);
    label(g, "COIL", k(qx - 4 * U, S.r - 12 * U), k(H * 0.82, H * 0.62), qx, qy, lt, 0.55, 44);
    label(g, "CONE", k(nx + 14 * U, S.x + 11 * U), k(S.y + 9 * U, H * 0.37), nx, ny, lt, 0.75, 45);
    const air = P ? [[ax, ay - 2 * U], [ax + 1 * U, ay - 9 * U]] : [[ax + 3 * U, ay], [ax + 16 * U, ay - 1 * U]];
    scrawlArrow(g, air, B.prog(lt, 0.95, 0.25), 46);
    ransom(g, "AIR", P ? ax + 8 * U : ax + 19 * U, P ? ay - 8 * U : ay, 7 * U, 47, { n: count(lt, 1.2) });
  }

  function shotNumber(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H, k = F.pick, cx = W / 2;
    typed(g, "YOUR EARS TOP OUT AT", cx, H * k(0.22, 0.36), 5 * U, { align: "center", p: B.prog(lt, 0, 0.3) });
    spotBlock(g, cx, H * k(0.45, 0.46), k(120, 88) * U, k(30, 32) * U, -0.03, 51);
    ransom(g, "20,000", cx, H * k(0.45, 0.46), k(18, 13) * U, 52, { n: count(lt, 0.2), align: "center" });
    const y2 = H * k(0.65, 0.565);
    typed(g, "WOBBLES A SECOND", cx, y2, 5.5 * U, { align: "center", p: B.prog(lt, 0.8, 0.2) });
    scrawl(g, [[cx - 25 * U, y2 + 4 * U], [cx, y2 + 4.6 * U], [cx + 25 * U, y2 + 3.6 * U]], B.prog(lt, 1.1, 0.2), 1.1, 53);
    typed(g, "(20,000 Hz: the highest pitch most young ears can hear)", cx, y2 + 9 * U, 4.2 * U, { align: "center", maxW: k(120, 76) * U, p: B.prog(lt, 1.15, 0.4) });
    safetyPin(g, k(W * 0.8, W * 0.76), H * k(0.25, 0.235), 0.4, 13 * U);
    if (P) {
      placeX(g, frontCut(), W * 0.27, H * 0.765, 0.55, -0.12);
      staple(g, W * 0.27, H * 0.765 - 12 * U, 0.3);
    }
  }

  /** A step: a white snipped sheet, stapled, with a ransom header, a visual and typewriter lines. */
  function stepSheet(g, F, x, y, w, h, head, text, lt, at, seed, visual) {
    if (lt < at) return;
    const P = F.portrait;
    g.save();
    g.translate(x, y);
    g.rotate((B.hash01(seed, 2) - 0.5) * 0.05);
    scrap(g, snip(w, h, seed, 1.2), PAL.white);
    staple(g, 0, -h / 2 + 1.2 * U, 0.05);
    ransom(g, head, -w / 2 + 4 * U, -h / 2 + 7.5 * U, 6 * U, seed + 1, { n: count(lt, at + 0.1) });
    visual(P ? -w / 2 + 15 * U : 0, P ? 7 * U : -1 * U);
    typed(g, text, P ? -w / 2 + 30 * U : -w / 2 + 4 * U, P ? -h / 2 + 15 * U : h / 2 - 14 * U, 4.2 * U, { maxW: P ? w - 33 * U : w - 8 * U, p: B.prog(lt, at + 0.3, 0.5), seed });
    g.restore();
  }

  function shotSteps(g, F, lt) {
    const P = F.portrait, W = F.W, H = F.H, k = F.pick, w = k(76, 84) * U, h = k(68, 42) * U;
    stepSheet(g, F, k(W * 0.27, W * 0.5), H * k(0.54, 0.31), w, h, "1 CURRENT IN", "Music arrives as a wiggling current. The coil turns into a magnet.", lt, 0, 61, (vx, vy) => {
      placeX(g, coilCut(), vx, vy, 0.85, 0.04);
      const pts = [];
      for (let i = 0; i <= 16; i++) pts.push([vx - 14 * U + i * 0.7 * U, vy + 11 * U + Math.sin(i * 1.3 + B.boil(T, FPS)) * 1.2 * U]);
      scrawl(g, pts, B.prog(lt, 0.5, 0.3), 0.8, 62);
    });
    stepSheet(g, F, k(W * 0.73, W * 0.5), H * k(0.54, 0.585), w, h, "2 PUSH-PULL", "The big magnet pushes and pulls the coil: in, out, in, out.", lt, 0.75, 71, (vx, vy) => {
      const map = placeX(g, sectionCut(), vx, vy, P ? 0.32 : 0.38, 0.02), [qx, qy] = map(...PARTS.coil);
      const p = B.prog(lt, 1.15, 0.25);
      scrawlArrow(g, [[qx - 2 * U, qy - 6 * U], [qx + 7 * U, qy - 6 * U]], p, 72);
      scrawlArrow(g, [[qx + 7 * U, qy - 9 * U], [qx - 2 * U, qy - 9 * U]], B.prog(lt, 1.3, 0.25), 73);
    });
  }

  function shotAir(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H, k = F.pick;
    const sc = k([W * 0.25, H * 0.52], [W * 0.44, H * 0.36]), pulse = 1 + 0.035 * (B.boil(T, FPS) % 2);
    placeX(g, frontCut(), sc[0], sc[1], k(1.15, 0.92) * pulse, -0.04);
    for (let i = 0; i < 3; i++) {
      const R = (k(33, 30) + i * 5) * U;
      scrawl(g, B.arcPts(sc[0], sc[1], R, -0.55, 0.55, 18), B.prog(lt, 0.4 + i * 0.15, 0.2), 1.0, 81 + i);
    }
    const x = k(W * 0.53, S.x + 3 * U), y = H * k(0.3, 0.6);
    ransom(g, "3 PUSH AIR", x, y, k(7, 7.5) * U, 84, { n: count(lt, 0.1) });
    typed(g, "The cone shoves the air back and forth. Those pressure waves hit your ears: that's sound.", x, y + 9 * U, 4.2 * U, { maxW: k(70, 82) * U, p: B.prog(lt, 0.6, 0.6), seed: 85 });
  }

  function shotClose(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H, k = F.pick, x0 = S.x + 4 * U;
    issue(g, F, lt);
    spotBlock(g, k(W * 0.3, W * 0.5), H * k(0.47, 0.47), k(84, 84) * U, k(40, 40) * U, 0.05, 91);
    const sc = k([W * 0.76, H * 0.47], [W * 0.73, H * 0.25]), sz = k(0.95, 0.6);
    placeX(g, frontCut(), sc[0], sc[1], sz, -0.08);
    safetyPin(g, sc[0] - 4 * U, sc[1] - 25 * U * sz, -0.2, 12 * U);
    ransom(g, "MAKE", k(W * 0.29, W * 0.5), H * k(0.38, 0.42), 12 * U, 92, { n: count(lt, 0.1), align: "center" });
    ransom(g, "NOISE!", k(W * 0.31, W * 0.5), H * k(0.56, 0.52), 14 * U, 93, { n: count(lt, 0.4), align: "center" });
    const ty = H * k(0.72, 0.65);
    typed(g, "It's magic.", x0, ty, 5.5 * U, { p: B.prog(lt, 0.6, 0.15), seed: 94 });
    g.font = B.font(5.5 * U, TYPE, 400);
    const a = g.measureText("It's ").width, b = g.measureText("It's magic").width;
    crossOut(g, x0 + a - U, x0 + b + U, ty, 5.5 * U, B.prog(lt, 0.85, 0.15), 95);
    scrawlText(g, "just air, pushed fast!", x0, ty + k(9, 10) * U, 4.4 * U, B.prog(lt, 1.0, 0.4));
  }

  const SHOTS = [shotTitle, shotDiagram, shotNumber, shotSteps, shotAir, shotClose];

  // ------------------------------------------------------------------ the copier: page, toner, glass, sweeps
  /** Toner specks: three cached variants, swapped each held frame (clusters, dots, a few hairs). */
  function specks(W, H, v) {
    return B.layer(`pz-specks:${v}`, W, H, (g, w, h) => {
      const r = B.rng(300 + v), n = Math.round(((w * h) / (U * U)) * 0.012);
      g.fillStyle = PAL.ink;
      for (let i = 0; i < n; i++) {
        g.globalAlpha = r.range(0.35, 0.95);
        g.beginPath();
        B.circle(g, r() * w, r() * h, r() < 0.92 ? r.range(0.06, 0.16) * U : r.range(0.25, 0.55) * U);
        g.fill();
      }
      for (let c = 0; c < 3; c++) {
        const cx = r() * w, cy = r() * h;
        for (let i = 0; i < 40; i++) {
          g.beginPath();
          B.circle(g, cx + r.gauss(0, 2.5) * U, cy + r.gauss(0, 2.5) * U, r.range(0.05, 0.15) * U);
          g.fill();
        }
      }
    });
  }
  /** Copier glass: grey shadow bands at the page edges, two drum streaks, a faint band across. */
  function haze(W, H) {
    return B.layer("pz-haze", W, H, (g, w, h) => {
      const e = 9 * U;
      g.fillStyle = B.linear(g, 0, 0, e, 0, ["rgba(18,18,18,0.55)", "rgba(18,18,18,0)"]);
      g.fillRect(0, 0, e, h);
      g.fillStyle = B.linear(g, w, 0, w - e, 0, ["rgba(18,18,18,0.6)", "rgba(18,18,18,0)"]);
      g.fillRect(w - e, 0, e, h);
      g.fillStyle = B.linear(g, 0, h, 0, h - e * 0.6, ["rgba(18,18,18,0.35)", "rgba(18,18,18,0)"]);
      g.fillRect(0, h - e, w, e);
      g.fillStyle = "rgba(18,18,18,0.16)";
      g.fillRect(w * 0.13, 0, 0.25 * U, h);
      g.fillRect(w * 0.87, 0, 0.18 * U, h);
      g.fillStyle = "rgba(18,18,18,0.04)";
      g.fillRect(0, h * 0.61, w, 6 * U);
    });
  }
  function renderPage(key, i, F, tq) {
    const W = F.W, H = F.H, g = B.scratch(key, W, H);
    SP = B.scratch(key + "-spot", W, H);
    g.fillStyle = PAL.paper;
    g.fillRect(0, 0, W, H);
    SHOTS[i](g, F, tq - BEATS[i]);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.drawImage(specks(W, H, B.boil(tq, FPS) % 3), 0, 0);
    g.drawImage(haze(W, H), 0, 0);
    g.globalCompositeOperation = "multiply"; // the spot plate overprints, a little off register
    g.drawImage(SP.canvas, 1.3 * U, -0.9 * U);
    g.globalCompositeOperation = "source-over";
    return g.canvas;
  }
  /** Each held frame the copy lands a hair differently; a jump cut re-frames the page abruptly. */
  function placePage(ctx, page, F, i, tq) {
    const f = B.boil(tq, FPS), j = tq - BEATS[i] >= JUMPS[i] ? 1 : 0;
    const dx = (hh(f, 1, 7) - 0.5) * 0.5 * U + j * (hh(i, 2, 8) - 0.5) * 4 * U, dy = (hh(f, 2, 7) - 0.5) * 0.5 * U + j * (hh(i, 3, 8) - 0.5) * 3 * U;
    const z = 1 + j * 0.03, rot = (hh(f, 3, 7) - 0.5) * 0.004 + j * (hh(i, 4, 8) - 0.5) * 0.016;
    ctx.save();
    ctx.translate(F.W / 2 + dx, F.H / 2 + dy);
    ctx.rotate(rot);
    ctx.scale(z, z);
    ctx.drawImage(page, -F.W / 2, -F.H / 2);
    ctx.restore();
  }
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H), tq = B.stepTime(t, FPS), i = B.beat(tq, BEATS, DUR).i;
    U = F.u;
    T = tq;
    ctx.fillStyle = PAL.glass;
    ctx.fillRect(0, 0, W, H);
    if (!SWEEP[i] && tq - BEATS[i] < 0.1) {
      // a one-frame black copy (lid up) between shots
      ctx.fillStyle = PAL.ink;
      ctx.fillRect(0, 0, W, H);
      B.grain(ctx, W, H, { amount: 0.25, t, fps: FPS, mode: "screen" });
      return;
    }
    placePage(ctx, renderPage("pz-a", i, F, tq), F, i, tq);
    const ls = t - BEATS[i];
    if (SWEEP[i] && ls < 0.42) {
      // the copier light bar: the new page is behind it, the old page (or bare glass) ahead of it
      const p = B.ease.inOutSine(ls / 0.42), V = F.portrait, D = V ? H : W, bar = 10 * U, pos = p * (D + 2 * bar) - bar;
      ctx.save();
      ctx.beginPath();
      if (V) ctx.rect(0, pos, W, H);
      else ctx.rect(pos, 0, W, H);
      ctx.clip();
      ctx.fillStyle = PAL.glass;
      ctx.fillRect(0, 0, W, H);
      if (i > 0) placePage(ctx, renderPage("pz-b", i - 1, F, BEATS[i] - 0.1), F, i - 1, BEATS[i] - 0.1);
      ctx.restore();
      const gr = V ? B.linear(ctx, 0, pos - bar, 0, pos + bar, ["rgba(236,255,236,0)", "rgba(244,255,240,0.95)", "rgba(236,255,236,0)"])
        : B.linear(ctx, pos - bar, 0, pos + bar, 0, ["rgba(236,255,236,0)", "rgba(244,255,240,0.95)", "rgba(236,255,236,0)"]);
      ctx.fillStyle = gr;
      if (V) ctx.fillRect(0, pos - bar, W, 2 * bar);
      else ctx.fillRect(pos - bar, 0, 2 * bar, H);
    }
    B.grain(ctx, W, H, { amount: 0.06, t: tq, fps: FPS, mode: "overlay" });
  }

  // ------------------------------------------------------------------ sound: copier, stapler, snips, drums, stabs, marker
  SOUND.define("pz-whirr", (v, o) => {
    // copier pass: a motor hum, a rushing scan and a clunk at the end
    const d = o.dur ?? 0.45;
    v.tone({ type: "square", f: 98, a: 0.02, hold: d, len: 0.05, peak: 0.05 });
    v.noise({ filter: "bandpass", f: 900, f2: 1600, glide: d, q: 1.6, a: 0.04, hold: d * 0.8, len: 0.08, peak: 0.28 });
    v.tone({ f: 140, f2: 60, glide: 0.05, at: d, a: 0.001, len: 0.08, peak: 0.25 });
  }, { verb: 0.1 });
  SOUND.define("pz-staple", (v) => {
    v.noise({ filter: "highpass", f: 3000, a: 0.0005, len: 0.025, peak: 0.5 });
    v.tone({ f: 220, f2: 90, glide: 0.05, at: 0.01, a: 0.001, len: 0.07, peak: 0.45 });
  }, { verb: 0.08 });
  SOUND.define("pz-snip", (v) => {
    for (const at of [0, 0.06]) v.noise({ filter: "bandpass", f: 5200, q: 6, at, a: 0.0005, len: 0.03, peak: 0.35 });
  }, { verb: 0.05 });
  SOUND.define("pz-kick", (v) => {
    v.tone({ f: 150, f2: 42, glide: 0.09, a: 0.001, len: 0.18, peak: 0.7 });
    v.noise({ filter: "lowpass", f: 900, a: 0.001, len: 0.04, peak: 0.25 });
  }, { verb: 0.05 });
  SOUND.define("pz-snare", (v) => {
    v.noise({ filter: "bandpass", f: 1900, q: 0.7, a: 0.001, len: 0.13, peak: 0.45 });
    v.tone({ type: "square", f: 210, f2: 160, glide: 0.04, a: 0.001, len: 0.05, peak: 0.12 });
  }, { verb: 0.12 });
  SOUND.define("pz-stab", (v, o) => {
    // a scratchy power-chord stab: detuned saws a fifth apart, plus pick noise
    const r = v.hz(o.note || "E2");
    for (const m of [1, 1.5, 2]) v.tone({ type: "sawtooth", f: r * m, detune: 9, a: 0.004, hold: 0.12, len: 0.18, peak: 0.08 });
    v.noise({ filter: "bandpass", f: 2600, q: 1.2, a: 0.001, len: 0.05, peak: 0.25 });
  }, { verb: 0.15 });

  function score(k) {
    k.bed("hum", 0, DUR, { gain: 0.25 });
    // a raw drum loop: kick and snare on a fast backbeat
    k.repeat(0, 0.8, 15, "pz-kick", { gain: 0.6 }).repeat(0.4, 0.8, 15, "pz-snare", { gain: 0.45 }).repeat(0.6, 0.8, 15, "pz-kick", { gain: 0.35 });
    // copier passes and black copies between shots
    [0, 1, 3, 5].forEach((i) => k.at(BEATS[i], "pz-whirr", { dur: 0.42, gain: 0.8 }));
    [2, 4].forEach((i) => k.at(BEATS[i], "impact", { gain: 0.6 }).at(BEATS[i] + 0.1, "pz-stab", { note: "A2" }));
    // stabs on the big words, staples and pins, snips for the ransom letters
    [[0.3, "E2"], [1.0, "G2"], [4.2, "E2"], [8.5, "D2"], [10.4, "E2"], [10.7, "G2"]].forEach(([at, n]) => k.at(at, "pz-stab", { note: n, gain: 0.8 }));
    k.at(0.15, "pz-staple").at(6.25, "pz-staple").at(6.95, "pz-staple").at(5.2, "click").at(10.35, "click");
    k.repeat(0.25, 0.2, 6, "pz-snip", { gain: 0.45, vary: 2 }).repeat(1.95, 0.2, 3, "pz-snip", { gain: 0.4 }).repeat(4.2, 0.2, 3, "pz-snip", { gain: 0.45 });
    k.repeat(10.4, 0.2, 4, "pz-snip", { gain: 0.45 });
    // typewriter strikes and marker squeaks
    [[0.1, 4], [4.0, 6], [6.5, 8], [7.4, 8], [9.0, 10], [10.9, 3]].forEach(([at, n]) => k.repeat(at, 0.07, n, "type", { gain: 0.5, vary: 2 }));
    [[2.35, 0.3], [2.55, 0.3], [2.75, 0.3], [2.9, 0.25], [5.1, 0.2], [6.7, 0.3], [7.5, 0.25], [8.8, 0.5], [11.15, 0.2], [11.3, 0.4]].forEach(([at, d]) => k.at(at, "marker", { dur: d, gain: 0.6 }));
  }

  Player.register({
    id: "punk-zine",
    name: "Punk Zine Collage",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Archivo+Black&family=Abril+Fatface&family=Special+Elite&family=Bungee&family=Rock+Salt&display=swap",
      faces: ['400 20px "Archivo Black"', '400 20px "Abril Fatface"', '400 20px "Special Elite"', '400 20px "Bungee"', '400 20px "Rock Salt"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.6, 3.6, 5.8, 8.0, 10.0, 11.7],
    draw,
    score,
  });
})();
