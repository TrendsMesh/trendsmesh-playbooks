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
                 "on": "<id>" (drawn on that layer on purpose, as a chip on its card)}]}

The text is two layers, as organic video's edit has it: `caption` (under the speech, at the bottom) and `overlay`
(the hook, a number, a tag, a code chip, the logo); a window, a scene card or a capture is a `picture`. Three checks:

- **faces**: for each picture under a layer, at the times both are shown (their first and last moment, the middle and
  every second between, at most 12), the faces in the picture's own frame (`tm tool cover_fit`'s detector, whose head
  runs from above the forehead to the chin), placed in the edit's frame through the picture's crop and box. A layer
  over a head is a collision (a caption over the mouth, a chip over the chin, a window over a face).
- **layers**: two layers shown together whose boxes overlap, neither filling the frame, unless one is `on` the other
  (a tag running under the caption band).
- **sharpness**: a still (png, jpg, webp) drawn larger than its own pixels (more than 5 % up): capture it sharper
  instead (`tm tool site capture` at a device scale of 2 to 3, or of the element itself).

Writes `<edit dir>/qa/<edit stem>_layers_vNN.json` (the next version): {"edit", "layers": {"file", "sha256"}, "size",
"faces": [{"layer", "at", "head"}], "collisions": [{"kind" (face, layer, scaled_up), "layer", "with", "at", "box",
"other", "message"}], "message"}. `tm ad check edit` refuses an edit whose latest layer check has a collision: move
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
               "n": n}
        if layer.get("box") is None and kind == "picture":
            row["box"] = (0.0, 0.0, float(width), float(height))
        else:
            row["box"] = _box(layer.get("box"), f"{where} ({lid}) box")
        if kind == "picture":
            src = layer.get("src")
            if not isinstance(src, str) or not src.strip():
                raise c.ToolError(f"{where} ({lid}) is a picture: give src, the video or image in the run it shows.")
            found = c.resolve(run, src)
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


def check(run, layers: list[dict], size: tuple[int, int], scratch: Path) -> tuple[list[dict], list[dict]]:
    """(the faces found, the collisions), for layers bottom to top."""
    faces: list[dict] = []
    collisions: list[dict] = []
    heads: dict[tuple[str, float], list[tuple]] = {}
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
                hit = _face_hit(low, high, span, scratch, heads, faces)
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
              heads: dict, faces: list[dict]) -> dict | None:
    box = _edges(layer["box"])
    src_size = _size(picture["path"])
    for at in times(*span):
        key = (picture["id"], at if picture["path"].suffix.lower() not in STILLS else 0.0)
        if key not in heads:
            frame = _frame(picture, at, scratch / f"{len(heads):04d}.png")
            placed = [place(cover_fit.head(f), src_size, picture["crop"], picture["box"])
                      for f in cover_fit.faces(frame)]
            heads[key] = [h for h in placed if h is not None]
            faces.extend({"layer": picture["id"], "at": at, "head": list(h)} for h in heads[key])
        for head in heads[key]:
            if overlap(box, head):
                return {"kind": "face", "layer": layer["id"], "with": picture["id"], "at": at,
                        "box": list(layer["box"]), "other": list(head),
                        "message": f"{layer['id']} covers a face in {picture['id']} at {at:.2f} s (the head at "
                                   f"{', '.join(str(v) for v in head)}): move it clear of the face and the chin"}
    return None


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
    try:
        faces, collisions = check(run, layers, size, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    out = run.next_version(organic_qa.qa_stage(run, edit), f"{edit.stem}_layers", "json")
    said = (f"{len(collisions)} collision(s): " + "; ".join(x["message"] for x in collisions) + ". Fix them in the "
            "next version of the edit (S6) and check that." if collisions else
            f"No layer covers a face or another layer, and no still is scaled up ({len(layers)} layers, "
            f"{len(faces)} face sightings).")
    data = {"edit": c.rel(run, edit), "layers": {"file": c.rel(run, layers_path), "sha256": _sha(layers_path)},
            "size": list(size), "faces": faces, "collisions": collisions, "message": said}
    out.parent.mkdir(parents=True, exist_ok=True)
    c.write_json(out, data, newline="\n")
    c.record(run, out, "tm tool layer_check", c.rel(run, edit), params={"layers": c.rel(run, layers_path),
                                                                        "collisions": len(collisions)},
             model="OpenCV Haar faces (tm tool cover_fit's)", cost="0 (local)")
    return c.finish(a, {"tool": "layer_check", "outputs": [c.rel(run, out)], "collisions": collisions,
                        "faces": len(faces), "message": said}, f"Wrote {c.rel(run, out)}. {said}")


if __name__ == "__main__":
    raise SystemExit(main())
