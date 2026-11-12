"""A run's two languages and the pages' words in them (issue #3).

A run has a **working language**, for what the user and their team read (check-in cards, pages, labels, help,
briefs, reports), and a **market language**, for what the audience sees or hears (ad copy, captions, voiceover,
on-screen and cover text). Both are BCP 47 tags in every playbook's config.yaml, under one key:
`languages: {working: pl, market: pl}`. `run_languages(run)` / `languages_of(cfg)` read them, and read a config
written before the key existed from its older keys (`account.language`, trend research's `language` and
`market_lang`, organic video's `page_lang`). See references/languages.md.

The fixed words of the pages are one keyed English table, `data/i18n/en.yaml` (`<area>.<key>`, nested in the
file). Another language's table is the agent's translation of it, made once and reused across runs:

    tm i18n export --lang pl --out i18n_pl.yaml     what has no Polish yet, with the English to translate
    tm i18n import --lang pl i18n_pl.yaml           checks every key and placeholder, then keeps it
    tm i18n check  --lang pl [--area brief ...]     what is still missing

A translation is kept in the plugin data folder (`i18n/<lang>.yaml`), with the English it was made from: when an
English string changes, its translation counts as missing again. The plugin may also ship a translation
(`data/i18n/<lang>.yaml`); a kept one wins. A region's table falls back to its language's (`pt-BR` reads `pt`).

    t(key, lang="en", **values)    one string, filled; `Missing` when `lang` has no translation of it (never
                                   a silent English); KeyError for a key the English table does not have
    translator(lang)               the same, the table read once (a page build); `tr.plural(key, count,
                                   **values)` the form of a count (below)
    page_lang(wanted, *areas)      the language to build a page in: `wanted` when its table has every key of the
                                   areas, else English, with `.warning` saying so and what to run (loud, never
                                   silent)

A count's words are a group of forms keyed by CLDR plural category (`report.lede.one`, `report.lede.other`):
the English table writes `one` and `other`, and another language's table writes the forms its whole numbers take
(`count_forms`: Polish one, few, many; Japanese other alone), each translated from the English `other` (`one`
from the English `one`). `category(count, lang)` is the CLDR rule; a form may say the count where the English
leaves it out (Russian's one is 1, 21, 31 …).

`transliterate` keeps file names readable: é -> e, ß -> ss, ł -> l, ś -> s; other scripts stay as they are.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import string
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import yaml

from tm import cli, paths

TABLES = paths.bundled_data() / "i18n"
ENGLISH = "en"
CACHE = "i18n"             # the folder in the plugin data folder

_TAG = re.compile(r"^(?P<lang>[A-Za-z]{2,3})(?:-(?P<script>[A-Za-z]{4}))?(?:-(?P<region>[A-Za-z]{2}|\d{3}))?$")
_MARKUP = re.compile(r"<[^>]+>")

# English names (for messages) and the names people write, English and their own, for the common languages.
NAMES = {
    "ar": ("Arabic", "العربية"), "bg": ("Bulgarian", "български"), "ca": ("Catalan", "català"),
    "cs": ("Czech", "čeština"), "da": ("Danish", "dansk"), "de": ("German", "Deutsch"), "el": ("Greek", "Ελληνικά"),
    "en": ("English", "English"), "es": ("Spanish", "español"), "et": ("Estonian", "eesti"),
    "fa": ("Persian", "فارسی"), "fi": ("Finnish", "suomi"), "fil": ("Filipino", "Filipino"),
    "fr": ("French", "français"), "ga": ("Irish", "Gaeilge"), "he": ("Hebrew", "עברית"), "hi": ("Hindi", "हिन्दी"),
    "hr": ("Croatian", "hrvatski"), "hu": ("Hungarian", "magyar"), "id": ("Indonesian", "Bahasa Indonesia"),
    "is": ("Icelandic", "íslenska"), "it": ("Italian", "italiano"), "ja": ("Japanese", "日本語"),
    "ko": ("Korean", "한국어"), "lt": ("Lithuanian", "lietuvių"), "lv": ("Latvian", "latviešu"),
    "ms": ("Malay", "Bahasa Melayu"), "nb": ("Norwegian Bokmål", "norsk bokmål"), "nl": ("Dutch", "Nederlands"),
    "no": ("Norwegian", "norsk"), "pl": ("Polish", "polski"), "pt": ("Portuguese", "português"),
    "ro": ("Romanian", "română"), "ru": ("Russian", "русский"), "sk": ("Slovak", "slovenčina"),
    "sl": ("Slovenian", "slovenščina"), "sr": ("Serbian", "српски"), "sv": ("Swedish", "svenska"),
    "th": ("Thai", "ไทย"), "tr": ("Turkish", "Türkçe"), "uk": ("Ukrainian", "українська"),
    "vi": ("Vietnamese", "Tiếng Việt"), "zh": ("Chinese", "中文"), "be": ("Belarusian", "беларуская"),
    "mk": ("Macedonian", "македонски"), "kk": ("Kazakh", "қазақ тілі"), "ur": ("Urdu", "اردو"),
}
_BY_NAME = {n.casefold(): code for code, names in NAMES.items() for n in names}
_BY_NAME.update({"polish language": "pl", "brazilian portuguese": "pt-BR", "castilian": "es", "flemish": "nl",
                 "farsi": "fa", "mandarin": "zh", "norwegian bokmal": "nb", "bokmål": "nb", "deutsch": "de",
                 "espanol": "es", "francais": "fr", "portugues": "pt", "turkce": "tr", "cestina": "cs"})

# Letters that Unicode does not decompose into a base letter and a mark.
_LETTERS = {"ß": "ss", "ẞ": "SS", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE",
            "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "Th", "ð": "d", "Ð": "D", "ı": "i", "ħ": "h", "Ħ": "H", "ŀ": "l",
            "Ŀ": "L", "ŋ": "ng", "Ŋ": "NG", "ſ": "s"}


class Missing(LookupError):
    """A language has no translation of a key: build in English and say so (`page_lang`), or translate first."""


# --- tags and names ------------------------------------------------------------------------------------

def tag(value: object) -> str | None:
    """`value` as a BCP 47 tag (`pl`, `pl-PL`, `zh-Hant-TW`), from a tag in any case or with `_`, or a language's
    English or own name ("Polish", "polski"). None for anything else."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    named = _BY_NAME.get(text.casefold())
    if named:
        return named
    m = _TAG.match(text.replace("_", "-"))
    if not m:
        return None
    out = m.group("lang").lower()
    if len(out) == 3 and out not in NAMES:
        out = out                       # an ISO 639-2/3 code is still a tag
    if m.group("script"):
        out += "-" + m.group("script").title()
    if m.group("region"):
        out += "-" + m.group("region").upper()
    return out


def primary(lang: str) -> str:
    """`pt-BR` -> `pt`."""
    return lang.split("-")[0].lower()


def is_english(lang: str | None) -> bool:
    return not lang or primary(lang) == ENGLISH


def name(lang: str | None) -> str:
    """The language's English name for a message ("Polish", "Portuguese (BR)"), else the tag itself."""
    if not lang:
        return "English"
    base = NAMES.get(primary(lang), (None,))[0]
    if base is None:
        return lang
    rest = lang.split("-")[1:]
    return base + (f" ({'-'.join(rest)})" if rest else "")


# --- a run's two languages ------------------------------------------------------------------------------

class Languages(NamedTuple):
    working: str        # what the user and their team read
    market: str         # what the audience sees or hears


def _older(cfg: dict) -> tuple[str | None, str | None]:
    """(working, market) from a config written before `languages`: refresh-ad's and creative brief's
    `account.language` (both), trend research's `language` and `market_lang`, organic video's `page_lang`."""
    account = cfg.get("account") if isinstance(cfg.get("account"), dict) else {}
    said = tag(account.get("language")) or tag(cfg.get("language"))
    market = tag(cfg.get("market_lang")) or said
    working = said or tag(cfg.get("page_lang"))
    return working, market


def languages_of(cfg: dict | None) -> Languages:
    """The run's languages from its config: `languages`, else the older keys; the one left out is the other, and
    English when there is neither."""
    cfg = cfg if isinstance(cfg, dict) else {}
    given = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
    old_working, old_market = _older(cfg)
    working = tag(given.get("working")) or old_working
    market = tag(given.get("market")) or old_market
    working = working or market or ENGLISH
    return Languages(working, market or working)


def stated_market(cfg: dict | None) -> tuple[str | None, str | None]:
    """(the market language the config states, where), never a default: `languages.market`, else an older
    config's account.language, market_lang or language; (None, None) when it states none (video fonts then look
    at the organic channel profile)."""
    cfg = cfg if isinstance(cfg, dict) else {}
    given = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
    if tag(given.get("market")):
        return tag(given.get("market")), "languages.market in config.yaml"
    account = cfg.get("account") if isinstance(cfg.get("account"), dict) else {}
    for where, value in (("account.language", account.get("language")), ("market_lang", cfg.get("market_lang")),
                         ("language", cfg.get("language"))):
        if tag(value):
            return tag(value), f"{where} in config.yaml"
    return None, None


def run_languages(run) -> Languages:
    """The two languages of a run (a RunFolder), from its config.yaml; English for both before it is written."""
    from tm import config            # config's validation uses this module
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = {}
    return languages_of(cfg)


def settle(cfg: dict) -> dict:
    """At intake: write `languages` in full, as tags, from what the answers gave (`languages`, else the older
    keys); the one left out is the other. Nothing given leaves both null, for validation to ask (never a silent
    English). A value that is not a language is left as given, for validation to name."""
    given = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
    older = dict(zip(("working", "market"), _older(cfg)))
    out = {}
    for key in ("working", "market"):
        raw = given.get(key)
        out[key] = raw if (raw is not None and tag(raw) is None) else tag(raw) or older[key]
    if out["working"] is None and tag(out["market"]):
        out["working"] = out["market"]
    if out["market"] is None and tag(out["working"]):
        out["market"] = out["working"]
    cfg["languages"] = out
    return cfg


def given(cfg: dict) -> bool:
    """The config names a language: in `languages` or in an older key."""
    langs = cfg.get("languages") if isinstance(cfg.get("languages"), dict) else {}
    return any(v is not None for v in langs.values()) or any(_older(cfg))


def config_problems(cfg: dict) -> list:
    """`language_problems`, and one when the config names no language at all."""
    from tm.config import Problem
    out = language_problems(cfg)
    if not out and not given(cfg):
        out.append(Problem("languages", "The run's languages are missing: the working language (what you and your "
                                        "team read) and the market language (what the audience sees and hears).",
                           "Confirm both to Claude on the intake card (by default the language you write in)."))
    return out


def language_problems(cfg: dict) -> list:
    """config.Problem for each of `languages` that is not a language tag; none when the key is left out (an older
    config: `languages_of` reads its older keys)."""
    from tm.config import Problem
    if "languages" not in cfg or cfg["languages"] is None:
        return []
    given = cfg["languages"]
    if not isinstance(given, dict):
        return [Problem("languages", f"languages must be a group with working and market, not {given!r}.",
                        "Write it as languages: {working: <tag>, market: <tag>}, e.g. {working: pl, market: pl}.")]
    out = []
    for key, what in (("working", "what you and your team read"), ("market", "what the audience sees and hears")):
        value = given.get(key)
        if value is not None and (not isinstance(value, str) or tag(value) != value.strip()):
            hint = tag(value) if isinstance(value, str) else None
            out.append(Problem(f"languages.{key}", f"languages.{key} ({what}) must be a language tag such as pl or "
                                                   f"pt-BR, not {value!r}.",
                               f"Set it to {hint}." if hint else "Give it the language's tag."))
    return out


# --- counts: CLDR plural categories ------------------------------------------------------------------

CATEGORIES = ("zero", "one", "two", "few", "many", "other")     # CLDR's order


class _Count(NamedTuple):
    """CLDR's operands of a count: n the absolute value, i its whole digits, v how many fraction digits it shows,
    f those digits, t them without trailing zeros ("1.50": n 1.5, i 1, v 2, f 50, t 5)."""
    n: Decimal
    i: int
    v: int
    f: int
    t: int


def _operands(count) -> _Count:
    try:
        d = abs(Decimal(str(count).strip()))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{count!r} is not a count.") from None
    whole, _, frac = format(d, "f").partition(".")
    return _Count(d, int(whole), len(frac), int(frac or 0), int(frac.rstrip("0") or 0))


def _in(x, low: int, high: int) -> bool:
    """CLDR's `x = low..high`: a whole number in the range."""
    return x == int(x) and low <= x <= high


def _million(o: _Count) -> bool:          # CLDR's `e = 0 and i != 0 and i % 1000000 = 0 and v = 0`
    return o.i != 0 and o.i % 1_000_000 == 0 and o.v == 0


def _slavic(o: _Count) -> str:            # ru, uk
    if o.v:
        return "other"
    if o.i % 10 == 1 and o.i % 100 != 11:
        return "one"
    if 2 <= o.i % 10 <= 4 and not 12 <= o.i % 100 <= 14:
        return "few"
    return "many"


def _polish(o: _Count) -> str:
    if o.v:
        return "other"
    if o.i == 1:
        return "one"
    return "few" if 2 <= o.i % 10 <= 4 and not 12 <= o.i % 100 <= 14 else "many"


def _belarusian(o: _Count) -> str:
    if o.n % 10 == 1 and o.n % 100 != 11:
        return "one"
    if _in(o.n % 10, 2, 4) and not _in(o.n % 100, 12, 14):
        return "few"
    if o.n % 10 == 0 or _in(o.n % 10, 5, 9) or _in(o.n % 100, 11, 14):
        return "many"
    return "other"


def _czech(o: _Count) -> str:             # cs, sk
    if o.v:
        return "many"
    return "one" if o.i == 1 else "few" if 2 <= o.i <= 4 else "other"


def _bosnian(o: _Count) -> str:           # hr, sr, bs
    if (not o.v and o.i % 10 == 1 and o.i % 100 != 11) or (o.f % 10 == 1 and o.f % 100 != 11):
        return "one"
    if (not o.v and 2 <= o.i % 10 <= 4 and not 12 <= o.i % 100 <= 14) or \
            (2 <= o.f % 10 <= 4 and not 12 <= o.f % 100 <= 14):
        return "few"
    return "other"


def _slovenian(o: _Count) -> str:
    if not o.v and o.i % 100 == 1:
        return "one"
    if not o.v and o.i % 100 == 2:
        return "two"
    return "few" if o.v or 3 <= o.i % 100 <= 4 else "other"


def _lithuanian(o: _Count) -> str:
    if o.f:
        return "many"
    if o.n % 10 == 1 and not _in(o.n % 100, 11, 19):
        return "one"
    return "few" if _in(o.n % 10, 2, 9) and not _in(o.n % 100, 11, 19) else "other"


def _latvian(o: _Count) -> str:
    if o.n % 10 == 0 or _in(o.n % 100, 11, 19) or (o.v == 2 and 11 <= o.f % 100 <= 19):
        return "zero"
    if (o.n % 10 == 1 and o.n % 100 != 11) or (o.v == 2 and o.f % 10 == 1 and o.f % 100 != 11) or \
            (o.v != 2 and o.f % 10 == 1):
        return "one"
    return "other"


def _romanian(o: _Count) -> str:
    if o.i == 1 and not o.v:
        return "one"
    return "few" if o.v or o.n == 0 or (o.n != 1 and _in(o.n % 100, 1, 19)) else "other"


def _arabic(o: _Count) -> str:
    if o.n in (0, 1, 2):
        return ("zero", "one", "two")[int(o.n)]
    if _in(o.n % 100, 3, 10):
        return "few"
    return "many" if _in(o.n % 100, 11, 99) else "other"


def _hebrew(o: _Count) -> str:
    if (o.i == 1 and not o.v) or (o.i == 0 and o.v):
        return "one"
    return "two" if o.i == 2 and not o.v else "other"


def _irish(o: _Count) -> str:
    if o.n in (1, 2):
        return ("one", "two")[int(o.n) - 1]
    return "few" if _in(o.n, 3, 6) else "many" if _in(o.n, 7, 10) else "other"


def _macedonian(o: _Count) -> str:
    one = (not o.v and o.i % 10 == 1 and o.i % 100 != 11) or (o.f % 10 == 1 and o.f % 100 != 11)
    return "one" if one else "other"


def _filipino(o: _Count) -> str:
    one = (not o.v and (o.i in (1, 2, 3) or o.i % 10 not in (4, 6, 9))) or (o.v and o.f % 10 not in (4, 6, 9))
    return "one" if one else "other"


def _icelandic(o: _Count) -> str:
    one = (o.t == 0 and o.i % 10 == 1 and o.i % 100 != 11) or (o.t % 10 == 1 and o.t % 100 != 11)
    return "one" if one else "other"


def _rule(one, million: bool = False):
    """one/other by `one` (and many for a round million, the Romance languages' `de`)."""
    return lambda o: "one" if one(o) else "many" if million and _million(o) else "other"


_ONE_WHOLE = _rule(lambda o: o.i == 1 and not o.v)              # CLDR `i = 1 and v = 0`
_ONE_N = _rule(lambda o: o.n == 1)                              # CLDR `n = 1`
_ONE_ZERO = _rule(lambda o: o.i == 0 or o.n == 1)               # CLDR `i = 0 or n = 1`
_NONE = lambda o: "other"                                       # noqa: E731  (no forms)

PLURAL_RULES = {
    **dict.fromkeys(("en", "de", "nl", "sv", "et", "fi", "ur"), _ONE_WHOLE),
    **dict.fromkeys(("nb", "no", "el", "bg", "hu", "tr", "kk"), _ONE_N),
    **dict.fromkeys(("hi", "fa"), _ONE_ZERO),
    **dict.fromkeys(("ja", "ko", "zh", "th", "vi", "id", "ms"), _NONE),
    **dict.fromkeys(("it", "ca", "pt-PT"), _rule(lambda o: o.i == 1 and not o.v, million=True)),
    "es": _rule(lambda o: o.n == 1, million=True),
    "fr": _rule(lambda o: o.i in (0, 1), million=True),
    "pt": _rule(lambda o: o.i in (0, 1), million=True),
    "da": _rule(lambda o: o.n == 1 or (o.t != 0 and o.i in (0, 1))),
    "is": _icelandic, "pl": _polish, "ru": _slavic, "uk": _slavic, "be": _belarusian, "cs": _czech, "sk": _czech,
    "hr": _bosnian, "sr": _bosnian, "bs": _bosnian, "sl": _slovenian, "lt": _lithuanian, "lv": _latvian,
    "ro": _romanian, "ar": _arabic, "he": _hebrew, "ga": _irish, "mk": _macedonian, "fil": _filipino,
}
_SAMPLE = (*range(0, 1001), 1_000_000)        # the whole numbers that show each language's forms


def _plural_rule(lang: str | None):
    """`lang`'s CLDR cardinal rule, its region's first (pt-PT); a language CLDR's table here lacks counts like
    English (one: 1)."""
    for code in reversed(_candidates(tag(lang) or ENGLISH)):
        if code in PLURAL_RULES:
            return PLURAL_RULES[code]
    return _ONE_WHOLE


def category(count, lang: str | None = ENGLISH) -> str:
    """The CLDR plural category of `count` (a number, or its text: "1.50" keeps its fraction digits) in `lang`:
    zero, one, two, few, many or other."""
    return _plural_rule(lang)(_operands(count))


@lru_cache(maxsize=64)
def _examples(lang: str) -> dict[str, tuple[int, ...]]:
    rule, out = _plural_rule(lang), {}
    for n in _SAMPLE:
        out.setdefault(rule(_operands(n)), []).append(n)
    return {c: tuple(out[c]) for c in CATEGORIES if c in out}


def count_forms(lang: str | None) -> tuple[str, ...]:
    """The forms a count of whole things takes in `lang`, in CLDR's order: what its table writes for each count
    (a fraction form only where whole numbers take it too)."""
    return tuple(_examples(tag(lang) or ENGLISH))


def _form_hint(lang: str) -> str:
    """"one: 1; few: 2, 3, 4, 22, 23, 24, …; many: 0, 5, …": the numbers each form of `lang` is for."""
    parts = []
    for cat, nums in _examples(lang).items():
        shown = [f"{n:,}".replace(",", " ") for n in nums[:6]]
        parts.append(f"{cat}: {', '.join(shown)}{', …' if len(nums) > 6 else ''}")
    return "; ".join(parts)


def groups(en: dict | None = None) -> dict[str, dict[str, str]]:
    """The English table's counts: each group's key (`report.lede`) -> its forms ({"one": …, "other": …}). A
    group is a mapping of CLDR categories with an `other`."""
    en = english() if en is None else en
    found: dict[str, dict[str, str]] = {}
    for key, text in en.items():
        base, _, cat = key.rpartition(".")
        if cat in CATEGORIES and base:
            found.setdefault(base, {})[cat] = text
    return {base: forms for base, forms in found.items() if "other" in forms}


def _source_of(key: str, en: dict, counts: dict) -> str | None:
    """The English a key of a table is translated from: its own, or for a form of a count the English form of
    that category, else the English `other`; None for a key that is neither."""
    base, _, cat = key.rpartition(".")
    if base in counts and cat in CATEGORIES:
        return counts[base].get(cat) or counts[base]["other"]
    return en.get(key)


def wanted(lang: str, areas: tuple[str, ...] | list[str] = ()) -> dict[str, str]:
    """Each key `lang`'s table needs (of `areas`, else all), with the English it is translated from, in the
    table's order: every string, and for each count the forms `lang` takes (`count_forms`)."""
    en = english()
    if is_english(lang):
        return {k: v for k, v in en.items() if not areas or k.split(".")[0] in areas}
    counts, forms, out = groups(en), count_forms(lang), {}
    for key, text in en.items():
        if areas and key.split(".")[0] not in areas:
            continue
        base = key.rpartition(".")[0]
        if base in counts:
            out.update({f"{base}.{c}": counts[base].get(c) or counts[base]["other"] for c in forms})
        else:
            out[key] = text
    return out


# --- the tables -------------------------------------------------------------------------------------------

def _flat(node: object, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(_flat(value, f"{prefix}{key}." if prefix or key else ""))
            if not isinstance(value, dict):
                out[f"{prefix}{key}"] = value
    return {k: v for k, v in out.items() if not isinstance(v, dict)}


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path.name} is not a readable string table ({exc}).") from None
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _english() -> tuple[tuple[str, str], ...]:
    return tuple(_flat(_read(TABLES / f"{ENGLISH}.yaml")).items())


def english() -> dict[str, str]:
    """The English table: every key and its string."""
    return dict(_english())


def _shipped(lang: str) -> dict[str, str]:
    """The plugin's own translation into `lang` (data/i18n/<lang>.yaml), if it ships one."""
    if is_english(lang):
        return {}
    data = _read(TABLES / f"{lang}.yaml")
    return {k: v for k, v in _flat(data.get("strings", data)).items() if isinstance(v, str)}


def cache_dir() -> Path | None:
    """Where kept translations live (the plugin data folder's i18n/); None when the plugin's folders are unknown."""
    try:
        return paths.data_dir() / CACHE
    except RuntimeError:
        return None


def _source(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _kept(lang: str) -> dict:
    folder = cache_dir()
    return _read(folder / f"{lang}.yaml") if folder else {}


def _candidates(lang: str) -> list[str]:
    """`zh-Hant-TW` -> [zh, zh-Hant, zh-Hant-TW]: the most general first, so the closest wins."""
    parts = lang.split("-")
    return ["-".join(parts[:i]) for i in range(1, len(parts) + 1)]


def placeholders(text: str) -> set[str]:
    try:
        return {f for _, f, _, _ in string.Formatter().parse(text) if f is not None}
    except ValueError:
        return {"<unbalanced braces>"}


def _markup(text: str) -> list[str]:
    return sorted(_MARKUP.findall(text))


def problems(strings: dict, en: dict | None = None) -> list[str]:
    """What is wrong in a translation: a key the English table lacks (a form of a count is `<count>.<category>`,
    a CLDR category), an empty string, other placeholders or other markup than the English. A form of a count
    may leave out or say any of its count's placeholders (Russian's one is 1, 21 …, where the English one is 1)."""
    en = english() if en is None else en
    counts = groups(en)
    return [bad for key, text in strings.items() if (bad := _problem(key, text, en, counts))]


def _problem(key: str, text: object, en: dict, counts: dict) -> str | None:
    source = _source_of(key, en, counts)
    if source is None:
        return f"{key}: not a key of the English table"
    if not isinstance(text, str) or not text.strip():
        return f"{key}: empty"
    base = key.rpartition(".")[0]
    if base in counts:
        allowed = set().union(*(placeholders(v) for v in counts[base].values()))
        if not placeholders(text) <= allowed:
            want = ", ".join(sorted("{" + p + "}" for p in allowed)) or "none"
            return f"{key}: placeholders must be among {want}, as in English"
    elif placeholders(text) != placeholders(source):
        want = ", ".join(sorted("{" + p + "}" for p in placeholders(source))) or "none"
        return f"{key}: placeholders must be {want}, exactly as in English"
    if _markup(text) != _markup(source):
        return f"{key}: keep the English markup ({' '.join(_markup(source)) or 'none'})"
    return None


def table(lang: str) -> dict[str, str]:
    """Every string `lang` has a valid translation of: shipped, then kept (the kept wins), the language's before
    its region's; a kept one made from an older English is left out."""
    if is_english(lang):
        return english()
    en = english()
    counts = groups(en)
    out: dict[str, str] = {}
    for code in _candidates(lang):
        shipped = _shipped(code)
        out.update({k: v for k, v in shipped.items() if not _problem(k, v, en, counts)})
        kept = _kept(code)
        strings, sources = kept.get("strings") or {}, kept.get("sources") or {}
        for k, v in strings.items():
            source = _source_of(k, en, counts)
            if source is not None and sources.get(k) == _source(source) and not _problem(k, v, en, counts):
                out[k] = v
    return out


def missing(lang: str, areas: tuple[str, ...] | list[str] = ()) -> list[str]:
    """The keys `lang`'s table needs (of `areas`, else all, `wanted`) that it has no translation of, in the
    table's order."""
    have = table(lang)
    return [k for k in wanted(lang, areas) if k not in have]


@dataclass
class Translator:
    """`tr(key, **values)`: one string of the table in `lang`, filled. Read once, for a page build."""
    lang: str
    strings: dict[str, str] = field(repr=False)
    en: dict[str, str] = field(repr=False)
    counts: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.counts = self.counts or groups(self.en)

    def __call__(self, key: str, **values) -> str:
        if key not in self.en:
            raise KeyError(f"{key} is not a key of the English table (data/i18n/en.yaml).")
        text = self.strings.get(key)
        if text is None:
            raise Missing(f"{name(self.lang)} ({self.lang}) has no translation of {key}. Translate the table once: "
                          f"tm i18n export --lang {self.lang} --out i18n_{self.lang}.yaml, then tm i18n import.")
        return text.format(**values) if values else text

    def plural(self, key: str, count, **values) -> str:
        """The form of the count `key` (a group of the English table, `report.lede`) that `count` takes in
        `lang` (`category`), filled from `values`. A fraction in a language whose table has no fraction form
        takes `other`, else the last form (Polish many)."""
        if key not in self.counts:
            raise KeyError(f"{key} is not a count of the English table (data/i18n/en.yaml: {key}.one, {key}.other).")
        cat = category(count, self.lang)
        if f"{key}.{cat}" not in self.strings and (is_english(self.lang) or cat not in count_forms(self.lang)):
            cat = "other" if f"{key}.other" in self.strings else count_forms(self.lang)[-1]
        text = self.strings.get(f"{key}.{cat}")
        if text is None:
            raise Missing(f"{name(self.lang)} ({self.lang}) has no translation of {key}.{cat}. Translate the table "
                          f"once: tm i18n export --lang {self.lang} --out i18n_{self.lang}.yaml, then tm i18n import.")
        return text.format(**values) if values else text


def translator(lang: str) -> Translator:
    return Translator(lang, table(lang), english())


def t(key: str, lang: str = ENGLISH, **values) -> str:
    """One string of the table in `lang`, its placeholders filled from `values`. Missing (never English in its
    place) when `lang` has no translation of it; KeyError for a key the English table does not have."""
    return translator(lang)(key, **values)


@dataclass(frozen=True)
class PageLang:
    lang: str                 # the language the page is built in (and its `lang` attribute)
    wanted: str               # the run's working language
    missing: tuple[str, ...]  # its keys without a translation (empty when lang is wanted)

    @property
    def warning(self) -> str | None:
        if self.lang == self.wanted:
            return None
        return (f"The page is built in English: {len(self.missing)} of its texts have no {name(self.wanted)} "
                f"translation yet. Translate them once (reused by every run in {name(self.wanted)}): tm i18n export "
                f"--lang {self.wanted} --out i18n_{self.wanted}.yaml, translate each string in that file, tm i18n "
                f"import --lang {self.wanted} i18n_{self.wanted}.yaml, then build the page again.")


def page_lang(wanted: str | None, *areas: str) -> PageLang:
    """The language to build a page of `areas` in: `wanted` when its table has every key of them, else English
    (with a warning to show the user)."""
    wanted = tag(wanted) or ENGLISH
    if is_english(wanted):
        return PageLang(wanted, wanted, ())
    gaps = tuple(missing(wanted, areas))
    return PageLang(ENGLISH if gaps else wanted, wanted, gaps)


def html_lang(lang: str) -> str:
    """The `lang` attribute's value."""
    return tag(lang) or ENGLISH


# --- phrases offered to the user -------------------------------------------------------------------

OFFERED = ("trends.weekly_phrase",)    # what the engine's messages tell the user to say, quoted


def offered(text: str, lang: str | None) -> str:
    """`text` (an engine message for the agent) with each phrase it offers the user to say in `lang`: the
    translation when the table has it, else the English with a note to say it in `lang` (never silently English)."""
    if is_english(lang) or not text:
        return text
    en, have = english(), table(lang)
    for key in OFFERED:
        quoted = f"'{en[key]}'"
        if quoted in text:
            text = text.replace(quoted, f"'{have[key]}'" if key in have else
                                f"{quoted} (offer it to the user in {name(lang)})")
    return text


# --- export and import --------------------------------------------------------------------------------

_HOW = ("Translate each string into {name}, for the people who read the pages (the run's working language). Keep "
        "every {{placeholder}} and every <tag> exactly as it is; change nothing else in this file. Then: tm i18n "
        "import --lang {lang} <this file>.")
_FORMS = (" A key ending in .zero, .one, .two, .few, .many or .other is one form of a count, given in the English "
          "of its kind: write the form {name} uses for these numbers ({forms}). A form may say the count where the "
          "English leaves it out.")


def export(lang: str, out: Path, areas: tuple[str, ...] | list[str] = ()) -> Path:
    """Write what `lang` has no translation of (of `areas`, else all), with the English, for the agent to
    translate in place."""
    lang = _lang_arg(lang)
    en = english()
    source = wanted(lang, areas)
    strings = {k: source[k] for k in missing(lang, areas)}
    how = _HOW.format(name=name(lang), lang=lang)
    if any(k.rpartition(".")[0] in groups(en) for k in strings):
        how += _FORMS.format(name=name(lang), forms=_form_hint(lang))
    body = {"lang": lang, "how": how, "strings": strings}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    return out


def _lang_arg(lang: str) -> str:
    got = tag(lang)
    if got is None:
        raise ValueError(f"{lang!r} is not a language tag: use one such as pl, de or pt-BR.")
    if is_english(got):
        raise ValueError("English is the table itself: there is nothing to translate.")
    return got


def import_file(lang: str, path: Path) -> dict:
    """Keep the translation in `path` (an exported file, translated): every key known, no string empty, the
    English placeholders and markup in each. All or nothing. {imported, missing}."""
    lang = _lang_arg(lang)
    data = _read(Path(path))
    if tag(data.get("lang")) not in (None, lang):
        raise ValueError(f"{Path(path).name} is a translation into {data.get('lang')}, not {lang}.")
    strings = data.get("strings", {k: v for k, v in data.items() if k not in ("lang", "how")})
    if not isinstance(strings, dict):
        raise ValueError(f"{Path(path).name} has no strings mapping.")
    strings = {k: v for k, v in _flat(strings).items()}
    bad = problems(strings)
    if bad:
        raise ValueError(f"{Path(path).name} is not kept, nothing of it: " + "; ".join(bad)
                         + ". Correct those strings, then import again.")
    folder = cache_dir()
    if folder is None:
        raise ValueError(paths._NOT_FOUND)
    en = english()
    kept = _kept(lang)
    have, sources = dict(kept.get("strings") or {}), dict(kept.get("sources") or {})
    have.update(strings)
    counts = groups(en)
    sources.update({k: _source(_source_of(k, en, counts)) for k in strings})
    folder.mkdir(parents=True, exist_ok=True)
    target, tmp = folder / f"{lang}.yaml", folder / f"{lang}.yaml.tmp"
    tmp.write_text(yaml.safe_dump({"lang": lang, "strings": have, "sources": sources}, allow_unicode=True,
                                  sort_keys=True, width=1000), encoding="utf-8")
    os.replace(tmp, target)
    return {"imported": len(strings), "missing": missing(lang)}


# --- file names ----------------------------------------------------------------------------------------

def transliterate(text: str) -> str:
    """Latin letters with accents as plain ones (é -> e, ß -> ss, ł -> l, ś -> s), so a file name keeps them;
    letters of other scripts stay as they are."""
    out = []
    for ch in text:
        if ch in _LETTERS:
            out.append(_LETTERS[ch])
            continue
        parts = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in parts if not unicodedata.combining(c))
        out.append(base if base and base.isascii() and len(parts) > 1 else ch)
    return "".join(out)


# --- command line --------------------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    e = sub.add_parser("export", help="write what a language has no translation of, to translate")
    e.add_argument("--out", help="the file to write (default: i18n_<lang>.yaml here)")
    i = sub.add_parser("import", help="keep a translated file, after checking every key and placeholder")
    i.add_argument("file")
    c = sub.add_parser("check", help="what a language has no translation of yet")
    for sp in (e, c):
        sp.add_argument("--area", action="append", default=[], help="only this area's keys (brief, report, organic, ...)")
    for sp in sub.choices.values():
        sp.add_argument("--lang", required=True, help="the language's tag, e.g. pl")
        sp.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        lang = _lang_arg(args.lang)
        if args.action == "export":
            out = export(lang, Path(args.out or f"i18n_{lang}.yaml"), args.area)
            n = len(missing(lang, args.area))
            text = (f"Wrote {out}: {n} strings to translate into {name(lang)}. Translate each value in place, then "
                    f"tm i18n import --lang {lang} {out}." if n else f"{name(lang)} has every string already.")
            cli.emit(args, {"status": "done", "file": str(out), "missing": n, "message": text}, text)
            return 0
        if args.action == "import":
            got = import_file(lang, Path(args.file))
            left = got["missing"]
            text = (f"Kept {got['imported']} {name(lang)} strings."
                    + (f" {len(left)} are still missing: tm i18n export --lang {lang}." if left else
                       f" Every page can now be built in {name(lang)}."))
            cli.emit(args, {"status": "done", **got, "message": text}, text)
            return 0
        gaps = missing(lang, args.area)
        if gaps:
            text = (f"{name(lang)} has no translation of {len(gaps)} strings yet, so pages with them are built in "
                    f"English. Translate them once: tm i18n export --lang {lang}, then tm i18n import.")
            cli.emit(args, {"status": "stop", "complete": False, "missing": gaps, "message": text}, text)
            return 2
        text = f"{name(lang)} has every string."
        cli.emit(args, {"status": "done", "complete": True, "missing": [], "message": text}, text)
        return 0
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("i18n", _setup, _run)
