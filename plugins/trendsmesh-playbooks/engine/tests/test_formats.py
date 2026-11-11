"""R6: formats by placement."""

import json

import pytest

from tm.cli import main
from tm.formats import required, shares


def test_feed_55_percent_needs_4x5():
    # ExampleTravel: the feed was 55% of purchases
    rows = [{"placement": "feed", "results": 55}, {"placement": "instagram_reels", "results": 30},
            {"placement": "instagram_stories", "results": 15}]
    assert required(rows, 0.25) == ["9:16", "4:5"]


def test_feed_under_the_share_stays_9x16():
    rows = [{"placement": "feed", "results": 20}, {"placement": "instagram_reels", "results": 80}]
    assert required(rows, 0.25) == ["9:16"]


def test_exactly_the_share_counts():
    rows = [{"placement": "feed", "results": 25}, {"placement": "facebook_reels", "results": 75}]
    assert required(rows, 0.25) == ["9:16", "4:5"]


def test_facebook_and_instagram_feed_add_up():
    rows = [{"publisher_platform": "facebook", "platform_position": "feed", "results": "15"},
            {"publisher_platform": "instagram", "platform_position": "feed", "results": "15"},
            {"publisher_platform": "instagram", "platform_position": "story", "results": "70"}]
    assert required(rows, 0.25) == ["9:16", "4:5"]


def test_an_empty_or_unreadable_breakdown_is_an_error_not_the_base_format():
    # issue #20: these used to answer "9:16" only, which reads like a real rule result
    with pytest.raises(ValueError, match="no placement rows"):
        required([], 0.25)
    with pytest.raises(ValueError, match="no results could be read"):
        required([{"placement": "feed", "results": 0}], 0.25)
    with pytest.raises(ValueError, match="no results could be read"):
        required([{"placement": "feed"}, {"placement": "instagram_reels"}], 0.25)
    with pytest.raises(ValueError, match="names a placement"):
        required([{"results": 5}, {"results": 3}], 0.25)


# --- Meta's own row shape (issue #20) ------------------------------------------------------------

def _res(n):
    return {"indicator": "actions:offsite_conversion.fb_pixel_purchase",
            "values": [{"attribution_windows": ["default"], "value": str(n)}]}


def _meta_rows(feed, reels, stories):
    return [{"publisher_platform": "facebook", "platform_position": "feed", "results": _res(feed),
             "spend": {"value": "120.00", "unit": "PLN"}},
            {"publisher_platform": "instagram", "platform_position": "instagram_reels", "results": _res(reels)},
            {"publisher_platform": "instagram", "platform_position": "instagram_stories", "results": _res(stories)}]


def test_meta_results_objects_are_read():
    assert required(_meta_rows(12, 6, 4), 0.25) == ["9:16", "4:5"]   # feed 12 of 22
    assert required(_meta_rows(2, 14, 6), 0.25) == ["9:16"]          # feed 2 of 22


def test_shares_show_what_the_decision_read():
    feed, total = shares(_meta_rows(12, 6, 2))
    assert (feed, total) == (12.0, 20.0)


def _cli(capsys, breakdown, tmp_path, name="b.json", encoding="utf-8"):
    f = tmp_path / name
    f.write_text(json.dumps(breakdown), encoding=encoding)
    capsys.readouterr()
    code = main(["formats", "--breakdown", str(f), "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_cli_reads_the_meta_mcp_answer_as_saved(tmp_path, capsys):
    mcp = {"ad_entities": json.dumps(_meta_rows(12, 6, 2)), "client_conversation_id": "conv-0001"}
    code, out = _cli(capsys, mcp, tmp_path)
    assert code == 0 and out["formats"] == ["9:16", "4:5"], out
    assert out["feed_share"] == 0.6 and out["results"] == 20.0 and out["rows"] == 3
    saved = {"_tool": "ads_get_ad_entities", "_input": {}, "_at": "2026-11-05T08:00:00+00:00",
             "answer": {"ad_entities": json.dumps(_meta_rows(2, 14, 6))}}
    code, out = _cli(capsys, saved, tmp_path, "saved.json", "utf-8-sig")
    assert code == 0 and out["formats"] == ["9:16"] and out["feed_share"] == 0.0909, out


@pytest.mark.parametrize("breakdown", [
    {"ad_entities": "[]", "client_conversation_id": "conv-0001"},
    {"ad_entities": "not json", "client_conversation_id": "conv-0001"},
    {"client_conversation_id": "conv-0001"},
    {"error": {"raw": "Rate limit"}},
    [{"platform_position": "feed", "results": {"indicator": "x"}}],
])
def test_cli_fails_loudly_when_nothing_can_be_read(tmp_path, capsys, breakdown):
    code, out = _cli(capsys, breakdown, tmp_path)
    assert code == 1 and out["status"] == "error", out
    assert "formats" not in out
