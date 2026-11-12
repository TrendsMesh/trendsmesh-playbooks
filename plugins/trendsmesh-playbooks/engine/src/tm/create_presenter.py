"""Create an ad's talking person, chosen on the plan's page (issue #100): CA5's table by situation, the plan's
situation first, each row with its model, what it needs and today's price from Replicate.

    rows(run, plan)                      the table's rows for the page, the plan's situation first, each priced
    choose(presenter, situation, model)  the plan's `presenter` object after a pick
    record(run, situation, model)        the pick written into the next production plan version, when it changes it

**Prices** are Replicate's, read with `tm tool replicate_price` (free) and saved in the run; nothing here fetches.
A row's price comes from the first file that prices its model: the plan's `presenter.price_file`, the price files
of its take lines, then the run's `02_research/models/prices_<day>_vNN.json`, newest first. The variant priced is the
row's (`tier`: the words its criteria hold, as #86's Models page compares the variant it prices), through
`organic_pack.price_of`, and a take is 15 s (`organic_pages.models._units`). A price older than
`pricing.max_age_days` is shown with its age; a row with no price says so. The page never blocks on a price: the
plan's own lines carry the prices the check reads.

**The pick** is two answers: the situation (`presenter`: one of the rows) and the model (`presenter_model`: the
row's own, or another of the table's). It is written as the plan's `presenter.situation`, with `presenter.
user_choice: true` and `presenter.model` when the model is not the row's (`create_plan.PRESENTERS`), so `tm ad check
plan` reads it unchanged: a take on another model than the row's passes only as the user's choice. A pick that changes
the plan is a new plan version, checked again; the take lines are rewritten to the pick before the check.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tm import config, create_config, create_plan, manifest
from tm.runfolder import RunFolder

TAKE_S = 15
PRICES = "02_research/models"
ROW = "row"                       # the presenter_model answer for the row's own model
# CA5's table (skills/create-ad/references/rules.md), in its order, keyed as create_plan.PRESENTERS: the model on
# Replicate, the words of its priced tier's criteria, and what the row needs from the user.
ROWS = {
    "described": {"model": "bytedance/seedance-2.0", "tier": ("non_video_in", "720p")},
    "specific_person": {"model": "minimax/h3", "tier": ("768P",)},
    "own_voice": {"model": "minimax/h3", "tier": ("768P",)},
    "exact_wording": {"model": "google/gemini-omni-1.2-flash", "tier": ("720p",)},
    "fallback": {"model": "kwaivgi/kling-avatar-v2", "tier": ("std",), "plus": "elevenlabs"},
}
MODELS = {"bytedance/seedance-2.0": "Seedance 2.0", "minimax/h3": "MiniMax H3",
          "google/gemini-omni-1.2-flash": "Gemini Omni 1.2 Flash",
          "kwaivgi/kling-avatar-v2": "ElevenLabs + Kling Avatar v2"}
FALLBACK = "fallback"             # only once a review showed a take looks or sounds wrong (presenter.why)


def _presenter(plan: dict) -> dict:
    return plan.get("presenter") if isinstance(plan.get("presenter"), dict) else {}


def _inside(run: RunFolder, rel: object) -> Path | None:
    if not isinstance(rel, str) or not rel:
        return None
    path = (run.path / rel).resolve()
    return path if path.is_file() and path.is_relative_to(run.path.resolve()) else None


def _price_files(run: RunFolder, plan: dict) -> list[Path]:
    named = [_presenter(plan).get("price_file")] + [ln.get("price_file") for ln in plan.get("lines") or []
                                                     if isinstance(ln, dict) and ln.get("type") == "presenter"]
    out = [p for p in (_inside(run, r) for r in named) if p is not None]
    base = run.path / PRICES
    saved = sorted(base.glob("prices_*.json"), key=lambda p: p.name, reverse=True) if base.is_dir() else []
    return list(dict.fromkeys(out + [p.resolve() for p in saved]))


def _tier(path: Path, model: str, words: tuple[str, ...]) -> str | None:
    """The criteria of the one tier of `model` in `path` holding all `words` (else its only tier), or None."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = next((e for e in entries if isinstance(e, dict) and e.get("model") == model), None) \
        if isinstance(entries, list) else None
    tiers = [t for t in (entry or {}).get("tiers") or [] if isinstance(t, dict)]
    found = [t for t in tiers if all(w.lower() in str(t.get("criteria") or "").lower() for w in words)]
    if len(found) != 1 and len(tiers) == 1:
        found = tiers
    return str(found[0].get("criteria")) if len(found) == 1 else None


def price(run: RunFolder, plan: dict, situation: str, *, today: date | None = None) -> dict | None:
    """A row's price for one 15 s take: `{usd, unit_price, unit, checked, file, old_days}` (`old_days` set when the
    price is older than `pricing.max_age_days`), or None when no saved price file prices its model."""
    from tm import organic          # first: organic_pack's own imports load in their order from it  # noqa: F401
    from tm import organic_pack
    from tm.organic_pages import models as organic_models

    row = ROWS[situation]
    today = today or date.today()
    for path in _price_files(run, plan):
        criteria = _tier(path, row["model"], row["tier"])
        if criteria is None:
            continue
        try:
            unit_price, unit, checked = organic_pack.price_of(path, row["model"], criteria)
        except (OSError, ValueError, TypeError):
            continue
        usd = round(unit_price * organic_models._units("video", unit, {"video_seconds": TAKE_S, "takes": 1}), 4)
        max_age = config.get(create_config.load(run), "pricing.max_age_days") or 7
        try:
            age = (today - date.fromisoformat(checked[:10])).days
        except ValueError:
            age = None
        return {"usd": usd, "unit_price": unit_price, "unit": unit, "checked": checked,
                "file": path.relative_to(run.path.resolve()).as_posix(),
                "old_days": age if age is None or age > max_age else None}
    return None


def situation_of(plan: dict) -> str | None:
    s = _presenter(plan).get("situation")
    return s if s in ROWS else None


def rows(run: RunFolder, plan: dict, *, today: date | None = None) -> list[dict]:
    """CA5's rows, the plan's situation first, then the others in the table's order: `{situation, model, plan (the
    plan's own row), needs (its words' key: the situation), plus (ElevenLabs on top, the fallback), price}`."""
    first = situation_of(plan)
    order = ([first] if first else []) + [s for s in ROWS if s != first]
    return [{"situation": s, "model": ROWS[s]["model"], "plan": s == first, "needs": s,
             "plus": ROWS[s].get("plus"), "price": price(run, plan, s, today=today)} for s in order]


def is_rows_model(situation: str, model: object) -> bool:
    return model in (None, "", ROW) or create_plan.PRESENTERS[situation][0] in str(model).lower()


def choose(presenter: dict, situation: str, model: object) -> dict:
    """The plan's `presenter` after the pick: the situation, and `user_choice: true` with the `model` only when it is
    not the row's (the fallback's `why` and the plan's `price_file` are kept)."""
    out = {k: v for k, v in (presenter or {}).items() if k not in ("situation", "user_choice", "model")}
    out = {"situation": situation, **out}
    if not is_rows_model(situation, model):
        out.update({"user_choice": True, "model": model})
    return out


def record(run: RunFolder, situation: str, model: object) -> str | None:
    """Write the pick into the next `production_plan_vNN.json` (the checked plan with its `presenter` changed), and
    its run-relative path; None when the pick leaves the plan as it is (or there is no checked plan)."""
    path = create_plan.checked_file(run, create_plan.PLAN)
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    if situation not in ROWS or not isinstance(plan, dict):
        return None
    new = choose(_presenter(plan), situation, model)
    if new == _presenter(plan):
        return None
    target = run.next_version(create_config.WIP, create_plan.PLAN, "json")
    run.assert_writable(target)
    target.write_text(json.dumps({**plan, "presenter": new}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel = target.relative_to(run.path).as_posix()
    manifest.record(run, rel, create_config.WIP, "tm page decision --record (the talking person picked on the page)")
    return rel
