"""Plugin secrets, read from <data>/secrets.env (written by the session hook, mode 0600)."""

from __future__ import annotations

from typing import Literal

from tm.paths import data_dir

Name = Literal["replicate_api_token", "elevenlabs_api_key"]
_VARS = {"replicate_api_token": "REPLICATE_API_TOKEN", "elevenlabs_api_key": "ELEVENLABS_API_KEY"}


def get(name: Name) -> str | None:
    if name not in _VARS:
        raise ValueError(f"unknown secret: {name}")
    try:
        text = (data_dir() / "secrets.env").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == _VARS[name]:
            return value or None
    return None
