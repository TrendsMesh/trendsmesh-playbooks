"""R6: output formats follow the distribution of results by placement.

The video is always made in 9:16 (Reels and Stories, with safe zones). A group of placements with
at least `formats.placement_share_min` (25%) of the results gets its own format: feed placements
(any position whose name contains "feed", plus "explore") need 4:5.

A breakdown row is a dict with the number of results (`results`, a number or a numeric string)
and the position under `placement`, `platform_position` or `position`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from tm import cli, config
from tm.r2 import run_config
from tm.runfolder import RunFolder

Format = Literal["9:16", "4:5"]


def _number(value: object) -> float:
    try:
        n = float(str(value).replace(",", "."))
    except ValueError:
        return 0.0
    return n if n > 0 and n != float("inf") else 0.0


def _is_feed(row: dict) -> bool:
    name = str(row.get("placement") or row.get("platform_position") or row.get("position") or "").lower()
    return "feed" in name or name == "explore"


def required(placement_breakdown: list[dict], share_min: float) -> list[Format]:
    total = sum(_number(r.get("results")) for r in placement_breakdown if isinstance(r, dict))
    feed = sum(_number(r.get("results")) for r in placement_breakdown
               if isinstance(r, dict) and _is_feed(r))
    out: list[Format] = ["9:16"]
    if total > 0 and feed / total >= share_min - 1e-12:
        out.append("4:5")
    return out


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--breakdown", required=True, help="JSON list of placement rows: a file or the JSON itself")
    p.add_argument("--run", help="a run folder: the share comes from its config")
    p.add_argument("--share-min", type=float, help="override formats.placement_share_min")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        text = args.breakdown.strip()
        rows = json.loads(text if text[:1] in "[{" else Path(text).read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("data") or rows.get("rows") or []
        cfg = run_config(RunFolder.open(Path(args.run))) if args.run else None
        share = args.share_min if args.share_min is not None else float(config.value(cfg, "formats.placement_share_min"))
        formats = required(rows, share)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    cli.emit(args, {"status": "done", "formats": formats, "share_min": share},
             "Formats: " + ", ".join(formats))
    return 0


cli.register("formats", _setup, _run)
