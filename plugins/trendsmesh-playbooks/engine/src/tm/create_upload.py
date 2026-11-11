"""Create an ad (playbook 05), S10: the Meta upload, offered, proposed in full and created PAUSED (CA14).

S10a. The agent runs the checks (the Pages the ad account can use; the site's pixel: which one, whether it fires,
which events arrive), saves each Meta answer in the run, and writes the proposal, `05_results/upload_proposal_vNN.json`
(the format: skills/create-ad/references/flow.md#s10a). `tm ad upload check` refuses a proposal that does not list
everything in full, that rests on a check it did not save, whose objective, ad budget or AI disclosure has no words
from the user (the budget is never inferred; the disclosure is the advertiser's call), that optimises for a
conversion the pixel does not send, that runs several text variants under Traffic, whose names read like "Ad set 1",
whose files are not the delivered ones, whose copy is not the accepted copy, or whose status is not PAUSED. `card`
gives what the go-ahead card shows: the proposal and the placement facts, in the working language (tm.i18n).

S10b. After the user's go-ahead, the objects are created PAUSED (or as drafts), read back, and written to
`05_results/meta_objects_vNN.json`. `tm ad upload record` checks it: every object's id and status, each video
`ready`, each creative's AI disclosure as proposed, a preview link per ad, the Meta answers saved. **An object that
is not paused (or a draft) is a stop**: pause it now. Nothing in this playbook activates an ad (issue #46).
"""

from __future__ import annotations

import re
from pathlib import Path

from tm import create_config, create_copy, create_plan, i18n, state, stepchecks
from tm.config import Problem
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

RESULTS, FINAL = "05_results", create_copy.FINAL
PROPOSAL, OBJECTS = "upload_proposal", "meta_objects"
KEY_PROPOSAL, KEY_OBJECTS = "ad_upload_proposal", "ad_upload_record"
OBJECTIVES = ("OUTCOME_AWARENESS", "OUTCOME_ENGAGEMENT", "OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_TRAFFIC",
              "OUTCOME_APP_PROMOTION")
MULTI_TEXT = ("OUTCOME_AWARENESS", "OUTCOME_ENGAGEMENT", "OUTCOME_LEADS", "OUTCOME_SALES")  # 2 to 5 text variants
# optimisation events that need no pixel: everything else is a conversion the pixel must send
NO_PIXEL_EVENTS = ("LINK_CLICKS", "LANDING_PAGE_VIEWS", "REACH", "IMPRESSIONS", "THRUPLAY", "VIDEO_VIEWS",
                   "POST_ENGAGEMENT", "TWO_SECOND_CONTINUOUS_VIDEO_VIEWS")
CADENCES = ("daily", "lifetime")
DISCLOSURES = ("OPT_IN", "OPT_OUT")
PAUSED, DRAFT = "PAUSED", "DRAFT"
CREATED_AS = {"paused": (PAUSED,), "draft": (DRAFT, PAUSED)}
COUNTRY = re.compile(r"^[A-Z]{2}$")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _event(name: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


def _in_run(run: RunFolder, rel: object) -> bool:
    return create_plan._in_run(run, rel)


def _latest_rel(run: RunFolder, stage: str, stem: str, ext: str) -> str | None:
    path = run.latest(stage, stem, ext)
    return path.relative_to(run.path).as_posix() if path else None


def _thumb(run: RunFolder, key: str) -> str | None:
    return next((r for r in (_latest_rel(run, FINAL, f"{key}_thumb", e) for e in ("jpg", "png")) if r), None)


# --- S10a the proposal ------------------------------------------------------------

def _checks(run: RunFolder, data: dict, out: list[Problem]) -> dict:
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    pages = checks.get("pages") if isinstance(checks.get("pages"), dict) else {}
    if not (_in_run(run, pages.get("saved")) and isinstance(pages.get("ids"), list) and pages["ids"]):
        out.append(Problem("checks.pages", "The Pages the ad account can use are not checked and saved.",
                           "Ask Meta which Pages the account can use, save the answer, and list their ids."))
    elif data.get("page_id") not in pages["ids"]:
        out.append(Problem("page_id", "The proposal's Page is not one the ad account can use.",
                           "Pick one of the checked Pages."))
    pixel = checks.get("pixel") if isinstance(checks.get("pixel"), dict) else None
    if pixel is None or not _in_run(run, pixel.get("saved")) or not isinstance(pixel.get("fires"), bool) \
            or not isinstance(pixel.get("events"), list):
        out.append(Problem("checks.pixel", "The site's pixel is not checked: which one it is, whether it fires and "
                           "which events arrive (saved).", "Check the pixel before the proposal: it decides which "
                           "objective and optimisation event are possible."))
        return {}
    return pixel


def _objective(data: dict, pixel: dict, out: list[Problem]) -> str | None:
    obj = data.get("objective") if isinstance(data.get("objective"), dict) else {}
    options = obj.get("options")
    if not (isinstance(options, list) and 1 <= len(options) <= 2 and all(
            isinstance(o, dict) and o.get("objective") in OBJECTIVES and _text(o.get("event")) and _text(o.get("why"))
            for o in options)):
        out.append(Problem("objective.options", "The objective and optimisation event are proposed as 1 or 2 options, "
                           f"each an objective ({', '.join(OBJECTIVES)}), an event and why.", "Write the options."))
        return None
    chosen = obj.get("chosen")
    if not (isinstance(chosen, int) and 0 <= chosen < len(options)) or not _text(obj.get("said")):
        out.append(Problem("objective.chosen", "The objective has no pick in the user's words.",
                           "Ask the user which option, and write their words in said."))
        return None
    pick = options[chosen]
    event = _event(pick["event"])
    if event not in {_event(e) for e in NO_PIXEL_EVENTS}:
        sent = {_event(e) for e in pixel.get("events") or []}
        if not pixel.get("fires") or not pixel.get("dataset_id") or event not in sent:
            out.append(Problem("objective", f"{pick['event']} is a conversion the site's pixel does not send.",
                               "Optimise for what the pixel sends, or for clicks with the UTM link, and say what that "
                               "costs (CA14)."))
    return pick["objective"]


def check_proposal(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    copy_rel = _latest_rel(run, FINAL, create_copy.ACCEPTED, "json")
    copy = create_copy.accepted(run)
    if copy is None:
        return [Problem("copy", "The copy is not accepted yet.", "Nothing is uploaded before the copy is accepted "
                        "(CA13): accept it first (tm ad copy accept).")]
    if data.get("copy") != copy_rel:
        out.append(Problem("copy", f"The proposal's copy is {data.get('copy')!r}, not the accepted copy {copy_rel}.",
                           "Name the accepted copy."))
    if not _text(data.get("ad_account_id")):
        out.append(Problem("ad_account_id", "The ad account is missing.", "Write the ad account."))
    pixel = _checks(run, data, out)
    objective = _objective(data, pixel, out) if pixel else None
    texts = max((len(ad.get("primary_texts") or []) for ad in copy["ads"]), default=0)
    if objective and texts > 1 and objective not in MULTI_TEXT:
        out.append(Problem("objective", f"{texts} text variants need the Awareness, Engagement, Leads or Sales "
                           "objective; Traffic takes one.", "Keep one primary text, or pick another objective."))
    money = data.get("budget") if isinstance(data.get("budget"), dict) else {}
    amount = money.get("amount")
    if not (isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount > 0
            and money.get("cadence") in CADENCES and _text(money.get("currency")) and _text(money.get("said"))):
        out.append(Problem("budget", "The ad budget needs the amount, the cadence (daily or lifetime), the currency "
                           "and the user's own words: it is never inferred.", "Ask the user (CA14)."))
    countries = data.get("country")
    if not (isinstance(countries, list) and countries and all(isinstance(c, str) and COUNTRY.match(c)
                                                              for c in countries)):
        out.append(Problem("country", "The countries must be two-letter codes, such as PL or DE.", "Write them."))
    for field in ("audience", "placements"):
        value = data.get(field)
        if not (value == "advantage_plus" or (isinstance(value, (dict, list)) and value)):
            out.append(Problem(field, f"The {field} is missing (Advantage+ by default).", f"Write the {field}."))
    names = data.get("names") if isinstance(data.get("names"), dict) else {}
    for field in ("campaign", "adset"):
        if not create_copy.readable(names.get(field)):
            out.append(Problem(f"names.{field}", f"The {field} name {names.get(field)!r} does not say what it is.",
                               "Name it by product, test, audience and concept (CA14)."))
    keys = [ad["key"] for ad in copy["ads"]]
    ads = data.get("ads") if isinstance(data.get("ads"), list) else []
    by_key = {a.get("key"): a for a in ads if isinstance(a, dict)}
    if sorted(map(str, by_key)) != sorted(keys):
        out.append(Problem("ads", f"The proposal's ads are {sorted(map(str, by_key))}, not the accepted copy's "
                           f"{sorted(keys)}.", "One creative and one ad per accepted ad."))
    for key in keys:
        ad = by_key.get(key) or {}
        if ad.get("video") != _latest_rel(run, FINAL, key, "mp4"):
            out.append(Problem(f"ads.{key}.video", f"{key}'s video is not the delivered one in {FINAL}.",
                               "Name the delivered video."))
        if not ad.get("thumbnail") or ad.get("thumbnail") != _thumb(run, key):
            out.append(Problem(f"ads.{key}.thumbnail", f"{key}'s thumbnail is not the delivered one in {FINAL}.",
                               "Name the delivered thumbnail."))
        if not create_copy.readable((names.get("ads") or {}).get(key) if isinstance(names.get("ads"), dict) else None):
            out.append(Problem(f"names.ads.{key}", f"{key}'s ad name does not say what it is.", "Name it (CA14)."))
    ai = data.get("ai_disclosure") if isinstance(data.get("ai_disclosure"), dict) else {}
    if ai.get("value") not in DISCLOSURES or not _text(ai.get("said")):
        out.append(Problem("ai_disclosure", "The AI-content disclosure needs the user's answer (OPT_IN or OPT_OUT) in "
                           "their words: it is the advertiser's decision, set when the creative is made.",
                           f"Ask: \"{i18n.t('ad.upload.ai_question')}\""))
    if data.get("status") != PAUSED:
        out.append(Problem("status", f"The objects are created {PAUSED}, never {data.get('status')!r}.",
                           f"Set status to {PAUSED}."))
    return out


def _path(run: RunFolder, file: str | Path, stem: str) -> tuple[Path, str]:
    return create_copy._path(run, file, RESULTS, stem)


def check(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm ad upload check`: check the latest proposal; a clean one is marked."""
    if state.load(run).playbook != CREATE_AD:
        raise ValueError("tm ad upload is for Create an ad runs.")
    path, rel = _path(run, file, PROPOSAL)
    data, problems = create_plan._read(path)
    if data is None:
        return rel, problems
    problems = check_proposal(run, data)
    if not problems:
        stepchecks.mark(run, KEY_PROPOSAL, path)
    return rel, problems


def proposal(run: RunFolder) -> dict | None:
    if stepchecks.fresh(run, KEY_PROPOSAL, RESULTS, PROPOSAL, "json") is not None:
        return None
    return create_plan._read(run.latest(RESULTS, PROPOSAL, "json"))[0]


def card(run: RunFolder) -> dict:
    """What the go-ahead card (and later its page) shows: the proposal in full, the accepted copy, the placement facts
    and, without a pixel that fires, what that costs; in the keyed strings."""
    data = proposal(run) or {}
    tr, built = create_config.page_words(run)
    pixel = (data.get("checks") or {}).get("pixel") or {}
    notes = []
    if not pixel.get("dataset_id"):
        notes.append(tr("ad.upload.pixel_none"))
    elif not pixel.get("fires"):
        notes.append(tr("ad.upload.pixel_silent", dataset=pixel["dataset_id"]))
    obj = data.get("objective") or {}
    pick = (obj.get("options") or [{}])[obj.get("chosen") or 0] if obj.get("options") else {}
    return {"lang": built.lang, "language_warning": built.warning,
            "title": tr("ad.upload.title"), "question": tr("ad.upload.question"),
            "paused_note": tr("ad.upload.paused_note"),
            "facts": [tr("ad.upload.fact_no_description"), tr("ad.upload.fact_display_link")],
            "asks": {"budget": tr("ad.upload.budget_question"), "ai_disclosure": tr("ad.upload.ai_question")},
            "pixel_notes": notes,
            "ad_account_id": data.get("ad_account_id"), "page_id": data.get("page_id"), "names": data.get("names"),
            "objective": pick.get("objective"), "event": pick.get("event"), "why": pick.get("why"),
            "budget": data.get("budget"), "country": data.get("country"), "audience": data.get("audience"),
            "placements": data.get("placements"), "ads": data.get("ads"), "ai_disclosure": data.get("ai_disclosure"),
            "copy": create_copy.accepted(run), "status": data.get("status")}


# --- S10b the objects, read back --------------------------------------------------

def check_record(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    plan = proposal(run)
    if plan is None:
        return [Problem("proposal", "The upload proposal is not checked.", "Check it first (tm ad upload check).")]
    if data.get("proposal") != _latest_rel(run, RESULTS, PROPOSAL, "json"):
        out.append(Problem("proposal", "The record does not name the checked proposal.", "Name it."))
    created = data.get("created_as")
    if created not in CREATED_AS:
        out.append(Problem("created_as", "Say how Meta created the objects: paused or draft.", "Write it."))
    allowed = CREATED_AS.get(created, (PAUSED,))
    not_paused = []
    keys = sorted(a["key"] for a in plan.get("ads") or [] if isinstance(a, dict))
    groups = [("campaign", [data.get("campaign")]), ("ad set", [data.get("adset")]),
              ("ad", data.get("ads") if isinstance(data.get("ads"), list) else [])]
    for what, objects in groups:
        for obj in objects:
            if not (isinstance(obj, dict) and _text(obj.get("id")) and _text(obj.get("status"))):
                out.append(Problem(what, f"The {what} has no id or status read back from Meta.",
                                   "Read the objects back and record each id and status."))
                continue
            if obj["status"].upper() not in allowed:
                label = f"The {what} {obj.get('name') or obj['id']}"
                not_paused.append(i18n.t("ad.upload.active_found", what=label, status=obj["status"]))
    if not_paused:
        raise Stop(" ".join(not_paused) + f" Nothing was recorded; {AGAIN}.")
    ads = {a.get("key"): a for a in groups[2][1] if isinstance(a, dict)}
    if sorted(map(str, ads)) != keys:
        out.append(Problem("ads", f"The record's ads are {sorted(map(str, ads))}, not the proposal's {keys}.",
                           "Record one ad per proposed ad."))
    for key, ad in ads.items():
        if not _text(ad.get("preview_url")):
            out.append(Problem(f"ads.{key}.preview_url", f"{key} has no preview link.", "Read its preview."))
    videos = {v.get("key"): v for v in data.get("videos") or [] if isinstance(v, dict)}
    for key in keys:
        v = videos.get(key) or {}
        if not _text(v.get("id")) or v.get("status") != "ready":
            out.append(Problem(f"videos.{key}", f"{key}'s video is not uploaded and ready.",
                               "Use the video only once Meta says it is ready."))
    want = (plan.get("ai_disclosure") or {}).get("value")
    creatives = {c.get("key"): c for c in data.get("creatives") or [] if isinstance(c, dict)}
    for key in keys:
        c = creatives.get(key) or {}
        if not _text(c.get("id")) or c.get("self_ai_disclosure") != want:
            out.append(Problem(f"creatives.{key}", f"{key}'s creative does not carry the AI disclosure the user chose "
                               f"({want}).", "It can't be set later: make the creative again with it, PAUSED."))
    if not _in_run(run, data.get("answers")):
        out.append(Problem("answers", "Meta's answers are not saved in the run.", f"Save them in {RESULTS}/."))
    return out


def record(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm ad upload record`: check the objects read back; a clean record is marked. Raises Stop for an object that is
    not paused."""
    if state.load(run).playbook != CREATE_AD:
        raise ValueError("tm ad upload is for Create an ad runs.")
    path, rel = _path(run, file, OBJECTS)
    data, problems = create_plan._read(path)
    if data is None:
        return rel, problems
    problems = check_record(run, data)
    if not problems:
        stepchecks.mark(run, KEY_OBJECTS, path)
    return rel, problems


def outcome(run: RunFolder) -> dict:
    """What the user hears after the upload: how it was created, every id, the preview links, how to switch it on."""
    if stepchecks.fresh(run, KEY_OBJECTS, RESULTS, OBJECTS, "json") is not None:
        raise ValueError("The objects are not recorded yet (tm ad upload record).")
    data = create_plan._read(run.latest(RESULTS, OBJECTS, "json"))[0]
    campaign = data["campaign"].get("name") or data["campaign"]["id"]
    tr, built = create_config.page_words(run)
    text = " ".join([tr(f"ad.upload.created_{data['created_as']}"), tr("ad.upload.activate_howto", campaign=campaign)])
    return {"created_as": data["created_as"], "text": text, "lang": built.lang, "language_warning": built.warning,
            "ids": {"campaign": data["campaign"]["id"], "adset": data["adset"]["id"],
                    "creatives": [c["id"] for c in data.get("creatives") or []],
                    "ads": [a["id"] for a in data.get("ads") or []]},
            "previews": {a["key"]: a["preview_url"] for a in data.get("ads") or []}}


# --- step checks ---------------------------------------------------------------

def proposal_gap(run: RunFolder) -> str | None:
    gap = stepchecks.fresh(run, KEY_PROPOSAL, RESULTS, PROPOSAL, "json")
    return f"the upload proposal passes tm ad upload check ({gap})" if gap else None


def record_gap(run: RunFolder) -> str | None:
    gap = stepchecks.fresh(run, KEY_OBJECTS, RESULTS, OBJECTS, "json")
    return f"the objects read back from Meta pass tm ad upload record ({gap})" if gap else None
