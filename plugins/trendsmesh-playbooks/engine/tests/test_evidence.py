"""Guess mode (issue #9): what a run's changes rest on, the notice, the A5/A7 checks, the register."""

import json
from datetime import date

import pytest

from tm import checkins, evidence, flow, library, playbooks, register, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

ALL_OUTPUTS = ["creative_brief", "edited_video", "ai_video", "live_test"]
GUESS_ROW = {"account": "act_1", "product": "mug", "market": "PL", "diagnosis": "hook",
             "trend": None, "evidence": "guess", "change": {"layer": "hook", "method": "opening_card"},
             "decision_metric": "cost per purchase", "result_vs_control": -0.1, "events": 40,
             "decision": "won", "variant": "B"}


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = list(ALL_OUTPUTS)
    s.test_plan = {"feasible": True, "variants": 1, "calculation": "a feasible R4 plan"}
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(r, s)
    return r


def _answer(run, nxt):
    choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
    if nxt.action == "ask":
        decide(run, nxt.checkin.card or nxt.checkin.ids[0], choice, by="user", note=None)
    else:
        decide(run, nxt.checkin.ids[0], choice, by="rule", note="test data")


def _until(run, pred, *, at_work=None):
    """Answer check-ins and finish work until pred(next) holds; return that next. `at_work` runs
    before each step's `tm done`."""
    later = date(2027, 1, 1)  # every measurement date has come
    for _ in range(120):
        nxt = flow.next(run, today=later)
        if pred(nxt):
            return nxt
        if nxt.action in ("ask", "auto"):
            _answer(run, nxt)
        elif nxt.action == "work":
            if at_work:
                at_work(nxt.step)
            if nxt.step == "E3":
                from tm import budget
                assert budget.spend(run, "test", 1, "live test") == 0
            if nxt.step == "E4":
                s = state.load(run)
                pending = [d for d in s.measurements_due if d not in s.measurements_done]
                if pending:
                    complete(run, "E4", measured=pending[0], today=later)
                else:  # R5: the guessed variant's row, with no trend
                    library.add_to_run(run.path, GUESS_ROW)
                continue
            complete(run, nxt.step)
        else:
            raise AssertionError(nxt)
    raise AssertionError("never got there")


def _guess_register(run):
    f = run.path / "04_final" / "change_register_v01.json"
    f.write_text(json.dumps({"items": [{"change": "new opening card", "basis": "guess",
                                        "because": "the account's own winners open with a question"}]}),
                 encoding="utf-8")
    register.record(run, f)


# --- tm evidence -----------------------------------------------------------------------------

def test_evidence_is_recorded_with_its_reason(run):
    evidence.record(run, "guess", "no Agent plan")
    evidence.record(run, "trendsmesh", "the user bought the Agent plan")
    s = state.load(run)
    assert s.evidence == "trendsmesh"
    assert [e["evidence"] for e in s.evidence_log] == ["guess", "trendsmesh"]
    assert s.evidence_log[0]["why"] == "no Agent plan"


@pytest.mark.parametrize("value,why", [("maybe", "x"), ("guess", " ")])
def test_evidence_refuses_bad_input(run, value, why):
    with pytest.raises(ValueError):
        evidence.record(run, value, why)


def test_evidence_cli(run, capsys):
    assert main(["evidence", "guess", "--run", str(run.path), "--why", "no plan", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["evidence"] == "guess"
    assert main(["evidence", "nope", "--run", str(run.path), "--why", "x"]) != 0


# --- A5: the run says what it rests on --------------------------------------------------------

def test_a5_message_asks_for_evidence_and_done_refuses_without_it(run):
    set_level(run, "hands_off")
    nxt = _until(run, lambda n: n.action == "work" and n.step == "A5")
    assert "tm evidence" in nxt.message
    with pytest.raises(ValueError, match="tm evidence"):
        complete(run, "A5")


def test_a5_trendsmesh_needs_a_saved_trend(run):
    set_level(run, "hands_off")
    _until(run, lambda n: n.action == "work" and n.step == "A5")
    evidence.record(run, "trendsmesh", "Agent plan")
    with pytest.raises(ValueError, match="02_research/trend_"):
        complete(run, "A5")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    complete(run, "A5")


def test_a5_guess_needs_no_trend_file(run):
    set_level(run, "hands_off")
    _until(run, lambda n: n.action == "work" and n.step == "A5")
    evidence.record(run, "guess", "the user skipped sign-in")
    complete(run, "A5")
    assert "tm evidence" not in (flow.next(run).message or "")


def test_a7_waits_for_a_checked_register(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no plan")
    _until(run, lambda n: n.action == "work" and n.step == "A7")
    with pytest.raises(ValueError, match="tm register check"):
        complete(run, "A7")
    _guess_register(run)
    complete(run, "A7")


# --- the notice and the guess-mode rule -------------------------------------------------------

def _walk_guess(run, level):
    set_level(run, level)
    evidence.record(run, "guess", "no Agent plan")
    seen = []

    def work(step):
        if step == "A7":
            _guess_register(run)

    def pred(n):
        if n.notice:
            seen.append((n.action, tuple(n.checkin.ids) if n.checkin else (), n.step))
        return n.action == "done"

    done = _until(run, pred, at_work=work)
    return seen, done


@pytest.mark.parametrize("level", ["every_step", "big_calls"])
def test_guess_run_notices_on_direction_launch_and_report(run, level):
    seen, done = _walk_guess(run, level)
    assert done.notice == evidence.NOTICE
    asked = [ids for action, ids, _ in seen if action == "ask"]
    assert any("G2" in ids for ids in asked)
    assert any("G11" in ids for ids in asked)
    # nowhere else: every noticed check-in holds G2 or G11
    assert all({"G2", "G11"} & set(ids) for action, ids, _ in seen if action != "done")


def test_hands_off_guess_run_uses_the_guess_rule_and_reports_it(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no Agent plan")
    nxt = _until(run, lambda n: n.action == "auto" and "G2" in n.checkin.ids)
    assert "evergreen" in nxt.message and "rising" not in nxt.checkin.rule
    decide(run, "G2", "ok", by="rule", note="own winners")
    entry = [d for d in state.load(run).decisions if d["checkin"] == "G2"][-1]
    assert "evergreen" in entry["rule"]


def test_trendsmesh_run_has_no_notice_and_the_trend_rule(run):
    set_level(run, "hands_off")
    evidence.record(run, "trendsmesh", "Agent plan")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    nxt = _until(run, lambda n: n.action == "auto" and "G2" in n.checkin.ids)
    assert nxt.notice is None and "rising" in nxt.checkin.rule


def test_next_json_carries_the_notice(run, capsys):
    set_level(run, "every_step")
    evidence.record(run, "guess", "no plan")
    _until(run, lambda n: n.action == "ask" and "G2" in n.checkin.ids)
    assert main(["next", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["notice"] == evidence.NOTICE


def test_hands_off_guess_run_notices_only_in_the_final_report(run):
    seen, done = _walk_guess(run, "hands_off")
    assert done.notice == evidence.NOTICE
    assert [action for action, _, _ in seen] == ["done"]


@pytest.mark.parametrize("level", ["every_step", "big_calls", "hands_off"])
def test_refresh_ad_final_report_still_repeats_the_notice(run, level):
    """Creative brief says its notice once (Task 5 Step 0); refresh-ad's final report still carries
    it at every level, after G2 and G11 were asked as well."""
    set_level(run, level)
    evidence.record(run, "guess", "no Agent plan")
    s = state.load(run)
    assert evidence.notice_for(s, None, done=True) == evidence.NOTICE
    assert evidence.notice_for(s, ["G2"]) == evidence.NOTICE
    assert evidence.notice_for(s, ["G11"]) == evidence.NOTICE
    assert evidence.notice_for(s, ["G3"]) is None and evidence.notice_for(s, None) is None


def test_trendsmesh_run_has_no_notice_at_the_end(run):
    set_level(run, "hands_off")
    evidence.record(run, "trendsmesh", "Agent plan")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")

    def work(step):
        if step == "A7":
            f = run.path / "04_final" / "change_register_v01.json"
            f.write_text(json.dumps({"items": [{"change": "hook", "basis": "proof",
                                                "sources": ["02_research/trend_42.json"]}]}), encoding="utf-8")
            register.record(run, f)
        if step == "E4" and not [d for d in state.load(run).measurements_due
                                 if d not in state.load(run).measurements_done]:
            library.add_to_run(run.path, {**GUESS_ROW, "evidence": "trendsmesh",
                                          "trend": {"id": "42", "type": "hook_trend", "status_on_test_day": "rising"}})

    done = _until(run, lambda n: n.action == "done", at_work=work)
    assert done.notice is None


def test_a_run_that_ends_early_gets_no_hook_notice(run):
    set_level(run, "every_step")
    evidence.record(run, "guess", "no plan")
    s = state.load(run)
    s.status, s.ended = "done", "The refresh is not supported for this stage."
    state.save(run, s)
    assert flow.next(run).notice is None


# --- changing the evidence -------------------------------------------------------------------

def test_switching_clears_a_register_checked_before_a7_is_done(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no plan")
    _until(run, lambda n: n.action == "work" and n.step == "A7")
    _guess_register(run)
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    evidence.record(run, "trendsmesh", "the user bought the plan")
    assert state.load(run).register is None
    with pytest.raises(ValueError, match="tm register check"):
        complete(run, "A7")


def test_switching_to_trendsmesh_after_a5_needs_a_saved_trend(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no plan")
    _until(run, lambda n: n.action == "work" and n.step == "A6")
    with pytest.raises(ValueError, match="02_research/trend_"):
        evidence.record(run, "trendsmesh", "the user bought the plan")
    assert state.load(run).evidence == "guess"


def test_evidence_is_fixed_once_the_register_is_done(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no plan")

    def work(step):
        if step == "A7":
            _guess_register(run)

    _until(run, lambda n: n.action == "work" and n.step == "B1", at_work=work)
    for value in ("trendsmesh", "guess"):
        with pytest.raises(ValueError, match="already decided"):
            evidence.record(run, value, "late change")


def test_evidence_refused_on_a_finished_run(run):
    s = state.load(run)
    s.status = "done"
    state.save(run, s)
    with pytest.raises(ValueError, match="done"):
        evidence.record(run, "guess", "x")


def test_an_old_run_past_a5_is_told_to_record_evidence(run):
    set_level(run, "hands_off")
    evidence.record(run, "guess", "no plan")
    _until(run, lambda n: n.action == "work" and n.step == "A6")
    raw = json.loads((run.path / "run.json").read_text(encoding="utf-8"))
    for k in ("evidence", "evidence_log", "register"):
        raw.pop(k)
    (run.path / "run.json").write_text(json.dumps(raw), encoding="utf-8")  # as v1 wrote it
    nxt = flow.next(run)
    assert nxt.step == "A6" and "tm evidence" in nxt.message


# --- tm register check -----------------------------------------------------------------------

def _reg(run, items):
    f = run.path / "03_wip" / "register.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    return f


def test_register_needs_evidence_first(run):
    with pytest.raises(ValueError, match="tm evidence"):
        register.record(run, _reg(run, [{"change": "x", "basis": "guess", "because": "y"}]))


def test_register_proof_needs_a_saved_trendsmesh_answer(run):
    evidence.record(run, "trendsmesh", "Agent plan")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    (run.path / "02_research" / "ad_library_summary_v01.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="saved TrendsMesh answer"):
        register.record(run, _reg(run, [{"change": "hook", "basis": "proof",
                                         "sources": ["02_research/ad_library_summary_v01.md"]}]))
    with pytest.raises(ValueError, match="not a file"):
        register.record(run, _reg(run, [{"change": "hook", "basis": "proof",
                                         "sources": ["02_research/trend_99.json"]}]))
    reg = register.record(run, _reg(run, [
        {"change": "hook", "basis": "proof", "sources": ["02_research/trend_42.json"]},
        {"change": "headline", "basis": "guess", "because": "no data on headlines"}]))
    assert (reg["proof"], reg["guess"]) == (1, 1)
    assert state.load(run).register["file"] == "03_wip/register.json"


def test_register_guess_run_has_no_proof(run):
    evidence.record(run, "guess", "no plan")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")  # even with a file
    with pytest.raises(ValueError, match="no TrendsMesh data"):
        register.record(run, _reg(run, [{"change": "hook", "basis": "proof",
                                         "sources": ["02_research/trend_42.json"]}]))


@pytest.mark.parametrize("items,match", [
    ([], "at least one"),
    ([{"basis": "guess", "because": "y"}], "needs a `change`"),
    ([{"change": "x", "basis": "maybe"}], "proof or guess"),
    ([{"change": "x", "basis": "guess"}], "what it rests on"),
    ([{"change": "x", "basis": "guess", "sources": ["../../outside.json"]}], "not a file in this run"),
])
def test_register_refuses_bad_items(run, items, match):
    evidence.record(run, "guess", "no plan")
    (run.path.parent / "outside.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        register.record(run, _reg(run, items))


def test_register_takes_an_absolute_path_inside_the_run(run):
    evidence.record(run, "trendsmesh", "Agent plan")
    (run.path / "02_research" / "trend_42.json").write_text("{}", encoding="utf-8")
    reg = register.record(run, _reg(run, [{"change": "hook", "basis": "proof",
                                           "sources": [str(run.path / "02_research" / "trend_42.json")]}]))
    assert reg["proof"] == 1


def test_register_refuses_a_symlink_dressed_as_a_trend(run):
    evidence.record(run, "trendsmesh", "Agent plan")
    mine = run.path / "03_wip" / "mine.json"
    mine.write_text("{}", encoding="utf-8")
    (run.path / "02_research" / "trend_fake.json").symlink_to(mine)
    with pytest.raises(ValueError, match="saved TrendsMesh answer"):
        register.record(run, _reg(run, [{"change": "hook", "basis": "proof",
                                         "sources": ["02_research/trend_fake.json"]}]))


def test_register_cli(run, capsys):
    evidence.record(run, "guess", "no plan")
    f = _reg(run, [{"change": "x", "basis": "guess", "because": "y"}])
    assert main(["register", "check", "--run", str(run.path), "--file", str(f), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["register"]["guess"] == 1
    bad = _reg(run, [{"change": "x", "basis": "proof", "sources": []}])
    assert main(["register", "check", "--run", str(run.path), "--file", str(bad)]) == 1


# --- the results library ---------------------------------------------------------------------

def test_library_takes_a_guess_row_without_a_trend(tmp_path):
    library.add(tmp_path, {**GUESS_ROW, "run": "r1"})
    assert library.summary(tmp_path, "mug", "PL") == {"method:opening_card": {"won": 1, "lost": 0}}


def test_a_guess_runs_row_takes_its_evidence_from_the_run(run, tmp_path):
    evidence.record(run, "guess", "no plan")
    row = {k: v for k, v in GUESS_ROW.items() if k != "evidence"}
    ws = library.add_to_run(run.path, row)
    assert library.rows(ws)[-1]["evidence"] == "guess"


@pytest.mark.parametrize("bad", [
    {"trend": {"id": "made-up", "type": "hook_trend", "status_on_test_day": "rising"}},
    {"evidence": "trendsmesh", "trend": {"id": "x", "type": "hook_trend", "status_on_test_day": "rising"}},
])
def test_a_guess_runs_row_cannot_claim_a_trend(run, bad):
    evidence.record(run, "guess", "no plan")
    with pytest.raises(ValueError, match="no TrendsMesh data"):
        library.add_to_run(run.path, {**GUESS_ROW, **bad})


@pytest.mark.parametrize("row", [
    {**GUESS_ROW, "evidence": "trendsmesh"},          # TrendsMesh rows still need their trend
    {k: v for k, v in GUESS_ROW.items() if k != "evidence"},  # no evidence reads as trendsmesh
    {**GUESS_ROW, "evidence": "maybe"},
])
def test_library_refuses_a_missing_trend_outside_guess_mode(tmp_path, row):
    with pytest.raises(ValueError):
        library.add(tmp_path, {**row, "run": "r1"})


def test_evidence_refuses_a_run_at_an_unknown_step(run):
    s = state.load(run)
    s.step = "Z9"
    state.save(run, s)
    with pytest.raises(ValueError, match="unknown step"):
        evidence.record(run, "guess", "x")


# --- other playbooks (creative brief: plan Task 4) ----------------------------------------------

def test_every_guess_playbook_has_an_evidence_window():
    guessing = {pb.id for pb in playbooks.all_playbooks() if pb.guess}
    assert guessing and set(flow._EVIDENCE_WINDOW) == guessing == set(evidence.NOTICES)
    for pb in guessing:
        first, last = flow._EVIDENCE_WINDOW[pb]
        order = [st.id for st in flow.steps(pb)]
        assert first in order and last in order and order.index(first) < order.index(last), pb
        cat = checkins.load(playbook=pb)
        assert evidence.NOTICES[pb].at <= set(cat.checkins), pb   # the notice sits on real check-ins


def test_trend_research_still_refuses_evidence(tmp_path, capsys, monkeypatch):
    (tmp_path / "ws").mkdir()
    tr = RunFolder.create(tmp_path / "ws", "beauty", date(2026, 11, 7), playbook=TREND_RESEARCH)
    with pytest.raises(ValueError) as no:
        evidence.record(tr, "guess", "no Agent plan")
    # only playbooks whose skill ships are named: the plugin ships refresh-ad and creative-brief
    assert str(no.value) == "Guess mode is part of Refresh an ad and Creative brief, not of Trend research."
    with monkeypatch.context() as m:
        root = tmp_path / "skills"
        for skill in ("refresh-ad", "trend-research"):
            (root / skill).mkdir(parents=True)
            (root / skill / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
        m.setattr(playbooks, "skills_root", lambda: root)
        with pytest.raises(ValueError) as no:
            evidence.record(tr, "guess", "no Agent plan")
        assert str(no.value) == "Guess mode is part of Refresh an ad, not of Trend research."
    assert main(["evidence", "guess", "--run", str(tr.path), "--why", "no plan", "--json"]) == 1
    capsys.readouterr()
    s = state.load(tr)
    assert s.evidence is None and s.evidence_log == []
    s.evidence = "guess"   # even a hand-edited run.json gets no notice
    assert evidence.notice_for(s, ["G2"], done=True) is None
