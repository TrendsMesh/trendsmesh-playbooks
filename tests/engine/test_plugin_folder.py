"""The plugin folder stays within Anthropic's plugin directory checklist (issue #108).

The directory counts every file in `plugins/trendsmesh-playbooks/`: at most 512 files and 256 KiB per file, and the
folder needs its own README of at least 40 words. Tests and evals live at the repository's root (`tests/`, `evals/`)
for that reason. A branch cut before the move can still add a test under the old `engine/tests/` or `evals/`
folders; this check fails then, so the file is moved to `tests/engine/` or `evals/` instead of shipping in the plugin
(and running nowhere).

The check reads `git ls-files`, so it covers every committed file and every new file not yet committed (but not
git-ignored ones). Outside a git checkout (an installed plugin, a ZIP) it is skipped."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = "plugins/trendsmesh-playbooks"
MAX_FILES = 512
MAX_BYTES = 256 * 1024
# Over the size limit on purpose: a review hold, not a block (the plugin README says why).
BIG_ON_PURPOSE = {f"{PLUGIN}/env/pixi.lock"}
TEST_LIKE = re.compile(r"(^|/)(tests?|evals?)(/|$)|(^|/)test_[^/]*\.py$|(^|/)conftest\.py$")


def _plugin_files() -> list[str]:
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "--cached", "--others", "--exclude-standard", "-z",
                        "--", PLUGIN], capture_output=True, text=True, encoding="utf-8", check=True)
    return [p for p in r.stdout.split("\0") if p and (REPO / p).is_file()]


def test_no_tests_or_evals_in_the_plugin_folder():
    stray = sorted(p for p in _plugin_files() if TEST_LIKE.search(p[len(PLUGIN) + 1:]))
    assert not stray, (f"{len(stray)} test or eval file(s) are in the plugin folder, which ships to users and counts "
                       f"toward the directory's {MAX_FILES}-file limit. Move engine tests to tests/engine/, skill "
                       f"tests to tests/skills/ and eval cases to evals/:\n" + "\n".join(stray))


def test_plugin_folder_within_the_file_limit():
    n = len(_plugin_files())
    assert n <= MAX_FILES, f"the plugin folder has {n} files; Anthropic's directory checklist allows {MAX_FILES}"


def test_no_file_over_the_size_limit():
    big = sorted(f"{(REPO / p).stat().st_size} {p}" for p in _plugin_files()
                 if p not in BIG_ON_PURPOSE and (REPO / p).stat().st_size > MAX_BYTES)
    assert not big, f"file(s) in the plugin folder over {MAX_BYTES // 1024} KiB:\n" + "\n".join(big)


def test_plugin_readme_has_40_words():
    readme = REPO / PLUGIN / "README.md"
    assert readme.is_file(), "the plugin folder needs its own README.md (the directory blocks a plugin without one)"
    assert len(readme.read_text(encoding="utf-8").split()) >= 40
