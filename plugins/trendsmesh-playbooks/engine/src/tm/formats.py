"""R6: output formats follow the distribution of results by placement.

The video is always made in 9:16 (Reels and Stories, with safe zones). A group of placements with
at least `formats.placement_share_min` (25%) of the results gets its own format: feed placements
(any position whose name contains "feed", plus "explore") need 4:5.

A breakdown row is a Meta row with the number of results (`results`: Meta's
`{"values": [{"value": ...}]}`, a number or a numeric string, read by `meta_rows.results`) and the
position under `placement`, `platform_position` or `position`. A breakdown with no rows, no
placement or no results that can be read is an error, never "9:16" alone: that would read like a
rule result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from tm import cli, config, meta_rows
from tm.r2 import run_config
from tm.runfolder import RunFolder

Format = Literal["9:16", "4:5"]


def _placement(row: dict) -> str:
    return str(row.get("placement") or row.get("platform_position") or row.get("position") or "").strip().lower()


def _is_feed(row: dict) -> bool:
    name = _placement(row)
    return "feed" in name or name == "explore"


def _results(row: dict) -> float:
    return max(0.0, meta_rows.results(row.get("results")))


def shares(placement_breakdown: list[dict]) -> tuple[float, float]:
    """(results in feed placements, all results) of the breakdown. ValueError when it has no rows,
    no row names a placement, or no results can be read: R6 cannot be decided from it."""
    rows = [r for r in placement_breakdown or [] if isinstance(r, dict)]
    if not rows:
        raise ValueError("The breakdown holds no placement rows, so the formats cannot be decided (R6).")
    if not any(_placement(r) for r in rows):
        raise ValueError("No row of the breakdown names a placement (platform_position), so the formats "
                         "cannot be decided (R6). Ask Meta for the breakdowns publisher_platform and "
                         "platform_position.")
    total = sum(_results(r) for r in rows)
    if total <= 0:
        raise ValueError("The breakdown has rows, but no results could be read from them (results is "
                         "missing, 0 or not a number), so the formats cannot be decided (R6).")
    return sum(_results(r) for r in rows if _is_feed(r)), total


def required(placement_breakdown: list[dict], share_min: float) -> list[Format]:
    feed, total = shares(placement_breakdown)
    out: list[Format] = ["9:16"]
    if feed / total >= share_min - 1e-12:
        out.append("4:5")
    return out


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--breakdown", required=True,
                   help="the saved Meta answer of the placement breakdown, as it came (a file or the JSON itself)")
    p.add_argument("--run", help="a run folder: the share comes from its config")
    p.add_argument("--share-min", type=float, help="override formats.placement_share_min")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        rows = meta_rows.answer_rows(cli.json_arg(args.breakdown))
        if rows is None:
            raise ValueError("The breakdown is not a Meta answer with rows (under data, rows or ad_entities): "
                             "give the saved answer of the publisher_platform × platform_position read as it came.")
        cfg = run_config(RunFolder.open(Path(args.run))) if args.run else None
        share = args.share_min if args.share_min is not None else float(config.value(cfg, "formats.placement_share_min"))
        feed, total = shares(rows)
        formats = required(rows, share)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    feed_share = round(feed / total, 4)
    cli.emit(args, {"status": "done", "formats": formats, "share_min": share, "feed_share": feed_share,
                    "results": total, "rows": len(rows)},
             f"Formats: {', '.join(formats)} (feed {feed_share:.0%} of {total:g} results, {len(rows)} rows; "
             f"4:5 from {share:.0%}).")
    return 0


cli.register("formats", _setup, _run)
