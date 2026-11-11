"""Toolchain tiers. Each tier is a pixi environment installed only after a yes.

Ruling 25: the manifest stays in the plugin root. pixi keys a detached environment on the
manifest's path, and that path changes with every plugin version, so each version installs its
tiers again (mostly from pixi's package cache) into a new `<data>/envs/<name>-<hash>/` folder.
`clean_stale` removes the folders whose manifest is gone; `tm env status` and `tm env install`
run it first.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from tm import cli, paths


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
    # user's own browser. Its outputs are creative brief's, which takes tiers from requirements.yaml.
    "animatic": Tier("animatic", "video", ["base"], 150, {"animatics"}),
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
    return {**os.environ, **paths.pixi_env()}


def installed(tier: str) -> bool:
    """True when pixi reports a prefix for the tier's environment that holds pixi's
    conda-meta/pixi marker (written only after an install finished). The video tier also needs
    the Remotion packages and headless browser for this lock file (`render.setup_done`), the
    animatic tier its node package (`atlas.setup_done`): `tm env install` sets both up, and this
    one check is what the doctor and the renderers ask."""
    if not _env_installed(TIERS[tier].env):
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


def clean_stale() -> list[Path]:
    """Remove the environment folders of plugin versions that are gone: a folder under
    `<data>/envs` whose every finished environment (conda-meta/pixi) names a manifest that no
    longer exists. A folder with no finished environment may be an install under way: kept.
    Returns the folders removed. Cheap: a directory listing and a few small files."""
    try:
        root = paths.data_dir() / "envs"
        folders = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    except (OSError, RuntimeError):
        return []
    removed = []
    for folder in sorted(folders):
        manifests = []
        for marker in folder.glob("envs/*/conda-meta/pixi"):
            try:
                manifests.append(json.loads(marker.read_text(encoding="utf-8"))["manifest_path"])
            except (OSError, ValueError, KeyError, TypeError):
                manifests.append(None)  # unreadable: keep the folder
        if not manifests or any(m is None or Path(m).exists() for m in manifests):
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


def install(tier: str, yes: bool) -> int:
    if tier not in TIERS:
        print(f"Unknown tier '{tier}'. Choose one of: {', '.join(TIERS)}.")
        return 1
    t = TIERS[tier]
    if not yes:
        minutes = max(1, round(t.approx_mb / 500))
        print(
            f"Installing '{tier}' downloads about {_size(t.approx_mb)} and takes about "
            f"{minutes} minute(s). Nothing was installed. Say yes, then run: "
            f"tm env install {tier} --yes. The run continues from the same place."
        )
        return 2
    try:
        proc = subprocess.run(
            [str(paths.pixi_bin()), "install", "--frozen", "-e", t.env, "--manifest-path", str(_manifest())],
            env=_pixi_env(),
        )
    except OSError as exc:
        print(f"Could not start the installer: {exc}")
        return 1
    if proc.returncode != 0:
        return 1
    if tier == "video":  # the Remotion packages and headless browser belong to this tier (and this yes)
        from tm import render
        from tm.tools import _common

        try:
            render.setup()
        except (_common.ToolError, OSError, RuntimeError, ValueError) as exc:
            print(f"The video tools are installed, but the Remotion setup did not finish: {exc}")
            return 1
    if tier == "animatic":  # puppeteer-core only: the browser is the user's own
        from tm import atlas
        from tm.tools import _common

        try:
            atlas.setup()
        except (_common.ToolError, OSError, RuntimeError, ValueError) as exc:
            print(f"The animatic tools are installed, but their setup did not finish: {exc}")
            return 1
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="env_command", metavar="action")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    inst = sub.add_parser("install")
    inst.add_argument("tier", choices=list(TIERS))
    inst.add_argument("--yes", action="store_true")


def _run(args: argparse.Namespace) -> int:
    if args.env_command in ("install", "status"):
        gone = clean_stale()
        if gone and not getattr(args, "json", False):
            print(f"Removed {len(gone)} environment folder(s) left by earlier plugin versions.")
    if args.env_command == "install":
        return install(args.tier, args.yes)
    if args.env_command == "status":
        rows = {n: {"installed": installed(n), "approx_mb": t.approx_mb} for n, t in TIERS.items()}
        if args.json:
            print(json.dumps({"tiers": rows, "removed_old_environments": len(gone)}))
        else:
            for n, r in rows.items():
                print(f"{n}: {'installed' if r['installed'] else 'not installed'} (about {_size(r['approx_mb'])})")
        return 0
    print("Use: tm env status [--json] | tm env install <tier> --yes")
    return 1


cli.register("env", _setup, _run)
