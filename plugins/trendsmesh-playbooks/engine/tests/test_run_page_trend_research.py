"""Trend research on the shared run page (issue #60): the report (`tm research report`) is built by the run page's
template, in the TrendsMesh look, with the run's settled check-ins read-only under it; `tm page build` knows Trend
research's check-ins. The made-up "Uroda, PL" run of test_research_report.py is used throughout."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
import requests

from test_research_report import BLASK, DZIEN, POV, _cfg, _hook, _uroda, _with_hooks
from tm import i18n, page, research_report, run_page, state
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.run_page import words


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("offline in tests")
    monkeypatch.setattr(page.requests, "get", no_network)


def _decide(run, checkin, choice, by="user", note=None, minutes=0):
    s = state.load(run)
    at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    s.decisions.append({"checkin": checkin, "choice": choice, "by": by, "at": at, "note": note,
                        **({"rule": "agent review applied"} if by == "rule" else {})})
    state.save(run, s)


def _build(run) -> str:
    folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    return (folder / "index.html").read_text(encoding="utf-8")


def _settled(html: str) -> str:
    m = re.search(r'<section class="settled">.*?</section>(?=</main>)', html, re.S)
    return m.group(0) if m else ""


def test_the_report_has_the_trendsmesh_look_and_keeps_its_views(tmp_path):
    run, _ = _uroda(tmp_path)
    html = _build(run)
    for token in ("#fff4e6", "#fffbf6", "#16110d", "#ff4f8b", "#d6246e", "#ffe14a"):     # assets/page/theme.css
        assert token in html
    assert '<header class="top">' in html and "<svg" in html and '<span class="pill dark">Trend research</span>' in html
    assert "<title>Uroda Trend Report</title>" in html                       # the report's own title
    assert "fonts.googleapis" not in html and "fonts.gstatic" not in html   # a shared report never calls Google
    for view in ("report", "digest", "paid"):
        assert f'id="view-{view}"' in html and f"<a href='#{view}'>" in html
    assert html.index('<header class="top">') < html.index('<nav class="views"')
    assert "What is moving in Uroda" in html and "Trend data: TrendsMesh, 4 Nov 2026." in html
    # the report's own styles keep to its part of the page, the run page's to theirs
    assert ".report .card" in html and "--act:" in html
    assert "Nothing to decide right now." not in html                       # the report is the page's content
    assert "Every number shows its source when you hover" not in html       # not said of the report's numbers


def test_settled_check_ins_are_read_only_summaries_under_the_report(tmp_path):
    run, _ = _uroda(tmp_path)
    _decide(run, "G0", "accept", by="rule", note="Uroda, PL, polski")
    _decide(run, "G1", "accept", note="Bez diety keto.", minutes=1)
    _decide(run, "G2", "accept", minutes=2)
    html = _build(run)
    settled = _settled(html)
    assert "Already settled (3)" in settled
    names = re.findall(r'<span class="what">(.*?)</span>', settled)
    assert names == ["The picks: Accepted", "The category map: Accepted", "Seed phrases and market: Accepted"]
    assert "Pick the ad" not in html and "Hooks:" not in settled            # Refresh an ad's names stay its own
    assert "Bez diety keto." in settled and "Decided by rule" in settled and "agent review applied" in settled
    # nothing on the page takes input: the report is read-only, its check-ins answered in chat
    assert "<input" not in html and "<textarea" not in html and 'data-ask="' not in html
    assert html.index('id="view-report"') < html.index('<section class="settled">')
    assert json.loads(re.search(r'<script type="application/json" id="tm-page">(.*?)</script>', html, re.S)
                      .group(1))["local"] is True


def test_the_settled_stages_say_what_was_decided_from_the_runs_files(tmp_path):
    run, picks = _uroda(tmp_path)
    _with_hooks(run, picks, [
        _hook(POV, "pov _", use="in_category", rank=1, relative={"velocity_index": 1.3, "rising_of": 40,
                                                                  "band": "top 10%"}),
        _hook(DZIEN, "dzień _ z _", use="transfer", rank=2, relative={"velocity_index": 0.7, "rising_of": 40}),
        _hook(BLASK, "glow _", use="transfer", rank=3, relative={"velocity_index": 0.5, "rising_of": 40})],
        hooks_rising=40)
    _decide(run, "G1", "accept")
    _decide(run, "G2", "accept", minutes=1)
    settled = _settled(_build(run))
    g1 = settled[settled.index('id="stage-G1"'):]
    assert "<dt>Sub-categories</dt><dd>2</dd>" in g1 and "<dt>Trends kept</dt><dd>3</dd>" in g1
    assert "<dt>Left out</dt><dd>1</dd>" in g1
    assert "<dt>Hooks used in Uroda</dt><dd>pov _</dd>" in g1
    assert "<dt>Hooks to transfer</dt><dd>dzień _ z _, glow _</dd>" in g1
    g2 = settled[settled.index('id="stage-G2"'):settled.index('id="stage-G1"')]
    assert "<dt>Act now</dt><dd>Krem z filtrem na co dzień</dd>" in g2
    assert "<dt>Still rising</dt><dd>Olejowanie włosów, pov _</dd>" in g2
    assert "Source: 03_wip/picks_v01.json" in g2


def test_a_weekly_schedule_and_the_page_check_in_are_named_in_words(tmp_path):
    run, _ = _uroda(tmp_path)
    _decide(run, "G3", "keep_local", by="rule", note="no publishing tool")
    _decide(run, "GS", "by_hand", minutes=1)
    s = state.load(run)
    s.schedule = {"how": "by_hand"}
    state.save(run, s)
    names = re.findall(r'<span class="what">(.*?)</span>', _settled(_build(run)))
    assert names == ["The weekly report: By hand", "The page: Keep it a local file"]


def test_the_page_language_needs_the_run_page_words_translated_too(tmp_path):
    run, _ = _uroda(tmp_path)
    assert set(words.AREAS[TREND_RESEARCH]) == {"report", "common"}
    assert research_report.page_language(run).lang == "en"
    strings = {k: "PL·" + v for k, v in i18n.wanted("pl", ("report", "common")).items()}   # not run_page
    path = tmp_path / "i18n_pl.yaml"
    import yaml
    path.write_text(yaml.safe_dump({"lang": "pl", "strings": strings}, allow_unicode=True), encoding="utf-8")
    i18n.import_file("pl", path)
    pl = research_report.page_language(run)
    assert pl.lang == "en" and "built in English" in pl.warning
    assert '<html lang="en">' in _build(run)


def test_page_build_knows_trend_research_check_ins(tmp_path, capsys):
    run, _ = _uroda(tmp_path)
    _decide(run, "G1", "accept")
    ask = run.path / "03_wip" / "ask_G2.json"
    ask.write_text(json.dumps({"checkin": "G2", "title": "Wybory na ten tydzień", "question": "Akceptujesz?",
                               "options": [{"choice": "accept", "label": "Tak", "recommended": True}]},
                              ensure_ascii=False), encoding="utf-8")
    assert main(["page", "build", "--run", str(run.path), "--ask", str(ask), "--local", "--json"]) == 0
    built = json.loads(capsys.readouterr().out)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<span class="pill dark">Trend research</span>' in html
    now = html[html.index('class="panel now"'):html.index('<section class="settled">')]
    assert "The picks" in now and "<dt>Act now</dt><dd>Krem z filtrem na co dzień</dd>" in now
    assert "The category map: Accepted" in html and "<dt>Sub-categories</dt><dd>2</dd>" in html


def test_refresh_ad_stage_names_are_unchanged(tmp_path):
    from datetime import date
    from tm.runfolder import RunFolder
    r = RunFolder.create(tmp_path / "ws", "Ad 3", date(2026, 11, 5))
    _decide(r, "G1", "ad1")
    html = (r.path / run_page.build(r, local=True)["folder"] / "index.html").read_text(encoding="utf-8")
    assert "Pick the ad: ad1" in html and "The category map" not in html


def test_a_translated_report_with_settled_check_ins_has_no_english_left(tmp_path):
    from test_i18n_research_report import _english_left, _translate
    run, _ = _uroda(tmp_path)
    for n, (cid, choice) in enumerate((("G0", "accept"), ("G1", "accept"), ("G2", "accept"), ("G3", "publish"),
                                       ("GS", "schedule"))):
        _decide(run, cid, choice, minutes=n)
    s = state.load(run)
    s.schedule = {"how": "desktop_task", "id": "x", "cron": "0 9 * * 1"}
    state.save(run, s)
    _translate(tmp_path)
    html = _build(run)
    assert '<html lang="pl">' in html and "Already settled" not in html
    assert i18n.t("run_page.trend_research.stage.G1", "pl") in html
    assert _english_left(html) == []


def test_every_trend_research_page_word_is_in_the_table_and_used():
    from pathlib import Path
    from tm.run_page import trend_research
    text = Path(trend_research.__file__).read_text(encoding="utf-8")
    used = {"run_page.trend_research." + k for k in re.findall(r'_w\(ctx, "([a-z_.]+)"', text)}
    used |= {f"run_page.trend_research.stage.{k}" for k in ("G0", "G1", "G2", "G3", "GS", "approve_map",
                                                           "approve_report")}
    used |= {f"run_page.trend_research.choice.{c}" for c in ("accept", "changed_a_lot", "publish", "keep_local",
                                                            "schedule", "by_hand")}
    used |= {f"run_page.trend_research.schedule.{h}" for h in ("desktop_task", "by_hand")}
    en = i18n.english()
    assert sorted(used - set(en)) == []
    assert sorted(k for k in en if k.startswith("run_page.trend_research.") and k not in used) == []
    from tm import checkins
    cat = checkins.load(playbook=TREND_RESEARCH)
    for cid, c in cat.checkins.items():                  # every check-in and every choice has its words
        assert f"run_page.trend_research.stage.{cid}" in en
        assert all(f"run_page.trend_research.choice.{ch}" in en for ch in c.choices)
    assert all(f"run_page.trend_research.stage.{card}" in en for card in cat.cards)
