"""Organic video's config.yaml (playbook 03): the defaults (PLAYBOOK.md §7 and the plan's numbers),
the A0 intake, its checks and the `organic_intake_written` step check."""

import json
from datetime import date

import pytest

from test_channel_profile import EXAMPLEEDU
from tm import brand, config, organic, organic_config, state
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

ANSWERS = {"level": "every_step", "outputs": ["proposals"], "channels": ["ExampleEdu"],
           "chat_language": "pl", "audience_language": "pl"}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "exampleedu", date(2026, 11, 7), playbook=ORGANIC_VIDEO)


def _problems(run):
    return {p.field: p for p in organic_config.validate(run)}


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_defaults_match_playbook_config(run):
    """config.yaml's defaults: PLAYBOOK.md §7's numbers and the plugin's own defaults that the plan's Global
    Constraints name (the OV numbers that live in later tasks' checks, such as the kit's caps, are theirs)."""
    path = config.write_from_intake(run, ANSWERS)     # config hands an organic run to organic_config
    assert path == run.path / "config.yaml"
    cfg = config.load(run)
    expected = {
        "weekly.per_week": 5, "weekly.days": ["mon", "wed", "fri", "sat", "sun"], "weekly.flexible_day": "sun",
        "weekly.run_day": "sun", "weekly.rhythm": "all_at_once",
        "generation.provider": "replicate", "generation.quality_tier": "default", "generation.resolution": "768p",
        "generation.upscale": "none",
        "budget.per_run_usd": 5, "budget.per_week_usd": 5, "publishing.tool": "none",
        "mode.variant": "gated", "mode.gates": ["pack", "images", "video", "edit"],
        "currency": "USD", "fx_rate": None, "output": "script", "kind": "proposals",
        "pricing.max_age_days": 7,
        "qa.transcript_min": 0.9, "qa.wps_min": 2.8, "qa.wps_max": 3.0, "qa.tail_s": 1.5, "qa.speed_max": 1.25,
        "qa.take_max_s": 15, "qa.lufs_target": -14, "qa.lufs_asmr": -16, "qa.lufs_usable": [-30, -5],
        "qa.cut_flag_s": 1.0, "qa.upload_max_mb": 15, "qa.preview_crf": 27, "qa.upload_crf": [26, 28],
        "safe_zone.x": [90, 880], "safe_zone.y": [260, 1540], "safe_zone.atlas_text_max_y": 1260,
        "proposals.min": 4, "proposals.max": 6,
        "research.cards": 12, "research.recent_days": 7,
        "animation.fps": 30,
    }
    for key, value in expected.items():
        assert config.get(cfg, key) == value, key
        assert config.get(organic_config.DEFAULTS, key) == value, key
    assert cfg["channels"] == ["exampleedu"] and organic_config.DEFAULTS["channels"] == []
    assert organic_config.OUTPUTS_READY == ("script", "ai_video", "weekly_pack")   # every output (PR E, Task 21)
    assert set(organic_config.FIXED) == {"generation.provider", "publishing.tool"}
    assert organic_config.validate(run) == []


def test_intake_sets_level_outputs_and_kind(run):
    organic_config.write_from_intake(run, {**ANSWERS, "level": "big_calls"})
    s = state.load(run)
    assert (s.level, s.outputs) == ("big_calls", ["proposals"])
    cfg = config.load(run)
    assert cfg["kind"] == "proposals" and cfg["mode"]["variant"] == "gated"
    assert not set(cfg) & {"level", "outputs", "chat_language", "audience_language"}   # intake-only
    with pytest.raises(ValueError, match="hands-off|Check every step|level"):
        organic_config.write_from_intake(run, {**ANSWERS, "level": "sometimes"})
    for outputs in (["script_to_film"], ["proposals", "weekly_plan"], [], "proposals"):
        with pytest.raises(ValueError, match="outputs"):
            organic_config.write_from_intake(run, {**ANSWERS, "outputs": outputs})


def test_weekly_plan_is_a_week_run(run):
    """PR E (Task 21): the weekly pack is built, so the intake takes a week run and the config the weekly_pack
    output."""
    organic_config.write_from_intake(run, {**ANSWERS, "outputs": ["weekly_plan"], "output": "weekly_pack"})
    assert state.load(run).outputs == ["weekly_plan"] and config.load(run)["kind"] == "weekly_plan"
    assert "output" not in _problems(run)
    with pytest.raises(ValueError, match="outputs must be one of"):
        organic_config.write_from_intake(run, {**ANSWERS, "outputs": ["organic_video"]})


NO_LEVEL = {k: v for k, v in ANSWERS.items() if k != "level"}


def test_mode_variant_maps_to_level(ws):
    for name, variant, level in (("az", "az", "hands_off"), ("gated", "gated", "every_step")):
        run = RunFolder.create(ws, name, date(2026, 11, 7), playbook=ORGANIC_VIDEO)
        organic_config.write_from_intake(run, {**NO_LEVEL, "mode": {"variant": variant}})
        assert state.load(run).level == level                      # no level yet: the variant sets it
    run = RunFolder.create(ws, "levels", date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    organic_config.write_from_intake(run, {**ANSWERS, "level": "hands_off"})
    assert config.load(run)["mode"]["variant"] == "az" and organic_config.validate(run) == []
    organic_config.write_from_intake(run, {**ANSWERS, "level": "big_calls", "mode": {"variant": "az"}})
    assert state.load(run).level == "big_calls" and config.load(run)["mode"]["variant"] == "gated"   # the level wins


def test_level_set_with_tm_level_wins_over_the_variant(run, capsys, bundled_skills):
    """`tm level` first, then `tm config write` with a variant: the user's level stays (both orders happen)."""
    assert _cli(capsys, "level", "big_calls", "--run", str(run.path))[0] == 0
    for variant in ("az", "gated"):
        (run.path / "answers.json").write_text(json.dumps({**NO_LEVEL, "mode": {"variant": variant}}), encoding="utf-8")
        code, out = _cli(capsys, "config", "write", "--run", str(run.path), "--answers", "answers.json")
        assert code == 0, out
        assert state.load(run).level == "big_calls" and config.load(run)["mode"]["variant"] == "gated"
    for bad in ("sometimes", ["az"], {"az": True}):
        (run.path / "answers.json").write_text(json.dumps({**NO_LEVEL, "mode": {"variant": bad}}), encoding="utf-8")
        code, out = _cli(capsys, "config", "write", "--run", str(run.path), "--answers", "answers.json")
        assert code == 1 and "mode.variant must be one of gated, az" in out["message"], bad
    assert state.load(run).level == "big_calls" and config.load(run)["mode"]["variant"] == "gated"


def test_higgsfield_and_publishing_tool_not_supported_yet(run):
    organic_config.write_from_intake(run, {**ANSWERS, "generation": {"provider": "higgsfield"},
                                           "publishing": {"tool": "buffer_mcp"}})
    p = _problems(run)
    assert p["generation.provider"].what.startswith("Higgsfield is not supported yet: generation uses Replicate")
    assert p["publishing.tool"].what.startswith(
        "Posting through a tool is not supported yet: you download from the page and post")
    for problem in (p["generation.provider"], p["publishing.tool"]):
        assert organic_config.ISSUES in problem.what
    assert p["generation.provider"].todo == "Set generation.provider to replicate."
    assert p["publishing.tool"].todo == "Set publishing.tool to none."


@pytest.mark.parametrize("chat, working", [("de", "de"), ("en", "en"), ("pl", "pl"), ("PL", "pl"), ("en-GB", "en-GB"),
                                           ("Polish", "pl")])
def test_the_chat_language_is_the_working_language(run, chat, working):
    """Issue #3: any language, not English or Polish alone; the page falls back to English only while the language
    has no translated table (tm i18n), and says so when it is built."""
    organic_config.write_from_intake(run, {**ANSWERS, "chat_language": chat})
    cfg = config.load(run)
    assert cfg["languages"] == {"working": working, "market": "pl"}
    assert "page_lang" not in cfg and "page_lang_note" not in cfg
    assert organic_config.page_lang(cfg) == working
    assert organic_config.validate(run) == []


def test_languages_are_kept_as_given(run):
    answers = {k: v for k, v in ANSWERS.items() if k not in ("chat_language", "audience_language")}
    organic_config.write_from_intake(run, {**answers, "languages": {"working": "en", "market": "de"}})
    assert config.load(run)["languages"] == {"working": "en", "market": "de"}
    organic_config.write_from_intake(run, {**answers, "languages": {"working": "Deutsch", "market": None}})
    assert config.load(run)["languages"] == {"working": "de", "market": "de"}
    organic_config.write_from_intake(run, {**answers, "languages": {"working": "nonsense!", "market": "pl"}})
    assert "languages.working" in _problems(run)


def test_no_language_given_is_english(run):
    answers = {k: v for k, v in ANSWERS.items() if k not in ("chat_language", "audience_language")}
    organic_config.write_from_intake(run, answers)
    assert config.load(run)["languages"] == {"working": "en", "market": "en"}


def test_an_older_config_keeps_its_page_language(run):
    """A config written before issue #3: page_lang is the working language, page_lang_note is accepted."""
    organic_config.write_from_intake(run, ANSWERS)
    cfg = {k: v for k, v in config.load(run).items() if k != "languages"}
    config.save(run, {**cfg, "page_lang": "en", "page_lang_note": "Pages are built in English; post text stays in Polish."})
    assert organic_config.validate(run) == []
    assert organic_config.page_lang(config.load(run)) == "en"


def test_the_market_language_reads_a_two_word_channel_by_its_key(ws, run):
    """No audience language in the answers: the market language comes from the saved profile of the channel the
    config names by its key ("Cat Corner" -> cat-corner)."""
    brand.save(ws, {**EXAMPLEEDU, "channel": "Cat Corner", "audience_language": "pl"}, run=None)
    answers = {k: v for k, v in ANSWERS.items() if k != "audience_language"}
    organic_config.write_from_intake(run, {**answers, "channels": ["Cat Corner"], "chat_language": "de"})
    cfg = config.load(run)
    assert cfg["channels"] == ["cat-corner"]
    assert cfg["languages"] == {"working": "de", "market": "pl"}


def test_fx_rate_required_when_not_usd(run):
    organic_config.write_from_intake(run, {**ANSWERS, "currency": "PLN"})
    p = _problems(run)["fx_rate"]
    assert "PLN" in p.what and "USD" in p.todo
    organic_config.write_from_intake(run, {**ANSWERS, "currency": "PLN", "fx_rate": 3.7})
    assert organic_config.validate(run) == []
    organic_config.write_from_intake(run, {**ANSWERS, "currency": "zl"})
    assert "currency" in _problems(run)


def test_other_fields_checked(run):
    organic_config.write_from_intake(run, {
        **ANSWERS, "colour": "red", "budget": {"per_run_usd": 0},
        "qa": {"wps_min": 3.2, "lufs_usable": [-5, -30], "upload_crf": [26]},
        "proposals": {"min": 7}, "weekly": {"days": ["mon", "funday"], "contents": "films"},
        "generation": {"quality_tier": "cheap", "resolution": "4k", "upscale": "topaz"},
        "mode": {"gates": ["pack", "publish"]}, "kind": "production2"})
    assert set(_problems(run)) >= {"colour", "budget.per_run_usd", "qa.wps_max", "qa.lufs_usable", "qa.upload_crf",
                                   "proposals.max", "weekly.days", "weekly.contents", "generation.quality_tier",
                                   "generation.resolution", "generation.upscale", "mode.gates"}
    assert config.load(run)["kind"] == "proposals"     # the run kind follows the outputs, never the answers
    organic_config.write_from_intake(run, {**ANSWERS, "channels": ["Example Edu", 3]})
    assert "channels" in _problems(run)


def test_intake_closed_after_a0(run):
    organic_config.write_from_intake(run, ANSWERS)
    s = state.load(run)
    s.step = "A1"
    state.save(run, s)
    with pytest.raises(ValueError, match="intake is already done"):
        organic_config.write_from_intake(run, ANSWERS)


def test_organic_intake_written_is_the_a0_check(run, capsys, bundled_skills):
    before = (run.path / "run.json").read_text(encoding="utf-8")
    assert "config.yaml" in organic_config.intake_gap(run)
    assert (run.path / "run.json").read_text(encoding="utf-8") == before        # reads only
    (run.path / "answers.json").write_text(json.dumps({**ANSWERS, "channels": []}), encoding="utf-8")
    code, out = _cli(capsys, "config", "write", "--run", str(run.path), "--answers", "answers.json")
    assert code == 0, out                         # found in the run (RunFolder.given)
    gap = organic_config.intake_gap(run)
    assert "channels" in gap
    code, out = _cli(capsys, "done", "A0", "--run", str(run.path))
    assert code == 2 and "A0" in out["message"] and "channels" in out["message"]
    (run.path / "answers.json").unlink()
    (run.path / "answers_v02.json").write_text(json.dumps(ANSWERS), encoding="utf-8")
    assert _cli(capsys, "config", "write", "--run", str(run.path), "--answers", "answers_v02.json")[0] == 0
    assert organic_config.intake_gap(run) is None
    code, out = _cli(capsys, "done", "A0", "--run", str(run.path))
    assert code == 2 and "stack" in out["message"]                      # the stack check is A0's too (Task 4)
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="ok")
    assert _cli(capsys, "done", "A0", "--run", str(run.path))[0] == 0
    code, out = _cli(capsys, "config", "write", "--run", str(run.path), "--answers", "answers_v02.json")
    assert code == 1 and "intake is already done" in out["message"]
