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

Issue #143 adds, around the method:
 - the product match (`tm r1 --links`, each ad's link from `ads_get_creatives`): an ad whose link has another host
   than `product.landing_url` is `other_product`, listed apart and never judged or ranked; one on the same host
   with another path is a near match (`product` "near"), judged as usual and listed for the user to confirm; the
   query string (tracking parameters) never counts (`product_match`);
 - `paused`: no spend in the 14 days up to the last included day;
 - `too_little_data`: every ad of the product is `not_enough_data`; the line says so with the best ad's results;
 - when no account row has a readable result, the account trend is built from the ad rows, and every judged ad
   says so in its note.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from tm import cli, manifest
from tm.meta_rows import Row, answer_rows, normalise, results_readable
from tm.runfolder import ReadOnlyError, RunFolder

VERDICTS = ("fading", "stable", "not_a_winner", "not_enough_data", "other_product")
PAUSED_DAYS = 14   # no spend in this many days up to the last included day: the ad is paused (issue #143)
FROM_ADS = "The account rows have no results, so the account trend is built from the ad rows."


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
    product: str | None = None   # own | near | other, from the ad's link (`--links`); None without one
    link: str | None = None
    paused: bool = False
    results_total: float = 0.0   # every result in the history, for the "too little data" line

    def to_json(self) -> dict:
        return {"ad_id": self.ad_id, "name": self.name, "rank": self.rank, "verdict": self.verdict,
                "peak": self.peak.to_json() if self.peak else None,
                "latest": self.latest.to_json() if self.latest else None,
                "cost_increase": self.cost_increase, "p_value": self.p_value,
                "account_ratio": self.account_ratio, "value_to_recover": self.value_to_recover,
                "note": self.note, "dropped_rows": self.dropped_rows, "product": self.product,
                "link": self.link, "paused": self.paused, "results_total": _round(self.results_total, 2)}


@dataclass
class Ranking:
    today: date
    last_day: date
    target_cpa: float | None
    cfg: WinnerCfg
    candidates: list[Candidate] = field(default_factory=list)
    product: dict | None = None          # {name, landing_url} the links were matched with
    too_little_data: dict | None = None  # every ad of the product lacks the data (`little`)

    @property
    def ranked(self) -> list[Candidate]:
        return [c for c in self.candidates if c.rank is not None]

    def to_json(self) -> dict:
        return {"today": self.today.isoformat(), "last_day": self.last_day.isoformat(),
                "target_cpa": self.target_cpa,
                "config": {k: getattr(self.cfg, k) for k in self.cfg.__dataclass_fields__},
                "ranking": [c.ad_id for c in self.ranked],
                "candidates": [c.to_json() for c in self.candidates],
                "product": self.product,
                "other_products": [c.ad_id for c in self.candidates if c.verdict == "other_product"],
                "near_matches": [c.ad_id for c in self.candidates if c.product == "near"],
                "too_little_data": self.too_little_data}


def _host_path(url: object) -> tuple[str, str] | None:
    """A link's host (lower case, without `www.` and the port) and path (without its trailing slash); the query and
    the fragment (tracking parameters) are left out. None for no link."""
    if not isinstance(url, str) or not url.strip():
        return None
    text = url.strip()
    parts = urlsplit(text if "://" in text else "//" + text)
    host = (parts.hostname or "").lower().removeprefix("www.")
    return (host, parts.path.rstrip("/")) if host else None


def product_match(link: object, landing: object) -> str | None:
    """How an ad's link matches the product's landing page (owner decision, #148 line 24): "own" for the same host
    and a path at or under the landing page's, "near" for the same host and another path (for the user to
    confirm), "other" for another host, None when the ad has no link."""
    ad, page = _host_path(link), _host_path(landing)
    if ad is None or page is None:
        return None
    if ad[0] != page[0]:
        return "other"
    return "own" if ad[1] == page[1] or ad[1].startswith(page[1] + "/") else "near"


def little(cands: list[Candidate], cfg: WinnerCfg, product: str | None) -> dict | None:
    """The "too little data" summary (issue #143): when every ad of the product (all but other products) is
    `not_enough_data`, the best one by results and the line the G1 card says. None otherwise."""
    own = [c for c in cands if c.verdict != "other_product"]
    if not own or any(c.verdict != "not_enough_data" for c in own):
        return None
    best = max(own, key=lambda c: c.results_total)
    name, need, got = product or "product", cfg.min_results, best.results_total
    line = (f"Your {name} ads have too little data to judge: the best has {got:g} of the {need} results needed."
            if got < need else
            f"Your {name} ads have too little data to judge: the best has {got:g} results, but not {need} in an "
            "earlier window to compare with.")
    return {"ads": len(own), "best_ad": best.ad_id, "best_name": best.name, "best_results": _round(got, 2),
            "min_results": need, "line": line}


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


def _add_note(c: Candidate, text: str) -> None:
    c.note = (c.note + " " if c.note else "") + text


def rank(ads: dict[str, list[Row]], account: list[Row], cfg: WinnerCfg, today: date, *,
         links: dict[str, object] | None = None, product: dict | None = None,
         account_from_ads: bool = False) -> Ranking:
    """`links` (ad id -> its link) are matched with `product["landing_url"]` (`product_match`); `account_from_ads`:
    the account rows are the ad rows summed, because the account's own rows had no results (each judged ad says
    so)."""
    last_day = today - timedelta(days=cfg.drop_recent_days)
    buckets = _buckets(cfg, last_day)
    oldest = buckets[-1][0]
    quiet = last_day - timedelta(days=PAUSED_DAYS - 1)

    def kept(rows: list[Row]) -> list[Row]:
        return [r for r in rows if oldest <= r.stop <= last_day]

    def late(rows: list[Row]) -> int:
        """Rows that end after the last included day (a period row crossing the cut goes whole)."""
        return sum(1 for r in rows if r.stop > last_day and r.start <= last_day)

    account = kept(account)
    target = _target_cpa(cfg, account, buckets)
    landing = (product or {}).get("landing_url")
    cands = []
    for ad_id, rows in ads.items():
        link = (links or {}).get(ad_id) if links is not None else None
        match = product_match(link, landing) if links is not None else None
        here = kept(rows)
        if match == "other":
            name = next((r.name for r in reversed(rows) if r.name), "")
            host, path = _host_path(link)
            c = Candidate(ad_id, name, "other_product", note=(
                f"Its link goes to {host}{path}, not to the product's landing page, so it is another product's ad "
                "and is set apart."))
        else:
            c = _judge(ad_id, here, account, cfg, buckets, target)
            if match == "near":
                _add_note(c, "Its link is on the product's site but another page: confirm it is this product.")
            if account_from_ads and c.account_ratio is not None:
                _add_note(c, FROM_ADS)
        c.product, c.link = match, link if isinstance(link, str) and link.strip() else None
        c.results_total = sum(r.results for r in here)
        c.paused = not any(r.spend > 0 for r in here if quiet <= r.stop)
        c.dropped_rows = late(rows)
        if c.dropped_rows:
            _add_note(c, f"{c.dropped_rows} period row(s) cross the last included day and are left out.")
        cands.append(c)
    fading = sorted((c for c in cands if c.verdict == "fading"),
                    key=lambda c: -(c.value_to_recover or 0.0))
    for i, c in enumerate(fading, 1):
        c.rank = i
    order = {v: i for i, v in enumerate(VERDICTS)}
    rest = sorted((c for c in cands if c.verdict != "fading"), key=lambda c: order[c.verdict])
    return Ranking(today, last_day, _round(target, 4), cfg, fading + rest, product=product if links is not None
                   else None, too_little_data=little(cands, cfg, (product or {}).get("name")))


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


_AGAIN = ("Fetch it again with ads_get_ad_entities (the collector saves the answer in 01_base/meta), or give "
          "the Meta answer saved as it came (meta-mcp.md); nothing was ranked.")


def _read(files: list[str], what: str, *, once: bool = False) -> tuple[dict[str, list[Row]], bool]:
    """Every file's ads joined, and whether any raw row holds a readable `results`. ValueError naming
    the file when it gives no rows, or names an ad none of whose rows can be read. With `once` (the
    collector's files, oldest first), a row of the same ad and days as one in a later file is that
    week fetched again: only the later file's row counts. Rows of one file are never dropped."""
    ads: dict[str, list[Row]] = {}
    readable = False
    parts = []
    for f in files:
        data = _answer(f)
        parts.append((f, data, load_ads(data)))
    counted = [part for _, _, part in parts]           # the rows each file adds
    if once:
        def key(ad: str, r: Row) -> tuple[str, date, date]:
            return r.ad_id or ad, r.start, r.stop
        later: set[tuple[str, date, date]] = set()
        for i in range(len(parts) - 1, -1, -1):          # newest first: its rows stand
            part = parts[i][2]
            counted[i] = {ad: kept for ad, rows in part.items()
                          if (kept := [r for r in rows if key(ad, r) not in later])}
            later |= {key(ad, r) for ad, rows in part.items() for r in rows}
    for (f, data, part), use in zip(parts, counted):
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
        for ad_id, rows in use.items():
            ads.setdefault(ad_id, []).extend(rows)
    return ads, readable


# --- the collector's files (issue #128) ------------------------------------------------------------
#
# A refresh-ad run collects (trend_spool.COLLECTING): every ads_get_ad_entities answer is saved as
# 01_base/meta/ads_get_ad_entities_vNN.json in the collector's envelope {"_tool", "_input", "_at", "answer"},
# with the same input in its manifest row. Without --ads (and --account), `pick` chooses R1's files from
# them by that input: `weekly` says which are weekly ad or account totals and why each other one is not.
# A later read that extends A1 (issue #143: the spend-filtered id list, the ad links) adds its own rule
# here, beside `weekly`.

COLLECTED = "01_base/meta"
ENTITIES = "ads_get_ad_entities"
WEEKLY = 7


@dataclass
class Picked:
    """The files `pick` chose: R1's ad and account reads, oldest first, where the account came from
    (`account`, or `ads` when no account read holds rows: the ad rows are summed), and every other
    saved read with why it was left out."""
    ads: list[Path]
    account: list[Path]
    account_from: str
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    def to_json(self, run: RunFolder) -> dict:
        def rel(p: Path) -> str:
            try:
                return p.resolve().relative_to(run.path.resolve()).as_posix()
            except ValueError:
                return str(p)
        return {"ads": [rel(p) for p in self.ads], "account": [rel(p) for p in self.account],
                "account_from": self.account_from,
                "skipped": [{"file": rel(p), "why": why} for p, why in self.skipped]}


def weekly(tool_input: object) -> tuple[str | None, str | None]:
    """("ad" or "account", None) for the input of a weekly ads_get_ad_entities read (`level` ad or account,
    `time_increment` 7, as a number or text); else (None, why it is not one of R1's reads)."""
    given = tool_input if isinstance(tool_input, dict) else {}
    level, step = given.get("level"), given.get("time_increment")
    step = None if step is None else str(step).strip()
    if level not in ("ad", "account"):
        return None, f"not an ad or account read (level {level})" if level else "no level"
    if step == str(WEEKLY):
        return level, None
    if step == "1":
        return None, "daily rows (time_increment 1)"
    return None, f"not weekly (time_increment {step})" if step else "not weekly (no time_increment)"


def _version(path: Path) -> int:
    stem = path.stem.rsplit("_v", 1)
    return int(stem[1]) if len(stem) == 2 and stem[1].isdigit() else 0


def _has_rows(path: Path) -> bool:
    try:
        return any(load_ads(_answer(str(path))).values())
    except (OSError, ValueError):
        return False


def pick(run: RunFolder, ads: list[Path] | None = None) -> Picked:
    """R1's reads among the collector's files (`COLLECTED`), by the input each was fetched with (`weekly`):
    the weekly ad reads, unless `ads` are given, and the weekly account reads; when none of these holds
    rows, the ad reads stand in for the account (meta-mcp.md). ValueError when no weekly ad read is saved
    and none is given."""
    folder = run.path / COLLECTED
    found = sorted(folder.glob(f"{ENTITIES}_v*.json"), key=_version) if folder.is_dir() else []
    chosen: dict[str, list[Path]] = {"ad": [], "account": []}
    skipped: list[tuple[Path, str]] = []
    for path in found:
        try:
            saved = _answer(str(path))
        except (OSError, ValueError):
            skipped.append((path, "not readable JSON"))
            continue
        if not isinstance(saved, dict) or saved.get("_tool") != ENTITIES or "answer" not in saved:
            skipped.append((path, "not the collector's envelope"))
            continue
        level, why = weekly(saved.get("_input"))
        if level is None:
            skipped.append((path, why))
        else:
            chosen[level].append(path)
    ad_files = list(ads) if ads else chosen["ad"]
    if not ad_files:
        raise ValueError(f"No weekly ad read is saved in {COLLECTED} ({ENTITIES} at level ad, time_increment "
                         f"{WEEKLY}): turn collection on (tm trends collect on --run R) and fetch A1's weekly "
                         "totals (flow.md#a1), or give the files with --ads. Nothing was ranked.")
    account = [p for p in chosen["account"] if _has_rows(p)]
    skipped += [(p, "the account read holds no rows") for p in chosen["account"] if p not in account]
    if account:
        return Picked(ad_files, account, "account", skipped)
    return Picked(ad_files, ad_files, "ads", skipped)


def read_summary(ads: dict[str, list[Row]], account: list[Row]) -> dict:
    """What was read, for the agent to compare with what it fetched (and for the card)."""
    rows = [r for rs in ads.values() for r in rs]
    return {"ads": len(ads), "rows": len(rows),
            "from": min(r.start for r in rows).isoformat(), "to": max(r.stop for r in rows).isoformat(),
            "spend": round(sum(r.spend for r in rows), 2), "results": round(sum(r.results for r in rows), 2),
            "account_rows": len(account)}


def _money(x: float) -> str:
    return f"{x:.0f}" if abs(x - round(x)) < 0.005 else f"{x:.2f}"


def read_links(path: str) -> dict[str, object]:
    """`01_base/ad_links_vNN.json`: `{"<ad id>": "<link url>"}`, each ad's link from `ads_get_creatives`."""
    data = cli.read_json(path)
    if not isinstance(data, dict) or not all(v is None or isinstance(v, str) for v in data.values()):
        raise ValueError(f"{Path(path).name} must be one JSON object of ad id to its link, "
                         "{\"<ad id>\": \"<link url>\"}, from ads_get_creatives (flow.md#a1).")
    return {str(k): v for k, v in data.items()}


def _check(ads: dict[str, list[Row]], results_read: bool, account: list[Row]) -> None:
    """Refuse a read that cannot give a true ranking, rather than an empty one that reads as
    "nothing is fading"."""
    if not any(r.spend > 0 for rs in ads.values() for r in rs):
        weeks = {(r.start, r.stop) for rs in ads.values() for r in rs}
        spent = sum(r.spend for r in account if (r.start, r.stop) in weeks)
        if spent > 0:   # issue #143: the fetch gave only the ads that did not spend
            raise ValueError(f"The ad rows hold no spend, but the account spent {_money(spent)} in the same weeks: "
                             "the fetch missed the ads that spent. Fetch the ads with amount_spent greater than 0, "
                             "sorted by amount_spent descending (flow.md#a1). Nothing was ranked.")
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
    p.add_argument("--ads", nargs="+",
                   help="JSON files: the Meta answer saved as it came ({\"ad_entities\": \"<rows>\", ...}, "
                        "{\"data\": [rows]} or the collector's envelope), a flat list of rows with id, or "
                        "{ad_id: [rows]}; several files (pages) are joined. Default: the collector's weekly ad "
                        f"reads in {COLLECTED} (ads_get_ad_entities, level ad, time_increment 7)")
    p.add_argument("--account", nargs="+",
                   help="JSON files of account-level rows (or every ad's rows: they are summed), "
                        "in the same shapes. Default: the collector's weekly account reads, else the ad files")
    p.add_argument("--links", help="01_base/ad_links_vNN.json: {\"<ad id>\": \"<link url>\"} from ads_get_creatives; "
                                   "an ad linked to another product (another host than product.landing_url) is set "
                                   "apart, never ranked (issue #143)")
    p.add_argument("--today", help="ISO date, default today")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        args.ads = [str(run.given(f)) for f in args.ads or []]          # a run-relative answer, whatever the cwd
        args.account = [str(run.given(f)) for f in args.account or []]
        own_ads, own_account = bool(args.ads), bool(args.account)
        picked = None
        if not (own_ads and own_account):                               # the collector's files (issue #128)
            picked = pick(run, [Path(f) for f in args.ads] or None)
            args.ads = args.ads or [str(p) for p in picked.ads]
            args.account = args.account or [str(p) for p in picked.account]
        today = date.fromisoformat(args.today) if args.today else date.today()
        from tm import config
        config_file = run.path / config.FILE
        if config_file.is_file():
            bad = [p for p in config.validate(run) if p.field.startswith("winner")]
            if bad:
                return cli.fail(args, " ".join(f"{p.what} {p.todo}" for p in bad))
        loaded = config.load(run) if config_file.is_file() else None
        cfg = WinnerCfg.from_config(loaded)
        product = {"name": config.value(loaded, "product.name"), "landing_url": config.value(loaded, "product.landing_url")}
        links = None
        if args.links:
            if not product["landing_url"]:
                raise ValueError("--links compares each ad's link with the product's landing page, and config.yaml "
                                 "has no product.landing_url: ask the user for it and write it with the intake "
                                 "(tm config write). Nothing was ranked.")
            links = read_links(str(run.given(args.links)))
        ads, results_read = _read(args.ads, "ad", once=not own_ads)
        account_rows, account_results = _read(args.account, "account", once=not own_account)
        account = [r for rs in account_rows.values() for r in rs]
        _check(ads, results_read, account)
        from_ads = not account_results   # issue #143: no account row has a readable result
        if from_ads:
            account = [r for rs in ads.values() for r in rs]
        read = read_summary(ads, account)
        account_from = "ads" if from_ads or (picked and picked.account_from == "ads") else "account"
        ranking = rank(ads, account, cfg, today, links=links, product=product, account_from_ads=from_ads)
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
    data = ranking.to_json()
    little_line = (ranking.too_little_data or {}).get("line")
    text += "".join(f"\n{label}: {', '.join(data[key])}." for key, label in (
        ("other_products", "Ads of other products, set aside"), ("near_matches", "Near matches to confirm"))
        if data[key])
    paused = [c.ad_id for c in ranking.candidates if c.paused and c.verdict != "other_product"]
    if paused:
        text += f"\nPaused (no spend in the last {PAUSED_DAYS} days): {', '.join(paused)}."
    if little_line:
        text += f"\n{little_line}"
    if from_ads:
        text += f"\n{FROM_ADS}"
    payload = {"status": "done", "file": f"01_base/{target.name}", "fading": [c.ad_id for c in rows],
               "candidates": len(ranking.candidates), "read": read, "account_from": account_from,
               "other_products": data["other_products"],
               "near_matches": data["near_matches"], "paused": paused, "too_little_data": little_line}
    if picked is not None:
        payload["picked"] = picked.to_json(run)
        took = payload["picked"]
        text += (f"\nTook the collector's weekly reads: ads {', '.join(took['ads'])}; account "
                 + (', '.join(took['account']) if took["account_from"] == "account" else "from the ad rows")
                 + (f"; left out {len(took['skipped'])} other reads" if took["skipped"] else "") + ".")
    cli.emit(args, payload, text)
    return 0


cli.register("r1", _setup, _run)
