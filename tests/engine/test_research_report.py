"""tm.research_report: the page (TR10), a port of the handoff's tools/pb4/build_report.py.

The beauty run (beauty.py) is mapped and grown as of 4 Nov 2026 by the ports, with all three
outputs chosen, and gets the reference picks_v04, digest and Ad Library summary. The map's `results` counts
need the raw searches that are left out of the handoff, so the reference category_map.json is copied over as
the latest map. report.json must then equal the reference 04_final/report_v05/report.json, with only the
keys a port may add (`plugin`, `pool_ids`) stripped (decision 5, ruling F7b). Every test is
offline: no thumbnail is downloaded unless a test fakes the download.

The "Uroda, PL" run is small and made up, in Polish, so that nothing on its page can come from
the beauty data (Review Focus 4).
"""

import json
import locale
import shutil
from datetime import date

import pytest
import requests

import beauty
from tm import config, page, research_config, research_growth, research_map, research_report, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

AS_OF = beauty.CREATED
ALL = ["category_report", "weekly_digest", "paid_view"]
REPORT_V05 = beauty.BEAUTY / "04_final" / "report_v05"
RECONSTRUCTED = beauty.BEAUTY / "02_research" / "snapshot_growth_2026-10-29_reconstructed.json"
BACKTESTS = [beauty.BEAUTY / "03_wip" / f"backtest_{d}_rule_v3.json" for d in ("2026-09-23", "2026-10-07", "2026-10-21")]


def _strip(data):
    """Without what a port may add: every `plugin` and `pool_ids` key."""
    if isinstance(data, dict):
        return {k: _strip(v) for k, v in data.items() if k not in ("plugin", "pool_ids")}
    if isinstance(data, list):
        return [_strip(v) for v in data]
    return data


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _cfg(run: RunFolder) -> dict:
    return research_map.settings(config.load(run))


def _copy(run: RunFolder, tmp_path) -> RunFolder:
    ws = tmp_path / "ws"
    shutil.copytree(run.path.parents[2], ws)
    return RunFolder.open(ws / run.path.relative_to(run.path.parents[2]))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test downloads anything: every request fails as it would with no network."""
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("offline in tests")
    monkeypatch.setattr(page.requests, "get", no_network)


@pytest.fixture(scope="module")
def beauty_run(tmp_path_factory):
    """The beauty run, grown by the ports, with the reference map, digest, Ad Library summary and picks_v04."""
    run = beauty.mapped_run(tmp_path_factory.mktemp("beauty"))
    research_config.write_from_intake(run, {"category": {"inputs": [beauty.ROOT], "phrase": beauty.ROOT, "seeds": []},
                                            "market": "US", "language": "en", "outputs": ALL})
    research_growth.compute(run, AS_OF, _cfg(run))
    shutil.copyfile(beauty.BEAUTY / "02_research" / "category_map.json",
                    run.next_version("02_research", research_map.STEM, "json"))
    beauty.copy_input(run, "02_research/digest.json")
    beauty.copy_input(run, "02_research/ad_library_summary_v02.json")
    beauty.copy_input(run, "03_wip/picks_v04.json")
    return run


def _build_beauty(run: RunFolder, **kw):
    return research_report.build(run, run.path / "03_wip" / "picks_v04.json", prev_snapshot=RECONSTRUCTED,
                                 backtests=BACKTESTS, cfg=kw.pop("cfg", None) or _cfg(run), **kw)


# --- the beauty run ---------------------------------------------------------------------------

@pytest.mark.private_data
def test_report_json_rebuilds_report_v05(beauty_run, tmp_path):
    run = _copy(beauty_run, tmp_path)
    folder = _build_beauty(run)
    assert folder == run.path / "04_final" / "report_v01"
    got = _read(folder / "report.json")
    expected = beauty.as_judged(_strip(_read(REPORT_V05 / "report.json")), run)   # issue #3: judged hooks
    # issue #58: hooks by their rising place; the digest is the reference's own, copied in
    expected = {**beauty.as_rising_bands(expected, run), "digest": expected["digest"]}
    assert _strip(got) == expected
    assert research_report.schema_problems(got) == []
    # F7b: the weighted total goes under each pick's plugin key (the reference picks have no score table)
    assert got["act_now"][0]["plugin"] == {"weighted_total": None, "scale": [7.0, 35.0]}
    assert (folder / "index.html").is_file() and (folder / "assets").is_dir()
    assert "04_final/report_v01" in (run.path / "manifest.md").read_text(encoding="utf-8")


@pytest.mark.private_data
def test_page_has_three_views_and_switch(beauty_run, tmp_path):
    run = _copy(beauty_run, tmp_path)
    text = (_build_beauty(run) / "index.html").read_text(encoding="utf-8")
    for view in ("report", "digest", "paid"):
        assert f'id="view-{view}"' in text and f"<a href='#{view}'>" in text
    assert '<nav class="views"' in text and "window.addEventListener('hashchange'" in text
    assert "<title>Beauty Trend Report</title>" in text and "What is moving in beauty" in text
    assert "Valid until 18 Nov 2026" in text and "Meta Ad Library (US)" in text
    assert "fonts.googleapis" not in text and "fonts.gstatic" not in text           # no call to Google (GDPR)
    assert "Four trends to act on now" in text and "Act on these four" in text
    # the reference digest's previous state is not marked rebuilt: no "rebuilt" line
    assert "Compared with the report of 29 Oct 2026 (6 days of evidence)." in text
    assert "rebuilt from the evidence dates" not in text
    # issue #58: a hook's band is its place among the 101 rising hooks TrendsMesh lists
    assert "a hook by its place among the 101 rising hooks TrendsMesh lists" in text
    assert "of TrendsMesh&#x27;s 101 rising hooks" in text and "of all rising hooks" not in text
    hooks = text[text.index("<section id='hooks'>"):]
    hooks = hooks[:hooks.index("</section>")]
    assert "<h3>Already used in beauty · 5</h3>" in hooks and "<b>day _ of _</b>" in hooks
    assert "<h3>Fit the message, not used in beauty yet · 0</h3>" in hooks
    assert "Every shortlisted hook already has a beauty video." in hooks
    assert hooks.count("Ad Library: not checked") == 5                    # no B4 check in the reference run


@pytest.mark.private_data
def test_page_places_hooks_among_every_rising_hook_when_only_the_shortlist_is_read(beauty_run, tmp_path):
    """Issue #8: only the shortlisted hooks' videos are fetched. Issue #58: the band still compares a hook with
    every rising hook, by its place in TrendsMesh's list, so the page never says "the rising hooks read"."""
    run = _copy(beauty_run, tmp_path)
    mapped = {r["id"] for r in research_growth.category_map(run)["kept"]}   # one hook is on the map too
    for row in beauty.handoff("02_research/hooks_in_category.json")["not_in_category"]:
        for f in trends.video_files(run, row["id"]) if row["id"] not in mapped else []:
            f.unlink()
    research_growth.compute(run, AS_OF, _cfg(run))
    text = (_build_beauty(run) / "index.html").read_text(encoding="utf-8")
    assert "a hook by its place among the 101 rising hooks TrendsMesh lists" in text
    assert "rising hooks read" not in text and "whose videos were read" not in text


@pytest.mark.private_data
def test_only_chosen_views_render(beauty_run, tmp_path):
    run = _copy(beauty_run, tmp_path)
    cfg = {**_cfg(run), "outputs": ["category_report"]}
    folder = _build_beauty(run, cfg=cfg)
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert 'id="view-report"' in text and "<a href='#report'>" in text
    assert 'id="view-digest"' not in text and 'id="view-paid"' not in text
    assert "#digest" not in text and "#paid" not in text
    report = _read(folder / "report.json")
    assert report["outputs"] == ["report"] and report["digest"] is None
    assert research_report.schema_problems(report) == []


@pytest.mark.private_data
def test_second_build_writes_report_v02(beauty_run, tmp_path, capsys):
    run = _copy(beauty_run, tmp_path)
    first = _build_beauty(run)
    before = (first / "index.html").read_bytes()
    args = ["research", "report", "--run", str(run.path), "--picks", "03_wip/picks_v04.json",
            "--prev-snapshot", str(RECONSTRUCTED), "--backtest", *map(str, BACKTESTS), "--json"]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["folder"] == "04_final/report_v02"
    assert [f["as"] for f in payload["files"]] == ["index.html", "report.json"]
    assert payload["files"] == page.files(run.path / "04_final" / "report_v02")
    assert (first / "index.html").read_bytes() == before                      # the first build is never touched
    assert _strip(_read(run.path / "04_final" / "report_v02" / "report.json")) == \
        _strip(_read(first / "report.json"))


@pytest.mark.private_data
def test_schema_problems_are_said():
    good = _read(REPORT_V05 / "report.json")
    assert research_report.schema_problems(good) == []
    broken = {**good, "schema": "pb4-report/2", "act_now": [{"id": "x"}], "outputs": "report"}
    del broken["buckets"]
    problems = research_report.schema_problems(broken)
    assert "report lacks buckets" in problems
    assert "report.schema is 'pb4-report/2', not 'pb4-report/1'" in problems
    assert "report.outputs is str, not array" in problems
    assert "report.act_now[0] lacks trend" in problems


# --- a made-up "Uroda, PL" run ----------------------------------------------------------------

KREM, OLEJ, MASKA = "a1" * 16, "b2" * 16, "c3" * 16


def _row(tid: str, name: str, bucket: str) -> dict:
    return {"id": tid, "kind": "topic_trend", "name": name, "group": "pielęgnacja", "sub_category": "pielęgnacja",
            "status": "confirmed", "what_it_is": "Krótkie filmy z porannej pielęgnacji.", "bucket": bucket,
            "confidence": "medium", "confidence_why": "12 twórców", "seasonal_over": None, "platforms": ["tiktok"],
            "growth": {"creators": 12, "new_recent": 5, "new_base": 2, "ratio": 2.5, "last_seen_days": 1,
                       "age_days": 30, "videos_known": 20, "median_views": 8000, "views_total": 160000,
                       "top_creator": "ania", "top_creator_share": 0.2},
            "relative": {"velocity_index": 1.7, "percentile": 0.9, "band": "top 10%"}}


def _write(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _uroda(tmp_path, *, act_now: bool = True, as_of: str = "2026-11-04") -> tuple[RunFolder, dict]:
    """A run for "Uroda", market PL, with its growth, map, digest, Ad Library summary, videos and picks
    written as the tools would; returns the run and its picks."""
    run = RunFolder.create(tmp_path / "ws", "uroda", AS_OF, playbook=TREND_RESEARCH)
    research_config.write_from_intake(run, {"category": {"inputs": ["Uroda"], "phrase": "Uroda", "seeds": []},
                                            "market": "PL", "language": "pl", "outputs": ALL})
    research = run.path / "02_research"
    params = {"as_of": "2026-11-04", "ref": "2026-11-02", "lag": 2, "window": 14, "baseline": 28, "rule": "v3",
              "category": {"median_new": 3, "trends_active": 3, "creators_active": 30, "trends": 3, "hooks_pool": 10}}
    _write(research / "growth_v01.json", {"params": params, "trends": [
        _row(KREM, "Krem z filtrem na co dzień", "act_now"), _row(OLEJ, "Olejowanie włosów", "still_rising"),
        _row(MASKA, "Maseczki w płachcie", "too_late")]})
    _write(research / "category_map_v01.json", {
        "root": "Uroda", "min_match": 40, "min_relevant": 10,
        "queries": [{"query": "Uroda", "parent": None, "relevant": 4, "results": 20, "file": "search/search_uroda.json"},
                    {"query": "pielęgnacja", "parent": "Uroda", "relevant": 12, "results": 20,
                     "file": "search/search_pielegnacja.json"}],
        "kept": [{"id": t, "sub_category": "pielęgnacja"} for t in (KREM, OLEJ, MASKA)],
        "dropped": [{"id": "d4" * 16, "name": "Dieta keto", "dropped_because": ["poza kategorią"]}]})
    _write(research / "digest_v01.json", {
        "prev": {**params, "as_of": "2026-10-28", "ref": "2026-10-26"}, "now": params,
        "new": [{"id": OLEJ, "name": "Olejowanie włosów", "bucket": "still_rising"}], "reidentified": [],
        "up": [], "down": [{"id": MASKA, "name": "Maseczki w płachcie", "from": "still_rising", "to": "too_late"}],
        "ended": [{"id": "e5" * 16, "name": "Brokatowe brwi", "kind": "topic_trend"}],
        "calls": [{"id": KREM, "name": "Krem z filtrem na co dzień", "call": "act_now", "new_creators_since": 3,
                   "held": True},
                  {"id": "f6" * 16, "name": "Lakier żelowy", "call": "act_now", "new_creators_since": None, "held": None,
                   "plugin": {"verdict": "unknown", "in_map": False, "reidentified_as": None}}],
        "hit_rate": {"act_now": [1.0, 1], "past_peak": [None, 0]}})
    _write(research / "ad_library_summary_v01.json", {"checked": True, "checks": [
        {"trend_id": KREM, "trend": "Krem z filtrem na co dzień", "query": "krem z filtrem", "level": "found",
         "advertisers": ["Marka A"], "estimated": 120},
        {"trend_id": OLEJ, "trend": "Olejowanie włosów", "query": "olej do włosów", "level": "none",
         "advertisers": [], "estimated": 0}]})
    _write(research / "videos" / f"{KREM}_p01.json", {"data": [
        {"asset_id": "tiktok:1", "creator": "ania", "published": "2026-08-01T10:00:00Z", "views": 10,
         "url": "https://www.tiktok.com/@ania/video/1", "thumbnail_url": "https://img.example/aug.jpg"},
        {"asset_id": "tiktok:2", "creator": "ola", "published": "2026-05-01T10:00:00Z", "views": 1000,
         "url": "https://www.tiktok.com/@ola/video/2", "thumbnail_url": "https://img.example/may.jpg"}]})
    pick = {"what": "Poranna rutyna z kremem.", "how": "Pokaż nakładanie w 10 sekund.", "risk": "Sezonowe latem."}
    picks = {"category": "Uroda", "market": "PL, polski", "as_of": as_of, "moves": [],
             "act_now": [{"id": KREM, **pick}] if act_now else [], "still_rising": [{"id": OLEJ, **pick}],
             "watch_next": "Olejowanie włosów, jeśli dojdą nowi twórcy.", "outputs": ["report", "digest", "paid"],
             "paid_reading": ["Olejowanie: brak reklam w tytułach Ad Library."],
             "digest_reading": {"summary": ["Krem z filtrem nadal rośnie."], "todo": ["Nagraj rutynę."]}}
    _write(run.path / "03_wip" / "picks_v01.json", picks)
    return run, picks


def _picks_file(run: RunFolder, picks: dict):
    path = run.next_version("03_wip", "picks", "json")
    _write(path, picks)
    return path


def test_report_is_not_hard_coded_to_beauty(tmp_path):
    run, _ = _uroda(tmp_path)
    saved = locale.setlocale(locale.LC_TIME)
    polish = False
    for name in ("pl_PL.UTF-8", "pl_PL.utf8", "pl_PL", "Polish_Poland.1250"):
        try:
            locale.setlocale(locale.LC_TIME, name)
            polish = True
            break
        except locale.Error:
            continue
    try:
        if polish:                                  # the locale took: strftime would say "lis", not "Nov"
            assert date(2026, 11, 18).strftime("%b") != "Nov"
        folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    finally:
        locale.setlocale(locale.LC_TIME, saved)
    text = (folder / "index.html").read_text(encoding="utf-8")
    data = (folder / "report.json").read_text(encoding="utf-8")
    for written in (text, data):
        low = written.casefold()
        assert "beauty" not in low and "staging" not in low and "dry run" not in low
        assert " US" not in written
    assert "<title>Uroda Trend Report</title>" in text and "What is moving in Uroda" in text
    assert "Meta Ad Library (PL)" in text and "active PL ads" in text and "typical Uroda trend" in text
    assert "Trend data: TrendsMesh, 4 Nov 2026." in text
    assert "As of 4 Nov 2026" in text and "Valid until 18 Nov 2026" in text          # in any locale
    assert _read(folder / "report.json")["valid_until"] == "18 Nov 2026"
    assert _read(folder / "report.json")["paid"]["checks"][KREM]["query_note"] == "search 'krem z filtrem', active PL ads"
    # the digest: an unknown call of a trend that left the map is shown as such, never as stalled
    assert "Lakier żelowy" in text and "Not on this week's map." in text and "? Last week: act now · Unknown" in text
    assert "Compared with the report of 28 Oct 2026 (7 days of evidence)." in text
    assert "One trend to act on now" in text and "<h2>Act on this one</h2>" in text
    assert "kept adding creators (1 unknown)" in text


def test_rebuilt_previous_week_is_said(tmp_path):
    run, _ = _uroda(tmp_path)
    prev = run.path / "02_research" / "snapshot_growth_2026-10-28_rebuilt_v01.json"
    _write(prev, {"params": {"as_of": "2026-10-28", "ref": "2026-10-26"}, "trends": {}, "rebuilt": True})
    digest = _read(run.path / "02_research" / "digest_v01.json")
    _write(run.path / "02_research" / "digest_v02.json", {**digest, "plugin": {"ended_checked": False, "prev_rebuilt": True}})
    text = (research_report.build(run, run.path / "03_wip" / "picks_v01.json", prev_snapshot=prev, cfg=_cfg(run))
            / "index.html").read_text(encoding="utf-8")
    assert "rebuilt from the evidence dates" in text and "Compared with the report of" not in text
    assert "Not checked this week: the previous week is rebuilt from evidence dates, so ended trends are left out." in text


def test_no_act_now_says_so_in_one_line(tmp_path):
    run, picks = _uroda(tmp_path, act_now=False)
    folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    text = (folder / "index.html").read_text(encoding="utf-8")
    report_view = text.split('id="view-report"')[1].split('id="view-digest"')[0]
    assert report_view.count(research_report.NO_ACT_NOW) == 1 and text.count(research_report.NO_ACT_NOW) == 1
    assert "Act on these" not in text
    headings = [h.split("</h2>")[0] for h in report_view.split("<h2>")[1:]]
    assert headings[:2] == ["Still rising: worth watching", "Watch next"]
    assert _read(folder / "report.json")["act_now"] == []


def test_offline_thumbnails_still_build_the_page(tmp_path, monkeypatch):
    run, picks = _uroda(tmp_path)
    folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert "<img" not in text and list((folder / "assets").iterdir()) == []
    assert "Poranna rutyna z kremem." in text                                    # the card is there, without images

    # online: the thumbnails are the page's own files, chosen by the picks' date, never today's. As of
    # 10 Aug, the video of 1 Aug (10 views) is within 45 days and that of 1 May (1,000 views) is not;
    # by a today rule both are out of the window (in any year from mid-September 2026 on), so the 1 May
    # video, with more views, would come first
    fetched = []

    def fetch(url, dest):
        assert dest.name == page.asset_name(dest.name) and dest.parent == page.latest_folder(run, "report") / "assets"
        fetched.append(url)
        dest.write_bytes(b"\xff\xd8 jpeg")
        return True

    monkeypatch.setattr(page, "fetch_image", fetch)
    old = _picks_file(run, {**picks, "as_of": "2026-08-10"})
    folder2 = research_report.build(run, old, cfg=_cfg(run))
    assert fetched == ["https://img.example/aug.jpg"]
    text = (folder2 / "index.html").read_text(encoding="utf-8")
    assert f"<img src='assets/{KREM[:8]}_1.jpg'" in text and (folder2 / "assets" / f"{KREM[:8]}_1.jpg").is_file()
    assert "10 Aug 2026" in text and "24 Aug 2026" in text                      # as of, valid until


def test_weighted_total_goes_under_plugin_with_its_scale(tmp_path):
    run, picks = _uroda(tmp_path)
    scores = {KREM: {c: 3 for c in research_config.CRITERIA}, OLEJ: {c: 4 for c in research_config.CRITERIA}}
    scores[KREM]["growth"] = 5
    path = _picks_file(run, {**picks, "scores": scores})
    folder = research_report.build(run, path, cfg=_cfg(run))
    report = _read(folder / "report.json")
    assert report["act_now"][0]["plugin"] == {"weighted_total": 23, "scale": [7.0, 35.0]}
    assert report["still_rising"][0]["plugin"]["weighted_total"] == 28
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert "Fit score 23 on a scale of 7–35 (TR5: 7 criteria scored 1–5, weighted)" in text


def test_picks_naming_unknown_trends_are_refused(tmp_path, capsys):
    run, picks = _uroda(tmp_path)
    path = _picks_file(run, {**picks, "still_rising": [{"id": "ff" * 16, "what": "x", "how": "y", "risk": "z"}]})
    assert main(["research", "report", "--run", str(run.path), "--picks", str(path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "ff" * 16 in payload["message"] and "tm research picks check" in payload["message"]
    assert not (run.path / "04_final").exists() or not list((run.path / "04_final").iterdir())


# --- fix round 1 ------------------------------------------------------------------------------

def test_first_run_has_no_digest_view(tmp_path, capsys):
    run, _ = _uroda(tmp_path)
    (run.path / "02_research" / "digest_v01.json").unlink()                # a first run: no digest yet
    assert main(["research", "report", "--run", str(run.path), "--picks", "03_wip/picks_v01.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "no digest yet (first run)" in payload["message"]
    folder = run.path / payload["folder"]
    report = _read(folder / "report.json")
    assert report["outputs"] == ["report", "paid"] and report["digest"] is None
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert 'id="view-digest"' not in text and "#digest" not in text and "<a href='#paid'>" in text


HALLO, OLD_HALLO = "d7" * 16, "e8" * 16


def test_reidentified_rows_show_their_true_stage(tmp_path):
    run, _ = _uroda(tmp_path)
    growth = _read(run.path / "02_research" / "growth_v01.json")
    halloween = {**_row(HALLO, "Makijaż na Halloween", "past_peak"), "seasonal_over": "Halloween (31 Oct) is over"}
    _write(run.path / "02_research" / "growth_v02.json", {**growth, "trends": growth["trends"] + [halloween]})
    digest = _read(run.path / "02_research" / "digest_v01.json")
    digest["reidentified"] = [{"id": HALLO, "name": "Makijaż na Halloween", "was": "Halloweenowy makijaż",
                               "bucket": "past_peak", "plugin": {"was_id": OLD_HALLO}}]
    digest["calls"].append({"id": OLD_HALLO, "name": "Halloweenowy makijaż", "call": "act_now", "new_creators_since": 2,
                            "held": True, "plugin": {"verdict": "held", "in_map": False, "reidentified_as": HALLO}})
    digest["plugin"] = {"unknown_calls": {"act_now": 2, "past_peak": 0}, "ended_checked": False, "prev_rebuilt": True}
    _write(run.path / "02_research" / "digest_v02.json", digest)

    # no previous snapshot to look the old id up in: the stage then is unknown, never "act now"
    text = (research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
            / "index.html").read_text(encoding="utf-8")
    cooling = text.split("<h2>Cooling down</h2>")[1].split("</table>")[0]
    assert "<td>Makijaż na Halloween</td><td>— → Past its peak</td>" in cooling
    assert "Makijaż na Halloween <span class='sub'>(was Halloweenowy makijaż)</span>" in text
    assert "kept adding creators (2 unknown)" in text
    assert "Not checked this week: the previous snapshot has no pool list, so ended trends are left out." in text

    # the previous snapshot has it under its old id
    prev = tmp_path / "prev_snapshot.json"
    _write(prev, {"params": {"as_of": "2026-10-28", "ref": "2026-10-26"},
                  "trends": {OLD_HALLO: {"name": "Halloweenowy makijaż", "bucket": "still_rising"}}})
    text = (research_report.build(run, run.path / "03_wip" / "picks_v01.json", prev_snapshot=prev, cfg=_cfg(run))
            / "index.html").read_text(encoding="utf-8")
    assert "<td>Makijaż na Halloween</td><td>Still rising → Past its peak</td>" in text


def _fake_fetch(monkeypatch):
    def fetch(url, dest):
        dest.write_bytes(b"\xff\xd8 jpeg")
        return True
    monkeypatch.setattr(page, "fetch_image", fetch)


def test_thumbnails_stop_at_the_publish_limit(tmp_path, monkeypatch):
    run, picks = _uroda(tmp_path)
    _fake_fetch(monkeypatch)
    monkeypatch.setattr(page, "MAX_FILES", 3)                  # index.html, report.json and one image
    folder = research_report.build(run, _picks_file(run, {**picks, "as_of": "2026-05-10"}), cfg=_cfg(run))
    assert len(list((folder / "assets").iterdir())) == 1
    assert len(page.files(folder)) == 3                        # publishable as it is
    assert '"thumbnails_missing": 1' in (run.path / "manifest.md").read_text(encoding="utf-8")   # the one left out


SCRIPT_TAG, BREAK_OUT = "<script>alert(1)</script>", "\"'><img src=x onerror=alert(1)>"


def test_page_escapes_text_and_links_only_http(tmp_path, monkeypatch):
    run, picks = _uroda(tmp_path)
    weird = "\"'><b>" + "9" * 26                                 # a trend id that tries to leave its attribute
    growth = _read(run.path / "02_research" / "growth_v01.json")
    growth["trends"][0]["name"] = f"Krem {SCRIPT_TAG}"
    growth["trends"].append(_row(weird, f"Olej {BREAK_OUT}", "still_rising"))
    _write(run.path / "02_research" / "growth_v02.json", growth)
    _write(run.path / "02_research" / "videos" / f"{KREM}_p02.json", {"data": [
        {"asset_id": "tiktok:3", "creator": BREAK_OUT, "published": "2026-11-01T10:00:00Z", "views": 99999,
         "url": "javascript:alert(1)", "thumbnail_url": "https://img.example/x.jpg"}]})
    text_fields = {"what": SCRIPT_TAG, "how": BREAK_OUT, "risk": SCRIPT_TAG, "maturity": BREAK_OUT}
    bad = {**picks, "as_of": "2026-08-10", "act_now": [{"id": KREM, **text_fields}], "still_rising": [{"id": weird, **text_fields}],
           "watch_next": SCRIPT_TAG, "paid_reading": [BREAK_OUT],
           "digest_reading": {"summary": [SCRIPT_TAG], "todo": [BREAK_OUT]},
           "lens": {"label": SCRIPT_TAG, "note": BREAK_OUT, "items": [{"id": KREM, "line": SCRIPT_TAG}]},
           "moves": [{"id": KREM, "from": "act_now", "to": "act_now", "why": BREAK_OUT}]}
    _fake_fetch(monkeypatch)
    text = (research_report.build(run, _picks_file(run, bad), cfg=_cfg(run)) / "index.html").read_text(encoding="utf-8")
    assert "<script>alert" not in text and "<img src=x" not in text and "\"'><b>99" not in text
    assert "id='t-&quot;&#x27;&gt;&lt;b&gt;99'" in text and "href='#t-&quot;&#x27;&gt;&lt;b&gt;99'" in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "javascript:" not in text and "<span class='thumb'><img src='assets/" in text   # shown, not linked
    assert "href='https://www.tiktok.com/@ania/video/1'" in text                          # http(s) links stay


def test_unchecked_ad_library_is_said(tmp_path):
    run, picks = _uroda(tmp_path)
    _write(run.path / "02_research" / "ad_library_summary_v02.json", {"checked": False, "checks": []})
    folder = research_report.build(run, _picks_file(run, {**picks, "category": "kosmetyki naturalne"}), cfg=_cfg(run))
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert "checked in Meta Ad Library" not in text and "titles only" not in text
    assert "Meta Ad Library was not checked in this run" in text
    assert "Paid check: Meta Ad Library was not checked in this run" in text
    assert "<title>Kosmetyki naturalne Trend Report</title>" in text            # only the first letter raised


# --- issue #58: the hooks section, the hooks' band by their rising place -------------------------

POV, DZIEN, BLASK = "d7" * 16, "e8" * 16, "f9" * 16


def _hook(tid: str, name: str, *, use: str | None, rank: int, relative: dict, ad: dict | None = None) -> dict:
    row = {**_row(tid, name, "still_rising"), "kind": "hook_trend", "group": "hooks", "sub_category": "hooks",
           "relative": relative}
    if use is None:                                 # a hooks path from before 0.11: no use, no fit
        return row
    return {**row, "category_videos": 2 if use == "in_category" else 0, "videos_checked": 6,
            "plugin": {"fit": 4.25, "fit_rank": rank, "in_category": use == "in_category", "use": use,
                       "why": "Pasuje do porannej rutyny.", "ad_library": ad}}


def _with_hooks(run: RunFolder, picks: dict, hooks: list[dict], **category) -> None:
    growth = _read(run.path / "02_research" / "growth_v01.json")
    growth["params"]["category"].update(category)
    growth["trends"] += hooks
    _write(run.path / "02_research" / "growth_v02.json", growth)
    picks["still_rising"].append({"id": hooks[0]["id"], "what": "Otwarcie: POV.", "how": "POV klientki.",
                                  "risk": "Ogólny hook."})
    _write(run.path / "03_wip" / "picks_v01.json", picks)


def test_hooks_section_lists_used_and_transfer_hooks_with_their_rising_band(tmp_path):
    run, picks = _uroda(tmp_path)
    _with_hooks(run, picks, [
        _hook(POV, "pov _", use="in_category", rank=1,
              relative={"velocity_index": 1.3, "rising_position": 2, "rising_of": 40, "percentile": 0.95,
                        "band": "top 10%"},
              ad={"verdict": "competitor_found", "query": "pov krem", "advertisers": ["Marka B"]}),
        _hook(DZIEN, "dzień _ z _", use="transfer", rank=2,
              relative={"velocity_index": 0.7, "rising_position": None, "rising_of": 40},
              ad={"verdict": "none_found", "query": "dzień 3 pielęgnacji", "advertisers": []}),
        _hook(BLASK, "glow _", use="transfer", rank=3,
              relative={"velocity_index": 0.5, "rising_position": 30, "rising_of": 40, "percentile": 0.25,
                        "band": "lower half"})],
        hooks_rising=40)
    folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    text = (folder / "index.html").read_text(encoding="utf-8")
    hooks = text[text.index("<section id='hooks'>"):]
    hooks = hooks[:hooks.index("</section>")]
    assert "<h2>Hooks for Uroda</h2>" in hooks
    used, transfer = hooks.split("<h3>Fit the message, not used in Uroda yet · 2</h3>")
    assert "<h3>Already used in Uroda · 1</h3>" in used and "<b>pov _</b>" in used
    assert "Uroda videos: 2 of 6" in used and "Ad Library: competitor found (Marka B)" in used
    assert "Top 10% of TrendsMesh&#x27;s 40 rising hooks" in used and "fit 4.2" in used
    assert transfer.index("dzień _ z _") < transfer.index("glow _")                     # fit order
    assert transfer.count("<span class='pill k-hook'>transfer</span>") == 2
    assert "Nobody in Uroda uses these yet" in transfer
    assert "Not in TrendsMesh&#x27;s rising hooks" in transfer and "Lower half of TrendsMesh" in transfer
    assert "Ad Library: none found in Ad Library titles" in transfer and "Ad Library: not checked" in transfer
    # the card and the sample say the band is the hook's place among every rising hook
    assert "a hook by its place among the 40 rising hooks TrendsMesh lists" in text
    assert "rising hooks read" not in text and "of all rising hooks" not in text
    assert _read(folder / "report.json")["plugin"] == {"hooks": {"in_category": [POV], "transfer": [DZIEN, BLASK]}}


def test_report_of_a_growth_file_from_before_the_rising_band_still_renders(tmp_path):
    """A run grown before issue #58 (hooks ranked among the hooks read, no use marked) builds its page as before."""
    run, picks = _uroda(tmp_path)
    _with_hooks(run, picks, [_hook(POV, "pov _", use=None, rank=1,
                                   relative={"velocity_index": 1.3, "percentile": 0.8, "band": "top 25%"})])
    folder = research_report.build(run, run.path / "03_wip" / "picks_v01.json", cfg=_cfg(run))
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert "Top 25% of all rising hooks" in text and "a hook among all 10 rising hooks" in text
    assert "<section id='hooks'>" not in text and "TrendsMesh lists" not in text
    assert "plugin" not in _read(folder / "report.json")
