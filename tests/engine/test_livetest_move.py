"""Refresh an ad, G12 (issue #64, option 1): both test ads are new and the original keeps running untouched; when the
variant wins, on the user's yes, the winning ad moves into the original's campaign in a new ad set, PAUSED, from the
test ad's post, never inside the original's ad set. A proposal, the user's yes and a record, as Create an ad's upload;
nothing is ever activated, and the final report gives the user's part step by step."""

import json
from datetime import date

import pytest

from test_flow import _book_test, _library_rows, _measuring_run, run  # noqa: F401  (run is a fixture)
from tm import flow, livetest_move as mv, state
from tm.cli import main
from tm.flow import complete, decide
from tm.stops import Stop


def _measured(run):
    _measuring_run(run)
    for day in ("2026-11-13", "2026-11-15", "2026-11-17"):
        flow.next(run, today=date.fromisoformat(day))
        complete(run, "E4", measured=day, today=date.fromisoformat(day))
    assert flow.next(run, today=date(2026, 11, 17)).checkin.ids == ["G12"]


@pytest.fixture
def won(run):
    _measured(run)
    decide(run, "G12", "scale", by="user", note="the variant won on hook rate")
    return run


def _save(run, rel, data):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _proposal(run, **over):
    _save(run, "05_results/move_reads_v01.json", {"answer": "Meta's answers, saved"})
    data = {"ad_account_id": "act_1",
            "original": {"ad_id": "ad_orig", "adset_id": "set_orig", "campaign_id": "camp_orig",
                         "campaign_name": "Ebook prospecting", "adset_name": "Ebook broad PL",
                         "ad_name": "Ebook hook original", "saved": "05_results/move_reads_v01.json"},
            "winner": {"key": "v1", "ad_id": "ad_test_v1", "post_id": "page_1_post_9",
                       "saved": "05_results/move_reads_v01.json"},
            "adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                      "budget": {"campaign_budget": True}},
            "ad": {"name": "Ebook new hook winner", "post_id": "page_1_post_9"},
            "status": "PAUSED"}
    for key, value in over.items():
        data[key] = value
    return _save(run, "05_results/move_proposal_v01.json", data)


def _objects(run, **over):
    data = {"proposal": "05_results/move_proposal_v01.json",
            "adset": {"id": "set_new", "name": "Ebook new hook winner PL", "status": "PAUSED",
                      "campaign_id": "camp_orig"},
            "ad": {"id": "ad_new", "name": "Ebook new hook winner", "status": "PAUSED", "adset_id": "set_new",
                   "post_id": "page_1_post_9", "preview_url": "https://example.com/preview"},
            "answers": "05_results/move_reads_v01.json"}
    data.update(over)
    return _save(run, "05_results/move_objects_v01.json", data)


def _fields(problems):
    return {p.field for p in problems}


def test_a_clean_proposal_passes_and_its_card_says_paused_post_and_own_ad_set(won):
    _, problems = mv.check(won, _proposal(won))
    assert problems == []
    card = mv.card(won)
    assert "Ebook prospecting" in card["question"] and "PAUSED" in card["question"]
    notes = " ".join(card["notes"])
    assert "likes, comments and shares" in notes and "restart" in notes and "nothing is spent" in notes


def test_nothing_moves_unless_the_variant_won(run):
    _measured(run)
    decide(run, "G12", "keep", by="user", note=None)
    with pytest.raises(ValueError, match="scale"):
        mv.check(run, _proposal(run))
    assert mv.done_note(run) is None


@pytest.mark.parametrize("change,field", [
    ({"status": "ACTIVE"}, "status"),
    ({"adset": {"id": "set_orig", "campaign_id": "camp_orig", "settings_from": "set_orig",
                "name": "Ebook new hook winner PL", "budget": {"campaign_budget": True}}}, "adset"),
    ({"adset": {"campaign_id": "camp_other", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                "budget": {"campaign_budget": True}}}, "adset.campaign_id"),
    ({"ad": {"name": "Ebook new hook winner", "post_id": "page_1_post_other"}}, "ad.post_id"),
    ({"adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ad set 1",
                "budget": {"campaign_budget": True}}}, "adset.name"),
    ({"adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                "budget": {"amount": 50, "cadence": "daily", "currency": "PLN"}}}, "adset.budget"),     # no words
    ({"adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                "budget": {"amount": 500, "cadence": "lifetime", "currency": "PLN", "said": "500 in all"}}},
     "adset.budget"),                                                                        # daily only
    ({"adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                "budget": {"campaign_budget": True, "amount": 50}}}, "adset.budget"),     # none under CBO
    ({"adset": {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
                "budget": {"amount": 50, "cadence": "daily", "currency": "PLN", "said": "50 a day"}}},
     "original.adset_budget"),                                                     # the reference is not read
    ({"winner": {"key": "v1", "ad_id": "ad_test_v1", "post_id": "page_1_post_9"}}, "winner"),
])
def test_the_check_refuses(won, change, field):
    _, problems = mv.check(won, _proposal(won, **change))
    assert field in _fields(problems)


def _own_budget(won):
    """A campaign without a campaign budget: the user's daily budget, the original ad set's shown for reference."""
    budget = {"amount": 50, "cadence": "daily", "currency": "PLN", "said": "50 zł a day for the new one"}
    adset = {"campaign_id": "camp_orig", "settings_from": "set_orig", "name": "Ebook new hook winner PL",
             "budget": budget}
    original = {**json.loads(_proposal(won).read_text())["original"], "adset_budget": "120 PLN"}
    return _proposal(won, adset=adset, original=original)


def test_a_daily_ad_set_budget_in_the_users_words_passes_with_the_original_shown(won):
    assert mv.check(won, _own_budget(won))[1] == []
    notes = " ".join(mv.card(won)["notes"])
    assert "120 PLN" in notes and "How much a day" in notes and "targeting, placements" in notes


def test_under_a_campaign_budget_the_card_says_the_ad_set_gets_none(won):
    mv.check(won, _proposal(won))
    assert "gets none of its own" in " ".join(mv.card(won)["notes"])


def test_nothing_is_recorded_without_the_users_yes(won):
    mv.check(won, _proposal(won))
    _, problems = mv.record(won, _objects(won))
    assert _fields(problems) == {"yes"}
    with pytest.raises(ValueError, match="--note"):
        mv.approve(won, " ")


def test_a_yes_to_an_older_proposal_does_not_count(won):
    mv.check(won, _proposal(won))
    mv.approve(won, "yes, do it")
    _save(won, "05_results/move_proposal_v02.json", json.loads(_proposal(won).read_text()))
    _, problems = mv.record(won, _objects(won))
    assert _fields(problems) == {"proposal"}           # v02 is not checked, so v01's yes doesn't carry over
    mv.check(won, won.path / "05_results/move_proposal_v02.json")
    assert _fields(mv.record(won, _objects(won))[1]) == {"yes"}


def test_an_object_that_is_not_paused_is_a_stop(won):
    mv.check(won, _proposal(won))
    mv.approve(won, "yes, do it")
    ad = {"id": "ad_new", "name": "Ebook new hook winner", "status": "ACTIVE", "adset_id": "set_new",
          "post_id": "page_1_post_9", "preview_url": "https://example.com/preview"}
    with pytest.raises(Stop, match="not paused"):
        mv.record(won, _objects(won, ad=ad))
    assert mv.recorded(won) is None


def test_the_record_refuses_the_originals_ad_set_and_another_post(won):
    mv.check(won, _proposal(won))
    mv.approve(won, "yes, do it")
    adset = {"id": "set_orig", "name": "Ebook broad PL", "status": "PAUSED", "campaign_id": "camp_orig"}
    ad = {"id": "ad_new", "name": "Ebook new hook winner", "status": "PAUSED", "adset_id": "set_orig",
          "post_id": "page_1_post_other", "preview_url": ""}
    _, problems = mv.record(won, _objects(won, adset=adset, ad=ad))
    assert {"adset.id", "ad.post_id", "ad.preview_url"} <= _fields(problems)


def test_the_final_report_gives_the_users_three_steps(won):
    mv.check(won, _proposal(won))
    mv.approve(won, "yes, do it")
    assert mv.record(won, _objects(won))[1] == []
    out = mv.report(won)
    assert len(out["steps"]) == 3
    on, money, off = out["steps"]
    assert "turn on" in on and "Ebook new hook winner PL" in on
    # under a campaign budget: Meta can shift budget at once, so spend limits for a gradual move (the owner, #64)
    assert "Ebook prospecting" in money and "at once" in money and "spend limits" in money
    assert "turn off" in off and "Ebook hook original" in off
    assert out["preview_url"] == "https://example.com/preview"
    assert "Nothing in this run switches anything on" in out["text"]


def test_with_ad_set_budgets_the_budget_step_moves_it_between_the_ad_sets(won):
    mv.check(won, _own_budget(won))
    mv.approve(won, "yes, do it")
    mv.record(won, _objects(won))
    money = mv.report(won)["steps"][1]
    assert "50 PLN" in money and "same amount" in money and "Ebook broad PL" in money


def test_tm_next_offers_the_move_then_reports_the_users_part(won):
    _library_rows(won, 1)
    nxt = flow.next(won)
    assert nxt.action == "done" and "new ad set" in nxt.message and "PAUSED" in nxt.message
    mv.check(won, _proposal(won))
    mv.approve(won, "yes, do it")
    mv.record(won, _objects(won))
    assert "tm live-test move report" in flow.next(won).message


def test_a_no_is_recorded_and_not_asked_again(won):
    mv.decline(won, "no, I'll do it myself")
    _library_rows(won, 1)
    assert "new ad set" not in flow.next(won).message
    assert state.load(won).checked[mv.KEY_NO]["said"] == "no, I'll do it myself"


def test_cli_check_approve_record_report(won, capsys):
    def cli(*args):
        code = main(["live-test", "move", *args, "--run", str(won.path), "--json"])
        return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    code, out = cli("check", "--file", str(_proposal(won)))
    assert code == 0 and out["card"]["status"] == "PAUSED"
    code, out = cli("record", "--file", str(_objects(won)))
    assert code == 2 and "yes" in out["message"]
    assert cli("approve", "--note", "yes, do it")[0] == 0
    code, out = cli("record", "--file", str(_objects(won)))
    assert code == 0 and len(out["steps"]) == 3
    code, out = cli("report")
    assert code == 0 and out["ids"] == {"adset": "set_new", "ad": "ad_new"}
