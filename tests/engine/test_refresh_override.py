"""Issue #143 item 1: the user overrules the diagnosis at G1a (`tm decide G1a override --stage S --said ...`), the
"too little data" diagnosis (item 3), and the line every later money ask carries (owner decision #148 line 4)."""

import json
from datetime import date

import pytest
from conftest import trend_steps_ready

from tm import budget, changes, flow, r2, state
from tm.cli import main
from tm.flow import complete, decide, set_level
from tm.runfolder import RunFolder

ALL_OUTPUTS = ["creative_brief", "edited_video", "ai_video", "live_test"]
LEVELS = ("every_step", "big_calls", "hands_off")
SAID = "The landing page has not changed; the ad is worn out"


@pytest.fixture
def run(tmp_path):
    ws = tmp_path / "Moje reklamy"
    ws.mkdir()
    r = RunFolder.create(ws, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = list(ALL_OUTPUTS)
    s.test_plan = {"feasible": True, "variants": 1, "calculation": "a feasible R4 plan"}
    s.budgets = {"ai_usd": 50.0, "voice_credits": 50000.0, "test": 500.0}
    state.save(r, s)
    trend_steps_ready(r)
    return r


def _at_a1a(run, level):
    set_level(run, level)
    for _ in range(40):
        nxt = flow.next(run)
        if nxt.action in ("ask", "auto"):
            cid = nxt.checkin.card or nxt.checkin.ids[0]
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            if nxt.action == "ask":
                decide(run, cid, choice, by="user", note=None, said="ok")
            else:
                decide(run, nxt.checkin.ids[0], choice, by="rule", note="test data")
            continue
        assert nxt.action == "work", nxt
        if nxt.step == "A1a":
            return nxt
        complete(run, nxt.step)
    raise AssertionError("never reached A1a")


def _landing():
    return r2.Diagnosis(stage="landing", refresh=False, evidence={"conversion": (0.05, 0.02)})


def _cli(run, *extra):
    return main(["decide", "G1a", "override", "--run", str(run.path), "--json", *extra])


# --- item 1: the override ------------------------------------------------------------------------

@pytest.mark.parametrize("level", LEVELS)
def test_the_user_overrules_a_landing_diagnosis(run, level, capsys):
    _at_a1a(run, level)
    r2.record(run, _landing())
    nxt = flow.next(run)
    assert nxt.checkin.ids == ["G1a"]
    assert "tm decide G1a override --stage" in nxt.message and "--said" in nxt.message
    assert _cli(run, "--stage", "fatigue", "--said", SAID) == 0
    s = state.load(run)
    assert s.status == "active"
    d = s.diagnosis
    assert d["target_stage"] == "fatigue"
    assert d["override"] == {"stage": "fatigue", "said": SAID, "by": "user", "diagnosed_stage": "landing"}
    assert s.decisions[-1]["checkin"] == "G1a" and s.decisions[-1]["choice"] == "override"
    assert s.decisions[-1]["said"] == SAID and s.decisions[-1]["stage"] == "fatigue"
    assert flow._blocking(s) is None
    complete(run, "A1a")
    assert state.load(run).step == "A2"


def test_an_override_needs_the_users_words_and_a_stage(run, capsys):
    _at_a1a(run, "every_step")
    r2.record(run, _landing())
    assert _cli(run, "--stage", "fatigue") == 1
    assert "--said" in capsys.readouterr().out
    assert _cli(run, "--said", SAID) == 1
    assert "--stage" in capsys.readouterr().out
    assert _cli(run, "--stage", "landing", "--said", SAID) == 1     # not a refreshable stage
    assert main(["decide", "G1a", "override", "--by", "rule", "--note", "x", "--stage", "hook",
                 "--run", str(run.path)]) == 1
    assert "Only the user" in capsys.readouterr().out
    assert state.load(run).diagnosis.get("override") is None


def test_stage_is_only_for_the_override(run, capsys):
    _at_a1a(run, "every_step")
    r2.record(run, _landing())
    assert main(["decide", "G1a", "do_not_refresh", "--stage", "hook", "--said", "no", "--run", str(run.path)]) == 1
    assert "--stage" in capsys.readouterr().out


def test_an_override_needs_a_supported_change_for_the_stage(run, capsys):
    _at_a1a(run, "every_step")
    changes.record_material(run, "talking_head")            # a talking head: only its middle is re-cut
    r2.record(run, _landing())
    assert _cli(run, "--stage", "hook", "--said", SAID) == 1
    out = capsys.readouterr().out
    assert "Refreshing the opening isn't supported yet for this ad; pick another stage." in out
    assert _cli(run, "--stage", "middle", "--said", SAID) == 0
    s = state.load(run)
    assert s.diagnosis["target_stage"] == "middle" and flow.flow_on(s, "R")


def test_an_override_is_accepted_over_a_refreshable_diagnosis_too(run):
    _at_a1a(run, "every_step")
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True, evidence={"hook_rate": (0.3, 0.2)}))
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="promise_cta")
    assert state.load(run).diagnosis["target_stage"] == "promise_cta"


def test_the_card_does_not_take_the_override(run):
    _at_a1a(run, "big_calls")
    r2.record(run, _landing())
    with pytest.raises(ValueError, match="G1a itself"):
        decide(run, "pick_the_ad", "override", by="user", note=None, said=SAID, stage="hook")
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="hook")   # at A1a, before the card
    assert state.load(run).diagnosis["target_stage"] == "hook"


def test_a_new_diagnosis_or_material_keeps_the_override(run):
    _at_a1a(run, "every_step")
    r2.record(run, _landing())
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="hook")
    changes.record_material(run, "text_cards")
    assert state.load(run).diagnosis["target_stage"] == "hook"
    r2.record(run, r2.Diagnosis(stage="account", refresh=False))
    d = state.load(run).diagnosis
    assert d["target_stage"] == "hook" and d["override"]["diagnosed_stage"] == "account"
    changes.record_material(run, "static")                    # no edit for the opening now: G1a again
    nxt = flow.next(run)
    assert nxt.checkin.ids == ["G1a"] and "pick another stage" in nxt.message


def test_do_not_refresh_still_ends_the_run(run):
    _at_a1a(run, "every_step")
    r2.record(run, _landing())
    decide(run, "G1a", "do_not_refresh", by="user", note=None, said="ok, stop")
    assert state.load(run).status == "done"


# --- item 3: too little data ------------------------------------------------------------------------

def test_too_little_data_waits_for_the_users_stage(run, capsys):
    _at_a1a(run, "every_step")
    assert main(["diagnose", "--run", str(run.path), "--too-little-data", "--json"]) == 0
    d = state.load(run).diagnosis
    assert d["too_little_data"] is True and d["refresh"] is False and d["stage"] == "unclear"
    nxt = flow.next(run)
    assert nxt.checkin.ids == ["G1a"] and "too little data" in nxt.message
    assert "tm decide G1a override --stage" in nxt.message
    decide(run, "G1a", "override", by="user", note=None, said="refresh it anyway, the opening", stage="hook")
    assert flow.next(run).action == "work"


def test_too_little_data_takes_both_windows_or_none(run, capsys):
    _at_a1a(run, "every_step")
    w = {"start": "2026-10-01", "stop": "2026-10-07", "spend": 10, "results": 2, "impressions": 1000, "p25": 300,
         "thruplay": 100, "clicks_est": 10, "frequency": 1.2, "cpm": 10}
    assert main(["diagnose", "--run", str(run.path), "--too-little-data", "--peak", json.dumps(w)]) == 1
    assert main(["diagnose", "--run", str(run.path), "--peak", json.dumps(w), "--latest", json.dumps(w)]) == 1
    assert "--account-ratio" in capsys.readouterr().out


# --- owner decision #148 line 4: every later money ask says so -----------------------------------

def test_every_later_money_ask_says_the_run_goes_against_the_diagnosis(run, capsys):
    _at_a1a(run, "every_step")
    r2.record(run, _landing())
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="hook")
    line = flow.against_diagnosis(state.load(run))
    assert "against the diagnosis" in line and "the landing page" in line and SAID in line
    seen = set()
    for _ in range(80):
        nxt = flow.next(run)
        if nxt.action in ("ask", "auto"):
            cid = nxt.checkin.ids[0]
            if any(flow.checkins.load().checkins[c].money for c in nxt.checkin.ids):
                assert "against the diagnosis" in nxt.message, cid
                seen.add(cid)
            choice = nxt.checkin.choices[0] if nxt.checkin.choices else "ok"
            if cid == "G11":
                break
            decide(run, nxt.checkin.card or cid, choice, by="user", note=None, said="ok")
            continue
        if nxt.action != "work":
            break
        if nxt.step == "E3":
            s = state.load(run)
            s.spend["test"] = 1.0
            state.save(run, s)
        complete(run, nxt.step)
    assert {"G6", "G10"} <= seen
    assert main(["budget", "approve", "--run", str(run.path), "ai_usd", "60", "--json"]) in (0, 2)
    out = capsys.readouterr().out
    assert "against the diagnosis" in out


def test_the_live_test_estimate_says_it_too(run):
    _at_a1a(run, "every_step")
    s = state.load(run)
    s.test_plan = None
    state.save(run, s)
    r2.record(run, _landing())
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="hook")
    complete(run, "A1a")
    nxt = flow.next(run)
    assert nxt.step == "A2" and "tm r4 --estimate" in nxt.message and "against the diagnosis" in nxt.message


def test_no_line_without_an_override(run):
    _at_a1a(run, "every_step")
    r2.record(run, r2.Diagnosis(stage="hook", refresh=True))
    assert flow.against_diagnosis(state.load(run)) is None
