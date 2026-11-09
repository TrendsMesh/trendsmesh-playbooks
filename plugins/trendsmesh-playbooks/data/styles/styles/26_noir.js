/* 26 Noir - reference animation.
 * Topic (setting, replace it): "The case of the locked safe" - how a combination lock's wheel pack opens.
 * Rendering (keep it): a monochrome forties crime picture. Every scene is painted twice, in deep shadow and fully lit;
 * the lit copy shows only through swaying window-blind bars, with haze in the beams. Half-lit forms with bright rims;
 * glowing condensed-caps titles; typed, crooked placards with double borders; white newsreel arrows; a rolling
 * counter; a greyed red stamp that jolts the frame. Film finish: bloom, gate weave, flicker, dirt, vignette, grain.
 * Transitions: iris, a spinning newspaper, a clock sweep, a wipe; slow pushes in with a handheld tremble.
 */
(function () {
  "use strict";
  const B = window.Brush;

  // ---- palette and type (from the card)
  const PAL = { black: "#050505", charcoal: "#1c1c1e", mid: "#6b6b6b", light: "#bdbab2", white: "#f2efe6", stamp: "#8c1c1c" };
  const TITLE = "Oswald", TYPE = "Special Elite";
  const DUR = 13;
  const BEATS = [0, 2.3, 4.9, 7.2, 9.4, 11.2];

  // ---- light and shade helpers (reuse these)
  /** A grey on the black-to-white scale; in shadow the same surface sits far down it. */
  const tone = (k, lit) => (lit ? B.mix(PAL.charcoal, PAL.white, B.clamp(k)) : B.mix(PAL.black, PAL.mid, B.clamp(k) * 0.45));
  /** Fade up out of darkness, brightest parts first: the lit copy arrives before the shadow copy. */
  const fadeUp = (t, at, lit) => (lit ? B.prog(t, at, 0.45, "inQuad") : B.prog(t, at + 0.3, 0.6, "inQuad"));
  /**
   * Window-blind light: soft-edged slanted bars in a patch of light that feathers away (o.soft px) and dims away
   * from the window: light falling on things, never a striped card. o: { region, angle, period, duty, shift, soft }
   */
  function blinds(g, o, t) {
    const a = o.angle + 0.025 * Math.sin(t * 0.45), ca = Math.cos(a), sa = Math.sin(a);
    const bx = o.region.reduce((m, p) => [Math.min(m[0], p[0]), Math.min(m[1], p[1]), Math.max(m[2], p[0]), Math.max(m[3], p[1])], [1e9, 1e9, -1e9, -1e9]);
    const cx = (bx[0] + bx[2]) / 2, cy = (bx[1] + bx[3]) / 2, R = Math.hypot(bx[2] - bx[0], bx[3] - bx[1]);
    g.save();
    g.fillStyle = "#fff";
    g.filter = `blur(${(o.soft * 0.06).toFixed(1)}px)`;
    const shift = (o.shift ?? 0) + Math.sin(t * 0.3) * o.period * 0.06;
    for (let d = -R; d < R; d += o.period) {
      const d0 = d + shift, d1 = d0 + o.period * o.duty;
      g.beginPath();
      g.moveTo(cx - ca * R - sa * d0, cy - sa * R + ca * d0);
      g.lineTo(cx + ca * R - sa * d0, cy + sa * R + ca * d0);
      g.lineTo(cx + ca * R - sa * d1, cy + sa * R + ca * d1);
      g.lineTo(cx - ca * R - sa * d1, cy - sa * R + ca * d1);
      g.fill();
    }
    g.globalCompositeOperation = "destination-in"; // the patch of light, feathered, brightest near the window
    g.filter = `blur(${o.soft.toFixed(1)}px)`;
    g.fillStyle = B.linear(g, bx[0], bx[1], bx[2], bx[3], ["#fff", "rgba(255,255,255,0.8)", "rgba(255,255,255,0.45)"]);
    g.beginPath();
    B.poly(g, o.region, true);
    g.fill();
    g.restore();
  }
  /** Curling haze: a cached cloud texture drifting upward, seen only in the beams. */
  function haze(g, W, H, t) {
    const tile = B.layer("noir-haze", Math.ceil(W / 8), Math.ceil(H / 8), (c, w, h) => {
      const img = c.createImageData(w, h), d = img.data, s = 6 / Math.min(w, h);
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          const v = B.clamp(0.5 + 0.9 * B.fbm(x * s, y * s, 4, 26)), i = (y * w + x) * 4;
          d[i] = d[i + 1] = d[i + 2] = 255;
          d[i + 3] = v * v * 255;
        }
      c.putImageData(img, 0, 0);
    });
    g.imageSmoothingEnabled = true;
    const dy = (t * 0.035 * H) % H, dx = Math.sin(t * 0.2) * W * 0.03;
    for (const k of [0, -1]) g.drawImage(tile, dx - W * 0.05, H + k * H - dy, W * 1.1, H);
  }
  /** Paint a scene: shadow copy, lit copy through the blinds, haze in the beams, then overlays. sc: { cam, paint, beams, overlay, hud } */
  function render(g, sc, t, F) {
    const W = F.W, H = F.H, cam = sc.cam(t, F);
    const inCam = (c, fn) => {
      c.save();
      c.translate(W / 2 + cam.dx, H / 2 + cam.dy);
      c.scale(cam.z, cam.z);
      c.translate(-cam.x, -cam.y);
      fn(c);
      c.restore();
    };
    g.fillStyle = PAL.black;
    g.fillRect(0, 0, W, H);
    inCam(g, (c) => sc.paint(c, false, t, F));
    const M = B.scratch("noir-mask", W, H);
    inCam(M, (c) => blinds(c, { soft: F.u * 6, ...sc.beams(F, t) }, t));
    const Lc = B.scratch("noir-lit", W, H);
    inCam(Lc, (c) => sc.paint(c, true, t, F));
    Lc.globalCompositeOperation = "destination-in";
    Lc.drawImage(M.canvas, 0, 0);
    g.drawImage(Lc.canvas, 0, 0);
    const Hz = B.scratch("noir-hz", W, H);
    haze(Hz, W, H, t);
    Hz.globalCompositeOperation = "destination-in";
    Hz.drawImage(M.canvas, 0, 0);
    g.save();
    g.globalCompositeOperation = "screen";
    g.globalAlpha = 0.28;
    g.drawImage(Hz.canvas, 0, 0);
    g.restore();
    if (sc.overlay) inCam(g, (c) => sc.overlay(c, t, F));
    if (sc.hud) sc.hud(g, t, F); // screen-space cards, outside the camera push
  }
  /** Slow push in with a faint handheld tremble around a focus point. */
  function pushCam(t, F, a, b, fx, fy, z0, z1) {
    const k = B.span(t, a, b, "inOutSine"), [dx, dy] = B.shake(t, 0.25 * F.u, 3, 1.3);
    return { x: fx, y: fy, z: B.lerp(z0, z1, k), dx, dy };
  }
  /** Condensed caps arriving word by word with a flicker and a faint glow. lines: [[words...]] */
  function titleWords(g, lines, x, y, size, t, at, gap, o = {}) {
    g.save();
    g.font = B.font(size, TITLE, 700);
    g.textBaseline = "middle";
    if ("letterSpacing" in g) g.letterSpacing = (size * 0.02).toFixed(1) + "px";
    let n = 0;
    lines.forEach((words, li) => {
      const ly = y + li * size * 1.05, sp = size * 0.22;
      const ws = words.map((w) => g.measureText(w).width), lw = ws.reduce((a, b) => a + b, 0) + sp * (words.length - 1);
      let xx = o.align === "left" ? x : x - lw / 2;
      words.forEach((w, i) => {
        const k = B.prog(t, at + n++ * gap, 0.3), fl = k < 1 ? 0.55 + 0.45 * B.hash01("tw", Math.floor(t * 24), n) : 1;
        if (k > 0) {
          g.globalAlpha = k * fl * (o.alpha ?? 1);
          g.shadowColor = B.rgba(PAL.white, 0.5);
          g.shadowBlur = size * 0.35;
          g.fillStyle = PAL.white;
          g.textAlign = "left";
          g.fillText(w, xx, ly);
        }
        xx += ws[i] + sp;
      });
    });
    g.restore();
  }
  /**
   * Typed placard: off-white card, thin double border, typed text; slides in and rests crooked. p: slide, typed: 0..1.
   * o: { from: -1 | 1, rot, caseNo, extra (blank px under the text, for a stamp) }. Returns { y, h } of the blank.
   */
  function placard(g, x, y, w, text, size, p, typed, o = {}) {
    if (p <= 0) return;
    const m = B.measureText(g, text, { size, family: TYPE, weight: 400, maxW: w - size * 1.6, lineH: 1.2 });
    const ex = o.extra ?? 0, tp = o.caseNo ? size * 0.6 : 0, h = m.height + size * 1.5 + ex + tp, k = B.ease.outCubic(p);
    g.save();
    g.translate(x + (1 - k) * (o.from ?? -1) * w * 1.4, y);
    g.rotate((o.rot ?? -0.03) * k + (1 - k) * 0.2 * (o.from ?? -1));
    B.withShadow(g, { color: "rgba(0,0,0,0.7)", blur: size * 0.8, x: size * 0.2, y: size * 0.35 }, () => {
      g.fillStyle = B.linear(g, -w / 2, -h / 2, w / 2, h / 2, [PAL.white, "#d9d5ca"]);
      g.fillRect(-w / 2, -h / 2, w, h);
    });
    g.strokeStyle = PAL.black;
    g.lineWidth = Math.max(1, size * 0.06);
    g.strokeRect(-w / 2 + size * 0.25, -h / 2 + size * 0.25, w - size * 0.5, h - size * 0.5);
    g.strokeRect(-w / 2 + size * 0.38, -h / 2 + size * 0.38, w - size * 0.76, h - size * 0.76);
    // the stamped case number is texture: nobody needs to read it
    if (o.caseNo) B.texture(g, () => B.text(g, o.caseNo, w / 2 - size * 0.6, -h / 2 + size * 0.75, { size: size * 0.55, family: TYPE, weight: 400, color: B.mix(PAL.stamp, PAL.mid, 0.4), align: "right" }));
    B.text(g, text, 0, (tp - ex) / 2, { size, family: TYPE, weight: 400, color: PAL.black, maxW: w - size * 1.6, lineH: 1.2, reveal: typed });
    g.restore();
    return { y: y + h / 2 - ex / 2, h };
  }
  /** Plain bright newsreel arrow, drawn on with a thin steady line and a small solid head. */
  function reelArrow(g, pts, p, u) {
    B.withShadow(g, { color: B.rgba(PAL.white, 0.6), blur: u * 1.2 }, () => B.arrow(g, pts, { p, width: 0.45 * u, head: 2.6 * u, color: PAL.white, headStyle: "tri" }));
  }
  /** Odometer: digit drums in a metal housing; a drum rolls only while every drum to its right turns over from 9. */
  function odometer(g, x, y, digits, value, h) {
    const cw = h * 0.68, sep = cw * 0.42, ns = Math.floor((digits - 1) / 3), w = cw * digits + sep * ns + h * 0.3;
    g.save();
    g.fillStyle = PAL.charcoal;
    g.fillRect(x - w / 2, y - h * 0.68, w, h * 1.36);
    g.strokeStyle = PAL.light;
    g.lineWidth = h * 0.03;
    g.strokeRect(x - w / 2, y - h * 0.68, w, h * 1.36);
    for (let i = 0; i < digits; i++) {
      const place = Math.pow(10, digits - 1 - i), below = value % place;
      let pos = Math.floor(value / place);
      if (place > 1 && below > place - 1) pos += below - (place - 1);
      else if (place === 1) pos = value;
      // commas between thousands groups
      const gi = Math.floor((digits - 1 - i) / 3), dx = x - w / 2 + h * 0.15 + i * cw + (ns - gi) * sep, f = B.fract(pos), d = Math.floor(pos) % 10;
      if (i && (digits - i) % 3 === 0) {
        g.font = B.font(h * 0.92, TITLE, 600);
        g.fillStyle = PAL.white;
        g.textAlign = "center";
        g.fillText(",", dx - sep / 2, y + h * 0.3);
      }
      g.save();
      g.beginPath();
      g.rect(dx + cw * 0.06, y - h * 0.55, cw * 0.88, h * 1.1);
      g.clip();
      g.fillStyle = B.linear(g, 0, y - h * 0.55, 0, y + h * 0.55, ["#55524c", PAL.white, PAL.white, "#55524c"]);
      g.fillRect(dx, y - h, cw, h * 2);
      g.font = B.font(h * 0.92, TITLE, 600);
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillStyle = PAL.black;
      g.fillText(String(d), dx + cw / 2, y - f * h * 1.1);
      g.fillText(String((d + 1) % 10), dx + cw / 2, y + h * 1.1 - f * h * 1.1);
      g.restore();
    }
    g.restore();
  }

  // ---- subjects (the setting: replace these)
  /** The office safe: box, dial, door seam, handle, a rim of light on its right edge. */
  function safe(g, lit, cx, cy, s, o = {}) {
    const w = s * 1.0, h = s * 1.25, x = cx - w / 2, y = cy - h / 2;
    g.fillStyle = tone(0.42, lit);
    g.fillRect(x, y, w, h);
    g.fillStyle = tone(0.2, lit);
    g.fillRect(x, y + h * 0.95, w, h * 0.05);
    g.fillRect(x + w * 0.06, y + h, w * 0.1, h * 0.05);
    g.fillRect(x + w * 0.84, y + h, w * 0.1, h * 0.05);
    const dw = w * 0.82, dh = h * 0.8, dx = x + w * 0.09, dy = y + h * 0.08;
    const open = o.open ?? 0;
    if (open > 0) {
      g.fillStyle = tone(lit ? 0.95 : 0.1, lit); // the open strongroom catches the beam
      g.fillRect(dx, dy, dw, dh);
      g.fillStyle = tone(0.55, lit);
      g.fillRect(dx + dw * 0.1, dy + dh * 0.45, dw * 0.8, dh * 0.04);
    }
    g.save();
    g.translate(dx, dy);
    g.transform(1 - open * 0.75, -open * 0.12, 0, 1, 0, 0); // the door swings toward the viewer's left
    g.fillStyle = tone(0.5, lit);
    g.fillRect(0, 0, dw, dh);
    g.strokeStyle = tone(0.12, lit);
    g.lineWidth = s * 0.012;
    g.strokeRect(dw * 0.04, dh * 0.04, dw * 0.92, dh * 0.92);
    const dr = dw * 0.17, dcx = dw * 0.5, dcy = dh * 0.42, rot = o.dial ?? 0;
    g.fillStyle = tone(0.75, lit);
    g.beginPath();
    B.circle(g, dcx, dcy, dr);
    g.fill();
    g.strokeStyle = tone(0.2, lit);
    g.lineWidth = s * 0.006;
    for (let i = 0; i < 20; i++) {
      const a = rot + (i / 20) * B.TAU;
      g.beginPath();
      g.moveTo(dcx + Math.cos(a) * dr * 0.78, dcy + Math.sin(a) * dr * 0.78);
      g.lineTo(dcx + Math.cos(a) * dr * 0.95, dcy + Math.sin(a) * dr * 0.95);
      g.stroke();
    }
    g.fillStyle = tone(0.3, lit);
    g.beginPath();
    B.circle(g, dcx, dcy, dr * 0.4);
    g.fill();
    g.fillRect(dw * 0.45, dh * 0.68, dw * 0.1, dh * 0.2);
    g.fillRect(dw * 0.3, dh * 0.76, dw * 0.4, dh * 0.04);
    g.restore();
    if (!lit) {
      // rim light: a thin bright edge from a lamp behind the safe
      g.fillStyle = B.rgba(PAL.light, 0.85);
      g.fillRect(x + w - s * 0.012, y, s * 0.012, h * 0.95);
      g.fillRect(x, y - s * 0.006, w, s * 0.008);
    }
  }
  /** The wall behind: panelled plaster with a dado rail and a skirting board. */
  function wall(g, lit, F, floorY) {
    g.fillStyle = tone(0.38, lit);
    g.fillRect(-F.W, -F.H, F.W * 3, floorY + F.H);
    g.fillStyle = tone(0.3, lit);
    for (let x = -F.W; x < F.W * 2; x += F.u * 14) g.fillRect(x, -F.H, F.u * 0.35, floorY + F.H);
    g.fillStyle = tone(0.5, lit);
    g.fillRect(-F.W, floorY - F.u * 18, F.W * 3, F.u * 0.8);
    g.fillStyle = tone(0.16, lit);
    g.fillRect(-F.W, floorY, F.W * 3, F.H * 2);
  }
  // the wheel pack: three gated wheels on one spindle, the fence riding above
  const WHEEL_OFF = [1.05, -0.5];
  function wheel(g, lit, cx, cy, r, gateA, s) {
    const gw = 0.34, depth = r * 0.2;
    const path = (c) => {
      c.beginPath();
      c.arc(cx, cy, r, gateA + gw / 2, gateA - gw / 2 + B.TAU);
      c.lineTo(cx + Math.cos(gateA - gw / 3) * (r - depth), cy + Math.sin(gateA - gw / 3) * (r - depth));
      c.lineTo(cx + Math.cos(gateA + gw / 3) * (r - depth), cy + Math.sin(gateA + gw / 3) * (r - depth));
      c.closePath();
    };
    // edge thickness toward the back, then the face
    g.save();
    g.translate(WHEEL_OFF[0] * s * 0.25, WHEEL_OFF[1] * s * 0.25);
    path(g);
    g.fillStyle = tone(0.15, lit);
    g.fill();
    g.restore();
    path(g);
    g.fillStyle = B.radial(g, cx - r * 0.3, cy - r * 0.35, r * 0.1, r * 1.2, [tone(1, lit), tone(0.72, lit), tone(0.4, lit)]);
    g.fill();
    g.strokeStyle = tone(0.2, lit);
    g.lineWidth = s * 0.03;
    g.beginPath();
    B.circle(g, cx, cy, r * 0.62);
    g.stroke();
    g.fillStyle = tone(0.12, lit);
    g.beginPath();
    B.circle(g, cx, cy, r * 0.14);
    g.fill();
    // rim light from a lamp behind: a crisp edge on every wheel
    g.strokeStyle = B.rgba(PAL.white, lit ? 1 : 0.9);
    g.lineWidth = s * (lit ? 0.06 : 0.05);
    g.beginPath();
    g.arc(cx, cy, r * 0.99, Math.max(-1.2, gateA + gw / 2), 0.8);
    g.stroke();
  }
  /** Gate angle of wheel i at time t (0 = front wheel, 2 = back). Steps park the back wheel first. */
  function gateAngle(i, t) {
    const top = -Math.PI / 2, start = [top - 0.75, top + 1.7, top + 0.9][i];
    const parks = [8.15, 7.75, 7.4]; // left, right, left: one number parks one wheel
    const k = B.prog(t, parks[i] - 0.05, 0.42, "outBack");
    const idle = t < 7.3 ? Math.sin(t * 0.7 + i) * 0.15 : 0;
    return B.lerp(start + idle, top, k);
  }
  function wheelPack(g, lit, t, c, s) {
    const r = s * 2.1, drop = B.prog(t, 9.6, 0.25, "inQuad") * r * 0.2;
    const bolt = B.prog(t, 9.95, 0.55, "inOutCubic");
    const cen = (i) => [c[0] + i * WHEEL_OFF[0] * s, c[1] + i * WHEEL_OFF[1] * s];
    // spindle
    g.strokeStyle = tone(0.35, lit);
    g.lineWidth = s * 0.22;
    g.beginPath();
    g.moveTo(...cen(-0.8));
    g.lineTo(...cen(3));
    g.stroke();
    for (let i = 2; i >= 0; i--) wheel(g, lit, ...cen(i), r, gateAngle(i, t), s);
    // fence: a bar on the rims, dropping into the lined-up gates
    const f0 = cen(-0.3), f1 = cen(2.5), fy = -r - s * 0.12 + drop;
    g.fillStyle = tone(0.7, lit);
    g.beginPath();
    B.poly(g, [[f0[0] - s * 0.1, f0[1] + fy - s * 0.18], [f1[0] - s * 0.1, f1[1] + fy - s * 0.18], [f1[0] + s * 0.1, f1[1] + fy + s * 0.18], [f0[0] + s * 0.1, f0[1] + fy + s * 0.18]], true);
    g.fill();
    // lever up to the bolt, which slides back when the fence drops
    const lv = [f0[0], f0[1] + fy], bx = c[0] + s * 3.4 - bolt * s * 1.6, by = c[1] - r * 1.55;
    g.strokeStyle = tone(0.6, lit);
    g.lineWidth = s * 0.16;
    g.beginPath();
    g.moveTo(lv[0], lv[1]);
    g.lineTo(lv[0] - s * 0.2, by + s * 0.3);
    g.lineTo(bx - s * 1.4, by + s * 0.3);
    g.stroke();
    g.fillStyle = B.linear(g, 0, by - s * 0.45, 0, by + s * 0.45, [tone(0.9, lit), tone(0.5, lit), tone(0.25, lit)]);
    g.fillRect(bx - s * 1.5, by - s * 0.42, s * 4.2, s * 0.84);
    return { gate: [cen(0)[0], cen(0)[1] - r * 0.9], fence: [f1[0], f1[1] + fy], bolt: [bx + s * 2.7, by], r };
  }

  // ---- the scenes
  function layout(F) {
    const P = F.portrait, u = F.u, S = F.safe;
    return {
      P, u, S,
      safeC: P ? [F.W * 0.55, F.H * 0.625] : [F.W * 0.7, F.H * 0.56], safeS: P ? 44 * u : 40 * u,
      floor: P ? F.H * 0.72 : F.H * 0.86,
      pack: P ? [F.W * 0.31, F.H * 0.52] : [F.W * 0.3, F.H * 0.6], packS: P ? 8.8 * u : 8 * u,
      tSize: 12 * u, card: 3.95 * u, // every label at least 3.8 % of the short side
      closeC: P ? [F.W * 0.55, F.H * 0.72 - 16.25 * u] : [F.W * 0.7, F.H * 0.56], closeS: P ? 26 * u : 40 * u,
    };
  }
  const office = {
    cam: (t, F) => pushCam(t, F, 0, 2.4, F.W / 2, F.H / 2, 1.0, 1.06),
    beams: (F) => ({ region: F.portrait ? [[-F.W * 0.1, F.H * 0.42], [F.W * 1.1, F.H * 0.3], [F.W * 1.1, F.H * 0.9], [F.W * 0.05, F.H * 0.98]] : [[F.W * 0.42, -F.H * 0.1], [F.W * 1.1, -F.H * 0.1], [F.W * 1.1, F.H * 1.1], [F.W * 0.62, F.H * 1.1]], angle: -0.42, period: F.u * 9, duty: 0.58 }),
    paint(g, lit, t, F) {
      const L = layout(F);
      wall(g, lit, F, L.floor);
      g.globalAlpha = fadeUp(t, 0.05, lit);
      safe(g, lit, L.safeC[0], L.safeC[1], L.safeS, { dial: t * 0.8 });
      g.globalAlpha = 1;
    },
    overlay(g, t, F) {
      const L = layout(F), S = L.S;
      const tx = L.P ? F.W / 2 : S.x + 4 * L.u, ty = L.P ? S.y + L.tSize * 1.1 : F.H * 0.3;
      titleWords(g, [["THE", "LOCKED"], ["SAFE"]], tx, ty, L.tSize * (L.P ? 1.15 : 1.1), t, 0.35, 0.22, { align: L.P ? "center" : "left" });
      const cw = L.P ? S.w * 0.9 : S.w * 0.4;
      placard(g, L.P ? F.W / 2 : S.x + 4 * L.u + cw / 2, L.P ? S.y + L.tSize * 3.6 : F.H * 0.66, cw, "Case file: how a combination lock knows the code", L.card, B.prog(t, 0.8, 0.4), B.prog(t, 1.0, 0.65), { from: -1, rot: -0.035, caseNo: "No. 1947" });
    },
  };
  const pack = {
    cam: (t, F) => {
      // centred right of the pack: the bolt stays in frame, with room for cards
      const L = layout(F), fx = L.pack[0] + L.packS + F.W * (L.P ? 0.08 : 0.15), fy = L.pack[1] - L.packS * 0.8;
      return t >= BEATS[3] ? pushCam(t, F, 7.2, 11.2, fx, fy, 1.02, 1.1) : pushCam(t, F, 2.3, 4.9, fx, fy, 1.0, 1.05);
    },
    beams: (F) => {
      const L = layout(F), [x, y] = L.pack, s = L.packS;
      return { region: [[x - s * 4.5, y - s * 4.6], [x + s * 4.2, y - s * 5.4], [x + s * 6.2, y + s * 3.4], [x - s * 2.6, y + s * 4.2]], angle: -0.35, period: F.u * 10, duty: 0.66, shift: F.u * 2 };
    },
    paint(g, lit, t, F) {
      const L = layout(F);
      g.fillStyle = tone(0.05, lit);
      g.fillRect(-F.W, -F.H, F.W * 3, F.H * 3);
      g.fillStyle = tone(0.1, lit); // the inside of the door: a riveted steel plate, dark so the wheels stand out
      g.fillRect(F.W * 0.04, F.H * 0.12, F.W * 0.92, F.H * 0.8);
      g.fillStyle = tone(0.45, lit);
      for (let i = 0; i < 6; i++) for (const yy of [0.15, 0.89]) {
        g.beginPath();
        B.circle(g, F.W * (0.1 + i * 0.16), F.H * yy, F.u * 0.6);
        g.fill();
      }
      g.globalAlpha = fadeUp(t, 2.35, lit);
      wheelPack(g, lit, t, L.pack, L.packS);
      g.globalAlpha = 1;
    },
    overlay(g, t, F) {
      const geo = wheelPackGeo(layout(F), t), u = F.u;
      if (t > 10.0) reelArrow(g, [[geo.bolt[0] + 8 * u, geo.bolt[1]], [geo.bolt[0] + 1 * u, geo.bolt[1]]], B.prog(t, 10.0, 0.4), u);
    },
    hud(g, t, F) {
      if (t < BEATS[2]) diagramCards(g, t, F);
      if (t < BEATS[3] - 0.5) return;
      // steps: a montage of headline cards
      const L = layout(F), steps = [[7.35, "1. EACH NUMBER PARKS ONE WHEEL", "Left, right, left: the dial drags the wheels round"], [8.3, "2. THE GATES LINE UP", "Three notches, all under the fence"], [9.5, "3. THE FENCE DROPS", "The lever pulls, and the bolt slides back"]];
      steps.forEach(([at, head, line], i) => {
        const on = B.prog(t, at, 0.35), off = i < 2 ? 1 - B.prog(t, steps[i + 1][0] - 0.1, 0.25) : 1;
        if (on * off > 0) headlineCard(g, F, L, head, line, on, off, t - at);
      });
    },
  };
  /** The diagram's placards, in screen space (clear of the camera push), with arrows to points of the pack. */
  function diagramCards(g, t, F) {
    const L = layout(F), S = L.S, u = L.u, P = L.P, W = F.W, lt = t - BEATS[1], geo = wheelPackGeo(L, t), cam = pack.cam(t, F);
    const scr = ([x, y]) => [W / 2 + cam.dx + (x - cam.x) * cam.z, F.H / 2 + cam.dy + (y - cam.y) * cam.z];
    const gate = scr(geo.gate), fence = scr(geo.fence);
    const gp = P ? [S.x + S.w * 0.22, S.y + 9 * u] : [S.x + 23 * u, S.y + 10 * u], fp = P ? [S.r - S.w * 0.25, S.y + 13 * u] : [S.r - 25 * u, S.y + 11 * u];
    placard(g, gp[0], gp[1], P ? S.w * 0.42 : 46 * u, "GATE: a notch in each wheel", L.card, B.prog(lt, 0.6, 0.4), B.prog(lt, 0.8, 0.6), { from: -1, rot: 0.03 });
    reelArrow(g, B.quad(gp[0], gp[1] + 9 * u, gp[0] + 2 * u, gate[1] - 6 * u, gate[0] - u, gate[1] - u), B.prog(lt, 1.2, 0.5, "inOutCubic"), u);
    placard(g, fp[0], fp[1], P ? S.w * 0.48 : 50 * u, "FENCE: drops only into gates in a line", L.card, B.prog(lt, 1.1, 0.4), B.prog(lt, 1.3, 0.7), { from: 1, rot: -0.04 });
    reelArrow(g, B.quad(fp[0], fp[1] + (P ? 13 : 9) * u, fp[0] - 2 * u, fence[1] - 8 * u, fence[0] + u, fence[1] - 1.5 * u), B.prog(lt, 1.6, 0.5, "inOutCubic"), u);
    placard(g, P ? W / 2 : S.r - 27 * u, P ? S.b - 10 * u : F.H * 0.72, P ? S.w * 0.8 : 50 * u, "THE WHEEL PACK, behind the dial", L.card, B.prog(lt, 0.2, 0.4), B.prog(lt, 0.35, 0.5), { from: -1, rot: -0.02, caseNo: "Exhibit A" });
  }
  function wheelPackGeo(L, t) {
    // geometry only (no drawing): same numbers as wheelPack
    const s = L.packS, r = s * 2.1, c = L.pack, drop = B.prog(t, 9.6, 0.25, "inQuad") * r * 0.2, bolt = B.prog(t, 9.95, 0.55, "inOutCubic");
    const f1 = [c[0] + 2.5 * WHEEL_OFF[0] * s, c[1] + 2.5 * WHEEL_OFF[1] * s];
    const ga = gateAngle(0, t);
    return { gate: [c[0] + Math.cos(ga) * r * 0.85, c[1] + Math.sin(ga) * r * 0.85], fence: [f1[0], f1[1] - r - s * 0.12 + drop], bolt: [c[0] + s * 3.4 - bolt * s * 1.6 + s * 2.7, c[1] - r * 1.55] };
  }
  function headlineCard(g, F, L, head, line, on, off, lt) {
    const S = L.S, u = L.u, w = L.P ? S.w : S.w * 0.42, x = L.P ? F.W / 2 : S.r - w / 2, y = L.P ? S.b - 14.5 * u : S.b - 13 * u;
    g.save();
    g.globalAlpha = off;
    g.translate(x, y + (1 - B.ease.outCubic(on)) * 6 * u);
    g.rotate(-0.02);
    const h = L.P ? 25 * u : 24 * u;
    B.withShadow(g, { color: "rgba(0,0,0,0.75)", blur: 3 * u, y: 1.2 * u }, () => {
      g.fillStyle = B.linear(g, 0, -h / 2, 0, h / 2, [PAL.white, "#d6d2c6"]);
      g.fillRect(-w / 2, -h / 2, w, h * on);
    });
    if (on > 0.6) {
      g.fillStyle = PAL.black;
      g.fillRect(-w / 2 + 2 * u, -h / 2 + 2 * u, w - 4 * u, 0.35 * u);
      B.text(g, head, 0, -h * 0.17, { size: L.P ? 6.4 * u : 5.6 * u, family: TITLE, weight: 700, color: PAL.black, maxW: w - 5 * u, maxLines: 2, lineH: 1.0, alpha: B.prog(lt, 0.2, 0.15) });
      B.text(g, line, 0, h * 0.24, { size: 3.95 * u, family: TYPE, weight: 400, color: PAL.black, maxW: w - 5 * u, reveal: B.prog(lt, 0.35, 0.6) });
    }
    g.restore();
  }
  const paper = {
    cam: (t, F) => pushCam(t, F, 5.6, 7.2, F.W / 2, F.H * 0.5, 1.0, 1.07),
    beams: (F) => ({ region: [[-F.W * 0.2, -F.H * 0.2], [F.W * 1.15, -F.H * 0.2], [F.W * 0.8, F.H * 1.2], [-F.W * 0.2, F.H * 1.2]], angle: -0.5, period: F.u * 15, duty: 0.8 }),
    paint(g, lit, t, F) {
      const L = layout(F), lt = t - BEATS[2], k = B.prog(lt, 0, 0.75, "outCubic");
      g.fillStyle = tone(0.22, lit); // the desk
      g.fillRect(-F.W, -F.H, F.W * 3, F.H * 3);
      const pw = L.P ? F.W * 0.86 : F.H * 0.62, ph = pw * 1.3;
      g.save();
      g.translate(F.W / 2, L.P ? F.H * 0.48 : F.H * 0.52);
      g.rotate(-0.06 + (1 - k) * B.TAU * 2);
      g.scale(0.08 + 0.92 * k, 0.08 + 0.92 * k);
      g.fillStyle = tone(0.88, lit);
      g.fillRect(-pw / 2, -ph / 2, pw, ph);
      g.fillStyle = tone(0.15, lit);
      g.font = B.font(pw * 0.06, TITLE, 600);
      g.textAlign = "center";
      g.textBaseline = "middle";
      B.texture(g, () => g.fillText("THE  EVENING  EDITION", 0, -ph * 0.43)); // the masthead dresses the prop
      g.fillRect(-pw * 0.45, -ph * 0.39, pw * 0.9, pw * 0.006);
      g.fillRect(-pw * 0.45, -ph * 0.375, pw * 0.9, pw * 0.003);
      B.text(g, "ONE IN A MILLION", 0, -ph * 0.3, { size: pw * 0.13, family: TITLE, weight: 700, color: tone(0.05, lit), maxW: pw * 0.92, maxLines: 1 });
      g.fillStyle = tone(0.12, lit); // photo box for the counter
      g.fillRect(-pw * 0.42, -ph * 0.2, pw * 0.84, ph * 0.3);
      g.fillStyle = tone(0.45, lit); // columns of small print
      for (let col = 0; col < 3; col++) for (let ln = 0; ln < 14; ln++) {
        const lw = pw * 0.26 * (ln % 5 === 4 ? 0.6 : 0.85 + 0.15 * B.hash01(col, ln));
        g.fillRect(-pw * 0.42 + col * pw * 0.29, ph * 0.21 + ln * ph * 0.018, lw, ph * 0.007);
      }
      g.restore();
    },
    overlay(g, t, F) {
      const L = layout(F), lt = t - BEATS[2], u = L.u, pw = L.P ? F.W * 0.86 : F.H * 0.62, ph = pw * 1.3;
      if (lt < 0.75) return;
      const cy = (L.P ? F.H * 0.48 : F.H * 0.52) - ph * 0.05;
      g.save();
      g.translate(F.W / 2, cy);
      g.rotate(-0.06);
      g.translate(-F.W / 2, -cy);
      const v = 1e6 * B.ease.inOutCubic(B.prog(lt, 0.8, 0.85));
      odometer(g, F.W / 2, cy, 7, Math.min(v, 999999.999) + (lt > 1.65 ? 0.001 : 0), pw * 0.1);
      g.restore();
      placard(g, F.W / 2 + (L.P ? 0 : pw * 0.1), L.P ? F.H * 0.48 + ph * 0.42 : F.H * 0.52 + ph * 0.3, L.P ? F.W * 0.66 : F.W * 0.3, "Three wheels,\n100 numbers each:\n100 x 100 x 100", L.card, B.prog(lt, 1.0, 0.35), B.prog(lt, 1.15, 0.6), { from: 1, rot: 0.035 });
    },
  };
  const closing = {
    cam: (t, F) => pushCam(t, F, 11.2, 13, F.W / 2, F.H / 2, 1.0, 1.05),
    beams: office.beams,
    paint(g, lit, t, F) {
      const L = layout(F);
      wall(g, lit, F, L.floor);
      safe(g, lit, L.closeC[0], L.closeC[1], L.closeS, { open: B.prog(t, 11.3, 0.8, "inOutCubic"), dial: 0 });
    },
    overlay(g, t, F) {
      const L = layout(F), S = L.S, u = L.u;
      const tx = L.P ? F.W / 2 : S.x + 4 * u, ty = L.P ? S.y + L.tSize * 0.9 : F.H * 0.24;
      titleWords(g, [["THREE", "GATES,"], ["ONE", "LINE."]], tx, ty, L.tSize, t, 11.35, 0.18, { align: L.P ? "center" : "left" });
      // a case card with room at its foot for the stamp
      const cw = L.P ? S.w * 0.84 : S.w * 0.42, cx = L.P ? F.W / 2 : S.x + 4 * u + cw / 2, cy = L.P ? S.y + 46.5 * u : F.H * 0.63, ss = (L.P ? 5 : 4.8) * u;
      const c = placard(g, cx, cy, cw, "The fence drops into the gates. The door opens.", L.card, B.prog(t, 11.5, 0.4), B.prog(t, 11.7, 0.7), { from: -1, rot: -0.025, extra: ss * 3.6 });
      const st = t - 12.35;
      if (c && st > 0) stamp(g, cx + cw * 0.06, c.y + 0.4 * u, ss, st < 0.08 ? B.lerp(1.6, 1, st / 0.08) : 1, -0.1);
    },
  };
  /** Rubber stamp in greyed red: double border, condensed caps, dry specks. */
  function stamp(g, x, y, size, s, rot) {
    const sc = B.scratch("noir-stamp", Math.ceil(size * 9), Math.ceil(size * 3));
    const w = sc.canvas.width, h = sc.canvas.height;
    sc.strokeStyle = sc.fillStyle = PAL.stamp;
    sc.lineWidth = size * 0.12;
    sc.strokeRect(size * 0.2, size * 0.2, w - size * 0.4, h - size * 0.4);
    sc.lineWidth = size * 0.05;
    sc.strokeRect(size * 0.42, size * 0.42, w - size * 0.84, h - size * 0.84);
    sc.font = B.font(size * 1.5, TITLE, 700);
    sc.textAlign = "center";
    sc.textBaseline = "middle";
    sc.fillText("CASE CLOSED", w / 2, h / 2 + size * 0.06);
    sc.globalCompositeOperation = "destination-out";
    const r = B.rng(47);
    for (let i = 0; i < 260; i++) {
      sc.globalAlpha = r.range(0.3, 1);
      sc.beginPath();
      B.circle(sc, r() * w, r() * h, r.range(0.02, 0.12) * size);
      sc.fill();
    }
    g.save();
    g.translate(x, y);
    g.rotate(rot);
    g.scale(s, s);
    g.globalAlpha = 0.9;
    g.drawImage(sc.canvas, -w / 2, -h / 2);
    g.restore();
  }

  // ---- frame: scenes, transitions, film finish
  function draw(ctx, W, H, t) {
    const F = B.frame(W, H);
    const W2 = [BEATS[5] - 0.2, BEATS[5] + 0.25]; // the wipe into the close straddles the beat change
    const scene = t < BEATS[1] ? office : t < BEATS[2] ? pack : t < BEATS[3] ? paper : t < W2[1] ? pack : closing;
    // jolt when the stamp lands
    const jolt = Math.max(0, 1 - Math.abs(t - 12.4) / 0.18);
    const film = B.scratch("noir-film", W, H);
    render(film, scene, t, F);
    // clock sweep from the newspaper into the steps
    const sw = B.span(t, BEATS[3] - 0.45, BEATS[3]);
    if (sw > 0 && sw < 1) {
      const nx = B.scratch("noir-next", W, H);
      render(nx, pack, t, F);
      film.save();
      film.beginPath();
      film.moveTo(W / 2, H / 2);
      film.arc(W / 2, H / 2, Math.hypot(W, H), -Math.PI / 2, -Math.PI / 2 + B.TAU * sw);
      film.closePath();
      film.clip();
      film.drawImage(nx.canvas, 0, 0);
      film.restore();
      film.strokeStyle = B.rgba(PAL.white, 0.7);
      film.lineWidth = F.u * 0.4;
      film.beginPath();
      film.moveTo(W / 2, H / 2);
      film.lineTo(W / 2 + Math.cos(-Math.PI / 2 + B.TAU * sw) * H, H / 2 + Math.sin(-Math.PI / 2 + B.TAU * sw) * H);
      film.stroke();
    }
    // wipe into the close
    const wp = B.span(t, W2[0], W2[1], "inOutCubic");
    if (wp > 0 && wp < 1) {
      const nx = B.scratch("noir-next", W, H);
      render(nx, closing, t, F);
      const x = wp * W * 1.1;
      film.save();
      film.beginPath();
      film.rect(0, 0, x, H);
      film.clip();
      film.drawImage(nx.canvas, 0, 0);
      film.restore();
      film.fillStyle = B.linear(film, x - F.u * 4, 0, x, 0, ["rgba(0,0,0,0)", "rgba(0,0,0,0.9)"]);
      film.fillRect(x - F.u * 4, 0, F.u * 4, H);
    }
    // iris out on the dial, iris in on the pack; fade before the newspaper
    const b1 = BEATS[1];
    const L = layout(F);
    if (t < b1) B.iris(film, W, H, 1 - B.span(t, b1 - 0.5, b1, "inCubic"), L.safeC[0], L.safeC[1] - L.safeS * 0.25, PAL.black);
    else if (t < b1 + 0.6) B.iris(film, W, H, B.span(t, b1, b1 + 0.6, "outCubic"), L.pack[0], L.pack[1], PAL.black);
    B.cover(film, W, H, PAL.black, B.span(t, BEATS[2] - 0.3, BEATS[2]) * (1 - B.span(t, BEATS[2], BEATS[2] + 0.15)));
    // print the film
    const [wx, wy] = B.shake(t, F.u * 0.18, 9, 6), [jx, jy] = B.shake(t, F.u * 1.4 * jolt, 4, 30);
    ctx.fillStyle = PAL.black;
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2 + wx + jx, H / 2 + wy + jy);
    ctx.rotate(B.noise1(t * 3, 5) * 0.0018);
    ctx.drawImage(film.canvas, -W / 2, -H / 2);
    ctx.restore();
    const bw = Math.ceil(W / 6), bh = Math.ceil(H / 6), bl = B.scratch("noir-bloom", bw, bh);
    bl.drawImage(ctx.canvas, 0, 0, bw, bh);
    bl.globalCompositeOperation = "multiply"; // keep only the brights
    bl.drawImage(bl.canvas, 0, 0);
    bl.drawImage(bl.canvas, 0, 0);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.32;
    ctx.filter = `blur(${(F.u * 0.5).toFixed(1)}px)`;
    ctx.drawImage(bl.canvas, 0, 0, W, H);
    ctx.restore();
    B.cover(ctx, W, H, PAL.black, 0.08 * (B.flicker(t, 1, 18, 2) - 0.5) + 0.04);
    B.dust(ctx, W, H, t, { count: 9, hairs: 1, scratches: 0.35, color: PAL.white, alpha: 0.45, seed: 2 });
    B.dust(ctx, W, H, t, { count: 6, hairs: 1, scratches: 0.2, color: PAL.black, alpha: 0.6, seed: 3 });
    B.vignette(ctx, W, H, { amount: 0.92, inner: 0.32, color: PAL.black });
    B.grain(ctx, W, H, { amount: 0.15, t, fps: 24, mode: "overlay", seed: 26 });
    B.grain(ctx, W, H, { amount: 0.06, t, fps: 24, mode: "screen", seed: 27 });
  }

  // ---- sound: room tone, projector, typing, stamp, ticks, brass
  SOUND.define("noir-brass", (v, o) => {
    // a muted brass sting: a dark minor chord swelling and dying
    const d = o.dur ?? 1.4;
    [o.root ?? 48, (o.root ?? 48) + 3, (o.root ?? 48) + 7, (o.root ?? 48) + 12].forEach((m, i) => {
      v.tone({ type: "sawtooth", f: SOUND.midi(m), a: 0.06, hold: d * 0.3, len: d * 0.7, peak: 0.045 - i * 0.006, detune: (i - 1.5) * 6 });
      v.tone({ type: "triangle", f: SOUND.midi(m), a: 0.05, hold: d * 0.3, len: d * 0.7, peak: 0.06 });
    });
  }, { verb: 0.5 });

  function score(k) {
    k.bed("room", 0, DUR, { gain: 0.8 });
    k.bed("projector", 0, DUR, { gain: 0.35 });
    k.at(0.0, "noir-brass", { dur: 1.8, root: 45, gain: 0.8 });
    k.repeat(0.35, 0.22, 3, "thud", { gain: 0.25, vary: 1 });
    k.at(1.15, "typing", { dur: 0.9, gain: 0.7 });
    k.at(1.9, "whoosh", { dur: 0.6, gain: 0.35 });
    // wheel pack: dial clicks, placards typed, arrows
    k.repeat(2.4, 0.15, 6, "knock", { gain: 0.25, vary: 2 });
    k.at(2.55, "typing", { dur: 0.5 }).at(3.1, "typing", { dur: 0.6 }).at(3.6, "typing", { dur: 0.7 });
    k.at(3.5, "swish", { dur: 0.4, gain: 0.4 }).at(3.9, "swish", { dur: 0.4, gain: 0.4 });
    // spinning newspaper lands, the counter rolls, brass reveal
    k.at(4.95, "whoosh", { dur: 0.75, gain: 0.7 }).at(5.65, "paper", { dur: 0.3 }).at(5.7, "thud", { gain: 0.5 });
    k.repeat(5.75, 0.05, 22, "tick", { gain: 0.35, vary: 1 });
    k.at(6.85, "noir-brass", { dur: 1.3, root: 50 });
    k.at(6.5, "typing", { dur: 0.5 });
    // steps: clock sweep, wheels parking with heavy clicks, cards typed
    k.at(6.75, "swish", { dur: 0.5, gain: 0.4 });
    [7.4, 7.75, 8.15].forEach((at, i) => k.repeat(at - 0.3, 0.07, 5, "tick", { gain: 0.3, pitch: -4 }).at(at + 0.1, "click", { gain: 0.8, pitch: -6 + i }));
    k.at(7.7, "typing", { dur: 0.6 }).at(8.65, "typing", { dur: 0.5 }).at(9.85, "typing", { dur: 0.6 });
    k.at(9.6, "knock", { gain: 0.8, pitch: -5 }).at(9.95, "swish", { dur: 0.5, gain: 0.5, pitch: -6 }).at(10.5, "thud", { gain: 0.5 });
    // close: wipe, the door creaks open, words, stamp
    k.at(10.8, "whoosh", { dur: 0.5, gain: 0.4 }).at(11.3, "fall", { dur: 0.8, gain: 0.25 });
    k.at(11.7, "typing", { dur: 0.7 });
    k.at(12.35, "stamp", { gain: 1, verb: 0.3 }).at(12.36, "thud", { gain: 0.8, verb: 0.3 });
    k.at(12.45, "noir-brass", { dur: 1.4, root: 45, gain: 0.9 });
  }

  Player.register({
    id: "noir",
    name: "Noir",
    duration: DUR,
    fonts: {
      href: "https://fonts.googleapis.com/css2?family=Oswald:wght@600;700&family=Special+Elite&display=swap",
      faces: ['700 20px "Oswald"', '600 20px "Oswald"', '400 20px "Special Elite"'],
    },
    beats: BEATS,
    beatNames: ["Title", "Diagram", "Key number", "Steps 1-2", "Step 3", "Close"],
    stills: [1.75, 4.6, 6.65, 9.25, 10.65, 12.9],
    draw,
    score,
  });
})();
