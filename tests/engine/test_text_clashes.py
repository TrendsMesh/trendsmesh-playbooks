"""Text sets that fit the animation's style, the cover in the approved style, a face collision with its fix and the
same check in creative-brief animatics, refresh-ad in the brand's text set (issue #139). Made-up runs, public."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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


# --- 2. the cover takes the run's approved text style ------------------------------------------------

def _approved(monkeypatch, style):
    from tm.tools import cover_fit
    monkeypatch.setattr(cover_fit.organic_edit, "approved_style",
                        lambda run: ("03_wip/text_style_v03.json", "abc", style))


def test_a_cover_caption_takes_the_approved_sets_family_accent_ink_and_font(ws, monkeypatch):
    from tm.tools import cover_fit

    run = _animation(ws, saved=None)
    style = organic_edit.default_style(caption="", overlay="", look="outline", accent="#FFD84D",
                                       font={"family": "Brand Sans", "src": "03_wip/text_set/brand.ttf"})
    _approved(monkeypatch, style)
    data = {"width": 1080, "height": 1920, "captions": [
        {"from": 0, "to": 2, "text": "One *habit* fixes mornings", "style": "hook", "place": "top", "fontSize": 72},
        {"from": 0, "to": 2, "text": "and nobody says it", "style": "caption"}]}
    out, said = cover_fit.styled(run, data)
    hook, cap = out["captions"]
    assert hook["overlay"] == {"kind": "hook", "family": "outline", "accent": "#FFD84D", "ink": "#111111",
                               "size": 72}            # the cover's own size, which a family would otherwise drop
    assert hook["text"] == "One *habit* fixes mornings"      # the marker stays, parsed by the look, never drawn
    assert cap["look"] == "outline" and cap["ink"] == "#111111"
    assert out["brandFont"] == {"family": "Brand Sans", "src": "03_wip/text_set/brand.ttf"}
    assert "03_wip/text_style_v03.json" in said and data["captions"][0].get("overlay") is None   # a copy


def test_what_the_cover_names_itself_is_kept(ws, monkeypatch):
    from tm.tools import cover_fit

    run = _animation(ws, saved=None)
    _approved(monkeypatch, organic_edit.default_style(caption="", overlay="", look="outline", accent="#FFD84D"))
    data = {"captions": [{"from": 0, "to": 2, "text": "Hi", "style": "hook",
                          "overlay": {"kind": "hook", "family": "pill", "accent": "#22AA88"}}],
            "brandFont": {"family": "Own", "src": "03_wip/own.ttf"}}
    out, said = cover_fit.styled(run, data)
    assert out["captions"][0]["overlay"] == {"kind": "hook", "family": "pill", "accent": "#22AA88", "ink": "#111111"}
    assert out["brandFont"]["family"] == "Own"


def test_without_an_approved_style_the_cover_is_unchanged_and_a_plain_hook_drops_its_stars(ws, monkeypatch):
    from tm.tools import cover_fit

    run = _animation(ws, saved=None)
    monkeypatch.setattr(cover_fit.organic_edit, "approved_style", lambda run: None)
    data = {"captions": [{"from": 0, "to": 2, "text": "One *habit*", "style": "hook"}]}
    assert cover_fit.styled(run, data) == (data, None)
    _approved(monkeypatch, organic_edit.default_style(caption="", overlay=""))      # a style with no look
    out, said = cover_fit.styled(run, data)
    assert out["captions"][0]["text"] == "One habit" and out["captions"][0]["background"] == "#FFFFFF"
    assert out["captions"][0]["color"] == "#111111" and said


# --- 4. the same collision check in creative-brief animatics ---------------------------------------

needs_node = pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node draws the scenes")
HOOK = {"str": "Your mornings, fixed in a week", "style": "center", "size": 66}


def _concept(*beats):
    return {"id": "C1", "beats": [{"t0": 2 * i, "t1": 2 * i + 2, "see": "x", "hear": "", "ost": "",
                                   "animatic": {"scene": scene, "params": params, "texts": texts}}
                                  for i, (scene, params, texts) in enumerate(beats)]}


@needs_node
def test_the_page_marks_the_phone_screen_and_the_product_name_and_gives_the_hooks_boxes(monkeypatch):
    from tm import animatic

    monkeypatch.setattr(render, "_prefix", lambda: [])                  # node from PATH, not the video tier's
    anim = animatic.build_anim(_concept(("product_phone", {"product": "Lumen lamp"}, [HOOK]),
                                        ("selfie_talk", {}, [{**HOOK, "style": "top"}])))
    got = animatic.probe.__wrapped__(anim, "9x16")
    phone, selfie = got["beats"]
    assert {m["kind"] for m in phone["marks"]} == {"screen", "brand"}
    assert {m["kind"] for m in selfie["marks"]} == {"face"}
    hook = phone["texts"][0]
    assert hook["index"] == 0 and set(hook["boxes"]) == {"top", "center", "bottom"}
    assert [s for s, _ in hook["boxes"]["center"]][:3] == [66, 56, 48]     # × 0.85 a step, never under 32
    assert hook["boxes"]["center"][-1][0] == 32
    screen = next(m["box"] for m in phone["marks"] if m["kind"] == "screen")
    assert animatic.covers(hook["boxes"]["center"][0][1], screen)          # the centre covers the phone
    assert not animatic.covers(hook["boxes"]["top"][0][1], screen)         # the top is clear of it


def _probe(texts_boxes, marks):
    return {"beats": [{"marks": [{"kind": k, "box": b} for k, b in marks],
                       "texts": [{"index": 0, "boxes": texts_boxes}]}]}


def test_a_hook_over_the_screen_moves_to_the_free_place_and_says_so():
    from tm import animatic

    anim = animatic.build_anim(_concept(("product_phone", {"product": "Lumen"}, [HOOK])))
    boxes = {"top": [[66, [100, 280, 880, 90]]], "center": [[66, [100, 860, 880, 90]]],
             "bottom": [[66, [100, 1580, 880, 90]]]}
    fixed, changes = animatic.fit_hooks(anim, _probe(boxes, [("screen", [330, 580, 420, 820])]))
    assert fixed["beats"][0]["texts"][0]["style"] == "top" and anim["beats"][0]["texts"][0]["style"] == "center"
    assert changes == ["C1 beat 1: the hook \"Your mornings, fixed in a week\" moved from center to top (it covered "
                       "the product screen)"]
    clear, none = animatic.fit_hooks(anim, _probe(boxes, [("face", [0, 0, 50, 50])]))
    assert none == [] and clear == anim


def test_a_hook_with_no_free_place_is_made_smaller_and_one_that_fits_nowhere_is_named():
    from tm import animatic

    anim = animatic.build_anim(_concept(("selfie_talk", {}, [HOOK])))
    boxes = {p: [[66, [100, 200, 880, 1500]], [56, [100, 200, 880, 1500]], [48, [300, 100, 400, 60]]]
             for p in ("top", "center", "bottom")}
    fixed, changes = animatic.fit_hooks(anim, _probe(boxes, [("face", [285, 230, 510, 640])]))
    hook = fixed["beats"][0]["texts"][0]
    assert (hook["style"], hook["size"]) == ("center", 48)
    assert "made smaller (66 to 48)" in changes[0] and "the face" in changes[0]
    boxes = {p: [[66, [100, 200, 880, 1500]], [32, [100, 200, 880, 1500]]] for p in ("top", "center", "bottom")}
    fixed, changes = animatic.fit_hooks(anim, _probe(boxes, [("face", [285, 230, 510, 640])]))
    assert fixed == anim and "still covers the face" in changes[0]


@needs_node
def test_tm_brief_animatic_moves_the_hook_before_rendering_and_names_the_change(tmp_path, monkeypatch, capsys):
    from tm import animatic, atlas
    from tm.playbooks import CREATIVE_BRIEF

    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)
    (run.path / "04_final").mkdir(exist_ok=True)
    (run.path / "04_final" / "brief_pack_v01.json").write_text(json.dumps(
        {"concepts": [_concept(("product_phone", {"product": "Lumen lamp"}, [HOOK]))]}), encoding="utf-8")
    monkeypatch.setattr(animatic, "probe", animatic.probe.__wrapped__)
    monkeypatch.setattr(render, "_prefix", lambda: [])                  # node from PATH, not the video tier's
    monkeypatch.setattr(atlas, "need", lambda: tmp_path / "chrome")
    drawn = []

    def fake_render(page, out, *, fps=atlas.FPS, stills=atlas.STILLS):
        drawn.append(Path(page).read_text(encoding="utf-8"))
        Path(out).write_bytes(b"mp4")
        return {"render_s": 1, "page_errors": []}

    monkeypatch.setattr(atlas, "render", fake_render)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--formats", "9x16")
    assert code == 0, out
    js = (run.path / animatic.WIP / "C1_anim_v01.js").read_text(encoding="utf-8")
    assert json.loads(js.removeprefix("window.ANIM = ").rstrip().rstrip(";"))["beats"][0]["texts"][0]["style"] == "top"
    assert out["hook_changes"] and "moved from center to top" in out["message"]


# --- 5. refresh-ad uses the brand's text set ------------------------------------------------------------

def _refresh(ws, product="Pet Store", name="refresh"):
    import copy

    from tm.playbooks import REFRESH_AD

    run = RunFolder.create(ws, name, date(2026, 11, 17), playbook=REFRESH_AD)
    cfg = copy.deepcopy(config.DEFAULTS)
    cfg["product"]["name"] = product
    config.save(run, cfg)
    return run


def test_a_refresh_ad_run_reads_its_brands_set(ws):
    run = _refresh(ws)
    assert text_sets.owners(run) == [("brand", "Pet Store")]
    assert text_sets.for_run(run) is None
    text_sets.save(ws, "brand", "Pet Store", look="pill", accent="#2E7D32", run=None, note="the green pill")
    assert text_sets.for_run(run)["look"] == "pill"
    assert text_sets.owners(_refresh(ws, product=None, name="no product")) == []


def _hookswap(run, **extra):
    (run.path / "01_base").mkdir(exist_ok=True)
    (run.path / "01_base" / "ad_original.mp4").write_bytes(b"the original")
    props = {"base": "01_base/ad_original.mp4", "width": 1080, "height": 1920, "durationSec": 8,
             "cards": [{"from": 0, "to": 3, "top": 190, "height": 113, "fullBleed": True,
                        "lines": [{"at": 0, "text": "Your cat drinks too little"}]}], "inserts": [], **extra}
    path = run.path / "03_wip" / "edit_a_v01.props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    return "03_wip/edit_a_v01.props.json"


def test_hookswap_and_wordcaptions_are_drawn_in_the_brands_set(ws, remotion, capsys):
    run = _refresh(ws)
    logo = run.path / "01_base" / "logo.png"
    logo.parent.mkdir(exist_ok=True)
    logo.write_bytes(b"\x89PNG logo")
    font = run.path / "01_base" / "Pet-Bold.ttf"
    font.write_bytes(b"\x00\x01\x00\x00 font")
    text_sets.save(ws, "brand", "Pet Store", look="pill", accent="#2E7D32", font=font, logo=logo, run=None,
                   note="the green pill")
    seen = []
    real = render._sh

    def spy(argv, cwd, what):
        given = next(a for a in argv if a.startswith("--props=")).removeprefix("--props=")
        seen.append(json.loads(Path(given).read_text(encoding="utf-8")))
        return real(argv, cwd, what)

    render._sh = spy
    try:
        code, out = _cli(capsys, "render", "still", "--run", str(run.path), "--comp", "HookSwap", "--props",
                         _hookswap(run), "--frame", "10")
    finally:
        render._sh = real
    assert code == 0, out
    used = seen[-1]["textSet"]
    assert used["look"] == "pill" and used["accent"] == "#2E7D32" and used["ink"] == "#FFFFFF"
    assert used["font"] == {"family": "Pet-Bold", "src": "03_wip/text_set/pet-bold_v01.ttf"}
    assert used["logo"] == "03_wip/text_set/logo_v01.png" and (run.path / used["logo"]).is_file()
    row = [r for r in manifest.rows(run) if r["model"] == "remotion still"][-1]
    assert json.loads(row["params"])["props"]["textSet"] == used          # the record says which set drew it
    # the props' own choice stands: null keeps the original's look
    render._sh = spy
    try:
        code, out = _cli(capsys, "render", "still", "--run", str(run.path), "--comp", "HookSwap", "--props",
                         _hookswap(run, textSet=None), "--frame", "10")
    finally:
        render._sh = real
    assert code == 0 and seen[-1]["textSet"] is None
