"""Music from the whole library in one step (issue #142 item 3, issue #144 item 1, #148 lines 3 and 23): the offered
Mixkit tracks copied into the run with their licence before the D2 page, the pick filed into the library, every
channel's free-licence tracks offered across channels (a channel's own or bought tracks stay with it), and a run
without a channel (Create an ad) keeping its track in 03_wip/audio/ and its brand's music folder. Mixkit is a
stand-in here: nothing is fetched from the network."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import date

import pytest
from _media import ffmpeg
from test_music_fetch import CALM, SUN, _page, mixkit  # noqa: F401  (the fixture)

from tm import config, create_config, manifest, organic_config
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import music_fetch, music_index

PAGE = "https://mixkit.co/free-stock-music/discover/calm-piano/"


@pytest.fixture(autouse=True)
def no_tempo(monkeypatch):
    """The tempo estimate needs numpy (the breakdown tier): left out here."""
    monkeypatch.setattr(music_index, "tempo", lambda path, duration: None)


def _profile(workspace, channel, folder=None):
    path = workspace / "library" / "channels" / channel / "channel_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "channel/1", "kind": "channel", "channel": channel,
                                "music": {"folder": folder, "index": None}}), encoding="utf-8")


def _track(path, licence=None, title="T"):
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = ["-metadata", f"title={title}"] + (["-metadata", f"licence={licence}"] if licence else [])
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=2", *tags,
                    "-f", "mp3", str(path)], check=True)
    return path


@pytest.fixture
def ws(tmp_path):
    """Two channels, kanal (the run's) and koty, each with its music; koty has one Mixkit track and one bought."""
    workspace = tmp_path / "ws"
    run = RunFolder.create(workspace, "m5", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    cfg = organic_config.defaults()
    cfg["channels"] = ["kanal"]
    config.save(run, cfg)
    _profile(workspace, "kanal")
    _profile(workspace, "koty")
    _track(workspace / "library" / "channels" / "kanal" / "music" / "own.mp3", licence="bought, for kanal")
    koty = workspace / "library" / "channels" / "koty" / "music"
    _track(koty / "mixkit-sun-580.mp3", licence=music_fetch.LICENCE)
    _track(koty / "bought.mp3", licence="Epidemic Sound, koty's subscription")
    return workspace, run


def _tool(capsys, *argv):
    code = music_fetch.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_every_folder_the_runs_first(ws):
    workspace, run = ws
    found = [(f["path"].relative_to(workspace).as_posix(), f["channel"], f["own"]) for f in music_fetch.folders(run)]
    assert found == [("library/channels/kanal/music", "kanal", True), ("library/channels/koty/music", "koty", False)]


def test_the_index_reads_every_channels_free_tracks(ws, capsys):
    workspace, run = ws
    assert music_index.main(["--run", str(run.path), "--json"]) == 0      # no folder: every music folder
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    rows = list(csv.DictReader((run.path / out["outputs"][0]).open(encoding="utf-8", newline="")))
    assert list(rows[0]) == music_index.COLUMNS + ["channel"]
    assert [(r["file"], r["channel"]) for r in rows] == [("own.mp3", "kanal"), ("mixkit-sun-580.mp3", "koty")]
    assert out["files"] == 2                                              # koty's bought track stays with koty


def test_copy_takes_another_channels_free_track_never_its_bought_one(ws, capsys):
    workspace, run = ws
    code, out = _tool(capsys, "--run", str(run.path), "--copy", "own.mp3", "--copy", "mixkit-sun-580.mp3")
    assert code == 0, out
    assert out["outputs"] == ["02_research/music/own.mp3", "02_research/music/mixkit-sun-580.mp3"]
    assert out["from"] == {"02_research/music/mixkit-sun-580.mp3": "koty"}
    code, out = _tool(capsys, "--run", str(run.path), "--copy", "bought.mp3")
    assert code == 1 and "koty" in out["message"] and "free" in out["message"]


def test_the_offered_tracks_come_into_the_run_with_their_licence(ws, mixkit, capsys):
    workspace, run = ws
    pages, fetched = mixkit
    pages[PAGE] = _page(SUN, CALM)
    code, out = _tool(capsys, "--run", str(run.path), "--search", "calm piano", "--offer", "580", "--offer", "127")
    assert code == 0, out
    offered = {t["id"]: t for t in out["offered"]}
    assert offered["580"]["file"] == "02_research/music/mixkit-sun-and-his-daughter-580.mp3"
    assert offered["127"]["file"] == "02_research/music/mixkit-calm-slow-127.mp3"
    assert offered["580"]["licence"] == music_fetch.LICENCE and "free for commercial use" in offered["580"]["licence_line"]
    assert (run.path / offered["580"]["file"]).is_file()
    rows = {r["file"]: r for r in manifest.rows(run) if r["source"] == music_fetch.OFFER_SOURCE}
    assert set(rows) == {offered["580"]["file"], offered["127"]["file"]}
    assert music_fetch.LICENCE in rows[offered["580"]["file"]]["params"]
    assert not (workspace / "library" / "channels" / "kanal" / "music" / "mixkit-sun-and-his-daughter-580.mp3").exists()
    code, out = _tool(capsys, "--run", str(run.path), "--search", "calm piano", "--offer", "999")
    assert code == 1 and "999" in out["message"]
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--offer", "580")
    assert code == 1 and "--search" in out["message"]


def test_the_picked_offer_is_filed_into_the_library_and_indexed(ws, mixkit, capsys):
    workspace, run = ws
    mixkit[0][PAGE] = _page(SUN, CALM)
    _tool(capsys, "--run", str(run.path), "--search", "calm piano", "--offer", "580", "--offer", "127")
    got = music_fetch.file_picked(run, "02_research/music/mixkit-sun-and-his-daughter-580.mp3")
    assert got["file"] == "library/channels/kanal/music/mixkit-sun-and-his-daughter-580.mp3"
    assert (workspace / got["file"]).is_file() and (run.path / got["index"]).is_file()
    assert not (workspace / "library" / "channels" / "kanal" / "music" / "mixkit-calm-slow-127.mp3").exists()
    assert music_fetch.file_picked(run, "02_research/music/own.mp3") is None          # not an offer: nothing to file


def _ad_run(workspace, *, brand_url="https://www.zorbo.example/", name="ad"):
    run = RunFolder.create(workspace, name, date(2026, 11, 12), playbook=CREATE_AD)
    cfg = create_config.defaults()
    cfg["brand"]["url"] = brand_url
    config.save(run, cfg)
    return run


def test_without_a_channel_the_track_goes_into_the_run_and_the_brands_library(tmp_path, mixkit, capsys):
    workspace = tmp_path / "ws"
    run = _ad_run(workspace)
    mixkit[0][PAGE] = _page(SUN)
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", PAGE)
    assert code == 2 and "03_wip/audio" in out["message"] and "library/brands/zorbo/music" in out["message"]
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", PAGE, "--yes")
    assert code == 0, out
    assert out["file"] == "03_wip/audio/mixkit-sun-and-his-daughter-580.mp3"
    assert (run.path / out["file"]).is_file()
    assert (workspace / "library" / "brands" / "zorbo" / "music" / "mixkit-sun-and-his-daughter-580.mp3").is_file()
    assert out["library"] == "library/brands/zorbo/music/mixkit-sun-and-his-daughter-580.mp3" and out["index"]
    rows = [r for r in manifest.rows(run) if r["file"] == out["file"]]
    assert rows and music_fetch.LICENCE in rows[0]["params"]
    later = _ad_run(workspace, name="next ad")
    found = [(f["path"].relative_to(workspace).as_posix(), f["own"]) for f in music_fetch.folders(later)]
    assert ("library/brands/zorbo/music", True) in found                  # the brand's next run finds it


def test_without_a_channel_or_a_brand_the_run_keeps_the_track(tmp_path, mixkit, capsys):
    run = _ad_run(tmp_path / "ws", brand_url=None)
    mixkit[0][PAGE] = _page(SUN)
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", PAGE, "--yes")
    assert code == 0 and out["file"] == "03_wip/audio/mixkit-sun-and-his-daughter-580.mp3" and "library" not in out
    assert music_fetch.channel_folder(run) == run.path / "03_wip" / "audio"
