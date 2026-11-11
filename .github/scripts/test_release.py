import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import release  # noqa: E402
from release import ReleaseError, main, notes, parse_tag, prepare  # noqa: E402

CHANGELOG_RC = """# Changelog

What changed in each version.

## Unreleased

- **Report an issue.** Ask Claude to report a problem.
- **Developed in the open.**

## 0.9.2

- **A failed tools install says why.**
"""

CHANGELOG_RELEASE = CHANGELOG_RC.replace("## Unreleased", "## 0.10.0")


def make_root(tmp_path, version="0.10.0-rc.1", changelog=CHANGELOG_RC, skip=()):
    plugin = tmp_path / "plugins/trendsmesh-playbooks"
    files = {
        ".claude-plugin/plugin.json": json.dumps({"name": "trendsmesh-playbooks", "version": version}, indent=2),
        "engine/pyproject.toml": f'[project]\nname = "tm"\nversion = "{version}"\n',
        "engine/src/tm/__init__.py": f'"""tm."""\n\n__version__ = "{version}"\n',
        "engine/tests/test_cli.py": f'def test_version(capsys):\n    assert out == "tm {version}"\n',
    }
    for rel, text in files.items():
        if rel in skip:
            continue
        (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
        (plugin / rel).write_text(text, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("tag,expected", [
    ("v0.10.0", ("0.10.0", False)),
    ("v0.10.0-rc.1", ("0.10.0-rc.1", True)),
    ("v1.0.12-rc.10", ("1.0.12-rc.10", True)),
])
def test_parse_tag(tag, expected):
    assert parse_tag(tag) == expected


@pytest.mark.parametrize("tag", ["0.10.0", "v0.10", "v0.10.0-rc", "v0.10.0-rc.0", "v0.10.0-beta.1",
                                 "v01.0.0", "v0.10.0 ", "v0.10.0-rc.1\n", "release-0.10.0"])
def test_parse_tag_refuses(tag):
    with pytest.raises(ReleaseError):
        parse_tag(tag)


def test_rc_notes_are_the_unreleased_section():
    assert notes(CHANGELOG_RC, "0.10.0-rc.1", True) == (
        "- **Report an issue.** Ask Claude to report a problem.\n- **Developed in the open.**\n")


def test_release_notes_are_its_own_section():
    assert notes(CHANGELOG_RELEASE, "0.10.0", False).startswith("- **Report an issue.**")


def test_last_section_runs_to_the_end():
    assert notes(CHANGELOG_RELEASE, "0.9.2", False) == "- **A failed tools install says why.**\n"


def test_release_refuses_a_leftover_unreleased():
    text = CHANGELOG_RELEASE.replace("# Changelog\n", "# Changelog\n\n## Unreleased\n\n- later\n")
    with pytest.raises(ReleaseError, match="still has ## Unreleased"):
        notes(text, "0.10.0", False)


def test_missing_section_refused():
    with pytest.raises(ReleaseError, match="exactly one ## 0.11.0"):
        notes(CHANGELOG_RELEASE, "0.11.0", False)


def test_dated_heading_is_not_the_section():
    with pytest.raises(ReleaseError, match="exactly one"):
        notes(CHANGELOG_RELEASE.replace("## 0.10.0", "## 0.10.0 (2026-11-12)"), "0.10.0", False)


def test_duplicate_section_refused():
    with pytest.raises(ReleaseError, match="found 2"):
        notes(CHANGELOG_RC + "\n## Unreleased\n\n- again\n", "0.10.0-rc.1", True)


def test_empty_section_refused():
    with pytest.raises(ReleaseError, match="is empty"):
        notes("## Unreleased\n\n\n## 0.9.2\n\n- x\n", "0.10.0-rc.1", True)


def test_prepare_rc(tmp_path):
    outputs, text = prepare("v0.10.0-rc.1", make_root(tmp_path))
    assert outputs == {"version": "0.10.0-rc.1", "prerelease": "true", "title": "0.10.0-rc.1"}
    assert text.startswith("- **Report an issue.**")


def test_prepare_release(tmp_path):
    outputs, _ = prepare("v0.10.0", make_root(tmp_path, "0.10.0", CHANGELOG_RELEASE))
    assert outputs["prerelease"] == "false"


def test_prepare_names_each_wrong_place(tmp_path):
    root = make_root(tmp_path)
    init = root / "plugins/trendsmesh-playbooks/engine/src/tm/__init__.py"
    init.write_text('__version__ = "0.9.2"\n', encoding="utf-8")
    with pytest.raises(ReleaseError) as e:
        prepare("v0.10.0-rc.1", root)
    assert "engine/src/tm/__init__.py (0.9.2)" in str(e.value)
    assert "plugin.json" not in str(e.value)


def test_prepare_missing_place_is_wrong(tmp_path):
    root = make_root(tmp_path, skip=("engine/tests/test_cli.py",))
    with pytest.raises(ReleaseError, match=r"test_cli.py \(None\)"):
        prepare("v0.10.0-rc.1", root)


def test_prepare_unreadable_json_is_wrong(tmp_path):
    root = make_root(tmp_path)
    (root / "plugins/trendsmesh-playbooks/.claude-plugin/plugin.json").write_text("{", encoding="utf-8")
    with pytest.raises(ReleaseError, match=r"plugin.json \(None\)"):
        prepare("v0.10.0-rc.1", root)


def test_prepare_plugin_json_not_an_object(tmp_path):
    root = make_root(tmp_path)
    (root / "plugins/trendsmesh-playbooks/.claude-plugin/plugin.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ReleaseError, match=r"plugin.json \(None\)"):
        prepare("v0.10.0-rc.1", root)


def test_heading_inside_a_code_block_is_not_a_heading():
    text = "## Unreleased\n\n- a\n```\n## not a heading\n```\n- b\n\n## 0.9.2\n\n- x\n"
    assert notes(text, "0.10.0-rc.1", True) == "- a\n```\n## not a heading\n```\n- b\n"


def test_crlf_changelog():
    assert notes(CHANGELOG_RC.replace("\n", "\r\n"), "0.10.0-rc.1", True).startswith("- **Report an issue.**")


def test_prepare_tag_for_another_version(tmp_path):
    with pytest.raises(ReleaseError, match="not 0.10.0-rc.2"):
        prepare("v0.10.0-rc.2", make_root(tmp_path))


def test_main_writes_notes_and_outputs(tmp_path, capsys):
    out = tmp_path / "notes.md"
    assert main(["prepare", "v0.10.0-rc.1", str(make_root(tmp_path / "r")), str(out)]) == 0
    assert capsys.readouterr().out.splitlines() == ["version=0.10.0-rc.1", "prerelease=true", "title=0.10.0-rc.1"]
    assert out.read_text(encoding="utf-8").startswith("- **Report an issue.**")


def test_main_failure_writes_nothing(tmp_path, capsys):
    out = tmp_path / "notes.md"
    assert main(["prepare", "v0.11.0", str(make_root(tmp_path / "r")), str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "release.py:" in captured.err
    assert not out.exists()


def test_main_usage():
    assert main(["notes"]) == 2


def test_the_repositorys_own_release_files_parse():
    """The real four places and CHANGELOG.md, as they stand: each version readable and all the same."""
    root = Path(__file__).resolve().parents[2]
    found = release.versions(root)
    assert None not in found.values() and len(set(found.values())) == 1
    assert "## Unreleased" in (root / "CHANGELOG.md").read_text(encoding="utf-8") or \
        f"## {next(iter(found.values()))}" in (root / "CHANGELOG.md").read_text(encoding="utf-8")
