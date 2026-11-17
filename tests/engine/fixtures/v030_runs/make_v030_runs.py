"""How these fixtures were made: runs driven by the 0.3.0 engine itself (commit 9119b14), each
run.json saved with 0.3.0's own `tm next` answer in expected.json. test_flow.py's
test_old_run_resumes_at_same_step loads them into the current engine.

    git archive 9119b14 plugins/trendsmesh-playbooks/engine/src plugins/trendsmesh-playbooks/data \
        | tar -x -C <old>
    PYTHONPATH=<old>/plugins/trendsmesh-playbooks/engine/src python -I make_v030_runs.py <out dir>
(with -I, put <old>/.../engine/src on sys.path by hand.) Not collected by pytest.

Unlike 0.2.1's runs, three of these use flow R (a middle diagnosis, or a structural one), and
one is measuring: its live test was activated in the past, so its measurements are due on any
day the test runs.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from tm import __version__, budget, changes, flow, r2, state
from tm.flow import complete, decide, set_level
from tm.runfolder import RunFolder

assert __version__ == "0.3.0", __version__
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
ACTIVATED = date(2026, 10, 1)  # G11 activate: measurements due 3, 5 and 7 days later, all past
ALL_OUTPUTS = ["creative_brief", "edited_video", "ai_video", "live_test"]
STRUCTURAL = {"structural": True, "step": "p75/p50", "segment_s": [12.1, 18.1], "uploads": []}


def ready(run, evidence="trendsmesh"):
    if evidence == "trendsmesh":
        (run.path / "02_research" / "trend_t1.json").write_text(json.dumps({"id": "t1"}), encoding="utf-8")
    s = state.load(run)
    s.evidence = evidence
    s.register = {"file": "04_final/change_register_v01.json", "proof": int(evidence == "trendsmesh"),
                  "guess": int(evidence == "guess")}
    s.test_plan = {"feasible": True, "variants": 1, "calculation": "a feasible R4 plan"}
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(run, s)


def settle(run):
    for _ in range(50):
        nxt = flow.next(run)
        if nxt.action in ("ask", "auto"):
            cid = nxt.checkin.card or nxt.checkin.ids[0]
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            if "G1a" in nxt.checkin.ids:
                choice = "refresh"
            if nxt.action == "ask":
                decide(run, cid, choice, by="user", note=None, today=ACTIVATED)
            else:
                decide(run, nxt.checkin.ids[0], choice, by="rule", note="fixture", today=ACTIVATED)
        else:
            return nxt
    raise AssertionError("kept asking")


def drive_to(run, step, *, diagnosis, material="text_cards", flows_at_a1a=()):
    for _ in range(80):
        nxt = settle(run)
        if nxt.step == step and nxt.action == "work":
            return nxt
        assert nxt.action == "work", nxt
        if nxt.step == "A1a" and state.load(run).diagnosis is None:
            changes.record_material(run, material)
            r2.record(run, diagnosis)
            for f in flows_at_a1a:
                flow.use_flow(run, f)
            continue
        if nxt.step == "E3":
            assert budget.spend(run, "test", 1, "live test") == 0
        complete(run, nxt.step)
    raise AssertionError(f"never reached {step}")


def diagnosis(stage, structural=None):
    return r2.Diagnosis(stage=stage, refresh=True, evidence={"hook_rate": (0.3, 0.2)},
                        structural=structural)


def new(ws, outputs, level, evidence="trendsmesh"):
    ws.mkdir()
    run = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    ready(run, evidence)
    set_level(run, level)
    return run


def save(run, name, nxt):
    data = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
    (OUT / f"{name}.run.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    return {"name": name, "step": nxt.step, "action": nxt.action,
            "checkin": nxt.checkin.ids if nxt.checkin else None}


cases = []
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)
    # 1. a middle run, every step, flow R: CR3 done, G3r asked (ask)
    run = new(ws / "a", ["edited_video"], "every_step")
    drive_to(run, "CR3", diagnosis=diagnosis("middle"), flows_at_a1a=["R"])
    complete(run, "CR3")
    cases.append(save(run, "middle_every_cr3_g3r", flow.next(run)))
    # 2. a middle run, Hands-off (flow R from the diagnosis alone): RB decided by rule, at CR5a (work)
    run = new(ws / "b", ["edited_video"], "hands_off")
    nxt = drive_to(run, "CR5a", diagnosis=diagnosis("middle"))
    assert any(d["checkin"] == "RB" and d["by"] == "rule" for d in state.load(run).decisions)
    cases.append(save(run, "middle_handsoff_cr5a", nxt))
    # 3. a hook run with a structural weakness, every step: flow R's steps done, at C2 (work)
    run = new(ws / "c", ["edited_video"], "every_step")
    cases.append(save(run, "hook_struct_at_c2",
                      drive_to(run, "C2", diagnosis=diagnosis("hook", STRUCTURAL), flows_at_a1a=["R"])))
    # 4. every output, every step, the live test activated: one measurement taken, at E4 (work)
    run = new(ws / "d", ALL_OUTPUTS, "every_step")
    drive_to(run, "E4", diagnosis=diagnosis("hook"))
    first = state.load(run).measurements_due[0]
    complete(run, "E4", measured=first, today=date(2026, 11, 5))
    assert state.load(run).measurements_done == [first]
    cases.append(save(run, "all_measuring_at_e4", flow.next(run, today=date(2026, 11, 5))))
    # 5. a run on the agent's guess (no TrendsMesh), every step, at A6 (work)
    run = new(ws / "e", ["creative_brief"], "every_step", evidence="guess")
    cases.append(save(run, "guess_run_at_a6", drive_to(run, "A6", diagnosis=diagnosis("hook"))))

(OUT / "expected.json").write_text(json.dumps({"saved_by": "tm 0.3.0 (9119b14)", "cases": cases},
                                              indent=2) + "\n", encoding="utf-8")
print(json.dumps(cases, indent=1))
