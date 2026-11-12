"""Speaker similarity (ECAPA-TDNN, SpeechBrain spkrec-ecapa-voxceleb): cosine of 192-d embeddings.

    tm tool speaker_sim --run RUN A.wav B.wav [C.wav ...] [--no-band] [--out PATH] [--json]

Used only for QA of a clone, never for choosing a voice (HANDOFF 3, VARIANTS 4). By default both
recordings are limited to the 100 Hz - 4 kHz band first (VARIANTS 4, rule 0: compare only with
equalised quality). Thresholds from the calibration: >= 0.65 same, <= 0.40 different, between them
the listening test decides; the blind test (G-V) always has the final word.
Ported from handoff/refresh-ad_v02/tools/speaker_sim.py, keeping LocalStrategy.COPY (no symlinks,
which Windows refuses without developer mode). The model lives in <data>/models.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tm.tools import _common as c

SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
BAND = "highpass=f=100,lowpass=f=4000"

_model = None


def _encoder_class():
    from speechbrain.inference.speaker import EncoderClassifier

    return EncoderClassifier


def model():
    global _model
    if _model is None:
        from speechbrain.utils.fetching import FetchConfig, LocalStrategy

        _model = _encoder_class().from_hparams(
            source=SOURCE, savedir=str(c.models_dir("spkrec-ecapa-voxceleb")), run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
            fetch_config=FetchConfig(huggingface_cache_dir=str(c.models_dir("huggingface"))))
    return _model


def load(path: Path | str, start: float | None = None, end: float | None = None, band: bool = False):
    import numpy as np

    argv = [c.ffmpeg_bin(), "-nostdin", "-v", "error"]
    argv += (["-ss", str(start)] if start is not None else []) + (["-to", str(end)] if end is not None else [])
    argv += ["-i", c.media(path)] + (["-af", BAND] if band else [])
    argv += ["-f", "f32le", "-ac", "1", "-ar", "16000", "-"]
    return np.frombuffer(subprocess.run(argv, capture_output=True, check=True).stdout, np.float32).copy()


def embed(path: Path | str, start: float | None = None, end: float | None = None, band: bool = True):
    import torch

    x = torch.from_numpy(load(path, start, end, band)).unsqueeze(0)
    with torch.no_grad():
        e = model().encode_batch(x).squeeze()
    return e / e.norm()


def cos(a, b) -> float:
    return float((a * b).sum())


def matrix(files: list[Path | str], band: bool = True) -> list[list[float]]:
    es = [embed(f, band=band) for f in files]
    return [[round(cos(a, b), 3) for b in es] for a in es]


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("speaker_sim", "Speaker similarity matrix (ECAPA) for clone QA.")
    p.add_argument("files", nargs="+")
    p.add_argument("--no-band", action="store_true", help="compare the full band (not recommended)")
    a = p.parse_args(argv)
    if len(a.files) < 2:
        raise c.ToolError("Give at least two recordings to compare.")
    run = c.open_run(a.run)
    c.inputs(run, a, "files")   # a run-relative input, whatever the working folder
    out = c.output(run, a.out, "wip", "speaker_sim", "json")
    names = [c.parent_ref(run, f) for f in a.files]
    sims = matrix(a.files, band=not a.no_band)
    result = {"files": names, "band": None if a.no_band else "100-4000 Hz", "matrix": sims}
    c.write_json(out, result)
    c.record(run, out, "speaker similarity (ECAPA, local)", ", ".join(names), model=SOURCE, cost="0 (local)",
             params={"band": result["band"]}, request={"files": names, "band": result["band"]}, response=result)
    lines = [" ".join(f"{v:.3f}" for v in row) + f"  {n}" for row, n in zip(sims, names)]
    return c.finish(a, {"tool": "speaker_sim", "outputs": [c.rel(run, out)], **result},
                    "\n".join(lines + [f"Saved to {c.rel(run, out)}."]))


if __name__ == "__main__":
    raise SystemExit(main())
