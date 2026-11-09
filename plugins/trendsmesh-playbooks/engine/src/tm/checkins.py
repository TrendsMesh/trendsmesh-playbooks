"""The check-in catalogue of each playbook (data/checkins.yaml for refresh-ad) and level routing.

Which level shows which check-in lives in the YAML file only. The engine knows the three
level ids for one purpose: to refuse a catalogue or a level that is not one of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from tm import playbooks, stepchecks
from tm.playbooks import REFRESH_AD

LEVEL_IDS = ("every_step", "big_calls", "hands_off")
ROUTES = ("own", "card", "rule", "stop")
CARD_ASK = ("first", "last", "before_first_spend")
EFFECTS = ("end", "stop", "measure_days", "needs", "skips", "requires")


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    ask: str  # "first" / "last" member's place, or "before_first_spend" (before the first paid step)


@dataclass(frozen=True)
class Checkin:
    id: str
    name: str
    route: dict[str, str]
    rule: str
    card: str | None = None
    choices: tuple[str, ...] | None = None  # allowed choices; None means any
    on_choice: dict[str, dict] = field(default_factory=dict)  # choice -> {EFFECTS}
    stop: dict[str, str] | None = None  # {what, todo} when the route is "stop"
    money: bool = False  # lets money be spent or ads go live: refused while the run is stopped
    rule_guess: str | None = None  # the rule in a run without TrendsMesh data
    yes_for: tuple[str, ...] = ()  # the budget kinds a yes here approves (a money check-in only)

    def rule_for(self, evidence: str | None) -> str:
        return self.rule_guess if evidence == "guess" and self.rule_guess else self.rule


@dataclass(frozen=True)
class Catalogue:
    levels: dict[str, str]  # id -> the name users see
    cards: dict[str, Card]
    checkins: dict[str, Checkin]  # in file order

    def route(self, checkin_id: str, level: str) -> str:
        return self.checkins[checkin_id].route[level]


def default_path(playbook: str = REFRESH_AD) -> Path:
    return playbooks.get(playbook).data_dir / "checkins.yaml"


def validate_level(level: str) -> str:
    if level not in LEVEL_IDS:
        names = load().levels
        options = ", ".join(f"{names[i]} ({i})" for i in LEVEL_IDS)
        raise ValueError(f"{level!r} is not a level. Pick one of: {options}.")
    return level


def _bad(path: Path, what: str) -> ValueError:
    return ValueError(f"{path.name}: {what}")


def _parse(path: Path) -> Catalogue:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    levels = data.get("levels") or {}
    if set(levels) != set(LEVEL_IDS):
        raise _bad(path, f"levels must be exactly {', '.join(LEVEL_IDS)}")
    cards = {}
    for cid, c in (data.get("cards") or {}).items():
        ask = c.get("ask", "last")
        if ask not in CARD_ASK:
            raise _bad(path, f"card {cid}: ask must be one of {', '.join(CARD_ASK)}, not {ask!r}")
        cards[cid] = Card(id=cid, name=c["name"], ask=ask)
    checkins: dict[str, Checkin] = {}
    for raw in data.get("checkins") or []:
        cid = raw["id"]
        if cid in checkins:
            raise _bad(path, f"check-in {cid} is listed twice")
        route = dict(raw.get("route") or {})
        if set(route) != set(LEVEL_IDS):
            raise _bad(path, f"{cid}: route must name every level")
        for level, r in route.items():
            if r not in ROUTES:
                raise _bad(path, f"{cid}: route {r!r} at {level} is not one of {', '.join(ROUTES)}")
        card = raw.get("card")
        if card is not None and card not in cards:
            raise _bad(path, f"{cid}: unknown card {card!r}")
        if "card" in route.values() and card is None:
            raise _bad(path, f"{cid}: routes to a card but names none")
        stop = raw.get("stop")
        if "stop" in route.values() and not (stop and stop.get("what") and stop.get("todo")):
            raise _bad(path, f"{cid}: routes to stop but has no stop.what and stop.todo")
        choices = tuple(raw["choices"]) if raw.get("choices") else None
        on_choice = dict(raw.get("on_choice") or {})
        for choice, effect in on_choice.items():
            if choices is not None and choice not in choices:
                raise _bad(path, f"{cid}: on_choice {choice!r} is not one of its choices")
            if not set(effect) <= set(EFFECTS):
                raise _bad(path, f"{cid}: on_choice {choice!r} has an unknown effect")
            unknown = [n for n in effect.get("requires") or () if n not in stepchecks.NAMES]
            if unknown:
                raise _bad(path, f"{cid}: on_choice {choice!r} requires an unknown check: "
                                 f"{', '.join(unknown)}")
        money = bool(raw.get("money", False))
        yes_for = raw.get("yes_for", [])
        if not (isinstance(yes_for, list) and all(isinstance(k, str) and k for k in yes_for)):
            raise _bad(path, f"{cid}: yes_for must be a list of budget kinds")
        if yes_for and not money:  # its kinds are checked by flow._load_steps (flow imports this module)
            raise _bad(path, f"{cid}: yes_for approves a budget, so it needs money: true")
        checkins[cid] = Checkin(
            id=cid, name=raw["name"], route=route, rule=str(raw["rule"]), card=card,
            choices=choices, on_choice=on_choice, stop=stop, money=money,
            rule_guess=str(raw["rule_guess"]) if raw.get("rule_guess") else None,
            yes_for=tuple(yes_for))
    for c in checkins.values():
        for choice, effect in c.on_choice.items():
            for other, wanted in (effect.get("needs") or {}).items():
                known = checkins.get(other)
                if known is None or (known.choices and wanted not in known.choices):
                    raise _bad(path, f"{c.id}: on_choice {choice!r} needs {other}={wanted}, "
                                     "which is not a check-in choice")
    return Catalogue(levels=dict(levels), cards=cards, checkins=checkins)


@lru_cache(maxsize=None)
def _load_cached(path: Path) -> Catalogue:
    return _parse(path)


def load(path: Path | None = None, *, playbook: str = REFRESH_AD) -> Catalogue:
    """Read and check the catalogue at `path`, else the playbook's. Raises ValueError on a
    malformed file."""
    if path is not None:
        return _parse(Path(path))
    return _load_cached(default_path(playbook))
