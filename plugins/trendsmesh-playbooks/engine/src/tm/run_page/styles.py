"""Our animation styles on the run page (issue #116): the 2 to 3 suggested styles as playing loops, each with its name
and the agent's one-line why, then a gallery of every style grouped by family (posters; a loop plays on a click),
where picking a style works as picking a suggested one. Shown at the proposals (C2, `organic_plan`) and the style,
voice and music (D2, `organic_video`) check-ins.

    media(ctx, card)                         the style's poster and loop on the page: {"poster", "loop"}
    gallery(ctx)                             every style by family, each with its poster and loop
    suggested_html(...)                      the suggested styles, saving through the shared script's `data-detail`
    gallery_html(...)                        the gallery with a radio per style (D2: one picker on the page)
    browse_html(...), other_html(...)        the gallery drawn once and each picker's list of the others (C2, #129)
    HEAD, TAIL                               the stylesheet and the script, once per page (tm.run_page.static)

The 49 styles are the page's fixed style catalogue (issue #129 part 3): `catalogue_js()` is `assets/static/styles-
<version>.js`, which sets `window.TM_STYLES` (every family and style, its poster and loop) and draws the galleries and
the lists from it, so the page itself holds only where each one goes (`<div class="sty-slot">`, a list's first
option). It is a script that sets a global, never JSON read with fetch(): Chrome refuses a page opened as a local
file a fetch() of its own folder's files. It is loaded after the blocks it draws (`TAIL`) and before the run page's
own script, which then finds every input.

The previews are the library's (`data/styles/previews/`, made by atlas/previews.mjs), copied into the page's folder
(`assets/media/styles/`) once per build: a page reads only its own files. Every style's poster and loop are copied
(about 10 MB), since any of them can be played and picked.
"""

from __future__ import annotations

import json
import shutil

from tm import atlas_prompt
from tm.run_page import static
from tm.run_page.context import Context
from tm.run_page.template import E

FOLDER = "assets/media/styles"
KEYS = tuple(f"organic.proposals.styles_{k}" for k in ("all", "hint", "suggested", "play", "browse", "other", "choose"))


def media(ctx: Context, card: dict) -> dict:
    """The style's poster and loop as the page serves them, copied into the page's folder once."""
    kept = ctx.__dict__.setdefault("_sty_put", {})
    if card["styleId"] not in kept:
        out = {}
        for kind, path in zip(("poster", "loop"), atlas_prompt.preview_files(card)):
            out[kind] = f"{FOLDER}/{path.name}"
            if ctx.folder is not None and path.is_file():
                target = ctx.folder / out[kind]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        kept[card["styleId"]] = out
    return kept[card["styleId"]]


def value(card: dict) -> str:
    """A style as the pages keep it: `<number> <name>` (organic_proposals.style_value)."""
    return f"{card['order']} {card['name']}"


def gallery(ctx: Context) -> list[dict]:
    """Every style grouped by family, the families in the library's order: `[{"family", "styles": [{"value", "name",
    "description", "styleId", "poster", "loop"}]}]`."""
    out: dict[str, list[dict]] = {}
    for s in atlas_prompt.styles():
        out.setdefault(s["category"], []).append({"value": value(s), "name": value(s), "description": s["description"],
                                                  "styleId": s["styleId"], **media(ctx, s)})
    return [{"family": k, "styles": v} for k, v in out.items()]


def catalogue() -> list[dict]:
    """`gallery`'s families and styles as every page serves them (the same in every run): `[{"family", "styles":
    [{"value", "name", "description", "poster", "loop"}]}]`."""
    out: dict[str, list[dict]] = {}
    for s in atlas_prompt.styles():
        poster, loop = atlas_prompt.preview_files(s)
        out.setdefault(s["category"], []).append({"value": value(s), "name": value(s), "description": s["description"],
                                                  "poster": f"{FOLDER}/{poster.name}", "loop": f"{FOLDER}/{loop.name}"})
    return [{"family": k, "styles": v} for k, v in out.items()]


def catalogue_js() -> str:
    """The style catalogue's script (`assets/static/styles-<version>.js`): the catalogue, then `SCRIPT`."""
    data = json.dumps(catalogue(), ensure_ascii=False, separators=(",", ":"))
    return f"window.TM_STYLES = {data};\n{SCRIPT}"


def loop_tag(src: str, poster: str, alt: str) -> str:
    return (f'<video class="sty-loop" src="{E(src)}" poster="{E(poster)}" autoplay muted loop playsinline '
            f'preload="metadata" aria-label="{E(alt)}"></video>')


def _radio(name: str, path: str, val: str, picked: str | None) -> str:
    return (f'<input type="radio" name="{E(name)}" value="{E(val)}" data-detail="{path}"'
            f'{" checked" if val == picked else ""} disabled>')


def _data(value: object) -> str:
    return E(json.dumps(value, ensure_ascii=False))


def suggested_html(name: str, path: str, options: list[dict], picked: str | None) -> str:
    """The suggested styles, each a radio with its loop playing (when it is one of ours), its name and its why.
    `options`: `[{"value", "name", "words", "poster"?, "loop"?}]`."""
    cards = []
    for o in options:
        clip = loop_tag(o["loop"], o.get("poster") or "", o["name"]) if o.get("loop") else ""
        cards.append(f'<label class="sty-card">{_radio(name, path, o["value"], picked)}{clip}'
                     f'<span><b>{E(o["name"])}</b> {E(o.get("words") or "")}</span></label>')
    return f'<div class="sty-pick" role="radiogroup">{"".join(cards)}</div>'


def gallery_html(name: str, path: str, picked: str | None, words: dict, *,
                 taken: set[str] = frozenset(), ids: dict[str, str] | None = None) -> str:
    """Where the catalogue draws every style by family: its poster (a click plays its loop) and a radio to pick it,
    saved like a suggested style's. A style already suggested (`taken`, by value) is shown without a radio, marked as
    suggested above. `ids`: the radio's value per style value where the page saves another id (the taste page's
    option ids)."""
    w = {k: words[k] for k in ("all", "hint", "suggested", "play")}
    return (f'<div class="sty-slot" data-name="{E(name)}" data-path="{path}" data-picked="{E(picked or "")}" '
            f'data-taken="{_data(sorted(taken))}" data-ids="{_data(ids or {})}" data-words="{_data(w)}"></div>')


def browse_html(words: dict) -> str:
    """Where the catalogue draws the gallery once, for a page of several pickers (the proposals, issue #129): every
    style by family, its poster playing its loop on a click, with no radio; each picker names its style in
    `other_html`'s list."""
    w = {k: words[k] for k in ("all", "browse", "play")}
    return f'<div class="sty-slot" data-words="{_data(w)}"></div>'


def other_html(path: str, picked: str | None, words: dict, *, taken: set[str] = frozenset()) -> str:
    """A picker's "another style" list, pointing at the gallery drawn once (`browse_html`): the catalogue fills it
    with every style by family but the suggested ones (`taken`). It saves on the same `data-detail` path as the
    suggested radios, and nothing while nothing is chosen in it (`data-or`), so a ticked suggested style stays the
    pick."""
    return (f'<label class="small soft sty-other">{E(words["other"])}<select data-detail="{path}" data-or '
            f'data-taken="{_data(sorted(taken))}" data-picked="{E(picked or "")}" disabled>'
            f'<option value="">{E(words["choose"])}</option></select></label>')


CSS = """
.sty-pick{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(170px,100%),1fr));gap:10px}
.sty-card,.sty-tile{display:grid;gap:6px;align-content:start;border:2px solid var(--line);border-radius:12px;padding:6px;
cursor:pointer;min-width:0}.sty-card:has(input:checked),.sty-tile:has(input:checked){border-color:var(--ink)}
.sty-card video,.sty-tile img,.sty-tile video{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px;
background:var(--ink);display:block}.sty-all{margin-top:10px}.sty-all summary{cursor:pointer;font-weight:600}
.sty-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(130px,100%),1fr));gap:8px}
.sty-play{padding:0;border:0;background:none;cursor:pointer;display:block;width:100%}
.media video.sty-loop,video.sty-loop{width:min(180px,100%);aspect-ratio:9/16;object-fit:cover;border-radius:8px;background:var(--ink);display:block}
.sty-desc{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.sty-other{display:grid;gap:4px;margin-top:6px}.sty-other select{width:100%;font:inherit;padding:6px;
border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink)}
"""

# The galleries and the lists drawn from the catalogue (`window.TM_STYLES`, set just before this), every text set as
# text, never as markup. A poster in a gallery plays its loop on a click (and stops on the next); the label's radio is
# not ticked by it. A picker's suggested radios and its list are one pick: choosing in one clears the other.
SCRIPT = r"""
(function () {
  const C = window.TM_STYLES || [];
  const json = (s, d) => { try { return JSON.parse(s || ''); } catch (e) { return d; } };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  function tile(s, w, radio, mark, tag) {
    const t = el(tag, 'sty-tile');
    if (radio) t.appendChild(radio);
    const b = el('button', 'sty-play'); b.type = 'button'; b.dataset.loop = s.loop; b.setAttribute('aria-label', w.play + ': ' + s.name);
    const img = el('img'); img.src = s.poster; img.alt = s.name; img.loading = 'lazy'; b.appendChild(img); t.appendChild(b);
    const words = el('span'); words.appendChild(el('b', null, s.name));
    if (mark) { words.appendChild(document.createTextNode(' ')); words.appendChild(el('span', 'pill', w.suggested)); }
    words.appendChild(document.createTextNode(' ')); words.appendChild(el('span', 'small soft sty-desc', s.description));
    t.appendChild(words);
    return t;
  }
  function draw(slot) {
    const w = json(slot.dataset.words, {}), path = slot.dataset.path, taken = new Set(json(slot.dataset.taken, []));
    const ids = json(slot.dataset.ids, {}), picked = slot.dataset.picked || '';
    const d = el('details', path ? 'sty-all' : 'sty-all sty-once');
    d.appendChild(el('summary', null, w.all)); d.appendChild(el('p', 'small soft', path ? w.hint : w.browse));
    C.forEach(g => {
      d.appendChild(el('h4', null, g.family));
      const grid = el('div', 'sty-grid');
      g.styles.forEach(s => {
        const mark = !!path && taken.has(s.value);
        let radio = null;
        if (path && !mark) {
          radio = el('input'); radio.type = 'radio'; radio.name = slot.dataset.name; radio.value = ids[s.value] || s.value;
          radio.dataset.detail = path; radio.checked = radio.value === picked; radio.disabled = true;
        }
        grid.appendChild(tile(s, w, radio, mark, path ? 'label' : 'div'));
      });
      d.appendChild(grid);
    });
    slot.replaceWith(d);
  }
  function fill(list) {
    const taken = new Set(json(list.dataset.taken, [])), picked = list.dataset.picked || '';
    C.forEach(g => {
      const og = el('optgroup'); og.label = g.family;
      g.styles.forEach(s => { if (taken.has(s.value)) return; const o = el('option', null, s.name); o.value = s.value; o.selected = s.value === picked; og.appendChild(o); });
      list.appendChild(og);
    });
    delete list.dataset.taken;
  }
  document.querySelectorAll('div.sty-slot').forEach(draw);
  document.querySelectorAll('select[data-or][data-taken]').forEach(fill);
  if (window.__tmStyles) return; window.__tmStyles = true;
  document.addEventListener('click', e => {
    const b = e.target.closest('button.sty-play'); if (!b) return;
    e.preventDefault();
    const shown = b.querySelector('video');
    if (shown) { const img = document.createElement('img'); img.src = shown.poster; img.alt = shown.getAttribute('aria-label') || ''; shown.replaceWith(img); return; }
    const img = b.querySelector('img'), v = document.createElement('video');
    v.src = b.dataset.loop; v.poster = img ? img.src : ''; v.muted = true; v.loop = true; v.autoplay = true; v.playsInline = true;
    v.setAttribute('aria-label', img ? img.alt : '');
    if (img) img.replaceWith(v); else b.appendChild(v);
    v.play().catch(() => {});
  });
  document.addEventListener('change', e => {
    const t = e.target, box = t.closest ? t.closest('.sty-picker') : null; if (!box) return;
    const list = box.querySelector('select[data-or]'); if (!list) return;
    if (t === list) { if (list.value) box.querySelectorAll('input[type=radio]').forEach(r => { r.checked = false; }); }
    else if (t.type === 'radio' && t.checked) list.value = '';
  }, true);
  document.addEventListener('tm-restored', e => {
    const t = e.target;
    if (t.matches && t.matches('.sty-picker select[data-or]') && t.selectedIndex < 0) t.selectedIndex = 0;
  }, true);
})();
"""

HEAD = static.link("styles.css")      # before the blocks that use the styles
TAIL = static.script("styles.js")     # after them: it draws their galleries and fills their lists


def words(lang: str) -> dict:
    """The gallery's words in the run page's language (organic.proposals.styles_*)."""
    from tm.run_page.words import tx
    out = {k: tx(f"organic.proposals.styles_{k}", lang) for k in ("hint", "suggested", "play", "browse", "other",
                                                                   "choose")}
    return {**out, "all": tx("organic.proposals.styles_all", lang, n=len(atlas_prompt.styles()))}
