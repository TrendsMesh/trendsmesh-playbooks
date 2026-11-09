/* 36 Art Deco - reference animation.
 * Topic (setting, replace it): "The rule of 72" - how long money takes to double.
 * Rendering (keep it): a 1920s luxury poster in black lacquer and gold foil, mirror-symmetric about the vertical axis.
 * Every gold element is drawn flat into one gold plate, which is then foiled: metallic light and dark bands laid over
 * it, a lighter gold edge on filled shapes, and a narrow bright shine band sweeping diagonally across. A stepped border
 * of nested notched rectangles with chevron rows, sunbursts of alternating gold and dark rays, fans of nested arcs,
 * a stepped tower of pinstriped tiers, tall Limelight capitals in gold, small Poiret One text in cream on plaques.
 * Finishing: lacquer sheen (soft broad lighter patches), corner vignette, light print grain.
 * Motion: the border draws out from the middle of each side; rays and arcs open like a fan, both halves at once;
 * tiers arrive as wipes from the centre outward; title letters stamp in one at a time with a gold flash; numbers
 * roll like an odometer; scene changes close two gold-edged doors from left and right, then reopen. Stately, even.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { black: "#0e0d0c", gold: "#c9a23f", foil: "#f1d680", dark: "#8a6a22", cream: "#efe6cf", teal: "#14504f", oxblood: "#6e1f26" };
  const DISPLAY = "Limelight", THIN = "Poiret One";
  const DUR = 12.5;
  const BEATS = [0, 2.3, 4.6, 6.9, 9.2, 10.8];
  const DOORS = [2.3, 4.6, 6.9, 10.8]; // doors fully closed at these times; the scene swaps behind them
  let U = 1, T = 0, F = null;
  const PL = (portrait, landscape) => (F.portrait ? portrait : landscape);

  // ------------------------------------------------------------------ the gold plate and its foil pass (reuse these)
  /**
   * Draw gold with fn(g) into a scratch plate, then foil it: metallic bands (light above, a dark horizon line through
   * each band, as polished gold reflects the room), then a narrow bright shine band sweeping diagonally, all applied
   * with source-atop so only the gold is lit. Then lay the plate onto the poster.
   */
  function goldPass(ctx, W, H, key, fn, shineAt) {
    const g = B.scratch("deco-gold-" + key, W, H);
    fn(g);
    g.save();
    g.globalCompositeOperation = "source-atop";
    const stops = [], n = Math.round(H / (24 * U));
    for (let i = 0; i <= n * 2; i++) stops.push([i / (n * 2), i % 2 ? "rgba(255,240,200,0.24)" : "rgba(40,20,0,0.3)"]);
    g.fillStyle = B.linear(g, 0, 0, W * 0.12, H, stops); // metallic bands, slightly tilted
    g.fillRect(0, 0, W, H);
    // the shine: a narrow bright diagonal band crossing the frame every few seconds
    const ph = B.fract((T - (shineAt ?? 0)) / 3.2), x = B.lerp(-0.2 * W, W + H * 0.7 + 0.2 * W, ph), bw = 7 * U;
    g.fillStyle = B.linear(g, x - bw, 0, x + bw, 0, [[0, "rgba(255,250,228,0)"], [0.5, "rgba(255,250,228,0.85)"], [1, "rgba(255,250,228,0)"]]);
    g.beginPath();
    g.moveTo(x - bw, 0);
    g.lineTo(x + bw, 0);
    g.lineTo(x + bw - H * 0.7, H);
    g.lineTo(x - bw - H * 0.7, H);
    g.closePath();
    g.fill();
    g.restore();
    ctx.drawImage(g.canvas, 0, 0);
  }
  /** Stroke a gold line (thin, parallel-line deco drawing). */
  function line(g, pts, w, color = PAL.gold) {
    if (pts.length < 2) return;
    g.save();
    g.strokeStyle = color;
    g.lineWidth = w;
    g.lineJoin = "miter";
    g.lineCap = "butt";
    g.beginPath();
    B.poly(g, pts);
    g.stroke();
    g.restore();
  }
  /** Notched-corner rectangle as four side polylines (each side runs corner to corner through its middle). */
  function notchSides(x, y, w, h, n) {
    return [
      [[x + n, y + n], [x + n, y], [x + w - n, y], [x + w - n, y + n]],
      [[x + w - n, y + n], [x + w, y + n], [x + w, y + h - n], [x + w - n, y + h - n]],
      [[x + w - n, y + h - n], [x + w - n, y + h], [x + n, y + h], [x + n, y + h - n]],
      [[x + n, y + h - n], [x, y + h - n], [x, y + n], [x + n, y + n]],
    ];
  }
  const notchPoly = (x, y, w, h, n) => notchSides(x, y, w, h, n).flatMap((s) => s.slice(1));
  /** Draw a side from its middle outward to both ends at once (p 0..1): deco lines finish symmetrically. */
  function fromMiddle(g, side, p, w, color) {
    if (p <= 0) return;
    line(g, B.trim(side, 0.5 - p / 2, 0.5 + p / 2), w, color);
  }
  /** Poiret One is hairline: a stroke in its own colour thickens it enough to read small. */
  const thick = (color, size) => ({ stroke: color, strokeW: size * 0.05 });
  /** The stepped border: three nested notched frames and chevron rows, drawn from the middle of each side. */
  function border(g, W, H, p) {
    const m = PL(3.2, 2.6) * U;
    [[m, 1, 0.28, PAL.gold], [m + 1.4 * U, 3.2, 0.14, PAL.foil], [m + 2.5 * U, 4.6, 0.1, PAL.dark]].forEach(([inset, notch, w, col], i) => {
      const k = B.clamp(p * 1.4 - i * 0.2);
      notchSides(inset, inset, W - 2 * inset, H - 2 * inset, notch * U).forEach((s) => fromMiddle(g, s, k, w * U * 2, col));
    });
    const k = B.clamp(p * 1.6 - 0.6);
    chevrons(g, W / 2, m + 4.2 * U, 9, 1.6 * U, k, 1);
    chevrons(g, W / 2, H - m - 4.2 * U, 9, 1.6 * U, k, -1);
    if (!F.portrait) return;
    // 9:16: a mirrored skyline frieze along the foot keeps the tall frame dressed below the story
    const fy = H - m - 7 * U;
    [[0, 20, 14], [13, 15, 11], [24, 11, 10], [34, 8, 9]].forEach(([dx, h, w], i) => [-1, 1].forEach((sd) => (i || sd > 0) && tier(g, W / 2 + sd * dx * U, fy - h * U, w * U, h * U, k, 5)));
  }
  /** A row of small chevrons centred on cx, appearing from the middle outward. */
  function chevrons(g, cx, y, n, s, p, dir) {
    for (let i = 0; i < n; i++) {
      const off = i - (n - 1) / 2, k = B.clamp(p * ((n + 1) / 2) - Math.abs(off));
      if (k <= 0) continue;
      const x = cx + off * s * 2.2;
      line(g, [[x - s, y + dir * s * 0.5 * k], [x, y - dir * s * 0.5 * k], [x + s, y + dir * s * 0.5 * k]], 0.3 * U);
    }
  }
  /**
   * Sunburst: long thin rays fanning out of (cx, cy) over the upper half, alternating gold and dark gold bands,
   * opening from the vertical outward on both sides at once (p 0..1).
   */
  function sunburst(g, cx, cy, r0, r1, n, p, span = Math.PI) {
    for (let i = 0; i < n; i++) {
      const a = (i + 0.5) / n - 0.5, k = B.clamp(p * 1.3 - Math.abs(a) * 1.6);
      if (k <= 0) continue;
      const ang = -Math.PI / 2 + a * span, wid = (span / n) * (i % 2 ? 0.22 : 0.4);
      g.fillStyle = i % 2 ? PAL.dark : PAL.gold;
      g.beginPath();
      g.moveTo(cx + Math.cos(ang - wid / 2) * r0, cy + Math.sin(ang - wid / 2) * r0);
      g.lineTo(cx + Math.cos(ang) * B.lerp(r0, r1, k), cy + Math.sin(ang) * B.lerp(r0, r1, k));
      g.lineTo(cx + Math.cos(ang + wid / 2) * r0, cy + Math.sin(ang + wid / 2) * r0);
      g.fill();
    }
  }
  /** Fan of nested arcs above (cx, cy), opening symmetrically from the top (p 0..1). */
  function fan(g, cx, cy, r, rings, p, w = 0.22) {
    for (let i = 0; i < rings; i++) {
      const rr = r * (1 - i / rings), half = (Math.PI / 2) * B.clamp(p * 1.4 - i * 0.08);
      if (half <= 0) continue;
      g.save();
      g.strokeStyle = i % 2 ? PAL.dark : PAL.gold;
      g.lineWidth = w * U * (i ? 1 : 2);
      g.beginPath();
      g.arc(cx, cy, rr, -Math.PI / 2 - half, -Math.PI / 2 + half);
      g.stroke();
      g.restore();
    }
  }
  /**
   * One tier of the stepped tower: a solid black block with a gold frame, a lighter gold top edge and vertical
   * pinstripes, arriving as a wipe from the centre outward (p 0..1).
   */
  function tier(g, cx, y, w, h, p, stripes = 9) {
    if (p <= 0) return;
    const ww = w * B.ease.outCubic(p);
    g.save();
    g.beginPath();
    g.rect(cx - ww / 2, y - 1 * U, ww, h + 2 * U);
    g.clip();
    g.globalCompositeOperation = "destination-out"; // the tier is black lacquer: cut the gold behind it
    g.fillRect(cx - w / 2, y, w, h);
    g.globalCompositeOperation = "source-over";
    line(g, B.rectPts(cx - w / 2, y, w, h), 0.4 * U);
    g.fillStyle = PAL.foil;
    g.fillRect(cx - w / 2, y, w, 0.5 * U); // the lighter gold edge
    for (let i = 1; i < stripes; i++) {
      const x = cx - w / 2 + (w * i) / stripes;
      if (i === Math.floor(stripes / 2) || i === Math.ceil(stripes / 2)) continue;
      line(g, [[x, y + 1.6 * U], [x, y + h - 1.2 * U]], 0.14 * U, PAL.dark);
    }
    g.restore();
  }
  /** Long thin gold arrow with a notched head (a straight shaft, never a curved hand arrow), drawn to p. */
  function decoArrow(g, x0, y0, x1, y1, p, s = 1) {
    if (p <= 0) return;
    const x = B.lerp(x0, x1, p), y = B.lerp(y0, y1, p), a = Math.atan2(y1 - y0, x1 - x0), L = 2.6 * U * s, Wd = 1.4 * U * s;
    line(g, [[x0, y0], [x - Math.cos(a) * L * 0.6, y - Math.sin(a) * L * 0.6]], 0.3 * U);
    const pt = (d, o) => [x + Math.cos(a) * d - Math.sin(a) * o, y + Math.sin(a) * d + Math.cos(a) * o];
    g.fillStyle = PAL.gold;
    g.beginPath();
    B.poly(g, [pt(0, 0), pt(-L, Wd), pt(-L * 0.62, 0), pt(-L, -Wd)], true);
    g.fill();
  }
  /** Odometer: one gold window per digit, digit strips rolling up; v is continuous (e.g. 72 * k). */
  function odometer(g, cx, cy, v, digits, size) {
    const cw = size * 0.92, ch = size * 1.2, x0 = cx - (digits * cw) / 2;
    for (let d = 0; d < digits; d++) {
      const place = Math.pow(10, digits - 1 - d), whole = v / place;
      let pos = Math.floor(whole); // a digit only turns while the digit to its right rolls from 9 to 10
      if (place > 1) pos += B.clamp((v % place) / (place / 10) - (10 - 1));
      else pos = whole;
      const x = x0 + d * cw + cw / 2;
      g.save(); // the window is lacquer: no rays show behind the figure
      g.globalCompositeOperation = "destination-out";
      g.beginPath();
      B.poly(g, notchPoly(x - cw / 2 + 0.4 * U, cy - ch / 2, cw - 0.8 * U, ch, 0.9 * U), true);
      g.fill();
      g.restore();
      notchSides(x - cw / 2 + 0.4 * U, cy - ch / 2, cw - 0.8 * U, ch, 0.9 * U).forEach((s) => line(g, s, 0.25 * U));
      g.save();
      g.beginPath();
      g.rect(x - cw / 2, cy - ch / 2 + 0.4 * U, cw, ch - 0.8 * U);
      g.clip();
      g.fillStyle = PAL.gold;
      g.font = B.font(size, DISPLAY, 400);
      g.textAlign = "center";
      g.textBaseline = "middle";
      const f = pos - Math.floor(pos);
      for (let j = 0; j <= (f > 0.001 ? 1 : 0); j++) g.fillText(String((((Math.floor(pos) + j) % 10) + 10) % 10), x, cy + size * 0.06 + (j - f) * ch);
      g.restore();
    }
  }
  /** Title letters stamped one at a time: each lands from 1.25x with a bright flash that cools to gold. */
  function stampTitle(g, text, cx, cy, size, at, gap = 0.07) {
    g.save();
    const setFont = () => {
      g.font = B.font(size, DISPLAY, 400);
      if ("letterSpacing" in g) g.letterSpacing = (size * 0.12).toFixed(1) + "px";
    };
    setFont();
    let total = g.measureText(text).width;
    if (total > F.safe.w * 0.86) { // shrink to stay well inside the border, the sparkle included
      size *= (F.safe.w * 0.86) / total;
      setFont();
      total = g.measureText(text).width;
    }
    let x = cx - total / 2;
    [...text].forEach((ch, i) => {
      const w = g.measureText(ch).width, dt = T - (at + i * gap);
      if (dt > 0 && ch !== " ") {
        const k = B.clamp(dt / 0.14), s = B.lerp(1.25, 1, B.ease.outCubic(k));
        g.save();
        g.translate(x + w / 2, cy);
        g.scale(s, s);
        g.globalAlpha *= k;
        g.fillStyle = B.mix("#fffaf0", PAL.gold, B.clamp(dt / 0.35)); // the flash cools to gold
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillText(ch, 0, 0);
        g.restore();
        if (dt < 0.3) star(g, x + w * 0.8, cy - size * 0.38, size * 0.22 * Math.sin((dt / 0.3) * Math.PI));
      }
      x += w;
    });
    g.restore();
  }
  function star(g, x, y, r) {
    if (r <= 0) return;
    g.fillStyle = "#fff6d8";
    g.beginPath();
    B.sparkle(g, x, y, r, 0.12);
    g.fill();
  }
  /** Plaque: a notched gold-outlined panel on black (or cream), small text centred in it. */
  function plaque(ctx, g, cx, cy, w, h, lines, p, o = {}) {
    if (p <= 0) return;
    const ww = w * B.ease.outCubic(p), x = cx - ww / 2;
    const poly = notchPoly(x, cy - h / 2, ww, h, 1.2 * U);
    g.save();
    g.globalCompositeOperation = "destination-out";
    g.beginPath();
    B.poly(g, poly, true);
    g.fill();
    g.restore();
    line(g, poly.concat([poly[0]]), 0.3 * U);
    const inner = notchPoly(x + 0.8 * U, cy - h / 2 + 0.8 * U, ww - 1.6 * U, h - 1.6 * U, 0.8 * U);
    line(g, inner.concat([inner[0]]), 0.12 * U, PAL.dark);
    if (o.fill) {
      ctx.fillStyle = o.fill;
      ctx.beginPath();
      B.poly(ctx, notchPoly(x + 0.8 * U, cy - h / 2 + 0.8 * U, ww - 1.6 * U, h - 1.6 * U, 0.8 * U), true);
      ctx.fill();
    }
    const a = B.clamp((p - 0.6) / 0.4);
    lines.forEach((l, i) => {
      const y = cy + (i - (lines.length - 1) / 2) * l.size * 1.25;
      const col = l.color || (o.fill ? PAL.black : PAL.cream);
      B.text(ctx, l.text, cx, y, { size: l.size, maxLines: 1, minSize: l.size * 0.8, family: l.display ? DISPLAY : THIN, weight: 400, color: col, letterSpacing: l.display ? 0.12 : 0.06, maxW: w * 0.9, alpha: a, ...(l.display ? {} : thick(col, l.size)) });
    });
  }

  // ------------------------------------------------------------------ scenes (the setting: replace the content)
  function sceneTitle(ctx, g) {
    const W = F.W, H = F.H, S = F.safe, cy = H * PL(0.63, 0.7), th = PL(9, 6) * U;
    sunburst(g, W / 2, cy, 6 * U, PL(80, 62) * U, 30, B.prog(T, 0.35, 1.1, "outCubic"));
    fan(g, W / 2, cy, PL(34, 22) * U, 6, B.prog(T, 0.6, 0.9, "outCubic"));
    [[PL(54, 46), 0.8], [PL(38, 34), 0.95], [PL(22, 22), 1.1]].forEach(([w, at], i) => tier(g, W / 2, cy - i * th, w * U, th + 0.5, B.prog(T, at, 0.25)));
    line(g, [[S.x, cy + th + 0.5], [S.r, cy + th + 0.5]], 0.3 * U);
    const ty = H * PL(0.3, 0.3), ts = PL(13, 12) * U;
    if (F.portrait) {
      stampTitle(g, "THE RULE", W / 2, ty, ts, 0.5);
      stampTitle(g, "OF 72", W / 2, ty + ts * 1.15, ts * 1.2, 1.1);
    } else stampTitle(g, "THE RULE OF 72", W / 2, ty, ts, 0.5, 0.06);
    const sy = cy + th + 0.5 + PL(6, 4) * U; // small text sits under the ground line, clear of the rays
    B.text(ctx, PL("HOW LONG MONEY\nTAKES TO DOUBLE", "HOW LONG MONEY TAKES TO DOUBLE"), W / 2, sy, { size: 5 * U, minSize: 5 * U, family: THIN, weight: 400, color: PAL.cream, letterSpacing: 0.16, maxW: S.w, maxLines: 2, baseline: "top", alpha: B.prog(T, 1.1, 0.4), ...thick(PAL.cream, 5 * U) });
  }

  function sceneDiagram(ctx, g) {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[1], base = H * PL(0.74, 0.74), th = PL(22, 11) * U;
    sunburst(g, W / 2, base - th * 2, 4 * U, PL(56, 40) * U, 26, B.prog(lt, 0.0, 1.0, "outCubic"));
    tier(g, W / 2, base - th, PL(58, 50) * U, th, B.prog(lt, 0.1, 0.35), 13);
    tier(g, W / 2, base - th * 2, PL(36, 36) * U, th, B.prog(lt, 0.45, 0.35), 9);
    tier(g, W / 2, base - th * 2.6, PL(14, 12) * U, th * 0.6, B.prog(lt, 0.8, 0.3), 5);
    line(g, [[S.x, base], [S.r, base]], 0.3 * U);
    plaque(ctx, g, W / 2, base - th * 0.5, PL(40, 34) * U, th * 0.62, [{ text: "SAVINGS", size: PL(4.6, 4.4) * U, display: true }], B.prog(lt, 0.4, 0.4));
    plaque(ctx, g, W / 2, base - th * 1.5, PL(34, 34) * U, th * 0.62, [{ text: "INTEREST", size: PL(4.4, 4.2) * U, display: true }], B.prog(lt, 0.7, 0.4));
    // mirrored notched arrows climbing both flanks: interest is added on top and earns interest too
    const ax = PL(36, 34) * U, p = B.prog(lt, 1.0, 0.6, "inOutCubic");
    [-1, 1].forEach((sd) => {
      decoArrow(g, W / 2 + sd * ax, base - 2 * U, W / 2 + sd * ax, base - th * 2.7, p, 1.2);
    });
    plaque(ctx, g, W / 2, base - th * 3.6, PL(70, 60) * U, PL(15, 14) * U, [{ text: "INTEREST EARNS", size: PL(4.6, 4.2) * U, display: true }, { text: "INTEREST TOO", size: PL(4.6, 4.2) * U, display: true }], B.prog(lt, 1.05, 0.4));
    B.text(ctx, "each year it joins the pile", W / 2, base + PL(6, 5) * U, { size: 5.2 * U, family: THIN, weight: 400, color: PAL.cream, letterSpacing: 0.08, alpha: B.prog(lt, 1.15, 0.4), ...thick(PAL.cream, 5.2 * U) });
    if (F.portrait) stampTitle(g, "HOW IT GROWS", W / 2, S.y + 9 * U, 8.5 * U, BEATS[1] + 0.1, 0.05);
  }

  function sceneNumber(ctx, g) {
    const W = F.W, H = F.H, lt = T - BEATS[2], cy = H * PL(0.42, 0.36), R = PL(38, 25) * U;
    sunburst(g, W / 2, cy, R * 1.05, R * PL(1.9, 1.6), 40, B.prog(lt, 0.05, 0.9, "outCubic"), Math.PI * 1.25);
    // gauge ring: ticks around a half circle
    const gp = B.prog(lt, 0.2, 0.8, "outCubic");
    for (let i = 0; i <= 24; i++) {
      const a = Math.PI + (i / 24) * Math.PI, k = B.clamp(gp * 1.4 - Math.abs(i / 24 - 0.5) * 1.2);
      if (k <= 0) continue;
      const r1 = R * (i % 6 ? 0.92 : 0.86);
      line(g, [[W / 2 + Math.cos(a) * r1, cy + Math.sin(a) * r1], [W / 2 + Math.cos(a) * R, cy + Math.sin(a) * R]], (i % 6 ? 0.2 : 0.45) * U);
    }
    g.save();
    g.strokeStyle = PAL.gold;
    g.lineWidth = 0.35 * U;
    g.beginPath();
    g.arc(W / 2, cy, R, Math.PI + (1 - gp) * Math.PI / 2, -(1 - gp) * Math.PI / 2);
    g.stroke();
    g.restore();
    odometer(g, W / 2, cy - R * 0.22, 72 * B.ease.outCubic(B.prog(lt, 0.3, 1.2)), 2, PL(24, 17) * U);
    line(g, [[W / 2 - R * 0.9, cy + R * 0.28], [W / 2 + R * 0.9, cy + R * 0.28]], 0.3 * U);
    chevrons(g, W / 2, cy + R * 0.38, 7, 1.2 * U, B.prog(lt, 1.2, 0.5), 1);
    const ph = PL(17, 14) * U, py = cy + R * PL(0.85, 0.85);
    plaque(ctx, g, W / 2, py, PL(86, 84) * U, ph, [{ text: "YEARS TO DOUBLE", size: PL(5, 4.6) * U, display: true }, { text: "= 72 ÷ the yearly rate in %", size: PL(4.8, 4.6) * U }], B.prog(lt, 1.0, 0.45));
    // worked examples on small teal plaques, a mirrored row under the rule; 6 % is the case the piece builds on
    [[4, 18, -1], [6, 12, 0], [9, 8, 1]].forEach(([r, y, sd], i) => {
      plaque(ctx, g, W / 2 + sd * 29 * U, py + ph / 2 + PL(11.5, 9.5) * U, PL(26, 27) * U, 15 * U, [{ text: "AT " + r + " %", size: 4.8 * U, display: true, color: PAL.cream }, { text: y + " YEARS", size: 4.8 * U, color: PAL.cream }], B.prog(lt, 1.15 + i * 0.1, 0.35), { fill: PAL.teal });
    });
  }

  function sceneSteps(ctx, g) {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[3], base = S.b - PL(3, 1) * U, th = PL(19, 11.5) * U, tc = PL(16, 11.5) * U;
    const lands = [0.2, 0.75, 1.3];
    sunburst(g, W / 2, base - th * 3, 12 * U, PL(72, 50) * U, 34, B.prog(lt, 0.1, 1.2, "outCubic"));
    g.save(); // a heading for the build, cleared before the crown lands
    g.globalAlpha = 1 - B.prog(lt, 2.0, 0.3);
    if (g.globalAlpha > 0) stampTitle(g, "HOW TO USE IT", W / 2, S.y + PL(9, 6) * U, PL(8.5, 7.5) * U, BEATS[3] + 0.15, 0.05);
    g.restore();
    const rows = [
      ["I", "RATE IS 6 %"],
      ["II", "DIVIDE 72 BY 6"],
      ["III", "12 YEARS"],
    ];
    rows.forEach(([num, txt], i) => {
      const w = PL(86 - i * 8, 80 - i * 10) * U, y = base - th * (i + 1), p = B.prog(lt, lands[i], 0.3);
      tier(g, W / 2, y, w, th, p, 11 - i * 2);
      plaque(ctx, g, W / 2, y + th * 0.5, w * 0.9, th * 0.7, [{ text: num + "  " + txt, size: PL(4.8, 4.4) * U, display: true }], B.prog(lt, lands[i] + 0.15, 0.35));
    });
    // the crown: a stepped spire with the doubling, and an oxblood accent bar
    const cp = B.prog(lt, 2.35, 0.4), top = base - th * 3;
    tier(g, W / 2, top - tc * 0.8, PL(22, 18) * U, tc * 0.8, cp, 5);
    tier(g, W / 2, top - tc * 1.4, PL(10, 8) * U, tc * 0.6, B.prog(lt, 2.55, 0.3), 3);
    if (cp > 0) {
      line(g, [[W / 2, top - tc * 1.4], [W / 2, top - tc * 1.4 - PL(9, 0.8) * U * cp]], 0.35 * U);
      ctx.fillStyle = PAL.oxblood;
      ctx.fillRect(W / 2 - PL(8, 6.5) * U * cp, top - tc * 0.48, PL(16, 13) * U * cp, 0.9 * U);
    }
    const tp = B.prog(lt, 2.5, 0.4), os = PL(8.5, 9) * U, hy = top - tc * 1.4 - PL(10, 2) * U - os;
    if (tp > 0) {
      odometer(g, W / 2 - os * 2.3, hy, 100, 3, os);
      decoArrow(g, W / 2 - os * 0.6, hy, W / 2 + os * 0.6, hy, tp, 1);
      odometer(g, W / 2 + os * 2.3, hy, 100 + 101 * B.ease.outCubic(B.prog(lt, 2.6, 0.8)), 3, os);
      B.text(ctx, "$100 at 6 % a year, 12 years on", W / 2, hy - os * PL(1.3, 1.15), { size: 5.2 * U, family: THIN, weight: 400, color: PAL.cream, letterSpacing: 0.06, alpha: B.prog(lt, 2.7, 0.4), ...thick(PAL.cream, 5.2 * U) });
    }
  }

  function sceneClose(ctx, g) {
    const W = F.W, H = F.H, S = F.safe, lt = T - BEATS[5], cy = H * PL(0.67, 0.66);
    sunburst(g, W / 2, cy, 8 * U, PL(80, 66) * U, 36, B.prog(lt, 0.0, 1.0, "outCubic"));
    fan(g, W / 2, cy, PL(30, 24) * U, 7, B.prog(lt, 0.15, 0.9, "outCubic"));
    [[PL(44, 50), 0.2], [PL(32, 36), 0.35], [PL(20, 22), 0.5], [PL(10, 10), 0.65]].forEach(([w, at], i) => tier(g, W / 2, cy - i * PL(7, 6) * U, w * U, PL(7, 6) * U + 0.5, B.prog(lt, at, 0.25), 7 - i));
    line(g, [[S.x, cy + PL(7, 6) * U + 0.5], [S.r, cy + PL(7, 6) * U + 0.5]], 0.3 * U);
    const ty = H * PL(0.27, 0.27), ts = PL(12, 11) * U;
    if (F.portrait) {
      stampTitle(g, "PATIENCE", W / 2, ty, ts, BEATS[5] + 0.3, 0.06);
      stampTitle(g, "COMPOUNDS", W / 2, ty + ts * 1.2, ts, BEATS[5] + 0.8, 0.06);
    } else stampTitle(g, "PATIENCE COMPOUNDS", W / 2, ty, ts, BEATS[5] + 0.4, 0.05);
    B.text(ctx, "DIVIDE 72 BY THE RATE", W / 2, cy + PL(7, 6) * U + PL(9, 7) * U, { size: 5 * U, minSize: 5 * U, family: THIN, color: PAL.cream, letterSpacing: 0.18, maxW: S.w, alpha: B.prog(lt, 0.9, 0.4), ...thick(PAL.cream, 5 * U) });
  }
  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneSteps, sceneClose];

  // ------------------------------------------------------------------ backdrop, doors and finishing
  function lacquer(ctx, W, H, t) {
    ctx.fillStyle = PAL.black;
    ctx.fillRect(0, 0, W, H);
    // satin sheen: very soft, broad lighter patches drifting a little (about 8 %)
    const D = Math.hypot(W, H);
    [[0.25, 0.2, 0.55], [0.8, 0.65, 0.5], [0.45, 0.95, 0.45]].forEach(([x, y, r], i) => {
      const g = B.radial(ctx, W * x + B.bob(t, 2 * U, 9, i * 0.3), H * y, 0, D * r, [[0, "rgba(255,240,215,0.075)"], [1, "rgba(255,240,215,0)"]]);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    });
  }
  /** Two gold-edged black doors closing from left and right (c 0 open .. 1 shut), fan ornament meeting in the middle. */
  function doors(ctx, W, H, c) {
    if (c <= 0) return;
    const half = (W / 2) * B.ease.inOutCubic(c);
    ctx.fillStyle = PAL.black;
    ctx.fillRect(0, 0, half, H);
    ctx.fillRect(W - half, 0, half, H);
    goldPass(ctx, W, H, "doors", (g) => {
      [-1, 1].forEach((sd) => {
        const edge = sd < 0 ? half : W - half, x0 = sd < 0 ? 0 : W;
        g.fillStyle = PAL.gold;
        g.fillRect(edge - (sd < 0 ? 1.2 * U : 0), 0, 1.2 * U, H);
        for (let i = 1; i <= 3; i++) line(g, [[edge - sd * i * 2.2 * U, 0], [edge - sd * i * 2.2 * U, H]], 0.16 * U, i === 2 ? PAL.foil : PAL.dark);
        // a half sunburst on each door: the two halves make one when the doors meet
        g.save();
        g.beginPath();
        g.rect(Math.min(x0, edge), 0, Math.abs(edge - x0), H);
        g.clip();
        for (let i = 0; i < 9; i++) {
          const a = -Math.PI / 2 + sd * ((i + 0.5) / 9) * (Math.PI / 2);
          line(g, [[edge, H / 2], [edge + Math.cos(a) * W * 0.45, H / 2 + Math.sin(a) * W * 0.45]], 0.2 * U, i % 2 ? PAL.dark : PAL.gold);
          const b = Math.PI / 2 - sd * ((i + 0.5) / 9) * (Math.PI / 2);
          line(g, [[edge, H / 2], [edge + Math.cos(b) * W * 0.45, H / 2 + Math.sin(b) * W * 0.45]], 0.2 * U, i % 2 ? PAL.dark : PAL.gold);
        }
        g.restore();
      });
    }, 0.4);
  }
  function doorClose(t) {
    let c = 0;
    DOORS.forEach((d) => (c = Math.max(c, B.span(t, d - 0.45, d) * (1 - B.span(t, d + 0.15, d + 0.6)))));
    return c;
  }

  function draw(ctx, W, H, t) {
    F = B.frame(W, H);
    U = F.u;
    T = t;
    lacquer(ctx, W, H, t);
    const bi = B.beat(t, BEATS, DUR).i;
    const cream = B.scratch("deco-cream", W, H); // cream text is drawn after the gold so it sits on the plaques
    goldPass(ctx, W, H, "scene", (g) => {
      border(g, W, H, B.prog(t, 0.0, 1.0, "inOutSine"));
      const m = PL(3.2, 2.6) * U + 3.4 * U, mt = PL(3.2, 2.6) * U + 6.4 * U;
      g.save(); // rays and arcs stay inside the border
      g.beginPath();
      g.rect(m, mt, W - 2 * m, H - 2 * mt);
      g.clip();
      SCENES[bi](cream, g);
      g.restore();
    });
    ctx.drawImage(cream.canvas, 0, 0);
    doors(ctx, W, H, doorClose(t));
    B.vignette(ctx, W, H, { amount: 0.5, inner: 0.5 });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12 });
  }

  // ------------------------------------------------------------------ sound: brass chimes per tier, foil shimmers, heavy door slides, a stately hum
  SOUND.define("deco-brass", (v, o) => {
    // bright brass-like chime: a few bright partials with a soft horn swell under a bell strike
    const f = v.hz(o.note || "C5");
    v.tone({ type: "sawtooth", f, a: 0.03, hold: 0.05, len: 0.5, peak: 0.05 });
    v.tone({ f, a: 0.002, len: 1.4, peak: 0.18 });
    v.tone({ f: f * 2.76, a: 0.001, len: 0.5, peak: 0.06 });
    v.tone({ f: f * 1.5, a: 0.002, len: 0.9, peak: 0.07 });
  }, { verb: 0.45 });
  SOUND.define("deco-door", (v, o) => {
    // heavy smooth slide: a long low-passed rumble, ending in a soft deep thud when the doors meet
    const d = o.dur ?? 0.45;
    v.noise({ filter: "lowpass", f: 380, f2: 900, glide: d, brown: true, a: d * 0.6, len: d * 0.5, peak: 0.45 });
    v.tone({ f: 70, f2: 45, glide: 0.25, at: d, a: 0.003, len: 0.35, peak: 0.45 });
  }, { verb: 0.3 });

  function score(k) {
    k.bed("drone", 0, DUR, { note: "C2", gain: 0.55 });
    k.bed("pad", 0, DUR, { notes: ["C3", "G3", "E4", "B4"], gain: 0.35, bright: 900 });
    k.at(0.0, "swell", { dur: 1.0, gain: 0.5 });
    [..."THE RULE OF 72"].forEach((c, i) => c !== " " && k.at(0.5 + i * 0.07, "tick", { gain: 0.5, pitch: i % 3 }));
    k.at(0.6, "sparkle", { gain: 0.4 }).at(1.2, "sparkle", { gain: 0.35, pitch: 3 });
    [0.8, 0.95, 1.1].forEach((at, i) => k.at(at, "deco-brass", { note: ["C5", "E5", "G5"][i], gain: 0.7 }));
    DOORS.forEach((d) => k.at(d - 0.45, "deco-door", { dur: 0.45 }).at(d + 0.15, "deco-door", { dur: 0.45, gain: 0.6, pitch: 2 }));
    // diagram: tiers land, arrows climb, plaque
    [2.4, 2.75, 3.1].forEach((at, i) => k.at(at, "deco-brass", { note: ["G4", "C5", "E5"][i], gain: 0.6 }));
    k.at(3.3, "swish", { dur: 0.6, gain: 0.4 }).at(3.7, "sparkle", { gain: 0.35 });
    // number: odometer clicks, the hum swells under the reveal
    k.at(4.65, "swell", { dur: 1.6, gain: 0.6 }).repeat(4.95, 0.08, 14, "tick", { gain: 0.4, vary: 1 });
    k.at(6.2, "chord", { notes: ["C4", "E4", "G4", "C5"], gain: 0.6 }).at(6.2, "sparkle", { gain: 0.4 });
    // steps: one brass chime per tier, a fanfare for the crown
    [7.15, 7.85, 8.55].forEach((at, i) => k.at(at, "deco-brass", { note: ["C5", "E5", "G5"][i] }));
    k.at(9.25, "deco-brass", { note: "C6" }).at(9.3, "chord", { notes: ["C4", "G4", "C5", "E5"], strum: 0.04, gain: 0.6 }).at(9.4, "sparkle", { gain: 0.45 });
    k.repeat(9.7, 0.07, 12, "tick", { gain: 0.3, vary: 1 });
    // close
    k.at(10.85, "swell", { dur: 1.2, gain: 0.5 });
    [..."PATIENCE COMPOUNDS"].forEach((c, i) => c !== " " && k.at(11.2 + i * 0.05, "tick", { gain: 0.4, pitch: i % 4 }));
    k.at(11.3, "deco-brass", { note: "G4" }).at(11.6, "deco-brass", { note: "C5" }).at(11.9, "chord", { notes: ["C3", "G3", "C4", "E4", "G4"], gain: 0.7, strum: 0.05 });
  }

  Player.register({
    id: "art-deco",
    name: "Art Deco",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Limelight&family=Poiret+One&display=swap",
      faces: ['400 20px "Limelight"', '400 20px "Poiret One"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three tiers", "Doubled", "Close"],
    stills: [1.9, 4.0, 6.3, 8.9, 10.25, 12.3],
    draw,
    score,
  });
})();
