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
    translator(lang)               the same, the table read once (a page build)
    page_lang(wanted, *areas)      the language to build a page in: `wanted` when its table has every key of the
                                   areas, else English, with `.warning` saying so and what to run (loud, never
                                   silent)

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
    """What is wrong in a translation: a key the English table lacks, an empty string, other placeholders or
    other markup than the English."""
    en = english() if en is None else en
    out = []
    for key, text in strings.items():
        if key not in en:
            out.append(f"{key}: not a key of the English table")
        elif not isinstance(text, str) or not text.strip():
            out.append(f"{key}: empty")
        elif placeholders(text) != placeholders(en[key]):
            want = ", ".join(sorted("{" + p + "}" for p in placeholders(en[key]))) or "none"
            out.append(f"{key}: placeholders must be {want}, exactly as in English")
        elif _markup(text) != _markup(en[key]):
            out.append(f"{key}: keep the English markup ({' '.join(_markup(en[key])) or 'none'})")
    return out


def table(lang: str) -> dict[str, str]:
    """Every string `lang` has a valid translation of: shipped, then kept (the kept wins), the language's before
    its region's; a kept one made from an older English is left out."""
    if is_english(lang):
        return english()
    en = english()
    out: dict[str, str] = {}
    for code in _candidates(lang):
        shipped = _shipped(code)
        out.update({k: v for k, v in shipped.items() if not problems({k: v}, en)})
        kept = _kept(code)
        strings, sources = kept.get("strings") or {}, kept.get("sources") or {}
        out.update({k: v for k, v in strings.items()
                    if k in en and sources.get(k) == _source(en[k]) and not problems({k: v}, en)})
    return out


def missing(lang: str, areas: tuple[str, ...] | list[str] = ()) -> list[str]:
    """The English keys (of `areas`, else all) that `lang` has no translation of, in the table's order."""
    have = table(lang)
    return [k for k in english() if k not in have and (not areas or k.split(".")[0] in areas)]


@dataclass
class Translator:
    """`tr(key, **values)`: one string of the table in `lang`, filled. Read once, for a page build."""
    lang: str
    strings: dict[str, str] = field(repr=False)
    en: dict[str, str] = field(repr=False)

    def __call__(self, key: str, **values) -> str:
        if key not in self.en:
            raise KeyError(f"{key} is not a key of the English table (data/i18n/en.yaml).")
        text = self.strings.get(key)
        if text is None:
            raise Missing(f"{name(self.lang)} ({self.lang}) has no translation of {key}. Translate the table once: "
                          f"tm i18n export --lang {self.lang} --out i18n_{self.lang}.yaml, then tm i18n import.")
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


def export(lang: str, out: Path, areas: tuple[str, ...] | list[str] = ()) -> Path:
    """Write what `lang` has no translation of (of `areas`, else all), with the English, for the agent to
    translate in place."""
    lang = _lang_arg(lang)
    en = english()
    body = {"lang": lang, "how": _HOW.format(name=name(lang), lang=lang),
            "strings": {k: en[k] for k in missing(lang, areas)}}
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
    sources.update({k: _source(en[k]) for k in strings})
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
