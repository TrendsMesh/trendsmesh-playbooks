"""Create an ad's text layer (S6, issue #117 section 4): the same text sets as organic video, over the ffmpeg cut.

    tm ad text --run R --cut 03_wip/edit_cut_vNN.mp4 --overlays 03_wip/edit_text_vNN.json [--words <transcript>]
               [--pictures <picture layers>] [--look L] [--accent #RRGGBB] [--json]

The cut stays ffmpeg's (the pictures, the windows, the sound, with no text). The captions and the overlays are drawn
over it with Remotion's `OrganicCaptions`, in the brand's saved text set (`tm.text_sets`; the default `outline` when
none is saved, `--look` for this ad only), with its accent, its font and its logo:

- **captions** from the words of the cut's own transcript (`--words`: `tm tool transcribe` of the cut, or Scribe's),
  in the set's word groups (`organic_edit.caption_layer`), at the bottom; a word marked `"key": true` is a key word;
- **overlays** from `--overlays`, `{"overlays": [{"from", "to", "text", "overlay": {"kind": "hook" | "label" |
  "number" | "cta" | "end", "sub"?, "brand"?, "hold"?}}]}` (`*word*` marks the key word of a line); a hook with
  `"hold": true` stays the whole ad and moves the other top overlays to the middle; the end card shows the brand's
  logo, or its name when there is none.

Writes `03_wip/edit_mix_vNN.props.json`, renders it to `03_wip/edit_mix_vNN.mp4` (`tm render video`, free) and writes
`03_wip/edit_layers_vNN.json` (the NN of the edit `tm tool deliver finish` writes next, or later, never an earlier
file) from the same props: the picture layers given with `--pictures` (`{"layers": [...]}`, kind picture, as S6 always
wrote them), then each overlay and caption with its box (`text_boxes`), so `tm tool layer_check` (S7) checks them.

`text_boxes` places each text as `OrganicCaptions.tsx` lays it out (the safe zone, the column, the place and
`offsetY`, the set's sizes by kind) and estimates its width from its letters: about 0.6 of the size a letter for the
sets' own fonts, and for the brand's font its own average letter width (its OS/2 table, `font_letter`) with a margin,
or a wide guess when the file can't be read (WOFF2), so a box is at least as large as the text drawn. An end card
fills the frame.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import zlib
from pathlib import Path

from tm import cli, organic_edit as oe
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop
from tm.tools import _common as c

WIP = "03_wip"
MIX, LAYERS, EDIT = "edit_mix", "edit_layers", "edit"
SAFE = {"top": 260, "bottom": 380, "left": 90, "right": 200}   # OrganicCaptions.tsx SAFE_1080
COLUMN = 680                                                   # its default column
LETTER = 0.6                                                   # a letter's width, of the size (a heavy sans)
UNKNOWN_LETTER = 0.8                                           # a brand font whose width can't be read
BOLDER = 1.1                                                   # the drawn weight is heavier than the file's average
LINE = 1.3                                                     # the line height, of the size, on the safe side
# The sizes the sets draw at, px at 1080 (CaptionLooks.tsx SIZE, OverlayLooks.tsx SIZES and the native ones)
CAPTION_SIZE = oe.LOOK_SIZE
OVERLAY_SIZE = {"hook": 62, "label": 40, "number": 150, "cta": 54, "end": 96}
NATIVE_SIZE = {"hook": 58, "label": 44, "cta": 50, "end": 64}
SUB_SIZE = 38
BOXED = ("pill", "block", "quiet", "native")                   # sets that draw a box behind an overlay


def font_letter(path: Path) -> float | None:
    """The font's average letter width, of its size (OS/2 xAvgCharWidth / head unitsPerEm), from a TTF, OTF or WOFF
    file; None when it can't be read (WOFF2 is Brotli-packed, a collection, a damaged file)."""
    try:
        data = Path(path).read_bytes()
        tables: dict[bytes, bytes] = {}
        if data[:4] == b"wOFF":
            count = struct.unpack(">H", data[12:14])[0]
            for i in range(count):
                tag, off, comp, orig, _ = struct.unpack(">4sIIII", data[44 + 20 * i:64 + 20 * i])
                raw = data[off:off + comp]
                tables[tag] = zlib.decompress(raw) if comp < orig else raw
        elif data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            count = struct.unpack(">H", data[4:6])[0]
            for i in range(count):
                tag, _, off, length = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
                tables[tag] = data[off:off + length]
        else:
            return None
        avg = struct.unpack(">h", tables[b"OS/2"][2:4])[0]
        upm = struct.unpack(">H", tables[b"head"][18:20])[0]
    except (OSError, KeyError, struct.error, zlib.error):
        return None
    return avg / upm if avg > 0 and upm > 0 else None


def letter_of(font: Path | None) -> float:
    """The letter width `text_boxes` measures with: the sets' own, or the brand font's with a margin."""
    if font is None:
        return LETTER
    own = font_letter(font)
    return UNKNOWN_LETTER if own is None else max(LETTER, own * BOLDER)


def _lines(text: str, size: float, room: float, factor: float = LETTER) -> tuple[float, int]:
    """(the width, the lines) of `text` at `size` in `room` px. A text that wraps takes the whole room: a wrapped
    inline box widens to the width it may use (CSS), whatever its lines' balance."""
    longest = max((len(part) for part in text.split("\n")), default=0)
    total = longest * factor * size
    lines = max(1, math.ceil(total / max(room, size))) + text.count("\n")
    return (room if lines > 1 else min(room, total)), lines


def _place(place: str, h: float, k: float, height: int, shift: float) -> float:
    top = SAFE["top"] * k + shift
    bottom = height - SAFE["bottom"] * k + shift
    if place == "bottom":
        return bottom - h
    if place == "middle":
        return (top + bottom) / 2 - h / 2
    return top


def _box(x: float, y: float, w: float, h: float, width: int, height: int) -> list[float]:
    x, y = max(0.0, x), max(0.0, y)
    return [round(x, 1), round(y, 1), round(min(w, width - x), 1), round(min(h, height - y), 1)]


def text_boxes(props: dict, letter: float = LETTER) -> list[dict]:
    """One layer per caption and overlay of OrganicCaptions props, in their order (the module docstring):
    {"id", "kind" (caption, overlay), "start", "end", "box": [x, y, w, h]} in px of the props' frame. `letter`: a
    letter's width of the size in the font the sets draw with (`letter_of` the brand's font); native is always
    TikTok Sans."""
    width, height = int(props["width"]), int(props["height"])
    k = width / 1080
    out = []
    n = {"caption": 0, "overlay": 0}
    for cap in props.get("captions") or []:
        kind = "caption" if cap.get("style") == "caption" else "overlay"
        n[kind] += 1
        shift = float(cap.get("offsetY") or 0) * k
        text = str(cap.get("text") or "").replace("*", "")
        ov = cap.get("overlay") if isinstance(cap.get("overlay"), dict) else None
        place = cap.get("place") or ("bottom" if kind == "caption" else "top")
        if ov and ov.get("kind") == "end":
            box = [0, 0, width, height]
        elif ov:
            fam, what = ov.get("family"), ov.get("kind", "hook")
            size = (NATIVE_SIZE.get(what, 58) if fam == "native" and what != "number" else
                    OVERLAY_SIZE.get(what, 62) * (1.25 if fam == "pop" and what != "number" else
                                                  0.85 if fam == "quiet" else 1)) * k
            left, room = SAFE["left"] * k, width - (SAFE["left"] + SAFE["right"]) * k
            room = min(room, 700 * k) if fam == "native" else room
            pad = 0.7 * size if fam in BOXED or what == "label" else 0.2 * size
            own = LETTER if fam == "native" else letter
            factor = own * (1.15 if what == "label" or fam == "pop" else 1)
            if what == "number":
                w = max(len(text) * own * 1.05 * size, len(ov.get("sub") or "") * own * SUB_SIZE * k) + pad
                h = size + (SUB_SIZE * k * 1.25 + 6 * k if ov.get("sub") else 0) + 0.4 * size
                w = min(w, room)
            else:
                line, lines = _lines(text + (" →" if what == "cta" else ""), size, room - pad, factor)
                w, h = line + pad, lines * size * LINE + (0.4 * size if fam in BOXED else 0.1 * size)
            x = left + (room - w) / 2 + (width - (SAFE["left"] + SAFE["right"]) * k - room) / 2
            box = _box(x, _place(place, h, k, height, shift), w, h, width, height)
        else:
            look = cap.get("look")
            size = float(cap.get("fontSize") or (CAPTION_SIZE.get(look, 64) if kind == "caption" else 58)) * k
            usable = 1080 - SAFE["left"] - SAFE["right"]
            col = min(max(float(cap.get("width") or COLUMN), 120), usable) * k
            left = min(max(width / 2 - col / 2, SAFE["left"] * k), width - SAFE["right"] * k - col)
            factor = (LETTER if look == "native" else letter) * (1.15 if look == "pop" else 1)
            pad = 0.5 * size if look in ("pill", "block") or kind == "overlay" else 0.2 * size
            line, lines = _lines(text.upper() if look == "pop" else text, size, col - pad, factor)
            w, h = min(col, line + pad), lines * size * LINE + 0.2 * size
            box = _box(left + (col - w) / 2, _place(place, h, k, height, shift), w, h, width, height)
        out.append({"id": f"{kind}_{n[kind]}", "kind": kind, "start": cap["from"], "end": cap["to"], "box": box})
    return out


# --- tm ad text -----------------------------------------------------------------------------------

def _number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _read_overlays(run: RunFolder, given: str) -> tuple[str, list[dict]]:
    path, rel = oe._inside(run, given, "overlays file")
    data = oe._json(path, rel, "overlays file")
    items = data.get("overlays") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise Stop(f"{rel} must be {{\"overlays\": [{{\"from\", \"to\", \"text\", \"overlay\": {{\"kind\"}}}}]}}; "
                   f"{AGAIN}.")
    bad = []
    for i, o in enumerate(items, 1):
        if not (isinstance(o, dict) and _number(o.get("from")) and _number(o.get("to")) and 0 <= o["from"] < o["to"]
                and isinstance(o.get("text"), str) and o["text"].strip()):
            bad.append(f"overlay {i} needs from and to (seconds, from before to) and a text")
            continue
        kind = (o.get("overlay") or {}).get("kind", "hook") if isinstance(o.get("overlay"), dict) else "hook"
        if kind not in oe.OVERLAY_KINDS:
            bad.append(f"overlay {i}'s kind is one of {', '.join(oe.OVERLAY_KINDS)}, not {kind!r}")
    if bad:
        raise Stop(f"{rel}: {'; '.join(bad)}. Nothing was rendered; {AGAIN}.")
    return rel, [{**o, "style": "hook"} for o in items]


def _read_pictures(run: RunFolder, given: str | None) -> list[dict]:
    if given is None:
        return []
    path, rel = oe._inside(run, given, "picture layers")
    data = oe._json(path, rel, "picture layers")
    layers = data.get("layers") if isinstance(data, dict) else None
    if not (isinstance(layers, list) and all(isinstance(x, dict) and x.get("kind") == "picture" for x in layers)):
        raise Stop(f"{rel} must be {{\"layers\": [...]}} with the edit's pictures only (kind picture); the text "
                   f"layers are written from the props; {AGAIN}.")
    return layers


def _nn(path: Path) -> int:
    return int(path.name.split("_v")[-1].split(".")[0])


def text(run: RunFolder, cut: str, *, overlays: str, words: str | None = None, pictures: str | None = None,
         look_id: str | None = None, accent: str | None = None) -> dict:
    """The cut with its text drawn in the brand's set, and its layers (the module docstring)."""
    from tm import render, text_sets   # they read the organic modules: imported where they are used

    cut_path, cut_rel = oe._inside(run, cut, "cut")
    if accent is not None and not oe.COLOUR.fullmatch(accent):
        raise Stop(f"--accent must be a colour as #RRGGBB (the brand's), not {accent!r}; {AGAIN}.")
    over_rel, given = _read_overlays(run, overlays)
    shown = _read_pictures(run, pictures)
    found = c.probe(cut_path)
    if not found.get("is_video", found.get("has_video")):
        raise Stop(f"{cut_rel} is not a video: give the ffmpeg cut of the edit, without its text; {AGAIN}.")
    duration = float(found["duration"])
    saved = text_sets.for_run(run)
    kit = text_sets.into_run(run, saved) if saved else {}
    look = look_id or kit.get("look") or oe.DEFAULT_LOOK
    style = oe.default_style(caption="", overlay="", look=look, accent=accent.upper() if accent else kit.get("accent"),
                             font=kit.get("font"), logo=kit.get("logo"))
    caps: list[dict] = []
    words_rel = None
    if words is not None:
        wpath, words_rel = oe._inside(run, words, "words file")
        caps = oe.caption_layer(oe._read_words(wpath, words_rel), style)
    tops = oe.overlay_entries(given, style, total=duration)
    props = {"width": int(found["width"]), "height": int(found["height"]), "fps": round(float(found["fps"]) or 30),
             "keepAudio": True, "segments": [{"src": cut_rel, "start": 0, "end": round(duration, 3)}],
             "captions": tops + caps, **({"brandFont": style["font"]} if style.get("font") else {})}
    mix = run.next_version("wip", MIX, "mp4")
    props_path = mix.with_name(mix.name.removesuffix(".mp4") + ".props.json")
    c.write_json(props_path, props, newline="\n")
    c.record(run, props_path, "tm ad text", cut_rel, cost="free",
             params={"look": look, "text_set": saved["file"] if saved else None, "overlays": over_rel,
                     "words": words_rel, "captions": len(caps)})
    done = render.video(run, "OrganicCaptions", props_path, mix)
    nn = max(_nn(run.next_version("wip", EDIT, "mp4")), _nn(run.next_version("wip", LAYERS, "json")))
    layers_path = run.path / WIP / f"{LAYERS}_v{nn:02d}.json"
    letter = letter_of(run.path / style["font"]["src"]) if style.get("font") else LETTER
    c.write_json(layers_path, {"layers": shown + text_boxes(props, letter)}, newline="\n")
    c.record(run, layers_path, "tm ad text", c.rel(run, props_path), cost="free")
    return {"props": c.rel(run, props_path), "mix": c.rel(run, done), "layers": c.rel(run, layers_path),
            "look": look, "text_set": saved["file"] if saved else None, "captions": len(caps), "overlays": len(tops)}


def add_parser(sub) -> argparse.ArgumentParser:
    t = sub.add_parser("text", help="the edit's captions and overlays over the ffmpeg cut, in the brand's text set (S6)")
    t.add_argument("--cut", required=True, help="the ffmpeg cut without text, 03_wip/edit_cut_vNN.mp4")
    t.add_argument("--overlays", required=True, help="03_wip/edit_text_vNN.json: {\"overlays\": [...]}")
    t.add_argument("--words", help="the cut's transcript (tm tool transcribe), for the captions")
    t.add_argument("--pictures", help="the edit's picture layers, {\"layers\": [...]}, for edit_layers_vNN.json")
    t.add_argument("--look", choices=oe.LOOKS, help="another set for this ad only (default: the brand's saved one)")
    t.add_argument("--accent", help="the brand colour, #RRGGBB (default: the saved set's)")
    return t


def run_cli(args: argparse.Namespace, run: RunFolder) -> int:
    try:
        out = text(run, args.cut, overlays=args.overlays, words=args.words, pictures=args.pictures,
                   look_id=args.look, accent=args.accent)
    except c.ToolStop as exc:      # the render's own stop (the video tools not set up): its todo, exit 2
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except c.ToolError as exc:
        return cli.fail(args, str(exc))
    message = (f"Drew {out['captions']} captions and {out['overlays']} overlays in the {out['look']} set over "
               f"{args.cut}: {out['mix']}, and wrote {out['layers']}. Next: tm tool deliver finish --run R "
               f"{out['mix']}, then the edit QA (S7) with --layers {out['layers']}.")
    cli.emit(args, {"status": "done", **out, "message": message}, message)
    return 0
