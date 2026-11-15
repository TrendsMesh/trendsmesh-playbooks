"""tm.research_digest and the backtest: TR3's calibration, the previous run (A2, V24), the fetch plan
and the digest (TR8), the call check and library/trend_calls.jsonl (TR9).

The backtests and the digest's calls are checked against the handoff's beauty files. Its digest.json
was made with `--prev-cards` (two full trend dumps, not in the package), so its new and ended lists
are not rebuilt; without them the reference tool gives the `up` and `down` asserted here. Its 29 Oct
snapshot was written while confidence still read the evidence language, so 9 of its rows differ
from a rebuild in `confidence` alone: the digest never reads confidence, so the calls and hit rate
are equal whether the previous state is the reference file or our rebuild (both are checked).

The weekly cases (a trend that left the map, pool ids, the fetch plan, the previous run) use two
small "nails" runs built here, `runs/04-trend-research/2026-10-29_nails` and `2026-11-04_nails`.
"""

import errno
import json
import os
from datetime import date

import pytest

import beauty
from tm import brief_config, config, page, research_config, research_digest, research_growth, research_map, state, trends
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

AS_OF = date(2026, 11, 4)
REBUILT_AS_OF = date(2026, 10, 29)
RECONSTRUCTED = beauty.BEAUTY / "02_research" / "snapshot_growth_2026-10-29_reconstructed.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strip_calls(calls: list[dict]) -> list[dict]:
    return [{k: v for k, v in c.items() if k != "plugin"} for c in calls]


@pytest.fixture(scope="module")
def beauty_run(tmp_path_factory):
    """The beauty run, mapped, with growth as of 4 Nov (its snapshot is the digest's "now")."""
    run = beauty.mapped_run(tmp_path_factory.mktemp("beauty"))
    research_growth.compute(run, AS_OF, beauty.cfg())
    return run


# --- the backtest (TR3 calibration, TR9) -------------------------------------------------------

@pytest.mark.private_data
@pytest.mark.parametrize("as_of", ["2026-09-23", "2026-10-07", "2026-10-21"])
def test_backtest_v3_rebuilds_three_dates(beauty_run, as_of, capsys):
    path = research_growth.backtest(beauty_run, date.fromisoformat(as_of), beauty.cfg())
    assert path == beauty_run.path / "03_wip" / f"backtest_{as_of}_rule_v3_v01.json"
    assert _read(path) == beauty.as_rising_bands(beauty.handoff(f"03_wip/backtest_{as_of}_rule_v3.json"), beauty_run)
    his_md = (beauty.BEAUTY / "03_wip" / f"backtest_{as_of}_rule_v3.md").read_text(encoding="utf-8")
    assert path.with_suffix(".md").read_text(encoding="utf-8") == his_md.replace("\r\n", "\n")
    assert f"03_wip/backtest_{as_of}_rule_v3_v01.json" in (beauty_run.path / "manifest.md").read_text(encoding="utf-8")

    # the command writes the next version beside it, never over it
    assert main(["research", "backtest", "--run", str(beauty_run.path), "--as-of", as_of, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["json"] == f"03_wip/backtest_{as_of}_rule_v3_v02.json"
    assert payload["summary"] == _read(path)["summary"]
    assert _read(beauty_run.path / payload["json"]) == _read(path)
    assert main(["research", "backtest", "--run", str(beauty_run.path), "--as-of", as_of]) == 0
    assert "new creators in the next 14 days" in capsys.readouterr().out
    assert main(["research", "backtest", "--run", str(beauty_run.path), "--as-of", as_of, "--horizon", "0"]) == 1


# --- the digest and the call check (TR8, TR9) --------------------------------------------------

@pytest.mark.private_data
def test_digest_calls_match_beauty_digest(beauty_run, capsys):
    original = beauty.handoff("02_research/digest.json")
    path = research_digest.diff(beauty_run, RECONSTRUCTED, beauty.cfg())
    assert path.parent.name == "02_research" and path.name.startswith("digest_v")
    digest = _read(path)
    assert _strip_calls(digest["calls"]) == original["calls"] and digest["hit_rate"] == original["hit_rate"]
    assert digest["hit_rate"] == {"act_now": [0.83, 12], "past_peak": [1.0, 2]}
    assert [u["name"] for u in digest["up"]] == [
        "Sephora Savings Event sale hauls and picks", "Medicube K-beauty skincare hauls and routines",
        "Hair braiding and long-hair styling", "Keratin hair straightening salon transformations"]
    assert len(digest["down"]) == 22
    assert (digest["prev"], digest["now"]) == (original["prev"], beauty.as_rising_bands(original["now"], beauty_run))
    # the reference file has no pool_ids, so it is a rebuilt previous state: new by the original rule, ended left out
    assert digest["new"] == [] and digest["ended"] == [] and digest["reidentified"] == []
    assert digest["plugin"]["prev_rebuilt"] is True and digest["plugin"]["ended_checked"] is False
    assert {c["plugin"]["verdict"] for c in digest["calls"]} == {"held", "missed"}

    # our own rebuild of 29 Oct (V24, F9) differs from the reference only in confidence, which the digest never
    # reads: the same calls, up and down, found by `tm research digest` on its own
    research_digest.rebuild_previous(beauty_run, REBUILT_AS_OF, beauty.cfg())
    assert main(["research", "digest", "--run", str(beauty_run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    ours = _read(beauty_run.path / payload["json"])
    assert payload["prev"] == "02_research/snapshot_growth_2026-10-29_rebuilt_v01.json"
    assert _strip_calls(ours["calls"]) == original["calls"] and ours["hit_rate"] == original["hit_rate"]
    assert (ours["up"], ours["down"]) == (digest["up"], digest["down"])
    assert "rebuilt" in payload["message"]


@pytest.mark.private_data
def test_digest_writes_fourteen_call_rows_once(tmp_path, capsys):
    run = beauty.mapped_run(tmp_path)
    research_growth.compute(run, AS_OF, beauty.cfg())
    calls_file = tmp_path / "ws" / "library" / "trend_calls.jsonl"
    first = _read(research_digest.diff(run, RECONSTRUCTED, beauty.cfg()))
    assert first["plugin"]["calls_added"] == 14
    rows = _lines(calls_file)
    assert len(rows) == 14
    original = {c["id"]: c for c in beauty.handoff("02_research/digest.json")["calls"]}
    prev = _read(RECONSTRUCTED)["trends"]
    for row in rows:
        then = prev[row["trend_id"]]
        assert set(row) == {"schema", "call_run", "checked_in_run", "category", "market", "trend_id", "trend_name",
                            "call", "ref_then", "ref_now", "metrics_then", "metrics_now", "held", "verdict",
                            "reidentified_as"}
        assert row["schema"] == "pb4-call/1" and row["checked_in_run"] == run.path.name
        assert row["call_run"] == f"{run.path.name}:rebuilt:2026-10-29"
        assert (row["category"], row["market"]) == ("beauty", "US")
        assert (row["ref_then"], row["ref_now"]) == ("2026-10-27", "2026-11-02")
        assert row["call"] == then["bucket"] == original[row["trend_id"]]["call"]
        assert row["held"] is original[row["trend_id"]]["held"]
        assert row["verdict"] == ("held" if row["held"] else "missed") and row["reidentified_as"] is None
        assert row["metrics_then"] == {"new_recent": then["growth"]["new_recent"], "creators": then["growth"]["creators"],
                                       "last_seen_days": then["growth"]["last_seen_days"],
                                       "velocity_index": then["relative"]["velocity_index"]}
        assert row["metrics_now"]["new_creators_since"] == original[row["trend_id"]]["new_creators_since"]
        assert row["metrics_now"]["bucket_now"] in research_growth.BUCKETS

    # a second digest of the same calls adds none
    assert _read(research_digest.diff(run, RECONSTRUCTED, beauty.cfg()))["plugin"]["calls_added"] == 0
    assert len(_lines(calls_file)) == 14
    assert research_digest.add_calls(tmp_path / "ws", rows) == 0

    # these calls are a rebuild's (no run made them): left out of the hit rate unless asked for
    ws = tmp_path / "ws"
    assert research_digest.calls_summary(ws) == {"calls": {}, "damaged": []}
    summary = research_digest.calls_summary(ws, include_rebuilt=True)
    assert summary == {"calls": {"act_now": {"held": 10, "missed": 2, "unknown": 0, "checked": 12, "hit_rate": 0.83},
                                 "past_peak": {"held": 2, "missed": 0, "unknown": 0, "checked": 2, "hit_rate": 1.0}},
                       "damaged": []}
    assert research_digest.calls_summary(ws, category="nails", include_rebuilt=True)["calls"] == {}
    assert main(["research", "calls", "--workspace", str(ws), "--category", "Beauty", "--include-rebuilt",
                 "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed.pop("message").startswith("Act now: held 10, missed 2, unknown 0, hit rate 83%")
    assert printed == {"status": "done", **summary}
    assert main(["research", "calls", "--workspace", str(ws), "--include-rebuilt"]) == 0
    assert "Act now: held 10, missed 2, unknown 0, hit rate 83%" in capsys.readouterr().out

    # a damaged line is named, never skipped quietly, and nothing is added while it is there
    with open(calls_file, "a", encoding="utf-8") as fh:
        fh.write('{"schema": "pb4-call/1", "call_run": "cut off\n')
    assert research_digest.calls_summary(ws, include_rebuilt=True)["damaged"] == [15]
    assert main(["research", "calls", "--workspace", str(ws)]) == 0
    assert "Lines 15 of library/trend_calls.jsonl are damaged" in capsys.readouterr().out
    with pytest.raises(research_digest.DamagedCalls, match="damaged lines .*: 15"):
        research_digest.add_calls(ws, [{**rows[0], "call_run": "another"}])
    versions = sorted((run.path / "02_research").glob("digest_v*"))
    assert main(["research", "digest", "--run", str(run.path), "--prev", str(RECONSTRUCTED), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and ": 15." in payload["message"]
    assert sorted((run.path / "02_research").glob("digest_v*")) == versions        # nothing written
    assert len(calls_file.read_text(encoding="utf-8").splitlines()) == 15


def test_a_known_verdict_supersedes_an_unknown_one(tmp_path):
    row = {"schema": "pb4-call/1", "call_run": "2026-10-29_nails", "checked_in_run": "2026-11-04_nails",
           "category": "nails", "market": "US", "trend_id": "d", "call": "act_now", "held": None, "verdict": "unknown"}
    assert research_digest.add_calls(tmp_path, [row]) == 1
    assert research_digest.add_calls(tmp_path, [row]) == 0                           # unknown again: nothing
    assert research_digest.calls_summary(tmp_path)["calls"]["act_now"]["unknown"] == 1
    known = {**row, "held": True, "verdict": "held", "checked_in_run": "2026-11-05_nails"}
    assert research_digest.add_calls(tmp_path, [known]) == 1                         # fetched later: it counts
    assert research_digest.calls_summary(tmp_path)["calls"] == {
        "act_now": {"held": 1, "missed": 0, "unknown": 0, "checked": 1, "hit_rate": 1.0}}
    assert research_digest.add_calls(tmp_path, [row, {**known, "verdict": "missed", "held": False}]) == 0
    assert len(_lines(tmp_path / "library" / "trend_calls.jsonl")) == 2


# --- a weekly run: two small "nails" runs ------------------------------------------------------

PREV_PARAMS = {"as_of": "2026-10-29", "ref": "2026-10-27", "lag": 2, "window": 14, "baseline": 28, "rule": "v3"}


def _trend(name: str, bucket: str, creators: int = 9, kind: str = "topic_trend") -> dict:
    """A previous snapshot's row."""
    return {"name": name, "kind": kind, "group": "nails", "bucket": bucket, "confidence": "medium",
            "growth": {"creators": creators, "new_recent": 4, "last_seen_days": 1, "median_views": 9000,
                       "views_total": 90000, "top_creator_share": 0.2},
            "relative": {"velocity_index": 1.5, "percentile": 0.9, "band": "top 10%"}}


def _videos(run: RunFolder, trend_id: str, creators_and_days: list[tuple[str, str]], page_no: int = 1) -> None:
    folder = run.path / "02_research" / "videos"
    folder.mkdir(parents=True, exist_ok=True)
    vids = [{"asset_id": f"tiktok:{trend_id}{page_no}{i}", "creator": c, "published": f"{day}T10:00:00Z",
             "views": 9000, "url": f"https://www.tiktok.com/@{c}/video/{i}"}
            for i, (c, day) in enumerate(creators_and_days)]
    (folder / f"{trend_id}_p{page_no:02d}.json").write_text(json.dumps({"data": vids, "page": page_no}),
                                                           encoding="utf-8")


def _weekly(tmp_path, prev_trends: dict, now_kept: list[dict], *, pool_ids: list[str] | None = None,
            rebuilt: bool = False) -> tuple[RunFolder, RunFolder]:
    """A previous nails run holding `prev_trends` in its snapshot, and this week's run after it, with
    `now_kept` as its map (each row an id and a name)."""
    ws = tmp_path / "ws"
    prev = RunFolder.create(ws, "nails", REBUILT_AS_OF, playbook=TREND_RESEARCH)
    research_config.write_from_intake(prev, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    snap = {"params": PREV_PARAMS, "trends": prev_trends}
    if pool_ids is not None:
        snap["pool_ids"] = pool_ids
    if rebuilt:
        snap["rebuilt"] = True
    (prev.path / "02_research" / "snapshot_v01.json").write_text(json.dumps(snap), encoding="utf-8")
    now = RunFolder.create(ws, "nails", AS_OF, playbook=TREND_RESEARCH)
    s = state.load(now)
    s.previous_run = prev.path.relative_to(ws).as_posix()
    state.save(now, s)
    research_config.write_from_previous(now)
    kept = [{"kind": "topic_trend", "group": "nails", "sub_category": "nails", "status": "confirmed", **row}
            for row in now_kept]
    (now.path / "02_research" / "category_map_v01.json").write_text(json.dumps(
        {"root": "nails", "kept": kept, "dropped": [], "pool_ids": [r["id"] for r in kept]}), encoding="utf-8")
    return prev, now


def _get_trend(run: RunFolder, trend_id: str, answer) -> None:
    trends.save_answer(run, "get_trend", {"trend_id": trend_id}, answer)


def test_call_check_covers_trend_that_left_the_map(tmp_path, capsys):
    prev_trends = {
        "a": _trend("Chrome nails", "act_now"),                          # still in the map
        "b": _trend("Velvet cat-eye nails", "act_now"),                  # left the map, alive, fetched again
        "c": _trend("Glazed donut nail art tutorials", "act_now"),       # came back as "c2"
        "d": _trend("Jelly pedicure colours", "act_now"),                # left the map, no dated videos, no answer
        "e": _trend("Halloween nail stickers", "past_peak"),             # left the map, momentum over
        "f": _trend("French tip manicures", "still_rising"),             # not a call
        "g": _trend("Pastel ombre nails", "too_late"),                   # half its words in "h2": not the same trend
    }
    _, run = _weekly(tmp_path, prev_trends, [{"id": "a", "name": "Chrome nails"},
                                            {"id": "c2", "name": "Glazed donut nail art designs"},
                                            {"id": "h2", "name": "Pastel ombre hair"}],
                     pool_ids=sorted(prev_trends))
    assert main(["research", "previous", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == ["00_raw/prev_category_map.json", "00_raw/prev_split.json"]
    _videos(run, "a", [("a1", "2026-10-20"), ("a2", "2026-10-30")])
    _videos(run, "c2", [("c1", "2026-10-20"), ("c3", "2026-10-31"), ("c4", "2026-11-01")])
    _videos(run, "h2", [("h1", "2026-10-25"), ("h3", "2026-10-31"), ("h4", "2026-11-01")])
    _videos(run, "b", [("b1", "2026-10-20")])                             # nobody new since 27 Oct: missed
    _videos(run, "e", [("e1", "2026-10-10")])                             # nobody new: the call held
    _get_trend(run, "b", {"id": "b", "kind": "topic_trend", "name": "Velvet cat-eye nails", "momentum": "cooling"})
    _get_trend(run, "d", {"error": "Trend not found"})
    _get_trend(run, "e", {"id": "e", "kind": "topic_trend", "name": "Halloween nail stickers", "momentum": "over"})
    _get_trend(run, "f", {"data": {"id": "f", "kind": "topic_trend", "name": "French tip manicures", "momentum": None}})
    research_growth.compute(run, AS_OF, research_map.settings(config.load(run)))

    # d's videos were never fetched: the digest stops and writes nothing, rather than freeze "unknown"
    assert main(["research", "digest", "--run", str(run.path), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stop" and "'Jelly pedicure colours' (d)" in payload["message"]
    assert "get_trend_videos" in payload["message"] and "continues from the same place" in payload["message"]
    assert not list((run.path / "02_research").glob("digest_v*"))
    assert not (tmp_path / "ws" / "library" / "trend_calls.jsonl").exists()

    # fetched: TrendsMesh has no dated video with a creator for d, so its verdict is unknown
    trends.save_answer(run, "get_trend_videos", {"trend_id": "d"}, {"data": [{"asset_id": "x", "views": 5}],
                                                                   "has_more": False})
    assert main(["research", "digest", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["prev"] == "00_raw/prev_snapshot.json"
    digest = _read(run.path / payload["json"])
    calls = {c["id"]: c for c in digest["calls"]}
    assert set(calls) == {"a", "b", "c", "d", "e"}                         # every call, none dropped
    assert (calls["a"]["held"], calls["a"]["new_creators_since"]) == (True, 1)
    assert calls["b"]["held"] is False and calls["b"]["plugin"] == {"verdict": "missed", "in_map": False,
                                                                     "reidentified_as": None}
    assert calls["c"]["held"] is True and calls["c"]["new_creators_since"] == 2      # c2's videos
    assert calls["c"]["plugin"]["reidentified_as"] == "c2"
    assert calls["d"]["held"] is None and calls["d"]["new_creators_since"] is None
    assert calls["d"]["plugin"]["verdict"] == "unknown"
    assert calls["e"]["held"] is True and calls["e"]["call"] == "past_peak"
    assert digest["hit_rate"] == {"act_now": [0.67, 3], "past_peak": [1.0, 1]}       # d is not counted
    assert digest["plugin"]["unknown_calls"] == {"act_now": 1, "past_peak": 0}
    # ended: left the map, answer missing (c, g), an error (d) or over (e); b and f are alive. c came back
    # as c2 (4 of 6 words, 0.67); g and h2 share 2 of 4 words (0.5), so g stays ended and h2 stays new
    assert digest["reidentified"] == [{"id": "c2", "name": "Glazed donut nail art designs",
                                       "was": "Glazed donut nail art tutorials", "bucket": "still_rising",
                                       "plugin": {"was_id": "c"}}]
    assert [e["id"] for e in digest["ended"]] == ["d", "e", "g"]
    assert digest["new"] == [{"id": "h2", "name": "Pastel ombre hair", "bucket": "still_rising"}]
    assert "1 unknown" in payload["message"] and "'Jelly pedicure colours' (d)" in payload["message"]
    assert main(["research", "digest", "--run", str(run.path)]) == 0                 # again: no call twice
    assert "Added 0 rows to library/trend_calls.jsonl" in capsys.readouterr().out

    rows = {r["trend_id"]: r for r in _lines(tmp_path / "ws" / "library" / "trend_calls.jsonl")}
    assert set(rows) == {"a", "b", "c", "d", "e"}
    assert rows["c"]["reidentified_as"] == "c2" and rows["c"]["metrics_now"]["bucket_now"] == "still_rising"
    assert rows["d"]["verdict"] == "unknown" and rows["d"]["held"] is None
    assert rows["d"]["metrics_now"] == {"new_creators_since": None, "bucket_now": None, "velocity_index": None}
    assert {r["call_run"] for r in rows.values()} == {"2026-10-29_nails"}


def test_new_uses_pool_ids_with_stored_snapshot(tmp_path):
    prev_trends = {"a": _trend("Chrome nails", "too_late"), "z": _trend("Aura nails", "past_peak", creators=0)}
    now_kept = [{"id": "a", "name": "Chrome nails"}, {"id": "x", "name": "Matte black tips"},
                {"id": "y", "name": "Gel x extensions"}, {"id": "z", "name": "Aura nails"}]
    # x was among last week's search results (not mapped), y never was: only y is new
    _, run = _weekly(tmp_path, prev_trends, now_kept, pool_ids=["a", "x", "z"])
    research_digest.load_previous(run)
    for tid in ("a", "x", "y", "z"):
        _videos(run, tid, [(f"{tid}1", "2026-10-25"), (f"{tid}2", "2026-10-31"), (f"{tid}3", "2026-11-01")])
    cfg = research_map.settings(config.load(run))
    research_growth.compute(run, AS_OF, cfg)
    digest = _read(research_digest.diff(run, run.path / "00_raw" / "prev_snapshot.json", cfg))
    assert [n["id"] for n in digest["new"]] == ["y"]
    assert "z" in {u["id"] for u in digest["up"]}                         # had no creators then: in the pool, so up
    assert digest["plugin"]["prev_rebuilt"] is False and digest["plugin"]["ended_checked"] is True

    # the same snapshot marked rebuilt (V24): new by the old rule (no creators then), ended left out
    snap = _read(run.path / "00_raw" / "prev_snapshot.json")
    rebuilt = tmp_path / "rebuilt.json"
    rebuilt.write_text(json.dumps({**snap, "rebuilt": True}), encoding="utf-8")
    digest = _read(research_digest.diff(run, rebuilt, cfg))
    assert [n["id"] for n in digest["new"]] == ["z"] and digest["ended"] == []
    assert digest["plugin"]["prev_rebuilt"] is True


def test_fetch_plan_reuses_not_updated_and_refetches_act_now(tmp_path, capsys):
    prev_trends = {"a": _trend("Chrome nails", "act_now"), "b": _trend("Velvet nails", "still_rising"),
                   "g": _trend("Milky nails", "too_late"), "h": _trend("Matte tips", "too_late"),
                   "p": _trend("Halloween nail stickers", "past_peak"), "q": _trend("Jelly nails", "act_now")}
    prev, run = _weekly(tmp_path, prev_trends, [{"id": "a", "name": "Chrome nails"}, {"id": "g", "name": "Milky nails"},
                                                {"id": "h", "name": "Matte tips"}, {"id": "n", "name": "Gel x"}],
                        pool_ids=sorted(prev_trends))
    for tid in ("a", "b", "g", "h", "k"):
        _videos(prev, tid, [(f"{tid}1", "2026-10-20")])
    _videos(prev, "a", [("a9", "2026-10-21")], page_no=2)
    hooks = run.path / "02_research" / "lists" / "list_rising_hook_trend_all_p01.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text(json.dumps({"data": [{"id": "k", "kind": "hook_trend", "name": "day _ of _"}]}), encoding="utf-8")
    research_growth.hook_fit(run, {"k": {c: 3 for c in brief_config.CRITERIA}}, {})   # the shortlist (issue #8)

    # before the previous run's files are copied, nothing can be reused
    assert research_digest.fetch_plan(run, {})["reuse"] == []
    research_digest.load_previous(run)
    # a: act now (fetched again, 2 pages); b: still rising, p: past its peak, q: act now, all three off
    # the map now; n: new. b, p and q need a get_trend answer, or the digest counts them as ended
    everything = ["a", "b", "g", "h", "k", "n", "p", "q"]
    plan = research_digest.fetch_plan(run, {})
    assert plan["fetch"] == everything and plan["reuse"] == [] and plan["check"] == ["b", "p", "q"]
    assert "no list of updated trends is saved" in plan["note"]

    # a list that may stop short of 27 Oct (more pages, last card newer) proves nothing is unchanged
    trends.save_answer(run, "list_trends", {"sort": "updated"}, {"data": [
        {"id": "h", "kind": "topic_trend", "name": "Matte tips", "updated_at": "2026-11-01T08:00:00Z"}],
        "page": 1, "has_more": True})
    plan = research_digest.fetch_plan(run, {})
    assert plan["fetch"] == everything and "does not reach back to 2026-10-27" in plan["note"]

    # a hook list reaching back by date (its last card is from before 27 Oct) covers the hooks only
    trends.save_answer(run, "list_trends", {"sort": "updated", "trend_type": "hook_trend"}, {"data": [
        {"id": "k9", "kind": "hook_trend", "name": "pov _", "updated_at": "2026-10-01T08:00:00Z"}], "has_more": True})
    plan = research_digest.fetch_plan(run, {})
    assert plan["reuse"] == ["k"] and "only for hook_trend" in plan["note"]

    # the last page of every type says nothing follows: g (not updated) is copied too, h (updated) is not
    trends.save_answer(run, "list_trends", {"sort": "updated", "page": 2}, {"data": [
        {"id": "zz", "kind": "topic_trend", "name": "Other", "updated_at": "2026-11-02T08:00:00Z"}],
        "page": 2, "has_more": False})
    assert research_digest.updated_lists(run, date(2026, 10, 27))[1] == {"all", "hook_trend"}
    plan = research_digest.fetch_plan(run, {})
    assert plan["fetch"] == ["a", "b", "h", "n", "p", "q"] and plan["reuse"] == ["g", "k"] and plan["note"] is None
    assert plan["calls_estimate"] == 7 and plan["since"] == "2026-10-27"
    assert main(["research", "fetch-plan", "--run", str(run.path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["fetch"] == plan["fetch"]
    assert main(["research", "fetch-plan", "--run", str(run.path)]) == 0
    out = capsys.readouterr().out
    assert "copy the 2 not updated since 2026-10-27 from 2026-10-29_nails" in out
    assert "(TrendsMesh get_trend), or the digest counts them as ended: b, p, q" in out

    copied = research_digest.reuse(run)
    assert sorted(p.name for p in copied) == ["g_p01.json", "k_p01.json"]
    assert trends.load_videos(run, "g") == trends.load_videos(prev, "g")
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "copied from 2026-10-29_nails: not updated since 2026-10-27 (TR8)" in manifest
    assert main(["research", "reuse", "--run", str(run.path), "--json"]) == 0      # already here: nothing again
    payload = json.loads(capsys.readouterr().out)
    assert payload["copied"] == [] and "nothing" in payload["message"].lower()
    assert sorted(f.name for f in (run.path / "02_research" / "videos").iterdir()) == ["g_p01.json", "k_p01.json"]


def test_fetch_plan_check_leaves_out_hooks_kept_this_week(tmp_path):
    """A hook kept by last week's hooks path and by this week's is in this week's snapshot: it needs no
    get_trend answer. One the hooks path no longer keeps does."""
    prev_trends = {"a": _trend("Chrome nails", "act_now"), "k": _trend("day _ of _", "still_rising", kind="hook_trend"),
                   "j": _trend("pov _", "too_late", kind="hook_trend")}
    _, run = _weekly(tmp_path, prev_trends, [{"id": "a", "name": "Chrome nails"}], pool_ids=sorted(prev_trends))
    hook = {"kind": "hook_trend", "status": "confirmed"}
    lists = run.path / "02_research" / "lists" / "list_rising_hook_trend_all_p01.json"
    lists.parent.mkdir(parents=True)
    lists.write_text(json.dumps({"data": [{"id": "k", "name": "day _ of _", **hook},
                                          {"id": "j", "name": "pov _", **hook}]}), encoding="utf-8")
    (run.path / "02_research" / "hooks_in_category_v01.json").write_text(json.dumps(
        {"terms": ["nail"], "kept": [{"id": "k", "name": "day _ of _", **hook}],
         "not_in_category": [{"id": "j", "name": "pov _", **hook}]}), encoding="utf-8")
    research_digest.load_previous(run)
    plan = research_digest.fetch_plan(run, {})
    assert plan["check"] == ["j"] and {"a", "j", "k"} <= set(plan["fetch"])


def test_digest_stops_on_a_file_that_is_not_a_snapshot(tmp_path, capsys):
    _, run = _weekly(tmp_path, {"a": _trend("Chrome nails", "act_now")}, [{"id": "a", "name": "Chrome nails"}])
    (run.path / "02_research" / "snapshot_v01.json").write_text(json.dumps(
        {"params": PREV_PARAMS, "trends": {}, "pool_ids": []}), encoding="utf-8")
    bad = run.path / "03_wip" / "not_a_snapshot.json"
    bad.write_text(json.dumps({"trends": []}), encoding="utf-8")
    assert main(["research", "digest", "--run", str(run.path), "--prev", "03_wip/not_a_snapshot.json", "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "not a growth snapshot" in out["message"]
    assert "tm research rebuild-previous" in out["message"] and "same place" in out["message"]
    assert run.latest("02_research", "digest", "json") is None


def test_previous_copies_snapshot_map_and_config_into_raw(tmp_path, capsys):
    prev, run = _weekly(tmp_path, {"a": _trend("Chrome nails", "act_now")}, [{"id": "a", "name": "Chrome nails"}],
                        pool_ids=["a"])
    newer = {"params": {**PREV_PARAMS, "as_of": "2026-10-30"}, "trends": {}, "pool_ids": []}
    (prev.path / "02_research" / "snapshot_v02.json").write_text(json.dumps(newer), encoding="utf-8")
    (prev.path / "02_research" / "snapshot_growth_2026-10-20_rebuilt_v01.json").write_text("{}", encoding="utf-8")
    (prev.path / "02_research" / "category_map_v01.json").write_text(json.dumps({"kept": [{"id": "a"}]}), encoding="utf-8")
    split = {"root": "nails", "queries": [{"query": "nails", "parent": None, "depth": 0, "source": "seed"},
                                          {"query": "nail art", "parent": "nails", "depth": 1, "source": "closest_names"}]}
    (prev.path / "03_wip" / "split_v01.json").write_text(json.dumps({**split, "queries": split["queries"][:1]}),
                                                        encoding="utf-8")
    (prev.path / "03_wip" / "split_v02.json").write_text(json.dumps(split), encoding="utf-8")
    folder = page.new_folder(prev, research_digest.PAGE)
    (folder / "index.html").write_text("<html></html>", encoding="utf-8")
    page.record_published(prev, research_digest.PAGE, "slug-1", "v1", "https://claude.ai/a/slug-1")

    got = research_digest.load_previous(run)
    raw = run.path / "00_raw"
    assert got["previous_run"] == "runs/04-trend-research/2026-10-29_nails"
    assert got["snapshot"] == "00_raw/prev_snapshot.json" and got["page"]["slug"] == "slug-1"
    assert got["copied"] == ["00_raw/prev_snapshot.json", "00_raw/prev_category_map.json", "00_raw/prev_split.json",
                             "00_raw/prev_config.yaml"]
    assert got["already"] == [] and got["missing"] == []
    assert not list(raw.glob(".*.tmp"))
    assert _read(raw / "prev_snapshot.json") == newer                      # the latest snapshot, never a rebuilt one
    assert _read(raw / "prev_category_map.json") == {"kept": [{"id": "a"}]}
    assert _read(raw / "prev_split.json") == split                         # the latest split, for B1's queries
    assert (raw / "prev_config.yaml").read_text(encoding="utf-8") == (prev.path / "config.yaml").read_text(encoding="utf-8")
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert all(f"00_raw/{name}" in manifest
               for name in ("prev_snapshot.json", "prev_category_map.json", "prev_split.json", "prev_config.yaml"))

    # 00_raw is never changed: a second call finds the files and says so, even when the previous run moved on
    (prev.path / "02_research" / "snapshot_v03.json").write_text(json.dumps({**newer, "trends": {"q": {}}}), encoding="utf-8")
    (prev.path / "03_wip" / "split_v03.json").write_text(json.dumps({**split, "queries": []}), encoding="utf-8")
    assert main(["research", "previous", "--run", str(run.path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done" and payload["copied"] == [] and payload["missing"] == []
    assert payload["already"] == ["00_raw/prev_snapshot.json", "00_raw/prev_category_map.json", "00_raw/prev_split.json",
                                  "00_raw/prev_config.yaml"]
    assert "were in 00_raw already and stay as they are" in payload["message"]
    assert "Nothing was copied this time." in payload["message"]
    assert _read(raw / "prev_snapshot.json") == newer and _read(raw / "prev_split.json") == split

    # a first run follows nothing
    first = RunFolder.create(tmp_path / "ws", "first", AS_OF, playbook=TREND_RESEARCH)
    research_config.write_from_intake(first, {"category": {"phrase": "nails"}, "market": "US", "language": "en"})
    assert research_digest.load_previous(first) == {"previous_run": None}
    assert main(["research", "previous", "--run", str(first.path)]) == 0
    assert "follows no earlier run" in capsys.readouterr().out
    assert main(["research", "digest", "--run", str(first.path), "--json"]) == 2     # nothing to compare with
    assert "continues from the same place" in json.loads(capsys.readouterr().out)["message"]

    # the run it follows was moved away: a plain stop, not a traceback
    s = state.load(first)
    s.previous_run = "runs/04-trend-research/2026-10-22_gone"
    state.save(first, s)
    for action in ("previous", "fetch-plan", "reuse"):
        assert main(["research", action, "--run", str(first.path), "--json"]) == 2
        message = json.loads(capsys.readouterr().out)["message"]
        assert "2026-10-22_gone" in message and "not there" in message
        assert "continues from the same place" in message
    assert not list((first.path / "00_raw").iterdir())


def test_filtered_or_partial_updated_list_never_covers(tmp_path):
    prev, run = _weekly(tmp_path, {"g": _trend("Milky nails", "too_late")}, [{"id": "g", "name": "Milky nails"}],
                        pool_ids=["g"])
    _videos(prev, "g", [("g1", "2026-10-20")])
    research_digest.load_previous(run)
    other = [{"id": "zz", "kind": "topic_trend", "name": "Other", "updated_at": "2026-11-02T08:00:00Z"}]

    def covered() -> set[str]:
        return research_digest.updated_lists(run, date(2026, 10, 27))[1]

    # narrowed by a text or to another feed: it does not list every updated trend
    trends.save_answer(run, "list_trends", {"sort": "updated", "q": "nails"}, {"data": other, "has_more": False})
    trends.save_answer(run, "list_trends", {"sort": "updated", "feed": "us"}, {"data": other, "has_more": False})
    assert covered() == set() and research_digest.fetch_plan(run, {})["reuse"] == []
    # its last page alone: page 1 may hold g
    trends.save_answer(run, "list_trends", {"sort": "updated", "page": 2}, {"data": other, "page": 2, "has_more": False})
    assert covered() == set() and research_digest.fetch_plan(run, {})["reuse"] == []
    # page 1 of the default feed, named or not: the list reaches back, g was not updated
    trends.save_answer(run, "list_trends", {"sort": "updated", "feed": "global"},
                       {"data": other, "page": 1, "has_more": True})
    assert covered() == {"all"} and research_digest.fetch_plan(run, {})["reuse"] == ["g"]


def test_calls_library_without_a_last_newline_takes_new_rows(tmp_path):
    row = {"schema": "pb4-call/1", "call_run": "2026-10-29_nails", "trend_id": "a", "call": "act_now",
           "held": True, "verdict": "held"}
    path = tmp_path / "library" / "trend_calls.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps(row), encoding="utf-8")                      # saved by hand, no last newline
    assert research_digest.add_calls(tmp_path, [{**row, "trend_id": "b"}]) == 1
    assert [r["trend_id"] for r in _lines(path)] == ["a", "b"]
    assert research_digest.calls_summary(tmp_path)["damaged"] == []
    assert path.read_bytes().endswith(b"}\n") and b"\n\n" not in path.read_bytes()


def test_previous_copies_without_hard_links(tmp_path, monkeypatch):
    prev, run = _weekly(tmp_path, {"a": _trend("Chrome nails", "act_now")}, [{"id": "a", "name": "Chrome nails"}],
                        pool_ids=["a"])

    def no_links(src, dst):
        raise OSError(errno.EPERM, "Operation not permitted", str(dst))      # FAT, some network shares

    monkeypatch.setattr(os, "link", no_links)
    got = research_digest.load_previous(run)
    raw = run.path / "00_raw"
    assert got["copied"] == ["00_raw/prev_snapshot.json", "00_raw/prev_config.yaml"]
    assert _read(raw / "prev_snapshot.json") == _read(prev.path / "02_research" / "snapshot_v01.json")
    assert not list(raw.glob(".*.tmp"))
    again = research_digest.load_previous(run)                              # never over a file already there
    assert again["copied"] == [] and again["already"] == ["00_raw/prev_snapshot.json", "00_raw/prev_config.yaml"]



def test_cover_is_reached_by_the_oldest_card_of_the_last_page(tmp_path):
    """A list sorted updated is paged until a page's oldest card is on or before the previous run's
    reference date; the cards need not be in order, and a page with no updated_at proves nothing."""
    prev, run = _weekly(tmp_path, {"g": _trend("Milky nails", "too_late")}, [{"id": "g", "name": "Milky nails"}],
                        pool_ids=["g"])
    since = date(2026, 10, 27)
    trends.save_answer(run, "list_trends", {"sort": "updated", "limit": 50}, {"data": [
        {"id": "x", "kind": "topic_trend", "name": "X"}, {"id": "y", "kind": "topic_trend", "name": "Y"}],
        "page": 1, "has_more": True})
    assert research_digest.updated_lists(run, since)[1] == set()            # no date on page 1: page on
    trends.save_answer(run, "list_trends", {"sort": "updated", "limit": 50, "page": 2}, {"data": [
        {"id": "h", "kind": "topic_trend", "name": "Matte tips", "updated_at": "2026-10-26T23:00:00Z"},
        {"id": "zz", "kind": "topic_trend", "name": "Other", "updated_at": "2026-11-02T08:00:00Z"}],
        "page": 2, "has_more": True})
    ids, covered, listed = research_digest.updated_lists(run, since)
    assert covered == {"all"} and listed and ids == {"x", "y", "zz"}       # h was updated before since

def test_cover_needs_a_plain_list_with_one_limit(tmp_path):
    prev, run = _weekly(tmp_path, {"g": _trend("Milky nails", "too_late")}, [{"id": "g", "name": "Milky nails"}],
                        pool_ids=["g"])
    _videos(prev, "g", [("g1", "2026-10-20")])
    research_digest.load_previous(run)
    other = [{"id": "zz", "kind": "topic_trend", "name": "Other", "updated_at": "2026-11-02T08:00:00Z"}]

    def covered() -> set[str]:
        return research_digest.updated_lists(run, date(2026, 10, 27))[1]

    # only sort, trend_type, page and limit may be given: anything else may hide updated trends
    for extra in ({"include_general": False}, {"as_of": "2026-11-01"}, {"min_match": 40}):
        trends.save_answer(run, "list_trends", {"sort": "updated", "trend_type": "hook_trend", **extra},
                           {"data": other, "has_more": False})
    assert covered() == set()
    # pages asked with different limits do not join up
    trends.save_answer(run, "list_trends", {"sort": "updated", "limit": 50}, {"data": other, "page": 1, "has_more": True})
    trends.save_answer(run, "list_trends", {"sort": "updated", "limit": 20, "page": 2},
                       {"data": other, "page": 2, "has_more": False})
    assert covered() == set() and research_digest.fetch_plan(run, {})["reuse"] == []
    # one limit on every page of a type: that list reaches back (the default feed is no narrowing)
    for page_no, more in ((1, True), (2, False)):
        trends.save_answer(run, "list_trends", {"sort": "updated", "trend_type": "topic_trend", "limit": 50,
                                                "page": page_no, "feed": "global"},
                           {"data": other, "page": page_no, "has_more": more})
    assert covered() == {"topic_trend"}
