import pytest

from tm.secrets import get


def test_secret_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path))
    assert get("replicate_api_token") is None


def test_secret_value_is_read(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path))
    (tmp_path / "secrets.env").write_text("REPLICATE_API_TOKEN=tok-1\n")
    assert get("replicate_api_token") == "tok-1"
    assert get("elevenlabs_api_key") is None


def test_secret_keeps_equals_signs_and_ignores_blank_and_comments(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path))
    (tmp_path / "secrets.env").write_text(
        "# note\n\nELEVENLABS_API_KEY=ab=cd==\nREPLICATE_API_TOKEN=\n"
    )
    assert get("elevenlabs_api_key") == "ab=cd=="
    assert get("replicate_api_token") is None  # empty counts as unset


def test_unknown_secret_name_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path))
    with pytest.raises(ValueError):
        get("other")
