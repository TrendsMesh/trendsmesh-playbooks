"""tm tool music_fetch (issue 89): a Mixkit track found, shown, fetched after the user's yes into the channel's music
folder with every field of the index filled, and the offered tracks copied into the run (the page plays them, the edit
uses the picked one). Mixkit's pages and
files are stand-ins here: nothing is fetched from the network."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import date

import pytest
from _media import ffmpeg

from tm import config, organic_config
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import music_fetch, music_index

CARD = """
<div class="item-grid__item">
 <div class="item-grid-card item-grid-card--show-meta" >
  <div data-test-id="audio-player" data-controller="audio-player"
   data-audio-player-preview-url-value="https://assets.mixkit.co/music/{id}/{id}.mp3"
   data-audio-player-item-id-value="{id}" data-audio-player-item-type-value="music"></div>
  <div class="item-grid-card__meta">
   <h2 class="item-grid-card__title"> {title} </h2>
   <p class="item-grid-music-preview__author"> by {author} </p>
   <div class="meta-links__links" >
    <a class="meta-links__link" data-global--meta-links-target="link" href="/free-stock-music/world/">World</a>
    <a class="meta-links__link" data-global--meta-links-target="link" href="/free-stock-music/mood/atmospheric/">Atmospheric</a>
    <a class="meta-links__link" data-global--meta-links-target="link" href="/free-stock-music/mood/reflective/">Reflective</a>
   </div>
   <div class="item-grid-music-preview__meta-duration"> {length} </div>
   <button class="download-button--icon" data-download--button-modal-url-value="/free-stock-music/download/{id}/?context=item+grid"> Download Free Music </button>
  </div>
 </div>
</div>"""


def _page(*tracks):
    return "<html><body>" + "".join(CARD.format(**t) for t in tracks) + "</body></html>"


SUN = {"id": "580", "title": "Sun and His Daughter", "author": "Eugenio Mininni", "length": "2:48"}
CALM = {"id": "127", "title": "Calm &amp; Slow", "author": "Arulo", "length": "0:15"}


@pytest.fixture
def ws(tmp_path):
    """A workspace with an organic run for the channel `kanal`, whose saved profile names no music folder."""
    workspace = tmp_path / "Pulpit Łukasz"
    run = RunFolder.create(workspace, "m5", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    cfg = organic_config.defaults()
    cfg["channels"] = ["kanal"]
    config.save(run, cfg)
    profile = workspace / "library" / "channels" / "kanal" / "channel_v01.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"schema": "channel/1", "kind": "channel", "channel": "kanal",
                                   "music": {"folder": None, "index": None}}), encoding="utf-8")
    return workspace, run


@pytest.fixture
def mixkit(monkeypatch, tmp_path):
    """Mixkit's pages and files: `pages` by URL, each track's mp3 a 15 s tone."""
    pages: dict[str, str] = {}
    fetched: list[str] = []

    def get(url):
        fetched.append(url)
        if url not in pages:
            raise music_fetch.c.ToolError(f"no such page {url}")
        return pages[url]

    def head(url):
        fetched.append(f"HEAD {url}")
        return 412345

    def download(url, dest):
        fetched.append(f"GET {url}")
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=330:sample_rate=44100:duration=15", "-f", "mp3", str(dest)], check=True)

    monkeypatch.setattr(music_fetch, "_get", get)
    monkeypatch.setattr(music_fetch, "_size", head)
    monkeypatch.setattr(music_fetch, "_download", download)
    return pages, fetched


def _tool(capsys, *argv):
    code = music_fetch.main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_cards_are_read_from_a_mixkit_page():
    cards = music_fetch.cards(_page(SUN, CALM))
    assert [c["id"] for c in cards] == ["580", "127"]
    sun = cards[0]
    assert (sun["title"], sun["author"], sun["length"]) == ("Sun and His Daughter", "Eugenio Mininni", "2:48")
    assert sun["moods"] == ["Atmospheric", "Reflective"] and sun["tags"] == ["World", "Atmospheric", "Reflective"]
    assert cards[1]["title"] == "Calm & Slow"
    assert sun["preview"] == "https://assets.mixkit.co/music/580/580.mp3"


def test_only_mixkit_pages_are_read(ws, mixkit, capsys):
    _, run = ws
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", "https://example.com/x")
    assert code == 1 and "mixkit.co" in out["message"] and mixkit[1] == []
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "58o")
    assert code == 1 and "number" in out["message"]


def test_a_search_lists_the_tracks(ws, mixkit, capsys):
    _, run = ws
    pages, _ = mixkit
    pages["https://mixkit.co/free-stock-music/discover/calm-piano/"] = _page(SUN, CALM)
    code, out = _tool(capsys, "--run", str(run.path), "--search", "Calm piano")
    assert code == 0, out
    assert out["page"] == "https://mixkit.co/free-stock-music/discover/calm-piano/"
    assert [t["id"] for t in out["tracks"]] == ["580", "127"] and out["tracks"][0]["licence"].startswith("Mixkit")


def test_a_track_is_shown_and_fetched_only_after_the_users_yes(ws, mixkit, capsys):
    pytest.importorskip("numpy")   # the folder's index measures the tempo (the breakdown tier)
    workspace, run = ws
    pages, fetched = mixkit
    page = "https://mixkit.co/free-stock-music/discover/calm-piano/"
    pages[page] = _page(SUN, CALM)
    music = workspace / "library" / "channels" / "kanal" / "music"
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", page)
    assert code == 2 and out["status"] == "stop"
    track = out["track"]
    assert (track["title"], track["author"], track["length"]) == ("Sun and His Daughter", "Eugenio Mininni", "2:48")
    assert track["size_mb"] == 0.4 and track["licence"] == music_fetch.LICENCE
    assert track["source"] == "https://assets.mixkit.co/music/580/580.mp3"
    assert "--yes" in out["message"] and "Mixkit" in out["message"]
    assert not music.exists() and not any(f.startswith("GET") for f in fetched)    # nothing downloaded
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", page, "--yes")
    assert code == 0, out
    assert out["file"] == "library/channels/kanal/music/mixkit-sun-and-his-daughter-580.mp3"
    assert (music / "mixkit-sun-and-his-daughter-580.mp3").is_file()
    assert [p.name for p in music.iterdir()] == ["mixkit-sun-and-his-daughter-580.mp3"]   # no part file left
    rows = list(csv.DictReader((run.path / out["index"]).open(encoding="utf-8", newline="")))
    row = rows[0]
    assert row["file"] == "mixkit-sun-and-his-daughter-580.mp3" and row["title"] == "Sun and His Daughter"
    assert row["author"] == "Eugenio Mininni" and row["mood"] == "Atmospheric, Reflective"
    assert row["licence"] == music_fetch.LICENCE and row["source"] == "https://assets.mixkit.co/music/580/580.mp3"
    assert all(row[k] for k in music_index.COLUMNS if k != "bpm_est")   # every field filled
    # fetched again: already there, never downloaded twice
    downloads = sum(f.startswith("GET") for f in fetched)
    assert _tool(capsys, "--run", str(run.path), "--mixkit", "580", "--page", page, "--yes")[0] == 0
    assert sum(f.startswith("GET") for f in fetched) == downloads


def test_a_track_not_on_the_page_asks_for_the_page(ws, mixkit, capsys):
    _, run = ws
    mixkit[0][music_fetch.FRONT] = _page(CALM)
    code, out = _tool(capsys, "--run", str(run.path), "--mixkit", "580")
    assert code == 2 and "--page" in out["message"] and "580" in out["message"]


def test_the_profiles_music_folder_is_used(ws, mixkit, capsys, tmp_path):
    workspace, run = ws
    own = tmp_path / "Moja muzyka"
    (workspace / "library" / "channels" / "kanal" / "channel_v02.json").write_text(json.dumps(
        {"schema": "channel/1", "kind": "channel", "channel": "kanal", "music": {"folder": str(own), "index": None}}),
        encoding="utf-8")
    assert music_fetch.channel_folder(run) == own


def test_the_offered_tracks_are_copied_into_the_run(ws, capsys):
    """The 2 to 3 tracks offered at D2 are copied into 02_research/music/, where the style, voice and music page plays
    them and the edit's music.src names the picked one (taste.music.file)."""
    workspace, run = ws
    music = workspace / "library" / "channels" / "kanal" / "music"
    music.mkdir(parents=True)
    for name in ("track one.mp3", "two.mp3"):
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=duration=2", "-f", "mp3",
                        str(music / name)], check=True)
    code, out = _tool(capsys, "--run", str(run.path), "--copy", "track one.mp3", "--copy", "two.mp3")
    assert code == 0, out
    assert out["outputs"] == ["02_research/music/track one.mp3", "02_research/music/two.mp3"]
    assert (run.path / "02_research" / "music" / "two.mp3").read_bytes() == (music / "two.mp3").read_bytes()
    assert "track one.mp3" in (run.path / "manifest.md").read_text(encoding="utf-8")
    again = _tool(capsys, "--run", str(run.path), "--copy", "track one.mp3")[1]
    assert again["outputs"] == ["02_research/music/track one.mp3"]                   # the same file is reused
    code, out = _tool(capsys, "--run", str(run.path), "--copy", "nothing.mp3")
    assert code == 1 and "nothing.mp3" in out["message"] and "music_fetch" in out["message"]
