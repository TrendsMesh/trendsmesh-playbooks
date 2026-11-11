"""Normalise Meta `ads_get_ad_entities` rows into plain numbers.

Meta sends numbers as strings, money as `{"value": "93.22", "unit": "PLN"}`, rates like
`"14.24%"`, and the result count as `results.values[0].value`. A missing or unreadable number is
0; this module never raises on a number. A row with no readable date cannot be placed in time, so
it is skipped. Rows may be daily or 7-day periods (`date_start` to `date_stop`).

`answer_rows` is the one reader of a saved Meta answer (the Meta MCP's `{"ad_entities": "<JSON
text>", ...}`, the collector's envelope, `{"data": [...]}` pages, a plain list): every command that
reads saved Meta answers takes its rows from it.
"""

from __future__ import annotations

import json
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


def results_readable(value: object) -> bool:
    """Whether a row's `results` holds a number at all (a readable 0 counts; a missing or unreadable
    value does not), so a reader can tell "no results" from "results it could not read"."""
    if isinstance(value, dict) and isinstance(value.get("values"), list):
        value = value["values"][0] if value["values"] else None
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, str):
        try:
            return math.isfinite(float(value.strip().rstrip("%").strip()))
        except ValueError:
            return False
    return False


# --- a saved Meta answer --------------------------------------------------------------------------

ROW_KEYS = ("data", "rows", "ad_entities")


def _text_blocks(value: object) -> bool:
    """MCP content blocks (`[{"type": "text", "text": ...}]`), as a tool result file may hold them."""
    return isinstance(value, list) and bool(value) and all(
        isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) for b in value)


def answer_rows(data: object, _depth: int = 0) -> list[dict] | None:
    """The rows of a Meta answer, in any shape it is saved in; None when `data` is not one.

    Opens the collector's envelope (`{"_tool", "_input", "_at", "answer"}`), a JSON text, MCP text
    content blocks, then takes a list as it is, or the list under `data`, `rows` or `ad_entities`.
    The Meta MCP answers `ads_get_ad_entities` as `{"ad_entities": "<the rows as a JSON text>",
    "client_conversation_id": ...}`, so a text under those keys is parsed too. An answer with no
    rows gives `[]`; an object with none of those keys (`{ad_id: rows}`, an error) gives None, so the
    caller decides: never read an envelope's own keys as rows.
    """
    if _depth > 4:
        return None
    again = lambda value: answer_rows(value, _depth + 1)  # noqa: E731
    if isinstance(data, str):
        try:
            return again(json.loads(data.lstrip("﻿")))
        except ValueError:
            return None
    if _text_blocks(data):
        return again("".join(b["text"] for b in data))
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if not isinstance(data, dict):
        return None
    if "_tool" in data and "answer" in data:
        return again(data["answer"])
    for key in ROW_KEYS:
        if key in data and isinstance(data[key], (list, str, dict)):
            found = again(data[key])
            if found is not None:
                return found
    return None


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
