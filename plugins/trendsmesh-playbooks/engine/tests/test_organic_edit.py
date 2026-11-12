"""Organic video's edit (issue 89): the AI shot's own sound under a voiceover, the two text layers (captions from the
voiceover's word times, overlays in a box) in a style the user approved, and the G1 check that the edit follows it.
The real renders run with `-m video`; everything here runs in the light suite."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from conftest import remotion_cache, video_asked_for

from tm import config, organic_config, organic_edit, render, state
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.tools import _common as common

sys.path.insert(0, str(Path(__file__).parent / "tools"))


@pytest.fixture
def ov(tmp_path):
    """A production run of organic video with one AI take (a Replicate record of a video) and a voiceover."""
    run = RunFolder.create(tmp_path / "ws" / "runs" / "03" / "x", "m5", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    s = state.load(run)
    s.organic = {"proposal": "M5", "channel": "exampleedu"}
    state.save(run, s)
    config.save(run, organic_config.defaults())
    wip = run.path / "03_wip"
    (wip / "take_v01.run.json").write_text(json.dumps(
        {"model": "minimax/h3", "status": "done", "prediction_id": "p1", "outputs": ["take_v01_0.mp4"]}),
        encoding="utf-8")
    (wip / "take_v01_0.mp4").write_bytes(b"an AI take")
    (wip / "anim.mp4").write_bytes(b"an animation, not a take")
    (wip / "vo_v01.mp3").write_bytes(b"the voiceover")
    return run


def _props(run, name="edit_v01", **extra):
    props = {"width": 1080, "height": 1920, "fps": 24, "keepAudio": True,
             "segments": [{"src": "03_wip/take_v01_0.mp4", "start": 0, "end": 4, "volume": 0.2},
                          {"src": "03_wip/anim.mp4", "start": 0, "end": 3}],
             "audioTracks": [{"src": "03_wip/vo_v01.mp3", "from": 0.3, "volume": 1}], "captions": [], **extra}
    path = run.path / "03_wip" / f"{name}.props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    return path, props


# --- the AI shot's own sound -------------------------------------------------------------------------

def test_an_ai_shot_is_muted_under_a_voiceover(ov):
    _, props = _props(ov)
    gap = organic_edit.shot_audio_gap(ov, props)
    assert gap and "segment 1 (03_wip/take_v01_0.mp4)" in gap and "keepAudio" in gap and "--keep-shot-audio" in gap
    assert "anim.mp4" not in gap                                   # only the AI shot's sound is muted
    assert organic_edit.shot_audio_gap(ov, {**props, "keepAudio": False}) is None
    muted = [{**props["segments"][0], "volume": 0}, props["segments"][1]]
    assert organic_edit.shot_audio_gap(ov, {**props, "segments": muted}) is None
    assert organic_edit.shot_audio_gap(ov, {**props, "audioTracks": []}) is None   # no voiceover: the take talks


def test_a_sped_up_copy_of_a_take_is_still_the_ai_shot(ov):
    fast = ov.path / "03_wip" / "take_v01_0_speed117.mp4"
    fast.write_bytes(b"sped up")
    common.record(ov, fast, "tm tool deliver speed", "03_wip/take_v01_0.mp4", params={"factor": 1.17})
    _, props = _props(ov)
    props["segments"][0]["src"] = "03_wip/take_v01_0_speed117.mp4"
    assert "take_v01_0_speed117.mp4" in organic_edit.shot_audio_gap(ov, props)


def _ns(run, props, *extra):
    import argparse

    p = argparse.ArgumentParser()
    render._setup_cli(p)
    return p.parse_args(["video", "--run", str(run.path), "--comp", "OrganicCaptions", "--props", str(props),
                         "--json", *extra])



def _plugin_folders(run, monkeypatch):
    """The plugin's folders as a session's set-up names them (~/.trendsmesh/paths.json exists only on a machine
    where the plugin ran, never on CI): the plugin itself, and a data folder of the test's own."""
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(run.path.parent / "plugin-data"))

def test_tm_render_refuses_the_shot_sound_under_a_voiceover_before_anything_runs(ov, monkeypatch, capsys):
    _plugin_folders(ov, monkeypatch)
    path, _ = _props(ov)
    ran = []
    monkeypatch.setattr(render, "_need_setup", lambda: ran.append("setup"))
    monkeypatch.setattr(render, "_sh", lambda *a, **k: ran.append("remotion"))
    assert render._run_cli(_ns(ov, path)) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error" and "voiceover" in out["message"] and ran == []
    # the user asked to keep it: the render goes on, and its record says so
    monkeypatch.setattr(render, "_sync_src", lambda: None)

    def fake(argv, cwd, what):
        part = next(a for a in argv if a.endswith(".mp4"))
        open(part, "wb").write(b"rendered")

    monkeypatch.setattr(render, "_sh", fake)
    assert render._run_cli(_ns(ov, path, "--keep-shot-audio")) == 0
    rows = [r for r in __import__("tm").manifest.rows(ov) if r["model"] == "remotion render"]
    assert json.loads(rows[-1]["params"])["keep_shot_audio"] is True


# --- the composition (real renders, -m video) ---------------------------------------------------------

def _picture(run, name, colour):
    import subprocess

    from _media import ffmpeg

    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi", "-i", f"color=c={colour}:s=1080x1920",
                    "-frames:v", "1", str(run.path / "03_wip" / name)], check=True)
    return [{"src": f"03_wip/{name}", "start": 0, "end": 2}]


def _still(run, name, captions, segments=None, frame=6):
    """One frame of OrganicCaptions (after the text's pop, frame 6) over a black picture (or the given segments) as
    RGB pixels, 1080×1920."""
    import subprocess

    from _media import ffmpeg

    segments = _picture(run, "black.png", "black") if segments is None else segments
    props = run.path / "03_wip" / f"{name}.props.json"
    props.write_text(json.dumps({"width": 1080, "height": 1920, "fps": 24, "segments": list(segments),
                                 "language": "pl", "captions": captions}, ensure_ascii=False), encoding="utf-8")
    png = render.still(run, "OrganicCaptions", props, frame, run.path / "03_wip" / f"{name}.png")
    return subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(png), "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-"], capture_output=True, check=True).stdout


def _box(px, test, step=2):
    """(left, top, right, bottom) of the pixels where test(r, g, b) holds."""
    hits = [(x, y) for y in range(0, 1920, step) for x in range(0, 1080, step)
            if test(*px[(y * 1080 + x) * 3:(y * 1080 + x) * 3 + 3])]
    assert hits, "nothing drawn"
    return min(x for x, _ in hits), min(y for _, y in hits), max(x for x, _ in hits), max(y for _, y in hits)


def _white(r, g, b):
    return min(r, g, b) > 220


@pytest.fixture
def drawn(request, tmp_path, tmp_path_factory, monkeypatch):
    import shutil

    if not video_asked_for(request.config):
        pytest.skip("the real render runs with -m video (pixi run -e dev-full test-video)")
    if not shutil.which("node"):
        pytest.skip("Node is not on PATH (run: pixi run -e dev-full test-video)")
    cache = remotion_cache(tmp_path_factory)
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setattr(render.paths, "data_dir", lambda: cache)
    monkeypatch.setattr(render, "_prefix", lambda: [])
    monkeypatch.setattr(render.envtiers, "installed", lambda tier: True)
    render.setup()
    return RunFolder.create(tmp_path / "Napisy Łukasz", "napisy", date(2026, 11, 12))


LONG = "Ten jeden nawyk zmienia twoje poranki na zawsze i nikt o tym nie mówi"


@pytest.mark.video
def test_a_hook_box_moves_up_and_widens_to_the_safe_zone(drawn):
    """Issue 89: `offsetY` moves the text up off a face (place top started at y 260 with no offset) and `width` takes
    the column up to the safe zone (x 90 to 880; the box was held to 680 px)."""
    hook = {"from": 0, "to": 1, "text": LONG, "style": "hook", "place": "top", "fontSize": 58}
    x0, y0, x1, _ = _box(_still(drawn, "plain", [hook]), _white)
    assert y0 >= 255 and x1 - x0 <= 682
    x0, y0, x1, _ = _box(_still(drawn, "moved", [{**hook, "offsetY": -120, "width": 790}]), _white)
    assert 130 <= y0 <= 150                          # 260 - 120
    assert x1 - x0 > 740 and x0 >= 88 and x1 <= 882  # wider, still inside the safe zone


@pytest.mark.video
def test_the_lines_follow_the_font_size(drawn):
    hook = {"from": 0, "to": 1, "text": LONG, "style": "hook", "width": 790}
    _, small_top, _, small_bottom = _box(_still(drawn, "small", [{**hook, "fontSize": 44}]), _white)
    _, big_top, _, big_bottom = _box(_still(drawn, "big", [{**hook, "fontSize": 88}]), _white)
    assert big_bottom - big_top > 2.5 * (small_bottom - small_top)   # twice the size, more lines


@pytest.mark.video
def test_a_caption_sits_at_the_bottom_with_an_outline_and_the_spoken_word_lit(drawn):
    """The captions layer: white letters with a black outline at the bottom of the safe zone (y 1540), the word being
    spoken in the highlight colour."""
    words = [{"text": "Ten", "from": 0.0, "to": 0.4}, {"text": "jeden", "from": 0.4, "to": 0.9},
             {"text": "nawyk", "from": 0.9, "to": 1.5}]
    cap = {"from": 0, "to": 1.5, "text": "Ten jeden nawyk", "style": "caption", "highlight": "#FFE14D",
           "words": words}
    grey = _picture(drawn, "grey.png", "0x808080")
    px = _still(drawn, "cap", [cap], grey, frame=12)          # 0.5 s: "jeden" is spoken
    _, y0, _, y1 = _box(px, _white)
    assert 1380 < y0 and y1 <= 1545                           # at the bottom of the safe zone
    assert _box(px, lambda r, g, b: max(r, g, b) < 30)        # the outline (the picture is grey)
    lx0, _, lx1, _ = _box(px, lambda r, g, b: r > 220 and g > 190 and b < 120)   # the lit word, yellow
    wx0, _, wx1, _ = _box(px, _white)
    assert wx0 < lx0 and lx1 < wx1                            # the middle word of three


# --- the text style, its look and its approval ---------------------------------------------------------

@pytest.fixture
def remotion(monkeypatch, tmp_path):
    """tm render without Node: the Remotion call writes its output file, everything else (the record) is real."""
    monkeypatch.setattr(render, "_need_setup", lambda: None)
    monkeypatch.setattr(render, "_sync_src", lambda: None)
    monkeypatch.setattr(render.video_fonts, "check", lambda *a, **k: None)   # the font tables need the real setup
    monkeypatch.setattr(render, "work_dir", lambda: tmp_path / "remotion")
    (tmp_path / "remotion").mkdir()

    def fake(argv, cwd, what):
        part = next(a for a in argv if a.endswith((".png", ".mp4")) and "/." in a.replace("\\", "/"))
        open(part, "wb").write(b"\x89PNG rendered" if part.endswith(".png") else b"rendered")

    monkeypatch.setattr(render, "_sh", fake)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _frame(run):
    (run.path / "03_wip" / "frame_v01_0.png").write_bytes(b"\x89PNG the first frame")
    return "03_wip/frame_v01_0.png"


def test_a_style_with_wrong_values_is_refused():
    good = organic_edit.default_style(caption="Ten jeden nawyk", overlay="3 sekundy")
    assert organic_edit.style_problems(good) == []
    bad = json.loads(json.dumps(good))
    bad["captions"].update({"color": "white", "fontSize": 300, "words": [5, 2]})
    bad["overlays"]["width"] = 900
    said = " | ".join(organic_edit.style_problems(bad))
    assert "captions.color" in said and "captions.fontSize" in said and "captions.words" in said
    assert "overlays.width" in said and "790" in said
    assert organic_edit.style_problems({"captions": {}}) != []


def test_the_look_is_a_still_of_both_layers_on_the_first_frame(ov, remotion, capsys):
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(ov.path), "--picture", _frame(ov),
                     "--caption", "Ten jeden nawyk zmienia poranki", "--overlay", "Jeden nawyk")
    assert code == 0, out
    assert out["style"] == "03_wip/text_style_v01.json" and out["still"].startswith("03_wip/text_look_v01")
    style = json.loads((ov.path / out["style"]).read_text(encoding="utf-8"))
    assert style["sample"] == {"caption": "Ten jeden nawyk zmienia poranki", "overlay": "Jeden nawyk"}
    props = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))
    assert props["segments"] == [{"src": "03_wip/frame_v01_0.png", "start": 0, "end": 2}]
    overlay, caption = props["captions"]
    assert (overlay["style"], overlay["place"], overlay["text"]) == ("hook", "top", "Jeden nawyk")
    assert (caption["style"], caption["place"]) == ("caption", "bottom")
    assert [w["text"] for w in caption["words"]] == ["Ten", "jeden", "nawyk", "zmienia", "poranki"]
    assert props["textStyle"]["file"] == "03_wip/text_style_v01.json"
    row = [r for r in __import__("tm").manifest.rows(ov) if r["file"] == out["still"]][0]
    assert row["model"] == "remotion still" and json.loads(row["params"])["composition"] == "OrganicCaptions"
    # the user's changes: a new style version, its own look
    style["captions"]["fontSize"] = 72
    (ov.path / "03_wip" / "text_style_v02.json").write_text(json.dumps(style), encoding="utf-8")
    code, out = _cli(capsys, "organic", "text", "look", "--run", str(ov.path), "--picture", _frame(ov),
                     "--style", "03_wip/text_style_v02.json")
    assert code == 0 and out["style"] == "03_wip/text_style_v02.json"
    assert json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))["captions"][1]["fontSize"] == 72


def test_the_style_is_approved_after_its_look_and_only_its_latest_version(ov, remotion, capsys):
    style = ov.path / "03_wip" / "text_style_v01.json"
    style.write_text(json.dumps(organic_edit.default_style(caption="a b c", overlay="x")), encoding="utf-8")
    approve = ("organic", "text", "approve", "--run", str(ov.path), "--style", "03_wip/text_style_v01.json",
               "--note", "tak, ale większe")
    code, out = _cli(capsys, *approve)
    assert code == 2 and "tm organic text look" in out["message"]        # never approved unseen
    assert _cli(capsys, "organic", "text", "look", "--run", str(ov.path), "--picture", _frame(ov), "--style",
                "03_wip/text_style_v01.json")[0] == 0
    code, out = _cli(capsys, *approve)
    assert code == 0, out
    entry = state.load(ov).checked["text_style"]
    assert (entry["file"], entry["by"], entry["note"]) == ("03_wip/text_style_v01.json", "user", "tak, ale większe")
    assert organic_edit.approved_style(ov)[0] == "03_wip/text_style_v01.json"
    (ov.path / "03_wip" / "text_style_v02.json").write_text(style.read_text(encoding="utf-8"), encoding="utf-8")
    assert organic_edit.approved_style(ov) is None                        # a newer version is not approved yet
    code, out = _cli(capsys, "organic", "text", "approve", "--run", str(ov.path), "--style",
                     "03_wip/text_style_v01.json", "--note", "x")
    assert code == 2 and "text_style_v02.json" in out["message"]          # only the latest is approved


# --- the captions layer ------------------------------------------------------------------------------

WORDS = [("Ten", 0.0, 0.2), ("jeden", 0.25, 0.5), ("nawyk", 0.55, 0.9), ("zmienia", 0.95, 1.3),
         ("poranki.", 1.35, 1.8), ("Serio,", 2.6, 2.9), ("sprawdź", 2.95, 3.3), ("sam", 3.35, 3.5),
         ("dziś", 3.55, 3.8), ("wieczorem", 3.85, 4.3), ("koniecznie", 4.35, 4.9)]


def test_words_are_grouped_two_to_four():
    """A group closes at 4 words, at a sentence's end, at a comma once it has 2 words, and before a pause."""
    groups = organic_edit.caption_groups([{"word": w, "start": s, "end": e} for w, s, e in WORDS], 2, 4)
    assert [" ".join(w["word"] for w in g) for g in groups] == [
        "Ten jeden nawyk zmienia", "poranki.", "Serio, sprawdź sam dziś", "wieczorem koniecznie"]
    spaced = [{"word": w, "start": s, "end": e} for w, s, e in [("a", 0, 0.2), ("b", 0.9, 1.1), ("c", 1.15, 1.3)]]
    assert [len(g) for g in organic_edit.caption_groups(spaced, 2, 4)] == [1, 2]   # the pause after "a"
    commas = [{"word": w, "start": i, "end": i + 0.1} for i, w in enumerate(["raz,", "dwa,", "trzy", "cztery"])]
    assert [len(g) for g in organic_edit.caption_groups([{**w, "start": w["start"] / 10, "end": w["end"] / 10}
                                                         for w in commas], 2, 4)] == [2, 2]


def _approved(ov, capsys, **changes):
    style = organic_edit.default_style(caption="a b", overlay="x")
    for layer, values in changes.items():
        style[layer].update(values)
    (ov.path / "03_wip" / "text_style_v01.json").write_text(json.dumps(style), encoding="utf-8")
    assert _cli(capsys, "organic", "text", "look", "--run", str(ov.path), "--picture", _frame(ov), "--style",
                "03_wip/text_style_v01.json")[0] == 0
    assert _cli(capsys, "organic", "text", "approve", "--run", str(ov.path), "--style", "03_wip/text_style_v01.json",
                "--by", "rule", "--note", "the default style")[0] == 0
    return style


def _words_file(ov):
    path = ov.path / "03_wip" / "vo_v01.words.json"
    path.write_text(json.dumps([{"word": w, "start": s, "end": e} for w, s, e in WORDS]), encoding="utf-8")
    return "03_wip/vo_v01.words.json"


def test_captions_come_from_the_voiceovers_word_times_in_the_approved_style(ov, remotion, capsys):
    path, props = _props(ov, keepAudio=False, captions=[
        {"from": 0, "to": 2, "text": "Jeden nawyk", "style": "hook"},
        {"from": 2.5, "to": 4, "text": "87%", "style": "note", "place": "middle"},
        {"from": 1, "to": 2, "text": "a hand-written caption", "style": "caption"}])
    words = _words_file(ov)
    code, out = _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_v01.props.json",
                     "--words", words)
    assert code == 2 and "tm organic text look" in out["message"]          # the style is approved first
    style = _approved(ov, capsys, captions={"highlight": "#FFE14D"})
    code, out = _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_v01.props.json",
                     "--words", words)
    assert code == 0, out
    assert out["props"] == "03_wip/edit_v02.props.json" and out["offset"] == 0.3   # the voiceover's `from`
    made = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))
    assert made["textStyle"]["file"] == "03_wip/text_style_v01.json"
    overlays = [c for c in made["captions"] if c["style"] != "caption"]
    captions = [c for c in made["captions"] if c["style"] == "caption"]
    assert [o["text"] for o in overlays] == ["Jeden nawyk", "87%"]
    assert all(o["style"] == "hook" and o["place"] == style["overlays"]["place"]
               and o["fontSize"] == style["overlays"]["fontSize"] for o in overlays)
    assert "a hand-written caption" not in [c["text"] for c in captions]   # the layer is made again
    assert captions[0]["text"] == "Ten jeden nawyk zmienia" and captions[0]["from"] == 0.3
    assert captions[0]["words"][1] == {"text": "jeden", "from": 0.55, "to": 0.8}
    assert all(c["highlight"] == "#FFE14D" and c["place"] == "bottom" for c in captions)
    assert all(a["to"] <= b["from"] for a, b in zip(captions, captions[1:]))  # one block at a time
    assert json.loads(path.read_text(encoding="utf-8")) == props            # the given props stay as written


def test_more_than_three_overlays_are_refused(ov, remotion, capsys):
    hooks = [{"from": i, "to": i + 1, "text": f"line {i}", "style": "hook"} for i in range(4)]
    _props(ov, keepAudio=False, captions=hooks)
    _approved(ov, capsys)
    code, out = _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_v01.props.json",
                     "--words", _words_file(ov))
    assert code == 2 and "4 overlays" in out["message"] and "the hook, the key number and the closing question" in out[
        "message"]
    assert not (ov.path / "03_wip" / "edit_v02.props.json").exists()


def test_a_takes_transcript_is_placed_through_the_cuts(ov, remotion, capsys):
    """A talking take: its transcript's words are placed where the edit cuts the take (a cut from 1 s to 4 s at the
    start of the edit); words outside the cuts are left out."""
    _props(ov, keepAudio=True, audioTracks=[], segments=[{"src": "03_wip/take_v01_0.mp4", "start": 1, "end": 4}])
    _approved(ov, capsys)
    transcript = ov.path / "02_research" / "transcript_v01.json"
    transcript.write_text(json.dumps({"segments": [{"words": [
        {"word": " Za", "start": 0.2, "end": 0.5}, {"word": " chwilę", "start": 1.2, "end": 1.6},
        {"word": " zobaczysz", "start": 1.7, "end": 2.2}, {"word": " koniec.", "start": 4.5, "end": 5.0}]}]}),
        encoding="utf-8")
    code, out = _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_v01.props.json",
                     "--words", "02_research/transcript_v01.json", "--source", "03_wip/take_v01_0.mp4")
    assert code == 0, out
    made = json.loads((ov.path / out["props"]).read_text(encoding="utf-8"))
    assert [c["text"] for c in made["captions"]] == ["chwilę zobaczysz"]
    assert made["captions"][0]["from"] == pytest.approx(0.2)


# --- G1: the edit follows the approved style ----------------------------------------------------------

def _final_from(ov, props):
    render_rel = "03_wip/edit_v09_organiccaptions_v01.mp4"
    out = ov.path / render_rel
    out.write_bytes(b"rendered")
    common.record(ov, out, "03_wip/edit_v09.props.json", None, params={"composition": "OrganicCaptions",
                                                                         "props": props}, model="remotion render")
    final = ov.path / "04_final" / "M5_final_v01.mp4"
    final.write_bytes(b"final")
    common.record(ov, final, "tm tool deliver finish", render_rel)


def test_g1_needs_the_captions_in_the_approved_style(ov, remotion, capsys):
    from tm import flow, stepchecks

    assert "text_followed" in {s.id: s for s in flow.steps(ORGANIC_VIDEO)}["G1"].requires
    assert stepchecks.NAMES["text_followed"] == "tm.organic_edit:text_gap"
    assert organic_edit.text_gap(ov) is None                                # no final yet: final_checked says so
    _, props = _props(ov, keepAudio=False)
    _final_from(ov, props)
    assert "captions under the voiceover" in organic_edit.text_gap(ov)
    _final_from(ov, {**props, "captions": [{"from": 0, "to": 1, "text": "x", "style": "caption"}]})
    assert "approved" in organic_edit.text_gap(ov)
    _approved(ov, capsys)
    assert "tm organic captions" in organic_edit.text_gap(ov)               # written by hand, not in the style
    assert _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_v01.props.json",
                "--words", _words_file(ov))[0] == 0
    _final_from(ov, json.loads((ov.path / "03_wip" / "edit_v02.props.json").read_text(encoding="utf-8")))
    assert organic_edit.text_gap(ov) is None and stepchecks.run("text_followed", ov) is None
    _final_from(ov, {**props, "audioTracks": [], "keepAudio": True})       # a talking take with no text: fine
    assert organic_edit.text_gap(ov) is None


def test_the_next_props_keep_the_edits_own_name(ov, remotion, capsys):
    _props(ov, name="edit_M5_v01", keepAudio=False)
    _approved(ov, capsys)
    code, out = _cli(capsys, "organic", "captions", "--run", str(ov.path), "--props", "03_wip/edit_M5_v01.props.json",
                     "--words", _words_file(ov))
    assert code == 0 and out["props"] == "03_wip/edit_M5_v02.props.json"


@pytest.mark.video
def test_a_real_cover_is_measured_and_moved(drawn, monkeypatch, capsys):
    """tm tool cover_fit with the real Remotion drafts (issue 89): a face given by hand where the hook sits (the top of
    the safe zone) moves the text below it, and the cover PNG is drawn from the fitted props."""
    pytest.importorskip("cv2")
    from tm.tools import cover_fit

    s = state.load(drawn)
    s.organic = {"proposal": "M5"}
    state.save(drawn, s)
    segments = _picture(drawn, "frame.png", "0x406080")
    path = drawn.path / "03_wip" / "cover_M5_v01.props.json"
    path.write_text(json.dumps({"width": 1080, "height": 1920, "fps": 24, "segments": segments, "language": "pl",
                                "captions": [{"from": 0, "to": 2, "text": "Jeden nawyk", "style": "hook",
                                              "place": "top", "fontSize": 72}]}), encoding="utf-8")
    capsys.readouterr()
    code = cover_fit.main(["--run", str(drawn.path), "--props", "03_wip/cover_M5_v01.props.json", "--frame", "6",
                           "--face", "380,300,320,360", "--json"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0, out
    assert out["changes"] and out["changes"][0].startswith("moved down")
    assert out["outputs"] == ["04_final/kits/cover_M5_v01.png"]
    fitted = json.loads((drawn.path / out["props"]).read_text(encoding="utf-8"))["captions"][0]
    assert 260 + fitted["offsetY"] >= 660                     # below the head (y 120 to 660)


def test_the_images_page_shows_the_latest_text_look(ov, remotion, capsys):
    from tm import organic_gates, organic_pages

    t = organic_pages.gate_words("en")
    assert organic_gates._text_look(ov, t) is None
    for n in (1, 2):
        assert _cli(capsys, "organic", "text", "look", "--run", str(ov.path), "--picture", _frame(ov),
                    "--caption", f"wersja {n} napisów", "--overlay", "Hak")[0] == 0
    ref = organic_gates._text_look(ov, t)
    assert ref == {"src": "03_wip/text_look_v02.png", "caption": t["cap_text_style"]}
    assert "accept" in t["cap_text_style"].lower()
    assert organic_pages.gate_words("pl")["cap_text_style"] != t["cap_text_style"]   # translated
