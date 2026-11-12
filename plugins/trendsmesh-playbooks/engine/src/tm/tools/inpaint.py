"""Free caption removal (VC, `variants.md` 4a, mode budget): OpenCV Telea on the old captions' pixels.

    tm tool inpaint --run RUN VIDEO --teardown TEARDOWN.json [--overlay N ...] [--box X0 Y0 X1 Y1 ...]
                    [--from S] [--to S] [--pad 16] [--grow 6] [--hold 2] [--smooth 2] [--radius 5]
                    [--mask text|box] [--mode budget] [--out PATH] [--json]

Cost 0, local, no approval: the free way next to ProPainter (`tm tool replicate_run`, paid). It
writes the clean plate (`03_wip/inpaint_vNN.mp4`, the sound copied from VIDEO) and the mask it
used (`..._mask.mp4`, white where it painted): render the new captions over the plate, then
`tm tool inpaint_mode --run R <mask> <composite> --crop <crop>` says whether the free plate is
good enough (`crop` is in the answer).

1. Where: the teardown's overlays (`--overlay`, its 0-based indices; by default every `word_captions`
   and `text` overlay), each with its box and the times its text is on screen (`spans_s`, so the
   gaps between words stay untouched), and any `--box` (on for the whole video, or `--from`/`--to`).
   Only frames inside `--from`/`--to` are painted (the window where the text changes). Each box
   grows by `--pad` px (4a: box +16 px).
2. The mask, per frame: in each box on screen, the text's pixels (bright and grey-ish, very dark,
   or an edge: white glyphs with a dark outline, also coloured ones by their edges), closed and
   grown by `--grow` px; `--mask box` takes the whole box instead.
3. Over time, so the patch does not flicker: a frame's mask is the union of the masks `--hold`
   frames before and after it in the same shot (4a: union with neighbouring frames), so it does not
   change shape with every word; each frame is painted (Telea, `--radius`), and inside the mask the
   result is the mean of the painted frames `--smooth` before and after it in the same shot (where
   a neighbour shows the background, its real pixels count); the patch is blended in with a soft
   edge. Shots come from the teardown's `scenes`.

Limits (4a): on texture (sand, water, a face) and on a large card Telea leaves a visible patch;
the residue check (`inpaint_mode`) and a look at the frames decide. Moving text is not followed:
its box is the union of where it went.
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path

from tm.tools import _common as c

TEXT_KINDS = ("word_captions", "text")
# The plate's and the mask's manifest sources (issue #56): classical image processing, no model, so the free
# plate alone doesn't get Meta's AI label. No `tm ai-media` AI marker matches them (it says "inpaint" for a
# model's inpainting); runs recorded before #56 carry "tm tool inpaint budget (...)", which it reads the same way.
SOURCE = "opencv-telea (free caption removal)"
MASK_SOURCE = "opencv-telea mask (free caption removal)"


def regions(teardown: dict, fps: float, frames: int, width: int, height: int, *, overlays: list[int] | None = None,
            boxes: list[tuple[int, int, int, int]] = (), start: float | None = None, end: float | None = None,
            pad: int = 16) -> list[dict]:
    """The boxes to clean, each {"box": (x0, y0, x1, y1) padded and clipped, "spans": [(f0, f1)] inclusive
    frames, "from": the overlay index or "box"}. Frames outside `start`/`end` (seconds) are left out."""
    found = teardown.get("overlays") or []
    if overlays is None:
        picked = [i for i, o in enumerate(found) if o.get("kind") in TEXT_KINDS]
    else:
        bad = [i for i in overlays if not 0 <= i < len(found)]
        if bad:
            raise c.ToolError(f"The teardown has {len(found)} overlay(s) (0 to {len(found) - 1}); "
                              f"--overlay {', '.join(map(str, bad))} is not one of them.")
        picked = list(overlays)
    lo = 0 if start is None else max(0, math.floor(start * fps + 1e-6))
    hi = frames - 1 if end is None else min(frames - 1, math.ceil(end * fps - 1e-6) - 1)

    def clip(box) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = (int(v) for v in box)
        return max(0, x0 - pad), max(0, y0 - pad), min(width, x1 + pad), min(height, y1 + pad)

    def frames_of(spans_s) -> list[tuple[int, int]]:
        out = []
        for a, b in spans_s:
            f0, f1 = max(lo, math.floor(float(a) * fps + 1e-6)), min(hi, math.ceil(float(b) * fps - 1e-6) - 1)
            if f0 <= f1:
                out.append((f0, f1))
        return out

    out = []
    for i in picked:
        o = found[i]
        spans = o.get("spans_s") or [[o.get("start_s", 0), o.get("end_s", frames / fps)]]
        fr = frames_of(spans)
        if fr:
            out.append({"box": clip(o["bbox"]), "spans": fr, "from": i})
    for box in boxes:
        if lo <= hi:
            out.append({"box": clip(box), "spans": [(lo, hi)], "from": "box"})
    return [r for r in out if r["box"][2] > r["box"][0] and r["box"][3] > r["box"][1]]


def _shots(teardown: dict, frames: int) -> list[int]:
    """The shot number of every frame (from the teardown's scenes; one shot when there are none)."""
    shot = [0] * frames
    for n, s in enumerate(teardown.get("scenes") or []):
        for f in range(max(0, int(s["start_frame"])), min(frames, int(s["end_frame"]) + 1)):
            shot[f] = n
    return shot


def _text_pixels(frame, box: tuple[int, int, int, int], grow: int, whole: bool):
    """The mask of one box in one frame, in the box's own coordinates (uint8, 0 or 255)."""
    import cv2
    import numpy as np

    x0, y0, x1, y1 = box
    if whole:
        return np.full((y1 - y0, x1 - x0), 255, np.uint8)
    crop = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    text = ((hsv[..., 2] > 200) & (hsv[..., 1] < 60)) | (hsv[..., 2] < 50) | (cv2.Canny(gray, 60, 160) > 0)
    m = cv2.morphologyEx(text.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    if grow > 0:
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    return m


def _encoder(out: Path, width: int, height: int, fps: float, pix_fmt: str, extra: list[str]):
    import subprocess

    return subprocess.Popen(
        [c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix_fmt,
         "-s", f"{width}x{height}", "-r", f"{fps:g}", "-i", "-", *extra, str(out)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def _close(proc, what: str) -> None:
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    if proc.wait() != 0:
        raise c.ToolError(f"ffmpeg could not write the {what}: {err.strip()[-300:]}")


def clean(video: Path | str, teardown: dict, plate: Path, mask_out: Path, *, overlays: list[int] | None = None,
          boxes: list[tuple[int, int, int, int]] = (), start: float | None = None, end: float | None = None,
          pad: int = 16, grow: int = 6, hold: int = 2, smooth: int = 2, radius: int = 5,
          whole_box: bool = False) -> dict:
    """Paint out the old captions (module docstring) into `plate`, the mask used into `mask_out`."""
    import cv2
    import numpy as np

    info = c.probe(video)
    if not info.get("is_video"):
        raise c.ToolError(f"{c.name_of(video)} is not a video.")
    w, h, fps = info["width"], info["height"], info["fps"]
    tw, th = teardown.get("width"), teardown.get("height")
    if (tw, th) != (None, None) and (tw, th) != (w, h):
        raise c.ToolError(f"The teardown is of a {tw}x{th} video, and {c.name_of(video)} is {w}x{h}: give the "
                          "teardown of this video.")
    frames = sum(1 for _ in c.decode(video, w, h, "gray"))
    regs = regions(teardown, fps, frames, w, h, overlays=overlays, boxes=boxes, start=start, end=end, pad=pad)
    if not regs:
        raise c.ToolError("Nothing to paint out: the teardown lists no text overlay in that window, and no --box "
                          "was given. Look at the frames (the teardown's check_frames too) and give the caption's "
                          "box with --box X0 Y0 X1 Y1.")
    crop = (min(r["box"][0] for r in regs), min(r["box"][1] for r in regs),
            max(r["box"][2] for r in regs), max(r["box"][3] for r in regs))
    cx0, cy0, cx1, cy1 = crop
    shot = _shots(teardown, frames)
    on = [[r for r in regs if any(a <= f <= b for a, b in r["spans"])] for f in range(frames)]

    # pass 1: each frame's own mask, inside the crop, packed
    raw: list = [None] * frames
    for f, frame in enumerate(c.decode(video, w, h, "bgr24", exact=True)):
        if f >= frames or not on[f]:
            continue
        m = np.zeros((cy1 - cy0, cx1 - cx0), np.uint8)
        for r in on[f]:
            x0, y0, x1, y1 = r["box"]
            m[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0] |= _text_pixels(frame, r["box"], grow, whole_box)
        raw[f] = np.packbits(m > 0)
    shape = (cy1 - cy0, cx1 - cx0)
    n = shape[0] * shape[1]

    masks: dict = {}

    def held(f: int):
        """The union of the masks `hold` frames around f, in f's shot, as bool (crop coordinates), or None
        when none of them has one. Kept until frame f is written."""
        if f not in masks:
            near = [g for g in range(max(0, f - hold), min(frames, f + hold + 1))
                    if raw[g] is not None and shot[g] == shot[f]]
            m = None
            if near:
                m = np.zeros(n, bool)
                for g in near:
                    m |= np.unpackbits(raw[g], count=n).astype(bool)
                m = m.reshape(shape)
            masks[f] = m
        return masks[f]

    feather = max(3, grow) | 1
    tmp_plate = plate.with_name(plate.stem + ".video.mp4")   # the picture first, then it gets the sound
    picture = _encoder(tmp_plate, w, h, fps, "bgr24",
                       ["-vf", f"scale=flags={c.EXACT_SWS}", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                        "-pix_fmt", "yuv420p"])
    mask_enc = _encoder(mask_out, w, h, fps, "gray", ["-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p"])
    window: deque = deque()   # (frame index, original frame) not written yet: they wait for `smooth` frames after
    painted = 0

    def write(f: int, original, crops: dict) -> None:
        nonlocal painted
        out = original
        full = np.zeros((h, w), np.uint8)
        m = masks.pop(f, None)
        if m is not None:
            near = [crops[g] for g in range(f - smooth, f + smooth + 1) if g in crops and shot[g] == shot[f]]
            mean = np.mean(np.stack(near).astype(np.float32), axis=0)
            soft = cv2.GaussianBlur(cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32),
                                    (feather, feather), 0)[..., None]
            soft = np.maximum(soft, m[..., None].astype(np.float32))
            out = original.copy()
            region = out[cy0:cy1, cx0:cx1].astype(np.float32)
            out[cy0:cy1, cx0:cx1] = np.clip(region * (1 - soft) + mean * soft + 0.5, 0, 255).astype(np.uint8)
            full[cy0:cy1, cx0:cx1] = m.astype(np.uint8) * 255
            painted += 1
        picture.stdin.write(np.ascontiguousarray(out).tobytes())
        mask_enc.stdin.write(full.tobytes())

    crops: dict = {}
    done = False
    try:
        for f, frame in enumerate(c.decode(video, w, h, "bgr24", exact=True)):
            if f >= frames:
                break
            region = frame[cy0:cy1, cx0:cx1]
            if held(f) is not None:
                region = cv2.inpaint(np.ascontiguousarray(region), held(f).astype(np.uint8) * 255, radius,
                                     cv2.INPAINT_TELEA)
            crops[f] = region
            window.append((f, frame))
            while window and window[0][0] <= f - smooth:
                g, original = window.popleft()
                write(g, original, crops)
                crops.pop(g - smooth, None)
        while window:
            g, original = window.popleft()
            write(g, original, crops)
        done = True
    finally:
        try:
            _close(picture, "clean plate")
            _close(mask_enc, "mask")
        finally:
            if not done:   # nothing half-made stays behind (files are never overwritten, so it would block a retry)
                tmp_plate.unlink(missing_ok=True)
                mask_out.unlink(missing_ok=True)
    try:
        sound = ["-i", c.media(video), "-map", "0:v:0", "-map", "1:a?", "-c:a", "copy"] if info.get("has_audio") \
            else ["-map", "0:v:0"]
        c.run_ffmpeg(["-i", str(tmp_plate), *sound, "-c:v", "copy", "-shortest", str(plate)])
    except Exception:
        plate.unlink(missing_ok=True)
        mask_out.unlink(missing_ok=True)
        raise
    finally:
        tmp_plate.unlink(missing_ok=True)
    return {"mode": "budget", "method": "OpenCV Telea", "frames": frames, "frames_painted": painted,
            "crop": list(crop), "regions": [{"box": list(r["box"]), "from": r["from"],
                                             "spans_s": [[round(a / fps, 3), round((b + 1) / fps, 3)]
                                                         for a, b in r["spans"]]} for r in regs],
            "params": {"pad": pad, "grow": grow, "hold": hold, "smooth": smooth, "radius": radius,
                       "mask": "box" if whole_box else "text", "from": start, "to": end}}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("inpaint", "Free caption removal (OpenCV Telea) from the teardown's overlay boxes and times.")
    p.add_argument("video")
    p.add_argument("--teardown", required=True, help="the teardown JSON of this video (tm tool teardown)")
    p.add_argument("--mode", choices=["budget"], default="budget",
                   help="budget (free, OpenCV Telea); pro is ProPainter through tm tool replicate_run (paid)")
    p.add_argument("--overlay", type=int, action="append", default=None,
                   help="a teardown overlay to paint out (0-based; default: every word_captions and text overlay)")
    p.add_argument("--box", type=int, nargs=4, action="append", default=[], metavar=("X0", "Y0", "X1", "Y1"),
                   help="a box to paint out as well (within --from/--to, else the whole video)")
    p.add_argument("--from", dest="start", type=float, default=None, help="paint only from this second")
    p.add_argument("--to", dest="end", type=float, default=None, help="paint only up to this second")
    p.add_argument("--pad", type=int, default=16, help="px added around each box")
    p.add_argument("--grow", type=int, default=6, help="px added around the text's pixels")
    p.add_argument("--hold", type=int, default=2, help="frames before and after whose masks are joined")
    p.add_argument("--smooth", type=int, default=2, help="frames before and after averaged inside the mask")
    p.add_argument("--radius", type=int, default=5, help="Telea's radius in px")
    p.add_argument("--mask", choices=["text", "box"], default="text", help="the text's pixels, or the whole box")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    c.inputs(run, a, "video", "teardown")   # a run-relative input, whatever the working folder
    teardown = c.read_json(run, a.teardown, "teardown")
    if a.start is not None and a.end is not None and a.end <= a.start:
        raise c.ToolError("--to must come after --from.")
    out = c.output(run, a.out, "wip", "inpaint", "mp4")
    mask = out.with_name(out.stem + "_mask.mp4")
    if mask.exists():
        raise c.ToolError(f"{c.rel(run, mask)} already exists, and files are never overwritten.")
    res = clean(a.video, teardown, out, mask, overlays=a.overlay, boxes=[tuple(b) for b in a.box], start=a.start,
                end=a.end, pad=a.pad, grow=a.grow, hold=a.hold, smooth=a.smooth, radius=a.radius,
                whole_box=a.mask == "box")
    parents = [c.parent_ref(run, a.video), c.parent_ref(run, c.resolve(run, a.teardown))]
    c.record(run, out, SOURCE, ", ".join(parents), params=res["params"],
             cost="0 (local)", request={"video": parents[0], "teardown": parents[1], **res["params"]},
             response={k: v for k, v in res.items() if k != "params"})
    c.record(run, mask, MASK_SOURCE, c.rel(run, out), params=res["params"], cost="0 (local)")
    outputs = [c.rel(run, out), c.rel(run, mask)]
    x0, y0, x1, y1 = res["crop"]
    return c.finish(a, {"tool": "inpaint", "outputs": outputs, "cost": 0, **{k: v for k, v in res.items()
                                                                              if k != "params"}},
                    f"Clean plate saved to {outputs[0]} (free, OpenCV Telea: {res['frames_painted']} of "
                    f"{res['frames']} frames painted), its mask to {outputs[1]}. Render the new captions over it, "
                    f"then check the residue: tm tool inpaint_mode --run R {outputs[1]} <composite> "
                    f"--crop {x0} {y0} {x1} {y1}.")


if __name__ == "__main__":
    raise SystemExit(main())
