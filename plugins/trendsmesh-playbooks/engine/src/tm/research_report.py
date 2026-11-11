"""The page of a trend research run (TR10): the handoff's tools/pb4/build_report.py, ported.

    build   04_final/report_vNN/: index.html (one view per chosen output: #report always,
            #digest, #paid), report.json (its one data source) and assets/ (evidence thumbnails)

Read from the run: the latest growth, category map and digest, the Ad Library summary (the latest
02_research/ad_library_summary_vNN.json unless another is given) and the agent's picks. Changed
from the reference tool, nothing else:
- the folder is a new `page.new_folder(run, "report")`, never written over (decisions §5);
- thumbnails go through `page.fetch_image`, chosen by the picks' date (`as_of`), never today's; a
  thumbnail that cannot be fetched is left out and never fails the build;
- nothing is hard-coded to the reference dry run: the category is the picks' `category`, the country the
  config's `market` ("Meta Ad Library (US)" becomes "Meta Ad Library (<market>)"), the footer says
  where the trend data came from and when, never "staging" or "dry run";
- dates print as "18 Nov 2026" on every OS and locale (no strftime);
- the views are the run's outputs, mapped to the original's words by `research_config.PICK_OUTPUTS` (F7c);
- the review's moves, the picks and the weighted totals come from `research_checks` (`after_moves`,
  `pick_ids`, `weighted_totals`). `build` does not check the picks (ruling F7b: `tm research picks
  check` does): a pick's weighted total goes under its row's `plugin` key, so report.json keeps the
  original's keys exactly;
- the digest view handles calls of trends that left the map, unknown verdicts, a rebuilt previous
  week (said only when the previous snapshot has `rebuilt: true`) and ended trends left out;
- with no act now pick (V15) the page says so in one line and leads with "Still rising";
- a first run (no digest yet) drops "digest" from the views, so the page claims only views it has;
- with `checked: false` in the Ad Library summary (V22) the paid view and the footer say it was not
  checked;
- no Google Fonts: every view of a shared page would call Google (GDPR), so the CSS's own Georgia
  and system-ui fallbacks are used;
- links to videos are http(s) only (else no link), every text is escaped, and the thumbnails stop
  at the Artifact tool's file limit (`page.MAX_FILES`, less index.html and report.json): the ones left
  out count as missing.
"""

from __future__ import annotations

import copy
import html
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from tm import (json_schema, manifest, page, research_checks, research_config, research_digest, research_growth,
                research_map, trends)
from tm.runfolder import RunFolder
from tm.stops import Stop

PAGE = research_digest.PAGE
SCHEMA = "pb4-report/1"
SCHEMA_FILE = Path(__file__).with_name("schemas") / "pb4_report.schema.json"
CSS_FILE = Path(__file__).with_name("research_report.css")
PAID_STEM = "ad_library_summary"
SOURCE = "tm research report"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
RECENT_DAYS = 45                     # the cards' thumbnails: videos of the 45 days before as_of first

LABEL = research_growth.LABEL
BUCKET_NOTE = {
    "act_now": "Early and spreading: new creators keep coming, recently, with an audience.",
    "still_rising": "Still gaining creators, but slower, smaller or older.",
    "too_late": "Crowded or slowing: many creators already, or few new ones.",
    "past_peak": "No new creators for two weeks, or the event it belonged to is over.",
}
PAID_LABEL = {"none": "None found in Ad Library titles", "found": "A few advertisers", "crowded": "Crowded in paid",
              "not_checkable": "Not checkable without Foreplay"}
VIEWS = {"report": "Category report", "digest": "Weekly digest", "paid": "Paid vs organic"}
assert set(VIEWS) == set(research_config.PICK_OUTPUTS.values())
NO_ACT_NOW = "No trend reaches 'act now' this time."
E = html.escape

SCRIPT = """<script>
(function(){
  var views=[].slice.call(document.querySelectorAll('.view')), tabs=[].slice.call(document.querySelectorAll('.views a'));
  if(views.length<2)return;
  document.documentElement.classList.add('js');
  tabs.forEach(function(t){t.addEventListener('click',function(e){
    var id=t.getAttribute('href').slice(1); e.preventDefault(); show(id);
    try{history.replaceState(null,'','#'+id);}catch(err){}
  });});
  function show(force){
    var h=typeof force==='string'?force:(location.hash||'').slice(1), target=document.getElementById('view-'+h);
    var inner=h?document.getElementById(h):null;
    if(!target){ target=inner?inner.closest('.view'):null; }
    if(!target)target=views[0];
    views.forEach(function(v){v.classList.toggle('on',v===target);});
    tabs.forEach(function(t){t.setAttribute('aria-current',t.getAttribute('href')==='#'+target.id.slice(5)?'page':'false');});
    if(inner&&inner.closest('.view')===target)inner.scrollIntoView();else window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',function(){show();});show();
})();
</script>"""


# --- small helpers (the original's, unchanged unless said) ---------------------------------------

def day(value: date | str | None) -> str:
    """`18 Nov 2026`, the same on every OS and locale; an ISO text is read first (an unreadable one
    is shown as it is)."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    if not isinstance(value, date):
        return ""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def fmt(n) -> str:
    n = n or 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def kind(t: dict) -> str:
    return (t.get("kind") or "").replace("_trend", "")


def spread(g: dict) -> tuple[str, str]:
    s = g.get("top_creator_share", 0)
    if s > 0.6:
        return "One account", f"{round(s * 100)}% of views from @{g.get('top_creator')}"
    if s > 0.4:
        return "A few accounts", f"top account {round(s * 100)}% of views"
    return "Broad", f"no account above {max(round(s * 100), 1)}% of views"


def _label(bucket: str) -> str:
    return LABEL.get(bucket, bucket)


def safe_url(url: object) -> str | None:
    """A link the page may carry: http(s) with a host, else None (no link)."""
    try:
        parts = urlsplit(url) if isinstance(url, str) else None
    except ValueError:
        return None
    return url if parts and parts.scheme.lower() in ("http", "https") and parts.netloc else None


def _short_id(t: dict) -> str:
    """The trend id's first 8 characters, escaped for an id or href."""
    return E(str(t["id"])[:8])


# --- the schema -------------------------------------------------------------------------------

def schema_problems(data: object) -> list[str]:
    """What in `data` breaks the report schema (`tm.json_schema`); empty when it holds."""
    return json_schema.problems(data, json_schema.load(SCHEMA_FILE), "report")


# --- inputs -----------------------------------------------------------------------------------

def _latest(run: RunFolder, stem: str, what: str) -> dict:
    path = run.latest(trends.RESEARCH, stem, "json")
    if path is None:
        raise Stop(f"This run has no {what} yet ({trends.RESEARCH}/{stem}_vNN.json), so there is no page to build. "
                   "Run that step first; the run continues from the same place.")
    data = trends.read(path)
    if not isinstance(data, dict):
        raise Stop(f"{path.name} must hold one JSON object. Run the step that writes it again; the run continues "
                   "from the same place.")
    return data


def _json(path: Path, what: str) -> dict:
    data = trends.read(Path(path))
    if not isinstance(data, dict):
        raise Stop(f"{Path(path).name} ({what}) must hold one JSON object. Fix it or give another file, then build "
                   "again; the run continues from the same place.")
    return data


def _check_ids(picks: dict, rows: dict[str, dict]) -> None:
    """The picks name only trends of the latest growth (the page needs their numbers)."""
    listed = [p.get("id") for key in ("act_now", "still_rising", "moves", "act_now_other")
              for p in picks.get(key) or [] if isinstance(p, dict)]
    lens = picks.get("lens")
    listed += [i.get("id") for i in (lens.get("items") or []) if isinstance(i, dict)] if isinstance(lens, dict) else []
    unknown = [str(i) for i in listed if i not in rows]
    if unknown:
        raise Stop(f"The picks name trends that are not in the latest growth: {', '.join(unknown)}. Check them "
                   "with tm research picks check, fix the file, then build again; the run continues from the "
                   "same place.")


def _prev_snapshot(run: RunFolder, digest: dict | None) -> Path | None:
    """The previous snapshot the digest compared with (its `plugin.prev_snapshot`), else the default."""
    named = ((digest or {}).get("plugin") or {}).get("prev_snapshot")
    if isinstance(named, str) and (run.path / named).is_file():
        return run.path / named
    return research_digest.default_prev(run)


# --- the page ---------------------------------------------------------------------------------

class _Page:
    """One build: the run, its folder, and the words of this category and market."""

    def __init__(self, run: RunFolder, out: Path, *, category: str, market: str, as_of: date, sample: dict,
                 trends_by_id: dict[str, dict], paid: dict[str, dict], paid_checked: bool):
        self.run, self.out, self.category, self.market, self.as_of = run, out, category, market, as_of
        self.sample, self.trends, self.paid, self.paid_checked = sample, trends_by_id, paid, paid_checked
        self.thumbs_missing = 0
        self.files_left = page.MAX_FILES - 2         # index.html and report.json: never over the Artifact tool's limit

    # thumbnails ------------------------------------------------------------------------------

    def _fetch(self, pool: list[dict], prefix: str, n: int, *, excerpt: bool) -> list[dict]:
        res = []
        for i, v in enumerate(pool[:n]):
            name = page.asset_name(f"{prefix}_{i + 1}.jpg")
            dest = self.out / "assets" / name
            known = dest.is_file()                         # the same thumbnail shown twice is one file
            if not known and self.files_left <= 0:
                self.thumbs_missing += 1                   # the page is full: the card shows fewer
                continue
            if not page.fetch_image(v.get("thumbnail_url"), dest):
                self.thumbs_missing += 1                   # offline or gone: the card shows fewer
                continue
            if not known:
                self.files_left -= 1
            x = {"src": f"assets/{name}", "url": v.get("url"), "views": v.get("views"),
                 "date": str(v.get("published") or "")[:10], "creator": trends.creator_of(v)}
            if excerpt:
                x["excerpt"] = str(v.get("excerpt") or "")[:90]
            res.append(x)
        return res

    def thumbs(self, tid: str, n: int = 3) -> list[dict]:
        vids = trends.load_videos(self.run, tid)
        recent_cut = (self.as_of - timedelta(days=RECENT_DAYS)).isoformat()
        pool = [v for v in vids if str(v.get("published") or "") >= recent_cut and v.get("thumbnail_url")] or \
               [v for v in vids if v.get("thumbnail_url")]
        pool.sort(key=lambda v: -(v.get("views") or 0))
        return self._fetch(pool, tid[:8], n, excerpt=True)

    def thumbs_since(self, tid: str, since: str, n: int = 3) -> list[dict]:
        """Evidence thumbnails for the digest: videos published after `since` (what is new this week)."""
        vids = trends.load_videos(self.run, tid)
        fresh = [v for v in vids if str(v.get("published") or "")[:10] > since and v.get("thumbnail_url")]
        pool = sorted(fresh, key=lambda v: -(v.get("views") or 0))
        return self._fetch(pool, f"dg_{tid[:8]}", n, excerpt=False)

    @staticmethod
    def strip_html(th: list[dict], alt: str = "Video by") -> str:
        out = []
        for x in th:
            inner = (f"<img src='{E(x['src'])}' alt='{E(alt)} {E(x['creator'] or '')}' loading='lazy'>"
                     f"<span>{fmt(x['views'])} views · {E(day(x['date']))}</span>")
            url = safe_url(x["url"])
            out.append(f"<a class='thumb' href='{E(url)}' target='_blank' rel='noopener'>{inner}</a>" if url
                       else f"<span class='thumb'>{inner}</span>")
        return "".join(out)

    # the report view -------------------------------------------------------------------------

    def momentum(self, t: dict) -> tuple[str, str]:
        rel = t.get("relative") or {}
        pool = "of all rising hooks" if t.get("kind") == "hook_trend" else f"of {self.category} topics"
        return (f"{rel.get('band', '—').capitalize()} {pool}",
                f"{rel.get('velocity_index', 0)}× the new creators of a typical {self.category} trend")

    def glance(self, t: dict, paid: dict | None) -> str:
        """TR10 (v02): position in the sample first; raw counts behind 'Raw counts'."""
        g, ctx = t["growth"], self.sample
        m, msub = self.momentum(t)
        sp, spsub = spread(g)
        cells = [
            ("Momentum, last 14 days", m, msub),
            ("Spread", sp, spsub),
            ("Reach of the evidence", f"{fmt(g.get('views_total'))} views", f"across {g.get('videos_known', 0)} videos"),
            ("Freshness", f"new video {g.get('last_seen_days', '—')} d ago", f"trend seen for {g.get('age_days', '—')} d"),
            ("Confidence", (t.get("confidence") or "—").capitalize(),
             f"{t.get('confidence_why', '')}; status {t.get('status')}"),
            (f"Meta Ad Library ({self.market})", (paid or {}).get("verdict", "not checked"),
             (paid or {}).get("query_note", "")),
        ]
        raw = (f"<details class='raw'><summary>Raw counts in the sample</summary><p>{g.get('new_recent', 0)} new creators "
               f"in the last 14 days (of {ctx.get('creators_active')} creators who joined any mapped {E(self.category)} "
               f"trend in that window), {g.get('new_base', 0)} in the 28 days before; {g.get('creators', 0)} creators in "
               f"all; median {fmt(g.get('median_views'))} views per video. TrendsMesh evidence is a collected sample, "
               "not platform totals.</p></details>")
        return "<dl class='glance'>" + "".join(
            f"<div class='c-{E(a.split()[0].lower())}'><dt>{E(a)}</dt><dd class='num'>{E(b)}</dd>"
            f"<dd class='sub'>{E(c)}</dd></div>" for a, b, c in cells) + "</dl>" + raw

    def card(self, p: dict, big: bool, valid_until: str, total: float | None, scale: tuple[float, float]) -> str:
        t = self.trends[p["id"]]
        th = self.thumbs(t["id"], 3 if big else 2)
        strip = self.strip_html(th, "Evidence video by")
        tags = f"<span class='pill k-{E(kind(t))}'>{E(kind(t))}</span><span class='pill'>{E(t.get('group') or '')}</span>"
        if p.get("maturity"):
            tags += f"<span class='pill soft'>{E(p['maturity'])}</span>"
        body = "".join(f"<p><b>{lab}</b> {E(p[k])}</p>" for lab, k in
                       (("What it is.", "what"), ("How to use it.", "how"), ("Risk.", "risk")) if p.get(k))
        score = (f"<p class='valid'>Fit score {total:g} on a scale of {scale[0]:g}–{scale[1]:g} (TR5: "
                 f"{len(research_config.CRITERIA)} criteria scored 1–5, weighted)</p>" if total is not None else "")
        return (f"<article class='card {'big' if big else ''}' id='t-{_short_id(t)}'><header><h3>{E(t['name'])}</h3>"
                f"<div class='tags'>{tags}</div></header>{self.glance(t, self.paid.get(p['id']))}"
                f"<div class='strip'>{strip}</div>{body}{score}"
                f"<p class='valid'>Valid until {E(valid_until)} · trend id {_short_id(t)}</p></article>")

    @staticmethod
    def table(rows: list[dict], moved: dict, picked: set) -> str:
        head = ("<tr><th>Trend</th><th>Type</th><th>Group</th><th>Momentum</th><th class='r'>× typical</th><th>Spread</th>"
                "<th class='r'>Reach</th><th class='r'>New video (d ago)</th><th>Confidence</th><th>Note</th>"
                "<th class='r raw'>Raw: new / before</th></tr>")
        body = []
        for t in rows:
            g, rel = t["growth"], t.get("relative") or {}
            note = t.get("seasonal_over") or moved.get(t["id"], "")
            name = f"<a href='#t-{_short_id(t)}'>{E(t['name'])}</a>" if t["id"] in picked else E(t["name"])
            body.append(f"<tr><td>{name}</td><td>{E(kind(t))}</td><td>{E(t.get('group') or '')}</td>"
                        f"<td>{E(rel.get('band', '—'))}</td><td class='r num'>{rel.get('velocity_index', '—')}</td>"
                        f"<td>{E(spread(g)[0])}</td><td class='r num'>{fmt(g.get('views_total'))}</td>"
                        f"<td class='r num'>{g.get('last_seen_days', '—')}</td><td><span class='conf "
                        f"conf-{E(t.get('confidence') or '')}'>{E(t.get('confidence') or '')}</span></td>"
                        f"<td class='note'>{E(note)}</td><td class='r num raw'>{g.get('new_recent', 0)} / "
                        f"{g.get('new_base', 0)}</td></tr>")
        return f"<div class='tw'><table>{head}{''.join(body)}</table></div>"

    def lens_section(self, lens: dict) -> str:
        items = "".join(f"<li><b>{E(self.trends[i['id']]['name'])}</b> <span class='pill'>"
                        f"{E(_label(self.trends[i['id']]['bucket']))}</span> {E(i.get('line') or '')}</li>"
                        for i in lens.get("items") or [])
        return (f"<section id='lens'><div class='sec-head'><h2>{E(lens.get('label') or '')}</h2>"
                f"<p>{E(lens.get('note') or '')}</p></div><ol class='lens'>{items}</ol></section>")

    # the digest view -------------------------------------------------------------------------

    def digest_section(self, dg: dict, prev: dict, reading: dict) -> str:
        """TR8 digest + TR9 call check (v02): the week in one minute (agent), numbers strip, what to do
        this week (agent), last week's calls with this week's videos, moved up and new on the radar
        as cards with this week's videos, cooling down grouped by reason, ended or merged."""
        trends_ = self.trends
        since = dg["prev"]["ref"]
        days = (date.fromisoformat(dg["now"]["ref"]) - date.fromisoformat(since)).days
        pt = prev.get("trends", {})
        then = day(dg["prev"].get("as_of"))

        def mini(t: dict, tid: str, head: str, line: str, th_n: int = 3, was: str | None = None) -> str:
            rel = t.get("relative") or {}
            pd = self.paid.get(tid)
            th = self.thumbs_since(tid, since, th_n)
            chips = (f"<span class='pill b-{E(str(t.get('bucket')))}'>{E(_label(t.get('bucket') or ''))}</span>"
                     f"<span class='pill'>{E(rel.get('band', '—'))}</span><span class='pill'>{E(kind(t))} · "
                     f"{E(t.get('group') or '')}</span>" + (f"<span class='pill'>{E(pd['verdict'])}</span>" if pd else ""))
            vids = f"<div class='strip'>{self.strip_html(th)}</div>" if th else \
                "<p class='sub'>No new evidence video this week.</p>"
            title = E(t["name"]) + (f" <span class='sub'>(was {E(was)})</span>" if was else "")
            return (f"<article class='card dgcard'><header><p class='kicker'>{head}</p><h3>{title}</h3>"
                    f"<div class='tags'>{chips}</div></header><p>{E(line)}</p>{vids}</article>")

        def what(tid: str) -> str:
            w = (trends_.get(tid) or {}).get("what_it_is") or ""
            return (w[:220].rsplit(" ", 1)[0] + "…") if len(w) > 220 else w

        def seasonal(x: dict) -> str | None:
            return (trends_.get(x["id"]) or {}).get("seasonal_over")

        a_n = dg["hit_rate"]["act_now"][1]
        held = [c for c in dg["calls"] if c["call"] == "act_now"]
        cooled = [x for x in dg["down"] if seasonal(x)] + [x for x in dg.get("reidentified", []) if seasonal(x)]
        slowing = [x for x in dg["down"] if not seasonal(x)]
        new_live = [x for x in dg["new"] if (trends_.get(x["id"]) or {}).get("bucket") in ("act_now", "still_rising")]
        new_other = [x for x in dg["new"] if x not in new_live and x["id"] in trends_]

        calls_html = ""
        for c in sorted(held, key=lambda c: (c["held"] is not True, -(c.get("new_creators_since") or 0))):
            as_now = (c.get("plugin") or {}).get("reidentified_as")
            now_id = c["id"] if c["id"] in trends_ else as_now if as_now in trends_ else None
            if c["held"] is None:
                mark, verdict = "?", "Unknown: TrendsMesh has no dated video with a creator"
            else:
                mark, verdict = ("✓", "Kept adding creators") if c["held"] else ("✗", "Stalled: no new creator")
            if now_id is None:            # it left this week's map (Review Focus 2)
                calls_html += (f"<article class='card dgcard'><header><p class='kicker'>{mark} Last week: act now · "
                               f"{E(verdict)}</p><h3>{E(c['name'])}</h3></header><p>Not on this week's map.</p></article>")
                continue
            t_now = trends_[now_id]
            now_b = t_now["bucket"]
            idx = (t_now.get("relative") or {}).get("velocity_index")
            stage = "Still 'act now'" if now_b == "act_now" else f"Now '{_label(now_b).lower()}'"
            note = (f"{stage}" + (f": {t_now['seasonal_over']}" if t_now.get("seasonal_over") else "")
                    + (f". This fortnight {idx}× the new creators of a typical {self.category} trend."
                       if idx is not None else ".") + f" {what(now_id)}")
            calls_html += mini(t_now, now_id, f"{mark} Last week: act now · {E(verdict)}", note, 2,
                               was=c["name"] if now_id != c["id"] else None)

        up_html = "".join(mini(trends_[x["id"]], x["id"], f"Moved up · {E(_label(x['from']))} → {E(_label(x['to']))}",
                               what(x["id"])) for x in dg["up"] if x["id"] in trends_)
        new_html = "".join(mini(trends_[x["id"]], x["id"], "New on the radar", what(x["id"])) for x in
                           sorted(new_live, key=lambda x: -((trends_[x["id"]].get("relative") or {}).get("velocity_index")
                                                            or 0)))

        def then_stage(x: dict) -> str:
            """Its stage last week: the row's own, else the previous snapshot's under its id or, for a
            trend under a new id, under the id it had (`plugin.was_id`); "—" when unknown."""
            was = pt.get(x["id"]) or pt.get((x.get("plugin") or {}).get("was_id")) or {}
            bucket = x.get("from") or was.get("bucket")
            return _label(bucket) if bucket else "—"

        def rows(items, why):
            return "".join(
                f"<tr><td>{E(x.get('name') or trends_[x['id']]['name'])}</td><td>{E(then_stage(x))} → "
                f"{E(_label((trends_.get(x['id']) or {}).get('bucket') or x.get('to') or ''))}</td>"
                f"<td class='note'>{E(why(x))}</td></tr>" for x in items)
        cool = rows(cooled, lambda x: seasonal(x) or "") + rows(slowing, lambda x: "fewer new creators than last week")
        plug = dg.get("plugin") or {}
        ended_checked = plug.get("ended_checked", True)
        ended = "".join(f"<li>{E(x['name'])}</li>" for x in dg["ended"])
        if not ended_checked:
            why = ("the previous week is rebuilt from evidence dates" if prev.get("rebuilt") is True
                   else "the previous snapshot has no pool list")
            ended = f"<li>Not checked this week: {why}, so ended trends are left out.</li>"
        unknown = (plug.get("unknown_calls") or {}).get("act_now")
        if not isinstance(unknown, int):
            unknown = sum(c["held"] is None for c in held)
        reid = "".join(f"<li>{E(x['was'])} → {E(x['name'])}</li>" for x in dg.get("reidentified", []))
        summary = "".join(f"<li>{E(s)}</li>" for s in reading.get("summary", []))
        todo = "".join(f"<li>{E(s)}</li>" for s in reading.get("todo", []))
        stats = [(f"{sum(c['held'] is True for c in held)}/{a_n}", "last week's 'act now' calls kept adding creators"
                  + (f" ({unknown} unknown)" if unknown else "")),
                 (str(len(dg["up"])), "moved up"), (str(len(new_live)), "new and rising"),
                 (str(len(cooled)), "seasonal, now over"), (str(len(slowing)), "slowing"),
                 (str(len(dg["ended"])) if ended_checked else "—", "ended or merged")]
        strip = "".join(f"<div class='count'><b>{E(a)}</b><span>{E(b)}</span></div>" for a, b in stats)
        if prev.get("rebuilt") is True:
            compared = (f"Compared with {E(then)} ({days} days of evidence). This digest uses a snapshot of that week "
                        "rebuilt from the evidence dates, so \"new\" means no creators then and ended trends are left "
                        "out; from next week it compares with the stored snapshot.")
        else:
            compared = f"Compared with the report of {E(then)} ({days} days of evidence)."
        also = (f"<p class=small-print>Also new, not rising: " + E(", ".join(
            trends_[x["id"]]["name"] + " (" + _label(trends_[x["id"]]["bucket"]).lower() + ")" for x in new_other))
            + ".</p>" if new_other else "")
        return (f"<section id='since'><p class='sample'>{compared}</p><div class='counts six'>{strip}</div></section>"
                f"<section><div class='sec-head'><h2>The week in one minute</h2></div><ul class='reading big'>{summary}"
                "</ul></section>"
                f"<section style='--c:var(--act)'><div class='sec-head'><h2>What to do this week</h2></div>"
                f"<ol class='todo'>{todo}</ol></section>"
                f"<section style='--c:var(--rise)'><div class='sec-head'><h2>Moved up</h2><p>Trends that climbed a stage, "
                f"with videos posted since {E(then)}.</p></div><div class='cards small'>{up_html or '<p>none</p>'}</div>"
                "</section>"
                f"<section style='--c:var(--rise)'><div class='sec-head'><h2>New on the radar</h2><p>Trends that entered "
                f"the TrendsMesh list since {E(then)} and are rising now.</p></div>"
                f"<div class='cards small'>{new_html or '<p>none</p>'}</div>{also}</section>"
                f"<section style='--c:var(--act)'><div class='sec-head'><h2>Last week's calls</h2><p>Did the 'act now' "
                f"picks of {E(then)} keep growing? This week's videos under each.</p></div>"
                f"<div class='cards small'>{calls_html or '<p>none</p>'}</div></section>"
                f"<section style='--c:var(--late)'><div class='sec-head'><h2>Cooling down</h2></div><div class='tw'><table>"
                f"<tr><th>Trend</th><th>Stage</th><th>Why</th></tr>{cool}</table></div></section>"
                f"<section style='--c:var(--past)'><div class='sec-head'><h2>Ended or merged</h2><p>Gone from the trend "
                f"list since {E(then)}.</p></div><ul class='small-print'>{ended}</ul>"
                f"{'<p class=small-print>Same trend under a new id:</p><ul class=small-print>' + reid + '</ul>' if reid else ''}"
                "</section>")

    # the paid view ---------------------------------------------------------------------------

    def paid_view(self, reading: list[str]) -> str:
        """TR7 view: organic stage x presence in paid ads, for rising trends and the largest slowing ones."""
        trends_, paid = self.trends, self.paid
        rows = {"rising": [t for t in trends_.values() if t["bucket"] in ("act_now", "still_rising")],
                "slowing": [t for t in trends_.values() if t["bucket"] == "too_late" and t["id"] in paid]}
        cols = ["none", "found", "crowded"]
        head = "".join(f"<th>{E(PAID_LABEL[c])}</th>" for c in cols)

        def cell(ts):
            items = []
            for t in sorted(ts, key=lambda t: -((t.get("relative") or {}).get("velocity_index") or 0)):
                pd = paid[t["id"]]
                adv = ", ".join(str(a).split(" (")[0] for a in (pd["advertisers"] or [])[:3])
                items.append(f"<li><b>{E(t['name'])}</b> <span class='pill b-{E(t['bucket'])}'>{E(_label(t['bucket']))}</span>"
                             f"<span class='sub'>{E((t.get('relative') or {}).get('band', ''))}"
                             f"{' · ' + E(adv) if adv else ''}</span></li>")
            return "<ul class='cell'>" + "".join(items) + "</ul>" if items else "<p class='sub'>none</p>"

        body = ""
        for key, label in (("rising", "Rising in organic<br><span class='sub'>act now, still rising</span>"),
                           ("slowing", "Slowing in organic<br><span class='sub'>the largest 'too late' trends</span>")):
            body += f"<tr><th class='rowh'>{label}</th>" + "".join(
                f"<td class='q q-{key}-{c}'>{cell([t for t in rows[key] if paid.get(t['id'], {}).get('level') == c])}</td>"
                for c in cols) + "</tr>"
        hooks = [t for t in trends_.values() if paid.get(t["id"], {}).get("level") == "not_checkable"]
        unchecked = [t for t in rows["rising"] if t["id"] not in paid]
        read = "".join(f"<li>{E(x)}</li>" for x in reading)
        if self.paid_checked:
            what = (f"Every rising trend and the largest slowing ones, checked in Meta Ad Library (active "
                    f"{E(self.market)} ads). Titles only: 'none found' means none in titles, not proof that nobody "
                    "advertises it.")
        else:                                       # V22: the Meta Ads connector was unavailable
            what = (f"Meta Ad Library was not checked in this run (active {E(self.market)} ads), so every trend "
                    "here is \"not checked\"; the report is otherwise complete.")
        return (f"<div class='sec-head'><h2>Organic stage × presence in paid</h2><p>What is rising in organic but not yet "
                f"in ads. {what}</p></div><ul class='reading'>{read}</ul>"
                f"<div class='tw'><table class='matrix'><tr><th></th>{head}</tr>{body}</table></div>"
                f"<p class='small-print'><b>Hooks, not checkable in titles:</b> "
                f"{E(', '.join(t['name'] for t in hooks)) or 'none'}. "
                f"{'<b>Not checked:</b> ' + E(', '.join(t['name'] for t in unchecked)) + '. ' if unchecked else ''}"
                "With Foreplay connected this view adds, per trend and hook, how many paid ads use it, on which "
                "platforms, and how long the longest has run.</p>")


# --- build ------------------------------------------------------------------------------------

def _paid_rows(raw: list, rows: dict[str, dict], market: str) -> dict[str, dict]:
    paid = {}
    for c in raw:
        if isinstance(c, dict) and c.get("trend_id") in rows and c.get("level") in PAID_LABEL:
            paid[c["trend_id"]] = {"level": c["level"], "verdict": PAID_LABEL[c["level"]],
                                   "query_note": f"search '{c['query']}', active {market} ads" if c.get("query")
                                   else "needs Foreplay",
                                   "advertisers": c.get("advertisers", []), "estimated": c.get("estimated"),
                                   "example_id": c.get("example_id"), "note": c.get("note", "")}
    return paid


def build(run: RunFolder, picks_path: Path, *, paid: Path | None = None, prev_snapshot: Path | None = None,
          backtests: list[Path] = (), cfg: dict) -> Path:
    """Build the page into a new 04_final/report_vNN/ (index.html, report.json, assets/) and return
    the folder. Nothing is written when an input is missing or the report breaks its schema."""
    cfg = research_map.settings(cfg)
    gj = _latest(run, research_growth.STEM, "growth")
    cmap = _latest(run, research_map.STEM, "category map")
    picks = _json(Path(picks_path), "the picks")
    growth_rows = {t["id"]: t for t in gj["trends"]}
    _check_ids(picks, growth_rows)
    market = str(cfg.get("market") or "").strip()
    if not market:
        raise Stop("The run's config has no market, so the Ad Library country is unknown. Set market in "
                   "config.yaml; the run continues from the same place.")
    category = str(picks.get("category") or cfg["category"].get("phrase") or "").strip()
    try:
        as_of = date.fromisoformat(picks["as_of"]) if isinstance(picks.get("as_of"), str) else None
    except ValueError:
        as_of = None
    if as_of is None:
        raise Stop("The picks have no as_of date (YYYY-MM-DD): the page's dates and its valid-until come from it. Add "
                   "it, then build again; the run continues from the same place.")
    valid_until = day(as_of + timedelta(days=cfg["picks"]["valid_days"]))

    paid_file = Path(paid) if paid else run.latest(trends.RESEARCH, PAID_STEM, "json")
    summary = _json(paid_file, "the Ad Library summary") if paid_file else {}
    paid_raw = summary.get("checks") or []
    paid_checked = bool(paid_file) and summary.get("checked") is not False
    # the review's moves, applied (research_checks.after_moves): the reference tool changed the rows in place
    stage = research_checks.after_moves(growth_rows, picks)
    rows = [{**copy.deepcopy(t), "bucket": stage[t["id"]]} for t in gj["trends"]]
    by_id = {t["id"]: t for t in rows}
    paid_rows = _paid_rows(paid_raw, by_id, market)
    moved = {m["id"]: f"Moved by review from {_label(m['from'])}: {m.get('why', '')}" for m in picks.get("moves") or []
             if isinstance(m, dict) and stage.get(m.get("id")) != growth_rows.get(m.get("id"), {}).get("bucket")}
    by = {b: [t for t in rows if t["bucket"] == b] for b in LABEL}
    picked = set(research_checks.pick_ids(picks))
    totals = research_checks.weighted_totals(picks, cfg)
    weights = cfg["scoring"]["weights"]
    scale = (float(sum(weights[c] for c in research_config.CRITERIA)),
             float(5 * sum(weights[c] for c in research_config.CRITERIA)))

    outputs = [research_config.PICK_OUTPUTS[o] for o in cfg["outputs"] if o in research_config.PICK_OUTPUTS]
    if "report" not in outputs:
        outputs.insert(0, "report")
    digest_path = run.latest(trends.RESEARCH, research_digest.STEM, "json")
    digest = trends.read(digest_path) if digest_path and "digest" in outputs else None
    if digest is None and "digest" in outputs:     # a first run: no digest yet, so the page claims no view of it
        outputs.remove("digest")
    ctx, p = gj["params"]["category"], gj["params"]
    platforms = sorted({pl for t in rows for pl in t.get("platforms", [])})
    q = cmap["queries"]
    backtest_data = [_json(Path(f), "a backtest") for f in backtests]

    def pick_row(x: dict) -> dict:
        return {**x, "trend": by_id[x["id"]], "paid": paid_rows.get(x["id"]),
                "plugin": {"weighted_total": totals.get(x["id"]), "scale": list(scale)}}

    report = {"schema": SCHEMA, "category": picks.get("category"), "market": picks.get("market"), "as_of": picks["as_of"],
              "valid_until": valid_until, "outputs": outputs,
              "sample": {**ctx, "platforms": platforms, **{k: p[k] for k in ("window", "baseline", "ref", "rule")}},
              "act_now": [pick_row(x) for x in picks.get("act_now") or []],
              "still_rising": [pick_row(x) for x in picks.get("still_rising") or []],
              "moves": picks.get("moves") or [], "lens": picks.get("lens"), "watch_next": picks.get("watch_next"),
              "buckets": {b: [{"id": t["id"], "name": t["name"], "kind": t.get("kind"), "group": t.get("group"),
                               "relative": t.get("relative"), "confidence": t.get("confidence"),
                               "growth": {k: t["growth"].get(k) for k in ("new_recent", "new_base", "last_seen_days",
                                                                         "views_total", "top_creator_share", "creators")},
                               "note": t.get("seasonal_over") or moved.get(t["id"], "")} for t in by[b]] for b in LABEL},
              "paid": {"reading": picks.get("paid_reading", []), "checks": paid_rows},
              "digest": (digest | {"reading": picks.get("digest_reading", {})}) if digest is not None else None,
              "category_map": {"queries": q, "dropped": cmap["dropped"], "min_match": cmap["min_match"]},
              "backtest": [b["summary"] | {"ref": b["ref"]} for b in backtest_data]}
    wrong = schema_problems(report)
    if wrong:
        raise Stop(f"The report breaks its schema ({SCHEMA}): {'; '.join(wrong)}. Fix the input it comes from, "
                   "then build again; the run continues from the same place.")

    out = page.new_folder(run, PAGE)
    pg = _Page(run, out, category=category, market=market, as_of=as_of, sample=ctx, trends_by_id=by_id,
               paid=paid_rows, paid_checked=paid_checked)
    prev = prev_snapshot if prev_snapshot is not None else _prev_snapshot(run, digest)
    prev_snap = _json(Path(prev), "the previous snapshot") if digest is not None and prev else {}
    html_text = _render(pg, picks, report, cmap, gj, by, moved, picked, totals, scale, backtest_data, digest,
                        prev_snap, valid_until)
    (out / "index.html").write_text(html_text, encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, page.FINAL, SOURCE,
                    params={"picks": Path(picks_path).name, "paid": paid_file.name if paid_file else None,
                            "outputs": outputs, "thumbnails_missing": pg.thumbs_missing})
    return out


def _render(pg: _Page, picks: dict, report: dict, cmap: dict, gj: dict, by: dict, moved: dict, picked: set,
            totals: dict, scale: tuple[float, float], backtest_data: list[dict], digest: dict | None,
            prev_snap: dict, valid_until: str) -> str:
    category, market, trends_ = pg.category, pg.market, pg.trends
    ctx, p = gj["params"]["category"], gj["params"]
    act, rising = picks.get("act_now") or [], picks.get("still_rising") or []
    big = "".join(pg.card(x, True, valid_until, totals.get(x["id"]), scale) for x in act)
    small = "".join(pg.card(x, False, valid_until, totals.get(x["id"]), scale) for x in rising)
    digest_html = pg.digest_section(digest, prev_snap, picks.get("digest_reading") or {}) if digest is not None else ""
    lens = pg.lens_section(picks["lens"]) if isinstance(picks.get("lens"), dict) else ""
    n_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    n_act = n_words.get(len(act), str(len(act)))
    one = len(act) == 1
    other = "".join(f"<li><b>{E(trends_[o['id']]['name'])}</b>: {E(o.get('note') or '')}</li>"
                    for o in picks.get("act_now_other") or [])
    moves = "".join(f"<li><b>{E(trends_[m['id']]['name'])}</b>: {E(_label(m.get('from') or ''))} → "
                    f"{E(_label(m.get('to') or ''))}. {E(m.get('why') or '')}</li>" for m in picks.get("moves") or [])
    counts = "".join(f"<a class='count b-{b}' href='#{b.replace('_', '-')}'><b>{len(by[b])}</b><span>{LABEL[b]}</span></a>"
                     for b in LABEL)

    q = cmap["queries"]
    kept_by_sub: dict[str, int] = {}
    for r in cmap["kept"]:
        kept_by_sub[r["sub_category"]] = kept_by_sub.get(r["sub_category"], 0) + 1
    qrows = "".join(f"<tr><td>{E(x['query'])}</td><td>{E(x['parent'] or '—')}</td><td class='r num'>{x['relevant']}</td>"
                    f"<td class='r num'>{kept_by_sub.get(x['query'], 0)}</td>"
                    f"<td>{'split further' if x['relevant'] < cmap['min_relevant'] else ''}</td></tr>"
                    for x in sorted(q, key=lambda x: ((x['parent'] or ''), x['query'])))
    dropped = "".join(f"<li>{E(r['name'])}: {E('; '.join(r['dropped_because']))}</li>" for r in cmap["dropped"])
    root = cmap.get("root") or category
    root_relevant = next((x["relevant"] for x in q if x["query"] == root), 0)
    split = any(x.get("parent") for x in q)
    mapped = (f'One phrase in: "{E(root)}" matched only {root_relevant} trend{"" if root_relevant == 1 else "s"} '
              "strongly, so it was split into sub-categories, and thin ones split once more" if split else
              f'One phrase in: "{E(root)}" matched {root_relevant} trend{"" if root_relevant == 1 else "s"} strongly, '
              "so it was not split")

    bt_rows = ""
    for b in backtest_data:
        s = b["summary"]
        bt_rows += "".join(f"<tr><td>{E(day(b['ref']))} · rule {E(b.get('rule', ''))}</td><td>{LABEL[k]}</td>"
                           f"<td class='r num'>{s[k]['n']}</td><td class='r num'>{s[k]['median_new']}</td>"
                           f"<td class='r num'>{round((s[k]['share_with_3plus'] or 0) * 100)}%</td></tr>" for k in LABEL)
    if not bt_rows:
        bt_rows = "<tr><td colspan='5'>No backtest in this run.</td></tr>"

    colour = {"act_now": "act", "still_rising": "rise", "too_late": "late", "past_peak": "past"}
    tables = "".join(
        f"<section id='{b.replace('_', '-')}' style='--c:var(--{colour[b]})'><div class='sec-head'><h2>{LABEL[b]} · "
        f"{len(by[b])}</h2><p>{BUCKET_NOTE[b]}</p></div>{pg.table(by[b], moved, picked)}</section>" for b in LABEL)
    n_hooks = sum(1 for t in gj["trends"] if t.get("kind") == "hook_trend")
    outputs = report["outputs"]
    nav = "".join(f"<a href='#{o}'>{E(VIEWS[o])}</a>" for o in outputs)
    cat = E(category)

    still = (f'<section style="--c:var(--rise)"><div class="sec-head"><h2>Still rising: worth watching</h2>'
             f'<p>{BUCKET_NOTE["still_rising"]}</p></div><div class="cards small">{small}</div></section>')
    watch = (f'<section><div class="sec-head"><h2>Watch next</h2></div><p class="callout">'
             f'{E(picks.get("watch_next") or "")}</p></section>')
    others = (f"<div class='small-print'><b>Also in 'act now' by the numbers, not recommended yet:</b><ul>{other}</ul>"
              "</div>" if other else "")
    if act:
        lede = (f"{n_act.capitalize()} trend{'' if one else 's'} to act on now, what is still rising, and what to "
                "leave out.")
        act_html = (f'<section style="--c:var(--act)"><div class="sec-head"><h2>Act on '
                    f'{"this one" if one else "these " + n_act}</h2>'
                    f'<p>{BUCKET_NOTE["act_now"]} Ordered by fit to the {E(market)} market and room left in paid.</p>'
                    f'</div><div class="cards">{big}</div>{others}</section>')
        lead = act_html + lens + still + watch
    else:                                     # V15: one line, and the page leads with still rising
        lede = NO_ACT_NOW
        lead = still + watch + (f'<section style="--c:var(--act)">{others}</section>' if others else "") + lens
    lede += (f" Each trend is placed against the rest of the {cat} sample: how fast new creators join it compared with a "
             f"typical {cat} trend, how widely its views are spread, and how much reach its evidence has.")

    digest_view = (f'<div class="view" id="view-digest"><header><h1>Weekly digest: {cat}</h1><div class="meta">'
                   f'<span>{E(picks["market"])}</span><span>this week vs the previous run</span></div></header>'
                   f'{digest_html}</div>' if digest_html else "")
    paid_view = (f'<div class="view" id="view-paid"><header><h1>Paid vs organic: {cat}</h1><div class="meta">'
                 f'<span>{E(picks["market"])}</span><span>Meta Ad Library, active ads</span></div></header>'
                 f'<section>{pg.paid_view(picks.get("paid_reading") or [])}</section></div>' if "paid" in outputs else "")
    css = CSS_FILE.read_text(encoding="utf-8")
    paid_note = (f'Paid check: Meta Ad Library, active {E(market)} ads, titles only, so "none found" means none in '
                 'titles, not "not in ads".' if pg.paid_checked else
                 f"Paid check: Meta Ad Library was not checked in this run, so every paid verdict is \"not checked\".")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(category[:1].upper() + category[1:])} Trend Report</title>
<style>{css}</style></head><body><main>
<nav class="views" aria-label="Views">{nav}</nav>
<div class="view" id="view-report">
<header><h1>What is moving in {cat}</h1>
<div class="meta"><span>Market: {E(picks['market'])}</span><span>As of {E(day(picks['as_of']))}</span><span>{len(gj['trends']) - n_hooks} topics + {n_hooks} hooks mapped</span><span>Source: TrendsMesh evidence videos, Meta Ad Library</span></div>
<p class="lede">{lede}</p>
<div class="counts">{counts}</div>
<p class="sample"><b>The sample.</b> In the {p['window']} days to {E(day(p['ref']))}, {ctx.get('creators_active')} creators joined one of the {ctx.get('trends')} mapped {cat} trends in TrendsMesh evidence ({E(', '.join(report['sample']['platforms']) or 'unknown platform')} only). A typical active trend gained {ctx.get('median_new')} of them; "2×" means twice that. Bands rank a topic among {cat} topics and a hook among all {ctx.get('hooks_pool', '')} rising hooks. Raw counts sit under each card.</p></header>
{lead}
<section><div class="sec-head"><h2>Moved by review</h2><p>The numbers put these in one stage; reading the evidence moved them.</p></div><ul class="moves">{moves}</ul></section>
{tables}
<section><div class="sec-head"><h2>How the category was mapped</h2><p>{mapped} (relevant = search match score ≥ {cmap['min_match']:g}). Hooks were kept when their evidence videos are about {cat}.</p></div>
<div class="tw"><table><tr><th>Search</th><th>Parent</th><th class="r">Relevant results</th><th class="r">Trends kept here</th><th></th></tr>{qrows}</table></div>
<details><summary>Left out ({len(cmap['dropped'])}) and why</summary><ul class="small-print">{dropped}</ul></details></section>
<section><div class="sec-head"><h2>How sure are we</h2><p>Backtest: stages computed with the evidence known on a past date, then the new creators that joined in the next 14 days. A good rule puts more growth in "act now" than in "past its peak".</p></div>
<div class="tw"><table><tr><th>Reference date</th><th>Stage then</th><th class="r">Trends</th><th class="r">Median new creators after</th><th class="r">Share with 3+ new</th></tr>{bt_rows}</table></div>
<p class="small-print">Limits: evidence is a sample; most trends have 5–50 creators, so single weeks are noisy. Trends that ended before today are not in the pool, which flatters every stage. A trend whose views come mostly from one account is not counted as spreading, however many creators it has. "Too late" includes crowded trends that still add creators: they grow, but there is little room left. When the stage rule was calibrated, the growth ratio alone did not predict anything; the count of new creators and how recently they posted did.</p></section>
</div>
{digest_view}
{paid_view}
<footer class="small-print">Built by the TrendsMesh trend-research playbook. Trend data: TrendsMesh, {E(day(p['as_of']))}. {paid_note} Valid until {E(valid_until)}.</footer>
</main>
{SCRIPT}
</body></html>"""
