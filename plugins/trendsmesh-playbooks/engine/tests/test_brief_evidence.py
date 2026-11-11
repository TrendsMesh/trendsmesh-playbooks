"""tm brief evidence on TrendsMesh clips (issue #11): every thumbnail URL ends in `/thumb.jpg`, so each kept file is
named by the clip's video id, and its path is written back into the brief for `tm brief page`.

A made-up run, public: one trend's saved video page and a brief whose clips name the TrendsMesh thumbnail URLs.
No test touches the network: `requests.get` is replaced.
"""

import json
from datetime import date

import pytest
import requests

from tm import brief_page, manifest, trends
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder
from tm.stops import Stop

TREND = "t-0001"
IDS = ("tiktok:1001", "tiktok:1002", "tiktok:1003")


def _video(asset_id: str) -> dict:
    n = asset_id.split(":")[1]
    return {"asset_id": asset_id, "url": f"https://www.tiktok.com/@maker{n}/video/{n}", "creator": f"maker{n}",
            "published": "2026-10-30T10:00:00Z", "views": 1000, "thumbnail_url": f"https://cdn.example.com/{n}/thumb.jpg"}


def _brief() -> dict:
    clips = [{"url": _video(a)["url"], "thumb": _video(a)["thumbnail_url"], "views": "1K views", "caption": f"Clip {a}"}
             for a in IDS]
    return {
        "meta": {"title": "Lumen lamp", "market": "US", "language": "en", "prepared": "2026-11-01",
                 "valid_until": "2026-11-15", "recipients": ["strategy", "creator"], "product": {"name": "Lumen"}},
        "concepts": [{
            "id": "C1", "brief_id": "B1", "title": "Day one", "one_liner": "A diary.", "key_message": "Calmer evenings.",
            "hypothesis": "A diary hook holds.", "glance": [], "hook": {"text": "Day 1"},
            "beats": [{"t0": 0, "t1": 3, "see": "A lamp", "hear": "Day one", "ost": "Day 1"}],
            "animatic": {"9x16": "animatic/C1_9x16_v01.mp4", "default": "9x16"},
            "copy_from_hook": {"text": "The diary count.", "evidence": clips},
            "plugin": {"trend": {"trend_id": TREND}},
        }],
    }


class _Image:
    headers = {"Content-Type": "image/jpeg"}

    def __init__(self, body: bytes):
        self.body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        yield self.body

    def close(self):
        pass


@pytest.fixture
def web(monkeypatch):
    """requests.get replaced: offline unless `answers` holds the URL."""
    calls, answers = [], {}

    def get(url, **kw):
        calls.append(url)
        if url not in answers:
            raise requests.ConnectionError("offline")
        return _Image(answers[url])
    monkeypatch.setattr(requests, "get", get)
    return calls, answers


@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    run = RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)
    trends.save_answer(run, "get_trend_videos", {"trend_id": TREND},
                       {"data": [_video(a) for a in IDS], "page": 1, "has_more": False}, at="2026-11-01T09:00:00+00:00")
    _put(run, "04_final/brief_pack_v01.json", json.dumps(_brief()))
    _put(run, f"{brief_page.RENDERS}/C1_9x16_v01.mp4", b"mp4")
    return run


def _put(run: RunFolder, rel: str, data) -> None:
    path = run.path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data) if isinstance(data, bytes) else path.write_text(data, encoding="utf-8")


def _cli(capsys, *argv) -> tuple[int, dict]:
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _clips(run: RunFolder, rel: str) -> list[dict]:
    return json.loads((run.path / rel).read_text(encoding="utf-8"))["concepts"][0]["copy_from_hook"]["evidence"]


def test_each_clip_keeps_its_own_thumbnail_by_video_id(run, capsys, web):
    calls, answers = web
    for a in IDS:
        answers[_video(a)["thumbnail_url"]] = b"\xff\xd8 " + a.encode()
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    names = [f"tiktok_{a.split(':')[1]}.jpg" for a in IDS]
    assert out["fetched"] == [f"{brief_page.EVIDENCE}/{n}" for n in names] and out["missing"] == []
    for a, n in zip(IDS, names):
        assert (run.path / brief_page.EVIDENCE / n).read_bytes() == b"\xff\xd8 " + a.encode()
    # the new version names the kept files, never the URLs: the page builds from it as it is
    assert out["brief"] == "04_final/brief_pack_v02.json"
    assert [x["thumb"] for x in _clips(run, out["brief"])] == [f"evidence/{n}" for n in names]
    row = next(r for r in manifest.rows(run) if r["file"] == out["brief"])
    assert row["source"] == "tm brief evidence"
    got = brief_page.build(run)
    assert got["media_missing"] == [] and got["media_copied"] == 1 + 3
    html = (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")
    assert all(f'src="evidence/{n}"' in html for n in names) and "thumb.jpg" not in html

    count = len(calls)                                   # kept: never fetched again, no new version
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0 and out["brief"] is None and calls[count:] == []
    assert out["fetched"] == [f"{brief_page.EVIDENCE}/{n}" for n in names]


def test_a_thumbnail_not_kept_leaves_no_url_for_the_page(run, capsys, web):
    calls, answers = web
    answers[_video(IDS[0])["thumbnail_url"]] = b"\xff\xd8"          # the other two are offline
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    assert {m["url"]: m["why"] for m in out["missing"]} == {_video(a)["url"]: "not fetched" for a in IDS[1:]}
    clips = _clips(run, out["brief"])
    assert clips[0]["thumb"] == "evidence/tiktok_1001.jpg"
    assert ["thumb" in x for x in clips[1:]] == [False, False]      # the URL taken out: the page shows the link
    assert "without them" in out["message"]
    got = brief_page.build(run)
    assert got["media_missing"] == [] and got["media_copied"] == 1 + 1


def test_a_kept_file_of_another_clip_is_never_reused(run, capsys, web):
    calls, answers = web
    answers[_video(IDS[0])["thumbnail_url"]] = b"\xff\xd8 one"
    kept = f"{brief_page.EVIDENCE}/tiktok_1001.jpg"
    _put(run, kept, b"\xff\xd8 other")
    manifest.record(run, kept, "02_research", "tm brief evidence", parent="x",
                    params={"url": "https://cdn.example.com/x/thumb.jpg", "clip": "https://www.tiktok.com/@else/video/9"})
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    assert {m["url"]: m["why"] for m in out["missing"]}[_video(IDS[0])["url"]] == "thumb name used by another clip"
    assert (run.path / kept).read_bytes() == b"\xff\xd8 other"


def test_a_hidden_name_and_a_video_without_id_are_listed_not_fetched(run, capsys, web):
    calls, answers = web
    videos = [_video(a) for a in IDS]
    videos[0]["asset_id"] = ".1001"                     # page.files would never publish it
    del videos[1]["asset_id"]
    trends.save_answer(run, "get_trend_videos", {"trend_id": TREND}, {"data": videos, "page": 1, "has_more": False},
                       at="2026-11-02T09:00:00+00:00")
    for a in IDS:
        answers[_video(a)["thumbnail_url"]] = b"\xff\xd8"
    code, out = _cli(capsys, "brief", "evidence", "--run", str(run.path))
    assert code == 0, out
    why = {m["url"]: m["why"] for m in out["missing"]}
    assert why == {videos[0]["url"]: "thumb name starts with a dot", videos[1]["url"]: "no asset_id in the saved video"}
    assert out["fetched"] == [f"{brief_page.EVIDENCE}/tiktok_1003.jpg"]
    assert sorted(p.name for p in (run.path / brief_page.EVIDENCE).iterdir()) == ["tiktok_1003.jpg"]


def test_page_refuses_a_remote_thumb_and_says_what_to_run(run):
    brief = _brief()
    for x in brief["concepts"][0]["copy_from_hook"]["evidence"]:
        x["plugin"] = {"as_of": "2026-11-01"}
    _put(run, "04_final/brief_pack_v02.json", json.dumps(brief))
    with pytest.raises(Stop, match=r"web address.*tm brief evidence"):
        brief_page.build(run)
