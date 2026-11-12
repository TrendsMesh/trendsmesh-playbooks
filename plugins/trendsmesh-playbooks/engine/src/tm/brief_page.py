"""The creative brief's shared page (CB12, CB13): the port of the handoff's `build_brief_pack.py`, and
the decisions taken on it.

    render(brief)                  the page's HTML and its views, from brief.json alone (CB10)
    view_text(brief, view)         the texts one view of that page shows (CB13's scan of the creator view)
    build(run, brief_path=None, *, single_file=False)   04_final/brief_pack_vNN/ or brief_pack_vNN.html
    creator_pdf(run, brief)        the creator PDF of the page built from that brief (CB13 reads its text)
    read_decisions(saved)          the decisions in a saved ArtifactData list (or db_list) answer or a copied text
    verdicts(docs, concept_ids)    approved | changes | split | none per concept (plan Decision 8)
    mark_carried(docs, earlier)    rows equal to the earlier decisions file's: carried over, not a new look
    take_decisions / await_decisions / choose    `tm brief decisions`, `await`, `choose`
    built_gap / chosen_gap         the step checks `page_built` and `concepts_chosen`

The port keeps the original's HTML byte for byte (the LD dry run's `brief_pack_v05/index.html` is
rebuilt exactly). Its changes: no backslash inside an f-string expression (Python 3.11); the title
in the decisions script is a JSON string with `'` and `</` escaped; the template is filled in one
pass, so a title holding a placeholder stays text; concept ids are letters, digits, `_` and `-`
(they sit in the page's attributes and selectors); a link that is not http(s) is left out; media
paths are served under `page.asset_name` names and never leave the page folder. `plugin` keys are
never read.

The page folder `04_final/brief_pack_vNN/` and the brief `04_final/brief_pack_vNN.json` share the
stem, as in the reference dry run, and are numbered apart: `page._versions` takes the folder names,
`RunFolder.latest(..., "json")` the files. Each build adds a manifest row (source SOURCE, parent =
the brief file, with the brief's sha256), which `page_built` reads.

Decisions are read only whole (a paged, sorted, filtered or cut db answer is refused, by `tm.page`) and are
matched to the concepts of the brief the published page was built from, which the decisions file
records. The page pre-fills each person's earlier choice and the db keeps it when the page is
republished, so a row equal to the earlier decisions file's is marked `carried`; choosing from the
page refuses a carried approval unless the user kept it in chat (`--keep-carried`). A viewer's decision note is data: it is kept as a string and shown to the user, never
acted on.

The PDFs (issue #10, `tm.brief_pdf`): a folder build prints `pdf/brief_pack-full.pdf` and one PDF per view
from the page's print mode (`render(..., stills=...)`: one view or all, no view bar, sidebar or decision
forms, each animatic as its stills, a banner), and the page's view bar gets two buttons that save them (the
`downloads` capability on claude.ai) or open them (a local file). A computer without a browser builds the
page without them. The print mode and the buttons are the plugin's, over the handoff's template, which stays
verbatim (as `WORDING`); the page without PDFs keeps the reference HTML but for the view bar's hint.
"""

from __future__ import annotations

import base64
import copy
import html
import json
import re
import shutil
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from tm import animatic, brief_checks, brief_pdf, i18n, manifest, page, state, stepchecks, trends
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

FINAL, STEM = brief_checks.FINAL, brief_checks.STEM
PAGE = STEM                                   # the page's name for tm page: 04_final/brief_pack_vNN/
TEMPLATE = Path(__file__).parent / "brief_pack" / "template.html"
SOURCE = "tm brief page"
DECISIONS_SOURCE = "tm brief decisions"
PDF_SOURCE = "tm brief page (PDF)"           # a PDF's manifest row: not a page build, which `SOURCE` rows are
RENDERS = animatic.RENDERS                    # where `tm brief animatic --render` writes
EVIDENCE = "02_research/evidence"             # where `tm brief evidence` saves the thumbnails
MEDIA_DIRS = (RENDERS, EVIDENCE)
WIP = "03_wip"
STAGES = ("G2", "G3", "G4")
SOURCES = ("page", "chat", "rule")
FORMATS = ("9x16", "4x5")
COLLECTION = "decisions"
# HANDOFF §4, verbatim (plan Global Constraints): the page's decisions in the artifact's db; and the downloads.
CAPABILITIES = {"db": {"rules": [{"path": "decisions", "read": "view", "write": "owner"},
                                 {"path": "decisions/{self}", "read": "view", "write": "interact"}]},
                "user": {"scopes": ["profile"]},
                "downloads": True}                    # the PDFs' buttons (issue #10)
AWAITING = ("People are deciding on the page now. A new version would change it under them. Read their decisions "
            "first (`tm brief decisions`), then build again. If the team decided another way (in chat, say), "
            "record it with `tm brief choose --source chat` and stop waiting with `tm brief await --run <run> "
            "--clear`. The run continues from the same place.")

ALL_VIEWS = ['decision', 'strategy', 'creator', 'editor', 'media-buyer']
# Every fixed word of the page is a key of the string table (data/i18n/en.yaml, area brief), in the language the
# page is built in (`render(brief, lang)`; `build` takes the run's working language, `i18n.page_lang`).
VIEW_KEY = {'decision': 'brief.view_decision', 'strategy': 'brief.view_strategy', 'creator': 'brief.view_creator',
            'editor': 'brief.view_editor', 'media-buyer': 'brief.view_media_buyer'}
VIEW_LABEL = {view: i18n.english()[key] for view, key in VIEW_KEY.items()}   # the English, as before
# The views whose phone cards show who a concept is for and its trend line (CB13): every view but the
# creator's, whose cards show the concept's title and phone note alone (issue #15).
HEADER_FACTS_VIEWS = [x for x in ALL_VIEWS if x != 'creator']
TODO = '<span class="todo">{}</span>'               # with brief.to_set
_ID = re.compile(r"[A-Za-z0-9_-]+")
_FILL = re.compile(r"\{\{(TITLE|TITLE_JS|RECIPIENTS|CONCEPT_IDS)\}\}|<!--BODY-->")
# The handoff's template stays verbatim (TEMPLATE); the plugin's own wording goes over it here, as organic video's
# pages do theirs (organic_pages.WORDING). A page that cannot save (opened as a local file, or not signed in) says to
# decide in chat, never that the decisions are kept on it (issue #2).
WORDING: list[tuple[str, str]] = [
    ("'Kept on this page only. Open the page from its claude.ai link to save it for the team, or use "
     "\"Copy my decisions\".'",
     "'Not saved: this copy can\\'t save decisions. Open the page from its claude.ai link to save them for the "
     "team, or tell Claude your decisions in chat (\"Copy my decisions\" helps).'"),
    ("'Decisions are kept on this page only. Open it from its claude.ai link to save them for the team.'",
     "'This copy can\\'t save decisions: tell Claude your decisions in chat (\"Copy my decisions\" helps), or "
     "open the page from its claude.ai link to save them for the team.'"),
]


def worded(page: str) -> str:
    """The page with `WORDING` applied."""
    for old, new in WORDING:
        page = page.replace(old, new)
    return page


# The PDFs (issue #10): the page's labels for them, and its print mode. The view bar's hint says to share the link
# with the team only (it opens every view) and, with the PDFs, to send one view as its PDF.
# Their words are the table's `brief.pdf_<name>` (issue #3); PDF_WORDS is the English, for the tests.
PDF_KEYS = ("full", "view", "hint", "hint_no_pdf", "unavailable", "failed", "banner_full", "banner_view", "stills")
PDF_WORDS = {name: i18n.english()[f"brief.pdf_{name}"] for name in PDF_KEYS}
PRINT_CSS = """
  /* print mode (issue #10): print.html#print-full or #print-<view>, as the PDFs are printed */
  @page{size:A4;margin:12mm}
  html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body.print{font-size:14px}
  body.print .viewbar,body.print aside,body.print .decide,body.print .decisions,body.print .toggle,body.print .toast{display:none !important}
  body.print .night{padding:28px 16px 32px}
  body.print .page{display:block;padding:28px 0 0}
  body.print .phones{grid-template-columns:repeat(3,minmax(0,1fr));max-width:none;gap:18px;margin-top:24px}
  body.print .phone .frame{width:min(100%,170px)}
  .phone img.still{width:100%;height:100%;object-fit:cover;border-radius:22px;display:block;background:#000}
  body.print .concept{padding:20px}
  body.print .concept header{grid-template-columns:1fr}
  .stills{margin:6px 0 0}
  .stills-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
  .stills img{width:100%;border-radius:8px;display:block;background:#000}
  .stills figcaption{color:var(--muted);font-size:13px;margin-top:6px}
  .print-banner{background:var(--note);color:var(--note-ink);font-weight:700;padding:10px 16px}
  .print-banner[hidden]{display:none}
  body.print tr,body.print .fact,body.print .glance .g,body.print blockquote,body.print .findings li,body.print .evidence a,body.print .phone,body.print .stills,body.print .hookline,body.print .note-box,body.print .copy{break-inside:avoid}
  body.print h2,body.print h3{break-after:avoid}
"""
DOWNLOAD_CSS = """
  /* the PDFs' buttons (issue #10) */
  .vb-pdf{display:flex;flex-wrap:wrap;gap:6px}
  .vb-pdf button{font:inherit;font-weight:600;padding:8px 14px;border-radius:999px;border:1px solid var(--ink);background:#fff;color:var(--ink);cursor:pointer}
  .vb-pdf button:disabled{opacity:.5;cursor:default}
"""
PRINT_SCRIPT = """<script>
  // print mode (issue #10): one view, or every view of the brief for the full report, and its banner
  (() => {
    const m = location.hash.match(/^#print-([A-Za-z0-9_-]+)$/); if (!m) return;
    const key = m[1]; document.body.classList.add('print');
    if (key === 'full') document.querySelectorAll('[data-v]').forEach(el => { el.hidden = !el.dataset.v.split(' ').some(x => RECIPIENTS.includes(x)); });
    else showView(key);
    document.querySelectorAll('.print-banner').forEach(b => { b.hidden = b.dataset.print !== key; });
  })();
</script>
"""
DOWNLOAD_SCRIPT = """<script>
  // the PDFs (issue #10): on claude.ai saved with the downloads capability, elsewhere opened as files
  (() => {
    const bs = [...document.querySelectorAll('.vb-dl')], note = document.querySelector('.vb-dl-note');
    const say = t => { note.textContent = t || ''; note.hidden = !t; };
    const open = () => bs.forEach(b => b.addEventListener('click', () => window.open(b.dataset.file, '_blank', 'noopener')));
    if (location.protocol === 'file:') { open(); return; }
    bs.forEach(b => { b.disabled = true; });
    (async () => {
      for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
      if (!(window.claude && window.claude.use)) { bs.forEach(b => { b.disabled = false; }); open(); return; }
      let dls = null; try { dls = await window.claude.use('downloads'); } catch (e) { dls = null; }
      if (!dls) { say(note.dataset.unavailable); return; }
      bs.forEach(b => { b.disabled = false; b.addEventListener('click', async () => {
        if (b.disabled) return;
        b.disabled = true; say('');
        try {
          const res = await fetch(b.dataset.file); if (!res.ok) throw new Error(String(res.status));
          await dls.save({ filename: b.dataset.file.split('/').pop(), data: await res.blob() });
        } catch (e) { if (!(e && e.code === 'declined')) say(note.dataset.failed); }
        finally { b.disabled = false; }
      }); });
    })();
  })();
</script>
"""


def _with_parts(tpl: str, *, pdfs: bool, printing: bool) -> str:
    """The template with the plugin's print mode (print.html) or download script (a page with PDFs)."""
    css = (PRINT_CSS if printing else "") + (DOWNLOAD_CSS if pdfs else "")
    if css:
        tpl = tpl.replace("</style>", css + "</style>", 1)
    scripts = (PRINT_SCRIPT if printing else "") + (DOWNLOAD_SCRIPT if pdfs else "")
    if scripts:
        head, end, tail = tpl.rpartition("</body>")
        tpl = head + scripts + end + tail
    return tpl


# The words of the template's script (the handoff's English, and WORDING's), in another language: each (the
# English as the worded template writes it, its key, how it is written there, the script's expressions for its
# placeholders). `js` is a single-quoted string, `tpl` a template literal. Applied after `worded`; the template
# itself stays verbatim. {{TITLE_JS}} stays for the fill.
TEMPLATE_WORDS: list[tuple[str, str, str, dict[str, str]]] = [
    ("'Approved'", "brief.approved", "js", {}),
    ("'Changes requested'", "brief.changes_requested", "js", {}),
    ("'Not saved yet.'", "brief.not_saved_yet", "js", {}),
    ("'Choose Approve or Ask for changes first.'", "brief.choose_first", "js", {}),
    (WORDING[0][1], "brief.cannot_save_here", "js", {}),
    ("'Your access is view-only. Ask the sender for Contributor access, or use \"Copy my decisions\".'",
     "brief.view_only", "js", {}),
    ("'Saving…'", "brief.saving", "js", {}),
    ("'Saved. Everyone with this link can see it.'", "brief.saved", "js", {}),
    ("'Not saved: the connection failed. Try again in a moment.'", "brief.save_failed", "js", {}),
    ("'You'", "brief.you", "js", {}),
    ("'Someone'", "brief.someone", "js", {}),
    ("`${c}: ${a} approved, ${ch} changes requested`", "brief.tally_counts", "tpl",
     {"id": "${c}", "approved": "${a}", "changes": "${ch}"}),
    ("`${c}: none yet`", "brief.tally_none", "tpl", {"id": "${c}"}),
    ("'Decisions on this concept:'", "brief.decisions_on_concept", "js", {}),
    ("'Decisions on \"{{TITLE_JS}}\"'", "brief.copy_header", "js", {"title": "{{TITLE_JS}}"}),
    ("'no decision'", "brief.no_decision", "js", {}),
    ("'Copied. Paste it wherever you send feedback.'", "brief.copied", "js", {}),
    ("'Select the text below and copy it.'", "brief.select_and_copy", "js", {}),
    (WORDING[1][1], "brief.page_cannot_save", "js", {}),
    ("'Still connecting to shared decisions…'", "brief.still_connecting", "js", {}),
    ("'Shared decisions are unavailable here (sign in on claude.ai). Use \"Copy my decisions\".'",
     "brief.shared_unavailable", "js", {}),
    ("'Sign in to save decisions for the team. Use \"Copy my decisions\" meanwhile.'", "brief.sign_in", "js", {}),
    ("'Decisions you save are shared with everyone who has this link.'", "brief.shared_with_link", "js", {}),
    ("'You can read decisions; your access does not allow saving.'", "brief.read_only", "js", {}),
    ("'Shared decisions could not be loaded. Use \"Copy my decisions\".'", "brief.load_failed", "js", {}),
]
_HTML_LANG = '<html lang="en">'
_TEMPLATE_WORD = re.compile("|".join(re.escape(w[0]) for w in sorted(TEMPLATE_WORDS, key=lambda w: -len(w[0]))))


def js_text(text: str, kind: str, fills: dict[str, str] | None = None) -> str:
    """`text` as the script writes it: a single-quoted string (`js`) or a template literal (`tpl`), its
    {placeholders} then filled with `fills` as they are (script expressions). `</` and `<!--` cannot end the
    script."""
    out = (text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("</", "<\\/")
           .replace("<!--", "<\\!--"))
    out = "'" + out.replace("'", "\\'") + "'" if kind == "js" else "`" + out.replace("`", "\\`").replace("${", "\\${") + "`"
    for name, expr in (fills or {}).items():
        out = out.replace("{" + name + "}", expr)
    return out


def translated(page: str, tr: i18n.Translator) -> str:
    """The worded template in `tr`'s language: `TEMPLATE_WORDS` in one pass (a translation is never read as
    English again), and its `lang`."""
    if not i18n.is_english(tr.lang):
        swap = {old: js_text(tr(key), kind, fills) for old, key, kind, fills in TEMPLATE_WORDS}
        page = _TEMPLATE_WORD.sub(lambda m: swap[m.group(0)], page)
    return page.replace(_HTML_LANG, f'<html lang="{E(i18n.html_lang(tr.lang))}">', 1)


_MIME = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


def E(s) -> str:
    return html.escape(str(s or ''), quote=True)


def _href(url) -> str:
    """A link the page may carry: http(s) with a host, else nothing."""
    try:
        parts = urlsplit(url) if isinstance(url, str) else None
    except ValueError:
        return ''
    return url if parts and parts.scheme.lower() in ("http", "https") and parts.netloc else ''


def _script(value) -> str:
    """JSON for the page's script: `</` cannot close it."""
    return json.dumps(value).replace("</", "<\\/")


def title_js(title: str) -> str:
    """The title inside the script's single-quoted string: `</` cannot end the script, and `<!--`
    cannot put the HTML parser in the state where the page's own `</script>` would not end it."""
    return (json.dumps(title, ensure_ascii=False)[1:-1].replace("'", "\\'").replace("</", "<\\/")
            .replace("<!--", "<\\!--"))


# --- the port of build_brief_pack.py ---------------------------------------------------------------

def _english() -> i18n.Translator:
    return i18n.translator(i18n.ENGLISH)


def W(tr: i18n.Translator, key: str, **fills) -> str:
    """A word of the table as HTML text, its {placeholders} filled with `fills` as they are (HTML already)."""
    text = html.escape(tr(key), quote=False)
    return text.format(**fills) if fills else text


def A(tr: i18n.Translator, key: str, **fills) -> str:
    """A word of the table in an attribute's value, its {placeholders} filled with `fills` (escaped already)."""
    text = E(tr(key))
    return text.format(**fills) if fills else text


def v(*views):
    return f' data-v="{" ".join(views)}"'


def todo_or(x, tr: i18n.Translator | None = None):
    return E(x) if x else TODO.format(W(tr or _english(), "brief.to_set"))


def labeled_dl(items):
    return '<dl class="copy">' + ''.join(f'<dt>{E(i["label"])}</dt><dd>{E(i["text"])}</dd>' for i in items) + '</dl>'


def _beat(b, tr: i18n.Translator | None = None) -> str:
    ost = ' class="ost"' if b.get("ost_strong") else ""
    t = W(tr or _english(), "brief.beat_time", start=f'{b["t0"]:g}', end=f'{b["t1"]:g}')
    return (f'<tr><td class="t">{t}</td><td>{E(b["see"])}</td><td>{E(b["hear"])}</td>'
            f'<td{ost}>{E(b["ost"])}</td></tr>')


def _thumb(x) -> str:
    """The clip's thumbnail; none when it has no path (a standalone file without it)."""
    return f'<img src="{E(x["thumb"])}" alt="{E(x["caption"])}">' if x.get("thumb") else ''


def _stills_html(shots: list[str], tr: i18n.Translator | None = None) -> str:
    """The print mode's player: the animatic's stills, captioned (none without stills)."""
    if not shots:
        return ''
    imgs = ''.join(f'<img src="{E(s)}" alt="">' for s in shots)
    return (f'<figure class="stills"><div class="stills-row">{imgs}</div>'
            f'<figcaption>{E((tr or _english())("brief.pdf_stills"))}</figcaption></figure>')


def _translated(p, tr: i18n.Translator) -> str:
    """After a customer phrase marked `translated` (CB5): the original words it was translated from."""
    if p.get("translated") is not True:
        return ''
    return f' <span class="src">({W(tr, "brief.phrase_translated", original=E(p.get("adapted_from")))})</span>'


def concept_html(c, idx, total, stills=None, tr: i18n.Translator | None = None):
    """A concept's section; with `stills` ({animatic path: its stills}) the print mode's, its stills in
    place of the player."""
    tr = tr or _english()
    cid = E(c['id'])
    a = c.get('animatic', {})
    default = a.get('default', '9x16')
    src = a.get(default, '')
    toggle = ''.join(f'<button aria-pressed="{"true" if f == default else "false"}" data-src="{E(a[f])}">{f.replace("x", ":")}</button>' for f in FORMATS if a.get(f))
    player = (_stills_html(stills.get(src) or [], tr) if stills is not None else
              f'<div class="player" data-player="{cid}"><video src="{E(src)}" controls muted playsinline preload="metadata"></video>'
              f'<div class="toggle" role="group" aria-label="{A(tr, "brief.format")}">{toggle}</div></div>')
    out = [f'<section id="{cid.lower()}" class="concept">',
           '<header><div>',
           f'<p class="tag">{W(tr, "brief.concept_of", idx=idx, total=total)}</p>',
           f'<h2>{E(c["title"])}</h2>',
           f'<p>{E(c["one_liner"])}</p>',
           f'<p class="keymsg"><b>{W(tr, "brief.key_message")}</b> {E(c["key_message"])}</p>',
           f'<p class="hyp"{v("decision", "strategy", "media-buyer")}><b>{W(tr, "brief.what_this_tests")}</b> {E(c["hypothesis"])}</p>',
           '</div>',
           player,
           '</header>']
    # evidence at a glance
    rows = ''.join(f'<div class="g{" trend" if g.get("highlight") else ""}"><dt>{E(g["label"])}</dt><dd>{E(g["text"])}<span class="src">{E(g["source"])}</span></dd></div>' for g in c['glance'])
    out.append(f'<div class="glance"{v("decision", "strategy", "media-buyer")}><h3>{W(tr, "brief.evidence_at_a_glance")}</h3><dl>{rows}</dl></div>')
    d = c.get('decision_facts', {})
    if d:
        bda = W(tr, "brief.budget_line", budget=todo_or(d.get('budget'), tr), deadline=todo_or(d.get('deadline'), tr), approver=todo_or(d.get('approver'), tr))
        out.append(f'<div class="facts small"{v("decision", "strategy")}>'
                   f'<div class="fact"><b>{W(tr, "brief.goal")}</b><span>{E(d.get("goal"))}</span></div>'
                   f'<div class="fact"><b>{W(tr, "brief.effort")}</b><span>{E(d.get("effort"))}</span></div>'
                   f'<div class="fact"><b>{W(tr, "brief.budget_deadline_approver")}</b><span>{bda}</span></div>'
                   f'<div class="fact"><b>{W(tr, "brief.main_risk")}</b><span>{E(d.get("risk"))}</span></div></div>')
    h = c['hook']
    out.append(f'<div{v("strategy", "creator", "editor")}><h3>{W(tr, "brief.the_hook")}</h3><div class="hookline">{E(h["text"])}</div><p>{E(h.get("description"))}</p></div>')
    trs = ''.join(_beat(b, tr) for b in c['beats'])
    note = c.get('note')
    note_html = f'<div class="note-box"><b>{E(note["title"])}</b> {E(note["text"])}</div>' if note else ''
    heads = ''.join(f'<th>{W(tr, k)}</th>' for k in ("brief.col_time", "brief.col_see", "brief.col_hear", "brief.col_on_screen"))
    out.append(f'<div{v("strategy", "editor")}><h3>{W(tr, "brief.second_by_second", length=E(c.get("length_s", c["beats"][-1]["t1"])))}</h3>'
               f'<div class="table-scroll"><table><tr>{heads}</tr>{trs}</table></div>{note_html}</div>')
    if c.get('why'):
        qs = ''.join(f'<blockquote>{E(q["quote"])}<cite><a href="{E(_href(q["url"]))}" target="_blank" rel="noopener">{E(q["source_label"])}</a></cite></blockquote>' for q in c['why'])
        out.append(f'<div{v("strategy")}><h3>{W(tr, "brief.why_people_care")}</h3>{qs}</div>')
    if c.get('customer_phrases'):
        lis = ''.join(f'<li>{W(tr, "brief.customer_phrase", phrase=E(p["phrase"]), used_in=E(p["used_in"]))}{_translated(p, tr)} (<a href="{E(_href(p["url"]))}" target="_blank" rel="noopener">{W(tr, "brief.source")}</a>)</li>' for p in c['customer_phrases'])
        out.append(f'<div{v("strategy")}><h3>{W(tr, "brief.customers_own_words")}</h3><ul class="plain">{lis}</ul></div>')
    cf = c.get('copy_from_hook')
    if cf:
        ev = ''.join(f'<a href="{E(_href(x["url"]))}" target="_blank" rel="noopener">{_thumb(x)}<b>{E(x["views"])}</b><br>{E(x["caption"])}</a>' for x in cf.get('evidence', []))
        out.append(f'<div{v("strategy", "creator", "editor")}><h3>{W(tr, "brief.copy_from_hook")}</h3><p>{E(cf["text"])}</p><div class="evidence">{ev}</div></div>')
    ac = c.get('ad_copy')
    if ac or c.get('hooks_to_test'):
        left = (f'<div><h3>{W(tr, "brief.ad_copy")}</h3><dl class="copy"><dt>{W(tr, "brief.primary_text")}</dt><dd>{E(ac.get("primary"))}</dd><dt>{W(tr, "brief.headline")}</dt><dd>{E(ac.get("headline"))}</dd><dt>{W(tr, "brief.button")}</dt><dd>{E(ac.get("button"))}</dd></dl></div>') if ac else ''
        hk = ''.join(f'<tr><td>{chr(65 + i)}</td><td>{E(t)}</td></tr>' for i, t in enumerate(c.get('hooks_to_test', [])))
        out.append(f'<div class="two"{v("strategy", "media-buyer")}>{left}<div><h3>{W(tr, "brief.hooks_to_test")}</h3><table>{hk}</table></div></div>')
    if c.get('casting'):
        out.append(f'<div{v("strategy")}><h3>{W(tr, "brief.casting_and_look")}</h3><p>{E(c["casting"])}</p></div>')
    cr = c.get('creator')
    if cr:
        has_key = any(s.get('key') for s in cr.get('say', []))
        head = (f'<tr><th>{W(tr, "brief.col_moment")}</th>' + (f'<th>{W(tr, "brief.col_key_point")}</th>' if has_key else '') + '<th>'
                + (W(tr, "brief.col_sample_line") if has_key else W(tr, "brief.col_line")) + '</th></tr>')
        say = ''.join('<tr><td>{}</td>{}<td>{}</td></tr>'.format(E(s['moment']), f'<td><b>{E(s["key"])}</b></td>' if has_key else '', E(s['line'])) for s in cr.get('say', []))
        shots = ''.join(f'<tr><td>{i}</td><td>{E(s["shot"])}</td><td>{E(s["framing"])}</td><td>{E(s["takes"])}</td></tr>' for i, s in enumerate(cr.get('shots', []), 1))
        send = ''.join(f'<li>{E(x)}</li>' for x in cr.get('send_back', []))
        send += f'<li>{W(tr, "brief.deadline_usage", deadline=todo_or(cr.get("deadline"), tr), usage=todo_or(cr.get("usage"), tr))}</li>'
        extra = f'<p><b>{E(cr["extra_takes"])}</b></p>' if cr.get('extra_takes') else ''
        shot_heads = ''.join(f'<th>{W(tr, k)}</th>' for k in ("brief.col_shot", "brief.col_framing", "brief.col_takes"))
        out.append(f'<div class="role"{v("creator")}><h3>{W(tr, "brief.your_part")}</h3><p>{E(cr.get("role"))}</p>'
                   f'<h3>{W(tr, "brief.what_to_say")}</h3><p class="small-note">{E(cr.get("say_note"))}</p><table>{head}{say}</table>'
                   f'<h3>{W(tr, "brief.shots_to_record")}</h3><table><tr><th>#</th>{shot_heads}</tr>{shots}</table>{extra}'
                   f'<h3>{W(tr, "brief.look_and_props")}</h3><p>{E(cr.get("look"))}</p><h3>{W(tr, "brief.send_back")}</h3><ul class="plain">{send}</ul></div>')
    if c.get('editor'):
        out.append(f'<div class="role"{v("editor")}><h3>{W(tr, "brief.edit_spec")}</h3>{labeled_dl(c["editor"])}</div>')
    if c.get('media'):
        out.append(f'<div class="role"{v("media-buyer")}><h3>{W(tr, "brief.test_plan")}</h3>{labeled_dl(c["media"])}</div>')
    if c.get('qa'):
        qa = ''.join(f'<li><label><input type="checkbox"> {E(q)}</label></li>' for q in c['qa'])
        out.append(f'<div{v("strategy", "editor")}><h3>{W(tr, "brief.before_live")}</h3><ul class="qa">{qa}</ul></div>')
    out.append(f'''<div class="decide" data-concept="{cid}"{v("decision", "strategy", "media-buyer")}>
    <h3>{W(tr, "brief.decision_on", id=cid)}</h3>
    <div class="row"><button type="button" class="choice" data-d="approve" aria-pressed="false">{W(tr, "brief.approve")}</button><button type="button" class="choice" data-d="change" aria-pressed="false">{W(tr, "brief.ask_for_changes")}</button></div>
    <label class="sr" for="note-{cid}">{W(tr, "brief.note_for", id=cid)}</label>
    <textarea id="note-{cid}" placeholder="{A(tr, "brief.note_placeholder")}"></textarea>
    <div class="row"><button type="button" class="save">{W(tr, "brief.save_decision")}</button><span class="status" role="status" aria-live="polite"></span></div>
    <div class="others" aria-live="polite"></div></div>''')
    out.append('</section>')
    return '\n'.join(out)


def _pdf_buttons(pdfs: dict[str, str], views: list[str], tr: i18n.Translator | None = None) -> str:
    """The view bar's download buttons: the full report, and the view shown (a button per view, shown with it)."""
    tr = tr or _english()
    full = f'<button type="button" class="vb-dl" data-file="{E(pdfs[brief_pdf.FULL])}">{E(tr("brief.pdf_full"))}</button>'
    per = ''.join(f'<button type="button" class="vb-dl"{v(x)} data-file="{E(pdfs[x])}">'
                  f'{E(tr("brief.pdf_view", view=tr(VIEW_KEY[x])))}</button>' for x in views if x in pdfs)
    return (f'<div class="vb-pdf">{full}{per}</div><span class="vb-hint vb-dl-note" role="status" '
            f'data-unavailable="{A(tr, "brief.pdf_unavailable")}" data-failed="{A(tr, "brief.pdf_failed")}" hidden></span>')


def body_html(p, pdfs=None, stills=None, tr: i18n.Translator | None = None):
    """The page's body and its views. `pdfs` ({"full" | view: served path}) adds the download buttons; `stills`
    ({animatic path: its stills}) makes the print mode's body: a banner per PDF, stills in place of videos."""
    tr = tr or _english()
    m = p['meta']
    views = [x for x in ALL_VIEWS if x in m['recipients']]
    out = ['<div class="night"><div class="wrap">', f'<h1>{E(m["title"])}</h1>']
    if stills is not None:
        banners = [(brief_pdf.FULL, tr("brief.pdf_banner_full"))] + [
            (x, tr("brief.pdf_banner_view", view=tr(VIEW_KEY[x]))) for x in views]
        out.insert(0, ''.join(f'<div class="print-banner" data-print="{x}" hidden>{E(t)}</div>' for x, t in banners))
    for k, txt in m.get('lede', {}).items():
        out.append(f'<p class="lede"{v(E(k))}>{E(txt)}</p>')
    meta = W(tr, "brief.meta_line", market=E(m["market"]), language=E(m["language"]), prepared=E(m["prepared"]), valid_until=E(m["valid_until"]))
    out.append(f'<p class="meta">{meta}</p><div class="phones">')
    for c in p['concepts'][:3]:
        a = c.get('animatic', {})
        phone = a.get("9x16") or a.get(a.get("default", "9x16"), "")   # a run drawn in 4x5 alone has no 9x16
        facts = v(*HEADER_FACTS_VIEWS)
        # the creator's card: the title under the phone note (when the note is not the title), no account data
        title = f'<div class="who"{v("creator")}>{E(c["title"])}</div>' if c.get("phone_note", c["title"]) != c["title"] else ''
        shots = (stills or {}).get(phone) or []
        screen = ((f'<img class="still" src="{E(shots[min(1, len(shots) - 1)])}" alt="">' if shots else '') if stills is not None
                  else f'<video src="{E(phone)}" autoplay muted loop playsinline aria-label="{A(tr, "brief.animatic_label", id=E(c["id"]))}"></video>')
        out.append(f'<a class="phone" href="#{E(c["id"].lower())}" data-jump="{E(c["id"].lower())}"><div class="frame">{screen}</div>'
                   f'<div class="note">{E(c.get("phone_note", c["title"]))}</div>{title}<div class="who"{facts}>{E(c.get("for_whom"))}</div><div class="trendline"{facts}>{E(c.get("trend_line"))}</div></a>')
    out.append('</div></div></div>')
    btns = ''.join(f'<button type="button" data-view="{x}">{W(tr, VIEW_KEY[x])}</button>' for x in views)
    if len(views) > 1 or pdfs:
        pick = (f'<span class="vb-label">{W(tr, "brief.i_am_the")}</span><div class="vb-buttons">{btns}</div>'
                if len(views) > 1 else '')
        hint = E(tr("brief.pdf_hint" if pdfs else "brief.pdf_hint_no_pdf"))
        out.append(f'<div class="viewbar" role="navigation" aria-label="{A(tr, "brief.choose_view")}"><div class="wrap viewbar-in">{pick}{_pdf_buttons(pdfs, views, tr) if pdfs else ""}<span class="vb-hint">{hint}</span></div></div>')
    out.append('<div class="wrap page"><main>')
    f = p.get('findings')
    if f:
        items = ''.join(f'<li><strong>{E(i["title"])}</strong> {E(i["text"])}</li>' for i in f.get('items', []))
        cav = f'<p class="caveat">{E(f["caveat"])}</p>' if f.get('caveat') else ''
        out.append(f'<section id="evidence"{v("decision", "strategy", "media-buyer")}><h2>{W(tr, "brief.evidence_changed")}</h2><ul class="findings">{items}</ul>{cav}</section>')
    au = p.get('audience')
    if au:
        facts = ''.join(f'<div class="fact"><b>{E(x["value"])}</b><span>{E(x["label"])}</span></div>' for x in au.get('facts', []))
        out.append(f'<section id="audience"{v("decision", "strategy", "media-buyer")}><h2>{W(tr, "brief.audience")}</h2><p>{E(au.get("text"))}</p><div class="facts">{facts}</div><p class="src">{E(au.get("source"))}</p></section>')
    pr = m['product']
    plan = ''.join(f'<li>{E(x)}</li>' for x in pr.get('plan', []))
    out.append(f'<section id="product"{v("creator", "editor")}><h2>{W(tr, "brief.product_plain")}</h2><p><b>{E(pr["name"])}</b>. {E(pr.get("plain_description"))}</p><ul class="plain">{plan}</ul><p>{E(pr.get("price_note"))}</p></section>')
    t = p.get('tone')
    if t:
        must = ''.join(f'<li>{E(x)}</li>' for x in t.get('must', []))
        never = ''.join(f'<li>{E(x)}</li>' for x in t.get('never', []))
        out.append(f'<section id="tone"{v("strategy", "creator", "editor")}><h2>{W(tr, "brief.tone_must")}</h2><div class="two"><div><h3>{W(tr, "brief.tone")}</h3><p>{E(t.get("tone"))}</p><h3>{W(tr, "brief.must_have")}</h3><ul class="plain">{must}</ul></div><div><h3>{W(tr, "brief.never")}</h3><ul class="plain">{never}</ul></div></div></section>')
    n = len(p['concepts'])
    for i, c in enumerate(p['concepts'], 1):
        out.append(concept_html(c, i, n, stills, tr))
    out.append(f'<footer><p{v("decision", "strategy", "media-buyer")}>{E(m.get("sources_note"))}</p><p>{E(m.get("animatic_note"))}</p></footer></main>')
    nav = ''.join(f'<a href="#{E(c["id"].lower())}" data-jump="{E(c["id"].lower())}">{E(c["id"])} {E(c["title"][:28])}</a>' for c in p['concepts'])
    tally = ''.join(f'<li>{W(tr, "brief.tally_none", id=E(c["id"]))}</li>' for c in p['concepts'])
    out.append(f'<aside><nav aria-label="{A(tr, "brief.sections")}">{nav}</nav><div class="decisions"{v("decision", "strategy", "media-buyer")}><h3>{W(tr, "brief.decisions_so_far")}</h3><ul id="tally">{tally}</ul><p id="mode">{W(tr, "brief.connecting")}</p>'
               f'<button type="button" class="save" id="copy">{W(tr, "brief.copy_my_decisions")}</button><textarea id="copybox" class="copybox" readonly hidden aria-label="{A(tr, "brief.decisions_as_text")}"></textarea></div></aside></div>')
    return '\n'.join(out), views


def _required(brief: object) -> list[str]:
    """The original's `check`: the fields the page cannot be built without."""
    if not isinstance(brief, dict) or not isinstance(brief.get("meta"), dict):
        return ["meta"]
    miss = [k for k in ('title', 'market', 'language', 'prepared', 'valid_until', 'recipients', 'product')
            if k not in brief['meta']]
    concepts = brief.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        return miss + ["concepts"]
    for c in concepts:
        if not isinstance(c, dict):
            miss.append("concepts[]")
            continue
        for k in ('id', 'brief_id', 'title', 'one_liner', 'key_message', 'hypothesis', 'glance', 'hook', 'beats'):
            if k not in c:
                miss.append(f'{c.get("id", "?")}.{k}')
        if "id" in c and not (isinstance(c["id"], str) and _ID.fullmatch(c["id"])):
            miss.append(f"{c['id']!r} as a concept id (letters, digits, _ and -, e.g. C1)")
        a = c.get("animatic")
        if isinstance(a, dict) and "default" in a and a["default"] not in FORMATS:
            miss.append(f"{c.get('id', '?')}.animatic.default as one of {', '.join(FORMATS)}")
    same: dict[str, list[str]] = {}
    for c in concepts:
        if isinstance(c, dict) and isinstance(c.get("id"), str):
            same.setdefault(c["id"].lower(), []).append(c["id"])
    miss += [f"an id of its own for each concept ({' and '.join(ids)} are one id on the page, case aside)"
             for ids in same.values() if len(ids) > 1]
    return miss


def render(brief: dict, lang: str = i18n.ENGLISH, *, pdfs: dict[str, str] | None = None,
           stills: dict[str, list[str]] | None = None) -> tuple[str, list[str]]:
    """The page's HTML in `lang` and the views it shows (`meta.recipients` in the page's order). Stop for a
    brief the page cannot be built from; i18n.Missing when `lang` has no translation of a word of the page
    (`build` picks the language with `i18n.page_lang`). `pdfs` ({"full" | view: served path}) adds the buttons
    that download them; `stills` ({animatic path: its stills' paths}) makes the print mode the PDFs are printed
    from."""
    tr = i18n.translator(lang)
    miss = _required(brief)
    if miss:
        raise Stop(f"The brief is missing {', '.join(miss)}, so the page cannot be built from it. Fix brief.json "
                   f"(a new version) and check it (tm brief check), then build again. The run continues from the "
                   "same place.")
    try:
        body, views = body_html(brief, pdfs, stills, tr)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise Stop(f"The brief is not in its shape ({type(exc).__name__}: {exc}), so the page cannot be built from "
                   "it. Check it with tm brief check, fix it (a new version), then build again. The run continues "
                   "from the same place.") from None
    title = brief['meta']['title']
    fills = {"{{TITLE}}": E(title), "{{TITLE_JS}}": title_js(str(title)), "{{RECIPIENTS}}": _script(views),
             "{{CONCEPT_IDS}}": _script([c['id'] for c in brief['concepts']]), "<!--BODY-->": body}
    tpl = translated(_with_parts(worded(TEMPLATE.read_text(encoding="utf-8")), pdfs=bool(pdfs),
                                 printing=stills is not None), tr)
    return _FILL.sub(lambda mt: fills[mt.group(0)], tpl), views


class _ViewText(HTMLParser):
    """The text a view of the page shows, as its script shows it: an element whose `data-v` does not
    name the view is hidden, with all inside it, and so is a `hidden` one; scripts and styles are not
    text. The labels a viewer may see or hear (alt, aria-label, placeholder, title) count."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    LABELS = ("alt", "aria-label", "placeholder", "title")

    def __init__(self, view: str):
        super().__init__(convert_charrefs=True)
        self.view, self.open, self.texts = view, [], []

    def _hidden(self) -> bool:
        return any(hide for _, hide in self.open)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hide = (tag in ("script", "style") or "hidden" in a
                or (a.get("data-v") is not None and self.view not in (a["data-v"] or "").split()))
        if not (hide or self._hidden()):
            self.texts += [a[k] for k in self.LABELS if a.get(k)]
        if tag not in self.VOID:
            self.open.append((tag, hide))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.open.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                del self.open[i:]
                return

    def handle_data(self, data):
        if data.strip() and not self._hidden():
            self.texts.append(data)


def view_text(brief: dict, view: str, lang: str = i18n.ENGLISH) -> list[str]:
    """Every text the page built from `brief` (in `lang`) shows in `view`, in page order (CB13's scan of the
    creator view reads it, so a field new on the page cannot slip past). Stop as `render` does."""
    parser = _ViewText(view)
    parser.feed(render(brief, lang)[0])
    parser.close()
    return parser.texts


# --- building it in the run --------------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{path} is not inside the run folder {run.path}.") from None


def load_brief(run: RunFolder, brief_path: Path | None) -> tuple[Path, str, dict]:
    """The brief (default: the latest `04_final/brief_pack_vNN.json`), its run-relative path and its
    JSON object. Stop when there is none, or it is not one JSON object."""
    path = Path(brief_path) if brief_path is not None else run.latest(FINAL, STEM, "json")
    if path is None:
        raise Stop(f"This run has no {FINAL}/{STEM}_vNN.json yet: write brief.json and check it (tm brief check) "
                   f"first. The run continues from the same place.")
    rel = _rel(run, path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{rel} is not valid JSON ({exc}). Write it again as one JSON object; {AGAIN}.") from None
    if not isinstance(data, dict):
        raise Stop(f"{rel} is not one JSON object. Write brief.json again; {AGAIN}.")
    return path, rel, data


def _served(ref: str) -> str:
    """The path a media file is served at inside the page folder: the brief's path, each part an
    `asset_name`. Stop for a path that would leave the folder or is not a file path."""
    text = ref.replace("\\", "/")
    parts = text.split("/")
    if "://" in ref:
        raise Stop(f"brief.json names the media file {ref!r}, a web address: the page serves only files kept in the "
                   "run. For a clip's thumbnail run `tm brief evidence`: it keeps each thumbnail in "
                   f"{EVIDENCE} and writes its path (evidence/<video id>.jpg) into a new brief version, or takes the "
                   "address out when it cannot be had. Then build the page from that version. The run continues "
                   "from the same place.")
    if (PurePosixPath(text).is_absolute() or PureWindowsPath(ref).drive
            or any(p in ("", ".", "..") for p in parts)):
        raise Stop(f"brief.json names the media file {ref!r}: a media path is relative, like animatic/C1_9x16_v01.mp4 "
                   "or evidence/<clip>.jpg. Fix it (a new version), then build again. The run continues from the "
                   "same place.")
    return "/".join(page.asset_name(p) for p in parts)


def _refs(brief: dict) -> list[tuple[str, str, str]]:
    """Every media file the brief names: (concept id, kind, path), kind animatic or thumbnail."""
    out = []
    for c in brief["concepts"]:
        a = c.get("animatic") or {}
        out += [(c["id"], "animatic", a[f]) for f in FORMATS if isinstance(a, dict) and isinstance(a.get(f), str)
                and a[f]]
        for x in (c.get("copy_from_hook") or {}).get("evidence", []) or []:
            if isinstance(x, dict) and isinstance(x.get("thumb"), str) and x["thumb"]:
                out.append((c["id"], "thumbnail", x["thumb"]))
    return out


def _undated_clips(brief: dict) -> list[str]:
    """"<id> <url>" for each clip of a concept on a TrendsMesh trend (`plugin.trend`) without its
    `plugin.as_of`. A guess run's concepts have no trend, and their clips are not asked."""
    out = []
    for c in brief["concepts"]:
        if not ((c.get("plugin") or {}).get("trend") or {}).get("trend_id"):
            continue
        for x in (c.get("copy_from_hook") or {}).get("evidence", []) or []:
            if isinstance(x, dict) and not (x.get("plugin") or {}).get("as_of"):
                out.append(f"{c['id']} {x.get('url')}")
    return out


def find_media(run: RunFolder, ref: str, folders: tuple[str, ...] = MEDIA_DIRS) -> Path | None:
    """The media file a brief names, by its file name (as `page.asset_name` makes it, else as
    written) in the run's renders and evidence folders."""
    base = ref.replace("\\", "/").rsplit("/", 1)[-1]
    for folder in folders:
        for name in dict.fromkeys((page.asset_name(base), base)):
            candidate = run.path / folder / name
            if candidate.is_file():
                return candidate
    return None


def _swap(brief: dict, new: dict[str, str]) -> dict:
    """The brief with each media path replaced by where the page finds it."""
    out = copy.deepcopy(brief)
    for c in out["concepts"]:
        a = c.get("animatic")
        if isinstance(a, dict):
            for f in FORMATS:
                if a.get(f) in new:
                    a[f] = new[a[f]]
        for x in (c.get("copy_from_hook") or {}).get("evidence", []) or []:
            if isinstance(x, dict) and x.get("thumb") in new:
                x["thumb"] = new[x["thumb"]]
    return out


def _data_uri(path: Path) -> str:
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _print_pdfs(run: RunFolder, out: Path, brief: dict, served: dict[str, str], present: dict[str, Path],
                missing: list[str], views: list[str], planned: dict[str, int],
                lang: str = i18n.ENGLISH) -> tuple[dict[str, str], str | None]:
    """Print the page's PDFs into `out/pdf/` (`brief_pdf`): the print page `.print/print.html` (media from the
    page folder, each animatic's stills as JPEGs beside it), then one PDF per key of `brief_pdf.names`. Returns
    ({key: served path}, None), or ({}, why there are none): no browser, a print that failed, or a page the PDFs
    would put over the Artifact tool's limits. The page is built either way."""
    browser = brief_pdf.browser()
    if browser is None:
        return {}, "no Chrome or Edge was found on this computer to print them"
    to_print = {ref: f"../{served[ref]}" for ref in present} | {ref: "" for ref in missing}
    shots = {}
    for _, kind, ref in _refs(brief):
        if kind == "animatic" and ref in present and to_print[ref] not in shots:
            made = brief_pdf.stills(run.path, present[ref], out / brief_pdf.PRINT_DIR / "stills")
            shots[to_print[ref]] = [f"stills/{f.name}" for f in made]
    print_page = brief_pdf.write_print_page(out, render(_swap(brief, to_print), lang, stills=shots)[0])
    wanted = brief_pdf.names(views)
    try:
        for key, served_at in wanted.items():
            brief_pdf.print_pdf(browser, print_page, key, out / served_at)
    except ValueError as exc:
        brief_pdf.remove(out)
        return {}, f"printing them failed: {exc}"
    over = page.over_limits(planned | {p: (out / p).stat().st_size for p in wanted.values()})
    if over:
        brief_pdf.remove(out)
        return {}, f"with them the page would be too big to publish as one artifact: {over}"
    return wanted, None


def build(run: RunFolder, brief_path: Path | None = None, *, single_file: bool = False) -> dict:
    """Build the page from brief.json (default: the latest `04_final/brief_pack_vNN.json`) into a new
    `04_final/brief_pack_vNN/` (index.html plus the media it names), or with `single_file` into
    `04_final/brief_pack_vNN.html` with every media file inlined (CB12's fallback). Nothing is
    written when a decision is awaited, an animatic the brief names is not rendered, the brief
    cannot make a page, or the folder would be over the Artifact tool's limits (each a Stop). A missing
    thumbnail is listed in `media_missing` (a single file leaves its image out). A folder build prints the
    PDFs (`_print_pdfs`, `pdfs`), each with a manifest row; without them `pdf_note` says why. The page and its
    PDFs are in the run's working language, or in English while that language's table lacks a word of it:
    `language_warning` says so."""
    if page.awaiting(run, PAGE) is not None:
        raise page.Deciding(PAGE, AWAITING)
    path, rel, brief = load_brief(run, brief_path)
    pl = i18n.page_lang(i18n.run_languages(run).working, "brief")
    render(brief, pl.lang)                                # the brief can make a page: Stop before anything is written
    undated = _undated_clips(brief)
    if undated:
        raise Stop(f"{rel} cites {len(undated)} TrendsMesh clip{'' if len(undated) == 1 else 's'} with no as-of date "
                   f"(plugin.as_of, CB8): {', '.join(undated)}. Run `tm brief evidence` first: it keeps each clip's "
                   "thumbnail and the day it was saved in a new brief version. Then build the page from that version. "
                   "A clip it cannot find in the trend's saved video pages is read with get_trend_videos, or taken "
                   "out of the brief. Nothing was written. The run continues from the same place.")
    refs = _refs(brief)
    served = {ref: _served(ref) for _, _, ref in refs}
    found = {ref: find_media(run, ref) for _, _, ref in refs}
    no_animatic = [f"{cid} {ref}" for cid, kind, ref in refs if kind == "animatic" and found[ref] is None]
    if no_animatic:
        raise Stop(f"The brief names {len(no_animatic)} animatic{'' if len(no_animatic) == 1 else 's'} that "
                   f"{'is' if len(no_animatic) == 1 else 'are'} not in {RENDERS}: {', '.join(no_animatic)}. Render "
                   f"it first with `tm brief animatic --render`, then build the page again. Nothing was written. The "
                   f"run continues from the same place.")
    missing = sorted({ref for ref, f in found.items() if f is None})
    present = {ref: f for ref, f in found.items() if f is not None}
    if single_file:
        # a standalone file cannot reach a thumbnail that is not there: its <img> is left out
        inline = {ref: _data_uri(f) for ref, f in present.items()} | {ref: "" for ref in missing}
        html_text, views = render(_swap(brief, inline), pl.lang)
        out = run.next_version(FINAL, STEM, "html")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "x", encoding="utf-8", newline="\n") as fh:    # never over an earlier file
            fh.write(html_text)
    else:
        html_text, views = render(_swap(brief, served), pl.lang)
        planned = {"index.html": len(html_text.encode("utf-8"))}
        planned |= {served[ref]: f.stat().st_size for ref, f in present.items()}
        over = page.over_limits(planned)
        if over:
            raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Draw "
                       "fewer formats (animatic.formats in config.yaml) or shorter beats in the brief, render the "
                       "animatics again and build again; or build one file with --single-file for a recipient "
                       "without claude.ai. The run continues from the same place.")
        out = page.new_folder(run, PAGE)
        (out / "assets").rmdir()           # this page serves its media under the brief's own paths
        for ref, f in present.items():
            dest = out / served[ref]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dest)
        try:
            pdfs, pdf_note = _print_pdfs(run, out, brief, served, present, missing, views, planned, pl.lang)
        except OSError as exc:                   # the page is written all the same: PDFs are its extra
            brief_pdf.remove(out)
            pdfs, pdf_note = {}, f"printing them failed: {exc}"
        if pdfs:
            html_text = render(_swap(brief, served), pl.lang, pdfs=pdfs)[0]
        with open(out / "index.html", "x", encoding="utf-8", newline="\n") as fh:
            fh.write(html_text)
    out_rel = out.relative_to(run.path).as_posix()
    if not single_file:                          # before the page's row, which decided_page takes as the last
        for key, served_at in pdfs.items():
            manifest.record(run, f"{out_rel}/{served_at}", FINAL, PDF_SOURCE, parent=out_rel, model=brief_pdf.MODEL,
                            cost="0", params={"view": key})
    params = {"brief_sha256": stepchecks.sha256(path), "views": views, "single_file": single_file,
              "media_missing": missing}
    manifest.record(run, out_rel, FINAL, SOURCE, parent=rel, params=params | ({} if single_file else {"pdfs": pdfs}))
    result = {"views": views, "media_copied": len(present), "media_missing": missing, "brief": rel, "lang": pl.lang}
    if pl.warning:
        result["language_warning"] = pl.warning
    if single_file:
        return {"file": out_rel, **result, "bytes": out.stat().st_size}
    return {"folder": out_rel, **result, "pdfs": [f"{out_rel}/{p}" for p in pdfs.values()], "pdf_note": pdf_note,
            "files": page.files(out)}


def creator_pdf(run: RunFolder, brief: dict) -> tuple[str, Path] | None:
    """The creator PDF of the latest page built from a brief file equal to `brief` and unchanged since (its
    `tm brief page` row: the brief's sha256, the PDFs it printed), as (run-relative path, path); None when no
    such page printed one. The path may be gone: the caller says so."""
    for row in reversed(manifest.rows(run)):
        if row["source"] != SOURCE:
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
            parent = run.path / row["parent"]
            same = (isinstance(params, dict) and parent.is_file()
                    and params.get("brief_sha256") == stepchecks.sha256(parent)
                    and json.loads(parent.read_text(encoding="utf-8-sig")) == brief)
        except (OSError, ValueError):
            continue
        if not same:
            continue
        served = (params.get("pdfs") or {}).get("creator")
        if not isinstance(served, str):
            return None
        rel = f"{row['file']}/{served}"
        return rel, run.path / rel
    return None


# --- decisions ---------------------------------------------------------------------------------

_HEADER = 'Decisions on "'
_CHOICES = ("approve", "change")
_COPY_KEYS = ("brief.copy_header", "brief.approved", "brief.changes_requested", "brief.no_decision")


def _copy_words(lang: str | None) -> list[tuple[str, str, dict[str, str], re.Pattern]]:
    """How a "Copy my decisions" text is written, in English and (when its table has the words) `lang`: the
    header's start and end around the title, the labels of a choice, and a concept's line."""
    out = []
    for code in dict.fromkeys((i18n.ENGLISH, lang or i18n.ENGLISH)):
        words = i18n.table(code)
        if not all(k in words for k in _COPY_KEYS):
            continue
        head, _, tail = words["brief.copy_header"].partition("{title}")
        if not head.strip():                  # a header that starts with the title is not told from a line
            continue
        labels = {words["brief.approved"]: "approve", words["brief.changes_requested"]: "change"}
        said = "|".join(re.escape(x) for x in (*labels, words["brief.no_decision"]))
        line = re.compile(rf"^(?P<cid>[A-Za-z0-9_-]+): (?P<label>{said})(?: \| (?P<note>.*))?$")
        out.append((head, tail, labels, line))
    return out
READ_AGAIN = page.READ_AGAIN.format(collection=COLLECTION)
_TOO_LARGE = ("If it says tooLarge again, ask that person for their decision in chat, record the choice with `tm brief "
              "choose --source chat` and stop waiting with `tm brief await --clear`.")


def _note(value) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _from_db(data: dict) -> dict:
    return {cid: {"d": x["d"], "n": _note(x.get("n"))} for cid, x in data.items()
            if isinstance(x, dict) and x.get("d") in _CHOICES}


def _from_text(text: str, title: str | None, lang: str | None = None) -> list[dict]:
    docs: list[dict] = []
    current, last, seen = None, None, set()
    languages, words = _copy_words(lang), None
    for line in text.splitlines():
        header = next((w for w in languages if line.startswith(w[0])), None)
        if header is not None:
            head, tail = header[0], header[1]
            named = line[len(head):-len(tail)] if tail and line.endswith(tail) else line[len(head):]
            if title is not None and named != title:
                raise Stop(f'This "Copy my decisions" text is from the page "{named}", not this one ("{title}"). Ask '
                           "for the text from this page. The run continues from the same place.")
            current, last, seen = {"who": f"copied text {len(docs) + 1}", "decisions": {}}, None, set()
            words = header
            docs.append(current)
            continue
        m = words[3].match(line) if current is not None else None
        if m:
            if m["cid"] in seen:      # the page writes one line per concept: one of these is a note's line
                raise Stop(f"Copied text {len(docs)} has two lines for {m['cid']}, so a note line reads like a "
                           "decision and the text is ambiguous. Ask that person what they decided on "
                           f"{m['cid']}, or read the decisions with an ArtifactData list. The run continues from the same "
                           "place.")
            seen.add(m["cid"])
            last = None
            if m["label"] in words[2]:
                current["decisions"][m["cid"]] = {"d": words[2][m["label"]], "n": m["note"] or ""}
                last = current["decisions"][m["cid"]] if m["note"] is not None else None
        elif last is not None:                   # a note with a line break goes on
            last["n"] += "\n" + line
    for d in docs:
        for x in d["decisions"].values():
            x["n"] = x["n"].rstrip()
    if not docs:
        raise Stop(f'The text holds no "Copy my decisions" text from the page (it starts with {_HEADER}…"). Paste '
                   f"the text as the page gave it, then read it again. The run continues from the same place.")
    return docs


def read_decisions(saved: dict | str, *, title: str | None = None, lang: str | None = None) -> list[dict]:
    """The decisions in a saved ArtifactData list/query (or `db_list`) answer (an envelope or its answer: every JSON
    object with an `id` in its text, or in its JSON) or in the page's "Copy my decisions" text
    (whose header must name `title`, when given; in English or `lang`, the page's language). Each is `{"who", "decisions": {concept: {"d":
    "approve"|"change", "n": note}}}`; a note stays a plain string. A read that may hold part of the
    decisions is a Stop: an error answer, one page of several, a document without data (tooLarge),
    a line that does not parse, a summary count that differs from the documents read; and for
    copied text, another page's title or two lines for one concept."""
    if isinstance(saved, str):
        return _from_text(saved, title, lang)
    docs = dict(page.db_docs(saved, collection=COLLECTION, chat=_TOO_LARGE))
    return [{"who": who, "decisions": _from_db(data)} for who, data in docs.items()]


def verdicts(docs: list[dict], concept_ids: list[str]) -> dict[str, dict]:
    """Per concept: approved (at least one approve, no change), changes (changes only), split
    (both), none (no decision); the approve count and each change with its note."""
    out = {}
    for cid in concept_ids:
        mine = [(d["who"], d["decisions"][cid]) for d in docs if cid in d["decisions"]]
        approve = sum(1 for _, x in mine if x["d"] == "approve")
        change = [{"who": who, "note": x["n"]} for who, x in mine if x["d"] == "change"]
        verdict = ("none" if not approve and not change else "approved" if not change
                   else "changes" if not approve else "split")
        out[cid] = {"verdict": verdict, "approve": approve, "change": change}
    return out


def quote_notes(docs: list[dict], concept_ids: list[str], lang: str = i18n.ENGLISH) -> tuple[list[dict], str]:
    """Every note left on the page, as written (issue #55): `[{concept, who, choice, note}]` by concept, then
    person, an approval's note too; and the lines that quote them to the user, ready to paste, one per note:
    `C2, u1, Changes requested: "<the note, whole>"` (the choice in the page's words, `lang`). An empty note is
    no note. Nothing is shortened: a note that reads like an order to the agent is quoted whole like any other."""
    words = {"approve": i18n.t("brief.approved", lang), "change": i18n.t("brief.changes_requested", lang)}
    notes = [{"concept": cid, "who": d["who"], "choice": x["d"], "note": x["n"]}
             for cid in concept_ids for d in docs
             for x in [d["decisions"].get(cid)] if x and x["d"] in words and x["n"].strip()]
    quote = "\n".join(f'{n["concept"]}, {n["who"]}, {words[n["choice"]]}: "{n["note"]}"' for n in notes)
    return notes, quote


def _ids_of(brief: dict, rel: str) -> list[str]:
    concepts = brief.get("concepts")
    if not isinstance(concepts, list):
        raise Stop(f"{rel} has no concepts list. Fix brief.json (a new version); {AGAIN}.")
    return [c["id"] for c in concepts if isinstance(c, dict) and isinstance(c.get("id"), str)]


def _slug(run: RunFolder) -> str | None:
    record = state.load(run).pages.get(PAGE) or {}
    return record.get("slug") or None


def decided_page(run: RunFolder) -> dict:
    """The page people decide on and the brief it was built from: the published folder
    (`state.pages["brief_pack"]`), else the latest build; its `tm brief page` manifest row gives the
    brief and its sha256. `{page, brief, brief_sha256, ids, title}`. Stop when that brief is gone
    or changed since."""
    target = (state.load(run).pages.get(PAGE) or {}).get("folder")
    rows = [r for r in manifest.rows(run) if r["source"] == SOURCE and (target is None or r["file"] == target)]
    if not rows:
        where = f"the published folder {target}" if target else "this run"
        raise Stop(f"No page build of {where} is recorded (tm brief page), so it is unknown which brief people "
                   f"decided on. Build the page and publish it, then read the decisions. The run continues from the "
                   "same place.")
    row = rows[-1]
    try:
        params = json.loads(row["params"]) if row["params"] else {}
    except ValueError:
        params = {}
    path = run.path / row["parent"]
    if not path.is_file() or params.get("brief_sha256") != stepchecks.sha256(path):
        raise Stop(f"The page {row['file']} was built from {row['parent']}, which is gone or changed since, so it is "
                   "unknown which concepts people decided on. Rebuild the page (tm brief page), publish it again and "
                   "let people decide on it. The run continues from the same place.")
    _, rel, brief = load_brief(run, path)
    return {"page": row["file"], "brief": rel, "brief_sha256": params["brief_sha256"], "ids": _ids_of(brief, rel),
            "title": str((brief.get("meta") or {}).get("title", ""))}


def mark_carried(docs: list[dict], earlier: list[dict]) -> dict[str, list[str]]:
    """Mark each row (a person's decision on a concept) equal to the one the earlier decisions file
    recorded for that person and concept as `carried: true`, in place (`page.mark_carried`, keyed by
    person and concept). Returns {concept: [who, ...]} of the carried rows."""
    rows = {(d["who"], cid): x for d in docs for cid, x in d["decisions"].items()}
    before = {(d.get("who"), cid): x for d in earlier if isinstance(d, dict)
              for cid, x in (d.get("decisions") or {}).items()}
    carried: dict[str, list[str]] = {}
    for who, cid in page.mark_carried(rows, before):
        carried.setdefault(cid, []).append(who)
    return {cid: carried[cid] for cid in sorted(carried)}


def _earlier_docs(run: RunFolder, built: str) -> list[dict]:
    """The rows of the latest decisions file read on another page build than `built` ([] when there
    is none): `page.earlier_decisions`."""
    return page.earlier_decisions(run, _decisions_files(run), built, built="page", rows="docs",
                                  command="tm brief decisions", shape=list) or []


def take_decisions(run: RunFolder, stage: str, *, file: Path | None = None, text: Path | None = None) -> dict:
    """Read the decisions taken on the page into `03_wip/decisions_<stage>_vNN.json` and clear the
    wait. The concepts are those of the brief the page was built from (`decided_page`). Default
    input: the latest saved db answer on this page's slug (another artifact's answer is never read
    as this page's); a read that may hold part of the decisions is refused. A row equal to the
    decisions file of an earlier page build is marked carried (`mark_carried`, `_earlier_docs`); the
    verdicts still count it."""
    if stage not in STAGES:
        raise ValueError(f"The stage is one of {', '.join(STAGES)}, not {stage!r}.")
    slug = _slug(run)
    if text is None and slug is None:
        raise Stop(f"The page's publish is not recorded (tm page published --page {PAGE}), so it is unknown which "
                   "artifact's decisions to read. Record it, read the decisions with an ArtifactData list first, or give the "
                   "copied text with --text. The run continues from the same place.")
    decided = decided_page(run)
    if text is not None:
        source = Path(text)
        docs = read_decisions(source.read_text(encoding="utf-8-sig"), title=decided["title"],
                              lang=i18n.run_languages(run).working)
    else:
        if file is None:
            file = page.saved_answer(run, PAGE, COLLECTION)
            if file is None:
                raise Stop(f"No saved answer holds the decisions of this page ({slug}): read the decisions with "
                           f"an ArtifactData list first (the page's url, collection {COLLECTION}, query.limit 1000; "
                           f"with the older tools, db_list on slug {slug}), then run this again. "
                           "The run continues from the same place.")
        source = Path(file)
        docs = read_decisions(page.whole_answer(run, PAGE, source, COLLECTION))
    rel = _rel(run, source)
    carried = mark_carried(docs, _earlier_docs(run, decided["page"]))
    got = verdicts(docs, decided["ids"])
    notes, quote = quote_notes(docs, decided["ids"], i18n.page_lang(i18n.run_languages(run).working, "brief").lang)
    latest = run.latest(FINAL, STEM, "json")
    latest_rel = _rel(run, latest) if latest else None
    same = latest is not None and latest_rel == decided["brief"] and stepchecks.sha256(latest) == decided["brief_sha256"]
    not_in_latest = [] if same else [c for c in decided["ids"] if latest is None
                                     or c not in _ids_of(load_brief(run, latest)[2], latest_rel)]
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = run.next_version(WIP, f"decisions_{stage}", "json")
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {"stage": stage, "from": rel, "slug": slug, "at": at, "page": decided["page"], "brief": decided["brief"],
            "brief_sha256": decided["brief_sha256"], "docs": docs, "verdicts": got, "carried": carried}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, WIP, DECISIONS_SOURCE, parent=rel,
                    params={"stage": stage, "page": decided["page"], "brief": decided["brief"]})
    page.clear_await(run, PAGE)
    return {"file": out_rel, "from": rel, "stage": stage, "page": decided["page"], "brief": decided["brief"],
            "latest_brief": latest_rel, "brief_is_latest": same, "not_in_latest": not_in_latest,
            "verdicts": got, "carried": carried, "docs": len(docs), "notes": notes, "quote": quote}


def await_decisions(run: RunFolder, stage: str | None, version: str | None, *, clear: bool = False) -> dict | None:
    """Mark that people decide on the published page (`page.await_` on brief_pack, with the stage),
    or clear it (`tm brief await` is `tm page await --page brief_pack` with a stage)."""
    if clear:
        page.clear_await(run, PAGE)
        return None
    if stage not in STAGES:
        raise ValueError(f"--stage is one of {', '.join(STAGES)}.")
    return page.await_(run, PAGE, version, stage)


def _latest_decisions(run: RunFolder) -> Path | None:
    found = _decisions_files(run)
    return found[-1] if found else None


def _decisions_files(run: RunFolder) -> list[Path]:
    """The decisions files of `tm brief decisions`, in the order they were read (their `at`)."""
    name = re.compile(r"^decisions_(G\d)_v(\d+)\.json$")
    found = []
    folder = run.path / WIP
    for f in folder.glob("decisions_*_v*.json") if folder.is_dir() else ():
        m = name.match(f.name)
        if m:
            try:
                at = str(trends.read(f).get("at") or "")
            except (ValueError, AttributeError):
                at = ""
            found.append((at, m.group(1), int(m.group(2)), f))
    return [f for *_, f in sorted(found)]


def rule_pick(run: RunFolder, brief: dict) -> list[str]:
    """What `tm brief pick` picks from this brief (Hands-off G2)."""
    return brief_checks.rule_pick(run, brief)["picked"]


def choose(run: RunFolder, concepts: list[str], source: str, decisions: Path | None = None, *,
           keep_carried: bool = False) -> dict:
    """Record the concepts chosen to brief (`state.brief.chosen`): from the page (each one approved
    in the decisions file, and no approval carried over from an earlier page unless the user kept
    those in chat: `keep_carried`), the rule (exactly `tm brief pick`), or the user's word in chat.
    It never decides a check-in."""
    if source not in SOURCES:
        raise ValueError(f"--source is one of {', '.join(SOURCES)}, not {source!r}.")
    if keep_carried and source != "page":
        raise ValueError("--keep-carried keeps approvals carried over on the page: it goes with --source page.")
    chosen = list(dict.fromkeys(concepts))
    if not chosen:
        raise ValueError("Name at least one concept, e.g. --concepts C1 C3.")
    latest, rel, brief = load_brief(run, None)
    ids = _ids_of(brief, rel)
    unknown = [c for c in chosen if c not in ids]
    if unknown:
        raise ValueError(f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not a concept of the latest brief "
                         f"({rel}: {', '.join(ids)}).")
    used, kept = None, []
    if source == "page":
        path = Path(decisions) if decisions is not None else _latest_decisions(run)
        if path is None:
            raise Stop("No decisions have been read from the page yet: read them with tm brief decisions first. The "
                       "run continues from the same place.")
        used = _rel(run, path)
        try:
            read = trends.read(path)
            got = read.get("verdicts") or {}
        except (ValueError, AttributeError):
            raise Stop(f"{used} is not a decisions file of tm brief decisions; {AGAIN}.") from None
        if read.get("brief") != rel or read.get("brief_sha256") != stepchecks.sha256(latest):
            was = read.get("brief") or "an unknown brief"
            raise Stop(f"The decisions in {used} were taken on the page built from {was}, and the brief is now {rel}. Rebuild the page (tm brief page) and publish it again, "
                       "then let people decide on it and read their decisions; or ask the user in chat and record "
                       "their answer with --source chat. The run continues from the same place.")
        not_approved = [f"{c} ({(got.get(c) or {}).get('verdict', 'not on the page')})" for c in chosen
                        if (got.get(c) or {}).get("verdict") != "approved"]
        if not_approved:
            raise Stop(f"Only a concept approved on the page is chosen from it, and {', '.join(not_approved)} "
                       f"{'is' if len(not_approved) == 1 else 'are'} not, in {used}. Show the user the notes and "
                       "ask in chat; record their answer with --source chat. The run continues from the same place.")
        held: dict[str, list[str]] = {}
        for d in read.get("docs") or []:
            for c in chosen:
                x = (d.get("decisions") or {}).get(c) if isinstance(d, dict) else None
                if isinstance(x, dict) and x.get("d") == "approve" and x.get("carried"):
                    held.setdefault(c, []).append(str(d.get("who")))
        if held and not keep_carried:
            n = sum(len(w) for w in held.values())
            listed = "; ".join(f"{c}: {', '.join(map(str, w))}" for c, w in held.items())
            raise Stop(f"{n} approval{'' if n == 1 else 's'} in {used} {'was' if n == 1 else 'were'} carried over from "
                       f"an earlier page ({listed}): the page shows each person's earlier choice until they save "
                       "again. Ask the user once whether to keep them; on a yes, choose again with --keep-carried. "
                       "The run continues from the same place.")
        kept = sorted(held)
    elif source == "rule":
        picked = rule_pick(run, brief)
        if sorted(chosen) != sorted(picked):
            raise Stop(f"The rule (tm brief pick) picks {', '.join(picked) or 'none'}, not {', '.join(chosen)}. "
                       f"Choose what it picks, or ask the user and record their answer with --source chat. The run "
                       "continues from the same place.")
    record = {"concepts": chosen, "source": source, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if kept:
        record["kept_carried"] = kept
    s = state.load(run)
    s.brief = {**(s.brief or {}), "chosen": record}
    state.save(run, s)
    return {**record, "brief": rel, "decisions": used}


# --- the step checks -------------------------------------------------------------------------------

def built_gap(run: RunFolder) -> str | None:
    """`page_built`: a page folder or file built from the latest brief, unchanged since."""
    latest = run.latest(FINAL, STEM, "json")
    if latest is None:
        return f"{FINAL}/{STEM}_vNN.json is written and the page built from it (tm brief page)"
    try:
        rel = latest.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        return f"the latest {STEM} is a file inside the run folder"
    sha = stepchecks.sha256(latest)
    for row in reversed(manifest.rows(run)):
        if row["source"] != SOURCE or row["parent"] != rel:
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        if isinstance(params, dict) and params.get("brief_sha256") == sha and (run.path / row["file"]).exists():
            return None
    return f"the page is built from the latest brief, {rel} (tm brief page)"


def chosen_gap(run: RunFolder) -> str | None:
    """`concepts_chosen`: a choice is recorded and its concepts are in the latest brief."""
    chosen = (state.load(run).brief or {}).get("chosen") or {}
    concepts = chosen.get("concepts") or []
    if not concepts:
        return "the concepts to brief are chosen (tm brief choose)"
    latest = run.latest(FINAL, STEM, "json")
    try:
        brief = json.loads(latest.read_text(encoding="utf-8-sig")) if latest else None
        ids = {c["id"] for c in brief["concepts"]}
    except (OSError, ValueError, TypeError, KeyError):
        return f"the latest {STEM} is readable, with the chosen concepts in it"
    gone = [c for c in concepts if c not in ids]
    if gone:
        return (f"the chosen concepts are in the latest brief ({latest.name} has no {', '.join(gone)}): choose again "
                "(tm brief choose)")
    return None
