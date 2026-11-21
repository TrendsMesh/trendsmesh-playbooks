"""The creator view of the brief page (CB13, issues #15 and #146): what it shows, and the production check that reads
it.

A made-up brief, public: the page needs only the fields `brief_page.render` asks for. The CB13 check reads data, never
words (issue #146): the run's own account figures in its saved Meta reads and the advertisers of its Ad Library
answers, in the creator view as the page builds it. Its figures are made up.
"""

import copy
import json
from datetime import date

import pytest

from tm import brief_checks, brief_page, mcp_saves
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

FOR_WHOM = "Night-shift nurses, 38% of last quarter's checkouts"
TREND_LINE = "Rising hook \"day _ of _\": 12 creators, 3.1M views"


def _brief() -> dict:
    concept = {
        "id": "C1", "brief_id": "B1", "title": "Day one of better evenings", "one_liner": "A diary of small wins.",
        "key_message": "Your evenings, a little calmer.", "hypothesis": "A diary hook holds attention.",
        "phone_note": "day 1 of trying it", "for_whom": FOR_WHOM, "trend_line": TREND_LINE,
        "glance": [{"label": "Trend", "text": "day _ of _", "source": "TrendsMesh"}],
        "hook": {"text": "Day 1 of trying this lamp", "description": "Hand-held, morning light."},
        "beats": [{"t0": 0, "t1": 3, "see": "A lamp on a desk", "hear": "Day one", "ost": "Day 1"}],
        "casting": "Someone in their thirties, relaxed.",
        "creator": {"role": "You tell your own diary.", "say": [{"moment": "Open", "line": "Day one."}],
                    "shots": [{"shot": "Lamp on", "framing": "Close", "takes": "3"}], "look": "Soft light.",
                    "send_back": ["Raw footage"], "deadline": None, "usage": None},
    }
    return {
        "meta": {"title": "Lumen lamp: three concepts", "market": "US", "language": "en", "prepared": "2026-11-01",
                 "valid_until": "2026-11-15", "recipients": ["decision", "strategy", "creator"],
                 "lede": {"decision": "Three concepts to approve.", "creator": "Your part in three short videos."},
                 "product": {"name": "Lumen", "plain_description": "A desk lamp that dims by itself.",
                             "plan": ["Turn it on", "Let it dim"], "price_note": "One price, no plan."},
                 "plugin": {"account_currency": "PLN"}},
        "tone": {"tone": "Warm and plain.", "must": ["Show the lamp"], "never": ["Hard sell"]},
        "concepts": [concept],
    }


@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)


def _said(problems) -> str:
    return "\n".join(f"{p.field}: {p.what}" for p in problems)


SPEND, CPA, RESULTS, RIVAL = "1234.56", "12.47", "305", "Rival Lamps"


def _account(run: RunFolder) -> None:
    """The run's saved account read (made-up figures, the Meta MCP's shapes: a list sent as a JSON text, `results`
    as values) and a saturation answer naming an advertiser."""
    rows = [{"age": "35-44", "gender": "female", "spend": SPEND, "cost_per_result": {"value": CPA, "unit": "PLN"},
             "results": {"values": [{"value": RESULTS}]}},
            {"age": "25-34", "gender": "male", "spend": 7, "results": {"values": [{"value": "1"}]}}]
    mcp_saves.save(run, "ads_get_ad_entities", {"ad_account_id": "act_1", "breakdowns": ["age", "gender"]},
                   {"data": json.dumps(rows)})
    sat = run.path / "02_research" / "saturation_v01.json"
    sat.parent.mkdir(parents=True, exist_ok=True)
    sat.write_text(json.dumps({"checks": [{"candidate": "x", "query": "desk lamp", "verdict": "competitor_found",
                                           "advertisers": [RIVAL, "Lumen"]}]}), encoding="utf-8")


def test_creator_header_shows_no_account_data():
    brief = _brief()
    creator = " ".join(brief_page.view_text(brief, "creator"))
    assert FOR_WHOM not in creator and TREND_LINE not in creator
    assert "day 1 of trying it" in creator and "Day one of better evenings" in creator   # phone note and title
    assert "Your part in three short videos." in creator and "Three concepts to approve." not in creator
    # issue #146: built from the creator fields only, so the one-liner and the key message are not on it
    assert "A diary of small wins." not in creator and "Your evenings, a little calmer." not in creator
    assert "Day 1 of trying this lamp" in creator and "You tell your own diary." in creator and "Warm and plain." in creator
    for view in ("decision", "strategy"):                  # the other views keep the header as it was
        shown = " ".join(brief_page.view_text(brief, view))
        assert FOR_WHOM in shown and TREND_LINE in shown
        assert "A diary of small wins." in shown and "Your evenings, a little calmer." in shown


def test_view_text_reads_what_the_page_hides_per_view():
    brief = _brief()
    creator = " ".join(brief_page.view_text(brief, "creator"))
    strategy = " ".join(brief_page.view_text(brief, "strategy"))
    assert "Your part" in creator and "Your part" not in strategy               # the creator's own part
    assert "Someone in their thirties" in strategy and "Someone in their thirties" not in creator   # casting
    assert "Your decision on C1" not in creator and "Your decision on C1" in strategy
    assert "recipient views" not in creator                                      # the script is not text


def test_account_figures_and_advertisers_are_the_runs_own(run):
    _account(run)
    figures = {shown: what for shown, what, _, _ in brief_checks.account_figures(run)}
    assert figures == {SPEND: "spend", CPA: "cost per result", RESULTS: "results"}   # "7" and "1" say nothing
    assert brief_checks.advertisers_seen(run, _brief()) == [RIVAL]                  # the product itself aside
    pattern = next(p for shown, _, _, p in brief_checks.account_figures(run) if shown == SPEND)
    for written in ("1234.56", "1,234.56", "1 234,56", "1.234,56", "1235", "1,235"):
        assert pattern.search(written), written
    for other in ("51234.56", "1234.567", "234.56"):
        assert not pattern.search(other), other


def test_production_check_refuses_the_runs_data_on_the_creator_view(run):
    _account(run)
    brief = _brief()
    assert brief_checks._production_checks(run, brief, {}) == []
    for path, text, value in ((("concepts", 0, "phone_note"), "under 1,234.56 a month", SPEND),
                              (("meta", "lede", "creator"), "Beat Rival Lamps at their own game", RIVAL),
                              (("concepts", 0, "title"), "12.47 a day", CPA),
                              (("concepts", 0, "hook", "text"), "305 people said yes", RESULTS),
                              (("meta", "title"), "Lumen versus Rival Lamps", RIVAL)):
        changed = copy.deepcopy(brief)
        where = changed
        for k in path[:-1]:
            where = where[k]
        where[path[-1]] = text
        said = _said(brief_checks._production_checks(run, changed, {}))
        field = ".".join(str(k) if isinstance(k, str) else f"[{k}]" for k in path).replace(".[", "[")
        assert field in said and f'"{value}"' in said and "CB13" in said, (field, said)


def test_ad_words_pass_in_every_language(run):
    """Issue #146: hooks and ad copy are shown as written: no word list, so "competitors" or "Ad Library" pass, in
    English as in Polish."""
    _account(run)
    brief = _brief()
    brief["concepts"][0]["hook"]["text"] = "DO NOT show this to your competitors..."
    brief["concepts"][0]["phone_note"] = "before it hits the Ad Library?"
    brief["concepts"][0]["creator"]["role"] = "Opowiadasz o konkurencji i o wydatkach, cost per checkout, ROAS."
    brief["meta"]["product"]["price_note"] = "Cheaper than a CPA course, about 20 PLN."
    assert brief_checks._production_checks(run, brief, {}) == []
    assert brief_checks._production_checks(run, brief, {"languages": {"working": "pl", "market": "pl"}}) == []


def test_production_check_catches_account_data_on_the_creator_view(run, monkeypatch):
    """The scan reads the built creator view, not a list of fields: were `for_whom` on it again (the bug of #15), the
    check would refuse the account figure in it."""
    _account(run)
    brief = _brief()
    brief["concepts"][0]["for_whom"] = "Night-shift nurses, 1,234.56 PLN spent on them"
    assert brief_checks._production_checks(run, brief, {}) == []
    monkeypatch.setattr(brief_page, "HEADER_FACTS_VIEWS", brief_page.ALL_VIEWS)
    said = _said(brief_checks._production_checks(run, brief, {}))
    assert "concepts[0].for_whom" in said and f'"{SPEND}"' in said


def test_production_check_keeps_the_usage_exception_and_the_view_gate(run):
    _account(run)
    brief = _brief()
    brief["concepts"][0]["creator"]["usage"] = "12 months of paid use, 1,234.56 PLN"   # the fee may be any number
    assert brief_checks._production_checks(run, brief, {}) == []
    brief = _brief()
    brief["concepts"][0]["hook"]["text"] = "We spent 1,234.56 on this"
    brief["meta"]["recipients"] = ["decision", "strategy"]          # no creator view on this page
    assert brief_checks._production_checks(run, brief, {}) == []
    brief["meta"]["recipients"] = ["decision", "creator"]
    assert "concepts[0].hook.text" in _said(brief_checks._production_checks(run, brief, {}))
