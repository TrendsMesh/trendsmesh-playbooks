"""The diagnosis report of a Refresh an ad run that ends at "Accept the diagnosis" (G1a `do_not_refresh`, issue #143).

    write(run) -> Path      04_final/diagnosis_report_vNN.md from templates/diagnosis_report_template.md
    finish(run) -> dict     the report, and the run page built again when the run has one
    language(run)           the language it is written in (i18n.PageLang)

Everything in it is read from the run's own files: run.json (the diagnosis, the decisions, the spend), the ranking
(01_base/winner_ranking_vNN.json), the diagnosis windows the agent took from it (03_wip/diagnosis_windows/) and the
structural check stored with the diagnosis. Nothing is retyped, so every figure is Meta's as the run read it. The
diagnosis keeps the ad it judged (its id, name and ranking numbers) and the two windows it was judged on (issue
#171), so the report names the ad and shows its numbers even when the G1 answer or a later ranking does not match.

The report is in the run's working language (issue #171): its words are the string table's `diagnosis.*` area
(data/i18n/en.yaml), and a language whose table lacks one of them gets the English report with a warning saying what
to translate (`i18n.page_lang`), never a silent English.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from string import Template

from tm import i18n, manifest, playbooks, state
from tm.runfolder import RunFolder

SOURCE = "tm decide G1a do_not_refresh"
AREA = "diagnosis"
_RATES = {"hook_rate", "middle_rate", "ctr", "conversion"}
_FIX = ("landing", "account", "auction", "unclear")   # a verdict that is not a creative problem: what to look at
_WHY = ("no_refresh", "unsupported", "too_little_data")   # why the run cannot refresh (flow._blocking's kinds)


def _template() -> Template:
    path = playbooks.skills_root() / playbooks.get(playbooks.REFRESH_AD).skill / "templates" / \
        "diagnosis_report_template.md"
    return Template(path.read_text(encoding="utf-8-sig").split("\n---\n", 1)[1].lstrip("\n"))


def language(run: RunFolder) -> i18n.PageLang:
    """The run's working language when its table has every `diagnosis.*` string, else English with a warning."""
    return i18n.page_lang(i18n.run_languages(run).working, AREA)


def _latest(run: RunFolder, folder: str, stem: str) -> Path | None:
    found = sorted((run.path / folder).glob(f"{stem}_v*.json"), key=lambda p: p.stem) \
        if (run.path / folder).is_dir() else []
    return found[-1] if found else None


def _json(path: Path | None) -> object:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _rel(run: RunFolder, path: Path | None) -> str:
    return path.relative_to(run.path).as_posix() if path else ""


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _money(v: object) -> str:
    return f"{v:,.2f}" if _num(v) else "?"


def _value(metric: str, v: object) -> str:
    if not _num(v):
        return "?"
    return f"{v * 100:.2f}%" if metric in _RATES else f"{v:,.2f}"


def _or(tr: i18n.Translator, key: str, default: object) -> str:
    return tr(key) if key in tr.en else str(default)


def _stage(tr: i18n.Translator, stage: object) -> str:
    return _or(tr, f"{AREA}.stage.{stage}", stage)


def _kept(d: dict | None) -> dict | None:
    """The ad as the diagnosis keeps it (r2.ad_of), when it does."""
    ad = (d or {}).get("ad")
    return ad if isinstance(ad, dict) and ad.get("id") else None


def _chosen(run: RunFolder, s: state.RunState, d: dict | None) -> tuple[str | None, dict | None, str]:
    """The ad's name (None when nothing names it), its ranking candidate and the ranking file: the ad the diagnosis
    keeps, else the one picked at G1, else the one ranked first. The ad is matched by its id, else by its name."""
    path = _latest(run, "01_base", "winner_ranking")
    data = _json(path)
    cands = [c for c in (data.get("candidates") or []) if isinstance(c, dict)] if isinstance(data, dict) else []
    kept = _kept(d) or {}
    picked = [x.get("choice") for x in s.decisions if x.get("checkin") == "G1"]
    ad = kept.get("id") or (picked[-1] if picked else None)
    found = None
    if ad and ad != "none":
        found = (next((c for c in cands if str(c.get("ad_id")) == str(ad)), None)
                 or next((c for c in cands if str(c.get("name") or "").strip().casefold()
                          == str(ad).strip().casefold()), None))
    if found is None and not picked and not kept and isinstance(data, dict) and data.get("ranking"):
        found = next((c for c in cands if c.get("ad_id") == data["ranking"][0]), None)
    name = (kept.get("name") or (found or {}).get("name") or kept.get("id") or (found or {}).get("ad_id")
            or (ad if ad and ad != "none" else None))
    return name, found, _rel(run, path)


def _window(run: RunFolder, which: str, d: dict | None, cand: dict | None, ranking: str) -> tuple[dict | None, str]:
    """The window the diagnosis was judged on (kept with it), else the file the agent took from the ranking, else the
    ranking candidate's own; with where it was read."""
    kept = ((d or {}).get("windows") or {}).get(which) if isinstance((d or {}).get("windows"), dict) else None
    if isinstance(kept, dict) and "start" in kept:
        return kept, _rel(run, _latest(run, "04_final", "diagnosis")) or "run.json"
    path = _latest(run, "03_wip/diagnosis_windows", which)
    data = _json(path)
    if isinstance(data, dict) and "start" in data:
        return data, _rel(run, path)
    w = (cand or {}).get(which)
    return (w, ranking) if isinstance(w, dict) else (None, "")


def _cpr(w: dict) -> object:
    if _num(w.get("cpr")):
        return w["cpr"]
    spend, results = w.get("spend"), w.get("results")
    return spend / results if _num(spend) and _num(results) and results else None


def _results(v: object) -> str:
    return f"{v:g}" if _num(v) else "?"


def _checked(tr: i18n.Translator, run: RunFolder, s: state.RunState, d: dict | None) -> str:
    name, cand, ranking = _chosen(run, s, d)
    kept = _kept(d) or {}
    ad_id = kept.get("id") or (cand or {}).get("ad_id")
    name = name or tr(f"{AREA}.unnamed_ad")
    lines = ["- " + (tr(f"{AREA}.ad_id", name=name, id=ad_id) if ad_id and str(ad_id) != name
                     else tr(f"{AREA}.ad", name=name))]
    if d is None:
        lines.append("- " + tr(f"{AREA}.every_ad", ranking=ranking or tr(f"{AREA}.the_ranking")))
        return "\n".join(lines)
    ranked = kept if kept.get("ranking") else ({**cand, "ranking": ranking} if cand else {})
    value = ranked.get("value_to_recover")
    if ranked.get("rank") is not None:
        lines.append("- " + tr(f"{AREA}.ranked", ranking=ranked["ranking"], rank=ranked["rank"], value=_money(value)))
    elif _num(value):
        lines.append("- " + tr(f"{AREA}.in_ranking", ranking=ranked["ranking"], value=_money(value)))
    for which in ("peak", "latest"):
        w, src = _window(run, which, d, cand, ranking)
        if w:
            lines.append("- " + tr(f"{AREA}.window", label=tr(f"{AREA}.{which}"), start=w.get("start"),
                                   stop=w.get("stop"), spend=_money(w.get("spend")), results=_results(w.get("results")),
                                   cpr=_money(_cpr(w)), source=src))
    ratio = (d.get("account_check") or {}).get("account_ratio")
    if _num(ratio):
        lines.append("- " + tr(f"{AREA}.account_ratio", ratio=f"{ratio:.2f}"))
    return "\n".join(lines)


def _row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def _shows(tr: i18n.Translator, d: dict | None, why: str) -> str:
    if d is None:
        return tr(f"{AREA}.no_winner")
    best, latest = tr(f"{AREA}.col_best"), tr(f"{AREA}.col_latest")
    parts = []
    rows = [(k, v) for k, v in (d.get("evidence") or {}).items() if isinstance(v, (list, tuple)) and len(v) == 2]
    if rows:
        parts += [_row(tr(f"{AREA}.col_funnel"), best, latest), "|---|---|---|"]
        parts += [_row(_or(tr, f"{AREA}.metric.{k}", k), _value(k, v[0]), _value(k, v[1])) for k, v in rows]
        parts.append("")
    lad = d.get("ladder") or {}
    if isinstance(lad.get("peak"), dict) and isinstance(lad.get("latest"), dict):
        dropped = set(lad.get("dropped") or [])
        parts += [_row(tr(f"{AREA}.col_ladder"), best, latest), "|---|---|---|"]
        parts += [_row(tr(f"{AREA}.dropped", step=k) if k in dropped else str(k), _value("ctr", lad["peak"].get(k)),
                       _value("ctr", lad["latest"].get(k))) for k in lad["peak"]]
        parts.append("")
    found = d.get("structural")
    if isinstance(found, dict):
        if found.get("structural"):
            seg = found.get("segment_s") or []
            at = tr(f"{AREA}.structural_at", start=f"{seg[0]:g}", stop=f"{seg[1]:g}") if len(seg) == 2 else ""
            parts.append("- " + tr(f"{AREA}.structural_weak", step=found.get("step"), at=at))
        else:
            parts.append("- " + tr(f"{AREA}.structural_none"))
    else:
        parts.append("- " + tr(f"{AREA}.structural_not_run"))
    parts.append("- " + tr(f"{AREA}.verdict", stage=_stage(tr, d.get("stage")), why=why))
    seen = [_stage(tr, x) for x in d.get("also_seen") or []]
    if seen:
        parts.append("- " + tr(f"{AREA}.also_seen", stages=", ".join(seen)))
    return "\n".join(parts)


def _why(tr: i18n.Translator, block) -> str:
    """Why the run did not refresh, in the report's language (the kind of `flow._blocking`'s answer)."""
    kind = getattr(block, "kind", None)
    if kind == "too_little_data":
        from tm import r1   # a leaf: it imports nothing of the flow
        return tr(f"{AREA}.why.too_little_data", n=r1.WinnerCfg().min_results)
    return tr(f"{AREA}.why.{kind}") if kind in _WHY else tr(f"{AREA}.why.declined")


def _fix(tr: i18n.Translator, d: dict | None, s: state.RunState, blocked: bool) -> str:
    if d is None:
        return tr(f"{AREA}.fix.nothing")
    stage = d.get("stage")
    if not blocked:   # a refresh the plugin could make, declined by the user
        return tr(f"{AREA}.fix.declined", stage=_stage(tr, d.get("target_stage") or stage))
    if d.get("too_little_data"):
        return tr(f"{AREA}.fix.too_little_data")
    if stage in _FIX:
        return tr(f"{AREA}.fix.{stage}")
    material = _or(tr, f"{AREA}.material.{s.material}", tr(f"{AREA}.material.unknown")) if s.material \
        else tr(f"{AREA}.material.unknown")
    return tr(f"{AREA}.fix.unsupported", stage=_stage(tr, stage), material=material)


def _spent(tr: i18n.Translator, s: state.RunState) -> str:
    spent = {k: v for k, v in s.spend.items() if v}
    if not spent:
        return tr(f"{AREA}.spent_nothing")
    return tr(f"{AREA}.spent", amounts=", ".join(tr(f"{AREA}.spent_item", amount=f"{v:g}", kind=k)
                                                 for k, v in spent.items()))


def write(run: RunFolder) -> Path:
    """Write the report as the next 04_final/diagnosis_report_vNN.md, record it, and return its path."""
    from tm import flow   # flow calls this module when G1a ends the run
    s = state.load(run)
    d = s.diagnosis if isinstance(s.diagnosis, dict) else None
    tr = i18n.translator(language(run).lang)
    block = flow._blocking(s)
    name, _, _ = _chosen(run, s, d)
    h = lambda key: tr(f"{AREA}.heading_{key}")   # noqa: E731
    text = _template().substitute(
        title=tr(f"{AREA}.title", ad=name or tr(f"{AREA}.unnamed_ad")),
        written=tr(f"{AREA}.written", when=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")),
        heading_checked=h("checked"), heading_shows=h("shows"), heading_fix=h("fix"), heading_spent=h("spent"),
        checked=_checked(tr, run, s, d), shows=_shows(tr, d, _why(tr, block)), fix=_fix(tr, d, s, block is not None),
        spent=_spent(tr, s))
    target = run.next_version("04_final", "diagnosis_report", "md")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    manifest.record(run, f"04_final/{target.name}", "04_final", SOURCE)
    return target


def finish(run: RunFolder) -> dict:
    """The report, then the run page built once more (when the run has one), with G1a settled and its "Done" stage.
    The page is built as its last build was (local or to publish); the agent publishes it to the same URL. `warning`
    when the report is in English because the working language's table lacks some of its strings."""
    from tm import page, run_page   # the run page imports the flow, which calls this
    report = write(run)
    out: dict = {"report": f"04_final/{report.name}", "page": None}
    lang = language(run)
    if lang.warning:
        out["warning"] = (f"The diagnosis report is written in English: {len(lang.missing)} of its texts have no "
                          f"{i18n.name(lang.wanted)} translation yet. Tell the user what it says in their language. "
                          f"Translate them once for the next runs: tm i18n export --lang {lang.wanted} --out "
                          f"i18n_{lang.wanted}.yaml, translate each string in that file, then tm i18n import --lang "
                          f"{lang.wanted} i18n_{lang.wanted}.yaml.")
    last = page.latest_folder(run, run_page.PAGE)
    if last is not None:
        built = _json(last / run_page.BUILD_FILE)
        local = bool(built.get("local")) if isinstance(built, dict) else False
        result = run_page.build(run, local=local)
        out["page"] = {"folder": result["folder"], "index": result["index"], "local": local,
                       **({"artifact": result["artifact"]} if not local else {})}
    return out
