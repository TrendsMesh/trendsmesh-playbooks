"""The teardown's text pass (issue #29): on-screen text found in frames every TEXT_STEP_S, tracked
over time, checked against the transcript's word times.

The edge method (`teardown`, step 1-6) needs an edge to stay still for about 0.2 s and a run of
0.3 s, so word-by-word captions (a new word every few tenths of a second) never reach it, and the
lines of one caption that come in at different moments stay apart. This pass looks for text
itself, in every sampled frame, and joins what belongs together over time:

1. Strokes: Canny edges (stricter than the edge method's) present in three frames in a row, the
   pixel hardly changing between them (TEXT_STILL), minus the shot's background (the edge
   method's step 2). Text drawn on top holds still for a word; a moving picture does not.
2. Lines: strokes closed sideways into blobs as tall as a line of text (TEXT_MIN_H to TEXT_MAX_H of
   the frame), not much narrower than tall, dense with strokes (TEXT_DENSITY), crossed by several
   of them along a row (the letters) and still: their pixels typically change by TEXT_LINE_STILL
   or less (a zoom over texture keeps some edges, but its pixels move). The box is trimmed of the
   thin bits of background the closing caught. Lines stacked closely in one sample are one block
   (a two-line caption with its bar).
3. Tracks: a block continues the track whose box it overlaps in the same band, within
   TRACK_GAP_S; the track's box is the union of its blocks. The text changed (a new word) where
   the strokes differ from the sample before (stroke IoU below CHANGE_IOU) and the new strokes
   hold for the next sample; its frame is found frame by frame. Tracks on screen together and
   stacked closely merge (the lines of one caption); changing tracks in one band with gaps up to
   CAPTION_GAP_S merge (sentences of the captions). Tracks seen in fewer than MIN_SAMPLES samples
   are dropped. The start and end are found frame by frame around the first and last sample.
4. Kinds: a track whose text changes CAPTION_CHANGES times or more, at CAPTION_RATE per second or
   more, is `word_captions`, else `text`. With a transcript, its changes are compared with the
   word starts (within ALIGN_S): when the share of changes on a word start is ALIGNED_SHARE or
   more and ALIGN_OVER_CHANCE above what changes at random moments would reach (dense speech
   puts a word start near most moments), it is word-by-word captioning (`aligned`), also with
   fewer changes. A band of the frame (one of CHECK_BANDS) whose strokes change CHECK_EVENTS
   times or more, in step with the words, yet in at most CHECK_EVENT_SHARE of the samples where
   it has strokes (captions hold each word; a busy picture changes all the time), with no text
   found there, is returned as a "check frames" region.
5. Full-frame graphics: in a still scene (the picture hardly changes, STILL_SCENE), text lines
   that stay all through it and that no text track covers (the background rule took them: they
   are there for the whole shot) are `full_frame`, an end card or a full-frame title; its box is
   the text's.

Limits: no OCR, so the words on screen are never read; the transcript check compares times only.
Stylised fonts, thin text, text over a busy still picture, and text that moves (a scroll, a
bounce) are missed or broken up; a still shot whose own picture holds text (a product label) can
come out as `full_frame`. The "check frames" regions and the agent's look at the frames catch
those. Tuned on synthetic clips (tests/tools/_textad.py).
"""

from __future__ import annotations

TEXT_STEP_S = 0.1
TEXT_CANNY = (40, 120)
TEXT_STILL = 12
TEXT_MIN_H = 0.012
TEXT_MAX_H = 0.14
TEXT_DENSITY = 0.25
TEXT_LINE_STILL = 4
TRACK_GAP_S = 0.6
CAPTION_GAP_S = 2.0
CHANGE_IOU = 0.7
CHANGE_MERGE_S = 0.15
CAPTION_CHANGES = 3
CAPTION_RATE = 0.7
ALIGN_S = 0.12
ALIGNED_SHARE = 0.6
ALIGN_OVER_CHANCE = 0.25
MIN_SAMPLES = 3
CHECK_EVENT_SHARE = 0.5
STILL_SCENE = 1.0
MIN_SCENE_S = 0.5
CHECK_BANDS = 12
CHECK_EVENTS = 4


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _h(b) -> int:
    return b[3] - b[1]


def _w(b) -> int:
    return b[2] - b[0]


def _vover(a, b) -> int:
    return min(a[3], b[3]) - max(a[1], b[1])


def _hover(a, b) -> int:
    return min(a[2], b[2]) - max(a[0], b[0])


class _Strokes:
    """Text strokes per frame, computed once each (step 1)."""

    def __init__(self, gray, scenes: list[tuple[int, int]], backgrounds: list[tuple[int, int, object]]):
        import numpy as np

        self.gray = gray
        self.scene_of = np.zeros(len(gray), np.int32)
        self.scenes = scenes
        for i, (a, b) in enumerate(scenes):
            self.scene_of[a: b + 1] = i
        self.bg = [None] * len(gray)
        for a, b, mask in backgrounds:
            for t in range(a, b + 1):
                self.bg[t] = mask
        self._edges: dict[int, object] = {}
        self._strokes: dict[int, object] = {}

    def edges(self, t: int):
        import cv2
        import numpy as np

        if t not in self._edges:
            e = cv2.Canny(cv2.GaussianBlur(self.gray[t], (3, 3), 0), *TEXT_CANNY)
            self._edges[t] = cv2.dilate(e, np.ones((3, 3), np.uint8)) > 0
        return self._edges[t]

    def raw(self, t: int):
        """Strokes without the background removed."""
        import numpy as np

        a, b = self.scenes[self.scene_of[t]]
        idx = [i for i in (t - 1, t, t + 1) if a <= i <= b]
        if len(idx) < 2:
            return np.zeros(self.gray.shape[1:], bool)
        m = np.logical_and.reduce([self.edges(i) for i in idx])
        return m & (self.diff(t) <= TEXT_STILL)

    def diff(self, t: int):
        """How much each pixel changes across the frames around t (within the scene)."""
        import numpy as np

        a, b = self.scenes[self.scene_of[t]]
        lo, hi = max(a, t - 1), min(b, t + 1)
        return np.abs(self.gray[hi].astype(np.int16) - self.gray[lo])

    def lines(self, t: int, raw: bool = False) -> list[tuple[int, int, int, int]]:
        return _lines(self.raw(t) if raw else self.at(t), self.diff(t))

    def at(self, t: int):
        if t not in self._strokes:
            m = self.raw(t)
            if self.bg[t] is not None:
                m = m & ~self.bg[t]
            self._strokes[t] = m
        return self._strokes[t]


def _lines(mask, diff=None) -> list[tuple[int, int, int, int]]:
    """Text-line boxes in a stroke mask (step 2), in analysis pixels. With `diff` (how much each
    pixel changes around the frame), a line whose strokes typically change by more than
    TEXT_LINE_STILL is texture, not text drawn on top."""
    import cv2
    import numpy as np

    h, w = mask.shape
    kx = max(3, round(0.035 * w))
    closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, kx), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    out = []
    lo, hi = max(5, round(TEXT_MIN_H * h)), round(TEXT_MAX_H * h)
    for i in range(1, n):
        x, y, bw, bh = (int(v) for v in stats[i][:4])
        if not lo <= bh <= hi or bw < 0.6 * bh:
            continue
        block = mask[y:y + bh, x:x + bw]
        if block.mean() < TEXT_DENSITY:
            continue
        if diff is not None and np.median(diff[y:y + bh, x:x + bw][block]) > TEXT_LINE_STILL:
            continue
        # letters: several strokes crossed along the middle rows
        mid = block[bh // 4: bh - bh // 4] if bh >= 4 else block
        crossings = (np.diff(mid.astype(np.int8), axis=1) == 1).sum(axis=1)
        if np.median(crossings) < 2:
            continue
        out.append(_trim(block, x, y))
    return out


def _trim(block, x: int, y: int) -> tuple[int, int, int, int]:
    """The line's box without the thin bits of background the closing caught at its sides: rows
    (columns) at the box's border holding under a quarter (a tenth) of a typical row's strokes."""
    import numpy as np

    rows, cols = block.sum(axis=1), block.sum(axis=0)
    r = np.nonzero(rows >= 0.25 * np.median(rows[rows > 0]))[0]
    k = np.nonzero(cols >= 0.1 * np.median(cols[cols > 0]))[0]
    return x + int(k.min()), y + int(r.min()), x + int(k.max()) + 1, y + int(r.max()) + 1


def _stacked(a, b) -> bool:
    """Lines of one block: one under the other, close, overlapping sideways."""
    gap = max(a[1], b[1]) - min(a[3], b[3])
    return gap <= 0.8 * max(_h(a), _h(b)) and _hover(a, b) >= 0.3 * min(_w(a), _w(b))


def _blocks(lines: list) -> list:
    boxes = list(lines)
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _stacked(boxes[i], boxes[j]) or (_hover(boxes[i], boxes[j]) > 0 and _vover(boxes[i], boxes[j]) > 0):
                    boxes[i] = _union(boxes[i], boxes[j])
                    del boxes[j]
                    changed = True
                    break
            if changed:
                break
    return boxes


def _same_band(a, b, w: int) -> bool:
    centre = abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2)
    return _vover(a, b) >= 0.5 * min(_h(a), _h(b)) and (_hover(a, b) > 0 or centre <= 0.15 * w)


def _iou(m1, m2) -> float:
    inter = (m1 & m2).sum()
    union = (m1 | m2).sum()
    return float(inter / union) if union else 1.0


def _track(strokes: _Strokes, samples: list[int], fps: float, w: int, step: int) -> list[dict]:
    """Blocks followed over the samples (step 3)."""
    gap = max(2, round(TRACK_GAP_S * fps))
    tracks: list[dict] = []
    for t in samples:
        for box in _blocks(strokes.lines(t)):
            best, score = None, 0
            for tr in tracks:
                if t - tr["last_sample"] > gap or tr["last_sample"] == t:
                    continue
                if strokes.scene_of[tr["last_sample"]] != strokes.scene_of[t]:
                    continue
                if _same_band(tr["last_box"], box, w) or _same_band(tr["box"], box, w):
                    s = _vover(tr["box"], box)
                    if s > score:
                        best, score = tr, s
            if best is None:
                tracks.append({"first_sample": t, "last_sample": t, "box": box, "last_box": box,
                               "first_box": box, "samples": [t], "boxes": {t: box}})
                continue
            best.update(last_sample=t, last_box=box, box=_union(best["box"], box))
            best["samples"].append(t)
            best["boxes"][t] = box
    tracks = [tr for tr in tracks if len(tr["samples"]) >= 2]
    for tr in tracks:
        tr["changes"] = _changes(strokes, tr, step, fps)
    return tracks


def _changes(strokes: _Strokes, tr: dict, step: int, fps: float) -> list[int]:
    """Frames where the track's text changed: its strokes differ from the sample before (across a
    gap too: a new word after a pause) and the new text then holds for the next sample. A
    background showing through a bar flickers without holding; a word swap passes through a frame
    or two of half strokes, which do not hold either; text back unchanged after a sample or two
    where it was missed is no change."""
    ts, boxes = tr["samples"], tr["boxes"]

    def same(i: int, j: int) -> bool:
        x0, y0, x1, y1 = _union(boxes[ts[i]], boxes[ts[j]])
        return _iou(strokes.at(ts[i])[y0:y1, x0:x1], strokes.at(ts[j])[y0:y1, x0:x1]) >= CHANGE_IOU

    out: list[int] = []
    for i in range(1, len(ts)):
        if same(i - 1, i):
            continue
        if not (i + 1 < len(ts) and ts[i + 1] - ts[i] <= 1.5 * step and same(i, i + 1)):
            continue
        frame = _change_frame(strokes, ts[i - 1], ts[i], _union(boxes[ts[i - 1]], boxes[ts[i]]))
        if out and frame - out[-1] <= CHANGE_MERGE_S * fps:
            out[-1] = frame
        else:
            out.append(frame)
    return out


def _change_frame(strokes: _Strokes, before: int, t: int, box) -> int:
    """The first frame of the new text: the strokes of sample `t` show from one frame after it."""
    x0, y0, x1, y1 = box
    ref = strokes.at(t)[y0:y1, x0:x1]
    first = t
    while first - 1 > before and _iou(strokes.at(first - 1)[y0:y1, x0:x1], ref) >= CHANGE_IOU:
        first -= 1
    return max(before + 1, first - 1)


def _overlap_t(a: dict, b: dict) -> int:
    return min(a["last_sample"], b["last_sample"]) - max(a["first_sample"], b["first_sample"])


def _merge(strokes: _Strokes, a: dict, b: dict, step: int, fps: float) -> dict:
    boxes = dict(a["boxes"])
    for t, box in b["boxes"].items():
        boxes[t] = _union(boxes[t], box) if t in boxes else box
    samples = sorted(boxes)
    tr = {"first_sample": samples[0], "last_sample": samples[-1], "box": _union(a["box"], b["box"]),
          "first_box": boxes[samples[0]], "last_box": boxes[samples[-1]], "samples": samples, "boxes": boxes}
    tr["changes"] = _changes(strokes, tr, step, fps)
    return tr


def _join_tracks(strokes: _Strokes, tracks: list[dict], fps: float, w: int, step: int) -> list[dict]:
    """Lines of one caption (on together, stacked) and sentences of the captions (one band)."""
    caption_gap = round(CAPTION_GAP_S * fps)
    tracks = sorted(tracks, key=lambda tr: tr["first_sample"])
    changed = True
    while changed:
        changed = False
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                a, b = tracks[i], tracks[j]
                shorter = min(a["last_sample"] - a["first_sample"], b["last_sample"] - b["first_sample"])
                together = _overlap_t(a, b) >= 0.5 * shorter and _stacked(a["box"], b["box"])
                sentences = a["changes"] and b["changes"] and _same_band(a["box"], b["box"], w) and \
                    -_overlap_t(a, b) <= caption_gap  # the gap between them, or overlapping
                if together or sentences:
                    tracks[i] = _merge(strokes, a, b, step, fps)
                    del tracks[j]
                    changed = True
                    break
            if changed:
                break
    return tracks


def _present(strokes: _Strokes, t: int, box, ref) -> bool:
    x0, y0, x1, y1 = box
    m = strokes.at(t)[y0:y1, x0:x1]
    return ref.sum() > 0 and (m & ref).sum() >= 0.6 * ref.sum()


def _ends(strokes: _Strokes, tr: dict, step: int) -> tuple[int, int]:
    """First and last frame on screen, walked frame by frame from the first and last sample."""
    a, b = strokes.scenes[strokes.scene_of[tr["first_sample"]]]
    _, b2 = strokes.scenes[strokes.scene_of[tr["last_sample"]]]
    box = tr["first_box"]
    x0, y0, x1, y1 = box
    ref = strokes.at(tr["first_sample"])[y0:y1, x0:x1]
    first = tr["first_sample"]
    while first - 1 >= max(a, tr["first_sample"] - step) and _present(strokes, first - 1, box, ref):
        first -= 1
    box = tr["last_box"]
    x0, y0, x1, y1 = box
    ref = strokes.at(tr["last_sample"])[y0:y1, x0:x1]
    last = tr["last_sample"]
    while last + 1 <= min(b2, tr["last_sample"] + step) and _present(strokes, last + 1, box, ref):
        last += 1
    # strokes need a neighbouring frame, so the first and last frame of the text are one further out
    return max(a, first - 1), min(b2, last + 1)


def _spans(samples: list[int], step: int) -> list[tuple[int, int]]:
    spans: list[list[int]] = []
    for t in samples:
        if spans and t - spans[-1][1] <= int(step * 1.5):
            spans[-1][1] = t
        else:
            spans.append([t, t])
    return [(s, e) for s, e in spans]


def _chance(word_starts: list[float], start_s: float, end_s: float) -> float:
    """The share of [start_s, end_s] within ALIGN_S of a word start: how often a change at a random
    moment would land on a word."""
    windows = sorted((max(start_s, w - ALIGN_S), min(end_s, w + ALIGN_S)) for w in word_starts)
    covered, reach = 0.0, start_s
    for a, b in windows:
        a = max(a, reach)
        if b > a:
            covered += b - a
            reach = b
    return covered / (end_s - start_s) if end_s > start_s else 1.0


def _alignment(changes_s: list[float], word_starts: list[float], start_s: float, end_s: float) -> dict | None:
    """How the text's changes line up with the spoken words' starts, against chance."""
    if not word_starts:
        return None
    inside = [w for w in word_starts if start_s - ALIGN_S <= w <= end_s + ALIGN_S]
    on_word = sum(1 for c in changes_s if any(abs(c - w) <= ALIGN_S for w in inside))
    words_hit = sum(1 for w in inside if any(abs(c - w) <= ALIGN_S for c in changes_s))
    share = on_word / len(changes_s) if changes_s else 0.0
    chance = _chance(inside, start_s, end_s)
    need = min(0.95, max(ALIGNED_SHARE, chance + ALIGN_OVER_CHANCE))
    return {"changes": len(changes_s), "on_word_starts": on_word, "words_spoken": len(inside),
            "words_with_change": words_hit, "share": round(share, 2), "chance": round(chance, 2),
            "aligned": len(changes_s) >= 2 and share >= need}


def _full_frames(strokes: _Strokes, gray, fps: float, found: list[dict]) -> list[dict]:
    """Still scenes with text that stays all through them and that no text overlay covers (the
    background rule took it): an end card or a full-frame title (step 5)."""
    import numpy as np

    out = []
    for a, b in strokes.scenes:
        if (b - a + 1) < MIN_SCENE_S * fps:
            continue
        settle = a + (b - a) // 3  # past an entry animation
        diffs = [float(np.abs(gray[t].astype(np.int16) - gray[t - 1]).mean()) for t in range(settle + 1, b + 1)]
        if not diffs or float(np.median(diffs)) > STILL_SCENE:
            continue
        mid = (settle + b) // 2
        lines = []
        for ln in strokes.lines(mid, raw=True):
            x0, y0, x1, y1 = ln
            area = (x1 - x0) * (y1 - y0)
            covered = any(f["first"] <= mid <= f["last"] and _hover(ln, f["box"]) > 0 and
                          _hover(ln, f["box"]) * _vover(ln, f["box"]) >= 0.5 * area for f in found)
            ref = strokes.raw(mid)[y0:y1, x0:x1]
            stays = all((strokes.raw(t)[y0:y1, x0:x1] & ref).sum() >= 0.6 * ref.sum()
                        for t in (settle + 1, max(settle + 1, b - 1)))
            if not covered and stays:
                lines.append(ln)
        if not lines:
            continue
        box = lines[0]
        for ln in lines[1:]:
            box = _union(box, ln)
        out.append({"first": a, "last": b, "box": box, "lines": len(lines)})
    return out


def _check_regions(strokes: _Strokes, samples: list[int], fps: float, word_starts: list[float],
                   found: list[dict]) -> list[dict]:
    """Bands whose strokes change with the spoken words though no text line was found there."""
    import numpy as np

    if len(word_starts) < CHECK_EVENTS:
        return []
    h, w = strokes.gray.shape[1:]
    band_h = h // CHECK_BANDS
    hits = []
    for k in range(CHECK_BANDS):
        y0, y1 = k * band_h, (k + 1) * band_h if k < CHECK_BANDS - 1 else h
        events, prev, xs, active = [], None, [], 0
        for t in samples:
            m = strokes.at(t)[y0:y1]
            if m.sum() >= 20:
                active += 1
            if prev is not None and (m.sum() >= 20 or prev[1].sum() >= 20) and _iou(prev[1], m) < CHANGE_IOU:
                events.append(_change_frame(strokes, prev[0], t, (0, y0, w, y1)))
                cols = np.nonzero(m.any(axis=0))[0]
                if cols.size:
                    xs += [int(cols.min()), int(cols.max()) + 1]
            prev = (t, m)
        # captions hold each word for a while; a picture that changes at every sample is not text
        if len(events) < CHECK_EVENTS or len(events) > CHECK_EVENT_SHARE * max(1, active):
            continue
        first, last = events[0], events[-1]
        align = _alignment([t / fps for t in events], word_starts, first / fps, (last + 1) / fps)
        if not align or not align["aligned"]:
            continue
        covered = any(f["box"][1] < y1 and f["box"][3] > y0 and f["first"] <= last and f["last"] >= first
                      for f in found)
        if not covered:
            hits.append({"band": k, "first": first, "last": last,
                         "box": (min(xs) if xs else 0, y0, max(xs) if xs else w, y1)})
    regions: list[dict] = []
    for hit in hits:  # neighbouring bands are one region
        if regions and hit["band"] == regions[-1]["band"] + 1:
            r = regions[-1]
            r.update(band=hit["band"], box=_union(r["box"], hit["box"]), first=min(r["first"], hit["first"]),
                     last=max(r["last"], hit["last"]))
        else:
            regions.append(dict(hit))
    return [{"first": r["first"], "last": r["last"], "box": r["box"]} for r in regions]


def find(gray, fps: float, scenes: list[tuple[int, int]], backgrounds: list, word_starts: list[float]) -> dict:
    """{"text": [track], "full_frame": [scene], "check": [region]}, boxes in analysis pixels.

    A track: first, last (frames), box, kind ("text" or "word_captions"), spans [(first, last)],
    changes (frames where the text changed), transcript (the alignment, None without words)."""
    w = gray.shape[2]
    step = max(1, round(TEXT_STEP_S * fps))
    strokes = _Strokes(gray, scenes, backgrounds)
    samples = list(range(0, len(gray), step))
    tracks = _join_tracks(strokes, _track(strokes, samples, fps, w, step), fps, w, step)
    out = []
    for tr in (tr for tr in tracks if len(tr["samples"]) >= MIN_SAMPLES):
        first, last = _ends(strokes, tr, step)
        dur_s = max(1, last - first + 1) / fps
        changes = tr["changes"]
        changes_s = [round(t / fps, 3) for t in changes]
        align = _alignment(changes_s, word_starts, first / fps, (last + 1) / fps)
        captions = len(changes) >= CAPTION_CHANGES and len(changes) / dur_s >= CAPTION_RATE
        if align and align["aligned"]:
            captions = True
        out.append({"first": first, "last": last, "box": tr["box"],
                    "kind": "word_captions" if captions else "text",
                    "spans": _spans(tr["samples"], step), "changes": changes, "samples": len(tr["samples"]),
                    "transcript": align})
    full = _full_frames(strokes, gray, fps, out)
    checks = _check_regions(strokes, samples, fps, word_starts, out)
    return {"text": out, "full_frame": full, "check": checks}
