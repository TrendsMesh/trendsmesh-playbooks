"""The teardown's OCR (issue 57): the rules that confirm, correct or drop the unsure rows, with the reads faked (no
ocr tier needed), and the worker's call. The real read is in tests/tools/test_teardown.py."""

import json
import subprocess
from pathlib import Path

import pytest

from tm.tools import _common as c
from tm.tools import _ocr, teardown

FPS, W, H = 25, 540, 960
REAL_READER = _ocr.reader   # the conftest stands in for it in every test (no tier); this test checks it


def _overlay(kind, box, first, last, check="look", confidence=0.4, spans=None, methods=("edges",)):
    start, end = round(first / FPS, 3), round((last + 1) / FPS, 3)
    return {"start_frame": first, "end_frame": last, "bbox": list(box), "touches_edge": False,
            "semi_transparent": False, "kind": kind, "confidence": confidence, "methods": list(methods),
            "check": check, "transcript": None, "start_s": start, "end_s": end, "spans_s": spans or [[start, end]]}


def _data(overlays=(), bands=(), wholes=()):
    return {"fps": FPS, "width": W, "height": H, "frame_count": 200, "overlays": [dict(o) for o in overlays],
            "check_frames": [dict(b) for b in bands], "possible_whole_shot_overlays": [dict(x) for x in wholes]}


def _line(text, box, score=0.95):
    return {"text": text, "score": score, "box": list(box)}


def _reads(data, by_item):
    """Every crop of item n reads by_item[n] (a list of lines), as the worker would answer."""
    items = teardown.check_items(data)
    out = {}
    for cr in _ocr.crops_for(items, data):
        n = int(cr["id"].split(":")[0])
        out[cr["id"]] = by_item.get(n, [])
    return items, out


SAID = {"segments": [{"start": 0.0, "end": 3.0, "text": "zrobiliśmy to dla was",
                      "words": [{"word": "zrobiliśmy", "start": 0.2, "end": 0.8}, {"word": "to", "start": 0.8, "end": 1.0},
                                {"word": "dla", "start": 1.0, "end": 1.3}, {"word": "was", "start": 1.3, "end": 1.7}]}]}


def test_an_edge_find_with_words_becomes_a_sure_text_overlay_and_its_box_grows():
    data = _data([_overlay("graphic", (100, 300, 300, 360), 10, 60, teardown.GRAPHIC_CHECK)])
    items, reads = _reads(data, {0: [_line("SALE TODAY", (90, 305, 320, 355))]})
    out = _ocr.settle(data, items, reads, None, edge_px=24)
    o = data["overlays"][0]
    assert o["kind"] == "text" and o["check"] is None and o["confidence"] == 0.8
    assert o["methods"] == ["edges", "ocr"] and o["ocr_text"] == ["SALE TODAY"]
    assert o["bbox"] == [90, 300, 320, 360]        # the box cut the letters off: it grows to what was read
    assert out["counts"]["confirmed"] == 1 and out["read"][0]["verdict"] == "confirmed"
    assert out["read"][0]["bbox_now"] == [90, 300, 320, 360] and teardown.check_items(data) == []


def test_an_edge_find_with_no_words_is_dropped_and_kept_in_the_list_of_dropped():
    keep = _overlay("text", (40, 700, 500, 760), 0, 100, None, 0.9, methods=("text",))
    data = _data([keep, _overlay("graphic", (10, 10, 120, 90), 20, 80, teardown.GRAPHIC_CHECK)])
    items, reads = _reads(data, {0: [_line("x", (20, 20, 40, 40)), _line("FAINT", (20, 20, 90, 40), 0.3)]})
    out = _ocr.settle(data, items, reads, None, edge_px=24)
    assert data["overlays"] == [keep]               # one letter, and a line under MIN_SCORE: no words
    assert out["counts"] == {"confirmed": 0, "found": 0, "dropped": 1, "to_check": 0}
    assert out["read"][0]["verdict"] == "dropped"
    assert [(d["what"], d["kind"], d["bbox"]) for d in out["dropped"]] == [("overlay", "graphic", [10, 10, 120, 90])]


def test_words_outside_the_box_do_not_count():
    data = _data([_overlay("graphic", (100, 300, 300, 360), 10, 60, teardown.GRAPHIC_CHECK)])
    items, reads = _reads(data, {0: [_line("ELSEWHERE", (100, 380, 300, 400))]})   # in the margin only
    _ocr.settle(data, items, reads, None, edge_px=24)
    assert data["overlays"] == []


def test_captions_that_say_what_is_spoken_are_sure_accents_or_not():
    data = _data([_overlay("word_captions", (40, 760, 500, 820), 5, 45, teardown.CAPTIONS_CHECK, 0.6,
                           spans=[[0.2, 0.8], [0.8, 1.0], [1.0, 1.3], [1.3, 1.8]], methods=("text",))])
    items, reads = _reads(data, {0: [_line("ZROBILISMY", (60, 765, 300, 815)), _line("DLA", (60, 765, 150, 815))]})
    _ocr.settle(data, items, reads, SAID, edge_px=24)
    o = data["overlays"][0]
    assert o["check"] is None and o["confidence"] == 0.9 and o["transcript"]["ocr_match"] is True


def test_captions_that_say_something_else_stay_to_check_with_the_words():
    data = _data([_overlay("word_captions", (40, 760, 500, 820), 5, 45, teardown.CAPTIONS_CHECK, 0.6,
                           methods=("text",))])
    items, reads = _reads(data, {0: [_line("BUY TWO GET ONE", (60, 765, 450, 815))]})
    out = _ocr.settle(data, items, reads, SAID, edge_px=24)
    o = data["overlays"][0]
    assert o["transcript"]["ocr_match"] is False and "BUY TWO GET ONE" in o["check"]
    assert out["read"][0]["verdict"] == "unmatched" and teardown.check_items(data)


def test_a_full_frame_gets_its_words_and_stays_to_check():
    data = _data([_overlay("full_frame", (100, 400, 440, 560), 150, 199, teardown.FULL_FRAME_CHECK, 0.5,
                           methods=("text",))])
    items, reads = _reads(data, {0: [_line("SHOP NOW", (120, 410, 420, 470))]})
    _ocr.settle(data, items, reads, None, edge_px=24)
    o = data["overlays"][0]
    assert o["kind"] == "full_frame" and "SHOP NOW" in o["check"] and o["ocr_text"] == ["SHOP NOW"]


def test_text_that_ocr_cannot_read_stays_to_check_and_says_so():
    data = _data([_overlay("text", (100, 100, 300, 150), 10, 20, teardown.SHORT_CHECK, 0.6, methods=("text",))])
    items, reads = _reads(data, {})
    out = _ocr.settle(data, items, reads, None, edge_px=24)
    assert data["overlays"][0]["check"].endswith(_ocr.NOT_READ) and out["read"][0]["verdict"] == "not_read"


def test_a_band_where_ocr_reads_the_spoken_words_becomes_an_overlay():
    band = {"first_frame": 5, "last_frame": 45, "bbox": [0, 740, 540, 840], "start_s": 0.2, "end_s": 1.84}
    data = _data(bands=[band])
    items, reads = _reads(data, {0: [_line("to dla", (150, 760, 380, 820)), _line("was", (200, 760, 330, 820))]})
    out = _ocr.settle(data, items, reads, SAID, edge_px=24)
    assert data["check_frames"] == [] and out["counts"]["found"] == 1
    o = data["overlays"][0]
    assert o["methods"] == ["ocr"] and o["kind"] == "word_captions" and o["check"] is None
    assert o["bbox"] == [0, 740, 540, 840] and o["start_frame"] == 5 and o["end_s"] == 1.84


def test_a_band_with_nothing_read_stays():
    band = {"first_frame": 5, "last_frame": 45, "bbox": [0, 740, 540, 840], "start_s": 0.2, "end_s": 1.84}
    data = _data(bands=[band])
    items, reads = _reads(data, {})
    _ocr.settle(data, items, reads, SAID, edge_px=24)
    assert data["check_frames"] == [band] and data["overlays"] == []


def test_a_whole_shot_card_keeps_its_words_or_is_dropped():
    wholes = [{"first_frame": 0, "last_frame": 99, "bbox": [50, 50, 300, 200]},
              {"first_frame": 100, "last_frame": 199, "bbox": [60, 600, 480, 700]}]
    data = _data(wholes=wholes)
    items, reads = _reads(data, {0: [_line("LOGO CO", (60, 60, 250, 120))]})
    out = _ocr.settle(data, items, reads, None, edge_px=24)
    assert [w["bbox"] for w in data["possible_whole_shot_overlays"]] == [[50, 50, 300, 200]]
    assert data["possible_whole_shot_overlays"][0]["ocr_text"] == ["LOGO CO"]
    assert [v["verdict"] for v in out["read"]] == ["read", "dropped"]


def test_changing_captions_are_read_inside_their_spans():
    o = _overlay("word_captions", (40, 760, 500, 820), 0, 99, "look", 0.6,
                 spans=[[0.0, 0.4], [0.6, 1.0], [1.2, 1.6], [1.8, 2.2], [2.4, 2.8]])
    data = _data([o])
    item = teardown.check_items(data)[0]
    assert _ocr.frames_for(item, data) == [5, 35, 65]          # the middle of the first, middle and last span
    crops = _ocr.crops_for([item], data)
    assert [cr["box"] for cr in crops][0] == [0, 744, 540, 836]  # grown by MARGIN, inside the frame


def test_tokens_drop_accents_case_and_one_letter_words():
    assert _ocr.tokens("Zrobiliśmy TO, a Łódź!") == ["zrobilismy", "to", "lodz"]
    assert _ocr.matches(["ZR0BILISMY"], SAID, 0.0, 1.0) is True       # one misread letter
    assert _ocr.matches(["anything"], {"segments": []}, 0.0, 1.0) is None


# The teardown's side ---------------------------------------------------------------------------

def test_without_the_tier_the_unsure_rows_ask_for_the_offer(monkeypatch):
    data = _data([_overlay("graphic", (10, 10, 120, 90), 20, 80, teardown.GRAPHIC_CHECK)])
    got = teardown._read_unsure("ad.mp4", data, None, None)
    assert got["installed"] is False and got["rows"] == 1 and got["tier"] == "ocr"
    assert "tm env install ocr" in got["offer"] and "by eye" in got["offer"]
    assert teardown._read_unsure("ad.mp4", _data(), None, None) is None    # nothing unsure: nothing to offer


def test_a_failed_read_leaves_the_rows_to_check(monkeypatch):
    data = _data([_overlay("graphic", (10, 10, 120, 90), 20, 80, teardown.GRAPHIC_CHECK)])

    def broken(video, crops):
        raise c.ToolError("OCR could not run: no model")

    got = teardown._read_unsure("ad.mp4", data, None, broken)
    assert got == {"installed": True, "rows": 1, "error": "OCR could not run: no model"}
    assert len(data["overlays"]) == 1
    data["ocr"] = got
    assert any("stay to check by eye" in n for n in teardown._notes(data, None))


def test_the_teardown_reads_with_the_reader_it_is_given():
    data = _data([_overlay("graphic", (100, 300, 300, 360), 10, 60, teardown.GRAPHIC_CHECK)])
    asked = []

    def fake(video, crops):
        asked.append((video, crops))
        return {"engine": "RapidOCR 0.0", "crops": {cr["id"]: [_line("HELLO", (110, 310, 290, 350))] for cr in crops}}

    got = teardown._read_unsure("ad.mp4", data, None, fake)
    assert asked[0][0] == "ad.mp4" and [cr["frame"] for cr in asked[0][1]] == [10, 35, 60]
    assert got["engine"] == "RapidOCR 0.0" and got["counts"]["confirmed"] == 1 and data["overlays"][0]["kind"] == "text"
    data["ocr"] = got
    assert any(n.startswith("OCR read the 1 unsure row(s): 1 confirmed") for n in teardown._notes(data, None))


def test_the_worker_runs_in_the_ocr_environment(monkeypatch, tmp_path):
    from tm import paths

    root = tmp_path / "plugin Łukasz"
    monkeypatch.setattr(paths, "plugin_root", lambda: root)
    monkeypatch.setattr(paths, "pixi_bin", lambda: tmp_path / "pixi")
    argv = _ocr.worker_argv(tmp_path / "req.json", tmp_path / "res.json")
    assert argv[1:7] == ["run", "--as-is", "--manifest-path", str(root / "env" / "pixi.toml"), "-e", "ocr"]
    assert argv[7:10] == ["python", "-m", "tm.tools._ocr"] and Path(argv[-1]) == tmp_path / "res.json"


def test_read_with_tier_returns_the_workers_answer_or_says_why_not(monkeypatch, tmp_path):
    monkeypatch.setattr(_ocr, "save_frames", lambda video, frames, folder: {str(f): str(folder / f"{f}.png")
                                                                            for f in frames})
    monkeypatch.setattr(_ocr, "worker_env", lambda: {})
    seen = {}

    def worker(argv, **kw):
        seen["request"] = json.loads(Path(argv[-2]).read_text(encoding="utf-8"))
        Path(argv[-1]).write_text(json.dumps({"engine": "RapidOCR 0.0", "crops": {"0:3": []}}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(_ocr.subprocess, "run", worker)
    monkeypatch.setattr(_ocr, "worker_argv", lambda req, res: ["pixi", str(req), str(res)])
    crops = [{"id": "0:3", "frame": 3, "box": [0, 0, 10, 10]}]
    assert _ocr.read_with_tier("ad.mp4", crops)["engine"] == "RapidOCR 0.0"
    assert seen["request"]["crops"] == crops and set(seen["request"]["frames"]) == {"3"}

    monkeypatch.setattr(_ocr.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "boom\nModuleNotFoundError: x"))
    with pytest.raises(c.ToolError, match="OCR could not run: boom ModuleNotFoundError: x"):
        _ocr.read_with_tier("ad.mp4", crops)


def test_no_reader_when_the_tier_is_not_installed(monkeypatch):
    from tm import envtiers

    monkeypatch.setattr(envtiers, "installed", lambda tier: False)
    assert REAL_READER() is None
    monkeypatch.setattr(envtiers, "installed", lambda tier: tier == "ocr")
    assert REAL_READER() is _ocr.read_with_tier

    def broken(tier):
        raise RuntimeError("no plugin folders")

    monkeypatch.setattr(envtiers, "installed", broken)
    assert REAL_READER() is None
