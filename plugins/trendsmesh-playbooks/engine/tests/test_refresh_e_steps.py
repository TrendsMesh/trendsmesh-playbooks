"""Refresh an ad, the live test's E1 (test plan), E2 (upload and paused ads) and E2b (R8 check): the prose and
templates for issues #24 (the AI disclosure is decided before E2 creates the creatives), #26 (the control gets a
4:5 crop of the original too, the plan names files and placements per ad, the build matches it) and #25 (the
desktop app's upload window: the files go to the user first, one round)."""

import re

from test_brief_flow import _leaf, _tm_commands
from test_organic_skill import _tool_parser
from tm import cli, paths

PLUGIN = paths.bundled_data().parent
SKILL = PLUGIN / "skills" / "refresh-ad"


def _text(path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _flow_section(step: str) -> str:
    text = _text(SKILL / "references" / "flow.md")
    start = text.index(f'<a id="{step}"></a>')
    end = text.find('<a id="', start + 1)
    return text[start:end if end > 0 else None]


def _skill_section(n: int) -> str:
    text = _text(SKILL / "SKILL.md")
    start = text.index(f"## {n}. ")
    return text[start:text.index("## ", start + 4)]


# --- #24: the AI disclosure -------------------------------------------------------------------------------------

def test_e1_derives_the_ai_facts_from_the_run_and_asks_before_e2():
    e1 = _flow_section("e1")
    for part in ("`tm ai-media --run R --file", "self_ai_disclosure", "created or edited with generative AI",
                 "both", "neither", "only the variant", "second difference", "never decide",
                 "the original"):
        assert part in e1, part
    # Hands-off: nobody to ask, and Meta says never infer it, so the run stops before E2 creates anything
    assert "`tm stop --run R --reason ai_disclosure" in e1


def test_e2_sets_the_disclosure_on_every_creative_and_e2b_only_checks_it():
    e2 = _flow_section("e2")
    assert "self_ai_disclosure" in e2 and "OPT_IN" in e2 and "OPT_OUT" in e2
    assert "every creative" in e2 and "can't be set later" in e2
    e2b = _flow_section("e2b")
    assert "self_ai_disclosure" in e2b and "never asks" in e2b
    assert "AI labelling," not in e2b      # no longer a question asked here
    skill = _skill_section(7)
    assert "self_ai_disclosure" in skill


def test_prelaunch_item_1_uses_metas_wording_and_checks_the_creatives():
    t = _text(SKILL / "templates" / "prelaunch_check_template.md")
    assert "AI-generated people or scenes)" not in t   # the old, narrower item
    item = t[t.index("| 1 |"):t.index("| 2 |")]
    for part in ("created or edited with a generative AI tool", "cloned or synthetic voice", "inpaint",
                 "self_ai_disclosure", "the plan's decision", "Red if", "never ask"):
        assert part in item, part


def test_the_plan_and_the_card_carry_the_ai_disclosure():
    plan = _text(SKILL / "templates" / "live_test_plan_template.md")
    assert "AI disclosure" in plan and "self_ai_disclosure" in plan and "`tm ai-media`" in plan
    cards = _text(SKILL / "references" / "checkin-cards.md")
    g10 = cards[cards.index("| G10 |"):cards.index("| E2b |")]
    assert "AI disclosure" in g10


def test_the_free_opencv_plate_alone_gives_no_reason_for_the_ai_label():
    """#56, option 2: the free caption removal is classical image processing, not AI media; ProPainter is."""
    e1 = _flow_section("e1")
    assert "OpenCV Telea: classical image processing, no model) is not AI media" in e1
    assert "ProPainter" in e1 and "the free plate is the run's only edit" in e1
    vc = _flow_section("vc")
    assert "not AI media, so alone it adds no AI label" in vc
    cards = _text(SKILL / "references" / "checkin-cards.md")
    g10 = cards[cards.index("| G10 |"):cards.index("| E2b |")]
    assert "free OpenCV caption plate is not AI media" in g10
    item = _text(SKILL / "templates" / "prelaunch_check_template.md")
    assert "not the free OpenCV plate" in item


# --- #26: the 4:5 crop of the original, files and placements per ad --------------------------------------------

def test_e1_crops_the_original_to_4x5_when_r6_asks_for_it():
    e1 = _flow_section("e1")
    for part in ("`tm tool reframe", "4:5 version of the original", "free", "placement asset customization",
                 "differ only in the change under test", "files and placements per ad"):
        assert part in e1, part


def test_e2_builds_the_plan_and_stops_before_any_difference():
    e2 = _flow_section("e2")
    assert "exactly" in e2 and "stop and ask" in e2 and "before creating" in e2


def test_e2b_checks_the_built_ads_against_the_plans_formats_and_placements():
    assert "formats and placements" in _flow_section("e2b")
    t = _text(SKILL / "templates" / "prelaunch_check_template.md")
    assert "| 8 |" in t
    item = t[t.index("| 8 |"):].lower()
    assert "formats and placements" in item and "approved plan" in item and "control" in item


def test_the_plan_template_names_files_and_placements_per_ad():
    plan = _text(SKILL / "templates" / "live_test_plan_template.md")
    for part in ("| Ad | Reels and Stories (9:16) | Feed (4:5) |", "| Control |", "| Variant",
                 "placement asset customization", "4:5 version of the original", "`tm tool reframe`"):
        assert part in plan, part


# --- #25: the upload window in the desktop app -------------------------------------------------------------------

def test_section_7_describes_the_upload_window_as_an_upload_the_user_finishes():
    skill = _skill_section(7)
    for part in ("upload window", "not a failure", "SendUserFile", "thumbnail", "one round",
                 "05_results/meta_objects_v01.json", "--reason upload_by_hand", "Never upload to a public host"):
        assert part in skill, part


def test_flow_e2_sends_every_file_first_then_one_upload():
    e2 = _flow_section("e2")
    for part in ("upload window", "SendUserFile", "thumbnail", "one round", "SKILL.md section 7"):
        assert part in e2, part


def test_the_e_steps_name_only_commands_and_flags_tm_has():
    parser = cli.build_parser()
    seen = 0
    for section in [_flow_section(s) for s in ("e1", "e2", "e2b")] + [_skill_section(7)]:
        for cmd in _tm_commands(section):
            words = cmd.split()[1:]
            path = [w for w in words if re.fullmatch(r"[a-z][a-z0-9*-]*", w)]
            if path[:1] == ["tool"]:   # `tm tool <name>` hands its arguments to the tool's own parser
                leaf = _tool_parser(path[1])
            else:
                leaf, _ = _leaf(parser, path[:2])
            options = {o for a in leaf._actions for o in a.option_strings}
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", cmd):
                assert flag in options, f"`{cmd}`: {flag} is not an option"
            seen += 1
    assert seen >= 5
