"""tm.trend_pace (issue #129, part 2): TrendsMesh calls are paced to the plan's limits, so none is refused.

The hook itself is bootstrap/pace-mcp.sh with pace.awk (tested in tests/bootstrap/test-bootstrap.sh); this is the
same rule in Python, and a check that the two decide alike. No MCP call is made: events and answers are fixtures.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tm import trend_pace, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder
from tm.trend_pace import Budget, Window

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks"
AWK = PLUGIN / "bootstrap" / "pace.awk"
NOW = 1_795_000_000_000
DEFAULT = [Window(*w) for w in trend_pace.DEFAULTS]


def _event(ws: Path, tool: str = "search_trends") -> dict:
    return {"session_id": "s", "cwd": str(ws), "hook_event_name": "PreToolUse",
            "tool_name": f"mcp__plugin_trendsmesh-playbooks_trendsmesh__{tool}", "tool_input": {}}


class Clock:
    """A fake clock: `sleep` moves it on, so a test of a minute takes no time."""

    def __init__(self, now: int = NOW):
        self.now = now
        self.slept: list[float] = []

    def ms(self) -> int:
        return self.now

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += int(s * 1000)


def test_a_call_that_fits_goes_now():
    assert trend_pace.decide([], DEFAULT, [], NOW, "search_trends") == (NOW, "")


def test_the_11th_search_of_a_minute_waits_for_the_first_to_leave():
    entries = [(NOW - 50_000 + i * 2000, "search_trends") for i in range(10)]     # 10 in the last 50 s
    at, why = trend_pace.decide(entries, DEFAULT, [], NOW, "search_trends")
    assert at == NOW - 50_000 + 60_000 + trend_pace.MARGIN_MS and why == ""
    # another tool is not held back by it
    assert trend_pace.decide(entries, DEFAULT, [], NOW, "get_trend")[0] == NOW


def test_ten_a_second_for_every_tool_and_booked_calls_keep_their_place():
    entries = [(NOW + 5000, "get_trend_videos")]                                  # booked 5 s from now
    entries += [(NOW - 100 + i, "get_trend") for i in range(9)]
    assert trend_pace.decide(entries, DEFAULT, [], NOW, "get_trend") == (NOW, "")
    entries.append((NOW - 10, "get_trend"))
    at, _ = trend_pace.decide(entries, DEFAULT, [], NOW, "get_trend")
    assert at == NOW - 100 + 1000 + trend_pace.MARGIN_MS                          # the first of the ten leaves
    # 20 video pages a minute, then the 21st waits; a page booked later than now still counts
    pages = [(NOW - 30_000 + i * 1000, "get_trend_videos") for i in range(19)] + [(NOW + 2000, "get_trend_videos")]
    at, _ = trend_pace.decide(pages, DEFAULT, [], NOW, "get_trend_videos")
    assert at == NOW - 30_000 + 60_000 + trend_pace.MARGIN_MS


def test_a_call_that_cannot_fit_within_a_minute_is_denied():
    entries = [(NOW + 5000 + i * 1000, "get_trend_videos") for i in range(20)]    # a minute's pages booked from 5 s on
    at, why = trend_pace.decide(entries, DEFAULT, [], NOW, "get_trend_videos")
    assert at is None and "would have to wait more than 65 s" in why
    assert "20 get_trend_videos calls per 60 s" in why and "same place" in why


def test_a_spent_budget_denies_until_its_reset_and_a_near_reset_waits():
    spent = Budget(2, NOW - 1000, NOW + 3_600_000, "*", "2026-11-22 00:00 UTC")
    entries = [(NOW - 500, "search_trends"), (NOW - 400, "get_trend")]
    at, why = trend_pace.decide(entries, DEFAULT, [spent], NOW, "get_trend")
    assert at is None and why.startswith("TrendsMesh allows 0 more calls until 2026-11-22 00:00 UTC")
    soon = Budget(2, NOW - 1000, NOW + 20_000, "*", "x")
    assert trend_pace.decide(entries, DEFAULT, [soon], NOW, "get_trend")[0] == NOW + 20_000 + trend_pace.MARGIN_MS
    # calls before the get_usage answer do not count against it
    assert trend_pace.decide(entries, DEFAULT, [Budget(2, NOW - 450, NOW + 3_600_000, "*", "x")], NOW, "x")[0] == NOW


# --- the limits from get_usage --------------------------------------------------------------------

USAGE = {"plan_code": "agent", "meters": [
    {"meter": "search_trends", "windows": [{"window_seconds": 60, "limit": 12, "remaining": 12},
                                           {"window": "day", "limit": 500, "remaining": 3,
                                            "resets_at": "2026-11-22T00:00:00Z"}]},
    {"name": "trend videos", "window": "60s", "limit": 30, "remaining": 30},
    {"name": "requests", "period": "minute", "limit": 100}]}


def test_get_usage_gives_the_windows_and_the_daily_budget():
    windows, budgets = trend_pace.usage_limits(USAGE)
    assert windows == [Window(60_000, 12, "search_trends"), Window(60_000, 30, "get_trend_videos"),
                       Window(60_000, 100, "*")]
    assert budgets == [Budget(3, 0, 1_795_305_600_000, "search_trends", "")]
    assert trend_pace.usage_limits({"plan_code": "human", "meters": []}) == ([], [])
    assert trend_pace.usage_limits({"error": "not_in_plan"}) == ([], [])
    assert trend_pace.usage_limits({"meters": [{"name": "x", "window": "fortnight?", "limit": "many"}, 3]}) == ([], [])


def test_learn_writes_the_limits_beside_the_log_and_keeps_the_rest_of_the_defaults(tmp_path):
    path = trend_pace.learn(tmp_path, USAGE, now_ms=NOW)
    assert path == tmp_path / ".trendsmesh" / "pace-limits.tsv"
    windows, budgets = trend_pace.read_limits(path.parent)
    assert Window(1000, 10, "*") in windows and Window(60_000, 12, "search_trends") in windows
    assert Window(60_000, 10, "search_trends") not in windows                    # replaced by get_usage's
    assert budgets == [Budget(3, NOW, 1_795_305_600_000, "search_trends", "2026-11-22 00:00 UTC")]
    assert trend_pace.learn(tmp_path, {"meters": []}) is None and path.is_file()  # no limits given: kept
    assert trend_pace.read_limits(tmp_path / "none") == (DEFAULT, [])


def test_a_saved_get_usage_answer_updates_the_workspaces_limits(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "nails", date(2026, 11, 21), playbook=TREND_RESEARCH)
    trends.save_answer(run, "get_usage", {}, USAGE)
    windows, _ = trend_pace.read_limits(tmp_path / "ws" / ".trendsmesh")
    assert Window(60_000, 12, "search_trends") in windows


# --- the hook -------------------------------------------------------------------------------------

def test_the_hook_books_the_call_and_sleeps_until_its_moment(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".trendsmesh").mkdir(parents=True)
    run = ws / "runs" / "04-trend-research" / "2026-11-21_nails"
    run.mkdir(parents=True)
    clock = Clock()
    for _ in range(10):
        assert trend_pace.pace(_event(run), now_ms=clock.ms, sleep=clock.sleep) is None
    assert clock.slept == [] or max(clock.slept) < 1.5                            # ten a second, and a little
    start = clock.now
    assert trend_pace.pace(_event(run), now_ms=clock.ms, sleep=clock.sleep) is None   # the 11th search of the minute
    assert clock.now - start >= 59_000
    log = trend_pace.read_log(ws / ".trendsmesh")
    assert len(log) == 11 and {k for _, k in log} == {"search_trends"}
    assert not (ws / ".trendsmesh" / trend_pace.LOCK).exists()


def test_the_hook_denies_with_the_reason_and_books_nothing(tmp_path):
    clock = Clock()
    folder = tmp_path / ".trendsmesh"
    folder.mkdir()
    (folder / trend_pace.LIMITS).write_text("window\t90000\t1\tsearch_trends\n", encoding="utf-8")
    assert trend_pace.pace(_event(tmp_path), now_ms=clock.ms, sleep=clock.sleep) is None
    got = trend_pace.pace(_event(tmp_path), now_ms=clock.ms, sleep=clock.sleep)
    assert got["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "1 search_trends calls per 90 s" in got["hookSpecificOutput"]["permissionDecisionReason"]
    assert len(trend_pace.read_log(folder)) == 1


def test_a_stale_lock_is_taken_over_and_a_fresh_one_waited_for(tmp_path):
    clock = Clock()
    lock = tmp_path / ".trendsmesh" / trend_pace.LOCK
    lock.mkdir(parents=True)
    (lock / "t").write_text(str(NOW - 9000), encoding="utf-8")
    assert trend_pace.pace(_event(tmp_path), now_ms=clock.ms, sleep=clock.sleep) is None
    assert not lock.exists()
    lock.mkdir()
    (lock / "t").write_text(str(NOW), encoding="utf-8")                          # fresh: waited for, then broken
    assert trend_pace.pace(_event(tmp_path), now_ms=clock.ms, sleep=clock.sleep) is None
    assert clock.slept and not lock.exists()


def test_the_workspace_is_found_above_the_cwd_but_never_the_home_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trendsmesh").mkdir()                                            # the plugin's paths file lives here
    ws = tmp_path / "work"
    (ws / "runs" / "03-organic-video").mkdir(parents=True)
    assert trend_pace.workspace_for(ws / "runs" / "03-organic-video") == ws
    other = tmp_path / "loose" / "folder"
    other.mkdir(parents=True)
    assert trend_pace.workspace_for(other) == other


def test_the_command_reads_an_event_and_says_its_status(tmp_path, capsys, monkeypatch):
    folder = tmp_path / ".trendsmesh"
    folder.mkdir()
    (folder / trend_pace.LIMITS).write_text("window\t90000\t1\tsearch_trends\n", encoding="utf-8")
    event = tmp_path / "event.json"
    event.write_text(json.dumps(_event(tmp_path)), encoding="utf-8")
    assert main(["trends", "pace", "--event", str(event)]) == 0
    assert capsys.readouterr().out == ""
    assert main(["trends", "pace", "--event", str(event), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    event.write_text("not json", encoding="utf-8")
    assert main(["trends", "pace", "--event", str(event)]) == 0 and capsys.readouterr().out == ""   # never fails a call
    assert main(["trends", "pace", "--status", "--workspace", str(tmp_path), "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["status"] == "done" and got["from_get_usage"] is True
    assert got["windows"] == [{"ms": 90000, "limit": 1, "tool": "search_trends", "booked": 1}]


# --- the shell's pace.awk decides as tm does ------------------------------------------------------

def _awk(tmp_path: Path, entries, windows, budgets, now, tool) -> tuple[int | None, str]:
    lim = tmp_path / "lim.tsv"
    lim.write_text("".join(f"window\t{w.ms}\t{w.limit}\t{w.tool}\n" for w in windows)
                   + "".join(f"budget\t{b.left}\t{b.since_ms}\t{b.reset_ms}\t{b.tool}\t{b.reset_text}\n" for b in budgets),
                   encoding="utf-8")
    log = tmp_path / "log.jsonl"
    log.write_text("".join(f'{{"t":{t},"tool":"{k}"}}\n' for t, k in entries), encoding="utf-8")
    lim_p, log_p = lim.as_posix(), log.as_posix()    # forward slashes, as pace-mcp.sh passes them: awk -v reads a backslash as an escape
    out = subprocess.run(["awk", "-v", f"now={now}", "-v", f"tool={tool}", "-v", f"margin={trend_pace.MARGIN_MS}",
                          "-v", f"maxwait={trend_pace.MAX_WAIT_S * 1000}", "-v", f"lim={lim_p}", "-v", f"out={log_p}",
                          "-f", str(AWK), lim_p, log_p], capture_output=True, text=True, check=True).stdout
    if out.startswith("go "):
        last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])        # the call's booked moment
        assert last["tool"] == tool and abs(now + float(out[3:]) * 1000 - last["t"]) < 1
        return last["t"], ""
    return None, out[5:].strip()


@pytest.mark.skipif(shutil.which("awk") is None, reason="no awk")
def test_pace_awk_decides_as_tm_does(tmp_path):
    rng = random.Random(129)
    tools = ["search_trends", "get_trend_videos", "get_trend", "list_trends"]
    for case in range(150):
        windows = DEFAULT if case % 3 else [Window(1500, 2, "search_trends"), Window(1000, 3, "*")]
        budgets = [Budget(rng.randint(0, 5), NOW - 30_000, NOW + rng.choice([10_000, 3_600_000]), "*", "the reset")] \
            if case % 7 == 0 else []
        entries = sorted((NOW + rng.randint(-70_000, 40_000), rng.choice(tools)) for _ in range(rng.randint(0, 40)))
        tool = rng.choice(tools)
        mine = trend_pace.decide(entries, windows, budgets, NOW, tool)
        theirs = _awk(tmp_path, entries, windows, budgets, NOW, tool)
        assert (mine[0], mine[1][:60]) == (theirs[0], theirs[1][:60]), (case, entries, tool)
