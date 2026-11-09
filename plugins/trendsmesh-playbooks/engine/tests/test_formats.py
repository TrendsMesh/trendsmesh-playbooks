"""R6: formats by placement."""

from tm.formats import required


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


def test_empty_or_zero_breakdown_gives_the_base_format():
    assert required([], 0.25) == ["9:16"]
    assert required([{"placement": "feed", "results": 0}], 0.25) == ["9:16"]
    assert required([{"placement": "feed"}, {"results": 5}], 0.25) == ["9:16"]
