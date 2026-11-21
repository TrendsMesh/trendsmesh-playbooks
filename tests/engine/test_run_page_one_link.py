"""Issue #131: every check-in of a run on one run page, under one link. Trend research's check-ins live on the
report's link (the report is the run page from E1 on), the start card and the brief's page share the run page's
link, and a done run's page has nothing open and ends with "Done"."""

import json
import re
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from test_research_report import _cfg, _uroda
from tm import flow, page, research_report, run_page, state
from tm.cli import main
from tm.flow import set_level
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

URL = "https://claude.ai/artifact/Ab3dEfGh1jKlMnOpQrStUv"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("offline in tests")
    monkeypatch.setattr(page.requests, "get", no_network)


def _decide(run, checkin, choice, minutes=0):
    s = state.load(run)
    at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    s.decisions.append({"checkin": checkin, "choice": choice, "by": "user", "at": at, "note": None})
    state.save(run, s)


def _ask(run, checkin, choice="accept"):
    path = run.path / "03_wip" / f"my_ask_{checkin}.json"
    path.write_text(json.dumps({"checkin": checkin, "title": f"About {checkin}", "question": "Accept it?",
                                "options": [{"choice": choice, "label": "Yes", "recommended": True}]}),
                    encoding="utf-8")
    return path


# --- trend research: the report's link ------------------------------------------------------------------

def test_trend_research_check_ins_are_versions_of_the_report_page(tmp_path):
    run, _ = _uroda(tmp_path)
    assert run_page.page_name(run) == research_report.PAGE == "report"
    first = run_page.build(run, _ask(run, "G0"))                 # before E1: the check-in alone
    assert first["folder"].startswith("04_final/report_v") and first["page"] == "report"
    assert first["capabilities"] == run_page.CAPABILITIES
    _decide(run, "G0", "accept", minutes=1)
    research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    later = run_page.build(run, _ask(run, "G2"))                  # after E1: the report above the check-in
    html = (run.path / later["folder"] / "index.html").read_text(encoding="utf-8")
    assert 'id="view-report"' in html and "<title>Uroda Trend Report</title>" in html
    assert later["open"] == ["G2"] and (run.path / later["folder"] / "report.json").is_file()
    listed = {f["as"] for f in page.files(run.path / later["folder"])}
    assert ".report_parts.json" not in listed and ".build.json" not in listed


def test_the_report_page_keeps_one_link_across_weeks(tmp_path):
    run, _ = _uroda(tmp_path)
    run_page.build(run, _ask(run, "G0"))
    page.record_published(run, "report", None, "v1", URL)
    assert page.published(run, "report")["url"] == URL


# --- the start card, the run page and the brief's page share one link ------------------------------------

def test_the_run_page_goes_to_the_start_cards_link(tmp_path):
    run = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    (run.path / "04_final" / "intake_v01").mkdir(parents=True)
    (run.path / "04_final" / "intake_v01" / "index.html").write_text("<p>start</p>", encoding="utf-8")
    page.record_published(run, "intake", None, "v1", URL)
    got = page.published(run, run_page.PAGE)
    assert got["url"] == URL and got["page"] == "intake"
    assert page.published(run, "report") is None                  # a page of its own keeps its own link


def test_a_creative_briefs_g0_and_g1_are_run_page_stages(tmp_path):
    run = RunFolder.create(tmp_path, "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)
    set_level(run, "every_step")
    (run.path / "01_base").mkdir(exist_ok=True)
    (run.path / "01_base" / "account_context.md").write_text("Winners: ad 1. The data diverges.", encoding="utf-8")
    _decide(run, "G0", "accept")
    built = run_page.build(run, _ask(run, "G1"), local=True)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert "Winners: ad 1. The data diverges." in html and "Accept the persona" in html
    assert page.linked(CREATIVE_BRIEF, "brief_pack") == ("intake", "run_page", "brief_pack")


def test_the_brief_pages_settled_group_is_for_the_decision_and_strategy_views():
    from tm import brief_page
    html = brief_page._shell("<p>b</p>", {"stage": None, "settled": "<section>s</section>", "updated": "now",
                                          "run": "r"}, "en")
    assert re.search(r'<div class="settled-group" data-v="decision strategy">', html), html


# --- a done run: nothing open, "Done" last --------------------------------------------------------------

def test_a_done_run_has_nothing_open_and_ends_with_done(tmp_path):
    run = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    set_level(run, "every_step")
    run_page.build(run, _ask(run, "G1b"))                         # asked, then the run ended
    _decide(run, "G1", "ad1")
    s = state.load(run)
    s.status = "done"
    state.save(run, s)
    built = run_page.build(run)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert built["open"] == [] and "Every check-in is settled and the run is done." in html
    assert "Every step of this run is done." in flow.next(run).message and "tm page build" in flow.next(run).message
