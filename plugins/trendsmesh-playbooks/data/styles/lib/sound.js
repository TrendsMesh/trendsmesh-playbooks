/* sound.js - synthesized sound effects for TrendsMesh style pages. window.SOUND
 *
 * No audio files: every sound is built from oscillators, noise and filters with Web Audio, so the same score
 * renders the same samples every time (offline, for the MP4) and plays live in the page's player.
 *
 * A style writes a score, a function that receives a scheduler `k`:
 *
 *   score(k) {
 *     k.bed("pad", 0, k.duration, { gain: 0.6 });        // a soft bed under everything (left out with voiceover)
 *     k.at(0.4, "whoosh", { dur: 0.8, pan: -0.3 });       // an effect at 0.4 s
 *     k.at(1.2, "pluck", { note: "E4" });                 // tonal effects take a note
 *     k.chord(5.0, ["A3", "C4", "E4"], { voice: "keys" });
 *     k.repeat(6.0, 0.09, 8, "type", { vary: 2 });        // 8 keystrokes, 0.09 s apart, pitch varied +-2 semitones
 *   }
 *
 * Common options on every effect: gain (linear, 1 = the effect's normal level), pitch (semitones, +12 = an octave
 * up), pan (-1 left .. 1 right), verb (reverb send 0..1), dur (seconds, for effects that have a length).
 * With { voiceover: true } every effect plays about 8 dB quieter and beds are left out, so a narration sits on top.
 *
 * SOUND.renderOffline(score, duration, sampleRate, { voiceover }) -> Promise<{ inter, peak, buffer }>
 * SOUND.play(score, from, duration, { voiceover }) -> { stop(), time() }   (live, for the player)
 * SOUND.define(name, fn, { bed, verb })  adds an effect; fn(v, o) builds it (see "voice helpers" below).
 * SOUND.names() lists effects; SOUND.note("A4") -> 440; SOUND.scale("A3", "minorPent", 8) -> MIDI numbers.
 */
(function () {
  "use strict";
  const S = {};
  const effects = {};
  const VOICEOVER_GAIN = Math.pow(10, -8 / 20); // -8 dB

  // ------------------------------------------------------------------ small utilities
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hash(str) {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }
  const NOTE_INDEX = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  /** Note name ("A4", "C#3", "Eb5") or MIDI number -> Hz. */
  S.note = function (n) {
    if (typeof n === "number") return 440 * Math.pow(2, (n - 69) / 12);
    const m = /^([A-Ga-g])([#b]?)(-?\d)$/.exec(String(n).trim());
    if (!m) return 440;
    let semi = NOTE_INDEX[m[1].toUpperCase()] + (m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0);
    const midi = 12 * (parseInt(m[3], 10) + 1) + semi;
    return 440 * Math.pow(2, (midi - 69) / 12);
  };
  /** Note name -> MIDI number. */
  S.midi = (n) => (typeof n === "number" ? n : Math.round(69 + 12 * Math.log2(S.note(n) / 440)));
  const MODES = {
    major: [0, 2, 4, 5, 7, 9, 11],
    minor: [0, 2, 3, 5, 7, 8, 10],
    dorian: [0, 2, 3, 5, 7, 9, 10],
    phrygian: [0, 1, 3, 5, 7, 8, 10],
    lydian: [0, 2, 4, 6, 7, 9, 11],
    mixolydian: [0, 2, 4, 5, 7, 9, 10],
    harmonicMinor: [0, 2, 3, 5, 7, 8, 11],
    pent: [0, 2, 4, 7, 9],
    minorPent: [0, 3, 5, 7, 10],
    blues: [0, 3, 5, 6, 7, 10],
    whole: [0, 2, 4, 6, 8, 10],
  };
  /** count ascending MIDI notes of a scale from root, e.g. SOUND.scale("A3", "minorPent", 8). Modes: see MODES. */
  S.scale = function (root, mode = "minor", count = 8) {
    const r = S.midi(root), steps = MODES[mode] || MODES.minor, out = [];
    for (let i = 0; i < count; i++) out.push(r + steps[i % steps.length] + 12 * Math.floor(i / steps.length));
    return out;
  };
  S.modes = () => Object.keys(MODES);

  // ------------------------------------------------------------------ voice helpers (used inside effect definitions)
  // Every effect fn(v, o) gets a voice v:
  //   v.ac (AudioContext), v.out (connect here), v.t (start time, context seconds), v.rate (pitch ratio),
  //   v.rng() (seeded random for this event), v.dur (o.dur or undefined), v.hz(note) (note -> Hz with pitch applied)
  //   v.tone({...}), v.noise({...}), v.grains({...}), v.sub(name, offset, opts), v.lfo(param, rate, depth, type)
  //
  // Envelope options shared by tone/noise: at (offset s), a (attack s), hold (s), len (decay/release s),
  //   peak (gain), shape "exp" | "lin". Frequency: f, plus f2 + glide (s) for a sweep, or fpath [[offset, Hz], ...].

  function envelope(param, t0, a, hold, len, peak, shape) {
    peak = Math.max(0.0002, peak);
    param.setValueAtTime(0.0001, t0);
    param.linearRampToValueAtTime(peak, t0 + a);
    if (hold > 0) param.setValueAtTime(peak, t0 + a + hold);
    if (shape === "lin") param.linearRampToValueAtTime(0.0001, t0 + a + hold + len);
    else param.exponentialRampToValueAtTime(0.0001, t0 + a + hold + len);
    return t0 + a + hold + len;
  }
  function sweep(param, v, t0, o, scale) {
    const ny = v.ac.sampleRate * 0.45;
    const fz = (hz) => Math.min(ny, Math.max(10, hz * scale));
    param.setValueAtTime(fz(o.f), t0);
    if (o.fpath) for (const [dt, hz] of o.fpath) param.exponentialRampToValueAtTime(fz(hz), t0 + Math.max(0.001, dt));
    else if (o.f2) param.exponentialRampToValueAtTime(fz(o.f2), t0 + (o.glide ?? (o.a ?? 0.004) + (o.hold ?? 0) + (o.len ?? 0.3)));
  }
  function makeVoice(ac, out, t, o, eventSeed, noiseBufs) {
    const v = { ac, out, t, rate: Math.pow(2, (o.pitch ?? 0) / 12), dur: o.dur, rng: rng(eventSeed), noiseBufs };
    v.hz = (n) => S.note(n) * v.rate;
    v.tone = function (p) {
      const t0 = v.t + (p.at ?? 0), a = p.a ?? 0.004, hold = p.hold ?? 0, len = p.len ?? 0.3;
      const osc = ac.createOscillator();
      osc.type = p.type || "sine";
      sweep(osc.frequency, v, t0, p, p.noPitch ? 1 : v.rate);
      if (p.detune) osc.detune.value = p.detune;
      const g = ac.createGain();
      const end = envelope(g.gain, t0, a, hold, len, p.peak ?? 0.3, p.shape);
      osc.connect(g);
      g.connect(p.dest || v.out);
      osc.start(t0);
      osc.stop(end + 0.05);
      return { osc, gain: g, end };
    };
    v.noise = function (p) {
      const t0 = v.t + (p.at ?? 0), a = p.a ?? 0.004, hold = p.hold ?? 0, len = p.len ?? 0.3;
      const src = ac.createBufferSource();
      src.buffer = p.brown ? noiseBufs.brown : noiseBufs.white;
      src.loop = true;
      let node = src, filter = null;
      if (p.filter) {
        filter = ac.createBiquadFilter();
        filter.type = p.filter;
        sweep(filter.frequency, v, t0, p, v.rate);
        filter.Q.value = p.q ?? 1;
        src.connect(filter);
        node = filter;
      }
      const g = ac.createGain();
      const end = envelope(g.gain, t0, a, hold, len, p.peak ?? 0.3, p.shape);
      node.connect(g);
      g.connect(p.dest || v.out);
      src.start(t0, v.rng() * 2.5);
      src.stop(end + 0.05);
      return { src, gain: g, filter, end };
    };
    /** Many tiny noise bursts over a span: paper, pencil, rain, crackle. p: { at, span, count, len, peak, filter, f, q, vary } */
    v.grains = function (p) {
      const n = Math.max(1, Math.round(p.count ?? 12));
      for (let i = 0; i < n; i++) {
        const at = (p.at ?? 0) + v.rng() * (p.span ?? 0.4);
        const f = p.f ? p.f * (1 + (v.rng() - 0.5) * (p.vary ?? 0.5)) : undefined;
        v.noise({ at, a: 0.0008, len: (p.len ?? 0.015) * (0.5 + v.rng()), peak: (p.peak ?? 0.2) * (0.3 + 0.7 * v.rng()), filter: p.filter, f, q: p.q, brown: p.brown });
      }
    };
    /** Play another effect from inside this one, offset seconds later, inheriting pitch/pan routing. */
    v.sub = function (name, offset, opts = {}) {
      const eff = effects[name];
      if (!eff) return;
      const sv = makeVoice(ac, v.out, v.t + offset, { pitch: opts.pitch ?? 0, dur: opts.dur }, (eventSeed ^ hash(name + offset)) >>> 0, noiseBufs);
      sv.rate *= v.rate;
      eff.fn(sv, opts);
    };
    /** Slow modulation of an AudioParam: rate (Hz), depth (in the param's units). Runs until stop time. */
    v.lfo = function (param, rate, depth, stopAt, type = "sine") {
      const o2 = ac.createOscillator(), g = ac.createGain();
      o2.type = type;
      o2.frequency.value = rate;
      g.gain.value = depth;
      o2.connect(g);
      g.connect(param);
      o2.start(v.t);
      o2.stop(stopAt);
      return o2;
    };
    /** Sustained gain node with a slow fade in and out, for beds: everything connected to it follows the swell. */
    v.bedGain = function (dur, peak, fade) {
      const g = ac.createGain(), f = Math.min(fade ?? 1.5, dur / 3);
      g.gain.setValueAtTime(0.0001, v.t);
      g.gain.linearRampToValueAtTime(peak, v.t + f);
      g.gain.setValueAtTime(peak, v.t + dur - f);
      g.gain.linearRampToValueAtTime(0.0001, v.t + dur);
      g.connect(v.out);
      return g;
    };
    return v;
  }

  /** Register an effect. meta: { bed: true for beds (left out with voiceover), verb: default reverb send }. */
  S.define = function (name, fn, meta = {}) {
    effects[name] = { fn, bed: !!meta.bed, verb: meta.verb ?? 0.12, len: meta.len ?? 1 };
  };
  S.names = () => Object.keys(effects).sort();
  S.isBed = (name) => !!(effects[name] && effects[name].bed);
  const def = S.define;

  // ------------------------------------------------------------------ the effects kit
  // UI and small things
  def("tick", (v) => {
    v.noise({ filter: "highpass", f: 4500, a: 0.0005, len: 0.012, peak: 0.35 });
    v.tone({ f: 2600, a: 0.0005, len: 0.018, peak: 0.12 });
  }, { verb: 0.05 });
  def("click", (v) => {
    v.tone({ type: "triangle", f: 1500, f2: 650, glide: 0.02, a: 0.0008, len: 0.03, peak: 0.4 });
    v.noise({ filter: "bandpass", f: 3200, q: 1.5, a: 0.0005, len: 0.018, peak: 0.25 });
  }, { verb: 0.06 });
  def("pop", (v) => {
    v.tone({ f: 260, f2: 920, glide: 0.045, a: 0.002, len: 0.09, peak: 0.5 });
    v.noise({ filter: "bandpass", f: 1800, q: 2, a: 0.001, len: 0.02, peak: 0.1 });
  }, { verb: 0.15 });
  def("boop", (v) => {
    // rounded, bends upward: sine + a soft octave
    v.tone({ f: 330, f2: 560, glide: 0.12, a: 0.012, len: 0.16, peak: 0.45 });
    v.tone({ type: "triangle", f: 660, f2: 1120, glide: 0.12, a: 0.012, len: 0.1, peak: 0.05 });
  }, { verb: 0.18 });
  def("snap", (v) => v.noise({ filter: "bandpass", f: 2200, q: 1.2, a: 0.0005, len: 0.05, peak: 0.6 }), { verb: 0.2 });
  def("beep", (v, o) => v.tone({ f: o.note ? S.note(o.note) : 1000, a: 0.003, hold: o.dur ?? 0.12, len: 0.03, peak: 0.18, shape: "lin" }), { verb: 0.08 });
  def("success", (v) => {
    v.tone({ f: S.note("C6"), a: 0.004, len: 0.25, peak: 0.22 });
    v.tone({ at: 0.09, f: S.note("G6"), a: 0.004, len: 0.45, peak: 0.22 });
  }, { verb: 0.3 });
  def("error", (v) => {
    v.tone({ type: "square", f: 220, a: 0.004, hold: 0.08, len: 0.05, peak: 0.08, shape: "lin" });
    v.tone({ type: "square", at: 0.13, f: 160, a: 0.004, hold: 0.14, len: 0.06, peak: 0.08, shape: "lin" });
  }, { verb: 0.1 });

  // tonal
  def("pluck", (v, o) => {
    // marimba-like: fundamental + the bar's bright 4th partial that dies fast + a mallet tick
    const f = S.note(o.note ?? "A4");
    v.tone({ f, a: 0.002, len: o.dur ?? 0.7, peak: 0.42 });
    v.tone({ f: f * 4, a: 0.001, len: 0.12, peak: 0.1 });
    v.tone({ f: f * 9.9, a: 0.0005, len: 0.03, peak: 0.03 });
    v.noise({ filter: "bandpass", f: f * 2, q: 3, a: 0.0005, len: 0.02, peak: 0.05 });
  }, { verb: 0.3 });
  def("marimba", (v, o) => effects.pluck.fn(v, o), { verb: 0.3 });
  def("keys", (v, o) => {
    // soft electric-piano note
    const f = S.note(o.note ?? "A4");
    v.tone({ f, a: 0.006, len: o.dur ?? 1.4, peak: 0.22 });
    v.tone({ f: f * 2, a: 0.004, len: 0.5, peak: 0.06 });
    v.tone({ type: "triangle", f: f * 1.003, a: 0.01, len: (o.dur ?? 1.4) * 0.8, peak: 0.05 });
  }, { verb: 0.35 });
  def("chime", (v, o) => {
    // inharmonic bell partials, each with its own decay
    const f = S.note(o.note ?? "E6");
    [[1, 0.26, 2.2], [2.76, 0.1, 1.3], [5.4, 0.05, 0.7], [8.93, 0.025, 0.35]].forEach(([m, pk, len]) => v.tone({ f: f * m, a: 0.002, len: len * (o.dur ?? 1), peak: pk }));
  }, { verb: 0.45 });
  def("bell", (v, o) => {
    const f = S.note(o.note ?? "A4");
    [[1, 0.25, 3.5], [2, 0.08, 2.2], [2.4, 0.09, 2], [3, 0.05, 1.4], [4.2, 0.04, 0.9], [5.4, 0.02, 0.5]].forEach(([m, pk, len]) =>
      v.tone({ f: f * m, a: 0.002, len: len * (o.dur ?? 1), peak: pk, detune: (v.rng() - 0.5) * 6 }));
  }, { verb: 0.5 });
  def("ding", (v, o) => {
    const f = S.note(o.note ?? "A5");
    v.tone({ f, a: 0.002, len: 1.1, peak: 0.3 });
    v.tone({ f: f * 2.01, a: 0.002, len: 0.4, peak: 0.07 });
  }, { verb: 0.4 });
  def("sparkle", (v, o) => {
    // a quick glittering run of high chimes
    const base = S.midi(o.note ?? "E6");
    [0, 4, 7, 12, 16].forEach((st, i) => v.tone({ at: i * 0.045, f: S.note(base + st), a: 0.002, len: 0.5, peak: 0.07 }));
  }, { verb: 0.6 });
  def("chord", (v, o) => {
    // a bright, warm chord stab: triangle + sine per note, soft attack
    const notes = o.notes || ["A4", "C#5", "E5", "A5"];
    notes.forEach((n, i) => {
      const f = S.note(n);
      v.tone({ at: i * (o.strum ?? 0), type: "triangle", f, a: 0.008, len: o.dur ?? 1.6, peak: 0.1 });
      v.tone({ at: i * (o.strum ?? 0), f: f * 2, a: 0.006, len: (o.dur ?? 1.6) * 0.5, peak: 0.04 });
    });
  }, { verb: 0.45 });
  def("gong", (v, o) => {
    const f = S.note(o.note ?? "A2");
    [[1, 0.3, 5], [1.48, 0.12, 4], [2.1, 0.1, 3], [2.9, 0.06, 2], [4.3, 0.04, 1.2]].forEach(([m, pk, len]) => v.tone({ f: f * m, a: 0.01, len, peak: pk, detune: (v.rng() - 0.5) * 10 }));
    v.noise({ filter: "lowpass", f: 900, a: 0.002, len: 0.3, peak: 0.12 });
  }, { verb: 0.5 });
  def("twang", (v, o) => {
    // plucked string: buzzy saw, filter closes quickly
    const f = S.note(o.note ?? "D3");
    const lp = v.ac.createBiquadFilter();
    lp.type = "lowpass";
    lp.Q.value = 2;
    lp.frequency.setValueAtTime(Math.min(v.ac.sampleRate * 0.45, f * 14), v.t);
    lp.frequency.exponentialRampToValueAtTime(f * 1.5, v.t + 0.6);
    lp.connect(v.out);
    v.tone({ type: "sawtooth", f, a: 0.002, len: o.dur ?? 1.1, peak: 0.25, dest: lp });
  }, { verb: 0.3 });
  def("drum", (v) => {
    v.tone({ f: 180, f2: 85, glide: 0.12, a: 0.002, len: 0.32, peak: 0.6 });
    v.noise({ filter: "bandpass", f: 320, q: 1, a: 0.001, len: 0.08, peak: 0.2 });
  }, { verb: 0.25 });

  // air and motion
  def("whoosh", (v, o) => {
    // filtered noise that swells as its band rises, then falls away
    const d = o.dur ?? 0.7;
    v.noise({ filter: "bandpass", q: 0.9, f: 280, fpath: [[d * 0.55, 2600], [d, 900]], a: d * 0.55, len: d * 0.45, peak: 0.45 });
    v.noise({ brown: true, filter: "lowpass", f: 500, a: d * 0.5, len: d * 0.5, peak: 0.2 });
  }, { verb: 0.25 });
  def("swish", (v, o) => {
    const d = o.dur ?? 0.25;
    v.noise({ filter: "highpass", f: 1400, f2: 5000, glide: d, a: d * 0.4, len: d * 0.6, peak: 0.3 });
  }, { verb: 0.15 });
  def("breath", (v, o) => {
    // airy, soft: for camera moves
    const d = o.dur ?? 1.0;
    v.noise({ filter: "lowpass", f: 900, f2: 1500, glide: d, a: d * 0.45, len: d * 0.55, peak: 0.2 });
    v.noise({ filter: "bandpass", f: 1700, q: 0.5, a: d * 0.5, len: d * 0.5, peak: 0.08 });
  }, { verb: 0.3 });
  def("riser", (v, o) => {
    // tension build: noise band and a tone climb together, cut at the top
    const d = o.dur ?? 1.5;
    v.noise({ filter: "highpass", f: 400, f2: 6000, glide: d, a: d, len: 0.08, peak: 0.3 });
    v.tone({ type: "triangle", f: 220, f2: 880, glide: d, a: d, len: 0.06, peak: 0.06 });
  }, { verb: 0.3 });
  def("swell", (v, o) => {
    // reversed-cymbal swell that lands on the time + dur
    const d = o.dur ?? 1.2;
    v.noise({ filter: "highpass", f: 2500, a: d, len: 0.05, peak: 0.28 });
  }, { verb: 0.4 });
  def("fall", (v, o) => v.tone({ f: 900, f2: 110, glide: o.dur ?? 0.5, a: 0.005, len: o.dur ?? 0.5, peak: 0.25 }), { verb: 0.2 });

  // weight
  def("thud", (v) => {
    v.tone({ f: 130, f2: 45, glide: 0.2, a: 0.002, len: 0.28, peak: 0.75 });
    v.noise({ filter: "lowpass", f: 420, a: 0.001, len: 0.06, peak: 0.25 });
  }, { verb: 0.12 });
  def("boom", (v, o) => {
    const d = o.dur ?? 1.4;
    v.tone({ f: 80, f2: 32, glide: d, a: 0.004, len: d, peak: 0.8 });
    v.noise({ brown: true, filter: "lowpass", f: 220, a: 0.004, len: d * 0.75, peak: 0.55 });
  }, { verb: 0.2 });
  def("impact", (v) => {
    effects.thud.fn(v, {});
    v.noise({ filter: "bandpass", f: 1300, q: 0.8, a: 0.001, len: 0.2, peak: 0.35 });
    v.noise({ brown: true, filter: "lowpass", f: 180, a: 0.003, len: 0.7, peak: 0.4 });
  }, { verb: 0.25 });
  def("knock", (v) => {
    v.tone({ type: "triangle", f: 520, f2: 400, glide: 0.05, a: 0.0008, len: 0.07, peak: 0.5 });
    v.noise({ filter: "bandpass", f: 950, q: 4, a: 0.0005, len: 0.04, peak: 0.25 });
  }, { verb: 0.15 });
  def("stamp", (v) => {
    v.tone({ f: 110, f2: 55, glide: 0.1, a: 0.002, len: 0.16, peak: 0.6 });
    v.noise({ filter: "lowpass", f: 900, a: 0.0008, len: 0.08, peak: 0.45 });
  }, { verb: 0.15 });

  // paper, pens, desk
  def("paper", (v, o) => {
    // a sheet sliding: broad band of noise plus little crinkle grains
    const d = o.dur ?? 0.5;
    v.noise({ filter: "bandpass", f: 2000, q: 0.7, f2: 3200, glide: d, a: d * 0.3, len: d * 0.7, peak: 0.22 });
    v.grains({ span: d, count: d * 30, filter: "highpass", f: 3000, len: 0.012, peak: 0.12 });
  }, { verb: 0.15 });
  def("rustle", (v, o) => v.grains({ span: o.dur ?? 0.35, count: 16, filter: "bandpass", f: 2600, q: 0.8, len: 0.02, peak: 0.25 }), { verb: 0.15 });
  def("crumple", (v, o) => v.grains({ span: o.dur ?? 0.6, count: 34, filter: "bandpass", f: 2000, q: 0.6, len: 0.025, peak: 0.35 }), { verb: 0.15 });
  def("flip", (v, o) => {
    // page turn: a quick airy sweep and a slap of paper at the end
    const d = o.dur ?? 0.4;
    v.noise({ filter: "bandpass", f: 900, f2: 3500, glide: d, q: 0.7, a: d * 0.7, len: d * 0.3, peak: 0.25 });
    v.noise({ at: d * 0.85, filter: "highpass", f: 1800, a: 0.001, len: 0.05, peak: 0.25 });
  }, { verb: 0.2 });
  def("marker", (v, o) => {
    // felt-tip squeak: a narrow, wobbling band of noise with a faint rubbery tone
    const d = o.dur ?? 0.35;
    v.noise({ filter: "bandpass", q: 9, f: 2500, fpath: [[d * 0.3, 3100], [d * 0.6, 2400], [d, 2900]], a: 0.02, hold: d * 0.8, len: 0.05, peak: 0.4 });
    v.tone({ type: "triangle", f: 1750, fpath: [[d * 0.3, 2050], [d * 0.6, 1800], [d, 1950]], a: 0.02, hold: d * 0.8, len: 0.04, peak: 0.025 });
  }, { verb: 0.1 });
  def("scribble", (v, o) => {
    const d = o.dur ?? 0.6, n = Math.max(2, Math.round(d * 11));
    for (let i = 0; i < n; i++) v.noise({ at: (i * d) / n, filter: "bandpass", q: 6, f: 2300 + v.rng() * 900, a: 0.01, len: d / n, peak: 0.25 });
  }, { verb: 0.1 });
  def("pencil", (v, o) => {
    // graphite scratch: grainy high noise
    const d = o.dur ?? 0.6;
    v.noise({ filter: "bandpass", f: 5200, q: 1.1, a: 0.03, hold: d * 0.8, len: 0.06, peak: 0.07 });
    v.grains({ span: d, count: d * 55, filter: "highpass", f: 3500, len: 0.008, peak: 0.1 });
  }, { verb: 0.08 });
  def("chalk", (v, o) => {
    const d = o.dur ?? 0.6;
    v.noise({ filter: "bandpass", f: 2600, q: 2, a: 0.02, hold: d * 0.8, len: 0.06, peak: 0.12 });
    v.grains({ span: d, count: d * 45, filter: "bandpass", f: 3200, q: 1.5, len: 0.01, peak: 0.2 });
  }, { verb: 0.15 });
  def("type", (v) => {
    // one keystroke: a bright clack and a low thock
    v.noise({ filter: "bandpass", f: 2600 + v.rng() * 1400, q: 2, a: 0.0005, len: 0.025, peak: 0.32 });
    v.tone({ type: "triangle", f: 170 + v.rng() * 40, a: 0.001, len: 0.035, peak: 0.22 });
  }, { verb: 0.08 });
  def("typing", (v, o) => {
    const d = o.dur ?? 1;
    for (let at = 0; at < d; at += 0.055 + v.rng() * 0.09) v.sub("type", at);
  }, { verb: 0.08 });
  def("shutter", (v) => {
    effects.click.fn(v, {});
    v.noise({ at: 0.012, filter: "bandpass", f: 1500, q: 0.8, a: 0.001, len: 0.05, peak: 0.2 });
    v.sub("click", 0.07, { pitch: -3 });
  }, { verb: 0.1 });
  def("bubble", (v) => {
    const f = 380 + v.rng() * 450;
    v.tone({ f, f2: f * 2.3, glide: 0.06, a: 0.003, len: 0.08, peak: 0.3 });
  }, { verb: 0.4 });
  def("sonar", (v, o) => v.tone({ f: S.note(o.note ?? "G6"), a: 0.004, len: o.dur ?? 1.3, peak: 0.25 }), { verb: 0.7 });

  // 8-bit and digital
  def("blip", (v, o) => v.tone({ type: "square", f: S.note(o.note ?? "A5"), a: 0.001, hold: 0.045, len: 0.03, peak: 0.12, shape: "lin" }), { verb: 0.05 });
  def("coin", (v) => {
    v.tone({ type: "square", f: S.note("B5"), a: 0.001, hold: 0.06, len: 0.01, peak: 0.11, shape: "lin" });
    v.tone({ type: "square", at: 0.07, f: S.note("E6"), a: 0.001, hold: 0.12, len: 0.15, peak: 0.11, shape: "lin" });
  }, { verb: 0.05 });
  def("jump", (v) => v.tone({ type: "square", f: 280, f2: 920, glide: 0.15, a: 0.002, len: 0.18, peak: 0.11, shape: "lin" }), { verb: 0.05 });
  def("powerup", (v, o) => {
    const base = S.midi(o.note ?? "C5");
    [0, 4, 7, 12, 16, 19].forEach((st, i) => v.tone({ type: "square", at: i * 0.055, f: S.note(base + st), a: 0.001, hold: 0.04, len: 0.02, peak: 0.1, shape: "lin" }));
  }, { verb: 0.05 });
  def("crunch8", (v) => v.noise({ filter: "lowpass", f: 2400, f2: 300, glide: 0.35, a: 0.001, len: 0.38, peak: 0.35 }), { verb: 0.05 });
  def("glitch", (v, o) => {
    // stuttering digital fault: random square blips and noise slices
    const d = o.dur ?? 0.3, n = Math.max(3, Math.round(d * 26));
    for (let i = 0; i < n; i++) {
      const at = (i / n) * d;
      if (v.rng() < 0.55) v.tone({ type: "square", at, f: 150 + v.rng() * 2800, a: 0.0005, hold: d / n * 0.7, len: 0.004, peak: 0.08, shape: "lin" });
      else v.noise({ at, filter: "bandpass", f: 500 + v.rng() * 5000, q: 2, a: 0.0005, hold: d / n * 0.6, len: 0.004, peak: 0.22, shape: "lin" });
    }
  }, { verb: 0.05 });
  def("static", (v, o) => {
    const d = o.dur ?? 0.5;
    v.noise({ filter: "highpass", f: 1800, a: 0.01, hold: d, len: 0.05, peak: 0.12 });
    v.grains({ span: d, count: d * 40, filter: "highpass", f: 3000, len: 0.004, peak: 0.25 });
  }, { verb: 0.05 });
  def("zap", (v) => v.tone({ type: "sawtooth", f: 2400, f2: 120, glide: 0.18, a: 0.001, len: 0.2, peak: 0.12 }), { verb: 0.15 });
  def("data", (v, o) => {
    // soft computery chirps: a run of quiet sine blips
    const d = o.dur ?? 0.6, n = Math.max(3, Math.round(d * 18));
    for (let i = 0; i < n; i++) v.tone({ at: (i / n) * d, f: 1200 + Math.floor(v.rng() * 6) * 220, a: 0.001, hold: 0.012, len: 0.01, peak: 0.07, shape: "lin" });
  }, { verb: 0.2 });

  // ------------------------------------------------------------------ beds (left out with voiceover; give dur)
  def("pad", (v, o) => {
    // warm low pad: detuned saws through a slowly breathing low-pass filter
    const d = v.dur ?? 8, notes = o.notes || ["A2", "E3", "A3", "C4"];
    const g = v.bedGain(d, 0.16, o.fade ?? 2);
    const lp = v.ac.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = (o.bright ?? 650) * v.rate;
    lp.Q.value = 0.6;
    lp.connect(g);
    v.lfo(lp.frequency, 0.09, 220, v.t + d + 0.1);
    notes.forEach((n) => {
      for (const det of [-7, 7]) {
        const osc = v.ac.createOscillator();
        osc.type = "sawtooth";
        osc.frequency.value = v.hz(n);
        osc.detune.value = det;
        const og = v.ac.createGain();
        og.gain.value = 0.22 / notes.length;
        osc.connect(og);
        og.connect(lp);
        osc.start(v.t);
        osc.stop(v.t + d + 0.1);
      }
    });
  }, { bed: true, verb: 0.35 });
  def("drone", (v, o) => {
    const d = v.dur ?? 8, f = v.hz(o.note ?? "A1");
    const g = v.bedGain(d, 0.2, o.fade ?? 2);
    [[1, "sine", 0.55], [1.005, "sine", 0.4], [2, "triangle", 0.12], [3.002, "sine", 0.05]].forEach(([m, type, pk]) => {
      const osc = v.ac.createOscillator();
      osc.type = type;
      osc.frequency.value = f * m;
      const og = v.ac.createGain();
      og.gain.value = pk;
      osc.connect(og);
      og.connect(g);
      osc.start(v.t);
      osc.stop(v.t + d + 0.1);
    });
  }, { bed: true, verb: 0.3 });
  /** Looping noise through a filter into a bed swell (shared by several beds). */
  function noiseBed(v, d, o) {
    const g = v.bedGain(d, o.peak, o.fade ?? 1.5);
    const src = v.ac.createBufferSource();
    src.buffer = o.brown ? v.noiseBufs.brown : v.noiseBufs.white;
    src.loop = true;
    const bq = v.ac.createBiquadFilter();
    bq.type = o.filter || "lowpass";
    bq.frequency.value = o.f * v.rate;
    bq.Q.value = o.q ?? 0.7;
    src.connect(bq);
    bq.connect(g);
    if (o.lfoRate) v.lfo(bq.frequency, o.lfoRate, o.lfoDepth ?? o.f * 0.4, v.t + d + 0.1);
    src.start(v.t, v.rng() * 2);
    src.stop(v.t + d + 0.1);
    return { g, bq, src };
  }
  def("wind", (v, o) => noiseBed(v, v.dur ?? 8, { brown: true, filter: "bandpass", f: 420, q: 0.6, peak: 0.5, lfoRate: 0.13, lfoDepth: 200, fade: o.fade }), { bed: true, verb: 0.2 });
  def("room", (v, o) => noiseBed(v, v.dur ?? 8, { brown: true, filter: "lowpass", f: 300, peak: 0.18, fade: o.fade }), { bed: true, verb: 0.1 });
  def("underwater", (v, o) => {
    const d = v.dur ?? 8;
    noiseBed(v, d, { brown: true, filter: "lowpass", f: 260, peak: 0.55, lfoRate: 0.08, lfoDepth: 90, fade: o.fade });
    for (let at = 0.5; at < d - 0.3; at += 0.4 + v.rng() * 1.6) v.sub("bubble", at, { pitch: -5 });
  }, { bed: true, verb: 0.4 });
  def("hum", (v, o) => {
    // electrical hum of machines and screens
    const d = v.dur ?? 8, g = v.bedGain(d, 0.12, o.fade ?? 1);
    [[50, 0.5], [100, 0.3], [150, 0.12], [200, 0.06]].forEach(([f, pk]) => {
      const osc = v.ac.createOscillator();
      osc.frequency.value = f * v.rate;
      const og = v.ac.createGain();
      og.gain.value = pk;
      osc.connect(og);
      og.connect(g);
      osc.start(v.t);
      osc.stop(v.t + d + 0.1);
    });
    noiseBed(v, d, { filter: "bandpass", f: 3000, q: 0.5, peak: 0.015, fade: o.fade });
  }, { bed: true, verb: 0.05 });
  def("crackle", (v, o) => {
    // vinyl / old film crackle: faint hiss with sparse pops
    const d = v.dur ?? 8;
    noiseBed(v, d, { filter: "highpass", f: 4000, peak: 0.02, fade: o.fade ?? 0.5 });
    for (let at = 0; at < d; at += 0.03 + v.rng() * 0.25) v.noise({ at, filter: "highpass", f: 1500 + v.rng() * 3000, a: 0.0003, len: 0.004 + v.rng() * 0.006, peak: 0.05 + v.rng() * 0.2 });
  }, { bed: true, verb: 0.02 });
  def("projector", (v, o) => {
    // film projector clatter: noise chopped at 24 Hz, plus motor hum
    const d = v.dur ?? 8;
    const { g } = noiseBed(v, d, { filter: "bandpass", f: 1600, q: 0.8, peak: 0.08, fade: o.fade ?? 0.6 });
    const chop = v.ac.createGain();
    g.disconnect();
    g.connect(chop);
    chop.connect(v.out);
    chop.gain.value = 0.5;
    v.lfo(chop.gain, 24, 0.5, v.t + d + 0.1, "square");
    const hum = v.ac.createOscillator();
    hum.frequency.value = 60 * v.rate;
    const hg = v.bedGain(d, 0.03, o.fade ?? 0.6);
    hum.connect(hg);
    hum.start(v.t);
    hum.stop(v.t + d + 0.1);
  }, { bed: true, verb: 0.1 });
  def("rain", (v, o) => {
    const d = v.dur ?? 8;
    noiseBed(v, d, { filter: "bandpass", f: 3500, q: 0.4, peak: 0.12, fade: o.fade });
    v.grains({ span: d, count: d * 22, filter: "highpass", f: 2500, len: 0.01, peak: 0.12 });
  }, { bed: true, verb: 0.25 });
  def("pulse", (v, o) => {
    // a soft heartbeat-like groove: low thumps on every beat
    const d = v.dur ?? 8, step = 60 / (o.bpm ?? 90);
    for (let at = 0.3; at < d - 0.2; at += step) v.tone({ at, f: 95, f2: 45, glide: 0.18, a: 0.004, len: 0.22, peak: 0.3 * Math.min(1, at / 1.5, (d - at) / 1.5) });
  }, { bed: true, verb: 0.1 });
  def("arp", (v, o) => {
    // a quiet arpeggio of plucks over a scale: light music bed
    const d = v.dur ?? 8, step = o.step ?? 0.25, notes = o.notes || S.scale("A3", "minorPent", 8);
    const order = o.pattern || [0, 2, 4, 2, 5, 3, 4, 1];
    let i = 0;
    for (let at = 0.2; at < d - 0.3; at += step, i++) {
      const env = Math.min(1, at / 1.5, (d - at) / 1.5);
      const f = S.note(notes[order[i % order.length] % notes.length]);
      v.tone({ at, f, a: 0.002, len: 0.35, peak: 0.07 * env });
      v.tone({ at, f: f * 4, a: 0.001, len: 0.06, peak: 0.015 * env });
    }
  }, { bed: true, verb: 0.45 });

  // ------------------------------------------------------------------ scheduler (records a score)
  function record(score, duration, opts = {}) {
    const events = [];
    const kr = rng(hash("score"));
    const push = (time, name, o, fn) => {
      time = Math.max(0, +time || 0);
      if (time >= duration) return;
      events.push({ time, name, o: o || {}, fn, i: events.length });
    };
    const k = {
      duration,
      voiceover: !!opts.voiceover,
      /** Seeded random for humanising a score (same every render). */
      rng: () => kr(),
      /** Play effect `name` at `time` seconds. */
      at(time, name, o = {}) {
        if (!effects[name]) console.warn("SOUND: no effect named " + name);
        else push(time, name, o);
        return k;
      },
      /** A bed from start to end seconds (default: to the end). Beds are left out in voiceover mode. */
      bed(name, start = 0, end = duration, o = {}) {
        return k.at(start, name, { ...o, dur: Math.max(0.1, Math.min(end, duration) - start) });
      },
      /** Notes together (or strummed with o.strum seconds apart), played on o.voice (default "keys"). */
      chord(time, notes, o = {}) {
        notes.forEach((n, i) => k.at(time + i * (o.strum ?? 0), o.voice || "keys", { ...o, note: n }));
        return k;
      },
      /** A melody: notes (names, MIDI numbers, or null for a rest) every `step` seconds on o.voice (default "pluck"). */
      seq(time, step, notes, o = {}) {
        notes.forEach((n, i) => n != null && k.at(time + i * step, o.voice || "pluck", { ...o, note: n }));
        return k;
      },
      /** The same effect count times, step seconds apart; o.jitter (s) and o.vary (semitones) humanise it. */
      repeat(time, step, count, name, o = {}) {
        for (let i = 0; i < count; i++) {
          const j = o.jitter ? (kr() - 0.5) * 2 * o.jitter : 0;
          const p = (o.pitch ?? 0) + (o.vary ? (kr() - 0.5) * 2 * o.vary : 0);
          k.at(time + i * step + j, name, { ...o, pitch: p });
        }
        return k;
      },
      /** A one-off sound built by hand: fn(v, o) with the voice helpers (see SOUND.define). o.bed marks it a bed. */
      custom(time, fn, o = {}) {
        push(time, null, o, fn);
        return k;
      },
    };
    score(k);
    events.sort((a, b) => a.time - b.time || a.i - b.i);
    return events;
  }
  S.events = (score, duration, opts) => record(score, duration, opts).map((e) => ({ time: e.time, name: e.name || "custom", ...e.o }));

  // ------------------------------------------------------------------ rendering a recorded score into a context
  function noiseBuffers(ac) {
    const n = Math.round(ac.sampleRate * 3), r = rng(12345);
    const white = ac.createBuffer(1, n, ac.sampleRate), brown = ac.createBuffer(1, n, ac.sampleRate);
    const w = white.getChannelData(0), b = brown.getChannelData(0);
    let last = 0;
    for (let i = 0; i < n; i++) {
      w[i] = r() * 2 - 1;
      last = (last + 0.02 * w[i]) / 1.02;
      b[i] = last * 3.5;
    }
    return { white, brown };
  }
  function impulse(ac, seconds = 1.8) {
    const n = Math.round(ac.sampleRate * seconds), buf = ac.createBuffer(2, n, ac.sampleRate), r = rng(777);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch);
      let lp = 0;
      for (let i = 0; i < n; i++) {
        const x = r() * 2 - 1;
        lp += (x - lp) * 0.35; // darker tail
        d[i] = lp * Math.pow(1 - i / n, 3.2) * (i < ac.sampleRate * 0.01 ? i / (ac.sampleRate * 0.01) : 1);
      }
    }
    return buf;
  }
  function realize(ac, dest, events, o) {
    const from = o.from ?? 0, start = o.start ?? 0, vo = !!o.voiceover;
    const comp = ac.createDynamicsCompressor();
    comp.threshold.value = -12;
    comp.knee.value = 10;
    comp.ratio.value = 3;
    comp.attack.value = 0.004;
    comp.release.value = 0.25;
    const master = ac.createGain();
    master.gain.value = (vo ? VOICEOVER_GAIN : 1) * 0.9;
    comp.connect(master);
    master.connect(dest);
    const verb = ac.createConvolver();
    verb.buffer = impulse(ac);
    const verbIn = ac.createGain();
    verbIn.gain.value = 0.55;
    verbIn.connect(verb);
    verb.connect(comp);
    const bufs = noiseBuffers(ac);
    for (const ev of events) {
      const eff = ev.name ? effects[ev.name] : { fn: ev.fn, bed: !!ev.o.bed, verb: 0.12 };
      if (vo && eff.bed) continue;
      const len = ev.o.dur ?? (eff.bed ? 8 : 2);
      if (ev.time < from - 0.02 && !(eff.bed && ev.time + len > from + 0.2)) continue;
      const when = start + (ev.time - from);
      const input = ac.createGain();
      input.gain.value = ev.o.gain ?? 1;
      const pan = ac.createStereoPanner();
      pan.pan.value = Math.max(-1, Math.min(1, ev.o.pan ?? 0));
      input.connect(pan);
      pan.connect(comp);
      const send = ac.createGain();
      send.gain.value = ev.o.verb ?? eff.verb;
      pan.connect(send);
      send.connect(verbIn);
      const v = makeVoice(ac, input, when, ev.o, hash((ev.name || "custom") + ":" + ev.time.toFixed(4) + ":" + ev.i), bufs);
      try {
        eff.fn(v, ev.o);
      } catch (err) {
        console.warn("SOUND: effect " + (ev.name || "custom") + " failed: " + err.message);
      }
    }
  }

  /**
   * Render a score offline. Resolves to { inter (Float32Array L,R,L,R...), peak (max |sample|), buffer (AudioBuffer) }.
   */
  S.renderOffline = async function (score, duration, sampleRate = 48000, opts = {}) {
    const len = Math.max(1, Math.ceil(duration * sampleRate));
    const ac = new OfflineAudioContext(2, len, sampleRate);
    realize(ac, ac.destination, record(score, duration, opts), { from: 0, start: 0, voiceover: opts.voiceover });
    const buf = await ac.startRendering();
    const L = buf.getChannelData(0), R = buf.getChannelData(1), inter = new Float32Array(len * 2);
    let peak = 0;
    for (let i = 0; i < len; i++) {
      inter[2 * i] = L[i];
      inter[2 * i + 1] = R[i];
      const m = Math.max(Math.abs(L[i]), Math.abs(R[i]));
      if (m > peak) peak = m;
    }
    return { inter, peak, buffer: buf };
  };

  /**
   * Live playback from `from` seconds (for the player). Returns { stop(), time() }: time() is the score time now,
   * by the audio clock, so the picture can follow the sound.
   */
  S.play = function (score, from = 0, duration = 10, opts = {}) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return { stop() {}, time: () => null };
    const ac = new AC();
    const start = ac.currentTime + 0.08;
    realize(ac, ac.destination, record(score, duration, opts), { from, start, voiceover: opts.voiceover });
    if (ac.state === "suspended") ac.resume();
    let stopped = false;
    return {
      ctx: ac,
      time: () => (stopped ? null : from + Math.max(0, ac.currentTime - start)),
      stop() {
        if (stopped) return;
        stopped = true;
        ac.close().catch(() => {});
      },
    };
  };

  window.SOUND = S;
})();
