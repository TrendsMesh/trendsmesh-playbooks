"""tm tool take_qa: QA of a generated take, on a clip made here with ffmpeg (two framings, cut A-B-A, and a tone).

The transcript runs through faster-whisper when a model is already in the plugin's data folder; with none cached
it is replaced here (the test never downloads a model), and the rest of the QA still runs."""

from __future__ import annotations

import json
import subprocess

import pytest
from _media import ffmpeg

from tm import organic_config
from tm.tools import take_qa, transcribe

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
    else:   # transcription skipped: a tone says nothing anyway
        monkeypatch.setattr(transcribe, "transcribe", lambda media, model, lang: {
            "language": lang, "language_probability": 0.0, "duration": 3 * SHOT_S, "segments": []})
    assert take_qa.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["outputs"][0] == "03_wip/qa/take_v01_0_qa_v01.json"
    qa = json.loads((run.path / "03_wip" / "qa" / "take_v01_0_qa_v01.json").read_text(encoding="utf-8"))
    assert list(qa) == ["take", "transcript", "match", "words", "speech_seconds", "wps", "tail_silence", "cuts",
                        "cut_offsets", "lufs", "peak", "contact_sheet"]
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
    # the rubric answer: the tone fails the transcript, the cuts are on time
    assert out["rubric"]["fails"] and not out["rubric"]["findings"]
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
    assert len(qa["cuts"]) == 2 and isinstance(qa["lufs"], float)
    assert out["rubric"] == {"fails": [], "findings": [], "speed": None}
    assert not list((run.path / "03_wip" / "qa").glob("*_transcript_*"))
