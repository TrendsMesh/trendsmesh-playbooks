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
    assert {"start_frame", "end_frame", "start_s", "end_s", "bbox", "touches_edge",
            "semi_transparent"} <= set(data["overlays"][0])
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
