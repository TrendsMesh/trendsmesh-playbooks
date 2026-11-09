import json
from datetime import date
from pathlib import Path

from tm.meta_rows import normalise

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parses_ad3_fixture():
    rows = normalise(load("ad3_meta_daily.json"))
    assert len(rows) == 88
    first = rows[0]
    assert first.spend == 93.22 and first.results == 2 and first.ctr == 14.24
    assert first.impressions == 1166 and first.p25 == 329 and first.thruplay == 133
    assert first.unique_link_clicks_ctr == 3.831041 and first.frequency == 1.145383
    assert first.cpm == 79.95 and first.start == first.stop == date(2026, 8, 7)
    assert first.ad_id == "90000000000001" and first.name == "Ad 3 (video)"


def test_missing_results_is_zero():
    row = normalise([{"date_start": "2026-08-07", "date_stop": "2026-08-07", "id": "1", "name": "x"}])[0]
    assert row.results == 0 and row.spend == 0 and row.impressions == 0 and row.ctr == 0


def test_unreadable_numbers_are_zero_never_a_crash():
    row = normalise([{"date_start": "2026-08-07", "date_stop": "2026-08-07",
                      "amount_spent": {"value": None, "unit": "PLN"}, "impressions": "n/a",
                      "ctr": "-%", "cpm": [1], "frequency": True,
                      "results": {"indicator": "x", "values": []}}])[0]
    assert (row.spend, row.impressions, row.ctr, row.cpm, row.frequency, row.results) == (0,) * 6


def test_results_take_the_first_value():
    row = normalise([{"date_start": "2026-08-07", "date_stop": "2026-08-07", "results": {
        "values": [{"value": "7"}, {"value": "9"}]}}])[0]
    assert row.results == 7


def test_period_row_keeps_both_dates_and_a_row_without_date_is_skipped():
    rows = normalise([{"date_start": "2026-08-01", "date_stop": "2026-08-07", "amount_spent": "700"},
                      {"id": "no date"}])
    assert len(rows) == 1 and rows[0].start == date(2026, 8, 1) and rows[0].stop == date(2026, 8, 7)


def _ad3_video_rows():
    return json.loads(load("ad3_meta_daily_video_raw.json")["ad_entities"])


def test_normalise_reads_the_ladder():  # first row of the Ad 3 fixture (2026-08-07)
    r = normalise(_ad3_video_rows())[0]
    assert (r.plays, r.p25, r.p50, r.p75, r.p95, r.p100) == (955, 329, 182, 98, 60, 53)
    assert r.avg_time_s == 7.0
