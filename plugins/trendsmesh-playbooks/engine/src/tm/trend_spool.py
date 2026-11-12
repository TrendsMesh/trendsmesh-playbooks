"""The collector: a PostToolUse hook saves every TrendsMesh answer of a trend research, creative
brief or organic video run (`COLLECTING`), a creative brief run's Meta reads and artifacts answers,
and an organic video run's artifacts answers (`mcp_saves.SAVED_BY`).

    tm trends collect on|off --run RUN [--session ID] [--json]
    tm trends spool [--event FILE]           the hook's command: one event on stdin (or in FILE)
    tm trends ingest --run RUN --tool T --input JSON --file ANSWER [--json]

One marker per Claude Code session (issue #1): `collect on` writes
`<workspace>/.trendsmesh/collect/<session>.json` (`{"run", "since", "session"}`) for the session it
runs in, so several sessions in one workspace each collect into their own run. The session is
`--session`, else `CLAUDE_CODE_SESSION_ID`, which Claude Code sets for every command it runs to the
same id its hooks receive as `session_id`; without one `collect on` refuses, as nothing could tie
the answers to a session. A hook event is saved only into the run its own session's marker names: no
marker for the event's `session_id`, nothing saved, so a refresh-ad session in the same workspace
never sees summaries or feeds a run. `collect off` and `tm run new` for a `COLLECTING` playbook's run
remove this session's marker only (another playbook's `run new` leaves it); another session's
marker is never written or removed while its run is unfinished. A marker whose run is finished, or
gone, or that cannot be read is stale: the hook removes its own session's marker of a finished run,
and every `collect on` removes all stale ones, and the old one-per-workspace `.trendsmesh/collect.json`
(0.10.0 and earlier), which belongs to no session. `collect on|off` find the workspace from the run
folder, so they work from inside it too.

While its session's marker names an unfinished run of a `COLLECTING` playbook, the hook
(bootstrap/collect-mcp.sh, .ps1) hands each answer of that session that its matcher takes to
`spool`. A TrendsMesh or Ad Library answer is saved with `trends.save_answer` and, for a search, a
list or a video page in a known envelope (and never an error), `spool` prints a short summary that
Claude sees instead of the whole answer (`updatedToolOutput`, in the answer's own shape). Task 5's
spike proved both under `claude plugin eval` on Claude Code 2.1.319. A Meta read or an artifacts
answer (`mcp_saves.SAVES`) is saved by `mcp_saves.save` in a run whose playbook keeps that tool
(`mcp_saves.SAVED_BY`) and never replaced; in any other run it is ignored.

An answer too large for Claude Code to show reaches the hook as Claude Code's notice naming the file
it saved the answer to (issue #84): `spool` reads that file (`saved_by_claude_code`: only this
session's own tool-results folder, never a path an answer could plant), saves the answer with the
hook's tool input and summarises it as usual, so nothing is asked of Claude.

`spool` never fails a tool call. When an answer of the collecting session cannot be saved, Claude is
told (`additionalContext`: save it with `tm trends ingest`), a line goes to the run's
`02_research/collect_failures.log`, and the reason to `<data>/logs/collect.log`.
`ingest` saves an answer that reached the run without the hook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from tm import cli, mcp_saves, paths, playbooks, state, trends
from tm.runfolder import RunFolder

MARKERS = Path(".trendsmesh") / "collect"         # <session>.json: one marker per Claude Code session
LEGACY_MARKER = Path(".trendsmesh") / "collect.json"   # 0.10.0 and earlier: one per workspace, no session
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"           # Claude Code sets it for every command it runs
_SESSION = re.compile(r"[A-Za-z0-9_-]{1,128}")    # a file name, never a path
SUMMARISED = ("search_trends", "list_trends", "get_trend_videos")
LOCK = ".collect.lock"
WINDOWS = os.name == "nt"
FAILURES = Path(trends.RESEARCH) / "collect_failures.log"
STALE_LOCK_S = 5.0
COLLECTING = (playbooks.TREND_RESEARCH, playbooks.CREATIVE_BRIEF, playbooks.ORGANIC_VIDEO)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def short_name(tool_name: str) -> str:
    """`mcp__plugin_trendsmesh-playbooks_trendsmesh__get_trend` -> `get_trend`."""
    return str(tool_name).rsplit("__", 1)[-1]


SHARING_WAIT_S = 2.0


def _shared(do: Any) -> Any:
    """`do()`, again for up to SHARING_WAIT_S while Windows refuses it with PermissionError because
    another hook process has the file open at that moment (os.replace over an open file, or a read
    of a file being replaced). Elsewhere the first try is the only one."""
    deadline = time.monotonic() + SHARING_WAIT_S
    while True:
        try:
            return do()
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def _write_json(path: Path, data: Any) -> None:
    """Write whole or not at all: a temp file beside it, then os.replace."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _shared(lambda: os.replace(tmp, path))


# --- one writer at a time ---------------------------------------------------------------------

@contextmanager
def _locked(lock: Path, *, wait: float = 20.0) -> Iterator[None]:
    """An exclusive lock file. A lock older than STALE_LOCK_S (a save takes milliseconds) was left by
    a killed process: it is renamed aside first, so two waiters never both break it, and given back
    when it turns out to be a fresh one. The owner removes only its own lock."""
    deadline = time.monotonic() + wait
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            mine = os.fstat(fd).st_ino
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except PermissionError:
            # Windows: a lock its owner has just removed stays "delete pending" while another waiter
            # still holds it open for a stat, and creating it again is refused, not FileExistsError.
            if not WINDOWS:
                raise
            if time.monotonic() > deadline:
                raise TimeoutError(f"{lock.name} stayed locked for {wait:.0f} s") from None
            time.sleep(0.02)
        except FileExistsError:
            try:
                seen = lock.stat()
                if time.time() - seen.st_mtime > STALE_LOCK_S:
                    _break(lock, seen)
                    continue
            except OSError:
                pass                                  # gone already: try again
            if time.monotonic() > deadline:
                raise TimeoutError(f"{lock.name} stayed locked for {wait:.0f} s") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            if lock.stat().st_ino == mine:
                lock.unlink()
        except OSError:
            pass


def _break(lock: Path, seen: os.stat_result) -> None:
    aside = lock.with_name(f"{lock.name}.{os.getpid()}.{time.monotonic_ns()}")
    try:
        os.replace(lock, aside)
    except FileNotFoundError:
        return                                        # another waiter broke it
    try:
        now = aside.stat()
        if (now.st_ino, now.st_mtime_ns) != (seen.st_ino, seen.st_mtime_ns):
            try:
                os.link(aside, lock)                  # a fresh lock was taken meanwhile: give it back
            except OSError:
                pass
    finally:
        aside.unlink(missing_ok=True)


# --- the marker -------------------------------------------------------------------------------

def safe_session(value: Any) -> str | None:
    """A session id that can name a marker file (Claude Code's are UUIDs), else None."""
    return value if isinstance(value, str) and _SESSION.fullmatch(value) else None


def this_session() -> str | None:
    """The Claude Code session tm runs in: `CLAUDE_CODE_SESSION_ID`, the id its hooks receive as
    `session_id`; None outside Claude Code (or in a version that does not set it)."""
    return safe_session(os.environ.get(SESSION_ENV))


def marker_path(workspace: Path, session: str) -> Path:
    return Path(workspace) / MARKERS / f"{session}.json"


def find_workspace(start: Path, session: Any) -> Path | None:
    """`start` or the nearest folder above it that holds this session's marker (Claude may have gone
    into a run folder), else None; None for a session id that cannot name a marker."""
    session = safe_session(session)
    if session is None:
        return None
    start = Path(start)
    for folder in (start, *start.parents):
        if marker_path(folder, session).is_file():
            return folder
    return None


def _read_marker(marker: Path) -> dict:
    data = json.loads(_shared(lambda: marker.read_text(encoding="utf-8")))
    if not isinstance(data, dict) or not isinstance(data.get("run"), str) or not data["run"]:
        raise ValueError(f"{marker} does not name a run; turn collection on again with tm trends collect on.")
    return data


def _marker_or_none(marker: Path) -> dict | None:
    """The marker, or None when another process (collect off, run new) removed it after it was seen:
    then collection is off."""
    try:
        return _read_marker(marker)
    except FileNotFoundError:
        return None


def _names(ids: tuple[str, ...]) -> str:
    """"Trend research and Creative brief": the registry's names of those whose skill ships, joined."""
    names = [pb.name for pb in map(playbooks.get, ids) if playbooks.bundled(pb)] or [playbooks.get(ids[0]).name]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def active_run(workspace: Path, session: Any) -> RunFolder | None:
    """The run this session's marker names while it is an unfinished run of a `COLLECTING` playbook
    (trend research, creative brief, organic video), else None (no marker for this session, a
    finished run, a run of another playbook). The marker of a finished run is removed, so the hook
    stops starting Python for every later call. A run folder that is gone raises FileNotFoundError:
    the hook says so."""
    session = safe_session(session)
    if session is None:
        return None
    marker = marker_path(workspace, session)
    data = _marker_or_none(marker) if marker.is_file() else None
    if data is None:
        return None
    run = RunFolder.open(Path(workspace) / data["run"])
    s = state.load(run)
    if s.status == "done":
        marker.unlink(missing_ok=True)
        return None
    return run if s.playbook in COLLECTING else None


def _live(workspace: Path, marker: Path) -> dict | None:
    """The marker while its run is an unfinished run of a `COLLECTING` playbook; None when it is stale
    (unreadable, its run finished, gone or of another playbook). A run whose state cannot be read is
    left as live: only the run's own session finds out."""
    try:
        data = _read_marker(marker)
        run = RunFolder.open(Path(workspace) / data["run"])
    except (OSError, ValueError):
        return None
    try:
        s = state.load(run)
    except (OSError, ValueError):
        return data
    return data if s.status != "done" and s.playbook in COLLECTING else None


def _sessions(workspace: Path) -> list[Path]:
    folder = Path(workspace) / MARKERS
    return sorted(p for p in folder.glob("*.json") if safe_session(p.stem)) if folder.is_dir() else []


def prune(workspace: Path) -> None:
    """Remove every stale marker (a session that ended without collect off leaves one behind) and the
    old one-per-workspace marker, which belongs to no session. Live markers of other sessions stay."""
    (Path(workspace) / LEGACY_MARKER).unlink(missing_ok=True)
    for marker in _sessions(workspace):
        if _live(workspace, marker) is None:
            marker.unlink(missing_ok=True)


def others(workspace: Path, session: str) -> list[dict]:
    """The live markers of the other sessions in this workspace: [{"session", "run"}]."""
    out = []
    for marker in _sessions(workspace):
        data = _live(workspace, marker) if marker.stem != session else None
        if data is not None:
            out.append({"session": marker.stem, "run": data["run"]})
    return out


def collect_on(workspace: Path, run_path: Path, session: str) -> str:
    """Write this session's marker for this run (it replaces this session's own marker only), after
    removing stale ones; returns the run, workspace-relative."""
    if safe_session(session) is None:
        raise ValueError(f"{session!r} is not a Claude Code session id (letters, digits, - and _ only).")
    run = RunFolder.open(run_path)
    try:
        rel = run.path.resolve().relative_to(Path(workspace).resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{run.path} is not a run in this workspace ({workspace}).") from None
    s = state.load(run)
    if s.playbook not in COLLECTING:
        theirs = next((p.name for p in playbooks.all_playbooks() if p.id == s.playbook), s.playbook)
        raise ValueError(f"{run.path.name} is a run of {theirs}: Claude reads its TrendsMesh answers as "
                         f"they come, so they are not collected. Collection is only for runs of "
                         f"{_names(COLLECTING)}.")
    if s.status == "done":
        raise ValueError(f"{run.path.name} is finished, so nothing more is collected for it. Start the "
                         "next run with tm run new, then turn collection on for that run.")
    folder = Path(workspace) / MARKERS
    folder.mkdir(parents=True, exist_ok=True)
    with _locked(folder / LOCK):                 # one collect on, off or run new at a time
        prune(workspace)
        _write_json(marker_path(workspace, session), {"run": rel, "since": _now(), "session": session})
    return rel


def workspace_of(run: RunFolder) -> Path:
    """The workspace a run belongs to (<workspace>/runs/<playbook>/<run>), wherever tm is run from."""
    return run.path.resolve().parents[2]


def _marked(workspace: Path, session: str) -> Path | None:
    """The run folder this session's marker names, as written; None without a readable marker."""
    try:
        run = json.loads(marker_path(workspace, session).read_text(encoding="utf-8")).get("run")
    except (OSError, ValueError, AttributeError):
        return None
    return Path(workspace) / run if isinstance(run, str) and run else None


def turn_off(workspace: Path, session: str | None) -> bool:
    """Remove this session's marker, whichever run it names (`tm run new` for a `COLLECTING`
    playbook's run calls this), and the stale ones; another session's live marker stays. True if this
    session's marker was there. Without a session only stale markers go."""
    folder = Path(workspace) / MARKERS
    if not folder.is_dir():
        (Path(workspace) / LEGACY_MARKER).unlink(missing_ok=True)
        return False
    with _locked(folder / LOCK):
        prune(workspace)
        marker = marker_path(workspace, session) if safe_session(session) else None
        if marker is None or not marker.is_file():
            return False
        marker.unlink()
        return True


# --- reading an answer ------------------------------------------------------------------------

def _blocks(value: Any) -> bool:
    """MCP content blocks: a non-empty list of objects that each carry a `type`."""
    return isinstance(value, list) and bool(value) and all(
        isinstance(b, dict) and isinstance(b.get("type"), str) for b in value)


def _envelope(value: Any) -> bool:
    """An MCP tool result: `content` blocks and/or `structuredContent`."""
    return isinstance(value, dict) and (_blocks(value.get("content"))
                                        or isinstance(value.get("structuredContent"), (dict, list)))


def parse_answer(response: Any) -> tuple[Any, bool]:
    """The answer in a tool response, and whether it was JSON: a JSON text, a dict, a list, MCP
    content blocks whose text is JSON, or a tool result holding `structuredContent` or `content`
    blocks (an `isError` result becomes `{"error": ...}`). Anything else is `{"raw": ...}`, False."""
    if isinstance(response, str):
        try:
            value = json.loads(response)
        except ValueError:
            return {"raw": response}, False
        return parse_answer(value) if _blocks(value) or _envelope(value) else (value, True)
    if _envelope(response):
        inner = response.get("structuredContent")
        answer, parsed = (inner, True) if isinstance(inner, (dict, list)) else parse_answer(response["content"])
        return ({"error": answer}, parsed) if response.get("isError") is True else (answer, parsed)
    if _blocks(response):
        texts = [b["text"] for b in response if b["type"] == "text" and isinstance(b.get("text"), str)]
        if not texts:
            return {"raw": response}, False
        joined = "".join(texts)
        try:
            return json.loads(joined), True
        except ValueError:
            return {"raw": joined}, False
    if isinstance(response, (dict, list)):
        return response, True
    return {"raw": response}, False


# --- an answer too large to show (issue #84) --------------------------------------------------
#
# Claude Code shows no MCP answer over its limit. It saves the answer to a file and passes, as the tool's
# output (and as the hook's tool_response), only a notice naming that file. Claude Code 2.1.229 to 2.1.317
# write it as, the first line:
#   Error: result (143,210 characters across 1 line) exceeds maximum allowed tokens. Output has been saved
#   to <config>/projects/<project>/<session>/tool-results/mcp-<server>-<tool>-<ms>.txt.
# then "Format: Plain text" (the answer's text) or, in older versions, "Format: JSON array ..." (its content
# blocks), and advice on reading it. The file is read only when the notice is the whole answer from its
# first character and names a regular file, not a link, directly in this session's own tool-results folder,
# named for this tool: no path an answer could plant elsewhere is ever read.

_TOO_LARGE = re.compile(r"Error: result \(\d[\d,]* characters(?: across \d[\d,]* lines?)?\) exceeds maximum "
                        r"allowed tokens\. Output has been saved to (?P<path>[^\n]+?)\.(?:\n|$)")
TOOL_RESULTS = "tool-results"
CONFIG_ENV = "CLAUDE_CONFIG_DIR"            # Claude Code's config folder, else ~/.claude
MAX_SAVED_BYTES = 64 * 1024 * 1024


def too_large_path(text: Any) -> str | None:
    """The file Claude Code's too-large notice names, when `text` is that notice; else None."""
    m = _TOO_LARGE.match(text) if isinstance(text, str) else None
    return m["path"] if m else None


def _own_folder(event: dict, session: str, folder: Path) -> bool:
    """Whether `folder` (resolved) is this session's tool-results folder: beside its transcript
    (<project>/<session>.jsonl -> <project>/<session>/tool-results), else in a project of Claude Code's
    config folder (`CLAUDE_CONFIG_DIR`, else ~/.claude), as an event may name no usable transcript."""
    if folder.name != TOOL_RESULTS or folder.parent.name != session:
        return False
    transcript = event.get("transcript_path")
    if isinstance(transcript, str) and transcript.endswith(".jsonl"):
        beside = Path(transcript).parent / session / TOOL_RESULTS
        if beside.is_dir() and beside.resolve() == folder:
            return True
    projects = Path(os.environ.get(CONFIG_ENV) or Path.home() / ".claude") / "projects"
    return projects.is_dir() and folder.parent.parent.parent == projects.resolve()


def saved_by_claude_code(event: dict, tool: str, text: Any) -> Path | None:
    """The file of a too-large answer, when `text` is Claude Code's notice naming a regular file (not a
    link) directly in this session's own tool-results folder, named `mcp-...-<tool>-<digits>.txt|.json`;
    else None."""
    named = too_large_path(text)
    session = safe_session(event.get("session_id"))
    if named is None or session is None:
        return None
    path = Path(named)
    if not path.is_absolute() or not re.fullmatch(rf"mcp-.+-{re.escape(tool)}-\d+\.(?:txt|json)", path.name):
        return None
    try:
        if path.is_symlink() or not path.is_file():
            return None
        real = path.resolve(strict=True)
        ok = _own_folder(event, session, real.parent) and real.stat().st_size <= MAX_SAVED_BYTES
    except OSError:
        return None
    return real if ok else None


def _raw_text(answer: Any) -> Any:
    return answer.get("raw") if isinstance(answer, dict) and set(answer) == {"raw"} else None


# --- the summary Claude sees ------------------------------------------------------------------

def summarisable(tool: str, answer: Any) -> bool:
    """Only a known envelope is ever replaced, and never an error: a search or list holds a `data`
    list, the live server's `trends` list (with its `total`) or the legacy `items`, a video page a
    `data` or `videos` list."""
    if tool not in SUMMARISED or not isinstance(answer, dict) or "error" in answer:
        return False
    keys = ("data", "videos") if tool == "get_trend_videos" else ("data", "trends", "items")
    return any(isinstance(answer.get(k), list) for k in keys)


def _number(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _card(card: dict) -> dict:
    match = card.get("match")
    if isinstance(match, dict):
        match = match.get("score")
    reach = card.get("reach") if isinstance(card.get("reach"), dict) else {}
    return {"id": card.get("id"), "kind": card.get("kind"), "name": card.get("name"),
            "match": _number(match), "creators": _number(reach.get("creators", card.get("creators"))),
            "status": card.get("status")}


def _more(answer: dict, tool_input: dict, page: Any, results: int) -> bool:
    """Whether a search or list has more pages: its `has_more`, else, in the live `{trends, total}`
    envelope, whether the pages so far (of the call's `limit`, else of this page's size) hold fewer
    cards than `total`. A page with no cards is the last."""
    if "has_more" in answer:
        return answer["has_more"] is True
    total = _number(answer.get("total"))
    if total is None or not results:
        return False
    size = tool_input.get("limit")
    size = size if isinstance(size, int) and not isinstance(size, bool) and size > 0 else results
    done = (page - 1) * size if isinstance(page, int) and not isinstance(page, bool) and page > 1 else 0
    return done + results < total


def summary(tool: str, tool_input: dict, answer: dict, saved_to: str) -> dict:
    """What Claude sees of a search, a list or a video page: where it is saved and the gist."""
    page = answer.get("page") if isinstance(answer.get("page"), int) else tool_input.get("page", 1)
    if tool == "get_trend_videos":
        vids, more = trends.videos(answer)
        vids = [v for v in vids if isinstance(v, dict)]
        dates = sorted(v["published"] for v in vids if isinstance(v.get("published"), str) and v["published"])
        return {"saved_to": saved_to, "trend_id": tool_input.get("trend_id"), "page": page,
                "videos": len(vids), "has_more": more, "newest": dates[-1] if dates else None,
                "oldest": dates[0] if dates else None,
                "creators_on_page": len({c for c in map(trends.creator_of, vids) if c})}
    cards = [c for c in trends.items(answer) if isinstance(c, dict)]
    out = {"saved_to": saved_to, "page": page, "results": len(cards),
           "has_more": _more(answer, tool_input, page, len(cards)), "cards": [_card(c) for c in cards]}
    total = _number(answer.get("total"))
    if total is not None:
        out = {**out, "total": total}
    if tool == "list_trends" and tool_input.get("sort") == "updated":
        out["oldest_updated_at"] = trends.oldest_updated_at(cards)   # page on until the previous run's date
    return out


def _shaped(response: Any, data: dict) -> Any:
    """`data` in the response's own shape (Claude Code drops a rewrite of another shape)."""
    text = json.dumps(data, ensure_ascii=False)
    block = [{"type": "text", "text": text}]
    if _envelope(response):
        out = {**response, "content": block}
        if "structuredContent" in response:
            out["structuredContent"] = data
        return out
    if _blocks(response):
        return block
    if isinstance(response, str):
        return text
    if isinstance(response, dict):
        return data
    return None


# --- saving -----------------------------------------------------------------------------------

def _save(run: RunFolder, tool: str, tool_input: Any, answer: Any) -> Path:
    with _locked(run.path / LOCK):
        return trends.save_answer(run, tool, tool_input, answer)


def _keep(run: RunFolder, tool: str, tool_input: Any, answer: Any, *, server: str | None = None) -> Path:
    """A Meta read or an artifacts answer of a creative brief run, under the same lock."""
    with _locked(run.path / LOCK):
        path = mcp_saves.save(run, tool, tool_input, answer, server=server)
    if path is None:
        raise ValueError(f"{tool} is not an answer the collector keeps.")
    return path


def _not_saved(reason: str, run: str | None = None, tool: str | None = None) -> dict:
    """The hook output that tells Claude an answer of the collecting session was not saved."""
    text = (f"This answer was not saved to the run ({reason}). Save it with "
            f"tm trends ingest --run {run or '<run folder>'} --tool {tool or '<tool name>'} "
            "--input <file with the tool's input> --file <file with this answer>; the run continues "
            "from the same place.")
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def _not_json(run: str, tool: str, tool_input: Any) -> dict:
    """The hook output for a TrendsMesh or Ad Library answer that is not JSON: Claude Code's notice in
    place of an answer too large to show whose file cannot be read (`saved_by_claude_code`), or the
    tool's plain-text message."""
    text = ("This answer was not saved to the run (it is not JSON, so it holds no trend or Ad Library data). "
            "If it is Claude Code's notice that the output was too large and saved to a file, save that file "
            f"whole with tm trends ingest --run {run} --tool {tool} --input <file with the tool's input> "
            f"--file <the file the notice names>; the tool's input was {json.dumps(tool_input, ensure_ascii=False)}. "
            "If it is the tool's own message (a limit, an outage), nothing was saved and the run continues from "
            "the same place.")
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def _failed(run: RunFolder, tool: str, reason: str) -> None:
    """One line in the run's collect_failures.log, for a later check to read."""
    try:
        with open(run.path / FAILURES, "a", encoding="utf-8") as fh:
            fh.write(f"{_now()}\t{tool}\t{' '.join(reason.split())}\n")
    except OSError:
        pass                                          # the message to Claude still says it


def handle(event: dict, workspace: Path) -> dict | None:
    """Save one PostToolUse event's answer into the run its own session collects for (the marker
    named by the event's `session_id`); an event of a session without a marker is never saved
    anywhere. Returns the hook output: the summary that replaces a search, a list or a video page; a
    note to Claude when the answer could not be saved; else None. A `mcp_saves.SAVES` tool is kept
    by `mcp_saves.save` in a run whose playbook keeps it (`mcp_saves.SAVED_BY`; None: Claude sees it
    unchanged), its answer as it came, and ignored in any other run, before `_save` could file it
    under 02_research/other/. Any other (TrendsMesh, Ad Library) answer that is not JSON is not saved:
    it is logged and Claude is told how to ingest the whole answer (`_not_json`); an isError result
    is the tool's answer and is saved."""
    session = safe_session(event.get("session_id"))
    if session is None or not marker_path(workspace, session).is_file():
        return None
    tool_name = event.get("tool_name", "")
    tool = short_name(tool_name)
    kept = tool in mcp_saves.SAVES
    if not kept and not str(tool_name).startswith("mcp__"):
        return None                                   # a built-in tool the collector does not keep (ArtifactComments)
    run = active_run(workspace, session)
    if run is None:
        return None
    given = event.get("tool_input") if event.get("tool_input") is not None else {}
    if kept and not mcp_saves.kept_by(state.load(run).playbook, tool, given):
        return None                                   # not this playbook's (a trend research run keeps no Meta read)
    tool_input = mcp_saves.own_input(given)            # never the desktop app's own keys (`__artifact*`)
    response = event.get("tool_response")
    try:
        answer, parsed = parse_answer(response)
        if kept:
            _keep(run, tool, tool_input, answer, server=mcp_saves.server_of(tool_name))
            return None
        big = None
        if not parsed and "error" not in answer:      # {"raw": ...}: a notice or a message, no data
            big = saved_by_claude_code(event, tool, _raw_text(answer))
            if big is not None:                       # Claude Code's notice: its file holds the answer
                answer, parsed = parse_answer(big.read_text(encoding="utf-8-sig"))
            if not parsed and "error" not in answer:
                reason = "the answer is not JSON (Claude Code's notice for a large answer, or the tool's message)"
                _failed(run, tool, reason)
                _log(f"{tool}: {reason}")
                return _not_json(run.path.relative_to(Path(workspace)).as_posix(), tool, tool_input)
        path = _save(run, tool, tool_input, answer)
    except (OSError, ValueError) as exc:              # TimeoutError is an OSError
        reason = f"{type(exc).__name__}: {exc}"
        _failed(run, tool, reason)
        _log(f"{tool}: {reason}")
        return _not_saved(str(exc), run.path.relative_to(Path(workspace)).as_posix(), tool)
    saved_to = path.relative_to(Path(workspace)).as_posix()
    shaped = _shaped(response, summary(tool, tool_input, answer, saved_to)) if summarisable(tool, answer) else None
    if shaped is not None:
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": shaped}}
    if big is not None:                               # Claude sees only the notice: say it is saved
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
            f"This answer was saved to the run ({saved_to}) from the file Claude Code saved it to, so there is "
            "nothing to ingest by hand. Read that file only for what this step needs from it.")}}
    return None


# --- command line -----------------------------------------------------------------------------

def add_parsers(sub: argparse._SubParsersAction) -> None:
    c = sub.add_parser("collect", help="save every TrendsMesh answer to a trend research, creative "
                                       "brief or organic video run (or stop)")
    c.add_argument("state", choices=("on", "off"))
    c.add_argument("--run", required=True, help="the run folder")
    c.add_argument("--session", help=f"the Claude Code session that collects (default: ${SESSION_ENV}, "
                                     "which Claude Code sets for every command it runs)")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("spool", help="the PostToolUse hook: one event on stdin")
    s.add_argument("--event", help="read the event from this file instead of stdin")
    i = sub.add_parser("ingest", help="save an answer that reached the run without the hook")
    i.add_argument("--run", required=True, help="the run folder")
    i.add_argument("--tool", required=True, help="the tool's name, short or full")
    i.add_argument("--input", required=True,
                   help="the tool's input: a JSON object or a file holding one (from here first, else in the run)")
    i.add_argument("--file", required=True, help="the answer as the tool gave it (from here first, else in the run)")
    i.add_argument("--json", action="store_true")


def _log(message: str) -> None:
    try:
        folder = paths.data_dir() / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "collect.log", "a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {' '.join(message.split())}\n")
    except (OSError, RuntimeError):
        pass                                          # no data folder: nowhere to say it


def _spool(args: argparse.Namespace) -> int:
    tool = "?"
    workspace = None
    try:
        raw = Path(args.event).read_bytes() if args.event else sys.stdin.buffer.read()
        event = json.loads(raw.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("the hook event is not a JSON object")
        tool = short_name(event.get("tool_name") or "?")
        cwd = event.get("cwd")
        workspace = find_workspace(Path(cwd) if isinstance(cwd, str) and cwd else paths.workspace(),
                                   event.get("session_id"))
        result = handle(event, workspace) if workspace else None
    except Exception as exc:  # noqa: BLE001 - the hook never fails a tool call; the log says why
        _log(f"{tool}: {type(exc).__name__}: {exc}")
        result = _not_saved(str(exc), tool=None if tool == "?" else tool) if workspace else None
    if result is not None:
        print(json.dumps(result))
    return 0


NO_SESSION = (f"Collection is tied to the Claude Code session that turns it on, and this command was given no "
              f"session: {SESSION_ENV} is not set (tm was not run by Claude Code, or by a version that does not "
              "set it) and there is no --session. Collection stays off, so no answer is saved to the run by "
              "itself: save each TrendsMesh or Ad Library answer with tm trends ingest, or update Claude Code "
              "and turn collection on again.")


def _session(args: argparse.Namespace) -> str:
    """--session, else this session (`CLAUDE_CODE_SESSION_ID`); ValueError without one."""
    if args.session is not None:
        if safe_session(args.session) is None:
            raise ValueError(f"--session {args.session!r} is not a Claude Code session id (letters, digits, "
                             "- and _ only).")
        return args.session
    session = this_session()
    if session is None:
        raise ValueError(NO_SESSION)
    return session


def _also_collecting(rel: str, theirs: list[dict]) -> str:
    """What collect on says about the other sessions collecting in this workspace."""
    same = [o for o in theirs if o["run"] == rel]
    other = sorted({Path(o["run"]).name for o in theirs if o["run"] != rel})
    text = (" Another session collects for this run too: its answers are saved to it as well." if same else "")
    if other:
        n = len([o for o in theirs if o["run"] != rel])
        text += (f" {n} other session{'s' if n > 1 else ''} collect{'' if n > 1 else 's'} in this workspace, "
                 f"each into its own run ({', '.join(other)}).")
    return text


def _collect(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        workspace = workspace_of(run)
        session = _session(args)
        if args.state == "on":
            here = paths.workspace().resolve()     # the hook looks for the marker from Claude's folder
            if here != workspace and workspace not in here.parents:
                raise ValueError(f"{run.path} is not a run in this workspace ({paths.workspace()}).")
            rel = collect_on(workspace, run.path, session)
            theirs = others(workspace, session)
            playbook = state.load(run).playbook
            brief = playbook == playbooks.CREATIVE_BRIEF
            also = (" Its Meta reads (01_base/meta) and page answers (03_wip/decisions, 03_wip/publish) "
                    "are saved too, and Claude sees them whole." if brief else
                    " Its page answers (03_wip/decisions, 03_wip/publish) are saved too, and Claude sees them whole."
                    if playbook in mcp_saves.SAVED_BY else "")
            payload = {"status": "done", "collecting": True, "run": Path(rel).name}
            if theirs:
                payload["other_sessions"] = [{"run": Path(o["run"]).name} for o in theirs]
            cli.emit(args, payload,
                     f"Collecting for {rel} in this Claude Code session: every TrendsMesh and Ad Library answer "
                     "of this session is saved to its 02_research folder, and searches, lists and video pages "
                     f"show Claude a short summary instead of the whole answer.{also} Answers of other sessions "
                     f"are never saved to it.{_also_collecting(rel, theirs)} Turn it off with tm trends collect off.")
            return 0
        name = run.path.resolve().name
        named = _marked(workspace, session)
        if named is not None and named.resolve() != run.path.resolve():
            cli.emit(args, {"status": "done", "collecting": True, "run": named.name},
                     f"Collection in this session is on for {named.name}, not {name}, so it is left on.")
            return 0
        if not turn_off(workspace, session):
            cli.emit(args, {"status": "none", "collecting": False, "run": name},
                     f"Collection was not on for {name} in this session: nothing was turned off.")
            return 0
        cli.emit(args, {"status": "done", "collecting": False, "run": name},
                 f"Collection is off: this session's TrendsMesh answers are no longer saved to {name}.")
        return 0
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


VIEWER_CHECK = ("This ArtifactData read was made with as_level, so it shows what a viewer sees, not the decisions saved "
                "on the page, and nothing was saved. Read the decisions with one unfiltered ArtifactData list without "
                "as_level, then save that read.")


def _ingest(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        given = args.input.strip()       # inline JSON, or a file: from here first, else in the run
        tool_input = cli.json_arg(given if given[:1] in ("{", "[") else str(run.given(given)))
        if not isinstance(tool_input, dict):
            raise ValueError("--input must be a JSON object, for example '{\"trend_id\": \"t1\"}'.")
        tool_input = mcp_saves.own_input(tool_input)
        answer, _ = parse_answer(run.given(args.file).read_text(encoding="utf-8-sig"))   # PowerShell writes a BOM
        tool = short_name(args.tool)
        playbook = state.load(run).playbook
        if tool == "ArtifactData" and mcp_saves.viewer_check(tool_input):
            raise ValueError(VIEWER_CHECK)
        if mcp_saves.kept_by(playbook, tool, tool_input) or mcp_saves.page_read(tool, tool_input):
            path = _keep(run, tool, tool_input, answer,     # where the collector would have kept it; a page's
                         server=mcp_saves.server_of(args.tool))   # read in any run, where its reader looks
        elif tool in mcp_saves.SAVES and playbook in mcp_saves.SAVED_BY:
            raise ValueError(f"{run.path.name} does not keep {tool} answers (a run of this playbook keeps "
                             f"{', '.join(mcp_saves.SAVED_BY[playbook])}), so nothing was saved.")
        else:
            path = _save(run, tool, tool_input, answer)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    rel = path.relative_to(run.path).as_posix()
    cli.emit(args, {"status": "done", "file": rel}, f"Saved to {rel} in {run.path.name}.")
    return 0


ACTIONS = {"collect": _collect, "spool": _spool, "ingest": _ingest}
