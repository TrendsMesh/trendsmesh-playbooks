"""A file the skill names run-relative (`03_wip/brand_v02.json`) is found from the workspace, where
Claude works (the collector needs it there): the run first, then the cwd (issue #90), for tm brand check and save,
tm config write, tm voice import and tm trends ingest. The commands are the ones flow.md#a1 and
references/trend-collection.md write."""

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from tm import trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

def _slashes(message: str) -> str:
    """Windows writes paths with backslashes (doubled inside an OSError's repr)."""
    return re.sub(r"\\+", "/", message)


PLUGIN = Path(__file__).resolve().parents[2]
EXAMPLE = PLUGIN / "skills" / "creative-brief" / "templates" / "intake_answers_example.json"
PROFILE = {
    "schema": "brand/1", "kind": "brand", "brand": "Night School",
    "stands_for": "Sleep better with a calm evening routine.", "tone": ["warm", "plain", "dry"],
    "off_limits": ["medical claims"], "off_limits_asked": True,
    "claims": [{"claim": "Read in 20 minutes", "wording": "A 20-minute read", "source": "00_raw/landing.md"}],
    "competitors": ["Calm"], "guide": {"source": "none", "where": ""},
    "drafted_from": ["landing", "user"], "confirmed": "2026-11-07",
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace, the current folder, with one creative brief run; R is its path from there."""
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.chdir(folder)
    run = RunFolder.create(folder, "nightschool", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    return folder, run, run.path.relative_to(folder).as_posix()


def _put(run: RunFolder, rel: str, data) -> None:
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_a1_brand_and_config_files_named_run_relative_from_the_workspace(ws, capsys):
    folder, run, r = ws
    _put(run, "03_wip/brand_v01.json", PROFILE)
    code, out = _cli(capsys, "brand", "check", "--run", r, "--file", "03_wip/brand_v01.json")
    assert code == 0, out
    code, out = _cli(capsys, "brand", "check", "--file", "03_wip/brand_v01.json")     # no --run: from the cwd only
    assert code == 1 and "03_wip/brand_v01.json" in _slashes(out["message"])
    _put(run, "03_wip/brand_v02.json", PROFILE)
    code, out = _cli(capsys, "brand", "save", "--run", r, "--file", "03_wip/brand_v02.json")
    assert code == 0, out
    assert out["file"] == "library/brands/night-school/brand_v01.json"
    answers = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    answers["brand"]["profile"] = out["file"]
    _put(run, "03_wip/intake_answers_v01.json", answers)
    code, out = _cli(capsys, "config", "write", "--run", r, "--answers", "03_wip/intake_answers_v01.json")
    assert code == 0, out
    assert (run.path / "config.yaml").is_file()


def test_the_runs_file_is_taken_first(ws, capsys):
    """Issue #90: a relative path is the run's whatever the working folder; one only in the working folder is still
    found there."""
    folder, run, r = ws
    (folder / "brand_draft.json").write_text(json.dumps({**PROFILE, "tone": ["one"]}), encoding="utf-8")
    _put(run, "brand_draft.json", PROFILE)
    code, out = _cli(capsys, "brand", "check", "--run", r, "--file", "brand_draft.json")
    assert code == 0, out                                                # the run's draft, not the workspace's
    (run.path / "brand_draft.json").unlink()
    code, out = _cli(capsys, "brand", "check", "--run", r, "--file", "brand_draft.json")
    assert code == 2 and "tone" in out["message"]                       # only the workspace has it


def test_voice_import_and_trends_ingest_from_the_workspace(ws, capsys):
    folder, run, r = ws
    _put(run, "00_raw/reviews.txt", "Loved it, slept well.\n\nToo long, but it worked.\n")
    code, out = _cli(capsys, "voice", "import", "--run", r, "--file", "00_raw/reviews.txt", "--format", "text",
                     "--source", "store", "--tier", "A")
    assert code == 0, out
    assert out["items_added"] == 2
    _put(run, "03_wip/ingest_input.json", {"about": "lucid dreaming"})
    _put(run, "03_wip/ingest_answer.json", {"data": [{"id": "t1", "kind": "hook_trend"}]})
    code, out = _cli(capsys, "trends", "ingest", "--run", r, "--tool", "search_trends",
                     "--input", "03_wip/ingest_input.json", "--file", "03_wip/ingest_answer.json")
    assert code == 0, out
    assert trends.answer_of(run.path / out["file"]) == {"data": [{"id": "t1", "kind": "hook_trend"}]}
    # a file that is in neither place is still said to be missing, by the name the agent gave
    code, out = _cli(capsys, "voice", "import", "--run", r, "--file", "00_raw/gone.txt", "--format", "text",
                     "--source", "store", "--tier", "A")
    assert code == 2 and "00_raw/gone.txt is not there" in _slashes(out["message"])
