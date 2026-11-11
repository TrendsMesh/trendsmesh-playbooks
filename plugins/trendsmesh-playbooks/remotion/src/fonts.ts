// The Google Fonts a composition loads for the market language (its `language` prop, BCP 47), from fonts.json:
// the subsets the language's script needs (always latin and latin-ext), in the composition's own font when it has
// them all, else in the script's fallback family for the whole composition. engine/src/tm/video_fonts.py applies
// the same rule to check, before a render, that the font covers every letter on screen. Keep the two in step.
import { loadFont as BebasNeue } from "@remotion/google-fonts/BebasNeue";
import { loadFont as Nunito } from "@remotion/google-fonts/Nunito";
import { loadFont as Baloo2 } from "@remotion/google-fonts/Baloo2";
import { loadFont as Fredoka } from "@remotion/google-fonts/Fredoka";
import { loadFont as Montserrat } from "@remotion/google-fonts/Montserrat";
import { loadFont as Poppins } from "@remotion/google-fonts/Poppins";
import { loadFont as NotoSans } from "@remotion/google-fonts/NotoSans";
import { loadFont as NotoSansArabic } from "@remotion/google-fonts/NotoSansArabic";
import { loadFont as NotoSansHebrew } from "@remotion/google-fonts/NotoSansHebrew";
import { loadFont as NotoSansThai } from "@remotion/google-fonts/NotoSansThai";
import { loadFont as NotoSansJP } from "@remotion/google-fonts/NotoSansJP";
import { loadFont as NotoSansKR } from "@remotion/google-fonts/NotoSansKR";
import { loadFont as NotoSansSC } from "@remotion/google-fonts/NotoSansSC";
import { loadFont as NotoSansTC } from "@remotion/google-fonts/NotoSansTC";
import table from "./fonts.json";

type Loader = (style: string, options: { weights: string[]; subsets: string[] }) => { fontFamily: string };
const LOADERS: Record<string, Loader> = {
  BebasNeue, Nunito, Baloo2, Fredoka, Montserrat, Poppins, NotoSans, NotoSansArabic, NotoSansHebrew, NotoSansThai,
  NotoSansJP, NotoSansKR, NotoSansSC, NotoSansTC,
} as unknown as Record<string, Loader>;

type Table = {
  compositions: Record<string, string | Record<string, string>>;
  families: Record<string, { subsets: string[]; italic: boolean }>;
  scripts: Record<string, { subsets: string[]; fallback: string }>;
  languages: Record<string, string>;
};
const T = table as unknown as Table;

// The script a language is written in, by its longest prefix in the table (zh-hant-tw, zh-hant, zh); latin when unknown.
export const scriptOf = (language?: string): string => {
  const parts = (language ?? "").trim().replace(/_/g, "-").toLowerCase().split("-").filter(Boolean);
  for (let n = parts.length; n > 0; n--) {
    const hit = T.languages[parts.slice(0, n).join("-")];
    if (hit) return hit;
  }
  return "latin";
};

// The family and subsets a composition whose own font is `primary` uses for the language.
export const pickFamily = (primary: string, language?: string): { family: string; subsets: string[] } => {
  const spec = T.scripts[scriptOf(language)];
  const own = T.families[primary].subsets;
  const family = spec.subsets.every((s) => own.includes(s)) ? primary : spec.fallback;
  return { family, subsets: spec.subsets };
};

// The composition's own font family in fonts.json (`key` picks one of WordCaptions' caption fonts).
export const compFont = (comp: string, key?: string): string => {
  const named = T.compositions[comp];
  if (typeof named === "string") return named;
  return (key !== undefined ? named[key] : undefined) ?? Object.values(named)[0];
};

// Loads the weights of the picked family and returns its CSS font-family. Loading is cached per font file, so
// calling this on every frame is cheap. An italic the picked family lacks is drawn from its normal face.
export const loadFor = (primary: string, language: string | undefined, weights: string[], style: "normal" | "italic" = "normal"): string => {
  const { family, subsets } = pickFamily(primary, language);
  const face = style === "italic" && !T.families[family].italic ? "normal" : style;
  return LOADERS[family](face, { weights, subsets }).fontFamily;
};
