"""Issue #115, section 6: the checks after the change, one test each."""

import copy
import json
from datetime import date
from pathlib import Path

import pytest

import tm.tools as tools
from tm import config, model_registry, organic_config, state
from tm.organic_pages import models
from tm.playbooks import CREATE_AD, REFRESH_AD
from tm.runfolder import RunFolder
from tm.tools import elevenlabs

REPO = Path(__file__).resolve().parents[2]
TEXT = {".py", ".md", ".yaml", ".yml", ".json", ".txt", ".js", ".ts", ".tsx", ".mjs", ".html", ".css", ".sh", ".ps1",
        ".toml"}


def _texts(*roots):
    for root in roots:
        for path in (REPO / root).rglob("*"):
            if path.is_file() and path.suffix in TEXT and "node_modules" not in path.parts and not path.is_symlink():
                yield path


def test_seedance_1_5_pro_appears_nowhere():
    gone = "seedance-1." + "5-pro"                    # gone from Replicate (written so, this file holds no copy)
    found = [p.relative_to(REPO).as_posix() for p in _texts("plugins", "tests", ".github")
             if gone in p.read_text(encoding="utf-8", errors="ignore")]
    assert found == []


@pytest.mark.parametrize("inputs, ok", [({"resolution": "768P"}, True), ({"resolution": "2K"}, True),
                                        ({}, False), ({"resolution": "1080p"}, False)])
def test_every_h3_call_sends_768p_unless_the_user_chose_2k(inputs, ok):
    assert (model_registry.send_problems("minimax/h3", inputs) == []) is ok
    assert model_registry.star("image_to_video")["send"] == {"resolution": "768P"}
    assert model_registry.route("talking_person")["situations"]["specific_person"]["variant"] == "768P"


def test_sound_effects_send_their_model_id():
    assert elevenlabs.SFX_MODEL["send"] == {"model_id": "eleven_text_to_sound_v3"}
    assert "eleven_text_to_sound_v2" in {e["id"] for e in model_registry.left_out()}   # never offered: deprecated


def test_topaz_is_priced_per_replicates_real_unit(tmp_path):
    price = model_registry.price("topazlabs/video-upscale", "1080p")
    assert (price["usd"], price["per"]) == (0.0186, "second")          # ~$0.019/s at 1080p, 30 fps
    f = tmp_path / "prices.json"
    f.write_text(json.dumps([{"model": "topazlabs/video-upscale", "checked": "2026-11-17",
                              "tiers": [{"criteria": "all", "price": "$0.08", "unit": "unit"}]}]), encoding="utf-8")
    assert round(model_registry.live_price(f, "topazlabs/video-upscale", "1080p")[0], 4) == 0.0186
    readme = (REPO / "plugins/trendsmesh-playbooks/references/model-prompting/README.md").read_text(encoding="utf-8")
    assert "$0.08 per unit" not in readme


def test_no_gpt_image_call_is_sent_with_quality_auto():
    gpt = [m for m in model_registry.ids() if m.startswith("openai/gpt-image-")]
    assert len(gpt) == 5
    for model in gpt:
        for name, var in model_registry.variants(model).items():
            assert var["send"]["quality"] in ("low", "medium", "high"), (model, name)
        assert model_registry.send_problems(model, {"quality": "auto"})
        assert model_registry.send_problems(model, {})
        assert model_registry.send_problems(model, {"quality": "medium"}) == []


def _spec(run, name, spec):
    path = run.path / "03_wip" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("playbook", [REFRESH_AD, CREATE_AD])
def test_every_playbooks_replicate_call_sends_its_variant(tmp_path, playbook, monkeypatch):
    run = RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 17), playbook=playbook)
    monkeypatch.setitem(tools.PRECHECK, playbook, {})              # the playbook's own rules apart
    auto = _spec(run, "frame", {"model": "openai/gpt-image-2", "input": {"prompt": "x", "quality": "auto"}})
    said = tools._precheck(run, "replicate_run", [auto, "--name", "frame", "--cost", "0.05", "--run", str(run.path)])
    assert said and 'never "auto"' in said and "Nothing was run or spent" in said
    h3 = _spec(run, "take", {"model": "minimax/h3", "input": {"prompt": "x"}})
    said = tools._precheck(run, "replicate_run", [h3, "--name", "take", "--cost", "1.2", "--run", str(run.path)])
    assert said and '768P: {"resolution": "768P"}' in said
    ok = _spec(run, "take2", {"model": "minimax/h3", "input": {"prompt": "x", "resolution": "2K"}})
    assert tools._precheck(run, "replicate_run", [ok, "--name", "take2", "--cost", "2", "--run", str(run.path)]) is None
    other = _spec(run, "other", {"model": "acme/not-in-the-registry", "input": {}})    # the user's own model
    assert tools._precheck(run, "replicate_run", [other, "--name", "o", "--cost", "1", "--run", str(run.path)]) is None


def _priced(run, tasks):
    rows = []
    for model in models.price_ids(tasks):
        rows.append({"model": model, "checked": date.today().isoformat(), "tiers": [
            {"criteria": v["live"]["criteria"], "price": f"${v['price']['usd'] / v['live'].get('factor', 1):g}",
             "unit": "x"} for v in model_registry.variants(model).values() if v.get("live")]})
    path = run.path / "02_research" / "models" / f"prices_{date.today().isoformat()}_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_a_models_page_lists_the_registrys_models_and_no_new_one(tmp_path, monkeypatch):
    run = RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 17), playbook=CREATE_AD)
    tasks = [t for t in model_registry.tasks() if model_registry.active(t)]
    _priced(run, tasks)
    data = models.tasks_page_json(run, tasks, {"images": 2, "video_seconds": 15, "characters": 300})
    for task in tasks:
        shown = [(e["model"] or "none-upscale", e["variant"]) for e in data["plugin"][task].values()]
        assert shown == [(r["model"], r["variant"]) for r in model_registry.active(task)], task
    reg = copy.deepcopy(model_registry.load())
    reg["models"].append({**copy.deepcopy(next(m for m in reg["models"] if m["id"] == "minimax/h3")),
                          "id": "acme/new-video", "status": "new", "name": "Acme New Video"})
    for m in reg["models"]:
        for entries in (m.get("tasks") or {}).values():
            for e in entries:
                e.pop("star", None) if m["id"] == "acme/new-video" else None
    monkeypatch.setattr(model_registry, "load", lambda: reg)
    data = models.tasks_page_json(run, ["image_to_video"], {"video_seconds": 15})
    assert "Acme New Video" not in json.dumps(data)


def test_create_ad_and_refresh_ad_get_the_models_page_through_tm_models(tmp_path, capsys):
    from tm.cli import main

    run = RunFolder.create(tmp_path / "ws", "x", date(2026, 11, 17), playbook=REFRESH_AD)
    _priced(run, ["photos", "image_to_video"])
    capsys.readouterr()
    code = main(["models", "page", "--run", str(run.path), "--task", "photos", "--task", "image_to_video", "--units",
                 '{"images": 1, "video_seconds": 8}', "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and (run.path / out["folder"] / "index.html").is_file(), out
    html = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<span class="pill dark">Refresh an ad</span>' in html and "Organic AI video" not in html   # #156
    code = main(["models", "decisions", "--run", str(run.path), "--by-rule", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    picked = models.chosen(run)
    assert (picked["photos"]["model"], picked["photos"]["variant"]) == ("openai/gpt-image-2", "medium")
    assert (picked["image_to_video"]["model"], picked["image_to_video"]["send"]) == ("minimax/h3", {"resolution": "768P"})
    assert picked["total_usd"] == pytest.approx(0.047 + 8 * 0.08)
