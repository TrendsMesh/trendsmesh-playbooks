"""Supported changes (data/supported_changes.yaml) and the material check.

`classify_material(teardown)` reads these keys of the teardown dict (Task 10 produces them):
    is_video          bool  - false for a static graphic or carousel
    has_speech        bool  - somebody speaks in the ad
    speech_on_camera  bool  - the speaker is a face on screen (a talking head)
    overlays          list  - on-screen text boxes (text cards, captions); [] when none
Rules: not a video -> static; speech on camera -> talking_head; speech off camera ->
vo_captions; no speech but overlays -> text_cards; nothing at all -> static (no supported edit).
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from tm import cli, paths, state
from tm.runfolder import RunFolder

Material = Literal["text_cards", "vo_captions", "talking_head", "static"]
MATERIALS = ("text_cards", "vo_captions", "talking_head", "static")
MATERIAL_NAMES = {"text_cards": "text cards", "vo_captions": "voiceover with captions",
          "talking_head": "talking head", "static": "static graphic"}
STAGES = {"hook": "the opening", "middle": "the middle", "promise_cta": "the promise or call to action",
           "fatigue": "image fatigue", "landing": "the landing page", "account": "the whole account",
           "auction": "the auction"}
RECUT_STAGE = "middle"  # the re-cuts of path C-R (flow R); their ids are an edit list's change_id


@dataclass(frozen=True)
class Change:
    id: str
    layer: str
    method: str
    summary: str
    stage: str | None = None
    materials: tuple[str, ...] = ()


@lru_cache(maxsize=None)
def _load_file(path: Path) -> tuple[tuple[Change, ...], tuple[Change, ...]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    staged = tuple(Change(c["id"], c["layer"], c["method"], c["summary"], c["stage"], tuple(c["materials"]))
                   for c in data["changes"])
    always = tuple(Change(c["id"], c["layer"], c["method"], c["summary"]) for c in data["always"])
    return staged, always


def _load() -> tuple[tuple[Change, ...], tuple[Change, ...]]:
    return _load_file(paths.bundled_data() / "supported_changes.yaml")


def _check(material: str | None) -> None:
    if material is not None and material not in MATERIALS:
        raise ValueError(f"Unknown material {material!r}: use one of {', '.join(MATERIALS)}.")


def for_stage(stage: str, material: str | None) -> list[Change]:
    """The stage's own edits for this material; `material=None` asks only about the stage.

    The edits open to every stage (`always`) are not included: a run whose only options are
    those has nothing to change and ends.
    """
    _check(material)
    staged, _ = _load()
    return [c for c in staged if c.stage == stage and (material is None or material in c.materials)]


def recut_ids() -> list[str]:
    """The ids of the re-cut changes (stage middle), in file order: the change_id values an edit
    list may name (`tm recut check`)."""
    return [c.id for c in _load()[0] if c.stage == RECUT_STAGE]


def always() -> list[Change]:
    return _load()[1]


def classify_material(teardown: dict) -> Material:
    if not isinstance(teardown, dict) or "is_video" not in teardown:
        raise ValueError("The teardown lacks is_video, so the material cannot be classified.")
    if not teardown["is_video"]:
        return "static"
    if teardown.get("has_speech"):
        return "talking_head" if teardown.get("speech_on_camera") else "vo_captions"
    return "text_cards" if teardown.get("overlays") else "static"


def unsupported_message(stage: str, material: str | None, spent: bool = False) -> str:
    """The plain end: what happened, what it means, and that nothing was spent (when true)."""
    staged = _load()[0]
    if material and not any(c.stage == stage and material in c.materials for c in staged) \
            and any(c.stage == stage for c in staged):
        if any(material in c.materials for c in staged):  # a talking head: only its middle is re-cut
            what = (f"This ad is a {MATERIAL_NAMES[material]}, and refreshing {STAGES.get(stage, stage)} of a "
                    f"{MATERIAL_NAMES[material]} isn't supported yet.")
        else:
            what = (f"This ad is a {MATERIAL_NAMES[material]}, and refreshing a {MATERIAL_NAMES[material]} "
                    f"isn't supported yet.")
    else:
        what = (f"The diagnosis points at {STAGES.get(stage, stage)}, and refreshing that "
                f"isn't supported yet.")
    money = ("nothing was spent" if not spent
             else "what was already spent stays counted and nothing more is spent")
    return (f"{what} This run ends here and {money}. The diagnosis report is saved in "
            "the run folder (04_final) for you to use.")


def stage_supported(stage: str, material: str | None = None) -> bool:
    return bool(for_stage(stage, material))


@dataclass(frozen=True)
class Resolution:
    kind: str                 # ok | unsupported | no_refresh
    target: str | None        # the stage to refresh (ok only)
    message: str = ""         # the plain reason (unsupported, no_refresh)
    note: str = ""            # why the target differs from the main stage


def resolve(stage: str, also_seen: list[str], refresh: bool, material: str | None,
            spent: bool = False) -> Resolution:
    """Which stage the refresh targets, or why the run cannot go on.

    The run is unsupported only when no stage in {stage} + also_seen has a supported edit for the
    material. If the main stage has none but an also-seen stage has, that one is the target.
    """
    if not refresh:
        return Resolution("no_refresh", None, (
            f"The diagnosis points at {STAGES.get(stage, stage)}, which is not fixed by "
            "refreshing the creative (R2)."))
    for candidate in [stage, *also_seen]:
        if for_stage(candidate, material):
            note = "" if candidate == stage else (
                f"{stage} is not supported yet for this ad, so the refresh targets {candidate}, "
                "which was also seen in the data.")
            return Resolution("ok", candidate, note=note)
    return Resolution("unsupported", None, unsupported_message(stage, material, spent))


def record_material(run: RunFolder, material: str) -> None:
    _check(material)
    if material is None:
        raise ValueError("Say which material it is.")
    s = state.load(run)
    if s.status == "done":
        raise ValueError("This run is done; the material can no longer be changed.")
    s.material = material
    if s.diagnosis:  # the refresh target depends on the material
        from tm import r2
        r2.retarget(s)
    state.save(run, s)


def _setup_material(p: argparse.ArgumentParser) -> None:
    p.add_argument("material", nargs="?", choices=MATERIALS, help="the material, when Claude already decided")
    p.add_argument("--teardown", help="a teardown JSON file: classify it")
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--json", action="store_true")


def _run_material(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.material:
            material = args.material
        elif args.teardown:
            material = classify_material(json.loads(Path(args.teardown).read_text(encoding="utf-8")))
        else:
            return cli.fail(args, "Give the material or --teardown <file>.")
        record_material(run, material)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    cli.emit(args, {"status": "done", "material": material}, f"Material: {material}")
    return 0


def _setup_changes(p: argparse.ArgumentParser) -> None:
    p.add_argument("--stage", required=True)
    p.add_argument("--material", choices=MATERIALS)
    p.add_argument("--json", action="store_true")


def _run_changes(args: argparse.Namespace) -> int:
    try:
        listed = for_stage(args.stage, args.material)
    except ValueError as exc:
        return cli.fail(args, str(exc))
    extra = always()
    payload = {"status": "done", "stage": args.stage, "material": args.material,
               "supported": bool(listed),
               "changes": [c.__dict__ | {"materials": list(c.materials)} for c in listed],
               "always": [c.__dict__ | {"materials": list(c.materials)} for c in extra],
               "message": None if listed else unsupported_message(args.stage, args.material)}
    text = "\n".join(f"{c.id}: {c.summary}" for c in [*listed, *extra]) if listed else payload["message"]
    cli.emit(args, payload, text)
    return 0


cli.register("material", _setup_material, _run_material)
cli.register("changes", _setup_changes, _run_changes)
