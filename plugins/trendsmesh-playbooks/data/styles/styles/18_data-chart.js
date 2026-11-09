/* 18 Editorial Data Chart - reference animation.
 * Topic (setting, replace it): "Daylight swings with the seasons" - hours between sunrise and sunset through the
 * year at the equator, 30 N and 52 N (computed from the sunrise equation), why it happens (the 23.4 degree tilt).
 * Rendering (keep it): a quality-newspaper graphic on pale peach paper. Each panel opens with a thick ink rule with a
 * short wine block, a small-caps wine kicker, a bold serif headline, a lighter muted subhead and a plain note line.
 * Horizontal hairline gridlines only (darker zero line, value labels above the lines, unit on the top label), one wine
 * series with a pale wash fading downward, grey context series, every series named at its right end, a hollow ring on
 * the latest value, handwritten notes with wobbly curved leaders and small open arrowheads, a marker ring, waffle grids,
 * a numbered step strip and a hairline diagram, a hairline + small-caps source line at the bottom.
 * Finish (restraint): very light paper tooth that shifts a few times a second, a slow 1-2 % push per shot, thin wine
 * rings pulsing from the live end point. Motion: calm ease-in-out; the page scrolls up like a long-read and the
 * headline docks into a slim sticky header listing the sections. Every word on the page, kickers and source lines
 * included, is at least 4 u (small caps are drawn at 0.82 of their size, so they are set at 5 u).
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { paper: "#fdeee2", ink: "#302c2a", muted: "#6b645f", grid: "#dccdc0", context: "#a9a198", wine: "#8e1a44", wash: "#ecc9cf" };
  const SERIF = "Source Serif 4", HAND = "Kalam";
  const DUR = 13.5;
  const BEATS = [0, 1.9, 3.8, 5.7, 8.4, 11.2];
  const PANEL_AT = [0, 5.7, 8.4, 11.2]; // the page's four panels (the first holds title, chart and notes)
  const SECTIONS = ["Year", "Gap", "Why", "Takeaway"]; // short, so the sticky header fits a phone's width

  // ------------------------------------------------------------------ data (the setting): day length from the sunrise equation
  /** Hours from sunrise to sunset at latitude (deg) on day n of the year (Cooper's declination, -0.833 deg refraction). */
  function dayLength(lat, n) {
    const decl = B.deg(23.44) * Math.sin((B.TAU * (284 + n)) / 365), phi = B.deg(lat), h0 = B.deg(-0.833);
    const c = (Math.sin(h0) - Math.sin(phi) * Math.sin(decl)) / (Math.cos(phi) * Math.cos(decl));
    return (24 / Math.PI) * Math.acos(B.clamp(c, -1, 1));
  }
  const SERIES = [
    { name: "Equator", lat: 0 },
    { name: "30°N", lat: 30 },
    { name: "52°N", lat: 52, hi: true },
  ].map((s) => ({ ...s, v: Array.from({ length: 365 }, (_, i) => dayLength(s.lat, i + 1)) }));
  const HI = SERIES[2], MAXD = Math.max(...HI.v), MIND = Math.min(...HI.v), PEAK = HI.v.indexOf(MAXD);
  // the key number is the difference of the two values the chart prints (16.7 h and 7.7 h), so the page always adds up
  const GAP = +MAXD.toFixed(1) - +MIND.toFixed(1), LOW = HI.v.indexOf(MIND);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];

  // ------------------------------------------------------------------ editorial helpers (reuse these)
  let U = 1;
  const font = (size, weight = 400, style = "") => B.font(size, SERIF, weight, style);
  /** Set text line by line: each line rises a few px as it fades in (calm, no bounce). Returns the bottom y. */
  function setLines(ctx, str, x, y, o, t, at, gap = 0.12) {
    const m = B.measureText(ctx, str, { family: SERIF, lineH: 1.12, ...o });
    m.lines.forEach((ln, i) => {
      const p = B.prog(t, at + i * gap, 0.45, "inOutSine");
      if (p <= 0) return;
      B.text(ctx, ln, x, y + i * m.lh + (1 - p) * 1.2 * U, { family: SERIF, ...o, size: m.size, maxW: undefined, baseline: "top", align: "left", alpha: p, lineH: 1.12 });
    });
    return y + m.height;
  }
  /** Small caps: upper-case at a smaller size with open letter spacing. */
  function smallCaps(ctx, str, x, y, size, color, alpha = 1, align = "left") {
    return B.text(ctx, str.toUpperCase(), x, y, { family: SERIF, size: size * 0.82, weight: 600, color, letterSpacing: 0.09, baseline: "top", align, alpha });
  }
  /** The panel opener: a thick ink rule drawn across, with a short heavier wine block at its left end. */
  function openerRule(ctx, x, y, w, p) {
    if (p <= 0) return;
    ctx.fillStyle = PAL.ink;
    ctx.fillRect(x, y, w * B.ease.inOutCubic(p), 0.45 * U);
    ctx.fillStyle = PAL.wine;
    ctx.fillRect(x, y - 0.35 * U, Math.min(1, p * 3) * 9 * U, 1.15 * U);
  }
  /** Handwritten note that writes itself on left to right (a clip sweeping across), in ink or muted grey. */
  function handNote(ctx, str, x, y, p, o = {}) {
    if (p <= 0) return null;
    const size = o.size ?? 3.4 * U;
    const m = B.measureText(ctx, str, { size, family: HAND, weight: 400, maxW: o.maxW ?? 30 * U, lineH: 1.05 });
    const n = m.lines.length;
    m.lines.forEach((ln, i) => {
      const lp = B.clamp(p * n - i);
      if (lp <= 0) return;
      ctx.save();
      ctx.beginPath();
      ctx.rect(x - 2 * U, y + i * m.lh - U, (m.width + 4 * U) * lp, m.lh + 2 * U);
      ctx.clip();
      B.text(ctx, ln, x, y + i * m.lh, { size, family: HAND, weight: 400, color: o.color || PAL.ink, align: "left", baseline: "top" });
      ctx.restore();
    });
    return { w: m.width, h: m.height };
  }
  /** Slightly wobbly curved leader from (x1, y1) to the target, ending in a small open arrowhead. */
  function leader(ctx, x1, y1, x2, y2, p, bend = 0.3, seed = 1, color = PAL.ink) {
    if (p <= 0) return;
    const pts = B.wobble(B.arcBetween(x1, y1, x2, y2, bend, 40), { amp: 0.25 * U, freq: 2.5, seed });
    B.arrow(ctx, pts, { p, width: 0.3 * U, color, head: 1.6 * U, headStyle: "open" });
  }
  /** Marker ring: a hand-drawn loop that overshoots its own start. */
  function markerRing(ctx, cx, cy, rx, ry, p, seed = 3) {
    if (p <= 0) return;
    const r = B.rng(seed), a0 = r.range(-2.4, -1.8), pts = [];
    for (let i = 0; i <= 80; i++) {
      const k = i / 80, a = a0 + k * B.TAU * 1.13, grow = 1 + 0.06 * k + B.noise1(k * 4, seed) * 0.03;
      pts.push([cx + Math.cos(a) * rx * grow, cy + Math.sin(a) * ry * grow]);
    }
    B.strokeReveal(ctx, pts, B.ease.inOutSine(p), { width: 0.42 * U, color: PAL.wine });
  }
  /** Lining figures: each character centred in a fixed slot, so a counting number never jiggles. */
  function liningNumber(ctx, str, x, y, size, color) {
    ctx.save();
    ctx.font = font(size, 600);
    ctx.fillStyle = color;
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "center";
    const slot = ctx.measureText("0").width;
    let xx = x;
    for (const ch of str) {
      const w = /[0-9]/.test(ch) ? slot : ctx.measureText(ch).width;
      ctx.fillText(ch, xx + w / 2, y);
      xx += w;
    }
    ctx.restore();
    return xx - x;
  }
  /** Waffle grid: n squares in rows of `cols`, the first `on` in wine, the rest grey; squares settle in one by one. */
  function waffle(ctx, x, y, cols, n, on, cell, p) {
    const gap = cell * 0.16;
    for (let i = 0; i < n; i++) {
      const k = B.clamp(p * n * 1.15 - i);
      if (k <= 0) continue;
      const cx = x + (i % cols) * (cell + gap), cy = y + Math.floor(i / cols) * (cell + gap);
      ctx.globalAlpha = B.ease.inOutSine(k);
      ctx.fillStyle = i < on ? PAL.wine : PAL.grid;
      ctx.fillRect(cx, cy, cell, cell);
    }
    ctx.globalAlpha = 1;
    return { w: cols * (cell + gap) - gap, h: Math.ceil(n / cols) * (cell + gap) - gap };
  }
  /** The hairline above the small-caps source line that closes the frame. */
  function sourceLine(ctx, F, y, str, a = 1) {
    const S = F.safe;
    ctx.fillStyle = B.rgba(PAL.ink, 0.5 * a);
    ctx.fillRect(S.x, y, S.w, 0.14 * U);
    smallCaps(ctx, str, S.x, y + 0.9 * U, 5 * U, PAL.muted, a);
  }
  const SOURCE = "Source: sunrise equation";

  // ------------------------------------------------------------------ layout (per aspect, from the safe area)
  function lay(F) {
    const S = F.safe, P = F.portrait;
    return {
      P, S,
      head: P ? 7 * U : 6.4 * U,
      sub: P ? 4.4 * U : 4.3 * U,
      note: 4.0 * U,
      kick: 5.0 * U, // small caps: seen at 4.1 u
      label: 4.0 * U,
      hand: 4.3 * U,
      srcY: S.b - (P ? 6.8 : 6.6) * U,
      sticky: P ? 12 * U : 6.6 * U, // height of the docked header
    };
  }

  // ------------------------------------------------------------------ panel 0: title, chart, notes
  function panelChart(ctx, F, Lo, t) {
    const S = Lo.S, P = Lo.P;
    openerRule(ctx, S.x, S.y, S.w, B.prog(t, 0.05, 0.6));
    smallCaps(ctx, "Earth & sky", S.x, S.y + 1.6 * U, Lo.kick, PAL.wine, B.prog(t, 0.35, 0.4, "inOutSine"));
    let y = S.y + 1.6 * U + Lo.kick * 1.3;
    y = setLines(ctx, "Daylight swings with the seasons", S.x, y, { size: Lo.head, weight: 700, color: PAL.ink, maxW: S.w }, t, 0.45);
    // 9:16 keeps the deck to one line each, so the chart takes the height
    y = setLines(ctx, P ? "Daylight hours at three latitudes" : "Hours from sunrise to sunset through the year, at three latitudes", S.x, y + 0.8 * U, { size: Lo.sub, weight: 400, color: PAL.muted, maxW: S.w }, t, 0.55);
    y = setLines(ctx, P ? "Hours per day, for a typical year" : "Hours per day, computed for a typical year", S.x, y + 0.6 * U, { size: Lo.note, weight: 400, color: PAL.muted, maxW: S.w }, t, 0.7);

    // chart frame: gridlines and context lines set during the title, so the page is never bare
    const labW = P ? 17 * U : 17 * U;
    // the chart takes every pixel of height the header leaves (9:16: about two thirds of the text-safe box)
    // the value labels sit in a gutter left of the plot, so no line ever runs over them
    const gut = 5 * U, C = { x: S.x + gut, y: y + (P ? 6 : 7) * U, w: S.w - labW - gut, b: Lo.srcY - (P ? 5.6 : 5) * U };
    C.h = C.b - C.y;
    const X = (d) => C.x + (d / 364) * C.w, Y = (h) => C.b - (h / 20) * C.h;
    // horizontal hairlines only, bottom first, left to right; labels sit above each line at the left edge
    [0, 4, 8, 12, 16, 20].forEach((h, i) => {
      const p = B.prog(t, 0.15 + i * 0.07, 0.5, "inOutCubic");
      if (p <= 0) return;
      ctx.fillStyle = h === 0 ? PAL.ink : PAL.grid;
      ctx.fillRect(S.x, Y(h) - (h === 0 ? 0.12 * U : 0.06 * U), (C.w + gut + labW * 0.25) * p, h === 0 ? 0.24 * U : 0.13 * U);
      const lp = B.prog(t, 0.35 + i * 0.07, 0.4, "inOutSine");
      if (lp > 0) B.text(ctx, h === 20 ? "20 hours" : String(h), S.x, Y(h) - 0.5 * U, { size: Lo.label, family: SERIF, weight: 400, color: PAL.muted, align: "left", baseline: "bottom", alpha: lp });
    });
    MONTHS.forEach((m, i) => {
      // a phone-width chart uses the initials, as newspapers do
      const a = B.prog(t, 0.5 + i * 0.02, 0.4, "inOutSine");
      if (a > 0) B.text(ctx, P ? m[0] : m, X((MONTH_START[i] + MONTH_START[i + 1]) / 2), C.b + 1.2 * U, { size: Lo.label, family: SERIF, weight: 400, color: PAL.muted, baseline: "top", alpha: a });
    });
    // right-end names, nudged apart so they never touch: equator, 30 N, then the highlight's name (value below it)
    const endY = [Y(SERIES[0].v[364]), Y(SERIES[1].v[364]), Y(HI.v[364])];
    for (let i = 1; i < 3; i++) endY[i] = Math.max(endY[i], endY[i - 1] + Lo.label * 1.15);
    const pts = (s, upto = 364) => s.v.slice(0, Math.floor(upto) + 1).map((v, d) => [X(d), Y(v)]);
    // all three lines settle in grey first (context), then 52 N is drawn over in wine
    SERIES.forEach((s, i) => {
      const a = B.prog(t, 0.35 + i * 0.1, 0.35, "inOutSine");
      if (a <= 0) return;
      ctx.save();
      ctx.globalAlpha = a;
      ctx.strokeStyle = PAL.context;
      ctx.lineWidth = 0.3 * U;
      ctx.lineJoin = "round";
      ctx.beginPath();
      B.poly(ctx, pts(s));
      ctx.stroke();
      if (!s.hi) B.text(ctx, s.name, C.x + C.w + 1.2 * U, endY[i], { size: Lo.label, family: SERIF, weight: 600, color: PAL.muted, align: "left", baseline: "middle" });
      ctx.restore();
    });
    // the highlight grows left to right, a dot leading its tip, the wash filling in behind
    const gp = B.prog(t, 2.1, 1.6, "inOutSine"), tipD = gp * 364;
    if (gp > 0) {
      const hp = pts(HI, tipD);
      ctx.save();
      ctx.beginPath();
      B.poly(ctx, [[hp[0][0], C.b], ...hp, [hp[hp.length - 1][0], C.b]], true);
      ctx.fillStyle = B.linear(ctx, 0, Y(MAXD), 0, C.b, [B.rgba(PAL.wash, 0.85), B.rgba(PAL.wash, 0)]);
      ctx.fill();
      ctx.strokeStyle = PAL.wine;
      ctx.lineWidth = 0.75 * U;
      ctx.lineJoin = ctx.lineCap = "round";
      ctx.beginPath();
      B.poly(ctx, hp);
      ctx.stroke();
      const [tx, ty] = hp[hp.length - 1];
      if (gp < 1) {
        ctx.fillStyle = PAL.wine;
        ctx.beginPath();
        ctx.arc(tx, ty, 0.9 * U, 0, B.TAU);
        ctx.fill();
      } else {
        // the latest value: a hollow ring, the name and the value beside it, and thin live rings during holds
        for (let k = 0; k < 2; k++) {
          const ph = B.fract((t - 3.8 - k * 0.8) / 1.6);
          if (t > 3.8 + k * 0.8) {
            ctx.strokeStyle = B.rgba(PAL.wine, 0.5 * (1 - ph));
            ctx.lineWidth = 0.15 * U;
            ctx.beginPath();
            ctx.arc(tx, ty, (1.1 + ph * 3.2) * U, 0, B.TAU);
            ctx.stroke();
          }
        }
        ctx.fillStyle = PAL.paper;
        ctx.strokeStyle = PAL.wine;
        ctx.lineWidth = 0.4 * U;
        ctx.beginPath();
        ctx.arc(tx, ty, 1.1 * U, 0, B.TAU);
        ctx.fill();
        ctx.stroke();
        const a = B.prog(t, 3.7, 0.4, "inOutSine");
        B.text(ctx, HI.name, C.x + C.w + 2.6 * U, endY[2], { size: Lo.label * 1.05, family: SERIF, weight: 700, color: PAL.wine, align: "left", baseline: "middle", alpha: a });
      }
    }
    // notes write on once the line has passed their point, then their leaders draw to the target
    const nt = 3.85;
    const peak = [X(PEAK), Y(MAXD)];
    const n1x = P ? X(228) : X(222), n1y = Y(P ? 19.6 : 19.8);
    // every note, leader and ring is complete well before the beat's still (4.9 s)
    const n1 = handNote(ctx, "longest day: " + MAXD.toFixed(1) + " hours", n1x, n1y, B.prog(t, nt, 0.45), { size: Lo.hand, maxW: P ? 30 * U : 52 * U });
    if (n1) leader(ctx, n1x - 0.8 * U, n1y + Lo.hand * 0.6, peak[0] + 1.6 * U, peak[1] - 0.6 * U, B.prog(t, nt + 0.4, 0.3, "inOutSine"), 0.35, 4);
    markerRing(ctx, peak[0], peak[1], (P ? 6 : 5) * U, (P ? 3.4 : 3) * U, B.prog(t, nt + 0.6, 0.4), 7);
    const n2x = X(P ? 34 : 30), n2y = Y(P ? 19.9 : 19.7);
    const n2 = handNote(ctx, P ? "equator:\n12 h\nall year" : "equator: 12 h all year", n2x, n2y, B.prog(t, nt + 0.2, 0.4), { size: Lo.hand, color: PAL.muted, maxW: P ? 28 * U : 50 * U });
    // its leader ends with the arrowhead on the equator line itself
    if (n2) leader(ctx, n2x + 3 * U, n2y + n2.h + 0.3 * U, X(P ? 58 : 46), Y(12) - 0.25 * U, B.prog(t, nt + 0.55, 0.35, "inOutSine"), -0.25, 6, PAL.muted);
    // the shortest day, named on the chart, with a leader to the low point in December
    // set left of the low, its arrow rising straight up to a dot on 21 December, clear of the end ring
    const n3s = "shortest day: " + MIND.toFixed(1) + " hours", n3o = { size: Lo.hand, maxW: P ? 26 * U : 48 * U };
    const lx = X(LOW), ly = Y(MIND), n3x = lx - B.measureText(ctx, n3s, { ...n3o, family: HAND, lineH: 1.05 }).width - (P ? 1 : 2) * U, n3y = Y(P ? 5.6 : 4.6);
    if (handNote(ctx, n3s, n3x, n3y, B.prog(t, nt + 0.5, 0.3), n3o)) {
      const lp = B.prog(t, nt + 0.75, 0.25, "inOutSine");
      leader(ctx, lx - (P ? 0.8 : 2) * U, n3y - 0.6 * U, lx, ly + 1.3 * U, lp, -0.12, 8);
      ctx.fillStyle = PAL.ink; ctx.globalAlpha = B.clamp(lp * 3); ctx.beginPath(); ctx.arc(lx, ly, 0.7 * U, 0, B.TAU); ctx.fill(); ctx.globalAlpha = 1;
    }
    sourceLine(ctx, F, Lo.srcY, SOURCE, B.prog(t, 0.6, 0.5));
  }

  // ------------------------------------------------------------------ panel 1: the key number and two waffles
  function panelNumber(ctx, F, Lo, t) {
    const S = Lo.S, P = Lo.P, top = S.y + Lo.sticky + 2 * U;
    openerRule(ctx, S.x, top, S.w, B.prog(t, -0.3, 0.6));
    smallCaps(ctx, "The gap", S.x, top + 1.6 * U, Lo.kick, PAL.wine, B.prog(t, -0.1, 0.4));
    let y = setLines(ctx, "Nine more hours of light in June", S.x, top + 1.6 * U + Lo.kick * 1.3, { size: Lo.head * 0.9, weight: 700, color: PAL.ink, maxW: S.w }, t, 0.0);
    // the key figure: large serif numerals counting up, digits held still in lining slots
    const size = P ? 22 * U : 27 * U, p = B.prog(t, 0.35, 1.0, "inOutCubic");
    const nx = S.x + size * 0.36, ny = y + size * 0.95; // room for the marker ring inside the margin
    const shown = (Math.round(p * GAP * 10) / 10).toFixed(1);
    const nw = liningNumber(ctx, shown, nx, ny, size, PAL.ink);
    B.text(ctx, "hours", nx + nw * 1.3 + U, ny - size * 0.1, { size: size * 0.24, family: SERIF, weight: 600, color: PAL.ink, align: "left", baseline: "bottom", alpha: B.prog(t, 1.2, 0.4) });
    markerRing(ctx, nx + nw * 0.5, ny - size * 0.36, nw * 0.68, size * 0.52, B.prog(t, 1.25, 0.5), 11);
    const noteY = ny + size * 0.24, noteStr = "between the shortest and\nlongest day at 52°N", noteW = P ? 70 * U : 60 * U;
    handNote(ctx, noteStr, S.x + 2 * U, noteY, B.prog(t, 1.25, 0.45), { size: Lo.hand, maxW: noteW });
    // waffles: one square = one hour of the day, wine = daylight (9:16: rows of 8 under the note; 16:9: rows of 6 beside)
    const noteH = B.measureText(ctx, noteStr, { size: Lo.hand, family: HAND, maxW: noteW, lineH: 1.05 }).height;
    const wy = P ? noteY + noteH + 3 * U : y + 4 * U, cell = P ? 4.4 * U : 5.4 * U, cols = P ? 8 : 6;
    const groups = [{ label: "21 June", on: Math.round(MAXD) }, { label: "21 December", on: Math.round(MIND) }];
    groups.forEach((g, i) => {
      const gx = P ? S.x + i * S.w * 0.52 : S.x + S.w * (0.52 + i * 0.25);
      const gy = wy;
      const a = B.prog(t, 0.6 + i * 0.2, 0.4, "inOutSine");
      B.text(ctx, g.label, gx, gy, { size: Lo.label * 1.05, family: SERIF, weight: 700, color: PAL.ink, align: "left", baseline: "top", alpha: a });
      B.text(ctx, g.on + " of 24 hours light", gx, gy + Lo.label * 1.3, { size: Lo.label, family: SERIF, weight: 400, color: PAL.wine, align: "left", baseline: "top", alpha: a });
      // all 24 squares of each day are down well before the beat's still
      waffle(ctx, gx, gy + Lo.label * 2.9, cols, 24, g.on, cell, B.prog(t, 0.7 + i * 0.2, 0.6, "inOutSine"));
    });
    smallCaps(ctx, "One square = one hour", P ? S.x : S.x + S.w * 0.52, wy + Lo.label * 2.9 + cell * (24 / cols) * 1.16 + 2 * U, Lo.kick, PAL.muted, B.prog(t, 1.6, 0.4));
    sourceLine(ctx, F, Lo.srcY, SOURCE);
  }

  // ------------------------------------------------------------------ panel 2: why - a step strip and a hairline diagram
  function earth(ctx, x, y, r, tiltToward, lit) {
    // hairline node: day half washed toward the Sun, tilted axis, equator, a 52 N marker
    const tilt = B.deg(23.4) * (tiltToward ? 1 : 1);
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = PAL.paper;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, B.TAU);
    ctx.fill();
    ctx.fillStyle = B.rgba(PAL.wash, 0.9);
    ctx.beginPath();
    ctx.arc(0, 0, r, lit > 0 ? -Math.PI / 2 : Math.PI / 2, lit > 0 ? Math.PI / 2 : Math.PI * 1.5);
    ctx.fill();
    ctx.strokeStyle = PAL.ink;
    ctx.lineWidth = 0.22 * U;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, B.TAU);
    ctx.stroke();
    ctx.rotate(tilt);
    ctx.lineWidth = 0.28 * U;
    ctx.beginPath();
    ctx.moveTo(0, -r * 1.35);
    ctx.lineTo(0, r * 1.35);
    ctx.stroke();
    ctx.strokeStyle = PAL.context;
    ctx.lineWidth = 0.15 * U;
    ctx.beginPath();
    ctx.moveTo(-r, 0);
    ctx.lineTo(r, 0);
    ctx.stroke();
    ctx.strokeStyle = PAL.wine;
    ctx.lineWidth = 0.3 * U;
    const yl = -Math.sin(B.deg(52)) * r, xl = Math.cos(B.deg(52)) * r;
    ctx.beginPath();
    ctx.moveTo(-xl, yl);
    ctx.lineTo(xl, yl);
    ctx.stroke();
    ctx.restore();
  }
  function panelWhy(ctx, F, Lo, t) {
    const S = Lo.S, P = Lo.P, top = S.y + Lo.sticky + 2 * U;
    openerRule(ctx, S.x, top, S.w, B.prog(t, -0.3, 0.6));
    smallCaps(ctx, "Why", S.x, top + 1.6 * U, Lo.kick, PAL.wine, B.prog(t, -0.1, 0.4));
    const y = setLines(ctx, "The tilt decides who gets the long days", S.x, top + 1.6 * U + Lo.kick * 1.3, { size: Lo.head * 0.82, weight: 700, color: PAL.ink, maxW: S.w }, t, 0.0);
    // numbered step strip across the top: the current step in wine
    const steps = ["Earth's axis leans 23.4°, always the same way", "June: the north leans toward the Sun", "December: the north leans away"];
    const stepAt = [0.3, 0.8, 1.3], cur = stepAt.reduce((a, s, i) => (t >= s ? i : a), -1);
    const sw = S.w / 3, sy = y + 3 * U, stepH = Math.max(...steps.map((s) => B.measureText(ctx, s, { size: Lo.label, family: SERIF, weight: 600, maxW: sw - 3 * U, lineH: 1.15 }).height));
    steps.forEach((s, i) => {
      const a = B.prog(t, stepAt[i] - 0.25, 0.4, "inOutSine");
      if (a <= 0) return;
      const sx = S.x + i * sw, on = i === cur;
      ctx.globalAlpha = a;
      ctx.fillStyle = on ? PAL.wine : PAL.grid;
      ctx.fillRect(sx, sy, sw - 2 * U, on ? 0.5 * U : 0.25 * U);
      ctx.globalAlpha = 1;
      B.text(ctx, String(i + 1), sx, sy + 1.4 * U, { size: Lo.sub * 1.3, family: SERIF, weight: 700, color: on ? PAL.wine : PAL.muted, align: "left", baseline: "top", alpha: a });
      B.text(ctx, s, sx, sy + 1.4 * U + Lo.sub * 1.55, { size: Lo.label, family: SERIF, weight: on ? 600 : 400, color: on ? PAL.ink : PAL.muted, align: "left", baseline: "top", maxW: sw - 3 * U, alpha: a, lineH: 1.15 });
    });
    // the hairline diagram: Sun node, orbit, Earth nodes; links darker where the light is stronger
    const dy0 = sy + 1.4 * U + Lo.sub * 1.55 + stepH + 3 * U, dyb = Lo.srcY - 2 * U, er = P ? 8.5 * U : 7 * U;
    const cx = S.cx, cy = dy0 + er * (P ? 1.6 : 1.35), rx = S.w * 0.36, ry = (dyb - dy0) * (P ? 0.2 : 0.25), lo = P ? 1.4 : 1.15;
    const a0 = B.prog(t, 0.2, 0.6, "inOutSine");
    ctx.save();
    ctx.globalAlpha = a0;
    ctx.strokeStyle = PAL.grid;
    ctx.lineWidth = 0.18 * U;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, B.TAU);
    ctx.stroke();
    ctx.fillStyle = PAL.wine;
    ctx.beginPath();
    ctx.arc(cx, cy, er * 0.9, 0, B.TAU);
    ctx.fill();
    ctx.restore();
    B.text(ctx, "Sun", cx, cy + er * 1.5, { size: Lo.label, family: SERIF, weight: 600, color: PAL.ink, baseline: "top", alpha: a0 });
    const link = (x, a, w) => {
      ctx.strokeStyle = B.rgba(PAL.ink, a);
      ctx.lineWidth = w;
      ctx.beginPath();
      ctx.moveTo(cx + Math.sign(x - cx) * er, cy);
      ctx.lineTo(x - Math.sign(x - cx) * er * 1.2, cy);
      ctx.stroke();
    };
    // step 1: one Earth on the orbit shows the lean
    const e1 = B.prog(t, 0.35, 0.4, "inOutSine");
    if (e1 > 0 && t < 0.8) {
      ctx.globalAlpha = e1;
      earth(ctx, cx - rx, cy, er, true, 1);
      ctx.globalAlpha = 1;
      handNote(ctx, "23.4° lean", cx - rx + er * 1.6, cy - er * (P ? 1.5 : 2.6), B.prog(t, 0.5, 0.35), { size: Lo.hand });
    }
    // step 2: June, north leaning in: a strong link, long days
    const e2 = B.prog(t, 0.8, 0.4, "inOutSine");
    if (e2 > 0) {
      ctx.globalAlpha = e2;
      link(cx - rx, 0.85, 0.32 * U);
      earth(ctx, cx - rx, cy, er, true, 1);
      ctx.globalAlpha = 1;
      B.text(ctx, "June", cx - rx, cy + er * 1.6, { size: Lo.label, family: SERIF, weight: 700, color: PAL.ink, baseline: "top", alpha: e2 });
      handNote(ctx, "long days", cx - rx - er, cy + er * 1.6 + Lo.label * lo, B.prog(t, 1.0, 0.4), { size: Lo.hand });
    }
    // step 3: December, north leaning away: a faint link, short days
    const e3 = B.prog(t, 1.3, 0.4, "inOutSine");
    if (e3 > 0) {
      ctx.globalAlpha = e3;
      link(cx + rx, 0.3, 0.16 * U);
      earth(ctx, cx + rx, cy, er, true, -1);
      ctx.globalAlpha = 1;
      B.text(ctx, "December", cx + rx, cy + er * 1.6, { size: Lo.label, family: SERIF, weight: 700, color: PAL.ink, baseline: "top", alpha: e3 });
      const sw2 = B.measureText(ctx, "short days", { size: Lo.hand, family: HAND }).width;
      handNote(ctx, "short days", Math.min(S.r - sw2 - U, cx + rx - er), cy + er * 1.6 + Lo.label * lo, B.prog(t, 1.4, 0.4), { size: Lo.hand, color: PAL.muted });
    }
    sourceLine(ctx, F, Lo.srcY, "Diagram not to scale");
  }

  // ------------------------------------------------------------------ panel 3: the takeaway
  function panelClose(ctx, F, Lo, t) {
    const S = Lo.S, P = Lo.P, top = S.y + Lo.sticky + 2 * U;
    openerRule(ctx, S.x, top, S.w, B.prog(t, -0.3, 0.6));
    smallCaps(ctx, "Takeaway", S.x, top + 1.6 * U, Lo.kick, PAL.wine, B.prog(t, -0.1, 0.4));
    let y = setLines(ctx, "Tilt, not distance, sets the length of our days", S.x, top + 1.6 * U + Lo.kick * 1.3, { size: Lo.head, weight: 700, color: PAL.ink, maxW: S.w }, t, 0.05);
    y = setLines(ctx, "Earth is nearest the Sun in early January, in the middle of the northern winter.", S.x, y + 1 * U, { size: Lo.sub, weight: 400, color: PAL.muted, maxW: S.w }, t, 0.4);
    // the highlight line once more, small, with its peak ringed
    const C = { x: S.x, y: y + (P ? 10 : 13) * U, w: P ? S.w : S.w * 0.82, b: Lo.srcY - (P ? 10 : 7) * U };
    const X = (d) => C.x + (d / 364) * C.w, Y = (h) => C.b - ((h - 6) / 12) * (C.b - C.y);
    const gp = B.prog(t, 0.6, 1.0, "inOutSine");
    ctx.fillStyle = PAL.ink;
    ctx.fillRect(C.x, C.b, C.w * B.prog(t, 0.3, 0.5, "inOutCubic"), 0.2 * U);
    if (gp > 0) {
      const hp = HI.v.slice(0, Math.floor(gp * 364) + 1).map((v, d) => [X(d), Y(v)]);
      ctx.strokeStyle = PAL.wine;
      ctx.lineWidth = 0.7 * U;
      ctx.lineJoin = ctx.lineCap = "round";
      ctx.beginPath();
      B.poly(ctx, hp);
      ctx.stroke();
    }
    B.text(ctx, "52°N daylight, Jan to Dec", C.x, C.b + 1.2 * U, { size: Lo.label, family: SERIF, weight: 400, color: PAL.muted, align: "left", baseline: "top", alpha: B.prog(t, 0.6, 0.4) });
    markerRing(ctx, X(PEAK), Y(MAXD), 4.5 * U, 2.6 * U, B.prog(t, 1.1, 0.5), 21);
    // the note sits up and to the right of the ringed peak, with a leader down to the ring
    const nx = X(PEAK) + (P ? 6 : 8) * U, ny = Y(MAXD) - (P ? 9 : 10) * U;
    handNote(ctx, "the same Sun, a different angle", nx, ny, B.prog(t, 1.3, 0.5), { size: Lo.hand, maxW: P ? 34 * U : 44 * U });
    leader(ctx, nx - U, ny + Lo.hand * 0.6, X(PEAK) + 3.5 * U, Y(MAXD) - 2.4 * U, B.prog(t, 1.75, 0.3, "inOutSine"), -0.3, 9);
    sourceLine(ctx, F, Lo.srcY, SOURCE);
  }

  const PANELS = [panelChart, panelNumber, panelWhy, panelClose];

  // ------------------------------------------------------------------ the page: a long-read that scrolls, with a sticky header
  function scrollPos(t) {
    let s = 0;
    for (let i = 1; i < PANEL_AT.length; i++) s += B.span(t, PANEL_AT[i] - 0.75, PANEL_AT[i] - 0.05, "inOutCubic");
    return s;
  }
  function stickyHeader(ctx, F, Lo, t, s) {
    const S = Lo.S, P = Lo.P, a = B.clamp(s * 1.4);
    if (a <= 0) return;
    const h = Lo.sticky;
    ctx.fillStyle = PAL.paper;
    ctx.fillRect(0, 0, F.W, S.y + h);
    ctx.save();
    ctx.globalAlpha = a;
    // the headline docks in: it slides up from below into the slim bar
    const dy = (1 - B.ease.inOutCubic(a)) * 3 * U;
    B.text(ctx, "Daylight and the seasons", S.x, S.y + U + dy, { size: 4.4 * U, family: SERIF, weight: 700, color: PAL.ink, align: "left", baseline: "top" });
    const cur = Math.round(s);
    let x = P ? S.x : S.x + S.w * 0.46;
    const ry = P ? S.y + 6.4 * U : S.y + 1.3 * U;
    SECTIONS.forEach((name, i) => {
      const on = i === cur;
      const r = B.text(ctx, name.toUpperCase(), x, ry + dy, { size: 4.1 * U, family: SERIF, weight: on ? 700 : 600, color: on ? PAL.wine : PAL.muted, align: "left", baseline: "top", letterSpacing: 0.06 });
      if (on) {
        ctx.fillStyle = PAL.wine;
        ctx.fillRect(x, ry + dy + r.height + 0.3 * U, r.width, 0.25 * U);
      }
      x += r.width + (P ? 3.4 : 3) * U;
    });
    ctx.restore();
    ctx.fillStyle = PAL.grid;
    ctx.fillRect(0, S.y + h - 0.1 * U, F.W, 0.14 * U);
  }

  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    U = F.u;
    const Lo = lay(F), s = scrollPos(t);
    ctx.fillStyle = PAL.paper;
    ctx.fillRect(0, 0, W, H);
    // slow push: the camera creeps in by about 1.5 % across each shot, then the scroll starts a fresh shot
    const shot = Math.floor(s + 1e-6), shotStart = shot === 0 ? 0 : PANEL_AT[shot], shotEnd = PANEL_AT[shot + 1] ? PANEL_AT[shot + 1] - 0.75 : DUR;
    const push = 1 + 0.015 * B.span(t, shotStart, shotEnd, "inOutSine") * (s === shot ? 1 : 0);
    PANELS.forEach((panel, i) => {
      const off = (i - s) * H;
      if (Math.abs(off) >= H) return;
      ctx.save();
      ctx.translate(0, off);
      if (Math.abs(i - s) < 1e-3) {
        ctx.translate(Lo.S.cx, Lo.S.cy);
        ctx.scale(push, push);
        ctx.translate(-Lo.S.cx, -Lo.S.cy);
      }
      panel(ctx, F, Lo, t - PANEL_AT[i]);
      ctx.restore();
    });
    stickyHeader(ctx, F, Lo, t, s);
    // paper tooth: fine grain that shifts a few times a second
    B.grain(ctx, W, H, { amount: 0.03, t, fps: 4, mode: "multiply" });
  }

  // ------------------------------------------------------------------ sound: wheel notches and paper glide, felt-tip notes, dry digit clicks, one deeper hit
  SOUND.define("chart-notch", (v) => {
    v.noise({ filter: "bandpass", f: 3200, q: 3, a: 0.0004, len: 0.008, peak: 0.28 });
    v.tone({ type: "triangle", f: 1600, a: 0.0004, len: 0.01, peak: 0.05 });
  }, { verb: 0.03 });
  SOUND.define("chart-glide", (v) => {
    const d = v.dur ?? 0.7;
    v.noise({ filter: "lowpass", f: 700, a: d * 0.45, hold: d * 0.1, len: d * 0.45, peak: 0.12, brown: true });
  }, { verb: 0.1 });
  SOUND.define("chart-pen", (v) => {
    // a felt tip on paper: soft band noise, a slight rasp, as long as the stroke
    const d = v.dur ?? 0.5;
    v.noise({ filter: "bandpass", f: 2300, q: 1.1, a: 0.02, hold: Math.max(0, d - 0.06), len: 0.05, peak: 0.07 });
    v.grains({ span: d, count: Math.round(d * 40), filter: "bandpass", f: 3400, q: 2, len: 0.006, peak: 0.04 });
  }, { verb: 0.05 });
  SOUND.define("chart-digit", (v) => {
    v.noise({ filter: "highpass", f: 4200, a: 0.0004, len: 0.01, peak: 0.22 });
  }, { verb: 0.04 });
  SOUND.define("chart-key", (v) => {
    // the key figure lands: a rounder, deeper hit
    v.tone({ f: 130, f2: 85, glide: 0.12, a: 0.003, len: 0.4, peak: 0.45 });
    v.tone({ f: v.hz("E4"), a: 0.004, len: 0.6, peak: 0.08 });
    v.noise({ filter: "lowpass", f: 900, a: 0.002, len: 0.06, peak: 0.12 });
  }, { verb: 0.25 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.25 });
    // page scrolls: mouse-wheel notches over a soft paper glide
    PANEL_AT.slice(1).forEach((at) => {
      k.at(at - 0.75, "chart-glide", { dur: 0.75, gain: 0.8 });
      k.repeat(at - 0.72, 0.08, 8, "chart-notch", { gain: 0.7, vary: 1 });
    });
    k.at(0.05, "paper", { dur: 0.5, gain: 0.25 });
    k.repeat(0.3, 0.07, 6, "tick", { gain: 0.12, pitch: -8 });
    k.at(2.1, "chart-pen", { dur: 1.6, gain: 0.5 }); // the line drawing itself
    // notes and leaders: pen strokes as long as each
    k.at(3.85, "chart-pen", { dur: 0.45 }).at(4.25, "chart-pen", { dur: 0.3 }).at(4.45, "chart-pen", { dur: 0.4 });
    k.at(4.05, "chart-pen", { dur: 0.4, gain: 0.8 }).at(4.4, "chart-pen", { dur: 0.35, gain: 0.8 });
    // key number: digit clicks that slow as the number settles, then one deeper hit
    let tt = PANEL_AT[1] + 0.35;
    for (let i = 0; i < 14; i++) {
      k.at(tt, "chart-digit", { gain: 0.6, pitch: (i % 3) - 1 });
      tt += 0.03 + i * 0.006;
    }
    k.at(PANEL_AT[1] + 1.35, "chart-key", { gain: 0.9 });
    k.at(PANEL_AT[1] + 1.25, "chart-pen", { dur: 0.5 }).at(PANEL_AT[1] + 1.4, "chart-pen", { dur: 0.5, gain: 0.8 });
    k.repeat(PANEL_AT[1] + 1.0, 0.04, 16, "chart-digit", { gain: 0.18, pitch: -12 });
    // why: steps change, notes write
    [0.3, 0.8, 1.3].forEach((s) => k.at(PANEL_AT[2] + s, "click", { gain: 0.25, pitch: -5 }));
    k.at(PANEL_AT[2] + 0.5, "chart-pen", { dur: 0.35 }).at(PANEL_AT[2] + 1.0, "chart-pen", { dur: 0.4 }).at(PANEL_AT[2] + 1.4, "chart-pen", { dur: 0.4 });
    // close
    k.at(PANEL_AT[3] + 0.6, "chart-pen", { dur: 1.0, gain: 0.4 }).at(PANEL_AT[3] + 1.1, "chart-pen", { dur: 0.5 }).at(PANEL_AT[3] + 1.3, "chart-pen", { dur: 0.6 });
    k.at(PANEL_AT[3] + 2.0, "chart-key", { gain: 0.4, pitch: 7 });
  }

  Player.register({
    id: "data-chart",
    name: "Editorial Data Chart",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Kalam:wght@400;700&display=swap",
      faces: ['400 20px "Source Serif 4"', '600 20px "Source Serif 4"', '700 20px "Source Serif 4"', '400 20px "Kalam"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Chart", "Notes", "Key number", "Why: steps", "Takeaway"],
    stills: [1.6, 3.6, 4.9, 7.5, 10.35, 13.3],
    draw,
    score,
  });
})();
