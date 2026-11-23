"""Toolchain tiers. Each tier is a pixi environment installed only after a yes.

Ruling 25: the manifest stays in the plugin root. pixi keys a detached environment on the
manifest's path, and that path changes with every plugin version, so each version installs its
tiers again (mostly from pixi's package cache) into a new `<data>/envs/<name>-<hash>/` folder.
`clean_stale` removes the folders whose manifest is gone; `tm env status` and `tm env install`
run it first.

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
import shutil
import stat
import subprocess
import sys
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


def clean_stale() -> list[Path]:
    """Remove the environment folders of plugin versions that are gone: a folder under
    `<data>/envs` whose every finished environment (conda-meta/pixi) names a manifest that no
    longer exists. A folder with no finished environment may be an install under way: kept.
    On Windows also each venv under `<data>/venvs` whose marker names a plugin root that is gone.
    Returns the folders removed. Cheap: a directory listing and a few small files."""
    try:
        root = paths.data_dir() / "envs"
        folders = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    except (OSError, RuntimeError):
        return []
    removed = _clean_venvs()
    for folder in sorted(folders):
        manifests = []
        for marker in folder.glob("envs/*/conda-meta/pixi"):
            try:
                manifests.append(json.loads(marker.read_text(encoding="utf-8-sig"))["manifest_path"])
            except (OSError, ValueError, KeyError, TypeError):
                manifests.append(None)  # unreadable: keep the folder
        if not manifests or any(m is None or Path(m).exists() for m in manifests):
            continue
        shutil.rmtree(folder, onerror=_force)
        if not folder.exists():
            removed.append(folder)
    return removed


def _clean_venvs() -> list[Path]:
    """The venvs (Windows) of plugin versions that are gone: their marker names a plugin root that no longer exists.
    One with no marker may be an install under way: kept."""
    try:
        root = paths.venvs_dir()
        folders = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    except (OSError, RuntimeError):
        return []
    removed = []
    for folder in sorted(folders):
        try:
            owner = json.loads((folder / paths.VENV_MARKER).read_text(encoding="utf-8-sig"))["plugin_root"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(owner, str) or not owner or Path(owner).exists():
            continue
        shutil.rmtree(folder, onerror=_force)
        if not folder.exists():
            removed.append(folder)
    return removed


def _force(func, path, _exc) -> None:
    """Windows marks some package files read-only; clear that and try once more."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _size(mb: int) -> str:
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb} MB"


def install(tier: str, yes: bool, as_json: bool = False) -> int:
    """Install a tier. With `as_json` stdout is one JSON object, {"status": "done"|"stop"|"error", "tier",
    "message"} (issue #126): the installer's own output goes to stderr. The exit codes are the same either way."""
    if not as_json:
        code, message = _install(tier, yes)
        print(message)
        return code
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)                    # pixi, npm and their children write to fd 1: send it to stderr meanwhile
    try:
        with contextlib.redirect_stdout(sys.stderr):
            code, message = _install(tier, yes)
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)
    status = {0: "done", 2: "stop"}.get(code, "error")
    print(json.dumps({"status": status, "tier": tier, "message": message}, ensure_ascii=False))
    return code


def _install(tier: str, yes: bool) -> tuple[int, str]:
    if tier not in TIERS:
        return 1, f"Unknown tier '{tier}'. Choose one of: {', '.join(TIERS)}."
    t = TIERS[tier]
    if not yes:
        minutes = max(1, round(t.approx_mb / 500))
        return 2, (f"Installing '{tier}' downloads about {_size(t.approx_mb)} and takes about "
                   f"{minutes} minute(s). Nothing was installed. Say yes, then run: "
                   f"tm env install {tier} --yes. The run continues from the same place.")
    try:
        proc = subprocess.run(
            [str(paths.pixi_bin()), "install", "--frozen", "-e", t.env, "--manifest-path", str(_manifest())],
            env=_pixi_env(),
        )
    except OSError as exc:
        return 1, f"Could not start the installer: {exc}"
    if proc.returncode != 0:
        return 1, f"The installer stopped with exit code {proc.returncode}; its messages are above."
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
        gone = clean_stale()
        if gone and not getattr(args, "json", False):
            print(f"Removed {len(gone)} environment folder(s) left by earlier plugin versions.")
    if args.env_command == "install":
        return install(args.tier, args.yes, args.json)
    if args.env_command == "status":
        rows = {n: {"installed": installed(n), "approx_mb": t.approx_mb} for n, t in TIERS.items()}
        if args.json:
            print(json.dumps({"tiers": rows, "removed_old_environments": len(gone)}))
        else:
            for n, r in rows.items():
                print(f"{n}: {'installed' if r['installed'] else 'not installed'} (about {_size(r['approx_mb'])})")
        return 0
    print("Use: tm env status [--json] | tm env install <tier> --yes [--json]")
    return 1


cli.register("env", _setup, _run)
