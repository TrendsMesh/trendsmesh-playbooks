"""Named checks a step requires before `tm done` (steps.yaml `requires`).

A check-in's choice may require checks too (checkins.yaml `on_choice: {<choice>: {requires:
[...]}}`): `tm decide` runs them before it records that choice.

Each check is a function `(run: RunFolder) -> str | None`: what is still missing, in words that
follow "<step> is done once …", or None when it passes. `NAMES` lists every check a playbook's
steps may require, as "module:function"; the module is imported only when the check runs, so a
step may name a check whose module comes in a later task (it says "not built yet" until then).
A check only reads; it never writes run.json (`tm done` saves the state it loaded before the
checks ran, so a check's own write would be lost).

A check of a file the agent wrote (`tm voice check`, `tm brief check`) records the file it passed
on with `mark`; the step's check then asks `fresh` that the latest version is that same file,
unchanged.
"""

from __future__ import annotations

import hashlib
import importlib
from datetime import datetime, timezone
from pathlib import Path

from tm import state
from tm.runfolder import RunFolder

NAMES: dict[str, str] = {
    "intake_written": "tm.brief_config:intake_gap",
    "audience_picked": "tm.audience:picked_gap",
    "voice_checked": "tm.voice_themes:checked_gap",
    "trends_or_guess": "tm.brief_research:trends_gap",
    "scores_and_saturation": "tm.brief_research:scoring_gap",
    "concepts_checked": "tm.brief_checks:concepts_gap",
    "brief_checked": "tm.brief_checks:brief_gap",
    "production_checked": "tm.brief_checks:production_gap",
    "page_built": "tm.brief_page:built_gap",
    "concepts_chosen": "tm.brief_page:chosen_gap",
    "animatics_rendered": "tm.animatic:rendered_gap",
    "handed_off": "tm.brief:handoff_gap",
    # organic video (playbook 03)
    "organic_intake_written": "tm.organic_config:intake_gap",
    "profile_written": "tm.brand:channel_gap",
    "stack_recorded": "tm.organic:stack_gap",
    "credits_recorded": "tm.organic:credits_gap",
    "profile_confirmed": "tm.brand:confirmed_gap",
    "shortlist_written": "tm.organic_research:shortlist_gap",
    "evidence_saved": "tm.organic_research:evidence_gap",
    "proposals_checked": "tm.organic_proposals:checked_gap",
    "proposals_page_built": "tm.organic_pages.proposals:built_gap",
    "videos_started": "tm.organic_proposals:started_gap",
    "script_checked": "tm.organic_pages.script:checked_gap",
    "script_page_built": "tm.organic_pages.script:built_gap",
    "recipe_written": "tm.organic_pack:recipe_gap",
    "pack_checked": "tm.organic_pack:pack_gap",
    "images_picked": "tm.organic_qa:images_gap",
    "takes_checked": "tm.organic_qa:takes_gap",
    "final_checked": "tm.organic_final:final_gap",
    "sections_covered": "tm.organic_final:sections_gap",
    "kit_checked": "tm.kit:kit_gap",
    "final_page_built": "tm.organic_gates:delivery_gap",
    "week_checked": "tm.organic_week:checked_gap",
    "week_page_built": "tm.organic_pages.week:built_gap",
    "week_in_budget": "tm.organic_week:budget_gap",
    "slots_started": "tm.organic_week:started_gap",
    "week_delivered": "tm.organic_week_delivery:delivered_gap",
}


def run(name: str, folder: RunFolder) -> str | None:
    """The gap the named check finds in the run folder, or None. Raises ValueError for a name not
    in `NAMES`, for a check whose module or function is not built yet, and for a check that
    answers anything but None or a gap in words (an empty one would pass unseen). That last one is
    a bug in the check, not a gap: a plain ValueError (exit 1, one JSON object), never a Stop."""
    if name not in NAMES:
        raise ValueError(f"{name!r} is not a step check. Known: {', '.join(NAMES)}.")
    module, _, function = NAMES[name].partition(":")
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:  # the module exists but something it imports does not
            raise
        raise ValueError(f"{name} is not built yet") from None
    fn = getattr(mod, function, None)
    if fn is None:
        raise ValueError(f"{name} is not built yet")
    gap = fn(folder)
    if gap is not None and not (isinstance(gap, str) and gap.strip()):
        raise ValueError(f"The step check {name} answered {gap!r}: a check gives its gap in words, "
                         "or None when it passes.")
    return gap


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


_sha256 = sha256


def mark(run: RunFolder, key: str, path: Path | str, *, extra: dict | None = None) -> None:
    """Record that the check `key` passed on this file (inside the run folder): its run-relative
    path, sha256 and the time, in run.json `checked[key]`, plus `extra` (what else the check read,
    e.g. the scores a saturation check was made against)."""
    target = Path(path) if Path(path).is_absolute() else run.path / path
    try:
        rel = target.resolve().relative_to(run.path.resolve())
    except ValueError:
        raise ValueError(f"{path} is not inside the run folder {run.path}.") from None
    if not target.is_file():
        raise ValueError(f"{rel.as_posix()} is not a file in the run.")
    s = state.load(run)
    s.checked[key] = {**(extra or {}), "file": rel.as_posix(), "sha256": sha256(target),
                      "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    state.save(run, s)


def fresh(run: RunFolder, key: str, stage: str, stem: str, ext: str) -> str | None:
    """None when `checked[key]` names the latest <stage>/<stem>_vNN.<ext> (in any case: one name on a
    case-blind disk) and it is unchanged since; otherwise the gap."""
    latest = run.latest(stage, stem, ext)
    if latest is None:
        return f"{stage}/{stem}_vNN.{ext} is written and checked"
    entry = state.load(run).checked.get(key)
    if entry is None:
        return f"the latest {stem} is checked"
    try:
        rel = latest.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:  # a link to a file outside the run
        return f"the latest {stem} is a file inside the run folder"
    if str(entry.get("file")).casefold() != rel.casefold() or entry.get("sha256") != sha256(latest):
        return f"the latest {stem} changed after it was checked: run the check again"
    return None
