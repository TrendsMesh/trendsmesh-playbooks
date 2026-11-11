"""`tm review build`: Refresh an ad's local review page is now the run page (tm.run_page, issue #19).

    tm review build --run RUN [--json]     the same as `tm page build --run RUN --local`

The run page shows what the old review page showed (before/after pairs with one play and seek control, the change
register, the briefs, the decisions), at each check-in's stage, in the TrendsMesh look. Built locally, its decisions
are answered in chat. `pairs` stays here: the edited video's stage reads it.

Pairing, from the manifest's before/after cell: `after (before: <path>)` pairs that row's file with
<path>; `before: <path> / after: <path>` names both.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from tm import cli, manifest
from tm.runfolder import RunFolder
from tm.stops import Stop

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}      # read by organic video's QA and check-in pages
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_AFTER_OF = re.compile(r"^after \(before: (.+)\)$")
_BOTH = re.compile(r"^before: (.+?) / after: (.+)$")
REDIRECT = ("tm review build now builds the run page (tm page build --run R --local): {path}. At a check-in, build it "
            "with tm page build and publish it when the session can (references/pages.md).")


def pairs(run: RunFolder) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for row in manifest.rows(run):
        cell = row["before/after"].strip()
        if m := _AFTER_OF.match(cell):
            pair = (m.group(1).strip(), row["file"])
        elif m := _BOTH.match(cell):
            pair = (m.group(1).strip(), m.group(2).strip())
        else:
            continue
        if pair not in found:
            found.append(pair)
    return found


def build(run: RunFolder) -> Path:
    """The run page, built locally (`04_final/run_page_vNN/index.html`)."""
    from tm import run_page

    return Path(run_page.build(run, local=True)["index"])


def _setup_cli(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="kind", metavar="build")
    s = sub.add_parser("build", help="the run page, built locally (tm page build --local)")
    s.add_argument("--run", required=True)
    s.add_argument("--json", action="store_true")


def _run_cli(a: argparse.Namespace) -> int:
    if a.kind != "build":
        print("Use: tm review build --run RUN [--json]")
        return 1
    try:
        path = build(RunFolder.open(Path(a.run)))
    except Stop as exc:
        cli.emit(a, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError, KeyError) as exc:
        return cli.fail(a, f"Could not build the review page: {exc}")
    message = REDIRECT.format(path=path)
    cli.emit(a, {"status": "done", "path": str(path), "message": message}, message)
    return 0


cli.register("review", _setup_cli, _run_cli)
