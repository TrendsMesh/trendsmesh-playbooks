"""The cover's text clear of the face (organic video's G1, issue 89).

    tm tool cover_fit --run RUN --props 03_wip/cover_<id>_vNN.props.json --frame N [--face X,Y,W,H ...]
                      [--out PATH] [--json]

The cover props are OrganicCaptions' (a frame of the final's picture and 2 to 7 words in the hook's style). The frame
is drawn without its text (`render.draft_still`, a scratch file never recorded) and the faces in it are found with
OpenCV's YuNet detector, a detection scored 0.8 or more (issue #167: its model from `tm env install video`,
`tm.face_model`), else, while that model is missing or fails its checksum, its Haar detectors (frontal and profile,
both ways); `detector` says which ran (`--face` adds one the detector missed, px at 1080×1920). A detected face is
the forehead or the eyes to the chin, so the head counts (`head`: half its height above it, a sixth of its width on
each side). The text is drawn and measured (the pixels it changes), and while it covers a head it is moved
(`offsetY`) to the nearer side where it clears the head and stays inside the 3:4 crop (y 240 to 1680), else made
smaller (`fontSize` × 0.85, not under 32; an overlay drawn in a text set through its `overlay.size`) and placed
again. Before fitting, the cover takes the run's approved text style (`styled`, issue #139): each caption's family,
accent and ink and the brand font, where the props name none, so a `*key*` marker is read as the key word and the
text gets the set's box or stroke. A detection whose head covers 70 % or more of the frame is no face: it is left out
and listed as `rejected_faces` ("covers almost the whole frame: not a face"). The cover is a still, so its props are
`"static": true` (issue #165): OrganicCaptions draws every text in its final state, the whole hook whatever the frame,
never its entrance. The text is measured whether or not a face is found; once it is clear of the heads, the picture
behind it (each block of text, from its first to its last column) is checked against its ink with WCAG's contrast
ratio: when more than a fifth of it is under 4.5:1, the words take the other ink (dark or light: an overlay's `fill`,
a plain caption's `color` with the opposite `stroke`) where that passes, else a dark `backing` box; a set with a box of
its own is not checked. The answer's `contrast` says {ink, ratio, below, fix}. A fitted cover writes the props' next version
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

from tm import face_model, organic_edit, organic_final, render
from tm.tools import _common as c

CROP = (240, 1680)      # the 3:4 crop of a 1080×1920 cover, y at 1080 wide
MARGIN = 24             # px between the text and a head
SHRINK, SMALLEST = 0.85, 32
TRIES = 10
DIFF = 40               # a pixel the text changes by more than this (0-255, any channel) is the text's
REJECT_SHARE = 0.70     # a head box covering this much of the frame or more is not a face (issue #139)
STATIC_SAID = "drawn in its final state (static: every word on, no entrance animation)"
NOT_A_FACE = "covers almost the whole frame: not a face"


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


def not_a_face(face: tuple[int, int, int, int], size: tuple[int, int]) -> bool:
    """A detection whose head box (`head`, inside the frame) covers REJECT_SHARE of the frame or more: the detector
    took the whole picture for a head (issue #139)."""
    left, top, right, bottom = head(face)
    width, height = size
    w, h = max(0, min(right, width) - max(left, 0)), max(0, min(bottom, height) - max(top, 0))
    return w * h >= REJECT_SHARE * width * height


YUNET, HAAR = "yunet", "haar"
DETECTORS = {YUNET: f"OpenCV YuNet faces (score {face_model.SCORE} or more)",
             HAAR: "OpenCV Haar faces (YuNet's model is missing or failed its checksum)"}
YUNET_SIDE = 960        # the longer side YuNet looks at (a 1080×1920 frame at half size)
_last: list[str] = []   # the detector the latest `faces` ran


def detector_used() -> str:
    """Which detector found the faces (`DETECTORS`' key): the one the latest `faces` ran, else the one it would."""
    return _last[-1] if _last else (YUNET if face_model.usable() else HAAR)


def _yunet(cv2, img, model: Path) -> list[tuple[int, int, int, int]]:
    """YuNet's detections scored SCORE or more, (x, y, w, h) in the picture's px. Its box runs from the forehead to
    the chin, as Haar's frontal one does, so `head` is the same for both."""
    height, width = img.shape[:2]
    scale = min(1.0, YUNET_SIDE / max(width, height))
    pic = cv2.resize(img, (round(width * scale), round(height * scale))) if scale < 1 else img
    size = (pic.shape[1], pic.shape[0])
    net = cv2.FaceDetectorYN.create(str(model), "", size, face_model.SCORE, 0.3, 50)
    net.setInputSize(size)
    _, rows = net.detect(pic)
    out = []
    for row in rows if rows is not None else []:
        if float(row[14]) < face_model.SCORE:
            continue
        x, y, w, h = (float(v) / scale for v in row[:4])
        out.append((int(round(x)), int(round(y)), int(round(w)), int(round(h))))
    return out


def _haar(cv2, img) -> list[tuple[int, int, int, int]]:
    """The Haar detectors' detections (frontal and profile, both ways), (x, y, w, h)."""
    side = max(48, img.shape[1] // 16)
    out = []
    for name, flip in (("haarcascade_frontalface_default.xml", False), ("haarcascade_profileface.xml", False),
                       ("haarcascade_profileface.xml", True)):
        cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / name))
        pic = cv2.flip(img, 1) if flip else img
        for x, y, w, h in cascade.detectMultiScale(pic, scaleFactor=1.1, minNeighbors=6, minSize=(side, side)):
            x = img.shape[1] - x - w if flip else x
            out.append((int(x), int(y), int(w), int(h)))
    return out


def faces(png: Path, rejected: list | None = None) -> list[tuple[int, int, int, int]]:
    """The faces in a picture, (x, y, w, h): OpenCV's YuNet detector, a detection scored 0.8 or more (issue #167:
    a hoodie, a hand or a site capture is no face), when its model is in the data folder and passes its checksum
    (`tm.face_model`), else the Haar detectors; `detector_used` says which ran. A detection that is no face
    (`not_a_face`) is left out, and added to `rejected` as {face, reason} when a list is given."""
    import cv2
    import numpy as np

    raw = np.fromfile(str(png), dtype=np.uint8)
    model = face_model.usable()
    detections, used = None, HAAR
    if model is not None:
        img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if img is None:
            raise c.ToolError(f"{c.name_of(png)} cannot be read as a picture.")
        try:
            detections, used = _yunet(cv2, img, model), YUNET
        except (cv2.error, AttributeError):   # an OpenCV without YuNet, or a model it cannot load: Haar's
            detections = None
    if detections is None:
        img = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise c.ToolError(f"{c.name_of(png)} cannot be read as a picture.")
        detections = _haar(cv2, img)
    _last[:] = [used]
    found: list[tuple[int, int, int, int]] = []
    for box in detections:
        if not_a_face(box, (img.shape[1], img.shape[0])):
            if rejected is not None and not any(r["face"] == list(box) for r in rejected):
                rejected.append({"face": list(box), "reason": NOT_A_FACE})
            continue
        if not any(_overlaps(head(box), head(f), 0) for f in found):
            found.append(box)
    return found


def _pixels(png: Path, width: int, height: int):
    import numpy as np

    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-i", c.media(png), "-vf",
                          f"scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape((height, width, 3)).astype(np.int16)


def _changed(plain_px, texted_px):
    """The pixels the text changes (a bool mask)."""
    return abs(texted_px - plain_px).max(axis=2) > DIFF


def _bounds(changed) -> tuple[int, int, int, int] | None:
    import numpy as np

    rows, cols = np.flatnonzero(changed.any(axis=1)), np.flatnonzero(changed.any(axis=0))
    if rows.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def text_box(plain: Path, texted: Path, width: int, height: int) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of what the text changes in the frame, or None when it changes nothing."""
    return _bounds(_changed(_pixels(plain, width, height), _pixels(texted, width, height)))


# --- the contrast behind the text (issue #165) ---------------------------------------------------------------

CONTRAST = 4.5          # WCAG's ratio for text (AA)
BELOW_SHARE = 0.2       # the text fails when more of its pixels than this sit on a picture it contrasts less with
DARK_INK, LIGHT_INK = "#111111", "#FFFFFF"
BOXED = ("pill", "native", "block", "quiet")   # the sets whose overlays sit in a box of their own (OverlayLooks.tsx)
INK_FIX = {DARK_INK: "dark ink", LIGHT_INK: "light ink"}
BACKING = "backing"


def _lum(rgb):
    """WCAG's relative luminance of rgb values (0-255, last axis the channels)."""
    import numpy as np

    s = np.asarray(rgb, dtype=float) / 255
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)
    return lin @ np.array([0.2126, 0.7152, 0.0722])



def contrast_ratio(a: str, b: str) -> float:
    """WCAG's contrast ratio of two colours #RRGGBB, 1 to 21."""
    la, lb = organic_edit._luminance(a), organic_edit._luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def ink_of(cap: dict) -> str | None:
    """The colour of a caption's words where nothing of its own is behind them, else None (a box, a backing, the
    key number or the end card's dimmed picture: they carry their own contrast)."""
    ov = cap.get("overlay") if isinstance(cap.get("overlay"), dict) else None
    colour = None
    if ov is not None:
        family, kind = ov.get("family"), ov.get("kind", "hook")
        if (ov.get("backing") or family in BOXED or kind in ("number", "end")
                or (kind == "label" and family in ("marker", "pop"))):
            return None
        colour = ov.get("fill")
    elif cap.get("style") in ("caption", "note"):
        if cap.get("backing") or cap.get("look") in BOXED:
            return None
        colour = None if cap.get("look") else cap.get("color")
    else:
        return None                  # the plain hook: its own box
    return colour.upper() if isinstance(colour, str) and organic_edit.COLOUR.fullmatch(colour) else LIGHT_INK


def _inkable(cap: dict) -> bool:
    """The ink of the caption can be switched: an overlay (its `fill`) or a plain caption or note (`color`); a caption
    drawn in a set takes a backing instead."""
    return isinstance(cap.get("overlay"), dict) or not cap.get("look")


BLOCK_GAP = 48          # px: rows of text closer than this are one block of text


def _blocks(changed):
    """The area behind the text: each block of text (rows of changed pixels, gaps under BLOCK_GAP closed) from its
    first changed column to its last. Not only the changed pixels: where the text's colour is the picture's, the text
    changes nothing, and that is the place it cannot be read."""
    import numpy as np

    region = np.zeros_like(changed)
    rows = np.flatnonzero(changed.any(axis=1))
    if rows.size == 0:
        return region
    starts = [rows[0], *rows[1:][np.diff(rows) > BLOCK_GAP]]
    ends = [*rows[:-1][np.diff(rows) > BLOCK_GAP], rows[-1]]
    for a, b in zip(starts, ends):
        cols = np.flatnonzero(changed[a:b + 1].any(axis=0))
        region[a:b + 1, cols[0]:cols[-1] + 1] = True
    return region


def contrast(plain_px, changed, caps: list[dict]) -> dict | None:
    """The text's contrast on the picture under it (`plain_px` behind each block of `changed`, `_blocks`): {ink,
    ratio (the median, WCAG's),
    below (the share of the text's pixels under CONTRAST), fix: None | "dark ink" | "light ink" | "backing"}. None
    when every caption carries its own box, or the text changes nothing. A failing text takes the other ink when it
    passes there and every caption can switch it, else a backing."""
    import numpy as np

    open_caps = [cap for cap in caps if ink_of(cap) is not None]
    if not open_caps or not changed.any():
        return None
    behind = _lum(plain_px[_blocks(changed)])

    def check(ink: str) -> tuple[float, float]:
        li = organic_edit._luminance(ink)
        ratios = (np.maximum(behind, li) + 0.05) / (np.minimum(behind, li) + 0.05)
        return float(np.median(ratios)), float((ratios < CONTRAST).mean())

    worst = None
    for ink in dict.fromkeys(ink_of(cap) for cap in open_caps):
        ratio, below = check(ink)
        if worst is None or below > worst[2]:
            worst = (ink, ratio, below)
    ink, ratio, below = worst
    fix = None
    if below > BELOW_SHARE:
        other = DARK_INK if organic_edit._luminance(ink) >= 0.18 else LIGHT_INK
        fix = INK_FIX[other] if all(_inkable(cap) for cap in open_caps) and check(other)[1] <= BELOW_SHARE \
            else BACKING
    return {"ink": ink, "ratio": round(ratio, 1), "below": round(below, 2), "fix": fix}


def apply_fix(caps: list[dict], fix: str) -> None:
    """The contrast's fix on every caption without a box of its own: the other ink (an overlay's `fill`, a caption's
    `color` with the opposite `stroke`), or a backing box."""
    for cap in [cap for cap in caps if ink_of(cap) is not None]:
        ov = cap.get("overlay") if isinstance(cap.get("overlay"), dict) else None
        if fix == BACKING:
            (ov if ov is not None else cap)["backing"] = True
            continue
        ink = next(k for k, v in INK_FIX.items() if v == fix)
        if ov is not None:
            ov["fill"] = ink
        else:
            cap["color"], cap["stroke"] = ink, LIGHT_INK if ink == DARK_INK else "#000000"


def contrast_said(found: dict | None) -> str:
    """The contrast in words, for the answer."""
    if found is None or found.get("ink") is None:
        return "The text carries its own box, so its contrast on the picture is its set's."
    if found["fix"] is None:
        return f"The text reads on the picture: contrast {found['ratio']:g}:1 (WCAG asks {CONTRAST:g}:1)."
    done = ("a dark box is behind it now" if found["fix"] == BACKING
            else f"its words are {'dark' if found['fix'] == 'dark ink' else 'light'} now")
    return (f"The picture under the text is too close to its ink: contrast {found['ratio']:g}:1, "
            f"{round(found['below'] * 100)} % of it under {CONTRAST:g}:1, so {done}.")


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


OVERLAY_SIZES = {"hook": 62, "label": 40, "number": 150, "cta": 54, "end": 96}   # OverlayLooks.tsx SIZES


def size_of(cap: dict) -> float:
    """The size a caption is drawn at, px at 1080: an overlay in a family its `overlay.size`, else its kind's."""
    ov = cap.get("overlay") if isinstance(cap.get("overlay"), dict) else None
    if ov is not None:
        return float(ov.get("size") or OVERLAY_SIZES.get(ov.get("kind", "hook"), 62))
    return float(cap.get("fontSize") or 58)


def set_size(cap: dict, size: float) -> None:
    """Draw the caption at `size` (px at 1080): an overlay in a family through `overlay.size`."""
    if isinstance(cap.get("overlay"), dict):
        cap["overlay"]["size"] = size
    else:
        cap["fontSize"] = size


def fit(run, data: dict, frame: int, given: list[tuple], scratch: Path,
        rejected: list | None = None) -> tuple[dict, list[tuple], list[str], dict | None]:
    """(the fitted props, the faces, what was changed, in words, the text's contrast on the picture, `contrast`);
    detections that are no face go to `rejected`. The text is measured whether or not a face is found: once it is
    clear of every head, its contrast is checked, and a failing one fixed (the other ink, or a backing) and the text
    measured again."""
    width, height = int(data.get("width") or 1080), int(data.get("height") or 1920)
    k = width / 1080
    plain = _draft(run, {**data, "captions": []}, frame, scratch / "plain.png")
    found = [*(faces(plain) if rejected is None else faces(plain, rejected)), *given]
    heads = [tuple(round(v * k) for v in head(f)) for f in found]
    bounds = {"top": round(CROP[0] * k), "bottom": round(CROP[1] * k), "margin": round(MARGIN * k)}
    data = json.loads(json.dumps(data))
    caps = [x for x in data.get("captions") or [] if isinstance(x, dict)]
    changes: list[str] = []
    checked: dict | None = None
    plain_px = _pixels(plain, width, height) if caps else None
    for n in range(TRIES):
        if not caps:
            return data, found, changes, checked
        changed = _changed(plain_px, _pixels(_draft(run, data, frame, scratch / f"text_{n}.png"), width, height))
        box = _bounds(changed)
        if box is None:
            return data, found, changes, checked
        shift = clear_shift(box, heads, **bounds) if heads else 0
        if shift == 0:
            if checked is None:
                checked = contrast(plain_px, changed, caps) or {"ink": None, "fix": None}
                if checked["fix"]:
                    apply_fix(caps, checked["fix"])
                    changes.append(f"contrast {checked['ratio']:g}:1 behind the text: "
                                   + ("a backing box" if checked["fix"] == BACKING else checked["fix"]))
                    continue          # measured again: a backing makes the text's box larger
            return data, found, changes, checked
        if shift is not None:
            for cap in caps:
                cap["offsetY"] = round(float(cap.get("offsetY") or 0) + shift / k)
            changes.append(f"moved {'up' if shift < 0 else 'down'} {abs(round(shift / k))} px")
            continue
        sizes = [size_of(cap) for cap in caps]
        if all(s <= SMALLEST for s in sizes):
            break
        for cap, size in zip(caps, sizes):
            set_size(cap, max(SMALLEST, round(size * SHRINK)))
        changes.append(f"made smaller: fontSize {', '.join(f'{s:g}' for s in sizes)} → "
                       f"{', '.join(f'{size_of(cap):g}' for cap in caps)}")
    raise c.ToolStop("The cover's text cannot clear the face inside the 3:4 crop (y 240 to 1680) even at its "
                     f"smallest ({'; '.join(changes) or 'no change helped'}). Nothing was written. Pick another frame "
                     "(the face smaller or to one side), or fewer words, and run it again.")


def styled(run, data: dict) -> tuple[dict, str | None]:
    """(the cover props in the run's approved text style, what was filled in words; None when nothing was): each
    caption's family (look), accent and ink and the brand font, where the props name none (issue #139). A hook
    drawn in a family reads `*key*` as the key word; a plain hook box (a style with no look) draws the stars, so
    they are dropped there."""
    approved = organic_edit.approved_style(run)
    if approved is None:
        return data, None
    rel, _, style = approved
    look, accent = style.get("look"), style.get("accent")
    tint = {"accent": accent, "ink": organic_edit.accent_ink(accent)} if accent else {}
    out = json.loads(json.dumps(data))
    for cap in [x for x in out.get("captions") or [] if isinstance(x, dict)]:
        if cap.get("style") == "caption":
            if look and not cap.get("look"):
                cap["look"] = look
            if accent and not cap.get("ink"):
                cap["ink"] = tint["ink"]
            continue
        given = cap.get("overlay") if isinstance(cap.get("overlay"), dict) else None
        if given is not None or look:
            ov = dict(given or {})
            ov.setdefault("kind", "hook")
            if look:
                ov.setdefault("family", look)
            if accent:
                ov.setdefault("accent", accent)
            if ov.get("accent") and organic_edit.COLOUR.fullmatch(str(ov["accent"])):
                ov.setdefault("ink", organic_edit.accent_ink(ov["accent"]))
            if ov.get("family"):
                if given is None and isinstance(cap.get("fontSize"), (int, float)):
                    ov.setdefault("size", cap["fontSize"])   # a family sizes by kind: keep the cover's own size
                cap["overlay"] = ov
                continue
        group = style.get("overlays") if isinstance(style.get("overlays"), dict) else {}
        for key in ("color", "background"):
            if not cap.get(key) and group.get(key):
                cap[key] = group[key]
        cap["text"] = str(cap.get("text", "")).replace("*", "")
    if style.get("font") and not out.get("brandFont"):
        out["brandFont"] = style["font"]
    if out == data:
        return data, None
    return out, f"drawn in the approved text style ({rel})"


def _next_props(run, rel: str) -> Path:
    stem = re.sub(r"_v\d+$", "", Path(rel).name.removesuffix(".json").removesuffix(".props"))
    return run.next_version("wip", stem or "cover", "props.json")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("cover_fit", "The cover's text clear of the face: moved or made smaller, then drawn.")
    p.add_argument("--props", required=True, help="the cover's OrganicCaptions props, relative to the run folder")
    p.add_argument("--frame", type=int, required=True, help="the frame of the props the cover is")
    p.add_argument("--face", action="append", default=[], help="X,Y,W,H of a face the detector missed (px, 1080×1920)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    path = c.resolve(run, a.props)
    try:
        rel = c.rel(run, path)
    except ValueError:
        raise c.ToolError(f"The cover props {c.name_of(a.props)} must be inside the run folder.") from None
    data, filled = styled(run, render._check_props(run, "OrganicCaptions", path))
    settled = None
    if data.get("static") is not True:     # a cover is a still: the whole hook, never its entrance (issue #165)
        data, settled = {**data, "static": True}, STATIC_SAID
    given = [_box(f) for f in a.face]
    scratch = Path(tempfile.mkdtemp(prefix="tm-cover-"))
    rejected: list[dict] = []
    _last.clear()
    try:
        fitted, found, changes, checked = fit(run, data, a.frame, given, scratch, rejected)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    changes = [x for x in (filled, settled) if x] + changes
    props_path = path
    if changes:
        props_path = _next_props(run, rel)
        c.write_json(props_path, fitted, newline="\n")
        c.record(run, props_path, "tm tool cover_fit", rel, params={"faces": [list(f) for f in found],
                                                                     "rejected_faces": rejected,
                                                                     "detector": detector_used(),
                                                                     "contrast": checked,
                                                                     "changes": changes}, cost="0 (local)")
    pid = organic_final.idea_id(run) or "cover"
    out = c.output(run, a.out, organic_final.KITS, f"cover_{pid}", "png")
    done = render.still(run, "OrganicCaptions", props_path, a.frame, out)
    moves = [x for x in changes if x not in (filled, settled) and not x.startswith("contrast ")]
    said = ("No face was found in the frame: look at the cover, and give --face X,Y,W,H (px at 1080×1920) for a face "
            "the detector missed." if not found else
            f"The text is clear of {len(found)} face(s)" + (f": {'; '.join(moves)}." if moves else ", as it was."))
    if filled:
        said += f" The text is {filled}."
    if settled:
        said += f" It is {settled}."
    if checked is not None:
        said += " " + contrast_said(checked)
    if rejected:
        said += (f" {len(rejected)} detection(s) left out: they cover almost the whole frame, so they are not a "
                 "face.")
    payload = {"tool": "cover_fit", "outputs": [c.rel(run, done)], "props": c.rel(run, props_path),
               "faces": [list(f) for f in found], "detector": detector_used(), "rejected_faces": rejected,
               "contrast": checked, "changes": changes, "message": said}
    return c.finish(a, payload, f"Wrote {c.rel(run, done)}. {said} Then: tm tool deliver cover --run <run> "
                                f"{c.rel(run, done)}.")


if __name__ == "__main__":
    raise SystemExit(main())
