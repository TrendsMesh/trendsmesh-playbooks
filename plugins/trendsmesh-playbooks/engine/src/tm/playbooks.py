"""The playbook registry (data/playbooks.yaml): each playbook's name, skill and data folder.

A run's playbook is its run folder id (`01-refresh-ad`), which run.json stores as `playbook`, so
a run saved before the registry existed needs no migration.

A playbook is offered (`tm run new`, `tm doctor`) only once its skill is bundled
(`skills/<skill>/SKILL.md`): the registry and the engine can ship before the skill does.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from tm import paths

REFRESH_AD = "01-refresh-ad"
CREATIVE_BRIEF = "02-creative-brief"
ORGANIC_VIDEO = "03-organic-ai-video"
TREND_RESEARCH = "04-trend-research"
CREATE_AD = "05-create-ad"
_FIELDS = ("id", "name", "skill", "data")


@dataclass(frozen=True)
class Playbook:
    id: str
    name: str
    skill: str
    data_dir: Path  # holds its steps.yaml and checkins.yaml
    guess: bool = False  # it may run without live trend data (guess mode)
    budgets: tuple[str, ...] = ()  # the budget kinds it spends from (checked against flow.BUDGET_KINDS)


def _registry_path() -> Path:
    return paths.bundled_data() / "playbooks.yaml"


@lru_cache(maxsize=None)
def _load(path: Path) -> tuple[Playbook, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("playbooks") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path.name}: `playbooks` must be a list of rows")
    out: list[Playbook] = []
    for n, raw in enumerate(rows, 1):
        if not (isinstance(raw, dict) and all(isinstance(raw.get(k), str) and raw[k].strip()
                                              for k in _FIELDS)):
            raise ValueError(f"{path.name}: row {n} ({raw!r}) needs {', '.join(_FIELDS)}, "
                             "each a non-empty text")
        if not isinstance(raw.get("guess", False), bool):
            raise ValueError(f"{path.name}: row {n} ({raw!r}): guess must be true or false")
        budgets = raw.get("budgets", [])
        if not (isinstance(budgets, list) and all(isinstance(k, str) and k.strip() for k in budgets)):
            raise ValueError(f"{path.name}: row {n} ({raw!r}): budgets must be a list of budget kinds, "
                             "each a non-empty text")
        pb = Playbook(id=raw["id"], name=raw["name"], skill=raw["skill"],
                      data_dir=paths.bundled_data() / raw["data"], guess=raw.get("guess", False),
                      budgets=tuple(budgets))
        if any(pb.id in (o.id, o.skill) or pb.skill in (o.id, o.skill) for o in out):
            raise ValueError(f"{path.name}: playbook {pb.id} ({pb.skill}) is listed twice")
        out.append(pb)
    return tuple(out)


def all_playbooks() -> list[Playbook]:
    return list(_load(_registry_path()))


def skills_root() -> Path:
    """The plugin's skills/ folder, found next to its data/ (the same plugin version)."""
    return paths.bundled_data().parent / "skills"


def bundled(pb: Playbook) -> bool:
    """Whether the playbook's skill ships in this plugin version (what `offered` requires). Text that
    names playbooks to the user names only these."""
    return (skills_root() / pb.skill / "SKILL.md").is_file()


def offered(key: str) -> Playbook:
    """The playbook with this id or skill name, once its skill is bundled. Raises ValueError
    for an unknown playbook, and for one whose skill comes in a later plugin version."""
    pb = get(key)
    if not bundled(pb):
        raise ValueError(f"{pb.name} comes in a later version of this plugin. Check that the "
                         "plugin is up to date.")
    return pb


def get(key: str) -> Playbook:
    """The playbook with this id (`01-refresh-ad`) or skill name (`refresh-ad`)."""
    known = all_playbooks()
    for pb in known:
        if key in (pb.id, pb.skill):
            return pb
    names = ", ".join(f"{pb.id} ({pb.skill})" for pb in known)
    raise ValueError(f"{key!r} is not a playbook. Known: {names}.")
