"""What every tool shares: its outputs in the run folder, the manifest row, ffmpeg, exit codes.

Every tool's CLI takes `--run <run folder>` and writes its output inside that run folder: either
`--out` (a path relative to the run folder, which must not exist yet) or the next free version
under the tool's stage (`03_wip/<stem>_v01.<ext>`, `_v02`, ...). Inputs are ordinary paths.
Nothing is ever overwritten. Each output gets a manifest row, and the tool's raw request and
response go next to it as `<file>.response.json` (through `manifest.record`).

Exit codes: 0 done, 2 stop (the user must act: a key, credits, a missing tier), 1 error.
`--json` prints one JSON object on stdout; progress goes to stderr.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterator

from tm import manifest, paths
from tm.runfolder import ReadOnlyError, RunFolder, slug

KEY_VARS = ("REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY")


class ToolError(Exception):
    """The tool could not do its job (exit 1)."""


class ToolStop(Exception):
    """The user must act before the tool can run (exit 2)."""


def scrub(text: str) -> str:
    """Remove any key value this process holds from a message before it is shown."""
    for var in KEY_VARS:
        value = os.environ.get(var)
        if value and len(value) >= 6:
            text = text.replace(value, "[key hidden]")
    return text


def parser(prog: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"tm tool {prog}", description=description, allow_abbrev=False)
    add_common(p)
    return p


def add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder (runs/01-refresh-ad/<date>_<name>)")
    p.add_argument("--out", default=None, help="output path relative to the run folder (default: next version)")
    p.add_argument("--json", action="store_true", help="print one JSON object")


def say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def guarded(main: Callable[[list[str] | None], int]) -> Callable[[list[str] | None], int]:
    """Every failure becomes one message (one JSON object with --json) and exit code 1 (error) or
    2 (stop). Unexpected exceptions are errors too, never a traceback on stdout."""

    @functools.wraps(main)
    def wrapper(argv: list[str] | None = None) -> int:
        as_json = "--json" in (sys.argv[1:] if argv is None else argv)
        try:
            return main(argv)
        except SystemExit as exc:  # argparse: --help (0) or bad arguments (its usage is on stderr)
            if exc.code in (0, None):
                return 0
            return _fail(as_json, "error", "The arguments are not valid (see the usage above).", 1)
        except ToolStop as exc:
            return _fail(as_json, "stop", str(exc), 2)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            tail = " ".join(detail.strip().splitlines()[-3:])
            return _fail(as_json, "error", f"{Path(str(exc.cmd[0])).name} failed: {tail}", 1)
        except ModuleNotFoundError as exc:
            from tm import tools

            tier = getattr(tools.TOOLS.get(main.__module__.rsplit(".", 1)[-1]), "tier", "this tool's")
            return _fail(as_json, "stop", f"The '{tier}' tools are missing a part ({exc.name}): they may be "
                         f"out of date. Nothing was run. Update them with: tm env install {tier} --yes "
                         "(after the user's yes). The run continues from the same place.", 2)
        except (ToolError, ValueError, OSError, RuntimeError, ReadOnlyError) as exc:
            return _fail(as_json, "error", str(exc), 1)
        except Exception as exc:  # noqa: BLE001 - a bug still answers in the contract's shape
            return _fail(as_json, "error", f"Unexpected {type(exc).__name__}: {exc}", 1)

    return wrapper


def report_cost(spent: bool, actual: float | None = None) -> None:
    """Tell the engine (through the file it named in TM_COST_REPORT) whether money was spent and,
    when known, the actual cost; the engine reconciles it with the approved estimate."""
    path = os.environ.get("TM_COST_REPORT")
    if path:
        Path(path).write_text(json.dumps({"spent": spent, "actual": actual}), encoding="utf-8")


def media(path: Path | str) -> str:
    """A path for ffmpeg/ffprobe argv: absolute, so a name starting with '-' or holding ':' is
    never read as an option or a protocol."""
    return str(Path(path).resolve())


def _fail(as_json: bool, status: str, message: str, code: int) -> int:
    message = scrub(message)
    print(json.dumps({"status": status, "message": message}, ensure_ascii=False) if as_json else message)
    return code


def finish(args: argparse.Namespace, payload: dict, text: str) -> int:
    print(json.dumps({"status": "done", **payload}, ensure_ascii=False) if args.json else text)
    return 0


# Run folder and manifest -------------------------------------------------------------------

def open_run(path: str) -> RunFolder:
    return RunFolder.open(Path(path))


def stem_of(path: Path | str) -> str:
    return slug(Path(path).stem)


def output(run: RunFolder, out: str | None, stage: str, stem: str, ext: str) -> Path:
    if out:
        target = Path(out)
        target = target if target.is_absolute() else run.path / target
        try:
            target.resolve().relative_to(run.path.resolve())
        except ValueError:
            raise ToolError(f"--out must be inside the run folder {run.path}, got {out}.") from None
        if target.exists():
            raise ToolError(f"{out} already exists, and files are never overwritten. Leave out --out "
                            "to get the next version.")
    else:
        target = run.next_version(stage, stem, ext)
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def rel(run: RunFolder, path: Path) -> str:
    return Path(path).resolve().relative_to(run.path.resolve()).as_posix()


def parent_ref(run: RunFolder, path: Path | str) -> str:
    """The parent column: the path inside the run folder, or the file's own name when outside."""
    path = Path(path)
    try:
        return rel(run, path)
    except ValueError:
        return path.name


def record(run: RunFolder, path: Path, source: str, parent: str | None = None, *,
           prompt: str | None = None, params: dict | None = None, model: str | None = None,
           cost: str | None = None, before_after: str | None = None,
           request: dict | None = None, response: object = None) -> None:
    """One manifest row for `path`, with {"request", "response"} saved next to it."""
    file = rel(run, path)
    raw = None
    if request is not None or response is not None:
        raw = json.dumps({"request": request, "response": response}, ensure_ascii=False, indent=1, default=str)
        raw = scrub(raw)
    manifest.record(run, file, file.split("/", 1)[0], source, parent=parent, prompt=prompt, params=params,
                    model=model, cost=cost, before_after=before_after, raw_response=raw)


def local_file(value: object, base: Path) -> Path | None:
    """A spec input that names an existing local file (absolute, or relative to `base`, the spec's
    folder), else None: what replicate_run sends as a file, and what the organic guard checks."""
    if isinstance(value, str) and value and not value.startswith(("http://", "https://", "data:")):
        p = Path(value) if Path(value).is_absolute() else Path(base) / value
        if p.is_file():
            return p
    return None


def name_of(path: Path | str) -> str:
    """A file's own name, the last part on either separator: what messages show, never a whole path."""
    return str(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def resolve(run: RunFolder, text: Path | str) -> Path:
    """An input path as given, else relative to the run folder when only that exists."""
    path = Path(text)
    if not path.is_absolute() and not path.exists() and (run.path / path).exists():
        return run.path / path
    return path


def read_json(run: RunFolder, text: Path | str | None, what: str, after: str = "") -> dict | None:
    """The JSON object in `text` (see `resolve`), or None for None. `after` ends each error message."""
    if text is None:
        return None
    name = name_of(text)
    try:
        data = json.loads(resolve(run, text).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"The {what} {name} does not exist.{after}") from None
    except json.JSONDecodeError as exc:
        raise ToolError(f"The {what} {name} is not valid JSON: {exc}.{after}") from None
    if not isinstance(data, dict):
        raise ToolError(f"The {what} {name} must hold one JSON object.{after}")
    return data


REPLACE_WAIT_S = 2.0


def replace(src: Path, dst: Path) -> None:
    """`os.replace`, again for up to REPLACE_WAIT_S while Windows refuses it with PermissionError because another
    process (a player, a preview, an antivirus scan) has the file open; elsewhere the first try is the only one."""
    deadline = time.monotonic() + REPLACE_WAIT_S
    while True:
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def write_json(path: Path, data: object, *, newline: str | None = None) -> None:
    """`newline="\\n"` keeps LF on Windows too (a file read beside LF-only ones)."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline=newline)


def models_dir(name: str) -> Path:
    """Downloaded models live in the plugin data folder, never in a global cache."""
    folder = paths.data_dir() / "models" / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ffmpeg ------------------------------------------------------------------------------------

def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run([ffmpeg_bin(), "-nostdin", "-v", "error", "-y", *args], check=True, capture_output=True)


_IMAGE_FORMATS = ("image2", "png_pipe", "jpeg_pipe", "webp_pipe", "bmp_pipe", "tiff_pipe", "gif")


def probe(path: Path | str) -> dict:
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-show_streams", "-show_format", "-of", "json",
                          media(path)], capture_output=True, check=True).stdout
    data = json.loads(out.decode("utf-8", "replace"))
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    fmt = data.get("format", {})
    if video is None:
        return {"has_video": False, "has_audio": audio, "is_video": False,
                "duration": float(fmt.get("duration") or 0)}
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    fps = float(Fraction(rate)) if rate not in ("0/0", "") else 0.0
    duration = float(video.get("duration") or fmt.get("duration") or 0)
    frames = int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else round(duration * fps)
    still = any(f in fmt.get("format_name", "") for f in _IMAGE_FORMATS) and frames <= 1
    return {"has_video": True, "has_audio": audio, "is_video": not still and frames > 1,
            "width": int(video["width"]), "height": int(video["height"]), "fps": round(fps, 3),
            "frames": frames, "duration": round(duration, 3)}


def decode_mono(video: Path | str, sr: int):
    """The soundtrack as mono float32 at `sr`, decoded by ffmpeg (no audio track gives an empty array)."""
    import numpy as np

    if not probe(video).get("has_audio"):
        return np.zeros(0, dtype=np.float32)
    raw = subprocess.run([ffmpeg_bin(), "-nostdin", "-v", "error", "-i", media(video), "-vn", "-ac", "1",
                          "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def decode(path: Path | str, width: int, height: int, pix_fmt: str = "gray") -> Iterator:
    """Decoded frames as numpy arrays (height, width[, 3]), streamed from ffmpeg (any path works)."""
    import numpy as np

    channels = {"gray": 1, "bgr24": 3}[pix_fmt]
    size = width * height * channels
    proc = subprocess.Popen(
        [ffmpeg_bin(), "-nostdin", "-v", "error", "-i", media(path), "-vf", f"scale={width}:{height}",
         "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        assert proc.stdout is not None
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            frame = np.frombuffer(buf, np.uint8)
            yield frame.reshape((height, width) if channels == 1 else (height, width, 3))
    finally:
        if proc.stdout:
            proc.stdout.close()
        proc.wait()
