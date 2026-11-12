"""`tm acceptance`: a human-run acceptance suite, with the agent as the operator
(`/trendsmesh-playbooks:acceptance <suite>`).

A suite is `data/acceptance/<suite>.yaml`: the playbook its cases run (`playbook`, its id or
skill; refresh-ad when absent), a budget (`ai_usd`, `voice_credits`; `{}` or absent when no case
needs one) and a list of cases, each `{id, title, proves, needs, steps, pass, judge}`. `start`
copies it into `<workspace>/acceptance/<YYYY-MM-DD>_<suite>/acceptance.json`, every case `todo`,
and makes a run folder of that playbook per case under that folder (`RunFolder.create`, so
`tm next` runs in it: `runs/<playbook id>/<YYYY-MM-DD>_<case>/`).
Everything needed to resume is in acceptance.json: a new session runs `start` again (it resumes,
never overwrites) or `next`. A suite is resumed until its report is written: while it has a case
to do, and then until a `report_vNN.md` exists.

`tm acceptance` keeps track of a suite budget (controller ruling R6) and stops spending cases once
it is used up: budgets are per run in the engine, so the spend is summed from each case run's
`run.json` (in an organic video suite also from the production runs started from a case run,
`_children`), and `next` says what is left per kind; the agent approves each case run's budget with
`tm budget approve` for no more than that.

A case that spends names the budget kinds it uses (`kinds`); `next` stops a case only when one
of its own kinds is over the suite budget, or when a case run's spend can't be read (then what is
left can't be told).

A case whose `judge` is set is the person's to judge (they watch or listen): `record pass|fail`
needs `--by person`. `blocked` needs a note saying what was missing. `report` writes
`report_vNN.md` from the playbook skill's `templates/acceptance_report_template.md`.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from string import Template

import yaml

from tm import __version__, cli, doctor, paths, playbooks, state
from tm.budget import _fmt
from tm.playbooks import REFRESH_AD
from tm.runfolder import RunFolder, slug

NEEDS = ("file", "key", "budget", "meta", "trendsmesh", "artifacts", "human_verdict")
RESULTS = ("pass", "fail", "blocked")
FILE = "acceptance.json"
CONTINUES = "The acceptance continues from the same place."
_FIELDS = ("id", "title", "proves", "needs", "steps", "pass", "judge")
_OPTIONAL = ("kinds",)  # the budget kinds a case spends: exactly when `needs` has budget


def _today() -> date:
    return date.today()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- the suite --------------------------------------------------------------------

def _suites() -> Path:
    return paths.bundled_data() / "acceptance"


def load_suite(name: str) -> dict:
    known = sorted(p.stem for p in _suites().glob("*.yaml"))
    if name not in known:
        raise ValueError(f"There is no acceptance suite {name!r}. Pick one of: {', '.join(known)}.")
    data = yaml.safe_load((_suites() / f"{name}.yaml").read_text(encoding="utf-8")) or {}
    try:
        data["playbook"] = playbooks.get(data.get("playbook") or REFRESH_AD).id
    except ValueError as exc:
        raise ValueError(f"{name}.yaml: {exc}") from None
    b = data.setdefault("budget", {})
    if not (isinstance(b, dict) and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in b.values())):
        raise ValueError(f"{name}.yaml: `budget` must map each budget kind to an amount.")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{name}.yaml: `cases` must be a list of cases.")
    if not b and any(isinstance(c, dict) and "budget" in (c.get("needs") or []) for c in cases):
        raise ValueError(f"{name}.yaml: a case needs a budget, so `budget` must map each budget "
                         "kind to an amount.")
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id") if isinstance(c, dict) else None
        if not cid or cid in seen or not set(_FIELDS) <= set(c) <= set(_FIELDS + _OPTIONAL):
            raise ValueError(f"{name}.yaml: each case needs a new id and exactly {', '.join(_FIELDS)}, "
                             f"plus `kinds` when it spends ({cid!r}).")
        seen.add(cid)
        if not (isinstance(c["needs"], list) and c["needs"] and set(c["needs"]) <= set(NEEDS)):
            raise ValueError(f"{name}.yaml {cid}: `needs` is a list of {', '.join(NEEDS)}.")
        if (c["judge"] is not None) != ("human_verdict" in c["needs"]):
            raise ValueError(f"{name}.yaml {cid}: a case the person judges has both `judge` and the "
                             "human_verdict need; a case proven by numbers has neither.")
        kinds = c.get("kinds")
        if ("budget" in c["needs"]) != ("kinds" in c):
            raise ValueError(f"{name}.yaml {cid}: `kinds` is given exactly when `needs` has budget.")
        if "kinds" in c and not (isinstance(kinds, list) and kinds and set(kinds) <= set(b)):
            raise ValueError(f"{name}.yaml {cid}: `kinds` lists the budget kinds the case spends, "
                             f"from: {', '.join(b)}.")
    return data


# --- the acceptance folder ----------------------------------------------------------

def _load(folder: Path) -> dict:
    return json.loads((folder / FILE).read_text(encoding="utf-8"))


def _save(folder: Path, data: dict) -> None:
    tmp = folder / f"{FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, folder / FILE)


def _started(workspace: Path, suite: str | None = None) -> list[Path]:
    """The workspace's acceptance folders that hold an acceptance.json, oldest first; the workspace
    itself when it is one (the `trends` cases are worked from inside their suite's folder)."""
    if (Path(workspace) / FILE).is_file():
        return [Path(workspace)] if suite is None or Path(workspace).resolve().name.endswith(f"_{suite}") else []
    base = Path(workspace) / "acceptance"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir()
                  if (p / FILE).is_file() and (suite is None or p.name.endswith(f"_{suite}")))


def _todo(data: dict) -> list[dict]:
    return [c for c in data["cases"] if c["status"] == "todo"]


def _reported(folder: Path) -> bool:
    return any(folder.glob("report_v*.md"))


def _resumable(found: list[Path]) -> Path | None:
    """The folder `start` resumes and `find` works in: the newest with a case still to do, else
    the newest with no report yet, else None (every suite is reported: `start` makes a new one).
    One rule for both, so they never pick different folders."""
    with_todo = [p for p in found if _todo(_load(p))]
    unreported = [p for p in found if not _reported(p)]
    return (with_todo or unreported or [None])[-1]


def find(workspace: Path, suite: str | None = None, folder: str | None = None) -> Path:
    """The acceptance folder to work in: `folder` if given, else the one `start` resumes, else
    (every suite is reported) the newest, so `next` says done and `report` can be written again."""
    if folder:
        path = Path(folder)
        if not (path / FILE).is_file():
            raise ValueError(f"{path} is not an acceptance folder (no {FILE}).")
        return path
    found = _started(workspace, suite)
    if not found:
        raise ValueError(f"No acceptance is started in {workspace} yet: run `tm acceptance start "
                         f"--suite {suite or '<suite>'}` first.")
    return _resumable(found) or found[-1]


def start(workspace: Path, suite: str, today: date, new: bool = False) -> tuple[Path, bool]:
    """Resume the suite's folder `find` picks (the newest with a case still to do, else the
    newest with no report yet), or create today's; never overwrite. With `new`, create today's
    even when an earlier one is unfinished (today's own is still resumed). Returns
    (folder, resumed)."""
    defn = load_suite(suite)
    folder = Path(workspace) / "acceptance" / f"{today:%Y-%m-%d}_{slug(suite)}"
    found = _started(workspace, suite)
    if not new:
        pick = _resumable(found)
        if pick is not None:
            return pick, True
    if (folder / FILE).is_file():
        return folder, True
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    playbook = defn["playbook"]
    for c in defn["cases"]:
        run_path = folder / "runs" / playbook / f"{today:%Y-%m-%d}_{slug(c['id'])}"
        # a start cut off before acceptance.json was written left valid run folders: keep them
        run = (RunFolder.open(run_path) if run_path.exists()
               else RunFolder.create(folder, c["id"], today, playbook=playbook))
        cases.append({**{k: c[k] for k in _FIELDS}, "kinds": c.get("kinds", []),
                      "run": run.path.relative_to(folder).as_posix(), "status": "todo", "by": None, "note": None, "evidence": [], "at": None,
                      "history": []})
    _save(folder, {"suite": suite, "playbook": playbook, "created": f"{today:%Y-%m-%d}",
                   "budget": defn["budget"], "approvals": [], "cases": cases})
    return folder, False


def _children(folder: Path, data: dict) -> tuple[dict[str, list[tuple[str, dict]]], list[str]]:
    """An organic video suite's production runs (PR E review I3): `tm organic start` makes them beside the case runs,
    naming the idea run (`organic.parent`) or the week run (`organic.week`) they came from. ({case id: [(run folder
    name, its spend)]}, the run folders whose run.json can't be read). A week case run's dropped slot whose folder is
    gone counts the spend its week run recorded (`organic.dropped[].spent`). Another playbook's suite has none."""
    if data.get("playbook") != playbooks.ORGANIC_VIDEO:
        return {}, []
    of = {c["run"]: c["id"] for c in data["cases"]}
    found: dict[str, list[tuple[str, dict]]] = {}
    unreadable: list[str] = []
    root = folder / "runs" / playbooks.get(playbooks.ORGANIC_VIDEO).id
    for run_json in sorted(root.glob("*/run.json")) if root.is_dir() else ():
        rel = run_json.parent.relative_to(folder).as_posix()
        if rel in of:
            continue
        try:
            raw = json.loads(run_json.read_text(encoding="utf-8"))
            mine = raw.get("organic") if isinstance(raw.get("organic"), dict) else {}
            spend = {k: float(v) for k, v in (raw.get("spend") or {}).items()}
        except (OSError, ValueError, TypeError, AttributeError):
            unreadable.append(rel)
            continue
        case = of.get(mine.get("parent")) or of.get(mine.get("week"))
        if case is not None:
            found.setdefault(case, []).append((run_json.parent.name, spend))
    for c in data["cases"]:                   # re-review N5: a dropped slot whose folder is gone, as its week recorded it
        try:
            own = json.loads((folder / c["run"] / "run.json").read_text(encoding="utf-8")).get("organic") or {}
        except (OSError, ValueError, AttributeError):
            continue                          # the case run itself is listed unreadable by `spent`
        dropped = (own.get("dropped") if isinstance(own, dict) else None) or []
        for entry in dropped if isinstance(dropped, list) else []:
            gone = isinstance(entry, dict) and isinstance(entry.get("path"), str) and entry["path"] \
                and not (folder / entry["path"] / "run.json").exists()
            if not gone:
                continue
            spent = entry.get("spent")
            if not isinstance(spent, (int, float)) or isinstance(spent, bool):
                unreadable.append(entry["path"])          # no record and no folder: never counted as zero
                continue
            found.setdefault(c["id"], []).append((entry.get("run") or Path(entry["path"]).name, {"ai_usd": float(spent)}))
    return found, unreadable


def spent(folder: Path, data: dict) -> tuple[dict, dict, list[str]]:
    """(the suite's total spend per kind, each case's spend, the cases whose spend can't be read),
    summed from the case runs' run.json and, in an organic video suite, their production runs'
    (`_children`: a case's spend is its run's and theirs; one that can't be read is listed by its
    folder). A run that can't be read is never counted as zero."""
    totals = {k: 0.0 for k in data["budget"]}
    per_case: dict[str, dict] = {}
    children, lost = _children(folder, data)
    unreadable: list[str] = []
    for c in data["cases"]:
        theirs = [s for _, s in children.get(c["id"], [])]
        try:
            own = {k: float(v) for k, v in state.load(RunFolder.open(folder / c["run"])).spend.items()}
        except (OSError, ValueError, TypeError, AttributeError):
            unreadable.append(c["id"])
            own = None
        spend: dict[str, float] = {}
        for one in [own or {}, *theirs]:       # an unreadable case run's children still count (a floor)
            for k, v in one.items():
                spend[k] = round(spend.get(k, 0.0) + v, 6)
        if own is not None:
            per_case[c["id"]] = {k: v for k, v in spend.items() if v}
        for k, v in spend.items():
            if v or k in totals:
                totals[k] = round(totals.get(k, 0.0) + v, 6)
    return totals, per_case, [*unreadable, *lost]


def budget_view(folder: Path, data: dict) -> dict:
    """What is spent and left of the suite budget. While a case run's spend can't be read
    (`unreadable`), `spent` is a floor and `left` is None per kind: it can't be told."""
    totals, _, unreadable = spent(folder, data)
    suite = data["budget"]
    return {"suite": suite, "spent": totals,
            "left": {k: None if unreadable else round(max(suite[k] - totals.get(k, 0.0), 0.0), 6)
                     for k in suite},
            "over": [k for k, v in totals.items() if v > suite.get(k, 0) + 1e-9],
            "unreadable": unreadable,
            "approved": bool(data.get("approvals"))}


def next_case(folder: Path) -> tuple[int, dict]:
    data = _load(folder)
    view = budget_view(folder, data)
    todo = _todo(data)
    if not todo:
        return 0, {"status": "done", "path": str(folder), "budget": view,
                   "message": "Every case has a result. Write the report: `tm acceptance report`."}
    case = dict(todo[0])
    case["run"] = str(folder / case["run"])
    out = {"status": "case", "path": str(folder), "case": case, "budget": view,
           "position": {"case": data["cases"].index(todo[0]) + 1, "of": len(data["cases"]),
                        "todo": len(todo)}}
    kinds = case.get("kinds") or []
    if kinds and view["unreadable"]:
        out.update(status="stop", message=(
            f"The spend of {', '.join(view['unreadable'])} can't be read (its run folder or run.json "
            f"is missing or damaged), so what is left of the suite budget can't be told and "
            f"{case['id']}, which spends, cannot start. Tell the person; put the run folder back "
            f"(or repair its run.json), then ask again. {CONTINUES}"))
        return 2, out
    over_kinds = [k for k in kinds if k in view["over"]]
    if over_kinds:
        over = "; ".join(f"{view['spent'][k]:g} of {_fmt(k, data['budget'].get(k, 0))}"
                         for k in over_kinds)
        out.update(status="stop", message=(
            f"The case runs have spent more than the suite budget ({over}), so {case['id']}, which "
            "needs a budget, cannot start. Tell the person; if they cannot add to it, record "
            f"{case['id']} as blocked with that note (`tm acceptance record {case['id']} blocked "
            f"--note ...`); the cases that spend nothing still run. {CONTINUES}"))
        return 2, out
    return 0, out


def record(folder: Path, case_id: str, result: str, note: str | None, evidence: list[str],
           by: str) -> dict:
    data = _load(folder)
    case = next((c for c in data["cases"] if c["id"] == case_id), None)
    if case is None:
        raise ValueError(f"There is no case {case_id!r} in this suite. The cases are "
                         f"{', '.join(c['id'] for c in data['cases'])}.")
    if result not in RESULTS:
        raise ValueError(f"{result!r} is not a result. Use one of: {', '.join(RESULTS)}.")
    note = (note or "").strip() or None
    if result == "blocked" and not note:
        raise ValueError(f"A blocked case needs --note saying what was missing (what the person "
                         f"could not provide for {case_id}). Nothing was recorded.")
    if result != "blocked" and case["judge"] and by != "person":
        raise ValueError(f"{case_id} is the person's to judge: they watch or listen to it. Record "
                         "their verdict, in their words, with --by person once they have given it; "
                         "the agent never judges it for them. Nothing was recorded.")
    files = []
    for item in evidence:
        p = Path(item).expanduser().resolve()
        if not p.exists():
            raise ValueError(f"There is no file at {p}: give the evidence's real path. Nothing was recorded.")
        files.append(str(p))
    if case["status"] != "todo":
        case["history"].append({k: case[k] for k in ("status", "by", "note", "evidence", "at")})
    case.update(status=result, by=by if result != "blocked" else None, note=note, evidence=files,
                at=_now())
    _save(folder, data)
    return case


def approve(folder: Path, note: str) -> None:
    """The person's one yes to the suite budget, in their words."""
    if not (note or "").strip():
        raise ValueError("The suite budget's approval needs --note with the person's own words.")
    data = _load(folder)
    data.setdefault("approvals", []).append({"note": note.strip(), "at": _now()})
    _save(folder, data)


# --- the report ---------------------------------------------------------------------

_KIND_NAMES = {"ai_usd": "AI (Replicate)", "voice_credits": "Voice and music (ElevenLabs)",
               "test": "Meta ads"}


def _template_path(playbook: str) -> Path:
    return (playbooks.skills_root() / playbooks.get(playbook).skill / "templates"
            / "acceptance_report_template.md")


def _template(playbook: str) -> Template:
    path = _template_path(playbook)
    return Template(path.read_text(encoding="utf-8").split("\n---\n", 1)[1].lstrip("\n"))


def _spend_words(spend: dict) -> str:
    return ", ".join(_fmt(k, v) for k, v in spend.items()) if spend else "none"


def _shown(folder: Path, path: str) -> str:
    """A path inside the acceptance folder as relative to it: the user keeps the report or sends it privately."""
    try:
        return Path(path).relative_to(folder.resolve()).as_posix()
    except ValueError:
        return path


def _case_block(folder: Path, case: dict, spend: dict | None, show_spend: bool = True,
                runs: list[tuple[str, dict]] = ()) -> str:
    if case["status"] == "todo":
        result = "**not run yet**"
    elif case["status"] == "blocked":
        result = "**blocked**"
    else:
        who = "the person's verdict" if case["by"] == "person" else "recorded by the agent from the run's numbers"
        result = f"**{case['status']}** ({who})"
    lines = [f"#### {case['id']}: {case['title']}", "",
             f"- Result: {result}",
             f"- Proves: {case['proves']}",
             f"- Note: {case['note'] or 'none'}",
             "- Evidence: " + (", ".join(f"`{_shown(folder, e)}`" for e in case["evidence"]) or "none"),
             f"- Run folder: `{case['run']}`"]
    if show_spend:   # a suite without a budget spends nothing: no spend line
        made = (" (with its production runs: " + "; ".join(f"`{name}` {_spend_words({k: v for k, v in s.items() if v})}"
                                                         for name, s in runs) + ")") if runs and spend is not None else ""
        lines.insert(-1, "- Spend: " + (_spend_words(spend) + made if spend is not None
                                        else "**could not be read** (the run folder or its run.json is missing or damaged)"))
    for h in case["history"]:
        lines.append(f"- Earlier result: {h['status']} ({h['at']}): {h['note'] or 'no note'}")
    return "\n".join(lines)


def report(folder: Path) -> tuple[Path, dict]:
    data = _load(folder)
    view = budget_view(folder, data)
    _, per_case, unreadable = spent(folder, data)
    children, _ = _children(folder, data)
    counts = {r: sum(c["status"] == r for c in data["cases"]) for r in (*RESULTS, "todo")}
    approvals = data.get("approvals") or []
    approval = (f"{_spend_words(data['budget'])}, approved by the person: \"{approvals[-1]['note']}\" "
                f"({approvals[-1]['at']})." if approvals
                else f"{_spend_words(data['budget'])}, not approved yet.")
    totals = []
    for k, v in view["spent"].items():
        cap = data["budget"].get(k, 0)
        if unreadable:
            line = f"- {_KIND_NAMES.get(k, k)}: at least {v:g} of {_fmt(k, cap)}; what is left can't be told"
        else:
            line = f"- {_KIND_NAMES.get(k, k)}: {v:g} of {_fmt(k, cap)}, {max(cap - v, 0):g} left"
        totals.append(line + (" (**over the suite budget**)" if k in view["over"] else ""))
    if unreadable:
        totals.append(f"\n**The spend of {', '.join(unreadable)} could not be read**, so these totals "
                      "are incomplete.")
    # an acceptance.json written before suites named their playbook is a refresh-ad one
    text = _template(data.get("playbook") or REFRESH_AD).substitute(
        suite=data["suite"], created=data["created"], written=f"{_today():%Y-%m-%d}",
        machine=doctor.system_name(),     # Windows 11 by its build (issue 76)
        version=__version__,
        counts=(f"{counts['pass']} pass, {counts['fail']} fail, {counts['blocked']} blocked, "
                f"{counts['todo']} not run yet, of {len(data['cases'])}"),
        approval=approval,
        cases="\n\n".join(_case_block(folder, c, None if c["id"] in unreadable else per_case.get(c["id"], {}),
                                        bool(data["budget"]), children.get(c["id"], []))
                            for c in data["cases"]),
        totals="\n".join(totals))
    target = RunFolder(folder).next_version("", "report", "md")
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(text)
    return target, counts


# --- command line -------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("start", help="start the suite in this workspace, or resume it")
    s.add_argument("--suite", required=True)
    s.add_argument("--new", action="store_true",
                   help="start today's even when an earlier one of the suite has cases left")
    n = sub.add_parser("next", help="the first case still to do, its needs and steps")
    r = sub.add_parser("record", help="record a case's result")
    r.add_argument("case")
    r.add_argument("result", choices=RESULTS)
    r.add_argument("--note", help="what happened, in the person's words for a verdict")
    r.add_argument("--evidence", nargs="+", action="extend", default=[], metavar="PATH")
    r.add_argument("--by", choices=("person", "agent"), default="agent",
                   help="person: the person's own verdict (needed on a case they judge)")
    a = sub.add_parser("approve", help="the person's one yes to the suite budget")
    a.add_argument("--note", required=True, help="the person's own words")
    w = sub.add_parser("report", help="write report_vNN.md")
    for sp in (s, n, r, a, w):
        sp.add_argument("--json", action="store_true")
        if sp is not s:
            sp.add_argument("--suite", help="the suite, when the workspace has more than one")
            sp.add_argument("--dir", help="the acceptance folder, instead of the latest one")


def _run(args: argparse.Namespace) -> int:
    ws = paths.workspace()
    try:
        if args.action == "start":
            folder, resumed = start(ws, args.suite, _today(), new=args.new)
            data = _load(folder)
            done = len(data["cases"]) - len(_todo(data))
            message = (f"Resumed {folder}: {done} of {len(data['cases'])} cases have a result."
                       if resumed else f"Started {folder}: {len(data['cases'])} cases, all to do.")
            cli.emit(args, {"status": "done", "path": str(folder), "resumed": resumed,
                            "suite": data["suite"], "playbook": data.get("playbook") or REFRESH_AD,
                            "budget": data["budget"], "message": message},
                     message)
            return 0
        folder = find(ws, args.suite, args.dir)
        if args.action == "next":
            code, out = next_case(folder)
            text = out.get("message") or (
                f"{out['case']['id']} ({out['position']['case']} of {out['position']['of']}): "
                f"{out['case']['title']}. Needs: {', '.join(out['case']['needs'])}.")
            cli.emit(args, out, text)
            return code
        if args.action == "record":
            case = record(folder, args.case, args.result, args.note, args.evidence, args.by)
            cli.emit(args, {"status": "done", "case": case["id"], "result": case["status"],
                            "by": case["by"]}, f"Recorded {case['id']}: {case['status']}.")
            return 0
        if args.action == "approve":
            approve(folder, args.note)
            cli.emit(args, {"status": "done", "approved": True}, "Recorded the suite budget's approval.")
            return 0
        target, counts = report(folder)
        cli.emit(args, {"status": "done", "path": str(target), "counts": counts},
                 f"Wrote {target}.")
        return 0
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("acceptance", _setup, _run)
