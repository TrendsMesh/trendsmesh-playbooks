"""Issue #138 item 4 (owner decision #148 line 2, as changed by @piotr-lezon): a creative brief's animatic is always
drawn in one of the 49 library styles; the fixed sketch scenes are gone.

`tm brief animatic --style auto` picks each named concept's style (`animatic.matched`) from the concept's format,
hook, idea and tone, against the styles' cards (issue #162 item 3; a talking head, a screen recording and a UGC phone video get different styles; the channel's own style first with
`--own`), writes it into a new brief version as `animatic.style` with its poster, and writes each concept's build
prompt. A subagent writes the style module; `tm brief animatic --render` builds its page with `atlas_prompt.module_page`
and draws it with `atlas.render`. A concept without a style is refused. The brief page shows the style's name and
poster. CI has no browser: `atlas.need`, `atlas.layout` and `atlas.render` are replaced, as in test_animatic.py.
"""
from __future__ import annotations

import copy
from datetime import date
import json
from pathlib import Path

import pytest

from tm import animatic, atlas, atlas_prompt, brief_checks, brief_page, manifest, paths
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder

EXAMPLE = paths.bundled_data().parent / "skills" / "creative-brief" / "templates" / "brief_pack_example.json"
V01 = "04_final/brief_pack_v01.json"
WIP = "03_wip/animatic"


def _ad() -> dict:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    brief = {k: v for k, v in data.items() if not k.startswith("_")}
    c3 = copy.deepcopy(brief["concepts"][0])
    c3["id"], c3["title"] = "C3", "Unboxing the plan"
    c3["plugin"]["axes"]["format"] = "UGC phone video"
    brief["concepts"].append(c3)
    return brief


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    return folder


@pytest.fixture
def run(ws) -> RunFolder:
    run = RunFolder.create(ws, "Example App", date(2026, 1, 1), playbook=CREATIVE_BRIEF)
    path = run.path / V01
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_ad(), ensure_ascii=False), encoding="utf-8")
    return run


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _latest(run: RunFolder) -> dict:
    return json.loads(run.latest("04_final", "brief_pack", "json").read_text(encoding="utf-8"))


def _concept(brief: dict, cid: str) -> dict:
    return next(c for c in brief["concepts"] if c["id"] == cid)


def _module(beats) -> str:
    return ("(function () {\n  \"use strict\";\n  function draw(ctx, W, H, t) { ctx.fillRect(0, 0, W, H); }\n"
            f"  Player.register({{ id: \"c1\", name: \"C1\", duration: 15, beats: {json.dumps(beats)}, "
            "beatNames: [], draw, score() {} });\n})();\n")


def _fake_render(calls: list, seconds: float = 70):
    def render(page_, out_mp4, *, fps=atlas.FPS, stills=atlas.STILLS):
        out_mp4 = Path(out_mp4)
        assert not out_mp4.exists() and Path(page_).is_file()
        calls.append((Path(page_), out_mp4, fps))
        out_mp4.write_bytes(b"mp4")
        for s in stills:
            (out_mp4.parent / f"{out_mp4.stem}_still_{round(s * 100):03d}.png").write_bytes(b"png")
        return {"out": str(out_mp4), "duration": 15, "render_s": seconds, "page_errors": []}
    return render


@pytest.fixture
def renderer(monkeypatch):
    calls: list = []
    monkeypatch.setattr(atlas, "need", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(atlas, "missing", lambda: None)
    monkeypatch.setattr(atlas, "layout", lambda page_: {"beats": [0, 3, 9]})
    monkeypatch.setattr(atlas, "layout_problems", lambda summary: [])
    monkeypatch.setattr(atlas, "render", _fake_render(calls))
    return calls


# --- the choice -----------------------------------------------------------------------------------------------

def test_three_formats_get_three_styles_chosen_by_the_ranking():
    brief = _ad()
    picked = animatic.choose_styles(brief, ["C1", "C2", "C3"])
    ids = [picked[c]["styleId"] for c in ("C1", "C2", "C3")]
    assert len(set(ids)) == 3                                       # three formats, three looks
    for cid in ("C1", "C2", "C3"):
        kind, _ = animatic.rank_args(animatic.concept_format(_concept(brief, cid)))
        card = picked[cid]
        assert kind in card["tags"]["channels"], cid                 # each suits its format
        assert card["reason"] != "none" and card["why"], cid         # and says why
    assert animatic.rank_args("talking head")[0] == "lifestyle_vlog"
    assert animatic.rank_args("screen recording")[0] == "howto_education"
    assert animatic.rank_args("UGC phone video")[0] == "shop_product"
    assert animatic.rank_args(None) == (None, ())


def test_the_style_matches_the_concepts_hook_idea_and_tone():
    """Issue #162 item 3: the concept's own words (its hook, idea and the brief's tone) are scored against each
    style's description and what it suits, so a format no row of FORMAT_RANKS knows still gets a matched style."""
    brief = _ad()
    brief["tone"]["tone"] = "serious, a little tense"
    c1 = _concept(brief, "C1")
    c1["plugin"]["axes"]["format"] = "carousel"
    c1["title"] = "The case of the missing money"
    c1["one_liner"] = "An investigation into where the household money goes, cracked like a mystery."
    c1["hook"]["text"] = "Who took the grocery money?"
    picked = animatic.choose_styles(brief, ["C1"])["C1"]
    assert picked["styleId"] == "noir" and picked["reason"] == "words", picked["reason"]
    assert {"investigation", "mystery", "money"} <= set(picked["matched"])
    assert "investigation" in picked["why"] and "serious" in picked["why"]


def _unmatched(brief: dict) -> dict:
    """Every concept in words no style's card has (Polish) and in a format FORMAT_RANKS does not know."""
    brief["tone"]["tone"] = "ciepły"
    for c in brief["concepts"]:
        c["plugin"]["axes"].update(format="karuzela", angle="marnowanie jedzenia", hook_type="lista")
        c.update(title="Lodówka", one_liner="Rodzic otwiera lodówkę.", key_message="Mniej marnowania.",
                 hook={"text": "Co wyrzucam co tydzień", "style": "top", "description": "Tekst na ekranie."})
    return brief


def test_nothing_matched_is_said_plainly_and_the_agent_asks(run, capsys):
    """Never a silent fallback: with nothing to match, the reason says so, and the answer tells the agent to have
    the user pick a style or confirm this one (#176 line 54: with keywords given, and only when nothing scores)."""
    picked = animatic.choose_styles(_unmatched(_ad()), ["C1"])["C1"]
    assert picked["reason"] == "none" and picked["matched"] == []
    assert "nothing" in picked["why"].lower() and "next free style" not in picked["why"]
    (run.path / V01).write_text(json.dumps(_unmatched(_ad()), ensure_ascii=False), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1",
                     "--keywords", "C1: hook=lodówka")
    assert code == 0, out
    assert "No keywords" not in out["message"]
    assert out["styles"][0]["reason"] == "none"
    message = out["message"]
    assert "matched" in message and "pick" in message and "confirm" in message
    assert "--style <number|styleId> --concepts C1" in message


POLISH_KEYWORDS = {"format": "carousel, list", "tone": "warm, friendly", "hook": "fridge, food waste, weekly list"}


def test_a_polish_concept_with_english_keywords_gets_a_style_without_the_question(run, capsys):
    """#176 line 54: the style is scored on the English keywords Claude passes for the concept's format, tone and
    hook, whatever the brief's language; a Polish concept with them is matched, and nobody is asked."""
    picked = animatic.choose_styles(_unmatched(_ad()), ["C1"], keywords={"C1": POLISH_KEYWORDS})["C1"]
    assert picked["reason"] != "none", picked["why"]
    assert "warm" in picked["shared_tone"] or picked["matched"], picked
    (run.path / V01).write_text(json.dumps(_unmatched(_ad()), ensure_ascii=False), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1",
                     "--keywords", "C1: format=carousel, list; tone=warm, friendly; hook=fridge, food waste")
    assert code == 0, out
    assert out["styles"][0]["reason"] != "none"
    assert "pick a style" not in out["message"]
    params = [json.loads(r["params"]) for r in manifest.rows(run) if r["file"] == out["brief"]]
    assert params and params[-1]["animatic_keywords"]["C1"]["tone"] == "warm, friendly"


def test_the_keywords_hook_words_meet_the_styles_card_but_never_its_poor_for_part():
    """The hook keywords count as the concept's own words do: against the card's name, description and the
    positive part of `suits`; what a style is poor for never counts."""
    brief = _unmatched(_ad())
    picked = animatic.choose_styles(brief, ["C1"], keywords={"C1": {"hook": "investigation, mystery, money",
                                                                     "tone": "serious"}})["C1"]
    assert picked["styleId"] == "noir" and {"investigation", "mystery"} <= set(picked["matched"])
    poor = {}
    for s in atlas_prompt.ranked():
        parts = str(atlas_prompt.find_style(s["styleId"]).get("suits") or "").split(";", 1)
        if len(parts) == 2:
            poor = {"id": s["styleId"], "words": animatic._words(parts[1]) - animatic._card_words(s["styleId"])}
            if poor["words"]:
                break
    assert poor.get("words"), "no style's card has a poor-for word of its own"
    cards = animatic.matched(brief, _concept(brief, "C1"),
                             keywords={"hook": ", ".join(sorted(poor["words"]))})
    card = next(c for c in cards if c["styleId"] == poor["id"])
    assert card["matched"] == []


def test_only_a_concept_nothing_scores_on_asks_and_no_keywords_says_to_pass_them(run, capsys):
    """The question comes only when nothing scores; when no keywords were given, the answer first says to pass
    them in English."""
    (run.path / V01).write_text(json.dumps(_unmatched(_ad()), ensure_ascii=False), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1")
    assert code == 0, out
    assert "--keywords" in out["message"] and "English" in out["message"]


@pytest.mark.parametrize("given", ["C1 format=carousel", "C1: colour=red", "C9: tone=warm", "C1: tone="])
def test_keywords_that_cannot_be_read_are_refused(run, capsys, given):
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1",
                     "--keywords", given)
    assert code != 0 and "--keywords" in out.get("message", json.dumps(out)), out
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"     # nothing written


def test_keywords_go_with_style_auto(run, capsys):
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "noir", "--concepts", "C1",
                     "--keywords", "C1: tone=warm")
    assert code != 0 and "--keywords" in json.dumps(out), out


def test_the_channels_own_style_comes_first_and_a_given_style_is_kept():
    brief = _ad()
    own = animatic.choose_styles(brief, ["C1", "C2"], own="12")
    assert {c["styleId"] for c in own.values()} == {"linocut"} and own["C1"]["reason"] == "channel"
    given = animatic.choose_styles(brief, ["C2"], given="ink-wash")
    assert given["C2"]["styleId"] == "ink-wash" and given["C2"]["reason"] == "given"
    with pytest.raises(ValueError, match="Unknown style"):
        animatic.choose_styles(brief, ["C2"], given="no-such-style")


def test_a_later_concept_keeps_clear_of_the_styles_the_brief_has():
    brief = _ad()
    first = animatic.choose_styles(brief, ["C1"])["C1"]["styleId"]
    _concept(brief, "C3")["animatic"] = {"style": first}
    brief["concepts"][0]["plugin"]["axes"]["format"] = "UGC phone video"
    assert animatic.choose_styles(brief, ["C1"])["C1"]["styleId"] != first


# --- no sketch: every animatic is styled -----------------------------------------------------------------------

def test_a_concept_without_a_style_is_refused_and_nothing_is_written(run, capsys, renderer):
    """No sketch to fall back on (#148 line 2): a concept with no `animatic.style` is a stop that names the style step."""
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 2 and out["status"] == "stop", out
    assert "C1" in out["message"] and "--style auto --concepts C1" in out["message"]
    assert "Nothing was written" in out["message"]
    assert not (run.path / WIP).exists() and manifest.rows(run) == rows and not renderer
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"


def test_the_sketch_library_is_gone():
    """The fixed sketch scenes (`animatic_js/scenes.js`) no longer draw animatics: the plugin does not ship them."""
    folder = Path(animatic.__file__).parent / "animatic_js"
    assert not (folder / "scenes.js").exists() and not (folder / "engine.js").exists()
    assert not hasattr(animatic, "build_anim") and not hasattr(animatic, "scene_names")


# --- the style step: tm brief animatic --style ------------------------------------------------------------------

def test_the_style_step_writes_the_brief_a_poster_and_a_prompt_per_concept(run, capsys):
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1,C2")
    assert code == 0, out
    assert out["brief"] == "04_final/brief_pack_v02.json"
    brief = _latest(run)
    for row in out["styles"]:
        cid, style = row["concept"], atlas_prompt.find_style(row["style"])
        a = _concept(brief, cid)["animatic"]
        assert a["style"] == style["styleId"]
        assert a["poster"] == f"animatic/style_{style['order']:02d}_{style['styleId']}.jpg"
        poster = run.path / animatic.RENDERS / Path(a["poster"]).name
        assert poster.read_bytes() == atlas_prompt.preview_files(style)[0].read_bytes()
        assert row["prompt"] == f"{WIP}/{cid}_prompt_v01.txt" and row["module"] == f"{WIP}/{cid}_style_v01.js"
        prompt = (run.path / row["prompt"]).read_text(encoding="utf-8")
        assert style["name"] in prompt and "## An animatic of a brief" in prompt
        for beat in _concept(brief, cid)["beats"]:
            for text in beat["animatic"]["texts"]:
                assert text["str"] in prompt
        assert "1080x1920" in prompt and "1080x1350" in prompt        # both formats drawn from one module
    assert "animatic" not in _concept(brief, "C3")                   # not named, not styled
    assert not list((run.path / WIP).glob("*.html"))                 # nothing drawn yet
    rows = [r for r in manifest.rows(run) if r["file"].endswith("_prompt_v01.txt")]
    assert len(rows) == 2 and all(json.loads(r["params"])["style"] for r in rows)
    assert "C1_style_v01.js" in out["message"] and "--render" in out["message"]


def test_the_style_step_refuses_render_and_an_unknown_style(run, capsys):
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--render")
    assert code == 1 and "--style" in out["message"]
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "nope", "--concepts", "C1")
    assert code == 1 and "Unknown style" in out["message"]
    assert run.latest("04_final", "brief_pack", "json").name == "brief_pack_v01.json"


# --- the render of a styled concept -----------------------------------------------------------------------------

def _styled(run, capsys, cid="C1", style="ink-wash") -> dict:
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", style, "--concepts", cid)
    assert code == 0, out
    return out["styles"][0]


def test_a_styled_concept_is_drawn_from_its_style_module_not_from_scenes(run, capsys, renderer):
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 0, out
    assert [i["format"] for i in out["items"]] == ["9x16", "4x5"]
    assert not (run.path / WIP / "scenes.js").exists() and not (run.path / WIP / "engine.js").exists()
    version = out["version"]
    page = (run.path / WIP / f"C1_9x16_{version}.html").read_text(encoding="utf-8")
    assert "Player.register" in page and "window.Brush" in page and "scenes.js" not in page
    assert '"width": 1080, "height": 1920' in page
    assert '"height": 1350' in (run.path / WIP / f"C1_4x5_{version}.html").read_text(encoding="utf-8")
    assert len(renderer) == 2
    a = _concept(_latest(run), "C1")["animatic"]
    assert a == {"9x16": f"animatic/C1_animatic_9x16_{version}.mp4", "4x5": f"animatic/C1_animatic_4x5_{version}.mp4",
                 "default": "9x16", "style": "ink-wash", "poster": "animatic/style_20_ink-wash.jpg"}
    assert out["items"][0]["style"] == "ink-wash"


def test_the_module_needs_one_beat_per_beat_of_the_brief(run, capsys, renderer):
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 2 and "2 beats" in out["message"] and "3 beats" in out["message"]
    assert not list((run.path / WIP).glob("*.html")) and not renderer


def test_beats_kept_in_a_constant_are_read_from_the_page(run, capsys, renderer, monkeypatch):
    """A module shaped like the reference modules (`beats: BEATS`) is counted as its page registers it."""
    row = _styled(run, capsys)
    code = (_module([0, 3]).replace("beats: [0, 3]", "beats: BEATS")
            .replace('"use strict";', '"use strict"; const BEATS = [0, 3];'))
    (run.path / row["module"]).write_text(code, encoding="utf-8")
    monkeypatch.setattr(atlas, "layout", lambda page_: {"beats": [0, 3]})
    code_, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code_ == 2 and "2 beats" in out["message"]
    monkeypatch.setattr(atlas, "layout", lambda page_: {"beats": [0, 3, 9]})
    assert _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")[0] == 0


def test_a_frames_list_does_not_refuse_a_brief_animatic(run, capsys, renderer):
    """Issue #141's check compares an organic item's storyboard with its frames list; a brief's beats are its own."""
    row = _styled(run, capsys)
    (run.path / WIP / "frames_v01.json").write_text(json.dumps([{"scene": n} for n in range(5)]), encoding="utf-8")
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 0, out


def test_a_styled_concept_without_its_module_is_a_stop(run, capsys, renderer):
    row = _styled(run, capsys)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 2 and row["prompt"] in out["message"] and row["module"] in out["message"]
    assert not renderer


def test_a_module_from_before_the_style_changed_is_not_drawn(run, capsys, renderer):
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    again = _styled(run, capsys, style="clay")                       # a new style: a new prompt, v02
    assert again["prompt"].endswith("C1_prompt_v02.txt")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 2 and again["module"] in out["message"]


def test_a_styled_concept_and_one_without_a_style_in_one_call_is_refused(run, capsys, renderer):
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1,C2",
                     "--formats", "9x16")
    assert code == 2 and "C2" in out["message"] and "--style auto --concepts C2" in out["message"], out
    assert "C1" not in out["message"]                                       # C1 has its style
    assert not list((run.path / WIP).glob("*.html")) and not renderer


@pytest.mark.parametrize("image", ["../lumen.png", "/tmp/lumen.png", "https://cdn.example.com/lumen.png",
                                   "01_base/none.png", "04_final/brief_pack_v01.json", 3])
def test_a_picture_that_is_not_an_image_of_the_run_stops(run, capsys, image):
    """A beat's `params.image` is a picture of the product in the run (issue #12), or the style step stops."""
    brief = _ad()
    brief["concepts"][0]["beats"][1]["animatic"]["params"] = {"image": image}
    (run.path / V01).write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    rows = manifest.rows(run)
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--style", "auto", "--concepts", "C1")
    assert code == 2 and "names the image" in out["message"] and "Nothing was written" in out["message"], out
    assert not (run.path / WIP).exists() and manifest.rows(run) == rows


# --- the time the question says ---------------------------------------------------------------------------------

CARDS = paths.bundled_data().parent / "skills" / "creative-brief" / "references" / "checkin-cards.md"
NO_FIXED_TIME = ("Animatics take a while: depending on the style and the computer, from a few to over a dozen "
                 "minutes per concept.")


def test_the_question_gives_no_fixed_time(run, capsys, renderer, tmp_path):
    """#148 line 157 as changed by @piotr-lezon: no measured or default minutes, the one sentence instead."""
    cards = " ".join(CARDS.read_text(encoding="utf-8").split())
    assert NO_FIXED_TIME in cards and "<N>" not in cards and "--estimate" not in cards
    for gone in ("minutes_per_concept", "DEFAULT_MINUTES", "TIMING", "_record_time"):
        assert not hasattr(animatic, gone), gone
    assert main(["brief", "animatic", "--run", str(run.path), "--estimate", "--json"]) != 0   # gone with it
    capsys.readouterr()
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 0 and all(isinstance(i["render_s"], (int, float)) for i in out["items"]), out
    assert not (tmp_path / "data" / "animatic_timing.json").exists()   # no render time is kept


# --- the check and the page -------------------------------------------------------------------------------------

def test_brief_check_refuses_a_style_the_library_has_not(run):
    brief = _ad()
    brief["concepts"][0]["animatic"] = {"style": "no-such-style"}
    found = [p for p in brief_checks.check(run, brief, "concepts", {}) if p.field.endswith("animatic.style")]
    assert found and "no-such-style" in found[0].what
    brief["concepts"][0]["animatic"] = {"style": "ink-wash", "poster": "animatic/style_20_ink-wash.jpg"}
    assert not [p for p in brief_checks.check(run, brief, "concepts", {}) if "animatic" in p.field]
    assert brief_checks.shape(brief, "production") == []


def test_brief_check_needs_no_sketch_scene_per_beat(run):
    """The per-beat sketch scene held only while the sketch was the default: a beat may leave it out, or keep an old
    one, at every stage (an organic brief's O7 check no longer reads it either)."""
    brief = _ad()
    beats = [b for c in brief["concepts"] for b in c["beats"]]
    for beat in beats[:-1]:
        beat["animatic"].pop("scene", None)
    beats[-1]["animatic"]["scene"] = "dance_floor"                        # a name no library has: not read
    for stage in ("concepts", "brief", "production"):
        assert not [p for p in brief_checks.check(run, brief, stage, {}) if "scene" in p.field + p.what], stage
        assert brief_checks.shape(brief, stage) == [], stage


def test_the_page_shows_the_styles_name_and_poster():
    concept = _ad()["concepts"][0]
    concept["animatic"] = {"9x16": "animatic/C1_animatic_9x16_v02.mp4", "default": "9x16", "style": "ink-wash",
                           "poster": "animatic/style_20_ink-wash.jpg"}
    html = brief_page.concept_html(concept, 1, 3)
    assert "Ink Wash" in html and 'src="animatic/style_20_ink-wash.jpg"' in html
    assert "ink-wash" not in html.replace("style_20_ink-wash.jpg", "")      # the name, never the id
    assert ("C1", "poster", "animatic/style_20_ink-wash.jpg") in brief_page._refs({"concepts": [concept]})
    plain = _ad()["concepts"][1]
    assert "anim-style" not in brief_page.concept_html(plain, 2, 3)


def test_the_build_prompt_has_an_animatic_mode():
    style = atlas_prompt.find_style("ink-wash")
    text = atlas_prompt.build(style, content="The beats", aspect="9:16", animatic={"pictures": []}, duration=15)
    assert "## An animatic of a brief" in text and "The beats" in text and "15 s" in text
    with pytest.raises(ValueError):
        atlas_prompt.build(style, storyboard=True, animatic={"pictures": []})
