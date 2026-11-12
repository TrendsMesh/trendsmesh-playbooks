"""R1: which Meta ad is a fading winner worth refreshing. Deterministic statistics, stdlib only.

Method (PLAYBOOK.md R1; a proposal, awaiting the playbook owner's sign-off):
 1. The last included day is `today - drop_recent_days`. The days are cut into buckets of
    `window_days` (a multiple of 7) backwards from it; there are ceil(history_days / window_days)
    of them, so a bucket is never partial. A row belongs to the bucket that holds its `date_stop`
    (a 7-day period row that straddles a boundary goes by its stop day). A row that stops after
    the last included day is dropped whole, as is one older than the oldest bucket.
 2. Latest window: bucket 0, plus older buckets until results >= `min_results`.
 3. Peak window: for each older start bucket that does not overlap the latest window, the fewest
    consecutive buckets with results >= `min_results`; the peak is the lowest cost per result. A
    winner needs peak cost per result <= target CPA (`target_cpa`, or the median weekly account
    cost per result).
 4. Account ratio `a`: the rest of the account's (this ad excluded) results per spend in the
    latest window over the same in the peak window; 1 if `detrend_by_account` is off or the rest
    has no spend or no results in either window.
 5. Test: n = r_P + r_L, p0 = s_L*a / (s_P + s_L*a); p is the two-sided mid-p
    2*(F(r_L-1) + f(r_L)/2), capped at 1, of Binomial(n, p0).
 6. Fading when cpr_L >= (1 + fade_cost_increase) * cpr_P and p < fade_p_value.
 7. value_to_recover = (s_P / weeks_P) * (cpr_L / cpr_P - 1), or s_P / weeks_P for
    rank_by == "peak_spend". Fading ads are ranked by it, descending.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from tm import cli, manifest
from tm.meta_rows import Row, answer_rows, normalise, results_readable
from tm.runfolder import ReadOnlyError, RunFolder

VERDICTS = ("fading", "stable", "not_a_winner", "not_enough_data")


def _div(a: float, b: float, empty: float = 0.0) -> float:
    return a / b if b else empty


@dataclass(frozen=True)
class Window:
    """Totals of a span of days. Ratios are guarded: a zero denominator gives 0.0 (cpr: inf)."""
    start: date
    stop: date
    spend: float
    results: float
    impressions: int
    p25: int
    thruplay: int
    clicks_est: float   # sum of impressions * unique_link_clicks_ctr / 100, per row
    frequency: float    # impression-weighted mean
    cpm: float          # impression-weighted mean
    weeks: int
    plays: int = 0          # video plays; with p25..p100 the whole retention ladder
    p50: int = 0
    p75: int = 0
    p95: int = 0
    p100: int = 0
    avg_time_s: float = 0.0  # mean watch time in seconds, weighted by plays

    @property
    def cpr(self) -> float:
        return _div(self.spend, self.results, math.inf)

    @property
    def hook_rate(self) -> float:
        return _div(self.p25, self.impressions)

    @property
    def middle_rate(self) -> float:
        return _div(self.thruplay, self.p25)

    @property
    def ctr(self) -> float:
        return _div(self.clicks_est, self.impressions)

    @property
    def conversion(self) -> float:
        return _div(self.results, self.clicks_est)

    def to_json(self) -> dict:
        """Every field, so `tm diagnose --peak/--latest` takes a candidate's window as it is."""
        cpr = self.cpr
        return {"start": self.start.isoformat(), "stop": self.stop.isoformat(),
                "spend": round(self.spend, 2), "results": self.results,
                "cpr": None if math.isinf(cpr) else round(cpr, 4), "weeks": self.weeks,
                "impressions": self.impressions, "p25": self.p25, "thruplay": self.thruplay,
                "clicks_est": round(self.clicks_est, 4), "frequency": round(self.frequency, 6),
                "cpm": round(self.cpm, 4), "plays": self.plays, "p50": self.p50,
                "p75": self.p75, "p95": self.p95, "p100": self.p100,
                "avg_time_s": round(self.avg_time_s, 4)}


def aggregate(rows: list[Row], start: date, stop: date) -> Window:
    """Sum the rows whose `stop` day is in [start, stop] (daily and period rows alike)."""
    inside = [r for r in rows if start <= r.stop <= stop]
    imp = sum(r.impressions for r in inside)
    plays = sum(r.plays for r in inside)
    return Window(
        start=start, stop=stop,
        spend=sum(r.spend for r in inside), results=sum(r.results for r in inside),
        impressions=imp, p25=sum(r.p25 for r in inside), thruplay=sum(r.thruplay for r in inside),
        clicks_est=sum(r.impressions * r.unique_link_clicks_ctr / 100 for r in inside),
        frequency=_div(sum(r.frequency * r.impressions for r in inside), imp),
        cpm=_div(sum(r.cpm * r.impressions for r in inside), imp),
        weeks=max(1, round(((stop - start).days + 1) / 7)),
        plays=plays, p50=sum(r.p50 for r in inside), p75=sum(r.p75 for r in inside),
        p95=sum(r.p95 for r in inside), p100=sum(r.p100 for r in inside),
        avg_time_s=_div(sum(r.avg_time_s * r.plays for r in inside), plays),
    )


@dataclass(frozen=True)
class WinnerCfg:
    history_days: int = 90
    window_days: int = 7
    min_results: int = 30
    drop_recent_days: int = 2
    target_cpa: float | None = None
    fade_cost_increase: float = 0.30
    fade_p_value: float = 0.10
    detrend_by_account: bool = True
    rank_by: str = "value_to_recover"

    @classmethod
    def from_config(cls, config: dict | None) -> "WinnerCfg":
        """Build from the run config's `winner.*` keys; missing keys keep the defaults."""
        winner = (config or {}).get("winner") or {}
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in winner.items() if k in known and v is not None})


def mid_p_two_sided(r_late: int, n: int, p0: float) -> float:
    """Two-sided mid-p 2*(F(r_late-1) + f(r_late)/2) of Binomial(n, p0), capped at 1.

    Meta can report fractional results (rare); callers round them to int before this.
    """
    r_late = max(0, min(int(r_late), n))

    def pmf(k: int) -> float:
        if k < 0 or k > n:
            return 0.0
        if p0 <= 0:
            return 1.0 if k == 0 else 0.0
        if p0 >= 1:
            return 1.0 if k == n else 0.0
        log = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
               + k * math.log(p0) + (n - k) * math.log1p(-p0))
        return math.exp(log)

    below = sum(pmf(k) for k in range(r_late))
    return min(1.0, 2 * (below + 0.5 * pmf(r_late)))


@dataclass
class Candidate:
    ad_id: str
    name: str
    verdict: str
    peak: Window | None = None
    latest: Window | None = None
    cost_increase: float | None = None
    p_value: float | None = None
    account_ratio: float | None = None
    value_to_recover: float | None = None
    rank: int | None = None
    note: str = ""
    dropped_rows: int = 0

    def to_json(self) -> dict:
        return {"ad_id": self.ad_id, "name": self.name, "rank": self.rank, "verdict": self.verdict,
                "peak": self.peak.to_json() if self.peak else None,
                "latest": self.latest.to_json() if self.latest else None,
                "cost_increase": self.cost_increase, "p_value": self.p_value,
                "account_ratio": self.account_ratio, "value_to_recover": self.value_to_recover,
                "note": self.note, "dropped_rows": self.dropped_rows}


@dataclass
class Ranking:
    today: date
    last_day: date
    target_cpa: float | None
    cfg: WinnerCfg
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def ranked(self) -> list[Candidate]:
        return [c for c in self.candidates if c.rank is not None]

    def to_json(self) -> dict:
        return {"today": self.today.isoformat(), "last_day": self.last_day.isoformat(),
                "target_cpa": self.target_cpa,
                "config": {k: getattr(self.cfg, k) for k in self.cfg.__dataclass_fields__},
                "ranking": [c.ad_id for c in self.ranked],
                "candidates": [c.to_json() for c in self.candidates]}


def _round(x: float | None, digits: int = 6) -> float | None:
    return None if x is None or not math.isfinite(x) else round(x, digits)


def _buckets(cfg: WinnerCfg, last_day: date) -> list[tuple[date, date]]:
    """Bucket 0 is the newest. Each is `window_days` long."""
    w = cfg.window_days
    count = max(1, -(-cfg.history_days // w))
    return [(last_day - timedelta(days=(k + 1) * w - 1), last_day - timedelta(days=k * w))
            for k in range(count)]


def _span(buckets: list[tuple[date, date]], first: int, last: int) -> tuple[date, date]:
    """Buckets first..last (0 = newest) as one span."""
    return buckets[last][0], buckets[first][1]


def _fewest(buckets, rows, begin: int, min_results: float):
    """From bucket `begin` go older until results >= min_results. Returns (first, last) or None."""
    total = 0.0
    for i in range(begin, len(buckets)):
        total += aggregate(rows, *buckets[i]).results
        if total >= min_results:
            return begin, i
    return None


def _target_cpa(cfg: WinnerCfg, account: list[Row], buckets) -> float | None:
    if cfg.target_cpa is not None:
        return float(cfg.target_cpa)
    cprs = []
    for b in buckets:
        w = aggregate(account, *b)
        if w.results > 0:
            cprs.append(w.spend / w.results)
    return statistics.median(cprs) if cprs else None


def _rest_rate(account: list[Row], ad: list[Row], start: date, stop: date):
    """Results per spend of the account without this ad in a window.

    Returns (rate, problem): rate is None when it is undefined; problem is a short code:
    "not_included" (account spend below the ad's, so the account rows lack the ad),
    "no_spend" (the rest spent nothing), "no_results" (the rest spent but got nothing; rate 0.0).
    """
    a, d = aggregate(account, start, stop), aggregate(ad, start, stop)
    spend, results = a.spend - d.spend, a.results - d.results
    if a.spend < d.spend - 1e-6 or a.results < d.results - 1e-6:
        return None, "not_included"
    if spend <= 1e-9:
        return None, "no_spend"
    if results <= 1e-9:
        return 0.0, "no_results"
    return results / spend, None


def _judge(ad_id: str, rows: list[Row], account: list[Row], cfg: WinnerCfg, buckets,
           target: float | None) -> Candidate:
    name = next((r.name for r in reversed(rows) if r.name), "")
    cand = Candidate(ad_id, name, "not_enough_data")
    latest_idx = _fewest(buckets, rows, 0, cfg.min_results)
    if latest_idx is None:
        cand.note = f"Fewer than {cfg.min_results} results in the whole history."
        return cand
    latest = aggregate(rows, *_span(buckets, *latest_idx))
    best = None  # (cpr, first, last)
    for begin in range(latest_idx[1] + 1, len(buckets)):
        found = _fewest(buckets, rows, begin, cfg.min_results)
        if found is None:
            continue
        w = aggregate(rows, *_span(buckets, *found))
        if w.spend > 0 and (best is None or w.cpr < best[0]):
            best = (w.cpr, *found)
    cand.latest = latest
    if best is None:
        cand.note = f"No earlier window with {cfg.min_results} results to compare with."
        return cand
    peak = aggregate(rows, *_span(buckets, best[1], best[2]))
    cand.peak = peak
    cand.cost_increase = _round(latest.cpr / peak.cpr - 1)
    ratio = 1.0
    if cfg.detrend_by_account:
        rl, pl = _rest_rate(account, rows, latest.start, latest.stop)
        rp, pp = _rest_rate(account, rows, peak.start, peak.stop)
        if "not_included" in (pl, pp):
            cand.note = ("The account rows spend less than this ad in a window, so they do not "
                         "include it; account ratio is 1.")
        elif rp is None or rp == 0.0:
            cand.note = ("The rest of the account had no spend or no results in the peak window, "
                         "so there is no trend to subtract; account ratio is 1.")
        elif pl == "no_spend":
            cand.note = ("The rest of the account did not spend in the latest window, "
                         "so there is no trend to subtract; account ratio is 1.")
        else:
            ratio = rl / rp  # 0.0 when the rest spent in the latest window and got nothing
            if pl == "no_results":
                cand.note = "The rest of the account got no results in the latest window; account ratio is 0."
    cand.account_ratio = _round(ratio)
    p0 = latest.spend * ratio / (peak.spend + latest.spend * ratio)
    p = mid_p_two_sided(round(latest.results), round(peak.results) + round(latest.results), p0)
    cand.p_value = _round(p)
    weeks = peak.weeks
    scale = peak.spend / weeks
    cand.value_to_recover = _round(scale if cfg.rank_by == "peak_spend"
                                   else scale * (latest.cpr / peak.cpr - 1), 2)
    if target is not None and peak.cpr > target:
        cand.verdict = "not_a_winner"
    elif latest.cpr >= (1 + cfg.fade_cost_increase) * peak.cpr and p < cfg.fade_p_value:
        cand.verdict = "fading"
    else:
        cand.verdict = "stable"
    return cand


def rank(ads: dict[str, list[Row]], account: list[Row], cfg: WinnerCfg, today: date) -> Ranking:
    last_day = today - timedelta(days=cfg.drop_recent_days)
    buckets = _buckets(cfg, last_day)
    oldest = buckets[-1][0]

    def kept(rows: list[Row]) -> list[Row]:
        return [r for r in rows if oldest <= r.stop <= last_day]

    def late(rows: list[Row]) -> int:
        """Rows that end after the last included day (a period row crossing the cut goes whole)."""
        return sum(1 for r in rows if r.stop > last_day and r.start <= last_day)

    account = kept(account)
    target = _target_cpa(cfg, account, buckets)
    cands = []
    for ad_id, rows in ads.items():
        c = _judge(ad_id, kept(rows), account, cfg, buckets, target)
        c.dropped_rows = late(rows)
        if c.dropped_rows:
            c.note = (c.note + " " if c.note else "") + (
                f"{c.dropped_rows} period row(s) cross the last included day and are left out.")
        cands.append(c)
    fading = sorted((c for c in cands if c.verdict == "fading"),
                    key=lambda c: -(c.value_to_recover or 0.0))
    for i, c in enumerate(fading, 1):
        c.rank = i
    order = {v: i for i, v in enumerate(VERDICTS)}
    rest = sorted((c for c in cands if c.verdict != "fading"), key=lambda c: order[c.verdict])
    return Ranking(today, last_day, _round(target, 4), cfg, fading + rest)


# --- command line ---------------------------------------------------------------------

def load_ads(data: object) -> dict[str, list[Row]]:
    """A saved Meta answer (any shape `meta_rows.answer_rows` reads: the Meta MCP's
    `{"ad_entities": "<JSON text>", ...}`, `{"data": [...]}`, the collector's envelope, a flat list of
    rows that each carry `id`) or `{ad_id: [rows]}`. ValueError when an `{ad_id: rows}` value is not a
    list: an envelope's own keys are never taken for ads."""
    rows = answer_rows(data)
    if rows is None and isinstance(data, dict):
        out = {}
        for ad_id, value in data.items():
            if not isinstance(value, list):
                raise ValueError(
                    f"{str(ad_id)[:40]!r} is not an ad id with a list of Meta rows, and the file is not a "
                    "Meta answer with ad rows under data, rows or ad_entities.")
            normed = normalise(value)
            out[str(ad_id)] = [r if r.ad_id else _with_id(r, str(ad_id)) for r in normed]
        return out
    out: dict[str, list[Row]] = {}
    for r in normalise(rows or []):
        out.setdefault(r.ad_id, []).append(r)
    return out


def _with_id(row: Row, ad_id: str) -> Row:
    from dataclasses import replace
    return replace(row, ad_id=ad_id)


def _answer(path: str) -> object:
    """A saved file's JSON (a BOM from PowerShell is dropped); `load_ads` opens the answer."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


_AGAIN = ("Save the Meta answer of ads_get_ad_entities as it came (meta-mcp.md) and give that file; "
          "nothing was ranked.")


def _read(files: list[str], what: str) -> tuple[dict[str, list[Row]], bool]:
    """Every file's ads joined, and whether any raw row holds a readable `results`. ValueError naming
    the file when it gives no rows, or names an ad none of whose rows can be read."""
    ads: dict[str, list[Row]] = {}
    readable = False
    for f in files:
        data = _answer(f)
        part = load_ads(data)
        if not any(part.values()):
            raise ValueError(f"{Path(f).name} holds no {what} rows of a Meta read (rows with a date). {_AGAIN}")
        empty = next((ad for ad, rows in part.items() if not rows), None)
        if empty is not None:
            raise ValueError(f"{Path(f).name}: no row of ad {empty[:40]!r} can be read (none has a date), so "
                             f"no ad rows of it were read. {_AGAIN}")
        raw = answer_rows(data)
        if raw is None:   # {ad_id: [rows]}
            raw = [r for rs in data.values() for r in rs if isinstance(r, dict)]
        readable = readable or any(results_readable(r.get("results")) for r in raw)
        for ad_id, rows in part.items():
            ads.setdefault(ad_id, []).extend(rows)
    return ads, readable


def read_summary(ads: dict[str, list[Row]], account: list[Row]) -> dict:
    """What was read, for the agent to compare with what it fetched (and for the card)."""
    rows = [r for rs in ads.values() for r in rs]
    return {"ads": len(ads), "rows": len(rows),
            "from": min(r.start for r in rows).isoformat(), "to": max(r.stop for r in rows).isoformat(),
            "spend": round(sum(r.spend for r in rows), 2), "results": round(sum(r.results for r in rows), 2),
            "account_rows": len(account)}


def _check(ads: dict[str, list[Row]], results_read: bool, account: list[Row]) -> None:
    """Refuse a read that cannot give a true ranking, rather than an empty one that reads as
    "nothing is fading"."""
    if not any(r.spend > 0 for rs in ads.values() for r in rs):
        raise ValueError("No spend could be read from the ad rows (amount_spent), so no ad can be ranked. "
                         f"Ask Meta for amount_spent with R1's fields. {_AGAIN}")
    if not results_read:
        raise ValueError("The ads spent, but no results could be read from their rows (results is missing or "
                         f"not a number). Ask Meta for results with R1's fields. {_AGAIN}")
    if not account:
        raise ValueError("The account files hold no rows. When the account read is empty, give the ad files "
                         f"as --account too (meta-mcp.md). {_AGAIN}")


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--ads", required=True, nargs="+",
                   help="JSON files: the Meta answer saved as it came ({\"ad_entities\": \"<rows>\", ...}, "
                        "{\"data\": [rows]} or the collector's envelope), a flat list of rows with id, or "
                        "{ad_id: [rows]}; several files (pages) are joined")
    p.add_argument("--account", required=True, nargs="+",
                   help="JSON files of account-level rows (or every ad's rows: they are summed), "
                        "in the same shapes")
    p.add_argument("--today", help="ISO date, default today")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        args.ads = [str(run.given(f)) for f in args.ads or []]          # a run-relative answer, whatever the cwd
        args.account = [str(run.given(f)) for f in args.account or []]
        today = date.fromisoformat(args.today) if args.today else date.today()
        from tm import config
        config_file = run.path / config.FILE
        if config_file.is_file():
            bad = [p for p in config.validate(run) if p.field.startswith("winner")]
            if bad:
                return cli.fail(args, " ".join(f"{p.what} {p.todo}" for p in bad))
        cfg = WinnerCfg.from_config(config.load(run) if config_file.is_file() else None)
        ads, results_read = _read(args.ads, "ad")
        account = [r for rs in _read(args.account, "account")[0].values() for r in rs]
        _check(ads, results_read, account)
        read = read_summary(ads, account)
        ranking = rank(ads, account, cfg, today)
        target = run.next_version("01_base", "winner_ranking", "json")
        run.assert_writable(target)
        target.write_text(json.dumps(ranking.to_json(), indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        manifest.record(run, f"01_base/{target.name}", "01_base", "tm r1",
                        params={"today": today.isoformat(), "ads": len(ads), "rows": read["rows"]})
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ReadOnlyError) as exc:
        return cli.fail(args, f"Could not rank: {exc!r}" if not isinstance(exc, (OSError, ValueError, ReadOnlyError)) else str(exc))
    rows = ranking.ranked
    text = (f"Wrote 01_base/{target.name}: {len(rows)} fading of {len(ranking.candidates)} ads."
            + f"\nRead {read['ads']} ads, {read['rows']} rows, {read['from']} to {read['to']}, spend "
              f"{read['spend']}, results {read['results']}; {read['account_rows']} account rows."
            + "".join(f"\n{c.rank}. {c.name or c.ad_id}: value to recover {c.value_to_recover}"
                      for c in rows))
    cli.emit(args, {"status": "done", "file": f"01_base/{target.name}",
                    "fading": [c.ad_id for c in rows], "candidates": len(ranking.candidates),
                    "read": read}, text)
    return 0


cli.register("r1", _setup, _run)
