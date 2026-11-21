// The hook check of `tm brief animatic` (issue #139): draws each beat of an animatic with a canvas that only
// measures (no browser), and prints what a hook must keep clear of and where each hook would sit.
// Usage: node probe.js <scenes.js> <anim.js> <engine.js> <9x16|4x5>
// Prints one JSON line: {"beats": [{"marks": [{kind, box}], "texts": [{index, boxes: {top|center|bottom:
// [[size, [x, y, w, h]], ...]}}]}]}: the marks of the beat at 5 moments (K.mark: faces, screens, the brand's name), and
// each hook text's box at each place, at its size and each smaller one (x 0.85 a step, never under 32). A letter is
// measured as 0.6 of the size (the hooks' heavy sans), a little wider than it is drawn, so a box is never too small.
const fs = require('fs'), vm = require('vm');
const [scenes, anim, engine, fmt] = process.argv.slice(2);
const ctx = new Proxy({}, {
  get(o, k) {
    if (k in o) return o[k];
    if (k === 'measureText') return (s) => {
      const m = /(\d+(?:\.\d+)?)px/.exec(o.font || ''); return { width: String(s).length * 0.6 * (m ? +m[1] : 10) };
    };
    if (k === 'createRadialGradient' || k === 'createLinearGradient') return () => ({ addColorStop() {} });
    return () => {};
  },
  set(o, k, v) { o[k] = v; return true; },
});
class Picture { set src(v) { this.s = v; this.naturalWidth = 40; this.naturalHeight = 20; } get src() { return this.s; } decode() { return Promise.resolve(); } }
let onload = null;
const window = { FMT: fmt, addEventListener: (e, f) => { if (e === 'load') onload = f; } };
const document = { createElement: () => ({ style: {}, getContext: () => ctx }), body: { style: {}, appendChild() {} } };
const box = vm.createContext({ window, document, navigator: { webdriver: true }, Image: Picture, performance: { now: () => 0 } });
for (const f of [scenes, anim, engine]) vm.runInContext(fs.readFileSync(f, 'utf8'), box);
(async () => {
  await onload();
  const A = window.ANIMATIC;
  const sizes = (s) => { const out = [s]; while (out[out.length - 1] > 32) out.push(Math.max(32, Math.round(out[out.length - 1] * 0.85))); return out; };
  const beats = window.ANIM.beats.map((b) => {
    const marks = [];
    for (const p of [0.02, 0.25, 0.5, 0.75, 0.98]) marks.push(...A.marks(b.t0 + p * (b.t1 - b.t0)));
    const texts = (b.texts || []).map((o, index) => ({ o, index })).filter(({ o }) => A.places.includes(o.style))
      .map(({ o, index }) => ({ index, boxes: Object.fromEntries(A.places.map((place) => [place,
        sizes(o.size || 66).map((size) => [size, A.hookBox({ ...o, style: place, size })])])) }));
    return { marks, texts };
  });
  console.log(JSON.stringify({ beats }));
})().catch((e) => { console.error(String(e && e.stack || e)); process.exit(1); });
