"""Text sets that fit the animation's style, the cover in the approved style, a face collision with its fix and the
same check in creative-brief animatics, refresh-ad in the brand's text set (issue #139). Made-up runs, public."""

from __future__ import annotations

import json
from datetime import date

import pytest

from exampleedu import PROFILE as EXAMPLEEDU
from tm import atlas_prompt, brand, config, manifest, organic_config, organic_edit, render, text_sets
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


@pytest.fixture
def remotion(monkeypatch, tmp_path):
    """tm render without Node: the Remotion call writes its output file, everything else (the record) is real."""
    monkeypatch.setattr(render, "_need_setup", lambda: None)
    monkeypatch.setattr(render, "_sync_src", lambda: None)
    monkeypatch.setattr(render.video_fonts, "check", lambda *a, **k: None)
    monkeypatch.setattr(render, "work_dir", lambda: tmp_path / "remotion")
    (tmp_path / "remotion").mkdir()

    def fake(argv, cwd, what):
        part = next(a for a in argv if a.endswith((".png", ".mp4")) and "/." in a.replace("\\", "/"))
        open(part, "wb").write(b"\x89PNG rendered" if part.endswith(".png") else b"rendered")

    monkeypatch.setattr(render, "_sh", fake)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _animation(ws, *, style="04 whiteboard", overlay="3 steps", saved="outline"):
    """An organic run whose item m5 is an animation in `style`, its frames list with `overlay` text on a panel, and
    the channel's saved set `saved` (None: none saved)."""
    brand.save(ws, EXAMPLEEDU, run=None)
    run = RunFolder.create(ws, "ideas", date(2026, 11, 17), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": ["exampleedu"]})
    item = run.path / "03_wip" / "m5"
    item.mkdir(parents=True)
    (item / "prompt_v01.txt").write_text("the build prompt", encoding="utf-8")
    manifest.record(run, "03_wip/m5/prompt_v01.txt", "03_wip", "tm organic atlas-prompt",
                    params={"style": style, "storyboard": True, "animation": False, "layout": False})
    (item / "frames_v01.json").write_text(json.dumps(
        [{"panel": 1, "from": 0, "to": 2, "line": "Three steps", "overlay": overlay},
         {"panel": 2, "from": 2, "to": 4, "line": "The first one"}]), encoding="utf-8")
    (item / "frame_v01.png").write_bytes(b"\x89PNG a storyboard panel")
    if saved:
        text_sets.save(ws, "channel", "exampleedu", look=saved, run=run, note="the channel's set")
    return run


# --- 1. a text set that fits the animation's style family ------------------------------------------

def test_every_style_category_has_a_look_as_the_issue_lists_them():
    categories = {s["category"] for s in atlas_prompt.styles()}
    assert set(text_sets.FAMILY_LOOKS) == categories and len(categories) == 16
    assert set(text_sets.FAMILY_LOOKS.values()) <= set(organic_edit.LOOKS)
    want = {"marker": ("Hand-drawn", "Painterly", "Paper and craft", "Illustration"),
            "block": ("Clean explainer", "Data", "Product and UI", "Design movements", "Print", "Type and pattern",
                      "Collage"),
            "pop": ("Retro digital", "Retro desktop"),
            "outline": ("Dimensional", "Light and imaging", "Cosmic")}
    for look, cats in want.items():
        assert all(text_sets.FAMILY_LOOKS[c] == look for c in cats)


def test_a_hand_drawn_animation_draws_both_samples_and_suggests_marker(ws, remotion, capsys):
    run = _animation(ws, overlay="")
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                     "03_wip/m5/frame_v01.png", "--caption", "Three steps to a clean desk", "--overlay", "3 steps")
    assert code == 0, out
    assert out["family_look"] == "marker" and out["style_family"] == "Hand-drawn"
    assert "The channel's set is outline; for a Hand-drawn style, marker fits better." in out["message"]
    # the suggestion is drawn first, the saved set last: the latest style is still the channel's
    suggestion = json.loads((run.path / out["suggestion"]["style"]).read_text(encoding="utf-8"))
    latest = json.loads((run.path / out["style"]).read_text(encoding="utf-8"))
    assert suggestion["look"] == "marker" and latest["look"] == "outline"
    assert run.latest("wip", "text_style", "json").name == "text_style_v02.json" == run.path.joinpath(
        out["style"]).name
    assert out["suggestion"]["still"].endswith(".png") and out["still"] != out["suggestion"]["still"]
    # the saved set is not changed
    assert text_sets.for_run(run)["look"] == "outline"
    assert text_sets.for_run(run)["file"].endswith("text_style_v01.json")


def test_no_suggestion_when_the_saved_set_is_the_familys_or_a_look_is_asked_for(ws, remotion, capsys):
    run = _animation(ws, overlay="", saved="marker")
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                     "03_wip/m5/frame_v01.png", "--caption", "Three steps", "--overlay", "3 steps")
    assert code == 0 and out["suggestion"] is None and out["family_look"] == "marker"
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                     "03_wip/m5/frame_v01.png", "--caption", "Three steps", "--overlay", "3 steps", "--look", "pop")
    assert code == 0 and out["suggestion"] is None


def test_the_top_overlay_is_off_when_the_animation_draws_its_own_headings(ws, remotion, capsys):
    run = _animation(ws, saved="marker")
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                     "03_wip/m5/frame_v01.png", "--caption", "Three steps", "--overlay", "3 steps")
    assert code == 0, out
    assert out["overlays_off"] is True
    assert "The animation draws its own headings, so the top overlay is off." in out["message"]
    style = json.loads((run.path / out["style"]).read_text(encoding="utf-8"))
    assert style["overlays"]["on"] is False and organic_edit.style_problems(style) == []
    props = json.loads((run.path / out["props"]).read_text(encoding="utf-8"))
    assert [c["style"] for c in props["captions"]] == ["caption"]
    # the user turns them on
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(run.path), "--picture",
                     "03_wip/m5/frame_v01.png", "--caption", "Three steps", "--overlay", "3 steps",
                     "--overlays", "on")
    assert code == 0 and out["overlays_off"] is False
    props = json.loads((run.path / out["props"]).read_text(encoding="utf-8"))
    assert [c["style"] for c in props["captions"]] == ["hook", "caption"]


def test_overlays_off_leave_the_edits_top_overlays_out_but_keep_the_end_card():
    style = organic_edit.default_style(caption="", overlay="", look="marker")
    style["overlays"]["on"] = False
    given = [{"from": 0, "to": 2, "text": "3 steps", "style": "hook"},
             {"from": 2, "to": 3, "text": "42", "style": "hook", "overlay": {"kind": "number"}},
             {"from": 8, "to": 10, "text": "Follow", "style": "hook", "overlay": {"kind": "end"}}]
    out = organic_edit.overlay_entries(given, style, total=10)
    assert [o["overlay"]["kind"] for o in out] == ["end"]
    style["overlays"]["on"] = "no"
    assert any("overlays.on" in p for p in organic_edit.style_problems(style))
