"""Teardown of the original ad (step A3): scenes, frames, overlays, transcript and material keys.

    tm tool teardown --run RUN VIDEO [--transcript T.json | --no-transcribe] [--every-s 1.0]
                     [--model large-v3-turbo] [--lang pl] [--out PATH] [--json]

Writes 02_research/teardown_vNN.json, its frames to 02_research/teardown_vNN_frames/, the check sheet
02_research/teardown_vNN_check.png (when anything is to check) and (unless a transcript is given)
02_research/transcript_vNN.json. The JSON carries the keys
`changes.classify_material` reads: is_video, has_speech, speech_on_camera, overlays.

Every frame is decoded by ffmpeg into memory (never cv2.VideoCapture), so paths with spaces and
non-ASCII names work on every system. Analysis runs on frames scaled to ANALYSIS_W wide (about
400 MB for a 30 s ad at 30 fps; longer videos are analysed smaller, within MAX_ANALYSIS_BYTES).

Scenes: PySceneDetect's ContentDetector, fed those frames.

Overlays (lesson 12), with edge detection and temporal differences, never colour thresholds:
1. Canny edges per frame (dilated by a pixel). An edge pixel is *stable* when it is an edge in
   every frame of a centred window of about 0.2 s, kept inside the scene; slow camera moves and
   zooms drift out of it.
   A box that appears at frame f is stable from f + half a window, so times are shifted back.
2. Background: edges stable in the shot's first and last 0.2 s, with the pixel looking the same in
   both (an overlay over texture keeps edges, not the look), so only an overlay spanning the whole
   shot is lost; a card-like block of such edges is reported as a note ("Possible overlay
   spanning the whole shot ... check the frames") and in `possible_whole_shot_overlays`. Scenes
   joined by a cut that keeps most edges (a jump cut) count as one shot. Stable edges that carry
   across a real cut are never background: the picture changed under them, so they are on top.
3. What is stable and not background is overlay material. Per pixel, its longest run of material
   frames (short gaps bridged; across a real cut only for pixels that carry across, same look);
   runs under MIN_S are dropped. Pixels whose runs start together and
   end together (within half a window) form one group, closed into blobs; a blob counts only when
   at least COHERENT of the long-run pixels in its box start, or end, with its group (texture and
   moving scenes switch at scattered times; a slide-in starts staggered but ends together) and
   its pixels hardly change while it is on (STILL_DIFF: a slow zoom keeps edges, not pixels).
   Aligned blobs of one group join (the top and bottom edges of a box).
   Then pieces of one overlay merge (same start or end, nested), background the overlay covered or
   revealed is dropped, and the pieces of a slide (one ends as the next comes in, same band) merge.
4. Entry and exit: long lines of short-lived material continuing the box's own edge lines in the
   frames around its start or end (a card sliding in) widen the box; and while the frames just
   before the start (or after the end) change inside the box much more than around it (temporal
   differences), that is the entry (or exit) animation and counts as part of its life cycle.
5. `bbox` is the union over the whole life cycle, in source pixels (x0, y0, x1, y1; x1 and y1
   exclusive). `touches_edge` is true when it comes within EDGE_PX (24 px) of a frame edge.
6. `semi_transparent`: inside the box (shrunk by a fifth) the background shows through: either
   its gradients correlate with the frame before the overlay (r >= 0.5, at 15 % of the strength or
   more), or, over a moving background, the box changes at 15 to 95 % of the rate around it.
Limits: an overlay that lasts a whole shot (with no real cut) looks like background: it is not
listed as an overlay, only noted when its edges look like a card; a static logo across jump cuts
likewise. Thresholds are heuristics tuned on synthetic clips only; Claude checks the frames and can
override the material with `tm material`.

Text (issue #29; `_text_overlays` has the method): steps 1-6 need an edge to hold still for a
window, so word-by-word captions, which change every few tenths of a second, never reach them, and
the lines of one caption that come and go at different moments stay apart. A second pass looks for
text lines in frames every 0.1 s, joins stacked lines into one block, follows each block over
time as one track (a caption band whose words change is one overlay with one start and end), and
compares the moments its text changes with the transcript's word starts. Each overlay then has:
- `kind`: `word_captions` (text that changes word by word), `text` (a caption or card with text),
  `full_frame` (a still scene with text: an end card or full-frame title; its box is the text's)
  or `graphic` (found by edges only, no text line in it: a bar, a shape, or a false find);
- `methods` (`edges`, `text`), `confidence` (0 to 1) and `check`: why to look at its frames, or
  null; `spans_s`: when its text is on screen ([start, end] pairs; gaps between words show);
- `transcript` (text overlays, with a transcript): how many changes land on word starts against
  chance, and `aligned`, true for word-by-word captioning.
Text and edge boxes that overlap in space and time are one overlay (the box is their union, so a
caption's bar or frame is kept). `check_frames` lists bands whose picture changes with the spoken
words where no text line was found (captions in a font the pass misses, maybe): look there.

Limits of the text pass (`TEXT_LIMITS`, in the JSON's `check_sheet.limits`): it finds text lines, it does not read
them (no OCR), so it cannot compare the words on screen with the transcript, it may miss stylised or thin fonts,
and a still shot with text in the picture (a product label) can come out as `full_frame`. The edge method's
leftover false finds are `graphic` with a `check`, flagged, never trusted.

The check sheet (issue 57), where the agent's look starts: one row per item the tool is unsure of, each with its
box drawn in red on its first, middle and last frame (`check_items`, `check_sheet`): the overlays with a `check`,
least sure first, then the `check_frames` bands, then the `possible_whole_shot_overlays`. The JSON's
`check_sheet.rows` says what each row is (row 1 at the top); null when there is nothing to check. At most
MAX_SHEET_ROWS rows; past them, the rest are listed in `check_sheet.left_out`.

speech_on_camera (VARIANTS 1 and 4 V0): OpenCV's bundled Haar frontal-face detector on frames
sampled in the speech segments; true when a face at least FACE_MIN_W of the frame width is found in
FACE_SHARE (half) of them or more. Limits: profiles, small or partly covered faces are missed, and
a silent person on screen while a voiceover speaks counts as on camera.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

from tm.tools import _common as c
from tm.tools import _text_overlays as tx

ANALYSIS_W = 270
MAX_ANALYSIS_BYTES = 1.2e9
EDGE_PX = 24
STABLE_S = 0.2
MIN_S = 0.3
MAX_ANIMATION_S = 1.0
JUMP_CUT_KEEP = 0.3
BACKGROUND_SHARE = 0.6
BACKGROUND_LOOK = 20
JOIN_FRAC = 0.2
TRAIL_FRAC = 0.06
COHERENT = 0.35
STILL_DIFF = 4.0
FACE_MIN_W = 0.15
FACE_SHARE = 0.5
MAX_FACE_SAMPLES = 40
SHEET_TILE_W = 240     # the check sheet's tile width (three tiles a row)
MAX_SHEET_ROWS = 12
TEXT_LIMITS = (
    "No OCR: the text pass finds text lines but does not read them, so the words on screen are never compared "
    "with the transcript.",
    "Stylised or thin fonts may be missed (a band that changes with the spoken words is listed in check_frames).",
    "A still shot with text in the picture (a product label) can be reported as full_frame.",
    "The edge method's leftover false finds come out as graphic with confidence 0.4 and a check: flagged, never "
    "trusted.",
)


@dataclass(frozen=True)
class Overlay:
    start_frame: int
    end_frame: int
    bbox: tuple[int, int, int, int]
    touches_edge: bool
    semi_transparent: bool
    kind: str = "graphic"
    confidence: float = 0.5
    methods: tuple[str, ...] = ("edges",)
    check: str | None = None
    spans: tuple[tuple[int, int], ...] = ()
    transcript: dict | None = None


# Decoding and scenes -------------------------------------------------------------------------

def _analysis_size(width: int, height: int, frames: int = 0) -> tuple[float, int, int]:
    """Frames scaled to ANALYSIS_W wide, smaller still for long videos so the four per-frame
    arrays (gray, edges, stable, material) stay under MAX_ANALYSIS_BYTES."""
    scale = min(1.0, ANALYSIS_W / width)
    if frames:
        scale = min(scale, math.sqrt(MAX_ANALYSIS_BYTES / (4 * frames * width * height)))
    return scale, max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2)


class _Clip:
    """The video decoded once: gray analysis frames and the scene cuts (frame numbers)."""

    def __init__(self, video: Path | str):
        import cv2
        import numpy as np
        from scenedetect import FrameTimecode
        from scenedetect.detectors import ContentDetector

        self.info = c.probe(video)
        if not self.info.get("is_video"):
            raise c.ToolError(f"{Path(video).name} is not a video.")
        self.fps = self.info["fps"]
        if not self.fps or self.fps <= 0:
            raise c.ToolError(f"The frame rate of {Path(video).name} is unknown, so it cannot be analysed.")
        self.scale, w, h = _analysis_size(self.info["width"], self.info["height"], self.info["frames"])
        self.sx, self.sy = self.info["width"] / w, self.info["height"] / h
        detector = ContentDetector()
        grays, cuts = [], []
        for i, bgr in enumerate(c.decode(video, w, h, "bgr24")):
            cuts += [int(tc.frame_num) for tc in detector.process_frame(FrameTimecode(i, fps=self.fps), bgr)]
            grays.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
        if not grays:
            raise c.ToolError(f"No frames could be decoded from {Path(video).name}.")
        self.gray = np.stack(grays)
        self.cuts = sorted({f for f in cuts if 0 < f < len(grays)})

    @property
    def frames(self) -> int:
        return len(self.gray)

    def scene_frames(self) -> list[tuple[int, int]]:
        """[(first, last)] frame numbers, last inclusive."""
        bounds = [0, *self.cuts, self.frames]
        return [(a, b - 1) for a, b in zip(bounds, bounds[1:])]


def _seconds(frame: int, fps: float) -> float:
    return round(frame / fps, 3)


def scenes(video: Path | str) -> list[tuple[float, float]]:
    """[(start_s, end_s)] per shot (PySceneDetect ContentDetector)."""
    clip = _Clip(video)
    return [(_seconds(a, clip.fps), _seconds(b + 1, clip.fps)) for a, b in clip.scene_frames()]


def frames(video: Path | str, out_dir: Path | str, every_s: float) -> list[tuple[Path, float]]:
    """Full-size PNG stills every `every_s` seconds, from 0: [(path, t)]."""
    if every_s <= 0:
        raise ValueError("every_s must be above 0.")
    info = c.probe(video)
    duration = info.get("duration") or 0
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = []
    for i in range(max(1, math.ceil(duration / every_s - 1e-6))):
        t = round(i * every_s, 3)
        path = out / f"frame_{i + 1:04d}_{t:08.3f}s.png"
        c.run_ffmpeg(["-ss", f"{t:.3f}", "-i", c.media(video), "-frames:v", "1", c.media(path)])
        if path.is_file():
            result.append((path, t))
    return result


# Overlays ------------------------------------------------------------------------------------

def _stable_edges(gray, fps: float, scenes_: list[tuple[int, int]]):
    """Edges present in every frame of a centred window that stays inside its scene."""
    import cv2
    import numpy as np

    kernel = np.ones((3, 3), np.uint8)
    edges = np.empty(gray.shape, bool)
    for t in range(len(gray)):
        edges[t] = cv2.dilate(cv2.Canny(cv2.GaussianBlur(gray[t], (3, 3), 0), 20, 60), kernel) > 0
    half = max(1, round(fps * STABLE_S) // 2)
    stable = np.zeros_like(edges)
    for a, b in scenes_:
        count = edges[a: min(b, a + half) + 1].sum(axis=0, dtype=np.int16)
        for t in range(a, b + 1):
            if t > a:
                if t + half <= b:
                    count += edges[t + half]
                if t - half - 1 >= a:
                    count -= edges[t - half - 1]
            stable[t] = count >= min(t + half, b) - max(t - half, a) + 1  # an edge in every frame
    return stable, half


def _shots(stable, scenes_: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Scenes joined across jump cuts (a cut that keeps most stable edges): [(first, last)]."""
    shots = [list(scenes_[0])]
    for a, b in scenes_[1:]:
        before, after = stable[a - 1], stable[a]
        kept = (before & after).sum() / max(1, before.sum())
        if kept >= JUMP_CUT_KEEP:
            shots[-1][1] = b
        else:
            shots.append([a, b])
    return [tuple(x) for x in shots]


def _persists(gray, stable, cut: int):
    """Pixels that carry across the cut before frame `cut`: an edge on both sides, same look."""
    import numpy as np

    look = np.abs(gray[cut - 1].astype(np.int16) - gray[cut]) <= BACKGROUND_LOOK
    return stable[cut - 1] & stable[cut] & look


def _overlay_material(gray, stable, shots: list[tuple[int, int]], half: int):
    """Stable edges minus each shot's background (see the module docstring, step 2).
    Returns (material, [(first, last, background mask)] per shot)."""
    import numpy as np

    material = stable.copy()
    backgrounds = []
    for i, (a, b) in enumerate(shots):
        edge = max(1, min(2 * half + 1, (b - a + 1) // 2))  # the shot's first and last 0.2 s
        head, tail = slice(a, a + edge), slice(b + 1 - edge, b + 1)
        same_look = np.abs(gray[head].mean(axis=0) - gray[tail].mean(axis=0)) <= BACKGROUND_LOOK
        background = (stable[head].mean(axis=0) >= BACKGROUND_SHARE) & \
                     (stable[tail].mean(axis=0) >= BACKGROUND_SHARE) & same_look
        if i > 0:  # carried across the real cut into this shot: on top of the picture
            background &= ~_persists(gray, stable, a)
        if i < len(shots) - 1:
            background &= ~_persists(gray, stable, b + 1)
        material[a: b + 1] &= ~background
        backgrounds.append((a, b, background))
    return material, backgrounds


def _whole_shot_suspects(backgrounds, close: int) -> list[dict]:
    """Compact, box-like blocks of background edges: maybe an overlay that spans the whole shot
    (which the background rule cannot tell from the picture). A block counts when it is 0.5 to
    50 % of the frame (and at least 5 % of its width), holds at least half an outline of edges and
    has two long horizontal edges a third of its height apart or more (a card's top and bottom).
    At most 3 per shot, the largest first. Reported as notes for Claude to check, never as
    overlays."""
    import cv2
    import numpy as np

    out = []
    for a, b, background in backgrounds:
        h, w = background.shape
        m = cv2.morphologyEx(background.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        found = []
        for i in range(1, n):
            x, y, bw, bh = (int(v) for v in stats[i][:4])
            if not 0.005 * w * h <= bw * bh <= 0.5 * w * h:
                continue
            block = background[y:y + bh, x:x + bw]
            if block.sum() < bw + bh:  # not even half an outline of edges
                continue
            full = np.nonzero(block.mean(axis=1) >= 0.6)[0]  # rows the edges cross nearly fully
            if bw >= 0.05 * w and bh >= 4 and full.size and full.max() - full.min() >= max(4, bh // 3):
                found.append((int(block.sum()), {"first": a, "last": b, "box": (x, y, x + bw, y + bh)}))
        out += [f for _, f in sorted(found, key=lambda t: -t[0])[:3]]
    return out


def _runs(material, gap: int, cuts: dict):
    """Per pixel, the longest run of material frames (gaps up to `gap` frames bridged; at a real
    cut only the pixels in `cuts[frame]` carry on): (first, last, length) arrays."""
    import numpy as np

    shape = material.shape[1:]
    cur_s = np.full(shape, -1, np.int32)
    cur_last = np.full(shape, -(10 ** 6), np.int32)
    best_s = np.zeros(shape, np.int32)
    best_e = np.zeros(shape, np.int32)
    best_len = np.zeros(shape, np.int32)
    for t in range(len(material)):
        if t in cuts:
            cur_last[~cuts[t]] = -(10 ** 6)
        on = material[t]
        new = on & (t - cur_last > gap + 1)
        cur_s[new] = t
        cur_last[on] = t
        length = t - cur_s + 1
        better = on & (length > best_len)
        best_len[better] = length[better]
        best_s[better] = cur_s[better]
        best_e[better] = t
    return best_s, best_e, best_len


def _gap(a, b) -> tuple[int, int, int, int]:
    """(x overlap, y overlap, x gap, y gap) of two boxes; overlaps negative when apart."""
    xo = min(a[2], b[2]) - max(a[0], b[0])
    yo = min(a[3], b[3]) - max(a[1], b[1])
    return xo, yo, max(0, -xo), max(0, -yo)


def _join_lines(boxes: list, w: int, h: int) -> list:
    """Join parts of one overlay that the time grouping keeps apart: the top and bottom edges of
    a box (aligned, close), or side by side pieces of a broken outline."""
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                xo, yo, xg, yg = _gap(a, b)
                narrow_w = min(a[2] - a[0], b[2] - b[0])
                narrow_h = min(a[3] - a[1], b[3] - b[1])
                stacked = xo >= 0.7 * narrow_w and yg <= JOIN_FRAC * h
                side = yo >= 0.7 * narrow_h and xg <= JOIN_FRAC * w
                if stacked or side or (xo > 0 and yo > 0):
                    boxes[i] = _union(a, b)
                    del boxes[j]
                    changed = True
                    break
            if changed:
                break
    return boxes


def _still(gray, sel, box, first: int, last: int) -> bool:
    """The group's pixels hardly change while it is on screen (an overlay does not move; a slow
    zoom over texture keeps edges in place yet changes every pixel)."""
    import numpy as np

    x0, y0, x1, y1 = box
    mask = sel[y0:y1, x0:x1]
    frames = range(first + 1, last + 1, max(1, (last - first) // 20))
    diffs = [np.abs(gray[t, y0:y1, x0:x1].astype(np.int16) - gray[t - 1, y0:y1, x0:x1])[mask].mean()
             for t in frames]
    return not diffs or float(np.mean(diffs)) <= STILL_DIFF


def _groups(gray, best_s, best_e, cand, tol: int, close: int, min_px: int, min_area: int) -> list[dict]:
    """Material pixels that switched on together and off together, as boxes (step 3)."""
    import cv2
    import numpy as np

    h, w = cand.shape
    remaining = cand.copy()
    out = []
    span = int(best_e.max()) + 2
    while remaining.sum() >= min_px:
        keys, counts = np.unique(best_s[remaining] * span + best_e[remaining], return_counts=True)
        s0, e0 = divmod(int(keys[np.argmax(counts)]), span)
        sel = remaining & (np.abs(best_s - s0) <= tol) & (np.abs(best_e - e0) <= tol)
        remaining &= ~sel
        if sel.sum() < min_px:
            break
        m = cv2.morphologyEx(sel.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        same_start = cand & (np.abs(best_s - s0) <= tol)
        same_end = cand & (np.abs(best_e - e0) <= tol)

        def coherent(b) -> bool:  # most long-run pixels in the box start, or end, with this group
            total = cand[b[1]:b[3], b[0]:b[2]].sum()
            together = max(same_start[b[1]:b[3], b[0]:b[2]].sum(), same_end[b[1]:b[3], b[0]:b[2]].sum())
            return together >= COHERENT * total

        parts = []
        for i in range(1, n):
            px = int((sel & (labels == i)).sum())
            x, y, bw, bh = (int(v) for v in stats[i][:4])
            if px >= 8 and coherent((x, y, x + bw, y + bh)) and _still(gray, sel, (x, y, x + bw, y + bh), s0, e0):
                parts.append((x, y, x + bw, y + bh))
        for box in _join_lines(parts, w, h):
            x0, y0, x1, y1 = box
            px = int(sel[y0:y1, x0:x1].sum())
            if px >= min_px and (x1 - x0) * (y1 - y0) >= min_area and coherent(box):
                inside = sel[y0:y1, x0:x1]
                out.append({"first": int(np.median(best_s[y0:y1, x0:x1][inside])),
                            "last": int(np.median(best_e[y0:y1, x0:x1][inside])), "box": box})
    return out


def _area(r) -> int:
    return (r[2] - r[0]) * (r[3] - r[1])


def _relate(a: dict, b: dict, tol: int, span: int, w: int, h: int, step: str) -> str | None:
    """How two pieces relate (a starts no later than b): "merge", "drop_a", "drop_b" or None.

    - the same overlay: touching or nested boxes with the same start or the same end (the other
      end within the animation span), or nested within the other's time;
    - a slide: a piece that ends while the other is coming in (or starts while it goes out),
      beside it in the same band;
    - occluded or revealed background: a piece inside the other's box that ends while the other
      comes in (or starts while it goes out) is background the overlay covers, not an overlay.
    """
    xo, yo, xg, yg = _gap(a["box"], b["box"])
    near = xg <= JOIN_FRAC * w and yg <= JOIN_FRAC * h and (xo > 0 or yo > 0)
    same_end = abs(a["last"] - b["last"]) <= tol and abs(a["first"] - b["first"]) <= span
    same_start = abs(a["first"] - b["first"]) <= tol and abs(a["last"] - b["last"]) <= span
    within = (b["first"] >= a["first"] - tol and b["last"] <= a["last"] + tol) or \
             (a["first"] >= b["first"] - tol and a["last"] <= b["last"] + tol)
    nested = _overlap(a["box"], b["box"]) >= 0.8
    a_ends_as_b_enters = b["first"] - tol <= a["last"] <= b["first"] + span
    b_starts_as_a_leaves = a["last"] - span <= b["first"] <= a["last"] + tol
    if step == "same":
        same = (near and (same_end or same_start)) or (nested and (same_end or same_start or within))
        return "merge" if same else None
    if step == "covered":
        if a_ends_as_b_enters and nested and _area(a["box"]) <= _area(b["box"]):
            return "drop_a"
        if b_starts_as_a_leaves and nested and _area(b["box"]) <= _area(a["box"]):
            return "drop_b"
        return None
    ha, hb = a["box"][3] - a["box"][1], b["box"][3] - b["box"][1]
    wa, wb = a["box"][2] - a["box"][0], b["box"][2] - b["box"][0]
    across = (yo >= 0.7 * max(ha, hb) and min(ha, hb) >= 0.7 * max(ha, hb)) or \
             (xo >= 0.7 * max(wa, wb) and min(wa, wb) >= 0.7 * max(wa, wb))  # same height (or width)
    return "merge" if near and across and (a_ends_as_b_enters or b_starts_as_a_leaves) else None


def _merge_animated(items: list[dict], tol: int, span: int, w: int, h: int) -> list[dict]:
    """Join the pieces of one overlay and drop covered background (see `_relate`), in that
    order: pieces of the same overlay first, then covered background, then slides."""
    for step in ("same", "covered", "slide"):
        items = _merge_step(items, tol, span, w, h, step)
    return items


def _merge_step(items: list[dict], tol: int, span: int, w: int, h: int, step: str) -> list[dict]:
    items = sorted(items, key=lambda it: it["first"])
    changed = True
    while changed:
        changed = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                how = _relate(a, b, tol, span, w, h, step)
                if how is None:
                    continue
                if how == "merge":
                    items[i] = {"first": min(a["first"], b["first"]), "last": max(a["last"], b["last"]),
                                "box": _union(a["box"], b["box"])}
                    del items[j]
                elif how == "drop_a":
                    del items[i]
                else:
                    del items[j]
                changed = True
                break
            if changed:
                break
    return items


def _overlap(a, b) -> float:
    xo, yo, _, _ = _gap(a, b)
    if xo <= 0 or yo <= 0:
        return 0.0
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])  # noqa: E731
    return xo * yo / min(area(a), area(b))


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _reach(line, start: int, step: int, gap: int) -> int:
    """From index `start`, walk in `step` direction while `line` stays on (gaps up to `gap`)."""
    i, last_on, n = start, start - step, len(line)
    while 0 <= i < n and abs(i - last_on) <= gap + 1:
        if line[i]:
            last_on = i
        i += step
    return last_on


def _long_runs(line, transient, min_len: int):
    """The runs of True at least `min_len` long and mostly transient (short-lived material)."""
    import numpy as np

    out = np.zeros_like(line)
    i, n = 0, len(line)
    while i < n:
        if line[i]:
            j = i
            while j < n and line[j]:
                j += 1
            if j - i >= min_len and transient[i:j].mean() >= 0.5:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def _trail(material, transient, item: dict, span: int, half: int):
    """Entry and exit trails (step 4): a card sliding in from an edge leaves its top and bottom
    edges as long lines of short-lived overlay material along the rows of the box's own
    horizontal edges (a vertical slide: the columns of its vertical edges) in the frames before
    it settles or after it leaves. Those lines, followed from the box outwards, widen the box."""
    import numpy as np

    x0, y0, x1, y1 = item["box"]
    t_count = len(material)
    h, w = material.shape[1:]
    min_x, min_y = max(8, round(TRAIL_FRAC * w)), max(8, round(TRAIL_FRAC * h))
    own = material[item["first"]: item["last"] + 1, y0:y1, x0:x1].mean(axis=0) >= 0.5
    # the box's own edge lines: rows (columns) its material covers far more than the others
    by_row, by_col = own.mean(axis=1), own.mean(axis=0)
    rows_at = [y0 + int(i) for i in np.nonzero(by_row >= max(0.2, 3 * np.median(by_row)))[0]]
    cols_at = [x0 + int(i) for i in np.nonzero(by_col >= max(0.2, 3 * np.median(by_col)))[0]]
    rows = material[0, 0, :] & False
    cols = material[0, :, 0] & False
    frames = [*range(max(0, item["first"] - span), min(t_count, item["first"] + half + 1)),
              *range(max(0, item["last"] - half), min(t_count, item["last"] + span + 1))]
    for t in frames:
        for y in rows_at:
            rows |= _long_runs(material[t, y, :], transient[y, :], min_x)
        for x in cols_at:
            cols |= _long_runs(material[t, :, x], transient[:, x], min_y)
    gap = 2
    return _union(item["box"], (_reach(rows, x0, -1, gap), _reach(cols, y0, -1, gap),
                                _reach(rows, x1 - 1, 1, gap) + 1, _reach(cols, y1 - 1, 1, gap) + 1))


def _ring(box, shape):
    x0, y0, x1, y1 = box
    px, py = max(4, (x1 - x0) // 4), max(4, (y1 - y0) // 4)
    return (max(0, x0 - px), max(0, y0 - py), min(shape[1], x1 + px), min(shape[0], y1 + py))


def _changed(gray, t: int, box) -> tuple[float, float]:
    """Share of pixels that changed from frame t-1 to t: inside `box` and in the ring around it."""
    import numpy as np

    diff = np.abs(gray[t].astype(np.int16) - gray[t - 1].astype(np.int16)) > 12
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = _ring(box, gray.shape[1:])
    inside = diff[y0:y1, x0:x1]
    ring_all = diff[ry0:ry1, rx0:rx1]
    ring_n = ring_all.size - inside.size
    ring = (ring_all.sum() - inside.sum()) / ring_n if ring_n > 0 else 0.0
    return float(inside.mean()) if inside.size else 0.0, float(ring)


def _animated(gray, t: int, box, base: float) -> bool:
    """Frame t changed inside `box` much more than around it, or much more than the box usually
    changes (`base`, over a busy background): part of an entry or exit."""
    if t < 1 or t >= len(gray):
        return False
    inside, ring = _changed(gray, t, box)
    return inside >= 0.02 and (inside >= 2 * ring + 0.01 or inside >= 3 * base + 0.01)


def _base(gray, frames, box) -> float:
    import numpy as np

    shares = [_changed(gray, t, box)[0] for t in frames if 1 <= t < len(gray)]
    return float(np.median(shares)) if shares else 0.0


def _semi_transparent(gray, first: int, last: int, box) -> bool:
    import cv2
    import numpy as np

    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) // 5, (y1 - y0) // 5
    inner = (x0 + dx, y0 + dy, x1 - dx, y1 - dy)
    if inner[2] - inner[0] < 4 or inner[3] - inner[1] < 4:
        return False

    def grad(t):
        g = gray[t].astype(np.float32)
        mag = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
        return mag[inner[1]:inner[3], inner[0]:inner[2]].ravel()

    before = first - 1 if first > 0 else (last + 1 if last + 1 < len(gray) else None)
    if before is not None:
        g_pre, g_dur = grad(before), grad((first + last) // 2)
        if g_pre.mean() > 5 and g_dur.std() > 0 and g_pre.std() > 0:
            r = float(np.corrcoef(g_pre, g_dur)[0, 1])
            if r >= 0.5 and g_dur.mean() >= 0.15 * g_pre.mean():
                return True
    rates = [_changed(gray, t, inner) for t in range(max(first + 1, 1), last + 1)]
    if rates:
        inside = sum(r[0] for r in rates) / len(rates)
        ring = sum(r[1] for r in rates) / len(rates)
        if ring > 0.02 and 0.15 <= inside / ring <= 0.95:
            return True
    return False


def _to_source(clip: _Clip, box) -> tuple[int, int, int, int]:
    W, H = clip.info["width"], clip.info["height"]
    return (math.floor(box[0] * clip.sx), math.floor(box[1] * clip.sy),
            min(W, math.ceil(box[2] * clip.sx)), min(H, math.ceil(box[3] * clip.sy)))


def _find_overlays(clip: _Clip, transcript: dict | None = None) -> tuple[list[Overlay], list[dict], list[dict]]:
    """(overlays, possible whole-shot overlays as {first_frame, last_frame, bbox}, check-frames
    regions as {first_frame, last_frame, bbox})."""
    gray, fps = clip.gray, clip.fps
    scenes_ = clip.scene_frames()
    stable, half = _stable_edges(gray, fps, scenes_)
    shots = _shots(stable, scenes_)
    material, backgrounds = _overlay_material(gray, stable, shots, half)
    h, w = gray.shape[1:]
    min_frames = max(3, round(MIN_S * fps))
    best_s, best_e, best_len = _runs(material, half, {a: _persists(gray, stable, a) for a, _ in shots[1:]})
    close = max(3, round(w * 0.06) | 1)
    min_area = max(40, int(0.002 * w * h))
    items = _groups(gray, best_s, best_e, best_len >= min_frames, tol=half, close=close, min_px=20, min_area=min_area)
    for item in items:  # a run of stable frames starts half a window after the overlay does
        item["first"] = max(0, item["first"] - half)
        item["last"] = min(len(gray) - 1, item["last"] + half)
    span = max(1, round(MAX_ANIMATION_S * fps))
    items = _merge_animated(items, tol=half, span=span, w=w, h=h)
    out = []
    for item in items:
        box, first, last = _trail(material, best_len < min_frames, item, span, half), item["first"], item["last"]
        lo, hi = max(1, first - span), min(len(gray) - 1, last + span)
        before, after = _base(gray, range(lo, first), box), _base(gray, range(last + 1, hi + 1), box)
        while first - 1 >= lo and _animated(gray, first - 1, box, before):
            first -= 1
        while last + 2 <= hi and _animated(gray, last + 1, box, after) and _animated(gray, last + 2, box, after):
            last += 1
        out.append(_overlay(clip, first, last, box, _semi_transparent(gray, item["first"], item["last"], item["box"])))
    suspects = [{"first_frame": s["first"], "last_frame": s["last"], "bbox": list(_to_source(clip, s["box"]))}
                for s in _whole_shot_suspects(backgrounds, close)]
    text = tx.find(gray, fps, scenes_, backgrounds, _word_starts(transcript))
    out, suspects = _with_text(clip, out, text, suspects)
    checks = [{"first_frame": r["first"], "last_frame": r["last"], "bbox": list(_to_source(clip, r["box"]))}
              for r in text["check"]]
    return sorted(out, key=lambda o: (o.start_frame, o.bbox[1], o.bbox[0])), suspects, checks


def _overlay(clip: _Clip, first: int, last: int, box, semi: bool, **more) -> Overlay:
    """An overlay in source pixels, from a box in analysis pixels."""
    W, H = clip.info["width"], clip.info["height"]
    sx0, sy0, sx1, sy1 = _to_source(clip, box)
    touches = sx0 <= EDGE_PX or sy0 <= EDGE_PX or W - sx1 <= EDGE_PX or H - sy1 <= EDGE_PX
    return Overlay(first, last, (sx0, sy0, sx1, sy1), bool(touches), bool(semi), **more)


def _word_starts(transcript: dict | None) -> list[float]:
    out = []
    for seg in (transcript or {}).get("segments", []):
        for w in seg.get("words") or []:
            try:
                out.append(float(w["start"]))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(out)


GRAPHIC_CHECK = "Found by edges only, with no text line in it: a bar or a shape, or a false find; check the frames."
FULL_FRAME_CHECK = ("A still scene with text in it: an end card or a full-frame title (or text in the picture "
                    "itself); check the frames.")
CAPTIONS_CHECK = "Text that changes, but not in step with the spoken words; check the frames."
SHORT_CHECK = "Text seen only briefly or faintly; check the frames."
UNCHECKED_CAPTIONS = "Text that changes, with no spoken words to check it against; check the frames."


def _same_overlay(a: Overlay, b: Overlay) -> bool:
    """Overlapping in space (half the smaller box) and in time (half the shorter life)."""
    t = min(a.end_frame, b.end_frame) - max(a.start_frame, b.start_frame) + 1
    shorter = min(a.end_frame - a.start_frame, b.end_frame - b.start_frame) + 1
    return t >= 0.5 * shorter and _overlap(a.bbox, b.bbox) >= 0.5


def _absorb(a: Overlay, b: Overlay, W: int, H: int, reach: int) -> Overlay:
    """`a` with `b` joined into it: the union of the boxes and both methods. `a`'s life stays,
    widened by `b` by up to `reach` frames at either end (an entry or exit animation): the edge
    method can join text that comes and goes at different moments, the text pass keeps it apart."""
    from dataclasses import replace

    box = _union(a.bbox, b.bbox)
    touches = box[0] <= EDGE_PX or box[1] <= EDGE_PX or W - box[2] <= EDGE_PX or H - box[3] <= EDGE_PX
    methods = tuple(m for m in ("edges", "text") if m in a.methods or m in b.methods)
    first = b.start_frame if a.start_frame - reach <= b.start_frame < a.start_frame else a.start_frame
    last = b.end_frame if a.end_frame < b.end_frame <= a.end_frame + reach else a.end_frame
    return replace(a, start_frame=first, end_frame=last, bbox=box, touches_edge=bool(touches),
                   semi_transparent=a.semi_transparent or b.semi_transparent, methods=methods)


def _confidence(kind: str, methods: tuple[str, ...], samples: int, align: dict | None) -> tuple[float, str | None]:
    if kind == "full_frame":
        return 0.5, FULL_FRAME_CHECK
    if kind == "word_captions":
        if align and align["aligned"]:
            return 0.9, None
        return (0.6, CAPTIONS_CHECK) if align else (0.6, UNCHECKED_CAPTIONS)
    if kind == "text":
        score = 0.6 + (0.2 if "edges" in methods else 0) + (0.1 if samples >= 10 else 0)
        return round(min(score, 0.9), 2), (SHORT_CHECK if score < 0.7 else None)
    return 0.4, GRAPHIC_CHECK


def _with_text(clip: _Clip, edges: list[Overlay], text: dict, suspects: list[dict]) -> tuple[list[Overlay], list[dict]]:
    """The edge method's overlays joined with the text pass (module docstring, "Text")."""
    from dataclasses import replace

    gray, W, H = clip.gray, clip.info["width"], clip.info["height"]
    found = []
    for tr in text["text"]:
        found.append((_overlay(clip, tr["first"], tr["last"], tr["box"],
                               _semi_transparent(gray, tr["first"], tr["last"], tr["box"]), kind=tr["kind"],
                               methods=("text",), spans=tuple(tr["spans"]), transcript=tr["transcript"]),
                      tr["samples"]))
    full = [_overlay(clip, f["first"], f["last"], f["box"], False, kind="full_frame", methods=("text",))
            for f in text["full_frame"]]
    reach = max(1, round(MAX_ANIMATION_S * clip.fps))
    rest = []
    for e in edges:
        hits = [i for i, (o, _) in enumerate(found) if _same_overlay(o, e)]
        for i in hits:
            o = found[i][0]
            if len(hits) > 1:  # the edge method joined text the text pass keeps apart: it only confirms
                o = replace(o, methods=("edges", "text"))
            else:
                o = _absorb(o, e, W, H, reach)
            found[i] = (o, found[i][1])
        if not hits:
            rest.append(e)
    out = []
    for o, samples in found:
        conf, check = _confidence(o.kind, o.methods, samples, o.transcript)
        out.append(replace(o, confidence=conf, check=check))
    for o in rest:
        conf, check = _confidence("graphic", o.methods, 0, None)
        out.append(replace(o, confidence=conf, check=check))
    tol = max(1, round(STABLE_S * clip.fps))
    for f in full:  # what lies mostly in a full-frame graphic's scene and box is part of it
        inside = [o for o in out if _overlap(o.bbox, f.bbox) >= 0.5 and
                  min(o.end_frame, f.end_frame) - max(o.start_frame, f.start_frame) + 1
                  >= 0.5 * (o.end_frame - o.start_frame + 1)]
        for o in inside:
            f = _absorb(f, o, W, H, 0)
            out.remove(o)
        conf, check = _confidence("full_frame", f.methods, 0, None)
        out.append(replace(f, start_frame=max(f.start_frame, 0), confidence=conf, check=check))
        suspects = [x for x in suspects
                    if not (x["first_frame"] >= f.start_frame - tol and x["last_frame"] <= f.end_frame + tol)]
    return out, suspects


def overlays(video: Path | str, transcript: dict | None = None) -> list[Overlay]:
    """On-screen overlays (text cards, captions, bars) with their life cycle and box."""
    return _find_overlays(_Clip(video), transcript)[0]


# Speech on camera ----------------------------------------------------------------------------

def _face_detector():
    import cv2

    # Read through FileStorage from memory: CascadeClassifier(path) cannot open non-ASCII paths on
    # Windows, and the plugin data folder may sit under C:\Users\Łukasz.
    xml = (Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml").read_text(encoding="utf-8")
    storage = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    detector = cv2.CascadeClassifier()
    if not detector.read(storage.getFirstTopLevelNode()):
        raise c.ToolError("OpenCV's face detector could not be loaded.")
    return detector


def _speech_times(transcript: dict | None) -> list[float]:
    times = []
    for seg in (transcript or {}).get("segments", []):
        if not seg.get("words") and not (seg.get("text") or "").strip():
            continue
        t, end = float(seg["start"]) + 0.25, float(seg["end"])
        while t < end:
            times.append(t)
            t += 0.5
    if len(times) > MAX_FACE_SAMPLES:
        step = len(times) / MAX_FACE_SAMPLES
        times = [times[int(i * step)] for i in range(MAX_FACE_SAMPLES)]
    return times


def speech_on_camera(clip: _Clip, transcript: dict | None) -> tuple[bool, dict]:
    times = _speech_times(transcript)
    evidence = {"method": "opencv haar frontal face", "sampled": 0, "with_face": 0, "share": 0.0}
    if not times:
        return False, evidence
    detector = _face_detector()
    w = clip.gray.shape[2]
    side = max(24, int(FACE_MIN_W * w))
    found = 0
    for t in times:
        frame = clip.gray[min(clip.frames - 1, round(t * clip.fps))]
        faces = detector.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5, minSize=(side, side))
        found += int(len(faces) > 0)
    share = found / len(times)
    evidence.update({"sampled": len(times), "with_face": found, "share": round(share, 3)})
    return share >= FACE_SHARE, evidence


# The teardown --------------------------------------------------------------------------------

def _has_speech(transcript: dict | None) -> bool:
    return any((s.get("text") or "").strip() or s.get("words") for s in (transcript or {}).get("segments", []))


def teardown(video: Path | str, transcript: dict | None) -> dict:
    """The teardown dict without file references (main() adds frames and the transcript file)."""
    info = c.probe(video)
    if not info.get("is_video"):
        return {"is_video": False, "width": info.get("width"), "height": info.get("height"), "fps": None,
                "duration_s": info.get("duration"), "frame_count": 1 if info.get("has_video") else 0,
                "has_audio": info.get("has_audio", False), "scenes": [], "overlays": [],
                "has_speech": _has_speech(transcript), "speech_on_camera": False,
                "speech_on_camera_evidence": {"method": "not a video", "sampled": 0, "with_face": 0, "share": 0.0},
                "possible_whole_shot_overlays": [], "check_frames": [],
                "notes": ["Not a video (a still image): the material is static."]}
    clip = _Clip(video)
    fps = clip.fps
    on_camera, evidence = speech_on_camera(clip, transcript)
    found, suspects, checks = _find_overlays(clip, transcript)
    notes = [f"Possible overlay spanning the whole shot (frames {x['first_frame']}-{x['last_frame']}) at "
             f"{x['bbox']}; check the frames." for x in suspects]
    for x in checks:
        x.update(start_s=_seconds(x["first_frame"], fps), end_s=_seconds(x["last_frame"] + 1, fps))
        notes.append(f"The picture at {x['bbox']} changes with the spoken words from {x['start_s']} s to "
                     f"{x['end_s']} s, but no text was found there: maybe captions; check the frames.")
    if transcript is None:
        notes.append("Not transcribed: has_speech is false until a transcript is given.")
    elif not _has_speech(transcript):
        notes.append("No speech found (lesson 3): the structure comes from captions and shots.")
    return {
        "is_video": True, "width": info["width"], "height": info["height"],
        "fps": int(fps) if float(fps).is_integer() else fps, "duration_s": info["duration"],
        "frame_count": clip.frames, "has_audio": info["has_audio"],
        "scenes": [{"start_s": _seconds(a, fps), "end_s": _seconds(b + 1, fps), "start_frame": a, "end_frame": b}
                   for a, b in clip.scene_frames()],
        "overlays": [_overlay_json(o, fps) for o in found],
        "has_speech": _has_speech(transcript), "speech_on_camera": on_camera,
        "speech_on_camera_evidence": evidence, "notes": notes, "possible_whole_shot_overlays": suspects,
        "check_frames": checks,
    }


def _overlay_json(o: Overlay, fps: float) -> dict:
    d = asdict(o)
    spans = d.pop("spans")
    return {**d, "bbox": list(o.bbox), "methods": list(o.methods), "start_s": _seconds(o.start_frame, fps),
            "end_s": _seconds(o.end_frame + 1, fps),
            "spans_s": [[_seconds(a, fps), _seconds(b + 1, fps)] for a, b in spans]
            or [[_seconds(o.start_frame, fps), _seconds(o.end_frame + 1, fps)]]}


# The check sheet ------------------------------------------------------------------------------

def _three(first: int, last: int) -> list[int]:
    return sorted({int(first), (int(first) + int(last)) // 2, int(last)})


def check_items(data: dict) -> list[dict]:
    """What the tool is unsure of, in the sheet's order: the overlays with a `check` (least sure first), the
    `check_frames` bands, the `possible_whole_shot_overlays`; each with the frames to show (first, middle, last)
    and its box."""
    fps = data.get("fps") or 0
    sure = sorted(((i, o) for i, o in enumerate(data.get("overlays") or []) if o.get("check")),
                  key=lambda x: (x[1].get("confidence", 0), x[1]["start_frame"]))
    items = [{"what": "overlay", "overlay": i, "kind": o["kind"], "confidence": o["confidence"], "check": o["check"],
              "frames": _three(o["start_frame"], o["end_frame"]), "bbox": list(o["bbox"])} for i, o in sure]
    items += [{"what": "check_frames", "frames": _three(x["first_frame"], x["last_frame"]), "bbox": list(x["bbox"])}
              for x in data.get("check_frames") or []]
    items += [{"what": "whole_shot", "frames": _three(x["first_frame"], x["last_frame"]), "bbox": list(x["bbox"])}
              for x in data.get("possible_whole_shot_overlays") or []]
    for item in items:
        item["t_s"] = [_seconds(f, fps) for f in item["frames"]] if fps else None
    return items


def check_sheet(video: Path | str, items: list[dict], out: Path) -> Path | None:
    """One PNG, a row per item: its box drawn on its frames, three tiles of SHEET_TILE_W a row (ffmpeg; free and
    local). None, and no file, when there is nothing to check."""
    if not items:
        return None
    rows = [c.frame_row(i["frames"], width=SHEET_TILE_W, columns=3, box=i["bbox"]) for i in items]
    args = []
    for _ in rows:
        args += ["-i", c.media(video)]
    graph = ";".join(f"[{n}:v]{row}[r{n}]" for n, row in enumerate(rows))
    if len(rows) > 1:
        graph += ";" + "".join(f"[r{n}]" for n in range(len(rows))) + f"vstack=inputs={len(rows)}[sheet]"
    last = "[sheet]" if len(rows) > 1 else "[r0]"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c.run_ffmpeg([*args, "-filter_complex", graph, "-map", last, "-frames:v", "1", c.media(out)])
    return Path(out)


def _transcript_ref(run, path: Path | None, transcript: dict | None) -> dict | None:
    if transcript is None:
        return None
    segments = transcript.get("segments", [])
    return {"file": c.parent_ref(run, path) if path else None, "language": transcript.get("language"),
            "segments": len(segments), "words": sum(len(s.get("words") or []) for s in segments),
            "speech_s": round(sum(float(s["end"]) - float(s["start"]) for s in segments), 2)}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    import json

    from tm.tools import transcribe as tr

    p = c.parser("teardown", "Scenes, frames, overlays and material keys of the original ad.")
    p.add_argument("video")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--transcript", default=None, help="a transcript JSON from tm tool transcribe")
    group.add_argument("--no-transcribe", action="store_true", help="skip speech (has_speech stays false)")
    p.add_argument("--every-s", type=float, default=1.0, help="seconds between saved frames")
    p.add_argument("--model", default=tr.DEFAULT_MODEL)
    p.add_argument("--lang", default=None)
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    c.inputs(run, a, "video", "transcript")   # a run-relative input, whatever the working folder
    out = c.output(run, a.out, "research", "teardown", "json")
    frames_dir = out.with_name(out.stem + "_frames")
    sheet = out.with_name(out.stem + "_check.png")
    for taken in (frames_dir, sheet):
        if taken.exists():
            raise c.ToolError(f"{c.rel(run, taken)} already exists, and files are never overwritten.")
    outputs = []
    transcript_path: Path | None
    if a.transcript:
        transcript_path = Path(a.transcript)
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    elif a.no_transcribe:
        transcript_path, transcript = None, None
    else:
        transcript_path = c.output(run, None, "research", "transcript", "json")
        transcript = tr.save(run, a.video, transcript_path, a.model, a.lang)
        outputs.append(c.rel(run, transcript_path))
    data = teardown(a.video, transcript)
    stills = frames(a.video, frames_dir, a.every_s)
    items = check_items(data)
    shown = items[:MAX_SHEET_ROWS]
    made = check_sheet(a.video, [{"frames": i["frames"], "bbox": i["bbox"]} for i in shown], sheet) \
        if data["is_video"] else None
    data = {"video": c.parent_ref(run, a.video), **data,
            "frames": {"dir": c.rel(run, frames_dir), "every_s": a.every_s,
                       "files": [{"file": pth.name, "t": t} for pth, t in stills]},
            "check_sheet": {"file": c.rel(run, made), "rows": [{"row": n, **i} for n, i in enumerate(shown, 1)],
                            "left_out": items[MAX_SHEET_ROWS:], "limits": list(TEXT_LIMITS)} if made else None,
            "transcript": _transcript_ref(run, transcript_path, transcript)}
    c.write_json(out, data)
    outputs.insert(0, c.rel(run, out))
    parent = c.parent_ref(run, a.video)
    c.record(run, out, "tm tool teardown (PySceneDetect, OpenCV, ffmpeg)", parent,
             params={"every_s": a.every_s, "analysis_width": ANALYSIS_W, "edge_px": EDGE_PX,
                     "text_step_s": tx.TEXT_STEP_S}, cost="0 (local)",
             request={"video": parent, "transcript": data["transcript"] and data["transcript"]["file"],
                      "every_s": a.every_s},
             response={k: data[k] for k in ("is_video", "has_speech", "speech_on_camera",
                                            "speech_on_camera_evidence", "scenes", "overlays", "check_frames")})
    c.record(run, frames_dir, "tm tool teardown (ffmpeg stills)", parent,
             params={"every_s": a.every_s, "frames": len(stills)}, cost="0 (local)")
    to_check = ""
    if made:
        c.record(run, made, "tm tool teardown (ffmpeg check sheet)", parent,
                 params={"rows": len(shown), "left_out": len(items) - len(shown), "tile_w": SHEET_TILE_W},
                 cost="0 (local)")
        outputs.append(c.rel(run, made))
        to_check = (f"; {len(items)} item(s) to check, from the check sheet {c.rel(run, made)} "
                    f"(its rows: check_sheet.rows)")
    summary = {k: data[k] for k in ("is_video", "has_speech", "speech_on_camera")}
    return c.finish(a, {"tool": "teardown", "outputs": outputs, **summary, "scenes": len(data["scenes"]),
                        "overlays": len(data["overlays"]), "to_check": len(items),
                        "check_sheet": c.rel(run, made) if made else None},
                    f"Teardown saved to {c.rel(run, out)}: {len(data['scenes'])} shot(s), "
                    f"{len(data['overlays'])} overlay(s), speech: {'yes' if data['has_speech'] else 'no'}"
                    f"{' (on camera)' if data['speech_on_camera'] else ''}, {len(stills)} frame(s){to_check}.")


if __name__ == "__main__":
    raise SystemExit(main())
