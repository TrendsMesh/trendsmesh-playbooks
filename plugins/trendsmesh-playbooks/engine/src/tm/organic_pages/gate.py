"""The check-in pages of organic video (F1 images, F2 takes) and its delivery page (G4): the port of the handoff's
`tools/pb3/gate_page.py`.

    build(run, data, *, page)   04_final/<page>_vNN/ (index.html, media/) from a page's data

`page` is one of `PAGES`: `gate_images`, `gate_video` and `delivery` (drift check 26), and the weekly pack's
`week_delivery` (`tm.organic_week`, gate `edit`; a script to film on it is shown as a link to its Markdown, the
port's one addition to the original's media). Each saves its choices in
its artifact's db collection, the original's `gate_images`, `gate_video` and `gate_edit` (`COLLECTIONS`): one document
per item, `{choice, action: accept|redo|drop, note, platforms, thumbnail, item, updated_at}`. The data is the handoff's
`gate.schema.json` (`schemas/pb3_gate.schema.json`, its kit `$ref` the plugin's `pb3_kit.schema.json`), made by
`tm.organic_gates`; its `plugin` block (not shown) ties each item to the run's files.

The port keeps the original's HTML byte for byte, up to the wording table (`organic_pages.WORDING`: "check-in", never
"gate"): the ExampleEdu walkthrough's delivery page, made by the reference tool, is rebuilt exactly
(fixtures/organic/edit_gate_golden/README.md). Its changes:
- the planned files are checked against the Artifact tool's limits (`page.over_limits`) before any is written, and a
  video shown on the page over 15 MB is refused: make its 720p preview first (`tm tool deliver preview`);
- media go into `media/` (the original's path; the empty `assets/` of `page.new_folder` stays), each under a Windows-safe
  name (`page.asset_name`); two different files of one name get `2_`, `3_` … before the later ones (the original's
  `put` kept the first and showed it twice);
- the page's script data cannot be ended by `</` or turned by `<!--`; nothing is built while people decide on
  the page (`page.Deciding`);
- the original's Polish table is the string table's `organic.gate.*` keys (`FRAGS`, `localize`), with the kit's
  pinned and first comment, which it left in English: the page is built in any language whose table has them
  (`organic_pages.page_lang` of the data's `lang`), else in English with a warning.
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tm import i18n, json_schema, kit as kits, manifest, organic_pages, page as pages, stepchecks
from tm.organic_pages import Frag
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGES = {"gate_images": "images", "gate_video": "video", "delivery": "edit",      # page -> its gate
         "week_delivery": "edit"}                                                 # the week's (tm.organic_week)
COLLECTIONS = {p: f"gate_{g}" for p, g in PAGES.items()}                          # page -> its db collection
SOURCE = "tm organic page"
DATA = "03_wip/gates"                     # the data each build was made from, <page>_vNN.json
SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "pb3_gate.schema.json"
KIT_SCHEMA = SCHEMA.with_name("pb3_kit.schema.json")
VIDEO_MAX_BYTES = 15_000_000              # a video shown on the page (the handoff: previews under ~15 MB; 10^6 bytes a MB)
VIDEO = (".mp4", ".mov", ".webm")
DOCUMENT = (".md",)                       # shown as a link, not an image (the plugin's, for a script to film)
READ_WITH = "tm organic decisions --run <run> --page {page}"

PLATFORMS = [("tiktok", "TikTok"), ("instagram", "Instagram Reels"), ("youtube", "YouTube Shorts"), ("facebook", "Facebook Reels")]


def _now() -> str:
    """When a page is built (its manifest row's `built_at`): a page's accept counts only after the latest pack check."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


CSS = """
:root{--bg:#F2F4F6;--surface:#FFFFFF;--ink:#13202A;--muted:#5A6977;--line:#D9DFE5;--accent:#B7791F;--accent-soft:#F6EBD9;
--ok:#2F7D4F;--ok-soft:#E3F2E8;--warn:#A86A00;--warn-soft:#FBF0D9;--bad:#B23A3A;--bad-soft:#F8E1E1;
--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:"Source Sans 3","Segoe UI",system-ui,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--body)}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 64px;display:grid;gap:24px}
.eyebrow{font:600 13px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(26px,4vw,38px)/1.1 var(--display);margin:0}h2{font:700 22px/1.2 var(--display);margin:0}
h3{font:600 14px/1.3 var(--body);margin:0;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.lede{color:var(--muted);max-width:72ch;margin:0}
.bar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.06)}
.sum{display:flex;flex-wrap:wrap;gap:6px 14px;font-variant-numeric:tabular-nums}.sum b{font:700 18px/1 var(--display)}
.btn{font:600 14px/1 var(--body);padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
.btn.primary{background:var(--ink);color:var(--surface);border-color:var(--ink)}.btn:hover{border-color:var(--accent)}
.btn:focus-visible,.seg input:focus-visible+span,textarea:focus-visible,.opt input:focus-visible+.card{outline:2px solid var(--accent);outline-offset:2px}
.status{font-size:13px;color:var(--muted)}
section.it{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;display:grid;gap:14px;scroll-margin-top:80px}
section.it.accept{border:2px solid var(--ok)}section.it.drop{opacity:.7}section.it.redo{border:2px solid var(--warn)}
.opts{display:flex;gap:12px;overflow-x:auto;padding-bottom:6px}
.opt{flex:0 0 auto;display:grid;gap:6px;cursor:pointer;position:relative}
.opt input{position:absolute;opacity:0}
.card{display:grid;gap:6px;padding:6px;border-radius:10px;border:2px solid var(--line);background:var(--bg);width:min(260px,72vw)}
.opt input:checked+.card{border-color:var(--ok);background:var(--ok-soft)}
.media{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:6px;background:#000;display:block}
.media.sq{aspect-ratio:1/1}
.cap{font-size:13px;line-height:1.35}.pick{font:700 11px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.ref .card{border-style:dashed;cursor:default}
.row{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.lbl{font:600 13px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);min-width:80px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--surface)}
.seg label{position:relative;cursor:pointer}.seg input{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
.seg span{display:block;padding:8px 13px;font:600 14px/1 var(--body);border-right:1px solid var(--line)}.seg label:last-child span{border-right:none}
.seg input:checked+span{background:var(--ink);color:var(--surface)}
.seg input[value="accept"]:checked+span{background:var(--ok);color:#fff}.seg input[value="redo"]:checked+span{background:var(--warn);color:#fff}.seg input[value="drop"]:checked+span{background:var(--bad);color:#fff}
.chk{display:inline-flex;gap:6px;align-items:center;font-size:14px;cursor:pointer}.chk input{width:16px;height:16px;accent-color:var(--ink)}
textarea{font:15px/1.4 var(--body);color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-height:42px;resize:vertical;width:100%}
.kit{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:10px}
.pf{border:1px solid var(--line);border-radius:10px;padding:12px;display:grid;gap:8px;align-content:start;background:var(--bg)}
.pf[hidden]{display:none}
.pf h4{margin:0;font:700 15px/1.2 var(--display);display:flex;justify-content:space-between;gap:8px;align-items:center}
.fld{display:grid;gap:3px}.fld .k{font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.fld pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.45 var(--body);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:8px}
.copy{font:600 12px/1 var(--body);padding:5px 8px;border-radius:6px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
.note{font-size:13px;color:var(--muted);margin:0}
.dl{font:600 13px/1 var(--body);padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer;justify-self:start}
.dl[hidden]{display:none}.dl:hover{border-color:var(--accent)}
@media (max-width:700px){.bar{position:static}}
"""

JS = r"""
(function(){
  const ITEMS = window.__ITEMS__, GATE = window.__GATE__, KEY = 'pb3-gate-' + window.__RUN_ID__ + '-' + GATE;
  const state = {}; let db = null;
  const st = document.getElementById('save-status'); const setStatus = t => { st.textContent = t; };
  ITEMS.forEach(it => { state[it.id] = {choice: it.pick, action: null, note: '', platforms: ['tiktok','instagram','youtube','facebook'], thumbnail: false}; });
  try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s) Object.keys(s).forEach(k => { if (state[k]) Object.assign(state[k], s[k]); }); } catch (e) {}
  function paint(){
    const n = {accept:0, redo:0, drop:0};
    ITEMS.forEach(it => {
      const s = state[it.id];
      document.querySelectorAll(`input[name="o-${it.id}"]`).forEach(r => r.checked = r.value === s.choice);
      ['accept','redo','drop'].forEach(v => { const el = document.getElementById(`a-${it.id}-${v}`); if (el) el.checked = s.action === v; });
      document.querySelectorAll(`#it-${it.id} input[data-pf]`).forEach(cb => { cb.checked = s.platforms.includes(cb.dataset.pf); const box = document.getElementById(`pf-${it.id}-${cb.dataset.pf}`); if (box) box.hidden = !cb.checked; });
      const th = document.getElementById(`th-${it.id}`); if (th) th.checked = !!s.thumbnail;
      const nt = document.getElementById(`n-${it.id}`); if (document.activeElement !== nt) nt.value = s.note || '';
      const sec = document.getElementById(`it-${it.id}`); ['accept','redo','drop'].forEach(v => sec.classList.toggle(v, s.action === v));
      if (s.action) n[s.action]++;
    });
    const open = ITEMS.length - n.accept - n.redo - n.drop;
    document.getElementById('sum').innerHTML = `<span><b>${n.accept}</b> accepted</span><span>${n.redo} redo · ${n.drop} dropped · ${open} open</span>`;
  }
  const pending = {};
  async function save(id){
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
    if (!db) { setStatus('Saved in this browser only'); return; }
    if (pending[id]) { pending[id].again = true; return; }
    pending[id] = {again:false}; setStatus('Saving…');
    try { do { pending[id].again = false; await db.doc(`gate_${GATE}/${id}`).set(Object.assign({}, state[id], {item: id, updated_at: new Date().toISOString()})); } while (pending[id].again);
      setStatus('Saved · Claude can read your choices'); } catch (e) { setStatus('Could not save to the page; kept in this browser'); }
    delete pending[id];
  }
  const timers = {}; const saveSoon = id => { clearTimeout(timers[id]); timers[id] = setTimeout(() => save(id), 600); };
  ITEMS.forEach(it => {
    const id = it.id;
    document.querySelectorAll(`input[name="o-${id}"]`).forEach(r => r.addEventListener('change', () => { state[id].choice = r.value; paint(); save(id); }));
    document.querySelectorAll(`input[name="a-${id}"]`).forEach(r => r.addEventListener('change', () => { state[id].action = r.value; paint(); save(id); }));
    document.querySelectorAll(`#it-${id} input[data-pf]`).forEach(cb => cb.addEventListener('change', () => { state[id].platforms = [...document.querySelectorAll(`#it-${id} input[data-pf]`)].filter(x => x.checked).map(x => x.dataset.pf); paint(); save(id); }));
    const th = document.getElementById(`th-${id}`); if (th) th.addEventListener('change', () => { state[id].thumbnail = th.checked; save(id); });
    document.getElementById(`n-${id}`).addEventListener('input', e => { state[id].note = e.target.value; saveSoon(id); });
  });
  document.querySelectorAll('button.copy').forEach(b => b.addEventListener('click', async () => {
    const t = document.getElementById(b.dataset.src).innerText;
    try { await navigator.clipboard.writeText(t); b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200); } catch (e) { b.textContent = 'Blocked'; }
  }));
  document.getElementById('all-accept').addEventListener('click', () => { ITEMS.forEach(it => { if (!state[it.id].action) state[it.id].action = 'accept'; }); paint(); ITEMS.forEach(it => save(it.id)); });
  (async () => {
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    let dls = null; try { dls = window.claude && window.claude.use ? await window.claude.use('downloads') : null; } catch (e) { dls = null; }
    if (!dls) return;
    document.querySelectorAll('button.dl').forEach(b => { b.hidden = false; b.addEventListener('click', async ev => {
      ev.preventDefault(); ev.stopPropagation();
      const t = b.textContent; b.textContent = '…';
      try { const blob = await (await fetch(b.dataset.href)).blob(); await dls.save({filename: b.dataset.name, data: blob}); b.textContent = '✓ Saved'; }
      catch (e) { b.textContent = (e && e.code === 'declined') ? t : '✕ Download failed'; }
      setTimeout(() => { b.textContent = t; }, 2500);
    }); });
  })();
  paint(); setStatus('Choices are kept in this browser until the page connects…');
  (async () => {
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    try { db = window.claude && window.claude.use ? await window.claude.use('db') : null; } catch (e) { db = null; }
    if (!db) { setStatus('Saved in this browser only'); return; }
    try { const snap = await db.collection(`gate_${GATE}`).get();
      snap.docs.forEach(d => { const v = d.data(); if (v && state[d.id]) Object.assign(state[d.id], {choice: v.choice ?? state[d.id].choice, action: v.action ?? null, note: v.note || '', platforms: Array.isArray(v.platforms) ? v.platforms : state[d.id].platforms, thumbnail: !!v.thumbnail}); });
      paint(); setStatus('Ready · your choices save automatically');
    } catch (e) { setStatus('Page storage not reachable; choices kept in this browser'); }
  })();
})();
"""


def media_tag(rel: str, alt: str, square: bool = False) -> str:
    cls = "media sq" if square else "media"
    if rel.lower().endswith(DOCUMENT):   # the plugin's: a script to film on the week's delivery page (no media to show)
        return f'<a class="{cls}" href="{esc(rel)}" target="_blank" rel="noopener">{esc(alt or Path(rel).name)}</a>'
    if rel.lower().endswith((".mp3", ".wav", ".m4a")):
        return f'<audio src="{esc(rel)}" controls preload="metadata" aria-label="{esc(alt)}" style="width:100%"></audio>'
    if rel.lower().endswith((".mp4", ".mov", ".webm")):
        return f'<video class="{cls}" src="{esc(rel)}" controls playsinline preload="metadata" aria-label="{esc(alt)}"></video>'
    return f'<img class="{cls}" src="{esc(rel)}" alt="{esc(alt)}" loading="lazy">'


def dl_button(put, d) -> str:
    if not d:
        return ""
    rel = put(d["src"])
    return f'<button class="dl" type="button" hidden data-href="{esc(rel)}" data-name="{esc(d.get("filename") or Path(rel).name)}">⬇ Download {esc(d.get("label",""))}</button>'


PASTE_LABELS = {"description": "Description to paste (with hashtags)"}       # TikTok, Instagram, Facebook
YOUTUBE_LABELS = {"title": "Title", "description": "Description (with hashtags)", "tags": "Tags"}
STEP_LABELS = {"cover": "Cover", "ai_label": "AI label", "sound": "Sound", "product": "Product mention"}
SEARCH_CHECK = ("Look it up in TikTok’s Creator Search Insights before you post: if people search for it in other "
                "words, use theirs in the first line.")
YOU_POST = "You post the video yourself: copy each text into the app as it is. The steps under it are what to set when you post."


def kit_html(it_id: str, kit: dict) -> str:
    """The posting kit on the page (issue #91): per platform the texts the user pastes as they are, each with its
    Copy (`kit.paste`: one description with its hashtags; YouTube's title, description and tags), then "At posting",
    the steps that are not pasted (`kit.steps`, and TikTok's search phrase to check), with no Copy."""
    out = [f'<div class="block" style="display:grid;gap:8px"><h3>Posting kit</h3><p class="note">{YOU_POST}</p>'
           '<div class="kit">']
    for key, name in PLATFORMS:
        pf = kit.get("platforms", {}).get(key)
        if not pf:
            continue
        rows = []
        for fk, v in kits.paste(key, pf):
            label = (YOUTUBE_LABELS if key == "youtube" else PASTE_LABELS)[fk]
            fid = f"k-{it_id}-{key}-{fk}"
            rows.append(f'<div class="fld"><span class="k">{label} <button class="copy" type="button" data-src="{fid}">Copy</button></span><pre id="{fid}">{esc(v)}</pre></div>')
        todo = [f"<li><b>{STEP_LABELS[fk]}:</b> {esc(v)}</li>" for fk, v in kits.steps(key, pf)]
        phrase = kit.get("search_phrase")
        if key == "tiktok" and isinstance(phrase, str) and phrase.strip():
            todo.append(f"<li><b>Search phrase:</b> “{esc(phrase.strip())}”. {SEARCH_CHECK}</li>")
        if todo:
            rows.append(f'<div class="fld"><span class="k">At posting</span><ul class="steps">{"".join(todo)}</ul></div>')
        out.append(f'<div class="pf" id="pf-{esc(it_id)}-{key}"><h4>{esc(name)}</h4>{"".join(rows)}</div>')
    out.append("</div></div>")
    return "".join(out)


def platform_row(iid: str) -> str:
    """The platform ticks (issue #91: which platforms get a posting kit, never where the plugin posts) and the
    YouTube-thumbnail tick, `iid` escaped."""
    return ('<div class="row"><span class="lbl">Posting kit for</span>' + "".join(f'<label class="chk"><input type="checkbox" data-pf="{k}" checked>{esc(n)}</label>' for k, n in PLATFORMS) +
            f'<label class="chk"><input type="checkbox" id="th-{iid}">Make a YouTube thumbnail</label>'
            f'<p class="note" style="flex-basis:100%">{organic_pages.POST_NOTE}</p></div>')


# The page's fixed fragments in another language (the original's Polish table, keyed, in its order), each the
# plugin's English (after `WORDING`) -> the same in the page language.
_G = "organic.gate."
FRAGS: list[Frag] = [
    Frag("§", _G + "eyebrow_images"), Frag("§", _G + "eyebrow_video"), Frag("§", _G + "eyebrow_edit"),
    Frag('aria-label="§"', "organic.your_decisions"),
    Frag(">§<", _G + "accept_rest"),
    Frag("§", _G + "note"),
    Frag("<span class=pick>§</span>", _G + "agent_pick"), Frag(">§<", _G + "accept"), Frag(">§<", _G + "redo"),
    Frag(">§<", _G + "drop"),
    Frag('<span class="lbl">§</span>', "organic.decision"), Frag('aria-label="§ ', "organic.decision_for"),
    Frag('<span class="lbl">§</span>', "organic.post_to"), Frag(">§<", _G + "make_thumbnail"),
    Frag("<h3>§</h3>", "organic.kit.posting_kit"), Frag(">§</button>", "organic.copy"),
    Frag("§", _G + "note_label"), Frag(">§ ", "organic.run_folder"),
    Frag('<p class="note">§</p>', "organic.kit.you_post"), Frag("§", "organic.post_note"),
    *(Frag('<span class="k">§ <button', f"organic.kit.{k}") for k in ("paste", "title", "description_hashtags", "tags")),
    Frag('<span class="k">§</span>', "organic.kit.at_posting"),
    *(Frag("<li><b>§:</b> ", f"organic.kit.{k}") for k in ("cover", "ai_label", "sound", "product", "search_phrase")),
    Frag("”. §</li>", "organic.kit.search_check"),
    Frag("`<span><b>${n.accept}</b> §0</span><span>${n.redo} §1 · ${n.drop} §2 · ${open} §3</span>`",
         (_G + "sum_accepted", _G + "sum_redo", _G + "sum_dropped", _G + "sum_open"), "tpl"),
    Frag("'§'", "organic.not_saved", "js"), Frag("'§'", "organic.saving", "js"), Frag("'§'", "organic.saved", "js"),
    Frag("'§'", _G + "save_failed", "js"), Frag("'§'", "organic.copied", "js"), Frag("'§'", "organic.copy", "js"),
    Frag("'§'", _G + "blocked", "js"),
    Frag("'§'", "organic.connecting", "js"), Frag("'§'", "organic.ready", "js"),
    Frag("'§'", "organic.storage_unreachable", "js"),
    Frag(">⬇ § ", _G + "download"), Frag("'§'", "organic.saved_check", "js"),
    Frag("'§'", "organic.download_failed", "js"),
]


def localize(page: str, lang) -> str:
    """The page in `lang` (`organic_pages.localize`)."""
    return organic_pages.localize(page, lang, FRAGS)


def _script(value) -> str:
    """JSON for the page's script (the original's `json.dumps`): `</` cannot end it and `<!--` cannot change how it is parsed."""
    return json.dumps(value).replace("</", "<\\/").replace("<!--", "<\\u0021--")


def render(data: dict, put) -> str:
    """The original's `render`, with `put(src) -> "media/<name>"` given (the files are copied by `build`)."""
    gate = data["gate"]
    out = [f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(data['title'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header style="display:grid;gap:8px"><div class="eyebrow">Organic AI video · gate: {esc(gate)} · {esc(data['date'])}</div><h1>{esc(data['title'])}</h1><p class="lede">{esc(data.get('lede',''))}</p></header>
<div class="bar" role="region" aria-label="Your decisions"><div class="sum" id="sum"></div>
<div class="row"><button class="btn primary" id="all-accept" type="button">Accept the rest</button><span class="status" id="save-status" aria-live="polite"></span></div>
<p class="note" style="flex-basis:100%">Pick an option where there is a choice, then Accept, Redo (write what to change) or Drop. Choices save as you click; write “ready” to Claude in the chat when done.</p></div>"""]
    meta = []
    for it in data["items"]:
        iid = esc(it["id"])
        pick = next((o["id"] for o in it.get("options", []) if o.get("pick")), (it.get("options") or [{"id": "0"}])[0]["id"])
        meta.append({"id": it["id"], "pick": pick})
        opts = []
        for o in it.get("options", []):
            rel = put(o["src"])
            badge = "<span class=pick>Agent’s pick</span>" if o.get("pick") else ""
            opts.append(f'<label class="opt"><input type="radio" name="o-{iid}" value="{esc(o["id"])}"><span class="card">{media_tag(rel, o.get("caption",""), o.get("square", False))}'
                        f'{badge}<span class="cap">{esc(o.get("caption",""))}</span>{dl_button(put, o.get("download"))}</span></label>')
        refs = "".join(f'<div class="opt ref"><span class="card">{media_tag(put(r["src"]), r.get("caption",""), r.get("square", False))}<span class="cap">{esc(r.get("caption",""))}</span>{dl_button(put, r.get("download"))}</span></div>' for r in it.get("refs", []))
        acts = "".join(f'<label><input type="radio" name="a-{iid}" id="a-{iid}-{v}" value="{v}"><span>{t}</span></label>' for v, t in (("accept", "Accept"), ("redo", "Redo"), ("drop", "Drop")))
        kit = it.get("kit")
        pf_row = ""
        if kit:
            pf_row = platform_row(iid)
        question = f'<p class="lede">{esc(it["question"])}</p>' if it.get('question') else ''
        kit_block = kit_html(it['id'], kit) if kit else ''
        out.append(f"""<section class="it" id="it-{iid}"><div style="display:grid;gap:4px"><div class="eyebrow">{esc(it.get('proposal',''))}</div><h2>{esc(it['label'])}</h2>{question}</div>
<div class="opts" role="radiogroup" aria-label="{esc(it['label'])}">{''.join(opts)}{refs}</div>
<div class="row"><span class="lbl">Decision</span><span class="seg" role="radiogroup" aria-label="Decision for {iid}">{acts}</span></div>
{pf_row}{kit_block}
<div style="display:grid;gap:4px"><label for="n-{iid}" style="font-size:14px">Note for Claude (what to change on Redo)</label><textarea id="n-{iid}" rows="1"></textarea></div></section>""")
    out.append(f"""<footer class="note">Run folder: {esc(data['run'])}</footer></div>
<script>window.__ITEMS__ = {_script(meta)}; window.__GATE__ = {_script(gate)}; window.__RUN_ID__ = {_script(Path(data['run']).name)};</script>
<script>{JS}</script></body></html>""")
    return "".join(out)


def page_html(data: dict, put) -> tuple[str, i18n.PageLang]:
    """The page as built, and the language it is built in (`organic_pages.page_lang` of its data)."""
    built = organic_pages.page_lang(data)
    return localize(render(data, put), built.lang), built


# --- building it in the run ------------------------------------------------------------------------

def _schema() -> dict:
    """The handoff's gate schema, its kit `$ref` replaced by the plugin's kit schema (json_schema takes local refs only)."""
    schema = json_schema.load(SCHEMA)
    kit = json_schema.load(KIT_SCHEMA)
    item = schema["properties"]["items"]["items"]["properties"]
    item["kit"] = kit
    return schema


def check_page(page: str) -> str:
    if page not in PAGES:
        raise ValueError(f"{page!r} is not a check-in page: use one of {', '.join(PAGES)}.")
    return page


def _sources(data: dict) -> list[str]:
    """Every src the page shows or offers for download, in page order."""
    out = []
    for it in data["items"]:
        for entry in [*it.get("options", []), *it.get("refs", [])]:
            out.append(entry["src"])
            if entry.get("download"):
                out.append(entry["download"]["src"])
    return out


def _shown_videos(data: dict) -> list[str]:
    """The srcs shown on the page as a video (options and refs; a download is not played on the page)."""
    return [e["src"] for it in data["items"] for e in [*it.get("options", []), *it.get("refs", [])]
            if e["src"].lower().endswith(VIDEO)]


def _with_previews(run: RunFolder, data: dict) -> list[str]:
    """Each video the page shows over `VIDEO_MAX_BYTES` is shown as its 720p preview (`showcase/<stem>_720p.mp4`),
    made here when it is not made yet, as `tm tool deliver preview` makes it (free, local; issue #90). The data's
    `src` is changed to the preview; what an option picks (its plugin entry's file) stays the video. Returns the
    previews made. A preview that is itself over the limit is left for the size check."""
    from tm.tools import deliver   # ffmpeg is reached only for a video over the limit

    made = []
    for it in data["items"]:
        for entry in [*it.get("options", []), *it.get("refs", [])]:
            src = entry["src"]
            path = _resolve(run, src)
            if (not src.lower().endswith(VIDEO) or not path.is_file() or path.stat().st_size <= VIDEO_MAX_BYTES
                    or path.stem.endswith("_720p")):
                continue
            preview = deliver.preview_of(run, path)
            if not preview.is_file():
                deliver.make_preview(run, path)
                made.append(preview.relative_to(run.path).as_posix())
            entry["src"] = preview.relative_to(run.path).as_posix()
    return made


def _resolve(run: RunFolder, src: str) -> Path:
    """A src: run-relative, or an absolute path (a packshot in the library)."""
    p = Path(src)
    return p if p.is_absolute() else run.path / src


def _names(run: RunFolder, data: dict) -> dict[str, tuple[str, Path]]:
    """src -> (its name in media/, the file): `page.asset_name` of the file's name; another file of a name already
    taken gets `2_`, `3_` … before it. Names are compared case-folded (Mug.png and mug.png are one name on a
    case-blind disk, so neither is copied over the other). Stop for a file that is not there."""
    out: dict[str, tuple[str, Path]] = {}
    taken: dict[str, Path] = {}   # casefolded name -> its file
    for src in _sources(data):
        if src in out:
            continue
        path = _resolve(run, src)
        if not path.is_file():
            raise Stop(f"{src} is not there, so the page cannot show it. Make it again, or build the page's data again "
                       f"(tm organic page …); {AGAIN}.")
        name, n = pages.asset_name(path.name), 1
        while name.casefold() in taken and taken[name.casefold()].resolve() != path.resolve():
            n += 1
            name = f"{n}_{pages.asset_name(path.name)}"
        taken[name.casefold()] = path
        out[src] = (name, path)
    return out


def build(run: RunFolder, data: dict, *, page: str) -> dict:
    """Build `page` from its data into a new `04_final/<page>_vNN/` (index.html, media/), and keep the data it was
    built from in `03_wip/gates/<page>_vNN.json`. Nothing is written while people decide on the page
    (`page.Deciding`), for data that is not in the handoff's shape, for a video shown over 15 MB or for files over
    the Artifact tool's limits (each a Stop). Returns {folder, files, data, lang, language_warning}: the language it is
    built in, and why when that is English and not the data's `lang` (`organic_pages.page_lang`)."""
    check_page(page)
    if pages.awaiting(run, page) is not None:
        raise pages.Deciding(page, read=READ_WITH.format(page=page))
    problems = json_schema.problems(data, _schema(), name="page")
    if not problems and data["gate"] != PAGES[page]:
        problems = [f"page.gate is {data['gate']!r}, and the {page} page shows the gate {PAGES[page]!r}"]
    if problems:
        raise Stop(f"The {page} page's data is not in the page's shape ({'; '.join(problems[:5])}). Build it again "
                   f"with tm organic page; {AGAIN}.")
    previews = _with_previews(run, data)
    names = _names(run, data)
    big = [f"{src} ({names[src][1].stat().st_size / 1e6:.1f} MB)" for src in dict.fromkeys(_shown_videos(data))
           if names[src][1].stat().st_size > VIDEO_MAX_BYTES]
    if big:
        raise Stop(f"{', '.join(big)} {'is' if len(big) == 1 else 'are'} over 15 MB even as a 720p preview, too big "
                   "to play on the page. Show a shorter cut of it, or leave it out of the page and give its path in "
                   f"chat. Nothing was written; {AGAIN}.")
    text, built = page_html(data, lambda src: f"media/{names[src][0]}")
    lang = built.lang
    planned = {"index.html": len(text.encode("utf-8"))} | {f"media/{n}": p.stat().st_size for n, p in names.values()}
    over = pages.over_limits(planned)
    if over:
        raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Show fewer "
                   f"options or smaller previews, then build again; {AGAIN}.")
    out = pages.new_folder(run, page)
    (out / "media").mkdir()
    for name, path in dict(names.values()).items():
        shutil.copyfile(path, out / "media" / name)
    with open(out / "index.html", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    kept = run.next_version(DATA, page, "json")
    kept.parent.mkdir(parents=True, exist_ok=True)
    with open(kept, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    out_rel, kept_rel = out.relative_to(run.path).as_posix(), kept.relative_to(run.path).as_posix()
    final = (data.get("plugin") or {}).get("final")
    params = {"page": page, "data_sha256": stepchecks.sha256(kept), "lang": lang, "built_at": _now()}
    if isinstance(final, str) and (run.path / final).is_file():
        params |= {"final": final, "final_sha256": stepchecks.sha256(run.path / final)}
    manifest.record(run, out_rel, pages.FINAL, f"{SOURCE} {page}", parent=kept_rel, params=params)
    return {"folder": out_rel, "files": pages.files(out), "data": kept_rel, "lang": lang,
            "language_warning": built.warning, "previews": previews}
