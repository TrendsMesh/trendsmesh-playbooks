"""Every skill and command file's YAML front matter parses with a strict YAML parser (issue #9).

Claude Code skips a skill whose front matter is not valid YAML, without a word: an unquoted `: ` in
organic-video's description once hid the whole playbook. This reads each `skills/*/SKILL.md` and
`commands/*.md` the way a YAML loader does and checks the keys Claude Code needs are strings.
"""

import re

import pytest
import yaml

from tm import paths

PLUGIN = paths.bundled_data().parent
SKILLS = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
COMMANDS = sorted((PLUGIN / "commands").glob("*.md"))
_HEAD = re.compile(r"\A---\n(.*?)\n---\n", re.S)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that also refuses a key given twice (PyYAML keeps the last one without a word)."""


def _no_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    twice = sorted({k for k in keys if keys.count(k) > 1})
    if twice:
        raise yaml.constructor.ConstructorError(None, None, f"key given twice: {', '.join(map(str, twice))}",
                                                node.start_mark)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def front_matter(text: str) -> dict:
    """The front matter of a skill or command file as a dict; raises ValueError or yaml.YAMLError."""
    m = _HEAD.match(text.replace("\r\n", "\n"))
    if not m:
        raise ValueError("no front matter: the file must start with a '---' line, the YAML, and a '---' line")
    data = yaml.load(m.group(1), Loader=_StrictLoader)  # noqa: S506 - a SafeLoader subclass
    if not isinstance(data, dict):
        raise ValueError(f"the front matter is a {type(data).__name__}, not a mapping")
    return data


def _string(data: dict, key: str) -> str:
    value = data.get(key)
    assert isinstance(value, str) and value.strip(), f"{key!r} must be a non-empty string, got {value!r}"
    return value


def test_the_plugin_has_skills_and_commands():
    assert len(SKILLS) >= 5 and len(COMMANDS) >= 2, (SKILLS, COMMANDS)


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_front_matter_is_valid_yaml_with_name_and_description(path):
    data = front_matter(path.read_text(encoding="utf-8"))
    assert _string(data, "name") == path.parent.name
    _string(data, "description")


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.stem)
def test_command_front_matter_is_valid_yaml_with_a_description(path):
    _string(front_matter(path.read_text(encoding="utf-8")), "description")


@pytest.mark.parametrize("head", [
    "name: x\ndescription: built on rising trends: video ideas\n",   # the #9 line: a plain scalar with ': '
    "name: x\nname: y\ndescription: d\n",
    "- name: x\n",
])
def test_the_check_refuses_what_a_yaml_loader_refuses(head):
    with pytest.raises((ValueError, yaml.YAMLError)):
        front_matter(f"---\n{head}---\n\nbody\n")


def test_the_check_refuses_a_file_without_front_matter():
    with pytest.raises(ValueError, match="no front matter"):
        front_matter("# Title\n\nname: x\n")
