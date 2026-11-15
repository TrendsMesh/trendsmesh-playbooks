"""Issue #100: Create an ad's talking person chosen on a page, from CA5's table, with today's Replicate prices."""

import json
from datetime import date, timedelta

from tm import create_plan, create_presenter, manifest

from test_create_plan import TODAY, _check, _new, _ready_for, plan

PRICES = "02_research/models/prices_{day}_v01.json"


def _prices(run, day=TODAY, models=None):
    rows = [{"model": "bytedance/seedance-2.0", "checked": day, "tiers": [
                {"criteria": "model variant=non_video_in, target resolution=720p", "price": "$0.18", "unit": "second"},
                {"criteria": "model variant=video_in, target resolution=720p", "price": "$0.22", "unit": "second"}]},
            {"model": "minimax/h3", "checked": day, "tiers": [
                {"criteria": "target resolution=768P", "price": "$0.08", "unit": "second"},
                {"criteria": "target resolution=2K", "price": "$0.13", "unit": "second"}]},
            {"model": "google/gemini-omni-1.2-flash", "checked": day, "tiers": [
                {"criteria": "target resolution=720p", "price": "$0.105", "unit": "second"}]},
            {"model": "kwaivgi/kling-avatar-v2", "checked": day, "tiers": [
                {"criteria": "mode=std", "price": "$0.056", "unit": "second"},
                {"criteria": "mode=pro", "price": "$0.11", "unit": "second"}]}]
    rows = [r for r in rows if models is None or r["model"] in models]
    rel = PRICES.format(day=day)
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rel


def test_the_rows_are_ca5s_table_in_the_plan_checks_words():
    assert list(create_presenter.ROWS) == list(create_plan.PRESENTERS)
    for situation, row in create_presenter.ROWS.items():
        assert create_plan.PRESENTERS[situation][0] in row["model"], situation
    assert {m for m in create_presenter.MODELS} == {r["model"] for r in create_presenter.ROWS.values()}


def test_the_plans_situation_comes_first_then_the_other_rows_each_priced_for_15_s(tmp_path):
    run = _new(tmp_path)
    _prices(run)
    rows = create_presenter.rows(run, plan())
    assert [r["situation"] for r in rows] == ["exact_wording", "described", "specific_person", "own_voice", "fallback"]
    first = rows[0]
    assert first["plan"] is True and not any(r["plan"] for r in rows[1:])
    assert first["model"] == "google/gemini-omni-1.2-flash" and first["needs"] == "exact_wording"
    assert first["price"] == {"usd": 1.575, "unit_price": 0.105, "unit": "second", "checked": TODAY,
                              "file": PRICES.format(day=TODAY), "old_days": None}
    by = {r["situation"]: r for r in rows}
    assert by["described"]["price"]["usd"] == 2.7              # the tier without a video input, at 720p
    assert by["own_voice"]["price"]["usd"] == by["specific_person"]["price"]["usd"] == 1.2
    assert by["fallback"]["price"]["usd"] == 0.84              # Kling's std tier; ElevenLabs' line comes on top


def test_a_row_with_no_price_read_says_so_and_an_old_price_says_how_old(tmp_path):
    run = _new(tmp_path)
    old = (date.today() - timedelta(days=9)).isoformat()          # today now, not at import: a run past midnight
    _prices(run, day=old, models={"minimax/h3"})
    rows = {r["situation"]: r for r in create_presenter.rows(run, plan())}
    assert rows["described"]["price"] is None
    assert rows["own_voice"]["price"]["old_days"] == 9


def test_the_plans_own_price_file_is_read_first(tmp_path):
    run = _new(tmp_path)
    _prices(run)
    mine = "02_research/presenter_prices_v01.json"
    (run.path / mine).write_text(json.dumps([{"model": "minimax/h3", "checked": TODAY, "tiers": [
        {"criteria": "target resolution=768P", "price": "$0.10", "unit": "second"}]}]), encoding="utf-8")
    rows = {r["situation"]: r for r in create_presenter.rows(run, plan(presenter={
        "situation": "exact_wording", "price_file": mine}))}
    assert rows["specific_person"]["price"]["usd"] == 1.5 and rows["specific_person"]["price"]["file"] == mine
    assert rows["described"]["price"]["usd"] == 2.7           # the others from the run's latest price file


def test_the_pick_is_the_situation_and_user_choice_only_for_another_model_than_the_rows():
    old = {"situation": "exact_wording"}
    assert create_presenter.choose(old, "exact_wording", "row") == {"situation": "exact_wording"}
    assert create_presenter.choose(old, "own_voice", "row") == {"situation": "own_voice"}
    assert create_presenter.choose(old, "own_voice", "minimax/h3") == {"situation": "own_voice"}   # the row's own
    assert create_presenter.choose(old, "described", "minimax/h3") == {
        "situation": "described", "user_choice": True, "model": "minimax/h3"}
    assert create_presenter.choose({"situation": "described", "user_choice": True, "model": "minimax/h3",
                                    "price_file": "p.json"}, "described", "row") == {
        "situation": "described", "price_file": "p.json"}


def test_a_changed_pick_is_written_into_the_next_plan_version_which_tm_ad_check_plan_reads(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)                    # the plan v01 checked
    assert create_presenter.record(run, "exact_wording", "row") is None      # nothing changed, nothing written
    rel = create_presenter.record(run, "exact_wording", "minimax/h3")
    assert rel == "03_wip/production_plan_v02.json"
    data = json.loads((run.path / rel).read_text(encoding="utf-8"))
    assert data["presenter"] == {"situation": "exact_wording", "user_choice": True, "model": "minimax/h3"}
    assert data["lines"] == plan()["lines"]
    assert any(r.get("file") == rel for r in manifest.rows(run))
    assert create_plan.check(run, create_plan.PLAN, run.path / rel)[1] == []     # the user's choice: the check passes


def test_another_situation_without_its_model_is_caught_by_the_plan_check_unchanged(tmp_path):
    run = _new(tmp_path)
    _ready_for(run, create_plan.STORYBOARD)
    rel = create_presenter.record(run, "described", "row")
    problems = create_plan.check(run, create_plan.PLAN, run.path / rel)[1]
    assert [p.field for p in problems] == ["presenter"]       # the take is still Gemini: rewrite it with Seedance
    assert _check(run, create_plan.PLAN, plan(presenter={"situation": "described"}, lines=[
        {**plan()["lines"][1]}, {**plan()["lines"][2], "model": "bytedance/seedance-2.0"}])) == []
