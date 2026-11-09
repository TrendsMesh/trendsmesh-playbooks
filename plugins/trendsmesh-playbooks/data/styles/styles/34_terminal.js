/* 34 Green Screen Terminal - reference animation.
 * Topic (setting, replace it): "How does DNS find a website?" - resolver, root, .com, name server, cache.
 * Rendering (keep it): a 1980s monochrome monitor. Everything on the glass is one green phosphor in three
 * brightnesses on near-black: blocky VT323 text in rows with a wide left margin and a block cursor, a reversed status
 * bar, bracketed CAPS tags, boxes and arrows drawn as thin glowing strokes with block heads, block-digit numbers with
 * a block meter. The screen is drawn flat first, then finished like a tube: a strong phosphor bloom (blurred copy added
 * back at low resolution), fine scanlines, a slow dim roll bar and flicker, then a barrel bulge (two strip passes)
 * with a faint red/blue fringe toward the edges, a vignette and a window reflection sweeping over the glass, all
 * inside a dark plastic bezel with rounded glass corners.
 * Motion: power-on (dot, line, flashing field, steady light), typing at typing speed with the cursor following,
 * scene changes by a vertical roll or a quick clear, every move in steps, pauses as if the machine were thinking.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ------------------------------------------------------------------ palette and type (from the card)
  const PAL = { black: "#050a06", bright: "#7dff9a", mid: "#2fd35f", dim: "#14742f", bloom: "#9dffb3", bezel: "#2b2a26", glare: "#c9d6cc" };
  const VT = "VT323", MONO = "Share Tech Mono";
  const DUR = 12.5;
  const BEATS = [0, 2.3, 4.4, 6.5, 9.0, 10.9];
  const CPS = 22; // typing speed, characters a second

  // ------------------------------------------------------------------ layout: glass, text grid
  function layout(W, H) {
    const F = B.frame(W, H), u = F.u, P = F.portrait;
    const glass = P ? { x: W * 0.03, y: H * 0.035, w: W * 0.94, h: H * 0.88 } : { x: W * 0.035, y: H * 0.05, w: W * 0.93, h: H * 0.9 };
    const fs = P ? 6.2 * u : 6.8 * u;
    return {
      F, u, P, glass, fs, lh: fs * (P ? 1.18 : 1.05),
      x0: glass.x + (P ? 6 : 7) * u, y0: P ? H * 0.155 : glass.y + 5 * u,
      status: P ? H * 0.752 : H * 0.85, big: P ? 2.4 : 2.0,
    };
  }

  // ------------------------------------------------------------------ terminal helpers (reuse these)
  let S = null, L = null, CW = 10, CUR = null, T = 0, REVS = [];
  /** Text at a cell (col, row). o: { col: brightness colour, scale (big text), rev (reversed: dark on green) } */
  function put(str, col, row, o = {}) {
    if (!str) return;
    const sc = o.scale || 1, fs = L.fs * sc, x = L.x0 + col * CW, y = L.y0 + row * L.lh;
    S.font = B.font(fs, VT, 400);
    S.textBaseline = "top";
    S.textAlign = "left";
    if (o.rev) {
      S.fillStyle = o.col === PAL.bright ? PAL.mid : o.col || PAL.mid;
      S.fillRect(x - CW * 0.15, y - L.lh * 0.04, str.length * CW * sc + CW * 0.3, L.lh * sc * 0.98);
      S.fillStyle = PAL.black;
      REVS.push([str, x, y + fs * 0.02, B.font(fs, VT, 400), S.getTransform(), "top", "left"]); // re-stamped after the bloom
    } else S.fillStyle = o.col || PAL.mid;
    S.fillText(str, x, y + fs * 0.02);
  }
  /** A typed command line "> text": chars appear at CPS from `at`; the cursor follows. Returns true once done. */
  function cmd(lt, at, text, row) {
    if (lt < at) return false;
    const n = Math.min(text.length, Math.floor((lt - at) * CPS));
    put("> ", 0, row, { col: PAL.mid });
    put(text.slice(0, n), 2, row, { col: PAL.bright });
    CUR = [2 + n, row, n < text.length];
    return n >= text.length;
  }
  /** Printed output: the whole line lands at once (the machine answers, it does not type). */
  function out(lt, at, text, col, row, o = {}) {
    if (lt < at) return false;
    put(text, col, row, o);
    if (!o.keepCursor) CUR = [0, row + (o.scale ? Math.ceil(o.scale) : 1), false];
    return true;
  }
  /** Bracketed CAPS tag: [OK] mid, [WARN] reversed. */
  const tagTxt = (k) => "[" + k + "]";
  /** Thin glowing box around a cell rectangle, its outline drawn on in steps (p 0..1). */
  function box(c, r, wc, label, p, col = PAL.mid) {
    if (p <= 0) return;
    const x = L.x0 + (c - 0.6) * CW, y = L.y0 + (r - 0.35) * L.lh, w = (wc + 1.2) * CW, h = L.lh * 1.7;
    const pts = B.rectPts(x, y, w, h);
    B.strokeReveal(S, pts, Math.floor(p * 8) / 8, { width: Math.max(2, L.u * 0.32), color: col, cap: "square", join: "miter" });
    if (p >= 1) put(label, c + (wc - label.length) / 2, r, { col: PAL.bright });
  }
  /** Thin line with a block head, between cell points, drawn on in steps. */
  function wire(pts, p) {
    if (p <= 0) return;
    const P = pts.map(([c, r]) => [L.x0 + c * CW, L.y0 + r * L.lh]);
    const k = Math.floor(p * 6) / 6, shown = B.trim(P, 0, Math.max(0.001, k));
    B.strokeReveal(S, shown, 1, { width: Math.max(2, L.u * 0.28), color: PAL.mid, cap: "square", join: "miter" });
    if (k >= 1) {
      const e = P[P.length - 1], s = L.u * 1.3;
      S.fillStyle = PAL.bright;
      S.fillRect(e[0] - s / 2, e[1] - s / 2, s, s);
    }
  }
  /** A block meter "[####....] label": one solid block per filled cell, a dot per empty one. */
  function meter(c, r, n, total, label, col = PAL.mid) {
    put("[", c, r, { col });
    for (let i = 0; i < total; i++) {
      S.fillStyle = i < n ? PAL.bright : PAL.dim;
      const bx = L.x0 + (c + 1 + i) * CW + CW * 0.1, by = L.y0 + r * L.lh + L.lh * 0.15;
      if (i < n) S.fillRect(bx, by, CW * 0.8, L.lh * 0.62);
      else S.fillRect(bx + CW * 0.3, by + L.lh * 0.28, CW * 0.2, L.lh * 0.08);
    }
    put("] " + label, c + total + 1, r, { col });
  }
  /** Block digits: each digit from a 3 x 5 grid of solid blocks (like stacked full-block characters). */
  const DIG = { 0: "111101101101111", 1: "010110010010111", 2: "111001111100111", 3: "111001111001111", 4: "101101111001001", 5: "111100111001111", 6: "111100111101111", 7: "111001001001001", 8: "111101111101111", 9: "111101111001111" };
  function blockDigits(str, x, y, cell, roll) {
    [...str].forEach((ch, i) => {
      const bits = DIG[ch] || "";
      for (let k = 0; k < 15; k++) {
        if (bits[k] !== "1") continue;
        const bx = x + (i * 4 + (k % 3)) * cell, by = y + Math.floor(k / 3) * cell + (i === str.length - 1 ? roll * cell : 0);
        S.fillStyle = PAL.bright;
        S.fillRect(bx + cell * 0.06, by + cell * 0.06, cell * 0.88, cell * 0.88);
      }
    });
  }

  // ------------------------------------------------------------------ the session (the setting: replace these)
  /** The headline scale: the longest line fills the text width, up to `cap`. */
  const fit = (lines, cap) => Math.min(cap * (L.P ? 1.15 : 1), (L.glass.x + L.glass.w - (L.P ? 5 : 6) * L.u - L.x0) / (Math.max(...lines.map((l) => l.length)) * CW * 1.04));
  const STATUS = [" DNS 101: WHAT IS A NAME?", " Q: WHO KNOWS THE ADDRESS?", " ROOT SERVERS", " LOOKUP: THREE HOPS", " NEXT TIME: CACHE", " END OF SESSION"];
  function sceneTitle(lt) {
    if (!cmd(lt, 0.95, "man dns", 0)) return;
    const lines = L.P ? ["HOW DNS", "FINDS A", "WEBSITE"] : ["HOW DNS FINDS", "A WEBSITE"], b = fit(lines, 3.3);
    lines.forEach((w, i) => out(lt, 1.42 + i * 0.1, w, 0, 1.5 + i * b, { col: PAL.bright, scale: b }));
    out(lt, 1.85, "[SYS] names in, numbers out", 0, 2 + lines.length * b, { col: PAL.mid });
  }
  function sceneDiagram(lt) {
    if (!cmd(lt, 0.1, "trace example.com", 0)) return;
    const P = L.P;
    const you = P ? [1, 3] : [1, 4.5], res = P ? [1, 7.5] : [12, 4.5], srv = P ? [[17, 4], [17, 7.5], [17, 11]] : [[31, 2], [31, 4.5], [31, 7]];
    const st = (a, d = 0.25) => B.prog(lt, a, d);
    box(you[0], you[1], 5, "YOU", st(0.88, 0.1));
    wire(P ? [[3.5, you[1] + 1.4], [3.5, res[1] - 0.45]] : [[you[0] + 5.6, you[1] + 0.5], [res[0] - 0.7, res[1] + 0.5]], st(0.9, 0.1));
    box(res[0], res[1], 8, "RESOLVER", st(0.92, 0.1));
    ["ROOT", ".COM", "NS"].forEach((name, i) => {
      const [c, r] = srv[i], a = 0.95 + i * 0.04;
      const ex = res[0] + 8.7, ey = res[1] + 0.5;
      wire(P ? [[ex, ey], [ex + 2.6, ey], [ex + 2.6, r + 0.5], [c - 0.75, r + 0.5]] : [[ex, ey], [ex + 4, ey], [ex + 4, r + 0.5], [c - 0.75, r + 0.5]], st(a - 0.1));
      box(c, r, 6, name, st(a, 0.18));
      if (lt > a + 0.25) put(tagTxt("OK"), c + 7.4, r, { col: PAL.mid });
    });
    out(lt, 1.0, P ? "it asks three servers" : "the resolver asks three servers for you", 0, P ? 12.4 : 8.9, { col: PAL.mid });
  }
  function sceneNumber(lt) {
    if (!cmd(lt, 0.15, "count root-servers", 0)) return;
    const k = B.prog(lt, 1.0, 0.7), n = Math.floor(k * 13 + 1e-6), step = (lt - 1.0) / (0.7 / 13);
    const roll = k < 1 ? Math.round((1 - B.fract(step)) * 2) / 2 : 0; // the last digit rolls up in steps
    const cell = L.u * 8, x = L.x0, y = L.y0 + (L.P ? 2 : 1.6) * L.lh;
    if (lt > 0.97) {
      S.save();
      S.beginPath();
      S.rect(x - cell, y - cell * 0.2, cell * 12, cell * 5.4);
      S.clip();
      blockDigits(String(n).padStart(2, "0"), x, y, cell, roll);
      S.restore();
      // the meter: a row of 13 blocks filling with the count
      const mr = L.P ? 2 + (cell * 5.8) / L.lh : 2.2, mc = L.P ? 0 : 23, cr = L.P ? mr + 2 : 4.2;
      meter(mc, mr, n, 13, n + "/13");
      out(lt, 1.0, L.P ? "root server names: A to M" : "names: A to M", mc, cr, { col: PAL.bright });
      (L.P ? ["each one copied worldwide"] : ["each one copied", "worldwide"]).forEach((l, i) => out(lt, 1.1, l, mc, cr + 1.2 + i, { col: PAL.mid }));
      const sr = L.P ? cr + 2.6 : 8.4, sys = "[SYS] 13 names, 1,500+ copies";
      if (out(lt, 1.3, sys, 0, sr, { col: PAL.mid })) CUR = [sys.length + 1, sr, false]; // cursor at the line end, clear of the status bar
    }
  }
  function sceneSteps(lt) {
    if (!cmd(lt, 0.1, "dig example.com", 0)) return;
    if (out(lt, 0.85, tagTxt("WARN"), 0, 1, { rev: true, col: PAL.bright, keepCursor: true })) put("not in cache", 7, 1, { col: PAL.mid });
    if (lt < 0.95) return;
    // the table prints at once; each hop's answer lands in turn, and a meter counts the hops
    const rows = [["1 ROOT", "try .com"], ["2 .COM", "try its NS"], ["3 NS", "203.0.113.7"]], gap = L.P ? 2.6 : 1.4;
    let done = 0;
    rows.forEach(([who, what], i) => {
      const a = 1.1 + i * 0.25, r = 3 + i * gap;
      put(" " + who.padEnd(7) + "->", 0, r, { col: PAL.bright });
      const ac = L.P ? 12 : 17;
      if (lt < a) return put(".".repeat(1 + (Math.floor(lt * 8) % 3)), ac, r, { col: PAL.mid });
      done += 1;
      const emph = i === 2 && lt > a + 0.3 && !(lt > a + 0.42 && lt < a + 0.54); // flips to reversed, blinks once
      put(what, ac, r, emph ? { rev: true, col: PAL.bright } : { col: PAL.mid });
      put(tagTxt("OK"), L.P ? 25 : 36, r, { col: PAL.mid });
    });
    const mr = 3 + 2 * gap + (L.P ? 2.4 : 1.6);
    meter(0, mr, done * (L.P ? 3 : 6), L.P ? 9 : 18, done + "/3 HOPS", done === 3 ? PAL.bright : PAL.mid);
    if (out(lt, 2.0, "[SYS] answer saved in cache", 0, mr + (L.P ? 1.5 : 1.2), { col: PAL.mid })) CUR = [0, mr + (L.P ? 2.7 : 2.2), false];
    else CUR = [0, mr + (L.P ? 1.5 : 1.2), true];
  }
  function sceneCache(lt) {
    if (!cmd(lt, 0.05, "dig example.com", 0)) return;
    if (out(lt, 0.75, tagTxt("OK"), 0, 1.5, { col: PAL.bright, keepCursor: true })) put("cache hit: no trips", 5, 1.5, { col: PAL.mid });
    if (!out(lt, 0.82, "203.0.113.7", 0, 3, { rev: true, col: PAL.bright, scale: L.P ? 1.8 : 2.4 })) return;
    // 9:16 lists the skipped hops under the answer, 16:9 beside it; then the TTL drains in a meter
    const r0 = L.P ? 6.2 : 3, gap = L.P ? 1.25 : 1.2, c0 = L.P ? 0 : 29, end = L.P ? r0 + 3 * gap + 0.4 : 7;
    ["ROOT", ".COM", "NS"].forEach((w, i) => out(lt, 0.85 + i * 0.03, " " + w.padEnd(6) + "skipped", c0, r0 + i * gap, { col: PAL.mid }));
    if (!out(lt, 0.92, "[SYS] kept until TTL ends", 0, end, { col: PAL.mid })) return;
    meter(0, end + 1.4, 12 - Math.min(3, Math.floor(Math.max(0, lt - 1.2) / 0.15)), 12, "TTL 1 h");
    CUR = [0, end + 2.6, false];
  }
  function sceneClose(lt) {
    const lines = L.P ? ["NAMES IN,", "NUMBERS", "OUT."] : ["NAMES IN,", "NUMBERS OUT."], b = fit(lines, 3.3), r = 0.6 + lines.length * b;
    lines.forEach((w, i) => out(lt, 0.3 + i * 0.15, w, 0, 0.6 + i * b, { col: PAL.bright, scale: b }));
    out(lt, 0.75, "[SYS] lookup complete", 0, r + 0.2, { col: PAL.mid });
    if (lt > 0.95) {
      put("> ", 0, r + 1.3, { col: PAL.mid });
      CUR = [2, r + 1.3, false];
    }
  }
  const SCENES = [sceneTitle, sceneDiagram, sceneNumber, sceneSteps, sceneCache, sceneClose];
  const ROLL = { 2: true, 5: true }; // scenes that arrive by a vertical roll; the others by a quick clear

  /** Paint one scene's screen (text area) with an optional vertical offset. */
  function paintScene(i, t, dy) {
    S.save();
    S.translate(0, dy);
    CUR = null;
    SCENES[i](t - BEATS[i]);
    if (CUR && t > 0.9) {
      const on = CUR[2] || Math.floor(t * 2.6) % 2 === 0;
      if (on) {
        S.fillStyle = PAL.bright;
        S.fillRect(L.x0 + CUR[0] * CW, L.y0 + CUR[1] * L.lh + L.lh * 0.08, CW * 0.9, L.lh * 0.8);
      }
    }
    S.restore();
  }
  function statusBar(i, t) {
    const y = L.status, x = L.x0 - CW * 0.5, w = L.glass.x + L.glass.w - (L.P ? 5 : 6) * L.u - x;
    S.fillStyle = PAL.mid;
    S.fillRect(x, y, w, L.lh * 1.05);
    const f = B.font(Math.max(L.fs * 0.72, L.u * 4.8), MONO, 400), ty = y + L.lh * 0.53, m = S.getTransform();
    REVS.push([STATUS[i], x + CW * 0.3, ty, f, m, "middle", "left"], [(i + 1) + "/6", x + w - CW * 0.6, ty, f, m, "middle", "right"]);
    if (!L.P) return;
    // 9:16 uses the tube's full height: a double rule over the text and a session strip under the status bar
    const ry = L.glass.y + (L.y0 - L.glass.y) * 0.45, sw = (w - 5 * CW * 0.6) / 6;
    S.fillStyle = PAL.dim;
    S.fillRect(x, ry, w, L.u * 0.4);
    S.fillRect(x, ry + L.u * 1.2, w, L.u * 0.4);
    for (let k = 0; k < 6; k++) {
      S.fillStyle = k <= i ? PAL.mid : PAL.dim;
      S.fillRect(x + k * (sw + CW * 0.6), y + L.lh * 1.8, sw, L.lh * 0.45);
    }
  }
  /** Dark letters of reversed text, drawn over the bloomed picture so the halo never fills them in. */
  function restamp(Q) {
    REVS.forEach(([str, x, y, f, m, base, align]) => {
      Q.save();
      Q.setTransform(m);
      Q.font = f;
      Q.textBaseline = base;
      Q.textAlign = align;
      Q.fillStyle = Q.strokeStyle = PAL.black;
      Q.lineWidth = L.u * 0.25;
      Q.strokeText(str, x, y);
      Q.fillText(str, x, y);
      Q.restore();
    });
  }

  // ------------------------------------------------------------------ the tube: bloom, scanlines, roll bar, barrel, fringe
  function barrel(src, W, H, g, k) {
    const tmp = B.scratch("term-barrel", W, H), n = 72, cx = g.x + g.w / 2, cy = g.y + g.h / 2;
    for (let i = 0; i < n; i++) {
      const y = g.y + (i * g.h) / n, h = g.h / n, d = (y + h / 2 - cy) / (g.h / 2), s = 1 - k * d * d;
      tmp.drawImage(src, g.x, y, g.w, h + 0.5, cx - (g.w * s) / 2, y, g.w * s, h + 0.5);
    }
    const dst = B.scratch("term-barrel2", W, H);
    for (let j = 0; j < n; j++) {
      const x = g.x + (j * g.w) / n, w = g.w / n, d = (x + w / 2 - cx) / (g.w / 2), s = 1 - k * 0.8 * d * d;
      dst.drawImage(tmp.canvas, x, g.y, w + 0.5, g.h, x, cy - (g.h * s) / 2, w + 0.5, g.h * s);
    }
    return dst.canvas;
  }
  const glassPath = (c, g, r) => B.roundRect(c, g.x, g.y, g.w, g.h, r);

  function draw(ctx, W, H, t) {
    L = layout(W, H);
    T = t;
    const u = L.u, g = L.glass;
    S = B.scratch("term-screen", W, H);
    REVS = [];
    S.font = B.font(L.fs, VT, 400);
    CW = S.measureText("0").width;
    S.fillStyle = PAL.black;
    S.fillRect(g.x, g.y, g.w, g.h);
    const bt = B.beat(t, BEATS, DUR), i = bt.i;
    // power-on: a bright dot, a line, a flashing field, then steady light
    if (t < 0.9) {
      const cx = g.x + g.w / 2, cy = g.y + g.h / 2;
      if (t < 0.2) B.glow(S, cx, cy, u * (2 + t * 20), PAL.bloom, 1);
      else if (t < 0.4) {
        const w = g.w * B.ease.outCubic(B.prog(t, 0.2, 0.2));
        S.fillStyle = PAL.bloom;
        S.fillRect(cx - w / 2, cy - u * 0.4, w, u * 0.8);
      } else {
        const h = g.h * B.ease.outCubic(B.prog(t, 0.4, 0.15)), fl = Math.floor(t * 20) % 2 ? 0.7 : 0.35;
        S.fillStyle = B.rgba(PAL.mid, fl * (1 - B.prog(t, 0.55, 0.35)));
        S.fillRect(g.x, cy - h / 2, g.w, h);
      }
    } else {
      // scene change: a vertical roll (old picture rolls up, a black bar, the new one) or a quick clear
      const r = ROLL[i] ? B.prog(t, BEATS[i], 0.3) : 1, clear = !ROLL[i] && i > 0 && t - BEATS[i] < 0.12;
      if (r < 1) {
        const step = Math.floor(r * 8) / 8; // the roll jumps in frames, it does not glide
        paintScene(i - 1, BEATS[i] - 0.01, -step * g.h * 1.1);
        paintScene(i, t, (1 - step) * g.h * 1.1);
        S.fillStyle = PAL.black;
        S.fillRect(g.x, g.y + (1 - step) * g.h * 1.1 - g.h * 0.1, g.w, g.h * 0.1);
      } else if (!clear) paintScene(i, t, 0);
      if (!clear) statusBar(i, t);
    }
    S.save(); // keep everything on the glass
    S.globalCompositeOperation = "destination-in";
    S.fillStyle = "#000";
    S.fillRect(g.x, g.y, g.w, g.h);
    S.restore();
    // bloom: the bright picture blurred at quarter size and added back over itself (strong)
    const q = 4, gl = B.scratch("term-glow", Math.ceil(W / q), Math.ceil(H / q));
    gl.filter = `blur(${(u * 0.45).toFixed(1)}px)`;
    gl.drawImage(S.canvas, 0, 0, W / q, H / q);
    gl.filter = "none";
    // tint the halo toward pure phosphor green, so light added over light stays green and never burns to white
    gl.globalCompositeOperation = "multiply";
    gl.fillStyle = "#28a03c";
    gl.fillRect(0, 0, gl.canvas.width, gl.canvas.height);
    gl.globalCompositeOperation = "source-over";
    const Q = B.scratch("term-tube", W, H);
    Q.fillStyle = PAL.black;
    Q.fillRect(g.x, g.y, g.w, g.h);
    Q.drawImage(S.canvas, 0, 0);
    Q.globalCompositeOperation = "lighter";
    Q.imageSmoothingQuality = "high";
    Q.globalAlpha = 0.8;
    Q.drawImage(gl.canvas, 0, 0, W, H);
    Q.globalAlpha = 0.5;
    Q.filter = `blur(${(u * 1.2).toFixed(1)}px)`;
    Q.drawImage(gl.canvas, 0, 0, W, H);
    Q.filter = "none";
    Q.globalAlpha = 1;
    Q.globalCompositeOperation = "source-over";
    restamp(Q);
    // a faint lit-phosphor haze over the black, scanlines, a broad dim bar rolling down, flicker
    Q.fillStyle = B.rgba(PAL.dim, 0.07);
    Q.fillRect(g.x, g.y, g.w, g.h);
    B.scanlines(Q, W, H, { gap: Math.max(3, Math.round(u * 0.42)), alpha: 0.38 });
    const by = g.y + B.fract(t / 5.5) * (g.h * 1.4) - g.h * 0.2;
    Q.fillStyle = B.linear(Q, 0, by - g.h * 0.12, 0, by + g.h * 0.12, ["rgba(0,0,0,0)", "rgba(0,0,0,0.13)", "rgba(0,0,0,0)"]);
    Q.fillRect(g.x, by - g.h * 0.12, g.w, g.h * 0.24);
    B.cover(Q, W, H, "#000", 0.06 * (B.flicker(t, 1, 15, 3) - 0.6));
    const bent = barrel(Q.canvas, W, H, g, 0.075);

    // the monitor: bezel, glass, picture, fringe, vignette, reflection
    ctx.fillStyle = PAL.bezel;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = B.linear(ctx, 0, 0, 0, H, ["rgba(255,255,255,0.06)", "rgba(0,0,0,0.25)"]);
    ctx.fillRect(0, 0, W, H);
    const rr = u * (L.P ? 6 : 5);
    ctx.save();
    ctx.beginPath();
    B.roundRect(ctx, g.x - u * 1.6, g.y - u * 1.6, g.w + u * 3.2, g.h + u * 3.2, rr + u);
    ctx.fillStyle = B.shade(PAL.bezel, -0.45);
    ctx.fill();
    ctx.beginPath();
    glassPath(ctx, g, rr);
    ctx.clip();
    ctx.fillStyle = PAL.black;
    ctx.fillRect(g.x, g.y, g.w, g.h);
    ctx.drawImage(bent, 0, 0);
    // faint red and blue fringe: the picture, tinted, a hair bigger / smaller, added toward the edges
    const fr = B.scratch("term-fringe", W, H);
    [["#ff2a2a", 1.006], ["#2a5cff", 0.994]].forEach(([col, s]) => {
      fr.globalCompositeOperation = "source-over";
      fr.fillStyle = "#000";
      fr.fillRect(0, 0, W, H);
      fr.drawImage(bent, W / 2 - (W * s) / 2, H / 2 - (H * s) / 2, W * s, H * s);
      fr.globalCompositeOperation = "multiply";
      fr.fillStyle = col;
      fr.fillRect(0, 0, W, H);
      fr.globalCompositeOperation = "destination-in";
      fr.fillStyle = B.radial(fr, W / 2, H / 2, Math.min(g.w, g.h) * 0.42, Math.hypot(g.w, g.h) * 0.55, [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,1)"]]);
      fr.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.3;
      ctx.drawImage(fr.canvas, 0, 0);
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    });
    ctx.fillStyle = B.radial(ctx, g.x + g.w / 2, g.y + g.h / 2, Math.min(g.w, g.h) * 0.35, Math.hypot(g.w, g.h) * 0.56, [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0.6)"]]);
    ctx.fillRect(g.x, g.y, g.w, g.h);
    // window reflection sweeping slowly across the glass, plus a curved highlight on the bulge
    const sx = g.x - g.w * 0.6 + B.fract(t / 9 + 0.15) * g.w * 2.2;
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = B.linear(ctx, sx, 0, sx + g.w * 0.35, 0, ["rgba(201,214,204,0)", "rgba(201,214,204,0.05)", "rgba(201,214,204,0)"]);
    ctx.beginPath();
    B.poly(ctx, [[sx, g.y], [sx + g.w * 0.28, g.y], [sx + g.w * 0.08, g.y + g.h], [sx - g.w * 0.2, g.y + g.h]], true);
    ctx.fill();
    ctx.fillStyle = B.radial(ctx, g.x + g.w * 0.28, g.y + g.h * 0.16, 0, g.w * 0.45, [[0, B.rgba(PAL.glare, 0.07)], [1, B.rgba(PAL.glare, 0)]]);
    ctx.fillRect(g.x, g.y, g.w, g.h);
    ctx.restore();
    // bezel bevel and a green power lamp
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = u * 0.4;
    ctx.beginPath();
    B.roundRect(ctx, g.x - u * 1.8, g.y - u * 1.8, g.w + u * 3.6, g.h + u * 3.6, rr + u);
    ctx.stroke();
    const lx = g.x + g.w - u * 3, ly = Math.min(H - u * 3, g.y + g.h + (L.P ? 5 : 2.4) * u);
    ctx.fillStyle = t > 0.05 ? PAL.mid : "#1a2a1c";
    ctx.beginPath();
    B.circle(ctx, lx, ly, u * 0.6);
    ctx.fill();
    if (t > 0.05) B.glow(ctx, lx, ly, u * 2.5, PAL.mid, 0.5, { add: true });
  }

  // ------------------------------------------------------------------ sound: key ticks synced to typing, hum and power thunk, square beeps, a buzz
  SOUND.define("term-thunk", (v) => {
    // relay and degauss at power-on: a hard click, a low thump, a short rising whine
    v.noise({ filter: "bandpass", f: 900, q: 1, a: 0.0005, len: 0.03, peak: 0.5 });
    v.tone({ f: 70, f2: 45, glide: 0.25, a: 0.003, len: 0.35, peak: 0.55 });
    v.tone({ type: "sawtooth", f: 60, a: 0.01, len: 0.5, peak: 0.08 });
    v.tone({ f: 7000, f2: 15000, glide: 0.6, a: 0.05, len: 0.4, peak: 0.015 });
  }, { verb: 0.1 });
  SOUND.define("term-buzz", (v) => {
    // the harsh error buzz: two detuned low squares
    v.tone({ type: "square", f: 98, a: 0.003, hold: 0.22, len: 0.04, peak: 0.12, shape: "lin" });
    v.tone({ type: "square", f: 104, a: 0.003, hold: 0.22, len: 0.04, peak: 0.08, shape: "lin" });
  }, { verb: 0.05 });

  function score(k) {
    k.bed("hum", 0.05, DUR, { gain: 0.9, fade: 0.3 });
    k.at(0.05, "term-thunk", { gain: 1 }).at(0.4, "static", { dur: 0.25, gain: 0.25 });
    const typing = (at, text) => {
      for (let i = 0; i < text.length; i++) k.at(at + i / CPS, "type", { gain: 0.5, pitch: (i * 7) % 5 - 2 });
      k.at(at + text.length / CPS + 0.08, "type", { gain: 0.65, pitch: -5 }); // return key
    };
    const beep = (at, note = "A5") => k.at(at, "blip", { note, gain: 0.8 });
    typing(0.95, "man dns");
    k.at(1.42, "data", { dur: 0.35, gain: 0.5 });
    k.at(1.62, "beep", { note: "E6", dur: 0.08, gain: 0.5 });
    typing(2.3 + 0.1, "trace example.com");
    [0.88, 0.9, 0.92, 0.95, 0.99].forEach((a, i) => k.at(2.3 + a, "tick", { gain: 0.5, pitch: i }));
    [1.2, 1.24, 1.28].forEach((a, i) => beep(2.3 + a, ["A5", "C#6", "E6"][i]));
    k.at(4.4, "static", { dur: 0.3, gain: 0.3 }).at(4.4, "fall", { dur: 0.3, gain: 0.15 });
    typing(4.4 + 0.15, "count root-servers");
    k.repeat(4.4 + 0.75, 0.7 / 13, 13, "blip", { gain: 0.35, vary: 0, note: "E5" });
    beep(4.4 + 1.5, "A6");
    k.at(6.5, "click", { gain: 0.5 });
    typing(6.5 + 0.1, "dig example.com");
    k.at(6.5 + 0.85, "term-buzz", { gain: 1 });
    k.at(6.5 + 0.95, "data", { dur: 0.15, gain: 0.35 });
    [1.1, 1.35, 1.6].forEach((a, i) => beep(6.5 + a, ["A5", "B5", "E6"][i]));
    k.at(9.0, "click", { gain: 0.5 });
    typing(9.0 + 0.05, "dig example.com");
    beep(9.0 + 0.75, "E6");
    k.at(9.0 + 0.82, "blip", { note: "A6", gain: 0.6 });
    k.at(9.0 + 0.9, "data", { dur: 0.2, gain: 0.3 });
    k.at(10.9, "static", { dur: 0.3, gain: 0.3 });
    k.at(11.2, "data", { dur: 0.3, gain: 0.4 });
    beep(11.65, "A5");
    k.at(11.75, "blip", { note: "E6", gain: 0.6 });
  }

  Player.register({
    id: "terminal",
    name: "Green Screen Terminal",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&display=swap",
      faces: ['400 20px "VT323"', '400 20px "Share Tech Mono"'],
    },
    beats: BEATS,
    beatNames: ["Power on + title", "Diagram", "Key number", "Three steps", "Cache", "Close"],
    stills: [2.1, 4.25, 6.3, 8.85, 10.7, 12.3],
    draw,
    score,
  });
})();
