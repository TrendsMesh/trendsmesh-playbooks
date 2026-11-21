"""Issue #86 and #115: the Models page, after the idea is picked and before the pack: each task's models from the model
registry, priced for this video from today's Replicate prices, the ones that can't work greyed out with the reason,
and the choice E1 starts from. Synthetic runs only (the public M5 pack fixture, prices made from the registry)."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tm import config, mcp_saves, model_registry, organic_config, organic_pack, organic_pages, page, state, \
    trend_spool
from tm.cli import main
from tm.organic_pages import choices, intake, models
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import Stop

FIXTURES = Path(__file__).parent / "fixtures" / "organic"
SLUG = "5e0a1b2c-0000-4000-8000-000000000086"
TODAY = date.today().isoformat()


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _run(tmp_path, *, host="image", route="elevenlabs_narrator") -> tuple[RunFolder, dict]:
    """A run whose page has every section: an upscaling run (generation.upscale pruna) with an ElevenLabs narrator."""
    run = RunFolder.create(tmp_path / "ws", "zorbo", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    cfg = {**organic_config.defaults(), "languages": {"working": "en", "market": "en"}}
    cfg["generation"] = {**cfg["generation"], "upscale": "pruna"}
    config.save(run, cfg)
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["lang"] = "en"
    pack["host"] = {"kind": host, "image": "03_wip/host_v01_0.png" if host == "image" else None}
    pack["speech"]["route"] = route
    for st in pack["stages"]:
        for item in st["items"]:
            item["face"] = host == "image"                    # a frame with a face only with a host image
    path = run.path / "03_wip" / "pack_v01.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="recipe")
    return run, pack


def _prices(run, checked=TODAY, *, drop=(), gone=()):
    """A price file as `tm tool replicate_price` writes it, for every Replicate model the page shows: each registry
    variant's tier at its registry price (as Replicate bills it: Topaz in units, P-Image per 1,000)."""
    rows = []
    for model in models.price_ids(models.ORGANIC.values()):
        if model in drop:
            continue
        if model in gone:
            rows.append({"model": model, "error": "billingConfig not found"})
            continue
        tiers = [{"criteria": v["live"]["criteria"], "price": f"${v['price']['usd'] / v['live'].get('factor', 1):g}",
                  "unit": "second of output video"} for v in model_registry.variants(model).values() if v.get("live")]
        rows.append({"model": model, "checked": checked, "tiers": tiers})
    path = run.path / "02_research" / "models" / f"prices_{checked}_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path.relative_to(run.path).as_posix()


def _options(data, sid):
    return {o["id"]: o for o in next(s for s in data["sections"] if s["id"] == sid)["options"]}


def _by_label(data, sid):
    return {o["label"]: o for o in _options(data, sid).values()}


def test_the_page_lists_exactly_the_registrys_active_models_with_the_star_ticked(tmp_path):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    data = models.page_json(run)
    assert [s["id"] for s in data["sections"]] == ["images", "video", "upscale", "voice", "notes"]
    for sid, task in models.ORGANIC.items():
        shown = [(e["model"] or "none-upscale", e["variant"]) for e in data["plugin"][sid].values()]
        assert shown == [(r["model"], r["variant"]) for r in model_registry.active(task)], sid
        ticked = [o for o in _options(data, sid).values() if o["default"]]
        star = model_registry.star(task)
        assert len(ticked) == 1 and data["plugin"][sid][ticked[0]["id"]]["model"] in (star["model"], None)
    video = _by_label(data, "video")
    h3 = video["MiniMax H3"]
    assert h3["cost"] == pytest.approx(1.04) and h3["default"] and h3["group"] == "Suggested"   # M5's 13 s × $0.08
    assert h3["means"] == "Natural motion and native speech from an image, takes a last frame. · 0.08 USD per second"
    assert not any(k in h3 for k in ("link", "badge"))                     # only price and good_for (#115)
    assert _by_label(data, "upscale")["Topaz Video Upscale"]["cost"] == pytest.approx(13 * 0.0186)  # per its units
    assert _by_label(data, "upscale")["No upscale"]["cost"] == 0
    assert all(s.get("text") for s in data["sections"] if s["id"] in models.ORGANIC)    # the user's own model
    assert data["plugin"]["rankings_stale"] == ((date.today() - model_registry.checked()).days > 30)


def test_a_new_or_removed_model_is_never_shown(tmp_path, monkeypatch):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    reg = json.loads(json.dumps(model_registry.load()))
    for m in reg["models"]:
        if m["id"] == "alibaba/wan-3":
            m["status"] = "new"
        if m["id"] == "xai/grok-imagine-video-1.5":
            m["status"] = "removed"
    monkeypatch.setattr(model_registry, "load", lambda: reg)
    labels = set(_by_label(models.page_json(run), "video"))
    assert "Wan 3" not in labels and "Grok Imagine Video 1.5" not in labels and "MiniMax H3" in labels


def test_models_that_cant_work_for_this_video_are_greyed_out_with_the_reason(tmp_path):
    run, _ = _run(tmp_path, host="image")                     # a photoreal host image is the first frame
    _prices(run, gone=("alibaba/wan-3",))
    video = _by_label(models.page_json(run), "video")
    for name in ("Seedance 2.0", "Seedance 2.5"):
        assert video[name]["disabled"] == "doesn't accept a frame with a realistic face" and not video[name]["default"]
    assert video["Wan 3"]["disabled"] == "not available on Replicate today" and "cost" not in video["Wan 3"]


def test_no_price_file_or_a_model_left_out_or_old_prices_are_refused(tmp_path):
    run, _ = _run(tmp_path, host="none")
    with pytest.raises(Stop, match="tm tool replicate_price --run .* minimax/h3"):
        models.page_json(run)
    _prices(run, drop=("minimax/h3",))
    with pytest.raises(Stop, match="minimax/h3 is not in"):
        models.page_json(run)
    run2, _ = _run(tmp_path / "b", host="none")
    _prices(run2, checked=(date.today() - timedelta(days=30)).isoformat())
    with pytest.raises(Stop, match="read them again"):
        models.page_json(run2)


def test_the_voice_is_priced_in_credits_from_the_registry(tmp_path):
    run, pack = _run(tmp_path, host="none")
    _prices(run)
    voice = _by_label(models.page_json(run), "voice")
    said = len(" ".join(ln["text"] for ln in pack["script"]["lines"] if ln["speaker"] != "none"))  # as sent (#140)
    assert said == organic_pack.voice_numbers(pack)["characters"] == models._pack_units(pack)["characters"]
    assert voice["ElevenLabs Eleven v4"]["cost_text"] == f"≈ {said * 0.5:,.0f} credits"
    assert "0.5 credits per character" in voice["ElevenLabs Eleven v4"]["means"]


def test_the_choice_on_the_page_is_what_e1_starts_from(tmp_path, capsys):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    code, out = _cli(capsys, "organic", "page", "models", "--run", str(run.path))
    assert code == 0, out
    built = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<header class="top">' in built and '<style id="tm-look">' in built       # the run page's look (#60)
    page.record_published(run, "models", SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    page.await_(run, "models", "v1")
    data = choices.decided(run, "models")["data"]
    seedance = _by_label(data, "video")["Seedance 2.0"]
    doc = json.dumps({"id": "video", "data": {"section": "video", "choice": seedance["id"], "text": "", "note": "",
                                              "notes": {}, "updated_at": "2026-11-12T10:00:00.000Z"}, "version": 1})
    text = "\n".join([json.dumps({"count": 1, "nextCursor": None}), "<untrusted-document-86>", doc,
                      "</untrusted-document-86>"])
    mcp_saves.save(run, "db_list", {"slug": SLUG, "collection": "models", "limit": 1000}, {"raw": text},
                   at=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(timespec="seconds"),
                   server="claude-artifacts")
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "models")
    assert code == 0, out
    chosen = models.chosen(run)
    assert chosen["video"]["model"] == "bytedance/seedance-2.0" and chosen["video"]["variant"] == "720p"
    assert chosen["by"] == "user"
    assert chosen["images"]["model"] == "openai/gpt-image-2" and chosen["images"]["variant"] == "medium"
    assert chosen["voice"]["model"] == "eleven_v4"
    # the pack's video model is the one chosen, not the registry's selected one
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["host"] = {"kind": "none", "image": None}
    pack["stages"][0]["items"][0]["face"] = False
    out_problems: list = []
    organic_pack._models(pack, config.load(run), date.today(), out_problems, run=run)
    said = " ".join(str(p) for p in out_problems)
    assert "the model chosen on the Models page is bytedance/seedance-2.0" in said


def test_hands_off_takes_the_registrys_selected_models_by_rule(tmp_path, capsys):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    models.build(run)
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "models", "--by-rule")
    assert code == 0, out
    chosen = models.chosen(run)
    assert chosen["by"] == "rule" and (chosen["video"]["model"], chosen["video"]["variant"]) == ("minimax/h3", "768P")
    assert chosen["upscale"]["model"] == "topazlabs/video-upscale"
    assert chosen["images"]["send"] == {"quality": "medium"}


def test_the_users_own_model_is_taken_and_gets_a_recipe(tmp_path, monkeypatch):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    models.build(run)
    answer = run.path / "03_wip" / "answer.txt"
    answer.write_text("video: kwaivgi/kling-v3-omni-video", encoding="utf-8")
    data = choices.decided(run, "models")["data"]
    default = next(o["id"] for o in _options(data, "video").values() if o["default"])
    docs = [("video", {"section": "video", "choice": default, "text": "kwaivgi/kling-v3-omni-video"})]
    got = choices.from_docs(run, "models", choices.decided(run, "models"), docs, source=answer, how="chat")
    monkeypatch.setattr(choices, "read", lambda *a, **k: got)
    taken = models.take(run, text=answer)
    pick = taken["models"]["video"]
    assert (pick["model"], pick["user_named"], pick["cost"]) == ("kwaivgi/kling-v3-omni-video", True, None)
    assert "library/model-prompting/kwaivgi-kling-v3-omni-video.md" in taken["recipes_to_write"]


def test_a_chosen_model_without_a_recipe_gets_one_written_in_the_library(tmp_path):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    models.build(run)
    got = models.take(run, by_rule=True)
    assert got["recipes_to_write"] == []                       # every ★ model has its recipe in the plugin
    wan = next(e for e in json.loads((run.path / got["from"]).read_text(encoding="utf-8"))["plugin"]["video"].values()
               if e["model"] == "alibaba/wan-3")
    assert wan["recipe_to_write"] == "library/model-prompting/alibaba-wan-3.md"    # picked, its recipe is written first
    lib = trend_spool.workspace_of(run) / "library" / "model-prompting" / "minimax-h3.md"
    lib.parent.mkdir(parents=True)
    lib.write_text("# MiniMax H3: prompting recipe\n\nSources:\n- x\n", encoding="utf-8")
    assert models.recipe_of(run, "library/model-prompting/minimax-h3.md") is None      # undated: not current
    lib.write_text("# MiniMax H3: prompting recipe (checked 2026-11-12)\n\nSources:\n- x\n", encoding="utf-8")
    assert models.recipe_of(run, "library/model-prompting/minimax-h3.md") == lib
    assert models.recipe_of(run, "library/model-prompting/../x.md") is None


def test_any_playbook_gets_the_page_for_its_tasks(tmp_path):
    run, _ = _run(tmp_path, host="none")
    _prices(run)
    rows = []
    for model in models.price_ids(["photos", "image_to_video", "talking_person"]):
        rows.append({"model": model, "checked": TODAY, "tiers": [
            {"criteria": v["live"]["criteria"], "price": f"${v['price']['usd'] / v['live'].get('factor', 1):g}",
             "unit": "x"} for v in model_registry.variants(model).values() if v.get("live")]})
    (run.path / "02_research" / "models" / f"prices_{TODAY}_v02.json").write_text(json.dumps(rows), encoding="utf-8")
    data = models.tasks_page_json(run, ["photos", "talking_person"], {"images": 4, "video_seconds": 30}, face=True)
    assert [s["id"] for s in data["sections"]] == ["photos", "talking_person", "notes"]
    talking = _by_label(data, "talking_person")
    assert talking["Gemini Omni 1.2 Flash"]["default"] and talking["Gemini Omni 1.2 Flash"]["cost"] == pytest.approx(3.15)
    assert talking["Seedance 2.0"]["disabled"]                                           # a casting face: E005
    assert _by_label(data, "photos")["GPT Image 2 (medium)"]["cost"] == pytest.approx(4 * 0.047)
    with pytest.raises(ValueError, match="tasks of the model registry"):
        models.tasks_page_json(run, ["dancing"], {})


def test_the_intake_no_longer_asks_the_quality_tier(tmp_path):
    run, _ = _run(tmp_path)
    assert all(s["id"] != "quality" for s in intake.page_json(run)["sections"])


def test_the_models_page_has_its_own_collection():
    assert organic_pages.CAPABILITIES["models"]["db"]["rules"][0]["path"] == "models"


# --- issue #137: the page prices only what this video makes -------------------------------------------------------

def _recipe_run(tmp_path, fixture: str, *, upscale: str = "none", change=None) -> tuple[RunFolder, dict]:
    run = RunFolder.create(tmp_path / "ws", "zorbo", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    cfg = {**organic_config.defaults(), "languages": {"working": "en", "market": "en"}}
    cfg["generation"] = {**cfg["generation"], "upscale": upscale}
    config.save(run, cfg)
    pack = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    pack["lang"] = "en"
    if change:
        change(pack)
    path = run.path / "03_wip" / "pack_v01.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="recipe")
    return run, pack


def _price_file(run, ids):
    rows = [{"model": m, "checked": TODAY, "tiers": [
        {"criteria": v["live"]["criteria"], "price": f"${v['price']['usd'] / v['live'].get('factor', 1):g}",
         "unit": "x"} for v in model_registry.variants(m).values() if v.get("live")]} for m in ids]
    path = run.path / "02_research" / "models" / f"prices_{TODAY}_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def _narrated_stills(pack):
    pack["speech"]["route"] = "elevenlabs_narrator"
    for line in pack["script"]["lines"]:
        line["speaker"] = "narrator"
    pack["stages"][0]["items"].append({"name": "extra", "model": "openai/gpt-image-2", "images": 1})


def test_an_animation_shows_only_the_voice_and_needs_no_replicate_prices(tmp_path, capsys):
    run, _ = _recipe_run(tmp_path, "m1_animation_pack.json")
    data = models.page_json(run)                                        # no price file at all
    assert [s["id"] for s in data["sections"]] == ["voice", "notes"]
    assert data["plugin"]["tasks"] == {"voice": "voiceover"}
    assert not any("cost" in o for o in _options(data, "voice").values())   # credits only, no USD
    code, out = _cli(capsys, "models", "ids", "--run", str(run.path))
    assert code == 0 and out["ids"] == []


def test_a_stills_video_shows_its_planned_pictures_and_the_voice(tmp_path, capsys):
    run, pack = _recipe_run(tmp_path, "p6_quiz_pack.json", change=_narrated_stills)
    code, out = _cli(capsys, "models", "ids", "--run", str(run.path))
    assert code == 0 and out["ids"] == models.price_ids(["illustrations"])
    _price_file(run, out["ids"])                                         # only the illustration models are priced
    data = models.page_json(run)
    assert [s["id"] for s in data["sections"]] == ["images", "voice", "notes"]
    assert data["plugin"]["tasks"] == {"images": "illustrations", "voice": "voiceover"}
    assert data["plugin"]["units"]["images"] == 5                        # the five cards, not one per 15 s
    star = next(o for o in _options(data, "images").values() if o["default"])
    assert star["cost"] == pytest.approx(5 * 0.047)
    assert next(s for s in data["sections"] if s["id"] == "images")["title"] == "Images (the cards and pictures)"


def test_without_stages_the_pictures_are_one_per_shot(tmp_path):
    def shots(pack):
        _narrated_stills(pack)
        pack.pop("stages")
    run, pack = _recipe_run(tmp_path, "p6_quiz_pack.json", change=shots)
    _price_file(run, models.price_ids(["illustrations"]))
    assert models.page_json(run)["plugin"]["units"]["images"] == len(pack["script"]["lines"])


def test_a_photoreal_face_takes_the_photos_task(tmp_path):
    def face(pack):
        _narrated_stills(pack)
        pack["stages"][0]["items"][0]["face"] = True
    run, _ = _recipe_run(tmp_path, "p6_quiz_pack.json", change=face)
    _price_file(run, models.price_ids(["photos"]))
    assert models.page_json(run)["plugin"]["tasks"]["images"] == "photos"


def test_the_upscale_is_shown_only_when_the_run_upscales(tmp_path):
    run, _ = _recipe_run(tmp_path, "m5_pl_pack.json")                  # 768p, generation.upscale: none
    _price_file(run, models.price_ids(["photos", "image_to_video"]))
    data = models.page_json(run)
    assert [s["id"] for s in data["sections"]] == ["images", "video", "notes"]   # H3 speaks: no ElevenLabs voice
    assert data["plugin"]["units"]["images"] == 2                       # the host item's two pictures
    run2, _ = _recipe_run(tmp_path / "b", "m5_pl_pack.json", upscale="pruna")
    _price_file(run2, models.price_ids(["photos", "image_to_video", "upscale"]))
    data2 = models.page_json(run2)
    assert [s["id"] for s in data2["sections"]] == ["images", "video", "upscale", "notes"]
    ticked = next(o for o in _options(data2, "upscale").values() if o["default"])
    assert data2["plugin"]["upscale"][ticked["id"]]["model"] == model_registry.star("upscale")["model"]


def test_no_upscale_is_ticked_on_a_page_of_tasks_when_the_run_does_not_upscale(tmp_path):
    run, _ = _recipe_run(tmp_path, "m5_pl_pack.json")
    _price_file(run, models.price_ids(["upscale"]))
    data = models.tasks_page_json(run, ["upscale"], {"video_seconds": 13}, upscale=False)
    ticked = next(o for o in _options(data, "upscale").values() if o["default"])
    assert data["plugin"]["upscale"][ticked["id"]]["model"] is None and ticked["label"] == "No upscale"
