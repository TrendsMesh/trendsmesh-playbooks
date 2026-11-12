"""The intake page (organic video A0, issue #83 point 1): every start question on one page, one option set per
question with its default ticked, a text field only where something has to be typed, and one Done button.

    page_json(run, *, working, market, week)   the page's data (tm.organic_pages.choices)
    take(run, *, file, text)                   03_wip/intake_answers_vNN.json and 03_wip/intake_profile_vNN.json

The questions are flow.md A0's: the channel and its platforms, the account type, the bubble, what performed, the
catalogue and the product role, the two languages, the output, the video's quality tier and resolution, the budget
and the currency, the level, the content rules for a sensitive niche; a week run asks the week's own questions in
place of the output. **A paid output is never the default**: the default is the free script to film, and an AI video
is chosen only by a click (a week's contents default to scripts).

`take` reads the answers (`choices.read`: the page, or the user's words in chat) into two files: the answers in the
config's shape (`templates/intake_answers_example.json`), which `tm config write --answers` takes as it takes the
answers the agent writes from chat, and the profile's answers (the bubble, the links, the catalogue, the product
role, the platforms, the account type, the content rules) that A1 drafts the profile from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tm import brand, i18n, manifest, organic_pages, organic_proposals
from tm.organic_config import WEEKDAYS
from tm.organic_pages import choices
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "intake"
ANSWERS = "intake_answers"
PROFILE = "intake_profile"
_I = "organic.intake."
PLATFORM_NAMES = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube", "facebook": "Facebook"}
RESOLUTIONS = {"768p": ("768p", "none"), "1080p": ("1080p", "none"), "768p_pruna": ("768p", "pruna")}
TIERS = ("budget", "default", "top")
WEEK_DAYS_DEFAULT = ("mon", "wed", "fri", "sat", "sun")


def _opt(oid: str, label: str, means: str = "", *, default: bool = False, badge: str | None = None) -> dict:
    return {"id": oid, "label": label, "means": means, "default": default, **({"badge": badge} if badge else {})}


def page_json(run: RunFolder, *, working: str | None = None, market: str | None = None, week: bool = False) -> dict:
    """The intake page's data, in the working language (its table, else English). `working` and `market` are the
    defaults shown (the language you are talking in, and the audience's); `week` asks a week run's questions."""
    working = i18n.tag(working) or i18n.ENGLISH
    market = i18n.tag(market) or working
    tr = organic_pages.translator(organic_pages.page_lang({"lang": working}).lang)
    t = lambda key, **v: tr(_I + key, **v)
    lv = organic_pages.levels(tr)
    sections = [
        {"id": "channel", "kind": "text", "title": t("channel"), "hint": t("channel_hint"),
         "text": {"label": t("channel_label"), "value": ""}},
        {"id": "platforms", "kind": "many", "title": t("platforms"), "hint": t("platforms_hint"),
         "options": [_opt(p, PLATFORM_NAMES[p], default=True) for p in brand.PLATFORMS]},
        {"id": "account", "kind": "one", "title": t("account"),
         "options": [_opt("creator", t("account_creator"), default=True),
                     _opt("business", t("account_business"), t("account_business_means"))]},
        {"id": "bubble", "kind": "text", "title": t("bubble"), "hint": t("bubble_hint"),
         "text": {"label": t("bubble_label"), "value": ""}},
        {"id": "links", "kind": "text", "title": t("links"), "hint": t("links_hint"),
         "text": {"label": t("links_label"), "value": t("links_none")}},
        {"id": "catalogue", "kind": "text", "title": t("catalogue"), "hint": t("catalogue_hint"),
         "text": {"label": t("catalogue_label"), "value": t("catalogue_none")}},
        {"id": "product_role", "kind": "one", "title": t("product_role"), "hint": t("product_role_hint"),
         "options": [_opt(level.replace(" ", "_"), str(organic_pages.value(level, "product", tr)),
                          default=level == "not shown") for level in organic_proposals.PRODUCT_LEVELS]},
        {"id": "languages", "kind": "text", "title": t("languages"), "hint": t("languages_hint"),
         "text": {"label": t("languages_label"), "value": f"{working}, {market}"}},
    ]
    if week:
        days = [(d, tr(f"organic.week.day_{d}")) for d in WEEKDAYS]
        sections += [
            {"id": "contents", "kind": "one", "title": t("contents"),
             "options": [_opt("scripts", t("contents_scripts"), t("free"), default=True),
                         _opt("videos", t("contents_videos"), t("paid")),
                         _opt("mix", t("contents_mix"), t("paid"))]},
            {"id": "per_week", "kind": "one", "title": t("per_week"),
             "options": [_opt(str(n), str(n), default=n == 5) for n in range(1, 8)]},
            {"id": "days", "kind": "many", "title": t("days"),
             "options": [_opt(d, name, default=d in WEEK_DAYS_DEFAULT) for d, name in days]},
            {"id": "flexible_day", "kind": "one", "title": t("flexible_day"), "hint": t("flexible_day_hint"),
             "options": [_opt(d, name, default=d == "sun") for d, name in days]},
            {"id": "run_day", "kind": "one", "title": t("run_day"),
             "options": [_opt(d, name, default=d == "sun") for d, name in days]},
            {"id": "week_budget", "kind": "text", "title": t("week_budget"),
             "text": {"label": t("usd_label"), "value": "5"}},
        ]
    else:
        sections.append(
            {"id": "output", "kind": "one", "title": t("output"), "hint": t("output_hint"),
             "options": [_opt("script", t("output_script"), t("free"), default=True),
                         _opt("ai_video", t("output_video"), t("output_video_means"), badge=t("paid"))]})
    sections.append({"id": "quality", "kind": "one", "title": t("quality"), "hint": t("quality_hint"),
                     "options": [_opt(tier, t(f"quality_{tier}"), default=tier == "default") for tier in TIERS]})
    sections += [
        {"id": "resolution", "kind": "one", "title": t("resolution"), "hint": t("resolution_hint"),
         "options": [_opt(r, t(f"resolution_{r}"), default=r == "768p") for r in RESOLUTIONS]},
        {"id": "budget", "kind": "text", "title": t("budget"), "hint": t("budget_hint"),
         "text": {"label": t("usd_label"), "value": "5"}},
        {"id": "currency", "kind": "text", "title": t("currency"), "hint": t("currency_hint"),
         "text": {"label": t("currency_label"), "value": "USD"}},
        {"id": "level", "kind": "one", "title": t("level"),
         "options": [_opt(k, name, default=k == "every_step") for k, name in lv.items()]},
        {"id": "rules", "kind": "one", "title": t("rules"), "hint": t("rules_hint"),
         "options": [_opt("none", t("rules_none"), default=True), _opt("sensitive", t("rules_sensitive"))]},
    ]
    return {"page": PAGE, "lang": working, "title": t("title"), "lede": t("lede"), "run": choices.run_ref(run),
            "date": choices.today(), "sections": sections, "total": None, "week": week}


def build(run: RunFolder, **kw) -> dict:
    data = page_json(run, **kw)
    return choices.build(run, data, week=data["week"])


# --- the answers ---------------------------------------------------------------------------------------------

_NUMBER = re.compile(r"^\s*\$?\s*(\d+(?:[.,]\d+)?)\s*(?:usd|\$)?\s*$", re.IGNORECASE)


def _usd(text: str, what: str) -> float:
    m = _NUMBER.match(text or "")
    if not m:
        raise Stop(f"The {what} on the intake page is {text!r}, not a number of USD. Ask the user, then read their "
                   f"answer from chat (--text); {AGAIN}.")
    return float(m.group(1).replace(",", "."))


def _languages(text: str) -> dict:
    parts = [p.strip() for p in re.split(r"[,;/]", text or "") if p.strip()]
    working = i18n.tag(parts[0]) if parts else None
    market = i18n.tag(parts[1]) if len(parts) > 1 else working
    if working is None or market is None:
        raise Stop(f"The languages on the intake page are {text!r}: write them as two language tags, the working "
                   f"language then the market's (for example: pl, pl). Ask the user, then read their answer from "
                   f"chat (--text); {AGAIN}.")
    return {"working": working, "market": market}


def take(run: RunFolder, *, file: Path | None = None, text: Path | None = None) -> dict:
    """The intake's answers into `03_wip/intake_answers_vNN.json` (the config's shape, for `tm config write
    --answers`) and `03_wip/intake_profile_vNN.json` (A1's). Returns both paths and the answers."""
    got = choices.read(run, PAGE, file=file, text=text)
    a = got["answers"]
    week = bool(got["data"].get("week"))
    channels = [c.strip() for c in re.split(r"[,\n]", a["channel"]["text"]) if c.strip()]
    if not channels:
        raise Stop(f"The intake page names no channel. Ask the user for the channel's name, then read their answer "
                   f"from chat (--text, a line `channel: <name>`); {AGAIN}.")
    resolution, upscale = RESOLUTIONS[a["resolution"]["choice"] or "768p"]
    answers: dict = {
        "level": a["level"]["choice"] or "every_step",
        "outputs": ["weekly_plan"] if week else ["proposals"],
        "languages": _languages(a["languages"]["text"]),
        "channels": channels,
        "output": "weekly_pack" if week else (a["output"]["choice"] or "script"),
        "generation": {"resolution": resolution, "upscale": upscale},
        "budget": {"per_run_usd": _usd(a["budget"]["text"], "budget per run")},
        "currency": (a["currency"]["text"] or "USD").strip().upper(),
    }
    answers["generation"]["quality_tier"] = a["quality"]["choice"] or "default"
    if week:
        answers["weekly"] = {"contents": a["contents"]["choice"] or "scripts",
                             "per_week": int(a["per_week"]["choice"] or 5),
                             "days": a["days"]["choice"] or list(WEEK_DAYS_DEFAULT),
                             "flexible_day": a["flexible_day"]["choice"] or "sun",
                             "run_day": a["run_day"]["choice"] or "sun"}
        answers["budget"]["per_week_usd"] = _usd(a["week_budget"]["text"], "week's budget")
    role = (a["product_role"]["choice"] or "not_shown").replace("_", " ")
    profile = {"channels": channels, "platforms": a["platforms"]["choice"], "account": a["account"]["choice"],
               "bubble": a["bubble"]["text"], "links": a["links"]["text"], "catalogue": a["catalogue"]["text"],
               "product_role": role, "content_rules": a["rules"]["choice"] == "sensitive",
               "notes": {k: v["note"] for k, v in a.items() if v["note"]},
               "defaults_kept": sorted(k for k, v in a.items() if v["default"])}
    answers_rel = _write(run, ANSWERS, answers)
    profile_rel = choices.record(run, PAGE, PROFILE, {"answers_file": answers_rel, "profile": profile}, got)
    return {"answers": answers_rel, "profile": profile_rel, "intake": answers, "profile_answers": profile,
            "from": got["from"], "source": got["source"], "done": got["done"], "folder": got["folder"]}


def _write(run: RunFolder, stem: str, body: dict) -> str:
    """The answers in the config's shape, as the agent writes them from chat (no page fields in it)."""
    out = run.next_version("03_wip", stem, "json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, "03_wip", choices.DECISIONS_SOURCE, params={"page": PAGE})
    return rel
