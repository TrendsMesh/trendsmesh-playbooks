"""R5: the results library, <workspace>/library/results.jsonl (append-only, one row per variant).

Row fields: account, product, market, diagnosis, trend {id, type, status_on_test_day} (null in a
run without TrendsMesh data, with `evidence: guess`; `evidence` defaults to trendsmesh),
change {layer, method}, decision_metric, result_vs_control, events, decision, run, variant.
`variant` is an id of the tested variant (a string or number, e.g. "B"): two rows with the same
run and variant count once when the run is closed. `run` is the run folder's name; `tm library add
--run <run folder>` fills it and writes to that run's workspace.
Optional: `category` (the summary groups by it; without it the product is used).

`decision` counts as won for scale/won and as lost for kill/lost; anything else (no verdict)
is stored and not counted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tm import cli, paths

REQUIRED = ("account", "product", "market", "diagnosis", "trend", "change", "decision_metric",
            "result_vs_control", "events", "decision", "run", "variant")
WON = ("scale", "won", "win")
LOST = ("kill", "lost", "lose")
FILE = Path("library") / "results.jsonl"


def _file(workspace: Path) -> Path:
    return Path(workspace) / FILE


# --- append-only JSONL files of the workspace library (shared by trend_calls.jsonl and seeds.jsonl) ---

def read_jsonl(path: Path) -> tuple[list[dict], list[int]]:
    """The rows (JSON objects) of an append-only library file and the numbers (from 1) of its
    damaged lines, those that are not a JSON object. A missing file has neither.

    Lines end at a line feed only (a carriage return before it is dropped): `str.splitlines` would also break
    at U+2028, U+2029 and U+0085, which `ensure_ascii=False` writes inside a row's text. A BOM
    (Notepad adds one) is skipped."""
    path = Path(path)
    if not path.is_file():
        return [], []
    rows, damaged = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), 1):
        line = line.removesuffix("\r")
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if isinstance(row, dict):
            rows.append(row)
        else:
            damaged.append(number)
    return rows, damaged


def append_jsonl(path: Path, rows: list[dict]) -> None:
    """Append `rows`, one JSON object per line, flushed to disk. A last line without its newline
    (edited by hand) gets one first, so a new row never joins it."""
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as fh:
        fh.seek(0, os.SEEK_END)
        lead = b""
        if fh.tell():
            fh.seek(-1, os.SEEK_END)
            lead = b"" if fh.read(1) == b"\n" else b"\n"
        fh.write(lead + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())


def add(workspace: Path, row: dict) -> None:
    if not isinstance(row, dict):
        raise ValueError("A library row must be a JSON object.")
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        raise ValueError(f"The library row lacks: {', '.join(missing)}.")
    basis = row.get("evidence", "trendsmesh")
    if basis not in ("trendsmesh", "guess"):
        raise ValueError(f"The library row's evidence must be trendsmesh or guess, not {basis!r}.")
    for key, parts in (("trend", ("id", "type", "status_on_test_day")), ("change", ("layer", "method"))):
        if key == "trend" and row[key] is None and basis == "guess":
            continue  # a guessed change has no trend: it moves only the per-method ranking
        if not isinstance(row[key], dict) or any(p not in row[key] for p in parts):
            raise ValueError(f"The library row's {key} needs: {', '.join(parts)}.")
    target = _file(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    with open(target, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def add_to_run(run_path: Path, row: dict) -> Path:
    """Add a row for a run: `run` is the run folder's name (what the closing gate counts) and the
    row goes to the library of the run's own workspace (<workspace>/runs/<playbook>/<run>)."""
    run_path = Path(run_path).resolve()        # `--run .` has no parents or name until resolved
    if not (run_path / "manifest.md").is_file():
        raise ValueError(f"{run_path} is not a run folder (no manifest.md).")
    if not isinstance(row, dict):
        raise ValueError("A library row must be a JSON object.")
    if row.get("run") not in (None, run_path.name):
        raise ValueError(f"The row says run {row['run']!r}, but this run is {run_path.name!r}.")
    workspace = run_path.parents[2]
    row = {**row, "run": run_path.name}
    try:
        run_evidence = json.loads((run_path / "run.json").read_text(encoding="utf-8")).get("evidence")
    except (OSError, ValueError):
        run_evidence = None
    if run_evidence == "guess":  # the run's changes were guesses: so is every row it adds
        if row.get("evidence", "guess") != "guess" or isinstance(row.get("trend"), dict):
            raise ValueError("This run has no TrendsMesh data, so its rows are guesses: "
                             '"evidence": "guess" and "trend": null.')
        row = {**row, "evidence": "guess", "trend": None}
    add(workspace, row)
    return workspace


def rows(workspace: Path) -> list[dict]:
    """The readable rows of results.jsonl; a damaged line never hides the others."""
    return read_jsonl(_file(workspace))[0]


def variants_for_run(workspace: Path, run_id: str) -> list[str]:
    """The distinct variant ids that have a row for this run (a repeat counts once)."""
    return sorted({str(r.get("variant")) for r in rows(workspace)
                   if r.get("run") == run_id and r.get("variant") not in (None, "")})


def summary(workspace: Path, category: str, market: str) -> dict[str, dict[str, int]]:
    """Won and lost per trend ("trend:<id>") and per method ("method:<method>") in a category and market."""
    out: dict[str, dict[str, int]] = {}
    for r in rows(workspace):
        if r.get("market") != market or (r.get("category") or r.get("product")) != category:
            continue
        verdict = str(r.get("decision", "")).lower()
        if verdict not in WON + LOST:
            continue
        side = "won" if verdict in WON else "lost"
        keys = []
        if isinstance(r.get("trend"), dict) and r["trend"].get("id") is not None:
            keys.append(f"trend:{r['trend']['id']}")
        if isinstance(r.get("change"), dict) and r["change"].get("method"):
            keys.append(f"method:{r['change']['method']}")
        for k in keys:
            out.setdefault(k, {"won": 0, "lost": 0})[side] += 1
    return out


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="library_command", metavar="action")
    add_p = sub.add_parser("add")
    add_p.add_argument("--row", help="a JSON file with the row")
    add_p.add_argument("--run", help="the run folder: fills the row's run and uses the run's workspace")
    add_p.add_argument("--json", nargs="?", const=True, default=False, metavar="FILE",
                       help="print JSON; given a file, it is the row to add (as --row)")
    add_p.add_argument("--workspace")
    s = sub.add_parser("summary")
    s.add_argument("--category", required=True)
    s.add_argument("--market", required=True)
    s.add_argument("--json", action="store_true")
    s.add_argument("--workspace")


def _run(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if getattr(args, "workspace", None) else paths.workspace()
    try:
        if args.library_command == "add":
            source = args.row or (args.json if isinstance(args.json, str) else None)
            args.json = bool(args.json)
            if not source:
                return cli.fail(args, "Give the row: tm library add --run <run folder> --row <file>.")
            from tm.runfolder import RunFolder

            path = RunFolder.open(Path(args.run)).given(source) if args.run else Path(source)   # run-relative
            row = json.loads(path.read_text(encoding="utf-8"))
            if args.run:
                ws = add_to_run(Path(args.run), row)
            else:
                add(ws, row)
            cli.emit(args, {"status": "done", "file": FILE.as_posix()}, f"Added a row to {FILE.as_posix()}.")
            return 0
        if args.library_command == "summary":
            data = summary(ws, args.category, args.market)
            text = "\n".join(f"{k}: won {v['won']}, lost {v['lost']}" for k, v in sorted(data.items())) \
                or "No earlier results for this category and market."
            cli.emit(args, {"status": "done", "summary": data}, text)
            return 0
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    return cli.fail(args, "Use: tm library add --run <run folder> --row <file> | tm library summary --category <c> --market <m>")


cli.register("library", _setup, _run)
