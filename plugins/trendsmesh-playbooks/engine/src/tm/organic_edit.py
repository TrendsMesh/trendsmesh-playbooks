"""Organic video's edit (FLOWS.md G1, issue 89): the AI shot's own sound under a voiceover.

`shot_audio_gap(run, props)` reads an `OrganicCaptions` edit's props: with a voiceover (any `audioTracks` entry) the
AI shot's own sound is muted (MiniMax H3 always makes sound), so a segment cut from an AI take (an output of a
Replicate record, `03_wip/<item>_vNN.run.json`, or a file made from one, up the manifest's parents: a sped-up copy)
that keeps its sound (`keepAudio: true` and a `volume` that is not 0) is refused by `tm render video` before anything
runs, unless the user asked to keep it (`--keep-shot-audio`, recorded in the render's params). Other segments (an
animation insert, a motion-graphics render) keep their own level. Reads only.

The text on screen is two layers (FLOWS.md G1), in a style the user approves at the images check-in (F1):

- **captions** under the voiceover, TikTok style: groups of 2 to 4 words (`caption_groups`) from the recording's word
  times (`<stem>.words.json` of `tm tool elevenlabs tts --timestamps`, or a take's transcript from `tm tool
  transcribe`), white with a black outline, at the bottom, the spoken word lit when the style has a `highlight`;
- **overlays** at the top, in a box: only the hook, the key number and the closing question (`OVERLAYS_MAX`).

The style is `03_wip/text_style_vNN.json` (`default_style`, checked by `style_problems`):

    {"captions": {fontSize, color, stroke, highlight (a colour or null), place, offsetY, width, words: [min, max]},
     "overlays": {fontSize, color, background, place, offsetY, width},
     "sample": {"caption": "<a line of the voiceover>", "overlay": "<the hook>"}}

in px at 1080×1920 (`width` at most 790, the safe zone's; `offsetY` negative moves the text up).

    tm organic text look --run R --picture <the first frame> [--style S | --caption T --overlay T] [--at SEC]
        the style (the default with the given samples when no --style: the next text_style_vNN.json) drawn on the
        picture: `03_wip/text_look_vNN.props.json` and its still `03_wip/text_look_vNN.png` (`tm render still`, free).
        It is the latest OrganicCaptions still in 03_wip, so the images page shows it beside every item
        (`organic_gates._still`); a chat card shows the PNG.
    tm organic text approve --run R --style S [--by user|rule] --note "<their words>"
        the user's yes to the latest style once its look was drawn: run.json `checked["text_style"]` (`stepchecks.mark`,
        with `by`, `note` and `look`). Their changes are a new style version, drawn and shown again.
    tm organic captions --run R --props <the edit's props> --words <words file> [--source FILE] [--from SEC]
        the next version of the edit's props with the captions layer made again from the words in the approved style,
        the overlays (every caption that is not a `caption`) in the overlay style, and `textStyle` {file, sha256}.
        The words are placed where the edit plays them: a voiceover at its `audioTracks` `from`, a take through the
        segments that cut it (words outside the cuts are left out); `--source` names that file when the words file's
        name does not (`<stem>.words.json` beside `<stem>.mp3`), `--from` gives the seconds by hand.

`text_gap` is G1's `text_followed` check: the edit the latest final was made from (its `tm render video` row, up the
manifest's parents) carries captions under a voiceover, and an edit with any text carries the approved style's stamp
(`tm organic captions` wrote it). A talking take with no text passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from tm import cli, manifest, organic_audio, organic_final, state, stepchecks
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop
from tm.tools import _common as c

WIP = "03_wip"
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".m4v", ".mkv")


def ai_takes(run: RunFolder) -> set[str]:
    """Every video a Replicate record in 03_wip made, run-relative and case-folded (`organic_final._key`)."""
    folder = run.path / WIP
    found: set[str] = set()
    for path in sorted(folder.glob("*.run.json")) if folder.is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        outputs = record.get("outputs") if isinstance(record, dict) else None
        for name in outputs if isinstance(outputs, list) else []:
            if isinstance(name, str) and Path(name).suffix.lower() in VIDEO_SUFFIXES:
                found.add(organic_final._key(f"{WIP}/{name}"))
    return found


def shot_audio_gap(run: RunFolder, props: dict) -> str | None:
    """What keeps an AI shot's own sound under the voiceover, in words, or None (the module docstring)."""
    tracks = props.get("audioTracks")
    if not (isinstance(tracks, list) and tracks) or props.get("keepAudio") is not True:
        return None
    takes = ai_takes(run)
    if not takes:
        return None
    rows = organic_final._rows(run)
    loud = []
    segments = props.get("segments") if isinstance(props.get("segments"), list) else []
    for n, seg in enumerate(segments, 1):
        if not isinstance(seg, dict) or not isinstance(seg.get("src"), str) or seg.get("volume") == 0:
            continue
        if set(organic_final._lineage(rows, seg["src"])) & takes:
            loud.append(f"segment {n} ({seg['src']})")
    if not loud:
        return None
    return (f"The edit keeps the AI shot's own sound under the voiceover: {', '.join(loud)}. With a voiceover the "
            "shot's sound is muted: set keepAudio to false (or volume 0 on those segments). Nothing was rendered. "
            "Keep it only when the user asks for it: tm render video ... --keep-shot-audio.")


# --- the text style ----------------------------------------------------------------------------------

STYLE_STEM, LOOK_STEM, STYLE_KEY = "text_style", "text_look", "text_style"
OVERLAYS_MAX = 3
PLACES = ("top", "middle", "bottom")
SAFE_WIDTH = 790        # x 90 to 880 at 1080 (OrganicCaptions.tsx SAFE_1080)
LOOK_SECONDS, LOOK_FRAME = 2, 6   # the look's still: frame 6, after the text's pop
PAUSE = 0.4             # a pause this long (seconds) between two words ends a caption group
TAIL = 0.3              # a group stays on screen this long after its last word, unless the next comes first
COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")
SENTENCE_END = (".", "?", "!", "…")


def default_style(*, caption: str, overlay: str) -> dict:
    """The suggested style: TikTok captions (white, black outline, at the bottom, 2 to 4 words) and the overlays in a
    white box at the top, with the two sample lines the look draws."""
    return {"captions": {"fontSize": 64, "color": "#FFFFFF", "stroke": "#000000", "highlight": None,
                         "place": "bottom", "offsetY": 0, "width": SAFE_WIDTH, "words": [2, 4]},
            "overlays": {"fontSize": 58, "color": "#111111", "background": "#FFFFFF", "place": "top",
                         "offsetY": 0, "width": 680},
            "sample": {"caption": caption, "overlay": overlay}}


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def style_problems(style: object) -> list[str]:
    """What is wrong with a text style, one line each; [] when it can be used."""
    if not isinstance(style, dict):
        return ["The text style must be one JSON object with captions, overlays and sample."]
    out: list[str] = []
    colours = {"captions": ("color", "stroke"), "overlays": ("color", "background")}
    for layer in ("captions", "overlays"):
        group = style.get(layer)
        if not isinstance(group, dict):
            out.append(f"{layer} must be an object ({', '.join(default_style(caption='', overlay='')[layer])}).")
            continue
        size = group.get("fontSize")
        if not (_number(size) and 32 <= size <= 120):
            out.append(f"{layer}.fontSize must be a number from 32 to 120 (px at 1080×1920), not {size!r}.")
        for key in colours[layer]:
            if not (isinstance(group.get(key), str) and COLOUR.fullmatch(group[key])):
                out.append(f"{layer}.{key} must be a colour as #RRGGBB, not {group.get(key)!r}.")
        if group.get("place") not in PLACES:
            out.append(f"{layer}.place must be one of {', '.join(PLACES)}, not {group.get('place')!r}.")
        shift = group.get("offsetY", 0)
        if not (_number(shift) and -600 <= shift <= 600):
            out.append(f"{layer}.offsetY must be a number from -600 to 600 (px; negative moves up), not {shift!r}.")
        width = group.get("width")
        if not (_number(width) and 300 <= width <= SAFE_WIDTH):
            out.append(f"{layer}.width must be a number from 300 to {SAFE_WIDTH} (the safe zone's width), "
                       f"not {width!r}.")
    caps = style.get("captions") if isinstance(style.get("captions"), dict) else {}
    lit = caps.get("highlight")
    if "captions" in style and lit is not None and not (isinstance(lit, str) and COLOUR.fullmatch(lit)):
        out.append(f"captions.highlight must be a colour as #RRGGBB or null, not {lit!r}.")
    words = caps.get("words")
    if "captions" in style and not (isinstance(words, list) and len(words) == 2
                                    and all(isinstance(n, int) and not isinstance(n, bool) for n in words)
                                    and 1 <= words[0] <= words[1] <= 6):
        out.append(f"captions.words must be [min, max] words a caption shows, 1 to 6 (e.g. [2, 4]), not {words!r}.")
    sample = style.get("sample")
    if sample is not None and not (isinstance(sample, dict)
                                   and all(isinstance(sample.get(k), str) for k in ("caption", "overlay"))):
        out.append("sample must be {\"caption\": \"<a line of the voiceover>\", \"overlay\": \"<the hook>\"}.")
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(run: RunFolder, given: str, what: str) -> tuple[Path, str]:
    path = run.given(given)
    try:
        rel = path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise Stop(f"The {what} {c.name_of(given)} must be a file inside the run folder; {AGAIN}.") from None
    if not path.is_file():
        raise Stop(f"The {what} {rel} does not exist in the run; {AGAIN}.")
    return path, rel


def _json(path: Path, rel: str, what: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"The {what} {rel} is not valid JSON ({exc}); {AGAIN}.") from None


def _style_at(run: RunFolder, given: str) -> tuple[Path, str, dict]:
    path, rel = _inside(run, given, "text style")
    style = _json(path, rel, "text style")
    problems = style_problems(style)
    if problems:
        raise Stop(f"The text style {rel} cannot be used: {' '.join(problems)} Fix it in its next version "
                   f"({WIP}/{STYLE_STEM}_vNN.json); {AGAIN}.")
    return path, rel, style


def caption_entry(layer: str, group: dict, text: str, start: float, end: float,
                  words: list[dict] | None = None) -> dict:
    """One OrganicCaptions caption of a layer ("captions" or "overlays") in the style's `group`."""
    entry = {"from": round(start, 3), "to": round(end, 3), "text": text,
             "style": "caption" if layer == "captions" else "hook", "place": group["place"],
             "fontSize": group["fontSize"], "offsetY": group.get("offsetY", 0), "width": group["width"],
             "color": group["color"]}
    if layer == "captions":
        entry["stroke"] = group["stroke"]
        if group.get("highlight"):
            entry["highlight"] = group["highlight"]
        if words:
            entry["words"] = words
    else:
        entry["background"] = group["background"]
    return entry


def _stamp(rel: str, path: Path) -> dict:
    return {"file": rel, "sha256": _sha(path)}


def look(run: RunFolder, picture: str, *, style: str | None, caption: str | None, overlay: str | None,
         at: float = 0.0) -> dict:
    """The style drawn on the picture (the module docstring): {style, props, still}."""
    from tm import render   # it reads organic modules for an organic render: imported where it is used

    _, pic = _inside(run, picture, "picture")
    if style is None:
        if not (caption and caption.strip() and overlay and overlay.strip()):
            raise Stop("Without --style, give the two sample lines the look draws: --caption \"<a line of the "
                       f"voiceover>\" --overlay \"<the hook>\", in the audience language; {AGAIN}.")
        target = run.next_version("wip", STYLE_STEM, "json")
        c.write_json(target, default_style(caption=caption.strip(), overlay=overlay.strip()), newline="\n")
        c.record(run, target, "tm organic text look", None, params={"default": True}, cost="free")
        style = c.rel(run, target)
    path, rel, data = _style_at(run, style)
    sample = data.get("sample") or {}
    if not (sample.get("caption", "").strip() and sample.get("overlay", "").strip()):
        raise Stop(f"The text style {rel} has no sample lines to draw: write sample {{caption, overlay}} in its next "
                   f"version; {AGAIN}.")
    text = sample["caption"].split()
    step = 0.2      # each sample word 0.2 s: at the still's frame the second word is the one spoken
    words = [{"text": w, "from": round(i * step, 3), "to": round((i + 1) * step, 3)} for i, w in enumerate(text)]
    start = max(float(at), 0.0)
    props = {"width": 1080, "height": 1920, "fps": 24,
             "segments": [{"src": pic, "start": start, "end": start + LOOK_SECONDS}],
             "captions": [caption_entry("overlays", data["overlays"], sample["overlay"].strip(), 0, LOOK_SECONDS),
                          caption_entry("captions", data["captions"], " ".join(text), 0, LOOK_SECONDS, words)],
             "textStyle": _stamp(rel, path)}
    target = run.next_version("wip", LOOK_STEM, "props.json")
    c.write_json(target, props, newline="\n")
    png = target.with_name(target.name.removesuffix(".props.json") + ".png")
    done = render.still(run, "OrganicCaptions", target, LOOK_FRAME, png)
    return {"style": rel, "props": c.rel(run, target), "still": c.rel(run, done)}


def approved_style(run: RunFolder) -> tuple[str, str, dict] | None:
    """(file, sha256, style) of the approved text style, when it is the latest version and unchanged; else None."""
    if stepchecks.fresh(run, STYLE_KEY, WIP, STYLE_STEM, "json") is not None:
        return None
    entry = state.load(run).checked[STYLE_KEY]
    try:
        style = json.loads((run.path / entry["file"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return entry["file"], entry["sha256"], style


def _looks_of(run: RunFolder, sha: str) -> list[str]:
    """The stills drawn from a style (manifest rows of `tm render still` whose props carry its stamp)."""
    out = []
    for row in manifest.rows(run):
        if row["model"] != "remotion still":
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        props = params.get("props") if isinstance(params, dict) else None
        stamp = props.get("textStyle") if isinstance(props, dict) else None
        if isinstance(stamp, dict) and stamp.get("sha256") == sha:
            out.append(row["file"])
    return out


def approve(run: RunFolder, style: str, *, by: str, note: str) -> dict:
    path, rel, _ = _style_at(run, style)
    latest = run.latest(WIP, STYLE_STEM, "json")
    if latest is None or latest.resolve() != path.resolve():
        raise Stop(f"Only the latest text style is approved: {c.rel(run, latest) if latest else rel}. Draw its look "
                   f"and show it, then approve that one; {AGAIN}.")
    looks = _looks_of(run, _sha(path))
    if not looks:
        raise Stop(f"{rel} has no look drawn yet, and a style is never approved unseen: tm organic text look --run "
                   f"<run> --picture <the first frame> --style {rel}, show it, then approve; {AGAIN}.")
    stepchecks.mark(run, STYLE_KEY, path, extra={"by": by, "note": note, "look": looks[-1]})
    return {"style": rel, "look": looks[-1], "by": by}


# --- the captions layer ------------------------------------------------------------------------------

def caption_groups(words: list[dict], lo: int, hi: int, pause: float = PAUSE) -> list[list[dict]]:
    """Words ({word, start, end}) in groups: one closes at `hi` words, at a sentence's end, at a comma once it has `lo`
    words, and before a pause of `pause` seconds."""
    groups: list[list[dict]] = []
    group: list[dict] = []
    for w in words:
        if group and w["start"] - group[-1]["end"] > pause:
            groups.append(group)
            group = []
        group.append(w)
        word = w["word"].rstrip(organic_audio.CLOSING)
        comma = len(group) >= lo and word.endswith(organic_audio.PHRASE_END)
        if len(group) >= hi or word.endswith(SENTENCE_END) or comma:
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    return groups


def _read_words(path: Path, rel: str) -> list[dict]:
    """[{word, start, end}] from an ElevenLabs words file (a list) or a transcript (`segments[].words`)."""
    data = _json(path, rel, "words file")
    raw = data if isinstance(data, list) else [w for seg in (data.get("segments") or []) if isinstance(seg, dict)
                                                for w in (seg.get("words") or [])] if isinstance(data, dict) else None
    words = []
    for w in raw or []:
        if (isinstance(w, dict) and isinstance(w.get("word"), str) and w["word"].strip()
                and _number(w.get("start")) and _number(w.get("end"))):
            words.append({"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])})
    if not words:
        raise Stop(f"{rel} holds no words with times ([{{word, start, end}}], or a transcript's segments[].words); "
                   f"{AGAIN}.")
    return words


def _place(props: dict, words: list[dict], words_rel: str, source: str | None, offset: float | None
           ) -> tuple[list[dict], float | None]:
    """The words at their seconds in the edit, and the voiceover's offset (None when placed through cuts)."""
    key = organic_final._key
    if source is None:
        stem = Path(words_rel).name.removesuffix(".json").removesuffix(".words").casefold()
        named = [t.get("src") for t in props.get("audioTracks") or [] if isinstance(t, dict)
                 and isinstance(t.get("src"), str) and Path(t["src"]).stem.casefold() == stem]
        named += [s.get("src") for s in props.get("segments") or [] if isinstance(s, dict)
                  and isinstance(s.get("src"), str) and Path(s["src"]).stem.casefold() == stem]
        source = named[0] if named else None
    if source is not None:
        track = next((t for t in props.get("audioTracks") or [] if isinstance(t, dict)
                      and isinstance(t.get("src"), str) and key(t["src"]) == key(source)), None)
        if track is not None:
            offset = float(track.get("from") or 0) if offset is None else offset
        elif offset is None:
            placed, cursor = [], 0.0
            for seg in props.get("segments") or []:
                if not isinstance(seg, dict):
                    continue
                start, end = float(seg.get("start") or 0), float(seg.get("end") or 0)
                if isinstance(seg.get("src"), str) and key(seg["src"]) == key(source):
                    placed += [{**w, "start": cursor + w["start"] - start, "end": cursor + min(w["end"], end) - start}
                               for w in words if start <= w["start"] < end]
                cursor += end - start
            if not any(isinstance(s, dict) and isinstance(s.get("src"), str) and key(s["src"]) == key(source)
                       for s in props.get("segments") or []):
                raise Stop(f"The edit neither plays nor cuts {source}: give --source, the voiceover in its "
                           f"audioTracks or the take its segments cut; {AGAIN}.")
            return placed, None
    if offset is None:
        raise Stop(f"Which recording are the words of {words_rel}? Give --source <the voiceover or the take> (as the "
                   f"edit names it) or --from <the seconds the voiceover starts at>; {AGAIN}.")
    return [{**w, "start": w["start"] + offset, "end": w["end"] + offset} for w in words], offset


def captions(run: RunFolder, props_file: str, words_file: str, *, source: str | None = None,
             offset: float | None = None) -> dict:
    """The edit's next props with both text layers in the approved style (the module docstring)."""
    approved = approved_style(run)
    if approved is None:
        raise Stop("The text style is approved first: draw it on the first frame (tm organic text look --run <run> "
                   "--picture <the first frame> ...), show it at the images check-in, then tm organic text approve "
                   f"with the user's words; {AGAIN}.")
    style_rel, _, style = approved
    path, rel = _inside(run, props_file, "edit's props")
    props = _json(path, rel, "edit's props")
    if not isinstance(props, dict):
        raise Stop(f"The edit's props {rel} must be one JSON object; {AGAIN}.")
    given = [x for x in props.get("captions") or [] if isinstance(x, dict)]
    overlays = [x for x in given if x.get("style") != "caption"]
    if len(overlays) > OVERLAYS_MAX:
        raise Stop(f"The edit has {len(overlays)} overlays ({'; '.join(str(o.get('text')) for o in overlays)}): the "
                   f"overlays carry only the hook, the key number and the closing question, at most {OVERLAYS_MAX}. "
                   f"The rest is said in the voiceover and shown in its captions. Nothing was written; {AGAIN}.")
    wpath, wrel = _inside(run, words_file, "words file")
    placed, start = _place(props, _read_words(wpath, wrel), wrel, source, offset)
    lo, hi = style["captions"]["words"]
    groups = caption_groups(placed, lo, hi)
    layer = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0]["start"] if i + 1 < len(groups) else None
        end = g[-1]["end"] + TAIL if nxt is None else min(g[-1]["end"] + TAIL, nxt)
        words = [{"text": w["word"], "from": round(w["start"], 3), "to": round(w["end"], 3)} for w in g]
        layer.append(caption_entry("captions", style["captions"], " ".join(w["word"] for w in g), g[0]["start"],
                                   max(end, g[0]["start"] + 0.1), words))
    tops = [{**caption_entry("overlays", style["overlays"], str(o.get("text", "")), float(o.get("from") or 0),
                             float(o.get("to") or 0))} for o in overlays]
    out = {**props, "captions": tops + layer, "textStyle": _stamp(style_rel, run.path / style_rel)}
    stem = re.sub(r"_v\d+$", "", Path(rel).name.removesuffix(".json").removesuffix(".props"))
    target = run.next_version("wip", stem or "edit", "props.json")
    c.write_json(target, out, newline="\n")
    c.record(run, target, "tm organic captions", rel, params={"words": wrel, "style": style_rel, "offset": start,
                                                               "captions": len(layer), "overlays": len(tops)},
             cost="free")
    return {"props": c.rel(run, target), "offset": start, "captions": len(layer), "overlays": len(tops),
            "style": style_rel}


# --- G1: the edit follows the approved style ----------------------------------------------------------

CAPTIONS_CMD = ("tm organic captions --run <run> --props <the edit's props> --words <the voiceover's .words.json>, "
                "then render and finish it again")


def _edit_render(run: RunFolder, final: Path) -> tuple[str, dict] | None:
    """(the render, its props) of the OrganicCaptions edit a final was made from, up the manifest's parents."""
    rows = organic_final._rows(run)
    for key in organic_final._lineage(rows, c.rel(run, final)):
        row = rows.get(key)
        if not row or row["model"] != "remotion render":
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            return None
        props = params.get("props") if isinstance(params, dict) else None
        if params.get("composition") == "OrganicCaptions" and isinstance(props, dict):
            return row["file"], props
        return None
    return None


def text_gap(run: RunFolder) -> str | None:
    """G1's `text_followed` check (the module docstring). Reads only."""
    pid = organic_final.idea_id(run)
    final = organic_final.final_of(run, pid) if pid else None
    edit = _edit_render(run, final) if final is not None else None
    if edit is None:
        return None
    render_rel, props = edit
    texts = [x for x in props.get("captions") or [] if isinstance(x, dict)]
    voiced = isinstance(props.get("audioTracks"), list) and bool(props["audioTracks"])
    if not texts:
        return (f"the edit the final was made from ({render_rel}) has captions under the voiceover ({CAPTIONS_CMD})"
                if voiced else None)
    approved = approved_style(run)
    if approved is None:
        return ("the text style is approved: drawn on the first frame (tm organic text look), shown at the images "
                "check-in and approved (tm organic text approve)")
    stamp = props.get("textStyle") if isinstance(props.get("textStyle"), dict) else {}
    if stamp.get("sha256") != approved[1]:
        return (f"the edit the final was made from ({render_rel}) has its text in the approved style ({approved[0]}): "
                f"{CAPTIONS_CMD}")
    return None


# --- command line (tm organic text, tm organic captions) ---------------------------------------------

def add_parsers(sub) -> None:
    t = sub.add_parser("text", help="the edit's text style: its look on the first frame and the user's approval")
    ts = t.add_subparsers(dest="text_action", required=True)
    a = ts.add_parser("look", help="draw the text style on a picture: 03_wip/text_look_vNN.png (free)")
    a.add_argument("--run", required=True)
    a.add_argument("--picture", required=True, help="the first frame (or a take) in the run")
    a.add_argument("--style", help="03_wip/text_style_vNN.json (default: the suggested style, written as the next one)")
    a.add_argument("--caption", help="without --style: a line of the voiceover, in the audience language")
    a.add_argument("--overlay", help="without --style: the hook, in the audience language")
    a.add_argument("--at", type=float, default=0.0, help="seconds into a video picture (default 0)")
    a.add_argument("--json", action="store_true")
    a = ts.add_parser("approve", help="record the user's yes to the latest text style, once its look was shown")
    a.add_argument("--run", required=True)
    a.add_argument("--style", required=True)
    a.add_argument("--by", choices=("user", "rule"), default="user")
    a.add_argument("--note", required=True, help="the user's words (by rule: the rubric)")
    a.add_argument("--json", action="store_true")
    a = sub.add_parser("captions", help="the edit's next props with both text layers in the approved style")
    a.add_argument("--run", required=True)
    a.add_argument("--props", required=True, help="the edit's props, 03_wip/edit_vNN.props.json")
    a.add_argument("--words", required=True, help="<stem>.words.json of the voiceover, or a take's transcript")
    a.add_argument("--source", help="the recording the words are of, as the edit names it (default: by the name)")
    a.add_argument("--from", dest="offset", type=float, help="the seconds the voiceover starts at in the edit")
    a.add_argument("--json", action="store_true")


def _text(args: argparse.Namespace) -> int:
    run = RunFolder.open(Path(args.run))
    if args.text_action == "look":
        out = look(run, args.picture, style=args.style, caption=args.caption, overlay=args.overlay, at=args.at)
        message = (f"Drew {out['style']} on {args.picture}: {out['still']}. Show it at the images check-in (the images "
                   "page shows it beside every item, or send the PNG); their changes are a new style version.")
    else:
        out = approve(run, args.style, by=args.by, note=args.note)
        message = (f"Approved {out['style']} (its look {out['look']}). The edit's captions follow it "
                   "(tm organic captions).")
    cli.emit(args, {"status": "done", **out, "message": message}, message)
    return 0


def _captions(args: argparse.Namespace) -> int:
    out = captions(RunFolder.open(Path(args.run)), args.props, args.words, source=args.source, offset=args.offset)
    message = (f"Wrote {out['props']}: {out['captions']} captions and {out['overlays']} overlays in {out['style']}. "
               "Render it with tm render video.")
    cli.emit(args, {"status": "done", **out, "message": message}, message)
    return 0


ACTIONS = {"text": _text, "captions": _captions}
