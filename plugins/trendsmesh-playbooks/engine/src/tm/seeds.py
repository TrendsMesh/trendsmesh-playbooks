"""Seeds: picks one playbook hands on to another, `<workspace>/library/seeds.jsonl`.

    tm seeds list [--source pb4] [--valid-on D] [--workspace W] [--json]   the seeds, as the creative brief reads them

One JSON object per line, append-only: a row is never rewritten, and a row whose `seed_id` is in the
file already is not added again. A line that is not a JSON object is named, and nothing is added
until it is fixed or deleted (as `library/trend_calls.jsonl`, through `library.read_jsonl` and
`library.append_jsonl`).

A row (`seed/1`):

    {"schema": "seed/1", "seed_id": "<run>:<trend_id>", "source": "pb4", "run": "<run folder name>",
     "created": "YYYY-MM-DD", "category": "beauty", "sub_category": "nail art", "market": "US",
     "trend_id": "...", "kind": "topic_trend", "trend_name": "...", "bucket": "act_now",
     "band": "top 10%", "paid_level": "none|found|crowded|not_checkable|not_checked",
     "angle": "<the pick's how>", "risk": "<the pick's risk>", "valid_until": "YYYY-MM-DD",
     "report": {"slug": "...", "version": "..."} | null,
     "evidence": "runs/04-trend-research/<run>/02_research/videos/<trend_id>*.json"}

The keys of the PB4 to PB2 contract (both PLAYBOOK.md files, "Contracts with other playbooks") keep
their names: source to valid_until. The plugin adds `schema`, `seed_id`, `created` (the day the seed
was written), `market` (the run's config), `report` (the artifact this run's page was published to
at E2; null when the page was kept local, never an earlier run's version) and `evidence` (a glob,
relative to the workspace, of the run's saved videos of the trend).

    add       one row; False when its seed_id is there already
    rows      the readable rows, one per seed_id, of one source, still valid on a date
    from_run  E3 of a trend research run (`tm research seeds`): one seed per act now and still
              rising pick (after G2) of the picks file the latest page was built from, with that
              page's Ad Library summary (its manifest row names both; without a page, the latest
              of each); the run's own 04_final/seeds_vNN.json is written first, then the new rows
              are appended to the library
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from tm import (cli, library, manifest, page, paths, research_checks, research_growth, research_map, research_report, state,
                trend_spool, trends)
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

SCHEMA = "seed/1"
FILE = Path("library") / "seeds.jsonl"
PB4 = "pb4"
CONTRACT = ("source", "run", "category", "sub_category", "trend_id", "kind", "trend_name", "bucket", "band",
            "paid_level", "angle", "risk", "valid_until")
REQUIRED = ("schema", "seed_id", "source", "run", "created", "category", "sub_category", "market", "trend_id", "kind",
            "trend_name", "bucket", "band", "paid_level", "angle", "risk", "valid_until", "report", "evidence")
NOT_CHECKED = "not_checked"
PAID_LEVELS = (*research_checks.LEVELS, NOT_CHECKED)
STEM = "seeds"
SOURCE = "tm research seeds"


class DamagedSeeds(Stop):
    """library/seeds.jsonl has lines that are not JSON rows: nothing is added until they are fixed."""


def _file(workspace: Path) -> Path:
    return Path(workspace) / FILE


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def check(row: object) -> None:
    """Refuses (ValueError, naming the field) a row that breaks seed/1."""
    if not isinstance(row, dict):
        raise ValueError("A seed must be a JSON object.")
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        raise ValueError(f"The seed lacks: {', '.join(missing)}.")
    if row["schema"] != SCHEMA:
        raise ValueError(f"The seed's schema is {row['schema']!r}; this plugin writes {SCHEMA}.")
    if not (isinstance(row["seed_id"], str) and row["seed_id"].strip()):
        raise ValueError("The seed needs its seed_id, <run>:<trend_id>.")
    for key in ("created", "valid_until"):
        if _date(row[key]) is None:
            raise ValueError(f"The seed's {key} must be a date, YYYY-MM-DD, not {row[key]!r}.")
    if row["paid_level"] not in PAID_LEVELS:
        raise ValueError(f"The seed's paid_level is {row['paid_level']!r}; use one of {', '.join(PAID_LEVELS)}.")
    for key in ("bucket", "evidence"):
        if not isinstance(row[key], str):
            raise ValueError(f"The seed's {key} must be a string, not {row[key]!r}.")
    report = row["report"]
    if report is not None and not (isinstance(report, dict) and set(report) == {"slug", "version"}
                                   and all(isinstance(v, str) and v.strip() for v in report.values())):
        raise ValueError(f"The seed's report is null or {{slug, version}} of the published page, not {report!r}.")


def _pending(workspace: Path, new: list[dict]) -> tuple[list[dict], list[dict]]:
    """(the rows to append, the rows whose seed_id is there already). Refuses (DamagedSeeds) while
    the library has damaged lines."""
    existing, damaged = library.read_jsonl(_file(workspace))
    if damaged:
        raise DamagedSeeds(f"{FILE.as_posix()} has damaged lines (not JSON rows): {', '.join(map(str, damaged))}. No "
                           "seed is added while they are there, so a seed is never written twice. Fix or delete those "
                           "lines, then run this again; the run continues from the same place.")
    present = {r.get("seed_id") for r in existing}
    fresh, already = [], []
    for row in new:
        (already if row["seed_id"] in present else fresh).append(row)
        present.add(row["seed_id"])
    return fresh, already


def add(workspace: Path, row: dict) -> bool:
    """Append one seed; False (nothing written) when its seed_id is in the library already. Refuses a
    row that breaks seed/1 (ValueError) and a library with damaged lines (DamagedSeeds)."""
    check(row)
    fresh, _ = _pending(workspace, [row])
    library.append_jsonl(_file(workspace), fresh)
    return bool(fresh)


def _kept(read: list[dict], source: str | None, valid_on: date | None) -> list[dict]:
    seen: set = set()
    out = []
    for r in read:                                   # one seed per seed_id: the first written
        if r.get("seed_id") in seen:
            continue
        seen.add(r.get("seed_id"))
        out.append(r)
    if source is not None:
        out = [r for r in out if r.get("source") == source]
    if valid_on is not None:
        out = [r for r in out if (_date(r.get("valid_until")) or date.min) >= valid_on]
    return out


def rows(workspace: Path, *, source: str | None = None, valid_on: date | None = None) -> list[dict]:
    """The readable seeds, in the order written, one per seed_id (the first written): of `source`
    only when given, and only those valid through `valid_on` (valid_until on or after it) when given."""
    return _kept(library.read_jsonl(_file(workspace))[0], source, valid_on)


# --- E3: the picks of a trend research run --------------------------------------------------

def _paid_levels(path: Path | None) -> dict[str, str]:
    """Each trend's Ad Library level in the summary, as the page reads it; empty (every seed
    not_checked) without a summary or when it says the Ad Library was not checked (V22)."""
    summary = trends.read(path) if path else None
    if not isinstance(summary, dict) or summary.get("checked") is False:
        return {}
    return {c["trend_id"]: c["level"] for c in summary.get("checks") or []
            if isinstance(c, dict) and isinstance(c.get("trend_id"), str) and c.get("level") in research_checks.LEVELS}


def _page_inputs(run: RunFolder) -> tuple[Path | None, Path | None, bool]:
    """(picks, Ad Library summary, from the page): the files the latest page (04_final/report_vNN) was
    built from, by its manifest row, so the seeds say what the page says; without a built page, the
    latest picks and summary. Stops when the page's file is no longer in the run."""
    folder = page.latest_folder(run, research_report.PAGE)
    rel = folder.relative_to(run.path).as_posix() if folder else None
    built = [r for r in manifest.rows(run) if rel and r["file"] == rel and r["source"] == research_report.SOURCE]
    if not built:
        return (run.latest(research_checks.WIP, research_checks.PICKS_STEM, "json"),
                run.latest(trends.RESEARCH, research_report.PAID_STEM, "json"), False)
    try:
        params = json.loads(built[-1]["params"] or "{}")
    except ValueError:
        params = {}
    found = []
    for key, stage in (("picks", research_checks.WIP), ("paid", trends.RESEARCH)):
        name = params.get(key) if isinstance(params, dict) else None
        path = run.path / stage / name if isinstance(name, str) and name else None
        if key == "picks" and path is None:
            raise Stop(f"The manifest row of {rel} does not name its picks file, so the seeds cannot follow the page. "
                       f"Build the page again with tm research report, then run this again; {AGAIN}.")
        if path is not None and not path.is_file():
            raise Stop(f"{rel} was built from {name}, which is not in {stage}/ of this run, so the seeds cannot say what "
                       f"the page says. Build the page again from files in the run (tm research report), then run this "
                       f"again; {AGAIN}.")
        found.append(path)
    return found[0], found[1], True


def _picks(path: Path | None) -> dict:
    if path is None:
        raise Stop(f"This run has no picks yet ({research_checks.WIP}/{research_checks.PICKS_STEM}_vNN.json), so there "
                   f"is nothing to hand on. Write and check the picks (D3) first; {AGAIN}.")
    data = trends.read(path)
    if not isinstance(data, dict):
        raise Stop(f"{path.name} must hold one JSON object. Write the picks again and check them (tm research picks "
                   f"check), then run this again; {AGAIN}.")
    return data


def from_run(run: RunFolder, cfg: dict, *, today: date | None = None) -> dict:
    """E3: a seed for every act now and still rising pick of the page's picks (`_page_inputs`). Writes the run's
    04_final/seeds_vNN.json (every seed, which were added, which were there already) and a manifest
    row, then appends the new seeds to the library. Nothing is written when the library has damaged
    lines or a pick is not in the latest growth."""
    cfg = research_map.settings(cfg)
    picks_path, paid_path, from_page = _page_inputs(run)
    picks = _picks(picks_path)
    as_of = _date(picks.get("as_of"))
    if as_of is None:
        raise Stop(f"{picks_path.name} has no as_of date (YYYY-MM-DD): a seed's valid-until comes from it. Add it, "
                   f"check the picks again (tm research picks check), then run this again; {AGAIN}.")
    grown = {r["id"]: r for r in research_checks.growth(run)["trends"]}
    listed = [(b, p) for b in research_checks.PICKED for p in picks.get(b) or [] if isinstance(p, dict)]
    unknown = [str(p.get("id")) for _, p in listed if not (isinstance(p.get("id"), str) and p["id"] in grown)]
    if unknown:
        raise Stop(f"The picks name trends that are not in the latest growth: {', '.join(unknown)}. Check them with tm "
                   f"research picks check, fix the file, then run this again; {AGAIN}.")
    workspace = trend_spool.workspace_of(run)
    run_rel = run.path.resolve().relative_to(workspace).as_posix()
    name = run.path.resolve().name
    published = state.load(run).pages.get(research_report.PAGE)   # this run's own page only
    report = {"slug": published["slug"], "version": published["version"]} if published else None
    paid = _paid_levels(paid_path)
    created = (today or date.today()).isoformat()
    valid_until = (as_of + timedelta(days=cfg["picks"]["valid_days"])).isoformat()
    category = str(picks.get("category") or cfg["category"].get("phrase") or "").strip()
    market = str(cfg.get("market") or "").strip() or None
    out, seen = [], set()
    for bucket, p in listed:
        tid = p["id"]
        if tid in seen:                                  # a pick listed twice is one seed (its first bucket)
            continue
        seen.add(tid)
        t = grown[tid]
        out.append({"schema": SCHEMA, "seed_id": f"{name}:{tid}", "source": PB4, "run": name, "created": created,
                    "category": category, "sub_category": t.get("sub_category"), "market": market, "trend_id": tid,
                    "kind": t.get("kind"), "trend_name": t.get("name"), "bucket": bucket,
                    "band": (t.get("relative") or {}).get("band"), "paid_level": paid.get(tid, NOT_CHECKED),
                    "angle": p.get("how"), "risk": p.get("risk"), "valid_until": valid_until, "report": report,
                    "evidence": f"{run_rel}/{trends.RESEARCH}/videos/{tid}*.json"})
    for row in out:
        check(row)
    fresh, already = _pending(workspace, out)            # a damaged library stops here, before anything is written
    target = run.next_version(page.FINAL, STEM, "json")
    target.write_text(json.dumps({"picks": picks_path.name, "paid": paid_path.name if paid_path else None,
                                  "from_page": from_page, "library": FILE.as_posix(),
                                  "added": [r["seed_id"] for r in fresh], "already": [r["seed_id"] for r in already],
                                  "rows": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    rel = f"{page.FINAL}/{target.name}"
    manifest.record(run, rel, page.FINAL, SOURCE, params={"picks": picks_path.name,
                                                         "paid": paid_path.name if paid_path else None,
                                                         "added": len(fresh)})
    library.append_jsonl(_file(workspace), fresh)        # the run's own file first, then the library
    return {"json": rel, "file": FILE.as_posix(), "picks": picks_path.name, "paid": paid_path.name if paid_path else None,
            "from_page": from_page, "rows": out, "added": len(fresh), "already": len(already)}


# --- command line -----------------------------------------------------------------------------

def _line(r: dict) -> str:
    where = " / ".join(str(x) for x in (r.get("category"), r.get("sub_category")) if x)
    return (f"{r.get('seed_id')}  {r.get('trend_name')} ({research_growth.LABEL.get(r.get('bucket'), r.get('bucket'))}, "
            f"{r.get('band')}, paid {r.get('paid_level')}), {where}, {r.get('market')}, valid until "
            f"{r.get('valid_until')}")


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    ls = sub.add_parser("list", help=f"the seeds in {FILE.as_posix()}, for the creative brief")
    ls.add_argument("--source", help="one source only, e.g. pb4 (trend research)")
    ls.add_argument("--valid-on", help="YYYY-MM-DD: only the seeds still valid on that day")
    ls.add_argument("--workspace", help="default the current workspace")
    ls.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        workspace = Path(args.workspace) if args.workspace else paths.workspace()
        valid_on = date.fromisoformat(args.valid_on) if args.valid_on else None
        read, damaged = library.read_jsonl(_file(workspace))
        found = _kept(read, args.source, valid_on)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    lines = [_line(r) for r in found] or ["No seeds" + (f" from {args.source}" if args.source else "")
                                         + (f" valid on {valid_on.isoformat()}" if valid_on else "") + "."]
    if damaged:
        lines.append(f"Lines {', '.join(map(str, damaged))} of {FILE.as_posix()} are damaged (not JSON rows) and not "
                     "listed; no seed is added until they are fixed or deleted.")
    text = "\n".join(lines)
    cli.emit(args, {"status": "done", "seeds": found, "damaged": damaged, "message": text}, text)
    return 0


cli.register("seeds", _setup, _run)
