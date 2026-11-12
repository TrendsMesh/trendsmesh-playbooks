"""deliver: an organic video's delivery files (playbook 03, FLOWS.md G1 and G2; PLAYBOOK.md "Output format").

    tm tool deliver finish  --run RUN IN --id ID [--asmr] [--json]
    tm tool deliver speed   --run RUN IN --factor F [--json]
    tm tool deliver upload  --run RUN FINAL [--json]
    tm tool deliver preview --run RUN IN [--json]
    tm tool deliver cover   --run RUN PNG [--json]
    tm tool deliver nosound --run RUN FINAL [--json]
    tm tool deliver measure --run RUN FILE... [--json]

Free and local (base tier).

- finish: the edit's render becomes `04_final/<ID>_final_vNN.mp4` (the next version; ID in the run's own spelling,
  `--id M5` and `--id m5` are one idea, another idea's id is refused): scaled to 1080×1920 (lanczos),
  H.264 (CRF 18), AAC 48 kHz, `alimiter`, then a two-pass `loudnorm` to the run's `qa.lufs_target` (−14 LUFS), or
  `qa.lufs_asmr` (−16) with --asmr. The final is measured again and its LUFS printed. A render with no sound is
  refused: a video posted with only the in-app sound is a final's `nosound` export. (A 720p take made 1080p by an
  upscaler is a pack item, paid at F2; this scaling is free.)
- speed: IN sped up ×F (`setpts` and `atempo`: the pitch is kept, so lips stay in sync), F above 1 and at most the
  run's `qa.speed_max` (×1.25), else refused (exit 2). `<IN stem>_speed<F×100>.mp4` beside IN (in 03_wip when IN is
  a saved original).
- upload: the copy for the page's download button, `<FINAL stem>_upload.mp4` beside it: H.264 at CRF `qa.upload_crf[0]`
  to `[1]` (26 to 28) with faststart, the first under `qa.upload_max_mb` (15 MB, 10^6 bytes a MB). Still over at the
  last CRF: no copy is kept, the stop is recorded for this final (run.json `checked.upload_over`, its path and sha256,
  which `final_checked` accepts), and exit 2: the video stays a local file.
- preview: `showcase/<IN stem>_720p.mp4`, 720 wide, CRF `qa.preview_crf` (27), faststart, for the gate pages.
- cover: `04_final/kits/<PNG stem>.jpg`, the JPG of the cover for download (`cover_<id>_vNN`, the id in the run's
  spelling).
- nosound: `<FINAL stem>_nosound.mp4` beside it, the picture as it is with no sound track, for a post whose trending
  sound replaces the whole track in the app (PB3 decision 10).
- measure: the integrated loudness (LUFS) and true peak (dBFS) of each file, to set a segment's `volume` in the
  edit's props.

Every output is new: a name that is taken is refused (exit 1), and each file is written under a hidden temporary name
and moved to its own only when complete. Each gets a manifest row. The settings are the run's `qa.*` (config.yaml),
else organic video's defaults.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Callable

from tm import organic_final, stepchecks
from tm.runfolder import READ_ONLY_STAGES, RunFolder
from tm.tools import _common as c
from tm.tools.take_qa import loudness

TRUE_PEAK, LRA = -1.5, 11
LIMITER = "alimiter=limit=0.891:level=0"      # −1 dBFS, no make-up gain: loudnorm sets the level
VIDEO = ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"]
FINAL_CRF = 18
ASPECT_SLACK = 0.02   # 9:16 within 2 %: MiniMax H3's 768×1344 (4:7) and its 1088×1904 upscale are vertical takes
FASTSTART = ["-movflags", "+faststart"]
PREVIEW_WIDTH = 720


def _input(run: RunFolder, text: str, what: str) -> Path:
    path = c.resolve(run, text)
    if not path.is_file():
        raise c.ToolError(f"The {what} {c.name_of(text)} does not exist.")
    return path


def _beside(run: RunFolder, src: Path) -> Path:
    """The folder for a file made from `src`: src's own, unless it is outside the run or a saved original (03_wip)."""
    try:
        parts = src.resolve().relative_to(run.path.resolve()).parts
    except ValueError:
        parts = ()
    return src.parent if len(parts) > 1 and parts[0] not in READ_ONLY_STAGES else run.path / "03_wip"


def _new(run: RunFolder, target: Path) -> Path:
    """`target`, refused when it exists: files are never overwritten."""
    run.assert_writable(target)
    if target.exists():
        raise c.ToolError(f"{c.rel(run, target)} already exists, and files are never overwritten.")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _write(run: RunFolder, target: Path, make: Callable[[Path], None]) -> Path:
    """Make `target` under a hidden temporary name beside it, then move it to its name."""
    part = target.with_name(f".{target.stem}.part{target.suffix}")
    part.unlink(missing_ok=True)
    try:
        make(part)
        if not part.is_file():
            raise c.ToolError(f"ffmpeg finished without writing {target.name}.")
        _new(run, target)    # taken meanwhile: still never overwritten
        c.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return target


def _ffmpeg(args: list[str]) -> None:
    subprocess.run([c.ffmpeg_bin(), "-nostdin", "-hide_banner", "-v", "error", "-y", *args], check=True,
                   capture_output=True)


def _has_audio(path: Path) -> bool:
    return bool(c.probe(path).get("has_audio"))


def _level(lufs: float | None, peak: float | None) -> str:
    if lufs is None:
        return "no sound"
    return f"{lufs:.1f} LUFS, peak {peak:.1f} dBFS" if peak is not None else f"{lufs:.1f} LUFS"


# --- finish -------------------------------------------------------------------------------------------

def final_path(run: RunFolder, given: str) -> Path:
    """The next `04_final/<id>_final_vNN.mp4`, the id the run's own spelling of `given` (`organic_final.idea_named`):
    a plain name, as it is part of every file name."""
    try:
        pid = organic_final.idea_named(run, given)
    except ValueError as exc:
        raise c.ToolError(str(exc)) from None
    return _new(run, run.next_version(organic_final.FINAL, f"{pid}_final", "mp4"))


def cover_name(run: RunFolder, stem: str) -> str:
    """The cover JPG's stem: the PNG's, with the run's spelling of the idea id when it names it (cover_M5_v01 for an
    idea m5 is cover_m5_v01)."""
    pid = organic_final.idea_id(run)
    head = f"cover_{pid}" if pid else None
    if head and stem.casefold().startswith(head.casefold()) and stem[len(head):len(head) + 2].lower() in ("", "_v"):
        return head + stem[len(head):]
    return stem


def _first_pass(src: Path, target: float) -> dict:
    """loudnorm's measure of the limited sound (its print_format=json block)."""
    proc = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-hide_banner", "-nostats", "-v", "info", "-i", c.media(src),
                           "-vn", "-af",
                           f"{LIMITER},loudnorm=I={target:g}:TP={TRUE_PEAK:g}:LRA={LRA}:print_format=json",
                           "-f", "null", "-"], capture_output=True, check=True)
    text = proc.stderr.decode("utf-8", "replace")
    found = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.S)
    if not found:
        raise c.ToolError(f"ffmpeg's loudnorm did not measure {src.name}.")
    measured = json.loads(found[-1])
    if not math.isfinite(float(measured["input_i"])):
        raise c.ToolError(f"{src.name} is silent, so it cannot be levelled to {target:g} LUFS.")
    return measured


def _finish(run: RunFolder, src: Path, out: Path, target: float, measured: dict) -> None:
    m = measured
    norm = (f"{LIMITER},loudnorm=I={target:g}:TP={TRUE_PEAK:g}:LRA={LRA}:measured_I={m['input_i']}:"
            f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true,aresample={organic_final.SAMPLE_RATE}")
    w, h = organic_final.SIZE
    _write(run, out, lambda part: _ffmpeg(
        ["-i", c.media(src), "-map", "0:v:0", "-map", "0:a:0", "-vf", f"scale={w}:{h}:flags=lanczos,setsar=1",
         "-af", norm, *VIDEO, "-crf", str(FINAL_CRF), "-c:a", "aac", "-b:a", "192k",
         "-ar", str(organic_final.SAMPLE_RATE), *FASTSTART, str(part)]))


def _not_vertical(src: Path) -> str | None:
    """`W×H` when the picture is not 9:16 within ASPECT_SLACK (finish scales to 1080×1920 and never stretches)."""
    found = c.probe(src)
    width, height = found.get("width"), found.get("height")
    if not width or not height:
        return "no picture size"
    w, h = organic_final.SIZE
    return None if abs((width / height) / (w / h) - 1) <= ASPECT_SLACK else f"{width}×{height}"


def finish(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    src = _input(run, a.input, "render")
    out = final_path(run, a.id)
    size = _not_vertical(src)
    if size:
        raise c.ToolError(f"{c.name_of(a.input)} is {size}, not 9:16, and a finish never stretches a picture to "
                          "1080×1920. Render the edit at 9:16 (OrganicCaptions renders 1080×1920), and crop a take "
                          "that is not vertical in the edit (its zoom). Nothing was written.")
    if not _has_audio(src):
        raise c.ToolError(f"{c.name_of(a.input)} has no sound, and a final is levelled to its loudness target. A "
                          "video posted with only the in-app trending sound is a final's no-sound export "
                          "(tm tool deliver nosound --run <run> <final>).")
    target = float(organic_final.setting(run, "lufs_asmr" if a.asmr else "lufs_target"))
    measured = _first_pass(src, target)
    _finish(run, src, out, target, measured)
    lufs, peak = loudness(out)
    rel = c.rel(run, out)
    c.record(run, out, "tm tool deliver finish", c.parent_ref(run, src),
             params={"lufs_target": target, "asmr": a.asmr, "lufs": lufs, "peak": peak},
             model="ffmpeg scale (lanczos), alimiter, loudnorm (two passes)", cost="0 (local)",
             request={"action": "finish", "input": c.parent_ref(run, src), "id": out.name.rsplit("_final_v", 1)[0],
                      "lufs_target": target, "asmr": a.asmr},
             response={"first_pass": measured, "lufs": lufs, "peak": peak})
    text = f"Wrote {rel}: 1080×1920, H.264, AAC 48 kHz, {_level(lufs, peak)} (target {target:g} LUFS)."
    if lufs is None or abs(lufs - target) > organic_final.LUFS_SLACK:
        text += " That is more than 1 LU from the target, so the final check will not pass: look at the render's sound."
    return {"outputs": [rel], "lufs": lufs, "peak": peak, "lufs_target": target}, text


# --- speed --------------------------------------------------------------------------------------------

def speed(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    factor, cap = a.factor, float(organic_final.setting(run, "speed_max"))
    if not math.isfinite(factor) or factor <= 1:
        raise c.ToolError(f"--factor speeds a take up: give a number above 1, at most {cap:g} (not {factor:g}).")
    if factor > cap:
        raise c.ToolStop(f"×{factor:g} is faster than this run allows (qa.speed_max, ×{cap:g}): speed the take up at "
                         f"most ×{cap:g}, or redo it with a note. Nothing was written.")
    src = _input(run, a.input, "take")
    out = _new(run, _beside(run, src) / f"{src.stem}_speed{round(factor * 100)}.mp4")
    sound = ["-filter:a", f"atempo={factor:g}", "-c:a", "aac", "-b:a", "192k"] if _has_audio(src) else ["-an"]
    _write(run, out, lambda part: _ffmpeg(["-i", c.media(src), "-filter:v", f"setpts=PTS/{factor:g}", *VIDEO,
                                           "-crf", str(FINAL_CRF), *sound, str(part)]))
    rel = c.rel(run, out)
    c.record(run, out, "tm tool deliver speed", c.parent_ref(run, src), params={"factor": factor},
             model="ffmpeg setpts + atempo (pitch kept)", cost="0 (local)")
    return {"outputs": [rel], "factor": factor}, f"Wrote {rel}: ×{factor:g}, the pitch kept."


# --- upload -------------------------------------------------------------------------------------------

def _encode_upload(src: Path, part: Path, crf: int) -> None:
    _ffmpeg(["-i", c.media(src), "-map", "0:v:0", "-map", "0:a?", *VIDEO, "-crf", str(crf), "-c:a", "copy",
             *FASTSTART, str(part)])


def _size(path: Path) -> int:
    return path.stat().st_size


def upload(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    src = _input(run, a.input, "final")
    out = _new(run, _beside(run, src) / organic_final.upload_of(src).name)
    low, high = (int(v) for v in organic_final.setting(run, "upload_crf"))
    limit = organic_final.setting(run, "upload_max_mb")
    size = 0
    for crf in range(low, high + 1):
        part = out.with_name(f".{out.stem}.part{out.suffix}")
        part.unlink(missing_ok=True)
        try:
            _encode_upload(src, part, crf)
            size = _size(part)
            if size < limit * organic_final.MB:
                _new(run, out)
                c.replace(part, out)
                rel = c.rel(run, out)
                c.record(run, out, "tm tool deliver upload", c.parent_ref(run, src),
                         params={"crf": crf, "mb": round(size / organic_final.MB, 2)},
                         model="ffmpeg libx264 + faststart", cost="0 (local)")
                return ({"outputs": [rel], "crf": crf, "mb": round(size / organic_final.MB, 2)},
                        f"Wrote {rel}: CRF {crf}, {size / organic_final.MB:.2f} MB, under the page's {limit:g} MB.")
        finally:
            part.unlink(missing_ok=True)
    stepchecks.mark(run, organic_final.UPLOAD_OVER, src,
                    extra={"crf": high, "mb": round(size / organic_final.MB, 2), "max_mb": limit})
    raise c.ToolStop(f"The video is too long for the page's {limit:g} MB download; it stays a local file.")


# --- preview, cover, nosound --------------------------------------------------------------------------

def preview_of(run: RunFolder, src: Path) -> Path:
    """Where a video's 720p preview is kept: `showcase/<stem>_720p.mp4`."""
    return run.path / "showcase" / f"{Path(src).stem}_720p.mp4"


def make_preview(run: RunFolder, src: Path) -> Path:
    """The 720p preview of `src` (free, local, never over another file), with its manifest row: what `tm tool deliver
    preview` writes, and what a page build makes itself for a video over the page's limit (issue #90)."""
    out = _new(run, preview_of(run, src))
    crf = int(organic_final.setting(run, "preview_crf"))
    _write(run, out, lambda part: _ffmpeg(
        ["-i", c.media(src), "-map", "0:v:0", "-map", "0:a?", "-vf", f"scale={PREVIEW_WIDTH}:-2:flags=lanczos",
         *VIDEO, "-crf", str(crf), "-c:a", "aac", "-b:a", "128k", *FASTSTART, str(part)]))
    c.record(run, out, "tm tool deliver preview", c.parent_ref(run, src), params={"crf": crf},
             model="ffmpeg libx264", cost="0 (local)")
    return out


def preview(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    src = _input(run, a.input, "video")
    out = make_preview(run, src)
    rel = c.rel(run, out)
    crf = int(organic_final.setting(run, "preview_crf"))
    return {"outputs": [rel]}, f"Wrote {rel}: {PREVIEW_WIDTH} wide, CRF {crf}."


def cover(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    """The cover JPG, made for the run's latest final (its record names it: `organic_final.cover_of`)."""
    src = _input(run, a.input, "cover")
    if src.suffix.lower() != ".png":
        raise c.ToolError(f"{c.name_of(a.input)} is not a PNG: give the cover's PNG (a Remotion still).")
    out = _new(run, run.path / organic_final.KITS / f"{cover_name(run, src.stem)}.jpg")
    pid = organic_final.idea_id(run)
    final = organic_final.final_of(run, pid) if pid else None
    if final is None:
        raise c.ToolError(f"A cover is made for its final, and this run has none yet: make the final first "
                          f"({organic_final.FINISH.format(id=pid or '<the idea id>')}), then the cover. Nothing was "
                          "written.")
    _write(run, out, lambda part: _ffmpeg(["-i", c.media(src), "-frames:v", "1", "-q:v", "2", str(part)]))
    rel, final_rel = c.rel(run, out), c.rel(run, final)
    c.record(run, out, "tm tool deliver cover", c.parent_ref(run, src), model="ffmpeg -q:v 2", cost="0 (local)",
             params={"final": final_rel},
             request={"action": "cover", "input": c.parent_ref(run, src), "final": final_rel})
    return {"outputs": [rel], "final": final_rel}, f"Wrote {rel}, the cover of {final_rel}."


def nosound(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    src = _input(run, a.input, "final")
    out = _new(run, _beside(run, src) / f"{src.stem}_nosound.mp4")
    _write(run, out, lambda part: _ffmpeg(["-i", c.media(src), "-map", "0:v:0", "-c:v", "copy", "-an", *FASTSTART,
                                           str(part)]))
    rel = c.rel(run, out)
    c.record(run, out, "tm tool deliver nosound", c.parent_ref(run, src), model="ffmpeg -an", cost="0 (local)")
    return {"outputs": [rel]}, f"Wrote {rel}: the picture with no sound track."


# --- measure ------------------------------------------------------------------------------------------

def measure(run: RunFolder, a: argparse.Namespace) -> tuple[dict, str]:
    rows = []
    for given in a.files:
        path = _input(run, given, "file")
        lufs, peak = loudness(path)
        rows.append({"file": c.parent_ref(run, path), "lufs": lufs, "peak": peak})
    return {"files": rows}, "\n".join(f"{r['file']}: {_level(r['lufs'], r['peak'])}" for r in rows)


ACTIONS = {"finish": finish, "speed": speed, "upload": upload, "preview": preview, "cover": cover,
           "nosound": nosound, "measure": measure}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tm tool deliver", allow_abbrev=False,
                                description="An organic video's delivery files: final, speed, upload copy, preview, "
                                            "cover, no-sound export, loudness.")
    sub = p.add_subparsers(dest="action", required=True)

    def action(name: str, help_: str, what: str) -> argparse.ArgumentParser:
        s = sub.add_parser(name, help=help_, allow_abbrev=False)
        s.add_argument("--run", required=True, help="the run folder")
        s.add_argument("--json", action="store_true", help="print one JSON object")
        if name == "measure":
            s.add_argument("files", nargs="+", help=what)
        else:
            s.add_argument("input", help=what)
        return s

    f = action("finish", "the final: 1080×1920, H.264, AAC 48 kHz, levelled", "the edit's render")
    f.add_argument("--id", required=True, help="the idea's id (00_raw/proposal.json's; any case, the run's spelling "
                                                "is written)")
    f.add_argument("--asmr", action="store_true", help="level to qa.lufs_asmr (−16) instead of qa.lufs_target")
    action("speed", "a take sped up, the pitch kept", "the take").add_argument(
        "--factor", type=float, required=True, help="above 1, at most qa.speed_max (1.25)")
    action("upload", "the upload copy under the page's download limit", "the final")
    action("preview", "the 720p preview in showcase/", "the video")
    action("cover", "the cover's JPG in 04_final/kits/", "the cover PNG")
    action("nosound", "the final with no sound track", "the final")
    action("measure", "LUFS and true peak per file", "the files")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    payload, text = ACTIONS[a.action](run, a)
    return c.finish(a, {"tool": "deliver", "action": a.action, **payload}, text)


if __name__ == "__main__":
    raise SystemExit(main())
