"""speaker_sim: ECAPA embeddings; here only the audio loading (the model is not downloaded)."""

import pytest

pytestmark = pytest.mark.tools
np = pytest.importorskip("numpy")
pytest.importorskip("speechbrain")

from tm.tools import speaker_sim  # noqa: E402


def test_load_with_band_limit_and_window(clip):
    full = speaker_sim.load(clip)
    part = speaker_sim.load(clip, start=1.0, end=2.0)
    assert abs(len(full) - 48000) < 1600 and abs(len(part) - 16000) < 800
    # 440 Hz sits inside the 100 Hz - 4 kHz band, so the band limit keeps it.
    assert np.abs(speaker_sim.load(clip, band=True)).max() > 0.1


def test_model_uses_copy_strategy_and_plugin_data(monkeypatch, tmp_path):
    seen = {}

    class Fake:
        @staticmethod
        def from_hparams(**kw):
            seen.update(kw)
            return "model"

    monkeypatch.setattr(speaker_sim, "_encoder_class", lambda: Fake)
    monkeypatch.setattr(speaker_sim, "_model", None)
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    assert speaker_sim.model() == "model"
    from speechbrain.utils.fetching import LocalStrategy
    assert seen["local_strategy"] is LocalStrategy.COPY
    assert seen["savedir"].startswith(str(tmp_path / "data"))
    assert seen["fetch_config"].huggingface_cache_dir.startswith(str(tmp_path / "data"))
    assert seen["run_opts"] == {"device": "cpu"}
