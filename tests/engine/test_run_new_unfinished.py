"""Issue #90, point 5: `tm run new` returns `unfinished_runs`, this playbook's runs of the same name or channel that
were started and are not done (folder, date, step), so the skill always asks "continue it, or start a new one?"."""

import json
from datetime import date

import pytest
import yaml

from tm import playbooks, state
from tm.cli import main
from tm.runfolder import RunFolder

PLAYBOOKS = ["refresh-ad", "trend-research", "creative-brief", "organic-video", "create-ad"]


def _old(ws, playbook, name, day, *, step="C3", status="active", channels=None):
    run = RunFolder.create(ws, name, date(2026, 11, day), playbook=playbooks.get(playbook).id)
    s = state.load(run)
    s.step, s.status = step, status
    state.save(run, s)
    if channels is not None:
        (run.path / "config.yaml").write_text(yaml.safe_dump({"channels": channels}), encoding="utf-8")
    return run


@pytest.mark.parametrize("playbook", PLAYBOOKS)
def test_run_new_lists_the_unfinished_runs_of_its_name(tmp_path, monkeypatch, capsys, playbook):
    ws = tmp_path / "ws"
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    stopped = _old(ws, playbook, "ExampleEdu", 3, step="C3", status="stopped")
    second = _old(ws, playbook, "exampleedu", 5, step="B1")               # the same name, any case
    later = _old(ws, playbook, "exampleedu-2", 5, step="A1")              # the same day's second run
    _old(ws, playbook, "exampleedu", 4, step="end", status="done")        # done: nothing to continue
    _old(ws, playbook, "exampleedu", 6, step=None)                        # made and never used
    _old(ws, playbook, "exampleedu-shop", 6)                              # another name
    other = "organic-video" if playbook != "organic-video" else "creative-brief"
    _old(ws, other, "exampleedu", 6)                                      # another playbook's
    assert main(["run", "new", "--playbook", playbook, "--name", "exampleedu", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    rel = lambda run: run.path.relative_to(ws).as_posix()                 # noqa: E731
    assert [r["folder"] for r in out["unfinished_runs"]] == [rel(later), rel(second), rel(stopped)], out
    assert out["unfinished_runs"][-1] == {"folder": rel(stopped), "created": "2026-11-03", "step": "C3",
                                          "status": "stopped"}
    assert "Ask the user first whether to continue one" in out["message"]
    assert later.path.name.endswith("_exampleedu-2")


def test_organic_video_lists_the_channels_production_runs_too(tmp_path, monkeypatch, capsys):
    ws = tmp_path / "ws"
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    production = _old(ws, "organic-video", "exampleedu-m5", 4, step="F2", channels=["exampleedu"])
    _old(ws, "organic-video", "petstore-p1", 4, step="F2", channels=["petstore"])
    assert main(["run", "new", "--playbook", "organic-video", "--name", "exampleedu", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [r["folder"] for r in out["unfinished_runs"]] == [production.path.relative_to(ws).as_posix()]


def test_run_new_with_nothing_unfinished_says_nothing_more(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "ws"))
    assert main(["run", "new", "--playbook", "organic-video", "--name", "exampleedu", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["unfinished_runs"] == [] and out["message"] == out["path"]
