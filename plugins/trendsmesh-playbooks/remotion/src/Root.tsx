import { Composition } from "remotion";
import { HookSwap, HookSwapProps, hookSwapDefaults } from "./HookSwap";
import { WordCaptions, WordCaptionsProps, wordCaptionsDefaults } from "./WordCaptions";
import { OrganicCaptions, OrganicCaptionsProps, organicCaptionsDefaults, totalSeconds } from "./OrganicCaptions";
import { RankingList, RankingListProps, rankingListDefaults, rankingSeconds } from "./RankingList";
import { RankingSplit, RankingSplitProps, rankingSplitDefaults, rankingSplitSeconds } from "./RankingSplit";
import { QuizGrid, QuizGridProps, quizGridDefaults } from "./QuizGrid";

// Props come from a JSON file per run (--props), so every render is documented next to its assets.
export const RemotionRoot: React.FC = () => (
  <>
  <Composition
    id="HookSwap"
    component={HookSwap}
    width={720}
    height={1280}
    fps={30}
    durationInFrames={725}
    defaultProps={hookSwapDefaults}
    calculateMetadata={({ props }: { props: HookSwapProps }) => ({
      durationInFrames: Math.round(props.durationSec * 30),
      width: props.width,
      height: props.height,
    })}
  />
  <Composition
    id="WordCaptions"
    component={WordCaptions}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={806}
    defaultProps={wordCaptionsDefaults}
    calculateMetadata={({ props }: { props: WordCaptionsProps }) => ({
      durationInFrames: Math.round(props.durationSec * 30),
      width: props.width,
      height: props.height,
    })}
  />
  <Composition
    id="OrganicCaptions"
    component={OrganicCaptions}
    width={1080}
    height={1920}
    fps={24}
    durationInFrames={360}
    defaultProps={organicCaptionsDefaults}
    calculateMetadata={({ props }: { props: OrganicCaptionsProps }) => ({
      durationInFrames: Math.max(1, Math.round(totalSeconds(props.segments) * props.fps)),
      width: props.width,
      height: props.height,
      fps: props.fps,
    })}
  />
  <Composition
    id="RankingList"
    component={RankingList}
    width={1080}
    height={1920}
    fps={24}
    durationInFrames={504}
    defaultProps={rankingListDefaults}
    calculateMetadata={({ props }: { props: RankingListProps }) => ({
      durationInFrames: Math.max(1, Math.round(rankingSeconds(props.items) * props.fps)),
      width: props.width,
      height: props.height,
      fps: props.fps,
    })}
  />
  <Composition
    id="RankingSplit"
    component={RankingSplit}
    width={1080}
    height={1920}
    fps={24}
    durationInFrames={504}
    defaultProps={rankingSplitDefaults}
    calculateMetadata={({ props }: { props: RankingSplitProps }) => ({
      durationInFrames: Math.max(1, Math.round(rankingSplitSeconds(props.items) * props.fps)),
      width: props.width,
      height: props.height,
      fps: props.fps,
    })}
  />
  <Composition
    id="QuizGrid"
    component={QuizGrid}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={450}
    defaultProps={quizGridDefaults}
    calculateMetadata={({ props }: { props: QuizGridProps }) => ({
      durationInFrames: Math.round(props.durationSec * props.fps),
      width: props.width,
      height: props.height,
      fps: props.fps,
    })}
  />
  </>
);
