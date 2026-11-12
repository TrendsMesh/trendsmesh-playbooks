"""The Models page (organic video, after the idea is picked and before the pack, issue #86): the user chooses the
model of each task from today's rankings and Replicate prices, instead of a list fixed in the plugin.

    page_json(run, candidates_file)   the page's data (tm.organic_pages.choices)
    take(run, *, file, text, by_rule) 03_wip/models_vNN.json, which E1 starts from
    chosen(run)                       the latest choice of models in the run, or None
    recipe_of(run, path)              the recipe a model names, in the plugin or the workspace's library, when it is
                                      there and dated (its sources and the day they were checked)

**What the agent reads first** (flow.md E1, free reads only): the rankings of each task (Arena: text-to-image,
image edit, image-to-video; Artificial Analysis: image-to-video, voice), and the price of each candidate on
Replicate (`tm tool replicate_price`, the model's public page), then writes `02_research/models/candidates_vNN.json`:

    {"price_file": "02_research/models/prices_<day>_vNN.json",
     "units": {"images": 1, "video_seconds": 15, "takes": 1, "upscale_seconds": 15},
     "tasks": {"images" | "video" | "upscale": [candidate], "voice": [voice candidate]}}
    candidate = {"model", "criteria" (the priced variant's tier, as the price file holds it), "group":
                 budget|suggested|best, "rank": {"source", "place", "date"}, "good_at", "selected", "recipe",
                 "start_frame" (video: takes the approved first frame), "cannot" (a reason it can't work here)}
    voice candidate = {"model", "label", "group", "good_at", "credits" (for this video), "selected"}
    an upscale candidate with "model": null is "no upscale" ($0)

The engine prices each candidate itself: the unit price of the named variant in the price file (`organic_pack.
price_of`, so the variant compared is the variant priced) × this video's units (seconds for a price per second,
else images or takes). A ranking or a price file older than `pricing.max_age_days` is refused. **Greyed out, with the
reason** (never chosen by mistake): a model the price file has no price for; Seedance (any version) when the frame
has a photoreal face (Replicate E005, which cannot be worked around there); a variant with audio when the video has
a separate voiceover and the file prices one without; and any `cannot` the agent wrote. A video model with no
start-frame input is not listed. A model without a recipe is listed with "recipe to write": once it is chosen, the
agent writes the recipe (from the model's official prompting guide, with the sources and the date, the input fields
from Replicate's API) into the workspace's `library/model-prompting/` before E1.

Sections: images, video, upscale, voice model, each in the groups budget, suggested, best quality; the one marked
`selected` (else the first suggested) is ticked. The total at the bottom is the video's cost in USD for the ticked
models, recalculated on every change (the voice is in credits, on the user's ElevenLabs account, shown beside it).
At Hands-off the suggested models are taken by rule (`take(..., by_rule=True)`): the page's defaults, recorded as
the rule's.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

from tm import config, organic_pages, paths, stepchecks, state, trend_spool
from tm.organic_pages import choices
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "models"
STEM = "models"
WIP = "03_wip"
CANDIDATES = "02_research/models"
TASKS = ("images", "video", "upscale", "voice")
GROUPS = ("budget", "suggested", "best")
_M = "organic.models."
SEEDANCE = "bytedance/seedance"                    # refuses a photoreal face in its inputs (Replicate E005)
LIBRARY = "library/model-prompting/"               # the workspace's recipes, written for a model the plugin has none of
PLUGIN_RECIPES = paths.bundled_data().parent / "references" / "model-prompting"
PLUGIN_PREFIX = "references/model-prompting/"
_CHECKED = re.compile(r"\(checked (\d{4}-\d{2}-\d{2})\)")
_SOURCES = re.compile(r"^Sources?:", re.MULTILINE)
_WITH_AUDIO = re.compile(r"audio\s*=\s*(true|yes|on|with)", re.IGNORECASE)
_NO_AUDIO = re.compile(r"audio\s*=\s*(false|no|off|without)", re.IGNORECASE)
TAKE_MAX_S = 15
# The voice models (ElevenLabs, on the user's key and credits; not on Replicate). ElevenLabs v4 is the default
# (#88 sets it as tm tool elevenlabs tts's default); v4 Turbo the budget one.
VOICE_MODELS = {"eleven_v4": ("ElevenLabs Eleven v4", "suggested"),
                "eleven_v4_turbo": ("ElevenLabs Eleven v4 Turbo", "budget")}


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


def _candidates(run: RunFolder, rel: str | None) -> tuple[str, dict]:
    path = run.path / rel if rel else run.latest(CANDIDATES, "candidates", "json")
    if path is None or not Path(path).is_file():
        raise Stop(f"Read today's rankings and Replicate prices first, and write the candidates as "
                   f"{CANDIDATES}/candidates_vNN.json (flow.md E1), then build the page; {AGAIN}.")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{Path(path).name} is not JSON ({exc}): write it again as a new version; {AGAIN}.") from None
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), dict):
        raise Stop(f"{Path(path).name} must be an object with price_file, units and tasks; {AGAIN}.")
    return Path(path).resolve().relative_to(run.path.resolve()).as_posix(), data


def _face(pack: dict) -> bool:
    """Whether a frame the video starts from has a photoreal face: a host image, or an images item marked `face`."""
    host = (pack.get("host") or {}).get("kind")
    return host == "image" or any(item.get("face") for st in pack.get("stages") or []
                                  for item in st.get("items") or [])


def _narrated(pack: dict) -> bool:
    from tm import organic_voiced
    return organic_voiced.narrated(pack)


def _units(task: str, unit: str, units: dict) -> float:
    """How many of `unit` this video takes for `task`: seconds for a price per second, else images or takes."""
    seconds = float(units.get("upscale_seconds" if task == "upscale" else "video_seconds") or 0)
    if "second" in unit.lower():
        return seconds
    if task == "images":
        return float(units.get("images") or 0)
    return float(units.get("takes") or math.ceil(seconds / TAKE_MAX_S) or 1)


def _price_tiers(price_file: Path, model: str) -> list[dict]:
    try:
        entries = json.loads(price_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entry = next((e for e in entries if isinstance(e, dict) and e.get("model") == model), {})
    return entry.get("tiers") or []


def page_json(run: RunFolder, candidates_file: str | None = None, *, today: date | None = None) -> dict:
    """The Models page's data (the module docstring). A Stop for a stale ranking or price file, or a candidates file
    not in its shape."""
    from tm import organic_pack

    today = today or date.today()
    pack_rel, pack = _recipe_pack(run)
    cand_rel, cand = _candidates(run, candidates_file)
    tr = organic_pages.translator(organic_pages.lang_of(pack))
    t = lambda key, **v: tr(_M + key, **v)
    max_age = config.get(config.load(run), "pricing.max_age_days") or 7
    problems: list[str] = []
    price_rel = cand.get("price_file")
    price_path = (run.path / price_rel).resolve() if isinstance(price_rel, str) else None
    if price_path is None or not price_path.is_file() or not price_path.is_relative_to(run.path.resolve()):
        problems.append(f"price_file {price_rel!r} is not a price file of this run (tm tool replicate_price)")
    units = cand.get("units") if isinstance(cand.get("units"), dict) else {}
    face, narrated = _face(pack), _narrated(pack)
    sections, plugin = [], {}
    for task in TASKS:
        rows = cand["tasks"].get(task) or []
        if not isinstance(rows, list) or not rows:
            continue
        options, entries = [], {}
        taken: set[str] = set()
        for n, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                problems.append(f"{task} {n} is not an object")
                continue
            model = row.get("model")
            group = row.get("group")
            if group not in GROUPS:
                problems.append(f"{task} {model}: group {group!r} is not one of {', '.join(GROUPS)}")
                continue
            if task == "video" and row.get("start_frame") is False:
                continue                                  # the video's start must be the approved first frame
            rank = row.get("rank") if isinstance(row.get("rank"), dict) else None
            if task != "voice" and model is not None:
                late = _day((rank or {}).get("date"))
                if rank is None or late is None or (today - late).days > max_age:
                    problems.append(f"{model}'s ranking ({(rank or {}).get('source') or 'none'}, read "
                                    f"{(rank or {}).get('date') or 'never'}) is older than {max_age} days: read it today")
            from tm.organic_gates import item_id
            oid = item_id(f"{model or 'none'}-{row.get('criteria') or ''}".strip("-"), taken)
            option = {"id": oid, "label": row.get("label") or model or t("no_upscale"),
                      "means": " · ".join(x for x in (row.get("good_at") or "", _rank_words(rank, t)) if x),
                      "group": t(f"group_{group}"), "default": False, "recommended": bool(row.get("selected"))}
            if model and task != "voice":
                option["link"] = f"https://replicate.com/{model}"
            if row.get("criteria"):
                option["badge"] = str(row["criteria"])
            reason = row.get("cannot") if isinstance(row.get("cannot"), str) and row["cannot"].strip() else None
            cost = 0.0 if model is None else None
            if task == "voice":
                credits = row.get("credits")
                option["cost_text"] = t("credits", n=f"{credits:,.0f}") if isinstance(credits, (int, float)) else ""
            elif model is not None and price_path is not None and price_path.is_file():
                try:
                    price, unit, checked = organic_pack.price_of(price_path, model, row.get("criteria"))
                except (ValueError, TypeError) as exc:
                    reason = reason or t("no_price")
                    price, unit, checked = None, "", ""
                    plugin.setdefault("unpriced", []).append(f"{model}: {exc}")
                if price is not None:
                    late = _day(checked)
                    if late is None or (today - late).days > max_age:
                        problems.append(f"the prices in {price_rel} were checked {checked or 'never'}, more than "
                                        f"{max_age} days ago: read them again (tm tool replicate_price)")
                    cost = round(price * _units(task, unit, units), 4)
                    option["means"] = " · ".join(x for x in (option["means"], t("unit_price", price=f"{price:g}",
                                                                                unit=unit)) if x)
                    if narrated and _WITH_AUDIO.search(str(row.get("criteria") or "")) and any(
                            _NO_AUDIO.search(str(x.get("criteria") or "")) for x in _price_tiers(price_path, model)):
                        reason = reason or t("audio_variant")
            if task == "video" and face and str(model or "").startswith(SEEDANCE):
                reason = reason or t("face")
            if model and task != "voice" and recipe_of(run, row.get("recipe")) is None:
                option["badge"] = " · ".join(x for x in (option.get("badge"), t("recipe_to_write")) if x)
            if cost is not None:
                option["cost"] = cost
            if reason:
                option["disabled"] = reason
            options.append(option)
            entries[oid] = {"model": model, "criteria": row.get("criteria"), "group": group, "cost": cost,
                            "credits": row.get("credits") if task == "voice" else None, "rank": rank,
                            "recipe": row.get("recipe") if recipe_of(run, row.get("recipe")) else None,
                            "recipe_to_write": None if (model is None or task == "voice" or recipe_of(run, row.get("recipe")))
                            else library_recipe(model), "label": option["label"]}
        order = {t(f"group_{g}"): i for i, g in enumerate(GROUPS)}
        options.sort(key=lambda o: order[o["group"]])
        usable = [o for o in options if not o.get("disabled")]
        pick = next((o for o in usable if o["recommended"]), None) or next(
            (o for o in usable if o["group"] == t("group_suggested")), None) or (usable[0] if usable else None)
        if pick:
            pick["default"] = True
        for o in options:
            o["recommended"] = o is pick
        sections.append({"id": task, "kind": "one", "title": t(f"task_{task}"), "hint": t(f"hint_{task}"),
                         "options": options})
        plugin[task] = entries
    if problems:
        raise Stop(f"The Models page cannot be built from {cand_rel}: {'; '.join(problems[:5])}. Nothing was written. "
                   f"Read again what is old, write the next candidates version, then build again; {AGAIN}.")
    if not sections:
        raise Stop(f"{cand_rel} lists no candidates: write them per task (flow.md E1), then build again; {AGAIN}.")
    sections.append({"id": "notes", "kind": "text", "title": t("notes"), "text": {"label": t("notes_label"), "value": ""}})
    return {"page": PAGE, "lang": pack.get("lang") or "en", "title": t("title", title=pack["title"]), "lede": t("lede"),
            "run": choices.run_ref(run), "date": choices.today(), "sections": sections,
            "total": {"label": t("total")},
            "plugin": {**plugin, "pack": pack_rel, "candidates": cand_rel, "price_file": price_rel}}


def _rank_words(rank: dict | None, t) -> str:
    if not rank or not rank.get("source"):
        return ""
    return t("rank", place=rank.get("place") if rank.get("place") is not None else "?", source=rank["source"],
             date=rank.get("date") or "?")


def build(run: RunFolder, candidates_file: str | None = None) -> dict:
    data = page_json(run, candidates_file)
    return choices.build(run, data, pack=data["plugin"]["pack"], candidates=data["plugin"]["candidates"])


# --- the choice ----------------------------------------------------------------------------------------------

def take(run: RunFolder, *, file: Path | None = None, text: Path | None = None, by_rule: bool = False) -> dict:
    """The models chosen into `03_wip/models_vNN.json` = `{images, video, upscale, voice: {model, criteria, group,
    cost, credits, recipe, recipe_to_write, label} | null, total_usd, notes, by: user|rule}`. `by_rule` (Hands-off)
    takes the page's defaults, the suggested models."""
    if by_rule:
        got = choices.decided(run, PAGE)
        found, _, _ = choices.answers(got["data"], [])
        got = {**got, "from": got["data_file"], "source": "rule", "answers": found, "done": True}
    else:
        got = choices.read(run, PAGE, file=file, text=text)
    plugin = got["data"]["plugin"]
    picks = {}
    for task in TASKS:
        answer = got["answers"].get(task)
        picks[task] = plugin[task][answer["choice"]] if answer and answer["choice"] else None
    total = round(sum(p["cost"] or 0 for t, p in picks.items() if p and t != "voice"), 4)
    notes = got["answers"].get("notes", {}).get("text") or ""
    body = {**picks, "total_usd": total, "notes": notes, "by": "rule" if by_rule else "user",
            "candidates": plugin["candidates"], "price_file": plugin["price_file"]}
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
