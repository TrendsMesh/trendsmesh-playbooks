"""Normalise Meta `ads_get_ad_entities` rows into plain numbers.

Meta sends numbers as strings, money as `{"value": "93.22", "unit": "PLN"}`, rates like
`"14.24%"`, and the result count as `results.values[0].value`. A missing or unreadable number is
0; this module never raises on a number. A row with no readable date cannot be placed in time, so
it is skipped. Rows may be daily or 7-day periods (`date_start` to `date_stop`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Row:
    ad_id: str
    name: str
    start: date
    stop: date
    spend: float
    results: float
    impressions: int
    p25: int
    thruplay: int
    ctr: float
    unique_link_clicks_ctr: float
    frequency: float
    cpm: float
    plays: int = 0
    p50: int = 0
    p75: int = 0
    p95: int = 0
    p100: int = 0
    avg_time_s: float = 0.0


def number(value: object) -> float:
    """Parse 93.22, "93.22", "14.24%", {"value": "93.22", "unit": "PLN"}; anything else is 0."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        out = float(value)
    elif isinstance(value, str):
        try:
            out = float(value.strip().rstrip("%").strip())
        except ValueError:
            return 0.0
    else:
        return 0.0
    return out if math.isfinite(out) else 0.0


def results(value: object) -> float:
    """A row's `results` field: Meta's `{"values": [{"value": "7"}, ...]}` (the first value), or a
    plain number."""
    if isinstance(value, dict) and isinstance(value.get("values"), list):
        first = value["values"][0] if value["values"] else None
        return number(first)
    return number(value)


_results = results  # the name PB01's modules knew


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def normalise(rows: list[dict]) -> list[Row]:
    out: list[Row] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        start = _day(r.get("date_start") or r.get("date_stop"))
        stop = _day(r.get("date_stop") or r.get("date_start"))
        if start is None or stop is None:
            continue
        if stop < start:
            start, stop = stop, start
        out.append(Row(
            ad_id=str(r.get("id") or r.get("ad_id") or ""),
            name=str(r.get("name") or r.get("ad_name") or ""),
            start=start, stop=stop,
            spend=number(r.get("amount_spent", r.get("spend"))),
            results=results(r.get("results")),
            impressions=int(number(r.get("impressions"))),
            p25=int(number(r.get("video_p25_watched_actions"))),
            thruplay=int(number(r.get("video_thruplay_watched_actions"))),
            ctr=number(r.get("ctr")),
            unique_link_clicks_ctr=number(r.get("unique_link_clicks_ctr")),
            frequency=number(r.get("frequency")),
            cpm=number(r.get("cpm")),
            plays=int(number(r.get("video_play_actions"))),
            p50=int(number(r.get("video_p50_watched_actions"))),
            p75=int(number(r.get("video_p75_watched_actions"))),
            p95=int(number(r.get("video_p95_watched_actions"))),
            p100=int(number(r.get("video_p100_watched_actions"))),
            avg_time_s=number(r.get("video_avg_time_watched_actions")),
        ))
    return out
