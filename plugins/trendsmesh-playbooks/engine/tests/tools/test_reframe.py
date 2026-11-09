"""reframe.to_4x5: crop 9:16 to 4:5 at an offset that keeps every overlay inside, else pad."""

import json

from _media import gray_frame, make_clip
from tm.tools import reframe

# An opaque white box near the bottom of a 540x960 clip. 4:5 of 540 is 675 rows, made even (yuv420p): 674.
LOW_BOX = [150, 820, 390, 900]
LOW_DRAW = "drawbox=x=150:y=820:w=240:h=80:color=white:t=fill"


def _ov(bbox):
    return {"start_frame": 0, "end_frame": 74, "bbox": bbox, "touches_edge": False,
            "semi_transparent": False}


def test_reframe_keeps_overlay_inside(tmp_path):
    video = make_clip(tmp_path / "low box.mp4", vf=LOW_DRAW)
    out = tmp_path / "out 4x5.mp4"
    res = reframe.to_4x5(video, [_ov(LOW_BOX)], out)
    assert res["method"] == "crop"
    assert res["size"] == [540, 674]
    y = res["offset_y"]
    assert y <= LOW_BOX[1] - reframe.MARGIN and y + 674 >= LOW_BOX[3] + reframe.MARGIN
    assert y == 250  # the closest fit to the centre (900 + 24 - 674), offsets even for yuv420p
    w, h, raw = gray_frame(out, 10)
    assert (w, h) == (540, 674)
    inside = raw[(LOW_BOX[1] - y + 40) * w + 270]  # middle of the box, in the cropped frame
    assert inside > 230


def test_centre_crop_when_overlays_allow(tmp_path):
    video = make_clip(tmp_path / "plain.mp4", vf="null")
    res = reframe.to_4x5(video, [], tmp_path / "c.mp4")
    assert res["method"] == "crop" and res["offset_y"] == 142  # (960 - 674) / 2 = 143, made even


def test_pads_when_no_offset_fits(tmp_path):
    video = make_clip(tmp_path / "two.mp4", vf="null")
    res = reframe.to_4x5(video, [_ov([0, 30, 300, 120]), _ov([0, 840, 300, 930])], tmp_path / "p.mp4")
    assert res["method"] == "pad"
    assert res["size"] == [540, 674]
    w, h, raw = gray_frame(tmp_path / "p.mp4", 10)
    assert (w, h) == (540, 674)
    assert raw[300 * w + 2] < 20  # the side bar is black: the whole 9:16 frame is kept


def test_cli_reads_teardown_and_records(run, tmp_path):
    video = make_clip(tmp_path / "low box.mp4", vf=LOW_DRAW)
    td = tmp_path / "teardown.json"
    td.write_text(json.dumps({"width": 540, "height": 960, "overlays": [_ov(LOW_BOX)]}))
    assert reframe.main(["--run", str(run.path), str(video), "--teardown", str(td), "--json"]) == 0
    out = run.path / "03_wip" / "low-box_4x5_v01.mp4"
    assert out.is_file()
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "03_wip/low-box_4x5_v01.mp4" in manifest and '"method": "crop"' in manifest
    # never overwrite: a second run makes _v02
    assert reframe.main(["--run", str(run.path), str(video), "--teardown", str(td)]) == 0
    assert (run.path / "03_wip" / "low-box_4x5_v02.mp4").is_file()


def test_cli_refuses_teardown_of_another_size(run, tmp_path, capsys):
    video = make_clip(tmp_path / "v.mp4", vf="null")
    td = tmp_path / "teardown.json"
    td.write_text(json.dumps({"width": 1080, "height": 1920, "overlays": []}))
    assert reframe.main(["--run", str(run.path), str(video), "--teardown", str(td)]) == 1
    assert "1080x1920" in capsys.readouterr().out
