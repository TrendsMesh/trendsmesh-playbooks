"""`tm permissions allow` (issue #163): in Claude Code's auto mode a run asks once, at readiness, to allow the plugin's
commands and pages, and on the user's yes adds the rules to the project's .claude/settings.local.json, merged with
what is there."""

import json
import time

import pytest

from tm import permissions
from tm.cli import main

RULES = ["Bash(tm *)", "PowerShell(tm *)", "Artifact"]


@pytest.fixture
def project(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "user-claude"))
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.delenv("TM_WORKSPACE", raising=False)
    return proj


def record(mode: str, proj, age: float = 0) -> None:
    """What the key guard writes before a `tm permissions` command (bootstrap/guard-secrets.sh)."""
    data = permissions.paths.data_dir()
    (data / "permission-mode").write_text(f"{int(time.time() - age)}\t{mode}\t{proj}\n", encoding="utf-8")


def answer(capsys, *argv):
    code = main(["permissions", "allow", *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def settings(proj):
    return json.loads((proj / ".claude" / "settings.local.json").read_text(encoding="utf-8"))


def test_the_rules_are_the_owners_three():
    assert list(permissions.RULES) == RULES


def test_auto_mode_without_the_rules_asks_once_and_a_dry_run_writes_nothing(project, capsys):
    record("auto", project)
    code, out = answer(capsys)
    assert code == 0 and out["mode"] == "auto" and out["ask"] is True
    assert out["missing"] == RULES and out["present"] == []
    assert out["question"] == "So the run doesn't stop on the way, allow the plugin's commands and its pages?"
    assert out["file"] == str(project / ".claude" / "settings.local.json") and out["written"] is False
    assert not (project / ".claude").exists()


def test_yes_creates_the_file_when_it_is_missing(project, capsys):
    record("auto", project)
    code, out = answer(capsys, "--yes")
    assert code == 0 and out["written"] is True and out["added"] == RULES
    assert settings(project) == {"permissions": {"allow": RULES}}


def test_yes_keeps_the_users_own_rules_and_their_order(project, capsys):
    record("auto", project)
    own = {"model": "x", "permissions": {"deny": ["Bash(rm *)"], "allow": ["Bash(git status)", "Artifact",
                                                                          "Read(*)"]},
           "env": {"A": "1"}}
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text(json.dumps(own, indent=4), encoding="utf-8")
    code, out = answer(capsys, "--yes")
    assert code == 0 and out["added"] == ["Bash(tm *)", "PowerShell(tm *)"]
    got = settings(project)
    assert list(got) == ["model", "permissions", "env"] and got["env"] == {"A": "1"}
    assert got["permissions"]["deny"] == ["Bash(rm *)"]
    assert got["permissions"]["allow"] == ["Bash(git status)", "Artifact", "Read(*)", "Bash(tm *)", "PowerShell(tm *)"]
    assert (project / ".claude" / "settings.local.json").read_text(encoding="utf-8").startswith('{\n    "model"')


def test_present_rules_ask_nothing_and_are_never_added_twice(project, capsys):
    record("auto", project)
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(tm:*)", "PowerShell(tm *)", "Artifact"]}}), encoding="utf-8")
    code, out = answer(capsys)
    assert code == 0 and out["ask"] is False and out["missing"] == []
    code, out = answer(capsys, "--yes")
    assert code == 0 and out["added"] == [] and out["written"] is False
    assert settings(project)["permissions"]["allow"] == ["Bash(tm:*)", "PowerShell(tm *)", "Artifact"]


def test_rules_in_the_shared_or_user_settings_count(project, capsys, tmp_path):
    record("auto", project)
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Artifact"]}}),
                                                       encoding="utf-8")
    user = tmp_path / "user-claude"
    user.mkdir()
    (user / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(tm *)", "PowerShell(tm *)"]}}),
                                        encoding="utf-8")
    code, out = answer(capsys)
    assert code == 0 and out["ask"] is False and out["missing"] == []


def test_invalid_json_is_refused_without_writing(project, capsys):
    record("auto", project)
    (project / ".claude").mkdir()
    bad = '{"permissions": {"allow": ["Read(*)",]}}'
    (project / ".claude" / "settings.local.json").write_text(bad, encoding="utf-8")
    code, out = answer(capsys, "--yes")
    assert code == 1 and out["status"] == "error" and "not valid JSON" in out["message"]
    assert "nothing was changed" in out["message"] and '"Bash(tm *)"' in out["message"]
    assert (project / ".claude" / "settings.local.json").read_text(encoding="utf-8") == bad


@pytest.mark.parametrize("text", ['["Artifact"]', '{"permissions": ["Artifact"]}',
                                  '{"permissions": {"allow": "Artifact"}}'])
def test_a_file_of_another_shape_is_refused_without_writing(project, capsys, text):
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text(text, encoding="utf-8")
    code, out = answer(capsys, "--yes")
    assert code == 1 and "nothing was changed" in out["message"]
    assert (project / ".claude" / "settings.local.json").read_text(encoding="utf-8") == text


def test_a_bom_file_is_read_and_kept_valid(project, capsys):
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.local.json").write_text('﻿{"permissions": {"allow": []}}',
                                                             encoding="utf-8")
    code, out = answer(capsys, "--yes")
    assert code == 0 and settings(project) == {"permissions": {"allow": RULES}}


@pytest.mark.parametrize("mode, ask", [("auto", True), ("default", False), ("acceptEdits", False),
                                       ("bypassPermissions", False), ("plan", False)])
def test_only_auto_mode_asks(project, capsys, mode, ask):
    record(mode, project)
    code, out = answer(capsys)
    assert code == 0 and out["mode"] == mode and out["ask"] is ask


def test_an_unknown_mode_asks_when_rules_are_missing(project, capsys):
    """No record (the hook did not run, or an older Claude Code sent no mode), a stale one, or another project's:
    the mode is unknown, and the question is asked whenever the needed rules are missing (#163 decision)."""
    code, out = answer(capsys)
    assert out["mode"] == "unknown" and out["ask"] is True
    record("default", project, age=600)
    code, out = answer(capsys)
    assert out["mode"] == "unknown" and out["ask"] is True
    record("", project)
    code, out = answer(capsys)
    assert out["mode"] == "unknown"


def test_the_recorded_project_is_the_default_folder(project, capsys, tmp_path):
    """The hook records Claude Code's project folder (CLAUDE_PROJECT_DIR): the settings go there even when the
    command runs in a subfolder; --project wins over it."""
    sub = project / "runs" / "01-x"
    sub.mkdir(parents=True)
    import os
    os.chdir(sub)
    record("auto", project)
    code, out = answer(capsys)
    assert out["file"] == str(project / ".claude" / "settings.local.json") and out["mode"] == "auto"
    other = tmp_path / "other"
    other.mkdir()
    code, out = answer(capsys, "--project", str(other))
    assert out["file"] == str(other / ".claude" / "settings.local.json") and out["mode"] == "unknown"


def test_the_evals_sandbox_gives_the_mode_without_a_hook(project, capsys, monkeypatch):
    monkeypatch.setenv("TM_PERMISSION_MODE", "default")
    record("auto", project)
    code, out = answer(capsys)
    assert out["mode"] == "default" and out["ask"] is False
    assert out["file"] == str(project / ".claude" / "settings.local.json")


# Change request on #176 line 65: only the rules the user's system needs bring the question; a yes still adds the
# whole set.

def own_rules(proj, rules):
    (proj / ".claude").mkdir(exist_ok=True)
    (proj / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {"allow": rules}}),
                                                          encoding="utf-8")


def test_the_rules_each_system_needs():
    assert permissions.needed(windows=False) == ["Bash(tm *)", "Artifact"]
    assert permissions.needed(windows=True) == RULES


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_on_a_mac_or_linux_a_missing_powershell_rule_asks_nothing(project, capsys, monkeypatch, platform):
    monkeypatch.setattr(permissions.sys, "platform", platform)
    record("auto", project)
    own_rules(project, ["Bash(tm *)", "Artifact"])
    code, out = answer(capsys)
    assert code == 0 and out["ask"] is False and out["needed"] == ["Bash(tm *)", "Artifact"]
    assert out["missing"] == ["PowerShell(tm *)"]


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_on_a_mac_or_linux_a_yes_still_adds_the_powershell_rule(project, capsys, monkeypatch, platform):
    monkeypatch.setattr(permissions.sys, "platform", platform)
    record("auto", project)
    own_rules(project, ["Artifact"])
    code, out = answer(capsys)
    assert out["ask"] is True and out["missing"] == ["Bash(tm *)", "PowerShell(tm *)"]
    code, out = answer(capsys, "--yes")
    assert code == 0 and out["added"] == ["Bash(tm *)", "PowerShell(tm *)"] and out["missing"] == []
    assert settings(project)["permissions"]["allow"] == ["Artifact", "Bash(tm *)", "PowerShell(tm *)"]


@pytest.mark.parametrize("have, missing", [(["Bash(tm *)", "Artifact"], ["PowerShell(tm *)"]),
                                           (["PowerShell(tm *)", "Artifact"], ["Bash(tm *)"])])
def test_on_windows_both_shells_rules_count(project, capsys, monkeypatch, have, missing):
    """On Windows Claude Code may run tm through its Bash tool (Git Bash) or its PowerShell tool, so either rule
    missing brings the question."""
    monkeypatch.setattr(permissions.sys, "platform", "win32")
    record("auto", project)
    own_rules(project, have)
    code, out = answer(capsys)
    assert code == 0 and out["ask"] is True and out["needed"] == RULES and out["missing"] == missing
    code, out = answer(capsys, "--yes")
    assert out["added"] == missing
    code, out = answer(capsys)
    assert out["ask"] is False and out["missing"] == []
