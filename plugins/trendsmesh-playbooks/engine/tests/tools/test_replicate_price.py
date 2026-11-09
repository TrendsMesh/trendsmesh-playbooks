"""tm tool replicate_price: live prices from the model pages' billingConfig (the HTTP fetch is faked)."""

import json
from pathlib import Path

import pytest

from tm import organic_pack
from tm.tools import TOOLS
from tm.tools import replicate_price as tool

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "organic"
PAGE = (FIXTURES / "h3_model_page.html").read_text(encoding="utf-8")
SPEC = Path(__file__).resolve().parents[5] / "handoff" / "organic-video_v02" / "examples" / \
    "pet-store-proposals" / "02_research" / "models" / "prices_2026-11-06.json"


@pytest.fixture
def pages(monkeypatch):
    served = {"https://replicate.com/alibaba/wan-3": PAGE}
    monkeypatch.setattr(tool, "fetch", lambda url: served.get(url, "<html>$0.0001 per second</html>"))
    monkeypatch.setattr(tool, "today", lambda: "2026-11-06")
    return served


def _call(run, capsys, *models, extra=()):
    code = tool.main(["--run", str(run.path), "--json", *extra, *models])
    return code, json.loads(capsys.readouterr().out)


def test_billing_config_parsed_from_page(run, pages, capsys):
    code, out = _call(run, capsys, "alibaba/wan-3")
    assert code == 0 and out["outputs"] == ["02_research/models/prices_2026-11-06_v01.json"]
    written = json.loads((run.path / out["outputs"][0]).read_text(encoding="utf-8"))
    assert [t["criteria"] for t in written[0]["tiers"]] == [f"target resolution={r}" for r in ("480p", "720p", "1080p")]
    assert written[0]["checked"] == "2026-11-06" and written[0]["tiers"][1] == {
        "criteria": "target resolution=720p", "price": "$0.07", "unit": "second of output video"}
    assert "replicate.com model page billingConfig" in (run.path / "manifest.md").read_text(encoding="utf-8")
    if not SPEC.is_file():
        pytest.skip("the handoff's price file is not in this checkout")

    theirs = next(e for e in json.loads(SPEC.read_text(encoding="utf-8")) if e["model"] == "alibaba/wan-3")
    assert theirs["tiers"] == written[0]["tiers"]


def test_placeholder_price_string_ignored(run, pages, capsys):
    code, out = _call(run, capsys, "someone/else", "alibaba/wan-3")   # a partial failure exits 0
    assert code == 0
    written = json.loads((run.path / out["outputs"][0]).read_text(encoding="utf-8"))
    assert written[0] == {"model": "someone/else", "error": "billingConfig not found"}
    assert "0.0001" not in json.dumps(written)
    code, out = _call(run, capsys, "someone/else")                    # every model failed: a stop
    assert code == 2 and out["status"] == "stop" and "billingConfig not found" in out["message"]


def test_price_of_needs_matching_tier(tmp_path):
    f = tmp_path / "prices.json"
    f.write_text(json.dumps([
        {"model": "a/b", "checked": "2026-11-06", "tiers": [
            {"criteria": "target resolution=720p", "price": "$0.07", "unit": "second of output video"},
            {"criteria": "target resolution=1080p", "price": "$0.14", "unit": "second of output video"}]},
        {"model": "c/d", "checked": "2026-11-06", "tiers": [{"criteria": "all", "price": "$1,000.5", "unit": "run"}]},
        {"model": "e/f", "error": "billingConfig not found"}]), encoding="utf-8")
    assert organic_pack.price_of(f, "a/b", "target resolution=720p") == (0.07, "second of output video", "2026-11-06")
    assert organic_pack.price_of(f, "c/d") == (1000.5, "run", "2026-11-06")
    for model, crit in (("a/b", None), ("a/b", "target resolution=480p"), ("a/b", "720p"), ("zz/zz", None),
                        ("e/f", None)):
        with pytest.raises(ValueError):
            organic_pack.price_of(f, model, crit)
    for bad in ("nan", "inf", "0", "$0.00", "-1"):
        g = tmp_path / f"bad{bad}.json"
        g.write_text(json.dumps([{"model": "x/y", "checked": "d", "tiers": [
            {"criteria": "all", "price": bad, "unit": "run"}]}]), encoding="utf-8")
        with pytest.raises(ValueError):
            organic_pack.price_of(g, "x/y")
    with pytest.raises(ValueError, match="720p = \\$0.07.*1080p = \\$0.14"):
        organic_pack.price_of(f, "a/b")


def test_price_tool_is_free():
    t = TOOLS["replicate_price"]
    assert t.tier == "base" and t.keys == () and t.kind_for(["--run", "r", "a/b"]) is None


def test_never_overwrites_a_price_file(run, pages, capsys):
    _, first = _call(run, capsys, "alibaba/wan-3")
    path = run.path / first["outputs"][0]
    before = path.read_text(encoding="utf-8")
    _, second = _call(run, capsys, "alibaba/wan-3")
    assert second["outputs"] == ["02_research/models/prices_2026-11-06_v02.json"]
    assert path.read_text(encoding="utf-8") == before
    code, refused = _call(run, capsys, "alibaba/wan-3", extra=["--out", first["outputs"][0]])
    assert code == 1 and "never overwritten" in refused["message"]
    assert path.read_text(encoding="utf-8") == before


def test_collection_lists_its_models(run, monkeypatch, capsys):
    monkeypatch.setattr(tool, "today", lambda: "2026-11-06")
    monkeypatch.setattr(tool, "fetch", lambda url: '<a href="/explore/x"></a><a href="/a/b"></a><a href="/a/b"></a>'
                        if "collections" in url else PAGE)
    _, out = _call(run, capsys, extra=["--collection", "image-to-video"])
    assert [r["model"] for r in out["results"]] == ["a/b"]


TIERS = {"current_tiers": [{"criteria": [], "prices": [{"price": "$0.5", "metric_display": "image"}]}]}
GOOD = [{"criteria": "all", "price": "$0.5", "unit": "image"}]


def _serve(monkeypatch, html):
    monkeypatch.setattr(tool, "today", lambda: "2026-11-06")
    monkeypatch.setattr(tool, "fetch", lambda url: html)


@pytest.mark.parametrize("name,html", [
    ("last key", '<script>{"id": 1, "billingConfig": ' + json.dumps(TIERS) + '}</script>'),
    ("other order", '{"modelName": "m", "billingConfig":' + json.dumps(TIERS) + ', "price": "$0.0001"}'),
    ("html entities", '<div data-x="{&quot;billingConfig&quot;: ' + json.dumps(TIERS).replace('"', "&quot;") + '}">'),
    ("backslash escaped", '<script>var s = "{\\"billingConfig\\": '
     + json.dumps(TIERS).replace('"', '\\"') + '}";</script>'),
])
def test_billing_config_found_in_any_form(monkeypatch, name, html):
    _serve(monkeypatch, html)
    assert tool.billing("a/b", "2026-11-06") == {"model": "a/b", "checked": "2026-11-06", "tiers": GOOD}


def test_every_failure_is_an_error_entry_never_a_price(monkeypatch):
    _serve(monkeypatch, '{"billingConfig": {"current_tiers": [ nope]}, "price": 1}')
    assert tool.billing("a/b", "d") == {"model": "a/b", "error": "billingConfig not found"}
    _serve(monkeypatch, '{"billingConfig": {"current_tiers": []}, "price": "$0"}')
    assert tool.billing("a/b", "d") == {"model": "a/b", "error": "billingConfig holds no prices"}

    def down(url):
        raise tool.requests.ConnectionError("boom")
    monkeypatch.setattr(tool, "fetch", down)
    assert tool.billing("a/b", "d") == {"model": "a/b", "error": "page could not be read: ConnectionError"}


def test_bad_model_names_are_never_fetched(monkeypatch):
    seen = []
    monkeypatch.setattr(tool, "fetch", lambda url: seen.append(url) or "")
    for bad in ("a/b?x=1", "../x", "a/b/c", "nobar", "a b/c"):
        assert "error" in tool.billing(bad, "d")
    assert seen == []


def test_one_date_for_the_file_and_checked(run, monkeypatch, capsys):
    days = iter(["2026-11-06", "2026-11-07"])
    monkeypatch.setattr(tool, "today", lambda: next(days))
    monkeypatch.setattr(tool, "fetch", lambda url: PAGE)
    _, out = _call(run, capsys, "alibaba/wan-3")
    assert out["outputs"] == ["02_research/models/prices_2026-11-06_v01.json"]
    assert out["results"][0]["checked"] == "2026-11-06"
