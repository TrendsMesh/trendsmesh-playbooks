"""Issue #3 on organic video's pages: every fixed string is a key `organic.<key>` of the English table, the plugin
ships the Polish (data/i18n/pl.yaml), and any other language works once its table is translated. That the English
and Polish pages are byte for byte what they were is the goldens' (test_organic_pages, test_organic_gates,
test_organic_week, test_organic_script)."""

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from tm import i18n, organic, organic_pages, organic_week_delivery
from tm.organic_pages import gate, proposals, script, week
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

SOURCES = [Path(organic_pages.__file__).parent.glob("*.py"),
           [Path(organic_week_delivery.__file__), Path(organic_week_delivery.__file__).with_name("organic_gates.py")]]
PSEUDO = "DE·"


def _organic(table: dict) -> dict:
    return {k: v for k, v in table.items() if k.startswith("organic.")}


def _german(tmp_path) -> None:
    """A complete pseudo-translation into German: each organic string with DE· before it."""
    path = tmp_path / "i18n_de.yaml"
    strings = {k: PSEUDO + v for k, v in _organic(i18n.english()).items()}
    path.write_text(yaml.safe_dump({"lang": "de", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("de", path)


def _frag_keys(frags) -> set[str]:
    return {k for f in frags for k in ((f.keys,) if isinstance(f.keys, str) else f.keys)}


def _week_keys(spec) -> set[str]:
    if isinstance(spec, dict):
        return set().union(*(_week_keys(v) for v in spec.values()))
    return {spec[0] if isinstance(spec, tuple) else spec}


def _used() -> set[str]:
    """Every key the pages' code reads."""
    return (set(organic_pages.LEVELS.values()) | set(organic_pages.GATE_WORDS.values())
            | {k for _, k in organic_pages.WORDING} | {k for _, k in organic_pages.REFERENCE["pl"]}
            | _frag_keys(proposals.FRAGS) | _frag_keys(f for n in (1, 2, 5) for f in proposals.lede_frags(n))
            | set(proposals._DECISION_KEYS.values()) | set(proposals._FIELD_KEYS.values())
            | _frag_keys(gate.FRAGS) | _week_keys(week.LABELS) | {f"organic.week.day_{d}" for d in week.DAYS}
            | {"organic.output"} | set(script.WORDS.values()) | set(organic_week_delivery.WORDS.values()))


def _literals() -> set[str]:
    """The whole keys written in the pages' code."""
    found = set()
    for path in (p for group in SOURCES for p in group):
        found |= set(re.findall(r"[\"'](organic\.[a-z0-9_.]*[a-z0-9_])[\"']", path.read_text(encoding="utf-8")))
    return found


# --- synthetic pages (no account data) ----------------------------------------------------------------

def _proposals(lang):
    def one(pid, risk, trend):
        return {"id": pid, "channel": "c1", "video_type": "Vtq", "title": f"Tq {pid}", "approach": "aq",
                "risk": {"level": risk, "items": ["rq"]}, "product": {"level": "hero", "note": "pq"},
                "cost": {"low": 1.0, "high": 2.0, "note": "cq"}, "length": "15 s", "why": "wq", "beats": ["bq"],
                "recipe": {"production": "prq", "voice": "vq", "music": "mq", "text": "tq"}, "taste": ["qq?"],
                "facts": "fq", "trends": [{"id": trend, "role": "roq", "pick": [0, 1]}]}
    return {"lang": lang, "title": "Zq", "date": "2026-11-11", "store": {"name": "Zorbo", "note": "nq"},
            "already_made": ["aq"], "data_note": "dq", "run": "runs/03-organic-ai-video/2026-11-11_zq",
            "channels": [{"id": "c1", "name": "Zorbo", "niche": "kq"}],
            "proposals": [one("m1", "low", "t1"), one("m2", "medium", "t2"), one("m3", "high", "t3"),
                          one("m4", "low", "t4")]}


KINDS = {"t1": "hook_trend", "t2": "topic_trend", "t3": "sound_trend", "t4": "format_trend"}


def _trends(tid):
    card = {"kind": KINDS[tid], "name": "nq", "reach": {"creators": 12, "videos": 3400, "views": 5600000},
            "status": "rq"}
    return card, [{"url": "https://example.com/v", "creator": "cq", "views": 1200, "hook_source": "sq",
                   "hook_text": "hq", "platform": "tiktok"}] * 2


def _proposals_page(lang, built=None):
    return proposals.render(_proposals(lang), _trends, lambda v: "", level="hands_off", lang=built)


KIT = {"platforms": {"tiktok": {f: f"{f}q" for f in ("title", "caption", "description", "cover", "ai_label", "sound",
                                                     "product", "pinned_comment", "first_comment")}}}


def _gate(lang, gate_name="edit"):
    return {"lang": lang, "title": "Gq", "date": "2026-11-11", "gate": gate_name, "run": "runs/x/zq", "lede": "lq",
            "items": [{"id": "final", "proposal": "pq", "label": "lbq", "question": "qq",
                       "options": [{"id": "v01", "src": "a.mp4", "caption": "cq", "pick": True,
                                    "download": {"src": "a.mp4", "filename": "a.mp4", "label": "dq"}},
                                   {"id": "v02", "src": "b.png", "caption": "c2q"}],
                       "refs": [{"src": "r.png", "caption": "rq"}], "kit": KIT}]}


def _week(lang):
    def idea(i, day):
        return {"id": i, "day": day, "title": f"Tq {i}", "format": "fq", "why": "wq", "trend": "tq",
                "evidence": "https://example.com/e", "cost_video": 1.5, "cost_script": 0, "production": "pq",
                "risk": "low", "time": "18:00", "date": "2026-11-16", "output": "video"}
    return {"lang": lang, "week": "2026-W47", "title": "Wq", "channel": "Zorbo", "budget": 5.0, "rhythm": "rq",
            "platforms": ["tiktok", "youtube"], "note": "nq", "run": "runs/x/wq",
            "slots": [idea("w1", "mon"), idea("w2", "wed")], "reserves": [{**idea("r1", "sun"), "day": None}]}


def _script(lang):
    return {"lang": lang, "id": "M1", "version": "v01", "date": "2026-11-11", "title": "Sq", "channel": "Zorbo",
            "format": "fq", "length": "20 s", "word_count": 30, "goal": "gq", "trends": ["tq"],
            "hook": {"line": "hq", "on_screen": "oq", "why": "wq"},
            "shots": [{"n": 1, "time": "0–3 s", "framing": "frq", "action": "aq", "line": "lq", "on_screen": "osq"}],
            "filming": ["fiq"], "edit": ["eq"], "sound": "sq",
            "kit": {"tiktok": {"title": "tiq", "caption": "caq", "description": "deq", "hashtags": ["#hq"],
                               "ai_label": "alq", "sound": "soq"}},
            "facts": [{"claim": "clq", "source": "srq", "url": "https://example.com/f", "note": "ntq"}],
            "generate_instead": {"note": "gnq", "host_image_prompt": "hpq", "video_prompt": "vpq"}}


def _pages(lang):
    """Each page of the synthetic data in `lang` (as built: the language it is built in, `organic_pages.page_lang`)."""
    md = script.to_md(_script(lang), script.labels(organic_pages.lang_of(_script(lang))))
    return {"proposals": proposals.render(_proposals(lang), _trends, lambda v: "", level="hands_off"),
            **{f"gate_{g}": gate.page_html(_gate(lang, g), lambda s: f"media/{s}")[0]
               for g in ("images", "video", "edit")},
            "week": week.page_html(_week(lang))[0], "script": script.page_html(_script(lang), "M1.md", md)[0],
            "script_md": md}


# --- the table ------------------------------------------------------------------------------------------

def test_every_key_the_pages_read_is_in_the_english_table_and_every_organic_key_is_read():
    en = _organic(i18n.english())
    used = _used() | _literals()
    assert sorted(used - set(en)) == []                       # a key the code reads that the table lacks
    assert sorted(set(en) - used) == []                       # a string no page reads
    assert _literals() <= _used()                             # every key written in the code is one listed above


def test_the_plugin_ships_every_organic_string_in_polish():
    en = _organic(i18n.english())
    shipped = i18n._shipped("pl")
    assert sorted(set(en) - set(shipped)) == []
    assert i18n.problems({k: shipped[k] for k in en}) == []   # the same placeholders and markup as the English
    assert i18n.missing("pl", ["organic"]) == []
    built = i18n.page_lang("pl", "organic")
    assert built.lang == "pl" and built.warning is None
    assert organic_pages.levels("pl") == {"every_step": "Sprawdzaj każdy krok",
                                          "big_calls": "Tylko najważniejsze decyzje", "hands_off": "Bez zatrzymywania"}


def test_a_fragment_is_escaped_for_where_it_sits():
    assert organic_pages.escape('a "b" <c> & \'d\'', "html") == "a &quot;b&quot; &lt;c&gt; &amp; &#x27;d&#x27;"
    assert organic_pages.escape("it's \\ </script> <!--", "js") == "it\\'s \\\\ <\\/script> <\\!--"
    assert organic_pages.escape("`${x}` <b>", "tpl") == "\\`\\${x}\\` &lt;b&gt;"
    assert organic_pages.escape("`${x}`\n", "text") == "\\`\\${x}\\`\\n"


# --- English and Polish -----------------------------------------------------------------------------------

def test_english_and_polish_pages_say_their_language():
    for lang in ("en", "pl"):
        for name, text in _pages(lang).items():
            if name != "script_md":
                assert f'<html lang="{lang}">' in text, (lang, name)
    assert "Organiczne wideo AI · punkt kontrolny: finalny montaż" in _pages("pl")["gate_edit"]
    assert "Przypięty komentarz" in _pages("pl")["gate_edit"]          # the kit's pinned comment, English before


# --- another language with its table ---------------------------------------------------------------------

def _left(page: str) -> list[str]:
    """The organic English strings left on a page outside a translated (DE·) one: each value's parts between its
    placeholders, of words a page's code does not use too (more than one lower-case word)."""
    out = []
    for key, value in _organic(i18n.english()).items():
        for part in re.split(r"\{[^}]*\}", value):
            part = part.strip(" :·()“”„")
            if len(part) < 3 or re.fullmatch(r"[a-z_]+", part):
                continue
            for m in re.finditer(rf"(?<![A-Za-z_.]){re.escape(part)}(?![A-Za-z_(])", page):
                start = max(page.rfind(c, 0, m.start()) for c in "<>'\"`\n")
                if PSEUDO not in page[start + 1:m.start()]:
                    out.append(f"{key}: {part!r} at {page[max(0, m.start() - 40):m.end() + 10]!r}")
    return out


def test_a_translated_language_builds_every_page_in_it(tmp_path):
    _german(tmp_path)
    assert i18n.page_lang("de", "organic").warning is None
    english, german = _pages("en"), _pages("de")
    for name, text in german.items():
        if name != "script_md":
            assert '<html lang="de">' in text, name
        assert _left(text) == [], name
        assert text != english[name], name
    for frags, page_en, page_de in ((proposals.FRAGS + proposals.lede_frags(4), english["proposals"],
                                     german["proposals"]),
                                    (gate.FRAGS, english["gate_edit"] + english["gate_images"],
                                     german["gate_edit"] + german["gate_images"])):
        en_tr, de_tr = i18n.translator("en"), i18n.translator("de")
        for frag in frags:
            shown = frag.english or frag.fill(en_tr)
            if shown in page_en:                                           # on the English page: translated here
                assert frag.fill(de_tr) in page_de, frag
                if not frag.template.startswith(organic_pages.SLOT):
                    assert shown not in page_de, frag
    assert '<p class="lede">DE·4 video ideas for Zorbo (nq), DE·each built on' in german["proposals"]
    assert all(v.startswith(PSEUDO) for v in organic_pages.gate_words("de").values())
    assert all(v.startswith(PSEUDO) for v in organic_week_delivery.words("de").values())
    assert week.labels("de")["run"] == "DE·Run folder: " and week.labels("de")["reserve"] == " (DE·reserve)"


def test_the_copy_summary_is_read_in_the_page_language(tmp_path):
    _german(tmp_path)
    data = _proposals("de")
    docs = proposals.parse_summary("M1 Tq m1: DE·produce, DE·Just the big calls; DE·output: script; "
                                   "DE·platforms: tiktok, youtube; DE·note: a; b\n"
                                   "M2 Tq m2: produce, Check every step; output: video; platforms: tiktok", data)
    assert docs == [("m1", {"decision": "produce", "level": "big_calls", "output": "script",
                            "platforms": ["tiktok", "youtube"], "note": "a; b"}),
                    ("m2", {"decision": "produce", "level": "every_step", "output": "video", "platforms": ["tiktok"]})]
    assert proposals.parse_summary("M1 Tq m1: bez decyzji; platformy: tiktok", data) == [
        ("m1", {"decision": None, "platforms": ["tiktok"]})]                  # Polish is read on every page


# --- a language without its table ---------------------------------------------------------------------------

def test_a_language_without_its_table_builds_english_and_says_so():
    built = organic_pages.page_lang({"lang": "fr"})
    assert built.lang == "en" and built.wanted == "fr" and built.missing
    assert "tm i18n export --lang fr" in built.warning and "French" in built.warning
    english = _pages("en")
    for name, text in _pages("fr").items():
        assert text == english[name], name                                # the English page, as it is
    assert organic._built("Built the page.", {"language_warning": built.warning}) == \
        f"Built the page. {built.warning}"
    assert organic._built("Built the page.", {"language_warning": None}) == "Built the page."


def test_a_page_build_reports_the_warning(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "zq", date(2026, 11, 11), playbook=ORGANIC_VIDEO)
    for name in ("a.png", "r.png"):
        (run.path / name).write_bytes(b"png")
    item = {"id": "images-a", "label": "lq", "options": [{"id": "a", "src": "a.png"}],
            "refs": [{"src": "r.png", "caption": "rq"}]}
    data = {**_gate("fr", "images"), "items": [item]}
    got = gate.build(run, data, page="gate_images")
    assert got["lang"] == "en" and "French" in got["language_warning"]
    text = (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in text and "Organic AI video · check-in: images" in text
    got = gate.build(run, {**data, "lang": "pl"}, page="gate_images")
    assert got["lang"] == "pl" and got["language_warning"] is None


@pytest.mark.parametrize("lang", ["en", "pl"])
def test_the_script_file_name_takes_any_language_tag(lang):
    assert script.NAME.fullmatch(f"03_wip/script_M5_{lang}_v01.json")["lang"] == lang
    assert script.NAME.fullmatch("03_wip/script_M5_pt-BR_v02.json")["lang"] == "pt-BR"
    assert script.NAME.fullmatch("03_wip/script_my_id_de_v01.json")["id"] == "my_id"
