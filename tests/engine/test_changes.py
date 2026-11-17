"""Supported changes and the material check."""

import pytest

from tm import changes


def ids(stage, material):
    return [c.id for c in changes.for_stage(stage, material)]


def test_hook_changes_by_material():
    assert ids("hook", "text_cards") == ["opening_text_card"]
    assert ids("hook", "vo_captions") == ["opening_text_card", "first_voiceover_line"]


def test_promise_cta_and_fatigue():
    assert ids("promise_cta", "text_cards") == ["ending_card"]
    assert ids("fatigue", "vo_captions") == ["ai_video_new_look"]
    assert ids("fatigue", "text_cards") == ["ai_video_new_look"]


RECUTS = ["recut_shorter", "recut_speedup", "recut_reorder", "recut_proof_insert", "recut_new_shot",
          "recut_new_vo_line", "bumper_6s"]


def test_middle_has_the_seven_recut_changes():
    assert ids("middle", None) == RECUTS
    assert ids("middle", "text_cards") == ["recut_shorter", "recut_speedup", "recut_proof_insert",
                                           "recut_new_shot", "bumper_6s"]
    assert ids("middle", "vo_captions") == ["recut_shorter", "recut_reorder", "recut_proof_insert",
                                            "recut_new_shot", "recut_new_vo_line"]
    assert ids("middle", "static") == []
    by_id = {c.id: c for c in changes.for_stage("middle", None)}
    assert by_id["recut_new_shot"].method == "veo_first_last_frame" and by_id["recut_new_shot"].layer == "image"
    assert by_id["recut_new_vo_line"].method == "flow_v" and by_id["recut_new_vo_line"].layer == "audio"
    assert by_id["bumper_6s"].summary.startswith("A 6 s version from one continuous shot")
    assert changes.recut_ids() == RECUTS


def test_talking_head_middle_resolves_to_recut():
    assert ids("middle", "talking_head") == ["recut_shorter", "recut_reorder", "recut_proof_insert"]
    res = changes.resolve("middle", [], True, "talking_head")
    assert (res.kind, res.target, res.note) == ("ok", "middle", "")
    rescued = changes.resolve("hook", ["middle"], True, "talking_head")   # the opening has no edit
    assert (rescued.kind, rescued.target) == ("ok", "middle") and "middle" in rescued.note


def test_talking_head_hook_still_unsupported():
    for stage in ("hook", "promise_cta", "fatigue"):
        assert changes.for_stage(stage, "talking_head") == []
    res = changes.resolve("hook", [], True, "talking_head")
    assert res.kind == "unsupported" and res.target is None
    msg = changes.unsupported_message("hook", "talking_head")
    assert "talking head" in msg and "isn't supported yet" in msg and "opening" in msg
    assert "nothing was spent" in msg


def test_static_middle_still_unsupported():
    msg = changes.resolve("middle", [], True, "static").message
    assert "static graphic" in msg and "isn't supported yet" in msg


def test_static_unsupported():
    assert changes.for_stage("hook", "static") == []


def test_stage_alone_before_the_material_is_known():
    assert changes.for_stage("hook", None) != []
    assert changes.for_stage("middle", None) != []


def test_always_available_changes():
    assert [c.id for c in changes.always()] == ["format_4x5", "copy_and_thumbnail"]


def test_unknown_material_refused():
    with pytest.raises(ValueError, match="material"):
        changes.for_stage("hook", "hologram")


def td(**kw):
    base = {"is_video": True, "has_speech": False, "speech_on_camera": False, "overlays": []}
    base.update(kw)
    return base


def test_classify_material():
    assert changes.classify_material(td(is_video=False)) == "static"
    assert changes.classify_material(td(has_speech=True, speech_on_camera=True)) == "talking_head"
    assert changes.classify_material(td(has_speech=True)) == "vo_captions"
    assert changes.classify_material(td(overlays=[{"text": "Hello"}])) == "text_cards"


def test_classify_material_without_speech_or_overlays_is_static():
    assert changes.classify_material(td()) == "static"


def test_classify_material_missing_keys_refused():
    with pytest.raises(ValueError, match="is_video"):
        changes.classify_material({})
