"""The diagnosis report of a Refresh an ad run that ends at "Accept the diagnosis" (G1a `do_not_refresh`, issue #143).

    write(run) -> Path      04_final/diagnosis_report_vNN.md from templates/diagnosis_report_template.md
    finish(run) -> dict     the report, and the run page built again when the run has one

Everything in it is read from the run's own files: run.json (the diagnosis, the decisions, the spend), the ranking
(01_base/winner_ranking_vNN.json), the diagnosis windows the agent took from it (03_wip/diagnosis_windows/) and the
structural check stored with the diagnosis. Nothing is retyped, so every figure is Meta's as the run read it. The
report is in English (like every engine report); the agent tells the user what it says in their language.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from string import Template

from tm import changes, manifest, playbooks, state
from tm.runfolder import RunFolder

SOURCE = "tm decide G1a do_not_refresh"
_RATES = {"hook_rate", "middle_rate", "ctr", "conversion"}
_METRICS = {"hook_rate": "Share who watch the first quarter (hook rate)",
            "middle_rate": "Of those, share who watch to ThruPlay (middle)", "ctr": "Clicks per impression (CTR)",
            "conversion": "Results per click (conversion)", "frequency": "Frequency", "cpm": "Cost per 1,000 impressions"}
# What to look at for each verdict that is not a creative problem (or a creative problem the plugin can't refresh).
_FIX = {
    "landing": ("People still click the ad as often as before, and fewer of those who click buy, sign up or "
                "install: the drop is after the click. Check the landing page in the latest window: how fast it opens "
                "on a phone, the price and the offer against what the ad promises, stock and delivery times, the "
                "checkout or form and its payment step, and any change made to the page since the best window. The "
                "shop's own analytics show at which step the visitors drop."),
    "account": ("The whole account fell by about as much as this ad, so the cause is outside the video. Look at the "
                "account: budget or bid changes, the pixel and conversion tracking (are the events still counted), "
                "the season and the market, the offer and the prices, and new competitors in the Ad Library."),
    "auction": ("Only the cost of reach rose (CPM): the ad still works on the people who see it, and reaching them "
                "costs more. Look at the account: the season and the competition, the audience size and overlap "
                "between ad sets, and the bid strategy."),
    "unclear": ("No step of the funnel changed enough to name a cause, so a new creative would be a guess. Check that "
                "the conversion tracking is counting, then look again in a few weeks with more data."),
}
_NO_WINNER = ("No ad of the account is a fading winner: none spent its way to a better cost per result before and "
              "lost it since. Nothing needs a refresh now; check again when an ad's cost per result rises.")


def _template() -> Template:
    path = playbooks.skills_root() / playbooks.get(playbooks.REFRESH_AD).skill / "templates" / \
        "diagnosis_report_template.md"
    return Template(path.read_text(encoding="utf-8-sig").split("\n---\n", 1)[1].lstrip("\n"))


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


def _chosen(run: RunFolder, s: state.RunState) -> tuple[str, dict | None, str]:
    """The ad's name, its ranking candidate and the ranking file: the ad picked at G1, else the one ranked first."""
    path = _latest(run, "01_base", "winner_ranking")
    data = _json(path)
    cands = [c for c in (data.get("candidates") or []) if isinstance(c, dict)] if isinstance(data, dict) else []
    picked = [d.get("choice") for d in s.decisions if d.get("checkin") == "G1"]
    ad = picked[-1] if picked else None
    found = next((c for c in cands if c.get("ad_id") == ad), None) if ad else None
    if found is None and not picked and isinstance(data, dict) and data.get("ranking"):
        found = next((c for c in cands if c.get("ad_id") == data["ranking"][0]), None)
    name = (found or {}).get("name") or (found or {}).get("ad_id") or (ad if ad and ad != "none" else None)
    return name or "the ad chosen for the diagnosis", found, _rel(run, path)


def _window(run: RunFolder, which: str, cand: dict | None, ranking: str) -> tuple[dict | None, str]:
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


def _window_line(label: str, w: dict) -> str:
    return (f"- {label}: {w.get('start')} to {w.get('stop')}, spend {_money(w.get('spend'))}, "
            f"{w.get('results')} results, cost per result {_money(_cpr(w))}")


def _checked(run: RunFolder, s: state.RunState, d: dict | None) -> str:
    name, cand, ranking = _chosen(run, s)
    lines = [f"- The ad: {name}" + (f" (id {cand['ad_id']})" if cand and cand.get("ad_id") else "") + "."]
    if d is None:
        lines.append(f"- Every ad of the account over the ranking's history ({ranking or 'the ranking'}).")
        return "\n".join(lines)
    for which, label in (("peak", "The best window"), ("latest", "The latest window")):
        w, src = _window(run, which, cand, ranking)
        if w:
            lines.append(_window_line(label, w) + f" (source: {src}).")
    ratio = (d.get("account_check") or {}).get("account_ratio")
    if _num(ratio):
        lines.append(f"- The rest of the account: its results per spend in the latest window are {ratio:.2f} times "
                     "those of the best window (1 means flat).")
    return "\n".join(lines)


def _shows(d: dict | None, why: str) -> str:
    if d is None:
        return _NO_WINNER
    parts = []
    rows = [(k, v) for k, v in (d.get("evidence") or {}).items() if isinstance(v, (list, tuple)) and len(v) == 2]
    if rows:
        parts += ["| Funnel | Best window | Latest window |", "|---|---|---|"]
        parts += [f"| {_METRICS.get(k, k)} | {_value(k, v[0])} | {_value(k, v[1])} |" for k, v in rows]
        parts.append("")
    lad = d.get("ladder") or {}
    if isinstance(lad.get("peak"), dict) and isinstance(lad.get("latest"), dict):
        dropped = set(lad.get("dropped") or [])
        parts += ["| Who keeps watching (of those at the step before) | Best window | Latest window |", "|---|---|---|"]
        parts += [f"| {k}{' (dropped)' if k in dropped else ''} | {_value('ctr', lad['peak'].get(k))} | "
                  f"{_value('ctr', lad['latest'].get(k))} |" for k in lad["peak"]]
        parts.append("")
    found = d.get("structural")
    if isinstance(found, dict):
        if found.get("structural"):
            seg = found.get("segment_s") or []
            at = f" at {seg[0]:g} to {seg[1]:g} s" if len(seg) == 2 else ""
            parts.append(f"- The structural check (every upload of this video): the file is weakest at "
                         f"{found.get('step')}{at} in each one. That is an improvement for a later video, not why "
                         "this ad fades.")
        else:
            parts.append("- The structural check (every upload of this video): no step is weak by design.")
    else:
        parts.append("- The structural check was not run.")
    stage = d.get("stage")
    parts.append(f"- The verdict: {changes.STAGES.get(stage, stage)}. {why}")
    seen = [changes.STAGES.get(x, x) for x in d.get("also_seen") or []]
    if seen:
        parts.append(f"- Also seen in the data: {', '.join(seen)}.")
    return "\n".join(parts)


def _fix(d: dict | None, s: state.RunState, blocked: bool) -> str:
    if d is None:
        return "Nothing: no ad needs a refresh now."
    stage = d.get("stage")
    if not blocked:   # a refresh the plugin could make, declined by the user
        return (f"The diagnosis points at {changes.STAGES.get(d.get('target_stage') or stage, stage)}, which a "
                "refresh can change; the user decided not to refresh it now. A new run can make it.")
    if d.get("too_little_data"):
        return ("Wait until the ad has more results, or refresh it against the diagnosis in a new run, choosing "
                "the part of the ad yourself.")
    if stage in _FIX:
        return _FIX[stage]
    material = changes.MATERIAL_NAMES.get(s.material or "", "this kind of ad")
    return (f"The diagnosis points at {changes.STAGES.get(stage, stage)}, a part of the video, and refreshing it "
            f"isn't supported yet for {material}. Give the numbers above to whoever edits the ad (an editor or the "
            "creator) as the brief for a new version.")


def _spent(s: state.RunState) -> str:
    spent = {k: v for k, v in s.spend.items() if v}
    if not spent:
        return "Nothing: no money was spent in this run."
    return ("This run spent " + ", ".join(f"{v:g} ({k})" for k, v in spent.items())
            + " before the diagnosis ended it, and nothing more.")


def write(run: RunFolder) -> Path:
    """Write the report as the next 04_final/diagnosis_report_vNN.md, record it, and return its path."""
    from tm import flow   # flow calls this module when G1a ends the run
    s = state.load(run)
    d = s.diagnosis if isinstance(s.diagnosis, dict) else None
    block = flow._blocking(s)
    why = block.message if block else "The user decided not to refresh it."
    name, _, _ = _chosen(run, s)
    text = _template().substitute(ad=name, written=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
                                  checked=_checked(run, s, d), shows=_shows(d, why), fix=_fix(d, s, block is not None),
                                  spent=_spent(s))
    target = run.next_version("04_final", "diagnosis_report", "md")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    manifest.record(run, f"04_final/{target.name}", "04_final", SOURCE)
    return target


def finish(run: RunFolder) -> dict:
    """The report, then the run page built once more (when the run has one), with G1a settled and its "Done" stage.
    The page is built as its last build was (local or to publish); the agent publishes it to the same URL."""
    from tm import page, run_page   # the run page imports the flow, which calls this
    report = write(run)
    out: dict = {"report": f"04_final/{report.name}", "page": None}
    last = page.latest_folder(run, run_page.PAGE)
    if last is not None:
        built = _json(last / run_page.BUILD_FILE)
        local = bool(built.get("local")) if isinstance(built, dict) else False
        result = run_page.build(run, local=local)
        out["page"] = {"folder": result["folder"], "index": result["index"], "local": local,
                       **({"artifact": result["artifact"]} if not local else {})}
    return out
