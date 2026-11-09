"""The retention ladder: five conditional steps from plays to completed views.

Each step is the share of the viewers who reached the previous mark that also reached the next
one (p50/p25 is "of those who saw a quarter, how many saw half"). Unlike ThruPlay/p25 it does not
mix different video lengths and it points to the part of the video where viewers leave.

A step whose reached count exceeds its out-of count is clamped to 1.0 (Meta's counters are not
strictly nested); a step with nothing to divide by is None ("no data"), never a drop.
"""

from __future__ import annotations

import math

from tm.r1 import Window

STEPS = ("p25/play", "p50/p25", "p75/p50", "p95/p75", "p100/p95")
MIDDLE = ("p50/p25", "p75/p50", "p95/p75")
# the share of the video length each step covers
SEGMENT = {"p25/play": (0.0, 0.25), "p50/p25": (0.25, 0.5), "p75/p50": (0.5, 0.75),
           "p95/p75": (0.75, 0.95), "p100/p95": (0.95, 1.0)}


def counts(w: Window) -> dict[str, tuple[int, int]]:
    """Step to (reached, out of)."""
    marks = (w.plays, w.p25, w.p50, w.p75, w.p95, w.p100)
    return {step: (marks[i + 1], marks[i]) for i, step in enumerate(STEPS)}


def steps(w: Window) -> dict[str, float | None]:
    """Step to its rate, clamped to [0, 1]; None when nothing reached the previous mark."""
    out: dict[str, float | None] = {}
    for step, (reached, total) in counts(w).items():
        out[step] = None if total <= 0 else min(1.0, max(0.0, reached / total))
    return out


def two_proportion_p(s1: int, n1: int, s2: int, n2: int) -> float:
    """Two-sided p of the pooled two-proportion z test; 1.0 when either sample is empty."""
    if n1 <= 0 or n2 <= 0:
        return 1.0
    s1, s2 = min(max(s1, 0), n1), min(max(s2, 0), n2)  # a count cannot exceed its sample
    pooled = (s1 + s2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (s1 / n1 - s2 / n2) / se
    return math.erfc(abs(z) / math.sqrt(2))
