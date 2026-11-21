"""Issue #136: the organic video brief, O1 to O8, beside the ad brief: its steps and check-ins, its config, the
channel context, the checks at `organic_concepts` and `organic_views`, its page (the publisher view, the posting
plan) and its hand-off to organic video (a `seed/1` row with `source: pb2`)."""

import copy
import json
from datetime import date

import pytest

from tm import (audience, brief, brief_checks, brief_config, brief_organic, brief_page, checkins, flow, manifest,
                page_text, paths, seeds, state, stepchecks)
from tm.cli import main
from tm.flow import complete, decide
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

ORGANIC_STEPS = ["A0", "O1", "O2", "O3", "O4", "O5", "D2", "O7", "O8"]
ANSWERS = {
    "level": "every_step",
    "languages": {"working": "en", "market": "en"},
    "account": {"market": "US"},
    "product": {"name": "Example Bakery", "category_phrase": "sourdough baking"},
    "channel": {"name": "Example Bakery", "platforms": ["tiktok", "instagram"], "url": None,
                "description": "A home bakery channel: one loaf a week, start to finish.", "business": True},
    "organic": {"goal": "followers", "films": "self"},
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return folder


def _organic_run(ws, answers=ANSWERS) -> RunFolder:
    run = RunFolder.create(ws, "bakery", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    decide(run, "brief_kind", "organic", by="user", note=None, said="an organic video for our channel")
    complete(run, "A0")
    brief_config.write_from_intake(run, answers)
    return run


@pytest.fixture
def run(ws) -> RunFolder:
    """An organic run at O5's work: the config, a guess evidence and the persona from the description."""
    r = _organic_run(ws)
    s = state.load(r)
    s.evidence = "guess"
    state.save(r, s)
    hyp = r.path / "02_research" / "audience" / "hypothesis_v01.md"
    hyp.parent.mkdir(parents=True, exist_ok=True)
    hyp.write_text("Home bakers aged 25 to 45 who want a weekly loaf without fuss.\n", encoding="utf-8")
    audience.record_hypothesis(r, hyp)
    audience.pick_audience(r, no_data=True)
    return r


def _concept(cid: str, topic: str, fmt: str, hook_type: str, persona: str, licence: str = "commercial") -> dict:
    return {
        "id": cid, "brief_id": f"PB2-BAKERY-{cid}", "title": f"{topic.capitalize()} in one take",
        "one_liner": f"{topic.capitalize()}, shown as {fmt}.", "key_message": "A good loaf takes less than you think.",
        "hypothesis": f"This concept tests whether {topic} as {fmt} brings new followers.",
        "glance": [
            {"key": "guess", "label": "Hook (agent's guess)", "text": f"{hook_type} hook about {topic}",
             "source": "the agent's guess from the channel's own videos"},
            {"key": "channel", "label": "Channel", "text": "Weekly loaf videos, 30 to 45 seconds",
             "source": "the channel description, O2"},
            {"key": "persona", "label": "Persona", "text": "Home bakers 25 to 45 (directional)",
             "source": "the audience hypothesis, O3"},
        ],
        "hook": {"text": f"Nobody tells you this about {topic}", "style": "top"},
        "beats": [{"t0": 0, "t1": 3, "see": "Hands on the dough", "hear": "The hook", "ost": "Watch this",
                   "animatic": {"scene": "selfie_talk"}},
                  {"t0": 3, "t1": 30, "see": "The loaf comes out", "hear": "The steps", "ost": "Done",
                   "animatic": {"scene": "proof_card"}}],
        "plugin": {"candidate": f"guess:{topic.replace(' ', '-')}", "trend": None,
                   "axes": {"angle": topic, "hook_type": hook_type, "format": fmt, "persona": persona,
                            "awareness": "problem_aware"},
                   "saturation": None, "hook_image": {"relation": "consistent", "why": None},
                   "sound": {"licence": licence, "organic_only": licence != "commercial", "licensed_equivalent": None},
                   "thumbnail": "The loaf cut open, the words 'one loaf'", "directional": True},
        "organic": {"topic": topic, "format": fmt, "length_s": 30,
                    "sound": {"name": "Calm kitchen track", "trend_id": None, "licence": licence}},
        "creator": {"role": "You film yourself at home.", "say": [{"moment": "0-3 s", "line": "The hook"}],
                    "shots": [{"shot": "Dough close-up", "framing": "top", "takes": "3"}],
                    "send_back": ["Raw footage, 9:16"], "deadline": None, "usage": None},
        "editor": [{"label": label, "text": "as the beats say"} for label in brief_checks.EDITOR_ROWS],
        "posting": {
            "tiktok": {"description": f"How I bake {topic} every week. What do you bake on Sundays?",
                       "hashtags": ["#sourdough", "#homebaking", "#bread"], "post_time": "Tue 18:00",
                       "sound": "Calm kitchen track"},
            "instagram": {"description": f"{topic.capitalize()}, start to finish.",
                          "hashtags": ["#sourdough", "#homebaking"], "post_time": "Wed 12:00",
                          "sound": "Calm kitchen track"},
        },
    }


def organic_brief() -> dict:
    return {
        "meta": {"kind": "organic", "pack_id": "PB2-BAKERY-US-20261107", "title": "Example Bakery: three videos",
                 "market": "US", "language": "en", "prepared": "2026-11-07", "valid_until": "2026-11-21",
                 "recipients": ["decision", "creator", "editor", "publisher"],
                 "product": {"name": "Example Bakery", "plain_description": "A home bakery channel."},
                 "channel": {"name": "Example Bakery", "platforms": ["tiktok", "instagram"], "url": None,
                             "description": "A home bakery channel.", "business": True},
                 "plugin": {"evidence": "guess"}},
        "concepts": [_concept("C1", "starter care", "tutorial", "question", "beginners"),
                     _concept("C2", "shaping", "day in the life", "statement", "regulars"),
                     _concept("C3", "scoring patterns", "before and after", "challenge", "gift bakers")],
        "plan": {"posts": [{"concept": "C1", "platform": "tiktok", "date": "2026-11-10", "time": "18:00"},
                           {"concept": "C2", "platform": "instagram", "date": "2026-11-12", "time": "12:00"}],
                 "metrics": [{"name": n, "target": None, "source": "to set: no channel data"}
                             for n in ("views", "completion_rate", "saves", "shares")]},
    }


def _problems(run, data, stage):
    return brief_checks.check(run, data, stage, brief_config.config.load(run))


def _text(problems) -> str:
    return "\n".join(f"{p.field}: {p.what}" for p in problems)


# --- the steps and check-ins ------------------------------------------------------------------------------

def test_an_organic_run_goes_o1_to_o8(ws):
    run = _organic_run(ws)
    assert [st.id for st in flow._picture(state.load(run)).app] == ORGANIC_STEPS
    o = {st.id: st for st in flow.steps(CREATIVE_BRIEF)}
    assert [list(o[i].requires) for i in ("O1", "O2", "O3", "O4", "O5", "O7", "O8")] == [
        ["intake_written"], ["channel_context_written"], ["audience_picked"], ["trends_or_guess"],
        ["organic_concepts_checked", "page_built"], ["organic_views_checked", "page_built"],
        ["concepts_chosen", "page_built", "handed_off"]]
    assert all(o[i].skip_when == (("brief_kind", "ad"),) for i in ORGANIC_STEPS if i.startswith("O"))
    assert all(list(o[i].outputs) == ["organic_brief"] for i in ORGANIC_STEPS if i.startswith("O"))
    assert set(o["D2"].outputs) == {"briefs", "organic_brief"} and o["D2"].before == ("animatics",)
    assert (o["O1"].checkins, o["O7"].checkins) == (("G0o",), ("G4o",))


def test_the_organic_check_ins():
    cat = checkins.load(playbook=CREATIVE_BRIEF)
    g0o, g4o = cat.checkins["G0o"], cat.checkins["G4o"]
    assert (g0o.name, g0o.card, g0o.route) == ("Confirm the start card", "approve_setup",
                                               {"every_step": "own", "big_calls": "card", "hands_off": "rule"})
    assert (g4o.name, g4o.card, g4o.route) == ("Accept the brief views", "approve_briefs",
                                               {"every_step": "own", "big_calls": "card", "hands_off": "rule"})
    assert g4o.on_choice == {"accept": {"requires": ["concepts_chosen"]}}


def test_an_ad_run_never_sees_an_organic_step(ws, monkeypatch):
    monkeypatch.setattr(stepchecks, "run", lambda name, r: None)
    run = RunFolder.create(ws, "ad", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    decide(run, "brief_kind", "ad", by="user", note=None, said="an ad")
    complete(run, "A0")
    assert state.load(run).step == "A1"
    s = state.load(run)
    s.outputs, s.level = ["review_pack", "briefs", "page"], "every_step"
    state.save(run, s)
    assert not any(st.id.startswith("O") for st in flow._picture(state.load(run)).app)


def test_organic_walk_asks_g0o_then_animatics_then_g4o(ws, monkeypatch):
    monkeypatch.setattr(stepchecks, "run", lambda name, r: None)
    run = _organic_run(ws)
    seen = []
    for _ in range(40):
        nxt = flow.next(run)
        if nxt.action == "done":
            break
        if nxt.action == "work":
            complete(run, nxt.step)
            continue
        seen.append(nxt.checkin.ids[0])
        choice = "skip" if nxt.checkin.ids[0] == "animatics" else "accept"
        decide(run, nxt.checkin.ids[0], choice, by="user", note=None, said="ok")
    assert seen == ["G0o", "animatics", "G4o"]


# --- the config -----------------------------------------------------------------------------------------------

def test_an_organic_config_needs_no_landing_page_account_or_brand(ws):
    run = _organic_run(ws)
    assert brief_config.validate(run) == []
    cfg = brief_config.config.load(run)
    assert cfg["brief"]["recipients"] == ["decision", "creator", "editor", "publisher"]
    assert brief_config.intake_gap(run) is None


@pytest.mark.parametrize("path, value, field", [
    (("channel", "platforms"), [], "channel.platforms"),
    (("channel", "platforms"), ["myspace"], "channel.platforms"),
    (("channel", "business"), None, "channel.business"),
    (("channel", "name"), None, "channel.name"),
    (("organic", "goal"), "fame", "organic.goal"),
    (("organic", "films"), "robot", "organic.films"),
])
def test_an_organic_config_refuses_a_missing_channel_fact(ws, path, value, field):
    answers = copy.deepcopy(ANSWERS)
    answers[path[0]][path[1]] = value
    run = _organic_run(ws, answers)
    assert field in [p.field for p in brief_config.validate(run)]


def test_publisher_is_an_organic_view_and_media_buyer_an_ad_one(ws):
    answers = copy.deepcopy(ANSWERS)
    answers["brief"] = {"recipients": ["creator", "media-buyer"]}
    run = _organic_run(ws, answers)
    assert "brief.recipients" in [p.field for p in brief_config.validate(run)]


# --- O2: the channel context ----------------------------------------------------------------------------------

def test_channel_context_is_written_and_recorded(run):
    assert "01_base/channel_context.md" in brief_organic.channel_gap(run)
    path = run.path / "01_base" / "channel_context.md"
    path.write_text("Films: weekly loaves. Audience: home bakers.\n", encoding="utf-8")
    assert "recorded" in brief_organic.channel_gap(run)
    manifest.record(run, "01_base/channel_context.md", "01_base", "the user's description of the channel")
    assert brief_organic.channel_gap(run) is None


def test_page_fetch_takes_a_channel_page():
    page_text._check("https://www.tiktok.com/@examplebakery", "bakery", "channel", None)
    assert "channel" in page_text.KINDS


# --- O5 and O7: the checks ------------------------------------------------------------------------------------

def test_the_organic_brief_passes_both_stages(run):
    data = organic_brief()
    assert _text(_problems(run, data, "organic_concepts")) == ""
    assert _text(_problems(run, data, "organic_views")) == ""


def test_an_organic_brief_is_not_an_ad_brief(run):
    assert "meta.kind" in _text(_problems(run, organic_brief(), "concepts"))
    data = organic_brief()
    del data["meta"]["channel"]
    assert "brief.meta lacks channel" in _text(_problems(run, data, "organic_concepts"))


def test_no_customer_phrases_or_ad_library_rows_are_asked(run):
    data = organic_brief()
    for c in data["concepts"]:
        assert "customer_phrases" not in c and not any(r["key"] == "competition" for r in c["glance"])
    assert _problems(run, data, "organic_concepts") == []


def test_a_business_account_takes_only_sounds_licensed_for_business(run):
    data = organic_brief()
    data["concepts"][0] = _concept("C1", "starter care", "tutorial", "question", "beginners", licence="organic")
    said = _text(_problems(run, data, "organic_concepts"))
    assert "concepts[0].organic.sound" in said and "business" in said


def test_a_personal_account_takes_a_trending_sound_with_its_licence_shown(ws):
    answers = copy.deepcopy(ANSWERS)
    answers["channel"]["business"] = False
    r = _organic_run(ws, answers)
    s = state.load(r)
    s.evidence = "guess"
    state.save(r, s)
    hyp = r.path / "02_research" / "audience" / "hypothesis_v01.md"
    hyp.parent.mkdir(parents=True, exist_ok=True)
    hyp.write_text("Home bakers.\n", encoding="utf-8")
    audience.record_hypothesis(r, hyp)
    audience.pick_audience(r, no_data=True)
    data = organic_brief()
    data["meta"]["channel"]["business"] = False
    data["concepts"][0] = _concept("C1", "starter care", "tutorial", "question", "beginners", licence="organic")
    assert _problems(r, data, "organic_concepts") == []


def test_the_channel_and_persona_rows_are_asked(run):
    data = organic_brief()
    data["concepts"][1]["glance"] = data["concepts"][1]["glance"][:1]
    said = _text(_problems(run, data, "organic_concepts"))
    assert "Channel row" in said and "Persona row" in said


def test_two_organic_concepts_too_alike_are_refused(run):
    data = organic_brief()
    data["concepts"][1]["plugin"]["axes"] = dict(data["concepts"][0]["plugin"]["axes"])
    assert "axes" in _text(_problems(run, data, "organic_concepts"))


@pytest.mark.parametrize("change, said", [
    (lambda c: c["posting"]["tiktok"].update(hashtags=["#a", "#b", "#c", "#d", "#e", "#f"]), "hashtags"),
    (lambda c: c["posting"]["tiktok"].update(description="Bake along at https://example.com"), "link"),
    (lambda c: c["posting"].pop("instagram"), "instagram"),
    (lambda c: c["posting"]["tiktok"].update(post_time=""), "post_time"),
])
def test_the_publisher_view_keeps_the_platform_rules(run, change, said):
    data = organic_brief()
    change(data["concepts"][0])
    assert said in _text(_problems(run, data, "organic_views"))


def test_the_plan_measures_views_completion_saves_and_shares(run):
    data = organic_brief()
    data["plan"]["metrics"] = data["plan"]["metrics"][:3]
    assert "shares" in _text(_problems(run, data, "organic_views"))
    data = organic_brief()
    data["plan"]["metrics"][0].update(target="10000", source="")
    assert "plan.metrics[0].source" in _text(_problems(run, data, "organic_views"))
    data = organic_brief()
    data["plan"]["posts"][0]["concept"] = "C9"
    assert "C9" in _text(_problems(run, data, "organic_views"))


def test_check_command_marks_the_organic_stages(run, capsys):
    path = run.path / "04_final" / "brief_pack_v01.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(organic_brief()), encoding="utf-8")
    assert brief_checks.organic_concepts_gap(run) is not None
    for stage in ("organic_concepts", "organic_views"):
        assert main(["brief", "check", "--run", str(run.path), "--file", str(path), "--stage", stage, "--json"]) == 0
    capsys.readouterr()
    assert brief_checks.organic_concepts_gap(run) is None and brief_checks.organic_views_gap(run) is None


# --- the page -------------------------------------------------------------------------------------------------

def test_the_page_has_the_publisher_view_and_the_posting_plan():
    html, views = brief_page.body_html(organic_brief())
    assert views == ["decision", "creator", "editor", "publisher"]
    assert 'data-view="publisher"' in html and "#homebaking" in html and "Tue 18:00" in html
    assert "Posting plan" in html and "% watched to the end" in html
    text = " ".join(brief_page.view_text(organic_brief(), "publisher"))
    assert "#sourdough" in text and "Calm kitchen track" in text
    creator = " ".join(brief_page.view_text(organic_brief(), "creator"))
    assert "#sourdough" not in creator


# --- O8: the hand-off to organic video ------------------------------------------------------------------------

def _checked(run, capsys) -> None:
    """The organic brief written, checked at organic_views and every concept kept, as at O7 and G4o."""
    path = run.path / "04_final" / "brief_pack_v01.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(organic_brief()), encoding="utf-8")
    assert main(["brief", "check", "--run", str(run.path), "--file", str(path), "--stage", "organic_views",
                 "--json"]) == 0
    capsys.readouterr()
    brief_page.choose(run, "chat")


def test_the_hand_off_writes_a_pb2_seed_for_the_concept_named(run, ws, capsys):
    _checked(run, capsys)
    got = brief.handoff(run, to_video=["C2"])
    assert got["test_plan"] is False and got["seeds"] == [f"{run.path.name}:PB2-BAKERY-C2"]
    rows = seeds.rows(ws, source=seeds.PB2)
    assert len(rows) == 1
    row = rows[0]
    seeds.check(row)
    assert (row["source"], row["brief_id"], row["concept"], row["run"]) == ("pb2", "PB2-BAKERY-C2", "C2",
                                                                         run.path.name)
    assert (row["hook"], row["format"], row["length_s"], row["sound"]) == (
        "Nobody tells you this about shaping", "day in the life", 30,
        {"name": "Calm kitchen track", "trend_id": None, "licence": "commercial"})
    assert (row["category"], row["sub_category"], row["market"]) == ("sourdough baking", "sourdough baking", "US")
    assert (row["trend_id"], row["kind"], row["valid_until"], row["paid_level"]) == (None, None, "2026-11-21",
                                                                                      "not_checked")
    assert brief.handoff_gap(run) is None
    again = brief.handoff(run, to_video=["C2"])            # one seed per concept, never twice
    assert again["seeds"] == [] and again["seeds_there"] == [row["seed_id"]]
    assert len(seeds.rows(ws, source=seeds.PB2)) == 1


def test_without_a_yes_no_seed_is_written(run, ws, capsys):
    _checked(run, capsys)
    assert brief.handoff(run)["seeds"] == []
    assert seeds.rows(ws, source=seeds.PB2) == []


def test_only_a_kept_concept_of_an_organic_brief_is_handed_to_video(run, capsys):
    _checked(run, capsys)
    with pytest.raises(ValueError, match="C9"):
        brief.handoff(run, to_video=["C9"])


def test_an_ad_brief_hands_no_concept_to_video(ws):
    ad = RunFolder.create(ws, "ad", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    s = state.load(ad)
    s.outputs, s.brief = ["review_pack", "briefs", "page"], {"chosen": {"concepts": ["C1"]}}
    state.save(ad, s)
    with pytest.raises(ValueError, match="organic video brief"):
        brief.handoff(ad, to_video=["C1"])


def test_organic_video_starts_from_a_pb2_seed(run, ws, capsys, bundled_skills):
    _checked(run, capsys)
    seed_id = brief.handoff(run, to_video=["C1"])["seeds"][0]
    assert main(["seeds", "list", "--source", "pb2", "--json"]) == 0
    assert [r["seed_id"] for r in json.loads(capsys.readouterr().out)["seeds"]] == [seed_id]
    assert main(["run", "new", "--playbook", "organic-video", "--name", "loaf", "--seed", seed_id, "--json"]) == 0
    made = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    kept = json.loads((made.path / "00_raw" / "seed.json").read_text(encoding="utf-8"))
    assert (kept["source"], kept["hook"], kept["format"]) == ("pb2", "Nobody tells you this about starter care",
                                                              "tutorial")
    assert state.load(made).organic["seed"] == seed_id
    with pytest.raises(ValueError, match="pb4"):          # a creative brief starts from trend research picks only
        brief_config.find_seed(ws, seed_id)


def test_both_skills_say_how_they_split_the_work():
    root = paths.bundled_data().parent / "skills"
    cb = (root / "creative-brief" / "SKILL.md").read_text(encoding="utf-8")
    ov = (root / "organic-video" / "SKILL.md").read_text(encoding="utf-8")
    assert ("creative-brief is the brief for the people who will film the video; to have the video made here, "
            "that is organic-video.") in " ".join(cb.split())
    assert ("To brief people who will film a video themselves, that is creative-brief's organic video brief; "
            "organic-video makes the video itself.") in " ".join(ov.split())
