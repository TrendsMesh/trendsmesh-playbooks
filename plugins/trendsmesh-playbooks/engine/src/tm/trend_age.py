"""How old a run's trend data is, for the resume question (issue 59): `tm status` gives it as `trend_data`.

A run's trend data is its saved TrendsMesh trend answers (`02_research/`, `tm.trends.save_answer`), and the trend
pick it was started from (`00_raw/seed.json`, `tm run new --seed`). The data is valid for the run's valid days
from the day it was last fetched: trend research's `picks.valid_days`, the creative brief's
`brief.valid_days_default`, else `DEFAULT_DAYS` (the same 14 both default to). A pick is valid until its own
`valid_until`. The earlier date wins; past it, the data has expired.

    of(run, today=None) -> {"fetched", "valid_until", "days", "expired", "message"} | None (no trend data)
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from tm import config, trends
from tm.runfolder import RunFolder

DEFAULT_DAYS = 14
TREND_TOOLS = ("search_trends", "list_trends", "get_trend", "get_trend_videos")   # not get_usage, not the Ad Library
SEED_FILE = "00_raw/seed.json"   # brief_config.SEED_FILE: where a seeded run keeps its pick
DAYS_KEYS = ("picks.valid_days", "brief.valid_days_default")


def _today() -> date:
    return date.today()


def _day(text: object) -> date | None:
    if not isinstance(text, str) or len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _fetched(run: RunFolder) -> date | None:
    """The day the run's trend data was last fetched: the latest saved trend answer that holds data (an error
    or a non-JSON answer holds none). A legacy video file gives its `fetched`."""
    folder = run.path / trends.RESEARCH
    latest = None
    for path in sorted(folder.rglob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if "_tool" in data:
            if data.get("_tool") not in TREND_TOOLS or trends.holds_no_cards(data.get("answer")):
                continue
            day = _day(data.get("_at"))
        else:
            day = _day(data.get("fetched")) if "trend_id" in data else None
        if day and (latest is None or day > latest):
            latest = day
    return latest


def _days(run: RunFolder) -> int:
    try:
        cfg = config.load(run)
    except ValueError:
        return DEFAULT_DAYS
    for key in DAYS_KEYS:
        value = config.get(cfg, key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return DEFAULT_DAYS


def _seed_until(run: RunFolder) -> date | None:
    try:
        seed = json.loads((run.path / SEED_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _day(seed.get("valid_until")) if isinstance(seed, dict) else None


def of(run: RunFolder, today: date | None = None) -> dict | None:
    """The run's trend data: when it was last fetched, until when it is valid, and whether that day has passed,
    with a sentence saying so; None when the run has no trend data yet."""
    today = today or _today()
    fetched, seed_until = _fetched(run), _seed_until(run)
    if fetched is None and seed_until is None:
        return None
    days = _days(run)
    dates = [d for d in (fetched + timedelta(days=days) if fetched else None, seed_until) if d]
    until = min(dates)
    expired = today > until
    by_seed = seed_until is not None and until == seed_until
    end = f"it expired on {until}" if expired else f"valid until {until}"
    if fetched is None:
        said = f"Nothing is fetched yet, and the trend pick it started from is {end.replace('it ', '', 1)}."
    elif by_seed:
        said = f"Its trend data was last fetched on {fetched}, but the trend pick it started from is " \
               f"{end.replace('it ', '', 1)}."
    else:
        said = f"Its trend data was last fetched on {fetched}, for {days} days: {end}."
    return {"fetched": fetched.isoformat() if fetched else None, "valid_until": until.isoformat(), "days": days,
            "expired": expired, "message": said}

