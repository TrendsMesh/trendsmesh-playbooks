"""Video fonts: the Google Fonts subsets a Remotion composition loads for the run's market language, the family it
falls back to when its own font lacks them, and the check before a render that the font covers every letter on
screen (issue 3, problem 1).

The rules live in one table, `remotion/src/fonts.json`, which the compositions (`remotion/src/fonts.ts`) read too:

- a language (BCP 47) maps to a script by its longest known prefix (`zh-hant-tw`, `zh-hant`, `zh`); an unknown
  language, or none, is `latin`;
- a script lists the subsets to load (always `latin` and `latin-ext`, plus its own); a composition's font that has
  them all is used as it is, otherwise the whole composition uses the script's fallback (a Noto Sans family);
- the composition gets the language as its `language` prop. `tm render` fills it in from the run config when the
  props do not give one: `languages.market`, else `account.language` (a tag or an English or native language
  name), else an organic run's audience language (its channel profile's `audience_language`).

`check` reads the character ranges of the chosen family's subsets from the installed `@remotion/google-fonts`
package (the version the render uses) and stops when a letter, digit, mark, punctuation or currency sign of an
on-screen text is outside them, so no letter is drawn in the browser's fallback font. Emoji and other symbols are
not checked: the browser draws them from its emoji font on purpose.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tm.runfolder import RunFolder
from tm.tools import _common as c

TABLE = Path(__file__).resolve().parents[3] / "remotion" / "src" / "fonts.json"
PACKAGE = Path("node_modules") / "@remotion" / "google-fonts" / "dist" / "esm"
DEFAULT_SCRIPT = "latin"
CHECKED = ("L", "M", "N", "P", "Sc", "Sm")   # Unicode categories that must come from the font
NOT_LETTERS = {0x20E3, 0x200D} | set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0))  # keycap, ZWJ, selectors

# account.language is often written as a name ("Polish"): English and native names of the languages the table
# knows a script for, and of common Latin-script markets.
NAMES = {
    "english": "en", "polish": "pl", "polski": "pl", "german": "de", "deutsch": "de", "french": "fr",
    "français": "fr", "francais": "fr", "spanish": "es", "español": "es", "espanol": "es", "italian": "it",
    "italiano": "it", "portuguese": "pt", "português": "pt", "portugues": "pt", "dutch": "nl", "nederlands": "nl",
    "czech": "cs", "čeština": "cs", "cestina": "cs", "slovak": "sk", "slovenčina": "sk", "hungarian": "hu",
    "magyar": "hu", "romanian": "ro", "română": "ro", "romana": "ro", "croatian": "hr", "hrvatski": "hr",
    "slovenian": "sl", "slovenščina": "sl", "lithuanian": "lt", "lietuvių": "lt", "latvian": "lv",
    "latviešu": "lv", "estonian": "et", "eesti": "et", "finnish": "fi", "suomi": "fi", "swedish": "sv",
    "svenska": "sv", "danish": "da", "dansk": "da", "norwegian": "no", "norsk": "no", "turkish": "tr",
    "türkçe": "tr", "turkce": "tr", "indonesian": "id", "vietnamese": "vi", "tiếng việt": "vi",
    "russian": "ru", "русский": "ru", "ukrainian": "uk", "українська": "uk", "belarusian": "be",
    "bulgarian": "bg", "български": "bg", "serbian": "sr", "српски": "sr", "macedonian": "mk", "kazakh": "kk",
    "greek": "el", "ελληνικά": "el", "hindi": "hi", "हिन्दी": "hi", "arabic": "ar", "العربية": "ar",
    "persian": "fa", "farsi": "fa", "urdu": "ur", "hebrew": "he", "עברית": "he", "thai": "th", "ไทย": "th",
    "japanese": "ja", "日本語": "ja", "korean": "ko", "한국어": "ko", "chinese": "zh", "中文": "zh",
    "simplified chinese": "zh-Hans", "traditional chinese": "zh-Hant",
}
_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")


@lru_cache(maxsize=1)
def table() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


# --- the choice -----------------------------------------------------------------------------

def language_tag(value: object) -> str | None:
    """A BCP 47 tag from a config value: a tag as given (`pl`, `pl-PL`, `ru_RU` -> `ru-RU`), or a language name
    (`Polish`, `polski` -> `pl`); None for anything else."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.casefold() in NAMES:
        return NAMES[text.casefold()]
    tag = text.replace("_", "-")
    return tag if _TAG.match(tag) else None


def script_of(language: str | None) -> str:
    """The script a language is written in, by its longest prefix in the table; `latin` when unknown."""
    if not language:
        return DEFAULT_SCRIPT
    parts = language.strip().replace("_", "-").lower().split("-")
    languages = table()["languages"]
    for n in range(len(parts), 0, -1):
        key = "-".join(parts[:n])
        if key in languages:
            return languages[key]
    return DEFAULT_SCRIPT


def pick(primary: str, language: str | None) -> tuple[str, list[str]]:
    """(the family a composition whose font is `primary` uses, the subsets it loads) for the language. Same rule
    as fonts.ts: the font when it has every subset the script needs, else the script's fallback."""
    t = table()
    spec = t["scripts"][script_of(language)]
    family = primary if set(spec["subsets"]) <= set(t["families"][primary]["subsets"]) else spec["fallback"]
    return family, list(spec["subsets"])


# --- the market language --------------------------------------------------------------------

def market_language(run: RunFolder) -> tuple[str | None, str | None]:
    """(the run's market language as a BCP 47 tag, where it came from), or (None, None) when the run names none."""
    from tm import config, state
    from tm.playbooks import ORGANIC_VIDEO

    try:
        cfg = config.load(run)
    except ValueError:
        return None, None
    for path in ("languages.market", "account.language"):
        tag = language_tag(config._get(cfg, path))
        if tag:
            return tag, f"{path} in config.yaml"
    if state.load(run).playbook == ORGANIC_VIDEO:
        from tm import organic_config

        tag = language_tag(organic_config._audience_language(run, None, cfg.get("channels")))
        if tag:
            return tag, "the channel profile's audience_language"
    return None, None


# --- on-screen texts ------------------------------------------------------------------------

def _primary(comp: str, key: object = None) -> str:
    named = table()["compositions"][comp]
    if isinstance(named, dict):
        return named.get(key, next(iter(named.values()))) if isinstance(key, str) else next(iter(named.values()))
    return named


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def texts(comp: str, data: dict) -> list[tuple[str, str, str]]:
    """(where in the props, the text, the composition's own font family) of every text the composition draws.
    Keep in step with the compositions: a new on-screen field must be listed here."""
    out: list[tuple[str, str, str]] = []

    def add(where: str, text: object, family: str, upper: bool = False) -> None:
        if isinstance(text, str) and text:
            out.append((where, text, family))
            if upper and text.upper() != text:
                out.append((where, text.upper(), family))   # CSS uppercase can make new letters (ß -> SS)

    if comp == "HookSwap":
        for i, card in enumerate(_list(data.get("cards"))):
            for j, line in enumerate(_list(_dict(card).get("lines"))):
                add(f"cards[{i}].lines[{j}].text", _dict(line).get("text"), _primary(comp))
    elif comp == "WordCaptions":
        style = _dict(data.get("style"))
        upper = style.get("textTransform", "uppercase") != "none"
        for i, w in enumerate(_list(data.get("words"))):
            add(f"words[{i}].text", _dict(w).get("text"), _primary(comp, style.get("font")), upper)
        for i, p in enumerate(_list(data.get("probe"))):
            p = _dict(p)
            add(f"probe[{i}].text", p.get("text"), _primary(comp, p.get("font") or style.get("font")), upper)
    elif comp == "OrganicCaptions":
        for i, cap in enumerate(_list(data.get("captions"))):
            add(f"captions[{i}].text", _dict(cap).get("text"), _primary(comp))
    elif comp in ("RankingList", "RankingSplit"):
        for i, line in enumerate(_list(data.get("title"))):
            for j, w in enumerate(_list(line)):
                add(f"title[{i}][{j}].text", _dict(w).get("text"), _primary(comp))
        add("teaser", data.get("teaser"), _primary(comp))
        for i, it in enumerate(_list(data.get("items"))):
            for key in ("label", "score"):   # an item's `emoji` is drawn from the emoji font
                add(f"items[{i}].{key}", _dict(it).get(key), _primary(comp))
    elif comp == "QuizGrid":
        add("title", data.get("title"), _primary(comp))
        add("answerLine", data.get("answerLine"), _primary(comp))
        for i, o in enumerate(_list(data.get("options"))):
            for key in ("label", "name", "note"):
                add(f"options[{i}].{key}", _dict(o).get(key), _primary(comp))
    return out


# --- the installed package's character ranges ------------------------------------------------

@dataclass(frozen=True)
class FontInfo:
    family: str
    ranges: dict[str, tuple[tuple[int, int], ...]]   # subset (or chunk "[n]") -> code point ranges
    subsets: tuple[str, ...]                          # the family's named subsets
    italic: bool


def _ranges(text: str) -> tuple[tuple[int, int], ...]:
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part.upper().startswith("U+"):
            continue
        lo, _, hi = part[2:].partition("-")
        out.append((int(lo, 16), int(hi or lo, 16)))
    return tuple(out)


def font_info(esm: Path, family: str) -> FontInfo:
    """A family's subsets and their character ranges, read from its @remotion/google-fonts module (`getInfo`)."""
    path = Path(esm) / f"{family}.mjs"
    try:
        src = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise c.ToolError(f"Could not read the character ranges of the font {family} ({path}): {exc}. "
                          "Set the video tools up again: tm env install video --yes.") from None
    block = re.search(r"\n\s*unicodeRanges:\s*\{\n(.*?)\n\s*\},", src, re.S)
    listed = re.search(r"\n\s*subsets:\s*\[(.*?)\]", src, re.S)
    if not block or not listed:
        raise c.ToolError(f"The font module {path} does not list its character ranges as expected, so the "
                          "on-screen text cannot be checked against it.")
    ranges = {(m.group(1) or m.group(2)): _ranges(m.group(3))
              for m in re.finditer(r'^\s*(?:"([^"]+)"|([\w-]+)):\s*"([^"]*)"', block.group(1), re.M)}
    subsets = tuple(re.findall(r'"([^"]+)"', listed.group(1)))
    return FontInfo(family, ranges, subsets, bool(re.search(r"\n\s*italic:\s*\{", src)))


def coverage(info: FontInfo, subsets: list[str]) -> tuple[tuple[int, int], ...]:
    """The code points the subsets load, as @remotion/google-fonts resolves them: a subset with its own ranges,
    or, for a family split in numbered chunks (CJK), every chunk."""
    chunks = [k for k in info.ranges if re.fullmatch(r"\[\d+\]", k)]
    out: list[tuple[int, int]] = []
    for s in subsets:
        if s in info.ranges:
            out += info.ranges[s]
        elif s in info.subsets and chunks:
            out += [r for k in chunks for r in info.ranges[k]]
    return tuple(sorted(out))


def _covered(cp: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _checked(ch: str) -> bool:
    cat = unicodedata.category(ch)
    return ord(ch) not in NOT_LETTERS and (cat[0] in CHECKED or cat in CHECKED)


# --- the check ------------------------------------------------------------------------------

def check(comp: str, data: dict, language: str | None, esm: Path, source: str | None = None) -> tuple[str, list[str]]:
    """Stop (ToolStop) when an on-screen text has a letter the composition's font, as picked for the language,
    does not cover. Returns (the family, its subsets) of the composition's main font."""
    found = texts(comp, data)
    primary = _primary(comp, _dict(data.get("style")).get("font") if comp == "WordCaptions" else None)
    chosen = pick(primary, language)
    infos: dict[str, tuple[tuple[int, int], ...]] = {}
    missing: dict[str, list[str]] = {}
    families: dict[str, tuple[str, list[str]]] = {}
    for where, text, own in found:
        family, subsets = pick(own, language)
        families[family] = (family, subsets)
        letters = [ch for ch in text if _checked(ch)]
        if not letters:
            continue
        if family not in infos:
            infos[family] = coverage(font_info(esm, family), subsets)
        for ch in letters:
            if not _covered(ord(ch), infos[family]) and ch not in missing.setdefault(where, []):
                missing[where].append(ch)
    missing = {w: chars for w, chars in missing.items() if chars}
    if missing:
        said = f"{language} (from {source})" if language and source else language or "none given (Latin script)"
        fams = "; ".join(f"{f} with {', '.join(s)}" for f, s in families.values())
        rows = "; ".join(f"{w}: " + " ".join(f"'{ch}' (U+{ord(ch):04X})" for ch in chars[:8])
                         + (" ..." if len(chars) > 8 else "") for w, chars in missing.items())
        raise c.ToolStop(
            f"The on-screen text has letters the {comp} font does not have for the market language {said}, so "
            f"they would be drawn in a fallback font. Font: {fams}. Missing: {rows}. Nothing was rendered. If the "
            "text is in another language than the run's market language, set the market language in config.yaml "
            "(languages.market, a BCP 47 tag such as uk or el) or give `language` in the props; otherwise change "
            "the text.")
    return chosen
