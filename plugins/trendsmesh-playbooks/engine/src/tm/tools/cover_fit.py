"""The cover's text clear of the face (organic video's G1, issue 89).

    tm tool cover_fit --run RUN --props 03_wip/cover_<id>_vNN.props.json --frame N [--face X,Y,W,H ...]
                      [--out PATH] [--json]

The cover props are OrganicCaptions' (a frame of the final's picture and 2 to 7 words in the hook's style). The frame
is drawn without its text (`render.draft_still`, a scratch file never recorded) and the faces in it are found with
OpenCV's Haar detectors (frontal and profile, both ways; `--face` adds one the detector missed, px at 1080×1920). A
detected face is the eyes to the chin, so the head counts (`head`: half its height above it, a sixth of its width on
each side). The text is drawn and measured (the pixels it changes), and while it covers a head it is moved
(`offsetY`) to the nearer side where it clears the head and stays inside the 3:4 crop (y 240 to 1680), else made
smaller (`fontSize` × 0.85, not under 32) and placed again. A fitted cover writes the props' next version
(`03_wip/cover_<id>_vNN.props.json`); then the cover is drawn from them with `tm render still` into
`04_final/kits/cover_<id>_vNN.png` (the next version), ready for `tm tool deliver cover`. Free and local.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tm import organic_final, render
from tm.tools import _common as c

CROP = (240, 1680)      # the 3:4 crop of a 1080×1920 cover, y at 1080 wide
MARGIN = 24             # px between the text and a head
SHRINK, SMALLEST = 0.85, 32
TRIES = 10
DIFF = 40               # a pixel the text changes by more than this (0-255, any channel) is the text's


def head(face: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the head a detected face (x, y, w, h) belongs to."""
    x, y, w, h = face
    return (round(x - 0.15 * w), round(y - 0.5 * h), round(x + w + 0.15 * w), y + h)


def _overlaps(a: tuple, b: tuple, margin: int) -> bool:
    return a[0] < b[2] + margin and b[0] < a[2] + margin and a[1] < b[3] + margin and b[1] < a[3] + margin


def clear_shift(text: tuple, heads: list[tuple], *, top: int, bottom: int, margin: int) -> int | None:
    """How far to move the text (px, negative is up) so it clears every head and stays within top..bottom: 0 when it
    is clear already, None when neither side has room."""
    hit = [h for h in heads if _overlaps(text, h, margin)]
    if not hit:
        return 0
    up = min(h[1] for h in hit) - margin - text[3]
    down = max(h[3] for h in hit) + margin - text[1]
    options = []
    for dy in (up, down):
        moved = (text[0], text[1] + dy, text[2], text[3] + dy)
        if moved[1] >= top and moved[3] <= bottom and not any(_overlaps(moved, h, margin) for h in heads):
            options.append(dy)
    return min(options, key=abs) if options else None


def faces(png: Path) -> list[tuple[int, int, int, int]]:
    """The faces OpenCV's Haar detectors find in a picture, (x, y, w, h)."""
    import cv2
    import numpy as np

    img = cv2.imdecode(np.fromfile(str(png), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise c.ToolError(f"{c.name_of(png)} cannot be read as a picture.")
    side = max(48, img.shape[1] // 16)
    found: list[tuple[int, int, int, int]] = []
    for name, flip in (("haarcascade_frontalface_default.xml", False), ("haarcascade_profileface.xml", False),
                       ("haarcascade_profileface.xml", True)):
        cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / name))
        pic = cv2.flip(img, 1) if flip else img
        for x, y, w, h in cascade.detectMultiScale(pic, scaleFactor=1.1, minNeighbors=6, minSize=(side, side)):
            x = img.shape[1] - x - w if flip else x
            box = (int(x), int(y), int(w), int(h))
            if not any(_overlaps(head(box), head(f), 0) for f in found):
                found.append(box)
    return found


def _pixels(png: Path, width: int, height: int):
    import numpy as np

    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-i", c.media(png), "-vf",
                          f"scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape((height, width, 3)).astype(np.int16)


def text_box(plain: Path, texted: Path, width: int, height: int) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of what the text changes in the frame, or None when it changes nothing."""
    import numpy as np

    changed = np.abs(_pixels(texted, width, height) - _pixels(plain, width, height)).max(axis=2) > DIFF
    rows, cols = np.flatnonzero(changed.any(axis=1)), np.flatnonzero(changed.any(axis=0))
    if rows.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _draft(run, data: dict, frame: int, dest: Path) -> Path:
    return render.draft_still(run, "OrganicCaptions", data, frame, dest)


def _box(text: str) -> tuple[int, int, int, int]:
    try:
        x, y, w, h = (int(round(float(v))) for v in text.split(","))
    except ValueError:
        raise c.ToolError(f"--face {text} must be X,Y,W,H in px at 1080×1920 (e.g. 380,300,320,360).") from None
    if w <= 0 or h <= 0:
        raise c.ToolError(f"--face {text} needs a width and a height above 0.")
    return x, y, w, h


def fit(run, data: dict, frame: int, given: list[tuple], scratch: Path) -> tuple[dict, list[tuple], list[str]]:
    """(the fitted props, the faces, what was changed, in words)."""
    width, height = int(data.get("width") or 1080), int(data.get("height") or 1920)
    k = width / 1080
    plain = _draft(run, {**data, "captions": []}, frame, scratch / "plain.png")
    found = [*faces(plain), *given]
    heads = [tuple(round(v * k) for v in head(f)) for f in found]
    bounds = {"top": round(CROP[0] * k), "bottom": round(CROP[1] * k), "margin": round(MARGIN * k)}
    data = json.loads(json.dumps(data))
    caps = [x for x in data.get("captions") or [] if isinstance(x, dict)]
    changes: list[str] = []
    for n in range(TRIES):
        if not heads or not caps:
            return data, found, changes
        box = text_box(plain, _draft(run, data, frame, scratch / f"text_{n}.png"), width, height)
        if box is None:
            return data, found, changes
        shift = clear_shift(box, heads, **bounds)
        if shift == 0:
            return data, found, changes
        if shift is not None:
            for cap in caps:
                cap["offsetY"] = round(float(cap.get("offsetY") or 0) + shift / k)
            changes.append(f"moved {'up' if shift < 0 else 'down'} {abs(round(shift / k))} px")
            continue
        sizes = [float(cap.get("fontSize") or 58) for cap in caps]
        if all(s <= SMALLEST for s in sizes):
            break
        for cap, size in zip(caps, sizes):
            cap["fontSize"] = max(SMALLEST, round(size * SHRINK))
        changes.append(f"made smaller: fontSize {', '.join(f'{s:g}' for s in sizes)} → "
                       f"{', '.join(str(cap['fontSize']) for cap in caps)}")
    raise c.ToolStop("The cover's text cannot clear the face inside the 3:4 crop (y 240 to 1680) even at its "
                     f"smallest ({'; '.join(changes) or 'no change helped'}). Nothing was written. Pick another frame "
                     "(the face smaller or to one side), or fewer words, and run it again.")


def _next_props(run, rel: str) -> Path:
    stem = re.sub(r"_v\d+$", "", Path(rel).name.removesuffix(".json").removesuffix(".props"))
    return run.next_version("wip", stem or "cover", "props.json")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("cover_fit", "The cover's text clear of the face: moved or made smaller, then drawn.")
    p.add_argument("--props", required=True, help="the cover's OrganicCaptions props in the run")
    p.add_argument("--frame", type=int, required=True, help="the frame of the props the cover is")
    p.add_argument("--face", action="append", default=[], help="X,Y,W,H of a face the detector missed (px, 1080×1920)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    path = c.resolve(run, a.props)
    try:
        rel = c.rel(run, path)
    except ValueError:
        raise c.ToolError(f"The cover props {c.name_of(a.props)} must be inside the run folder.") from None
    data = render._check_props(run, "OrganicCaptions", path)
    given = [_box(f) for f in a.face]
    scratch = Path(tempfile.mkdtemp(prefix="tm-cover-"))
    try:
        fitted, found, changes = fit(run, data, a.frame, given, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    props_path = path
    if changes:
        props_path = _next_props(run, rel)
        c.write_json(props_path, fitted, newline="\n")
        c.record(run, props_path, "tm tool cover_fit", rel, params={"faces": [list(f) for f in found],
                                                                     "changes": changes}, cost="0 (local)")
    pid = organic_final.idea_id(run) or "cover"
    out = c.output(run, a.out, organic_final.KITS, f"cover_{pid}", "png")
    done = render.still(run, "OrganicCaptions", props_path, a.frame, out)
    said = ("No face was found in the frame: look at the cover, and give --face X,Y,W,H (px at 1080×1920) for a face "
            "the detector missed." if not found else
            f"The text is clear of {len(found)} face(s)" + (f": {'; '.join(changes)}." if changes else ", as it was."))
    payload = {"tool": "cover_fit", "outputs": [c.rel(run, done)], "props": c.rel(run, props_path),
               "faces": [list(f) for f in found], "changes": changes, "message": said}
    return c.finish(a, payload, f"Wrote {c.rel(run, done)}. {said} Then: tm tool deliver cover --run <run> "
                                f"{c.rel(run, done)}.")


if __name__ == "__main__":
    raise SystemExit(main())
