import json
import re
from collections import namedtuple
from pathlib import Path

import pytest

from tm import cli, doctor, envtiers

Usage = namedtuple("Usage", "total used free")
GB = 1024**3
ALL_OK = {"trendsmesh": "ok", "meta": "ok"}
REAL_INSTALLED = envtiers.installed  # the world fixture stubs it; a test that needs the real check puts it back
REAL_PROBE = doctor._video_probe   # conftest stubs it (`_no_real_probe`)


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
    assert it.fix.startswith("Make a token at https://replicate.com/account/api-tokens")   # #66: where, and the link
    assert "open /plugin, choose Installed, then trendsmesh-playbooks, then Configure options" in it.fix


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


def test_unchecked_mcp_is_pending_and_ready():
    """Issue #124: an MCP Claude has not checked yet is checked by Claude a moment later, so it is pending, not a
    blocker: ⏳ on the card, still ready."""
    r = doctor.check({"creative_brief"}, False, {"trendsmesh": "ok"})
    it = item(r, "mcp_meta")
    assert not it.ok and it.pending and it.fixer == "agent" and "not checked" in it.fix.lower() and r.ready
    card = doctor.card(r)
    assert "- ⏳ Meta Ads connected and signed in: checking in a moment" in card and "❌" not in card
    assert card.startswith("**Ready to go.** I'm still checking Meta Ads connected and signed in and Meta Ads "
                           "enabled for your ad account.")


def test_missing_tier_is_agent_fix_with_size(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t != "breakdown")
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    it = item(r, "tier_breakdown")
    assert not it.ok and it.fixer == "agent" and it.size_mb == 2500
    card = doctor.card(r)
    assert "2.5 GB" in card


def test_a_tier_an_earlier_version_had_says_the_update_sets_it_up_again(monkeypatch):
    """Issue #161: after an update every tier is installed again (pixi keys an environment on the plugin's folder).
    The card says why, in one line with the size and time, for the tiers an earlier version had."""
    from tm import __version__

    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t not in ("breakdown", "video", "voice"))
    monkeypatch.setattr(doctor.envtiers, "earlier_install", lambda t: t in ("breakdown", "video"))
    r = doctor.check({"edited_video"}, True, ALL_OK)
    assert item(r, "tier_breakdown").earlier and not item(r, "tier_voice").earlier
    card = doctor.card(r)
    line = [x for x in card.splitlines() if "once more" in x]
    assert line == [f"- The update to {__version__} sets up the video breakdown tools and video editing tools once "
                    "more (an earlier version had them): about 3.0 GB, about 6 min."]
    monkeypatch.setattr(doctor.envtiers, "earlier_install", lambda t: False)
    assert "once more" not in doctor.card(doctor.check({"edited_video"}, True, ALL_OK))


def test_the_card_says_the_space_an_earlier_versions_tools_freed(monkeypatch, capsys):
    """Issue #161: the doctor removes an earlier version's copy of a tier this version has, and says the space."""
    monkeypatch.setattr(doctor.envtiers, "clean", lambda: envtiers.Cleaned([Path("x")], 2_600_000_000))
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok", "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["freed_mb"] == 2600
    assert "Removed the tools of an earlier plugin version: 2.6 GB freed." in got["card"]
    monkeypatch.setattr(doctor.envtiers, "clean", lambda: envtiers.Cleaned())
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok", "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["freed_mb"] == 0 and "freed" not in got["card"]


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
    it = item(r, "elevenlabs_cloning_plan")
    assert not it.ok and not it.unchecked and it.warn and it.later   # known no: waits for V3 too (#5 follow-up)
    assert r.ready


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


def test_known_no_cloning_plan_waits_for_the_voice_step(world, capsys):
    """Follow-up to #5: a plan the user says has no cloning blocks nothing at the start either. A clone is
    needed only if V1c does not find the original voice; V3 stops there with the choices. The card says
    cloning is not available, without sending the user to elevenlabs.io now."""
    (world / "secrets.env").write_text("ELEVENLABS_API_KEY=k\nREPLICATE_API_TOKEN=t\n")
    r = doctor.check({"creative_brief", "edited_video", "ai_video", "live_test"}, True, ALL_OK, caption_removal=True,
                     facts={"elevenlabs_plan": "no_cloning"})
    assert r.ready
    card = doctor.card(r)
    assert card.startswith("**Ready to go.** You can start now. One thing matters later, only if the run needs it.")
    assert "Not ready" not in card and "You need to do" not in card and "results better" not in card
    go_on = card.split("**You can go on without these:**")[1]
    assert "does not include voice cloning" in go_on
    assert "voice step" in go_on and "ElevenLabs history" in go_on and "stock" in go_on
    assert "elevenlabs.io" not in card and "(not checked yet)" not in card and "I check your plan" not in card
    code = cli.main(["doctor", "--outputs", "edited_video", "--voice", "--mcp", "trendsmesh=ok,meta=ok", "--fact",
                     "elevenlabs_plan=no_cloning", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ready"] and "elevenlabs_cloning_plan" in out["warnings"]


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
    assert path == tmp_path / "ws" / "trendsmesh-support.md"


def test_one_report_file_overwritten_each_time_with_the_plugin_version(tmp_path, monkeypatch):
    """Issue #124: one name, so the current report is never in doubt; the Date line stays inside."""
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "trendsmesh-playbooks", "version": "9.8.7"}')
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(plugin))
    r = doctor.check({"creative_brief"}, False, ALL_OK)
    a, b, c = (doctor.support_report(r, f"run {n}") for n in range(3))
    assert a == b == c == tmp_path / "ws" / "trendsmesh-support.md"
    assert [p.name for p in (tmp_path / "ws").iterdir() if p.name.startswith("trendsmesh-support")] == [a.name]
    text = c.read_text(encoding="utf-8")
    assert "run 2" in text and "run 0" not in text and "- Date: " in text
    assert "- Plugin: trendsmesh-playbooks 9.8.7\n- tm engine: " in text


def test_report_says_unknown_when_plugin_json_is_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(tmp_path / "nowhere"))
    text = doctor.support_report(doctor.check({"creative_brief"}, False, ALL_OK), "").read_text(encoding="utf-8")
    assert "- Plugin: trendsmesh-playbooks (version unknown)" in text


def test_meta_account_names_currency_and_count_on_card_and_report(capsys):
    """Issue #124: which account was checked, as its currency and the number of accounts; never a name or an id."""
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok",
                     "--meta-account", "currency=eur,accounts=2", "--report", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["meta_account"] == {"currency": "EUR", "accounts": 2}
    row = next(i for i in out["items"] if i["id"] == "meta_mcp_enabled_for_account")
    assert row["name"] == "Meta Ads enabled for your ad account (EUR; 1 of 2 accounts checked)"
    assert "✅ Meta Ads enabled for your ad account (EUR; 1 of 2 accounts checked)" in out["card"]
    report = Path(out["report"]).read_text(encoding="utf-8")
    assert "| meta_mcp_enabled_for_account (EUR; 1 of 2 accounts checked) | ok |" in report
    assert "- Meta ad account: EUR; 1 of 2 accounts checked" in report


def test_one_meta_account_reads_as_the_only_one():
    r = doctor.check({"creative_brief"}, False, ALL_OK, meta_account={"currency": "PLN", "accounts": 1})
    assert item(r, "meta_mcp_enabled_for_account").name.endswith("(PLN; your only ad account)")
    assert item(r, "mcp_meta").name == "Meta Ads connected and signed in"


@pytest.mark.parametrize("given", ["currency=EURO,accounts=2", "currency=EUR,accounts=0", "currency=EUR",
                                   "accounts=2", "currency=EUR,accounts=2,name=Shop", "currency=EUR,accounts=x",
                                   "currency=EUR,accounts=2,id=act_123"])
def test_meta_account_refuses_anything_but_a_currency_and_a_count(capsys, given):
    code = cli.main(["doctor", "--outputs", "creative_brief", "--meta-account", given, "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and "--meta-account" in out["message"] and "currency=<ISO 4217 code>,accounts=<n>" in out["message"]


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
    assert code == 0 and "trendsmesh-support.md" in capsys.readouterr().out


def test_card_shows_no_command_flags_and_says_who_acts(monkeypatch):
    """The first screen the user sees: no `--mcp` or `--fact`; Claude's own checks read as
    Claude's actions, not as the user's to-dos."""
    monkeypatch.setattr(doctor.secrets, "get", lambda name: "set")
    r = doctor.check(set(doctor.flow.output_ids()), True, {})            # nothing checked, plan unknown
    card = doctor.card(r)
    assert "--" not in card and "<result>" not in card
    mine = [line for line in card.splitlines() if line.startswith("- ⏳")]
    assert any("TrendsMesh" in line for line in mine) and any("Meta Ads" in line for line in mine)
    assert "TrendsMesh call" not in card
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
    assert doctor.evidence.CHOOSE_NOTE in card  # Free or Paid is the user's choice, never a slide into guessing
    assert "❌" not in card


def test_trendsmesh_unchecked_does_not_block_but_stays_on_claudes_list():
    r = doctor.check({"creative_brief"}, False, {"meta": "ok"})
    assert r.ready
    card = doctor.card(r)
    assert "- ⏳ TrendsMesh connected and signed in: checking in a moment" in card


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
    assert not it.ok and it.warn and "You skipped the TrendsMesh sign-in in an earlier version" in it.fix
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
    assert doctor.evidence.CHOOSE_NOTE in card and "Agent plan" not in card and "trendsmesh.com" not in card


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
ARTIFACTS_FIX = ("This session can't publish claude.ai artifacts (it has no Artifact tool), so the page is "
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
    ("missing", "Trend research is Paid only: it reports what repeats across creators over time, which I can't see "
                "on my own. Open /mcp, choose trendsmesh, and sign in."),
    ("skipped", "You chose to go on without TrendsMesh, but trend research is Paid only: on guesses it has nothing "
                "worth reporting. Say so when you want to sign in."),
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
    card = doctor.card(r)
    assert "- ⏳ Meta Ad Library connected and signed in: checking in a moment" in card
    assert "- ⏳ Shared page links (claude.ai artifacts): checking in a moment" in card


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
- ⏳ Meta Ads connected and signed in: checking in a moment
- ⏳ Meta Ads enabled for your ad account: checking in a moment
- ⚠️ TrendsMesh Agent plan
- ❌ Video editing tools (Remotion)
- ❌ Replicate token: missing
- ❌ ElevenLabs key: missing

**You can go on without these:**
- You're on the free TrendsMesh plan: it has no trend data.
- Free or Paid is your choice: Paid reads TrendsMesh's trends, with evidence across creators; Free goes on with my guesses, each labelled as one. Nothing starts on guesses until you say Free.

**I can fix these for you, once you say yes:**
- I install the video editing tools (about 500 MB, about 1 min). Say yes and I start.
- Together: about 500 MB, about 1 min.

**You need to do these yourself:**
1. Make a token at https://replicate.com/account/api-tokens (sign in, then Create token, and copy it). Then open /plugin, choose Installed, then trendsmesh-playbooks, then Configure options, paste it as the Replicate API token, and start a new session. It makes the AI images and video; each run is paid from your Replicate account (https://replicate.com/account/billing).
2. Make a key at https://elevenlabs.io/app/settings/api-keys (Developers, then API Keys, then Create key). If you restrict it, allow: Text to Speech, Voices (read and write), Audio Isolation, Music Generation, History (read) and User (read). Then open /plugin, choose Installed, then trendsmesh-playbooks, then Configure options, paste it as the ElevenLabs API key, and start a new session. It makes the voices and the music, from your ElevenLabs credits.

When they are done, tell me and I check again. The run continues from the same place."""


def test_refresh_ad_card_unchanged(monkeypatch):
    """The card plugin 0.3.0 printed for this input, word for word, but for the key rows: since #66 they say the
    key's state (missing here) and where to make it."""
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier != "video")
    args = ({"creative_brief", "edited_video"}, True, {"trendsmesh": "free"})
    r = doctor.check(*args, caption_removal=True)
    assert doctor.card(r) == REFRESH_AD_CARD_030
    assert doctor.check(*args, caption_removal=True, playbook="refresh-ad") == r


# --- creative brief (plan Task 4): Meta blocks, TrendsMesh and the artifacts connector warn ---

CB = "02-creative-brief"
CB_OUTPUTS = "review_pack,briefs,page"
CB_ARTIFACTS_NOTE = ("Without shared page links you get the page as a local file, and "
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
    assert it["warn"] and it["note"] == doctor.evidence.CHOOSE_NOTE
    assert it["fixer"] == "user"
    card = out["card"]
    assert card.startswith("**Ready to go.** You can start now. One thing would make the results "
                           "better.\n")
    assert card.endswith(f"\n- {doctor.evidence.CHOOSE_NOTE}") and card.count(doctor.evidence.CHOOSE_NOTE) == 1
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
    code, out = _cb_cli("trendsmesh=ok,artifacts=ok")  # Meta not checked yet: pending, Claude checks it (#124)
    assert code == 0 and out["ready"] and next(i for i in out["items"] if i["id"] == "mcp_meta")["pending"]
    assert out["pending"] == ["mcp_meta", "meta_mcp_enabled_for_account"] and out["warnings"] == []


def test_artifacts_warning_uses_brief_note(_cb_cli):
    code, out = _cb_cli("trendsmesh=ok,meta=ok,artifacts=missing")
    assert code == 0 and out["ready"] is True and out["warnings"] == ["artifacts_pages_brief"]
    card = out["card"]
    assert "- ⚠️ Shared page links (claude.ai artifacts)\n" in card
    assert card.endswith(f"- {ARTIFACTS_FIX}\n- {CB_ARTIFACTS_NOTE}")
    assert ARTIFACTS_NOTE not in card and doctor.evidence.CHOOSE_NOTE not in card
    code, out = _cb_cli("trendsmesh=free,meta=ok,artifacts=missing")  # two warnings, two notes
    assert code == 0 and out["warnings"] == ["trendsmesh_agent_plan_brief", "artifacts_pages_brief"]
    assert out["card"].endswith(f"- {doctor.evidence.CHOOSE_NOTE}\n- {CB_ARTIFACTS_NOTE}")


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


def test_v3_stops_with_the_choices_when_the_plan_has_no_cloning():
    """Follow-up to #5: a plan known to have no cloning waits for V3 as an unknown one does; the playbook says
    so at the start, and V3 stops with three choices, only when a clone is needed."""
    plugin = doctor.paths.bundled_data().parent
    text = lambda rel: " ".join((plugin / rel).read_text(encoding="utf-8").split())  # noqa: E731
    skill, command, flow = text("skills/refresh-ad/SKILL.md"), text("commands/doctor.md"), text(
        "skills/refresh-ad/references/flow.md")
    assert "A plan known to have no cloning still stops" not in skill
    assert "**A plan known to have no cloning waits too.**" in skill
    assert "no_cloning" in command and "waits too" in command
    v3 = flow[flow.index('<a id="v3"></a>'):flow.index('<a id="v4"></a>')]
    assert "`no_cloning`" in v3
    for choice in ("a plan with voice cloning", "a stock voice", "no voice change"):
        assert choice in v3, choice


# --- issue #66: the key rows in three states, from one free call per provider --------------------------------------

def _answers(monkeypatch, tmp_path, **by_provider):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({k: {"status": s, "body": b} for k, (s, b) in by_provider.items()}))
    monkeypatch.setenv("TM_PROVIDER_ANSWERS", str(path))


def test_a_missing_replicate_token_says_where_to_make_one():
    it = item(doctor.check({"ai_video"}, False, ALL_OK), "replicate_api_token")
    assert not it.ok and it.state == "missing" and it.name == "Replicate token: missing"
    assert "https://replicate.com/account/api-tokens" in it.fix and "/plugin" in it.fix


def test_a_working_replicate_token(world, monkeypatch, tmp_path):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\n")
    _answers(monkeypatch, tmp_path, replicate=(200, {"type": "user", "username": "someone"}))
    it = item(doctor.check({"ai_video"}, False, ALL_OK), "replicate_api_token")
    assert it.ok and it.state == "works" and it.name == "Replicate token: works"


def test_a_refused_replicate_token_is_connected_but_unusable(world, monkeypatch, tmp_path, capsys):
    """The eval case for #66: a key that is set but refused blocks AI video, with the fix for that cause."""
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\n")
    _answers(monkeypatch, tmp_path, replicate=(401, {"detail": "Invalid token."}))
    r = doctor.check({"ai_video"}, False, ALL_OK)
    it = item(r, "replicate_api_token")
    assert not it.ok and not r.ready and it.state == "unusable" and it.fixer == "user"
    assert it.name == "Replicate token: connected but unusable"
    assert "it is wrong, or it was revoked" in it.fix and "https://replicate.com/account/api-tokens" in it.fix
    card = doctor.card(r)
    assert "❌ Replicate token: connected but unusable" in card and "r8_x" not in card
    code = cli.main(["doctor", "--outputs", "ai_video", "--mcp", "trendsmesh=ok,meta=ok", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and next(i for i in out["items"] if i["id"] == "replicate_api_token")["state"] == "unusable"


def test_an_unreachable_provider_does_not_block(world):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\n")
    it = item(doctor.check({"ai_video"}, False, ALL_OK), "replicate_api_token")   # the tests have no network
    assert it.ok and it.state == "unchecked" and "not checked" in it.name


def test_elevenlabs_with_no_credits_left_is_unusable_and_its_plan_is_read(world, monkeypatch, tmp_path):
    (world / "secrets.env").write_text("ELEVENLABS_API_KEY=k\n")
    _answers(monkeypatch, tmp_path, elevenlabs=(200, {"tier": "free", "character_count": 10000,
                                                      "character_limit": 10000,
                                                      "can_use_instant_voice_cloning": False}))
    r = doctor.check({"edited_video"}, True, ALL_OK)
    key = item(r, "elevenlabs_api_key")
    assert not key.ok and key.state == "unusable" and "https://elevenlabs.io/app/subscription" in key.fix
    plan = item(r, "elevenlabs_cloning_plan")   # read from the same answer, not left unknown
    assert not plan.ok and not plan.unchecked and plan.later


def test_a_cloning_plan_the_user_named_wins_over_the_answer(world, monkeypatch, tmp_path):
    (world / "secrets.env").write_text("ELEVENLABS_API_KEY=k\n")
    _answers(monkeypatch, tmp_path, elevenlabs=(200, {"character_count": 0, "character_limit": 30000,
                                                      "can_use_instant_voice_cloning": True}))
    r = doctor.check({"edited_video"}, True, ALL_OK)
    assert item(r, "elevenlabs_api_key").state == "works" and item(r, "elevenlabs_cloning_plan").ok
    r = doctor.check({"edited_video"}, True, ALL_OK, facts={"elevenlabs_plan": "no_cloning"})
    assert not item(r, "elevenlabs_cloning_plan").ok


def test_an_unusable_key_is_a_warning_where_the_playbook_goes_on_without_it(world, monkeypatch, tmp_path):
    """Create an ad and organic video run without the keys: a refused key is a warning there, with its fix."""
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\nELEVENLABS_API_KEY=k\n")
    _answers(monkeypatch, tmp_path, replicate=(429, {"detail": "Request was throttled."}),
             elevenlabs=(401, {"detail": {"code": "invalid_api_key"}}))
    r = doctor.check({"video_ad"}, False, {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}, playbook="create-ad")
    rep, el = item(r, "replicate_api_token_create"), item(r, "elevenlabs_api_key_create")
    assert r.ready and rep.warn and el.warn and rep.state == el.state == "unusable"
    go_on = doctor.card(r).split("**You can go on without these:**")[1]
    assert "6 runs a minute" in go_on and "https://elevenlabs.io/app/settings/api-keys" in go_on


def test_every_key_row_checks_its_key():
    rows = [e for e in doctor._catalogue() if e["kind"] == "secret"]
    assert rows and all(e.get("check") in ("replicate", "elevenlabs") for e in rows)
    assert all(e["check"] == e["secret"].split("_")[0] for e in rows)


def test_create_ad_asks_for_remotion_for_its_text(monkeypatch):
    """Issue 96 built Create an ad's edit with the plugin's ffmpeg alone; issue 117 draws its text over the ffmpeg cut
    with Remotion's OrganicCaptions, in the brand's text set, so its doctor asks for the video editing tools too."""
    mcp = {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: True)
    r = doctor.check({"video_ad"}, False, mcp, playbook="create-ad")
    assert {"tier_base", "tier_breakdown", "tier_voice", "tier_ai", "tier_video"} <= ids(r)
    assert r.ready
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: tier != "video")
    r = doctor.check({"video_ad"}, False, mcp, playbook="create-ad")
    assert not item(r, "tier_video").ok


def test_create_ad_without_a_browser_is_a_warning(monkeypatch):
    """Issue 96: the site's captures, logo and font are read in the user's own Chrome or Edge; without one the run
    goes on and the user gives them as files."""
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: None)
    r = doctor.check({"video_ad"}, False, {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}, playbook="create-ad")
    it = item(r, "browser_for_create")
    assert r.ready and not it.ok and it.warn
    assert "logo" in doctor.card(r)


# --- Free or Paid, the user's choice (issue #106) ---------------------------------------------

@pytest.mark.parametrize("state", ["missing", "skipped", "free", "no_agents", "inactive", None])
def test_on_free_trendsmesh_is_one_line_with_what_free_misses(state):
    mcp = {"meta": "ok", "artifacts": "ok", **({"trendsmesh": state} if state else {})}
    r = doctor.check({"creative_brief"}, False, mcp, mode="free")
    rows = [i for i in r.items if "trendsmesh" in i.id]
    assert r.ready and len(rows) == 1 and rows[0].ok and rows[0].free and not rows[0].warn
    card = doctor.card(r)
    assert f"- ℹ️ {doctor.FREE_ROW}. {doctor.evidence.NOTICE_SHORT}" in card
    assert "⚠️" not in card and "✅ TrendsMesh" not in card and "trendsmesh.com" not in card
    assert card.startswith("**Ready to go.** Everything this run needs is in place.")


def test_on_free_a_working_trendsmesh_is_used():
    r = doctor.check({"creative_brief"}, False, {"meta": "ok", "trendsmesh": "ok"}, mode="free")
    assert not any(i.free for i in r.items) and item(r, "mcp_trendsmesh").ok


def test_paid_without_trendsmesh_keeps_its_own_step_not_the_choice_note():
    """Issue #124: Paid is the user's saved choice, so the card no longer says Free or Paid is theirs to make."""
    r = doctor.check({"creative_brief"}, False, {"meta": "ok", "trendsmesh": "free"}, mode="paid")
    it = item(r, "trendsmesh_agent_plan")
    assert it.warn and it.note != doctor.evidence.CHOOSE_NOTE and not any(i.free for i in r.items)
    assert it.fix == "You're on the free TrendsMesh plan: it has no trend data."
    card = doctor.card(r)
    assert doctor.evidence.CHOOSE_NOTE not in card and "\n- \n" not in card and not card.endswith("- ")


def test_the_choice_note_only_when_no_mode_is_saved_and_the_row_is_not_ok():
    r = doctor.check({"creative_brief"}, False, {"meta": "ok", "trendsmesh": "free"})
    assert item(r, "trendsmesh_agent_plan").note == doctor.evidence.CHOOSE_NOTE
    assert item(r, "mcp_trendsmesh").note == ""   # signed in: ok, no note
    for mode in ("paid", None):
        r = doctor.check({"creative_brief"}, False, ALL_OK, mode=mode)
        assert not any(i.note == doctor.evidence.CHOOSE_NOTE for i in r.items)


def test_cli_after_tm_mode_paid_carries_no_choice_note(capsys):
    assert cli.main(["mode", "paid", "--json"]) == 0
    capsys.readouterr()
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=missing,meta=ok", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["mode"] == "paid"
    assert not any(i["note"] == doctor.evidence.CHOOSE_NOTE for i in out["items"] if "trendsmesh" in i["id"])


def test_trend_research_is_paid_only_even_on_free():
    r = doctor.check({"category_report"}, False, {"meta": "ok", "artifacts": "ok", "trendsmesh": "missing"},
                     playbook="trend-research", mode="free")
    assert not r.ready and not item(r, "mcp_trendsmesh_research").ok and not any(i.free for i in r.items)


def test_the_cli_reads_the_workspace_choice(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    from tm import offer
    offer.mode_set(tmp_path, "free")
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=missing,meta=ok", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "free" and out["warnings"] == []
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=missing,meta=ok", "--mode", "paid",
                     "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "paid" and "mcp_trendsmesh" in out["warnings"]


def test_a_failed_test_render_makes_the_video_tools_an_agent_fix(monkeypatch):
    """Issue #124: the files of the video tier are in place, but the test render fails. The row is not ready, Claude
    sets the tools up again after the user's yes, and the card quotes what failed."""
    monkeypatch.setattr(doctor, "_video_probe", lambda: (
        "failed", "Remotion test render failed: npm error could not determine executable to run"))
    r = doctor.check({"edited_video"}, False, ALL_OK)
    it = item(r, "tier_video")
    assert not it.ok and it.fixer == "agent" and not r.ready
    assert it.fix.startswith("The video editing tools are installed but a test render failed: ")
    assert "could not determine executable to run" in it.fix and "tm env install video --yes" in it.fix
    assert "❌ " + it.name in doctor.card(r)


def test_a_test_render_that_passed_now_says_so_once(monkeypatch):
    monkeypatch.setattr(doctor, "_video_probe", lambda: ("passed", ""))
    it = item(doctor.check({"edited_video"}, False, ALL_OK), "tier_video")
    assert it.ok and "test render passed" in it.name and "about a minute" in it.name
    monkeypatch.setattr(doctor, "_video_probe", lambda: ("cached", ""))
    it = item(doctor.check({"edited_video"}, False, ALL_OK), "tier_video")
    assert it.ok and "test render" not in it.name


def test_the_probe_runs_only_for_an_installed_video_tier(monkeypatch):
    ran = []
    monkeypatch.setattr(doctor, "_video_probe", lambda: ran.append(1) or ("cached", ""))
    doctor.check({"creative_brief"}, False, ALL_OK)
    assert not ran
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: t != "video")
    assert not item(doctor.check({"edited_video"}, False, ALL_OK), "tier_video").ok and not ran
    monkeypatch.setattr(doctor.envtiers, "installed", lambda t: True)
    doctor.check({"edited_video"}, False, ALL_OK)
    assert ran == [1]


def test_video_probe_runs_a_render_only_without_a_cached_pass(monkeypatch):
    from tm import render
    from tm.tools import _common
    ran = []
    monkeypatch.setattr(render, "probe_ok", lambda: True)
    monkeypatch.setattr(render, "probe", lambda: ran.append(1))
    assert REAL_PROBE() == ("cached", "") and not ran
    monkeypatch.setattr(render, "probe_ok", lambda: False)
    assert REAL_PROBE() == ("passed", "") and ran == [1]

    def broken():
        raise _common.ToolError("Remotion test render failed: boom")
    monkeypatch.setattr(render, "probe", broken)
    assert REAL_PROBE() == ("failed", "Remotion test render failed: boom")


SKILLS = Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks" / "skills"
_OUTPUTS = re.compile(r"--outputs\s+(?:<(?:chosen, from|one of)\s+)?([a-z_]+(?:[,|][a-z_]+)*)")


@pytest.mark.parametrize("pb", [p for p in doctor.playbooks.all_playbooks() if doctor.playbooks.bundled(p)],
                         ids=lambda p: p.skill)
def test_each_skill_names_its_exact_output_ids(pb):
    """Issue #124: the readiness command in each playbook's SKILL.md names the output ids `tm doctor` takes, read from
    the playbook's data (`flow.output_ids`), so a first call never fails on a guessed name."""
    text = (SKILLS / pb.skill / "SKILL.md").read_text(encoding="utf-8")
    named = [i for m in _OUTPUTS.finditer(text) for i in re.split(r"[,|]", m.group(1))]
    assert named, f"{pb.skill}/SKILL.md gives no --outputs ids"
    assert set(named) == set(doctor.flow.output_ids(pb.id)), f"{pb.skill}/SKILL.md names {named}"


@pytest.mark.parametrize("given, hint", [("brief", "creative_brief"), ("video", "edited_video"),
                                         ("edited_vidoe", "edited_video"), ("zzz", None)])
def test_an_unknown_output_suggests_the_closest_id(capsys, given, hint):
    code = cli.main(["doctor", "--outputs", given, "--json"])
    message = json.loads(capsys.readouterr().out)["message"]
    assert code == 1 and message.startswith(f"Unknown output {given}.")
    assert (f"Did you mean {hint}?" in message) if hint else "Did you mean" not in message
    assert "Choose from: creative_brief, edited_video, ai_video, live_test." in message


ARTIFACT_ROWS = {"artifacts_pages": "trend-research", "artifacts_pages_brief": "creative-brief",
                 "artifacts_pages_organic": "organic-video", "artifacts_pages_create": "create-ad"}


@pytest.mark.parametrize("row, pb", ARTIFACT_ROWS.items())
def test_a_refused_publish_is_recorded_as_denied_with_the_allow_step(row, pb):
    """Issue #125: when Claude Code's permissions refused a page publish, `artifacts=denied` says so and how to allow
    it; the row stays a warning, as without a publishing tool."""
    outputs = {doctor.flow.output_ids(pb)[0]}
    r = doctor.check(outputs, False, {"trendsmesh": "ok", "meta": "ok", "artifacts": "denied"}, playbook=pb)
    it = item(r, row)
    assert not it.ok and it.warn and not it.pending and it.fixer == "user"
    assert it.fix.startswith("Claude Code's permission settings refused to publish a page")
    assert "`Artifact`" in it.fix and "permissions.allow" in it.fix and "tell me and I check again" in it.fix
    missing = item(doctor.check(outputs, False, {"trendsmesh": "ok", "meta": "ok", "artifacts": "missing"},
                                playbook=pb), row)
    assert "permission" not in missing.fix


def test_denied_is_a_state_of_artifacts_only(capsys):
    assert "denied" in doctor.MCP_STATES and doctor.MCP_STATES_OF["artifacts"] == ("ok", "missing", "denied")
    assert cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "meta=denied", "--json"]) == 1
    capsys.readouterr()
    assert cli.main(["doctor", "--playbook", "create-ad", "--outputs", "video_ad", "--mcp",
                     "trendsmesh=ok,meta=ok,artifacts=denied", "--json"]) == 0


def test_creative_brief_reads_the_legacy_animatics_output(capsys, bundled_skills):
    """`animatics`, an output before issue #145 (the animatics are made on request now), is read and left out."""
    rows = []
    for outputs in (CB_OUTPUTS, "review_pack,briefs,animatics,page"):
        code = cli.main(["doctor", "--playbook", "creative-brief", "--outputs", outputs,
                         "--mcp", "trendsmesh=ok,meta=ok,artifacts=ok", "--json"])
        out = json.loads(capsys.readouterr().out)
        assert code in (0, 2), out
        rows.append([i["id"] for i in out["items"]])
    assert rows[0] == rows[1] and "browser_for_animatics" in rows[0] and "tier_animatic" in rows[0]
