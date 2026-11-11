"""The Creative brief page in the run's working language (issue #3): every fixed word of brief_page.py and of the
template's script is a `brief.*` key of the string table, the page's `lang` is the language it is built in, and a
language whose table lacks a word builds the page in English and says so.

The brief here is made up and public; its texts are upper case, so any lower-case word left on a page built from a
pseudo-translation (each string upper case, "PL·" before it) is English the table does not cover.
"""

import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

from tm import brief_page, config, i18n
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

SOURCE = Path(brief_page.__file__)


def _concept(cid: str) -> dict:
    return {
        "id": cid, "brief_id": f"B{cid}", "title": f"TITLE {cid}", "one_liner": "ONE LINER", "key_message": "KEY",
        "hypothesis": "HYPOTHESIS", "phone_note": "PHONE NOTE", "for_whom": "FOR WHOM", "trend_line": "TREND LINE",
        "glance": [{"label": "ACCOUNT", "text": "GLANCE", "source": "SRC", "highlight": True}],
        "decision_facts": {"goal": "GOAL", "effort": "EFFORT", "risk": "RISK", "budget": None, "deadline": "1 XII",
                           "approver": None},
        "hook": {"text": "HOOK", "description": "HOOK DESCRIPTION"},
        "beats": [{"t0": 0, "t1": 2.5, "see": "SEE", "hear": "HEAR", "ost": "OST", "ost_strong": True}],
        "length_s": 12, "note": {"title": "NOTE", "text": "NOTE TEXT"},
        "why": [{"quote": "QUOTE", "url": "https://example.com/q", "source_label": "FORUM"}],
        "customer_phrases": [{"phrase": "PHRASE", "used_in": "HOOK", "url": "https://example.com/p"},
                             {"phrase": "WORDS", "used_in": "END", "url": "https://example.com/w", "translated": True,
                              "adapted_from": "SŁOWA <B>"}],
        "copy_from_hook": {"text": "COPY", "evidence": [{"url": "https://example.com/v", "views": "1,2M",
                                                         "caption": "CAPTION"}]},
        "ad_copy": {"primary": "PRIMARY", "headline": "HEADLINE", "button": "BUY"},
        "hooks_to_test": ["HOOK A", "HOOK B"], "casting": "CASTING",
        "creator": {"role": "ROLE", "say_note": "SAY NOTE", "say": [{"moment": "OPEN", "key": "KEY", "line": "LINE"}],
                    "shots": [{"shot": "SHOT", "framing": "CLOSE", "takes": "3"}], "extra_takes": "EXTRA",
                    "look": "LOOK", "send_back": ["RAW"], "deadline": None, "usage": None},
        "editor": [{"label": "CUT", "text": "FAST"}], "media": [{"label": "BUDGET", "text": "SMALL"}],
        "qa": ["CHECK"],
    }


def _brief() -> dict:
    return {
        "meta": {"title": "LUMEN: TWO CONCEPTS", "market": "PL", "language": "PL", "prepared": "2026-11-01",
                 "valid_until": "2026-11-15", "recipients": list(brief_page.ALL_VIEWS),
                 "lede": {"decision": "LEDE"}, "sources_note": "SOURCES", "animatic_note": "ANIMATIC",
                 "product": {"name": "LUMEN", "plain_description": "A LAMP", "plan": ["ON"], "price_note": "PRICE"}},
        "findings": {"items": [{"title": "FINDING", "text": "TEXT"}], "caveat": "CAVEAT"},
        "audience": {"text": "AUDIENCE", "facts": [{"value": "38%", "label": "NURSES"}], "source": "SURVEY"},
        "tone": {"tone": "WARM", "must": ["LAMP"], "never": ["SELL"]},
        "concepts": [_concept("C1"), _concept("C2")],
    }


def _brief_keys() -> dict[str, str]:
    return {k: v for k, v in i18n.english().items() if k.startswith("brief.")}


def _pseudo(text: str) -> str:
    """The string upper case, "PL·" before it; its {placeholders} as they are."""
    return "PL·" + "".join(p if p.startswith("{") else p.upper() for p in re.split(r"(\{[^}]*\})", text))


def _import(tmp_path: Path, strings: dict[str, str]) -> None:
    path = tmp_path / "i18n_pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)


@pytest.fixture
def polish(tmp_path):
    """Every brief string in pseudo-Polish, kept as an imported translation."""
    _import(tmp_path, {k: _pseudo(v) for k, v in _brief_keys().items()})


class _Shown(HTMLParser):
    """Every text node and label (alt, aria-label, placeholder, title) of a page, in any view or state, and the
    string literals of its script."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts, self.literals, self.lang, self._in = [], [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        self.texts += [a[k] for k in brief_page._ViewText.LABELS if a.get(k)]
        if tag in ("script", "style"):
            self._in = tag

    def handle_endtag(self, tag):
        if tag == self._in:
            self._in = None

    def handle_data(self, data):
        if self._in == "script":
            self.literals += re.findall(r"'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`", data)
        elif self._in is None and data.strip():
            self.texts.append(data)


def _shown(text: str) -> _Shown:
    parser = _Shown()
    parser.feed(text)
    parser.close()
    return parser


def _fragments(text: str) -> list[str]:
    """The English words of a string around its placeholders, each with at least three letters."""
    out = [p.strip(" :.,()\"'") for p in re.split(r"\{[^}]*\}", text)]
    return [p for p in out if len(re.findall(r"[A-Za-z]", p)) >= 3]


# --- English stays as it was ------------------------------------------------------------------------------

def test_the_english_page_is_the_default():
    assert brief_page.render(_brief()) == brief_page.render(_brief(), "en")
    text, _ = brief_page.render(_brief())
    assert '<html lang="en">' in text and "Concept 1 of 2" in text and "<b>Key message:</b> KEY" in text
    assert "Customers' own words in this ad" in text and '<li>"PHRASE": HOOK (<a ' in text
    assert 'Budget: <span class="todo">to set</span> · Deadline: 1 XII · Approver: <span class="todo">to set</span>' in text
    assert "const LABEL = { approve: 'Approved', change: 'Changes requested' };" in text
    assert brief_page.body_html(_brief()) == brief_page.body_html(_brief(), tr=i18n.translator("en"))


def test_a_translated_customer_phrase_names_its_original():
    text, _ = brief_page.render(_brief())
    assert ('<li>"WORDS": END <span class="src">(translated from: SŁOWA &lt;B&gt;)</span> (<a ' in text)
    assert '<li>"PHRASE": HOOK (<a ' in text                    # an unmarked phrase is as it was
    brief = _brief()
    brief["concepts"][0]["customer_phrases"][1]["translated"] = False
    assert "translated from" not in brief_page.render(brief)[0].split('id="c2"')[0]


# --- the keys -------------------------------------------------------------------------------------------

def test_every_brief_key_is_used_and_every_key_used_exists():
    used = set(re.findall(r"""["'](brief\.[a-z0-9_]+)["']""", SOURCE.read_text(encoding="utf-8")))
    assert used == set(_brief_keys())


def test_every_template_word_is_in_the_worded_template_as_its_english():
    template = brief_page.worded(brief_page.TEMPLATE.read_text(encoding="utf-8"))
    en = i18n.english()
    for old, key, kind, fills in brief_page.TEMPLATE_WORDS:
        assert old in template, key
        assert brief_page.js_text(en[key], kind, fills) == old, key
    assert brief_page._HTML_LANG in template


def test_a_script_string_is_escaped():
    assert brief_page.js_text("can't </script>\n\\", "js") == "'can\\'t <\\/script>\\n\\\\'"
    assert brief_page.js_text("`{id}` ${x}", "tpl", {"id": "${c}"}) == "`\\`${c}\\` \\${x}`"


# --- a page in another language ----------------------------------------------------------------------

def test_a_page_in_polish_has_no_english_word_of_the_table(polish):
    text, views = brief_page.render(_brief(), "pl")
    assert views == brief_page.ALL_VIEWS
    shown = _shown(text)
    assert shown.lang == "pl"
    everything = shown.texts + shown.literals
    for key, english in _brief_keys().items():
        for fragment in _fragments(english):
            left = [t for t in everything if fragment in t]
            assert not left, f"{key}: {fragment!r} is still on the page ({left[:3]})"
    # the brief's own texts are upper case: a lower-case word in a text or label is English the table lacks
    lower = [t for t in shown.texts if re.search(r"[a-z]{3,}", t)]
    assert not lower, lower
    assert "PL·CONCEPT 1 OF 2" in text and "PL·KEY MESSAGE:" in text
    assert "PL·BUDGET: <span class=\"todo\">PL·TO SET</span>" in text
    assert "const LABEL = { approve: 'PL·APPROVED', change: 'PL·CHANGES REQUESTED' };" in text
    assert "`PL·${c}: ${a} APPROVED, ${ch} CHANGES REQUESTED`" in text and "`PL·${c}: NONE YET`" in text
    assert "'PL·NOT SAVED: THIS COPY CAN\\'T SAVE DECISIONS." in text
    assert "const lines = ['PL·DECISIONS ON \"LUMEN: TWO CONCEPTS\"'];" in text      # the title filled after


def test_the_creator_view_in_polish(polish):
    creator = " ".join(brief_page.view_text(_brief(), "creator", "pl"))
    assert "PL·YOUR PART" in creator and "Your part" not in creator
    assert "Your part" in " ".join(brief_page.view_text(_brief(), "creator"))


def test_a_polish_copied_text_reads_back(polish):
    tr = i18n.translator("pl")
    title = _brief()["meta"]["title"]
    text = "\n".join([tr("brief.copy_header", title=title), f"C1: {tr('brief.approved')} | OK",
                      f"C2: {tr('brief.changes_requested')} | SHORTER", f"C3: {tr('brief.no_decision')}"])
    docs = brief_page.read_decisions(text, title=title, lang="pl")
    assert docs == [{"who": "copied text 1", "decisions": {"C1": {"d": "approve", "n": "OK"},
                                                           "C2": {"d": "change", "n": "SHORTER"}}}]
    english = f'Decisions on "{title}"\nC1: Approved | OK'
    assert brief_page.read_decisions(english, title=title, lang="pl")[0]["decisions"] == {"C1": {"d": "approve", "n": "OK"}}


# --- the language of a run's page ---------------------------------------------------------------------

@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)
    (run.path / config.FILE).write_text(yaml.safe_dump({"languages": {"working": "pl", "market": "pl"}}),
                                        encoding="utf-8")
    brief = run.path / "04_final" / "brief_pack_v01.json"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(json.dumps(_brief()), encoding="utf-8")
    return run


def _page(run, capsys) -> tuple[dict, str]:
    code = main(["brief", "page", "--run", str(run.path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    return out, (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")


def test_a_polish_run_builds_its_page_in_polish(run, polish, capsys):
    out, text = _page(run, capsys)
    assert out["lang"] == "pl" and "language_warning" not in out
    assert '<html lang="pl">' in text and "PL·DECISIONS SO FAR" in text
    assert "English" not in out["message"]


def test_an_incomplete_table_builds_in_english_and_says_so(run, tmp_path, capsys):
    strings = {k: _pseudo(v) for k, v in _brief_keys().items()}
    del strings["brief.save_decision"]
    _import(tmp_path, strings)
    got = i18n.page_lang("pl", "brief")
    assert got.lang == "en" and got.missing == ("brief.save_decision",) and got.warning
    out, text = _page(run, capsys)
    assert out["lang"] == "en" and out["language_warning"] == got.warning
    assert got.warning in out["message"] and "tm i18n export --lang pl" in out["message"]
    assert '<html lang="en">' in text and "Save decision" in text and "PL·" not in text


def test_a_run_without_a_language_builds_in_english(run, capsys):
    (run.path / config.FILE).unlink()
    out, text = _page(run, capsys)
    assert out["lang"] == "en" and "language_warning" not in out and '<html lang="en">' in text


def test_the_print_mode_and_the_pdf_buttons_in_polish(polish):
    """Issue #10's print mode (the PDFs are printed from it) and its download buttons, in the page's language."""
    brief = _brief()
    stills = {c["animatic"]["9x16"]: ["s1.jpg", "s2.jpg"] for c in brief["concepts"] if c.get("animatic")}
    text, _ = brief_page.render(brief, "pl", stills=stills)
    shown = _shown(text)
    assert shown.lang == "pl" and "body.print" in text
    assert "PL·FULL REPORT" in text and "PL·VIEW: PL·CREATOR" in text
    if stills:
        assert "PL·STILLS FROM THE ANIMATIC." in text
    for name in ("banner_full", "stills"):
        assert brief_page.PDF_WORDS[name] not in text
    pdfs = {"full": "pdf/full.pdf", **{v: f"pdf/{v}.pdf" for v in brief_page.ALL_VIEWS}}
    text, _ = brief_page.render(brief, "pl", pdfs=pdfs)
    assert _shown(text).lang == "pl"
    assert "PL·DOWNLOAD FULL REPORT (PDF)" in text and "PL·DOWNLOAD PL·DECISION MAKER VIEW (PDF)" in text
    assert brief_page.E(brief_page.PDF_WORDS["hint"]) not in text and "PL·SHARE THIS PAGE" in text
    english, _ = brief_page.render(brief, pdfs=pdfs)
    assert '<html lang="en">' in english and brief_page.E(brief_page.PDF_WORDS["hint"]) in english
