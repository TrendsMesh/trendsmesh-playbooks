"""Issue #142 item 2: a trend counts as used once its production run delivered a final video or script; one idea per
batch may build on a used trend that is still rising, with a new angle (`plugin.new_angle`); the shortlist keeps used
trends, marked; the proposals page says which video the trend was in."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tm import i18n, organic_proposals, organic_research, playbooks, shortlist, trends
from tm.organic_pages import proposals as proposals_page
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

T1, T2, T3 = "a" * 12, "b" * 12, "c" * 12
TODAY = date(2026, 11, 20)


def _row(tid, run, **kw):
    return {"trend_id": tid, "name": f"trend {tid[0]}", "kind": "topic_trend", "run": run, "video": "m1",
            "used": "2026-11-12", **kw}


def _production(ws, name, *, final=None, script=False, production="animation"):
    """A production run of the channel `ch`, with its 00_raw/proposal.json, and a final video or script if asked."""
    run = RunFolder.create(ws, name, date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    kept = {"proposal": {"id": "m1", "plugin": {"production": production}}, "channel": "ch",
            "used": [{k: v for k, v in _row(T1, run.path.name).items()} | {"production": production}]}
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps(kept), encoding="utf-8")
    if final:
        (run.path / "04_final" / final).write_bytes(b"mp4")
    if script:
        (run.path / "04_final" / "m1_script_pl_v01").mkdir(parents=True)
        (run.path / "04_final" / "m1_script_pl_v01" / "index.html").write_text("x", encoding="utf-8")
    return run


def test_a_trend_counts_only_once_its_run_delivered_a_video_or_a_script(tmp_path):
    ws = tmp_path / "ws"
    made = _production(ws, "ch-m1", final="m1_final_v01.mp4", production="stills_motion")
    scripted = _production(ws, "ch-m2", script=True)
    started = _production(ws, "ch-m3")                         # started, never produced
    organic_research.record_used(ws, "ch", [_row(T1, made.path.name), _row(T2, scripted.path.name),
                                            _row(T3, started.path.name)])
    found = organic_research.used(ws, "ch")
    assert sorted(found) == [T1, T2]
    assert found[T1]["production"] == "stills_motion" and found[T2]["production"] == "animation"
    organic_research.record_used(ws, "ch", [_row(T3, "2026-01-01_gone", final="04_final/m1_final_v01.mp4")])
    assert T3 in organic_research.used(ws, "ch")              # a row written at delivery counts as it is


def test_the_used_trends_without_some_runs(tmp_path):
    """#148 line 99: the flexible day asks what the week's other days built on before the week, so the week's own
    slot runs can be left out; an earlier row of the same trend then shows."""
    ws = tmp_path / "ws"
    organic_research.record_used(ws, "ch", [_row(T1, "2026-11-01_ch-m1", final="04_final/m1_final_v01.mp4"),
                                            _row(T1, "2026-11-09_ch-w1", final="04_final/w1_final_v01.mp4"),
                                            _row(T2, "2026-11-09_ch-w1", final="04_final/w1_final_v01.mp4")])
    assert organic_research.used(ws, "ch")[T1]["run"] == "2026-11-09_ch-w1"
    before = organic_research.used(ws, "ch", {"2026-11-09_ch-w1"})
    assert sorted(before) == [T1] and before[T1]["run"] == "2026-11-01_ch-m1"


def test_used_hits_skip_a_series_and_the_ideas_own_run():
    hits = organic_proposals.used_hits(_p("m1", [T1, T3]), [T1, T3], USED, None)
    assert [tid for tid, _ in hits] == [T1]
    assert organic_proposals.used_hits(_p("m1", [T1], series="Ranks"), [T1], USED, None) == []
    assert organic_proposals.used_hits(_p("m1", [T1]), [T1], USED, "2026-11-12_ch-m1") == []


def test_the_used_rows_are_written_when_the_final_is_delivered_once(tmp_path):
    ws = tmp_path / "ws"
    run = _production(ws, "ch-m1", final="m1_final_v01.mp4")
    assert organic_research.used(ws, "ch") == {}              # the start recorded nothing
    assert organic_research.record_delivered(run, "04_final/m1_final_v01.mp4") == 1
    assert organic_research.record_delivered(run, "04_final/m1_final_v02.mp4") == 0   # once per trend and run
    row = organic_research.used(ws, "ch")[T1]
    assert row["final"] == "04_final/m1_final_v01.mp4" and row["production"] == "animation"
    other = RunFolder.create(ws, "no-proposal", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    assert organic_research.record_delivered(other, "04_final/x_final_v01.mp4") == 0   # an idea run's own


def _p(pid, tids, **plugin):
    return {"id": pid, "title": pid.upper(), "plugin": {"series": None, **plugin}, "trends": [{"id": t} for t in tids]}


USED = {T1: _row(T1, "2026-11-12_ch-m1", production="animation"), T2: _row(T2, "2026-11-10_ch-m4",
                                                                           production="ai_footage")}
ANGLE = {"previous": "2026-11-12_ch-m1", "differs": ["hook", "format"], "why": "a POV on another topic"}


def _check(proposals, rising=(T1, T2), own=None):
    out = []
    organic_proposals.used_rule(proposals, {p["id"]: [t["id"] for t in p["trends"]] for p in proposals},
                                {p["id"]: USED for p in proposals}, own or {}, lambda tid: tid in rising, out)
    return out


def test_one_used_trend_per_batch_with_a_new_angle():
    assert _check([_p("m1", [T1], new_angle=ANGLE), _p("m2", [T3])]) == []
    found = _check([_p("m1", [T1], new_angle=ANGLE), _p("m2", [T2], new_angle=ANGLE)])
    assert [(p.field, p.what) for p in found] == [(
        "m2.trends", "Only one idea per batch may build on a trend this channel already used; “M2” (m2) is the "
        "second. Use another trend.")]
    assert _check([_p("m1", [T1], series="Ranks"), _p("m2", [T2], new_angle=ANGLE)]) == []   # a series continues


def test_a_used_trend_without_a_new_angle_is_refused():
    for angle in (None, {}, {"previous": "x", "differs": [], "why": "w"}, {**ANGLE, "differs": ["sound"]},
                  {**ANGLE, "why": " "}):
        found = _check([_p("m1", [T1], **({"new_angle": angle} if angle is not None else {}))])
        assert [(p.field, p.what) for p in found] == [(
            "m1.plugin.new_angle", "“M1” (m1) builds on trend a, which the channel used in 2026-11-12_ch-m1 "
            "(2026-11-12, an animation): say in plugin.new_angle what is new (topic, hook or format).")], angle


def test_a_used_trend_no_longer_rising_is_refused():
    found = _check([_p("m1", [T1], new_angle=ANGLE)], rising=())
    assert [(p.field, p.what) for p in found] == [
        ("m1.trends", "trend a is no longer rising, so a second video on it is not proposed.")]


def test_the_ideas_own_run_is_not_another_use():
    assert _check([_p("m1", [T1])], own={"m1": "2026-11-12_ch-m1"}) == []


def test_still_rising_is_rising_with_evidence_in_the_recent_days(tmp_path):
    run = RunFolder.create(tmp_path / "ws", "ideas", TODAY, playbook=ORGANIC_VIDEO)
    for tid, momentum, seen in ((T1, "rising", "2026-11-18"), (T2, "rising", "2026-10-01"),
                                (T3, "holding", "2026-11-19")):
        trends.save_answer(run, "get_trend", {"trend_id": tid}, {"id": tid, "kind": "topic_trend", "momentum": momentum,
                                                                 "examples": [{"published": seen}]})
    rising = [tid for tid in (T1, T2, T3) if organic_proposals.still_rising(run, tid, 7, TODAY)]
    assert rising == [T1]


def test_the_shortlist_keeps_used_trends_marked():
    scored = {k: [] for k in shortlist.LISTS}
    scored["topics"] = [{"id": T1, "name": "a", "flags": []}, {"id": T3, "name": "c", "flags": []}]
    shortlist.mark_used(scored, {T1: USED[T1]})
    assert scored["topics"][0]["used"] == {"run": "2026-11-12_ch-m1", "date": "2026-11-12",
                                           "production_type": "animation"}
    assert "used" not in scored["topics"][1] and len(scored["topics"]) == 2


@pytest.mark.parametrize("lang, line", [
    ("en", "Was in the video of 12.11 (an animation); now a POV on another topic"),
    ("pl", "Był w filmie z 12.11 (animacja); teraz a POV on another topic")])
def test_the_page_says_which_video_the_trend_was_in(lang, line):
    p = _p("m1", [T1], new_angle=ANGLE)
    tr = i18n.translator(lang)
    got = proposals_page.used_line(p, USED, tr)
    assert got.split("(")[0] == line.split("(")[0] and got.endswith(line.rsplit(")", 1)[1])
    assert proposals_page.used_line(_p("m2", [T3]), USED, tr) is None


def test_the_runs_folder_is_organic_videos():
    assert organic_research.run_folder(Path("/w"), "r1").as_posix() == f"/w/runs/{playbooks.get(ORGANIC_VIDEO).id}/r1"
