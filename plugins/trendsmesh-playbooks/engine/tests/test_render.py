"""tm render: the Remotion compositions. The real render needs Node and a browser (the `video`
mark, run with `pixi run -e dev-full test-video`); the rest runs in the light suite."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from tm import render
from tm.runfolder import RunFolder
from tm.tools import _common as common

sys.path.insert(0, str(Path(__file__).parent / "tools"))
from _media import W, H, ffmpeg, make_clip  # noqa: E402


def gray(png: Path) -> bytes:
    return subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(png), "-f", "rawvideo",
                           "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout


@pytest.fixture
def real(tmp_path_factory, monkeypatch):
    """A real Remotion setup in a throw-away data folder, run in this (dev-full) environment."""
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    cache = Path(__import__("os").environ.get("TM_TEST_REMOTION_CACHE") or tmp_path_factory.getbasetemp().parent / "tm-remotion-cache")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setattr(render.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(render, "_prefix", lambda: [])  # already inside an environment with Node
    monkeypatch.setattr(render.envtiers, "installed", lambda tier: True)
    render.setup()
    return cache


def _pixi() -> Path:
    exe = shutil.which("pixi") or str(Path.home() / ".pixi" / "bin" / "pixi")
    if not Path(exe).is_file():
        pytest.skip("pixi is not available")
    return Path(exe)


@pytest.mark.video
def test_real_pixi_wrapper_with_awkward_paths(tmp_path_factory, tmp_path, monkeypatch):
    """The real `pixi run --as-is -e video npx ...` path (no patched prefix), run folder with spaces
    and non-ASCII characters."""
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    plugin = Path(__file__).resolve().parents[2]
    pixi = _pixi()
    # pixi's default home and the environment next to env/pixi.toml, not a throw-away one
    subprocess.run([str(pixi), "install", "-e", "video", "--manifest-path", str(plugin / "env" / "pixi.toml")],
                   check=True, capture_output=True)
    cache = Path(os.environ.get("TM_TEST_REMOTION_CACHE") or tmp_path_factory.getbasetemp().parent / "tm-remotion-cache-wrapper")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(plugin))
    monkeypatch.setattr(render.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(render.paths, "pixi_bin", lambda: pixi)
    monkeypatch.setattr(render.paths, "pixi_env", lambda: {})
    assert render._prefix()[0] == str(pixi)
    render.setup()
    run = RunFolder.create(tmp_path / "Moje reklamy Łódź", "reklama żółta", date(2026, 11, 5))
    make_clip(run.path / "01_base" / "oryginał (1).mp4", vf="null", seconds=1.0)
    props = run.path / "03_wip" / "zażółć gęślą.props.json"
    props.write_text(json.dumps({"base": "01_base/oryginał (1).mp4", "width": W, "height": H,
                                 "durationSec": 1.0, "inserts": [], "cards": []}), encoding="utf-8")
    out = render.still(run, "HookSwap", props, 3, run.path / "03_wip" / "ramka Łódź_v01.png")
    assert out.is_file() and out.stat().st_size > 1000
    assert not list(out.parent.glob(".*.part.*"))


@pytest.mark.video
def test_ending_card_renders_in_last_second(real, tmp_path):
    run = RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "test ad", date(2026, 11, 5))
    make_clip(run.path / "01_base" / "reklama oryginał.mp4", vf="null", seconds=3.0)
    last = 89  # 3 s at Remotion's 30 fps
    card = {"from": 2.0, "to": 3.0, "top": 400, "height": 120, "fullBleed": True, "fontSize": 40,
            "typeCharsPerSec": 10000, "lines": [{"at": 2.0, "text": "KONIEC"}]}
    base = {"base": "01_base/reklama oryginał.mp4", "width": W, "height": H, "durationSec": 3.0, "inserts": []}
    props_ref = run.path / "03_wip" / "ref.props.json"
    props_end = run.path / "03_wip" / "end.props.json"
    props_ref.write_text(json.dumps({**base, "cards": []}), encoding="utf-8")
    props_end.write_text(json.dumps({**base, "cards": [card]}), encoding="utf-8")
    ref = render.still(run, "HookSwap", props_ref, last, run.path / "03_wip" / "ref.png")
    end = render.still(run, "HookSwap", props_end, last, run.path / "03_wip" / "end.png")
    a, b = gray(ref), gray(end)
    assert len(a) == len(b) == W * H
    band = slice(400 * W, 520 * W)
    changed = sum(x != y for x, y in zip(a[band], b[band]))
    assert changed > 0.5 * 120 * W  # the white card replaces the picture
    # Outside the card and its drop shadow the picture is the same (up to video decode noise).
    outside = list(zip(a[:360 * W], b[:360 * W])) + list(zip(a[560 * W:], b[560 * W:]))
    assert sum(abs(x - y) > 8 for x, y in outside) < 0.001 * len(outside)
    assert "end.png" in (run.path / "manifest.md").read_text(encoding="utf-8")


# Light tests: no Node, no browser ---------------------------------------------------------

@pytest.fixture
def light(tmp_path, monkeypatch):
    root = tmp_path / "plugin root Łukasz"
    (root / "remotion" / "src").mkdir(parents=True)
    (root / "remotion" / "package.json").write_text("{}")
    (root / "remotion" / "package-lock.json").write_text("{}")
    (root / "remotion" / "src" / "index.ts").write_text("//")
    (root / "env").mkdir()
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(render.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(render.paths, "pixi_env", lambda: {})
    run = RunFolder.create(tmp_path / "Moje reklamy", "ad", date(2026, 11, 5))
    (run.path / "01_base" / "a b.mp4").write_bytes(b"x")
    props = run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a b.mp4", "cards": []}))
    return run, props, root


def test_stops_when_video_tier_missing(light, monkeypatch, capsys):
    run, props, _ = light
    monkeypatch.setattr(render.envtiers, "installed", lambda t: False)
    code = render._run_cli(argparse_ns(run, props))
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and out["status"] == "stop" and "tm env install video --yes" in out["message"]


def test_stops_when_setup_missing_and_downloads_nothing(light, monkeypatch, capsys):
    run, props, _ = light
    monkeypatch.setattr(render.envtiers, "_env_installed", lambda env: True)   # the environment, no Remotion setup
    calls = []
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: calls.append(a))
    assert render._run_cli(argparse_ns(run, props)) == 2
    assert calls == [] and "set up" in json.loads(capsys.readouterr().out)["message"]


def test_stop_names_what_is_missing_from_the_one_video_check(light, monkeypatch, capsys):
    """#4: render asks `envtiers.installed("video")`, the check the doctor makes, and only then says which part is
    missing: the environment, or the Remotion setup for this lock file."""
    run, props, _ = light
    monkeypatch.setattr(render.envtiers, "_env_installed", lambda env: True)
    monkeypatch.setattr(render, "setup_done", lambda: False)
    assert render._run_cli(argparse_ns(run, props)) == 2
    assert "Remotion part is not set up" in json.loads(capsys.readouterr().out)["message"]
    monkeypatch.setattr(render.envtiers, "_env_installed", lambda env: False)
    assert render._run_cli(argparse_ns(run, props)) == 2
    assert "which are not installed yet" in json.loads(capsys.readouterr().out)["message"]


def test_setup_reruns_only_when_lock_changes(light, monkeypatch):
    _, _, root = light
    calls = []

    def fake(argv, **kw):
        calls.append(argv[len(render._prefix()):])
        shell = render.work_dir() / "node_modules" / ".remotion" / "chrome-headless-shell"
        shell.mkdir(parents=True, exist_ok=True)
        (shell / "VERSION").write_text("1")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    render.setup()
    assert [c[:2] for c in calls] == [[render._node_tool("npm"), "ci"], [render._node_tool("npx"), "remotion"]]
    assert render.setup_done()
    render.setup()
    assert len(calls) == 2  # reused
    (root / "remotion" / "package-lock.json").write_text('{"changed": 1}')
    assert not render.setup_done()
    render.setup()
    assert len(calls) == 4


def test_render_argv_is_a_list_with_public_dir_and_props(light, monkeypatch):
    run, props, _ = light
    monkeypatch.setattr(render.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(render, "setup_done", lambda: True)
    seen = []

    def fake(argv, **kw):
        seen.append((argv, kw))
        if "still" in argv:
            Path(argv[argv.index("still") + 3]).write_bytes(b"png")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    out = run.path / "03_wip" / "edit_v01.png"
    render.work_dir().mkdir(parents=True)
    render.still(run, "HookSwap", props, 7, out)
    argv = seen[-1][0]
    assert isinstance(argv, list) and argv[:3] == [str(render.paths.pixi_bin()), "run", "--as-is"]
    assert f"--public-dir={run.path.resolve()}" in argv and f"--props={props.resolve()}" in argv
    assert "--frame=7" in argv and seen[-1][1]["cwd"] == render.work_dir()
    row = (run.path / "manifest.md").read_text(encoding="utf-8").splitlines()[-1]
    assert "edit_v01.png" in row and "edit.props.json" in row
    with pytest.raises(common.ToolError):  # never overwritten
        render.still(run, "HookSwap", props, 7, out)


def test_missing_base_is_an_error_before_any_render(light, monkeypatch, capsys):
    run, props, _ = light
    props.write_text(json.dumps({"base": "01_base/nope.mp4"}))
    assert render._run_cli(argparse_ns(run, props)) == 1
    assert "nope.mp4" in json.loads(capsys.readouterr().out)["message"]


def argparse_ns(run, props):
    import argparse

    return argparse.Namespace(kind="still", run=str(run.path), comp="HookSwap", props=str(props),
                              out=None, json=True, frame=0)


def test_failed_render_leaves_no_file_and_retry_gets_same_version(light, monkeypatch):
    run, props, _ = light
    monkeypatch.setattr(render.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(render, "setup_done", lambda: True)
    render.work_dir().mkdir(parents=True)
    state = {"fail": True}

    def fake(argv, **kw):
        target = Path(next(a for a in argv if a.endswith((".mp4", ".png")) and "part" in a))
        target.write_bytes(b"half")
        if state["fail"]:
            return subprocess.CompletedProcess(argv, 1, "", "boom")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    out = run.next_version("wip", "edit", "mp4")
    with pytest.raises(common.ToolError):
        render.video(run, "HookSwap", props, out)
    assert not out.exists() and not list(out.parent.glob(".*part*"))
    assert "edit_v01.mp4" not in (run.path / "manifest.md").read_text(encoding="utf-8")
    assert run.next_version("wip", "edit", "mp4") == out  # a retry gets the same version
    state["fail"] = False
    render.video(run, "HookSwap", props, out)
    assert out.read_bytes() == b"half" and not list(out.parent.glob(".*part*"))


def test_windows_runs_cmd_shims_as_argv(light, monkeypatch):
    run, props, _ = light
    monkeypatch.setattr(render, "_is_windows", lambda: True)
    monkeypatch.setattr(render.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(render, "setup_done", lambda: True)
    render.work_dir().mkdir(parents=True)
    seen = []

    def fake(argv, **kw):
        seen.append(argv)
        for a in argv:
            if ".part" in a:
                Path(a).write_bytes(b"x")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    render.video(run, "HookSwap", props, run.path / "03_wip" / "edit_v01.mp4")
    argv = seen[-1]
    assert argv[argv.index("-e") + 2] == "npx.cmd" and isinstance(argv, list)
    assert render._node_tool("npm") == "npm.cmd"


def test_props_paths_must_stay_inside_the_run(light):
    run, props, _ = light
    for bad in ("../x.mp4", "/etc/hosts", "C:\\x.mp4", "01_base/../../x.mp4"):
        props.write_text(json.dumps({"base": bad}))
        with pytest.raises(common.ToolError, match="inside the run folder"):
            render._check_props(run, "HookSwap", props)


def test_render_accepts_outline_bar_and_inserts(light):
    run, props, _ = light
    (run.path / "02_assets").mkdir(exist_ok=True)
    (run.path / "02_assets" / "broll.mp4").write_bytes(b"x")
    card = {"from": 0, "to": 2, "top": 100, "style": "outlineBar", "barExt": 10, "barHeight": 60,
            "borderPx": 4, "lines": [{"at": 0, "text": "hi"}]}
    body = {"base": "01_base/a b.mp4", "cards": [card],
            "inserts": [{"src": "02_assets/broll.mp4", "from": 1, "to": 2}]}
    props.write_text(json.dumps(body))
    assert "outlineBar" in render.CARD_STYLES
    assert render._check_props(run, "HookSwap", props)["cards"][0]["style"] == "outlineBar"
    body["inserts"][0]["src"] = "../outside.mp4"  # an insert outside the run is refused as before
    props.write_text(json.dumps(body))
    with pytest.raises(common.ToolError, match="inside the run folder"):
        render._check_props(run, "HookSwap", props)


def test_render_rejects_unknown_card_style(light):
    run, props, _ = light
    props.write_text(json.dumps({"base": "01_base/a b.mp4", "cards": [
        {"from": 0, "to": 1, "top": 0, "style": "neon", "lines": []}]}))
    with pytest.raises(common.ToolError, match="box.*outlineBar"):
        render._check_props(run, "HookSwap", props)


def test_sync_src_skips_when_unchanged(light):
    _, _, root = light
    render.work_dir().mkdir(parents=True)
    render._sync_src()
    stamp = (render.work_dir() / "src" / "index.ts").stat().st_mtime_ns
    render._sync_src()
    assert (render.work_dir() / "src" / "index.ts").stat().st_mtime_ns == stamp
    (root / "remotion" / "src" / "index.ts").write_text("// new")
    render._sync_src()
    assert (render.work_dir() / "src" / "index.ts").read_text() == "// new"
