import React from "react";
import { AbsoluteFill, Audio, Easing, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { compFont, loadFor } from "./fonts";

// PB3 organic edit: source segments cut back to back (always muted: the trending sound is attached
// in the app), plus native-style text inside the default safe zone.
// Default safe zone = the most restrictive margins of TikTok, Reels and Shorts at 1080x1920
// (PB3 decision 12; values and sources in playbook-03-organic-ai-video/ANALYSIS.md). Scaled to other sizes.
export const SAFE_1080 = { top: 260, bottom: 380, left: 90, right: 200 };

// A segment is a video cut (`start` to `end` seconds of it), or a still picture (.png, .jpg, .webp) shown for
// `end - start` seconds: the text look and a cover are drawn over a first frame (issue 89).
export type Segment = { src: string; start: number; end: number; volume?: number; zoom?: number; zoomOrigin?: string }; // volume used only with keepAudio (0 mutes this segment)
// One spoken word and its seconds in the video (tm organic captions writes them from the voiceover's word times).
export type Word = { text: string; from: number; to: number };
export type Caption = {
  from: number;
  to: number;
  text: string;
  // "hook" = a box with dark text (TikTok background style): the overlays (the hook, the key number, the closing
  // question); "caption" = the captions under the voiceover, TikTok style: white with a black outline, at the bottom;
  // "note" = white text with a dark outline
  style?: "hook" | "note" | "caption";
  // anchor inside the safe zone (default: top, bottom for a caption)
  place?: "top" | "middle" | "bottom";
  // the lines follow the size and the width; a line break in the text is kept
  fontSize?: number;
  // px at 1080×1920 from the anchor: negative moves the text up (off a face), positive down
  offsetY?: number;
  // the text column's width, px at 1080 (default 680, centred on the frame; at most 790, the safe zone's width)
  width?: number;
  color?: string;
  background?: string; // the box of a hook
  stroke?: string; // the outline of a caption or a note
  // the spoken word's colour, when `words` are given (a caption)
  highlight?: string;
  words?: Word[];
};
export type Music = { src: string; volume: number; fadeInSec?: number; fadeOutSec?: number };
export type OrganicCaptionsProps = {
  width: number;
  height: number;
  fps: number;
  segments: Segment[];
  captions: Caption[];
  showSafeZone?: boolean;
  // PB3 round 30: native speech/ASMR takes keep their own sound (default stays muted for in-app trending sounds)
  keepAudio?: boolean;
  // optional music bed under the native sound (volume 0-1, linear)
  music?: Music;
  // extra audio tracks (e.g. an ElevenLabs voiceover), placed at `from` seconds
  audioTracks?: { src: string; from: number; volume: number }[];
  // the market language (BCP 47); picks the font subsets, or the fallback family (fonts.ts). tm render fills it in.
  language?: string;
};

export const organicCaptionsDefaults: OrganicCaptionsProps = {
  width: 1080,
  height: 1920,
  fps: 24,
  segments: [],
  captions: [],
  showSafeZone: false,
};

export const totalSeconds = (segments: Segment[]) => segments.reduce((s, x) => s + (x.end - x.start), 0);

export const COLUMN_1080 = 680; // the default column: the larger side margin on both sides
export const IMAGE = /\.(png|jpe?g|webp)$/i;

// The text column, px in the output frame: `width` (default COLUMN_1080) centred on the frame, moved left as far as
// the safe zone allows when it is wider than the centred column can be.
export const column = (c: Caption, k: number, width: number) => {
  const usable = 1080 - SAFE_1080.left - SAFE_1080.right;
  const w = Math.min(Math.max(c.width ?? COLUMN_1080, 120), usable) * k;
  const left = Math.min(Math.max(width / 2 - w / 2, SAFE_1080.left * k), width - SAFE_1080.right * k - w);
  return { left, w };
};

const Words: React.FC<{ c: Caption; t: number }> = ({ c, t }) => (
  <>
    {(c.words ?? []).map((w, i) => (
      <React.Fragment key={i}>
        {i > 0 ? " " : null}
        <span style={{ color: t >= w.from && t < w.to ? c.highlight : undefined }}>{w.text}</span>
      </React.Fragment>
    ))}
  </>
);

const CaptionView: React.FC<{ c: Caption; k: number; fontFamily: string }> = ({ c, k, fontFamily }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const pop = interpolate(frame, [0, 5], [0.9, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.back(2)) });
  const shift = (c.offsetY ?? 0) * k;
  const top = SAFE_1080.top * k + shift;
  const bottom = SAFE_1080.bottom * k - shift;
  // Text is centered on the frame, not on the (asymmetric) safe zone: the default column uses the larger
  // side margin on both sides, so it stays inside the safe zone and looks centered (user, round 6).
  const { left, w: boxW } = column(c, k, width);
  const caption = c.style === "caption";
  const place = c.place ?? (caption ? "bottom" : "top");
  const justify = place === "bottom" ? "flex-end" : place === "middle" ? "center" : "flex-start";
  const size = (c.fontSize ?? (caption ? 64 : c.style === "note" ? 52 : 58)) * k;
  const hook = c.style !== "note" && !caption;
  const outline = caption ? 9 : 6;
  const lit = caption && c.highlight && (c.words ?? []).length > 0;
  return (
    <div style={{ position: "absolute", top, left, width: boxW, height: height - top - bottom, display: "flex", flexDirection: "column", justifyContent: justify, alignItems: "center" }}>
      <div
        style={{
          transform: `scale(${pop})`,
          fontFamily,
          fontWeight: 800,
          fontSize: size,
          lineHeight: 1.18,
          textAlign: "center",
          color: c.color ?? (hook ? "#111" : "#fff"),
          background: hook ? c.background ?? "#fff" : "transparent",
          borderRadius: 14 * k,
          padding: hook ? `${10 * k}px ${22 * k}px` : 0,
          WebkitTextStroke: hook ? undefined : `${outline * k}px ${c.stroke ?? (caption ? "#000" : "#111")}`,
          paintOrder: "stroke fill",
          textShadow: hook ? undefined : `0 ${3 * k}px ${8 * k}px rgba(0,0,0,${caption ? 0.6 : 0.45})`,
          maxWidth: boxW,
          whiteSpace: "pre-line",
          textWrap: "balance",
          boxDecorationBreak: "clone",
        } as React.CSSProperties}
      >
        {lit ? <Words c={c} t={c.from + frame / fps} /> : c.text}
      </div>
    </div>
  );
};

export const OrganicCaptions: React.FC<OrganicCaptionsProps> = ({ segments, captions, showSafeZone, keepAudio, music, audioTracks, language }) => {
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const fontFamily = loadFor(compFont("OrganicCaptions"), language, ["700", "800"]);
  const k = width / 1080;
  let cursor = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {segments.map((s, i) => {
        const from = Math.round(cursor * fps);
        const dur = Math.round((s.end - s.start) * fps);
        cursor += s.end - s.start;
        return (
          <Sequence key={`s${i}`} from={from} durationInFrames={dur}>
            {IMAGE.test(s.src) ? (
              <Img src={staticFile(s.src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: s.zoom ? `scale(${s.zoom})` : undefined, transformOrigin: s.zoomOrigin ?? "50% 50%" }} />
            ) : (
              <OffthreadVideo src={staticFile(s.src)} startFrom={Math.round(s.start * fps)} muted={!keepAudio || s.volume === 0} volume={s.volume ?? 1} style={{ width: "100%", height: "100%", objectFit: "cover", transform: s.zoom ? `scale(${s.zoom})` : undefined, transformOrigin: s.zoomOrigin ?? "50% 50%" }} />
            )}
          </Sequence>
        );
      })}
      {(audioTracks ?? []).map((a, i) => (
        <Sequence key={`a${i}`} from={Math.round(a.from * fps)} layout="none">
          <Audio src={staticFile(a.src)} volume={a.volume} />
        </Sequence>
      ))}
      {music ? (
        <Audio
          src={staticFile(music.src)}
          volume={(f) => {
            const fin = Math.max(1, Math.round((music.fadeInSec ?? 0.3) * fps));
            const fout = Math.max(1, Math.round((music.fadeOutSec ?? 1) * fps));
            return music.volume * interpolate(f, [0, fin, durationInFrames - fout, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          }}
        />
      ) : null}
      {captions.map((c, i) => (
        <Sequence key={`c${i}`} from={Math.round(c.from * fps)} durationInFrames={Math.max(1, Math.round((c.to - c.from) * fps))} layout="none">
          <CaptionView c={c} k={k} fontFamily={fontFamily} />
        </Sequence>
      ))}
      {showSafeZone ? (
        <div
          style={{
            position: "absolute",
            top: SAFE_1080.top * k,
            left: SAFE_1080.left * k,
            width: width - (SAFE_1080.left + SAFE_1080.right) * k,
            height: height - (SAFE_1080.top + SAFE_1080.bottom) * k,
            border: `${3 * k}px dashed #00ff66`,
            boxSizing: "border-box",
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
