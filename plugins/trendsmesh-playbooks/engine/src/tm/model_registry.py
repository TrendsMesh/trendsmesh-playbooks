"""The model registry (issue #115): the one source of models, variants, prices, limits and routes for every paid call.

    load()                        data/models/registry.yaml, read once (dates as YYYY-MM-DD text)
    aliases()                     data/models/aliases.yaml: each model's names in Arena, Artificial Analysis, Replicate
    validate(data, aliases)       what is wrong with a registry, in words ([] when it holds)
    model(id) / ids()             one model's entry / the ids of the active models (or of the given statuses)
    active(task)                  the task's rows a user may see: active models only, budget, suggested, best
    star(task)                    the row selected in advance (★)
    variants(id) / send(id, v)    a model's variants / the inputs the plugin always sends for variant v
    price(id, v)                  {usd | credits, per, checked} of variant v, as the provider bills it
    live_price(file, id, v)       the variant's price today from a `tm tool replicate_price` file, in the registry's unit
    route(name)                   talking_person, voice, lipsync_fallback, long_speech
    cannot(id) / with_limit(x)    a model's hard limits / the models with limit x (e.g. photoreal_face, E005)
    ai_markers()                  the providers and model names Meta's AI disclosure looks for (tm.ai_media)
    checked() / stale(today)      the day the prices were read / whether that is more than 30 days ago

Only an `active` model is ever offered: `new` (found by the two-weekly review, not tested) and `removed` are never
shown. Nothing here writes the registry: the owner reviews every change (`.github/workflows/model-review.yml`).
A model the user names outside the registry is not blocked here; the playbooks write its recipe first.
"""

from __future__ import annotations

import functools
import json
import math
from datetime import date
from pathlib import Path

import yaml

from tm import paths

FILE = paths.bundled_data() / "models" / "registry.yaml"
ALIASES = paths.bundled_data() / "models" / "aliases.yaml"
PROVIDERS = ("replicate", "elevenlabs", "local")
STATUSES = ("active", "new", "removed")
GROUPS = ("budget", "suggested", "best")
PER = ("image", "second", "run", "character", "minute")
ROUTES = ("talking_person", "voice", "lipsync_fallback", "long_speech")
STALE_DAYS = 30                    # rankings are read live only when the registry is older than this
RECIPES = paths.bundled_data().parent / "references" / "model-prompting"


def _text_dates(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _text_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_text_dates(v) for v in value]
    return value


def _read(path: Path) -> dict:
    return _text_dates(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


@functools.lru_cache(maxsize=None)
def _cached() -> dict:
    return _read(FILE)


def load() -> dict:
    """The shipped registry (cached: do not change what it returns; copy it first)."""
    return _cached()


@functools.lru_cache(maxsize=None)
def aliases() -> dict:
    return _read(ALIASES)


def _data(data: dict | None) -> dict:
    return load() if data is None else data


def model(model_id: str, *, data: dict | None = None) -> dict | None:
    return next((m for m in _data(data).get("models") or [] if m.get("id") == model_id), None)


def ids(statuses: tuple[str, ...] = ("active",), *, provider: str | None = None, data: dict | None = None) -> list[str]:
    return [m["id"] for m in _data(data).get("models") or []
            if m.get("status") in statuses and (provider is None or m.get("provider") == provider)]


def variants(model_id: str, *, data: dict | None = None) -> dict:
    found = model(model_id, data=data)
    return (found or {}).get("variants") or {}


def _variant(model_id: str, variant: str, data: dict | None = None) -> dict:
    found = variants(model_id, data=data).get(variant)
    if found is None:
        raise KeyError(f"{model_id} has no variant {variant!r} in the model registry.")
    return found


def send(model_id: str, variant: str, *, data: dict | None = None) -> dict:
    """The inputs the plugin always sends for this variant (Replicate's defaults are often the dear ones)."""
    return dict(_variant(model_id, variant, data).get("send") or {})


def price(model_id: str, variant: str, *, data: dict | None = None) -> dict:
    """`{usd | credits, per, checked}` of the variant, as the provider bills it."""
    got = dict(_variant(model_id, variant, data).get("price") or {})
    got.setdefault("checked", _data(data).get("checked"))
    return got


def _row(m: dict, task: str, entry: dict, data: dict | None) -> dict:
    var = (m.get("variants") or {}).get(entry.get("variant")) or {}
    p = dict(var.get("price") or {})
    p.setdefault("checked", _data(data).get("checked"))
    return {"model": m["id"], "variant": entry.get("variant"), "group": entry.get("group"),
            "star": bool(entry.get("star")), "name": m.get("name") or m["id"], "provider": m.get("provider"),
            "good_for": m.get("good_for") or "", "send": dict(var.get("send") or {}), "price": p,
            "live": dict(var.get("live") or {}), "cannot": list(m.get("cannot") or []), "recipe": m.get("recipe"),
            "task": task}


def active(task: str, *, data: dict | None = None) -> list[dict]:
    """The task's rows a user may see (active models only), ordered budget, suggested, best (registry order inside)."""
    rows = [_row(m, task, e, data) for m in _data(data).get("models") or [] if m.get("status") == "active"
            for e in (m.get("tasks") or {}).get(task) or []]
    return sorted(rows, key=lambda r: GROUPS.index(r["group"]) if r["group"] in GROUPS else len(GROUPS))


def star(task: str, *, data: dict | None = None) -> dict:
    found = [r for r in active(task, data=data) if r["star"]]
    if len(found) != 1:
        raise KeyError(f"The model registry has {len(found)} selected models for {task}, and needs one.")
    return found[0]


def tasks(*, data: dict | None = None) -> dict:
    return _data(data).get("tasks") or {}


def models_of(task: str, *, data: dict | None = None) -> list[str]:
    return list(dict.fromkeys(r["model"] for r in active(task, data=data)))


def route(name: str, *, data: dict | None = None):
    routes = _data(data).get("routes") or {}
    if name not in routes:
        raise KeyError(f"The model registry has no route {name!r}.")
    return routes[name]


def cannot(model_id: str, *, data: dict | None = None) -> set[str]:
    return set((model(model_id, data=data) or {}).get("cannot") or [])


def with_limit(limit: str, *, data: dict | None = None) -> list[str]:
    """Every model (any status) with this hard limit, so a removed or new one is still refused what it cannot do."""
    return [m["id"] for m in _data(data).get("models") or [] if limit in (m.get("cannot") or [])]


def variant_by_send(model_id: str, key: str, value: object, *, data: dict | None = None) -> str | None:
    """The variant of `model_id` that sends `key: value` (H3's `resolution: "2K"` -> "2K"), or None."""
    for name, var in variants(model_id, data=data).items():
        if str((var.get("send") or {}).get(key, "")).lower() == str(value).lower():
            return name
    return None


def live_price(price_file: Path | str, model_id: str, variant: str, *, data: dict | None = None
               ) -> tuple[float, str, str]:
    """(price in the registry's unit, per, checked) of the variant in a `tm tool replicate_price` file: the tier its
    `live.criteria` names, times its `live.factor`. A ValueError when the file does not price it (never a 0)."""
    var = _variant(model_id, variant, data)
    live, per = var.get("live") or {}, (var.get("price") or {}).get("per")
    name = Path(price_file).name
    entries = json.loads(Path(price_file).read_text(encoding="utf-8"))
    entry = next((e for e in entries if isinstance(e, dict) and e.get("model") == model_id), None)
    if entry is None:
        raise ValueError(f"{model_id} is not in {name}.")
    if "error" in entry:
        raise ValueError(f"{model_id} has no price in {name}: {entry['error']}.")
    tiers = [t for t in entry.get("tiers") or [] if isinstance(t, dict)]
    found = [t for t in tiers if t.get("criteria") == live.get("criteria")]
    if len(found) != 1:
        raise ValueError(f"{model_id} has no price in {name} for {live.get('criteria')!r} (the {variant} variant).")
    text = str(found[0].get("price") or "").replace("$", "").replace(",", "").strip()
    try:
        usd = float(text) * float(live.get("factor", 1))
    except ValueError:
        usd = float("nan")
    if not math.isfinite(usd) or usd <= 0:
        raise ValueError(f"{model_id}: the price {found[0].get('price')!r} in {name} is not a number above zero.")
    return usd, str(per or found[0].get("unit") or ""), str(entry.get("checked") or "")


def ai_markers(*, data: dict | None = None) -> tuple[str, ...]:
    """What names a generative-AI source in a manifest row: the paid providers and every paid model's id and name
    (any status, so a removed model's old files are still disclosed). Free local tools are not AI media."""
    out: list[str] = [p for p in PROVIDERS if p != "local"]
    for m in _data(data).get("models") or []:
        if m.get("provider") == "local":
            continue
        mid = str(m["id"]).lower()
        out.append(mid)
        short = mid.rsplit("/", 1)[-1]
        if len(short) >= 4 and any(ch.isdigit() or ch in "-_" for ch in short):
            out.append(short)
    return tuple(dict.fromkeys(out))


def checked(*, data: dict | None = None) -> date:
    return date.fromisoformat(str(_data(data)["checked"])[:10])


def stale(today: date | None = None, *, data: dict | None = None) -> bool:
    """Whether the registry is older than 30 days: then a run reads the rankings live too (issue #115, section 2)."""
    return ((today or date.today()) - checked(data=data)).days > STALE_DAYS


# --- the check ------------------------------------------------------------------------------------------------

def _price_problems(where: str, p: object) -> list[str]:
    if not isinstance(p, dict):
        return [f"{where}: no price"]
    out = []
    amounts = [k for k in ("usd", "credits") if k in p]
    if len(amounts) != 1 or not isinstance(p[amounts[0]], (int, float)) or p[amounts[0]] < 0:
        out.append(f"{where}: the price needs one amount, usd or credits, 0 or more")
    if p.get("per") not in PER:
        out.append(f"{where}: the price's per is {p.get('per')!r}, not one of {', '.join(PER)}")
    return out


def validate(data: dict, alias_table: dict | None = None) -> list[str]:
    """What is wrong with `data` as a registry, in words; [] when it holds."""
    out: list[str] = []
    task_names = set((data.get("tasks") or {}))
    try:
        date.fromisoformat(str(data.get("checked"))[:10])
    except ValueError:
        out.append("checked: the day the prices were read is missing")
    seen: set[str] = set()
    stars: dict[str, int] = {t: 0 for t in task_names}
    for n, m in enumerate(data.get("models") or []):
        mid = m.get("id") if isinstance(m, dict) else None
        where = mid or f"model {n + 1}"
        if not isinstance(mid, str) or not mid:
            out.append(f"{where}: no id")
            continue
        if mid in seen:
            out.append(f"{mid} is listed twice")
        seen.add(mid)
        if m.get("provider") not in PROVIDERS:
            out.append(f"{mid}: provider {m.get('provider')!r} is not one of {', '.join(PROVIDERS)}")
        if m.get("status") not in STATUSES:
            out.append(f"{mid}: status {m.get('status')!r} is not one of {', '.join(STATUSES)}")
        if not str(m.get("good_for") or "").strip():
            out.append(f"{mid}: no good_for sentence")
        recipe = m.get("recipe")
        if recipe is not None and not (RECIPES / str(recipe)).is_file():
            out.append(f"{mid}: its recipe {recipe} is not in references/model-prompting/")
        var = m.get("variants") or {}
        if not var:
            out.append(f"{mid}: no variant")
        for name, v in var.items():
            if not isinstance(v, dict) or not isinstance(v.get("send"), dict):
                out.append(f"{mid} {name}: no send")
                continue
            if str(v["send"].get("quality", "")).lower() == "auto":
                out.append(f"{mid} {name}: sends quality auto, the dearest; name the quality")
            out += _price_problems(f"{mid} {name}", v.get("price"))
            if m.get("provider") == "replicate" and m.get("status") == "active" and "live" in v \
                    and not str((v.get("live") or {}).get("criteria") or "").strip():
                out.append(f"{mid} {name}: live names no criteria of Replicate's price file")
        for task, entries in (m.get("tasks") or {}).items():
            if task not in task_names:
                out.append(f"{mid}: no task {task} in tasks")
                continue
            for e in entries or []:
                if e.get("variant") not in var:
                    out.append(f"{mid} {task}: no variant {e.get('variant')}")
                if e.get("group") not in GROUPS:
                    out.append(f"{mid} {task}: group {e.get('group')} is not one of {', '.join(GROUPS)}")
                if e.get("star"):
                    if m.get("status") != "active":
                        out.append(f"{mid} is {m.get('status')} and selected in advance for {task}: only an active "
                                   "model is")
                    else:
                        stars[task] += 1
    for task, count in stars.items():
        used = any(task in (m.get("tasks") or {}) for m in data.get("models") or [] if isinstance(m, dict))
        if used and count != 1:
            out.append(f"{task} has {count} stars: one model is selected in advance per task")
    routes = data.get("routes") or {}
    for name in ROUTES:
        if name not in routes:
            out.append(f"routes: no {name}")
    named: list[tuple[str, object]] = []
    for sit, r in ((routes.get("talking_person") or {}).get("situations") or {}).items():
        named += [(f"talking_person {sit}", r.get(k)) for k in ("model", "then", "plus")]
        named += [(f"talking_person {sit}", x) for x in r.get("also") or []]
        if r.get("variant") not in variants(str(r.get("model")), data=data):
            out.append(f"talking_person {sit}: {r.get('model')} has no variant {r.get('variant')}")
    for n, r in enumerate(routes.get("voice") or [], 1):
        named += [(f"voice {n}", r.get(k)) for k in ("model", "then", "budget")]
    named.append(("lipsync_fallback", (routes.get("lipsync_fallback") or {}).get("model")))
    for where, mid in named:
        if mid is not None and model(str(mid), data=data) is None:
            out.append(f"routes {where}: {mid} is not in the registry")
        elif mid is not None and model(str(mid), data=data).get("status") != "active":
            out.append(f"routes {where}: {mid} is not active")
    if alias_table is not None:
        for mid in alias_table:
            if mid not in seen:
                out.append(f"aliases: {mid} is not in the registry")
    return out
