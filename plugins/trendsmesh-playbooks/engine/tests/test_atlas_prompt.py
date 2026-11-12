"""Animation in organic video (plan Task 19): our style library and build prompt (`tm.atlas_prompt`, `data/styles/`,
`tm organic atlas-styles`, `tm organic atlas-prompt`), the storyboard drawn by the Atlas renderer (`atlas.storyboard`,
`tm organic storyboard`), its check-in on the images page or by rule, and the full animation drawn only from an
accepted storyboard (`tm organic animate`). An animation as an AI video starts and passes the pack check only where
the renderer can draw (PB02's `animatic` tier, its setup and a browser). The real drawings of our styles (every
style's storyboard, two styles rendered) need Node and a browser and run only when the `video` mark is asked for
(`pixi run -e dev-full test-video`)."""

from __future__ import annotations

import difflib
import json
import shutil
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import exampleedu
import private
from conftest import remotion_cache, video_asked_for
from test_atlas import FakePopen, light, popen, ready  # noqa: F401  (fixtures)
from test_organic_pack import _production
from test_organic_proposals import _checked, _decided, _doc, _idea_run, _production_runs, _start
from tm import atlas, atlas_prompt, config, envtiers, manifest, organic_gates, organic_pack, organic_qa, paths, render, \
    state, stepchecks
from tm.cli import main
from tm.stops import AGAIN
from tm.tools import _common as common

PLUGIN = paths.bundled_data().parent
REPO = PLUGIN.parents[1]
DATA = PLUGIN / "data" / "styles"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "organic"
NOT_INSTALLED = "Drawing animatics needs the 'animatic' tools, which are not installed or not set up yet."
NO_BROWSER = "Drawing animatics needs Google Chrome or Microsoft Edge (or Chromium on Linux) on this computer"
REAL_LAYOUT = atlas.layout          # conftest answers clean outside the video tests; these tests run it
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 1920) + b"\x08\x06\x00\x00\x00"


@pytest.fixture(autouse=True)
def _storyboard_script(request):
    """PB02's `light` plugin root, with storyboard.mjs beside its render.mjs: a bundled script that is missing is a
    stop (Task 19 review M2)."""
    if "light" in request.fixturenames:
        root = request.getfixturevalue("light")
        (root / "atlas" / "storyboard.mjs").write_text("// storyboard", encoding="utf-8")


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r", "")


def _m1_pack() -> dict:
    return json.loads((FIXTURES / "m1_animation_pack.json").read_text(encoding="utf-8"))


def _m1_run(tmp_path, capsys, pack=None, n=1):
    """ExampleEdu's M1 as a production run (an AI video, ElevenLabs there) with its animation pack checked at the
    pack stage, M1's content and word SRT copied into its 03_wip/M1/."""
    run = exampleedu.build(tmp_path / "ws")
    m1 = next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m1")
    _production(run, m1, exampleedu.CHANNEL)
    folder = run.path / "03_wip" / "M1"
    folder.mkdir(parents=True)
    for name in ("content_v01.txt", "vo_words_v01.srt"):          # as the plugin's run would hold them: aliased
        (folder / name).write_bytes(private.alias(exampleedu.m1_file(name).read_bytes()))
    _check(run, capsys, pack or _m1_pack(), n)
    return run


def _check(run, capsys, pack, n):
    rel = f"03_wip/pack_v{n:02d}.json"
    (run.path / rel).write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    code, out = _cli(capsys, "organic", "pack", "check", "--run", str(run.path), "--file", rel, "--stage", "pack",
                     "--today", "2026-11-07")
    assert code == 0, out
    return out


def _page(run, name="storyboard_v01.html") -> str:
    """A page the subagent wrote: here style 14's own reference animation, as a storyboard or as the animation."""
    rel = f"03_wip/M1/{name}"
    page = atlas_prompt.page(atlas_prompt.find_style("14"), "9:16", storyboard="storyboard" in name)
    (run.path / rel).write_text(page, encoding="utf-8")
    return rel


def _draws_storyboard(code=0, stderr="", panels=6, written=None, size=(1080, 1920)):
    """What storyboard.mjs leaves: its panels and sheet in the folder it was given, then its summary line."""
    def act(argv, kw):
        out = Path(argv[argv.index("--browser") - 1])
        out.mkdir(parents=True, exist_ok=True)
        files = atlas.panel_paths(out, panels)
        for f in files[:written]:
            f.write_bytes(PNG)
        summary = {"written": [str(f) for f in files], "sizes": [list(size)] * panels, "page_errors": []}
        return code, (json.dumps(summary) + "\n") if code == 0 else "", stderr
    return act


def _draws_animation(code=0):
    def act(argv, kw):
        out = Path(argv[argv.index("--browser") - 1])
        out.write_bytes(b"mp4")
        for still in atlas.still_paths(out):
            still.write_bytes(PNG)
        summary = {"out": str(out), "duration": 25.0, "frames": 750, "size": [1080, 1920], "sound": True,
                   "render_s": 149, "page_errors": []}
        return code, json.dumps(summary) + "\n", ""
    return act


def _storyboard(run, capsys, page="03_wip/M1/storyboard_v01.html"):
    return _cli(capsys, "organic", "storyboard", "--run", str(run.path), "--item", "M1", "--page", page)


def _animate(run, capsys, page="03_wip/M1/explainer_v01.html", *extra):
    return _cli(capsys, "organic", "animate", "--run", str(run.path), "--item", "m1", "--page", page, *extra)


# --- the library and the build prompt ----------------------------------------------------------------------------

FAMILIES = {"Clean explainer", "Painterly", "Paper and craft", "Hand-drawn", "Cosmic", "Light and imaging",
            "Illustration", "Print", "Dimensional", "Retro digital", "Retro desktop", "Design movements", "Data",
            "Type and pattern"}
CARD_KEYS = {"order", "styleId", "name", "category", "description", "suits", "look", "palette", "fonts", "finish",
             "motion", "explaining", "sound", "avoid"}


def _first_line(part: str) -> str:
    """The first line of a prompt part with nothing to fill in."""
    return next(line for line in _text(DATA / "prompt" / part).splitlines() if line.strip() and "{{" not in line)


def test_the_library_has_a_card_and_a_reference_animation_per_style():
    """data/styles/ (issue #75, ours): 39 styles numbered from 1, one per family at least, each with a full card
    and its reference animation; the library, the page template and the prompt's parts; all pinned LF."""
    styles = atlas_prompt.styles()
    assert len(styles) == 39 and [s["order"] for s in styles] == list(range(1, len(styles) + 1))
    assert len({s["styleId"] for s in styles}) == len(styles) and {s["category"] for s in styles} == FAMILIES
    for s in styles:
        assert set(s) >= CARD_KEYS and 5 <= len(s["palette"]) <= 8 and s["fonts"], s["styleId"]
        assert atlas_prompt.module_path(s).is_file(), s["styleId"]
    for rel in ("lib/brush.js", "lib/sound.js", "lib/player.js", "lib/page.html", "prompt/build.md",
                "prompt/voiceover.md", "prompt/storyboard.md", "README.md"):
        assert (DATA / rel).is_file(), rel
    assert sorted(p.name for p in (DATA / "styles").iterdir()) == sorted(
        atlas_prompt.module_path(s).name for s in styles)
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "plugins/trendsmesh-playbooks/data/styles/** text eol=lf" in lines
    assert "plugins/trendsmesh-playbooks/atlas/storyboard.mjs text eol=lf" in lines
    assert atlas_prompt.ROOT == DATA


@pytest.mark.private_data
def test_prompt_for_m1_in_style_14(tmp_path, capsys, animatic_ready):
    """Style 14 with --voiceover --storyboard --aspect 9:16, M1's content and word SRT: the three parts of the prompt,
    the content and the SRT filled in, the 9:16 frame, the card, then the libraries' API and style 14's reference
    animation, written as 03_wip/M1/prompt_v01.txt (never over an earlier one) with its manifest row."""
    style = atlas_prompt.find_style("14")
    assert (style["styleId"], style["name"]) == ("halftone-comic", "Halftone Comic")
    content, srt = exampleedu.m1_text("content_v01.txt"), exampleedu.m1_text("vo_words_v01.srt")
    built = atlas_prompt.build(style, True, True, content, srt, "9:16")
    assert content.strip() in built and srt.strip() in built and "{{" not in built
    assert "1080x1920" in built and atlas_prompt.CONTENT_PH not in built and atlas_prompt.SRT_PH not in built
    for part in ("build.md", "voiceover.md", "storyboard.md"):
        assert _first_line(part) in built, part
    module = _text(atlas_prompt.module_path(style)).rstrip()
    assert built.index("Halftone Comic (Print)") < built.index(atlas_prompt.api()) < built.index(module)
    run = _m1_run(tmp_path, capsys)
    argv = ("organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "halftone-comic",
            "--voiceover", "--storyboard", "--aspect", "9:16", "--content", "03_wip/M1/content_v01.txt", "--srt",
            "03_wip/M1/vo_words_v01.srt")
    code, out = _cli(capsys, *argv)
    assert (code, out["file"], out["item"], out["style"]) == (0, "03_wip/M1/prompt_v01.txt", "M1", "halftone-comic")
    assert _text(run.path / out["file"]) == built and b"\r" not in (run.path / out["file"]).read_bytes()
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert row["source"] == "tm organic atlas-prompt" and row["parent"] == "03_wip/M1/content_v01.txt"
    assert json.loads(row["params"])["style"] == "14 halftone-comic"
    code, out = _cli(capsys, *argv)
    assert out["file"] == "03_wip/M1/prompt_v02.txt"                     # the next version, never over v01
    code, out = _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "M1", "--style", "14",
                     "--srt", "03_wip/M1/vo_words_v01.srt")
    assert code == 1 and "--voiceover" in out["message"]


def test_the_prompt_is_smaller_than_the_old_catalogues():
    """Claude gets the libraries' API, not their code, and writes only a style module: every build prompt stays under
    the 90,000 characters the old catalogue's took, and none carries brush.js, sound.js or player.js."""
    libs = [_text(DATA / "lib" / n) for n in atlas_prompt.LIB]
    for style in atlas_prompt.styles():
        text = atlas_prompt.build(style, True, True, "topic", "1\n00:00:00,000 --> 00:00:01,000\nhi", "9:16")
        assert len(text) < 90_000, (style["styleId"], len(text))
        assert _text(atlas_prompt.module_path(style)).rstrip() in text and atlas_prompt.api() in text
        assert not any(lib[2000:2400] in text for lib in libs), style["styleId"]


@pytest.mark.private_data
def test_atlas_page_builds_the_page_of_a_module(tmp_path, capsys, animatic_ready):
    """tm organic atlas-page: the module the subagent wrote becomes <stem>.html beside it, at the latest prompt's
    frame, in storyboard or play mode, the libraries and the fonts <link> inlined; never over a page, never from
    outside the item's folder, never before a prompt."""
    run = _m1_run(tmp_path, capsys)
    module = _text(atlas_prompt.module_path(atlas_prompt.find_style("14")))
    (run.path / "03_wip" / "M1" / "storyboard_v01.js").write_text(module, encoding="utf-8")
    page = ("organic", "atlas-page", "--run", str(run.path), "--item", "m1", "--module", "03_wip/M1/storyboard_v01.js",
            "--storyboard")
    code, out = _cli(capsys, *page)
    assert code == 1 and "tm organic atlas-prompt first" in out["message"]
    assert _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "14",
                "--voiceover", "--storyboard", "--aspect", "9:16")[0] == 0
    code, out = _cli(capsys, *page)
    assert (code, out["file"], out["item"]) == (0, "03_wip/M1/storyboard_v01.html", "M1"), out
    html = _text(run.path / out["file"])
    assert '"width": 1080, "height": 1920, "mode": "storyboard", "panels": 6, "voiceover": true' in html
    assert module.rstrip() in html and all(_text(DATA / "lib" / n).rstrip() in html for n in atlas_prompt.LIB)
    assert '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?' in html
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert row["source"] == "tm organic atlas-page" and row["parent"] == "03_wip/M1/storyboard_v01.js"
    code, out = _cli(capsys, *page)
    assert code == 1 and "never overwritten" in out["message"]
    (run.path / "03_wip" / "M1" / "explainer_v01.js").write_text(module, encoding="utf-8")
    code, out = _cli(capsys, *page[:-2], "03_wip/M1/explainer_v01.js")
    assert code == 0 and '"mode": "play", "panels": 0' in _text(run.path / out["file"])
    (run.path / "03_wip" / "stray.js").write_text(module, encoding="utf-8")
    code, out = _cli(capsys, *page[:-2], "03_wip/stray.js")
    assert code == 1 and "not in 03_wip/M1/" in out["message"]
    assert not (run.path / "03_wip" / "stray.html").exists()


@pytest.mark.private_data
def test_atlas_page_tells_claude_what_the_layout_check_found(tmp_path, capsys, animatic_ready, monkeypatch):
    """tm organic atlas-page runs the layout check on the module's play page, at the prompt's frame, even for a
    storyboard page: findings come back as sentences to fix before drawing, and no draw command is offered."""
    run = _m1_run(tmp_path, capsys)
    module = _text(atlas_prompt.module_path(atlas_prompt.find_style("14")))
    (run.path / "03_wip" / "M1" / "storyboard_v01.js").write_text(module, encoding="utf-8")
    assert _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "14",
                "--storyboard", "--aspect", "9:16")[0] == 0
    seen = []

    def found(page):
        seen.append(_text(page))
        return {"min_label_px": 41, "small": [{"text": "Step 2", "px": 30.0, "min": 41, "t": 4.0}],
                "outside": [{"text": "Key", "t": 6.0, "box": [0, 1700, 90, 1760], "side": ["bottom"]}],
                "empty": [{"t": 8.0, "from": 900, "to": 1300}], "texture": 0, "page_errors": []}

    monkeypatch.setattr(atlas, "layout", found)
    code, out = _cli(capsys, "organic", "atlas-page", "--run", str(run.path), "--item", "m1", "--module",
                     "03_wip/M1/storyboard_v01.js", "--storyboard")
    assert code == 0 and out["layout"]["checked"] is True and len(out["layout"]["problems"]) == 3, out
    assert '"Step 2" is at most 30.0 px; labels need at least 41 px' in out["message"]
    assert "outside the safe area (bottom)" in out["message"] and "empty from y 900 to 1300 px" in out["message"]
    assert "fix the module" in out["message"] and "Draw it with" not in out["message"]
    assert '"mode": "play"' in seen[0] and '"width": 1080, "height": 1920' in seen[0]
    monkeypatch.setattr(atlas, "missing", lambda: ("tier", "x", "y"))
    (run.path / "03_wip" / "M1" / "storyboard_v02.js").write_text(module, encoding="utf-8")
    code, out = _cli(capsys, "organic", "atlas-page", "--run", str(run.path), "--item", "m1", "--module",
                     "03_wip/M1/storyboard_v02.js", "--storyboard")
    assert code == 0 and out["layout"]["checked"] is False and "was not checked" in out["message"]


def test_layout_runs_layout_check_mjs(tmp_path, ready, popen, monkeypatch):
    """atlas.layout: layout_check.mjs copied beside node_modules and run on the page with the user's browser; its
    JSON summary returned; a missing page is an error."""
    (ready / "atlas" / "layout_check.mjs").write_text("// layout", encoding="utf-8")
    page = tmp_path / "anim" / "explainer v01.html"
    page.parent.mkdir()
    page.write_text("<html></html>", encoding="utf-8")
    summary = {"size": [1280, 720], "min_label_px": 27, "small": [], "outside": [], "empty": [], "texture": 2,
               "page_errors": []}
    popen.act = lambda argv, kw: (0, "Rendering\n" + json.dumps(summary) + "\n", "")
    assert REAL_LAYOUT(page) == summary
    argv = popen.calls[-1][0]
    assert Path(argv[argv.index("node") + 1]) == atlas.work_dir() / "layout_check.mjs"
    assert argv[argv.index("node") + 2] == str(page.resolve()) and argv[argv.index("--browser") + 1] == str(Path("/Apps/Google Chrome"))
    assert (atlas.work_dir() / "layout_check.mjs").read_text() == "// layout"
    with pytest.raises(common.ToolError, match="does not exist"):
        REAL_LAYOUT(tmp_path / "nope.html")
    assert atlas.layout_problems(summary) == []


def test_the_modes_and_frames_of_the_prompt():
    """No mode: build.md alone, at 1280x720; a mode adds its part; each frame says its own size and safe area."""
    style = atlas_prompt.find_style("3")
    plain = atlas_prompt.build(style)
    assert "1280x720" in plain and atlas_prompt.CONTENT_PH in plain
    assert _first_line("voiceover.md") not in plain and _first_line("storyboard.md") not in plain
    for aspect, (w, h) in atlas_prompt.ASPECTS.items():
        text = atlas_prompt.build(style, aspect=aspect)
        top, bottom = atlas_prompt.safe_area(aspect)
        assert f"{w}x{h}" in text and f"{top}" in text and f"{bottom}" in text, aspect
    assert atlas_prompt.build(style, extra="KEEP THE BAND FREE").count("KEEP THE BAND FREE") == 1


def test_the_reference_says_the_prompts_safe_zone():
    """Task 19 review M4: references/animation-styles.md's top band is the prompt's (nothing important in the top 269
    px of 1920), not another number."""
    top, bottom = atlas_prompt.safe_area("9:16")
    assert (top, bottom) == (269, 384)
    text = _text(PLUGIN / "references" / "animation-styles.md")
    assert f"below y {top}," in text and "below y 260" not in text


def test_unknown_style_lists_closest(capsys):
    with pytest.raises(ValueError) as no:
        atlas_prompt.find_style("halftone")
    assert "14 halftone-comic (Halftone Comic)" in str(no.value) and "tm organic atlas-styles" in str(no.value)
    with pytest.raises(ValueError, match="Unknown style '99'"):
        atlas_prompt.find_style("99")
    assert atlas_prompt.find_style(" 1 ")["styleId"] == "flat-explainer"
    code, out = _cli(capsys, "organic", "atlas-styles")
    assert code == 0 and [s["order"] for s in out["styles"]] == list(range(1, len(atlas_prompt.styles()) + 1))
    assert set(out["styles"][13]) == {"order", "styleId", "name", "category", "description", "suits"}


def test_every_style_builds_in_every_mode_and_as_a_page():
    for style in atlas_prompt.styles():
        for vo, sb in ((False, False), (True, False), (False, True), (True, True)):
            text = atlas_prompt.build(style, vo, sb, "topic", "1\n00:00:00,000 --> 00:00:01,000\nhi", "9:16")
            assert "1080x1920" in text and "{{" not in text and style["name"] in text, style["styleId"]
        for storyboard in (False, True):
            html = atlas_prompt.page(style, "9:16", storyboard)
            assert html.lstrip().lower().startswith("<!doctype html") and "{{" not in html, style["styleId"]
            assert '"mode": "storyboard"' in html if storyboard else '"mode": "play"' in html


# --- the animation needs the Atlas renderer -----------------------------------------------------------------------

@pytest.mark.private_data
@pytest.mark.parametrize("tier,browser,says", [(False, Path("chrome"), NOT_INSTALLED), (True, None, NO_BROWSER)])
def test_animation_pack_needs_animatic_tier(tmp_path, capsys, monkeypatch, tier, browser, says):
    """Drift check 13: no doctor row can say a pack animates, so the pack check holds an animation to the `animatic`
    tier (its setup included) and a browser, in PB02's words; with them it passes."""
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: tier and t == "animatic")
    monkeypatch.setattr(atlas, "find_browser", lambda: browser)
    run = exampleedu.build(tmp_path / "ws")
    _production(run, next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m1"), exampleedu.CHANNEL)
    pack = _m1_pack()
    problems = organic_pack.check(run, pack, config.load(run), stage="pack", today=datetime(2026, 11, 7).date())
    assert [p.field for p in problems] == ["production"], problems
    assert problems[0].what.startswith(f"This idea is an animation. {says}") and "script to film" in problems[0].todo
    assert ("tm env install animatic --yes" in problems[0].todo) is (not tier)
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path("/Apps/Google Chrome"))
    assert organic_pack.check(run, pack, config.load(run), stage="pack", today=datetime(2026, 11, 7).date()) == []


@pytest.mark.private_data
def test_animation_pack_needs_the_animatic_setup_done(tmp_path, monkeypatch):
    """Task 19 review M6: the animatic environment installed but its node package not set up (`atlas.setup_done`) is
    the same refusal, read through the real `envtiers.installed`."""
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: True)
    monkeypatch.setattr(render, "setup_done", lambda: True)   # the video tier's Remotion setup (#4)
    monkeypatch.setattr(atlas, "setup_done", lambda: False)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path("/Apps/Google Chrome"))
    assert envtiers.installed("animatic") is False and envtiers.installed("video") is True
    run = exampleedu.build(tmp_path / "ws")
    _production(run, next(p for p in exampleedu.proposals()["proposals"] if p["id"] == "m1"), exampleedu.CHANNEL)
    problems = organic_pack.check(run, _m1_pack(), config.load(run), stage="pack", today=datetime(2026, 11, 7).date())
    assert [p.field for p in problems] == ["production"] and NOT_INSTALLED in problems[0].what, problems
    monkeypatch.setattr(atlas, "setup_done", lambda: True)
    assert organic_pack.check(run, _m1_pack(), config.load(run), stage="pack", today=datetime(2026, 11, 7).date()) == []


@pytest.mark.private_data
def test_animation_ai_video_starts_only_where_it_can_be_drawn(tmp_path, capsys, monkeypatch):
    """PR C's refusal is lifted for an animation: it starts as an AI video when the tier, its setup and a browser are
    there; without them the start stops in PB02's words, before any folder, and the idea can be a script."""
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: False)
    run = _idea_run(tmp_path)
    _checked(run, capsys)
    _decided(run, {"m1": _doc(output="video")})
    code, out = _start(capsys, run)
    assert code == 2 and out["message"].endswith(AGAIN + ".") and _production_runs(run) == []
    assert "is an animation, and it cannot be drawn here" in out["message"] and NOT_INSTALLED in out["message"]
    assert "tm env install animatic --yes" in out["message"] and "script to film" in out["message"]
    assert "later version" not in out["message"]
    # issue #87: everything the animation's route needs, in one question, and no breakdown or AI video tools
    assert "everything it needs" in out["message"] and "tm env install video --yes" in out["message"]
    assert "breakdown" not in out["message"] and "tm env install ai " not in out["message"]
    monkeypatch.setattr(atlas.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path("/Apps/Google Chrome"))
    code, out = _start(capsys, run)
    assert code == 0 and [(x["proposal"], x["output"]) for x in out["started"]] == [("m1", "video")], out


# --- the storyboard -----------------------------------------------------------------------------------------------

@pytest.mark.private_data
def test_storyboard_stops_without_browser_and_renders_nothing(tmp_path, capsys, ready, popen, monkeypatch):
    run = _m1_run(tmp_path, capsys)                                     # checked while the browser was there
    monkeypatch.setattr(atlas, "find_browser", lambda: None)
    page = _page(run)
    with pytest.raises(common.ToolStop) as stop:
        atlas.storyboard(run.path / page, run.path / "03_wip" / "M1" / "storyboard_v01")
    assert NO_BROWSER in str(stop.value) and "Nothing was rendered." in str(stop.value)
    code, out = _storyboard(run, capsys, page)
    assert (code, out["status"]) == (2, "stop") and NO_BROWSER in out["message"], out
    assert out["message"].endswith("The run continues from the same place.")
    assert popen.calls == [] and not (run.path / "03_wip" / "M1" / "storyboard_v01").exists()


@pytest.mark.private_data
def test_storyboard_runs_storyboard_mjs_and_never_overwrites(tmp_path, capsys, ready, popen):
    """One argv list in the video environment (the panels, the browser), the next storyboard_vNN folder each time;
    files already there are refused; a failed drawing leaves no panel and no empty folder."""
    run = _m1_run(tmp_path, capsys)
    page = _page(run)
    popen.act = _draws_storyboard()
    code, out = _storyboard(run, capsys, page)
    assert code == 0, out
    assert out["files"] == [f"03_wip/M1/storyboard_v01/panel_{n:02d}.png" for n in range(1, 7)] + [
        "03_wip/M1/storyboard_v01/sheet.png"] and out["sheet"] == "03_wip/M1/storyboard_v01/sheet.png"
    argv, kw = popen.calls[0]
    assert isinstance(argv, list) and "shell" not in kw and (kw.get("start_new_session") or kw.get("creationflags"))
    assert argv[len(render._prefix()):] == [
        "node", str(atlas.work_dir() / "storyboard.mjs"), str((run.path / page).resolve()),
        str((run.path / "03_wip" / "M1" / "storyboard_v01").resolve()), "--browser", str(Path("/Apps/Google Chrome")),
        "--panels", "6"]
    assert {r["file"] for r in manifest.rows(run) if r["source"] == "tm organic storyboard"} == set(out["files"])
    code, out = _storyboard(run, capsys, page)
    assert out["sheet"] == "03_wip/M1/storyboard_v02/sheet.png"            # the next version
    taken = run.path / "03_wip" / "M1" / "storyboard_v03"
    taken.mkdir()
    (taken / "panel_02.png").write_bytes(b"old")
    with pytest.raises(common.ToolError, match="panel_02.png already exist"):
        atlas.storyboard(run.path / page, taken)
    assert (taken / "panel_02.png").read_bytes() == b"old"
    popen.act = _draws_storyboard(1, stderr="Error: the page has no canvas with id \"p4\"", written=3)
    code, out = _storyboard(run, capsys, page)
    assert code == 1 and 'no canvas with id "p4"' in out["message"]
    assert not (run.path / "03_wip" / "M1" / "storyboard_v04").exists()
    code, out = _cli(capsys, "organic", "storyboard", "--run", str(run.path), "--item", "M5", "--page", page)
    assert code == 2 and "not an animation of the checked pack (its animated items: M1)" in out["message"]


@pytest.mark.parametrize("system,root,browser,flag", [
    ("linux", False, "/usr/bin/google-chrome", False),
    ("linux", True, "/usr/bin/google-chrome", True),
    ("linux", False, "/data/remotion/node_modules/.remotion/chrome-headless-shell/linux64/"
                     "chrome-headless-shell-linux64/chrome-headless-shell", True),
    ("macos", True, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", False),
    ("windows", False, "C:/x/chrome-headless-shell-win64/chrome-headless-shell.exe", False),
])
def test_storyboard_passes_no_sandbox_only_when_atlas_says(tmp_path, ready, popen, monkeypatch, system, root, browser,
                                                           flag):
    monkeypatch.setattr(atlas, "_system", lambda: system)
    monkeypatch.setattr(atlas, "_is_root", lambda: root)
    monkeypatch.setattr(atlas, "find_browser", lambda: Path(browser))
    page = tmp_path / "storyboard_v01.html"
    page.write_text("<html></html>", encoding="utf-8")
    popen.act = _draws_storyboard()
    atlas.storyboard(page, tmp_path / "storyboard_v01")
    assert ("--no-sandbox" in popen.calls[0][0]) is flag and (popen.calls[0][0][-1] == "--no-sandbox") is flag
    assert atlas.needs_no_sandbox(Path(browser)) is flag


@pytest.mark.parametrize("said", ["[1107/101010.1:FATAL:zygote_host_impl_linux.cc(127)] No usable sandbox!",
                                  "Running as root without --no-sandbox is not supported."])
def test_a_storyboard_sandbox_refusal_is_pb02s_stop(tmp_path, ready, popen, said):
    page = tmp_path / "storyboard_v01.html"
    page.write_text("<html></html>", encoding="utf-8")
    popen.act = _draws_storyboard(1, stderr="Error: Failed to launch the browser process!\n" + said, written=2)
    with pytest.raises(common.ToolStop) as stop:
        atlas.storyboard(page, tmp_path / "out")
    text = str(stop.value)
    assert "sandbox" in text and "Nothing was rendered." in text and "not as root" in text
    assert text.endswith("The run continues from the same place.") and not any((tmp_path / "out").iterdir())


def test_a_hung_storyboard_is_stopped_under_the_time_limit(tmp_path, ready, monkeypatch):
    """storyboard.mjs runs under atlas.TIMEOUT_S, its process tree killed on a hang, and leaves no panel."""
    monkeypatch.setattr(atlas, "TIMEOUT_S", 1)
    killed = []

    class Hangs:
        def __init__(self, argv, **kw):
            self.argv, self.pid, self.returncode = argv, 4242, None

        def communicate(self, timeout=None):
            (Path(self.argv[self.argv.index("--browser") - 1]) / "panel_01.png").write_bytes(PNG)
            raise atlas.subprocess.TimeoutExpired(self.argv, timeout)

    monkeypatch.setattr(atlas.subprocess, "Popen", Hangs)
    monkeypatch.setattr(atlas, "_kill_tree", lambda proc: killed.append(proc.pid))
    page = tmp_path / "storyboard_v01.html"
    page.write_text("<html></html>", encoding="utf-8")
    (tmp_path / "out").mkdir()
    with pytest.raises(common.ToolError, match="storyboard renderer did not finish storyboard_v01.html in 0 minutes"):
        atlas.storyboard(page, tmp_path / "out")
    assert killed == [4242] and not any((tmp_path / "out").iterdir())


def test_sync_copies_both_scripts(light):
    (light / "atlas" / "storyboard.mjs").write_text("// storyboard", encoding="utf-8")
    assert atlas._sync_script() == atlas.work_dir() / "render.mjs"
    assert atlas._sync_script(atlas.STORYBOARD_SCRIPT) == atlas.work_dir() / "storyboard.mjs"
    assert (atlas.work_dir() / "storyboard.mjs").read_text() == "// storyboard"
    assert (atlas.work_dir() / "render.mjs").read_text() == "// render"


@pytest.mark.private_data
def test_storyboard_panels_of_another_size_are_said(tmp_path, capsys, ready, popen):
    """Task 19 review M3: panels drawn at the Atlas default 1280x720, not the prompt's 1080x1920 (9:16), are said in
    the message, as page errors are, before the storyboard is shown."""
    run = _m1_run(tmp_path, capsys)
    popen.act = _draws_storyboard()
    code, out = _storyboard(run, capsys, _page(run))
    assert code == 0 and out["wrong_sizes"] == [] and "1080×1920" not in out["message"], out
    popen.act = _draws_storyboard(size=(1280, 720))
    code, out = _storyboard(run, capsys, "03_wip/M1/storyboard_v01.html")
    assert code == 0 and out["wrong_sizes"] == [1, 2, 3, 4, 5, 6], out
    assert "panels 1, 2, 3, 4, 5, 6 are 1280×720, not 1080×1920 (9:16, the prompt's)" in out["message"], out
    _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "M1", "--style", "14", "--voiceover",
         "--storyboard", "--aspect", "4:5")
    popen.act = _draws_storyboard(size=(1080, 1350))
    code, out = _storyboard(run, capsys, "03_wip/M1/storyboard_v01.html")
    assert code == 0 and out["wrong_sizes"] == [], out                 # the latest prompt's 4:5


@pytest.mark.private_data
def test_a_missing_bundled_script_is_a_plain_stop(tmp_path, capsys, ready, popen):
    """Task 19 review M2: storyboard.mjs gone from the plugin is a stop that says the plugin is damaged, never a stale
    copy run from the data folder nor node's "Cannot find module"; render.mjs is held the same way."""
    run = _m1_run(tmp_path, capsys)
    _drawn_storyboard(run, capsys, popen)                             # a copy of storyboard.mjs in the data folder
    (ready / "atlas" / "storyboard.mjs").unlink()
    calls = len(popen.calls)
    with pytest.raises(common.ToolStop, match="storyboard.mjs is missing from the plugin"):
        atlas.storyboard(run.path / "03_wip" / "M1" / "storyboard_v01.html", tmp_path / "out")
    code, out = _storyboard(run, capsys, "03_wip/M1/storyboard_v01.html")
    assert (code, out["status"]) == (2, "stop") and "reinstall" in out["message"], out
    assert out["message"].endswith("The run continues from the same place.") and len(popen.calls) == calls
    assert not (run.path / "03_wip" / "M1" / "storyboard_v02").exists()
    (ready / "atlas" / "render.mjs").unlink()
    page = tmp_path / "x.html"
    page.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(common.ToolStop, match="render.mjs is missing from the plugin"):
        atlas.render(page, tmp_path / "x.mp4")
    assert len(popen.calls) == calls


@pytest.mark.private_data
def test_storyboard_mjs_is_the_originals_but_for_the_browser_panels_and_sandbox_options():
    """The handoff's render_storyboard.mjs, with its hard-coded Windows browsers and require path replaced by --browser
    and an import from the atlas package (as PB02 did for render.mjs), --no-sandbox, --panels in place of --suffix
    and --only (one storyboard_vNN folder per drawing), a single summary line, and no font check of one style."""
    theirs = _text(exampleedu.M1 / "render_storyboard.mjs").splitlines()
    ours = _text(PLUGIN / "atlas" / "storyboard.mjs").splitlines()
    changed = [line for line in difflib.unified_diff(theirs, ours, lineterm="", n=0)
               if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    allowed = ("--browser", "--no-sandbox", "NO_SANDBOX", "--panels", "panels", "--suffix", "--only", "suffix", "only",
               "createRequire", "require", "puppeteer-core", "BROWSERS", "executablePath", "// Usage:", "// Same toolchain",
               "// Linux only", "fontOk", "sizes", "const got", "if (!got)", "writeFileSync(targets[n]", "console.log",
               "const b64", "const targets", "const sheetPath")
    changed = [line for line in changed if line[1:].strip()]
    assert changed and all(any(a in line for a in allowed) for line in changed), changed
    assert 'import puppeteer from "puppeteer-core";' in ours and "C:/" not in "\n".join(ours)


# --- the storyboard check-in, then the animation ------------------------------------------------------------------

def _drawn_storyboard(run, capsys, popen):
    popen.act = _draws_storyboard()
    code, out = _storyboard(run, capsys, _page(run))
    assert code == 0, out
    return out["sheet"]


@pytest.mark.private_data
def test_animate_refused_before_storyboard_accepted(tmp_path, capsys, ready, popen):
    """OV9 (style frame or storyboard -> full render): `tm organic animate` draws nothing until the latest storyboard
    is accepted on the images check-in page or picked by rule, after the pack check that last changed it; then it
    renders at the config's 30 fps (PB02's atlas.FPS stays 24) into 03_wip/M1/renders/anim_vNN.mp4."""
    run = _m1_run(tmp_path, capsys)
    _page(run, "explainer_v01.html")
    code, out = _animate(run, capsys)
    assert code == 2 and "not accepted" in out["message"] and "tm organic storyboard" in out["message"], out
    assert stepchecks.run("images_picked", run).startswith("each animation's latest storyboard is accepted")
    sheet = _drawn_storyboard(run, capsys, popen)
    code, out = _animate(run, capsys)
    assert code == 2 and f"Its latest is {sheet}" in out["message"] and "tm organic pick --stage storyboard" in out[
        "message"] and "images check-in page" in out["message"] and out["message"].endswith(AGAIN + ".")
    assert len(popen.calls) == 1 and not (run.path / "03_wip" / "M1" / "renders").exists()   # nothing drawn
    code, out = _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1",
                     "--file", "03_wip/M1/storyboard_v01/panel_01.png", "--reason", "x")
    assert code == 2 and f"not the latest storyboard of M1 (that is {sheet})" in out["message"]
    code, out = _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "m1",
                     "--file", sheet, "--reason", "style 14 kept, the same kid in every panel, text above y 1260")
    assert code == 0 and out["row"]["rubric"] == {"against": list(organic_qa.STORYBOARD_RUBRIC)}, out
    assert stepchecks.run("images_picked", run) is None
    assert "its animation is not drawn" in stepchecks.run("takes_checked", run)
    popen.act = _draws_animation()
    code, out = _animate(run, capsys)
    assert code == 0 and out["file"] == "03_wip/M1/renders/anim_v01.mp4" and out["fps"] == 30, out
    argv = popen.calls[-1][0]
    assert argv[argv.index("--fps") + 1] == "30" and atlas.FPS == 24
    assert out["storyboard"] == sheet and len(out["stills"]) == 5
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    assert row["source"] == "tm organic animate" and json.loads(row["params"])["storyboard"] == sheet
    assert stepchecks.run("takes_checked", run) is None
    code, out = _animate(run, capsys, "03_wip/M1/explainer_v01.html", "--fps", "24")
    assert out["file"] == "03_wip/M1/renders/anim_v02.mp4" and out["fps"] == 24

    # a newer storyboard voids the pick until it is accepted itself
    newer = _drawn_storyboard(run, capsys, popen)
    code, out = _animate(run, capsys)
    assert code == 2 and f"{sheet} is not the item's latest storyboard ({newer})" in out["message"]
    _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file", newer,
         "--reason", "the fixes are in")
    assert "its animation is not drawn from its accepted storyboard" in stepchecks.run("takes_checked", run)

    # a pack check that changes what the storyboard shows makes the pick stale; one that leaves it as it was keeps
    # it, a change to the spoken words alone included (issue #90: the voiceover's text is not drawn)
    _backdate_picks(run)
    pack = _m1_pack()
    pack["facts"][0]["claim"] += " "                                      # not the storyboard's
    _check(run, capsys, pack, 2)
    code, out = _animate(run, capsys)
    assert code == 0, out
    pack["script"]["lines"][2]["text"] = "Bawi, bo brzmi głupio, a zna go każdy kolega z tej sali."
    pack["script"]["words"] += 2
    pack["cost"]["lines"][0]["units"] = pack["cost"]["lines"][0]["cost"] = pack["cost"]["totals"]["voice_credits"] = 397
    _check(run, capsys, pack, 3)
    code, out = _animate(run, capsys)
    assert code == 0, out
    pack["script"]["lines"][2]["on_screen"] = "KOLEGA Z SALI"               # the on-screen text: the storyboard's
    _check(run, capsys, pack, 4)
    code, out = _animate(run, capsys)
    assert code == 2 and "made before the pack was checked again" in out["message"], out
    _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file", newer,
         "--reason", "the new caption is drawn")
    _backdate_picks(run)
    pack["script"]["lines"][1]["shot"] += " Close-up."                    # a scene drawn otherwise
    _check(run, capsys, pack, 5)
    code, out = _animate(run, capsys)
    assert code == 2 and "made before the pack was checked again" in out["message"], out


@pytest.mark.private_data
def test_an_animation_drawn_under_an_old_script_fails_f2_after_a_re_pick(tmp_path, capsys, ready, popen):
    """Task 19 review I1: the animation's manifest row records the storyboard pick it was drawn from; after a change to
    a scene, re-picking the same sheet does not make the old animation pass F2: it is drawn again."""
    run = _m1_run(tmp_path, capsys)
    _page(run, "explainer_v01.html")
    sheet = _drawn_storyboard(run, capsys, popen)
    pick = ("organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file", sheet,
            "--reason", "style 14 kept")
    assert _cli(capsys, *pick)[0] == 0
    _backdate_picks(run)
    popen.act = _draws_animation()
    code, out = _animate(run, capsys)
    assert code == 0, out
    row = next(r for r in manifest.rows(run) if r["file"] == out["file"])
    board = organic_qa.picks(run, "storyboard")[common.stem_of("M1")]
    assert json.loads(row["params"])["storyboard_pick"] == {"file": sheet, "at": board["at"], "read_at": None}
    assert stepchecks.run("takes_checked", run) is None
    pack = _m1_pack()
    pack["script"]["lines"][2]["shot"] += " Close-up."                    # a scene drawn otherwise
    _check(run, capsys, pack, 2)
    assert "made before the pack was checked again" in stepchecks.run("takes_checked", run)
    assert _cli(capsys, *pick)[0] == 0                                  # the same sheet, picked again
    assert stepchecks.run("images_picked", run) is None
    gap = stepchecks.run("takes_checked", run)
    assert gap and "its animation is not drawn from its accepted storyboard" in gap, gap
    code, out = _animate(run, capsys)
    assert code == 0 and out["file"] == "03_wip/M1/renders/anim_v02.mp4", out
    assert stepchecks.run("takes_checked", run) is None


@pytest.mark.private_data
def test_fps_0_is_refused(tmp_path, capsys, ready, popen):
    """Task 19 review M1: --fps 0 (or a config's animation.fps 0) is refused, never drawn at the default."""
    run = _m1_run(tmp_path, capsys)
    _page(run, "explainer_v01.html")
    sheet = _drawn_storyboard(run, capsys, popen)
    assert _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file",
                sheet, "--reason", "style 14 kept")[0] == 0
    calls = len(popen.calls)
    code, out = _animate(run, capsys, "03_wip/M1/explainer_v01.html", "--fps", "0")
    assert code == 1 and "--fps is a whole number above 0, not 0" in out["message"], out
    config.save(run, {**config.load(run), "animation": {"fps": 0}})
    code, out = _animate(run, capsys)
    assert code == 1 and "not 0" in out["message"], out
    assert len(popen.calls) == calls and not (run.path / "03_wip" / "M1" / "renders").exists()


@pytest.mark.private_data
def test_a_storyboard_accepted_on_the_published_page_goes_stale_after_a_replan(tmp_path, capsys, ready, popen):
    """Task 19 review M6: the user's accept saved on the published images page (read with db_list) is the storyboard's
    pick, dated by the page build; a pack check that changes a scene after that build makes it stale."""
    from test_organic_gates import SLUG, _decide, _doc, _ready, _save_db

    run = _m1_run(tmp_path, capsys)
    sheet = _drawn_storyboard(run, capsys, popen)
    _ready(run, capsys, "gate_images", "images")
    _save_db(run, "gate_images", _doc("storyboard-M1", action="accept", choice="storyboard_v01"))
    code, out = _decide(run, capsys, "gate_images")
    assert code == 0 and out["source"] == "page" and out["decisions"]["storyboard-M1"]["file"] == sheet, out
    assert organic_qa.accepted_storyboard(run, "M1")["file"] == sheet and SLUG
    pack = _m1_pack()
    pack["script"]["lines"][2]["shot"] += " Close-up."                    # a scene drawn otherwise
    _check(run, capsys, pack, 2)
    s = state.load(run)                                                # the re-check a minute after the page build
    s.checked["pack"]["at"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(timespec="seconds")
    state.save(run, s)
    gap = stepchecks.run("images_picked", run)
    assert gap and "made before the pack was checked again" in gap, gap
    _page(run, "explainer_v01.html")
    code, out = _animate(run, capsys)
    assert code == 2 and "made before the pack was checked again" in out["message"], out


@pytest.mark.private_data
def test_video_page_lists_animation_renders_in_any_case(tmp_path, capsys, ready, popen):
    """Task 19 review M6: an animation render named in another case (`ANIM_V02.MP4`, as a Windows tool may write it)
    is listed in version order, never an error."""
    run = _m1_run(tmp_path, capsys)
    renders = run.path / "03_wip" / "M1" / "renders"
    renders.mkdir(parents=True)
    for name in ("anim_v01.mp4", "ANIM_V02.MP4", "anim_v10.mp4", "anim_vx.mp4"):
        (renders / name).write_bytes(b"mp4")
    data = organic_gates.gate_json(run, "video")
    item = next(i for i in data["items"] if i["id"] == "animation-M1")
    assert [o["id"] for o in item["options"]] == ["anim_v01", "ANIM_V02", "anim_v10"]
    assert [o.get("pick", False) for o in item["options"]] == [False, False, True]


def _backdate_picks(run):
    """The pack check set back 10 minutes and every pick of the A–Z log 5, so a pack check made now comes after the
    picks, and the picks after the check they were made on."""
    def ago(minutes):
        return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    log = run.path / organic_qa.AZ_LOG
    rows = [{**json.loads(line), "at": ago(5)} for line in log.read_text(encoding="utf-8").splitlines()]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    s = state.load(run)
    s.checked["pack"]["at"] = ago(10)
    state.save(run, s)


@pytest.mark.private_data
def test_storyboard_accepted_on_the_images_page(tmp_path, capsys, ready, popen):
    """The images check-in page shows an animation's latest storyboard (and the voiceover beside it); the user's
    accept there is the storyboard's pick, and a later redo on the page ends it; the video page shows the
    animation's renders."""
    run = _m1_run(tmp_path, capsys)
    code, out = _cli(capsys, "organic", "page", "gate", "--gate", "images", "--run", str(run.path))
    assert code == 2 and "nothing to show" in out["message"]
    sheet = _drawn_storyboard(run, capsys, popen)
    code, out = _cli(capsys, "organic", "page", "gate", "--gate", "images", "--run", str(run.path))
    assert code == 0, out
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    assert [it["id"] for it in data["items"]] == ["storyboard-M1"]
    assert data["items"][0]["label"] == "Storyboard: M1" and data["items"][0]["options"][0]["src"] == sheet
    text = run.path / "03_wip" / "chat_v01.txt"
    text.write_text("storyboard-M1: accept\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "gate_images", "--text",
                     "03_wip/chat_v01.txt")
    assert code == 0 and out["decisions"]["storyboard-M1"]["file"] == sheet, out
    assert organic_qa.accepted_storyboard(run, "M1")["file"] == sheet
    assert stepchecks.run("images_picked", run) is None
    page_built = next(r for r in manifest.rows(run) if r["source"] == "tm organic page gate_images")
    assert page_built["file"] == "04_final/gate_images_v01"
    code, out = _cli(capsys, "organic", "page", "gate", "--gate", "images", "--run", str(run.path))
    text.write_text("storyboard-M1: redo; note: the bat above the lid\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "gate_images", "--text",
                     "03_wip/chat_v01.txt")
    assert code == 0, out
    code, out = _animate(run, capsys)
    assert code == 2 and "not accepted" in out["message"]
    decided = run.path / "03_wip" / "decisions_gate_images_v02.json"
    body = json.loads(decided.read_text(encoding="utf-8"))   # read a minute ago: the user's pick below comes after it
    body["at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    decided.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    _cli(capsys, "organic", "pick", "--run", str(run.path), "--stage", "storyboard", "--name", "M1", "--file", sheet,
         "--reason", "the user accepted it in chat", "--by", "user")
    _page(run, "explainer_v01.html")
    popen.act = _draws_animation()
    code, out = _animate(run, capsys)
    assert code == 0, out
    code, out = _cli(capsys, "organic", "page", "gate", "--gate", "video", "--run", str(run.path))
    assert code == 0, out
    data = json.loads((run.path / out["data"]).read_text(encoding="utf-8"))
    assert [it["id"] for it in data["items"]] == ["animation-M1"]
    assert data["items"][0]["options"] == [{"id": "anim_v01", "src": "03_wip/M1/renders/anim_v01.mp4",
                                            "caption": "M1/anim_v01", "pick": True}]
    # Task 19 review M5: a redo on the video page is named by that page and the item's label, in plain words
    text.write_text("animation-M1: redo; note: a slower first beat\n", encoding="utf-8")
    code, out = _cli(capsys, "organic", "decisions", "--run", str(run.path), "--page", "gate_video", "--text",
                     "03_wip/chat_v01.txt")
    assert code == 0 and out["redos"] == ["gate_video:M1_animation"], out
    assert "redo request for Animacja: M1 (on the video check-in page)" in out["message"], out["message"]   # pl page
    assert "delivery:" not in out["message"] and "M1_animation" not in out["message"]
    assert state.load(run).organic["redos"]["gate_video:M1_animation"][0]["note"] == "a slower first beat"


# --- real drawings of our styles --------------------------------------------------------------------------------

def _real(request, tmp_path_factory, monkeypatch):
    if not video_asked_for(request.config):
        pytest.skip("the real drawings run with -m video (pixi run -e dev-full test-video)")
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    cache = remotion_cache(tmp_path_factory)
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(PLUGIN))
    monkeypatch.setattr(atlas.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(atlas.remotion, "_prefix", lambda: [])  # already inside an environment with Node
    monkeypatch.setattr(atlas.envtiers, "installed", lambda tier: True)
    if atlas.find_browser() is None:
        pytest.skip("no Chrome, Edge or Chromium on this computer")
    atlas.setup()


@pytest.mark.video
def test_real_storyboard_of_every_style(request, tmp_path, tmp_path_factory, monkeypatch):
    """Each style's reference animation as a 9:16 storyboard page, drawn by storyboard.mjs in this computer's
    browser: six 1080x1920 panels and a sheet, no page errors (the page loads its fonts from Google Fonts)."""
    _real(request, tmp_path_factory, monkeypatch)
    for style in atlas_prompt.styles():
        page = tmp_path / f"{style['styleId']} board" / "storyboard_v01.html"
        page.parent.mkdir()
        page.write_text(atlas_prompt.page(style, "9:16", storyboard=True), encoding="utf-8")
        out = tmp_path / "03_wip" / style["styleId"] / "storyboard_v01"
        summary = atlas.storyboard(page, out)
        assert summary["page_errors"] == [] and summary["sizes"] == [[1080, 1920]] * 6, (style["styleId"], summary)
        names = sorted(p.name for p in out.iterdir())
        assert names == [f"panel_{n:02d}.png" for n in range(1, 7)] + ["sheet.png"]
        for name in names[:-1]:
            head = (out / name).read_bytes()[:24]
            assert head[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", head[16:24]) == (1080, 1920), name
        assert (out / "sheet.png").stat().st_size > 0


@pytest.mark.video
@pytest.mark.parametrize("aspect", ["9:16", None])        # None: the 1280x720 frame
def test_every_style_passes_the_layout_check(request, tmp_path, tmp_path_factory, monkeypatch, aspect):
    """Each style's reference animation, checked by layout_check.mjs in this computer's browser at 9:16 and 16:9:
    every label at least the prompt's size, nothing to read outside the safe area, no dead band, no page error.
    Claude copies the reference's rendering, so the reference meets the rules the prompt gives."""
    _real(request, tmp_path_factory, monkeypatch)
    problems = {}
    for style in atlas_prompt.styles():
        page = tmp_path / style["styleId"] / "explainer_v01.html"
        page.parent.mkdir()
        page.write_text(atlas_prompt.page(style, aspect), encoding="utf-8")
        found = atlas.layout_problems(REAL_LAYOUT(page))
        if found:
            problems[style["styleId"]] = found
    assert problems == {}, json.dumps(problems, indent=1)


@pytest.mark.video
@pytest.mark.parametrize("key,aspect,size", [("3", "9:16", (1080, 1920)), ("14", "9:16", (1080, 1920)),
                                             ("14", None, (1280, 720))])
def test_real_render_of_a_style(request, tmp_path, tmp_path_factory, monkeypatch, key, aspect, size):
    """A style's reference animation rendered end to end by render.mjs: the frame size asked for, every frame, the
    stills, the sound score mixed in, no page errors."""
    _real(request, tmp_path_factory, monkeypatch)
    style = atlas_prompt.find_style(key)
    page = tmp_path / "anim page" / "explainer_v01.html"
    page.parent.mkdir()
    page.write_text(atlas_prompt.page(style, aspect), encoding="utf-8")
    out = tmp_path / "03_wip" / "renders" / "anim_v01.mp4"
    out.parent.mkdir(parents=True)
    summary = atlas.render(page, out)
    assert summary["page_errors"] == [] and summary["size"] == list(size) and summary["sound"] is True, summary
    assert 8 <= summary["duration"] <= 16 and summary["frames"] == round(summary["duration"] * atlas.FPS)
    info = common.probe(out)
    assert (info["width"], info["height"], info["has_audio"]) == (*size, True)
    stills = sorted(p.name for p in out.parent.glob("anim_v01_still_*.png"))
    assert stills == [f"anim_v01_still_{n}.png" for n in ("006", "030", "055", "080", "095")]


@pytest.mark.private_data
def test_the_decided_look_is_kept_in_the_recipe_and_the_prompt(tmp_path, capsys, animatic_ready):
    """Issue #87: the look decided on the proposals page (00_raw/proposal.json decision.aesthetic) must be in the
    recipe, and the animation's build prompt carries it, so every scene keeps it. A pack without a decided look, as
    before, needs none."""
    run = _m1_run(tmp_path, capsys)
    kept = json.loads((run.path / "00_raw" / "proposal.json").read_text(encoding="utf-8"))
    kept["decision"] = {"aesthetic": "paper cut-out collage, flat colour"}
    (run.path / "00_raw" / "proposal.json").write_text(json.dumps(kept), encoding="utf-8")
    today = datetime(2026, 11, 7).date()
    problems = organic_pack.check(run, _m1_pack(), config.load(run), stage="recipe", today=today)
    assert [p.field for p in problems] == ["aesthetic"] and "paper cut-out collage" in problems[0].what
    pack = {**_m1_pack(), "aesthetic": "paper cut-out collage, flat colour"}
    assert organic_pack.check(run, pack, config.load(run), stage="recipe", today=today) == []
    assert [p.field for p in organic_pack.check(run, {**pack, "aesthetic": " "}, config.load(run), stage="recipe",
                                                today=today)] == ["aesthetic"]
    _check(run, capsys, pack, 2)
    code, out = _cli(capsys, "organic", "atlas-prompt", "--run", str(run.path), "--item", "m1", "--style", "7",
                     "--aspect", "9:16")
    assert code == 0, out
    assert "kept in every scene: paper cut-out collage, flat colour." in _text(run.path / out["file"])
