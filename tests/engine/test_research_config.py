"""Trend research's config.yaml: the intake answers, the previous run's config, and validation."""

import json
from datetime import date

import pytest
import yaml

from tm import config, research_config, state
from tm.cli import main
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

BASE = {"category": {"phrase": "uroda", "seeds": ["pielęgnacja twarzy"]}, "market": "PL",
        "language": "Polish"}


@pytest.fixture
def ws(tmp_path):
    folder = tmp_path / "Badania trendów Łódź"
    folder.mkdir()
    return folder


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "uroda", date(2026, 11, 7), playbook=TREND_RESEARCH)


def _problems(run):
    return {p.field: p for p in research_config.validate(run)}


def test_config_defaults_match_playbook_numbers(run):
    path = research_config.write_from_intake(run, {**BASE, "level": "big_calls"})
    assert path == run.path / "config.yaml"
    cfg = config.load(run)
    assert cfg["trends"] == {"min_match": 40, "min_relevant": 10, "max_split_depth": 2,
                             "exclude_terms": []}   # TR1 wins: seasonal is a tag, not noise
    assert cfg["hooks"] == {"shortlist": 8, "min_fit": 3, "max_candidates": 50}
    assert cfg["review"] == {"max_trends": 50}          # issue #129
    assert cfg["growth"] == {"window_days": 14, "baseline_days": 28, "lag_days": 2}
    assert cfg["buckets"] == {
        "act_index": 1.3, "act_min_new": 3, "act_last_days": 5, "act_median_views": 5000,
        "concentrated": 0.6, "rise_index": 0.6, "rise_min_new": 2, "rise_last_days": 7,
        "crowded_creators": 100, "crowded_age_days": 90, "active_days": 14, "season_after_days": 60}
    assert cfg["confidence"] == {"low_creators": 8, "low_top_share": 0.6, "high_creators": 15,
                                 "high_top_share": 0.4}
    assert cfg["picks"] == {"act_now": 5, "still_rising": 5, "valid_days": 14}
    assert cfg["paid"] == {"too_late_min_creators": 30}
    assert cfg["scoring"]["weights"] == {k: 1 for k in ("growth", "earliness", "spread", "confidence",
                                                        "fit", "transfer", "feasibility")}
    assert cfg["benchmark"] == {"source": "meta_ad_library"}
    assert cfg["digest"] == {"map_change_share": 0.25, "schedule": "weekly_monday", "channel": "link"}
    assert cfg["delivery"] == {"channel": "artifact"}
    assert (cfg["currency"], cfg["fx_rate"], cfg["focus"], cfg["market_lang"]) == ("USD", None, None, None)
    assert cfg["category"] == {"inputs": [], "phrase": "uroda", "seeds": ["pielęgnacja twarzy"]}
    assert (cfg["market"], cfg["language"], cfg["mode"]) == ("PL", "Polish", "hitl")
    assert cfg["outputs"] == ["category_report"]
    s = state.load(run)
    assert (s.level, s.outputs) == ("big_calls", ["category_report"])
    assert research_config.validate(run) == []
    assert set(research_config.FIXED) == {"benchmark.source", "digest.channel"}


def test_intake_outputs_level_and_mode(run):
    research_config.write_from_intake(run, {**BASE, "level": "hands_off",
                                            "outputs": ["weekly_digest", "paid_view"]})
    cfg = config.load(run)
    assert cfg["mode"] == "auto"
    assert cfg["outputs"] == ["category_report", "weekly_digest", "paid_view"]  # the report is always made
    assert state.load(run).outputs == cfg["outputs"]
    with pytest.raises(ValueError, match="category_report, weekly_digest, paid_view"):
        research_config.write_from_intake(run, {**BASE, "outputs": ["live_test"]})


def test_missing_intake_is_reported_with_what_to_do(run):
    research_config.write_from_intake(run, {"level": "every_step"})
    problems = _problems(run)
    assert set(problems) == {"category.phrase", "market", "languages"}
    assert all(p.todo.startswith(("Tell Claude", "Confirm both")) for p in problems.values())


def test_rules_are_fixed_and_thresholds_checked(run):
    research_config.write_from_intake(run, {**BASE, "level": "every_step"})
    cfg = config.load(run)
    cfg["benchmark"]["source"] = "foreplay"
    cfg["digest"]["channel"] = "email"
    cfg["buckets"]["act_min_new"] = 2.5
    cfg["confidence"]["low_top_share"] = 1.5
    cfg["scoring"]["weights"]["virality"] = 1
    cfg["scoring"]["weights"]["fit"] = -1
    cfg["trends"]["exclude_terms"] = "sport"
    cfg["outputs"] = ["weekly_digest"]
    cfg["delivery"]["channel"] = "slack"
    cfg["own_results"] = True
    (run.path / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    problems = _problems(run)
    assert set(problems) == {"benchmark.source", "digest.channel", "buckets.act_min_new",
                             "confidence.low_top_share", "scoring.weights.virality",
                             "scoring.weights.fit", "trends.exclude_terms", "outputs",
                             "delivery.channel", "own_results"}
    assert problems["benchmark.source"].what == (
        "benchmark.source is fixed to meta_ad_library: 'foreplay' is not supported yet; it is "
        f"tracked at {research_config.ISSUES}.")
    assert problems["digest.channel"].what == (
        "digest.channel is fixed to link: the digest is a link only; nothing is sent.")
    assert "whole number" in problems["buckets.act_min_new"].what
    assert "category_report" in problems["outputs"].what


def _inputs_problems(run, inputs, **category):
    cfg = config.load(run)
    cfg["category"] = {**cfg["category"], **category, "inputs": inputs}
    (run.path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return research_config.validate(run)


def test_any_start_input_is_accepted_with_the_phrases_proposed_from_it(run):
    """Issue #135: a product or site link, a store, a note or a photo starts a run; the approved phrases are the
    category phrase and its seeds, and the original input stays in category.inputs (V3)."""
    (run.path / "00_raw" / "photo_serum.jpg").write_bytes(b"\xff\xd8 fake photo")
    research_config.write_from_intake(run, {**BASE, "level": "every_step", "focus": "Hebe", "category": {
        "phrase": "serum do twarzy", "seeds": ["pielęgnacja twarzy", "witamina c"],
        "inputs": [{"kind": "phrase", "value": "uroda"}, "pielęgnacja",
                   "https://sklep.example/serum", {"kind": "product", "value": "https://sklep.example/serum"},
                   {"kind": "store", "value": "Hebe"},
                   {"kind": "note", "value": "Klient sprzedaje serum z witaminą C dla cery dojrzałej."},
                   {"kind": "photo", "value": "00_raw/photo_serum.jpg"}]}})
    assert research_config.validate(run) == []
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 0
    assert set(research_config.INPUT_KINDS) >= {"phrase", "product", "store", "note", "photo"}
    assert set(research_config.UNSUPPORTED_INPUTS) == {"competitor", "ad"}


PRODUCT_PAGE = ("<html><head><title>Cat eye gel polish</title></head><body><h1>Magnetic cat eye gel polish</h1>"
                "<p>A magnetic gel polish for a cat eye manicure at home, with a magnet wand. Lasts three weeks "
                "under a UV lamp, for nail art beginners and salons alike.</p><p>Price: 39 PLN</p></body></html>")


def test_a_run_started_from_a_product_link_reads_it_and_takes_the_approved_phrases(run, monkeypatch, capsys):
    """Issue #135 acceptance: only a product link is given; its page is saved (no network: a fixture), the agent
    proposes the phrases, the user approves them, and the config check passes."""
    from tm import page_text
    url = "https://shop.example/cat-eye-gel"
    monkeypatch.setattr(page_text, "download", lambda u: (PRODUCT_PAGE, u))
    monkeypatch.setattr(page_text, "MIN_WORDS", 5)
    assert main(["page", "fetch", "--run", str(run.path), "--url", url, "--name", "cat-eye", "--found-in", "user",
                 "--json"]) == 0
    saved = json.loads(capsys.readouterr().out)["file"]
    assert "magnetic gel polish" in (run.path / saved).read_text(encoding="utf-8")
    research_config.write_from_intake(run, {**BASE, "level": "every_step", "category": {
        "inputs": [{"kind": "product", "value": url}], "phrase": "cat eye nails",
        "seeds": ["nail art", "gel manicure"]}})
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 0
    cfg = config.load(run)
    assert cfg["category"]["inputs"] == [{"kind": "product", "value": url}]   # the original input is kept


def test_a_start_input_is_checked_and_competitors_and_ads_are_not_supported_yet(run):
    research_config.write_from_intake(run, {**BASE, "level": "every_step"})
    whats = [p.what for p in _inputs_problems(run, [
        {"kind": "competitor", "value": "Drogeria Przykład"}, {"kind": "ad", "value": "https://fb.example/ad/1"},
        {"kind": "podcast", "value": "x"}, {"kind": "phrase"}, {"kind": "phrase", "value": "  "},
        {"kind": "note", "value": " "}, {"kind": "product", "value": "serum"},
        {"kind": "photo", "value": "00_raw/missing.jpg"}])]
    assert len(whats) == 8, whats
    assert "(V5)" in whats[0] and "not supported yet" in whats[0] and research_config.ISSUES in whats[0]
    assert "(V6)" in whats[1]
    assert "podcast" in whats[2] and all("is not a category input" in w for w in whats[2:6])
    assert "link" in whats[6] and "00_raw/missing.jpg" in whats[7]
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 2


def test_a_store_input_has_the_brand_as_its_focus(run):
    """V4: one seed phrase per product line, and the focus is the brand unless the user named another."""
    research_config.write_from_intake(run, {**BASE, "level": "every_step"})
    problems = _inputs_problems(run, [{"kind": "store", "value": "Hebe"}])
    assert [p.field for p in problems] == ["focus"] and "V4" in problems[0].what
    assert "Hebe" in problems[0].todo


def test_write_from_previous_copies_and_defaults_to_hands_off(ws, run, monkeypatch, capsys,
                                                            bundled_skills):
    research_config.write_from_intake(run, {**BASE, "level": "every_step",
                                            "outputs": ["category_report", "weekly_digest"],
                                            "trends": {"min_match": 50}})
    first = config.load(run)
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    assert main(["run", "new", "--playbook", "trend-research", "--name", "w2", "--after",
                 str(run.path), "--json"]) == 0
    w2 = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    assert main(["config", "write", "--from-previous", "--run", str(w2.path), "--json"]) == 0
    capsys.readouterr()
    copied = config.load(w2)
    assert copied == {**first, "mode": "auto"}
    assert copied["trends"]["min_match"] == 50
    s = state.load(w2)
    assert (s.level, s.outputs) == ("hands_off", ["category_report", "weekly_digest"])
    # a level from the answers wins; a run that follows no other run has nothing to copy
    w3 = RunFolder.create(ws, "w3", date(2026, 11, 14), playbook=TREND_RESEARCH)
    with pytest.raises(ValueError, match="follows no earlier run"):
        research_config.write_from_previous(w3)
    s3 = state.load(w3)
    s3.previous_run = state.load(w2).previous_run
    state.save(w3, s3)
    research_config.write_from_previous(w3, {"level": "big_calls"})
    assert state.load(w3).level == "big_calls" and config.load(w3)["mode"] == "hitl"


def test_config_command_dispatches_by_playbook(ws, run, tmp_path, capsys):
    answers = tmp_path / "odpowiedzi.json"
    answers.write_text(json.dumps({**BASE, "level": "every_step"}), encoding="utf-8")
    assert main(["config", "write", "--answers", str(answers), "--run", str(run.path), "--json"]) == 0
    assert config.load(run)["trends"]["min_match"] == 40
    assert main(["config", "check", "--run", str(run.path), "--json"]) == 0
    capsys.readouterr()
    ad = RunFolder.create(ws, "Ad 3", date(2026, 11, 7))   # refresh-ad keeps its own config
    assert main(["config", "write", "--from-previous", "--run", str(ad.path), "--json"]) == 1
    assert "Trend research" in json.loads(capsys.readouterr().out)["message"]
    assert main(["config", "write", "--answers", str(answers), "--run", str(ad.path), "--json"]) == 2
    assert "account.id" in {p["field"] for p in json.loads(capsys.readouterr().out)["problems"]}
