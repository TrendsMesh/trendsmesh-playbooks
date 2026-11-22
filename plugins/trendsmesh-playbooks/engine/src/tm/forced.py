"""Check-ins the situation answers (issue #148 line 30): `tm decide <id> <choice> --by forced`.

A check-in has exactly one possible answer only in a situation the run's own data shows. The catalogue names it on the
check-in, `forced: {<choice>: <condition>}`, and the engine allows `--by forced` only for that choice and only while
the condition holds: a condition reads the run's files and returns the reason (a key of `REASONS`), else None. The
decision is the situation's, never the user's: it has no `said`, and the page and the run log show it as "forced by
the situation" with the reason in words (`run_page.record.forced_reason.<reason>`).

The conditions (every check-in of the flows with one possible answer):
- `no_fading_ad` (refresh-ad G1 `none`): the latest ranking (01_base/winner_ranking_vNN.json) ranks no ad as
  fading, and its ads do not have too little data to judge (then the user may still pick one, flow.md#a1). With no
  ranking file yet, nothing is forced.
- `no_ad_to_diagnose` (refresh-ad G1a `do_not_refresh`): the same, and no ad was picked at G1 (it is `none`, or not
  recorded: at Just the big calls its card never comes). Its reason is `no_fading_ad`.
- `no_reusable_profile` (organic video's `reuse_profile` `new`): `reuse` is refused (the `profile_confirmed` check
  finds a gap), so `new` is left: `no_saved_profile` when a channel of the run has none saved, else
  `no_confirmed_profile` (a saved one the user never confirmed, or one that no longer passes its check).
"""

from __future__ import annotations

import json
from typing import Callable

from tm.runfolder import RunFolder

FORCED = "forced"
REASONS = ("no_fading_ad", "no_saved_profile", "no_confirmed_profile")
WORDS = "run_page.record.forced_reason."      # + a reason: its words (data/i18n/en.yaml, pl.yaml)


def _no_fading_ad(run: RunFolder) -> str | None:
    path = run.latest("01_base", "winner_ranking", "json")
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("ranking"), list):
        return None
    if data["ranking"] or data.get("too_little_data"):
        return None
    return "no_fading_ad"


def _no_ad_to_diagnose(run: RunFolder) -> str | None:
    """G1a: no ad is fading and none was picked at G1 (its answer is `none`, or it sits on a card that never came)."""
    why = _no_fading_ad(run)
    if why is None:
        return None
    from tm import state
    picked = [d.get("choice") for d in state.load(run).decisions if d.get("checkin") == "G1"]
    return why if not picked or picked[-1] == "none" else None


def _no_reusable_profile(run: RunFolder) -> str | None:
    from tm import brand, config, trend_spool    # brand reads the flow's state
    if brand.confirmed_gap(run) is None:
        return None
    try:
        channels = config.load(run).get("channels") or []
    except ValueError:
        channels = []
    workspace = trend_spool.workspace_of(run)
    for slug in channels:
        try:
            if brand.latest(workspace, slug, kind="channel") is None:
                return "no_saved_profile"
        except ValueError:
            continue
    return "no_confirmed_profile"


CONDITIONS: dict[str, Callable[[RunFolder], str | None]] = {
    "no_fading_ad": _no_fading_ad,
    "no_ad_to_diagnose": _no_ad_to_diagnose,
    "no_reusable_profile": _no_reusable_profile,
}


def reason(condition: str, run: RunFolder) -> str | None:
    """The reason the situation leaves one answer (a key of REASONS), or None when it does not."""
    return CONDITIONS[condition](run)


def answer(run: RunFolder, forced: dict[str, str]) -> tuple[str, str] | None:
    """(choice, reason) when one of a check-in's `forced` conditions holds, else None."""
    for choice, condition in forced.items():
        why = reason(condition, run)
        if why is not None:
            return choice, why
    return None


def words(why: str, lang: str = "en") -> str:
    """The reason in words (the English table's for the engine's messages and the run log)."""
    from tm import i18n
    return i18n.t(WORDS + why, lang)
