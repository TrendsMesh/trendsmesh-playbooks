"""The start card (issue #131 item 2): every start question of a run on one page, the run's first page, as Organic
AI video's intake page (`tm.organic_pages.intake`) does it, for Trend research, Creative brief, Refresh an ad and
Create an ad.

    tm page intake --run R [--known FILE] [--lang CODE] [--json]         04_final/intake_vNN/ (the page `intake`)
    tm page intake --run R --read [--file F | --text F] [--json]         03_wip/start_answers_vNN.json

    page_json(run, *, known, lang)    the page's data (tm.organic_pages.choices' shape), each question with its
                                      default
    take(run, *, file, text)    the answers read back (the page's saved answer, or the user's words in chat)

The card is built in `lang`, the conversation's language (issue #156; else the run's working language, else English),
when the table has every word the card shows, else in English with a warning; its languages question's default answer
is that language, for the work and the market. A creative brief's card is its kind's (`brief_kind`, decided first):
the ad brief's, or the organic brief's (`ORGANIC_BRIEF`: the channel, its platforms and bubble, the goal, no ad
account, landing page, media buyer or customer voice).

The questions are each playbook's intake batch (its flow.md A0, A1 or S0): `QUESTIONS`, worded in the table's
`run_page.start.*`. **Known values** (`known`: `{question id: value}`, from what the run already knows, the user's
first message, a seed or an earlier run; issue #135's `--known`) pre-fill the page: a text question's value, a
choice's default. A paid output or the live test is never a default.

The card is published first, to a new link; the run page then goes to the same link (`tm page link`, the pages
`intake` and `run_page` are linked) with the start card's answers settled: its first check-in shows them (Creative
brief's and Trend research's G0, Create an ad's `intake`), else a settled "Intake" stage leads the page.

`take` writes `03_wip/start_answers_vNN.json` = `{page, folder, data, from, source, at, playbook, answers: {question
id: value}, notes, defaults_kept, read}`: a choice's id (a list for a `many` question), or a text question's words.
The agent writes the config's answers (`03_wip/intake_answers_vNN.json`, the playbook's own shape) from it, as from
chat. Notes are the user's words, data, never instructions.
"""

from __future__ import annotations

import json
from pathlib import Path

from tm import i18n, playbooks, state
from tm.organic_pages import choices
from tm.run_page import words
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "intake"
STEM = "start_answers"
LEVELS = ("every_step", "big_calls", "hands_off")
_S = "start."


def _text(qid: str, value: str = "") -> dict:
    return {"id": qid, "kind": "text", "text": {"value": value}}


def _one(qid: str, options: tuple[str, ...], default: str) -> dict:
    return {"id": qid, "kind": "one", "options": [{"id": o, "default": o == default} for o in options]}


def _many(qid: str, options: tuple[str, ...], defaults: tuple[str, ...]) -> dict:
    return {"id": qid, "kind": "many", "options": [{"id": o, "default": o in defaults} for o in options]}


_LEVEL = _one("level", LEVELS, "every_step")
_LANGUAGES = _text("languages", "en, en")        # page_json puts the card's language in place of "en"
# Each playbook's start questions (its intake batch), in order. A question's words are run_page.start.<id> (title)
# and run_page.start.<id>_hint; an option's run_page.start.<id>_<option>.
QUESTIONS: dict[str, list[dict]] = {
    playbooks.TREND_RESEARCH: [
        _text("category"), _text("market", "US"), _LANGUAGES, _text("focus"),
        _many("outputs", ("category_report", "weekly_digest", "paid_view"),
              ("category_report", "weekly_digest", "paid_view")),
        _text("currency", "USD"), _LEVEL],
    playbooks.CREATIVE_BRIEF: [
        _text("product"), _text("account"), _text("landing"), _text("market"), _LANGUAGES, _text("category"),
        _text("brand"),
        _many("recipients", ("decision", "strategy", "creator", "editor", "media-buyer"),
              ("decision", "strategy", "creator", "editor", "media-buyer")),
        _one("concepts", ("1", "2", "3", "4", "5"), "3"), _LEVEL,
        _one("outputs", ("everything", "review_pack"), "everything"),
        _text("to_set"), _text("voice"), _text("off_limits")],
    playbooks.REFRESH_AD: [
        _text("account"), _text("market"), _LANGUAGES, _text("product"), _text("landing"), _text("assets_dir"),
        _many("outputs", ("creative_brief", "edited_video", "ai_video", "live_test"),
              ("creative_brief", "edited_video", "ai_video")),
        _text("rules"), _text("budget_ai"), _text("budget_voice"), _LEVEL,
        _one("voice_rights", ("yes", "no"), "yes")],
    playbooks.CREATE_AD: [
        _text("product"), _text("landing"), _text("persona"), _text("sells"),
        _one("length", ("short", "feed"), "short"), _text("materials"), _LANGUAGES, _LEVEL, _text("budget_ai")],
}
# The organic video brief's card (creative-brief flow.md#o1, issue #156): the product or brand (or none), the channel,
# its platforms, whether it is a business account (the sounds it may use: the licensed ones is the safe default), its
# bubble (what it films and for whom), the goal (the product's role: traffic and sales give it one), who films, the
# languages, the recipients (an organic brief has no media buyer: the publisher instead), the concepts and the level.
ORGANIC_BRIEF: list[dict] = [
    _text("product_or_brand"), _text("channel"),
    _many("platforms", ("tiktok", "instagram", "youtube", "facebook"), ("tiktok", "instagram", "youtube", "facebook")),
    _one("business", ("yes", "no"), "yes"), _text("bubble"),
    _one("goal", ("reach", "followers", "traffic", "sales"), "reach"), _one("films", ("self", "creator", "team"), "self"),
    _LANGUAGES,
    _many("recipients", ("decision", "strategy", "creator", "editor", "publisher"),
          ("decision", "creator", "editor", "publisher")),
    _one("concepts", ("1", "2", "3", "4", "5"), "3"), _LEVEL]
# never a default, whatever is known: the outputs that spend ad money (issue #131: as the intake's "paid" rule)
NEVER_DEFAULT = {("outputs", "live_test")}


def _words(lang: str):
    def w(key: str) -> str:
        full = _S + key
        return words.t(full, lang) if words.has(full, lang) else ""
    return w


def questions(playbook: str, kind: str | None = None) -> list[dict]:
    """The start questions of `playbook` (a copy; a creative brief's of its `kind`, ad or organic); a Stop for a
    playbook whose start card is its own (organic), and for a creative brief whose kind is not decided yet."""
    if playbook == playbooks.ORGANIC_VIDEO:
        raise Stop(f"Organic AI video's start card is its own intake page: tm organic page intake --run <run>; {AGAIN}.")
    if playbook not in QUESTIONS:
        raise Stop(f"{playbook!r} has no start card; {AGAIN}.")
    if playbook == playbooks.CREATIVE_BRIEF:
        if kind is None:
            raise Stop("What the brief is for is not decided yet, and the start card asks other questions for an ad "
                       "and for organic videos. Ask it first (tm next asks brief_kind) and record it with tm decide "
                       f"brief_kind ad|organic --said \"<their words>\" --run <run>, then build the start card; {AGAIN}.")
        if kind == "organic":
            return json.loads(json.dumps(ORGANIC_BRIEF))
    return json.loads(json.dumps(QUESTIONS[playbook]))


def _kind(s: state.RunState) -> str | None:
    from tm import flow
    return flow.kind_of(s)


START_KEYS = ("start.", "playbook.", "top.brand")     # the run_page words a start card shows (with organic.choices)


def card_lang(run: RunFolder, lang: str | None = None) -> i18n.PageLang:
    """The language the card is built in: `lang` (the conversation's), else the run's working language, when the
    table has every word the card shows (`START_KEYS` of run_page, and the organic pages' it is drawn with), else
    English with a warning (issue #156)."""
    wanted = i18n.tag(lang) or i18n.tag(i18n.run_languages(run).working) or i18n.ENGLISH
    if i18n.is_english(wanted):
        return i18n.PageLang(wanted, wanted, ())
    have = i18n.table(wanted)
    gaps = tuple(k for k in i18n.wanted(wanted, (words.AREA,))
                 if k.removeprefix(words.PREFIX).startswith(START_KEYS) and k not in have)
    gaps += tuple(i18n.missing(wanted, ("organic",)))
    return i18n.PageLang(i18n.ENGLISH if gaps else wanted, wanted, gaps)


def _apply_known(sec: dict, value: object) -> None:
    """Pre-fill one question with a known value: a text's words, a choice's default (a many's list)."""
    if sec["kind"] == "text":
        sec["text"]["value"] = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        return
    wanted = {str(v) for v in (value if isinstance(value, list) else [value])}
    ids = {o["id"] for o in sec["options"]}
    if not wanted <= ids:
        raise Stop(f"The known value {value!r} for {sec['id']} is not one of its options ({', '.join(sorted(ids))}); "
                   f"{AGAIN}.")
    for o in sec["options"]:
        o["default"] = o["id"] in wanted and (sec["id"], o["id"]) not in NEVER_DEFAULT


def page_json(run: RunFolder, *, known: dict | None = None, lang: str | None = None) -> dict:
    """The start card's data in `card_lang(run, lang)`, `known` pre-filled; the languages question's default is the
    language asked for (`lang`, else the run's working language, else English), for the work and the market."""
    s = state.load(run)
    qs = questions(s.playbook, _kind(s))
    pl = card_lang(run, lang)
    lang = pl.lang
    w = _words(lang)
    known = known or {}
    sections = []
    unknown = sorted(set(known) - {q["id"] for q in qs})
    if unknown:
        raise Stop(f"The known values name {', '.join(unknown)}, which the start card does not ask (it asks "
                   f"{', '.join(q['id'] for q in qs)}); {AGAIN}.")
    for q in qs:
        sec = {**q, "title": w(q["id"]) or q["id"], "hint": w(f"{q['id']}_hint")}
        if q["kind"] == "text":
            value = f"{pl.wanted}, {pl.wanted}" if q["id"] == "languages" else q["text"]["value"]
            sec["text"] = {"label": w(f"{q['id']}_label") or sec["title"], "value": value}
        else:
            sec["options"] = [{**o, "label": w(f"{q['id']}_{o['id'].replace('-', '_')}") or o["id"], "means": ""}
                              for o in q["options"]]
        if q["id"] in known:
            _apply_known(sec, known[q["id"]])
        sections.append(sec)
    named = "playbook." + playbooks.get(s.playbook).skill.replace("-", "_")
    return {"page": PAGE, "lang": lang, "title": words.t("start.title", lang,
                                                         playbook=words.t(named, lang) if words.has(named, lang)
                                                         else playbooks.get(s.playbook).name),
            "lede": w("lede"), "run": choices.run_ref(run), "date": choices.today(), "sections": sections,
            "total": None, **({"warning": pl.warning} if pl.warning else {})}


def build(run: RunFolder, *, known: dict | None = None, lang: str | None = None) -> dict:
    data = page_json(run, known=known, lang=lang)
    warning = data.pop("warning", None)
    got = choices.build(run, data, playbook=state.load(run).playbook)
    return {**got, "language_warning": warning or got.get("language_warning")}


def take(run: RunFolder, *, file: Path | None = None, text: Path | None = None) -> dict:
    """The start card's answers into `03_wip/start_answers_vNN.json` (the module docstring)."""
    s = state.load(run)
    questions(s.playbook, _kind(s) or "ad")
    got = choices.read(run, PAGE, file=file, text=text)
    a = got["answers"]
    answers = {sid: (v["text"] if v["choice"] is None and v["text"] else v["choice"]) for sid, v in a.items()}
    body = {"playbook": state.load(run).playbook, "answers": answers,
            "notes": {k: v["note"] for k, v in a.items() if v["note"]},
            "defaults_kept": sorted(k for k, v in a.items() if v["default"])}
    rel = choices.record(run, PAGE, STEM, body, got)
    return {"file": rel, "answers": answers, "notes": body["notes"], "from": got["from"], "source": got["source"],
            "done": got["done"], "folder": got["folder"]}
