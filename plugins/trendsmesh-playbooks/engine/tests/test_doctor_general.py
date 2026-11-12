"""Issue 76: the doctor with no playbook chosen runs a short general check (the base tools, the keys' states, the
TrendsMesh sign-in) without Meta Ads; the support report names Windows 11 by its build; one sentence about sending
the report."""

import json
import re
from collections import namedtuple
from pathlib import Path

import pytest

from tm import cli, doctor, i18n, playbooks

Usage = namedtuple("Usage", "total used free")
GB = 1024**3
PLUGIN = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    """Everything installed, plenty of disk, macOS, no keys, workspace in tmp (as test_doctor.py's)."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: True)
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(500 * GB, 100 * GB, 400 * GB))
    monkeypatch.setattr(doctor, "_os_key", lambda: "macos")
    return data


def general(mcp=None, **kw):
    return doctor.check(set(), False, {"trendsmesh": "ok"} if mcp is None else mcp, playbook=doctor.GENERAL, **kw)


def one_playbook():
    names = ", ".join(pb.name for pb in playbooks.all_playbooks() if playbooks.bundled(pb))
    return i18n.t("doctor.general.one_playbook", playbooks=names)


def item(r, id_):
    return next(i for i in r.items if i.id == id_)


def _answers(monkeypatch, tmp_path, **by_provider):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({k: {"status": s, "body": b} for k, (s, b) in by_provider.items()}))
    monkeypatch.setenv("TM_PROVIDER_ANSWERS", str(path))


# --- what the general check looks at ----------------------------------------------------------------------------

def test_the_general_check_has_the_base_tools_the_keys_and_trendsmesh_and_no_meta():
    r = general()
    ids = [i.id for i in r.items]
    assert "tier_base" in ids and "disk_free" in ids
    assert "replicate_api_token_general" in ids and "elevenlabs_api_key_general" in ids
    assert "mcp_trendsmesh_general" in ids
    assert not [i for i in ids if "meta" in i or "artifacts" in i or i.startswith("tier_") and i != "tier_base"]


def test_the_general_check_installs_only_the_base_tools(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: False)
    r = general()
    assert not r.ready
    assert [i.id for i in r.items if i.id.startswith("tier_")] == ["tier_base"]
    assert not item(r, "tier_base").ok and item(r, "tier_base").fixer == "agent"


def test_missing_keys_and_no_trendsmesh_are_warnings_in_the_general_check():
    r = general({"trendsmesh": "missing"})
    assert r.ready
    for id_ in ("replicate_api_token_general", "elevenlabs_api_key_general", "mcp_trendsmesh_general"):
        assert item(r, id_).warn and not item(r, id_).ok, id_
    assert item(r, "replicate_api_token_general").name == "Replicate token: missing"
    assert item(r, "elevenlabs_api_key_general").name == "ElevenLabs key: missing"


def test_the_general_check_shows_each_keys_state_from_one_free_call(world, monkeypatch, tmp_path):
    (world / "secrets.env").write_text("REPLICATE_API_TOKEN=r8_x\nELEVENLABS_API_KEY=k\n")
    _answers(monkeypatch, tmp_path, replicate=(200, {"type": "user", "username": "someone"}),
             elevenlabs=(401, {"detail": {"code": "invalid_api_key"}}))
    r = general()
    rep, el = item(r, "replicate_api_token_general"), item(r, "elevenlabs_api_key_general")
    assert rep.ok and rep.state == "works"
    assert not el.ok and el.state == "unusable" and el.warn and r.ready
    assert "https://elevenlabs.io/app/settings/api-keys" in el.fix


def test_the_general_check_reads_the_trendsmesh_plan():
    r = general({"trendsmesh": "free"})
    assert r.ready and item(r, "trendsmesh_agent_plan_general").warn
    assert not item(r, "trendsmesh_agent_plan_general").ok


def test_trendsmesh_not_checked_stays_on_claudes_list():
    r = general({})
    it = item(r, "mcp_trendsmesh_general")
    assert it.unchecked and it.fixer == "agent"
    assert "I still need to check these" in doctor.card(r, general=True)


# --- the card ---------------------------------------------------------------------------------------------------

def test_the_general_card_speaks_of_the_plugin_not_a_run_and_says_how_to_check_one_playbook():
    card = doctor.card(general(), general=True)
    assert card.startswith(i18n.t("doctor.general.ready"))
    assert "this run" not in card and "Refresh an ad: readiness check" not in card
    assert one_playbook() in card


def test_the_general_card_when_something_blocks(monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: False)
    card = doctor.card(general(), general=True)
    assert card.startswith(i18n.t("doctor.general.not_ready"))
    assert "The run continues from the same place" not in card
    assert one_playbook() in card


def test_a_playbooks_card_is_unchanged_by_the_general_wording():
    card = doctor.card(doctor.check({"creative_brief"}, False, {"trendsmesh": "ok", "meta": "ok"}))
    assert card.startswith("**Ready to go.** Everything this run needs is in place.")
    assert "This was the general check" not in card


# --- the command line -------------------------------------------------------------------------------------------

def test_cli_general_needs_no_outputs_and_no_meta(capsys):
    code = cli.main(["doctor", "--general", "--mcp", "trendsmesh=ok", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ready"] and out["playbook"] is None
    assert one_playbook() in out["card"] and "Create an ad" in out["card"]
    assert not [i for i in out["items"] if "meta" in i["id"]]


@pytest.mark.parametrize("args,says", [
    (["--general", "--mcp", "trendsmesh=ok,meta=ok"], "TrendsMesh only"),
    (["--general", "--outputs", "creative_brief"], "--general"),
    (["--general", "--playbook", "trend-research"], "--general"),
    ([], "--outputs"),
])
def test_cli_general_refuses_what_belongs_to_a_playbook(capsys, args, says):
    assert cli.main(["doctor", *args, "--json"]) == 1
    assert says in capsys.readouterr().out


def test_a_playbook_check_still_needs_its_outputs_and_says_which_playbook(capsys):
    code = cli.main(["doctor", "--outputs", "creative_brief", "--mcp", "trendsmesh=ok,meta=ok", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["playbook"] == "01-refresh-ad"


# --- the support report -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("version,name", [
    ("10.0.22000", "Windows 11"), ("10.0.22631", "Windows 11"), ("10.0.26100", "Windows 11"),
    ("10.0.19045", "Windows 10"), ("10.0.10240", "Windows 10"),
])
def test_the_report_names_windows_11_by_its_build(monkeypatch, version, name):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(doctor.platform, "release", lambda: "10")
    monkeypatch.setattr(doctor.platform, "version", lambda: version)
    monkeypatch.setattr(doctor.platform, "machine", lambda: "AMD64")
    build = version.rsplit(".", 1)[1]
    assert doctor.system_name() == f"{name} (build {build}, AMD64)"
    text = doctor.support_report(general(), "").read_text(encoding="utf-8")
    assert f"- System: {name} (build {build}, AMD64)" in text


def test_an_unreadable_windows_version_keeps_the_release(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(doctor.platform, "release", lambda: "10")
    monkeypatch.setattr(doctor.platform, "version", lambda: "")
    monkeypatch.setattr(doctor.platform, "machine", lambda: "AMD64")
    assert doctor.system_name() == "Windows 10 (AMD64)"


def test_other_systems_keep_their_release(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor.platform, "release", lambda: "25.5.0")
    monkeypatch.setattr(doctor.platform, "machine", lambda: "arm64")
    assert doctor.system_name() == "Darwin 25.5.0 (arm64)"


def test_the_acceptance_report_names_the_system_the_same_way():
    from tm import acceptance
    assert "doctor.system_name()" in Path(acceptance.__file__).read_text(encoding="utf-8")


def test_one_sentence_about_sending_the_report(capsys):
    send = i18n.t("doctor.report.send")
    assert "contact@trendsmesh.com" in send and "privately" in send and "read it" in send
    text = doctor.support_report(general(), "").read_text(encoding="utf-8")
    assert send in text
    assert cli.main(["doctor", "--general", "--mcp", "trendsmesh=ok", "--report"]) == 0
    assert send in capsys.readouterr().out
    command = " ".join((PLUGIN / "commands" / "doctor.md").read_text(encoding="utf-8").split())
    assert "as it is" not in command and "send it privately" in command and "read it" in command


def test_no_other_support_address_in_the_plugin():
    found = []
    for p in PLUGIN.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".py", ".yaml", ".json", ".sh", ".txt"} and ".pixi" not in p.parts:
            text = p.read_text(encoding="utf-8", errors="replace")
            found += [f"{p.relative_to(PLUGIN)}: {m}" for m in re.findall(r"[a-z]+@trendsmesh\.com", text)
                      if m != "contact@trendsmesh.com"]
    assert not found, found


# --- the command ------------------------------------------------------------------------------------------------

def test_doctor_md_runs_the_general_check_when_no_playbook_is_named():
    command = (PLUGIN / "commands" / "doctor.md").read_text(encoding="utf-8")
    step0 = " ".join(command.split("\n1. ", 1)[0].split())
    assert 'otherwise it is "Refresh an ad"' not in step0
    assert "General check" in step0
    general_md = " ".join(command.split("**General check.**", 1)[1].split("\n**", 1)[0].split())
    assert "tm doctor --general --mcp trendsmesh=<result> --report --json" in general_md
    assert "Meta Ads" in general_md and "readiness check" in general_md
    assert "how to check one playbook" in general_md
