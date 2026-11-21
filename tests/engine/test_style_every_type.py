"""Issue #138 item 3: the picked style card shapes every production type. An image or a video prompt carries the card's
look in words (`atlas_prompt.look_text`), and the guard refuses a paid image or video spec without it while
`taste.style` is set, before anything is paid."""

from __future__ import annotations

import copy
import json

import test_organic_specs as specs
from test_organic_specs import engine, ov  # noqa: F401  (the fixtures)
from tm import atlas_prompt, organic_proposals, organic_specs
from tm.cli import main


def test_a_style_is_offered_for_every_production_type():
    assert set(organic_proposals.STYLED) == set(organic_proposals.PRODUCTIONS)
    for production in organic_proposals.PRODUCTIONS:
        p = {"plugin": {"production": production, "styles": [{"style": 7, "why": "w"}, {"style": 4, "why": "w"}]}}
        assert [o["value"] for o in organic_proposals.style_options(p, None)] == [
            organic_proposals.style_value(7), organic_proposals.style_value(4)], production


def test_the_look_text_is_the_cards_looks_avoid_palette_and_fonts():
    card = atlas_prompt.find_style(7)
    text = atlas_prompt.look_text(card)
    assert text.startswith(f"Look of style {card['order']} {card['name']}: ")
    for item in card["look"] + card["avoid"]:
        assert item in text
    for p in card["palette"]:
        assert p["hex"] in text
    for font in card["fonts"]:
        assert font in text
    assert "\n" not in text                                          # one line, to copy into a prompt
    assert atlas_prompt.look_text("7") == text == atlas_prompt.look_text(f"{card['order']} {card['name']}")


def test_atlas_styles_json_gives_each_styles_look_text(capsys):
    assert main(["organic", "atlas-styles", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["styles"]
    assert rows and all(r["look_text"] == atlas_prompt.look_text(str(r["order"])) for r in rows)


def _styled(run, style="7"):
    pack = specs._pack()
    pack["taste"]["style"] = organic_proposals.style_value(style)
    specs._check_pack(run, pack, 2)
    return pack


def test_an_image_spec_without_the_styles_look_is_refused(ov):
    _styled(ov)
    card = atlas_prompt.find_style(7)
    problems = organic_specs.check(ov, specs.HOST, specs._spec(ov, "host", specs.HOST))
    assert problems == [f"This video's style is {card['name']}: put its look (the card's Looks, Avoid, palette and "
                        "fonts) in the prompt."]
    spec = copy.deepcopy(specs.HOST)
    spec["input"]["prompt"] += " " + atlas_prompt.look_text(card).upper().replace(": ", ":  ")   # case and spaces aside
    assert organic_specs.check(ov, spec, specs._spec(ov, "host", spec)) == []


def test_no_style_no_look_needed(ov):
    assert organic_specs.check(ov, specs.HOST, specs._spec(ov, "host", specs.HOST)) == []


def test_the_guard_refuses_before_anything_is_paid(ov, engine, capsys):
    _styled(ov)
    code, out = specs._tool(capsys, ov, specs._spec(ov, "host", specs.HOST), "host")
    assert code == 2 and "put its look" in out["message"] and engine == []
