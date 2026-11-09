import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Poppins";
import { SAFE_1080 } from "./OrganicCaptions";
import { RankItem, rankingSeconds } from "./RankingList";

const { fontFamily } = loadFont("normal", { weights: ["700", "800"], subsets: ["latin"] });
const italic = loadFont("italic", { weights: ["800"], subsets: ["latin"] });

// PB3 ranking, "split" look copied from three "Ranking _" videos of the TrendsMesh evidence (2026-11-05):
// - top panel: the same clip, zoomed and blurred, carrying the title and the list;
// - bottom panel: the clip itself;
// - title in a rounded bold sans, Title Case, each key word in its own colour, thick black outline;
// - small green teaser under the title;
// - italic numbers in medal colours (1 gold, 2 silver, 3 bronze, 4-5 white), no "active" highlight;
// - white label with an emoji and a grey score lands in its slot when its clip starts.

export const RANK_COLORS = { yellow: "#FFD60A", red: "#FF3D5A", blue: "#2E9BFF", green: "#4BE04B", white: "#FFFFFF", grey: "#C8C8C8" };
const MEDAL: Record<number, string> = { 1: "#FFD60A", 2: "#C9CDD4", 3: "#F28A2E" };

export type SplitWord = { text: string; color?: keyof typeof RANK_COLORS };
export type SplitItem = RankItem & { emoji?: string; objectPosition?: string };
export type RankingSplitProps = {
  width: number;
  height: number;
  fps: number;
  title: SplitWord[][];
  titleSize?: number; // px at 1080 wide
  teaser?: string;
  items: SplitItem[]; // play order (5..1)
  slots?: number;
  splitY?: number; // where the clip panel starts, px at 1080x1920
  rowH?: number;
  showSafeZone?: boolean;
};

export const rankingSplitDefaults: RankingSplitProps = { width: 1080, height: 1920, fps: 24, title: [[{ text: "Ranking", color: "yellow" }]], items: [] };
export const rankingSplitSeconds = (items: SplitItem[]) => rankingSeconds(items);

const outline = (k: number, w: number) => ({ WebkitTextStroke: `${w * k}px #000`, paintOrder: "stroke fill" as const });

export const RankingSplit: React.FC<RankingSplitProps> = ({ title, titleSize = 62, teaser, items, slots = 5, splitY = 880, rowH = 88, showSafeZone }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const k = width / 1080;
  const t = frame / fps;

  const starts: number[] = [];
  let acc = 0;
  for (const it of items) {
    starts.push(acc);
    acc += it.end - it.start;
  }
  const split = splitY * k;
  // Text sits in the top panel, above the platforms' right-hand action column (which starts lower),
  // so the title may use the full width between the left margin on both sides; the top margin stays.
  const top = SAFE_1080.top * k;
  const side = SAFE_1080.left * k;
  const listLeft = (SAFE_1080.left + 10) * k;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {items.map((it, i) => (
        <Sequence key={`v${i}`} from={Math.round(starts[i] * fps)} durationInFrames={Math.round((it.end - it.start) * fps)}>
          {/* top panel: zoomed, blurred copy of the clip */}
          <div style={{ position: "absolute", left: 0, top: 0, width, height: split, overflow: "hidden" }}>
            <OffthreadVideo src={staticFile(it.src)} startFrom={Math.round(it.start * fps)} muted
              style={{ position: "absolute", left: -0.15 * width, top: -0.1 * split, width: 1.3 * width, height: 1.3 * split, objectFit: "cover", filter: `blur(${26 * k}px) brightness(0.62)` }} />
          </div>
          {/* bottom panel: the clip */}
          <div style={{ position: "absolute", left: 0, top: split, width, height: height - split, overflow: "hidden" }}>
            <OffthreadVideo src={staticFile(it.src)} startFrom={Math.round(it.start * fps)} muted
              style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: it.objectPosition ?? "50% 65%" }} />
          </div>
        </Sequence>
      ))}

      {/* title */}
      <div style={{ position: "absolute", top, left: side, width: width - 2 * side, textAlign: "center", fontFamily, fontWeight: 800, lineHeight: 1.12 }}>
        {title.map((line, li) => (
          <div key={li} style={{ fontSize: titleSize * k, whiteSpace: "nowrap", ...outline(k, 9) }}>
            {line.map((w, wi) => (
              <span key={wi} style={{ color: RANK_COLORS[w.color ?? "white"] }}>
                {w.text}
                {wi < line.length - 1 ? " " : ""}
              </span>
            ))}
          </div>
        ))}
        {teaser ? <div style={{ marginTop: 6 * k, fontSize: 34 * k, fontWeight: 800, color: RANK_COLORS.green, ...outline(k, 6) }}>{teaser}</div> : null}
      </div>

      {/* list: fills the space between the title block and the split */}
      {Array.from({ length: slots }, (_, s) => s + 1).map((rank, row) => {
        const listTop = split - 24 * k - slots * rowH * k;
        const idx = items.findIndex((x) => x.rank === rank);
        const revealed = idx >= 0 && t >= starts[idx];
        const since = idx >= 0 ? (t - starts[idx]) * fps : 0;
        const pop = revealed ? interpolate(since, [0, 6], [0.5, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.back(2.4)) }) : 1;
        const it = idx >= 0 ? items[idx] : undefined;
        return (
          <div key={rank} style={{ position: "absolute", top: listTop + row * rowH * k, left: listLeft, height: rowH * k, display: "flex", alignItems: "center", whiteSpace: "nowrap" }}>
            <span style={{ fontFamily: italic.fontFamily, fontStyle: "italic", fontWeight: 800, fontSize: 60 * k, width: 92 * k, color: MEDAL[rank] ?? "#fff", ...outline(k, 8) }}>{rank}.</span>
            {revealed && it ? (
              <span style={{ display: "inline-block", transform: `scale(${pop})`, transformOrigin: "left center", fontFamily, fontWeight: 800, fontSize: 44 * k, color: "#fff", ...outline(k, 7) }}>
                {it.label}
                {it.emoji ? <span style={{ WebkitTextStroke: 0, marginLeft: 8 * k }}>{it.emoji}</span> : null}
                {it.score ? <span style={{ color: RANK_COLORS.grey, marginLeft: 16 * k }}>{it.score}</span> : null}
              </span>
            ) : null}
          </div>
        );
      })}

      {showSafeZone ? (
        <>
          <div style={{ position: "absolute", top: SAFE_1080.top * k, left: SAFE_1080.left * k, width: width - (SAFE_1080.left + SAFE_1080.right) * k, height: height - (SAFE_1080.top + SAFE_1080.bottom) * k, border: `${3 * k}px dashed #00ff66`, boxSizing: "border-box" }} />
          <div style={{ position: "absolute", top: split, left: 0, width, height: 3 * k, background: "#ff00ff" }} />
        </>
      ) : null}
    </AbsoluteFill>
  );
};
