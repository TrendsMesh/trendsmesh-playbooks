"""teardown: scenes, frames, overlays (edges and temporal differences) and the teardown JSON."""

import json

import pytest

pytestmark = pytest.mark.tools
pytest.importorskip("cv2")
pytest.importorskip("scenedetect")

from _media import BAR, CARD, FPS, H, W, make_clip  # noqa: E402
from tm import changes  # noqa: E402
from tm.tools import teardown  # noqa: E402


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])  # noqa: E731
    return inter / (area(a) + area(b) - inter)


def _match(found, box):
    best = max(found, key=lambda o: _iou(o.bbox, box), default=None)
    assert best is not None and _iou(best.bbox, box) > 0.6, [o.bbox for o in found]
    return best


def test_overlay_found_with_edge_contact(clip):
    found = teardown.overlays(clip)
    bar = _match(found, BAR)
    assert bar.touches_edge
    assert bar.semi_transparent
    assert abs(bar.start_frame - 20) <= 2 and abs(bar.end_frame - 55) <= 2


def test_opaque_card_inside_the_frame(clip):
    card = _match(teardown.overlays(clip), CARD)
    assert not card.touches_edge
    assert not card.semi_transparent
    assert abs(card.start_frame - 25) <= 2 and abs(card.end_frame - 50) <= 2


def test_overlay_sliding_in_from_the_left_touches_edge(tmp_path):
    # A semi-transparent bar that slides in from beyond the left edge, then stays at x 120..420.
    vf = ("color=c=white@0.5:s=300x100:r=25,format=rgba[b];[in][b]overlay="
          "x='if(lt(t,1),-300+420*(t-0.6)/0.4,120)':y=650:enable='gte(t,0.6)':shortest=1")
    video = make_clip(tmp_path / "slide in.mp4", vf=vf)
    bar = _match(teardown.overlays(video), (120, 650, 420, 750))
    assert bar.touches_edge
    assert bar.start_frame <= 17  # the entry animation counts (first partial frame is 16)


def test_overlay_across_a_cut_is_found_even_when_it_never_leaves(tmp_path):
    # testsrc2 cuts to a mandelbrot at 1.5 s; a card stays on screen the whole time.
    vf = ("mandelbrot=size=540x960:rate=25[m];[in][m]overlay=enable='gte(t,1.5)':shortest=1,"
          "drawbox=x=100:y=420:w=340:h=120:color=white:t=fill")
    video = make_clip(tmp_path / "cut.mp4", vf=vf)
    assert len(teardown.scenes(video)) == 2
    card = _match(teardown.overlays(video), (100, 420, 440, 540))
    assert card.start_frame <= 2 and card.end_frame >= 72
    assert not card.touches_edge


def test_card_over_most_of_a_single_shot_is_found(tmp_path):
    # The review's probe: a white card from 0.5 s to 9.5 s of a 10 s single shot at 30 fps.
    vf = "drawbox=x=100:y=150:w=340:h=100:color=white:t=fill:enable='between(t,0.5,9.5)'"
    video = make_clip(tmp_path / "long card.mp4", vf=vf, seconds=10.0, tone=False, fps=30)
    card = _match(teardown.overlays(video), (100, 150, 440, 250))
    assert abs(card.start_frame - 15) <= 3 and abs(card.end_frame - 285) <= 3
    assert not card.touches_edge


def test_card_over_the_whole_shot_is_flagged_in_the_notes(tmp_path):
    # Over a moving picture (a mandelbrot zoom); over a still shot nothing can tell it apart.
    vf = ("mandelbrot=size=540x960:rate=25[m];[in][m]overlay=shortest=1,"
          "drawbox=x=100:y=150:w=340:h=100:color=white:t=fill")
    video = make_clip(tmp_path / "whole card.mp4", vf=vf, seconds=3.0, tone=False)
    data = teardown.teardown(video, transcript={"segments": []})
    flagged = [n for n in data["notes"] if n.startswith("Possible overlay spanning the whole shot")]
    assert flagged, data["notes"]
    assert data["possible_whole_shot_overlays"]
    box = data["possible_whole_shot_overlays"][0]["bbox"]
    assert _iou(box, (100, 150, 440, 250)) > 0.5


def test_scenes_single_shot(clip):
    assert teardown.scenes(clip) == [(0.0, 3.0)]


def test_frames_every_second(clip, tmp_path):
    out = tmp_path / "klatki Łukasz"
    files = teardown.frames(clip, out, every_s=1.0)
    assert [round(t, 2) for _, t in files] == [0.0, 1.0, 2.0]
    assert all(p.is_file() and p.parent == out for p, _ in files)


def test_teardown_json_has_material_keys_and_is_recorded(clip, run, tmp_path):
    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps({"language": "pl", "segments": []}))
    assert teardown.main(["--run", str(run.path), str(clip), "--transcript", str(transcript)]) == 0
    out = run.path / "02_research" / "teardown_v01.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["is_video"] is True and data["has_speech"] is False  # lesson 3: no speech is fine
    assert data["speech_on_camera"] is False
    assert (data["width"], data["height"], data["fps"]) == (W, H, FPS)
    assert data["scenes"] == [{"start_s": 0.0, "end_s": 3.0, "start_frame": 0, "end_frame": 74}]
    assert {"start_frame", "end_frame", "start_s", "end_s", "bbox", "touches_edge", "semi_transparent", "kind",
            "confidence", "methods", "check", "spans_s", "transcript"} <= set(data["overlays"][0])
    assert data["check_frames"] == []
    assert data["frames"]["files"] and (run.path / data["frames"]["dir"]).is_dir()
    assert changes.classify_material(data) == "text_cards"
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "02_research/teardown_v01.json" in manifest
    assert (out.parent / "teardown_v01.json.response.json").is_file()
    assert "02_research/teardown_v01_frames" in manifest


def test_teardown_has_speech_from_transcript(clip, run, tmp_path):
    transcript = tmp_path / "t.json"
    transcript.write_text(json.dumps({"language": "pl", "segments": [
        {"start": 0.2, "end": 2.5, "text": "Zimowa wyprzedaż", "words": [
            {"start": 0.2, "end": 1.0, "word": "Zimowa", "probability": 0.9}]}]}))
    data = teardown.teardown(clip, transcript=json.loads(transcript.read_text()))
    assert data["has_speech"] is True
    assert data["speech_on_camera"] is False  # testsrc2 has no face
    assert data["speech_on_camera_evidence"]["sampled"] > 0
    assert changes.classify_material(data) == "vo_captions"


def test_still_image_is_not_video(tmp_path, run):
    from _media import ffmpeg
    import subprocess

    img = tmp_path / "grafika.png"
    subprocess.run([ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=540x960",
                    "-frames:v", "1", str(img)], check=True)
    data = teardown.teardown(img, transcript={"segments": []})
    assert data["is_video"] is False
    assert changes.classify_material(data) == "static"


# Text overlays (issue #29): a synthetic ad with word-by-word captions, a two-line hook, a second
# top caption and an end card (_textad.py has the layout and times).

import _textad as ad  # noqa: E402
from tm.tools import _text_overlays as tx  # noqa: E402


@pytest.fixture(scope="module")
def text_ad(tmp_path_factory):
    return ad.make_ad(tmp_path_factory.mktemp("text ad") / "Reklama z napisami.mp4")


@pytest.fixture(scope="module")
def text_teardown(text_ad):
    return teardown.teardown(text_ad, ad.transcript())


def _find(data, part, kind=None):
    want = ad.box(part)
    pool = [o for o in data["overlays"] if kind is None or o["kind"] == kind]
    best = max(pool, key=lambda o: _iou(o["bbox"], want), default=None)
    assert best is not None and _iou(best["bbox"], want) > 0.6, \
        (want, [(o["kind"], o["bbox"], o["start_s"], o["end_s"]) for o in data["overlays"]])
    return best


def test_word_by_word_captions_are_one_overlay_matched_to_the_transcript(text_teardown):
    cap = _find(text_teardown, "words", "word_captions")
    assert abs(cap["start_s"] - ad.WORDS[0][1]) <= 0.1 and abs(cap["end_s"] - ad.WORDS[-1][2]) <= 0.1
    assert cap["transcript"]["aligned"] is True
    assert cap["transcript"]["on_word_starts"] >= 0.6 * len(ad.WORDS)
    assert cap["confidence"] >= 0.8 and cap["check"] is None and "text" in cap["methods"]
    assert len(cap["spans_s"]) >= 3  # the pauses between the words show
    captions = [o for o in text_teardown["overlays"] if o["kind"] == "word_captions"]
    assert len(captions) == 1, captions


def test_two_line_hook_is_one_box_from_its_first_frame(text_teardown):
    # Line 2 (on a semi-transparent bar) comes 0.6 s after line 1 and leaves 0.4 s before it.
    hook = _find(text_teardown, "hook", "text")
    assert _iou(hook["bbox"], ad.box("hook")) > 0.75
    assert hook["start_s"] <= 0.1 and abs(hook["end_s"] - ad.HOOK[0][3]) <= 0.1
    line2 = (0, ad.HOOK[1][1] - 40, ad.W, ad.HOOK[1][1] + 30)
    others = [o for o in text_teardown["overlays"] if o is not hook and o["start_s"] < ad.HOOK[0][3]
              and teardown._overlap(o["bbox"], line2) > 0.3 and o["kind"] != "graphic"]
    assert not others, others


def test_second_top_caption_is_its_own_overlay(text_teardown):
    # The edge method joins it with the hook line in the same band (one box, 0 to 4.6 s).
    top2 = _find(text_teardown, "top2", "text")
    assert abs(top2["start_s"] - ad.TOP2[2]) <= 0.1 and ad.TOP2[3] - 0.1 <= top2["end_s"] <= ad.TOP2[3] + 0.25
    hook = _find(text_teardown, "hook", "text")
    assert hook is not top2 and hook["end_s"] < ad.TOP2[2]


def test_full_frame_end_card_is_an_overlay_to_check(text_teardown):
    card = _find(text_teardown, "end_card", "full_frame")
    assert abs(card["start_s"] - ad.END_CARD_S) <= 0.05 and card["end_s"] == ad.SECONDS
    assert card["check"]
    assert not text_teardown["possible_whole_shot_overlays"]  # an overlay now, not only a note
    assert not [o for o in text_teardown["overlays"] if o["kind"] == "full_frame" and o["start_s"] < ad.END_CARD_S]


def test_text_over_a_still_picture(tmp_path):
    video = ad.make_ad(tmp_path / "still.mp4", pan=0.0)
    data = teardown.teardown(video, ad.transcript())
    assert _find(data, "words", "word_captions")["transcript"]["aligned"] is True
    _find(data, "hook", "text")
    _find(data, "top2", "text")
    assert [o["start_s"] for o in data["overlays"] if o["kind"] == "full_frame"] == [ad.END_CARD_S]


def test_changing_text_without_a_transcript_is_flagged(text_ad):
    data = teardown.teardown(text_ad, None)
    cap = _find(data, "words", "word_captions")
    assert cap["transcript"] is None and cap["check"] == teardown.UNCHECKED_CAPTIONS
    assert cap["confidence"] < 0.8


def test_captions_out_of_step_with_the_speech_are_flagged(text_ad):
    late = ad.transcript()
    for w in late["segments"][0]["words"]:  # half way between the caption changes
        w["start"] += 0.17
    cap = _find(teardown.teardown(text_ad, late), "words", "word_captions")
    assert cap["transcript"]["aligned"] is False and cap["check"] == teardown.CAPTIONS_CHECK


def test_words_on_screen_without_a_text_line_ask_for_a_frame_check(text_ad, monkeypatch):
    # Captions in a font the line finder misses: the band still changes with the spoken words.
    lines = tx._Strokes.lines
    monkeypatch.setattr(tx._Strokes, "lines",
                        lambda self, t, raw=False: [b for b in lines(self, t, raw) if b[1] < self.gray.shape[1] * 0.6])
    data = teardown.teardown(text_ad, ad.transcript())
    band = ad.box("words")
    hits = [x for x in data["check_frames"] if x["bbox"][1] < band[3] and x["bbox"][3] > band[1]]
    assert hits, data["check_frames"]
    assert hits[0]["start_s"] <= 1.0 and hits[0]["end_s"] >= 4.5
    assert any("no text was found there" in n for n in data["notes"])


def test_alignment_is_measured_against_chance():
    words = [0.2 + 0.4 * i for i in range(10)]
    on = tx._alignment([w + 0.04 for w in words], words, 0.2, 4.2)
    assert on["aligned"] and on["share"] == 1.0 and on["chance"] < 0.7
    off = tx._alignment([w + 0.2 for w in words], words, 0.2, 4.2)
    assert not off["aligned"] and off["share"] == 0.0
    assert tx._alignment([1.0], [], 0.0, 2.0) is None
    assert tx._chance([1.0], 0.0, 2.0) == pytest.approx(2 * tx.ALIGN_S / 2.0)


# The contact sheet of what the tool is unsure of (issue 57): one row per item to check, its box drawn on its first,
# middle and last frame.

def _png(path):
    import cv2
    import numpy as np

    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def _red(pixel) -> bool:
    b, g, r = (int(v) for v in pixel)
    return r > 180 and g < 90 and b < 90


def test_check_items_list_the_unsure_first_and_skip_the_sure(text_teardown):
    items = teardown.check_items(text_teardown)
    sure = [o for o in text_teardown["overlays"] if o["check"] is None]
    assert sure and len(items) == len(text_teardown["overlays"]) - len(sure)   # the word captions are sure
    assert all(i["what"] == "overlay" and i["check"] for i in items)
    assert [i["confidence"] for i in items] == sorted(i["confidence"] for i in items)
    end = next(i for i in items if i["kind"] == "full_frame")
    o = text_teardown["overlays"][end["overlay"]]
    assert end["frames"] == [o["start_frame"], (o["start_frame"] + o["end_frame"]) // 2, o["end_frame"]]
    assert end["bbox"] == o["bbox"] and end["t_s"][0] == o["start_s"]


def test_check_items_take_the_bands_and_whole_shot_notes_too():
    data = {"fps": 25, "overlays": [],
            "check_frames": [{"first_frame": 10, "last_frame": 11, "bbox": [0, 0, 10, 10], "start_s": 0.4}],
            "possible_whole_shot_overlays": [{"first_frame": 0, "last_frame": 74, "bbox": [5, 5, 50, 50]}]}
    items = teardown.check_items(data)
    assert [i["what"] for i in items] == ["check_frames", "whole_shot"]
    assert items[0]["frames"] == [10, 11] and items[1]["frames"] == [0, 37, 74]
    assert teardown.check_items({"fps": 25, "overlays": [], "check_frames": [],
                                 "possible_whole_shot_overlays": []}) == []


def test_check_sheet_draws_each_box_on_three_frames(clip, tmp_path):
    items = [{"frames": [25, 37, 50], "bbox": list(CARD)}, {"frames": [20, 55], "bbox": list(BAR)}]
    out = tmp_path / "unsure sheet ł.png"
    teardown.check_sheet(clip, items, out)
    img = _png(out)
    tile_w = teardown.SHEET_TILE_W
    tile_h = round(H * tile_w / W / 2) * 2
    assert img.shape[:2] == (2 * tile_h, 3 * tile_w)
    s = tile_w / W
    for col in range(3):                    # row 1: the card's top edge is red in all three tiles
        x, y = col * tile_w + round((CARD[0] + CARD[2]) / 2 * s), round(CARD[1] * s) + 1
        assert _red(img[y, x]), (col, img[y, x])
    x, y = round((BAR[0] + BAR[2]) / 2 * s), tile_h + round(BAR[1] * s) + 1
    assert _red(img[y, x])                  # row 2: the bar's box
    assert img[tile_h + tile_h // 2, 2 * tile_w + tile_w // 2].max() < 30   # its third tile is blank: two frames


def test_teardown_writes_the_check_sheet_and_records_it(text_ad, run, tmp_path):
    transcript = tmp_path / "words.json"
    transcript.write_text(json.dumps(ad.transcript()), encoding="utf-8")
    assert teardown.main(["--run", str(run.path), str(text_ad), "--transcript", str(transcript)]) == 0
    data = json.loads((run.path / "02_research" / "teardown_v01.json").read_text(encoding="utf-8"))
    sheet = data["check_sheet"]
    assert sheet["file"] == "02_research/teardown_v01_check.png" and (run.path / sheet["file"]).is_file()
    assert [r["row"] for r in sheet["rows"]] == list(range(1, len(sheet["rows"]) + 1))
    assert {r["what"] for r in sheet["rows"]} == {"overlay"} and sheet["limits"] == list(teardown.TEXT_LIMITS)
    assert _png(run.path / sheet["file"]).shape[0] > len(sheet["rows"]) * 100
    assert "02_research/teardown_v01_check.png" in (run.path / "manifest.md").read_text(encoding="utf-8")


def test_nothing_to_check_writes_no_sheet(tmp_path):
    out = tmp_path / "none.png"
    assert teardown.check_sheet(tmp_path / "missing.mp4", [], out) is None and not out.exists()
