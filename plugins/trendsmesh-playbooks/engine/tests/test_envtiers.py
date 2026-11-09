import json
import subprocess

import pytest

from tm import envtiers
from tm.cli import main
from tm.envtiers import TIERS, install, installed, tiers_for


def test_brief_needs_base_and_breakdown():
    assert tiers_for({"creative_brief"}, voice=False) == ["base", "breakdown"]


def test_edited_video_with_voice_adds_video_voice_and_ai():
    assert tiers_for({"edited_video"}, voice=True) == ["base", "breakdown", "video", "voice", "ai"]


def test_install_without_yes_stops_with_size(capsys):
    assert install("breakdown", yes=False) == 2
    assert "GB" in capsys.readouterr().out


def test_tier_sizes():
    assert {n: t.approx_mb for n, t in TIERS.items()} == {
        "base": 500, "breakdown": 2500, "video": 500, "voice": 1000, "ai": 20, "animatic": 150}


@pytest.fixture
def fake_pixi(tmp_path, monkeypatch):
    root = tmp_path / "root with space" / "Łukasz"
    (root / "env").mkdir(parents=True)
    monkeypatch.setattr(envtiers.paths, "plugin_root", lambda: root)
    monkeypatch.setattr(envtiers.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(envtiers.paths, "pixi_env", lambda: {"PIXI_HOME": "h", "PIXI_NO_PATH_UPDATE": "1"})
    calls = []
    monkeypatch.setattr(envtiers.subprocess, "run", lambda *a, **k: calls.append((a, k)) or _result.pop())
    return calls, root


_result = []


def _proc(code=0, out=""):
    return subprocess.CompletedProcess([], code, stdout=out, stderr="")


def test_install_runs_pixi_with_argv_and_env(fake_pixi):
    calls, root = fake_pixi
    _result.append(_proc())
    assert install("voice", yes=True) == 0
    argv = calls[0][0][0]
    assert argv[1:] == ["install", "--frozen", "-e", "voice", "--manifest-path", str(root / "env" / "pixi.toml")]
    assert isinstance(argv, list) and "shell" not in calls[0][1]
    assert calls[0][1]["env"]["PIXI_NO_PATH_UPDATE"] == "1"


def test_install_failure_returns_one(fake_pixi):
    _result.append(_proc(1))
    assert install("ai", yes=True) == 1


def test_installed_reads_marker_in_prefix(fake_pixi, tmp_path):
    prefix = tmp_path / "envs" / "voice"
    info = json.dumps({"environments_info": [{"name": "voice", "prefix": str(prefix)}]})
    _result.append(_proc(0, info))
    assert installed("voice") is False
    (prefix / "conda-meta").mkdir(parents=True)
    (prefix / "conda-meta" / "pixi").write_text("{}")
    _result.append(_proc(0, info))
    assert installed("voice") is True


def test_installed_false_when_pixi_fails(fake_pixi):
    _result.append(_proc(1))
    assert installed("ai") is False


def test_status_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(envtiers, "installed", lambda t: t == "base")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # never the real data folder
    assert main(["env", "status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tiers"]["base"]["installed"] is True and data["tiers"]["ai"]["installed"] is False


def test_cli_install_without_yes_exits_two(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # never the real data folder
    assert main(["env", "install", "video"]) == 2


def _env_folder(data, name, manifest):
    """A detached pixi environment folder as pixi lays it out, with its conda-meta/pixi marker."""
    meta = data / "envs" / name / "envs" / "base" / "conda-meta"
    meta.mkdir(parents=True)
    (meta / "pixi").write_text(json.dumps({"manifest_path": str(manifest), "environment_name": "base"}),
                               encoding="utf-8")
    (meta / "python-3.11.json").write_text("{}", encoding="utf-8")
    return data / "envs" / name


def test_environments_of_removed_plugin_versions_are_cleaned(tmp_path, monkeypatch):
    """Final review I9 (Ruling 25): pixi keys a detached environment on the manifest's path, so
    every plugin version installs its own. Folders whose manifest is gone are removed."""
    data = tmp_path / "plugin data Łukasz"
    current = tmp_path / "cache" / "0.2.0" / "env" / "pixi.toml"
    current.parent.mkdir(parents=True)
    current.write_text("", encoding="utf-8")
    old = _env_folder(data, "trendsmesh-playbooks-111", tmp_path / "cache" / "0.1.0" / "env" / "pixi.toml")
    live = _env_folder(data, "trendsmesh-playbooks-222", current)
    partial = data / "envs" / "trendsmesh-playbooks-333" / "envs" / "base"
    partial.mkdir(parents=True)                                    # no marker: an install under way
    (data / "envs" / "stray.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: data)
    assert envtiers.clean_stale() == [old]
    assert not old.exists() and live.is_dir() and partial.is_dir()
    assert envtiers.clean_stale() == []
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path / "nothing here")
    assert envtiers.clean_stale() == []


def test_env_status_cleans_old_versions_first(tmp_path, monkeypatch, capsys):
    data = tmp_path / "data"
    old = _env_folder(data, "trendsmesh-playbooks-111", tmp_path / "gone" / "pixi.toml")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: data)
    monkeypatch.setattr(envtiers, "installed", lambda tier: False)
    assert main(["env", "status", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert not old.exists() and out["removed_old_environments"] == 1
