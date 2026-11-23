"""Issue #126: one path rule for run files (`RunFolder.given`), the workspace found from the run or from any folder
inside it (`paths.workspace`), JSON written with a BOM read everywhere (`cli.read_json`), and `--json` on every
command."""

import argparse
import ast
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tm import brand, cli, envtiers, paths, stepchecks
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import NotInRun, RunFolder
from tm.tools import _common as c
from tm.tools import replicate_run, site

ENGINE = Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks" / "engine" / "src" / "tm"


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace with one run; HOME is elsewhere and TM_WORKSPACE is not set."""
    monkeypatch.delenv("TM_WORKSPACE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    return tmp_path / "ws"


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "x", date(2026, 11, 12), playbook=ORGANIC_VIDEO)


def _file(run, rel, body="{}"):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _rel_run(run):
    return Path("runs") / run.path.parent.name / run.path.name


# --- 1. the run path is absolute, and given() is the one rule -----------------------------------------------------

def test_open_keeps_the_run_path_absolute(run, ws, monkeypatch):
    monkeypatch.chdir(ws)
    opened = RunFolder.open(_rel_run(run))
    assert opened.path.is_absolute() and opened.path == run.path.resolve()
    assert RunFolder(Path(".")).path.is_absolute()


def test_given_reads_a_relative_path_inside_the_run(run, ws, monkeypatch):
    inside = _file(run, "03_wip/edit_v01.props.json")
    for here in (ws, run.path, run.path / "03_wip", ws.parent):
        monkeypatch.chdir(here)
        opened = RunFolder.open(run.path)
        assert opened.given("03_wip/edit_v01.props.json") == inside
        assert opened.given(_rel_run(run) / "03_wip" / "edit_v01.props.json") == inside   # written from the workspace
        assert opened.given(str(inside)) == inside                                         # absolute: as it is


def test_given_refuses_a_missing_file_and_a_relative_path_outside_the_run(run, ws, monkeypatch):
    monkeypatch.chdir(ws)
    (ws / "notes.json").write_text("{}", encoding="utf-8")
    with pytest.raises(NotInRun, match=r"03_wip/missing.json is not in the run folder .*relative to the run folder"):
        run.given("03_wip/missing.json")
    with pytest.raises(ValueError, match="absolute path"):
        run.given("notes.json")                       # found from the working folder only: give it as absolute
    with pytest.raises(FileNotFoundError, match="absolute path"):
        run.given("../../../notes.json")               # outside the run
    assert run.given(str(ws / "notes.json")) == ws / "notes.json"
    assert run.given("03_wip/missing.json", missing_ok=True) == run.path / "03_wip" / "missing.json"


def test_mark_takes_the_same_path_from_the_workspace_and_from_the_run(run, ws, monkeypatch):
    _file(run, "03_wip/concepts_v01.json")
    for here in (ws, run.path):
        monkeypatch.chdir(here)
        rel_run = RunFolder.open(_rel_run(run) if here == ws else Path("."))
        stepchecks.mark(rel_run, "concepts", "03_wip/concepts_v01.json")
        assert stepchecks.state.load(rel_run).checked["concepts"]["file"] == "03_wip/concepts_v01.json"
    with pytest.raises(ValueError, match="is not in the run folder"):
        stepchecks.mark(run, "concepts", "03_wip/concepts_v09.json")


def test_site_logos_land_in_the_run_brand_folder_once(run, ws, monkeypatch):
    monkeypatch.chdir(ws)
    rel = RunFolder.open(_rel_run(run))
    monkeypatch.setattr(site, "logo_candidates", lambda *a: [{"svg": "<svg></svg>", "kind": "svg_logo",
                                                              "names_brand": True}])
    monkeypatch.setattr(site, "_png", lambda src, dest: False)
    out, _ = site.logos(rel, None, "", "https://example.com")
    assert out[0]["file"] == f"{site.BRAND_DIR}/svg_logo_01.svg"
    assert (run.path / site.BRAND_DIR / "svg_logo_01.svg").is_file()
    assert not (run.path / "runs").exists()


def test_a_spec_naming_a_missing_local_file_stops_before_any_call(run, ws, monkeypatch):
    monkeypatch.chdir(ws)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr(replicate_run, "_client", lambda: pytest.fail("a paid call was started"))
    spec = _file(run, "03_wip/still.spec.json", json.dumps(
        {"model": "owner/model", "input": {"prompt": "A dog on a sofa, 9:16.", "image": "03_wip/frame_v01.png"}}))
    assert replicate_run.main(["--run", str(_rel_run(run)), "03_wip/still.spec.json", "--json"]) == 1
    assert not list((run.path / "03_wip").glob("still*.run.json"))
    frame = _file(run, "03_wip/frame_v01.png", "png")
    assert c.local_file("03_wip/frame_v01.png", spec.parent, run) == frame       # run-relative first
    assert c.local_file("frame_v01.png", spec.parent, run) == frame              # else beside the spec
    assert c.local_file("A dog on a sofa, 9:16.", spec.parent, run) is None
    assert c.looks_local("03_wip/frame_v02.png") and not c.looks_local("make it 1.5 times faster")


# --- 2. the workspace, from the run or from any folder inside it --------------------------------------------------

def test_workspace_walks_up_to_the_runs_folder_or_the_marker(run, ws, monkeypatch, tmp_path):
    for here in (ws, run.path, run.path / "03_wip"):
        monkeypatch.chdir(here)
        assert paths.workspace() == ws
    other = tmp_path / "other" / "deep"
    other.mkdir(parents=True)
    (tmp_path / "other" / "library").mkdir()           # a bare library/ is not a workspace
    monkeypatch.chdir(other)
    assert paths.workspace() == other
    (tmp_path / "other" / ".trendsmesh").mkdir()
    assert paths.workspace() == tmp_path / "other"
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "set"))
    assert paths.workspace() == tmp_path / "set"


def test_the_home_folder_marker_is_not_a_workspace(tmp_path, monkeypatch):
    monkeypatch.delenv("TM_WORKSPACE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trendsmesh").mkdir()                 # ~/.trendsmesh/paths.json
    (tmp_path / "projects" / "a").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "projects" / "a")
    assert paths.workspace() == tmp_path / "projects" / "a"


def test_a_command_with_run_takes_the_workspace_from_the_run(run, ws, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setitem(cli._COMMANDS, "probe", (lambda p: p.add_argument("--run"),
                                                 lambda a: seen.append(paths.workspace()) or 0))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path / "elsewhere"))
    assert main(["probe", "--run", str(run.path)]) == 0
    assert seen == [ws] and paths.workspace() == tmp_path / "elsewhere"   # only for that command


def test_brand_show_finds_the_profile_from_inside_a_run(run, ws, monkeypatch, capsys):
    from test_brand import _profile
    brand.save(ws, _profile(), run=None)
    monkeypatch.chdir(run.path / "03_wip")
    assert main(["brand", "show", "--name", "Night School", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["profile"]["brand"] == "Night School"
    assert main(["brand", "show", "--name", "Nobody", "--json"]) == 1
    assert str(ws / "library" / "brands") in json.loads(capsys.readouterr().out)["message"]


# --- 3. JSON and YAML with a BOM -------------------------------------------------------------------------------

def test_read_json_takes_a_bom(tmp_path):
    path = tmp_path / "fit.json"
    path.write_bytes("﻿".encode("utf-8") + b'{"a": 1}')
    assert cli.read_json(path) == {"a": 1}
    assert cli.json_arg(str(path)) == {"a": 1}


def _plain_utf8_read(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "read_text"
            and any(isinstance(a, ast.Constant) and a.value == "utf-8" for a in node.args)
            or isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "read_text"
            and any(k.arg == "encoding" and isinstance(k.value, ast.Constant) and k.value.value == "utf-8"
                    for k in node.keywords))


def _parser_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
    owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
    return (owner, name) in {("json", "loads"), ("yaml", "safe_load"), ("yaml", "safe_load_all"), ("yaml", "load")}


def test_no_json_or_yaml_is_read_without_the_bom_rule():
    """`read_text(encoding="utf-8")` is never fed to json.loads or yaml.safe_load, directly or through a name set
    from it in the same function: a file written by Windows PowerShell 5.1 starts with a BOM."""
    found = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in [tree, *(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                         ast.Lambda)))]:
            plain = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign) and _plain_utf8_read(n.value)
                     for t in n.targets if isinstance(t, ast.Name)}
            for n in ast.walk(fn):
                if _parser_call(n) and n.args and (any(_plain_utf8_read(x) for x in ast.walk(n.args[0]))
                                                   or isinstance(n.args[0], ast.Name) and n.args[0].id in plain):
                    found.append(f"{path.relative_to(ENGINE).as_posix()}:{n.lineno}")
    assert sorted(set(found)) == []


# --- 4. --json everywhere -------------------------------------------------------------------------------------

NO_JSON = {
    ("tool",): "passes its arguments to the tool, and every tool takes --json itself",
    ("trends", "spool"): "the PostToolUse hook's command, read by Claude Code, never by Claude",
}


def _leaves(parser, path=()):
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subs:
        yield path, parser
    for a in subs:
        for name, sp in a.choices.items():
            yield from _leaves(sp, (*path, name))


def test_every_command_takes_json():
    missing = [" ".join(path) for path, p in _leaves(cli.build_parser())
               if path not in NO_JSON and not any("--json" in a.option_strings for a in p._actions)]
    assert missing == []


NOT_A_PATH = {("organic", "atlas-prompt", "--style"),   # a style's number or styleId
              ("brief", "animatic", "--style")}         # auto, or a style's number or styleId (issue #138 item 4)


def test_every_run_file_argument_says_where_it_is_read():
    vague = []
    for path, p in _leaves(cli.build_parser()):
        if not any("--run" in a.option_strings for a in p._actions):
            continue
        for a in p._actions:
            name = a.option_strings[0] if a.option_strings else a.dest
            if name in ("--file", "--style", "--props", "--spec", "spec") and (*path[:2], name) not in NOT_A_PATH \
                    and "run folder" not in (a.help or "") and "run-relative" not in (a.help or ""):
                vague.append(f"{' '.join(path)} {name}")
    assert vague == []


def test_env_install_json_prints_one_object(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(envtiers, "clean", lambda: envtiers.Cleaned())
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # pixi's log (#161): never the real data folder
    monkeypatch.setattr(envtiers, "_pixi_env", lambda: {})
    monkeypatch.setattr(envtiers.paths, "pixi_bin", lambda: Path("pixi"))
    monkeypatch.setattr(envtiers, "_manifest", lambda: Path("pixi.toml"))

    def pixi(cmd, env=None, **kw):
        print("pixi talks on its stdout")
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(envtiers.subprocess, "run", pixi)
    from tm import render
    monkeypatch.setattr(render, "setup", lambda force=False: print("npm talks too"))
    monkeypatch.setattr(render, "setup_done", lambda: True)
    monkeypatch.setattr(render, "probe", lambda: print("remotion talks too"))
    assert main(["env", "install", "video", "--yes", "--json"]) == 0
    out = capsys.readouterr()
    got = json.loads(out.out)
    assert got["status"] == "done" and got["tier"] == "video" and got["message"]
    assert "pixi talks" in out.err and "npm talks" in out.err
    assert main(["env", "install", "video", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"
    monkeypatch.setattr(envtiers.subprocess, "run", lambda cmd, env=None, **kw: subprocess.CompletedProcess(cmd, 1))
    assert main(["env", "install", "video", "--yes", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
