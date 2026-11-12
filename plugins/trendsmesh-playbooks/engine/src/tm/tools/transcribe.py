"""Local transcription with word timestamps (faster-whisper, free, CPU, int8).

    tm tool transcribe --run RUN MEDIA [--model large-v3-turbo] [--lang pl] [--out PATH] [--json]

Writes {"language", "language_probability", "duration", "segments": [{start, end, text,
words: [{start, end, word, probability}]}]} to 02_research/transcript_vNN.json. An ad without
speech, or no audio track at all, gives no segments (lesson 3): the structure then comes from
captions and shots.
Ported from handoff/refresh-ad_v02/tools/transcribe.py. The model downloads once into the plugin
data folder (<data>/models/whisper), never into a global cache.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tm.tools import _common as c

DEFAULT_MODEL = "large-v3-turbo"


def load_audio(path: Path | str):
    """16 kHz mono float32, decoded with ffmpeg (the bundled PyAV decoder breaks on some versions)."""
    import numpy as np

    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-loglevel", "error", "-i", c.media(path), "-f", "f32le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _model_class():
    from faster_whisper import WhisperModel

    return WhisperModel


def transcribe(media: Path | str, model: str = DEFAULT_MODEL, lang: str | None = None) -> dict:
    info = c.probe(media)
    if not info.get("has_audio"):
        return {"language": None, "language_probability": 0.0, "duration": info.get("duration") or 0.0,
                "segments": [], "note": "no audio track"}
    whisper = _model_class()(model, device="cpu", compute_type="int8",
                             download_root=str(c.models_dir("whisper")))
    segments, info = whisper.transcribe(load_audio(media), language=lang, word_timestamps=True, vad_filter=True)
    result = {"language": info.language, "language_probability": round(float(info.language_probability), 3),
              "duration": round(float(info.duration), 2), "segments": []}
    for s in segments:
        result["segments"].append({
            "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word,
                       "probability": round(w.probability, 3)} for w in (s.words or [])],
        })
        c.say(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text.strip()}")
    return result


def save(run, media: Path | str, out: Path, model: str, lang: str | None) -> dict:
    """Transcribe `media` into `out` and give it its manifest row (teardown uses this too)."""
    result = transcribe(media, model, lang)
    c.write_json(out, result)
    params = {"lang": lang, "device": "cpu", "compute_type": "int8", "word_timestamps": True, "vad_filter": True}
    c.record(run, out, "faster-whisper (local)", c.parent_ref(run, media), params=params, model=model,
             cost="0 (local)", request={"media": c.parent_ref(run, media), "model": model, **params},
             response={k: result[k] for k in ("language", "language_probability", "duration")}
             | {"segments": len(result["segments"])})
    return result


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("transcribe", "Transcript with word timestamps (faster-whisper on CPU).")
    p.add_argument("media")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--lang", default=None, help="language code, e.g. pl (default: detect)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    c.inputs(run, a, "media")   # a run-relative input, whatever the working folder
    out = c.output(run, a.out, "research", "transcript", "json")
    result = save(run, a.media, out, a.model, a.lang)
    words = sum(len(s["words"]) for s in result["segments"])
    return c.finish(a, {"tool": "transcribe", "outputs": [c.rel(run, out)], "language": result["language"],
                        "segments": len(result["segments"]), "words": words},
                    f"Transcript saved to {c.rel(run, out)}: {len(result['segments'])} segment(s), "
                    f"{words} word(s), language {result['language']}.")


if __name__ == "__main__":
    raise SystemExit(main())
