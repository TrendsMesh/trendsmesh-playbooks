"""run.json: everything needed to resume a run in a new session."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

from tm.runfolder import RunFolder


@dataclass
class RunState:
    run_id: str
    playbook: str
    created: str
    level: str | None = None
    outputs: list[str] = field(default_factory=list)
    step: str | None = None
    decisions: list[dict] = field(default_factory=list)
    spend: dict[str, float] = field(default_factory=dict)
    budgets: dict[str, float] = field(default_factory=dict)
    approvals: list[dict] = field(default_factory=list)  # each budget approval and the yes behind it
    stops: list[dict] = field(default_factory=list)
    measurements_due: list[str] = field(default_factory=list)
    measurements_done: list[str] = field(default_factory=list)  # ISO dates already measured (E4)
    status: str = "active"
    flows: list[str] = field(default_factory=list)  # variant flows in use, e.g. "V" (VARIANTS.md)
    diagnosis: dict | None = None   # R2, written by `tm diagnose`
    material: str | None = None     # text_cards | vo_captions | talking_head | static, `tm material`
    test_plan: dict | None = None   # R4, written by `tm r4`
    test_estimate: dict | None = None  # R4 worked out early, `tm r4 --estimate`: at intake, after G1a
    ended: str | None = None        # the plain message of a run that ended early (not supported)
    evidence: str | None = None     # trendsmesh | guess: what the changes rest on, `tm evidence`
    evidence_log: list[dict] = field(default_factory=list)  # each change of `evidence`, with why
    register: dict | None = None    # the checked change register: {file, proof, guess}
    recut: dict | None = None       # re-cut edit lists, `tm recut check`: {"checked": [...]}
    previous_run: str | None = None  # the run this one follows (`tm run new --after`), workspace-relative
    pages: dict[str, dict] = field(default_factory=dict)  # local pages, where they were published, awaiting
    schedule: dict | None = None    # how the next run of the playbook is started
    brief: dict | None = None       # creative brief: seed, seed_paid, seed_check, chosen, pages built
    checked: dict[str, dict] = field(default_factory=dict)  # files a check passed on: {key: {file, sha256, at}}
    audience: dict | None = None    # `tm audience`: {hypothesis: {file, at}, file, sha256, pick, formats}
    organic: dict | None = None     # organic video: parent, proposal, channel, seed, seed_check, stack, redos, week
    planned: dict[str, float] = field(default_factory=dict)  # a checked pack's totals per budget kind
    planned_at: str | None = None   # when `planned` was last set: a budget's yes counts from then on


BRIEF_PAGE = "brief_pack"   # the creative brief's page (brief_page.PAGE)


def load(run: RunFolder) -> RunState:
    """run.json as a RunState: unknown keys are left out, and 0.5.0's wait for decisions on the
    brief page (`brief.awaiting`) is moved to where every page keeps it (`pages["brief_pack"]
    ["awaiting"]`, tm.page)."""
    data = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
    known = {f.name for f in fields(RunState)}
    s = RunState(**{k: v for k, v in data.items() if k in known})
    if isinstance(s.brief, dict) and "awaiting" in s.brief:
        waiting = s.brief["awaiting"]
        s.brief = {k: v for k, v in s.brief.items() if k != "awaiting"}
        if isinstance(waiting, dict):
            s.pages = {**s.pages, BRIEF_PAGE: {**(s.pages.get(BRIEF_PAGE) or {}), "awaiting": waiting}}
    return s


def save(run: RunFolder, state: RunState) -> None:
    target = run.path / "run.json"
    tmp = run.path / "run.json.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(state), fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
