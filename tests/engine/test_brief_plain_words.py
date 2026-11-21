"""tm brief check refuses codes and run files in what the page shows (issue #132): the source in words in `source`,
the MCP call, run file or trend id in `source_ref`.

The run is test_brief_checks.py's: the LD dry run (ld.py) with its voice themes, a saturation file, the account's
creatives and the audience pick.
"""

import json
from pathlib import Path

import pytest

import ld
import test_audience
from tm import audience, brief_checks, config, mcp_saves, state, voice
from tm.cli import main
from tm.runfolder import RunFolder

pytestmark = pytest.mark.private_data

FIXTURES = Path(__file__).parent / "fixtures" / "creative_brief"
STAGES = ("concepts", "brief", "production")
C1 = "c2173b6a4e7f496093804bb8efb3e785"
CFG = {"account": {"currency": "PLN"}, "brief": {"fx_rate": 3.7}}
SATURATION = {"checks": [
    {"candidate": C1, "query": "gateway process", "country": "CA", "verdict": "none_found", "advertisers": [],
     "own_ads": False, "note": "all noise"},
    {"candidate": "b4f8d078758f4c3784587030a19e122c", "query": "lucid dreaming research", "country": "CA",
     "verdict": "none_found", "advertisers": [], "own_ads": False, "note": None},
    {"candidate": "11bfc2efae5b44c9aa3e6893210a0d9b", "query": "lucid dream", "country": "CA",
     "verdict": "competitor_found", "advertisers": ["Yogi Wisdom"], "own_ads": False, "note": "speaks to age"},
]}


@pytest.fixture
def run(tmp_path, monkeypatch) -> RunFolder:
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = ld.build(folder)
    s = state.load(run)
    s.evidence = "trendsmesh"
    state.save(run, s)
    _write(run, f"{voice.STAGE}/voice_themes_v01.json", (FIXTURES / "ld_voice_themes.json").read_text(encoding="utf-8"))
    _write(run, "02_research/saturation_v01.json", SATURATION)
    mcp_saves.save(run, "ads_get_creatives", {"ad_account_id": "act_12345678"}, {"data": []})
    audience.record_hypothesis(run, test_audience._write_hypothesis(run))
    breakdown = test_audience._save(run, test_audience.AGE_GENDER_INPUT, test_audience._age_gender_rows(),
                                    test_audience.AFTER)
    audience.pick_audience(run, breakdown=breakdown)
    return run


def _write(run: RunFolder, rel: str, data) -> Path:
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _concept(brief: dict, cid: str) -> dict:
    return next(c for c in brief["concepts"] if c["id"] == cid)


def _text(problems) -> str:
    return "\n".join(f"{p.field}: {p.what} {p.todo}" for p in problems)


def _check(run, brief, stage="concepts"):
    return brief_checks.check(run, brief, stage, CFG)


def _set(brief: dict, cid: str, path: str, value) -> dict:
    node = brief["meta"] if cid == "meta" else _concept(brief, cid)
    *head, last = path.split(".")
    for key in head:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    return brief


def test_the_ld_brief_with_its_trend_ids_in_source_ref_passes_every_stage(run):
    brief = ld.brief()
    assert all("c2173b6a" not in r["source"] for r in _concept(brief, "C1")["glance"])
    assert _concept(brief, "C1")["glance"][0]["source_ref"].startswith("TrendsMesh trend c2173b6a")
    for stage in STAGES:
        assert _check(run, brief, stage) == [], stage


@pytest.mark.parametrize("cid, path, value, field, said", [
    ("C1", "glance.1.source", "02_research/saturation_v01.json, query \"gateway process\", CA",
     "concepts[0].glance[1].source", "concepts[0].glance[1].source shows a run file (02_research/saturation_v01.json). "
                                     "Say the source in words in source, and put the file in source_ref."),
    ("C1", "glance.0.source", "TrendsMesh: Rising hook \"day _ of _\", trend c2173b6a", "concepts[0].glance[0].source",
     "shows a trend id (c2173b6a)"),
    ("C2", "glance.2.text", f"Trend {C1} rose.", "concepts[1].glance[2].text", f"shows a trend id ({C1})"),
    ("C2", "note", {"title": "Mind the themes", "text": "T01, T06"}, "concepts[1].note.text", "shows a theme id (T01)"),
    ("C3", "hook.description", "From voice_themes_v01.json", "concepts[2].hook.description",
     "shows a run file (voice_themes_v01.json)"),
    ("C3", "beats.0.see", "as in 03_wip/scores_v01.json", "concepts[2].beats[0].see", "shows a run file"),
    ("C1", "why.0.source_label", "02_research/voice/reddit.jsonl", "concepts[0].why[0].source_label",
     "shows a run file"),
    ("C2", "customer_phrases.0.used_in", "hook, T08", "concepts[1].customer_phrases[0].used_in", "theme id (T08)"),
    ("meta", "title", "Brief b4f8d078", "meta.title", "shows a trend id (b4f8d078)"),
])
def test_visible_fields_refuse_codes_and_files(run, cid, path, value, field, said):
    problems = [p for p in _check(run, _set(ld.brief(), cid, path, value)) if p.field == field]
    assert problems and said in _text(problems), _text(_check(run, _set(ld.brief(), cid, path, value)))


def test_codes_and_files_stay_in_source_ref(run):
    brief = ld.brief()
    brief["audience"]["source_ref"] = "01_base/account_context.md; 02_research/voice/voice_themes_v01.json, T01 and T06"
    brief.setdefault("findings", {}).setdefault("items", [{"title": "t", "text": "x"}])[0]["source_ref"] = \
        "01_base/meta/ads_get_ad_entities_v03.json"
    for c in brief["concepts"]:
        for row in c["glance"][1:]:
            row["source_ref"] = "02_research/saturation_v01.json, query \"lucid dream\", CA"
    for stage in STAGES:
        assert _check(run, brief, stage) == [], stage
    brief["audience"]["source"] = "01_base/account_context.md"
    brief["findings"]["items"][0]["text"] += " (T08)"
    brief["findings"]["caveat"] = "see c2173b6a"
    assert {p.field for p in _check(run, brief)} == {"audience.source", "findings.items[0].text", "findings.caveat"}


def test_the_trend_row_names_the_trend_in_source_and_its_id_in_source_ref(run):
    brief = ld.brief()
    del _concept(brief, "C1")["glance"][0]["source_ref"]
    problems = _check(run, brief)
    assert [p.field for p in problems] == ["concepts[0].glance[0].source_ref"]
    assert "its id in source_ref" in _text(problems) and "c2173b6a" in _text(problems)
    brief = _set(ld.brief(), "C1", "glance.0.source", "TrendsMesh, pulled 4 November")      # the trend not named
    assert [p.field for p in _check(run, brief)] == ["concepts[0].glance[0].source"]
    assert "day _ of _" in _text(_check(run, brief))


def test_a_brief_with_a_code_in_a_glance_source_exits_2_naming_the_field(run, capsys):
    config.save(run, CFG)
    target = _write(run, "04_final/brief_pack_v01.json",
                    _set(ld.brief(), "C1", "glance.3.source", "02_research/saturation_v01.json"))
    code = main(["brief", "check", "--run", str(run.path), "--file", str(target), "--stage", "concepts", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and [p["field"] for p in out["problems"]] == ["concepts[0].glance[3].source"]
