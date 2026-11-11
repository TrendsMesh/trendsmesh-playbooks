"""Checks a release tag against the commit it names, and writes the release notes (RELEASING.md).

    python3 .github/scripts/release.py prepare TAG ROOT NOTES_OUT

ROOT is a checkout of the tagged commit. On success it prints three lines for $GITHUB_OUTPUT
(version=, prerelease=, title=) and writes the notes to NOTES_OUT; on any problem it prints why to
stderr and exits 1, and writes nothing. Where the commit sits (dev or main) is the workflow's check.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

TAG = re.compile(r"v(?P<version>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?P<rc>-rc\.[1-9]\d*)?)")
PLUGIN = Path("plugins/trendsmesh-playbooks")


class ReleaseError(Exception):
    pass


def parse_tag(tag: str) -> tuple[str, bool]:
    """`v0.10.0-rc.1` -> ("0.10.0-rc.1", True); `v0.10.0` -> ("0.10.0", False)."""
    m = TAG.fullmatch(tag)
    if not m:
        raise ReleaseError(f"{tag!r} is not a release tag: vX.Y.Z or vX.Y.Z-rc.N")
    return m["version"], m["rc"] is not None


def versions(root: Path) -> dict[str, str | None]:
    """The version in each of the four places RELEASING.md lists, None where it can't be read."""
    def read(rel: Path) -> str | None:
        try:
            return (root / rel).read_text(encoding="utf-8")
        except OSError:
            return None

    def plugin_json(text):
        data = json.loads(text)
        return data.get("version") if isinstance(data, dict) else None

    def pyproject(text):
        project = tomllib.loads(text).get("project")
        return project.get("version") if isinstance(project, dict) else None

    def init(text):
        m = re.search(r'^__version__ = "([^"]+)"', text, re.M)
        return m and m[1]

    def test_cli(text):
        m = re.search(r'== "tm ([^"]+)"', text)
        return m and m[1]

    places = {
        PLUGIN / ".claude-plugin/plugin.json": plugin_json,
        PLUGIN / "engine/pyproject.toml": pyproject,
        PLUGIN / "engine/src/tm/__init__.py": init,
        PLUGIN / "engine/tests/test_cli.py": test_cli,
    }
    found = {}
    for rel, parse in places.items():
        text = read(rel)
        try:
            found[rel.as_posix()] = parse(text) if text is not None else None
        except (ValueError, tomllib.TOMLDecodeError):
            found[rel.as_posix()] = None
    return found


def notes(changelog: str, version: str, prerelease: bool) -> str:
    """The changelog section being released, without its heading: `## Unreleased` for a release
    candidate, `## X.Y.Z` for a release, which must no longer have an Unreleased section."""
    headings, fenced = [], False
    for i, line in enumerate(changelog.splitlines()):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif line.startswith("## ") and not fenced:
            headings.append((i, line))
    titles = [line[3:].strip() for _, line in headings]
    want = "Unreleased" if prerelease else version
    if not prerelease and "Unreleased" in titles:
        raise ReleaseError("CHANGELOG.md still has ## Unreleased: a release turns it into ## " + version)
    if titles.count(want) != 1:
        raise ReleaseError(f"CHANGELOG.md needs exactly one ## {want} heading, found {titles.count(want)}")
    lines = changelog.splitlines()
    start = next(i for i, line in headings if line[3:].strip() == want) + 1
    end = next((i for i, _ in headings if i >= start), len(lines))
    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ReleaseError(f"CHANGELOG.md's ## {want} section is empty")
    return body + "\n"


def prepare(tag: str, root: Path) -> tuple[dict[str, str], str]:
    version, prerelease = parse_tag(tag)
    wrong = {place: found for place, found in versions(root).items() if found != version}
    if wrong:
        raise ReleaseError(f"the version is not {version} in: "
                           + ", ".join(f"{place} ({found})" for place, found in wrong.items()))
    try:
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError as e:
        raise ReleaseError(f"cannot read CHANGELOG.md: {e}") from None
    outputs = {"version": version, "prerelease": str(prerelease).lower(), "title": version}
    return outputs, notes(changelog, version, prerelease)


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[0] != "prepare":
        print("usage: release.py prepare TAG ROOT NOTES_OUT", file=sys.stderr)
        return 2
    _, tag, root, out = argv
    try:
        outputs, text = prepare(tag, Path(root))
    except ReleaseError as e:
        print(f"release.py: {e}", file=sys.stderr)
        return 1
    Path(out).write_text(text, encoding="utf-8")
    for key, value in outputs.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
