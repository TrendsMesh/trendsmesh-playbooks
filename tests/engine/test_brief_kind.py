"""Issue #136: creative-brief asks what the brief is for (`brief_kind`: ad or organic) before A0, so the doctor
knows whether to check Meta; an organic brief skips every ad step, and an ad brief every organic one."""

from datetime import date
from pathlib import Path

import pytest

from tm import brief_config, config, doctor, flow, state
from tm.flow import complete, decide, set_level
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

AD = ["review_pack", "briefs", "page"]
ORGANIC = ["organic_brief", "page"]
CB = "02-creative-brief"


def _new(tmp_path):
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    return RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


def test_the_kind_is_asked_first_and_before_a0(tmp_path):
    run = _new(tmp_path)
    nxt = flow.next(run)
    assert (nxt.step, nxt.action, nxt.checkin.ids) == ("A0", "ask", ["brief_kind"])
    assert nxt.checkin.name == "What is the brief for?" and nxt.checkin.choices == ["ad", "organic"]
    with pytest.raises(ValueError, match="brief_kind"):        # A0 waits for the kind
        complete(run, "A0")


def test_the_kind_is_never_decided_by_rule(tmp_path):
    run = _new(tmp_path)
    with pytest.raises(ValueError, match="not decided by rule"):
        decide(run, "brief_kind", "organic", by="rule", note="x")
    with pytest.raises(ValueError, match="takes one of"):
        decide(run, "brief_kind", "video", by="user", note=None, said="video")


@pytest.mark.parametrize("kind, intake", [("ad", "A1"), ("organic", "O1")])
def test_after_the_kind_a0_then_its_own_intake(tmp_path, kind, intake):
    run = _new(tmp_path)
    decide(run, "brief_kind", kind, by="user", note=None, said=f"an {kind} one")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A0", "work")
    want = "organic_brief,page" if kind == "organic" else "review_pack,briefs,page"
    assert want in nxt.message
    complete(run, "A0")
    assert state.load(run).step == intake
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == (intake, "work")


def test_an_organic_run_skips_every_ad_step_and_an_ad_run_every_organic_one(tmp_path):
    for kind, outputs in (("ad", AD), ("organic", ORGANIC)):
        run = _new(tmp_path / kind)
        decide(run, "brief_kind", kind, by="user", note=None, said=kind)
        s = state.load(run)
        s.outputs = list(outputs)
        state.save(run, s)
        set_level(run, "every_step")
        ids = [st.id for st in flow._picture(state.load(run)).app]
        if kind == "ad":
            assert ids == ["A0", "A1", "B1", "B2", "B3", "B4", "C1", "D1", "D3", "D2", "E1", "E2"]
        else:
            assert all(i == "A0" or i == "D2" or i.startswith("O") for i in ids), ids
            assert "B2" not in ids and "B4" not in ids


def test_a_run_whose_outputs_are_set_reads_its_kind_from_them(tmp_path):
    """A run started before issue #145's kind question (or set up directly) is an ad brief by its outputs, and is
    never asked the kind."""
    run = _new(tmp_path)
    s = state.load(run)
    s.outputs = list(AD)
    state.save(run, s)
    set_level(run, "every_step")
    nxt = flow.next(run)
    assert (nxt.step, nxt.action) == ("A0", "work") and (nxt.checkin is None or "brief_kind" not in nxt.checkin.ids)
    with pytest.raises(ValueError, match="outputs"):
        decide(run, "brief_kind", "organic", by="user", note=None, said="organic")


def test_config_takes_the_kind_and_its_outputs(tmp_path):
    run = _new(tmp_path)
    decide(run, "brief_kind", "organic", by="user", note=None, said="organic")
    brief_config.write_from_intake(run, {"level": "every_step"})
    cfg = config.load(run)
    assert cfg["brief"]["kind"] == "organic" and set(cfg["outputs"]) == set(ORGANIC)
    assert set(state.load(run).outputs) == set(ORGANIC)


def test_config_refuses_a_kind_its_outputs_do_not_fit(tmp_path):
    run = _new(tmp_path)
    decide(run, "brief_kind", "ad", by="user", note=None, said="an ad")
    brief_config.write_from_intake(run, {"level": "every_step", "outputs": ORGANIC})
    problems = {p.field: p.what for p in brief_config.validate(run)}
    assert "an ad brief" in problems["outputs"]
    brief_config.write_from_intake(run, {"level": "every_step", "brief": {"kind": "organic"}})
    assert config.load(run)["brief"]["kind"] == "ad"          # the user's answer at the check-in wins


def test_the_doctor_asks_no_meta_for_an_organic_brief(monkeypatch, tmp_path):
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks"))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))      # CI has no ~/.trendsmesh/paths.json
    r = doctor.check(set(ORGANIC), False, {"trendsmesh": "ok", "artifacts": "ok"}, playbook=CB)
    ids = [i.id for i in r.items]
    assert "mcp_meta" not in ids and "meta_mcp_enabled_for_account" not in ids
    assert "tier_animatic" in ids and "browser_for_animatics" in ids   # animatics on request (O6)
    ad = doctor.check(set(AD), False, {"trendsmesh": "ok", "meta": "ok", "artifacts": "ok"}, playbook=CB)
    assert "mcp_meta" in [i.id for i in ad.items]
