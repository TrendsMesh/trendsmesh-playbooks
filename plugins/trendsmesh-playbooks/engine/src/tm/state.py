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
    trendsmesh_mode: str | None = None  # free | paid for this run only (`tm mode free --run R`), else the workspace's
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
    ad: dict | None = None          # create an ad: the user's redo requests for a video item (`tm ad redo`)


BRIEF_PAGE = "brief_pack"   # the creative brief's page (brief_page.PAGE)
CREATIVE_BRIEF = "02-creative-brief"   # tm.playbooks.CREATIVE_BRIEF (playbooks reads data this module must not)
LEGACY_ANIMATICS = "animatics"         # a creative brief output before issue #145 (brief_config.LEGACY_OUTPUTS)
# A run started before issue #145 made its animatics at D2, between D1 and D3; D2 now comes after D3 (the
# animatics on request). Steps the old D2 is behind, and the step an old run at D2 goes back to.
_PAST_OLD_D2 = ("D3", "E1", "E2", "end")   # "end": tm.flow.END


def load(run: RunFolder) -> RunState:
    """run.json as a RunState: unknown keys are left out, 0.5.0's wait for decisions on the
    brief page (`brief.awaiting`) is moved to where every page keeps it (`pages["brief_pack"]
    ["awaiting"]`, tm.page), and a creative brief started before issue #145 is read in the new flow
    (`_before_animatics_on_request`)."""
    data = json.loads((run.path / "run.json").read_text(encoding="utf-8-sig"))
    known = {f.name for f in fields(RunState)}
    s = RunState(**{k: v for k, v in data.items() if k in known})
    if s.playbook == CREATIVE_BRIEF and LEGACY_ANIMATICS in s.outputs:
        _before_animatics_on_request(s)
    if isinstance(s.brief, dict) and "awaiting" in s.brief:
        waiting = s.brief["awaiting"]
        s.brief = {k: v for k, v in s.brief.items() if k != "awaiting"}
        if isinstance(waiting, dict):
            s.pages = {**s.pages, BRIEF_PAGE: {**(s.pages.get(BRIEF_PAGE) or {}), "awaiting": waiting}}
    return s


def _before_animatics_on_request(s: RunState) -> None:
    """A creative brief run started before issue #145 (its outputs list `animatics`), read in the new flow: the
    legacy output is left out (the briefs make the animatics now, on request); a run at the old D2 (its briefs
    written, the page with them not built yet) is at D3, which now comes first; and a run whose animatics the old
    D2 made already (at D3 or later) has them recorded as the `animatics` check-in's `make`, for the concepts it
    chose, so it is never asked again. A recorded G2 needs nothing: it is no check-in now, and the flow reads
    past it."""
    s.outputs = [o for o in s.outputs if o != LEGACY_ANIMATICS]
    if s.step == "D2":
        s.step = "D3"
        return
    past = s.step in _PAST_OLD_D2 or s.status == "done"
    if past and not any(isinstance(d, dict) and d.get("checkin") == "animatics" for d in s.decisions):
        chosen = ((s.brief or {}).get("chosen") or {}).get("concepts") if isinstance(s.brief, dict) else None
        s.decisions.append({"checkin": "animatics", "choice": "make", "by": "rule",
                            "rule": "made at D2 with the briefs, in a run started before animatics were on request",
                            "note": "legacy run: its animatics were made with its briefs",
                            **({"concepts": list(chosen)} if isinstance(chosen, list) and chosen else {}),
                            "legacy": True})


def save(run: RunFolder, state: RunState) -> None:
    target = run.path / "run.json"
    tmp = run.path / "run.json.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(state), fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
