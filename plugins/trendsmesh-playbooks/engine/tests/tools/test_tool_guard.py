"""Every tool answers in the contract's shape: one JSON object with --json, exit 0, 1 or 2."""

import json

import pytest

from tm.tools import _common as c
from tm.tools import vo_qa


def test_unexpected_exception_is_one_json_error(run, monkeypatch, capsys):
    def broken(*a, **k):
        return 1 / 0

    monkeypatch.setattr(vo_qa, "compare", broken)
    assert vo_qa.main(["--run", str(run.path), "a.wav", "b.wav", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "error", "message": "Unexpected ZeroDivisionError: division by zero"}


def test_bad_arguments_are_an_error_not_a_stop(run, capsys):
    assert vo_qa.main(["--run", str(run.path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_missing_module_is_a_stop_to_update_the_tier(run, monkeypatch, capsys):
    def missing(*a, **k):
        raise ModuleNotFoundError("No module named 'numpy'", name="numpy")

    monkeypatch.setattr(vo_qa, "compare", missing)
    assert vo_qa.main(["--run", str(run.path), "a.wav", "b.wav", "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "tm env install voice" in out["message"]


def test_media_paths_are_absolute_for_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert c.media("-weird:name.mp4") == str(tmp_path.resolve() / "-weird:name.mp4")


def test_cost_report_is_written_only_when_asked(tmp_path, monkeypatch):
    monkeypatch.delenv("TM_COST_REPORT", raising=False)
    c.report_cost(True, 3)  # nowhere to write: nothing happens
    target = tmp_path / "cost.json"
    monkeypatch.setenv("TM_COST_REPORT", str(target))
    c.report_cost(True, 3)
    assert json.loads(target.read_text()) == {"spent": True, "actual": 3}


@pytest.mark.parametrize("fps", [0.0])
def test_teardown_refuses_unknown_frame_rate(fps, monkeypatch, tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("scenedetect")
    from tm.tools import teardown

    monkeypatch.setattr(teardown.c, "probe", lambda v: {"is_video": True, "has_video": True, "fps": fps,
                                                       "width": 540, "height": 960, "frames": 10})
    with pytest.raises(c.ToolError, match="frame rate"):
        teardown._Clip(tmp_path / "v.mp4")
