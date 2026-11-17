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


# --- reading a saved Meta answer (issues #28, #20) --------------------------------------------------

from tm.meta_rows import answer_rows  # noqa: E402

_ROWS = [{"id": "1", "date_start": "2026-10-01", "date_stop": "2026-10-07"}]


def test_answer_rows_opens_the_meta_mcp_envelope():
    # The Meta MCP answers ads_get_ad_entities as the rows in a JSON text, next to its own ids.
    mcp = {"ad_entities": json.dumps(_ROWS), "client_conversation_id": "c-1"}
    assert answer_rows(mcp) == _ROWS
    assert answer_rows({"ad_entities": _ROWS, "client_conversation_id": "c-1"}) == _ROWS
    assert answer_rows(json.dumps(mcp)) == _ROWS   # the whole answer as a JSON text


def test_answer_rows_reads_every_saved_shape():
    assert answer_rows(_ROWS) == _ROWS
    assert answer_rows({"data": _ROWS, "paging": {"next": "x"}}) == _ROWS
    assert answer_rows({"rows": _ROWS}) == _ROWS
    saved = {"_tool": "ads_get_ad_entities", "_input": {}, "_at": "2026-11-01T00:00:00+00:00",
             "answer": {"ad_entities": json.dumps(_ROWS), "client_conversation_id": "c-1"}}
    assert answer_rows(saved) == _ROWS   # the collector's envelope
    blocks = [{"type": "text", "text": json.dumps({"ad_entities": json.dumps(_ROWS)})}]
    assert answer_rows(blocks) == _ROWS   # MCP content blocks, as a tool result file holds them
    assert answer_rows({"ad_entities": json.dumps({"data": _ROWS})}) == _ROWS


def test_answer_rows_is_none_when_it_is_not_a_meta_answer():
    assert answer_rows({"ad_entities": "not json", "client_conversation_id": "c-1"}) is None
    assert answer_rows({"client_conversation_id": "c-1"}) is None
    assert answer_rows({"90000000000001": _ROWS}) is None   # {ad_id: rows}: the caller's own shape
    assert answer_rows({"error": {"raw": "Rate limit"}}) is None
    assert answer_rows("not json") is None and answer_rows(None) is None
    assert answer_rows({"ad_entities": "[]"}) == []   # an answer with no rows is still an answer


def test_results_readable_tells_a_zero_from_a_missing_value():
    from tm.meta_rows import results_readable
    assert results_readable({"values": [{"value": "0"}]}) and results_readable(3) and results_readable("2")
    assert not results_readable(None) and not results_readable({"indicator": "x"})
    assert not results_readable({"values": []}) and not results_readable("n/a")
