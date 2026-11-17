import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Look } from "./CaptionLooks";
import { loadFor } from "./fonts";

// Overlays drawn in the same visual language as a caption look: every caption look has its own overlay family,
// so a channel or brand style is one set (captions + overlays). Kinds: the hook at the top from 0 s, a label,
// the key number (counts up), the CTA and the end card. `*word*` in the text marks the key word.
// Every animation is timed from the overlay's own first frame.
export type OverlayKind = "hook" | "label" | "number" | "cta" | "end";
export type Overlay = { kind: OverlayKind; family: Look; sub?: string; brand?: string; accent?: string };

const DARK = "#111111";
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = (f: number, n: number, e = Easing.out(Easing.cubic)) => interpolate(f, [0, n], [0, 1], { ...clamp, easing: e });
const stroke = (px: number, color = "#000"): React.CSSProperties => ({ WebkitTextStroke: `${px}px ${color}`, paintOrder: "stroke fill" } as React.CSSProperties);
const shadow = (k: number, a = 0.5) => `0 ${3 * k}px ${10 * k}px rgba(0,0,0,${a})`;

const parse = (text: string) =>
  text.split(" ").map((w) => (w.startsWith("*") && w.endsWith("*") ? { w: w.slice(1, -1), key: true } : { w, key: false }));

// One line of overlay text in the family's look; words animate in one after another where the family does that.
const Words: React.FC<{ text: string; family: Look; size: number; k: number; accent: string; frame: number; fps: number; onBox?: boolean }> = ({ text, family, size, k, accent, frame, fps, onBox }) => {
  const words = parse(family === "quiet" ? text.toLowerCase() : family === "pop" ? text.toUpperCase() : text);
  return (
    <>
      {words.map(({ w, key }, i) => {
        const s: React.CSSProperties = { display: "inline-block", whiteSpace: "pre", margin: `0 ${0.08 * size}px` };
        const f = frame - i * (family === "karaoke" ? 4 : family === "pop" ? 2 : 1.5);
        switch (family) {
          case "outline": {
            const p = interpolate(f, [0, 5], [0.6, 1], { ...clamp, easing: Easing.out(Easing.back(2.2)) });
            Object.assign(s, { fontWeight: 900, color: key ? accent : "#fff", transform: `scale(${p})`, opacity: f < 0 ? 0 : 1, textShadow: shadow(k) }, stroke(0.15 * size));
            break;
          }
          case "pill":
            Object.assign(s, key
              ? { fontWeight: 800, color: accent, background: DARK, borderRadius: 0.3 * size, padding: `0 ${0.18 * size}px` }
              : { fontWeight: 800 });
            break;
          case "block":
            Object.assign(s, { fontWeight: 700, color: key ? accent : "#fff" });
            break;
          case "karaoke": {
            // read-along: the line is there at once, dimmed, and each word lights up in turn
            const lit = f >= 0;
            Object.assign(s, { fontWeight: 800, color: lit && key ? accent : "#fff", opacity: lit ? 1 : 0.45, textShadow: shadow(k) }, stroke(0.14 * size));
            break;
          }
          case "pop": {
            const sp = spring({ frame: Math.max(0, f), fps, config: { damping: 9, stiffness: 240, mass: 0.6 } });
            Object.assign(s, { fontWeight: 900, color: key ? accent : "#fff", opacity: f < 0 ? 0 : 1, transform: `translateY(${(1 - sp) * 40 * k}px) scale(${0.55 + 0.45 * sp})`, textShadow: shadow(k) }, stroke(0.13 * size));
            break;
          }
          case "native":
            Object.assign(s, { fontWeight: 600 });
            break;
          case "quiet":
            Object.assign(s, { fontWeight: key ? 700 : 500, color: "#fff" });
            break;
          case "marker": {
            const p = key ? ease(frame - 5, 8) : 0;
            const covered = p > 0.45;
            Object.assign(s, {
              fontWeight: 800,
              color: covered ? DARK : "#fff",
              backgroundImage: key ? `linear-gradient(${accent}, ${accent})` : undefined,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "left center",
              backgroundSize: `${p * 100}% 80%`,
              padding: key ? `0 ${0.12 * size}px` : undefined,
              textShadow: covered || onBox ? undefined : shadow(k),
              ...(covered || onBox ? {} : stroke(0.15 * size)),
            });
            break;
          }
        }
        return <span key={i} style={s}>{w}</span>;
      })}
    </>
  );
};

// The box a family draws its overlay text in (none for the outline families)
const boxOf = (family: Look, k: number, accent: string, kind: OverlayKind): React.CSSProperties => {
  switch (family) {
    case "pill":
      return { background: kind === "label" ? DARK : accent, color: kind === "label" ? accent : DARK, borderRadius: 999, padding: `${10 * k}px ${34 * k}px`, boxShadow: `0 ${6 * k}px ${18 * k}px rgba(0,0,0,0.25)` };
    case "native":
      return { background: "#fff", color: DARK, borderRadius: 18 * k, padding: `${12 * k}px ${30 * k}px` };
    case "block":
      return { background: "rgba(10,10,10,0.7)", borderRadius: 18 * k, padding: `${14 * k}px ${28 * k}px` };
    case "quiet":
      return { background: "rgba(25,25,25,0.34)", backdropFilter: `blur(${16 * k}px)`, WebkitBackdropFilter: `blur(${16 * k}px)`, border: `${1.5 * k}px solid rgba(255,255,255,0.38)`, borderRadius: 24 * k, padding: `${14 * k}px ${30 * k}px`, textShadow: `0 ${1 * k}px ${8 * k}px rgba(0,0,0,0.5)` } as React.CSSProperties;
    case "marker":
      return kind === "label" ? { background: accent, padding: `${6 * k}px ${18 * k}px`, transform: "rotate(-2deg)" } : {};
    case "pop":
      return kind === "label" ? { background: accent, borderRadius: 10 * k, padding: `${6 * k}px ${20 * k}px`, transform: "rotate(-4deg)", border: `${5 * k}px solid ${DARK}` } : {};
    default:
      return {};
  }
};

// Whole-overlay entrance and exit, per family
const motion = (family: Look, frame: number, fps: number, dur: number, k: number): React.CSSProperties => {
  const out = interpolate(frame, [dur - 4, dur], [1, 0], clamp);
  switch (family) {
    case "pill": {
      const sp = spring({ frame, fps, config: { damping: 11, stiffness: 220, mass: 0.6 } });
      return { transform: `scale(${0.6 + 0.4 * sp})`, opacity: Math.min(1, frame / 2) * out };
    }
    case "block":
      return { transform: `translateY(${(1 - ease(frame, 6)) * 14 * k}px)`, opacity: ease(frame, 5) * out };
    case "quiet":
      return { transform: `translateY(${(1 - ease(frame, 8)) * 10 * k}px)`, opacity: ease(frame, 8) * out, filter: `blur(${(1 - ease(frame, 8)) * 8 * k}px)` };
    case "pop":
      return { transform: "rotate(-3deg)", opacity: out };
    case "native":
      return {}; // TikTok text appears and disappears on a cut
    case "karaoke":
    case "marker":
      return { transform: `scale(${interpolate(frame, [0, 5], [0.9, 1], { ...clamp, easing: Easing.out(Easing.back(2)) })})`, opacity: out };
    default:
      return { opacity: out };
  }
};

const SIZES: Record<OverlayKind, number> = { hook: 62, label: 40, number: 150, cta: 54, end: 96 };

export const OverlayLook: React.FC<{ text: string; o: Overlay; k: number; fontFamily: string; durFrames: number; language?: string }> = ({ text, o, k, fontFamily: brandFont, durFrames, language }) => {
  const fontFamily = o.family === "native" ? loadFor("TikTokSans", language, ["500", "600", "700", "800", "900"]) : brandFont;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const accent = o.accent ?? "#FFD84D";
  const fam = o.family;
  const base = SIZES[o.kind] * (fam === "pop" && o.kind !== "number" ? 1.25 : fam === "quiet" ? 0.85 : 1) * k;
  const m = motion(fam, frame, fps, durFrames, k);
  const box = boxOf(fam, k, accent, o.kind);
  const onBox = Object.keys(box).length > 0 && fam !== "pop";

  if (o.kind === "number") {
    // counts up to the figure in the text (e.g. "+212%") over the first half second
    const match = text.match(/^(\D*)(\d+)(\D*)$/);
    const target = match ? Number(match[2]) : 0;
    const shownNum = match ? `${match[1]}${Math.round(target * ease(frame, 12, Easing.out(Easing.quad)))}${match[3]}` : text;
    const numStyle: React.CSSProperties = { color: fam === "pill" || fam === "native" ? DARK : "#fff", fontWeight: 900, fontSize: base, lineHeight: 1, fontVariantNumeric: "tabular-nums", letterSpacing: -0.02 * base };
    if (fam === "outline" || fam === "karaoke" || fam === "pop" || fam === "marker") Object.assign(numStyle, { color: fam === "outline" || fam === "pop" ? accent : "#fff", textShadow: shadow(k) }, stroke(14 * k));
    if (fam === "marker") Object.assign(numStyle, { backgroundImage: `linear-gradient(${accent}, ${accent})`, backgroundRepeat: "no-repeat", backgroundPosition: "left 85%", backgroundSize: `${ease(frame - 6, 8) * 100}% 28%`, padding: `0 ${16 * k}px` });
    if (fam === "quiet") Object.assign(numStyle, { fontWeight: 700 });
    return (
      <div style={{ fontFamily, textAlign: "center", ...m }}>
        <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 6 * k, ...box }}>
          <div style={numStyle}>{shownNum}</div>
          {o.sub ? (
            <div style={{ fontSize: 38 * k * (fam === "quiet" ? 0.9 : 1), lineHeight: 1.2 }}>
              <Words text={o.sub} family={fam} size={38 * k} k={k} accent={accent} frame={frame - 6} fps={fps} onBox={onBox} />
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  if (fam === "native" && o.kind !== "number") {
    // TikTok's "text with background": white boxes hugging each line, black text, no motion
    const sizeN = (o.kind === "end" ? 64 : o.kind === "label" ? 44 : o.kind === "cta" ? 50 : 58) * k;
    const lineBox = (t: string, sz: number, weight = 600) => (
      <div style={{ textAlign: "center", lineHeight: 1.5, fontSize: sz, maxWidth: 700 * k, margin: "0 auto", textWrap: "balance" } as React.CSSProperties}>
        <span style={{ background: "#fff", color: DARK, fontWeight: weight, padding: `${0.14 * sz}px ${0.32 * sz}px`, borderRadius: 0.24 * sz, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" } as React.CSSProperties}>
          {t.replace(/\*/g, "")}{o.kind === "cta" ? " →" : ""}
        </span>
      </div>
    );
    if (o.kind === "end") {
      return (
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 24 * k, fontFamily }}>
          {lineBox(o.brand ?? "brand", sizeN * 1.25, 700)}
          {lineBox(text, sizeN * 0.75)}
          {lineBox(o.sub ?? "Link in bio", sizeN * 0.75, 700)}
        </div>
      );
    }
    return <div style={{ fontFamily, width: "100%" }}>{lineBox(text, sizeN)}</div>;
  }

  if (o.kind === "end") {
    // end card: the video dimmed (blurred for the quiet family), the logo, the brand, a line and the CTA
    const enter = ease(frame, 8);
    const dim: React.CSSProperties = fam === "quiet"
      ? { background: "rgba(0,0,0,0.25)", backdropFilter: `blur(${24 * k * enter}px)` } as React.CSSProperties
      : fam === "pill" ? { background: accent } : { background: `rgba(0,0,0,${0.62 * enter})` };
    const markBg = fam === "pill" ? DARK : fam === "quiet" ? "rgba(255,255,255,0.18)" : accent;
    const markFg = fam === "pill" ? accent : fam === "quiet" ? "#fff" : DARK;
    const cardText = fam === "pill" ? DARK : "#fff";
    return (
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 28 * k, fontFamily, color: cardText, ...dim, opacity: fam === "pill" ? enter : 1, transform: fam === "pill" ? `translateY(${(1 - enter) * 120 * k}px)` : undefined }}>
        <div style={{ transform: `translateY(${(1 - enter) * 30 * k}px)`, opacity: enter, display: "flex", flexDirection: "column", alignItems: "center", gap: 22 * k }}>
          <div style={{ width: 190 * k, height: 190 * k, borderRadius: 46 * k, background: markBg, color: markFg, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, fontSize: 118 * k, border: fam === "quiet" ? `${2 * k}px solid rgba(255,255,255,0.5)` : undefined }}>t</div>
          <div style={{ fontSize: base, lineHeight: 1.1 }}>
            {fam === "pill" ? <span style={{ fontWeight: 900 }}>{o.brand ?? "brand"}</span> : <Words text={o.brand ?? "brand"} family={fam === "marker" ? "outline" : fam} size={base} k={k} accent={accent} frame={frame - 4} fps={fps} />}
          </div>
          <div style={{ fontSize: 46 * k, fontWeight: 600, opacity: 0.92, textShadow: fam === "pill" ? undefined : shadow(k, 0.4) }}>{fam === "quiet" ? text.toLowerCase() : text}</div>
          <div style={{ marginTop: 10 * k, fontSize: 50 * k, fontWeight: 800, padding: `${18 * k}px ${50 * k}px`, borderRadius: 999, background: fam === "pill" ? DARK : fam === "quiet" ? "rgba(255,255,255,0.2)" : accent, color: fam === "pill" ? accent : fam === "quiet" ? "#fff" : DARK, border: fam === "quiet" ? `${1.5 * k}px solid rgba(255,255,255,0.45)` : undefined, transform: `scale(${1 + 0.04 * Math.sin(Math.max(0, frame - 10) / 5)})` }}>
            {fam === "quiet" ? (o.sub ?? "link in bio").toLowerCase() : fam === "pop" ? (o.sub ?? "Link in bio").toUpperCase() : o.sub ?? "Link in bio"}
          </div>
        </div>
      </div>
    );
  }

  // hook, label, CTA: one box (or none) with the family's words; the CTA arrow nudges
  const label = o.kind === "label";
  const size = base;
  const line: React.CSSProperties = {
    display: "inline-block",
    fontFamily,
    fontSize: size,
    lineHeight: 1.18,
    textAlign: "center",
    textWrap: "balance",
    letterSpacing: label ? 0.06 * size : undefined,
    textTransform: label && fam !== "quiet" ? "uppercase" : undefined,
    color: fam === "pill" || ((fam === "marker" || fam === "pop") && label) ? DARK : "#fff",
    ...box,
  } as React.CSSProperties;
  const arrow = o.kind === "cta" ? <span style={{ display: "inline-block", marginLeft: 0.25 * size, transform: `translateX(${Math.sin(frame / 4) * 6 * k}px)`, fontWeight: 900 }}>→</span> : null;
  const labelFamily: Look = label && (fam === "marker" || fam === "pop") ? "pill" : fam; // a label on a sticker reads dark
  return (
    <div style={{ textAlign: "center", ...m }}>
      <div style={line}>
        <Words text={text} family={labelFamily} size={size} k={k} accent={accent} frame={frame} fps={fps} onBox={onBox} />
        {arrow}
      </div>
    </div>
  );
};
