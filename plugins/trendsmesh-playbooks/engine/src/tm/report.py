"""`tm report`: helpers for the report-issue skill.

`check` finds private data left in a draft (an account id, an email, a key, a home folder, an amount
of money, a name from the user's workspace) before it is filed. `findings` and `workspace_values`
are also what `send` and `github` use to refuse a draft that is not clean.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Tuple

from tm import cli, paths

Finding = Tuple[int, str, str]   # (line, kind, value)

_KEYS = ("account_id", "account_name", "ad_account_id", "ad_account_name", "page_id", "page_name", "brand",
         "business_name", "handle", "campaign_name", "adset_name", "ad_name")
_SKIP_DIRS = {".pixi", "node_modules", ".git"}
_MAX_JSON = 5 * 1024 * 1024
_MIN_VALUE = 3
_ALLOWED_MAIL = {"contact@trendsmesh.com"}
_ALLOWED_DOMAINS = {"example.com", "example.org", "example.net"}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_KEY = re.compile(r"(?<![A-Za-z0-9])(?:r8_[A-Za-z0-9]{20,}|sk_[a-f0-9]{40,}|EAA[A-Za-z0-9]{20,}"
                  r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{20,})")
_ACT = re.compile(r"(?<![A-Za-z0-9])act_\d{5,}")
_DIGITS = re.compile(r"(?<!\w)\d{13,17}(?!\w)")
_PATH = re.compile(r"(?<![\w.-])(?:/(?:Users|home)/|(?i:c):\\Users\\)([^/\\\s\"']+)")
_NUM = r"\d(?:[\d ,.]*\d)?"
_CUR = r"(?:[$€£]|zł|(?<![A-Za-z])(?:USD|EUR|GBP|PLN)(?![A-Za-z]))"
_AMOUNT = re.compile(rf"(?:{_CUR} ?(?P<a>{_NUM})|(?P<b>{_NUM}) ?{_CUR})")

# When two matches overlap, the more specific kind wins.
_PRIORITY = ["key", "account_id", "email", "home_path", "amount", "workspace_value"]


def _candidates(line: str, known_re: "re.Pattern[str] | None"):
    for m in _KEY.finditer(line):
        yield m.start(), m.end(), "key"
    for m in _ACT.finditer(line):
        yield m.start(), m.end(), "account_id"
    for m in _DIGITS.finditer(line):
        yield m.start(), m.end(), "account_id"
    for m in _EMAIL.finditer(line):
        addr = m.group(0)
        if addr.lower() in _ALLOWED_MAIL or addr.rsplit("@", 1)[1].lower() in _ALLOWED_DOMAINS:
            continue
        yield m.start(), m.end(), "email"
    for m in _PATH.finditer(line):
        if m.group(1) != "<user>":
            yield m.start(), m.end(), "home_path"
    for m in _AMOUNT.finditer(line):
        digits = re.sub(r"\D", "", m.group("a") or m.group("b"))
        if 1 <= len(digits) <= 9:
            yield m.start(), m.end(), "amount"
    if known_re is not None:
        for m in known_re.finditer(line):
            yield m.start(), m.end(), "workspace_value"


def findings(text: str, known: set[str]) -> list[Finding]:
    """The private data in `text`, as (line, kind, value) sorted by line then column. A value that
    several kinds match is reported once, as the most specific kind."""
    values = sorted({v for v in known if v and v.strip()}, key=len, reverse=True)
    known_re = (re.compile(r"(?<!\w)(?:" + "|".join(re.escape(v) for v in values) + r")(?!\w)", re.IGNORECASE)
                if values else None)
    out: list[tuple[int, int, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        taken: list[tuple[int, int]] = []
        found = sorted(_candidates(line, known_re), key=lambda c: (_PRIORITY.index(c[2]), c[0]))
        for start, end, kind in found:
            if any(start < e and s < end for s, e in taken):
                continue
            taken.append((start, end))
            out.append((number, start, kind, line[start:end]))
    out.sort(key=lambda f: (f[0], f[1]))
    return [(n, kind, value) for n, _, kind, value in out]


def _collect(node: object, into: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _KEYS and isinstance(value, str) and len(value) >= _MIN_VALUE:
                into.add(value)
            _collect(value, into)
    elif isinstance(node, list):
        for item in node:
            _collect(item, into)


def _secret_values() -> set[str]:
    try:
        text = (paths.data_dir() / "secrets.env").read_text(encoding="utf-8")
    except (OSError, RuntimeError):
        return set()
    values = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        _, sep, value = line.partition("=")
        value = value.strip().strip("'\"")
        if sep and len(value) >= _MIN_VALUE:
            values.add(value)
    return values


def workspace_values(root: Path) -> set[str]:
    """Names and ids from the user's saved JSON under `root` (any depth), plus the plugin's secrets."""
    values: set[str] = set()
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if not name.endswith(".json"):
                continue
            path = Path(folder) / name
            try:
                if path.stat().st_size > _MAX_JSON:
                    continue
                _collect(json.loads(path.read_text(encoding="utf-8-sig")), values)
            except (OSError, ValueError):
                continue
    return values | _secret_values()


# --- command line ------------------------------------------------------------------------------

_SUBCOMMANDS: dict[str, tuple[Callable[[argparse.ArgumentParser], None], Callable[[argparse.Namespace], int]]] = {}


def subcommand(name: str, setup: Callable[[argparse.ArgumentParser], None],
               run: Callable[[argparse.Namespace], int]) -> None:
    """Add `tm report <name>` (send and github register theirs here)."""
    _SUBCOMMANDS[name] = (setup, run)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="report_command", metavar="command")
    for name, (setup, _run) in _SUBCOMMANDS.items():
        setup(sub.add_parser(name))


def _run(args: argparse.Namespace) -> int:
    name = getattr(args, "report_command", None)
    if name is None:
        print("usage: tm report {" + ",".join(_SUBCOMMANDS) + "} ...", file=sys.stderr)
        return 1
    return _SUBCOMMANDS[name][1](args)


def _check_setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file")
    parser.add_argument("--workspace", default=None)


def _check_run(args: argparse.Namespace) -> int:
    try:
        text = Path(args.file).read_text(encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    root = Path(args.workspace) if args.workspace else paths.workspace()
    found = findings(text, workspace_values(root))
    if not found:
        print("clean")
        return 0
    for line, kind, value in found:
        print(f"{line}\t{kind}\t{value}")
    return 1


subcommand("check", _check_setup, _check_run)
cli.register("report", _setup, _run)
