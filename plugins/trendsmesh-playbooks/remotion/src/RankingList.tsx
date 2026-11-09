import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Montserrat";
import { SAFE_1080 } from "./OrganicCaptions";

const { fontFamily } = loadFont("normal", { weights: ["700", "800", "900"], subsets: ["latin"] });

// PB3 ranking format (countdown 5 -> 1), copied from TrendsMesh evidence ("ranking the _",
// Family Guy clip rankings, Voice Kids top 5): title block on top with coloured key words,
// a numbered list down the left side that starts empty, each label (+ score) lands in its slot
// when its clip starts, the active number is highlighted. Clips are cut back to back and muted.

export type TitleWord = { text: string; accent?: boolean };
export type RankItem = { rank: number; label: string; score?: string; src: string; start: number; end: number };
export type RankingListProps = {
  width: number;
  height: number;
  fps: number;
  title: TitleWord[][]; // lines of words
  teaser?: string;
  items: RankItem[]; // in play order (5, 4, 3, 2, 1)
  slots?: number;
  accent?: string;
  showSafeZone?: boolean;
};

export const rankingListDefaults: RankingListProps = {
  width: 1080,
  height: 1920,
  fps: 24,
  title: [[{ text: "RANKING" }]],
  items: [],
  slots: 5,
  accent: "#FF8A1F",
};

export const rankingSeconds = (items: RankItem[]) => items.reduce((s, x) => s + (x.end - x.start), 0);

const stroke = (k: number, w = 7) => ({ WebkitTextStroke: `${w * k}px #111`, paintOrder: "stroke fill" as const });

export const RankingList: React.FC<RankingListProps> = ({ title, teaser, items, slots = 5, accent = "#FF8A1F", showSafeZone }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const k = width / 1080;
  const t = frame / fps;

  // start time of each item in the output
  const starts: number[] = [];
  let acc = 0;
  for (const it of items) {
    starts.push(acc);
    acc += it.end - it.start;
  }
  const activeIdx = starts.reduce((a, s, i) => (t >= s ? i : a), 0);
  const activeRank = items[activeIdx]?.rank;

  const top = SAFE_1080.top * k;
  const side = Math.max(SAFE_1080.left, SAFE_1080.right) * k;
  const listLeft = (SAFE_1080.left + 20) * k;
  const listTop = top + 300 * k;
  const rowH = 118 * k;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {items.map((it, i) => (
        <Sequence key={`v${i}`} from={Math.round(starts[i] * fps)} durationInFrames={Math.round((it.end - it.start) * fps)}>
          <OffthreadVideo src={staticFile(it.src)} startFrom={Math.round(it.start * fps)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </Sequence>
      ))}

      {/* title block, centred on the frame */}
      <div style={{ position: "absolute", top, left: side, width: width - 2 * side, textAlign: "center", fontFamily, fontWeight: 900, lineHeight: 1.08 }}>
        {title.map((line, li) => (
          <div key={li} style={{ fontSize: 50 * k, whiteSpace: "nowrap", color: "#fff", ...stroke(k, 8) }}>
            {line.map((w, wi) => (
              <span key={wi} style={{ color: w.accent ? accent : "#fff" }}>
                {w.text}
                {wi < line.length - 1 ? " " : ""}
              </span>
            ))}
          </div>
        ))}
        {teaser ? <div style={{ marginTop: 10 * k, fontSize: 36 * k, fontWeight: 800, color: "#FFE15C", ...stroke(k, 6) }}>{teaser}</div> : null}
      </div>

      {/* numbered list, left side */}
      {Array.from({ length: slots }, (_, s) => s + 1).map((rank, row) => {
        const idx = items.findIndex((x) => x.rank === rank);
        const revealed = idx >= 0 && t >= starts[idx];
        const since = idx >= 0 ? (t - starts[idx]) * fps : 0;
        const pop = revealed ? interpolate(since, [0, 6], [0.6, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.back(2.2)) }) : 1;
        const isActive = rank === activeRank;
        return (
          <div key={rank} style={{ position: "absolute", top: listTop + row * rowH, left: listLeft, display: "flex", alignItems: "baseline", fontFamily, whiteSpace: "nowrap" }}>
            <span style={{ fontSize: 84 * k, fontWeight: 900, color: isActive ? accent : "#fff", width: 116 * k, ...stroke(k, 8) }}>{rank}.</span>
            {revealed ? (
              <span style={{ display: "inline-block", transform: `scale(${pop})`, transformOrigin: "left center", fontSize: 44 * k, fontWeight: 800, color: "#fff", ...stroke(k, 6) }}>
                {items[idx].label}
                {items[idx].score ? <span style={{ color: "#FFE15C" }}>{`  ${items[idx].score}`}</span> : null}
              </span>
            ) : null}
          </div>
        );
      })}

      {showSafeZone ? (
        <div style={{ position: "absolute", top: SAFE_1080.top * k, left: SAFE_1080.left * k, width: width - (SAFE_1080.left + SAFE_1080.right) * k, height: height - (SAFE_1080.top + SAFE_1080.bottom) * k, border: `${3 * k}px dashed #00ff66`, boxSizing: "border-box" }} />
      ) : null}
    </AbsoluteFill>
  );
};
