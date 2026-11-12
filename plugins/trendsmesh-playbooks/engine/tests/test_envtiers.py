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
        "base": 500, "breakdown": 2500, "video": 500, "voice": 1000, "ai": 20, "animatic": 150, "ocr": 350}


def test_the_ocr_tier_is_never_asked_for_by_a_route():
    """Issue 57: OCR is optional. No output needs it, so no playbook's route (and no doctor card) asks for it; the
    teardown says when it would help, and the playbook offers it once."""
    from tm import doctor, playbooks

    every = {"creative_brief", "edited_video", "ai_video", "live_test", "animatics", "organic_video", "video_ad",
             "review_pack", "briefs", "page", "proposals", "weekly_plan", "script_to_film", "category_report",
             "weekly_digest", "paid_view"}
    assert "ocr" not in tiers_for(every, voice=True)
    for pb in playbooks.all_playbooks():
        assert "ocr" not in doctor.route_tiers(pb.id, every, voice=True)
    assert TIERS["ocr"].env == "ocr" and TIERS["ocr"].needs == ["base"]


def test_the_ocr_environment_pins_rapidocr_and_stays_out_of_the_others():
    import tomllib
    from pathlib import Path

    manifest = tomllib.loads((Path(__file__).resolve().parents[2] / "env" / "pixi.toml").read_text(encoding="utf-8"))
    deps = manifest["feature"]["ocr"]["pypi-dependencies"]
    assert deps["rapidocr"].startswith("==") and deps["onnxruntime"].startswith("==")
    envs = manifest["environments"]
    assert "ocr" in envs["ocr"]["features"]
    assert not any("ocr" in (e.get("features") or []) for name, e in envs.items() if name != "ocr")


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


def test_video_counts_as_installed_only_with_the_remotion_setup(monkeypatch):
    """#4: render needs the Remotion packages and headless browser for this lock file (`render.setup_done`), which
    `tm env install video` sets up; the pixi environment alone is not the video tier."""
    from tm import render
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: True)
    monkeypatch.setattr(render, "setup_done", lambda: False)
    assert installed("video") is False and installed("base") is True
    monkeypatch.setattr(render, "setup_done", lambda: True)
    assert installed("video") is True
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: False)
    assert installed("video") is False


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
