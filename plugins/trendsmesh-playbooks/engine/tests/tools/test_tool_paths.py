"""Review Focus 1: paths with spaces and non-ASCII names reach the tools unchanged (argv lists only)."""

import json
import os
import subprocess

import pytest

from _media import make_clip


def test_path_with_spaces(run, tmp_path):
    """The real chain: pixi run -> python -m tm.tools.reframe, with a run folder, video and
    teardown under folders like C:\\Users\\Łukasz Nowak\\Desktop\\Moje reklamy\\."""
    pixi, env = os.environ.get("PIXI_EXE"), os.environ.get("PIXI_ENVIRONMENT_NAME")
    manifest = os.environ.get("PIXI_PROJECT_MANIFEST")
    if not (pixi and env and manifest):
        pytest.skip("not running under pixi")
    folder = tmp_path / "Łukasz Nowak" / "Desktop" / "Moje reklamy"
    video = make_clip(folder / "Reklama — zimowa 'v1' (9x16).mp4", vf="null", tone=False)
    td = folder / "teardown $HOME ;echo.json"
    td.write_text(json.dumps({"width": 540, "height": 960, "overlays": []}), encoding="utf-8")
    proc = subprocess.run(
        [pixi, "run", "--as-is", "--manifest-path", manifest, "-e", env,
         "python", "-m", "tm.tools.reframe", "--run", str(run.path), str(video),
         "--teardown", str(td), "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    out = run.path / result["outputs"][0]
    assert out.is_file() and out.parent.name == "03_wip"
    manifest_md = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "Reklama — zimowa 'v1' (9x16).mp4" in manifest_md  # the parent, named as it is


def test_teardown_frames_with_unicode_paths(tmp_path):
    pytest.importorskip("cv2")
    from tm.tools import teardown

    folder = tmp_path / "Moje reklamy" / "Łukasz Nowak"
    video = make_clip(folder / "zażółć gęślą jaźń.mp4", vf="null", tone=False, seconds=1.0)
    files = teardown.frames(video, folder / "klatki ąę", every_s=0.5)
    assert len(files) == 2 and all(p.is_file() for p, _ in files)
    assert teardown.scenes(video) == [(0.0, 1.0)]
