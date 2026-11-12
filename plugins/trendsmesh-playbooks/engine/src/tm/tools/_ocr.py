"""The teardown's OCR (issue 57): the optional `ocr` tier reads the words in the rows the text pass is unsure of.

The tier is its own pixi environment (RapidOCR with onnxruntime: pip packages only, no system binary, its models in
the wheel), never installed by default: the playbook offers it once, during a teardown, when the ad has on-screen
text to remove or replace and the text pass is unsure of it. `tm tool teardown` runs in the breakdown environment;
when the `ocr` tier is installed (`reader()`), it saves the unsure rows' frames at full size with ffmpeg and starts

    pixi run --as-is --manifest-path <root>/env/pixi.toml -e ocr python -m tm.tools._ocr REQUEST.json RESULT.json

(argv, never a shell string), which reads each row's box, grown by MARGIN, on up to MAX_FRAMES frames (the row's
first, middle and last; for changing captions the middle of up to three of their spans, where words are on screen).
Nothing is downloaded or spent. A failed read never fails the teardown: its rows stay to check, and `ocr.error`
says why.

`settle` then uses what was read (lines of MIN_SCORE or more, two letters or digits at least, overlapping the row's
box) to confirm or correct the text pass. Every change is listed in `ocr.read`:
- an edge find (`graphic`): words read -> a `text` overlay, sure; none -> dropped (`ocr.dropped`): the edge
  method's false finds, or a plain bar or shape;
- `text` seen briefly or faintly: words read -> sure;
- changing captions: words read -> sure when they are what is said then (the transcript, within WINDOW_S; accents
  and small misreads allowed: MATCH_RATIO, MATCH_SHARE) or when there are no spoken words to compare; still to
  check, with the words, when they do not match;
- `full_frame`: the words are added, and it stays to check (OCR cannot tell an end card from a product label);
- a `check_frames` band: words read -> a new overlay (`methods: ["ocr"]`), sure when they match the transcript,
  and the band is gone; none -> the band stays;
- a possible whole-shot overlay: words read -> kept, with the words; none -> dropped.
A confirmed or new overlay's box is the union with the lines read in it (a box that cut letters off grows).
The check sheet is still made, from the rows still unsure.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

TIER = "ocr"
MIN_SCORE = 0.6
MARGIN = 0.25
MIN_MARGIN_PX = 16
MAX_FRAMES = 3
WINDOW_S = 0.5
MATCH_RATIO = 0.75
MATCH_SHARE = 0.5
TIMEOUT_S = 900

LIMITS = (
    "OCR read only the rows the text pass was unsure of, on up to three frames each: the sure overlays were not "
    "read.",
    "The bundled model reads Latin letters and digits; it may drop accents and misread stylised or very thin fonts "
    "(the transcript match allows for small misreads). A row it could not read stays to check.",
    "A still shot with text in the picture (a product label) reads as text too: a full_frame stays to check.",
    "An edge find with no words read was dropped (ocr.dropped): a plain bar or shape among them is still on screen.",
)
OFFER = ("{rows} row(s) on the check sheet are unsure. The optional 'ocr' tier (RapidOCR, about {size} MB, free and "
         "local) could read their words and settle some of them; it is not installed. Offer it once if the ad has "
         "on-screen text to remove or replace (tm env install ocr, after the user's yes, then the teardown again); "
         "otherwise check the frames by eye.")
CAPTIONS_UNMATCHED = ("OCR read “{text}”, which is not what is said at that time: captions in another wording or "
                      "language, or a misread; check the frames.")
FULL_FRAME_READ = ("OCR read “{text}”. An end card or full-frame title, or text in the picture itself (a product "
                   "label); check the frames.")
OCR_ONLY_CHECK = ("Found by OCR where the text pass found no text line (“{text}”), and not what is said then; "
                  "check the frames.")
NOT_READ = " OCR read no words in its frames."


# The worker: runs in the ocr environment -----------------------------------------------------

def _image(path: str):
    import cv2
    import numpy as np

    data = np.fromfile(path, np.uint8)   # cv2.imread cannot open non-ASCII paths on Windows
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def read(request: dict) -> dict:
    """{"frames": {frame: png}, "crops": [{"id", "frame", "box"}]} -> {"engine", "crops": {id: [line]}}, a line
    being {"text", "score", "box"} with the box in source pixels."""
    from importlib.metadata import version

    from rapidocr import RapidOCR

    engine = RapidOCR(params={"Global.log_level": "error"})
    images: dict[str, object] = {}
    out: dict[str, list[dict]] = {}
    for crop in request["crops"]:
        key = str(crop["frame"])
        if key not in images:
            images[key] = _image(request["frames"][key])
        img = images[key]
        if img is None:
            out[crop["id"]] = []
            continue
        x0, y0, x1, y1 = (int(v) for v in crop["box"])
        part = img[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        lines = []
        if part.size:
            got = engine(part)
            for text, score, quad in zip(got.txts or (), got.scores or (), got.boxes if got.boxes is not None else ()):
                xs, ys = [float(p[0]) for p in quad], [float(p[1]) for p in quad]
                lines.append({"text": str(text), "score": round(float(score), 3),
                              "box": [round(min(xs)) + x0, round(min(ys)) + y0, round(max(xs)) + x0,
                                      round(max(ys)) + y0]})
        out[crop["id"]] = lines
    return {"engine": f"RapidOCR {version('rapidocr')}", "crops": out}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Use: python -m tm.tools._ocr REQUEST.json RESULT.json", file=sys.stderr)
        return 1
    request = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    Path(args[1]).write_text(json.dumps(read(request), ensure_ascii=False), encoding="utf-8")
    return 0


# The teardown's side: runs in the breakdown environment --------------------------------------

def reader():
    """The function that reads crops with the ocr tier, or None when the tier is not installed."""
    try:
        from tm import envtiers

        ok = envtiers.installed(TIER)
    except Exception:   # noqa: BLE001  (no pixi, no plugin folders: no OCR, the rows stay to check)
        ok = False
    return read_with_tier if ok else None


def worker_argv(request: Path, result: Path) -> list[str]:
    from tm import envtiers, paths

    return [str(paths.pixi_bin()), "run", "--as-is", "--manifest-path", str(paths.plugin_root() / "env" / "pixi.toml"),
            "-e", envtiers.TIERS[TIER].env, "python", "-m", "tm.tools._ocr", str(request), str(result)]


def worker_env() -> dict[str, str]:
    from tm import paths

    return {**paths.child_environ(dict(os.environ)), **paths.pixi_env()}


def save_frames(video: Path | str, frames: list[int], folder: Path) -> dict[str, str]:
    """The frames numbered `frames`, full size, as PNGs: {frame: path}. One ffmpeg call."""
    from tm.tools import _common as c

    wanted = sorted({int(f) for f in frames})
    sel = "+".join(rf"eq(n\,{f})" for f in wanted)
    c.run_ffmpeg(["-i", c.media(video), "-vf", f"select='{sel}'", "-fps_mode", "passthrough",
                  c.media(folder / "f_%05d.png")])
    return {str(f): str(folder / f"f_{n:05d}.png") for n, f in enumerate(wanted, 1)
            if (folder / f"f_{n:05d}.png").is_file()}


def read_with_tier(video: Path | str, crops: list[dict]) -> dict:
    """Run the worker in the ocr environment on `crops` of `video`'s frames: the worker's answer."""
    from tm.tools import _common as c

    with tempfile.TemporaryDirectory(prefix="tm-ocr-") as tmp:
        folder = Path(tmp)
        frames = save_frames(video, [cr["frame"] for cr in crops], folder)
        request, result = folder / "request.json", folder / "result.json"
        request.write_text(json.dumps({"frames": frames, "crops": crops}), encoding="utf-8")
        try:
            proc = subprocess.run(worker_argv(request, result), env=worker_env(), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as exc:
            raise c.ToolError(f"OCR could not run: {exc}") from None
        if proc.returncode != 0 or not result.is_file():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            raise c.ToolError(c.scrub("OCR could not run: " + (" ".join(tail) or f"exit {proc.returncode}")))
        return json.loads(result.read_text(encoding="utf-8"))


# Which crops to read --------------------------------------------------------------------------

def _grow(box, width: int, height: int) -> list[int]:
    x0, y0, x1, y1 = box
    mx = max(MIN_MARGIN_PX, round(MARGIN * (x1 - x0)))
    my = max(MIN_MARGIN_PX, round(MARGIN * (y1 - y0)))
    return [max(0, x0 - mx), max(0, y0 - my), min(width, x1 + mx), min(height, y1 + my)]


def frames_for(item: dict, data: dict) -> list[int]:
    """The frames to read for one check item: its first, middle and last, or, for an overlay whose text comes and
    goes (spans_s), the middle of up to MAX_FRAMES of its spans, spread over it."""
    fps = data.get("fps") or 0
    if item["what"] == "overlay" and fps:
        spans = data["overlays"][item["overlay"]].get("spans_s") or []
        if len(spans) > 1:
            pick = [spans[round(i * (len(spans) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)] \
                if len(spans) > MAX_FRAMES else spans
            return sorted({min(data["frame_count"] - 1, round((a + b) / 2 * fps)) for a, b in pick})
    return list(item["frames"])[:MAX_FRAMES]


def crops_for(items: list[dict], data: dict) -> list[dict]:
    """[{"id": "<item>:<frame>", "frame", "box"}]: each item's box, grown by MARGIN, on its frames."""
    out = []
    for n, item in enumerate(items):
        box = _grow(item["bbox"], data["width"], data["height"])
        out += [{"id": f"{n}:{f}", "frame": f, "box": box} for f in frames_for(item, data)]
    return out


# Settling the rows ----------------------------------------------------------------------------

def _plain(text: str) -> str:
    """Lower case, accents off (ą -> a), letters and digits only."""
    decomposed = unicodedata.normalize("NFKD", text.casefold().replace("ł", "l"))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", _plain(text)) if len(t) >= 2 or t.isdigit()]


def _letters(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def _overlaps(a, b) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def lines_in(read: list[dict], box) -> list[dict]:
    """The lines worth trusting: MIN_SCORE or more, two letters or digits at least, overlapping `box`."""
    return [ln for ln in read or [] if float(ln.get("score", 0)) >= MIN_SCORE and _letters(ln.get("text", "")) >= 2
            and _overlaps(ln["box"], box)]


def _spoken(transcript: dict | None, start_s: float, end_s: float) -> list[str]:
    out = []
    for seg in (transcript or {}).get("segments", []):
        for w in seg.get("words") or []:
            try:
                if start_s - WINDOW_S <= float(w["start"]) <= end_s + WINDOW_S:
                    out += tokens(str(w.get("word", "")))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def matches(texts: list[str], transcript: dict | None, start_s: float, end_s: float) -> bool | None:
    """True when most words read (MATCH_SHARE) are said between start_s and end_s (WINDOW_S either side), allowing
    small misreads (MATCH_RATIO); None when nothing is said then (nothing to compare)."""
    said = _spoken(transcript, start_s, end_s)
    seen = [t for text in texts for t in tokens(text)]
    if not said or not seen:
        return None
    hit = sum(any(t == s or difflib.SequenceMatcher(None, t, s).ratio() >= MATCH_RATIO for s in said) for t in seen)
    return hit / len(seen) >= MATCH_SHARE


def _union(boxes) -> list[int]:
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _texts(lines: list[dict]) -> list[str]:
    seen: list[str] = []
    for ln in lines:
        t = " ".join(ln["text"].split())
        if t and t not in seen:
            seen.append(t)
    return seen


def _touches(box, width: int, height: int, edge_px: int) -> bool:
    return box[0] <= edge_px or box[1] <= edge_px or width - box[2] <= edge_px or height - box[3] <= edge_px


def _seconds(frame: int, fps: float) -> float:
    return round(frame / fps, 3)


def settle(data: dict, items: list[dict], reads: dict, transcript: dict | None, *, edge_px: int) -> dict:
    """Confirm, correct or drop `items` (teardown.check_items(data)) from what OCR read (`reads`: the worker's
    "crops", {crop id: lines}); `data` is changed in place. Returns the JSON's `ocr` section."""
    fps, W, H = data["fps"], data["width"], data["height"]
    overlays, bands = data["overlays"], data["check_frames"]
    wholes = data["possible_whole_shot_overlays"]
    gone_o, gone_b, gone_w, new, dropped, report = set(), set(), set(), [], [], []
    for n, item in enumerate(items):
        frames = frames_for(item, data)
        lines = [dict(ln, frame=f) for f in frames for ln in lines_in(reads.get(f"{n}:{f}", []), item["bbox"])]
        texts = _texts(lines)
        entry = {"what": item["what"], "kind": item.get("kind"), "bbox": list(item["bbox"]), "frames": frames,
                 "lines": [{"frame": ln["frame"], "text": ln["text"], "score": ln["score"], "box": ln["box"]}
                           for ln in lines]}
        grown = _union([item["bbox"], *(ln["box"] for ln in lines)]) if lines else list(item["bbox"])
        if item["what"] == "overlay":
            o = overlays[item["overlay"]]
            verdict = _overlay(o, texts, grown, transcript, W, H, edge_px)
            if verdict == "dropped":
                gone_o.add(item["overlay"])
                dropped.append({"what": "overlay", **o})
        elif item["what"] == "check_frames":
            band = bands[item["index"]]
            if texts:
                gone_b.add(item["index"])
                new.append(_found(band, texts, grown, transcript, fps, W, H, edge_px))
                verdict = "found"
            else:
                verdict = "not_read"
        else:
            whole = wholes[item["index"]]
            if texts:
                whole["ocr_text"] = texts
                verdict = "read"
            else:
                gone_w.add(item["index"])
                dropped.append({"what": "whole_shot", **whole})
                verdict = "dropped"
        entry["verdict"] = verdict
        if texts and grown != list(item["bbox"]) and verdict in ("confirmed", "found"):
            entry["bbox_now"] = grown
        report.append(entry)
    data["overlays"] = sorted([o for i, o in enumerate(overlays) if i not in gone_o] + new,
                              key=lambda o: (o["start_frame"], o["bbox"][1], o["bbox"][0]))
    data["check_frames"] = [b for i, b in enumerate(bands) if i not in gone_b]
    data["possible_whole_shot_overlays"] = [w for i, w in enumerate(wholes) if i not in gone_w]
    counts = {v: sum(e["verdict"] == v for e in report) for v in ("confirmed", "found", "dropped")}
    counts["to_check"] = len(items) - sum(counts.values())
    return {"installed": True, "rows": len(items), "counts": counts, "read": report, "dropped": dropped}


def _overlay(o: dict, texts: list[str], grown: list[int], transcript: dict | None, W: int, H: int,
             edge_px: int) -> str:
    """Settle one overlay row in place: "confirmed", "dropped", "unmatched", "read" or "not_read"."""
    kind = o["kind"]
    if not texts:
        if kind == "graphic":
            return "dropped"
        o["check"] = (o.get("check") or "").rstrip() + NOT_READ
        return "not_read"
    o["ocr_text"] = texts
    if "ocr" not in o["methods"]:
        o["methods"] = [*o["methods"], "ocr"]
    if kind == "full_frame":
        o["confidence"], o["check"] = 0.6, FULL_FRAME_READ.format(text=" / ".join(texts))
        return "read"
    if kind == "word_captions":
        match = matches(texts, transcript, o["start_s"], o["end_s"])
        o["transcript"] = {**(o.get("transcript") or {}), "ocr_match": match}
        if match is False:
            o["check"] = CAPTIONS_UNMATCHED.format(text=" / ".join(texts))
            return "unmatched"
        o["confidence"] = 0.9 if match else 0.8
    else:   # text seen briefly, or an edge find with words in it
        o["kind"], o["confidence"] = "text", 0.8
    o["check"] = None
    o["bbox"] = [max(0, grown[0]), max(0, grown[1]), min(W, grown[2]), min(H, grown[3])]
    o["touches_edge"] = _touches(o["bbox"], W, H, edge_px)
    return "confirmed"


def _found(band: dict, texts: list[str], grown: list[int], transcript: dict | None, fps: float, W: int, H: int,
           edge_px: int) -> dict:
    """A band where the text pass found no line, but OCR read words: a new overlay."""
    first, last = band["first_frame"], band["last_frame"]
    start_s, end_s = _seconds(first, fps), _seconds(last + 1, fps)
    match = matches(texts, transcript, start_s, end_s)
    box = [max(0, grown[0]), max(0, grown[1]), min(W, grown[2]), min(H, grown[3])]
    return {"start_frame": first, "end_frame": last, "bbox": box, "touches_edge": _touches(box, W, H, edge_px),
            "semi_transparent": False, "kind": "word_captions" if len(texts) > 1 else "text",
            "confidence": 0.8 if match else 0.7, "methods": ["ocr"],
            "check": None if match else OCR_ONLY_CHECK.format(text=" / ".join(texts)),
            "transcript": {"ocr_match": match}, "start_s": start_s, "end_s": end_s, "spans_s": [[start_s, end_s]],
            "ocr_text": texts}


def not_installed(rows: int) -> dict:
    """The JSON's `ocr` section when the tier is not installed and rows are unsure: what to offer."""
    from tm import envtiers

    size = envtiers.TIERS[TIER].approx_mb
    return {"installed": False, "rows": rows, "tier": TIER, "approx_mb": size,
            "offer": OFFER.format(rows=rows, size=size)}


if __name__ == "__main__":
    raise SystemExit(main())
