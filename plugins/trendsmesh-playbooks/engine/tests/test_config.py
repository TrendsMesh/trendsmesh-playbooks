"""config.yaml from the intake answers, and its validation."""

import json
from datetime import date

import pytest
from conftest import trend_steps_ready
import yaml

from tm import config, flow, state
from tm.cli import main
from tm.flow import complete, decide
from tm.runfolder import RunFolder
from test_flow import _finish, _settle, next_at

BASE = {
    "account": {"id": "12345678", "market": "PL", "language": "Polish"},
    "product": {"name": "Lucid Dreaming", "landing_url": "https://example.com/e-book"},
    "brand": {"assets_dir": "Desktop/Moje reklamy", "rules": "no health claims",
              "compliance": "music license"},
}


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy Łódź"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    trend_steps_ready(r)
    return r


def _write(run, **answers):
    return config.write_from_intake(run, {**BASE, **answers})


def _fields(run):
    return {p.field for p in config.validate(run)}


def test_defaults_match_playbook(run):
    path = _write(run, level="big_calls", outputs=["creative_brief"])
    assert path == run.path / "config.yaml"
    cfg = config.load(run)
    assert cfg["winner"]["window_days"] == 7
    assert cfg["winner"]["min_results"] == 30
    assert cfg["winner"]["drop_recent_days"] == 2
    assert cfg["winner"]["fade_cost_increase"] == 0.30
    assert cfg["winner"]["fade_p_value"] == 0.10
    assert cfg["winner"]["history_days"] == 90 and cfg["winner"]["rank_by"] == "value_to_recover"
    assert cfg["formats"]["placement_share_min"] == 0.25
    assert cfg["vo"]["stretch_max"] == 1.12 and cfg["vo"]["qa_tolerance"] == 0.10
    assert cfg["diagnosis"]["drop"] == 0.15
    assert (cfg["test"]["min_effect"], cfg["test"]["alpha"], cfg["test"]["power"],
            cfg["test"]["max_days"]) == (0.20, 0.10, 0.80, 14)
    assert cfg["generation"]["provider"] == "replicate"
    assert cfg["benchmark"]["source"] == "meta_ad_library"
    assert cfg["intake"]["voice_rights_confirmed"] is False
    assert cfg["library"]["path"] == "library/results.jsonl"
    assert cfg["mode"] == "hitl"


def test_intake_sets_the_run_state(run):
    _write(run, level="hands_off", outputs=["creative_brief", "edited_video"], flows=["V"],
           intake={"voice_rights_confirmed": True})
    s = state.load(run)
    assert (s.level, s.outputs, s.flows) == ("hands_off", ["creative_brief", "edited_video"], ["V"])
    assert config.load(run)["mode"] == "auto"
    assert "voice" in (run.path / "manifest.md").read_text(encoding="utf-8").lower()
    complete(run, "A0")     # `tm done A0` no longer refuses
    with pytest.raises(ValueError, match="already"):
        _write(run, level="hands_off", outputs=["creative_brief"])


def test_answers_override_thresholds(run):
    _write(run, level="every_step", outputs=["creative_brief"],
           winner={"fade_cost_increase": 0.4, "window_days": 14})
    cfg = config.load(run)
    assert cfg["winner"]["fade_cost_increase"] == 0.4 and cfg["winner"]["min_results"] == 30
    assert config.validate(run) == []


def test_rule_values_only_change_thresholds(run):
    _write(run, level="every_step", outputs=["creative_brief"])
    assert config.validate(run) == []
    path = run.path / "config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["skip_rule"] = "R1"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert "skip_rule" in _fields(run)
    del cfg["skip_rule"]
    cfg["winner"]["drop_recent_days"] = 0.5
    cfg["winner"]["window_days"] = 5          # not a multiple of 7
    cfg["winner"]["no_such_rule"] = True
    cfg["generation"]["provider"] = "higgsfield"
    cfg["benchmark"]["source"] = "foreplay"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert {"winner.drop_recent_days", "winner.window_days", "winner.no_such_rule",
            "generation.provider", "benchmark.source"} <= _fields(run)


def test_missing_inputs_are_reported_with_what_to_do(run):
    config.write_from_intake(run, {"level": "big_calls", "outputs": ["live_test", "creative_brief"]})
    problems = {p.field: p for p in config.validate(run)}
    assert {"account.id", "account.market", "languages", "product.name",
            "product.landing_url"} <= set(problems)
    p = problems["product.landing_url"]
    assert p.what and p.todo and "live test" in p.what.lower()


def test_voice_rights_needed_for_flow_v(run):
    _write(run, level="big_calls", outputs=["edited_video"], flows=["V"])
    assert "intake.voice_rights_confirmed" in _fields(run)
    _write_again = {**BASE, "level": "big_calls", "outputs": ["edited_video"], "flows": ["V"],
                    "intake": {"voice_rights_confirmed": True}}
    config.write_from_intake(run, _write_again)
    assert config.validate(run) == []


def test_hands_off_without_budget_keeps_paid_outputs_waiting(run):
    _write(run, level="hands_off", outputs=["creative_brief", "edited_video", "ai_video"])
    problems = config.validate(run)
    assert [p.field for p in problems] == ["budget.ai_usd"]
    assert problems[0].todo
    # free outputs go on; the first AI spend (D2) is where the run waits
    next_at(run, "D1")
    nxt = _finish(run, "D1")
    assert (nxt.action, nxt.checkin.ids) == ("auto", ["G6"])
    decide(run, "G6", "approve", by="rule", note="no limit in the config")
    nxt = _settle(run)
    assert (nxt.step, nxt.action) == ("D2", "stop")
    assert "AI" in nxt.message and "continues from the same place" in nxt.message
    s = state.load(run)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "budget_ai_usd"
    assert s.stops[-1]["engine"] is True
    from tm import budget
    budget.approve(run, "ai_usd", 12.0)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("D2", "work")
    assert state.load(run).status == "active"


def test_hands_off_budgets_in_the_config_are_approved(run):
    _write(run, level="hands_off", outputs=["ai_video", "live_test", "edited_video"], flows=["V"],
           intake={"voice_rights_confirmed": True},
           budget={"ai_usd": 15, "voice_credits": 20000, "test_per_day": 30, "test_days": 5})
    assert config.validate(run) == []
    assert state.load(run).budgets == {"ai_usd": 15, "voice_credits": 20000, "test": 150}


@pytest.mark.parametrize("missing,kinds", [
    ({"voice_credits": 5000, "test_per_day": 20, "test_days": 4}, ["budget.ai_usd"]),
    ({"ai_usd": 5, "test_per_day": 20, "test_days": 4}, ["budget.voice_credits"]),
    ({"ai_usd": 5, "voice_credits": 5000}, ["budget.test_per_day", "budget.test_days"]),
])
def test_hands_off_names_each_missing_budget(run, missing, kinds):
    _write(run, level="hands_off", outputs=["ai_video", "live_test", "edited_video"], flows=["V"],
           intake={"voice_rights_confirmed": True}, budget=missing)
    assert [p.field for p in config.validate(run)] == kinds


RECUT_AI = "Hands-off needs an AI budget before it repairs or generates shots for a re-cut."


def _with_flow_r(run):
    s = state.load(run)
    s.flows = ["R"]   # turned on after the diagnosis (`tm flow R`), never at intake
    state.save(run, s)


@pytest.mark.parametrize("cap", [3, 4, 5])
def test_hands_off_recut_above_level_2_needs_an_ai_budget(run, cap):
    _write(run, level="hands_off", outputs=["edited_video"], recut={"max_level": cap})
    problems = config.validate(run)                             # at intake, before any flow R
    assert [(p.field, p.what) for p in problems] == [("budget.ai_usd", RECUT_AI)]
    assert problems[0].todo
    _with_flow_r(run)
    assert [(p.field, p.what) for p in config.validate(run)] == [("budget.ai_usd", RECUT_AI)]
    _write(run, level="hands_off", outputs=["edited_video"], recut={"max_level": cap}, budget={"ai_usd": 4})
    assert config.validate(run) == []


@pytest.mark.parametrize("answers", [
    {"level": "hands_off", "recut": {"max_level": 2}},
    {"level": "hands_off", "recut": {"max_level": 0}},
    {"level": "hands_off"},                                     # unset: Hands-off stops at level 2
    {"level": "big_calls", "recut": {"max_level": 5}},          # G3r asks the user
    {"level": "hands_off", "outputs": ["creative_brief"], "recut": {"max_level": 5}},
])
def test_recut_needs_no_ai_budget_at_level_2_or_outside_hands_off(run, answers):
    _write(run, **{"outputs": ["edited_video"], **answers})
    _with_flow_r(run)
    assert config.validate(run) == []


def test_hands_off_ai_video_and_recut_name_the_ai_budget_once(run):
    _write(run, level="hands_off", outputs=["edited_video", "ai_video"], recut={"max_level": 4})
    _with_flow_r(run)
    assert [p.field for p in config.validate(run)] == ["budget.ai_usd"]


def test_budgets_are_not_required_outside_hands_off(run):
    _write(run, level="big_calls", outputs=["ai_video", "edited_video"], flows=["V"],
           intake={"voice_rights_confirmed": True})
    assert config.validate(run) == []
    # the live test is the exception (issue #22): picked, it comes with the user's daily budget and days
    _write(run, level="big_calls", outputs=["ai_video", "live_test"], intake={"voice_rights_confirmed": True})
    assert _fields(run) == {"budget.test_per_day", "budget.test_days"}


def test_budget_values_are_checked(run):
    _write(run, level="big_calls", outputs=["ai_video", "live_test"],
           budget={"ai_usd": -1, "test_per_day": 20, "test_days": 0})
    assert {"budget.ai_usd", "budget.test_days"} <= _fields(run)


def test_cli_config_write_and_check(run, tmp_path):
    answers = tmp_path / "answers ł.json"
    answers.write_text(json.dumps({**BASE, "level": "hands_off", "outputs": ["ai_video"]}),
                       encoding="utf-8")
    assert main(["config", "write", "--answers", str(answers), "--run", str(run.path), "--json"]) == 2
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 2
    answers.write_text(json.dumps({**BASE, "level": "hands_off", "outputs": ["ai_video"],
                                   "budget": {"ai_usd": 10}}), encoding="utf-8")
    assert main(["config", "write", "--answers", str(answers), "--run", str(run.path), "--json"]) == 0
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 0
    assert main(["config", "check", "--run", str(run.path / "nowhere"), "--json"]) == 1
