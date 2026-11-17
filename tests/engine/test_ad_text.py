"""Create an ad's text layer (S6, issue #117 section 4): the cut stays ffmpeg's, the captions and overlays are drawn
over it with OrganicCaptions in the brand's text set, and edit_layers_vNN.json is written from the same props, each
caption's and overlay's box, so the layer check (S7) keeps working."""

from __future__ import annotations

import json
from datetime import date

import pytest

from test_organic_edit import remotion  # noqa: F401  (tm render without Node)
from tm import config, create_config, create_text, manifest, text_sets
from tm.cli import main
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder
from tm.tools import layer_check

SAFE = {"top": 260, "bottom": 380, "left": 90, "right": 200}


def _props(*captions, width=1080, height=1920):
    return {"width": width, "height": height, "fps": 30, "segments": [{"src": "cut.mp4", "start": 0, "end": 8}],
            "captions": list(captions)}


def _caption(text, **extra):
    return {"from": 1, "to": 2, "text": text, "style": "caption", "place": "bottom", "fontSize": 68, "offsetY": 0,
            "width": 790, "look": "outline", **extra}


def _inside(box, width=1080, height=1920, k=1.0):
    x, y, w, h = box
    return (x >= SAFE["left"] * k - 1 and x + w <= width - SAFE["right"] * k + 1 and y >= SAFE["top"] * k - 1
            and y + h <= height - SAFE["bottom"] * k + 1)


# --- the boxes ------------------------------------------------------------------------------------

def test_a_captions_box_sits_on_the_safe_zones_bottom_and_grows_with_its_text():
    short, long = create_text.text_boxes(_props(_caption("I check"),
                                                _caption("I check what is rising every single morning")))
    assert short["kind"] == long["kind"] == "caption" and (short["start"], short["end"]) == (1, 2)
    for layer in (short, long):
        x, y, w, h = layer["box"]
        assert _inside(layer["box"]) and abs(y + h - (1920 - 380)) < 1           # on the bottom of the safe zone
    assert long["box"][2] > short["box"][2] and long["box"][3] > short["box"][3]  # wider, then a second line
    up = create_text.text_boxes(_props(_caption("I check", offsetY=-200)))[0]
    assert abs(up["box"][1] - (short["box"][1] - 200)) < 1


def test_overlay_boxes_by_kind_and_the_end_card_fills_the_frame():
    hook = {"from": 0, "to": 8, "text": "How I find ideas", "style": "hook", "place": "top", "offsetY": 0,
            "width": 680, "color": "#111111", "background": "#FFFFFF",
            "overlay": {"kind": "hook", "family": "pill", "accent": "#FFD84D"}}
    number = {**hook, "from": 2, "to": 4, "text": "+212%", "place": "middle",
              "overlay": {"kind": "number", "family": "pill", "sub": "this week"}}
    end = {**hook, "from": 7, "to": 8, "text": "Today's trends", "overlay": {"kind": "end", "family": "pill"}}
    boxes = create_text.text_boxes(_props(hook, number, end))
    assert [b["kind"] for b in boxes] == ["overlay"] * 3
    assert _inside(boxes[0]["box"]) and abs(boxes[0]["box"][1] - 260) < 1
    assert _inside(boxes[1]["box"]) and boxes[1]["box"][3] > 150                   # the figure and its sub line
    assert boxes[2]["box"] == [0, 0, 1080, 1920] and layer_check.fills(tuple(boxes[2]["box"]), (1080, 1920))
    assert not layer_check.overlap(tuple(boxes[0]["box"]), tuple(boxes[1]["box"]))


def test_the_boxes_scale_with_a_feed_frame():
    box = create_text.text_boxes(_props(_caption("I check what is rising"), width=1080, height=1350))[0]["box"]
    assert _inside(box, 1080, 1350) and abs(box[1] + box[3] - (1350 - 380)) < 1
    small = create_text.text_boxes(_props(_caption("I check what is rising"), width=720, height=1280))[0]["box"]
    assert _inside(small, 720, 1280, k=720 / 1080)


# --- tm ad text -----------------------------------------------------------------------------------

@pytest.fixture
def ad(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    run = RunFolder.create(ws, "ad", date(2026, 11, 17), playbook=CREATE_AD)
    cfg = create_config.defaults()
    cfg["brand"]["product"] = "Pet Store"
    config.save(run, cfg)
    wip = run.path / "03_wip"
    (wip / "edit_cut_v01.mp4").write_bytes(b"the cut")
    (wip / "edit_cut_v01.words.json").write_text(json.dumps({"segments": [{"words": [
        {"word": "Cats", "start": 0.2, "end": 0.5}, {"word": "drink", "start": 0.55, "end": 0.8},
        {"word": "too", "start": 0.85, "end": 1.0}, {"word": "little.", "start": 1.05, "end": 1.5, "key": True},
        {"word": "This", "start": 2.0, "end": 2.2}, {"word": "helps.", "start": 2.25, "end": 2.7}]}]}),
        encoding="utf-8")
    (wip / "edit_text_v01.json").write_text(json.dumps({"overlays": [
        {"from": 0, "to": 3, "text": "Your cat drinks *too little*", "overlay": {"kind": "hook", "hold": True}},
        {"from": 3, "to": 5, "text": "+40%", "overlay": {"kind": "number", "sub": "more water a day"}},
        {"from": 6.5, "to": 8, "text": "Calm, healthy pets", "overlay": {"kind": "end", "brand": "Pet Store",
                                                                         "sub": "Shop now"}}]}), encoding="utf-8")
    (wip / "edit_pictures_v01.json").write_text(json.dumps({"layers": [
        {"id": "take", "kind": "picture", "start": 0, "end": 8, "src": "03_wip/edit_cut_v01.mp4"}]}),
        encoding="utf-8")
    monkeypatch.setattr(create_text.c, "probe", lambda path: {"has_video": True, "has_audio": True, "width": 1080,
                                                              "height": 1920, "fps": 30.0, "duration": 8.0})
    return run


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


TEXT = ("ad", "text", "--cut", "03_wip/edit_cut_v01.mp4", "--words", "03_wip/edit_cut_v01.words.json",
        "--overlays", "03_wip/edit_text_v01.json", "--pictures", "03_wip/edit_pictures_v01.json")


def test_the_text_is_drawn_over_the_cut_in_the_brands_set_and_the_layers_come_from_the_props(ad, remotion,
                                                                                               capsys):
    font = ad.path / "02_research" / "brand" / "Pet-Bold.otf"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"OTTO font")
    (ad.path / "02_research" / "brand" / "logo.png").write_bytes(b"\x89PNG logo")
    text_sets.save(ad.path.parents[2], "brand", "Pet Store", look="pill", accent="#2E7D32", font=font,
                   logo=ad.path / "02_research" / "brand" / "logo.png", run=ad, note="the green pill")
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:])
    assert code == 0, out
    assert (out["props"], out["mix"], out["layers"]) == ("03_wip/edit_mix_v01.props.json", "03_wip/edit_mix_v01.mp4",
                                                         "03_wip/edit_layers_v01.json")
    assert out["look"] == "pill" and out["text_set"] == "library/brands/pet-store/text_style_v01.json"
    props = json.loads((ad.path / out["props"]).read_text(encoding="utf-8"))
    assert props["segments"] == [{"src": "03_wip/edit_cut_v01.mp4", "start": 0, "end": 8.0}]
    assert props["keepAudio"] is True and (props["width"], props["height"], props["fps"]) == (1080, 1920, 30)
    assert props["brandFont"] == {"family": "Pet-Bold", "src": "03_wip/text_set/pet-bold_v01.otf"}
    caps = [x for x in props["captions"] if x["style"] == "caption"]
    tops = [x for x in props["captions"] if x["style"] != "caption"]
    assert [x["text"] for x in caps] == ["Cats drink too", "little.", "This helps."]   # pill: 1 to 3 words
    assert caps[0]["look"] == "pill" and caps[0]["ink"] == "#FFFFFF" and caps[1]["words"][0]["key"] is True
    assert tops[0]["to"] == 8.0 and tops[1]["place"] == "middle"                  # the held hook, the number off it
    assert tops[2]["overlay"]["logo"] == "03_wip/text_set/logo_v01.png"
    assert (ad.path / out["mix"]).is_file()
    row = [r for r in manifest.rows(ad) if r["file"] == out["mix"]][0]
    assert row["model"] == "remotion render" and json.loads(row["params"])["composition"] == "OrganicCaptions"
    layers = json.loads((ad.path / out["layers"]).read_text(encoding="utf-8"))["layers"]
    assert layers[0]["id"] == "take" and [x["kind"] for x in layers[1:]] == ["overlay"] * 3 + ["caption"] * 3
    assert [(x["start"], x["end"]) for x in layers[1:]] == [(x["from"], x["to"]) for x in props["captions"]]
    assert len({x["id"] for x in layers}) == len(layers)
    assert layer_check.read_layers(ad, ad.path / out["layers"], (1080, 1920))            # the S7 check reads it
    assert json.loads(row["params"])["props"]["captions"] == props["captions"]


def test_without_a_saved_set_the_default_is_drawn_and_one_ad_can_use_another_set(ad, remotion, capsys):
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:])
    assert code == 0, out
    assert out["look"] == "outline" and out["text_set"] is None
    end = [x for x in json.loads((ad.path / out["props"]).read_text(encoding="utf-8"))["captions"]
           if x.get("overlay", {}).get("kind") == "end"][0]
    assert "logo" not in end["overlay"] and end["overlay"]["brand"] == "Pet Store"   # the name, no logo
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:], "--look", "native")
    assert code == 0 and out["look"] == "native" and out["props"] == "03_wip/edit_mix_v02.props.json"
    assert out["layers"] == "03_wip/edit_layers_v02.json"        # the edit's NN, never an earlier file overwritten


def test_an_overlays_file_without_overlays_or_with_a_bad_kind_is_refused(ad, remotion, capsys):
    (ad.path / "03_wip" / "edit_text_v01.json").write_text(json.dumps({"overlays": [{"text": "x"}]}),
                                                          encoding="utf-8")
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:])
    assert code == 2 and "from" in out["message"]
    assert not (ad.path / "03_wip" / "edit_mix_v01.mp4").exists()


def test_a_render_that_cannot_start_is_a_stop_with_its_todo_not_a_crash(ad, monkeypatch, capsys):
    from tm import render

    def missing(*a, **k):
        raise create_text.c.ToolStop("Rendering needs the 'video' tools. Install them with: tm env install video")

    monkeypatch.setattr(render, "video", missing)
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:])
    assert code == 2 and out["status"] == "stop" and "tm env install video" in out["message"]

    def broken(*a, **k):
        raise create_text.c.ToolError("remotion render failed: a page error")

    monkeypatch.setattr(render, "video", broken)
    code, out = _cli(capsys, *TEXT[:2], "--run", str(ad.path), *TEXT[2:])
    assert code == 1 and "remotion render failed" in out["message"]


def _sfnt(avg: int, upm: int = 1000, woff: bool = False) -> bytes:
    """A minimal font file: the OS/2 table's xAvgCharWidth and head's unitsPerEm, nothing else."""
    import struct
    import zlib

    os2 = struct.pack(">Hh", 4, avg) + bytes(94)
    head = bytes(18) + struct.pack(">H", upm) + bytes(34)
    tables = [(b"OS/2", os2), (b"head", head)]
    if not woff:
        out = struct.pack(">IHHHH", 0x00010000, len(tables), 0, 0, 0)
        offset = 12 + 16 * len(tables)
        body = b""
        for tag, data in tables:
            out += tag + struct.pack(">III", 0, offset + len(body), len(data))
            body += data
        return out + body
    out = b"wOFF" + struct.pack(">IIHH", 0x00010000, 0, len(tables), 0) + bytes(28)   # a 44-byte header
    offset = 44 + 20 * len(tables)
    body = b""
    for tag, data in tables:
        packed = zlib.compress(data)
        out += tag + struct.pack(">IIII", offset + len(body), len(packed), len(data), 0)
        body += packed
    return out + body


def test_a_brand_fonts_own_letter_width_widens_the_boxes(tmp_path):
    wide = tmp_path / "wide.ttf"
    wide.write_bytes(_sfnt(780))
    packed = tmp_path / "wide.woff"
    packed.write_bytes(_sfnt(780, woff=True))
    unreadable = tmp_path / "x.woff2"
    unreadable.write_bytes(b"wOF2 brotli")
    assert create_text.font_letter(wide) == pytest.approx(0.78)
    assert create_text.font_letter(packed) == pytest.approx(0.78)
    assert create_text.font_letter(unreadable) is None
    narrow = create_text.text_boxes(_props(_caption("I check")))[0]["box"]
    props = {**_props(_caption("I check")), "brandFont": {"family": "Wide", "src": "wide.ttf"}}
    broad = create_text.text_boxes(props, letter=create_text.letter_of(tmp_path / "wide.ttf"))[0]["box"]
    assert broad[2] > narrow[2] * 1.3
    guessed = create_text.letter_of(tmp_path / "x.woff2")
    assert guessed == create_text.UNKNOWN_LETTER > create_text.LETTER


def test_a_text_on_two_lines_has_a_box_as_wide_as_its_room():
    hook = {"from": 0, "to": 8, "text": "Your cat drinks too little every single day", "style": "hook",
            "place": "top", "offsetY": 0, "width": 680, "overlay": {"kind": "hook", "family": "pill"}}
    box = create_text.text_boxes(_props(hook))[0]["box"]
    assert (box[0], box[2]) == (90, 790)                      # a wrapped box widens to the safe zone (CSS)
    caption = create_text.text_boxes(_props(_caption("I check what is rising every single morning",
                                                     look="block")))[0]["box"]
    assert (caption[0], caption[2]) == (90, 790)              # to its column
