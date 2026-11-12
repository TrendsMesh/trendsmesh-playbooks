"""Every file in the repository keeps its path, from the repository's root, within MAX_PATH characters (issue 76).

Windows refuses a path longer than 260 characters unless long paths are switched on, and most laptops don't have
them on. Claude Code puts a plugin's marketplace clone under the user's profile, for example
`C:\\Users\\<name>\\.claude\\plugins\\marketplaces\\trendsmesh\\`, and a ZIP is often unpacked in the temp folder, which
is longer still. With a long user name that prefix alone is well over 100 characters, so a path inside the
repository of more than MAX_PATH characters can make `git clone` fail with "Filename too long".

The check reads `git ls-files`, so it covers every committed file and every new file not yet committed (but not
git-ignored ones). Outside a git checkout (an installed plugin, a ZIP) it is skipped."""

import shutil
import subprocess
from pathlib import Path

import pytest

MAX_PATH = 90  # characters, from the repository's root; the one place this limit is set

REPO = Path(__file__).resolve().parents[4]


def _repo_files() -> list[str]:
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return [p for p in r.stdout.split("\0") if p]


def too_long(paths: list[str], limit: int = MAX_PATH) -> list[str]:
    return sorted((p for p in paths if len(p) > limit), key=lambda p: (-len(p), p))


def explain(long: list[str], limit: int = MAX_PATH) -> str:
    lines = [f"{len(p)} {p}" for p in long]
    return (f"{len(long)} path(s) in the repository are longer than {limit} characters. On Windows, Claude Code's "
            f"plugin folders and the user's profile come in front of each path, and Windows stops at 260 characters, "
            f"so the clone fails with 'Filename too long'. Shorten them (an eval case: a shorter case name; a mock is "
            f"named after its tool, so shorten the case or its fixtures):\n" + "\n".join(lines))


def test_every_path_in_the_repository_is_short_enough_for_windows():
    long = too_long(_repo_files())
    assert not long, explain(long)


def test_the_check_names_each_long_path_and_says_why():
    ok = "plugins/trendsmesh-playbooks/evals/short/case.yaml"
    bad = "plugins/trendsmesh-playbooks/evals/" + "a_very_long_case_name_" * 3 + "/graders/x.md"
    assert too_long([ok, bad]) == [bad]
    text = explain([bad])
    assert bad in text and str(len(bad)) in text
    assert "260" in text and "Windows" in text and str(MAX_PATH) in text


def test_the_repository_root_is_the_one_with_the_plugin():
    assert (REPO / "plugins" / "trendsmesh-playbooks" / "engine" / "tests" / "test_path_lengths.py").is_file()
