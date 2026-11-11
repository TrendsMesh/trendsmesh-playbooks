"""A synthetic 9:16 ad with four kinds of on-screen text, rendered frame by frame (issue #29).

Generated in the test with OpenCV's built-in Hershey fonts and piped to ffmpeg, never committed.
Over a moving, textured picture (a window panning over blurred noise, so the background never
holds still), at 540x960 and 25 fps, 7 s long:

- a two-line hook caption at the top: line 1 from 0.0 to 2.4 s; line 2, on a semi-transparent red
  bar, from 0.6 to 2.0 s (the lines come and go at different moments and differ in style);
- a second top caption from 3.0 to 4.6 s;
- word-by-word captions at the bottom centre, one word at a time while it is spoken, from 0.2 s
  to 5.8 s (WORDS; the matching transcript is `transcript()`);
- a cut to a full-frame end card (flat colour, two lines of text) for the last 1.2 s.

`box(part)` is what a part covers on screen, measured from its own pixels (x0, y0, x1, y1 in
source pixels, x1 and y1 exclusive).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from _media import ffmpeg

W, H, FPS, SECONDS = 540, 960, 25, 7.0
FONT_SCALE, THICK = 1.4, 3

HOOK = [("STOP SCROLLING", 110, 0.0, 2.4), ("THIS IS NEW", 190, 0.6, 2.0)]  # text, baseline, on, off
TOP2 = ("ONLY TODAY", 150, 3.0, 4.6)
END_CARD_S = 5.8
END_LINES = [("SHOP NOW", 420), ("LINK BELOW", 520)]
CAPTION_Y = 780
WORDS = [("we", 0.2, 0.5), ("made", 0.5, 0.9), ("this", 0.9, 1.2), ("for", 1.2, 1.5),
         ("you", 1.5, 1.9), ("and", 2.2, 2.5), ("your", 2.5, 2.9), ("dog", 2.9, 3.4),
         ("try", 3.6, 3.9), ("it", 3.9, 4.2), ("free", 4.2, 4.7), ("today", 4.7, 5.2),
         ("enjoy", 5.3, 5.8)]


def transcript() -> dict:
    return {"language": "en", "segments": [
        {"start": WORDS[0][1], "end": WORDS[-1][2], "text": " ".join(w for w, _, _ in WORDS),
         "words": [{"word": w, "start": s, "end": e, "probability": 0.95} for w, s, e in WORDS]}]}


def _text(img, text: str, baseline: int, colour=(255, 255, 255)) -> None:
    import cv2

    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, FONT_SCALE, THICK)
    x = (W - tw) // 2
    cv2.putText(img, text, (x, baseline), cv2.FONT_HERSHEY_DUPLEX, FONT_SCALE, (0, 0, 0), THICK + 4, cv2.LINE_AA)
    cv2.putText(img, text, (x, baseline), cv2.FONT_HERSHEY_DUPLEX, FONT_SCALE, colour, THICK, cv2.LINE_AA)


def _bar(img, text: str, baseline: int, alpha: float = 0.55) -> None:
    import cv2

    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, FONT_SCALE, THICK)
    x0, y0, x1, y1 = (W - tw) // 2 - 16, baseline - th - 14, (W + tw) // 2 + 16, baseline + base + 10
    region = img[y0:y1, x0:x1]
    red = region.copy()
    red[:] = (30, 30, 220)
    img[y0:y1, x0:x1] = cv2.addWeighted(red, alpha, region, 1 - alpha, 0)


def _parts(img, t: float, parts: set) -> None:
    for i, (text, y, on, off) in enumerate(HOOK):
        if "hook" in parts and on <= t < off:
            if i == 1:
                _bar(img, text, y)
            _text(img, text, y)
    text, y, on, off = TOP2
    if "top2" in parts and on <= t < off:
        _text(img, text, y, (0, 255, 255))
    if "words" in parts:
        for w, s, e in WORDS:
            if s <= t < e:
                _text(img, w, CAPTION_Y)


def box(part: str) -> tuple[int, int, int, int]:
    """The pixels a part ever covers, measured by drawing it alone on black and white frames."""
    import numpy as np

    if part == "end_card":
        times = [END_CARD_S]
    else:
        times = [i / FPS for i in range(round(END_CARD_S * FPS))]
    seen = np.zeros((H, W), bool)
    for t in times:
        for fill in (0, 255):
            img = np.full((H, W, 3), fill, np.uint8)
            if part == "end_card":
                for text, y in END_LINES:
                    _text(img, text, y)
            else:
                _parts(img, t, {part})
            seen |= (np.abs(img.astype(np.int16) - fill) > 8).any(axis=2)
    ys, xs = np.nonzero(seen)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def frame(i: int, field, parts: set, pan: float = 1.0):
    t = i / FPS
    if "end_card" in parts and t >= END_CARD_S:
        img = field[:H, :W].copy()
        img[:] = (40, 90, 200)
        for text, y in END_LINES:
            _text(img, text, y)
        return img
    x, y = int(40 + 60 * pan * t), int(30 + 25 * pan * t)  # the camera pans over the texture
    img = field[y:y + H, x:x + W].copy()
    _parts(img, t, parts)
    return img


def make_ad(path: Path, parts: tuple[str, ...] = ("hook", "top2", "words", "end_card"), pan: float = 1.0) -> Path:
    """The ad; `pan` 0 holds the picture still (text over a still, textured photo)."""
    import cv2
    import numpy as np

    rng = np.random.default_rng(29)
    field = rng.integers(0, 255, (H + 400, W + 600, 3), dtype=np.uint8)
    field = cv2.normalize(cv2.GaussianBlur(field, (0, 0), 6), None, 30, 220, cv2.NORM_MINMAX)
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "18", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for i in range(round(SECONDS * FPS)):
        proc.stdin.write(frame(i, field, set(parts), pan).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg could not encode the synthetic ad")
    return path
