"""tm atlas: the animatic renderer (the second node package), its `animatic` tier and the doctor's
browser row. The real render needs Node and a browser and runs only when the `video` mark is asked
for (`pixi run -e dev-full test-video`); the rest runs in the light suite."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import pytest

import ld
from conftest import video_asked_for
from tm import atlas, doctor, envtiers, render
from tm.tools import _common as common

PLUGIN = Path(__file__).resolve().parents[2]
ANIMATIC_GEN = ld.LD / "03_wip" / "animatic_gen"
Usage = namedtuple("Usage", "total used free")
CB = "02-creative-brief"
ALL = {"review_pack", "briefs", "animatics", "page"}
CB_MCP = {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}


@pytest.fixture
def light(tmp_path, monkeypatch):
    """A plugin root with an atlas package, a data folder, and a pixi that is never run."""
    root = tmp_path / "plugin root Łukasz"
    (root / "atlas").mkdir(parents=True)
    for name in ("package.json", "package-lock.json"):
        (root / "atlas" / name).write_text("{}", encoding="utf-8")
    (root / "atlas" / "render.mjs").write_text("// render", encoding="utf-8")
    (root / "env").mkdir()
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(render.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(render.paths, "pixi_env", lambda: {})
    return root


def _on(monkeypatch, system: str) -> None:
    """Look at the browser places of `system`, through the os.name and sys.platform atlas reads."""
    name, platform = {"windows": ("nt", "win32"), "macos": ("posix", "darwin"), "linux": ("posix", "linux")}[system]
    monkeypatch.setattr(atlas, "os", SimpleNamespace(name=name, environ=os.environ))
    monkeypatch.setattr(atlas, "sys", SimpleNamespace(platform=platform))


# --- the browser ---------------------------------------------------------------------------------

def test_find_browser_per_os(tmp_path, monkeypatch):
    monkeypatch.setattr(atlas.remotion, "setup_done", lambda: False)
    present: set[Path] = set()
    monkeypatch.setattr(atlas, "_exists", lambda p: p in present)
    which: dict[str, str] = {}
    monkeypatch.setattr(atlas.shutil, "which", lambda name: which.get(name))

    # Windows: Edge alone, under Program Files (x86); the 64-bit folder and the user's folder are empty.
    pf, pf86, local = tmp_path / "Program Files", tmp_path / "Program Files (x86)", tmp_path / "Local"
    monkeypatch.setenv("ProgramFiles", str(pf))
    monkeypatch.setenv("ProgramFiles(x86)", str(pf86))
    monkeypatch.setenv("LocalAppData", str(local))
    _on(monkeypatch, "windows")
    assert atlas.find_browser() is None
    edge = pf86 / "Microsoft/Edge/Application/msedge.exe"
    present.add(edge)
    assert atlas.find_browser() == edge
    chrome = local / "Google/Chrome/Application/chrome.exe"
    present.add(chrome)
    assert atlas.find_browser() == chrome   # Chrome before Edge, the user's own install included
    present.clear()

    # macOS: Chrome in the user's own Applications folder, not in /Applications.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _on(monkeypatch, "macos")
    assert atlas.find_browser() is None
    mine = Path.home() / "Applications" / "Google Chrome.app/Contents/MacOS/Google Chrome"
    present.add(mine)
    assert atlas.find_browser() == mine
    everyone = Path("/Applications") / "Chromium.app/Contents/MacOS/Chromium"
    present.add(everyone)
    assert atlas.find_browser() == everyone   # /Applications first
    present.clear()

    # Linux: chromium on PATH.
    _on(monkeypatch, "linux")
    assert atlas.find_browser() is None
    which["chromium"] = "/usr/bin/chromium"
    present.add(Path("/usr/bin/chromium"))
    assert atlas.find_browser() == Path("/usr/bin/chromium")
    which["google-chrome-stable"] = "/opt/google/chrome/google-chrome"
    present.add(Path("/opt/google/chrome/google-chrome"))
    assert atlas.find_browser() == Path("/opt/google/chrome/google-chrome")


def test_headless_shell_only_after_remotion_setup(light, monkeypatch):
    _on(monkeypatch, "linux")
    monkeypatch.setattr(atlas.shutil, "which", lambda name: None)
    shell = (render.work_dir() / "node_modules" / ".remotion" / "chrome-headless-shell" / "linux64"
             / "chrome-headless-shell-linux64" / "chrome-headless-shell")
    shell.parent.mkdir(parents=True)
    shell.write_bytes(b"")
    monkeypatch.setattr(atlas.remotion, "setup_done", lambda: False)
    assert atlas.find_browser() is None
    monkeypatch.setattr(atlas.remotion, "setup_done", lambda: True)
    assert atlas.find_browser() == shell
    monkeypatch.setattr(atlas.shutil, "which", lambda name: "/usr/bin/chromium" if name == "chromium" else None)
    monkeypatch.setattr(atlas, "_exists", lambda p: True)
    assert atlas.find_browser() == Path("/usr/bin/chromium")   # the user's browser comes first


# --- setup and render ----------------------------------------------------------------------------

def _page(tmp_path: Path) -> Path:
    page = tmp_path / "anim" / "C1_9x16_v03.html"
    page.parent.mkdir()
    page.write_text("<html></html>", encoding="utf-8")
    return page


class FakePopen:
    """subprocess.Popen for render.mjs: `act(argv, kw)` writes files and returns (code, stdout, stderr)."""
    calls: list = []
    act = None

    def __init__(self, argv, **kw):
        FakePopen.calls.append((argv, kw))
        self.argv, self.pid = argv, 4242
        self.returncode, self._out, self._err = FakePopen.act(argv, kw)

    def communicate(self, timeout=None):
        return self._out, self._err


@pytest.fixture
def popen(monkeypatch):
    FakePopen.calls = []
    FakePopen.act = lambda argv, kw: pytest.fail("render.mjs ran")
    monkeypatch.setattr(atlas.subprocess, "Popen", FakePopen)
    return FakePopen


@pytest.fixture
def ready(light, monkeypatch):
    """The tier set up, Chrome found, ffmpeg known, macOS, not root."""
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path("/Apps/Google Chrome"))
    monkeypatch.setattr(atlas.c, "ffmpeg_bin", lambda: "/env/ffmpeg")
    monkeypatch.setattr(atlas, "_system", lambda: "macos")
    monkeypatch.setattr(atlas, "_is_root", lambda: False)
    return light


@pytest.mark.parametrize("tier,browser,says", [
    (False, Path("chrome"), "tm env install animatic --yes"),
    (True, None, "Google Chrome or Microsoft Edge"),
])
def test_render_stops_without_browser_and_runs_nothing(light, popen, tmp_path, monkeypatch, tier, browser, says):
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: tier and t == "animatic")
    monkeypatch.setattr(atlas, "find_browser", lambda: browser)
    page = _page(tmp_path)
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"
    with pytest.raises(common.ToolStop) as stop:
        atlas.render(page, out)
    text = str(stop.value)
    assert says in text and "Nothing was rendered." in text and text.endswith(
        "The run continues from the same place.")
    assert popen.calls == [] and not out.exists() and not atlas.work_dir().exists()


def test_setup_reruns_only_when_lock_changes(light, monkeypatch):
    calls = []

    def fake(argv, **kw):
        calls.append(argv[len(render._prefix()):])
        package = atlas.work_dir() / "node_modules" / "puppeteer-core"
        package.mkdir(parents=True, exist_ok=True)
        (package / "package.json").write_text("{}")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    assert not atlas.setup_done()
    atlas.setup()
    assert calls == [[render._node_tool("npm"), "ci"]]   # no browser download
    assert atlas.setup_done() and atlas.work_dir() == render.paths.data_dir() / "atlas"
    assert (atlas.work_dir() / "package-lock.json").read_text() == "{}"
    atlas.setup()
    assert len(calls) == 1  # reused
    (light / "atlas" / "package-lock.json").write_text('{"changed": 1}')
    assert not atlas.setup_done()
    atlas.setup()
    assert len(calls) == 2


def _writes(out: Path, code: int = 0, stdout: str = "", stderr: str = "", stills: bool = True):
    """What render.mjs leaves: its in-between files, the MP4 and the five stills."""
    def act(argv, kw):
        Path(f"{out}.video.mp4").write_bytes(b"v")
        Path(f"{out}.wav").write_bytes(b"w")
        out.write_bytes(b"mp4")
        for still in atlas.still_paths(out) if stills else []:
            still.write_bytes(b"png")
        return code, stdout, stderr
    return act


def test_render_runs_render_mjs_with_the_browser_and_ffmpeg_as_argv(ready, popen, tmp_path):
    """One argv list in the video environment, in a process group of its own; the last JSON line
    is the answer; render.mjs's in-between files never stay."""
    page = _page(tmp_path)
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"
    answer = {"out": str(out), "duration": 15, "frames": 360, "size": [1080, 1920], "page_errors": []}
    popen.act = _writes(out, stdout="puppeteer says hi\n" + json.dumps(answer) + "\n")
    assert atlas.render(page, out) == answer
    argv, kw = popen.calls[0]
    assert isinstance(argv, list) and "shell" not in kw and kw["cwd"] == atlas.work_dir()
    assert kw.get("start_new_session") or kw.get("creationflags")
    assert argv[:len(render._prefix())] == render._prefix() and "-e" in argv and "video" in argv
    assert argv[len(render._prefix()):] == [
        "node", str(atlas.work_dir() / "render.mjs"), str(page.resolve()), str(out.resolve()),
        "--browser", str(Path("/Apps/Google Chrome")), "--ffmpeg", "/env/ffmpeg",
        "--fps", "24", "--stills", "0.06,0.3,0.55,0.8,0.95"]
    assert (atlas.work_dir() / "render.mjs").read_text() == "// render"
    assert not Path(f"{out}.video.mp4").exists() and not Path(f"{out}.wav").exists()
    assert out.exists() and all(p.exists() for p in atlas.still_paths(out))
    assert [p.name for p in atlas.still_paths(out)] == [f"C1_9x16_v01_still_{n}.png"
                                                        for n in ("006", "030", "055", "080", "095")]
    assert atlas.still_paths(out, (0.125, 0.5))[0].name == "C1_9x16_v01_still_013.png"   # JS Math.round


def test_render_never_overwrites_and_a_failed_one_leaves_nothing(ready, popen, tmp_path):
    page = _page(tmp_path)
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"
    out.write_bytes(b"old")
    with pytest.raises(common.ToolError, match="C1_9x16_v01.mp4 already exist"):
        atlas.render(page, out)
    out.unlink()
    orphan = atlas.still_paths(out)[2]
    orphan.write_bytes(b"old still")
    with pytest.raises(common.ToolError, match="C1_9x16_v01_still_055.png already exist"):
        atlas.render(page, out)
    assert orphan.read_bytes() == b"old still" and popen.calls == []
    orphan.unlink()

    popen.act = _writes(out, 1, stderr="Error: ffmpeg video exit 1\n    at render.mjs:52")
    with pytest.raises(common.ToolError, match="ffmpeg video exit 1"):
        atlas.render(page, out)
    assert sorted(p.name for p in out.parent.iterdir()) == [page.name]   # no MP4, no stills, no parts


@pytest.mark.parametrize("system,root,browser,flag", [
    ("linux", False, "/usr/bin/google-chrome", False),
    ("linux", True, "/usr/bin/google-chrome", True),
    ("linux", False, "/data/remotion/node_modules/.remotion/chrome-headless-shell/linux64/"
                     "chrome-headless-shell-linux64/chrome-headless-shell", True),
    ("macos", True, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", False),
    ("macos", False, "/data/chrome-headless-shell-mac-arm64/chrome-headless-shell", False),
    ("windows", False, "C:/x/chrome-headless-shell-win64/chrome-headless-shell.exe", False),
])
def test_no_sandbox_only_on_linux_as_root_or_with_the_headless_shell(ready, popen, tmp_path, monkeypatch,
                                                                      system, root, browser, flag):
    monkeypatch.setattr(atlas, "_system", lambda: system)
    monkeypatch.setattr(atlas, "_is_root", lambda: root)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path(browser))
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"
    page = _page(tmp_path)
    popen.act = _writes(out, stdout=json.dumps({"out": str(out)}))
    atlas.render(page, out)
    assert ("--no-sandbox" in popen.calls[0][0]) is flag
    assert (popen.calls[0][0][-1] == "--no-sandbox") is flag


@pytest.mark.parametrize("said", [
    "[1107/101010.1:FATAL:zygote_host_impl_linux.cc(127)] No usable sandbox! Update your kernel ...",
    "Running as root without --no-sandbox is not supported. See https://crbug.com/638180.",
])
def test_a_sandbox_refusal_is_a_stop_with_what_to_install(ready, popen, tmp_path, said):
    page = _page(tmp_path)
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"
    popen.act = _writes(out, 1, stderr="Error: Failed to launch the browser process!\n" + said + "\n")
    with pytest.raises(common.ToolStop) as stop:
        atlas.render(page, out)
    text = str(stop.value)
    assert "sandbox" in text and "Nothing was rendered." in text and "Google Chrome" in text
    assert "not as root" in text and text.endswith("The run continues from the same place.")
    assert sorted(p.name for p in out.parent.iterdir()) == [page.name]


def test_a_hung_render_is_stopped_with_all_it_started(ready, tmp_path, monkeypatch):
    """A real process tree: the child starts a grandchild, and both are gone when the time is up."""
    monkeypatch.setattr(atlas, "TIMEOUT_S", 1)
    monkeypatch.setattr(atlas, "GRACE_S", 2)
    atlas.work_dir().mkdir(parents=True)
    pid_file = tmp_path / "grandchild.pid"
    child = ("import subprocess, sys, time\n"
             "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
             f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
             "time.sleep(60)\n")
    started = time.monotonic()
    with pytest.raises(common.ToolError, match="did not finish"):
        atlas._run([sys.executable, "-c", child], "C1_9x16_v03.html")
    assert time.monotonic() - started < 30
    grandchild = int(pid_file.read_text())
    if os.name != "nt":
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _alive(grandchild):
            time.sleep(0.1)
        assert not _alive(grandchild)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:   # a zombie of ours is dead too
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return True


def test_a_failed_or_hung_render_leaves_nothing(ready, popen, tmp_path, monkeypatch):
    page = _page(tmp_path)
    out = tmp_path / "anim" / "C1_9x16_v01.mp4"

    def hang(argv, kw):
        _writes(out)(argv, kw)
        raise common.ToolError("The animatic renderer did not finish C1 in 15 minutes and was stopped.")

    monkeypatch.setattr(atlas, "_run", lambda argv, name: hang(argv, {}))
    with pytest.raises(common.ToolError, match="did not finish"):
        atlas.render(page, out)
    assert sorted(p.name for p in out.parent.iterdir()) == [page.name]


def test_snap_chromium_is_not_used(tmp_path, monkeypatch):
    """Ubuntu's chromium is a snap (and chromium-browser a script that starts it): its own /tmp and
    its confinement keep it from puppeteer's profile and from hidden folders."""
    _on(monkeypatch, "linux")
    monkeypatch.setattr(atlas.remotion, "setup_done", lambda: False)
    script = tmp_path / "chromium-browser"
    script.write_text("#!/bin/sh\nexec /snap/bin/chromium \"$@\"\n")
    which = {"chromium": "/snap/bin/chromium", "chromium-browser": str(script)}
    monkeypatch.setattr(atlas.shutil, "which", lambda name: which.get(name))
    monkeypatch.setattr(atlas, "_exists", lambda p: True)
    assert atlas.find_browser() is None
    real = tmp_path / "microsoft-edge"
    real.write_bytes(b"\x7fELF")
    which["microsoft-edge"] = str(real)
    assert atlas.find_browser() == real


@pytest.mark.private_data
def test_render_mjs_is_the_originals_but_for_the_browser_ffmpeg_and_sandbox_options():
    theirs = (ld.REPO / "handoff" / "creative-brief_v02" / "tools" / "atlas_render" / "render.mjs").read_text(
        encoding="utf-8").replace("\r", "").splitlines()
    ours = (PLUGIN / "atlas" / "render.mjs").read_text(encoding="utf-8").splitlines()
    changed = [line for line in difflib.unified_diff(theirs, ours, lineterm="", n=0)
               if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    allowed = ("// Render an", "--browser", "--ffmpeg", "FFMPEG", "NO_SANDBOX", "BROWSERS", "existsSync);", "Program Files",
               "];", "// Usage:", "// Needs ffmpeg", "// Linux only", 'spawn("ffmpeg"', "usage: node render.mjs",
               "puppeteer.launch({ executablePath, headless: true")
    assert changed and all(any(a in line for a in allowed) for line in changed), changed


# --- the tier and the doctor ---------------------------------------------------------------------

@pytest.fixture
def world(tmp_path, monkeypatch, bundled_skills):
    """Everything installed, plenty of disk, a browser, macOS."""
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: True)
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(500 * 1024**3, 0, 400 * 1024**3))
    monkeypatch.setattr(doctor, "_os_key", lambda: "macos")
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: Path("chrome"))


def _item(r, id_):
    return next((i for i in r.items if i.id == id_), None)


@pytest.mark.parametrize("system,says", [
    ("windows", "Install Microsoft Edge or Google Chrome (both free), then say continue. I draw the animatics "
                "in it, on your computer."),
    ("macos", "Install Google Chrome (free), then say continue. I draw the animatics in it, on your computer."),
    ("linux", "Install Google Chrome (free), then say continue. I draw the animatics in it, on your computer."),
])
def test_doctor_browser_row_only_for_animatics(world, monkeypatch, system, says):
    assert _item(doctor.check(ALL, False, CB_MCP, playbook=CB), "browser_for_animatics").ok
    assert _item(doctor.check({"review_pack", "page"}, False, CB_MCP, playbook=CB), "browser_for_animatics") is None
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: None)
    monkeypatch.setattr(doctor, "_os_key", lambda: system)
    r = doctor.check(ALL, False, CB_MCP, playbook=CB)
    it = _item(r, "browser_for_animatics")
    assert not r.ready and not it.ok and it.fixer == "user" and it.fix == says and not it.warn
    assert doctor.check({"review_pack", "page"}, False, CB_MCP, playbook=CB).ready
    # refresh-ad never asks for it
    assert _item(doctor.check({"creative_brief", "edited_video"}, False, {"trendsmesh": "ok", "meta": "ok"}),
                 "browser_for_animatics") is None


def test_doctor_linux_headless_shell_needs_chromes_libraries(world, monkeypatch):
    """The headless shell brings none of the libraries a Chrome package installs, so on Linux it
    counts only when they are there; elsewhere, and for Chrome itself, it is never looked at."""
    shell = Path("/data/remotion/node_modules/.remotion/chrome-headless-shell/linux64/"
                 "chrome-headless-shell-linux64/chrome-headless-shell")
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: shell)
    monkeypatch.setattr(doctor, "_missing_libs", lambda: ["libnss3"])
    monkeypatch.setattr(doctor, "_os_key", lambda: "linux")
    assert not _item(doctor.check(ALL, False, CB_MCP, playbook=CB), "browser_for_animatics").ok
    monkeypatch.setattr(doctor, "_os_key", lambda: "macos")
    assert _item(doctor.check(ALL, False, CB_MCP, playbook=CB), "browser_for_animatics").ok
    monkeypatch.setattr(doctor, "_os_key", lambda: "linux")
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: Path("/usr/bin/google-chrome"))
    assert _item(doctor.check(ALL, False, CB_MCP, playbook=CB), "browser_for_animatics").ok
    monkeypatch.setattr(doctor.atlas, "find_browser", lambda: shell)
    monkeypatch.setattr(doctor, "_missing_libs", lambda: [])
    assert _item(doctor.check(ALL, False, CB_MCP, playbook=CB), "browser_for_animatics").ok


def test_review_pack_run_needs_no_animatic_tier(world, monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: False)
    # base 500 + 2048 = 2548 MB for the review pack; base + animatic 150 + 2048 = 2698 MB for everything
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(0, 0, 2600 * 1024**2))
    pack = doctor.check({"review_pack", "page"}, False, CB_MCP, playbook=CB)
    assert _item(pack, "tier_animatic") is None and _item(pack, "tier_base") is not None
    assert _item(pack, "disk_free").ok
    full = doctor.check(ALL, False, CB_MCP, playbook=CB)
    tier = _item(full, "tier_animatic")
    assert not tier.ok and tier.fixer == "agent" and tier.size_mb == 150
    assert tier.fix == "I install the animatic tools (about 150 MB, about 1 min). Say yes and I start."
    disk = _item(full, "disk_free")
    assert not disk.ok and doctor._gb(500 + 150 + 2048) in disk.fix


def test_trend_research_tiers_unchanged(world, monkeypatch):
    monkeypatch.setattr(doctor.envtiers, "installed", lambda tier: False)
    monkeypatch.setattr(doctor.shutil, "disk_usage", lambda p: Usage(0, 0, 2600 * 1024**2))
    r = doctor.check({"category_report", "weekly_digest", "paid_view"}, False, CB_MCP, playbook="04-trend-research")
    assert [i.id for i in r.items if i.id.startswith("tier_")] == ["tier_base"]
    assert _item(r, "disk_free").ok and _item(r, "browser_for_animatics") is None   # base + 2048 MB only
    # refresh-ad still takes its tiers from its outputs, and never the animatic one
    assert envtiers.tiers_for({"creative_brief", "edited_video", "ai_video", "live_test"}, voice=True) == [
        "base", "breakdown", "video", "voice", "ai"]


def test_animatic_tier_shares_video_env(tmp_path, monkeypatch):
    assert envtiers.TIERS["animatic"] == envtiers.Tier("animatic", "video", ["base"], 150, {"animatics"})
    assert envtiers.TIERS["base"].outputs == {"creative_brief", "edited_video", "ai_video", "live_test"}
    monkeypatch.setattr(envtiers.paths, "plugin_root", lambda: tmp_path)
    monkeypatch.setattr(envtiers.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(envtiers.paths, "pixi_env", lambda: {})
    calls, steps = [], []
    monkeypatch.setattr(envtiers.subprocess, "run", lambda argv, **k: calls.append(argv)
                        or subprocess.CompletedProcess(argv, 0, "", ""))
    monkeypatch.setattr(atlas, "setup", lambda: steps.append("atlas"))
    monkeypatch.setattr(render, "setup", lambda: steps.append("remotion"))
    assert envtiers.install("animatic", yes=True) == 0
    assert calls == [[str(tmp_path / "pixi"), "install", "--frozen", "-e", "video", "--manifest-path",
                      str(tmp_path / "env" / "pixi.toml")]]
    assert steps == ["atlas"]   # never Remotion's setup or its browser
    monkeypatch.setattr(atlas, "setup", lambda: (_ for _ in ()).throw(common.ToolError("npm ci failed")))
    assert envtiers.install("animatic", yes=True) == 1

    monkeypatch.setattr(envtiers, "_env_installed", lambda env: env == "video")
    monkeypatch.setattr(atlas, "setup_done", lambda: False)
    assert envtiers.installed("video") and not envtiers.installed("animatic")
    monkeypatch.setattr(atlas, "setup_done", lambda: True)
    assert envtiers.installed("animatic")


# --- the real render ------------------------------------------------------------------------------

@pytest.mark.parametrize("expr,asked", [("", False), ("video", True), ("video and not slow", True),
                                        ("not video", False), ("tools", False), ("tools or video", True)])
def test_video_asked_for_reads_the_mark_expression(expr, asked):
    assert video_asked_for(SimpleNamespace(getoption=lambda name: expr)) is asked


@pytest.mark.private_data
@pytest.mark.video
def test_real_render_of_ld_c1_9x16(request, tmp_path, tmp_path_factory, monkeypatch):
    if not video_asked_for(request.config):
        pytest.skip("the real render runs with -m video (pixi run -e dev-full test-video)")
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    cache = Path(os.environ.get("TM_TEST_REMOTION_CACHE")
                 or tmp_path_factory.getbasetemp().parent / "tm-remotion-cache")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(PLUGIN))
    monkeypatch.setattr(atlas.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(atlas.remotion, "_prefix", lambda: [])  # already inside an environment with Node
    monkeypatch.setattr(atlas.envtiers, "installed", lambda tier: True)
    if atlas.find_browser() is None:
        pytest.skip("no Chrome, Edge or Chromium on this computer")
    atlas.setup()
    folder = tmp_path / "animatic gen"
    folder.mkdir()
    for name in ("C1_9x16_v03.html", "engine.js", "scenes.js", "C1_anim_v03.js"):
        shutil.copyfile(ANIMATIC_GEN / name, folder / name)
    out = tmp_path / "03_wip" / "C1_9x16_v01.mp4"
    out.parent.mkdir()
    summary = atlas.render(folder / "C1_9x16_v03.html", out)
    assert summary["page_errors"] == [] and summary["size"] == [1080, 1920], summary
    assert summary["frames"] == round(summary["duration"] * 24)
    probe = json.loads(subprocess.run(
        [common.ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "json", str(out)], capture_output=True, text=True, check=True).stdout)
    assert (probe["streams"][0]["width"], probe["streams"][0]["height"]) == (1080, 1920)
    stills = sorted(p.name for p in out.parent.glob("C1_9x16_v01_still_*.png"))
    assert stills == [f"C1_9x16_v01_still_{n}.png" for n in ("006", "030", "055", "080", "095")]
    assert sorted(p.name for p in out.parent.iterdir()) == sorted([out.name, *stills])
