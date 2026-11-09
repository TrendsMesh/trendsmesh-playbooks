"""R1 tests. Synthetic ads use week-long period rows. With today = 2026-11-05 and
drop_recent_days = 2 the last included day is 2026-11-03; with history_days = 28 and
window_days = 7 the buckets are (0 = newest):
    b0 Oct 28 - Nov 3, b1 Oct 21 - 27, b2 Oct 14 - 20, b3 Oct 7 - 13.
"""
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from tm.cli import main
from tm.meta_rows import normalise
from tm.r1 import WinnerCfg, aggregate, load_ads, mid_p_two_sided, rank
from tm.runfolder import RunFolder

def load(name):
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))


TODAY = date(2026, 11, 5)
LAST = date(2026, 11, 3)
CFG = WinnerCfg(history_days=28, target_cpa=15.0)


def week(ad, k, spend, results, name=None):
    """A 7-day period row for bucket k."""
    stop = LAST - timedelta(days=7 * k)
    return {"id": ad, "name": name or ad, "date_start": str(stop - timedelta(days=6)),
            "date_stop": str(stop), "amount_spent": {"value": str(spend), "unit": "PLN"},
            "impressions": "1000", "results": {"values": [{"value": str(results)}]}}


def ad_rows(ad, weeks):
    """weeks = [(spend, results)] for b0, b1, b2, b3."""
    return [week(ad, k, s, r) for k, (s, r) in enumerate(weeks)]


# Ad A: peak b2 = 600 PLN / 50 results (cpr 12); latest b0 = 600 / 30 (cpr 20, +66.7%).
# n = 80, p0 = 600/1200 = 0.5 -> expected 40 in the latest window, 30 seen: significant.
A = ad_rows("A", [(600, 30), (600, 40), (600, 50), (600, 40)])
# Account constant elsewhere: ad B earns 1000 PLN / 100 results every week.
B = ad_rows("B", [(1000, 100)] * 4)


def run_rank(ads, account, cfg=CFG, today=TODAY):
    return rank({k: normalise(v) for k, v in ads.items()}, normalise(account), cfg, today)


def only(r, ad):
    return next(c for c in r.candidates if c.ad_id == ad)


def test_calibration_30_to_18_equal_spend():  # PLAYBOOK.md: "30 -> 18 purchases is p ~ 0.09"
    assert 0.08 < mid_p_two_sided(r_late=18, n=48, p0=0.5) < 0.09


def test_mid_p_is_one_when_nothing_changed_and_caps_at_one():
    assert mid_p_two_sided(24, 48, 0.5) == pytest.approx(1.0)  # F(23) + f(24)/2 is 0.5 -> 2 * 0.5
    assert mid_p_two_sided(48, 48, 0.5) == 1.0
    assert mid_p_two_sided(0, 10, 0.0) == 1.0  # nothing is possible but zero: no evidence


def test_fading_ad_with_a_steady_account():
    r = run_rank({"A": A}, A + B)
    c = only(r, "A")
    assert c.verdict == "fading" and c.rank == 1
    assert (c.peak.start, c.peak.stop) == (date(2026, 10, 14), date(2026, 10, 20))
    assert (c.latest.start, c.latest.stop) == (date(2026, 10, 28), date(2026, 11, 3))
    assert (c.peak.cpr, c.latest.cpr) == (12.0, 20.0)
    assert c.cost_increase == pytest.approx(2 / 3, abs=1e-5)
    assert c.account_ratio == 1.0  # rest of the account is flat
    assert c.p_value == pytest.approx(mid_p_two_sided(30, 80, 0.5), abs=1e-5) and c.p_value < 0.1
    assert c.value_to_recover == 400.0  # 600 PLN a week at the peak * (20/12 - 1)


def test_whole_account_drop_is_not_fading():
    # B falls from 100 to 60 results on the same spend in the latest week (rest rate 0.06 vs 0.10),
    # so a = 0.6 and p0 = 360/960 = 0.375: 80 * 0.375 = 30 results are expected, 30 seen.
    b_drop = ad_rows("B", [(1000, 60), (1000, 100), (1000, 100), (1000, 100)])
    r = run_rank({"A": A}, A + b_drop)
    c = only(r, "A")
    assert c.account_ratio == pytest.approx(0.6)
    assert c.cost_increase == pytest.approx(2 / 3, abs=1e-5)  # the ad did get dearer ...
    assert c.p_value > 0.5 and c.verdict == "stable"  # ... but no more than the account
    assert r.ranked == []


def test_detrend_off_ignores_the_account():
    b_drop = ad_rows("B", [(1000, 60), (1000, 100), (1000, 100), (1000, 100)])
    cfg = WinnerCfg(history_days=28, target_cpa=15.0, detrend_by_account=False)
    c = only(run_rank({"A": A}, A + b_drop, cfg), "A")
    assert c.account_ratio == 1.0 and c.verdict == "fading"


def test_too_few_results_not_ranked():
    d = ad_rows("D", [(100, 5), (100, 5), (100, 5), (100, 5)])  # 20 results in all history
    r = run_rank({"A": A, "D": d}, A + d + B)
    assert only(r, "D").verdict == "not_enough_data" and only(r, "D").rank is None
    assert [c.ad_id for c in r.ranked] == ["A"]
    assert r.to_json()["ranking"] == ["A"]
    assert r.candidates[-1].ad_id == "D"  # listed after the judged ads


def test_no_earlier_window_with_enough_results_is_not_enough_data():
    e = ad_rows("E", [(600, 30), (600, 10), (600, 10), (600, 9)])
    assert only(run_rank({"E": e}, e), "E").verdict == "not_enough_data"


def test_last_two_days_ignored():
    crash = [  # Nov 4 and Nov 5: spend and no results
        {"id": "A", "name": "A", "date_start": "2026-11-04", "date_stop": "2026-11-04",
         "amount_spent": "5000", "results": {"values": [{"value": "0"}]}},
        {"id": "A", "name": "A", "date_start": "2026-11-05", "date_stop": "2026-11-05",
         "amount_spent": "5000"}]
    plain = run_rank({"A": A}, A + B).to_json()
    crashed = run_rank({"A": A + crash}, A + crash + B).to_json()
    assert crashed == plain
    # but the 3rd of November is the last day that counts
    nov3 = [dict(crash[0], date_start="2026-11-03", date_stop="2026-11-03", amount_spent="600")]
    assert only(run_rank({"A": A + nov3}, A + nov3 + B), "A").latest.spend == 1200


def test_not_a_winner_when_peak_cost_is_above_target():
    cfg = WinnerCfg(history_days=28, target_cpa=10.0)  # peak cpr is 12
    assert only(run_rank({"A": A}, A + B, cfg), "A").verdict == "not_a_winner"


def test_target_is_the_median_weekly_account_cpr_when_not_given():
    cfg = WinnerCfg(history_days=28)
    r = run_rank({"A": A}, A + B, cfg)
    # account weeks (A + B): 1600/130, 1600/140, 1600/150, 1600/140 -> median of the middle two
    assert r.target_cpa == pytest.approx(1600 / 140, abs=1e-3)
    assert only(r, "A").verdict == "not_a_winner"  # peak cpr 12 > 11.43


def test_ranking_order_by_value_to_recover():
    c_rows = ad_rows("C", [(1200, 60), (1200, 80), (1200, 100), (1200, 80)])  # cpr 12 -> 20, 1200 a week
    cfg = WinnerCfg(history_days=28, target_cpa=15.0, detrend_by_account=False)
    r = run_rank({"A": A, "C": c_rows}, A + c_rows, cfg)
    assert [c.ad_id for c in r.ranked] == ["C", "A"]
    assert [c.value_to_recover for c in r.ranked] == [800.0, 400.0]
    assert [c.rank for c in r.ranked] == [1, 2]
    by_spend = WinnerCfg(history_days=28, target_cpa=15.0, detrend_by_account=False,
                         rank_by="peak_spend")
    r2 = run_rank({"A": A, "C": c_rows}, A + c_rows, by_spend)
    assert [c.value_to_recover for c in r2.ranked] == [1200.0, 600.0]


def test_latest_window_grows_until_enough_results():
    # b0 has 20 results, b0+b1 have 20 + 15 = 35: the latest window is two buckets (14 days)
    f = ad_rows("F", [(400, 20), (400, 15), (600, 60), (600, 50)])
    c = only(run_rank({"F": f}, f), "F")
    assert (c.latest.start, c.latest.stop, c.latest.weeks) == (date(2026, 10, 21), date(2026, 11, 3), 2)
    assert c.latest.cpr == pytest.approx(800 / 35)
    assert c.peak.start == date(2026, 10, 14) and c.peak.stop == date(2026, 10, 20)


def test_period_rows_equal_daily_rows():
    days = [{"id": "A", "date_start": str(LAST - timedelta(days=d)), "date_stop": str(LAST - timedelta(days=d)),
             "amount_spent": "100", "impressions": "100", "results": {"values": [{"value": "5"}]}}
            for d in range(7)]
    period = [{"id": "A", "date_start": str(LAST - timedelta(days=6)), "date_stop": str(LAST),
               "amount_spent": "700", "impressions": "700", "results": {"values": [{"value": "35"}]}}]
    a, b = (aggregate(normalise(x), LAST - timedelta(days=6), LAST) for x in (days, period))
    assert (a.spend, a.results, a.impressions) == (b.spend, b.results, b.impressions) == (700, 35, 700)


def test_period_row_straddling_a_boundary_goes_by_its_stop_day():
    straddle = normalise([{"date_start": "2026-10-25", "date_stop": "2026-10-31", "amount_spent": "70"}])
    assert aggregate(straddle, date(2026, 10, 28), LAST).spend == 70   # b0: stop day Oct 31
    assert aggregate(straddle, date(2026, 10, 21), date(2026, 10, 27)).spend == 0


def test_window_ratios_and_weighted_means():
    rows = normalise([
        {"date_start": "2026-10-01", "date_stop": "2026-10-01", "amount_spent": "50", "impressions": "1000",
         "unique_link_clicks_ctr": "2.0", "video_p25_watched_actions": "300",
         "video_thruplay_watched_actions": "150", "results": {"values": [{"value": "4"}]},
         "frequency": "1.5", "cpm": "50"},
        {"date_start": "2026-10-02", "date_stop": "2026-10-02", "amount_spent": "150", "impressions": "3000",
         "unique_link_clicks_ctr": "1.0", "video_p25_watched_actions": "600",
         "video_thruplay_watched_actions": "300", "results": {"values": [{"value": "6"}]},
         "frequency": "2.0", "cpm": "30"}])
    w = aggregate(rows, date(2026, 10, 1), date(2026, 10, 7))
    assert w.cpr == 20 and w.clicks_est == 50 and w.weeks == 1
    assert w.ctr == 0.0125 and w.hook_rate == 0.225 and w.middle_rate == 0.5 and w.conversion == 0.2
    assert w.frequency == 1.875 and w.cpm == 35  # (1.5*1000 + 2*3000)/4000, (50*1000 + 30*3000)/4000


def test_empty_window_is_guarded():
    w = aggregate([], date(2026, 10, 1), date(2026, 10, 7))
    assert math.isinf(w.cpr) and w.hook_rate == w.middle_rate == w.ctr == w.conversion == 0.0
    assert w.frequency == 0.0 and w.cpm == 0.0


def test_fractional_results_are_rounded_for_the_test():
    a = [dict(r) for r in A]
    a[0]["results"] = {"values": [{"value": "30.4"}]}  # rounds to 30; 29.6 would not reach min_results
    c = only(run_rank({"A": a}, a + B), "A")
    assert c.p_value == pytest.approx(mid_p_two_sided(30, 80, 0.5), abs=1e-5)


def test_winner_cfg_from_config():
    cfg = WinnerCfg.from_config({"winner": {"event": None, "window_days": 14, "target_cpa": None,
                                            "rank_by": "peak_spend", "bogus": 1}})
    assert cfg.window_days == 14 and cfg.target_cpa is None and cfg.rank_by == "peak_spend"
    assert cfg.history_days == 90 and WinnerCfg.from_config(None).min_results == 30


def test_load_ads_accepts_dict_and_flat_list():
    flat = load_ads(A + B)
    keyed = load_ads({"A": [{k: v for k, v in r.items() if k != "id"} for r in A]})
    assert sorted(flat) == ["A", "B"] and list(keyed) == ["A"]
    assert all(r.ad_id == "A" for r in keyed["A"])


def test_cli_writes_versioned_ranking_and_manifest(tmp_path):
    run = RunFolder.create(tmp_path, "r1", date(2026, 11, 5))
    ads, acc = tmp_path / "ads.json", tmp_path / "acc.json"
    ads.write_text(json.dumps(A), encoding="utf-8")   # flat list form
    acc.write_text(json.dumps(A + B), encoding="utf-8")
    argv = ["r1", "--run", str(run.path), "--ads", str(ads), "--account", str(acc),
            "--today", "2026-11-05", "--json"]
    assert main(argv) == 0
    assert main(argv) == 0
    first = run.path / "01_base" / "winner_ranking_v01.json"
    assert (run.path / "01_base" / "winner_ranking_v02.json").is_file()
    data = json.loads(first.read_text(encoding="utf-8"))
    assert data["candidates"][0]["ad_id"] == "A" and data["last_day"] == "2026-11-03"
    text = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "01_base/winner_ranking_v01.json" in text and "01_base/winner_ranking_v02.json" in text


def test_cli_takes_raw_mcp_answers_in_several_pages(tmp_path, capsys):
    """Raw Meta answers saved as they came: {"data": [...]} pages, several files per flag."""
    run = RunFolder.create(tmp_path, "pages", date(2026, 11, 5))
    p1, p2 = tmp_path / "ads_p1.json", tmp_path / "ads_p2.json"
    p1.write_text(json.dumps({"data": A, "paging": {"next": "x"}}), encoding="utf-8")
    p2.write_text(json.dumps({"data": B}), encoding="utf-8")
    capsys.readouterr()
    assert main(["r1", "--run", str(run.path), "--ads", str(p1), str(p2),
                 "--account", str(p1), str(p2), "--today", "2026-11-05", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 2
    data = json.loads((run.path / "01_base" / "winner_ranking_v01.json").read_text(encoding="utf-8"))
    assert {c["ad_id"] for c in data["candidates"]} == {"A", "B"}


def test_ranking_windows_feed_tm_diagnose(tmp_path, capsys):
    """The skill passes a candidate's peak and latest windows from the ranking to `tm diagnose`."""
    run = RunFolder.create(tmp_path, "r1d", date(2026, 11, 5))
    rows = load("ad3_meta_daily.json")
    ads, acc = tmp_path / "ads.json", tmp_path / "acc.json"
    ads.write_text(json.dumps({"90000000000001": rows}), encoding="utf-8")
    acc.write_text(json.dumps(rows), encoding="utf-8")
    assert main(["r1", "--run", str(run.path), "--ads", str(ads), "--account", str(acc),
                 "--today", "2026-11-05", "--json"]) == 0
    data = json.loads((run.path / "01_base" / "winner_ranking_v01.json").read_text(encoding="utf-8"))
    c = data["candidates"][0]
    for key in ("impressions", "p25", "thruplay", "clicks_est", "frequency", "cpm", "cpr"):
        assert key in c["peak"] and key in c["latest"], key
    capsys.readouterr()
    assert main(["diagnose", "--run", str(run.path), "--peak", json.dumps(c["peak"]),
                 "--latest", json.dumps(c["latest"]), "--account-ratio", str(c["account_ratio"]),
                 "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["file"] == "04_final/diagnosis_v01.json"


def test_ad3_fixture_is_sensitive_to_low_volume():
    # 93 results in 88 days: on Nov 4 no earlier window reaches 30 results; one day later the
    # first week (39 results) does, and the 12-week latest window looks worse. Documents the
    # method's sensitivity at low volume.
    rows = normalise(load("ad3_meta_daily.json"))
    ads = {"90000000000001": rows}
    c4 = rank(ads, rows, WinnerCfg(), date(2026, 11, 4)).candidates[0]
    c5 = rank(ads, rows, WinnerCfg(), date(2026, 11, 5)).candidates[0]
    assert c4.verdict == "not_enough_data" and c5.verdict == "fading"
    assert c5.peak.results == 39 and c5.latest.results == 54


def test_rest_of_account_collapse_is_stable():
    # The rest of the account (B) spends 1000 PLN in the latest week and gets 0 results.
    # Rest rate: latest 0, peak 0.10 -> a = 0, p0 = 0, p = 1: the ad is not judged on its own.
    b = ad_rows("B", [(1000, 0), (1000, 100), (1000, 100), (1000, 100)])
    c = only(run_rank({"A": A}, A + b), "A")
    assert c.account_ratio == 0.0 and c.p_value == 1.0 and c.verdict == "stable"
    assert "no results in the latest window" in c.note


def test_no_rest_spend_falls_back_to_one_with_its_own_note():
    c = only(run_rank({"A": A}, A), "A")
    assert c.account_ratio == 1.0 and "no spend or no results in the peak window" in c.note


def test_account_rows_that_lack_the_ad_fall_back_to_one():
    small = ad_rows("B", [(100, 10)] * 4)
    c = only(run_rank({"A": A}, small), "A")
    assert c.account_ratio == 1.0 and "do not include it" in c.note


def test_period_row_crossing_the_cut_is_counted():
    cross = [{"id": "A", "date_start": "2026-10-29", "date_stop": "2026-11-04", "amount_spent": "700"}]
    c = only(run_rank({"A": A + cross}, A + B), "A")
    assert c.dropped_rows == 1 and "left out" in c.note
    assert run_rank({"A": A + cross}, A + B).to_json()["candidates"][0]["dropped_rows"] == 1


def test_mid_p_edges():
    assert mid_p_two_sided(0, 0, 0.5) == 1.0   # n = 0: f(0) = 1, no evidence
    assert mid_p_two_sided(10, 10, 1.0) == 1.0  # p0 = 1: all 10 seen is certain
    assert mid_p_two_sided(5, 10, 1.0) == 0.0   # p0 = 1 and only 5 of 10: impossible


def test_cli_errors_stay_one_json_error(tmp_path, capsys):
    run = RunFolder.create(tmp_path, "bad", date(2026, 11, 5))
    ads, acc = tmp_path / "ads.json", tmp_path / "acc.json"
    ads.write_text(json.dumps({"A": 5}), encoding="utf-8")   # rows is not a list
    acc.write_text(json.dumps([1, 2]), encoding="utf-8")
    argv = ["r1", "--run", str(run.path), "--ads", str(ads), "--account", str(acc), "--json"]
    capsys.readouterr()
    assert main(argv) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and json.loads(out[0])["status"] == "error"


def test_cli_refuses_an_invalid_winner_config(tmp_path, capsys):
    run = RunFolder.create(tmp_path, "cfg", date(2026, 11, 5))
    (run.path / "config.yaml").write_text("winner:\n  window_days: 10\n  fade_p_value: 2\n", encoding="utf-8")
    ads = tmp_path / "ads.json"
    ads.write_text("[]", encoding="utf-8")
    capsys.readouterr()
    assert main(["r1", "--run", str(run.path), "--ads", str(ads), "--account", str(ads), "--json"]) == 1
    out = capsys.readouterr().out
    assert "winner.fade_p_value" in out and "error" in out


def test_window_peak_matches_the_reference_ladder():  # retention_ladder_v01.json "peak 08-09..08-13"
    rows = normalise(json.loads(load("ad3_meta_daily_video_raw.json")["ad_entities"]))
    w = aggregate(rows, date(2026, 8, 9), date(2026, 8, 13))
    assert (w.plays, w.p25, w.p50, w.p75, w.p95, w.p100) == (22989, 7185, 4166, 2318, 1430, 1282)
    inside = [r for r in rows if date(2026, 8, 9) <= r.stop <= date(2026, 8, 13)]
    expected = sum(r.avg_time_s * r.plays for r in inside) / w.plays
    assert w.avg_time_s == pytest.approx(expected) and w.avg_time_s > 0
    assert w.to_json()["plays"] == 22989 and w.to_json()["p100"] == 1282


def test_window_with_no_plays_has_zero_avg_time():
    assert aggregate([], date(2026, 8, 9), date(2026, 8, 13)).avg_time_s == 0.0
