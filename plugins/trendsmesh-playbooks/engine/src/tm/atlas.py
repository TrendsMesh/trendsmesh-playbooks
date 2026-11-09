"""The Atlas renderer: an animatic page (window.seek, window.DURATION, one canvas) to an MP4 with
its stills, drawn in the user's own Chrome or Edge. Shared by the creative brief and PB03.

    find_browser()                                  the browser render.mjs drives, or None
    render(page, out_mp4, *, fps=24, stills=...)    render.mjs's JSON summary of one render
    storyboard(page, out_dir, *, panels=6)          storyboard.mjs's JSON summary: a storyboard's panels
    layout(page)                                    layout_check.mjs's JSON summary: text too small, text
                                                    outside the safe area, dead bands in a vertical frame

The plugin's second node package (`<plugin>/atlas/`: package.json, its lock and the handoff's
`render.mjs`) is set up the way `tm.render` sets up Remotion, reusing its `_prefix`, `_env` and
`_node_tool`: `setup()` copies package.json and package-lock.json to `<data>/atlas/` and runs
`npm ci` there (puppeteer-core alone: no browser is downloaded). It is the `animatic` tier, which
shares the `video` pixi environment (Node 22): `tm env install animatic --yes` calls it. The
marker file holds the hash of the lock file, so a new lock (a plugin update) runs it again.
render.mjs, storyboard.mjs and layout_check.mjs are copied next to `node_modules` before every
run, so they always match the plugin.

`storyboard` (organic video's storyboard check-in) draws a storyboard page the way the handoff's
`render_storyboard.mjs` does: the page sets `window.STORYBOARD_READY = true`, draws each panel on
a canvas `p1` ... `pN` and gives the contact sheet from `window.makeSheet()` (a data URL);
storyboard.mjs writes `panel_NN.png` and `sheet.png` into the folder. It goes through the same
`need()`, sandbox rule, time limit and process-tree kill as a render.

`layout` checks a play-mode page the way a viewer on a phone meets it (layout_check.mjs says how): every
label at least the build prompt's size, nothing to read outside the safe area or off the frame, no dead band
in a vertical frame. It draws nothing to keep; `tm organic atlas-page` runs it on each module Claude writes.

The browser is the user's: Chrome or Edge on Windows, Chrome, Edge or Chromium on macOS, any of
those on PATH on Linux, and Remotion's headless shell only when the `video` tier set it up. A render
never downloads anything: without the tier, its setup or a browser it stops with the todo. A snap's
Chromium is not used (its confinement keeps it from puppeteer's profile). On Linux, as root or
with the headless shell, Chrome runs without its sandbox (`--no-sandbox`: the page is local and
the plugin's); a sandbox refusal anyway is a stop that says what to install. Every subprocess gets
an argv list, never a shell string; a render that hangs is stopped with all it started.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from tm import envtiers, paths, render as remotion
from tm.stops import AGAIN_SENTENCE
from tm.tools import _common as c

TIER = "animatic"
MARKER = ".setup-done"
PACKAGE = ("package.json", "package-lock.json")
SCRIPT = "render.mjs"
STORYBOARD_SCRIPT = "storyboard.mjs"
LAYOUT_SCRIPT = "layout_check.mjs"
SCRIPTS = (SCRIPT, STORYBOARD_SCRIPT, LAYOUT_SCRIPT)
PANELS = 6                   # a storyboard's panels (FLOWS.md F3: 5-6)
FPS = 24
STILLS = (0.06, 0.3, 0.55, 0.8, 0.95)
LINUX_BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
                  "microsoft-edge-stable")
MAC_BROWSERS = ("Google Chrome.app/Contents/MacOS/Google Chrome", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Chromium.app/Contents/MacOS/Chromium")
WIN_CHROME = "Google/Chrome/Application/chrome.exe"
WIN_EDGE = "Microsoft/Edge/Application/msedge.exe"
_AGAIN = AGAIN_SENTENCE
SHELL_NAMES = ("chrome-headless-shell", "chrome-headless-shell.exe")
TIMEOUT_S = 15 * 60          # one page; LD's take 20-50 s
GRACE_S = 10                 # after SIGTERM, for puppeteer to close its Chrome, before SIGKILL
# What Chrome says when its sandbox cannot run here (root, or no user namespaces for a downloaded binary).
SANDBOX_ERRORS = ("No usable sandbox", "without --no-sandbox", "Running as root without")


def project_dir() -> Path:
    return paths.plugin_root() / "atlas"


def work_dir() -> Path:
    return paths.data_dir() / "atlas"


def lock_hash() -> str:
    pj = project_dir()
    h = hashlib.sha256()
    for name in PACKAGE:
        h.update((pj / name).read_bytes())
    return h.hexdigest()


def setup_done() -> bool:
    try:
        return ((work_dir() / MARKER).read_text(encoding="utf-8").strip() == lock_hash()
                and (work_dir() / "node_modules" / "puppeteer-core" / "package.json").is_file())
    except OSError:
        return False


def setup() -> None:
    """npm ci of puppeteer-core into <data>/atlas, once per lock file. No browser is downloaded."""
    if setup_done():
        return
    work_dir().mkdir(parents=True, exist_ok=True)
    for name in PACKAGE:
        shutil.copyfile(project_dir() / name, work_dir() / name)
    (work_dir() / MARKER).unlink(missing_ok=True)
    remotion._sh([remotion._node_tool("npm"), "ci"], work_dir(), "npm ci (the animatic renderer)")
    (work_dir() / MARKER).write_text(lock_hash(), encoding="utf-8")


# --- the browser ---------------------------------------------------------------------------------

def _exists(path: Path) -> bool:
    return path.is_file()


def _system() -> str:
    """windows, macos or linux (any other POSIX system is looked at as Linux)."""
    if os.name == "nt":
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


def _candidates() -> list[Path]:
    """The places the user's own browser is looked for on this system, in order."""
    system = _system()
    if system == "windows":
        roots = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData")]
        chrome = [Path(r) / WIN_CHROME for r in roots if r]
        return chrome + [Path(r) / WIN_EDGE for r in roots[:2] if r]
    if system == "macos":
        return [root / app for root in (Path("/Applications"), Path.home() / "Applications") for app in MAC_BROWSERS]
    return [Path(found) for name in LINUX_BROWSERS if (found := shutil.which(name)) and not _is_snap(Path(found))]


def _is_snap(path: Path) -> bool:
    """A snap's browser (Ubuntu's `chromium`, and the `chromium-browser` script that starts it): its
    confinement gives it a /tmp of its own, where puppeteer's profile is not, and keeps it out of
    hidden folders, so it cannot draw the animatics."""
    try:
        if "snap" in Path(path).resolve().parts[1:2]:
            return True
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    return head.startswith(b"#!") and b"/snap/" in head


def _headless_shell() -> Path | None:
    """Remotion's Chrome Headless Shell, when the `video` tier set it up."""
    if not remotion.setup_done():
        return None
    shell = remotion.work_dir() / "node_modules" / ".remotion" / "chrome-headless-shell"
    for name in SHELL_NAMES:
        for path in sorted(shell.glob(f"*/chrome-headless-shell-*/{name}")):
            if _exists(path):
                return path
    return None


def find_browser() -> Path | None:
    """The first browser found: the user's Chrome or Edge (Chromium on macOS and Linux), then
    Remotion's headless shell when the `video` tier set it up; None when there is none."""
    return next((p for p in _candidates() if _exists(p)), None) or _headless_shell()


def is_headless_shell(browser: Path) -> bool:
    return Path(browser).name in SHELL_NAMES


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def needs_no_sandbox(browser: Path) -> bool:
    """Linux only: Chrome refuses its sandbox to root, and a downloaded headless shell has neither
    the setuid helper nor the AppArmor profile a packaged Chrome brings (Ubuntu 23.10 and later)."""
    return _system() == "linux" and (_is_root() or is_headless_shell(browser))


# --- render --------------------------------------------------------------------------------------

def missing() -> tuple[str, str, str] | None:
    """What drawing needs and is not there, as (`tier` or `browser`, what is missing, what to do), or None when
    the tier, its setup and a browser are all there: `need()`'s words, which organic video's start and pack check
    say too."""
    if not envtiers.installed(TIER):
        return (TIER, "Drawing animatics needs the 'animatic' tools, which are not installed or not set up yet.",
                "Install them with: tm env install animatic --yes (after the user's yes; about "
                f"{envtiers.TIERS[TIER].approx_mb} MB, no browser)")
    if find_browser() is None:
        return ("browser", "Drawing animatics needs Google Chrome or Microsoft Edge (or Chromium on Linux) on this computer, "
                "and none was found.", "Ask the user to install one (both are free)")
    return None


def need() -> Path:
    """The browser, once the tier, its setup and a browser are all there."""
    gap = missing()
    if gap is not None:
        kind, what, todo = gap
        then = ", then render again" if kind == "browser" else ""
        raise c.ToolStop(f"{what} Nothing was rendered. {todo}{then}. {_AGAIN}")
    return find_browser()


def _sync_script(name: str = SCRIPT) -> Path:
    """render.mjs, storyboard.mjs and layout_check.mjs next to node_modules, so `import "puppeteer-core"` resolves; each copied
    whole, then swapped in. Returns the path of `name`. `name` missing from the plugin is a stop (a damaged
    install, never a stale copy run in its place); the other script is copied when it is there."""
    if not (project_dir() / name).is_file():
        raise c.ToolStop(f"{name} is missing from the plugin ({project_dir()}), so nothing was drawn: the plugin's "
                         f"install is damaged. Ask the user to reinstall or update the plugin. {_AGAIN}")
    work_dir().mkdir(parents=True, exist_ok=True)
    for script in SCRIPTS:
        if not (project_dir() / script).is_file():
            continue
        dest, tmp = work_dir() / script, work_dir() / f".{script}.new"
        shutil.copyfile(project_dir() / script, tmp)
        os.replace(tmp, dest)
    return work_dir() / name


def _summary(stdout: str) -> dict:
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    try:
        data = json.loads(lines[-1]) if lines else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise c.ToolError(f"The animatic renderer finished without its summary line: {(lines or [''])[-1][:200]}")
    return data


def still_paths(out_mp4: Path, stills: tuple[float, ...] = STILLS) -> list[Path]:
    """The stills render.mjs writes beside `out_mp4`: `<stem>_still_NNN.png`, NNN the percent (JS rounding)."""
    out = Path(out_mp4)
    return [out.with_name(f"{out.stem}_still_{math.floor(s * 100 + 0.5):03d}.png") for s in stills]


def _kill_tree(proc: subprocess.Popen) -> None:
    """Stop render.mjs and what it started. On Windows taskkill takes the tree. Elsewhere the process
    group gets SIGTERM first, so puppeteer closes its Chrome (which runs in a group of its own), then
    SIGKILL."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except OSError:
                break
            try:
                proc.wait(timeout=GRACE_S)
                break
            except subprocess.TimeoutExpired:
                continue
    try:
        proc.communicate(timeout=GRACE_S)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass


def _run(argv: list[str], name: str, what: str = "animatic renderer") -> subprocess.CompletedProcess:
    """render.mjs (or storyboard.mjs) in its own process group, killed with all it started after TIMEOUT_S or
    when tm itself is stopped."""
    group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
             else {"start_new_session": True})
    try:
        proc = subprocess.Popen(argv, cwd=work_dir(), env=remotion._env(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **group)
    except OSError as exc:
        raise c.ToolError(f"Could not start the {what}: {exc}") from None
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        raise c.ToolError(f"The {what} did not finish {name} in {TIMEOUT_S // 60} minutes and was "
                          "stopped.") from None
    except BaseException:
        _kill_tree(proc)
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def render(page: Path, out_mp4: Path, *, fps: int = FPS, stills: tuple[float, ...] = STILLS) -> dict:
    """Render `page` to `out_mp4` and its stills (`still_paths`) with render.mjs; returns
    render.mjs's JSON summary (out, duration, frames, size, sound, page_errors ...). Never
    overwrites: an existing `out_mp4` or still is refused. A failed render leaves none of its files."""
    page, out = Path(page).resolve(), Path(out_mp4).resolve()
    if not page.is_file():
        raise c.ToolError(f"The animatic page {page} does not exist.")
    pictures = still_paths(out, stills)
    taken = [p.name for p in (out, *pictures) if p.exists()]
    if taken:
        raise c.ToolError(f"{', '.join(taken)} already exist(s), and files are never overwritten.")
    browser = need()
    script = _sync_script()
    argv = [*remotion._prefix(), "node", str(script), str(page), str(out), "--browser", str(browser),
            "--ffmpeg", c.ffmpeg_bin(), "--fps", str(int(fps)), "--stills", ",".join(f"{s:g}" for s in stills)]
    if needs_no_sandbox(browser):
        argv.append("--no-sandbox")
    c.say(f"Drawing the animatic {out.name} ...")
    parts = [Path(f"{out}.video.mp4"), Path(f"{out}.wav")]   # render.mjs's own in-between files
    ok = False
    try:
        proc = _run(argv, page.name)
        ok = proc.returncode == 0
    finally:
        for part in parts if ok else [*parts, out, *pictures]:   # never a half-written file under a name
            part.unlink(missing_ok=True)
    if not ok:
        _failed(proc, f"The animatic renderer failed on {page.name}")
    return _summary(proc.stdout)


def _failed(proc: subprocess.CompletedProcess, failed: str) -> None:
    """A sandbox refusal is a stop that says what to install; any other failure an error with the output's tail."""
    said = (proc.stderr or proc.stdout or "").strip()
    reason = next((e for e in SANDBOX_ERRORS if e in said), None)
    if reason:
        raise c.ToolStop(f"Chrome would not start on this computer: its sandbox cannot run here (\"{reason}\"). "
                         "Nothing was rendered. Ask the user to install Google Chrome from google.com/chrome "
                         "(its .deb or .rpm package) and to run Claude Code as their normal user, not as root, "
                         f"then render again. {_AGAIN}")
    tail = " | ".join(said.splitlines()[-4:])
    raise c.ToolError(f"{failed}: {tail}")


def panel_paths(out_dir: Path, panels: int = PANELS) -> list[Path]:
    """The files storyboard.mjs writes into `out_dir`: `panel_01.png` ... and `sheet.png`, last."""
    out = Path(out_dir)
    return [out / f"panel_{n:02d}.png" for n in range(1, panels + 1)] + [out / "sheet.png"]


def storyboard(page: Path, out_dir: Path, *, panels: int = PANELS) -> dict:
    """Draw the storyboard `page` into `out_dir` (`panel_paths`) with storyboard.mjs; returns its JSON summary
    (written, sizes, page_errors). Never overwrites: a panel or sheet already there is refused. A failed
    drawing leaves none of its files."""
    page, out = Path(page).resolve(), Path(out_dir).resolve()
    if not page.is_file():
        raise c.ToolError(f"The storyboard page {page} does not exist.")
    if isinstance(panels, bool) or not isinstance(panels, int) or panels < 1:
        raise c.ToolError(f"A storyboard has a whole number of panels above 0, not {panels!r}.")
    targets = panel_paths(out, panels)
    taken = [p.name for p in targets if p.exists()]
    if taken:
        raise c.ToolError(f"{', '.join(taken)} already exist(s) in {out}, and files are never overwritten.")
    browser = need()
    script = _sync_script(STORYBOARD_SCRIPT)
    argv = [*remotion._prefix(), "node", str(script), str(page), str(out), "--browser", str(browser),
            "--panels", str(panels)]
    if needs_no_sandbox(browser):
        argv.append("--no-sandbox")
    c.say(f"Drawing the storyboard {out.name} ({panels} panels) ...")
    ok = False
    try:
        proc = _run(argv, page.name, "storyboard renderer")
        ok = proc.returncode == 0
    finally:
        if not ok:
            for part in targets:                      # never a half-drawn storyboard under its names
                part.unlink(missing_ok=True)
    if not ok:
        _failed(proc, f"The storyboard renderer failed on {page.name}")
    return _summary(proc.stdout)


def layout(page: Path) -> dict:
    """Check the play-mode `page` with layout_check.mjs; returns its JSON summary: `small` (labels below the
    prompt's size at a moment they are settled on screen), `outside` (text standing outside the safe area or off the
    frame's sides), `empty` (dead bands in a vertical frame), `texture` (strings drawn as texture),
    `min_label_px`, `size`, `page_errors`. Writes nothing."""
    page = Path(page).resolve()
    if not page.is_file():
        raise c.ToolError(f"The animation page {page} does not exist.")
    browser = need()
    script = _sync_script(LAYOUT_SCRIPT)
    argv = [*remotion._prefix(), "node", str(script), str(page), "--browser", str(browser)]
    if needs_no_sandbox(browser):
        argv.append("--no-sandbox")
    c.say(f"Checking the layout of {page.name} ...")
    proc = _run(argv, page.name, "layout check")
    if proc.returncode != 0:
        _failed(proc, f"The layout check failed on {page.name}")
    return _summary(proc.stdout)


def layout_problems(summary: dict) -> list[str]:
    """The layout check's findings as short sentences for Claude to fix, most useful first; [] when clean."""
    out: list[str] = []
    small, outside, empty = (summary.get(k) or [] for k in ("small", "outside", "empty"))
    want = summary.get("min_label_px")
    for r in small[:8]:
        out.append(f"\"{r.get('text')}\" is at most {r.get('px')} px; labels need at least {want} px")
    for r in outside[:8]:
        out.append(f"\"{r.get('text')}\" stands outside the safe area ({', '.join(r.get('side') or [])}) "
                   f"at {r.get('t')} s")
    for r in empty[:6]:
        out.append(f"at {r.get('t')} s the frame is empty from y {r.get('from')} to {r.get('to')} px: fill it")
    for e in (summary.get("page_errors") or [])[:3]:
        out.append(f"page error: {e}")
    more = len(small) + len(outside) + len(empty) - min(len(small), 8) - min(len(outside), 8) - min(len(empty), 6)
    if more > 0:
        out.append(f"and {more} more")
    return out
