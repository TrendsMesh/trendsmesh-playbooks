"""Trend research (playbook 04) in the step engine: its steps, and its check-ins at each level."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from tm import checkins, flow, playbooks, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.playbooks import REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder

ALL = ["category_report", "weekly_digest", "paid_view"]
STEP_IDS = ["A0", "A1", "A2", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "F2", "D1", "D2", "D3",
            "E1", "E2", "F5", "E3"]
WEEKLY_ONLY = {"F2", "F5"}
SKILL = Path(__file__).resolve().parents[2] / "skills" / "trend-research"


def _research(tmp_path, level, outputs):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "beauty", date(2026, 11, 7), playbook=TREND_RESEARCH)
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    set_level(run, level)
    return run


def _walk(run, choices=None, until=None):
    """Do each step's work and answer each check-in (by rule when the engine says auto) until the
    run is done or stops, or `until` is the step to work on next. Returns the check-ins seen as (step,
    action, ids, card), the steps worked, and the last next(). A card is answered as a card when
    every member takes the same choice, else member by member."""
    choices = choices or {}
    seen, worked = [], []
    for _ in range(100):
        nxt = flow.next(run)
        if nxt.action in ("done", "stop") or (nxt.action == "work" and nxt.step == until):
            return seen, worked, nxt
        if nxt.action == "work":
            worked.append(nxt.step)
            complete(run, nxt.step)
            continue
        assert nxt.action in ("ask", "auto"), nxt
        seen.append((nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card))
        cat = checkins.load(playbook=TREND_RESEARCH)
        picked = {cid: choices.get(cid, cat.checkins[cid].choices[0]) for cid in nxt.checkin.ids}
        by, note = ("rule", "test data") if nxt.action == "auto" else ("user", None)
        if nxt.checkin.card and len(set(picked.values())) == 1:
            decide(run, nxt.checkin.card, next(iter(picked.values())), by=by, note=note)
        else:
            for cid, choice in picked.items():
                decide(run, cid, choice, by=by, note=note)
    raise AssertionError("the run never ended")


# --- the registry, steps and catalogue --------------------------------------------

def test_trend_research_is_registered():
    pb = playbooks.get("trend-research")
    assert (pb.id, pb.name, pb.skill) == (TREND_RESEARCH, "Trend research", "trend-research")
    assert pb.data_dir.name == "trend-research"


def test_trend_research_steps_match_the_plan():
    every = flow.steps(TREND_RESEARCH)
    assert flow.output_ids(TREND_RESEARCH) == ALL
    assert [st.id for st in every] == STEP_IDS
    assert flow.flows(TREND_RESEARCH) == set()
    for st in every:
        assert not st.spends and st.budget is None, st.id   # PB04 spends nothing
        assert st.ref == f"skills/trend-research/references/flow.md#{st.id.lower()}"
        assert list(st.outputs) == (["weekly_digest"] if st.id in WEEKLY_ONLY else ALL), st.id
    placed = {st.id: (st.before, st.checkins, dict(st.skip_when)) for st in every
              if st.before or st.checkins or st.skip_when}
    assert placed == {"A1": ((), ("G0",), {}), "B4": ((), ("G1",), {}), "D3": ((), ("G2",), {}),
                      "E1": ((), ("G3",), {}), "E2": ((), (), {"G3": "keep_local"}),
                      "F5": (("GS",), (), {"GS": "by_hand"})}
    titles = {st.id: st.title for st in every}
    assert titles["B4"] == "Hooks path" and titles["F2"] == "Digest and call check"
    assert titles["D2"] == "Paid vs organic (Ad Library)" and titles["E3"] == "Hand the picks on (seeds)"




def test_trend_research_catalogue():
    cat = checkins.load(playbook=TREND_RESEARCH)
    assert list(cat.checkins) == ["G0", "G1", "G2", "G3", "GS"]
    assert {c.id: (c.name, c.ask) for c in cat.cards.values()} == {
        "approve_map": ("Approve the category map", "last"),
        "approve_report": ("Approve the picks and the page", "last")}
    big = {"every_step": "own", "big_calls": "card", "hands_off": "rule"}
    for cid, card, choices in (("G0", "approve_map", ("accept",)),
                               ("G1", "approve_map", ("accept", "changed_a_lot")),
                               ("G2", "approve_report", ("accept",)),
                               ("G3", "approve_report", ("publish", "keep_local"))):
        c = cat.checkins[cid]
        assert (c.route, c.card, c.choices, c.money) == (big, card, choices, False), cid
    gs = cat.checkins["GS"]
    assert (gs.route, gs.card, gs.choices) == (
        {"every_step": "own", "big_calls": "own", "hands_off": "rule"}, None, ("schedule", "by_hand"))
    assert cat.checkins["G3"].rule.startswith("keep_local when `publish_files` is not in the session")
    assert "same link" in cat.checkins["G3"].rule
    assert "`tm research map-change`" in cat.checkins["G1"].rule
    assert cat.checkins["GS"].rule.startswith("by_hand unless the previous run's schedule.how is desktop_task")



def test_every_step_ref_has_its_anchor_in_the_skill():
    """Each step's ref is a section of the bundled skill's flow.md, one anchor per step, in step order."""
    flow_md = (SKILL / "references" / "flow.md").read_text(encoding="utf-8")
    anchors = re.findall(r'<a id="([a-z0-9]+)"></a>', flow_md)
    assert anchors == [st.ref.split("#")[1] for st in flow.steps(TREND_RESEARCH)]

def test_levels_are_named_the_same_in_every_playbook():
    known = playbooks.all_playbooks()
    assert {REFRESH_AD, TREND_RESEARCH} <= {p.id for p in known}
    names = checkins.load(playbook=REFRESH_AD).levels
    assert names == {"every_step": "Check every step", "big_calls": "Just the big calls",
                     "hands_off": "Hands-off"}
    for p in known:
        assert checkins.load(playbook=p.id).levels == names, p.id


def test_run_new_after_records_previous_run(tmp_path, monkeypatch, capsys, bundled_skills):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    w1 = RunFolder.create(ws, "w1", date(2026, 11, 7), playbook=TREND_RESEARCH)
    assert main(["run", "new", "--playbook", "trend-research", "--name", "w2", "--after",
                 str(w1.path), "--json"]) == 0
    w2 = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    s = state.load(w2)
    assert s.playbook == TREND_RESEARCH
    assert s.previous_run == "runs/04-trend-research/2026-11-07_w1"
    ad = RunFolder.create(ws, "ad", date(2026, 11, 7))   # a refresh-ad run
    assert main(["run", "new", "--playbook", "trend-research", "--name", "w3", "--after",
                 str(ad.path), "--json"]) == 1
    assert "Refresh an ad" in json.loads(capsys.readouterr().out)["message"]


# --- the levels ---------------------------------------------------------------------

def test_every_step_asks_g0_g1_g2_g3_one_by_one(tmp_path):
    run = _research(tmp_path, "every_step", ALL)
    seen, worked, end = _walk(run)
    assert seen == [("A1", "ask", ["G0"], None), ("B4", "ask", ["G1"], None),
                    ("D3", "ask", ["G2"], None), ("E1", "ask", ["G3"], None),
                    ("F5", "ask", ["GS"], None)]
    assert worked == STEP_IDS
    assert end.action == "done"
    assert all(d["by"] == "user" for d in state.load(run).decisions)


def test_big_calls_asks_map_card_after_b4_and_report_card_after_e1(tmp_path):
    run = _research(tmp_path, "big_calls", ALL)
    seen, _, nxt = _walk(run, until="D3")
    assert seen == [("B4", "ask", ["G0", "G1"], "approve_map")]
    assert nxt.checkin is None   # G2 waits for the report card
    assert main(["done", "D3", "--run", str(run.path), "--json"]) == 0   # before G2 is decided
    assert "G2" not in {d["checkin"] for d in state.load(run).decisions}
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.card) == (
        "E1", "work", ["G2", "G3"], "approve_report")
    complete(run, "E1")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids, nxt.checkin.name) == (
        "E1", "ask", ["G2", "G3"], "Approve the picks and the page")
    seen, worked, end = _walk(run)
    assert seen == [("E1", "ask", ["G2", "G3"], "approve_report"), ("F5", "ask", ["GS"], None)]
    assert worked == ["E2", "F5", "E3"] and end.action == "done"
    assert [(d["checkin"], d["choice"]) for d in state.load(run).decisions] == [
        ("G0", "accept"), ("G1", "accept"), ("G2", "accept"), ("G3", "publish"), ("GS", "schedule")]


def test_hands_off_decides_all_by_rule_and_g1_changed_a_lot_stops(tmp_path):
    run = _research(tmp_path, "hands_off", ALL)
    seen, worked, nxt = _walk(run, {"G1": "changed_a_lot"})
    assert seen == [("A1", "auto", ["G0"], None), ("B4", "auto", ["G1"], None)]
    assert worked == STEP_IDS[:STEP_IDS.index("C1")]
    assert (nxt.step, nxt.action) == ("B4", "stop")
    assert "The category map changed a lot since the last run." in nxt.message
    assert "Look at the new map and say whether to go on with it." in nxt.message
    assert "continues from the same place" in nxt.message
    assert state.load(run).status == "stopped"
    with pytest.raises(flow.Held):
        complete(run, "C1")
    decide(run, "G1", "accept", by="user", note="the new map is fine", change=True)
    seen, worked, end = _walk(run, {"GS": "by_hand"})  # a first run has no schedule to keep
    assert seen == [("D3", "auto", ["G2"], None), ("E1", "auto", ["G3"], None),
                    ("F5", "auto", ["GS"], None)]
    assert worked == [s for s in STEP_IDS[STEP_IDS.index("C1"):] if s != "F5"]
    assert end.action == "done"
    cat = checkins.load(playbook=TREND_RESEARCH)
    by_rule = [d for d in state.load(run).decisions if d["by"] == "rule"]
    assert [(d["checkin"], d["choice"]) for d in by_rule] == [
        ("G0", "accept"), ("G1", "changed_a_lot"), ("G2", "accept"), ("G3", "publish"),
        ("GS", "by_hand")]
    assert all(d["rule"] == cat.checkins[d["checkin"]].rule for d in by_rule)


@pytest.mark.parametrize("level", ["every_step", "hands_off"])
def test_keep_local_skips_publish(tmp_path, level):
    run = _research(tmp_path, level, ["category_report"])
    seen, worked, end = _walk(run, {"G3": "keep_local"})
    assert "E2" not in worked and worked[-2:] == ["E1", "E3"]
    assert ("E1", "auto" if level == "hands_off" else "ask", ["G3"], None) in seen
    assert "The page stays a local file; nothing was published." in end.message


def test_by_hand_skips_schedule(tmp_path):
    run = _research(tmp_path, "every_step", ["category_report", "weekly_digest"])
    seen, worked, end = _walk(run, {"GS": "by_hand"})
    assert seen[-1] == ("F5", "ask", ["GS"], None)
    assert "F2" in worked and "F5" not in worked and worked[-3:] == ["E1", "E2", "E3"]
    assert "No schedule was set up: say 'update my trend report' each week." in end.message


def test_report_only_run_skips_f2_and_f5(tmp_path):
    run = _research(tmp_path, "every_step", ["category_report"])
    seen, worked, end = _walk(run)
    assert worked == [i for i in STEP_IDS if i not in WEEKLY_ONLY]
    assert [ids for _, _, ids, _ in seen] == [["G0"], ["G1"], ["G2"], ["G3"]]
    assert end.action == "done"


# --- the weekly schedule (GS, F5) ---------------------------------------------------

def test_research_schedule_records_how_the_next_run_starts(tmp_path, capsys):
    run = _research(tmp_path, "big_calls", ALL)
    assert main(["research", "schedule", "--run", str(run.path), "--how", "desktop_task", "--id",
                 "trend-report-beauty", "--cron", "0 9 * * 1", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and "trend-report-beauty" in out["message"]
    assert state.load(run).schedule == {"how": "desktop_task", "id": "trend-report-beauty", "cron": "0 9 * * 1"}
    assert main(["research", "schedule", "--run", str(run.path), "--how", "by_hand", "--json"]) == 0
    capsys.readouterr()
    assert state.load(run).schedule == {"how": "by_hand"}
    for bad in (["--how", "desktop_task"],                                   # no id or cron
                ["--how", "desktop_task", "--id", "x", "--cron", "0 9 * *"],  # four fields
                ["--how", "by_hand", "--id", "x"]):                          # by hand has no task
        assert main(["research", "schedule", "--run", str(run.path), *bad, "--json"]) == 1
        assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert state.load(run).schedule == {"how": "by_hand"}
    report_only = RunFolder.create(tmp_path / "ws", "hair", date(2026, 11, 7), playbook=TREND_RESEARCH)
    assert main(["research", "schedule", "--run", str(report_only.path), "--how", "by_hand", "--json"]) == 1
    assert "weekly digest" in json.loads(capsys.readouterr().out)["message"]
    assert state.load(report_only).schedule is None
