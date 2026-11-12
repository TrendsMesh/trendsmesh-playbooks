"""Where the plugin lives. The session hook writes ~/.trendsmesh/paths.json and exports
TM_PLUGIN_ROOT / TM_PLUGIN_DATA; each lookup tries the env var first, then the file."""

from __future__ import annotations

import json
import os
from pathlib import Path

_NOT_FOUND = "TrendsMesh plugin folders are not known yet. Start a new Claude Code session so the plugin can set itself up."


def _paths_file() -> Path:
    return Path.home() / ".trendsmesh" / "paths.json"


def _from_file(key: str) -> str | None:
    try:
        value = json.loads(_paths_file().read_text(encoding="utf-8")).get(key)
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value else None


def _resolve(env_var: str, key: str) -> Path:
    value = os.environ.get(env_var) or _from_file(key)
    if not value:
        raise RuntimeError(_NOT_FOUND)
    return Path(value)


def plugin_root() -> Path:
    return _resolve("TM_PLUGIN_ROOT", "plugin_root")


def data_dir() -> Path:
    return _resolve("TM_PLUGIN_DATA", "plugin_data")


def workspace() -> Path:
    value = os.environ.get("TM_WORKSPACE")
    return Path(value) if value else Path.cwd()


def bundled_data() -> Path:
    """The plugin's data/ folder (steps, check-ins), shipped next to this engine's source.

    It is found from the package itself, not from TM_PLUGIN_ROOT, so the code and its data
    always come from the same plugin version.
    """
    return Path(__file__).resolve().parents[3] / "data"


def pixi_bin() -> Path:
    value = _from_file("pixi")
    if value:
        return Path(value)
    return data_dir() / "pixi" / "bin" / ("pixi.exe" if os.name == "nt" else "pixi")


def child_environ(env: dict[str, str]) -> dict[str, str]:
    """`env` for a nested pixi call, without an SSL_CERT_DIR that names a folder with no files in it. The engine runs
    inside an activated pixi environment, and conda-forge's openssl activation (on Windows) points SSL_CERT_DIR at
    its own empty certs folder; pixi, started from here, then says "ignoring SSL_CERT_DIR: no certificates found"
    on stderr (#54). A folder that holds certificates (a proxy's own, set by the user) is kept."""
    cert_dir = env.get("SSL_CERT_DIR")
    if cert_dir is None:
        return env
    try:
        holds = any(p.is_file() for p in Path(cert_dir).iterdir())
    except OSError:
        holds = False
    return env if holds else {k: v for k, v in env.items() if k != "SSL_CERT_DIR"}


def pixi_env() -> dict[str, str]:
    """Environment variables to pass to every pixi call.

    PIXI_HOME lives in the data folder, and its config.toml sends environments to
    <data>/envs. pixi names each environment folder after the manifest's path, which changes
    with every plugin version, so an update installs the tiers again (Ruling 25; mostly from
    pixi's package cache) and `tm env` removes the folders of versions that are gone.
    """
    data = data_dir()
    home = data / "pixi"
    home.mkdir(parents=True, exist_ok=True)
    config = home / "config.toml"
    line = f'detached-environments = "{(data / "envs").as_posix()}"\n'
    if not config.exists() or config.read_text(encoding="utf-8") != line:
        config.write_text(line, encoding="utf-8")
    # PYTHONIOENCODING: the tools are Python children; on Windows their piped output would
    # otherwise use the ANSI code page and fail on a non-ASCII path or ad name.
    return {"PIXI_HOME": str(home), "PIXI_NO_PATH_UPDATE": "1", "PYTHONIOENCODING": "utf-8"}
