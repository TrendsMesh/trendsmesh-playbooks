// Render the storyboard page's panel canvases to PNG (1080x1920 each) plus a contact sheet.
// Usage: node storyboard.mjs <storyboard.html> <out_dir> --browser <path> [--no-sandbox]
// The page says how many panels it draws (window.STORYBOARD_PANELS: one per beat), else its canvases p1 ... pN count.
// Same toolchain as render.mjs: puppeteer-core driving the installed Chrome/Edge at --browser, headless.
// Never overwrites: refuses if a target file already exists.
import puppeteer from "puppeteer-core";
import { readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const [page_, outDir_] = args;
const executablePath = opt("--browser", "");
if (!page_ || !outDir_ || !executablePath) { console.error("usage: node storyboard.mjs <page.html> <out_dir> --browser <path> [--no-sandbox]"); process.exit(2); }
// Linux only, when Chrome's sandbox cannot run (root, a downloaded headless shell); the page is local.
const NO_SANDBOX = args.includes("--no-sandbox") ? ["--no-sandbox"] : [];
const outDir = resolve(outDir_); mkdirSync(outDir, { recursive: true });
const sheetPath = join(outDir, "sheet.png");
const taken = readdirSync(outDir).filter((n) => /^panel_\d+\.png$/.test(n) || n === "sheet.png");
if (taken.length) { console.error("refusing to overwrite " + join(outDir, taken[0])); process.exit(3); }

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--allow-file-access-from-files", ...NO_SANDBOX] });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.setViewport({ width: 1300, height: 1000 });
  await page.goto(pathToFileURL(resolve(page_)).href, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction("window.STORYBOARD_READY === true", { timeout: 60000 });
  const panels = await page.evaluate(() => window.STORYBOARD_PANELS
    || [...document.querySelectorAll("canvas")].filter((c) => /^p\d+$/.test(c.id)).length);
  if (!(Number.isInteger(panels) && panels > 0)) throw new Error("the page draws no storyboard panels (no canvas p1)");
  const ids = Array.from({ length: panels }, (_, k) => k + 1);
  const targets = ids.map((i) => join(outDir, `panel_${String(i).padStart(2, "0")}.png`));
  const sizes = [];
  for (let n = 0; n < ids.length; n++) {
    const got = await page.evaluate((id) => { const c = document.getElementById("p" + id); return c && c.toDataURL ? [c.width, c.height, c.toDataURL("image/png").split(",")[1]] : null; }, ids[n]);
    if (!got) throw new Error(`the page has no canvas with id "p${ids[n]}" (panel ${ids[n]} of ${panels})`);
    sizes.push([got[0], got[1]]);
    writeFileSync(targets[n], Buffer.from(got[2], "base64"));
  }
  const sheet = await page.evaluate(() => window.makeSheet().split(",")[1]);
  writeFileSync(sheetPath, Buffer.from(sheet, "base64"));
  console.log(JSON.stringify({ written: [...targets, sheetPath], panels, sizes, page_errors: errors.slice(0, 10) }));
} finally {
  await browser.close();
}
