"""The shared page template (issue #19): one page per run, in the TrendsMesh look, that grows at every check-in.

    Datasets()                    the page's numbers, each table with its source (hover, CSV download)
    render(model)                 the page's HTML from a model (below); playbook-agnostic

Layout, top to bottom: the top bar (the mark and name, a dark pill with the playbook's name), the "Now" block
(the open stages: what is new, their materials, the decision right under them), the "Already settled" group (one
folded <details> per earlier stage, newest first, its decision a read-only summary with no inputs). Only an open
stage's decision block has inputs, so a click can never save an earlier decision again (the "lost decisions" of
issue #19). A local page (`model["local"]`, no publishing tool) has no inputs at all: its decision blocks say to
answer in chat.

The model is plain data: `{lang, title, playbook, run, updated, local, build, now: [stage], settled: [stage],
datasets}`; a stage is `{key, n, name, title, lede, blocks, decision | record}`. A decision is `{checkin, ask,
question, context, options: [{choice, label, means, recommended}]}`; a record (a settled stage's decision) is
`{label, choice, note, at, by, rule}`. Blocks are listed in `_BLOCKS`. Every text is escaped here: what the agent
wrote and what the run's files hold is data, never markup (a lede's `**bold**` is the one mark-up kept).

The decision is saved in the artifact's db as `decisions/<checkin>` = `{checkin, ask, choice, label, note,
saved_at}`: clicking an option saves it at once, "Save notes" saves only the note. A saved choice is shown again
only on the same question (`ask`), never on a later version of it.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from tm import paths
from tm.run_page.words import label as _label, t

THEME = paths.bundled_data().parent / "assets" / "page"
FONTS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,"
         "300..800&display=swap")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def E(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def bold(text: object) -> str:
    """Escaped text in which `**x**` is bold."""
    return _BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", E(text))


def _script_json(value: object) -> str:
    """JSON safe inside <script>: `</` and `<!--` cannot end or change it."""
    return (json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def fmt(value: object, kind: str = "num") -> str:
    """A number for the page: integers grouped by thin spaces, rates as percentages, others to 2 places."""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if float(value).is_integer() and abs(value) < 1e15:
        return f"{int(value):,}".replace(",", "\u2009")
    return f"{value:,.2f}".replace(",", "\u2009")


_SHOWN = ("sticker", "kind", "sub")    # how a row is shown (a highlighted tile, a rate), kept beside its columns


class Datasets:
    """Every number on the page lives in a dataset with its source (a run-relative file, or run.json)."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, title: str, source: str, columns: list[tuple[str, str, str]], rows: list[dict]) -> str:
        """A new dataset; `columns` are `(key, label, kind)` with kind `text`, `num`, `pct` or `link`. Its id."""
        did = f"d{len(self.items) + 1}"
        self.items[did] = {"id": did, "title": title, "source": source,
                           "columns": [{"key": k, "label": lab, "kind": kind} for k, lab, kind in columns],
                           "rows": [{**{c[0]: r.get(c[0]) for c in columns},
                                     **{k: r[k] for k in _SHOWN if k in r}} for r in rows]}
        return did

    def get(self, did: str) -> dict:
        return self.items[did]


# --- blocks -------------------------------------------------------------------------------------

def _source_line(ds: dict, lang: str) -> str:
    return (f'<div class="src"><span>{E(t("data.source", lang, file=ds["source"]))}</span>'
            f'<button class="csv" type="button" data-set="{E(ds["id"])}">{E(t("data.download_csv", lang))}</button></div>')


def _cell(value: object, kind: str, source: str, lang: str) -> str:
    title = E(t("data.source", lang, file=source))
    if kind == "link":
        url = value if isinstance(value, str) and re.match(r"^https?://[^\s\"'<>]+$", value) else ""
        return f'<td><a href="{E(url)}" target="_blank" rel="noopener">{E(t("data.open", lang))}</a></td>' if url \
            else "<td>—</td>"
    if kind in ("num", "pct"):
        return f'<td class="num" title="{title}">{E(fmt(value, kind))}</td>'
    return f'<td title="{title}">{E("—" if value in (None, "") else value)}</td>'


def _table(b: dict, ds: Datasets, lang: str) -> str:
    d = ds.get(b["data"])
    if not d["rows"]:
        return f'<p class="soft">{E(t("data.empty", lang))}</p>'
    head = "".join(f'<th class="{"num" if c["kind"] in ("num", "pct") else ""}">{E(c["label"])}</th>' for c in d["columns"])
    body = "".join("<tr>" + "".join(_cell(r.get(c["key"]), c["kind"], d["source"], lang) for c in d["columns"]) + "</tr>"
                   for r in d["rows"])
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{_source_line(d, lang)}'


def _tiles(b: dict, ds: Datasets, lang: str) -> str:
    d = ds.get(b["data"])
    title = E(t("data.source", lang, file=d["source"]))
    out = []
    for r in d["rows"]:
        out.append(f'<div class="tile{" sticker" if r.get("sticker") else ""}" title="{title}">'
                   f'<div class="k">{E(r.get("label"))}</div><div class="v">{E(fmt(r.get("value"), r.get("kind") or "num"))}</div>'
                   + (f'<div class="s">{E(r.get("sub"))}</div>' if r.get("sub") else "") + "</div>")
    return f'<div class="tiles">{"".join(out)}</div>{_source_line(d, lang)}'


def _compare(b: dict, ds: Datasets, lang: str) -> str:
    """Two values per row on one scale (the best window as a grey dot, the latest as a pink one)."""
    d = ds.get(b["data"])
    title = E(t("data.source", lang, file=d["source"]))
    rows = []
    for r in d["rows"]:
        a, z = r.get(b["a"]), r.get(b["b"])
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a, z)):
            continue
        top = max(abs(a), abs(z)) * 1.15 or 1
        kind = r.get("kind") or b.get("kind") or "num"
        change = f" ({(z - a) / a * 100:+.0f}%)" if a else ""
        rows.append(f'<div class="cmp" title="{title}"><span>{E(r.get(b["label"]))}</span><div class="scale">'
                    f'<span class="dot a" style="left:{abs(a) / top * 100:.1f}%"></span>'
                    f'<span class="dot b" style="left:{abs(z) / top * 100:.1f}%"></span></div>'
                    f'<span class="num">{E(fmt(a, kind))} → {E(fmt(z, kind))}{E(change)}</span></div>')
    if not rows:
        return f'<p class="soft">{E(t("data.empty", lang))}</p>'
    legend = (f'<div class="legend"><span><i style="background:var(--muted)"></i>{E(b["a_name"])}</span>'
              f'<span><i style="background:var(--pink)"></i>{E(b["b_name"])}</span></div>')
    return f'{legend}<div class="compare">{"".join(rows)}</div>{_source_line(d, lang)}'


def _bars(b: dict, ds: Datasets, lang: str) -> str:
    d = ds.get(b["data"])
    title = E(t("data.source", lang, file=d["source"]))
    vals = [r.get(b["value"]) for r in d["rows"]]
    nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return f'<p class="soft">{E(t("data.empty", lang))}</p>'
    top = max(abs(v) for v in nums) or 1
    kind = b.get("kind") or "num"
    rows = "".join(
        f'<div class="bar" title="{title}"><span>{E(r.get(b["label"]))}</span><div class="track"><div class="fill" '
        f'style="width:{abs(v) / top * 100:.1f}%"></div></div><span class="num">{E(fmt(v, kind))}</span></div>'
        for r, v in zip(d["rows"], vals) if isinstance(v, (int, float)) and not isinstance(v, bool))
    return f'<div class="bars">{rows}</div>{_source_line(d, lang)}'


def media_tag(src: str, alt: str = "") -> str:
    low = src.lower()
    if low.endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg")):
        return f'<audio src="{E(src)}" controls preload="metadata" aria-label="{E(alt)}"></audio>'
    if low.endswith((".mp4", ".mov", ".webm", ".m4v")):
        return f'<video src="{E(src)}" controls playsinline preload="metadata" aria-label="{E(alt)}"></video>'
    return f'<img src="{E(src)}" alt="{E(alt)}" loading="lazy">'


def _media(b: dict, ds: Datasets, lang: str) -> str:
    figs = "".join(f'<figure>{media_tag(i["src"], i.get("caption") or "")}'
                   + (f'<figcaption>{E(i["caption"])}</figcaption>' if i.get("caption") else "") + "</figure>"
                   for i in b["items"])
    return f'<div class="media">{figs}</div>'


def _pair(b: dict, ds: Datasets, lang: str) -> str:
    """Before and after side by side, with one play and seek control for both."""
    figs = "".join(f'<figure>{media_tag(i["src"], i.get("caption") or "")}<figcaption>{E(i.get("caption") or "")}'
                   f'</figcaption></figure>' for i in (b["before"], b["after"]))
    return (f'<div class="pair"><div class="media">{figs}</div><div class="pair-controls">'
            f'<button class="play" type="button" data-play="{E(t("media.play_both", lang))}" '
            f'data-pause="{E(t("media.pause", lang))}">{E(t("media.play_both", lang))}</button>'
            f'<input class="seek" type="range" min="0" max="1000" value="0" aria-label="{E(t("media.seek", lang))}"></div></div>')


def _text(b: dict, ds: Datasets, lang: str) -> str:
    src = f'<div class="src"><span>{E(t("data.source", lang, file=b["source"]))}</span></div>' if b.get("source") else ""
    if b.get("pre"):
        return f'<details><summary>{E(b.get("summary") or t("data.show_text", lang))}</summary><pre class="text">{E(b["text"])}</pre></details>{src}'
    return "".join(f"<p>{bold(p)}</p>" for p in str(b["text"]).split("\n\n") if p.strip()) + src


def _list(b: dict, ds: Datasets, lang: str) -> str:
    return "<ul>" + "".join(f"<li>{bold(i)}</li>" for i in b["items"]) + "</ul>"


def _chips(chips: list[dict]) -> str:
    return '<div class="chips">' + "".join(f'<span class="pill {E(c.get("style") or "")}">{E(c["text"])}</span>'
                                          for c in chips) + "</div>"


def _stack(b: dict, lang: str) -> str:
    parts = [p for p in b.get("parts") or [] if isinstance(p.get("value"), (int, float)) and p["value"] > 0]
    total = sum(p["value"] for p in parts)
    if not total:
        return ""
    bars = "".join(f'<span class="s{i % 3}" style="width:{p["value"] / total * 100:.1f}%" title="{E(p["label"])}: '
                   f'{E(fmt(p["value"]))}"></span>' for i, p in enumerate(parts))
    legend = "".join(f'<span><i class="s{i % 3}"></i>{E(p["label"])} {E(fmt(p["value"]))}</span>' for i, p in enumerate(parts))
    return f'<p class="small">{E(b.get("title") or "")}</p><div class="stack">{bars}</div><div class="legend">{legend}</div>'


def _trend(b: dict, ds: Datasets, lang: str) -> str:
    """One trend card: the template and its meaning, status chips, key numbers, badges, where the hook sits,
    the confirmations, example videos, and whether it is fresh in the market's Ad Library."""
    out = [f'<article class="card"><h3>{E(b["name"])}</h3>']
    if b.get("meaning"):
        out.append(f'<p>{E(b["meaning"])}</p>')
    if b.get("chips"):
        out.append(_chips(b["chips"]))
    if b.get("numbers"):
        out.append(_table({"data": b["numbers"]}, ds, lang))
    if b.get("badges"):
        out.append(_chips(b["badges"]))
    if b.get("placement"):
        out.append(_stack(b["placement"], lang))
    for key in ("confirmations", "videos"):
        if b.get(key):
            out.append(f'<p class="small"><b>{E(t("trend." + key, lang))}</b></p>' + _table({"data": b[key]}, ds, lang))
    if b.get("ad_library"):
        out.append(f'<p class="small">{E(b["ad_library"])}</p>')
    return "".join(out) + "</article>"


_BLOCKS = {"table": _table, "tiles": _tiles, "compare": _compare, "bars": _bars, "media": _media, "pair": _pair,
           "text": _text, "list": _list, "trend": _trend}


def _block(b: dict, ds: Datasets, lang: str) -> str:
    head = f"<h3>{E(b['title'])}</h3>" if b.get("title") else ""
    return f'<div class="block">{head}{_BLOCKS[b["kind"]](b, ds, lang)}</div>'


# --- the decision -------------------------------------------------------------------------------

def _options(d: dict, lang: str, *, inputs: bool) -> str:
    out = []
    for o in d["options"]:
        tag = f'<span class="pill pink tag">{E(t("decision.recommended", lang))}</span>' if o.get("recommended") else ""
        text = f'<span><b>{E(o["label"])}{tag}</b>{E(o.get("means") or "")}</span>'
        if inputs:
            out.append(f'<label class="opt"><input type="radio" name="d-{E(d["checkin"])}" value="{E(o["choice"])}" '
                       f'data-label="{E(o["label"])}" disabled>{text}</label>')
        else:
            out.append(f'<div class="opt"><span>•</span>{text}</div>')
    return f'<fieldset aria-label="{E(d["question"])}">{"".join(out)}</fieldset>'


def _decision(d: dict, lang: str, local: bool) -> str:
    head = (f'<div class="now-head"><span class="pill pink">{E(t("decision.now", lang))}</span>'
            f'<h3>{E(d["question"])}</h3></div>' + (f'<p>{bold(d["context"])}</p>' if d.get("context") else ""))
    if local:
        return (f'<section class="decision" data-checkin="{E(d["checkin"])}">{head}{_options(d, lang, inputs=False)}'
                f'<p class="chat-only">{E(t("decision.answer_in_chat", lang))}</p></section>')
    return (f'<section class="decision" data-checkin="{E(d["checkin"])}" data-ask="{E(d["ask"])}">{head}'
            f'{_options(d, lang, inputs=True)}<label class="small" for="n-{E(d["checkin"])}">{E(t("decision.note", lang))}</label>'
            f'<textarea id="n-{E(d["checkin"])}" disabled></textarea><div class="row"><button class="savebtn" type="button" '
            f'disabled>{E(t("decision.save_notes", lang))}</button><span class="status" role="status">'
            f'{E(t("decision.connecting", lang))}</span></div></section>')


def _record(r: dict, lang: str) -> str:
    rows = [(t("record.picked", lang), r.get("label") or r.get("choice"))]
    if r.get("by") == "rule":
        rows.append((t("record.by_rule", lang), r.get("rule") or ""))
    if r.get("note"):
        rows.append((t("record.note", lang), r["note"]))
    if r.get("at"):
        rows.append((t("record.saved", lang), str(r["at"]).replace("T", " ")[:16]))
    dl = "".join(f"<dt>{E(k)}</dt><dd>{E(v)}</dd>" for k, v in rows)
    return f'<div class="record"><dl>{dl}</dl></div>'


# --- the page -----------------------------------------------------------------------------------

def _stage_body(s: dict, ds: Datasets, lang: str) -> str:
    return "".join(_block(b, ds, lang) for b in s.get("blocks") or [])


def _now(s: dict, ds: Datasets, lang: str, local: bool, updated: str) -> str:
    lede = f'<p class="lede">{bold(s["lede"])}</p>' if s.get("lede") else ""
    return (f'<section class="panel now" id="stage-{E(s["key"])}"><div class="now-head"><span class="pill dark">'
            f'{E(t("now.new", lang))}</span><span class="soft small">{E(t("now.updated", lang, when=updated))}</span>'
            f'<span class="soft small">{E(s["n"])} · {E(s["name"])}</span></div><h1>{E(s["title"])}</h1>{lede}'
            f'{_stage_body(s, ds, lang)}{_decision(s["decision"], lang, local)}</section>')


def _settled(stages: list[dict], ds: Datasets, lang: str) -> str:
    if not stages:
        return ""
    out = [f'<section class="settled"><h2>{E(t("settled.heading", lang, n=len(stages)))}</h2>']
    for s in stages:
        r = s["record"]
        outcome = t("settled.outcome", lang, stage=s["name"], outcome=r.get("label") or r.get("choice"))
        status = t("settled.by_rule", lang) if r.get("by") == "rule" else t("settled.saved", lang)
        lede = f'<p>{bold(s["lede"])}</p>' if s.get("lede") else ""
        title = f'<h3>{E(s["title"])}</h3>' if s.get("title") else ""
        out.append(f'<details class="stage" id="stage-{E(s["key"])}"><summary><span class="n">{E(s["n"])}</span>'
                   f'<span class="what">{E(outcome)}</span><span class="pill ok">{E(status)}</span></summary>'
                   f'<div class="body">{title}{lede}{_stage_body(s, ds, lang)}{_record(r, lang)}</div></details>')
    return "".join(out) + "</section>"


def theme_css() -> str:
    return (THEME / "theme.css").read_text(encoding="utf-8")


def mark_svg() -> str:
    return (THEME / "mark.svg").read_text(encoding="utf-8").strip()


def render(model: dict) -> str:
    lang, ds, local = model.get("lang") or "en", model["datasets"], bool(model.get("local"))
    now = "".join(_now(s, ds, lang, local, model["updated"]) for s in model["now"])
    if not model["now"]:
        now = (f'<section class="panel now"><div class="now-head"><span class="pill dark">{E(t("now.label", lang))}</span>'
               f'<span class="soft small">{E(t("now.updated", lang, when=model["updated"]))}</span></div>'
               f'<h1>{E(t("now.nothing_open", lang))}</h1></section>')
    data = {"lang": lang, "local": local, "build": model["build"],
            "open": [{"checkin": s["decision"]["checkin"], "ask": s["decision"]["ask"]} for s in model["now"]],
            "datasets": ds.items,
            "words": {k: t("decision." + k, lang) for k in ("saving", "saved_at", "save_error", "cannot_save", "ready")}}
    mark = mark_svg()
    return (f'<!doctype html><html lang="{E(lang)}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(model["title"])}</title>'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="{E(FONTS)}">'
            f'<style>{theme_css()}</style></head><body><div class="wrap">'
            f'<header class="top"><span class="brand">{mark}<span>{E(t("top.brand", lang))}</span></span>'
            f'<span class="pill dark">{E(model["playbook"])}</span></header><main>{now}'
            f'{_settled(model["settled"], ds, lang)}</main>'
            f'<footer>{E(t("footer.built", lang, run=model["run"], when=model["updated"]))}</footer></div>'
            f'<script type="application/json" id="tm-page">{_script_json(data)}</script><script>{SCRIPT}</script>'
            f'</body></html>')


def stage_name(group_key: str, lang: str) -> str:
    return _label("stage", group_key, lang)


SCRIPT = r"""
(function () {
  const P = JSON.parse(document.getElementById('tm-page').textContent);
  const W = P.words;
  function csvCell(v) { const s = v == null ? '' : String(v); return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
  function csv(d) {
    const head = d.columns.map(c => csvCell(c.label)).join(',');
    return [head].concat(d.rows.map(r => d.columns.map(c => csvCell(r[c.key])).join(','))).join('\n') + '\n';
  }
  async function use(name) {
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    try { return window.claude && window.claude.use ? await window.claude.use(name) : null; } catch (e) { return null; }
  }
  document.querySelectorAll('button.csv').forEach(b => b.addEventListener('click', async () => {
    const d = P.datasets[b.dataset.set]; if (!d) return;
    const name = (d.title || d.id).replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 60) + '.csv';
    const blob = new Blob(['\ufeff' + csv(d)], {type: 'text/csv;charset=utf-8'});
    const dls = P.local ? null : await use('downloads');
    if (dls) { try { await dls.save({filename: name, data: blob}); return; } catch (e) { if (e && e.code === 'declined') return; } }
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }));
  document.querySelectorAll('.pair').forEach(pair => {
    const v = pair.querySelectorAll('video, audio'), play = pair.querySelector('.play'), seek = pair.querySelector('.seek');
    if (v.length < 2) return;
    const a = v[0], b = v[1], dur = () => Math.max(a.duration || 0, b.duration || 0);
    play.addEventListener('click', () => {
      if (a.paused) { a.play(); b.play(); play.textContent = play.dataset.pause; }
      else { a.pause(); b.pause(); play.textContent = play.dataset.play; }
    });
    seek.addEventListener('input', () => { const s = seek.value / 1000 * dur(); a.currentTime = s; b.currentTime = s; });
    a.addEventListener('timeupdate', () => {
      if (dur()) seek.value = Math.round(a.currentTime / dur() * 1000);
      if (Math.abs(a.currentTime - b.currentTime) > 0.15) b.currentTime = a.currentTime;
    });
    a.addEventListener('ended', () => { b.pause(); play.textContent = play.dataset.play; });
  });

  const blocks = Array.from(document.querySelectorAll('section.decision[data-ask]'));
  if (P.local || !blocks.length) return;
  const when = iso => { try { return new Date(iso).toLocaleTimeString(P.lang, {hour: '2-digit', minute: '2-digit'}); } catch (e) { return iso; } };
  function say(sec, text, err) { const s = sec.querySelector('.status'); s.textContent = text; s.classList.toggle('err', !!err); }
  function readOnly(sec) { sec.querySelectorAll('input, textarea, button').forEach(x => { x.disabled = true; }); say(sec, W.cannot_save); }
  (async () => {
    const db = await use('db'), user = await use('user');
    let owner = null;
    try { owner = user && user.isOwner ? await user.isOwner() : null; } catch (e) { owner = null; }
    if (!db || owner === false) { blocks.forEach(readOnly); return; }
    for (const sec of blocks) {
      const checkin = sec.dataset.checkin, ask = sec.dataset.ask;
      const ref = db.doc('decisions/' + checkin);
      const st = {choice: null, label: null, note: ''};
      const radios = Array.from(sec.querySelectorAll('input[type=radio]')), note = sec.querySelector('textarea');
      const btn = sec.querySelector('.savebtn');
      try {
        const snap = await ref.get();
        const v = snap.exists ? snap.data() : null;
        if (v && v.ask === ask && v.checkin === checkin) {   // a choice made on this very question, never an earlier one
          Object.assign(st, {choice: v.choice || null, label: v.label || null, note: typeof v.note === 'string' ? v.note : ''});
          radios.forEach(r => { r.checked = r.value === st.choice; });
          note.value = st.note;
          say(sec, v.saved_at ? W.saved_at.replace('{time}', when(v.saved_at)) : W.ready);
        } else { say(sec, W.ready); }
      } catch (e) { say(sec, W.ready); }
      let chain = Promise.resolve();
      const save = patch => {
        chain = chain.then(async () => {
          const body = {checkin: checkin, ask: ask, choice: st.choice, label: st.label, note: st.note,
                        saved_at: new Date().toISOString(), ...patch};
          say(sec, W.saving);
          try {
            await ref.set(body); Object.assign(st, patch); say(sec, W.saved_at.replace('{time}', when(body.saved_at)));
          } catch (e) {
            if (e && e.code === 'invalid_argument') { readOnly(sec); return; }
            say(sec, W.save_error.replace('{error}', (e && e.code) || 'error'), true);
          }
        });
        return chain;
      };
      radios.forEach(r => r.addEventListener('change', () => { if (r.checked) save({choice: r.value, label: r.dataset.label}); }));
      btn.addEventListener('click', () => save({note: note.value}));
      sec.querySelectorAll('input, textarea, button').forEach(x => { x.disabled = false; });
    }
  })();
})();
"""
