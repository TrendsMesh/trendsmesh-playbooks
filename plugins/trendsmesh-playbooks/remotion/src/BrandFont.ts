import { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";

// The brand's own font (issue #117): a file in the run (the props' `brandFont`, written by tm organic captions and
// tm ad text from the brand's saved text set), loaded with the FontFace API before the frame is drawn. It replaces
// Montserrat in every text set but "native" (always TikTok Sans). The Google Fonts stack stays behind it, so a
// letter the brand's font lacks, or a file the browser cannot read, is drawn by the stack instead.
export type BrandFont = { family: string; src: string };

const loading = new Map<string, Promise<void>>();

const load = (font: BrandFont): Promise<void> => {
  const key = `${font.family}\u0000${font.src}`;
  let p = loading.get(key);
  if (!p) {
    const face = new FontFace(font.family, `url(${JSON.stringify(staticFile(font.src))})`);
    p = face
      .load()
      .then((f) => {
        document.fonts.add(f);
      })
      .catch((err) => console.warn(`The brand font ${font.src} could not be loaded; the default font draws it.`, err));
    loading.set(key, p);
  }
  return p;
};

// The CSS font-family stack: the brand's family first, then `fallback` (the composition's Google Fonts stack).
export const useBrandFont = (font: BrandFont | undefined, fallback: string): string => {
  const [handle] = useState(() => (font ? delayRender(`the brand font ${font.src}`) : null));
  useEffect(() => {
    if (!font || handle === null) return;
    load(font).then(() => continueRender(handle));
  }, [font, handle]);
  return font ? `${JSON.stringify(font.family)}, ${fallback}` : fallback;
};
