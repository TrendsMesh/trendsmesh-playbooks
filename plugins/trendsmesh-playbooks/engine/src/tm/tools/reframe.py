"""to_4x5: a 4:5 version of a 9:16 video (R6) that keeps every overlay box inside.

    tm tool reframe --run RUN VIDEO --teardown TEARDOWN.json [--out PATH] [--json]

Decisions the brief left open (listed in the Task 10 report):
- The 4:5 frame keeps the full width: height = width x 5/4, rounded down to even for yuv420p
  (1080 -> 1350, 540 -> 674). Crop offsets are even for the same reason.
- Each overlay box (the teardown's `bbox`, the union over its whole life cycle) must sit inside the
  crop with MARGIN (24 px, lesson 12's edge distance) to spare. If no offset gives that margin, the
  margin drops to 0. Of the offsets that fit, the one closest to the centre wins.
- If no offset fits even then (boxes near both the top and the bottom), the video is padded: the
  whole 9:16 frame scaled to the 4:5 height with black bars left and right, so nothing is cut.
  The result says which it did (`method`: crop or pad) and the manifest row records it.
- A video that is not taller than 4:5 is refused (nothing to crop).
- Video is re-encoded as H.264 (CRF 18, yuv420p, faststart); audio is copied.
"""

from __future__ import annotations

import json
from pathlib import Path

from tm.tools import _common as c

MARGIN = 24


def crop_height(width: int) -> int:
    return (width * 5 // 4) // 2 * 2


def _bbox(overlay) -> list[int]:
    return list(overlay["bbox"] if isinstance(overlay, dict) else overlay.bbox)


def _offset(height: int, crop_h: int, boxes: list[list[int]], margin: int) -> int | None:
    lo, hi = 0, height - crop_h
    for _, y0, _, y1 in boxes:
        lo = max(lo, y1 + margin - crop_h)
        hi = min(hi, y0 - margin)
    lo += lo % 2  # even offsets only
    hi -= hi % 2
    if lo > hi:
        return None
    centre = (height - crop_h) // 2
    centre -= centre % 2
    return min(max(centre, lo), hi)


def plan(width: int, height: int, overlays: list) -> dict:
    crop_h = crop_height(width)
    if height <= crop_h:
        raise c.ToolError(f"The video is {width}x{height}, not taller than 4:5, so there is nothing to crop.")
    boxes = [_bbox(o) for o in overlays]
    for margin in (MARGIN, 0):
        y = _offset(height, crop_h, boxes, margin)
        if y is not None:
            return {"method": "crop", "offset_y": y, "margin": margin, "crop": [0, y, width, crop_h],
                    "size": [width, crop_h], "overlays_kept": len(boxes)}
    return {"method": "pad", "offset_y": None, "margin": None, "crop": None, "size": [width, crop_h],
            "overlays_kept": len(boxes)}


def to_4x5(video: Path | str, overlays: list, out: Path | str) -> dict:
    info = c.probe(video)
    if not info.get("has_video"):
        raise c.ToolError(f"{Path(video).name} has no video stream.")
    width, height = info["width"], info["height"]
    result = plan(width, height, overlays)
    crop_h = result["size"][1]
    if result["method"] == "crop":
        vf = f"crop={width}:{crop_h}:0:{result['offset_y']}"
    else:
        vf = f"scale=-2:{crop_h},setsar=1,pad={width}:{crop_h}:(ow-iw)/2:0:black"
    args = ["-i", c.media(video), "-map", "0:v:0", "-map", "0:a?", "-vf", vf, "-c:v", "libx264", "-crf", "18",
            "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", c.media(out)]
    c.run_ffmpeg(args)
    result["filter"] = vf
    return result


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("reframe", "Crop a 9:16 video to 4:5 keeping every overlay inside (pads if none fits).")
    p.add_argument("video")
    p.add_argument("--teardown", required=True, help="teardown JSON of this video (for its overlays)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    c.inputs(run, a, "video", "teardown")   # a run-relative input, whatever the working folder
    td = json.loads(Path(a.teardown).read_text(encoding="utf-8"))
    info = c.probe(a.video)
    if (td.get("width"), td.get("height")) != (info.get("width"), info.get("height")):
        raise c.ToolError(f"The teardown is of a {td.get('width')}x{td.get('height')} video, but "
                          f"{Path(a.video).name} is {info.get('width')}x{info.get('height')}. Run the "
                          "teardown on this video first.")
    out = c.output(run, a.out, "wip", f"{c.stem_of(a.video)}_4x5", "mp4")
    result = to_4x5(a.video, td.get("overlays") or [], out)
    parent = c.parent_ref(run, a.video)
    params = {k: result[k] for k in ("method", "offset_y", "margin", "size")}
    c.record(run, out, "tm tool reframe (ffmpeg)", parent, params=params,
             before_after=f"after (before: {parent})",
             request={"video": parent, "teardown": c.parent_ref(run, a.teardown),
                      "overlays": [_bbox(o) for o in td.get("overlays") or []]},
             response=result)
    what = (f"cropped at y={result['offset_y']}" if result["method"] == "crop"
            else "padded (no crop keeps every overlay inside)")
    return c.finish(a, {"tool": "reframe", "outputs": [c.rel(run, out)], **result},
                    f"4:5 version saved to {c.rel(run, out)}, {what}.")


if __name__ == "__main__":
    raise SystemExit(main())
