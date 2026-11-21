"""Creative brief runs started before issue #145 keep working (decision #148, line 25): a recorded G2 is read as done,
and an `animatics` output is a legacy output, left out. The run.json fields are a fixture of such runs."""

import json
from datetime import date
from pathlib import Path

import pytest

from tm import flow, state
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

RUNS = json.loads((Path(__file__).parent / "fixtures" / "creative_brief_pre_145" / "runs.json").read_text(
    encoding="utf-8"))["runs"]


@pytest.fixture
def old_run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))

    def make(name: str) -> RunFolder:
        run = RunFolder.create(ws, name, date(2026, 10, 1), playbook=CREATIVE_BRIEF)
        data = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
        (run.path / "run.json").write_text(json.dumps({**data, **RUNS[name]}), encoding="utf-8")
        return run
    return make


def test_every_fixture_run_lists_the_legacy_output_or_a_g2():
    for name, fields in RUNS.items():
        assert "animatics" in fields["outputs"] or any(d["checkin"] == "G2" for d in fields["decisions"]), name


def test_the_legacy_output_is_left_out_and_a_g2_is_read_past(old_run):
    run = old_run("g2_open_after_c1")
    s = state.load(run)
    assert s.outputs == ["review_pack", "briefs", "page"] and s.step == "D1"
    nxt = flow.next(run)                       # G2 was due here; the run goes on into D1, every concept in full
    assert (nxt.step, nxt.action, nxt.checkin) == ("D1", "work", None)
    with pytest.raises(ValueError, match="'G2' is not a check-in or a card"):
        flow.decide(run, "G2", "accept", by="user", note=None)


def test_a_recorded_g2_counts_as_done(old_run):
    run = old_run("g2_decided_at_d1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("D1", "work")
    assert [d["checkin"] for d in state.load(run).decisions] == ["G0", "G1", "G2"]    # kept as it was


def test_a_run_at_the_old_d2_goes_on_at_d3(old_run):
    """The old D2 came between D1 and D3; now D3 (the page with the briefs) comes first, then the animatics."""
    run = old_run("at_old_d2")
    assert state.load(run).step == "D3"
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("D3", "work")
    assert not any(d["checkin"] == "animatics" for d in state.load(run).decisions)   # asked after G3, as now


def test_a_run_past_the_old_d2_is_never_asked_for_animatics(old_run):
    run = old_run("at_e1_animatics_made")
    s = state.load(run)
    made = [d for d in s.decisions if d["checkin"] == "animatics"]
    assert made == [{"checkin": "animatics", "choice": "make", "by": "rule",
                     "rule": "made at D2 with the briefs, in a run started before animatics were on request",
                     "note": "legacy run: its animatics were made with its briefs", "concepts": ["C1", "C3"],
                     "legacy": True}]
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("E1", "work") and nxt.checkin.ids == ["G4"]
    state.save(run, s)                                         # saved once: read again, nothing is added
    assert [d["checkin"] for d in state.load(run).decisions].count("animatics") == 1
    raw = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
    assert "animatics" not in raw["outputs"]


def test_a_review_pack_run_with_its_g2_hands_off(old_run, capsys):
    run = old_run("review_pack_g2_decided")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("E2", "work")
    assert main(["status", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["outputs"] == ["review_pack", "page"]
