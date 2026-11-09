"""transcribe: faster-whisper large-v3-turbo on CPU, int8, word timestamps. No model download here."""

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.tools
pytest.importorskip("numpy")
pytest.importorskip("faster_whisper")

from tm.tools import transcribe  # noqa: E402


def test_load_audio_unicode_path_16k_mono(clip):
    audio = transcribe.load_audio(clip)
    assert audio.dtype.name == "float32" and abs(len(audio) - 3 * 16000) < 1600


class FakeModel:
    made = []

    def __init__(self, name, device, compute_type, download_root):
        FakeModel.made.append((name, device, compute_type, download_root))

    def transcribe(self, audio, language, word_timestamps, vad_filter):
        assert word_timestamps and vad_filter
        words = [SimpleNamespace(start=0.21, end=0.9, word=" Zimowa", probability=0.912)]
        seg = SimpleNamespace(start=0.2, end=1.0, text=" Zimowa ", words=words)
        return iter([seg]), SimpleNamespace(language="pl", language_probability=0.99, duration=3.0)


def test_defaults_and_shape(clip, monkeypatch, tmp_path):
    monkeypatch.setattr(transcribe, "_model_class", lambda: FakeModel)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    result = transcribe.transcribe(clip)
    assert FakeModel.made[-1][:3] == ("large-v3-turbo", "cpu", "int8")
    assert FakeModel.made[-1][3].startswith(str(tmp_path / "data"))  # models stay in the plugin data
    assert result["segments"] == [{"start": 0.2, "end": 1.0, "text": "Zimowa", "words": [
        {"start": 0.21, "end": 0.9, "word": " Zimowa", "probability": 0.912}]}]
    assert result["language"] == "pl"


def test_video_without_audio_has_no_speech(tmp_path, monkeypatch):
    from _media import make_clip

    monkeypatch.setattr(transcribe, "_model_class", lambda: pytest.fail("no audio: no model"))
    silent = make_clip(tmp_path / "bez dźwięku.mp4", vf="null", tone=False, seconds=1.0)
    assert transcribe.transcribe(silent)["segments"] == []


def test_cli_writes_transcript_and_records(clip, run, monkeypatch, tmp_path):
    monkeypatch.setattr(transcribe, "_model_class", lambda: FakeModel)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    assert transcribe.main(["--run", str(run.path), str(clip), "--lang", "pl"]) == 0
    out = run.path / "02_research" / "transcript_v01.json"
    assert json.loads(out.read_text(encoding="utf-8"))["segments"][0]["text"] == "Zimowa"
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "02_research/transcript_v01.json" in manifest and "large-v3-turbo" in manifest
