// Make the style previews: for each style's reference animation, a poster JPG from its best moment and a 4 s muted
// loop MP4, both rendered at 1080x1920 (9:16) and delivered small, into data/styles/previews/.
// Usage: node previews.mjs --browser <chrome> [--ffmpeg ffmpeg] [--only 14,flat-explainer] [--force] [--no-sandbox]
//   --only   style numbers or styleIds (default: every card in styles.json)
//   --force  re-make previews that already exist (default: only styles whose module or card changed, see below)
// Writes data/styles/previews/NN_<styleId>.jpg, NN_<styleId>.mp4 and previews.json (one entry per style: the files,
// their sizes, the poster time, the loop window and the hash of the module + card it was made from). Re-run it after a
// style's module or card changes: a style whose hash still matches is skipped.
//
// The best moment: the card's previewAt if it has one ({ poster: t, loop: t0 }), else the beat named like a key
// number ("number", "stat", "%"), else the title beat, at the style's own storyboard still time for that beat
// (style.stills, else 60 % into the beat: a preview keeps this moment of its own, while a storyboard panel is its beat's
// end, player.js). The loop is the 4 s around it, and its last 0.5 s cross-fades into its
// first frame so it plays round without a jump.
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync, rmSync } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";

const HERE = dirname(fileURLToPath(import.meta.url));
const STYLES = resolve(HERE, "../data/styles");
const OUT = join(STYLES, "previews");
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const browserPath = opt("--browser", "");
if (!browserPath) { console.error("usage: node previews.mjs --browser <chrome> [--ffmpeg ffmpeg] [--only 1,14] [--force]"); process.exit(2); }
const FFMPEG = opt("--ffmpeg", "ffmpeg");
const FORCE = args.includes("--force");
const NO_SANDBOX = args.includes("--no-sandbox") ? ["--no-sandbox"] : [];
const only = (opt("--only", "") || "").split(",").filter(Boolean);

const W = 1080, H = 1920;                 // rendered
const POSTER = [540, 960], LOOP = [360, 640];   // delivered
const LOOP_S = 4, FADE_S = 0.5, FPS = 24;
const POSTER_KB = 60, LOOP_KB = [160, 250];   // KiB; a loop stays under the plugin directory's 256 KiB a file

const read = (p) => readFileSync(p, "utf8").replace(/\r/g, "");
const cards = JSON.parse(read(join(STYLES, "styles.json")));
const pad = (n) => String(n).padStart(2, "0");
const wanted = cards.filter((c) => !only.length || only.includes(String(c.order)) || only.includes(c.styleId));

function page(module, title) {
  const font = module.match(/https:\/\/fonts\.googleapis\.com\/css2\?[^"'`\s]+/);
  const link = font ? `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link rel="stylesheet" href="${font[0].replace(/&/g, "&amp;")}">` : "";
  const code = ["brush.js", "sound.js", "player.js"].map((n) => read(join(STYLES, "lib", n))).concat([module]);
  const scripts = code.map((c) => "<script>\n" + c.trimEnd().replace(/<\/script/g, "<\\/script") + "\n</script>").join("\n");
  const cfg = { width: W, height: H, mode: "play", panels: 0, voiceover: false };
  return read(join(STYLES, "lib", "page.html")).replace("{{TITLE}}", title).replace("{{FONTS_LINK}}", link)
    .replace("{{CONFIG}}", JSON.stringify(cfg)).replace("{{SCRIPTS}}", scripts);
}

function run(cmd, a) {
  return new Promise((res, rej) => spawn(cmd, a, { stdio: ["ignore", "inherit", "inherit"] })
    .on("close", (c) => (c === 0 ? res() : rej(new Error(cmd + " exit " + c)))));
}

mkdirSync(OUT, { recursive: true });
const manifestPath = join(OUT, "previews.json");
const manifest = existsSync(manifestPath) ? JSON.parse(read(manifestPath)) : {};
const browser = await puppeteer.launch({ executablePath: browserPath, headless: true, args: ["--allow-file-access-from-files", ...NO_SANDBOX] });
const tmp = join(tmpdir(), "tm-previews-" + process.pid);
mkdirSync(tmp, { recursive: true });
const report = [];
try {
  for (const card of wanted) {
    const stem = `${pad(card.order)}_${card.styleId}`;
    const module = read(join(STYLES, "styles", stem + ".js"));
    const hash = createHash("sha256").update(module).update(JSON.stringify(card)).digest("hex").slice(0, 16);
    const jpg = join(OUT, stem + ".jpg"), mp4 = join(OUT, stem + ".mp4");
    if (!FORCE && manifest[card.styleId]?.hash === hash && existsSync(jpg) && existsSync(mp4)) { report.push({ style: stem, skipped: true }); continue; }
    const htmlPath = join(tmp, stem + ".html");
    writeFileSync(htmlPath, page(module, card.name));
    const p = await browser.newPage();
    const errors = [];
    p.on("pageerror", (e) => errors.push(String(e)));
    p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await p.setViewport({ width: 1200, height: 900 });
    await p.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle0", timeout: 90000 });
    await p.waitForFunction("typeof window.seek === 'function' && window.DURATION > 0", { timeout: 30000 });
    await p.evaluate(() => document.fonts.ready.then(() => window.Brush && Brush.clearLayers()));

    // The best moment, from the style's own beats.
    const when = await p.evaluate((pre) => {
      const s = Player.style, D = window.DURATION, beats = s.beats || [0], names = s.beatNames || [];
      const still = (i) => (Array.isArray(s.stills) && s.stills[i] != null ? s.stills[i]
        : beats[i] + 0.6 * ((i + 1 < beats.length ? beats[i + 1] : D) - beats[i]));
      let i = names.findIndex((n) => /number|stat|%|count|figure/i.test(n));
      if (i < 0) i = names.findIndex((n) => /title/i.test(n));
      if (i < 0) i = 0;
      const poster = pre && pre.poster != null ? pre.poster : still(i);
      let t0 = pre && pre.loop != null ? pre.loop : Math.max(0, poster - 1.8);
      t0 = Math.min(t0, Math.max(0, D - 4 - 0.5));
      return { D, poster: +poster.toFixed(2), loop: +t0.toFixed(2), beat: names[i] || "beat " + (i + 1) };
    }, card.previewAt || null);

    // Downscale in the page (high-quality smoothing), hand back small JPEG frames.
    await p.evaluate((PW, PH, LW, LH) => {
      const stage = [...document.querySelectorAll("canvas")].sort((a, b) => b.width * b.height - a.width * a.height)[0];
      const mk = (w, h) => { const c = document.createElement("canvas"); c.width = w; c.height = h; const g = c.getContext("2d"); g.imageSmoothingQuality = "high"; return [c, g]; };
      const [pc, pg] = mk(PW, PH), [lc, lg] = mk(LW, LH);
      window.__poster = (t) => { window.seek(t); pg.drawImage(stage, 0, 0, PW, PH); return pc.toDataURL("image/png").split(",")[1]; };
      window.__loop = (a, aB, k) => {                  // frame at a, cross-faded with frame at aB by weight k
        window.seek(a); lg.globalAlpha = 1; lg.drawImage(stage, 0, 0, LW, LH);
        if (k > 0) { window.seek(aB); lg.globalAlpha = k; lg.drawImage(stage, 0, 0, LW, LH); lg.globalAlpha = 1; }
        return lc.toDataURL("image/png").split(",")[1];
      };
    }, ...POSTER, ...LOOP);

    // Poster: JPEG quality stepped down until it is about POSTER_KB.
    const posterPng = join(tmp, stem + "_poster.png");
    writeFileSync(posterPng, Buffer.from(await p.evaluate((t) => window.__poster(t), when.poster), "base64"));
    // Busy textures (halftone, grain) stay big in JPEG: past q 9 the poster is made smaller instead (432x768).
    const steps = [4, 5, 6, 7, 8, 9].map((q) => [q, null]).concat([6, 7, 8, 9, 10, 11].map((q) => [q, "432:768"]));
    for (const [q, scale] of steps) {
      await run(FFMPEG, ["-y", "-loglevel", "error", "-i", posterPng, ...(scale ? ["-vf", "scale=" + scale + ":flags=lanczos"] : []), "-q:v", String(q), jpg]);
      if (statSync(jpg).size <= POSTER_KB * 1024 * 1.1) break;
    }

    // Loop: 4 s from t0; over its first FADE_S the frame from t0 + 4 fades out, so the end meets the start.
    const fdir = join(tmp, stem); rmSync(fdir, { recursive: true, force: true }); mkdirSync(fdir);
    const n = LOOP_S * FPS;
    for (let f = 0; f < n; f++) {
      const s = f / FPS, k = s < FADE_S ? 1 - s / FADE_S : 0;
      const b64 = await p.evaluate((a, aB, k) => window.__loop(a, aB, k), when.loop + s, when.loop + s + LOOP_S, k);
      writeFileSync(join(fdir, `f${String(f).padStart(4, "0")}.png`), Buffer.from(b64, "base64"));
    }
    let crf = 26;
    for (let tries = 0; tries < 8; tries++) {
      await run(FFMPEG, ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", join(fdir, "f%04d.png"), "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "slow", "-crf", String(crf), "-movflags", "+faststart", mp4]);
      const kb = statSync(mp4).size / 1024;
      if (kb > LOOP_KB[1]) crf += 2; else if (kb < LOOP_KB[0] * 0.6 && crf > 18) crf -= 2; else break;
    }
    await p.close();
    manifest[card.styleId] = { order: card.order, poster: stem + ".jpg", loop: stem + ".mp4", poster_t: when.poster,
      loop_from: when.loop, loop_s: LOOP_S, beat: when.beat, poster_kb: Math.round(statSync(jpg).size / 1024),
      loop_kb: Math.round(statSync(mp4).size / 1024), hash };
    report.push({ style: stem, ...manifest[card.styleId], page_errors: errors.slice(0, 5) });
    console.log(JSON.stringify(report.at(-1)));
  }
} finally {
  await browser.close();
  rmSync(tmp, { recursive: true, force: true });
}
const sorted = Object.fromEntries(Object.entries(manifest).sort((a, b) => a[1].order - b[1].order));
writeFileSync(manifestPath, JSON.stringify(sorted, null, 1) + "\n");
const all = Object.values(sorted);
console.log(JSON.stringify({ styles: all.length, made: report.filter((r) => !r.skipped).length,
  total_kb: all.reduce((a, e) => a + e.poster_kb + e.loop_kb, 0), errors: report.filter((r) => r.page_errors?.length).map((r) => r.style) }));
