import React from "react";
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont as loadNunito } from "@remotion/google-fonts/Nunito";
import { loadFont as loadBaloo } from "@remotion/google-fonts/Baloo2";
import { loadFont as loadFredoka } from "@remotion/google-fonts/Fredoka";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";

// Fonts tried when matching a burned-in caption style; `font` in props picks one.
const FONTS: Record<string, string> = {
  nunito: loadNunito("normal", { weights: ["900"], subsets: ["latin", "latin-ext"] }).fontFamily,
  baloo: loadBaloo("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }).fontFamily,
  fredoka: loadFredoka("normal", { weights: ["700"], subsets: ["latin", "latin-ext"] }).fontFamily,
  montserrat: loadMontserrat("normal", { weights: ["900"], subsets: ["latin", "latin-ext"] }).fontFamily,
  // ad_2 (UGC) captions: Montserrat SemiBold, lowercase
  montserrat600: loadMontserrat("normal", { weights: ["600"], subsets: ["latin", "latin-ext"] }).fontFamily,
};

// One word on screen at a time (karaoke-style captions), shown from `from` to `to` seconds.
export type Word = { text: string; from: number; to: number };

export type CaptionStyle = {
  font: keyof typeof FONTS;
  fontSize: number;
  fontWeight: number;
  color: string;
  stroke: string;
  strokeWidth: number;
  centerX: number;
  // y of the cap baseline (bottom of letters without descenders), px in the output frame
  baselineY: number;
  letterSpacing?: number;
  // vertical stretch around the baseline, to match captions rendered in a slightly condensed font
  scaleY?: number;
  // default "uppercase" (ExampleTravel); "none" keeps the words as given (ad_2 uses lowercase)
  textTransform?: "uppercase" | "none";
};

export type WordCaptionsProps = {
  base: string;
  baseMuted?: boolean;
  width: number;
  height: number;
  durationSec: number;
  words: Word[];
  style: CaptionStyle;
  // extra rows drawn for style matching (stills only)
  probe?: { text: string; dy: number; font?: keyof typeof FONTS; fontSize?: number; strokeWidth?: number }[];
};

export const wordCaptionsDefaults: WordCaptionsProps = {
  base: "01_base/exampletravel_original.mp4",
  width: 1080,
  height: 1920,
  durationSec: 26.865,
  words: [],
  style: { font: "nunito", fontSize: 64, fontWeight: 900, color: "#FFFFFF", stroke: "#15151A", strokeWidth: 7, centerX: 540, baselineY: 1499 },
};

const CaptionWord: React.FC<{ text: string; style: CaptionStyle; dy?: number; font?: keyof typeof FONTS }> = ({ text, style, dy = 0, font }) => {
  const family = FONTS[font ?? style.font];
  // Line box of 1.2 em; cap baseline sits about 0.2 em above the box bottom for these fonts,
  // fine-tuned per font with `baselineY`.
  const box = style.fontSize * 1.2;
  const common: React.CSSProperties = {
    position: "absolute",
    left: 0,
    width: style.centerX * 2,
    top: style.baselineY - box + style.fontSize * 0.2 + dy,
    height: box,
    lineHeight: `${box}px`,
    textAlign: "center",
    fontFamily: family,
    fontSize: style.fontSize,
    fontWeight: style.fontWeight,
    letterSpacing: style.letterSpacing ?? 0,
    textTransform: style.textTransform ?? "uppercase",
    whiteSpace: "nowrap",
    transform: `scaleY(${style.scaleY ?? 1})`,
    transformOrigin: `50% ${box - style.fontSize * 0.2}px`,
  };
  return (
    <>
      <div style={{ ...common, color: style.stroke, WebkitTextStroke: `${style.strokeWidth * 2}px ${style.stroke}`, strokeLinejoin: "round" }}>{text}</div>
      <div style={{ ...common, color: style.color }}>{text}</div>
    </>
  );
};

export const WordCaptions: React.FC<WordCaptionsProps> = ({ base, baseMuted, words, style, probe }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const current = words.find((w) => t >= w.from && t < w.to);
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <OffthreadVideo src={staticFile(base)} muted={baseMuted ?? true} />
      {current ? <CaptionWord text={current.text} style={style} /> : null}
      {(probe ?? []).map((p, i) => (
        <CaptionWord key={i} text={p.text} style={{ ...style, fontSize: p.fontSize ?? style.fontSize, strokeWidth: p.strokeWidth ?? style.strokeWidth }} dy={p.dy} font={p.font} />
      ))}
    </AbsoluteFill>
  );
};
