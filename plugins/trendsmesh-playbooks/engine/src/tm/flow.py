"""The step engine: which step comes next, whether a check-in pauses for the user or goes by
rule at the run's level, decisions and stops.

Each playbook has its own steps.yaml and checkins.yaml (data/playbooks.yaml says where); a run's
playbook is run.json's `playbook`. Refresh an ad's own checks (G1a's block, budgets, the R4 plan,
evidence at A5, the register at A7, the launch, the results library) run only for its runs
(`_pb01`). Guess mode (`tm evidence`) is open to every playbook with `guess: true`, each within
its own window of steps (`_EVIDENCE_WINDOW`).

Everything is derived from run.json, so a run resumed in a new session, days later, gets the
same answer. The life of a step:

1. check-ins listed `before` the step are asked first (G11 before activation);
2. `next` returns `work` for the step (with the check-in that will follow it, if any);
3. Claude does the work and calls `complete` (`tm done <step>`), which moves the run on once
   the checks the step `requires` (tm.stepchecks) pass; a gap is a `stops.Stop` (exit 2);
4. `next` then returns the check-ins `after` the finished step, one at a time, as `ask` (show
   it), `auto` (decide by rule, record it with `decide --by rule --note`) or `stop`;
5. once nothing is pending, `next` returns `work` for the following step, or `done`.

Stops come in two kinds:
- raised by Claude through `stop` (a missing file, a sign-in): they hold until `resume`;
- raised by the engine (a voice check in Hands-off, a red R8 item, a measurement not due yet,
  an R4 plan that cannot reach the minimum events): `next` re-derives them and lets the run go
  on once their cause is gone.

While any stop is open, money waits (`refuse_if_held`): `tm budget approve` and `tm budget
spend`, a paid `tm tool`, and the decisions marked `money` in checkins.yaml (the spending
check-ins, the launch, the results) are refused with exit 2, except what the stop itself is
about. The live test goes ahead only on a feasible R4 plan, and E3 only with its spend booked.
"""

from __future__ import annotations

import builtins
import copy
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from tm import changes, checkins, evidence, library, playbooks, state, stepchecks, stops
from tm.playbooks import CREATIVE_BRIEF, REFRESH_AD
from tm.runfolder import RunFolder

Action = Literal["work", "ask", "auto", "stop", "done"]
END = "end"  # run.json `step` once every step's work is done
CONTINUES = "The run continues from the same place afterwards."
NOT_DUE = "measurement_not_due"
BUDGET_KINDS = ("ai_usd", "voice_credits", "test")
_BUDGET_STOP = {
    "ai_usd": ("The AI video needs a budget, and Hands-off does not spend money without one.",
               "Tell Claude how much it may spend on AI generation, in US dollars."),
    "voice_credits": ("The new voiceover line needs a voice budget, and Hands-off does not spend "
                      "money without one.",
                      "Tell Claude how many ElevenLabs credits it may use."),
    "test": ("The live test needs a budget, and Hands-off does not spend money without one.",
             "Tell Claude how much to spend per day and for how many days."),
}
# A playbook other than refresh-ad that declares `budgets` (data/playbooks.yaml): the words of the
# stop at a spending step whose planned amount is not approved yet, per kind.
_PACK_TODO = ("Show the user the pack's cost and record their yes at \"Approve the generation "
              "pack and its cost\"; then approve the amount with `tm budget approve`.")
PLANNED_STOP = {
    "ai_usd": ("The pack's AI generation cost is not approved yet, so nothing was generated or paid.",
               _PACK_TODO),
    "voice_credits": ("The pack's voice credits are not approved yet, so nothing was generated or "
                      "paid.", _PACK_TODO),
}
_KIND = {"own": "ask", "rule": "auto", "stop": "stop"}
_first = builtins.next  # `next` below is the engine's, not the builtin

# The live test's seams the engine holds itself (final review I2, I4, I5).
SPENDING_CHECKIN = {"voice_credits": "VB", "ai_usd": "G6", "test": "G10"}  # budget kind -> its yes
RECUT_BUDGET = "RB"  # flow R's spending check-in: a yes for both ai_usd and voice_credits
_YES_FOR = {"voice_credits": ("VB", RECUT_BUDGET), "ai_usd": ("G6", RECUT_BUDGET), "test": ("G10",)}
RECUT_FLOW = "R"
RECUT_AFTER = "C1"  # flow R's steps follow the method selection
PLAN_STOP = "test_plan_infeasible"  # R4 cannot reach the minimum events at this budget
ESTIMATE_STOP = "test_estimate_infeasible"  # R4's estimate on the chosen ad (after G1a) cannot either
CAPTION_STEP = "VC"  # caption removal: its ProPainter cents may be approved there, before G6 (issue #21)
VIDEO_ACCEPTANCE = ("C4", "CR7", "D5")  # a video made in the run: the live test can be added for it
ESTIMATE_STEP = "A2"  # the step after "Accept the diagnosis" (G1a): R4 is estimated on the chosen ad here
DESIGN_STEP, LAUNCH_STEP, LAUNCH = "E1", "E3", "G11"
# Guess mode: what the changes rest on is recorded at A5, the register checked at A7.
TREND_STEP, REGISTER_STEP = "A5", "A7"
_EVIDENCE_STEPS = ("A5", "A6", "A7")  # a run resumed without evidence (an older run) is told here
# Per guess playbook (data/playbooks.yaml `guess: true`): the evidence is recorded before `tm done`
# of the first step (a switch to TrendsMesh after it needs the trends saved), and can change
# until the second is done. Creative brief: B3 finds the trends (its `trends_or_guess` check),
# C1 makes the concepts that rest on them.
_EVIDENCE_WINDOW = {REFRESH_AD: (TREND_STEP, REGISTER_STEP), CREATIVE_BRIEF: ("B3", "C1")}
# Playbooks whose level and outputs are chosen on a later step's card, not in A0's intake batch:
# the steps before it are done without them (creative brief: the user gives only the product, and
# A1's card, checked by `intake_written`, holds the level and the outputs). The message per step.
_LATE_INTAKE = {CREATIVE_BRIEF: ("A1", {
    "A0": ("Check readiness (the doctor), then finish with `tm done A0`. Ask nothing yet: the intake asks the user "
           "only which product, at A1, and the level and the outputs are chosen on A1's intake card."),
    "A1": ("Ask the user only which product to brief (one pick list from the ad account; a landing link only when "
           "neither the ads, the ad sets' Pixel nor the Ad Library gives one), then show the intake card, with the level of involvement and the outputs on it. "
           "`tm config write` records them with the rest of the card; then finish with `tm done A1`."),
})}
_EVIDENCE_FIRST = ("First record what this run's changes rest on: `tm evidence trendsmesh --run R "
                   "--why <reason>` when TrendsMesh answers with trend data, or `tm evidence guess "
                   "--run R --why <reason>` when it does not (no Agent plan, not signed in, or the user "
                   "said no). A guess run goes on, with the changes labelled as guesses.")
_PLAN_TODO = ("Tell Claude which way to go: raise the daily budget, allow more days, test fewer "
              "variants (Claude plans again with `tm r4`), or skip the live test.")
_ESTIMATE_TODO = ("Tell Claude which way to go: a higher daily budget or more days (Claude records them with "
                  "`tm live-test budget --run R --per-day <amount> --days <days>` and estimates again with "
                  "`tm r4 --estimate`), or skip the live test (`tm live-test drop --run R`). The other "
                  "outputs are not affected.")
_ESTIMATE_FIRST = ("The live test is in this run: first estimate it on the chosen ad (R4, issue #22): its latest "
                   "window from the ranking as a file, then `tm r4 --estimate --run R --stage <target_stage> "
                   "--control <that file> --variants <n> --json`, and tell the user the budget and days it "
                   "needs.")
_LIVE_TEST_OFFER = (
    "The live test is not part of this run. End the final report with one question: \"Do you want to test "
    "this against the original?\" (a Meta A/B test of the new video against the original ad, decided after "
    "7 to 14 days; nothing is spent or published before the user approves the test plan and the launch). On a "
    "yes, ask for the daily budget and the days (no amount is assumed) and run `tm live-test add --run R "
    "--per-day <amount> --days <days>` (in Hands-off with `--note \"<their words>\"`): the run reopens at the "
    "test design (E1).")


class Held(ValueError):
    """Refused because the run is stopped (exit 2): nothing was spent, approved or decided."""


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    outputs: tuple[str, ...]
    checkins: tuple[str, ...]  # asked after the step's work
    before: tuple[str, ...]  # asked before the step's work
    spends: bool  # the step's own work costs money
    ref: str
    flow: str | None = None  # variant flow (VARIANTS.md) the step belongs to
    targets: tuple[str, ...] = ()  # diagnosis target stages the step serves; () serves every one
    measures: bool = False  # done once per measurement date
    budget: str | None = None  # the budget kind the step spends from (BUDGET_KINDS)
    skip_when: tuple[tuple[str, str], ...] = ()  # (check-in, choice): the step is skipped on it
    requires: tuple[str, ...] = ()  # engine checks (stepchecks.NAMES) that pass before `tm done`


@dataclass
class CheckinView:
    ids: list[str]
    name: str
    card: str | None
    rule: str
    choices: list[str] | None = None


@dataclass
class NextStep:
    step: str
    title: str
    ref: str
    action: Action
    checkin: CheckinView | None
    message: str | None
    notice: str | None = None  # show it to the user, in their words: a run without TrendsMesh data


# --- data ---------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_steps(steps_path: Path, checkins_path: Path,
                budgets: tuple[str, ...] = ()) -> tuple[tuple[str, ...], tuple[Step, ...]]:
    """The playbook's outputs and steps, checked against its check-ins. `budgets` are the
    playbook's budget kinds (data/playbooks.yaml), the only ones a check-in's `yes_for` may name:
    checked here, since tm.checkins cannot import this module."""
    data = yaml.safe_load(steps_path.read_text(encoding="utf-8")) or {}
    outputs = tuple(data.get("outputs") or ())
    cat = checkins.load(checkins_path)
    for c in cat.checkins.values():
        unknown = [k for k in c.yes_for if k not in BUDGET_KINDS or k not in budgets]
        if unknown:
            raise ValueError(f"{checkins_path.name}: {c.id}: yes_for names {', '.join(unknown)}, which is "
                             f"not a budget kind of this playbook ({', '.join(budgets) or 'none'})")
    out: list[Step] = []
    seen_steps: set[str] = set()
    seen_checkins: set[str] = set()
    for raw in data.get("steps") or []:
        st = Step(id=raw["id"], title=raw["title"], outputs=tuple(raw["outputs"]),
                  checkins=tuple(raw.get("checkins") or ()), before=tuple(raw.get("before") or ()),
                  spends=bool(raw["spends"]), ref=raw["ref"], flow=raw.get("flow"),
                  measures=bool(raw.get("measures", False)), budget=raw.get("budget"),
                  skip_when=tuple((k, v) for k, v in (raw.get("skip_when") or {}).items()),
                  targets=tuple(raw.get("targets") or ()), requires=tuple(raw.get("requires") or ()))
        unknown = [name for name in st.requires if name not in stepchecks.NAMES]
        if unknown:
            raise ValueError(f"{steps_path.name}: step {st.id} requires an unknown check: "
                             f"{', '.join(unknown)}")
        if not set(st.targets) <= set(changes.STAGES):
            raise ValueError(f"{steps_path.name}: step {st.id} targets an unknown stage")
        if st.budget is not None and (st.budget not in BUDGET_KINDS or not st.spends):
            raise ValueError(f"{steps_path.name}: step {st.id} has an unknown budget or does not spend")
        for cid, choice in st.skip_when:
            allowed = cat.checkins[cid].choices if cid in cat.checkins else ()
            if not allowed or choice not in allowed:
                raise ValueError(f"{steps_path.name}: step {st.id}: skip_when {cid}={choice} is not a choice")
        if st.id in seen_steps or st.id == END:
            raise ValueError(f"{steps_path.name}: step {st.id} is listed twice or uses a reserved id")
        if not st.outputs or not set(st.outputs) <= set(outputs):
            raise ValueError(f"{steps_path.name}: step {st.id} names an unknown output")
        for cid in st.before + st.checkins:
            if cid not in cat.checkins or cid in seen_checkins:
                raise ValueError(f"{steps_path.name}: step {st.id}: check-in {cid} is unknown or listed twice")
            seen_checkins.add(cid)
        seen_steps.add(st.id)
        out.append(st)
    missing = set(cat.checkins) - seen_checkins
    if missing:
        raise ValueError(f"{steps_path.name}: no step has {', '.join(sorted(missing))}")
    return outputs, tuple(out)


def _playbook_data(playbook: str) -> tuple[tuple[str, ...], tuple[Step, ...]]:
    pb = playbooks.get(playbook)
    unknown = [k for k in pb.budgets if k not in BUDGET_KINDS]
    if unknown:
        raise ValueError(f"playbooks.yaml: {pb.id} lists an unknown budget kind: {', '.join(unknown)} "
                         f"(the kinds are {', '.join(BUDGET_KINDS)})")
    folder = pb.data_dir
    return _load_steps(folder / "steps.yaml", folder / "checkins.yaml", pb.budgets)


def steps(playbook: str = REFRESH_AD) -> list[Step]:
    """Every step of the playbook in order; for refresh-ad, FLOWS.md A0-E4 with flow V's steps
    before the render."""
    return list(_playbook_data(playbook)[1])


def output_ids(playbook: str = REFRESH_AD) -> list[str]:
    return list(_playbook_data(playbook)[0])


def flows(playbook: str = REFRESH_AD) -> set[str]:
    return {st.flow for st in steps(playbook) if st.flow}


def _pb01(s: state.RunState) -> bool:
    """The run is a Refresh an ad run: its own checks (see the module's docstring) apply."""
    return s.playbook == REFRESH_AD


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- the derived picture of a run ---------------------------------------------

@dataclass
class _Item:
    kind: str  # ask | auto | stop
    ids: list[str]
    point: int  # due once the current step index reaches this
    step: int  # index of the step it is shown with
    order: int
    card: str | None = None
    stop: dict | None = None
    blocking: bool = False  # a decision whose choice stops the run (E2b red)


@dataclass
class _Run:
    s: state.RunState
    cat: checkins.Catalogue
    app: list[Step]  # the steps that apply to the run's outputs and flows
    p: int  # index of the current step in `app`; len(app) once all work is done
    owner: dict[str, tuple[int, bool]] = field(default_factory=dict)  # cid -> (step, before)
    latest: dict[str, dict] = field(default_factory=dict)  # check-in -> latest decision

    def route(self, cid: str) -> str:
        return self.cat.route(cid, self.s.level)

    def own_place(self, cid: str) -> tuple[int, int]:
        i, before = self.owner[cid]
        return (i if before else i + 1), i

    def card_members(self, card: str) -> list[str]:
        return [cid for cid in self.owner
                if self.cat.checkins[cid].card == card and self.route(cid) == "card"]

    def card_place(self, card: str) -> tuple[int, int]:
        mode = self.cat.cards[card].ask
        places = [self.own_place(m) for m in self.card_members(card)]
        if mode == "before_first_spend":
            # at the earlier of the first spending step and the first member's own place
            k = _first((i for i, st in enumerate(self.app) if st.spends), None)
            if k is not None:
                return min(places + [(k, k)], key=lambda x: (x[0], -x[1]))
            mode = "last"
        return min(places) if mode == "first" else max(places)

    def place(self, cid: str) -> tuple[int, int]:
        if self.route(cid) == "card":
            return self.card_place(self.cat.checkins[cid].card)
        return self.own_place(cid)

    def items(self) -> list[_Item]:
        found: list[_Item] = []
        cards: dict[str, _Item] = {}
        for order, cid in enumerate(self.cat.checkins):
            if cid not in self.owner:
                continue
            c = self.cat.checkins[cid]
            last = self.latest.get(cid)
            if last is not None:
                effect = c.on_choice.get(last["choice"], {})
                if "stop" in effect:
                    point, step = self.own_place(cid)
                    found.append(_Item("stop", [cid], point, step, order,
                                       stop=effect["stop"], blocking=True))
                continue
            r = self.route(cid)
            if r == "card":
                item = cards.get(c.card)
                if item is None:
                    point, step = self.card_place(c.card)
                    item = cards[c.card] = _Item("ask", [], point, step, order, card=c.card)
                    found.append(item)
                item.ids.append(cid)
            else:
                point, step = self.own_place(cid)
                found.append(_Item(_KIND[r], [cid], point, step, order,
                                   stop=c.stop if r == "stop" else None))
        return sorted(found, key=lambda i: (i.point, i.order))

    def due(self) -> list[_Item]:
        return [i for i in self.items()
                if i.point <= self.p or (i.blocking and i.step <= self.p)]

    def coming(self) -> _Item | None:
        return _first((i for i in self.items() if i.point == self.p + 1 and not i.blocking), None)


def flow_on(s: state.RunState, flow_id: str) -> bool:
    """Whether the run uses a variant flow: turned on with `tm flow`, or, for flow R, a stored
    diagnosis whose target stage is the middle (a middle run always re-cuts; controller ruling,
    Task 11 fix round 2)."""
    if flow_id in s.flows:
        return True
    return flow_id == RECUT_FLOW and (s.diagnosis or {}).get("target_stage") == changes.RECUT_STAGE


def _applies(st: Step, s: state.RunState) -> bool:
    """The step meets the run's outputs and flows, and serves the diagnosis's target stage. A step
    with `targets` applies as before while no target is known (before A1a, a run of 0.2.x, or a
    diagnosis with no supported target); once one is, only when it is in the list."""
    if not (set(s.outputs) & set(st.outputs)) or (st.flow is not None and not flow_on(s, st.flow)):
        return False
    target = (s.diagnosis or {}).get("target_stage")
    return not st.targets or target is None or target in st.targets


def _picture(s: state.RunState) -> _Run:
    cat = checkins.load(playbook=s.playbook)
    every = steps(s.playbook)
    position = {st.id: i for i, st in enumerate(every)}
    chosen: dict[str, str] = {}
    for d in s.decisions:
        chosen[d.get("checkin")] = d.get("choice")
    app: list[Step] = []
    kept: list[tuple[Step, list[str]]] = []  # a skipped step's `before` check-ins that skipped it
    for st in every:
        if not _applies(st, s):
            continue
        by = [cid for cid, choice in st.skip_when if chosen.get(cid) == choice]
        if by:
            kept.append((st, [cid for cid in st.before if cid in by]))
        else:
            app.append(st)
    if s.step is None:
        p = 0
    elif s.step == END:
        p = len(app)
    elif s.step in position:
        g = position[s.step]
        p = _first((i for i, st in enumerate(app) if position[st.id] >= g), len(app))
    else:
        raise ValueError(f"run.json names an unknown step {s.step!r}.")
    run = _Run(s=s, cat=cat, app=app, p=p)
    for i, st in enumerate(app):
        for cid in st.before:
            run.owner[cid] = (i, True)
        for cid in st.checkins:
            run.owner[cid] = (i, False)
    for st, cids in kept:  # still decided (and changeable) where the skipped step would be
        i = _first((k for k, a in enumerate(app) if position[a.id] >= position[st.id]), len(app))
        for cid in cids:
            run.owner[cid] = (i, True)
    for d in s.decisions:
        if d.get("checkin") in cat.checkins:
            run.latest[d["checkin"]] = d
    return run


def _pointer(run: _Run) -> str:
    return run.app[run.p].id if run.p < len(run.app) else END


def _pending_measurements(s: state.RunState) -> list[str]:
    done = set(s.measurements_done)
    return sorted(d for d in s.measurements_due if d not in done)


def _budget_gap(s: state.RunState, st: Step) -> str | None:
    """Hands-off spends only inside an approved budget: the kind this step lacks, if any.

    Flow R's paid steps (CR5a, CR5b) never wait (controller ruling, Task 11): a re-cut's money is
    fenced per variant by `tm recut check` (an L3-L5 edit list waits without its budget) and by
    the tools' budget guard, so the free L0-L2 variants render and the paid ones stay waiting
    (FLOWS.md: AUTO "ends at the free outputs ... and leaves the paid steps as waiting")."""
    if not _pb01(s):
        return planned_gap(s) if st.spends else None
    if st.flow == RECUT_FLOW:
        return None
    if s.level == "hands_off" and st.budget and not s.budgets.get(st.budget):
        return st.budget
    return None


def planned_stop(kind: str) -> tuple[str, str]:
    """(what, todo) of the stop for a planned amount of `kind` that is not approved yet (`PLANNED_STOP`)."""
    return PLANNED_STOP.get(kind) or (
        f"The pack's {kind} amount is not approved yet, so nothing was generated or paid.", _PACK_TODO)


def planned_gap(s: state.RunState, kinds: tuple[str, ...] | None = None) -> str | None:
    """A playbook that declares budgets (organic video's pack): the first of `kinds` (default: every kind it
    declares) whose planned amount (run.json `planned`) is above 0 and not approved in full, or None. A planned
    amount waits at every level: the spending steps (`_budget_gap`) and organic video's generation guard."""
    for kind in kinds if kinds is not None else playbooks.get(s.playbook).budgets:
        planned = s.planned.get(kind, 0)
        if planned > 0 and s.budgets.get(kind, 0) + 1e-9 < planned:
            return kind
    return None


def _plan_gap(pic: _Run) -> str | None:
    """R4 (final review I4): the live test is still going ahead, on a plan that cannot reach the
    minimum events. The words of the stop, or None."""
    plan = pic.s.test_plan
    if (not _pb01(pic.s) or not plan or plan.get("feasible")
            or not any(st.id == LAUNCH_STEP for st in pic.app)):
        return None
    return ("The live test cannot collect enough results at this budget, so nothing is approved "
            f"or launched for it. {plan.get('calculation') or ''}").strip()


def _estimate_gap(pic: _Run) -> str | None:
    """R4's estimate on the chosen ad (issue #22): the live test is still going ahead, no plan is written yet
    (E1), and the estimate cannot reach the minimum events at the budget the user gave. The words of the stop,
    or None. The rough estimate at the intake (the account's numbers, the ad not chosen) never stops the run."""
    s = pic.s
    est = s.test_estimate
    if (not _pb01(s) or not est or est.get("basis") != "ad" or est.get("feasible") or s.test_plan
            or not any(st.id == LAUNCH_STEP for st in pic.app)):
        return None
    return ("The live test cannot collect enough results at the budget you gave, worked out on the chosen ad's "
            f"numbers. {est.get('calculation') or ''}").strip()


def estimate_recorded(run: RunFolder) -> None:
    """After `tm r4 --estimate`, `tm live-test budget` or `tm live-test drop`: hold the run on an estimate that
    cannot reach the minimum events, or clear that hold once it can (or the live test is out)."""
    s = state.load(run)
    gap = _estimate_gap(_picture(s)) if s.outputs else None
    if gap:
        _hold(s, ESTIMATE_STOP, gap, _ESTIMATE_TODO)
    else:
        for x in _open_stops(s):
            if x["reason_id"] == ESTIMATE_STOP:
                x["resumed_at"] = _now()
        if s.status == "stopped" and not _open_stops(s):
            s.status = "active"
    state.save(run, s)


def live_test_gap(s: state.RunState, pic: _Run | None = None) -> str | None:
    """Why the live test cannot be added to this run now (issue #22), or None when it can: a Refresh an ad run
    without it, not ended early, with a video made (or still to be made) to test against the original."""
    if not _pb01(s):
        return _other_playbook(s, "The live test is")
    if s.level is None or not s.outputs:
        return "Finish the intake first: pick the live test there, with its daily budget and days."
    if "live_test" in s.outputs:
        return "The live test is already part of this run."
    if _ended_early(s):
        return "This run ended before its changes were made, so there is no new video to test."
    pic = pic or _picture(s)
    if not any(st.id in VIDEO_ACCEPTANCE for st in pic.app):
        return ("No video is made in this run (no edited or AI video, or it was skipped), so there is nothing "
                "to test against the original.")
    return None


def _need_plan(s: state.RunState, what: str) -> None:
    """A live test is designed, approved and launched only on a feasible R4 plan."""
    plan = s.test_plan
    if not plan:
        raise ValueError(f"{what} needs R4's test plan first: run `tm r4 --run R --stage "
                         "<target_stage> --control <window file> --variants <n> --json` and show "
                         "its calculation to the user.")
    if not plan.get("feasible"):
        raise Held(f"{what} cannot go ahead: the live test cannot collect enough results at this "
                   f"budget. {plan.get('calculation') or ''} {_PLAN_TODO} {CONTINUES}")


def plan_recorded(run: RunFolder) -> None:
    """After `tm r4`: hold the run on a plan that cannot reach the minimum events, or clear that
    hold once a new plan can."""
    s = state.load(run)
    gap = _plan_gap(_picture(s)) if s.outputs else None
    if gap:
        _hold(s, PLAN_STOP, gap, _PLAN_TODO, checkin=SPENDING_CHECKIN["test"])
    else:
        for x in _open_stops(s):
            if x["reason_id"] == PLAN_STOP:
                x["resumed_at"] = _now()
        if s.status == "stopped" and not _open_stops(s):
            s.status = "active"
    state.save(run, s)


def approval_gap(s: state.RunState, kind: str, note: str | None, for_step: str | None = None) -> str | None:
    """Why a budget of `kind` cannot be approved now (final review I5), or None.

    The user's yes is: their answer (not `reject`) at a spending check-in for the kind (G6 or
    the re-cut's RB for ai_usd, VB or RB for voice_credits, G10 for the test); or a stop that
    asked them for this budget (Hands-off's missing budget, an exceeded budget, an R4 plan); or,
    when no check-in in the run asks for the kind (VC's ProPainter), their own words in `note`.
    Caption removal at VC (issue #21) may also be approved before G6 is reached: `for_step` "VC",
    while the run is at VC, with the user's words in `note`; it adds VC's amount to the kind's
    running total and approves nothing for the AI video (G6 asks for that, later, with the total).
    A no at every such check-in of the run refuses it. Hands-off's intake budgets are approved by
    the intake itself. Another playbook's run has no budgets."""
    if not _pb01(s) and playbooks.get(s.playbook).budgets:
        return _planned_approval_gap(s, kind, note)
    other = _other_playbook(s, "Budgets are")
    if other:
        return other
    if s.level is None or not s.outputs:
        return "Finish the intake first: the level and the outputs are not set yet."
    pic = _picture(s)
    if for_step is not None:
        return _caption_gap(s, pic, kind, note, for_step)
    cids = [c for c in _YES_FOR[kind] if c in pic.owner] or [SPENDING_CHECKIN[kind]]
    last = {c: pic.latest.get(c) for c in cids}
    if any(d and d.get("by") == "user" and d.get("choice") != "reject" for d in last.values()):
        return None
    open_ = sorted((c for c in cids if not last[c]),  # not decided yet, the earliest asked first
                   key=lambda c: pic.owner.get(c, (len(pic.app), True)))
    said_no = [c for c in cids if last[c] and last[c].get("choice") == "reject"]
    if said_no and not open_:
        cid = said_no[0]
        name = pic.cat.checkins[cid].name
        return (f"The user said no to this spending at \"{name}\" ({cid}), so no {kind} budget "
                f"can be approved. If they change their mind, record it first with `tm decide "
                f"{cid} approve --change`.")
    if any(_stop_kind(x) == kind for x in _open_stops(s)):
        return None
    cid = (open_ or cids)[0]
    name = pic.cat.checkins[cid].name
    if cid not in pic.owner:
        if note and note.strip():
            return None
        return (f"No check-in in this run asks for the {kind} budget, so approving it needs the "
                "user's own yes: ask them with the estimate, then pass their words with "
                "`--note \"<their words>\"`.")
    if s.level == "hands_off":
        return ("At Hands-off the budgets come from the intake. A new amount is approved only "
                "when the run stops for that budget, after the user says how much.")
    at_vc = kind == "ai_usd" and pic.p < len(pic.app) and pic.app[pic.p].id == CAPTION_STEP
    if at_vc:
        return (f"\"{name}\" ({cid}) comes later, after the edited video. For the caption removal here, "
                "show the estimate, ask the user, and record their yes for this amount alone: `tm budget "
                "approve --run R ai_usd <total> --for VC --note \"<their words>\"` (`<total>`: the ai_usd "
                f"already approved plus this amount). {cid} later approves the AI video's amount on top.")
    return (f"Ask \"{name}\" ({cid}) first and record the user's yes with `tm decide {cid} "
            "approve`; then approve the amount they agreed to.")


def _caption_gap(s: state.RunState, pic: _Run, kind: str, note: str | None, for_step: str) -> str | None:
    """`approval_gap` for caption removal's own yes at VC (issue #21), or None."""
    if for_step != CAPTION_STEP or kind != "ai_usd":
        return (f"Only the caption removal at {CAPTION_STEP} (ProPainter, ai_usd) is approved on its own "
                f"with --for; {kind} at {for_step} is approved at its spending check-in.")
    if s.level == "hands_off":
        return ("At Hands-off the caption removal uses the AI budget given at intake. Without one, take the "
                "free way and list its defect in the final report.")
    if pic.p >= len(pic.app) or pic.app[pic.p].id != CAPTION_STEP:
        return (f"The caption removal is approved with --for {CAPTION_STEP} only while the run is at "
                f"{CAPTION_STEP}; the run is at {_pointer(pic)}.")
    if not (note and note.strip()):
        return ("Approving the caption removal needs the user's own yes: show them the estimate (and the free "
                "way with its known defect), ask, then pass their words with `--note \"<their words>\"`.")
    return None


def _utc(text: str) -> datetime:
    """An ISO time; one without a time zone is read as UTC (`_now()` writes aware UTC times)."""
    at = datetime.fromisoformat(text)
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _planned_approval_gap(s: state.RunState, kind: str, note: str | None) -> str | None:
    """`approval_gap` for a playbook that declares budgets (organic video's pack): the yes is the
    user's answer (not `reject`) at a check-in whose `yes_for` holds `kind`, recorded at or after
    the latest re-plan (`s.planned_at`). A stop never approves: a pack re-checked to a higher cost
    waits for `tm decide <check-in> approve --change`. With no such check-in in the run, the
    user's own words in `note` are the yes."""
    pb = playbooks.get(s.playbook)
    if kind not in pb.budgets:
        return f"{pb.name} has no {kind} budget."
    if s.level is None or not s.outputs:
        return "Finish the intake first: the level and the outputs are not set yet."
    pic = _picture(s)
    cids = [cid for cid, c in pic.cat.checkins.items() if kind in c.yes_for and cid in pic.owner]
    if not cids:
        if note and note.strip():
            return None
        return (f"No check-in in this run asks for the {kind} budget, so approving it needs the "
                "user's own yes: ask them with the estimate, then pass their words with "
                "`--note \"<their words>\"`.")
    since = _utc(s.planned_at) if s.planned_at else None
    stale, said_no, open_ = [], [], []
    for cid in cids:
        d = pic.latest.get(cid)
        if not d or d.get("by") != "user":
            open_.append(cid)
        elif d.get("choice") == "reject":
            said_no.append(cid)
        elif since and _utc(d["at"]) < since:
            stale.append(cid)
        else:
            return None

    def name(cid: str) -> str:
        return pic.cat.checkins[cid].name

    if stale:
        cid = stale[0]
        return (f"The pack was checked again after the user's yes at \"{name(cid)}\" ({cid}), so "
                f"that yes no longer counts. Show them the new cost and record it with `tm decide "
                f"{cid} approve --change`.")
    if open_:
        cid = open_[0]
        return (f"Ask \"{name(cid)}\" ({cid}) first and record the user's yes with `tm decide "
                f"{cid} approve`; then approve the amount they agreed to.")
    cid = said_no[0]
    return (f"The user said no to this spending at \"{name(cid)}\" ({cid}), so no {kind} budget "
            f"can be approved. If they change their mind, record it first with `tm decide "
            f"{cid} approve --change`.")


# --- stops --------------------------------------------------------------------

def _open_stops(s: state.RunState) -> list[dict]:
    return [x for x in s.stops if "resumed_at" not in x]


def _hold(s: state.RunState, reason: str, what: str, todo: str, checkin: str | None = None) -> None:
    """Keep the run stopped for an engine-raised reason, recording it once. `checkin` names the
    check-in whose decision may still be recorded while it holds (G10 for an R4 plan stop)."""
    open_ = _open_stops(s)
    if not any(x["reason_id"] == reason for x in open_):
        entry = {"reason_id": reason, "what": what, "todo": todo, "at": _now(), "engine": True}
        if checkin:
            entry["checkin"] = checkin
        s.stops.append(entry)
    for x in open_:
        if x.get("engine") and x["reason_id"] != reason:
            x["resumed_at"] = _now()
    s.status = "stopped"


def _release(s: state.RunState) -> None:
    """Engine-raised stops whose cause is gone are resolved."""
    for x in _open_stops(s):
        if x.get("engine"):
            x["resumed_at"] = _now()
    if s.status == "stopped":
        s.status = "active"


def _stop_message(what: str, todo: str) -> str:
    return f"{what} {todo} {CONTINUES}"


def _stop_kind(x: dict) -> str | None:
    """The budget kind a stop is about (a missing or exceeded budget, an R4 plan), or None."""
    reason = x["reason_id"]
    for kind in BUDGET_KINDS:
        if reason in (f"budget_{kind}", f"over_budget_{kind}"):
            return kind
    return "test" if reason in (PLAN_STOP, ESTIMATE_STOP) else None


def refuse_if_held(s: state.RunState, refused: str, *, kind: str | None = None,
                   checkin: str | None = None) -> None:
    """Raise Held while the run has an open stop (final review I1). A stop about `kind`'s budget
    lets that budget be approved; a stop about `checkin` lets that check-in be decided."""
    for x in _open_stops(s):
        if kind is not None and _stop_kind(x) == kind:
            continue
        if checkin is not None and checkin in (x["reason_id"], x.get("checkin")):
            continue
        if x.get("engine"):
            how = ("the decision, the budget or the date that removes its cause clears it; then "
                   "run `tm next`")
        else:
            how = "once the user has acted, run `tm resume`, then `tm next`"
        raise Held(f"The run is stopped, so {refused}. {_stop_message(x['what'], x['todo'])} "
                   f"To go on: {how}.")


def _resolve(s: state.RunState, ids: list[str]) -> None:
    """Engine stops about these check-ins are cleared by their new decision."""
    for x in _open_stops(s):
        if x.get("engine") and (x["reason_id"] in ids or x.get("checkin") in ids):
            x["resumed_at"] = _now()
    if s.status == "stopped" and not _open_stops(s):
        s.status = "active"


# --- views --------------------------------------------------------------------

def _view(run: _Run, item: _Item) -> CheckinView:
    cat = run.cat
    if item.card:
        card = cat.cards[item.card]
        rule = "; ".join(f"{cid}: {cat.checkins[cid].rule_for(run.s.evidence)}" for cid in item.ids)
        shared = {cat.checkins[cid].choices for cid in item.ids}  # one list when every member has it
        only = shared.pop() if len(shared) == 1 else None
        return CheckinView(ids=list(item.ids), name=card.name, card=card.id, rule=rule,
                           choices=list(only) if only else None)
    c = cat.checkins[item.ids[0]]
    return CheckinView(ids=[c.id], name=c.name, card=None, rule=c.rule_for(run.s.evidence),
                       choices=list(c.choices) if c.choices else None)


def _member_commands(cat: checkins.Catalogue, ids: list[str]) -> str | None:
    """The card's members' own `tm decide` commands, in order, when no one answer fits them all
    (organic video's plan: taste takes accept, pack approve or reject); else None."""
    lists = [cat.checkins[cid].choices for cid in ids]
    restricted = [set(x) for x in lists if x]  # a member without choices takes any answer
    if not restricted or set.intersection(*restricted):
        return None
    return ", then ".join(
        " or ".join(f"`tm decide {cid} {ch}`" for ch in choices) if choices
        else f"`tm decide {cid} <choice>`" for cid, choices in zip(ids, lists))


def _item_message(view: CheckinView, kind: str, stop: dict | None,
                  cat: checkins.Catalogue) -> str:
    choices = f" Choices: {', '.join(view.choices)}." if view.choices else ""
    if kind == "stop":
        return _stop_message(stop["what"], stop["todo"])
    if kind == "auto":
        cid = view.ids[0]
        return (f"Decide {cid} ({view.name}) by the rule \"{view.rule}\" and record it with "
                f"`tm decide {cid} <choice> --by rule --note <the data behind it>`.{choices}")
    each = _member_commands(cat, view.ids) if view.card else None
    if each:
        return (f"Show the check-in \"{view.name}\" to the user and record the answer for each "
                f"check-in it covers, in order: {each} (each takes `--note ...`). No one answer "
                f"fits them all, so the card {view.card} is not decided as one.")
    target = view.card or view.ids[0]
    covers = f" It covers {', '.join(view.ids)}." if view.card else ""
    return (f"Show the check-in \"{view.name}\" to the user and record the answer with "
            f"`tm decide {target} <choice> [--note ...]`.{covers}{choices}")


def _step_view(st: Step, action: Action, message: str, checkin: CheckinView | None = None) -> NextStep:
    return NextStep(step=st.id, title=st.title, ref=st.ref, action=action, checkin=checkin,
                    message=message)


def _late_step(s: state.RunState) -> Step | None:
    """The current step while a late-intake playbook's level or outputs are not set yet, else None."""
    if s.playbook not in _LATE_INTAKE or (s.level is not None and s.outputs):
        return None
    every = steps(s.playbook)
    return _first((st for st in every if st.id == s.step), every[0]) if s.step else every[0]


def _intake(s: state.RunState) -> NextStep:
    late = _late_step(s)
    if late is not None:
        return _step_view(late, "work", _LATE_INTAKE[s.playbook][1][late.id])
    first = steps(s.playbook)[0]
    names = checkins.load(playbook=s.playbook).levels
    levels = ", ".join(f"{names[i]} (`{i}`)" for i in checkins.LEVEL_IDS)
    return _step_view(first, "work", (
        f"Ask the intake questions in one batch, including \"How involved do you want to be?\": "
        f"{levels}. Record the level with `tm level <id>` and the outputs with the intake "
        f"config, then finish with `tm done {first.id}`."))


def _done(run: _Run) -> NextStep:
    every = steps(run.s.playbook)
    if run.s.ended:  # ended early: the refresh is not supported (A1a or A3)
        owner = _first((st for st in every if st.id == ("A3" if run.s.material else "A1a")), every[-1])
        return _step_view(owner, "done", run.s.ended)
    for d in reversed(run.s.decisions):
        c = run.cat.checkins.get(d.get("checkin"))
        effect = c.on_choice.get(d.get("choice"), {}) if c else {}
        if "end" in effect:
            owner = _first(st for st in every if c.id in st.checkins + st.before)
            return _step_view(owner, "done", effect["end"])
    last = run.app[-1] if run.app else every[-1]
    offer = [_LIVE_TEST_OFFER] if _pb01(run.s) and live_test_gap(run.s, run) is None else []
    return _step_view(last, "done", " ".join(["Every step of this run is done.", *_skip_notes(run), *offer]))


def _skip_notes(run: _Run) -> list[str]:
    """The plain notes of the choices that skipped steps (a reject, keep_paused), in order."""
    notes = []
    for cid, d in run.latest.items():
        note = run.cat.checkins[cid].on_choice.get(d.get("choice"), {}).get("skips")
        if note and note not in notes:
            notes.append(note)
    return notes


def _blocking(s: state.RunState) -> changes.Resolution | None:
    """Why the run cannot go on to research and spend: the diagnosis says not to refresh, or no
    stage seen (main or also seen) has a supported edit for the material. None when it can."""
    d = s.diagnosis
    if not _pb01(s) or not d:
        return None
    spent = any(v for v in s.spend.values())
    res = changes.resolve(d["stage"], d.get("also_seen", []), d.get("refresh", False), s.material, spent)
    return None if res.kind == "ok" else res


def _blocking_ask(run: RunFolder, s: state.RunState, res: changes.Resolution, today: date | None = None) -> NextStep:
    """G1a alone, immediately, recommending do_not_refresh; Hands-off decides it by rule."""
    pic = _picture(s)
    cat = pic.cat
    c = cat.checkins["G1a"]
    owner = _first((st for st in steps() if st.id == ("A3" if s.material else "A1a")), steps()[0])
    again = ""
    if "G1a" in pic.latest and "end" not in c.on_choice.get(pic.latest["G1a"]["choice"], {}):
        again = " G1a was decided before the data changed: record it again with `--change`."
    view = CheckinView(ids=["G1a"], name=c.name, card=None, rule=c.rule, choices=["do_not_refresh"])
    if pic.route("G1a") == "rule":
        action: Action = "auto"
        how = (f"Record it with `tm decide G1a do_not_refresh --by rule --note \"{res.message}\"`.")
    else:
        action = "ask"
        how = ("Show it to the user, recommend do_not_refresh, and record the answer with "
               "`tm decide G1a do_not_refresh`.")
    message = (f"{res.message} {how} Any other answer is refused while this stands: a corrected "
               "`tm diagnose` or `tm material` is the way out." + again)
    return _step_view(owner, action, message, view)


def _library_gap(run: RunFolder, s: state.RunState, pic: _Run) -> str | None:
    """R5: a live test that was activated is closed only once the results library has a row for
    each variant. A test that never launched (G11 not `activate`) has nothing to record."""
    if not _pb01(s) or "live_test" not in s.outputs or not s.measurements_due:
        return None
    plan = s.test_plan or {}
    need = max(int(plan.get("variants") or 0), 1)  # a launch needs R4's plan, so it is stored
    here = run.path.resolve()                 # `--run .` has no parents or name until resolved
    have = library.variants_for_run(here.parents[2], here.name)
    if len(have) >= need:
        return None
    missing = need - len(have)
    return (f"The results library has {len(have)} of {need} variants for run \"{here.name}\" "
            f"({missing} missing; seen: {', '.join(have) or 'none'}). R5: write one row per "
            f"variant as JSON, each with its own `variant` id, and add it with "
            f"`tm library add --run {run.path} --row <file>` (that fills `run` with exactly "
            f"\"{here.name}\"), then run `tm next`. A repeat of the same variant counts once. "
            f"The run closes after that; it continues from the same place.")


def _current_step(s: state.RunState) -> Step:
    every = steps(s.playbook)
    if s.level is None or not s.outputs:
        return _late_step(s) or every[0]
    pic = _picture(s)
    return pic.app[pic.p] if pic.p < len(pic.app) else (pic.app[-1] if pic.app else every[-1])


def _ending_hints(run: _Run, st_index: int) -> str:
    hints = []
    for cid, (i, _before) in run.owner.items():
        if i != st_index or cid in run.latest:
            continue
        for choice, effect in run.cat.checkins[cid].on_choice.items():
            if "end" in effect:
                hints.append(f" If the result is {choice}, record it straight away with "
                             f"`tm decide {cid} {choice} --by rule --note <the data behind it>`: "
                             "the run then ends here, before anything is spent.")
    return "".join(hints)


# --- public API ---------------------------------------------------------------

def next(run: RunFolder, *, today: date | None = None) -> NextStep:  # noqa: A001 - the plan's name
    """What Claude does now. Records engine stops; a stop raised with `stop` holds until `resume`."""
    today = today or date.today()
    s = state.load(run)
    before = copy.deepcopy(asdict(s))

    def finish(result: NextStep) -> NextStep:
        if asdict(s) != before:
            state.save(run, s)
        return _with_notice(s, result)

    if s.status == "done":
        return _with_notice(s, _done(_picture(s)))
    held = [x for x in _open_stops(s) if not x.get("engine")]
    if s.status == "stopped" and held:
        last = held[-1]
        return _step_view(_current_step(s), "stop", (
            f"{_stop_message(last['what'], last['todo'])} Once the user has done it, run "
            "`tm resume`, then `tm next`."))
    if s.level is None or not s.outputs:
        return finish(_intake(s))
    block = _blocking(s)
    if block:
        return finish(_blocking_ask(run, s, block))
    pic = _picture(s)
    s.step = _pointer(pic)
    gap = _plan_gap(pic)
    if gap:
        _hold(s, PLAN_STOP, gap, _PLAN_TODO, checkin=SPENDING_CHECKIN["test"])
        st = _first((x for x in pic.app if x.id == DESIGN_STEP), _current_step(s))
        return finish(_step_view(st, "stop", _stop_message(gap, _PLAN_TODO)))
    gap = _estimate_gap(pic)
    if gap:
        _hold(s, ESTIMATE_STOP, gap, _ESTIMATE_TODO)
        return finish(_step_view(_current_step(s), "stop", _stop_message(gap, _ESTIMATE_TODO)))
    due = pic.due()
    if due:
        item = due[0]
        view = _view(pic, item)
        if item.kind == "stop":
            _hold(s, item.ids[0], item.stop["what"], item.stop["todo"])
        else:
            _release(s)
        return finish(_step_view(pic.app[item.step], item.kind,
                                 _item_message(view, item.kind, item.stop, pic.cat), view))
    if pic.p >= len(pic.app):
        gap = _library_gap(run, s, pic)
        if gap:
            _release(s)
            return finish(_step_view(_first(st for st in pic.app if st.measures), "work", gap))
        _release(s)
        s.status = "done"
        return finish(_done(pic))
    st = pic.app[pic.p]
    pending = _pending_measurements(s) if st.measures else []
    if pending and date.fromisoformat(pending[0]) > today:
        what = "The next live test measurement is not due yet."
        todo = f"Wait until {pending[0]}, then ask Claude to continue this run to take it."
        _hold(s, NOT_DUE, what, todo)
        return finish(_step_view(st, "stop", _stop_message(what, todo)))
    gap = _budget_gap(s, st)
    if gap:
        what, todo = _BUDGET_STOP[gap] if _pb01(s) else planned_stop(gap)
        yes = None if _pb01(s) else _first((cid for cid, c in pic.cat.checkins.items()
                                            if gap in c.yes_for and cid in pic.owner), None)
        _hold(s, f"budget_{gap}", what, todo, checkin=yes)
        return finish(_step_view(st, "stop", _stop_message(what, todo)))
    _release(s)
    coming = pic.coming()
    view = _view(pic, coming) if coming else None
    if pending:
        message = (f"Take the live test measurement for {pending[0]} as described at the ref, then "
                   f"run `tm done {st.id} --measured {pending[0]}`.")
    else:
        message = (f"Do the work of {st.id} ({st.title}) as described at the ref, record every "
                   f"file with `tm record`, then run `tm done {st.id}`.")
    if _pb01(s) and s.evidence is None and st.id in _EVIDENCE_STEPS:
        message = _EVIDENCE_FIRST + " " + message
    if (_pb01(s) and st.id == ESTIMATE_STEP and "live_test" in s.outputs and not s.test_plan
            and (s.test_estimate or {}).get("basis") != "ad"):
        message = _ESTIMATE_FIRST + " " + message
    if view:
        message += f" After it comes the check-in \"{view.name}\" ({', '.join(view.ids)})."
    message += _ending_hints(pic, pic.p)
    return finish(_step_view(st, "work", message, view))


def _ended_early(s: state.RunState) -> bool:
    """The run ended before its changes were made: not supported (A1a, A3) or a choice that ends it."""
    if s.ended:
        return True
    cat = checkins.load(playbook=s.playbook)
    return any("end" in cat.checkins[d["checkin"]].on_choice.get(d.get("choice"), {})
               for d in s.decisions if d.get("checkin") in cat.checkins)


def _with_notice(s: state.RunState, result: NextStep) -> NextStep:
    """The guess-mode notice, on what the user sees: a check-in shown to them (never one decided
    by rule, so Hands-off gets it only in the final report) and the final report of a run that
    made its changes (Creative brief: only when its G2 was not asked, `Notice.repeat_at_end`)."""
    ids = result.checkin.ids if result.checkin and result.action == "ask" else None
    done = result.action == "done" and not _ended_early(s)
    result.notice = evidence.notice_for(s, ids, done=done)
    return result


def set_evidence(run: RunFolder, value: str, why: str) -> state.RunState:
    """Record what the run's changes rest on (`tm evidence`), in a playbook with a guess mode. It
    can change until the window's last step is done (Refresh an ad: the change register, A7;
    Creative brief: the concepts, C1), and a switch to TrendsMesh after its first step (A5, B3)
    needs the trends saved. Refresh an ad: a change clears a register already checked."""
    if value not in evidence.EVIDENCE:
        raise ValueError(f"Evidence must be one of {', '.join(evidence.EVIDENCE)}, not {value!r}.")
    if not (why and why.strip()):
        raise ValueError("Say why with --why (for example: no Agent plan, the user skipped sign-in).")
    s = state.load(run)
    first, last = _evidence_window(s)
    if s.status == "done":
        raise ValueError("This run is done; its evidence can no longer change.")
    every = steps(s.playbook)
    order = [st.id for st in every]
    if s.step not in (None, END, *order):
        raise ValueError(f"run.json names an unknown step {s.step!r}; run `tm next` first.")
    at = len(order) if s.step == END else (order.index(s.step) if s.step in order else -1)
    if at > order.index(last):
        recorded = s.evidence or "unrecorded"
        if _pb01(s):
            raise ValueError(f"The changes of this run are already decided (the change register, "
                             f"{last}, is done), so what they rest on stays {recorded}.")
        title = every[order.index(last)].title
        skill = playbooks.get(s.playbook).skill
        raise ValueError(f"{last} ({title}) is done, so what this run rests on stays {recorded}. "
                         f"For concepts on other evidence, start a new run (`tm run new --playbook "
                         f"{skill}`); this run goes on from the same place.")
    if value == evidence.TRENDSMESH and at > order.index(first):
        _need_trends(run, f"Switching to TrendsMesh after {first}")
    if _pb01(s) and value != s.evidence:
        s.register = None  # checked against the old evidence: check it again
    s.evidence_log.append({"evidence": value, "why": why.strip(), "at_step": s.step})
    s.evidence = value
    state.save(run, s)
    return s


def _other_playbook(s: state.RunState, what: str) -> str | None:
    """"<what> part of Refresh an ad, not of <name>." for another playbook's run, else None."""
    if _pb01(s):
        return None
    return f"{what} part of {playbooks.get(REFRESH_AD).name}, not of {playbooks.get(s.playbook).name}."


def _only_pb01(s: state.RunState) -> None:
    why = _other_playbook(s, "Variant flows are")
    if why:
        raise ValueError(why)


def _evidence_window(s: state.RunState) -> tuple[str, str]:
    """The run's evidence window (first step, last step); refused for a playbook without a
    guess mode."""
    pb = playbooks.get(s.playbook)
    window = _EVIDENCE_WINDOW.get(pb.id) if pb.guess else None
    if window is None:
        guessing = [p.name for p in playbooks.all_playbooks()
                    if p.guess and p.id in _EVIDENCE_WINDOW and playbooks.bundled(p)]
        names = " and ".join([", ".join(guessing[:-1]), guessing[-1]] if len(guessing) > 1 else guessing)
        raise ValueError(f"Guess mode is part of {names}, not of {pb.name}.")
    return window


def set_level(run: RunFolder, level: str) -> None:
    """Change how involved the user is. Pending check-ins re-route; decisions and spend stay."""
    checkins.validate_level(level)
    s = state.load(run)
    s.level = level
    state.save(run, s)


def use_flow(run: RunFolder, flow_id: str) -> None:
    """Turn on a variant flow (VARIANTS.md), e.g. "V": a new voiceover line in the same voice, or
    "R": a re-cut (path C-R), which needs a diagnosis that allows it (`recut_refusal`)."""
    s = state.load(run)
    _only_pb01(s)
    known = flows()
    if flow_id not in known:
        raise ValueError(f"{flow_id!r} is not a variant flow. Known: {', '.join(sorted(known))}.")
    if flow_id == RECUT_FLOW and not flow_on(s, flow_id):
        why = recut_refusal(run, s) or _late_for_recut(s)
        if why:
            raise ValueError(why)
    if flow_id not in s.flows:  # a middle run has flow R on already: this only records it
        s.flows.append(flow_id)
        state.save(run, s)


def _late_for_recut(s: state.RunState) -> str | None:
    """Flow R's steps sit right after C1: a run past C1 would never reach them (the pointer only
    moves forward), so the flow can no longer be turned on."""
    order = [st.id for st in steps()]
    at = len(order) if s.step == END else (order.index(s.step) if s.step in order else 0)
    if at <= order.index(RECUT_AFTER):
        return None
    return ("Flow R must be turned on at the diagnosis (G1a), before the edited video's steps start. "
            f"This run is past the method selection ({RECUT_AFTER}), and the re-cut's steps come "
            "right after it, so they would never be reached. Make the re-cut in a new run (turn "
            "the flow on at G1a there), and go on here with the steps this run has. " + CONTINUES)


def recut_refusal(run: RunFolder, s: state.RunState) -> str | None:
    """Why flow R (a re-cut) cannot be turned on, or None. PLAYBOOK.md 7c and R2b: a re-cut answers
    a middle diagnosis (the stage, or the target a talking head's run is moved to), or a weakness
    R2b found structural; Hands-off re-cuts a structural weakness only with
    `diagnosis.structural_recut: true`. Hands-off is the run's level, or an unset level with the
    config's mode auto (as config.validate and recut_plan.run_context test it)."""
    from tm import config  # config imports this module

    d = s.diagnosis
    if not d:
        return ("A re-cut (flow R) answers the diagnosis, and this run has no diagnosis yet. Diagnose "
                "it first (A1a, `tm diagnose`), then turn the flow on. " + CONTINUES)
    if "middle" in (d.get("stage"), d.get("target_stage")):
        return None
    stage = changes.STAGES.get(d.get("stage"), d.get("stage"))
    found = d.get("structural")
    if not (isinstance(found, dict) and found.get("structural") is True):
        what = ("the structural check (R2b) found the file not structural: no step is weakest in "
                "every upload" if isinstance(found, dict)
                else "the structural check (R2b, `tm structural`) has not reported a weakness")
        return (f"A re-cut (flow R) is for a middle that is fading or a segment that is weak by "
                f"design, but the diagnosis points at {stage}, not the middle, and {what}. Refresh "
                "what the diagnosis points at instead, or run the structural check first. " + CONTINUES)
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = None
    hands_off = s.level == "hands_off" or (s.level is None and config.value(cfg, "mode") == "auto")
    if hands_off and config.value(cfg, "diagnosis.structural_recut") is not True:
        return ("The structural check (R2b) found a segment that is weak by design, but Hands-off "
                "re-cuts a structural weakness only when diagnosis.structural_recut is true in "
                "config.yaml, and it is not, so it stays in the diagnosis as an improvement "
                "opportunity. To re-cut it, set diagnosis.structural_recut: true, or choose another "
                "level and decide it yourself. " + CONTINUES)
    return None


def decide(run: RunFolder, checkin_id: str, choice: str, by: Literal["user", "rule"],
           note: str | None, *, today: date | None = None, change: bool = False) -> None:
    """Record a decision. A card id records one entry per check-in it covers.

    A decision by rule needs `note`: the data behind it. Deciding again needs `change`.
    A choice may end the run (G1a do_not_refresh, accepted from G1a's own step even when its
    card comes later), stop it (E2b red), set the measurement dates (G11 activate, from
    `today`; keep_paused clears them), need another decision first (activate needs a green
    E2b), need step checks to pass first (`requires`, organic video's reuse_profile reuse) or skip
    the steps it no longer allows (a reject at a spending check-in). A money
    decision is refused (Held) while the run is stopped for something else; G10 approve and G11
    activate need a feasible R4 plan.
    """
    if by not in ("user", "rule"):
        raise ValueError(f"--by must be user or rule, not {by!r}.")
    if by == "rule" and not (note and note.strip()):
        raise ValueError("A decision by rule needs --note with the data behind it.")
    s = state.load(run)
    if s.status == "done":
        raise ValueError("This run is done; nothing more can be decided in it.")
    if s.level is None or not s.outputs:
        raise ValueError("Finish the intake first: the level and the outputs are not set yet.")
    pic = _picture(s)
    cat = pic.cat
    level_name = cat.levels[s.level]
    current = _pointer(pic)
    pb01 = _pb01(s)
    covered = (["G1a"] if checkin_id == "G1a"
               else pic.card_members(checkin_id) if checkin_id in cat.cards else [])
    block = _blocking(s) if "G1a" in covered and choice != "do_not_refresh" else None
    if block:
        raise ValueError(f"{block.message} G1a accepts only do_not_refresh now; correct the "
                         "data with `tm diagnose` or `tm material` first.")
    if checkin_id in cat.cards:
        members = pic.card_members(checkin_id)
        if not members:
            raise ValueError(f"Nothing in this run goes to the card {checkin_id} at {level_name}.")
        if by == "rule":
            raise ValueError(f"{checkin_id} is a card for the user; it is not decided by rule.")
        if pic.card_place(checkin_id)[1] > pic.p:
            raise ValueError(f"The card {checkin_id} is not reached yet; the run is at {current}.")
        open_ids = [m for m in members if m not in pic.latest]
        if not open_ids and not change:
            raise ValueError(f"The card {checkin_id} is already decided. Use --change to change it.")
        ids = open_ids or members
    elif checkin_id in cat.checkins:
        if checkin_id not in pic.owner:
            raise ValueError(f"{checkin_id} is not part of this run (its step or flow is not in use).")
        ending = "end" in cat.checkins[checkin_id].on_choice.get(choice, {})
        reached = pic.owner[checkin_id][0] if ending else pic.place(checkin_id)[1]
        if reached > pic.p:
            raise ValueError(f"{checkin_id} is not reached yet; the run is at {current}.")
        if by == "rule" and pic.route(checkin_id) != "rule" and not ending:
            raise ValueError(f"{checkin_id} ({cat.checkins[checkin_id].name}) is not decided by rule "
                             f"at {level_name}: ask the user.")
        if checkin_id in pic.latest and not change:
            raise ValueError(f"{checkin_id} is already decided "
                             f"({pic.latest[checkin_id]['choice']}). Use --change to change it.")
        ids = [checkin_id]
    else:
        raise ValueError(f"{checkin_id!r} is not a check-in or a card.")
    for cid in ids:
        allowed = cat.checkins[cid].choices
        if allowed and choice not in allowed:
            each = _member_commands(cat, ids) if checkin_id in cat.cards else None
            if each:
                raise ValueError(f"No one answer fits every check-in the card {checkin_id} covers; "
                                 f"record each in order: {each}.")
            raise ValueError(f"{cid} takes one of: {', '.join(allowed)}.")
    for cid in ids:
        c = cat.checkins[cid]
        if c.money:  # spending and the launch wait while the run is stopped (I1)
            refuse_if_held(s, "nothing was decided", checkin=cid)
        for other, wanted in (c.on_choice.get(choice, {}).get("needs") or {}).items():
            got = pic.latest.get(other, {}).get("choice")
            if got != wanted:
                raise ValueError(f"{cid} {choice} needs {other} ({cat.checkins[other].name}) to be "
                                 f"{wanted} first; it is {got or 'not decided yet'}.")
        for name in c.on_choice.get(choice, {}).get("requires") or ():
            gap = stepchecks.run(name, run)
            if gap is not None:
                raise ValueError(f"{cid} ({c.name}) can be {choice} once {gap}; nothing was "
                                 "decided. Choose another answer, or fix that first.")
        if pb01 and ((cid == SPENDING_CHECKIN["test"] and choice != "reject")
                     or (cid == LAUNCH and choice == "activate")):
            _need_plan(s, f"{cid} ({c.name})")
        if cid in pic.latest:
            _check_unskip(s, cid, pic.latest[cid]["choice"], choice)
    for cid in ids:
        c = cat.checkins[cid]
        entry: dict = {"checkin": cid, "choice": choice, "by": by}
        if by == "rule":
            entry["rule"] = c.rule_for(s.evidence)
        if note:
            entry["note"] = note
        if cid in pic.latest:
            entry["change"] = True
        entry["at"] = _now()
        entry.update(_covers(run, s, cid, choice))
        s.decisions.append(entry)
        effect = c.on_choice.get(choice, {})
        if "measure_days" in effect:
            start = today or date.today()
            s.measurements_due = [(start + timedelta(days=n)).isoformat()
                                  for n in effect["measure_days"]]
            s.measurements_done = []
        elif any("measure_days" in e for e in c.on_choice.values()):
            s.measurements_due, s.measurements_done = [], []  # keep_paused: nothing to measure
        if "skips" in effect:  # a reject: the budgets that yes approved are approved no longer
            kinds = ([k for k, v in SPENDING_CHECKIN.items() if v == cid] if pb01
                     else c.yes_for)
            for kind in kinds:
                if not s.spend.get(kind):  # money already spent keeps its approval (PB01's rule)
                    s.budgets.pop(kind, None)
        if "end" in effect:
            s.status = "done"
            block = _blocking(s) if cid == "G1a" else None
            if block and block.kind == "unsupported":
                s.ended = block.message
        if "stop" in effect:
            _hold(s, cid, effect["stop"]["what"], effect["stop"]["todo"])
        else:
            _resolve(s, [cid])
    state.save(run, s)


def _check_unskip(s: state.RunState, cid: str, old: str, new: str) -> None:
    """A changed choice brings back the steps the old one skipped, but only while the run has not
    gone past them (the steps are linear, so work behind the pointer would never be done)."""
    every = steps(s.playbook)
    position = {st.id: i for i, st in enumerate(every)}
    back = [position[st.id] for st in every if _applies(st, s)
            and (cid, old) in st.skip_when and (cid, new) not in st.skip_when]
    here = len(every) if s.step == END else position.get(s.step, 0)
    if back and min(back) < here:
        raise ValueError(f"The run has gone past the steps that {cid} {old} skipped, so it cannot "
                         f"be changed to {new} now. Start a new run for that output.")


def stop(run: RunFolder, reason_id: str, what: str, todo: str) -> int:
    """Record that the user must act. Holds until `resume`. Returns the exit code 2."""
    s = state.load(run)
    s.stops.append({"reason_id": reason_id, "what": what, "todo": todo, "at": _now()})
    s.status = "stopped"
    state.save(run, s)
    return 2


def resume(run: RunFolder) -> None:
    """The user has acted: clear the stopped status and mark the open stops as resumed."""
    s = state.load(run)
    if s.status != "stopped":
        raise ValueError("This run is not stopped.")
    for x in _open_stops(s):
        x["resumed_at"] = _now()
    s.status = "active"
    state.save(run, s)


def open_stop(run: RunFolder, reason_ids: list[str] | None = None) -> str | None:
    """The words of the latest open stop (optionally only for these reasons), or None."""
    s = state.load(run)
    for x in reversed(_open_stops(s)):
        if reason_ids is None or x["reason_id"] in reason_ids:
            return _stop_message(x["what"], x["todo"])
    return None


def complete(run: RunFolder, step_id: str, *, measured: str | None = None,
             today: date | None = None) -> None:
    """Mark the current step's work as done and move to the next step that applies.

    A measuring step (E4) is done once per measurement date: pass `measured`; the run moves on
    after the last one.
    """
    today = today or date.today()
    s = state.load(run)
    if s.status == "done":
        raise ValueError("This run is done.")
    if s.status == "stopped":
        refuse_if_held(s, f"{step_id} cannot be finished")
        raise Held("The run is stopped. Run `tm next` to see why.")
    late = _late_step(s)
    if late is not None and late.id != _LATE_INTAKE[s.playbook][0]:
        _complete_before_intake(run, s, late, step_id)
        return
    # a late-intake playbook takes both from the intake card's answers, not from `tm level`
    how = (" Write the intake answers with the level and the outputs, then `tm config write`."
           if s.playbook in _LATE_INTAKE else "")
    if s.level is None:
        raise ValueError("The intake is not finished: the level of involvement is not set"
                         + (f".{how}" if how else " (`tm level <id>`)."))
    if not s.outputs:
        raise ValueError(f"The intake is not finished: the outputs are not set.{how}")
    pic = _picture(s)
    if pic.p >= len(pic.app):
        raise ValueError("Every step of this run is already done.")
    st = pic.app[pic.p]
    if step_id != st.id:
        raise ValueError(f"The run is at {st.id} ({st.title}), not {step_id}. "
                         "Steps are finished in order.")
    due = pic.due()
    if due:
        first = _view(pic, due[0])
        raise ValueError(f"Decide {', '.join(first.ids)} ({first.name}) first.")
    pb01 = _pb01(s)
    if pb01 and st.id == TREND_STEP:
        _need_evidence(run, s, st)
    if pb01 and st.id == REGISTER_STEP and not s.register:
        raise ValueError(f"{st.id} ({st.title}) is done once its change register is checked: write it "
                         "as JSON (each change with its basis, proof or guess) and run "
                         "`tm register check --run R --file <register JSON>`.")
    if pb01 and st.id == DESIGN_STEP and any(x.id == LAUNCH_STEP for x in pic.app):
        _need_plan(s, f"{st.id} ({st.title})")
    if pb01 and st.id == LAUNCH_STEP and not s.spend.get("test"):
        raise ValueError(f"{st.id} ({st.title}) is done only once the live test's spend is booked: "
                         "`tm budget spend --run R test <per day × days> --what \"live test\"` "
                         "(exit 0), then the A/B test is created and activated, then "
                         f"`tm done {st.id}`.")
    for name in st.requires:
        gap = stepchecks.run(name, run)
        if gap is not None:
            raise stops.Stop(f"{st.id} ({st.title}) is done once {gap}; {stops.AGAIN}.")
    pending = _pending_measurements(s) if st.measures else []
    if measured is not None and measured not in pending:
        raise ValueError(f"{measured} is not a measurement waiting in this run "
                         f"({', '.join(pending) or 'none'}).")
    if pending:
        if measured is None:
            raise ValueError(f"Say which measurement was taken: `tm done {st.id} --measured {pending[0]}`.")
        if date.fromisoformat(measured) > today:
            raise ValueError(f"The measurement for {measured} is not due yet.")
        if measured != pending[0]:
            raise ValueError(f"Take the measurements in order: {pending[0]} comes first.")
        s.measurements_done.append(measured)
        if len(pending) > 1:
            state.save(run, s)
            return
    s.step = pic.app[pic.p + 1].id if pic.p + 1 < len(pic.app) else END
    state.save(run, s)


def _complete_before_intake(run: RunFolder, s: state.RunState, st: Step, step_id: str) -> None:
    """A step before a late-intake playbook's card: done in order, with its required checks, and
    no check-in (none sits there), without the level or the outputs."""
    if step_id != st.id:
        raise ValueError(f"The run is at {st.id} ({st.title}), not {step_id}. Steps are finished in order.")
    for name in st.requires:
        gap = stepchecks.run(name, run)
        if gap is not None:
            raise stops.Stop(f"{st.id} ({st.title}) is done once {gap}; {stops.AGAIN}.")
    every = [x.id for x in steps(s.playbook)]
    s.step = every[every.index(st.id) + 1]
    state.save(run, s)


def _need_evidence(run: RunFolder, s: state.RunState, st: Step) -> None:
    if s.evidence is None:
        raise ValueError(f"{st.id} ({st.title}) is done once the run says what its changes rest on. "
                         + _EVIDENCE_FIRST)
    if s.evidence == evidence.TRENDSMESH:
        _need_trends(run, f"{st.id} ({st.title}) with TrendsMesh data")


def _need_trends(run: RunFolder, what: str) -> None:
    if not any((run.path / "02_research").glob("trend_*.json")):
        raise ValueError(f"{what} needs the trends saved: each `get_trend` answer as "
                         "02_research/trend_<id>.json. Without trend data, record "
                         "`tm evidence guess --run R --why <reason>` instead.")


WEEKLY_DIGEST = "weekly_digest"
WEEKLY_PLAN = "weekly_plan"     # organic video's week run
WEEK = timedelta(days=7)
DAY = timedelta(days=1)


def due(workspace: Path, today: date) -> list[dict]:
    """What is due on `today`, across `<workspace>/runs/*/*/run.json`:
    - live test measurements due on or before it and not taken (refresh-ad);
    - the weekly trend report: a done trend research run with the weekly digest, the latest of its
      chain (no run follows it), made a week or more ago, and not started by a desktop scheduled
      task (`schedule.how` "desktop_task": the task starts it);
    - an unfinished weekly run: the latest of its chain, following another run, started a day or
      more ago. It is reminded to be finished, so a weekly run left half-way never silences the
      reminders for good;
    - organic video's weekly pack: a done week run (outputs weekly_plan), the latest of its chain,
      made a week or more ago, and not started by a desktop scheduled task; and, the day before a
      week's flexible day and on that day, its video while it is not started (run.json `organic.flexible`)."""
    runs: list[tuple[Path, dict]] = []
    for path in sorted((Path(workspace) / "runs").glob("*/*/run.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            runs.append((path, data))
    followed = {d.get("previous_run") for _, d in runs}
    found: list[dict] = []
    for path, data in runs:
        run_id = data.get("run_id") or path.parent.name
        created = _weekly(data, path.parent.relative_to(Path(workspace)).as_posix() in followed)
        if created is not None:
            done = data.get("status") == "done"
            when = created + (WEEK if done else DAY)
            if when <= today:
                message = (f"Run {run_id}: the weekly trend report is due. Ask Claude to update the trend report."
                           if done else
                           f"Run {run_id}: this week's trend report was started on {created.isoformat()} and is not "
                           "finished. Ask Claude to continue the trend report.")
                found.append({"message": message, "run": run_id, "date": when.isoformat()})
        found += _organic_week(data, path.parent.relative_to(Path(workspace)).as_posix() in followed, run_id, today)
        if data.get("status") == "done":
            continue
        taken = set(data.get("measurements_done") or [])
        for value in data.get("measurements_due") or []:
            if value in taken:
                continue
            try:
                day = date.fromisoformat(value)
            except (TypeError, ValueError):
                continue
            if day <= today:
                found.append({
                    "message": (f"Run {run_id}: the live test measurement for {value} is due. "
                                "Ask Claude to continue this ad refresh to take it."),
                    "run": run_id, "date": value})
    return found


def _covers(run: RunFolder, s: state.RunState, cid: str, choice: str) -> dict:
    """What a yes binds to, kept in its decision: organic video's week approval covers the week's decisions it was
    given on (`organic_week.covered`), so decisions read after it need a new yes. Nothing for any other choice."""
    if s.playbook != playbooks.ORGANIC_VIDEO or cid != "week" or choice != "approve":
        return {}
    from tm import organic_week   # it starts production runs through organic_proposals, which imports this module

    return {"covers": organic_week.covered(run)}


def _organic_week(data: dict, followed: bool, run_id: str, today: date) -> list[dict]:
    """What an organic video week run has due (`due`): next week's plan, a week after a done week run that no run
    follows and no desktop scheduled task starts; the flexible day's video the day before that day and on the day, while
    its slot is OK and not started."""
    if data.get("playbook") != playbooks.ORGANIC_VIDEO or WEEKLY_PLAN not in (data.get("outputs") or []):
        return []
    found = []
    organic = data.get("organic") if isinstance(data.get("organic"), dict) else {}
    flexible = organic.get("flexible") if isinstance(organic.get("flexible"), dict) else {}
    try:
        day = date.fromisoformat(flexible.get("date"))
    except (TypeError, ValueError):
        day = None
    if day is not None and day - DAY <= today <= day and flexible.get("decision") == "ok" and not flexible.get("run"):
        when = "today" if today == day else "tomorrow"          # PR E review m3: the day itself too
        found.append({"message": (f"Week {flexible.get('week') or day.isoformat()}: the flexible day's video is due "
                                  f"{when}. Ask Claude to make the flexible day's video."),
                      "run": run_id, "date": today.isoformat()})
    schedule = data.get("schedule")
    if (followed or data.get("status") != "done"
            or (isinstance(schedule, dict) and schedule.get("how") == "desktop_task")):
        return found
    try:
        when = date.fromisoformat(data.get("created")) + WEEK
    except (TypeError, ValueError):
        return found
    if when <= today:
        found.append({"message": f"Run {run_id}: next week's videos are due. Ask Claude to plan my week of videos.",
                      "run": run_id, "date": when.isoformat()})
    return found


def _weekly(data: dict, followed: bool) -> date | None:
    """The created date of a trend research run with the weekly digest that a reminder may be about,
    or None: another playbook or no weekly digest, a later run follows it, a done run a desktop
    scheduled task starts again, an unfinished run that follows no other run (a first run), or an
    unreadable date."""
    if (followed or data.get("playbook") != playbooks.TREND_RESEARCH
            or WEEKLY_DIGEST not in (data.get("outputs") or [])):
        return None
    if data.get("status") == "done":
        schedule = data.get("schedule")
        if isinstance(schedule, dict) and schedule.get("how") == "desktop_task":
            return None
    elif not data.get("previous_run"):
        return None
    try:
        return date.fromisoformat(data.get("created"))
    except (TypeError, ValueError):
        return None
