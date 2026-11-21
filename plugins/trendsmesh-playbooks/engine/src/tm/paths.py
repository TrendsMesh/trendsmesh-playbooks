"""Where the plugin lives. The session hook writes ~/.trendsmesh/paths.json and exports
TM_PLUGIN_ROOT / TM_PLUGIN_DATA; each lookup tries the env var first, then the file."""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_NOT_FOUND = "TrendsMesh plugin folders are not known yet. Start a new Claude Code session so the plugin can set itself up."


def _paths_file() -> Path:
    return Path.home() / ".trendsmesh" / "paths.json"


def _from_file(key: str) -> str | None:
    try:
        value = json.loads(_paths_file().read_text(encoding="utf-8-sig")).get(key)
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


_RUN_WORKSPACE: ContextVar[Path | None] = ContextVar("tm_run_workspace", default=None)
_RUN_FOLDER = re.compile(r"0\d-.*")


def session_folder() -> Path:
    """Where tm was started from: TM_WORKSPACE, else the current folder (what Claude Code's hooks see)."""
    value = os.environ.get("TM_WORKSPACE")
    return Path(value) if value else Path.cwd()


def is_workspace(folder: Path) -> bool:
    """A TrendsMesh workspace holds .trendsmesh/ or runs/0N-<playbook>/: the test the key guard uses too
    (bootstrap/guard-secrets.sh). A bare library/ is not one (issue #126)."""
    folder = Path(folder)
    if (folder / ".trendsmesh").is_dir():
        return True
    try:
        return any(p.is_dir() and _RUN_FOLDER.fullmatch(p.name) for p in (folder / "runs").iterdir())
    except OSError:
        return False


def workspace() -> Path:
    """The workspace (issue #126): the run's, for a command given --run (`from_run`); else TM_WORKSPACE; else the
    first folder from the current one up that is a workspace (`is_workspace`), never the home folder (its
    .trendsmesh/ holds the plugin's paths file) or above it; else the current folder."""
    found = _RUN_WORKSPACE.get()
    if found is not None:
        return found
    value = os.environ.get("TM_WORKSPACE")
    if value:
        return Path(value)
    here = Path.cwd()
    try:
        home = os.path.normcase(str(Path.home()))
    except RuntimeError:
        home = None
    for folder in (here, *here.parents):
        if os.path.normcase(str(folder)) == home:
            break
        if is_workspace(folder):
            return folder
    return here


def workspace_of_run(path: Path | str) -> Path | None:
    """The workspace of a run folder (<workspace>/runs/<playbook>/<run>), None for a path that is not a run."""
    try:
        run = Path(path).resolve()
    except (OSError, RuntimeError, TypeError):
        return None
    if (run / "manifest.md").is_file() and len(run.parents) > 2 and run.parent.parent.name == "runs":
        return run.parents[2]
    return None


@contextmanager
def from_run(path: Path | str | None):
    """While a command given --run works, `workspace()` is that run's workspace, whatever the current folder."""
    found = workspace_of_run(path) if isinstance(path, (str, Path)) and str(path) else None
    token = _RUN_WORKSPACE.set(found) if found is not None else None
    try:
        yield found
    finally:
        if token is not None:
            _RUN_WORKSPACE.reset(token)


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
