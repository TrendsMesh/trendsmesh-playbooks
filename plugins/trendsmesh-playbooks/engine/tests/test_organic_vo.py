"""#88 point 4: the recorded voiceover against the pack's line times and the take's cuts (`tm organic vo-sync`, and
the paid take's guard). The times are the owner's run: planned 0–3.5 / 3.5–7.5 / 7.5–13.5 s, recorded 0–3.16 /
3.28–6.72 / 6.76–11.84 s, the take's prompt still cutting at 3.5 and 7.5 s."""

import json
from datetime import date
from pathlib import Path

import pytest

from tm import organic_pack, organic_specs, organic_vo
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

LINES = ["Pies kręci się w kółko przed snem.", "Wilki tak ubijały trawę w legowisku.",
         "Dziś robi to na dywanie, z tego samego powodu."]
PLANNED = [[0, 3.5], [3.5, 7.5], [7.5, 13.5]]
RECORDED = [(0.0, 3.16), (3.28, 6.72), (6.76, 11.84)]
PROMPT = ("[0 to 3.5 seconds] Close-up of a dog circling on a bed. [3.5 to 7.5 seconds] Hard cut to wolves in tall "
          "grass. [7.5 to 13.5 seconds] Hard cut to the dog on a rug, settling down.")


def _pack(seconds=14.0, route="elevenlabs_narrator", sections=None):
    lines = [{"n": i + 1, "text": t, "speaker": "narrator", "shot": "s", "at": at} for i, (t, at) in
             enumerate(zip(LINES, PLANNED))]
    return {"script": {"lines": lines, "words": sum(len(t.split()) for t in LINES), "seconds": seconds},
            "speech": {"route": route}, "sections": sections or [],
            "stages": [{"stage": "images", "items": [{"name": "frame", "model": "openai/gpt-image-2", "images": 1}]},
                       {"stage": "video", "items": [{"name": "take", "model": "minimax/h3", "seconds": 14}]}]}


def _words(times=RECORDED):
    """Each line's words spread evenly over its recorded span."""
    out = []
    for text, (start, end) in zip(LINES, times):
        parts = text.split()
        step = (end - start) / len(parts)
        out += [{"word": w, "start": round(start + i * step, 3), "end": round(start + (i + 1) * step, 3)}
                for i, w in enumerate(parts)]
    return out


def test_brackets_of_the_timed_shot_lists():
    assert organic_vo.brackets(PROMPT) == [(0, 3.5), (3.5, 7.5), (7.5, 13.5)]
    assert organic_vo.brackets("[00:00-00:02] a [00:02-00:05.5] b") == [(0, 2), (2, 5.5)]
    assert organic_vo.brackets("[3 to 9 seconds] x [0 to 3 seconds] y") == [(0, 3), (3, 9)]
    assert organic_vo.brackets("no shot list") == []


def test_the_owners_run_gets_new_line_times_and_cuts():
    res = organic_vo.compare(_pack(), _words(), {}, PROMPT)
    assert res["matched"] and not res["in_sync"]
    assert [r["recorded"] for r in res["lines"]] == [[0.0, 3.16], [3.28, 6.72], [6.76, 11.84]]
    assert [r["moved"] for r in res["lines"]] == [True, True, True]          # 3.5 vs 3.16 is 0.34 s off
    assert res["proposed"]["at"] == {"1": [0.0, 3.16], "2": [3.28, 6.72], "3": [6.76, 11.84]}
    assert [(c["prompt_s"], c["line"], c["moved"]) for c in res["cuts"]] == [(3.5, 2, False), (7.5, 3, True)]
    assert res["proposed"]["cuts"] == [6.74]                                  # the middle of the pause before line 3
    text = organic_vo.summary(res, "03_wip/audio/vo.words.json")
    assert "7.5 s → 6.74 s (line 3 starts at 6.76 s)" in text and "free" in text


def test_a_voice_on_the_plan_is_in_sync():
    on_plan = [(0.05, 3.4), (3.55, 7.4), (7.6, 13.3)]
    res = organic_vo.compare(_pack(), _words(on_plan), {"qa": {"wps_min": 1.0}}, PROMPT)
    assert res["in_sync"] and res["proposed"] == {"at": {}, "cuts": []}
    assert "follows the pack" in organic_vo.summary(res, "w.json")


def test_the_pace_check_covers_the_elevenlabs_voice():
    """`qa.wps_min` (2.8 by default) now holds the recorded voice too: line 3's 8 words over 5.08 s is 1.57."""
    res = organic_vo.compare(_pack(), _words(), {}, None)
    assert {x["n"] for x in res["slow"]} >= {3}
    assert res["cuts"] == []
    assert organic_vo.compare(_pack(), _words(), {"qa": {"wps_min": 1.0}}, None)["slow"] == []


def test_a_voice_longer_than_the_takes_says_re_plan():
    res = organic_vo.compare(_pack(seconds=11.0), _words(), {}, None)
    assert res["longer"] and "re-plan the pack (E2)" in organic_vo.summary(res, "w.json")


def test_words_that_do_not_match_the_lines_compare_nothing():
    res = organic_vo.compare(_pack(), _words()[:-1], {}, PROMPT)
    assert not res["matched"]
    assert "holds 21 recorded words, and the pack's said lines hold 22" in organic_vo.summary(res, "w.json")


def test_an_offset_takes_a_later_sections_take():
    later = PROMPT.replace("[0 to 3.5", "[0 to 0.5").replace("[3.5 to 7.5", "[0.5 to 4.5").replace(
        "[7.5 to 13.5", "[4.5 to 10.5")                                       # the same cuts, the take starts at 3 s
    res = organic_vo.compare(_pack(), _words(), {}, later, offset=3.0)
    assert [(c["prompt_s"], c["line"]) for c in res["cuts"]] == [(0.5, 2), (4.5, 3)]
    assert res["proposed"]["cuts"] == [3.74]                                  # in the take's own time


@pytest.fixture
def ov(tmp_path, monkeypatch):
    (tmp_path / "ws").mkdir()
    run = RunFolder.create(tmp_path / "ws", "dog", date(2026, 11, 12), playbook=ORGANIC_VIDEO)
    pack = _pack()
    monkeypatch.setattr(organic_pack, "checked_pack", lambda r: pack)
    audio = run.path / "03_wip" / "audio"
    audio.mkdir(parents=True)
    (audio / "vo.words.json").write_text(json.dumps(_words()), encoding="utf-8")
    return run, pack


def test_vo_sync_cli_reads_only(ov, capsys):
    run, _ = ov
    spec = run.path / "03_wip" / "take_v01.json"
    spec.write_text(json.dumps({"model": "minimax/h3", "input": {"prompt": PROMPT}}), encoding="utf-8")
    before = sorted(p.relative_to(run.path) for p in run.path.rglob("*"))
    assert main(["organic", "vo-sync", "--run", str(run.path), "--words", "03_wip/audio/vo.words.json",
                 "--spec", "03_wip/take_v01.json", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["proposed"]["cuts"] == [6.74] and out["words"] == "03_wip/audio/vo.words.json"
    assert sorted(p.relative_to(run.path) for p in run.path.rglob("*")) == before   # nothing written
    spec.write_text(json.dumps({"model": "minimax/h3", "input": {"prompt": "no list"}}), encoding="utf-8")
    assert main(["organic", "vo-sync", "--run", str(run.path), "--words", "03_wip/audio/vo.words.json",
                 "--spec", "03_wip/take_v01.json", "--json"]) == 1
    assert "no timed shot list" in json.loads(capsys.readouterr().out)["message"]


def test_the_take_guard_refuses_cuts_off_the_voice_before_paying(ov):
    run, pack = ov
    spec = {"model": "minimax/h3", "input": {"prompt": PROMPT}}
    said = organic_vo.take_gap(run, pack, spec, "take")
    assert said and "7.5 s → 6.74 s" in said and "03_wip/audio/vo.words.json" in said
    fixed = {"model": "minimax/h3", "input": {"prompt": PROMPT.replace("[3.5 to 7.5", "[3.2 to 6.7").replace(
        "[7.5 to 13.5", "[6.7 to 13.5")}}
    assert organic_vo.take_gap(run, pack, fixed, "take") is None
    assert organic_vo.take_gap(run, pack, spec, "frame") is None              # an image item: no cuts
    assert organic_vo.take_gap(run, {**pack, "speech": {"route": "h3_native"}}, spec, "take") is None
    assert organic_vo.take_gap(run, {**pack, "sections": [{"id": "S1"}]}, spec, "take") is None
    assert organic_vo.take_gap(run, pack, {"model": "minimax/h3", "input": {}}, "take") is None


def test_the_guard_calls_the_check(ov, monkeypatch):
    """organic_specs.guard runs take_gap after the spec's own checks and before the redo and money rules."""
    run, _ = ov
    seen = []
    monkeypatch.setattr(organic_specs, "check", lambda *a, **k: [])
    monkeypatch.setattr(organic_specs.organic_vo, "take_gap", lambda *a: seen.append(a[3]) or "cuts off the voice.")
    spec = run.path / "03_wip" / "take_v01.json"
    spec.write_text(json.dumps({"model": "minimax/h3", "input": {"prompt": PROMPT}}), encoding="utf-8")
    said = organic_specs.guard(run, ["--run", str(run.path), str(spec), "--name", "take", "--cost", "1"])
    assert seen == ["take"] and said.startswith("cuts off the voice.") and "Nothing was run or spent" in said
