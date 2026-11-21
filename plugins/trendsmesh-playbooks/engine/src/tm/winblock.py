"""Windows Smart App Control blocking a file of the plugin's Python (Windows error 4551, issue #123).

Smart App Control judges an unsigned file by Microsoft's cloud reputation of it, so a new conda-forge Python build
can be stopped on one machine and day and not on another. Since part 1 tm runs on python.org's Python on Windows,
signed by the Python Software Foundation (bootstrap/install-python.ps1); the packages in a tier's venv come from PyPI,
and their compiled files (numpy's, pydantic-core's, torch's ...) carry no signature, so they can still be blocked. It shows up as pixi's "(os error 4551)" when python.exe
itself is blocked, or as `ImportError: DLL load failed while importing _ssl: <Windows' text>` when one of its
modules is: that text is Windows' own message for error 4551, in the user's language, with no number.

    blocked(exc)        is this ImportError or OSError such a block?
    matches(text)       does a command's output say so (the launchers' probe and session start read it too)?
    blocked_file(exc)   the file Windows blocked, as the error names it
    message(file)       what tm prints: the table's env.smart_app_control, then one line for the agent

Only the standard library at import: tm prints this when its own imports fail."""
from __future__ import annotations

import re
from pathlib import Path

ERROR = 4551
_NUMBER = re.compile(r"(?i)(\bos error|\bwinerror|\berror)\W{0,3}4551\b")
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


def blocked_file(exc: BaseException) -> str:
    for name in ("path", "filename"):
        value = getattr(exc, name, None)
        if value:
            return str(value)
    m = re.search(r"while importing ([^\s:]+)", str(exc))
    if m:
        return m.group(1)
    return getattr(exc, "name", None) or "python.exe"


def message(file: str) -> str:
    """The user's message from the string table (read without yaml if that fails too), then the agent's line."""
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
