"""The creator view of the brief page (CB13, issue #15): what it shows, and the production check that reads it.

A made-up brief, public: the page needs only the fields `brief_page.render` asks for, and the CB13 scan reads the
creator view as the page builds it.
"""

import copy
from datetime import date

import pytest

from tm import brief_checks, brief_page
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


def test_creator_header_shows_no_account_data():
    brief = _brief()
    creator = " ".join(brief_page.view_text(brief, "creator"))
    assert FOR_WHOM not in creator and TREND_LINE not in creator
    assert "day 1 of trying it" in creator and "Day one of better evenings" in creator   # phone note and title
    assert "Your part in three short videos." in creator and "Three concepts to approve." not in creator
    for view in ("decision", "strategy"):                  # the other views keep the header as it was
        shown = " ".join(brief_page.view_text(brief, view))
        assert FOR_WHOM in shown and TREND_LINE in shown


def test_view_text_reads_what_the_page_hides_per_view():
    brief = _brief()
    creator = " ".join(brief_page.view_text(brief, "creator"))
    strategy = " ".join(brief_page.view_text(brief, "strategy"))
    assert "Your part" in creator and "Your part" not in strategy               # the creator's own part
    assert "Someone in their thirties" in strategy and "Someone in their thirties" not in creator   # casting
    assert "Your decision on C1" not in creator and "Your decision on C1" in strategy
    assert "recipient views" not in creator                                      # the script is not text


def test_production_check_reads_the_creator_header(run):
    brief = _brief()
    assert brief_checks._production_checks(run, brief, {}) == []    # for_whom is not on the creator view
    for path, text in ((("concepts", 0, "phone_note"), "cheaper than the checkout"),
                       (("meta", "lede", "creator"), "Our ROAS doubled with this"),
                       (("concepts", 0, "title"), "The spending diary"),
                       (("meta", "title"), "Lumen: what Reddit says")):
        changed = copy.deepcopy(brief)
        where = changed
        for k in path[:-1]:
            where = where[k]
        where[path[-1]] = text
        said = _said(brief_checks._production_checks(run, changed, {}))
        field = ".".join(str(k) if isinstance(k, str) else f"[{k}]" for k in path).replace(".[", "[")
        assert field in said and "CB13" in said, (field, said)


def test_production_check_catches_account_data_on_the_creator_view(run, monkeypatch):
    """The scan reads the built creator view, not a list of fields: were `for_whom` on it again (the bug of #15), the
    check would refuse it."""
    brief = _brief()
    monkeypatch.setattr(brief_page, "HEADER_FACTS_VIEWS", brief_page.ALL_VIEWS)
    assert FOR_WHOM in " ".join(brief_page.view_text(brief, "creator"))
    said = _said(brief_checks._production_checks(run, brief, {}))
    assert "concepts[0].for_whom" in said and '"checkout"' in said


def test_production_check_keeps_the_usage_exception_and_the_view_gate(run):
    brief = _brief()
    brief["concepts"][0]["creator"]["usage"] = "12 months of paid use, 1,100 PLN"   # the fee in the account's money
    assert brief_checks._production_checks(run, brief, {}) == []
    brief = _brief()
    brief["concepts"][0]["key_message"] = "Lower cost per checkout"
    brief["meta"]["recipients"] = ["decision", "strategy"]          # no creator view on this page
    assert brief_checks._production_checks(run, brief, {}) == []
    brief["meta"]["recipients"] = ["decision", "creator"]
    assert "concepts[0].key_message" in _said(brief_checks._production_checks(run, brief, {}))
