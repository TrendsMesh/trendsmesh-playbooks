"""tm tool take_qa: QA of a generated take, on a clip made here with ffmpeg (two framings, cut A-B-A, and a tone).

The transcript runs through faster-whisper when a model is already in the plugin's data folder; with none cached
it is replaced here (the test never downloads a model), and the rest of the QA still runs."""

from __future__ import annotations

import json
import subprocess

import pytest
from _media import ffmpeg

from tm import organic_config, tts_models
from tm.tools import _common, take_qa, transcribe

pytest.importorskip("numpy")
pytest.importorskip("scenedetect")

SHOT_S = 1.5


def _two_shot_clip(path):
    """4.5 s at 25 fps, 360x640: test pattern, a plain navy frame, the test pattern again; a 440 Hz tone."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shot_a = f"testsrc2=size=360x640:rate=25:duration={SHOT_S}"
    shot_b = f"color=c=navy:size=360x640:rate=25:duration={SHOT_S}"
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", shot_a, "-f", "lavfi", "-i", shot_b, "-f", "lavfi", "-i", shot_a,
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={3 * SHOT_S}",
                    "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                   check=True)
    return path


def qa_duration(run) -> float:
    return float(_common.probe(run.path / "03_wip" / "take_v01_0.mp4")["duration"])


def _cached_whisper() -> str | None:
    """A Whisper model already in the plugin's data folder, or None (nothing is downloaded)."""
    try:
        from faster_whisper.utils import download_model

        from tm.tools import _common

        root = str(_common.models_dir("whisper"))
    except (ImportError, RuntimeError, OSError):
        return None
    for name in ("small", transcribe.DEFAULT_MODEL):
        try:
            download_model(name, local_files_only=True, cache_dir=root)
            return name
        except Exception:  # noqa: BLE001 - not cached (huggingface_hub raises its own errors)
            continue
    return None


@pytest.mark.tools
def test_take_qa_on_generated_clip(run, monkeypatch, capsys):
    take = _two_shot_clip(run.path / "03_wip" / "take_v01_0.mp4")
    script = run.path / "03_wip" / "script_take.txt"
    script.write_text("Niewiele osób wie, że tablet też ma ustawienia rodzica.\n", encoding="utf-8")
    argv = ["--run", str(run.path), "03_wip/take_v01_0.mp4", "--script", "03_wip/script_take.txt", "--lang", "pl",
            "--brackets", "1.5,3.0", "--json"]
    model = _cached_whisper()
    if model:
        argv += ["--model", model]
    else:   # transcription skipped, the levelled second listen too: a tone says nothing anyway
        monkeypatch.setattr(transcribe, "transcribe", lambda media, model, lang: {
            "language": lang, "language_probability": 0.0, "duration": 3 * SHOT_S, "segments": []})
        monkeypatch.setattr(transcribe, "listen", lambda audio, model, lang, *, vad=True, offset=0.0: ([], None))
    assert take_qa.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["outputs"][0] == "03_wip/qa/take_v01_0_qa_v01.json"
    qa = json.loads((run.path / "03_wip" / "qa" / "take_v01_0_qa_v01.json").read_text(encoding="utf-8"))
    assert list(qa) == ["take", "transcript", "match", "words", "speech_seconds", "wps", "tail_silence", "cuts",
                        "cut_offsets", "lufs", "peak", "contact_sheet", "lines", "heard_by"]
    assert qa["heard_by"] == "whisper" and [line["line"] for line in qa["lines"]] == [
        "Niewiele osób wie, że tablet też ma ustawienia rodzica."]
    assert qa["take"] == "03_wip/take_v01_0.mp4"
    assert len(qa["cuts"]) == 2
    assert qa["cuts"] == pytest.approx([SHOT_S, 2 * SHOT_S], abs=0.1)
    assert [o["bracket"] for o in qa["cut_offsets"]] == [1.5, 3.0]
    assert all(abs(o["offset"]) <= 0.1 for o in qa["cut_offsets"])
    assert isinstance(qa["lufs"], float) and -40 < qa["lufs"] < 0   # a tone at -18 dBFS or so
    assert isinstance(qa["peak"], float)
    # no speech in a tone (a real model might still hallucinate a word, so only the match is asserted then)
    assert qa["match"] < organic_config.DEFAULTS["qa"]["transcript_min"]
    if not model:
        assert qa["words"] == 0 and qa["wps"] is None and qa["tail_silence"] == pytest.approx(3 * SHOT_S, abs=0.1)
    assert qa["transcript"] == "03_wip/qa/take_v01_0_transcript_v01.json"
    assert (run.path / qa["transcript"]).is_file()
    sheet = run.path / qa["contact_sheet"]
    assert qa["contact_sheet"] == "03_wip/qa/take_v01_0_contact_v01.png" and sheet.read_bytes()[:4] == b"\x89PNG"
    # the rubric answer: the tone fails the transcript (the line not heard even levelled: not missing yet, check it
    # with Scribe), the cuts are on time
    assert out["rubric"]["fails"] and not out["rubric"]["findings"]
    assert "no line is missing yet" in out["rubric"]["fails"][0]
    assert out["scribe"]["credits"] == tts_models.scribe_credits(qa_duration(run))   # 330 a minute, rounded up
    # a second QA is a new version, never an overwrite
    assert take_qa.main(argv) == 0
    capsys.readouterr()
    assert (run.path / "03_wip" / "qa" / "take_v01_0_qa_v02.json").is_file()


@pytest.mark.tools
def test_take_qa_refuses_bad_input(run, capsys):
    take = _two_shot_clip(run.path / "03_wip" / "take_v01_0.mp4")
    (run.path / "03_wip" / "empty.txt").write_text(" \n", encoding="utf-8")
    (run.path / "03_wip" / "ok.txt").write_text("Spróbuj dziś wieczór.", encoding="utf-8")
    base = ["--run", str(run.path), str(take), "--lang", "pl", "--json"]
    for extra in (["--script", "03_wip/empty.txt"], ["--script", "03_wip/missing.txt"],
                  ["--script", "03_wip/ok.txt", "--brackets", "1.5,soon"]):
        assert take_qa.main(base + extra) == 1
        assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert not (run.path / "03_wip" / "qa").exists()


@pytest.mark.tools
def test_take_qa_without_script_is_not_transcribed(run, monkeypatch, capsys):
    """A narrated or silent take (no spoken lines): cuts, loudness and the contact sheet only."""
    _two_shot_clip(run.path / "03_wip" / "take_v01_0.mp4")
    monkeypatch.setattr(transcribe, "transcribe", lambda *a: pytest.fail("a take with no lines is not transcribed"))
    assert take_qa.main(["--run", str(run.path), "03_wip/take_v01_0.mp4", "--lang", "en", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    qa = out["qa"]
    assert (qa["transcript"], qa["match"], qa["words"], qa["wps"]) == (None, None, None, None)
    assert (qa["lines"], qa["heard_by"]) == (None, None) and "scribe" not in out
    assert len(qa["cuts"]) == 2 and isinstance(qa["lufs"], float)
    assert out["rubric"] == {"fails": [], "findings": [], "speed": None}
    assert not list((run.path / "03_wip" / "qa").glob("*_transcript_*"))


# --- issue #94: one offset per cut, against its nearest mark ------------------------------------------------

def test_each_cut_is_measured_against_its_nearest_mark_only():
    """One cut at 11.75 s and the board's marks 3/6/9/11: 0.75 s off 11, and 3, 6 and 9 have no cut (it used to be
    8.75 / 5.75 / 2.75 / 0.75: the cut against every mark)."""
    assert take_qa.offsets([11.75], [3, 6, 9, 11]) == [
        {"bracket": 3, "cut": None, "offset": None}, {"bracket": 6, "cut": None, "offset": None},
        {"bracket": 9, "cut": None, "offset": None}, {"bracket": 11, "cut": 11.75, "offset": 0.75}]
    # one offset per cut, also when two cuts are nearest the same mark; a mark between them is still free
    assert take_qa.offsets([2.9, 3.4, 9.2], [3, 6, 9]) == [
        {"bracket": 3, "cut": 2.9, "offset": -0.1}, {"bracket": 3, "cut": 3.4, "offset": 0.4},
        {"bracket": 6, "cut": None, "offset": None}, {"bracket": 9, "cut": 9.2, "offset": 0.2}]
    assert take_qa.offsets([], [3]) == [{"bracket": 3, "cut": None, "offset": None}]
    assert take_qa.offsets([2.0], []) == []


def test_the_rubric_reads_one_offset_per_cut():
    from tm import organic_qa

    qa = {"lufs": -16.0, "cut_offsets": take_qa.offsets([11.75], [3, 6, 9, 11])}
    findings = organic_qa.rubric_takes(qa, None, speech=False)["findings"]
    assert findings == ["no cut near 3 s", "no cut near 6 s", "no cut near 9 s"]   # 0.75 s is inside the 1 s flag


# --- issue #94: a quiet line is heard again before it is called missing --------------------------------------

LOUD_S, QUIET_S = 3.0, 1.5
SCRIPT = "Your plan, sorted in a minute.\nFirst month free."


def _quiet_end_clip(path):
    """4.5 s, 360x640, a 440 Hz tone at full level for 3 s, then about 30 dB quieter (a whispered last line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    seconds = LOUD_S + QUIET_S
    subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc2=size=360x640:rate=25:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}",
                    "-af", f"volume='if(lt(t,{LOUD_S}),1,0.03)':eval=frame", "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(path)], check=True)
    return path


def _words(*timed):
    return [{"start": a, "end": b, "word": f" {w}", "probability": 0.9} for w, a, b in timed]


FIRST_LINE = _words(("Your", 0.2, 0.5), ("plan,", 0.5, 0.9), ("sorted", 0.9, 1.4), ("in", 1.4, 1.5), ("a", 1.5, 1.6),
                    ("minute.", 1.6, LOUD_S))   # the loud part of the clip


def _first_listen(monkeypatch):
    """Whisper's first listen hears the first line only (its silence filter dropped the quiet end)."""
    monkeypatch.setattr(transcribe, "transcribe", lambda media, model, lang: {
        "language": lang, "language_probability": 0.9, "duration": LOUD_S + QUIET_S,
        "segments": [{"start": 0.2, "end": LOUD_S, "text": "Your plan, sorted in a minute.", "words": FIRST_LINE}]})


def _setup(run):
    _quiet_end_clip(run.path / "03_wip" / "take_v01_0.mp4")
    (run.path / "03_wip" / "lines.txt").write_text(SCRIPT + "\n", encoding="utf-8")
    return ["--run", str(run.path), "03_wip/take_v01_0.mp4", "--script", "03_wip/lines.txt", "--lang", "en", "--json"]


@pytest.mark.tools
def test_a_quiet_line_is_heard_again_levelled_and_counts(run, monkeypatch, capsys):
    argv = _setup(run)
    _first_listen(monkeypatch)
    heard = []

    def listen(audio, model, lang, *, vad=True, offset=0.0):
        heard.append({"vad": vad, "offset": offset, "samples": len(audio), "peak": float(abs(audio).max())})
        return [{"start": round(offset + 0.4, 2), "end": round(offset + 1.4, 2), "text": "First month free.",
                 "words": _words(("First", offset + 0.4, offset + 0.7), ("month", offset + 0.7, offset + 1.0),
                                 ("free.", offset + 1.0, offset + 1.4))}], None

    monkeypatch.setattr(transcribe, "listen", listen)
    assert take_qa.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    # the part after the first line, heard again without the silence filter and raised to the take's level
    assert len(heard) == 1 and heard[0]["vad"] is False and heard[0]["offset"] == pytest.approx(LOUD_S)
    assert heard[0]["samples"] == pytest.approx(QUIET_S * 16000, rel=0.1)
    assert heard[0]["peak"] > 0.05   # raised: the quiet tone alone peaks at about 0.004
    qa = out["qa"]
    assert qa["match"] == 1.0 and qa["heard_by"] == "whisper"
    first, last = qa["lines"]
    assert first == {"line": "Your plan, sorted in a minute.", "heard": 1.0, "start": 0.2, "end": LOUD_S,
                     "by": "whisper"}
    assert last["line"] == "First month free." and last["heard"] == 1.0 and last["by"] == "levelled"
    assert last["start"] == pytest.approx(LOUD_S + 0.4) and last["quiet"] is True and last["gain_db"] >= 20
    assert out["rubric"]["fails"] == [] and "scribe" not in out
    saved = json.loads((run.path / qa["transcript"]).read_text(encoding="utf-8"))
    assert [s.get("levelled_db") for s in saved["segments"]] == [None, last["gain_db"]]
    assert "levelled" in (run.path / "manifest.md").read_text(encoding="utf-8")


@pytest.mark.tools
def test_a_line_still_not_heard_is_not_reported_missing(run, monkeypatch, capsys):
    argv = _setup(run)
    _first_listen(monkeypatch)
    monkeypatch.setattr(transcribe, "listen", lambda audio, model, lang, *, vad=True, offset=0.0: ([], None))
    assert take_qa.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    qa = out["qa"]
    assert qa["match"] == pytest.approx(6 / 9, abs=0.001)
    assert qa["lines"][1] | {"gain_db": 0} == {"line": "First month free.", "heard": 0.0, "start": None, "end": None,
                                               "by": None, "gain_db": 0, "quiet": True}
    # a fail (the take is not accepted by rule), and it says the line is not missing yet: check with Scribe
    fail, = out["rubric"]["fails"]
    assert "“First month free.”" in fail and "no line is missing yet" in fail and "Scribe" in fail
    credits = tts_models.scribe_credits(qa_duration(run))
    assert out["scribe"]["lines"] == ["First month free."] and out["scribe"]["credits"] == credits
    assert out["scribe"]["command"].startswith("tm tool elevenlabs scribe --run ")
    assert out["scribe"]["command"].endswith(f"03_wip/take_v01_0.mp4 --cost {credits}")
    # the transcript is the first listen's: a levelled listen that heard nothing replaces nothing
    saved = json.loads((run.path / qa["transcript"]).read_text(encoding="utf-8"))
    assert [w["word"] for s in saved["segments"] for w in s["words"]] == [w["word"] for w in FIRST_LINE]


def _scribe_file(run, words, media="03_wip/take_v01_0.mp4"):
    from tm.tools import elevenlabs

    path = run.path / "03_wip" / "qa" / "take_v01_0_scribe_v01.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": "scribe", "model": "scribe_v3", "media": media, "language": "en",
                                "language_probability": 0.99, "duration": 4.5,
                                "segments": elevenlabs.scribe_segments(words), "credits_used": 25}), encoding="utf-8")
    return "03_wip/qa/take_v01_0_scribe_v01.json"


def _scribe_words(*timed):
    return [{"text": w, "start": a, "end": b, "type": "word", "logprob": -0.1} for w, a, b in timed]


@pytest.mark.tools
def test_scribe_words_decide_whether_a_line_is_there(run, monkeypatch, capsys):
    argv = _setup(run)
    monkeypatch.setattr(transcribe, "transcribe", lambda *a: pytest.fail("with Scribe, no local listen"))
    lines = [("Your", 0.2, 0.5), ("plan,", 0.5, 0.9), ("sorted", 0.9, 1.4), ("in", 1.4, 1.5), ("a", 1.5, 1.6),
             ("minute.", 1.6, 2.6)]
    rel = _scribe_file(run, _scribe_words(*lines, ("First", 3.4, 3.7), ("month", 3.7, 4.0), ("free.", 4.0, 4.4)))
    assert take_qa.main([*argv, "--scribe", rel]) == 0
    out = json.loads(capsys.readouterr().out)
    qa = out["qa"]
    assert (qa["transcript"], qa["heard_by"], qa["match"]) == (rel, "scribe", 1.0)
    assert [line["by"] for line in qa["lines"]] == ["scribe", "scribe"] and out["rubric"]["fails"] == []
    assert out["outputs"] == ["03_wip/qa/take_v01_0_qa_v01.json", "03_wip/qa/take_v01_0_contact_v01.png"]
    # Scribe does not hear the end either: only now is the line missing
    rel = _scribe_file(run, _scribe_words(*lines))
    assert take_qa.main([*argv, "--scribe", rel]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["rubric"]["fails"] == ["the transcript matches 67% of the script, under 90%"]
    assert out["rubric"]["findings"][0] == ("Scribe hears 0% of the line “First month free.”: the rest is missing "
                                            "from the take")
    assert "scribe" not in out


@pytest.mark.tools
def test_scribe_of_another_take_or_without_lines_is_refused(run, capsys):
    argv = _setup(run)
    rel = _scribe_file(run, _scribe_words(("Hi.", 0.2, 0.5)), media="03_wip/take_v02_0.mp4")
    assert take_qa.main([*argv, "--scribe", rel]) == 1
    assert "not of 03_wip/take_v01_0.mp4" in json.loads(capsys.readouterr().out)["message"]
    no_script = [a for a in argv if a not in ("--script", "03_wip/lines.txt")]
    assert take_qa.main([*no_script, "--scribe", rel]) == 1
    assert "--scribe needs --script" in json.loads(capsys.readouterr().out)["message"]
