"""Issue #87: the proposals' look (`plugin.aesthetic`), an animation's suggested styles (`plugin.styles`), the
channel's own style (`video_style` in the channel profile), what an AI video's route installs, and the risk level
counted from the risks' weights (data/organic-video/risks.yaml), not their number. No private data: each test makes
its own minimal proposal."""

import copy
import json
import re
from pathlib import Path

import pytest

from exampleedu import PROFILE as EXAMPLEEDU   # a made-up channel profile, typed as channel/1
from tm import atlas, brand, doctor, envtiers, i18n, organic_pages, organic_proposals
from tm.organic_pages import proposals as page
from tm.stops import Stop

OK = {"trendsmesh": "ok", "artifacts": "ok"}


def _proposal(production="stills_motion", hits=(), level="low", **plugin):
    return {
        "id": "m1", "channel": "ch", "title": "Five fruit you never heard of", "video_type": "Quiz",
        "approach": "Inspire", "why": "Rising now.", "trends": [{"id": "abcd1234", "role": "format", "pick": [0, 1]}],
        "beats": ["Hook", "Five cards", "Answer"], "length": "20 s",
        "recipe": {"production": "stills", "voice": "none", "music": "bed", "text": "captions in the edit"},
        "product": {"level": "not shown", "note": "nothing sold"},
        "risk": {"level": level, "items": ["named below"]},
        "cost": {"low": 0.1, "high": 0.4, "note": "two cards"},
        "plugin": {"production": production, "output": "video", "risk_hits": [dict(h) for h in hits],
                   "transfer": False, "weak_link": "loose", "series": None, "seed": None, **plugin},
    }


def _file(*proposals):
    return {"title": "Ideas", "date": "2026-11-12", "store": {"name": "ch", "note": "nothing sold"},
            "channels": [{"id": "ch", "name": "Channel", "niche": "facts"}], "proposals": list(proposals),
            "data_note": "TrendsMesh", "run": "runs/x", "lang": "en"}


def _risk(p):
    out = []
    organic_proposals._risk(p, p["id"], out)
    return out


def _look(p):
    out = []
    organic_proposals._look(p, p["id"], out)
    return out


TEXT_IN_EDIT = {"item": "model_text", "mitigation": "no text in any prompt", "case": "text_in_edit"}
ONE_IN_FRONT = {"item": "several_characters", "mitigation": "one person in front"}


# --- 4. the risk level from the weights ---------------------------------------------------------------

def test_every_risk_has_a_weight_for_every_production_type():
    weights = organic_proposals.risk_weights()
    assert set(weights["risks"]) == set(organic_proposals.RISK_ITEMS)
    for item, row in weights["risks"].items():
        assert set(row["weight"]) == set(organic_proposals.PRODUCTIONS), item
        assert set(row["weight"].values()) <= set(organic_proposals.RISK_LEVELS)


def test_the_owner_examples_weigh_as_the_issue_says():
    w = organic_proposals.weight
    assert w("several_characters", "stills_motion") == "low"
    assert w("several_characters", "ai_footage") == "medium"
    assert w("model_text", "stills_motion", "text_in_edit") == "none"
    assert w("model_text", "ai_footage", "text_in_edit") == "none"


def test_stills_with_text_in_the_edit_and_one_person_in_front_is_low():
    """The live run: two named risks, both covered. Under the count rule "low" was refused."""
    p = _proposal("stills_motion", [TEXT_IN_EDIT, ONE_IN_FRONT], "low")
    assert _risk(p) == []
    level, top = organic_proposals.risk_level(p)
    assert level == "low" and top["item"] == "several_characters"
    medium = _risk(_proposal("stills_motion", [TEXT_IN_EDIT, ONE_IN_FRONT], "medium"))
    assert [x.field for x in medium] == ["m1.risk.level"]
    assert "several characters" in medium[0].what and "low" in medium[0].todo


def test_the_level_is_the_highest_weight_not_the_count():
    assert _risk(_proposal("ai_footage", [ONE_IN_FRONT], "medium")) == []              # one risk, yet medium
    assert [x.field for x in _risk(_proposal("ai_footage", [ONE_IN_FRONT], "low"))] == ["m1.risk.level"]
    assert _risk(_proposal("talking_character", [ONE_IN_FRONT], "high")) == []
    assert _risk(_proposal("ai_footage", [], "low")) == []                             # none named: low
    assert [x.field for x in _risk(_proposal("ai_footage", [], "high"))] == ["m1.risk.level"]
    fast = {"item": "fast_motion", "mitigation": "slow it down"}
    assert _risk(_proposal("ai_footage", [ONE_IN_FRONT, fast], "high")) == []


def test_a_case_the_risk_does_not_have_is_refused():
    bad = {**ONE_IN_FRONT, "case": "text_in_edit"}
    assert [x.field for x in _risk(_proposal("stills_motion", [bad], "low"))] == ["m1.plugin.risk_hits[0].case"]


def test_the_page_says_where_the_level_comes_from():
    p = _proposal("ai_footage", [ONE_IN_FRONT, TEXT_IN_EDIT], "medium")
    line = page.risk_from(p, i18n.translator("en"))
    assert line == "Highest risk: several characters, in AI footage (medium)"
    covered = page.risk_from(_proposal("stills_motion", [TEXT_IN_EDIT], "low"), i18n.translator("en"))
    assert covered == "No risk is left once the named ones are covered"
    assert page.risk_from(_proposal("stills_motion", [], "low"), i18n.translator("en")) is None


# --- 1 and 2. the look and an animation's styles -------------------------------------------------------

def test_a_proposal_saved_before_the_look_still_checks():
    """Old files: no aesthetic, no styles, no case. The shape holds and the look check says nothing."""
    p = _proposal("animation", [], "low")
    assert organic_proposals.shape(_file(p)) == []
    assert _look(p) == []


def test_the_look_is_words_never_blank():
    assert _look(_proposal(aesthetic="realistic, 1990s home camcorder")) == []
    assert [x.field for x in _look(_proposal(aesthetic="  "))] == ["m1.plugin.aesthetic"]
    assert organic_proposals.shape(_file(_proposal(aesthetic=3))) != []


def _styles(*keys):
    return [{"style": k, "why": f"fits ({k})"} for k in keys]


def test_an_animation_suggests_two_or_three_catalogue_styles():
    assert _look(_proposal("animation", styles=_styles(7, "whiteboard"))) == []
    assert _look(_proposal("animation", styles=_styles(1, 2, 3))) == []
    for styles, field in ((_styles(7), "m1.plugin.styles"), (_styles(1, 2, 3, 4), "m1.plugin.styles"),
                          (_styles(7, "paper-layers"), "m1.plugin.styles[1].style"),     # 7 is paper-layers
                          (_styles(7, "no-such-style"), "m1.plugin.styles[1].style"),
                          ([{"style": 7, "why": " "}, {"style": 8, "why": "x"}], "m1.plugin.styles[0].why")):
        assert field in [x.field for x in _look(_proposal("animation", styles=styles))], styles
    assert [x.field for x in _look(_proposal("ai_footage", styles=_styles(7, 8)))] == ["m1.plugin.styles"]
    assert _look(_proposal("sections", styles=_styles(7, 8))) == []                       # an animation insert


def test_style_value_is_the_catalogue_number_and_name():
    assert organic_proposals.style_value(7) == organic_proposals.style_value("paper-layers")
    assert re.fullmatch(r"7 \S.*", organic_proposals.style_value(7))
    assert organic_proposals.style_value("nope") is None


# --- 3. the channel's own style ----------------------------------------------------------------------------

def _channel(**over):
    return {**copy.deepcopy(EXAMPLEEDU), **over}


def test_a_profile_saved_before_the_channel_style_still_checks():
    assert "video_style" not in EXAMPLEEDU
    assert brand.check(_channel()) == []
    assert brand.check(_channel(video_style=None)) == []
    assert brand.check(_channel(video_style="paper cut-out collage, old engravings, flat colour")) == []
    assert [p.field for p in brand.check(_channel(video_style=" "))] == ["video_style"]


def test_the_channel_style_comes_first_and_is_picked_in_advance():
    p = _proposal("animation", styles=_styles(7, 4))
    own = organic_proposals.style_options(p, _channel(video_style="paper cut-out collage"))
    assert [o["value"] for o in own] == ["channel", organic_proposals.style_value(7), organic_proposals.style_value(4)]
    assert own[0]["text"] == "paper cut-out collage"
    assert organic_proposals.default_style(p, _channel(video_style="paper cut-out collage")) == "channel"
    assert organic_proposals.default_style(p, _channel()) == organic_proposals.style_value(7)
    assert organic_proposals.style_options(_proposal("ai_footage"), _channel(video_style="collage")) == []
    old = _proposal("animation")                                         # no styles suggested: the channel's alone
    assert [o["value"] for o in organic_proposals.style_options(old, _channel(video_style="collage"))] == ["channel"]


def test_decisions_carry_the_look_and_the_style():
    p = _proposal("animation", styles=_styles(7, 4), aesthetic="flat paper, warm light")
    data = _file(p)
    defaults = {"ch": {"level": "every_step", "output": "video", "platforms": ["tiktok"], "video_style": None}}
    row = organic_proposals.decisions([], data, defaults)["m1"]
    assert row["aesthetic"] == "flat paper, warm light" and row["style"] == organic_proposals.style_value(7)
    doc = {"decision": "produce", "aesthetic": "black and white, grainy", "style": organic_proposals.style_value(4)}
    row = organic_proposals.decisions([("m1", doc)], data, defaults)["m1"]
    assert row["aesthetic"] == "black and white, grainy" and row["style"] == organic_proposals.style_value(4)
    odd = organic_proposals.decisions([("m1", {**doc, "style": "channel", "aesthetic": " "})], data, defaults)["m1"]
    assert odd["style"] == organic_proposals.style_value(7) and odd["aesthetic"] == "flat paper, warm light"
    own = {"ch": {**defaults["ch"], "video_style": "collage"}}
    assert organic_proposals.decisions([("m1", {**doc, "style": "channel"})], data, own)["m1"]["style"] == "channel"
    assert organic_proposals.decisions([], data, own)["m1"]["style"] == "channel"
    footage = organic_proposals.decisions([], _file(_proposal("ai_footage")), defaults)["m1"]
    assert footage["aesthetic"] is None and footage["style"] is None


# --- the page --------------------------------------------------------------------------------------------

def _render(p, lang="en", **kw):
    return page.render(_file(p), lambda tid: ({"kind": "format_trend", "name": "Fruit quiz", "reach": {}}, []),
                       lambda v: "", level="every_step", lang=lang, **kw)


def test_the_page_shows_the_look_the_styles_and_what_an_ai_video_installs():
    p = _proposal("animation", [TEXT_IN_EDIT], "low", styles=_styles(7, 4), aesthetic="flat paper, warm light")
    needs = {"m1": [{"what": "the animatic tools", "size": "150 MB", "minutes": 1}, {"what": "Chrome or Edge"}]}
    text = _render(p, profile={"ch": _channel(video_style="paper cut-out collage")}, needs=needs)
    assert "<dt data-plugin>Look</dt><dd data-plugin>flat paper, warm light</dd>" in text
    assert 'id="look-m1"' in text and ">flat paper, warm light</textarea>" in text
    assert "Your channel’s style" in text and "paper cut-out collage" in text
    first = re.search(r'name="s-m1" value="([^"]+)"( checked)?', text)
    assert first.group(1) == "channel" and first.group(2)                      # first, and picked
    assert "the animatic tools (about 150 MB, about 1 min)" in text and "Chrome or Edge" in text
    assert "No risk is left once the named ones are covered" in text
    meta = json.loads(re.search(r"window.__PROPOSALS__ = (\[.*?\]);", text).group(1).replace("<\\/", "</"))
    assert meta[0]["look"] == "flat paper, warm light" and meta[0]["style"] == "channel"


def test_a_page_of_old_proposals_has_none_of_it():
    text = _render(_proposal("stills_motion", [], "low"))
    assert "data-plugin" not in text and "look-m1" not in text and '"look"' not in text


def test_the_polish_page_has_the_new_words_in_polish():
    p = _proposal("ai_footage", [ONE_IN_FRONT], "medium", aesthetic="realistyczny, kamera VHS")
    text = _render(p, lang="pl", needs={"m1": [{"what": "x", "size": "2.5 GB", "minutes": 5}]})
    for english in ("Look", "Highest risk", "An AI video of this idea needs", "in AI footage"):
        assert english not in re.sub(r"<script>.*?</script>", "", text, flags=re.S), english


def test_copy_summary_reads_back_the_look_and_the_style():
    p = _proposal("animation", styles=_styles(7, 4), aesthetic="flat paper")
    seven = organic_proposals.style_value(7)
    line = f"M1 {p['title']}: produce, Check every step; output: video; look: grainy; b&w; style: {seven}; " \
           "platforms: tiktok; note: more cats"
    (pid, doc), = page.parse_summary(line, _file(p))
    assert doc["aesthetic"] == "grainy; b&w" and doc["style"] == seven and doc["note"] == "more cats"


# --- 2. what an AI video's route installs ----------------------------------------------------------------

def _plugin_folders(tmp_path, monkeypatch):
    """The plugin's folders as a session's set-up names them (~/.trendsmesh/paths.json exists only on a machine
    where the plugin ran, never on CI): the plugin itself, and a data folder of the test's own."""
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "plugin-data"))


def _tier_rows(**kw):
    r = doctor.check({"organic_video"}, False, OK, playbook="organic-video", **kw)
    return {i.id for i in r.items if i.id.startswith("tier_")}


def test_an_animation_asks_for_the_animatic_tools_not_breakdown_or_ai(tmp_path, monkeypatch):
    _plugin_folders(tmp_path, monkeypatch)
    assert _tier_rows() >= {"tier_breakdown", "tier_ai", "tier_video", "tier_voice"}     # as before
    assert "tier_animatic" not in _tier_rows()
    anim = _tier_rows(production="animation")
    assert "tier_breakdown" not in anim and "tier_ai" not in anim and {"tier_animatic", "tier_video"} <= anim
    assert _tier_rows(production="ai_footage") == _tier_rows()


def test_route_installs_lists_what_is_missing_once(monkeypatch):
    monkeypatch.setattr(envtiers, "installed", lambda t: t in ("base", "voice"))
    monkeypatch.setattr(atlas, "find_browser", lambda: None)
    needs = organic_proposals.route_installs("animation")
    assert [n.get("tier") for n in needs] == ["video", "animatic", None]
    assert needs[1]["size"] == "150 MB" and needs[2]["what"] == "Chrome or Edge"
    footage = organic_proposals.route_installs("ai_footage")
    assert [n["tier"] for n in footage] == ["breakdown", "video", "ai"]
    monkeypatch.setattr(envtiers, "installed", lambda t: True)
    monkeypatch.setattr(atlas, "find_browser", lambda: "/chrome")
    assert organic_proposals.route_installs("animation") == []


def test_the_installer_names_the_tier_it_installed(tmp_path, monkeypatch, capsys):
    _plugin_folders(tmp_path, monkeypatch)
    monkeypatch.setattr(envtiers.subprocess, "run", lambda *a, **kw: type("P", (), {"returncode": 0})())
    monkeypatch.setattr(atlas, "setup", lambda: None)
    assert envtiers.install("animatic", True) == 0
    out = capsys.readouterr().out
    assert out.strip().endswith("Installed the animatic tools (the 'animatic' tier).")


def test_a_video_in_sections_weighs_as_its_riskiest_type():
    """Its sections are written only at D1, so a proposal of one weighs each risk as the riskiest type could."""
    levels = organic_proposals.RISK_LEVELS
    for item, row in organic_proposals.risk_weights()["risks"].items():
        others = [w for t, w in row["weight"].items() if t != "sections"]
        assert row["weight"]["sections"] == max(others, key=levels.index), item
