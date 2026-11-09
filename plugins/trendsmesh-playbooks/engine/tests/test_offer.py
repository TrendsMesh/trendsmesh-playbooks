"""The Agent plan offer and the sign-in choice (issue #9, PR B)."""

import json

import pytest

from tm import offer
from tm.cli import main

# The answer as https://trendsmesh.com/v1/plans gives it (2026-11-06).
PLANS = {"plans": [{"code": "human", "name": "Human", "monthlyPriceUsd": 0, "trendData": False},
                   {"code": "agent", "name": "Agent", "monthlyPriceUsd": 99, "trendData": True},
                   {"code": "swarm", "name": "AI Swarm", "monthlyPriceUsd": 2000, "trendData": True}],
         "offer": None}


def test_free_month_while_an_offer_covers_agent():
    o = offer.from_plans({**PLANS, "offer": {"plans": ["agent", "swarm"], "freeMonths": 1}})
    assert (o.known, o.free_months, o.price_usd) == (True, 1, 99.0)
    assert "first month is $0" in o.text and "$99 a month" in o.text and o.text.endswith("Want to try it?")


def test_several_free_months():
    o = offer.from_plans({**PLANS, "offer": {"plans": ["agent"], "freeMonths": 3}})
    assert "first 3 months are $0" in o.text


def test_an_offer_for_other_plans_only_is_the_price():
    o = offer.from_plans({**PLANS, "offer": {"plans": ["swarm"], "freeMonths": 2}})
    assert o.free_months is None and "$99 a month" in o.text and "$0" not in o.text


def test_no_offer_is_the_price():
    o = offer.from_plans(PLANS)
    assert o.free_months is None and o.text == (
        "Trend data needs the TrendsMesh Agent plan, $99 a month (tax, where it applies, is shown "
        "at checkout). Want to try it?")


def test_sales_are_always_open_so_a_sales_flag_is_ignored():
    o = offer.from_plans({**PLANS, "salesOpen": False, "offer": {"plans": ["agent"], "freeMonths": 1}})
    assert o.known and o.free_months == 1 and "isn't on sale" not in o.text


@pytest.mark.parametrize("data", [
    None, [], "x", {}, {"offer": None},
    {"plans": [{"code": "agent", "monthlyPriceUsd": "99"}]},
    {"plans": []},
    {"plans": [{"code": "agent", "monthlyPriceUsd": -1}]},
])
def test_unreadable_plans_fall_back_to_the_plans_page(data):
    o = offer.from_plans(data)
    assert not o.known and o.text == "Trend data needs the TrendsMesh Agent plan: https://trendsmesh.com/plans"


@pytest.mark.parametrize("months", [0, -1, True, "1", 1.5])
def test_a_bad_offer_is_ignored(months):
    o = offer.from_plans({**PLANS, "offer": {"plans": ["agent"], "freeMonths": months}})
    assert o.known and o.free_months is None and "$0" not in o.text


def test_unknown_fields_are_ignored():
    o = offer.from_plans({**PLANS, "currency": "USD", "plans": PLANS["plans"] + [{"code": "x"}]})
    assert o.known


def test_cli_with_a_plans_file_and_the_given_upgrade_url(tmp_path, capsys):
    f = tmp_path / "plans.json"
    f.write_text(json.dumps({**PLANS, "offer": {"plans": ["agent"], "freeMonths": 1}}), encoding="utf-8")
    url = "https://trendsmesh.com/app/plan?plan=agent"
    assert main(["offer", "--plans-file", str(f), "--upgrade-url", url, "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["free_months"] == 1 and out["upgrade_url"] == url


def test_cli_refuses_a_non_https_upgrade_url(tmp_path, capsys):
    f = tmp_path / "plans.json"
    f.write_text(json.dumps(PLANS), encoding="utf-8")
    assert main(["offer", "--plans-file", str(f), "--upgrade-url", "javascript:alert(1)", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["upgrade_url"] == offer.PLANS_PAGE


def test_cli_reads_the_api_envelope_and_survives_no_network(monkeypatch, capsys):
    class Resp:
        def __init__(self, body): self.body = body
        def read(self, n): return json.dumps(self.body).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(offer.urllib.request, "urlopen", lambda req, timeout: Resp({"ok": True, "data": PLANS}))
    assert main(["offer", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["known"] is True

    def offline(req, timeout):
        raise OSError("no network")
    monkeypatch.setattr(offer.urllib.request, "urlopen", offline)
    assert main(["offer", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["known"] is False


# --- the sign-in choice ----------------------------------------------------------------------

def test_signin_skip_is_kept_per_workspace(tmp_path):
    assert offer.signin_status(tmp_path) == {"skipped": False, "at": None}
    assert offer.signin_set(tmp_path, "skip")["skipped"] is True
    assert offer.signin_status(tmp_path)["skipped"] is True
    assert offer.signin_status(tmp_path / "other")["skipped"] is False
    assert offer.signin_set(tmp_path, "ask")["skipped"] is False


def test_signin_survives_a_broken_prefs_file(tmp_path):
    (tmp_path / ".trendsmesh").mkdir()
    (tmp_path / ".trendsmesh" / "prefs.json").write_text("{not json", encoding="utf-8")
    assert offer.signin_status(tmp_path)["skipped"] is False


def test_signin_cli(tmp_path, capsys):
    assert main(["signin", "skip", "--workspace", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] is True
    assert main(["signin", "status", "--workspace", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] is True


def test_a_saved_plans_answer_from_the_environment(tmp_path, monkeypatch):
    f = tmp_path / "plans.json"
    f.write_text(json.dumps({**PLANS, "offer": {"plans": ["agent"], "freeMonths": 1}}), encoding="utf-8")
    monkeypatch.setenv("TM_PLANS_FILE", str(f))
    assert offer.from_plans(offer.fetch()).free_months == 1
    monkeypatch.setenv("TM_PLANS_FILE", str(tmp_path / "missing.json"))
    assert offer.fetch() is None


# --- review fixes ----------------------------------------------------------------------------

@pytest.mark.parametrize("data", [
    {**PLANS, "offer": {"plans": 5, "freeMonths": 1}},
    {**PLANS, "offer": {"plans": "superagent", "freeMonths": 1}},
])
def test_odd_offer_plans_are_ignored(data):
    o = offer.from_plans(data)
    assert o.known and o.free_months is None


def test_a_price_that_is_not_finite_is_unknown():
    o = offer.from_plans({**PLANS, "plans": [{"code": "agent", "monthlyPriceUsd": float("inf")}]})
    assert not o.known


def test_more_than_twelve_free_months_is_ignored():
    o = offer.from_plans({**PLANS, "offer": {"plans": ["agent"], "freeMonths": 99}})
    assert o.free_months is None


def test_the_price_says_tax_is_shown_at_checkout():
    o = offer.from_plans({**PLANS, "offer": {"plans": ["agent"], "freeMonths": 1}})
    assert "tax" in o.text and "new subscribers" in o.text


@pytest.mark.parametrize("url,kept", [
    ("https://trendsmesh.com/app/plan?plan=agent", True),
    ("https://app.trendsmesh.com/plans", True),
    ("https://evil.example/pay", False),
    ("https://trendsmesh.com.evil.example/pay", False),
    ("https://evil.example/?u=https://trendsmesh.com", False),
    ("http://trendsmesh.com/plans", False),
    ("https://trendsmesh.com/plans x", False),
    ("https://user@evil.example/", False),
    ("https://evil.example\\.trendsmesh.com/pay", False),
    ("https://trendsmesh.com:abc/", False),
    ("https://trendsmesh.com:99999/", False),
    ("https://trendsmesh.com/\x00", False),
])
def test_only_a_trendsmesh_upgrade_url_is_kept(url, kept):
    assert (offer.safe_upgrade_url(url) == url) is kept
    if not kept:
        assert offer.safe_upgrade_url(url) == offer.PLANS_PAGE


def test_a_broken_answer_never_crashes_fetch(monkeypatch):
    import http.client

    def broken(req, timeout):
        raise http.client.IncompleteRead(b"{")
    monkeypatch.setattr(offer.urllib.request, "urlopen", broken)
    assert offer.fetch() is None
