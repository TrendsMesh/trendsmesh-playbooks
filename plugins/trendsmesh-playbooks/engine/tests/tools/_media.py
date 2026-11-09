"""Fixtures for the tool tests. Media is generated here with ffmpeg, never committed."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tm.runfolder import RunFolder

FPS = 25
W, H = 540, 960
# A semi-transparent bar against the left edge (frames 20-55) and an opaque card in the middle
# (frames 25-50), over testsrc2's colour bars, moving bar and dots.
BAR = (0, 600, 300, 710)
CARD = (150, 200, 390, 290)
DRAW = ("drawbox=x=0:y=600:w=300:h=110:color=white@0.5:t=fill:enable='between(t,0.8,2.2)',"
        "drawbox=x=150:y=200:w=240:h=90:color=white:t=fill:enable='between(t,1,2)'")


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("ffmpeg is not on PATH (run the tests through pixi)")
    return exe


def make_clip(path: Path, vf: str = DRAW, seconds: float = 3.0, tone: bool = True, fps: int = FPS) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    argv = [ffmpeg(), "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={W}x{H}:rate={fps}:duration={seconds}"]
    if tone:
        argv += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={seconds}"]
    argv += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    argv += (["-c:a", "aac", "-shortest"] if tone else [])
    argv += [str(path)]
    subprocess.run(argv, check=True)
    return path


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> Path:
    """3 s, 540x960 at 25 fps: testsrc2 with two drawbox overlays and a 440 Hz tone."""
    folder = tmp_path_factory.mktemp("media") / "Moje reklamy Łukasz Nowak"
    return make_clip(folder / "Reklama zimowa — wersja 1.mp4")


@pytest.fixture
def run(tmp_path) -> RunFolder:
    return RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "test ad", date(2026, 11, 5))


def gray_frame(video: Path, index: int) -> tuple[int, int, bytes]:
    """One decoded frame as 8-bit gray bytes, read with ffmpeg (no numpy needed)."""
    probe = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    raw = subprocess.run(
        [ffmpeg(), "-nostdin", "-v", "error", "-i", str(video), "-vf", f"select=eq(n\\,{index})",
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True).stdout
    return w, h, raw
