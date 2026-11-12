"""Organic video's pages (playbook 03): ports of the handoff's page builders (`tools/pb3/`), one module each.

    proposals   the proposals page (C2), `tm organic page proposals`
    script      the script to film (E3), `tm organic page script`
    gate        the check-in pages (F1 images, F2 takes) and the delivery page (G4), `tm organic page gate|delivery`;
                the week's delivery page (I4, `tm organic deliver-week`)
    week        the week plan (I2), `tm organic page week`

Shared here:
- `CAPABILITIES[page]`: what each page declares as the `capabilities` of its publish (the Artifact
  tool's; with the older tools, `declare_capabilities` after the first publish). A page's db holds one collection; its rules
  let the owner read and write that collection and every document in it (PB02's rule shape,
  `brief_page.CAPABILITIES`). `downloads` is the original's own (`window.claude.use('downloads')` in
  gate_page.py and script_page.py). The live check against `describe_capabilities` is acceptance's
  (fixtures/organic/README.md).
- The words (issue #3). Every fixed string of these pages is a key `organic.<key>` of the one English table
  (data/i18n/en.yaml); the plugin ships the Polish (data/i18n/pl.yaml), and any other language works once its
  table is translated (`tm i18n`). A page is built in `page_lang(data)`: the data file's `lang` (the run's working
  language, which the checks hold it to) when its table has every organic key, else English with a `warning`
  (`i18n.page_lang`), which each page command shows as `language_warning`. `lang_of(data)` is that language.
  `levels(lang)` names the levels (plan Global Constraints), `gate_words(lang)` the titles, ledes, questions,
  labels and captions `tm.organic_gates` writes into the check-in and delivery pages. `value(stored, kind, lang)`
  shows the run's data in the page language (the product level, a trend's status, OV4's risk items); the run
  files keep the stored value.
- `WORDING`: the original's visible English strings -> the plugin's (plan Decision 10: "check-in", never "gate";
  the levels in place of its "A–Z"; issue #2: a page that cannot save says to choose in chat), each as the key
  whose English it becomes. The builders of the proposals and check-in pages make the original's English page;
  `localize` applies `WORDING`, then, in another language, puts each `Frag`'s text in that language in place of
  its English (escaped for where it sits).
- `worded(page, lang)`: a page of the reference tool (`tools/pb3/`) as the plugin builds it: `WORDING`, then the
  reference tool's own Polish words (`REFERENCE`) -> the plugin's Polish, and the stored values it shows in the
  plugin's words (`value`). Only the equality tests use it, on the goldens the reference tool made.
- `POST_NOTE`: under the platform ticks of the proposals and delivery pages, labelled "Posting kit for" (issue #91:
  the original's "Post to" read as if the plugin posts the video). `worded` puts both in a reference page's row.
- `CSS` (pages.css): the reference pages' stylesheet, verbatim.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import NamedTuple

from tm import i18n

CSS = (Path(__file__).parent / "pages.css").read_text(encoding="utf-8")
AREA = "organic"                      # the pages' keys in the string table: organic.<key>
SLOT = "§"                            # where a Frag's text sits (§0, §1 … for several)
POST_NOTE = "You post the video yourself: the plugin posts nothing. Untick a platform you do not want a posting kit for."


def _db(*collections: str) -> dict:
    return {"rules": [{"path": c, "read": "owner", "write": "owner"} for c in collections]}


CAPABILITIES: dict[str, dict] = {
    "proposals": {"db": _db("decisions"), "user": {"scopes": ["profile"]}},
    "gate": {"db": _db("gate_images", "gate_video", "gate_edit"), "user": {"scopes": ["profile"]}, "downloads": {}},
    "script": {"downloads": {}},
    "week": {"db": _db("week"), "user": {"scopes": ["profile"]}},
}


# --- the page language ----------------------------------------------------------------------------------

def page_lang(data: dict) -> i18n.PageLang:
    """The language a page of `data` is built in: its `lang` (the run's working language) when that language's
    table has every organic key, else English, with `.warning` to show the user (`i18n.page_lang`)."""
    return i18n.page_lang(data.get("lang") if isinstance(data, dict) else None, AREA)


def lang_of(data: dict) -> str:
    """The language a page of `data` is built in (`page_lang(data).lang`)."""
    return page_lang(data).lang


def translator(lang: str | i18n.Translator) -> i18n.Translator:
    return lang if isinstance(lang, i18n.Translator) else i18n.translator(lang)


LEVELS = {"every_step": "organic.level_every_step", "big_calls": "organic.level_big_calls",
          "hands_off": "organic.level_hands_off"}


def levels(lang: str | i18n.Translator) -> dict[str, str]:
    """The levels' names in `lang`, named exactly as the plugin names them (plan Global Constraints)."""
    tr = translator(lang)
    return {level: tr(key) for level, key in LEVELS.items()}


GATE_WORDS = {name: f"organic.gate.{name}" for name in (
    "title_images", "title_video", "title_edit", "lede_images", "lede_video", "lede_edit", "proposal", "label_final",
    "q_final", "label_images", "q_images", "label_takes", "q_takes", "label_voiceover", "q_voiceover",
    "label_storyboard", "q_storyboard", "label_animation", "q_animation", "label_motion", "q_motion", "cap_final",
    "cap_cover", "cap_packshot", "cap_host", "cap_evidence", "cap_still", "cap_contact", "dl_video", "dl_cover",
    "cover_file", "qa_pass", "qa_fails", "qa_findings", "qa_none")}


def gate_words(lang: str | i18n.Translator) -> dict[str, str]:
    """What `tm.organic_gates` writes into the check-in and delivery pages, in `lang` (placeholders unfilled)."""
    tr = translator(lang)
    return {name: tr(key) for name, key in GATE_WORDS.items()}


# --- the run's data as stored, in the page language -----------------------------------------------------

_V = "organic.value."
STATUS_KEY = {s: f"{_V}status_{s}" for s in ("confirmed", "unconfirmed", "contradicted")}


def value_keys(kind: str) -> dict[str, str]:
    """The stored values of `kind` (`product`: OV5's product levels; `status`: a trend's; `risk`: OV4's items;
    `production`: a production type) -> their keys of the string table."""
    from tm import organic_proposals   # it reads the pages' data, not their words

    if kind == "product":
        return {level: _V + "product_" + level.replace(" ", "_") for level in organic_proposals.PRODUCT_LEVELS}
    if kind == "risk":
        return {item: f"{_V}risk_{item}" for item in organic_proposals.RISK_ITEMS}
    if kind == "status":
        return dict(STATUS_KEY)
    if kind == "production":   # after "in" (the risk's origin, issue #87)
        return {t: f"{_V}production_{t}" for t in organic_proposals.PRODUCTIONS}
    raise KeyError(kind)


def value(stored, kind: str, lang: str | i18n.Translator):
    """A value of the run's data (`value_keys(kind)`) in `lang`, else as it is stored. The run files keep the
    stored value; a product level is read as the checks read it (`soft_mention`, ExampleEdu's "nie występuje")."""
    keys = value_keys(kind)
    if kind == "product" and isinstance(stored, str):
        from tm import organic_proposals
        key = keys.get(organic_proposals.PRODUCT_WORDS.get(stored.strip().lower().replace("_", " "), ""))
    else:
        key = keys.get(stored) if isinstance(stored, str) else None
    return translator(lang)(key) if key else stored


# --- the words on a built page ---------------------------------------------------------------------------

def escape(text: str, where: str) -> str:
    """`text` for where it sits: `html` (text or an attribute), `js` (a '…' string in a script), `tpl` (a JS
    template literal set as HTML) or `text` (a JS template literal's plain text)."""
    if where in ("html", "tpl"):
        text = html.escape(text, quote=True)
    if where in ("js", "tpl", "text"):
        text = text.replace("\\", "\\\\").replace("\n", "\\n")
        text = text.replace("'", "\\'") if where == "js" else text.replace("`", "\\`").replace("${", "\\${")
        text = text.replace("</", "<\\/").replace("<!--", "<\\!--")
    return text


class Frag(NamedTuple):
    """A fixed fragment of a built page: `template` with SLOT where the text of `keys` sits (§0, §1 … for several
    keys), escaped for `where` (`escape`). `english` is the English page's own fragment where its code differs from
    the template's (filled from the keys, it is used for the other languages only); `values` fill the keys'
    placeholders. With a `count`, each key is a count of the table (`tr.plural`), in the form that count takes."""
    template: str
    keys: str | tuple[str, ...]
    where: str = "html"
    english: str | None = None
    values: dict | None = None
    count: int | None = None

    def fill(self, tr: i18n.Translator) -> str:
        keys = (self.keys,) if isinstance(self.keys, str) else self.keys
        values = self.values or {}
        words = [escape(tr(k, **values) if self.count is None else tr.plural(k, self.count, **values), self.where)
                 for k in keys]
        if len(words) == 1:
            return self.template.replace(SLOT, words[0])
        out = self.template
        for i, word in enumerate(words):
            out = out.replace(f"{SLOT}{i}", word)
        return out


# The original's English -> the key whose English it becomes. Longer strings first: each is a part of the next.
WORDING: list[tuple[str, str]] = [
    # the check-in and delivery pages' eyebrow (the original's "gate: <gate>")
    ("Organic AI video · gate: edit", "organic.gate.eyebrow_edit"),
    ("Organic AI video · gate: images", "organic.gate.eyebrow_images"),
    ("Organic AI video · gate: video", "organic.gate.eyebrow_video"),
    # the proposals page's hint under Hands-off (the original's "A–Z")
    ("A–Z: Claude produces the whole video without stopping. While we test, the exact cost is still confirmed once "
     "before anything is paid.", "organic.proposals.hands_off_hint"),
    # A page that cannot save (opened as a local file, or without page storage) says to choose in chat, never that
    # the choices are saved or read from it (issue #2).
    ("Mark each proposal below. Choices save as you click; when you are done, write “ready” to Claude in the chat "
     "and it reads them from this page.", "organic.proposals.hint"),
    ("Pick an option where there is a choice, then Accept, Redo (write what to change) or Drop. Choices save as you "
     "click; write “ready” to Claude in the chat when done.", "organic.gate.note"),
    ("Saved in this browser only (page storage not reachable)", "organic.not_saved_unreachable"),
    ("Saved in this browser only", "organic.not_saved"),
    ("Page storage not reachable; choices kept in this browser", "organic.storage_unreachable"),
    ("No access to page storage; choices stay in this browser", "organic.week.no_db"),
]

# The reference tool's own Polish (its pages' table) -> the key whose Polish it becomes, for its goldens (`worded`).
REFERENCE: dict[str, list[tuple[str, str]]] = {"pl": [
    ("Organiczne wideo AI · bramka: finalny montaż", "organic.gate.eyebrow_edit"),
    ("Organiczne wideo AI · bramka: obraz", "organic.gate.eyebrow_images"),
    ("Organiczne wideo AI · bramka: wideo", "organic.gate.eyebrow_video"),
    ("A–Z: Claude robi cały film bez zatrzymywania się. W fazie testów dokładny koszt i tak potwierdzasz raz, zanim "
     "cokolwiek zostanie opłacone.", "organic.proposals.hands_off_hint"),
    ("Oznacz każdą propozycję poniżej. Wybory zapisują się od razu; gdy skończysz, napisz w czacie „gotowe”, a Claude "
     "odczyta je z tej strony.", "organic.proposals.hint"),
    ("Wybierz opcję tam, gdzie jest wybór, potem Akceptuj, Popraw (napisz, co zmienić) albo Odrzuć. Wybory zapisują "
     "się od razu; gdy skończysz, napisz w czacie „gotowe”.", "organic.gate.note"),
    ("Zapisane tylko w tej przeglądarce (brak dostępu do zapisu strony)", "organic.not_saved_unreachable"),
    ("Zapisane tylko w tej przeglądarce", "organic.not_saved"),
    ("Brak dostępu do zapisu strony; wybory zostają w tej przeglądarce", "organic.storage_unreachable"),
]}


def localize(page: str, lang: str | i18n.Translator, frags: list[Frag]) -> str:
    """The original's English page in `lang`: `WORDING` applied, then, in another language, each of `frags` in
    `lang` in place of its English, in order; the `<html lang>` is `lang`'s."""
    en = i18n.translator(i18n.ENGLISH)
    for old, key in WORDING:
        page = page.replace(old, en(key))
    tr = translator(lang)
    if not i18n.is_english(tr.lang):
        for frag in frags:
            page = page.replace(frag.english or frag.fill(en), frag.fill(tr))
    return page.replace('<html lang="en">', f'<html lang="{i18n.html_lang(tr.lang)}">', 1)


def worded(page: str, lang: str) -> str:
    """A page of the reference tool as the plugin builds it: `WORDING`, then (a Polish page) the reference tool's
    Polish words -> the plugin's (`REFERENCE`, and the proposals page's lede, which the reference tool leaves in
    English)."""
    en = i18n.translator(i18n.ENGLISH)
    for old, key in WORDING:
        page = page.replace(old, en(key))
    page = _platform_rows(page, en if lang not in REFERENCE else i18n.translator(lang))
    if lang not in REFERENCE:
        return page
    tr = i18n.translator(lang)
    from tm.organic_pages import proposals
    pairs = [*((old, tr(key)) for old, key in REFERENCE[lang]),
             *((f.english or f.fill(en), f.fill(tr)) for n in range(1, 10) for f in proposals.lede_frags(n))]
    for old, new in pairs:
        page = page.replace(old, new)
    return _stored_values(page, tr)


# A reference page's platform row: its label (the original's "Post to", its Polish "Publikuj na") and ticks.
_PLATFORM_ROW = re.compile(r'(<div class="row"( id="pfs-[^"]*")?><span class="lbl">)(Post to|Publikuj na)(</span>.*?)'
                           r'(</div>)', re.S)


def _platform_rows(page: str, tr: i18n.Translator) -> str:
    """A reference page's platform rows as the plugin builds them: "Posting kit for" and `POST_NOTE` (a proposal's
    row a `hint`, the delivery page's a `note`), in `tr`'s language."""
    label, note = escape(tr("organic.post_to"), "html"), escape(tr("organic.post_note"), "html")

    def row(m: re.Match) -> str:
        shown = f'<p class="hint">{note}</p>' if m.group(2) else f'<p class="note" style="flex-basis:100%">{note}</p>'
        return m.group(1) + label + m.group(4) + shown + m.group(5)

    return _PLATFORM_ROW.sub(row, page)


_CHIP = re.compile(r'(<span class="chip">[^<]*<b>)([^<]*)(</b></span>)')
_RECIPE = re.compile(r"(<dd><b>)([^<]*)(</b>: )")
_TSTATS = re.compile(r'(<div class="tstats">)([^<]*)(</div>)')


def _stored_values(page: str, tr: i18n.Translator) -> str:
    """A reference page's stored values as the plugin shows them (`value`): the product level of a card's chip and
    of the recipe, a trend's status (the fourth part of its stats line)."""
    def shown(text: str, kind: str) -> str:            # as the page has it, unless the plugin translates it
        stored = html.unescape(text)
        got = value(stored, kind, tr)
        return text if got == stored else escape(str(got), "html")

    def product(m: re.Match) -> str:
        return m.group(1) + shown(m.group(2), "product") + m.group(3)

    def stats(m: re.Match) -> str:
        parts = m.group(2).split(" · ")
        if len(parts) > 3:
            parts[3] = shown(parts[3], "status")
        return m.group(1) + " · ".join(parts) + m.group(3)

    return _TSTATS.sub(stats, _RECIPE.sub(product, _CHIP.sub(product, page)))

