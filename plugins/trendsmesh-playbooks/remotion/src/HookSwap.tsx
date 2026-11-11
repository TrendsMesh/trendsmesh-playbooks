import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { compFont, loadFor } from "./fonts";

// A text card shown from `from` to `to` (seconds). `lines` are typed one after another;
// each line replaces the previous one at its `at` time. `top` is the card's top edge in px.
// A card that covers a burned-in overlay must span the overlay's whole lifecycle (with a few
// frames of margin on both ends) and its full bounding box, and must not animate its size.
// Keep in step with CARD_STYLES in engine/src/tm/render.py.
export type CardStyle = "box" | "outlineBar";

export type Card = {
  from: number;
  to: number;
  top: number;
  left?: number;
  width?: number;
  height?: number;
  animateIn?: boolean;
  // Edge-to-edge band (borders only top and bottom). Required whenever the covered overlay
  // touches or nearly touches a frame edge in any frame, e.g. a strip that slides in from the side.
  fullBleed?: boolean;
  fontSize?: number;
  typeCharsPerSec?: number;
  // "box" (default): white box with an orange border. "outlineBar": the Ad 3 original style, an
  // orange outline (left/top/width/height) with a white bar across it that sticks out by
  // `barExt` px on both sides and is `barHeight` px tall; the text sits in the bar.
  style?: CardStyle;
  barExt?: number;
  barHeight?: number;
  borderPx?: number;
  lines: { at: number; text: string }[];
};
// A clip laid over the base video (base audio keeps playing underneath).
export type Insert = { src: string; from: number; to: number; trimStart?: number; zoom?: number };

export type HookSwapProps = {
  base: string;
  width: number;
  height: number;
  durationSec: number;
  cards: Card[];
  inserts: Insert[];
  typeCharsPerSec?: number;
  // the market language (BCP 47); picks the font subsets, or the fallback family (fonts.ts). tm render fills it in.
  language?: string;
};

export const hookSwapDefaults: HookSwapProps = {
  base: "01_base/ad3_original.mp4",
  width: 720,
  height: 1280,
  durationSec: 24.15,
  cards: [],
  inserts: [],
};

const ORANGE = "#E8892B";

const TextCard: React.FC<{ card: Card; cps: number; fontFamily: string }> = ({ card, cps, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps + card.from;
  const current = [...card.lines].reverse().find((l) => t >= l.at) ?? card.lines[0];
  const lineCps = card.typeCharsPerSec ?? cps;
  // >= 1000 chars/s means "no typewriter": the full line is on screen from its first frame.
  const typed = lineCps >= 1000 ? current.text.length : Math.max(0, Math.floor((t - current.at) * lineCps));
  const visible = current.text.slice(0, typed);
  const appear = card.animateIn
    ? interpolate(frame, [0, 6], [0.85, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) })
    : 1;
  const height = card.height ?? 80;
  const left = card.fullBleed ? 0 : card.left ?? 24;
  const border = `${card.borderPx ?? 3}px solid ${ORANGE}`;
  if (card.style === "outlineBar") {
    const w = card.width ?? width - 2 * left;
    const ext = card.barExt ?? 10;
    const bh = card.barHeight ?? Math.round(height * 0.58);
    return (
      <div style={{ position: "absolute", top: card.top, left, width: w, height, transform: `scale(${appear})` }}>
        <div style={{ position: "absolute", inset: 0, border, boxSizing: "border-box" }} />
        <div
          style={{
            position: "absolute", left: -ext, width: w + 2 * ext, top: (height - bh) / 2, height: bh, background: "#FFFFFF",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <span style={{ fontFamily, fontSize: card.fontSize ?? 36, color: "#111", letterSpacing: 0.5, lineHeight: 1, whiteSpace: "pre" }}>{visible}</span>
        </div>
      </div>
    );
  }
  return (
    <div
      style={{
        position: "absolute",
        top: card.top,
        left,
        width: card.fullBleed ? width : card.width ?? width - 2 * left,
        height,
        background: "#FFFFFF",
        ...(card.fullBleed ? { borderTop: border, borderBottom: border } : { border, borderRadius: 4 }),
        boxSizing: "border-box",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `scale(${appear})`,
        boxShadow: "0 2px 10px rgba(0,0,0,0.18)",
      }}
    >
      <span style={{ fontFamily, fontSize: card.fontSize ?? 36, color: "#111", letterSpacing: 0.5, lineHeight: 1.05, padding: "0 18px", textAlign: "center", whiteSpace: "pre-line" }}>
        {visible}
      </span>
    </div>
  );
};

const InsertClip: React.FC<{ insert: Insert }> = ({ insert }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const len = (insert.to - insert.from) * fps;
  const opacity = interpolate(frame, [0, 4, len - 4, len], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, len], [1, insert.zoom ?? 1.06]);
  return (
    <AbsoluteFill style={{ opacity }}>
      <OffthreadVideo
        src={staticFile(insert.src)}
        startFrom={Math.round((insert.trimStart ?? 0) * fps)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }}
      />
    </AbsoluteFill>
  );
};

export const HookSwap: React.FC<HookSwapProps> = ({ base, cards, inserts, typeCharsPerSec, language }) => {
  const { fps } = useVideoConfig();
  const fontFamily = loadFor(compFont("HookSwap"), language, ["400"]);
  const cps = typeCharsPerSec ?? 40;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <OffthreadVideo src={staticFile(base)} style={{ width: "100%", height: "100%" }} />
      {inserts.map((ins, i) => (
        <Sequence key={`i${i}`} from={Math.round(ins.from * fps)} durationInFrames={Math.round((ins.to - ins.from) * fps)}>
          <InsertClip insert={ins} />
        </Sequence>
      ))}
      {cards.map((c, i) => (
        <Sequence key={`c${i}`} from={Math.round(c.from * fps)} durationInFrames={Math.round((c.to - c.from) * fps)} layout="none">
          <TextCard card={c} cps={cps} fontFamily={fontFamily} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
