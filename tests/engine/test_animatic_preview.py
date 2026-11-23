"""Issue #162 item 1: each rendered animatic gets a 720p preview for the brief page (the shorter side 720, a bitrate
set from its length so it stays at or under PREVIEW_MAX_BYTES), kept beside the full-size MP4 as
`<C>_animatic_<fmt>_<ver>_720p.mp4`; the brief names it as `animatic.preview.<fmt>` ({path, bytes}), and the full-size
file stays as it was. The encoder runs on short synthetic clips (ffmpeg's testsrc); `atlas.render` is replaced, as in
test_animatic_styled.py.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tm import animatic, atlas, brief_page, manifest, page
from tm.tools import _common as c

import test_animatic_styled as styled
from test_animatic_styled import _cli, _concept, _latest, _module, _styled, run, ws  # noqa: F401  (fixtures)


def _clip(path: Path, size: str, seconds: float = 1.0, sound: bool = True) -> Path:
    """A short synthetic clip (testsrc, with a tone) at `size`."""
    args = [c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=24",
            *(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"] if sound else []),
            "-t", f"{seconds:g}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            *(["-c:a", "aac", "-shortest"] if sound else []), str(path)]
    subprocess.run(args, check=True, capture_output=True)
    return path


# --- the bitrate ------------------------------------------------------------------------------------------------

def test_the_bitrate_comes_from_the_length_and_keeps_under_the_budget():
    budget = animatic.PREVIEW_MAX_BYTES
    assert animatic.preview_kbps(15) == animatic.PREVIEW_KBPS_MAX           # a short animatic: the quality cap
    for seconds in (60, 120, 300):
        kbps = animatic.preview_kbps(seconds)
        total = (kbps + animatic.PREVIEW_AUDIO_KBPS) * 1000 / 8 * seconds
        assert total <= budget, seconds
    assert animatic.preview_kbps(600) < animatic.preview_kbps(120) < animatic.PREVIEW_KBPS_MAX
    assert animatic.preview_kbps(10**6) == animatic.PREVIEW_KBPS_MIN       # never zero: a very long one may not fit
    assert animatic.preview_of(Path("r/C1_animatic_9x16_v02.mp4")) == Path("r/C1_animatic_9x16_v02_720p.mp4")


# --- the encode -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size, want", [("1080x1920", (720, 1280)), ("1080x1350", (720, 900))])
def test_the_preview_is_720p_on_its_shorter_side(tmp_path, size, want):
    src = _clip(tmp_path / "C1_animatic_x_v01.mp4", size)
    before = src.read_bytes()
    got = animatic.make_preview(src)
    out = tmp_path / "C1_animatic_x_v01_720p.mp4"
    assert got["path"] == out and got["bytes"] == out.stat().st_size <= animatic.PREVIEW_MAX_BYTES
    info = c.probe(out)
    assert (info["width"], info["height"]) == want and info["has_audio"]
    assert abs(info["duration"] - 1.0) < 0.2
    assert src.read_bytes() == before                                       # the full-size file is untouched
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]   # no part file left
    with pytest.raises(FileExistsError):
        animatic.make_preview(src)                                          # never over an earlier file


def test_the_preview_steps_the_bitrate_down_until_it_fits(tmp_path, monkeypatch):
    src = _clip(tmp_path / "C1_animatic_9x16_v01.mp4", "1080x1920", sound=False)
    tried: list[int] = []

    def encode(src_, part, kbps, scale, sound):
        tried.append(kbps)
        part.write_bytes(b"x" * kbps * 8000)                                # 2500 kb/s: 20 MB, over the budget
    monkeypatch.setattr(animatic, "_encode_preview", encode)
    got = animatic.make_preview(src)
    assert tried[0] == animatic.PREVIEW_KBPS_MAX and tried == sorted(tried, reverse=True) and len(tried) > 1
    assert got["bytes"] <= animatic.PREVIEW_MAX_BYTES and got["kbps"] == tried[-1]

    tried.clear()
    monkeypatch.setattr(animatic, "PREVIEW_MAX_BYTES", 1)                  # never fits: the last try is kept
    got = animatic.make_preview(_clip(tmp_path / "C2_animatic_9x16_v01.mp4", "1080x1920", sound=False))
    assert len(tried) == animatic.PREVIEW_TRIES and got["bytes"] > 1 and got["path"].is_file()


# --- in the render ----------------------------------------------------------------------------------------------

def _fake_preview(made: list):
    def make(src, duration=None):
        out = animatic.preview_of(src)
        out.write_bytes(b"preview " + Path(src).name.encode())
        made.append(Path(src).name)
        return {"path": out, "bytes": out.stat().st_size, "kbps": 900}
    return make


@pytest.fixture
def renderer(monkeypatch):
    calls: list = []
    monkeypatch.setattr(atlas, "need", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(atlas, "missing", lambda: None)
    monkeypatch.setattr(atlas, "layout", lambda page_: {"beats": [0, 3, 9]})
    monkeypatch.setattr(atlas, "layout_problems", lambda summary: [])
    monkeypatch.setattr(atlas, "render", styled._fake_render(calls))
    return calls


def test_the_render_names_each_preview_in_the_brief(run, capsys, renderer, monkeypatch):  # noqa: F811
    made: list = []
    monkeypatch.setattr(animatic, "make_preview", _fake_preview(made))
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 0, out
    v = out["version"]
    assert made == [f"C1_animatic_9x16_{v}.mp4", f"C1_animatic_4x5_{v}.mp4"]
    a = _concept(_latest(run), "C1")["animatic"]
    assert a["9x16"] == f"animatic/C1_animatic_9x16_{v}.mp4"                # the full-size file, as before
    size = len(f"preview C1_animatic_9x16_{v}.mp4".encode())
    assert a["preview"]["9x16"] == {"path": f"animatic/C1_animatic_9x16_{v}_720p.mp4", "bytes": size}
    assert set(a["preview"]) == {"9x16", "4x5"}
    assert out["items"][0]["preview"] == {"path": f"{animatic.RENDERS}/C1_animatic_9x16_{v}_720p.mp4", "bytes": size}
    rows = {r["file"]: r for r in manifest.rows(run)}
    prow = rows[f"{animatic.RENDERS}/C1_animatic_9x16_{v}_720p.mp4"]
    assert prow["parent"] == f"{animatic.RENDERS}/C1_animatic_9x16_{v}.mp4" and prow["cost"] == "0"
    assert json.loads(prow["params"])["kbps"] == 900
    assert "720p preview" in out["message"] and "too big" not in out["message"]


def test_a_preview_that_cannot_be_made_is_said_and_the_render_holds(run, capsys, renderer):  # noqa: F811
    """The fake render writes no real MP4, so ffmpeg cannot read it: the render stands, the brief names no preview
    for it, and the answer says the page will serve the full-size file."""
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1",
                     "--formats", "9x16")
    assert code == 0, out
    assert "preview" not in _concept(_latest(run), "C1")["animatic"]
    assert out["items"][0]["preview_error"] and "full-size" in out["message"]


def test_the_render_says_when_a_preview_is_still_over_the_limit(run, capsys, renderer, monkeypatch):  # noqa: F811
    """Item 2: the old hint (fewer formats in animatic.formats, which cannot change after A1) is gone; the answer
    says the page is built without the file and names the local file."""
    monkeypatch.setattr(animatic, "make_preview", _fake_preview([]))
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 10)
    row = _styled(run, capsys)
    (run.path / row["module"]).write_text(_module([0, 3, 9]), encoding="utf-8")
    code, out = _cli(capsys, "brief", "animatic", "--run", str(run.path), "--render", "--concepts", "C1")
    assert code == 0, out
    assert "animatic.formats" not in out["message"] and "shorter" not in out["message"]
    assert "without it" in out["message"] and f"C1_animatic_9x16_{out['version']}.mp4" in out["message"]


# --- the page (issue #162 items 1 and 2) ------------------------------------------------------------------------

FULL = {f: f"C1_animatic_{f}_v01.mp4" for f in animatic.FORMATS}
PREV = {f: f"C1_animatic_{f}_v01_720p.mp4" for f in animatic.FORMATS}


def _rendered(run, preview_bytes: dict[str, int], version: str = "v02") -> dict:  # noqa: F811
    """C1 rendered in both formats with a preview of each (the sizes given), as tm brief animatic --render leaves
    it; the brief naming them is the run's `version`."""
    brief = styled._ad()
    concept = _concept(brief, "C1")
    concept["animatic"] = {**{f: f"animatic/{FULL[f]}" for f in FULL}, "default": "9x16", "style": "ink-wash",
                           "preview": {f: {"path": f"animatic/{PREV[f]}", "bytes": n}
                                       for f, n in preview_bytes.items()}}
    renders = run.path / animatic.RENDERS
    renders.mkdir(parents=True, exist_ok=True)
    for f in FULL:
        (renders / FULL[f]).write_bytes(b"F" * 3000)
    for f, n in preview_bytes.items():
        (renders / PREV[f]).write_bytes(b"P" * n)
    (run.path / "04_final" / f"brief_pack_{version}.json").write_text(json.dumps(brief, ensure_ascii=False),
                                                                     encoding="utf-8")
    return brief


def _page(run, got) -> str:  # noqa: F811
    return (run.path / got["folder"] / "index.html").read_text(encoding="utf-8")


def test_the_page_plays_the_preview_and_names_the_full_size_file(run):  # noqa: F811
    _rendered(run, {"9x16": 500, "4x5": 400})
    got = brief_page.build(run)
    served = run.path / got["folder"] / "animatic"
    assert sorted(p.name for p in served.iterdir()) == sorted(PREV.values())   # never the full-size files
    text = _page(run, got)
    assert f'<video src="animatic/{PREV["9x16"]}"' in text and f'data-src="animatic/{PREV["4x5"]}"' in text
    assert f'"animatic/{FULL["9x16"]}"' not in text
    assert f"Full size: {animatic.RENDERS}/{FULL['9x16']}" in text                # where the full-size file is
    assert got["media_dropped"] == []


def test_an_animatic_still_too_big_is_left_out_and_named_as_a_local_file(run, monkeypatch):  # noqa: F811
    """Item 2: the page is built anyway, without the file over the Artifact tool's limit a file; the concept says
    where the local file is, and the other format still plays."""
    monkeypatch.setattr(page, "MAX_FILE_BYTES", 1_000_000)                  # above index.html, below one preview
    _rendered(run, {"9x16": 1_000_001, "4x5": 400})
    got = brief_page.build(run)
    served = run.path / got["folder"] / "animatic"
    assert sorted(p.name for p in served.iterdir()) == [PREV["4x5"]]
    assert got["media_dropped"] == [f"C1 9x16: {animatic.RENDERS}/{FULL['9x16']}"]
    text = _page(run, got)
    assert f"Local file: {animatic.RENDERS}/{FULL['9x16']}" in text
    assert f'<video src="animatic/{PREV["4x5"]}"' in text and PREV["9x16"] not in text   # 4:5 plays first now
    row = next(r for r in manifest.rows(run) if r["file"] == got["folder"])
    assert json.loads(row["params"])["media_dropped"] == got["media_dropped"]

    _rendered(run, {"9x16": 1_000_001, "4x5": 1_500_000}, "v03")                    # neither fits: no player at all
    got = brief_page.build(run)
    text = _page(run, got)
    section = text.split('id="c1" class="concept"', 1)[1].split("</section>", 1)[0]
    assert "<video" not in section and section.count("Local file: ") == 2
    phone = text.split('<div class="phones">', 1)[1].split('href="#c2"', 1)[0]
    assert "<video" not in phone and "Local file: " in phone
    assert len(got["media_dropped"]) == 2


def test_a_page_over_the_limits_for_another_reason_still_stops(run, monkeypatch):  # noqa: F811
    from tm.stops import Stop

    _rendered(run, {"9x16": 500, "4x5": 400})
    monkeypatch.setattr(page, "MAX_FILES", 1)
    with pytest.raises(Stop) as stop:
        brief_page.build(run)
    assert "too big to publish" in str(stop.value) and "animatic.formats" not in str(stop.value)


def test_the_new_lines_are_in_english_and_polish():
    from tm import i18n

    for key in ("brief.animatic_full_file", "brief.animatic_local_file"):
        assert "{path}" in i18n.english()[key]
        assert "{path}" in i18n._shipped("pl")[key]
