"""tm.trend_age: how old a run's trend data is, for the resume question (issue 59)."""

import json
from datetime import date

import pytest

from tm import brief_config, config, research_config, state, trend_age, trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO, TREND_RESEARCH
from tm.runfolder import RunFolder


@pytest.fixture
def ws(tmp_path):
    folder = tmp_path / "ws"
    folder.mkdir()
    return folder


def _run(ws, playbook=ORGANIC_VIDEO):
    return RunFolder.create(ws, "cats", date(2026, 10, 1), playbook=playbook)


def _save(run, tool, at, answer=None):
    given = {"trend_id": "t1"} if tool == "get_trend" else {"query": "cat toys"}
    return trends.save_answer(run, tool, given, answer if answer is not None else {"items": []},
                              at=f"{at}T09:00:00+00:00")


def test_a_run_without_trend_data_has_none(ws):
    run = _run(ws)
    assert trend_age.of(run, today=date(2026, 12, 1)) is None


def test_fresh_data_is_not_expired(ws):
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01")
    got = trend_age.of(run, today=date(2026, 10, 15))
    assert got["fetched"] == "2026-10-01" and got["valid_until"] == "2026-10-15" and got["expired"] is False
    assert "valid until 2026-10-15" in got["message"]


def test_data_past_its_valid_until_is_expired(ws):
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01")
    got = trend_age.of(run, today=date(2026, 10, 16))
    assert got["expired"] is True and got["days"] == trend_age.DEFAULT_DAYS
    assert "expired on 2026-10-15" in got["message"] and "2026-10-01" in got["message"]


def test_the_latest_fetch_counts_and_other_tools_do_not(ws):
    """Data fetched again in the run is fresh again; usage and Ad Library answers are not trend data."""
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01")
    _save(run, "get_trend", "2026-10-20", {"id": "t1", "kind": "trend"})
    _save(run, "get_usage", "2026-11-30")
    _save(run, "ads_library_search", "2026-11-30")
    got = trend_age.of(run, today=date(2026, 11, 1))
    assert got["fetched"] == "2026-10-20" and got["valid_until"] == "2026-11-03" and got["expired"] is False


def test_an_error_answer_is_no_trend_data(ws):
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01", {"error": "rate limited"})
    assert trend_age.of(run, today=date(2026, 12, 1)) is None


def test_the_runs_own_valid_days(ws):
    """Trend research's picks.valid_days and the creative brief's brief.valid_days_default are the run's
    valid days."""
    research = _run(ws, TREND_RESEARCH)
    config.save(research, {**research_config.defaults(), "picks": {**research_config.defaults()["picks"],
                                                                   "valid_days": 7}})
    _save(research, "list_trends", "2026-10-01")
    assert trend_age.of(research, today=date(2026, 10, 9))["valid_until"] == "2026-10-08"
    brief = RunFolder.create(ws, "brief", date(2026, 10, 1), playbook=CREATIVE_BRIEF)
    cfg = brief_config.defaults()
    cfg["brief"]["valid_days_default"] = 30
    config.save(brief, cfg)
    _save(brief, "search_trends", "2026-10-01")
    assert trend_age.of(brief, today=date(2026, 10, 9))["valid_until"] == "2026-10-31"


def test_a_seed_past_its_valid_until_is_said(ws):
    """A run started from a trend pick: the pick's own valid-until, before anything is fetched."""
    run = _run(ws)
    (run.path / brief_config.SEED_FILE).write_text(
        json.dumps({"seed_id": "r:t1", "valid_until": "2026-10-05"}), encoding="utf-8")
    got = trend_age.of(run, today=date(2026, 10, 9))
    assert got["fetched"] is None and got["valid_until"] == "2026-10-05" and got["expired"] is True
    assert "trend pick" in got["message"]
    _save(run, "get_trend", "2026-10-09", {"id": "t1", "kind": "trend"})
    got = trend_age.of(run, today=date(2026, 10, 9))      # the earlier of the two dates
    assert got["valid_until"] == "2026-10-05" and got["expired"] is True


def test_status_json_says_when_trend_data_expired(ws, capsys, monkeypatch):
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01")
    monkeypatch.setattr(trend_age, "_today", lambda: date(2026, 11, 12))
    capsys.readouterr()
    assert main(["status", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["trend_data"]["expired"] is True and out["created"] == "2026-10-01"
    assert state.load(run).step is None                    # tm status changes nothing


def test_status_text_says_it_too(ws, capsys, monkeypatch):
    run = _run(ws)
    _save(run, "search_trends", "2026-10-01")
    monkeypatch.setattr(trend_age, "_today", lambda: date(2026, 11, 12))
    capsys.readouterr()
    assert main(["status", "--run", str(run.path)]) == 0
    assert "expired on 2026-10-15" in capsys.readouterr().out
