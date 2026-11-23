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


def test_a_head_covering_70_percent_of_the_frame_or_more_is_not_a_face():
    """Issue #139: a detection whose head box (`head`, inside the frame) covers 70 % or more of it is dropped."""
    assert cover_fit.not_a_face((0, 200, 1000, 1300), (1080, 1920))        # 1080 × 1500 of 1080 × 1920: 78 %
    assert not cover_fit.not_a_face((300, 400, 480, 560), (1080, 1920))
    assert cover_fit.NOT_A_FACE == "covers almost the whole frame: not a face"


@pytest.mark.tools
def test_a_cover_in_the_approved_style_is_written_in_its_family_and_says_so(ov, drawn, monkeypatch, capsys):
    from tm import organic_edit

    style = organic_edit.default_style(caption="", overlay="", look="outline", accent="#FFD84D")
    monkeypatch.setattr(cover_fit.organic_edit, "approved_style", lambda run: ("03_wip/text_style_v01.json", "x",
                                                                                style))
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    _cover_props(ov, text="One *habit*")
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0 and out["props"] == "03_wip/cover_M5_v02.props.json"
    cap = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert cap["overlay"]["family"] == "outline" and cap["overlay"]["accent"] == "#FFD84D"
    assert any("approved text style" in ch for ch in out["changes"])
    assert out["rejected_faces"] == []


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


PICTURE = {"vf": None}     # the picture under the text in `_draw`: None is plain grey (0x606060)


def _draw(run, data, frame, dest):
    """A stand-in for the Remotion still: grey (or PICTURE's), and each caption a block at the top of the safe zone
    moved by its offsetY, three lines of its fontSize (or its overlay's size) tall: white with a black outline, in its
    overlay's `fill` or its `color` (the outline the opposite), on a dark box with `backing`."""
    boxes = []
    for cap in data.get("captions") or []:
        ov = cap.get("overlay") or {}
        y = 260 + int(cap.get("offsetY", 0))
        h = int(ov.get("size") or cap.get("fontSize", 58)) * 3
        ink = (ov.get("fill") or cap.get("color") or "#FFFFFF").replace("#", "0x")
        edge = "white" if ink.upper() == "0X111111" else "black"
        if ov.get("backing") or cap.get("backing"):
            boxes.append(f"drawbox=x=180:y={y - 20}:w=720:h={h + 40}:color=0x1a1a1a:t=fill")
        boxes.append(f"drawbox=x=200:y={y}:w=680:h={h}:color={edge}:t=fill")
        boxes.append(f"drawbox=x=206:y={y + 6}:w=668:h={h - 12}:color={ink}:t=fill")
    vf = ",".join(([PICTURE["vf"]] if PICTURE["vf"] else []) + boxes) or "null"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x606060:s=1080x1920",
                    "-vf", vf, "-frames:v", "1", str(dest)], check=True)
    return dest


def _cover_props(run, *, top: dict | None = None, **caption):
    props = {"width": 1080, "height": 1920, "fps": 24, **(top or {}),
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
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [FACE])
    _cover_props(ov)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0, out
    assert out["outputs"] == ["04_final/kits/cover_M5_v01.png"] and out["props"] == "03_wip/cover_M5_v02.props.json"
    assert out["changes"][0] == cover_fit.STATIC_SAID and "moved" in out["changes"][1]
    fitted = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    x0, y0, x1, y1 = cover_fit.head(FACE)
    top = 260 + fitted["offsetY"]
    assert top >= y1 or top + fitted["fontSize"] * 3 <= y0           # clear of the head
    assert drawn[-1]["captions"][0]["offsetY"] == fitted["offsetY"]  # the final is drawn from the fitted props
    assert top + fitted["fontSize"] * 3 <= 1680                      # inside the 3:4 crop


@pytest.mark.tools
def test_a_text_that_fits_nowhere_is_shrunk(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [(300, 520, 480, 900)])   # the head is most of the frame
    _cover_props(ov, fontSize=110)
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0, out
    fitted = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert fitted["fontSize"] < 110 and any("smaller" in ch for ch in out["changes"])


@pytest.mark.tools
def test_a_clear_cover_is_drawn_as_it_is(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [(380, 1100, 320, 300)])
    _cover_props(ov, top={"static": True})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6")
    assert code == 0 and out["changes"] == [] and out["props"] == "03_wip/cover_M5_v01.props.json"
    assert not (ov.path / "03_wip" / "cover_M5_v02.props.json").exists()


# --- issue #165: the cover in its final state, and readable -------------------------------------------------

@pytest.fixture(autouse=True)
def grey_picture():
    PICTURE["vf"] = None
    yield
    PICTURE["vf"] = None


WHITE = "drawbox=x=0:y=0:w=1080:h=1920:color=white:t=fill"
STRIPES = "geq=r='if(lt(mod(X\\,40)\\,20)\\,255\\,0)':g='if(lt(mod(X\\,40)\\,20)\\,255\\,0)':b='if(lt(mod(X\\,40)\\,20)\\,255\\,0)'"


def test_the_contrast_ratio_is_wcags():
    assert cover_fit.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21)
    assert cover_fit.contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1)
    assert cover_fit.contrast_ratio("#FFFFFF", "#767676") == pytest.approx(4.54, abs=0.01)


def test_only_text_without_a_box_of_its_own_is_checked():
    assert cover_fit.ink_of({"style": "hook", "overlay": {"kind": "hook", "family": "outline"}}) == "#FFFFFF"
    assert cover_fit.ink_of({"style": "hook", "overlay": {"kind": "hook", "family": "outline", "fill": "#111111"}}) \
        == "#111111"
    for boxed in ({"style": "hook", "overlay": {"kind": "hook", "family": "pill"}},
                  {"style": "hook", "overlay": {"kind": "hook", "family": "outline", "backing": True}},
                  {"style": "hook", "overlay": {"kind": "label", "family": "marker"}},
                  {"style": "hook", "overlay": {"kind": "number", "family": "outline"}},
                  {"style": "hook", "text": "a plain hook in its box"},
                  {"style": "caption", "look": "block"}):
        assert cover_fit.ink_of(boxed) is None, boxed
    assert cover_fit.ink_of({"style": "caption", "look": "outline", "color": "#000000"}) == "#FFFFFF"
    assert cover_fit.ink_of({"style": "note", "color": "#222222"}) == "#222222"


@pytest.mark.tools
def test_a_cover_is_drawn_static_and_measured_without_a_face(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    _cover_props(ov, overlay={"kind": "hook", "family": "outline"})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    props = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))
    assert props["static"] is True and drawn[-1]["static"] is True                 # the final still too
    assert out["changes"] == [cover_fit.STATIC_SAID] and "final state" in out["message"]
    assert out["contrast"]["fix"] is None and out["contrast"]["ratio"] > 4.5     # white on grey 0x606060
    assert "reads on the picture" in out["message"]


@pytest.mark.tools
def test_white_text_on_a_light_picture_turns_dark(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    PICTURE["vf"] = WHITE
    _cover_props(ov, top={"static": True}, overlay={"kind": "hook", "family": "outline"})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    assert out["contrast"]["fix"] == "dark ink" and out["contrast"]["ratio"] == 1
    cap = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert cap["overlay"]["fill"] == "#111111" and "backing" not in cap["overlay"]
    assert "its words are dark now" in out["message"]


@pytest.mark.tools
def test_a_plain_caption_turns_dark_with_a_white_outline(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    PICTURE["vf"] = WHITE
    _cover_props(ov, top={"static": True}, style="note")
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    cap = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert (cap["color"], cap["stroke"]) == ("#111111", "#FFFFFF")


@pytest.mark.tools
def test_a_picture_neither_ink_reads_on_gets_a_backing(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    PICTURE["vf"] = STRIPES                                   # black and white stripes: neither ink passes
    _cover_props(ov, top={"static": True}, overlay={"kind": "hook", "family": "outline"})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    assert out["contrast"]["fix"] == "backing"
    cap = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert cap["overlay"]["backing"] is True and "fill" not in cap["overlay"]
    assert "a dark box is behind it now" in out["message"]


@pytest.mark.tools
def test_a_caption_drawn_in_a_set_gets_a_backing_never_another_ink(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    PICTURE["vf"] = WHITE
    _cover_props(ov, top={"static": True}, style="caption", look="outline")
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    cap = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert cap["backing"] is True and "color" not in cap


@pytest.mark.tools
def test_a_boxed_set_on_a_light_picture_is_left_as_it_is(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
    PICTURE["vf"] = WHITE
    _cover_props(ov, top={"static": True}, overlay={"kind": "hook", "family": "pill"})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0 and out["changes"] == [] and out["contrast"]["ink"] is None
    assert "its own box" in out["message"]


@pytest.mark.tools
def test_the_contrast_is_checked_where_the_text_lands_after_it_clears_the_face(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [FACE])
    PICTURE["vf"] = "drawbox=x=0:y=680:w=1080:h=1240:color=white:t=fill"   # light only below the face
    _cover_props(ov, top={"static": True}, overlay={"kind": "hook", "family": "outline", "size": 72})
    code, out = _tool(capsys, "--run", str(ov.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "0")
    assert code == 0, out
    assert any("moved" in ch for ch in out["changes"]) and out["contrast"]["fix"] == "dark ink"


@pytest.mark.tools
def test_no_face_found_says_so_and_a_face_can_be_given(ov, drawn, monkeypatch, capsys):
    monkeypatch.setattr(cover_fit, "faces", lambda png, rejected=None: [])
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

