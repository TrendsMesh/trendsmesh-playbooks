"""How these fixtures were made: runs driven by the 0.2.1 engine itself (commit 051c428), each
run.json saved with 0.2.1's own `tm next` answer in expected.json. test_flow.py's
test_old_run_without_targets_or_r_resumes_at_same_step loads them into the current engine.

    git archive 051c428 plugins/trendsmesh-playbooks/engine/src plugins/trendsmesh-playbooks/data \
        | tar -x -C <old>
    PYTHONPATH=<old>/plugins/trendsmesh-playbooks/engine/src python -I make_v021_runs.py <out dir>
(with -I, put <old>/.../engine/src on sys.path by hand.) Not collected by pytest.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from tm import flow, r2, state, changes, __version__
from tm.flow import complete, decide, set_level
from tm.runfolder import RunFolder

assert __version__ == "0.2.1", __version__
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def ready(run):
    (run.path / "02_research" / "trend_t1.json").write_text(json.dumps({"id": "t1"}), encoding="utf-8")
    s = state.load(run)
    s.evidence = "trendsmesh"
    s.register = {"file": "04_final/change_register_v01.json", "proof": 1, "guess": 0}
    s.test_plan = {"feasible": True, "variants": 1, "calculation": "a feasible R4 plan"}
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(run, s)


def settle(run):
    for _ in range(50):
        nxt = flow.next(run)
        if nxt.action in ("ask", "auto"):
            cid = nxt.checkin.card or nxt.checkin.ids[0]
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            if cid == "G1a" or "G1a" in nxt.checkin.ids:
                choice = "refresh"
            if nxt.action == "ask":
                decide(run, cid, choice, by="user", note=None)
            else:
                decide(run, nxt.checkin.ids[0], choice, by="rule", note="fixture")
        else:
            return nxt
    raise AssertionError("kept asking")


def drive_to(run, step, *, stage="hook", material="vo_captions", answer_after=True):
    for _ in range(80):
        nxt = settle(run) if answer_after else flow.next(run)
        if nxt.step == step and nxt.action == "work":
            return nxt
        assert nxt.action == "work", nxt
        if nxt.step == "A1a" and state.load(run).diagnosis is None:
            r2.record(run, r2.Diagnosis(stage=stage, refresh=True, evidence={"hook_rate": (0.3, 0.2)}))
            continue
        if nxt.step == "A3" and state.load(run).material is None:
            changes.record_material(run, material)
        complete(run, nxt.step)
    raise AssertionError(f"never reached {step}")


def new(ws, outputs, level, flows=()):
    run = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(run)
    s.outputs = list(outputs)
    s.flows = list(flows)
    state.save(run, s)
    ready(run)
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
    # 1. edited video with flow V, every step, at C2 (work)
    (ws / "a").mkdir()
    run = new(ws / "a", ["edited_video"], "every_step", ["V"])
    cases.append(save(run, "edited_flow_v_at_c2", drive_to(run, "C2")))
    # 2. every output, Just the big calls, flow V, at V3 (work)
    (ws / "b").mkdir()
    run = new(ws / "b", ["creative_brief", "edited_video", "ai_video", "live_test"], "big_calls", ["V"])
    cases.append(save(run, "all_flow_v_at_v3", drive_to(run, "V3")))
    # 3. edited video, Hands-off, no flow, at C1 (work)
    (ws / "c").mkdir()
    run = new(ws / "c", ["edited_video"], "hands_off")
    cases.append(save(run, "edited_handsoff_c1", drive_to(run, "C1")))
    # 4. edited video + live test, every step, C4 done: G5 asked (ask)
    (ws / "d").mkdir()
    run = new(ws / "d", ["edited_video", "live_test"], "every_step")
    drive_to(run, "C4")
    complete(run, "C4")
    cases.append(save(run, "edited_c4_g5_asked", flow.next(run)))
    # 5. every output, every step, at E1 (work), after C2-C4 and D1-D5
    (ws / "e").mkdir()
    run = new(ws / "e", ["creative_brief", "edited_video", "ai_video", "live_test"], "every_step")
    cases.append(save(run, "all_outputs_at_e1", drive_to(run, "E1")))
    # 6. a middle diagnosis ended by 0.2.1 as not supported (done)
    (ws / "f").mkdir()
    run = new(ws / "f", ["edited_video"], "every_step")
    for _ in range(10):
        nxt = settle(run)
        if nxt.step == "A1a":
            break
        complete(run, nxt.step)
    r2.record(run, r2.Diagnosis(stage="middle", refresh=True, evidence={"hook_rate": (0.3, 0.3)}))
    decide(run, "G1a", "do_not_refresh", by="user", note=None)
    cases.append(save(run, "middle_not_supported", flow.next(run)))

(OUT / "expected.json").write_text(json.dumps({"saved_by": "tm 0.2.1 (051c428)", "cases": cases},
                                              indent=2) + "\n", encoding="utf-8")
print(json.dumps(cases, indent=1))
