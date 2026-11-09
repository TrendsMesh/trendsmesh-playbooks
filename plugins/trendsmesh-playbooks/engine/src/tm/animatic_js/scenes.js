// PB2 animatic scene library. Each scene draws one beat on the 1080 x 1080 stage.
// Signature: (K, p, t, h, params) where K = scene components from engine.js, p = beat progress 0..1,
// t = time in s, h = drawing helpers (pen, line, ell, hatch, glow, hand, seg, ease, lerp, ctx), params = beat params.
// The mode (palette) of each scene is in SCENE_MODES; build_animatic.py copies it into the beat.
// Add a scene here when a new kind of shot is needed; name it by what the viewer sees.
window.SCENE_MODES = {
  bed_writing: 'lamp', notebook_closeup: 'lamp', lie_whisper: 'night', phone_alarm: 'night', morning_talk: 'day',
  product_phone: 'card', desk_sticky_write: 'lamp', sticky_to_phone: 'lamp', phone_dark_wake: 'night', finger_tap: 'night',
  proof_card: 'card', selfie_talk: 'night', backcam_notebook: 'night', back_to_sleep: 'night', morning_then_product: 'day',
};
window.SCENES = {
  // creator in bed at night, lamp on, writing in a notebook
  bed_writing(K, p, t) {
    K.lamp(930, 640, true); K.nightstand(830, 640); K.room({ window: 'moon' });
    K.bed(60, 600, 720); K.pillow(110, 540);
    K.personSit(330, 330, { t });
    K.duvet(100, 600, 700, 30);
    const n = K.notebook(250, 470, 260, 150, 0.15 + p * 0.5, 4);
    K.penHand(n.penX, n.penY + 10);
  },
  // notebook close-up being written; params.lights_off darkens the end of the beat
  notebook_closeup(K, p, t, h, prm) {
    h.glow(540, 300, 700, 'rgba(255,196,120,A)', 0.4);
    const n = K.notebook(140, 240, 800, 560, h.seg(p, 0, 0.75), 6);
    if (p < 0.78 || !prm.lights_off) K.penHand(n.penX, n.penY + 14);
    if (prm.lights_off && p > 0.78) { const k = h.seg(p, 0.78, 1); h.ctx.fillStyle = `rgba(10,12,20,${0.75 * k})`; h.ctx.fillRect(-200, -200, 1480, 1480); h.hand('click', 900, 120, 40, `rgba(255,255,255,${k})`); }
  },
  // lying in bed, eyes closed, whispering a sentence
  lie_whisper(K, p, t) {
    K.room({ window: 'moon' }); K.bed(60, 600, 720); K.pillow(110, 540);
    K.personLie(250, 500, { eyesClosed: true, talk: p > 0.2 && p < 0.85, t });
    K.duvet(100, 600, 700, 10);
  },
  // phone alarm lights the face; sits up, then lies back; params.time
  phone_alarm(K, p, t, h, prm) {
    K.room({ window: 'moon' }); K.nightstand(830, 640); K.bed(60, 600, 720); K.pillow(110, 540);
    const lit = p < 0.75;
    K.phone(880, 520, 110, 200, { lit, screen: lit ? (x, y, w, hh) => K.alarmScreen(x, y, w, hh, prm.time || '4:30') : null });
    const up = p > 0.15 && p < 0.6;
    if (up) K.personSit(330, 330, { t }); else K.personLie(250, 500, { eyesClosed: p >= 0.6, t });
    K.duvet(100, 600, 700, up ? 30 : 10);
  },
  // morning daylight, sitting up with a notebook, talking to camera
  morning_talk(K, p, t) {
    K.room({ window: 'sun' }); K.bed(60, 600, 720); K.pillow(110, 540);
    K.personSit(330, 330, { t, talk: true });
    K.duvet(100, 600, 700, 30);
    K.notebook(420, 430, 230, 140, 1, 4);
  },
  // the book and its night-by-night schedule on a phone; params.highlight (0-6) or params.cycle
  product_phone(K, p, t, h, prm) {
    const hi = prm.cycle ? Math.min(6, Math.floor(p * 9)) : (prm.highlight ?? -1);
    K.phone(330, 160, 420, 820, { screen: (x, y, w, hh) => K.bookScreen(x, y, w, hh, hi) });
  },
  // top-down: a hand writing a sticky note; params.note
  desk_sticky_write(K, p, t, h, prm) {
    K.deskTop(); h.glow(540, 300, 700, 'rgba(255,196,120,A)', 0.35);
    K.sticky(300, 380, 420, prm.note || '', 0.15 + p * 0.45);
    K.penHand(420 + p * 160, 560 + Math.sin(t * 20) * 6);
  },
  // the finished note moves onto a phone; params.note
  sticky_to_phone(K, p, t, h, prm) {
    K.deskTop(); h.glow(540, 300, 700, 'rgba(255,196,120,A)', 0.35);
    K.phone(380, 420, 320, 560, {});
    const k = h.ease(h.seg(p, 0.2, 0.8));
    K.sticky(h.lerp(120, 410, k), h.lerp(120, 520, k), h.lerp(420, 260, k), prm.note || '', 1, h.lerp(-0.04, 0.03, k));
  },
  // phone with the note in the dark; the screen wakes; params.note, params.time
  phone_dark_wake(K, p, t, h, prm) {
    K.deskTop();
    K.phone(380, 420, 320, 560, { lit: p > 0.3, screen: p > 0.3 ? (x, y, w, hh) => K.alarmScreen(x, y, w, hh, prm.time || '4:51') : null });
    K.sticky(410, 520, 260, prm.note || '', 1, 0.03);
  },
  // a finger taps the note on the phone; params.note
  finger_tap(K, p, t, h, prm) {
    K.deskTop();
    K.phone(380, 420, 320, 560, {});
    K.sticky(410, 520, 260, prm.note || '', 1, 0.03);
    const tap = Math.abs(Math.sin(p * Math.PI * 2)) * 30;
    h.pen(5); h.line(700, 1000, 560, 700 + tap, 2); h.ell(720, 1040, 70, 50, 3);
  },
  // a plain proof card frame (the lines come from the beat texts)
  proof_card(K, p, t, h) { h.pen(3); h.rect(120, 120, 840, 840, 3); },
  // front-camera selfie at night; params.clock, params.eyes_closed
  selfie_talk(K, p, t, h, prm) {
    K.selfieFace(540, 600, { talk: prm.eyes_closed ? (p > 0.15 && p < 0.8) : true, eyesClosed: !!prm.eyes_closed, t });
    if (prm.clock) K.clock(830, 900, prm.clock);
  },
  // back camera: notebook on the duvet, writing by phone light
  backcam_notebook(K, p, t, h) {
    h.glow(540, 520, 620, 'rgba(160,190,255,A)', 0.45);
    h.pen(3); h.hatch(0, 760, 1080, 320, 26);
    const n = K.notebook(180, 360, 720, 420, 0.05 + h.seg(p, 0.1, 0.8) * 0.2, 5);
    K.penHand(n.penX, n.penY + 14);
  },
  // phone face down, back to sleep, fade to black
  back_to_sleep(K, p, t, h) {
    K.room({ window: 'moon' }); K.bed(60, 600, 720); K.pillow(110, 540);
    K.personLie(250, 500, { eyesClosed: true, t }); K.duvet(100, 600, 700, 10);
    K.nightstand(830, 640); K.phone(860, 600, 150, 36, {});
    const k = h.seg(p, 0.55, 1); h.ctx.fillStyle = `rgba(0,0,0,${0.85 * k})`; h.ctx.fillRect(-200, -200, 1480, 1480);
  },
  // morning notebook, then the book on a phone; params.highlight
  morning_then_product(K, p, t, h, prm) {
    if (p < 0.42) { K.room({ window: 'sun' }); K.notebook(200, 360, 680, 400, 0.4, 5); }
    else K.phone(330, 160, 420, 820, { screen: (x, y, w, hh) => K.bookScreen(x, y, w, hh, prm.highlight ?? -1) });
  },
};
