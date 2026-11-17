"""The channel's or brand's text set, kept in its library folder (issue #117, section 3): saved once, used in every
run, its font and logo kept beside it; the default and the three sets suggested the first time; the ink on the
accent picked by contrast."""

from __future__ import annotations

import json
from datetime import date

import pytest

from exampleedu import PROFILE as EXAMPLEEDU
from tm import brand, config, create_config, manifest, organic_config, text_sets
from tm.cli import main
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import Stop


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


def _organic(ws, channel="exampleedu"):
    run = RunFolder.create(ws, "ideas", date(2026, 11, 17), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": [channel]})
    return run


def _ad(ws, product="Pet Store"):
    run = RunFolder.create(ws, f"ad-{product}", date(2026, 11, 17), playbook=CREATE_AD)
    cfg = create_config.defaults()
    cfg["brand"]["product"] = product
    config.save(run, cfg)
    return run


def _files(run):
    font = run.path / "02_research" / "brand" / "Brand-Bold.ttf"
    font.parent.mkdir(parents=True, exist_ok=True)
    font.write_bytes(b"\x00\x01\x00\x00 a font")
    logo = run.path / "02_research" / "brand" / "logo.png"
    logo.write_bytes(b"\x89PNG logo")
    return font, logo


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


# --- the ink on the accent and the suggestion -----------------------------------------------------

@pytest.mark.parametrize("accent, ink", [("#FFD84D", "#111111"), ("#FFFFFF", "#111111"), ("#1A237E", "#FFFFFF"),
                                         ("#000000", "#FFFFFF"), ("#E53935", "#111111"), ("#767676", "#FFFFFF"),
                                         ("#6A1B9A", "#FFFFFF")])
def test_the_text_on_the_accent_is_dark_or_white_by_contrast(accent, ink):
    assert text_sets.accent_ink(accent) == ink


def test_three_sets_are_suggested_and_native_comes_first_for_ugc():
    for kind in (*brand.CHANNEL_TYPES, None):
        looks = text_sets.suggest_looks(kind)
        assert len(looks) == 3 == len(set(looks)) and set(looks) <= set(text_sets.oe.LOOKS)
    assert text_sets.suggest_looks(None)[0] == text_sets.oe.DEFAULT_LOOK == "outline"
    assert text_sets.suggest_looks("howto_education", ugc=True)[0] == "native"
    assert len(set(text_sets.suggest_looks("lifestyle_vlog", ugc=True))) == 3


# --- saved in the library and found for a run -------------------------------------------------------

def test_a_channel_set_is_saved_with_its_font_and_logo_and_found_for_the_run(ws):
    brand.save(ws, EXAMPLEEDU, run=None)
    run = _organic(ws)
    font, logo = _files(run)
    saved = text_sets.save(ws, "channel", "ExampleEdu", look="pill", accent="#22aa88", font=font,
                           font_family="Brand Sans", logo=logo, run=run, note="the second one")
    assert saved == ws / "library" / "channels" / "exampleedu" / "text_style_v01.json"
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["schema"] == "text_style/1" and data["look"] == "pill" and data["accent"] == "#22AA88"
    assert data["font"] == {"family": "Brand Sans", "file": "library/channels/exampleedu/text/brand-bold_v01.ttf"}
    assert data["logo"] == "library/channels/exampleedu/text/logo_v01.png"
    assert (ws / data["logo"]).read_bytes() == b"\x89PNG logo"
    assert data["note"] == "the second one" and data["run"] == run.path.name
    found = text_sets.for_run(run)
    assert found["look"] == "pill" and found["file"] == "library/channels/exampleedu/text_style_v01.json"
    # a later save is a new version; the earlier one is never touched
    again = text_sets.save(ws, "channel", "exampleedu", look="native", run=run, note="native after all")
    assert again.name == "text_style_v02.json" and json.loads(saved.read_text(encoding="utf-8"))["look"] == "pill"
    assert text_sets.for_run(run)["look"] == "native" and text_sets.for_run(run)["font"] is None


def test_a_channel_without_a_set_uses_its_stores_and_a_run_without_either_has_none(ws):
    store = {"schema": "brand/1", "kind": "brand", "brand": "Pet Store", "stands_for": "Calm pets at home.",
             "tone": ["warm", "plain", "dry"], "off_limits": [], "off_limits_asked": True, "claims": [],
             "competitors": [], "guide": {"source": "none", "where": ""}, "drafted_from": ["landing"],
             "confirmed": None, "catalog": {"products": [{"name": "Fountain", "packshot": None, "problems": []}]}}
    brand.save(ws, store, run=None)
    brand.save(ws, {**EXAMPLEEDU, "channel": "Cat Corner", "store": "Pet Store", "product_role": "incidental"},
               run=None)
    run = _organic(ws, "cat-corner")
    assert text_sets.for_run(run) is None
    text_sets.save(ws, "brand", "Pet Store", look="block", accent="#1A237E", run=None, note="brand guide")
    assert text_sets.for_run(run)["look"] == "block"
    ad = _ad(ws, "pet store")
    assert text_sets.for_run(ad)["file"] == "library/brands/pet-store/text_style_v01.json"
    assert text_sets.for_run(_ad(ws, "Other")) is None


def test_a_bad_look_accent_or_file_is_refused(ws):
    run = _organic(ws)
    with pytest.raises(Stop, match="look must be one of"):
        text_sets.save(ws, "channel", "exampleedu", look="neon", run=run, note="x")
    with pytest.raises(Stop, match="accent must be a colour"):
        text_sets.save(ws, "channel", "exampleedu", look="pop", accent="yellow", run=run, note="x")
    bad = run.path / "02_research" / "logo.svg"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("<svg/>", encoding="utf-8")
    with pytest.raises(Stop, match="PNG"):
        text_sets.save(ws, "channel", "exampleedu", look="pop", logo=bad, run=run, note="x")
    assert not (ws / "library" / "channels" / "exampleedu").exists()


def test_into_the_run_copies_the_font_and_the_logo_where_remotion_reads_them(ws):
    run = _organic(ws)
    font, logo = _files(run)
    text_sets.save(ws, "channel", "exampleedu", look="outline", accent="#FFD84D", font=font, logo=logo, run=run,
                   note="x")
    other = RunFolder.create(ws, "next", date(2026, 11, 18), playbook=ORGANIC_VIDEO)
    config.save(other, {**organic_config.defaults(), "channels": ["exampleedu"]})
    used = text_sets.into_run(other, text_sets.for_run(other))
    assert used["look"] == "outline" and used["accent"] == "#FFD84D" and used["ink"] == "#111111"
    assert used["font"]["family"] == "Brand-Bold"           # the file's name when no family was given
    assert (other.path / used["font"]["src"]).read_bytes() == font.read_bytes()
    assert used["font"]["src"].startswith("03_wip/text_set/") and used["logo"].startswith("03_wip/text_set/")
    rows = {r["file"]: r for r in manifest.rows(other)}
    assert json.loads(rows[used["logo"]]["params"])["library"].endswith("logo_v01.png")
    assert text_sets.into_run(other, text_sets.for_run(other)) == used    # the same files are not copied twice
    (ws / "library" / "channels" / "exampleedu" / "text" / "logo_v01.png").unlink()
    fresh = RunFolder.create(ws, "third", date(2026, 11, 19), playbook=ORGANIC_VIDEO)
    config.save(fresh, {**organic_config.defaults(), "channels": ["exampleedu"]})
    with pytest.raises(Stop, match="logo_v01.png"):
        text_sets.into_run(fresh, text_sets.for_run(fresh))


# --- the command ------------------------------------------------------------------------------------

def test_tm_brand_text_style_saves_from_a_style_file_and_shows_the_runs_set(ws, capsys):
    run = _organic(ws)
    font, logo = _files(run)
    style = run.path / "03_wip" / "text_style_v03.json"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text(json.dumps({"look": "marker", "accent": "#E53935",
                                 "font": {"family": "Brand", "src": "02_research/brand/Brand-Bold.ttf"},
                                 "logo": "02_research/brand/logo.png"}), encoding="utf-8")
    code, out = _cli(capsys, "brand", "text-style", "save", "--run", str(run.path), "--kind", "channel",
                     "--name", "exampleedu", "--style", "03_wip/text_style_v03.json", "--note", "the marker one")
    assert code == 0, out
    assert out["file"] == "library/channels/exampleedu/text_style_v01.json"
    code, out = _cli(capsys, "brand", "text-style", "show", "--run", str(run.path))
    assert code == 0 and out["text_style"]["look"] == "marker" and out["text_style"]["font"]["family"] == "Brand"
    code, out = _cli(capsys, "brand", "text-style", "show", "--run", str(_ad(ws, "Nobody").path))
    assert code == 0 and out["text_style"] is None and out["suggested"][0] == "outline"


# --- organic video: the edit's text style follows the saved set -------------------------------------

from test_organic_edit import remotion  # noqa: E402,F401  (tm render without Node)

from tm import organic_edit, organic_gates, organic_pages  # noqa: E402


def _cli_last(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _picture(run):
    (run.path / "03_wip").mkdir(exist_ok=True)
    (run.path / "03_wip" / "frame_v01_0.png").write_bytes(b"\x89PNG the first frame")
    return "03_wip/frame_v01_0.png"


def _look(capsys, run, *extra):
    return _cli_last(capsys, "organic", "text", "look", "--run", str(run.path), "--picture", _picture(run),
                     "--caption", "I check what is rising", "--overlay", "How I find ideas", *extra)


def test_no_saved_set_draws_the_default_outline_set(ws, remotion, capsys):
    run = _organic(ws)
    code, out = _look(capsys, run)
    assert code == 0, out
    style = json.loads((run.path / out["style"]).read_text(encoding="utf-8"))
    assert style["look"] == "outline" and out["text_set"] is None


def test_the_saved_set_is_drawn_with_the_brands_font_and_logo_and_a_video_can_use_another(ws, remotion, capsys):
    brand.save(ws, EXAMPLEEDU, run=None)
    run = _organic(ws)
    font, logo = _files(run)
    text_sets.save(ws, "channel", "exampleedu", look="pill", accent="#1A237E", font=font, font_family="Brand",
                   logo=logo, run=run, note="the pill one")
    code, out = _look(capsys, run)
    assert code == 0, out
    assert out["text_set"] == "library/channels/exampleedu/text_style_v01.json"
    style = json.loads((run.path / out["style"]).read_text(encoding="utf-8"))
    assert (style["look"], style["accent"]) == ("pill", "#1A237E")
    assert style["font"] == {"family": "Brand", "src": "03_wip/text_set/brand-bold_v01.ttf"}
    assert style["logo"] == "03_wip/text_set/logo_v01.png" and organic_edit.style_problems(style) == []
    props = json.loads((run.path / out["props"]).read_text(encoding="utf-8"))
    assert props["brandFont"] == style["font"]
    overlay, caption = props["captions"]
    assert caption["look"] == "pill" and caption["ink"] == "#FFFFFF"
    assert overlay["overlay"]["ink"] == "#FFFFFF" and overlay["overlay"]["accent"] == "#1A237E"
    # one video in another set, for its format: the saved set stays
    code, out = _look(capsys, run, "--look", "native")
    assert code == 0, out
    assert json.loads((run.path / out["style"]).read_text(encoding="utf-8"))["look"] == "native"
    assert text_sets.for_run(run)["look"] == "pill"


def test_a_style_with_a_bad_font_or_logo_is_refused():
    style = organic_edit.default_style(caption="a", overlay="b", look="pop", font={"family": "", "src": 3},
                                       logo="logo.svg")
    said = " | ".join(organic_edit.style_problems(style))
    assert "font must be" in said and "logo must be" in said


def test_a_held_hook_stays_the_whole_video_and_the_end_card_has_the_logo(ws, remotion, capsys):
    run = _organic(ws)
    font, logo = _files(run)
    text_sets.save(ws, "channel", "exampleedu", look="outline", accent="#FFD84D", font=font, logo=logo, run=run,
                   note="x")
    code, out = _look(capsys, run)
    assert code == 0, out
    assert _cli_last(capsys, "organic", "text", "approve", "--run", str(run.path), "--style", out["style"],
                     "--by", "rule", "--note", "the channel's saved text set")[0] == 0
    (run.path / "03_wip" / "vo_v01.mp3").write_bytes(b"vo")
    (run.path / "03_wip" / "take.mp4").write_bytes(b"take")
    edit = {"width": 1080, "height": 1920, "fps": 24,
            "segments": [{"src": "03_wip/take.mp4", "start": 0, "end": 4}, {"src": "03_wip/take.mp4", "start": 5,
                                                                             "end": 8}],
            "audioTracks": [{"src": "03_wip/vo_v01.mp3", "from": 0, "volume": 1}],
            "captions": [{"from": 0, "to": 2, "text": "How I find ideas", "style": "hook",
                          "overlay": {"kind": "hook", "hold": True}},
                         {"from": 2.5, "to": 4, "text": "+212%", "style": "hook",
                          "overlay": {"kind": "number", "sub": "this week"}},
                         {"from": 6, "to": 7, "text": "Follow for more", "style": "hook",
                          "overlay": {"kind": "end", "brand": "ExampleEdu"}}]}
    (run.path / "03_wip" / "edit_v01.props.json").write_text(json.dumps(edit), encoding="utf-8")
    (run.path / "03_wip" / "vo_v01.words.json").write_text(json.dumps(
        [{"word": "Hi", "start": 0.1, "end": 0.4}, {"word": "there.", "start": 0.5, "end": 0.9}]), encoding="utf-8")
    code, made = _cli_last(capsys, "organic", "captions", "--run", str(run.path), "--props",
                           "03_wip/edit_v01.props.json", "--words", "03_wip/vo_v01.words.json")
    assert code == 0, made
    props = json.loads((run.path / made["props"]).read_text(encoding="utf-8"))
    hook, number, end = [c for c in props["captions"] if c["style"] != "caption"]
    assert (hook["from"], hook["to"]) == (0, 7.0) and hook["place"] == "top"       # the whole video
    assert number["place"] == "middle"                                             # off the held hook
    assert end["overlay"]["logo"] == "03_wip/text_set/logo_v01.png" and end["overlay"]["brand"] == "ExampleEdu"
    assert props["brandFont"]["src"] == "03_wip/text_set/brand-bold_v01.ttf"


def test_the_images_page_shows_one_still_per_set_drawn(ws, remotion, capsys):
    run = _organic(ws)
    t = organic_pages.gate_words("en")
    assert organic_gates._text_looks(run, t) == []
    for look in ("outline", "native", "pop"):
        assert _look(capsys, run, "--look", look)[0] == 0
    assert _look(capsys, run, "--look", "native")[0] == 0          # the pick, drawn again as the latest
    refs = organic_gates._text_looks(run, t)
    assert [r["src"] for r in refs] == ["03_wip/text_look_v04.png", "03_wip/text_look_v03.png",
                                        "03_wip/text_look_v01.png"]
    assert "native" in refs[0]["caption"] and "pop" in refs[1]["caption"]
    assert organic_pages.gate_words("pl")["cap_text_set"] != t["cap_text_set"]          # translated


def test_show_suggests_the_three_sets_by_the_channels_type(ws, capsys):
    brand.save(ws, EXAMPLEEDU, run=None)                       # howto_education
    code, out = _cli(capsys, "brand", "text-style", "show", "--run", str(_organic(ws).path))
    assert code == 0 and out["text_style"] is None
    assert out["suggested"] == text_sets.suggest_looks("howto_education")
