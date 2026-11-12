"""recut_qa: automatic QA of a rendered re-cut (path C-R, step CR6). A port of handoff v03 tools/recut_qa.py.

    tm tool recut_qa --run RUN VIDEO [--sidecar S.recut.json] [--caption-band x0,y0,x1,y1]
                     [--expected TEXT] [--lang pl] [--original VIDEO] [--json]

Reads the sidecar `<video>.recut.json` that `tm tool recut` writes next to the render (or the file
named with --sidecar) for the picture joints, the audio joints, the expected length and the audio
mode. Without a sidecar there are no joints and the whole-track checks still run.

Writes `03_wip/qa/<name>_qa_vNN.json` = {"pass": bool, "flags": [{"check", "at_s", "detail"}],
"measures": {...}} and, per picture joint, a strip of the frames -3..+3 around it in
`03_wip/qa/<name>_strips_vNN/joint<n>.png`. Both are versioned and never overwritten. The tool is
free; a red flag sends the agent back to CR4 (the edit list).

Checks (the `check` name of each flag):
- audio_missing: the file has no audio track although the edit list has sound.
- length: the file's length against the sidecar's `length_s` (more than 2 frames apart).
- one_frame_flash: a frame unlike both neighbours at a picture joint (e.g. the next shot leaking in
  after a frame-rate conversion).
- music_joint: at an audio joint, a short-term level jump above `recut.qa.music_joint_db` or an
  inter-beat interval off the median by more than `recut.qa.beat_interval` (music re-cut).
- tempo_drift: the median inter-beat interval of the two halves differs by more than
  `recut.qa.tempo_drift`.
- fade_before_end: the last 3 s are more than `-recut.qa.tail_db` dB below the body.
- word_across_fade: a word spans an audio fade point (cut mid-word; L- and J-cuts accounted for;
  speech re-cut, `audio_mode` "sync").
- script: with --expected, more than 10 % of the expected words are not heard. Whisper mishears
  brand and rare words, so fewer missing words are only reported in `measures`.
- caption_flash: with --caption-band, a caption shown for less than `recut.qa.caption_flash_s`
  next to a picture joint (a remnant word of the cut-out speech).
- loudness: with --original, the integrated loudness (ebur128) is more than 1 LU from the original's.

Known limits (HANDOFF 9c): the music checks run on the whole soundtrack, so on a mix with a
voiceover the tempo and tail measurements are unreliable; beat-cut joints that pass the numbers can
still be audible, music is accepted by ear.

Thresholds are read from the config (`recut.qa.*`) and passed to the checks as arguments. Heavy
imports (numpy, librosa, faster-whisper) happen inside the functions that need them.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tm import config
from tm.tools import _common as c
from tm.tools import transcribe

QA_MODEL = "small"  # the QA only needs word times; a small model keeps it quick
LENGTH_TOLERANCE_FRAMES = 2
LOUDNESS_TOLERANCE_LU = 1.0
THRESHOLD_NAMES = ("music_joint_db", "beat_interval", "tempo_drift", "tail_db", "caption_flash_s")


def flag(check: str, at_s: float | None, detail: str) -> dict:
    return {"check": check, "at_s": None if at_s is None else round(float(at_s), 3), "detail": detail}


def thresholds(cfg: dict | None) -> dict:
    return {name: config.value(cfg, f"recut.qa.{name}") for name in THRESHOLD_NAMES}


# ---- inputs --------------------------------------------------------------------------------

def _words(video: Path | str, lang: str) -> list[dict]:
    """The spoken words with their times: [{"w", "s", "e"}]. Tests replace this with a fixture."""
    result = transcribe.transcribe(video, QA_MODEL, lang)
    return [{"w": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2)}
            for s in result["segments"] for w in s["words"]]


def _sidecar(video: Path, given: str | None, run) -> dict:
    if given is None:
        path = Path(str(video) + ".recut.json")
        if not path.is_file():
            return {}
    else:
        path = c.resolve(run, given)
    data = c.read_json(run, path, "sidecar", " Nothing was checked.")
    for key in ("joints_s", "music_joints_s"):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                  for x in value):
            raise c.ToolError(f"The sidecar {path.name} has a {key} that is not a list of times in seconds.")
    return data


# ---- music ---------------------------------------------------------------------------------

def beat_times(y, sr: int):
    """(tempo in BPM, beat times in s) from librosa's beat tracker. It follows one tempo at a time
    and pulls a mid-track tempo change towards a single grid, so the drift it can show is small."""
    import librosa

    return librosa.beat.beat_track(y=y, sr=sr, units="time")


def music_checks(y, sr: int, joints: list[float], thr: dict) -> tuple[list[dict], dict]:
    """Level and beat measurements at each audio joint, tempo drift between the halves, and the
    music fading before the end. `y` is the soundtrack as mono float32 at `sr`."""
    import librosa
    import numpy as np

    flags: list[dict] = []
    measures: dict = {}
    dur = len(y) / sr
    if dur <= 0:
        return flags, measures
    hop = 256
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    tr = librosa.times_like(rms, sr=sr, hop_length=hop)
    db = 20 * np.log10(rms + 1e-9)
    tempo, beats = beat_times(y, sr)
    ibi = np.diff(beats)
    med = float(np.median(ibi)) if len(ibi) else 0.0
    measures["tempo_bpm"] = round(float(np.atleast_1d(tempo)[0]), 1)
    measures["music_joints"] = []
    for j in joints:
        near = (tr > j - 0.05) & (tr < j + 0.05)
        ctx = (tr > j - 0.5) & (tr < j + 0.5) & ~near
        jump = float(np.max(np.abs(db[near] - np.median(db[ctx])))) if near.any() and ctx.any() else 0.0
        dev = 0.0
        if len(beats) and med > 0:
            k = int(np.argmin(np.abs(beats - j)))
            w = ibi[max(0, k - 2): k + 2]
            dev = float(np.max(np.abs(w - med) / med)) if len(w) else 0.0
        bad = bool(jump > thr["music_joint_db"] or dev > thr["beat_interval"])
        measures["music_joints"].append({"t": round(float(j), 3), "level_jump_db": round(jump, 1),
                                         "beat_interval_dev": round(dev, 3), "flag": bad})
        if bad:
            flags.append(flag("music_joint", j, f"level jump {jump:.1f} dB, beat interval deviation {dev:.0%}"))
    half = beats[1:] < dur / 2
    if med > 0 and half.sum() > 3 and (~half).sum() > 3:
        drift = abs(float(np.median(ibi[half])) - float(np.median(ibi[~half]))) / med
        measures["tempo_drift"] = round(drift, 3)
        if drift > thr["tempo_drift"]:
            flags.append(flag("tempo_drift", None, f"tempo drift {drift:.1%} between the halves"))
    if dur > 6:
        body = np.median(db[(tr > 1) & (tr < dur - 3)])
        tail = np.median(db[(tr >= dur - 3) & (tr < dur - 0.35)])
        measures["tail_vs_body_db"] = round(float(tail - body), 1)
        if tail - body < thr["tail_db"]:
            flags.append(flag("fade_before_end", None,
                              f"music fades before the end (last 3 s {tail - body:.1f} dB vs body)"))
    return flags, measures


# ---- speech --------------------------------------------------------------------------------

def speech_checks(words: list[dict], joints: list[float], video_spec: list[dict], xfade_ms: float) -> tuple[list[dict], list[dict]]:
    """Flag each audio joint that cuts through a word. With split edits the audio does not switch at
    the picture joint: the outgoing segment's audio fades at joint + audio_tail (L-cut), the incoming
    one starts at joint - audio_head (J-cut)."""
    flags, items = [], []
    xh = xfade_ms / 2000
    for k, j in enumerate(joints, start=1):
        out_seg = video_spec[k - 1] if k - 1 < len(video_spec) else {}
        in_seg = video_spec[k] if k < len(video_spec) else {}
        t_out = j + max(0.0, out_seg.get("audio_tail", 0.0) - xh)
        t_in = j - max(0.0, in_seg.get("audio_head", 0.0) - xh)

        def spans(w, tt):
            return w["s"] + 0.03 < tt < w["e"] - 0.03

        # an outgoing word may run on under an L-cut until t_out, an incoming one may start under a
        # J-cut from t_in; a word is cut only where its own segment's audio fades
        inside = [w for w in words
                  if (spans(w, t_out) and not (t_in < j and w["s"] >= t_in - 0.03))
                  or (spans(w, t_in) and not (t_out > j and w["e"] <= t_out + 0.03))]
        prev = max([w["e"] for w in words if w["e"] <= t_out + 0.03], default=None)
        nxt = min([w["s"] for w in words if w["s"] >= t_in - 0.03], default=None)
        items.append({"t": round(j, 3), "audio_fade_out_t": round(t_out, 3), "audio_fade_in_t": round(t_in, 3),
                      "gap_before_s": None if prev is None else round(t_out - prev, 2),
                      "gap_after_s": None if nxt is None else round(nxt - t_in, 2),
                      "word_across": [w["w"] for w in inside]})
        if inside:
            flags.append(flag("word_across_fade", j, f"audio joint {j:.2f} s cuts through the word '{inside[0]['w']}'"))
    return flags, items


def script_check(expected: str, words: list[dict]) -> tuple[list[dict], dict]:
    """Expected against heard words. Whisper mishears brand and rare words ("e-booka" as "i buka"),
    so a flag needs more than 10 % of the expected words missing (HANDOFF 9c)."""
    def norm(text):
        return re.findall(r"\w+", text.lower())

    exp, got = norm(expected), norm(" ".join(w["w"] for w in words))
    missing = [w for w in exp if w not in got]
    extra = [w for w in got if w not in exp]
    flags = []
    if exp and len(missing) > 0.1 * len(exp):
        flags.append(flag("script", None, f"{len(missing)} of {len(exp)} expected words not heard"))
    return flags, {"missing_words": missing, "extra_words": extra}


# ---- picture -------------------------------------------------------------------------------

def frame_flashes(video: Path, joints: list[float], fps: float) -> tuple[list[dict], list[dict]]:
    """A frame that differs strongly from both neighbours next to a picture joint (e.g. the last frame
    of a segment already belongs to the next shot after frame-rate conversion)."""
    import numpy as np

    if not joints:
        return [], []
    frames = np.stack([f.astype(np.float32) for f in c.decode(video, 90, 160, "gray")])
    flags, found = [], []
    for j in joints:
        f0 = round(j * fps)
        start = max(0, f0 - 8)
        window = frames[start:start + 16]
        d = np.array([np.abs(window[i + 1] - window[i]).mean() for i in range(len(window) - 1)])
        if len(d) < 4:
            continue
        base = max(float(np.median(d)), 1.0)
        big = d > max(6 * base, 15)
        pairs = [i for i in range(len(d) - 1) if big[i] and big[i + 1]]
        if pairs:
            t_flash = round((start + pairs[0] + 1) / fps, 3)
            found.append({"joint": j, "flash_frame_t": t_flash})
            flags.append(flag("one_frame_flash", t_flash, f"one-frame flash at {t_flash:.3f} s next to the joint at {j:.2f} s"))
    return flags, found


def caption_checks(video: Path, band: tuple[int, int, int, int], joints: list[float], fps: float, width: int,
                   height: int, flash_s: float) -> tuple[list[dict], dict]:
    """Burned-in caption switches are found from the share of white pixels in the band; a caption
    shown for less than `flash_s` next to a joint is a remnant word of the cut-out speech."""
    import numpy as np

    x0, y0, x1, y1 = band
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise c.ToolError(f"--caption-band {x0},{y0},{x1},{y1} does not fit the {width}x{height} picture. "
                          "Give x0,y0,x1,y1 in output pixels.")
    share = np.array([float((f[y0:y1, x0:x1] > 235).mean()) for f in c.decode(video, width, height, "gray")])
    if len(share) < 2:
        return [], {"caption_switches": 0, "caption_joints": []}
    # a switch = the white share changes by more than 25 % of the larger value (and by > 0.004)
    d = np.abs(np.diff(share))
    big = np.maximum(share[1:], share[:-1])
    sw = np.where((d > 0.004) & (d > 0.25 * big))[0] + 1
    sw_t = sw / fps
    bounds = np.concatenate([[0], sw_t, [len(share) / fps]])
    shown = [(float(bounds[i]), float(bounds[i + 1])) for i in range(len(bounds) - 1)]
    # a real caption has at least ~30 % of the typical caption's white share; lower values are other
    # white details in the band (e.g. text on a product shown under the captions)
    on = share[share > 0.01]
    min_cap = 0.3 * float(np.median(on)) if len(on) else 0.01
    flags, per_joint = [], []
    for j in joints:
        near = sw_t[np.argmin(np.abs(sw_t - j))] if len(sw_t) else None
        short = [(round(s, 2), round(e, 2)) for s, e in shown
                 if e - s < flash_s and share[min(int(s * fps), len(share) - 1)] > min_cap
                 and (abs(s - j) < 0.25 or abs(e - j) < 0.25)]
        per_joint.append({"t": j, "nearest_switch_offset_s": None if near is None else round(float(near - j), 3),
                          "short_caption_flash": short})
        if short:
            flags.append(flag("caption_flash", short[0][0],
                              f"caption flash {short[0][0]}-{short[0][1]} s next to the joint at {j:.2f} s"))
    return flags, {"caption_switches": int(len(sw)), "caption_joints": per_joint}


def strips(video: Path, joints: list[float], fps: float, folder: Path) -> list[str]:
    """One PNG per picture joint: the frames -3..+3 around it side by side."""
    names = []
    for n, j in enumerate(joints, start=1):
        f0 = round(j * fps)
        png = folder / f"joint{n}.png"
        row = c.frame_row(range(max(0, f0 - 3), f0 + 4), width=160, height=-1, columns=7)
        c.run_ffmpeg(["-i", c.media(video), "-vf", row, "-frames:v", "1", str(png)])
        names.append(png.name)
    return names


# ---- loudness ------------------------------------------------------------------------------

def loudness(video: Path | str) -> float | None:
    """Integrated loudness in LUFS (ebur128), or None when there is no sound to measure."""
    proc = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "info", "-i", c.media(video), "-vn", "-af",
                           "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True)
    text = proc.stderr.decode("utf-8", "replace")
    found = re.findall(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", text[text.rfind("Summary"):], re.M) \
        if "Summary" in text else []
    return float(found[-1]) if found else None


# ---- the tool ------------------------------------------------------------------------------

def _band(text: str | None) -> tuple[int, int, int, int] | None:
    if text is None:
        return None
    try:
        x0, y0, x1, y1 = (int(v) for v in text.split(","))
    except ValueError:
        raise c.ToolError(f"--caption-band {text!r} must be x0,y0,x1,y1 in output pixels, e.g. 40,1500,680,1700.") from None
    return x0, y0, x1, y1


def _strips_folder(out: Path) -> Path:
    name = re.sub(r"_qa_v(\d+)$", r"_strips_v\1", out.stem)
    return out.parent / (name if name != out.stem else f"{out.stem}_strips")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("recut_qa", "QA of a rendered re-cut: length, joints, flash, music, words, captions, loudness.")
    p.add_argument("video", help="the rendered re-cut (04_final/<variant>_vNN.mp4)")
    p.add_argument("--sidecar", default=None, help="the .recut.json that tm tool recut wrote (default: next to the video)")
    p.add_argument("--caption-band", default=None, help="x0,y0,x1,y1 of the burned-in captions, in output pixels")
    p.add_argument("--expected", default=None, help="the expected spoken text (speech re-cut)")
    p.add_argument("--lang", default=None, help="language of the speech (default pl)")
    p.add_argument("--original", default=None, help="the original video, for the loudness comparison")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    video = c.resolve(run, a.video)
    if not video.is_file():
        raise c.ToolError(f"The video {a.video} does not exist. Nothing was checked.")
    original = None
    if a.original is not None:
        original = c.resolve(run, a.original)
        if not original.is_file():
            raise c.ToolError(f"The original {a.original} does not exist. Nothing was checked.")
    band = _band(a.caption_band)
    side = _sidecar(video, a.sidecar, run)
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = None
    thr = thresholds(cfg)
    out = c.output(run, a.out, "03_wip/qa", f"{c.stem_of(video)}_qa", "json")
    folder = _strips_folder(out)
    if folder.exists():
        raise c.ToolError(f"{c.rel(run, folder)} already exists, and files are never overwritten. Nothing "
                          "was checked. Leave out --out to get the next version.")

    info = c.probe(video)
    if not info.get("is_video"):
        raise c.ToolError(f"{video.name} has no moving picture, so there is no re-cut to check.")
    fps, width, height = info["fps"], info["width"], info["height"]
    spec = side.get("spec") if isinstance(side.get("spec"), dict) else {}
    speech = spec.get("audio_mode") == "sync" or (not side and a.expected is not None)
    pic_joints = [float(j) for j in side.get("joints_s", [])]
    audio_joints = [float(j) for j in side.get("music_joints_s", pic_joints)]
    flags: list[dict] = []
    measures: dict = {"file": video.name, "duration_s": round(info["duration"], 3), "fps": fps,
                      "has_audio": bool(info.get("has_audio")), "mode": "speech" if speech else "music",
                      "picture_joints": pic_joints, "audio_joints": audio_joints}

    # a re-cut that lost its sound: unless the edit list never had any (no audio list, no audio mode,
    # no extra audio, or no sidecar to say)
    wants_audio = bool(spec.get("audio") or spec.get("audio_mode") or spec.get("extra_audio"))
    if not info.get("has_audio") and wants_audio:
        flags.append(flag("audio_missing", None, "the rendered file has no audio track, but the edit list has sound"))

    length = side.get("length_s")
    if isinstance(length, (int, float)) and not isinstance(length, bool):
        measures["expected_length_s"] = round(float(length), 3)
        if abs(info["duration"] - length) > LENGTH_TOLERANCE_FRAMES / fps:
            flags.append(flag("length", None, f"the file is {info['duration']:.2f} s long, the edit list says "
                              f"{float(length):.2f} s"))

    c.say("Checking the picture joints")
    found, measures["frame_flash"] = frame_flashes(video, pic_joints, fps)
    flags += found

    if speech:
        c.say("Listening to the speech")
        words = _words(video, a.lang or "pl")
        measures["transcript"] = " ".join(w["w"] for w in words)
        found, measures["audio_joints_check"] = speech_checks(
            words, audio_joints, spec.get("video", []), spec.get("sync_xfade_ms", 40))
        flags += found
        if a.expected is not None:
            found, extra = script_check(a.expected, words)
            flags += found
            measures.update(extra)
    else:
        c.say("Checking the music")
        found, extra = music_checks(c.decode_mono(video, 22050), 22050, audio_joints, thr)
        flags += found
        measures.update(extra)
        if a.expected is not None or a.lang is not None:
            measures["script"] = "not checked: music mode"

    if band is not None:
        c.say("Checking the captions")
        found, extra = caption_checks(video, band, pic_joints, fps, width, height, thr["caption_flash_s"])
        flags += found
        measures.update(extra)

    lufs = loudness(video)
    measures["loudness_lufs"] = lufs
    if original is not None:
        ref = loudness(original)
        measures["original_loudness_lufs"] = ref
        if lufs is not None and ref is not None and abs(lufs - ref) > LOUDNESS_TOLERANCE_LU:
            flags.append(flag("loudness", None, f"{lufs:.1f} LUFS against {ref:.1f} LUFS in the original "
                              f"({lufs - ref:+.1f} LU)"))

    folder.mkdir(parents=True)
    run.assert_writable(folder)
    measures["picture_strips"] = [f"{folder.name}/{n}" for n in strips(video, pic_joints, fps, folder)]
    result = {"pass": not flags, "flags": flags, "measures": measures}
    c.write_json(out, result)

    parent = c.parent_ref(run, video)
    c.record(run, out, "tm tool recut_qa", parent, params={"flags": [f["check"] for f in flags]},
             request={"video": parent, "sidecar": a.sidecar, "expected": a.expected is not None,
                      "caption_band": a.caption_band}, response={"pass": result["pass"], "flags": flags})
    outputs = [c.rel(run, out)]
    for png in sorted(folder.glob("*.png")):
        c.record(run, png, "tm tool recut_qa (ffmpeg)", parent)
        outputs.append(c.rel(run, png))
    text = (f"QA saved to {c.rel(run, out)}: " + ("pass." if result["pass"] else
            f"{len(flags)} flag(s): " + "; ".join(f"{f['check']}" + ("" if f["at_s"] is None else f" at {f['at_s']:g} s")
                                                   for f in flags) + "."))
    return c.finish(a, {"tool": "recut_qa", "outputs": outputs, **result}, text)


if __name__ == "__main__":
    raise SystemExit(main())
