"""Video fonts (issue 3, problem 1): the subsets a composition loads for the market language, the family it falls
back to, where the market language comes from, and the coverage check before a render."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from tm import render, video_fonts as vf
from tm.runfolder import RunFolder
from tm.tools import _common as common

LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, "
         "U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
LATIN_EXT = ("U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, "
             "U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF")
CYRILLIC = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116"
CYRILLIC_EXT = "U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F"
GREEK = "U+0370-0377, U+037A-037F, U+0384-038A, U+038C, U+038E-03A1, U+03A3-03FF"


def _mjs(family: str, ranges: dict[str, str], subsets: list[str]) -> str:
    """A font module laid out as @remotion/google-fonts generates it (its getInfo)."""
    rows = ",\n".join(f'    {json.dumps(k) if not k.isidentifier() else k}: "{v}"' for k, v in ranges.items())
    listed = ", ".join(json.dumps(s) for s in subsets)
    return (f'import {{ loadFonts }} from "./ABeeZee-x.mjs";\n\n// src/{family}.ts\nvar getInfo = () => ({{\n'
            f'  fontFamily: "{family}",\n  importName: "{family}",\n  unicodeRanges: {{\n{rows}\n  }},\n'
            f'  fonts: {{\n    normal: {{\n      "400": {{}}\n    }}\n  }},\n  subsets: [{listed}]\n}});\n')


@pytest.fixture
def fonts(tmp_path) -> Path:
    d = tmp_path / "esm"
    d.mkdir()
    latin = {"latin-ext": LATIN_EXT, "latin": LATIN}
    cyr = {"cyrillic-ext": CYRILLIC_EXT, "cyrillic": CYRILLIC}
    (d / "Montserrat.mjs").write_text(_mjs("Montserrat", {**cyr, **latin}, ["cyrillic", "cyrillic-ext", "latin", "latin-ext"]))
    (d / "Poppins.mjs").write_text(_mjs("Poppins", latin, ["latin", "latin-ext"]))
    (d / "BebasNeue.mjs").write_text(_mjs("Bebas Neue", latin, ["latin", "latin-ext"]))
    (d / "NotoSans.mjs").write_text(_mjs("Noto Sans", {**cyr, "greek": GREEK, **latin},
                                         ["cyrillic", "cyrillic-ext", "greek", "latin", "latin-ext"]))
    # a chunked family: "japanese" is not a key of its own, it is every numbered chunk
    (d / "NotoSansJP.mjs").write_text(_mjs("Noto Sans JP", {"[0]": "U+65E5, U+672C", "[1]": "U+3042-3093, U+8A9E"},
                                           ["japanese", "latin", "latin-ext"]))
    return d


# --- the choice -----------------------------------------------------------------------------

@pytest.mark.parametrize("tag, script", [
    ("pl", "latin"), ("pl-PL", "latin"), ("PL", "latin"), ("es_MX", "latin"), (None, "latin"), ("", "latin"),
    ("xx", "latin"), ("vi", "vietnamese"), ("uk", "cyrillic"), ("ru-RU", "cyrillic"), ("sr", "cyrillic"),
    ("sr-Latn-RS", "latin"), ("el", "greek"), ("hi", "devanagari"), ("ar-EG", "arabic"), ("he", "hebrew"),
    ("th", "thai"), ("ja", "japanese"), ("ko", "korean"), ("zh", "chinese-simplified"),
    ("zh-CN", "chinese-simplified"), ("zh-TW", "chinese-traditional"), ("zh-Hant-HK", "chinese-traditional"),
])
def test_script_of_a_language_tag(tag, script):
    assert vf.script_of(tag) == script


L = ["latin", "latin-ext"]


@pytest.mark.parametrize("primary, tag, drawn", [
    ("Montserrat", "pl", [("Montserrat", L)]),
    ("Montserrat", None, [("Montserrat", L)]),   # latin-ext always, not latin alone
    ("Montserrat", "uk", [("Montserrat", [*L, "cyrillic", "cyrillic-ext"])]),
    ("Montserrat", "vi", [("Montserrat", [*L, "vietnamese"])]),
    ("Poppins", "hi", [("Poppins", [*L, "devanagari"])]),
    ("Fredoka", "he", [("Fredoka", [*L, "hebrew"])]),
    # issue 3, item 6: the composition's font keeps the letters it has, the script's fallback draws the others
    ("Poppins", "ru", [("Poppins", L), ("NotoSans", ["cyrillic", "cyrillic-ext"])]),
    ("BebasNeue", "bg", [("BebasNeue", L), ("NotoSans", ["cyrillic", "cyrillic-ext"])]),
    ("Montserrat", "el", [("Montserrat", L), ("NotoSans", ["greek"])]),
    ("Montserrat", "ar", [("Montserrat", L), ("NotoSansArabic", ["arabic"])]),
    ("Montserrat", "he", [("Montserrat", L), ("NotoSansHebrew", ["hebrew"])]),
    ("Montserrat", "ja", [("Montserrat", L), ("NotoSansJP", ["japanese"])]),
    ("Poppins", "zh-TW", [("Poppins", L), ("NotoSansTC", ["chinese-traditional"])]),
])
def test_stack_keeps_the_font_for_its_letters_and_falls_back_for_the_rest(primary, tag, drawn):
    assert vf.stack(primary, tag) == drawn


def test_table_is_consistent():
    t = vf.table()
    for script, spec in t["scripts"].items():
        assert spec["fallback"] in t["families"], script
        assert set(spec["subsets"]) <= set(t["families"][spec["fallback"]]["subsets"]), script
        assert {"latin", "latin-ext"} <= set(spec["subsets"]), script
    assert set(t["languages"].values()) <= set(t["scripts"])
    for comp in render.COMPS:
        named = t["compositions"][comp]
        for fam in (named.values() if isinstance(named, dict) else [named]):
            assert fam in t["families"], (comp, fam)


def test_compositions_load_fonts_through_the_table_only():
    """No composition loads a Google Font of its own: every one goes through fonts.ts, which takes the language
    prop, and fonts.ts has a loader for every family of the table."""
    src = Path(__file__).resolve().parents[2] / "remotion" / "src"
    for comp in render.COMPS:
        text = (src / f"{comp}.tsx").read_text(encoding="utf-8")
        assert "@remotion/google-fonts" not in text and "language" in text, comp
    fonts_ts = (src / "fonts.ts").read_text(encoding="utf-8")
    for fam in vf.table()["families"]:
        assert f'@remotion/google-fonts/{fam}"' in fonts_ts, fam


# --- the market language ------------------------------------------------------------------

@pytest.mark.parametrize("value, tag", [("pl", "pl"), ("pl-PL", "pl-PL"), ("Polish", "pl"), ("polski", "pl"),
                                        ("Ukrainian", "uk"), (" ru_RU ", "ru-RU"), ("", None), (None, None),
                                        (3, None), ("Klingon", None)])
def test_language_tag(value, tag):
    assert vf.language_tag(value) == tag


def _run(tmp_path, cfg: dict | None, playbook: str = "refresh-ad") -> RunFolder:
    run = RunFolder.create(tmp_path / "ws", "ad", date(2026, 11, 5), playbook)
    if cfg is not None:
        (run.path / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return run


def test_market_language_prefers_languages_market(tmp_path):
    run = _run(tmp_path, {"languages": {"market": "uk"}, "account": {"language": "Polish"}})
    assert vf.market_language(run) == ("uk", "languages.market in config.yaml")


def test_market_language_falls_back_to_account_language(tmp_path):
    run = _run(tmp_path, {"account": {"language": "Polish"}})
    assert vf.market_language(run) == ("pl", "account.language in config.yaml")


def test_market_language_none_without_config(tmp_path):
    assert vf.market_language(_run(tmp_path, None)) == (None, None)


def test_market_language_of_an_organic_run_is_its_audience_language(tmp_path, monkeypatch):
    from tm import organic_config

    run = _run(tmp_path, {"channels": ["kanal"]}, "organic-video")
    seen = []
    monkeypatch.setattr(organic_config, "_audience_language",
                        lambda r, given, channels: seen.append(channels) or "pl")
    assert vf.market_language(run) == ("pl", "the channel profile's audience_language")
    assert seen == [["kanal"]]


# --- on-screen texts ----------------------------------------------------------------------

def test_texts_of_each_composition():
    assert vf.texts("HookSwap", {"cards": [{"lines": [{"at": 0, "text": "Zażółć"}]}]}) == \
        [("cards[0].lines[0].text", "Zażółć", "BebasNeue")]
    words = vf.texts("WordCaptions", {"style": {"font": "nunito"}, "words": [{"text": "straße"}],
                                      "probe": [{"text": "ab", "font": "fredoka"}]})
    assert words == [("words[0].text", "straße", "Nunito"), ("words[0].text", "STRASSE", "Nunito"),
                     ("probe[0].text", "ab", "Fredoka"), ("probe[0].text", "AB", "Fredoka")]
    assert vf.texts("WordCaptions", {"style": {"font": "montserrat600", "textTransform": "none"},
                                     "words": [{"text": "x"}]}) == [("words[0].text", "x", "Montserrat")]
    assert vf.texts("OrganicCaptions", {"captions": [{"text": "a"}, {"text": 5}]}) == \
        [("captions[0].text", "a", "Montserrat")]
    ranking = {"title": [[{"text": "Top"}, {"text": "5"}]], "teaser": "t",
               "items": [{"label": "L", "score": "9/10", "emoji": "🔥"}]}
    assert [w for w, _, _ in vf.texts("RankingSplit", ranking)] == \
        ["title[0][0].text", "title[0][1].text", "teaser", "items[0].label", "items[0].score"]
    assert {f for _, _, f in vf.texts("RankingList", ranking)} == {"Montserrat"}
    quiz = {"title": "T", "answerLine": "A", "options": [{"label": "1", "name": "N", "note": "x"}]}
    assert [w for w, _, _ in vf.texts("QuizGrid", quiz)] == \
        ["title", "answerLine", "options[0].label", "options[0].name", "options[0].note"]


# --- the coverage check -------------------------------------------------------------------

def test_polish_text_is_covered_in_latin_runs(fonts):
    data = {"captions": [{"text": "Zażółć gęślą jaźń „cytat” – 5 zł €"}]}
    assert vf.check("OrganicCaptions", data, "pl", fonts) == [("Montserrat", ["latin", "latin-ext"])]
    vf.check("OrganicCaptions", data, None, fonts)   # latin-ext is loaded for any Latin-script run


def test_cyrillic_text_in_a_polish_run_stops_and_names_the_letters(fonts):
    data = {"captions": [{"text": "ok"}, {"text": "Привіт"}]}
    with pytest.raises(common.ToolStop) as stop:
        vf.check("OrganicCaptions", data, "pl", fonts)
    msg = str(stop.value)
    assert "captions[1].text" in msg and "П" in msg and "U+041F" in msg and "Montserrat" in msg
    assert "Nothing was rendered" in msg and "languages.market" in msg


def test_cyrillic_text_in_a_ukrainian_run_is_covered(fonts):
    data = {"captions": [{"text": "Привіт, ґанок! Їжак"}]}
    assert [f for f, _ in vf.check("OrganicCaptions", data, "uk", fonts)] == ["Montserrat"]


def test_a_font_without_the_script_is_checked_against_its_fallback(fonts):
    data = {"items": [{"label": "Привет"}], "title": [[{"text": "Топ 5"}]]}
    assert vf.check("RankingSplit", data, "ru", fonts) == [("Poppins", L), ("NotoSans", ["cyrillic", "cyrillic-ext"])]
    drawn = vf.check("HookSwap", {"cards": [{"lines": [{"text": "Γειά, OK 5"}]}]}, "el", fonts)
    assert [f for f, _ in drawn] == ["BebasNeue", "NotoSans"]


def test_emoji_and_their_joiners_are_not_font_letters(fonts):
    data = {"captions": [{"text": "Super 🔥❤️ 👍🏽 1️⃣ 👨‍👩‍👧 ✨\n"}]}
    vf.check("OrganicCaptions", data, "pl", fonts)


def test_a_chunked_family_covers_every_chunk(fonts):
    vf.check("OrganicCaptions", {"captions": [{"text": "日本語 あ"}]}, "ja", fonts)
    with pytest.raises(common.ToolStop) as stop:
        vf.check("OrganicCaptions", {"captions": [{"text": "日本語 鮨"}]}, "ja", fonts)
    assert "鮨" in str(stop.value) and "NotoSansJP" in str(stop.value)


def test_a_chunked_fallback_loads_only_the_chunks_the_text_needs(fonts):
    """Issue 3, item 6: Remotion loads every numbered chunk of a CJK font for each weight (about 120), so a still
    took seconds; `tm render` names only the chunks holding a letter on screen."""
    def chunks(text, language="ja", comp="OrganicCaptions"):
        return vf.font_subsets(comp, {"captions": [{"text": text}]}, language, fonts)

    assert chunks("日本 OK") == {"NotoSansJP": ["[0]"]}
    assert chunks("語、あ 日") == {"NotoSansJP": ["[0]", "[1]"]}             # in number order
    assert chunks("OK 5") == {"NotoSansJP": []}                          # no Japanese letter: no chunk
    assert chunks("Zażółć", "pl") == {} and chunks("Привет", "uk") == {}  # nothing chunked is drawn
    two = vf.font_subsets("QuizGrid", {"title": "日本", "options": [{"label": "あ"}]}, "ja", fonts)
    assert two == {"NotoSansJP": ["[0]", "[1]"]}                          # every text of the composition
    (fonts / "Montserrat.mjs").unlink()                    # a composition's own font is never read for its chunks
    assert chunks("Zażółć", "pl") == {} and chunks("日本", "ja") == {"NotoSansJP": ["[0]"]}


def test_missing_font_data_is_an_error_not_a_pass(fonts):
    (fonts / "Montserrat.mjs").unlink()
    with pytest.raises(common.ToolError):
        vf.check("OrganicCaptions", {"captions": [{"text": "a"}]}, "pl", fonts)
    vf.check("OrganicCaptions", {"captions": []}, "pl", fonts)   # no text: nothing to read


# --- render ------------------------------------------------------------------------------

@pytest.fixture
def light_run(tmp_path, monkeypatch, fonts):
    root = tmp_path / "plugin"
    (root / "remotion" / "src").mkdir(parents=True)
    for name in ("package.json", "package-lock.json"):
        (root / "remotion" / name).write_text("{}")
    (root / "remotion" / "src" / "index.ts").write_text("//")
    (root / "env").mkdir()
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(render.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(render.paths, "pixi_env", lambda: {})
    monkeypatch.setattr(render.envtiers, "installed", lambda t: True)
    monkeypatch.setattr(render, "setup_done", lambda: True)
    monkeypatch.setattr(render, "fonts_dir", lambda: fonts)
    render.work_dir().mkdir(parents=True)
    run = _run(tmp_path, {"account": {"language": "Polish"}})
    (run.path / "01_base" / "a.mp4").write_bytes(b"x")
    return run


def _fake_remotion(monkeypatch) -> list:
    seen = []

    def fake(argv, **kw):
        props = next(a for a in argv if a.startswith("--props="))[len("--props="):]
        seen.append(json.loads(Path(props).read_text(encoding="utf-8")))
        Path(next(a for a in argv if ".part" in a)).write_bytes(b"png")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", fake)
    return seen


def test_render_passes_the_market_language_as_a_prop_and_records_it(light_run, monkeypatch):
    run = light_run
    seen = _fake_remotion(monkeypatch)
    props = run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a.mp4", "cards": [{"lines": [{"at": 0, "text": "Zażółć"}]}]}))
    render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v01.png")
    assert seen[-1]["language"] == "pl"
    assert "language" not in json.loads(props.read_text())     # the props file stays as written
    assert not list(render.work_dir().glob(".props*"))          # the filled-in copy is gone
    row = (run.path / "manifest.md").read_text(encoding="utf-8").splitlines()[-1]
    assert '"language": "pl"' in row or '\\"language\\": \\"pl\\"' in row


def test_render_keeps_a_language_the_props_give(light_run, monkeypatch):
    run = light_run
    seen = _fake_remotion(monkeypatch)
    props = run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a.mp4", "language": "uk",
                                 "cards": [{"lines": [{"at": 0, "text": "Привіт"}]}]}))
    render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v01.png")
    assert seen[-1]["language"] == "uk"


def test_render_stops_before_remotion_when_the_font_lacks_a_letter(light_run, monkeypatch):
    run = light_run
    calls = []
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: calls.append(a))
    props = run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a.mp4", "cards": [{"lines": [{"at": 0, "text": "Привіт"}]}]}))
    with pytest.raises(common.ToolStop) as stop:
        render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v01.png")
    assert calls == [] and "account.language in config.yaml" in str(stop.value)
    assert not (run.path / "03_wip" / "e_v01.png").exists()


def test_render_names_the_cjk_chunks_the_text_needs_and_records_only_the_language(light_run, monkeypatch):
    run = light_run
    seen = _fake_remotion(monkeypatch)
    props = run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a.mp4", "language": "ja",
                                 "cards": [{"lines": [{"at": 0, "text": "日本 OK"}]}]}))
    render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v01.png")
    assert seen[-1]["fontSubsets"] == {"NotoSansJP": ["[0]"]} and seen[-1]["language"] == "ja"
    assert "fontSubsets" not in json.loads(props.read_text())
    assert not list(render.work_dir().glob(".props*"))
    assert "fontSubsets" not in (run.path / "manifest.md").read_text(encoding="utf-8").splitlines()[-1]
    # chunks the props name are kept as they are
    given = {"NotoSansJP": ["[0]", "[1]"]}
    props.write_text(json.dumps({**json.loads(props.read_text()), "fontSubsets": given}))
    render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v02.png")
    assert seen[-1]["fontSubsets"] == given
    props.write_text(json.dumps({**json.loads(props.read_text()), "fontSubsets": ["[0]"]}))
    with pytest.raises(common.ToolError, match="fontSubsets"):
        render.still(run, "HookSwap", props, 0, run.path / "03_wip" / "e_v03.png")


def test_render_rejects_a_language_prop_that_is_not_text(light_run):
    props = light_run.path / "03_wip" / "edit.props.json"
    props.write_text(json.dumps({"base": "01_base/a.mp4", "language": 7, "cards": []}))
    with pytest.raises(common.ToolError):
        render.still(light_run, "HookSwap", props, 0, light_run.path / "03_wip" / "e_v01.png")
