"""Issue #90, point 2: every `tm` command that takes `--run` finds a relative input path in the run folder first,
whatever the working folder (`RunFolder.given`, the one place; `_common.resolve`, `_common.inputs` and `cli.json_arg`
go through it). Each command is given a run-relative path from a working folder outside the run."""

import argparse
import json
from datetime import date

import pytest

from tm import changes, cli, library, r1, r2, r4, register, render, shortlist
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import _common as c
from tm.tools import elevenlabs, inpaint, inpaint_mode, music_index, reframe, speaker_sim, teardown, transcribe, vo_qa


@pytest.fixture
def run(tmp_path, monkeypatch):
    """A run, and a working folder elsewhere (the workspace's parent, as on the owner's Windows machine)."""
    run = RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    return run


def _file(run, rel, body="{}"):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# --- the one place ------------------------------------------------------------------------------------------------

def test_given_finds_a_relative_path_in_the_run_first(run, tmp_path):
    inside = _file(run, "03_wip/edit_v01.props.json")
    assert run.given("03_wip/edit_v01.props.json") == inside
    (tmp_path / "elsewhere" / "03_wip").mkdir()                   # the same name in the working folder too
    (tmp_path / "elsewhere" / "03_wip" / "edit_v01.props.json").write_text("{}", encoding="utf-8")
    assert run.given("03_wip/edit_v01.props.json") == inside
    only_here = tmp_path / "elsewhere" / "notes.json"            # a path from the working folder: as given
    only_here.write_text("{}", encoding="utf-8")
    assert run.given("notes.json").resolve() == only_here.resolve()
    assert run.given(str(only_here)) == only_here                 # an absolute path as it is
    assert run.given("03_wip/missing.json") == run.path / "03_wip/missing.json"   # where it was looked for


def test_the_helpers_go_through_it(run):
    _file(run, "03_wip/settings.json", '{"stability": 0.5}')
    assert cli.json_arg("03_wip/settings.json", run) == {"stability": 0.5}
    assert cli.json_arg('{"a": 1}', run) == {"a": 1}
    assert c.resolve(run, "03_wip/settings.json") == run.path / "03_wip/settings.json"
    a = argparse.Namespace(video="03_wip/settings.json", files=["03_wip/settings.json"], settings='{"x": 1}',
                           none=None)
    c.inputs(run, a, "video", "files", "settings", "none", "absent")
    assert a.video == str(run.path / "03_wip/settings.json") and a.files == [a.video]
    assert a.settings == '{"x": 1}' and a.none is None


# --- the issue's two commands -------------------------------------------------------------------------------------

def test_render_reads_a_run_relative_props_file(run, monkeypatch, capsys):
    props = _file(run, "03_wip/edit_v01.props.json", json.dumps({"segments": []}))
    seen = []

    def check(run_, comp, path):
        seen.append(path)
        raise c.ToolError("stop here")
    monkeypatch.setattr(render, "_check_props", check)
    code = main(["render", "video", "--run", str(run.path), "--comp", "OrganicCaptions", "--props",
                 "03_wip/edit_v01.props.json", "--json"])
    assert code == 1 and seen == [props.resolve()]
    assert "stop here" in capsys.readouterr().out


def test_transcribe_reads_a_run_relative_take(run, monkeypatch, capsys):
    take = _file(run, "03_wip/vo_take_v01.wav", "not decoded here")
    seen = []

    def heard(media, model, lang):
        seen.append(media)
        return {"language": "pl", "language_probability": 1.0, "duration": 1.0, "segments": []}
    monkeypatch.setattr(transcribe, "transcribe", heard)
    code = transcribe.main(["03_wip/vo_take_v01.wav", "--run", str(run.path), "--json"])
    assert code == 0 and seen == [str(take)], capsys.readouterr()


# --- every other command that read a path from the working folder -------------------------------------------------

TOOLS = [  # the tool, its arguments (the run's relative paths), the inputs it resolves
    (teardown, ["03_wip/v.mp4", "--transcript", "03_wip/t.json"], ("video", "transcript")),
    (reframe, ["03_wip/v.mp4", "--teardown", "03_wip/t.json"], ("video", "teardown")),
    (inpaint, ["03_wip/v.mp4", "--teardown", "03_wip/t.json"], ("video", "teardown")),
    (inpaint_mode, ["03_wip/m.png", "03_wip/c.png", "--crop", "0", "0", "9", "9"], ("mask", "composite")),
    (vo_qa, ["03_wip/a.wav", "03_wip/b.wav"], ("processed", "original")),
    (speaker_sim, ["03_wip/a.wav", "03_wip/b.wav"], ("files",)),
    (music_index, ["03_wip/music"], ("music_dir",)),
    (transcribe, ["03_wip/a.wav"], ("media",)),
    (elevenlabs, ["isolate", "03_wip/a.wav"], ("audio",)),
    (elevenlabs, ["clone-ivc", "--name", "v", "03_wip/a.wav"], ("files",)),
    (elevenlabs, ["music-upload", "03_wip/a.wav"], ("audio",)),
]


@pytest.mark.parametrize("tool, argv, names", TOOLS, ids=lambda x: getattr(x, "__name__", None))
def test_each_tool_resolves_its_inputs_in_the_run(run, monkeypatch, tool, argv, names):
    for rel in ("03_wip/v.mp4", "03_wip/t.json", "03_wip/m.png", "03_wip/c.png", "03_wip/a.wav", "03_wip/b.wav"):
        _file(run, rel)
    (run.path / "03_wip" / "music").mkdir()
    got = {}

    def inputs(run_, a, *asked):
        c.inputs.__wrapped__(run_, a, *asked)
        got.update({n: getattr(a, n, None) for n in asked})
        raise c.ToolError("resolved")
    inputs.__wrapped__ = c.inputs
    monkeypatch.setattr(c, "inputs", inputs)
    assert tool.main([*argv, "--run", str(run.path)]) == 1
    for name in names:
        value = got[name]
        for one in value if isinstance(value, list) else [value]:
            assert one.startswith(str(run.path)), (name, one)


def test_tm_record_reads_its_params_and_raw_answer_in_the_run(run, capsys):
    _file(run, "03_wip/x.txt", "x")
    _file(run, "03_wip/params.json", '{"seconds": 8}')
    _file(run, "03_wip/raw.json", '{"answer": 1}')
    code = main(["record", "--run", str(run.path), "--file", "03_wip/x.txt", "--stage", "03_wip", "--source", "a test",
                 "--params", "03_wip/params.json", "--raw-response-file", "03_wip/raw.json", "--json"])
    assert code == 0, capsys.readouterr()


def test_material_register_and_library_read_their_files_in_the_run(run, monkeypatch, capsys):
    _file(run, "03_wip/teardown_v01.json", '{"material": "x"}')
    seen = []
    monkeypatch.setattr(changes, "classify_material", lambda data: seen.append(data) or "ai")
    monkeypatch.setattr(changes, "record_material", lambda run_, material: None)
    assert main(["material", "--run", str(run.path), "--teardown", "03_wip/teardown_v01.json", "--json"]) == 0
    assert seen == [{"material": "x"}]
    _file(run, "03_wip/register_v01.json", '{"changes": []}')
    monkeypatch.setattr(register, "check", lambda run_, data: seen.append(data) or {"proof": 0, "guess": 0})
    assert register.record(run, "03_wip/register_v01.json")["file"] == "03_wip/register_v01.json"
    _file(run, "03_wip/row_v01.json", '{"variant": "a"}')
    monkeypatch.setattr(library, "add_to_run", lambda path, row: seen.append(row) or run.path)
    assert main(["library", "add", "--run", str(run.path), "--row", "03_wip/row_v01.json", "--json"]) == 0
    assert seen[-1] == {"variant": "a"}
    capsys.readouterr()


def test_the_ranking_and_diagnosis_read_their_answers_in_the_run(run, monkeypatch):
    _file(run, "01_base/peak.json", '{"spend": 1}')
    seen = []
    monkeypatch.setattr(r2, "window_from_json", lambda data: seen.append(data) or "window")
    assert r2._window_arg("01_base/peak.json", run) == "window" and seen == [{"spend": 1}]
    monkeypatch.setattr(r4, "window_from_json", lambda data: seen.append(data) or "window")
    a = argparse.Namespace(account=None, control="01_base/peak.json")
    assert r4._control(a, run) == "window"
    monkeypatch.setattr(r4, "account_window", lambda files: seen.append(files) or "account")
    assert r4._control(argparse.Namespace(account=["01_base/peak.json"], control=None), run) == "account"
    assert seen[-1] == [str(run.path / "01_base/peak.json")]
    read = []
    monkeypatch.setattr(r1, "_read", lambda files, what: (read.append(files), (_ for _ in ()).throw(ValueError("x"))))
    main(["r1", "--run", str(run.path), "--ads", "01_base/peak.json", "--account", "01_base/peak.json"])
    assert read and read[0] == [str(run.path / "01_base/peak.json")]


def test_the_shortlist_globs_in_the_run(run):
    found = _file(run, "02_research/trends_v01.json")
    assert shortlist.input_files(run, ["02_research/trends_*.json"]) == [found]
    assert shortlist.input_files(run, ["02_research/trends_v01.json"]) == [found]
