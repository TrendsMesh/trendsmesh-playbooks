"""What a run's changes rest on: TrendsMesh data, or the agent's guess.

A run on Free (issue #106: the user's choice, never a fallback; `tm mode`) goes to the end in a
playbook with a Free mode (`guess: true` in data/playbooks.yaml: Refresh an ad, Creative brief,
Create an ad, Organic AI video; Trend research is Paid only). Its hooks, topics and ideas are the
agent's guesses. The engine records it in run state (`tm evidence`, refused until the user chose
Free: `NOT_CHOSEN`), and while it is `guess`:

- `tm next` gives the playbook's notice (`NOTICES`) on its check-ins in `Notice.at` when they are
  shown to the user (Refresh an ad: the direction G2 and the launch G11; Creative brief: the
  briefs G3, alone or on the card "Approve the briefs"; Create an ad: the concept; Organic AI video: the ideas page and the week), and in the final report of a run that made its changes (so Hands-off hears it
  at the end, and at the launch, which every level asks). Creative brief's final report carries it only when G3 was not asked
  (`Notice.repeat_at_end`), so every level hears it once; the doctor's readiness card shows its
  short form;
- Refresh an ad: the change register cannot call a change "proof" (`tm register check`), and the
  results library keeps guessed rows out of the per-trend ranking.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from tm import cli, state
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD
from tm.runfolder import RunFolder

EVIDENCE = ("trendsmesh", "guess")
TRENDSMESH, GUESS = EVIDENCE
NOTICE_AT = frozenset({"G2", "G11"})  # the direction of changes, the launch; and the final report

NOT_CHOSEN = ("The user has not chosen Free, so this run cannot go on as guesses. Guessing is never a fallback "
              "(issue #106): ask Free or Paid (references/trendsmesh-sign-in.md). On Free, record it with `tm mode free` "
              "(remembered for the workspace) or `tm mode free --run R` (this run only), then record the evidence again.")

# The notices say what the guess missed, not only that it is a guess (issue #106). No numbers: a Free run has none
# from TrendsMesh, and an example number would read as one.
NOTICE = ("This new hook is my guess from your own past winners and the Ad Library. TrendsMesh would show whether it "
          "is repeating across creators right now, and how early it is, which is where refreshes work best.")


# The readiness card's form: no plan name, since the offer (if any) was already made apart.
NOTICE_SHORT = ("Free mode: the new hook will be my guess from your own past winners and the Ad Library. TrendsMesh "
                "would show whether it is repeating across creators right now, and how early.")

# The readiness card's line for a TrendsMesh row that isn't ready while the user hasn't chosen yet (or chose Paid).
CHOOSE_NOTE = ("Free or Paid is your choice: Paid reads TrendsMesh's trends, with evidence across creators; Free goes "
               "on with my guesses, each labelled as one. Nothing starts on guesses until you say Free.")


@dataclass(frozen=True)
class Notice:
    at: frozenset[str]  # the check-ins that carry it when shown to the user (and the final report)
    text: str
    short: str  # the readiness card's form: no plan name
    # The final report repeats it even when a check-in in `at` is asked at the run's level
    # (Refresh an ad). False: the final report carries it only when none is (Creative brief:
    # Hands-off), so the user hears it once.
    repeat_at_end: bool = True


_BRIEF_SHORT = ("Free mode: the hooks in these concepts will be my guesses from your customers' own words, your ads and "
                "the Ad Library. TrendsMesh would show which hooks and topics are repeating across creators right now, "
                "and how early.")
_AD_SHORT = ("Free mode: the model ads and trends in these concepts will be my guesses: ads from the Meta Ad Library "
             "where it returns any (its search covers mainly ads shown in the EU) and formats I know. TrendsMesh would "
             "show which hooks, sounds and formats are repeating across creators right now, and how early.")
_ORGANIC_SHORT = ("Free mode: the ideas will be my guesses from what I can see (trending tabs and public trend lists, "
                  "your channel, web search). TrendsMesh would show which are actually repeating across creators, and "
                  "how early.")
NOTICES = {
    REFRESH_AD: Notice(NOTICE_AT, NOTICE, NOTICE_SHORT),
    CREATIVE_BRIEF: Notice(frozenset({"G3"}),  # deciding on the briefs (G2, the concepts, before issue #145)
                           "The hooks in these concepts are my guesses from your customers' own words, your ads and the "
                           "Ad Library. TrendsMesh would show which hooks and topics are repeating across creators right "
                           "now, and how early, so each concept could ride one that is still rising.", _BRIEF_SHORT,
                           repeat_at_end=False),
    CREATE_AD: Notice(frozenset({"concept"}),  # picking the concept
                      "The model ads and trends in these concepts are my guesses: ads from the Meta Ad Library where it "
                      "returns any and formats I know. TrendsMesh would show which hooks, sounds and formats are "
                      "repeating across creators right now, and how early, so the concept rests on one that is still "
                      "rising.", _AD_SHORT, repeat_at_end=False),
    ORGANIC_VIDEO: Notice(frozenset({"proposals", "week"}),  # the ideas page, the week's plan
                          "These ideas are my guesses from what I could see: trending tabs and public trend lists, your "
                          "channel and web search. TrendsMesh would show which of them are actually repeating across "
                          "creators, how early each is, and two real videos to copy the structure from.",
                          _ORGANIC_SHORT, repeat_at_end=False),
}

# A Free run's final report ends with this box (`tm next` gives it as `free_box`): what TrendsMesh would have changed,
# for this run's own guesses. It is an instruction to the agent, never shown as it is.
FREE_BOX = ("End the final report with a short box titled \"What TrendsMesh would have changed\": two or three lines "
            "about this run's own guesses (name the hooks, topics or ideas it guessed), each saying what TrendsMesh "
            "would have shown: whether it repeats across creators right now, how early it is, and real videos to "
            "learn from. Specific to this run, in the user's language; no numbers, no price, no link but "
            "'say \"connect TrendsMesh\" any time'.")


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


def free_box_for(s: state.RunState, done: bool) -> str | None:
    """`FREE_BOX` for the final report of a Free run of a playbook with a notice, else None."""
    return FREE_BOX if done and s.evidence == GUESS and s.playbook in NOTICES else None


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
