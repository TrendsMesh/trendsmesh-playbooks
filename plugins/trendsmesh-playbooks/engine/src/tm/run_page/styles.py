"""Our animation styles on the run page (issue #116): the 2 to 3 suggested styles as playing loops, each with its name
and the agent's one-line why, then a gallery of every style grouped by family (posters; a loop plays on a click),
where picking a style works as picking a suggested one. Shown at the proposals (C2, `organic_plan`) and the style,
voice and music (D2, `organic_video`) check-ins.

    media(ctx, card)                         the style's poster and loop on the page: {"poster", "loop"}
    gallery(ctx)                             every style by family, each with its poster and loop
    suggested_html(...), gallery_html(...)   the inputs, saving through the shared script's `data-detail` paths
    ASSETS                                   the stylesheet and the script, once per page

The previews are the library's (`data/styles/previews/`, made by atlas/previews.mjs), copied into the page's folder
(`assets/media/styles/`) once per build: a page reads only its own files. Every style's poster and loop are copied
(about 10 MB), since any of them can be played and picked.
"""

from __future__ import annotations

import shutil

from tm import atlas_prompt
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


def loop_tag(src: str, poster: str, alt: str) -> str:
    return (f'<video class="sty-loop" src="{E(src)}" poster="{E(poster)}" autoplay muted loop playsinline '
            f'preload="metadata" aria-label="{E(alt)}"></video>')


def _radio(name: str, path: str, val: str, picked: str | None) -> str:
    return (f'<input type="radio" name="{E(name)}" value="{E(val)}" data-detail="{path}"'
            f'{" checked" if val == picked else ""} disabled>')


def suggested_html(name: str, path: str, options: list[dict], picked: str | None) -> str:
    """The suggested styles, each a radio with its loop playing (when it is one of ours), its name and its why.
    `options`: `[{"value", "name", "words", "poster"?, "loop"?}]`."""
    cards = []
    for o in options:
        clip = loop_tag(o["loop"], o.get("poster") or "", o["name"]) if o.get("loop") else ""
        cards.append(f'<label class="sty-card">{_radio(name, path, o["value"], picked)}{clip}'
                     f'<span><b>{E(o["name"])}</b> {E(o.get("words") or "")}</span></label>')
    return f'<div class="sty-pick" role="radiogroup">{"".join(cards)}</div>'


def gallery_html(name: str, path: str, groups: list[dict], picked: str | None, words: dict, *,
                 taken: set[str] = frozenset(), ids: dict[str, str] | None = None) -> str:
    """Every style by family: its poster (a click plays its loop) and a radio to pick it, saved like a suggested
    style's. A style already suggested (`taken`, by value) is shown without a radio, marked as suggested above.
    `ids`: the radio's value per style value where the page saves another id (the taste page's option ids)."""
    ids = ids or {}
    parts = []
    for g in groups:
        tiles = []
        for s in g["styles"]:
            taken_here = s["value"] in taken
            radio = "" if taken_here else _radio(name, path, ids.get(s["value"], s["value"]), picked)
            mark = f' <span class="pill">{E(words["suggested"])}</span>' if taken_here else ""
            tiles.append(f'<label class="sty-tile">{radio}<button type="button" class="sty-play" '
                         f'data-loop="{E(s["loop"])}" aria-label="{E(words["play"])}: {E(s["name"])}">'
                         f'<img src="{E(s["poster"])}" alt="{E(s["name"])}" loading="lazy"></button>'
                         f'<span><b>{E(s["name"])}</b>{mark} <span class="small soft sty-desc">{E(s["description"])}</span>'
                         f'</span></label>')
        parts.append(f'<h4>{E(g["family"])}</h4><div class="sty-grid">{"".join(tiles)}</div>')
    return (f'<details class="sty-all"><summary>{E(words["all"])}</summary>'
            f'<p class="small soft">{E(words["hint"])}</p>{"".join(parts)}</details>')


def _tiles(styles: list[dict], words: dict) -> str:
    return "".join(f'<div class="sty-tile"><button type="button" class="sty-play" data-loop="{E(s["loop"])}" '
                   f'aria-label="{E(words["play"])}: {E(s["name"])}"><img src="{E(s["poster"])}" alt="{E(s["name"])}" '
                   f'loading="lazy"></button><span><b>{E(s["name"])}</b> <span class="small soft sty-desc">'
                   f'{E(s["description"])}</span></span></div>' for s in styles)


def browse_html(groups: list[dict], words: dict) -> str:
    """The gallery drawn once for a page of several pickers (the proposals, issue #129): every style by family, its
    poster playing its loop on a click, with no radio; each picker names its style in `other_html`'s list."""
    parts = "".join(f'<h4>{E(g["family"])}</h4><div class="sty-grid">{_tiles(g["styles"], words)}</div>'
                    for g in groups)
    return (f'<details class="sty-all sty-once"><summary>{E(words["all"])}</summary>'
            f'<p class="small soft">{E(words["browse"])}</p>{parts}</details>')


def other_html(path: str, groups: list[dict], picked: str | None, words: dict, *,
               taken: set[str] = frozenset()) -> str:
    """A picker's "another style" list, pointing at the gallery drawn once (`browse_html`): every style by family
    but the suggested ones (`taken`), saved on the same `data-detail` path as the suggested radios. It saves nothing
    while nothing is chosen in it (`data-or`), so a ticked suggested style stays the pick."""
    groups_ = "".join(
        f'<optgroup label="{E(g["family"])}">'
        + "".join(f'<option value="{E(s["value"])}"{" selected" if s["value"] == picked else ""}>{E(s["name"])}</option>'
                  for s in g["styles"] if s["value"] not in taken) + "</optgroup>" for g in groups)
    return (f'<label class="small soft sty-other">{E(words["other"])}<select data-detail="{path}" data-or disabled>'
            f'<option value="">{E(words["choose"])}</option>{groups_}</select></label>')


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

# A poster in the gallery plays its loop on a click (and stops on the next); the label's radio is not ticked by it.
SCRIPT = r"""
(function () {
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
  // a picker's suggested radios and its "another style" list (the gallery drawn once): one pick at a time
  document.addEventListener('change', e => {
    const el = e.target, box = el.closest ? el.closest('.sty-picker') : null; if (!box) return;
    const list = box.querySelector('select[data-or]'); if (!list) return;
    if (el === list) { if (list.value) box.querySelectorAll('input[type=radio]').forEach(r => { r.checked = false; }); }
    else if (el.type === 'radio' && el.checked) list.value = '';
  }, true);
  document.addEventListener('tm-restored', e => {
    const el = e.target;
    if (el.matches && el.matches('.sty-picker select[data-or]') && el.selectedIndex < 0) el.selectedIndex = 0;
  }, true);
})();
"""

ASSETS = f"<style>{CSS}</style><script>{SCRIPT}</script>"


def words(lang: str) -> dict:
    """The gallery's words in the run page's language (organic.proposals.styles_*)."""
    from tm.run_page.words import tx
    out = {k: tx(f"organic.proposals.styles_{k}", lang) for k in ("hint", "suggested", "play", "browse", "other",
                                                                   "choose")}
    return {**out, "all": tx("organic.proposals.styles_all", lang, n=len(atlas_prompt.styles()))}
