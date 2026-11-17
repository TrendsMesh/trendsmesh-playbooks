/* 40 Editorial Collage - reference animation.
 * Topic (setting, replace it): "How does a hot air balloon fly?" - heat the air, hot air is lighter, open the vent to sink.
 * Rendering (keep it): grainy cream paper; "archival" halftone cut-outs (ink dot screen + one duotone screen, torn white
 * border, drop shadow); condensed caps slogans on torn black or red strips; yellow round and starburst stickers; sticky
 * notes and masking tape; a mono HUD label; italic serif asides; red marker underlines, rings and arrows.
 * Motion: shots joined by smeared whip pans and punch-in cuts; slams with a shake; cut-outs jitter on twelve.
 */
(function () {
  "use strict"; const B = window.Brush;

  // ------------------------------------------------------------------ brand (palette and display type)
  // BRAND: the default look. The channel's or brand's own colours and display font replace these when given.
  const BRAND = {
    ink: "#1a1816", accent: "#b8483a", paper: "#f0e9d9", kraft: "#c9a878", card: "#f5f1e7",
    highlight: "#ffe14a", // stickers
    notes: { yellow: "#f2d24b", teal: "#1f9e94", pink: "#ff4f8b" },
    display: "Anton", mono: "DM Mono", serif: "Libre Baskerville",
  };
  const TAPE = "#eee4c0"; const DUR = 12, BEATS = [0, 1.9, 4.0, 6.2, 8.4, 10.3];
  const CUTS = { 1: "whip-x", 2: "punch", 3: "whip-y", 4: "punch", 5: "whip-x" };   // how each shot is entered
  const WHIP = 0.34; const HUD_LABEL = "HOW THINGS FLY · EP 4";
  // slams [time, shake in U]: every hard landing nudges the frame
  const SLAMS = [[0.05, 0.7], [0.3, 0.5], [0.45, 0.7], [0.62, 1.1], [0.9, 0.4], [2.05, 0.8], [4.0, 1.4], [4.12, 0.5], [4.22, 0.5], [4.32, 0.5],
    [4.42, 0.9], [4.85, 0.7], [6.32, 0.7], [6.9, 0.9], [8.4, 1.2], [8.65, 0.8], [10.45, 0.8], [10.65, 1.1], [11.05, 0.5]];

  let U = 1, T = 0;

  // ------------------------------------------------------------------ motion helpers
  /** Slam: appears big and lands with a short rebound in about 0.15 s. 0 before `at`. */
  function slam(lt, at) {
    const d = lt - at;
    if (d < 0) return 0;
    if (d < 0.11) return B.lerp(1.6, 1, B.ease.inQuad(d / 0.11));
    return 1 - 0.045 * Math.exp(-16 * (d - 0.11)) * Math.sin(32 * (d - 0.11));
  }
  /** Stop-motion jitter: a fresh tiny offset and tilt twelve times a second, per piece. [dx, dy, rot] */
  function jit(id, amt = 1) {
    const f = B.boil(T, 12);
    return [(B.hash01(f, id, 1) - 0.5) * 0.4 * U * amt, (B.hash01(f, id, 2) - 0.5) * 0.4 * U * amt, (B.hash01(f, id, 3) - 0.5) * 0.008 * amt];
  }

  // ------------------------------------------------------------------ paper craft helpers (reuse these)
  const shadow = (g, a, blur, x, y) => {
    g.shadowColor = `rgba(44,30,16,${a})`; g.shadowBlur = blur * U; g.shadowOffsetX = x * U; g.shadowOffsetY = y * U;
  };
  /** A torn edge from a to b: slow wander plus fine fibrous teeth, as polygon points (b excluded). */
  function tornEdge(ax, ay, bx, by, seed, amp) {
    const L = Math.hypot(bx - ax, by - ay) || 1, n = Math.max(2, Math.round(L / (0.55 * U)));
    const nx = -(by - ay) / L, ny = (bx - ax) / L, r = B.rng(seed), out = [];
    for (let i = 0; i < n; i++) {
      const k = i / n, w = B.noise1((k * L) / (5 * U), seed) * amp * 0.7 + (r() - 0.5) * amp * 0.7;
      out.push([ax + (bx - ax) * k + nx * w, ay + (by - ay) * k + ny * w]);
    }
    return out;
  }
  /** Torn sheet centred on 0,0; tear = tear depth per edge [top, right, bottom, left] in U. */
  function tornRect(w, h, seed, tear = [0.6, 0.25, 0.6, 0.25]) {
    const x0 = -w / 2, y0 = -h / 2, x1 = w / 2, y1 = h / 2;
    return [].concat(tornEdge(x0, y0, x1, y0, seed, tear[0] * U), tornEdge(x1, y0, x1, y1, seed + 1, tear[1] * U),
      tornEdge(x1, y1, x0, y1, seed + 2, tear[2] * U), tornEdge(x0, y1, x0, y0, seed + 3, tear[3] * U));
  }
  /** Fill a paper polygon with a soft drop shadow and a pale fibrous rim where it was torn. */
  function sheet(g, pts, fill, o = {}) {
    g.save(); shadow(g, o.shadow ?? 0.32, o.blur ?? 1.6, o.sx ?? 0.45, o.sy ?? 0.8); g.beginPath(); B.poly(g, pts, true);
    g.fillStyle = fill; g.fill(); g.restore();
    if (o.rim !== false) {
      g.save(); g.beginPath(); B.poly(g, pts, true); g.strokeStyle = "rgba(255,250,238,0.32)"; g.lineWidth = 0.3 * U;
      g.stroke(); g.restore();
    }
  }
  /** Slogan on a torn strip (cream caps on black or red). x = left edge if o.align "left", else centre. Returns its box. */
  function strip(g, text, x, y, o) {
    const size = o.size, s = o.s ?? 1; g.font = B.font(size, BRAND.display, 400);
    const tw = g.measureText(text).width, w = tw + size * 0.7, h = size * 1.3;
    const cx = o.align === "left" ? x + w / 2 : x;
    if (s > 0) {
      g.save(); g.translate(cx, y); g.rotate(o.rot || 0); g.scale(s, s);
      sheet(g, tornRect(w, h, o.seed || 7, [0.75, 0.2, 0.75, 0.2]), o.fill || BRAND.ink, { shadow: 0.36 });
      g.font = B.font(size, BRAND.display, 400); g.textAlign = "center"; g.textBaseline = "middle";
      g.fillStyle = o.color || BRAND.card; g.fillText(text, 0, size * 0.03); g.restore();
    }
    return { w, h, l: cx - w / 2, r: cx + w / 2, t: y - h / 2, b: y + h / 2 };
  }
  /** Big condensed caps printed straight on the paper in ink (no strip). */
  function headline(g, text, x, y, size, s, o = {}) {
    if (s <= 0) return;
    g.save(); g.translate(x, y); g.rotate(o.rot || 0); g.scale(s, s); g.font = B.font(size, BRAND.display, 400);
    g.textAlign = o.align || "left"; g.textBaseline = "middle"; g.fillStyle = o.color || BRAND.ink;
    g.fillText(text, 0, 0); g.restore();
  }
  /** Italic serif aside (quotes, small explanations), written on by characters. */
  function aside(g, text, x, y, o) {
    const p = o.p ?? 1;
    if (p <= 0) return null;
    return B.text(g, text, x, y, { size: o.size ?? 4.2 * U, minSize: 3.9 * U, family: BRAND.serif, weight: 400, style: "italic", color: BRAND.ink,
      align: o.align || "left", baseline: "top", maxW: o.maxW, lineH: 1.32, reveal: p });
  }
  /** Masking tape: a translucent pale strip with zigzag torn ends. */
  function tape(g, x, y, w, h, rot, seed, s = 1) {
    if (s <= 0) return;
    const r = B.rng(seed), pts = [], n = 5;
    for (let i = 0; i <= n; i++) pts.push([w / 2 + (i % 2 ? -0.5 : 0.3) * U * r.range(0.5, 1.2), -h / 2 + (h * i) / n]);
    for (let i = 0; i <= n; i++) pts.push([-w / 2 + (i % 2 ? 0.5 : -0.3) * U * r.range(0.5, 1.2), h / 2 - (h * i) / n]);
    g.save(); g.translate(x, y); g.rotate(rot); g.scale(s, s); shadow(g, 0.14, 0.5, 0, 0.2);
    g.beginPath(); B.poly(g, pts, true); g.fillStyle = B.rgba(TAPE, 0.8); g.fill(); g.restore();
  }
  /** Sticky note: flat colour square, soft shadow, the lower corner lifting and fluttering (stepped). */
  function note(g, x, y, w, h, color, rot, o = {}) {
    const lift = Math.min(w, h) * (0.07 + 0.05 * Math.sin(B.stepTime(T, 12) * 5.1 + (o.seed || 0)));
    g.save(); g.translate(x, y); g.rotate(rot); g.scale(o.s ?? 1, o.s ?? 1); g.save(); shadow(g, 0.26, 1.4, 0.4, 0.9);
    g.beginPath();
    B.poly(g, [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2 - lift], [w / 2 - lift, h / 2], [-w / 2, h / 2]], true);
    g.fillStyle = color; g.fill(); g.restore(); g.beginPath();
    B.poly(g, [[w / 2, h / 2 - lift], [w / 2 - lift, h / 2], [w / 2 - lift * 1.15, h / 2 - lift * 1.15]], true);
    g.fillStyle = B.shade(color, 0.28); g.fill();
    if (o.text) aside(g, o.text, 0, -h * 0.34, { size: o.size, maxW: w * 0.84, align: "center", p: o.p });
    g.restore();
  }
  /** Round or starburst sticker in highlight yellow with condensed caps. lines: [[text, sizeInU], ...] */
  function sticker(g, x, y, r, lines, o = {}) {
    const s = o.s ?? 1;
    if (s <= 0) return;
    const [jx, jy, jr] = jit(o.id || 5, 0.6); g.save(); g.translate(x + jx, y + jy); g.rotate((o.rot || 0) + jr);
    g.scale(s, s); g.save(); shadow(g, 0.3, 1.2, 0.35, 0.7); g.beginPath();
    if (o.star) B.star(g, 0, 0, o.points || 16, r, r * 0.84, 0);
    else B.circle(g, 0, 0, r); g.fillStyle = o.fill || BRAND.highlight; g.fill(); g.restore();
    if (!o.star) {
      g.beginPath(); B.circle(g, 0, 0, r * 0.86); g.strokeStyle = B.rgba(BRAND.ink, 0.18); g.lineWidth = 0.25 * U;
      g.stroke();
    }
    const total = lines.reduce((a, l) => a + l[1] * U * 1.02, 0); let yy = -total / 2; g.textAlign = "center";
    g.textBaseline = "middle"; g.fillStyle = BRAND.ink;
    for (const [txt, sz] of lines) {
      g.font = B.font(sz * U, BRAND.display, 400); g.fillText(txt, 0, yy + sz * U * 0.53); yy += sz * U * 1.02;
    }
    g.restore();
  }
  /** Red marker stroke, drawn on as p goes 0 -> 1 (multiplied, so it soaks into the paper). */
  function marker(g, pts, p, w = 1.1, seed = 3) {
    if (p <= 0) return;
    g.save(); g.globalCompositeOperation = "multiply"; g.globalAlpha = 0.92;
    B.taperStroke(g, pts, { width: w * U, color: BRAND.accent, p, taperIn: 0.04, taperOut: 0.12, rough: 0.3, roughScale: 6, seed });
    g.restore();
  }
  /** Marker ring around something: a loose ellipse that overshoots its start. */
  function markerRing(g, cx, cy, rx, ry, p, seed = 4) {
    const pts = [];
    for (let i = 0; i <= 90; i++) {
      const k = i / 90, a = -2.3 + k * B.TAU * 1.1, rr = 1 + 0.05 * B.noise1(k * 4, seed) + k * 0.07;
      pts.push([cx + Math.cos(a) * rx * rr, cy + Math.sin(a) * ry * rr]);
    }
    marker(g, pts, p, 1.0, seed);
  }
  /** Marker arrow with an open head. */
  function markerArrow(g, pts, p, seed = 5) {
    if (p <= 0) return;
    g.save(); g.globalCompositeOperation = "multiply";
    B.arrow(g, pts, { p, width: 1.05 * U, color: BRAND.accent, head: 3.4 * U, headStyle: "open", rough: 0.35 * U, seed });
    g.restore();
  }
  /** Mono HUD label (series and episode) on black tape at the top of the safe area. */
  function hud(g, F) {
    const S = F.safe, size = 3.9 * U; g.save(); g.font = B.font(size, BRAND.mono, 500);
    g.letterSpacing = (0.12 * size).toFixed(1) + "px";
    const tw = g.measureText(HUD_LABEL).width, h = size * 1.65, w = tw + size * 1.1;
    g.translate(S.x, S.y + 0.6 * U); g.rotate(-0.008);
    sheet(g, [[0, 0], [w, 0], [w, h], [0, h]], BRAND.ink, { shadow: 0.2, blur: 0.6, sx: 0.2, sy: 0.4, rim: false });
    g.fillStyle = BRAND.card; g.textAlign = "left"; g.textBaseline = "middle";
    g.fillText(HUD_LABEL, size * 0.55, h / 2 + size * 0.04);
    g.beginPath(); B.circle(g, w + 2 * U, h / 2, 0.9 * U); // blinking red "on air" dot
    g.fillStyle = Math.floor(T * 2) % 2 ? B.rgba(BRAND.accent, 0.3) : BRAND.accent; g.fill(); g.restore();
  }

  // ------------------------------------------------------------------ archival halftone cut-outs (reuse these)
  // A subject is painted once as a tone map: red channel = ink tone, green channel = duotone tone, alpha = coverage.
  const TN = (ink, col = 0, a = 1) => `rgba(${Math.round(ink * 255)},${Math.round(col * 255)},0,${a})`;
  /**
   * Bake a cut-out (cached): the tone map becomes an ink screen at 45 deg plus a duotone screen at 15 deg a hair off
   * register, inside a torn white scissor cut around the subject. o: { duo, margin (U), cell (U), cx, cy (ray centre), seed }
   */
  function cutout(key, w, h, paint, o = {}) {
    const pad = Math.round(Math.max(w, h) * 0.1);
    const canvas = B.layer(`ec-cut:${key}:${o.duo}`, w + 2 * pad, h + 2 * pad, (g, cw, ch) => {
      const mg = B.canvas(cw, ch).getContext("2d"); mg.translate(pad, pad); paint(mg, w, h);
      const d = mg.getImageData(0, 0, cw, ch).data;
      const px = (x, y, c) => {
        x |= 0; y |= 0;
        return x < 0 || y < 0 || x >= cw || y >= ch ? 0 : d[(y * cw + x) * 4 + c];
      };
      // scissor line: each ray marches in to the first covered pixel, then widens over its neighbours
      const ox = pad + w * (o.cx ?? 0.5), oy = pad + h * (o.cy ?? 0.5), N = 160, rmax = Math.hypot(cw, ch) / 2, rad = [];
      for (let i = 0; i < N; i++) {
        const a = (i / N) * B.TAU, ca = Math.cos(a), sa = Math.sin(a); let r = rmax;
        for (; r > 0; r -= 1.5) if (px(ox + ca * r, oy + sa * r, 3) > 70) break;
        rad.push(r);
      }
      const sm = rad.map((_, i) => {
        let m = 0;
        for (let k = -4; k <= 4; k++) m = Math.max(m, rad[(i + k + N) % N] * (1 - Math.abs(k) * 0.018));
        return m;
      });
      const rr = B.rng(o.seed || 9), cut = [], M = N * 3, margin = (o.margin ?? 1.5) * U;
      for (let i = 0; i < M; i++) {
        const f = (i / M) * N, i0 = Math.floor(f) % N, i1 = (i0 + 1) % N, k = f - Math.floor(f);
        const a = (i / M) * B.TAU, r = B.lerp(sm[i0], sm[i1], k) + margin * (1 + 0.35 * B.noise1(i * 0.04, o.seed || 9)) + (rr() - 0.5) * 0.45 * U;
        cut.push([ox + Math.cos(a) * r, oy + Math.sin(a) * r]);
      }
      // white card with a fibre fringe and a soft drop shadow
      g.save(); g.beginPath(); B.poly(g, cut.map(([x, y]) => [ox + (x - ox) * 1.012, oy + (y - oy) * 1.012]), true);
      g.fillStyle = "rgba(255,252,244,0.55)"; g.fill(); shadow(g, 0.38, 1.8, 0.6, 1.1); g.beginPath(); B.poly(g, cut, true);
      g.fillStyle = BRAND.card; g.fill(); g.restore();
      // two screens, clipped to the cut: the duotone first (slightly off register), the ink multiplied over it
      const cell = (o.cell ?? 0.78) * U, A = (x, y) => px(x, y, 3) / 255;
      B.clip(g, (c) => B.poly(c, cut, true), (c) => {
        if (o.duo) {
          c.save(); c.translate(0.3 * U, -0.25 * U);
          B.halftone(c, 0, 0, cw, ch, { cell: cell * 1.05, angle: 15, color: o.duo, tone: (x, y) => (px(x, y, 1) / 255) * A(x, y) * 0.92 });
          c.restore();
        }
        c.globalCompositeOperation = "multiply";
        B.halftone(c, 0, 0, cw, ch, { cell, angle: 45, color: BRAND.ink, tone: (x, y) => (px(x, y, 0) / 255) * A(x, y) });
      });
    });
    return { canvas, pad, w, h };
  }
  /** Place a cut-out with its subject centred at (cx, cy), scale k, tilt rot, stop-motion jitter; returns a mapper. */
  function placeCut(g, cut, cx, cy, k, rot, id, s = 1) {
    const [jx, jy, jr] = jit(id); const sc = k * s, a = rot + jr;
    if (sc > 0) {
      g.save(); g.translate(cx + jx, cy + jy); g.rotate(a); g.scale(sc, sc);
      g.drawImage(cut.canvas, -cut.pad - cut.w / 2, -cut.pad - cut.h / 2); g.restore();
    }
    return (fx, fy) => {
      const x = (fx - 0.5) * cut.w * k, y = (fy - 0.5) * cut.h * k;
      return [cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)];
    };
  }

  // ------------------------------------------------------------------ subjects (the setting: replace these)
  function balloonGeo(w, h) {
    const R = Math.min(w * 0.47, h * 0.33), cx = w / 2, ey = R + h * 0.015, mouthY = ey + R * 1.18, mw = R * 0.26;
    const bw = w * 0.26, bh = h * 0.12, by = h - bh - h * 0.006, burnerY = by - h * 0.075;
    return { R, cx, ey, mouthY, mw, bw, bh, by, burnerY };
  }
  /** Half-width of the envelope at height y (matches the envelope path closely enough for gores). */
  function envHalf(G, y) {
    if (y <= G.ey) return Math.sqrt(Math.max(0, G.R * G.R - (y - G.ey) * (y - G.ey)));
    const k = B.clamp((y - G.ey) / (G.mouthY - G.ey));
    return G.mw + (G.R - G.mw) * (1 - Math.pow(k, 1.7));
  }
  /** Hot air balloon (modern striped, or o.ornate: the 1783 kind with bands and a gallery ring). */
  function paintBalloon(g, w, h, o = {}) {
    const G = balloonGeo(w, h), { R, cx, ey, mouthY, mw } = G;
    const env = () => {
      g.beginPath(); g.moveTo(cx - mw, mouthY);
      g.bezierCurveTo(cx - mw - R * 0.3, mouthY - R * 0.25, cx - R, ey + R * 0.6, cx - R, ey);
      g.arc(cx, ey, R, Math.PI, 0);
      g.bezierCurveTo(cx + R, ey + R * 0.6, cx + mw + R * 0.3, mouthY - R * 0.25, cx + mw, mouthY); g.closePath();
    };
    env();
    g.fillStyle = B.radial(g, cx - R * 0.42, ey - R * 0.45, 0, R * 1.9, [[0, TN(0.04)], [0.45, TN(0.36)], [1, TN(0.9)]]);
    g.fill(); g.save(); env(); g.clip();
    g.globalCompositeOperation = "lighter"; // duotone areas: add the green channel, keep the ink shading
    g.fillStyle = "rgba(0,215,0,1)";
    if (!o.ornate) {
      const F = [-1, -0.62, -0.22, 0.22, 0.62, 1];
      for (let b = 0; b < F.length - 1; b += 2) {
        const pts = [];
        for (let i = 0; i <= 24; i++) {
          const y = B.lerp(ey - R, mouthY, i / 24); pts.push([cx + F[b] * envHalf(G, y) * 1.02, y]);
        }
        for (let i = 24; i >= 0; i--) {
          const y = B.lerp(ey - R, mouthY, i / 24); pts.push([cx + F[b + 1] * envHalf(G, y) * 1.02, y]);
        }
        g.beginPath(); B.poly(g, pts, true); g.fill();
      }
    } else {
      for (const [yy, th] of [[ey - R * 0.55, 0.1], [ey - R * 0.05, 0.16], [ey + R * 0.55, 0.12]]) g.fillRect(cx - R * 1.1, yy, R * 2.2, R * th);
    }
    g.globalCompositeOperation = "source-over"; g.strokeStyle = TN(0.92); g.lineWidth = w * 0.014;
    const seams = o.ornate ? [-0.5, 0, 0.5] : [-0.62, -0.22, 0.22, 0.62];
    for (const f of seams) {
      g.beginPath();
      for (let i = 0; i <= 24; i++) {
        const y = B.lerp(ey - R, mouthY, i / 24);
        i ? g.lineTo(cx + f * envHalf(G, y), y) : g.moveTo(cx + f * envHalf(G, y), y);
      }
      g.stroke();
    }
    g.restore();
    // vent at the crown
    g.fillStyle = TN(0.75); g.beginPath(); g.ellipse(cx, ey - R * 0.93, R * 0.2, R * 0.06, 0, 0, B.TAU); g.fill();
    if (o.ornate) {
      // gallery ring hanging at the neck
      g.fillStyle = B.linear(g, cx - mw * 2.2, 0, cx + mw * 2.2, 0, [TN(0.5, 0.6), TN(0.95, 0.6)]);
      g.beginPath(); g.ellipse(cx, mouthY + h * 0.03, mw * 2.3, h * 0.035, 0, 0, B.TAU); g.fill();
      return G;
    }
    // skirt, ropes, burner, flame, basket
    g.fillStyle = TN(0.7); g.fillRect(cx - mw, mouthY - h * 0.005, mw * 2, h * 0.03); g.strokeStyle = TN(1);
    g.lineWidth = w * 0.022;
    for (const sx of [-1, 1]) {
      g.beginPath(); g.moveTo(cx + sx * mw * 0.9, mouthY + h * 0.02); g.lineTo(cx + sx * G.bw * 0.46, G.by);
      g.stroke();
    }
    g.fillStyle = TN(0.92); g.fillRect(cx - w * 0.06, G.burnerY, w * 0.12, h * 0.03);
    if (o.flame) {
      g.fillStyle = TN(0.1, 1); g.beginPath(); g.moveTo(cx, mouthY - h * 0.02);
      g.quadraticCurveTo(cx + w * 0.07, G.burnerY - h * 0.02, cx, G.burnerY);
      g.quadraticCurveTo(cx - w * 0.07, G.burnerY - h * 0.02, cx, mouthY - h * 0.02); g.fill();
    }
    g.fillStyle = B.linear(g, cx - G.bw / 2, 0, cx + G.bw / 2, 0, [TN(0.42), TN(0.88)]);
    g.fillRect(cx - G.bw / 2, G.by, G.bw, G.bh); g.strokeStyle = TN(1); g.lineWidth = w * 0.012;
    for (let i = 1; i < 4; i++) {
      g.beginPath(); g.moveTo(cx - G.bw / 2, G.by + (G.bh * i) / 4); g.lineTo(cx + G.bw / 2, G.by + (G.bh * i) / 4);
      g.stroke();
    }
    g.fillStyle = TN(1); g.fillRect(cx - G.bw / 2 - w * 0.01, G.by - h * 0.008, G.bw + w * 0.02, h * 0.02);
    return G;
  }
  /** The burner close-up: a tall flame (duotone) above a coiled burner block. */
  function paintFlame(g, w, h) {
    const cx = w / 2, base = h * 0.7, tip = h * 0.03;
    const fl = (k, top) => {
      g.beginPath(); g.moveTo(cx, top); g.bezierCurveTo(cx + w * 0.32 * k, h * 0.34, cx + w * 0.26 * k, base, cx, base);
      g.bezierCurveTo(cx - w * 0.26 * k, base, cx - w * 0.32 * k, h * 0.34, cx, top); g.closePath();
    };
    fl(1, tip);
    g.fillStyle = B.radial(g, cx, base - h * 0.14, 0, h * 0.62, [[0, TN(0.02, 0.3)], [0.55, TN(0.28, 0.9)], [1, TN(0.7, 1)]]);
    g.fill(); fl(0.5, h * 0.3); g.fillStyle = TN(0.0, 0.12); g.fill();
    g.fillStyle = B.linear(g, cx - w * 0.32, 0, cx + w * 0.32, 0, [TN(0.4), TN(0.92)]);
    g.fillRect(cx - w * 0.32, h * 0.72, w * 0.64, h * 0.12); g.strokeStyle = TN(1); g.lineWidth = w * 0.025;
    for (let i = 0; i < 6; i++) {
      const x = cx - w * 0.28 + (i * w * 0.56) / 5; g.beginPath(); g.moveTo(x, h * 0.72);
      g.lineTo(x + w * 0.03, h * 0.84); g.stroke();
    }
    g.fillStyle = TN(0.85); g.fillRect(cx - w * 0.09, h * 0.84, w * 0.18, h * 0.15);
  }
  // baked per aspect (the size is part of the cache key)
  const balloonCut = () => cutout("balloon", Math.round(44 * U), Math.round(58 * U), (g, w, h) => paintBalloon(g, w, h, { flame: true }), { duo: BRAND.accent, cy: 0.38, seed: 11 });
  const oldBalloonCut = () => cutout("balloon1783", Math.round(36 * U), Math.round(46 * U), (g, w, h) => paintBalloon(g, w, h, { ornate: true }), { duo: BRAND.notes.teal, cy: 0.42, seed: 12 });
  const flameCut = () => cutout("flame", Math.round(26 * U), Math.round(34 * U), paintFlame, { duo: BRAND.accent, cy: 0.5, seed: 13 });
  // fractions of the balloon subject box (44 x 58), for labels and marks
  const GEO = (() => {
    const G = balloonGeo(44, 58);
    return { rx: G.R / 44, ey: G.ey / 58, vent: (G.ey - G.R * 0.93) / 58, mouth: G.mouthY / 58, burner: G.burnerY / 58, basket: (G.by + G.bh / 2) / 58 };
  })();

  // ------------------------------------------------------------------ the shots (frame coordinates)
  function shotTitle(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    note(g, W * (P ? 0.8 : 0.86), H * (P ? 0.3 : 0.34), 34 * U, 34 * U, BRAND.notes.teal, 0.07, { seed: 1 });
    note(g, W * (P ? 0.12 : 0.06), H * (P ? 0.86 : 0.95), 30 * U, 30 * U, BRAND.notes.pink, -0.09, { seed: 2 });
    const cx = W * (P ? 0.62 : 0.72), cy = H * (P ? 0.32 : 0.48), k = P ? 0.95 : 1.0;
    placeCut(g, balloonCut(), cx, cy, k, 0.05, 1, slam(lt, 0.05));
    tape(g, cx - 2 * U, cy - 31 * U * k, 16 * U, 4.4 * U, -0.12, 3, slam(lt, 0.25));
    sticker(g, W * (P ? 0.24 : 0.53), H * (P ? 0.27 : 0.25), (P ? 11 : 10) * U, [["LIGHTER", 4.4], ["THAN AIR", 4.4]], { star: true, s: slam(lt, 0.9), rot: -0.12, id: 2 });
    const x = S.x + U, y0 = H * (P ? 0.535 : 0.34), sz = P ? 11 : 10;
    headline(g, "HOW DOES A", x, y0, sz * U, slam(lt, 0.3));
    strip(g, "HOT AIR BALLOON", x - U, y0 + (sz + 2.6) * U, { size: (P ? 10 : 10) * U, align: "left", rot: -0.012, s: slam(lt, 0.45), seed: 21 });
    const r2 = strip(g, "FLY?", x - 0.5 * U, y0 + (sz * 2 + 6.5) * U, { size: 15 * U, align: "left", fill: BRAND.accent, rot: 0.02, s: slam(lt, 0.62), seed: 22 });
    aside(g, "No wings, no engine. Just warm air.", r2.r + 3 * U, r2.t + 1.5 * U, { maxW: P ? S.r - r2.r - 4 * U : 52 * U, p: B.prog(lt, 0.75, 0.35) });
  }

  function shotDiagram(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    note(g, W * (P ? 0.9 : 0.06), H * (P ? 0.72 : 0.8), 30 * U, 30 * U, BRAND.notes.yellow, -0.1, { seed: 3 });
    const k = P ? 1.25 : 1.12, cx = W * (P ? 0.5 : 0.5), cy = H * (P ? 0.53 : 0.55);
    const map = placeCut(g, balloonCut(), cx, cy, k, -0.03, 4, 1);
    tape(g, cx + 14 * U, cy - 30 * U * k, 14 * U, 4.2 * U, 0.5, 5);
    strip(g, "WHAT'S INSIDE", S.x, S.y + (P ? 13 : 12) * U, { size: 8.5 * U, align: "left", fill: BRAND.accent, rot: -0.02, s: slam(lt, 0.15), seed: 31 });
    // labels: small black torn tags with a red marker leader to the part
    const parts = [
      ["ENVELOPE", 0.5 - GEO.rx * 0.75, GEO.ey, -1, 0.35],
      ["BURNER", 0.55, GEO.burner, 1, 0.5],
      ["BASKET", 0.42, GEO.basket, -1, 0.65],
    ];
    parts.forEach(([txt, fx, fy, side, at], i) => {
      const [px, py] = map(fx, fy);
      const tx = side < 0 ? (P ? S.x + 1 * U : px - 34 * U) : (P ? S.r - 1 * U : px + 30 * U), ty = py + (i === 0 ? -6 : 3) * U;
      const s = slam(lt, at), o = { size: 4.8 * U, align: "left", rot: side * 0.02, s, seed: 40 + i };
      const r = strip(g, txt, side < 0 ? tx : tx - strip(g, txt, 0, 0, { ...o, s: 0 }).w, ty, o); // s 0: measure only
      if (s <= 0) return;
      const from = side < 0 ? [r.r + 0.5 * U, ty] : [r.l - 0.5 * U, ty];
      marker(g, [from, [B.lerp(from[0], px, 0.6), B.lerp(from[1], py, 0.2)], [px, py]], B.prog(lt, at + 0.08, 0.25), 0.7, 7 + i);
      if (lt > at + 0.3) {
        g.beginPath(); B.circle(g, px, py, 0.9 * U); g.fillStyle = BRAND.accent; g.fill();
      }
    });
    // the hot air: a marker arrow rising from the flame into the envelope, and the note that says so
    const nx = P ? W * 0.74 : cx + 38 * U, ny = H * (P ? 0.255 : 0.36), [bx, by] = map(0.5 + GEO.rx * 0.55, GEO.ey - 0.12);
    note(g, nx, ny, (P ? 30 : 28) * U, 22 * U, BRAND.notes.yellow, 0.05,
      { seed: 4, s: slam(lt, 0.95), text: "Hot air rises and fills it", size: 4.0 * U, p: B.prog(lt, 1.0, 0.35) });
    markerArrow(g, [[nx - (P ? 6 : 15) * U, ny + 11 * U], [B.lerp(nx, bx, 0.6), by + 6 * U], [bx + 1.5 * U, by + 1.5 * U]], B.prog(lt, 0.8, 0.3, "outCubic"), 6);
  }

  function shotNumber(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    // kraft sheet behind
    g.save(); g.translate(W * (P ? 0.5 : 0.4), H * (P ? 0.5 : 0.53)); g.rotate(-0.04);
    sheet(g, tornRect((P ? 92 : 104) * U, (P ? 62 : 64) * U, 51, [1, 0.9, 1, 0.9]), BRAND.kraft, { shadow: 0.25 });
    g.restore();
    placeCut(g, oldBalloonCut(), W * (P ? 0.74 : 0.78), H * (P ? 0.3 : 0.47), P ? 0.95 : 1.25, 0.06, 7, 1);
    tape(g, W * (P ? 0.74 : 0.78), P ? H * 0.3 - 22 * U : H * 0.47 - 29 * U, 15 * U, 4.2 * U, -0.05, 8);
    // the number: digits stamped one by one onto a torn card
    const nc = P ? [W * 0.45, H * 0.47] : [W * 0.37, H * 0.45], size = (P ? 27 : 30) * U;
    g.save(); g.translate(nc[0], nc[1]); g.rotate(-0.025);
    sheet(g, tornRect(size * 2.65, size * 1.3, 52, [0.7, 0.5, 0.7, 0.5]), BRAND.card, { shadow: 0.34 });
    g.font = B.font(size, BRAND.display, 400);
    const digits = "1783", dw = digits.split("").map((c) => g.measureText(c).width), tot = dw.reduce((a, b) => a + b, 0) + size * 0.06 * 3;
    let xx = -tot / 2;
    digits.split("").forEach((c, i) => {
      const s = slam(lt, 0.12 + i * 0.1);
      if (s > 0) headline(g, c, xx + dw[i] / 2, size * 0.04, size, s, { align: "center", color: i === 3 ? BRAND.accent : BRAND.ink });
      xx += dw[i] + size * 0.06;
    });
    g.restore(); markerRing(g, nc[0], nc[1], size * 1.45, size * 0.78, B.prog(lt, 0.55, 0.35), 9);
    sticker(g, nc[0] - size * 1.25, nc[1] - size * 0.72, (P ? 8.5 : 7.5) * U, [["THE", 4.0], ["YEAR", 4.4]], { s: slam(lt, 0.7), rot: -0.2, id: 9 });
    const sy = H * (P ? 0.625 : 0.72);
    const r = strip(g, "PEOPLE FIRST FLEW", P ? W * 0.5 : nc[0], sy, { size: (P ? 8.5 : 7.5) * U, rot: 0.015, s: slam(lt, 0.85), seed: 53 });
    aside(g, "under a hot air balloon, over Paris.", P ? W * 0.5 : nc[0], r.b + 1.5 * U, { maxW: (P ? 70 : 90) * U, align: "center", p: B.prog(lt, 1.0, 0.35) });
    note(g, W * (P ? 0.14 : 0.95), H * (P ? 0.76 : 0.12), 26 * U, 26 * U, BRAND.notes.pink, 0.12, { seed: 6 });
  }

  /** One step card: torn card sheet with tape, number sticker, heading strip, a visual and an aside. */
  function stepCard(g, F, x, y, w, h, n, head, text, lt, at, visual) {
    const s = at > 0 ? slam(lt, at) : 1;
    if (s <= 0) return;
    const P = F.portrait; g.save(); g.translate(x, y); g.rotate(n === 1 ? -0.015 : 0.012); g.scale(s, s);
    sheet(g, tornRect(w, h, 60 + n, [0.6, 0.4, 0.6, 0.4]), BRAND.card, { shadow: 0.3 });
    tape(g, 0, -h / 2, 16 * U, 4.2 * U, n === 1 ? 0.06 : -0.08, 61 + n); const hs = 7 * U;
    const r = strip(g, head, -w / 2 + 12.5 * U, -h / 2 + 7.5 * U, { size: hs, align: "left", rot: -0.01, s: slam(lt, at + 0.12), seed: 62 + n });
    sticker(g, -w / 2 + 5 * U, -h / 2 + 6.5 * U, 5.6 * U, [[String(n), 7]], { s: slam(lt, at + 0.05), rot: 0.1, id: 63 + n });
    // the visual on one side (portrait: left), the aside beside or below it
    const vx = P ? -w / 2 + 16 * U : 0, vy = (P ? 6 : 1) * U; visual(vx, vy);
    aside(g, text, -w / 2 + (P ? 31 : 4) * U, P ? -h / 2 + 15 * U : h / 2 - 15 * U, { maxW: w - (P ? 34 : 8) * U, p: B.prog(lt, at + 0.3, 0.35) });
    g.restore();
    return r;
  }

  function shotSteps(g, F, lt) {
    const P = F.portrait, W = F.W, H = F.H;
    note(g, W * (P ? 0.08 : 0.5), H * (P ? 0.5 : 0.9), 26 * U, 26 * U, BRAND.notes.teal, 0.08, { seed: 7 });
    const cw = (P ? 84 : 72) * U, ch = (P ? 42 : 70) * U;
    const c1 = P ? [W * 0.5, H * 0.315] : [W * 0.27, H * 0.53], c2 = P ? [W * 0.5, H * 0.59] : [W * 0.73, H * 0.53];
    stepCard(g, F, c1[0], c1[1], cw, ch, 1, "HEAT THE AIR", "The burner heats the air inside to about 100°C.", lt, 0, (vx, vy) => {
      const fy = 1 + (B.hash01(B.boil(T, 12), 77) - 0.5) * 0.06; // the flame flickers on twelve
      g.save(); g.translate(vx, vy); g.scale(1, fy); placeCut(g, flameCut(), 0, 0, P ? 0.8 : 0.85, 0.03, 12, 1);
      g.restore();
    });
    if (P) markerArrow(g, [[W * 0.86, H * 0.425], [W * 0.875, H * 0.45], [W * 0.86, H * 0.48]], B.prog(lt, 0.55, 0.2), 13);
    else markerArrow(g, [[W * 0.475, H * 0.5], [W * 0.5, H * 0.48], [W * 0.528, H * 0.5]], B.prog(lt, 0.55, 0.2), 13);
    stepCard(g, F, c2[0], c2[1], cw, ch, 2, "HOT AIR IS LIGHTER", "So each cubic metre of it lifts about a quarter of a kilo.", lt, 0.7, (vx, vy) => {
      // a cubic metre drawn in marker, with a red arrow lifting it and a weight sticker
      const e = 9 * U, d = 4 * U, p = B.prog(lt, 0.95, 0.3);
      const fx = vx - e / 2 - d / 2, fy = vy - e / 2 + d / 2 + 2 * U;
      marker(g, [[fx, fy], [fx + e, fy], [fx + e, fy + e], [fx, fy + e], [fx, fy]], p, 0.8, 21);
      marker(g, [[fx, fy], [fx + d, fy - d], [fx + e + d, fy - d], [fx + e, fy]], p, 0.8, 22);
      marker(g, [[fx + e + d, fy - d], [fx + e + d, fy + e - d], [fx + e, fy + e]], p, 0.8, 23);
      markerArrow(g, [[fx + e / 2 + d / 2, fy - d - 1 * U], [fx + e / 2 + d / 2, fy - d - 9 * U]], B.prog(lt, 1.15, 0.2), 24);
      sticker(g, vx + (P ? 5 : 10) * U, vy + (P ? 9 : 5) * U, 7 * U, [["0.25", 5], ["KG", 4.2]], { s: slam(lt, 1.2), rot: 0.15, id: 25 });
    });
  }

  function shotVent(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    note(g, W * (P ? 0.88 : 0.93), H * (P ? 0.22 : 0.8), 28 * U, 28 * U, BRAND.notes.pink, 0.1, { seed: 8 });
    const k = P ? 1.15 : 1.15, sink = B.span(lt, 0.4, 1.9, "inOutSine") * 6 * U;
    const cx = W * (P ? 0.47 : 0.3), cy = (H * (P ? 0.375 : 0.5)) + sink;
    const map = placeCut(g, balloonCut(), cx, cy, k, -0.02, 14, 1);
    tape(g, cx - 13 * U, cy + 26 * U * k, 13 * U, 4 * U, 0.3, 15); const [vx, vy] = map(0.5, GEO.vent);
    markerRing(g, vx, vy, 7 * U, 3.6 * U, B.prog(lt, 0.4, 0.3), 16);
    for (let i = 0; i < 3; i++) {
      // hot air escaping: little marker wisps rising out of the vent, redrawn on twelve
      const p = B.prog(lt, 0.6 + i * 0.1, 0.3), ox = (i - 1) * 3.2 * U; const pts = [];
      for (let j = 0; j <= 10; j++) pts.push([vx + ox + Math.sin(j * 0.9 + i + B.boil(T, 12) * 0.5) * 0.8 * U, vy - 4 * U - j * 0.9 * U]);
      marker(g, pts, p, 0.6, 30 + i);
    }
    const ax = P ? cx + 33 * U : cx + 34 * U;
    markerArrow(g, [[ax, cy - 12 * U], [ax + 2 * U, cy], [ax, cy + 12 * U]], B.prog(lt, 0.7, 0.3), 17);
    const tx = W * (P ? 0.5 : 0.6), ty = H * (P ? 0.665 : 0.42);
    const r = strip(g, "OPEN THE VENT", tx, ty, { size: (P ? 10.5 : 10) * U, align: P ? "center" : "left", rot: -0.02, s: slam(lt, 0.25), seed: 71 });
    sticker(g, P ? r.l + 1 * U : tx - 4 * U, P ? r.t - 3 * U : ty - 15 * U, 6 * U, [["3", 7.5]], { s: slam(lt, 0.1), rot: -0.1, id: 18 });
    aside(g, "Hot air escapes and the rest cools: the balloon sinks.", P ? W * 0.5 : tx + U, r.b + 2 * U,
      { maxW: (P ? 76 : 62) * U, align: P ? "center" : "left", p: B.prog(lt, 0.75, 0.35) });
  }

  function shotClose(g, F, lt) {
    const P = F.portrait, S = F.safe, W = F.W, H = F.H;
    note(g, W * (P ? 0.16 : 0.6), H * (P ? 0.2 : 0.15), 30 * U, 30 * U, BRAND.notes.teal, -0.06, { seed: 9 });
    note(g, W * (P ? 0.9 : 0.96), H * (P ? 0.82 : 0.88), 28 * U, 28 * U, BRAND.notes.yellow, 0.08, { seed: 10 });
    const rise = (1 - B.span(lt, -0.3, 1.7, "outCubic")) * 10 * U;
    const cx = W * (P ? 0.56 : 0.75), cy = (H * (P ? 0.33 : 0.47)) + rise;
    placeCut(g, balloonCut(), cx, cy, P ? 0.95 : 1.0, 0.04 + 0.02 * Math.sin(B.stepTime(T, 12) * 3), 19, 1);
    tape(g, cx + 3 * U, cy - 30 * U, 15 * U, 4.2 * U, 0.08, 20); const x = S.x + U, y0 = H * (P ? 0.59 : 0.36);
    strip(g, "HOT AIR UP.", x, y0, { size: 12 * U, align: "left", rot: -0.015, s: slam(lt, 0.15), seed: 81 });
    const r = strip(g, "COOL AIR DOWN.", x, y0 + 16 * U, { size: 12 * U, align: "left", fill: BRAND.accent, rot: 0.01, s: slam(lt, 0.35), seed: 82 });
    marker(g, [[r.l + 2 * U, r.b + 2.2 * U], [r.r * 0.6 + r.l * 0.4, r.b + 3 * U], [r.r - 1 * U, r.b + 2 * U]], B.prog(lt, 0.6, 0.25), 1.2, 83);
    aside(g, "That's the whole trick.", x + U, r.b + 5 * U, { maxW: 70 * U, p: B.prog(lt, 0.8, 0.3) });
    sticker(g, W * (P ? 0.27 : 0.5), H * (P ? 0.41 : 0.22), (P ? 10 : 9) * U, [["THAT'S", 4.2], ["IT!", 6]], { star: true, s: slam(lt, 0.75), rot: 0.14, id: 21 });
  }

  const SHOTS = [shotTitle, shotDiagram, shotNumber, shotSteps, shotVent, shotClose];

  // ------------------------------------------------------------------ frame: shots, whip pans, punch-ins, finish
  function renderShot(key, i, F, t) {
    const g = B.scratch(key, F.W, F.H);
    B.paper(g, F.W, F.H, { color: BRAND.paper, seed: 40, mottle: 0.16, fibers: 0.7, specks: 0.5, tooth: 0.1 });
    SHOTS[i](g, F, t - BEATS[i]);
    return g.canvas;
  }
  /** Draw a shot shifted along the whip, with a smear of fainter copies trailing behind it. */
  function smear(ctx, c, off, horiz, amt, D) {
    ctx.drawImage(c, horiz ? off : 0, horiz ? 0 : off);
    if (amt < 0.05) return;
    ctx.save(); ctx.globalAlpha = 0.2 * amt;
    for (let k = 1; k <= 7; k++) {
      const o = off + k * 0.022 * D * amt; ctx.drawImage(c, horiz ? o : 0, horiz ? 0 : o);
    }
    ctx.restore();
  }
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H); U = F.u; T = t; ctx.fillStyle = BRAND.paper; ctx.fillRect(0, 0, W, H); let sh = 0;
    for (const [at, amp] of SLAMS) if (t >= at) sh += amp * Math.max(0, 1 - (t - at) / 0.2);
    const [dx, dy] = B.shake(t, sh * U, 40, 26); let whip = null;
    for (let i = 1; i < BEATS.length; i++) if (CUTS[i] !== "punch" && Math.abs(t - BEATS[i]) < WHIP / 2) whip = { i, p: (t - BEATS[i] + WHIP / 2) / WHIP };
    ctx.save(); ctx.translate(dx, dy);
    if (whip) {
      const horiz = CUTS[whip.i] === "whip-x", D = horiz ? W : H, e = B.ease.inOutCubic(whip.p), amt = Math.sin(Math.PI * whip.p);
      smear(ctx, renderShot("ec-a", whip.i - 1, F, t), -e * D, horiz, amt, D);
      smear(ctx, renderShot("ec-b", whip.i, F, t), (1 - e) * D, horiz, amt, D);
    } else {
      const i = B.beat(t, BEATS, DUR).i, c = renderShot("ec-a", i, F, t);
      // punch-in cut: the new shot lands a little too close and snaps back
      const z = CUTS[i] === "punch" ? 1 + 0.12 * (1 - B.ease.outCubic(B.prog(t, BEATS[i], 0.22))) : 1;
      ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.drawImage(c, -W / 2, -H / 2);
    }
    ctx.restore();
    // finishing: warm vignette, fine grain refreshed on twelve
    hud(ctx, F); // the HUD is an overlay: it stays put through whips and punch-ins
    B.vignette(ctx, W, H, { amount: 0.22, color: "#6a4f2e", inner: 0.55, mode: "multiply" });
    B.grain(ctx, W, H, { amount: 0.07, t, fps: 12, mode: "overlay" });
  }

  // ------------------------------------------------------------------ sound: rustle, tape rip, stamp thuds, whooshes, pluck bed
  SOUND.define("ec-tape", (v) => {
    // masking tape torn off the roll: a bright hiss with a crackle of small grains
    v.noise({ filter: "highpass", f: 2600, a: 0.004, hold: 0.1, len: 0.05, peak: 0.22 });
    v.grains({ span: 0.15, count: 14, filter: "bandpass", f: 3400, q: 1.2, len: 0.012, peak: 0.28 });
  }, { verb: 0.08 });
  SOUND.define("ec-slam", (v) => {
    // paper slapped down on a desk: a low knock with a dry papery crack
    v.tone({ f: 130, f2: 55, glide: 0.08, a: 0.001, len: 0.16, peak: 0.55 });
    v.noise({ filter: "bandpass", f: 1500, q: 0.8, a: 0.0008, len: 0.06, peak: 0.4 });
  }, { verb: 0.1 });

  function score(k) {
    // a confident pluck bed: C - G - Am - F - C - G, eighth notes at 120 bpm
    const bars = [["C3", "G3", "C4", "E4"], ["G2", "D3", "G3", "B3"], ["A2", "E3", "A3", "C4"], ["F2", "C3", "F3", "A3"], ["C3", "G3", "C4", "E4"], ["G2", "D3", "G3", "D4"]];
    bars.forEach((n, b) => k.seq(b * 2, 0.25, [n[0], null, n[2], n[3], n[1], null, n[2], n[3]], { gain: 0.3 }));
    k.at(11.5, "pluck", { note: "C5", gain: 0.4 });
    // whips and punch-ins
    [1, 3, 5].forEach((i) => k.at(BEATS[i] - 0.2, "whoosh", { gain: 0.8, dur: 0.38 }));
    [2, 4].forEach((i) => k.at(BEATS[i], "stamp", { gain: 0.9 }).at(BEATS[i], "ec-slam"));
    // slams
    SLAMS.forEach(([at, amp]) => at !== 4.0 && at !== 8.4 && k.at(at, amp > 0.75 ? "ec-slam" : "stamp", { gain: 0.45 + amp * 0.3 }));
    // cut-outs and tape
    k.at(0.05, "rustle", { dur: 0.3 }).at(0.25, "ec-tape").at(1.95, "paper", { gain: 0.5 });
    k.at(6.25, "rustle", { dur: 0.3 }).at(6.9, "ec-tape", { gain: 0.8 }).at(10.35, "rustle", { dur: 0.4 });
    // marker squeaks for leaders, ring, arrows and the underline
    [[2.33, 0.25], [2.48, 0.25], [2.63, 0.25], [2.7, 0.3], [4.55, 0.35], [7.15, 0.3], [8.8, 0.3], [9.1, 0.3], [10.9, 0.25]].forEach(([at, d]) => k.at(at, "marker", { dur: d, gain: 0.6 }));
    k.at(2.85, "pop", { gain: 0.4 }).at(7.4, "pop", { gain: 0.5 }).at(11.05, "pop", { gain: 0.5 });
  }

  Player.register({
    id: "editorial-collage",
    name: "Editorial Collage",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Anton&family=DM+Mono:wght@500&family=Libre+Baskerville:ital@1&display=swap",
      faces: ['400 20px "Anton"', '500 20px "DM Mono"', 'italic 400 20px "Libre Baskerville"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.55, 3.65, 5.8, 8.0, 10.0, 11.7],
    draw,
    score,
  });
})();
