"""Create an ad (playbook 05): its registration, config.yaml from the S0 intake, its checks, the asset inventory and
the `ad_intake_written` step check; the doctor's rows; the guess-mode notice."""

import json
from datetime import date

import pytest

from tm import create_config, doctor, evidence, flow, i18n, playbooks, state, stepchecks
from tm.cli import main
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder

from test_doctor import ids, item, world  # noqa: F401  (world: autouse fixture)

ANSWERS = {
    "level": "every_step",
    "languages": {"working": "pl", "market": "en"},
    "brand": {"product": "Example Planner", "url": "https://planner.example.com",
              "persona": {"who": "freelance designers", "makes": "brand identities for small shops"}},
    "intake": {"sells": {"kind": "feature", "what": "the client brief generator"}, "length_s": [15, 20],
               "placements": ["reels", "stories"], "live": True},
}
INVENTORY = {"earlier_runs_checked": True,
             "assets": [{"file": "00_raw/logo.svg", "kind": "logo", "usable": True, "replaces": None},
                        {"file": "00_raw/vo.wav", "kind": "voiceover", "usable": True, "replaces": "voice"}]}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "workspace"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


@pytest.fixture
def run(ws):
    return RunFolder.create(ws, "planner", date(2026, 11, 11), playbook=CREATE_AD)


def _write(run, rel, data):
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _answers(**over):
    out = json.loads(json.dumps(ANSWERS))
    for path, value in over.items():
        node = out
        *parents, last = path.split(".")
        for p in parents:
            node = node.setdefault(p, {})
        node[last] = value
    return out


def _fields(run):
    return {p.field for p in create_config.validate(run)}


def test_create_ad_is_registered_and_bundled():
    pb = playbooks.offered("create-ad")
    assert (pb.id, pb.name, pb.skill, pb.guess, pb.budgets) == (
        CREATE_AD, "Create an ad", "create-ad", True, ("ai_usd", "voice_credits"))
    assert flow.output_ids(CREATE_AD) == ["video_ad"]


def test_the_intake_writes_a_valid_config(run):
    create_config.write_from_intake(run, _answers())
    assert create_config.validate(run) == []
    s = state.load(run)
    assert (s.level, s.outputs) == ("every_step", ["video_ad"])
    cfg = create_config.load(run)
    assert cfg["mode"] == "hitl" and cfg["copy"]["primary_max"] == 125 and cfg["take"]["words_max"] == 45
    assert cfg["budget"]["daily_ad_spend"] is None   # never a default (CA14)
    assert not s.budgets                              # nothing approved outside Hands-off


@pytest.mark.parametrize("path,value,field", [
    ("brand.persona.makes", None, "brand.persona.makes"),          # CA1: the persona includes what they make
    ("intake.sells.kind", "everything", "intake.sells.kind"),
    ("intake.length_s", [30, 15], "intake.length_s"),              # length is a decision, low before high
    ("intake.placements", ["tiktok"], "intake.placements"),
    ("intake.live", None, "intake.live"),
    ("brand.url", "planner.example.com", "brand.url"),
    ("generation.provider", "fal", "generation.provider"),
    ("models.voice_clone", "x", "models.voice_clone"),
])
def test_the_intake_refuses_what_is_missing_or_wrong(run, path, value, field):
    create_config.write_from_intake(run, _answers(**{path: value}))
    assert field in _fields(run)


def test_not_live_needs_what_it_is(run):
    create_config.write_from_intake(run, _answers(**{"intake.live": False}))
    assert "intake.not_live" in _fields(run)
    create_config.write_from_intake(run, _answers(**{"intake.live": False, "intake.not_live": "a waitlist"}))
    assert create_config.validate(run) == []


def test_hands_off_spends_only_the_intake_budget(run):
    create_config.write_from_intake(run, _answers(level="hands_off"))
    assert "budget.generation_usd" in _fields(run)
    create_config.write_from_intake(run, _answers(level="hands_off", **{"budget.generation_usd": 12,
                                                                        "budget.daily_ad_spend": 20}))
    s = state.load(run)
    assert create_config.load(run)["mode"] == "auto"
    assert s.budgets == {"ai_usd": 12.0}             # the ad spend is never approved here
    assert s.approvals[0]["note"] == "the budget given at intake (Hands-off)"


def test_a_non_usd_account_needs_its_rate(run):
    create_config.write_from_intake(run, _answers(currency="PLN"))
    assert "fx_rate" in _fields(run)


def test_the_intake_is_written_once(run):
    create_config.write_from_intake(run, _answers())
    s = state.load(run)
    s.step = "S1"
    state.save(run, s)
    with pytest.raises(ValueError, match="already done"):
        create_config.write_from_intake(run, _answers())


def test_s0_needs_the_config_and_the_asset_inventory(run, capsys):
    gap = stepchecks.run("ad_intake_written", run)
    assert "config.yaml passes tm config check" in gap and "asset inventory" in gap
    _write(run, "answers.json", _answers())
    assert main(["config", "write", "--run", str(run.path), "--answers", "answers.json", "--json"]) == 0
    capsys.readouterr()
    assert "assets_vNN.json" in stepchecks.run("ad_intake_written", run)
    _write(run, "03_wip/assets_v01.json", {**INVENTORY, "earlier_runs_checked": False})
    assert "earlier_runs_checked" in stepchecks.run("ad_intake_written", run)   # earlier runs are always asked
    _write(run, "03_wip/assets_v02.json", {**INVENTORY, "assets": [
        {"file": "00_raw/old.mp4", "kind": "past_ad", "usable": False, "replaces": "presenter"}]})
    assert "only when usable" in stepchecks.run("ad_intake_written", run)
    _write(run, "03_wip/assets_v03.json", INVENTORY)
    assert stepchecks.run("ad_intake_written", run) is None


def test_the_doctor_warns_without_trendsmesh_and_meta():
    r = doctor.check({"video_ad"}, False, {"trendsmesh": "missing", "meta": "missing", "artifacts": "missing"},
                     playbook="create-ad")
    assert r.ready
    for row in ("mcp_trendsmesh_create", "mcp_meta_create", "artifacts_pages_create",
                "replicate_api_token_create", "elevenlabs_api_key_create"):
        assert row in ids(r)
    assert item(r, "mcp_trendsmesh_create").warn and item(r, "mcp_meta_create").warn
    assert "best guess" in item(r, "mcp_trendsmesh_create").note
    assert "paused ad" in item(r, "mcp_meta_create").note
    assert {"tier_base", "tier_ai", "tier_video", "tier_voice", "tier_breakdown"} <= set(ids(r))


def test_the_guess_notice_comes_with_the_concept():
    s = state.RunState(run_id="x", playbook=CREATE_AD, created="2026-11-11", evidence=evidence.GUESS)
    text = evidence.notice_for(s, ["concept"])
    assert text and "best guess" in text and "Ad Library" in text
    assert evidence.notice_for(s, ["plan"]) is None


def test_the_ad_languages_are_the_runs_two(run):
    create_config.write_from_intake(run, _answers())
    assert i18n.run_languages(run) == i18n.Languages("pl", "en")   # cards in Polish, the ad in English
    create_config.write_from_intake(run, _answers(languages={"market": "de"}))
    assert create_config.load(run)["languages"] == {"working": "de", "market": "de"}   # the one left out is the other
    create_config.write_from_intake(run, _answers(languages={"working": "the boss reads it", "market": "en"}))
    assert "languages.working" in _fields(run)                     # a language, or nothing
    create_config.write_from_intake(run, _answers(languages=None))
    assert "languages" in _fields(run)                             # asked on the intake card, never a silent English


def test_every_ad_string_is_read_and_every_key_read_is_in_the_table():
    import re
    from pathlib import Path
    src = Path(create_config.__file__).parent
    code = "".join((src / f).read_text(encoding="utf-8") for f in ("create_copy.py", "create_upload.py",
                                                                    "create_qa.py"))
    read = set(re.findall(r'"(ad\.[a-z_]+\.[a-z_]+)"', code))
    read |= {f"ad.upload.created_{how}" for how in ("paused", "draft")}   # read by the outcome's created_as
    from tm import create_qa
    read |= {f"ad.qa.check_{k}" for k in create_qa.EDIT_CHECKS} | {f"ad.qa.result_{r}" for r in create_qa.RESULTS}
    read = (read - {"ad.qa.finding_cuts"}) | {"ad.qa.finding_cuts.one", "ad.qa.finding_cuts.other"}   # a count
    # ad.page.* are the run page's words, read by tm.run_page.create_ad (test_run_page_create_ad checks them)
    table = {k for k in i18n.english() if k.startswith("ad.") and not k.startswith("ad.page.")}
    assert sorted(read - table) == [] and sorted(table - read) == []
    for key in table:
        assert i18n.t(key, **{p: "x" for p in i18n.placeholders(i18n.english()[key])}).strip()
