"""The weekly pack of organic video (FLOWS.md I, decisions §9, the plan's Decision 14): the week plan and its check,
the one approval, a production run per slot, the flexible day, and one delivery page with the posting plan.

A week run (outputs `weekly_plan`) does the research of an idea run (B1 to B3), then:

I2. The agent writes `03_wip/week_vNN.json` in the handoff's schema (`schemas/pb3_week.schema.json`,
copied) with the plugin's block on every idea, slot or reserve (a reserve becomes a slot's idea by a swap):

    plugin = {"trends": [{"id": <trend id or its first 8 characters>, "pick": [<video index>, ...]}],
              "production": ai_footage|talking_character|animation|stills_motion|sections,
              "approach": Recreate|Inspire (Odtworzenie|Inspiracja), "product_level": <OV5's level>,
              "series": str|null, "flexible": bool}

`tm organic week check --run W --file F` runs `check` and marks the file (`stepchecks.mark`, key `week`); the step
check `week_checked` (`checked_gap`) asks that the latest week file is that one, unchanged. `tm organic page week`
builds the page (`organic_pages.week`), whose decisions `tm organic decisions --page week` reads into
`03_wip/decisions_week_vNN.json` (`choices` per slot, `total`). The check-in `week` ("Approve the week") is the one
approval: `tm decide week approve` requires `week_in_budget` (`budget_gap`), so a week over its budget, or one that
changes a started day, is refused (OVER_BUDGET). The yes covers the decisions it was given on (`flow.decide` keeps
`covered` in it: the decisions file and the `fingerprint` of each day's idea, output and OK); decisions read after it
that change any of those need a new yes (`tm decide week approve --change`) before any day starts. The approval holds
no money: each slot's production run has its own pack check-in and budget, at
the week run's level, and the money rules of any production run (the pack's yes, `tm budget approve`, the generation
guard) hold there.

I3. `tm organic start --run W` (`start`) makes one production run per slot marked OK except the flexible one, in day
order, as `tm organic start` does for a picked idea (`organic_proposals._plan`, `_make`): `<date>_<channel>-<idea
id>`, run.json `organic = {parent: W, week: W, slot: <day>, proposal, channel, key}`, the slot's output, the week's
platforms and level. The week run records each in `organic.started` (by `organic_proposals.idea_key`) and the
flexible day in `organic.flexible = {day, date, week}`. The skill produces the runs one after another. The step check
`slots_started` (`started_gap`) asks for a start of every OK slot but the flexible one. A day has one run whatever
its idea (`started_days`): a decision that changes a started day's idea or output, or skips it, is refused until the
user drops that run (`tm organic drop-slot --run W --day D --note N`, `drop_slot`: the run ends, its spend still
counts against the week). `tm organic flexible --run W
--file 03_wip/flexible_vNN.json` (`flexible`) starts the flexible slot the day before its day, from an idea built on
fresh trends: a new search and the idea's cards saved after the week was approved; `flow.due` reminds the user that
day and on the flexible day itself.

A slot's pack (`organic_pack.check`) is capped by the week too: its `ai_usd` at most `budget.per_week_usd` minus what
the week's other slot runs planned, approved or spent (`week_left`; for each, the largest of the three). The
user may set the week's budget (`tm organic week budget --run W --usd N --note N`, `set_budget`); their yes to the
week is then asked again.

I4. `tm organic deliver-week --run W` builds one delivery page for the week and the posting plan
(`tm.organic_week_delivery`, its step check `week_delivered`).
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tm import (brand, brief_research, checkins, config, json_schema, organic, organic_config,
                organic_proposals, organic_research, playbooks, state, stepchecks, trend_spool)
from tm.config import Problem
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

WIP = "03_wip"
STEM = "week"
KEY = "week"                   # the stepchecks.mark key
NAME = re.compile(rf"^{WIP}/{STEM}_v\d+\.json$", re.IGNORECASE)
FILE_PATTERN = f"{WIP}/{STEM}_vNN.json"
FLEXIBLE_NAME = re.compile(rf"^{WIP}/flexible_v\d+\.json$", re.IGNORECASE)
FLEXIBLE_PATTERN = f"{WIP}/flexible_vNN.json"
DECISIONS_STEM = "decisions_week"
SCHEMA = Path(__file__).parent / "schemas" / "pb3_week.schema.json"
RESULTS = "05_results"
PLAN_STEM = "posting_plan"
DELIVERY = "week_delivery"     # the week's delivery page (the plan page is `week`)
WEEK_OUTPUT = "weekly_plan"
OVER_BUDGET = "The week is over its budget: switch a video to a script, swap it for a cheaper idea, or skip it."
WEEKDAYS = organic_config.WEEKDAYS
PL_DAYS = ("pon", "wt", "śr", "czw", "pt", "sob", "niedz")       # the handoff's day keys
DAY = {**{d: d for d in WEEKDAYS}, **dict(zip(PL_DAYS, WEEKDAYS))}  # a slot's day (the handoff's key or English) -> English
OUTPUTS = ("video", "script")
OUTPUT_WORDS = organic.OUTPUT_WORDS
DECISIONS = ("ok", "skip")
TOL = 1e-9
_DATES = re.compile(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})$")
_TEXT_OR_NULL = {"type": ["string", "null"]}
PLUGIN: dict = {
    "type": "object",
    "required": ["trends", "production", "approach", "product_level", "series", "flexible"],
    "properties": {
        "trends": {"type": "array", "minItems": 1,
                   "items": {"type": "object", "required": ["id"],
                             "properties": {"id": {"type": "string"},
                                            "pick": {"type": "array", "items": {"type": "integer"}}}}},
        "production": {"enum": list(organic_proposals.PRODUCTIONS)},
        "approach": {"type": "string"},
        "product_level": {"type": "string"},
        "series": _TEXT_OR_NULL,
        "flexible": {"type": "boolean"},
    },
}
_SHAPE_TODO = (f"Write the week in the handoff's schema (schemas/{SCHEMA.name}) with the plugin block on every slot and "
               "reserve, as a new version.")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _usd(amount: float) -> str:
    return f"${amount:.2f}"


def _name(idea: dict) -> str:
    """An idea as the user knows it: its title (never a bare code)."""
    return f"“{idea.get('title') or idea.get('id')}” ({idea.get('id')})"


def ideas(week: dict) -> list[dict]:
    """The week's ideas, the slots' then the reserves'."""
    return [*week.get("slots", []), *week.get("reserves", [])]


# --- I2: the check ------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _schema() -> dict:
    """The handoff's schema with the plugin block required on every slot and reserve."""
    schema = copy.deepcopy(json_schema.load(SCHEMA))
    for key in ("slots", "reserves"):
        item = schema["properties"][key]["items"]
        item["properties"]["plugin"] = PLUGIN
        item["required"] = [*item["required"], "plugin"]
    return schema


def shape(data: object) -> list[Problem]:
    """What breaks the schema, as problems; empty when the file is in its shape."""
    return [Problem(line.split(" ", 1)[0].removeprefix("week."), line, _SHAPE_TODO)
            for line in json_schema.problems(data, _schema(), name="week")]


def dates(week: dict) -> tuple[date, date] | None:
    """The week's first and last day (`week`: "YYYY-MM-DD/YYYY-MM-DD", seven days), or None."""
    m = _DATES.match(str(week.get("week") or ""))
    try:
        first, last = (date.fromisoformat(m[1]), date.fromisoformat(m[2])) if m else (None, None)
    except ValueError:
        return None
    return (first, last) if first and last and last - first == timedelta(days=6) else None


def day_date(week: dict, day: str) -> date | None:
    """The date of an English weekday within the week, or None."""
    found = dates(week)
    if found is None or day not in WEEKDAYS:
        return None
    first = found[0]
    return first + timedelta(days=(WEEKDAYS.index(day) - first.weekday()) % 7)


def channel_of(week: dict, cfg: dict) -> str | None:
    """The run's channel (its slug in config.yaml `channels`) the week names, or None."""
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    slug = brand.channel_key(week["channel"]) if _text(week.get("channel")) else ""
    return slug if slug in channels else None


def _idea_problems(run: RunFolder, week: dict, idea: dict, where: str, used: dict, own: dict,
                   out: list[Problem]) -> None:
    """One idea's own problems: its id, costs, approach, product level and series, its trends resolved to saved cards,
    and a trend the channel already used only in a series (the slot run this idea itself was started as, `own`, is
    not another use)."""
    plugin = idea["plugin"]
    if why := organic_proposals._id_gap(idea["id"]):
        out.append(Problem(f"{where}.id", f"{_name(idea)}: its id {why} (it names the idea's production run and its "
                                          "files).", f"{_ID_TODO}."))
    for key in ("cost_video", "cost_script"):
        if not (math.isfinite(idea[key]) and idea[key] >= 0):
            out.append(Problem(f"{where}.{key}", f"{_name(idea)}: {key} is {idea[key]}.", "Give the cost in USD, 0 or "
                                                                                         "more."))
    if organic_proposals.APPROACHES.get(str(plugin["approach"]).strip().lower()) is None:
        out.append(Problem(f"{where}.plugin.approach", f"{_name(idea)}: the approach is {plugin['approach']!r}.",
                           "Write Recreate or Inspire (Odtworzenie or Inspiracja on a Polish page)."))
    if organic_proposals.PRODUCT_WORDS.get(str(plugin["product_level"]).strip().lower()) is None:
        out.append(Problem(f"{where}.plugin.product_level", f"{_name(idea)}: the product level is "
                           f"{plugin['product_level']!r}.",
                           f"Write one of {', '.join(organic_proposals.PRODUCT_LEVELS)} (OV5)."))
    if plugin["series"] is not None and not _text(plugin["series"]):
        out.append(Problem(f"{where}.plugin.series", f"{_name(idea)}: plugin.series is blank.",
                           "Write the series, or null."))
    view = {**idea, "trends": plugin["trends"]}
    found = organic_proposals._trends(run, view, f"{where}.plugin", out)
    key = organic_proposals.idea_key(as_proposal(week, idea, {"output": "video"}))
    organic_proposals._used(view, where, found, used, own.get(key), out)


_ID_TODO = "Name it w1, w2, r1, ... or another id of ASCII letters, digits, '_' and '-'"


def check(run: RunFolder, week: object, cfg: dict) -> list[Problem]:
    """Everything wrong in a week plan (the module docstring and the plan's Task 21); empty when it holds. Reads only."""
    problems = shape(week)
    if problems:
        return problems
    out: list[Problem] = []
    page_lang = cfg.get("page_lang")
    if week.get("lang") != page_lang:
        out.append(Problem("lang", f"The week is in {week.get('lang')!r}, and this run's pages are in {page_lang!r} "
                                   "(config.yaml page_lang).", f"Write it in {page_lang}, with lang {page_lang}."))
    if dates(week) is None:
        out.append(Problem("week", f"The week is {week['week']!r}.", "Give its seven days as YYYY-MM-DD/YYYY-MM-DD, "
                                                                     "Monday to Sunday or any seven days in a row."))
    slug = channel_of(week, cfg)
    if slug is None:
        out.append(Problem("channel", f"The week is for {week['channel']!r}, which is not one of this run's channels "
                                      f"({', '.join(cfg.get('channels') or []) or 'none'}).",
                           "Name the run's channel."))
    bad = [p for p in week["platforms"] if p not in brand.PLATFORMS]
    if bad or not week["platforms"]:
        out.append(Problem("platforms", f"The week posts to {week['platforms']!r}.",
                           f"Name one or more of {', '.join(brand.PLATFORMS)}."))
    weekly = cfg.get("weekly") if isinstance(cfg.get("weekly"), dict) else {}
    per_week = weekly.get("per_week")
    days = [d for d in weekly.get("days") or [] if d in WEEKDAYS]
    flexible_day = weekly.get("flexible_day")
    if len(week["slots"]) != per_week:
        out.append(Problem("slots", f"The week has {len(week['slots'])} slots, and config.yaml weekly.per_week is "
                                    f"{per_week}.", f"Plan {per_week} videos, one idea per slot."))
    taken: dict[str, int] = {}
    for i, s in enumerate(week["slots"]):
        day = DAY.get(str(s.get("day")))
        if day is None or day not in days:
            out.append(Problem(f"slots[{i}].day", f"{_name(s)} is on {s.get('day')!r}, which is not a posting day "
                                                  f"(config.yaml weekly.days: {', '.join(days)}).",
                               "Put it on one of the posting days (mon to sun, or the Polish pon to niedz)."))
        elif day in taken:
            out.append(Problem(f"slots[{i}].day", f"{_name(s)} is on {day}, like slot {taken[day] + 1}.",
                               "Give each posting day one idea."))
        else:
            taken[day] = i
        if day is not None and (day == flexible_day) != (s["plugin"]["flexible"] is True):
            out.append(Problem(f"slots[{i}].plugin.flexible",
                               f"{_name(s)} is on {day}, and the flexible day is {flexible_day}: "
                               + ("its idea is picked the day before from fresh trends." if day == flexible_day
                                  else "only that day's slot is flexible."),
                               f"Set plugin.flexible to {'true' if day == flexible_day else 'false'}."))
    for j, r in enumerate(week["reserves"]):
        if r["plugin"]["flexible"]:
            out.append(Problem(f"reserves[{j}].plugin.flexible", f"{_name(r)} is a reserve, and only the flexible day's "
                                                                 "slot is flexible.", "Set plugin.flexible to false."))
    if not week["reserves"]:
        out.append(Problem("reserves", "The week has no reserve idea.", "Add at least one reserve to swap in."))
    budget = config.get(cfg, "budget.per_week_usd")
    if not (math.isfinite(week["budget"]) and week["budget"] > 0):    # PR E review m1: NaN would pass any total
        out.append(Problem("budget", f"The week's budget is {week['budget']}.",
                           "Write the week's budget as budget.per_week_usd, an amount above zero in USD."))
    elif budget is None or abs(week["budget"] - budget) > TOL:
        out.append(Problem("budget", f"The week's budget is {_usd(week['budget'])}, and config.yaml "
                                     f"budget.per_week_usd is {budget if budget is None else _usd(budget)}.",
                           "Write the week's budget as budget.per_week_usd."))
    seen: dict[str, str] = {}
    for idea in ideas(week):
        key = str(idea["id"]).casefold()
        if key in seen:
            out.append(Problem("slots", f"The id {idea['id']!r} is {seen[key]}'s id too, in any case (one folder on "
                                        "Windows and macOS).", "Give each idea its own id."))
        seen.setdefault(key, str(idea["id"]))
    workspace = trend_spool.workspace_of(run)
    used: dict = {}
    if slug is not None:
        try:
            used = organic_research.used(workspace, slug)
        except ValueError as exc:
            out.append(Problem("channel", f"The channel {slug}'s library cannot be read: "
                                          f"{organic_proposals._plain(exc)}.", "Fix the file it names, then check again."))
    own = (state.load(run).organic or {}).get("started") or {}
    own = {k: v.get("run") for k, v in own.items() if isinstance(v, dict)}
    for kind in ("slots", "reserves"):
        for i, idea in enumerate(week[kind]):
            _idea_problems(run, week, idea, f"{kind}[{i}]", used, own, out)
    return out


def checked_gap(run: RunFolder) -> str | None:
    """The `week_checked` step check: I2 is done once the latest 03_wip/week_vNN.json passed `tm organic week check`
    and is unchanged since. Reads only."""
    return stepchecks.fresh(run, KEY, WIP, STEM, "json")


def read_week(path: Path, rel: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"{rel} cannot be read ({exc}); check the week again (tm organic week check); {AGAIN}.") from None
    if not isinstance(data, dict):
        raise Stop(f"{rel} is not one JSON object; check the week again (tm organic week check); {AGAIN}.")
    return data


def checked_week(run: RunFolder) -> tuple[Path, str, dict]:
    """The checked week plan: its path, run-relative path and data. A Stop while it is not checked."""
    gap = checked_gap(run)
    if gap is not None:
        raise Stop(f"The week page and its slots come from a checked week plan, and I2 is done once {gap} (tm organic "
                   f"week check --run <run> --file {FILE_PATTERN}). Check it, then go on; {AGAIN}.")
    rel = state.load(run).checked[KEY]["file"]
    return run.path / rel, rel, read_week(run.path / rel, rel)


# --- the decisions on the page, the total and the approval ---------------------------------------------

def _page_key(day: str) -> str:
    from tm.organic_pages import week as week_page   # it imports this module

    return week_page.DAY_EN[day]


def newest_docs(week: dict, docs: list[tuple[str, dict]]) -> dict[str, dict]:
    """The page's newest document per slot (keyed by its English day, the page's `pon` … `niedz` too) and its `_week`
    document, the newest `updated_at` winning."""
    days = {DAY[str(s["day"])] for s in week["slots"] if str(s.get("day")) in DAY}
    newest: dict[str, dict] = {}
    for doc_id, doc in docs:
        key = "_week" if doc_id == "_week" else DAY.get(doc_id)
        if key is None or (key != "_week" and key not in days) or not isinstance(doc, dict):
            continue
        before = newest.get(key)
        if before is None or str(doc.get("updated_at") or "") >= str(before.get("updated_at") or ""):
            newest[key] = doc
    return newest


def order(week: dict) -> list[str]:
    """The week's slot days (English), in date order (`day_date`; weekday order when the dates cannot be read). A
    ValueError for a slot whose day is not a day of the week (M3)."""
    days = []
    for s in week["slots"]:
        day = DAY.get(str(s.get("day")))
        if day is None:
            raise ValueError(f"the slot {s.get('id')!r} is on {s.get('day')!r}, which is not a day of the week.")
        days.append(day)
    return sorted(dict.fromkeys(days), key=lambda d: (day_date(week, d) or date.max, WEEKDAYS.index(d)))


def choices(week: dict, docs: list[tuple[str, dict]]) -> dict[str, dict]:
    """Each slot's choice from the page's documents (`page.db_docs`: (id, document)), in date order: `{day: {slot,
    idea, output, decision, note, carried}}`, the page's own defaults where a document is silent (the slot's idea,
    its output else video, ok). A ValueError when a slot names an idea the week does not hold, or two slots one."""
    by_id = {str(i["id"]): i for i in ideas(week)}
    slot_of = {DAY[str(s["day"])]: s for s in week["slots"] if str(s.get("day")) in DAY}
    newest = newest_docs(week, docs)
    out: dict[str, dict] = {}
    for day in order(week):
        s = slot_of[day]
        doc = newest.get(day, {})
        idea = doc.get("idea") if _text(doc.get("idea")) else s["id"]
        if idea not in by_id:
            raise ValueError(f"the {day} slot names the idea {idea!r}, which is not in the week.")
        out[day] = {"slot": _page_key(day), "idea": idea,
                    "output": doc.get("output") if doc.get("output") in OUTPUTS else
                    (s.get("output") if s.get("output") in OUTPUTS else "video"),
                    "decision": doc.get("decision") if doc.get("decision") in DECISIONS else "ok",
                    "note": doc.get("note") if isinstance(doc.get("note"), str) else "", "carried": False}
    twice = [i for i in by_id if [r["idea"] for r in out.values()].count(i) > 1]
    if twice:
        raise ValueError(f"{', '.join(twice)} is chosen on two days; each idea is made once.")
    return out


def cost_of(idea: dict, row: dict) -> float:
    """What a slot's choice costs: nothing when skipped, the script's or the video's cost."""
    if row["decision"] == "skip":
        return 0.0
    return float(idea["cost_script"] if row["output"] == "script" else idea["cost_video"])


def chosen_cost(week: dict, rows: dict, extra: tuple[dict, ...] = ()) -> float:
    """What the slots' choices (`rows`, as `choices` makes them) cost together, rounded to the cent; `extra` ideas
    (the flexible day's fresh one) are known beside the week's. The one sum the page's meter, the approval, the start
    and the flexible day use."""
    by_id = {str(i["id"]): i for i in [*ideas(week), *extra]}
    return round(sum(cost_of(by_id[r["idea"]], r) for r in rows.values() if r.get("idea") in by_id), 2)


def total(week: dict, docs: list[tuple[str, dict]]) -> float:
    """The chosen outputs' costs, swaps applied (the page's meter), rounded to the cent."""
    return chosen_cost(week, choices(week, docs))


def fingerprint(week_rel: str, rows: dict) -> str:
    """What a yes to the week covers: the week plan and each day's idea, output and decision (notes aside)."""
    what = {"week": str(week_rel).casefold(),
            "rows": {d: [str(r.get("idea")), r.get("output"), r.get("decision")] for d, r in sorted(rows.items())}}
    return hashlib.sha256(json.dumps(what, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _decisions(run: RunFolder) -> tuple[str, dict] | None:
    """The latest week decisions file (its run-relative path, its body), or None. A Stop when it is not one."""
    path = run.latest(WIP, DECISIONS_STEM, "json")
    if path is None:
        return None
    rel = path.relative_to(run.path).as_posix()
    try:
        body = json.loads(path.read_text(encoding="utf-8-sig"))
        ok = isinstance(body["decisions"], dict) and all(isinstance(r, dict) for r in body["decisions"].values())
    except (OSError, ValueError, TypeError, KeyError):
        ok = False
    if not ok:
        raise Stop(f"{rel} is not a decisions file of the week page. Read the decisions again (tm organic decisions "
                   f"--page week); {AGAIN}.")
    return rel, body


def _current(run: RunFolder) -> tuple[str, dict, str, dict]:
    """(decisions file, its body, the checked week file, the week) once the decisions were read from the page built
    from the checked week; a Stop otherwise."""
    _, week_rel, week = checked_week(run)
    got = _decisions(run)
    if got is None:
        raise Stop("No decisions have been read from the week page yet: read them (tm organic decisions --page week), "
                   f"then go on; {AGAIN}.")
    rel, body = got
    if str(body.get("week") or "").casefold() != week_rel.casefold():
        raise Stop(f"The decisions in {rel} were taken on the page built from {body.get('week')}, and the checked week "
                   f"is now {week_rel}. Build the page again and publish it, let the user decide, and read the decisions "
                   f"again; {AGAIN}.")
    return rel, body, week_rel, week


def approval(run: RunFolder) -> dict | None:
    """The week's yes: the latest `week` decision when it is `approve`, else None."""
    latest = None
    for d in state.load(run).decisions:
        if d.get("checkin") == "week":
            latest = d
    return latest if latest and latest.get("choice") == "approve" else None


def covered(run: RunFolder) -> dict:
    """What a yes given now covers (`flow.decide` keeps it in the decision, `covers`): the latest decisions file, the
    fingerprint of its choices and their cost. Called once `week_in_budget` passed."""
    rel, body, week_rel, week = _current(run)
    gone = dropped_spend(run)
    return {"decisions": rel, "fingerprint": fingerprint(week_rel, body["decisions"]),
            "total": round(chosen_cost(week, body["decisions"]) + gone, 2), "dropped_spend": gone,
            "budget": week["budget"]}


def _approval_gap(run: RunFolder, rel: str, body: dict, week_rel: str, week: dict | None = None) -> str | None:
    """Why the week's yes does not cover the latest decisions and the week's budget (I2: money is never approved
    quietly; PR E review I2: a budget set after the yes needs a new one), or None."""
    name = checkins.load(playbook=ORGANIC_VIDEO).checkins["week"].name
    yes = approval(run)
    if yes is None:
        return f"the user approves the week (\"{name}\"): record their yes with tm decide week approve"
    covers = yes.get("covers") if isinstance(yes.get("covers"), dict) else {}
    budget = (week if week is not None else checked_week(run)[2]).get("budget")
    if covers.get("budget") != budget:
        was = covers.get("budget")
        return (f"the user approves the week at its budget of {_usd(budget)}: the budget was set after their yes"
                f"{f' (given at {_usd(was)})' if isinstance(was, (int, float)) else ''}. Show them the week again and "
                "record their yes with tm decide week approve --change")
    if covers.get("fingerprint") != fingerprint(week_rel, body["decisions"]):
        return (f"the user approves the week as it stands now: the decisions in {rel} changed a day's idea, output or "
                f"OK since their yes ({covers.get('decisions') or 'an earlier reading'}). Show them the week again and "
                f"record their yes with tm decide week approve --change")
    return None


def _conflicts(run: RunFolder, week: dict, rows: dict) -> list[str]:
    """Each started day the decisions now change (I1: one run per day): another idea or output, or a skip."""
    flex = next((DAY[str(s["day"])] for s in week["slots"] if s["plugin"]["flexible"]), None)
    out = []
    for day, (prod, _) in started_days(run).items():
        s = state.load(prod)
        idea = str((s.organic or {}).get("proposal") or "")
        output = "video" if "organic_video" in s.outputs else "script"
        row = rows.get(day)
        if row is None or row.get("decision") != "ok":
            said = "skip it"
        elif row.get("output") != output or (day != flex and str(row.get("idea")).casefold() != idea.casefold()):
            said = f"choose {row.get('idea')} as {OUTPUT_WORDS[row.get('output')] if row.get('output') in OUTPUT_WORDS else row.get('output')}"
        else:
            continue
        out.append(f"{day}'s run {prod.path.name} makes {idea} as {OUTPUT_WORDS[output]}, and the decisions now {said}")
    return out


def _drop_todo(run: RunFolder) -> str:
    return (f"drop that day's run first (tm organic drop-slot --run {week_ref(run)} --day <day> --note \"<the user's "
            "words>\"), or choose the started idea and output again on the page")


def budget_gap(run: RunFolder) -> str | None:
    """The `week_in_budget` check (`tm decide week approve` requires it): the week's decisions are read from the page
    built from the checked week, change no day whose run is started (one run per day), and cost no more than the
    week's budget. Reads only."""
    try:
        rel, body, _, week = _current(run)
        conflicts = _conflicts(run, week, body["decisions"])
        gone = dropped_spend(run)
    except Stop as exc:                       # m3: a step check gives its gap, never raises
        return f"the week's decisions and its started days can be read ({exc})"
    if conflicts:
        return f"no started day is changed ({'; '.join(conflicts)}): {_drop_todo(run)}"
    spent = round(chosen_cost(week, body["decisions"]) + gone, 2)
    if spent > week["budget"] + TOL:
        with_dropped = f", with {_usd(gone)} already spent on dropped days" if gone else ""
        return (f"the week's choices cost no more than its budget ({_usd(spent)} of {_usd(week['budget'])} in {rel}"
                f"{with_dropped}). {OVER_BUDGET}")
    return None


def _dropped(run: RunFolder) -> list[dict]:
    """The week run's dropped day runs (`organic.dropped`, written by `drop_slot`)."""
    return [e for e in (state.load(run).organic or {}).get("dropped") or [] if isinstance(e, dict) and _text(e.get("path"))]


def _dropped_spent(workspace: Path, entry: dict) -> float:
    """What one dropped day run spent: the larger of what the week run recorded at the drop (r1: it holds even once
    the folder is deleted) and the run's own spend while its folder is there. A run whose folder is there but cannot
    be read, or one with no record and no folder, is a Stop."""
    recorded = entry.get("spent")
    recorded = float(recorded) if isinstance(recorded, (int, float)) and not isinstance(recorded, bool) else None
    folder = workspace / entry["path"]
    if recorded is not None and not (folder / "run.json").exists():
        return recorded
    try:
        own = float((state.load(RunFolder(folder)).spend or {}).get("ai_usd") or 0)
    except (OSError, ValueError) as exc:
        raise Stop(f"The dropped run {entry['path']} cannot be read ({exc}), so what it spent is unknown. Restore "
                   f"it, then go on with the week; {AGAIN}.") from None
    return max(own, recorded or 0.0)


def dropped_spend(run: RunFolder) -> float:
    """What the week's dropped day runs spent (m1): it stays spent, so the week's yes and its budget count it. A
    dropped run that cannot be read is a Stop."""
    workspace = trend_spool.workspace_of(run)
    return round(sum(_dropped_spent(workspace, entry) for entry in _dropped(run)), 2)


# --- I3: the slot runs ------------------------------------------------------------------------------------

def _today() -> date:
    """Today (tests set it)."""
    return date.today()


def as_proposal(week: dict, idea: dict, row: dict) -> dict:
    """A slot's idea in the shape a production run is started from (`organic_proposals._plan`, `_make`): the week's
    channel, the idea's title, format, approach, trends and product level, its output."""
    plugin = idea["plugin"]
    return {"id": idea["id"], "channel": week["channel"], "title": idea["title"], "video_type": idea["format"],
            "approach": plugin["approach"], "why": idea["why"], "trends": copy.deepcopy(plugin["trends"]),
            "product": {"level": plugin["product_level"]}, "risk": {"level": idea["risk"]},
            "plugin": {"production": plugin["production"], "output": row["output"], "series": plugin["series"],
                       "risk_hits": [], "transfer": False, "weak_link": None, "seed": None}}


def week_ref(run: RunFolder) -> str:
    return run.path.resolve().relative_to(trend_spool.workspace_of(run)).as_posix()


def _rows_to_start(week: dict, rows: dict, *, flexible: bool) -> list[tuple[str, dict, dict]]:
    """(day, idea, row) of every OK slot, in date order: the flexible day's only when `flexible`, else every other."""
    by_id = {str(i["id"]): i for i in ideas(week)}
    slot_of = {DAY[str(s["day"])]: s for s in week["slots"]}
    out = []
    for day in order(week):
        row = rows.get(day)
        if row is None or row.get("decision") != "ok":
            continue
        if bool(slot_of[day]["plugin"]["flexible"]) == flexible:
            out.append((day, by_id[row["idea"]], row))
    return out


def _held(run: RunFolder, week: dict, plan: list[tuple[str, dict, dict]], keep_carried: bool, rel: str) -> None:
    """The refusals before anything starts: an AI video of a type the stack hides, a carried OK the user has not kept."""
    hidden = organic.hidden_types(organic.stack_of(run))
    blocked = [(day, idea) for day, idea, row in plan
               if row["output"] == "video" and idea["plugin"]["production"] in hidden]
    if blocked:
        stack = organic.stack_of(run) or {}
        why = []
        for day, idea in blocked:
            production = idea["plugin"]["production"]
            key, needs = organic_proposals.NEEDS[production]
            why.append(f"{_name(idea)} on {day} is {organic_proposals.PRODUCTION_WORDS[production]}, which needs {needs} "
                       f"(the stack check found {key} {stack.get(key, 'missing')})")
        raise Stop(f"Chosen as an AI video, which this run cannot make: {'; '.join(why)}. Ask the user: it can be a "
                   "script to film (switch the output on the page, then read the decisions again), or set the tool up "
                   f"and record the stack again (tm organic stack). Nothing was started; {AGAIN}.")
    carried = [(day, idea) for day, idea, row in plan if row.get("carried")]
    if carried and not keep_carried:
        names = ", ".join(f"{_name(idea)} on {day}" for day, idea in carried)
        raise Stop(f"{names}: chosen on an earlier page and carried over to this one ({rel}); the page shows the earlier "
                   "choice until the user saves again. Ask the user once whether those stand; on a yes, start again "
                   "with --keep-carried; on a no, let them change it on the page and read the decisions again. Nothing "
                   f"was started; {AGAIN}.")


def _make_all(run: RunFolder, week: dict, week_rel: str, plan: list[tuple[str, dict, dict]], today: date) -> list[dict]:
    """One production run per (day, idea, row), as `tm organic start` makes a picked idea's, with the week named."""
    workspace = trend_spool.workspace_of(run)
    cfg = config.load(run)
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    level = state.load(run).level
    platforms = [p for p in week["platforms"] if p in brand.PLATFORMS]
    data = {"channels": []}
    ref = week_ref(run)
    started = dict((state.load(run).organic or {}).get("started") or {})
    plans = []
    for day, idea, row in plan:
        p = as_proposal(week, idea, row)
        r = {"decision": "produce", "level": level, "output": row["output"], "platforms": platforms,
             "note": row.get("note") or "", "carried": bool(row.get("carried")), "day": day,
             "date": (day_date(week, day) or today).isoformat()}
        plans.append((day, organic_proposals._plan(workspace, run, data, p, r, channels, ref, today)))
    made = []
    for day, one in plans:
        got = organic_proposals._make(workspace, run, cfg, one, ref, week_rel, today, started,
                                      organic_extra={"week": ref, "slot": day})
        made.append({**got, "day": day})
    return made


def _record(run: RunFolder, week: dict, rows: dict, today: date, extra: tuple[dict, ...] = ()) -> int:
    """The week's decisions in the channel's decisions.jsonl (`organic_proposals._record_decisions`): an OK slot as
    produce once it is started, a skip as skip; `extra` ideas (the flexible day's fresh one) are known too."""
    workspace = trend_spool.workspace_of(run)
    cfg = config.load(run)
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    by_id = {str(i["id"]): i for i in [*ideas(week), *extra]}
    data = {"channels": [], "proposals": []}
    decided = {}
    for row in rows.values():
        idea = by_id.get(row.get("idea"))
        if idea is None:
            continue
        p = as_proposal(week, idea, row)
        data["proposals"].append(p)
        decided[p["id"]] = {"decision": "produce" if row["decision"] == "ok" else "skip", "output": row["output"],
                            "level": state.load(run).level}
    started = (state.load(run).organic or {}).get("started") or {}
    return organic_proposals._record_decisions(run, workspace, data, decided, {}, started, channels, today)


def _ready(run: RunFolder) -> tuple[str, dict, str, dict]:
    """(decisions file, its body, the checked week file, the week) once the week may start: the yes covers the
    latest decisions (I2), no started day is changed (I1), and the choices fit the budget. A Stop otherwise."""
    rel, body, week_rel, week = _current(run)
    conflicts = _conflicts(run, week, body["decisions"])
    gap = ((f"no started day is changed ({'; '.join(conflicts)}): {_drop_todo(run)}" if conflicts else None)
           or _approval_gap(run, rel, body, week_rel, week) or budget_gap(run))
    if gap is not None:
        raise Stop(f"The week's videos start once {gap}; {AGAIN}.")
    return rel, body, week_rel, week


def start(run: RunFolder, *, keep_carried: bool = False, today: date | None = None) -> dict:
    """Start one production run per OK day but the flexible one (the module docstring), once the week's yes covers
    its latest decisions within the budget. All or nothing for the refusals; a day whose run is started is never
    started again (one run per day, whatever its idea)."""
    today = today or _today()
    s = state.load(run)
    if s.playbook != ORGANIC_VIDEO or WEEK_OUTPUT not in s.outputs:
        raise ValueError(f"{run.path.name} is not an organic video week run.")
    rel, body, week_rel, week = _ready(run)
    rows = body["decisions"]
    started = started_days(run)
    plan = _rows_to_start(week, rows, flexible=False)
    new = [(d, i, r) for d, i, r in plan if d not in started]
    again = [(d, i) for d, i, _ in plan if d in started]
    _held(run, week, new, keep_carried, rel)
    made = _make_all(run, week, week_rel, new, today) if new else []
    flex = next((x for x in week["slots"] if x["plugin"]["flexible"]), None)
    if flex is not None:
        day = DAY[str(flex["day"])]
        st = state.load(run)
        own = dict(st.organic or {})
        if not isinstance(own.get("flexible"), dict) or not own["flexible"].get("run"):
            when = day_date(week, day)
            own["flexible"] = {"day": day, "date": when.isoformat() if when else None,
                               "week": dates(week)[0].isoformat() if dates(week) else None,
                               "decision": (rows.get(day) or {}).get("decision")}
            st.organic = own
            state.save(run, st)
    recorded = _record(run, week, rows, today)
    return {"started": made, "already_started": [{"day": d, "proposal": i["id"], "title": i["title"]} for d, i in again],
            "decisions": rel, "week": week_rel, "flexible": (state.load(run).organic or {}).get("flexible"),
            "decisions_recorded": recorded}


def started_gap(run: RunFolder) -> str | None:
    """The `slots_started` step check: I3 is done once the latest week decisions were taken on the page built from the
    checked week, change no started day, and every OK day but the flexible one has its run (one per day). Reads
    only."""
    try:
        _, body, _, week = _current(run)
        conflicts = _conflicts(run, week, body["decisions"])
        started = started_days(run)
    except Stop:
        return ("the week's decisions are read from its page (tm organic decisions --page week) and its slots are "
                "started (tm organic start)")
    if conflicts:
        return f"the started days are as decided ({'; '.join(conflicts)}): {_drop_todo(run)}"
    missing = [f"{_name(i)} on {d}" for d, i, _ in _rows_to_start(week, body["decisions"], flexible=False)
               if d not in started]
    return None if not missing else f"every OK slot but the flexible one is started (tm organic start): {', '.join(missing)}"


def drop_slot(run: RunFolder, day: str, note: str) -> dict:
    """Drop the run started for `day` (`tm organic drop-slot`), on the user's word (`note`): the slot run ends
    (run.json `status` done, `organic.dropped`), its approved budgets are capped at what it spent and every paid tool
    call in it is refused (`tools._precheck`), and the week forgets it, so the day may be decided and started again
    (its spend still counts against the week). A ValueError when no run is started for that day."""
    if not (isinstance(note, str) and note.strip()):
        raise ValueError("--note holds the user's own words for dropping the day's run.")
    found = DAY.get(str(day).strip().lower())
    started = started_days(run)
    if found is None or found not in started:
        names = ", ".join(started) or "none"
        raise ValueError(f"No run is started for {day!r} in this week (started: {names}).")
    prod, entry = started[found]
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ps = state.load(prod)
    ps.organic = {**(ps.organic or {}), "dropped": {"at": at, "note": note.strip(), "week": week_ref(run)}}
    ps.status = "done"
    ps.ended = f"Dropped from the week on the user's word: {note.strip()}"
    for kind in list(ps.budgets):              # N1: nothing more is approved than what it spent
        ps.budgets[kind] = float((ps.spend or {}).get(kind) or 0.0)
        ps.approvals.append({"kind": kind, "amount": ps.budgets[kind], "at": at,
                             "note": "dropped from the week: capped at what was spent"})
    state.save(prod, ps)                       # first: a dropped run is never a started day again (`slot_runs`)
    s = state.load(run)
    own = dict(s.organic or {})
    own["started"] = {k: v for k, v in (own.get("started") or {}).items()
                      if not (isinstance(v, dict) and v.get("path") == entry["path"])}
    spent = float((ps.spend or {}).get("ai_usd") or 0)
    own["dropped"] = [*(own.get("dropped") or []), {"day": found, "run": prod.path.name, "path": entry["path"],
                                                    "idea": (ps.organic or {}).get("proposal"), "note": note.strip(),
                                                    "at": at, "spent": spent}]   # r1: kept with the week
    flex = own.get("flexible")
    if isinstance(flex, dict) and flex.get("run") == prod.path.name:
        own["flexible"] = {k: v for k, v in flex.items() if k not in ("run", "idea", "file")}
    s.organic = own
    state.save(run, s)
    return {"day": found, "run": prod.path.name, "path": entry["path"], "spent": spent}


def _saved_at(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        at = json.loads(path.read_text(encoding="utf-8")).get("_at")
    except (OSError, ValueError, AttributeError):
        return None
    return at if isinstance(at, str) else None


def _when(text: str | None) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def flexible(run: RunFolder, file: Path, *, today: date | None = None) -> dict:
    """Start the flexible slot from `file` (03_wip/flexible_vNN.json: one idea in the slot's shape, plugin block and
    all, built on fresh trends): the week's yes covering its latest decisions, its flexible slot OK and not started, a
    search saved after the approval and each of the idea's trend cards saved after it too, the idea passing the
    slot's checks, and the week still within its budget with this idea in the flexible day's output. The idea is
    logged in the channel's decisions.jsonl like the week's others."""
    today = today or _today()
    rel, body, week_rel, week = _ready(run)
    approved = _when((approval(run) or {}).get("at"))
    s = state.load(run)
    own = s.organic or {}
    flex = next((x for x in week["slots"] if x["plugin"]["flexible"]), None)
    if flex is None:
        raise ValueError(f"{week_rel} has no flexible day.")
    day = DAY[str(flex["day"])]
    row = body["decisions"].get(day) or {}
    if row.get("decision") != "ok":
        raise Stop(f"The flexible day ({day}) is skipped in {rel}: there is nothing to make. If the user wants it after "
                   f"all, let them choose it on the page and read the decisions again; {AGAIN}.")
    if day in started_days(run) or (isinstance(own.get("flexible"), dict) and own["flexible"].get("run")):
        raise Stop(f"The flexible day is already started as {(own.get('flexible') or {}).get('run')}; a day is never "
                   f"started twice. Continue in its production run; {AGAIN}.")
    path, file_rel = Path(file), Path(file).resolve().relative_to(run.path.resolve()).as_posix()
    if not FLEXIBLE_NAME.fullmatch(file_rel):
        raise ValueError(f"The flexible day's idea is written as {FLEXIBLE_PATTERN}; {file_rel} is not.")
    try:
        idea = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{file_rel} is not valid JSON ({exc}). Write it again as one JSON object; {AGAIN}.") from None
    item = copy.deepcopy(_schema()["properties"]["slots"]["items"])
    out = [Problem(line.split(" ", 1)[0].removeprefix("idea."), line, _SHAPE_TODO)
           for line in json_schema.problems(idea, item, name="idea")]
    if not out:
        if not idea["plugin"]["flexible"]:
            out.append(Problem("plugin.flexible", f"{_name(idea)} is the flexible day's idea.", "Set it to true."))
        others = {str(i["id"]).casefold() for i in ideas(week)} - {str(flex["id"]).casefold()}
        if str(idea["id"]).casefold() in others:
            out.append(Problem("id", f"{idea['id']!r} is another idea's id in the week.", "Give it its own id."))
        slug = channel_of(week, config.load(run))
        used: dict = {}
        try:
            used = organic_research.used(trend_spool.workspace_of(run), slug) if slug else {}
        except ValueError as exc:            # a damaged library line (M4): a problem, as at the week check
            out.append(Problem("channel", f"The channel {slug}'s library cannot be read: "
                                          f"{organic_proposals._plain(exc)}.", "Fix the file it names, then start again."))
        _idea_problems(run, week, idea, "idea", used, {}, out)
    if out:
        raise Stop(f"{file_rel} needs fixing:\n" + "\n".join(f"- {p.field}: {p.what} {p.todo}" for p in out)
                   + f"\nFix the file (a new version), then start the flexible day again; {AGAIN}.")
    searched = [_when(_saved_at(p)) for p in (run.path / "02_research" / "search").glob("*.json")]
    if not any(w is not None and w > approved for w in searched):   # after it: one in the approval's second is not
        raise Stop("The flexible day's idea comes from fresh trends: no search was saved since the week was approved. "
                   f"Search again (collection on), save the cards of the trends it builds on, then start it; {AGAIN}.")
    stale = []
    for t in idea["plugin"]["trends"]:
        tid, _ = organic_research.resolve(run, t["id"])
        when = _when(_saved_at(brief_research.card_file(run, tid)))
        if when is None or when <= approved:
            stale.append(t["id"])
    if stale:
        raise Stop(f"The flexible day's idea comes from fresh trends, and the cards of {', '.join(stale)} were saved "
                   f"before the week was approved. Fetch them again with get_trend (collection on), then start it; "
                   f"{AGAIN}.")
    rows = {**body["decisions"], day: {**row, "idea": idea["id"]}}
    spent = round(chosen_cost(week, rows, (idea,)) + dropped_spend(run), 2)
    if spent > week["budget"] + TOL:
        raise Stop(f"With {_name(idea)} on the flexible day the week costs {_usd(spent)} of {_usd(week['budget'])}. "
                   f"{OVER_BUDGET} Write a cheaper idea, or ask the user to make it a script; {AGAIN}.")
    _held(run, week, [(day, idea, row)], True, rel)
    made = _make_all(run, week, week_rel, [(day, idea, row)], today)[0]
    st = state.load(run)
    st.organic = {**(st.organic or {}), "flexible": {**((st.organic or {}).get("flexible") or {}), "day": day,
                                                     "idea": idea["id"], "file": file_rel, "run": made["run"]}}
    state.save(run, st)
    _record(run, week, {day: rows[day]}, today, (idea,))
    return {"started": made, "file": file_rel, "day": day}


# --- the week cap of a slot's pack ------------------------------------------------------------------------

def _runs(workspace: Path) -> list[tuple[Path, dict]]:
    """Every organic video run's folder and run.json. A run.json that cannot be read is a Stop (M2): on the money
    path a run is never left out unseen."""
    folder = Path(workspace) / "runs" / playbooks.get(ORGANIC_VIDEO).id
    out = []
    for run_json in sorted(folder.glob("*/run.json")) if folder.is_dir() else ():
        try:
            data = json.loads(run_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            data = exc
        if not isinstance(data, dict):
            rel = run_json.relative_to(workspace).as_posix()
            raise Stop(f"{rel} cannot be read ({data if isinstance(data, Exception) else 'not one JSON object'}), so "
                       f"what the week's videos planned or spent is unknown. Restore it, then check the pack again; "
                       f"{AGAIN}.")
        out.append((run_json.parent, data))
    return out


def week_left(run: RunFolder) -> tuple[float, float, float] | None:
    """For a slot's production run: (the week's budget, what its other slot runs may spend, what is left) in USD. The
    budget is the week run's own `budget.per_week_usd` (M1: a raised week budget reaches every day), and no more than
    the budget the week's current yes covers (re-review N2: a raise counts once the user says yes to it, a cut at
    once). Each other run
    counts the largest of its planned, approved and spent `ai_usd` (PR E review I1: a pack re-checked cheaper keeps
    its higher yes, and the run may spend up to it); a dropped one what it spent (its approval is capped at that), as
    the week run recorded it, so a deleted dropped folder still counts (r1). None for a run of no week."""
    ref = (state.load(run).organic or {}).get("week")
    if not _text(ref):
        return None
    workspace = trend_spool.workspace_of(run)
    week_run = RunFolder(workspace / ref)
    try:
        budget = config.get(config.load(week_run), "budget.per_week_usd")
        dropped = _dropped(week_run)
        yes = approval(week_run)
    except (OSError, ValueError) as exc:
        raise Stop(f"The week run {ref} this video belongs to cannot be read ({exc}), so what the week has left is "
                   f"unknown. Restore it, then check the pack again; {AGAIN}.") from None
    if budget is None:
        return None
    said = ((yes or {}).get("covers") or {}).get("budget") if isinstance((yes or {}).get("covers"), dict) else None
    if isinstance(said, (int, float)) and not isinstance(said, bool) and math.isfinite(said):
        budget = min(float(budget), float(said))    # N2: a raised budget reaches the slots with the user's new yes
    others = _committed(workspace, ref, dropped, run.path.resolve())
    return float(budget), others, round(float(budget) - others, 2)


def _committed(workspace: Path, ref: str, dropped: list[dict], me: Path | None) -> float:
    """What the week `ref`'s slot runs (all but `me`) may spend, in USD: each run the largest of its planned, approved
    and spent `ai_usd`, a dropped one what it spent (`_dropped_spent`)."""
    recorded = {(workspace / e["path"]).resolve() for e in dropped}
    total_ = sum(_dropped_spent(workspace, e) for e in dropped if (workspace / e["path"]).resolve() != me)
    for path, data in _runs(workspace):
        mine = data.get("organic") if isinstance(data.get("organic"), dict) else {}
        if mine.get("week") != ref or path.resolve() == me or (mine.get("dropped") and path.resolve() in recorded):
            continue
        kinds = [] if mine.get("dropped") else ["planned", "budgets"]
        total_ += max(float((data.get(k) or {}).get("ai_usd") or 0) for k in [*kinds, "spend"])
    return round(total_, 2)


def set_budget(run: RunFolder, usd: float, note: str) -> dict:
    """Set the week's budget on the user's word (`tm organic week budget`, PR E review I2): logged in the week run's
    `approvals` with their words, written to its config's `budget.per_week_usd` (every slot's pack reads it,
    `week_left`) and to the checked week file's `budget` (marked checked again), and the week's yes no longer
    covers the week (`_approval_gap`: its `covers.budget` differs), so nothing more starts before the user's yes at
    the new budget. A budget below what the week's videos may already spend (`_committed`) is refused."""
    s = state.load(run)
    if s.playbook != ORGANIC_VIDEO or WEEK_OUTPUT not in s.outputs:
        raise ValueError(f"{run.path.name} is not an organic video week run.")
    if not (isinstance(note, str) and note.strip()):
        raise ValueError("--note holds the user's own words for the week's budget.")
    try:
        value = float(usd)
    except (TypeError, ValueError):
        raise ValueError(f"{usd!r} is not an amount in USD.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"The week's budget is an amount above zero in USD, not {usd!r}.")
    value = round(value, 2)
    committed = _committed(trend_spool.workspace_of(run), week_ref(run), _dropped(run), None)
    if value < committed - TOL:
        raise ValueError(f"The week's videos have already planned, approved or spent {_usd(committed)}, so the week's "
                         f"budget cannot go below it. Ask the user for {_usd(committed)} or more.")
    cfg = config.load(run)
    cfg["budget"] = {**(cfg.get("budget") if isinstance(cfg.get("budget"), dict) else {}), "per_week_usd": value}
    config.save(run, cfg)
    week_file = None
    if checked_gap(run) is None:
        path, week_file, week = checked_week(run)
        week["budget"] = value
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(week, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        from tm.tools import _common          # the tools import the playbooks: imported where it is used

        _common.replace(tmp, path)            # Windows: again while another process holds the file
        stepchecks.mark(run, KEY, path)
    s = state.load(run)
    s.approvals.append({"kind": "per_week_usd", "amount": value, "at": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), "note": note.strip()})
    state.save(run, s)
    return {"budget": value, "committed": committed, "week": week_file, "approved": approval(run) is not None}


# --- the started slots -----------------------------------------------------------------------------------

def slot_runs(run: RunFolder) -> list[tuple[str, RunFolder, dict]]:
    """(day, production run, its start record) of every started slot not dropped, in date order (the checked week's,
    else weekday order). A slot run that cannot be read, or names no day of the week, is a Stop (M2, M3)."""
    workspace = trend_spool.workspace_of(run)
    out = []
    for entry in ((state.load(run).organic or {}).get("started") or {}).values():
        if not isinstance(entry, dict) or not _text(entry.get("path")):
            continue
        prod = RunFolder(workspace / entry["path"])
        try:
            mine = state.load(prod).organic or {}
        except (OSError, ValueError) as exc:
            raise Stop(f"The slot run {entry['path']} cannot be read ({exc}): restore it, then go on with the week; "
                       f"{AGAIN}.") from None
        day = mine.get("slot")
        if day not in WEEKDAYS:
            raise Stop(f"The slot run {entry['path']} names {day!r}, which is not a day of the week: restore its run.json "
                       f"(organic.slot), then go on with the week; {AGAIN}.")
        if not mine.get("dropped"):
            out.append((day, prod, entry))
    try:
        week = checked_week(run)[2]
        when = {d: day_date(week, d) for d in WEEKDAYS}
    except Stop:
        when = {}
    return sorted(out, key=lambda x: (when.get(x[0]) or date.max, WEEKDAYS.index(x[0])))


def started_days(run: RunFolder) -> dict[str, tuple[RunFolder, dict]]:
    """Each started day's run (one per day): {day: (production run, its start record)}."""
    return {day: (prod, entry) for day, prod, entry in slot_runs(run)}
