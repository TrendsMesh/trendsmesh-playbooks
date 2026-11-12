"""tm.trend_spool: the PostToolUse collector saves every TrendsMesh answer of a trend research run.

Events are built in the shape Task 5's spike recorded under `claude plugin eval` (Claude Code
2.1.319): the full tool name `mcp__plugin_trendsmesh-playbooks_trendsmesh__<tool>`, the session's
`cwd`, and `tool_response` as MCP content blocks `[{"type": "text", "text": <the answer's JSON>}]`.
"""

import io
import json
import sys
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tm import manifest, state, trend_spool, trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder

PLUGIN = Path(__file__).resolve().parents[2]
MOCK_VIDEOS = PLUGIN / "evals" / "mocks" / "trendsmesh" / "fixtures" / "videos_trend_example_01.json"
FULL = "mcp__plugin_trendsmesh-playbooks_trendsmesh__"
RUN_REL = "runs/04-trend-research/2026-11-07_beauty"


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace with one trend research run; the data folder (for collect.log) beside it."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(workspace))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    RunFolder.create(workspace, "beauty", date(2026, 11, 7), playbook=TREND_RESEARCH)
    return workspace


def _on(ws: Path, capsys) -> None:
    assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL), "--json"]) == 0
    capsys.readouterr()


def _marker(ws: Path, session: str = "s1", run: str = RUN_REL, since: str | None = None) -> Path:
    """A session's marker, written as `tm trends collect on` writes it."""
    path = trend_spool.marker_path(ws, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run": run, "since": since or trend_spool._now(), "session": session}),
                    encoding="utf-8")
    return path


def _read_marker(ws: Path, session: str = "s1") -> dict:
    return json.loads(trend_spool.marker_path(ws, session).read_text(encoding="utf-8"))


def _event(ws: Path, tool: str, tool_input: dict, answer, *, prefix: str = FULL, cwd: Path | None = None,
           session: str = "s1") -> dict:
    text = answer if isinstance(answer, str) else json.dumps(answer)
    return {"session_id": session, "transcript_path": "/t.jsonl", "cwd": str(cwd or ws),
            "permission_mode": "default", "hook_event_name": "PostToolUse", "tool_name": prefix + tool,
            "tool_input": tool_input, "tool_response": [{"type": "text", "text": text}],
            "tool_use_id": "toolu_1", "mcp_server": {"name": "plugin:trendsmesh-playbooks:trendsmesh",
                                                     "source": "dynamic"}}


def _spool(monkeypatch, capsys, event) -> str:
    raw = event if isinstance(event, bytes) else json.dumps(event).encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8"))
    assert main(["trends", "spool"]) == 0
    return capsys.readouterr().out


def _summary(result: dict) -> dict:
    assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    blocks = result["hookSpecificOutput"]["updatedToolOutput"]
    assert isinstance(blocks, list) and len(blocks) == 1 and blocks[0]["type"] == "text"
    return json.loads(blocks[0]["text"])


def _saved(ws: Path) -> list[str]:
    research = ws / RUN_REL / "02_research"
    return sorted(p.relative_to(research).as_posix() for p in research.rglob("*") if p.is_file())


def test_no_marker_does_nothing(ws, monkeypatch, capsys):
    event = _event(ws, "get_trend_videos", {"trend_id": "t1"}, {"data": [], "page": 1, "has_more": False})
    assert trend_spool.handle(event, ws) is None
    assert _spool(monkeypatch, capsys, event) == ""
    assert _saved(ws) == []
    assert not (ws / ".trendsmesh").exists()


def test_videos_answer_saved_and_replaced_by_summary(ws, monkeypatch, capsys):
    _on(ws, capsys)
    page = {"data": [
        {"asset_id": "a1", "creator": "ann", "published": "2026-11-01T10:00:00Z", "views": 10},
        {"asset_id": "a2", "url": "https://www.tiktok.com/@bob/video/2", "published": "2026-10-20T08:00:00Z"},
        {"asset_id": "a3", "creator": " ann ", "published": None},
    ], "page": 2, "has_more": True}
    event = _event(ws, "get_trend_videos", {"trend_id": "t1", "page": 2}, page)
    summary = _summary(trend_spool.handle(event, ws))
    assert summary == {"saved_to": f"{RUN_REL}/02_research/videos/t1_p02.json", "trend_id": "t1", "page": 2,
                       "videos": 3, "has_more": True, "newest": "2026-11-01T10:00:00Z",
                       "oldest": "2026-10-20T08:00:00Z", "creators_on_page": 2}
    saved = json.loads((ws / summary["saved_to"]).read_text(encoding="utf-8"))
    assert saved["_tool"] == "get_trend_videos" and saved["_input"] == {"trend_id": "t1", "page": 2}
    assert saved["answer"] == page
    run = RunFolder.open(ws / RUN_REL)
    assert [r["source"] for r in manifest.rows(run)] == ["TrendsMesh MCP get_trend_videos"]
    assert [v["asset_id"] for v in trends.load_videos(run, "t1")] == ["a1", "a2", "a3"]

    # The mock's own page (the spike's answer), through the command the hook runs.
    mock = MOCK_VIDEOS.read_text(encoding="utf-8")
    out = _spool(monkeypatch, capsys, _event(ws, "get_trend_videos", {"trend_id": "trend_example_01"}, mock))
    summary = _summary(json.loads(out))
    assert summary["saved_to"] == f"{RUN_REL}/02_research/videos/trend_example_01_p01.json"
    assert summary["videos"] == 5 and summary["has_more"] is False and summary["page"] == 1
    assert summary["creators_on_page"] == 0                      # the mock carries no creator
    assert len(out) < len(mock) / 3


def test_search_answer_summary_lists_cards_with_match(ws, monkeypatch, capsys):
    _on(ws, capsys)
    answer = {"data": [
        {"id": "t1", "kind": "topic_trend", "name": "Glass skin", "status": "confirmed",
         "match": {"score": 62.5, "why": "close"}, "reach": {"videos": 40, "creators": 35},
         "what_it_is": "x" * 2000},
        {"id": "t2", "kind": "hook_trend", "name": "POV: ___", "status": "emerging"},
    ], "has_more": True}
    out = _spool(monkeypatch, capsys, _event(ws, "search_trends", {"about": "skin care", "limit": 50}, answer))
    summary = _summary(json.loads(out))
    assert summary == {"saved_to": f"{RUN_REL}/02_research/search/search_skin_care.json", "page": 1, "results": 2,
                       "has_more": True, "cards": [
                           {"id": "t1", "kind": "topic_trend", "name": "Glass skin", "match": 62.5,
                            "creators": 35, "status": "confirmed"},
                           {"id": "t2", "kind": "hook_trend", "name": "POV: ___", "match": None,
                            "creators": None, "status": "emerging"}]}
    assert "x" * 100 not in out
    assert trends.pool(RunFolder.open(ws / RUN_REL))["t1"]["found_by"] == {"skin care": 62.5}

    lst = _summary(trend_spool.handle(_event(ws, "list_trends", {"sort": "rising", "page": 3},
                                             {"data": answer["data"][:1]}), ws))
    assert lst["saved_to"] == f"{RUN_REL}/02_research/lists/list_rising_all_p03.json"
    assert lst["page"] == 3 and lst["results"] == 1 and lst["has_more"] is False and lst["cards"][0]["creators"] == 35
    assert "oldest_updated_at" not in lst                                  # only a list sorted updated pages by date


def test_updated_list_summary_says_its_oldest_card(ws, capsys):
    """The updated list is paged until its oldest card reaches the previous run's date: the summary says
    that card's updated_at (null when no card carries one)."""
    _on(ws, capsys)
    cards = [{"id": "t1", "kind": "topic_trend", "name": "A", "updated_at": "2026-11-05T10:00:00Z"},
             {"id": "t2", "kind": "topic_trend", "name": "B", "updated_at": "2026-10-30T08:00:00+00:00"},
             {"id": "t3", "kind": "topic_trend", "name": "C", "updated_at": "not a date"},
             {"id": "t4", "kind": "topic_trend", "name": "D"}]
    got = _summary(trend_spool.handle(_event(ws, "list_trends", {"sort": "updated", "limit": 50},
                                             {"data": cards, "page": 1, "has_more": True}), ws))
    assert got["oldest_updated_at"] == "2026-10-30T08:00:00+00:00" and got["has_more"] is True
    none = _summary(trend_spool.handle(_event(ws, "list_trends", {"sort": "updated", "page": 2},
                                              {"data": cards[2:], "page": 2, "has_more": True}), ws))
    assert none["oldest_updated_at"] is None


def test_get_trend_saved_not_replaced(ws, capsys):
    _on(ws, capsys)
    card = {"id": "t1", "kind": "topic_trend", "name": "Glass skin"}
    assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, card), ws) is None
    assert trend_spool.handle(_event(ws, "get_usage", {}, {"plan": "agent", "meters": []}), ws) is None
    ads = {"data": [{"ad_creative_bodies": ["Glow"]}]}
    assert trend_spool.handle(_event(ws, "ads_library_search", {"search_terms": "glow serum"}, ads,
                                     prefix="mcp__claude_ai_Meta_Ads__"), ws) is None
    files = _saved(ws)
    assert "trend_t1.json" in files and "ad_library/ads_glow_serum.json" in files
    assert any(f.startswith("usage/usage_") for f in files) and len(files) == 3
    run = RunFolder.open(ws / RUN_REL)
    assert trends.answer_of(run.path / "02_research" / "trend_t1.json") == card
    assert manifest.rows(run)[-1]["source"] == "Meta Ads MCP ads_library_search"


def test_same_phrase_twice_never_overwrites(ws, capsys):
    _on(ws, capsys)
    first = _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "nail art"}, {"data": [{"id": "a"}]}), ws))
    second = _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "nail art"}, {"data": [{"id": "b"}]}), ws))
    assert first["saved_to"].endswith("search/search_nail_art.json")
    assert second["saved_to"].endswith("search/search_nail_art_v02.json")
    assert trends.answer_of(ws / first["saved_to"]) == {"data": [{"id": "a"}]}
    assert trends.answer_of(ws / second["saved_to"]) == {"data": [{"id": "b"}]}


def test_done_run_or_pb01_run_is_ignored(ws, capsys):
    ad = RunFolder.create(ws, "ad", date(2026, 11, 7), playbook=REFRESH_AD)
    assert main(["trends", "collect", "on", "--run", str(ad.path), "--json"]) == 1
    # the three collecting playbooks are named, now that organic video's skill ships too
    message = json.loads(capsys.readouterr().out)["message"]
    assert "Collection is only for runs of Trend research, Creative brief and Organic AI video." in message
    _marker(ws, run="runs/01-refresh-ad/2026-11-07_ad")
    event = _event(ws, "get_trend_videos", {"trend_id": "t1"}, {"data": [], "page": 1, "has_more": False})
    assert trend_spool.handle(event, ws) is None
    assert not (ad.path / "02_research" / "videos").exists()

    _on(ws, capsys)
    run = RunFolder.open(ws / RUN_REL)
    s = state.load(run)
    s.status = "done"
    state.save(run, s)
    assert trend_spool.handle(event, ws) is None
    assert _saved(ws) == []
    assert main(["trends", "collect", "on", "--run", str(run.path), "--json"]) == 1
    assert "finished" in json.loads(capsys.readouterr().out)["message"]


TOO_LARGE = ("Error: result (64,537 characters) exceeds maximum allowed tokens. Output has been saved to "
             "/home/u/.claude/projects/p/tool-results/mcp-trendsmesh-search_trends-1.txt")


@pytest.mark.parametrize("tool, prefix, tool_input, text", [
    ("search_trends", FULL, {"about": "nails"}, TOO_LARGE),      # Claude Code's notice for a large answer
    ("get_trend", FULL, {"trend_id": "t1"}, "Rate limit reached. Try again in a minute."),
    ("ads_library_search", "mcp__meta__", {"search_terms": "nails"}, TOO_LARGE),
])
def test_an_answer_that_is_not_json_is_not_saved_and_said(ws, tmp_path, monkeypatch, capsys, tool, prefix,
                                                           tool_input, text):
    """A TrendsMesh or Ad Library answer that is not JSON (Claude Code's "too large" notice in its place,
    or a tool's plain-text message) is no data: nothing saved, a line in collect_failures.log and
    collect.log, and Claude is told how to save the whole answer with tm trends ingest."""
    _on(ws, capsys)
    told = json.loads(_spool(monkeypatch, capsys, _event(ws, tool, tool_input, text, prefix=prefix)))
    note = told["hookSpecificOutput"]["additionalContext"]
    assert "updatedToolOutput" not in told["hookSpecificOutput"]
    assert note.startswith("This answer was not saved to the run (it is not JSON")
    assert f"tm trends ingest --run {RUN_REL} --tool {tool}" in note
    assert "--file <the file the notice names>" in note and json.dumps(tool_input) in note
    assert _saved(ws) == ["collect_failures.log"]
    failures = (ws / RUN_REL / trend_spool.FAILURES).read_text(encoding="utf-8").splitlines()
    assert [line.split("\t")[1] for line in failures] == [tool] and "not JSON" in failures[0]
    assert tool in (tmp_path / "data" / "logs" / "collect.log").read_text(encoding="utf-8")


def test_an_error_result_without_json_is_still_saved(ws, capsys):
    """An isError tool result is the tool's answer (an error), not a cut one: saved, as before."""
    _on(ws, capsys)
    event = {**_event(ws, "search_trends", {"about": "nails"}, {}),
             "tool_response": {"content": [{"type": "text", "text": "quota exceeded"}], "isError": True}}
    assert trend_spool.handle(event, ws) is None
    path = ws / RUN_REL / "02_research" / "search" / "search_nails.json"
    assert trends.answer_of(path) == {"error": {"raw": "quota exceeded"}}


def test_other_sessions_are_left_alone(ws, monkeypatch, capsys):
    """The marker belongs to the session that ran collect on (CLAUDE_CODE_SESSION_ID), from the start:
    an answer of any other session, or of none, is never saved, whichever reaches the hook first."""
    _on(ws, capsys)
    assert _read_marker(ws) == {"run": RUN_REL, "since": _read_marker(ws)["since"], "session": "s1"}
    other = _event(ws, "search_trends", {"about": "lashes"}, {"data": [{"id": "b"}]}, session="s2")
    assert trend_spool.handle(other, ws) is None                                # first, and still not saved
    assert _spool(monkeypatch, capsys, other) == ""
    assert _spool(monkeypatch, capsys, {**other, "session_id": None}) == ""
    mine = _event(ws, "search_trends", {"about": "nails"}, {"data": [{"id": "a"}]})
    assert _summary(trend_spool.handle(mine, ws))["results"] == 1
    assert _saved(ws) == ["search/search_nails.json"]
    assert sorted(p.name for p in (ws / trend_spool.MARKERS).iterdir()) == ["s1.json"]   # nothing claimed


def test_parallel_sessions_each_collect_into_their_own_run(ws, monkeypatch, capsys):
    """Issue #1: four sessions in one workspace. Each answer goes to the run its own session turned
    collection on for; a refresh-ad session's Meta read and a session that never turned it on are
    saved nowhere."""
    _on(ws, capsys)                                                             # s1: trend research
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "brief")
    brief = _brief_on(ws, capsys)                                               # brief: creative brief
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert _read_marker(ws)["run"] == RUN_REL                                   # s1's marker is untouched
    assert _read_marker(ws, "brief")["run"] == BRIEF_REL

    ads = {"data": [{"ad_creative_bodies": ["Glow"]}]}
    meta = "mcp__claude_ai_Meta_Ads__"
    assert trend_spool.handle(_event(ws, "ads_library_search", {"search_terms": "glow"}, ads, prefix=meta,
                                     session="brief"), ws) is None
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "nails"}, {"data": []}), ws))[
        "saved_to"] == f"{RUN_REL}/02_research/search/search_nails.json"
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "serum"}, {"data": []},
                                              session="brief"), ws))[
        "saved_to"] == f"{BRIEF_REL}/02_research/search/search_serum.json"
    for session in ("refresh", "s1"):            # a refresh-ad session; the trend research run keeps no Meta read
        assert trend_spool.handle(_event(ws, "ads_get_ad_entities", {"level": "ad"}, {"data": []}, prefix=meta,
                                         session=session), ws) is None
    assert trend_spool.handle(_event(ws, "ads_get_ad_entities", {"level": "ad"}, {"data": []}, prefix=meta,
                                     session="brief"), ws) is None
    assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, {"id": "t1"}, session="video"), ws) is None

    assert _saved(ws) == ["search/search_nails.json"]
    brief_files = sorted(p.relative_to(brief.path).as_posix() for p in brief.path.rglob("*.json")
                         if p.name != "run.json")
    assert brief_files == ["01_base/meta/ads_get_ad_entities_v01.json", "02_research/ad_library/ads_glow.json",
                           "02_research/search/search_serum.json"]


def test_collect_on_says_which_other_sessions_collect(ws, monkeypatch, capsys):
    """collect on never takes or overwrites another session's marker, and says who else collects here."""
    _on(ws, capsys)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "brief")
    run = RunFolder.create(ws, "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    assert main(["trends", "collect", "on", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()
    assert main(["trends", "collect", "on", "--run", str(run.path)]) == 0
    text = capsys.readouterr().out
    assert "1 other session collects in this workspace, each into its own run (2026-11-07_beauty)" in text
    assert _read_marker(ws)["run"] == RUN_REL and _read_marker(ws, "brief")["run"] == BRIEF_REL
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "again")                      # a second session on the same run
    assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL)]) == 0
    assert "Another session collects for this run too" in capsys.readouterr().out
    assert _read_marker(ws)["run"] == RUN_REL


def test_collect_on_without_a_session_refuses(ws, monkeypatch, capsys):
    """No session id (not run by Claude Code, or an older one): collection cannot be tied to a session, so
    it is refused instead of collecting for whichever session answers first. --session names one."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL), "--json"]) == 1
    message = json.loads(capsys.readouterr().out)["message"]
    assert "CLAUDE_CODE_SESSION_ID" in message and "--session" in message and "tm trends ingest" in message
    assert not (ws / trend_spool.MARKERS).exists()
    for bad in ("../../etc", "a b", ""):
        assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL), "--session", bad, "--json"]) == 1
        capsys.readouterr()
    assert not (ws / trend_spool.MARKERS).exists()
    assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL), "--session", "abc-1", "--json"]) == 0
    capsys.readouterr()
    assert _read_marker(ws, "abc-1")["session"] == "abc-1"
    assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, {"id": "t1"}, session="abc-1"), ws) is None
    assert _saved(ws) == ["trend_t1.json"]


def test_an_event_with_an_unsafe_session_id_is_ignored(ws, capsys):
    _on(ws, capsys)
    for session in ("../s1", "s1/../s1", "", None, 7):
        assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, {"id": "t1"}, session=session), ws) is None
    assert _saved(ws) == []


def test_refresh_ad_session_in_the_same_workspace_is_not_replaced(ws, monkeypatch, capsys):
    _on(ws, capsys)
    trend_spool.handle(_event(ws, "get_usage", {}, {"plan": "agent"}), ws)       # the PB04 session
    ad = RunFolder.create(ws, "ad", date(2026, 11, 7), playbook=REFRESH_AD)
    answer = {"data": [{"id": "t1", "kind": "hook_trend", "what_it_is": "y" * 500}]}
    event = _event(ws, "search_trends", {"about": "hooks"}, answer, cwd=ad.path, session="refresh")
    assert _spool(monkeypatch, capsys, event) == ""
    assert not any(f.startswith("search/") for f in _saved(ws))
    assert not (ad.path / "02_research" / "search").exists()


def test_resume_turns_collection_on_again_for_the_new_session(ws, monkeypatch, capsys):
    _on(ws, capsys)
    trend_spool.handle(_event(ws, "search_trends", {"about": "nails"}, {"data": []}), ws)
    later = _event(ws, "search_trends", {"about": "lashes"}, {"data": []}, session="resumed")
    assert trend_spool.handle(later, ws) is None
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "resumed")
    _on(ws, capsys)                                   # the skill does this on every resume
    assert _read_marker(ws, "resumed")["session"] == "resumed"
    assert _summary(trend_spool.handle(later, ws))["saved_to"].endswith("search/search_lashes.json")
    # the first session's own marker is its own: still on, for the same run
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "brows"}, {"data": []}), ws))


def test_errors_and_unknown_envelopes_are_saved_not_replaced(ws, capsys):
    _on(ws, capsys)
    error = {"error": {"code": 429, "message": "Too many requests"}, "data": []}
    assert trend_spool.handle(_event(ws, "search_trends", {"about": "nails"}, error), ws) is None
    assert trend_spool.handle(_event(ws, "get_trend_videos", {"trend_id": "t1"}, {"error": "not found"}), ws) is None
    for answer in ([{"id": "a"}], {"results": [{"id": "a"}]}, {"message": "maintenance"}):
        assert trend_spool.handle(_event(ws, "list_trends", {}, answer), ws) is None
    assert trend_spool.handle(_event(ws, "get_trend_videos", {"trend_id": "t2"}, {"page": 1}), ws) is None
    research = ws / RUN_REL / "02_research"
    assert trends.answer_of(research / "search" / "search_nails.json") == error
    assert len([f for f in _saved(ws) if f.startswith("lists/")]) == 3
    # Known envelopes are: the legacy `items` for searches, REST `videos` for video pages.
    items = trend_spool.handle(_event(ws, "search_trends", {"about": "brows"}, {"items": [{"id": "c"}]}), ws)
    assert _summary(items)["results"] == 1
    rest = trend_spool.handle(_event(ws, "get_trend_videos", {"trend_id": "t3"},
                                     {"videos": [{"asset_id": "v"}], "page": 1, "pages": 1}), ws)
    assert _summary(rest)["videos"] == 1


def test_a_tool_result_envelope_is_unwrapped_and_kept_in_shape(ws):
    page = {"data": [{"asset_id": "a", "creator": "ann"}], "page": 1, "has_more": False}
    result = {"content": [{"type": "text", "text": json.dumps(page)}], "structuredContent": page}
    assert trend_spool.parse_answer(result) == (page, True)
    assert trend_spool.parse_answer({"content": [{"type": "text", "text": json.dumps(page)}]}) == (page, True)
    failed = {"content": [{"type": "text", "text": "quota exceeded"}], "isError": True}
    assert trend_spool.parse_answer(failed) == ({"error": {"raw": "quota exceeded"}}, False)

    _marker(ws)
    event ={**_event(ws, "get_trend_videos", {"trend_id": "t1"}, page), "tool_response": result}
    out = trend_spool.handle(event, ws)["hookSpecificOutput"]["updatedToolOutput"]
    assert set(out) == {"content", "structuredContent"} and out["structuredContent"]["videos"] == 1
    assert json.loads(out["content"][0]["text"]) == out["structuredContent"]
    assert trends.answer_of(ws / out["structuredContent"]["saved_to"]) == page
    event = {**event, "tool_response": failed}
    assert trend_spool.handle(event, ws) is None


def test_only_collecting_playbooks_collect(ws, capsys, playbook_two, bundled_skills):
    assert trend_spool.COLLECTING == (TREND_RESEARCH, CREATIVE_BRIEF, ORGANIC_VIDEO)
    two = RunFolder.create(ws, "two", date(2026, 11, 7), playbook=playbook_two)
    ad = RunFolder.create(ws, "ad", date(2026, 11, 7), playbook=REFRESH_AD)
    for other, name in ((two, "Playbook two"), (ad, "Refresh an ad")):
        assert main(["trends", "collect", "on", "--run", str(other.path), "--json"]) == 1
        message = json.loads(capsys.readouterr().out)["message"]
        assert f"is a run of {name}" in message
        assert message.endswith("Collection is only for runs of Trend research, Creative brief and Organic AI video.")
        _marker(ws, run=other.path.relative_to(ws).as_posix())
        assert trend_spool.active_run(ws, "s1") is None
        assert trend_spool.handle(_event(ws, "search_trends", {"about": "x"}, {"data": []}), ws) is None
        assert trend_spool.handle(_event(ws, "ads_get_creatives", {}, {"data": []},
                                         prefix="mcp__claude_ai_Meta_Ads__"), ws) is None
        assert not (other.path / "02_research" / "search").exists()
        assert not (other.path / "01_base" / "meta").exists()


BRIEF_REL = "runs/02-creative-brief/2026-11-07_ld"


def _brief_on(ws: Path, capsys) -> RunFolder:
    run = RunFolder.create(ws, "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    assert main(["trends", "collect", "on", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert {k: out[k] for k in ("status", "collecting", "run")} == {"status": "done", "collecting": True,
                                                                     "run": "2026-11-07_ld"}
    assert trend_spool.active_run(ws, os.environ["CLAUDE_CODE_SESSION_ID"]).path == run.path
    return run


def test_meta_answer_ignored_in_trend_research_run_before_save(ws, capsys, monkeypatch):
    _on(ws, capsys)
    saved, real = [], trend_spool._save
    monkeypatch.setattr(trend_spool, "_save", lambda *a: saved.append(a))
    for prefix, tool in (("mcp__claude_ai_Meta_Ads__", "ads_get_ad_accounts"),
                         ("mcp__claude_ai_Meta_Ads__", "ads_get_creatives"),
                         ("mcp__claude-artifacts__", "db_list"),
                         ("mcp__claude-artifacts__", "publish_files")):
        assert trend_spool.handle(_event(ws, tool, {}, {"data": []}, prefix=prefix), ws) is None
    assert saved == []                                  # ignored before _save, not filed under other/
    assert _saved(ws) == [] and not (ws / RUN_REL / "01_base" / "meta").exists()
    assert manifest.rows(RunFolder.open(ws / RUN_REL)) == []
    monkeypatch.setattr(trend_spool, "_save", real)
    assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, {"id": "t1"}), ws) is None
    assert _saved(ws) == ["trend_t1.json"]              # its TrendsMesh answers are still saved


def test_trendsmesh_answer_saved_and_summarised_in_brief_run(ws, capsys, monkeypatch):
    run = _brief_on(ws, capsys)
    answer = {"data": [{"id": "t1", "kind": "hook_trend", "name": "POV: ___", "what_it_is": "x" * 500}],
              "has_more": False}
    out = _spool(monkeypatch, capsys, _event(ws, "search_trends", {"about": "serum"}, answer))
    summary = _summary(json.loads(out))
    assert summary["saved_to"] == f"{BRIEF_REL}/02_research/search/search_serum.json"
    assert summary["results"] == 1 and "x" * 100 not in out
    page = {"data": [{"asset_id": "a1", "creator": "ann"}], "page": 1, "has_more": False}
    vids = _summary(trend_spool.handle(_event(ws, "get_trend_videos", {"trend_id": "t1"}, page), ws))
    assert vids["saved_to"] == f"{BRIEF_REL}/02_research/videos/t1_p01.json"
    assert [v["asset_id"] for v in trends.load_videos(run, "t1")] == ["a1"]
    assert trend_spool.handle(_event(ws, "get_trend", {"trend_id": "t1"}, {"id": "t1"}), ws) is None
    ads = {"data": [{"ad_creative_bodies": ["Glow"]}]}
    assert trend_spool.handle(_event(ws, "ads_library_search", {"search_terms": "glow serum"}, ads,
                                     prefix="mcp__claude_ai_Meta_Ads__"), ws) is None
    research = run.path / "02_research"
    assert (research / "trend_t1.json").is_file() and (research / "ad_library" / "ads_glow_serum.json").is_file()
    assert [r["source"] for r in manifest.rows(run)] == [
        "TrendsMesh MCP search_trends", "TrendsMesh MCP get_trend_videos", "TrendsMesh MCP get_trend",
        "Meta Ads MCP ads_library_search"]
    assert not (ws / RUN_REL / "02_research" / "search").exists()   # the trend research run got nothing


def test_brief_run_new_turns_collection_off(ws, monkeypatch, capsys, bundled_skills):
    """tm run new turns off only its own session's collection: a parallel session goes on collecting."""
    _brief_on(ws, capsys)
    _marker(ws, "other")                                 # another session collects for the trend research run
    assert main(["run", "new", "--playbook", "creative-brief", "--name", "ld2", "--json"]) == 0
    capsys.readouterr()
    assert not trend_spool.marker_path(ws, "s1").exists()
    meta = _event(ws, "ads_get_ad_accounts", {}, {"data": []}, prefix="mcp__claude_ai_Meta_Ads__")
    assert trend_spool.handle(meta, ws) is None
    assert not list(ws.glob("runs/02-creative-brief/*/01_base/meta"))
    assert _read_marker(ws, "other")["run"] == RUN_REL
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "x"}, {"data": []}, session="other"), ws))


def test_a_stale_lock_is_broken_and_a_fresh_one_waited_for(ws, capsys):
    _on(ws, capsys)
    lock = ws / RUN_REL / trend_spool.LOCK
    lock.write_text("99999999", encoding="utf-8")
    old = time.time() - trend_spool.STALE_LOCK_S - 1
    os.utime(lock, (old, old))
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "a"}, {"data": []}), ws))
    assert not lock.exists() and not list(lock.parent.glob(".collect.lock.*"))
    lock.write_text("1", encoding="utf-8")            # a live writer: wait, then give up
    with pytest.raises(TimeoutError):
        with trend_spool._locked(lock, wait=0.2):
            pass
    assert lock.read_text(encoding="utf-8") == "1"


def test_answer_shapes_are_read():
    blocks = [{"type": "text", "text": '{"data": [1]}'}]
    assert trend_spool.parse_answer(blocks) == ({"data": [1]}, True)
    assert trend_spool.parse_answer([{"type": "text", "text": '{"data": '}, {"type": "text", "text": "[1]}"}]) == \
        ({"data": [1]}, True)
    assert trend_spool.parse_answer('{"data": [2]}') == ({"data": [2]}, True)
    assert trend_spool.parse_answer(json.dumps(blocks)) == ({"data": [1]}, True)     # blocks saved as a file
    assert trend_spool.parse_answer({"data": [3]}) == ({"data": [3]}, True)
    assert trend_spool.parse_answer([{"id": "t1", "kind": "topic_trend"}]) == ([{"id": "t1", "kind": "topic_trend"}], True)
    assert trend_spool.parse_answer("not json") == ({"raw": "not json"}, False)
    assert trend_spool.parse_answer([{"type": "text", "text": "oops"}]) == ({"raw": "oops"}, False)
    image = [{"type": "image", "data": "AAAA", "mimeType": "image/png"}]
    assert trend_spool.parse_answer(image) == ({"raw": image}, False)
    assert trend_spool.parse_answer(None) == ({"raw": None}, False)


def test_run_new_turns_collection_off(ws, capsys, bundled_skills):
    _on(ws, capsys)
    assert trend_spool.marker_path(ws, "s1").is_file()
    assert main(["run", "new", "--playbook", "trend-research", "--name", "w2", "--json"]) == 0
    assert not trend_spool.marker_path(ws, "s1").exists()
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": []})
    assert trend_spool.handle(event, ws) is None
    assert _saved(ws) == []


def test_run_new_of_another_playbook_leaves_collection_on(ws, capsys, bundled_skills):
    _on(ws, capsys)
    assert main(["run", "new", "--playbook", REFRESH_AD, "--name", "ad", "--json"]) == 0
    capsys.readouterr()
    assert _read_marker(ws)["run"] == RUN_REL
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": []})
    assert _summary(trend_spool.handle(event, ws))["saved_to"].endswith("search/search_nails.json")


def test_a_marker_does_not_expire_with_time(ws):
    """The marker is its session's from collect on: a day later, the run going on, it still collects."""
    _marker(ws, since=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds"))
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": []})
    assert _summary(trend_spool.handle(event, ws))["saved_to"].endswith("search/search_nails.json")
    assert trend_spool.handle({**event, "session_id": "s2"}, ws) is None


def test_stale_markers_are_removed(ws, monkeypatch, capsys):
    """A marker whose run is finished or gone, or that cannot be read, collects nothing: the hook removes
    its own session's for a finished run (a gone one is said, test_failure_before_the_save_is_said_too),
    and any session's collect on removes every such one; live ones stay."""
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": []})
    run = RunFolder.open(ws / RUN_REL)
    done = RunFolder.create(ws, "old", date(2026, 10, 1), playbook=TREND_RESEARCH)
    s = state.load(done)
    s.status = "done"
    state.save(done, s)
    _marker(ws, run=done.path.relative_to(ws).as_posix())
    assert trend_spool.handle(event, ws) is None
    assert not trend_spool.marker_path(ws, "s1").exists()

    _marker(ws, "ended", run=done.path.relative_to(ws).as_posix())    # sessions that left their marker behind
    _marker(ws, "vanished", run="runs/04-trend-research/gone")
    trend_spool.marker_path(ws, "broken").write_text("{not json", encoding="utf-8")
    _marker(ws, "live")                                             # a session still at work
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "new")
    assert main(["trends", "collect", "on", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()
    assert sorted(p.name for p in (ws / trend_spool.MARKERS).iterdir()) == ["live.json", "new.json"]


def test_the_old_workspace_marker_is_ignored_and_removed(ws, capsys):
    """0.10.0's one marker per workspace (.trendsmesh/collect.json) belongs to no session: the hook never
    saves for it, and collect on (every run turns it on again on resuming) removes it."""
    legacy = ws / trend_spool.LEGACY_MARKER
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"run": RUN_REL, "since": trend_spool._now(), "session": "s1"}), encoding="utf-8")
    assert trend_spool.handle(_event(ws, "search_trends", {"about": "nails"}, {"data": []}), ws) is None
    assert _saved(ws) == []
    _on(ws, capsys)
    assert not legacy.exists() and _read_marker(ws)["run"] == RUN_REL


def test_a_marker_removed_before_it_is_read_is_collection_off(ws, tmp_path, monkeypatch, capsys):
    """Another process (collect off, run new) removes the marker after handle saw it."""
    real = trend_spool._read_marker

    def read(path):
        path.unlink()
        return real(path)

    monkeypatch.setattr(trend_spool, "_read_marker", read)
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": [{"id": "a"}]})
    _marker(ws)
    assert trend_spool.handle(event, ws) is None
    _marker(ws)
    assert _spool(monkeypatch, capsys, event) == ""                     # nothing replaced, nothing said
    assert not trend_spool.marker_path(ws, "s1").exists()
    assert _saved(ws) == []                                             # nothing saved
    assert not (tmp_path / "data" / "logs" / "collect.log").exists()


def test_run_new_succeeds_even_when_the_marker_cannot_be_removed(ws, capsys, bundled_skills, monkeypatch):
    def refuse(*_args, **_kw):
        raise PermissionError("read-only folder")
    monkeypatch.setattr(trend_spool, "turn_off", refuse)
    assert main(["run", "new", "--playbook", "trend-research", "--name", "w3", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"


def test_collect_on_off_and_answers_found_from_a_subfolder(ws, monkeypatch, capsys):
    assert main(["trends", "collect", "on", "--run", str(ws / RUN_REL), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["collecting"] is True and out["run"] == "2026-11-07_beauty"
    marker = _read_marker(ws)
    assert marker["run"] == RUN_REL and marker["since"] and marker["session"] == "s1"
    # Claude went into the run folder: the workspace is the nearest folder above with the marker.
    event = _event(ws, "search_trends", {"about": "nails"}, {"data": []}, cwd=ws / RUN_REL / "02_research")
    assert _summary(json.loads(_spool(monkeypatch, capsys, event)))["results"] == 0
    other = ws / "elsewhere"
    other.mkdir()
    assert main(["trends", "collect", "on", "--run", str(other), "--json"]) == 1
    assert "not a run folder" in json.loads(capsys.readouterr().out)["message"]

    second = RunFolder.create(ws, "second", date(2026, 11, 7), playbook=TREND_RESEARCH)
    assert main(["trends", "collect", "off", "--run", str(second.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["collecting"] is True          # another run's: left on
    assert trend_spool.marker_path(ws, "s1").is_file()
    _marker(ws, "s2")                                                          # another session's: never touched
    assert main(["trends", "collect", "off", "--run", str(ws / RUN_REL), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "collecting": False, "run": "2026-11-07_beauty"}
    assert not trend_spool.marker_path(ws, "s1").exists() and trend_spool.marker_path(ws, "s2").is_file()
    assert main(["trends", "collect", "off", "--run", str(ws / RUN_REL), "--json"]) == 0   # already off
    assert json.loads(capsys.readouterr().out)["status"] == "none"


def test_spool_never_fails_and_logs_why(ws, tmp_path, monkeypatch, capsys):
    _on(ws, capsys)
    bad = _event(ws, "get_trend_videos", {"trend_id": "../etc"}, {"data": []})
    told = json.loads(_spool(monkeypatch, capsys, bad))["hookSpecificOutput"]
    assert "updatedToolOutput" not in told
    assert told["additionalContext"].startswith("This answer was not saved to the run (")
    assert f"tm trends ingest --run {RUN_REL} --tool get_trend_videos" in told["additionalContext"]
    assert _spool(monkeypatch, capsys, b"{not json") == ""            # no event, no workspace: silent
    # a TrendsMesh tool the engine doesn't know yet is saved under a generic name, not refused
    assert _spool(monkeypatch, capsys, _event(ws, "get_topic_graph", {"trend_id": "t1"}, {"edges": []})) == ""
    log = (tmp_path / "data" / "logs" / "collect.log").read_text(encoding="utf-8")
    assert "trend_id" in log and "get_topic_graph" not in log and len(log.splitlines()) == 2
    saved = _saved(ws)
    assert saved[0] == "collect_failures.log" and len(saved) == 2 and saved[1].startswith("other/get_topic_graph_")
    failures = (ws / RUN_REL / trend_spool.FAILURES).read_text(encoding="utf-8").splitlines()
    assert [line.split("\t")[1] for line in failures] == ["get_trend_videos"]
    assert "trend_id" in failures[0]


def test_failure_before_the_save_is_said_too(ws, monkeypatch, capsys):
    _on(ws, capsys)
    _marker(ws, run="runs/04-trend-research/gone")
    out = json.loads(_spool(monkeypatch, capsys, _event(ws, "search_trends", {"about": "nails"}, {"data": []})))
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "not a run folder" in text and "tm trends ingest" in text and "--tool search_trends" in text
    assert _spool(monkeypatch, capsys, _event(ws, "search_trends", {"about": "x"}, {"data": []}, session="s2")) == ""


def test_ingest_saves_through_save_answer(ws, tmp_path, capsys):
    tool_input = tmp_path / "input.json"
    tool_input.write_text(json.dumps({"trend_id": "t9", "page": 1}), encoding="utf-8")
    answer = tmp_path / "answer.json"
    answer.write_text(json.dumps([{"type": "text", "text": json.dumps({"data": [{"asset_id": "z"}]})}]),
                      encoding="utf-8")
    assert main(["trends", "ingest", "--run", str(ws / RUN_REL), "--tool", FULL + "get_trend_videos",
                 "--input", str(tool_input), "--file", str(answer), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["file"] == "02_research/videos/t9_p01.json"
    run = RunFolder.open(ws / RUN_REL)
    assert [v["asset_id"] for v in trends.load_videos(run, "t9")] == ["z"]
    bom = tmp_path / "answer_bom.json"                  # Windows PowerShell's UTF-8 has a BOM
    bom.write_bytes(b"\xef\xbb\xbf" + json.dumps({"edges": [{"to": "t2"}]}).encode("utf-8"))
    bom_input = tmp_path / "input_bom.json"
    bom_input.write_bytes(b"\xef\xbb\xbf" + b'{"trend_id": "t2"}')
    assert main(["trends", "ingest", "--run", str(ws / RUN_REL), "--tool", "get_topic_graph",
                 "--input", str(bom_input), "--file", str(bom), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["file"].startswith("02_research/other/get_topic_graph_")
    assert trends.answer_of(run.path / out["file"]) == {"edges": [{"to": "t2"}]}


def test_collect_off_from_inside_the_run_folder(ws, monkeypatch, capsys):
    """`--run .` from inside the run: the workspace comes from the run, so the marker is found and
    removed; with no marker the answer says so instead of "off"."""
    run = ws / RUN_REL
    monkeypatch.delenv("TM_WORKSPACE")
    monkeypatch.chdir(run)
    assert main(["trends", "collect", "on", "--run", ".", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["collecting"] is True
    assert _read_marker(ws)["run"] == RUN_REL
    assert not (run / trend_spool.MARKERS).exists()
    assert main(["trends", "collect", "off", "--run", ".", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "collecting": False, "run": "2026-11-07_beauty"}
    assert not trend_spool.marker_path(ws, "s1").exists()
    assert main(["trends", "collect", "off", "--run", ".", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "none", "collecting": False, "run": "2026-11-07_beauty"}
    assert main(["trends", "collect", "off", "--run", "."]) == 0
    assert "Collection was not on for 2026-11-07_beauty in this session" in capsys.readouterr().out
    monkeypatch.chdir(ws.parent)                        # Claude works outside the run's workspace
    assert main(["trends", "collect", "on", "--run", str(run), "--json"]) == 1
    assert "not a run in this workspace" in json.loads(capsys.readouterr().out)["message"]


def test_answers_arriving_together_are_all_saved(ws, capsys):
    _on(ws, capsys)
    events = [_event(ws, "search_trends", {"about": "nail art"}, {"data": [{"id": str(i)}]}) for i in range(8)]
    threads = [threading.Thread(target=trend_spool.handle, args=(e, ws)) for e in events]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    files = [f for f in _saved(ws) if f.startswith("search/")]
    assert len(files) == 8
    ids = {trends.answer_of(ws / RUN_REL / "02_research" / f)["data"][0]["id"] for f in files}
    assert ids == {str(i) for i in range(8)}
    assert len(manifest.rows(RunFolder.open(ws / RUN_REL))) == 8


def test_marker_waits_while_windows_holds_it_open(ws, capsys, monkeypatch):
    """Windows refuses os.replace over a marker the hook is reading, and a read of a marker being
    replaced: collect on and the hook wait a moment instead of failing or losing the answer."""
    _on(ws, capsys)
    real_replace, real_read = os.replace, Path.read_text
    left = {"replace": 2, "read": 2}

    def busy_replace(src, dst):
        if Path(dst).name == "s1.json" and left["replace"]:
            left["replace"] -= 1
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    def busy_read(self, *a, **k):
        if self.name == "s1.json" and left["read"]:
            left["read"] -= 1
            raise PermissionError(13, "Permission denied")
        return real_read(self, *a, **k)

    monkeypatch.setattr(trend_spool.os, "replace", busy_replace)
    monkeypatch.setattr(Path, "read_text", busy_read)
    trend_spool.collect_on(ws, ws / RUN_REL, "s1")
    assert _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "a"}, {"data": []}), ws))
    assert left == {"replace": 0, "read": 0}
    assert json.loads(real_read(trend_spool.marker_path(ws, "s1"), encoding="utf-8"))["session"] == "s1"


def test_lock_waits_while_windows_finishes_removing_it(ws, capsys, monkeypatch):
    """On Windows, creating the lock just after its owner removed it can be refused (delete pending)
    instead of FileExistsError: the save waits a moment instead of losing the answer."""
    _on(ws, capsys)
    monkeypatch.setattr(trend_spool, "WINDOWS", True)
    real_open = os.open
    left = {"open": 2}

    def pending(path, flags, *a):
        if Path(path).name == trend_spool.LOCK and left["open"]:
            left["open"] -= 1
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, *a)

    monkeypatch.setattr(trend_spool.os, "open", pending)
    trend_spool.handle(_event(ws, "search_trends", {"about": "nail art"}, {"data": [{"id": "1"}]}), ws)
    assert left == {"open": 0}
    assert [f for f in _saved(ws) if f.startswith("search/")] == ["search/search_nail_art.json"]


def test_lock_refused_elsewhere_is_not_waited_on(tmp_path, monkeypatch):
    monkeypatch.setattr(trend_spool, "WINDOWS", False)

    def refused(path, flags, *a):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(trend_spool.os, "open", refused)
    with pytest.raises(PermissionError):
        with trend_spool._locked(tmp_path / trend_spool.LOCK, wait=5):
            pass


def test_marker_still_refused_after_the_wait(ws, capsys, monkeypatch):
    _on(ws, capsys)
    monkeypatch.setattr(trend_spool, "SHARING_WAIT_S", 0.05)

    def refused(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(trend_spool.os, "replace", refused)
    with pytest.raises(PermissionError):
        trend_spool.collect_on(ws, ws / RUN_REL, "s1")


def test_the_live_trends_envelope_is_summarised(ws, capsys):
    """Issue #54: the live search answers `{"trends": [...], "total": N}`. It is replaced by the summary, which says
    the total and whether more pages follow; an error in that envelope is still never replaced."""
    _on(ws, capsys)
    cards = [{"id": f"t{n}", "kind": "topic_trend", "name": f"T{n}", "status": "confirmed"} for n in range(3)]
    assert trend_spool.summarisable("search_trends", {"trends": cards, "total": 7})
    assert trend_spool.summarisable("list_trends", {"trends": [], "total": 0})
    assert not trend_spool.summarisable("search_trends", {"trends": cards, "error": "x"})
    assert not trend_spool.summarisable("get_trend_videos", {"trends": cards})
    got = _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "glass skin", "limit": 3},
                                             {"trends": cards, "total": 7}), ws))
    assert (got["results"], got["total"], got["has_more"]) == (3, 7, True)
    assert [c["id"] for c in got["cards"]] == ["t0", "t1", "t2"]
    last = _summary(trend_spool.handle(_event(ws, "search_trends", {"about": "glass skin", "limit": 3, "page": 3},
                                              {"trends": cards[:1], "total": 7}), ws))
    assert (last["page"], last["results"], last["has_more"]) == (3, 1, False)
    assert trend_spool.handle(_event(ws, "search_trends", {"about": "nails"},
                                     {"error": "not_in_plan", "trends": []}), ws) is None
