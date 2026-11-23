"""Where the plugin lives. The session hook writes ~/.trendsmesh/paths.json and exports
TM_PLUGIN_ROOT / TM_PLUGIN_DATA; each lookup tries the env var first, then the file."""

from __future__ import annotations

import hashlib
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


# Windows (issue #123): tm runs on python.org's Python, signed by the Python Software Foundation, not on conda-forge's,
# which Smart App Control can block. bootstrap/install-python.ps1 installs it into <data>/python/<version>/ and each
# tier's venv into <data>/venvs/<environment>-<key>/ (env/win-64/<environment>.txt); the pixi environments there hold
# only ffmpeg and node. macOS and Linux keep the pixi environment's own python.
WIN_PYTHON = "3.11.9"
# The pixi environments whose tools run Python, each with its venv on Windows (video and animatic run only node).
WIN_VENVS = ("base", "breakdown", "voice", "ai", "ocr")
VENV_MARKER = "tm-venv.json"


def is_windows() -> bool:
    return os.name == "nt"


def venv_key(root: str | Path) -> str:
    """The plugin root's part of a venv's folder name: the first 12 hex digits of the SHA-256 of its UTF-8 text, with
    / made \\ and no trailing \\. bin/tm and bootstrap/install-python.ps1 work it out the same way. Each plugin version
    has its own root, so its own venvs (their tm.pth names its engine), as each has its own pixi environments."""
    text = str(root).replace("/", "\\").rstrip("\\")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def win_python() -> Path:
    """The python.org python.exe the venvs are made from (Windows)."""
    return data_dir() / "python" / WIN_PYTHON / "python.exe"


def venvs_dir() -> Path:
    return data_dir() / "venvs"


def venv_dir(env: str) -> Path:
    """The venv of a pixi environment (base, breakdown, ...) on Windows, for this plugin version."""
    return venvs_dir() / f"{env}-{venv_key(plugin_root())}"


def win_requirements(env: str) -> Path:
    return plugin_root() / "env" / "win-64" / f"{env}.txt"


def python_bin(env: str) -> str:
    """The python a tool runs on inside `pixi run -e <env>`: on Windows the environment's venv (by its full path), else
    the pixi environment's own `python`."""
    if not is_windows():
        return "python"
    return str(venv_dir(env) / "Scripts" / "python.exe")


_PEM = b"-----BEGIN CERTIFICATE-----"


def _holds_certificate(folder: str) -> bool:
    """A file in `folder` holds a PEM certificate, as pixi's loader (rustls-native-certs) reads one."""
    try:
        entries = list(Path(folder).iterdir())
    except OSError:
        return False
    for entry in entries:
        try:
            if entry.is_file():
                with open(entry, "rb") as fh:
                    if _PEM in fh.read(1 << 20):
                        return True
        except OSError:
            continue
    return False


def child_environ(env: dict[str, str]) -> dict[str, str]:
    """`env` for a nested pixi call, without an SSL_CERT_DIR that names no folder with a certificate in it. The engine
    runs inside an activated pixi environment, and conda-forge's openssl activation (on Windows) points SSL_CERT_DIR
    at its own certs folder, which holds only an empty `.keep` file; pixi, started from here, then says "ignoring
    SSL_CERT_DIR: no certificates found" on stderr (#54; #161: "holds a file" kept that folder). A folder that holds
    a certificate (a proxy's own, set by the user), alone or in a list, is kept."""
    cert_dir = env.get("SSL_CERT_DIR")
    if cert_dir is None:
        return env
    holds = any(_holds_certificate(d) for d in cert_dir.split(os.pathsep) if d)
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
