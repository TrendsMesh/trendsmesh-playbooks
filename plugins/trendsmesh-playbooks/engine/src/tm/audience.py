"""The audience from two sources, the hypothesis first (CB1), shared by the playbooks.

    tm audience hypothesis --run R --file F [--json]
    tm audience pick --run R (--breakdown F [--placements F] | --no-data) [--json]

PLAYBOOK.md: "hypothesis from the product and the ads **before** reading data, then Meta targeting
and who actually bought. A divergence is a finding." The agent writes its hypothesis from the
product as `02_research/audience/hypothesis_vNN.md` and records it with `tm audience hypothesis`
at B1, before the age × gender breakdown is read. The collector saves every Meta read in
`01_base/meta/` with its `_input` and `_at` (`tm.mcp_saves`); `order_gap` checks that the
hypothesis was recorded before each read that is audience data.

`tm audience pick` sums the age × gender rows per segment and applies CB1: the lowest cost per
result among segments with at least `persona.min_results_per_segment` results, else the thin-data
fallback (the age band with the most results, genders summed), marked directional. The placement
rows give the formats (R6, `formats.required`). With `--no-data` (VARIANTS "New product, no ad
history") the persona is the hypothesis alone, directional, in both formats. It writes
`02_research/audience/audience_vNN.json` and `run.json` `audience`.

Audience data is "who actually bought": a read with a breakdown by age or gender. The Meta
parameter's name is not verified (preflight P-F2), so any key containing "breakdown" counts when
its value names `age` or `gender`; acceptance B2 records the real name. Targeting reads do not
count: A1 derives the market from the ad sets' targeting (`geo_locations`, PLAYBOOK "Inputs"),
before any hypothesis can be written (controller ruling on review C-1, narrowing P-F2).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from tm import brief_research, cli, config, formats, manifest, meta_rows, playbooks, state, trends
from tm.mcp_saves import META
from tm.runfolder import ReadOnlyError, RunFolder
from tm.stops import AGAIN, Stop

SCHEMA = "audience/1"
SOURCE = "meta_ads"
STAGE = "02_research/audience"
STEM = "audience"
HYPOTHESIS = re.compile(r"02_research/audience/hypothesis_v\d+\.md")
FORMAT_IDS = {"9:16": "9x16", "4:5": "4x5"}
DEFAULT_FORMATS = ["9x16", "4x5"]   # no placement data: both (VARIANTS "new product")
NO_DATA_SEGMENT = "hypothesis"
_ROW_KEYS = ("data", "rows", "ad_entities")

Rule = Literal["lowest_cost", "directional_fallback", "hypothesis_only"]


@dataclass(frozen=True)
class Segment:
    name: str
    age: str | None
    gender: str | None
    results: float
    spend: float
    cost_per_result: float | None


@dataclass(frozen=True)
class Pick:
    segment: str
    rule: Rule
    directional: bool
    results: float
    cost_per_result: float | None


# --- the numbers --------------------------------------------------------------------------------

def _label(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _cost(spend: float, results: float) -> float | None:
    return spend / results if results > 0 else None


def segments(rows: list[dict], keys: tuple[str, ...] = ("age", "gender")) -> list[Segment]:
    """One segment per distinct value tuple of `keys`, its rows summed (a breakdown per campaign
    gives one row per campaign and segment), in the order first seen. Spend is Meta's
    `amount_spent` or `spend`."""
    totals: dict[tuple[str | None, ...], list[float]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        t = totals.setdefault(tuple(_label(row.get(k)) for k in keys), [0.0, 0.0])
        t[0] += meta_rows.results(row.get("results"))
        t[1] += meta_rows.number(row.get("amount_spent", row.get("spend")))
    out = []
    for values, (results, spend) in totals.items():
        named = dict(zip(keys, values))
        out.append(Segment(name=" ".join(v or "unknown" for v in values), age=named.get("age"),
                           gender=named.get("gender"), results=results, spend=spend,
                           cost_per_result=_cost(spend, results)))
    return out


def _cheapest_first(cost: float | None) -> float:
    return math.inf if cost is None else cost


def pick(segments: list[Segment], min_results: int) -> Pick:
    """CB1: the lowest cost per result among segments with at least `min_results` results (ties
    to more results); else the age band with the most results, genders summed (ties to the lower
    cost per result), directional. With no results at all, the hypothesis alone."""
    enough = [s for s in segments if s.results >= min_results]
    if enough:
        best = min(enough, key=lambda s: (_cheapest_first(s.cost_per_result), -s.results, s.name))
        return Pick(best.name, "lowest_cost", False, best.results, best.cost_per_result)
    bands: dict[str, list[float]] = {}
    for s in segments:
        t = bands.setdefault(s.age or "unknown", [0.0, 0.0])
        t[0] += s.results
        t[1] += s.spend
    bands = {band: t for band, t in bands.items() if t[0] > 0}
    if not bands:
        return Pick(NO_DATA_SEGMENT, "hypothesis_only", True, 0.0, None)
    band, (results, spend) = min(bands.items(), key=lambda kv: (
        -kv[1][0], _cheapest_first(_cost(kv[1][1], kv[1][0])), kv[0]))
    return Pick(band, "directional_fallback", True, results, _cost(spend, results))


# --- the order: hypothesis first ----------------------------------------------------------------

AUDIENCE_BREAKDOWNS = frozenset({"age", "gender"})


def _words(value: object) -> set[str]:
    """The lowercase words in every text of a value: a list item, a comma-separated text, or the
    values of an object (`{"0": "age"}`, as the Meta MCP writes some lists)."""
    if isinstance(value, str):
        return set(re.split(r"[^a-z]+", value.lower())) - {""}
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*(_words(v) for v in value)) if value else set()
    return set()


def is_audience_data(tool_input: object) -> bool:
    """Whether a saved Meta read is audience data: a key containing "breakdown", at any depth,
    whose value names age or gender. Placement breakdowns (R6's formats), action breakdowns and
    targeting reads are not."""
    if isinstance(tool_input, dict):
        for key, value in tool_input.items():
            if "breakdown" in str(key).lower() and _words(value) & AUDIENCE_BREAKDOWNS:
                return True
            if is_audience_data(value):
                return True
    elif isinstance(tool_input, list):
        return any(is_audience_data(v) for v in tool_input)
    return False


def audience_reads(run: RunFolder) -> list[tuple[str, str | None]]:
    """The saved Meta reads in `01_base/meta/` that are audience data (age × gender breakdowns):
    (run-relative file, its `_at`). A file that is not a saved answer (no `_input`) is not the collector's and is not
    counted; nor is a read whose answer was an error (`brief_research.card_of`'s rule: no data was seen). A file
    that cannot be read is a Stop naming it, since it might be a read that came first."""
    out = []
    folder = run.path / META
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        rel = path.relative_to(run.path).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Stop(f"{rel} cannot be read ({' '.join(str(exc).split())[:100]}), so the order of the audience "
                       "hypothesis and the age × gender read cannot be checked. Fix the file or delete it (the "
                       f"read can be made again), then run this again; {AGAIN}.") from None
        if isinstance(data, dict) and "_input" in data and is_audience_data(data["_input"]):
            if not isinstance(data.get("answer"), list) and brief_research.card_of(path)[0] is None:
                continue   # a failed read (an error answer): no audience data was seen; a list is rows
            out.append((rel, data.get("_at")))
    return out


def _when(text: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _hypothesis(s: state.RunState) -> dict | None:
    hyp = (s.audience or {}).get("hypothesis")
    return hyp if isinstance(hyp, dict) else None


def _read_first(run: RunFolder, hyp: dict | None) -> tuple[str, str | None] | None:
    """The first age × gender read saved before the hypothesis was recorded (any such read, when
    none is recorded), else None. Both times are whole seconds, and the collector saves an answer
    after its call, so a read saved in the same second as the hypothesis came after it (an earlier
    read would need a model turn in between)."""
    recorded = _when(hyp.get("at")) if hyp else None
    for rel, at in audience_reads(run):
        read = _when(at)
        if recorded is None or read is None or read < recorded.replace(microsecond=0):
            return rel, at
    return None


def order_gap(run: RunFolder) -> str | None:
    """None when a hypothesis is recorded and its `at` is earlier than the `_at` of every age ×
    gender read saved in `01_base/meta/`; otherwise the gap, in words that follow "… is done once"."""
    hyp = _hypothesis(state.load(run))
    try:
        first = _read_first(run, hyp)
    except Stop as stop:
        return str(stop)
    if first is not None:
        before = f"before the hypothesis {hyp.get('file')} was recorded at {hyp.get('at')}" if hyp else \
            "before any hypothesis was recorded"
        return (f"the audience hypothesis is recorded before the age × gender data is read, but {first[0]} was read "
                f"at {first[1]}, {before}")
    if hyp is None:
        return (f"the audience hypothesis is written from the product as {STAGE}/hypothesis_vNN.md and recorded "
                "with tm audience hypothesis before the age × gender breakdown is read")
    return None


def _breach(run: RunFolder, rel: str, at: str | None) -> Stop:
    """The Stop for CB1's order broken in this run: what happened, and what the user can do."""
    skill = playbooks.get(state.load(run).playbook).skill
    return Stop(
        f"The age × gender breakdown {rel} was read at {at}, before the audience hypothesis was recorded. CB1 asks "
        "for the hypothesis from the product first and that data second, and a hypothesis written now would be "
        "shaped by the data, so step B1 of this run can never pass its check and the run cannot go on past it. "
        "Nothing was written. Tell the user plainly. They can keep this run's research as it is and start the "
        f"brief again in a new run (tm run new --playbook {skill}), where the hypothesis is recorded at B1 "
        "before the age × gender read (the A1 reads of accounts, ads and targeting do not count).")


# --- the files ----------------------------------------------------------------------------------

def _inside(run: RunFolder, given: str | Path) -> tuple[Path, str]:
    """A file named on the command line (as given, else inside the run) and its run-relative path.
    ValueError (a bad argument) for a file that does not exist or is outside the run."""
    path = run.given(given)
    if not path.is_file():
        raise ValueError(f"{given} is not a file.")
    try:
        rel = path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{given} is not inside the run folder {run.path}.") from None
    return path, rel


inside = _inside   # public name for the other playbook modules


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_hypothesis(run: RunFolder, file: str | Path) -> dict:
    """Record the agent's hypothesis file and the time, in run.json `audience.hypothesis`. Refused
    (Stop) when the file is empty, and when an age × gender breakdown was already read: CB1's order is then
    broken, and recording would also replace an earlier hypothesis that came first."""
    path, rel = _inside(run, file)
    if not HYPOTHESIS.fullmatch(rel):
        raise ValueError(f"The hypothesis is written as {STAGE}/hypothesis_vNN.md; {rel} is not.")
    if not path.read_text(encoding="utf-8-sig").strip():
        raise Stop(f"{rel} is empty. Write the audience hypothesis from the product and its ads, then record it "
                   f"again; {AGAIN}.")
    s = state.load(run)
    kept = _hypothesis(s)
    first = _read_first(run, kept)
    if first is not None:
        raise _breach(run, *first)
    reads = audience_reads(run)
    if reads:   # the recorded hypothesis came first: a new one now would come after the data
        raise Stop(f"The hypothesis {kept.get('file')} was recorded at {kept.get('at')}, before the age × gender "
                   f"breakdown {reads[0][0]} was read; it stays, because a hypothesis recorded now would come after "
                   f"that data. Nothing was recorded; go on with tm audience pick; {AGAIN}.")
    hyp = {"file": rel, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    s.audience = {**(s.audience or {}), "hypothesis": hyp}
    state.save(run, s)
    return hyp


def _rows(path: Path, rel: str) -> list[dict]:
    """The rows of a saved Meta answer (the envelope's answer: a list, or a list under data, rows
    or ad_entities, which the Meta MCP may send as a JSON text)."""
    answer = trends.unwrap(trends.read(path))
    if isinstance(answer, dict):
        for key in _ROW_KEYS:
            value = answer.get(key)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    continue
            if isinstance(value, list):
                answer = value
                break
    if not isinstance(answer, list):
        raise Stop(f"{rel} holds no rows of a Meta read. Give the saved answer of the breakdown read "
                   f"(01_base/meta/ads_get_ad_entities_vNN.json); {AGAIN}.")
    return [r for r in answer if isinstance(r, dict)]


def _breakdown_rows(path: Path, rel: str) -> list[dict]:
    rows = _rows(path, rel)
    if not any(_label(r.get("age")) or _label(r.get("gender")) for r in rows):
        raise Stop(f"{rel} has no age × gender rows. Give the saved answer of the read with breakdowns age and "
                   "gender, or use --no-data when the product has no ad history; nothing was written; "
                   f"{AGAIN}.")
    return rows


def _placement_rows(path: Path, rel: str) -> list[dict]:
    rows = [{"placement": r.get("platform_position") or r.get("publisher_platform"),
             "results": meta_rows.results(r.get("results"))} for r in _rows(path, rel)]
    if not any(_label(r["placement"]) for r in rows):
        raise Stop(f"{rel} has no placement rows. Give the saved answer of the read with breakdowns "
                   f"publisher_platform and platform_position; nothing was written; {AGAIN}.")
    return rows


def _setting(run: RunFolder, path: str):
    """A setting of the run's config.yaml, else the playbook's default."""
    cfg = config.load(run) if (run.path / config.FILE).is_file() else {}
    found = config._get(cfg, path)
    if found is None:
        module = config._for_playbook(run)
        found = config._get(module.DEFAULTS if module else config.DEFAULTS, path)
    if found is None:
        raise ValueError(f"{path} is not a setting of a {playbooks.get(state.load(run).playbook).name} run.")
    return found


def _segment_json(s: Segment) -> dict:
    out = asdict(s)
    out["spend"] = round(s.spend, 2)
    out["cost_per_result"] = None if s.cost_per_result is None else round(s.cost_per_result, 2)
    return out


def _pick_json(p: Pick) -> dict:
    out = asdict(p)
    out["cost_per_result"] = None if p.cost_per_result is None else round(p.cost_per_result, 2)
    return out


def _order_stop(run: RunFolder) -> Stop | None:
    """The Stop when CB1's order is not met yet (no hypothesis) or broken (data read first)."""
    first = _read_first(run, _hypothesis(state.load(run)))
    if first is not None:
        return _breach(run, *first)
    if _hypothesis(state.load(run)) is None:
        return Stop(f"The audience is not picked: no audience hypothesis is recorded. Write it from the product and "
                    f"its ads as {STAGE}/hypothesis_vNN.md and record it with tm audience hypothesis, then read the "
                    f"age × gender breakdown; nothing was written; {AGAIN}.")
    return None


def _require_saved_read(path: Path, rel: str) -> None:
    """Stop unless the file is a saved age × gender read in `01_base/meta/`: the one the order check
    counts, so the pick and the order check read the same thing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not (rel.startswith(f"{META}/") and isinstance(data, dict) and is_audience_data(data.get("_input"))):
        raise Stop(f"{rel} is not a saved age × gender read of this run. Give the file tm saved in {META}/ for the "
                   "Meta read with breakdowns age and gender (not a file made or changed by hand), or use --no-data "
                   f"when the product has no ad history; nothing was written; {AGAIN}.")


def pick_audience(run: RunFolder, *, breakdown: str | Path | None = None, placements: str | Path | None = None,
                  no_data: bool = False) -> tuple[Path, dict]:
    """Pick the audience, write the next `02_research/audience/audience_vNN.json` and run.json
    `audience`; returns the file and its content. Stop (nothing written) when the order is broken."""
    if no_data == (breakdown is not None):
        raise ValueError("Give --breakdown (the saved age × gender read) or --no-data, not both or neither.")
    if no_data and placements is not None:
        raise ValueError("--placements goes with --breakdown; with --no-data there is no placement data.")
    stop = _order_stop(run)
    if stop is not None:
        raise stop
    min_results = int(_setting(run, "persona.min_results_per_segment"))
    data_files: list[str] = []
    segs: list[Segment] = []
    chosen = Pick(NO_DATA_SEGMENT, "hypothesis_only", True, 0.0, None)
    formats_ = list(DEFAULT_FORMATS)
    if not no_data:
        path, rel = _inside(run, breakdown)
        _require_saved_read(path, rel)
        segs = segments(_breakdown_rows(path, rel))
        chosen = pick(segs, min_results)
        data_files.append(rel)
        if placements is not None:
            path, rel = _inside(run, placements)
            share = float(_setting(run, "formats.placement_share_min"))
            formats_ = [FORMAT_IDS[f] for f in formats.required(_placement_rows(path, rel), share)]
            data_files.append(rel)
    s = state.load(run)
    doc = {"schema": SCHEMA, "source": None if no_data else SOURCE, "hypothesis": _hypothesis(s),
           "data_files": data_files, "segments": [_segment_json(x) for x in segs], "pick": _pick_json(chosen),
           "formats": formats_, "min_results": min_results}
    target = run.next_version(STAGE, STEM, "json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")   # whole or not at all
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    rel = target.relative_to(run.path).as_posix()
    manifest.record(run, rel, rel.split("/", 1)[0], "tm audience pick", params={"data_files": data_files})
    s.audience = {**(s.audience or {}), "file": rel, "sha256": _sha256(target), "pick": doc["pick"],
                  "formats": formats_}
    state.save(run, s)
    return target, doc


def picked_gap(run: RunFolder) -> str | None:
    """The `audience_picked` step check: the hypothesis came first (`order_gap`), and the latest
    audience file is the one `tm audience pick` wrote, unchanged, on the recorded hypothesis."""
    gap = order_gap(run)
    if gap:
        return gap
    again = "the audience is picked with tm audience pick"
    latest = run.latest(STAGE, STEM, "json")
    a = state.load(run).audience or {}
    if latest is None or not isinstance(a.get("pick"), dict):
        return f"{again} ({STAGE}/{STEM}_vNN.json)"
    rel = latest.relative_to(run.path).as_posix()
    if a.get("file") != rel or a.get("sha256") != _sha256(latest):
        return f"{again}: the latest {rel} is not the file it wrote, so run it again"
    try:
        hypothesis = json.loads(latest.read_text(encoding="utf-8")).get("hypothesis")
    except (OSError, ValueError, AttributeError):
        return f"{again}: {rel} cannot be read, so run it again"
    if hypothesis != a.get("hypothesis"):
        return f"{again} again, on the hypothesis recorded since ({(a.get('hypothesis') or {}).get('file')})"
    return None


# --- command line -------------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    h = sub.add_parser("hypothesis", help="record the audience hypothesis, written before any audience data")
    h.add_argument("--run", required=True, help="the run folder")
    h.add_argument("--file", required=True, help=f"the hypothesis, {STAGE}/hypothesis_vNN.md")
    h.add_argument("--json", action="store_true")
    k = sub.add_parser("pick", help="pick the persona segment and the formats (CB1, R6)")
    k.add_argument("--run", required=True, help="the run folder")
    data = k.add_mutually_exclusive_group(required=True)
    data.add_argument("--breakdown", help="the saved age × gender read, 01_base/meta/ads_get_ad_entities_vNN.json")
    data.add_argument("--no-data", action="store_true", help="no ad history: the persona is the hypothesis alone")
    k.add_argument("--placements", help="the saved publisher_platform × platform_position read")
    k.add_argument("--json", action="store_true")


_RULE_WORDS = {"lowest_cost": "the lowest cost per result",
               "directional_fallback": "the largest cluster, thin data",
               "hypothesis_only": "the hypothesis alone, no data"}


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if args.action == "hypothesis":
            hyp = record_hypothesis(run, args.file)
            message = f"Recorded the audience hypothesis {hyp['file']} at {hyp['at']}."
            cli.emit(args, {"status": "done", "hypothesis": hyp, "message": message}, message)
            return 0
        target, doc = pick_audience(run, breakdown=args.breakdown, placements=args.placements, no_data=args.no_data)
        p = doc["pick"]
        rel = target.relative_to(run.path).as_posix()
        message = (f"Wrote {rel}: {p['segment']} ({_RULE_WORDS[p['rule']]}"
                   + (", directional" if p["directional"] else "") + f"); formats {', '.join(doc['formats'])}.")
        cli.emit(args, {"status": "done", "file": rel, "pick": p, "formats": doc["formats"], "message": message},
                 message)
        return 0
    except Stop as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))


cli.register("audience", _setup, _run)
