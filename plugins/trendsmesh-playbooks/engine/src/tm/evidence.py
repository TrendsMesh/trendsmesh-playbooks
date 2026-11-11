"""What a run's changes rest on: TrendsMesh data, or the agent's guess.

A run without TrendsMesh (no Agent plan, not signed in, or the user said no) still goes to the
end, in a playbook with a guess mode (`guess: true` in data/playbooks.yaml: Refresh an ad and
Creative brief). Its new hooks and topics are the agent's judgement, not proof from what is
rising now. The engine records that choice in run state (`tm evidence`), and while it is `guess`:

- `tm next` gives the playbook's notice (`NOTICES`) on its check-ins in `Notice.at` when they are
  shown to the user (Refresh an ad: the direction G2 and the launch G11; Creative brief: the
  concepts G2; Create an ad: the concept), and in the final report of a run that made its changes (so Hands-off hears it
  at the end, and at the launch, which every level asks). Creative brief's final report carries it only when G2 was not asked
  (`Notice.repeat_at_end`), so every level hears it once; the doctor's readiness card shows its
  short form;
- Refresh an ad: the change register cannot call a change "proof" (`tm register check`), and the
  results library keeps guessed rows out of the per-trend ranking.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from tm import cli, state
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, REFRESH_AD
from tm.runfolder import RunFolder

EVIDENCE = ("trendsmesh", "guess")
TRENDSMESH, GUESS = EVIDENCE
NOTICE_AT = frozenset({"G2", "G11"})  # the direction of changes, the launch; and the final report

NOTICE = ("Without live trend data, the new hook is my best guess from your own past winners and "
          "the Ad Library, not proof from what is rising now. With TrendsMesh (the Agent plan) I "
          "pick hooks that are rising right now, which is where refreshes work best.")


# The readiness card's form: no plan name, since the offer (if any) was already made apart.
NOTICE_SHORT = ("Without live trend data, the new hook is my best guess from your own past winners "
                "and the Ad Library, not proof from what is rising now.")


@dataclass(frozen=True)
class Notice:
    at: frozenset[str]  # the check-ins that carry it when shown to the user (and the final report)
    text: str
    short: str  # the readiness card's form: no plan name
    # The final report repeats it even when a check-in in `at` is asked at the run's level
    # (Refresh an ad). False: the final report carries it only when none is (Creative brief:
    # Hands-off), so the user hears it once.
    repeat_at_end: bool = True


_BRIEF_SHORT = ("Without live trend data, the hooks in these concepts are my best guess from your "
                "customers' own words, your ads and the Ad Library, not proof from what is rising now.")
_AD_SHORT = ("Without live trend data, the model ads and trends in these concepts are my best guess: ads from the "
             "Meta Ad Library where it returns any (its search covers mainly ads shown in the EU) and formats I "
             "know, not proof from what is rising now.")
NOTICES = {
    REFRESH_AD: Notice(NOTICE_AT, NOTICE, NOTICE_SHORT),
    CREATIVE_BRIEF: Notice(frozenset({"G2"}),  # choosing the concepts
                           _BRIEF_SHORT + " With TrendsMesh (the Agent plan) each concept rides a "
                           "hook or topic that is rising right now.", _BRIEF_SHORT,
                           repeat_at_end=False),
    CREATE_AD: Notice(frozenset({"concept"}),  # picking the concept
                      _AD_SHORT + " With TrendsMesh (the Agent plan) each concept rests on ads and trends that are "
                      "rising right now.", _AD_SHORT, repeat_at_end=False),
}


def record(run: RunFolder, value: str, why: str) -> state.RunState:
    """`tm evidence`: the rules (when it may change) are the step engine's, `flow.set_evidence`."""
    from tm import flow  # flow imports this module
    return flow.set_evidence(run, value, why)


def notice_for(s: state.RunState, checkin_ids: list[str] | None, done: bool = False) -> str | None:
    """The guess-mode notice of the run's playbook (`NOTICES`; None for a playbook without one)."""
    notice = NOTICES.get(s.playbook)
    if notice is None or s.evidence != GUESS:
        return None
    if checkin_ids and notice.at & set(checkin_ids):
        return notice.text
    if done and (notice.repeat_at_end or not _asked(s, notice)):
        return notice.text
    return None


def _asked(s: state.RunState, notice: Notice) -> bool:
    """Whether the user decided a check-in that carries the notice (`by: user` in run.json), so they
    heard it there. What happened counts, not the level now: the level can change mid-run."""
    return any(d.get("checkin") in notice.at and d.get("by") == "user" for d in s.decisions)


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("value", choices=EVIDENCE)
    p.add_argument("--run", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        s = record(RunFolder.open(args.run), args.value, args.why)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    text = ("This run uses TrendsMesh data." if s.evidence == TRENDSMESH else
            "This run goes on without TrendsMesh: its changes are guesses, labelled as such. "
            "`tm next` gives the notice where the user should hear it.")
    cli.emit(args, {"status": "done", "evidence": s.evidence}, text)
    return 0


cli.register("evidence", _setup, _run)
