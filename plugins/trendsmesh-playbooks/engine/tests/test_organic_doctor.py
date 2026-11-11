"""Organic video's stack check (playbook 03, plan Task 4): the doctor's rows, the free ElevenLabs
credits read, `tm organic stack` and the `stack_recorded` step check."""

import json
from datetime import date
from pathlib import Path

import pytest

from tm import cli, doctor, envtiers, evidence, organic, state, stepchecks
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import Stop
from tm.tools import TOOLS

from test_doctor import REAL_INSTALLED, REFRESH_AD_CARD_030, ALL_OK, ids, item, world  # noqa: F401  (world: autouse fixture)

OV = "organic-video"
OK = {"trendsmesh": "ok", "artifacts": "ok"}
IDEA = {"proposals"}
PRODUCTION = {"organic_video"}


def _check(outputs, mcp=OK, **kw):
    return doctor.check(set(outputs), False, mcp, playbook=OV, **kw)


def test_organic_not_ready_without_trendsmesh_and_no_guess_notice():
    r = _check(IDEA, {"trendsmesh": "missing", "artifacts": "ok"})
    it = item(r, "mcp_trendsmesh_organic")
    assert not r.ready and not it.ok and not it.warn
    assert it.fix == ("Open /mcp, choose trendsmesh, and sign in. Organic video builds every idea on trends "
                      "that are rising now, so it can't run without TrendsMesh.")
    assert item(r, "trendsmesh_agent_plan_organic").unchecked   # waits for the connection, as in trend research
    gone = _check(IDEA, {"trendsmesh": "no_agents", "artifacts": "ok"})
    assert not gone.ready and "trendsmesh_agent_plan_organic" not in ids(gone)  # the connection row says it all
    assert evidence.NOTICE_SHORT not in doctor.card(r)
    free = _check(IDEA, {"trendsmesh": "free", "artifacts": "ok"})
    assert not free.ready and not item(free, "trendsmesh_agent_plan_organic").warn
    assert evidence.NOTICE_SHORT not in doctor.card(free)


def test_missing_replicate_is_a_warning_with_its_note():
    r = _check(PRODUCTION)
    it = item(r, "replicate_api_token_organic")
    assert r.ready and not it.ok and it.warn
    assert it.note == ("Without a Replicate token, AI footage and talking characters are hidden; animations, "
                       "quizzes and scripts to film stay available.")
    assert it.fix == "Open /plugin, choose trendsmesh-playbooks, set the Replicate token"
    card = doctor.card(r)
    assert it.note in card and evidence.NOTICE_SHORT not in card
    assert item(r, "elevenlabs_api_key_organic").note == (
        "Without an ElevenLabs key, a narrator comes from the video model's prompt, or the lines stay in the script.")


def test_the_other_warnings_have_their_own_notes(monkeypatch):
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: None)
    r = _check(IDEA, {"trendsmesh": "ok", "artifacts": "missing"})
    assert r.ready
    assert item(r, "artifacts_pages_organic").note == (
        "Without the claude.ai artifacts connector you get each page as a local file, and choices are taken "
        "here in chat.")
    assert item(r, "browser_for_organic_animation").note == "Without Chrome or Edge, animations are hidden."
    assert not item(r, "browser_for_organic_animation").ok


def test_a_set_key_is_ok(world):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\nELEVENLABS_API_KEY=xi_y\n")
    r = _check(PRODUCTION)
    assert item(r, "replicate_api_token_organic").ok and item(r, "elevenlabs_api_key_organic").ok


def test_credits_call_is_free():
    assert TOOLS["elevenlabs"].kind_for(["credits"]) is None
    assert TOOLS["elevenlabs"].kind_for(["credits", "--run", "r", "--json"]) is None
    assert TOOLS["elevenlabs"].kind_for(["tts", "--run", "r"]) == "voice_credits"


def test_stack_hides_types():
    full = {"replicate": "ok", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"}
    assert organic.hidden_types(full) == set() and organic.unavailable_routes(full) == set()
    assert organic.hidden_types({**full, "replicate": "missing"}) == {"ai_footage", "talking_character"}
    assert organic.hidden_types({**full, "browser": "missing"}) == {"animation"}
    assert organic.hidden_types({"replicate": "missing", "browser": "missing"}) == {
        "ai_footage", "talking_character", "animation"}
    assert organic.hidden_types({**full, "artifacts": "missing"}) == set()   # pages as files hide no type
    for state_ in ("missing", "no_credits", "unchecked"):
        assert organic.unavailable_routes({**full, "elevenlabs": state_}) == {
            "elevenlabs_narrator", "elevenlabs_lipsync"}
    assert organic.hidden_types(None) == {"ai_footage", "talking_character", "animation"}


def test_idea_run_needs_base_tier_only(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: False)
    for output in ("proposals", "weekly_plan"):
        r = _check({output})
        assert [i.id for i in r.items if i.id.startswith("tier_")] == ["tier_base"]
        assert not r.ready and not item(r, "tier_base").ok
        assert not {"tier_animatic", "tier_video"} & ids(r)


def test_production_run_needs_media_tiers(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier == "base")
    r = _check(PRODUCTION)
    assert [i.id for i in r.items if i.id.startswith("tier_")] == [
        "tier_base", "tier_breakdown", "tier_video", "tier_voice", "tier_ai"]
    assert not r.ready and {i.id for i in r.items if i.fixer == "agent" and not i.ok} == {
        "tier_breakdown", "tier_video", "tier_voice", "tier_ai"}
    assert "tier_animatic" not in ids(_check(PRODUCTION | IDEA))   # the pack check holds the animatic tier
    # script to film makes no media: the idea run's base tier is all it asks
    assert [i.id for i in _check({"script_to_film"}).items if i.id.startswith("tier_")] == ["tier_base"]


def test_video_tier_needs_the_remotion_setup_render_needs(monkeypatch):
    """#4: the video environment installed but the Remotion setup missing, interrupted or out of date (no marker
    for this lock file) is not ready: the doctor asks `envtiers.installed`, the same check render makes, and offers
    the install at D1 with its size and time instead of render stopping at G1."""
    from tm import render
    monkeypatch.setattr(doctor.envtiers, "installed", REAL_INSTALLED)
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: True)
    monkeypatch.setattr(render, "setup_done", lambda: False)
    r = _check(PRODUCTION)
    it = item(r, "tier_video")
    assert not r.ready and not it.ok and it.fixer == "agent" and it.size_mb == envtiers.TIERS["video"].approx_mb
    assert "video editing tools (about 500 MB, about 1 min)" in it.fix
    assert "Together: about" in doctor.card(r)
    monkeypatch.setattr(render, "setup_done", lambda: True)
    assert item(_check(PRODUCTION), "tier_video").ok


def test_organic_cli_takes_the_playbook_by_skill_name(capsys, bundled_skills):
    code = cli.main(["doctor", "--playbook", OV, "--outputs", "proposals", "--mcp", "trendsmesh=ok,artifacts=ok",
                     "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "ready"
    assert out["warnings"] == ["replicate_api_token_organic", "elevenlabs_api_key_organic"]


# --- the recorded stack and the A0 step check ----------------------------------------------------

@pytest.fixture
def run(tmp_path):
    return RunFolder.create(tmp_path / "ws", "exampleedu", date(2026, 11, 7), playbook=ORGANIC_VIDEO)


def _stack(capsys, run, **over):
    found = {"replicate": "ok", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok", **over}
    argv = ["organic", "stack", "--run", str(run.path), "--json"]
    for k, v in found.items():
        argv += [f"--{k}", v]
    capsys.readouterr()
    code = cli.main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_a0_needs_the_stack_recorded(run, capsys):
    assert stepchecks.run("stack_recorded", run) == "the stack is checked and recorded in this run (tm organic stack)"
    code, out = _stack(capsys, run, replicate="missing", elevenlabs="unchecked")
    assert code == 0 and out["status"] == "done"
    assert out["hidden_types"] == ["ai_footage", "talking_character"]
    assert out["unavailable_routes"] == ["elevenlabs_lipsync", "elevenlabs_narrator"]
    assert stepchecks.run("stack_recorded", run) is None
    recorded = state.load(run).organic["stack"]
    assert {k: recorded[k] for k in ("replicate", "elevenlabs", "artifacts", "browser")} == {
        "replicate": "missing", "elevenlabs": "unchecked", "artifacts": "ok", "browser": "ok"}
    assert organic.stack_of(run) == recorded and recorded["at"]
    assert organic.hidden_types(recorded) == {"ai_footage", "talking_character"}
    # A0 requires it, next to the intake
    from tm import flow
    a0 = next(s for s in flow.steps(ORGANIC_VIDEO) if s.id == "A0")
    assert list(a0.requires) == ["organic_intake_written", "stack_recorded"]


def test_d1_records_the_stack_again_and_keeps_the_rest_of_organic(run, capsys):
    s = state.load(run)
    s.organic = {"parent": "x"}
    state.save(run, s)
    _stack(capsys, run, elevenlabs="unchecked")
    _stack(capsys, run, elevenlabs="no_credits")
    organic_state = state.load(run).organic
    assert organic_state["parent"] == "x" and organic_state["stack"]["elevenlabs"] == "no_credits"


def _outputs(run, outputs):
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)


def test_d1_of_an_ai_video_needs_the_credits_read(run, capsys):
    """Task 4's review carry (Task 18): A0 may leave ElevenLabs `unchecked`; an AI video's D1 is done only once
    this production run's own stack is recorded with the credits read (ok or no_credits, or missing with no
    key), never unchecked, so no ElevenLabs route rests on an unread account. A script to film makes no media."""
    from tm import flow
    d1 = next(s for s in flow.steps(ORGANIC_VIDEO) if s.id == "D1")
    assert list(d1.requires) == ["credits_recorded", "recipe_written"]
    _outputs(run, ["script_to_film"])
    assert stepchecks.run("credits_recorded", run) is None
    _outputs(run, ["organic_video"])
    gap = stepchecks.run("credits_recorded", run)   # tm organic start does not copy the idea run's stack
    assert "this production run" in gap and "tm tool elevenlabs credits" in gap and "tm organic stack" in gap
    _stack(capsys, run, elevenlabs="unchecked")
    gap = stepchecks.run("credits_recorded", run)
    assert "unchecked" in gap and "tm tool elevenlabs credits" in gap and "--elevenlabs ok, no_credits or missing" in gap
    for found in ("ok", "no_credits", "missing"):
        _stack(capsys, run, elevenlabs=found)
        assert stepchecks.run("credits_recorded", run) is None, found


def test_the_stack_command_refuses_bad_input(run, capsys, tmp_path):
    assert cli.main(["organic", "stack", "--run", str(run.path), "--replicate", "maybe", "--elevenlabs", "ok",
                     "--artifacts", "ok", "--browser", "ok"]) == 1   # argparse refusal is exit 1
    assert cli.main(["organic", "stack", "--run", str(run.path), "--replicate", "ok"]) == 1
    assert organic.stack_gap(run) is not None
    capsys.readouterr()
    other = RunFolder.create(tmp_path / "ws", "other", date(2026, 11, 7), playbook="02-creative-brief")
    code, out = _stack(capsys, other)
    assert code == 1 and "organic video" in out["message"]
    assert cli.main(["organic", "stack", "--run", str(tmp_path / "nope"), "--replicate", "ok", "--elevenlabs", "ok",
                     "--artifacts", "ok", "--browser", "ok"]) == 1


# --- refresh-ad does not change ---------------------------------------------------------------

def test_refresh_ad_card_unchanged(monkeypatch):
    """PB04's literal: the card plugin 0.3.0 printed for this input, word for word."""
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier != "video")
    args = ({"creative_brief", "edited_video"}, True, {"trendsmesh": "free"})
    r = doctor.check(*args, caption_removal=True)
    assert doctor.card(r) == REFRESH_AD_CARD_030
    assert doctor.check(*args, caption_removal=True, playbook="refresh-ad") == r


def test_refresh_ad_tiers_unchanged():
    outputs = ["creative_brief", "edited_video", "ai_video", "live_test"]
    for mask in range(1 << len(outputs)):
        chosen = {o for n, o in enumerate(outputs) if mask >> n & 1}
        for voice in (False, True):
            r = doctor.check(chosen, voice, ALL_OK, caption_removal=True)
            shown = [i.id.removeprefix("tier_") for i in r.items if i.id.startswith("tier_")]
            assert shown == envtiers.tiers_for(chosen, voice), (chosen, voice)


def test_doctor_names_organic_video_now_its_skill_ships(capsys):
    """Task 10 ships skills/organic-video/SKILL.md, so `/doctor` routes "organic video" and "TikTok or
    Reels ideas" to its section (its `tm doctor` call is offered), and `tm doctor --help` lists its
    outputs. Until then (PR A's I3) neither named it."""
    plugin = Path(__file__).resolve().parents[2]
    assert (plugin / "skills" / "organic-video" / "SKILL.md").is_file()
    command = (plugin / "commands" / "doctor.md").read_text(encoding="utf-8")
    step0 = command.split("\n1. ", 1)[0]
    assert "Organic video" in step0 and "TikTok or Reels ideas" in step0
    assert cli.main(["doctor", "--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "organic-video: proposals,weekly_plan" in text and "script_to_film or organic_video" in text


def test_organic_dispatcher_exits_2_on_a_stop(run, capsys, monkeypatch):
    """A Stop (a ValueError) is caught first: exit 2 with status stop, not a failure."""
    def stopped(*a, **kw):
        raise Stop("Fetch the channel profile first.")
    monkeypatch.setattr(organic, "record_stack", stopped)
    code, out = _stack(capsys, run)
    assert code == 2 and out == {"status": "stop", "message": "Fetch the channel profile first."}
