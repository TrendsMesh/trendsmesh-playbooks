"""Index a music folder so the agent can pick a track by length, loudness, tempo and mood.

    tm tool music_index --run RUN DIR [--moods MOODS.json] [--out PATH] [--json]

For every audio file in DIR (not its sub-folders): duration (ffprobe), integrated loudness in LUFS
(ffmpeg ebur128), an estimated tempo in BPM (onset autocorrelation on a 60 s excerpt, numpy only;
an estimate, and it may be half or double the felt tempo), and mood / licence / source from
MOODS.json {"file.mp3": {"mood", "licence", "source"}}, else the file's genre tag, else empty (the
agent then asks the user once). The agent cannot listen: it picks by this index and the user confirms.

The index is written into the run, `02_research/music_index_vNN.csv` (the next version, never an
overwrite), and never into DIR: the user's music folder is only read. The profile's `music.index`
names that file. Files ffprobe cannot read are skipped and named in the answer.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

from tm.tools import _common as c

AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
COLUMNS = ["file", "title", "duration_s", "lufs", "bpm_est", "mood", "licence", "source"]
TEMPO_SR = 11025


def _probe(path: Path) -> dict:
    out = subprocess.run([c.ffprobe_bin(), "-v", "error", "-show_entries",
                          "format=duration:format_tags=title,artist,genre,comment", "-of", "json", c.media(path)],
                         capture_output=True, check=True).stdout
    fmt = json.loads(out.decode("utf-8", "replace")).get("format", {})
    return {"duration": float(fmt.get("duration") or 0),
            "tags": {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}}


def loudness(path: Path) -> float | None:
    err = subprocess.run([c.ffmpeg_bin(), "-hide_banner", "-nostats", "-nostdin", "-i", c.media(path),
                          "-af", "ebur128", "-f", "null", "-"], capture_output=True).stderr.decode("utf-8", "replace")
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", err)
    return float(found[-1]) if found else None


def tempo(path: Path, duration: float) -> float | None:
    import numpy as np

    sr = TEMPO_SR
    start = "10" if duration > 30 else "0"  # skip an intro only when there is plenty left
    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", "-ss", start, "-t", "60", "-i", c.media(path),
                          "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    if x.size < sr * 10:
        return None
    hop, win = 256, 1024
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop] * np.hanning(win)
    spec = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(np.diff(np.log1p(spec), axis=0), 0).sum(axis=1)
    flux = flux - flux.mean()
    ac = np.correlate(flux, flux, mode="full")[flux.size - 1:]
    if not ac[0] > 0:  # no onsets at all (a steady tone, silence)
        return None
    bpm = 60 * (sr / hop) / np.maximum(np.arange(ac.size), 1)
    ok = (bpm >= 60) & (bpm <= 180)
    if not ok.any():
        return None
    return round(float(bpm[ok][np.argmax(ac[ok])]), 1)


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("music_index", "Index a music folder: length, loudness, tempo estimate, mood.")
    p.add_argument("music_dir", help="the folder with the music (only read)")
    p.add_argument("--moods", default=None, help="a JSON file {\"file.mp3\": {mood, licence, source}}")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    folder = Path(a.music_dir)
    if not folder.is_dir():
        raise c.ToolError(f"The music folder {c.name_of(folder)} does not exist. Nothing was written.")
    moods = c.read_json(run, a.moods, "moods file") or {}
    files = sorted((f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in AUDIO), key=lambda f: f.name)
    if not files:
        raise c.ToolError(f"The music folder {c.name_of(folder)} holds no audio files "
                          f"({', '.join(sorted(AUDIO))}). Nothing was written.")
    rows, skipped = [], []
    for f in files:
        try:
            info = _probe(f)
            bpm = tempo(f, info["duration"])
        except (subprocess.CalledProcessError, ValueError):
            skipped.append(f.name)
            continue
        extra = moods.get(f.name) if isinstance(moods.get(f.name), dict) else {}
        rows.append({"file": f.name, "title": info["tags"].get("title", ""),
                     "duration_s": round(info["duration"], 1), "lufs": loudness(f), "bpm_est": bpm,
                     "mood": extra.get("mood", info["tags"].get("genre", "")),
                     "licence": extra.get("licence", ""), "source": extra.get("source", "")})
    if not rows:
        raise c.ToolError(f"No audio file in {c.name_of(folder)} could be read ({', '.join(skipped)}). "
                          "Nothing was written.")
    out = c.output(run, a.out, "research", "music_index", "csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows({k: ("" if v is None else v) for k, v in r.items()} for r in rows)
    c.record(run, out, "music folder index", c.parent_ref(run, folder), params={"files": len(rows)},
             cost="free")
    note = f" Skipped (unreadable): {', '.join(skipped)}." if skipped else ""
    return c.finish(a, {"tool": "music_index", "outputs": [c.rel(run, out)], "files": len(rows),
                        "skipped": skipped},
                    f"Indexed {len(rows)} track(s) into {c.rel(run, out)}. The tempo is an estimate.{note}")


if __name__ == "__main__":
    raise SystemExit(main())
