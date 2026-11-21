"""A stills video in any format, the storyboard on the beats and the full animation's own prompt (issue 138 item 2,
issue 141). A stills item's layout is a style module the agent builds (`tm organic atlas-prompt --layout`, prompt part
`layout.md`), its page inlines the picked pictures (`atlas_prompt.module_page`, `Player.picture`), and its render by
`tm organic animate` is the item's F2 output (`render.LAYOUT_COMP`). A storyboard draws one panel per beat, each at its
beat's end, the count read from the page (no `--panels`), and the animation's QA stills are taken at the same times
(`atlas.BEATS`). `tm organic atlas-prompt --animation --from <module>` writes the full animation's prompt, its length
the pack's `script.seconds`. No browser runs here: render.mjs and storyboard.mjs are stubbed (test_atlas's FakePopen),
and the layout check is conftest's clean answer."""

from __future__ import annotations

import base64
import json
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from test_atlas import FakePopen, light, popen, ready  # noqa: F401  (fixtures)
from tm import atlas, atlas_prompt, checkins, flow, manifest, organic_gates, organic_qa, paths, render, state, stepchecks
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO

PLUGIN = paths.bundled_data().parent
DATA = PLUGIN / "data" / "styles"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1024, 1536) + b"\x08\x06\x00\x00\x00"
JPEG = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
        + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 720, 1280) + b"\x03" + b"\x00" * 9)
SRT = "1\n00:00:00,000 --> 00:00:01,200\nfive\n\n2\n00:00:28,500 --> 00:00:29,040\ntips\n"


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture(autouse=True)
def _storyboard_script(request):
    if "light" in request.fixturenames:
        (request.getfixturevalue("light") / "atlas" / "storyboard.mjs").write_text("// storyboard", encoding="utf-8")


# --- player.js: a panel at its beat's end ---------------------------------------------------------------------

PANEL_TIMES = """
const vm = require("vm"), fs = require("fs");
const ctx = { window: { TM_PAGE: {} }, console, Promise, setTimeout };
ctx.window.window = ctx.window;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const P = ctx.window.Player, out = {};
P.style = { duration: 30.5, beats: [0, 3.1, 8.1, 13.2, 18.3] };
out.five = P.panelTimes(5); out.ends = P.beatEnds();
P.style = { duration: 12, beats: [0, 2, 4, 6, 8, 10], stills: [1, 3, 5, 7, 9, 11] };
out.stills = P.panelTimes(6);
P.style = { duration: 12, beats: [0, 2, 4, 6, 8, 10], stills: [1, 3, 5] };
out.short_stills = P.panelTimes(6);
P.style = { duration: 4, beats: [0, 0.3, 4] };
out.tiny = P.panelTimes(3);
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_a_panel_is_its_beats_end_and_stills_count_only_one_per_beat(tmp_path):
    """Issue 141 item 2: the 5-beat module of the report gets 5 panels, each 0.2 s before the next beat starts (the
    length - 0.2 s for the last), not 60 % into the beat; `stills` replace them only when they give one time per beat;
    a beat shorter than 0.4 s is shown at its middle, never before it starts."""
    script = tmp_path / "times.js"
    script.write_text(PANEL_TIMES, encoding="utf-8")
    done = subprocess.run(["node", str(script), str(DATA / "lib" / "player.js")], capture_output=True, text=True,
                          check=True)
    got = json.loads(done.stdout)
    assert got["five"] == pytest.approx([2.9, 7.9, 13.0, 18.1, 30.3]) and got["ends"] == got["five"]
    assert got["stills"] == [1, 3, 5, 7, 9, 11]
    assert got["short_stills"] == pytest.approx([1.8, 3.8, 5.8, 7.8, 9.8, 11.8])
    assert got["tiny"] == pytest.approx([0.15, 3.8, 3.99])


def test_the_reference_styles_keep_their_storyboard_moments():
    """The 49 styles' storyboards (and the previews, which are play mode and keep their own poster time): a style
    whose `stills` give one time per beat keeps exactly those panels; only a style without `stills` moves to its
    beats' ends. The previews' hashes (module + card) are untouched by player.js."""
    without = [s["styleId"] for s in atlas_prompt.styles()
               if "stills:" not in atlas_prompt.module_path(s).read_text(encoding="utf-8")]
    assert without == ["flat-explainer", "halftone-comic"]
    previews = atlas_prompt.previews()
    assert all(previews[s["styleId"]]["hash"] == atlas_prompt.preview_hash(s) for s in atlas_prompt.styles())
    assert "60 % into the beat" in (PLUGIN / "atlas" / "previews.mjs").read_text(encoding="utf-8")


# --- the prompt's parts ---------------------------------------------------------------------------------------

def test_the_animation_prompt_is_built_from_the_accepted_storyboards_module_at_the_packs_length():
    """Issue 141 item 3: animation.md in place of storyboard.md: no "then stop", the module named and appended, the
    user's notes listed, `duration` the pack's script.seconds while the voiceover ends earlier."""
    style = atlas_prompt.find_style("14")
    module = "Player.register({ id: 'kid', beats: [0, 3.1, 8.1, 13.2, 18.3] });"
    text = atlas_prompt.build(style, True, False, "five tips", SRT, "9:16", duration=30.5,
                              animation={"file": "03_wip/M1/storyboard_v02.js", "code": module,
                                         "notes": "- frame 2: the kid smiles"})
    assert "then stop" not in text.lower() and "{{" not in text
    assert "`duration` is 30.5 s, the video's length (the voiceover ends at 29.04 s)" in text
    assert "`03_wip/M1/storyboard_v02.js`" in text and "- frame 2: the kid smiles" in text
    assert text.rstrip().endswith(module + "\n```") and text.index("## The reference module") < text.index(module)
    plain = atlas_prompt.build(style, True, False, "five tips", SRT, "9:16",
                               animation={"file": "03_wip/M1/storyboard_v02.js", "code": module})
    assert atlas_prompt.NO_NOTES in plain and "`duration` is 29.04 s" in plain   # no pack length: the last cue
    with pytest.raises(ValueError, match="one of them"):
        atlas_prompt.build(style, storyboard=True, animation={"file": "x", "code": ""})
    board = (DATA / "prompt" / "storyboard.md").read_text(encoding="utf-8")
    assert "One beat per scene of the content" in board and "5 or 6" not in board
    assert "5 or 6" not in (DATA / "prompt" / "build.md").read_text(encoding="utf-8")


def test_the_layout_prompt_lists_the_pictures_and_the_trends_format():
    """Issue 138 item 2: layout.md gives the style spec, the picked pictures by name with their sizes and the
    Player.picture helper; the libraries' API is there too."""
    style = atlas_prompt.find_style("3")
    spec = {"layout": "numbered tips over full-frame photos", "font_class": "rounded sans", "colours": ["#ffcc00"],
            "number_style": "big yellow numerals", "extras": [], "evidence": ["https://example.com/a", "https://b"]}
    text = atlas_prompt.build(style, False, False, "five tips", None, "9:16", layout={
        "pictures": [{"name": "tip1", "file": "03_wip/tip1_v01_0.png", "width": 1024, "height": 1536},
                     {"name": "own", "file": "00_raw/me.jpg"}], "style_spec": spec})
    assert "- `tip1`: 03_wip/tip1_v01_0.png (1024x1536 px)" in text and "- `own`: 00_raw/me.jpg" in text
    assert '"numbered tips over full-frame photos"' in text and "Player.picture(ctx, name" in text
    assert "{{" not in text and "then stop" not in text.lower()
    bare = atlas_prompt.build(style, layout={"pictures": [], "style_spec": None})
    assert atlas_prompt.NO_SPEC in bare


def test_a_layout_page_inlines_its_pictures(tmp_path):
    """module_page puts each picture in the page's config as a data URL (the page opens with no other file), and the
    README documents the helper."""
    png, jpg = tmp_path / "a.png", tmp_path / "b.jpg"
    png.write_bytes(PNG)
    jpg.write_bytes(JPEG)
    page = atlas_prompt.module_page("Player.register({});", "P6 layout_v01", "9:16", pictures={"tip1": png, "me": jpg})
    config = json.loads(page.split("window.TM_PAGE = ", 1)[1].split(";</script>", 1)[0])
    assert config["mode"] == "play" and set(config["pictures"]) == {"tip1", "me"}
    assert config["pictures"]["tip1"] == "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")
    assert config["pictures"]["me"].startswith("data:image/jpeg;base64,")
    assert atlas_prompt.picture_size(png) == (1024, 1536) and atlas_prompt.picture_size(jpg) == (1280, 720)
    with pytest.raises(ValueError, match="not a picture"):
        atlas_prompt.data_uri(tmp_path / "x.gif")
    assert "Player.picture(ctx, name, x, y, w, h" in (DATA / "README.md").read_text(encoding="utf-8")
    assert '"panels": 0' in atlas_prompt.page(atlas_prompt.find_style("1"), "9:16", storyboard=True)


# --- the renderer ---------------------------------------------------------------------------------------------

def _renders(beats=3, code=0):
    def act(argv, kw):
        out = Path(argv[argv.index("--browser") - 1])
        out.write_bytes(b"mp4")
        shots = [out.with_name(f"{out.stem}_still_b{n:02d}.png") for n in range(1, beats + 1)]
        for f in shots:
            f.write_bytes(PNG)
        return code, json.dumps({"out": str(out), "duration": 12, "stills": [str(f) for f in shots]}) + "\n", "boom"
    return act


def test_beat_stills_are_asked_for_and_left_nowhere_when_the_render_fails(tmp_path, ready, popen):
    """atlas.render(..., stills=BEATS) asks render.mjs for one still per beat; they are `<stem>_still_bNN.png`, and a
    failed render leaves none of them."""
    page = tmp_path / "p.html"
    page.write_text("<html></html>", encoding="utf-8")
    popen.act = _renders()
    atlas.render(page, tmp_path / "anim_v01.mp4", stills=atlas.BEATS)
    argv = popen.calls[-1][0]
    assert argv[argv.index("--stills") + 1] == "beats"
    assert [p.name for p in atlas.beat_still_paths(tmp_path / "anim_v01.mp4")] == [
        "anim_v01_still_b01.png", "anim_v01_still_b02.png", "anim_v01_still_b03.png"]
    popen.act = _renders(code=1)
    with pytest.raises(Exception, match="failed"):
        atlas.render(page, tmp_path / "anim_v02.mp4", stills=atlas.BEATS)
    assert atlas.beat_still_paths(tmp_path / "anim_v02.mp4") == [] and not (tmp_path / "anim_v02.mp4").exists()
    popen.act = _renders()
    atlas.render(page, tmp_path / "anim_v03.mp4")                      # a creative brief's: the five shares
    argv = popen.calls[-1][0]
    assert argv[argv.index("--stills") + 1] == "0.06,0.3,0.55,0.8,0.95"


def test_the_storyboard_count_is_read_from_the_page(tmp_path, ready, popen):
    """storyboard.mjs gets no --panels: the page says how many it draws, and a panel already there is refused."""
    page = tmp_path / "s.html"
    page.write_text("<html></html>", encoding="utf-8")
    popen.act = lambda argv, kw: (0, json.dumps({"written": [], "panels": 5, "sizes": [[1080, 1920]] * 5}) + "\n", "")
    assert atlas.storyboard(page, tmp_path / "storyboard_v01")["panels"] == 5
    assert "--panels" not in popen.calls[-1][0]
    taken = tmp_path / "storyboard_v02"
    taken.mkdir()
    (taken / "panel_07.png").write_bytes(b"old")
    with pytest.raises(Exception, match="panel_07.png already exist"):
        atlas.storyboard(page, taken)
    script = (PLUGIN / "atlas" / "storyboard.mjs").read_text(encoding="utf-8")
    assert "STORYBOARD_PANELS" in script and '"--panels"' not in script


@pytest.mark.parametrize("command", ["storyboard", "atlas-page"])
def test_the_panels_option_is_gone(tmp_path, capsys, command):
    extra = ("--page", "x.html") if command == "storyboard" else ("--module", "x.js")
    code, out = _cli(capsys, "organic", command, "--run", str(tmp_path), "--item", "M1", *extra, "--panels", "5")
    assert code == 1 and "--panels is gone" in out["message"] and "read from the page" in out["message"], out


# --- a stills video's layout, through F2 (P6's four picked cards) ---------------------------------------------

LAYOUT = """(function () {
  "use strict";
  const BEATS = [0, 3, 6, 9];
  function draw(ctx, W, H, t) {
    const i = Math.min(3, Math.floor(t / 3));
    Player.picture(ctx, ["donut", "superman", "side", "bellyup"][i], 0, 0, W, H);
  }
  Player.register({ id: "p6-layout", name: "P6 layout", duration: 12, beats: BEATS, draw });
})();
"""


@pytest.fixture
def quiz(tmp_path, ready, popen):
    from test_organic_sections import _picked_cards

    run, pack = _picked_cards(tmp_path)
    return run, pack


def _layout_prompt(run, capsys, *extra):
    return _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "p6", "--style", "3", "--aspect",
                "9:16", *extra)


def _decide_up_to_video(run):
    """The check-ins due before F2's (the script draft, taste, pack, images) decided with their first choice."""
    cat = checkins.load(playbook=ORGANIC_VIDEO)
    for cid in ("script_draft", "taste", "pack", "images"):
        flow.decide(run, cid, cat.checkins[cid].choices[0], by="user", note="test data")


@pytest.mark.private_data
def test_a_stills_video_is_its_layout_built_drawn_and_taken_at_f2(quiz, capsys, popen):
    """Acceptance (issues 138 item 2 and 141 item 1): a stills item's prompt is a layout's (with its picked cards), its
    page inlines them, `tm organic animate` draws it with no storyboard, the video check-in shows it, and F2's step
    check passes; a card picked again needs a new render."""
    run, pack = quiz
    code, out = _layout_prompt(run, capsys, "--storyboard")
    assert code == 1 and "--layout" in out["message"] and "no storyboard" in out["message"], out
    code, out = _layout_prompt(run, capsys, "--layout")
    assert code == 0 and out["file"] == "03_wip/P6/prompt_v01.txt", out
    text = (run.path / out["file"]).read_text(encoding="utf-8")
    for name in ("donut", "superman", "side", "bellyup"):
        assert f"- `{name}`: 03_wip/{name}_v01_0.png" in text
    row = json.loads(next(r for r in manifest.rows(run) if r["file"] == out["file"])["params"])
    assert row["layout"] is True and row["pictures"] == {} and row["duration"] == pack["script"]["seconds"]

    gap = organic_qa.takes_gap(run)
    assert gap and "P6: it has no render" in gap and "tm organic animate" in gap and "--layout" in gap, gap
    (run.path / "03_wip" / "P6" / "layout_v01.js").write_text(LAYOUT, encoding="utf-8")
    page = ("organic", "atlas-page", "--run", str(run.path), "--item", "P6", "--module", "03_wip/P6/layout_v01.js")
    code, out = _cli(capsys, *page, "--storyboard")
    assert code == 1 and "no storyboard" in out["message"], out
    code, out = _cli(capsys, *page)
    assert code == 0 and out["file"] == "03_wip/P6/layout_v01.html", out
    assert out["pictures"] == {n: f"03_wip/{n}_v01_0.png" for n in ("donut", "superman", "side", "bellyup")}
    html = (run.path / out["file"]).read_text(encoding="utf-8")
    config = json.loads(html.split("window.TM_PAGE = ", 1)[1].split(";</script>", 1)[0])
    assert config["mode"] == "play" and sorted(config["pictures"]) == ["bellyup", "donut", "side", "superman"]
    assert all(v.startswith("data:image/png;base64,") for v in config["pictures"].values())

    code, out = _cli(capsys, "organic", "animate", "--run", str(run.path), "--item", "P6", "--page",
                     "03_wip/P6/explainer_v01.html")
    assert code == 1 and "is not in the run folder" in out["message"]   # the one path rule (issue 126)
    popen.act = _renders(beats=4)
    code, out = _cli(capsys, "organic", "animate", "--run", str(run.path), "--item", "P6", "--page",
                     "03_wip/P6/layout_v01.html")
    assert code == 0 and out["file"] == "03_wip/P6/renders/anim_v01.mp4" and out["storyboard"] is None, out
    assert len(out["stills"]) == 4 and popen.calls[-1][0][popen.calls[-1][0].index("--stills") + 1] == "beats"
    params = json.loads(next(r for r in manifest.rows(run) if r["file"] == out["file"])["params"])
    assert params["composition"] == render.LAYOUT_COMP and params["item"] == "P6"
    assert sorted(params["props"]["pictures"]) == sorted(f"03_wip/{n}_v01_0.png"
                                                         for n in ("donut", "superman", "side", "bellyup"))

    assert organic_qa.takes_gap(run) is None and stepchecks.run("takes_checked", run) is None
    assert organic_qa.chosen_motion(run, "P6")[0] == "03_wip/P6/renders/anim_v01.mp4"
    data = organic_gates.gate_json(run, "video")
    item = next(i for i in data["items"] if i["id"] == "motion-P6")
    assert [o["src"] for o in item["options"]] == ["03_wip/P6/renders/anim_v01.mp4"] and item["options"][0]["pick"]
    assert data["plugin"]["items"]["motion-P6"]["files"] == {item["options"][0]["id"]: "03_wip/P6/renders/anim_v01.mp4"}
    assert render.LAYOUT_COMP in organic_gates.compositions(pack)
    s = state.load(run)                    # the run at F2, its video check-in accepted: tm done F2 passes
    s.step, s.outputs = "F2", ["organic_video"]
    state.save(run, s)
    flow.set_level(run, "every_step")
    _decide_up_to_video(run)
    flow.decide(run, "video", "accept", by="user", note="the layout render")
    flow.complete(run, "F2")
    assert state.load(run).step != "F2"

    organic_qa.pick(run, "images", "donut", "03_wip/donut_v01_0.png", "the user's favourite", by="user")
    gap = organic_qa.takes_gap(run)
    assert gap and "rendered before donut was picked again" in gap, gap


@pytest.mark.private_data
def test_the_users_own_pictures_join_a_layout_only_when_the_pack_takes_them(quiz, capsys):
    run, _ = quiz
    (run.path / "00_raw").mkdir(exist_ok=True)
    (run.path / "00_raw" / "me.png").write_bytes(PNG)
    code, out = _layout_prompt(run, capsys, "--layout", "--picture", "me=00_raw/me.png")
    assert code == 2 and "none of the user's own pictures" in out["message"], out
    code, out = _layout_prompt(run, capsys, "--picture", "me=00_raw/me.png")
    assert code == 1 and "give --layout with it" in out["message"]
    code, out = _layout_prompt(run, capsys, "--layout", "--picture", "bad name=00_raw/me.png")
    assert code == 1 and "NAME=FILE" in out["message"]


# --- the storyboard's beats and the full animation's prompt (ExampleEdu's M1) --------------------------------

@pytest.fixture
def m1(tmp_path, capsys, ready, popen):
    from test_atlas_prompt import _m1_run

    run = _m1_run(tmp_path, capsys)
    assert _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "14",
                "--voiceover", "--storyboard", "--aspect", "9:16")[0] == 0
    return run


def _frames(run, n):
    rows = [{"panel": k, "from": 3 * (k - 1), "to": 3 * k, "line": f"line {k}", "scene": "s", "overlay": ""}
            for k in range(1, n + 1)]
    (run.path / "03_wip" / "M1" / "frames_v01.json").write_text(json.dumps(rows), encoding="utf-8")


@pytest.mark.private_data
def test_a_storyboard_module_needs_one_beat_per_scene_of_the_frames_list(m1, capsys):
    run = m1
    _frames(run, 5)
    module = "Player.register({ id: 'm1', name: 'M1', duration: 18, beats: [0, 3, 6, 9, 12, 15], draw() {} });"
    (run.path / "03_wip" / "M1" / "storyboard_v01.js").write_text(module, encoding="utf-8")
    page = ("organic", "atlas-page", "--run", str(run.path), "--item", "M1", "--storyboard", "--module")
    code, out = _cli(capsys, *page, "03_wip/M1/storyboard_v01.js")
    assert code == 1 and "The module has 6 beats and the frames list 5 scenes" in out["message"], out
    assert "one beat per scene" in out["message"] and not (run.path / "03_wip" / "M1" / "storyboard_v01.html").exists()
    (run.path / "03_wip" / "M1" / "storyboard_v02.js").write_text(module.replace("12, 15", "12"), encoding="utf-8")
    code, out = _cli(capsys, *page, "03_wip/M1/storyboard_v02.js")
    assert code == 0 and '"panels": 0' in (run.path / out["file"]).read_text(encoding="utf-8"), out
    reference = atlas_prompt.module_path(atlas_prompt.find_style("14")).read_text(encoding="utf-8")
    (run.path / "03_wip" / "M1" / "storyboard_v03.js").write_text(reference, encoding="utf-8")   # beats: BEATS
    assert _cli(capsys, *page, "03_wip/M1/storyboard_v03.js")[0] == 0     # not read from the code: not refused here
    assert _cli(capsys, *page, "03_wip/M1/storyboard_v04.js")[0] == 1


@pytest.mark.private_data
def test_the_full_animations_prompt_comes_from_the_accepted_storyboards_module(m1, capsys, popen):
    """Issue 141 item 3: `--animation` is refused until the storyboard is accepted, takes the module the accepted sheet
    was drawn from (any other --from is refused), the user's notes on it from the images check-in, and the pack's
    length."""
    from test_atlas_prompt import _draws_storyboard

    run = m1
    module = atlas_prompt.module_path(atlas_prompt.find_style("14")).read_text(encoding="utf-8")
    (run.path / "03_wip" / "M1" / "storyboard_v01.js").write_text(module, encoding="utf-8")
    argv = ("organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "14", "--voiceover",
            "--aspect", "9:16", "--animation")
    code, out = _cli(capsys, *argv)
    assert code == 2 and "accepted storyboard" in out["message"], out
    assert _cli(capsys, "organic", "atlas-page", "--run", str(run.path), "--item", "M1", "--storyboard", "--module",
                "03_wip/M1/storyboard_v01.js")[0] == 0
    popen.act = _draws_storyboard(panels=6)
    code, out = _cli(capsys, "organic", "storyboard", "--run", str(run.path), "--item", "M1", "--page",
                     "03_wip/M1/storyboard_v01.html")
    assert code == 0 and out["panels"] == 6 and len(out["files"]) == 7, out
    sheet = out["sheet"]
    assert _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file",
                sheet, "--reason", "kept")[0] == 0
    (run.path / "03_wip" / "decisions_gate_images_v01.json").write_text(json.dumps({"decisions": {
        "storyboard-M1": {"kind": "storyboard", "name": "M1", "action": "accept", "note": "a bigger title",
                          "frame_notes": {"panel_02": "the kid smiles"}}}}), encoding="utf-8")
    code, out = _cli(capsys, *argv)
    assert code == 0 and out["file"] == "03_wip/M1/prompt_v02.txt" and out["duration"] == 25, out
    text = (run.path / out["file"]).read_text(encoding="utf-8")
    assert "then stop" not in text.lower() and "`03_wip/M1/storyboard_v01.js`" in text
    assert "- a bigger title" in text and "- panel 02: the kid smiles" in text and "`duration` is 25 s" in text
    (run.path / "03_wip" / "M1" / "storyboard_v02.js").write_text(module, encoding="utf-8")
    code, out = _cli(capsys, *argv, "--from", "03_wip/M1/storyboard_v02.js")
    assert code == 1 and "was drawn from 03_wip/M1/storyboard_v01.js" in out["message"], out
    assert _cli(capsys, *argv, "--from", "03_wip/M1/storyboard_v01.js")[0] == 0
    code, out = _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "14",
                     "--from", "03_wip/M1/storyboard_v01.js")
    assert code == 1 and "give --animation with it" in out["message"]
