"""The model ads' clips for the concepts page (issue #97): `tm ad clips` saves each model ad's thumbnail and first
~15 s from its saved Ad Library answer into the run, and the concepts page plays them. Made-up answers; the
downloads are served from a local file, never the network."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import requests

from tm import create_clips, page, run_page
from tm.cli import main

from test_create_plan import _check, _new, _write, concepts

SNAPSHOT = "https://www.facebook.com/ads/archive/render_ad/?id=ad_1&access_token=made-up"
ANSWER = {"data": [
    {"id": "ad_1", "page_name": "Made-up Planner", "ad_snapshot_url": SNAPSHOT,
     "snapshot": {"videos": [{"video_sd_url": "https://video.example/ad_1_sd.mp4",
                              "video_hd_url": "https://video.example/ad_1_hd.mp4",
                              "video_preview_image_url": "https://img.example/ad_1.jpg"}]}},
    {"id": "ad_2", "page_name": "Made-up Studio", "ad_snapshot_url": SNAPSHOT.replace("ad_1", "ad_2"),
     "snapshot": {"images": [{"original_image_url": "https://img.example/ad_2.jpg"}]}}]}


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg is not on PATH (run the tests through pixi)")
    return exe


class _Answer:
    def __init__(self, body: bytes, kind: str, status: int = 200):
        self.body, self.headers, self.status_code = body, {"Content-Type": kind}, status

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]

    def close(self):
        pass


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    path = tmp_path_factory.mktemp("ad") / "whole_ad.mp4"      # a 20 s ad with sound, wider than the clip's limit
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=teal:s=800x1000:r=5:d=20",
                    "-f", "lavfi", "-i", "sine=f=440:d=20", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


@pytest.fixture
def web(monkeypatch, video):
    """The downloads: each video URL answers with the local ad; every URL asked for is listed."""
    asked = []

    def get(url, timeout=None, stream=False, **kw):
        asked.append(url)
        if "video.example" in url:
            return _Answer(video.read_bytes(), "video/mp4")
        raise requests.ConnectionError(url)

    def image(url, dest, timeout=30):
        asked.append(url)
        if not url:
            return False
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\xff\xd8 made-up jpeg")
        return True
    monkeypatch.setattr(create_clips.requests, "get", get)
    monkeypatch.setattr(page, "fetch_image", image)
    return asked


def _probe(path) -> dict:
    ffmpeg()
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,width", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def _concepts(run):
    _write(run, "02_research/ad_library/ads_planner.json", ANSWER)
    ads = [{"id": "ad_1", "name": "The made-up planner ad", "source": "ad_library", "why": "its first 3 s",
            "saved": "02_research/ad_library/ads_planner.json", "run_days": 41},
           {"id": "ad_2", "source": "ad_library", "why": "its layout", "saved": "02_research/ad_library/ads_planner.json"},
           {"id": "m3", "source": "guess", "why": "a format I know"}]
    data = concepts(model_ads=ads)
    for c, ad in zip(data["concepts"], ("ad_1", "ad_2")):
        c["model_ad"] = ad
    return _write(run, "03_wip/concepts_v01.json", data)


def test_each_model_ads_first_15_s_and_thumbnail_are_saved_from_its_ad_library_answer(tmp_path, web):
    run = _new(tmp_path)
    got = create_clips.fetch(run, _concepts(run))
    rows = {r["id"]: r for r in got["ads"]}
    assert rows["ad_1"]["clip"] == "02_research/clips/ad_1_15s.mp4" and rows["ad_1"]["problem"] is None
    assert rows["ad_1"]["thumb"] == "02_research/clips/ad_1_thumb.jpg"
    info = _probe(run.path / rows["ad_1"]["clip"])
    assert 14.5 <= float(info["format"]["duration"]) <= 15.5                       # the first ~15 s, not the whole ad
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    assert [s["width"] for s in info["streams"] if s["codec_type"] == "video"] == [create_clips.MAX_W]
    assert "https://video.example/ad_1_hd.mp4" in web and "https://video.example/ad_1_sd.mp4" not in web   # hd first
    assert not [u for u in web if u and "render_ad" in u]               # never the snapshot page (its access token)
    assert rows["ad_2"]["clip"] is None and "no video file" in rows["ad_2"]["problem"]       # an image ad
    assert rows["ad_2"]["thumb"] == "02_research/clips/ad_2_thumb.jpg"
    assert rows["m3"]["clip"] is None and "no saved answer" in rows["m3"]["problem"]
    assert not list((run.path / create_clips.FOLDER).glob(".*"))                   # no download left behind
    web.clear()
    again = create_clips.fetch(run, run.path / "03_wip/concepts_v01.json")          # kept: nothing downloaded again
    assert again["ads"][0]["clip"] == rows["ad_1"]["clip"] and not [u for u in web if u and "video" in u]


def test_a_failed_download_says_why_and_leaves_no_file(tmp_path, monkeypatch, web):
    run = _new(tmp_path)
    monkeypatch.setattr(create_clips.requests, "get", lambda url, **kw: _Answer(b"<html>", "text/html"))
    rows = create_clips.fetch(run, _concepts(run))["ads"]
    assert rows[0]["clip"] is None and "not a video" in rows[0]["problem"]
    assert not create_clips.clip_path(run, "ad_1").exists()
    monkeypatch.setattr(create_clips.requests, "get", lambda url, **kw: _Answer(b"", "video/mp4", 403))
    assert "HTTP 403" in create_clips.fetch(run, _concepts(run))["ads"][0]["problem"]


def test_tm_ad_clips_and_the_concepts_page_plays_them_with_the_thumbnail_as_poster(tmp_path, web, capsys):
    run = _new(tmp_path)
    path = _concepts(run)
    assert main(["ad", "clips", "--run", str(run.path), "--file", str(path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["ads"][0]["clip"] == "02_research/clips/ad_1_15s.mp4"
    assert _check(run, "concepts", json.loads(path.read_text(encoding="utf-8"))) == []
    ask = _write(run, "03_wip/my_ask.json", {"checkin": "concept", "title": "Concepts", "question": "Which one?",
                                             "options": [{"choice": "accept", "label": "Go"}]})
    built = run_page.build(run, ask)
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    assert '<video src="assets/media/01_ad_1_15s.mp4" poster="assets/media/02_ad_1_thumb.jpg"' in html
    assert '<img src="assets/media/03_ad_2_thumb.jpg"' in html                        # the image ad: its thumbnail
    assert (run.path / built["folder"] / "assets/media/01_ad_1_15s.mp4").is_file()
    assert "access_token" not in html
