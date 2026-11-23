"""Toolchain tiers. Each tier is a pixi environment installed only after a yes.

Ruling 25: the manifest stays in the plugin root. pixi keys a detached environment on the
manifest's path, and that path changes with every plugin version, so each version installs its
tiers again (mostly from pixi's package cache) into a new `<data>/envs/<name>-<hash>/` folder.
`clean` removes the folders whose manifest is gone, and (issue #161) an earlier version's copy of each tier this
version has installed: Claude Code keeps the old version's folder in its cache, so "the manifest is gone" alone
removed nothing after an update. `tm env status`, `tm env install` (before and after the install) and the doctor
run it, and say the space freed. `earlier_install` tells the doctor that a missing tier was installed for an
earlier version, so the card can say why it downloads again. pixi's own output goes to a log
(`<data>/install-env-<tier>.log`); only a failure shows its last lines.

On Windows (issue #123) the pixi environments hold only ffmpeg and node, and a tier whose tools run Python
(`paths.WIN_VENVS`) also needs its venv on python.org's signed Python: `tm env install` makes it after
`pixi install` (bootstrap/install-python.ps1), `installed` asks for its marker, and `clean_stale` removes the venvs
of plugin versions that are gone.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tm import cli, i18n, paths


@dataclass(frozen=True)
class Tier:
    name: str
    env: str
    needs: list[str] = field(default_factory=list)
    approx_mb: int = 0
    outputs: set[str] = field(default_factory=set)


TIERS: dict[str, Tier] = {
    "base": Tier("base", "base", [], 500, {"creative_brief", "edited_video", "ai_video", "live_test"}),
    "breakdown": Tier("breakdown", "breakdown", ["base"], 2500, {"creative_brief", "edited_video", "ai_video"}),
    "video": Tier("video", "video", ["base"], 500, {"edited_video"}),
    "voice": Tier("voice", "voice", ["base"], 1000, set()),
    "ai": Tier("ai", "ai", ["base"], 20, {"ai_video"}),
    # The animatic renderer (tm/atlas.py): puppeteer-core in the `video` environment's Node, and the
    # user's own browser. Its output is creative brief's briefs (the animatics on request, issue #145), which takes
    # tiers from requirements.yaml.
    "animatic": Tier("animatic", "video", ["base"], 150, {"briefs"}),
    # Optional (issue 57): RapidOCR reads the teardown's unsure text rows. No output needs it, so no route asks for
    # it: the teardown says when it would help and the playbook offers it once. About 110 MB to download.
    "ocr": Tier("ocr", "ocr", ["base"], 350, set()),
}


def tiers_for(outputs: set[str], voice: bool) -> list[str]:
    """Tier names needed for the chosen outputs, in install order."""
    wanted = {name for name, t in TIERS.items() if t.outputs & set(outputs)}
    if voice:
        wanted |= {"voice", "ai"}
    return [name for name in TIERS if name in wanted]


def _manifest() -> Path:
    return paths.plugin_root() / "env" / "pixi.toml"


def _pixi_env() -> dict[str, str]:
    return {**paths.child_environ(dict(os.environ)), **paths.pixi_env()}


def installed(tier: str) -> bool:
    """True when pixi reports a prefix for the tier's environment that holds pixi's
    conda-meta/pixi marker (written only after an install finished). The video tier also needs
    the Remotion packages and headless browser for this lock file (`render.setup_done`), the
    animatic tier its node package (`atlas.setup_done`): `tm env install` sets both up, and this
    one check is what the doctor and the renderers ask."""
    if not _env_installed(TIERS[tier].env):
        return False
    if paths.is_windows() and TIERS[tier].env in paths.WIN_VENVS and not venv_installed(TIERS[tier].env):
        return False
    if tier == "video":
        from tm import render

        return render.setup_done()
    if tier == "animatic":
        from tm import atlas

        return atlas.setup_done()
    return True


def _env_installed(env: str) -> bool:
    try:
        proc = subprocess.run(
            [str(paths.pixi_bin()), "info", "--json", "--manifest-path", str(_manifest())],
            env=_pixi_env(), capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if proc.returncode != 0:
            return False
        for info in json.loads(proc.stdout).get("environments_info", []):
            if info.get("name") == env and info.get("prefix"):
                return (Path(info["prefix"]) / "conda-meta" / "pixi").is_file()
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return False


def venv_installed(env: str) -> bool:
    """Windows (issue #123): the environment's venv is finished (its marker, written last by
    bootstrap/install-python.ps1) and was filled from the requirements file this plugin version ships."""
    try:
        venv = paths.venv_dir(env)
        marker = json.loads((venv / paths.VENV_MARKER).read_text(encoding="utf-8-sig"))
        wanted = hashlib.sha256(paths.win_requirements(env).read_bytes()).hexdigest()
    except (OSError, ValueError, RuntimeError):
        return False
    return (isinstance(marker, dict) and marker.get("requirements_sha256") == wanted
            and (venv / "Scripts" / "python.exe").is_file())


def _install_venv(env: str) -> tuple[int, str]:
    """Windows: make the environment's venv with bootstrap/install-python.ps1 (python.org's Python, its signature
    checked, then pip with every file's hash). What it prints goes to its log; a failure is its one line."""
    script = paths.plugin_root() / "bootstrap" / "install-python.ps1"
    env_vars = {**paths.child_environ(dict(os.environ)), "CLAUDE_PLUGIN_ROOT": str(paths.plugin_root()),
                "CLAUDE_PLUGIN_DATA": str(paths.data_dir())}
    try:
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                               "-Tier", env, "-Report"], env=env_vars, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as exc:
        return 1, f"Could not start the Python installer: {exc}"
    if proc.returncode != 0:
        why = " ".join((proc.stderr or proc.stdout or "").split())[:600] or f"exit code {proc.returncode}"
        return 1, f"The Python packages of the '{env}' tools did not install. The reason: {why}"
    return 0, ""


# An earlier version's folder changed this recently may still run in another session (issue #161): its environments
# wait for a later clean.
IN_USE_S = 600
_GOING = ".removing-"   # a folder renamed for removal; a clean cut short leaves it, and the next one finishes it


@dataclass
class Cleaned:
    """What `clean` removed, and the bytes that freed (a file pixi linked from its package cache frees nothing)."""
    removed: list[Path] = field(default_factory=list)
    freed_bytes: int = 0

    @property
    def freed_mb(self) -> int:
        return _mb(self.freed_bytes)


def _mb(size: int) -> int:
    return round(size / 1_000_000)


def _manifest_of(marker: Path) -> str | None:
    """The manifest a finished pixi environment (its conda-meta/pixi marker) was made for; None when unreadable."""
    try:
        value = json.loads(marker.read_text(encoding="utf-8-sig"))["manifest_path"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return value if isinstance(value, str) and value else None


def _same(a: str | Path, b: str | Path) -> bool:
    try:
        return (os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
                or Path(a).resolve() == Path(b).resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def _folders(root: Path) -> list[Path]:
    """The folders right under `root`: never a link (it may point outside the data folder), never one going."""
    try:
        return sorted(p for p in root.iterdir()
                      if p.is_dir() and not p.is_symlink() and not p.name.startswith(_GOING))
    except OSError:
        return []


def _inside(path: Path, base: Path) -> bool:
    """`path` is a real folder inside `base` (the plugin's data folder's envs/ or venvs/), not `base` itself."""
    try:
        real, top = path.resolve(), base.resolve()
    except (OSError, RuntimeError):
        return False
    return not path.is_symlink() and real != top and real.is_relative_to(top)


def _in_use(root: str | Path) -> bool:
    """The plugin root changed in the last IN_USE_S seconds: a session may still run that version."""
    try:
        return time.time() - Path(root).stat().st_mtime < IN_USE_S
    except OSError:
        return False


def _freed_by(folder: Path) -> int:
    """The bytes removing `folder` frees: its files, a hard-linked one only when all its links are inside."""
    total, linked = 0, {}
    for top, _dirs, files in os.walk(folder, followlinks=False):
        for name in files:
            try:
                st = os.lstat(os.path.join(top, name))
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if st.st_nlink <= 1 or not st.st_ino:
                total += st.st_size
                continue
            seen = linked.setdefault((st.st_dev, st.st_ino), [st.st_size, st.st_nlink, 0])
            seen[2] += 1
    return total + sum(size for size, links, inside in linked.values() if inside >= links)


def _remove(path: Path, base: Path, got: Cleaned, listed: bool = True) -> bool:
    """Remove `path`, a folder inside `base`, never anything outside it. It is renamed first: on Windows a folder
    whose files a running tool holds open cannot be renamed, so it is kept whole instead of half removed."""
    if not _inside(path, base):
        return False
    size = _freed_by(path)
    going = base / f"{_GOING}{uuid.uuid4().hex[:12]}"
    try:
        path.rename(going)
    except OSError:
        return False
    shutil.rmtree(going, onerror=_force)
    if going.exists():
        return False   # the rest goes with the next clean
    got.freed_bytes += size
    if listed:
        got.removed.append(path)
    return True


def _finish(base: Path, got: Cleaned) -> None:
    """The folders an earlier clean renamed but could not remove whole."""
    try:
        left = [p for p in base.iterdir() if p.name.startswith(_GOING) and p.is_dir() and not p.is_symlink()]
    except OSError:
        return
    for folder in left:
        size = _freed_by(folder)
        shutil.rmtree(folder, onerror=_force)
        if not folder.exists():
            got.freed_bytes += size


def _done_here(env: str, here: Path, folders: list[Path]) -> bool:
    """This plugin version has finished `env`: its pixi environment, and on Windows its venv too."""
    if not any(_same(m, here) for f in folders if (m := _manifest_of(f / "envs" / env / "conda-meta" / "pixi"))):
        return False
    return not (paths.is_windows() and env in paths.WIN_VENVS) or venv_installed(env)


def earlier_install(tier: str) -> bool:
    """True when the tier's environment was installed for another plugin version (an earlier one, still on disk):
    a finished pixi environment of it made for another manifest, or (Windows) a finished venv of it with another
    plugin root's key. The doctor then says that the update sets the tier up once more (issue #161)."""
    env = TIERS[tier].env
    try:
        here, data = _manifest(), paths.data_dir()
        mine = f"{env}-{paths.venv_key(paths.plugin_root())}"
    except RuntimeError:
        return False
    for folder in _folders(data / "envs"):
        made_for = _manifest_of(folder / "envs" / env / "conda-meta" / "pixi")
        if made_for and not _same(made_for, here):
            return True
    return any(v.name != mine and v.name.rpartition("-")[0] == env and (v / paths.VENV_MARKER).is_file()
               for v in _folders(paths.venvs_dir()))


def clean() -> Cleaned:
    """Remove what earlier plugin versions installed, inside the plugin's data folder only:
    - a folder under `<data>/envs` whose every finished environment (conda-meta/pixi) names a manifest that no
      longer exists, and each venv under `<data>/venvs` whose marker names a plugin root that is gone;
    - (issue #161) once this version has finished a tier's environment (`_done_here`), the copies of that
      environment another plugin root made, and on Windows its venvs with another root's key: right after an update
      Claude Code still keeps the old version's folder, so the rule above removes nothing. A root changed in the last
      IN_USE_S seconds is kept (a session may still run it), and a folder whose last environment went goes too.
    An environment or venv with no marker may be an install under way: kept. Cheap: directory listings, a few small
    files, and a walk of what is removed (its size, counted before)."""
    got = Cleaned()
    try:
        data = paths.data_dir()
    except RuntimeError:
        return got
    try:
        here: Path | None = _manifest()
    except RuntimeError:
        here = None
    base = data / "envs"
    _clean_venvs(here, got)
    _finish(base, got)
    kept = []
    for folder in _folders(base):
        manifests = [_manifest_of(m) for m in folder.glob("envs/*/conda-meta/pixi")]
        gone = manifests and all(m is not None and not Path(m).exists() and not (here and _same(m, here))
                                 for m in manifests)
        if gone and _remove(folder, base, got):
            continue
        kept.append(folder)
    if here is None:
        return got
    emptied = set()
    for env in dict.fromkeys(t.env for t in TIERS.values()):
        if not _done_here(env, here, kept):
            continue
        for folder in kept:
            made_for = _manifest_of(folder / "envs" / env / "conda-meta" / "pixi")
            if made_for and not _same(made_for, here) and not _in_use(Path(made_for).parent.parent) \
                    and _remove(folder / "envs" / env, base, got):
                emptied.add(folder)
    for folder in sorted(emptied):
        try:
            left = any((folder / "envs").iterdir())
        except OSError:
            left = True
        if not left:
            _remove(folder, base, got, listed=False)
    return got


def clean_stale() -> list[Path]:
    """`clean`, the folders it removed."""
    return clean().removed


def _clean_venvs(here: Path | None, got: Cleaned) -> None:
    """The venvs (Windows) of plugin versions that are gone (their marker names a plugin root that no longer
    exists), and those of another plugin root for a tier this version has finished (`clean`). One with no marker
    may be an install under way: kept."""
    try:
        base = paths.venvs_dir()
        mine = paths.plugin_root() if here is not None else None
    except RuntimeError:
        return
    folders, done = _folders(base), {}
    for folder in folders:
        try:
            owner = json.loads((folder / paths.VENV_MARKER).read_text(encoding="utf-8-sig"))["plugin_root"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(owner, str) or not owner:
            continue
        env = folder.name.rpartition("-")[0]
        if Path(owner).exists():
            if mine is None or _same(owner, mine) or folder.name == f"{env}-{paths.venv_key(mine)}" \
                    or env not in paths.WIN_VENVS or _in_use(owner):
                continue
            if env not in done:
                done[env] = _done_here(env, here, _folders(paths.data_dir() / "envs"))
            if not done[env]:
                continue
        _remove(folder, base, got)


def _force(func, path, _exc) -> None:
    """Windows marks some package files read-only; clear that and try once more."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _size(mb: int) -> str:
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb} MB"


def install(tier: str, yes: bool, as_json: bool = False, freed_bytes: int = 0) -> int:
    """Install a tier, then remove the earlier versions' copies of it (`clean`, issue #161) and say the space freed
    (with `freed_bytes`, what a clean before the install freed). With `as_json` stdout is one JSON object,
    {"status": "done"|"stop"|"error", "tier", "message", "freed_mb"} (issue #126): the output of npm and the
    installer's other children goes to stderr (pixi's to its log). The exit codes are the same either way."""
    if not as_json:
        code, message, _ = _install_and_clean(tier, yes, freed_bytes)
        print(message)
        return code
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)                    # pixi, npm and their children write to fd 1: send it to stderr meanwhile
    try:
        with contextlib.redirect_stdout(sys.stderr):
            code, message, freed_bytes = _install_and_clean(tier, yes, freed_bytes)
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)
    status = {0: "done", 2: "stop"}.get(code, "error")
    print(json.dumps({"status": status, "tier": tier, "message": message, "freed_mb": _mb(freed_bytes)},
                     ensure_ascii=False))
    return code


def _install_and_clean(tier: str, yes: bool, freed_bytes: int) -> tuple[int, str, int]:
    code, message = _install(tier, yes)
    if code == 0:
        freed_bytes += clean().freed_bytes   # this version has the tier now: the earlier copies go (issue #161)
        if _mb(freed_bytes):
            message = f"{message} {i18n.t('env.freed', size=_size(_mb(freed_bytes)))}"
    return code, message, freed_bytes


_ESCAPES = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-_]")
TAIL_LINES = 10


def _tail(log: Path) -> str:
    """The log's last lines that say something, without colour codes or other control characters."""
    try:
        text = _ESCAPES.sub("", log.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return ""
    lines = ["".join(ch for ch in line if ch == "\t" or ch.isprintable()).rstrip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line.strip()][-TAIL_LINES:])[-1500:]


def _install_log(tier: str) -> tuple[Path | None, object]:
    """Where pixi's output goes (issue #161): `<data>/install-env-<tier>.log`, beside install-pixi.log, so its
    warnings and the data folder's full path never reach the screen. (None, None) when it cannot be written: then
    pixi writes where it always did."""
    try:
        data = paths.data_dir()
        data.mkdir(parents=True, exist_ok=True)
        log = data / f"install-env-{tier}.log"
        return log, open(log, "w", encoding="utf-8", errors="replace")
    except (OSError, RuntimeError):
        return None, None


def _install(tier: str, yes: bool) -> tuple[int, str]:
    if tier not in TIERS:
        return 1, f"Unknown tier '{tier}'. Choose one of: {', '.join(TIERS)}."
    t = TIERS[tier]
    if not yes:
        minutes = max(1, round(t.approx_mb / 500))
        return 2, (f"Installing '{tier}' downloads about {_size(t.approx_mb)} and takes about "
                   f"{minutes} minute(s). Nothing was installed. Say yes, then run: "
                   f"tm env install {tier} --yes. The run continues from the same place.")
    log, out = _install_log(tier)
    try:
        proc = subprocess.run(
            [str(paths.pixi_bin()), "install", "--frozen", "-e", t.env, "--manifest-path", str(_manifest())],
            env=_pixi_env(), stdout=out, stderr=subprocess.STDOUT if out else None,
        )
    except OSError as exc:
        return 1, f"Could not start the installer: {exc}"
    finally:
        if out:
            out.close()
    if proc.returncode != 0:
        if log is None:
            return 1, f"The installer stopped with exit code {proc.returncode}; its messages are above."
        return 1, i18n.t("env.install_failed", code=proc.returncode, tail=_tail(log) or "-", log=str(log))
    if log is not None:
        log.unlink(missing_ok=True)   # removed again when all went well, as install-pixi.log
    if paths.is_windows() and t.env in paths.WIN_VENVS and not venv_installed(t.env):
        code, message = _install_venv(t.env)   # Windows: the tier's Python packages, in its venv (issue #123)
        if code:
            return code, message
    if tier == "video":  # the Remotion packages and headless browser belong to this tier (and this yes)
        from tm import render
        from tm.tools import _common

        try:
            fresh = not render.setup_done()
            render.setup()
        except (_common.ToolError, OSError, RuntimeError, ValueError) as exc:
            return 1, f"The video tools are installed, but the Remotion setup did not finish: {exc}"
        try:   # a test render (issue #124): the files of a setup can be in place while a render fails
            try:
                render.probe()
            except _common.ToolError:
                if fresh:
                    raise
                render.setup(force=True)   # an earlier setup's files: set them up again from scratch, then test again
                render.probe()
        except (_common.ToolError, OSError, RuntimeError, ValueError) as exc:
            return 1, f"The video tools are installed, but a test render failed: {exc}"
        from tm import face_model

        face_model.fetch_for_install()   # YuNet's face model, once, pinned by its SHA-256 (issue #167); never fails
    if tier == "animatic":  # puppeteer-core only: the browser is the user's own
        from tm import atlas
        from tm.tools import _common

        try:
            atlas.setup()
        except (_common.ToolError, OSError, RuntimeError, ValueError) as exc:
            return 1, f"The animatic tools are installed, but their setup did not finish: {exc}"
    return 0, i18n.t("env.installed", what=i18n.t(f"env.tier.{tier}"), tier=tier)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="env_command", metavar="action")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    inst = sub.add_parser("install")
    inst.add_argument("tier", choices=list(TIERS))
    inst.add_argument("--yes", action="store_true")
    inst.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    if args.env_command in ("install", "status"):
        cleaned = clean()
        gone = cleaned.removed
        if gone and not getattr(args, "json", False):
            print(f"Removed {len(gone)} environment folder(s) left by earlier plugin versions.")
    if args.env_command == "install":
        return install(args.tier, args.yes, args.json, cleaned.freed_bytes)
    if args.env_command == "status":
        rows = {n: {"installed": installed(n), "approx_mb": t.approx_mb} for n, t in TIERS.items()}
        if args.json:
            print(json.dumps({"tiers": rows, "removed_old_environments": len(gone), "freed_mb": cleaned.freed_mb}))
        else:
            if cleaned.freed_mb:
                print(i18n.t("env.freed", size=_size(cleaned.freed_mb)))
            for n, r in rows.items():
                print(f"{n}: {'installed' if r['installed'] else 'not installed'} (about {_size(r['approx_mb'])})")
        return 0
    print("Use: tm env status [--json] | tm env install <tier> --yes [--json]")
    return 1


cli.register("env", _setup, _run)
