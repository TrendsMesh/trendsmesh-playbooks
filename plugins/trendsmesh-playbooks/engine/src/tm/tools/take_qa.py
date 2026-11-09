"""take_qa: QA of a generated take (organic video, OV10): cuts, transcript, pace, loudness, contact sheet.

    tm tool take_qa --run RUN TAKE --lang L [--script F] [--brackets 3.1,7.25,11.25] [--model M] [--out PATH] [--json]

TAKE is a video inside the run (a `replicate_run` output, `03_wip/<item>_vNN_<i>.mp4`). F holds the lines the take
speaks: a text file, or the pack (`pack_vNN.json`): its lines said (`speaker` not `none`), when its route speaks in
the model (`organic_qa.SPEECH_IN_TAKE`) and it has one video item; otherwise give a text file of this take's
lines. Leave --script out for a take that carries no spoken lines (a narrated or silent route: the voice comes
in the edit): it is not transcribed, and its transcript keys are null. L is the audio language. --brackets are
the times the script cuts at, in seconds.

Writes `<take dir>/qa/<stem>_qa_vNN.json` (the next version, never an overwrite):

    {"take", "transcript", "match", "words", "speech_seconds", "wps", "tail_silence", "cuts", "cut_offsets",
     "lufs", "peak", "contact_sheet"}

- transcript (with --script): `tm.tools.transcribe` (faster-whisper, word timestamps, the default model unless
  --model), saved beside it as `<stem>_transcript_vNN.json`; `match` is `organic_qa.match` of the script and the
  heard words; `words`, `speech_seconds` (first word's start to last word's end), `wps` (None without words) and
  `tail_silence` (the take's end after the last word);
- cuts: PySceneDetect's ContentDetector (`teardown.scenes`), in seconds; `cut_offsets` one per bracket:
  {bracket, cut (the nearest, or None), offset (cut − bracket)};
- loudness: ffmpeg `ebur128` integrated loudness (LUFS) and true peak (dBFS), None without a sound track (an
  ffmpeg failure is an error, never "no sound");
- contact sheet: 6 frames spread over the take, 3×2, `<stem>_contact_vNN.png`.

The answer adds the takes rubric (`organic_qa.rubric_takes`, the run's `qa.*` thresholds; the transcript rule
only with --script): fails, findings and the speed-up for a slow take. Free, local. Heavy imports happen inside
the functions that need them.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tm.tools import _common as c
from tm.tools import transcribe

SHEET_FRAMES, SHEET_COLUMNS, SHEET_WIDTH = 6, 3, 360


def script_text(path: Path) -> str:
    """The words the take speaks: a text file as it is, or the lines a pack's one video item says."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise c.ToolError(f"The script {c.name_of(path)} does not exist.") from None
    if path.suffix.lower() == ".json":
        text = _pack_lines(path, text)
    if not text.strip():
        raise c.ToolError(f"The script {c.name_of(path)} holds no words.")
    return text


def _pack_lines(path: Path, text: str) -> str:
    from tm import organic_qa, organic_specs

    name = c.name_of(path)
    try:
        pack = json.loads(text)
        lines = pack["script"]["lines"]
        route = pack["speech"]["route"]
        takes = [i for st in pack["stages"] for i in st["items"] if i.get("model") and organic_specs.is_video(pack, i)]
        said = [str(line["text"]) for line in lines if line["speaker"] != "none"]
    except (ValueError, KeyError, TypeError):
        raise c.ToolError(f"The script {name} is JSON but not a pack (script.lines, speech.route, stages): give the "
                          "pack or a text file with the lines the take speaks.") from None
    if route not in organic_qa.SPEECH_IN_TAKE:
        raise c.ToolError(f"The pack's speech route is {route}: its takes carry no spoken lines (the voice comes in "
                          "the edit). Leave out --script; the take is judged on its cuts and loudness.")
    if len(takes) != 1:
        raise c.ToolError(f"The pack {name} has {len(takes)} video items, and its lines do not say which take speaks "
                          "which: give a text file with this take's own lines.")
    return " ".join(said)


def brackets(text: str | None) -> list[float]:
    if not text:
        return []
    try:
        return [float(v) for v in text.split(",")]
    except ValueError:
        raise c.ToolError(f"--brackets {text!r} must be the cut times in seconds, e.g. 3.1,7.25,11.25.") from None


def cuts(take: Path) -> list[float]:
    """The cut times in seconds (the start of every shot after the first)."""
    from tm.tools import teardown

    return [start for start, _ in teardown.scenes(take)[1:]]


def offsets(found: list[float], wanted: list[float]) -> list[dict]:
    out = []
    for b in wanted:
        cut = min(found, key=lambda t: abs(t - b)) if found else None
        out.append({"bracket": b, "cut": cut, "offset": None if cut is None else round(cut - b, 3)})
    return out


def parse_ebur128(text: str) -> tuple[float | None, float | None]:
    """(integrated LUFS, true peak dBFS) from ffmpeg's ebur128 log: the last Summary, whatever prefixes its lines."""
    at = text.rfind("Summary:")
    if at < 0:
        return None, None
    summary = text[at:]
    lufs = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?|-inf)\s*LUFS", summary)
    peak = re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?|-inf)\s*dBFS", summary)

    def number(found: list[str]) -> float | None:
        return float(found[-1]) if found and found[-1] != "-inf" else None

    return number(lufs), number(peak)


def loudness(take: Path) -> tuple[float | None, float | None]:
    """(integrated LUFS, true peak dBFS) of a file; (None, None) without a sound track. ffmpeg failing is an error
    (CalledProcessError), never "no sound"."""
    if not c.probe(take).get("has_audio"):
        return None, None
    argv = [c.ffmpeg_bin(), "-nostdin", "-hide_banner", "-nostats", "-v", "info", "-i", c.media(take), "-vn", "-af",
            "ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
    proc = subprocess.run(argv, capture_output=True)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, argv, stderr=proc.stderr)
    return parse_ebur128(proc.stderr.decode("utf-8", "replace"))


def contact_sheet(take: Path, duration: float, out: Path) -> None:
    rate = SHEET_FRAMES / duration if duration > 0 else 1
    rows = SHEET_FRAMES // SHEET_COLUMNS
    c.run_ffmpeg(["-i", c.media(take), "-vf",
                  f"fps={rate:.6f},scale={SHEET_WIDTH}:-2,tile={SHEET_COLUMNS}x{rows}",
                  "-frames:v", "1", str(out)])


def speech(transcript: dict | None, duration: float) -> dict:
    if transcript is None:   # no spoken lines: not transcribed
        return {"words": None, "speech_seconds": None, "wps": None, "tail_silence": None}
    words = [w for s in transcript.get("segments") or [] for w in s.get("words") or []]
    if not words:
        return {"words": 0, "speech_seconds": 0.0, "wps": None, "tail_silence": round(duration, 2)}
    span = words[-1]["end"] - words[0]["start"]
    return {"words": len(words), "speech_seconds": round(span, 2),
            "wps": round(len(words) / span, 2) if span > 0 else None,
            "tail_silence": round(max(0.0, duration - words[-1]["end"]), 2)}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    from tm import organic_qa
    from tm.r2 import run_config

    p = c.parser("take_qa", "QA of a generated take: cuts, transcript, pace, loudness, contact sheet.")
    p.add_argument("take", help="the take, a video inside the run")
    p.add_argument("--script", default=None, help="the lines the take speaks: a text file, or the pack (leave out "
                                                  "for a take with no spoken lines)")
    p.add_argument("--lang", required=True, help="the audio language, e.g. pl")
    p.add_argument("--brackets", default=None, help="the times the script cuts at, in seconds: 3.1,7.25,11.25")
    p.add_argument("--model", default=transcribe.DEFAULT_MODEL, help="the Whisper model")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    take = c.resolve(run, a.take)
    if not take.is_file():
        raise c.ToolError(f"The take {c.name_of(a.take)} does not exist.")
    try:
        stage = organic_qa.qa_stage(run, take)
    except ValueError:
        raise c.ToolError(f"The take {c.name_of(a.take)} is not inside the run folder {run.path}.") from None
    script = script_text(c.resolve(run, a.script)) if a.script else None
    wanted = brackets(a.brackets)
    info = c.probe(take)
    if not info.get("is_video"):
        raise c.ToolError(f"{c.name_of(take)} is not a video.")
    duration = float(info["duration"])
    out = c.output(run, a.out, stage, f"{take.stem}_qa", "json")
    said = transcript = None
    if script is not None:
        said = run.next_version(stage, f"{take.stem}_transcript", "json")
        transcript = transcribe.save(run, take, said, a.model, a.lang)
    found = cuts(take)
    lufs, peak = loudness(take)
    sheet = run.next_version(stage, f"{take.stem}_contact", "png")
    contact_sheet(take, duration, sheet)
    c.record(run, sheet, "contact sheet (6 frames)", c.parent_ref(run, take), cost="0 (local)")
    qa = {"take": c.rel(run, take), "transcript": c.rel(run, said) if said else None,
          "match": round(organic_qa.match(script, organic_qa.words_of(transcript)), 3) if script else None,
          **speech(transcript, duration), "cuts": [round(t, 3) for t in found],
          "cut_offsets": offsets(found, wanted), "lufs": lufs, "peak": peak, "contact_sheet": c.rel(run, sheet)}
    c.write_json(out, qa)
    c.record(run, out, "take QA", c.parent_ref(run, take), params={"lang": a.lang, "brackets": wanted},
             model=a.model, cost="0 (local)")
    rubric = organic_qa.rubric_takes(qa, run_config(run), speech=script is not None)
    level = f"{lufs:.1f} LUFS" if lufs is not None else "no sound"
    pace = f"{qa['wps']:g} words/s" if qa["wps"] else "no speech"
    heard = f"the transcript matches {qa['match']:.0%} of the script" if script else "no spoken lines (not transcribed)"
    text = (f"QA of {qa['take']} in {c.rel(run, out)}: {heard}, {pace}, {len(found)} cut(s), {level}; contact sheet "
            f"{qa['contact_sheet']}.")
    if rubric["fails"]:
        text += " Fails the takes rubric: " + "; ".join(rubric["fails"]) + "."
    if rubric["findings"]:
        text += " Findings: " + "; ".join(rubric["findings"]) + "."
    outputs = [c.rel(run, out), *([qa["transcript"]] if said else []), qa["contact_sheet"]]
    return c.finish(a, {"tool": "take_qa", "outputs": outputs,
                        "qa": qa, "rubric": rubric}, text)


if __name__ == "__main__":
    raise SystemExit(main())
