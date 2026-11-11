"""The fixed words of Create an ad (data/create-ad/strings.yaml), by key. English only for now: the table moves onto
the shared translation mechanism (issue #3) without changing a caller."""

from __future__ import annotations

from functools import lru_cache

import yaml

from tm import paths

LANG = "en"


@lru_cache(maxsize=None)
def _table() -> dict[str, str]:
    data = yaml.safe_load((paths.bundled_data() / "create-ad" / "strings.yaml").read_text(encoding="utf-8")) or {}
    table = data.get(LANG)
    if not (isinstance(table, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in table.items())):
        raise ValueError(f"create-ad/strings.yaml: `{LANG}` must map keys to texts")
    return table


def text(key: str, **fill: object) -> str:
    """The text for `key`, its {placeholders} filled. A missing key is a ValueError (a bug, never shown blank)."""
    table = _table()
    if key not in table:
        raise ValueError(f"create-ad/strings.yaml has no {key!r}")
    return table[key].format(**fill) if fill else table[key]


def keys() -> list[str]:
    return list(_table())
