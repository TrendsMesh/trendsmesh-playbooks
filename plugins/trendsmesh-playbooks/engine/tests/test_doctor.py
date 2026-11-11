import json
from collections import namedtuple

import pytest

from tm import cli, doctor, envtiers

Usage = namedtuple("Usage", "total used free")
GB = 1024**3
ALL_OK = {"trendsmesh": "ok", "meta": "ok"}
REAL_INSTALLED = envtiers.installed  # the world fixture stubs it; a test that needs the real check puts it back


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    """Everything installed, plenty of disk, macOS, a browser, no keys, workspace in tmp."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: True)
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(500 * GB, 100 * GB, 400 * GB))
    monkeypatch.setattr(doctor, "_os_key", lambda: "macos")
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: data / "chrome")
    return data


def item(r, id_):
    return next(i for i in r.items if i.id == id_)


def ids(r):
    return {i.id for i in r.items}


def test_brief_needs_no_keys():
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    assert r.ready
    assert not ids(r) & {"replicate_api_token", "elevenlabs_api_key", "elevenlabs_cloning_plan"}
    assert {"tier_base", "tier_breakdown"} <= ids(r)
    assert "tier_video" not in ids(r)


def test_missing_replicate_for_ai_video_tells_user_where():
    r = doctor.check({"ai_video"}, False, ALL_OK)
    it = item(r, "replicate_api_token")
    assert not it.ok and it.fixer == "user" and not r.ready
    assert it.fix == "Open /plugin, choose trendsmesh-playbooks, set the Replicate token"


def test_replicate_set_is_ok(world):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\n")
    assert item(doctor.check({"ai_video"}, False, ALL_OK), "replicate_api_token").ok


def test_replicate_for_edited_video_only_with_caption_removal():
    assert "replicate_api_token" not in ids(doctor.check({"edited_video"}, False, ALL_OK))
    r = doctor.check({"edited_video"}, False, ALL_OK, caption_removal=True)
    assert not item(r, "replicate_api_token").ok


def test_meta_not_enabled_is_user_fix():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "ok", "meta": "not_enabled"})
    assert item(r, "mcp_meta").ok
    it = item(r, "meta_mcp_enabled_for_account")
    assert not it.ok and it.fixer == "user" and it.fix and not r.ready


def test_no_plan_says_the_plan_has_no_trend_data():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "no_plan", "meta": "ok"})
    assert item(r, "mcp_trendsmesh").ok
    it = item(r, "trendsmesh_agent_plan")
    assert not it.ok and it.fixer == "user"
    assert it.fix == "You're on the free TrendsMesh plan: it has no trend data."


def test_unchecked_mcp_is_not_ready_and_says_so():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "ok"})
    it = item(r, "mcp_meta")
    assert not it.ok and "not checked" in it.fix.lower() and not r.ready
    assert "Not checked yet" in doctor.card(r)


def test_missing_tier_is_agent_fix_with_size(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t != "breakdown")
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    it = item(r, "tier_breakdown")
    assert not it.ok and it.fixer == "agent" and it.size_mb == 2500
    card = doctor.card(r)
    assert "2.5 GB" in card


def test_voice_adds_elevenlabs_checks(world):
    r = doctor.check({"edited_video"}, True, ALL_OK)
    assert not item(r, "elevenlabs_api_key").ok
    assert "elevenlabs_cloning_plan" not in ids(r)  # skipped while the key is missing
    assert {"tier_voice", "tier_ai"} <= ids(r)
    (world / "secrets.env").write_text("ELEVENLABS_API_KEY=k\n")
    r = doctor.check({"edited_video"}, True, ALL_OK)
    it = item(r, "elevenlabs_cloning_plan")
    assert not it.ok and it.fixer == "user" and it.unchecked and it.warn  # unknown: a warning (#5)
    r = doctor.check({"edited_video"}, True, ALL_OK, facts={"elevenlabs_plan": "cloning"})
    assert item(r, "elevenlabs_cloning_plan").ok
    r = doctor.check({"edited_video"}, True, ALL_OK, facts={"elevenlabs_plan": "no_cloning"})
    assert not item(r, "elevenlabs_cloning_plan").ok and not item(r, "elevenlabs_cloning_plan").warn
    assert not r.ready


def test_unknown_cloning_plan_does_not_block_the_start(world, capsys):
    """#5: whether the plan includes cloning matters only if the new line needs a clone (V3, after V1c did not
    find the original voice), so an unknown plan is a warning that says when it is checked, not a to-do that
    sends the user to elevenlabs.io before the run starts."""
    (world / "secrets.env").write_text("ELEVENLABS_API_KEY=k\nREPLICATE_API_TOKEN=t\n")
    r = doctor.check({"creative_brief", "edited_video", "ai_video", "live_test"}, True, ALL_OK, caption_removal=True,
                     facts={"elevenlabs_plan": "unknown"})
    assert r.ready
    card = doctor.card(r)
    assert card.startswith("**Ready to go.** You can start now. One thing is checked later, only if the run needs it.")
    assert "Not ready" not in card and "You need to do" not in card and "results better" not in card
    go_on = card.split("**You can go on without these:**")[1]
    assert "voice cloning" in go_on and "voice step" in go_on and "ElevenLabs history" in go_on
    assert "elevenlabs.io" not in card and "(not checked yet)" not in card
    code = cli.main(["doctor", "--outputs", "creative_brief,edited_video,ai_video,live_test", "--voice",
                     "--caption-removal", "--mcp", "trendsmesh=ok,meta=ok", "--fact", "elevenlabs_plan=unknown",
                     "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ready"] and "elevenlabs_cloning_plan" in out["warnings"]
    code = cli.main(["doctor", "--outputs", "edited_video", "--voice", "--mcp", "trendsmesh=ok,meta=ok", "--fact",
                     "elevenlabs_plan=no_cloning", "--json"])
    assert code == 2 and not json.loads(capsys.readouterr().out)["ready"]   # known to be missing: still a stop


def test_disk_sum_of_tiers_plus_two_gb(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: False)
    # base 500 + breakdown 2500 + 2048 = 5048 MB
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(0, 0, 4000 * 1024**2))
    it = item(doctor.check({"creative_brief"}, False, ALL_OK), "disk_free")
    assert not it.ok and it.fixer == "user"
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(0, 0, 5100 * 1024**2))
    assert item(doctor.check({"creative_brief"}, False, ALL_OK), "disk_free").ok


def test_linux_chrome_libs_only_on_linux_with_video(monkeypatch):
    monkeypatch.setattr(doctor, "_missing_libs", lambda: ["libnss3"])
    assert "linux_chrome_libs" not in ids(doctor.check({"edited_video"}, False, ALL_OK))  # macOS
    monkeypatch.setattr(doctor, "_os_key", lambda: "linux")
    assert "linux_chrome_libs" not in ids(doctor.check({"creative_brief"}, False, ALL_OK))
    it = item(doctor.check({"edited_video"}, False, ALL_OK), "linux_chrome_libs")
    assert not it.ok and it.fixer == "user" and "sudo apt-get install" in it.fix
    monkeypatch.setattr(doctor, "_missing_libs", lambda: [])
    assert item(doctor.check({"edited_video"}, False, ALL_OK), "linux_chrome_libs").ok


def test_card_orders_agent_fixes_before_user_fixes(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t != "base")
    r = doctor.check({"ai_video"}, False, {"trendsmesh": "ok", "meta": "ok"})
    card = doctor.card(r)
    assert card.index("I can fix") < card.index("You need to")
    assert "❌" in card and "✅" in card
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: True)
    assert doctor.card(doctor.check({"creative_brief"}, False, ALL_OK)).startswith("**Ready")


def test_report_contains_no_secret(world, tmp_path):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_secretvalue\n")
    r = doctor.check({"ai_video"}, False, ALL_OK)
    path = doctor.support_report(r, "step failed: Authorization: Bearer r8_secretvalue\nbye")
    text = path.read_text(encoding="utf-8")
    assert "r8_secretvalue" not in text
    assert "step failed" in text and "tier_base" in text
    assert path.parent == tmp_path / "ws" and path.name.startswith("trendsmesh-support-")


def test_report_never_overwrites():
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    a, b, c = (doctor.support_report(r, "") for _ in range(3))
    assert len({a, b, c}) == 3
    assert b.name.endswith("_2.md") and c.name.endswith("_3.md")


def test_cli_exit_codes_and_json(capsys, monkeypatch):
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok", "--json"])
    assert code == 0
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=not_enabled", "--json"])
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert code == 2 and '"ready": false' in out
    assert cli.main(["doctor", "--outputs", "nonsense"]) == 1
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "meta=weird"]) == 1


def test_cli_report_prints_path(capsys):
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok", "--report"])
    assert code == 0 and "trendsmesh-support-" in capsys.readouterr().out


def test_card_shows_no_command_flags_and_says_who_acts(monkeypatch):
    """The first screen the user sees: no `--mcp` or `--fact`; Claude's own checks read as
    Claude's actions, not as the user's to-dos."""
    monkeypatch.setattr(doctor.secrets, "get", lambda name: "set")
    r = doctor.check(set(doctor.flow.output_ids()), True, {})            # nothing checked, plan unknown
    card = doctor.card(r)
    assert "--" not in card and "<result>" not in card
    mine = card.split("**I still need to check these (nothing for you to do):**")[1].split("**You need")[0]
    assert "TrendsMesh" in mine and "Meta Ads" in mine
    assert "TrendsMesh call" not in card.split("**I still need to check these")[0]
    go_on = card.split("**You can go on without these:**")[1].split("**I")[0]
    assert "voice cloning" in go_on   # the unknown plan is checked at the voice step, if a clone is needed (#5)


@pytest.mark.parametrize("release,package", [
    ({"ID": "ubuntu", "VERSION_ID": "24.04"}, "libasound2t64"),
    ({"ID": "ubuntu", "VERSION_ID": "25.10"}, "libasound2t64"),
    ({"ID": "ubuntu", "VERSION_ID": "22.04"}, "libasound2 "),
    ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian", "VERSION_ID": "22", "UBUNTU_CODENAME": "noble"}, "libasound2t64"),
    ({"ID": "debian", "VERSION_ID": "13"}, "libasound2t64"),
    ({"ID": "debian", "VERSION_ID": "12"}, "libasound2 "),
    ({}, "libasound2 "),
])
def test_linux_sudo_line_names_the_sound_library_of_the_release(monkeypatch, release, package):
    """Ubuntu 24.04 renamed libasound2 to libasound2t64; apt-get aborts on the old name there."""
    monkeypatch.setattr(doctor, "_os_key", lambda: "linux")
    monkeypatch.setattr(doctor, "_missing_libs", lambda: ["libasound2"])
    monkeypatch.setattr(doctor, "_os_release", lambda: release)
    it = item(doctor.check({"edited_video"}, False, ALL_OK), "linux_chrome_libs")
    assert package in it.fix + " "


# --- TrendsMesh warns, it does not block (issue #9) ---------------------------------------

@pytest.mark.parametrize("state", ["missing", "no_plan"])
def test_trendsmesh_missing_warns_but_the_run_can_go_on(state):
    r = doctor.check({"creative_brief"}, False, {"meta": "ok", "trendsmesh": state})
    assert r.ready
    warned = [i for i in r.items if i.warn and not i.ok]
    assert warned and all(i.id in ("mcp_trendsmesh", "trendsmesh_agent_plan") for i in warned)
    card = doctor.card(r)
    assert card.startswith("**Ready to go.**")
    assert "You can go on without these" in card
    assert "my best guess" in card  # the guess-mode warning
    assert "❌" not in card


def test_trendsmesh_unchecked_does_not_block_but_stays_on_claudes_list():
    r = doctor.check({"creative_brief"}, False, {"meta": "ok"})
    assert r.ready
    card = doctor.card(r)
    mine = card.split("**I still need to check these (nothing for you to do):**")[1]
    assert "TrendsMesh" in mine


def test_meta_missing_still_blocks_with_trendsmesh_missing():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "missing", "meta": "missing"})
    assert not r.ready
    assert not item(r, "mcp_meta").warn


def test_trendsmesh_ok_shows_no_warning():
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    assert r.ready and "You can go on without these" not in doctor.card(r)


def test_cli_lists_warnings_and_exits_0(capsys):
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=missing,meta=ok", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["ready"] is True and data["status"] == "ready"
    assert "mcp_trendsmesh" in data["warnings"]


def test_a_blocker_is_never_listed_as_something_to_go_on_without(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t != "breakdown")
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "no_plan", "meta": "ok"})
    assert not r.ready
    card = doctor.card(r)
    go_on = card.split("**You can go on without these:**")[1].split("**")[0]
    assert "Video breakdown" not in go_on and "❌" not in go_on
    assert "free TrendsMesh plan" in go_on


# --- the sign-in states (issue #9, PR B) ---------------------------------------------------

def test_free_plan_is_signed_in_and_warns_about_the_plan():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "free", "meta": "ok"})
    assert r.ready and item(r, "mcp_trendsmesh").ok
    it = item(r, "trendsmesh_agent_plan")
    assert not it.ok and it.warn and "free TrendsMesh plan" in it.fix


def test_skipped_sign_in_says_it_was_the_users_choice():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "skipped", "meta": "ok"})
    assert r.ready
    it = item(r, "mcp_trendsmesh")
    assert not it.ok and it.warn and "You chose to go on without TrendsMesh" in it.fix
    assert "trendsmesh_agent_plan" not in ids(r)  # nothing to check about a plan nobody signed in to


def test_inactive_account_names_it():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "inactive", "meta": "ok"})
    assert r.ready and item(r, "mcp_trendsmesh").ok
    it = item(r, "trendsmesh_agent_plan")
    assert not it.ok and "not active" in it.fix


def test_cli_takes_the_new_states(capsys):
    for st in ("free", "skipped", "inactive", "no_agents"):
        assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", f"trendsmesh={st},meta=ok"]) == 0


def test_the_card_never_names_the_plan_after_a_skip():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "skipped", "meta": "ok"})
    card = doctor.card(r)
    assert "my best guess" in card and "Agent plan" not in card and "trendsmesh.com" not in card


def test_free_plan_card_does_not_pitch_the_plan_again():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "free", "meta": "ok"})
    card = doctor.card(r)
    assert "trendsmesh.com" not in card and "free TrendsMesh plan" in card


def test_no_agents_is_not_shown_as_connected():
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "no_agents", "meta": "ok"})
    assert r.ready
    it = item(r, "mcp_trendsmesh")
    assert not it.ok and it.warn and "doesn't include connecting an agent" in it.fix
    assert "trendsmesh_agent_plan" not in ids(r)


@pytest.mark.parametrize("pair", ["meta=free", "meta=inactive", "meta=skipped", "trendsmesh=not_enabled"])
def test_each_mcp_takes_only_its_own_states(pair):
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", pair]) == 1


# --- which playbook the doctor checks (trend research, plan Task 3) ------------------------

TR = "04-trend-research"
TR_OUTPUTS = {"category_report", "weekly_digest", "paid_view"}
TR_OK = {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}
META_NOTE = ("Without the Meta Ads connector the paid check says 'not checked'; the report is "
             "otherwise complete.")
ARTIFACTS_FIX = ("Shared page links need Claude Code in the Claude desktop app; here the page is "
                 "saved as a file you can open and share.")
ARTIFACTS_NOTE = "Without shared page links the report is otherwise complete."


@pytest.fixture
def _tr_cli(capsys, bundled_skills):
    return lambda mcp, *extra: _tr_main(capsys, mcp, *extra)


def _tr_main(capsys, mcp, *extra):
    code = cli.main(["doctor", "--playbook", "trend-research", "--outputs",
                     "category_report,weekly_digest,paid_view", "--mcp", mcp, "--json", *extra])
    return code, json.loads(capsys.readouterr().out)


def test_trend_research_checks_only_its_own_rows():
    r = doctor.check(TR_OUTPUTS, False, TR_OK, playbook=TR)
    assert r.ready and [i.id for i in r.items] == [
        "tier_base", "disk_free", "mcp_trendsmesh_research", "trendsmesh_agent_plan_research",
        "meta_ad_library_research", "artifacts_pages"]
    assert doctor.card(r).startswith("**Ready to go.** Everything this run needs is in place.")
    assert doctor.check(TR_OUTPUTS, False, TR_OK, playbook="trend-research") == r  # skill name too


def test_trend_research_needs_the_base_tools(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier != "base")
    r = doctor.check(TR_OUTPUTS, False, TR_OK, playbook=TR)
    it = item(r, "tier_base")
    assert not r.ready and not it.ok and it.fixer == "agent" and it.size_mb == 500


@pytest.mark.parametrize("state,says", [
    ("missing", "Open /mcp, choose trendsmesh, and sign in. Trend research reads every number from "
                "TrendsMesh, so it can't run without it."),
    ("skipped", "You chose to go on without TrendsMesh, but trend research has nothing to report "
                "without it. Say so when you want to sign in."),
])
def test_trend_research_not_ready_without_trendsmesh(_tr_cli, state, says):
    code, out = _tr_cli(f"trendsmesh={state},meta=ok,artifacts=ok")
    assert code == 2 and out["ready"] is False and out["status"] == "stop"
    card = out["card"]
    assert "- ❌ TrendsMesh connected and signed in\n" in card
    assert "**You can go on without these:**" not in card and "⚠️" not in card
    assert doctor.evidence.NOTICE_SHORT not in card and "my best guess" not in card  # no guess mode
    it = next(i for i in out["items"] if i["id"] == "mcp_trendsmesh_research")
    assert it["fix"] == says and not it["warn"]
    if state == "skipped":  # no plan row after the user's no
        assert "trendsmesh_agent_plan_research" not in [i["id"] for i in out["items"]]
        assert "Agent plan" not in card


PLANS = "Choose the Agent plan at https://trendsmesh.com/plans, then say continue."


@pytest.mark.parametrize("state,says", [
    ("free", f"You're on the free TrendsMesh plan: it has no trend data. {PLANS}"),
    ("no_plan", f"You're on the free TrendsMesh plan: it has no trend data. {PLANS}"),
    ("inactive", "Your TrendsMesh account is not active, so it gives no trend data. Open "
                 "https://trendsmesh.com/app/plan to see why."),
])
def test_trend_research_not_ready_without_the_agent_plan(state, says):
    r = doctor.check(TR_OUTPUTS, False, {**TR_OK, "trendsmesh": state}, playbook=TR)
    assert not r.ready and item(r, "mcp_trendsmesh_research").ok
    it = item(r, "trendsmesh_agent_plan_research")
    assert not it.ok and not it.warn and it.fixer == "user" and it.fix == says
    assert "my best guess" not in doctor.card(r)


def test_trend_research_no_agents_says_what_to_do(_tr_cli):
    code, out = _tr_cli("trendsmesh=no_agents,meta=ok,artifacts=ok")
    assert code == 2 and out["ready"] is False
    ids_ = [i["id"] for i in out["items"]]
    assert "trendsmesh_agent_plan_research" not in ids_  # the connection row says it all
    it = next(i for i in out["items"] if i["id"] == "mcp_trendsmesh_research")
    assert not it["ok"] and not it["warn"] and it["fixer"] == "user"
    assert it["fix"] == ("Your TrendsMesh plan doesn't include connecting an agent yet, so I can't "
                         f"read trend data. {PLANS}")
    assert f"1. {it['fix']}" in out["card"] and "my best guess" not in out["card"]


@pytest.mark.parametrize("meta", ["missing", "not_enabled"])
def test_trend_research_meta_and_artifacts_are_warnings_with_their_own_note(_tr_cli, meta):
    code, out = _tr_cli(f"trendsmesh=ok,meta={meta},artifacts=missing")
    assert code == 0 and out["ready"] is True
    assert out["warnings"] == ["meta_ad_library_research", "artifacts_pages"]
    card = out["card"]
    assert card.startswith("**Ready to go.** You can start now. A few things would make the "
                           "results better.\n")
    assert "- ⚠️ Meta Ad Library connected and signed in\n" in card
    assert "- ⚠️ Shared page links (claude.ai artifacts)\n" in card
    go_on = card.split("**You can go on without these:**\n")[1]
    assert f"- {ARTIFACTS_FIX}\n" in go_on and "/mcp" not in go_on.split(ARTIFACTS_FIX)[1]
    assert go_on.endswith(f"- {META_NOTE}\n- {ARTIFACTS_NOTE}")
    assert doctor.evidence.NOTICE_SHORT not in card and "❌" not in card


def test_one_warning_keeps_the_one_thing_heading():
    r = doctor.check(TR_OUTPUTS, False, {**TR_OK, "artifacts": "missing"}, playbook=TR)
    card = doctor.card(r)
    assert card.startswith("**Ready to go.** You can start now. One thing would make the results "
                           "better.\n")
    assert card.count("⚠️") == 1


def test_trend_research_unchecked_warnings_stay_on_claudes_list():
    r = doctor.check(TR_OUTPUTS, False, {"trendsmesh": "ok"}, playbook=TR)
    assert r.ready
    mine = doctor.card(r).split("**I still need to check these (nothing for you to do):**")[1]
    assert "Meta Ads call" in mine and "shared page links" in mine


def test_trend_research_cli_refuses_other_outputs_and_states(_tr_cli):
    assert _tr_cli("trendsmesh=ok,meta=ok,artifacts=weird")[0] == 1
    assert _tr_cli("trendsmesh=ok,meta=free")[0] == 1
    code, out = _tr_cli("trendsmesh=ok", "--outputs", "creative_brief")
    assert code == 1 and "category_report" in out["message"]
    assert cli.main(["doctor", "--playbook", "nope", "--outputs", "creative_brief"]) == 1
    assert cli.main(["doctor", "--outputs", "category_report"]) == 1  # refresh-ad by default


REFRESH_AD_CARD_030 = """**Not ready yet.** Here is what is in place and what is not.

- ✅ Base tools
- ✅ Video breakdown tools (transcription and scene detection)
- ✅ Voice tools (new voiceover)
- ✅ AI video tools
- ✅ Free disk space
- ✅ TrendsMesh connected and signed in
- ⚠️ TrendsMesh Agent plan
- ❌ Video editing tools (Remotion)
- ❌ Replicate token set
- ❌ ElevenLabs key set
- ❌ Meta Ads connected and signed in (not checked yet)
- ❌ Meta Ads enabled for your ad account (not checked yet)

**You can go on without these:**
- You're on the free TrendsMesh plan: it has no trend data.
- Without live trend data, the new hook is my best guess from your own past winners and the Ad Library, not proof from what is rising now.

**I can fix these for you, once you say yes:**
- I install the video editing tools (about 500 MB, about 1 min). Say yes and I start.
- Together: about 500 MB, about 1 min.

**I still need to check these (nothing for you to do):**
- Not checked yet: I check it with one quick Meta Ads call, then look again.
- Can't be checked until Meta Ads is connected and signed in.

**You need to do these yourself:**
1. Open /plugin, choose trendsmesh-playbooks, set the Replicate token
2. Open /plugin, choose trendsmesh-playbooks, set the ElevenLabs key

When they are done, tell me and I check again. The run continues from the same place."""


def test_refresh_ad_card_unchanged(monkeypatch):
    """The card plugin 0.3.0 printed for this input, word for word."""
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier != "video")
    args = ({"creative_brief", "edited_video"}, True, {"trendsmesh": "free"})
    r = doctor.check(*args, caption_removal=True)
    assert doctor.card(r) == REFRESH_AD_CARD_030
    assert doctor.check(*args, caption_removal=True, playbook="refresh-ad") == r


# --- creative brief (plan Task 4): Meta blocks, TrendsMesh and the artifacts connector warn ---

CB = "02-creative-brief"
CB_OUTPUTS = "review_pack,briefs,animatics,page"
CB_NOTE = ("Without live trend data, the hooks in these concepts are my best guess from your "
           "customers' own words, your ads and the Ad Library, not proof from what is rising now.")
CB_ARTIFACTS_NOTE = ("Without the claude.ai artifacts connector you get the page as a local file, and "
                     "decisions are taken here in chat.")
CB_ROWS = ["tier_base", "tier_animatic", "disk_free", "mcp_trendsmesh_brief", "trendsmesh_agent_plan_brief",
           "mcp_meta", "meta_mcp_enabled_for_account", "artifacts_pages_brief", "browser_for_animatics"]


@pytest.fixture
def _cb_cli(capsys, bundled_skills):
    def run(mcp):
        code = cli.main(["doctor", "--playbook", "creative-brief", "--outputs", CB_OUTPUTS,
                         "--mcp", mcp, "--json"])
        return code, json.loads(capsys.readouterr().out)
    return run


@pytest.mark.parametrize("state,warned", [
    ("missing", "mcp_trendsmesh_brief"),
    ("skipped", "mcp_trendsmesh_brief"),
    ("no_agents", "mcp_trendsmesh_brief"),
    ("free", "trendsmesh_agent_plan_brief"),
    ("inactive", "trendsmesh_agent_plan_brief"),
])
def test_creative_brief_ready_without_trendsmesh_with_its_notice(_cb_cli, state, warned):
    code, out = _cb_cli(f"trendsmesh={state},meta=ok,artifacts=ok")
    assert code == 0 and out["ready"] is True and out["status"] == "ready"
    assert out["warnings"] == [warned]
    it = next(i for i in out["items"] if i["id"] == warned)
    assert it["warn"] and it["note"] == CB_NOTE == doctor.evidence.NOTICES[CB].short
    assert it["fixer"] == "user"
    card = out["card"]
    assert card.startswith("**Ready to go.** You can start now. One thing would make the results "
                           "better.\n")
    assert card.endswith(f"\n- {CB_NOTE}") and card.count(CB_NOTE) == 1
    assert doctor.evidence.NOTICE_SHORT not in card and "❌" not in card
    assert "With TrendsMesh (the Agent plan)" not in card  # the card's form has no plan name


def test_creative_brief_checks_its_own_rows_and_is_ready_with_everything():
    r = doctor.check(set(CB_OUTPUTS.split(",")), False,
                     {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}, playbook=CB)
    assert r.ready and [i.id for i in r.items] == CB_ROWS
    assert doctor.card(r).startswith("**Ready to go.** Everything this run needs is in place.")
    assert doctor.check(set(CB_OUTPUTS.split(",")), False,
                        {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}, playbook="creative-brief") == r


@pytest.mark.parametrize("meta,blocked,says", [
    ("missing", "mcp_meta", "Open /mcp, choose the Meta Ads connector, and sign in to Meta."),
    ("not_enabled", "meta_mcp_enabled_for_account",
     "Meta turns its Ads connector on account by account, and yours is not on yet. In Meta "
     "Business settings, ask for access to the Ads connector (MCP) for this ad account, then say "
     "continue."),
])
def test_creative_brief_not_ready_without_meta(_cb_cli, meta, blocked, says):
    code, out = _cb_cli(f"trendsmesh=ok,meta={meta},artifacts=ok")
    assert code == 2 and out["ready"] is False and out["status"] == "stop"
    assert out["warnings"] == []
    it = next(i for i in out["items"] if i["id"] == blocked)
    assert not it["ok"] and not it["warn"] and it["fixer"] == "user" and it["fix"] == says
    assert f"1. {says}" in out["card"] and "**You can go on without these:**" not in out["card"]
    code, out = _cb_cli("trendsmesh=ok,artifacts=ok")  # Meta not checked yet: not ready either
    assert code == 2 and next(i for i in out["items"] if i["id"] == "mcp_meta")["unchecked"]


def test_artifacts_warning_uses_brief_note(_cb_cli):
    code, out = _cb_cli("trendsmesh=ok,meta=ok,artifacts=missing")
    assert code == 0 and out["ready"] is True and out["warnings"] == ["artifacts_pages_brief"]
    card = out["card"]
    assert "- ⚠️ Shared page links (claude.ai artifacts)\n" in card
    assert card.endswith(f"- {ARTIFACTS_FIX}\n- {CB_ARTIFACTS_NOTE}")
    assert ARTIFACTS_NOTE not in card and CB_NOTE not in card
    code, out = _cb_cli("trendsmesh=free,meta=ok,artifacts=missing")  # two warnings, two notes
    assert code == 0 and out["warnings"] == ["trendsmesh_agent_plan_brief", "artifacts_pages_brief"]
    assert out["card"].endswith(f"- {CB_NOTE}\n- {CB_ARTIFACTS_NOTE}")


# --- the catalogue refuses a typo -----------------------------------------------------------

@pytest.mark.parametrize("extra,says", [
    ({"playbooks": ["04-trend-reserch"]}, "check x names playbook 04-trend-reserch, which "
                                          "data/playbooks.yaml does not list"),
    ({"ok_states": ["ok", "conected"]}, "check x has ok_states ['ok', 'conected']; the states of "
                                        "MCP 'meta' are ok, missing, not_enabled"),
    ({"ok_states": "ok"}, "check x has ok_states 'ok'"),
    ({"ok_states": []}, "check x has ok_states []"),
])
def test_catalogue_names_an_unknown_playbook_or_mcp_state(tmp_path, extra, says):
    path = tmp_path / "requirements.yaml"
    entry = {"id": "x", "name": "X", "kind": "mcp", "mcp": "meta", "fixer": "user", **extra}
    path.write_text(__import__("yaml").safe_dump({"checks": [entry]}), encoding="utf-8")
    with pytest.raises(ValueError) as no:
        doctor._read_catalogue(path)
    assert str(no.value).startswith("requirements.yaml: " + says)


def test_bundled_catalogue_passes_its_own_checks():
    assert doctor._read_catalogue(doctor.paths.bundled_data() / "requirements.yaml") == doctor._catalogue()


def test_the_cloning_plan_is_checked_at_v3_not_at_the_start():
    """#5: the playbook's words match the engine: the doctor step does not send the user to look the plan up, and
    V3 reads it (free) before any clone material is made, stopping only when the plan has no cloning."""
    plugin = doctor.paths.bundled_data().parent
    text = lambda rel: (plugin / rel).read_text(encoding="utf-8").replace("\r", "")  # noqa: E731
    command, skill = text("commands/doctor.md"), " ".join(text("skills/refresh-ad/SKILL.md").split())
    assert "Don't ask, and don't send them to look it" in command
    assert "**An unknown voice-cloning plan is a warning too.**" in skill and "flow.md#v3" in skill
    flow = text("skills/refresh-ad/references/flow.md")
    v3 = " ".join(flow[flow.index('<a id="v3"></a>'):flow.index('<a id="v4"></a>')].split())
    assert v3.index("tm tool elevenlabs credits --run R --json") < v3.index("tm tool elevenlabs clone-ivc")
    assert "`instant_cloning` true: go on. False: stop and wait" in v3
