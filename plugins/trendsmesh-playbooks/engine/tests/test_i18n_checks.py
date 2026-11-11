"""Issue #3 outside the pages: CB13's words in the run's languages, glance rows named by key, the shortlist's market
language, the weekly phrase and file names that keep their letters."""

import argparse
from datetime import date

import yaml

from tm import brief_checks, config, flowcmd, i18n, shortlist, trends, voice
from tm.playbooks import CREATIVE_BRIEF, TREND_RESEARCH
from tm.runfolder import RunFolder


def _translate(tmp_path, lang, strings):
    path = tmp_path / f"i18n_{lang}.yaml"
    path.write_text(yaml.safe_dump({"lang": lang, "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file(lang, path)


# --- CB13 -------------------------------------------------------------------------------------------

def test_creator_words_in_english_only_say_so():
    cfg = {"languages": {"working": "en", "market": "en"}}
    assert brief_checks.language_words(cfg) == ([], [])
    assert brief_checks.language_note(cfg) == "CB13 read the creator view for ad and research words in English."


def test_an_uncovered_language_is_named():
    cfg = {"languages": {"working": "pl", "market": "de"}}
    words, uncovered = brief_checks.language_words(cfg)
    assert words == [] and uncovered == ["pl", "de"]
    note = brief_checks.language_note(cfg)
    assert "in English." in note and "Polish (pl) and German (de) is not covered" in note
    assert "tm i18n export --lang pl" in note


def test_the_translated_table_adds_words(tmp_path):
    _translate(tmp_path, "pl", {"checks.creator_words": "koszt na, wydat*, konkurenc*, ctr"})
    cfg = {"languages": {"working": "pl", "market": "pl"}}
    assert brief_checks.language_words(cfg) == (["koszt na", "wydat*", "konkurenc*"], [])
    assert brief_checks.language_note(cfg) == ("CB13 read the creator view for ad and research words in English and "
                                               "Polish.")
    brief = {"meta": {"plugin": {"account_currency": "PLN"}}}
    words = dict(brief_checks._creator_words(cfg, brief, []))
    assert words["wydat*"].search("nasze wydatki rosną") and words["wydat*"].search("wydatków")
    assert not words["wydat*"].search("przewydatny")                 # a whole word, any ending
    assert words["koszt na"].search("koszt na klienta") and not words["koszt na"].search("koszt nauki")
    assert words["konkurenc*"].search("konkurencja")


def test_an_older_config_reads_its_account_language():
    cfg = {"account": {"language": "Polish"}}
    assert brief_checks.language_words(cfg) == ([], ["pl"])


# --- glance rows by key -------------------------------------------------------------------------------

def test_a_glance_row_is_found_by_key_in_any_language():
    concept = {"glance": [{"label": "Konkurencja", "text": "x", "source": "y", "key": "competition"},
                          {"label": "Account", "text": "x", "source": "y"}]}
    assert brief_checks._row(concept, "Competition")[0] == 0
    assert brief_checks._row(concept, "Account")[0] == 1
    assert brief_checks._row(concept, "Customers") == (None, None)


def test_the_glance_keys_are_in_the_schema():
    import json
    from pathlib import Path
    schema = json.loads((Path(brief_checks.__file__).parent / "schemas" / "pb2_brief.schema.json").read_text())
    glance = schema["definitions"]["concept"]["properties"]["glance"] if "definitions" in schema else None
    text = json.dumps(schema)
    assert all(k in text for k in brief_checks.GLANCE_KEYS) and (glance is None or glance)


# --- the shortlist's market language -------------------------------------------------------------------

def _shortlist_run(tmp_path, cfg):
    run = RunFolder.create(tmp_path, "langs", date(2026, 11, 5), playbook=TREND_RESEARCH)
    config.save(run, cfg)
    return run


def test_the_shortlist_market_language_defaults_from_the_run(tmp_path, monkeypatch):
    seen = {}

    def fake_write(run, inputs, terms, *, market, **kw):
        seen["market"] = market
        return {"skipped": [], "files": [], "message": "ok"}

    monkeypatch.setattr(shortlist, "write", fake_write)
    monkeypatch.setattr(shortlist, "input_files", lambda run, given: ["x.json"])
    from tm import cli
    for cfg, given, want in (({"languages": {"working": "en", "market": "pl-PL"}}, None, "pl"),
                             ({"language": "Italian"}, None, "it"), ({}, None, "en"),
                             ({"languages": {"working": "pl", "market": "pl"}}, "de", "de")):
        run = _shortlist_run(tmp_path / str(len(seen)) / want, cfg)
        argv = ["trends", "shortlist", "--run", str(run.path), "--terms", "sleep"]
        if given:
            argv += ["--market-language", given]
        try:
            cli.main(argv)
        except (KeyError, TypeError):
            pass                                # the fake's answer may not fill the command's message
        assert seen.pop("market") == want


# --- the weekly phrase -------------------------------------------------------------------------------

NOTE = "No schedule was set up: say 'update my trend report' each week."


def test_the_weekly_phrase_follows_the_working_language(tmp_path):
    assert i18n.offered(NOTE, "en") == NOTE
    assert i18n.offered(NOTE, "pl") == ("No schedule was set up: say 'update my trend report' (offer it to the user "
                                        "in Polish) each week.")
    _translate(tmp_path, "pl", {"trends.weekly_phrase": "zaktualizuj mój raport trendów"})
    assert i18n.offered(NOTE, "pl") == "No schedule was set up: say 'zaktualizuj mój raport trendów' each week."


def test_the_weekly_phrase_is_the_checkin_note():
    from tm import checkins
    cat = checkins.load(playbook=TREND_RESEARCH)
    assert cat.checkins["GS"].on_choice["by_hand"]["skips"] == NOTE
    assert f"'{i18n.english()['trends.weekly_phrase']}'" in NOTE
    assert flowcmd.i18n is i18n


# --- file names ---------------------------------------------------------------------------------------

def test_a_saved_file_name_keeps_its_letters():
    assert trends._part("łódź ćwiczenia", "x") == "lodz_cwiczenia"
    assert trends._part("Straße", "x") == "strasse"
    assert trends._part("éclair", "x") == "eclair"
    assert len(trends._part("плов", "x")) == 8                          # another script: the text's digest


def test_a_reddit_file_name_keeps_its_letters(tmp_path):
    run = RunFolder.create(tmp_path, "langs", date(2026, 11, 5), playbook=CREATIVE_BRIEF)
    rel = voice._save(run, "posts", "polska", "żółć", {"data": [], "_params": {}})
    assert "zolc" in rel


# --- CB5: a customer phrase translated into the market language --------------------------------------------

def _concept(phrase):
    return {"id": "C1", "hook": {"text": "Nie mogę spać od miesięcy"}, "beats": [], "customer_phrases": [phrase]}


def test_a_translated_phrase_names_its_original():
    bank = ["I haven't slept in months"]
    ok = {"phrase": "Nie mogę spać od miesięcy", "translated": True, "adapted_from": "I haven't slept in months"}
    assert brief_checks._phrases(0, _concept(ok), bank, "02_research/voice_themes_v01.json", 1) == []
    bad = {"phrase": "Nie mogę spać od miesięcy", "translated": True}
    [p] = brief_checks._phrases(0, _concept(bad), bank, "02_research/voice_themes_v01.json", 1)
    assert p.field == "concepts[0].customer_phrases[0].adapted_from" and "translated" in p.what
    wrong = {**ok, "adapted_from": "a phrase nobody wrote"}
    [p] = brief_checks._phrases(0, _concept(wrong), bank, "02_research/voice_themes_v01.json", 1)
    assert p.field.endswith("adapted_from")
