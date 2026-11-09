"""Edit-list rules for re-cuts (path C-R): `tm recut points | check | music`.

    tm recut points --run RUN --teardown T [--transcript X] [--json]
    tm recut check  --run RUN EDIT.json --teardown T [--transcript X] [--json]
    tm recut music  --run RUN --target-s S [--json]

Claude writes one JSON edit list per re-cut variant in the handoff's `tools/recut.py` format
(handoff v03: `out`, `video` segments with `src`, `from`, `to`, `speed`, `seam`, `audio` segments,
`audio_mode`, `audio_tail` / `audio_head`; every `src` is relative to the edit list's own folder).
This build adds header fields: `variant` (str), `change_id` (the id of a `stage: middle` entry in
supported_changes.yaml, a re-cut: `changes.recut_ids()`), `level` (0-5, VARIANTS.md 3b), `cause`
(str), `music_source` (one of `recut.music_source`, or "sync" when the picture segments carry their
own sound) and, optionally, `jump` ("hard" | "punch_in" | "broll") and `draft` (bool).

`check` decides whether an edit list is legal before anything is rendered. Frames are source frames
at the teardown's fps (its `fps`, else a scene's start_frame / start_s), never an assumed 30. A
segment's first source frame is floor(from * fps), its last ceil(to * fps) - 1. The teardown's file
is its `video` (a path inside the run, or a bare name for a file outside it): each `src` is resolved
against the edit list's folder and matched to it; a hand-made teardown without `video` falls back to
the file most segments use. Segments of other files are other footage: each file is its own shot. A
segment that carries on from the previous one (same file, the next frame, no dissolve, e.g. a speed
change) is not a cut. The rules, each with its own message:

1. Flash margin. FLOWS.md CR4: "ending >= 2 frames before a shot change"; CR6 "one-frame flash (... the
   next shot pulled in by the 30 fps conversion)"; C-R lessons: "The 30 fps conversion can pull the
   first frame of the next shot into a segment that ends within about a frame of a shot change."
   A segment's last frame must be <= change - 2 for any shot change after its start within 2 frames
   of its end; the start mirrors it: its first frame must not be change - 3 to change - 1.
   Slivers: a piece of another shot at either edge of a segment (the frames after its last shot
   change, or before its first) is at least MIN_PIECE_FRAMES (8) frames, about 0.27 s at 30 fps: a
   segment ending 4-7 frames into the next shot, or starting 4-7 frames before a change, flashes
   that shot. So a segment starts at a change or 8 frames or more before it, and ends 2 frames
   before a change or 8 frames or more after it. "Another shot" is one the neighbouring segment
   does not show at that edge: when it does (a jump cut inside a talking-head shot, ad_2 J1 v05's
   segment 2 starting 5 frames before a change), the shot stays on screen and the frames both
   segments show of it count together.
2. No joint inside a continuous shot. CR4: "never inside one continuous shot (regenerate the shot
   instead, L4)"; VARIANTS.md 3b "do not patch a cut inside it (dissolve and FILM looked poor in R6)".
   "At a shot change" means the joint changes shot (Ad 3 R1, 11.146 -> 20.735 s: "the cut falls on
   the shot change, so it reads as a normal edit"), not that both its times sit on a change:
   a. A joint whose two sides (the outgoing segment's last frame, the incoming one's first) lie in
      the same shot is refused: a `seam: "dissolve"` always, a plain cut unless the ad has speech,
      `audio_mode` is "sync", a `jump` is declared and both audio cut points sit in a speech gap
      (the talking-head jump cut, ad_2 J1-J3).
   b. A shot played in separated pieces (its pieces do not follow each other in the output) is
      refused (an edge piece rule 1 or the sliver rule reports is not counted; one the neighbour
      exception lets through is): a scene reorder inside a continuous shot (RC12; C-R lessons "an ad of one or two
      continuous shots (Ad 3) has nothing to reorder without cutting inside a shot"). Swapping whole
      shots is legal.
   The output's own start and end are free.
   c. In sync mode no joint dissolves: the picture overlaps by the dissolve but the sound does not,
      so every later word would play late. A dissolve can't be used with speech: cut instead.
3. Speech is cut in sync mode. CR4: "Speech (talking head, VO): audio_mode: "sync"" and "speech audio
   in speech gaps, never mid-word". When the teardown has speech, `audio_mode` must be "sync", and
   no audio cut point (what recut.py reads: `from - max(audio_head, half the sync crossfade)` and
   `from + length + max(audio_tail, half the sync crossfade)`) may fall inside a transcript word.
4. Final music has no beat-cut joints. CR4: "a beat-cut edit of the track is never the final music";
   VARIANTS.md 3c: "Cutting the mixed or extracted music on beats gave audible jumps (Ad 3 R1)".
   More than one `audio` segment from the same file is refused unless `draft: true`.
5. Level. VARIANTS.md 3b (L0-L5) and PLAYBOOK.md Config `recut.max_level` ("AUTO: 2 (L3-L5 need
   budget.ai_*); HITL: asked"). L3 and L4 need `ai_usd` approved, L5 `voice_credits`; a missing
   budget makes the edit list wait. Above `recut.max_level` it waits in Hands-off and is refused
   otherwise; an unset max_level counts as 2 in Hands-off and passes otherwise (G3r asked).

`extra_audio` layers ({src, at, gain_db}) are checked too: `src` a file name, `at` seconds from 0 to
below the output's length, `gain_db` a number when given. The renderer mixes the values `extra_audio`
returns.

Lengths. `timeline` is the one place the output's frames are counted, for `check` and for
`tm tool recut` alike: segment i is exactly round-half-up((to - from) / speed * fps) frames at the
edit list's `fps` (default 30), and the renderer forces each segment to that count. Joint times,
the output length and the sync audio cut points all follow from those counts.

Known limit: footage rendered from the original before the edit list (e.g. ad_2 J2's punch-in clip
`seg3_punchin112.mp4`) is another file to `check`, so its source frames are not seen: a flash baked
into it (J2 v04) passes here. Task 7's QA (tools/recut_qa.py) checks the rendered output for it.

Every checked edit list is recorded in run.json `recut.checked`, by `tm recut check` and by
`tm tool recut` alike (`record`): {edit, variant, change_id, level, joints_s, length_s, audio_mode,
music_source, status}.

Music takes (`tm recut music`): each take `03_wip/audio/<name>_vNN.<ext>` has a record
`<name>_vNN.<ext>.json` with at least {"kind": "music_take", "file": "<take file name>",
"length_s": float, "model": str, "plan": {...}, "credits_used": int | null}; `elevenlabs
music-compose` writes it. A take within +/-0.05 s of the picture is reused (RC17: 0 credits). A record
still "music_pending" is a paid take whose file was not saved: `tm recut music` then answers
"resume" with the record, as `elevenlabs music-compose --resume <record>` fetches it for free.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import posixpath
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from tm import changes, cli, config, state
from tm.runfolder import ReadOnlyError, RunFolder
from tm.tools._common import ToolError, name_of, read_json, resolve

MARGIN_FRAMES = 2          # a segment ends >= 2 frames before a shot change (FLOWS.md CR4)
MIN_PIECE_FRAMES = 8       # a piece of another shot at a segment's edge (ruling, PR B review item 5)
SPEECH_GAP_MIN_S = 0.12    # the shortest gap the reference edit lists cut audio into (ad_2 cold open: 25.52-25.64 s)
JUMPS = ("hard", "punch_in", "broll")
LEVELS = range(0, 6)
HANDS_OFF_MAX_LEVEL = 2    # PLAYBOOK.md Config: recut.max_level AUTO: 2
TAKE_TOLERANCE_S = 0.05    # reuse an existing take within +/-0.05 s (HANDOFF 9b-2, RC17)
CREDITS_PER_TAKE = 220     # about 220 ElevenLabs credits per music take (FLOWS.md CR5)
OUT_FPS = 30               # recut.py's default output frame rate
BUDGET_FOR_LEVEL = {3: "ai_usd", 4: "ai_usd", 5: "voice_credits"}
_SERVICE = {"ai_usd": "Replicate (ProPainter, FILM, Veo)", "voice_credits": "ElevenLabs (music, voice)"}
_EPS = 1e-6

Status = Literal["ok", "refused", "waiting"]


@dataclass
class Verdict:
    status: Status
    problems: list[str] = field(default_factory=list)
    joints_s: list[float] = field(default_factory=list)
    length_s: float = 0.0
    level: int = -1

    def to_json(self) -> dict:
        return asdict(self)


class _Problems:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def refuse(self, text: str) -> None:
        self.items.append(("refused", text))

    def wait(self, text: str) -> None:
        self.items.append(("waiting", text))

    def status(self) -> Status:
        kinds = {k for k, _ in self.items}
        return "refused" if "refused" in kinds else "waiting" if "waiting" in kinds else "ok"

    @property
    def texts(self) -> list[str]:
        return [t for _, t in self.items]


# --- the teardown and the transcript ------------------------------------------------------

def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def source_fps(teardown: dict) -> float:
    """The source frame rate: the teardown's `fps`, else derived from a shot change's frame and time."""
    fps = teardown.get("fps")
    if _number(fps) and fps > 0:
        return float(fps)
    known = [sc for sc in teardown.get("scenes") or [] if isinstance(sc, dict) and _number(sc.get("start_frame"))
             and _number(sc.get("start_s")) and sc["start_frame"] > 0 and sc["start_s"] > 0]
    if known:  # the latest shot change: its 3-decimal seconds give the smallest rounding error
        sc = max(known, key=lambda x: x["start_frame"])
        return sc["start_frame"] / sc["start_s"]
    raise ValueError("The teardown has no fps and no shot change to derive it from, so cut points "
                     "cannot be counted in source frames. Run tm tool teardown on the video again.")


def _changes(teardown: dict) -> list[int]:
    scenes = teardown.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("The teardown has no scenes list. Run tm tool teardown on the video again.")
    frames = []
    for sc in scenes:
        if not isinstance(sc, dict) or not _number(sc.get("start_frame")):
            raise ValueError("A teardown scene has no start_frame. Run tm tool teardown on the video again.")
        if sc["start_frame"] > 0:
            frames.append(int(sc["start_frame"]))
    return sorted(set(frames))


def _frame_count(teardown: dict, fps: float) -> int | None:
    n = teardown.get("frame_count")
    if _number(n) and n > 0:
        return int(n)
    ends = [sc.get("end_frame") for sc in teardown.get("scenes") or [] if isinstance(sc, dict)]
    ends = [int(e) for e in ends if _number(e)]
    if ends:
        return max(ends) + 1
    dur = teardown.get("duration_s")
    return round(dur * fps) if _number(dur) and dur > 0 else None


def words(transcript: dict | None) -> list[dict]:
    """The transcript's words ({start, end, word}) in time order (tm tool transcribe's schema)."""
    out = []
    for seg in (transcript or {}).get("segments") or []:
        for w in (seg or {}).get("words") or []:
            if isinstance(w, dict) and _number(w.get("start")) and _number(w.get("end")):
                out.append({"start": float(w["start"]), "end": float(w["end"]),
                            "word": str(w.get("word") or "").strip()})
    return sorted(out, key=lambda w: w["start"])


def _gaps(ws: list[dict]) -> list[list[float]]:
    return [[a["end"], b["start"]] for a, b in zip(ws, ws[1:])
            if b["start"] - a["end"] >= SPEECH_GAP_MIN_S - 1e-9]


def points(teardown: dict, transcript: dict | None) -> dict:
    """Where an edit list may cut: shot changes (source frames), card switches and speech gaps (s)."""
    fps = source_fps(teardown)
    shot_changes = [{"frame": c, "s": round(c / fps, 3)} for c in _changes(teardown)]
    for sc in teardown.get("scenes") or []:  # the teardown's own seconds, where it gives them
        for p in shot_changes:
            if sc.get("start_frame") == p["frame"] and _number(sc.get("start_s")):
                p["s"] = round(float(sc["start_s"]), 3)
    n = _frame_count(teardown, fps)
    end = n / fps if n else math.inf
    switches = set()
    for o in teardown.get("overlays") or []:
        for key in ("start_s", "end_s"):
            t = (o or {}).get(key)
            if _number(t) and 0 < t < round(end, 3) - _EPS:
                switches.add(round(float(t), 3))
    return {"fps": fps, "shot_changes": shot_changes, "card_switches": sorted(switches),
            "speech_gaps": _gaps(words(transcript))}


# --- the edit list --------------------------------------------------------------------------

def norm_src(src: str) -> str:
    """A `src` as a POSIX path: backslashes (an edit list written on Windows) become slashes."""
    return posixpath.normpath(src.replace("\\", "/"))


def _nfc(text: str) -> str:  # macOS hands out NFD names, an edit list is usually typed in NFC
    return unicodedata.normalize("NFC", text)


def _blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def _header(edit: dict, cfg: dict | None, out: _Problems, material: str | None = None) -> int:
    for key, what in (("variant", "the variant's name"), ("change_id", "the change's id from supported_changes.yaml"),
                      ("cause", "the diagnosed cause this variant removes")):
        if _blank(edit.get(key)):
            out.refuse(f'The edit list needs "{key}": {what}, as a non-empty string. Add it and check again.')
    allowed = changes.recut_ids()
    if not _blank(edit.get("change_id")) and edit["change_id"] not in allowed:
        out.refuse(f'"change_id" must be one of the re-cut changes in supported_changes.yaml (stage '
                   f'middle): {", ".join(allowed)}, not {edit["change_id"]!r}. Name the change this '
                   'variant makes and check again.')
    elif not _blank(edit.get("change_id")) and material is not None:
        fits = [c.id for c in changes.for_stage(changes.RECUT_STAGE, material)]
        if edit["change_id"] not in fits:
            name = changes.MATERIAL_NAMES.get(material, material)
            out.refuse(f'"change_id" {edit["change_id"]!r} is not a re-cut for this ad, a {name} (the '
                       f"run's material): the re-cuts for a {name} are {', '.join(fits) or 'none'}. "
                       "Choose one of them and check again.")
    level = edit.get("level")
    good_level = isinstance(level, int) and not isinstance(level, bool) and level in LEVELS
    if not good_level:
        out.refuse(f'"level" must be a whole number from 0 to 5 (VARIANTS.md 3b), not {level!r}: '
                   "the lowest level that removes the cause.")
    chain = list(config.value(cfg, "recut.music_source") or [])
    source = edit.get("music_source")
    if source != "sync" and source not in chain:
        out.refuse(f'"music_source" must be one of {", ".join(chain)} (recut.music_source), or "sync" when '
                   f"the picture segments carry their own sound, not {source!r}.")
    sync = edit.get("audio_mode") == "sync"
    if source == "sync" and not sync:
        out.refuse('"music_source" is "sync", but "audio_mode" is not "sync": the sound comes with the '
                   'picture only in sync mode. Set "audio_mode": "sync", or name where the music comes from.')
    elif sync and source in chain:
        out.refuse(f'"audio_mode" is "sync", so the sound comes with the picture segments and the '
                   f'"audio" list is not used: "music_source" must be "sync", not {source!r}.')
    if "jump" in edit and edit["jump"] not in JUMPS:
        out.refuse(f'"jump" must be one of {", ".join(JUMPS)}, not {edit["jump"]!r}.')
    if "draft" in edit and not isinstance(edit["draft"], bool):
        out.refuse(f'"draft" must be true or false, not {edit["draft"]!r}.')
    return level if good_level else -1


def _segments(edit: dict, key: str, out: _Problems, *, required: bool) -> list[dict] | None:
    segs = edit.get(key, [] if not required else None)
    if not isinstance(segs, list) or (required and not segs):
        out.refuse(f'The edit list needs "{key}" as a list of segments{" (at least one)" if required else ""}.')
        return None
    good = True
    for i, s in enumerate(segs, 1):
        name = f'{key} segment {i}'
        if not isinstance(s, dict) or _blank(s.get("src")):
            out.refuse(f'{name} needs "src": the file, relative to the edit list\'s folder.')
            good = False
            continue
        a, b = s.get("from"), s.get("to")
        if not (_number(a) and _number(b) and 0 <= a < b):
            out.refuse(f'{name} needs "from" < "to", both seconds of the source, not {a!r} and {b!r}.')
            good = False
        speed = s.get("speed", 1.0)
        if not (_number(speed) and speed > 0):
            out.refuse(f'{name}: "speed" must be a number above 0, not {speed!r}.')
            good = False
        if s.get("seam", "cut") not in ("cut", "dissolve"):
            out.refuse(f'{name}: "seam" must be "cut" or "dissolve", not {s.get("seam")!r}.')
            good = False
        frames = s.get("seam_frames", 6)
        if not (_number(frames) and frames > 0):
            out.refuse(f'{name}: "seam_frames" must be a number of frames above 0, not {frames!r}.')
            good = False
        for extra in ("audio_tail", "audio_head", "audio_from"):
            if extra in s and not (_number(s[extra]) and s[extra] >= 0):
                out.refuse(f'{name}: "{extra}" must be seconds (0 or more), not {s[extra]!r}.')
                good = False
    return segs if good else None


@dataclass
class Timeline:
    """The output as `tm tool recut` renders it: segment i is exactly `frames[i]` frames at `fps`."""
    fps: float
    frames: list[int]
    lens_s: list[float]       # frames[i] / fps
    starts_s: list[float]     # where segment i starts in the output (a dissolve overlaps the previous one)
    fades_s: list[float]      # the dissolve before segment i + 1 (0 for a cut)
    joints_s: list[float]     # the middle of each joint, rounded to 1 ms
    length_s: float
    sync_reads: list[dict]    # sync mode: {src, from, start, end, head, tail} each segment's sound is read from


def out_fps(edit: dict) -> float:
    fps = edit.get("fps", OUT_FPS)
    return float(fps) if _number(fps) and fps > 0 else float(OUT_FPS)


def segment_frames(seconds: float, fps: float) -> int:
    """Output frames of a segment `seconds` long: round half up, at least one."""
    return max(1, math.floor(seconds * fps + 0.5 + 1e-9))


def timeline(edit: dict, fps_out: float | None = None) -> Timeline:
    """Frame counts, joints, length and sync audio cut points of an edit list whose segments are valid."""
    video = edit["video"]
    fps = float(fps_out) if fps_out else out_fps(edit)
    frames = [segment_frames((s["to"] - s["from"]) / s.get("speed", 1.0), fps) for s in video]
    lens = [n / fps for n in frames]
    starts, fades, joints = [0.0], [], []
    for i in range(1, len(video)):
        s = video[i]
        d = s.get("seam_frames", 6) / fps if s.get("seam", "cut") == "dissolve" else 0.0
        start = starts[-1] + lens[i - 1] - d
        starts.append(start)
        fades.append(d)
        joints.append(round(start + d / 2, 3))
    xf = edit.get("sync_xfade_ms", 40)
    x = (xf if _number(xf) else 40) / 1000 / 2
    last = len(video) - 1
    reads = []
    for k, (s, ln) in enumerate(zip(video, lens)):
        a_from = float(s.get("audio_from", s["from"]))
        head = min(max(x, s.get("audio_head", 0.0)), a_from) if k > 0 else 0.0
        tail = max(x, s.get("audio_tail", 0.0)) if k < last else 0.0
        reads.append({"src": s.get("audio_src", s["src"]), "from": a_from, "start": a_from - head,
                      "end": a_from + ln + tail, "head": head, "tail": tail})
    return Timeline(fps, frames, lens, starts, fades, joints, round(sum(lens) - sum(fades), 3), reads)


def extra_audio(edit: dict, length_s: float) -> tuple[list[dict], list[str]]:
    """(the `extra_audio` layers as the renderer mixes them: {src, at, gain_db}, the problems)."""
    layers = edit.get("extra_audio", [])
    if not isinstance(layers, list):
        return [], ['"extra_audio" must be a list of layers ({"src", "at", "gain_db"}), not '
                    f"{type(layers).__name__}."]
    good, problems = [], []
    for i, layer in enumerate(layers, 1):
        name = f"extra_audio layer {i}"
        if not isinstance(layer, dict) or _blank(layer.get("src")):
            problems.append(f'{name} needs "src": the sound file, relative to the edit list\'s folder.')
            continue
        name += f" ({name_of(layer['src'])})"
        at, gain = layer.get("at"), layer.get("gain_db", 0)
        fine = True
        if not (_number(at) and 0 <= at < length_s):
            problems.append(f'{name}: "at" must be the second it starts in the output, from 0 to below the '
                            f"output's {length_s:g} s, not {at!r}.")
            fine = False
        if not _number(gain):
            problems.append(f'{name}: "gain_db" must be a number of dB (0 keeps its level), not {gain!r}.')
            fine = False
        if fine:
            good.append({"src": layer["src"], "at": float(at), "gain_db": float(gain)})
    return good, problems


def _teardown_file(srcs: list[str], teardown: dict, base: Path | None,
                   edit_dir: Path | None) -> tuple[str | None, str | None]:
    """(the src key of the file the teardown describes, or a problem when no segment uses it).

    The teardown's `video` is the file's path inside the run, or its bare name when it lives outside
    the run (tools/_common.parent_ref). With `base` and `edit_dir` paths are compared resolved; without,
    a src matches when its path ends with `video`. A teardown without `video` (hand-made) falls back
    to the file most segments use.
    """
    ref = teardown.get("video")
    if not isinstance(ref, str) or not ref.strip():
        counts = Counter(srcs)
        return max(srcs, key=lambda s: (counts[s], -srcs.index(s))), None
    ref_n = _nfc(norm_src(ref))
    bare = "/" not in ref_n
    if base is not None and edit_dir is not None and not bare:
        target = _nfc(str((Path(base) / ref_n).resolve()))
        found = {s for s in srcs if s == target}
    elif bare:
        found = {s for s in srcs if name_of(s) == ref_n}
    else:
        tail = ref_n.split("/")
        found = {s for s in srcs if s.replace("\\", "/").split("/")[-len(tail):] == tail}
    if len(found) == 1:
        return found.pop(), None
    if not found:
        return None, (f"No segment uses {ref}, the file this teardown describes, so its shot changes say nothing "
                      "about these cuts. Give the teardown of the file the edit list cuts (tm tool teardown), "
                      "or fix the segments' src.")
    segs = [str(i + 1) for i, s in enumerate(srcs) if s in found]
    listed = ", ".join(segs[:-1]) + " and " + segs[-1]
    return None, (f"Several different files are named like {name_of(ref)}, the file this teardown describes "
                  f"(segments {listed} use them). Give the segments' src paths so that only one is that file.")


# --- check ----------------------------------------------------------------------------------

def check(edit: dict, teardown: dict, transcript: dict | None, cfg: dict | None, *,
          mode: str, approved: set[str], base: Path | None = None, edit_dir: Path | None = None,
          material: str | None = None) -> Verdict:
    """Whether an edit list is legal before anything is rendered (the five rules above).

    `material` is the run's recorded material (`tm material`): when given, `change_id` must be a
    re-cut whose `materials` include it.

    `base` is the run folder the teardown's `video` is relative to, `edit_dir` the edit list's own
    folder its `src` paths are relative to; with both, files are compared as resolved paths.
    """
    if not isinstance(edit, dict):
        raise ValueError("The edit list must be one JSON object.")
    if not isinstance(teardown, dict):
        raise ValueError("The teardown must be one JSON object (tm tool teardown).")
    out = _Problems()
    level = _header(edit, cfg, out, material)
    video = _segments(edit, "video", out, required=True)
    audio = _segments(edit, "audio", out, required=False)
    if video is None or audio is None:
        return Verdict(out.status(), out.texts, [], 0.0, level)
    fps = source_fps(teardown)
    changes = _changes(teardown)
    n = _frame_count(teardown, fps)
    tl = timeline(edit)
    joints, length = tl.joints_s, tl.length_s
    for text in extra_audio(edit, length)[1]:
        out.refuse(text)
    sync = edit.get("audio_mode") == "sync"
    if sync:
        for k, s in enumerate(video, 1):
            if s.get("seam") == "dissolve":
                out.refuse(f'Segment {k} has "seam": "dissolve" in sync mode: the picture overlaps by the dissolve '
                           "but the sound does not, so every later word would play late. In sync mode a dissolve "
                           'can\'t be used with speech: cut instead ("seam": "cut").')

    def key(src: str) -> str:
        path = str((Path(edit_dir) / norm_src(src)).resolve()) if edit_dir is not None else norm_src(src)
        return _nfc(path)

    srcs = [key(s["src"]) for s in video]
    main, wrong = _teardown_file(srcs, teardown, base, edit_dir)
    if wrong:
        out.refuse(wrong)
        return Verdict(out.status(), out.texts, joints, length, level)

    def clamp(f: int) -> int:
        return max(0, min(f, n - 1)) if n else max(0, f)

    first = [clamp(math.floor(s["from"] * fps + _EPS)) for s in video]
    last = [clamp(math.ceil(s["to"] * fps - _EPS) - 1) for s in video]

    def shot(f: int) -> int:
        return bisect.bisect_right(changes, f)

    def shot_span(i: int) -> str:
        a = changes[i - 1] / fps if i > 0 else 0.0
        b = changes[i] / fps if i < len(changes) else (n / fps if n else math.inf)
        return f"shot {i + 1} ({a:.2f}-{b:.2f} s of the source)"

    def edge(k: int, end: bool) -> tuple[int, int]:  # (shot, frames) of segment k's first or last piece
        inner = [c for c in changes if first[k] < c <= last[k]]
        if end:
            return shot(last[k]), last[k] + 1 - (inner[-1] if inner else first[k])
        return shot(first[k]), (inner[0] if inner else last[k] + 1) - first[k]

    def on_screen(k: int, end: bool) -> int:  # frames of that shot in a row, with the neighbour's
        sh, frames = edge(k, end)
        j = k + 1 if end else k - 1
        if 0 <= j < len(video) and srcs[j] == main and edge(j, not end)[0] == sh:
            frames += edge(j, not end)[1]
        return frames

    def reported(k: int, end: bool) -> bool:  # rule 1 or the sliver rule reports this edge piece
        frames = edge(k, end)[1]
        j = k + 1 if end else k  # the segment whose start is this joint
        if 0 < j < len(video) and carries_on(j):
            return frames < MIN_PIECE_FRAMES  # a speed change goes on with the shot: as before
        if frames <= MARGIN_FRAMES + 1:
            return True  # rule 1's flash
        return frames < MIN_PIECE_FRAMES and on_screen(k, end) < MIN_PIECE_FRAMES

    def carries_on(k: int) -> bool:  # segment k continues segment k - 1: not a cut
        if srcs[k] != srcs[k - 1] or video[k].get("seam") == "dissolve":  # recut.py blends a dissolve
            return False
        if srcs[k] == main:
            return 0 <= first[k] - last[k - 1] <= 1
        return abs(video[k]["from"] - video[k - 1]["to"]) <= 1.0 / OUT_FPS

    ws = words(transcript)
    gaps = _gaps(ws)
    has_speech = teardown.get("has_speech") is True or bool(ws)
    cuts = [(key(r["src"]), r["start"], r["end"]) for r in tl.sync_reads]

    def in_gap(t: float) -> bool:
        if not ws:
            return False
        return (t <= ws[0]["start"] + _EPS or t >= ws[-1]["end"] - _EPS
                or any(a - _EPS <= t <= b + _EPS for a, b in gaps))

    # 1. flash margin and slivers
    for i, s in enumerate(video):
        if srcs[i] != main:
            continue
        inner = [c for c in changes if first[i] < c <= last[i]]
        if i + 1 == len(video) or not carries_on(i + 1):
            for c in changes:
                if c > first[i] and c - 1 <= last[i] <= c + MARGIN_FRAMES:
                    latest = math.floor((c - 1) / fps * 100 + _EPS) / 100
                    shown = (f"it shows {last[i] - c + 1} frame(s) of the next shot (a flash)" if last[i] >= c
                             else "it ends 1 frame before the change, inside the 2-frame margin")
                    if s["from"] > latest:
                        todo = (f"Drop segment {i + 1}, or start it in the next shot (at "
                                f"{math.ceil(c / fps * 100 - _EPS) / 100:.2f} s or later) so it ends 2 frames before "
                                "a later change: it starts after the latest end this shot allows.")
                    else:
                        todo = f"end it at {latest:.2f} s or earlier (last frame {c - 2})."
                    out.refuse(f"Segment {i + 1} ends at {s['to']:g} s, on source frame {last[i]}, and the shot "
                               f"changes at frame {c} ({c / fps:.3f} s at {fps:.3f} fps): {shown}. A segment ends "
                               f"at least 2 frames before a shot change{': ' if todo[0].islower() else '. '}{todo}")
            piece = last[i] - inner[-1] + 1 if inner else 0
            if MARGIN_FRAMES + 1 < piece < MIN_PIECE_FRAMES and on_screen(i, True) < MIN_PIECE_FRAMES:
                c = inner[-1]
                latest = math.floor((c - 1) / fps * 100 + _EPS) / 100
                longer = math.ceil((c + MIN_PIECE_FRAMES) / fps * 100 - _EPS) / 100
                shorter = f"end it at {latest:.2f} s or earlier (last frame {c - 2}), or " if s["from"] <= latest else ""
                out.refuse(f"Segment {i + 1} ends at {s['to']:g} s, on source frame {last[i]}: it shows only {piece} "
                           f"frames of the shot that starts at frame {c} ({c / fps:.3f} s at {fps:.3f} fps), a "
                           f"sliver that reads as a flash. A piece of another shot at a segment's edge is at least "
                           f"{MIN_PIECE_FRAMES} frames: {shorter}end it at {longer:.2f} s or later.")
        if i == 0 or not carries_on(i):
            for c in changes:
                if c - (MARGIN_FRAMES + 1) <= first[i] < c:
                    gap = c - first[i]
                    earliest = math.ceil(c / fps * 100 - _EPS) / 100
                    same = math.floor((c - MIN_PIECE_FRAMES) / fps * 100 + _EPS) / 100
                    out.refuse(f"Segment {i + 1} starts at {s['from']:g} s, on source frame {first[i]}, {gap} "
                               f"frame(s) before the shot change at frame {c} ({c / fps:.3f} s at {fps:.3f} fps): "
                               f"it would flash {gap} frame(s) of the previous shot. A segment starts at the "
                               f"change or at least {MIN_PIECE_FRAMES} frames before it: start it at {earliest:.2f} s "
                               f"(frame {c}) or later, or at {same:.2f} s (frame {c - MIN_PIECE_FRAMES}) or earlier "
                               "in the same shot.")
            gap = inner[0] - first[i] if inner else 0
            if MARGIN_FRAMES + 1 < gap < MIN_PIECE_FRAMES and on_screen(i, False) < MIN_PIECE_FRAMES:
                c = inner[0]
                earliest = math.ceil(c / fps * 100 - _EPS) / 100
                same = math.floor((c - MIN_PIECE_FRAMES) / fps * 100 + _EPS) / 100
                out.refuse(f"Segment {i + 1} starts at {s['from']:g} s, on source frame {first[i]}: it shows only {gap} "
                           f"frames of the shot before the change at frame {c} ({c / fps:.3f} s at {fps:.3f} fps), "
                           f"a sliver that reads as a flash. A piece of another shot at a segment's edge is at least "
                           f"{MIN_PIECE_FRAMES} frames: start it at {earliest:.2f} s (frame {c}) or later, or at "
                           f"{same:.2f} s (frame {c - MIN_PIECE_FRAMES}) or earlier.")

    # 2. no joint inside a continuous shot
    for k in range(1, len(video)):
        if srcs[k] != srcs[k - 1] or carries_on(k):
            continue
        if srcs[k] == main:
            if shot(last[k - 1]) != shot(first[k]):
                continue
            where = shot_span(shot(first[k]))
        else:
            where = f"the clip {name_of(srcs[k])} (another file, counted as one shot)"
        t = joints[k - 1]
        if video[k].get("seam") == "dissolve":
            out.refuse(f"Joint {k} at {t:.2f} s dissolves inside one continuous shot: segments {k} and {k + 1} "
                       f"both show {where}. A dissolve or FILM inside a shot looked poor in every test "
                       "(Ad 3 R6): regenerate the shot (L4) at the new length instead.")
            continue
        missing = []
        if has_speech and srcs[k] == main:
            if not sync:
                missing.append('"audio_mode" is not "sync"')
            if edit.get("jump") not in JUMPS:
                missing.append("no jump is declared")
            if not ws:
                missing.append("there is no transcript to find the speech gaps")
            else:
                for label, tt in (("out of", cuts[k - 1][2]), ("into", cuts[k][1])):
                    if not in_gap(tt):
                        missing.append(f"the audio cut {label} the joint at {tt:.2f} s is not in a speech gap")
            if not missing:
                continue
        text = (f"Joint {k} at {t:.2f} s cuts inside one continuous shot: segments {k} and {k + 1} both show "
                f"{where}, so the cut shows as a jump. Never cut inside a continuous shot: move the joint to a "
                "shot change, or regenerate the shot (L4).")
        if missing:
            text += (' In a talking-head shot a jump cut is allowed only with "audio_mode": "sync", a declared '
                     '"jump" (hard, punch_in or broll) and both audio cut points in a speech gap; here '
                     + "; ".join(missing) + ".")
        out.refuse(text)

    pieces: list[tuple[int | None, int]] = []  # (shot of the teardown's file or None, segment) in output order
    for i in range(len(video)):
        if srcs[i] != main:
            pieces.append((None, i))
            continue
        inner = [c for c in changes if first[i] < c <= last[i]]
        bounds = [first[i], *inner, last[i] + 1]
        parts = [(shot(a), b - a) for a, b in zip(bounds, bounds[1:])]
        if len(parts) > 1:  # a flash or sliver another rule reports is not a piece of that shot; one
            # the neighbour rule lets through (the same shot goes on across the joint) still is
            head, tail = reported(i, False), reported(i, True)
            if head:
                parts = parts[1:]
            if len(parts) > 1 and tail:
                parts = parts[:-1]
        pieces += [(sh, i) for sh, _ in parts]
    for sh in sorted({p for p, _ in pieces if p is not None}):
        at = [j for j, (p, _) in enumerate(pieces) if p == sh]
        if any(b - a != 1 for a, b in zip(at, at[1:])):
            segs = sorted({pieces[j][1] + 1 for j in at})
            out.refuse(f"Segments {', '.join(map(str, segs))} play {shot_span(sh)} in pieces apart from each "
                       "other: reordering scenes inside one continuous shot cuts inside it. Choose another "
                       "variant, or regenerate the shot (L4).")

    # 3. speech is cut in sync mode
    if has_speech:
        if not sync:
            out.refuse('The ad has speech (talking head or voiceover), so "audio_mode" must be "sync": picture and '
                       'sound are cut together (a crossfade overlap shifts the sound ahead of the lips). Set '
                       '"audio_mode": "sync" and "music_source": "sync".')
        elif not ws:
            out.refuse("The ad has speech, but no transcript was given, so the audio cut points cannot be checked "
                       "against the words. Give the transcript (--transcript, from tm tool transcribe).")
        else:
            for k, s in enumerate(video):
                if s.get("speed", 1.0) != 1.0:
                    out.refuse(f'Segment {k + 1} changes speed, which sync mode cannot do (the lips would drift). '
                               "Keep speech segments at speed 1.")
                a_src, start, end = cuts[k]
                if a_src != main:
                    continue
                for label, tt in (("starts", start), ("ends", end)):
                    for w in ws:
                        if w["start"] + _EPS < tt < w["end"] - _EPS:
                            out.refuse(f'Segment {k + 1}\'s audio {label} at {tt:.2f} s, inside the word "{w["word"]}" '
                                       f"({w['start']:.2f}-{w['end']:.2f} s). Move the cut into a speech gap, or let "
                                       "the audio run on into the neighbour's silence (audio_tail L-cut, audio_head "
                                       "J-cut).")
                            break

    # 4. final music has no beat-cut joints
    if edit.get("draft") is not True:
        music = Counter(key(a["src"]) for a in audio)
        for src, count in music.items():
            if count > 1:
                out.refuse(f"The music cuts {name_of(src)} into {count} pieces: beat-cut joints are "
                           "audible; use the original file or a continuation (method E). A beat-cut edit is "
                           'only for a draft ("draft": true), never the final music.')

    # 5. level
    if level >= 0:
        kind = BUDGET_FOR_LEVEL.get(level)
        if kind and kind not in approved:
            out.wait(f"Level {level} spends on {_SERVICE[kind]}, and budget.{kind} is not approved in this run, so "
                     f"nothing is rendered yet. Estimate the cost (tm budget estimate {kind} ...), ask the user and "
                     f"approve it (tm budget approve {kind} ...), or choose a level 0-2 variant.")
        configured = config.value(cfg, "recut.max_level")
        cap = configured if configured is not None else (HANDS_OFF_MAX_LEVEL if mode == "auto" else None)
        if cap is not None and level > cap:
            why = "" if configured is not None else " (Hands-off stops at level 2 unless the config sets it)"
            text = (f"Level {level} is above recut.max_level {cap}{why}. ")
            if mode == "auto":
                out.wait(text + "The variant waits for the user: they raise recut.max_level, or it is dropped.")
            else:
                out.refuse(text + f"Choose a variant at level 0 to {cap}, or ask the user to raise "
                                  "recut.max_level.")
    return Verdict(out.status(), out.texts, joints, length, level)


def reuse_take(takes: list[dict], target_s: float, tol: float = TAKE_TOLERANCE_S) -> dict | None:
    """The existing music take closest to `target_s` within +/-`tol` seconds, or None (RC17)."""
    best, gap = None, math.inf
    for take in takes:
        length = take.get("length_s")
        if not _number(length):
            continue
        d = abs(length - target_s)
        if d <= tol + 1e-9 and d < gap:
            best, gap = take, d
    return best


# --- the run --------------------------------------------------------------------------------

def run_context(run: RunFolder) -> tuple[str, set[str]]:
    """(mode, approved budget kinds) for `check` (ruling R3, as amended): "auto" when the run's level
    is Hands-off, or the level is unset and the config's mode is auto (config.validate's test), else
    "hitl"; the budget kinds with an approved amount in the run.

    Budgets are one running total per kind, shared with the other outputs (G6's AI video, VB's
    voiceover line), so a declined re-cut budget must not borrow theirs: while the latest decision
    of the re-cut budget check-in (RB) is `reject`, no kind counts as approved for a re-cut
    (controller ruling, PR C review), and an L3-L5 edit list waits."""
    s = state.load(run)
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = None
    auto = s.level == "hands_off" or (s.level is None and config.value(cfg, "mode") == "auto")
    approved = {k for k, v in (s.budgets or {}).items() if _number(v) and v > 0}
    recut_budget = [d for d in s.decisions or [] if isinstance(d, dict) and d.get("checkin") == "RB"]
    if recut_budget and recut_budget[-1].get("choice") == "reject":
        approved = set()
    return ("auto" if auto else "hitl"), approved


def _rel(run: RunFolder, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def record(run: RunFolder, edit_path: Path, edit: dict, v: Verdict) -> dict:
    """Append the checked edit list to run.json `recut.checked`."""
    entry = {"edit": _rel(run, edit_path), "variant": edit.get("variant"), "change_id": edit.get("change_id"),
             "level": v.level, "joints_s": v.joints_s, "length_s": v.length_s,
             "audio_mode": edit.get("audio_mode"), "music_source": edit.get("music_source"), "status": v.status}
    s = state.load(run)
    rec = dict(s.recut or {})
    rec["checked"] = [*(rec.get("checked") or []), entry]
    s.recut = rec
    state.save(run, s)
    return entry


def pending_takes(run: RunFolder) -> list[dict]:
    """Paid music takes whose file was not saved (records still "music_pending"): {record, file, credits_used}."""
    folder = run.path / "03_wip" / "audio"
    found = []
    for rec_path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("kind") == "music_pending":
            found.append({"record": _rel(run, rec_path), "file": data.get("file"),
                          "credits_used": data.get("credits_used")})
    return found


def takes(run: RunFolder) -> tuple[list[dict], list[str]]:
    """Music takes recorded in 03_wip/audio (ruling R2), and the records whose take is unusable."""
    folder = run.path / "03_wip" / "audio"
    found, skipped = [], []
    for rec_path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("kind") != "music_take":
            continue
        name, length = data.get("file"), data.get("length_s")
        take = rec_path.parent / name if isinstance(name, str) and name.strip() else None
        if take is None or not take.is_file() or not (_number(length) and length > 0):
            skipped.append(_rel(run, rec_path))
            continue
        found.append({"file": _rel(run, take), "record": _rel(run, rec_path), "length_s": float(length),
                      "model": data.get("model"), "credits_used": data.get("credits_used")})
    return found, skipped


# --- command line ---------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    pt = sub.add_parser("points", help="shot changes, card switches and speech gaps an edit list may cut at")
    ck = sub.add_parser("check", help="whether an edit list is legal, before anything is rendered")
    ck.add_argument("edit", help="the edit list JSON (03_wip/recut/<variant>_vNN.json)")
    for sp in (pt, ck):
        sp.add_argument("--teardown", required=True, help="the teardown JSON from tm tool teardown")
        sp.add_argument("--transcript", default=None, help="the transcript JSON from tm tool transcribe")
    mu = sub.add_parser("music", help="the recorded music takes, and whether one fits the picture")
    mu.add_argument("--target-s", required=True, type=float, help="the picture length in seconds")
    for sp in (pt, ck, mu):
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--json", action="store_true")


def _points(args: argparse.Namespace, run: RunFolder) -> int:
    p = points(read_json(run, args.teardown, "teardown"), read_json(run, args.transcript, "transcript"))
    shots = ", ".join(f"{x['s']:g} s (frame {x['frame']})" for x in p["shot_changes"]) or "none"
    cli.emit(args, {"status": "done", **p},
             f"Source at {p['fps']:.3f} fps. Shot changes: {shots}. {len(p['card_switches'])} card switch(es), "
             f"{len(p['speech_gaps'])} speech gap(s) of {SPEECH_GAP_MIN_S} s or more.")
    return 0


def _check(args: argparse.Namespace, run: RunFolder) -> int:
    if state.load(run).status == "done":
        raise ValueError("This run is done; its edit lists are no longer checked.")
    edit_path = resolve(run, args.edit)
    edit = read_json(run, args.edit, "edit list")
    teardown = read_json(run, args.teardown, "teardown")
    transcript = read_json(run, args.transcript, "transcript")
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = None
    mode, approved = run_context(run)
    v = check(edit, teardown, transcript, cfg, mode=mode, approved=approved, base=run.path,
              edit_dir=edit_path.parent, material=state.load(run).material)
    entry = record(run, edit_path, edit, v)
    payload = {**v.to_json(), "edit": entry["edit"], "mode": mode, "approved": sorted(approved)}
    name = entry["edit"]
    if v.status == "ok":
        joints = ", ".join(f"{t:g}" for t in v.joints_s) or "none"
        cli.emit(args, payload, f"{name} is legal: {v.length_s:g} s, joints at {joints} s, level {v.level}. "
                                "It can be rendered.")
        return 0
    listed = "\n".join(f"- {p}" for p in v.problems)
    todo = ("Fix the edit list in a new version and check it again." if v.status == "refused" else
            "Once the budget is approved or the level allowed, check it again.")
    word = "was refused" if v.status == "refused" else "is waiting"
    cli.emit(args, payload, f"{name} {word}, so nothing was rendered:\n{listed}\n{todo} "
                            "The run continues from the same place.")
    return 2


def _music(args: argparse.Namespace, run: RunFolder) -> int:
    target = args.target_s
    if not (_number(target) and target > 0):
        raise ValueError("The picture length (--target-s) must be more than 0 seconds.")
    found, skipped = takes(run)
    pending = pending_takes(run)
    take = reuse_take(found, target)
    decision = "reuse" if take else "resume" if pending else "generate"
    payload = {"status": "done", "target_s": target, "tolerance_s": TAKE_TOLERANCE_S, "takes": found,
               "skipped": skipped, "pending": pending, "decision": decision, "take": take,
               "credits": CREDITS_PER_TAKE if decision == "generate" else 0}
    if take:
        text = (f"Reuse {take['file']} ({take['length_s']:g} s, within {TAKE_TOLERANCE_S} s of {target:g} s): "
                "no new take, 0 credits.")
    elif pending:
        records = ", ".join(p["record"] for p in pending)
        text = (f"No saved music take fits {target:g} s, but {len(pending)} paid take(s) wait to be saved "
                f"({records}). Resume it before paying for another: tm tool elevenlabs music-compose "
                f"--resume {pending[0]['record']} in this run (free, 0 credits), then check again.")
    else:
        have = ", ".join(f"{t['file']} ({t['length_s']:g} s)" for t in found) or "none recorded"
        text = (f"No music take fits {target:g} s (+/-{TAKE_TOLERANCE_S} s; takes: {have}). Generate a new one by "
                f"method E: about {CREDITS_PER_TAKE} ElevenLabs credits per take, so estimate and approve "
                "budget.voice_credits first.")
    cli.emit(args, payload, text)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        return {"points": _points, "check": _check, "music": _music}[args.action](args, run)
    except (OSError, ValueError, ReadOnlyError, ToolError) as exc:
        return cli.fail(args, str(exc))


cli.register("recut", _setup, _run)
