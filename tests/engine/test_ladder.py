"""The retention ladder: conditional steps, clamping and the two-proportion test."""

from datetime import date

import pytest

from tm import ladder
from tm.r1 import Window


def window(*, plays=0, p25=0, p50=0, p75=0, p95=0, p100=0):
    return Window(start=date(2026, 10, 1), stop=date(2026, 10, 7), spend=100.0, results=10,
                  impressions=10_000, p25=p25, thruplay=0, clicks_est=100.0, frequency=1.0,
                  cpm=10.0, weeks=1, plays=plays, p50=p50, p75=p75, p95=p95, p100=p100)


def test_steps_and_segments():
    assert ladder.STEPS == ("p25/play", "p50/p25", "p75/p50", "p95/p75", "p100/p95")
    assert ladder.MIDDLE == ("p50/p25", "p75/p50", "p95/p75")
    assert set(ladder.SEGMENT) == set(ladder.STEPS)
    assert ladder.SEGMENT["p95/p75"] == (0.75, 0.95)


def test_counts_pair_reached_with_out_of():
    w = window(plays=100, p25=40, p50=20, p75=10, p95=5, p100=4)
    assert ladder.counts(w) == {"p25/play": (40, 100), "p50/p25": (20, 40), "p75/p50": (10, 20),
                                "p95/p75": (5, 10), "p100/p95": (4, 5)}
    assert ladder.steps(w)["p75/p50"] == 0.5


def test_ladder_clamps_out_of_order_counts():
    w = window(plays=0, p25=10, p50=12, p75=0)
    assert ladder.steps(w)["p25/play"] is None and ladder.steps(w)["p50/p25"] == 1.0
    assert ladder.steps(w)["p75/p50"] == 0.0


def test_two_proportion_p_values():
    assert ladder.two_proportion_p(1200, 2000, 1080, 2000) < 0.001
    assert ladder.two_proportion_p(30, 50, 27, 50) > 0.5
    assert ladder.two_proportion_p(5, 0, 3, 10) == 1.0
    assert ladder.two_proportion_p(0, 10, 0, 10) == 1.0


def test_two_proportion_p_clamps_counts_to_the_sample():
    assert ladder.two_proportion_p(12, 10, 12, 10) == 1.0
    assert ladder.two_proportion_p(-3, 10, 0, 10) == 1.0
