"""`tm research …`: the tools of playbook 04 "Trend research", on a trend research run.

    tm research search-status --run RUN [--json]                      TR1: relevant counts, split, depth,
                                                                      what is still to search
    tm research map --run RUN --split FILE [--review FILE] [--json]   TR1: the category map
    tm research map-change --run RUN [--json]                         V26: how much of the map is new
    tm research hook-fit --run RUN --file F [--json]                  TR1: the hooks ranked by fit, the shortlist
    tm research hooks --run RUN --terms "a,b,..." [--json]            TR1: the shortlist's category videos
    tm research growth --run RUN [--as-of D] [--stem S] [--json]      TR2-TR4: growth, stages, snapshot
    tm research backtest --run RUN --as-of D [--horizon N] [--json]   TR3 calibration: stages then, outcome after
    tm research previous --run RUN [--json]                           A2: the previous run's files into 00_raw
    tm research rebuild-previous --run RUN --as-of D [--json]         V24: the previous week rebuilt
    tm research fetch-plan --run RUN [--json]                         TR8: which videos to fetch again
    tm research reuse --run RUN [--json]                              TR8: copy the others from the previous run
    tm research digest --run RUN [--prev F] [--json]                  TR8, TR9: the digest and the call check
    tm research calls [--category C] [--include-rebuilt] [--workspace W] [--json]   TR9: hit rate per call
    tm research evidence --run RUN --trend ID [--top 5] [--json]      D1: the top videos of a trend, to read
    tm research paid check --run RUN --file F [--json]                TR7: the agent's Ad Library reading
    tm research picks check --run RUN --file F [--json]               TR3-TR6: the agent's picks
    tm research report --run RUN --picks F [--paid F] [--prev-snapshot F] [--backtest F ...] [--json]
                                                                      TR10: the page, 04_final/report_vNN/
    tm research seeds --run RUN [--json]                              E3: the picks as seeds for the creative
                                                                      brief, library/seeds.jsonl
    tm research schedule --run RUN --how desktop_task|by_hand [--id ID --cron C] [--json]
                                                                      GS, F5: how the next weekly run starts
                                                                      (the alias of tm schedule, tm.schedule)

Exit codes: 0 done, 2 stop (something to fix first), 1 error.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from tm import (cli, config, page, paths, playbooks, research_checks, research_digest, research_growth, research_map,
                research_report, schedule, seeds, state)
from tm.runfolder import ReadOnlyError, RunFolder
from tm.stops import AGAIN, Stop


def _open_run(args: argparse.Namespace) -> RunFolder:
    """The run; refuses a run of another playbook."""
    run = RunFolder.open(Path(args.run))
    pb = state.load(run).playbook
    if pb != playbooks.TREND_RESEARCH:
        theirs = next((p.name for p in playbooks.all_playbooks() if p.id == pb), pb)
        raise ValueError(f"{run.path.resolve().name} is a run of {theirs}; tm research works on runs of "
                         f"{playbooks.get(playbooks.TREND_RESEARCH).name}.")
    return run


def _open(args: argparse.Namespace) -> tuple[RunFolder, dict]:
    """The run and its config; refuses a run of another playbook."""
    run = _open_run(args)
    return run, research_map.settings(config.load(run))


def _search_status(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    rows = research_map.search_status(run, cfg)
    problems = research_map.search_problems(run, cfg)
    pending = research_map.to_search(run, cfg)
    max_depth = cfg["trends"]["max_split_depth"]
    lines = []
    for r in rows:
        if not r["split"]:
            flag = "ok"
        elif r["depth"] is not None and r["depth"] >= max_depth:
            flag = f"thin leaf at depth {r['depth']}: not split again"
        else:
            flag = "SPLIT"
        depth = "?" if r["depth"] is None else r["depth"]
        lines.append(f"{r['query']!r:32} results {r['results']:3}  relevant>={cfg['trends']['min_match']:g}: "
                     f"{r['relevant']:3}  depth {depth}  [{flag}]")
    if pending:
        lines.append(f"Still to search: {', '.join(map(repr, pending))}.")
    elif not rows:
        lines.append("No TrendsMesh search is saved yet. Search the category phrase with collection on "
                     "(tm trends collect on), then check again.")
    payload = {"status": "done", "searches": rows, "to_search": pending, "problems": problems}
    if problems:
        payload["status"] = "stop"
        lines.append(" ".join(problems) + f" Fix the split file, then check again; {AGAIN}.")
    payload["message"] = "\n".join(lines)
    cli.emit(args, payload, payload["message"])
    return 2 if problems else 0


def _map(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    split = _json_file(run, args.split)
    review = _json_file(run, args.review) if args.review else None
    m = research_map.build(run, split, review, cfg)
    path = run.latest("02_research", research_map.STEM, "json")
    rel = path.relative_to(run.path).as_posix()
    payload = {"status": "done", "json": rel, "md": rel[:-len(".json")] + ".md", "kept": len(m["kept"]),
               "dropped": len(m["dropped"]), "below_threshold": m["below_threshold"],
               "weak_match": len(m["weak_match"])}
    text = (f"Wrote {payload['json']} and {payload['md']}: kept {payload['kept']}, dropped {payload['dropped']}, "
            f"below the match threshold everywhere {payload['below_threshold']}.")
    if m["weak_match"]:
        text += (f" The map stayed thin after the last split, so the {len(m['weak_match'])} closest trends are "
                 f"listed as \"{research_map.WEAK}\".")
    payload["message"] = text
    cli.emit(args, payload, text)
    return 0


def _map_change(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    change = research_map.map_change(run, cfg)
    if change["new_share"] is None:
        text = "There is no previous category map, so nothing changed a lot."
    else:
        text = (f"{change['new_share']:.0%} of the mapped trends are new since the previous run"
                + (f"; new groups: {', '.join(change['new_groups'])}" if change["new_groups"] else "")
                + (". The map changed a lot (V26): show it at G1 again." if change["changed_a_lot"]
                   else ". The map did not change a lot."))
    cli.emit(args, {"status": "done", **change, "message": text}, text)
    return 0


def _rel(run: RunFolder, path: Path) -> str:
    return path.relative_to(run.path).as_posix()


def _hook_fit(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    data = _json_file(run, args.file)
    problems = research_growth.check_hook_fit(run, data)
    if problems:
        return _checked(args, problems, "")
    given = Path(args.file.strip())
    fit_file = given.as_posix() if (run.path / given).is_file() else None
    path = research_growth.hook_fit(run, data, cfg, fit_file=fit_file)
    out = json.loads(path.read_text(encoding="utf-8"))
    ids = [r["id"] for r in out["shortlist"]]
    scored = len(out["shortlist"]) + len(out["not_shortlisted"]) + len(out["contradicted"])
    lines = [f"Wrote {_rel(run, path)}: the {len(ids)} best-fitting of {scored} hooks (fit 1-5, Creative brief's "
             "criteria). Fetch only these hooks' videos (tm research fetch-plan lists them):"]
    lines += [f"  {r['rank']:>2}. {(r['name'] or '')[:40]:40} {r['fit']}" for r in out["shortlist"]]
    cli.emit(args, {"status": "done", "json": _rel(run, path), "shortlist": ids, "scored": scored,
                    "message": "\n".join(lines)}, "\n".join(lines))
    return 0


def _hooks(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    path = research_growth.hooks(run, args.terms.split(","), cfg)
    out = json.loads(path.read_text(encoding="utf-8"))
    candidates = research_growth.candidates_of(path)
    used = [r for r in out["kept"] if r["plugin"]["in_category"]]
    payload = {"status": "done", "json": _rel(run, path), "candidates": _rel(run, candidates),
               "kept": len(out["kept"]), "in_category": len(used), "transfer": len(out["kept"]) - len(used),
               "checked": len(out["kept"]) + len(out["not_shortlisted"])}
    lines = [f"Wrote {payload['json']} and {payload['candidates']}: the {payload['kept']} shortlisted hooks, by fit; "
             f"{payload['in_category']} already used in the category, {payload['transfer']} a transfer (no category "
             "video yet). Fit, then category videos / videos checked:"]
    lines += [f"  {r['name'][:40]:40} {r['plugin']['fit']}  {r['category_videos']}/{r['videos_checked']}"
              f"{'' if r['plugin']['in_category'] else '  transfer'}" for r in out["kept"]]
    payload["message"] = "\n".join(lines)
    cli.emit(args, payload, "\n".join(lines))
    return 0


def _growth(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    as_of = date.fromisoformat(args.as_of or state.load(run).created)
    path = research_growth.compute(run, as_of, cfg, stem=args.stem)
    out = json.loads(path.read_text(encoding="utf-8"))
    snapshot = research_growth.snapshot_of(path, args.stem)
    counts = {b: sum(r["bucket"] == b for r in out["trends"]) for b in research_growth.BUCKETS}
    payload = {"status": "done", "json": _rel(run, path), "md": _rel(run, path.with_suffix(".md")),
               "snapshot": _rel(run, snapshot), "as_of": out["params"]["as_of"], "ref": out["params"]["ref"],
               "buckets": counts, "category": out["params"]["category"],
               "no_creator_data": out.get("plugin", {}).get("no_creator_data", [])}
    payload["message"] = (f"Wrote {payload['json']}, {payload['md']} and {payload['snapshot']} (as of {payload['as_of']}, "
                          f"reference {payload['ref']}): " + ", ".join(f"{research_growth.LABEL[b].lower()} {n}"
                                                                      for b, n in counts.items()) + ".")
    if payload["no_creator_data"]:
        payload["message"] += (f" {len(payload['no_creator_data'])} hook candidates have no creator data, so they count "
                               "as 0 new creators in the hooks ranking (tell the TrendsMesh team): "
                               + ", ".join(payload["no_creator_data"]) + ".")
    cli.emit(args, payload, payload["message"])
    return 0


def _backtest(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    path = research_growth.backtest(run, date.fromisoformat(args.as_of), cfg, horizon=args.horizon)
    out = json.loads(path.read_text(encoding="utf-8"))
    payload = {"status": "done", "json": _rel(run, path), "md": _rel(run, path.with_suffix(".md")),
               "as_of": out["as_of"], "ref": out["ref"], "horizon": out["horizon"], "summary": out["summary"]}
    lines = [f"Wrote {payload['json']} and {payload['md']}: stages as of {out['ref']} (the videos known then), new "
             f"creators in the next {out['horizon']} days:"]
    for b, n in out["summary"].items():
        if n["n"]:
            lines.append(f"  {research_growth.LABEL[b]:14} {n['n']:3} trends, {n['share_with_new_creators']:.0%} gained a "
                         f"creator, median {n['median_new']} new")
        else:
            lines.append(f"  {research_growth.LABEL[b]:14}   0 trends")
    payload["message"] = lines[0]
    cli.emit(args, payload, "\n".join(lines))
    return 0


def _previous_run(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    got = research_digest.load_previous(run)
    if got["previous_run"] is None:
        text = ("This run follows no earlier run, so there is no previous snapshot to compare with. A weekly run "
                "starts with tm run new --after <last run>.")
        cli.emit(args, {"status": "done", **got, "copied": [], "message": text}, text)
        return 0
    name = Path(got["previous_run"]).name
    parts = []
    if got["copied"]:
        parts.append(f"Copied {', '.join(got['copied'])} from {name}.")
    if got["already"]:
        parts.append(f"{', '.join(got['already'])} {'was' if len(got['already']) == 1 else 'were'} in 00_raw already "
                     "and stay as they are (00_raw is never changed).")
    if got["missing"]:
        parts.append(f"{name} has nothing to copy for {', '.join(got['missing'])}.")
    if not got["copied"]:
        parts.append("Nothing was copied this time.")
    text = " ".join(parts)
    if got["snapshot"] is None:
        text += (f" {name} has no snapshot (its growth step never ran): rebuild the previous week from the "
                 "evidence dates with tm research rebuild-previous --as-of <its date> (V24).")
    page = got["page"]
    text += (f" Its page is published at {page.get('url') or page['slug']}: this week's page goes to the same link."
             if page else " No page was published along the previous runs, so this week's page starts a new one.")
    cli.emit(args, {"status": "done", **got, "message": text}, text)
    return 0


def _rebuild_previous(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    as_of = date.fromisoformat(args.as_of)
    path = research_digest.rebuild_previous(run, as_of, cfg)
    text = (f"Wrote {_rel(run, path)}, the state as of {as_of.isoformat()} rebuilt from the evidence dates and "
            "marked rebuilt. The digest uses it when 00_raw/prev_snapshot.json is missing; say on the page that "
            "last week is rebuilt.")
    cli.emit(args, {"status": "done", "snapshot": _rel(run, path), "as_of": as_of.isoformat(), "message": text}, text)
    return 0


def _fetch_plan(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    plan = research_digest.fetch_plan(run, cfg)
    n = plan["minutes_estimate"]
    text = (f"Fetch the videos of {len(plan['fetch'])} trends (every page, about {plan['calls_estimate']} "
            f"get_trend_videos calls, about {n} minute{'' if n == 1 else 's'}: tell the user before a fetch of "
            "minutes)")
    if plan["reuse"]:
        text += (f"; copy the {len(plan['reuse'])} not updated since {plan['since']} from "
                 f"{Path(plan['previous_run']).name} with tm research reuse")
    text += f"; {plan['note']}." if plan["note"] else "."
    if plan["fetch"]:
        text += f"\nFetch: {', '.join(plan['fetch'])}"
    if plan["check"]:
        text += (f"\nGet the card of each of these {len(plan['check'])} trends of last week that are not in this "
                 f"week's map or hooks path (TrendsMesh get_trend), or the digest counts them as ended: {', '.join(plan['check'])}")
    cli.emit(args, {"status": "done", **plan, "message": text}, text)
    return 0


def _reuse(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    copied = [_rel(run, p) for p in research_digest.reuse(run)]
    text = (f"Copied {len(copied)} video pages from the previous run (not updated since the last run, TR8)."
            if copied else "Nothing to copy: no trend is to be reused, or its videos are here already.")
    cli.emit(args, {"status": "done", "copied": copied, "message": text}, text)
    return 0


def _digest(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    if args.prev:
        given = Path(args.prev)
        prev = run.path / given if not given.is_absolute() and (run.path / given).is_file() else given
    else:
        prev = research_digest.default_prev(run)
        if prev is None:
            raise Stop(
                "There is no previous snapshot to compare with: run tm research previous (a weekly run copies the "
                "last run's), or rebuild the previous week with tm research rebuild-previous --as-of <date>; "
                f"{AGAIN}.")
    path = research_digest.diff(run, prev, cfg)
    out = json.loads(path.read_text(encoding="utf-8"))
    plug = out["plugin"]
    counts = {k: len(out[k]) for k in ("new", "reidentified", "up", "down", "ended")}
    payload = {"status": "done", "json": _rel(run, path), "prev": plug["prev_snapshot"], **counts,
               "hit_rate": out["hit_rate"], "unknown_calls": plug["unknown_calls"], "calls_added": plug["calls_added"]}
    rates = []
    for b, (rate, checked) in out["hit_rate"].items():
        held = sum(c["held"] is True for c in out["calls"] if c["call"] == b)
        rates.append(f"{research_growth.LABEL[b].lower()} held {held} of {checked}"
                     + (f" ({rate:.0%})" if rate is not None else ""))
    unknown = [c for c in out["calls"] if c["held"] is None]
    text = (f"Wrote {payload['json']} against {plug['prev_snapshot']}: {counts['new']} new, {counts['reidentified']} "
            f"under a new id, {counts['up']} moved up, {counts['down']} moved down, {counts['ended']} ended. "
            f"Calls: {'; '.join(rates)}")
    text += (f"; {len(unknown)} unknown (TrendsMesh has no dated video with a creator for them): "
             + ", ".join(f"{c['name']!r} ({c['id']})" for c in unknown) + "." if unknown else ".")
    text += f" Added {plug['calls_added']} rows to {plug['calls_file']}."
    if plug["prev_rebuilt"]:
        text += (" The previous state is rebuilt from evidence dates, so \"new\" means no creators then and ended "
                 "trends are left out: say so on the page.")
    payload["message"] = text
    cli.emit(args, payload, text)
    return 0


def _calls(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace) if args.workspace else paths.workspace()
    summary = research_digest.calls_summary(workspace, args.category, include_rebuilt=args.include_rebuilt)
    lines = [f"{research_growth.LABEL.get(call, call)}: held {c['held']}, missed {c['missed']}, unknown {c['unknown']}"
             + (f", hit rate {c['hit_rate']:.0%}" if c["hit_rate"] is not None else "")
             for call, c in sorted(summary["calls"].items())]
    if not lines:
        lines.append("No call has been checked yet" + (f" for {args.category}." if args.category else "."))
    if summary["damaged"]:
        lines.append(f"Lines {', '.join(map(str, summary['damaged']))} of {research_digest.CALLS.as_posix()} are damaged "
                     "(not JSON rows) and not counted; no call is added until they are fixed or deleted.")
    cli.emit(args, {"status": "done", **summary, "message": "\n".join(lines)}, "\n".join(lines))
    return 0


def _evidence(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    got = research_checks.evidence(run, args.trend, top=args.top)
    if got["already"]:
        note = f"{got['name']} is in {got['file']} already (this step's dump); its videos again:"
    else:
        note = f"{'Added' if got['appended'] else 'Wrote'} {got['name']} to {got['file']}:"
    text = got.pop("text")
    cli.emit(args, {"status": "done", **got, "message": note}, f"{note}\n{text}")
    return 0


def _json_file(run: RunFolder, text: str) -> dict:
    """A JSON object given inline or as a file, relative to the run folder or to here."""
    given = Path(text.strip())
    if text.strip()[:1] not in ("{", "[") and not given.is_absolute() and (run.path / given).is_file():
        text = str(run.path / given)
    data = cli.json_arg(text)
    if not isinstance(data, dict):
        raise Stop(f"{text} must hold one JSON object. Write it again as one object, then run this again; {AGAIN}.")
    return data


def _checked(args: argparse.Namespace, problems: list[config.Problem], done: str, **extra) -> int:
    if not problems:
        cli.emit(args, {"status": "done", "problems": [], **extra, "message": done}, done)
        return 0
    text = ("\n".join(f"{p.field}: {p.what} {p.todo}" for p in problems)
            + f"\nFix the file, save it as a new version and check again; {AGAIN}.")
    cli.emit(args, {"status": "stop", "problems": [asdict(p) for p in problems], "message": text}, text)
    return 2


def _paid(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    summary = _json_file(run, args.file)
    problems = research_checks.check_paid(run, summary, cfg)
    if problems:
        return _checked(args, problems, "")
    if summary["checked"] is False:
        done = ("The Ad Library reading holds: the Ad Library was not checked (checked is false), so the paid view "
                "and the card verdicts say \"not checked\".")
    else:
        done = (f"The Ad Library reading holds: {len(summary['checks'])} checks, all in scope, each with its saved "
                "answer.")
    return _checked(args, problems, done)


def _picks(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    picks = _json_file(run, args.file)
    problems = research_checks.check_picks(run, picks, cfg)
    if problems:
        return _checked(args, problems, "")
    totals = research_checks.weighted_totals(picks, cfg)
    names = {r["id"]: r["name"] for r in research_checks.growth(run)["trends"]}
    done = (f"The picks hold: {len(picks.get('act_now') or [])} act now, {len(picks.get('still_rising') or [])} still "
            "rising, each scored. Weighted totals (TR5): "
            + ", ".join(f"{names[i]} {t:g}" for i, t in sorted(totals.items(), key=lambda kv: -kv[1])) + ".")
    return _checked(args, problems, done, totals=totals)


def _in_run(run: RunFolder, text: str | None) -> Path | None:
    """A file given relative to the run folder (if it is there) or to here."""
    if not text:
        return None
    given = Path(text)
    return run.path / given if not given.is_absolute() and (run.path / given).is_file() else given


def _report(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    folder = research_report.build(run, _in_run(run, args.picks), paid=_in_run(run, args.paid),
                                   prev_snapshot=_in_run(run, args.prev_snapshot),
                                   backtests=[_in_run(run, f) for f in args.backtest], cfg=cfg)
    listed = page.files(folder)
    rel = _rel(run, folder)
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    images = sum(f["as"].startswith("assets/") for f in listed)
    views = ", ".join(report["outputs"])
    if research_checks.DIGEST in cfg["outputs"] and "digest" not in report["outputs"]:
        views += "; no digest yet (first run), so the weekly digest view comes with the next run"
    text = (f"Built {rel}/index.html from {rel}/report.json: views {views}, "
            f"{len(report['act_now'])} act now and {len(report['still_rising'])} still rising picks, {images} evidence "
            "thumbnails. Publish the folder with the Artifact tool (tm page files --run RUN --page "
            f"{research_report.PAGE} gives its file_path and files), or give the local index.html.")
    payload = {"status": "done", "folder": rel, "files": listed}
    warning = research_report.page_language(run).warning     # issue #3: built in English, not the working language
    if warning:
        text += " " + warning
        payload["language_warning"] = warning
    cli.emit(args, {**payload, "message": text}, text)
    return 0


def _seeds(args: argparse.Namespace, run: RunFolder, cfg: dict) -> int:
    got = seeds.from_run(run, cfg)
    counts = {b: sum(r["bucket"] == b for r in got["rows"]) for b in research_checks.PICKED}
    if got["rows"]:
        text = (f"Wrote {got['json']}: {len(got['rows'])} seeds for the creative brief ({counts['act_now']} act now, "
                f"{counts['still_rising']} still rising) from {got['picks']}"
                + (" (the picks the page was built from)" if got["from_page"] else "")
                + f". Added {got['added']} to {got['file']}")
        text += (f"; {got['already']} were there already and stay as they are (a seed is never rewritten)."
                 if got["already"] else ".")
        text += " tm seeds list --source pb4 shows them."
    else:
        text = (f"Wrote {got['json']}: the picks have no act now or still rising pick, so there is no seed to hand on.")
    cli.emit(args, {"status": "done", **got, "message": text}, text)
    return 0


def _schedule(args: argparse.Namespace) -> int:
    """GS and F5: how next week's run starts, in run.json `schedule` (GS reads it in the next run). The alias of `tm
    schedule` (`tm.schedule`, which organic video's week run uses too), kept for trend research runs only."""
    return schedule.run_command(args, _open_run(args))


ACTIONS = {"search-status": _search_status, "map": _map, "map-change": _map_change, "hook-fit": _hook_fit,
           "hooks": _hooks,
           "growth": _growth, "backtest": _backtest, "previous": _previous_run, "rebuild-previous": _rebuild_previous,
           "fetch-plan": _fetch_plan, "reuse": _reuse, "digest": _digest, "evidence": _evidence, "paid": _paid,
           "picks": _picks, "report": _report, "seeds": _seeds}


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("search-status", help="per saved search: relevant results, split or not, depth (TR1)")
    s.add_argument("--run", required=True, help="the run folder")
    s.add_argument("--json", action="store_true")
    m = sub.add_parser("map", help="build the category map from the saved searches (TR1)")
    m.add_argument("--run", required=True, help="the run folder")
    m.add_argument("--split", required=True, help="the split file, 03_wip/split_vNN.json")
    m.add_argument("--review", help="the agent's review, 03_wip/map_review_vNN.json")
    m.add_argument("--json", action="store_true")
    c = sub.add_parser("map-change", help="how much of the map is new since the previous run (V26)")
    c.add_argument("--run", required=True, help="the run folder")
    c.add_argument("--json", action="store_true")
    f = sub.add_parser("hook-fit", help="rank the hook candidates by the agent's fit scores, keep the shortlist (TR1)")
    f.add_argument("--run", required=True, help="the run folder")
    f.add_argument("--file", required=True, help="the fit scores, 03_wip/hook_fit_vNN.json (or the JSON itself)")
    f.add_argument("--json", action="store_true")
    h = sub.add_parser("hooks", help="the hooks path: the shortlisted hooks, each with its category videos (TR1)")
    h.add_argument("--run", required=True, help="the run folder")
    h.add_argument("--terms", required=True, help="the category's words, comma-separated")
    h.add_argument("--json", action="store_true")
    g = sub.add_parser("growth", help="growth, stage and confidence of every trend, and the snapshot (TR2-TR4, TR8)")
    g.add_argument("--run", required=True, help="the run folder")
    g.add_argument("--as-of", help="YYYY-MM-DD; default the run's created date")
    g.add_argument("--stem", default=research_growth.STEM, help="the output name, default growth")
    g.add_argument("--json", action="store_true")
    b = sub.add_parser("backtest", help="stages as of a date, then the new creators after it (TR3 calibration)")
    b.add_argument("--run", required=True, help="the run folder")
    b.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    b.add_argument("--horizon", type=int, default=14, help="days after the reference date, default 14")
    b.add_argument("--json", action="store_true")
    for name, what in (("previous", "copy the previous run's snapshot, map and config into 00_raw (A2)"),
                       ("fetch-plan", "which trends' videos to fetch again, which to reuse (TR8)"),
                       ("reuse", "copy the reused videos from the previous run (TR8)")):
        q = sub.add_parser(name, help=what)
        q.add_argument("--run", required=True, help="the run folder")
        q.add_argument("--json", action="store_true")
    r = sub.add_parser("rebuild-previous", help="rebuild the previous week from evidence dates (V24)")
    r.add_argument("--run", required=True, help="the run folder")
    r.add_argument("--as-of", required=True, help="YYYY-MM-DD, the previous run's date")
    r.add_argument("--json", action="store_true")
    dg = sub.add_parser("digest", help="the digest and the call check against the previous snapshot (TR8, TR9)")
    dg.add_argument("--run", required=True, help="the run folder")
    dg.add_argument("--prev", help="the previous snapshot; default 00_raw/prev_snapshot.json, else the latest rebuilt one")
    dg.add_argument("--json", action="store_true")
    cl = sub.add_parser("calls", help="the hit rate of earlier calls, from library/trend_calls.jsonl (TR9)")
    cl.add_argument("--category", help="one category only")
    cl.add_argument("--workspace", help="default the current workspace")
    cl.add_argument("--include-rebuilt", action="store_true", help="count the calls of rebuilt previous weeks too")
    cl.add_argument("--json", action="store_true")
    ev = sub.add_parser("evidence", help="the top videos of one trend by views, written to the evidence dump (D1)")
    ev.add_argument("--run", required=True, help="the run folder")
    ev.add_argument("--trend", required=True, help="the trend id, from the latest growth")
    ev.add_argument("--top", type=int, default=5, help="how many videos, default 5")
    ev.add_argument("--json", action="store_true")
    for name, what, file in (("paid", "the Ad Library reading (TR7)", "02_research/ad_library_summary_vNN.json"),
                             ("picks", "the picks: moves, buckets, write-ups, scores (TR3-TR6)", "03_wip/picks_vNN.json")):
        w = sub.add_parser(name, help=f"check {what}")
        checks = w.add_subparsers(dest="what", required=True)
        c = checks.add_parser("check", help=f"check {what}")
        c.add_argument("--run", required=True, help="the run folder")
        c.add_argument("--file", required=True, help=f"the file, {file} (or the JSON itself)")
        c.add_argument("--json", action="store_true")
    _setup_report(sub)
    sd = sub.add_parser("seeds", help="the accepted picks as seeds for the creative brief, library/seeds.jsonl (E3)")
    sd.add_argument("--run", required=True, help="the run folder")
    sd.add_argument("--json", action="store_true")
    schedule.add_arguments(sub.add_parser("schedule", help="how next week's run starts: a desktop scheduled task or by "
                                                          "hand (GS, F5); the alias of tm schedule"))


def _setup_report(sub) -> None:
    rp = sub.add_parser("report", help="build the page: index.html and report.json in 04_final/report_vNN (TR10)")
    rp.add_argument("--run", required=True, help="the run folder")
    rp.add_argument("--picks", required=True, help="the picks, 03_wip/picks_vNN.json")
    rp.add_argument("--paid", help="the Ad Library summary; default the latest 02_research/ad_library_summary_vNN.json")
    rp.add_argument("--prev-snapshot", help="the previous snapshot, for the digest view; default the digest's own")
    rp.add_argument("--backtest", nargs="+", action="extend", default=[],
                    help="backtests to show under 'How sure are we', 03_wip/backtest_<date>_rule_v3_vNN.json")
    rp.add_argument("--json", action="store_true")


def _stop(args: argparse.Namespace, exc: Stop) -> int:
    message = str(exc)
    if isinstance(exc, research_growth.NoCreators):
        message += (" Run tm trends check-fields to see what the saved answers lack, and tell the TrendsMesh team; "
                    f"once fresh videos carry a creator, run growth again; {AGAIN}.")
    cli.emit(args, {"status": "stop", "message": message}, message)
    return 2


def _run(args: argparse.Namespace) -> int:
    try:
        if args.action == "calls":
            return _calls(args)
        if args.action == "schedule":
            return _schedule(args)
        run, cfg = _open(args)
        return ACTIONS[args.action](args, run, cfg)
    except Stop as exc:
        return _stop(args, exc)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))


cli.register("research", _setup, _run)
