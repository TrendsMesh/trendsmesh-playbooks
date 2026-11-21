"""Issue #146 part 2: the skill ships an example brief pack, `templates/brief_pack_example.json`, for both kinds of
brief (issue #136), in the shape `tm brief check` holds a brief to, and the skill points to it instead of to files
that are only in the repository."""

import json

import pytest

from tm import brief_checks, brief_organic, paths

SKILL = paths.bundled_data().parent / "skills" / "creative-brief"
EXAMPLE = SKILL / "templates" / "brief_pack_example.json"


def _example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _ad() -> dict:
    return {k: v for k, v in _example().items() if not k.startswith("_")}


@pytest.mark.parametrize("stage", ["concepts", "brief", "production"])
def test_the_ad_example_is_in_the_shape_of_every_ad_stage(stage):
    assert brief_checks.shape(_example(), stage) == []
    assert brief_checks.shape(_ad(), stage) == []


@pytest.mark.parametrize("stage", ["organic_concepts", "organic_views"])
def test_the_organic_example_is_in_the_shape_of_every_organic_stage(stage):
    organic = _example()["_organic_video_brief"]
    assert brief_checks.shape(organic, stage) == []
    assert brief_checks.shape(organic, "concepts") != []      # an organic brief is not an ad brief


def test_the_examples_have_their_plugin_blocks_and_views():
    ad, organic = _ad(), _example()["_organic_video_brief"]
    assert ad["meta"]["kind"] == "ad" and organic["meta"]["kind"] == "organic"
    assert set(ad["meta"]["plugin"]) == {"evidence", "account_currency"}
    for c in ad["concepts"]:
        assert {"candidate", "trend", "axes", "saturation", "hook_image", "sound", "directional"} <= set(c["plugin"])
        assert all("as_of" in e["plugin"] for e in c["copy_from_hook"]["evidence"])
        assert [r["label"] for r in c["editor"]] == list(brief_checks.EDITOR_ROWS)
        assert [r["label"] for r in c["media"]] == list(brief_checks.MEDIA_ROWS)
    assert ad["meta"]["recipients"] == ["decision", "strategy", "creator", "editor", "media-buyer"]
    assert "publisher" in organic["meta"]["recipients"] and "media-buyer" not in organic["meta"]["recipients"]
    assert brief_organic.posting_problems(organic) == [] and brief_organic.plan_problems(organic) == []


def test_the_skill_points_to_the_example_not_to_the_repository():
    flow = (SKILL / "references" / "flow.md").read_text(encoding="utf-8")
    rules = (SKILL / "references" / "rules.md").read_text(encoding="utf-8")
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for text in (flow, rules, skill):
        assert "templates/brief_pack_example.json" in text
        for repo_only in ("spec/02-creative-brief", "tests/engine/fixtures", "schema/brief.schema.json",
                          "in the repository"):
            assert repo_only not in text, repo_only
