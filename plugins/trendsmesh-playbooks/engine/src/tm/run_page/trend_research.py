"""Trend research's check-ins on the shared run page (issue #60): what each stage shows from the run's files, and a
decided choice in words.

The report itself (`tm research report`, tm.research_report) is the page's content; these stages are the decisions
that shaped it, so each shows a few facts, not the report again: the seed phrases and market (G0), the map's counts
and the shortlisted hooks in their two lists (G1), the picks (G2), the views (G3) and how next week's run starts
(GS). Their words are `run_page.trend_research.*`; the views' names are the report's own (`report.view_*`).
"""

from __future__ import annotations

from tm import config, i18n, research_config, research_growth, research_map, state, trends
from tm.run_page.context import Context
from tm.run_page.words import tx

W = "trend_research."


def _w(ctx: Context, key: str, **values: object) -> str:
    return ctx.t(W + key, **values)


def _facts(rows: list[tuple[str, object]], source: str | None) -> list[dict]:
    rows = [(k, v) for k, v in rows if v not in (None, "", [])]
    return [{"kind": "facts", "rows": rows, "source": source}] if rows else []


def _cfg(ctx: Context) -> dict:
    try:
        return config.load(ctx.run)
    except (OSError, ValueError):
        return {}


def _category(ctx: Context) -> str:
    return str(((_cfg(ctx).get("category") or {}).get("phrase")) or "").strip()


def _growth(ctx: Context) -> dict[str, dict]:
    data = ctx.json(ctx.latest(trends.RESEARCH, research_growth.STEM, "json"))
    rows = data.get("trends") if isinstance(data, dict) else None
    return {t["id"]: t for t in rows or [] if isinstance(t, dict) and isinstance(t.get("id"), str)}


def _names(ids: list, rows: dict[str, dict]) -> str:
    return ", ".join(str((rows.get(i) or {}).get("name") or i) for i in ids)


def _seeds(ctx: Context) -> list[dict]:
    cfg = _cfg(ctx)
    cat = cfg.get("category") or {}
    langs = i18n.run_languages(ctx.run)
    views = [tx("report.view_" + research_config.PICK_OUTPUTS[o], ctx.lang) for o in cfg.get("outputs") or []
             if o in research_config.PICK_OUTPUTS]
    seeds = [str(s.get("phrase") if isinstance(s, dict) else s) for s in cat.get("seeds") or []]
    return _facts([(_w(ctx, "fact.category"), cat.get("phrase")), (_w(ctx, "fact.seeds"), ", ".join(seeds)),
                   (_w(ctx, "fact.market"), cfg.get("market")),
                   (_w(ctx, "fact.languages"), " / ".join(x for x in (langs.working, langs.market) if x)),
                   (_w(ctx, "fact.outputs"), ", ".join(views))], config.FILE)


def _map(ctx: Context) -> list[dict]:
    path = ctx.latest(trends.RESEARCH, research_map.STEM, "json")
    cmap = ctx.json(path)
    if not isinstance(cmap, dict):
        return []
    hooks = sorted((t for t in _growth(ctx).values() if t.get("kind") == "hook_trend"
                    and (t.get("plugin") or {}).get("use") in ("in_category", "transfer")),
                   key=lambda t: (t["plugin"].get("fit_rank") or 99, str(t.get("name"))))
    used = [t["id"] for t in hooks if t["plugin"]["use"] == "in_category"]
    transfer = [t["id"] for t in hooks if t["plugin"]["use"] == "transfer"]
    rows = {t["id"]: t for t in hooks}
    return _facts([(_w(ctx, "fact.subcategories"), len(cmap.get("queries") or [])),
                   (_w(ctx, "fact.kept"), len(cmap.get("kept") or [])),
                   (_w(ctx, "fact.dropped"), len(cmap.get("dropped") or [])),
                   (_w(ctx, "fact.hooks_used", category=_category(ctx)), _names(used, rows)),
                   (_w(ctx, "fact.hooks_transfer"), _names(transfer, rows))], ctx.rel(path))


def _picks(ctx: Context) -> list[dict]:
    path = ctx.latest("03_wip", "picks", "json")
    picks = ctx.json(path)
    if not isinstance(picks, dict):
        return []
    rows = _growth(ctx)

    def ids(key: str) -> list:
        return [p.get("id") for p in picks.get(key) or [] if isinstance(p, dict)]
    return _facts([(_w(ctx, "fact.act_now"), _names(ids("act_now"), rows)),
                   (_w(ctx, "fact.still_rising"), _names(ids("still_rising"), rows)),
                   (_w(ctx, "fact.moves"), _names(ids("moves"), rows))], ctx.rel(path))


def _views(ctx: Context) -> list[dict]:
    views = [tx("report.view_" + research_config.PICK_OUTPUTS[o], ctx.lang) for o in _cfg(ctx).get("outputs") or []
             if o in research_config.PICK_OUTPUTS]
    return _facts([(_w(ctx, "fact.outputs"), ", ".join(views))], config.FILE)


def _schedule(ctx: Context) -> list[dict]:
    how = (state.load(ctx.run).schedule or {}).get("how")
    shown = ctx.t_or(W + "schedule." + str(how), how) if how else None
    return _facts([(_w(ctx, "fact.schedule"), shown)], "run.json")


COMPONENTS = {"G0": (_seeds,), "G1": (_map,), "G2": (_picks,), "G3": (_views,), "GS": (_schedule,)}


def outcome(ctx: Context, checkin: str, choice: object) -> str | None:
    """A decided choice in words (`accept` is "Accepted"), else None (shown as recorded)."""
    key = W + "choice." + str(choice)
    return ctx.t_or(key, choice) if choice is not None else None


def materials(ctx: Context, checkin: str) -> list[dict]:
    out: list[dict] = []
    for part in COMPONENTS.get(checkin, ()):
        out += part(ctx)
    return out
