"""Quiz, ranking and sections (plan Task 20): the handoff's QuizGrid, RankingList and RankingSplit in the plugin's Remotion
project, their props from the handoff's examples through `render._check_props`; a video in sections (the pet store's P3:
footage -> Atlas insert -> footage) through the recipe check and the `sections_covered` step check (G1); stills with
motion graphics (P6's quiz: GPT Image 2 cards -> QuizGrid -> `tm render video`), on Replicate or the user's own
pictures; and the copied look of a Recreate (OV3, lesson 21): a style spec read from at least 2 saved evidence
videos, shown with a still of the composition on the images check-in page. The real QuizGrid render runs only with
`-m video`."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import typing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from conftest import video_asked_for

import exampleedu
import petstore
from test_organic_pack import _pack, _production
from tm import config, flow, manifest, organic, organic_final, organic_gates, organic_pack, organic_qa, render, state
from tm import stepchecks
from tm.cli import main
from tm.organic_pages import gate
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import _common as common

PLUGIN = Path(__file__).resolve().parents[2]
REPO = PLUGIN.parents[1]
REMOTION = PLUGIN / "remotion" / "src"
HANDOFF_REMOTION = REPO / "handoff" / "organic-video_v02" / "tools" / "remotion" / "src"
MOTION = ("RankingList", "RankingSplit", "QuizGrid")
TODAY = date(2026, 11, 7)
PNG = b"\x89PNG\r\n\x1a\n placeholder card"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


# RankingSplit.tsx's first comment line names where its look was copied from: the handoff's names the creators and titles of
# three evidence videos, ours only says they are "Ranking _" videos. Each file's text, with that comment left out.
EVIDENCE_NAMES = re.compile(r'^// PB3 ranking, "split" look copied from .*?(?=^// - top panel)', re.M | re.S)


def _code(path: Path) -> str:
    text = _text(path)
    if path.name == "RankingSplit.tsx":
        text, n = EVIDENCE_NAMES.subn("", text)
        assert n == 1, path
    return text


def _blocks(root: str) -> dict[str, str]:
    """Each `<Composition ... />` of a Root.tsx, by its id."""
    return {re.search(r'id="(\w+)"', b).group(1): b for b in re.findall(r"<Composition\n.*?\n  />", root, re.S)}


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _pet(tmp_path, pid, *, replicate="ok", browser="ok"):
    (tmp_path / "ws").mkdir(exist_ok=True)
    run = petstore.build(tmp_path / "ws")
    p = petstore.proposal(pid)
    run = _production(run, p, petstore.KEYS[p["channel"]])
    organic.record_stack(run, replicate=replicate, elevenlabs="ok", artifacts="ok", browser=browser)
    return run


def _check(run, pack, stage="pack"):
    return organic_pack.check(run, pack, config.load(run), stage=stage, today=TODAY)


def _fields(problems):
    return [p.field for p in problems]


def _what(problems):
    return " | ".join(f"{p.field}: {p.what} {p.todo}" for p in problems)


def _checked(run, pack, n=1):
    """The pack written and marked as checked at the pack stage, its check set an hour back so later picks count."""
    path = run.path / "03_wip" / f"pack_v{n:02d}.json"
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_pack.record(run, path, pack, stage="pack")
    s = state.load(run)
    s.checked["pack"]["at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    state.save(run, s)


def _record(run, stem, n, outputs, model="minimax/h3"):
    wip = run.path / "03_wip"
    (wip / f"{stem}_v{n:02d}.run.json").write_text(json.dumps(
        {"model": model, "status": "done", "prediction_id": f"p{n}", "outputs": outputs}), encoding="utf-8")
    for name in outputs:
        (wip / name).write_bytes(PNG if name.endswith(".png") else b"a clip, not decoded here")


def _rendered(run, comp, props, rel, *, kind="render", frame=None):
    """A `tm render` output with its manifest row, as render._render records it in an organic run (what it is made
    under from `organic_qa.made_under`; test_tm_render_records_what_a_motion_render_is_made_under runs the real
    one)."""
    out = run.path / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"rendered " + rel.encode("utf-8"))
    props_file = run.path / "03_wip" / f"{Path(rel).stem}.props.json"
    props_file.write_text(json.dumps(props), encoding="utf-8")
    params = {"composition": comp, **({"frame": frame} if frame is not None else {}),
              "made_under": organic_qa.made_under(run, comp, props), "props": props}
    common.record(run, out, str(props_file), None, params=params, model=f"remotion {kind}")
    return rel


# --- the compositions --------------------------------------------------------------------------------

@pytest.mark.private_data
def test_compositions_registered():
    """The handoff's three motion-graphics compositions, as text (RankingSplit's evidence comment aside), and their
    <Composition> blocks from the handoff's Root.tsx after the three already there (refresh-ad's two unchanged); render's COMPS
    and its Comp Literal name all six."""
    root, original = _text(REMOTION / "Root.tsx"), _text(HANDOFF_REMOTION / "Root.tsx")
    ours, theirs = _blocks(root), _blocks(original)
    assert list(ours) == ["HookSwap", "WordCaptions", "OrganicCaptions", *MOTION]
    assert all(ours[name] == theirs[name] for name in ours)
    for name in MOTION:
        assert _code(REMOTION / f"{name}.tsx") == _code(HANDOFF_REMOTION / f"{name}.tsx"), name
    for line in ('import { RankingList, RankingListProps, rankingListDefaults, rankingSeconds } from "./RankingList";',
                 'import { RankingSplit, RankingSplitProps, rankingSplitDefaults, rankingSplitSeconds } from '
                 '"./RankingSplit";',
                 'import { QuizGrid, QuizGridProps, quizGridDefaults } from "./QuizGrid";'):
        assert line in root
    assert "Promo" not in root   # the handoff's own promo composition stays out
    assert render.COMPS == ("HookSwap", "WordCaptions", "OrganicCaptions", *MOTION)
    assert typing.get_args(render.Comp) == render.COMPS
    assert render.MOTION_COMPS == MOTION
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    for name in MOTION:
        assert f"plugins/trendsmesh-playbooks/remotion/src/{name}.tsx text eol=lf" in lines


@pytest.mark.private_data
def test_ranking_split_props_from_dry_run_pass(tmp_path):
    """The dry run's R1 v02 (RankingSplit, five takes) passes once its clips are in the run; a clip outside it, or
    items that are not a list, are refused."""
    run = RunFolder.create(tmp_path / "ws", "r1", TODAY, playbook=ORGANIC_VIDEO)
    props = petstore.r1_props()
    path = run.path / "03_wip" / "R1" / "edit_v02.props.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(common.ToolError, match="R1/take5_v01_0.mp4"):
        render._check_props(run, "RankingSplit", path)
    for item in props["items"]:
        (run.path / item["src"]).parent.mkdir(parents=True, exist_ok=True)
        (run.path / item["src"]).write_bytes(b"take")
    got = render._check_props(run, "RankingSplit", path)
    assert [i["rank"] for i in got["items"]] == [5, 4, 3, 2, 1] and got["splitY"] == 880
    assert render._check_props(run, "RankingList", path)["items"][4]["label"] == "Playing Dead"
    for bad, words in (({"items": {"rank": 1}}, "items must be a list"),
                       ({"items": [{**props["items"][0], "src": "../take.mp4"}]}, "inside the run folder")):
        path.write_text(json.dumps({**props, **bad}), encoding="utf-8")
        with pytest.raises(common.ToolError, match=words):
            render._check_props(run, "RankingSplit", path)


@pytest.mark.private_data
def test_quiz_props_from_p6_pass(tmp_path):
    """P6's quiz (QuizGrid: four cards and music) passes once its cards and track are in the run; a card or the music
    outside it, or options that are not a list, are refused."""
    run = RunFolder.create(tmp_path / "ws", "p6", TODAY, playbook=ORGANIC_VIDEO)
    props = petstore.p6_props()
    path = run.path / "03_wip" / "P6" / "edit_v01.props.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(common.ToolError, match="P6/donut_v02_0.png"):
        render._check_props(run, "QuizGrid", path)
    for rel in [o["img"] for o in props["options"]] + [props["music"]["src"]]:
        (run.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (run.path / rel).write_bytes(PNG)
    got = render._check_props(run, "QuizGrid", path)
    assert [o["name"] for o in got["options"]] == ["Donut", "Superman", "Side sleeper", "Belly up"]
    assert got["answer"] == 3 and got["durationSec"] == 15
    for bad, words in (({"options": "four cards"}, "options must be a list"),
                       ({"music": {"src": "C:/music.mp3", "volume": 0.5}}, "inside the run folder"),
                       ({"music": "loud"}, "music must be one object")):
        path.write_text(json.dumps({**props, **bad}), encoding="utf-8")
        with pytest.raises(common.ToolError, match=words):
            render._check_props(run, "QuizGrid", path)


# --- a video in sections ----------------------------------------------------------------------------

@pytest.mark.private_data
def test_sections_footage_insert_footage_passes(tmp_path, animatic_ready):
    """The handoff's P3 (H3 footage, an Atlas insert, H3 footage) passes the recipe and the pack check as an AI video
    with every tool there; without a Replicate key its footage sections are refused, without a browser its insert,
    each in plain words."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    assert _check(run, pack, "recipe") == [] and _check(run, pack) == [], _what(_check(run, pack))
    organic.record_stack(run, replicate="missing", elevenlabs="ok", artifacts="ok", browser="ok")
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[0].type", "sections[2].type"], _what(problems)
    assert "Section 1 is AI footage" in problems[0].what and "REPLICATE_API_TOKEN" in problems[0].what
    organic.record_stack(run, replicate="ok", elevenlabs="ok", artifacts="ok", browser="missing")
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[1].type"] and "Section 2 is an animation" in problems[0].what
    for p in problems:
        assert not re.search(r"ai_footage|stills_motion|later version", p.what + p.todo), p.what


@pytest.mark.private_data
def test_second_video_model_in_sections_refused(tmp_path, animatic_ready):
    """One video model for every footage or talking section (OV6: another model only for a separate kind of section);
    an Atlas insert or a stills section has none; the sections follow each other with no gap or overlap."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][2]["model"] = "bytedance/seedance-2.0"
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[2].model"], _what(problems)
    assert "one video model" in problems[0].what and "minimax/h3" in problems[0].todo
    pack = _pack("p3_sections_pack.json")
    pack["sections"][1]["model"] = "minimax/h3"
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[1].model"] and "Section 2 is an animation" in problems[0].what
    pack = _pack("p3_sections_pack.json")
    pack["sections"][1]["from"] = 7
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[1].from"] and "6.5" in problems[0].what
    pack = _pack("p3_sections_pack.json")
    pack["sections"][2].update({"from": 15.5, "to": 15.5})
    assert _fields(_check(run, pack, "recipe")) == ["sections[2].to"]


@pytest.mark.private_data
def test_sections_start_at_0_and_several_need_a_video_in_sections(tmp_path, animatic_ready):
    """PR D review M3: the first section starts at 0 s; a pack whose production is not `sections` lists one section,
    of its own type (several sections, mixed or not, are a video in sections)."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][0]["from"] = 3
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[0].from"] and "starts at 3 s" in problems[0].what, _what(problems)
    pack = _pack("p3_sections_pack.json")
    pack["production"] = "ai_footage"
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections"] and "3 sections" in problems[0].what, _what(problems)
    assert "production to sections" in problems[0].todo
    quiz = _pack("p6_quiz_pack.json")
    quiz["sections"][0]["type"] = "ai_footage"
    (tmp_path / "p6").mkdir()
    problems = _check(_pet(tmp_path / "p6", "p6"), quiz, "recipe")
    assert _fields(problems) == ["sections[0].type"] and "stills with motion" in problems[0].what, _what(problems)


@pytest.mark.private_data
@pytest.mark.parametrize("sid", ["../../outside", "a/b", "a\\b", "S 2", "Ś2", "S2.", "CON", "con", "Lpt9", "nul",
                                 "COM1", "aux", ""])
def test_section_id_that_cannot_name_a_folder_refused(tmp_path, animatic_ready, sid):
    """PR D review I2: a section id names the folder 03_wip/<id>/ (an insert's prompt, storyboard and renders), so it
    holds only ASCII letters, digits, '_' and '-' and is never a name Windows keeps for a device, in any case."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][1]["id"] = sid
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[1].id"], _what(problems)
    assert "cannot name a folder" in problems[0].what and "S1, S2" in problems[0].todo
    if sid.upper() in ("CON", "LPT9", "NUL", "COM1", "AUX"):
        assert "Windows keeps for a device" in problems[0].what


@pytest.mark.private_data
def test_section_ids_differing_only_in_case_refused(tmp_path, animatic_ready):
    """Two sections whose ids differ only in case share one folder on Windows and macOS: refused at the recipe; the
    pack's own id, a folder of a whole animation and the final's name, is held to the same rule."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][2]["id"] = "s1"
    problems = _check(run, pack, "recipe")
    assert _fields(problems) == ["sections[2].id"] and "section 1's id too" in problems[0].what, _what(problems)
    pack = _pack("p3_sections_pack.json")
    pack["id"] = "../P3"
    problems = [p for p in _check(run, pack, "recipe") if "cannot name a folder" in p.what]
    assert _fields(problems) == ["id"], _what(_check(run, pack, "recipe"))


@pytest.mark.private_data
@pytest.mark.parametrize("sid", ["../../outside", "CON"])
def test_an_unsafe_section_id_writes_nothing(tmp_path, capsys, animatic_ready, sid):
    """A pack checked before ids were held to the rule: atlas-prompt, storyboard and animate refuse the id before
    writing anything, so nothing lands outside the run or in a device name."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][1]["id"] = sid
    _checked(run, pack)                                    # marked as checked without the recipe's id rule
    page = run.path / "03_wip" / "page.html"
    page.write_text("<html></html>", encoding="utf-8")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    for argv in (("atlas-prompt", "--style", "03", "--aspect", "9:16", "--voiceover", "--storyboard"),
                 ("storyboard", "--page", "03_wip/page.html"), ("animate", "--page", "03_wip/page.html")):
        code, out = _cli(capsys, "organic", argv[0], "--run", str(run.path), "--item", sid, *argv[1:])
        assert code == 2 and "cannot name a folder" in out["message"] and "nothing was written" in out["message"], out
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before
    assert not list(tmp_path.rglob("prompt_v*.txt"))


def _edit(run, segments, n):
    """The edit (OrganicCaptions props), its render and the final made from it, version `n`, as tm render video and
    tm tool deliver finish record them."""
    props = {"width": 1080, "height": 1920, "fps": 30, "keepAudio": True, "segments": segments}
    render_rel = _rendered(run, "OrganicCaptions", props, f"03_wip/edit_v{n:02d}_organiccaptions_v01.mp4")
    final = run.path / "04_final" / f"p3_final_v{n:02d}.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"final" + bytes([n]))
    common.record(run, final, "tm tool deliver finish", render_rel)


@pytest.mark.private_data
def test_edit_must_cover_sections_in_order(tmp_path, animatic_ready):
    """`sections_covered` (G1): the edit the final was made from cuts P3's sections in order, each segment from its own
    section's outputs (the H3 take for S1 and S3, a sped-up copy of it too; S2's animation render). A pack with one
    section passes."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    _checked(run, pack)
    gap = organic_final.sections_gap(run)
    assert gap and "tm render video" in gap and "04_final/p3_final_vNN.mp4" in gap
    _record(run, "take", 1, ["take_v01_0.mp4"])
    anim = run.path / "03_wip" / "S2" / "renders" / "anim_v01.mp4"
    anim.parent.mkdir(parents=True)
    anim.write_bytes(b"the insert")
    take, insert = "03_wip/take_v01_0.mp4", "03_wip/S2/renders/anim_v01.mp4"
    fast = run.path / "03_wip" / "take_v01_0_speed117.mp4"
    fast.write_bytes(b"sped up")
    common.record(run, fast, "tm tool deliver speed", take, params={"factor": 1.17})
    (run.path / "03_wip" / "other_v01.mp4").write_bytes(b"not from the pack")

    def seg(src, start=0.0, end=4.0):
        return {"src": src, "start": start, "end": end}

    _edit(run, [seg(take, 0, 5), seg(insert, 0, 8), seg(take, 6.5, 10.1)], 1)
    assert organic_final.sections_gap(run) is None and stepchecks.run("sections_covered", run) is None
    _edit(run, [seg(take), seg("03_wip/take_v01_0_speed117.mp4"), seg(insert), seg(take)], 2)
    assert organic_final.sections_gap(run) is None                     # two cuts of S1, one sped up
    _edit(run, [seg(insert), seg(take), seg(take)], 3)
    gap = organic_final.sections_gap(run)
    assert gap and "in order" in gap and "S1 → S2 → S3" in gap and "S2, S1/S3, S1/S3" in gap
    _edit(run, [seg(take), seg("03_wip/other_v01.mp4"), seg(take)], 4)
    gap = organic_final.sections_gap(run)
    assert gap and "segment 2 (03_wip/other_v01.mp4) is from no section" in gap
    _edit(run, [seg(take), seg(insert)], 5)
    gap = organic_final.sections_gap(run)
    assert gap and "S1/S3, S2" in gap                                 # S3 is missing at the end
    m5 = exampleedu.build(tmp_path / "m5")
    _checked(m5, _pack("m5_pl_pack.json"))
    assert organic_final.sections_gap(m5) is None                      # one section: nothing to cover


@pytest.mark.private_data
def test_segment_paths_in_any_spelling(tmp_path, animatic_ready):
    """PR D review M2: a segment's src written with a backslash, a leading ./, a doubled / or in another case is the
    same file (a Windows agent's spelling)."""
    run = _pet(tmp_path, "p3")
    _checked(run, _pack("p3_sections_pack.json"))
    _record(run, "take", 1, ["take_v01_0.mp4"])
    anim = run.path / "03_wip" / "S2" / "renders" / "anim_v01.mp4"
    anim.parent.mkdir(parents=True)
    anim.write_bytes(b"the insert")
    for n, (take, insert) in enumerate([("03_wip\\take_v01_0.mp4", "03_wip\\S2\\renders\\anim_v01.mp4"),
                                        ("./03_wip/take_v01_0.mp4", "./03_wip//S2/renders/anim_v01.mp4"),
                                        ("03_WIP/Take_v01_0.mp4", "03_wip/s2/renders/ANIM_v01.mp4")], 1):
        _edit(run, [{"src": take, "start": 0, "end": 3}, {"src": insert, "start": 0, "end": 3},
                    {"src": take, "start": 3, "end": 6}], n)
        assert organic_final.sections_gap(run) is None, (take, organic_final.sections_gap(run))


def test_g1_requires_sections_covered():
    """Preflight P3-F7: an edit that drops or swaps a section does not pass G1."""
    g1 = next(st for st in flow.steps(ORGANIC_VIDEO) if st.id == "G1")
    assert g1.requires == ("final_checked", "sections_covered")
    assert stepchecks.NAMES["sections_covered"] == "tm.organic_final:sections_gap"


@pytest.mark.private_data
def test_animation_insert_is_9_16_and_keeps_the_caption_band(tmp_path, capsys, animatic_ready):
    """P3's S2 is an insert in a captioned 9:16 edit: its build prompt is made with --aspect 9:16 only, and
    says to keep text and key action above y 1260 (the caption band)."""
    run = _pet(tmp_path, "p3")
    _checked(run, _pack("p3_sections_pack.json"))
    argv = ("organic", "atlas-prompt", "--run", str(run.path), "--item", "s2", "--style", "03", "--voiceover",
            "--storyboard")
    for extra in ((), ("--aspect", "4:5")):
        code, out = _cli(capsys, *argv, *extra)
        assert code == 1 and "--aspect 9:16" in out["message"] and "S2" in out["message"], out
    code, out = _cli(capsys, *argv, "--aspect", "9:16")
    assert (code, out["file"]) == (0, "03_wip/S2/prompt_v01.txt"), out
    text = (run.path / out["file"]).read_text(encoding="utf-8")
    assert "1080x1920" in text and text.count("above y 1260") == 1
    assert text.index("above y 1260") < text.index("\n## The style\n") < text.index("\n## The libraries' API\n")
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert json.loads(row["params"])["insert"] is True


# --- stills with motion graphics ----------------------------------------------------------------------

def _quiz(tmp_path, **stack):
    run = _pet(tmp_path, "p6", **stack)
    return run, _pack("p6_quiz_pack.json")


@pytest.mark.private_data
def test_quiz_pack_on_replicate_or_the_users_own_pictures(tmp_path):
    """P6's quiz: four GPT Image 2 cards ($0.20) and QuizGrid (free) pass with Replicate; without a Replicate key the
    cards are refused in plain words, and the same quiz on the user's own pictures (items with no model) passes."""
    run, pack = _quiz(tmp_path)
    assert _check(run, pack, "recipe") == [] and _check(run, pack) == [], _what(_check(run, pack))
    assert organic_pack.stills(pack) == ["P6"] and organic_pack.animated(pack) == []
    assert organic_pack.ai_label(pack) == "on"
    organic.record_stack(run, replicate="missing", elevenlabs="ok", artifacts="ok", browser="ok")
    assert _check(run, pack, "recipe") == []                          # a quiz is not hidden (plan Decision 16)
    problems = _check(run, pack)
    assert _fields(problems) == ["stages"], _what(problems)
    assert "donut, superman, side, bellyup" in problems[0].what and "Replicate" in problems[0].what
    assert "own pictures" in problems[0].todo and "script to film" in problems[0].todo
    own = copy.deepcopy(pack)
    for item in own["stages"][0]["items"]:
        item["model"] = None
    own["models"], own["cost"]["lines"], own["cost"]["totals"]["ai_usd"] = [], [], 0
    assert _check(run, own) == [], _what(_check(run, own))


@pytest.mark.private_data
def test_quiz_f2_needs_its_render_from_the_picked_cards(tmp_path):
    """F2 of stills with motion graphics is the free render: `takes_checked` needs a QuizGrid, RankingList or
    RankingSplit render whose generated pictures are the cards' current picks; the video check-in page shows it."""
    run, pack = _quiz(tmp_path)
    _checked(run, pack)
    cards = ("donut", "superman", "side", "bellyup")
    for name in cards:
        _record(run, name, 1, [f"{name}_v01_0.png", f"{name}_v01_1.png"], model="openai/gpt-image-2")
        organic_qa.pick(run, "images", name, f"03_wip/{name}_v01_0.png", "the clearest pose")
    assert organic_qa.images_gap(run) is None
    gap = organic_qa.takes_gap(run)
    assert gap and "P6" in gap and "tm render video" in gap and "QuizGrid" in gap
    props = petstore.p6_props()
    for option, name in zip(props["options"], cards):
        option["img"] = f"03_wip/{name}_v01_0.png"
    props["options"][3]["img"] = "03_wip/bellyup_v01_1.png"            # not the pick
    _rendered(run, "QuizGrid", props, "03_wip/edit_v01_quizgrid_v01.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "03_wip/bellyup_v01_1.png" in gap and "not the current pick" in gap
    props["options"][3]["img"] = "03_wip/bellyup_v01_0.png"
    _rendered(run, "QuizGrid", props, "03_wip/edit_v01_quizgrid_v02.mp4")
    assert organic_qa.takes_gap(run) is None
    data = organic_gates.gate_json(run, "video")
    item = next(i for i in data["items"] if i["id"] == "motion-P6")
    assert [o["src"] for o in item["options"]] == ["03_wip/edit_v01_quizgrid_v01.mp4", "03_wip/edit_v01_quizgrid_v02.mp4"]
    assert [o.get("pick", False) for o in item["options"]] == [False, True]
    assert data["plugin"]["items"]["motion-P6"]["kind"] == "motion"


CARDS = ("donut", "superman", "side", "bellyup")


def _picked_cards(tmp_path):
    """P6's checked pack, its four cards made and picked."""
    run, pack = _quiz(tmp_path)
    _checked(run, pack)
    for name in CARDS:
        _record(run, name, 1, [f"{name}_v01_0.png"], model="openai/gpt-image-2")
        organic_qa.pick(run, "images", name, f"03_wip/{name}_v01_0.png", "clear")
    return run, pack


def _quiz_props(pictures):
    props = petstore.p6_props()
    for option, picture in zip(props["options"], pictures):
        option["img"] = picture
    return props


@pytest.mark.private_data
def test_quiz_f2_refuses_pictures_the_pack_did_not_make(tmp_path):
    """PR D review I1: with the four paid cards picked, a QuizGrid of four other pictures (a stock picture, the
    evidence thumbnails the images page saved in 03_wip/gates/) does not pass F2."""
    run, _ = _picked_cards(tmp_path)
    stock = [f"03_wip/stock_{name}.png" for name in CARDS]
    for rel in stock:
        (run.path / rel).write_bytes(PNG)
    _rendered(run, "QuizGrid", _quiz_props(stock), "03_wip/edit_v01_quizgrid_v01.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "03_wip/stock_donut.png" in gap and "not made by the pack" in gap, gap
    assert "does not show the current pick of donut, superman, side, bellyup" in gap
    thumbs = run.path / "03_wip" / "gates" / "thumbs"
    thumbs.mkdir(parents=True)
    shown = []
    for name in CARDS:
        (thumbs / f"{name}.jpg").write_bytes(PNG)
        shown.append(f"03_wip/gates/thumbs/{name}.jpg")
    shown[0] = "03_wip/donut_v01_0.png"
    _rendered(run, "QuizGrid", _quiz_props(shown), "03_wip/edit_v01_quizgrid_v02.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "03_wip/gates/thumbs/superman.jpg" in gap and "check-in pages' own" in gap, gap
    assert organic_qa.CHECK_IN == f"{gate.DATA}/"
    _rendered(run, "QuizGrid", _quiz_props([f"03_wip/{n}_v01_0.png" for n in CARDS]), "03_wip/edit_v01_quizgrid_v03.mp4")
    assert organic_qa.takes_gap(run) is None


@pytest.mark.private_data
def test_quiz_f2_refuses_one_card_shown_four_times(tmp_path):
    """PR D review I1: every generated card's current pick is in the render: the donut card four times is refused."""
    run, _ = _picked_cards(tmp_path)
    _rendered(run, "QuizGrid", _quiz_props(["03_wip/donut_v01_0.png"] * 4), "03_wip/edit_v01_quizgrid_v01.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "does not show the current pick of superman, side, bellyup" in gap, gap
    _rendered(run, "QuizGrid", _quiz_props(["03_wip/Donut_v01_0.png", "./03_wip/superman_v01_0.png",
                                            "03_wip\\side_v01_0.png", "03_WIP/bellyup_v01_0.png"]),
              "03_wip/edit_v01_quizgrid_v02.mp4")
    assert organic_qa.takes_gap(run) is None                          # any spelling of the picks


@pytest.mark.private_data
def test_quiz_render_made_before_a_replan_fails_f2(tmp_path):
    """PR D review M1 (the stills twin of Task 19 I1): a motion render records what it was made under (the pack check
    that last changed its stills item, the picks it shows). A re-check that changes the quiz's script, its cards
    left as they were, needs a new render; so does a card picked again."""
    run, pack = _picked_cards(tmp_path)
    props = _quiz_props([f"03_wip/{n}_v01_0.png" for n in CARDS])
    _rendered(run, "QuizGrid", props, "03_wip/edit_v01_quizgrid_v01.mp4")
    assert organic_qa.takes_gap(run) is None
    first = state.load(run).checked["pack"]["at"]
    changed = copy.deepcopy(pack)
    changed["script"]["lines"][2]["text"] = "Donut: he keeps warm and safe"
    _checked(run, changed, n=2)
    s = state.load(run)
    s.checked["pack"]["at"] = (datetime.fromisoformat(first) + timedelta(minutes=1)).isoformat(timespec="seconds")
    state.save(run, s)
    assert organic_qa.images_gap(run) is None                          # the cards' picks still count
    gap = organic_qa.takes_gap(run)
    assert gap and "rendered before the pack was checked again" in gap, gap
    log = run.path / organic_qa.AZ_LOG               # the picks dated after that check, so the re-pick below is later
    earlier = (datetime.fromisoformat(first) + timedelta(minutes=2)).isoformat(timespec="seconds")
    log.write_text("".join(json.dumps({**json.loads(line), "at": earlier}) + "\n"
                           for line in log.read_text(encoding="utf-8").splitlines()), encoding="utf-8")
    _rendered(run, "QuizGrid", props, "03_wip/edit_v01_quizgrid_v02.mp4")
    assert organic_qa.takes_gap(run) is None
    organic_qa.pick(run, "images", "donut", "03_wip/donut_v01_0.png", "the user's favourite", by="user")
    gap = organic_qa.takes_gap(run)
    assert gap and "rendered before donut was picked again" in gap, gap


@pytest.mark.private_data
def test_the_users_choice_of_a_motion_render_is_what_f2_takes(tmp_path, capsys):
    """PR D review M5: an accept of an older motion render on the video check-in page is the render F2 (and the edit)
    takes, and the page marks it; a render made after that page was built takes over again."""
    run, _ = _picked_cards(tmp_path)
    good = _quiz_props([f"03_wip/{n}_v01_0.png" for n in CARDS])
    _rendered(run, "QuizGrid", _quiz_props(["03_wip/donut_v01_0.png"] * 4), "03_wip/edit_v01_quizgrid_v01.mp4")
    _rendered(run, "QuizGrid", good, "03_wip/edit_v01_quizgrid_v02.mp4")
    assert organic_qa.takes_gap(run) is None
    assert _cli(capsys, "organic", "page", "gate", "--gate", "video", "--run", str(run.path))[0] == 0
    chat = run.path / "03_wip" / "chat_v01.txt"
    chat.write_text("motion-P6: accept; choice: edit_v01_quizgrid_v01\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "gate_video", "--text",
                     "03_wip/chat_v01.txt")
    assert code == 0 and out["decisions"]["motion-P6"]["file"] == "03_wip/edit_v01_quizgrid_v01.mp4", out
    assert organic_qa.chosen_motion(run, "P6")[0] == "03_wip/edit_v01_quizgrid_v01.mp4"
    gap = organic_qa.takes_gap(run)
    assert gap and "03_wip/edit_v01_quizgrid_v01.mp4: it does not show the current pick of superman" in gap, gap
    item = next(i for i in organic_gates.gate_json(run, "video")["items"] if i["id"] == "motion-P6")
    assert [o.get("pick", False) for o in item["options"]] == [True, False]
    decided = run.path / "03_wip" / "decisions_gate_video_v01.json"   # read a minute ago: the render below is later
    body = json.loads(decided.read_text(encoding="utf-8"))
    body["at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    decided.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    _rendered(run, "QuizGrid", good, "03_wip/edit_v01_quizgrid_v03.mp4")
    assert organic_qa.chosen_motion(run, "P6")[0] == "03_wip/edit_v01_quizgrid_v03.mp4"
    assert organic_qa.takes_gap(run) is None


@pytest.mark.private_data
def test_the_edit_cuts_a_stills_section_from_the_chosen_render(tmp_path, animatic_ready):
    """PR D review M5, at G1: a stills section's segments come from the render F2 took (the user's choice on the video
    page, else the latest), not from any motion render of the run."""
    run = _pet(tmp_path, "p3")
    pack = _pack("p3_sections_pack.json")
    pack["sections"][1]["type"] = "stills_motion"                   # S2 a quiz between two footage sections
    _checked(run, pack)
    _record(run, "take", 1, ["take_v01_0.mp4"])
    older = _rendered(run, "QuizGrid", petstore.p6_props(), "03_wip/S2_quizgrid_v01.mp4")
    _rendered(run, "QuizGrid", petstore.p6_props(), "03_wip/S2_quizgrid_v02.mp4")
    take = "03_wip/take_v01_0.mp4"
    _edit(run, [{"src": src, "start": 0, "end": 3} for src in (take, older, take)], 1)
    gap = organic_final.sections_gap(run)
    assert gap and f"segment 2 ({older}) is from no section" in gap and "S2_quizgrid_v02.mp4" in gap, gap
    decided = {"page": "gate_video", "source": "chat", "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "keep_carried": False, "decisions": {"motion-S2": {"kind": "motion", "name": "S2", "action": "accept",
                                                                  "choice": "S2_quizgrid_v01", "file": older}}}
    (run.path / "03_wip" / "decisions_gate_video_v01.json").write_text(json.dumps(decided), encoding="utf-8")
    assert organic_final.sections_gap(run) is None


@pytest.mark.private_data
def test_ranking_f2_from_its_picked_takes_with_ranking_split(tmp_path):
    """PR D review M6: a ranking is stills with motion graphics whose entries are takes (AI footage, the dry run's R1):
    F2 needs each take picked on its QA and a RankingSplit render of those picks, every one of them."""
    run, quiz = _quiz(tmp_path)
    pack = copy.deepcopy(quiz)
    pack["stages"] = [{"stage": "video", "items": [{"name": f"take{n}", "model": "minimax/h3", "seconds": 6}
                                                   for n in range(1, 6)]}]
    _checked(run, pack)
    props = petstore.r1_props()
    for entry in props["items"]:
        n = entry["rank"]
        _record(run, f"take{n}", 1, [f"take{n}_v01_0.mp4"])
        qa = run.path / "03_wip" / "qa" / f"take{n}_v01_0_qa_v01.json"
        qa.parent.mkdir(exist_ok=True)
        qa.write_text(json.dumps({"lufs": -14.0, "cut_offsets": []}), encoding="utf-8")
        entry["src"] = f"03_wip/take{n}_v01_0.mp4"
    gap = organic_qa.takes_gap(run)
    assert gap and "each take is checked and picked" in gap and "it has no render" in gap, gap
    for n in range(1, 6):
        organic_qa.pick(run, "takes", f"take{n}", f"03_wip/take{n}_v01_0.mp4", "the trick reads in one second")
    path = run.path / "03_wip" / "R1_v01.props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    assert [i["src"] for i in render._check_props(run, "RankingSplit", path)["items"]][0] == "03_wip/take5_v01_0.mp4"
    short = copy.deepcopy(props)
    short["items"] = short["items"][1:]                               # take 5 left out
    _rendered(run, "RankingSplit", short, "03_wip/R1_rankingsplit_v01.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "does not show the current pick of take5" in gap, gap
    _rendered(run, "RankingSplit", props, "03_wip/R1_rankingsplit_v02.mp4")
    assert organic_qa.takes_gap(run) is None
    item = next(i for i in organic_gates.gate_json(run, "video")["items"] if i["id"] == "motion-P6")
    assert [o.get("pick", False) for o in item["options"]] == [False, True]


@pytest.mark.private_data
def test_delivery_page_lists_the_motion_graphics_renders(tmp_path):
    """OV9 (every step that made the video): the delivery page shows a stills item's motion-graphics renders, the one
    the video was made from marked, beside the cards."""
    run, _ = _picked_cards(tmp_path)
    _rendered(run, "QuizGrid", _quiz_props([f"03_wip/{n}_v01_0.png" for n in CARDS]), "03_wip/edit_v01_quizgrid_v01.mp4")
    pid = organic_final.idea_id(run)
    final = run.path / "04_final" / f"{pid}_final_v01.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"the final")
    kit = run.path / "04_final" / "kits" / f"{pid}_kit_v01.json"
    kit.parent.mkdir(parents=True)
    kit.write_text(json.dumps({"id": pid, "platforms": {}}), encoding="utf-8")
    data = organic_gates.delivery_json(run)
    ids = [i["id"] for i in data["items"]]
    assert ids[0] == "final" and "motion-P6" in ids and "images-donut" in ids, ids
    item = data["items"][ids.index("motion-P6")]
    assert [(o["src"], o.get("pick")) for o in item["options"]] == [("03_wip/edit_v01_quizgrid_v01.mp4", True)]
    assert data["plugin"]["items"]["motion-P6"]["kind"] == "motion"


@pytest.mark.private_data
def test_tm_render_records_what_a_motion_render_is_made_under(tmp_path, monkeypatch):
    """`tm render video` of a motion-graphics composition in an organic run records `made_under` in its manifest row
    (the stills item's pack check, the picks it shows, when it was made); in another playbook's run it records none."""
    run, _ = _picked_cards(tmp_path)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))        # never this computer's plugin folders

    def fake_sh(argv, cwd, what):
        Path(argv[5]).write_bytes(b"rendered")                         # the part file, renamed when done

    monkeypatch.setattr(render, "_need_setup", lambda: None)
    monkeypatch.setattr(render, "_sync_src", lambda: None)
    monkeypatch.setattr(render, "_sh", fake_sh)
    props = _quiz_props([f"03_wip/{n}_v01_0.png" for n in CARDS])
    props["music"]["src"] = "03_wip/donut_v01_0.png"                    # any file of the run, not decoded here
    path = run.path / "03_wip" / "P6_v01.props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    out = render.video(run, "QuizGrid", path, run.path / "03_wip" / "P6_v01_render.mp4")
    params = json.loads(next(r for r in manifest.rows(run) if r["file"] == "03_wip/P6_v01_render.mp4")["params"])
    under = params["made_under"]
    assert set(under) == {"at", "since", "picks"} and list(under["since"]) == ["P6"]
    assert sorted(under["picks"]) == sorted(f"03_wip/{n}_v01_0.png" for n in CARDS)
    assert out.is_file() and organic_qa.takes_gap(run) is None
    other = RunFolder.create(tmp_path / "ra", "ad", TODAY)
    (other.path / "03_wip" / "x.props.json").write_text(json.dumps({"base": None}), encoding="utf-8")
    render.video(other, "HookSwap", other.path / "03_wip" / "x.props.json", other.path / "03_wip" / "x.mp4")
    assert "made_under" not in json.loads(manifest.rows(other)[-1]["params"])


@pytest.mark.private_data
def test_own_pictures_quiz_takes_any_picture_but_a_check_in_page_s(tmp_path):
    """A quiz on the user's own pictures (images items with no model) shows pictures the pack never made; a picture
    of 03_wip/gates/ is never one of them."""
    run, pack = _quiz(tmp_path, replicate="missing")
    for item in pack["stages"][0]["items"]:
        item["model"] = None
    pack["models"], pack["cost"]["lines"], pack["cost"]["totals"]["ai_usd"] = [], [], 0
    _checked(run, pack)
    own = [f"03_wip/my_{name}.png" for name in CARDS]
    for rel in own:
        (run.path / rel).write_bytes(PNG)
    _rendered(run, "QuizGrid", _quiz_props(own), "03_wip/edit_v01_quizgrid_v01.mp4")
    assert organic_qa.takes_gap(run) is None
    (run.path / "03_wip" / "gates").mkdir()
    (run.path / "03_wip" / "gates" / "evidence.jpg").write_bytes(PNG)
    _rendered(run, "QuizGrid", _quiz_props([*own[:3], "03_wip/Gates/evidence.jpg"]), "03_wip/edit_v01_quizgrid_v02.mp4")
    gap = organic_qa.takes_gap(run)
    assert gap and "03_wip/Gates/evidence.jpg" in gap and "check-in pages' own" in gap, gap


# --- the copied look of a Recreate (OV3) --------------------------------------------------------------

@pytest.mark.private_data
def test_recreate_style_spec_needs_two_saved_evidence_videos(tmp_path):
    """P6 recreates the "Guess the _" quiz: its style spec (layout, font class, colours, number style, extras) is read
    from 2 distinct saved evidence videos of the idea's own trends, named by their URLs."""
    run, pack = _quiz(tmp_path)
    assert _check(run, pack, "recipe") == []
    spec = pack["style_spec"]
    p4_video = "https://www.tiktok.com/@creator_0101/video/7681503578850069790"   # saved, of P4's trend (petstore)
    for evidence, words in (([spec["evidence"][0]] * 2, "2 distinct"),
                            ([spec["evidence"][0]], "2 distinct"),
                            ([spec["evidence"][0], "https://www.tiktok.com/@someone/video/1"],
                             "https://www.tiktok.com/@someone/video/1 is not a saved video"),
                            ([spec["evidence"][0], p4_video],
                             "not a saved video of this idea's trends (250013b0)")):
        bad = copy.deepcopy(pack)
        bad["style_spec"]["evidence"] = evidence
        problems = _check(run, bad, "recipe")
        assert _fields(problems) == ["style_spec.evidence"] and words in problems[0].what, _what(problems)
    bad = copy.deepcopy(pack)
    del bad["style_spec"]["font_class"]
    bad["style_spec"]["colours"] = []
    problems = _check(run, bad, "recipe")
    assert _fields(problems) == ["style_spec.font_class", "style_spec.colours"], _what(problems)
    bad["style_spec"] = None
    assert _fields(_check(run, bad, "recipe")) == ["style_spec"]


@pytest.mark.private_data
def test_images_page_shows_the_look_beside_its_evidence(tmp_path, monkeypatch):
    """The images check-in shows the style spec's evidence thumbnails (found by URL among the idea's saved videos) and,
    beside them, the latest still of the composition (`tm render still`), so the look is judged before the render."""
    run, pack = _quiz(tmp_path)
    _checked(run, pack)
    fetched = []

    def fetch(url, dest, timeout=30):
        fetched.append(url)
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(PNG)
        return True

    monkeypatch.setattr(organic_gates.page, "fetch_image", fetch)
    _record(run, "donut", 1, ["donut_v01_0.png"], model="openai/gpt-image-2")
    still = _rendered(run, "QuizGrid", petstore.p6_props(), "03_wip/edit_v01_quizgrid_frame300_v01.png", kind="still",
                      frame=300)
    data = organic_gates.gate_json(run, "images")
    refs = data["items"][0]["refs"]
    assert [r["src"] for r in refs][-1] == still and "frame 300" in refs[-1]["caption"]
    creators = [url.split("/@")[1].split("/")[0] for url in pack["style_spec"]["evidence"]]   # the reference quiz pack's two
    assert len(creators) == 2 and [r["caption"] for r in refs][:2] == [f"Evidence video by @{c}" for c in creators]
    assert len(fetched) == 2 and data["plugin"]["missing_thumbnails"] == []
    # PR D review M4: a still of another composition, or made before the latest pack check, is not the look
    _rendered(run, "OrganicCaptions", {"segments": []}, "03_wip/edit_v01_organiccaptions_frame1_v01.png", kind="still",
              frame=1)
    assert organic_gates.gate_json(run, "images")["items"][0]["refs"][-1]["src"] == still
    s = state.load(run)
    s.checked["pack"]["at"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(timespec="seconds")
    state.save(run, s)
    refs = organic_gates.gate_json(run, "images")["items"][0]["refs"]
    assert [r["src"] for r in refs if r["src"].startswith("03_wip/edit_")] == []
    assert organic_gates.compositions(pack) == render.MOTION_COMPS
    assert organic_gates.compositions(_pack("m5_pl_pack.json")) == ("OrganicCaptions",)     # a talking piece's edit
    assert organic_gates.compositions(_pack("p3_sections_pack.json")) == ("OrganicCaptions",)


@pytest.mark.private_data
@pytest.mark.video
def test_real_render_quiz_grid(request, tmp_path, tmp_path_factory, monkeypatch):
    """P6's quiz props over four placeholder cards and a tone for the music: 1080×1920 at 30 fps, 15 s, with sound."""
    if not video_asked_for(request.config):
        pytest.skip("the real render runs with -m video (pixi run -e dev-full test-video)")
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    sys.path.insert(0, str(Path(__file__).parent / "tools"))
    from _media import ffmpeg

    cache = Path(os.environ.get("TM_TEST_REMOTION_CACHE")
                 or tmp_path_factory.getbasetemp().parent / "tm-remotion-cache")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(PLUGIN))
    monkeypatch.setattr(render.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(render, "_prefix", lambda: [])  # already inside an environment with Node
    monkeypatch.setattr(render.envtiers, "installed", lambda tier: True)
    render.setup()
    run = RunFolder.create(tmp_path / "Pulpit Łukasz", "pet p6", TODAY, playbook=ORGANIC_VIDEO)
    props = petstore.p6_props()
    for option, colour in zip(props["options"], ("orange", "teal", "purple", "olive")):
        option["img"] = f"03_wip/{option['img']}"
        (run.path / option["img"]).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c={colour}:s=1024x1024", "-frames:v", "1", str(run.path / option["img"])], check=True)
    props["music"]["src"] = "03_wip/music/tone.m4a"
    (run.path / props["music"]["src"]).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=15", "-c:a", "aac", str(run.path / props["music"]["src"])],
                   check=True)
    path = run.path / "03_wip" / "P6" / "edit_v01.props.json"
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    out = render.video(run, "QuizGrid", path, run.path / "03_wip" / "P6" / "edit_v01_render.mp4")
    info = common.probe(out)
    assert (info["width"], info["height"], info["fps"], info["has_audio"]) == (1080, 1920, 30.0, True)
    assert abs(info["duration"] - 15.0) < 0.1
