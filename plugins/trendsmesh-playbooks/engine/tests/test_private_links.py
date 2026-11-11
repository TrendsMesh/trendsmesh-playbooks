"""A TrendsMesh machine's checkout: private/ is cloned, its paths are linked in and git-ignored, and a push from here
runs the leak scanner as TrendsMesh. Without private/ (anyone else's clone) both tests are skipped."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

from private import REPO


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout.strip()


def git_config(key: str) -> str:
    return git("config", "--get", key)


@pytest.mark.private_data
def test_private_links_are_complete():
    link = load_module(REPO / "private" / "tools" / "link.py")
    assert link.check(REPO, REPO / "private") == []


@pytest.mark.private_data
def test_pushes_from_here_are_guarded():   # design 2: warn when private/ exists but the hook doesn't
    hook = Path(git("rev-parse", "--git-path", "hooks/pre-push"))   # works in a worktree too
    hook = hook if hook.is_absolute() else REPO / hook
    assert hook.is_file()
    assert "private/tools/scan.py" in hook.read_text(encoding="utf-8")   # the leak scan, not some other hook
    assert git_config("user.email") == "contact@trendsmesh.com" and git_config("user.name") == "TrendsMesh"
