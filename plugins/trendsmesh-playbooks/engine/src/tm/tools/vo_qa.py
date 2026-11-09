"""R9 QA: a processed voiceover line against its unprocessed version.

    tm tool vo_qa --run RUN PROCESSED ORIGINAL [--out PATH] [--json]

Two measures, each within +-tolerance (config `vo.qa_tolerance`, default 0.10) of the original:
- onset steepness, dB per 5 ms: the level envelope in 5 ms frames; at each syllable onset (a local
  peak of the frame-to-frame rise, over 3 dB, within 40 dB of the loudest frame) the rise is taken;
  the median over onsets. A smeared stretch (rubberband `smooth`, reverb) softens onsets.
- spectral flatness: geometric over arithmetic mean of the power spectrum (2048-point frames, hop
  512, Hann), the median over frames within 40 dB of the loudest. Reverb and smear raise it.
Both files are decoded with ffmpeg to mono 44.1 kHz. The A/B listening in HITL stays the judge.
"""

from __future__ import annotations

from pathlib import Path

from tm.tools import _common as c

SR = 44100
ONSET_FRAME_S = 0.005
ACTIVE_DB = 40.0
MIN_RISE_DB = 3.0


def load(path: Path | str):
    import subprocess

    import numpy as np

    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-i", c.media(path), "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def onset_steepness(x) -> float:
    import numpy as np

    n = int(SR * ONSET_FRAME_S)
    frames = len(x) // n
    if frames < 3:
        return 0.0
    rms = np.sqrt(np.mean(x[: frames * n].reshape(frames, n) ** 2, axis=1))
    level = 20 * np.log10(rms + 1e-10)
    rise = np.diff(level)
    active = level[1:] > level.max() - ACTIVE_DB
    peak = np.r_[False, (rise[1:-1] >= rise[:-2]) & (rise[1:-1] >= rise[2:]), False]
    onsets = rise[peak & active & (rise > MIN_RISE_DB)]
    return float(np.median(onsets)) if onsets.size else 0.0


def spectral_flatness(x) -> float:
    import numpy as np

    size, hop = 2048, 512
    if len(x) < size:
        return 0.0
    count = 1 + (len(x) - size) // hop
    idx = np.arange(size)[None, :] + hop * np.arange(count)[:, None]
    frames = x[idx] * np.hanning(size)
    power = np.abs(np.fft.rfft(frames, axis=1)) ** 2 + 1e-12
    level = 10 * np.log10(power.mean(axis=1))
    active = level > level.max() - ACTIVE_DB
    flat = np.exp(np.log(power).mean(axis=1)) / power.mean(axis=1)
    return float(np.median(flat[active]))


def _side(processed: float, original: float) -> dict:
    """rel_diff is None when the original measures 0 and the processed line does not."""
    rel = (processed - original) / abs(original) if original else (0.0 if processed == original else None)
    return {"processed": float(f"{processed:.6g}"), "original": float(f"{original:.6g}"),
            "rel_diff": None if rel is None else round(rel, 4)}


def _within(side: dict, tolerance: float) -> bool:
    return side["rel_diff"] is not None and abs(side["rel_diff"]) <= tolerance


def compare(processed: Path | str, original: Path | str, tolerance: float = 0.10) -> dict:
    p, o = load(processed), load(original)
    onset = _side(onset_steepness(p), onset_steepness(o))
    flat = _side(spectral_flatness(p), spectral_flatness(o))
    within = _within(onset, tolerance) and _within(flat, tolerance)
    return {"onset_steepness_db_per_5ms": onset, "spectral_flatness": flat, "tolerance": tolerance,
            "within_tolerance": bool(within)}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    from tm import config

    p = c.parser("vo_qa", "R9: compare a processed voiceover line with the unprocessed one.")
    p.add_argument("processed")
    p.add_argument("original")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    cfg = config.load(run) if (run.path / config.FILE).is_file() else None
    tolerance = float(config.value(cfg, "vo.qa_tolerance"))
    out = c.output(run, a.out, "wip", "vo_qa", "json")
    res = compare(a.processed, a.original, tolerance)
    res["processed"], res["original"] = c.parent_ref(run, a.processed), c.parent_ref(run, a.original)
    c.write_json(out, res)
    c.record(run, out, "tm tool vo_qa (R9)", res["processed"], params={"tolerance": tolerance},
             before_after=f"QA of {res['processed']} against {res['original']}",
             request={"processed": res["processed"], "original": res["original"], "tolerance": tolerance},
             response=res)
    verdict = "within" if res["within_tolerance"] else "outside"
    pct = lambda side: "n/a" if side["rel_diff"] is None else f"{side['rel_diff']:+.1%}"  # noqa: E731
    return c.finish(a, {"tool": "vo_qa", "outputs": [c.rel(run, out)], **res},
                    f"The processed line is {verdict} the {tolerance:.0%} tolerance (onset "
                    f"{pct(res['onset_steepness_db_per_5ms'])}, flatness {pct(res['spectral_flatness'])}). "
                    f"Saved to {c.rel(run, out)}.")


if __name__ == "__main__":
    raise SystemExit(main())
