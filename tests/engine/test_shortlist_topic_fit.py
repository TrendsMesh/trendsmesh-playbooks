"""Issue #142 item 4 (#148 line 23): an organic video shortlist scores its topics for the channel like its hooks and
formats, up to 20 topics of their own; a topic with a mean fit under 3 is a weak fit and never takes a B3 place."""

from __future__ import annotations

import pytest

from tm import shortlist

SCORES = ("brand_fit", "persona_fit", "bridge", "lifecycle", "transfer", "sensitivity", "feasibility")


def _fit(n, why="w"):
    return {**dict.fromkeys(SCORES, n), "why": why}


def _pool(topics=25):
    pool = {"h1": {"kind": "hook_trend", "name": "hook"}, "f1": {"kind": "format_trend", "name": "format"}}
    pool.update({f"t{i:02d}": {"kind": "topic_trend", "name": f"topic {i}"} for i in range(topics)})
    return pool


def _topic_rows(n=25):
    return [{"id": f"t{i:02d}", "name": f"topic {i}", "label": "topic", "flags": [], "score": 50 - i, "creators": 1,
             "views": 1} for i in range(n)]


def test_the_best_20_topics_join_the_fit_candidates():
    found = shortlist.fit_candidates(_pool(), [r["id"] for r in _topic_rows()])
    labels = [c["label"] for c in found]
    assert labels.count("topic") == shortlist.TOPIC_FIT_CAP == 20 and {"hook", "format"} <= set(labels)
    assert [c["id"] for c in found if c["label"] == "topic"] == [f"t{i:02d}" for i in range(20)]   # the ranked best
    assert [c["label"] for c in shortlist.fit_candidates(_pool())] == ["hook", "format"]   # without topics: as before


def test_the_topics_must_be_scored_too():
    pool = _pool(3)
    topics = ["t00", "t01", "t02"]
    data = {"h1": _fit(4), "f1": _fit(4), "t00": _fit(4), "t01": _fit(2)}
    wrong = shortlist.check_fit(data, pool, topics)
    assert len(wrong) == 1 and "topic 2" in wrong[0] and "topics" in wrong[0]
    assert shortlist.check_fit({**data, "t02": _fit(3)}, pool, topics) == []


def test_a_weak_topic_never_takes_a_place():
    rows = _topic_rows(4)
    scored = {"hooks": [], "formats": [], "sounds": [], "topics": rows}
    fit = {"t00": _fit(2, "Temu hauls are not an AI explainer's"), "t01": _fit(4), "t02": _fit(5), "t03": _fit(1)}
    shortlist.apply_fit(scored, fit)
    by_id = {r["id"]: r for r in scored["topics"]}
    assert shortlist.WEAK_FIT in by_id["t00"]["flags"] and by_id["t00"]["plugin"]["fit"]["score"] == 2
    assert shortlist.WEAK_FIT not in by_id["t01"]["flags"]
    assert [r["id"] for r in scored["topics"]] == ["t01", "t02", "t00", "t03"]   # weak last, the rest in their order
    split = {"places": {"hooks": 0, "topics": 4, "formats": 0, "sounds": 0}, "leading": "topics"}
    pulled = [r["id"] for r in shortlist.pulls(scored, split)["rows"]]
    assert "t00" not in pulled and "t03" not in pulled and {"t01", "t02"} <= set(pulled)


@pytest.mark.parametrize("fit", [None, {}])
def test_without_scores_the_topics_keep_their_order(fit):
    scored = {"hooks": [], "formats": [], "sounds": [], "topics": _topic_rows(3)}
    shortlist.apply_fit(scored, fit)
    assert [r["id"] for r in scored["topics"]] == ["t00", "t01", "t02"]
    assert all(shortlist.WEAK_FIT not in r["flags"] for r in scored["topics"])
