import React from "react";
import { AbsoluteFill, Audio, Easing, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { SAFE_1080 } from "./OrganicCaptions";
import { compFont, loadFor } from "./fonts";

const quizFont = (language?: string) => loadFor(compFont("QuizGrid"), language, ["700", "800", "900"]);

// PB3 P6 "Guess the _" quiz (format copied from the evidence: bold white title with a dark outline at the top,
// labelled pictures, countdown, reveal). Everything stays inside the default safe zone (SAFE_1080).
export type QuizOption = { label: string; name: string; img: string; note: string };
export type QuizGridProps = {
  width: number;
  height: number;
  fps: number;
  title: string;
  options: QuizOption[]; // 4 options, 2x2
  answer: number; // index of the right option
  answerLine: string;
  gridInSec: number; // cards fly in
  countdownSec: number; // 3-2-1 starts
  revealSec: number;
  durationSec: number;
  music?: { src: string; volume: number };
  background: string;
  // the market language (BCP 47); picks the font subsets, or the fallback family (fonts.ts). tm render fills it in.
  language?: string;
};

export const quizGridDefaults: QuizGridProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  title: "Guess the answer",
  options: [],
  answer: 0,
  answerLine: "",
  gridInSec: 1.6,
  countdownSec: 6,
  revealSec: 9,
  durationSec: 15,
  background: "#f3ece1",
};

const outline = (k: number, w = 7) => ({ WebkitTextStroke: `${w * k}px #111`, paintOrder: "stroke fill" as const });

export const QuizGrid: React.FC<QuizGridProps> = (p) => {
  const fontFamily = quizFont(p.language);
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const k = width / 1080;
  const t = frame / fps;
  const side = Math.max(SAFE_1080.left, SAFE_1080.right) * k; // centred column (round 6)
  const colW = width - 2 * side;
  const top = SAFE_1080.top * k;
  const bottomLimit = height - SAFE_1080.bottom * k;

  // title: drops in with a bounce, then a gentle breathing scale until the reveal
  const titleIn = spring({ frame, fps, config: { damping: 11, stiffness: 140 } });
  const breathe = t < p.revealSec ? 1 + 0.015 * Math.sin(t * 4) : 1;

  // grid geometry
  const gap = 22 * k;
  const card = (colW - gap) / 2;
  const labelH = 64 * k;
  const gridTop = top + 290 * k;
  const revealF = Math.round(p.revealSec * fps);
  const revealP = spring({ frame: frame - revealF, fps, config: { damping: 13, stiffness: 120 } });

  // camera: slow push-in over the whole video, a small punch on the reveal
  const push = 1 + 0.03 * (frame / durationInFrames) + 0.025 * revealP * Math.exp(-Math.max(0, frame - revealF) / 10);

  return (
    <AbsoluteFill style={{ background: p.background, overflow: "hidden" }}>
      {/* soft moving blobs so the background is not flat */}
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: 900 * k,
            height: 900 * k,
            borderRadius: "50%",
            background: ["#ffd9a8", "#cfe8d6", "#d9dcff"][i],
            filter: `blur(${120 * k}px)`,
            opacity: 0.55,
            left: (-200 + i * 380 + 60 * Math.sin(t * 0.6 + i * 2)) * k,
            top: (200 + i * 520 + 80 * Math.cos(t * 0.5 + i)) * k,
          }}
        />
      ))}
      <AbsoluteFill style={{ transform: `scale(${push})` }}>
        {/* title */}
        <div
          style={{
            position: "absolute",
            top,
            left: side,
            width: colW,
            textAlign: "center",
            fontFamily,
            fontWeight: 900,
            fontSize: 60 * k,
            lineHeight: 1.1,
            color: "#fff",
            ...outline(k, 5),
            textShadow: `0 ${5 * k}px ${12 * k}px rgba(0,0,0,0.35)`,
            transform: `translateY(${interpolate(titleIn, [0, 1], [-260 * k, 0])}px) scale(${breathe})`,
          }}
        >
          {p.title}
        </div>

        {/* cards */}
        {p.options.map((o, i) => {
          const row = Math.floor(i / 2);
          const col = i % 2;
          const x = side + col * (card + gap);
          const y = gridTop + row * (card + labelH + gap);
          const inF = Math.round((p.gridInSec + i * 0.22) * fps);
          const pop = spring({ frame: frame - inF, fps, config: { damping: 10, stiffness: 160 } });
          const fromX = (col === 0 ? -1 : 1) * 700 * k;
          const isAns = i === p.answer;
          const dim = isAns ? 0 : revealP;
          const bob = t < p.revealSec ? 6 * k * Math.sin(t * 3 + i * 1.3) : 0;
          // countdown wiggle: every second of the countdown the cards tick
          const cdT = t - p.countdownSec;
          const tick = cdT > 0 && t < p.revealSec ? Math.exp(-(cdT % 1) * 8) : 0;
          const rot = (col === 0 ? -1 : 1) * (3 * (1 - pop) + 2.2 * tick);
          const ansScale = isAns ? 1 + 0.12 * revealP : 1 - 0.06 * revealP;
          const kb = 1.06 + 0.06 * (frame / durationInFrames); // Ken Burns inside each photo
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: x,
                top: y + bob,
                width: card,
                transform: `translateX(${interpolate(pop, [0, 1], [fromX, 0])}px) rotate(${rot}deg) scale(${ansScale})`,
                transformOrigin: "50% 50%",
                zIndex: isAns ? 2 : 1,
              }}
            >
              <div
                style={{
                  width: card,
                  height: card,
                  borderRadius: 26 * k,
                  overflow: "hidden",
                  border: `${(isAns ? 6 + 6 * revealP : 6) * k}px solid ${isAns && revealP > 0.05 ? "#22c55e" : "#fff"}`,
                  boxShadow: isAns
                    ? `0 ${10 * k}px ${30 * k}px rgba(0,0,0,0.25), 0 0 ${60 * revealP * k}px rgba(34,197,94,${0.9 * revealP})`
                    : `0 ${10 * k}px ${30 * k}px rgba(0,0,0,0.25)`,
                  boxSizing: "border-box",
                  background: "#ddd",
                  position: "relative",
                }}
              >
                <Img
                  src={staticFile(o.img)}
                  style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${kb})`, filter: `grayscale(${dim}) brightness(${1 - 0.45 * dim})` }}
                />
                {!isAns ? (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 22 * k,
                      textAlign: "center",
                      fontFamily,
                      fontWeight: 800,
                      fontSize: 34 * k,
                      lineHeight: 1.16,
                      color: "#fff",
                      ...outline(k, 5),
                      opacity: spring({ frame: frame - revealF - Math.round((0.8 + i * 0.25) * fps), fps, config: { damping: 14 } }),
                    }}
                  >
                    {o.note}
                  </div>
                ) : null}
              </div>
              {/* label pill */}
              <div style={{ display: "flex", justifyContent: "center", marginTop: -30 * k, position: "relative", zIndex: 3 }}>
                <div
                  style={{
                    fontFamily,
                    fontWeight: 800,
                    fontSize: 36 * k,
                    background: isAns && revealP > 0.05 ? "#22c55e" : "#111",
                    color: "#fff",
                    padding: `${8 * k}px ${20 * k}px`,
                    borderRadius: 999,
                    whiteSpace: "nowrap",
                    opacity: interpolate(pop, [0.4, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                  }}
                >
                  {o.label} · {o.name}
                </div>
              </div>
              {/* check badge on the answer */}
              {isAns ? (
                <div
                  style={{
                    position: "absolute",
                    top: -26 * k,
                    right: -26 * k,
                    width: 92 * k,
                    height: 92 * k,
                    borderRadius: "50%",
                    background: "#22c55e",
                    border: `${6 * k}px solid #fff`,
                    color: "#fff",
                    fontFamily,
                    fontWeight: 900,
                    fontSize: 56 * k,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transform: `scale(${revealP}) rotate(${(1 - revealP) * -90}deg)`,
                  }}
                >
                  ✓
                </div>
              ) : null}
            </div>
          );
        })}

        {/* countdown 3-2-1 in the middle of the grid */}
        {[3, 2, 1].map((n, i) => {
          const s = Math.round((p.countdownSec + i) * fps);
          return (
            <Sequence key={n} from={s} durationInFrames={fps} layout="none">
              <Countdown fontFamily={fontFamily} n={n} k={k} cx={width / 2} cy={gridTop + card + gap / 2 + labelH / 2} />
            </Sequence>
          );
        })}

        {/* reveal notes under the grid */}
        <Sequence from={revealF} layout="none">
          <RevealText p={p} k={k} left={side} width={colW} top={gridTop + 2 * (card + labelH) + gap + 24 * k} bottom={bottomLimit} />
        </Sequence>
      </AbsoluteFill>
      {p.music ? (
        <Audio
          src={staticFile(p.music.src)}
          volume={(f) => p.music!.volume * interpolate(f, [0, 8, durationInFrames - fps, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
        />
      ) : null}
    </AbsoluteFill>
  );
};

const Countdown: React.FC<{ fontFamily: string; n: number; k: number; cx: number; cy: number }> = ({ fontFamily, n, k, cx, cy }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 9, stiffness: 200 } });
  const out = interpolate(frame, [fps * 0.7, fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const ring = interpolate(frame, [0, fps], [0, 360], { extrapolateRight: "clamp" });
  const d = 230 * k;
  return (
    <div
      style={{
        position: "absolute",
        left: cx - d / 2,
        top: cy - d / 2,
        width: d,
        height: d,
        borderRadius: "50%",
        background: `conic-gradient(#ffb020 ${ring}deg, rgba(17,17,17,0.85) ${ring}deg)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `scale(${s * 1.0})`,
        opacity: out,
        zIndex: 5,
        boxShadow: `0 ${10 * k}px ${40 * k}px rgba(0,0,0,0.4)`,
      }}
    >
      <div
        style={{
          width: d - 26 * k,
          height: d - 26 * k,
          borderRadius: "50%",
          background: "#111",
          color: "#fff",
          fontFamily,
          fontWeight: 900,
          fontSize: 150 * k,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {n}
      </div>
    </div>
  );
};

const RevealText: React.FC<{ p: QuizGridProps; k: number; left: number; width: number; top: number; bottom: number }> = ({ p, k, left, width, top, bottom }) => {
  const fontFamily = quizFont(p.language);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame, fps, config: { damping: 12, stiffness: 140 } });
  return (
    <div style={{ position: "absolute", left, top, width, height: bottom - top, display: "flex", flexDirection: "column", alignItems: "center", gap: 14 * k }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 44 * k,
          lineHeight: 1.15,
          textAlign: "center",
          background: "#fff",
          color: "#111",
          borderRadius: 16 * k,
          padding: `${12 * k}px ${22 * k}px`,
          boxShadow: `0 ${6 * k}px ${18 * k}px rgba(0,0,0,0.18)`,
          transform: `translateY(${(1 - a) * 80 * k}px) scale(${0.85 + 0.15 * a})`,
          opacity: a,
        }}
      >
        {p.answerLine}
      </div>
    </div>
  );
};
