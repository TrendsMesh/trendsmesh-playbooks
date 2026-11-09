"""The recipe and the generation pack (organic video D1 to E2): `organic_pack.check` on packs typed from
the handoff's examples (ExampleEdu M5 in Polish, the pet store's P4 host and P3 sections), broken one rule at a
time; `tm organic pack check`, its Markdown and the money it plans; the step checks; the kit's context
from the checked pack."""

import copy
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

import exampleedu
import petstore
from tm import config, flow, kit, organic, organic_pack, state, stepchecks
from tm.cli import main
from tm.organic_config import ISSUES
from tm.stops import Stop

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "organic"
TODAY = date(2026, 11, 7)
PLUGIN_RECIPES = organic_pack.RECIPES   # the plugin's references/model-prompting/ (Task 18)
TEMPLATE = exampleedu.REPO / "plugins" / "trendsmesh-playbooks" / "skills" / "organic-video" / "templates" / "pack_template.md"


@pytest.fixture(autouse=True)
def recipes(monkeypatch, tmp_path):
    """A copy of the plugin's model recipes (references/model-prompting/) stands in for them, so a test may add
    one or take one away."""
    folder = tmp_path / "recipes"
    shutil.copytree(PLUGIN_RECIPES, folder)
    monkeypatch.setattr(organic_pack, "RECIPES", folder)
    return folder


def _pack(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _production(run, proposal, channel, *, outputs=("organic_video",), elevenlabs="ok"):
    """Make the run a production run of `proposal` for `channel`, as tm organic start leaves it, with the
    stack D1 records."""
    cfg = config.load(run)
    cfg.update({"kind": "production", "output": "ai_video", "channels": [channel]})
    config.save(run, cfg)
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)
    organic.record_stack(run, replicate="ok", elevenlabs=elevenlabs, artifacts="ok", browser="ok")
    s = state.load(run)
    s.organic = {**s.organic, "proposal": proposal["id"], "channel": channel}
    state.save(run, s)
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps({"proposal": proposal, "channel": channel}),
                                                       encoding="utf-8")
    return run


def _m5_run(tmp_path, **kw):
    run = exampleedu.build(tmp_path / "ws")
    petstore.save_prices(run)
    m5 = next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m5")
    return _production(run, m5, exampleedu.CHANNEL, **kw)


def _pet_run(tmp_path, pid):
    (tmp_path / "ws").mkdir(exist_ok=True)
    run = petstore.build(tmp_path / "ws")
    p = petstore.proposal(pid)
    return _production(run, p, petstore.KEYS[p["channel"]])


def _set(run, **values):
    cfg = config.load(run)
    for path, value in values.items():
        node = cfg
        *parents, last = path.split("__")
        for key in parents:
            node = node[key]
        node[last] = value
    config.save(run, cfg)


def _check(run, pack, stage="pack", today=TODAY):
    return organic_pack.check(run, pack, config.load(run), stage=stage, today=today)


def _fields(problems):
    return [p.field for p in problems]


def _what(problems):
    return " | ".join(f"{p.field}: {p.what} {p.todo}" for p in problems)


def _write(run, pack, n=1):
    rel = f"03_wip/pack_v{n:02d}.json"
    (run.path / rel).write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return rel


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _swap_video_model(pack, model):
    pack["sections"][0]["model"] = model
    pack["stages"][1]["items"][0]["model"] = model
    pack["models"][1]["model"] = model


# --- the examples pass ---------------------------------------------------------------------------

@pytest.mark.private_data
def test_m5_pack_passes_and_plans_1_30(tmp_path, capsys):
    """ExampleEdu's M5 PL pack, its take sized as D1 says (33 words at about 2.9 words a second, 1.5 s after the last
    line: 13 s; the walkthrough's 15 s take came out slow, Task 21 fix round 2): $0.26 + $1.04 = $1.30."""
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    assert _check(run, pack, stage="recipe") == []
    assert _check(run, pack) == []
    rel = _write(run, pack)
    before = flow._now()
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "pack",
                     "--today", "2026-11-07")
    assert (code, out["status"], out["md"]) == (0, "done", "03_wip/pack_v01.md"), out
    s = state.load(run)
    assert set(s.planned) == {"ai_usd", "voice_credits"}
    assert abs(s.planned["ai_usd"] - 1.30) < 1e-9 and s.planned["voice_credits"] == 0
    assert s.planned_at >= before and flow._utc(s.planned_at).tzinfo is not None
    assert "$1.30" in out["message"] and "Approve the generation pack and its cost" in out["message"]
    md = (run.path / "03_wip" / "pack_v01.md").read_text(encoding="utf-8")
    assert md.startswith("# M5, paczka v01: “Mało kto wie, że Fortnite ma PEGI 12”")
    assert "## Koszt" in md and "**$1.30**" in md
    assert stepchecks.run("pack_checked", run) is None


@pytest.mark.private_data
@pytest.mark.parametrize("pid,fixture,total", [("p4", "p4_host_pack.json", 1.21), ("p3", "p3_sections_pack.json", 1.13)])
def test_pet_store_packs_pass(tmp_path, animatic_ready, pid, fixture, total):
    run = _pet_run(tmp_path, pid)
    pack = _pack(fixture)
    assert pack["product"]["packshots"] == ([petstore.packshot(tmp_path / "ws", "lick mat")] if pid == "p4" else [])
    assert _check(run, pack) == [], _what(_check(run, pack))
    assert abs(pack["cost"]["totals"]["ai_usd"] - total) < 1e-9


# --- cost and prices -----------------------------------------------------------------------------

@pytest.mark.private_data
def test_old_price_file_refused(tmp_path):
    run = _m5_run(tmp_path)
    problems = _check(run, _pack("m5_pl_pack.json"), today=date(2026, 11, 14))
    stale = [p for p in problems if p.field.endswith(".price_file")]
    assert [p.field for p in stale] == ["cost.lines[0].price_file", "cost.lines[1].price_file"]
    assert "checked on 2026-11-06, more than 7 days before 2026-11-14" in stale[1].what
    assert "tm tool replicate_price --run runs/03-organic-ai-video/" in stale[1].todo and "minimax/h3" in stale[1].todo
    assert {"models[0].ranking.date", "models[1].ranking.date"} <= set(_fields(problems))   # the ranking too


@pytest.mark.private_data
def test_price_or_ranking_dated_after_today_refused(tmp_path):
    run = _m5_run(tmp_path)
    problems = _check(run, _pack("m5_pl_pack.json"), today=date(2026, 11, 5))
    assert _fields(problems) == ["models[0].ranking.date", "models[1].ranking.date", "cost.lines[1].price_file"]
    assert "dated 2026-11-06, after today (2026-11-05): the date is wrong" in problems[2].what
    assert "more than" not in problems[2].what


@pytest.mark.private_data
def test_voice_credits_are_the_said_characters(tmp_path, animatic_ready):
    run = _pet_run(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["cost"]["lines"][2].update({"units": 300, "cost": 300})
    pack["cost"]["totals"]["voice_credits"] = 300
    problems = _check(run, pack)
    assert _fields(problems) == ["cost.lines"] and "price 300 characters, and the lines said hold 311" in problems[0].what
    pack = _pack("p3_sections_pack.json")
    pack["speech"]["route"] = "h3_narrator"
    assert _fields(_check(run, pack)) == ["cost.lines[2].kind"]   # no ElevenLabs, no credits


@pytest.mark.private_data
def test_cost_line_math_checked(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["lines"][1]["cost"] = 1.1
    assert _fields(_check(run, pack)) == ["cost.lines[1].cost", "resolution.options", "cost.totals.ai_usd"]
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["totals"]["ai_usd"] = 1.5
    assert _fields(_check(run, pack)) == ["cost.totals.ai_usd"]
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["lines"][1].update({"unit_price": 0.07, "cost": 0.91})
    pack["cost"]["totals"]["ai_usd"] = 1.17
    problems = _check(run, pack)
    assert _fields(problems) == ["cost.lines[1].unit_price", "resolution.options"]
    assert "at 0.08 per second of output video" in problems[0].what
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["lines"][1]["checked"] = "2026-11-07"
    assert _fields(_check(run, pack)) == ["cost.lines[1].checked"]
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["lines"][1]["criteria"] = "target resolution=1080p"
    problems = _check(run, pack)   # no such H3 tier, and not the chosen 768p
    assert _fields(problems) == ["cost.lines[1].criteria"] * 2 and "target resolution=768P" in problems[0].what
    assert "is made at 768p (the chosen resolution 768p)" in problems[1].what
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["lines"][1]["price_file"] = "../../outside.json"
    assert _fields(_check(run, pack)) == ["cost.lines[1].price_file"]


def _m5_at_1080p():
    """M5 at 1080p: its 13 s take priced at H3's 2K tier, $1.69, so $1.95 in all."""
    pack = _pack("m5_pl_pack.json")
    pack["resolution"]["choice"] = "1080p"
    pack["cost"]["lines"][1].update({"criteria": "target resolution=2K", "unit_price": 0.13, "cost": 1.69})
    pack["cost"]["totals"]["ai_usd"] = 1.95
    return pack


@pytest.mark.private_data
def test_over_budget_refused_names_cheaper_options(tmp_path):
    run = _m5_run(tmp_path)
    _set(run, budget__per_run_usd=1.9)
    problems = _check(run, _m5_at_1080p())
    assert _fields(problems) == ["cost.totals.ai_usd"]
    assert "costs $1.95, over the run's budget of $1.90" in problems[0].what
    for cheaper in ("resolution 768p ($1.04)", "resolution 768p_pruna ($1.30)", "a shorter script",
                    "a script to film instead ($0)"):
        assert cheaper in problems[0].todo
    assert "tier" not in problems[0].todo   # the host image fixes the model: no other tier passes
    _set(run, budget__per_run_usd=1.95)
    assert _check(run, _m5_at_1080p()) == []   # at the budget is within it


@pytest.mark.private_data
def test_cheaper_tiers_only_where_they_pass(tmp_path, animatic_ready):
    run = _pet_run(tmp_path, "p3")
    _set(run, budget__per_run_usd=1.0)
    pack = _pack("p3_sections_pack.json")
    problems = _check(run, pack)
    assert _fields(problems) == ["cost.totals.ai_usd"]
    assert "the budget tier (bytedance/seedance-1.5-pro)" in problems[0].todo and "resolution" not in problems[0].todo
    pack["sound_led"] = True
    assert "tier" not in _check(run, pack)[0].todo   # sound-led: never the budget tier


@pytest.mark.private_data
def test_cost_lines_tied_to_the_generated_items(tmp_path):
    """The reviewer's probes: a total that leaves out a take, or prices a 1080p choice at 768P, is refused."""
    run = _pet_run(tmp_path, "p4")
    pack = _pack("p4_host_pack.json")
    del pack["cost"]["lines"][1]
    pack["cost"]["totals"]["ai_usd"] = 0.09
    problems = _check(run, pack)
    assert "take (minimax/h3) is generated and has no cost line." in _what(problems)
    pack = _pack("p4_host_pack.json")
    pack["resolution"]["choice"] = "1080p"
    problems = _check(run, pack)
    assert _fields(problems) == ["cost.lines[1].criteria", "resolution.options"]
    assert "priced at 768P, and take is made at 1080p" in problems[0].what
    pack = _pack("p4_host_pack.json")
    pack["cost"]["lines"][0]["units"] = 1
    pack["cost"]["lines"][0]["cost"] = 0.05
    pack["cost"]["totals"]["ai_usd"] = 1.17
    problems = _check(run, pack)
    assert _fields(problems) == ["cost.lines[0].units"] and "host makes 2 images" in problems[0].what
    pack = _pack("p4_host_pack.json")
    pack["cost"]["lines"][1]["item"] = "b-roll"
    assert {"cost.lines[1].item", "cost.lines"} <= set(_fields(_check(run, pack)))
    pack = _pack("p4_host_pack.json")
    del pack["stages"][1]["items"][0]["seconds"]
    assert "stages[1].items[0].seconds" in _fields(_check(run, pack))
    pack = _pack("p4_host_pack.json")
    pack["cost"]["lines"].append({**pack["cost"]["lines"][1], "units": -5, "cost": -0.4})
    pack["cost"]["totals"]["ai_usd"] = 0.81
    problems = _check(run, pack)
    assert problems and problems[0].field == "cost.lines[2].units" and "must be above 0" in problems[0].what


@pytest.mark.private_data
def test_upscale_option_needs_its_upscale_item(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["resolution"]["choice"] = "768p_pruna"
    assert "no upscale stage item" in _what(_check(run, pack))
    pack["stages"].append({"stage": "upscale", "items": [{"name": "upscale", "model": "prunaai/p-video-upscale",
                                                          "seconds": 13}]})
    pack["models"].append({"component": "upscale to 1080p", "model": "prunaai/p-video-upscale", "why": "OV8's default",
                           "recipe": "references/model-prompting/p-video-upscale.md",
                           "ranking": {"source": "Replicate collection", "date": "2026-11-06"},
                           "user_named": False, "criteria": None})
    pack["cost"]["lines"].append({"what": "Pruna 1080p, 13 s", "item": "upscale", "model": "prunaai/p-video-upscale",
                                  "criteria": "model variant=up_to_30fps, target resolution=1080p", "unit_price": 0.02,
                                  "unit": "second of output video", "units": 13, "cost": 0.26, "kind": "ai_usd",
                                  "price_file": "02_research/models/prices_2026-11-06_v03.json", "checked": "2026-11-06"})
    pack["cost"]["totals"]["ai_usd"] = 1.56
    assert _check(run, pack) == []   # the option's $1.30 is the take's $1.04 and the upscale's $0.26
    pack["resolution"]["choice"] = "768p"
    assert "upscale upscales, and the chosen resolution 768p does not" in _what(_check(run, pack))


@pytest.mark.private_data
def test_pack_in_usd_with_rate_for_pln_account(tmp_path):
    run = _m5_run(tmp_path)
    _set(run, currency="PLN")
    problems = _check(run, _pack("m5_pl_pack.json"))
    assert _fields(problems) == ["cost.currency_note"] and "no fx_rate" in problems[0].what
    _set(run, fx_rate=3.65)
    problems = _check(run, _pack("m5_pl_pack.json"))
    assert _fields(problems) == ["cost.currency_note"] and '"1 USD = 3.65 PLN"' in problems[0].todo
    pack = _pack("m5_pl_pack.json")
    pack["cost"]["currency_note"] = "1 USD = 3.65 PLN"
    assert _check(run, pack) == []
    pack["cost"]["currency_note"] = "1 USD = 3.9 PLN"
    assert _fields(_check(run, pack)) == ["cost.currency_note"]


# --- models (OV6) -----------------------------------------------------------------------------------

@pytest.mark.private_data
def test_photoreal_host_on_seedance_refused(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    _swap_video_model(pack, "bytedance/seedance-2.0")
    problems = _check(run, pack)
    e005 = [p for p in problems if "E005" in p.what]
    assert [p.field for p in e005] == ["models[1].model"] and "minimax/h3" in e005[0].todo
    pack["models"][1]["user_named"] = True   # the user's naming never lifts the face block
    pack["models"][1]["criteria"] = {k: True for k in organic_pack.CRITERIA}
    assert any("E005" in p.what for p in _check(run, pack))


@pytest.mark.private_data
@pytest.mark.parametrize("tier", ["budget", "top"])
def test_silent_host_image_goes_to_h3_on_any_tier(tmp_path, tier):
    """A host image that says nothing still goes to H3: Seedance (the budget and top tiers) refuses its face."""
    run = _m5_run(tmp_path)
    _set(run, generation__quality_tier=tier)
    pack = _pack("m5_pl_pack.json")
    pack["production"] = pack["sections"][0]["type"] = "ai_footage"
    for line in pack["script"]["lines"]:
        line["speaker"] = "none"
    pack["script"]["words"] = 0
    pack["speech"].update({"route": "none", "voice": None})
    pack["taste"]["voice"] = None
    assert _check(run, pack) == []
    _swap_video_model(pack, organic_pack.TIERS[tier])
    assert "E005" in _what(_check(run, pack))


@pytest.mark.private_data
def test_described_person_goes_to_seedance_2_0(tmp_path):
    run = _pet_run(tmp_path, "p4")
    pack = _pack("p4_host_pack.json")
    pack["host"] = {"kind": "description", "image": None}
    problems = [p for p in _check(run, pack) if p.field == "models[1].model"]
    assert len(problems) == 1 and "a person described in text goes to Seedance 2.0 is bytedance/seedance-2.0" in problems[0].what
    _swap_video_model(pack, "bytedance/seedance-2.0")
    assert "models[1].model" not in _fields(_check(run, pack))


@pytest.mark.private_data
def test_asmr_on_budget_tier_refused(tmp_path, animatic_ready):
    run = _pet_run(tmp_path, "p3")
    _set(run, generation__quality_tier="budget")
    pack = _pack("p3_sections_pack.json")
    for sec in pack["sections"]:
        if sec["model"]:
            sec["model"] = "bytedance/seedance-1.5-pro"
    pack["stages"][1]["items"][0]["model"] = pack["models"][1]["model"] = "bytedance/seedance-1.5-pro"
    assert "models[1].model" not in _fields(_check(run, pack))   # the budget tier's own model
    pack["sound_led"] = True
    problems = [p for p in _check(run, pack) if p.field == "models[1].model"]
    assert len(problems) == 1 and "sound-led" in problems[0].what and "MiniMax H3" in problems[0].todo


@pytest.mark.private_data
def test_tier_model_or_a_user_named_model_with_six_criteria(tmp_path, animatic_ready):
    run = _pet_run(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    for sec in pack["sections"]:
        if sec["model"]:
            sec["model"] = "kwaivgi/kling-v3-omni-video"
    pack["stages"][1]["items"][0]["model"] = pack["models"][1]["model"] = "kwaivgi/kling-v3-omni-video"
    problems = [p for p in _check(run, pack) if p.field == "models[1].model"]
    assert len(problems) == 1 and "the default tier's model is minimax/h3" in problems[0].what
    pack["models"][1]["user_named"] = True
    pack["models"][1]["criteria"] = {**{k: True for k in organic_pack.CRITERIA}, "photoreal_person": "not needed"}
    del pack["models"][1]["criteria"]["live_price"]
    problems = [p for p in _check(run, pack) if p.field.startswith("models[1].")]
    assert _fields(problems) == ["models[1].criteria"] and "live_price" in problems[0].what
    pack["models"][1]["criteria"]["live_price"] = True
    pack["models"][1]["criteria"]["vertical"] = False
    problems = [p for p in _check(run, pack) if p.field == "models[1].criteria"]
    assert len(problems) == 1 and "fails: vertical (9:16)" in problems[0].what


@pytest.mark.private_data
def test_two_video_models_in_one_section_refused(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["stages"][1]["items"].append({"name": "close-up", "model": "bytedance/seedance-2.0", "seconds": 5})
    pack["models"].append({**copy.deepcopy(pack["models"][1]), "model": "bytedance/seedance-2.0"})
    problems = _check(run, pack)
    assert "stages[1].items[1].model" in _fields(problems)
    assert any("one video model per section" in p.what for p in problems)
    pack = _pack("m5_pl_pack.json")
    pack["sections"][0]["model"] = None
    assert "sections[0].model" in _fields(_check(run, pack))


@pytest.mark.private_data
@pytest.mark.parametrize("model,recipe", [("bytedance/seedance-1.5-pro", "seedance-1.5-pro.md"),
                                          ("bytedance/seedance-2.5", "seedance-2.5.md")])
def test_the_budget_and_premium_tiers_have_their_recipes(tmp_path, model, recipe):
    """The queued ruling: the budget and premium tiers' models are never refused with "Write its recipe first"."""
    run = _pet_run(tmp_path, "p4")
    pack = _pack("p4_host_pack.json")
    pack["models"][1].update({"model": model, "recipe": f"references/model-prompting/{recipe}"})
    assert "models[1].recipe" not in _fields(_check(run, pack))
    pack["models"][1]["recipe"] = "references/model-prompting/seedance-9.md"
    assert "models[1].recipe" in _fields(_check(run, pack))


@pytest.mark.private_data
def test_model_without_recipe_refused(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["models"][1]["recipe"] = "references/model-prompting/kling-v3.md"
    problems = _check(run, pack)
    assert _fields(problems) == ["models[1].recipe"] and "Write its recipe first" in problems[0].todo
    for recipe in (None, "resources/model-prompting/minimax-h3.md", "references/model-prompting/../model-prompting/minimax-h3.md"):
        pack["models"][1]["recipe"] = recipe
        assert _fields(_check(run, pack)) == ["models[1].recipe"], recipe


# --- speech (OV7) and resolution (OV8) ------------------------------------------------------------

@pytest.mark.private_data
def test_take_longer_than_15s_not_supported_yet(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["script"]["seconds"] = 20
    pack["sections"][0]["to"] = 20
    problems = _check(run, pack)
    assert _fields(problems) == ["script.seconds"]
    assert "A talking piece longer than one take is not supported yet" in problems[0].what and ISSUES in problems[0].what
    pack = _pack("m5_pl_pack.json")   # 13 s at 3 words a second with 1.5 s after the last line: 34.5 words fit
    pack["script"]["lines"][3]["text"] += " Jeszcze."
    pack["script"]["words"] = 34
    assert _check(run, pack) == []
    pack["script"]["lines"][3]["text"] += " Raz."
    pack["script"]["words"] = 35
    problems = _check(run, pack)
    assert _fields(problems) == ["script.words"] and "at most 34.5 fit" in problems[0].what
    pack["script"]["words"] = 34
    assert "the lines said hold 35 words" in _what(_check(run, pack))


@pytest.mark.private_data
def test_a_slow_take_is_refused_at_the_pack(tmp_path):
    """Task 21 fix round 2 (Task 22's evals): a take that speaks its lines is planned no slower than `qa.wps_min`, the
    take QA's pace, over its speech: the walkthrough's 33 words in a 15 s take (13.5 s of speech, 2.44 words a
    second) are refused before anything is paid; at 13 s (2.87) they pass. The todo names the lengths both pace checks
    pass (r2: 12.5 to 13.2 s, so a 13 s take; 20 words in 10 s fit no whole-second take, so add words). A take that
    speaks, h3_native or a one-take h3_narrator (r3: the take QA measures its pace too), is held to it."""
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["script"]["seconds"] = 15
    problems = [p for p in _check(run, pack) if p.field == "script.words"]
    assert len(problems) == 1
    assert "33 words over 13.5 s of speech" in problems[0].what and "2.44 words a second, under 2.8" in problems[0].what
    assert "come out slow" in problems[0].what and "Add words" in problems[0].todo
    assert "shorten the take to 13 s" in problems[0].todo and "12.5 to 13.2 s" in problems[0].todo
    _set(run, qa__wps_min=2.4)                                   # the take QA's own setting decides
    assert not [p for p in _check(run, pack) if p.field == "script.words"]
    pack["speech"]["route"] = "h3_narrator"                       # r3: one narrator take is measured by the QA too
    _set(run, qa__wps_min=2.8)
    assert "come out slow" in _what([p for p in _check(run, pack) if p.field == "script.words"])
    short = copy.deepcopy(pack)
    short["speech"]["route"] = "h3_native"
    short["script"]["seconds"] = 10
    lines = [line for line in short["script"]["lines"] if line["speaker"] != "none"]
    for line in lines:
        line["text"] = ""
    lines[0]["text"] = " ".join(["słowo"] * 20)
    short["script"]["words"] = 20
    todo = " ".join(p.todo for p in _check(run, short) if "come out slow" in p.what)
    assert "between 8.2 and 8.6 s" in todo and "no whole-second take" in todo and "shorten" not in todo
    pinned = _pack("m5_pl_pack.json")                            # the boundary, over the spoken seconds
    assert pinned["script"]["seconds"] == 13 and pinned["script"]["words"] == 33
    assert _check(run, pinned) == []                             # 33 words over 13 - 1.5 = 11.5 s: 2.87 words a second
    pinned["script"]["seconds"] = 13.5                           # over 12 s: 2.75, under 2.8
    assert "2.75 words a second, under 2.8" in _what(_check(run, pinned))


@pytest.mark.private_data
def test_speech_route_reference_and_elevenlabs(tmp_path):
    run = _m5_run(tmp_path, elevenlabs="unchecked")
    pack = _pack("m5_pl_pack.json")
    pack["speech"]["route"] = "elevenlabs_lipsync"
    fields = _fields(_check(run, pack))
    assert fields.count("speech.route") == 2   # not native without a reason, and no ElevenLabs in the stack
    pack["speech"]["alternative_reason"] = "the user asked for an exact brand voice"
    problems = _check(run, pack)
    assert _fields(problems) == ["speech.route", "cost.lines"] and "needs ElevenLabs" in problems[0].what
    assert "the lines said hold 189" in problems[1].what   # its voice credits are not priced
    pack = _pack("m5_pl_pack.json")
    pack["speech"]["voice_reference"] = {"user_words": "", "sample_s": 15}
    assert _fields(_check(run, pack)) == ["speech.voice_reference", "speech.voice_reference.sample_s"]
    pack["speech"]["voice_reference"] = {"user_words": "Use my own voice sample", "sample_s": 14}
    assert _check(run, pack) == []


@pytest.mark.private_data
def test_resolution_question_has_three_costed_options(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    del pack["resolution"]["options"][2]
    problems = _check(run, pack)
    assert _fields(problems) == ["resolution.options"] and "768p_pruna" in problems[0].what
    pack = _pack("m5_pl_pack.json")
    pack["resolution"]["options"][1]["cost"] = 0
    pack["resolution"]["choice"] = "4k"
    assert _fields(_check(run, pack)) == ["resolution.options[1].cost", "resolution.choice"]
    pack = _pack("m5_pl_pack.json")
    pack["resolution"]["options"][0]["id"], pack["resolution"]["options"][2]["id"] = "720p", "720p_pruna"
    pack["resolution"]["choice"] = "720p"
    assert _check(run, pack) == []   # 720p is the base on a model without 768P
    pack["resolution"] = None
    assert _fields(_check(run, pack)) == ["resolution"]


# --- the recipe (D1) --------------------------------------------------------------------------------

@pytest.mark.private_data
def test_featured_product_needs_packshot(tmp_path):
    run = _pet_run(tmp_path, "p4")
    pack = _pack("p4_host_pack.json")
    shot = pack["product"]["packshots"][0]
    assert _check(run, pack, stage="recipe") == []
    pack["product"]["packshots"] = []
    problems = _check(run, pack, stage="recipe")
    assert _fields(problems) == ["product.packshots"] and "featured" in problems[0].what
    pack["product"]["packshots"] = ["library/brands/brushwell-pets/packshots/paw-balm_v01.png"]
    assert "not a packshot of the channel's store catalogue" in _what(_check(run, pack, stage="recipe"))
    pack["product"]["packshots"] = [shot]
    (tmp_path / "ws" / shot).unlink()
    assert "the file is missing" in _what(_check(run, pack, stage="recipe"))
    pack["product"]["level"] = "soft mention"
    assert _check(run, pack, stage="recipe") == []


@pytest.mark.private_data
def test_recipe_stage_needs_only_the_recipe(tmp_path):
    run = _pet_run(tmp_path, "p4")
    pack = _pack("p4_host_pack.json")
    recipe = copy.deepcopy({k: v for k, v in pack.items() if k not in organic_pack.PACK_KEYS})
    assert _check(run, recipe, stage="recipe") == []
    assert set(_fields(_check(run, recipe))) == set(organic_pack.PACK_KEYS)
    recipe["style_spec"] = None   # P4 recreates its evidence
    problems = _check(run, recipe, stage="recipe")
    assert _fields(problems) == ["style_spec"] and "Recreate" in problems[0].what
    recipe = copy.deepcopy({k: v for k, v in pack.items() if k not in organic_pack.PACK_KEYS})
    recipe["taste"]["style"] = "02 Watercolour Bloom"
    recipe["production"] = "teleport"
    recipe["id"] = "P5"
    assert _fields(_check(run, recipe, stage="recipe")) == ["id", "production", "taste.style"]
    recipe = copy.deepcopy({k: v for k, v in pack.items() if k not in organic_pack.PACK_KEYS})
    for line in recipe["script"]["lines"]:
        line["speaker"] = "none"   # on-screen text only: no voice to pick
    recipe["taste"]["why"] = ""
    assert _fields(_check(run, recipe, stage="recipe")) == ["taste.voice", "taste.why"]
    del recipe["host"]
    problems = _check(run, recipe, stage="recipe")
    assert _fields(problems) == ["pack"] and "lacks host" in problems[0].what
    assert _fields(_check(run, [recipe], stage="recipe")) == ["pack"]


@pytest.mark.private_data
def test_hidden_production_type_refused(tmp_path):
    run = _pet_run(tmp_path, "p3")
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="missing")
    problems = _check(run, _pack("p3_sections_pack.json"), stage="recipe")
    assert _fields(problems) == ["sections[1].type"] and "Chrome or Edge" in problems[0].what
    assert "section 2 is an animation" in problems[0].what.lower() and "animation needs" not in problems[0].what


@pytest.mark.private_data
def test_risk_and_facts(tmp_path):
    run = _m5_run(tmp_path)
    pack = _pack("m5_pl_pack.json")
    pack["risk"]["hits"][0]["mitigation"] = "mniej niż 10% ryzyka"
    pack["risk"]["hits"].append({"item": "aliens", "mitigation": ""})
    pack["facts"][0]["source"] = " "
    assert _fields(_check(run, pack)) == ["facts[0]", "risk.hits[3].item", "risk.hits[3].mitigation", "risk"]


# --- the command, the Markdown, the step checks ------------------------------------------------------

@pytest.mark.private_data
def test_cli_marks_each_stage_and_never_rewrites_the_md(tmp_path, capsys):
    run = _pet_run(tmp_path, "p4")
    assert "tm organic pack check --stage recipe" in stepchecks.run("recipe_written", run)
    rel = _write(run, _pack("p4_host_pack.json"))
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "recipe",
                     "--today", "2026-11-07")
    assert (code, out["status"]) == (0, "done") and state.load(run).planned == {}
    assert stepchecks.run("recipe_written", run) is None and stepchecks.run("pack_checked", run) is not None
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "pack",
                     "--today", "2026-11-07")
    assert (code, out["status"]) == (0, "done") and stepchecks.run("pack_checked", run) is None
    (run.path / "03_wip" / "pack_v01.md").write_text("edited by hand\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "pack",
                     "--today", "2026-11-07")
    assert (code, out["status"]) == (2, "stop") and "never written over" in out["message"]
    planned_at = state.load(run).planned_at
    rel2 = _write(run, _pack("p4_host_pack.json"), 2)
    (run.path / "03_wip" / "pack_v02.md").write_text("written before its pack\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel2, "--stage", "pack",
                     "--today", "2026-11-07")
    assert (code, out["status"]) == (2, "stop")   # stopped: neither marked nor planned
    assert stepchecks.run("pack_checked", run) is not None and state.load(run).planned_at == planned_at
    bad = _pack("p4_host_pack.json")
    bad["cost"]["totals"]["ai_usd"] = 9
    rel3 = _write(run, bad, 3)
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel3, "--stage", "pack",
                     "--today", "2026-11-07")
    assert (code, out["status"]) == (2, "stop") and "cost.totals.ai_usd" in [p["field"] for p in out["problems"]]
    assert stepchecks.run("pack_checked", run) is not None   # the latest pack is not the checked one
    (run.path / "03_wip" / "pack.json").write_text("{}", encoding="utf-8")
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", "03_wip/pack.json",
                     "--stage", "pack")
    assert code == 1 and "pack_vNN.json" in out["message"]


def _pack_cli(capsys, run, rel, stage="pack"):
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", stage,
                     "--today", "2026-11-07")
    assert code == 0, out
    return out


def _budget(capsys, run, amount):
    capsys.readouterr()
    code = main(["budget", "approve", "ai_usd", str(amount), "--run", str(run.path), "--json"])
    out = capsys.readouterr()
    return code, out.out + out.err


def _backdate_yes(run):
    """The plan and the latest decision (the yes on it) moved to an earlier time, so a re-plan in this
    second is later than the yes (a yes in the same second as the plan still counts)."""
    s = state.load(run)
    s.planned_at = s.decisions[-1]["at"] = "2026-11-07T08:00:00+00:00"
    state.save(run, s)


@pytest.mark.private_data
def test_d1_and_e2_wait_for_the_checks_and_a_replanned_pack_needs_a_new_yes(tmp_path, capsys):
    """D1 and E2 require the recipe and the pack checked; the pack check plans the money, the pack yes and
    tm budget approve release F1; a re-check of the same items at no higher total keeps the yes, a higher
    total or other items need tm decide pack approve --change (P3-F1, the controller's ruling); a reject
    skips the paid steps."""
    run = _m5_run(tmp_path)
    flow.set_level(run, "every_step")
    with pytest.raises(Stop, match="tm organic pack check --stage recipe"):
        flow.complete(run, "D1")
    rel = _write(run, _pack("m5_pl_pack.json"))
    _pack_cli(capsys, run, rel, "recipe")
    assert _pack_cli(capsys, run, rel)["replanned"] is True
    for _ in range(10):   # D1 to E2, the taste accepted, until the pack is asked
        nxt = flow.next(run)
        if nxt.action == "work":
            flow.complete(run, nxt.step)
        elif nxt.checkin.ids == ["pack"]:
            break
        else:
            flow.decide(run, nxt.checkin.ids[0], "accept", by="user", note=None)
    assert flow.approval_gap(state.load(run), "ai_usd", None) is not None
    flow.decide(run, "pack", "approve", by="user", note=None)
    assert (nxt := flow.next(run)).step == "F1" and nxt.action == "stop"   # approved at the check-in, not yet in money
    assert _budget(capsys, run, 1.30)[0] == 0
    assert (nxt := flow.next(run)).step == "F1" and nxt.action == "work"   # F1 is no longer held

    _backdate_yes(run)
    out = _pack_cli(capsys, run, rel)   # the same pack again: the yes holds
    assert out["replanned"] is False and "that yes still holds" in out["message"]
    assert flow.approval_gap(state.load(run), "ai_usd", None) is None and flow.next(run).action == "work"

    rel2 = _write(run, _m5_at_1080p(), 2)   # the same items, at a higher total
    out = _pack_cli(capsys, run, rel2)
    assert out["replanned"] is True and "--change" in out["message"]
    assert "--change" in flow.approval_gap(state.load(run), "ai_usd", None)
    assert flow.next(run).action == "stop"   # $1.30 approved, $1.95 planned
    code, text = _budget(capsys, run, 1.95)
    assert code == 1 and "--change" in text
    flow.decide(run, "pack", "approve", by="user", note=None, change=True)
    assert _budget(capsys, run, 1.95)[0] == 0 and flow.next(run).action == "work"

    _backdate_yes(run)
    fewer = _m5_at_1080p()   # other items, at a lower total
    fewer["stages"][0]["items"][0]["images"] = 1
    fewer["cost"]["lines"][0].update({"units": 1, "cost": 0.13})
    fewer["cost"]["totals"]["ai_usd"] = 1.82
    assert _pack_cli(capsys, run, _write(run, fewer, 3))["replanned"] is True
    assert "--change" in flow.approval_gap(state.load(run), "ai_usd", None)

    flow.decide(run, "pack", "reject", by="user", note=None, change=True)
    nxt = flow.next(run)
    assert nxt.step not in ("F1", "F2", "G1", "G2", "G4"), nxt   # nothing generated or paid
    assert flow.approval_gap(state.load(run), "ai_usd", None) is not None


@pytest.mark.private_data
def test_script_to_film_recipe_is_its_script(tmp_path):
    run = _m5_run(tmp_path, outputs=("script_to_film",))
    assert "script_<id>_<lang>_vNN.json" in organic_pack.recipe_gap(run)
    (run.path / "03_wip" / "script_m5_pl_v01.json").write_text("{}", encoding="utf-8")
    assert organic_pack.recipe_gap(run) is None


def test_md_headings_are_the_templates():
    pack = _pack("m5_pl_pack.json")
    template = [ln for ln in TEMPLATE.read_text(encoding="utf-8").replace("\r", "").splitlines() if ln.startswith("## ")]
    template = [ln.replace("<n>", "33").replace("<s>", "13") for ln in template]
    assert [ln for ln in organic_pack.render_md(pack, "en").splitlines() if ln.startswith("## ")] == template
    polish = [ln for ln in organic_pack.render_md(pack, "pl").splitlines() if ln.startswith("## ")]
    assert len(polish) == len(template) and not set(polish) & set(template)


@pytest.mark.private_data
def test_kit_context_reads_the_pack(tmp_path, capsys):
    run = _m5_run(tmp_path)
    with pytest.raises(Stop, match="checked pack"):
        kit.context_of(run)
    rel = _write(run, _pack("m5_pl_pack.json"))
    code, _ = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "pack",
                   "--today", "2026-11-07")
    assert code == 0
    ctx = kit.context_of(run)
    assert (ctx.ai_label, ctx.product_level, ctx.filmed_by_person, ctx.language) == ("required", "not shown", False, "pl")
    assert kit.context_of(run, ai_label="on").ai_label == "on"   # a flag still wins
    p3 = _pack("p3_sections_pack.json")
    assert organic_pack.ai_label(p3) == "on"
    p3["sections"] = [p3["sections"][1]]
    p3["production"] = "animation"
    assert organic_pack.ai_label(p3) == "not_required"


def test_stepchecks_registered():
    assert stepchecks.NAMES["recipe_written"] == "tm.organic_pack:recipe_gap"
    assert stepchecks.NAMES["pack_checked"] == "tm.organic_pack:pack_gap"


# --- the PR C fix wave -----------------------------------------------------------------------------

def _redo_line(pack, item):
    """The pack with one more line for `item`, priced like its own and marked as a redo, in its total."""
    pack = copy.deepcopy(pack)
    line = next(x for x in pack["cost"]["lines"] if x["item"] == item and not x.get("redo"))
    pack["cost"]["lines"].append({**line, "what": f"{line['what']}, redo", "redo": True})
    pack["cost"]["totals"]["ai_usd"] = round(pack["cost"]["totals"]["ai_usd"] + line["cost"], 2)
    return pack


def _asked(run, stem, *afters):
    """The user's redo requests of `stem`, one per take they were asked after (as tm organic redo records them)."""
    s = state.load(run)
    s.organic = {**s.organic, "redos": {stem: [{"kind": "request", "note": "jeszcze raz", "by": "user",
                                                "at": "2026-11-07T10:00:00+00:00", "after": a} for a in afters]}}
    state.save(run, s)


@pytest.mark.private_data
def test_a_requested_redo_is_a_priced_line(tmp_path, capsys):
    """PR C review I4 (the ruling): the pack check accepts one `"redo": true` line per requested redo of an item,
    priced like the item's own line; the total rises, so the yes needs --change."""
    run = _m5_run(tmp_path)
    redo = _redo_line(_pack("m5_pl_pack.json"), "take")
    problems = _check(run, redo)                                  # nobody asked for it
    assert _fields(problems) == ["cost.lines"] and "take has 1 redo line, and the user asked for 0 redos" in \
        problems[0].what
    _asked(run, "take", "take_v01.run.json", "take_v01.run.json")   # two words for one take: one redo
    assert _check(run, redo) == []
    assert "2 redo lines" in _what(_check(run, _redo_line(redo, "take")))
    _asked(run, "take", "take_v01.run.json", "take_v02.run.json")
    assert _check(run, _redo_line(redo, "take")) == []
    cheap = copy.deepcopy(redo)                                   # a redo priced unlike its item
    cheap["cost"]["lines"][-1].update({"units": 5, "cost": 0.4})
    cheap["cost"]["totals"]["ai_usd"] = 1.70
    assert _fields(_check(run, cheap)) == ["cost.lines[2].units"]
    stray = copy.deepcopy(redo)
    stray["cost"]["lines"][-1]["item"] = "broll"
    assert "cost.lines[2].item" in _fields(_check(run, stray))
    voice = copy.deepcopy(redo)
    voice["cost"]["lines"][-1]["kind"] = "voice_credits"
    voice["cost"]["totals"].update({"ai_usd": 1.30, "voice_credits": 1.2})
    assert "cost.lines[2].redo" in _fields(_check(run, voice))
    # through the CLI: the re-check at the higher total resets the plan, so the yes is asked again
    _pack_cli(capsys, run, _write(run, _pack("m5_pl_pack.json")))
    out = _pack_cli(capsys, run, _write(run, redo, 2))
    assert out["replanned"] is True and abs(state.load(run).planned["ai_usd"] - 2.34) < 1e-9
