"""Allow the plugin's commands and pages once, before a run (issue #163).

In Claude Code's auto mode a classifier can refuse a step the user already approved in chat, and each refusal
stops the run (`references/permissions.md`). So at readiness the playbook asks once, and only in auto mode: "So the
run doesn't stop on the way, allow the plugin's commands and its pages?" On the user's yes,

    tm permissions allow [--project DIR] --yes [--json]

adds RULES to `permissions.allow` in the project's `.claude/settings.local.json` (the user's own file for that
folder, never shared), merged with what is there: the user's own rules and keys stay as they are and in their order,
a rule already there is not added again, a missing file is made, and a file that is not valid JSON (or not
settings' shape) is refused with nothing written. Without `--yes` it is a dry run that writes nothing: which rules
are there (in that file, the project's shared `.claude/settings.json` or the user's `~/.claude/settings.json`),
which are missing, which this system needs (`needed`), the session's permission mode, and `ask`, whether to ask
the question.

Only a missing rule the user's system needs brings the question (change request on #176 line 65): on a Mac or Linux
Claude Code runs tm through its Bash tool, so a missing `PowerShell(tm *)` asks nothing there; on Windows it may run tm
through its Bash tool (Git Bash) or its PowerShell tool, so both shells' rules count. A yes still adds every missing
rule of the set, PowerShell's included, so the folder is covered from any system.

The mode: Claude Code gives hooks the session's `permission_mode`. The key guard (`bootstrap/guard-secrets.sh`, a
PreToolUse hook) writes it, for a `tm permissions` command only, to `<data>/permission-mode` as one line,
`<epoch seconds>\\t<mode>\\t<project folder>` (CLAUDE_PROJECT_DIR, else the call's cwd), just before the command
runs. A record older than FRESH_S seconds, of another folder, or with no mode reads as "unknown", and an unknown mode
asks whenever a needed rule is missing: a question too many costs less than a run that stops again and again.
TM_PERMISSION_MODE (tests and the evals' sandbox, where no hook runs) gives the mode instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from tm import cli, i18n, paths

RULES = ("Bash(tm *)", "PowerShell(tm *)", "Artifact")
# The older spelling of a prefix rule Claude Code still reads as the same rule.
SAME = {"Bash(tm:*)": "Bash(tm *)", "PowerShell(tm:*)": "PowerShell(tm *)"}
# The rules a system without Claude Code's PowerShell tool (a Mac, Linux) needs; Windows needs all of RULES.
NOT_WINDOWS = ("Bash(tm *)", "Artifact")
FRESH_S = 120
MODE_FILE = "permission-mode"


def needed(windows: bool | None = None) -> list[str]:
    """The rules whose absence brings the question (`windows`: which system; default the one tm runs on)."""
    if windows is None:
        windows = sys.platform == "win32"
    return list(RULES) if windows else [r for r in RULES if r in NOT_WINDOWS]


def _config_dir() -> Path:
    value = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(value) if value else Path.home() / ".claude"


def _same_folder(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def recorded() -> tuple[str, Path] | None:
    """The mode and project folder the key guard recorded for this `tm permissions` call, when fresh."""
    try:
        line = (paths.data_dir() / MODE_FILE).read_text(encoding="utf-8-sig").splitlines()[0]
        when, mode, folder = line.split("\t", 2)
        age = time.time() - int(when)
    except (OSError, RuntimeError, ValueError, IndexError):
        return None
    mode, folder = mode.strip(), folder.strip()
    if not mode or not folder or not -5 <= age <= FRESH_S:
        return None
    return mode, Path(folder)


def _allow_of(path: Path) -> list[str]:
    """`permissions.allow` of a settings file, [] when it is missing or unreadable (reading never refuses)."""
    try:
        data = cli.read_json(path)
    except (OSError, ValueError):
        return []
    perms = data.get("permissions") if isinstance(data, dict) else None
    allow = perms.get("allow") if isinstance(perms, dict) else None
    return [r for r in allow if isinstance(r, str)] if isinstance(allow, list) else []


def _present(project: Path) -> set[str]:
    have = set()
    for path in (project / ".claude" / "settings.local.json", project / ".claude" / "settings.json",
                 _config_dir() / "settings.json"):
        have.update(SAME.get(r.strip(), r.strip()) for r in _allow_of(path))
    return have


def _indent(text: str) -> str | int:
    """The file's own indent (its first indented line's), so a merge changes the rules, not the layout."""
    for line in text.splitlines()[1:]:
        lead = line[:len(line) - len(line.lstrip(" \t"))]
        if lead:
            return lead if lead.strip(" ") == "" or lead.strip("\t") == "" else 2
    return 2


class Refused(Exception):
    pass


def merge(path: Path, rules: list[str]) -> list[str]:
    """Add `rules` to `permissions.allow` in `path` (made when missing); return the ones added. Refuses (Refused)
    a file that is not valid JSON or not settings' shape, before anything is written."""
    rules_text = ", ".join(json.dumps(r) for r in RULES)
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8-sig")
            data = json.loads(text)
        except (OSError, ValueError) as exc:
            raise Refused(i18n.t("permissions.invalid", file=str(path), error=str(exc), rules=rules_text)) from exc
    else:
        text, data = "", {}
    perms = data.get("permissions", {}) if isinstance(data, dict) else None
    allow = perms.get("allow", []) if isinstance(perms, dict) else None
    if not isinstance(allow, list):
        raise Refused(i18n.t("permissions.shape", file=str(path), rules=rules_text))
    have = {SAME.get(r.strip(), r.strip()) for r in allow if isinstance(r, str)}
    added = [r for r in rules if r not in have]
    if not added:
        return []
    allow.extend(added)
    perms["allow"] = allow
    data["permissions"] = perms
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tm-tmp")
    tmp.write_text(json.dumps(data, indent=_indent(text), ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return added


def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("allow", help="add the plugin's allow rules to the project's .claude/settings.local.json")
    a.add_argument("--project", help="the folder Claude Code was started in (default: the one the hook recorded, "
                                     "else the current folder)")
    a.add_argument("--yes", action="store_true", help="write them (only after the user's yes); without it a dry run")
    a.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    forced = os.environ.get("TM_PERMISSION_MODE")   # tests and the evals' sandbox only: the mode, without a hook
    rec = (forced, Path(args.project) if args.project else paths.session_folder()) if forced else recorded()
    if args.project:
        project = Path(args.project)
        mode = rec[0] if rec and _same_folder(rec[1], project) else "unknown"
    else:
        project = rec[1] if rec else paths.session_folder()
        mode = rec[0] if rec else "unknown"
    target = project / ".claude" / "settings.local.json"
    have = _present(project)
    missing = [r for r in RULES if r not in have]
    need = needed()
    ask = any(r in missing for r in need) and mode in ("auto", "unknown")
    payload = {"status": "ok", "mode": mode, "file": str(target), "present": [r for r in RULES if r in have],
               "missing": missing, "needed": need, "ask": ask, "question": i18n.t("permissions.question"), "added": [],
               "written": False}
    if args.yes and missing:
        try:
            payload["added"] = merge(target, missing)
        except Refused as exc:
            return cli.fail(args, str(exc))
        payload["written"] = bool(payload["added"])
        payload["missing"] = [r for r in missing if r not in payload["added"]]
        text = i18n.t("permissions.added", rules=", ".join(payload["added"]), file=str(target))
    elif not missing:
        text = i18n.t("permissions.all_there")
    else:
        text = (f"{payload['question']} " if ask else "") + i18n.t("permissions.would_add",
                                                                    rules=", ".join(missing), file=str(target))
    cli.emit(args, payload, text)
    return 0


cli.register("permissions", _setup, _run)
