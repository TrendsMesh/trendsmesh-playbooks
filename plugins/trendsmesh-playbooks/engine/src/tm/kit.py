"""The posting kit (OV11), shared by the script and the AI video outputs: `tm kit check` and `tm kit md`.

A kit is the handoff's `04_final/kits/<id>_kit_vNN.json` (`schemas/pb3_kit.schema.json`) plus the plugin's
block, which the agent writes with it:

    plugin = {"ai_label": bool, "trending_sound": {"name", "evidence", "replaces_track": bool} | null,
              "business_alternative": str | null, "platforms": [...], "youtube_thumbnail": bool}

`check(kit, ctx)` holds the platform rules a program can read (PLAYBOOK OV11): the limits of
`data/organic-video/platform_rules.yaml` (`RULES`), each with its source and the day it was checked there, and
`references/posting-kit.md` (the rules in words, written to the same date, `RULES["as_of"]`). What it cannot read
stays with the skill: that line 1 is a natural search phrase, that an emoji means something, that the product is a
soft line. `posting_problems` adds what `tm kit check` asks of a kit written at G2 (and not of a script's, E3):
`rules_read`, the rules' date its writer read, and `search_phrase`, which leads TikTok's first line.

What the user pastes (`paste`): on TikTok, Instagram and Facebook one description with the hashtags in it (the
caption, then the hashtags it does not hold yet); on YouTube the title, the description with its hashtags, and the
tags. The rest of a platform's block (`steps`: cover, AI label, sound, product) is what to do at posting, in plain
words. The limits are checked on the text as pasted. A field the kit does not use is a warning (`unused`), and so are
rules older than `RULES["max_age_days"]` (`stale_rules`) and a search phrase none of whose words are in the run's
trend data (`search_warning`).

The AI label by production type: photoreal (`ai_label` `required` or `on`): on, with its in-app step on every
platform; a clearly animated style (`not_required`): off, unless the user asked for it on (their words in
`plugin.ai_label_request`, or `--ai-label on`).

Where the context comes from (`context_of`), each flag winning over the run:
- language, platforms and account type: the run's config (`platforms`, else the channel profile's)
  and the channel profile (`audience_language`, `account_type`), the profile of the proposal's channel
  (`00_raw/proposal.json`), else of the config's first channel;
- product level: the latest checked pack (an AI video's), else `00_raw/proposal.json` (Task 6), the
  production run's start;
- AI label: `--ai-label`, else the latest checked pack's (`organic_pack.ai_label`: required for an AI
  host, not required for a stylised animation alone, on for other AI footage), else `not_required` for a
  script (which is filmed by a person).

Three readings of the rules that the reference run's approved kits fix (the controller's rulings):
- "at most one genuine question": the hook sentence of a caption (its first, when it is a question) is
  the search phrase and is not counted, so the question to the audience is the one that counts. The
  first sentence ends at the first `?`, `.`, `!` or line break that is not a decimal point or an ellipsis;
- the cover text takes 2 to 7 words (the brief's 2 to 4 contradicts M1 v02 at 6 and the pet store at 7);
- characters are counted as code points (`len`), the conservative reading: a ZWJ or flag emoji counts
  more than the platform may count it; a limit the platform counts otherwise says so in the rules file (`unit`:
  TikTok's UTF-16 runes, YouTube's description in bytes).
A filmed script (`filmed_by_person`) needs no AI label, whatever `ai_label` says.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

from tm import (brand, cli, config, i18n, json_schema, manifest, organic_final, organic_proposals, paths, state,
                stepchecks, trend_spool)
from tm.config import Problem
from tm.runfolder import ReadOnlyError, RunFolder
from tm.stops import AGAIN, Stop

SCHEMA = Path(__file__).parent / "schemas" / "pb3_kit.schema.json"
RULES_FILE = paths.bundled_data() / "organic-video" / "platform_rules.yaml"
DOCUMENT = "references/posting-kit.md"         # at the plugin root: the rules in words, of RULES["as_of"]
KEY = "kit"                                    # run.json checked[kit]: the latest kit file that passed
PLATFORMS = ("tiktok", "instagram", "youtube", "facebook")
PLATFORM_NAMES = {"tiktok": "TikTok", "instagram": "Instagram Reels", "youtube": "YouTube Shorts",
                  "facebook": "Facebook Reels"}
BRAND_LEVELS = ("incidental", "featured", "hero")   # the product levels that need "Your brand"
AI_LABELS = ("required", "on", "not_required")


def _load_rules() -> dict:
    data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    data["as_of"] = str(data["as_of"])
    return data


RULES = _load_rules()                          # data/organic-video/platform_rules.yaml, dated


def _limit(platform: str, name: str) -> dict:
    return RULES["platforms"].get(platform, {}).get(name) or {}


HASHTAGS = {p: (_limit(p, "hashtags")["min"], _limit(p, "hashtags")["max"])
            for p in ("tiktok", "instagram", "facebook")}   # YouTube's are in its description
YOUTUBE_HASHTAGS = (_limit("youtube", "hashtags")["min"], _limit("youtube", "hashtags")["max"])
YOUTUBE_TITLE_MAX = _limit("youtube", "title_max")["value"]
INSTAGRAM_LINE_MAX = _limit("instagram", "first_line_max")["value"]
# The fields a kit is read by (the page, the .md, the checks); any other is a warning (`unused`).
USED = {"id", "version", "date", "channel", "language", "video", "cover", "product", "platforms", "plugin",
        "rules_read", "search_phrase"}
USED_COVER = {"file", "frame_sec", "text"}
USED_PLUGIN = {"ai_label", "ai_label_request", "trending_sound", "business_alternative", "platforms",
               "youtube_thumbnail"}
STEPS = ("cover", "ai_label", "sound", "product")   # a platform's posting steps: instructions, never pasted
USED_BLOCK = {"youtube": ("title", "description", "hashtags", "tags", *STEPS),
              **{p: ("caption", "hashtags", *STEPS) for p in ("tiktok", "instagram", "facebook")}}
NO_ANGLES = re.compile(r"[<>]")                     # YouTube's title and description refuse < and >
MENTION = re.compile(r"(?<![\w@])@[\w.]+")
# The brief's bait phrases; BAIT_FORMS says what else each one catches.
BAIT = {"en": ("comment", "tag a friend", "tag someone", "share this with", "follow for more", "like if"),
        "pl": ("skomentuj", "oznacz", "udostępnij", "obserwuj po więcej", "daj lajka")}
BAIT_FORMS = {   # phrase -> a pattern for it and its inflections, as whole words ("commentary" passes)
    "comment": r"comment(?:s|ed|ing)?", "tag a friend": r"tag(?:s|ged|ging)?\s+a\s+friends?",
    "tag someone": r"tag(?:s|ged|ging)?\s+someone", "share this with": r"shar(?:e|es|ed|ing)\s+this\s+with",
    "follow for more": r"follow(?:s|ed|ing)?\s+for\s+more", "like if": r"like(?:s|d)?\s+if",
    "skomentuj": r"skomentuj(?:cie)?", "oznacz": r"oznacz(?:cie)?", "udostępnij": r"udostępnij(?:cie)?",
    "obserwuj po więcej": r"obserwuj(?:cie)?\s+po\s+więcej", "daj lajka": r"daj(?:cie)?\s+lajka"}
COVER_WORDS = (2, 7)
DOMAIN = re.compile(r"\b[\w-]+\.(com|org|net|io|pl|edu|gov)\b", re.IGNORECASE)
LINK = re.compile(r"http|www\.", re.IGNORECASE)
SOURCES = re.compile(r"(?<!\w)(sources?|źródł[aoó]\w*|źródeł)\s*:", re.IGNORECASE)   # "Źródła: …" (round 38)
WORD = re.compile(r"\w+")
HASHTAG = re.compile(r"#\w+")


@dataclass(frozen=True)
class KitContext:
    language: str                                          # the audience language
    platforms: tuple[str, ...]
    account_type: str
    product_level: str
    ai_label: Literal["required", "on", "not_required"]
    filmed_by_person: bool = False


def _bait() -> list[re.Pattern]:
    return [re.compile(rf"(?<!\w){BAIT_FORMS[p]}(?!\w)", re.IGNORECASE) for words in BAIT.values() for p in words]


_BAIT = _bait()


def _BAIT_MATCH(text: str) -> bool:   # noqa: N802 - the compiled patterns applied to a text (tests)
    return any(p.search(text) for p in _BAIT)


@functools.lru_cache(maxsize=None)
def _schema() -> dict:
    return json_schema.load(SCHEMA)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(block: dict) -> list[tuple[str, str]]:
    """The post text of one platform: every caption, title, description, hashtag, cover, product and sound
    text, with its field."""
    out = [(k, block[k]) for k in ("caption", "title", "description", "cover", "product", "sound")
           if isinstance(block.get(k), str)]
    for field in ("hashtags", "tags"):
        tags = block.get(field)
        out += [(field, t) for t in tags if isinstance(t, str)] if isinstance(tags, list) else []
    return out


# --- what the user pastes, and what they do at posting -----------------------------------------------------

def _strings(value: object) -> list[str]:
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def hashtags_in(text: str) -> list[str]:
    """The different hashtags of `text`, in order (case does not make another one)."""
    seen: dict[str, str] = {}
    for tag in HASHTAG.findall(text):
        seen.setdefault(tag.casefold(), tag)
    return list(seen.values())


def _with_hashtags(text: str, hashtags: list[str]) -> str:
    """`text` with the hashtags it does not hold yet after a blank line: what the user pastes."""
    base = text.rstrip()
    held = {t.casefold() for t in hashtags_in(base)}
    more = [t for t in dict.fromkeys(hashtags) if t.casefold() not in held]
    return (base + ("\n\n" if base else "") + " ".join(more)) if more else base


def _main_text(name: str, block: dict) -> tuple[str, str]:
    """(its field, its text): a platform's own text, its caption (YouTube: its description), else the other one."""
    first, second = ("description", "caption") if name == "youtube" else ("caption", "description")
    for field in (first, second):
        if _text(block.get(field)):
            return field, block[field]
    return first, ""


def paste(name: str, block: dict) -> list[tuple[str, str]]:
    """The texts the user pastes on platform `name`, each (what it is, the text): TikTok, Instagram and Facebook one
    `description` with its hashtags; YouTube its `title`, its `description` with its hashtags and its `tags` (as
    YouTube Studio takes them, separated by commas). A text that is empty is left out."""
    _, text = _main_text(name, block)
    out = [("description", _with_hashtags(str(text), _strings(block.get("hashtags"))))]
    if name == "youtube":
        out = [("title", str(block.get("title") or "").strip()), *out, ("tags", ", ".join(_strings(block.get("tags"))))]
    return [(what, t) for what, t in out if t]


def steps(name: str, block: dict) -> list[tuple[str, str]]:   # noqa: ARG001 - the same fields on every platform
    """What to do at posting on a platform, never pasted: its cover, AI label, sound and product steps, in that
    order, as the kit writes them (in plain words)."""
    return [(field, block[field].strip()) for field in STEPS if _text(block.get(field))]


def tags_length(tags: list[str]) -> int:
    """YouTube's count of a tag list (the videos resource): every tag, a comma between two, and the quotes it puts
    around a tag with a space ("Foo-Baz" is 7, "Foo Baz" 9)."""
    tags = _strings(tags)
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


def _length(text: str, unit: str) -> int:
    if unit == "utf16":
        return len(text.encode("utf-16-le")) // 2
    if unit == "bytes":
        return len(text.encode("utf-8"))
    return len(text)


_UNIT_WORD = {"utf16": "characters (UTF-16)", "bytes": "bytes", "characters": "characters"}


def _too_long(bad, field: str, platform: str, what: str, text: str, limit: str) -> None:
    spec = _limit(platform, limit)
    if not spec:
        return
    unit = spec.get("unit", "characters")
    n, most = _length(text, unit), spec["value"]
    if n > most:
        bad(field, f"{PLATFORM_NAMES[platform]}'s {what} is {n} {_UNIT_WORD[unit]} as pasted; it takes at most {most}.",
            f"Shorten it to {most} {_UNIT_WORD[unit]}, hashtags included.")


def _hashtag_count(bad, field: str, platform: str, text: str) -> None:
    low, high = HASHTAGS[platform] if platform in HASHTAGS else YOUTUBE_HASHTAGS
    n = len(hashtags_in(text))
    if not low <= n <= high:
        where = "description" if platform == "youtube" else "text"
        bad(field, f"{PLATFORM_NAMES[platform]} has {n} hashtags in its {where} to paste; it takes "
            + (f"{low} to {high}." if low else f"at most {high}."), f"Give {PLATFORM_NAMES[platform]} "
            + (f"{low} to {high}" if low else f"{high} or fewer") + " specific hashtags.")


_STOP = re.compile(r"\.{2,}|…|[?.!\n]")


def _first_sentence_end(text: str) -> int:
    """Where a caption's hook sentence ends when it ends with a question mark, else 0. A decimal point
    ("2.5") and an ellipsis do not end a sentence."""
    for m in _STOP.finditer(text):
        mark = m.group()
        if mark == "…" or len(mark) > 1:
            continue
        if mark == "." and text[m.start() - 1:m.start()].isdigit() and text[m.end():m.end() + 1].isdigit():
            continue
        return m.end() if mark == "?" else 0
    return 0


def _questions(caption: str) -> int:
    return caption[_first_sentence_end(caption):].count("?")


def _post_text(bad, field: str, text: str) -> None:
    """The rules every post text keeps: no link or domain, no engagement bait, no sources."""
    if LINK.search(text) or DOMAIN.search(text):
        bad(field, "The text holds a link or a domain.", "Take it out: links go on the channel page.")
    if any(p.search(text) for p in _BAIT):
        bad(field, "The text is engagement bait.", "Ask a genuine question instead of asking for an action.")
    if SOURCES.search(text):
        bad(field, "The text names sources.", "Keep sources out of every post text (round 38).")


def _plugin(kit: dict, ctx: KitContext, bad) -> dict:
    plugin = kit.get("plugin")
    if not isinstance(plugin, dict):
        bad("plugin", "The kit has no plugin block.",
            "Add plugin: {ai_label, trending_sound, business_alternative, platforms, youtube_thumbnail}.")
        return {}
    if not isinstance(plugin.get("ai_label"), bool):
        bad("plugin.ai_label", "plugin.ai_label is not true or false.", "Say whether the AI label is on.")
    sound = plugin.get("trending_sound")
    if sound is not None:
        if not (isinstance(sound, dict) and _text(sound.get("name")) and _text(sound.get("evidence"))
                and isinstance(sound.get("replaces_track"), bool)):
            bad("plugin.trending_sound", "The trending sound needs a name, its evidence and replaces_track (true or false).",
                "Fill the three, or set trending_sound to null.")
    if "platforms" in plugin and not (isinstance(plugin["platforms"], list)
                                      and all(p in PLATFORMS for p in plugin["platforms"])):
        bad("plugin.platforms", f"plugin.platforms is not a list of {', '.join(PLATFORMS)}.", "List the ticked platforms.")
    return plugin


def _ai_label(kit: dict, plugin: dict, ctx: KitContext, bad) -> None:
    """The AI label by production type (the module docstring); a filmed script needs none."""
    if ctx.filmed_by_person:
        return
    label, request = plugin.get("ai_label"), plugin.get("ai_label_request")
    if request is not None and not isinstance(request, str):
        bad("plugin.ai_label_request", "plugin.ai_label_request is not text.", "Put the user's words in it, or leave it out.")
    if label is False and ctx.ai_label in ("required", "on"):
        bad("plugin.ai_label", f"The AI label must be on here (it is {ctx.ai_label.replace('_', ' ')}): the video "
            "shows photoreal AI.", "Set plugin.ai_label to true and give the in-app step on each platform.")
    if label is True and ctx.ai_label == "not_required" and not _text(request):
        bad("plugin.ai_label", "The video is a clearly animated style, so the AI label is off by default.",
            "Set plugin.ai_label to false, or, when the user asked for it on, put their words in "
            "plugin.ai_label_request.")
    if label is True:
        for name, block in kit["platforms"].items():
            if isinstance(block, dict) and not _text(block.get("ai_label")):
                bad(f"platforms.{name}.ai_label", f"The AI label is on, and {PLATFORM_NAMES[name]} has no step for it.",
                    f"Write where to switch it on in {PLATFORM_NAMES[name]}, in plain words.")


def check(kit: dict, ctx: KitContext) -> list[Problem]:
    """What in a posting kit breaks the shape or the platform rules; empty when it holds."""
    out: list[Problem] = []

    def bad(field: str, what: str, todo: str) -> None:
        out.append(Problem(field, what, todo))

    for line in json_schema.problems(kit, _schema(), name="kit"):
        bad(line.split(" ", 1)[0], line, "Write the kit in the shape of the posting kit schema.")
    if out or not isinstance(kit, dict):
        return out
    plugin = _plugin(kit, ctx, bad)
    cover = (kit.get("cover") or {}).get("text")
    words = len(WORD.findall(cover)) if isinstance(cover, str) else 0
    if _text(cover) and not COVER_WORDS[0] <= words <= COVER_WORDS[1]:
        bad("cover.text", f"The cover text has {words} words; it takes {COVER_WORDS[0]} to {COVER_WORDS[1]}.",
            f"Write {COVER_WORDS[0]} to {COVER_WORDS[1]} words of keyword text.")
    for field, text in (("cover.text", cover), ("product", kit.get("product"))):
        if isinstance(text, str):
            _post_text(bad, field, text)
    if kit.get("language") != ctx.language:
        bad("language", f"The kit is in {kit.get('language')!r}, and the audience language is {ctx.language!r}.",
            f"Write the whole kit in {ctx.language}.")
    ticked = tuple(plugin.get("platforms") or ctx.platforms)
    outside = [p for p in ticked if p not in ctx.platforms]
    if outside:
        bad("plugin.platforms", f"{', '.join(outside)} is not among the run's platforms ({', '.join(ctx.platforms)}).",
            "Tick only platforms the run was set up for.")
    have = tuple(kit["platforms"])
    extra, missing = [p for p in have if p not in ticked], [p for p in ticked if p not in have]
    if extra:
        bad("platforms", f"The kit has {', '.join(extra)}, which is not ticked.", "Leave out the platforms that are not ticked.")
    if missing:
        bad("platforms", f"The kit has no {', '.join(missing)}, which is ticked.", "Write a block for each ticked platform.")
    for name in have:
        block = kit["platforms"][name]
        where = f"platforms.{name}"
        field, _ = _main_text(name, block)
        pasted = dict(paste(name, block))
        text = pasted.get("description", "")
        _hashtag_count(bad, f"{where}.{'description' if name == 'youtube' else 'hashtags'}", name, text)
        if name == "youtube":
            title = str(block.get("title") or "")
            if not title.strip() or len(title) > YOUTUBE_TITLE_MAX:
                bad(f"{where}.title", f"The title is {len(title)} characters; it takes 1 to {YOUTUBE_TITLE_MAX}.",
                    f"Write a title of at most {YOUTUBE_TITLE_MAX} characters.")
            _too_long(bad, f"{where}.{field}", name, "description", text, "description_max")
            for what, value in (("title", title), (field, text)):
                if NO_ANGLES.search(value):
                    bad(f"{where}.{what}", f"YouTube's {what} holds < or >, which YouTube refuses.",
                        "Take the < and > out.")
            n = tags_length(block.get("tags") or [])
            most = _limit("youtube", "tags_max")["value"]
            if n > most:
                bad(f"{where}.tags", f"YouTube's tags are {n} characters as YouTube counts them (a comma between two, "
                    f"quotes around a tag with a space); they take at most {most}.", f"Drop tags until they fit {most}.")
        else:
            _too_long(bad, f"{where}.{field}", name, "text", text, "text_max")
        if name == "instagram":
            lines = text.splitlines()
            line = lines[0] if lines else ""
            if len(line) > INSTAGRAM_LINE_MAX:
                bad(f"{where}.caption", f"The first line is {len(line)} characters; Instagram shows {INSTAGRAM_LINE_MAX}.",
                    f"Shorten line 1 to {INSTAGRAM_LINE_MAX} characters, hook and search phrase first.")
            mentions, most = len(MENTION.findall(text)), _limit("instagram", "mentions_max").get("value")
            if most is not None and mentions > most:
                bad(f"{where}.caption", f"The text tags {mentions} accounts; Instagram takes at most {most}.",
                    f"Keep to {most} @ tags.")
        if name == "tiktok" and ctx.product_level in BRAND_LEVELS and not _text(block.get("product")):
            bad(f"{where}.product", f"The product is {ctx.product_level}, so TikTok needs the “Your brand” disclosure.",
                "Fill product with the disclosure step.")
        for field, text in _texts(block):
            _post_text(bad, f"{where}.{field}", text)
        caption = block.get("caption")
        if isinstance(caption, str) and _questions(caption) > 1:
            bad(f"{where}.caption", "The caption asks more than one question.", "Keep one genuine question.")
    _ai_label(kit, plugin, ctx, bad)
    sound = plugin.get("trending_sound")
    if isinstance(sound, dict):
        if ctx.account_type == "business" and not _text(plugin.get("business_alternative")):
            bad("plugin.business_alternative", "A business account cannot use a trending sound from the app's library.",
                "Name a commercial-library alternative.")
        if sound.get("replaces_track") is True and "_nosound" not in str(kit.get("video") or ""):
            bad("video", "The trending sound replaces the track, so the video needs its _nosound file.",
                "Name the _nosound export in video.")
    return out


def posting_problems(kit: dict, ctx: KitContext) -> list[Problem]:
    """`check`, and what `tm kit check` asks of a kit written at G2: `rules_read`, the date of the rules its writer
    read (`RULES["as_of"]`, posting-kit.md's), and, with TikTok, the `search_phrase` leading TikTok's first line."""
    out = check(kit, ctx)
    if not isinstance(kit, dict) or json_schema.problems(kit, _schema(), name="kit"):   # not in the shape
        return out

    def bad(field: str, what: str, todo: str) -> None:
        out.append(Problem(field, what, todo))

    read, as_of = kit.get("rules_read"), RULES["as_of"]
    if not _text(read):
        bad("rules_read", "The kit does not say which platform rules it was written to.",
            f"Read {DOCUMENT} at the plugin root (the rules as of {as_of}) before writing the kit, then record "
            f"rules_read: \"{as_of}\".")
    elif str(read).strip() != as_of:
        bad("rules_read", f"The kit was written to the rules of {read}, and the plugin's are of {as_of}.",
            f"Read {DOCUMENT} again, write the kit to it and record rules_read: \"{as_of}\".")
    blocks = kit.get("platforms") if isinstance(kit.get("platforms"), dict) else {}
    tiktok = blocks.get("tiktok")
    if isinstance(tiktok, dict):
        phrase = kit.get("search_phrase")
        if not _text(phrase):
            bad("search_phrase", "The kit has no search phrase, which TikTok's first line leads with.",
                "Take it from the run's trend data (the hook's or the topic's own words) and record it in "
                "search_phrase.")
        else:
            field, caption = _main_text("tiktok", tiktok)
            first = (str(caption).splitlines() or [""])[0]
            if phrase.strip().casefold() not in first.casefold():
                bad(f"platforms.tiktok.{field}", f"TikTok's first line does not hold the search phrase "
                    f"“{phrase.strip()}”.", "Lead line 1 with the hook and the search phrase, word for word.")
    return out


def unused(kit: dict) -> list[str]:
    """The fields of `kit` nothing reads (not shown, not checked), in the kit's order: a warning, never a refusal."""
    if not isinstance(kit, dict):
        return []
    out = [k for k in kit if k not in USED]
    cover = kit.get("cover")
    out += [f"cover.{k}" for k in cover if k not in USED_COVER] if isinstance(cover, dict) else []
    blocks = kit.get("platforms") if isinstance(kit.get("platforms"), dict) else {}
    for name, block in blocks.items():
        if not isinstance(block, dict) or name not in USED_BLOCK:
            continue
        used = set(USED_BLOCK[name]) | {_main_text(name, block)[0]}
        out += [f"platforms.{name}.{k}" for k in block if k not in used]
    plugin = kit.get("plugin")
    out += [f"plugin.{k}" for k in plugin if k not in USED_PLUGIN] if isinstance(plugin, dict) else []
    return out


def stale_rules(today: date | None = None) -> str | None:
    """A warning when the rules are older than `RULES["max_age_days"]`: they still apply, and may have changed."""
    as_of = date.fromisoformat(RULES["as_of"])
    age = ((today or date.today()) - as_of).days
    if age <= RULES["max_age_days"]:
        return None
    return (f"The platform rules were checked against the platforms' pages on {as_of} ({age} days ago): limits may "
            f"have changed since. Tell the user to check the text in each app's own preview before posting; a newer "
            f"plugin version may have newer rules.")


_STEM = 5     # a word of the search phrase is found in the trend data by its first letters (Polish inflects)


def _stems(text: str) -> set[str]:
    return {w.casefold()[:_STEM] for w in WORD.findall(text) if len(w) >= 4 and not w.isdigit()}


def search_warning(kit: dict, trend_text: str | None) -> str | None:
    """A warning when none of the search phrase's words is in the run's trend data (`trend_text`, the proposal's
    topic and hook): a guessed phrase, which the user should check in Creator Search Insights."""
    phrase = kit.get("search_phrase") if isinstance(kit, dict) else None
    if not (_text(phrase) and _text(trend_text)):
        return None
    words = _stems(str(phrase))
    if not words or words & _stems(str(trend_text)):
        return None
    return (f"The search phrase “{phrase.strip()}” has none of the run's trend words (the proposal's topic and hook): "
            "take it from them, and tell the user to check it in TikTok's Creator Search Insights before posting.")


def trend_text(run: RunFolder) -> str | None:
    """The run's trend data a search phrase comes from: the started proposal's title, beats (the hook first), why
    and type, from `00_raw/proposal.json`; None without them."""
    path = run.path / organic_proposals.PROPOSAL_FILE
    try:
        proposal = json.loads(path.read_text(encoding="utf-8-sig")).get("proposal") if path.is_file() else None
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(proposal, dict):
        return None
    parts = [proposal.get(k) for k in ("title", "why", "video_type")] + list(proposal.get("beats") or [])
    text = " ".join(p for p in parts if isinstance(p, str))
    return text or None


# --- the .md beside the JSON ------------------------------------------------------------------------

LABELS = ("title", "video", "cover", "product", "paste", "name", "description", "tags", "steps", "search", "ai",
          "sound", "trending", "alternative")             # the string table's organic.kit_md.<label>
PASTE_LABELS = {("youtube", "title"): "name", ("youtube", "description"): "description", ("youtube", "tags"): "tags"}
STEP_LABELS = {"cover": "cover", "ai_label": "ai", "sound": "sound", "product": "product"}


def labels(lang: str | None) -> dict[str, str]:
    """The .md's labels in `lang` (the run's working language) when its table has every organic string, else in
    English (`i18n.page_lang`); `search_check` is the search phrase's step, shared with the delivery page."""
    tr = i18n.translator(i18n.page_lang(lang, "organic").lang)
    return {label: tr(f"organic.kit_md.{label}") for label in LABELS} | {"search_check": tr("organic.kit.search_check")}


def _fence(text: str) -> list[str]:
    return ["```", text, "```"]


def to_md(kit: dict, lang: str) -> str:
    """templates/posting_kit_template.md's sections (its `## ` headings are `PLATFORM_NAMES`, which a test
    compares to the template), filled: one per platform in the kit, its labels in `lang` (`labels`). Each holds
    the texts to paste as they are (`paste`), then what to do at posting (`steps`, and on TikTok the search
    phrase to check)."""
    t = labels(lang)
    plugin = kit.get("plugin") or {}
    cover = (kit.get("cover") or {}).get("file")
    head = [f"# {t['title']} {kit.get('id')} {kit.get('version')} ({kit.get('channel')})", ""]
    meta = [f"{t['video']}: `{kit.get('video')}`"] + ([f"{t['cover'].lower()}: `{cover}`"] if cover else []) \
        + ([f"{t['product'].lower()}: {kit['product']}"] if kit.get("product") else [])
    lines = head + [" · ".join(meta), ""]
    for name, block in (kit.get("platforms") or {}).items():
        lines += [f"## {PLATFORM_NAMES.get(name, name)}"]
        block = block if isinstance(block, dict) else {}
        for what, text in paste(name, block):
            lines += [f"**{t[PASTE_LABELS.get((name, what), 'paste')]}:**"] + _fence(text)
        todo = [f"- **{t[STEP_LABELS[field]]}:** {text}" for field, text in steps(name, block)]
        if name == "tiktok" and _text(kit.get("search_phrase")):
            todo.append(f"- **{t['search']}:** “{kit['search_phrase'].strip()}”. {t['search_check']}")
        if todo:
            lines += [f"**{t['steps']}:**", *todo]
        lines.append("")
    sound = plugin.get("trending_sound")
    if isinstance(sound, dict):
        lines += [f"**{t['trending']}:** {sound.get('name')} ({sound.get('evidence')})", ""]
    if plugin.get("business_alternative"):
        lines += [f"**{t['alternative']}:** {plugin['business_alternative']}", ""]
    return "\n".join(lines).rstrip() + "\n"


# --- the run's context ------------------------------------------------------------------------------

def context_of(run: RunFolder, *, language: str | None = None, account_type: str | None = None,
               product_level: str | None = None, ai_label: str | None = None,
               platforms: tuple[str, ...] | None = None) -> KitContext:
    """The kit's context: each given value, else the run's config, its channel profile and
    `00_raw/proposal.json` (the module docstring). A Stop names what is missing."""
    cfg = config.load(run)
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    profile: dict = {}
    proposal: dict = {}
    path = run.path / organic_proposals.PROPOSAL_FILE
    if path.is_file():
        try:
            proposal = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            raise Stop(f"{organic_proposals.PROPOSAL_FILE} is not valid JSON; this run's start is damaged. Start the "
                       f"idea again; {AGAIN}.") from None
    slug = proposal.get("channel") if _text(proposal.get("channel")) else (channels[0] if channels else None)
    if slug:
        try:
            profile = brand.latest(trend_spool.workspace_of(run), slug, kind="channel") or {}
        except ValueError:
            profile = {}
    from tm import organic_pack   # it reads organic_proposals, which this module imports too: imported here

    pack = organic_pack.checked_pack(run) or {}
    language = language or profile.get("audience_language")
    account_type = account_type or profile.get("account_type")
    ticked = tuple(platforms or cfg.get("platforms") or profile.get("platforms") or ())
    packed = (pack.get("product") or {}).get("level")
    packed = organic_proposals.PRODUCT_WORDS.get(str(packed).strip().lower(), packed) if packed else None
    level = product_level or packed or proposal.get("product_level")
    filmed = cfg.get("output") == "script" and ai_label is None   # a script is filmed by a person, unless --ai-label says otherwise
    if ai_label is None:
        if pack:
            ai_label = organic_pack.ai_label(pack)
        elif cfg.get("output") == "script":
            ai_label = "not_required"
        else:
            raise Stop(f"This run's AI label comes from its checked pack, which is not checked yet (tm organic pack check "
                       f"--stage pack). Check it first, or give the label with --ai-label ({', '.join(AI_LABELS)}); {AGAIN}.")
    missing = [n for n, v in (("the audience language (--audience-language)", language),
                              ("the account type (--account-type)", account_type),
                              ("the platforms", ticked), ("the product level (--product-level)", level)) if not v]
    if missing:
        raise Stop(f"The kit cannot be checked without {', '.join(missing)}: the run's channel profile and "
                   f"{organic_proposals.PROPOSAL_FILE} do not give it. Give it on the command line, or write the "
                   f"channel profile with tm brand; {AGAIN}.")
    if ai_label not in AI_LABELS:
        raise ValueError(f"--ai-label is one of {', '.join(AI_LABELS)}, not {ai_label!r}.")
    return KitContext(str(language), ticked, str(account_type), str(level), ai_label, filmed)  # type: ignore[arg-type]


# --- step check -------------------------------------------------------------------------------------

def kit_gap(run: RunFolder) -> str | None:
    """The `kit_checked` step check (G2): the latest 04_final/kits/<id>_kit_vNN.json of the run's idea passed
    `tm kit check` and is unchanged since. Reads only."""
    pid = organic_final.idea_id(run)
    if pid is None:
        return organic_final.NO_ID
    gap = stepchecks.fresh(run, KEY, organic_final.KITS, f"{pid}_kit", "json")
    return None if gap is None else f"{gap} (tm kit check --run <run> --file {organic_final.KITS}/{pid}_kit_vNN.json)"


# --- command line -----------------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="check a posting kit against the platform rules and mark it checked")
    md = sub.add_parser("md", help="write the .md beside a checked kit's JSON")
    for s in (c, md):
        s.add_argument("--run", required=True, help="the run folder")
        s.add_argument("--file", required=True, help="the kit, 04_final/kits/<id>_kit_vNN.json")
        s.add_argument("--json", action="store_true")
    c.add_argument("--audience-language", help="the kit's language (default: the channel profile's)")
    c.add_argument("--account-type", choices=brand.ACCOUNT_TYPES, help="default: the channel profile's")
    c.add_argument("--product-level", choices=tuple(organic_proposals.PRODUCT_LEVELS),
                   help="default: the proposal's, in 00_raw/proposal.json")
    c.add_argument("--ai-label", choices=AI_LABELS, help="default: the checked pack's (not_required for a clearly "
                   "animated style), not_required for a script; on when the user asked for the label")


def _load(run: RunFolder, given: str) -> tuple[Path, str, dict]:
    path = run.given(given).resolve()
    if not path.is_file():
        raise ValueError(f"{given} is not a file.")
    try:
        rel = path.relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{given} is not inside the run folder {run.path}.") from None
    try:
        return path, rel, json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{rel} is not valid JSON ({exc}). Write it again as one JSON object, then check it again; "
                   f"{AGAIN}.") from None


def _check(args: argparse.Namespace) -> int:
    run = RunFolder.open(Path(args.run))
    path, rel, data = _load(run, args.file)
    ctx = context_of(run, language=args.audience_language, account_type=args.account_type,
                     product_level=args.product_level, ai_label=args.ai_label)
    problems = posting_problems(data, ctx)
    if problems:
        return cli.refuse_problems(args, rel, problems)
    stepchecks.mark(run, KEY, path)
    warnings = [f"{field} is not a field the posting kit uses: nothing shows or checks it. Take it out, or put its "
                "text in a field that is used (references/posting-kit.md, the kit's fields)." for field in unused(data)]
    warnings += [w for w in (stale_rules(), search_warning(data, trend_text(run))) if w]
    message = (f"{rel} holds the platform rules of {RULES['as_of']} for "
               f"{', '.join(PLATFORM_NAMES[p] for p in data['platforms'])} ({ctx.language}). Write its .md with tm kit md."
               + "".join(f"\nWarning: {w}" for w in warnings))
    cli.emit(args, {"status": "done", "file": rel, "platforms": list(data["platforms"]), "rules": RULES["as_of"],
                    "warnings": warnings, "message": message}, message)
    return 0


def _md(args: argparse.Namespace) -> int:
    run = RunFolder.open(Path(args.run))
    path, rel, data = _load(run, args.file)
    if not isinstance(data, dict) or not isinstance(data.get("platforms"), dict):
        raise ValueError(f"{rel} is not a posting kit.")
    entry = state.load(run).checked.get(KEY)
    if not entry or entry.get("file") != rel or entry.get("sha256") != stepchecks.sha256(path):
        raise Stop(f"{rel} has not passed tm kit check as it is now (it is new or changed since). Check it with "
                   f"tm kit check --run {args.run} --file {rel}, then write its .md; {AGAIN}.")
    out = path.with_suffix(".md")
    done = out.relative_to(run.path.resolve()).as_posix()
    lang = i18n.page_lang(i18n.run_languages(run).working, "organic")   # the labels: what the user reads
    text = to_md(data, lang.lang)
    run.assert_writable(out)
    try:
        with open(out, "x", encoding="utf-8", newline="\n") as fh:   # never over an earlier .md (OV13)
            fh.write(text)
    except FileExistsError:
        raise Stop(f"{done} is already written and is never written over. To change it, write the kit as a new "
                   f"version, check it, then write its .md; {AGAIN}.") from None
    manifest.record(run, done, done.split("/", 1)[0], "tm kit md", parent=rel)
    message = f"Wrote {done}." + (f" {lang.warning}" if lang.warning else "")
    cli.emit(args, {"status": "done", "file": done, "message": message,
                    **({"language_warning": lang.warning} if lang.warning else {})}, message)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        return {"check": _check, "md": _md}[args.action](args)
    except Stop as exc:  # a Stop is a ValueError: caught first, it exits 2
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))


cli.register("kit", _setup, _run)
