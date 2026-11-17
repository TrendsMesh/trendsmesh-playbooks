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
