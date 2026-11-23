"""The edit's layers kept off faces and off each other, and no capture scaled up (Create an ad's S7, CA10 and CA11,
issue 96).

    tm tool layer_check --run RUN EDIT --layers 03_wip/edit_layers_vNN.json [--json]

The layers file says what the edit (S6) draws, bottom to top, in seconds of the edit and px of its frame:

    {"layers": [{"id", "kind" (picture, caption, overlay), "start", "end",
                 "box": [x, y, w, h] (where it is drawn; a picture without one fills the frame),
                 "src" (a picture: the video or image in the run it shows),
                 "from" (a video: its own second at the layer's start, 0 by default),
                 "crop": [x, y, w, h] (a picture: the part of the source it shows, px of the source; all of it by
                          default),
                 "on": "<id>" (drawn on that layer on purpose, as a chip on its card),
                 "place", "offsetY", "role" (a text: where `tm ad text` put it, and its overlay's kind or caption)}]}

The text is two layers, as organic video's edit has it: `caption` (under the speech, at the bottom) and `overlay`
(the hook, a number, a tag, a code chip, the logo); a window, a scene card or a capture is a `picture`. Three checks:

- **faces**: for each picture under a layer, at the times both are shown (their first and last moment, the middle and
  every second between, at most 12), the faces in the picture's own frame (`tm tool cover_fit`'s detector: YuNet, a
  detection scored 0.8 or more, else Haar when its model is missing; `detector` says which ran; a head runs from
  above the forehead to the chin), placed in the edit's frame through the picture's crop and box. A layer over a head
  is a collision (a caption over the mouth, a chip over the chin, a window over a face). A text's carries a
  `suggestion` (issue #167): `{"place": top | middle | bottom, "offsetY": px at 1080 from that place}`, the place
  that clears every head seen then and the box of every other text shown with it (at its suggested place when it
  was given one), tried in the safe zone's thirds: a hook (`role`) at the top, then the middle, then the bottom; the
  captions at the bottom, then the middle; any other where it is (`place`, else its box's third), then the nearest;
  from the place itself outwards in 10 px steps; else null (no size fix: a smaller text over a face is still over
  it); its message names it. A picture over a face has none. A detection whose head covers 70 % or more of the frame
  is no face: it is listed under `rejected_faces`.
- **layers**: two layers shown together whose boxes overlap, neither filling the frame, unless one is `on` the other
  (a tag running under the caption band).
- **sharpness**: a still (png, jpg, webp) drawn larger than its own pixels (more than 5 % up): capture it sharper
  instead (`tm tool site capture` at a device scale of 2 to 3, or of the element itself).

Writes `<edit dir>/qa/<edit stem>_layers_vNN.json` (the next version): {"edit", "layers": {"file", "sha256"}, "size",
"detector" (yunet, haar), "faces": [{"layer", "at", "head"}], "rejected_faces": [{"layer", "at", "face", "reason"}], "collisions": [{"kind"
(face, layer, scaled_up), "layer", "with", "at", "box", "other", "suggestion" (a face's), "message"}], "message"}. `tm ad check edit` refuses an edit whose latest layer check has a collision: move
the layer, render the next version (S6) and check that. Free and local (the breakdown tools).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tm import organic_qa
from tm.tools import _common as c
from tm.tools import cover_fit

KINDS = ("picture", "caption", "overlay")
STILLS = (".png", ".jpg", ".jpeg", ".webp")
SAMPLES = 12          # the most times a picture is looked at under one layer
STEP = 1.0            # seconds between those times
EDGE = 0.05           # seconds inside the first and the last moment both layers are shown
TOGETHER = 0.04       # two layers shown together less than this (a frame) are not shown together
UPSCALE = 1.05        # a still drawn more than 5 % larger than its pixels is scaled up
FULL = 0.98           # a box covering this much of the frame both ways fills it
SAFE_TOP, SAFE_BOTTOM = 260, 380   # the safe zone a suggested move stays in, px at 1080 (OrganicCaptions SAFE_1080)
PLACES = ("top", "middle", "bottom")   # OrganicCaptions' places, the safe zone's thirds
STEP_PX = 10          # px at 1080 between the offsets a placement tries
TEXT_MARGIN = 12      # px at 1080 a placed text keeps from another text


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _box(value: object, what: str) -> tuple[float, float, float, float]:
    if not (isinstance(value, list) and len(value) == 4 and all(_num(v) for v in value)
            and value[2] > 0 and value[3] > 0):
        raise c.ToolError(f"{what} must be [x, y, w, h] in px, with a width and a height above 0.")
    return tuple(float(v) for v in value)


def read_layers(run, path: Path, size: tuple[int, int]) -> list[dict]:
    """The layers of a layers file, checked; a ToolError names the first thing wrong."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise c.ToolError(f"{c.name_of(path)} cannot be read as JSON ({exc}).") from None
    layers = data.get("layers") if isinstance(data, dict) else None
    if not isinstance(layers, list) or not layers:
        raise c.ToolError(f"{c.name_of(path)} needs \"layers\": the edit's layers, bottom to top.")
    width, height = size
    out, seen = [], set()
    for n, layer in enumerate(layers, 1):
        where = f"layers[{n}]"
        if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or not layer["id"].strip():
            raise c.ToolError(f"{where} needs an id.")
        lid = layer["id"]
        if lid in seen:
            raise c.ToolError(f"{where}: the id {lid!r} is given twice.")
        seen.add(lid)
        kind = layer.get("kind")
        if kind not in KINDS:
            raise c.ToolError(f"{where} ({lid}): kind is one of {', '.join(KINDS)}.")
        start, end = layer.get("start"), layer.get("end")
        if not (_num(start) and _num(end) and 0 <= start < end):
            raise c.ToolError(f"{where} ({lid}) needs a start and an end in seconds, the end after the start.")
        row = {"id": lid, "kind": kind, "start": float(start), "end": float(end), "on": layer.get("on"),
               "n": n, "fontSize": float(layer["fontSize"]) if _num(layer.get("fontSize")) else None,
               "place": layer.get("place") if layer.get("place") in PLACES else None,
               "role": layer.get("role") if isinstance(layer.get("role"), str) else None}
        if layer.get("box") is None and kind == "picture":
            row["box"] = (0.0, 0.0, float(width), float(height))
        else:
            row["box"] = _box(layer.get("box"), f"{where} ({lid}) box")
        if kind == "picture":
            src = layer.get("src")
            if not isinstance(src, str) or not src.strip():
                raise c.ToolError(f"{where} ({lid}) is a picture: give src, the video or image in the run it shows.")
            found = c.resolve(run, src, missing_ok=True)
            if not found.is_file():
                raise c.ToolError(f"{where} ({lid}): its src {c.name_of(src)} does not exist.")
            row["src"], row["path"] = src, found
            row["from"] = float(layer["from"]) if _num(layer.get("from")) else 0.0
            row["crop"] = _box(layer["crop"], f"{where} ({lid}) crop") if layer.get("crop") is not None else None
        out.append(row)
    return out


def fills(box: tuple, size: tuple[int, int]) -> bool:
    x, y, w, h = box
    return x <= size[0] * (1 - FULL) and y <= size[1] * (1 - FULL) and w >= size[0] * FULL and h >= size[1] * FULL


def _edges(box: tuple) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return x, y, x + w, y + h


def overlap(a: tuple, b: tuple) -> bool:
    """Two (left, top, right, bottom) boxes share some area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def together(a: dict, b: dict) -> tuple[float, float] | None:
    lo, hi = max(a["start"], b["start"]), min(a["end"], b["end"])
    return (lo, hi) if hi - lo >= TOGETHER else None


def times(lo: float, hi: float) -> list[float]:
    """The moments a picture is looked at while both layers are shown (the module docstring)."""
    first, last = min(lo + EDGE, (lo + hi) / 2), max(hi - EDGE, (lo + hi) / 2)
    found = {round(first, 2), round((lo + hi) / 2, 2), round(last, 2)}
    t = first + STEP
    while t < last and len(found) < SAMPLES:
        found.add(round(t, 2))
        t += STEP
    return sorted(found)[:SAMPLES]


def place(head: tuple, src_size: tuple[int, int], crop: tuple | None, box: tuple) -> tuple[int, int, int, int] | None:
    """A head (left, top, right, bottom) in the source's pixels, in the edit's frame through the crop and the box;
    None when the crop leaves it out."""
    cx, cy, cw, ch = crop or (0.0, 0.0, float(src_size[0]), float(src_size[1]))
    left, top = max(head[0], cx), max(head[1], cy)
    right, bottom = min(head[2], cx + cw), min(head[3], cy + ch)
    if right <= left or bottom <= top:
        return None
    bx, by, bw, bh = box
    kx, ky = bw / cw, bh / ch
    return (round(bx + (left - cx) * kx), round(by + (top - cy) * ky), round(bx + (right - cx) * kx),
            round(by + (bottom - cy) * ky))


def _frame(picture: dict, at: float, dest: Path) -> Path:
    """The picture's own frame shown at the edit's second `at`, as a PNG (a still is itself)."""
    if picture["path"].suffix.lower() in STILLS:
        return picture["path"]
    if dest.is_file():
        return dest
    second = picture["from"] + (at - picture["start"])
    length = c.probe(picture["path"]).get("duration")
    if isinstance(length, (int, float)) and length > 0:
        second = min(second, max(0.0, length - 0.05))
    subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", "-ss", f"{max(0.0, second):.3f}", "-i",
                    c.media(picture["path"]), "-frames:v", "1", c.media(dest)], capture_output=True, check=True)
    if not dest.is_file():
        raise c.ToolError(f"No frame of {picture['src']} at {second:.2f} s: is its `from` inside it?")
    return dest


def _size(path: Path) -> tuple[int, int]:
    found = c.probe(path)
    width, height = found.get("width"), found.get("height")
    if not width or not height:
        raise c.ToolError(f"{c.name_of(path)} has no picture size.")
    return int(width), int(height)


def _zones(size: tuple[int, int], h: float) -> tuple[float, float, dict[str, float], dict[str, tuple]]:
    """(the safe zone's top, its bottom, each place's y for a box `h` tall as OrganicCaptions puts it, each place's
    band of the box's centre: the safe zone in thirds), px of the frame."""
    k = size[0] / 1080
    top, bottom = SAFE_TOP * k, size[1] - SAFE_BOTTOM * k
    third = (bottom - top) / 3
    anchors = {"top": top, "middle": (top + bottom) / 2 - h / 2, "bottom": bottom - h}
    bands = {"top": (top, top + third), "middle": (top + third, top + 2 * third), "bottom": (top + 2 * third, bottom)}
    return top, bottom, anchors, bands


def _order(layer: dict, box: tuple, size: tuple[int, int]) -> list[str]:
    """The places a text is tried at, the best first: a hook at the top, then the middle (issue #167); the captions
    at the bottom, then the middle; any other where it is, then the place nearest to it."""
    role = layer.get("role") or ("caption" if layer["kind"] == "caption" else None)
    if role == "hook":
        return ["top", "middle", "bottom"]
    if role == "caption":
        return ["bottom", "middle", "top"]
    h = box[3] - box[1]
    _, _, anchors, bands = _zones(size, h)
    centre = (box[1] + box[3]) / 2
    here = layer.get("place") if layer.get("place") in PLACES else next(
        (p for p in PLACES if bands[p][0] <= centre < bands[p][1]), "top" if centre < bands["top"][1] else "bottom")
    return [here] + sorted((p for p in PLACES if p != here), key=lambda p: abs(anchors[p] - box[1]))


def suggest(layer: dict, box: tuple, heads: list[tuple], others: list[tuple], size: tuple[int, int]) -> dict | None:
    """The placement that clears every head seen and every other text shown with it (issue #167): {"place": top |
    middle | bottom, "offsetY": px at 1080 from that place (negative is up)}, the layer's own place and offset
    (`tm ad text` sets both). Tried at each place in `_order`, from the place itself outwards in STEP_PX steps while
    the text's centre stays in that third of the safe zone and the text inside it; the first that clears wins. None
    when nothing clears: no size fix for a face (a smaller text over a face is still over it)."""
    k = size[0] / 1080
    h = box[3] - box[1]
    top, bottom, anchors, bands = _zones(size, h)
    if h > bottom - top:
        return None
    face_margin, text_margin = cover_fit.MARGIN * k, TEXT_MARGIN * k
    step = STEP_PX * k
    for where in _order(layer, box, size):
        lo, hi = bands[where]
        found = None
        for n in range(0, int((bottom - top) / step) + 2):
            for dy in ((0.0,) if n == 0 else (-n * step, n * step)):
                y = anchors[where] + dy
                if y < top - 0.5 or y + h > bottom + 0.5 or (n and not lo <= y + h / 2 <= hi):
                    continue
                moved = (box[0], y, box[2], y + h)
                if not any(cover_fit._overlaps(moved, head, face_margin) for head in heads) and \
                        not any(cover_fit._overlaps(moved, other, text_margin) for other in others):
                    found = round(dy / k)
                    break
            if found is not None:
                return {"place": where, "offsetY": found}
    return None


def _advice(suggestion: dict | None) -> str:
    if suggestion is None:
        return ("no place in the safe zone clears the face and the other text: move it by hand (another time, a "
                "shorter text) and pin it")
    dy = suggestion.get("offsetY") or 0
    return f"place it at the {suggestion['place']}" + (f", {'up' if dy < 0 else 'down'} {abs(dy)} px from there"
                                                       if dy else "")


def check(run, layers: list[dict], size: tuple[int, int], scratch: Path,
          rejected: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """(the faces found, the collisions), for layers bottom to top; detections that are no face go to `rejected`."""
    faces: list[dict] = []
    collisions: list[dict] = []
    heads: dict[tuple[str, float], list[tuple]] = {}
    moved: dict[str, tuple] = {}      # the texts already given a placement, at their new place (issue #167)
    rejected = [] if rejected is None else rejected
    for n, low in enumerate(layers):
        if low["kind"] == "picture":
            src_size = _size(low["path"])
            if low["path"].suffix.lower() in STILLS:
                cw, ch = (low["crop"] or (0, 0, *src_size))[2:]
                bw, bh = low["box"][2:]
                if bw > cw * UPSCALE or bh > ch * UPSCALE:
                    collisions.append({"kind": "scaled_up", "layer": low["id"], "with": None, "at": low["start"],
                                       "box": list(low["box"]), "other": [cw, ch],
                                       "message": f"{low['id']} draws {c.name_of(low['src'])} at {bw:g}×{bh:g} px, "
                                                  f"larger than its own {cw:g}×{ch:g}: capture it sharper (a device "
                                                  "scale of 2 to 3, or the element itself) instead of scaling it up"})
        for high in layers[n + 1:]:
            span = together(low, high)
            if span is None:
                continue
            if low["kind"] == "picture" and not fills(high["box"], size):
                hit = _face_hit(low, high, span, scratch, heads, faces, size, rejected, layers, moved)
                if hit:
                    collisions.append(hit)
            if (not fills(low["box"], size) and not fills(high["box"], size)
                    and high.get("on") != low["id"] and low.get("on") != high["id"]
                    and overlap(_edges(low["box"]), _edges(high["box"]))):
                collisions.append({"kind": "layer", "layer": high["id"], "with": low["id"], "at": round(span[0], 2),
                                   "box": list(high["box"]), "other": list(low["box"]),
                                   "message": f"{high['id']} overlaps {low['id']} from {span[0]:.2f} s: move one, or "
                                              f"say {high['id']} is on {low['id']} on purpose (\"on\")"})
    return faces, collisions


def _face_hit(picture: dict, layer: dict, span: tuple[float, float], scratch: Path,
              heads: dict, faces: list[dict], size: tuple[int, int], rejected: list[dict],
              layers: list[dict] | None = None, moved: dict | None = None) -> dict | None:
    """The first face the layer covers while both are shown, with the placement of a text that clears every head
    seen then and every other text shown with it, at its new place when it was given one (`suggest`), or None."""
    box = _edges(layer["box"])
    src_size = _size(picture["path"])
    hit = None
    seen: list[tuple] = []
    for at in times(*span):
        key = (picture["id"], at if picture["path"].suffix.lower() not in STILLS else 0.0)
        if key not in heads:
            frame = _frame(picture, at, scratch / f"{len(heads):04d}.png")
            dropped: list[dict] = []
            placed = [place(cover_fit.head(f), src_size, picture["crop"], picture["box"])
                      for f in cover_fit.faces(frame, dropped)]
            heads[key] = [h for h in placed if h is not None]
            faces.extend({"layer": picture["id"], "at": at, "head": list(h)} for h in heads[key])
            rejected.extend({"layer": picture["id"], "at": at, **r} for r in dropped)
        seen += heads[key]
        if hit is None:
            hit = next(((at, h) for h in heads[key] if overlap(box, h)), None)
    if hit is None:
        return None
    at, head = hit
    suggestion = None
    if layer["kind"] in ("caption", "overlay"):
        moved = {} if moved is None else moved
        others = [moved.get(x["id"], _edges(x["box"])) for x in layers or []
                  if x["id"] != layer["id"] and x["kind"] in ("caption", "overlay") and not fills(x["box"], size)
                  and together(x, layer) and x.get("on") != layer["id"] and layer.get("on") != x["id"]]
        suggestion = suggest(layer, box, seen, others, size)
        if suggestion is not None:
            k = size[0] / 1080
            y = _zones(size, box[3] - box[1])[2][suggestion["place"]] + suggestion["offsetY"] * k
            moved[layer["id"]] = (box[0], y, box[2], y + box[3] - box[1])
    return {"kind": "face", "layer": layer["id"], "with": picture["id"], "at": at,
            "box": list(layer["box"]), "other": list(head), "suggestion": suggestion,
            "message": f"{layer['id']} covers a face in {picture['id']} at {at:.2f} s (the head at "
                       f"{', '.join(str(v) for v in head)}): {_advice(suggestion)}"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest(run, edit: Path) -> Path | None:
    """The latest layer check of an edit, `<edit dir>/qa/<stem>_layers_vNN.json`, or None."""
    try:
        stage = organic_qa.qa_stage(run, Path(edit))
    except ValueError:
        return None
    return run.latest(stage, f"{Path(edit).stem}_layers", "json")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("layer_check", "The edit's captions and overlays kept off faces and off each other; no capture "
                 "scaled up.")
    p.add_argument("edit", help="the edit (03_wip/edit_vNN.mp4)")
    p.add_argument("--layers", required=True, help="the edit's layers file, bottom to top")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    edit = c.resolve(run, a.edit)
    layers_path = c.resolve(run, a.layers)
    for path, what in ((edit, "edit"), (layers_path, "layers file")):
        if not path.is_file():
            raise c.ToolError(f"The {what} {c.name_of(path)} does not exist.")
        try:
            c.rel(run, path)
        except ValueError:
            raise c.ToolError(f"The {what} {c.name_of(path)} must be inside the run folder.") from None
    size = _size(edit)
    layers = read_layers(run, layers_path, size)
    scratch = Path(tempfile.mkdtemp(prefix="tm-layers-"))
    rejected: list[dict] = []
    cover_fit._last.clear()
    try:
        faces, collisions = check(run, layers, size, scratch, rejected)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    out = run.next_version(organic_qa.qa_stage(run, edit), f"{edit.stem}_layers", "json")
    said = (f"{len(collisions)} collision(s): " + "; ".join(x["message"] for x in collisions) + ". Fix them in the "
            "next version of the edit (S6) and check that." if collisions else
            f"No layer covers a face or another layer, and no still is scaled up ({len(layers)} layers, "
            f"{len(faces)} face sightings).")
    data = {"edit": c.rel(run, edit), "layers": {"file": c.rel(run, layers_path), "sha256": _sha(layers_path)},
            "size": list(size), "detector": cover_fit.detector_used(), "faces": faces, "rejected_faces": rejected,
            "collisions": collisions,
            "message": said}
    out.parent.mkdir(parents=True, exist_ok=True)
    c.write_json(out, data, newline="\n")
    c.record(run, out, "tm tool layer_check", c.rel(run, edit), params={"layers": c.rel(run, layers_path),
                                                                        "collisions": len(collisions)},
             model=f"{cover_fit.DETECTORS[cover_fit.detector_used()]} (tm tool cover_fit's)", cost="0 (local)")
    return c.finish(a, {"tool": "layer_check", "outputs": [c.rel(run, out)], "collisions": collisions,
                        "faces": len(faces), "detector": cover_fit.detector_used(), "message": said},
                    f"Wrote {c.rel(run, out)}. {said}")


if __name__ == "__main__":
    raise SystemExit(main())
