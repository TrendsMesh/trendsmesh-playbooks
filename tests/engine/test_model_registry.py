"""The model registry (issue #115): the data file, its alias table and the loader that checks them."""

from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from tm import model_registry as reg


def _ids(rows):
    return [(r["model"], r["variant"]) for r in rows]


def test_the_shipped_registry_and_aliases_pass_their_own_check():
    assert reg.validate(reg.load(), reg.aliases()) == []
    assert reg.checked() == date(2026, 11, 17)


def test_the_stars_are_section_4s():
    want = {"photos": ("openai/gpt-image-2", "medium"), "illustrations": ("openai/gpt-image-2.5-sunburst", "medium"),
            "image_edit": ("openai/gpt-image-2.5-sunburst", "medium"), "image_to_video": ("minimax/h3", "768P"),
            "text_to_video": ("minimax/h3", "768P"), "talking_person": ("google/gemini-omni-1.2-flash", "720p"),
            "lipsync": ("kwaivgi/kling-avatar-v2", "std"), "upscale": ("topazlabs/video-upscale", "1080p"),
            "voiceover": ("eleven_v4", "default"), "sound_effects": ("eleven_text_to_sound_v3", "default"),
            "voice_changer": ("eleven_multilingual_sts_v2", "default"), "inpainting": ("jd7h/propainter", "default"),
            "transcription": ("scribe_v3", "default")}
    for task, (model, variant) in want.items():
        star = reg.star(task)
        assert (star["model"], star["variant"]) == (model, variant), task


def test_the_groups_of_photos_and_image_to_video():
    photos = reg.active("photos")
    assert [r["group"] for r in photos] == sorted((r["group"] for r in photos), key=reg.GROUPS.index)
    by = {g: _ids(r for r in photos if r["group"] == g) for g in reg.GROUPS}
    assert set(by["budget"]) == {("openai/gpt-image-2.5-sunburst", "low"), ("openai/gpt-image-2.5-flare", "low"),
                                 ("openai/gpt-image-2", "low"), ("prunaai/p-image", "default")}
    assert set(by["best"]) == {("openai/gpt-image-2.6-sunburst", "medium"), ("openai/gpt-image-2.5-sunburst", "high"),
                               ("openai/gpt-image-2", "high")}
    video = {g: {r["model"] for r in reg.active("image_to_video") if r["group"] == g} for g in reg.GROUPS}
    assert video == {"budget": {"alibaba/wan-3", "xai/grok-imagine-video-1.5"},
                     "suggested": {"minimax/h3", "google/gemini-omni-1.2-flash"},
                     "best": {"bytedance/seedance-2.5", "bytedance/seedance-2.0"}}


@pytest.mark.parametrize("model, variant, usd, per", [
    ("openai/gpt-image-2", "medium", 0.047, "image"), ("openai/gpt-image-2.6-sunburst", "medium", 0.09, "image"),
    ("prunaai/p-image", "default", 0.005, "image"), ("bytedance/seedream-5-pro", "1K", 0.045, "image"),
    ("black-forest-labs/flux-3-image", "1k", 0.048, "image"), ("minimax/h3", "768P", 0.08, "second"),
    ("minimax/h3", "2K", 0.13, "second"), ("minimax/h3-lite", "768P", 0.02, "second"),
    ("alibaba/wan-3", "720p", 0.07, "second"), ("google/gemini-omni-1.2-flash", "720p", 0.105, "second"),
    ("bytedance/seedance-2.0", "720p", 0.18, "second"), ("bytedance/seedance-2.5", "720p", 0.2312, "second"),
    ("kwaivgi/kling-avatar-v2", "std", 0.056, "second"), ("prunaai/p-video-avatar", "720p", 0.025, "second"),
    ("prunaai/p-video-upscale", "standard", 0.02, "second"), ("topazlabs/video-upscale", "1080p", 0.0186, "second"),
])
def test_section_4s_prices(model, variant, usd, per):
    price = reg.price(model, variant)
    assert (price["usd"], price["per"], price["checked"]) == (usd, per, "2026-11-17")


def test_a_price_per_15_s_is_what_the_issue_shows():
    assert round(reg.price("minimax/h3", "768P")["usd"] * 15, 2) == 1.20
    assert round(reg.price("bytedance/seedance-2.5", "720p")["usd"] * 15, 2) == 3.47
    assert round(reg.price("google/gemini-omni-1.2-flash", "720p")["usd"] * 10, 2) == 1.05
    assert round(reg.price("topazlabs/video-upscale", "1080p")["usd"] * 15, 2) == 0.28


def test_the_talking_person_route():
    route = reg.route("talking_person")["situations"]
    assert route["exact_wording"]["model"] == "google/gemini-omni-1.2-flash" and route["exact_wording"]["star"]
    assert route["specific_person"]["model"] == "minimax/h3"
    assert route["described"]["model"] == "bytedance/seedance-2.0"
    assert route["described"]["also"] == ["bytedance/seedance-2.5"]
    assert route["fallback"]["model"] == "kwaivgi/kling-avatar-v2"
    assert reg.route("long_speech") == {"takes": "several", "keep": ["reference_image", "voice"],
                                        "cut": "sentence_end"}


def test_the_voice_route():
    rows = {(r["on_screen"], r["recording"]): r for r in reg.route("voice")}
    assert rows[(False, True)]["route"] == "user_recording"
    assert rows[(False, False)]["model"] == "eleven_v4"
    assert rows[(True, True)]["model"] == "kwaivgi/kling-avatar-v2" and rows[(True, True)]["budget"] == \
        "prunaai/p-video-avatar"
    assert rows[(True, False)]["model"] == "google/gemini-omni-1.2-flash"
    assert rows[(True, False)]["then"] == "eleven_multilingual_sts_v2"


def test_the_limits():
    assert set(reg.with_limit("photoreal_face")) == {"bytedance/seedance-2.0", "bytedance/seedance-2.5"}
    assert "quality_auto" in reg.cannot("openai/gpt-image-2")
    assert reg.cannot("unknown/model") == set()


def test_the_variant_always_sent():
    assert reg.send("minimax/h3", "768P") == {"resolution": "768P"}
    assert reg.send("openai/gpt-image-2", "medium") == {"quality": "medium", "output_format": "png"}
    assert reg.send("eleven_text_to_sound_v3", "default") == {"model_id": "eleven_text_to_sound_v3"}
    assert reg.send("alibaba/wan-3", "720p") == {"resolution": "720p"}
    assert reg.send("topazlabs/video-upscale", "1080p") == {"target_resolution": "1080p", "target_fps": "source"}
    for model in reg.ids():
        for name, var in reg.variants(model).items():
            assert var["send"].get("quality") != "auto", (model, name)


def test_a_live_price_is_read_in_the_registrys_unit(tmp_path):
    f = tmp_path / "prices.json"
    f.write_text(json.dumps([
        {"model": "topazlabs/video-upscale", "checked": "2026-11-18", "tiers": [{"criteria": "all", "price": "$0.08",
                                                                                 "unit": "unit"}]},
        {"model": "minimax/h3", "checked": "2026-11-18", "tiers": [
            {"criteria": "target resolution=768P", "price": "$0.08", "unit": "second of output video"},
            {"criteria": "target resolution=2K", "price": "$0.13", "unit": "second of output video"}]},
        {"model": "alibaba/wan-3", "error": "billingConfig not found"}]), encoding="utf-8")
    usd, per, checked = reg.live_price(f, "topazlabs/video-upscale", "1080p")
    assert (round(usd, 4), per, checked) == (0.0186, "second", "2026-11-18")
    assert reg.live_price(f, "minimax/h3", "2K")[0] == 0.13
    with pytest.raises(ValueError, match="no price"):
        reg.live_price(f, "alibaba/wan-3", "720p")
    with pytest.raises(ValueError, match="not in"):
        reg.live_price(f, "bytedance/seedance-2.0", "720p")


def test_new_and_removed_models_are_never_offered():
    data = copy.deepcopy(reg.load())
    m = next(x for x in data["models"] if x["id"] == "alibaba/wan-3")
    m["status"] = "new"
    assert "alibaba/wan-3" not in {r["model"] for r in reg.active("image_to_video", data=data)}
    m["status"] = "removed"
    assert "alibaba/wan-3" not in {r["model"] for r in reg.active("image_to_video", data=data)}
    assert "alibaba/wan-3" not in reg.ids(data=data)


@pytest.mark.parametrize("break_it, says", [
    (lambda d: d["models"][0]["tasks"]["photos"].append({"variant": "high", "group": "best", "star": True}),
     "photos has 2 stars"),
    (lambda d: d["models"][0]["tasks"]["photos"].append({"variant": "ultra", "group": "best"}), "no variant ultra"),
    (lambda d: d["models"][0].update(status="maybe"), "status"),
    (lambda d: d["models"][0]["tasks"].update(dancing=[{"variant": "low", "group": "budget"}]), "no task dancing"),
    (lambda d: d["models"][0]["tasks"]["photos"].append({"variant": "low", "group": "cheap"}), "group cheap"),
    (lambda d: d["routes"]["talking_person"]["situations"]["described"].update(model="x/unknown"), "x/unknown"),
    (lambda d: d["models"][0]["variants"]["low"]["price"].pop("per"), "price"),
    (lambda d: d["models"][0]["variants"]["low"]["send"].update(quality="auto"), "quality auto"),
    (lambda d: d["models"].append(copy.deepcopy(d["models"][0])), "twice"),
])
def test_a_broken_registry_is_named(break_it, says):
    data = copy.deepcopy(reg.load())
    break_it(data)
    problems = reg.validate(data, reg.aliases())
    assert any(says in p for p in problems), problems


def test_a_new_model_with_a_star_is_refused():
    data = copy.deepcopy(reg.load())
    m = next(x for x in data["models"] if x["id"] == "minimax/h3")
    m["status"] = "new"
    assert any("new" in p and "minimax/h3" in p for p in reg.validate(data, reg.aliases()))


def test_every_active_paid_model_has_its_aliases():
    names = reg.aliases()
    for model in reg.ids():
        if reg.model(model)["provider"] != "local":
            assert model in names, model


def test_the_disclosure_markers_cover_every_paid_model():
    markers = reg.ai_markers()
    for model in reg.ids():
        if reg.model(model)["provider"] != "local":
            assert any(m in model.lower() for m in markers), model
    assert "replicate" in markers and "elevenlabs" in markers
    assert not any(m in ("opencv-telea", "mixkit", "whisper") for m in markers)


def test_the_registry_is_stale_after_30_days():
    assert not reg.stale(date(2026, 12, 17))
    assert reg.stale(date(2026, 12, 18))


def _cli(capsys, *argv):
    from tm.cli import main

    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_tm_models_check_list_and_ids(capsys):
    code, out = _cli(capsys, "models", "check")
    assert (code, out["problems"]) == (0, [])
    code, out = _cli(capsys, "models", "list", "--task", "upscale")
    assert code == 0 and [r["model"] for r in out["rows"]][-1] == "topazlabs/video-upscale"
    assert "★ topazlabs/video-upscale 1080p: 0.0186 USD per second" in out["message"]
    code, out = _cli(capsys, "models", "ids", "--task", "upscale", "--task", "lipsync")
    assert out["ids"] == ["prunaai/p-video-upscale", "topazlabs/video-upscale", "prunaai/p-video-avatar",
                          "kwaivgi/kling-avatar-v2"]
    code, out = _cli(capsys, "models", "list", "--task", "dancing")
    assert code == 1 and "not a task" in out["message"]
