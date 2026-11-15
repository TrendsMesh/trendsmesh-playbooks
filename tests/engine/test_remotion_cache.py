"""The video tests' Remotion cache: one per checkout (issue 63), so test runs in several checkouts at once never
swap each other's sources."""

import json
from pathlib import Path

from conftest import remotion_cache_for


def _setup(cache: Path, lock: str) -> Path:
    """A set-up cache, as render.setup leaves it (its marker holds the lock's hash)."""
    work = cache / "remotion"
    (work / "node_modules" / ".remotion").mkdir(parents=True)
    (work / "node_modules" / "pkg.js").write_text("x")
    (work / "src").mkdir()
    (work / "src" / "Old.tsx").write_text("old")
    (work / ".setup-done").write_text(lock)
    return cache


def test_each_checkout_has_its_own_cache(tmp_path):
    for checkout in ("checkout a", "checkout b"):
        (tmp_path / checkout / "plugin").mkdir(parents=True)
    a = remotion_cache_for(tmp_path, tmp_path / "checkout a" / "plugin", "h1")
    b = remotion_cache_for(tmp_path, tmp_path / "checkout b" / "plugin", "h1")
    assert a != b and a.parent == b.parent == tmp_path and a.name.startswith("tm-remotion-cache-")
    assert a == remotion_cache_for(tmp_path, tmp_path / "checkout a" / "plugin", "h1")   # the same run after run
    assert json.loads((a / ".checkout").read_text())["plugin"] == str(tmp_path / "checkout a" / "plugin")
    wrapper = remotion_cache_for(tmp_path, tmp_path / "checkout a" / "plugin", "h1", name="tm-remotion-cache-wrapper")
    assert wrapper != a and wrapper.name.startswith("tm-remotion-cache-wrapper-")


def test_a_new_cache_starts_from_a_set_up_one_with_the_same_lock(tmp_path):
    (tmp_path / "checkout a").mkdir()
    _setup(tmp_path / "tm-remotion-cache", "other lock")            # the shared cache of an older version
    first = remotion_cache_for(tmp_path, tmp_path / "checkout a", "h1")
    assert not (first / "remotion").exists()                      # a different lock: render.setup installs
    _setup(first, "h1")
    second = remotion_cache_for(tmp_path, tmp_path / "checkout b", "h1")
    assert (second / "remotion" / "node_modules" / "pkg.js").read_text() == "x"
    assert (second / "remotion" / ".setup-done").read_text() == "h1"
    assert not (second / "remotion" / "src").exists()            # src is the checkout's own, synced at render
    assert (first / "remotion" / "src" / "Old.tsx").is_file()     # the one copied from is untouched


def test_caches_of_checkouts_that_are_gone_are_removed(tmp_path):
    gone = remotion_cache_for(tmp_path, tmp_path / "removed worktree", "h1")
    _setup(gone, "h1")
    shared = _setup(tmp_path / "tm-remotion-cache", "h1")          # no .checkout: another version's, kept
    (tmp_path / "live").mkdir()
    live = remotion_cache_for(tmp_path, tmp_path / "live", "h1")
    assert not gone.exists() and shared.is_dir() and live.is_dir()
    assert (live / "remotion" / "node_modules" / "pkg.js").is_file()   # seeded before the gone one went
