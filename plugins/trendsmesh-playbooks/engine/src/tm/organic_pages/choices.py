"""Organic video's pages of choices (issue #83, #86): the intake (A0), the style, voice and music (D2) and the models
(after the idea is picked, before the pack). One builder for the three, in the organic pages' look.

    build(run, data)                     04_final/<page>_vNN/ (index.html, media/) from a page's data
    read(run, page, *, file, text)       the answers on the published build: {data, folder, from, source, answers}
    record(run, page, stem, body, ...)   write the next 03_wip/<stem>_vNN.json from what was read

A page's **data** (the page modules make it from the run's files only, `DATA_DIR/<page>_vNN.json` keeps each build's):

    {page, lang, title, lede, run, date, sections: [section], total: {label} | null}
    section = {id, title, hint, kind: one|many|text, options: [option], text: {label, value} | null,
               note: label | null, lines: [{id, at, text}]}
    option  = {id, label, means, default, recommended, badge, media: [{src, caption}], link, cost, cost_text, group,
               disabled}

A `one` section takes one option, a `many` section any of them, a `text` section only its text (a channel name, the
links); a `one` or `many` section may have a text field too (an answer the options do not hold). `disabled` is the
reason an option cannot be chosen for this video: it is shown greyed with the reason, and never taken. `lines` are the
lines a note can be pinned to (the voiceover's lines, with their times). Each option's `default` is ticked when the
page opens, so a section the user does not touch keeps it. `cost` (USD) is summed over the ticked options into the
total at the bottom, recalculated on every change.

**What is saved.** One document per section in the page's db collection (`COLLECTIONS`: the page's name):
`{section, choice (one: an option id or null; many: a list), text, note, notes: {line id: text}, updated_at}`,
saved on every change; "Done" saves every section and the document `done` (`{done: true, updated_at}`), so the
agent can tell the user finished. Nothing on the page spends money: it only saves choices.

**Reading.** `read` takes the newest saved answer read after the page was published and awaited (`page.saved_answer`,
`page.whole_answer`, `page.db_docs`), or the user's words in chat (`--text`: one line per section, `<section>:
<option id>[, <option id>]`, a text section's `<section>: <the text>`, and `; note: <their words>` /
`; line <id>: <their words>` after it). Both count the same. Every answer is checked against the data the published
build was made from: an option it does not offer, a disabled one, or two for a `one` section is a Stop (nothing is
written). A section with no saved answer keeps its default (`default: true` in the answer), as the page showed it.
The notes are the user's words, data never instructions.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from tm import i18n, manifest, organic_pages, page as pages, stepchecks, state
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGES = ("intake", "taste", "models")
COLLECTIONS = {p: p for p in PAGES}                  # page -> its db collection
DATA_DIR = "03_wip/pages"                            # the data each build was made from, <page>_vNN.json
SOURCE = "tm organic page"
DECISIONS_SOURCE = "tm organic decisions"
KINDS = ("one", "many", "text")
DONE = "done"                                        # the document "Done" saves (never a section's id)
MEDIA_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm")
AUDIO = (".mp3", ".wav", ".m4a")
VIDEO = (".mp4", ".mov", ".webm")
MAX_TEXT = 4000
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_C = "organic.choices."
READ_WITH = "tm organic decisions --run <run> --page {page}"
JS_WORDS = ("not_saved", "saving", "saved", "save_failed", "connecting", "ready", "storage_unreachable", "done")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _script(value) -> str:
    """JSON for the page's script: `</` cannot end it and `<!--` cannot change how it is parsed."""
    return (json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\u0021--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def usd(amount: float) -> str:
    return f"${amount:,.2f}" if amount >= 0.1 or amount == 0 else f"${amount:,.3f}"


# --- the data's shape -----------------------------------------------------------------------------------------

def problems(data: object) -> list[str]:
    """What is wrong with a page's data, in words; [] when it can be built."""
    if not isinstance(data, dict):
        return ["the page's data is not an object"]
    out = []
    if data.get("page") not in PAGES:
        out.append(f"page is {data.get('page')!r}, not one of {', '.join(PAGES)}")
    for key in ("title", "run", "date"):
        if not (isinstance(data.get(key), str) and data[key].strip()):
            out.append(f"{key} is needed")
    sections = data.get("sections")
    if not (isinstance(sections, list) and sections):
        return out + ["sections must list at least one section"]
    seen: set[str] = set()
    for n, sec in enumerate(sections, 1):
        if not isinstance(sec, dict):
            out.append(f"section {n} is not an object")
            continue
        sid = sec.get("id")
        if not (isinstance(sid, str) and _ID.match(sid)) or sid == DONE or sid in seen:
            out.append(f"section {n}: id {sid!r} must be unique letters, digits, _ . - (and not {DONE!r})")
        seen.add(sid if isinstance(sid, str) else "")
        kind = sec.get("kind")
        if kind not in KINDS:
            out.append(f"section {sid}: kind {kind!r} is not one of {', '.join(KINDS)}")
        options = sec.get("options") or []
        if kind in ("one", "many") and not options:
            out.append(f"section {sid}: a {kind} section needs options")
        ids: set[str] = set()
        defaults = 0
        for o in options:
            oid = o.get("id") if isinstance(o, dict) else None
            if not (isinstance(oid, str) and _ID.match(oid)) or oid in ids:
                out.append(f"section {sid}: option id {oid!r} must be unique letters, digits, _ . -")
                continue
            ids.add(oid)
            if not (isinstance(o.get("label"), str) and o["label"].strip()):
                out.append(f"section {sid}: option {oid} needs a label")
            if o.get("default"):
                defaults += 1
                if o.get("disabled"):
                    out.append(f"section {sid}: option {oid} is the default and cannot be chosen")
            cost = o.get("cost")
            if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0):
                out.append(f"section {sid}: option {oid}'s cost must be a number of USD from 0")
            for m in o.get("media") or []:
                src = m.get("src") if isinstance(m, dict) else None
                if not (isinstance(src, str) and Path(src).suffix.lower() in MEDIA_EXT):
                    out.append(f"section {sid}: option {oid}'s media {src!r} is not an image, a sound or a video")
        if kind == "one" and defaults > 1:
            out.append(f"section {sid}: a one section has at most one default")
        lines = sec.get("lines") or []
        if any(not (isinstance(x, dict) and isinstance(x.get("id"), str) and _ID.match(x["id"])) for x in lines):
            out.append(f"section {sid}: each line needs an id")
    return out


def _sources(data: dict) -> list[str]:
    return [m["src"] for sec in data["sections"] for o in sec.get("options") or [] for m in o.get("media") or []]


def _names(run: RunFolder, data: dict) -> dict[str, tuple[str, Path]]:
    """src -> (its name in media/, the file). Only a file inside the run is shown: a page reads the run's files."""
    out: dict[str, tuple[str, Path]] = {}
    taken: dict[str, Path] = {}
    root = run.path.resolve()
    for src in _sources(data):
        if src in out:
            continue
        path = (run.path / src).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise Stop(f"{src} is not a file of this run, and a page shows only the run's own files. Copy it into the "
                       f"run first (02_research/ or 03_wip/), name it there and build again; {AGAIN}.") from None
        if not path.is_file():
            raise Stop(f"{src} is not there, so the page cannot show it. Make it again or leave it out, then build the "
                       f"page again; {AGAIN}.")
        name, n = pages.asset_name(path.name), 1
        while name.casefold() in taken and taken[name.casefold()] != path:
            n += 1
            name = f"{n}_{pages.asset_name(path.name)}"
        taken[name.casefold()] = path
        out[src] = (name, path)
    return out


# --- the page ------------------------------------------------------------------------------------------------

CSS = """
:root{--bg:#F2F4F6;--surface:#FFFFFF;--ink:#13202A;--muted:#5A6977;--line:#D9DFE5;--accent:#B7791F;--accent-soft:#F6EBD9;
--ok:#2F7D4F;--ok-soft:#E3F2E8;--warn:#A86A00;--warn-soft:#FBF0D9;--bad:#B23A3A;--bad-soft:#F8E1E1;
--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:"Source Sans 3","Segoe UI",system-ui,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--body)}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 64px;display:grid;gap:20px}
.eyebrow{font:600 13px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(26px,4vw,38px)/1.1 var(--display);margin:0}h2{font:700 21px/1.2 var(--display);margin:0}
.lede,.hint{color:var(--muted);max-width:72ch;margin:0}.hint{font-size:14px}
section.q{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;display:grid;gap:12px}
.group{font:600 12px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-top:4px}
.opts{display:grid;gap:8px}
.opt{display:grid;grid-template-columns:auto 1fr auto;gap:4px 12px;align-items:start;padding:10px 12px;border:2px solid var(--line);border-radius:10px;background:var(--bg);cursor:pointer}
.opt:has(input:checked){border-color:var(--ok);background:var(--ok-soft)}
.opt.off{opacity:.55;cursor:not-allowed}.opt input{margin-top:4px;width:17px;height:17px;accent-color:var(--ink)}
.opt b{font-weight:700}.opt .means{display:block;font-size:14px;color:var(--muted)}
.opt .why-off{display:block;font-size:13px;color:var(--bad)}
.opt .cost{font:700 15px/1.2 var(--display);font-variant-numeric:tabular-nums;white-space:nowrap}
.opt .media{grid-column:2/4;display:flex;flex-wrap:wrap;gap:8px}.opt .media img,.opt .media video{max-width:min(220px,100%);border-radius:6px;background:#000}
.opt .media audio{width:min(340px,100%)}.opt a{font-size:13px;color:var(--muted)}
.badge{font:700 11px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-left:6px}
.lines{display:grid;gap:8px;margin:0;padding:0;list-style:none}.lines li{display:grid;gap:4px;border-left:3px solid var(--line);padding-left:10px}
.lines .at{font:600 12px/1 var(--body);color:var(--muted);font-variant-numeric:tabular-nums}
label.fld{display:grid;gap:4px;font-size:14px}
textarea,input[type=text]{font:15px/1.4 var(--body);color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:8px 10px;width:100%}
textarea{min-height:42px;resize:vertical}
.bar{position:sticky;bottom:0;z-index:5;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:0 -6px 18px rgba(0,0,0,.06)}
.total{font:700 20px/1 var(--display);font-variant-numeric:tabular-nums}
.btn{font:600 15px/1 var(--body);padding:10px 16px;border-radius:8px;border:1px solid var(--ink);background:var(--ink);color:var(--surface);cursor:pointer}
.btn:focus-visible,textarea:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.status{font-size:13px;color:var(--muted)}footer{font-size:13px;color:var(--muted)}
@media (max-width:700px){.bar{position:static}.opt{grid-template-columns:auto 1fr}.opt .cost{grid-column:2}}
"""

JS = r"""
(function(){
  const P = JSON.parse(document.getElementById('tm-choices').textContent), W = P.words, COL = P.collection;
  const KEY = 'tm-choices-' + P.run + '-' + COL; const st = document.getElementById('save-status');
  const say = t => { st.textContent = t; }; let db = null;
  const state = {};
  P.sections.forEach(s => { state[s.id] = {section: s.id, choice: s.kind === 'many' ? s.defaults.slice() : (s.defaults[0] || null), text: s.text, note: '', notes: {}}; });
  try { const kept = JSON.parse(localStorage.getItem(KEY) || 'null'); if (kept) Object.keys(kept).forEach(k => { if (state[k]) Object.assign(state[k], kept[k]); }); } catch (e) {}
  const total = document.getElementById('total');
  function paint(){
    P.sections.forEach(s => {
      const v = state[s.id];
      document.querySelectorAll(`input[data-s="${s.id}"]`).forEach(i => { i.checked = s.kind === 'many' ? v.choice.includes(i.value) : v.choice === i.value; });
      const tx = document.getElementById('t-' + s.id); if (tx && document.activeElement !== tx) tx.value = v.text || '';
      const nt = document.getElementById('n-' + s.id); if (nt && document.activeElement !== nt) nt.value = v.note || '';
      document.querySelectorAll(`textarea[data-line][data-s="${s.id}"]`).forEach(t => { if (document.activeElement !== t) t.value = v.notes[t.dataset.line] || ''; });
    });
    if (total) {
      let sum = 0; document.querySelectorAll('input[data-cost]:checked').forEach(i => { sum += +i.dataset.cost; });
      total.textContent = '$' + (sum >= 0.1 || sum === 0 ? sum.toFixed(2) : sum.toFixed(3));
    }
  }
  const pending = {};
  async function save(id, doc){
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
    if (!db) { say(W.not_saved); return; }
    if (pending[id]) { pending[id].again = true; return; }
    pending[id] = {again: false}; say(W.saving);
    try { do { pending[id].again = false; await db.doc(COL + '/' + id).set(Object.assign({}, doc || state[id], {updated_at: new Date().toISOString()})); } while (pending[id].again);
      say(W.saved); } catch (e) { say(W.save_failed); }
    delete pending[id];
  }
  const timers = {}; const soon = id => { clearTimeout(timers[id]); timers[id] = setTimeout(() => save(id), 600); };
  P.sections.forEach(s => {
    document.querySelectorAll(`input[data-s="${s.id}"]`).forEach(i => i.addEventListener('change', () => {
      state[s.id].choice = s.kind === 'many' ? [...document.querySelectorAll(`input[data-s="${s.id}"]:checked`)].map(x => x.value) : i.value;
      paint(); save(s.id);
    }));
    const tx = document.getElementById('t-' + s.id); if (tx) tx.addEventListener('input', () => { state[s.id].text = tx.value; soon(s.id); });
    const nt = document.getElementById('n-' + s.id); if (nt) nt.addEventListener('input', () => { state[s.id].note = nt.value; soon(s.id); });
    document.querySelectorAll(`textarea[data-line][data-s="${s.id}"]`).forEach(t => t.addEventListener('input', () => { state[s.id].notes[t.dataset.line] = t.value; soon(s.id); }));
  });
  document.getElementById('done').addEventListener('click', async () => {
    for (const s of P.sections) await save(s.id);
    await save(P.done, {done: true}); if (db) say(W.done);
  });
  paint(); say(W.connecting);
  (async () => {
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    try { db = window.claude && window.claude.use ? await window.claude.use('db') : null; } catch (e) { db = null; }
    if (!db) { say(W.not_saved); return; }
    try { const snap = await db.collection(COL).get();
      snap.docs.forEach(d => { const v = d.data(); if (v && state[d.id]) ['choice','text','note','notes'].forEach(k => { if (v[k] !== undefined && v[k] !== null) state[d.id][k] = v[k]; }); });
      paint(); say(W.ready);
    } catch (e) { say(W.storage_unreachable); }
  })();
})();
"""


def _media(src: str, caption: str) -> str:
    low = src.lower()
    if low.endswith(AUDIO):
        return f'<audio src="{esc(src)}" controls preload="none" aria-label="{esc(caption)}"></audio>'
    if low.endswith(VIDEO):
        return f'<video src="{esc(src)}" controls playsinline preload="metadata" aria-label="{esc(caption)}"></video>'
    return (f'<a href="{esc(src)}" target="_blank" rel="noopener"><img src="{esc(src)}" alt="{esc(caption)}" '
            f'loading="lazy"></a>')


def _option(sec: dict, o: dict, put, tr) -> str:
    sid, oid = sec["id"], o["id"]
    kind = "checkbox" if sec["kind"] == "many" else "radio"
    off = o.get("disabled")
    cost = o.get("cost")
    cost_attr = f' data-cost="{float(cost):.6f}"' if isinstance(cost, (int, float)) and not off else ""
    badges = "".join(f'<span class="badge">{esc(b)}</span>' for b in (
        [tr(_C + "recommended")] if o.get("recommended") else []) + ([o["badge"]] if o.get("badge") else []))
    means = f'<span class="means">{esc(o["means"])}</span>' if o.get("means") else ""
    why = f'<span class="why-off">{esc(tr(_C + "cannot", reason=off))}</span>' if off else ""
    link = (f' · <a href="{esc(o["link"])}" target="_blank" rel="noopener">{esc(tr(_C + "open_page"))}</a>'
            if isinstance(o.get("link"), str) and re.match(r"^https?://[^\s\"'<>]+$", o["link"]) else "")
    price = o.get("cost_text") or (usd(float(cost)) if isinstance(cost, (int, float)) else "")
    media = "".join(_media(put(m["src"]), m.get("caption") or o["label"]) for m in o.get("media") or [])
    return (f'<label class="opt{" off" if off else ""}"><input type="{kind}" name="o-{esc(sid)}" value="{esc(oid)}" '
            f'data-s="{esc(sid)}"{cost_attr}{" disabled" if off else ""}>'
            f'<span><b>{esc(o["label"])}</b>{badges}{means}{why}{link}</span><span class="cost">{esc(price)}</span>'
            + (f'<span class="media">{media}</span>' if media else "") + "</label>")


def _section(sec: dict, put, tr) -> str:
    sid = esc(sec["id"])
    head = (f'<h2>{esc(sec["title"])}</h2>' if sec.get("title") else "") + (
        f'<p class="hint">{esc(sec["hint"])}</p>' if sec.get("hint") else "")
    body = []
    if sec.get("lines"):
        items = "".join(
            f'<li><span class="at">{esc(x.get("at") or "")}</span><span>{esc(x.get("text") or "")}</span>'
            f'<label class="fld"><span class="hint">{esc(tr(_C + "line_note"))}</span><textarea rows="1" '
            f'data-s="{sid}" data-line="{esc(x["id"])}"></textarea></label></li>' for x in sec["lines"])
        body.append(f'<ol class="lines">{items}</ol>')
    group, opts = None, []
    for o in sec.get("options") or []:
        if o.get("group") and o["group"] != group:
            group = o["group"]
            opts.append(f'<div class="group">{esc(group)}</div>')
        opts.append(_option(sec, o, put, tr))
    if opts:
        role = "group" if sec["kind"] == "many" else "radiogroup"
        body.append(f'<div class="opts" role="{role}" aria-label="{esc(sec.get("title") or sec["id"])}">{"".join(opts)}</div>')
    text = sec.get("text")
    if text:
        body.append(f'<label class="fld"><span>{esc(text.get("label") or "")}</span><textarea id="t-{sid}" '
                    f'rows="{2 if sec["kind"] == "text" else 1}"></textarea></label>')
    if sec.get("note"):
        body.append(f'<label class="fld"><span class="hint">{esc(sec["note"])}</span><textarea id="n-{sid}" '
                    f'rows="1"></textarea></label>')
    return f'<section class="q" id="q-{sid}">{head}{"".join(body)}</section>'


def render(data: dict, put, lang: str) -> str:
    """The page's HTML in `lang`, with `put(src) -> "media/<name>"`."""
    tr = organic_pages.translator(lang)
    words = {k: tr(_C + k) for k in JS_WORDS}
    meta = {"run": Path(data["run"]).name, "collection": COLLECTIONS[data["page"]], "done": DONE, "words": words,
            "sections": [{"id": s["id"], "kind": s["kind"],
                          "defaults": [o["id"] for o in s.get("options") or [] if o.get("default")],
                          "text": (s.get("text") or {}).get("value") or ""} for s in data["sections"]]}
    total = data.get("total")
    bar_total = (f'<span>{esc(total.get("label") or tr(_C + "total"))} <span class="total" id="total"></span></span>'
                 if total else "<span></span>")
    eyebrow = tr(_C + "eyebrow", page=tr(_C + "page_" + data["page"]))
    return (f'<!DOCTYPE html><html lang="{esc(i18n.html_lang(lang))}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(data["title"])}</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700'
            '&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">'
            f'<style>{CSS}</style></head><body><div class="wrap">'
            f'<header style="display:grid;gap:8px"><div class="eyebrow">{esc(eyebrow)} · {esc(data["date"])}</div>'
            f'<h1>{esc(data["title"])}</h1>' + (f'<p class="lede">{esc(data["lede"])}</p>' if data.get("lede") else "")
            + f'<p class="hint">{esc(tr(_C + "how"))}</p></header>'
            + "".join(_section(s, put, tr) for s in data["sections"])
            + f'<div class="bar" role="region" aria-label="{esc(tr(_C + "your_choices"))}">{bar_total}'
            f'<span><button class="btn" id="done" type="button">{esc(tr(_C + "done_button"))}</button> '
            f'<span class="status" id="save-status" aria-live="polite"></span></span></div>'
            f'<footer>{esc(tr("organic.run_folder"))} {esc(data["run"])}</footer></div>'
            f'<script type="application/json" id="tm-choices">{_script(meta)}</script><script>{JS}</script>'
            "</body></html>")


# --- building it in the run --------------------------------------------------------------------------------

def run_ref(run: RunFolder) -> str:
    from tm import trend_spool
    try:
        return run.path.resolve().relative_to(trend_spool.workspace_of(run).resolve()).as_posix()
    except ValueError:
        return run.path.name


def today() -> str:
    return date.today().isoformat()


def build(run: RunFolder, data: dict, **params) -> dict:
    """Build the page of `data` into a new `04_final/<page>_vNN/` and keep the data as `03_wip/pages/<page>_vNN.json`.
    Nothing is written while people decide on the page (`page.Deciding`), for data not in the page's shape, for a
    file outside the run, or over the Artifact tool's limits (each a Stop). `params` go into the manifest row."""
    name = data.get("page") if isinstance(data, dict) else None
    if name in PAGES and pages.awaiting(run, name) is not None:
        raise pages.Deciding(name, read=READ_WITH.format(page=name))
    bad = problems(data)
    if bad:
        raise Stop(f"The {name or 'choices'} page's data is not in the page's shape ({'; '.join(bad[:5])}). Fix what it "
                   f"is made from, then build again; {AGAIN}.")
    built = organic_pages.page_lang(data)
    names = _names(run, data)
    text = render(data, lambda src: f"media/{names[src][0]}", built.lang)
    planned = {"index.html": len(text.encode("utf-8"))} | {f"media/{n}": p.stat().st_size for n, p in names.values()}
    over = pages.over_limits(planned)
    if over:
        raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Offer fewer or "
                   f"shorter clips, then build again; {AGAIN}.")
    out = pages.new_folder(run, name)
    (out / "media").mkdir()
    for media_name, path in dict(names.values()).items():
        shutil.copyfile(path, out / "media" / media_name)
    with open(out / "index.html", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    kept = run.next_version(DATA_DIR, name, "json")
    kept.parent.mkdir(parents=True, exist_ok=True)
    with open(kept, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    out_rel, kept_rel = out.relative_to(run.path).as_posix(), kept.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, pages.FINAL, f"{SOURCE} {name}", parent=kept_rel,
                    params={"page": name, "data_sha256": stepchecks.sha256(kept), "lang": built.lang,
                            "built_at": _now(), **params})
    return {"folder": out_rel, "files": pages.files(out), "data": kept_rel, "lang": built.lang, "page": name,
            "sections": len(data["sections"]), "language_warning": built.warning}


# --- reading the answers ------------------------------------------------------------------------------------

def decided(run: RunFolder, name: str) -> dict:
    """The build people decide on (the published folder, else the latest build) and the data it was made from:
    `{folder, data_file, data, params}`. Stop when the data is gone or changed since."""
    target = (state.load(run).pages.get(name) or {}).get("folder")
    rows = [r for r in manifest.rows(run) if r["source"] == f"{SOURCE} {name}"
            and (target is None or r["file"] == target)]
    if not rows:
        where = f"the published folder {target}" if target else "this run"
        raise Stop(f"No {name} page build of {where} is recorded (tm organic page {name}), so it is unknown what was "
                   f"asked. Build the page, publish it and let the user choose, or ask in chat; {AGAIN}.")
    row = rows[-1]
    try:
        params = json.loads(row["params"]) if row["params"] else {}
    except ValueError:
        params = {}
    path = run.path / row["parent"]
    if not path.is_file() or params.get("data_sha256") != stepchecks.sha256(path):
        raise Stop(f"The page {row['file']} was built from {row['parent']}, which is gone or changed since, so it is "
                   f"unknown what was asked. Build the page again (tm organic page {name}); {AGAIN}.")
    return {"folder": row["file"], "data_file": row["parent"],
            "data": json.loads(path.read_text(encoding="utf-8")), "params": params}


_NOTE = re.compile(r"^note\s*:\s*(.*)$", re.IGNORECASE | re.S)
_LINE = re.compile(r"^line\s+([A-Za-z0-9_.-]+)\s*:\s*(.*)$", re.IGNORECASE | re.S)


def parse_chat(text: str, data: dict) -> list[tuple[str, dict]]:
    """The user's answer in chat as documents: one line per section, `<section>: <option id>[, <option id>]` (a text
    section's `<section>: <the text>`), then `; note: …` and `; line <id>: …`. A line naming no section is a Stop."""
    by_id = {s["id"]: s for s in data["sections"]}
    docs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sid, sep, rest = line.partition(":")
        sid = sid.strip()
        if not sep or sid not in by_id:
            raise Stop(f"The chat answer's line {line!r} does not start with a section of the page "
                       f"({', '.join(by_id)}) and a colon. Write it again; {AGAIN}.")
        sec = by_id[sid]
        parts = [p.strip() for p in rest.split(";")]
        doc: dict = {"section": sid, "note": "", "notes": {}}
        head, extras = parts[0], parts[1:]
        if sec["kind"] == "text":
            doc["text"], doc["choice"] = head, None
        else:
            ids = [x.strip() for x in head.split(",") if x.strip()]
            known = {o["id"] for o in sec.get("options") or []}
            words = [x for x in ids if x not in known]
            if sec.get("text") and words and len(words) == len(ids):
                doc["choice"], doc["text"] = ([] if sec["kind"] == "many" else None), head
            else:
                doc["choice"] = ids if sec["kind"] == "many" else (ids[0] if len(ids) == 1 else ids)
        for extra in extras:
            if (m := _NOTE.match(extra)):
                doc["note"] = m.group(1).strip()
            elif (m := _LINE.match(extra)):
                doc["notes"][m.group(1)] = m.group(2).strip()
            elif extra:
                doc["note"] = "; ".join(x for x in (doc["note"], extra) if x)
        docs.append((sid, doc))
    if not docs:
        raise Stop(f"The chat answer holds no line for a section of the page ({', '.join(by_id)}); {AGAIN}.")
    return docs


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def answers(data: dict, docs: list[tuple[str, dict]]) -> tuple[dict[str, dict], bool, list[str]]:
    """Each section's answer from the documents (the newest per section), checked against `data`, and whether the
    user pressed Done: `({section: {choice, text, note, notes, default}}, done, problems)`."""
    newest: dict[str, dict] = {}
    done = False
    for did, doc in docs:
        if not isinstance(doc, dict):
            continue
        key = str(doc.get("section") or did)
        if did == DONE or key == DONE:
            done = done or doc.get("done") is True
            continue
        newest[key] = doc
    out, bad = {}, []
    known = {s["id"]: s for s in data["sections"]}
    bad += [f"{k!r} is not a section of this page" for k in newest if k not in known]
    for sid, sec in known.items():
        options = {o["id"]: o for o in sec.get("options") or []}
        defaults = [o["id"] for o in sec.get("options") or [] if o.get("default")]
        doc = newest.get(sid)
        if doc is None:
            choice = defaults if sec["kind"] == "many" else (defaults[0] if defaults else None)
            out[sid] = {"choice": choice, "text": _text((sec.get("text") or {}).get("value")), "note": "", "notes": {},
                        "default": True}
            continue
        choice = doc.get("choice")
        if sec["kind"] == "text":
            choice = None
        elif sec["kind"] == "many":
            if choice is None:
                choice = []
            if not (isinstance(choice, list) and all(isinstance(c, str) for c in choice)):
                bad.append(f"{sid}: the choice is not a list of options")
                choice = []
        elif isinstance(choice, list):
            if len(choice) > 1:
                bad.append(f"{sid}: one option is taken here, and {len(choice)} were given")
            choice = choice[0] if len(choice) == 1 else None
        for c in [choice] if isinstance(choice, str) else choice or []:
            if c not in options:
                bad.append(f"{sid}: {c!r} is not an option the page offered")
            elif options[c].get("disabled"):
                bad.append(f"{sid}: {options[c]['label']} cannot be chosen for this video ({options[c]['disabled']})")
        text = _text(doc.get("text"))
        note = _text(doc.get("note"))
        notes = doc.get("notes") if isinstance(doc.get("notes"), dict) else {}
        lines = {x["id"] for x in sec.get("lines") or []}
        kept = {}
        for k, v in notes.items():
            if k not in lines:
                bad.append(f"{sid}: a note on the line {k!r}, which the page did not show")
            elif _text(v):
                kept[k] = _text(v)
        if any(len(x) > MAX_TEXT for x in (text, note, *kept.values())):
            bad.append(f"{sid}: a text over {MAX_TEXT} characters")
        if sec["kind"] == "text" or sec.get("text"):
            pass
        elif text:
            bad.append(f"{sid}: a text where the page asked for an option")
        out[sid] = {"choice": choice, "text": text, "note": note, "notes": kept, "default": False}
    return out, done, bad


def read(run: RunFolder, name: str, *, file: Path | None = None, text: Path | None = None) -> dict:
    """The answers on the published `name` page (the module docstring): `{data, folder, data_file, from, source,
    answers, done}`. A Stop when there is nothing to read, or an answer the page did not offer."""
    if name not in PAGES:
        raise ValueError(f"{name!r} is not a page of choices ({', '.join(PAGES)}).")
    got = decided(run, name)
    data = got["data"]
    collection = COLLECTIONS[name]
    if text is not None:
        source = Path(text)
        docs = parse_chat(source.read_text(encoding="utf-8-sig"), data)
        how = "chat"
    else:
        slug = (state.load(run).pages.get(name) or {}).get("slug")
        if not slug and file is None:
            raise Stop(f"The {name} page's publish is not recorded (tm page published --page {name}), so it is unknown "
                       f"which artifact's choices to read. Record it and read them with an ArtifactData list, or write "
                       f"the user's answer from chat into a file and read it with --text; {AGAIN}.")
        source = Path(file) if file is not None else pages.saved_answer(run, name, collection)
        if source is None:
            raise Stop(f"No saved answer holds the choices of this page ({slug}): read them with one unfiltered "
                       f"ArtifactData list (the page's url, collection {collection}, query.limit 1000), then run this "
                       f"again; {AGAIN}.")
        docs = pages.db_docs(pages.whole_answer(run, name, source, collection), collection=collection)
        if not docs:
            raise Stop(f"Nothing was saved on the {name} page. Ask the user in chat; an answer in chat counts. Write it "
                       f"one line per section into a file in the run and read it with --text; {AGAIN}.")
        how = "page"
    found, done, bad = answers(data, docs)
    if bad:
        raise Stop(f"The {name} page's answer cannot be taken as it is: {'; '.join(bad[:5])}. Nothing was written. Ask "
                   f"the user to choose again on the latest page, or write their answer from chat and read it with "
                   f"--text; {AGAIN}.")
    try:
        rel = source.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        rel = str(source)
    return {"data": data, "folder": got["folder"], "data_file": got["data_file"], "from": rel, "source": how,
            "answers": found, "done": done}


def record(run: RunFolder, name: str, stem: str, body: dict, got: dict, *, stage: str = "03_wip") -> str:
    """Write `body` as the next `<stage>/<stem>_vNN.json` (with where it was read from), record it, and stop
    waiting on the page. Its path, run-relative."""
    out = run.next_version(stage, stem, "json")
    out.parent.mkdir(parents=True, exist_ok=True)
    full = {"page": name, "folder": got["folder"], "data": got["data_file"], "from": got["from"],
            "source": got["source"], "at": _now(), **body}
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(full, fh, ensure_ascii=False, indent=2)
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, stage.split("/")[0], DECISIONS_SOURCE, parent=got["from"],
                    params={"page": name, "folder": got["folder"], "source": got["source"]})
    if got["source"] == "page":
        pages.clear_await(run, name)
    return rel
