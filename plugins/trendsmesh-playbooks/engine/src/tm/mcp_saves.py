"""The Meta reads and artifacts answers of a creative brief run, and the artifacts answers of an
organic video run, saved by the collector.

The artifacts answers come from the Claude desktop app's built-in `Artifact` tool (a page's
publish) and `ArtifactData` tool (a read of its database: `list` and `query` are saved as `db_list`
and `db_query`, where the page's reader looks), or from the older artifacts MCP tools
(`publish_files`, `db_list`, ...), which some hosts still have. Only these actions are kept (`where`):
an `Artifact` read or list, an asset upload, a database write is never saved.

HANDOFF §4 asks for every MCP response to be saved (plan Decision 10). `trend_spool.handle` hands
each answer of a `SAVES` tool that the run's playbook keeps (`SAVED_BY`) to `save`, under the run's
lock, and returns nothing, so Claude sees the answer unchanged. Any other run ignores these tools.

Each answer is written in PB04's envelope `{"_tool", "_input", "_at", "answer"}` as a new version
`<folder>/<tool>_vNN.json`, never over an earlier one, with a manifest row. Later steps read them
by their `_input` (the audience order, the near-duplicate check, the page's decisions).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tm import manifest
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO
from tm.runfolder import RunFolder

META = "01_base/meta"
DECISIONS = "03_wip/decisions"
PUBLISH = "03_wip/publish"

SAVES: dict[str, tuple[str, str]] = {
    "ads_get_ad_accounts": (META, "ads_get_ad_accounts"),
    "ads_get_ad_entities": (META, "ads_get_ad_entities"),
    "ads_get_creatives": (META, "ads_get_creatives"),
    "db_list": (DECISIONS, "db_list"),
    "db_query": (DECISIONS, "db_query"),
    "publish_files": (PUBLISH, "publish_files"),
    "read_declaration": (PUBLISH, "read_declaration"),
    "declare_capabilities": (PUBLISH, "declare_capabilities"),
    "ArtifactData": (DECISIONS, "db_list"),          # by its action: `ACTIONS`
    "Artifact": (PUBLISH, "artifact_publish"),
}
# The built-in tools save some of their actions only, each under the stem the readers look for.
ACTIONS: dict[str, dict[str | None, str]] = {
    "ArtifactData": {"list": "db_list", "query": "db_query"},
    "Artifact": {None: "artifact_publish", "publish": "artifact_publish"},
}
BUILT_IN = tuple(ACTIONS)
_PAGES = ("db_list", "db_query", "publish_files", "read_declaration", "declare_capabilities", *BUILT_IN)

# Which of them each playbook's run keeps: an organic video run has pages and no Meta reads, so a
# Meta read never claims, or lands in, its marker.
SAVED_BY: dict[str, tuple[str, ...]] = {
    CREATIVE_BRIEF: tuple(SAVES),
    ORGANIC_VIDEO: _PAGES,
}

_SERVERS = {META: "Meta Ads", DECISIONS: "claude.ai artifacts", PUBLISH: "claude.ai artifacts"}


def where(tool: str, tool_input: Any = None) -> tuple[str, str] | None:
    """The folder and file stem an answer of `tool` (its short name) with this input is saved under,
    else None: a tool not in `SAVES`, or an action of a built-in tool that is not kept (`ACTIONS`;
    an `Artifact` publish of an asset is not the page's publish)."""
    found = SAVES.get(tool)
    if found is None or tool not in ACTIONS:
        return found
    given = tool_input if isinstance(tool_input, dict) else {}
    if tool_input is None or (tool == "Artifact" and given.get("asset")):
        return None
    stem = ACTIONS[tool].get(given.get("action"))
    return (found[0], stem) if stem else None


def kept_by(playbook: str | None, tool: str, tool_input: Any = None) -> bool:
    """Whether a run of `playbook` keeps this answer of `tool` (`SAVED_BY`, and `where` for a
    built-in tool's action)."""
    return tool in SAVED_BY.get(playbook or "", ()) and where(tool, tool_input) is not None


def server_of(tool_name: str) -> str | None:
    """The MCP server in a full tool name (`mcp__claude-artifacts__db_list` -> `claude-artifacts`),
    else None (a short name)."""
    name = str(tool_name)
    if not name.startswith("mcp__") or name.count("__") < 2:
        return None
    return name[len("mcp__"):].rsplit("__", 1)[0] or None


def save(run: RunFolder, tool: str, tool_input: dict, answer: Any, *, at: str | None = None,
         server: str | None = None) -> Path | None:
    """Save one answer of a `SAVES` tool (its short name) as the next `<folder>/<tool>_vNN.json`
    and add a manifest row; None for any other tool. `answer` is as `trend_spool.parse_answer` read
    it: a text that is not JSON (the db tools' summary, tagged documents and reminder) is
    `{"raw": text}`. The manifest names `server` (`server_of` the full tool name: the matcher takes
    any server's tool of these names), else the server the tool is expected from. The path is not
    reserved: the caller holds the run's lock."""
    if tool in SAVES and not isinstance(tool_input, dict):
        raise ValueError(f"{tool}'s input must be a JSON object.")
    found = where(tool, tool_input)
    if found is None:
        return None
    folder, stem = found
    at = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = run.next_version(folder, stem, "json")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"_tool": tool, "_input": tool_input, "_at": at, "answer": answer}
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")    # whole or not at all
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    rel = path.relative_to(run.path).as_posix()
    source = (f"claude.ai artifacts {tool}" if tool in BUILT_IN and not server
              else f"{server or _SERVERS[folder]} MCP {tool}")
    manifest.record(run, rel, rel.split("/", 1)[0], source, params=tool_input)
    return path
