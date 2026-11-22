"""Smart App Control blocking a compiled file of a tool (#148 line 154, after issue #123).

When a plugin tool fails while loading a compiled file (Python's "DLL load failed" or an ImportError on a `.pyd`, or
Windows error 4551) and Smart App Control is on (the registry's VerifiedAndReputablePolicyState is 1), tm shows the
python.exe message, naming the blocked file, instead of the raw Python error. Off Windows, or with Smart App Control
off, the raw error stays. The registry is stubbed with a fake `winreg` module, as Windows has it."""
import json
import subprocess
import sys
import types

import pytest

import tm.__main__ as entry
from tm import cli, i18n, toolrun, winblock
from tm.tools import _common as c
from tm.tools import _ocr

TEXT = "An Application Control policy has blocked this file."
DLL = f"DLL load failed while importing _x: {TEXT}"
PYD = r"C:\Users\x\data\venvs\breakdown\Lib\site-packages\scipy\linalg\_flapack.cp311-win_amd64.pyd"
PYD_ERROR = f"cannot import name 'flapack' from 'scipy.linalg._flapack' ({PYD})"


def _winreg(state=None, missing=False):
    """A fake winreg: the CI policy key holding VerifiedAndReputablePolicyState = state."""
    reads = []
    mod = types.ModuleType("winreg")
    mod.HKEY_LOCAL_MACHINE = "HKLM"

    class Key:
        def __init__(self, root, sub):
            if missing:
                raise FileNotFoundError(2, "The system cannot find the file specified")
            reads.append((root, sub))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def query(key, name):
        reads.append(name)
        if state is None:
            raise FileNotFoundError(2, "The system cannot find the file specified")
        return state, 4

    mod.OpenKey = Key
    mod.QueryValueEx = query
    mod.reads = reads
    return mod


@pytest.fixture
def sac(monkeypatch):
    """Smart App Control on, as the registry says it."""
    fake = _winreg(1)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


@pytest.fixture
def sac_off(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", _winreg(0))


# --- reading the registry --------------------------------------------------------------------------------------------

def test_smart_app_control_is_on_only_when_the_registry_says_1(monkeypatch):
    fake = _winreg(1)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert winblock.smart_app_control_on()
    assert fake.reads == [("HKLM", r"SYSTEM\CurrentControlSet\Control\CI\Policy"), "VerifiedAndReputablePolicyState"]
    for state in (0, 2):   # 0 off, 2 evaluation mode: Windows does not block then
        monkeypatch.setitem(sys.modules, "winreg", _winreg(state))
        assert not winblock.smart_app_control_on()
    monkeypatch.setitem(sys.modules, "winreg", _winreg(None))          # no such value
    assert not winblock.smart_app_control_on()
    monkeypatch.setitem(sys.modules, "winreg", _winreg(1, missing=True))   # no such key
    assert not winblock.smart_app_control_on()


def test_off_windows_there_is_no_registry_and_no_smart_app_control(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", None)   # `import winreg` raises ImportError, as on macOS and Linux
    assert not winblock.smart_app_control_on()
    assert winblock.tool_message(ImportError(DLL)) is None


# --- which failures count, and the file named --------------------------------------------------------------------------

def test_dll_load_failed_is_the_message_naming_the_module(sac):
    said = winblock.tool_message(ImportError(DLL))
    assert said.startswith(i18n.t("env.smart_app_control", file="_x"))
    assert winblock.AGENT in said


def test_the_path_python_gives_is_the_file_named(sac):
    exc = ImportError(DLL, name="_x", path=r"C:\v\Lib\site-packages\av\_x.cp311-win_amd64.pyd")
    assert r"(C:\v\Lib\site-packages\av\_x.cp311-win_amd64.pyd)" in winblock.tool_message(exc)


def test_an_import_error_naming_a_pyd_is_the_message_naming_it(sac):
    said = winblock.tool_message(ImportError(PYD_ERROR))
    assert said.startswith(i18n.t("env.smart_app_control", file=PYD))


def test_error_4551_counts_and_names_the_dll(sac):
    exc = OSError(f'[WinError 4551] {TEXT} Error loading "C:\\v\\torch\\lib\\c10.dll" or one of its dependencies.')
    assert winblock.tool_message(exc).startswith(i18n.t("env.smart_app_control", file=r"C:\v\torch\lib\c10.dll"))
    exc = OSError(1, TEXT, r"C:\v\torch\lib\c10.dll")
    exc.winerror = 4551
    assert r"(C:\v\torch\lib\c10.dll)" in winblock.tool_message(exc)


def test_a_file_the_error_does_not_name_is_said_so(sac):
    said = winblock.tool_message(OSError("[WinError 4551] blocked"))
    unnamed = i18n.t("env.smart_app_control_unnamed")
    assert said.startswith(i18n.t("env.smart_app_control", file=unnamed))
    assert "Smart App Control" in said


@pytest.mark.parametrize("exc", [ImportError("No module named 'scipy'"), ModuleNotFoundError("No module named 'x'"),
                                 OSError("[WinError 126] The specified module could not be found"),
                                 FileNotFoundError(2, "No such file", "runs/4551.mp4"), ValueError(DLL)])
def test_other_failures_stay_raw_with_smart_app_control_on(sac, exc):
    assert winblock.tool_message(exc) is None


def test_smart_app_control_off_leaves_the_raw_error(sac_off):
    assert winblock.tool_message(ImportError(DLL)) is None
    assert winblock.tool_message(ImportError(PYD_ERROR)) is None
    assert winblock.text_message("ImportError: " + DLL) is None


def test_a_childs_output_is_read_the_same_way(sac):
    stderr = ("Traceback (most recent call last):\n"
              '  File "C:\\v\\Lib\\site-packages\\scipy\\linalg\\__init__.py", line 3, in <module>\n'
              f"ImportError: {DLL}\n")
    assert winblock.text_message(stderr).startswith(i18n.t("env.smart_app_control", file="_x"))
    assert winblock.text_message(f"Traceback ...\nImportError: {PYD_ERROR}\n").startswith(
        i18n.t("env.smart_app_control", file=PYD))
    assert winblock.text_message("Traceback ...\nModuleNotFoundError: No module named 'rapidocr'\n") is None


@pytest.mark.parametrize("lang", ["en", "pl"])
def test_the_unnamed_words_exist_in_both_tables(lang):
    want = i18n.english() if lang == "en" else i18n._shipped(lang)
    assert want["env.smart_app_control_unnamed"]


# --- tm's own process ----------------------------------------------------------------------------------------------

def test_tm_itself_shows_the_message_for_a_blocked_pyd(sac, monkeypatch, capsys):
    monkeypatch.setattr(cli, "main", lambda argv=None: (_ for _ in ()).throw(ImportError(DLL, name="_x", path=PYD)))
    monkeypatch.delenv("TM_BLOCK_EXIT", raising=False)
    assert entry.run() == 1
    err = capsys.readouterr().err
    assert "Smart App Control" in err and PYD in err and "Traceback" not in err


def test_tm_itself_raises_a_pyd_failure_with_smart_app_control_off(sac_off, monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv=None: (_ for _ in ()).throw(ImportError(PYD_ERROR)))
    with pytest.raises(ImportError):
        entry.run()


# --- a tool's own process (tm tool <name>) -------------------------------------------------------------------------

def _tool(exc):
    @c.guarded
    def main(argv=None):
        raise exc
    return main


def test_a_tool_shows_the_message_as_a_stop(sac, capsys):
    assert _tool(ImportError(DLL))([]) == 2
    out = capsys.readouterr().out
    assert out.startswith(i18n.t("env.smart_app_control", file="_x")) and "DLL load failed" not in out
    assert _tool(ImportError(PYD_ERROR))(["--json"]) == 2
    said = json.loads(capsys.readouterr().out)
    assert said["status"] == "stop" and PYD in said["message"] and "Smart App Control" in said["message"]


def test_a_tool_keeps_the_raw_error_with_smart_app_control_off(sac_off, capsys):
    assert _tool(ImportError(DLL))([]) == 1
    assert capsys.readouterr().out.strip() == f"Unexpected ImportError: {DLL}"
    assert _tool(OSError("disk full"))([]) == 1
    assert capsys.readouterr().out.strip() == "disk full"


def test_a_tool_missing_a_part_still_says_so(sac, capsys):
    exc = ModuleNotFoundError("No module named 'faster_whisper'", name="faster_whisper")
    assert _tool(exc)([]) == 2
    assert "missing a part (faster_whisper)" in capsys.readouterr().out


def test_the_runner_shows_the_message_for_an_import_that_fails_before_the_tool_starts(sac, monkeypatch, capsys):
    seen = {}

    def blocked(name, run_name=None, alter_sys=False):
        seen.update(name=name, run_name=run_name, argv=list(sys.argv[1:]))
        raise ImportError(DLL, name="_x", path=PYD)

    monkeypatch.setattr(toolrun.runpy, "run_module", blocked)
    monkeypatch.setattr(sys, "argv", ["toolrun"])
    assert toolrun.run(["teardown", "--json", "a b.mp4"]) == 2
    said = json.loads(capsys.readouterr().out)
    assert said == {"status": "stop", "message": winblock.message(PYD)}
    assert seen == {"name": "tm.tools.teardown", "run_name": "__main__", "argv": ["--json", "a b.mp4"]}


def test_the_runner_raises_anything_else(sac_off, monkeypatch):
    def blocked(name, run_name=None, alter_sys=False):
        raise ImportError(DLL)

    monkeypatch.setattr(toolrun.runpy, "run_module", blocked)
    monkeypatch.setattr(sys, "argv", ["toolrun"])
    with pytest.raises(ImportError):
        toolrun.run(["teardown"])


def test_the_runner_runs_the_tool_as_its_main_in_a_child():
    proc = subprocess.run([sys.executable, "-m", "tm.toolrun", "ffmpeg", "--help"], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "usage: tm tool ffmpeg" in proc.stdout


def test_tm_tool_starts_the_tool_through_the_runner(monkeypatch, tmp_path):
    from tm import paths
    from tm.tools import child_argv

    monkeypatch.setenv("TM_PLUGIN_ROOT", str(tmp_path))            # CI has no ~/.trendsmesh/paths.json
    monkeypatch.setattr(paths, "pixi_bin", lambda: tmp_path / "pixi")
    argv = child_argv("teardown", ["--run", "r", "a.mp4"])
    assert argv[argv.index("-m"):] == ["-m", "tm.toolrun", "teardown", "--run", "r", "a.mp4"]


# --- the OCR worker's process: its stderr ----------------------------------------------------------------------------

@pytest.fixture
def ocr_child(monkeypatch):
    monkeypatch.setattr(_ocr, "save_frames", lambda video, frames, folder: {str(f): str(folder / f"{f}.png")
                                                                            for f in frames})
    monkeypatch.setattr(_ocr, "worker_env", lambda: {})
    monkeypatch.setattr(_ocr, "worker_argv", lambda req, res: ["pixi", str(req), str(res)])

    def child(stderr):
        monkeypatch.setattr(_ocr.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", stderr))
    return child


CROPS = [{"id": "0:3", "frame": 3, "box": [0, 0, 10, 10]}]
TRACEBACK = ('Traceback (most recent call last):\n  File "C:\\v\\Lib\\site-packages\\rapidocr\\main.py", line 1\n'
             "ImportError: {}\n")


def test_the_ocr_workers_blocked_pyd_is_the_message(sac, ocr_child):
    ocr_child(TRACEBACK.format(DLL))
    with pytest.raises(c.ToolError) as got:
        _ocr.read_with_tier("ad.mp4", CROPS)
    assert str(got.value) == winblock.message("_x")
    ocr_child(TRACEBACK.format(PYD_ERROR))
    with pytest.raises(c.ToolError) as got:
        _ocr.read_with_tier("ad.mp4", CROPS)
    assert str(got.value) == winblock.message(PYD)


def test_the_ocr_workers_raw_error_stays_with_smart_app_control_off(sac_off, ocr_child):
    ocr_child(TRACEBACK.format(DLL))
    with pytest.raises(c.ToolError, match="OCR could not run: .*DLL load failed while importing _x"):
        _ocr.read_with_tier("ad.mp4", CROPS)
