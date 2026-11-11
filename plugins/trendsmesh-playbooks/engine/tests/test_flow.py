"""The step engine: next step, check-in routing by level, decisions and stops."""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest
import yaml
from conftest import trend_steps_ready

from tm import budget, changes, checkins, evidence, flow, flowcmd, library, playbooks, r2, r4, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.runfolder import RunFolder

ALL_OUTPUTS = ["creative_brief", "edited_video", "ai_video", "live_test"]
LEVELS = ("every_step", "big_calls", "hands_off")
SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy Łódź"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = list(ALL_OUTPUTS)
    s.test_plan = {"feasible": True, "variants": 1, "calculation": "a feasible R4 plan"}  # E1 needs it
    state.save(r, s)
    trend_steps_ready(r)
    return r


def _outputs(run, outputs, flows=()):
    s = state.load(run)
    s.outputs = list(outputs)
    s.flows = list(flows)
    state.save(run, s)


def _approve_all(run):
    """Budgets approved for every kind, as the Hands-off config does."""
    s = state.load(run)
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(run, s)


def _reset(run, level):
    s = state.load(run)
    s.level, s.step, s.decisions, s.stops, s.status = None, None, [], [], "active"
    s.measurements_due, s.measurements_done = [], []
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(run, s)
    set_level(run, level)


def _settle(run):
    """Answer whatever the engine asks until it wants work, a stop or the end."""
    for _ in range(50):
        nxt = flow.next(run)
        if nxt.action in ("ask", "auto"):
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            if nxt.action == "ask":
                decide(run, nxt.checkin.card or nxt.checkin.ids[0], choice, by="user", note=None)
            else:
                decide(run, nxt.checkin.ids[0], choice, by="rule", note="test data")
        else:
            return nxt
    raise AssertionError("the engine kept asking")


def next_at(run, step):
    """Complete every step before `step`, answering check-ins on the way, and return next()."""
    for _ in range(60):
        nxt = _settle(run)
        assert nxt.action == "work", nxt
        if nxt.step == step:
            return nxt
        if nxt.step == "E3":
            _book_test(run)   # E3 is done once its spend is booked
        complete(run, nxt.step)
    raise AssertionError(f"never reached {step}")


def _finish(run, step):
    """Work up to `step`, complete it, and return what comes right after (without answering)."""
    next_at(run, step)
    complete(run, step)
    return flow.next(run)


def _book_test(run):
    """E3's work: the live test's spend, booked within an approved test budget."""
    s = state.load(run)
    s.budgets.setdefault("test", 500.0)
    state.save(run, s)
    assert budget.spend(run, "test", 1, "live test") == 0


def _cli(run, *args):
    return main([*args, "--run", str(run.path), "--json"])


def _library_rows(run, n, first=0):
    """n results-library rows for this run, variants "v<first>"..., as the closing step writes them."""
    ws = run.path.parents[2]
    for i in range(first, first + n):
        library.add(ws, {"variant": f"v{i}",
            "account": "act_1", "product": "Ebook", "market": "PL", "category": "ebooks",
            "diagnosis": "hook", "trend": {"id": f"t{i}", "type": "sound", "status_on_test_day": "rising"},
            "change": {"layer": "text", "method": "hook_swap"}, "decision_metric": "hook_rate",
            "result_vs_control": 0.1, "events": 400, "decision": "scale", "run": run.path.name})


def _to_e3(run):
    """Work through E2b with a green check and return next() at E3."""
    nxt = _finish(run, "E2b")
    assert (nxt.action, nxt.checkin.ids) == ("auto", ["E2b"])
    decide(run, "E2b", "green", by="rule", note="all green")
    return flow.next(run)


# --- the brief's tests -------------------------------------------------------

def test_every_step_asks_g1_alone(run):
    set_level(run, "every_step")
    assert next_at(run, "A1").checkin.ids == ["G1"]
    nxt = _finish(run, "A1")
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card) == ("A1", "ask", ["G1"], None)


def test_big_calls_merges_pick_the_ad(run):
    set_level(run, "big_calls")
    assert next_at(run, "A1").checkin is None  # G1 waits for the card
    assert next_at(run, "A3b").checkin.ids == ["G1", "G1a", "G1b"]
    complete(run, "A3b")
    nxt = flow.next(run)
    assert nxt.action == "ask" and nxt.step == "A3b"
    assert nxt.checkin.card == "pick_the_ad" and nxt.checkin.name == "Pick the ad"
    assert nxt.checkin.ids == ["G1", "G1a", "G1b"]
    assert "#1 from the ranking (R1)" in nxt.checkin.rule


G3_RULE = ("top 1–2, only those consistent with the image; in a middle run, the register of the "
           "diagnosed causes and the re-cut direction")


def test_hands_off_decides_g3_by_rule_and_logs_it(run):
    set_level(run, "hands_off")
    nxt = _finish(run, "A7")
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("A7", "auto", ["G3"])
    assert nxt.checkin.rule == G3_RULE
    decide(run, "G3", "hooks 1 and 2", by="rule", note="only these two match the image")
    last = state.load(run).decisions[-1]
    assert last["checkin"] == "G3" and last["by"] == "rule" and last["choice"] == "hooks 1 and 2"
    assert last["rule"] == G3_RULE
    assert last["note"] == "only these two match the image" and last["at"]
    assert (flow.next(run).step, flow.next(run).action) == ("B1", "work")


def test_voice_listening_test_stops_in_hands_off(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "hands_off")
    _approve_all(run)
    complete(run, next_at(run, "V1").step)
    assert _cli(run, "next") == 2
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("V1", "stop", ["V1c"])
    assert "continues from the same place" in nxt.message
    decide(run, "V1c", "voice_matches", by="user", note="voice 1")
    assert (flow.next(run).step, flow.next(run).action) == ("V3", "work")   # no clone yet, no GV
    complete(run, "V3")
    assert _cli(run, "next") == 2
    s = state.load(run)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "GV"
    assert flow.next(run).checkin.ids == ["GV"]
    decide(run, "GV", "could not tell", by="user", note=None)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("V4", "work")
    s = state.load(run)
    assert s.status == "active" and all("resumed_at" in x for x in s.stops)


def test_resume_from_run_json_only(run):
    set_level(run, "big_calls")
    next_at(run, "A3b")
    complete(run, "A3b")
    here = flow.next(run)
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    out = subprocess.run(
        [sys.executable, "-m", "tm", "next", "--run", str(run.path), "--json"],
        capture_output=True, text=True, encoding="utf-8", env=env)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == asdict(here)
    assert flow.next(RunFolder.open(run.path)) == here


def test_level_change_mid_run_reroutes_pending(run):
    set_level(run, "hands_off")
    next_at(run, "A5")
    complete(run, "A5")
    s = state.load(run)
    s.spend = {"ai_usd": 4.5}
    state.save(run, s)
    decided_before = list(state.load(run).decisions)
    assert flow.next(run).action == "auto"          # G2 by rule
    set_level(run, "every_step")
    nxt = flow.next(run)
    assert (nxt.action, nxt.checkin.ids) == ("ask", ["G2"])
    set_level(run, "big_calls")
    assert flow.next(run).action == "work"          # G2 waits for approve_changes
    assert flow.next(run).step == "A6"
    set_level(run, "hands_off")
    assert (flow.next(run).action, flow.next(run).checkin.ids) == ("auto", ["G2"])
    s = state.load(run)
    assert s.spend == {"ai_usd": 4.5}
    assert s.decisions == decided_before            # nothing re-decided or lost


def test_level_change_before_a_card_asks_only_what_is_left(run):
    set_level(run, "every_step")
    next_at(run, "A1a")                             # G1 answered on the way
    set_level(run, "big_calls")
    assert next_at(run, "A3b").checkin.ids == ["G1a", "G1b"]


def test_r8_red_item_stops_even_in_hands_off(run):
    for level in LEVELS:
        _reset(run, level)
        nxt = _finish(run, "E2b")
        assert (nxt.action, nxt.checkin.ids) == ("auto", ["E2b"]), level
        assert _cli(run, "decide", "E2b", "red", "--by", "rule", "--note", "no AI label") == 2
        s = state.load(run)
        assert s.status == "stopped" and s.stops[-1]["reason_id"] == "E2b"
        assert {"reason_id", "what", "todo", "at"} <= set(s.stops[-1])
        assert _cli(run, "next") == 2
        assert len(state.load(run).stops) == len(s.stops)   # asking again does not pile up stops
        with pytest.raises(ValueError, match="--change"):
            decide(run, "E2b", "green", by="rule", note="fixed")
        decide(run, "E2b", "green", by="rule", note="fixed the AI label", change=True)
        assert state.load(run).decisions[-1]["change"] is True
        assert flow.next(run).action != "stop"
        assert "resumed_at" in state.load(run).stops[-1]


def test_activation_sets_measurements_due(run):
    set_level(run, "every_step")
    nxt = _to_e3(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("E3", "ask", ["G11"])
    decide(run, "G11", "activate", by="user", note=None, today=date(2026, 11, 10))
    assert state.load(run).measurements_due == ["2026-11-13", "2026-11-15", "2026-11-17"]
    assert flow.next(run).step == "E3" and flow.next(run).action == "work"
    _book_test(run)
    complete(run, "E3")


# --- review round 1 ------------------------------------------------------------

@pytest.mark.parametrize("level,card", [("every_step", None), ("big_calls", "approve_launch")])
def test_launch_consent_comes_before_activation(run, level, card):
    set_level(run, level)
    nxt = _to_e3(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card) == ("E3", "ask", ["G11"], card)
    with pytest.raises(ValueError, match="G11"):
        complete(run, "E3")                         # no activation work before consent


def _measuring_run(run):
    set_level(run, "every_step")
    _to_e3(run)
    decide(run, "G11", "activate", by="user", note=None, today=date(2026, 11, 10))
    _book_test(run)
    complete(run, "E3")


def test_measurements_one_by_one_then_g12(run):
    _measuring_run(run)
    nxt = flow.next(run, today=date(2026, 11, 12))
    assert (nxt.step, nxt.action) == ("E4", "stop")
    assert "2026-11-13" in nxt.message and "continues from the same place" in nxt.message
    s = state.load(run)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "measurement_not_due"
    nxt = flow.next(run, today=date(2026, 11, 13))
    assert (nxt.step, nxt.action) == ("E4", "work") and "--measured 2026-11-13" in nxt.message
    with pytest.raises(ValueError, match="--measured"):
        complete(run, "E4", today=date(2026, 11, 13))
    with pytest.raises(ValueError, match="not due"):
        complete(run, "E4", measured="2026-11-15", today=date(2026, 11, 13))
    complete(run, "E4", measured="2026-11-13", today=date(2026, 11, 13))
    nxt = flow.next(run, today=date(2026, 11, 14))
    assert nxt.action == "stop" and "2026-11-15" in nxt.message
    ws = run.path.parents[2]
    assert flow.due(ws, date(2026, 11, 14)) == []
    assert [i["date"] for i in flow.due(ws, date(2026, 11, 16))] == ["2026-11-15"]
    flow.next(run, today=date(2026, 11, 15))
    complete(run, "E4", measured="2026-11-15", today=date(2026, 11, 15))
    flow.next(run, today=date(2026, 11, 17))
    complete(run, "E4", measured="2026-11-17", today=date(2026, 11, 17))
    assert flow.due(ws, date(2026, 11, 30)) == []
    nxt = flow.next(run, today=date(2026, 11, 17))
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("E4", "ask", ["G12"])
    decide(run, "G12", "scale", by="user", note=None)
    _library_rows(run, 1)
    assert flow.next(run).action == "done"


def test_spending_card_before_first_elevenlabs_step(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "big_calls")
    assert next_at(run, "V0").checkin.ids == ["VB"]      # previewed while V0 is worked on
    nxt = _finish(run, "V0")
    assert (nxt.step, nxt.action, nxt.checkin.card, nxt.checkin.ids) == (
        "V1", "ask", "approve_spending", ["VB"])
    with pytest.raises(ValueError, match="VB"):
        complete(run, "V1")


def test_voice_budget_asked_before_v1_at_every_step(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "every_step")
    nxt = _finish(run, "V0")
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("V1", "ask", ["VB"])


def test_spending_card_covers_every_budget_before_the_first_spend(run):
    _outputs(run, ALL_OUTPUTS, flows=["V"])
    set_level(run, "big_calls")
    nxt = _finish(run, "V0")
    assert (nxt.step, nxt.checkin.card, nxt.checkin.ids) == ("V1", "approve_spending",
                                                              ["VB", "G6", "G10"])


def test_spending_card_without_voice_comes_before_d2(run):
    set_level(run, "big_calls")
    assert next_at(run, "D1").checkin.ids == ["G6", "G10"]
    nxt = _finish(run, "D1")
    assert (nxt.step, nxt.action, nxt.checkin.card) == ("D2", "ask", "approve_spending")


def test_rule_decision_needs_a_note(run):
    set_level(run, "hands_off")
    _approve_all(run)
    _finish(run, "A1")
    with pytest.raises(ValueError, match="--note"):
        decide(run, "G1", "ad_1", by="rule", note=None)
    assert _cli(run, "decide", "G1", "ad_1", "--by", "rule") == 1
    assert _cli(run, "decide", "G1", "ad_1", "--by", "rule", "--note", "#1, cost +62%") == 0


def test_do_not_refresh_ends_before_a2_at_every_level(run):
    for level in LEVELS:
        _reset(run, level)
        nxt = next_at(run, "A1a")
        assert "do_not_refresh" in nxt.message
        decide(run, "G1a", "do_not_refresh", by="rule", note="whole account fell")
        s = state.load(run)
        assert s.status == "done" and s.spend == {} and s.step == "A1a", level
        done = flow.next(run)
        assert done.action == "done"
        assert "diagnosis report" in done.message and "nothing was spent" in done.message
        with pytest.raises(ValueError, match="done"):
            complete(run, "A1a")


def test_external_stop_holds_until_resume(run):
    set_level(run, "every_step")
    next_at(run, "A2")
    code = flow.stop(run, "missing_video", "The ad's video file is not in the brand folder.",
                     "Download it from Ads Manager and put it in the brand folder.")
    assert code == 2
    for _ in range(2):
        nxt = flow.next(run)
        assert (nxt.step, nxt.action) == ("A2", "stop") and "brand folder" in nxt.message
    assert _cli(run, "next") == 2
    assert len(state.load(run).stops) == 1
    with pytest.raises(ValueError, match="stopped"):
        complete(run, "A2")
    assert _cli(run, "resume") == 0
    s = state.load(run)
    assert s.status == "active" and s.stops[-1]["resumed_at"]
    assert (flow.next(run).step, flow.next(run).action) == ("A2", "work")
    assert _cli(run, "resume") == 1                # not stopped any more


def test_stop_cli_records_an_external_stop_until_resume(run, capsys):
    """The skill records a stop it found itself (A2 no video, E2 upload) with `tm stop`."""
    set_level(run, "every_step")
    next_at(run, "A2")
    capsys.readouterr()
    assert _cli(run, "stop", "--reason", "missing_video",
                "--what", "The ad's video file is not in the brand folder.",
                "--todo", "Download it from Ads Manager and put it in the brand folder.") == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "brand folder" in out["message"]
    assert _cli(run, "next") == 2
    s = state.load(run)
    assert s.status == "stopped" and s.stops[-1]["reason_id"] == "missing_video"
    assert _cli(run, "stop", "--reason", "x", "--what", " ", "--todo", "y") == 1
    assert _cli(run, "resume") == 0
    assert flow.next(run).action == "work"


def test_decide_does_not_repeat_an_unrelated_stop(run, capsys):
    set_level(run, "every_step")
    _finish(run, "A1")
    flow.stop(run, "sign_in", "Meta needs you to sign in again.", "Sign in, then tell Claude.")
    capsys.readouterr()
    assert _cli(run, "decide", "G1", "ad_1") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and "sign in" not in json.dumps(out).lower()


def test_redeciding_needs_change_and_is_recorded(run):
    set_level(run, "every_step")
    _finish(run, "A1")
    decide(run, "G1", "ad_1", by="user", note=None)
    with pytest.raises(ValueError, match="--change"):
        decide(run, "G1", "ad_2", by="user", note=None)
    assert _cli(run, "decide", "G1", "ad_2", "--change") == 0
    last = state.load(run).decisions[-1]
    assert last["choice"] == "ad_2" and last["change"] is True


# --- other controller decisions and edges ------------------------------------

def test_a0_is_work_until_level_set(run):
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin) == ("A0", "work", None)
    assert "Check every step" in nxt.message and "Hands-off" in nxt.message
    with pytest.raises(ValueError, match="level"):
        complete(run, "A0")


def test_unknown_level_refused(run):
    with pytest.raises(ValueError):
        set_level(run, "auto")
    assert _cli(run, "level", "auto") == 1
    assert _cli(run, "level", "big_calls") == 0
    assert state.load(run).level == "big_calls"


def test_card_decision_records_one_entry_per_member(run):
    set_level(run, "big_calls")
    next_at(run, "A3b")
    complete(run, "A3b")
    assert _cli(run, "decide", "pick_the_ad", "ad_123", "--note", "recommended") == 0
    entries = state.load(run).decisions
    assert [d["checkin"] for d in entries] == ["G1", "G1a", "G1b"]
    assert all(d["choice"] == "ad_123" and d["by"] == "user" and d["note"] == "recommended"
               for d in entries)
    assert "rule" not in entries[0]
    assert flow.next(run).step == "A4"
    assert _cli(run, "decide", "pick_the_ad", "ad_9") == 1
    assert _cli(run, "decide", "pick_the_ad", "ad_9", "--change") == 0


def test_changes_card_at_b2(run):
    set_level(run, "big_calls")
    assert next_at(run, "B2").checkin.ids == ["G2", "G3", "G4"]


def test_rule_refused_where_the_user_must_answer(run):
    set_level(run, "every_step")
    _finish(run, "A1")
    with pytest.raises(ValueError, match="G1"):
        decide(run, "G1", "ad_1", by="rule", note="data")
    assert _cli(run, "decide", "G1", "ad_1", "--by", "rule", "--note", "data") == 1


def test_cannot_skip_a_pending_checkin_or_step(run):
    set_level(run, "every_step")
    next_at(run, "A1")
    with pytest.raises(ValueError, match="A1"):
        complete(run, "A3")
    complete(run, "A1")
    with pytest.raises(ValueError, match="G1"):
        complete(run, "A1a")
    with pytest.raises(ValueError):
        decide(run, "G3", "x", by="user", note=None)   # not reached yet


def test_steps_outside_the_outputs_are_skipped(run):
    _outputs(run, ["creative_brief"])
    set_level(run, "every_step")
    nxt = next_at(run, "B1")
    assert nxt.step == "B1"
    with pytest.raises(ValueError, match="G6"):
        decide(run, "G6", "ok", by="user", note=None)   # no AI video in this run
    for step in ("B1", "B2", "B3"):
        next_at(run, step)
        complete(run, step)
    assert _settle(run).action == "done"
    assert state.load(run).status == "done"
    with pytest.raises(ValueError, match="done"):
        decide(run, "G4", "ok", by="user", note=None)


def test_voice_steps_skipped_without_flow_v(run):
    _outputs(run, ["edited_video"])
    set_level(run, "hands_off")
    nxt = _finish(run, "C1")
    assert (nxt.step, nxt.action) == ("C2", "work")
    with pytest.raises(ValueError, match="VB"):
        decide(run, "VB", "ok", by="user", note=None)


def test_status_json(run, capsys):
    set_level(run, "big_calls")
    capsys.readouterr()
    assert _cli(run, "status") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["level"] == "big_calls" and out["run_id"] == run.path.name


def test_done_and_next_cli(run, capsys):
    set_level(run, "every_step")
    capsys.readouterr()
    assert _cli(run, "next") == 0
    assert json.loads(capsys.readouterr().out)["step"] == "A0"
    assert _cli(run, "done", "A0") == 0
    assert _cli(run, "done", "A3") == 1
    capsys.readouterr()
    assert _cli(run, "next") == 0
    assert json.loads(capsys.readouterr().out)["step"] == "A0b"


def test_flow_cli_turns_on_flow_v(run):
    assert _cli(run, "flow", "V") == 0
    assert state.load(run).flows == ["V"]
    assert _cli(run, "flow", "Q") == 1


def test_due_lists_measurements_across_runs(run, monkeypatch, capsys):
    ws = run.path.parents[2]
    s = state.load(run)
    s.measurements_due = ["2026-11-01", "2026-11-03", "2026-11-04", "2099-01-01"]
    s.measurements_done = ["2026-11-04"]
    state.save(run, s)
    other = RunFolder.create(ws, "Ad 4", date(2026, 11, 5))
    s2 = state.load(other)
    s2.measurements_due = ["2026-11-02"]
    s2.status = "done"
    state.save(other, s2)
    (ws / "runs" / "01-refresh-ad" / "broken").mkdir()
    (ws / "runs" / "01-refresh-ad" / "broken" / "run.json").write_text("{", encoding="utf-8")
    items = flow.due(ws, date(2026, 11, 5))
    assert [i["date"] for i in items] == ["2026-11-01", "2026-11-03"]
    assert all(run.path.name in i["message"] for i in items)
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    capsys.readouterr()
    assert main(["due", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["due"]) == 2



def test_due_lists_weekly_report_after_seven_days(tmp_path, monkeypatch, capsys):
    """A done trend research run with the weekly digest, the latest of its chain and a week old, is
    due again; a run another run follows, a week not over and a run without the weekly digest are not.
    A chain whose latest run is still going is reminded to be finished instead."""
    ws = tmp_path / "ws"
    ws.mkdir()

    def research(name, created, outputs=("category_report", "weekly_digest"), status="done", after=None):
        r = RunFolder.create(ws, name, created, playbook=playbooks.TREND_RESEARCH)
        s = state.load(r)
        s.outputs, s.status = list(outputs), status
        s.previous_run = after.path.relative_to(ws).as_posix() if after else None
        state.save(r, s)
        return r

    first = research("beauty", date(2026, 10, 24))                       # followed by `beauty-w2`
    second = research("beauty-w2", date(2026, 10, 31), after=first)       # latest, 7 days on 7 Nov
    research("nails", date(2026, 11, 2))                                  # only 5 days old
    research("hair", date(2026, 10, 20), outputs=("category_report",))     # no weekly digest
    going = research("lashes", date(2026, 10, 20), status="active")       # followed: not reminded itself
    unfinished = research("lashes-w2", date(2026, 11, 6), after=going, status="active")
    items = flow.due(ws, date(2026, 11, 7))
    assert items == [{"message": f"Run {second.path.name}: the weekly trend report is due. Ask Claude to "
                                 "update the trend report.",
                      "run": second.path.name, "date": "2026-11-07"},
                     {"message": f"Run {unfinished.path.name}: this week's trend report was started on 2026-11-06 "
                                 "and is not finished. Ask Claude to continue the trend report.",
                      "run": unfinished.path.name, "date": "2026-11-07"}]   # in folder order
    assert flow.due(ws, date(2026, 11, 6)) == []
    monkeypatch.setenv("TM_WORKSPACE", str(ws))

    class Nov7(date):                     # `tm due` asks for today: the day the items above were listed for
        @classmethod
        def today(cls):
            return date(2026, 11, 7)

    monkeypatch.setattr(flowcmd, "date", Nov7)
    capsys.readouterr()
    assert main(["due", "--quiet"]) == 0
    assert capsys.readouterr().out.splitlines() == [i["message"] for i in items]


def test_due_skips_a_desktop_task_and_reminds_an_unfinished_weekly_run(tmp_path):
    """A done run whose weekly run a desktop scheduled task starts is not reminded; a weekly run left
    unfinished is reminded to be finished from the day after it started, so it never silences the
    reminders for good."""
    ws = tmp_path / "ws"
    ws.mkdir()
    first = RunFolder.create(ws, "beauty", date(2026, 10, 24), playbook=playbooks.TREND_RESEARCH)
    s = state.load(first)
    s.outputs, s.status = ["category_report", "weekly_digest"], "done"
    s.schedule = {"how": "desktop_task", "id": "trend-report-beauty-us", "cron": "0 9 * * 1"}
    state.save(first, s)
    assert flow.due(ws, date(2026, 11, 7)) == []                          # the task starts next week's run
    s.schedule = {"how": "by_hand"}
    state.save(first, s)
    assert [i["run"] for i in flow.due(ws, date(2026, 11, 7))] == [first.path.name]
    follower = RunFolder.create(ws, "beauty-w2", date(2026, 10, 31), playbook=playbooks.TREND_RESEARCH)
    s2 = state.load(follower)
    s2.outputs, s2.previous_run = ["category_report", "weekly_digest"], first.path.relative_to(ws).as_posix()
    state.save(follower, s2)
    assert flow.due(ws, date(2026, 10, 31)) == []                         # started today: still going
    assert flow.due(ws, date(2026, 11, 7)) == [{
        "message": (f"Run {follower.path.name}: this week's trend report was started on 2026-10-31 and is not "
                    "finished. Ask Claude to continue the trend report."),
        "run": follower.path.name, "date": "2026-11-01"}]
    lone = RunFolder.create(ws, "nails", date(2026, 10, 20), playbook=playbooks.TREND_RESEARCH)
    s3 = state.load(lone)
    s3.outputs = ["category_report", "weekly_digest"]                     # an unfinished first run: not a weekly one
    state.save(lone, s3)
    assert [i["run"] for i in flow.due(ws, date(2026, 11, 7))] == [follower.path.name]

def test_due_with_no_runs_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TM_WORKSPACE", str(tmp_path))
    assert main(["due", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"due": []}


# --- carried from the Task 5 review ---------------------------------------------

def test_spending_card_comes_at_the_earlier_of_first_spend_and_first_member(run):
    _outputs(run, ["creative_brief", "live_test"])
    set_level(run, "big_calls")
    assert next_at(run, "E1").checkin.ids == ["G10"]
    nxt = _finish(run, "E1")
    assert (nxt.step, nxt.action, nxt.checkin.card, nxt.checkin.ids) == (
        "E1", "ask", "approve_spending", ["G10"])           # right after E1, before E2's paused ads
    with pytest.raises(ValueError, match="G10"):
        complete(run, "E2")


def test_original_voice_found_skips_the_clone(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "every_step")
    _finish(run, "V1")
    assert flow.next(run).checkin.ids == ["V1c"]
    decide(run, "V1c", "original_voice_found", by="user", note="1:1 match in the library")
    nxt = _settle(run)
    assert (nxt.step, nxt.action) == ("V4", "work")        # no V3, no GV
    steps_done = []
    for _ in range(10):
        n = _settle(run)
        steps_done.append(n.step)
        if n.step == "C2":
            break
        complete(run, n.step)
    assert "V3" not in steps_done and "V4" in steps_done


def test_original_voice_found_in_hands_off_still_skips_gv(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "hands_off")
    _approve_all(run)
    _finish(run, "V1")
    assert flow.next(run).action == "stop"
    decide(run, "V1c", "original_voice_found", by="user", note=None)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("V4", "work")
    assert state.load(run).status == "active"


def test_other_v1c_choices_keep_the_clone(run):
    _outputs(run, ["edited_video"], flows=["V"])
    set_level(run, "every_step")
    _finish(run, "V1")
    decide(run, "V1c", "none_matches", by="user", note=None)
    assert (flow.next(run).step, flow.next(run).action) == ("V3", "work")


def test_measurements_must_be_taken_earliest_first(run):
    _measuring_run(run)
    late = date(2026, 11, 20)
    flow.next(run, today=late)
    with pytest.raises(ValueError, match="2026-11-13"):
        complete(run, "E4", measured="2026-11-15", today=late)
    complete(run, "E4", measured="2026-11-13", today=late)
    with pytest.raises(ValueError, match="2026-11-15"):
        complete(run, "E4", measured="2026-11-17", today=late)
    assert state.load(run).measurements_done == ["2026-11-13"]


# --- supported changes end the run (Task 8) ----------------------------------------

def _diagnosis(stage, refresh=True, also_seen=()):
    return r2.Diagnosis(stage=stage, refresh=refresh, evidence={"hook_rate": (0.3, 0.2)},
                        also_seen=list(also_seen))


def _asks_g1a_alone(run, level):
    nxt = flow.next(run)
    assert nxt.action == ("auto" if level == "hands_off" else "ask"), nxt
    assert nxt.checkin.ids == ["G1a"] and nxt.checkin.card is None
    assert "isn't supported yet" in nxt.message and "do_not_refresh" in nxt.message
    return nxt


@pytest.mark.parametrize("level", LEVELS)
def test_unsupported_material_ends_run_without_spend(run, level):
    # 0.3.0: the middle has re-cuts, so a run is unsupported by its material (a static graphic)
    set_level(run, level)
    next_at(run, "A1a")
    changes.record_material(run, "static")
    r2.record(run, _diagnosis("middle"))
    nxt = _asks_g1a_alone(run, level)
    assert state.load(run).status != "done"                      # not done mid-step
    for other in ("ok", "accept"):
        with pytest.raises(ValueError, match="only do_not_refresh"):
            decide(run, "G1a", other, by="rule" if level == "hands_off" else "user", note="x")
    if level == "big_calls":
        with pytest.raises(ValueError, match="only do_not_refresh"):
            decide(run, "pick_the_ad", "ok", by="user", note=None)
    if level == "hands_off":
        decide(run, "G1a", "do_not_refresh", by="rule", note=nxt.message)
    else:
        decide(run, "G1a", "do_not_refresh", by="user", note=None)
    done = flow.next(run)
    assert done.action == "done" and "isn't supported yet" in done.message and "static graphic" in done.message
    assert "nothing was spent" in done.message
    s = state.load(run)
    assert s.status == "done" and s.spend == {}
    assert flow.next(run).message == done.message                # a new session sees the same end
    assert main(["next", "--run", str(run.path), "--json"]) == 0
    with pytest.raises(ValueError, match="done"):
        r2.record(run, _diagnosis("hook"))
    with pytest.raises(ValueError, match="done"):
        changes.record_material(run, "text_cards")


def test_talking_head_ends_run_without_spend(run):
    set_level(run, "every_step")
    next_at(run, "A1a")
    r2.record(run, _diagnosis("hook"))
    assert flow.next(run).action == "work"                       # hook is fine for some materials
    changes.record_material(run, "talking_head")
    nxt = flow.next(run)
    assert nxt.action == "ask" and nxt.step == "A3" and nxt.checkin.ids == ["G1a"]
    assert "talking head" in nxt.message and "isn't supported yet" in nxt.message
    decide(run, "G1a", "do_not_refresh", by="user", note=None)
    done = flow.next(run)
    assert done.action == "done" and "talking head" in done.message
    assert state.load(run).spend == {}


def test_also_seen_stage_rescues_the_run(run):
    set_level(run, "every_step")
    next_at(run, "A1a")
    changes.record_material(run, "talking_head")                 # the opening of a talking head has no edit
    r2.record(run, _diagnosis("hook", also_seen=["middle"]))
    d = state.load(run).diagnosis
    assert d["stage"] == "hook" and d["target_stage"] == "middle" and "middle" in d["note"]
    nxt = flow.next(run)
    assert nxt.action == "work"                                  # nothing is asked: G1a is the normal one
    changes.record_material(run, "static")                       # no edit for any stage now
    assert flow.next(run).action == "ask"
    changes.record_material(run, "talking_head")                 # corrected: back on track
    assert state.load(run).diagnosis["target_stage"] == "middle"
    assert flow.next(run).action == "work"


def test_correcting_the_diagnosis_before_g1a_replaces_it(run):
    set_level(run, "every_step")
    next_at(run, "A1a")
    r2.record(run, _diagnosis("landing", refresh=False))
    assert flow.next(run).action == "ask"
    r2.record(run, _diagnosis("hook"))
    assert state.load(run).diagnosis["stage"] == "hook"
    assert flow.next(run).action == "work"
    assert (run.path / "04_final" / "diagnosis_v02.json").is_file()
    assert (run.path / "manifest.md").read_text(encoding="utf-8").count("diagnosis_v0") == 2


@pytest.mark.parametrize("level", LEVELS)
def test_not_a_refresh_is_enforced_at_g1a(run, level):
    set_level(run, level)
    next_at(run, "A1a")
    r2.record(run, _diagnosis("landing", refresh=False))
    nxt = flow.next(run)
    assert nxt.action == ("auto" if level == "hands_off" else "ask") and nxt.checkin.ids == ["G1a"]
    assert "landing" in nxt.message
    with pytest.raises(ValueError, match="only do_not_refresh"):
        decide(run, "G1a", "ok", by="rule" if level == "hands_off" else "user", note="x")
    decide(run, "G1a", "do_not_refresh", by="user", note=None)
    done = flow.next(run)
    assert done.action == "done" and "should not be refreshed" in done.message


def test_spent_money_is_not_called_unspent(run):
    set_level(run, "every_step")
    next_at(run, "A1a")
    s = state.load(run)
    s.spend = {"ai_usd": 3.0}
    state.save(run, s)
    changes.record_material(run, "static")
    r2.record(run, _diagnosis("middle"))
    nxt = flow.next(run)
    assert nxt.checkin.ids == ["G1a"] and "isn't supported yet" in nxt.message
    assert "nothing was spent" not in nxt.message and "already spent stays counted" in nxt.message


def test_a_supported_diagnosis_and_material_carry_on(run):
    set_level(run, "every_step")
    next_at(run, "A1a")
    r2.record(run, _diagnosis("hook"))
    changes.record_material(run, "text_cards")
    assert flow.next(run).action == "work"


def _measure_all(run):
    for d in ("2026-11-13", "2026-11-15", "2026-11-17"):
        flow.next(run, today=date.fromisoformat(d))
        complete(run, "E4", measured=d, today=date.fromisoformat(d))
    decide(run, "G12", "scale", by="user", note=None)


def test_run_not_closed_without_library_entry(run):
    _outputs(run, ["live_test"])
    set_level(run, "every_step")
    _measuring_run(run)
    r4.record(run, r4.plan("hook", _control(), 2, _cfg(400)))
    _measure_all(run)
    nxt = flow.next(run, today=date(2026, 11, 17))
    assert nxt.action == "work" and nxt.step == "E4" and "tm library add --run" in nxt.message
    assert f'run "{run.path.name}"' in nxt.message and "0 of 2 variants" in nxt.message
    assert "2 missing" in nxt.message and state.load(run).status != "done"
    _library_rows(run, 1)
    nxt = flow.next(run, today=date(2026, 11, 17))
    assert nxt.action == "work" and "1 of 2 variants" in nxt.message      # one of two variants
    _library_rows(run, 1)                                                   # the same variant again
    assert flow.next(run, today=date(2026, 11, 17)).action == "work"       # counts once
    _library_rows(run, 1, first=1)
    assert flow.next(run, today=date(2026, 11, 17)).action == "done"
    assert state.load(run).status == "done"


def test_untried_test_closes_without_library_rows(run):
    _outputs(run, ["live_test"])
    set_level(run, "every_step")
    _to_e3(run)
    decide(run, "G11", "keep_paused", by="user", note=None)
    assert state.load(run).measurements_due == []
    assert flow.next(run).action == "done"              # E3 and E4 are skipped: nothing to measure
    assert state.load(run).status == "done"


def test_library_rows_of_other_runs_do_not_count(run):
    _outputs(run, ["live_test"])
    set_level(run, "every_step")
    _measuring_run(run)
    _measure_all(run)
    library.add(run.path.parents[2], {
        "account": "a", "product": "p", "market": "PL", "diagnosis": "hook", "variant": "v0",
        "trend": {"id": "x", "type": "t", "status_on_test_day": "s"},
        "change": {"layer": "text", "method": "m"}, "decision_metric": "hook_rate",
        "result_vs_control": 0, "events": 1, "decision": "kill", "run": "some-other-run"})
    assert flow.next(run, today=date(2026, 11, 17)).action == "work"      # no plan stored: one row needed
    _library_rows(run, 1)
    assert flow.next(run, today=date(2026, 11, 17)).action == "done"


def test_library_add_run_fills_run_and_workspace(run, tmp_path):
    row = {"account": "a", "product": "p", "market": "PL", "diagnosis": "hook", "variant": "B",
           "trend": {"id": "x", "type": "t", "status_on_test_day": "s"},
           "change": {"layer": "text", "method": "m"}, "decision_metric": "hook_rate",
           "result_vs_control": 0, "events": 1, "decision": "scale"}
    f = tmp_path / "row.json"
    f.write_text(json.dumps(row), encoding="utf-8")
    assert main(["library", "add", "--run", str(run.path), "--row", str(f), "--json"]) == 0
    stored = library.rows(run.path.parents[2])
    assert [r["run"] for r in stored] == [run.path.name]
    f.write_text(json.dumps({**row, "run": "another-run"}), encoding="utf-8")
    assert main(["library", "add", "--run", str(run.path), "--row", str(f)]) == 1
    assert len(library.rows(run.path.parents[2])) == 1


def test_diagnose_material_r4_cli_write_state_and_files(run, tmp_path):
    peak = r2.window_to_json(_control())
    late = dict(peak, p25=21_000, thruplay=10_500)
    pf, lf = tmp_path / "peak.json", tmp_path / "latest.json"
    pf.write_text(json.dumps(peak), encoding="utf-8")
    lf.write_text(json.dumps(late), encoding="utf-8")
    base = ["--run", str(run.path), "--json"]
    assert main(["diagnose", *base, "--peak", str(pf), "--latest", json.dumps(late), "--account-ratio", "1"]) == 0
    s = state.load(run)
    assert s.diagnosis["stage"] == "hook"
    assert (run.path / "04_final" / "diagnosis_v01.json").is_file()
    assert "diagnosis_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")
    assert main(["material", *base, "text_cards"]) == 0 and state.load(run).material == "text_cards"
    assert main(["material", *base, "hologram"]) == 1
    assert main(["changes", "--stage", "hook", "--material", "text_cards", "--json"]) == 0
    (run.path / "config.yaml").write_text("budget:\n  test_per_day: 1\n", encoding="utf-8")
    cf = tmp_path / "control.json"
    cf.write_text(json.dumps(peak), encoding="utf-8")
    assert main(["r4", *base, "--stage", "hook", "--control", str(cf), "--variants", "2"]) == 2
    assert state.load(run).test_plan["variants"] == 2 and state.load(run).test_plan["feasible"] is False


def _control():
    from tm.r1 import Window
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=1350.0, results=30,
                  impressions=100_000, p25=30_000, thruplay=15_000, clicks_est=1_500,
                  frequency=1.5, cpm=20.0, weeks=1)


def _cfg(per_day):
    from tm import config
    c = config.defaults()
    c["budget"]["test_per_day"] = per_day
    return c


def test_json_output_is_utf8_under_a_legacy_code_page(run):
    """Windows pipes default to cp1252: a Polish path must not crash `tm`."""
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    out = subprocess.run(
        [sys.executable, "-m", "tm", "status", "--run", str(run.path), "--json"],
        capture_output=True, env=env)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    assert json.loads(out.stdout.decode("utf-8"))["path"] == str(run.path)  # holds "Łódź"


# --- flow R, path C-R (handoff v03, Task 11) -----------------------------------------

V021 = Path(__file__).parent / "fixtures" / "v021_runs"
V030 = Path(__file__).parent / "fixtures" / "v030_runs"


def _applied(run):
    return [st.id for st in flow._picture(state.load(run)).app]


def _at_a1a(run, level, diagnosis, material="text_cards", outputs=("edited_video",)):
    _outputs(run, outputs)
    set_level(run, level)
    next_at(run, "A1a")
    changes.record_material(run, material)
    r2.record(run, diagnosis)


def _structural(yes=True):
    return {"structural": yes, "step": "p75/p50", "segment_s": [12.1, 18.1], "uploads": []}


def _config(run, **diagnosis):
    (run.path / "config.yaml").write_text(yaml.safe_dump({"diagnosis": diagnosis}), encoding="utf-8")


CR = ["CR1", "CR2", "CR3", "CR4", "CR5a", "CR5b", "CR6", "CR7"]


def test_middle_run_gets_cr_steps_and_skips_c2_c4(run):
    _at_a1a(run, "every_step", _diagnosis("middle"))
    assert state.load(run).diagnosis["target_stage"] == "middle"
    flow.use_flow(run, "R")
    applied = _applied(run)
    assert applied[applied.index("C1"):] == ["C1", *CR]
    assert not {"C2", "C3", "C4"} & set(applied)
    # the run walks C1, CR1..CR7 in order, with G3r after CR3, RB before CR5a and G5r after CR7
    seen, asked = [], []
    for _ in range(80):
        nxt = flow.next(run)
        if nxt.action == "ask":
            asked.append((nxt.step, tuple(nxt.checkin.ids)))
            decide(run, nxt.checkin.card or nxt.checkin.ids[0],
                   nxt.checkin.choices[0] if nxt.checkin.choices else "ok", by="user", note=None)
            continue
        if nxt.action == "done":
            break
        assert nxt.action == "work", nxt
        seen.append(nxt.step)
        complete(run, nxt.step)
    assert seen[seen.index("C1"):] == ["C1", *CR]
    assert ("CR3", ("G3r",)) in asked and ("CR5a", ("RB",)) in asked and ("CR7", ("G5r",)) in asked
    assert asked.index(("CR5a", ("RB",))) < asked.index(("CR7", ("G5r",)))
    assert "G5" not in {cid for _, ids in asked for cid in ids}       # C4 is not in a middle run


def test_middle_run_with_a_new_vo_line_runs_flow_v_between_cr4_and_cr5a(run):
    _at_a1a(run, "every_step", _diagnosis("middle"), material="vo_captions")
    flow.use_flow(run, "R")
    flow.use_flow(run, "V")                                     # recut_new_vo_line, turned on at G3r
    applied = _applied(run)
    assert applied[applied.index("C1"):] == ["C1", "CR1", "CR2", "CR3", "CR4", "V0", "V1", "V3", "V4",
                                             "V5", "VC", "CR5a", "CR5b", "CR6", "CR7"]


def test_hook_run_with_structural_gets_both(run):
    _at_a1a(run, "every_step", r2.Diagnosis(stage="hook", refresh=True, evidence={"hook_rate": (0.3, 0.2)},
                                             structural=_structural()))
    assert state.load(run).diagnosis["target_stage"] == "hook"
    flow.use_flow(run, "R")
    applied = _applied(run)
    assert applied[applied.index("C1"):] == ["C1", *CR, "C2", "C3", "C4"]


def test_steps_with_targets_apply_until_a_target_is_known(run):
    _outputs(run, ["edited_video"])
    set_level(run, "every_step")
    assert {"C2", "C3", "C4"} <= set(_applied(run))            # no diagnosis yet
    s = state.load(run)
    s.diagnosis = {"stage": "landing", "refresh": False, "target_stage": None}
    state.save(run, s)
    assert {"C2", "C3", "C4"} <= set(_applied(run))            # no target stage: as before
    for stage, kept in (("promise_cta", True), ("fatigue", True), ("middle", False)):
        s.diagnosis = {"stage": stage, "refresh": True, "target_stage": stage}
        state.save(run, s)
        assert ({"C2", "C3", "C4"} <= set(_applied(run))) is kept, stage


def test_flow_r_needs_a_middle_or_a_structural_diagnosis(run):
    _outputs(run, ["edited_video"])
    set_level(run, "every_step")
    with pytest.raises(ValueError, match="no diagnosis"):
        flow.use_flow(run, "R")
    next_at(run, "A1a")
    changes.record_material(run, "text_cards")
    r2.record(run, _diagnosis("hook"))
    with pytest.raises(ValueError, match="R2b") as no:
        flow.use_flow(run, "R")
    assert "middle" in str(no.value) and "same place" in str(no.value)
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True, structural=_structural(False)))
    with pytest.raises(ValueError, match="not structural"):
        flow.use_flow(run, "R")
    assert "R" not in state.load(run).flows
    flow.use_flow(run, "V")                                     # flow V has no such guard
    assert state.load(run).flows == ["V"]


@pytest.mark.parametrize("level", [None, "every_step", "big_calls"])
def test_a_structural_weakness_turns_on_flow_r_outside_hands_off(run, level):
    _at_a1a(run, "every_step", r2.Diagnosis(stage="hook", refresh=True, structural=_structural()))
    s = state.load(run)
    s.level = level
    state.save(run, s)
    flow.use_flow(run, "R")
    assert state.load(run).flows == ["R"]


def test_rc3_hands_off_structural_without_switch_refuses_flow_r(run):
    _at_a1a(run, "hands_off", r2.Diagnosis(stage="hook", refresh=True, structural=_structural()))
    with pytest.raises(ValueError, match="diagnosis.structural_recut") as no:
        flow.use_flow(run, "R")
    assert "Hands-off" in str(no.value) and "same place" in str(no.value)
    _config(run, structural_recut=False)
    with pytest.raises(ValueError, match="diagnosis.structural_recut"):
        flow.use_flow(run, "R")
    assert "R" not in state.load(run).flows
    _config(run, structural_recut=True)
    flow.use_flow(run, "R")
    assert "R" in state.load(run).flows


def test_unset_level_with_auto_mode_counts_as_hands_off_for_flow_r(run):
    _at_a1a(run, "every_step", r2.Diagnosis(stage="hook", refresh=True, structural=_structural()))
    s = state.load(run)
    s.level = None
    state.save(run, s)
    (run.path / "config.yaml").write_text("mode: auto\n", encoding="utf-8")
    with pytest.raises(ValueError, match="diagnosis.structural_recut"):
        flow.use_flow(run, "R")


def test_hands_off_middle_turns_on_flow_r_without_the_switch(run):
    _at_a1a(run, "hands_off", _diagnosis("middle"))
    flow.use_flow(run, "R")
    assert "R" in state.load(run).flows


def test_rb_approve_lets_the_recut_budgets_be_approved(run):
    _outputs(run, ["edited_video", "ai_video"])            # G6 is in the run too, but not asked yet
    set_level(run, "every_step")
    s = state.load(run)
    s.budgets = {}
    state.save(run, s)
    next_at(run, "A1a")
    changes.record_material(run, "text_cards")
    r2.record(run, _diagnosis("middle"))
    flow.use_flow(run, "R")
    with pytest.raises(ValueError):
        budget.approve(run, "ai_usd", 5)                       # nobody said yes yet
    nxt = next_at(run, "CR4")
    complete(run, "CR4")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("CR5a", "ask", ["RB"])
    decide(run, "RB", "approve", by="user", note=None)
    budget.approve(run, "ai_usd", 5)
    budget.approve(run, "voice_credits", 500)
    assert state.load(run).budgets == {"ai_usd": 5.0, "voice_credits": 500.0}


def test_rb_reject_skips_the_paid_recut_steps_only(run):
    _at_a1a(run, "every_step", _diagnosis("middle"))
    flow.use_flow(run, "R")
    next_at(run, "CR4")
    complete(run, "CR4")
    assert flow.next(run).checkin.ids == ["RB"]
    decide(run, "RB", "reject", by="user", note=None)
    applied = _applied(run)
    assert applied[applied.index("C1"):] == ["C1", "CR1", "CR2", "CR3", "CR4", "CR6", "CR7"]
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("CR6", "work")
    with pytest.raises(ValueError, match="said no"):
        budget.approve(run, "ai_usd", 5)


def test_hands_off_recut_goes_past_cr5a_and_cr5b_without_budgets(run):
    """Controller ruling (Task 11, concern 1): in Hands-off, re-cut money is fenced by `tm recut
    check` (L3-L5 wait without the budget) and the tools' budget guard, so CR5a and CR5b never stop
    the run: the free L0-L2 variants render and the paid ones stay waiting."""
    _at_a1a(run, "hands_off", _diagnosis("middle"))
    flow.use_flow(run, "R")
    s = state.load(run)
    s.budgets = {}
    state.save(run, s)
    next_at(run, "CR4")
    complete(run, "CR4")
    nxt = flow.next(run)
    assert (nxt.action, nxt.checkin.ids) == ("auto", ["RB"])
    decide(run, "RB", "approve", by="rule", note="limit from the config")
    for step in ("CR5a", "CR5b"):
        nxt = flow.next(run)
        assert (nxt.step, nxt.action) == (step, "work"), nxt
        complete(run, step)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("CR6", "work")
    s = state.load(run)
    assert s.status == "active" and s.stops == [] and s.budgets == {} and s.spend == {}


def test_hands_off_still_waits_for_the_voice_budget_outside_flow_r(run):
    _outputs(run, ["edited_video"], flows=["V", "R"])
    set_level(run, "hands_off")
    s = state.load(run)
    s.budgets = {}
    state.save(run, s)
    nxt = _finish(run, "V0")
    nxt = _settle(run)
    assert (nxt.step, nxt.action) == ("V1", "stop") and "voice budget" in nxt.message


LATE_R = "Flow R must be turned on at the diagnosis (G1a), before the edited video's steps start."


@pytest.mark.parametrize("level", LEVELS)
def test_a_middle_target_runs_the_recut_steps_without_tm_flow_r(run, level):
    _at_a1a(run, level, _diagnosis("middle"))
    assert state.load(run).flows == []                          # nobody ran `tm flow R`
    seen = []
    for _ in range(80):
        nxt = _settle(run)
        if nxt.action != "work":
            break
        seen.append(nxt.step)
        complete(run, nxt.step)
    assert nxt.action == "done", nxt
    assert seen[seen.index("C1"):] == ["C1", *CR]
    s = state.load(run)
    assert {d["checkin"] for d in s.decisions} >= {"G3r", "RB", "G5r"}


def test_tm_flow_r_after_c1_is_refused(run):
    _at_a1a(run, "every_step", r2.Diagnosis(stage="hook", refresh=True, structural=_structural()))
    next_at(run, "C1")
    complete(run, "C1")
    with pytest.raises(ValueError) as late:
        flow.use_flow(run, "R")
    assert LATE_R in str(late.value) and "same place" in str(late.value)
    assert "R" not in state.load(run).flows
    assert flow.next(run).step == "C2"


def test_tm_flow_r_at_c1_is_still_in_time(run):
    _at_a1a(run, "every_step", r2.Diagnosis(stage="hook", refresh=True, structural=_structural()))
    next_at(run, "C1")
    flow.use_flow(run, "R")
    complete(run, "C1")
    assert _settle(run).step == "CR1"


def test_tm_flow_r_late_in_a_middle_run_changes_nothing(run):
    _at_a1a(run, "every_step", _diagnosis("middle"))
    next_at(run, "CR2")                                         # flow R is on by the target
    flow.use_flow(run, "R")                                     # recorded, not refused: it was on
    assert state.load(run).flows == ["R"] and flow.next(run).step == "CR2"


OLD_RUNS = [(folder.name, p.name[:-len(".run.json")])
            for folder in (V021, V030) for p in sorted(folder.glob("*.run.json"))]


@pytest.mark.parametrize("dirname,name", OLD_RUNS, ids=[f"{d}-{n}" for d, n in OLD_RUNS])
def test_old_run_resumes_at_same_step(run, dirname, name):
    """A run.json saved by tm 0.2.1 or 0.3.0 (no `pages`, `previous_run` or `schedule`) gives the
    step, action and check-in that engine itself gave (fixtures/<dirname>/expected.json). 0.2.1's
    runs also have no flow R, no targets and a diagnosis without structural or ladder; three of
    0.3.0's are flow R and one structural by design."""
    folder = Path(__file__).parent / "fixtures" / dirname
    expected = {c["name"]: c for c in json.loads((folder / "expected.json").read_text(encoding="utf-8"))["cases"]}
    saved = json.loads((folder / f"{name}.run.json").read_text(encoding="utf-8"))
    assert not {"pages", "previous_run", "schedule"} & set(saved)
    if folder == V021:
        assert "recut" not in saved and "R" not in saved["flows"]
        assert saved["diagnosis"] and "structural" not in saved["diagnosis"]
    (run.path / "run.json").write_text(json.dumps(saved), encoding="utf-8")
    nxt = flow.next(run)
    want = expected[name]
    assert (nxt.step, nxt.action) == (want["step"], want["action"])
    assert (nxt.checkin.ids if nxt.checkin else None) == want["checkin"]
    assert state.load(run).step == saved["step"]


def test_old_run_fixtures_cover_both_releases():
    assert {d for d, _ in OLD_RUNS} == {"v021_runs", "v030_runs"}
    assert len([n for d, n in OLD_RUNS if d == "v030_runs"]) == 5


# --- more than one playbook (trend research, Task 1) ---------------------------------

REFRESH_AD_STEPS_030 = [
    "A0", "A0b", "A1", "A1a", "A2", "A3", "A3b", "A4", "A5", "A6", "A7", "B1", "B2", "B3", "C1",
    "CR1", "CR2", "CR3", "CR4", "V0", "V1", "V3", "V4", "V5", "VC", "CR5a", "CR5b", "CR6", "CR7",
    "C2", "C3", "C4", "D1", "D2", "D3", "D4", "D5", "E1", "E2", "E2b", "E3", "E4"]


def test_refresh_ad_steps_unchanged():
    assert len(REFRESH_AD_STEPS_030) == 42
    assert [s.id for s in flow.steps()] == REFRESH_AD_STEPS_030
    assert [s.id for s in flow.steps(playbooks.REFRESH_AD)] == REFRESH_AD_STEPS_030
    assert flow.output_ids() == ALL_OUTPUTS and flow.flows() == {"V", "R"}


def _two(tmp_path, playbook, outputs, level="every_step"):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "w1", date(2026, 11, 7), playbook=playbook)
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    set_level(run, level)
    return run


def test_second_playbook_walks_its_own_steps(tmp_path, playbook_two):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "w1", date(2026, 11, 7), playbook=playbook_two)
    assert run.path == tmp_path / "ws" / "runs" / "99-two" / "2026-11-07_w1"
    assert state.load(run).playbook == "99-two"
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("P1", "work")      # the intake: its own first step
    assert "Check every step" in nxt.message
    s = state.load(run)
    s.outputs = ["page"]
    state.save(run, s)
    set_level(run, "every_step")
    assert flow.output_ids(playbook_two) == ["page", "live_test"]
    assert [st.id for st in flow.steps(playbook_two)] == ["P1", "P2", "A5", "A7", "E1", "E3"]
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("P1", "work", ["Q1"])
    complete(run, "P1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("P1", "ask", ["Q1"])
    assert _cli(run, "decide", "Q1", "yes") == 0
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin) == ("P2", "work", None)
    complete(run, "P2")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("P2", "done") and nxt.notice is None
    assert list(checkins.load(playbook=playbook_two).checkins) == ["Q1"]
    assert "Q1" not in checkins.load().checkins


def test_refresh_ad_guards_skip_other_playbooks(tmp_path, playbook_two):
    """Each of refresh-ad's own checks would hold this 99-two run if it applied to it: a diagnosis
    that says not to refresh (G1a's block), an infeasible R4 plan (the plan stop, and E1), a
    Hands-off step with no approved budget (E3), no evidence (A5, and the line asking for it at
    A5 and A7), no checked register (A7), no booked spend (E3), and an activated live test with
    no results-library rows. Removing any one `_pb01` guard in `next`, `complete`, `set_evidence`,
    `use_flow` or `notice_for` fails this test; decide's G10/G11 plan check is not covered here,
    since 99-two's catalogue holds only Q1."""
    run = _two(tmp_path, playbook_two, ["live_test"], level="hands_off")
    s = state.load(run)
    s.diagnosis = {"stage": "landing", "refresh": False, "target_stage": None}
    s.test_plan = {"feasible": False, "variants": 2, "calculation": "too few events"}
    s.measurements_due = ["2026-01-01"]
    state.save(run, s)
    assert not flow._pb01(s) and s.evidence is None and s.register is None
    assert not s.budgets and not s.spend
    for step in ("A5", "A7", "E1", "E3"):
        nxt = flow.next(run)
        assert (nxt.step, nxt.action) == (step, "work"), nxt
        assert "tm evidence" not in nxt.message
        complete(run, step)
    assert flow.next(run).action == "done"
    for refused, says in ((lambda: flow.set_evidence(run, "guess", "no plan"),
                           "Guess mode is part of Refresh an ad and Creative brief, not of Playbook two."),
                          (lambda: flow.use_flow(run, "R"),
                           "Variant flows are part of Refresh an ad, not of Playbook two.")):
        with pytest.raises(ValueError) as no:
            refused()
        assert str(no.value) == says
    s.evidence = "guess"
    assert evidence.notice_for(s, ["G2"], done=True) is None


def test_budget_approve_is_refused_for_other_playbooks(tmp_path, playbook_two, capsys):
    run = _two(tmp_path, playbook_two, ["live_test"])
    assert _cli(run, "budget", "approve", "test", "5", "--note", "the user said yes") == 1
    assert json.loads(capsys.readouterr().out)["message"] == (
        "Budgets are part of Refresh an ad, not of Playbook two.")
    assert state.load(run).budgets == {}


def test_refresh_ad_run_is_pb01():
    assert flow._pb01(state.RunState(run_id="x", playbook="01-refresh-ad", created="2026-11-07"))
