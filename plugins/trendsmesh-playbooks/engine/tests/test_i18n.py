"""tm.i18n: the English string table, the translated tables, a run's two languages and file-name transliteration
(issue #3)."""

import json
from datetime import date

import pytest
import yaml

from tm import config, i18n
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder


@pytest.fixture
def table(monkeypatch):
    """A small English table in place of the shipped one."""
    from tm import cli
    cli._load_commands()                    # modules that read the real table at import, before it is swapped
    en = {"demo.hello": "Hello", "demo.count": "{n} videos", "demo.bold": "Seen by <b>{who}</b>"}
    monkeypatch.setattr(i18n, "english", lambda: dict(en))
    monkeypatch.setattr(i18n, "_shipped", lambda lang: {})
    return en


# --- the English table -----------------------------------------------------------------------------

def test_the_english_table_is_flat_keys_with_an_area():
    en = i18n.english()
    assert en and all(isinstance(v, str) and v for v in en.values())
    assert all(k.count(".") >= 1 and k == k.strip() for k in en)


def test_every_shipped_translation_matches_the_english_placeholders():
    en = i18n.english()
    for path in sorted(i18n.TABLES.glob("*.yaml")):
        if path.stem == "en":
            continue
        shipped = i18n._shipped(path.stem)
        assert set(shipped) <= set(en) | set(i18n.wanted(path.stem)), path.name     # a count in its own forms
        assert not i18n.problems(shipped), path.name


def test_every_english_string_fills():
    for key, text in i18n.english().items():
        assert i18n.t(key, **{p: "x" for p in i18n.placeholders(text)}), key


def test_t_in_english(table):
    assert i18n.t("demo.count", n=3) == "3 videos"
    assert i18n.t("demo.hello", "en") == "Hello"


def test_t_refuses_an_unknown_key(table):
    with pytest.raises(KeyError):
        i18n.t("demo.nope")


def test_t_never_falls_back_silently(table):
    with pytest.raises(i18n.Missing) as got:
        i18n.t("demo.hello", "pl")
    assert "tm i18n export" in str(got.value)


# --- tags --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("given, want", [
    ("pl", "pl"), ("PL", "pl"), ("pl_PL", "pl-PL"), ("pl-pl", "pl-PL"), ("Polish", "pl"), ("polski", "pl"),
    ("Español", "es"), ("pt-br", "pt-BR"), ("zh-hant-tw", "zh-Hant-TW"), ("German", "de"), (" en ", "en"),
])
def test_tag_normalises(given, want):
    assert i18n.tag(given) == want


@pytest.mark.parametrize("given", [None, "", "  ", "Klingonish", 12, "toolongprimary"])
def test_tag_refuses_what_is_no_language(given):
    assert i18n.tag(given) is None


def test_name_of_a_tag():
    assert i18n.name("pl") == "Polish"
    assert i18n.name("pt-BR") == "Portuguese (BR)"
    assert i18n.name("xx") == "xx"


# --- translated tables: export, import, check --------------------------------------------------------

def test_export_lists_what_is_missing(table, tmp_path):
    out = i18n.export("pl", tmp_path / "pl.yaml")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["lang"] == "pl" and data["strings"] == table


def test_import_then_t(table, tmp_path):
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": {"demo.hello": "Cześć", "demo.count": "{n} filmów"}},
                                   allow_unicode=True), encoding="utf-8")
    got = i18n.import_file("pl", path)
    assert got["imported"] == 2 and got["missing"] == ["demo.bold"]
    assert i18n.t("demo.count", "pl", n=4) == "4 filmów"
    assert set(yaml.safe_load(i18n.export("pl", tmp_path / "rest.yaml").read_text(encoding="utf-8"))["strings"]) \
        == {"demo.bold"}


def test_import_refuses_a_wrong_placeholder_or_markup(table, tmp_path):
    path = tmp_path / "pl.yaml"
    for bad in ({"demo.count": "{m} filmów"}, {"demo.bold": "Widziane przez {who}"}, {"demo.nope": "x"},
                {"demo.hello": ""}):
        path.write_text(yaml.safe_dump({"lang": "pl", "strings": bad}, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError):
            i18n.import_file("pl", path)
    assert i18n.table("pl") == {}


def test_import_refuses_another_language(table, tmp_path):
    path = tmp_path / "de.yaml"
    path.write_text(yaml.safe_dump({"lang": "de", "strings": {"demo.hello": "Hallo"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        i18n.import_file("pl", path)


def test_a_changed_english_string_is_missing_again(table, tmp_path, monkeypatch):
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": {"demo.hello": "Cześć"}}, allow_unicode=True),
                    encoding="utf-8")
    i18n.import_file("pl", path)
    assert "demo.hello" in i18n.table("pl")
    monkeypatch.setattr(i18n, "english", lambda: {**table, "demo.hello": "Hello there"})
    assert "demo.hello" not in i18n.table("pl")


def test_a_region_reuses_its_language(table, tmp_path):
    path = tmp_path / "pt.yaml"
    path.write_text(yaml.safe_dump({"lang": "pt", "strings": {"demo.hello": "Olá"}}, allow_unicode=True),
                    encoding="utf-8")
    i18n.import_file("pt", path)
    assert i18n.t("demo.hello", "pt-BR") == "Olá"


def test_page_lang_falls_back_loudly(table, tmp_path):
    got = i18n.page_lang("pl", "demo")
    assert got.lang == "en" and got.wanted == "pl" and len(got.missing) == 3
    assert "English" in got.warning and "tm i18n export --lang pl" in got.warning
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": {"demo.hello": "Cześć", "demo.count": "{n} filmów",
                                                              "demo.bold": "Widziane przez <b>{who}</b>"}},
                                   allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)
    got = i18n.page_lang("pl", "demo")
    assert got.lang == "pl" and got.warning is None
    assert i18n.page_lang("en", "demo").warning is None


def test_translator_binds_a_language(table):
    tr = i18n.translator("en")
    assert tr("demo.count", n=1) == "1 videos" and tr.lang == "en"


def test_cli_export_import_check(table, tmp_path, capsys):
    from tm import cli
    out = tmp_path / "todo.yaml"
    assert cli.main(["i18n", "export", "--lang", "pl", "--out", str(out), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == 3
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    data["strings"] = {"demo.hello": "Cześć", "demo.count": "{n} filmów", "demo.bold": "Widziane przez <b>{who}</b>"}
    out.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert cli.main(["i18n", "import", "--lang", "pl", str(out), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == []
    assert cli.main(["i18n", "check", "--lang", "pl", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["complete"] is True


def test_cli_check_says_what_is_missing(table, capsys):
    from tm import cli
    assert cli.main(["i18n", "check", "--lang", "de"]) == 2
    assert "tm i18n export --lang de" in capsys.readouterr().out


# --- a run's two languages ---------------------------------------------------------------------------

def _run(tmp_path, playbook, cfg):
    run = RunFolder.create(tmp_path, "langs", date(2026, 11, 5), playbook=playbook)
    if cfg is not None:
        config.save(run, cfg)
    return run


def test_languages_from_the_config(tmp_path):
    run = _run(tmp_path, CREATIVE_BRIEF, {"languages": {"working": "en", "market": "pl"}})
    assert i18n.run_languages(run) == i18n.Languages("en", "pl")


@pytest.mark.parametrize("playbook, cfg, want", [
    (REFRESH_AD, {"account": {"language": "Polish"}}, ("pl", "pl")),
    (CREATIVE_BRIEF, {"account": {"language": "es-ES"}}, ("es-ES", "es-ES")),
    (TREND_RESEARCH, {"language": "Italian", "market_lang": None}, ("it", "it")),
    (TREND_RESEARCH, {"language": "en", "market_lang": "de"}, ("en", "de")),
    (ORGANIC_VIDEO, {"page_lang": "pl"}, ("pl", "pl")),
    (ORGANIC_VIDEO, {"page_lang": "en", "page_lang_note": "Pages are built in English; post text stays in German."},
     ("en", "en")),
])
def test_languages_of_an_older_config(tmp_path, playbook, cfg, want):
    assert tuple(i18n.run_languages(_run(tmp_path, playbook, cfg))) == want


def test_languages_default_to_english(tmp_path):
    assert i18n.run_languages(_run(tmp_path, REFRESH_AD, None)) == i18n.Languages("en", "en")
    assert i18n.languages_of({}) == i18n.Languages("en", "en")


def test_languages_half_given(tmp_path):
    assert i18n.languages_of({"languages": {"working": "pl", "market": None}}) == i18n.Languages("pl", "pl")
    assert i18n.languages_of({"languages": {"working": None, "market": "de"}}) == i18n.Languages("de", "de")


def test_language_problems():
    assert i18n.language_problems({"languages": {"working": "pl", "market": "en-GB"}}) == []
    bad = i18n.language_problems({"languages": {"working": "Polish", "market": 3}})
    assert [p.field for p in bad] == ["languages.working", "languages.market"]
    assert [p.field for p in i18n.language_problems({"languages": "pl"})] == ["languages"]


def test_intake_languages_fill_the_older_keys():
    cfg = {"languages": {"working": "Polish", "market": None}}
    i18n.settle(cfg)
    assert cfg["languages"] == {"working": "pl", "market": "pl"}
    older = {"account": {"language": "German"}}
    i18n.settle(older)
    assert older["languages"] == {"working": "de", "market": "de"}


# --- file names ------------------------------------------------------------------------------------

@pytest.mark.parametrize("given, want", [
    ("éclair", "eclair"), ("Straße", "Strasse"), ("łódź", "lodz"), ("Środa", "Sroda"), ("żółć", "zolc"),
    ("Æsir øl", "AEsir ol"), ("naïve café", "naive cafe"), ("плов", "плов"),
])
def test_transliterate(given, want):
    assert i18n.transliterate(given) == want


def test_the_stated_market_language_is_never_a_default():
    assert i18n.stated_market({}) == (None, None)
    assert i18n.stated_market({"languages": {"working": "pl", "market": None}}) == (None, None)
    assert i18n.stated_market({"languages": {"market": "uk"}, "account": {"language": "Polish"}}) == \
        ("uk", "languages.market in config.yaml")
    assert i18n.stated_market({"account": {"language": "Polish"}}) == ("pl", "account.language in config.yaml")
    assert i18n.stated_market({"language": "en", "market_lang": "de"}) == ("de", "market_lang in config.yaml")
    assert i18n.stated_market({"page_lang": "pl"}) == (None, None)        # organic pages: not the audience's


def test_the_video_fonts_read_the_run_languages_through_i18n(tmp_path):
    from tm import video_fonts
    run = _run(tmp_path, TREND_RESEARCH, {"language": "English", "market_lang": "Belarusian"})
    assert video_fonts.market_language(run) == ("be", "market_lang in config.yaml")


# --- counts: CLDR plural categories --------------------------------------------------------------------

@pytest.mark.parametrize("n,want", [(1, "one"), (2, "few"), (4, "few"), (5, "many"), (11, "many"), (12, "many"),
                                    (14, "many"), (21, "many"), (22, "few"), (24, "few"), (25, "many"), (0, "many"),
                                    (101, "many"), (102, "few"), (112, "many"), (1.5, "other"), ("2.0", "other")])
def test_polish_counts_take_one_few_many_and_a_fraction_form(n, want):
    assert i18n.category(n, "pl") == want


@pytest.mark.parametrize("lang,n,want", [
    ("en", 1, "one"), ("en", 0, "other"), ("en", 2, "other"), ("en", "1.0", "other"),
    ("ru", 21, "one"), ("ru", 11, "many"), ("ru", 3, "few"), ("uk", 5, "many"),
    ("cs", 3, "few"), ("cs", 5, "other"), ("cs", 1.5, "many"),
    ("fr", 0, "one"), ("fr", 1, "one"), ("fr", 2, "other"), ("fr", 1_000_000, "many"),
    ("pt", 0, "one"), ("pt-PT", 0, "other"), ("pt-BR", 0, "one"),
    ("ar", 0, "zero"), ("ar", 2, "two"), ("ar", 3, "few"), ("ar", 11, "many"), ("ar", 100, "other"),
    ("sl", 102, "two"), ("lt", 11, "other"), ("lt", 2, "few"), ("lv", 0, "zero"), ("ga", 7, "many"),
    ("ja", 1, "other"), ("zh-Hant-TW", 1, "other"), ("xx", 1, "one"), ("xx", 2, "other"),
])
def test_counts_follow_each_languages_cldr_rule(lang, n, want):
    assert i18n.category(n, lang) == want


def test_the_forms_a_table_needs_are_the_whole_numbers_categories():
    assert i18n.count_forms("en") == ("one", "other")
    assert i18n.count_forms("pl") == ("one", "few", "many")        # the fraction form only for fractions
    assert i18n.count_forms("ja") == ("other",)
    assert i18n.count_forms("ar") == ("zero", "one", "two", "few", "many", "other")
    assert i18n.count_forms("fr") == ("one", "many", "other")       # many: a million (de)


@pytest.fixture
def counted(monkeypatch):
    """A small English table with a count: demo.videos.one / demo.videos.other."""
    from tm import cli
    cli._load_commands()
    en = {"demo.hello": "Hello", "demo.videos.one": "One video", "demo.videos.other": "{n} videos <b>seen</b>"}
    monkeypatch.setattr(i18n, "english", lambda: dict(en))
    monkeypatch.setattr(i18n, "_shipped", lambda lang: {})
    return en


def test_a_count_in_english(counted):
    tr = i18n.translator("en")
    assert tr.plural("demo.videos", 1, n=1) == "One video"
    assert tr.plural("demo.videos", 3, n=3) == "3 videos <b>seen</b>"
    with pytest.raises(KeyError):
        tr("demo.videos")
    with pytest.raises(KeyError):
        tr.plural("demo.hello", 2)


def test_a_language_needs_each_of_its_forms_of_a_count(counted, tmp_path):
    assert i18n.missing("pl") == ["demo.hello", "demo.videos.one", "demo.videos.few", "demo.videos.many"]
    assert i18n.missing("ja") == ["demo.hello", "demo.videos.other"]
    out = yaml.safe_load(i18n.export("pl", tmp_path / "pl.yaml").read_text(encoding="utf-8"))
    assert out["strings"]["demo.videos.few"] == "{n} videos <b>seen</b>"    # translated from the English other
    assert out["strings"]["demo.videos.one"] == "One video"
    assert "few: 2, 3, 4, 22" in out["how"] and "many: 0, 5, 6" in out["how"]


def test_a_translated_count_picks_its_form(counted, tmp_path):
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": {
        "demo.hello": "Cześć", "demo.videos.one": "Jeden film", "demo.videos.few": "{n} filmy <b>widziane</b>",
        "demo.videos.many": "{n} filmów <b>widzianych</b>"}}, allow_unicode=True), encoding="utf-8")
    assert i18n.import_file("pl", path)["missing"] == []
    tr = i18n.translator("pl")
    assert [tr.plural("demo.videos", n, n=n) for n in (1, 3, 5, 22)] == [
        "Jeden film", "3 filmy <b>widziane</b>", "5 filmów <b>widzianych</b>", "22 filmy <b>widziane</b>"]
    assert tr.plural("demo.videos", 1.5, n=1.5) == "1.5 filmów <b>widzianych</b>"   # no fraction form: many
    assert i18n.page_lang("pl", "demo").lang == "pl"


def test_a_form_may_say_the_count_the_english_one_leaves_out(counted, tmp_path):
    """Russian's one is 1, 21, 31 …: its form says the number, though the English "One video" does not."""
    path = tmp_path / "ru.yaml"
    path.write_text(yaml.safe_dump({"lang": "ru", "strings": {"demo.videos.one": "{n} видео"}},
                                   allow_unicode=True), encoding="utf-8")
    i18n.import_file("ru", path)
    assert i18n.translator("ru").plural("demo.videos", 21, n=21) == "21 видео"


def test_a_count_form_is_checked_like_any_string(counted, tmp_path):
    for strings in ({"demo.videos.few": "{count} filmy <b>x</b>"}, {"demo.videos.few": "{n} filmy"},
                    {"demo.hello.few": "x"}, {"demo.videos.lots": "{n} x <b>y</b>"}):
        path = tmp_path / "pl.yaml"
        path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError):
            i18n.import_file("pl", path)


def test_a_changed_english_count_is_missing_again(counted, tmp_path, monkeypatch):
    path = tmp_path / "pl.yaml"
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": {"demo.videos.many": "{n} filmów <b>x</b>"}},
                                   allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)
    assert "demo.videos.many" not in i18n.missing("pl")
    changed = {**counted, "demo.videos.other": "{n} clips <b>seen</b>"}
    monkeypatch.setattr(i18n, "english", lambda: dict(changed))
    assert "demo.videos.many" in i18n.missing("pl")


def test_every_count_of_the_english_table_has_its_other_form():
    en = i18n.english()
    for base, forms in i18n.groups(en).items():
        assert "other" in forms and set(forms) <= {"one", "other"}, base
