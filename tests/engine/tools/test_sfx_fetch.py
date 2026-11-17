"""tm tool sfx_fetch (issue 96): the plugin's small set of Mixkit sound effects, shown with its licence, fetched only
after the user's yes into the workspace's sound-effects folder and copied into the run. Mixkit's pages and files are
stand-ins here: nothing is fetched from the network."""

from __future__ import annotations

import json
import subprocess
from datetime import date

import pytest
from _media import ffmpeg

from tm import config, create_config, manifest
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder
from tm.tools import sfx_fetch

CARD = """<div class="item-grid__item"><div class="item-grid-card item-grid-card--show-meta">
 <div data-audio-player-item-id-value="{id}" data-audio-player-item-type-value="sfx"></div>
 <div class="item-grid-card__meta"><h2 class="item-grid-card__title"> {title} </h2>
 <div class="item-grid-sfx-preview__meta-time" data-test-id="duration"> {length} </div></div></div></div>"""


def _page(*cards):
    return "<html><body>" + "".join(CARD.format(**x) for x in cards) + "</body></html>"


def _download_page(sid, ext):
    return f'<a href="https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}.{ext}" download>Download</a>'


@pytest.fixture
def ad(tmp_path):
    workspace = tmp_path / "Pulpit Łukasz Nowak"
    run = RunFolder.create(workspace, "acme ad", date(2026, 11, 12), playbook=CREATE_AD)
    config.save(run, create_config.defaults())
    return workspace, run


@pytest.fixture
def mixkit(monkeypatch):
    """Mixkit as it lists the set's effects, every file a short tone; `fetched` is every address asked for."""
    pages, fetched = {}, []
    effects = sfx_fetch.the_set()["effects"]
    by_page: dict[str, list] = {}
    for name, e in effects.items():
        by_page.setdefault(e["page"], []).append({"id": e["id"], "title": e["title"], "length": "0:01"})
        pages[sfx_fetch.DOWNLOAD.format(id=e["id"])] = _download_page(e["id"], "mp3" if name == "pop" else "wav")
    pages.update({url: _page(*cards) for url, cards in by_page.items()})

    def get(url):
        fetched.append(url)
        if url not in pages:
            raise sfx_fetch.c.ToolError(f"Mixkit answered 404 for {url}.")
        return pages[url]

    def download(url, dest):
        fetched.append(f"GET {url}")
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.4",
                        "-f", url.rsplit(".", 1)[1], str(dest)], check=True)

    monkeypatch.setattr(sfx_fetch, "_get", get)
    monkeypatch.setattr(sfx_fetch, "_size", lambda url: fetched.append(f"HEAD {url}") or 45678)
    monkeypatch.setattr(sfx_fetch, "_download", download)
    return pages, fetched


def _tool(capsys, run, *argv):
    code = sfx_fetch.main(["--run", str(run.path), *argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_the_set_is_basic_effects_from_mixkit_with_its_licence():
    data = sfx_fetch.the_set()
    assert {"whoosh", "click", "pop", "notification"} <= set(data["effects"])
    assert data["licence"] == "Mixkit Sound Effects Free License" and data["licence_url"].startswith("https://mixkit.co")
    for e in data["effects"].values():
        assert isinstance(e["id"], int) and e["title"] and e["page"].startswith("https://mixkit.co/free-sound-effects/")


def test_the_list_shows_the_set_and_its_licence_without_the_network(ad, mixkit, capsys):
    _, run = ad
    code, out = _tool(capsys, run, "--list")
    assert code == 0 and [r["name"] for r in out["effects"]][:1] == ["whoosh"]
    assert out["licence"] == "Mixkit Sound Effects Free License" and not any(r["here"] for r in out["effects"])
    assert mixkit[1] == []


@pytest.mark.tools
def test_nothing_is_fetched_before_the_yes_then_the_set_is_fetched_once(ad, mixkit, capsys):
    workspace, run = ad
    _, fetched = mixkit
    code, out = _tool(capsys, run, "--effect", "whoosh", "--effect", "pop")
    assert code == 2 and out["status"] == "stop" and "Nothing was fetched" in out["message"]
    assert "Mixkit Sound Effects Free License" in out["message"] and "ads" in out["message"]
    assert [x["source"] for x in out["fetch"]] == ["https://assets.mixkit.co/active_storage/sfx/1490/1490.wav",
                                                   "https://assets.mixkit.co/active_storage/sfx/2354/2354.mp3"]
    assert not [f for f in fetched if f.startswith("GET ")] and not (workspace / "library" / "sfx").exists()
    code, out = _tool(capsys, run, "--effect", "whoosh", "--effect", "pop", "--yes")
    assert code == 0, out
    assert out["effects"] == {"whoosh": "02_research/sfx/mixkit-fast-whoosh-transition-1490.wav",
                              "pop": "02_research/sfx/mixkit-message-pop-alert-2354.mp3"}
    side = json.loads((workspace / "library" / "sfx" / "mixkit-fast-whoosh-transition-1490.wav.json")
                      .read_text(encoding="utf-8"))
    assert side["licence"] == "Mixkit Sound Effects Free License" and side["source"].endswith("/1490/1490.wav")
    rows = {r["file"]: r for r in manifest.rows(run)}
    row = rows["02_research/sfx/mixkit-fast-whoosh-transition-1490.wav"]
    assert row["source"] == "tm tool sfx_fetch" and "Mixkit Sound Effects Free License" in row["params"]
    # in the workspace now: another run takes it with no question and no download
    other = RunFolder.create(workspace, "second ad", date(2026, 11, 13), playbook=CREATE_AD)
    before = len(fetched)
    code, out = _tool(capsys, other, "--effect", "whoosh")
    assert code == 0 and out["fetched"] == [] and len(fetched) == before
    assert (other.path / "02_research" / "sfx" / "mixkit-fast-whoosh-transition-1490.wav").is_file()


@pytest.mark.tools
def test_an_effect_outside_the_set_needs_its_page_and_the_yes(ad, mixkit, capsys):
    _, run = ad
    pages, _ = mixkit
    page = "https://mixkit.co/free-sound-effects/camera-shutter/"
    pages[page] = _page({"id": 1133, "title": "Camera shutter click", "length": "0:01"})
    pages[sfx_fetch.DOWNLOAD.format(id=1133)] = _download_page(1133, "wav")
    assert _tool(capsys, run, "--mixkit", "1133")[0] == 1
    assert _tool(capsys, run, "--mixkit", "1133", "--page", "https://example.test/x")[0] == 1
    code, out = _tool(capsys, run, "--mixkit", "1133", "--page", page, "--yes")
    assert code == 0 and out["outputs"] == ["02_research/sfx/mixkit-camera-shutter-click-1133.wav"]


def test_an_effect_not_in_the_set_or_gone_from_its_page_is_said(ad, mixkit, capsys):
    _, run = ad
    pages, _ = mixkit
    code, out = _tool(capsys, run, "--effect", "thunder")
    assert code == 1 and "not in the set" in out["message"] and "--search" in out["message"]
    whoosh = sfx_fetch.the_set()["effects"]["whoosh"]
    pages[whoosh["page"]] = _page()
    code, out = _tool(capsys, run, "--effect", "whoosh")
    assert code == 2 and "no longer lists" in out["message"]


def test_search_lists_mixkits_effects_for_the_words(ad, mixkit, capsys):
    _, run = ad
    pages, _ = mixkit
    pages["https://mixkit.co/free-sound-effects/paper-swipe/"] = _page({"id": 7, "title": "Paper swipe", "length": "0:01"})
    code, out = _tool(capsys, run, "--search", "Paper swipe")
    assert code == 0 and out["effects"] == [{"id": "7", "title": "Paper swipe", "length": "0:01"}]
