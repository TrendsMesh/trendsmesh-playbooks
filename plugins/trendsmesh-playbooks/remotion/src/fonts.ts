// The Google Fonts a composition loads for the market language (its `language` prop, BCP 47), from fonts.json:
// the subsets the language's script needs (always latin and latin-ext), in the composition's own font when it has
// them all; else the composition's font draws the letters it has and the script's fallback family the others, one
// CSS font-family stack. A font split in numbered chunks (CJK) loads only the chunks `tm render` names in the props'
// `fontSubsets`. engine/src/tm/video_fonts.py applies the same rule to check, before a render, that the fonts cover
// every letter on screen, and picks the chunks. Keep the two in step.
import { getInputProps } from "remotion";
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

// The families a composition whose own font is `primary` draws with, in CSS order, each with the subsets it loads:
// the font alone when it has every subset the script needs; else the font with those of them it has (latin and
// latin-ext at least), then the script's fallback with the rest, so the composition's font draws every letter it
// has and the fallback only the others (issue 3).
export const stackFor = (primary: string, language?: string): { family: string; subsets: string[] }[] => {
  const spec = T.scripts[scriptOf(language)];
  const own = T.families[primary].subsets;
  const have = spec.subsets.filter((s) => own.includes(s));
  const rest = spec.subsets.filter((s) => !own.includes(s));
  if (rest.length === 0) return [{ family: primary, subsets: spec.subsets }];
  return [{ family: primary, subsets: have }, { family: spec.fallback, subsets: rest }];
};

// The composition's own font family in fonts.json (`key` picks one of WordCaptions' caption fonts).
export const compFont = (comp: string, key?: string): string => {
  const named = T.compositions[comp];
  if (typeof named === "string") return named;
  return (key !== undefined ? named[key] : undefined) ?? Object.values(named)[0];
};

// The subsets `tm render` names for a family (the props' `fontSubsets`): for a font split in numbered chunks (CJK),
// only the chunks the on-screen text needs, so a still does not fetch every chunk of every weight.
const named = (family: string): string[] | undefined => {
  const given = (getInputProps() as { fontSubsets?: Record<string, unknown> }).fontSubsets?.[family];
  return Array.isArray(given) ? (given as string[]) : undefined;
};

// Loads the weights of the families drawn with and returns their CSS font-family stack. Loading is cached per font
// file, so calling this on every frame is cheap. An italic a family lacks is drawn from its normal face.
export const loadFor = (primary: string, language: string | undefined, weights: string[], style: "normal" | "italic" = "normal"): string => {
  const out: string[] = [];
  for (const { family, subsets } of stackFor(primary, language)) {
    const load = named(family) ?? subsets;
    if (load.length === 0) continue;                     // the text needs none of its letters
    const face = style === "italic" && !T.families[family].italic ? "normal" : style;
    out.push(JSON.stringify(LOADERS[family](face, { weights, subsets: load }).fontFamily));
  }
  return out.join(", ");
};
