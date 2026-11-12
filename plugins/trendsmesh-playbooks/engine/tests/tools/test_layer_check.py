"""tm tool layer_check (issue 96): Create an ad's edit check finds a caption or an overlay over a face (a caption over
the mouth in a close-up, a code chip over the chin), two layers over each other (a tag under the caption band) and a
capture scaled up, from the layers file the edit was drawn from. The face detector is cover_fit's; here it is a
stand-in that finds one face in the take, so the test needs no photo of a person."""

from __future__ import annotations

import json
import subprocess
from datetime import date

import pytest
from _media import ffmpeg, make_clip

from tm import config, create_config, manifest
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder
from tm.tools import _common as c
from tm.tools import layer_check

W, H = 540, 960
FACE = (170, 300, 200, 220)      # x, y, w, h in the take (540×960): its head is x 140-400, y 190-520


@pytest.fixture
def ad(tmp_path):
    run = RunFolder.create(tmp_path / "Pulpit Łukasz Nowak", "rising ad", date(2026, 11, 12), playbook=CREATE_AD)
    config.save(run, create_config.defaults())
    make_clip(run.path / "03_wip" / "presenter-take_v01_0.mp4", vf="null", seconds=4.0)
    make_clip(run.path / "03_wip" / "edit_v01.mp4", vf="null", seconds=4.0)
    return run


@pytest.fixture
def one_face(monkeypatch):
    seen = []

    def faces(png):
        seen.append(png)
        return [] if "site_" in str(png) else [FACE]

    monkeypatch.setattr(layer_check.cover_fit, "faces", faces)
    return seen


def _layers(run, layers, version=1):
    path = run.path / "03_wip" / f"edit_layers_v{version:02d}.json"
    path.write_text(json.dumps({"layers": layers}), encoding="utf-8")
    return f"03_wip/edit_layers_v{version:02d}.json"


def _check(capsys, run, layers):
    code = layer_check.main(["--run", str(run.path), "03_wip/edit_v01.mp4", "--layers", layers, "--json"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out


TAKE = {"id": "creator", "kind": "picture", "src": "03_wip/presenter-take_v01_0.mp4", "start": 0, "end": 4}


@pytest.mark.tools
def test_a_caption_over_the_mouth_is_found_and_a_moved_one_passes(ad, one_face, capsys):
    over = {"id": "caption 1", "kind": "caption", "start": 0.5, "end": 2.0, "box": [90, 440, 360, 70]}
    code, out = _check(capsys, ad, _layers(ad, [TAKE, over]))
    assert code == 0 and [x["kind"] for x in out["collisions"]] == ["face"]
    hit = out["collisions"][0]
    assert (hit["layer"], hit["with"]) == ("caption 1", "creator") and "face" in hit["message"]
    saved = json.loads((ad.path / out["outputs"][0]).read_text(encoding="utf-8"))
    assert out["outputs"] == ["03_wip/qa/edit_v01_layers_v01.json"] and saved["edit"] == "03_wip/edit_v01.mp4"
    assert saved["layers"]["file"] == "03_wip/edit_layers_v01.json" and saved["collisions"] == out["collisions"]
    assert [r for r in manifest.rows(ad) if r["file"] == out["outputs"][0]][0]["source"] == "tm tool layer_check"
    moved = {**over, "box": [90, 700, 360, 70]}
    code, out = _check(capsys, ad, _layers(ad, [TAKE, moved], 2))
    assert code == 0 and out["collisions"] == [] and out["outputs"] == ["03_wip/qa/edit_v01_layers_v02.json"]
    assert layer_check.latest(ad, ad.path / "03_wip" / "edit_v01.mp4").name == "edit_v01_layers_v02.json"


@pytest.mark.tools
def test_a_tag_under_the_caption_band_is_found_unless_it_is_on_it_on_purpose(ad, one_face, capsys):
    band = {"id": "captions", "kind": "caption", "start": 0, "end": 4, "box": [60, 720, 420, 90]}
    tag = {"id": "early access", "kind": "overlay", "start": 1, "end": 3, "box": [300, 760, 160, 40]}
    code, out = _check(capsys, ad, _layers(ad, [TAKE, band, tag]))
    assert [(x["kind"], x["layer"], x["with"], x["at"]) for x in out["collisions"]] == [
        ("layer", "early access", "captions", 1.0)]
    code, out = _check(capsys, ad, _layers(ad, [TAKE, band, {**tag, "on": "captions"}], 2))
    assert out["collisions"] == []
    code, out = _check(capsys, ad, _layers(ad, [TAKE, {**band, "end": 1.0}, tag], 3))
    assert out["collisions"] == []    # one after the other, never together


@pytest.mark.tools
def test_a_window_carries_its_face_and_never_meets_the_captions(ad, one_face, capsys):
    """The creator in a corner window (the take scaled to half, cropped to its top half) over a site capture."""
    site = ad.path / "03_wip" / "site_home_v01.png"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={W}x{H}",
                    "-frames:v", "1", str(site)], check=True)
    back = {"id": "site", "kind": "picture", "src": "03_wip/site_home_v01.png", "start": 0, "end": 4}
    window = {**TAKE, "id": "window", "box": [270, 0, 270, 240], "crop": [0, 0, 540, 480]}
    chip = {"id": "code chip", "kind": "overlay", "start": 2, "end": 4, "box": [330, 220, 150, 50]}   # the chin
    caption = {"id": "caption", "kind": "caption", "start": 0, "end": 4, "box": [60, 720, 420, 90]}
    code, out = _check(capsys, ad, _layers(ad, [back, window, chip, caption]))
    found = {(x["kind"], x["layer"], x["with"]) for x in out["collisions"]}
    assert found == {("face", "code chip", "window"), ("layer", "code chip", "window")}
    # the face is placed through the crop and the box: half size, at the window's corner
    saved = json.loads((ad.path / out["outputs"][0]).read_text(encoding="utf-8"))
    assert {tuple(f["head"]) for f in saved["faces"] if f["layer"] == "window"} == {(340, 95, 470, 240)}
    clear = {**chip, "box": [330, 300, 150, 50]}
    code, out = _check(capsys, ad, _layers(ad, [back, window, clear, caption], 2))
    assert out["collisions"] == []


@pytest.mark.tools
def test_a_capture_drawn_larger_than_its_pixels_is_found(ad, monkeypatch, capsys):
    monkeypatch.setattr(layer_check.cover_fit, "faces", lambda png: [])
    small = ad.path / "03_wip" / "site_card_v01.png"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=240x240",
                    "-frames:v", "1", str(small)], check=True)
    card = {"id": "rising card", "kind": "picture", "src": "03_wip/site_card_v01.png", "start": 0, "end": 4,
            "box": [0, 240, 540, 540]}
    code, out = _check(capsys, ad, _layers(ad, [TAKE, card]))
    assert [x["kind"] for x in out["collisions"]] == ["scaled_up"] and "sharper" in out["collisions"][0]["message"]
    code, out = _check(capsys, ad, _layers(ad, [TAKE, {**card, "box": [150, 360, 240, 240]}], 2))
    assert out["collisions"] == []


@pytest.mark.tools
def test_a_layers_file_that_does_not_say_enough_is_refused(ad, one_face, capsys):
    for layers, fragment in [
        ([], "layers"),
        ([{"kind": "caption", "start": 0, "end": 1, "box": [0, 0, 10, 10]}], "id"),
        ([{"id": "a", "kind": "sticker", "start": 0, "end": 1}], "kind"),
        ([{"id": "a", "kind": "caption", "start": 2, "end": 1, "box": [0, 0, 10, 10]}], "end"),
        ([{"id": "a", "kind": "caption", "start": 0, "end": 1}], "box"),
        ([{"id": "a", "kind": "picture", "start": 0, "end": 1}], "src"),
        ([{"id": "a", "kind": "picture", "start": 0, "end": 1, "src": "03_wip/none.mp4"}], "does not exist"),
        ([TAKE, TAKE], "twice"),
    ]:
        code, out = _check(capsys, ad, _layers(ad, layers))
        assert code == 1 and fragment in out["message"], (layers, out)
    assert not (ad.path / "03_wip" / "qa").exists()


def test_a_head_is_placed_through_the_crop_and_the_box():
    head = (140, 190, 400, 520)
    assert layer_check.place(head, (540, 960), None, (0, 0, 540, 960)) == head
    assert layer_check.place(head, (540, 960), (0, 0, 540, 480), (270, 0, 270, 240)) == (340, 95, 470, 240)
    assert layer_check.place(head, (540, 960), (0, 600, 540, 360), (0, 0, 540, 360)) is None
    assert layer_check.times(0, 4) == [0.05, 1.05, 2.0, 2.05, 3.05, 3.95]
    assert len(layer_check.times(0, 60)) == layer_check.SAMPLES
