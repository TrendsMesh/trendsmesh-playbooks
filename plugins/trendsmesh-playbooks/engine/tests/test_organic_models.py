"""Issue #86: organic video's Models page, after the idea is picked and before the pack: each task's models from
today's rankings and Replicate prices, priced for this video by the engine, the ones that can't work greyed out with
the reason, and the choice E1 starts from. Synthetic runs only (the public M5 pack fixture, made-up prices)."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tm import config, mcp_saves, organic_config, organic_pack, organic_pages, page, state, trend_spool
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


def _run(tmp_path, *, host="image", route="h3_native") -> tuple[RunFolder, dict]:
    run = RunFolder.create(tmp_path / "ws", "zorbo", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "languages": {"working": "en", "market": "en"}})
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


def _prices(run, checked=TODAY):
    rows = [{"model": "openai/gpt-image-2", "checked": checked,
             "tiers": [{"criteria": "quality=medium", "price": "$0.047", "unit": "output image"},
                       {"criteria": "quality=high", "price": "$0.128", "unit": "output image"}]},
            {"model": "minimax/h3", "checked": checked,
             "tiers": [{"criteria": "target resolution=768P", "price": "$0.08", "unit": "second"},
                       {"criteria": "target resolution=2K", "price": "$0.13", "unit": "second"}]},
            {"model": "bytedance/seedance-1.5-pro", "checked": checked,
             "tiers": [{"criteria": "resolution=720p, audio=false", "price": "$0.026", "unit": "second"},
                       {"criteria": "resolution=720p, audio=true", "price": "$0.052", "unit": "second"}]},
            {"model": "prunaai/p-video-upscale", "checked": checked,
             "tiers": [{"criteria": "all", "price": "$0.02", "unit": "second"}]},
            {"model": "nobody/gone", "error": "billingConfig not found"}]
    path = run.path / "02_research" / "models" / f"prices_{checked}_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path.relative_to(run.path).as_posix()


def _rank(place, source="Arena image-to-video", day=TODAY):
    return {"source": source, "place": place, "date": day}


def _candidates(run, *, price_file=None, rank_day=TODAY, seedance_audio="resolution=720p, audio=false"):
    data = {"price_file": price_file or _prices(run),
            "units": {"images": 1, "video_seconds": 15, "takes": 1, "upscale_seconds": 15},
            "tasks": {
                "images": [{"model": "openai/gpt-image-2", "criteria": "quality=medium", "group": "suggested",
                            "rank": _rank(2, "Arena text-to-image", rank_day), "good_at": "first frames",
                            "selected": True, "recipe": "references/model-prompting/gpt-image-2.md"}],
                "video": [{"model": "bytedance/seedance-1.5-pro", "criteria": seedance_audio, "group": "budget",
                           "rank": _rank(9, day=rank_day), "good_at": "cheap motion", "start_frame": True,
                           "recipe": "references/model-prompting/seedance-1.5-pro.md"},
                          {"model": "minimax/h3", "criteria": "target resolution=768P", "group": "suggested",
                           "rank": _rank(4, day=rank_day), "good_at": "multi-shot 15 s", "start_frame": True,
                           "selected": True, "recipe": "references/model-prompting/minimax-h3.md"},
                          {"model": "acme/no-start", "criteria": "all", "group": "best", "rank": _rank(1, day=rank_day),
                           "good_at": "text only", "start_frame": False},
                          {"model": "nobody/gone", "criteria": "all", "group": "best", "rank": _rank(2, day=rank_day),
                           "good_at": "new", "start_frame": True, "recipe": None}],
                "upscale": [{"model": None, "label": "No upscale (768p)", "group": "budget"},
                            {"model": "prunaai/p-video-upscale", "criteria": "all", "group": "suggested",
                             "rank": _rank(1, "Artificial Analysis upscale", rank_day), "selected": True,
                             "recipe": "references/model-prompting/p-video-upscale.md"}],
                "voice": [{"model": "eleven_v4_turbo", "label": "ElevenLabs Eleven v4 Turbo", "group": "budget",
                           "credits": 160},
                          {"model": "eleven_v4", "label": "ElevenLabs Eleven v4", "group": "suggested",
                           "credits": 320, "selected": True}]}}
    path = run.path / "02_research" / "models" / "candidates_v01.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _options(data, sid):
    return {o["id"]: o for o in next(s for s in data["sections"] if s["id"] == sid)["options"]}


def test_models_page_prices_each_candidate_for_this_video_from_the_priced_variant(tmp_path):
    run, _ = _run(tmp_path)
    _candidates(run)
    data = models.page_json(run)
    assert [s["id"] for s in data["sections"]] == ["images", "video", "upscale", "voice", "notes"]
    images = _options(data, "images")
    assert images["openai-gpt-image-2-quality-medium"]["cost"] == pytest.approx(0.047)        # 1 frame × medium
    video = _options(data, "video")
    h3 = next(o for o in video.values() if o["label"] == "minimax/h3")
    assert h3["cost"] == pytest.approx(1.20) and h3["default"] and h3["group"] == "Suggested"   # 15 s × $0.08
    assert h3["link"] == "https://replicate.com/minimax/h3" and "#4 on Arena image-to-video" in h3["means"]
    assert all(o["label"] != "acme/no-start" for o in video.values())                         # no start frame: not listed
    upscale = _options(data, "upscale")
    assert upscale["none"]["cost"] == 0 and any(o["cost"] == pytest.approx(0.30) for o in upscale.values())
    assert data["total"]


def test_models_that_cant_work_for_this_video_are_greyed_out_with_the_reason(tmp_path):
    run, _ = _run(tmp_path, host="image")                     # a photoreal host image is the first frame
    _candidates(run)
    video = _options(models.page_json(run), "video")
    seedance = next(o for o in video.values() if o["label"].startswith("bytedance/seedance"))
    assert seedance["disabled"] == "doesn't accept a frame with a realistic face" and not seedance["default"]
    gone = next(o for o in video.values() if o["label"] == "nobody/gone")
    assert gone["disabled"] == "Replicate shows no price for it today"
    assert "recipe to write" in gone["badge"]


def test_a_narrated_video_prices_the_variant_without_audio(tmp_path):
    run, _ = _run(tmp_path, host="none", route="elevenlabs_narrator")
    _candidates(run, seedance_audio="resolution=720p, audio=true")
    video = _options(models.page_json(run), "video")
    seedance = next(o for o in video.values() if o["label"].startswith("bytedance/seedance"))
    assert "variant without audio" in seedance["disabled"]


def test_old_rankings_or_prices_are_refused(tmp_path):
    run, _ = _run(tmp_path, host="none")
    _candidates(run, rank_day=(date.today() - timedelta(days=30)).isoformat())
    with pytest.raises(Stop, match="older than 7 days"):
        models.page_json(run)
    run2, _ = _run(tmp_path / "b", host="none")
    old = (date.today() - timedelta(days=30)).isoformat()
    _candidates(run2, price_file=_prices(run2, checked=old))
    with pytest.raises(Stop, match="read them again"):
        models.page_json(run2)


def test_the_choice_on_the_page_is_what_e1_starts_from(tmp_path, capsys):
    run, _ = _run(tmp_path, host="none")
    _candidates(run)
    code, out = _cli(capsys, "organic", "page", "models", "--run", str(run.path))
    assert code == 0, out
    built = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<header class="top">' in built and '<style id="tm-look">' in built       # the run page's look (#60)
    page.record_published(run, "models", SLUG, "v1", f"https://claude.ai/artifact/{SLUG}")
    page.await_(run, "models", "v1")
    data = choices.decided(run, "models")["data"]
    seedance = next(o for o in _options(data, "video").values() if o["label"].startswith("bytedance/seedance"))
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
    assert chosen["video"]["model"] == "bytedance/seedance-1.5-pro" and chosen["by"] == "user"
    assert chosen["images"]["model"] == "openai/gpt-image-2"                      # untouched: the suggested one
    assert chosen["voice"]["model"] == "eleven_v4"
    assert chosen["total_usd"] == pytest.approx(0.047 + 0.39 + 0.30)
    # the pack's video model is the one chosen, not the tier's
    pack = json.loads((FIXTURES / "m5_pl_pack.json").read_text(encoding="utf-8"))
    pack["host"] = {"kind": "none", "image": None}
    pack["stages"][0]["items"][0]["face"] = False
    out_problems: list = []
    organic_pack._models(pack, config.load(run), date.today(), out_problems, run=run)
    said = " ".join(str(p) for p in out_problems)
    assert "the model chosen on the Models page is bytedance/seedance-1.5-pro" in said


def test_hands_off_takes_the_suggested_models_by_rule(tmp_path, capsys):
    run, _ = _run(tmp_path, host="none")
    _candidates(run)
    models.build(run)
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "models", "--by-rule")
    assert code == 0, out
    chosen = models.chosen(run)
    assert chosen["by"] == "rule" and chosen["video"]["model"] == "minimax/h3"
    assert chosen["upscale"]["model"] == "prunaai/p-video-upscale"


def test_a_chosen_model_without_a_recipe_gets_one_written_in_the_library(tmp_path, capsys):
    run, _ = _run(tmp_path, host="none")
    data = _candidates(run)
    data["tasks"]["video"][1]["recipe"] = None                    # pretend H3 had no recipe
    (run.path / "02_research" / "models" / "candidates_v02.json").write_text(json.dumps(data), encoding="utf-8")
    models.build(run)
    got = models.take(run, by_rule=True)
    assert got["recipes_to_write"] == ["library/model-prompting/minimax-h3.md"]
    lib = trend_spool.workspace_of(run) / "library" / "model-prompting" / "minimax-h3.md"
    lib.parent.mkdir(parents=True)
    lib.write_text("# MiniMax H3: prompting recipe\n\nSources:\n- x\n", encoding="utf-8")
    assert models.recipe_of(run, "library/model-prompting/minimax-h3.md") is None      # undated: not current
    lib.write_text("# MiniMax H3: prompting recipe (checked 2026-11-12)\n\nSources:\n- x\n", encoding="utf-8")
    assert models.recipe_of(run, "library/model-prompting/minimax-h3.md") == lib
    assert models.recipe_of(run, "library/model-prompting/../x.md") is None


def test_the_intake_no_longer_asks_the_quality_tier(tmp_path):
    run, _ = _run(tmp_path)
    assert all(s["id"] != "quality" for s in intake.page_json(run)["sections"])


def test_the_models_page_has_its_own_collection():
    assert organic_pages.CAPABILITIES["models"]["db"]["rules"][0]["path"] == "models"
