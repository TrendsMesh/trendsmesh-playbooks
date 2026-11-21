"""Windows Smart App Control (error 4551) stops tm with its own message (issue #123, part 2).

Windows names the block only in its own language (ctypes.FormatError(4551)), so these tests give ctypes a
FormatError on every system, as Windows has it."""
import ctypes

import pytest

import tm.__main__ as entry
from tm import cli, i18n, winblock

TEXT = "An Application Control policy has blocked this file."


@pytest.fixture
def windows_text(monkeypatch):
    monkeypatch.setattr(ctypes, "FormatError", lambda code=None: TEXT if code == 4551 else "Other error.",
                        raising=False)


def test_the_localized_text_alone_is_a_block(windows_text):
    exc = ImportError(ctypes.FormatError(4551))
    assert winblock.blocked(exc)


def test_a_blocked_dll_names_its_file(windows_text):
    exc = ImportError(f"DLL load failed while importing _ssl: {ctypes.FormatError(4551)}", name="_ssl",
                      path=r"C:\Users\x\data\envs\abc\envs\base\DLLs\_ssl.pyd")
    assert winblock.blocked(exc)
    assert winblock.blocked_file(exc) == r"C:\Users\x\data\envs\abc\envs\base\DLLs\_ssl.pyd"
    assert winblock.blocked_file(ImportError(f"DLL load failed while importing _queue: {TEXT}")) == "_queue"


def test_the_error_number_is_a_block_in_any_language():
    assert winblock.blocked(OSError("failed to spawn python.exe (os error 4551)"))
    assert winblock.blocked(ImportError("[WinError 4551] Zasady kontroli aplikacji zablokowały ten plik"))
    exc = OSError(1, "blocked", r"C:\x\python.exe")
    exc.winerror = 4551
    assert winblock.blocked(exc)
    assert winblock.blocked_file(exc) == r"C:\x\python.exe"


def test_other_errors_are_no_block(windows_text):
    assert not winblock.blocked(ImportError("No module named 'yaml'"))
    assert not winblock.blocked(FileNotFoundError(2, "No such file", "runs/4551.mp4"))
    assert not winblock.blocked(OSError("port 4551 is in use"))
    assert not winblock.blocked(ValueError(TEXT))


def test_text_matches_the_launchers_reading():
    assert winblock.matches(f"Error: failed to spawn (os error 4551)")
    assert winblock.matches("ImportError: DLL load failed while importing _ssl: " + TEXT, localized=TEXT)
    assert not winblock.matches("ImportError: DLL load failed while importing _ssl: The specified module could not "
                                "be found.", localized=TEXT)


def test_the_message_comes_from_the_string_table():
    text = winblock.message("_ssl.pyd")
    assert text.startswith(i18n.t("env.smart_app_control", file="_ssl.pyd"))
    assert "Smart App Control" in text and "_ssl.pyd" in text
    assert "Never change Windows security settings yourself" in text


@pytest.mark.parametrize("lang", ["en", "pl"])
def test_the_launchers_read_the_table_line_as_it_is(lang):
    # bin/tm, tm.ps1 and the session-start scripts take the text between the quotes, with no yaml.
    lines = [l for l in (i18n.TABLES / f"{lang}.yaml").read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("smart_app_control:")]
    assert len(lines) == 1
    raw = lines[0].split(":", 1)[1].strip()
    assert raw.startswith('"') and raw.endswith('"') and '\\' not in raw and '"' not in raw[1:-1]
    want = i18n.english() if lang == "en" else i18n._shipped(lang)
    assert raw[1:-1] == want["env.smart_app_control"]


def test_tm_prints_the_message_and_exits_1_with_no_traceback(windows_text, monkeypatch, capsys):
    def blocked(argv=None):
        raise ImportError(f"DLL load failed while importing _ssl: {ctypes.FormatError(4551)}", name="_ssl",
                          path=r"C:\d\DLLs\_ssl.pyd")
    monkeypatch.setattr(cli, "main", blocked)
    monkeypatch.delenv("TM_BLOCK_EXIT", raising=False)
    assert entry.run() == 1
    err = capsys.readouterr().err
    assert "Smart App Control" in err and r"C:\d\DLLs\_ssl.pyd" in err
    assert "Traceback" not in err


def test_the_launcher_can_tell_the_block_from_another_failure(windows_text, monkeypatch, capsys):
    monkeypatch.setattr(cli, "main", lambda argv=None: (_ for _ in ()).throw(ImportError(TEXT)))
    monkeypatch.setenv("TM_BLOCK_EXIT", "86")
    assert entry.run() == 86


def test_any_other_error_is_raised_as_before(windows_text, monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv=None: (_ for _ in ()).throw(ImportError("No module named 'x'")))
    with pytest.raises(ImportError):
        entry.run()
    monkeypatch.setattr(cli, "main", lambda argv=None: 2)
    assert entry.run() == 2
