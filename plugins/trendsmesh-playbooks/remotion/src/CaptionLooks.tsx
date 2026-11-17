import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Caption, Word } from "./OrganicCaptions";
import { loadFor } from "./fonts";

// The text style's looks for the captions under the speech (style "caption" with a `look`). Each look has an overlay
// family in OverlayLooks.tsx, so a text style is one set: captions + overlays. How the spoken words are split into
// on-screen chunks per look is the engine's (LOOK_WORDS, LOOK_CHARS in tm.organic_edit); this file draws one chunk.
// Every animation is timed from the moment its own word or chunk starts, never from the start of the video. The
// accent is the brand colour (`highlight`). "native" = TikTok's own look: TikTok Sans, captions like TikTok's auto
// captions, white-box overlays, no animation. Keep `Look` in step with LOOKS in tm.organic_edit.
export type Look = "outline" | "pill" | "block" | "karaoke" | "pop" | "quiet" | "marker" | "native";

const SIZE: Record<Look, number> = { outline: 68, pill: 64, block: 54, karaoke: 60, pop: 108, quiet: 50, marker: 66, native: 52 };
const DARK = "#111111";

type State = "past" | "active" | "future";

// The active word is the last one already spoken, so the highlight does not blink off in the gaps between words.
const states = (words: Word[], t: number): { state: State; since: number }[] => {
  let active = -1;
  words.forEach((w, i) => {
    if (t >= w.from) active = i;
  });
  return words.map((w, i) => ({
    state: i < active ? "past" : i === active ? "active" : "future",
    since: t - w.from,
  }));
};

const outlined = (k: number, px: number, color = "#000"): React.CSSProperties => ({
  WebkitTextStroke: `${px * k}px ${color}`,
  paintOrder: "stroke fill",
} as React.CSSProperties);

const shown = (look: Look, text: string) =>
  look === "quiet" ? text.toLowerCase().replace(/[.,!?;:]+$/, "") : look === "pop" ? text.replace(/[.,;:]+$/, "").toUpperCase() : text;

export const CaptionLook: React.FC<{ c: Caption & { look: Look }; k: number; fontFamily: string; language?: string }> = ({ c, k, fontFamily: brandFont, language }) => {
  const fontFamily = c.look === "native" ? loadFor("TikTokSans", language, ["500", "600", "700"]) : brandFont;
  const frame = useCurrentFrame(); // frames since this chunk appeared
  const { fps } = useVideoConfig();
  const t = c.from + frame / fps;
  const look = c.look;
  const accent = c.highlight ?? "#FFD84D";
  const ink = c.ink ?? DARK; // the text on the accent, dark or white by contrast
  const words = c.words ?? [];
  const st = states(words, t);
  const size = (c.fontSize ?? SIZE[look]) * k;
  const ease = (f: number, n: number) => interpolate(f, [0, n], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

  // Chunk entrance, from the chunk's first frame
  const enter = ease(frame, 4);
  let box: React.CSSProperties = {};
  let entrance = "";
  if (look === "outline" || look === "marker" || look === "karaoke" || look === "pill") {
    entrance = `scale(${interpolate(frame, [0, 4], [0.9, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.back(2)) })})`;
  } else if (look === "block" || look === "quiet") {
    entrance = `translateY(${(1 - enter) * 10 * k}px)`;
  }
  if (look === "block") {
    box = { background: "rgba(10,10,10,0.66)", borderRadius: 18 * k, padding: `${12 * k}px ${26 * k}px`, boxDecorationBreak: "clone" } as React.CSSProperties;
  }

  const base: React.CSSProperties = {
    fontFamily,
    fontSize: size,
    lineHeight: 1.22,
    textAlign: "center",
    color: "#fff",
    whiteSpace: "normal",
    textWrap: "balance",
    maxWidth: "100%",
    transform: entrance || undefined,
    opacity: look === "block" || look === "quiet" ? enter : 1,
    ...box,
  } as React.CSSProperties;

  const wordEl = (w: Word, i: number) => {
    const { state, since } = st[i];
    const wf = since * fps; // frames since this word was spoken (negative before)
    const key = (w as Word & { key?: boolean }).key === true;
    const text = shown(look, w.text);
    const s: React.CSSProperties = { display: "inline-block", whiteSpace: "pre", margin: `0 ${0.06 * size}px` };
    switch (look) {
      case "outline": {
        const grow = state === "active" ? interpolate(wf, [0, 3], [1, 1.08], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1;
        Object.assign(s, { fontWeight: 800, color: state === "active" ? accent : "#fff", transform: `scale(${grow})`, textShadow: `0 ${3 * k}px ${8 * k}px rgba(0,0,0,0.55)` }, outlined(k, 10));
        break;
      }
      case "pill": {
        const on = state === "active";
        const p = on ? ease(wf, 3) : 0;
        Object.assign(s, {
          fontWeight: 800,
          color: on ? ink : "#fff",
          background: on ? accent : "transparent",
          borderRadius: 0.24 * size,
          padding: `${0.02 * size}px ${0.22 * size}px`,
          margin: `0 ${-0.1 * size}px`,
          transform: `scale(${on ? 0.88 + 0.12 * p : 1})`,
          textShadow: on ? undefined : `0 ${3 * k}px ${10 * k}px rgba(0,0,0,0.6)`,
          ...(on ? {} : outlined(k, 6)),
        });
        break;
      }
      case "block":
        Object.assign(s, { fontWeight: 700 });
        break;
      case "karaoke": {
        // Whole phrase on screen: spoken words white, the word being spoken in the accent, the rest dimmed
        Object.assign(s, { fontWeight: 800, color: state === "active" ? accent : "#fff", opacity: state === "future" ? 0.5 : 1 }, outlined(k, 9));
        break;
      }
      case "pop": {
        const sp = spring({ frame: Math.max(0, wf), fps, config: { damping: 9, stiffness: 240, mass: 0.6 } });
        Object.assign(s, {
          fontWeight: 900,
          letterSpacing: 0.01 * size,
          color: key ? accent : "#fff",
          transform: `translateY(${(1 - sp) * 40 * k}px) scale(${0.55 + 0.45 * sp})`,
          textShadow: `0 ${4 * k}px ${12 * k}px rgba(0,0,0,0.5)`,
        }, outlined(k, 13));
        break;
      }
      case "quiet":
        Object.assign(s, { fontWeight: 600, textShadow: `0 ${2 * k}px ${10 * k}px rgba(0,0,0,0.75), 0 0 ${2 * k}px rgba(0,0,0,0.6)` });
        break;
      case "native":
        // TikTok auto captions: white, a thin dark edge, no motion
        Object.assign(s, { fontWeight: 600, textShadow: `0 ${2 * k}px ${4 * k}px rgba(0,0,0,0.55)` }, outlined(k, 0.07 * size / k));
        break;
      case "marker": {
        // The key word gets a highlighter stroke drawn left to right from the moment it is spoken
        const p = key && state !== "future" ? ease(wf, 6) : 0;
        const covered = p > 0.45;
        Object.assign(s, {
          fontWeight: 800,
          color: covered ? ink : "#fff",
          backgroundImage: key ? `linear-gradient(${accent}, ${accent})` : undefined,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "left center",
          backgroundSize: `${p * 100}% 78%`,
          padding: key ? `0 ${0.12 * size}px` : undefined,
          margin: key ? `0 ${-0.06 * size}px` : undefined,
          textShadow: covered ? undefined : `0 ${3 * k}px ${8 * k}px rgba(0,0,0,0.55)`,
          ...(covered ? {} : outlined(k, 10)),
        });
        break;
      }
    }
    return (
      <React.Fragment key={i}>
        {i > 0 ? " " : null}
        <span style={s}>{text}</span>
      </React.Fragment>
    );
  };

  return <div style={base}>{words.map(wordEl)}</div>;
};
