"""Write a case's earlier turns as a Claude Code session transcript, for `context.history_file`.

    python3 evals/_lib/make_history.py evals/<case>

Reads `<case>/history.json` and writes `<case>/history.jsonl`, which the harness resumes
(`claude --resume <file>`) before it sends the case's prompt as the next user turn. An eval case
has one user turn of its own; this is how a case starts after the agent has already shown
something and asked (the report-issue cases: the draft shown, the destination named, "shall I
send it?").

history.json is a list of turns:
    ["user", "<text>"]                                   a user message
    ["text", "<text>"]                                   an assistant message
    ["tool", "<tool_use id>", "<tool>", {input}, "<result text>"]   an assistant tool call and its result
    ["skill", "<tool_use id>", "<plugin>:<skill>"]       the Skill tool loading one of the plugin's skills:
                                                         its result, then the skill's SKILL.md body as the
                                                         harness injects it, read from the plugin at build time
                                                         (so rebuild the history after changing that skill)
Every "{draft}" in a string is replaced by the text of `<case>/draft.md`, the report the fixture
also saves in the workspace, so the shown text and the saved file are the same. The ids are fixed
(uuid5 of the session and the line), so the file only changes when the turns do.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]

SESSION = "7d3f1c2a-5b6e-4a8d-9c0f-1e2d3c4b5a60"
CWD = "/tmp/eval-workspace"
VERSION = "2.1.319"
MODEL = "claude-opus-5-5"


def build(turns: list) -> str:
    records: list[dict] = []
    parent = None

    def base(kind: str) -> dict:
        n = len(records)
        return {"parentUuid": parent, "isSidechain": False, "userType": "external", "cwd": CWD,
                "sessionId": SESSION, "version": VERSION, "type": kind,
                "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{SESSION}/{n}")),
                "timestamp": f"2026-11-11T09:{30 + n // 60:02d}:{n % 60:02d}.000Z"}

    def assistant(content: list, stop: str) -> dict:
        rec = base("assistant")
        rec["message"] = {"id": f"msg_hist_{len(records):03d}", "type": "message", "role": "assistant",
                          "model": MODEL, "content": content, "stop_reason": stop, "stop_sequence": None,
                          "usage": {"input_tokens": 0, "output_tokens": 0}}
        return rec

    for turn in turns:
        if turn[0] == "user":
            rec = base("user")
            rec["message"] = {"role": "user", "content": turn[1]}
        elif turn[0] == "text":
            rec = assistant([{"type": "text", "text": turn[1]}], "end_turn")
        elif turn[0] == "tool":
            _, tool_id, name, tool_input, result = turn
            rec = assistant([{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}], "tool_use")
            records.append(rec)
            parent = rec["uuid"]
            rec = base("user")
            rec["message"] = {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": result, "is_error": False}]}
            rec["sourceToolAssistantUUID"] = parent
        elif turn[0] == "skill":
            _, tool_id, skill = turn
            rec = assistant([{"type": "tool_use", "id": tool_id, "name": "Skill", "input": {"skill": skill}}],
                            "tool_use")
            records.append(rec)
            parent = rec["uuid"]
            rec = base("user")
            rec["message"] = {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": f"Launching skill: {skill}",
                 "is_error": False}]}
            rec["sourceToolAssistantUUID"] = parent
            records.append(rec)
            parent = rec["uuid"]
            folder = PLUGIN / "skills" / skill.split(":", 1)[-1]
            text = (folder / "SKILL.md").read_text(encoding="utf-8")
            body = text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text
            rec = base("user")
            rec["isMeta"] = True
            rec["message"] = {"role": "user", "content": [
                {"type": "text", "text": f"Base directory for this skill: ${{CLAUDE_PLUGIN_ROOT}}/skills/{folder.name}\n\n{body}"}]}
        else:
            raise SystemExit(f"unknown turn kind {turn[0]!r}")
        records.append(rec)
        parent = rec["uuid"]
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def _fill(node: object, draft: str) -> object:
    if isinstance(node, str):
        return node.replace("{draft}", draft)
    if isinstance(node, list):
        return [_fill(item, draft) for item in node]
    if isinstance(node, dict):
        return {key: _fill(value, draft) for key, value in node.items()}
    return node


def main() -> int:
    case = Path(sys.argv[1])
    turns = json.loads((case / "history.json").read_text(encoding="utf-8"))
    draft_file = case / "draft.md"
    if draft_file.exists():
        turns = _fill(turns, draft_file.read_text(encoding="utf-8"))
    (case / "history.jsonl").write_text(build(turns), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
