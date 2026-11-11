import React from "react";
import { AbsoluteFill, Audio, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { compFont, loadFor } from "./fonts";

// PB3 organic edit: source segments cut back to back (always muted: the trending sound is attached
// in the app), plus native-style text inside the default safe zone.
// Default safe zone = the most restrictive margins of TikTok, Reels and Shorts at 1080x1920
// (PB3 decision 12; values and sources in playbook-03-organic-ai-video/ANALYSIS.md). Scaled to other sizes.
export const SAFE_1080 = { top: 260, bottom: 380, left: 90, right: 200 };

export type Segment = { src: string; start: number; end: number; volume?: number; zoom?: number; zoomOrigin?: string }; // volume used only with keepAudio (0 mutes this segment)
export type Caption = {
  from: number;
  to: number;
  text: string;
  // "hook" = white box with black text (TikTok background style); "note" = white text with a dark outline
  style?: "hook" | "note";
  // anchor inside the safe zone
  place?: "top" | "middle" | "bottom";
  fontSize?: number;
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

const CaptionView: React.FC<{ c: Caption; k: number; fontFamily: string }> = ({ c, k, fontFamily }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const pop = interpolate(frame, [0, 5], [0.9, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.back(2)) });
  const top = SAFE_1080.top * k;
  const bottom = SAFE_1080.bottom * k;
  // Text is centered on the frame, not on the (asymmetric) safe zone: the column uses the larger
  // side margin on both sides, so it stays inside the safe zone and looks centered (user, round 6).
  const side = Math.max(SAFE_1080.left, SAFE_1080.right) * k;
  const left = side;
  const boxW = width - 2 * side;
  const justify = c.place === "bottom" ? "flex-end" : c.place === "middle" ? "center" : "flex-start";
  const size = (c.fontSize ?? (c.style === "note" ? 52 : 58)) * k;
  const hook = c.style !== "note";
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
          color: hook ? "#111" : "#fff",
          background: hook ? "#fff" : "transparent",
          borderRadius: 14 * k,
          padding: hook ? `${10 * k}px ${22 * k}px` : 0,
          WebkitTextStroke: hook ? undefined : `${6 * k}px #111`,
          paintOrder: "stroke fill",
          textShadow: hook ? undefined : `0 ${3 * k}px ${8 * k}px rgba(0,0,0,0.45)`,
          maxWidth: boxW,
          whiteSpace: "pre-line",
          boxDecorationBreak: "clone",
        }}
      >
        {c.text}
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
            <OffthreadVideo src={staticFile(s.src)} startFrom={Math.round(s.start * fps)} muted={!keepAudio || s.volume === 0} volume={s.volume ?? 1} style={{ width: "100%", height: "100%", objectFit: "cover", transform: s.zoom ? `scale(${s.zoom})` : undefined, transformOrigin: s.zoomOrigin ?? "50% 50%" }} />
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
