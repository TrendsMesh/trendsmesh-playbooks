/* 31 Newsprint - reference animation.
 * Topic (setting, replace it): "Why do we have leap years?" - the calendar and the solar year.
 * Rendering (keep it): an old broadsheet on yellowed pulp. Each page is set like a real front page and printed once
 * (cached at 1.5x): gothic nameplate between double rules with ears and a dateline, tall condensed headline decks
 * between thin rules, packed justified serif columns so small they read as grey texture, hairline column rules, a
 * coarse high-contrast dot-screen photo with an italic caption, boxed sidebars with reversed title bars, a ruled
 * table, a one-ink line diagram with numbered keys and a by-the-numbers box. Warm near-black ink, thin and uneven,
 * slightly spread; paper stained toward the edges and along two creases, fibres, flecks, a faint mirrored
 * show-through. Only a red wax crayon moves on the page.
 * Legibility: everything the story needs is set at least 4.1u (it is read at zoom 1); body copy, the ears and the
 * dateline are texture (Brush.texture). Every story box sits in a moat of body copy, so whatever the frame's edge
 * bands cross is texture or picture, never a label. The camera reads down the page (zoom 1) like a reader.
 * Motion: the page spins up out of darkness and lands with a thud; the camera glides down the page to each story
 * and creeps while it is read; a page turn changes the scene. Items never animate into place.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { paper: "#e6dcb8", edge: "#cbb98a", ink: "#23201b", faded: "#5b554a", red: "#c4352b", ghost: "#b9ad8a", dark: "#0c0b09" };
  const GOTH = "UnifrakturCook", SERIF = "Playfair Display", COND = "Oswald";
  const DUR = 12.5;
  const BEATS = [0, 2.2, 4.4, 6.4, 9.0, 10.8];
  const RES = 1.5; // pages are printed at 1.5x the frame
  const FLIP = [6.3, 6.95]; // the page turn
  const MIN = 4.1; // smallest text the story needs, in u

  // ---- page plan (page px): story boxes, each in a moat of body copy (y and h below in u)
  function plan(F, n) {
    const P = F.portrait, u = F.u, W = F.W, m = (P ? 4 : 3.4) * u, gut = 2.2 * u, C = P ? 3 : 5;
    const colW = (W - 2 * m - (C - 1) * gut) / C, span = (c, k) => ({ x: m + c * (colW + gut), w: k * colW + (k - 1) * gut });
    const R = { P, u, gut, colW, bodies: [], PW: W }, full = span(0, C);
    const off = P ? (F.H * 0.125) / u : 0; // portrait: a paper head margin, so the nameplate clears the safe line with the sheet filling the frame
    const at = (s, y, h) => ({ x: s.x, y: (y + off) * u, w: s.w, h: h * u });
    const body = (s, y0, y1) => R.bodies.push(at(s, y0, y1 - y0));
    R.mast = at(full, 3, n === 1 ? (P ? 21 : 18) : 6);
    if (n === 1) {
      R.head = at(full, P ? 26 : 22, P ? 27 : 14);
      R.deck = at(full, P ? 54 : 37, P ? 25 : 14);
      if (P) {
        R.photo = at(full, 81, 76);
        R.cap = at(full, 158, 9);
        body(full, 169, 209);
        R.diag = at(full, 211, 92);
        body(full, 305, 355);
        R.nums = at(full, 357, 80);
        body(full, 439, 495);
        R.PH = 495;
      } else {
        R.photo = at(span(0, 3), 53, 50);
        R.cap = at(span(0, 3), 104, 9);
        body(span(3, 2), 53, 128);
        body(span(0, 3), 115, 128);
        R.diag = at(full, 130, 70);
        body(full, 202, 222);
        R.nums = at(full, 224, 48);
        body(full, 274, 315);
        R.PH = 315;
      }
    } else {
      R.head = at(full, 11, P ? 27 : 14);
      R.deck = at(full, P ? 39 : 26, P ? 13 : 7);
      R.note = at(full, P ? 53 : 34, 11);
      if (P) {
        body(full, 66, 158);
        R.rules = at(full, 160, 102);
        body(full, 264, 306);
        R.chart = at(full, 308, 90);
        body(full, 400, 455);
        R.PH = 455;
      } else {
        body(full, 47, 103);
        R.rules = at(span(0, 3), 105, 75);
        R.table = at(span(3, 2), 105, 75);
        body(full, 182, 204);
        R.chart = at(full, 206, 70);
        body(full, 278, 300);
        R.PH = 300;
      }
    }
    R.PH = (R.PH + off) * u;
    return R;
  }

  // ---- newsprint helpers (reuse these)
  const WORDS = ("the calendar year sun earth orbit days hours minutes council astronomers measured spring equinox " +
    "season drift almanac farmers harvest record clock observatory noon shadow quarter added rule century " +
    "said reported yesterday officials figures show long slowly every fourth later than expected moon tides " +
    "and of to in a is was for on that by with as at from it this which have not but are be has were " +
    "printed morning edition correspondent according measure reckoning ancient reform February leap").split(" ");
  /** Justified columns of tiny serif body copy: texture (grey to the eye, never read), with indents and paragraph ends. */
  function columnText(g, r, size, seed) {
    B.texture(g, () => {
      const rng = B.rng(seed), lh = size * 1.2, n = Math.floor(r.h / lh);
      g.font = B.font(size, SERIF, 400);
      g.fillStyle = PAL.ink;
      g.textBaseline = "alphabetic";
      const sp = g.measureText(" ").width;
      let indent = false;
      for (let i = 0; i < n; i++) {
        const words = [], ind = indent ? size * 1.2 : 0;
        let w = ind;
        for (;;) {
          const wd = rng.pick(WORDS) + (rng.chance(0.07) ? "," : rng.chance(0.05) ? "." : ""), ww = g.measureText(wd).width;
          if (w + ww > r.w && words.length) break;
          words.push([wd, ww]);
          w += ww + sp;
        }
        const end = rng.chance(0.11) && i > 2, used = words.reduce((a, q) => a + q[1], 0);
        const gap = end ? sp : (r.w - ind - used) / Math.max(1, words.length - 1), cut = end ? Math.max(1, Math.floor(words.length * rng.range(0.3, 0.7))) : words.length;
        let x = r.x + ind;
        for (let k = 0; k < cut; k++) {
          g.fillText(words[k][0], x, r.y + (i + 1) * lh - size * 0.25);
          x += words[k][1] + gap;
        }
        indent = end;
      }
    });
  }
  function rule(g, x1, y1, x2, y2, w) {
    g.fillStyle = PAL.ink;
    if (y1 === y2) g.fillRect(x1, y1 - w / 2, x2 - x1, w);
    else g.fillRect(x1 - w / 2, y1, w, y2 - y1);
  }
  const dbl = (g, x, y, w, u) => {
    rule(g, x, y, x + w, y, 0.35 * u);
    rule(g, x, y + 0.75 * u, x + w, y + 0.75 * u, 0.12 * u);
  };
  /** Set type that must be read: never shrunk below MIN. */
  const txt = (g, s, x, y, o) => B.text(g, s, x, y, { color: PAL.ink, lineH: 1.12, minSize: Math.max(MIN * U, (o.size || 0) * 0.85), ...o });
  let U = 1;
  /** Boxed sidebar: hairline frame and a reversed (paper-on-ink) condensed title bar. Returns the inner top. */
  function sidebar(g, r, title, u) {
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.18 * u;
    g.strokeRect(r.x, r.y, r.w, r.h);
    const bh = 6.4 * u;
    g.fillStyle = PAL.ink;
    g.fillRect(r.x, r.y, r.w, bh);
    txt(g, title, r.x + r.w / 2, r.y + bh / 2 + 0.1 * u, { size: 4.3 * u, family: COND, weight: 700, color: PAL.paper, maxW: r.w - 2 * u, maxLines: 1, letterSpacing: 0.06 });
    return r.y + bh;
  }
  /** Coarse dot-screen photo: big dots, hard contrast, no real greys. tone(x, y) in 0..1 (1 = solid ink). */
  function dotPhoto(g, r, tone, u) {
    g.save();
    g.beginPath();
    g.rect(r.x, r.y, r.w, r.h);
    g.clip();
    B.halftone(g, r.x, r.y, r.w, r.h, { cell: 1.35 * u, angle: 45, color: PAL.ink, tone: (x, y) => B.smooth(0.2, 0.8, tone((x - r.x) / r.w, (y - r.y) / r.h)) });
    g.restore();
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.14 * u;
    g.strokeRect(r.x, r.y, r.w, r.h);
  }
  /** Noise tile with uneven alpha: rubbing it out of the ink leaves it thin and patchy. */
  function thinTile() {
    return B.layer("news-thin", 200, 200, (g, w, h) => {
      const img = g.createImageData(w, h), d = img.data, r = B.rng(77);
      for (let i = 0; i < w * h; i++) d[i * 4 + 3] = r() < 0.12 ? 150 + r() * 100 : r() * 60;
      g.putImageData(img, 0, 0);
    });
  }

  // ---- the stories (the setting: replace these)
  function paintMast(g, R, u, n) {
    const r = R.mast, P = R.P;
    if (n === 2) {
      rule(g, r.x, r.y + r.h, r.x + r.w, r.y + r.h, 0.16 * u);
      B.texture(g, () => {
        txt(g, "THE DAILY ALMANAC", r.x, r.y + r.h * 0.5, { size: 2.4 * u, minSize: 1, family: COND, weight: 500, align: "left", letterSpacing: 0.12 });
        txt(g, "PAGE 2", r.x + r.w, r.y + r.h * 0.5, { size: 2.4 * u, minSize: 1, family: COND, weight: 500, align: "right" });
      });
      return;
    }
    dbl(g, r.x, r.y, r.w, u);
    const ew = P ? 13 * u : 17 * u, ny = r.y + 8 * u;
    txt(g, "The Daily Almanac", r.x + r.w / 2, ny, { size: P ? 9 * u : 9.5 * u, minSize: 6 * u, family: GOTH, weight: 700, maxW: r.w - 2 * ew - 3 * u, maxLines: 1 });
    // the ears and the dateline are the tiny cells of a title block: texture
    B.texture(g, () => {
      [[r.x, "WEATHER", "Fair and cooler; frost by night"], [r.x + r.w - ew, "LATE CITY", "Final edition, all the news"]].forEach(([x, a, b]) => {
        g.strokeStyle = PAL.ink;
        g.lineWidth = 0.12 * u;
        g.strokeRect(x, r.y + 2.4 * u, ew, 10 * u);
        txt(g, a, x + ew / 2, r.y + 4.6 * u, { size: 2 * u, minSize: 1, family: COND, weight: 700, maxW: ew - u });
        txt(g, b, x + ew / 2, r.y + 8.6 * u, { size: 1.4 * u, minSize: 1, family: SERIF, style: "italic", weight: 400, maxW: ew - 1.6 * u, maxLines: 2 });
      });
      const dy = r.y + r.h - 2.2 * u;
      ["VOL. CXII . . . No. 38,512", "THURSDAY, FEBRUARY 29", "PRICE TWO CENTS"].forEach((s, i) =>
        txt(g, s, [r.x, r.x + r.w / 2, r.x + r.w][i], dy, { size: 1.8 * u, minSize: 1, family: COND, weight: 500, align: ["left", "center", "right"][i], letterSpacing: 0.05 }));
    });
    dbl(g, r.x, r.y + r.h - 5 * u, r.w, u);
    rule(g, r.x, r.y + r.h, r.x + r.w, r.y + r.h, 0.14 * u);
  }
  /** Headline in decks of decreasing size, a thin rule under each. */
  function paintHead(g, R, u, lines, deck1, deck2) {
    const r = R.head, d = R.deck, P = R.P;
    txt(g, lines, r.x + r.w / 2, r.y + r.h * 0.5, { size: P ? 12.5 * u : 11 * u, family: COND, weight: 700, maxW: r.w, maxLines: P ? 2 : 1, lineH: 1.0 });
    rule(g, r.x + r.w * 0.3, r.y + r.h - 0.2 * u, r.x + r.w * 0.7, r.y + r.h - 0.2 * u, 0.12 * u);
    const a = txt(g, deck1, d.x + d.w / 2, d.y + 1.2 * u, { size: P ? 5 * u : 4.6 * u, family: COND, weight: 500, maxW: d.w * 0.96, maxLines: 2, baseline: "top" });
    if (deck2) {
      rule(g, d.x + d.w * 0.42, a.bottom + 1.2 * u, d.x + d.w * 0.58, a.bottom + 1.2 * u, 0.12 * u);
      txt(g, deck2, d.x + d.w / 2, a.bottom + 2.4 * u, { size: P ? 4.4 * u : 4.2 * u, family: SERIF, style: "italic", weight: 400, maxW: d.w * 0.92, maxLines: 2, baseline: "top" });
    }
    rule(g, d.x, d.y + d.h, d.x + d.w, d.y + d.h, 0.12 * u);
  }
  /** Sunrise behind standing stones: white sun in the gap of a trilithon, stones solid black, glare on the grass. */
  function paintPhoto(g, R, u) {
    const r = R.photo, k = r.h / r.w, hz = 0.68;
    const stones = [[0.03, 0.035, 0.09], [0.12, 0.045, 0.15], [0.22, 0.045, 0.15], [0.29, 0.04, 0.1], [0.35, 0.05, 0.25], [0.6, 0.05, 0.25], [0.69, 0.04, 0.11], [0.77, 0.045, 0.16], [0.87, 0.045, 0.16], [0.96, 0.04, 0.08]];
    const lintels = [[0.11, 0.17, 0.15], [0.34, 0.32, 0.25], [0.76, 0.17, 0.16]];
    dotPhoto(g, r, (x, y) => {
      const Y = (y - hz) * k, d = Math.hypot(x - 0.5, Y + 0.1);
      let v = Y < 0 ? 0.48 + 0.45 * B.clamp(-Y / 0.5) - 0.2 * Math.exp(-Math.max(0, d - 0.07) * 6) : 0.92 - 0.75 * Math.exp(-(((x - 0.5) / (0.03 + Y * 1.4)) ** 2));
      if (d < 0.07) v = 0;
      for (const [a, w, h] of stones) if (x > a && x < a + w && Y > -h - 0.012 * Math.sin(x * 90) && Y < 0.012) v = 1;
      for (const [a, w, h] of lintels) if (x > a && x < a + w && Y > -h - 0.035 && Y < -h + 0.005) v = 1;
      return v;
    }, u);
    txt(g, "Sunrise over the standing stones. The Sun's yearly round sets the length of our year.", R.cap.x, R.cap.y + R.cap.h / 2, { size: 4.1 * u, family: SERIF, style: "italic", weight: 400, align: "left", maxW: R.cap.w, maxLines: 2 });
  }
  /** One-ink line diagram: the orbit with a ruled arrow, numbered keys, the quarter-day gap and a legend. */
  function paintDiagram(g, r, u, Rp, P) {
    const top = sidebar(g, r, "HOW A YEAR IS MEASURED", u);
    const ow = P ? r.w : r.w * 0.56, oh = P ? r.h * 0.56 : r.h - (top - r.y);
    const cx = r.x + ow / 2, cy = top + oh / 2 + (P ? 1 : 0.5) * u, rx = ow * 0.36, ry = Math.min(rx * 0.5, oh * 0.3);
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.18 * u;
    g.setLineDash([0.8 * u, 0.6 * u]);
    g.beginPath();
    g.ellipse(cx, cy, rx, ry, 0, 0, B.TAU);
    g.stroke();
    g.setLineDash([]);
    g.fillStyle = PAL.ink;
    g.beginPath();
    B.circle(g, cx, cy, 3 * u);
    g.fill();
    g.lineWidth = 0.28 * u;
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * B.TAU;
      g.beginPath();
      g.moveTo(cx + Math.cos(a) * 4 * u, cy + Math.sin(a) * 4 * u);
      g.lineTo(cx + Math.cos(a) * 5.4 * u, cy + Math.sin(a) * 5.4 * u);
      g.stroke();
    }
    const ex = cx, ey = cy + ry;
    g.beginPath();
    B.circle(g, ex, ey, 1.9 * u);
    g.fill();
    // ruled arrow along the orbit: 365 days ends a little short of where Earth started
    const arc = [];
    for (let i = 0; i <= 90; i++) {
      const a = Math.PI * 0.5 + 0.3 + (i / 90) * (B.TAU - 0.6);
      arc.push([cx + Math.cos(a) * rx * 1.13, cy + Math.sin(a) * ry * 1.25]);
    }
    B.arrow(g, arc, { width: 0.36 * u, color: PAL.ink, head: 2.6 * u, headStyle: "tri" });
    const key = (n, x, y) => {
      g.fillStyle = PAL.ink;
      g.beginPath();
      B.circle(g, x, y, 3.1 * u);
      g.fill();
      txt(g, String(n), x, y + 0.15 * u, { size: 4.2 * u, family: COND, weight: 700, color: PAL.paper });
    };
    const gap = [ex + 6 * u, ey - 6.5 * u];
    key(1, cx + 7.5 * u, cy - 5.5 * u);
    key(2, ex - 5.5 * u, ey - 4.5 * u);
    key(3, cx - rx * 0.8, cy - ry * 1.3);
    key(4, gap[0], gap[1]);
    const gl = txt(g, "+ 1/4 day", gap[0] + 4 * u, gap[1], { size: 4.6 * u, family: COND, weight: 700, align: "left" });
    Rp.gap = { x: gap[0] - 3.4 * u, y: gap[1] - 3.4 * u, w: gl.width + 8 * u, h: 6.8 * u };
    // the legend: numbered keys, as a newspaper sets them
    const lx = P ? r.x + 3 * u : r.x + ow + 1 * u, ly = P ? top + oh + 3 * u : top + 4 * u, lw = P ? r.w - 6 * u : r.w - ow - 4 * u;
    rule(g, P ? r.x + 2 * u : lx - 1.5 * u, P ? ly - 1.5 * u : top + 2 * u, P ? r.x + r.w - 2 * u : lx - 1.5 * u, P ? ly - 1.5 * u : r.y + r.h - 2 * u, 0.12 * u);
    let y = ly;
    ["1  Sun", "2  Earth", "3  One orbit: 365 days, 5 hours, 49 minutes", "4  The part a 365-day year leaves out"].forEach((s) => {
      const t = txt(g, s, lx, y, { size: 4.2 * u, family: SERIF, weight: 400, align: "left", baseline: "top", maxW: lw, maxLines: 2 });
      y = t.bottom + 1 * u;
    });
  }
  /** By-the-numbers box: heavy condensed figures, each over its italic caption. */
  function paintNums(g, r, u, Rp, P) {
    const top = sidebar(g, r, "BY THE NUMBERS", u);
    const items = [["365.2422", "days in one solar year, spring to spring"], ["24", "days of drift a century with no leap days"], ["97", "leap days in every 400 years"]];
    let y = top + 2.5 * u;
    items.forEach(([num, cap], i) => {
      const big = i === 0, cw = P ? r.w : r.w / 3, x = P ? r.x + r.w / 2 : r.x + cw * (i + 0.5);
      if (!P) y = top + 3 * u;
      const a = txt(g, num, x, y, { size: big ? (P ? 13 : 10) * u : (P ? 8 : 10) * u, family: COND, weight: 700, baseline: "top", maxW: cw - 4 * u, maxLines: 1, lineH: 1.0 });
      if (big) Rp.big = { x: x - a.width / 2, y: a.top, w: a.width, h: a.height };
      const c = txt(g, cap, x, a.bottom + (big ? 3 : 1) * u, { size: 4.2 * u, family: SERIF, style: "italic", weight: 400, baseline: "top", maxW: cw - 6 * u, maxLines: 3 });
      y = c.bottom + 2.6 * u;
      if (P && i < 2) rule(g, r.x + r.w * 0.3, y - 1.3 * u, r.x + r.w * 0.7, y - 1.3 * u, 0.12 * u);
      if (!P && i) rule(g, r.x + cw * i, top + 3 * u, r.x + cw * i, r.y + r.h - 3 * u, 0.1 * u);
    });
  }
  const YEARS = [["2024", "Yes"], ["2100", "No"], ["2000", "Yes"], ["2400", "Yes"]];
  function paintRules(g, r, u, Rp, P) {
    const top = sidebar(g, r, "THE TEST FOR A LEAP YEAR", u);
    const rows = [["Can the year be divided by 4?", "Then it gets a 29th of February."], ["Does it end in 00?", "Then it does not, after all . . ."], ["Can it be divided by 400?", ". . . unless it can. Then it does."]];
    const tabH = P ? 21 * u : 0, rh = (r.h - (top - r.y) - tabH - 1.5 * u) / 3;
    Rp.rows = [];
    rows.forEach(([q, a], i) => {
      const y = top + 0.8 * u + i * rh;
      txt(g, String(i + 1), r.x + 5 * u, y + rh / 2, { size: 10 * u, family: COND, weight: 700 });
      const qa = txt(g, q, r.x + 11 * u, y + rh * 0.36, { size: 4.6 * u, family: SERIF, weight: 700, align: "left", maxW: r.w - 13 * u, maxLines: 2 });
      txt(g, a, r.x + 11 * u, qa.bottom + 3.4 * u, { size: 4.2 * u, family: SERIF, style: "italic", weight: 400, align: "left", maxW: r.w - 13 * u, maxLines: 2 });
      Rp.rows.push({ x: r.x + 11 * u, y: qa.top, w: qa.width, h: qa.bottom - qa.top - 1.6 * u }); // under the question's baseline, clear of the answer below
      if (i < 2 || P) rule(g, r.x + 2 * u, y + rh, r.x + r.w - 2 * u, y + rh, 0.1 * u);
    });
    if (!P) return;
    // portrait: the ruled table of years runs along the foot of the box
    const ty = r.y + r.h - tabH, cw = (r.w - 4 * u) / 5;
    [["YEAR", "LEAP?"]].concat(YEARS).forEach(([a, b], i) => {
      const x = r.x + 2 * u + cw * (i + 0.5), hd = !i;
      txt(g, a, x, ty + 6 * u, { size: 4.4 * u, family: COND, weight: hd ? 700 : 500 });
      txt(g, b, x, ty + 14 * u, { size: 4.4 * u, family: hd ? COND : SERIF, weight: hd ? 700 : 400, style: hd ? "" : "italic" });
      if (i) rule(g, x - cw / 2, ty + 2 * u, x - cw / 2, ty + tabH - 2 * u, 0.08 * u);
    });
    rule(g, r.x + 2 * u, ty + 10 * u, r.x + r.w - 2 * u, ty + 10 * u, 0.08 * u);
  }
  function paintTable(g, r, u) {
    const top = sidebar(g, r, "WHICH YEARS?", u);
    const rows = [["YEAR", "LEAP?"]].concat(YEARS), rh = (r.h - (top - r.y)) / rows.length;
    rows.forEach(([a, b], i) => {
      const y = top + (i + 0.5) * rh, hd = i === 0;
      txt(g, a, r.x + r.w * 0.3, y, { size: 4.5 * u, family: COND, weight: hd ? 700 : 500 });
      txt(g, b, r.x + r.w * 0.72, y, { size: 4.5 * u, family: hd ? COND : SERIF, weight: hd ? 700 : 400, style: hd ? "" : "italic" });
      if (i) rule(g, r.x + u, y - rh / 2, r.x + r.w - u, y - rh / 2, 0.08 * u);
    });
    rule(g, r.x + r.w * 0.52, top + 0.6 * u, r.x + r.w * 0.52, r.y + r.h - 0.6 * u, 0.08 * u);
  }
  function paintChart(g, r, u, Rp, P) {
    const top = sidebar(g, r, "DRIFT AFTER 100 YEARS, IN DAYS", u);
    const bars = [["No leap days", 24.2, "24.2"], ["A leap day every 4th year", 0.78, "0.8"], ["Today's rules", 0.03, "0.03"]];
    const x0 = r.x + 3 * u, wMax = r.w - 18 * u, rh = (r.h - (top - r.y) - (P ? 13 : 8) * u) / 3;
    rule(g, x0, top + 1.5 * u, x0, top + 1.5 * u + rh * 3, 0.2 * u);
    bars.forEach(([name, v, lab], i) => {
      const y = top + 1.5 * u + i * rh, bw = Math.max(0.5 * u, (wMax * v) / 24.2);
      txt(g, name, x0 + 1.5 * u, y + rh * 0.26, { size: 4.3 * u, family: SERIF, weight: 700, align: "left", maxW: wMax });
      g.fillStyle = PAL.ink;
      g.fillRect(x0, y + rh * 0.5, bw, rh * 0.36);
      const l = txt(g, lab, x0 + bw + 2 * u, y + rh * 0.68, { size: 5.4 * u, family: COND, weight: 700, align: "left" });
      if (i === 2) Rp.tiny = { x: x0 + bw + 0.5 * u, y: y + rh * 0.68 - 4 * u, w: l.width + 3 * u, h: 8 * u };
    });
    txt(g, "Against a solar year of 365.2422 days. Figures rounded.", r.x + 3 * u, r.y + r.h - (P ? 6.5 : 4) * u, { size: 4.1 * u, family: SERIF, style: "italic", weight: 400, align: "left", maxW: r.w - 6 * u, maxLines: 2 });
  }
  function paintNote(g, r, u, Rp) {
    g.strokeStyle = PAL.ink;
    g.lineWidth = 0.18 * u;
    g.strokeRect(r.x, r.y, r.w, r.h);
    g.strokeRect(r.x + 0.6 * u, r.y + 0.6 * u, r.w - 1.2 * u, r.h - 1.2 * u);
    const a = txt(g, "NEXT LEAP DAY: TUESDAY, FEB. 29, 2028", r.x + r.w / 2, r.y + r.h / 2, { size: 5 * u, family: COND, weight: 700, maxW: r.w - 4 * u, maxLines: 1, letterSpacing: 0.03 });
    Rp.noteText = { x: r.x + r.w / 2 - a.width / 2, y: a.top, w: a.width, h: a.height };
  }

  // ---- printing a page (cached)
  const extra = {}; // marks positions found while setting type, per page and frame size
  function page(F, n) {
    const R = plan(F, n), key = n + "@" + F.W + "x" + F.H;
    const c = B.layer("news-page" + n, R.PW * RES, R.PH * RES, (pg, w, h) => {
      const u = R.u, Rp = (extra[key] = {});
      // pulp sheet: fibres and flecks, then yellowing at the edges and along the two creases
      B.paper(pg, w, h, { color: PAL.paper, seed: 31 + n, mottle: 0.16, fibers: 0.8, specks: 0.9, tooth: 0.12, fiberColor: "#8a7a50" });
      B.vignette(pg, w, h, { color: PAL.edge, amount: 0.95, inner: 0.25, mode: "multiply" });
      B.mottle(pg, w, h, { amount: 0.22, feature: 0.35, seed: 40 + n, mode: "multiply" });
      pg.save();
      pg.globalCompositeOperation = "multiply";
      const crease = (x0, y0, x1, y1, wd) => {
        pg.fillStyle = B.linear(pg, x0, y0, x1, y1, [[0, B.rgba(PAL.edge, 0)], [0.45, B.rgba(PAL.edge, 0.9)], [0.5, B.rgba("#a8925e", 0.9)], [0.55, B.rgba(PAL.edge, 0.6)], [1, B.rgba(PAL.edge, 0)]]);
        pg.fillRect(Math.min(x0, x1), Math.min(y0, y1), wd[0], wd[1]);
      };
      crease(w * 0.5 - 4 * u * RES, 0, w * 0.5 + 4 * u * RES, 0, [8 * u * RES, h]);
      crease(0, h * 0.42 - 4 * u * RES, 0, h * 0.42 + 4 * u * RES, [w, 8 * u * RES]);
      pg.restore();
      // the ink, set on its own sheet
      const ink = B.canvas(w, h), g = ink.getContext("2d");
      g.scale(RES, RES);
      paintMast(g, R, u, n);
      if (n === 1) {
        paintHead(g, R, u, R.P ? "CALENDAR FALLS\nBEHIND THE SUN" : "CALENDAR FALLS BEHIND THE SUN", "A PLAIN 365-DAY YEAR RUNS SHORT BY ALMOST A QUARTER OF A DAY", "Astronomers say the gap grows to a whole day every four years");
        paintPhoto(g, R, u);
        paintDiagram(g, R.diag, u, Rp, R.P);
        paintNums(g, R.nums, u, Rp, R.P);
      } else {
        paintHead(g, R, u, R.P ? "THREE RULES KEEP\nTHE DATE IN STEP" : "THREE RULES KEEP THE DATE IN STEP", "A SIMPLE TEST DECIDES WHICH YEARS GET A 29TH OF FEBRUARY");
        paintNote(g, R.note, u, Rp);
        paintRules(g, R.rules, u, Rp, R.P);
        if (R.table) paintTable(g, R.table, u);
        paintChart(g, R.chart, u, Rp, R.P);
      }
      R.bodies.forEach((b, i) => {
        const cols = Math.max(1, Math.round((b.w + R.gut) / (R.colW + R.gut)));
        for (let k = 0; k < cols; k++) {
          const x = b.x + k * (R.colW + R.gut);
          columnText(g, { x, y: b.y, w: R.colW, h: b.h }, (R.P ? 1.3 : 1.35) * u, n * 100 + i * 10 + k);
          if (k) rule(g, x - R.gut / 2, b.y + 0.5 * u, x - R.gut / 2, b.y + b.h, 0.08 * u);
        }
      });
      // thin, uneven ink: rub a patchy noise out of it
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.globalCompositeOperation = "destination-out";
      g.fillStyle = g.createPattern(thinTile(), "repeat");
      g.fillRect(0, 0, w, h);
      // show-through: the reverse side, mirrored and faint
      pg.save();
      pg.globalCompositeOperation = "multiply";
      pg.globalAlpha = 0.035; // very faint: a grey ghost, never readable
      pg.filter = `blur(${(1.4 * RES).toFixed(1)}px)`;
      pg.translate(w, 0);
      pg.scale(-1, 1);
      pg.drawImage(ink, 0, 9 * u * RES);
      pg.restore();
      // ink spread: a soft pass under the sharp one
      pg.save();
      pg.globalCompositeOperation = "multiply";
      pg.globalAlpha = 0.45;
      pg.filter = `blur(${(0.55 * RES).toFixed(1)}px)`;
      pg.drawImage(ink, 0, 0);
      pg.filter = "none";
      pg.globalAlpha = 0.92;
      pg.drawImage(ink, 0, 0);
      pg.restore();
    });
    return { c, R, X: extra[key] || {} };
  }

  // ---- camera: reading down the page at zoom 1, creeping while a story is read
  function camAt(F, t) {
    const u = F.u, R1 = plan(F, 1), R2 = plan(F, 2), dy = F.H / 2 - F.safe.cy;
    const top = F.H / 2; // the head of the sheet at the top of the frame
    const on = (r) => r.y + r.h / 2 + dy, cr = (y) => y + u;
    const keys = [[1.0, top, 1], [2.2, cr(top), 1], [3.0, on(R1.diag), 1], [4.2, cr(on(R1.diag)), 1], [4.9, on(R1.nums), 1], [6.1, cr(on(R1.nums)), 1], [FLIP[0], cr(on(R1.nums)), 1],
      [FLIP[1], top, 2], [7.6, on(R2.rules), 2], [8.95, cr(on(R2.rules)), 2], [9.5, on(R2.chart), 2], [10.8, cr(on(R2.chart)), 2], [11.4, top, 2], [DUR, cr(top), 2]];
    let y = top, n = 1;
    if (t > keys[0][0]) {
      const f = keys.findIndex((k) => t <= k[0]), i = f < 0 ? keys.length - 1 : f;
      const [t1, y1, n1] = keys[i], [t0, y0, n0] = keys[i - 1];
      n = n1;
      y = n0 !== n1 ? top : B.lerp(y0, y1, B.ease.inOutSine(B.prog(t, t0, t1 - t0)));
      if (n0 !== n1) return { x: F.W / 2, y, z: 1, n, prev: { x: F.W / 2, y: y0, z: 1 } }; // the turn: page 1 keeps its view
    }
    return { x: F.W / 2, y, z: 1, n };
  }
  /** Place page coordinates on the screen: camera point at the frame centre, plus the spin-up rotation. */
  function applyCam(g, F, c, rot = 0) {
    g.translate(F.W / 2, F.H / 2);
    g.scale(c.z, c.z);
    if (rot) g.rotate(rot);
    g.translate(-c.x, -c.y);
  }

  // ---- red wax crayon (the only thing that moves on the page)
  function crayonPath(g, pts, p, w, seed) {
    if (p <= 0) return;
    for (let k = 0; k < 3; k++) {
      g.save();
      g.translate((k - 1) * w * 0.22, (k % 2 ? 1 : -1) * w * 0.16);
      B.taperStroke(g, pts, { width: w * [1, 0.75, 0.55][k], color: B.rgba(PAL.red, [0.8, 0.6, 0.7][k]), p, taperIn: 0.08, taperOut: 0.12, rough: 0.55, roughScale: 3, seed: seed + k * 7 });
      g.restore();
    }
  }
  const ringPts = (r, seed) => {
    const pts = [], cx = r.x + r.w / 2, cy = r.y + r.h / 2, rx = r.w * 0.56 + r.h * 0.1, ry = r.h * 0.7;
    for (let i = 0; i <= 90; i++) {
      const a = -2.4 + (i / 90) * B.TAU * 1.12, k = 1 + 0.05 * Math.sin(i * 0.17 + seed) + 0.06 * (i / 90);
      pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    return pts;
  };
  const underPts = (r, u) => B.wobble(B.densify([[r.x - u, r.y + r.h + 0.8 * u], [r.x + r.w + u, r.y + r.h + 0.3 * u]], u), { amp: 0.35 * u, seed: 4 });
  const TICKS = [7.7, 8.15, 8.6];
  /** The marks on page n at time t: [kind, rect, start]. */
  function marks(n, X, R, t) {
    const out = [];
    if (n === 1) {
      out.push(["under", { x: R.head.x + R.head.w * 0.2, y: R.head.y + R.head.h * 0.9, w: R.head.w * 0.6, h: 0 }, 1.45]);
      if (X.gap) out.push(["ring", X.gap, 3.15]);
      if (X.big) out.push(["ring", { ...X.big, x: X.big.x - R.u, w: X.big.w + 2 * R.u }, 5.2]);
    } else {
      (X.rows || []).forEach((r, i) => out.push(["under", r, TICKS[i]]));
      if (X.tiny) out.push(["ring", X.tiny, 9.85]);
      if (X.noteText) out.push(["under", X.noteText, 11.6]);
    }
    return out.filter((m) => t > m[2]);
  }
  function drawCrayon(g, ms, t, u) {
    ms.forEach(([kind, r, at], i) => {
      const p = B.prog(t, at, kind === "ring" ? 0.5 : 0.35, "inOutSine");
      if (kind === "ring") crayonPath(g, ringPts(r, i), p, 0.85 * u, 10 + i);
      else crayonPath(g, underPts(r, u), p, 0.9 * u, 20 + i);
    });
  }

  /** Page n under camera c, with its crayon marks, as a frame-sized picture (so a page turn can bend it whole). */
  function view(F, n, c, t, rot = 0) {
    const pgx = page(F, n), u = F.u;
    const v = B.scratch("news-view" + n, F.W, F.H);
    v.fillStyle = PAL.dark;
    v.fillRect(0, 0, F.W, F.H);
    v.save();
    applyCam(v, F, c, rot);
    v.fillStyle = "rgba(0,0,0,0.55)"; // the sheet's shadow on the dark desk
    v.fillRect(0.5 * u, u, pgx.R.PW, pgx.R.PH);
    v.drawImage(pgx.c, 0, 0, pgx.R.PW, pgx.R.PH);
    v.restore();
    const ms = marks(n, pgx.X, pgx.R, t);
    if (ms.length) {
      const cr = B.scratch("news-crayon", F.W, F.H);
      cr.save();
      applyCam(cr, F, c, rot);
      drawCrayon(cr, ms, t, u);
      cr.restore();
      // waxy: the crayon skips over the paper tooth
      cr.globalCompositeOperation = "destination-out";
      const pat = cr.createPattern(thinTile(), "repeat");
      pat.setTransform(new DOMMatrix([1.4, 0, 0, 1.4, 0, 0]));
      cr.fillStyle = pat;
      cr.fillRect(0, 0, F.W, F.H);
      v.save();
      v.globalCompositeOperation = "multiply";
      v.drawImage(cr.canvas, 0, 0);
      v.restore();
    }
    return v.canvas;
  }

  function draw(ctx, W, H, t) {
    const F = B.frame(W, H), u = F.u;
    U = u;
    ctx.fillStyle = PAL.dark;
    ctx.fillRect(0, 0, W, H);
    const c = camAt(F, t);
    if (t < 1.0) {
      // spin-up: out of darkness, growing as it turns, faster and faster, then flat
      const p = B.prog(t, 0, 1.0, "inQuad"), rot = (1 - B.ease.outQuad(B.prog(t, 0, 1.0))) * Math.PI * 3.2, z = B.lerp(0.03, 1, p);
      if (z > 0.12) ctx.drawImage(view(F, 1, { ...c, z }, t, rot), 0, 0); // a speck before that: darkness
      B.cover(ctx, W, H, PAL.dark, 0.75 * (1 - p));
    } else if (t >= FLIP[0] && t < FLIP[1]) {
      // page turn: page 2 underneath, page 1 swinging away about the left edge
      const k = B.span(t, FLIP[0], FLIP[1], "inOutCubic"), sx = Math.cos(k * Math.PI * 0.5);
      ctx.drawImage(view(F, 2, c, t), 0, 0);
      ctx.save();
      ctx.fillStyle = B.linear(ctx, W * sx, 0, W * sx + 12 * u, 0, [B.rgba("#000", 0.45 * (1 - k)), B.rgba("#000", 0)]);
      ctx.fillRect(W * sx, 0, 12 * u, H);
      ctx.scale(Math.max(0.001, sx), 1);
      ctx.drawImage(view(F, 1, c.prev, t), 0, 0);
      ctx.fillStyle = B.linear(ctx, 0, 0, W, 0, [B.rgba("#000", 0.05 * k), B.rgba("#000", 0.5 * k)]);
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
    } else {
      // landing bounce and a short shake on the thud
      const land = t - 1.0, b = land < 0.6 ? 0.018 * Math.exp(-9 * land) * Math.sin(land * 30) : 0;
      const [dx, dy] = B.shake(t, u * 0.8 * Math.max(0, 1 - land / 0.25), 3, 30);
      ctx.save();
      ctx.translate(dx, dy);
      ctx.drawImage(view(F, c.n, { ...c, z: c.z * (1 + b) }, t), 0, 0);
      ctx.restore();
    }
    // finishing: fibre and fleck noise, a pool of light
    B.grain(ctx, W, H, { amount: 0.1, t, fps: 12, mode: "multiply", seed: 31 });
    B.grain(ctx, W, H, { amount: 0.05, t, fps: 12, mode: "overlay", seed: 9 });
    B.vignette(ctx, W, H, { amount: 0.42, inner: 0.42, color: "#1a1206", mode: "multiply" });
  }

  // ---- sound: rotary whoosh and a slap, page turns, crayon scratches
  SOUND.define("news-press", (v, o) => {
    // the rotary press spinning up: filtered noise chopped by a speeding drum, ending in the page's whoosh
    const d = o.dur ?? 1;
    const n = v.noise({ filter: "bandpass", f: 300, f2: 1800, glide: d, q: 1.2, a: d * 0.7, len: 0.25, peak: 0.35 });
    v.lfo(n.gain.gain, 9, 0.12, v.t + d + 0.3, "square");
    v.tone({ type: "sawtooth", f: 40, f2: 110, glide: d, a: d * 0.6, len: 0.2, peak: 0.04 });
  }, { verb: 0.15 });
  SOUND.define("news-slap", (v) => {
    // a flat slap of paper on a desk: a broad crack and a dull body
    v.noise({ filter: "bandpass", f: 1400, q: 0.6, a: 0.0006, len: 0.07, peak: 0.6 });
    v.noise({ filter: "lowpass", f: 400, brown: true, a: 0.001, len: 0.16, peak: 0.45 });
    v.tone({ f: 95, f2: 55, glide: 0.1, a: 0.002, len: 0.14, peak: 0.35 });
  }, { verb: 0.2 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 1 });
    k.at(0.0, "news-press", { dur: 0.95, gain: 0.9 }).at(0.55, "whoosh", { dur: 0.5, gain: 0.6 });
    k.at(1.0, "news-slap", { gain: 1 }).at(1.02, "thud", { gain: 0.5 }).at(1.1, "rustle", { dur: 0.3, gain: 0.4 });
    k.at(1.45, "pencil", { dur: 0.4, gain: 0.7 });
    [2.25, 4.25, 9.0].forEach((a) => k.at(a, "paper", { dur: 0.7, gain: 0.25 }));
    k.at(3.15, "pencil", { dur: 0.5, gain: 0.75 }).at(5.2, "pencil", { dur: 0.5, gain: 0.75 });
    k.at(FLIP[0], "flip", { gain: 0.9 }).at(FLIP[0] + 0.05, "paper", { dur: 0.6, gain: 0.7 }).at(FLIP[1] - 0.05, "rustle", { dur: 0.25, gain: 0.5 });
    TICKS.forEach((a, i) => k.at(a, "pencil", { dur: 0.3, gain: 0.6, pitch: i }));
    k.at(9.85, "pencil", { dur: 0.5, gain: 0.75 });
    k.at(10.85, "rustle", { dur: 0.4, gain: 0.35 });
    k.at(11.6, "pencil", { dur: 0.35, gain: 0.75 }).at(12.0, "knock", { gain: 0.3 });
  }

  Player.register({
    id: "newsprint",
    name: "Newsprint",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=UnifrakturCook:wght@700&family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Oswald:wght@500;700&display=swap",
      faces: ['700 20px "UnifrakturCook"', '400 20px "Playfair Display"', '700 20px "Playfair Display"', 'italic 400 20px "Playfair Display"', '500 20px "Oswald"', '700 20px "Oswald"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Three rules", "Chart", "Close"],
    stills: [1.9, 3.9, 6.0, 8.9, 10.5, 12.3],
    draw,
    score,
  });
})();
