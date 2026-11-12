"""Create an ad (#98): the concepts check names each missing trend card and the step that saves it, and a paid call
runs only the line's own model, after the user confirmed a model name of theirs that did not name it plainly."""

import json

import pytest

from tm import create_plan

from test_create_costs import _checked_plan, _line, _music, _music_args, _plan_file
from test_create_plan import _check, _new, _write, concepts


@pytest.fixture
def run(tmp_path):
    return _new(tmp_path)


# --- S1: the trend cards ------------------------------------------------------------

def _trendsmesh(tmp_path):
    run = _new(tmp_path, evidence="trendsmesh")
    _write(run, "02_research/m1.json", {"saved": "an ad answer"})
    data = concepts()
    data["model_ads"][0].update(source="trendsmesh", saved="02_research/m1.json")
    data["trends"] = [{"id": "t1", "type": "hook", "source": "trendsmesh", "evidence": ["v1", "v2"]},
                      {"id": "t2", "type": "format", "source": "trendsmesh", "evidence": ["v3", "v4"]},
                      {"id": "t3", "type": "topic", "source": "trendsmesh", "evidence": ["v5", "v6"]}]
    data["concepts"][0]["trends"], data["concepts"][1]["trends"] = ["t1"], ["t1", "t2"]   # t3 is used by none
    return run, data


def test_each_trend_a_concept_uses_has_its_card_saved(tmp_path):
    run, data = _trendsmesh(tmp_path)
    _write(run, "02_research/trend_t1.json", {"answer": {}})     # one card is not enough for the others
    problems = _check(run, "concepts", data)
    said = [p for p in problems if "trend card" in p.what]
    assert [p.field for p in said] == ["trends[2]"]
    assert "02_research/trend_t2.json" in said[0].what
    assert "S1" in said[0].todo and "tm trends ingest" in said[0].todo and "get_trend" in said[0].todo
    _write(run, "02_research/trend_t2_v02.json", {"answer": {}})  # saved again: the next version counts too
    assert _check(run, "concepts", data) == []


# --- the model of a paid call ----------------------------------------------------------

def _spec(run, model, name="spec.json"):
    return str(_write(run, f"03_wip/{name}", {"model": model, "input": {"prompt": "a face"}}))


def _args(spec, name, cost):
    return [spec, "--run", "R", "--name", name, "--cost", str(cost)]


def test_the_call_runs_the_lines_own_model(run):
    _checked_plan(run, _line("faces", model="openai/gpt-image-2"))
    assert create_plan.guard(run, _args(_spec(run, "openai/gpt-image-2"), "faces", 0.4)) is None
    assert create_plan.guard(run, _args(_spec(run, "openai/gpt-image-2:abc123"), "faces", 0.4)) is None   # pinned
    said = create_plan.guard(run, _args(_spec(run, "black-forest-labs/flux-1.1-pro"), "faces", 0.4))
    assert "flux-1.1-pro" in said and "openai/gpt-image-2" in said and "Nothing was" in said
    _checked_plan(run, _line("faces", model="gpt-image-2"))      # a line naming the model without its owner
    assert create_plan.guard(run, _args(_spec(run, "openai/gpt-image-2"), "faces", 0.4)) is None


@pytest.mark.parametrize("named,confirmed,runs", [
    ("Seedance 2.0 at 720p", None, True),                       # the user's words name it plainly
    ("seedance-2.0", None, True),
    ("Gemini Sequence 2.0 720p", None, False),                  # they don't: one short question first
    ("Gemini Sequence 2.0 720p", "yes, Seedance 2.0", True),
    ("Gemini Sequence 2.0 720p", " ", False),
])
def test_a_model_name_of_the_users_that_does_not_name_it_is_confirmed_first(run, named, confirmed, runs):
    line = _line("retake", model="bytedance/seedance-2.0", cost=2.7, user_named=named,
                 **({"model_confirmed": confirmed} if confirmed is not None else {}))
    _checked_plan(run, line)
    said = create_plan.guard(run, _args(_spec(run, "bytedance/seedance-2.0"), "retake", 2.7))
    if runs:
        assert said is None
    else:
        assert "Do you mean" in said and "Seedance 2.0" in said and "model_confirmed" in said and "Nothing" in said


def test_an_elevenlabs_call_runs_the_lines_own_model(run):
    _checked_plan(run, _music())
    plan_rel = _plan_file(run)
    assert create_plan.voice_guard(run, _music_args(1550, plan_rel=plan_rel)) is None          # the default model
    said = create_plan.voice_guard(run, _music_args(1550, "03_wip/audio/music_v01.mp3", plan_rel,
                                                    "--model", "music_v1"))
    assert "music_v1" in said and "music_v2_5" in said
    _checked_plan(run, _music(user_named="the new Eleven music 3"))
    assert "Do you mean" in create_plan.voice_guard(run, _music_args(1550, plan_rel=plan_rel))


def test_the_names_are_compared_by_their_words():
    assert create_plan.names_model("Seedance 2.0 720p", "bytedance/seedance-2.0")
    assert create_plan.names_model("GPT Image 2", "openai/gpt-image-2")
    assert create_plan.names_model("bytedance/seedance-2.0", "bytedance/seedance-2.0")
    assert not create_plan.names_model("Gemini Sequence 2.0", "bytedance/seedance-2.0")
    assert not create_plan.names_model("Seedance 1.0", "bytedance/seedance-2.0")
    assert create_plan.model_label("bytedance/seedance-2.0") == "Seedance 2.0"
    assert json.dumps(create_plan.model_label("music_v2_5")) == '"music_v2_5"'
