// Render an animation page (window.seek / DURATION / scoreSound) to MP4 with its sound effects.
// Usage: node render.mjs <page.html> <out.mp4> --browser <path> [--ffmpeg <path>] [--no-sandbox] [--fps 30] [--stills 0.1,0.5,0.9]
// Needs ffmpeg (on PATH, or --ffmpeg). Uses the installed Chrome (or Edge) at --browser through puppeteer-core, headless.
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { existsSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname, basename, join } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
const [page_, out_] = args;
const executablePath = opt("--browser", "");
if (!page_ || !out_ || !executablePath) { console.error("usage: node render.mjs <page.html> <out.mp4> --browser <path> [--ffmpeg <path>] [--no-sandbox] [--fps 30] [--stills 0.1,0.5,0.9]"); process.exit(2); }
const FFMPEG = opt("--ffmpeg", "ffmpeg");
// Linux only, when Chrome's sandbox cannot run (root, a downloaded headless shell); the page is local.
const NO_SANDBOX = args.includes("--no-sandbox") ? ["--no-sandbox"] : [];
const FPS = +opt("--fps", 30);
const stills = (opt("--stills", "") || "").split(",").filter(Boolean).map(Number);
const pagePath = resolve(page_), out = resolve(out_);
mkdirSync(dirname(out), { recursive: true });

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--autoplay-policy=no-user-gesture-required", "--allow-file-access-from-files", ...NO_SANDBOX] });
const t0 = Date.now();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(String(e)));
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  await page.setViewport({ width: 1400, height: 900 });
  await page.goto(pathToFileURL(pagePath).href, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction("typeof window.seek === 'function' && window.DURATION > 0", { timeout: 30000 });
  await page.evaluate(() => document.fonts.ready);
  const D = await page.evaluate(() => window.DURATION);
  const n = Math.round(D * FPS);

  // The page's canvas is the frame; take the largest canvas on the page.
  await page.evaluate(() => {
    const cs = [...document.querySelectorAll("canvas")].sort((a, b) => b.width * b.height - a.width * a.height);
    window.__frameCanvas = cs[0];
  });
  const size = await page.evaluate(() => [window.__frameCanvas.width, window.__frameCanvas.height]);

  const ff = spawn(FFMPEG, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", out + ".video.mp4"], { stdio: ["pipe", "inherit", "inherit"] });
  const slow = [];
  for (let i = 0; i < n; i++) {
    const f0 = Date.now();
    const b64 = await page.evaluate((t) => { window.seek(t); return window.__frameCanvas.toDataURL("image/png").split(",")[1]; }, i / FPS);
    slow.push(Date.now() - f0);
    if (!ff.stdin.write(Buffer.from(b64, "base64"))) await new Promise(r => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on("close", c => c === 0 ? res() : rej(new Error("ffmpeg video exit " + c))));

  // Stills for review.
  for (const f of stills) {
    const b64 = await page.evaluate((t) => { window.seek(t); return window.__frameCanvas.toDataURL("image/png").split(",")[1]; }, f * D);
    writeFileSync(join(dirname(out), `${basename(out, ".mp4")}_still_${String(Math.round(f * 100)).padStart(3, "0")}.png`), Buffer.from(b64, "base64"));
  }

  // Sound: render the score offline, 16-bit stereo WAV.
  const hasSound = await page.evaluate(() => typeof window.scoreSound === "function" && !!window.SOUND);
  if (hasSound) {
    const wavB64 = await page.evaluate(async (D) => {
      const r = await SOUND.renderOffline(window.scoreSound, D, 48000, { voiceover: false });
      const peak = Math.max(r.peak, 1e-9), g = peak > 0.98 ? 0.98 / peak : 1;
      const pcm = new Int16Array(r.inter.length);
      for (let i = 0; i < pcm.length; i++) pcm[i] = Math.max(-32768, Math.min(32767, Math.round(r.inter[i] * g * 32767)));
      const bytes = new Uint8Array(44 + pcm.byteLength), v = new DataView(bytes.buffer);
      const w = (o, s) => [...s].forEach((c, k) => v.setUint8(o + k, c.charCodeAt(0)));
      w(0, "RIFF"); v.setUint32(4, 36 + pcm.byteLength, true); w(8, "WAVEfmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
      v.setUint16(22, 2, true); v.setUint32(24, 48000, true); v.setUint32(28, 48000 * 4, true); v.setUint16(32, 4, true); v.setUint16(34, 16, true);
      w(36, "data"); v.setUint32(40, pcm.byteLength, true); bytes.set(new Uint8Array(pcm.buffer), 44);
      let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      return btoa(s);
    }, D);
    writeFileSync(out + ".wav", Buffer.from(wavB64, "base64"));
    await new Promise((res, rej) => spawn(FFMPEG, ["-y", "-loglevel", "error", "-i", out + ".video.mp4", "-i", out + ".wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out], { stdio: "inherit" })
      .on("close", c => c === 0 ? res() : rej(new Error("ffmpeg mux exit " + c))));
  } else {
    await new Promise((res, rej) => spawn(FFMPEG, ["-y", "-loglevel", "error", "-i", out + ".video.mp4", "-c", "copy", out], { stdio: "inherit" })
      .on("close", c => c === 0 ? res() : rej(new Error("ffmpeg copy exit " + c))));
  }
  slow.sort((a, b) => a - b);
  console.log(JSON.stringify({ out, duration: D, frames: n, size, sound: hasSound, render_s: Math.round((Date.now() - t0) / 1000),
    frame_ms_median: slow[n >> 1], frame_ms_p95: slow[Math.floor(n * 0.95)], page_errors: errors.slice(0, 10) }));
} finally {
  await browser.close();
}
