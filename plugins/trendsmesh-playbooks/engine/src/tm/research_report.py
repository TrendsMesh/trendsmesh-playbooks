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
- the page's fixed words are the `report` keys of data/i18n/en.yaml (months: `common`), in the run's working
  language when its table has all of them, else in English with a warning (`page_language`, issue #3);
  report.json keeps the original's English;
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
- the page is the shared run page (tm.run_page, issue #60): its top bar and theme, the report as its content
  (research_report.css styles only `.report`), and the run's settled check-ins read-only under it; it saves
  nothing. No Google Fonts: every view of a shared page would call Google (GDPR), so the theme's system
  fallbacks are used;
- links to videos are http(s) only (else no link), every text is escaped, and the thumbnails stop
  at the Artifact tool's file limit (`page.MAX_FILES`, less index.html and report.json): the ones left
  out count as missing.
"""

from __future__ import annotations

import copy
import html
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from tm import (i18n, json_schema, manifest, page, research_checks, research_config, research_digest,
                research_growth, research_map, trends)
from tm.runfolder import RunFolder
from tm.stops import Stop

PAGE = research_digest.PAGE
SCHEMA = "pb4-report/1"
SCHEMA_FILE = Path(__file__).with_name("schemas") / "pb4_report.schema.json"
CSS_FILE = Path(__file__).with_name("research_report.css")
PAID_STEM = "ad_library_summary"
SOURCE = "tm research report"
AREAS = ("report", "common")         # the page's words (data/i18n/en.yaml): its own and the month names
RECENT_DAYS = 45                     # the cards' thumbnails: videos of the 45 days before as_of first

# The page's fixed words are keys of the string table, read in the run's working language (issue #3);
# report.json keeps the original's English (the constants below are those words, for it and for tests).
LABEL = research_growth.LABEL
LABEL_KEY = {"act_now": "report.bucket_act_now", "still_rising": "report.bucket_still_rising",
             "too_late": "report.bucket_too_late", "past_peak": "report.bucket_past_peak"}
NOTE_KEY = {"act_now": "report.note_act_now", "still_rising": "report.note_still_rising",
            "too_late": "report.note_too_late", "past_peak": "report.note_past_peak"}
PAID_KEY = {"none": "report.paid_none", "found": "report.paid_found", "crowded": "report.paid_crowded",
            "not_checkable": "report.paid_not_checkable"}
VIEW_KEY = {"report": "report.view_report", "digest": "report.view_digest", "paid": "report.view_paid"}
NUMBER_KEY = {2: "report.number_2", 3: "report.number_3", 4: "report.number_4", 5: "report.number_5",
              6: "report.number_6"}
# A trend's data as the run stores it (research_growth, the card), shown in the page language; a value not
# listed is shown as stored, and the run files keep the stored value (issue #3).
_V = "report.value."
BAND_KEY = {"top 10%": _V + "band_top_10", "top 25%": _V + "band_top_25", "top half": _V + "band_top_half",
            "lower half": _V + "band_lower_half"}
CONFIDENCE_KEY = {c: _V + f"confidence_{c}" for c in ("high", "medium", "low")}
STATUS_KEY = {s: _V + f"status_{s}" for s in ("confirmed", "unconfirmed", "contradicted")}
KIND_KEY = {k: _V + f"kind_{k}" for k in ("hook", "topic", "sound", "format")}
WHY_KEY = {"views come mostly from one account": _V + "why_one_account",
           "broad creator base, no dominant account, confirmed": _V + "why_broad",
           "some limits: see the risk line": _V + "why_some_limits"}
_FEW_CREATORS = re.compile(r"only (\d+) creators in evidence")
_EN = i18n.english()
BUCKET_NOTE = {b: _EN[k] for b, k in NOTE_KEY.items()}
PAID_LABEL = {c: _EN[k] for c, k in PAID_KEY.items()}
VIEWS = {v: _EN[k] for v, k in VIEW_KEY.items()}
assert set(VIEWS) == set(research_config.PICK_OUTPUTS.values()) and set(LABEL_KEY) == set(LABEL)
NO_ACT_NOW = _EN["report.no_act_now"]
E = html.escape


@lru_cache(maxsize=1)
def _en() -> i18n.Translator:
    """The English table: report.json's words, and the page's when no other language is given."""
    return i18n.translator(i18n.ENGLISH)


def page_language(run: RunFolder) -> i18n.PageLang:
    """The language to build the page in: the run's working language when its table has every word of the
    page (the report's and the shared run page's, issue #60), else English (with `.warning` for what `tm research
    report` says)."""
    from tm import run_page   # here, not at the top: see _on_the_run_page
    return i18n.page_lang(i18n.run_languages(run).working, run_page.words.AREA, *AREAS)

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

def day(value: date | str | None, tr: i18n.Translator | None = None) -> str:
    """`18 Nov 2026`, the same on every OS and locale (the month's name from the table, in `tr`'s
    language, else English); an ISO text is read first (an unreadable one is shown as it is)."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    if not isinstance(value, date):
        return ""
    return f"{value.day} {(tr or _en())(f'common.month_{value.month}')} {value.year}"


def fmt(n) -> str:
    n = n or 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def kind(t: dict) -> str:
    return (t.get("kind") or "").replace("_trend", "")


def shown(value, keys: dict, tr: i18n.Translator | None = None):
    """A stored value (`keys`: the stored English -> its key) in `tr`'s language, else as it is stored."""
    return (tr or _en())(keys[value]) if isinstance(value, str) and value in keys else value


def why(text, tr: i18n.Translator | None = None):
    """A trend's confidence_why (research_growth.confidence's words) in `tr`'s language, else as stored."""
    tr = tr or _en()
    few = _FEW_CREATORS.fullmatch(text) if isinstance(text, str) else None
    if few:
        return tr.plural(_V + "why_few_creators", int(few.group(1)), n=int(few.group(1)))
    return shown(text, WHY_KEY, tr)


def first_up(text: str) -> str:
    """The first letter upper case, the rest as it is."""
    return text[:1].upper() + text[1:]


def count(value) -> int | float:
    """A count for the form of its words (`tr.plural`): the number, else 0 (a count the data does not give)."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def spread(g: dict, tr: i18n.Translator | None = None) -> tuple[str, str]:
    tr = tr or _en()
    s = g.get("top_creator_share", 0)
    if s > 0.6:
        return tr("report.spread_one"), tr("report.spread_one_sub", share=round(s * 100), creator=g.get('top_creator'))
    if s > 0.4:
        return tr("report.spread_few"), tr("report.spread_few_sub", share=round(s * 100))
    return tr("report.spread_broad"), tr("report.spread_broad_sub", share=max(round(s * 100), 1))


def _label(bucket: str, tr: i18n.Translator | None = None) -> str:
    """A stage's name (research_growth.LABEL) in `tr`'s language, else English; an unknown one as it is."""
    return (tr or _en())(LABEL_KEY[bucket]) if bucket in LABEL_KEY else bucket


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
                 trends_by_id: dict[str, dict], paid: dict[str, dict], paid_checked: bool, hooks_not_read: int = 0,
                 tr: i18n.Translator | None = None):
        self.tr = tr or _en()                    # the page's words, in the language it is built in
        self.run, self.out, self.category, self.market, self.as_of = run, out, category, market, as_of
        self.sample, self.trends, self.paid, self.paid_checked = sample, trends_by_id, paid, paid_checked
        self.hooks_not_read = hooks_not_read     # issue #8: only the shortlisted hooks' videos were read
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

    def strip_html(self, th: list[dict], alt: str = "report.video_by") -> str:
        tr = self.tr
        out = []
        for x in th:
            inner = (f"<img src='{E(x['src'])}' alt='{E(tr(alt, creator=x['creator'] or ''))}' loading='lazy'>"
                     f"<span>{tr('report.thumb_views', views=fmt(x['views']), date=E(day(x['date'], tr)))}</span>")
            url = safe_url(x["url"])
            out.append(f"<a class='thumb' href='{E(url)}' target='_blank' rel='noopener'>{inner}</a>" if url
                       else f"<span class='thumb'>{inner}</span>")
        return "".join(out)

    # the report view -------------------------------------------------------------------------

    def momentum(self, t: dict) -> tuple[str, str]:
        rel, tr = t.get("relative") or {}, self.tr
        hooks = "report.band_hooks_read" if self.hooks_not_read else "report.band_all_hooks"
        if t.get("kind") == "hook_trend" and "rising_of" in rel:      # issue #58: its place in the rising list
            hooks = "report.band_rising" if rel.get("band") else "report.band_not_rising"
        pool = hooks if t.get("kind") == "hook_trend" else "report.band_topics"
        band = first_up(shown(rel.get('band') or '—', BAND_KEY, tr))
        n = rel.get("rising_of")                                          # a count only in band_rising
        said = (tr.plural(pool, count(n), band=band, category=self.category, n=n) if pool in tr.counts
                else tr(pool, band=band, category=self.category, n=n))
        return (said,
                tr("report.velocity", index=rel.get('velocity_index', 0), category=self.category))

    def hooks_section(self) -> str:
        """Issue #58 (item 5 of #8): the shortlisted hooks in two lists, those already used in the category
        and the transfers (they fit, nobody in the category uses them yet), each in fit order with its fit,
        band, category videos and Ad Library verdict. Empty for a growth file from before the hooks path
        marked a hook's use (0.11), so an older run's page renders as it did."""
        tr, cat = self.tr, E(self.category)
        hooks = sorted((t for t in self.trends.values() if t.get("kind") == "hook_trend"
                        and (t.get("plugin") or {}).get("use") in ("in_category", "transfer")),
                       key=lambda t: (t["plugin"].get("fit_rank") or 99, t["name"]))
        if not hooks:
            return ""
        ads = {"competitor_found": "report.hooks_ad_competitor", "none_found": "report.hooks_ad_none"}

        def item(t: dict) -> str:
            p = t["plugin"]
            ad = p.get("ad_library") or {}
            verdict = (tr(ads[ad["verdict"]], advertisers=E(", ".join(ad.get("advertisers") or [])))
                       if ad.get("verdict") in ads else tr("report.hooks_ad_not_checked"))
            used = (tr("report.hooks_category_videos", category=cat,         # a map's row: under plugin
                       n=t.get("category_videos", p.get("category_videos")) or 0,
                       checked=t.get("videos_checked", p.get("videos_checked")) or 0) if p["use"] == "in_category"
                    else f"<span class='pill k-hook'>{tr('report.hooks_transfer')}</span>")
            fit = p.get("fit")
            pills = (f"<span class='pill'>{tr('report.hooks_fit', fit=f'{fit:.1f}')}</span>" if isinstance(fit, (int, float))
                     else "") + f"<span class='pill'>{E(self.momentum(t)[0])}</span>"
            why = f"<br><span class='small-print'>{E(p['why'])}</span>" if p.get("why") else ""
            return f"<li><b>{E(t['name'])}</b> {pills} {used} · {verdict}{why}</li>"

        def part(head: str, rows: list[dict], note: str, none: str) -> str:
            body = (f"<ul class='hooks'>{''.join(item(t) for t in rows)}</ul>" if rows
                    else f"<p class='small-print'>{tr(none, category=cat)}</p>")
            return (f"<h3>{tr(head, category=cat)} · {len(rows)}</h3>"
                    + (f"<p class='small-print'>{tr(note, category=cat)}</p>" if note else "") + body)

        used = [t for t in hooks if t["plugin"]["use"] == "in_category"]
        transfer = [t for t in hooks if t["plugin"]["use"] == "transfer"]
        return (f"<section id='hooks'><div class='sec-head'><h2>{tr('report.hooks_heading', category=cat)}</h2>"
                f"<p>{tr('report.hooks_note', category=cat)}</p></div>"
                + part("report.hooks_used_heading", used, "", "report.hooks_used_none")
                + part("report.hooks_transfer_heading", transfer, "report.hooks_transfer_note",
                       "report.hooks_transfer_none")
                + "</section>")

    def glance(self, t: dict, paid: dict | None) -> str:
        """TR10 (v02): position in the sample first; raw counts behind 'Raw counts'. Each cell's class is
        its English label's first word, in every language."""
        g, ctx, tr = t["growth"], self.sample, self.tr
        m, msub = self.momentum(t)
        sp, spsub = spread(g, tr)
        cells = [
            ("report.glance_momentum", m, msub),
            ("report.spread", sp, spsub),
            ("report.glance_reach", tr("report.reach_views", views=fmt(g.get('views_total'))),
             tr.plural("report.reach_videos", count(g.get('videos_known', 0)), videos=g.get('videos_known', 0))),
            ("report.glance_freshness", tr("report.fresh_new_video", days=g.get('last_seen_days', '—')),
             tr("report.fresh_seen", days=g.get('age_days', '—'))),
            ("report.confidence", first_up(shown(t.get("confidence") or "—", CONFIDENCE_KEY, tr)),
             tr("report.confidence_sub", why=why(t.get('confidence_why', ''), tr),
                status=shown(t.get('status'), STATUS_KEY, tr))),
            ("report.glance_ad_library", (paid or {}).get("verdict", tr("report.not_checked")),
             (paid or {}).get("query_note", "")),
        ]
        raw = (f"<details class='raw'><summary>{tr('report.raw_summary')}</summary><p>"
               + tr.plural("report.raw_counts", count(g.get('new_recent', 0)), new_recent=g.get('new_recent', 0), active=ctx.get('creators_active'),
                    category=E(self.category), new_base=g.get('new_base', 0), creators=g.get('creators', 0),
                    median=fmt(g.get('median_views')))
               + "</p></details>")
        return "<dl class='glance'>" + "".join(
            f"<div class='c-{E(_en()(k, market=self.market).split()[0].lower())}'>"
            f"<dt>{E(tr(k, market=self.market))}</dt><dd class='num'>{E(b)}</dd>"
            f"<dd class='sub'>{E(c)}</dd></div>" for k, b, c in cells) + "</dl>" + raw

    def card(self, p: dict, big: bool, valid_until: str, total: float | None, scale: tuple[float, float]) -> str:
        t, tr = self.trends[p["id"]], self.tr
        th = self.thumbs(t["id"], 3 if big else 2)
        strip = self.strip_html(th, "report.evidence_video_by")
        tags = f"<span class='pill k-{E(kind(t))}'>{E(shown(kind(t), KIND_KEY, tr))}</span><span class='pill'>{E(t.get('group') or '')}</span>"
        if p.get("maturity"):
            tags += f"<span class='pill soft'>{E(p['maturity'])}</span>"
        body = "".join(f"<p><b>{tr(lab)}</b> {E(p[k])}</p>" for lab, k in
                       (("report.card_what", "what"), ("report.card_how", "how"), ("report.card_risk", "risk"))
                       if p.get(k))
        score = ("<p class='valid'>" + tr("report.fit_score", total=format(total, "g"), low=format(scale[0], "g"),
                                          high=format(scale[1], "g"), criteria=len(research_config.CRITERIA))
                 + "</p>" if total is not None else "")
        return (f"<article class='card {'big' if big else ''}' id='t-{_short_id(t)}'><header><h3>{E(t['name'])}</h3>"
                f"<div class='tags'>{tags}</div></header>{self.glance(t, self.paid.get(p['id']))}"
                f"<div class='strip'>{strip}</div>{body}{score}"
                f"<p class='valid'>{tr('report.card_valid', date=E(valid_until), id=_short_id(t))}</p></article>")

    def table(self, rows: list[dict], moved: dict, picked: set) -> str:
        tr = self.tr
        head = (f"<tr><th>{tr('report.col_trend')}</th><th>{tr('report.col_type')}</th><th>{tr('report.col_group')}</th>"
                f"<th>{tr('report.col_momentum')}</th><th class='r'>{tr('report.col_typical')}</th>"
                f"<th>{tr('report.spread')}</th><th class='r'>{tr('report.col_reach')}</th>"
                f"<th class='r'>{tr('report.col_new_video')}</th><th>{tr('report.confidence')}</th>"
                f"<th>{tr('report.col_note')}</th><th class='r raw'>{tr('report.col_raw')}</th></tr>")
        body = []
        for t in rows:
            g, rel = t["growth"], t.get("relative") or {}
            note = t.get("seasonal_over") or moved.get(t["id"], "")
            name = f"<a href='#t-{_short_id(t)}'>{E(t['name'])}</a>" if t["id"] in picked else E(t["name"])
            body.append(f"<tr><td>{name}</td><td>{E(shown(kind(t), KIND_KEY, tr))}</td><td>{E(t.get('group') or '')}</td>"
                        f"<td>{E(shown(rel.get('band') or '—', BAND_KEY, tr))}</td><td class='r num'>{rel.get('velocity_index', '—')}</td>"
                        f"<td>{E(spread(g, tr)[0])}</td><td class='r num'>{fmt(g.get('views_total'))}</td>"
                        f"<td class='r num'>{g.get('last_seen_days', '—')}</td><td><span class='conf "
                        f"conf-{E(t.get('confidence') or '')}'>{E(shown(t.get('confidence') or '', CONFIDENCE_KEY, tr))}"
                        f"</span></td>"
                        f"<td class='note'>{E(note)}</td><td class='r num raw'>{g.get('new_recent', 0)} / "
                        f"{g.get('new_base', 0)}</td></tr>")
        return f"<div class='tw'><table>{head}{''.join(body)}</table></div>"

    def lens_section(self, lens: dict) -> str:
        items = "".join(f"<li><b>{E(self.trends[i['id']]['name'])}</b> <span class='pill'>"
                        f"{E(_label(self.trends[i['id']]['bucket'], self.tr))}</span> {E(i.get('line') or '')}</li>"
                        for i in lens.get("items") or [])
        return (f"<section id='lens'><div class='sec-head'><h2>{E(lens.get('label') or '')}</h2>"
                f"<p>{E(lens.get('note') or '')}</p></div><ol class='lens'>{items}</ol></section>")

    # the digest view -------------------------------------------------------------------------

    def digest_section(self, dg: dict, prev: dict, reading: dict) -> str:
        """TR8 digest + TR9 call check (v02): the week in one minute (agent), numbers strip, what to do
        this week (agent), last week's calls with this week's videos, moved up and new on the radar
        as cards with this week's videos, cooling down grouped by reason, ended or merged."""
        trends_, tr = self.trends, self.tr
        since = dg["prev"]["ref"]
        days = (date.fromisoformat(dg["now"]["ref"]) - date.fromisoformat(since)).days
        pt = prev.get("trends", {})
        then = day(dg["prev"].get("as_of"), tr)

        def mini(t: dict, tid: str, head: str, line: str, th_n: int = 3, was: str | None = None) -> str:
            rel = t.get("relative") or {}
            pd = self.paid.get(tid)
            th = self.thumbs_since(tid, since, th_n)
            chips = (f"<span class='pill b-{E(str(t.get('bucket')))}'>{E(_label(t.get('bucket') or '', tr))}</span>"
                     f"<span class='pill'>{E(shown(rel.get('band') or '—', BAND_KEY, tr))}</span><span class='pill'>"
                     f"{E(shown(kind(t), KIND_KEY, tr))} · "
                     f"{E(t.get('group') or '')}</span>" + (f"<span class='pill'>{E(pd['verdict'])}</span>" if pd else ""))
            vids = f"<div class='strip'>{self.strip_html(th)}</div>" if th else \
                f"<p class='sub'>{tr('report.no_new_video')}</p>"
            title = E(t["name"]) + (f" <span class='sub'>{tr('report.was', name=E(was))}</span>" if was else "")
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
                mark, verdict = "?", tr("report.call_unknown")
            else:
                mark, verdict = ("✓", tr("report.call_kept")) if c["held"] else ("✗", tr("report.call_stalled"))
            if now_id is None:            # it left this week's map (Review Focus 2)
                calls_html += (f"<article class='card dgcard'><header><p class='kicker'>"
                               f"{tr('report.call_kicker', mark=mark, verdict=E(verdict))}</p><h3>{E(c['name'])}</h3>"
                               f"</header><p>{tr('report.call_off_map')}</p></article>")
                continue
            t_now = trends_[now_id]
            now_b = t_now["bucket"]
            idx = (t_now.get("relative") or {}).get("velocity_index")
            stage = (tr("report.call_still_act_now") if now_b == "act_now"
                     else tr("report.call_now_stage", stage=_label(now_b, tr).lower()))
            note = (f"{stage}" + (f": {t_now['seasonal_over']}" if t_now.get("seasonal_over") else "")
                    + (". " + tr("report.call_fortnight", index=idx, category=self.category)
                       if idx is not None else ".") + f" {what(now_id)}")
            calls_html += mini(t_now, now_id, tr("report.call_kicker", mark=mark, verdict=E(verdict)), note, 2,
                               was=c["name"] if now_id != c["id"] else None)

        up_html = "".join(mini(trends_[x["id"]], x["id"], tr("report.moved_up_kicker", was=E(_label(x['from'], tr)),
                                                             now=E(_label(x['to'], tr))),
                               what(x["id"])) for x in dg["up"] if x["id"] in trends_)
        new_html = "".join(mini(trends_[x["id"]], x["id"], tr("report.new_on_radar"), what(x["id"])) for x in
                           sorted(new_live, key=lambda x: -((trends_[x["id"]].get("relative") or {}).get("velocity_index")
                                                            or 0)))

        def then_stage(x: dict) -> str:
            """Its stage last week: the row's own, else the previous snapshot's under its id or, for a
            trend under a new id, under the id it had (`plugin.was_id`); "—" when unknown."""
            was = pt.get(x["id"]) or pt.get((x.get("plugin") or {}).get("was_id")) or {}
            bucket = x.get("from") or was.get("bucket")
            return _label(bucket, tr) if bucket else "—"

        def rows(items, why):
            return "".join(
                f"<tr><td>{E(x.get('name') or trends_[x['id']]['name'])}</td><td>{E(then_stage(x))} → "
                f"{E(_label((trends_.get(x['id']) or {}).get('bucket') or x.get('to') or '', tr))}</td>"
                f"<td class='note'>{E(why(x))}</td></tr>" for x in items)
        cool = rows(cooled, lambda x: seasonal(x) or "") + rows(slowing, lambda x: tr("report.fewer_new_creators"))
        plug = dg.get("plugin") or {}
        ended_checked = plug.get("ended_checked", True)
        ended = "".join(f"<li>{E(x['name'])}</li>" for x in dg["ended"])
        if not ended_checked:
            why = (tr("report.ended_rebuilt") if prev.get("rebuilt") is True
                   else tr("report.ended_no_pool"))
            ended = f"<li>{tr('report.ended_not_checked', why=why)}</li>"
        unknown = (plug.get("unknown_calls") or {}).get("act_now")
        if not isinstance(unknown, int):
            unknown = sum(c["held"] is None for c in held)
        reid = "".join(f"<li>{E(x['was'])} → {E(x['name'])}</li>" for x in dg.get("reidentified", []))
        summary = "".join(f"<li>{E(s)}</li>" for s in reading.get("summary", []))
        todo = "".join(f"<li>{E(s)}</li>" for s in reading.get("todo", []))
        kept = sum(c['held'] is True for c in held)
        stats = [(f"{kept}/{a_n}", tr("report.stat_calls_unknown", unknown=unknown) if unknown
                  else tr("report.stat_calls")),
                 (str(len(dg["up"])), tr.plural("report.stat_moved_up", len(dg["up"]))),
                 (str(len(new_live)), tr.plural("report.stat_new_rising", len(new_live))),
                 (str(len(cooled)), tr.plural("report.stat_seasonal", len(cooled))),
                 (str(len(slowing)), tr.plural("report.stat_slowing", len(slowing))),
                 (str(len(dg["ended"])) if ended_checked else "—",
                  tr.plural("report.stat_ended", len(dg["ended"]) if ended_checked else 0))]
        strip = "".join(f"<div class='count'><b>{E(a)}</b><span>{E(b)}</span></div>" for a, b in stats)
        if prev.get("rebuilt") is True:
            compared = tr.plural("report.compared_rebuilt", days, then=E(then), days=days)
        else:
            compared = tr.plural("report.compared", days, then=E(then), days=days)
        also = ("<p class=small-print>" + tr("report.also_new", names=E(", ".join(
            trends_[x["id"]]["name"] + " (" + _label(trends_[x["id"]]["bucket"], tr).lower() + ")" for x in new_other)))
            + "</p>" if new_other else "")
        none = f"<p>{tr('report.none')}</p>"
        reid_html = (f"<p class=small-print>{tr('report.reidentified')}</p><ul class=small-print>{reid}</ul>"
                     if reid else "")
        return (f"<section id='since'><p class='sample'>{compared}</p><div class='counts six'>{strip}</div></section>"
                f"<section><div class='sec-head'><h2>{tr('report.week_in_a_minute')}</h2></div>"
                f"<ul class='reading big'>{summary}</ul></section>"
                f"<section style='--c:var(--act)'><div class='sec-head'><h2>{tr('report.todo_heading')}</h2></div>"
                f"<ol class='todo'>{todo}</ol></section>"
                f"<section style='--c:var(--rise)'><div class='sec-head'><h2>{tr('report.moved_up')}</h2>"
                f"<p>{tr('report.moved_up_note', then=E(then))}</p></div><div class='cards small'>{up_html or none}</div>"
                "</section>"
                f"<section style='--c:var(--rise)'><div class='sec-head'><h2>{tr('report.new_on_radar')}</h2>"
                f"<p>{tr('report.new_on_radar_note', then=E(then))}</p></div>"
                f"<div class='cards small'>{new_html or none}</div>{also}</section>"
                f"<section style='--c:var(--act)'><div class='sec-head'><h2>{tr('report.calls_heading')}</h2>"
                f"<p>{tr('report.calls_note', then=E(then))}</p></div>"
                f"<div class='cards small'>{calls_html or none}</div></section>"
                f"<section style='--c:var(--late)'><div class='sec-head'><h2>{tr('report.cooling_heading')}</h2></div>"
                f"<div class='tw'><table><tr><th>{tr('report.col_trend')}</th><th>{tr('report.col_stage')}</th>"
                f"<th>{tr('report.col_why')}</th></tr>{cool}</table></div></section>"
                f"<section style='--c:var(--past)'><div class='sec-head'><h2>{tr('report.ended_heading')}</h2>"
                f"<p>{tr('report.ended_note', then=E(then))}</p></div><ul class='small-print'>{ended}</ul>"
                f"{reid_html}"
                "</section>")

    # the paid view ---------------------------------------------------------------------------

    def paid_view(self, reading: list[str]) -> str:
        """TR7 view: organic stage x presence in paid ads, for rising trends and the largest slowing ones."""
        trends_, paid, tr = self.trends, self.paid, self.tr
        rows = {"rising": [t for t in trends_.values() if t["bucket"] in ("act_now", "still_rising")],
                "slowing": [t for t in trends_.values() if t["bucket"] == "too_late" and t["id"] in paid]}
        cols = ["none", "found", "crowded"]
        head = "".join(f"<th>{E(tr(PAID_KEY[c]))}</th>" for c in cols)
        none = tr("report.none")

        def cell(ts):
            items = []
            for t in sorted(ts, key=lambda t: -((t.get("relative") or {}).get("velocity_index") or 0)):
                pd = paid[t["id"]]
                adv = ", ".join(str(a).split(" (")[0] for a in (pd["advertisers"] or [])[:3])
                items.append(f"<li><b>{E(t['name'])}</b> <span class='pill b-{E(t['bucket'])}'>"
                             f"{E(_label(t['bucket'], tr))}</span>"
                             f"<span class='sub'>{E(shown((t.get('relative') or {}).get('band') or '', BAND_KEY, tr))}"
                             f"{' · ' + E(adv) if adv else ''}</span></li>")
            return "<ul class='cell'>" + "".join(items) + "</ul>" if items else f"<p class='sub'>{none}</p>"

        body = ""
        for key, label in (("rising", f"{tr('report.paid_rising')}<br><span class='sub'>"
                                      f"{tr('report.paid_rising_sub')}</span>"),
                           ("slowing", f"{tr('report.paid_slowing')}<br><span class='sub'>"
                                       f"{tr('report.paid_slowing_sub')}</span>")):
            body += f"<tr><th class='rowh'>{label}</th>" + "".join(
                f"<td class='q q-{key}-{c}'>{cell([t for t in rows[key] if paid.get(t['id'], {}).get('level') == c])}</td>"
                for c in cols) + "</tr>"
        hooks = [t for t in trends_.values() if paid.get(t["id"], {}).get("level") == "not_checkable"]
        unchecked = [t for t in rows["rising"] if t["id"] not in paid]
        read = "".join(f"<li>{E(x)}</li>" for x in reading)
        if self.paid_checked:
            what = tr("report.paid_checked", market=E(self.market))
        else:                                       # V22: the Meta Ads connector was unavailable
            what = tr("report.paid_unchecked", market=E(self.market))
        not_checked = (f"<b>{tr('report.paid_not_checked')}</b> " + E(', '.join(t['name'] for t in unchecked)) + ". "
                       if unchecked else "")
        return (f"<div class='sec-head'><h2>{tr('report.paid_heading')}</h2><p>{tr('report.paid_intro')} "
                f"{what}</p></div><ul class='reading'>{read}</ul>"
                f"<div class='tw'><table class='matrix'><tr><th></th>{head}</tr>{body}</table></div>"
                f"<p class='small-print'><b>{tr('report.paid_hooks')}</b> "
                f"{E(', '.join(t['name'] for t in hooks)) or none}. "
                f"{not_checked}"
                f"{tr('report.paid_foreplay')}</p>")


# --- build ------------------------------------------------------------------------------------

def _paid_rows(raw: list, rows: dict[str, dict], market: str, tr: i18n.Translator | None = None) -> dict[str, dict]:
    """The Ad Library checks by trend id, their words in `tr`'s language (English for report.json)."""
    tr = tr or _en()
    paid = {}
    for c in raw:
        if isinstance(c, dict) and c.get("trend_id") in rows and c.get("level") in PAID_KEY:
            paid[c["trend_id"]] = {"level": c["level"], "verdict": tr(PAID_KEY[c["level"]]),
                                   "query_note": tr("report.paid_query", query=c['query'], market=market)
                                   if c.get("query") else tr("report.paid_needs_foreplay"),
                                   "advertisers": c.get("advertisers", []), "estimated": c.get("estimated"),
                                   "example_id": c.get("example_id"), "note": c.get("note", "")}
    return paid


def build(run: RunFolder, picks_path: Path, *, paid: Path | None = None, prev_snapshot: Path | None = None,
          backtests: list[Path] = (), cfg: dict) -> Path:
    """Build the page into a new 04_final/report_vNN/ (index.html, report.json, assets/) and return
    the folder. Nothing is written when an input is missing or the report breaks its schema."""
    cfg = research_map.settings(cfg)
    tr = i18n.translator(page_language(run).lang)      # the page's words; report.json keeps the English
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
    valid_until_page = day(as_of + timedelta(days=cfg["picks"]["valid_days"]), tr)

    paid_file = Path(paid) if paid else run.latest(trends.RESEARCH, PAID_STEM, "json")
    summary = _json(paid_file, "the Ad Library summary") if paid_file else {}
    paid_raw = summary.get("checks") or []
    paid_checked = bool(paid_file) and summary.get("checked") is not False
    # the review's moves, applied (research_checks.after_moves): the reference tool changed the rows in place
    stage = research_checks.after_moves(growth_rows, picks)
    rows = [{**copy.deepcopy(t), "bucket": stage[t["id"]]} for t in gj["trends"]]
    by_id = {t["id"]: t for t in rows}
    paid_rows = _paid_rows(paid_raw, by_id, market)
    moves_made = [m for m in picks.get("moves") or []
                  if isinstance(m, dict) and stage.get(m.get("id")) != growth_rows.get(m.get("id"), {}).get("bucket")]
    moved = {m["id"]: _en()("report.moved_by_review", stage=_label(m['from']), why=m.get('why', '')) for m in moves_made}
    moved_page = {m["id"]: tr("report.moved_by_review", stage=_label(m['from'], tr), why=m.get('why', ''))
                  for m in moves_made}
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
    hook_use = {u: [t["id"] for t in sorted(rows, key=lambda t: (t.get("plugin") or {}).get("fit_rank") or 99)
                    if t.get("kind") == "hook_trend" and (t.get("plugin") or {}).get("use") == u]
                for u in ("in_category", "transfer")}
    if any(hook_use.values()):                     # issue #58: the hooks section's two lists
        report["plugin"] = {"hooks": hook_use}
    wrong = schema_problems(report)
    if wrong:
        raise Stop(f"The report breaks its schema ({SCHEMA}): {'; '.join(wrong)}. Fix the input it comes from, "
                   "then build again; the run continues from the same place.")

    out = page.new_folder(run, PAGE)
    pg = _Page(run, out, category=category, market=market, as_of=as_of, sample=ctx, trends_by_id=by_id,
               paid=_paid_rows(paid_raw, by_id, market, tr), paid_checked=paid_checked,
               hooks_not_read=len((gj.get("plugin") or {}).get("hooks_not_read") or []), tr=tr)
    prev = prev_snapshot if prev_snapshot is not None else _prev_snapshot(run, digest)
    prev_snap = _json(Path(prev), "the previous snapshot") if digest is not None and prev else {}
    title, css, body = _render(pg, picks, report, cmap, gj, by, moved_page, picked, totals, scale, backtest_data,
                               digest, prev_snap, valid_until_page)
    (out / "index.html").write_text(_on_the_run_page(run, out, title, css, body), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, page.FINAL, SOURCE,
                    params={"picks": Path(picks_path).name, "paid": paid_file.name if paid_file else None,
                            "outputs": outputs, "thumbnails_missing": pg.thumbs_missing})
    return out


def _on_the_run_page(run: RunFolder, out: Path, title: str, css: str, body: str) -> str:
    """The report on the shared run page (issue #60): the TrendsMesh top bar and theme, the report as the page's
    content, and the run's check-ins under it, settled ones as read-only summaries (an open one, put on the page
    with `tm page build --ask`, says to answer in chat). The page saves nothing (`local`): the report is read-only,
    and it is never published while a check-in about it is open. No Google Fonts: every view of a shared page would
    call Google (GDPR), so the theme's system fallbacks are used.

    The run page is imported here, not at the top: it loads every playbook's page code, and this module is loaded
    by the Organic AI video engine (organic -> audience -> ... -> seeds -> research_report), so a top-level import
    made a cycle that broke `tm tool deliver`, `tm kit` and ten other modules loaded first
    (test_imports.py)."""
    from tm import run_page
    m, _ = run_page.model(run, out, local=True)
    m.update(title=title, css=css, body=body, fonts=False,
             footer=run_page.words.t("footer.built_from", page_language(run).lang, run=run.path.name, when=m["updated"]))
    return run_page.template.render(m)


def _render(pg: _Page, picks: dict, report: dict, cmap: dict, gj: dict, by: dict, moved: dict, picked: set,
            totals: dict, scale: tuple[float, float], backtest_data: list[dict], digest: dict | None,
            prev_snap: dict, valid_until: str) -> tuple[str, str, str]:
    """The report's title, its CSS and its HTML (the views and their switch): the shared run page's content."""
    category, market, trends_, tr = pg.category, pg.market, pg.trends, pg.tr
    ctx, p = gj["params"]["category"], gj["params"]
    act, rising = picks.get("act_now") or [], picks.get("still_rising") or []
    big = "".join(pg.card(x, True, valid_until, totals.get(x["id"]), scale) for x in act)
    small = "".join(pg.card(x, False, valid_until, totals.get(x["id"]), scale) for x in rising)
    digest_html = pg.digest_section(digest, prev_snap, picks.get("digest_reading") or {}) if digest is not None else ""
    lens = pg.lens_section(picks["lens"]) if isinstance(picks.get("lens"), dict) else ""
    n_act = tr(NUMBER_KEY[len(act)]) if len(act) in NUMBER_KEY else str(len(act))
    other = "".join(f"<li><b>{E(trends_[o['id']]['name'])}</b>: {E(o.get('note') or '')}</li>"
                    for o in picks.get("act_now_other") or [])
    moves = "".join(f"<li><b>{E(trends_[m['id']]['name'])}</b>: {E(_label(m.get('from') or '', tr))} → "
                    f"{E(_label(m.get('to') or '', tr))}. {E(m.get('why') or '')}</li>" for m in picks.get("moves") or [])
    counts = "".join(f"<a class='count b-{b}' href='#{b.replace('_', '-')}'><b>{len(by[b])}</b>"
                     f"<span>{_label(b, tr)}</span></a>" for b in LABEL)

    q = cmap["queries"]
    kept_by_sub: dict[str, int] = {}
    for r in cmap["kept"]:
        kept_by_sub[r["sub_category"]] = kept_by_sub.get(r["sub_category"], 0) + 1
    qrows = "".join(f"<tr><td>{E(x['query'])}</td><td>{E(x['parent'] or '—')}</td><td class='r num'>{x['relevant']}</td>"
                    f"<td class='r num'>{kept_by_sub.get(x['query'], 0)}</td>"
                    f"<td>{tr('report.split_further') if x['relevant'] < cmap['min_relevant'] else ''}</td></tr>"
                    for x in sorted(q, key=lambda x: ((x['parent'] or ''), x['query'])))
    dropped = "".join(f"<li>{E(r['name'])}: {E('; '.join(r['dropped_because']))}</li>" for r in cmap["dropped"])
    root = cmap.get("root") or category
    root_relevant = next((x["relevant"] for x in q if x["query"] == root), 0)
    split = any(x.get("parent") for x in q)
    mapped = tr.plural("report.mapped_split" if split else "report.mapped_whole", count(root_relevant),
                       root=E(root), n=root_relevant)

    bt_rows = ""
    for b in backtest_data:
        s = b["summary"]
        bt_rows += "".join(f"<tr><td>{tr('report.backtest_ref', date=E(day(b['ref'], tr)), rule=E(b.get('rule', '')))}"
                           f"</td><td>{_label(k, tr)}</td>"
                           f"<td class='r num'>{s[k]['n']}</td><td class='r num'>{s[k]['median_new']}</td>"
                           f"<td class='r num'>{round((s[k]['share_with_3plus'] or 0) * 100)}%</td></tr>" for k in LABEL)
    if not bt_rows:
        bt_rows = f"<tr><td colspan='5'>{tr('report.no_backtest')}</td></tr>"

    colour = {"act_now": "act", "still_rising": "rise", "too_late": "late", "past_peak": "past"}
    tables = "".join(
        f"<section id='{b.replace('_', '-')}' style='--c:var(--{colour[b]})'><div class='sec-head'><h2>{_label(b, tr)} · "
        f"{len(by[b])}</h2><p>{tr(NOTE_KEY[b])}</p></div>{pg.table(by[b], moved, picked)}</section>" for b in LABEL)
    n_hooks = sum(1 for t in gj["trends"] if t.get("kind") == "hook_trend")
    n_topics = len(gj["trends"]) - n_hooks
    pool = ctx.get("hooks_pool", "")
    hook_pool = (tr("report.hook_pool_read", pool=pool, listed=pool + pg.hooks_not_read) if pg.hooks_not_read
                 else tr("report.hook_pool_all", pool=pool))
    if ctx.get("hooks_rising"):                   # issue #58: a growth file that placed hooks in the rising list
        hook_pool = tr.plural("report.hook_pool_rising", count(ctx["hooks_rising"]), n=ctx["hooks_rising"])
    outputs = report["outputs"]
    nav = "".join(f"<a href='#{o}'>{E(tr(VIEW_KEY[o]))}</a>" for o in outputs)
    cat = E(category)

    still = (f'<section style="--c:var(--rise)"><div class="sec-head"><h2>{tr("report.still_heading")}</h2>'
             f'<p>{tr(NOTE_KEY["still_rising"])}</p></div><div class="cards small">{small}</div></section>')
    watch = (f'<section><div class="sec-head"><h2>{tr("report.watch_next")}</h2></div><p class="callout">'
             f'{E(picks.get("watch_next") or "")}</p></section>')
    others = (f"<div class='small-print'><b>{tr('report.others')}</b><ul>{other}</ul>"
              "</div>" if other else "")
    if act:
        lede = tr.plural("report.lede", len(act), n=first_up(n_act))
        act_html = (f'<section style="--c:var(--act)"><div class="sec-head"><h2>'
                    f'{tr.plural("report.act_on", len(act), n=n_act)}</h2>'
                    f'<p>{tr(NOTE_KEY["act_now"])} {tr("report.act_order", market=E(market))}</p>'
                    f'</div><div class="cards">{big}</div>{others}</section>')
        lead = act_html + lens + still + watch
    else:                                     # V15: one line, and the page leads with still rising
        lede = tr("report.no_act_now")
        lead = still + watch + (f'<section style="--c:var(--act)">{others}</section>' if others else "") + lens
    lede += " " + tr("report.lede_sample", category=cat)

    digest_view = (f'<div class="view" id="view-digest"><header><h1>{tr("report.digest_title", category=cat)}</h1>'
                   f'<div class="meta"><span>{E(picks["market"])}</span><span>{tr("report.digest_meta")}</span></div>'
                   f'</header>{digest_html}</div>' if digest_html else "")
    paid_view = (f'<div class="view" id="view-paid"><header><h1>{tr("report.paid_title", category=cat)}</h1>'
                 f'<div class="meta"><span>{E(picks["market"])}</span><span>{tr("report.paid_meta")}</span></div>'
                 f'</header><section>{pg.paid_view(picks.get("paid_reading") or [])}</section></div>'
                 if "paid" in outputs else "")
    css = CSS_FILE.read_text(encoding="utf-8")
    paid_note = (tr("report.paid_note_checked", market=E(market)) if pg.paid_checked else
                 tr("report.paid_note_unchecked"))
    title = tr("report.page_title", category=category[:1].upper() + category[1:])     # plain text: escaped once, by the template
    topics, hooks = tr.plural("report.meta_topics", n_topics, n=n_topics), tr.plural("report.meta_hooks", n_hooks, n=n_hooks)
    meta = (f"<span>{tr('report.meta_market', market=E(picks['market']))}</span>"
            f"<span>{tr('report.meta_as_of', date=E(day(picks['as_of'], tr)))}</span>"
            f"<span>{tr('report.meta_mapped', topics=topics, hooks=hooks)}</span>"
            f"<span>{tr('report.meta_source')}</span>")
    sample = tr.plural("report.sample", count(ctx.get('creators_active')), window=p['window'],
                       ref=E(day(p['ref'], tr)), active=ctx.get('creators_active'), trends=ctx.get('trends'),
                       category=cat,
                       platforms=E(', '.join(report['sample']['platforms']) or tr('report.unknown_platform')),
                       median=ctx.get('median_new'), hook_pool=hook_pool)
    mapped_note = tr("report.mapped_note", mapped=mapped, min_match=format(cmap['min_match'], "g"), category=cat)
    footer = tr("report.footer", date=E(day(p['as_of'], tr)), paid_note=paid_note, valid_until=E(valid_until))
    body = f"""<div class="report">
<nav class="views" aria-label="{E(tr('report.nav_label'))}">{nav}</nav>
<div class="view" id="view-report">
<header><h1>{tr('report.h1', category=cat)}</h1>
<div class="meta">{meta}</div>
<p class="lede">{lede}</p>
<div class="counts">{counts}</div>
<p class="sample"><b>{tr('report.sample_head')}</b> {sample}</p></header>
{lead}
<section><div class="sec-head"><h2>{tr('report.moved_heading')}</h2><p>{tr('report.moved_note')}</p></div><ul class="moves">{moves}</ul></section>
{tables}
{pg.hooks_section()}
<section><div class="sec-head"><h2>{tr('report.mapped_heading')}</h2><p>{mapped_note}</p></div>
<div class="tw"><table><tr><th>{tr('report.col_search')}</th><th>{tr('report.col_parent')}</th><th class="r">{tr('report.col_relevant')}</th><th class="r">{tr('report.col_kept')}</th><th></th></tr>{qrows}</table></div>
<details><summary>{tr('report.left_out', n=len(cmap['dropped']))}</summary><ul class="small-print">{dropped}</ul></details></section>
<section><div class="sec-head"><h2>{tr('report.sure_heading')}</h2><p>{tr('report.backtest_note')}</p></div>
<div class="tw"><table><tr><th>{tr('report.col_ref_date')}</th><th>{tr('report.col_stage_then')}</th><th class="r">{tr('report.col_trends')}</th><th class="r">{tr('report.col_median_after')}</th><th class="r">{tr('report.col_share_3')}</th></tr>{bt_rows}</table></div>
<p class="small-print">{tr('report.limits')}</p></section>
</div>
{digest_view}
{paid_view}
<p class="small-print report-foot">{footer}</p>
</div>
{SCRIPT}"""
    return title, css, body
