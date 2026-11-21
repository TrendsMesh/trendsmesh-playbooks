"""Issue #138 item 1: the variety rule of a batch of proposals (organic video C1). Each idea names a format rising now
among its trends; no two ideas share a format and a production type (unless the shortlist holds too few rising
formats); a channel with its own style gets at least one idea in another look (`plugin.look: other`), unless the user
said every idea keeps the channel's style. The proposals page counts the looks."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tm import i18n, organic_proposals, state, trends
from tm.cli import main
from tm.organic_pages import proposals as proposals_page
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

FMT_A, FMT_B, FMT_C = "f" * 8 + "a" * 4, "f" * 8 + "b" * 4, "f" * 8 + "c" * 4
TOPIC = "t" * 12


def _p(pid, production, trends_, look=None):
    plugin = {"production": production}
    if look:
        plugin["look"] = look
    return {"id": pid, "title": pid.upper(), "channel": "ch", "plugin": plugin, "trends": [{"id": t} for t in trends_]}


def _variety(proposals, rising, *, own_style=True, channel_only=False):
    out = []
    found = {p["id"]: [t["id"] for t in p["trends"]] for p in proposals}
    organic_proposals.variety(proposals, found, rising, {p["id"]: "ch" for p in proposals},
                              {"ch": own_style}, channel_only, out)
    return out


RISING = {FMT_A: "Ranking", FMT_B: "POV", FMT_C: "Quiz"}


def test_each_idea_names_a_rising_format_among_its_trends():
    found = _variety([_p("m1", "animation", [FMT_A], "other"), _p("m2", "ai_footage", [TOPIC], "channel")], RISING)
    assert [p.field for p in found] == ["m2.trends"]
    assert "rising" in found[0].what and "Ranking" in found[0].todo


def test_no_two_ideas_share_a_format_and_a_production_type():
    batch = [_p("m1", "animation", [FMT_A], "other"), _p("m2", "animation", [FMT_A], "channel"),
             _p("m3", "ai_footage", [FMT_A], "channel")]
    found = _variety(batch, RISING)
    assert [p.field for p in found] == ["m2.plugin.production"] and "M1" in found[0].what
    # the same format in another production type, or another format in the same type, is variety
    assert _variety([batch[0], _p("m2", "animation", [FMT_B], "channel"), batch[2]], RISING) == []


def test_too_few_rising_formats_allow_a_repeat():
    batch = [_p("m1", "animation", [FMT_A], "other"), _p("m2", "animation", [FMT_A], "channel"),
             _p("m3", "ai_footage", [FMT_A], "channel")]
    assert _variety(batch, {FMT_A: "Ranking"}) == []


def test_all_in_the_channels_style_is_refused_with_the_issues_words():
    batch = [_p("m1", "animation", [FMT_A], "channel"), _p("m2", "ai_footage", [FMT_B], "channel")]
    found = _variety(batch, RISING)
    assert [p.what for p in found] == [
        "All 2 proposals are in the channel's own style: make at least one in another look (plugin.look: other), "
        "from a format rising now."]
    assert _variety(batch, RISING, channel_only=True) == []          # the user said: all in my channel's style
    assert _variety(batch, RISING, own_style=False) == []            # a channel with no style of its own


def test_a_channel_with_its_own_style_names_each_ideas_look():
    found = _variety([_p("m1", "animation", [FMT_A]), _p("m2", "ai_footage", [FMT_B], "other")], RISING)
    assert [p.field for p in found] == ["m1.plugin.look"]
    assert _variety([_p("m1", "animation", [FMT_A]), _p("m2", "ai_footage", [FMT_B])], RISING, own_style=False) == []


def test_with_no_rising_format_a_different_production_type_is_enough():
    """#148 line 20: no format is rising, so the idea in another look differs by its production type."""
    same = [_p("m1", "animation", [TOPIC], "channel"), _p("m2", "animation", [TOPIC], "other")]
    found = _variety(same, {})
    assert [p.field for p in found] == ["m2.plugin.production"] and "no format is rising" in found[0].what
    assert _variety([same[0], _p("m2", "stills_motion", [TOPIC], "other")], {}) == []
    # and with every idea in the channel's look, the refusal says how to vary without a format
    found = _variety([same[0], _p("m2", "ai_footage", [TOPIC], "channel")], {})
    assert len(found) == 1 and "another look (plugin.look: other)" in found[0].what


def test_the_look_is_one_of_two_words():
    data = {"proposals": [{"plugin": {"look": "mine"}}]}
    assert organic_proposals.PLUGIN["properties"]["look"] == {"enum": ["channel", "other"]}
    assert "look" not in organic_proposals.PLUGIN["required"] and data   # a file written before it still checks


def _run(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "ideas", date(2026, 11, 20), playbook=ORGANIC_VIDEO)
    return run


def test_rising_formats_are_the_shortlists_format_cards_rising_now(tmp_path):
    run = _run(tmp_path)
    for tid, momentum in ((FMT_A, "rising"), (FMT_B, "holding")):
        trends.save_answer(run, "get_trend", {"trend_id": tid},
                           {"id": tid, "kind": "format_trend", "name": f"fmt {tid[-1]}", "momentum": momentum})
    shortlist = {"hooks": [], "topics": [], "sounds": [],
                 "formats": [{"id": FMT_A, "name": "fmt a"}, {"id": FMT_B, "name": "fmt b"},
                             {"id": FMT_C, "name": "fmt c", "momentum": "rising"}]}   # no card saved: its row says
    (run.path / "03_wip" / "trend_shortlist_v01.json").write_text(json.dumps(shortlist), encoding="utf-8")
    assert organic_proposals.rising_formats(run) == {FMT_A: "fmt a", FMT_C: "fmt c"}


def test_the_users_words_keep_every_idea_in_the_channels_style(tmp_path, capsys):
    run = _run(tmp_path)
    assert organic_proposals.channel_only(run) is False
    code = main(["organic", "looks", "--run", str(run.path), "--channel-only", "--json"])
    assert code == 1 and "--said" in json.loads(capsys.readouterr().out)["message"]
    code = main(["organic", "looks", "--run", str(run.path), "--channel-only", "--said", "all in my channel's style",
                 "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["channel_only"] is True
    assert state.load(run).organic["looks"]["said"] == "all in my channel's style"
    assert organic_proposals.channel_only(run) is True
    assert main(["organic", "looks", "--run", str(run.path), "--clear", "--json"]) == 0
    capsys.readouterr()
    assert organic_proposals.channel_only(run) is False


@pytest.mark.parametrize("lang", ["en", "pl"])
def test_the_page_counts_the_looks(lang):
    data = {"proposals": [_p("m1", "animation", [], "channel"), _p("m2", "animation", [], "channel"),
                          _p("m3", "ai_footage", [], "other")]}
    line = proposals_page.looks_line(data, i18n.translator(lang))
    assert line == ("2 ideas in your channel's style, 1 in other styles" if lang == "en"
                    else "2 pomysły w stylu Twojego kanału, 1 w innych stylach")
    assert proposals_page.looks_line({"proposals": [_p("m1", "animation", [])]}, i18n.translator(lang)) is None
