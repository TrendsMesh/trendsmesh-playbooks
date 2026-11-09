"""R2: funnel diagnosis from the peak and latest windows."""

import json
from datetime import date
from pathlib import Path

import pytest

from tm import config
from tm.meta_rows import normalise
from tm.r1 import Window, aggregate
from tm.r2 import Diagnosis, diagnose, window_from_json, window_to_json

CFG = config.defaults()


def win(*, impressions=100_000, p25=30_000, thruplay=15_000, clicks=1_500, results=150,
        spend=2_000, freq=1.5, cpm=20.0):
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=spend, results=results,
                  impressions=impressions, p25=p25, thruplay=thruplay, clicks_est=clicks,
                  frequency=freq, cpm=cpm, weeks=1)


PEAK = win()


def test_hook_drop_is_hook():
    d = diagnose(PEAK, win(p25=21_000, thruplay=10_500), 1.0, CFG)
    assert d.stage == "hook" and d.refresh is True
    assert d.evidence["hook_rate"] == pytest.approx((0.30, 0.21))
    assert d.also_seen == []


def test_ctr_holds_conversion_drops_is_landing_no_refresh():
    d = diagnose(PEAK, win(results=90), 1.0, CFG)
    assert d.stage == "landing" and d.refresh is False
    assert d.evidence["conversion"] == pytest.approx((0.1, 0.06))


def test_earliest_stage_wins_and_rest_in_also_seen():
    d = diagnose(PEAK, win(p25=21_000, thruplay=7_000, clicks=900), 1.0, CFG)
    assert d.stage == "hook"
    assert set(d.also_seen) == {"middle", "promise_cta"}


def test_middle_when_hook_holds():
    d = diagnose(PEAK, win(thruplay=9_000), 1.0, CFG)
    assert d.stage == "middle" and d.refresh is True


def test_promise_cta_when_retention_holds_ctr_drops():
    d = diagnose(PEAK, win(clicks=1_000), 1.0, CFG)
    assert d.stage == "promise_cta" and d.refresh is True


def test_account_trend_similar_is_account_no_refresh():
    # the ad's results per spend fell to 0.6 and the rest of the account to 0.6 as well
    d = diagnose(PEAK, win(results=90, p25=21_000), 0.6, CFG)
    assert d.stage == "account" and d.refresh is False
    assert d.account_check == pytest.approx({"ad_rate_ratio": 0.6, "account_ratio": 0.6})
    assert "rate_ratio" not in d.evidence
    assert "hook" in d.also_seen


def test_a_flat_account_is_never_the_cause():
    d = diagnose(PEAK, win(results=90, p25=21_000), 1.0, CFG)
    assert d.stage != "account"


def test_fatigue_needs_everything_down_and_frequency_up():
    d = diagnose(PEAK, win(p25=21_000, thruplay=7_000, clicks=700, freq=1.9), 1.0, CFG)
    assert d.stage == "fatigue" and d.refresh is True
    assert d.evidence["frequency"] == pytest.approx((1.5, 1.9))
    flat = diagnose(PEAK, win(p25=21_000, thruplay=7_000, clicks=700, freq=1.6), 1.0, CFG)
    assert flat.stage == "hook"


def test_only_cpm_rising_is_auction_no_refresh():
    d = diagnose(PEAK, win(cpm=26.0), 1.0, CFG)
    assert d.stage == "auction" and d.refresh is False


def test_nothing_visible_is_unclear_no_refresh():
    d = diagnose(PEAK, win(), 1.0, CFG)
    assert d.stage == "unclear" and d.refresh is False


def test_drop_threshold_comes_from_config():
    cfg = config.defaults()
    cfg["diagnosis"]["drop"] = 0.5
    assert diagnose(PEAK, win(p25=21_000), 1.0, cfg).stage == "unclear"


def test_zero_peak_never_counts_as_a_drop():
    assert diagnose(win(p25=0), win(p25=0), 1.0, CFG).stage == "unclear"


def test_window_from_json_round_trip():
    assert window_from_json(window_to_json(PEAK)) == PEAK
    with pytest.raises(ValueError, match="impressions"):
        window_from_json({"start": "2026-10-01", "stop": "2026-10-07"})


def test_frequency_rise_comes_from_config():
    cfg = config.defaults()
    cfg["diagnosis"]["frequency_rise"] = 0.5
    bad = win(p25=21_000, thruplay=7_000, clicks=700, freq=1.9)
    assert diagnose(PEAK, bad, 1.0, cfg).stage == "hook"
    assert diagnose(PEAK, bad, 1.0, CFG).stage == "fatigue"


def test_window_from_json_without_ladder():  # a window stored by 0.2.x
    w = window_from_json({"start": "2026-10-01", "stop": "2026-10-07", "spend": 1350.0,
                          "results": 30, "impressions": 10000, "p25": 3000, "thruplay": 1200,
                          "clicks_est": 150.0, "frequency": 1.2, "cpm": 20.0, "weeks": 1})
    assert w.plays == 0 and w.p50 == 0 and w.avg_time_s == 0.0


def ladder_win(*, p75=1_200, p50=2_000, p25=4_000, plays=10_000, p95=None, p100=None):
    """Hook, CTR and ThruPlay held; only the conditional steps move."""
    p95 = round(p75 * 0.6) if p95 is None else p95
    p100 = round(p95 * 0.9) if p100 is None else p100
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=2_000, results=150,
                  impressions=100_000, p25=p25, thruplay=15_000, clicks_est=1_500, frequency=1.5,
                  cpm=20.0, weeks=1, plays=plays, p50=p50, p75=p75, p95=p95, p100=p100)


def test_rc1_ad3_middle_is_not_fading():
    path = Path(__file__).parent / "fixtures" / "ad3_meta_daily_video_raw.json"
    rows = normalise(json.loads(json.loads(path.read_text(encoding="utf-8"))["ad_entities"]))
    peak = aggregate(rows, date(2026, 8, 9), date(2026, 8, 13))
    fade = aggregate(rows, date(2026, 8, 14), date(2026, 8, 18))
    d = diagnose(peak, fade, account_ratio=1.0, cfg=None)
    assert d.stage != "middle"
    assert round(d.ladder["peak"]["p25/play"], 3) == 0.313
    assert round(d.ladder["latest"]["p25/play"], 3) == 0.295
    assert d.ladder["dropped"] == []


def test_rc4_six_pp_drop_with_enough_plays_is_middle():
    # p75/p50 0.60 -> 0.54 with 2,000 at p50 in both windows (z = 3.8)
    d = diagnose(ladder_win(), ladder_win(p75=1_080), 1.0, None)
    assert d.stage == "middle" and d.ladder["dropped"] == ["p75/p50"]


def test_six_pp_drop_on_50_plays_is_not_significant():
    # p75/p50 0.60 -> 0.54 with 50 at p50: p = 0.55
    peak = ladder_win(plays=250, p25=100, p50=50, p75=30)
    latest = ladder_win(plays=250, p25=100, p50=50, p75=27)
    d = diagnose(peak, latest, 1.0, None)
    assert d.stage != "middle" and d.ladder["dropped"] == []


def test_two_pp_drop_is_below_the_threshold():
    d = diagnose(ladder_win(), ladder_win(p75=1_160), 1.0, None)
    assert "p75/p50" not in d.ladder["dropped"] and d.stage != "middle"


def test_threshold_comes_from_config():
    cfg = config.defaults()
    cfg["diagnosis"]["middle_step_drop_pp"] = 1
    big = dict(plays=100_000, p25=40_000, p50=20_000)  # enough plays for 2 points to be significant
    d = diagnose(ladder_win(p75=12_000, **big), ladder_win(p75=11_600, **big), 1.0, cfg)
    assert "p75/p50" in d.ladder["dropped"]
    cfg["diagnosis"]["middle_step_drop_pp"] = 10
    assert diagnose(ladder_win(), ladder_win(), 1.0, cfg).ladder["dropped"] == []


def test_zero_denominator_is_no_data_not_a_drop():
    latest = ladder_win(p25=0, p50=0, p75=0, p95=0, p100=0)  # plays only: nothing reached a quarter
    d = diagnose(ladder_win(), latest, 1.0, None)
    assert d.ladder["latest"]["p50/p25"] is None and d.ladder["dropped"] == []


def test_ladder_in_one_window_only_falls_back():
    # peak has the ladder, latest comes from 0.2.x: no false collapse, v1's ThruPlay/p25 decides
    v1_latest = win()
    d = diagnose(ladder_win(p25=30_000), v1_latest, 1.0, None)
    assert d.ladder == {} and d.stage != "middle"
    d = diagnose(ladder_win(p25=30_000), win(thruplay=9_000), 1.0, None)
    assert d.stage == "middle"


def test_out_of_order_counts_are_not_a_crash_or_a_drop():
    # p50 above p25 in both windows: clamped to 1.0 at both ends
    d = diagnose(ladder_win(p25=100, p50=120), ladder_win(p25=100, p50=120), 1.0, None)
    assert d.ladder["dropped"] == [] and d.ladder["peak"]["p50/p25"] == 1.0


def test_middle_falls_back_without_ladder():
    # v1 windows (all ladder fields 0): ThruPlay/p25 with diagnosis.drop, as before
    d = diagnose(PEAK, win(thruplay=9_000), 1.0, None)
    assert d.stage == "middle" and d.ladder == {}


def test_fatigue_uses_the_ladder_middle():
    peak = ladder_win(p25=30_000)
    latest = ladder_win(p25=21_000, p75=1_080)
    latest = Window(**{**latest.__dict__, "clicks_est": 700.0, "frequency": 1.9})
    assert diagnose(peak, latest, 1.0, None).stage == "fatigue"


def test_ladder_round_trips_through_json():
    d = diagnose(ladder_win(), ladder_win(p75=1_080), 1.0, None)
    assert Diagnosis.from_json(d.to_json()).ladder == d.ladder
    assert Diagnosis.from_json({"stage": "unclear", "refresh": False}).ladder == {}


def test_window_with_ladder_fields_round_trips():
    w = Window(start=date(2026, 8, 9), stop=date(2026, 8, 13), spend=500.5, results=12,
               impressions=70_000, p25=7_185, thruplay=3_000, clicks_est=900.5, frequency=1.3,
               cpm=21.5, weeks=1, plays=22_989, p50=4_166, p75=2_318, p95=1_430, p100=1_282,
               avg_time_s=6.25)
    assert window_from_json(window_to_json(w)) == w


def test_a_step_with_odd_counts_in_either_window_is_no_data():
    # peak p50 > p25 (Meta counts view actions): the clamped 100% must not read as a drop
    peak = ladder_win(p25=1_000, p50=2_000, plays=100_000)
    latest = ladder_win(p25=4_000, p50=2_000, plays=100_000)
    d = diagnose(peak, latest, 1.0, None)
    assert "p50/p25" not in d.ladder["dropped"]
    # the same on the latest side
    d = diagnose(latest, peak, 1.0, None)
    assert "p50/p25" not in d.ladder["dropped"]
