"""Issue #143 items 2 to 4 in R1: the no-spend message that names the missed fetch, the product match (`--links`),
paused ads, "too little data", and the account trend built from the ad rows when the account rows have no results.
The weeks and ads are test_r1's (today 2026-11-05, buckets of a week back from 2026-11-03)."""

import json
from datetime import date

import pytest
import yaml
from test_r1 import A, B, CFG, TODAY, ad_rows, normalise, only, run_rank

from tm import r1
from tm.cli import main
from tm.runfolder import RunFolder

LANDING = "https://www.shop.example.com/serum?utm_source=meta"


def _run(tmp_path, name="p", landing=LANDING, product="Serum"):
    run = RunFolder.create(tmp_path, name, date(2026, 11, 5))
    cfg = {"product": {"name": product, "landing_url": landing}, "winner": {"history_days": 28, "target_cpa": 15.0}}
    (run.path / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return run


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _r1(capsys, run, ads, account, *extra):
    capsys.readouterr()
    code = main(["r1", "--run", str(run.path), "--ads", ads, "--account", account, "--today", "2026-11-05",
                 "--json", *extra])
    return code, json.loads(capsys.readouterr().out)


def _ranking(run):
    return json.loads((run.path / "01_base" / "winner_ranking_v01.json").read_text(encoding="utf-8"))


# --- item 2: the ads that spent were missed ------------------------------------------------------

def test_no_ad_spend_while_the_account_spent_names_the_missed_fetch(tmp_path, capsys):
    run = _run(tmp_path)
    zero = [{**row, "amount_spent": {"value": "0", "unit": "PLN"}} for row in A]
    code, out = _r1(capsys, run, _write(tmp_path, "ads.json", zero), _write(tmp_path, "acc.json", A + B))
    assert code == 1
    assert out["message"].startswith("The ad rows hold no spend, but the account spent 6400 in the same weeks: "
                                     "the fetch missed the ads that spent.")
    assert "amount_spent greater than 0, sorted by amount_spent descending (flow.md#a1)" in out["message"]
    assert "Nothing was ranked." in out["message"]


def test_no_spend_anywhere_keeps_the_old_message(tmp_path, capsys):
    run = _run(tmp_path)
    zero = [{**row, "amount_spent": {"value": "0", "unit": "PLN"}} for row in A]
    path = _write(tmp_path, "ads.json", zero)
    code, out = _r1(capsys, run, path, path)
    assert code == 1 and out["message"].startswith("No spend could be read from the ad rows")


# --- item 4: the account rows hold no results ------------------------------------------------------

def test_account_rows_without_results_give_the_trend_from_the_ad_rows(tmp_path, capsys):
    run = _run(tmp_path)
    account = [{**row, "results": "Not available"} for row in A + B]
    code, out = _r1(capsys, run, _write(tmp_path, "ads.json", A + B), _write(tmp_path, "acc.json", account))
    assert code == 0, out
    a = next(c for c in _ranking(run)["candidates"] if c["ad_id"] == "A")
    assert a["account_ratio"] == 1.0 and a["verdict"] == "fading"
    assert "The account rows have no results, so the account trend is built from the ad rows." in a["note"]
    assert "do not include it" not in a["note"]
    assert out["account_from"] == "ads"


def test_not_included_stays_for_its_real_case():
    r = run_rank({"A": A}, B[:1])     # the account spends less than the ad: it lacks it
    assert "do not include it" in only(r, "A").note


# --- item 3: the product match, paused ads, too little data ---------------------------------------

@pytest.mark.parametrize("link,match", [
    ("https://shop.example.com/serum/30ml?fbclid=abc", "own"),
    ("http://WWW.shop.example.com/serum/", "own"),
    ("shop.example.com/serum?utm_campaign=x", "own"),
    ("https://shop.example.com/serums", "near"),
    ("https://shop.example.com/cream", "near"),
    ("https://other.example.org/serum", "other"),
    ("", None), (None, None)])
def test_a_link_matches_by_host_and_path_prefix(link, match):
    assert r1.product_match(link, LANDING) == match


def test_a_landing_page_at_the_root_takes_every_path_of_its_host():
    assert r1.product_match("https://shop.example.com/cream?x=1", "https://shop.example.com/") == "own"


def _three(tmp_path):
    c = ad_rows("C", [(1000, 100)] * 4)
    links = {"A": "https://shop.example.com/serum/30ml?fbclid=1", "B": "https://other.example.org/cream",
             "C": "https://shop.example.com/cream"}
    return A + B + c, _write(tmp_path, "links.json", links)


def test_an_ad_of_another_product_is_set_apart_and_never_ranked(tmp_path, capsys):
    run = _run(tmp_path)
    rows, links = _three(tmp_path)
    code, out = _r1(capsys, run, _write(tmp_path, "ads.json", rows), _write(tmp_path, "acc.json", rows),
                    "--links", links)
    assert code == 0, out
    data = _ranking(run)
    by = {c["ad_id"]: c for c in data["candidates"]}
    assert by["B"]["verdict"] == "other_product" and by["B"]["rank"] is None and "B" not in data["ranking"]
    assert "other.example.org/cream" in by["B"]["note"]
    assert by["A"]["product"] == "own" and by["A"]["verdict"] == "fading"
    assert by["C"]["product"] == "near" and data["near_matches"] == ["C"]
    assert data["other_products"] == ["B"]
    assert data["product"] == {"name": "Serum", "landing_url": LANDING}
    assert out["other_products"] == ["B"] and out["near_matches"] == ["C"]


def test_links_need_the_landing_page(tmp_path, capsys):
    run = _run(tmp_path, landing=None)
    rows, links = _three(tmp_path)
    code, out = _r1(capsys, run, _write(tmp_path, "ads.json", rows), _write(tmp_path, "acc.json", rows),
                    "--links", links)
    assert code == 1 and "product.landing_url" in out["message"]


def test_an_ad_without_spend_in_the_last_14_days_is_paused():
    old = ad_rows("P", [(0, 0), (0, 0), (600, 50), (600, 40)])
    r = run_rank({"A": A, "P": old}, A + B + old)
    assert only(r, "P").paused is True and only(r, "A").paused is False
    assert only(r, "P").to_json()["paused"] is True


def test_too_little_data_is_said_with_the_best_ads_numbers(tmp_path, capsys):
    run = _run(tmp_path)
    thin = ad_rows("T", [(100, 5), (100, 6), (100, 4), (100, 3)])        # 18 results in all
    thinner = ad_rows("U", [(50, 2), (50, 1), (0, 0), (0, 0)])
    other = ad_rows("O", [(600, 30), (600, 40), (600, 50), (600, 40)])
    links = _write(tmp_path, "links.json", {"T": "https://shop.example.com/serum", "U": "https://shop.example.com/serum",
                                            "O": "https://other.example.org/x"})
    rows = thin + thinner + other
    code, out = _r1(capsys, run, _write(tmp_path, "ads.json", rows), _write(tmp_path, "acc.json", rows),
                    "--links", links)
    assert code == 0, out
    little = _ranking(run)["too_little_data"]
    assert little["best_ad"] == "T" and little["best_results"] == 18 and little["min_results"] == 30
    assert little["line"] == "Your Serum ads have too little data to judge: the best has 18 of the 30 results needed."
    assert out["too_little_data"] == little["line"]


def test_no_too_little_data_line_when_an_ad_can_be_judged(tmp_path, capsys):
    run = _run(tmp_path)
    path = _write(tmp_path, "ads.json", A + B)
    code, _ = _r1(capsys, run, path, path)
    assert code == 0 and _ranking(run)["too_little_data"] is None


def test_rank_without_links_marks_no_product():
    r = run_rank({"A": A}, A + B)
    assert only(r, "A").product is None and r.to_json()["other_products"] == []


def test_the_ranking_still_reads_as_before_for_old_pages():
    r = r1.rank({"A": normalise(A)}, normalise(A + B), CFG, TODAY)
    data = r.to_json()
    assert {"today", "last_day", "target_cpa", "config", "ranking", "candidates"} <= set(data)


def test_the_spend_filtered_id_list_is_left_out_with_its_reason():
    level, why = r1.weekly({"level": "ad", "filtering": [{"field": "spend", "operator": "GREATER_THAN", "value": 0}]})
    assert level is None and "step 2a" in why
    assert r1.weekly({"level": "ad", "ad_ids": ["A"], "time_increment": 7}) == ("ad", None)
