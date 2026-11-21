"""tm.plain_words (issue #132): the run's codes and files a page for people never shows."""

import json

import pytest

from tm import plain_words
from tm.runfolder import RunFolder

TID = "c2173b6a4e7f496093804bb8efb3e785"


@pytest.fixture
def run(tmp_path, monkeypatch) -> RunFolder:
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    folder = tmp_path / "ws" / "2026-11-04_ld"
    (folder / "02_research" / "voice").mkdir(parents=True)
    (folder / "02_research" / f"trend_{TID}.json").write_text("{}", encoding="utf-8")
    (folder / "02_research" / "trend_trend_ld_003_v02.json").write_text("{}", encoding="utf-8")
    (folder / "02_research" / "trend_abc.json").write_text("{}", encoding="utf-8")     # too short to look for
    themes = {"themes": [{"id": "T01", "title": "too much time scrolling"}, {"id": "T05", "title": "sleep"}]}
    (folder / "02_research" / "voice" / "voice_themes_v01.json").write_text(json.dumps(themes), encoding="utf-8")
    return RunFolder(folder)


def test_the_run_codes_are_its_cards_and_themes(run):
    codes = plain_words.codes(run)
    assert set(codes.trends) == {TID[:8], "trend_ld"}
    assert codes.themes == ("T01", "T05")


@pytest.mark.parametrize("text, kind, value", [
    (f"TrendsMesh, trend {TID}", "a trend id", TID),
    ("TrendsMesh trend c2173b6a, pulled 4 November", "a trend id", "c2173b6a"),
    ("trend trend_ld_003 and more", "a trend id", "trend_ld"),
    ("02_research/voice/voice_themes_v01.json, T02 and T05", "a run file", "02_research/voice/voice_themes_v01.json"),
    ("as read in 01_base/account_context.md.", "a run file", "01_base/account_context.md"),
    ("the read ads_get_ad_entities_v03.json says so", "a run file", "ads_get_ad_entities_v03.json"),
    ("saved as rows.csv", "a run file", "rows.csv"),
    ("log.jsonl", "a run file", "log.jsonl"),
    ("themes T01 and T05 say it", "a theme id", "T01"),
])
def test_found(run, text, kind, value):
    assert plain_words.found(text, plain_words.codes(run)) == (kind, value)


@pytest.mark.parametrize("text", [
    "TrendsMesh: Rising hook \"who said _\" (card), pulled 4 November",
    "Your Meta account, Night School campaigns, lifetime",
    "Customers: 8 of 114 items, theme \"too much time scrolling\"",
    "Meta Ad Library, query \"lucid dream\", US",
    "T01s and AT05 are not theme ids; T07 is not a theme of this run",
    "1 USD = 3.70 PLN, e.g. 35 creators",
    "",
])
def test_plain_text_passes(run, text):
    assert plain_words.found(text, plain_words.codes(run)) is None


def test_without_a_run_only_the_fixed_patterns_count():
    codes = plain_words.Codes()
    assert plain_words.found("T01 and c2173b6a", codes) is None
    assert plain_words.found(f"id {TID}", codes) == ("a trend id", TID)
    assert plain_words.found("03_wip/decisions_gate_images_v01.json", codes)[0] == "a run file"
