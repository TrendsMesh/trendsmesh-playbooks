"""tm render: text cards and word-by-word captions over the original ad, and organic video's edit, with Remotion.

    tm render still --run RUN --comp <composition> --props FILE --frame N [--out PATH] [--json]
    tm render video --run RUN --comp <composition> --props FILE [--out PATH] [--json]

HookSwap and WordCaptions are refresh-ad's. OrganicCaptions is the handoff's organic edit (playbook 03, FLOWS.md G1):
source segments cut back to back, the native sound kept per segment with `keepAudio`, an optional music bed and
voice tracks, and native-style captions inside the platforms' common safe zone. Its loudness is levelled after
the render by `tm tool deliver finish`. The handoff's motion graphics (`MOTION_COMPS`, FLOWS.md F4): `QuizGrid` (a "Guess the
_" quiz: its `options[].img` pictures in a 2×2 grid, a countdown, the reveal, an optional `music`), `RankingList` and
`RankingSplit` (a countdown ranking: one clip per `items[].src`, cut back to back and muted; RankingSplit is the look
copied from the evidence, lesson 21).

Remotion (free for individuals and companies of up to 3 people, see remotion.pro/license) runs on
the user's machine in the `video` environment (Node 22). The project lives in the plugin
(`<plugin>/remotion/`), but the plugin root changes per version, so `node_modules` never goes there:

- `setup()` copies package.json and package-lock.json to `<data>/remotion/`, runs `npm ci` there and
  `npx remotion browser ensure` (Chrome Headless Shell, about 0.5 GB with Node). It is part of the
  `video` tier: `tm env install video --yes` calls it. It runs once; the marker file holds the hash
  of the lock file, and a new lock file (a plugin update) means running it again.
- `src/` is copied next to `node_modules` before every render (it is small), so the source always
  matches the plugin version and module resolution finds the packages.
- A render never downloads anything: when the setup is missing it stops (exit 2) with the todo.

The run folder is Remotion's `--public-dir`, so props paths like `01_base/ad3_original.mp4`
resolve (OrganicCaptions' segment, music and voice files the same way). Outputs go to the next
free version in `03_wip` (never overwritten), with a manifest row whose params are the props and
whose source is the props file. Rendering is free: no budget.
The ending card is a HookSwap card whose from/to lie in the last seconds; there is no extra composition.
Fonts follow the market language (`video_fonts`, issue 3): every composition takes a `language` prop (BCP 47) and
loads the Google Fonts subsets its script needs, or a Noto Sans fallback for the whole composition when its own font
lacks them. When the props give no `language`, the run's market language is filled in (Remotion reads a filled-in
copy of the props; the file stays as written), and the render stops before Remotion starts when a letter on screen
is outside the chosen font's subsets.
Every subprocess gets an argv list, never a shell string. Exit codes: 0 done, 2 stop, 1 error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from tm import cli, envtiers, paths, video_fonts
from tm.runfolder import RunFolder
from tm.tools import _common as c

Comp = Literal["HookSwap", "WordCaptions", "OrganicCaptions", "RankingList", "RankingSplit", "QuizGrid"]
COMPS = ("HookSwap", "WordCaptions", "OrganicCaptions", "RankingList", "RankingSplit", "QuizGrid")
MOTION_COMPS = ("RankingList", "RankingSplit", "QuizGrid")   # organic video's motion graphics (stills with motion)
# Card styles HookSwap.tsx draws (the `style` of each card). Keep in step with CardStyle there.
CARD_STYLES = ("box", "outlineBar")
MARKER = ".setup-done"


def project_dir() -> Path:
    return paths.plugin_root() / "remotion"


def work_dir() -> Path:
    return paths.data_dir() / "remotion"


def lock_hash() -> str:
    pj = project_dir()
    h = hashlib.sha256()
    for name in ("package.json", "package-lock.json"):
        h.update((pj / name).read_bytes())
    return h.hexdigest()


def fonts_dir() -> Path:
    """The installed @remotion/google-fonts modules, whose character ranges the font check reads."""
    return work_dir() / video_fonts.PACKAGE


def setup_done() -> bool:
    marker = work_dir() / MARKER
    try:
        return (marker.read_text(encoding="utf-8").strip() == lock_hash()
                and (work_dir() / "node_modules" / ".remotion" / "chrome-headless-shell" / "VERSION").is_file())
    except OSError:
        return False


def _is_windows() -> bool:
    return os.name == "nt"


def _node_tool(name: str) -> str:
    """npm and npx are `.cmd` shims on Windows, which a process started from an argv list does not
    find by their bare name. Inside the pixi environment they are always on PATH, so on Windows the
    explicit `npm.cmd` / `npx.cmd` is used (no cmd.exe, no shell string); elsewhere the bare name."""
    return f"{name}.cmd" if _is_windows() else name


def _prefix() -> list[str]:
    """What starts a command in the `video` environment (Node 22)."""
    return [str(paths.pixi_bin()), "run", "--as-is", "--manifest-path",
            str(paths.plugin_root() / "env" / "pixi.toml"), "-e", envtiers.TIERS["video"].env]


def _env() -> dict[str, str]:
    return {**paths.child_environ(dict(os.environ)), **paths.pixi_env()}


def _sh(argv: list[str], cwd: Path, what: str) -> None:
    try:
        proc = subprocess.run([*_prefix(), *argv], cwd=cwd, env=_env(), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as exc:
        raise c.ToolError(f"Could not start {what}: {exc}") from None
    if proc.returncode != 0:
        tail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-4:])
        raise c.ToolError(f"{what} failed: {tail}")


def _tree_hash(folder: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in folder.rglob("*") if p.is_file()):
        h.update(f.relative_to(folder).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _sync_src() -> None:
    """Make <data>/remotion/src equal the plugin's src: skipped when unchanged, otherwise copied to
    a temp folder and swapped in, so a render never sees a half-copied tree."""
    src = project_dir() / "src"
    dest = work_dir() / "src"
    if dest.is_dir() and _tree_hash(dest) == _tree_hash(src):
        return
    tmp, old = work_dir() / ".src.new", work_dir() / ".src.old"
    for leftover in (tmp, old):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(src, tmp)
    if dest.exists():
        os.replace(dest, old)
    os.replace(tmp, dest)
    shutil.rmtree(old, ignore_errors=True)


def setup() -> None:
    """npm ci into <data>/remotion and fetch the headless browser, once per lock file."""
    if setup_done():
        return
    work_dir().mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(project_dir() / name, work_dir() / name)
    (work_dir() / MARKER).unlink(missing_ok=True)
    _sh([_node_tool("npm"), "ci"], work_dir(), "npm ci (Remotion packages)")
    _sync_src()
    _sh([_node_tool("npx"), "remotion", "browser", "ensure"], work_dir(), "Remotion browser setup")
    (work_dir() / MARKER).write_text(lock_hash(), encoding="utf-8")


def _need_setup() -> None:
    """The doctor's check (`envtiers.installed`); when it fails, the stop says which part is missing."""
    if envtiers.installed("video"):
        return
    if not envtiers._env_installed(envtiers.TIERS["video"].env):
        raise c.ToolStop("Rendering needs the 'video' tools, which are not installed yet. Nothing was "
                         "rendered. Install them with: tm env install video --yes (it asks before "
                         "downloading about 0.5 GB). The run continues from the same place.")
    raise c.ToolStop("The 'video' tools are installed but the Remotion part is not set up (or is "
                     "out of date). Nothing was rendered. Set it up with: tm env install video --yes "
                     "(after the user's yes; it downloads the packages and a headless browser). "
                     "The run continues from the same place.")


def _check_props(run: RunFolder, comp: str, props: Path) -> dict:
    if comp not in COMPS:
        raise c.ToolError(f"Unknown composition '{comp}'. Choose one of: {', '.join(COMPS)}.")
    try:
        data = json.loads(Path(props).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise c.ToolError(f"The props file {props} cannot be read as JSON: {exc}") from None
    if not isinstance(data, dict):
        raise c.ToolError(f"The props file {props} must hold one JSON object.")
    if "language" in data and not video_fonts.language_tag(data["language"]):
        raise c.ToolError(f"The props' language must be a language tag such as pl, uk or zh-Hant (or left out: "
                          f"the run's market language is used), not {data['language']!r}.")
    if comp == "HookSwap":
        for card in data.get("cards") or []:
            style = card.get("style") if isinstance(card, dict) else None
            if style is not None and style not in CARD_STYLES:
                raise c.ToolError(f"The props give a card style '{style}', which HookSwap does not have. "
                                  f"Choose one of: {', '.join(CARD_STYLES)}.")
    files = [data.get("base")] + [i.get("src") for i in data.get("inserts") or [] if isinstance(i, dict)]
    shapes = {"OrganicCaptions": ("segments", "audioTracks", "music"), "QuizGrid": ("options", "music"),
              "RankingList": ("items",), "RankingSplit": ("items",)}.get(comp, ())
    for key in shapes:
        kind, words = (dict, "one object") if key == "music" else (list, "a list")
        if data.get(key) is not None and not isinstance(data[key], kind):
            raise c.ToolError(f"The props' {key} must be {words} (or left out), not {type(data[key]).__name__}.")
    music = data.get("music") if "music" in shapes else None
    named = [*(data.get(k) or [] for k in shapes if k != "music")]
    files += [s.get("img" if comp == "QuizGrid" else "src") for group in named for s in group if isinstance(s, dict)]
    files += [music.get("src")] if music else []
    for rel_path in files:
        if isinstance(rel_path, str) and (
                PurePosixPath(rel_path.replace("\\", "/")).is_absolute() or PureWindowsPath(rel_path).drive
                or ".." in PurePosixPath(rel_path.replace("\\", "/")).parts):
            raise c.ToolError(f"The props name {rel_path}, which must be a path inside the run folder "
                              "(no absolute path, no '..').")
        if isinstance(rel_path, str) and not (run.path / rel_path).is_file():
            raise c.ToolError(f"The props name {rel_path}, which is not in the run folder {run.path}.")
    return data


def _organic(run: RunFolder) -> bool:
    from tm import state
    from tm.playbooks import ORGANIC_VIDEO

    return state.load(run).playbook == ORGANIC_VIDEO


def _render(run: RunFolder, kind: str, comp: str, props: Path, out: Path, extra: list[str], params: dict) -> Path:
    props, out = Path(props).resolve(), Path(out)
    data = _check_props(run, comp, props)
    run.assert_writable(out)
    if out.exists():
        raise c.ToolError(f"{out.name} already exists, and files are never overwritten.")
    _need_setup()
    data, props_arg = _with_language(run, comp, data, props)
    out.parent.mkdir(parents=True, exist_ok=True)
    _sync_src()
    c.say(f"Rendering {comp} ({kind}) ...")
    # Render to a hidden temp name in the same folder (same extension, so Remotion picks the codec)
    # and move it to the versioned name only when it is complete: no partial file ever carries a name.
    part = out.with_name(f".{out.stem}.part{out.suffix}")
    part.unlink(missing_ok=True)
    try:
        _sh([_node_tool("npx"), "remotion", kind, "src/index.ts", comp, str(part.resolve()), f"--props={props_arg}",
             f"--public-dir={run.path.resolve()}", "--log=warn", *extra], work_dir(), f"remotion {kind}")
        if not part.is_file():
            raise c.ToolError(f"Remotion finished but {out.name} was not written.")
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
        if props_arg != props:
            props_arg.unlink(missing_ok=True)
    if _organic(run):   # what an organic render is made under (PR D review M1): its F2 and the pages read it
        from tm import organic_qa   # it imports this module

        params = {**params, "made_under": organic_qa.made_under(run, comp, data)}
    c.record(run, out, str(props), c.parent_ref(run, run.path / data["base"]) if isinstance(data.get("base"), str) else None,
             params={"composition": comp, **params, "props": data}, model=f"remotion {kind}",
             request={"props_file": str(props), "composition": comp, **params})
    return out


def _with_language(run: RunFolder, comp: str, data: dict, props: Path) -> tuple[dict, Path]:
    """(the props with their `language`, the props file Remotion reads). The language is the props' own, else
    the run's market language (`video_fonts.market_language`); the fonts are checked to cover the on-screen text
    for it (a Stop otherwise). When the language is filled in, Remotion reads a copy of the props in the data
    folder, removed after the render; the props file stays as written."""
    if "language" in data:
        language, source = video_fonts.language_tag(data["language"]), "the props"
    else:
        language, source = video_fonts.market_language(run)
    video_fonts.check(comp, data, language, fonts_dir(), source)
    if not language or data.get("language") == language:
        return data, props
    data = {**data, "language": language}
    filled = work_dir() / f".props-{os.getpid()}-{props.stem}.json"
    filled.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, filled


def still(run: RunFolder, comp: Comp, props: Path, frame: int, out: Path) -> Path:
    """One frame of a composition as a PNG."""
    return _render(run, "still", comp, props, out, [f"--frame={int(frame)}"], {"frame": int(frame)})


def video(run: RunFolder, comp: Comp, props: Path, out: Path) -> Path:
    """The whole composition as an H.264 MP4."""
    return _render(run, "render", comp, props, out, ["--codec=h264"], {})


# CLI ---------------------------------------------------------------------------------------

def _setup_cli(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="kind", metavar="still|video")
    for name in ("still", "video"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--comp", required=True, choices=COMPS)
        s.add_argument("--props", required=True, help="the props JSON file")
        s.add_argument("--out", default=None, help="output path relative to the run folder (default: next version)")
        s.add_argument("--json", action="store_true")
        if name == "still":
            s.add_argument("--frame", type=int, required=True)


def _run_cli(a: argparse.Namespace) -> int:
    if not a.kind:
        print(f"Use: tm render still|video --run RUN --comp {'|'.join(COMPS)} --props FILE [--frame N] [--out PATH] [--json]")
        return 1
    try:
        run = c.open_run(a.run)
        stem = c.stem_of(Path(a.props).name.removesuffix(".json").removesuffix(".props"))
        if a.kind == "still":
            out = c.output(run, a.out, "wip", f"{stem}_{a.comp.lower()}_frame{a.frame}", "png")
            done = still(run, a.comp, Path(a.props), a.frame, out)
        else:
            out = c.output(run, a.out, "wip", f"{stem}_{a.comp.lower()}", "mp4")
            done = video(run, a.comp, Path(a.props), out)
        return c.finish(a, {"tool": "render", "kind": a.kind, "outputs": [c.rel(run, done)]},
                        f"Rendered {c.rel(run, done)}.")
    except c.ToolStop as exc:
        return c._fail(a.json, "stop", str(exc), 2)
    except (c.ToolError, ValueError, OSError, RuntimeError) as exc:
        return c._fail(a.json, "error", str(exc), 1)


cli.register("render", _setup_cli, _run_cli)
