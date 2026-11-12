"""Refresh an ad, G12: when the variant wins, the winning ad moves into the original's campaign, PAUSED (issue #64).

    tm live-test move check   --run R --file 05_results/move_proposal_vNN.json   the proposal; its answer is the card
    tm live-test move approve --run R --note "<the user's words>"                the user's yes to the checked proposal
    tm live-test move decline --run R --note "<the user's words>"                the user's no: nothing is created
    tm live-test move record  --run R --file 05_results/move_objects_vNN.json    the objects read back from Meta
    tm live-test move report  --run R                                            the user's part, for the final report

Both test ads are new (the control is made of the original's files), and the original keeps running, untouched, in
its own campaign during the test. When G12 is `scale`, and only on the user's yes, the playbook makes a new ad set in
the original's campaign, PAUSED, with one ad from the test ad's post (its likes, comments and shares come along). It
never adds the ad to the original's ad set: that would restart the ad set's learning. Nothing is ever activated:
switching the new ad on, moving the budget and switching the original off are the user's, step by step in the final
report (`report`).

`check` refuses a proposal that is not after G12 `scale`, that rests on Meta answers it did not save, whose ad set is
not new or not in the original's campaign, whose ad is not the test ad's post, whose names read like "Ad set 1", whose
ad set budget has no words from the user, or whose status is not PAUSED. `approve` marks the user's yes on the checked
proposal; `record` refuses without it. **An object that is not paused is a stop**: pause it now.
"""

from __future__ import annotations

from pathlib import Path

from tm import create_copy, create_plan, i18n, state, stepchecks
from tm.config import Problem
from tm.playbooks import REFRESH_AD
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

RESULTS = "05_results"
PROPOSAL, OBJECTS = "move_proposal", "move_objects"
KEY_PROPOSAL, KEY_YES, KEY_OBJECTS, KEY_NO = ("live_test_move_proposal", "live_test_move_yes",
                                              "live_test_move_record", "live_test_move_no")
PAUSED = "PAUSED"
CADENCES = ("daily", "lifetime")
AREA = "refresh"


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _in_run(run: RunFolder, rel: object) -> bool:
    return create_plan._in_run(run, rel)


def _latest_rel(run: RunFolder, stem: str) -> str | None:
    path = run.latest(RESULTS, stem, "json")
    return path.relative_to(run.path).as_posix() if path else None


def _g12(s: state.RunState) -> str | None:
    """The latest choice at G12 ("Act on the results"), or None before it is decided."""
    return next((d.get("choice") for d in reversed(s.decisions) if d.get("checkin") == "G12"), None)


def _refresh_run(run: RunFolder) -> state.RunState:
    s = state.load(run)
    if s.playbook != REFRESH_AD:
        raise ValueError("tm live-test move is for Refresh an ad runs.")
    if _g12(s) != "scale":
        raise ValueError("The winning ad moves only when the variant won: G12 (\"Act on the results\") is `scale`. "
                         f"It is {_g12(s)!r}, so nothing is created.")
    return s


def words(run: RunFolder) -> tuple[i18n.Translator, i18n.PageLang]:
    """The move's words (the `refresh` area of data/i18n/en.yaml) in the run's working language, or English with the
    warning to show the user when that language has no translation of them yet."""
    built = i18n.page_lang(i18n.run_languages(run).working, AREA)
    return i18n.translator(built.lang), built


# --- the proposal ------------------------------------------------------------------

def _saved(run: RunFolder, part: dict, what: str, fields: tuple[str, ...], out: list[Problem]) -> None:
    missing = [f for f in fields if not _text(part.get(f))]
    if missing or not _in_run(run, part.get("saved")):
        out.append(Problem(what, f"The {what}'s {', '.join(missing) or 'ids'} are not read from Meta and saved in the "
                           "run.", f"Read them with the Meta Ads connector, save the answer in {RESULTS}/ and name it "
                           "in saved."))


def check_proposal(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    if not _text(data.get("ad_account_id")):
        out.append(Problem("ad_account_id", "The ad account is missing.", "Write the ad account."))
    original = data.get("original") if isinstance(data.get("original"), dict) else {}
    winner = data.get("winner") if isinstance(data.get("winner"), dict) else {}
    _saved(run, original, "original", ("ad_id", "adset_id", "campaign_id"), out)
    _saved(run, winner, "winner", ("key", "ad_id", "post_id"), out)
    adset = data.get("adset") if isinstance(data.get("adset"), dict) else {}
    if adset.get("id"):
        out.append(Problem("adset.id", "The ad goes into a new ad set, made now; the proposal names an existing one.",
                           "Leave the id out: the new ad set gets one when it is created."))
    if original.get("adset_id") and adset.get("id") == original.get("adset_id"):
        out.append(Problem("adset", "The ad is never put inside the original's ad set: that would restart its "
                           "learning.", "Propose a new ad set in the original's campaign."))
    if not original.get("campaign_id") or adset.get("campaign_id") != original.get("campaign_id"):
        out.append(Problem("adset.campaign_id", "The new ad set goes into the original's campaign "
                           f"({original.get('campaign_id')!r}), not {adset.get('campaign_id')!r}.",
                           "Name the original's campaign."))
    if not original.get("adset_id") or adset.get("settings_from") != original.get("adset_id"):
        out.append(Problem("adset.settings_from", "The new ad set copies the targeting, placements, optimisation "
                           "and bid strategy of the original's ad set; the proposal does not name it.",
                           "Write the original's ad set id in settings_from."))
    out.extend(_budget_problems(adset.get("budget")))
    if not create_copy.readable(adset.get("name")):
        out.append(Problem("adset.name", f"The ad set name {adset.get('name')!r} does not say what it is.",
                           "Name it by product, the change that won and the test."))
    ad = data.get("ad") if isinstance(data.get("ad"), dict) else {}
    if not winner.get("post_id") or ad.get("post_id") != winner.get("post_id"):
        out.append(Problem("ad.post_id", "The ad is made from the test ad's post, so its likes, comments and shares "
                           "come along.", "Use the winning test ad's post id (its effective_object_story_id)."))
    if not create_copy.readable(ad.get("name")):
        out.append(Problem("ad.name", f"The ad name {ad.get('name')!r} does not say what it is.", "Name it."))
    if data.get("status") != PAUSED:
        out.append(Problem("status", f"The objects are created {PAUSED}, never {data.get('status')!r}.",
                           f"Set status to {PAUSED}."))
    return out


def _budget_problems(money: object) -> list[Problem]:
    """The new ad set's budget (pending the owner's rule, issue #64): none when the campaign holds the budget (CBO);
    otherwise the amount, the cadence, the currency and the user's own words, never inferred."""
    money = money if isinstance(money, dict) else {}
    if money.get("campaign_budget") is True:
        return []
    amount = money.get("amount")
    if (isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount > 0
            and money.get("cadence") in CADENCES and _text(money.get("currency")) and _text(money.get("said"))):
        return []
    return [Problem("adset.budget", "The new ad set's budget is either the campaign's (campaign_budget: true, when the "
                    "original's campaign holds the budget) or an amount, a cadence (daily or lifetime), a currency "
                    "and the user's own words: it is never inferred.", "Ask the user.")]


def _path(run: RunFolder, file: str | Path, stem: str) -> tuple[Path, str]:
    return create_copy._path(run, file, RESULTS, stem)


def check(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm live-test move check`: check the latest proposal; a clean one is marked."""
    _refresh_run(run)
    path, rel = _path(run, file, PROPOSAL)
    data, problems = create_plan._read(path)
    if data is None:
        return rel, problems
    problems = check_proposal(run, data)
    if not problems:
        stepchecks.mark(run, KEY_PROPOSAL, path)
    return rel, problems


def proposal(run: RunFolder) -> dict | None:
    """The checked proposal, when it is the latest and unchanged; else None."""
    if stepchecks.fresh(run, KEY_PROPOSAL, RESULTS, PROPOSAL, "json") is not None:
        return None
    return create_plan._read(run.latest(RESULTS, PROPOSAL, "json"))[0]


def card(run: RunFolder) -> dict:
    """What the go-ahead card shows: the proposal in full and the notes, in the keyed strings."""
    data = proposal(run) or {}
    tr, built = words(run)
    original = data.get("original") or {}
    campaign = original.get("campaign_name") or original.get("campaign_id") or ""
    return {"lang": built.lang, "language_warning": built.warning,
            "title": tr("refresh.move.title"), "question": tr("refresh.move.question", campaign=campaign),
            "notes": [tr("refresh.move.post_note"), tr("refresh.move.own_adset_note"), tr("refresh.move.paused_note")],
            "original": original, "winner": data.get("winner"), "adset": data.get("adset"), "ad": data.get("ad"),
            "status": data.get("status")}


# --- the user's yes, or no -----------------------------------------------------------

def approve(run: RunFolder, note: str) -> str:
    """`tm live-test move approve`: the user's yes to the checked proposal, in their words."""
    _refresh_run(run)
    if not _text(note):
        raise ValueError("Pass the user's own yes with --note \"<their words>\".")
    if proposal(run) is None:
        raise ValueError("The move proposal is not checked, or changed after its check: check it first "
                         "(tm live-test move check), show the card and ask.")
    rel = _latest_rel(run, PROPOSAL)
    stepchecks.mark(run, KEY_YES, rel, extra={"said": note.strip()})
    return rel


def decline(run: RunFolder, note: str) -> None:
    """`tm live-test move decline`: the user's no; nothing is created, and the final report doesn't ask again."""
    _refresh_run(run)
    if not _text(note):
        raise ValueError("Pass the user's own words with --note \"<their words>\".")
    s = state.load(run)
    s.checked[KEY_NO] = {"said": note.strip()}
    state.save(run, s)


def _yes_gap(run: RunFolder) -> str | None:
    gap = stepchecks.fresh(run, KEY_YES, RESULTS, PROPOSAL, "json")
    return None if gap is None else "the user's yes to the latest checked proposal (tm live-test move approve)"


# --- the objects, read back ----------------------------------------------------------

def check_record(run: RunFolder, data: dict) -> list[Problem]:
    plan = proposal(run)
    if plan is None:
        return [Problem("proposal", "The move proposal is not checked.", "Check it first (tm live-test move check).")]
    yes = _yes_gap(run)
    if yes:
        return [Problem("yes", "Nothing is created without the user's yes to the proposal.", f"Ask first: {yes}.")]
    out: list[Problem] = []
    if data.get("proposal") != _latest_rel(run, PROPOSAL):
        out.append(Problem("proposal", "The record does not name the checked proposal.", "Name it."))
    adset = data.get("adset") if isinstance(data.get("adset"), dict) else {}
    ad = data.get("ad") if isinstance(data.get("ad"), dict) else {}
    not_paused = []
    for what, obj in (("ad set", adset), ("ad", ad)):
        if not (_text(obj.get("id")) and _text(obj.get("status"))):
            out.append(Problem(what, f"The {what} has no id or status read back from Meta.",
                               "Read the objects back and record each id and status."))
        elif obj["status"].upper() != PAUSED:
            not_paused.append(i18n.t("refresh.move.active_found", what=f"The {what} {obj.get('name') or obj['id']}",
                                     status=obj["status"]))
    if not_paused:
        raise Stop(" ".join(not_paused) + f" Nothing was recorded; {AGAIN}.")
    original, winner = plan.get("original") or {}, plan.get("winner") or {}
    if adset.get("id") and adset.get("id") == original.get("adset_id"):
        out.append(Problem("adset.id", "The ad was put inside the original's ad set, which restarts its learning.",
                           "Delete that ad and create it in a new ad set in the original's campaign, PAUSED."))
    if adset.get("campaign_id") != original.get("campaign_id"):
        out.append(Problem("adset.campaign_id", "The new ad set is not in the original's campaign.",
                           "Read it back again; it belongs in the original's campaign."))
    if ad.get("adset_id") != adset.get("id"):
        out.append(Problem("ad.adset_id", "The ad is not in the new ad set.", "Read it back again."))
    if ad.get("post_id") != winner.get("post_id"):
        out.append(Problem("ad.post_id", "The ad is not the test ad's post, so its engagement did not come along.",
                           "Make the ad from the winning test ad's post, PAUSED."))
    if not _text(ad.get("preview_url")):
        out.append(Problem("ad.preview_url", "The ad has no preview link.", "Read its preview (ads_get_ad_preview)."))
    if not _in_run(run, data.get("answers")):
        out.append(Problem("answers", "Meta's answers are not saved in the run.", f"Save them in {RESULTS}/."))
    return out


def record(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm live-test move record`: check the objects read back; a clean record is marked. Raises Stop for an object
    that is not paused."""
    _refresh_run(run)
    path, rel = _path(run, file, OBJECTS)
    data, problems = create_plan._read(path)
    if data is None:
        return rel, problems
    problems = check_record(run, data)
    if not problems:
        stepchecks.mark(run, KEY_OBJECTS, path)
    return rel, problems


def recorded(run: RunFolder) -> dict | None:
    if stepchecks.fresh(run, KEY_OBJECTS, RESULTS, OBJECTS, "json") is not None:
        return None
    return create_plan._read(run.latest(RESULTS, OBJECTS, "json"))[0]


def report(run: RunFolder) -> dict:
    """The user's part, for the final report: what was created (PAUSED), the preview, and the steps that stay theirs:
    switch the new ad on, move the budget, switch the original off."""
    data = recorded(run)
    if data is None:
        raise ValueError("The moved ad is not recorded yet (tm live-test move record).")
    plan = proposal(run) or {}
    original = plan.get("original") or {}
    tr, built = words(run)
    campaign = original.get("campaign_name") or original.get("campaign_id")
    adset = data["adset"].get("name") or data["adset"]["id"]
    values = {"campaign": campaign, "adset": adset, "ad": data["ad"].get("name") or data["ad"]["id"],
              "original_ad": original.get("ad_name") or original.get("ad_id"),
              "original_adset": original.get("adset_name") or original.get("adset_id")}
    shared = ((plan.get("adset") or {}).get("budget") or {}).get("campaign_budget") is True
    steps = [tr("refresh.move.step_switch_on", **values),
             tr("refresh.move.step_budget_campaign" if shared else "refresh.move.step_budget", **values),
             tr("refresh.move.step_switch_off", **values)]
    created = tr("refresh.move.created", **values)
    text = "\n".join([created, tr("refresh.move.steps_title"), *(f"{i}. {s}" for i, s in enumerate(steps, 1)),
                      tr("refresh.move.never_on")])
    return {"text": text, "created": created, "steps": steps, "lang": built.lang,
            "language_warning": built.warning, "preview_url": data["ad"].get("preview_url"),
            "ids": {"adset": data["adset"]["id"], "ad": data["ad"]["id"]}}


def done_note(run: RunFolder) -> str | None:
    """What `tm next` adds to a finished run's message after G12 `scale`: offer the move, or report the user's part."""
    s = state.load(run)
    if s.playbook != REFRESH_AD or _g12(s) != "scale":
        return None
    if recorded(run) is not None:
        return ("The winning ad was moved, PAUSED: end the final report with the user's part, step by step "
                "(tm live-test move report --run R).")
    if KEY_NO in s.checked:
        return None
    return ("The variant won (G12 scale). Unless the user already answered it, ask once: \"Shall I create a new ad set "
            "in your original campaign, PAUSED, with the winning ad from the test's post?\" (flow.md#e4). Nothing is "
            "switched on; on a no, tm live-test move decline.")
