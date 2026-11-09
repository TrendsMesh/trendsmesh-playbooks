"""segment_map: the retention steps mapped to seconds of the ad's file (path C-R, step CR1).

    tm tool segment_map --run RUN VIDEO --teardown T [--transcript X] [--json]

Each step of the retention ladder covers a share of the video length (`ladder.SEGMENT`). For each
one this lists what was on screen and what was heard, so the agent can name the causes of a weak
middle: the cards on screen, the visual change, the loudness and the words spoken.

Writes `03_wip/retention/segment_map_vNN.json` (versioned, never overwritten) = {
  "video", "duration_s", "fps",
  "steps": [{step, from_s, to_s, peak, latest, cards, visual_change, loudness_db, speech_words}],
  "visual_change_0p5s": [[t, v]]  the mean absolute difference between grayscale frames 0.5 s apart
                                  (180 px wide), as in the handoff's motion_profile.py,
  "loudness_0p5s": [[t, dBFS]]    RMS per 0.5 s, silence floors at -90,
  "last_new_info_s": the later of the last overlay start and the last word start (null if none),
  "dropped": the diagnosis ladder's dropped steps ([] without a diagnosis),
  "weakest": the first dropped step in ladder.MIDDLE; else the diagnosis' structural step; else the
             step in ladder.MIDDLE with the lowest `latest`; else null}.

`peak` and `latest` come from the run's diagnosis ladder (null when it is `{}` or there is none).
`cards` are the indices in the teardown's `overlays` of the overlays on screen at any time within
the step. `speech_words` counts the transcript words starting in the step (null without a
transcript). The video length comes from the file. The tool is free.
"""

from __future__ import annotations

from pathlib import Path

from tm import ladder, state
from tm.tools import _common as c

SILENCE_DB = -90.0
SR = 16000
HALF_S = 0.5


def _visual(video: Path, fps: float, width: int, height: int) -> list[list[float]]:
    """[[t, mean abs frame difference 0.5 s apart]] at every 0.5 s, from the grayscale frames. Only
    every `step`-th frame is compared, so only the last of those is kept while the rest stream by."""
    import numpy as np

    w = 180
    h = max(1, int(w * height / width))
    step = max(1, int(round(fps / 2)))
    out, prev = [], None
    for n, frame in enumerate(c.decode(video, w, h, "gray")):
        if n % step:
            continue
        frame = frame.astype(np.float32)
        if prev is not None:
            out.append([(n - step) / fps, float(np.mean(np.abs(frame - prev)))])
        prev = frame
    return out


def _loudness(video: Path) -> list[list[float]]:
    """[[t, RMS dBFS]] per 0.5 s; silence floors at -90. Empty when the file has no audio track."""
    import numpy as np

    y = c.decode_mono(video, SR)
    n = int(SR * HALF_S)
    out = []
    for i in range(0, len(y) - n + 1, n):
        rms = float(np.sqrt(np.mean(np.square(y[i:i + n], dtype=np.float64))))
        out.append([i / SR, max(SILENCE_DB, 20 * float(np.log10(rms))) if rms > 0 else SILENCE_DB])
    return out


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _in(t: float, lo: float, hi: float, last: bool) -> bool:
    return lo <= t < hi or (last and t == hi)


def _overlays(teardown: dict) -> list[tuple[float, float]]:
    out = []
    for o in teardown.get("overlays") or []:
        try:
            out.append((float(o["start_s"]), float(o["end_s"])))
        except (KeyError, TypeError, ValueError):
            raise c.ToolError("The teardown has an overlay without start_s and end_s. Nothing was mapped.") from None
    return out


def _word_starts(transcript: dict) -> list[float]:
    try:
        return [float(w["start"]) for s in transcript.get("segments", []) for w in s.get("words", [])]
    except (KeyError, TypeError, ValueError):
        raise c.ToolError("The transcript has a word without a start time. Nothing was mapped.") from None


def build(duration: float, diagnosis: dict | None, overlays: list[tuple[float, float]],
          words: list[float] | None, visual: list[list[float]], loud: list[list[float]]) -> dict:
    diagnosis = diagnosis or {}
    lad = diagnosis.get("ladder") or {}
    peak, latest = lad.get("peak") or {}, lad.get("latest") or {}
    steps = []
    for step in ladder.STEPS:
        a, b = (share * duration for share in ladder.SEGMENT[step])
        last = step == ladder.STEPS[-1]
        steps.append({
            "step": step, "from_s": round(a, 2), "to_s": round(b, 2),
            "peak": peak.get(step), "latest": latest.get(step),
            "cards": [i for i, (s, e) in enumerate(overlays) if s < b and e > a],
            "visual_change": _mean([v for t, v in visual if _in(t, a, b, last)]),
            "loudness_db": _mean([v for t, v in loud if _in(t, a, b, last)]),
            "speech_words": None if words is None else sum(1 for t in words if _in(t, a, b, last)),
        })
    known = [(s["latest"], s["step"]) for s in steps if s["step"] in ladder.MIDDLE
             and isinstance(s["latest"], (int, float)) and not isinstance(s["latest"], bool)]
    structural = (diagnosis.get("structural") or {}).get("step")
    dropped = [d for d in lad.get("dropped") or [] if d in ladder.STEPS]
    first_dropped = next((d for d in ladder.MIDDLE if d in dropped), None)
    starts = [s for s, _ in overlays] + (words or [])
    return {"steps": steps, "last_new_info_s": round(max(starts), 2) if starts else None, "dropped": dropped,
            "weakest": first_dropped or structural or (min(known)[1] if known else None)}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("segment_map", "Retention steps mapped to seconds, with cards, visual change, loudness and speech.")
    p.add_argument("video", help="the ad's file (01_base/...)")
    p.add_argument("--teardown", required=True, help="the teardown JSON (02_research/teardown_vNN.json)")
    p.add_argument("--transcript", default=None, help="the transcript JSON (02_research/transcript_vNN.json)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    video = c.resolve(run, a.video)
    if not video.is_file():
        raise c.ToolError(f"The video {c.name_of(a.video)} does not exist. Nothing was mapped.")
    teardown = c.read_json(run, a.teardown, "teardown", " Nothing was mapped.")
    overlays = _overlays(teardown)
    transcript = c.read_json(run, a.transcript, "transcript", " Nothing was mapped.")
    words = _word_starts(transcript) if transcript is not None else None
    info = c.probe(video)
    if not info.get("is_video"):
        raise c.ToolError(f"{video.name} has no moving picture, so there is nothing to map.")
    duration = float(info["duration"])
    if duration <= 0:
        raise c.ToolError(f"{video.name} has no length, so there is nothing to map.")
    out = c.output(run, a.out, "03_wip/retention", "segment_map", "json")
    try:
        diagnosis = state.load(run).diagnosis
    except (OSError, ValueError):
        diagnosis = None

    c.say("Measuring the picture")
    visual = _visual(video, info["fps"], info["width"], info["height"])
    c.say("Measuring the sound")
    loud = _loudness(video) if info.get("has_audio") else []
    body = build(duration, diagnosis, overlays, words, visual, loud)
    if not info.get("has_audio"):
        for s in body["steps"]:
            s["loudness_db"] = SILENCE_DB
    result = {"video": c.parent_ref(run, video), "duration_s": round(duration, 3), "fps": info["fps"], **body,
              "visual_change_0p5s": [[round(t, 3), round(v, 3)] for t, v in visual],
              "loudness_0p5s": [[round(t, 3), round(v, 2)] for t, v in loud]}
    c.write_json(out, result)
    c.record(run, out, "tm tool segment_map", c.parent_ref(run, video),
             request={"video": result["video"], "teardown": a.teardown, "transcript": a.transcript},
             response={"weakest": body["weakest"], "last_new_info_s": body["last_new_info_s"]})
    text = (f"Segment map saved to {c.rel(run, out)}: {len(body['steps'])} steps over {duration:.1f} s, "
            f"weakest {body['weakest'] or 'unknown'}.")
    return c.finish(a, {"tool": "segment_map", "outputs": [c.rel(run, out)], **result}, text)


if __name__ == "__main__":
    raise SystemExit(main())
