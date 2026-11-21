"""Issue #143 item 5 (the diagnosis report when the run ends at G1a) and the run page's lines of items 1 and 3: the
override line, the money stages against the diagnosis, other products set apart, "too little data", and a done
run with G1a settled and a "Done" stage."""

import json
import re
from datetime import date

import pytest

from tm import changes, flow, r2, run_page, state
from tm.cli import main
from tm.flow import decide, set_level
from tm.runfolder import RunFolder

PEAK = {"start": "2026-08-05", "stop": "2026-08-11", "spend": 600.0, "results": 50, "cpr": 12.0, "impressions": 40000,
        "p25": 9000, "thruplay": 3000, "clicks_est": 800.0, "frequency": 1.4, "cpm": 15.0, "weeks": 1}
LATEST = {**PEAK, "start": "2026-10-28", "stop": "2026-11-03", "results": 30, "cpr": 20.0, "clicks_est": 790.0}
SAID = "The page has not changed; the ad is worn out"


@pytest.fixture
def run(tmp_path):
    r = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = ["creative_brief", "edited_video"]
    s.step = "A1a"
    s.decisions = [{"checkin": "G1", "choice": "a1", "by": "user", "said": "ok", "at": "2026-11-05T10:00:00+00:00"}]
    state.save(r, s)
    set_level(r, "every_step")
    ranking = {"ranking": ["a1"], "candidates": [
        {"ad_id": "a1", "name": "Serum spring", "verdict": "fading", "peak": PEAK, "latest": LATEST},
        {"ad_id": "o1", "name": "Cream", "verdict": "other_product", "link": "https://other.example.org/cream",
         "note": "Its link goes to other.example.org/cream"}], "product": {"name": "Serum"}}
    (r.path / "01_base" / "winner_ranking_v01.json").write_text(json.dumps(ranking), encoding="utf-8")
    folder = r.path / "03_wip" / "diagnosis_windows"
    folder.mkdir(parents=True)
    (folder / "peak_v01.json").write_text(json.dumps(PEAK), encoding="utf-8")
    (folder / "latest_v01.json").write_text(json.dumps(LATEST), encoding="utf-8")
    return r


def _landing(run):
    d = r2.Diagnosis(stage="landing", refresh=False, evidence={"ctr": (0.02, 0.0198), "conversion": (0.0625, 0.038)},
                     account_check={"ad_rate_ratio": 0.6, "account_ratio": 0.98},
                     structural={"structural": False, "step": None, "segment_s": None, "uploads": [], "skipped": []})
    r2.record(run, d)


def _html(run, folder):
    return (run.path / folder / "index.html").read_text(encoding="utf-8")


def test_do_not_refresh_writes_the_report_and_rebuilds_the_page(run, capsys):
    _landing(run)
    first = run_page.build(run)
    assert main(["decide", "G1a", "do_not_refresh", "--said", "ok, the page then", "--run", str(run.path),
                 "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["report"] == "04_final/diagnosis_report_v01.md" and out["page"]["folder"] != first["folder"]
    assert changes.DIAGNOSIS_REPORT in out["message"] and "publish it to the same URL" in out["message"]
    text = (run.path / out["report"]).read_text(encoding="utf-8")
    for heading in ("## What was checked", "## What the data shows", "## What to fix", "## What was spent"):
        assert heading in text
    assert "Serum spring" in text and "2026-08-05 to 2026-08-11" in text and "2026-10-28 to 2026-11-03" in text
    assert "| Results per click (conversion) | 6.25% | 3.80% |" in text
    assert "no step is weak by design" in text and "the landing page" in text
    assert "how fast it opens on a phone" in text
    assert "Nothing: no money was spent in this run." in text
    assert "diagnosis_report_v01.md" in (run.path / "manifest.md").read_text(encoding="utf-8")
    html = _html(run, out["page"]["folder"])
    assert 'class="now"' not in html or "Nothing to decide right now." in html
    assert "Done" in html and "The run ended here, without a refresh." in html and "What to fix" in html


def test_a_run_without_a_page_gets_the_report_only(run):
    _landing(run)
    wrote = decide(run, "G1a", "do_not_refresh", by="rule", note="landing")
    assert wrote == {"report": "04_final/diagnosis_report_v01.md", "page": None}
    assert not (run.path / "04_final" / "run_page_v01").exists()


def test_the_end_texts_name_the_file(run):
    assert "04_final/diagnosis_report_v01.md" in changes.unsupported_message("hook", "static")
    from tm import checkins
    end = checkins.load().checkins["G1a"].on_choice["do_not_refresh"]["end"]
    assert "04_final/diagnosis_report_v01.md" in end


def test_no_fading_winner_has_a_report_too(run):
    s = state.load(run)
    s.decisions = [{"checkin": "G1", "choice": "none", "by": "rule", "note": "no fading ad", "at": "2026-11-05T10:00:00"}]
    state.save(run, s)
    decide(run, "G1a", "do_not_refresh", by="rule", note="no fading winner")
    text = (run.path / "04_final" / "diagnosis_report_v01.md").read_text(encoding="utf-8")
    assert "No ad of the account is a fading winner" in text


def test_an_open_card_of_an_ended_run_is_settled(run):
    _landing(run)
    ask = run.path / "03_wip" / "ask.json"
    ask.write_text(json.dumps({"checkin": "pick_the_ad", "title": "Pick", "question": "Which?",
                               "options": [{"choice": "ok", "label": "OK"}]}), encoding="utf-8")
    run_page.build(run, ask)
    decide(run, "G1a", "do_not_refresh", by="user", note=None, said="no")
    built = run_page.build(run)
    assert built["open"] == []
    assert "Not answered (the run ended)" in _html(run, built["folder"]) or "Pick the ad" in _html(run, built["folder"])


def test_the_override_line_is_on_the_diagnosis_and_money_stages(run):
    _landing(run)
    decide(run, "G1a", "override", by="user", note=None, said=SAID, stage="fatigue")
    s = state.load(run)
    s.decisions.append({"checkin": "G6", "choice": "approve", "by": "user", "said": "yes",
                        "at": "2026-11-06T10:00:00+00:00"})
    s.budgets = {"ai_usd": 20.0}
    state.save(run, s)
    html = run_page.build(run)
    page = _html(run, html["folder"])
    assert f"Diagnosis: The landing page. The user decided to refresh Ad fatigue, because: {SAID}" in page
    assert "This run goes against the diagnosis (The landing page)" in page


def test_the_g1_stage_sets_other_products_apart_and_says_too_little_data(run):
    data = json.loads((run.path / "01_base" / "winner_ranking_v01.json").read_text(encoding="utf-8"))
    data["ranking"] = []
    data["candidates"][0].update(verdict="not_enough_data", paused=True)
    data["too_little_data"] = {"best_ad": "a1", "best_name": "Serum spring", "best_results": 18, "min_results": 30,
                               "line": "x"}
    (run.path / "01_base" / "winner_ranking_v02.json").write_text(json.dumps(data), encoding="utf-8")
    built = run_page.build(run)
    page = _html(run, built["folder"])
    assert "Ads of other products, set aside" in page and "other.example.org/cream" in page
    assert "Your Serum ads have too little data to judge: the best, Serum spring, has 18 of the 30 results needed." \
        in page
    assert re.search(r"not_enough_data · paused", page)
