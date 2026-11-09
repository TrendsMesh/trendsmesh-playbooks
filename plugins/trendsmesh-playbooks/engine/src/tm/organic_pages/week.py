"""The week plan page (organic video I2): the port of the handoff's `tools/pb3/weekly_page.py`, and the decisions taken
on it.

    build(run, file=None)                       04_final/week_vNN/index.html from the checked week plan
    take_decisions(run, *, file, text)          03_wip/decisions_week_vNN.json from the page's db or chat
    built_gap(run)                              the step check `week_page_built`

The port keeps the original's HTML byte for byte, up to the wording table (`organic_pages.WORDING`): the ExampleEdu walkthrough's
week, made by the reference tool under Python 3.12, is rebuilt exactly (fixtures/organic/README.md, week_golden.html). Its
changes:
- `lang` is required (the reference tool defaults to Polish): the week check (`organic_week.check`) asks for the run's
  page language, and `render` refuses a week without en or pl;
- the planned file is checked against publish_files' limits (`page.over_limits`) before it is written, and nothing
  is built while people decide on the page (`page.Deciding`);
- no backslash inside an f-string expression (Python 3.11), and the page's script data cannot be ended by `</` or
  turned by `<!--` (the original's own escape covered only the ideas, and only `</`);
- the original's `render` changed the week it was given (each slot's `day` and `slot`); the port works on a copy.

Decisions. The page saves one document per slot in its db collection `week` (`week/<slot>`, the slot being the original's
day key, `pon` … `niedz`: `{idea, output: video|script, decision: ok|skip, note, slot, updated_at}`) and one document
`week/_week` (`{approved, total, updated_at}`). `take_decisions` reads the newest saved `db_list`, whole and read
after the page was published and awaited (`page.saved_answer`, `page.whole_answer`, `page.db_docs`), or the user's
words in chat (`--text`, one line per day: `<day>: ok|skip[; idea: <id>][; output: video|script][; note: <their
words>]`, and `approved: yes|no`), into

    03_wip/decisions_week_vNN.json = {"page": "week", "week": <the checked week file the page was built from>,
        "folder", "from", "slug", "at", "source": page|chat, "decisions": {day: row}, "read": {day: document},
        "carried": [day, ...], "approved", "total", "page_total"}

each row as `organic_week.choices` makes it (keyed by the English day, `mon` … `sun`), `total` the engine's own sum
(`organic_week.total`), `page_total` what the page said. A row whose document equals the one the latest decisions
file of another page build read is `carried` (`page.mark_carried`); a row from chat never is.
"""

from __future__ import annotations

import copy
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tm import manifest, organic_week, page, state, stepchecks
from tm.organic_pages import worded
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "week"
COLLECTION = "week"
WEEK_DOC = "_week"
SOURCE = "tm organic page week"
DECISIONS_SOURCE = "tm organic decisions"
READ_WITH = f"tm organic decisions --run <run> --page {PAGE}"
EMPTY = ("Nothing was saved on the week page. Ask the user in chat; a decision written in chat counts. Write their "
         "answer one line per day (`<day>: ok|skip; idea: <id>; output: video|script; note: <their words>`, and "
         f"`approved: yes`), read it with --text, then go on; {AGAIN}.")

DAY_KEYS = ["pon", "wt", "śr", "czw", "pt", "sob", "niedz"]  # slot keys in week.json (also accepted: mon..sun)
DAY_EN = {"mon": "pon", "tue": "wt", "wed": "śr", "thu": "czw", "fri": "pt", "sat": "sob", "sun": "niedz"}
T = {
    "pl": dict(days=["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"], risk={"low": "niskie", "medium": "średnie", "high": "wysokie"},
               prod="Produkcja: ", trend="Trend: ", risk_l="Ryzyko: ", of="z", sum_v="wideo AI", sum_s="skrypty", sum_k="pominięte",
               approve="Zatwierdź tydzień", approved="✓ Tydzień zatwierdzony", local="Zapisane tylko w tej przeglądarce", saved="Zapisane · Claude widzi Twoje wybory",
               save_err="Nie udało się zapisać na stronie; zostaje w tej przeglądarce", wait="Wybory zostają w tej przeglądarce, dopóki strona się nie połączy…",
               ready="Gotowe · wybory zapisują się automatycznie", no_db="Brak dostępu do zapisu strony; wybory zostają w tej przeglądarce",
               reserve=" (rezerwa)", video="Wideo AI", script="Skrypt", ok="OK", skip="Pomiń", decision="Decyzja", swap="Zamień pomysł",
               note="Uwaga do tego filmu (opcjonalnie)", note_l="Uwaga", empty="bez publikacji",
               res_cost="Koszt: wideo ${v} · skrypt ${s}. Wybierz go w „Zamień pomysł” przy dowolnym dniu.",
               eyebrow="Organiczne wideo AI · pakiet tygodniowy · ", meta="{n} filmów w tygodniu · publikacja na: {pf} · produkcja: {rh} · budżet ${b} na cały tydzień.",
               bar="Budżet i zatwierdzenie", over="Plan przekracza budżet: zmień jakiś film na skrypt, zamień go na tańszy pomysł albo pomiń.",
               help="Przy każdym dniu wybierz „Wideo AI” albo „Skrypt” (nagrasz sam, $0), zamień pomysł na inny z listy albo go pomiń. „Zatwierdź tydzień” uruchamia produkcję całego tygodnia; potem dostaniesz jedną stronę z gotowymi filmami, skryptami i zestawami do publikacji.",
               cal="Kalendarz tygodnia", res="Pomysły w rezerwie", run="Folder runu: "),
    "en": dict(days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], risk={"low": "low", "medium": "medium", "high": "high"},
               prod="Production: ", trend="Trend: ", risk_l="Risk: ", of="of", sum_v="AI video", sum_s="scripts", sum_k="skipped",
               approve="Approve the week", approved="✓ Week approved", local="Saved in this browser only", saved="Saved · Claude sees your choices",
               save_err="Could not save on the page; kept in this browser", wait="Choices stay in this browser until the page connects…",
               ready="Ready · choices save automatically", no_db="No access to page storage; choices stay in this browser",
               reserve=" (reserve)", video="AI video", script="Script", ok="OK", skip="Skip", decision="Decision", swap="Swap idea",
               note="Note for this video (optional)", note_l="Note", empty="no post",
               res_cost="Cost: video ${v} · script ${s}. Pick it in “Swap idea” on any day.",
               eyebrow="Organic AI video · weekly pack · ", meta="{n} videos this week · posting to: {pf} · production: {rh} · budget ${b} for the whole week.",
               bar="Budget and approval", over="The plan is over budget: switch a video to a script, swap it for a cheaper idea, or skip it.",
               help="For each day pick “AI video” or “Script” (you film it, $0), swap the idea for another one from the list, or skip it. “Approve the week” starts production of the whole week; then you get one page with the finished videos, scripts and posting kits.",
               cal="Week calendar", res="Reserve ideas", run="Run folder: "),
}
PF = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube", "facebook": "Facebook"}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _script(value) -> str:
    """JSON for the page's script (the original's `json.dumps(..., ensure_ascii=False)`): `</` cannot end it and `<!--` cannot
    change how it is parsed."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\u0021--")


CSS = """:root{--bg:#F2F4F6;--surface:#fff;--ink:#13202A;--muted:#5A6977;--line:#D9DFE5;--accent:#B7791F;--accent-soft:#F6EBD9;--ok:#2F7D4F;--ok-soft:#E3F2E8;--warn:#A86A00;--warn-soft:#FBF0D9;--bad:#B23A3A;--bad-soft:#F8E1E1;
--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:"Source Sans 3","Segoe UI",system-ui,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;--ok:#6CC08F;--ok-soft:#173225;--warn:#E5B45A;--warn-soft:#33281A;--bad:#E58383;--bad-soft:#3A1F22;color-scheme:dark}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--body)}
.wrap{max-width:1240px;margin:0 auto;padding:28px 16px 64px;display:grid;gap:20px}
.eyebrow{font:600 13px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(26px,4vw,38px)/1.1 var(--display);margin:0}h2{font:700 20px/1.2 var(--display);margin:0}
.meta{color:var(--muted);margin:0}
.bar{position:sticky;top:0;z-index:5;display:grid;gap:8px;padding:12px 16px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.06)}
.brow{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;justify-content:space-between}
.meter{height:10px;border-radius:999px;background:var(--line);overflow:hidden}.meter>i{display:block;height:100%;background:var(--ok);width:0;transition:width .2s}
.meter.over>i{background:var(--bad)}
.sum{font-variant-numeric:tabular-nums}.sum b{font:700 18px/1 var(--display)}
.btn{font:600 14px/1 var(--body);padding:10px 14px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
.btn.primary{background:var(--ink);color:var(--surface);border-color:var(--ink)}.btn:disabled{opacity:.45;cursor:not-allowed}
.btn:focus-visible,select:focus-visible,textarea:focus-visible,.seg input:focus-visible+span{outline:2px solid var(--accent);outline-offset:2px}
.status{font-size:13px;color:var(--muted)}
.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px}
@media (max-width:1100px){.cal{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:640px){.cal{grid-template-columns:1fr}}
.day{display:grid;gap:8px;align-content:start;min-width:0}
.dh{display:flex;justify-content:space-between;align-items:baseline;font:700 14px/1.2 var(--display)}.dh span{font:600 12px/1 var(--body);color:var(--muted)}
.empty{border:1px dashed var(--line);border-radius:12px;padding:14px;color:var(--muted);font-size:14px;text-align:center}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;gap:8px;min-width:0}
.card.skip{opacity:.55}.card.ok{border:2px solid var(--ok)}
.t{font:700 16px/1.25 var(--display)}.fmt{font-size:13px;color:var(--accent);font-weight:600}
.why{font-size:14px;margin:0}.small{font-size:13px;color:var(--muted);margin:0;overflow-wrap:anywhere}
.chips{display:flex;flex-wrap:wrap;gap:5px}.chip{font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.chip.risk-high{background:var(--bad-soft);color:var(--bad);border:none}.chip.risk-medium{background:var(--warn-soft);color:var(--warn);border:none}.chip.risk-low{background:var(--ok-soft);color:var(--ok);border:none}
.cost{font:700 15px/1 var(--display);font-variant-numeric:tabular-nums}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--surface);flex-wrap:wrap}
.seg label{position:relative;cursor:pointer}.seg input{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
.seg span{display:block;padding:7px 10px;font:600 13px/1 var(--body);border-right:1px solid var(--line)}.seg label:last-child span{border-right:none}
.seg input:checked+span{background:var(--ink);color:var(--surface)}
.seg input[value="ok"]:checked+span{background:var(--ok);color:#fff}.seg input[value="skip"]:checked+span{background:var(--bad);color:#fff}
select,textarea{font:14px/1.4 var(--body);color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 8px;width:100%}
textarea{min-height:36px;resize:vertical}
a{color:inherit}.res{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr));gap:10px}
@media (max-width:640px){.bar{position:static}}"""

JS = r"""
(function(){
  const W = window.__WEEK__; const L = window.__L__; const IDEAS = {}; W.slots.concat(W.reserves).forEach(x => IDEAS[x.id] = x);
  const state = {}; let approved = false; let db = null;
  const st = document.getElementById('st'); const set = t => st.textContent = t;
  W.slots.forEach(s => { state[s.slot] = {idea: s.id, output: s.output || 'video', decision: 'ok', note: ''}; });
  const cost = s => { const i = IDEAS[s.idea]; return s.decision === 'skip' ? 0 : (s.output === 'script' ? i.cost_script : i.cost_video); };
  function paintCard(slot){
    const s = state[slot]; const i = IDEAS[s.idea]; const el = document.getElementById('c-' + slot);
    el.querySelector('.t').textContent = i.title; el.querySelector('.fmt').textContent = i.format; el.querySelector('.why').textContent = i.why;
    el.querySelector('.prod').textContent = L.prod + i.production;
    const ev = el.querySelector('.ev'); ev.innerHTML = '';
    if (i.evidence) { const a = document.createElement('a'); a.href = i.evidence; a.target = '_blank'; a.rel = 'noopener'; a.textContent = L.trend + i.trend + ' ↗'; ev.appendChild(a); } else { ev.textContent = L.trend + i.trend; }
    const r = el.querySelector('.risk'); r.className = 'chip risk risk-' + i.risk; r.textContent = L.risk_l + L.risk[i.risk];
    el.querySelector('.cost').textContent = '$' + cost(s).toFixed(2);
    el.querySelectorAll('input[name="o-' + slot + '"]').forEach(x => x.checked = x.value === s.output);
    el.querySelectorAll('input[name="d-' + slot + '"]').forEach(x => x.checked = x.value === s.decision);
    el.querySelector('select').value = s.idea;
    el.classList.toggle('skip', s.decision === 'skip'); el.classList.toggle('ok', s.decision === 'ok' && approved);
    const n = el.querySelector('textarea'); if (document.activeElement !== n) n.value = s.note || '';
  }
  function paint(){
    W.slots.forEach(s => paintCard(s.slot));
    let total = 0, nv = 0, ns = 0, nk = 0; Object.values(state).forEach(s => { total += cost(s); if (s.decision === 'skip') nk++; else if (s.output === 'script') ns++; else nv++; });
    const m = document.getElementById('meter'); m.classList.toggle('over', total > W.budget); m.firstElementChild.style.width = Math.min(100, total / W.budget * 100) + '%';
    document.getElementById('sum').innerHTML = `<b>$${total.toFixed(2)}</b> ${L.of} $${W.budget.toFixed(2)} · ${L.sum_v}: ${nv} · ${L.sum_s}: ${ns} · ${L.sum_k}: ${nk}`;
    const b = document.getElementById('approve'); b.disabled = total > W.budget; b.textContent = approved ? L.approved : L.approve;
    document.getElementById('over').hidden = total <= W.budget;
    document.querySelectorAll('select option').forEach(o => { const used = Object.entries(state).some(([k, s]) => s.idea === o.value && o.parentElement.dataset.slot !== k); o.disabled = used; });
  }
  async function save(slot){
    try { localStorage.setItem('pb3-week-' + W.week, JSON.stringify({state, approved})); } catch (e) {}
    if (!db) { set(L.local); return; }
    try { if (slot) await db.doc('week/' + slot).set(Object.assign({}, state[slot], {slot, updated_at: new Date().toISOString()}));
          await db.doc('week/_week').set({approved, total: Object.values(state).reduce((a, s) => a + cost(s), 0), updated_at: new Date().toISOString()});
          set(L.saved); } catch (e) { set(L.save_err); }
  }
  W.slots.forEach(s => {
    const slot = s.slot; const el = document.getElementById('c-' + slot);
    el.querySelectorAll('input[name="o-' + slot + '"]').forEach(x => x.addEventListener('change', () => { state[slot].output = x.value; approved = false; paint(); save(slot); }));
    el.querySelectorAll('input[name="d-' + slot + '"]').forEach(x => x.addEventListener('change', () => { state[slot].decision = x.value; approved = false; paint(); save(slot); }));
    el.querySelector('select').addEventListener('change', e => { state[slot].idea = e.target.value; approved = false; paint(); save(slot); });
    let t; el.querySelector('textarea').addEventListener('input', e => { state[slot].note = e.target.value; clearTimeout(t); t = setTimeout(() => save(slot), 600); });
  });
  document.getElementById('approve').addEventListener('click', () => { approved = true; paint(); save(null); });
  try { const s = JSON.parse(localStorage.getItem('pb3-week-' + W.week) || 'null'); if (s) { Object.assign(state, s.state || {}); approved = !!s.approved; } } catch (e) {}
  paint(); set(L.wait);
  (async () => {
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    try { db = window.claude && window.claude.use ? await window.claude.use('db') : null; } catch (e) { db = null; }
    if (!db) { set(L.local); return; }
    try { const snap = await db.collection('week').get();
      snap.docs.forEach(d => { const v = d.data(); if (d.id === '_week') approved = !!v.approved; else if (state[d.id]) Object.assign(state[d.id], {idea: v.idea || state[d.id].idea, output: v.output || state[d.id].output, decision: v.decision || state[d.id].decision, note: v.note || ''}); });
      paint(); set(L.ready); } catch (e) { set(L.no_db); }
  })();
})();
"""


def card(slot: str, s: dict, all_ideas: list, L: dict) -> str:
    opts = "".join(f'<option value="{esc(i["id"])}">{esc(i["title"])}{L["reserve"] if i["id"].startswith("r") else ""}</option>' for i in all_ideas)
    out = "".join(f'<label><input type="radio" name="o-{slot}" value="{v}"><span>{t}</span></label>' for v, t in (("video", L["video"]), ("script", L["script"])))
    dec = "".join(f'<label><input type="radio" name="d-{slot}" value="{v}"><span>{t}</span></label>' for v, t in (("ok", L["ok"]), ("skip", L["skip"])))
    return f"""<div class="card" id="c-{slot}"><div class="fmt"></div><div class="t"></div><p class="why"></p>
<div class="chips"><span class="chip risk"></span><span class="chip">{esc(s['time'])}</span></div>
<p class="small prod"></p><p class="small ev"></p>
<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"><span class="seg" role="radiogroup" aria-label="Output">{out}</span><span class="cost"></span></div>
<span class="seg" role="radiogroup" aria-label="{L['decision']}">{dec}</span>
<label class="small">{L['swap']}<select data-slot="{slot}" aria-label="{L['swap']}">{opts}</select></label>
<textarea rows="1" placeholder="{L['note']}" aria-label="{L['note_l']}"></textarea></div>"""


def render(week: dict) -> str:
    """The original's `render`, on a copy of the week, with `lang` required (en or pl): a ValueError without it."""
    w = copy.deepcopy(week)
    if w.get("lang") not in T:
        raise ValueError(f"The week page's language is en or pl, and the week's lang is {w.get('lang')!r}.")
    L = T[w["lang"]]
    for s in w["slots"]:
        s["day"] = DAY_EN.get(s["day"], s["day"])
    by_day = {s["day"]: s for s in w["slots"]}
    ideas = w["slots"] + w["reserves"]
    for s in w["slots"]:
        s["slot"] = s["day"]
    cal = []
    for key, name in zip(DAY_KEYS, L["days"]):
        s = by_day.get(key)
        body = card(key, s, ideas, L) if s else f'<div class="empty">{L["empty"]}</div>'
        date = s["date"] if s else ""
        cal.append(f'<div class="day"><div class="dh">{name}<span>{esc(date)}</span></div>{body}</div>')
    res = "".join(f'<div class="card"><div class="fmt">{esc(r["format"])}</div><div class="t">{esc(r["title"])}</div><p class="why">{esc(r["why"])}</p>'
                  f'<p class="small">{esc(L["res_cost"].replace("{v}", format(r["cost_video"], ".2f")).replace("{s}", format(r["cost_script"], ".2f")))}</p></div>' for r in w["reserves"])
    ideas_js = {i["id"]: {k: i[k] for k in ("title", "format", "why", "trend", "evidence", "cost_video", "cost_script", "production", "risk")} for i in ideas}
    pfs = " · ".join(PF[p] for p in w["platforms"])
    labels = _script({k: L[k] for k in L if k != "days"})
    week_js = _script(dict(week=w['week'], budget=w['budget'], slots=[dict(slot=s['slot'], id=s['id'], output=s.get('output', 'video')) for s in w['slots']], reserves=[]))
    ideas_text = _script(ideas_js)
    return f"""<!DOCTYPE html><html lang="{esc(w['lang'])}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(w['title'])}</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header style="display:grid;gap:8px"><div class="eyebrow">{L['eyebrow']}{esc(w['channel'])}</div><h1>{esc(w['title'])}</h1>
<p class="meta">{esc(L['meta'].format(n=len(w['slots']), pf=pfs, rh=w['rhythm'], b=format(w['budget'], '.2f')))}</p>
<p class="meta" style="font-size:14px">{esc(w.get('note',''))}</p></header>
<div class="bar" role="region" aria-label="{L['bar']}"><div class="brow"><span class="sum" id="sum"></span><span style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button class="btn primary" id="approve" type="button">{L['approve']}</button><span class="status" id="st" aria-live="polite"></span></span></div>
<div class="meter" id="meter"><i></i></div><p class="small" id="over" hidden>{L['over']}</p>
<p class="small">{L['help']}</p></div>
<section style="display:grid;gap:10px"><h2>{L['cal']}</h2><div class="cal">{''.join(cal)}</div></section>
<section style="display:grid;gap:10px"><h2>{L['res']}</h2><div class="res">{res}</div></section>
<p class="small">{L['run']}{esc(w['run'])}</p></div>
<script>window.__L__ = {labels};
window.__WEEK__ = {week_js};
(function(){{ const I = {ideas_text}; window.__WEEK__.slots.forEach(s => Object.assign(s, I[s.id], {{id: s.id}})); window.__WEEK__.reserves = Object.keys(I).filter(k => !window.__WEEK__.slots.some(s => s.id === k)).map(k => Object.assign({{id: k}}, I[k])); }})();</script>
<script>{JS}</script></body></html>"""


# --- building it in the run ------------------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{path} is not inside the run folder {run.path}.") from None


def build(run: RunFolder, file: Path | None = None) -> dict:
    """Build the page from the checked week plan into a new `04_final/week_vNN/index.html`. Nothing is written while
    people decide on the page (`page.Deciding`), before the week is checked, or when the page would be over
    publish_files' limits (each a Stop)."""
    if page.awaiting(run, PAGE) is not None:
        raise page.Deciding(PAGE, read=READ_WITH)
    path, rel, week = organic_week.checked_week(run)
    if file is not None and _rel(run, file).casefold() != rel.casefold():
        raise Stop(f"{_rel(run, file)} is not the checked week plan ({rel}): check it first (tm organic week check), "
                   f"then build the page from it; {AGAIN}.")
    try:
        text = worded(render(week), week["lang"])
    except (KeyError, ValueError, TypeError) as exc:   # the file's shape
        raise Stop(f"{rel} is not in the page's shape ({type(exc).__name__}: {exc}); check it again (tm organic week "
                   f"check); {AGAIN}.") from None
    over = page.over_limits({"index.html": len(text.encode("utf-8"))})
    if over:
        raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Shorten the "
                   f"week's texts, check it again and build again; {AGAIN}.")
    out = page.new_folder(run, PAGE)
    with open(out / "index.html", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, page.FINAL, SOURCE, parent=rel,
                    params={"week_sha256": stepchecks.sha256(path), "lang": week["lang"]})
    return {"folder": out_rel, "files": page.files(out), "week": rel, "lang": week["lang"]}


def built_gap(run: RunFolder) -> str | None:
    """The `week_page_built` step check: I2's page is built from the latest checked week plan, unchanged since. Reads
    only."""
    checked = (state.load(run).checked.get(organic_week.KEY) or {}).get("file")
    if not checked or organic_week.checked_gap(run) is not None:
        return "the week plan is checked (tm organic week check) and its page is built from it (tm organic page week)"
    sha = stepchecks.sha256(run.path / checked)
    for row in reversed(manifest.rows(run)):
        if row["source"] != SOURCE or row["parent"] != checked:
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        if isinstance(params, dict) and params.get("week_sha256") == sha and (run.path / row["file"]).is_dir():
            return None
    return f"the week page is built from the checked week plan, {checked} (tm organic page week)"


# --- decisions ----------------------------------------------------------------------------------------

def decided_page(run: RunFolder) -> dict:
    """The page people decide on and the week plan it was built from: the published folder (`state.pages["week"]`),
    else the latest build. `{folder, week, data}`; a Stop when that file is gone or changed since."""
    target = (state.load(run).pages.get(PAGE) or {}).get("folder")
    rows = [r for r in manifest.rows(run) if r["source"] == SOURCE and (target is None or r["file"] == target)]
    if not rows:
        where = f"the published folder {target}" if target else "this run"
        raise Stop(f"No week page build of {where} is recorded (tm organic page week), so it is unknown which week "
                   f"people decided on. Build the page and publish it, then read the decisions; {AGAIN}.")
    row = rows[-1]
    try:
        params = json.loads(row["params"]) if row["params"] else {}
    except ValueError:
        params = {}
    path = run.path / row["parent"]
    if not path.is_file() or params.get("week_sha256") != stepchecks.sha256(path):
        raise Stop(f"The page {row['file']} was built from {row['parent']}, which is gone or changed since, so it is "
                   "unknown which week people decided on. Build the page again (tm organic page week), publish it and "
                   f"let the user decide on it; {AGAIN}.")
    return {"folder": row["file"], "week": row["parent"], "data": organic_week.read_week(path, row["parent"])}


_DECISION_WORDS = {"ok": "ok", "skip": "skip", "pomiń": "skip", "pomin": "skip"}
_OUTPUT_WORDS = {"video": "video", "ai video": "video", "wideo": "video", "wideo ai": "video", "script": "script",
                 "skrypt": "script"}
_FIELDS = {"idea": "idea", "pomysł": "idea", "output": "output", "wynik": "output", "note": "note", "uwaga": "note"}
_APPROVED = ("approved", "zatwierdzony", "zatwierdzono")
_YES = {"yes": True, "tak": True, "no": False, "nie": False}


def parse_chat(text: str, week: dict) -> list[tuple[str, dict]]:
    """The user's words in chat, one line per day, as page documents (`(page slot key, document)`, and `_week`). A
    line naming no day of the week is a Stop that quotes it."""
    keys = {}
    for s in week["slots"]:
        day = organic_week.DAY[s["day"]]
        for name in (day, DAY_EN[day], s["id"]):
            keys[name.casefold()] = DAY_EN[day]
    docs: list[tuple[str, dict]] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-* ").strip()
        if not line:
            continue
        head, _, rest = line.partition(":")
        head = head.strip().casefold()
        if head in _APPROVED:
            said = _YES.get(rest.strip().rstrip(".").casefold())
            if said is None:
                raise Stop(f"“{raw.strip()}” says neither yes nor no. Write `approved: yes` or `approved: no`; {AGAIN}.")
            docs.append((WEEK_DOC, {"approved": said}))
            continue
        if head not in keys:
            raise Stop(f"“{raw.strip()}” names no day of this week ({', '.join(sorted(set(keys.values())))}, or the "
                       f"English day or the idea's id). Write one line per day; {AGAIN}.")
        parts = [p.strip() for p in rest.split(";")]
        decision = _DECISION_WORDS.get(parts[0].casefold())
        if decision is None:
            raise Stop(f"“{raw.strip()}”: the decision is ok or skip; {AGAIN}.")
        doc: dict = {"decision": decision}
        for part in parts[1:]:
            name, _, value = part.partition(":")
            field = _FIELDS.get(name.strip().casefold())
            if field is None:
                raise Stop(f"“{raw.strip()}”: {name.strip()!r} is not idea, output or note; {AGAIN}.")
            value = value.strip()
            if field == "output":
                value = _OUTPUT_WORDS.get(value.casefold())
                if value is None:
                    raise Stop(f"“{raw.strip()}”: the output is video or script; {AGAIN}.")
            doc[field] = value
        docs.append((keys[head], doc))
    return docs


def _decisions_files(run: RunFolder) -> list[Path]:
    """The decisions files of the week page, oldest first (by version)."""
    folder = run.path / organic_week.WIP
    name = re.compile(rf"^{organic_week.DECISIONS_STEM}_v(\d+)\.json$")
    found = [(int(m.group(1)), f) for f in folder.glob(f"{organic_week.DECISIONS_STEM}_v*.json") if folder.is_dir()
             for m in [name.match(f.name)] if m]
    return [f for _, f in sorted(found)]


def take_decisions(run: RunFolder, *, file: Path | None = None, text: Path | None = None) -> dict:
    """Read the decisions taken on the week page into `03_wip/decisions_week_vNN.json` (the module docstring) and stop
    waiting for them. Default input: the newest saved db answer on this page's slug; `text`: the user's words in chat.
    A Stop when a slot names an idea that is not in the week, or two slots the same idea."""
    slug = (state.load(run).pages.get(PAGE) or {}).get("slug")
    if text is None and not slug:
        raise Stop(f"The page's publish is not recorded (tm page published --page {PAGE}), so it is unknown which "
                   "artifact's decisions to read. Record it, read the decisions with `db_list` first, or give the "
                   f"user's answer in chat form with --text; {AGAIN}.")
    decided = decided_page(run)
    week = decided["data"]
    if text is not None:
        source = Path(text)
        docs = parse_chat(source.read_text(encoding="utf-8-sig"), week)
    else:
        source = Path(file) if file is not None else page.saved_answer(run, PAGE, COLLECTION)
        if source is None:
            raise Stop(f"No saved answer holds the decisions of this page ({slug}): read them with `db_list` first "
                       f"(slug {slug}, collection {COLLECTION}, limit 1000), then run this again; {AGAIN}.")
        docs = page.db_docs(page.whole_answer(run, PAGE, source, COLLECTION), collection=COLLECTION)
        if not docs:
            raise Stop(EMPTY)
    try:
        rows = organic_week.choices(week, docs)
        total = organic_week.total(week, docs)
    except ValueError as exc:
        raise Stop(f"The week page's decisions cannot be used: {exc} Let the user choose again on the page, or write "
                   f"their answer in chat form and read it with --text; {AGAIN}.") from None
    newest = organic_week.newest_docs(week, docs)
    read = {day: {k: v for k, v in doc.items() if k != "updated_at"} for day, doc in newest.items()
            if day != WEEK_DOC}
    week_doc = newest.get(WEEK_DOC) or {}
    carried = []
    if text is None:
        earlier = page.earlier_decisions(run, _decisions_files(run), decided["folder"], built="folder",
                                         rows="read", command=DECISIONS_SOURCE, shape=dict) or {}
        carried = page.mark_carried(copy.deepcopy(read), earlier)
        for day in carried:
            rows[day]["carried"] = True
    page_total = week_doc.get("total") if isinstance(week_doc.get("total"), (int, float)) else None
    rel = _rel(run, source)
    out = run.next_version(organic_week.WIP, organic_week.DECISIONS_STEM, "json")
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {"page": PAGE, "week": decided["week"], "folder": decided["folder"], "from": rel, "slug": slug or None,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "chat" if text is not None else "page", "decisions": rows, "read": read, "carried": carried,
            "approved": week_doc.get("approved") is True, "total": total, "page_total": page_total}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, organic_week.WIP, DECISIONS_SOURCE, parent=rel,
                    params={"page": PAGE, "folder": decided["folder"], "week": decided["week"]})
    page.clear_await(run, PAGE)
    return {"file": out_rel, "from": rel, "page": PAGE, "folder": decided["folder"], "week": decided["week"],
            "source": body["source"], "decisions": rows, "carried": carried, "docs": len(docs),
            "approved": body["approved"], "total": total, "budget": week["budget"]}
