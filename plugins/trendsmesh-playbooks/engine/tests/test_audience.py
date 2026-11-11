"""tm audience: the audience from a hypothesis first (the product) and the platform's data second (CB1).

The rows are made up in the shape of the handoff's LD dry run (`01_base/account_context.md`): its
two tables of checkouts, by age and gender and by placement, over the same campaigns (one total of
checkouts and of spend), thin enough that no segment reaches CB1's 10 results, written as Meta's `ads_get_ad_entities` gives them (money as `{value, unit}`, results as
`results.values[0].value`). Meta answers are saved as the collector saves them (`mcp_saves.save`).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from tm import audience, meta_rows, mcp_saves, state, stepchecks
from tm.audience import Pick, Segment
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

BEFORE = "2000-01-01T00:00:00+00:00"   # an answer saved before the hypothesis was recorded
AFTER = "2099-01-01T00:00:00+00:00"    # an answer saved after it

# (age, gender, spend PLN, checkouts), made up in the shape of account_context.md's age and gender table:
# 31 checkouts, 969.00 PLN
LD_AGE_GENDER = [
    ("18-24", "male", "41.30", 2), ("18-24", "female", "11.95", 0),
    ("25-34", "male", "98.40", 2), ("25-34", "female", "24.60", 1),
    ("35-44", "male", "151.75", 3), ("35-44", "female", "29.10", 2),
    ("45-54", "male", "87.20", 2), ("45-54", "female", "63.45", 1),
    ("55-64", "male", "112.80", 1), ("55-64", "female", "70.35", 2),
    ("65+", "male", "158.40", 6), ("65+", "female", "119.70", 9),
]
# (publisher_platform, platform_position, spend PLN, checkouts), made up in the shape of its placements table:
# the same 31 checkouts and 969.00 PLN
LD_PLACEMENTS = [
    ("facebook", "feed", "355.10", 8), ("audience_network", "an_classic", "97.15", 7),
    ("instagram", "instagram_stories", "66.80", 5), ("facebook", "facebook_reels", "131.45", 4),
    ("audience_network", "rewarded_video", "54.90", 3), ("instagram", "instagram_reels", "102.35", 2),
    ("facebook", "instream_video", "18.70", 1), ("instagram", "feed", "142.55", 1),
]


def _results(n) -> dict:
    return {"indicator": "actions:offsite_conversion.fb_pixel_initiate_checkout",
            "values": [{"attribution_windows": ["default"], "value": str(n)}]}


def _age_gender_rows(table=LD_AGE_GENDER) -> list[dict]:
    return [{"age": a, "gender": g, "spend": {"value": s, "unit": "PLN"}, "results": _results(n)}
            for a, g, s, n in table]


def _placement_rows(table=LD_PLACEMENTS) -> list[dict]:
    return [{"publisher_platform": p, "platform_position": pos, "spend": {"value": s, "unit": "PLN"},
             "results": _results(n)} for p, pos, s, n in table]


AGE_GENDER_INPUT = {"level": "campaign", "date_preset": "maximum", "breakdowns": ["age", "gender"],
                    "fields": ["spend", "results", "cost_per_result"]}
PLACEMENT_INPUT = {"level": "campaign", "date_preset": "maximum",
                   "breakdowns": ["publisher_platform", "platform_position"], "fields": ["spend", "results"]}


@pytest.fixture
def run(tmp_path, monkeypatch) -> RunFolder:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(workspace))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return RunFolder.create(workspace, "ld", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


def _write_hypothesis(run: RunFolder, n: int = 1) -> Path:
    path = run.path / "02_research" / "audience" / f"hypothesis_v{n:02d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Audience hypothesis (from the product, before data)\n\nAdults 30–55 who write down their "
                    "dreams and read about sleep and memory.\n", encoding="utf-8")
    return path


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    out = capsys.readouterr().out
    return code, json.loads(out)


def _hypothesis(capsys, run: RunFolder, n: int = 1) -> tuple[int, dict]:
    path = _write_hypothesis(run, n)
    return _cli(capsys, "audience", "hypothesis", "--run", str(run.path), "--file", str(path))


def _save(run: RunFolder, tool_input: dict, rows: list[dict], at: str) -> Path:
    return mcp_saves.save(run, "ads_get_ad_entities", tool_input, {"data": rows}, at=at)


def _audience_files(run: RunFolder) -> list[str]:
    folder = run.path / "02_research" / "audience"
    return sorted(p.name for p in folder.glob("audience_*")) if folder.is_dir() else []


def test_results_is_public_and_the_old_name_stays():
    assert meta_rows.results(_results(7)) == 7.0
    assert meta_rows.results("3") == 3.0
    assert meta_rows._results is meta_rows.results


def test_ld_thin_data_picks_65_plus_directional():
    rows = _age_gender_rows()
    assert len(rows) == 12
    segs = audience.segments(rows)
    assert len(segs) == 12
    assert sum(s.results for s in segs) == 31
    men_65 = next(s for s in segs if s.age == "65+" and s.gender == "male")
    assert men_65 == Segment(name="65+ male", age="65+", gender="male", results=6.0, spend=158.40,
                             cost_per_result=pytest.approx(26.40, abs=0.005))
    women_18 = next(s for s in segs if s.age == "18-24" and s.gender == "female")
    assert women_18.results == 0 and women_18.cost_per_result is None
    assert max(s.results for s in segs) < 10   # no segment reaches CB1's 10 results

    p = audience.pick(segs, 10)
    assert p.segment == "65+"
    assert p.rule == "directional_fallback"
    assert p.directional is True
    assert p.results == 15
    assert p.cost_per_result == pytest.approx((158.40 + 119.70) / 15)


def test_lowest_cost_at_ten_results():
    rows = _age_gender_rows([
        ("35-44", "male", "300.00", 12),   # 25.00 a result
        ("45-54", "male", "120.00", 6),    # this segment comes in two campaign rows: 10 results, 20.00
        ("45-54", "male", "80.00", 4),
        ("65+", "female", "45.00", 9),     # 5.00, the cheapest, but below 10 results
        ("25-34", "female", "0", 0),
    ])
    rows[2]["amount_spent"] = rows[2].pop("spend")   # Meta's own field name counts too
    segs = audience.segments(rows)
    assert len(segs) == 4
    summed = next(s for s in segs if s.name == "45-54 male")
    assert (summed.results, summed.spend, summed.cost_per_result) == (10.0, 200.0, 20.0)

    p = audience.pick(segs, 10)
    assert p == Pick(segment="45-54 male", rule="lowest_cost", directional=False, results=10.0,
                     cost_per_result=20.0)
    # the same rows with the threshold one higher: only 35-44 male is left
    assert audience.pick(segs, 11).segment == "35-44 male"
    # with no segment at the threshold, the fallback is directional
    assert audience.pick(segs, 13).rule == "directional_fallback"


def test_cluster_ties_go_to_the_lower_cost():
    segs = audience.segments(_age_gender_rows([
        ("25-34", "male", "60.00", 3), ("25-34", "female", "30.00", 1),   # 4 results, 22.50
        ("55-64", "male", "40.00", 2), ("55-64", "female", "40.00", 2),   # 4 results, 20.00
    ]))
    p = audience.pick(segs, 10)
    assert (p.segment, p.results, p.cost_per_result) == ("55-64", 4.0, 20.0)
    assert audience.pick([], 10).rule == "hypothesis_only"


def test_ld_placements_give_both_formats(run, capsys):
    code, out = _hypothesis(capsys, run)
    assert code == 0, out
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    placements = _save(run, PLACEMENT_INPUT, _placement_rows(), AFTER)
    assert audience.picked_gap(run) is not None   # nothing picked yet

    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(placements))
    assert code == 0, out
    assert out["status"] == "done"
    assert out["file"] == "02_research/audience/audience_v01.json"
    doc = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))
    assert list(doc) == ["schema", "source", "hypothesis", "data_files", "segments", "pick", "formats",
                         "min_results"]
    assert doc["schema"] == "audience/1" and doc["source"] == "meta_ads"
    assert doc["formats"] == ["9x16", "4x5"]   # the feeds: 8 + 1 of 31 checkouts, 29 % >= 25 %
    assert doc["min_results"] == 10
    assert doc["data_files"] == ["01_base/meta/ads_get_ad_entities_v01.json",
                                 "01_base/meta/ads_get_ad_entities_v02.json"]
    assert doc["hypothesis"]["file"] == "02_research/audience/hypothesis_v01.md"
    assert doc["pick"] == {"segment": "65+", "rule": "directional_fallback", "directional": True,
                           "results": 15.0, "cost_per_result": pytest.approx(18.54, abs=0.005)}
    assert len(doc["segments"]) == 12

    s = state.load(run)
    assert s.audience["file"] == out["file"]
    assert s.audience["formats"] == ["9x16", "4x5"]
    assert s.audience["pick"]["directional"] is True
    assert s.audience["hypothesis"] == doc["hypothesis"]
    assert audience.picked_gap(run) is None
    assert stepchecks.run("audience_picked", run) is None   # B1's step check resolves to picked_gap
    assert "02_research/audience/audience_v01.json" in (run.path / "manifest.md").read_text(encoding="utf-8")

    # with the feed placements below 25 % only 9:16 is needed
    thin_feed = [r if r[1] != "feed" else (r[0], r[1], r[2], 1) for r in LD_PLACEMENTS]   # 1 + 1 of 24
    placements = _save(run, PLACEMENT_INPUT, _placement_rows(thin_feed), AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(placements))
    assert code == 0, out
    assert out["file"] == "02_research/audience/audience_v02.json"
    assert out["formats"] == ["9x16"]
    assert state.load(run).audience["formats"] == ["9x16"]

    # a file the agent writes over the pick is not the pick
    (run.path / "02_research" / "audience" / "audience_v03.json").write_text("{}", encoding="utf-8")
    assert "tm audience pick" in audience.picked_gap(run)


def test_breakdown_without_placements_keeps_both_formats(run, capsys):
    assert _hypothesis(capsys, run)[0] == 0
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown))
    assert code == 0, out
    assert out["formats"] == ["9x16", "4x5"]
    assert out["pick"]["rule"] == "directional_fallback"


def test_hypothesis_after_breakdown_refused(run, capsys):
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), BEFORE)
    assert audience.order_gap(run) is not None

    # recording a hypothesis after the data is refused, and nothing is recorded
    code, out = _hypothesis(capsys, run)
    assert code == 2, out
    assert out["status"] == "stop"
    assert "age × gender breakdown 01_base/meta/ads_get_ad_entities_v01.json" in out["message"]
    assert "B1" in out["message"] and "Tell the user" in out["message"]
    assert "continues from the same place" not in out["message"]   # M-1: B1 can never pass here
    assert "can never pass" in out["message"] and "tm run new --playbook" in out["message"]
    assert state.load(run).audience is None

    # the pick is refused too, and writes nothing
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown))
    assert code == 2, out
    assert out["status"] == "stop"
    assert "age × gender breakdown 01_base/meta/ads_get_ad_entities_v01.json" in out["message"]
    assert _audience_files(run) == []
    assert state.load(run).audience is None
    assert "before any hypothesis was recorded" in audience.picked_gap(run)


def test_data_saved_before_a_recorded_hypothesis_stops_the_pick(run, capsys):
    assert _hypothesis(capsys, run)[0] == 0
    _save(run, {"level": "campaign", "breakdowns": "age,gender"}, [], BEFORE)   # read before, saved late
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    before = state.load(run).audience
    gap = audience.order_gap(run)
    assert "01_base/meta/ads_get_ad_entities_v01.json" in gap

    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown))
    assert code == 2, out
    assert _audience_files(run) == []
    assert state.load(run).audience == before
    assert audience.picked_gap(run) == gap


@pytest.mark.parametrize("tool_input, counts", [
    ({"level": "campaign", "breakdowns": ["age", "gender"]}, True),
    ({"breakdown": "age"}, True),
    ({"breakdowns": "age,gender"}, True),
    ({"params": {"breakdowns": ["gender"]}}, True),
    ({"breakdowns": {"0": "age", "1": "gender"}}, True),   # a list as the Meta MCP sometimes writes it
    ({"action_breakdowns": ["action_type"]}, False),
    ({"params": {"breakdowns": ["publisher_platform", "platform_position"]}}, False),   # R6's formats
    ({"breakdowns": "language"}, False),   # "age" only as a whole word
    ({"fields": ["name", "targeting"]}, False),
    ({"fields": "name,targeting{age_min,age_max}"}, False),
    ({"targeting": {"age_min": 18}}, False),
    ({"level": "ad", "breakdowns": []}, False),
    ({"level": "ad", "breakdowns": "", "fields": ["spend", "results"]}, False),
    ({"level": "ad", "ad_ids": ["1"]}, False),
])
def test_audience_data_is_an_age_or_gender_breakdown(tool_input, counts):
    assert audience.is_audience_data(tool_input) is counts


def test_reads_that_are_not_audience_data_never_block(run, capsys):
    mcp_saves.save(run, "ads_get_ad_accounts", {}, {"data": []}, at=BEFORE)
    _save(run, {"level": "ad", "fields": ["spend", "results"]}, [], BEFORE)
    _save(run, PLACEMENT_INPUT, _placement_rows(), BEFORE)
    assert _hypothesis(capsys, run)[0] == 0
    assert audience.order_gap(run) is None


def _mcp(rows: list[dict]) -> dict:
    """The Meta MCP's own answer: the rows as a JSON text next to its id (issue #28)."""
    return {"ad_entities": json.dumps(rows), "client_conversation_id": "conv-0001"}


def test_reads_are_taken_in_the_meta_mcp_shape(run, capsys):
    code, out = _hypothesis(capsys, run)
    assert code == 0, out
    breakdown = mcp_saves.save(run, "ads_get_ad_entities", AGE_GENDER_INPUT, _mcp(_age_gender_rows()), at=AFTER)
    placements = mcp_saves.save(run, "ads_get_ad_entities", PLACEMENT_INPUT, _mcp(_placement_rows()), at=AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(placements))
    assert code == 0, out
    assert out["pick"]["segment"] == "65+" and out["formats"] == ["9x16", "4x5"]


def test_placements_with_no_readable_results_stop_instead_of_9x16(run, capsys):
    """Issue #20: a placement read whose results cannot be read is not "9:16 only"."""
    code, out = _hypothesis(capsys, run)
    assert code == 0, out
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    unread = [{**r, "results": {"indicator": "actions:x"}} for r in _placement_rows()]
    placements = _save(run, PLACEMENT_INPUT, unread, AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(placements))
    assert code == 2 and out["status"] == "stop", out
    assert "no results" in out["message"] and "nothing was written" in out["message"]
    assert _audience_files(run) == []


# The LD dry run's first Meta read (its manifest row 1, meta_adsets_targeting_maximum.json): A1 derives
# the market from the ad sets' targeting (`geo_locations`, PLAYBOOK "Inputs"), before B1's hypothesis.
LD_A1_INPUT = {"account_id": "act_12345678", "level": "adset",
               "fields": ["name", "campaign_name", "targeting", "amount_spent", "effective_status"],
               "date_preset": "maximum", "sort": "amount_spent_descending", "limit": 25}
LD_A1_ANSWER = {"ad_entities": json.dumps([{
    "name": "Ad set 1", "campaign_name": "[CA] Concept A", "amount_spent": {"value": "142.86", "unit": "PLN"},
    "effective_status": "ACTIVE",
    "targeting": {"age_min": 18, "age_max": 65, "age_range": {"0": 24, "1": 65},
                  "geo_locations": {"countries": {"0": "CA"}, "location_types": {"0": "home", "1": "recent"}}}}])}


def test_ld_a1_market_read_before_the_hypothesis_is_fine(run, capsys):
    a1 = mcp_saves.save(run, "ads_get_ad_entities", LD_A1_INPUT, LD_A1_ANSWER, at=BEFORE)
    assert a1.relative_to(run.path).as_posix() == "01_base/meta/ads_get_ad_entities_v01.json"
    assert audience.audience_reads(run) == []

    code, out = _hypothesis(capsys, run)
    assert code == 0, out
    assert audience.order_gap(run) is None
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    placements = _save(run, PLACEMENT_INPUT, _placement_rows(), AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(placements))
    assert code == 0, out
    assert audience.picked_gap(run) is None
    assert stepchecks.run("audience_picked", run) is None


def test_a_recorded_hypothesis_that_came_first_stays(run, capsys):
    assert _hypothesis(capsys, run)[0] == 0
    kept = state.load(run).audience["hypothesis"]
    _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    code, out = _hypothesis(capsys, run, 2)
    assert code == 2, out
    assert "stays" in out["message"] and "start" not in out["message"]
    assert state.load(run).audience["hypothesis"] == kept
    assert audience.order_gap(run) is None


def test_a_read_saved_in_the_same_second_came_after(run, capsys):
    from datetime import datetime, timedelta

    assert _hypothesis(capsys, run)[0] == 0
    at = datetime.fromisoformat(state.load(run).audience["hypothesis"]["at"])
    _save(run, AGE_GENDER_INPUT, [], at.isoformat(timespec="seconds"))
    assert audience.order_gap(run) is None
    _save(run, AGE_GENDER_INPUT, [], (at - timedelta(seconds=1)).isoformat(timespec="seconds"))
    assert "ads_get_ad_entities_v02.json" in audience.order_gap(run)


def test_no_data_is_hypothesis_only_directional(run, capsys):
    # no hypothesis yet: refused, nothing written
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--no-data")
    assert code == 2, out
    assert _audience_files(run) == []

    assert _hypothesis(capsys, run)[0] == 0
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--no-data")
    assert code == 0, out
    doc = json.loads((run.path / out["file"]).read_text(encoding="utf-8"))
    assert doc["pick"]["rule"] == "hypothesis_only"
    assert doc["pick"]["directional"] is True
    assert doc["formats"] == ["9x16", "4x5"]
    assert doc["data_files"] == [] and doc["segments"] == []
    assert doc["source"] is None
    assert state.load(run).audience["pick"]["rule"] == "hypothesis_only"
    assert audience.picked_gap(run) is None

    # a new hypothesis after the pick: the pick is made again
    assert _hypothesis(capsys, run, 2)[0] == 0
    assert "tm audience pick" in audience.picked_gap(run)


def test_bad_arguments_are_errors(run, capsys, tmp_path):
    outside = tmp_path / "hypothesis_v01.md"
    outside.write_text("x", encoding="utf-8")
    code, out = _cli(capsys, "audience", "hypothesis", "--run", str(run.path), "--file", str(outside))
    assert code == 1 and out["status"] == "error"
    wrong = run.path / "03_wip" / "hypothesis_v01.md"
    wrong.write_text("x", encoding="utf-8")
    code, out = _cli(capsys, "audience", "hypothesis", "--run", str(run.path), "--file", str(wrong))
    assert code == 1 and "02_research/audience/hypothesis_vNN.md" in out["message"]
    assert state.load(run).audience is None

    assert _hypothesis(capsys, run)[0] == 0
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--no-data",
                     "--placements", str(wrong))
    assert code == 1 and out["status"] == "error"
    assert main(["audience", "pick", "--run", str(run.path)]) == 1   # neither --breakdown nor --no-data
    capsys.readouterr()


def test_empty_hypothesis_and_wrong_data_files_stop(run, capsys):
    path = _write_hypothesis(run)
    path.write_text("  \n", encoding="utf-8")
    code, out = _cli(capsys, "audience", "hypothesis", "--run", str(run.path), "--file", str(path))
    assert code == 2 and out["status"] == "stop"

    assert _hypothesis(capsys, run)[0] == 0
    placements = _save(run, PLACEMENT_INPUT, _placement_rows(), AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(placements))
    assert code == 2 and "age" in out["message"]   # placement rows given as the age × gender breakdown
    breakdown = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(breakdown),
                     "--placements", str(breakdown))
    assert code == 2 and "placement" in out["message"]
    assert _audience_files(run) == []


def test_failed_age_gender_read_is_not_audience_data(run, capsys):
    mcp_saves.save(run, "ads_get_ad_entities", AGE_GENDER_INPUT, {"error": {"raw": "Rate limit"}}, at=BEFORE)
    mcp_saves.save(run, "ads_get_ad_entities", AGE_GENDER_INPUT, {"raw": "not json"}, at=BEFORE)
    assert audience.audience_reads(run) == []
    assert _hypothesis(capsys, run)[0] == 0                       # no breach: nothing was read
    assert audience.order_gap(run) is None
    mcp_saves.save(run, "ads_get_ad_entities", AGE_GENDER_INPUT, [{"age": "18-24"}], at=BEFORE)   # rows as a list
    assert len(audience.audience_reads(run)) == 1


def test_pick_takes_only_a_saved_read_of_the_run(run, tmp_path, capsys):
    assert _hypothesis(capsys, run)[0] == 0
    rows = {"data": _age_gender_rows()}
    by_hand = run.path / "03_wip" / "rows.json"
    by_hand.parent.mkdir(parents=True, exist_ok=True)
    by_hand.write_text(json.dumps(rows), encoding="utf-8")
    forged = run.path / "01_base" / "meta" / "made_by_hand.json"
    forged.parent.mkdir(parents=True)
    forged.write_text(json.dumps(rows), encoding="utf-8")        # in the folder, but no _input
    for bad in (by_hand, forged):
        code, out = _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(bad))
        assert code == 2 and out["status"] == "stop", out
        assert "not a saved age × gender read" in out["message"] and "--no-data" in out["message"]
    assert _audience_files(run) == []
    good = _save(run, AGE_GENDER_INPUT, _age_gender_rows(), AFTER)
    assert _cli(capsys, "audience", "pick", "--run", str(run.path), "--breakdown", str(good))[0] == 0


def test_unreadable_meta_file_is_named(run, capsys):
    broken = run.path / "01_base" / "meta" / "ads_get_ad_entities_v09.json"
    broken.parent.mkdir(parents=True)
    broken.write_text('{"_input": ', encoding="utf-8")
    assert "01_base/meta/ads_get_ad_entities_v09.json cannot be read" in audience.order_gap(run)
    code, out = _hypothesis(capsys, run)
    assert code == 2 and out["status"] == "stop"
    assert "01_base/meta/ads_get_ad_entities_v09.json cannot be read" in out["message"]
    assert state.load(run).audience is None
