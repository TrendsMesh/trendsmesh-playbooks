"""Create an ad's costs (#93): music priced per second at ElevenLabs' billed rate and held to it by the paid-call
guard, the music_v2_5 plan's shape, one plan line for several calls, and the spend on rejected takes kept apart."""

import json

import pytest

from tm import create_plan, music_models, state, tools
from tm.playbooks import CREATE_AD

from test_create_plan import _check, _fields, _new, _ready_for, _write, plan

PRICES = "02_research/prices_v01.json"


@pytest.fixture
def run(tmp_path):
    return _new(tmp_path)


def _line(item, **over):
    from test_create_plan import TODAY
    base = {"item": item, "type": "still", "stage": "pre_video", "model": "openai/gpt-image-2",
            "alternative": "flux", "cost": 0.4, "budget": "ai_usd", "checked": TODAY, "price_file": PRICES}
    base.update(over)
    return base


def _music(**over):
    return _line("music", **{"type": "music", "model": "music_v2_5", "alternative": "the user's track",
                             "budget": "voice_credits", "seconds": 20, "cost": 1550, **over})


def _plan_with(*lines):
    """The test plan with `lines`: one with the item of a line there takes its place, the others come after."""
    data = plan()
    for line in lines:
        at = next((n for n, ln in enumerate(data["lines"]) if ln["item"] == line["item"]), None)
        if at is None:
            data["lines"].append(line)
        else:
            data["lines"][at] = line
    return data


def _checked_plan(run, *lines):
    _ready_for(run, create_plan.PLAN)
    assert _check(run, create_plan.PLAN, _plan_with(*lines)) == []


# --- the price table -----------------------------------------------------------------

def test_music_is_priced_per_second_at_the_billed_rate():
    assert music_models.credits(20, "music_v2_5") == 1550          # the owner's live run: about 1,550 for 20 s
    assert music_models.credits(14.5, "music_v2_5") == 1124        # rounded up to a whole credit
    assert music_models.rate("music_v9") == music_models.OTHER >= music_models.rate("music_v2_5")
    assert music_models.rate("music_v2_5") > music_models.DOCS_RATE   # billed above the docs' approximate rate
    table = music_models.table()
    assert table["checked"] == music_models.CHECKED and table["models"]["music_v2_5"]["credits_per_second"] == 77.5


def test_the_v2_5_plan_is_chunks_and_v1s_shape_is_refused():
    good = {"chunks": [{"song_id": "s1", "range": {"start_ms": 0, "end_ms": 10000}},
                       {"text": "[Main Theme]", "duration_ms": 10000, "positive_styles": ["ambient"]}]}
    assert music_models.plan_problems(good, "music_v2_5") == []
    assert music_models.plan_problems(music_models.V2_EXAMPLE, "music_v2_5") == []
    assert music_models.plan_seconds(good) == 20
    v1 = {"positive_global_styles": ["pop"], "negative_global_styles": [],
          "sections": [{"section_name": "Intro", "positive_local_styles": ["warm"], "negative_local_styles": [],
                        "duration_ms": 10000, "lines": []}]}
    said = music_models.plan_problems(v1, "music_v2_5")
    assert said and "chunks" in said[0] and "music_v1" in said[0]
    assert music_models.plan_problems(v1, "music_v1") == [] and music_models.plan_seconds(v1) == 10
    assert "chunks" in music_models.plan_problems(good, "music_v1")[0]
    short = {"chunks": [{"text": "x", "duration_ms": 1000, "positive_styles": ["a"]}]}
    assert "duration_ms" in music_models.plan_problems(short, "music_v2_5")[0]
    assert "positive_styles" in music_models.plan_problems({"chunks": [{"text": "x", "duration_ms": 5000}]})[0]


# --- the plan's music line and lines for several calls --------------------------------

def test_a_music_line_costs_at_least_its_seconds_at_the_rate(run):
    _ready_for(run, create_plan.PLAN)
    cheap = _music(cost=440, calls=2, cost_per_call=220)          # Refresh an ad's 220 a take, for 20 s takes
    problems = _check(run, create_plan.PLAN, _plan_with(cheap))
    assert "lines[2].cost" in _fields(problems)
    said = " ".join(p.what for p in problems)
    assert "1550" in said and "77.5" in said and "music_v2_5" in said
    no_seconds = _music()
    no_seconds.pop("seconds")
    assert "lines[2].seconds" in _fields(_check(run, create_plan.PLAN, _plan_with(no_seconds)))
    assert _check(run, create_plan.PLAN, _plan_with(_music(cost=3100, calls=2, cost_per_call=1550))) == []
    assert state.load(run).planned["voice_credits"] == 3100


@pytest.mark.parametrize("over,field", [
    ({"calls": 0, "cost_per_call": 0.128}, "lines[4].calls"),
    ({"calls": 2.5, "cost_per_call": 0.128}, "lines[4].calls"),
    ({"calls": 3}, "lines[4].cost_per_call"),
    ({"calls": 3, "cost_per_call": 0.2, "cost": 0.384}, "lines[4].cost"),   # the calls cost more than the line
])
def test_a_line_for_several_calls_is_checked(run, over, field):
    _ready_for(run, create_plan.PLAN)
    assert field in _fields(_check(run, create_plan.PLAN, _plan_with(_line("faces", **{"cost": 0.384, **over}))))


def _args(name, cost):
    return ["spec.json", "--run", "R", "--name", name, "--cost", str(cost)]


def test_one_line_runs_its_calls_with_different_prompts_inside_its_total(run):
    _checked_plan(run, _line("faces", cost=0.384, calls=3, cost_per_call=0.128))
    assert "is not faces's line" in create_plan.guard(run, _args("faces", 0.384))   # one call at the call's cost
    assert create_plan.guard(run, _args("faces", 0.128)) is None
    for n in (1, 2):
        _write(run, f"03_wip/faces_v0{n}.run.json", {"status": "done"})
    _write(run, "03_wip/faces_v03.run.json", {"status": "failed"})                    # a failed call cost nothing
    assert create_plan.guard(run, _args("faces", 0.128)) is None
    _write(run, "03_wip/faces_v04.run.json", {"status": "done"})
    said = create_plan.guard(run, _args("faces", 0.128))
    assert "3 calls" in said and "Nothing was" in said
    assert create_plan.guard(run, _args("casting", 0.4)) is None   # a line without calls runs as before


# --- the ElevenLabs guard --------------------------------------------------------------

def _plan_file(run, seconds=20, name="music_plan.json"):
    data = {"chunks": [{"text": "[Theme]", "duration_ms": seconds * 1000, "positive_styles": ["pop"]}]}
    _write(run, f"03_wip/audio/{name}", data)
    return f"03_wip/audio/{name}"


def _music_args(cost, out="03_wip/audio/music_v01.mp3", plan_rel="03_wip/audio/music_plan.json", *extra):
    return ["music-compose", "--run", "R", "--plan", plan_rel, "--cost", str(cost),
            *(["--out", out] if out else []), *extra]


def test_the_music_take_runs_only_inside_its_line_at_the_rate(run):
    _checked_plan(run, _music(cost=3100, calls=2, cost_per_call=1550))
    plan_rel = _plan_file(run)
    assert create_plan.voice_guard(run, _music_args(1550, plan_rel=plan_rel)) is None
    assert "is not music's line" in create_plan.voice_guard(run, _music_args(220, plan_rel=plan_rel))
    assert "--out" in create_plan.voice_guard(run, _music_args(1550, out=None, plan_rel=plan_rel))
    assert "not a line" in create_plan.voice_guard(run, _music_args(1550, out="03_wip/audio/jingle_v01.mp3",
                                                                    plan_rel=plan_rel))
    long = _plan_file(run, seconds=30, name="long.json")                        # 30 s is 2325 credits
    said = create_plan.voice_guard(run, _music_args(1550, plan_rel=long))
    assert "2325" in said and "Nothing was" in said
    v1 = _write(run, "03_wip/audio/v1.json", {"positive_global_styles": ["pop"], "negative_global_styles": [],
                                              "sections": []})
    assert "chunks" in create_plan.voice_guard(run, _music_args(1550, plan_rel=str(v1)))


def test_the_music_line_counts_its_takes(run):
    _checked_plan(run, _music(cost=3100, calls=2, cost_per_call=1550))
    plan_rel = _plan_file(run)
    for n in (1, 2):
        _write(run, f"03_wip/audio/music_v0{n}.mp3.json", {"kind": "music_take", "credits_used": 1550})
    said = create_plan.voice_guard(run, _music_args(1550, out="03_wip/audio/music_v03.mp3", plan_rel=plan_rel))
    assert "2 calls" in said


def test_other_voice_calls_and_free_ones_are_not_held(run):
    _checked_plan(run)
    assert create_plan.voice_guard(run, ["isolate", "--run", "R", "a.mp3", "--cost", "100"]) is None


def test_the_voice_guard_is_create_ads_precheck_for_elevenlabs(run, monkeypatch):
    seen = []
    monkeypatch.setattr(create_plan, "voice_guard", lambda r, a: seen.append(a) or "held")
    assert tools.PRECHECK[CREATE_AD]["elevenlabs"] == "tm.create_plan:voice_guard"
    assert tools._precheck(run, "elevenlabs", _music_args(1550)) == "held" and seen


# --- the spend on rejected takes --------------------------------------------------------

def _storyboard_yes(run):
    from test_create_plan import storyboard
    from tm import flow
    _ready_for(run, create_plan.STORYBOARD)
    assert _check(run, create_plan.STORYBOARD, storyboard()) == []
    s = state.load(run)
    s.decisions.append({"checkin": "storyboard", "choice": "approve", "by": "user", "at": flow._now()})
    state.save(run, s)


def test_a_redo_books_the_take_it_replaces_as_rejected(run):
    _storyboard_yes(run)
    _write(run, "03_wip/presenter-take_v01.run.json", {"status": "done"})
    entry = create_plan.redo(run, "presenter_take", "the second line stutters, make it again")
    rejected = state.load(run).ad["rejected"]
    assert rejected == [{"item": "presenter-take", "take": "03_wip/presenter-take_v01.run.json", "kind": "ai_usd",
                         "amount": 1.5, "note": "the second line stutters, make it again", "by": "user",
                         "at": rejected[0]["at"]}]
    assert entry["rejected"] == 1.5
    costs = create_plan.costs(run)
    assert costs["kinds"]["ai_usd"]["rejected"] == 1.5 and costs["kinds"]["voice_credits"]["rejected"] == 0


def test_a_take_turned_down_for_a_new_line_is_booked_once(run):
    _storyboard_yes(run)
    _write(run, "03_wip/presenter-take_v01.run.json", {"status": "done"})
    _write(run, "03_wip/presenter-take_v02.run.json", {"status": "failed"})   # cost nothing, not booked
    booked = create_plan.reject(run, "presenter_take", "not this person; take the other model")
    assert [b["take"] for b in booked] == ["03_wip/presenter-take_v01.run.json"]
    assert create_plan.reject(run, "presenter_take", "again") == []           # each take once
    with pytest.raises(ValueError, match="no paid take"):
        create_plan.reject(run, "casting", "no")
    with pytest.raises(ValueError, match="own words"):
        create_plan.reject(run, "presenter_take", " ")


def test_a_music_take_is_booked_at_what_it_cost(run):
    _checked_plan(run, _music(cost=3100, calls=2, cost_per_call=1550))
    _write(run, "03_wip/audio/music_v01.mp3.json", {"kind": "music_take", "credits_used": 1490})
    booked = create_plan.reject(run, "music", "too slow")
    assert booked[0]["kind"] == "voice_credits" and booked[0]["amount"] == 1490


def test_a_take_of_a_line_a_new_plan_dropped_is_priced_from_the_older_plan(run):
    _checked_plan(run, _line("faces", cost=0.384, calls=3, cost_per_call=0.128))
    _write(run, "03_wip/faces_v01.run.json", {"status": "done"})
    assert _check(run, create_plan.PLAN, plan()) == []                      # the new version has no faces line
    assert create_plan.reject(run, "faces", "use the new casting")[0]["amount"] == 0.128


def test_tm_ad_costs_shows_the_rejected_spend_on_its_own_line(run, capsys):
    from tm.cli import main
    _storyboard_yes(run)
    s = state.load(run)
    s.budgets, s.spend = {"ai_usd": 6.0, "voice_credits": 900}, {"ai_usd": 3.4, "voice_credits": 0}
    state.save(run, s)
    _write(run, "03_wip/presenter-take_v01.run.json", {"status": "done"})
    assert main(["ad", "reject", "--run", str(run.path), "--item", "presenter_take", "--note", "no", "--json"]) == 0
    capsys.readouterr()
    assert main(["ad", "costs", "--run", str(run.path)]) == 0
    text = capsys.readouterr().out
    lines = text.splitlines()
    assert any("3.4" in ln and "6" in ln for ln in lines)
    assert any("rejected" in ln and "1.5" in ln for ln in lines)
    assert main(["ad", "costs", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kinds"]["ai_usd"] == {"approved": 6.0, "planned": 1.9, "spent": 3.4, "rejected": 1.5}


def test_tm_ad_prices_saves_the_dated_price_file(run, capsys):
    from tm.cli import main
    assert main(["ad", "prices", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    saved = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))
    assert out["file"].startswith("02_research/elevenlabs_prices_v") and out["checked"] == saved["checked"]
    assert saved["music"]["models"]["music_v2_5"]["credits_per_second"] == 77.5
    assert saved["music"]["checked"] == music_models.CHECKED and "eleven_v4" in saved["tts"]["models"]
    _ready_for(run, create_plan.PLAN)
    assert _check(run, create_plan.PLAN, _plan_with(_music(price_file=out["file"], checked=out["checked"]))) == []
