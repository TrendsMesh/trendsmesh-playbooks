/* player.js - the page runtime for TrendsMesh style pages. window.Player
 *
 * The page sets a config before any script runs:
 *   window.TM_PAGE = { width: 1080, height: 1920, mode: "play" | "storyboard", panels: 6, voiceover: false };
 * then inlines brush.js, sound.js, player.js and one style module, which calls:
 *
 *   Player.register({
 *     id: "flat-explainer", name: "Flat Vector Explainer",
 *     duration: 12,                                  // seconds
 *     fonts: { href: "https://fonts.googleapis.com/css2?family=...", faces: ['800 10px "Baloo 2"', ...] },
 *     beats: [0, 2, 4.2, 6.6, 9, 10.8],              // start times of the 5-6 beats
 *     beatNames: ["Title", ...],                     // optional, for storyboard captions
 *     stills: [1.2, ...],                            // optional: exact storyboard panel times
 *     draw(ctx, W, H, t) { ... },                    // the frame at t: a pure function of t
 *     score(k) { ... },                              // the sound score (see sound.js)
 *   });
 *
 * Play mode: one <canvas id="stage"> at width x height (the frame), window.seek(t), window.DURATION,
 * window.scoreSound, and a small player for people. Nothing headless depends on the player: seek draws directly.
 * Storyboard mode: canvases p1..pN at width x height, each the still of one beat, window.STORYBOARD_READY = true
 * once drawn, window.makeSheet() -> PNG data URL contact sheet.
 */
(function () {
  "use strict";
  const cfg = Object.assign({ width: 1280, height: 720, mode: "play", panels: 0, voiceover: false }, window.TM_PAGE || {});
  const W = Math.round(cfg.width), H = Math.round(cfg.height);
  const P = { config: cfg, style: null, W, H };

  function clear(ctx) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    ctx.filter = "none";
    ctx.shadowBlur = 0;
    ctx.shadowColor = "rgba(0,0,0,0)";
    ctx.clearRect(0, 0, W, H);
  }
  /** Draw the style's frame at t onto a W x H context. */
  P.drawAt = function (ctx, t) {
    const s = P.style, d = s.duration;
    t = Math.max(0, Math.min(d, +t || 0));
    ctx.save();
    clear(ctx);
    try {
      s.draw(ctx, W, H, t);
    } finally {
      ctx.restore();
    }
  };

  function waitFonts(style) {
    const f = style.fonts || {};
    let faces = f.faces;
    if (!faces) faces = (f.families || []).flatMap((fam) => [`400 20px "${fam}"`, `700 20px "${fam}"`]);
    if (!document.fonts || !faces.length) return Promise.resolve();
    const loads = Promise.all(faces.map((face) => document.fonts.load(face).catch(() => null))).then(() => document.fonts.ready);
    const timeout = new Promise((res) => setTimeout(res, 8000)); // offline: fall back to system fonts, do not hang
    return Promise.race([loads, timeout]).then(() => window.Brush && Brush.clearLayers());
  }

  function css(text) {
    const st = document.createElement("style");
    st.textContent = text;
    document.head.appendChild(st);
  }
  const fmt = (t) => t.toFixed(1).padStart(4, " ");

  /** Panel times for the storyboard: style.stills, else 60 % of the way into each beat. */
  function panelTimes(style, n) {
    const d = style.duration;
    if (Array.isArray(style.stills) && style.stills.length >= n) return style.stills.slice(0, n);
    const beats = (style.beats || []).slice();
    const pickIdx = (i) => (beats.length <= 1 || n <= 1 ? 0 : Math.round((i * (beats.length - 1)) / (n - 1)));
    const out = [];
    for (let i = 0; i < n; i++) {
      if (beats.length >= n) {
        const bi = beats.length === n ? i : pickIdx(i);
        const a = beats[bi], b = bi + 1 < beats.length ? beats[bi + 1] : d;
        out.push(Math.min(d - 0.01, a + 0.6 * (b - a)));
      } else out.push(((i + 0.6) * d) / n);
    }
    return out;
  }

  // ------------------------------------------------------------------ play mode
  function buildPlayer(style) {
    css(`
      #tm-wrap{position:fixed;inset:0 0 56px 0;display:flex;align-items:center;justify-content:center;overflow:hidden}
      #stage{display:block;background:#000;box-shadow:0 8px 40px rgba(0,0,0,.6)}
      #tm-guides{position:absolute;pointer-events:none;display:none}
      #tm-guides div{position:absolute;left:0;right:0;background:rgba(255,60,60,.18);border:0 dashed rgba(255,90,90,.9)}
      #tm-bar{position:fixed;left:0;right:0;bottom:0;height:56px;display:flex;align-items:center;gap:10px;padding:0 14px;
        background:#1c1c1f;border-top:1px solid #2c2c31;font:13px/1 system-ui,-apple-system,Segoe UI,sans-serif;color:#cfcfd4;box-sizing:border-box}
      #tm-bar button{background:#2b2b31;color:#e8e8ec;border:1px solid #3a3a42;border-radius:6px;padding:7px 11px;font:inherit;cursor:pointer;min-width:64px}
      #tm-bar button[aria-pressed=false]{color:#8a8a92}
      #tm-bar input[type=range]{flex:1;accent-color:#9aa7ff}
      #tm-time{font-variant-numeric:tabular-nums;white-space:pre;min-width:92px;text-align:right}
      #tm-name{color:#8a8a92;max-width:22vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    `);
    const wrap = document.createElement("div");
    wrap.id = "tm-wrap";
    const canvas = document.createElement("canvas");
    canvas.id = "stage";
    canvas.width = W;
    canvas.height = H;
    const guides = document.createElement("div");
    guides.id = "tm-guides";
    wrap.append(canvas, guides);
    const bar = document.createElement("div");
    bar.id = "tm-bar";
    bar.innerHTML = `<button id="tm-play">Play</button><input id="tm-scrub" type="range" min="0" step="0.01" value="0">
      <span id="tm-time"></span><button id="tm-sound" aria-pressed="true">Sound</button><button id="tm-loop" aria-pressed="true">Loop</button>
      <button id="tm-guide" aria-pressed="false" title="Show the safe area (G)">Guides</button><span id="tm-name"></span>`;
    document.body.append(wrap, bar);
    const ctx = canvas.getContext("2d");
    const $ = (id) => document.getElementById(id);
    const D = style.duration;
    const scrub = $("tm-scrub"), timeEl = $("tm-time"), playBtn = $("tm-play");
    scrub.max = String(D);
    $("tm-name").textContent = style.name || style.id;

    // safe-area guides (a DOM overlay, never a canvas, so the frame stays the largest canvas)
    const F = window.Brush ? Brush.frame(W, H) : null;
    if (F) {
      guides.innerHTML = `<div style="top:0;height:${(F.safe.top / H) * 100}%;border-bottom-width:1px"></div>` +
        `<div style="bottom:0;height:${(F.safe.bottom / H) * 100}%;border-top-width:1px"></div>`;
    }

    let current = 0;
    window.seek = function (t) {
      current = Math.max(0, Math.min(D, +t || 0));
      P.drawAt(ctx, current);
      scrub.value = String(current);
      timeEl.textContent = fmt(current) + " / " + fmt(D);
    };

    function fit() {
      const aw = window.innerWidth - 32, ah = window.innerHeight - 56 - 32;
      const s = Math.max(0.05, Math.min(aw / W, ah / H));
      const w = Math.floor(W * s), h = Math.floor(H * s);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      Object.assign(guides.style, { width: w + "px", height: h + "px" });
    }
    window.addEventListener("resize", fit);
    fit();

    let playing = false, sound = null, t0 = 0, wall0 = 0, raf = 0, soundOn = true, loop = true;
    function startSound(from) {
      stopSound();
      if (!soundOn || !window.SOUND || typeof window.scoreSound !== "function") return;
      try {
        sound = SOUND.play(window.scoreSound, from, D, { voiceover: !!cfg.voiceover });
      } catch (e) {
        console.warn("sound failed: " + e.message);
        sound = null;
      }
    }
    function stopSound() {
      if (sound) sound.stop();
      sound = null;
    }
    function tick() {
      if (!playing) return;
      const st = sound && sound.time();
      let t = st != null ? st : t0 + (performance.now() - wall0) / 1000;
      if (t >= D) {
        if (loop) {
          play(0);
          return;
        }
        pause();
        window.seek(D);
        return;
      }
      window.seek(t);
      raf = requestAnimationFrame(tick);
    }
    function play(from) {
      cancelAnimationFrame(raf);
      t0 = from >= D - 0.02 ? 0 : from;
      wall0 = performance.now();
      playing = true;
      playBtn.textContent = "Pause";
      startSound(t0);
      raf = requestAnimationFrame(tick);
    }
    function pause() {
      playing = false;
      cancelAnimationFrame(raf);
      stopSound();
      playBtn.textContent = "Play";
    }
    playBtn.onclick = () => (playing ? pause() : play(current));
    let resumeAfterScrub = false;
    scrub.addEventListener("input", () => {
      if (playing) {
        resumeAfterScrub = true;
        pause();
      }
      window.seek(+scrub.value);
    });
    scrub.addEventListener("change", () => {
      if (resumeAfterScrub) play(current);
      resumeAfterScrub = false;
    });
    const toggle = (btn, on) => btn.setAttribute("aria-pressed", String(on));
    $("tm-sound").onclick = () => {
      soundOn = !soundOn;
      toggle($("tm-sound"), soundOn);
      if (playing) (soundOn ? startSound(current) : stopSound());
    };
    $("tm-loop").onclick = () => {
      loop = !loop;
      toggle($("tm-loop"), loop);
    };
    const guideBtn = $("tm-guide");
    const showGuides = () => {
      const on = guideBtn.getAttribute("aria-pressed") !== "true";
      toggle(guideBtn, on);
      guides.style.display = on ? "block" : "none";
    };
    guideBtn.onclick = showGuides;
    window.addEventListener("keydown", (e) => {
      if (e.target && e.target.tagName === "INPUT" && e.code !== "Space") return;
      if (e.code === "Space") {
        e.preventDefault();
        playing ? pause() : play(current);
      } else if (e.key === "ArrowLeft") window.seek(current - (e.shiftKey ? 0.1 : 1));
      else if (e.key === "ArrowRight") window.seek(current + (e.shiftKey ? 0.1 : 1));
      else if (e.key === "g" || e.key === "G") showGuides();
    });

    window.seek(0);
    P.ready = waitFonts(style).then(() => {
      if (!playing) window.seek(current);
    });
  }

  // ------------------------------------------------------------------ storyboard mode
  function buildStoryboard(style) {
    const n = cfg.panels > 0 ? cfg.panels : Math.max(1, (style.beats || []).length || 6);
    const times = panelTimes(style, n);
    const names = style.beatNames || [];
    const portrait = H > W;
    css(`
      body{padding:24px;box-sizing:border-box}
      #tm-board{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(${portrait ? 220 : 380}px,1fr))}
      #tm-board figure{margin:0;background:#1c1c1f;border:1px solid #2c2c31;border-radius:8px;padding:10px}
      #tm-board canvas{width:100%;height:auto;display:block;background:#000}
      #tm-board figcaption{font:13px system-ui,sans-serif;color:#bdbdc4;margin-top:8px}
      h1{font:600 16px system-ui,sans-serif;color:#d8d8dd;margin:0 0 16px}
    `);
    const h1 = document.createElement("h1");
    h1.textContent = (style.name || style.id) + " - storyboard";
    const board = document.createElement("div");
    board.id = "tm-board";
    const panels = [];
    for (let i = 0; i < n; i++) {
      const fig = document.createElement("figure");
      const c = document.createElement("canvas");
      c.id = "p" + (i + 1);
      c.width = W;
      c.height = H;
      const cap = document.createElement("figcaption");
      cap.textContent = `${i + 1}. ${names[i] || "Beat " + (i + 1)}  (${times[i].toFixed(1)} s)`;
      fig.append(c, cap);
      board.append(fig);
      panels.push(c);
    }
    document.body.append(h1, board);
    window.STORYBOARD_READY = false;
    P.ready = waitFonts(style).then(() => {
      panels.forEach((c, i) => P.drawAt(c.getContext("2d"), times[i]));
      window.STORYBOARD_READY = true;
    });

    /** Contact sheet of all panels with captions -> PNG data URL. */
    window.makeSheet = function () {
      const cols = n <= 3 ? n : portrait ? Math.min(n, n === 4 ? 4 : 3) : n === 4 ? 2 : 3;
      const rows = Math.ceil(n / cols);
      const tw = portrait ? 360 : 560, th = Math.round((tw * H) / W), pad = 24, cap = 34, head = 52;
      const sheet = document.createElement("canvas");
      sheet.width = pad + cols * (tw + pad);
      sheet.height = head + rows * (th + cap + pad) + pad / 2;
      const g = sheet.getContext("2d");
      g.fillStyle = "#18181b";
      g.fillRect(0, 0, sheet.width, sheet.height);
      g.fillStyle = "#e4e4e8";
      g.font = "600 20px system-ui, sans-serif";
      g.textBaseline = "middle";
      g.fillText(`${style.name || style.id}  -  ${W}x${H}  -  ${style.duration} s`, pad, head / 2 + 4);
      panels.forEach((c, i) => {
        const x = pad + (i % cols) * (tw + pad), y = head + Math.floor(i / cols) * (th + cap + pad);
        g.imageSmoothingQuality = "high";
        g.drawImage(c, x, y, tw, th);
        g.strokeStyle = "#34343a";
        g.strokeRect(x + 0.5, y + 0.5, tw - 1, th - 1);
        g.fillStyle = "#bdbdc4";
        g.font = "15px system-ui, sans-serif";
        g.fillText(`${i + 1}. ${names[i] || "Beat " + (i + 1)}  ${times[i].toFixed(1)} s`, x, y + th + cap / 2 + 2);
      });
      return sheet.toDataURL("image/png");
    };
  }

  /** Called once by the style module. */
  P.register = function (style) {
    if (P.style) throw new Error("Player.register: one style per page");
    for (const key of ["id", "name", "duration", "draw"]) if (style[key] == null) throw new Error("Player.register: style needs " + key);
    if (!(style.duration > 0)) throw new Error("Player.register: duration must be > 0");
    if (typeof style.draw !== "function") throw new Error("Player.register: draw must be a function");
    if (!Array.isArray(style.beats) || style.beats.length < 2) console.warn("Player.register: give beats (5-6 start times)");
    P.style = style;
    window.DURATION = style.duration;
    window.scoreSound = function (k) {
      if (typeof style.score === "function") style.score(k);
    };
    const go = () => (cfg.mode === "storyboard" ? buildStoryboard(style) : buildPlayer(style));
    if (document.body) go();
    else document.addEventListener("DOMContentLoaded", go);
  };

  window.Player = P;
})();
