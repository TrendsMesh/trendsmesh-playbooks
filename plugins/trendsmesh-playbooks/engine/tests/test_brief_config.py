"""The creative brief's config.yaml (playbook 02): the defaults, the one-card intake, its checks,
and a run started from a trend research pick (`tm run new --seed`)."""

import json
import shutil
from datetime import date

import pytest

from tm import brand, brief_config, config, manifest, seeds, state
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

BASE = {"account": {"id": "act_1", "market": "US", "language": "English"},
        "product": {"name": "Linen duvet", "landing_url": "https://example.com/duvet",
                    "category_phrase": "bedding"}}
PROFILE = {
    "schema": "brand/1", "kind": "brand", "brand": "Night School",
    "stands_for": "Sleep better with a calm evening routine.",
    "tone": ["warm", "plain", "dry"], "off_limits": [], "off_limits_asked": True, "claims": [],
    "competitors": [], "guide": {"source": "none", "where": ""}, "drafted_from": ["landing"],
    "confirmed": "2026-11-07",
}


def _seed(**kw) -> dict:
    base = {"schema": seeds.SCHEMA, "seed_id": "2026-11-04_beauty:t1", "source": "pb4", "run": "2026-11-04_beauty",
            "created": "2026-11-04", "category": "beauty", "sub_category": "nail art", "market": "GB",
            "trend_id": "t1", "kind": "topic_trend", "trend_name": "Cat-eye nails", "bucket": "act_now",
            "band": "top 25%", "paid_level": "crowded", "angle": "A 7 s macro clip.", "risk": "One account.",
            "valid_until": "2026-11-18", "report": None,
            "evidence": "runs/04-trend-research/2026-11-04_beauty/02_research/videos/t1*.json"}
    return {**base, **kw}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "Marka Łódź"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "duvet", date(2026, 11, 7), playbook=CREATIVE_BRIEF)


def _problems(run):
    return {p.field: p for p in brief_config.validate(run)}


def _new(capsys, *extra, name="pick"):
    capsys.readouterr()
    code = main(["run", "new", "--playbook", "creative-brief", "--name", name, *extra, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_defaults_match_playbook_numbers(run):
    path = config.write_from_intake(run, {**BASE, "level": "big_calls"})   # config hands it to brief_config
    assert path == run.path / "config.yaml"
    cfg = config.load(run)
    assert cfg["account"] == {"id": "act_1", "market": "US", "language": "English", "currency": None}
    assert cfg["brand"] == {"profile": None, "guide": None}
    assert cfg["voice"] == {"links": [], "tiers": ["own_customers", "category", "brand"],
                            "sources": ["reddit_archive", "import"], "min_phrases_per_concept": 1,
                            "bank_min": 20, "bank_max": 40}
    assert cfg["music"] == {"require_ads_license": False}
    assert cfg["trends"] == {"kinds": ["hook", "topic", "format", "sound"], "min_relevant": 5,
                             "terms": [], "exclude_terms": []}
    assert cfg["persona"] == {"min_results_per_segment": 10}
    assert cfg["formats"] == {"placement_share_min": 0.25}
    assert cfg["brief"] == {"valid_days_default": 14,
                            "recipients": ["decision", "strategy", "creator", "editor", "media-buyer"],
                            "currency": "USD", "fx_rate": None}
    assert cfg["scoring"] == {"weights": {c: 1 for c in ("brand_fit", "persona_fit", "bridge", "lifecycle",
                                                         "transfer", "sensitivity", "feasibility")}}
    assert cfg["benchmark"] == {"source": "meta_ad_library"}
    assert cfg["concepts"] == {"count": 3, "min_axes_diff": 2}
    assert cfg["outputs"] == ["review_pack", "briefs", "animatics", "page"]
    assert cfg["delivery"] == {"channel": "artifact"}
    assert cfg["animatic"] == {"formats": None, "fps": 24}
    assert cfg["intake"] == {k: None for k in ("budget", "deadline", "approver", "rights", "fee")}
    assert cfg["seed"] is None
    assert set(brief_config.FIXED) == {"benchmark.source", "voice.tiers"}
    s = state.load(run)
    assert (s.level, s.outputs) == ("big_calls", ["review_pack", "briefs", "animatics", "page"])
    assert brief_config.validate(run) == []
    assert config.validate(run) == []


def test_foreplay_not_supported_yet(run):
    brief_config.write_from_intake(run, {**BASE, "benchmark": {"source": "foreplay"}})
    problem = _problems(run)["benchmark.source"]
    assert "Foreplay is not supported yet: saturation uses the Meta Ad Library" in problem.what
    assert f"(tracked at {brief_config.ISSUES})" in problem.what
    brief_config.write_from_intake(run, {**BASE, "voice": {"tiers": ["own_customers", "category", "brand", "C"]}})
    assert "voice.tiers" in _problems(run)                # tier C never counts as evidence (CB5)


def test_briefs_without_animatics_refused_and_page_required(run):
    brief_config.write_from_intake(run, {**BASE, "outputs": ["briefs", "review_pack", "page"]})
    problem = _problems(run)["outputs"]
    assert "CB11" in problem.what and "animatics" in problem.what
    brief_config.write_from_intake(run, {**BASE, "outputs": ["review_pack", "animatics", "page"]})
    assert "CB11" in _problems(run)["outputs"].what       # and the reverse
    brief_config.write_from_intake(run, {**BASE, "outputs": ["review_pack"]})
    assert "CB12" in _problems(run)["outputs"].what
    for skipping in (["page"], ["animatics", "page"]):   # neither the review pack nor the briefs: no concepts
        brief_config.write_from_intake(run, {**BASE, "outputs": skipping})
        problems = [p for p in brief_config.validate(run) if p.field == "outputs"]
        assert any("C1, G2" in p.what and p.todo.startswith("Add review_pack") for p in problems), skipping
    brief_config.write_from_intake(run, {**BASE, "outputs": ["briefs", "animatics", "page"]})
    assert brief_config.validate(run) == []               # everything but the review pack still has concepts
    brief_config.write_from_intake(run, {**BASE, "outputs": ["page", "review_pack"]})
    assert config.load(run)["outputs"] == ["review_pack", "page"]   # the review pack alone: playbook order
    assert brief_config.validate(run) == []
    with pytest.raises(ValueError, match="review_pack, briefs, animatics, page"):
        brief_config.write_from_intake(run, {**BASE, "outputs": ["live_test"]})


def test_media_buyer_spelling_normalised(run):
    brief_config.write_from_intake(run, {**BASE, "brief": {"recipients": ["creator", "media_buyer"]}})
    assert config.load(run)["brief"]["recipients"] == ["creator", "media-buyer"]
    assert brief_config.validate(run) == []
    for recipients, word in ((["creator", "client"], "client"), ([], "at least one")):
        brief_config.write_from_intake(run, {**BASE, "brief": {"recipients": recipients}})
        assert word in _problems(run)["brief.recipients"].what


def test_fx_rate_required_for_pln_account(run):
    pln = {**BASE, "account": {**BASE["account"], "currency": "PLN"}}
    brief_config.write_from_intake(run, pln)
    problem = _problems(run)["brief.fx_rate"]
    assert "PLN" in problem.what and "USD" in problem.what
    brief_config.write_from_intake(run, {**pln, "brief": {"fx_rate": 3.70}})
    assert brief_config.validate(run) == []
    brief_config.write_from_intake(run, {**pln, "brief": {"fx_rate": 0}})
    assert "brief.fx_rate" in _problems(run)


def test_other_fields_checked(run):
    brief_config.write_from_intake(run, {
        "account": BASE["account"],
        "product": {"name": "Linen duvet", "landing_url": "ftp://example.com", "category_phrase": "  "},
        "trends": {"kinds": ["hook", "meme"]}, "delivery": {"channel": "email"}, "colour": "blue"})
    assert set(_problems(run)) == {"product.landing_url", "product.category_phrase", "trends.kinds",
                                   "delivery.channel", "colour"}
    brief_config.write_from_intake(run, {**BASE, "trends": {"kinds": []}})
    assert set(_problems(run)) == {"trends.kinds"}       # at least one kind


def test_answers_cannot_name_a_seed(run):
    brief_config.write_from_intake(run, {**BASE, "seed": "2026-11-04_beauty:t1"})
    assert config.load(run)["seed"] is None              # only run.json's seed counts


def test_unreadable_seed_file_is_refused(ws, bundled_skills, capsys):
    seeds.add(ws, _seed())
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    started = RunFolder.open(out["path"])
    (started.path / "00_raw" / "seed.json").unlink()
    (started.path / "00_raw" / "seed.json").write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError, match="does not hold one JSON object"):
        brief_config.write_from_intake(started, BASE)


def test_seed_prefills_category_and_market(ws, run, bundled_skills, capsys):
    seeds.add(ws, _seed())
    seeds.add(ws, _seed(seed_id="2026-11-04_beauty:t2", trend_id="t2", sub_category=None, paid_level="none"))
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    assert code == 0, out
    started = RunFolder.open(out["path"])
    assert json.loads((started.path / "00_raw" / "seed.json").read_text(encoding="utf-8")) == _seed()
    assert [(r["file"], r["source"]) for r in manifest.rows(started)] == [("00_raw/seed.json",
                                                                            "seed from 2026-11-04_beauty")]
    assert state.load(started).brief == {"seed": "2026-11-04_beauty:t1", "seed_paid": "competitor_found"}

    brief_config.write_from_intake(started, {"account": {"id": "act_1"}, "product": {"name": "Gel kit"}})
    cfg = config.load(started)
    assert (cfg["product"]["category_phrase"], cfg["account"]["market"], cfg["seed"]) == (
        "nail art", "GB", "2026-11-04_beauty:t1")
    brief_config.write_from_intake(started, BASE)       # the answers win
    cfg = config.load(started)
    assert (cfg["product"]["category_phrase"], cfg["account"]["market"]) == ("bedding", "US")

    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t2", name="pick2")   # no sub_category: the category
    assert code == 0, out
    other = RunFolder.open(out["path"])
    assert state.load(other).brief == {"seed": "2026-11-04_beauty:t2", "seed_paid": "none_found"}
    brief_config.write_from_intake(other, {"product": {"name": "Gel kit"}})
    assert config.load(other)["product"]["category_phrase"] == "beauty"

    brief_config.write_from_intake(run, {"product": {"name": "Gel kit"}})   # a run without a seed
    cfg = config.load(run)
    assert (cfg["product"]["category_phrase"], cfg["account"]["market"], cfg["seed"]) == (None, None, None)


def test_expired_seed_still_starts_a_run(ws, bundled_skills, capsys):
    seeds.add(ws, _seed(valid_until="2026-10-30", paid_level="not_checked"))
    assert date.fromisoformat("2026-10-30") < date.today()
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    assert code == 0, out
    started = RunFolder.open(out["path"])
    assert json.loads((started.path / "00_raw" / "seed.json").read_text(encoding="utf-8"))["valid_until"] == "2026-10-30"
    assert state.load(started).brief == {"seed": "2026-11-04_beauty:t1", "seed_paid": None}


def test_seed_paid_level_maps_all_five_values():
    assert set(brief_config.SEED_PAID) == set(seeds.PAID_LEVELS)
    assert brief_config.SEED_PAID == {"none": "none_found", "found": "competitor_found",
                                      "crowded": "competitor_found", "not_checkable": None, "not_checked": None}


@pytest.mark.parametrize("level,hint", [("none", "none_found"), ("found", "competitor_found"),
                                        ("crowded", "competitor_found"), ("not_checkable", None),
                                        ("not_checked", None)])
def test_each_paid_level_reaches_the_run(ws, bundled_skills, capsys, level, hint):
    seeds.add(ws, _seed(paid_level=level))
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    assert code == 0, out
    assert state.load(RunFolder.open(out["path"])).brief == {"seed": "2026-11-04_beauty:t1", "seed_paid": hint}


def test_failed_seed_write_leaves_no_run(ws, bundled_skills, capsys, monkeypatch):
    seeds.add(ws, _seed())

    def broken(*a, **kw):
        raise OSError("disk full")

    with monkeypatch.context() as m:
        m.setattr(manifest, "record", broken)
        code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    assert code == 1 and out["status"] == "error"
    assert "could not be started from the seed" in out["message"] and "disk full" in out["message"]
    assert list((ws / "runs" / CREATIVE_BRIEF).iterdir()) == []   # nothing resumes without its seed

    def kept(path, ignore_errors=False):                           # the folder cannot be removed
        pass

    with monkeypatch.context() as m:
        m.setattr(manifest, "record", broken)
        m.setattr(shutil, "rmtree", kept)
        code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1", name="held")
    (left,) = (ws / "runs" / CREATIVE_BRIEF).iterdir()
    assert code == 1 and "could not be removed" in out["message"] and str(left) in out["message"]
    shutil.rmtree(left)
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")    # the same command works again
    assert code == 0, out


def _raw_library(ws, *lines):
    path = ws / seeds.FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


@pytest.mark.parametrize("row,word", [(_seed(paid_level="bogus"), "paid_level"),
                                      (_seed(run=None, created="soon"), "created"),
                                      (_seed(kind="creator_trend"), "creator_trend")])
def test_seed_breaking_seed1_or_of_another_kind_is_refused(ws, bundled_skills, capsys, row, word):
    _raw_library(ws, json.dumps(row))
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")
    assert code == 1 and out["status"] == "error"          # no run exists yet: a bad argument, not a stop
    assert word in out["message"] and "start the brief without --seed" in out["message"]
    assert "continues from the same place" not in out["message"]
    assert not (ws / "runs" / CREATIVE_BRIEF).exists()


def test_damaged_seed_lines_are_named(ws, bundled_skills, capsys):
    good = json.dumps(_seed())
    _raw_library(ws, good, '{"schema": "seed/1", "seed_id": "2026-11-04_beauty:t3", "cut sh')
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t3")    # the wanted seed is on the damaged line
    assert code == 1 and out["status"] == "error" and "line 2" in out["message"]
    assert "run tm run new again" in out["message"] and "continues from the same place" not in out["message"]
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t9")    # another unknown id
    assert code == 1 and "Lines 2" in out["message"] and "2026-11-04_beauty:t1" in out["message"]
    assert not (ws / "runs" / CREATIVE_BRIEF).exists()
    code, out = _new(capsys, "--seed", "2026-11-04_beauty:t1")    # a readable seed still starts a run
    assert code == 0, out


def test_unknown_seed_lists_valid_ones(ws, bundled_skills, capsys):
    seeds.add(ws, _seed())
    seeds.add(ws, _seed(seed_id="2026-11-04_beauty:t2", trend_id="t2"))
    seeds.add(ws, _seed(seed_id="pb5:x", source="pb5"))      # another playbook's seed is not offered
    code, out = _new(capsys, "--seed", "pb5:x")
    assert code == 1 and out["status"] == "error"
    assert "pb5:x" in out["message"]
    assert "2026-11-04_beauty:t1" in out["message"] and "2026-11-04_beauty:t2" in out["message"]
    assert not (ws / "runs" / CREATIVE_BRIEF).exists()      # nothing was started

    code, out = _new(capsys, "--seed", "")
    assert code == 1

    capsys.readouterr()
    assert main(["run", "new", "--playbook", "trend-research", "--name", "t", "--seed",
                 "2026-11-04_beauty:t1", "--json"]) == 1
    assert "--seed" in json.loads(capsys.readouterr().out)["message"]
    assert not (ws / "runs" / "04-trend-research").exists()


def test_unknown_seed_with_no_seeds_says_so(ws, bundled_skills, capsys):
    code, out = _new(capsys, "--seed", "nope")
    assert code == 1 and "tm seeds list --source pb4" in out["message"]


def test_intake_gap_names_missing_landing_and_brand(ws, run):
    brief_config.write_from_intake(run, BASE)
    gap = brief_config.intake_gap(run)
    assert "brand.profile" in gap and "00_raw/landing_" in gap
    assert "account.currency" in gap                  # CB13's rate check cannot be skipped by leaving it blank

    saved = brand.save(ws, PROFILE, run=None).relative_to(ws).as_posix()
    (run.path / "00_raw" / "landing_example.md").write_text("A linen duvet.", encoding="utf-8")
    brief_config.write_from_intake(run, {**BASE, "brand": {"profile": saved}})
    assert brief_config.intake_gap(run) == "account.currency holds the ad account's currency (from ads_get_ad_accounts)"
    BASE_USD = {**BASE, "account": {**BASE["account"], "currency": "USD"}}
    brief_config.write_from_intake(run, {**BASE_USD, "brand": {"profile": saved}})
    assert brief_config.intake_gap(run) is None

    bad = ws / "library" / "brands" / "night-school" / "brand_v09.json"
    bad.write_text(json.dumps({**PROFILE, "tone": ["warm"]}), encoding="utf-8")
    brief_config.write_from_intake(run, {**BASE, "brand": {"profile": bad.relative_to(ws).as_posix()}})
    assert "tone" in brief_config.intake_gap(run)
    for elsewhere in ("../outside.json", "library/seeds.jsonl", "library/brands/none/brand_v01.json"):
        brief_config.write_from_intake(run, {**BASE, "brand": {"profile": elsewhere}})
        assert "brand.profile" in brief_config.intake_gap(run)
    assert "does not exist" in brief_config.intake_gap(run)
    brief_config.write_from_intake(run, {**BASE, "brand": {"profile": "library/brands/night-school"}})
    assert "cannot be read" in brief_config.intake_gap(run)   # a folder, not a missing file

    brief_config.write_from_intake(run, {**BASE, "brand": {"profile": saved}, "outputs": ["review_pack"]})
    assert "tm config check" in brief_config.intake_gap(run)


def test_intake_closed_after_a1(run):
    s = state.load(run)
    s.step = "B1"
    state.save(run, s)
    with pytest.raises(ValueError, match="already done"):
        brief_config.write_from_intake(run, BASE)


def test_tm_config_writes_and_checks_a_brief_run(run, tmp_path, capsys):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({**BASE, "level": "every_step"}), encoding="utf-8")
    assert main(["config", "write", "--run", str(run.path), "--answers", str(answers), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "done", "problems": []}
    assert main(["config", "write", "--run", str(run.path), "--from-previous", "--json"]) == 1
    assert "Creative brief writes its config from the intake answers" in json.loads(capsys.readouterr().out)["message"]
