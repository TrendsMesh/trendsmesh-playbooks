"""The change register check: each change is "proof" or "guess".

The register (A7) is written by Claude as JSON, next to the strategy brief:

    {"items": [{"change": "new opening card: ...", "basis": "proof",
                "sources": ["02_research/trend_123.json", "02_research/videos_123_p01.json"]},
               {"change": "headline: no change, because ...", "basis": "guess",
                "because": "the account's own winners open with a question"}]}

- `proof` needs at least one source that is a saved TrendsMesh answer of this run:
  `02_research/trend_*`, `videos_*` or `search_*`. Every source named must exist in the run folder.
- `guess` needs `sources` or `because`: what the guess rests on.
- A run whose evidence is `guess` has no proof: every item is a guess.

`tm done A7` waits until a register has been checked.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from tm import cli, evidence, state
from tm.runfolder import RunFolder

BASES = ("proof", "guess")
_TRENDSMESH_FILES = ("trend_", "videos_", "search_")


def _in_run(run: RunFolder, source: str) -> str | None:
    """The source's real path in the run folder (links followed), as posix; None outside it."""
    root = run.path.resolve()
    target = (run.path / source).resolve()
    if root not in target.parents:
        return None
    return target.relative_to(root).as_posix()


def _is_trendsmesh_answer(rel: str | None) -> bool:
    if rel is None:
        return False
    p = PurePosixPath(rel)
    return len(p.parts) == 2 and p.parts[0] == "02_research" and p.name.startswith(_TRENDSMESH_FILES)


def check(run: RunFolder, data: object) -> dict:
    """Check a register; return {proof, guess}. Raises ValueError listing every problem."""
    s = state.load(run)
    if s.evidence is None:
        raise ValueError("Record what this run's changes rest on first: "
                         "`tm evidence trendsmesh|guess --run R --why <reason>`.")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError('The register needs {"items": [...]} with at least one change.')
    problems: list[str] = []
    counts = {"proof": 0, "guess": 0}
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict) or not str(item.get("change", "")).strip():
            problems.append(f"item {n}: needs a `change`")
            continue
        basis = item.get("basis")
        if basis not in BASES:
            problems.append(f"item {n}: `basis` must be proof or guess, not {basis!r}")
            continue
        sources = item.get("sources") or []
        if not isinstance(sources, list) or not all(isinstance(x, str) and x.strip() for x in sources):
            problems.append(f"item {n}: `sources` must be a list of paths in the run folder")
            continue
        real = {src: _in_run(run, src) for src in sources}
        for src, rel in real.items():
            if rel is None or not (run.path / rel).is_file():
                problems.append(f"item {n}: the source {src} is not a file in this run folder")
        if basis == "proof":
            if s.evidence == evidence.GUESS:
                problems.append(f"item {n}: this run has no TrendsMesh data, so it is a guess, not proof")
            elif not any(_is_trendsmesh_answer(rel) for rel in real.values()):
                problems.append(f"item {n}: proof needs a saved TrendsMesh answer of this run in "
                                "`sources` (02_research/trend_*, videos_* or search_*)")
        elif not sources and not str(item.get("because", "")).strip():
            problems.append(f"item {n}: a guess needs `sources` or `because`: what it rests on")
        counts[basis] += 1
    if problems:
        raise ValueError("The change register has problems: " + "; ".join(problems) + ".")
    return counts


def record(run: RunFolder, file: Path) -> dict:
    file = run.given(file)
    data = json.loads(file.read_text(encoding="utf-8"))
    counts = check(run, data)
    s = state.load(run)
    try:
        shown = Path(file).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        shown = str(file)
    s.register = {"file": shown, **counts}
    state.save(run, s)
    return s.register


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="register_command", metavar="action")
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    c.add_argument("--file", required=True, help="the register JSON")
    c.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    if getattr(args, "register_command", None) != "check":
        return cli.fail(args, "Use: tm register check --run <run folder> --file <register JSON>")
    try:
        reg = record(RunFolder.open(args.run), Path(args.file))
    except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
        return cli.fail(args, str(exc))
    cli.emit(args, {"status": "done", "register": reg},
             f"The change register is fine: {reg['proof']} backed by TrendsMesh data, {reg['guess']} guesses.")
    return 0


cli.register("register", _setup, _run)
