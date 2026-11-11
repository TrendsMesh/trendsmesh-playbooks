"""The proposals page (organic video C2): the port of the handoff's `tools/pb3/proposals_page.py`, and the
decisions taken on it.

    build(run, file=None)            04_final/proposals_vNN/ from the checked proposals (C1)
    take_decisions(run, *, file, text)   03_wip/decisions_proposals_vNN.json from the page's db or chat
    built_gap(run)                   the step check `proposals_page_built`

The port keeps the original's HTML byte for byte, up to the wording table (`organic_pages.WORDING`): the
ExampleEdu walkthrough's page, made by the reference tool, is rebuilt exactly (fixtures/organic/README.md).
Its changes, plan Decision 10:
- "How" is the plugin's level radio (document key `level`), named in the page language
  (`organic_pages.levels`); the original's "Gates" row is gone, since the level decides the check-ins. The page reads
  the original's `mode`/`gates` documents too (`levelOf`, as `organic_proposals._level`). The run's level
  (run.json `level`, never `mode.variant`) is ticked first.
- Trends come from the run's saved answers (`organic_research.resolve`, `trends.load_videos`), not
  the original's `card_<id8>.json` files; a thumbnail is an asset file beside index.html
  (`assets/<asset_id>.jpg`, `page.fetch_image`), not a data URI; one that cannot be had leaves an
  empty `src`, as the reference tool does without a `thumbnail_url`.
- The original's Polish table is the string table's `organic.proposals.*` keys (`FRAGS`, `localize`): the page is
  built in any language whose table has them (`organic_pages.page_lang`), else in English with a warning.
- No backslash inside an f-string expression (Python 3.11); the page's script data cannot be ended by
  `</` or turned by `<!--`.

Decisions. The page saves one document per proposal in its db collection `decisions`
(`decisions/<pid>`: decision, level, output, platforms, answers, note, updated_at). `take_decisions`
reads the newest saved db read (ArtifactData list), whole and read after the page was published and awaited
(`page.saved_answer`, `page.whole_answer`, `page.db_docs`), or the page's "Copy summary" text that the
user sent or the agent wrote from their words in chat (`--text`), into

    03_wip/decisions_proposals_vNN.json = {"page": "proposals", "proposals": <the checked file the
        page was built from>, "folder": <the page build>, "from", "slug", "at",
        "decisions": {pid: row}, "read": {pid: document}, "carried": [pid, ...]}

with each row as `organic_proposals.decisions` makes it and each document as read (`updated_at`
aside). A row whose document read from the db equals the one an earlier page build's decisions file
read is `carried` (`page.mark_carried`, PB02's rule: compared with the latest file of another build
only; the documents, so a default that changed since does not hide it); a row from chat is the
user's word and never carried.
A whole, fresh read with no documents is a Stop that sends the agent to chat.
"""

from __future__ import annotations

import copy
import html
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from tm import (checkins, i18n, manifest, organic_pages, organic_proposals, organic_research, page, state, stepchecks,
                trends)
from tm.organic_pages import CSS, Frag, levels as level_names
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "proposals"
COLLECTION = "decisions"
SOURCE = "tm organic page proposals"
DECISIONS_SOURCE = "tm organic decisions"
WIP = organic_proposals.WIP
DECISIONS_STEM = organic_proposals.DECISIONS_STEM
READ_WITH = f"tm organic decisions --run <run> --page {PAGE}"
EMPTY = ("Nothing was saved on the page. Ask the user in chat; a decision written in chat counts. Write their answer "
         "as the page's Copy summary lines, one per proposal (for example `M1 <title>: produce, Check every step; "
         "output: script; platforms: tiktok, youtube`), to a file in the run and read it with --text. The run "
         "continues from the same place.")

KIND = {"hook_trend": "Hook", "topic_trend": "Topic", "sound_trend": "Sound", "format_trend": "Format"}
RISK = {"low": "Low", "medium": "Medium", "high": "High"}
PLATFORMS = [("tiktok", "TikTok"), ("instagram", "Instagram Reels"), ("youtube", "YouTube Shorts"), ("facebook", "Facebook Reels")]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def compact(n) -> str:
    if n is None:
        return "n/a"
    n = float(n)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            v = n / div
            return f"{v:.1f}{suf}".replace(".0" + suf, suf)
    return str(int(n))


def _script(value, *, ascii_only: bool = False) -> str:
    """JSON for the page's script: `</` cannot end it and `<!--` cannot change how it is parsed."""
    return json.dumps(value, ensure_ascii=ascii_only).replace("</", "<\\/").replace("<!--", "<\\u0021--")


def decision_panel(p: dict, levels: dict[str, str], level: str) -> str:
    pid = esc(p["id"])
    seg = "".join(
        f'<label><input type="radio" name="d-{pid}" id="d-{pid}-{v}" value="{v}"><span>{t}</span></label>'
        for v, t in (("produce", "Produce"), ("later", "Maybe later"), ("skip", "Skip"))
    )
    how = "".join(
        f'<label><input type="radio" name="l-{pid}" id="l-{pid}-{v}" value="{v}"{" checked" if v == level else ""}><span>{esc(t)}</span></label>'
        for v, t in levels.items()
    )
    outs = "".join(
        f'<label><input type="radio" name="o-{pid}" id="o-{pid}-{v}" value="{v}"><span>{t}</span></label>'
        for v, t in (("video", "AI video"), ("script", "Script to film"))
    )
    pfs = "".join(f'<label class="chk"><input type="checkbox" id="p-{pid}-{k}" data-pf="{k}" checked>{esc(n)}</label>' for k, n in PLATFORMS)
    qs = "".join(
        f'<div class="q"><label for="a-{pid}-{i}">{esc(q)}</label><textarea id="a-{pid}-{i}" data-q="{i}" rows="1" placeholder="Leave empty and Claude proposes options"></textarea></div>'
        for i, q in enumerate(p.get("taste", []))
    )
    return f"""<div class="decide" id="dec-{pid}" data-pid="{pid}">
<div class="row"><span class="lbl">Decision</span><span class="seg" role="radiogroup" aria-label="Decision for {pid.upper()}">{seg}</span></div>
<div class="row"><span class="lbl">Output</span><span class="seg" role="radiogroup" aria-label="Output for {pid.upper()}">{outs}</span></div>
<div class="row"><span class="lbl">How</span><span class="seg" role="radiogroup" aria-label="Production mode for {pid.upper()}">{how}</span></div>
<div class="row" id="pfs-{pid}"><span class="lbl">Post to</span>{pfs}</div>
<p class="hint" id="auto-{pid}" hidden>A–Z: Claude produces the whole video without stopping. While we test, the exact cost is still confirmed once before anything is paid.</p>
{qs}
<div class="q"><label for="n-{pid}">Notes for Claude (optional)</label><textarea id="n-{pid}" rows="1" placeholder="e.g. use a golden retriever instead of the husky"></textarea></div>
</div>"""


JS = r"""
(function(){
  const P = window.__PROPOSALS__;
  const LEVELS = window.__LEVELS__ || {};
  const levelOf = v => LEVELS[v.level] ? v.level : v.mode === 'auto' ? 'hands_off' : Array.isArray(v.gates) ? (['pack','images','video','edit'].every(g => v.gates.includes(g)) ? 'every_step' : 'big_calls') : v.mode === 'gates' ? 'every_step' : null;
  const KEY = 'pb3-decisions-' + window.__RUN_ID__;
  const state = {};
  let db = null;
  const statusEl = document.getElementById('save-status');
  const setStatus = t => { statusEl.textContent = t; };
  P.forEach(p => { state[p.id] = {decision: null, level: window.__DEFAULT_LEVEL__ || 'every_step', answers: {}, note: '', platforms: ['tiktok','instagram','youtube','facebook'], output: window.__DEFAULT_OUTPUT__ || 'video'}; });
  try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s) Object.keys(s).forEach(k => { if (state[k]) Object.assign(state[k], s[k]); }); } catch (e) {}

  function paint(){
    let n = {produce:0, later:0, skip:0}, lo = 0, hi = 0;
    P.forEach(p => {
      const s = state[p.id];
      ['produce','later','skip'].forEach(v => { const el = document.getElementById(`d-${p.id}-${v}`); if (el) el.checked = s.decision === v; });
      Object.keys(LEVELS).forEach(v => { const el = document.getElementById(`l-${p.id}-${v}`); if (el) el.checked = s.level === v; });
      ['video','script'].forEach(v => { const el = document.getElementById(`o-${p.id}-${v}`); if (el) el.checked = (s.output || 'video') === v; });
      document.querySelectorAll(`#pfs-${p.id} input[data-pf]`).forEach(cb => { cb.checked = (s.platforms || []).includes(cb.dataset.pf); });
      document.getElementById(`auto-${p.id}`).hidden = s.level !== 'hands_off';
      document.querySelectorAll(`#dec-${p.id} textarea[data-q]`).forEach(t => { if (document.activeElement !== t) t.value = s.answers[t.dataset.q] || ''; });
      const note = document.getElementById(`n-${p.id}`); if (document.activeElement !== note) note.value = s.note || '';
      const box = document.getElementById(`dec-${p.id}`); box.classList.toggle('on', s.decision === 'produce'); box.classList.toggle('skip', s.decision === 'skip');
      const pill = document.querySelector(`[data-pill="${p.id}"]`);
      pill.className = 'chip dpill' + (s.decision ? ' ' + s.decision : '');
      pill.textContent = {produce:'Produce', later:'Maybe later', skip:'Skip'}[s.decision] || 'Not decided';
      if (s.decision) n[s.decision]++;
      if (s.decision === 'produce') { lo += p.cost[0]; hi += p.cost[1]; }
    });
    const open = P.length - n.produce - n.later - n.skip;
    document.getElementById('sum').innerHTML = `<span><b>${n.produce}</b> to produce</span><span>${n.later} later · ${n.skip} skipped · ${open} not decided</span><span>Est. <b>$${lo.toFixed(2)}–${hi.toFixed(2)}</b></span>`;
  }

  const pending = {};
  async function save(pid){
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
    if (!db) { setStatus('Saved in this browser only'); return; }
    if (pending[pid]) { pending[pid].again = true; return; }
    pending[pid] = {again:false};
    setStatus('Saving…');
    try {
      do { pending[pid].again = false; await db.doc('decisions/' + pid).set(Object.assign({}, state[pid], {proposal: pid, updated_at: new Date().toISOString()})); } while (pending[pid].again);
      setStatus('Saved · Claude can read your choices');
    } catch (e) { setStatus('Could not save to the page (' + (e && e.code || 'error') + '); kept in this browser'); }
    delete pending[pid];
  }
  const timers = {};
  function saveSoon(pid){ clearTimeout(timers[pid]); timers[pid] = setTimeout(() => save(pid), 600); }

  P.forEach(p => {
    const pid = p.id;
    document.querySelectorAll(`input[name="d-${pid}"]`).forEach(r => r.addEventListener('change', () => { state[pid].decision = r.value; paint(); save(pid); }));
    document.querySelectorAll(`input[name="l-${pid}"]`).forEach(r => r.addEventListener('change', () => { state[pid].level = r.value; paint(); save(pid); }));
    document.querySelectorAll(`input[name="o-${pid}"]`).forEach(r => r.addEventListener('change', () => { state[pid].output = r.value; paint(); save(pid); }));
    document.querySelectorAll(`#dec-${pid} textarea[data-q]`).forEach(t => t.addEventListener('input', () => { state[pid].answers[t.dataset.q] = t.value; saveSoon(pid); }));
    document.getElementById(`n-${pid}`).addEventListener('input', e => { state[pid].note = e.target.value; saveSoon(pid); });
    document.querySelectorAll(`#pfs-${pid} input[data-pf]`).forEach(cb => cb.addEventListener('change', () => { state[pid].platforms = [...document.querySelectorAll(`#pfs-${pid} input[data-pf]`)].filter(x => x.checked).map(x => x.dataset.pf); save(pid); }));
  });
  document.getElementById('all-produce').addEventListener('click', () => { P.forEach(p => { state[p.id].decision = 'produce'; }); paint(); P.forEach(p => save(p.id)); });
  document.getElementById('copy-sum').addEventListener('click', async () => {
    const lines = P.map(p => { const s = state[p.id]; const a = Object.values(s.answers).filter(Boolean); return `${p.id.toUpperCase()} ${p.title}: ${s.decision || 'not decided'}` + (s.decision === 'produce' ? `, ${LEVELS[s.level] || s.level}` : '') + `; output: ${s.output || 'video'}` + `; platforms: ${(s.platforms || []).join(', ')}` + (a.length ? `; answers: ${a.join(' | ')}` : '') + (s.note ? `; note: ${s.note}` : ''); });
    try { await navigator.clipboard.writeText(lines.join('\n')); setStatus('Summary copied'); } catch (e) { setStatus('Copy was blocked by the browser'); }
  });
  paint();
  setStatus('Choices are kept in this browser until the page connects…');

  (async () => {
    const timer = setTimeout(() => { if (!db) setStatus('Saved in this browser only (page storage not reachable)'); }, 10000);
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    try { db = window.claude && window.claude.use ? await window.claude.use('db') : null; } catch (e) { db = null; }
    clearTimeout(timer);
    if (!db) { setStatus('Saved in this browser only'); return; }
    try {
      const snap = await db.collection('decisions').get();
      snap.docs.forEach(d => { const v = d.data(); if (v && state[d.id]) { Object.assign(state[d.id], {decision: v.decision ?? null, level: levelOf(v) || state[d.id].level, answers: v.answers || {}, note: v.note || '', platforms: Array.isArray(v.platforms) ? v.platforms : state[d.id].platforms, output: v.output || state[d.id].output}); } });
      paint();
      setStatus(snap.empty ? 'Ready · your choices save automatically' : 'Saved · Claude can read your choices');
    } catch (e) { setStatus('Page storage not reachable; choices kept in this browser'); }
  })();
})();
"""


# The page's fixed fragments in another language (the original's Polish table, keyed, in its order; its entries
# for the gates row, the "A–Z" mode and the risk words alone matched nothing on the page and are gone). Each is
# the plugin's English (after `WORDING`) -> the same in the page language.
_P = "organic.proposals."
FRAGS: list[Frag] = [
    Frag("§", _P + "risk_low"), Frag("§", _P + "risk_medium"), Frag("§", _P + "risk_high"),
    Frag(">§<", _P + "produce"), Frag(">§<", _P + "later"), Frag(">§<", _P + "skip"),
    Frag('placeholder="§"', _P + "taste_placeholder"),
    Frag('<span class="lbl">§</span>', "organic.decision"), Frag('<span class="lbl">§</span>', _P + "how"),
    Frag('<span class="lbl">§</span>', "organic.post_to"),
    Frag("§", _P + "hands_off_hint"),
    Frag("§", _P + "notes_label"), Frag('placeholder="§"', _P + "notes_placeholder"),
    Frag("{produce:'§0', later:'§1', skip:'§2'}[s.decision] || '§3'",
         (_P + "produce", _P + "later", _P + "skip", _P + "not_decided"), "js"),
    Frag("> §<", _P + "sum_to_produce", "tpl"), Frag(" § · ", _P + "sum_later", "tpl"),
    Frag(" § · ", _P + "sum_skipped", "tpl"), Frag(" §<", _P + "sum_not_decided", "tpl"),
    Frag("<span>§ <b>", _P + "sum_estimate", "tpl"),
    Frag("'§'", "organic.not_saved_unreachable", "js"), Frag("'§'", "organic.not_saved", "js"),
    Frag("'§'", "organic.saving", "js"), Frag("'§'", "organic.saved", "js"),
    Frag("'§ ('", _P + "save_failed", "js"), Frag("'); §'", _P + "save_failed_kept", "js"),
    Frag("'§'", _P + "summary_copied", "js"), Frag("'§'", _P + "copy_blocked", "js"),
    Frag("'§'", "organic.connecting", "js"), Frag("'§'", "organic.storage_unreachable", "js"),
    Frag("'§'", "organic.ready", "js"),
    Frag("§ · ", _P + "eyebrow"), Frag(">§<", _P + "already_made"),
    Frag(">§<", _P + "produce_all"), Frag(">§<", _P + "copy_summary"),
    Frag("§", _P + "hint"),
    Frag(">§ <b>", _P + "product_chip"), Frag(">§ <b>", "organic.length"),
    Frag("<h3>§</h3>", _P + "the_video"), Frag("<h3>§</h3>", _P + "recipe"), Frag("<dt>§</dt>", _P + "production"),
    Frag("<dt>§</dt>", _P + "voice"), Frag("<dt>§</dt>", _P + "music"), Frag("<dt>§</dt>", _P + "text"),
    Frag("<dt>§</dt>", _P + "product"), Frag("<h3>§</h3>", _P + "risks"), Frag("<h3>§</h3>", _P + "cost"),
    Frag("<b>§</b>", _P + "facts"), Frag("<h3>§</h3>", _P + "trends_behind"),
    Frag(" § · ", _P + "creators"), Frag(" § · ", _P + "videos"), Frag(" § · ", _P + "views"),
    Frag('<p class="role">§ ', _P + "used_for"), Frag('alt="§ ', _P + "evidence_by"),
    Frag(" §</span>", _P + "views_short"), Frag(">§ ", _P + "watch_on"), Frag("<p>§ ", "organic.run_folder"),
    Frag(">§<", _P + "kind_hook"), Frag(">§<", _P + "kind_topic"), Frag(">§<", _P + "kind_sound"),
    Frag(">§<", _P + "kind_format"),
    Frag(">§<", _P + "not_decided"), Frag('aria-label="§', "organic.decision_for"),
    Frag('aria-label="§', _P + "mode_for"), Frag('aria-label="§"', "organic.your_decisions"),
    Frag('aria-label="§"', _P + "nav"),
    Frag("${({produce:'§0', later:'§1', skip:'§2'})[s.decision] || '§3'}",
         (_P + "summary_produce", _P + "summary_later", _P + "summary_skip", _P + "summary_not_decided"), "js",
         english="${s.decision || 'not decided'}"),
    Frag("`; §: ", _P + "summary_platforms", "text"), Frag("`; §: ", _P + "summary_answers", "text"),
    Frag("`; §: ", _P + "summary_note", "text"),
    Frag('<span class="lbl">§</span>', "organic.output"), Frag(">§<", _P + "out_video"), Frag(">§<", _P + "out_script"),
    Frag('aria-label="§', _P + "output_for"), Frag("`; §: ", _P + "summary_output", "text"),
    # English the original's Polish table leaves as it is (the trend's stats line)
    Frag(" · § ", _P + "trend_hook"), Frag(" · § ", _P + "trend_id"),
]


def plural(n: int) -> str:
    """The form a count of n takes: `one`, `few` (2–4, 22–24 …, not 12–14) or `many` (Polish's rule; a language
    with two forms gives `few` and `many` the same words)."""
    return "one" if n == 1 else "few" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "many"


def lede_frags(n: int) -> list[Frag]:
    """The lede's words around the store, for n proposals."""
    return [Frag('<p class="lede">§ ', f"{_P}lede_ideas_{plural(n)}", values={"n": n}),
            Frag("), §</p>", _P + "lede_rest")]


def localize(text: str, lang) -> str:
    """The page in `lang` (`organic_pages.localize`), the lede for its count of proposals included."""
    found = re.search(r'<p class="lede">(\d+) ', text)
    return organic_pages.localize(text, lang, FRAGS + (lede_frags(int(found.group(1))) if found else []))


def render(data: dict, trends_of, thumb_of, *, level: str, lang: str | None = None) -> str:
    """The page in `lang` (else the language it is built in, `organic_pages.lang_of`): the original's `render`,
    then `localize`. `trends_of(id)` gives a proposal trend's (card, videos); `thumb_of(video)` its thumbnail's src."""
    tr = i18n.translator(lang or organic_pages.lang_of(data))
    levels = level_names(tr)
    chan = {c["id"]: c for c in data["channels"]}
    out = []
    out.append(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(data['title'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">""")
    out.append(f"""<header><div class="eyebrow">Organic AI video · proposals · {esc(data['date'])}</div>
<h1>{esc(data['title'])}</h1>
<p class="lede">{len(data['proposals'])} video ideas for {esc(data['store']['name'])} ({esc(data['store']['note'])}), each built on trends rising now, with the evidence videos behind it. Pick the ones to produce; nothing is generated or paid until you approve a pack and its cost.</p>
<div class="chips"><span class="chip">Already made:</span>{''.join(f'<span class="chip">{esc(x)}</span>' for x in data.get('already_made', []))}</div>
</header>""")

    out.append("""<div class="bar" role="region" aria-label="Your decisions"><div class="sum" id="sum"></div>
<div class="acts"><button class="btn primary" id="all-produce" type="button">Produce all</button><button class="btn" id="copy-sum" type="button">Copy summary</button><span class="status" id="save-status" aria-live="polite"></span></div>
<p class="hint">Mark each proposal below. Choices save as you click; when you are done, write “ready” to Claude in the chat and it reads them from this page.</p></div>""")
    out.append('<nav aria-label="Proposals" class="grid">')
    for p in data["proposals"]:
        c = chan[p["channel"]]
        out.append(f"""<a class="card" href="#{esc(p['id'])}"><span class="id">{esc(p['id'].upper())} · {esc(c['name'])}</span>
<span class="t">{esc(p['video_type'])}</span><span class="k">“{esc(p['title'])}”</span>
<span class="meta"><span class="chip risk {esc(p['risk']['level'])}">Risk: {RISK[p['risk']['level']]}</span><span class="chip">{esc(p['approach'])}</span><span class="chip">Product: <b>{esc(p['product']['level'])}</b></span><span class="chip cost">${p['cost']['low']:.2f}–{p['cost']['high']:.2f}</span><span class="chip dpill" data-pill="{esc(p['id'])}">Not decided</span></span></a>""")
    out.append("</nav>")

    for p in data["proposals"]:
        c = chan[p["channel"]]
        r = p["recipe"]
        out.append(f"""<section class="p" id="{esc(p['id'])}"><div class="phead"><div class="eyebrow">{esc(p['id'].upper())} · {esc(c['name'])} · {esc(c['niche'])}</div>
<h2>{esc(p['video_type'])}: “{esc(p['title'])}”</h2>
<div class="meta"><span class="chip risk {esc(p['risk']['level'])}">Risk: {RISK[p['risk']['level']]}</span><span class="chip">{esc(p['approach'])}</span><span class="chip">Length <b>{esc(p['length'])}</b></span><span class="chip cost">${p['cost']['low']:.2f}–{p['cost']['high']:.2f}</span></div></div>
{decision_panel(p, levels, level)}
<div class="cols"><div class="block" style="gap:16px">
<p class="why">{esc(p['why'])}</p>
<div class="block"><h3>The video</h3><ol class="beats">{''.join(f'<li>{esc(b)}</li>' for b in p['beats'])}</ol></div>
<div class="block"><h3>Recipe</h3><dl class="recipe"><dt>Production</dt><dd>{esc(r['production'])}</dd><dt>Voice</dt><dd>{esc(r['voice'])}</dd><dt>Music / sound</dt><dd>{esc(r['music'])}</dd><dt>Text</dt><dd>{esc(r['text'])}</dd><dt>Product</dt><dd><b>{esc(p['product']['level'])}</b>: {esc(p['product']['note'])}</dd></dl></div>
<div class="block"><h3>Risks</h3><ul class="plain">{''.join(f'<li>{esc(x)}</li>' for x in p['risk']['items'])}</ul></div>
<div class="block"><h3>Cost</h3><p style="margin:0" class="cost">${p['cost']['low']:.2f}–{p['cost']['high']:.2f}</p><p style="margin:0;color:var(--muted);font-size:14px">{esc(p['cost']['note'])}</p></div>""")
        if p.get("facts"):
            out.append(f'<div class="box"><p><b>Facts to source:</b> {esc(p["facts"])}</p></div>')
        out.append('</div><div class="block"><h3>Trends behind it</h3>')
        for t in p["trends"]:
            card, vids = trends_of(t["id"])
            reach = card.get("reach") or {}
            hs = {}
            for v in vids:
                if v.get("hook_source"):
                    hs[v["hook_source"]] = hs.get(v["hook_source"], 0) + 1
            hs_txt = (" · hook " + ", ".join(f"{k} {n}/{len(vids)}" for k, n in sorted(hs.items(), key=lambda x: -x[1]))) if hs else ""
            out.append(f"""<div class="trend"><div class="tname"><span class="kind">{esc(KIND.get(card.get('kind'), card.get('kind')))}</span><strong>{esc(card.get('name'))}</strong></div>
<div class="tstats">{compact(reach.get('creators'))} creators · {compact(reach.get('videos'))} videos · {compact(reach.get('views'))} views · {esc(card.get('status'))}{esc(hs_txt)} · id {esc(t['id'])}</div>
<p class="role">Used for: {esc(t['role'])}</p><div class="ev">""")
            for i in t.get("pick", [0, 1]):
                if i >= len(vids):
                    continue
                v = vids[i]
                label = v.get("hook_text") or v.get("excerpt") or ""
                out.append(f"""<a class="vid" href="{esc(v.get('url'))}" target="_blank" rel="noopener"><span class="thumb"><img alt="Evidence video by {esc(v.get('creator'))}" src="{esc(thumb_of(v))}"><span class="views">{compact(v.get('views'))} views</span></span>
<span class="who">@{esc(v.get('creator'))}</span><span class="hook">{esc(label)}</span><span class="open">Watch on {esc((v.get('platform') or 'tiktok').title())} ↗</span></a>""")
            out.append("</div></div>")
        out.append("</div></div></section>")

    meta = [{"id": p["id"], "title": p["title"], "cost": [p["cost"]["low"], p["cost"]["high"]]} for p in data["proposals"]]
    run_id = Path(data["run"]).name
    proposals_js, run_js = _script(meta), _script(run_id, ascii_only=True)
    output_js, level_js = _script(data.get("default_output", "video"), ascii_only=True), _script(level, ascii_only=True)
    out.append(f"""<footer><p>{esc(data['data_note'])}</p><p>Run folder: {esc(data['run'])}</p></footer></div>
<script>window.__PROPOSALS__ = {proposals_js}; window.__RUN_ID__ = {run_js}; window.__DEFAULT_OUTPUT__ = {output_js}; window.__DEFAULT_LEVEL__ = {level_js}; window.__LEVELS__ = {_script(levels)};</script>
<script>{JS}</script></body></html>""")
    return localize("".join(out), tr)


# --- building it in the run ------------------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{path} is not inside the run folder {run.path}.") from None


def _read(path: Path, rel: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"{rel} cannot be read ({exc}); check the proposals again (tm organic proposals check); "
                   f"{AGAIN}.") from None
    if not isinstance(data, dict):
        raise Stop(f"{rel} is not one JSON object; check the proposals again (tm organic proposals check); {AGAIN}.")
    return data


def _checked(run: RunFolder, file: Path | None) -> tuple[Path, str, dict]:
    """The checked proposals file (C1): its path, run-relative path and data. `file`, when given, must
    be that file. A Stop while C1 is not done."""
    gap = organic_proposals.checked_gap(run)
    if gap is not None:
        raise Stop(f"The page is built from checked proposals, and C1 is done once {gap} (tm organic proposals check "
                   f"--run <run> --file {organic_proposals.FILE_PATTERN}). Check them, then build again; {AGAIN}.")
    rel = state.load(run).checked[organic_proposals.KEY]["file"]
    if file is not None and _rel(run, file) != rel:
        raise Stop(f"{_rel(run, file)} is not the checked proposals file ({rel}): check it first (tm organic proposals "
                   f"check), then build the page from it; {AGAIN}.")
    return run.path / rel, rel, _read(run.path / rel, rel)


def _level(run: RunFolder) -> str:
    """The run's level (run.json `level`, never `mode.variant`), ticked first on the page."""
    level = state.load(run).level
    return level if level in checkins.LEVEL_IDS else "every_step"


def _trends(run: RunFolder, data: dict) -> dict[str, tuple[dict, list[dict]]]:
    """Each proposal trend's saved card and videos, by the id the proposal names."""
    found = {}
    for p in data["proposals"]:
        for t in p["trends"]:
            if t["id"] in found:
                continue
            tid, card = organic_research.resolve(run, t["id"])
            try:
                found[t["id"]] = (card, trends.load_videos(run, tid))
            except ValueError as exc:
                raise Stop(f"A saved video page of {tid} cannot be read ({exc}). Fetch it again with get_trend_videos, "
                           f"then build again; {AGAIN}.") from None
    return found


def _picked(data: dict, found: dict) -> list[dict]:
    """The evidence videos the page shows, in page order."""
    out = []
    for p in data["proposals"]:
        for t in p["trends"]:
            vids = found[t["id"]][1]
            out += [vids[i] for i in t.get("pick", [0, 1]) if i < len(vids)]
    return out


def _asset(v: dict) -> str | None:
    aid = v.get("asset_id")
    return page.asset_name(f"{aid}.jpg") if isinstance(aid, str) and aid else None


def build(run: RunFolder, file: Path | None = None) -> dict:
    """Build the page from the checked proposals into a new `04_final/proposals_vNN/` (index.html,
    assets/<asset_id>.jpg). Nothing is written while people decide on the page (`page.Deciding`),
    before C1 is done, or when the files would be over the Artifact tool's limits (each a Stop). A
    thumbnail that cannot be had is listed in `missing_thumbnails` and leaves an empty src. `lang` is the language
    it is built in; `language_warning` says why when that is English and not the run's (`organic_pages.page_lang`)."""
    if page.awaiting(run, PAGE) is not None:
        raise page.Deciding(PAGE, read=READ_WITH)
    path, rel, data = _checked(run, file)
    built = organic_pages.page_lang(data)
    level = _level(run)
    found = _trends(run, data)
    with tempfile.TemporaryDirectory() as tmp:
        thumbs: dict[str, Path] = {}
        missing: list[str] = []
        for v in _picked(data, found):
            name = _asset(v)
            if name in thumbs:
                continue
            if name is not None and page.fetch_image(v.get("thumbnail_url"), Path(tmp) / name):
                thumbs[name] = Path(tmp) / name
            elif str(v.get("asset_id") or v.get("url")) not in missing:
                missing.append(str(v.get("asset_id") or v.get("url")))
        try:
            text = render(data, lambda tid: found[tid], lambda v: f"assets/{_asset(v)}" if _asset(v) in thumbs else "",
                          level=level, lang=built.lang)
        except (KeyError, ValueError) as exc:   # the file's shape; anything else is the engine's, not the user's file
            raise Stop(f"{rel} is not in the page's shape ({type(exc).__name__}: {exc}); check it again (tm organic "
                       f"proposals check); {AGAIN}.") from None
        planned = {"index.html": len(text.encode("utf-8"))} | {f"assets/{n}": f.stat().st_size for n, f in thumbs.items()}
        over = page.over_limits(planned)
        if over:
            raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Pick fewer "
                       f"evidence videos in the proposals, check them again and build again; {AGAIN}.")
        out = page.new_folder(run, PAGE)
        for name, f in thumbs.items():
            shutil.copyfile(f, out / "assets" / name)
    with open(out / "index.html", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, page.FINAL, SOURCE, parent=rel,
                    params={"proposals_sha256": stepchecks.sha256(path), "lang": built.lang, "level": level,
                            "missing_thumbnails": len(missing)})
    return {"folder": out_rel, "files": page.files(out), "missing_thumbnails": missing, "proposals": rel,
            "lang": built.lang, "level": level, "language_warning": built.warning}


def built_gap(run: RunFolder) -> str | None:
    """The `proposals_page_built` step check: C2's page is built from the latest checked proposals,
    unchanged since. Reads only."""
    checked = (state.load(run).checked.get(organic_proposals.KEY) or {}).get("file")
    if not checked or organic_proposals.checked_gap(run) is not None:
        return "the proposals are checked (tm organic proposals check) and the page is built from them (tm organic page proposals)"
    sha = stepchecks.sha256(run.path / checked)
    for row in reversed(manifest.rows(run)):
        if row["source"] != SOURCE or row["parent"] != checked:
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        if isinstance(params, dict) and params.get("proposals_sha256") == sha and (run.path / row["file"]).is_dir():
            return None
    return f"the proposals page is built from the checked proposals, {checked} (tm organic page proposals)"


# --- decisions ---------------------------------------------------------------------------------------

def decided_page(run: RunFolder) -> dict:
    """The page people decide on and the proposals it was built from: the published folder
    (`state.pages["proposals"]`), else the latest build; its manifest row gives the file and its
    sha256. `{folder, proposals, data}`. Stop when that file is gone or changed since."""
    target = (state.load(run).pages.get(PAGE) or {}).get("folder")
    rows = [r for r in manifest.rows(run) if r["source"] == SOURCE and (target is None or r["file"] == target)]
    if not rows:
        where = f"the published folder {target}" if target else "this run"
        raise Stop(f"No proposals page build of {where} is recorded (tm organic page proposals), so it is unknown "
                   f"which proposals people decided on. Build the page and publish it, then read the decisions; {AGAIN}.")
    row = rows[-1]
    try:
        params = json.loads(row["params"]) if row["params"] else {}
    except ValueError:
        params = {}
    path = run.path / row["parent"]
    if not path.is_file() or params.get("proposals_sha256") != stepchecks.sha256(path):
        raise Stop(f"The page {row['file']} was built from {row['parent']}, which is gone or changed since, so it is "
                   "unknown which proposals people decided on. Build the page again (tm organic page proposals), "
                   f"publish it and let the user decide on it; {AGAIN}.")
    return {"folder": row["file"], "proposals": row["parent"], "data": _read(path, row["parent"])}


_DECISION_KEYS = {"produce": _P + "summary_produce", "later": _P + "summary_later", "skip": _P + "summary_skip",
                  None: _P + "summary_not_decided"}
_FIELD_KEYS = {"output": _P + "summary_output", "platforms": _P + "summary_platforms",
               "answers": _P + "summary_answers", "note": _P + "summary_note"}


class _Words(NamedTuple):
    decisions: dict      # a decision's word (lower case) -> the decision
    fields: dict         # a part's head ("platforms: ") -> the field
    levels: dict         # a level's name (lower case) -> the level


def _words(lang: str = i18n.ENGLISH) -> _Words:
    """The Copy summary's words in English, Polish and `lang` (the page's language)."""
    out = _Words({}, {}, {})
    for code in dict.fromkeys((i18n.ENGLISH, "pl", lang)):
        try:
            tr = i18n.translator(code)
            out.decisions.update({tr(key).lower(): value for value, key in _DECISION_KEYS.items()})
            out.fields.update({f"{tr(key)}: ": value for value, key in _FIELD_KEYS.items()})
            out.levels.update({name.lower(): lid for lid, name in level_names(tr).items()})
        except i18n.Missing:            # a language without the organic table: its pages are built in English
            continue
    return out


_AUTO = ("a–z automatic", "automatycznie a–z")
_GATES = ("gates: ", "bramki: ")


def _how(text: str, line: str, words: _Words) -> dict:
    """The level part of a produce line: a level's name, or the original page's "A–Z" or gates."""
    low = text.strip().lower()
    if low in words.levels:
        return {"level": words.levels[low]}
    if low in _AUTO:
        return {"mode": "auto"}
    for head in _GATES:
        if low.startswith(head):
            return {"mode": "gates", "gates": [g.strip() for g in text.strip()[len(head):].split(",") if g.strip()]}
    raise Stop(f"The Copy summary line {line!r} names the level {text.strip()!r}, which is none of "
               f"{', '.join(sorted(words.levels))}. Ask the user which "
               f"level they want and write the line again; {AGAIN}.")


def _line(rest: str, line: str, words: _Words | None = None) -> dict:
    """One proposal's document from its Copy summary line, after `<ID> <title>: `."""
    words = words or _words()
    parts = rest.split("; ")
    word, _, how = parts[0].partition(", ")
    if word.strip().lower() not in words.decisions:
        raise Stop(f"The Copy summary line {line!r} starts with {word!r}, which is not produce, later, skip or not "
                   f"decided. Ask the user and write the line again; {AGAIN}.")
    doc: dict = {"decision": words.decisions[word.strip().lower()]}
    if how:
        doc |= _how(how, line, words)
    field, values = None, {}
    for i, part in enumerate(parts[1:], 1):
        head = next((h for h in words.fields if part.startswith(h)), None)
        if head is None:
            if field is None:
                raise Stop(f"The Copy summary line {line!r} has a part it cannot read ({part!r}). Write it as the "
                           f"page writes it; {AGAIN}.")
            values[field] += "; " + part
            continue
        field = words.fields[head]
        if field == "note":                     # the last part: a note may hold "; "
            values[field] = "; ".join([part[len(head):], *parts[i + 1:]])
            break
        values[field] = part[len(head):]
    if "output" in values:
        doc["output"] = values["output"].strip()
    if "platforms" in values:
        doc["platforms"] = [x.strip() for x in values["platforms"].split(",") if x.strip()]
    if "answers" in values:
        doc["answers"] = {str(i): a for i, a in enumerate(values["answers"].split(" | "))}
    if "note" in values:
        doc["note"] = values["note"]
    return doc


def parse_summary(text: str, data: dict) -> list[tuple[str, dict]]:
    """The page's "Copy summary" text as page documents `(pid, document)`: one line per proposal,
    `<ID> <title>: <decision>[, <level>]; output: …; platforms: …[; answers: a | b][; note: …]`, in
    English, Polish or the page's language. A line for a proposal is known by its id and title; a line with a proposal's
    id and another title, or two lines for one proposal, is a Stop, and so is a text with none."""
    proposals = [p for p in data.get("proposals") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]
    words = _words(organic_pages.lang_of(data))
    docs: dict[str, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        for p in proposals:
            head = f"{p['id'].upper()} "
            if not line.startswith(head):
                continue
            prefix = f"{head}{p.get('title')}: "
            if not line.startswith(prefix):
                raise Stop(f"The line {line[:80]!r} names {p['id'].upper()} with another title than this page's "
                           f"(“{p.get('title')}”): it is from another page. Ask for the text from this page; {AGAIN}.")
            if p["id"] in docs:
                raise Stop(f"The text has two lines for {p['id'].upper()}, so it is unclear what the user decided. Ask "
                           f"them once and write one line; {AGAIN}.")
            docs[p["id"]] = _line(line[len(prefix):], line, words)
            break
    if not docs:
        raise Stop("The text holds no Copy summary line of this page (each starts with a proposal's id and title, e.g. "
                   f"`M1 <title>: produce, …`). Paste the text as the page gave it, or write the user's answer in that "
                   f"form; {AGAIN}.")
    return list(docs.items())


def _decisions_files(run: RunFolder) -> list[Path]:
    """The decisions files of the proposals page, oldest first (by version)."""
    folder = run.path / WIP
    name = re.compile(rf"^{DECISIONS_STEM}_v(\d+)\.json$")
    found = [(int(m.group(1)), f) for f in folder.glob(f"{DECISIONS_STEM}_v*.json") if folder.is_dir()
             for m in [name.match(f.name)] if m]
    return [f for _, f in sorted(found)]


def take_decisions(run: RunFolder, *, file: Path | None = None, text: Path | None = None) -> dict:
    """Read the decisions taken on the proposals page into `03_wip/decisions_proposals_vNN.json`
    (the module docstring) and stop waiting for them. Default input: the newest saved db answer on
    this page's slug; `text`: the Copy summary text (the user's word in chat)."""
    slug = (state.load(run).pages.get(PAGE) or {}).get("slug")
    if text is None and not slug:
        raise Stop(f"The page's publish is not recorded (tm page published --page {PAGE}), so it is unknown which "
                   "artifact's decisions to read. Record it, read the decisions with an ArtifactData list first, or give the "
                   f"user's answer as Copy summary text with --text; {AGAIN}.")
    decided = decided_page(run)
    data = decided["data"]
    if text is not None:
        source = Path(text)
        docs = parse_summary(source.read_text(encoding="utf-8-sig"), data)
    else:
        source = Path(file) if file is not None else page.saved_answer(run, PAGE, COLLECTION)
        if source is None:
            raise Stop(f"No saved answer holds the decisions of this page ({slug}): read them with an ArtifactData list "
                       f"first (the page's url, collection {COLLECTION}, query.limit 1000; with the older "
                       f"tools, db_list on slug {slug}), then run this again; {AGAIN}.")
        docs = page.db_docs(page.whole_answer(run, PAGE, source, COLLECTION), collection=COLLECTION)
        if not docs:
            raise Stop(EMPTY)
    rows = organic_proposals.decisions(docs, data, organic_proposals.profile_defaults(run, data))
    read = {pid: {k: v for k, v in doc.items() if k != "updated_at"}
            for pid, doc in organic_proposals.newest_docs(docs, data).items()}
    carried = []
    if text is None:
        earlier = page.earlier_decisions(run, _decisions_files(run), decided["folder"], built="folder",
                                         rows="read", command=DECISIONS_SOURCE, shape=dict) or {}
        carried = page.mark_carried(copy.deepcopy(read), earlier)
        for pid in carried:
            rows[pid]["carried"] = True
    rel = _rel(run, source)
    out = run.next_version(WIP, DECISIONS_STEM, "json")
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {"page": PAGE, "proposals": decided["proposals"], "folder": decided["folder"], "from": rel,
            "slug": slug or None, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "chat" if text is not None else "page", "decisions": rows, "read": read, "carried": carried}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, WIP, DECISIONS_SOURCE, parent=rel,
                    params={"page": PAGE, "folder": decided["folder"], "proposals": decided["proposals"]})
    page.clear_await(run, PAGE)
    return {"file": out_rel, "from": rel, "page": PAGE, "folder": decided["folder"], "proposals": decided["proposals"],
            "source": body["source"], "decisions": rows, "carried": carried, "docs": len(docs)}
