"""tm tool cover_fit (issue 89): the cover's text is moved or shrunk until a face in the frame is clear. Remotion and
the face detector are replaced here by drawn pictures: the plain frame is grey, the text a white block whose place and
height follow its offsetY and fontSize, so the loop and the measuring are the tool's own."""

from __future__ import annotations

import json
import subprocess

import pytest
from _media import ffmpeg

from tm import config, organic_config, state
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import cover_fit

FACE = (380, 300, 320, 360)     # x, y, w, h: a face high in the frame


def test_the_text_moves_to_the_nearer_clear_side_inside_the_bounds():
    # text at y 300-420 over a face at 300-660 (the head's box): above it there is no room (260), so below it
    assert cover_fit.clear_shift((200, 300, 880, 420), [(380, 300, 700, 660)], top=260, bottom=1540,
                                 margin=20) == 380
    # a face low in the frame, the text over its top: up is nearer
    assert cover_fit.clear_shift((200, 900, 880, 1000), [(380, 950, 700, 1300)], top=260, bottom=1540,
                                 margin=20) == -70
    assert cover_fit.clear_shift((200, 300, 880, 420), [(380, 700, 700, 900)], top=260, bottom=1540,
                                 margin=20) == 0                       # clear already
    assert cover_fit.clear_shift((200, 300, 880, 1500), [(380, 200, 700, 1600)], top=260, bottom=1540,
                                 margin=20) is None                    # no room on either side: shrink it


def test_the_head_above_the_detected_face_counts():
    assert cover_fit.head((100, 400, 200, 200)) == (70, 300, 330, 600)


@pytest.fixture
def ov(tmp_path):
    run = RunFolder.create(tmp_path / "ws" / "runs" / "03" / "x", "m5", date_(), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.organic = {"proposal": "M5", "channel": "exampleedu"}
    state.save(run, s)
    config.save(run, organic_config.defaults())
    return run


def date_():
    from datetime import date

    return date(2026, 11, 12)


def _draw(run, data, frame, dest):
    """A stand-in for the Remotion still: grey, and each caption a white block at the top of the safe zone moved by
    its offsetY, three lines of its fontSize tall."""
    boxes = []
    for cap in data.get("captions") or []:
        y = 260 + int(cap.get("offsetY", 0))
        boxes.append(f"drawbox=x=200:y={y}:w=680:h={int(cap.get('fontSize', 58)) * 3}:color=white:t=fill")
    vf = ",".join(boxes) or "null"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x606060:s=1080x1920",
                    "-vf", vf, "-frames:v", "1", str(dest)], check=True)
    return dest


def _cover_props(run, **caption):
    props = {"width": 1080, "height": 1920, "fps": 24,
             "segments": [{"src": "03_wip/frame.png", "start": 0, "end": 2}],
             "captions": [{"from": 0, "to": 2, "text": "Jeden nawyk", "style": "hook", "place": "top",
                           "fontSize": 72, **caption}]}
    (run.path / "03_wip" / "frame.png").write_bytes(b"\x89PNG")
    path = run.path / "03_wip" / "cover_M5_v01.props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    return path


@pytest.fixture
def drawn(monkeypatch):
    pytest.importorskip("numpy")
    monkeypatch.setattr(cover_fit, "_draft", _draw)
    made = []

    def final(run, comp, props, frame, out):
        data = json.loads(props.read_text(encoding="utf-8"))
        made.append(data)
        return _draw(run, data, frame, out)

    monkeypatch.setattr(cover_fit.render, "still", final)
    return made


def _tool(capsys, *argv):
    code = cover_fit.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


@pytest.mark.tools
def test_the_cover_text_is_moved_off_the_face(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png: [FACE])
    _cover_props(ov)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0, out
    assert out["outputs"] == ["04_final/kits/cover_M5_v01.png"] and out["props"] == "03_wip/cover_M5_v02.props.json"
    assert out["changes"] and "moved" in out["changes"][0]
    fitted = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    x0, y0, x1, y1 = cover_fit.head(FACE)
    top = 260 + fitted["offsetY"]
    assert top >= y1 or top + fitted["fontSize"] * 3 <= y0           # clear of the head
    assert drawn[-1]["captions"][0]["offsetY"] == fitted["offsetY"]  # the final is drawn from the fitted props
    assert top + fitted["fontSize"] * 3 <= 1680                      # inside the 3:4 crop


@pytest.mark.tools
def test_a_text_that_fits_nowhere_is_shrunk(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png: [(300, 520, 480, 900)])   # the head is most of the frame
    _cover_props(ov, fontSize=110)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0, out
    fitted = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert fitted["fontSize"] < 110 and any("smaller" in ch for ch in out["changes"])


@pytest.mark.tools
def test_a_clear_cover_is_drawn_as_it_is(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png: [(380, 1100, 320, 300)])
    _cover_props(ov)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0 and out["changes"] == [] and out["props"] == "03_wip/cover_M5_v01.props.json"
    assert not (ov.path / "03_wip" / "cover_M5_v02.props.json").exists()


@pytest.mark.tools
def test_no_face_found_says_so_and_a_face_can_be_given(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png: [])
    _cover_props(ov)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0 and out["faces"] == [] and "--face" in out["message"]
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6",
                      "--face", "380,300,320,360")
    assert code == 0 and out["faces"] == [list(FACE)] and out["changes"]


@pytest.mark.tools
def test_the_detector_finds_no_face_on_a_plain_picture(tmp_path):
    pytest.importorskip("cv2")
    png = tmp_path / "grey.png"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=0x606060:s=1080x1920",
                    "-frames:v", "1", str(png)], check=True)
    assert cover_fit.faces(png) == []

