"""Issue #3 on organic video's pages: every fixed string is a key `organic.<key>` of the English table, the plugin
ships the Polish (data/i18n/pl.yaml), and any other language works once its table is translated. That the English
and Polish pages are byte for byte what they were is the goldens' (test_organic_pages, test_organic_gates,
test_organic_week, test_organic_script)."""

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from tm import i18n, kit, organic, organic_pack, organic_pages, organic_qa, organic_week_delivery
from tm.organic_pages import gate, proposals, script, week
from tm.playbooks import ORGANIC_VIDEO
from tm.run_page import organic_plan, organic_video
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
            | set(proposals._DECISION_KEYS.values()) | set(proposals._FIELD_KEYS.values()) | set(proposals.LEAD_KEYS.values()) | set(proposals.ADDED.values())
            | _frag_keys(gate.FRAGS) | _week_keys(week.LABELS) | {week.META} | {f"organic.week.day_{d}" for d in week.DAYS}
            | {"organic.output"} | set(script.WORDS.values()) | set(organic_week_delivery.WORDS.values())
            | {f"organic.kit_md.{label}" for label in kit.LABELS} | _pack_md_keys() | _qa_keys()
            | {k for kind in ("product", "risk", "status", "production")
               for k in organic_pages.value_keys(kind).values()}
            | _choice_keys() | organic_video.keys() | organic_plan.keys() | {organic_pages.PLAYBOOK_KEY})



def _choice_keys() -> set[str]:
    """The keys of the pages of choices (issue #83): choices' `_C + "<key>"`, the intake's and the taste page's
    `t("<key>")`, and the names they build."""
    from tm.organic_pages import choices, intake, models, taste

    def found(module, pattern: str) -> set[str]:
        return set(re.findall(pattern, Path(module.__file__).read_text(encoding="utf-8")))
    keys = {choices._C + k for k in found(choices, r"""_C \+ ["']([a-z_]+)["']""") if not k.endswith("_")}
    keys |= {choices._C + f"page_{p}" for p in choices.PAGES} | {choices._C + k for k in choices.JS_WORDS}
    keys |= {intake._I + k for k in found(intake, r"""\bt\(["']([a-z_]+)["']""")}
    keys |= {intake._I + f"resolution_{r}" for r in intake.RESOLUTIONS}
    keys |= {models._M + k for k in found(models, r"""\bt\(["']([a-z_]+)["']""")}
    keys |= {models._M + f"{kind}_{task}" for kind in ("task", "hint") for task in models.TASKS}
    keys |= {models._M + f"group_{g}" for g in models.GROUPS}
    return keys | {taste._T + k for k in found(taste, r"""\bt\(["']([a-z_]+)["']""")}


def _qa_keys() -> set[str]:
    """The rubric's sentences organic_qa reads: _Q + "<key>"."""
    code = Path(organic_qa.__file__).read_text(encoding="utf-8")
    return {organic_qa._Q + n for n in re.findall(r"""_Q \+ ["']([a-z_]+)["']""", code)}


def _pack_md_keys() -> set[str]:
    """The keys organic_pack.render_md reads: t("<key>") and _M + "<key>", its tables of routes, risks, check-ins."""
    code = Path(organic_pack.__file__).read_text(encoding="utf-8")
    names = re.findall(r"""\bt\(["']([a-z_]+)["']""", code) + re.findall(r"""_M \+ ["']([a-z_]+)["']""", code)
    return ({organic_pack._M + n for n in names} | set(organic_pack.ROUTE_KEY.values())
            | set(organic_pack.RISK_KEY.values()) | set(organic_pack.CHECKIN_KEYS))


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


@pytest.mark.parametrize("lang, name", [("en", "Organic AI video"), ("pl", "Organiczne wideo AI")])
def test_every_page_has_the_run_pages_top_bar_and_look(lang, name):
    """Issue #60: the proposals, the check-in and delivery pages (the week's delivery is one), the week and the
    script in the TrendsMesh look, with its top bar naming the playbook in the page's language."""
    for which, text in _pages(lang).items():
        if which == "script_md":
            continue
        assert f'<div class="wrap"><header class="top"><span class="brand">' in text, which
        assert f'<span class="pill dark">{name}</span></header>' in text, which
        assert '<style id="tm-look">' in text and "Source+Sans" not in text, which


def test_the_proposals_page_shows_the_lead_lines():
    """Issue #85: the line on why a channel's proposals lead with one kind sits under the page's lede."""
    text = proposals.render(_proposals("en"), _trends, lambda v: "", level="hands_off",
                            leads=["A news & explainer channel, so topics come first."])
    assert '<p class="hint">A news &amp; explainer channel, so topics come first.</p><div class="chips">' in text
    assert proposals.render(_proposals("en"), _trends, lambda v: "", level="hands_off").count('<p class="hint">') == \
        text.count('<p class="hint">') - 1


# --- the table ------------------------------------------------------------------------------------------

def test_every_key_the_pages_read_is_in_the_english_table_and_every_organic_key_is_read():
    counts = i18n.groups()
    en = {k.rpartition(".")[0] if k.rpartition(".")[0] in counts else k for k in _organic(i18n.english())}
    used = _used() | _literals()
    assert sorted(used - set(en)) == []                       # a key the code reads that the table lacks
    assert sorted(set(en) - used) == []                       # a string no page reads
    assert _literals() <= _used()                             # every key written in the code is one listed above


def test_the_plugin_ships_every_organic_string_in_polish():
    en = i18n.wanted("pl", ["organic"])                         # with Polish's forms of each count
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
    assert "Opis do wklejenia (z hashtagami)" in _pages("pl")["gate_edit"]   # the kit's text to paste (issue #91)
    assert "Przy publikacji" in _pages("pl")["gate_edit"] and "Zestaw do publikacji dla" in _pages("pl")["gate_edit"]


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


@pytest.mark.parametrize("lang,count,said", [("en", 1, "1 video this week"), ("en", 2, "2 videos this week"),
                                             ("pl", 1, "1 film w tygodniu"), ("pl", 3, "3 filmy w tygodniu"),
                                             ("pl", 5, "5 filmów w tygodniu")])
def test_the_weeks_count_of_videos_takes_the_form_its_number_takes(lang, count, said):
    w = _week(lang)
    w["slots"] = [{**w["slots"][0], "id": f"w{n}", "day": day} for n, day in enumerate(("mon", "tue", "wed", "thu",
                                                                                         "fri")[:count])]
    meta = re.search(r'<p class="meta">([^<]*)</p>', week.render(w)).group(1)
    assert meta.startswith(said + " · ")


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


# --- the pack's and the kit's Markdown, the QA's words, the run's stored values (issue #3) ------------------

FIXTURES = Path(__file__).parent / "fixtures" / "organic"


def _pack():
    import json
    return json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))


def _md_left(md: str, prefix: str) -> list[str]:
    """English labels of `prefix` (organic.pack_md. / organic.kit_md.) still in a Markdown in another language."""
    out = []
    for key, value in i18n.english().items():
        if not key.startswith(prefix):
            continue
        for part in re.split(r"\{[^}]*\}", value):
            part = part.strip(" :·()–~/.+")
            if len(part) >= 5 and re.search(rf"(?<![A-Za-z·]){re.escape(part)}(?![A-Za-z])", md):
                out.append(f"{key}: {part!r}")
    return out


def test_the_packs_markdown_is_in_the_page_language(tmp_path):
    pack = _pack()
    english = organic_pack.render_md(pack, "en")
    assert english.startswith(f"# {pack['id']}, pack") and "## Picture" in english
    polish = organic_pack.render_md(pack, "pl")
    assert f"# {pack['id']}, paczka" in polish and "## Obraz" in polish and "## Punkty kontrolne" in polish
    words = pack["script"]["words"]
    form = i18n.category(words, "pl")
    assert f"## Scenariusz ({words} " + {"one": "słowo", "few": "słowa", "many": "słów"}[form] + "," in polish
    assert _md_left(polish, "organic.pack_md.") == []
    _german(tmp_path)
    german = organic_pack.render_md(pack, "de")
    assert "## DE·Picture" in german and "DE·long takes: " in german
    assert organic_pack.render_md(pack, "fr") == english                    # no French table: English
    assert organic_pack.md_lang("fr").warning and organic_pack.md_lang("pl").warning is None


def test_the_packs_stored_values_are_shown_in_the_page_language():
    pack = _pack()
    pack["risk"] = {"level": "medium", "hits": [{"item": "long_takes", "mitigation": "mq"},
                                                {"item": "custom", "mitigation": "cq"}]}
    pack["product"]["level"] = "soft mention"
    english, polish = organic_pack.render_md(pack, "en"), organic_pack.render_md(pack, "pl")
    assert "**Risk:** medium. long takes: mq; custom: cq." in english and "long_takes" not in english
    assert "**Ryzyko:** średnie. długie ujęcia: mq; custom: cq." in polish
    assert "Product: soft mention." in english and "Produkt: delikatna wzmianka." in polish
    assert pack["risk"]["hits"][0]["item"] == "long_takes"                 # the data keeps the stored value


def test_a_stored_value_shows_in_the_page_language_or_as_stored():
    assert organic_pages.value("soft mention", "product", "pl") == "delikatna wzmianka"
    assert organic_pages.value("soft_mention", "product", "pl") == "delikatna wzmianka"     # the profile's form
    assert organic_pages.value("nie występuje", "product", "en") == "not shown"           # ExampleEdu's Polish
    assert organic_pages.value("confirmed", "status", "pl") == "potwierdzony"
    assert organic_pages.value("long_takes", "risk", "en") == "long takes"
    assert organic_pages.value("as typed", "product", "pl") == "as typed"
    assert organic_pages.value(None, "status", "pl") is None
    en = i18n.translator("en")
    for level, key in organic_pages.value_keys("product").items():
        assert en(key) == level                                         # English shows the stored level itself
    for status, key in organic_pages.STATUS_KEY.items():
        assert en(key) == status


def test_the_proposals_page_shows_the_product_level_and_status_in_its_language():
    data = _proposals("pl")
    data["proposals"][0]["product"]["level"] = "soft mention"
    card, vids = _trends("t1")
    page = proposals.render(data, lambda tid: ({**card, "status": "confirmed"}, vids), lambda v: "",
                            level="hands_off")
    assert "<b>delikatna wzmianka</b>" in page and "· potwierdzony" in page
    assert "soft mention" not in page and "· confirmed" not in page
    english = proposals.render({**data, "lang": "en"}, lambda tid: ({**card, "status": "confirmed"}, vids),
                               lambda v: "", level="hands_off")
    assert "<b>soft mention</b>" in english and "views · confirmed" in english


def test_the_reference_pages_stored_values_are_worded_as_the_plugin_shows_them():
    ref = ('<span class="chip">Produkt: <b>soft mention</b></span><span class="chip">Długość <b>15 s</b></span>'
           '<dt>Produkt</dt><dd><b>hero</b>: nq</dd><div class="tstats">12 twórców · 3.4K filmów · 5.6M wyświetleń · '
           'confirmed · hook sq 2/2 · id t1</div>')
    got = organic_pages.worded(ref, "pl")
    assert "<b>delikatna wzmianka</b>" in got and "<b>15 s</b>" in got and "<dd><b>w roli głównej</b>: nq" in got
    assert "wyświetleń · potwierdzony · hook sq 2/2 · id t1" in got


def test_the_proposals_lede_counts_ideas_in_polish():
    tr = i18n.translator("pl")
    assert [proposals.lede_frags(n)[0].fill(tr) for n in (1, 3, 5, 12, 22)] == [
        '<p class="lede">1 pomysł na filmy dla ', '<p class="lede">3 pomysły na filmy dla ',
        '<p class="lede">5 pomysłów na filmy dla ', '<p class="lede">12 pomysłów na filmy dla ',
        '<p class="lede">22 pomysły na filmy dla ']


def test_the_kits_markdown_labels_are_in_the_page_language(tmp_path):
    k = {"id": "M1", "version": "v01", "channel": "Zorbo", "video": "v.mp4", "cover": {"file": "c.jpg"},
         "product": "pq", "language": "pl",
         "platforms": {"tiktok": {"caption": "caq", "hashtags": ["#a"], "ai_label": "alq", "cover": "coq"},
                       "youtube": {"title": "tiq", "description": "deq"}},
         "plugin": {"trending_sound": {"name": "snq", "evidence": "evq"}, "business_alternative": "baq"}}
    english, polish = kit.to_md(k, "en"), kit.to_md(k, "pl")
    assert english.startswith("# Posting kit M1 v01 (Zorbo)") and "**Description to paste (with hashtags):**" in english
    assert "caq\n\n#a" in english and "**At posting:**" in english and "- **AI label:** alq" in english
    assert polish.startswith("# Zestaw do publikacji M1 v01 (Zorbo)") and "**Opis do wklejenia (z hashtagami):**" in polish
    assert "**Przy publikacji:**" in polish and "**Opis filmu (z hashtagami):**" in polish
    assert "okładka: `c.jpg`" in polish and "**Alternatywa dla konta firmowego:** baq" in polish
    assert _md_left(polish, "organic.kit_md.") == []
    _german(tmp_path)
    assert kit.to_md(k, "de").startswith("# DE·Posting kit M1 v01")
    assert kit.to_md(k, "fr") == english


def test_the_qa_findings_are_in_the_page_language():
    cfg = None
    qa = {"match": 0.5, "lufs": -3.0, "wps": 2.0, "cut_offsets": [{"bracket": 3.0, "cut": None},
                                                                  {"bracket": 6.0, "cut": 7.5, "offset": 1.5}]}
    english = organic_qa.rubric_takes(qa, cfg)
    assert english == organic_qa.rubric_words(qa, cfg, "en")
    assert english["fails"][0].startswith("the transcript matches 50% of the script, under ")
    polish = organic_qa.rubric_words(qa, cfg, "pl")
    assert polish["speed"] == english["speed"] and len(polish["fails"]) == 2 and len(polish["findings"]) == 3
    assert polish["fails"][0].startswith("transkrypcja zgadza się ze scenariuszem w 50%")
    assert all("take" not in t and "cut " not in t for t in polish["fails"] + polish["findings"])
    silent = organic_qa.rubric_words({"lufs": None, "match": 1.0}, cfg, "pl")
    assert silent["fails"] == ["ujęcie nie ma mierzalnego dźwięku, a niesie kwestie mówione"]
