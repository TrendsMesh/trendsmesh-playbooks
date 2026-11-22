"""Windows runs tm on python.org's Python, signed by the Python Software Foundation (issue #123, part 1).

Smart App Control blocked conda-forge's unsigned python.exe and .pyd files. So on Windows the pixi environments keep
only ffmpeg and node, bootstrap/install-python.ps1 installs python.org's NuGet package (its SHA-256 pinned, its
signatures checked) and one venv per tier from the hash-pinned env/win-64/<tier>.txt, and the launchers and the
engine run each tool on its tier's venv. macOS and Linux keep pixi's python. These tests hold the pieces together:
the manifest and its lock, the requirements files, the venv's place (the same key in Python, sh and PowerShell), and
the engine's use of it. The real install runs in CI's windows-latest job.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from tm import envtiers, paths
from tm.envtiers import TIERS

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "trendsmesh-playbooks"
ENV = PLUGIN / "env"
WIN = ENV / "win-64"
BOOT = PLUGIN / "bootstrap"


def _manifest() -> dict:
    return tomllib.loads((ENV / "pixi.toml").read_text(encoding="utf-8"))


def _lock() -> dict:
    return yaml.safe_load((ENV / "pixi.lock").read_text(encoding="utf-8"))


def _requirements(env: str) -> dict[str, tuple[str, list[str]]]:
    """name -> (version, hashes) of a requirements file."""
    text = (WIN / f"{env}.txt").read_text(encoding="utf-8")
    found = {}
    for block in re.split(r"(?m)^(?=[A-Za-z0-9])", text):
        m = re.match(r"([A-Za-z0-9._-]+)==(\S+)", block)
        if m:
            found[_norm(m[1])] = (m[2], re.findall(r"--hash=sha256:([0-9a-f]{64})", block))
    return found


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


# --- the manifest and the lock --------------------------------------------------------------------------------------


def test_python_and_its_packages_are_for_macos_and_linux_only():
    m = _manifest()
    assert set(m["dependencies"]) == {"ffmpeg"}
    assert {"python", "pyyaml", "requests"} <= set(m["target"]["unix"]["dependencies"])
    assert "pypi-dependencies" not in m and "tm" in m["target"]["unix"]["pypi-dependencies"]
    for name, feature in m["feature"].items():
        assert "pypi-dependencies" not in feature, f"{name}: its pypi packages go under target.unix"
        assert "win-64" not in feature.get("target", {}) or name == "dev", f"{name}: no Windows packages but dev's"


def test_the_windows_environments_hold_no_python_package_of_ours():
    """The tiers' environments on win-64: no pypi package, no pyyaml or requests (the venv has them). conda-forge's
    python stays only as a dependency of ffmpeg's (glib), and nothing runs it. dev keeps its own for CI's tests."""
    lock = _lock()
    for env in {t.env for t in TIERS.values()}:
        entries = lock["environments"][env]["packages"]["win-64"]
        assert not [e for e in entries if "pypi" in e], env
        names = {e["conda"].rsplit("/", 1)[-1].rsplit("-", 2)[0] for e in entries if "conda" in e}
        assert "ffmpeg" in names and not names & {"pyyaml", "requests"}, env
    dev = lock["environments"]["dev"]["packages"]["win-64"]
    assert any("pypi" in e for e in dev), "dev keeps the engine on Windows, for CI's engine tests"


# --- the requirements files ------------------------------------------------------------------------------------------


def test_every_tier_that_runs_python_has_its_requirements_and_only_those():
    envs = {t.env for t in TIERS.values()}
    assert set(paths.WIN_VENVS) == envs - {"video"}, "video and animatic run only node"
    assert {p.stem for p in WIN.glob("*.txt")} == set(paths.WIN_VENVS)


def test_the_generator_writes_the_same_tiers():
    import ast

    tree = ast.parse((REPO / ".github" / "scripts" / "win64_requirements.py").read_text(encoding="utf-8"))
    values = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and t.id in ("TIERS", "PYTHON")}
    assert values == {"TIERS": tuple(paths.WIN_VENVS), "PYTHON": paths.WIN_PYTHON}


@pytest.mark.parametrize("env", paths.WIN_VENVS)
def test_each_file_pins_every_package_with_its_hashes(env):
    text = (WIN / f"{env}.txt").read_text(encoding="utf-8")
    assert "\r" not in text, "LF on every system (.gitattributes), so its hash is the same everywhere"
    reqs = _requirements(env)
    assert reqs and {"pyyaml", "requests"} <= set(reqs)
    for name, (version, hashes) in reqs.items():
        assert hashes, f"{env}: {name} has no hash"
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith(("#", " ", "--index-url", "--extra-index-url"))]
    assert all(re.match(r"[A-Za-z0-9._-]+==\S+ \\$", ln) for ln in lines), lines


@pytest.mark.parametrize("env", paths.WIN_VENVS)
def test_each_file_holds_the_versions_of_the_lock(env):
    """The same versions as pixi.lock has for the environment on linux-64 (what CI tests), for every package both
    have; a package only Windows needs (colorama) is the newest."""
    lock = _lock()
    pypi = {p["pypi"]: p for p in lock["packages"] if "pypi" in p}
    conda = {p["conda"]: p for p in lock["packages"] if "conda" in p}
    locked = {}
    for e in lock["environments"][env]["packages"]["linux-64"]:
        if "pypi" in e and pypi[e["pypi"]]["name"] != "tm":
            locked[_norm(pypi[e["pypi"]]["name"])] = str(pypi[e["pypi"]]["version"])
        elif "conda" in e and any(str(d).split()[0] == "python" for d in conda[e["conda"]].get("depends", [])):
            name, version, _ = e["conda"].rsplit("/", 1)[-1].rsplit("-", 2)
            locked[_norm(name)] = version
    reqs = _requirements(env)
    differ = {n: (v, locked[n]) for n, (v, _) in reqs.items() if n in locked and v != locked[n]}
    assert not differ, f"{env}: not the lock's versions (run .github/scripts/win64_requirements.py): {differ}"


@pytest.mark.parametrize("env", paths.WIN_VENVS)
def test_each_file_has_what_the_manifest_asks_of_the_tier(env):
    m = _manifest()
    wanted = {"pyyaml", "requests"}
    for f in m["environments"][env].get("features", []):
        target = m["feature"][f].get("target", {})
        wanted |= {_norm(n) for n in target.get("unix", {}).get("pypi-dependencies", {})}
    assert wanted <= set(_requirements(env)), wanted - set(_requirements(env))
    # scenedetect's opencv-python is dropped (pixi.toml's override): the headless build is the only cv2
    assert "opencv-python" not in _requirements(env)


def test_torch_comes_from_the_pytorch_index():
    text = (WIN / "voice.txt").read_text(encoding="utf-8")
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in text.splitlines()
    assert _requirements("voice")["torch"][0] == "2.8.0+cpu"


def test_charset_normalizer_is_its_pure_python_wheel():
    """requests needs it, so tm itself imports it at start: only its pure-Python wheel's hash is kept, as its compiled
    wheel is unsigned .pyd files Smart App Control could block."""
    for env in paths.WIN_VENVS:
        assert len(_requirements(env)["charset-normalizer"][1]) == 1, env


def test_the_requirements_files_are_lf_on_every_system():
    attrs = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "plugins/trendsmesh-playbooks/env/win-64/*.txt text eol=lf" in attrs.splitlines()


# --- the runtime install -----------------------------------------------------------------------------------------------


def test_the_runtime_is_python_orgs_311_pinned_by_hash():
    text = (BOOT / "install-python.ps1").read_text(encoding="utf-8")
    assert f"$TmPythonVersion = '{paths.WIN_PYTHON}'" in text
    assert re.search(r"\$TmPythonSha256 = '[0-9a-f]{64}'", text)
    assert "$TmPythonUrl = 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg'" in text
    assert "$TmPythonSigner = 'Python Software Foundation'" in text
    assert "Get-AuthenticodeSignature" in text and "'Valid'" in text
    assert "'--require-hashes', '--no-deps', '--only-binary', ':all:'" in text


# --- where the venv is ---------------------------------------------------------------------------------------------------


def test_the_venv_key_is_the_same_in_python_sh_and_powershell():
    """The first 12 hex digits of the SHA-256 of the plugin root, / made \\ and no trailing \\. The same vector is
    worked out in bin/tm and install-python.ps1 (tests/bootstrap runs those)."""
    root = "C:\\Users\\\u0141ukasz\\.claude\\plugins\\cache\\tm\\0.14.0"
    assert paths.venv_key(root) == "1bdc50a6043a"
    assert paths.venv_key(root.replace("\\", "/") + "/") == "1bdc50a6043a"
    assert paths.venv_key(root) == hashlib.sha256(root.encode("utf-8")).hexdigest()[:12]
    tm_sh = (PLUGIN / "bin" / "tm").read_text(encoding="utf-8")
    assert "tr '/' '\\\\' | sed 's/\\\\*$//' | sha256 | cut -c1-12" in tm_sh
    ps = (BOOT / "install-python.ps1").read_text(encoding="utf-8")
    assert "$Root.Replace('/', '\\').TrimEnd('\\')" in ps and ".Substring(0, 12)" in ps


@pytest.fixture
def windows(monkeypatch, tmp_path):
    root = tmp_path / "plugin \u0141ukasz"
    data = tmp_path / "data dir"
    (root / "env" / "win-64").mkdir(parents=True)
    for env in paths.WIN_VENVS:
        (root / "env" / "win-64" / f"{env}.txt").write_text(f"{env}==1 \\\n    --hash=sha256:{'0' * 64}\n")
    monkeypatch.setattr(paths, "is_windows", lambda: True)
    monkeypatch.setattr(paths, "plugin_root", lambda: root)
    monkeypatch.setattr(paths, "data_dir", lambda: data)
    monkeypatch.setattr(paths, "pixi_bin", lambda: data / "pixi" / "bin" / "pixi.exe")
    return root, data


def _finish(env: str, root: Path, data: Path, sha: str | None = None) -> Path:
    venv = data / "venvs" / f"{env}-{paths.venv_key(root)}"
    (venv / "Scripts").mkdir(parents=True, exist_ok=True)
    (venv / "Scripts" / "python.exe").write_bytes(b"")
    sha = sha or hashlib.sha256((root / "env" / "win-64" / f"{env}.txt").read_bytes()).hexdigest()
    (venv / paths.VENV_MARKER).write_text(json.dumps({"tier": env, "plugin_root": str(root), "python": "3.11.9",
                                                      "requirements_sha256": sha}), encoding="utf-8")
    return venv


def test_python_bin_is_the_tiers_venv_on_windows_and_pixis_python_elsewhere(windows, monkeypatch):
    root, data = windows
    want = data / "venvs" / f"breakdown-{paths.venv_key(root)}" / "Scripts" / "python.exe"
    assert paths.python_bin("breakdown") == str(want)
    assert paths.win_python() == data / "python" / "3.11.9" / "python.exe"
    monkeypatch.setattr(paths, "is_windows", lambda: False)
    assert paths.python_bin("breakdown") == "python"


def test_a_tool_runs_on_its_tiers_venv_inside_its_pixi_environment(windows):
    from tm.tools import child_argv

    root, data = windows
    argv = child_argv("teardown", ["--run", "runs/x y", "a b.mp4"])
    assert argv[1:7] == ["run", "--as-is", "--manifest-path", str(root / "env" / "pixi.toml"), "-e", "breakdown"]
    assert argv[7] == paths.python_bin("breakdown") and argv[8:] == ["-m", "tm.toolrun", "teardown", "--run",
                                                                       "runs/x y", "a b.mp4"]   # #148 line 154
    assert child_argv("elevenlabs", ["credits"])[7] == paths.python_bin("base")   # a light action: base


def test_the_ocr_worker_runs_on_the_ocr_venv(windows, tmp_path):
    from tm.tools import _ocr

    argv = _ocr.worker_argv(tmp_path / "req.json", tmp_path / "res.json")
    assert argv[argv.index("-e") + 1] == "ocr" and argv[argv.index("-e") + 2] == paths.python_bin("ocr")


# --- the engine's tiers on Windows -----------------------------------------------------------------------------------------


def test_a_tier_is_installed_only_with_its_finished_venv(windows, monkeypatch):
    root, data = windows
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: True)
    assert not envtiers.installed("breakdown")
    venv = _finish("breakdown", root, data, sha="1" * 64)       # filled from another requirements file
    assert not envtiers.installed("breakdown")
    _finish("breakdown", root, data)
    assert envtiers.installed("breakdown")
    (venv / "Scripts" / "python.exe").unlink()
    assert not envtiers.installed("breakdown")
    from tm import render
    monkeypatch.setattr(render, "setup_done", lambda: True)
    assert envtiers.installed("video"), "the video tier runs only node: no venv"


def test_install_makes_the_venv_after_pixi_with_install_python(windows, monkeypatch):
    root, data = windows
    calls = []

    def run(argv, **kw):
        calls.append((argv, kw))
        if argv[0] == "powershell.exe":
            _finish("voice", root, data)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(envtiers.subprocess, "run", run)
    monkeypatch.setattr(envtiers.paths, "pixi_env", lambda: {"PIXI_HOME": "h"})
    assert envtiers.install("voice", yes=True) == 0
    (pixi, _), (ps, kw) = calls
    assert pixi[1:3] == ["install", "--frozen"]
    assert ps == ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                  str(root / "bootstrap" / "install-python.ps1"), "-Tier", "voice", "-Report"]
    assert kw["env"]["CLAUDE_PLUGIN_ROOT"] == str(root) and kw["env"]["CLAUDE_PLUGIN_DATA"] == str(data)
    calls.clear()
    assert envtiers.install("voice", yes=True) == 0 and len(calls) == 1, "a finished venv is not made again"


def test_a_failed_venv_says_why(windows, monkeypatch, capsys):
    def run(argv, **kw):
        if argv[0] == "powershell.exe":
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="trendsmesh-playbooks: pip did not install "
                                               "the Python packages of the 'ai' tools (exit code 1). The install needs "
                                               "api.nuget.org (Python), pypi.org and files.pythonhosted.org\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(envtiers.subprocess, "run", run)
    monkeypatch.setattr(envtiers.paths, "pixi_env", lambda: {})
    assert envtiers.install("ai", yes=True, as_json=True) == 1
    said = json.loads(capsys.readouterr().out)
    assert said["status"] == "error" and "pip did not install" in said["message"]
    assert "files.pythonhosted.org" in said["message"]


def test_the_venvs_of_plugin_versions_that_are_gone_are_removed(windows, tmp_path):
    root, data = windows
    mine = _finish("base", root, data)
    old_root = tmp_path / "gone" / "0.1.0"
    old = data / "venvs" / f"base-{paths.venv_key(old_root)}"
    (old / "Scripts").mkdir(parents=True)
    (old / paths.VENV_MARKER).write_text(json.dumps({"plugin_root": str(old_root)}), encoding="utf-8")
    busy = data / "venvs" / "ai-000000000000"   # no marker yet: an install under way
    busy.mkdir(parents=True)
    assert envtiers.clean_stale() == [old]
    assert mine.is_dir() and busy.is_dir() and not old.exists()
