"""ffmpeg: the plugin's own ffmpeg for the edits no other tool makes (free, base tier).

    tm tool ffmpeg --run RUN (--out PATH | --name STEM --ext EXT [--stage 03_wip])
                   [--parent PATH] [--json] -- <ffmpeg inputs, filters and options>

For exact frames (the last frame of a clip, lesson 13), cuts and joins (D4), the voiceover mix
(flow V, V5), previews under 30 MB and masters. The arguments after `--` are passed to ffmpeg as
an argv list, in the run folder (so run-relative paths work), with `-n`: ffmpeg never overwrites
a file, and `-y` is refused. Network inputs and outputs (any argument with `://`) are refused:
files are never fetched from or sent to a host. **One output only:** `--out` (a new path inside
the run folder) or the next version of `<stage>/<STEM>_vNN.<EXT>` (`--stage` is one of the run
folder's stages); the tool adds it as the last argument and records it in the manifest with the
arguments as its parameters. Another output cannot be named: an argument other than an input
after `-i` that is absolute or leads out of the run folder is refused, and so are the options
that write files of their own (`-report`, `-vstats`, `-vstats_file`, `-passlogfile`,
`-progress`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

from tm.runfolder import STAGES
from tm.tools import _common as c

OVERWRITE = ("-y",)
SIDE_FILES = ("-report", "-vstats", "-vstats_file", "-passlogfile", "-progress")  # write files of their own


def _outside(run_path: Path, arg: str) -> bool:
    """An argument (not an input after -i) that names a place outside the run folder."""
    if PurePosixPath(arg).is_absolute() or PureWindowsPath(arg).is_absolute() or PureWindowsPath(arg).drive:
        return True
    if ".." in PurePosixPath(arg.replace("\\", "/")).parts:
        try:
            (run_path / arg).resolve().relative_to(run_path.resolve())
        except ValueError:
            return True
    return False


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("ffmpeg", "Run the plugin's ffmpeg in the run folder; one new output, never overwriting.")
    p.add_argument("--name", help="output name without version (with --ext; default stage 03_wip)")
    p.add_argument("--ext", help="output extension, e.g. mp4, png, wav")
    p.add_argument("--stage", default="03_wip", choices=STAGES,
                   help="the stage folder for --name (default 03_wip)")
    p.add_argument("--parent", help="the input this output is made from (manifest parent)")
    p.add_argument("args", nargs="*", help="ffmpeg arguments, after --")
    a = p.parse_args(argv)
    bad = [x for x in a.args if x in OVERWRITE]
    if bad:
        raise c.ToolError("-y is refused: files are never overwritten. Leave it out.")
    if any("://" in x for x in a.args):
        raise c.ToolError("Network addresses (://) are refused: use files in the run folder. Nothing was run.")
    if not a.args:
        raise c.ToolError("Give the ffmpeg arguments after --, e.g. -- -i 03_wip/clip.mp4 -frames:v 1.")
    side = [x for x in a.args if x.split("=", 1)[0] in SIDE_FILES]
    if side:
        raise c.ToolError(f"{side[0]} writes a file of its own and is refused: one output only. Nothing was run.")
    run = c.open_run(a.run)
    after_i = {i + 1 for i, x in enumerate(a.args) if x == "-i"}
    outside = [x for i, x in enumerate(a.args) if i not in after_i and _outside(run.path, x)]
    if outside:
        raise c.ToolError(f"{outside[0]} is outside the run folder: the only output is the one the tool "
                          "names (--out or --name). Nothing was run.")
    if not a.out and not (a.name and a.ext):
        raise c.ToolError("Name the output: --out <new path in the run folder>, or --name and --ext.")
    target = c.output(run, a.out, a.stage, c.stem_of(a.name or "out"), (a.ext or "").lstrip("."))
    argv_ff = [c.ffmpeg_bin(), "-nostdin", "-hide_banner", "-v", "error", "-n", *a.args, c.media(target)]
    try:
        subprocess.run(argv_ff, cwd=run.path, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        target.unlink(missing_ok=True)  # a half-written output never stays at a versioned name
        raise
    if not target.is_file():
        raise c.ToolError("ffmpeg finished without writing the output.")
    c.record(run, target, "ffmpeg (tm tool ffmpeg)", a.parent, params={"args": a.args})
    out = c.rel(run, target)
    return c.finish(a, {"tool": "ffmpeg", "outputs": [out]}, f"Wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
