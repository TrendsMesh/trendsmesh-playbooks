"""The run page's fixed words: the `run_page` area of the plugin's one table (`data/i18n/en.yaml`, read by tm.i18n).

Every fixed UI string of the template and the stage components is read here, through `t`, and nowhere else: what
the agent writes (titles, ledes, questions, options) is already in the run's language. The page is built in
`page_lang(run)`'s language: the run's working language when its table has every `run_page` key, else English with
a warning (`language_warning`), as every other page (references/languages.md).
"""

from __future__ import annotations

from functools import lru_cache

from tm import i18n

AREA = "run_page"
PREFIX = AREA + "."


def page_lang(run) -> i18n.PageLang:
    return i18n.page_lang(i18n.run_languages(run).working, AREA)


@lru_cache(maxsize=None)
def _translator(lang: str) -> i18n.Translator:
    return i18n.translator(lang)


def reset() -> None:
    """Read the tables again (a page build starts with it: a translation may have been imported since)."""
    _translator.cache_clear()


def has(key: str, lang: str = i18n.ENGLISH) -> bool:
    """Whether the table has `run_page.<key>` (the English table decides; a page language has every key)."""
    return PREFIX + key in _translator(lang).en


def t(key: str, lang: str = i18n.ENGLISH, **values: object) -> str:
    """The text of `run_page.<key>` in `lang`, with `{name}` placeholders filled. KeyError for a key the English
    table lacks (the tests check every key the page uses); i18n.Missing for a language without it (a page is only
    built in a language that has them all: `page_lang`)."""
    return _translator(lang)(PREFIX + key, **values)


def label(group: str, name: str, lang: str = i18n.ENGLISH) -> str:
    """A label for a data field or a stage (`run_page.<group>.<name>`), else the name made readable
    (`cost_per_result` -> `Cost per result`), so a new field never breaks a page."""
    key = f"{group}.{name}"
    return t(key, lang) if has(key, lang) else str(name).replace("_", " ").strip().capitalize()
