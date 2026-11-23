"""The pacer (issue #129, part 2): TrendsMesh calls wait until they fit the plan's limits, so none is refused.

    tm trends pace [--event FILE] [--json]          the PreToolUse hook, in Python: one event on stdin (or in FILE)
    tm trends pace --status [--workspace W] [--json]   the limits in use and the calls of the last minute

The hook that runs on every TrendsMesh call is bootstrap/pace-mcp.sh (pace.awk) and pace-mcp.ps1, a thin
limiter without Python (the owner's #148 line 12: Python costs about 0.5-1.5 s per call); this module is the
same limiter in Python, which pace-mcp.sh hands over to when it has no clock in milliseconds, and which
writes the limits the shell reads (`learn`). The three keep one call log per workspace,
`<workspace>/.trendsmesh/pace.jsonl` (`{"t": <ms>, "tool": "<short name>"}` per line), under one lock,
the file `.trendsmesh/pace.lock` with the time it was taken, made by an exclusive create (`O_EXCL`; the shell's
noclobber redirection is the same, so the shell and Python share it). Claude Code runs the PreToolUse hooks of
parallel calls at the same time (seen on 2.1.319), so the lock counts them one at a time. An older version's
lock, the folder `pace.lock` with the time in `pace.lock/t`, is waited for and taken over the same way.

A call goes ahead at the first moment T (now, or a moment a logged call leaves a window) at which, for every
window that applies to it, fewer than `limit` logged calls are closer to T than the window plus MARGIN_MS
(either side, so a call booked for later keeps its place), and no spent daily budget applies. Its moment is
booked in the log under the lock, and the hook then sleeps until T, so parallel calls queue. A call that
cannot go within MAX_WAIT_S is denied, with what to do; the hook's timeout in hooks.json is above it.

The windows: 10 calls a second for every tool, 10 `search_trends` and 20 `get_trend_videos` pages a minute
(the plan limits the issue gives), or the ones the newest saved `get_usage` answer gives: when a get_usage
answer is saved to a run (`trends.save_answer`), `learn` writes `.trendsmesh/pace-limits.tsv` beside the
log, one `window <ms> <limit> <tool or *>` line per window of a minute or less, and one `budget
<calls left> <answer ms> <reset ms> <tool or *> <reset, in words>` line per longer window (the day): the
calls logged since that answer count against it until the reset.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tm import cli, paths

DIR = ".trendsmesh"
LOG = "pace.jsonl"
LIMITS = "pace-limits.tsv"
LOCK = "pace.lock"
MARGIN_MS = 300                 # a call reaches TrendsMesh a little after the hook lets it go
MAX_WAIT_S = 65                 # a full minute of searches, and a little; hooks.json gives the hook 80 s
STALE_LOCK_MS = 5000            # the lock is held for milliseconds: older, its owner was killed
LOCK_WAIT_S = 5.0
DEFAULTS = ((1000, 10, "*"), (60_000, 10, "search_trends"), (60_000, 20, "get_trend_videos"))
_TOOL = re.compile(r"[A-Za-z0-9_-]{1,64}")
_RUN_FOLDER = re.compile(r"0[0-9]-.+")


@dataclass(frozen=True)
class Window:
    ms: int
    limit: int
    tool: str                   # a short tool name, or "*" for every tool


@dataclass(frozen=True)
class Budget:
    left: int
    since_ms: int
    reset_ms: int
    tool: str
    reset_text: str


def short_name(tool_name: Any) -> str:
    """mcp__…__search_trends -> search_trends; anything that is not a plain name -> "other"."""
    name = str(tool_name or "").rsplit("__", 1)[-1]
    return name if _TOOL.fullmatch(name) else "other"


def _hit(pattern: str, tool: str) -> bool:
    return pattern == "*" or pattern == tool


# --- where ------------------------------------------------------------------------------------

def workspace_for(cwd: Path) -> Path:
    """The workspace of the hook's cwd: it or the first folder above it holding .trendsmesh/ or runs/0N-…, never
    the home folder (its .trendsmesh/ holds the plugin's paths file) or above it; else the cwd itself (as
    pace-mcp.sh finds it)."""
    cwd = Path(cwd)
    try:
        home = os.path.normcase(str(Path.home()))
    except RuntimeError:
        home = None
    for folder in (cwd, *cwd.parents):
        if os.path.normcase(str(folder)) == home:
            break
        if (folder / DIR).is_dir():
            return folder
        try:
            if any(p.is_dir() and _RUN_FOLDER.fullmatch(p.name) for p in (folder / "runs").iterdir()):
                return folder
        except OSError:
            pass
    return cwd


# --- the limits -------------------------------------------------------------------------------

def read_limits(folder: Path) -> tuple[list[Window], list[Budget]]:
    """The windows and budgets of `<folder>/pace-limits.tsv`; the defaults when it has no window."""
    windows: list[Window] = []
    budgets: list[Budget] = []
    try:
        lines = (folder / LIMITS).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        f = line.split("\t")
        try:
            if f[0] == "window" and len(f) >= 4 and int(f[1]) > 0 and int(f[2]) > 0:
                windows.append(Window(int(f[1]), int(f[2]), f[3]))
            elif f[0] == "budget" and len(f) >= 6:
                budgets.append(Budget(int(f[1]), int(f[2]), int(f[3]), f[4], f[5]))
        except ValueError:
            continue
    return windows or [Window(*w) for w in DEFAULTS], budgets


def _seconds(value: Any) -> float | None:
    """A window's length in seconds, from a number of seconds or words like "60s", "1m", "minute", "day"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace("-", " ").replace("_", " ")
    words = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "daily": 86400, "hourly": 3600, "week": 604800}
    m = re.fullmatch(r"(\d+(?:\.\d+)?)?\s*(s|sec|secs|seconds?|m|min|mins|minutes?|h|hours?|d|days?)", text)
    if m:
        n = float(m.group(1) or 1)
        unit = m.group(2)[0]
        return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    for word, n in words.items():
        if word in text:
            return float(n)
    return None


def _ms(value: Any) -> int | None:
    """A reset time (ISO text or epoch seconds or ms) in epoch ms."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value if value > 1e11 else value * 1000)
    if isinstance(value, str) and value.strip():
        try:
            at = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return int((at if at.tzinfo else at.replace(tzinfo=timezone.utc)).timestamp() * 1000)
    return None


def _first(d: dict, *keys: str) -> Any:
    return next((d[k] for k in keys if k in d and d[k] is not None), None)


def _number(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _meter_tool(name: Any) -> str:
    text = str(name or "").lower()
    if "search" in text:
        return "search_trends"
    if "video" in text:
        return "get_trend_videos"
    return "*"


def usage_limits(answer: Any) -> tuple[list[Window], list[Budget]]:
    """The windows and budgets a get_usage answer gives (`{"meters": [...]}`; a meter has a name and either its own
    window or a `windows` list, each with a length, a limit and, for a budget, the calls left and the reset). Its
    shape is read loosely: any part it lacks is left out."""
    windows: list[Window] = []
    budgets: list[Budget] = []
    meters = answer.get("meters") if isinstance(answer, dict) else None
    for meter in meters if isinstance(meters, list) else []:
        if not isinstance(meter, dict):
            continue
        name = _first(meter, "meter", "name", "tool", "key", "id", "scope")
        rows = meter.get("windows") if isinstance(meter.get("windows"), list) else [meter]
        for w in rows:
            if not isinstance(w, dict):
                continue
            tool = _meter_tool(_first(w, "meter", "name", "tool") or name)
            length = _seconds(_first(w, "window_seconds", "window_s", "seconds", "period_seconds", "window", "period",
                                     "interval"))
            limit = _number(_first(w, "limit", "max", "quota", "allowed", "calls"))
            if length is None or not limit:
                continue
            if length <= MAX_WAIT_S:
                windows.append(Window(int(length * 1000), limit, tool))
                continue
            left = _number(_first(w, "remaining", "left", "calls_left", "available"))
            reset = _ms(_first(w, "resets_at", "reset_at", "reset", "resets", "reset_time"))
            if left is not None and reset is not None:
                budgets.append(Budget(left, 0, reset, tool, ""))
    return windows, budgets


def learn(workspace: Path, answer: Any, *, now_ms: int | None = None) -> Path | None:
    """Write `.trendsmesh/pace-limits.tsv` from a get_usage answer: its windows of a minute or less in place of the
    defaults of the same tool and length (the others kept), and its longer windows as budgets counted from now.
    Returns the file; None when the answer gives no limit (the old file, if any, is left as it is)."""
    windows, budgets = usage_limits(answer)
    if not windows and not budgets:
        return None
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    given = {(w.tool, w.ms) for w in windows}
    merged = windows + [Window(*d) for d in DEFAULTS if (d[2], d[0]) not in given]
    lines = [f"# the TrendsMesh limits the pacer keeps to, from the get_usage answer of "
             f"{datetime.fromtimestamp(now_ms / 1000, timezone.utc):%Y-%m-%d %H:%M} UTC (tm trends pace)"]
    lines += [f"window\t{w.ms}\t{w.limit}\t{w.tool}" for w in merged]
    for b in budgets:
        reset = f"{datetime.fromtimestamp(b.reset_ms / 1000, timezone.utc):%Y-%m-%d %H:%M} UTC"
        lines.append(f"budget\t{b.left}\t{now_ms}\t{b.reset_ms}\t{b.tool}\t{reset}")
    folder = Path(workspace) / DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / LIMITS
    tmp = folder / f"{LIMITS}.{os.getpid()}.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


# --- the log ----------------------------------------------------------------------------------

_T = re.compile(r'"t":(\d+)')
_K = re.compile(r'"tool":"([A-Za-z0-9_-]*)"')


def read_log(folder: Path) -> list[tuple[int, str]]:
    try:
        text = (folder / LOG).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        t, k = _T.search(line), _K.search(line)
        if t:
            out.append((int(t.group(1)), k.group(1) if k else ""))
    return out


def _write_log(folder: Path, entries: list[tuple[int, str]]) -> None:
    tmp = folder / f"{LOG}.{os.getpid()}.tmp"
    tmp.write_text("".join(f'{{"t":{t},"tool":"{k}"}}\n' for t, k in entries), encoding="utf-8")
    os.replace(tmp, folder / LOG)


def _keep(entries: list[tuple[int, str]], windows: list[Window], budgets: list[Budget], now: int) -> list[tuple[int, str]]:
    """The entries a later decision can still need: those inside the longest window, and those since the answer of a
    budget not reset yet."""
    since = now - max(w.ms for w in windows) - MARGIN_MS
    live = [b.since_ms for b in budgets if b.reset_ms > now]
    if live:
        since = min(since, min(live))
    return [e for e in entries if e[0] > since or e[0] >= now]


# --- the decision -----------------------------------------------------------------------------

def decide(entries: list[tuple[int, str]], windows: list[Window], budgets: list[Budget], now: int,
           tool: str) -> tuple[int | None, str]:
    """(the moment the call may go, "") or (None, why it may not go within MAX_WAIT_S)."""
    mine = [w for w in windows if _hit(w.tool, tool)]
    spent = [b for b in budgets if _hit(b.tool, tool)]

    def used(b: Budget) -> int:
        return sum(1 for t, k in entries if _hit(b.tool, k) and t >= b.since_ms)

    def fits(at: int) -> bool:
        for w in mine:
            if sum(1 for t, k in entries if _hit(w.tool, k) and abs(t - at) < w.ms + MARGIN_MS) >= w.limit:
                return False
        return all(not (at < b.reset_ms and used(b) >= b.left) for b in spent)

    moments = {now} | {t + w.ms + MARGIN_MS for t, k in entries for w in mine if _hit(w.tool, k)}
    moments |= {b.reset_ms + MARGIN_MS for b in spent}
    for at in sorted(m for m in moments if now <= m <= now + MAX_WAIT_S * 1000):
        if fits(at):
            return at, ""
    for b in spent:
        if now < b.reset_ms and used(b) >= b.left:
            return None, (f"TrendsMesh allows {max(b.left - used(b), 0)} more calls until {b.reset_text} (from the "
                          "latest get_usage answer), so this call was not made. Tell the user how many calls the pull "
                          "still needs, stop and wait for the reset, then continue from the same place and fetch only "
                          "what is not saved yet.")
    w = next((w for w in reversed(mine) if w.tool != "*"), mine[-1] if mine else None)
    rate = f"{w.limit} {'' if w.tool == '*' else tool + ' '}calls per {w.ms / 1000:g} s" if w else "its rate"
    return None, (f"This TrendsMesh call would have to wait more than {MAX_WAIT_S} s: TrendsMesh allows {rate}, and "
                  "this workspace has more calls than that queued already, so it was not made. Make it again in "
                  "about a minute, with at most 10 TrendsMesh calls at once; the run continues from the same place.")


# --- the hook ---------------------------------------------------------------------------------

def _lock(folder: Path, now_ms: Callable[[], int], sleep: Callable[[float], None]) -> Path:
    lock = folder / LOCK
    deadline = now_ms() + int(LOCK_WAIT_S * 1000)
    while True:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except (FileExistsError, IsADirectoryError, PermissionError):   # Windows: an older version's folder
            try:
                held = int((lock / "t" if lock.is_dir() else lock).read_text(encoding="utf-8") or 0)
            except (OSError, ValueError):
                held = 0
            if now_ms() > deadline + 1000:     # it cannot be taken over (a folder that refuses): the call goes
                raise TimeoutError(f"{lock} could not be taken")
            if (held and now_ms() - held > STALE_LOCK_MS) or now_ms() > deadline:
                _unlock(lock)                  # its owner was killed: take it
                continue
            sleep(0.02)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(now_ms()))
        return lock


def _unlock(lock: Path) -> None:
    try:
        if lock.is_dir():                      # an older version's folder
            (lock / "t").unlink(missing_ok=True)
            lock.rmdir()
        else:
            lock.unlink(missing_ok=True)
    except OSError:
        pass


def deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def pace(event: dict, *, now_ms: Callable[[], int] | None = None,
         sleep: Callable[[float], None] = time.sleep) -> dict | None:
    """One PreToolUse event: books the call's moment and sleeps until it (None), or the deny answer."""
    now_ms = now_ms or (lambda: int(time.time() * 1000))
    cwd = event.get("cwd")
    folder = workspace_for(Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()) / DIR
    folder.mkdir(parents=True, exist_ok=True)
    tool = short_name(event.get("tool_name"))
    lock = _lock(folder, now_ms, sleep)
    try:
        windows, budgets = read_limits(folder)
        now = now_ms()
        entries = read_log(folder)
        at, why = decide(entries, windows, budgets, now, tool)
        kept = _keep(entries, windows, budgets, now)
        if at is not None:
            kept.append((at, tool))
        _write_log(folder, kept)
    finally:
        _unlock(lock)
    if at is None:
        return deny(why)
    if at > now:
        sleep((at - now) / 1000)
    return None


def status(workspace: Path, now: int | None = None) -> dict:
    folder = Path(workspace) / DIR
    now = int(time.time() * 1000) if now is None else now
    windows, budgets = read_limits(folder)
    entries = read_log(folder)
    return {"workspace": str(workspace), "log": (folder / LOG).as_posix(),
            "from_get_usage": (folder / LIMITS).is_file(),
            "windows": [{"ms": w.ms, "limit": w.limit, "tool": w.tool,
                         "booked": sum(1 for t, k in entries if _hit(w.tool, k) and abs(t - now) < w.ms + MARGIN_MS)}
                        for w in windows],
            "budgets": [{"left": max(b.left - sum(1 for t, k in entries if _hit(b.tool, k) and t >= b.since_ms), 0),
                         "tool": b.tool, "until": b.reset_text} for b in budgets if b.reset_ms > now]}


# --- command line -----------------------------------------------------------------------------

def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("pace", help="pace TrendsMesh calls to the plan's limits: the PreToolUse hook (one event on "
                                    "stdin), or --status")
    p.add_argument("--event", help="read the event from this file instead of stdin")
    p.add_argument("--status", action="store_true", help="the limits in use and the calls booked, instead of a hook")
    p.add_argument("--workspace", help="with --status: the workspace (default: the current one)")
    p.add_argument("--json", action="store_true")


def run_pace(args: argparse.Namespace) -> int:
    if args.status:
        got = status(Path(args.workspace) if args.workspace else paths.workspace())
        lines = [f"{w['tool'] if w['tool'] != '*' else 'every tool'}: {w['limit']} per {w['ms'] / 1000:g} s, "
                 f"{w['booked']} booked now" for w in got["windows"]]
        lines += [f"{b['tool'] if b['tool'] != '*' else 'every tool'}: {b['left']} left until {b['until']}"
                  for b in got["budgets"]]
        source = "the latest get_usage answer" if got["from_get_usage"] else "the plan limits the plugin assumes"
        text = f"TrendsMesh calls are paced to {source}:\n" + "\n".join(lines)
        cli.emit(args, {"status": "done", **got, "message": text}, text)
        return 0
    try:
        raw = Path(args.event).read_bytes() if args.event else sys.stdin.buffer.read()
        event = json.loads(raw.decode("utf-8-sig"))
        result = pace(event) if isinstance(event, dict) else None
    except Exception:  # noqa: BLE001 - the pacer never fails a tool call: the call goes unpaced
        result = None
    if result is not None:
        print(json.dumps(result))
    return 0
