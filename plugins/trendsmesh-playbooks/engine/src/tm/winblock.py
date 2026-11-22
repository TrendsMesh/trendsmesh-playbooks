"""Windows Smart App Control blocking a file of the plugin's Python (Windows error 4551, issue #123).

Smart App Control judges an unsigned file by Microsoft's cloud reputation of it, so a new conda-forge Python build
can be stopped on one machine and day and not on another. Since part 1 tm runs on python.org's Python on Windows,
signed by the Python Software Foundation (bootstrap/install-python.ps1); the packages in a tier's venv come from PyPI,
and their compiled files (numpy's, pydantic-core's, torch's ...) carry no signature, so they can still be blocked. It shows up as pixi's "(os error 4551)" when python.exe
itself is blocked, or as `ImportError: DLL load failed while importing _ssl: <Windows' text>` when one of its
modules is: that text is Windows' own message for error 4551, in the user's language, with no number.

    blocked(exc)        is this ImportError or OSError such a block?
    matches(text)       does a command's output say so (the launchers' probe and session start read it too)?
    blocked_file(exc)   the file Windows blocked, as the error names it (None when it names none)
    message(file)       what tm prints: the table's env.smart_app_control, then one line for the agent

A tool's compiled file (#148 line 154): when a plugin tool fails while loading a compiled file (Python's "DLL load
failed", an ImportError on a `.pyd`, or error 4551) and Smart App Control is on (the registry's
VerifiedAndReputablePolicyState is 1), tm shows the same message, naming the file, instead of the raw error. Off
Windows (no winreg) or with Smart App Control off, the raw error stays.

    smart_app_control_on()   the registry says Smart App Control is on (enforcing)
    tool_message(exc)        the message for such a failure, or None (tools/_common.guarded, tm.toolrun, tm itself)
    text_message(text)       the same from a child's output (the OCR worker's stderr)

Only the standard library at import: tm prints this when its own imports fail."""
from __future__ import annotations

import re
from pathlib import Path

ERROR = 4551
_NUMBER = re.compile(r"(?i)(\bos error|\bwinerror|\berror)\W{0,3}4551\b")
POLICY_KEY = r"SYSTEM\CurrentControlSet\Control\CI\Policy"
POLICY_VALUE = "VerifiedAndReputablePolicyState"
_DLL = re.compile(r"(?i)\bDLL load failed\b")
_PYD = re.compile(r"(?i)\.pyd\b")
_PYD_LINE = re.compile(r"(?im)^\s*ImportError:.*\.pyd\b")
_IMPORT_LINE = re.compile(r"(?m)^\s*(?:ImportError|OSError):.*$")
_QUOTED = re.compile(r"""["'(]([^"'()\r\n]+?\.(?:pyd|dll))["')]""", re.I)
_DRIVE = re.compile(r"""([A-Za-z]:[\\/][^"'()<>|*?\r\n:]*?\.(?:pyd|dll))\b""", re.I)
_BARE = re.compile(r"""([^\s"'()<>|*?:]+\.(?:pyd|dll))\b""", re.I)
_IMPORTING = re.compile(r"while importing ([^\s:]+)")
AGENT = ("For Claude: tell the user these steps in plain words; it is no network or install failure. Never change "
         "Windows security settings yourself.")


def localized() -> str | None:
    """Windows' own text for error 4551, in the system's language (None off Windows, or when ctypes is blocked)."""
    try:
        import ctypes
        text = ctypes.FormatError(ERROR).strip()
    except Exception:
        return None
    return text.rstrip(".").strip() or None


def matches(text: str, localized: str | None = None) -> bool:
    """Does `text` say Windows blocked a file with error 4551: the number, or the localized text?"""
    if _NUMBER.search(text or ""):
        return True
    words = localized.rstrip(".").strip() if localized else None
    return bool(words) and words.lower() in (text or "").lower()


def blocked(exc: BaseException) -> bool:
    if not isinstance(exc, (ImportError, OSError)):
        return False
    if getattr(exc, "winerror", None) == ERROR:
        return True
    return matches(str(exc), localized())


def file_in_text(text: str) -> str | None:
    """The compiled file an error's text names: a quoted or bracketed `.pyd`/`.dll` path, a full Windows path to one,
    a bare file name, or the module of "while importing X"; None when it names none."""
    for pattern in (_QUOTED, _DRIVE, _BARE, _IMPORTING):
        m = pattern.search(text or "")
        if m:
            return m.group(1)
    return None


def blocked_file(exc: BaseException) -> str | None:
    """The file the error names: its own path or filename, else one in its text, else its module (None: no name)."""
    for name in ("path", "filename"):
        value = getattr(exc, name, None)
        if value:
            return str(value)
    return file_in_text(str(exc)) or getattr(exc, "name", None) or None


def smart_app_control_on() -> bool:
    """HKLM\\SYSTEM\\CurrentControlSet\\Control\\CI\\Policy, VerifiedAndReputablePolicyState = 1 (0 is off, 2 is
    evaluation, when Windows only watches). No winreg (macOS, Linux) or no such key or value: off."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, POLICY_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, POLICY_VALUE)
    except (ImportError, OSError, TypeError, ValueError, AttributeError):
        return False
    return value == 1


def compiled_failed(exc: BaseException) -> bool:
    """A compiled file did not load: "DLL load failed", an ImportError naming a `.pyd`, or error 4551. A module that is
    missing (ModuleNotFoundError, "No module named") is not one."""
    if isinstance(exc, ImportError) and not isinstance(exc, ModuleNotFoundError):
        text = str(exc)
        if _DLL.search(text) or _PYD.search(text) or str(getattr(exc, "path", "") or "").lower().endswith(".pyd"):
            return True
    return blocked(exc)


def tool_message(exc: BaseException) -> str | None:
    """The message for a tool (or tm) that failed loading a compiled file with Smart App Control on, else None."""
    if not compiled_failed(exc) or not smart_app_control_on():
        return None
    return message(blocked_file(exc))


def text_message(text: str) -> str | None:
    """The same for a child process's output (its traceback): None unless it shows such a failure and Smart App
    Control is on."""
    text = text or ""
    shown = bool(_DLL.search(text) or _PYD_LINE.search(text) or matches(text, localized()))
    if not shown or not smart_app_control_on():
        return None
    last = _IMPORT_LINE.findall(text)   # the traceback's last error line names the file best
    return message((file_in_text(last[-1]) if last else None) or file_in_text(text))


def _unnamed() -> str:
    try:
        from tm import i18n
        return i18n.t("env.smart_app_control_unnamed")
    except Exception:
        return "the error did not say which file"


def message(file: str | None) -> str:
    """The user's message from the string table (read without yaml if that fails too), then the agent's line. With no
    file, the table's env.smart_app_control_unnamed stands in its place."""
    file = file or _unnamed()
    try:
        from tm import i18n
        text = i18n.t("env.smart_app_control", file=file)
    except Exception:
        table = Path(__file__).resolve().parents[3] / "data" / "i18n" / "en.yaml"
        try:
            line = re.search(r'(?m)^\s*smart_app_control:\s*"(.*)"\s*$', table.read_text(encoding="utf-8"))
            text = line.group(1).replace("{file}", file)
        except Exception:
            text = f"Windows Smart App Control blocked a file of the plugin's Python ({file})."
    return f"{text}\n{AGENT}"
