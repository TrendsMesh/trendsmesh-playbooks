import json
import os

from tm import paths
from tm.paths import data_dir, plugin_root, pixi_bin, pixi_env, workspace


def _isolate(tmp_path, monkeypatch):
    for var in ("TM_PLUGIN_ROOT", "TM_PLUGIN_DATA", "TM_WORKSPACE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def _paths_json(tmp_path, **kw):
    (tmp_path / ".trendsmesh").mkdir(exist_ok=True)
    (tmp_path / ".trendsmesh/paths.json").write_text(json.dumps(kw))


def test_paths_prefers_env_then_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "d"))
    assert data_dir() == tmp_path / "d"
    monkeypatch.delenv("TM_PLUGIN_DATA")
    _paths_json(tmp_path, plugin_data=(tmp_path / "x").as_posix())
    assert data_dir() == tmp_path / "x"


def test_plugin_root_env_then_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _paths_json(tmp_path, plugin_root=(tmp_path / "r").as_posix())
    assert plugin_root() == tmp_path / "r"
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(tmp_path / "e"))
    assert plugin_root() == tmp_path / "e"


def test_missing_everywhere_raises_clear_error(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    try:
        data_dir()
    except RuntimeError as exc:
        assert "session" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_workspace_is_cwd_unless_overridden(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert workspace() == tmp_path
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "w"))
    assert workspace() == tmp_path / "w"


def test_pixi_bin_from_file_else_data_dir(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "d"))
    expected = tmp_path / "d" / "pixi" / "bin" / ("pixi.exe" if os.name == "nt" else "pixi")
    assert pixi_bin() == expected
    _paths_json(tmp_path, pixi=(tmp_path / "elsewhere/pixi").as_posix())
    assert pixi_bin() == tmp_path / "elsewhere/pixi"


def test_pixi_env_points_pixi_at_the_data_folder(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    data = tmp_path / "d with space"
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    env = pixi_env()
    assert env["PIXI_HOME"] == str(data / "pixi")
    assert env["PIXI_NO_PATH_UPDATE"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    config = (data / "pixi" / "config.toml").read_text()
    assert f'detached-environments = "{(data / "envs").as_posix()}"' in config
    assert pixi_env() == env  # idempotent
