"""The Models page (issue #86, built from the model registry since #115): the user chooses the model of each task from
the registry's groups, with today's price, before anything is generated. Organic AI video shows it at E1, Create an ad
at S5 and Refresh an ad at D1 (`tm models page`, the same page for any task of the registry).

    page_json(run, units_file)        organic video's page data: images, video, upscale, voice (tm.organic_pages.choices)
    tasks_page_json(run, tasks, ...)  the page for any registry tasks (Create an ad, Refresh an ad)
    take(run, *, file, text, by_rule) 03_wip/models_vNN.json, which the next step starts from
    chosen(run)                       the latest choice of models in the run, or None
    recipe_of(run, path)              the recipe a model names, in the plugin or the workspace's library, when it is
                                      there and dated (its sources and the day they were checked)

**Rows** are the registry's (`tm.model_registry.active`): per task budget, suggested and best, active models only
(`new` and `removed` are never shown), the ★ model ticked in advance. Each row shows only its price per unit as the
provider bills it and the registry's one sentence, `good_for`: no rankings, no test scores, no links. At the end of
each task a field takes the user's own model (used without being blocked; its recipe is written first).

**Live in a run: only price and availability.** The engine prices each Replicate row from the run's latest price file
(`tm tool replicate_price --run R <the ids tm models ids gives>`, saved in `02_research/models/`), through the tier its
registry variant names (`model_registry.live_price`), × this video's units: the variant priced is the variant sent. A
model Replicate shows no price for today is greyed out ("not available today"); a price file older than
`pricing.max_age_days`, or one that leaves a row's model out, is refused. ElevenLabs and the free local tools are
priced from the registry (credits, or $0). When the registry is older than 30 days the page says so, and the agent
reads the rankings live too (`plugin.rankings_stale`).

**Greyed out, with the reason**: a model with no price today; a model whose registry limits hold `photoreal_face`
(Seedance) when a frame has a photoreal face (Replicate E005); a variant sending its own sound under a voiceover.

Organic video's units come from the checked recipe: its video sections' seconds (or the script's), one first frame and
one take per 15 s; a units file (`{"images", "video_seconds", "takes", "upscale_seconds"}`, `--file`) overrides them.
At Hands-off the ★ models are taken by rule (`take(..., by_rule=True)`), recorded as the rule's.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

from tm import config, model_registry, organic_pages, paths, stepchecks, state, trend_spool
from tm.organic_pages import choices
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "models"
STEM = "models"
WIP = "03_wip"
PRICES = "02_research/models"
# organic video's sections and the registry task each shows
ORGANIC = {"images": "photos", "video": "image_to_video", "upscale": "upscale", "voice": "voiceover"}
TASKS = tuple(ORGANIC)
GROUPS = model_registry.GROUPS
_M = "organic.models."
LIBRARY = "library/model-prompting/"               # the workspace's recipes, written for a model the plugin has none of
PLUGIN_RECIPES = paths.bundled_data().parent / "references" / "model-prompting"
PLUGIN_PREFIX = "references/model-prompting/"
_CHECKED = re.compile(r"\(checked (\d{4}-\d{2}-\d{2})\)")
_SOURCES = re.compile(r"^Sources?:", re.MULTILINE)
TAKE_MAX_S = 15
# The voice models (ElevenLabs, on the user's key and credits): the registry's voiceover rows.
VOICE_MODELS = {r["model"]: (r["name"], r["group"]) for r in model_registry.active("voiceover")}


def _day(text: object) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def recipe_of(run: RunFolder, rel: object) -> Path | None:
    """The recipe file `rel` names: the plugin's (`references/model-prompting/<file>`) or the workspace's library
    (`library/model-prompting/<file>`), when it is there and dated `(checked YYYY-MM-DD)` with its sources."""
    if not isinstance(rel, str):
        return None
    for prefix, base in ((PLUGIN_PREFIX, PLUGIN_RECIPES), (LIBRARY, trend_spool.workspace_of(run) / LIBRARY)):
        name = rel[len(prefix):] if rel.startswith(prefix) else None
        if not name or "/" in name or "\\" in name or not name.endswith(".md"):
            continue
        path = Path(base) / name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return path if _CHECKED.search(text.split("\n", 1)[0]) and _SOURCES.search(text) else None
    return None


def library_recipe(model: str) -> str:
    """Where a new recipe for `model` goes: `library/model-prompting/<owner>-<name>.md`."""
    return LIBRARY + re.sub(r"[^A-Za-z0-9._-]+", "-", model.replace("/", "-")) + ".md"


def _recipe_pack(run: RunFolder) -> tuple[str, dict]:
    gap = stepchecks.fresh(run, "recipe", WIP, "pack", "json")
    entry = state.load(run).checked.get("recipe") or {}
    if gap is not None or not entry.get("file"):
        raise Stop(f"The Models page prices this video's recipe, and {gap or 'no recipe is checked'}: check it first "
                   f"(tm organic pack check --stage recipe), then build the page; {AGAIN}.")
    try:
        return entry["file"], json.loads((run.path / entry["file"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise Stop(f"{entry['file']} cannot be read: write the recipe again and check it; {AGAIN}.") from None


def _face(pack: dict) -> bool:
    """Whether a frame the video starts from has a photoreal face: a host image, or an images item marked `face`."""
    host = (pack.get("host") or {}).get("kind")
    return host == "image" or any(item.get("face") for st in pack.get("stages") or []
                                  for item in st.get("items") or [])


def _narrated(pack: dict) -> bool:
    from tm import organic_voiced
    return organic_voiced.narrated(pack)


def _pack_units(pack: dict) -> dict:
    """This video's units from its recipe: the video sections' seconds (else the script's), a first frame and a take
    for each 15 s of each section, the upscale over the same seconds, and the voiceover's characters."""
    from tm import organic_pack

    spans = [max(0.0, float(s.get("to") or 0) - float(s.get("from") or 0)) for s in pack.get("sections") or []
             if s.get("type") in organic_pack.VIDEO_TYPES]
    seconds = sum(spans) or float((pack.get("script") or {}).get("seconds") or TAKE_MAX_S)
    takes = sum(max(1, math.ceil(s / TAKE_MAX_S)) for s in spans if s) or max(1, math.ceil(seconds / TAKE_MAX_S))
    said = "".join(ln.get("text") or "" for ln in (pack.get("script") or {}).get("lines") or []
                   if ln.get("speaker") not in (None, "none"))
    return {"images": takes, "video_seconds": seconds, "takes": takes, "upscale_seconds": seconds,
            "characters": len(said)}


def _units_file(run: RunFolder, rel: str | None) -> dict:
    if not rel:
        return {}
    path = (run.path / rel).resolve()
    if not path.is_file() or not path.is_relative_to(run.path.resolve()):
        raise Stop(f"{rel} is not a file of this run: write the units as JSON in the run; {AGAIN}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{rel} is not JSON ({exc}): write it again; {AGAIN}.") from None
    if not isinstance(data, dict) or any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0
                                         for v in data.values()):
        raise Stop(f"{rel} must be an object of numbers: images, video_seconds, takes, upscale_seconds, characters, "
                   f"sound_seconds, music_seconds, minutes; {AGAIN}.")
    return data


def _units(task: str, per: str, units: dict) -> float:
    """How many of the registry's unit (`per`) this run takes for `task`."""
    if per == "image":
        return float(units.get("images") or 0)
    if per == "character":
        return float(units.get("characters") or 0)
    if per == "minute":
        return float(units.get("minutes") or (float(units.get("video_seconds") or 0) / 60))
    if per == "run":
        return float(units.get("takes") or 1)
    key = {"upscale": "upscale_seconds", "sound_effects": "sound_seconds", "music": "music_seconds"}.get(task,
                                                                                                    "video_seconds")
    return float(units.get(key) or units.get("video_seconds") or 0)


def latest_prices(run: RunFolder) -> Path | None:
    base = run.path / PRICES
    found = sorted(base.glob("prices_*.json"), key=lambda p: p.name) if base.is_dir() else []
    return found[-1] if found else None


def price_ids(tasks) -> list[str]:
    """The Replicate models a page of these registry tasks prices live (what `tm tool replicate_price` is given)."""
    return list(dict.fromkeys(r["model"] for t in tasks for r in model_registry.active(t) if r["provider"] == "replicate"))


def _rows(run: RunFolder, sections: dict[str, str], units: dict, *, face: bool, narrated: bool, today: date, t,
          price_path: Path | None) -> tuple[list[dict], dict, list[str]]:
    from tm.organic_gates import item_id

    try:
        max_age = config.get(config.load(run), "pricing.max_age_days") or 7
    except ValueError:                                   # a run whose config is not written yet
        max_age = 7
    out, plugin, problems = [], {}, []
    priced_needed = [m for t_ in sections.values() for m in price_ids([t_])]
    if priced_needed and price_path is None:
        problems.append(f"no price file of today in {PRICES}: read them first (tm tool replicate_price --run "
                        f"{run.path.name} {' '.join(priced_needed)})")
    for sid, task in sections.items():
        rows = model_registry.active(task)
        if not rows:
            continue
        options, entries, taken = [], {}, set()
        twice = {r["model"] for r in rows if sum(x["model"] == r["model"] for x in rows) > 1}
        for row in rows:
            model, variant, price = row["model"], row["variant"], row["price"]
            per = price.get("per")
            oid = item_id(f"{model}-{variant}", taken)
            reason, cost, unit_price = None, None, None
            label = f"{row['name']} ({variant})" if model in twice else row["name"]   # a model in two groups
            if row["provider"] == "local" and task == "upscale":
                label = t("no_upscale")
            option = {"id": oid, "label": label, "group": t(f"group_{row['group']}"), "default": False,
                      "recommended": row["star"]}
            if row["provider"] == "replicate":
                if price_path is not None:
                    try:
                        unit_price, per, checked = model_registry.live_price(price_path, model, variant)
                    except ValueError as exc:
                        if "is not in" in str(exc):
                            problems.append(f"{model} is not in {price_path.name}: price it too (tm tool "
                                            f"replicate_price --run {run.path.name} {model})")
                        else:
                            reason = t("no_price")
                    else:
                        late = _day(checked)
                        if late is None or (today - late).days > max_age:
                            problems.append(f"the prices in {price_path.name} were checked {checked or 'never'}, more "
                                            f"than {max_age} days ago: read them again (tm tool replicate_price)")
                        cost = round(unit_price * _units(task, per, units), 4)
            elif "credits" in price:
                unit_price = price["credits"]
                option["cost_text"] = t("credits", n=f"{unit_price * _units(task, per, units):,.0f}")
            else:
                unit_price, cost = price.get("usd", 0), 0.0
            words = [row["good_for"]]
            if unit_price is not None:
                each = {"price": f"{unit_price:g}", "unit": t(f"per_{per}")}
                money = t("unit_credits", **each) if "credits" in price else t("unit_price", **each)
                words.append(money if unit_price else t("free"))
            option["means"] = " · ".join(w for w in words if w)
            if face and "photoreal_face" in row["cannot"] and sid not in ("images", "photos"):
                reason = reason or t("face")
            if narrated and row["send"].get("generate_audio") is True:
                reason = reason or t("audio_variant")
            if cost is not None:
                option["cost"] = cost
            if reason:
                option["disabled"] = reason
            options.append(option)
            recipe = f"{PLUGIN_PREFIX}{row['recipe']}" if row["recipe"] else None
            entries[oid] = {"model": None if row["provider"] == "local" and task == "upscale" else model,
                            "variant": variant, "task": task, "criteria": row["live"].get("criteria"),
                            "group": row["group"], "send": row["send"], "cost": cost,
                            "credits": round(unit_price * _units(task, per, units), 2) if "credits" in price else None,
                            "recipe": recipe if recipe_of(run, recipe) else None,
                            "recipe_to_write": None if (row["provider"] != "replicate" or recipe_of(run, recipe))
                            else library_recipe(model), "label": label}
        usable = [o for o in options if not o.get("disabled")]
        pick = next((o for o in usable if o["recommended"]), None) or next(
            (o for o in usable if o["group"] == t("group_suggested")), None) or (usable[0] if usable else None)
        if pick:
            pick["default"] = True
        for o in options:
            o["recommended"] = o is pick
        out.append({"id": sid, "kind": "one", "title": t(f"task_{sid}"),
                    "hint": t(f"hint_{sid}") if sid in ORGANIC else t("hint_task"),
                    "options": options, "text": {"label": t("own_model"), "value": ""}})
        plugin[sid] = entries
    return out, plugin, problems


def _page(run: RunFolder, sections: dict[str, str], units: dict, *, face: bool, narrated: bool, lang: str,
          title: str, today: date | None, extra: dict) -> dict:
    today = today or date.today()
    tr = organic_pages.translator(lang)
    t = lambda key, **v: tr(_M + key, **v)
    price_path = latest_prices(run)
    out, plugin, problems = _rows(run, sections, units, face=face, narrated=narrated, today=today, t=t,
                                  price_path=price_path)
    if problems:
        raise Stop(f"The Models page cannot be built: {'; '.join(dict.fromkeys(problems))}. Nothing was written. Read "
                   f"the prices, then build again; {AGAIN}.")
    if not out:
        raise Stop(f"The model registry has no model for {', '.join(sections.values())}; {AGAIN}.")
    stale = model_registry.stale(today)
    out.append({"id": "notes", "kind": "text", "title": t("notes"), "text": {"label": t("notes_label"), "value": ""}})
    price_rel = price_path.relative_to(run.path).as_posix() if price_path else None
    return {"page": PAGE, "lang": lang, "title": t("title", title=title), "lede": t("lede"),
            "run": choices.run_ref(run), "date": choices.today(), "sections": out, "total": {"label": t("total")},
            "plugin": {**plugin, **extra, "tasks": sections, "units": units, "price_file": price_rel,
                       "registry_checked": model_registry.checked().isoformat(), "rankings_stale": stale}}


def page_json(run: RunFolder, units_file: str | None = None, *, today: date | None = None) -> dict:
    """Organic video's Models page data (the module docstring). A Stop for a stale or missing price file."""
    pack_rel, pack = _recipe_pack(run)
    units = {**_pack_units(pack), **_units_file(run, units_file)}
    return _page(run, dict(ORGANIC), units, face=_face(pack), narrated=_narrated(pack),
                 lang=organic_pages.lang_of(pack), title=pack["title"], today=today,
                 extra={"pack": pack_rel, "candidates": units_file})


def tasks_page_json(run: RunFolder, tasks: list[str], units: dict, *, face: bool = False, narrated: bool = False,
                    title: str | None = None, today: date | None = None) -> dict:
    """The Models page of any registry `tasks` (Create an ad's S5, Refresh an ad's D1), each a section named as the
    task, priced for `units`."""
    known = model_registry.tasks()
    wrong = [t for t in tasks if t not in known]
    if wrong or not tasks:
        raise ValueError(f"{', '.join(wrong) or 'No task'}: give tasks of the model registry ({', '.join(known)}).")
    lang = str((config.load(run).get("languages") or {}).get("working") or "en") if (run.path / config.FILE).is_file() \
        else "en"
    return _page(run, {t: t for t in tasks}, units, face=face, narrated=narrated, lang=lang,
                 title=title or run.path.name, today=today, extra={"candidates": None})


def build(run: RunFolder, units_file: str | None = None) -> dict:
    data = page_json(run, units_file)
    return choices.build(run, data, pack=data["plugin"]["pack"], candidates=units_file)


def build_tasks(run: RunFolder, tasks: list[str], units: dict, **kw) -> dict:
    data = tasks_page_json(run, tasks, units, **kw)
    return choices.build(run, data, tasks=",".join(tasks))


# --- the choice ----------------------------------------------------------------------------------------------

def take(run: RunFolder, *, file: Path | None = None, text: Path | None = None, by_rule: bool = False) -> dict:
    """The models chosen into `03_wip/models_vNN.json` = `{<section>: {model, variant, task, criteria, group, send,
    cost, credits, recipe, recipe_to_write, label, user_named} | null, total_usd, notes, by: user|rule}`. A model
    the user wrote in a task's field is theirs (`user_named`, priced and given a recipe before use). `by_rule`
    (Hands-off) takes the page's defaults, the ★ models."""
    if by_rule:
        got = choices.decided(run, PAGE)
        found, _, _ = choices.answers(got["data"], [])
        got = {**got, "from": got["data_file"], "source": "rule", "answers": found, "done": True}
    else:
        got = choices.read(run, PAGE, file=file, text=text)
    plugin = got["data"]["plugin"]
    sections = plugin.get("tasks") or {t: t for t in TASKS}
    picks = {}
    for sid, task in sections.items():
        answer = got["answers"].get(sid)
        own = (answer or {}).get("text") or ""
        if own.strip():
            model = own.strip().split()[0]
            picks[sid] = {"model": model, "variant": None, "task": task, "criteria": None, "group": None, "send": {},
                          "cost": None, "credits": None, "recipe": None, "recipe_to_write": library_recipe(model),
                          "label": own.strip(), "user_named": True}
        else:
            picks[sid] = plugin[sid][answer["choice"]] if answer and answer.get("choice") and sid in plugin else None
    total = round(sum(p["cost"] or 0 for p in picks.values() if p), 4)
    notes = got["answers"].get("notes", {}).get("text") or ""
    body = {**picks, "total_usd": total, "notes": notes, "by": "rule" if by_rule else "user",
            "tasks": sections, "price_file": plugin.get("price_file")}
    rel = choices.record(run, PAGE, STEM, body, got)
    write = [p["recipe_to_write"] for p in picks.values() if p and p.get("recipe_to_write")]
    return {"file": rel, "models": picks, "total_usd": total, "recipes_to_write": write, "from": got["from"],
            "source": got["source"], "done": got["done"], "folder": got["folder"], "by": body["by"]}


def chosen(run: RunFolder) -> dict | None:
    """The latest choice of models in the run (`03_wip/models_vNN.json`), or None (a run from before the page)."""
    path = run.latest(WIP, STEM, "json")
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("page") == PAGE else None
