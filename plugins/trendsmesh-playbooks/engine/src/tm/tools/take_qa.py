"""take_qa: QA of a generated take (organic video, OV10): cuts, transcript, pace, loudness, contact sheet.

    tm tool take_qa --run RUN TAKE --lang L [--script F [--scribe S]] [--brackets 3.1,7.25,11.25] [--model M]
                    [--out PATH] [--json]

TAKE is a video inside the run (a `replicate_run` output, `03_wip/<item>_vNN_<i>.mp4`). F holds the lines the take
speaks: a text file, or the pack (`pack_vNN.json`): its lines said (`speaker` not `none`), when its route speaks in
the model (`organic_qa.SPEECH_IN_TAKE`) and it has one video item; otherwise give a text file of this take's
lines. Leave --script out for a take that carries no spoken lines (a narrated or silent route: the voice comes
in the edit): it is not transcribed, and its transcript keys are null. L is the audio language. --brackets are
the times the script cuts at, in seconds (the board's marks). S is this take's ElevenLabs Scribe transcript
(`tm tool elevenlabs scribe`, paid): its words are used instead of local Whisper's.

Writes `<take dir>/qa/<stem>_qa_vNN.json` (the next version, never an overwrite):

    {"take", "transcript", "match", "words", "speech_seconds", "wps", "tail_silence", "cuts", "cut_offsets",
     "lufs", "peak", "contact_sheet", "lines", "heard_by"}

- transcript (with --script): `tm.tools.transcribe` (faster-whisper, word timestamps, the default model unless
  --model), saved beside it as `<stem>_transcript_vNN.json`; with --scribe, the Scribe file itself. `match` is
  `organic_qa.match` of the script and the heard words; `words`, `speech_seconds` (first word's start to last
  word's end), `wps` (None without words) and `tail_silence` (the take's end after the last word);
- lines (issue #94): one {line, heard (the share of its words heard), start, end (its heard words' times, None
  when none), by ("whisper", "levelled", "scribe", or None while it is not heard whole), gain_db (a levelled
  listen only), quiet} per line of the script (`organic_qa.script_lines`); `heard_by` "whisper" or "scribe". Whisper's
  silence filter drops quiet lines, so a line Whisper does not hear whole is listened to again before anything is
  reported: that part of the take (between the neighbouring lines' heard words) raised to the take's level (its
  integrated loudness, at most +LEVEL_MAX_DB dB; `quiet` when that is WHISPER_LU or more, a whisper) and heard
  without the filter. Its words replace the first listen's there when they hear more of the line and the match
  does not drop. A line still not heard whole is not reported missing: the answer names the Scribe check and its
  credits (`tts_models.scribe_credits`), and the rubric's fail says so. Only Scribe's words make a line missing;
- cuts: PySceneDetect's ContentDetector (`teardown.scenes`), in seconds; `cut_offsets` (issue #94): one per cut,
  {bracket (its nearest mark), cut, offset (cut − bracket)}, then each mark no cut is nearest to, {bracket, cut:
  None, offset: None}, in time order;
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
LEVEL_MAX_DB = 30.0   # the most a quiet part of a take is raised for the second listen
WHISPER_LU = 10.0     # a part this far under the take's level is a whisper
MIN_WINDOW_S = 0.3    # a gap shorter than this between the neighbouring lines holds no line to hear again
SCRIBE_TOOL = "tm tool elevenlabs scribe --run {run} {take} --cost {credits}"


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
    return "\n".join(said)   # one line each (organic_qa.script_lines)


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
    """Each cut against its nearest mark only (one offset per cut), then each mark no cut is nearest to (issue #94:
    one cut at 11.75 s against marks 3/6/9/11 is 0.75 s off 11, and 3, 6 and 9 have no cut)."""
    if not wanted:
        return []
    out, near = [], set()
    for cut in found:
        mark = min(wanted, key=lambda b: abs(cut - b))
        near.add(mark)
        out.append({"bracket": mark, "cut": round(cut, 3), "offset": round(cut - mark, 3)})
    out += [{"bracket": b, "cut": None, "offset": None} for b in wanted if b not in near]
    return sorted(out, key=lambda o: o["bracket"] if o["cut"] is None else o["cut"])


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


def _span(start: float | None, end: float | None) -> list[str]:
    return [] if start is None else ["-ss", f"{start:.3f}", "-t", f"{max(0.0, end - start):.3f}"]


def loudness(take: Path, start: float | None = None, end: float | None = None) -> tuple[float | None, float | None]:
    """(integrated LUFS, true peak dBFS) of a file, or of its part from `start` to `end` s; (None, None) without a
    sound track. ffmpeg failing is an error (CalledProcessError), never "no sound"."""
    if not c.probe(take).get("has_audio"):
        return None, None
    argv = [c.ffmpeg_bin(), "-nostdin", "-hide_banner", "-nostats", "-v", "info", *_span(start, end), "-i",
            c.media(take), "-vn", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
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


def levelled_audio(take: Path, start: float, end: float, gain_db: float):
    """The take's sound from `start` to `end` s raised by `gain_db` (a limiter keeps it from clipping), as 16 kHz
    mono samples for Whisper."""
    import numpy as np

    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-loglevel", "error", *_span(start, end), "-i", c.media(take),
                          "-vn", "-af", f"volume={gain_db:.1f}dB,alimiter=limit=0.9", "-f", "f32le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _words(transcript: dict) -> list[dict]:
    return [w for s in transcript.get("segments") or [] for w in s.get("words") or []]


def _window(n: int, hits: list[dict], words: list[dict], duration: float) -> tuple[float, float]:
    """Where line n can be: from the last heard word of the lines before it to the first of the lines after it."""
    before = [h["last"] for h in hits[:n] if h["last"] is not None]
    after = [h["first"] for h in hits[n + 1:] if h["first"] is not None]
    start = float(words[before[-1]]["end"]) if before else 0.0
    end = float(words[after[0]]["start"]) if after else duration
    return start, end


def _merged(transcript: dict, heard: list[dict], start: float, end: float, gain_db: float) -> dict:
    """The transcript with its words between `start` and `end` replaced by the levelled listen's."""
    def outside(w: dict) -> bool:
        return not start < (w["start"] + w["end"]) / 2 < end

    segments = []
    for s in transcript.get("segments") or []:
        kept = [w for w in s.get("words") or [] if outside(w)]
        if len(kept) == len(s.get("words") or []):
            segments.append(s)
        elif kept:
            segments.append({**s, "start": kept[0]["start"], "end": kept[-1]["end"],
                             "text": "".join(w["word"] for w in kept).strip(), "words": kept})
    segments += [{**s, "levelled_db": round(gain_db, 1)} for s in heard if s.get("words")]
    return {**transcript, "segments": sorted(segments, key=lambda s: s["start"])}


def relisten(take: Path, script: str, transcript: dict, take_lufs: float | None, duration: float, model: str,
             lang: str | None) -> tuple[dict, dict[int, dict]]:
    """(the transcript, {line: {gain_db, used}}) after each line Whisper did not hear whole was heard again,
    levelled and without the silence filter (the module docstring); `used`: the levelled words replaced the first
    listen's. A take with no sound is left as it is."""
    from tm import organic_qa

    lines = organic_qa.script_lines(script)
    levelled: dict[int, dict] = {}
    if take_lufs is None or not lines:
        return transcript, levelled
    for n in range(len(lines)):
        hits = organic_qa.line_hits(lines, _words(transcript))
        if hits[n]["heard"] >= 1:
            continue
        start, end = _window(n, hits, _words(transcript), duration)
        if end - start < MIN_WINDOW_S:
            continue
        level, _ = loudness(take, start, end)
        gain = LEVEL_MAX_DB if level is None else min(LEVEL_MAX_DB, max(0.0, take_lufs - level))
        levelled[n] = {"gain_db": round(gain, 1), "used": False}
        c.say(f"Listening again to {lines[n]!r} at {start:.2f}-{end:.2f} s, raised {gain:.1f} dB.")
        heard, _ = transcribe.listen(levelled_audio(take, start, end, gain), model, lang, vad=False, offset=start)
        candidate = _merged(transcript, heard, start, end, gain)
        better = organic_qa.line_hits(lines, _words(candidate))[n]["heard"] > hits[n]["heard"]
        if better and (organic_qa.match(script, organic_qa.words_of(candidate))
                       >= organic_qa.match(script, organic_qa.words_of(transcript))):
            transcript, levelled[n]["used"] = candidate, True
    return transcript, levelled


def line_report(script: str, transcript: dict, heard_by: str, levelled: dict[int, dict]) -> list[dict]:
    """The `lines` of the QA (the module docstring)."""
    from tm import organic_qa

    lines, words = organic_qa.script_lines(script), _words(transcript)
    out = []
    for n, (line, hit) in enumerate(zip(lines, organic_qa.line_hits(lines, words))):
        again = levelled.get(n)
        by = None if hit["heard"] < 1 else "levelled" if again and again["used"] else heard_by
        row = {"line": line, "heard": hit["heard"],
               "start": words[hit["first"]]["start"] if hit["first"] is not None else None,
               "end": words[hit["last"]]["end"] if hit["last"] is not None else None, "by": by}
        if again:
            row |= {"gain_db": again["gain_db"], "quiet": again["gain_db"] >= WHISPER_LU}
        out.append(row)
    return out


def scribe_words(run, path: Path, take: Path) -> dict:
    """A Scribe transcript of this take (`tm tool elevenlabs scribe`), in the transcript's shape."""
    name = c.name_of(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise c.ToolError(f"The Scribe transcript {name} does not exist.") from None
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get("source") != "scribe" or not isinstance(data.get("segments"), list):
        raise c.ToolError(f"{name} is not a Scribe transcript: make one with tm tool elevenlabs scribe.")
    if data.get("media") != c.rel(run, take):
        raise c.ToolError(f"{name} is Scribe's transcript of {data.get('media')}, not of {c.rel(run, take)}: run "
                          "Scribe on this take.")
    return data


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
    p.add_argument("--scribe", default=None, help="this take's Scribe transcript (tm tool elevenlabs scribe): its "
                                                  "words instead of local Whisper's")
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
    if a.scribe and script is None:
        raise c.ToolError("--scribe needs --script: Scribe's words are checked against the lines the take speaks.")
    scribe = scribe_words(run, c.resolve(run, a.scribe), take) if a.scribe else None
    wanted = brackets(a.brackets)
    info = c.probe(take)
    if not info.get("is_video"):
        raise c.ToolError(f"{c.name_of(take)} is not a video.")
    duration = float(info["duration"])
    out = c.output(run, a.out, stage, f"{take.stem}_qa", "json")
    lufs, peak = loudness(take)
    said = transcript = heard_by = lines = None
    if scribe is not None:
        said, transcript, heard_by = c.resolve(run, a.scribe), scribe, organic_qa.SCRIBE
        lines = line_report(script, transcript, heard_by, {})
    elif script is not None:
        said, heard_by = run.next_version(stage, f"{take.stem}_transcript", "json"), organic_qa.LOCAL
        transcript, levelled = relisten(take, script, transcribe.transcribe(take, a.model, a.lang), lufs, duration,
                                        a.model, a.lang)
        transcribe.keep(run, take, said, transcript, a.model, a.lang,
                        {"levelled": {str(n): v for n, v in levelled.items()}} if levelled else None)
        lines = line_report(script, transcript, heard_by, levelled)
    found = cuts(take)
    sheet = run.next_version(stage, f"{take.stem}_contact", "png")
    contact_sheet(take, duration, sheet)
    c.record(run, sheet, "contact sheet (6 frames)", c.parent_ref(run, take), cost="0 (local)")
    qa = {"take": c.rel(run, take), "transcript": c.rel(run, said) if said else None,
          "match": round(organic_qa.match(script, organic_qa.words_of(transcript)), 3) if script else None,
          **speech(transcript, duration), "cuts": [round(t, 3) for t in found],
          "cut_offsets": offsets(found, wanted), "lufs": lufs, "peak": peak, "contact_sheet": c.rel(run, sheet),
          "lines": lines, "heard_by": heard_by}
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
    answer = {"tool": "take_qa", "outputs": [c.rel(run, out), *([qa["transcript"]] if heard_by == organic_qa.LOCAL
                                                                else []), qa["contact_sheet"]],
              "qa": qa, "rubric": rubric}
    quiet = organic_qa.short_lines(qa, organic_qa.LOCAL)
    if quiet:
        from tm import tts_models

        credits = tts_models.scribe_credits(duration)
        command = SCRIBE_TOOL.format(run=a.run, take=qa["take"], credits=credits)
        answer["scribe"] = {"lines": [line["line"] for line in quiet], "command": command, "credits": credits}
        text += (f" Not heard whole, even levelled: {organic_qa._quoted(quiet)}. Whisper misses quiet lines, so do "
                 f"not call a line missing yet: check the take with Scribe ({command}, about {credits} credits), then "
                 "run this QA again with --scribe <its file>.")
    return c.finish(a, answer, text)


if __name__ == "__main__":
    raise SystemExit(main())
