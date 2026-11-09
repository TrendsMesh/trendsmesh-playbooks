"""The posting kit (OV11), shared by the script and the AI video outputs: `tm kit check` and `tm kit md`.

A kit is the handoff's `04_final/kits/<id>_kit_vNN.json` (`schemas/pb3_kit.schema.json`) plus the plugin's
block, which the agent writes with it:

    plugin = {"ai_label": bool, "trending_sound": {"name", "evidence", "replaces_track": bool} | null,
              "business_alternative": str | null, "platforms": [...], "youtube_thumbnail": bool}

`check(kit, ctx)` holds the 2026-11 platform rules (`resources/posting-kit/best_practices_2026-11.md`,
PLAYBOOK OV11) that a program can read. What it cannot read stays with the skill: that line 1 is a
natural search phrase, that an emoji means something, that the product is a soft line.

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
  more than the platform may count it.
A filmed script (`filmed_by_person`) needs no AI label, whatever `ai_label` says.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tm import (brand, cli, config, json_schema, manifest, organic_final, organic_proposals, state, stepchecks,
                trend_spool)
from tm.config import Problem
from tm.runfolder import ReadOnlyError, RunFolder
from tm.stops import AGAIN, Stop

SCHEMA = Path(__file__).parent / "schemas" / "pb3_kit.schema.json"
KEY = "kit"                                    # run.json checked[kit]: the latest kit file that passed
PLATFORMS = ("tiktok", "instagram", "youtube", "facebook")
PLATFORM_NAMES = {"tiktok": "TikTok", "instagram": "Instagram Reels", "youtube": "YouTube Shorts",
                  "facebook": "Facebook Reels"}
BRAND_LEVELS = ("incidental", "featured", "hero")   # the product levels that need "Your brand"
AI_LABELS = ("required", "on", "not_required")
HASHTAGS = {"tiktok": (3, 5), "instagram": (0, 5), "facebook": (1, 3)}   # YouTube's are in its description
YOUTUBE_HASHTAGS = (2, 3)
YOUTUBE_TITLE_MAX = 100
INSTAGRAM_LINE_MAX = 125
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
    tags = block.get("hashtags")
    return out + [("hashtags", t) for t in tags if isinstance(t, str)] if isinstance(tags, list) else out


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
        low, high = HASHTAGS.get(name, (0, 99))
        tags = block.get("hashtags") if isinstance(block.get("hashtags"), list) else []
        if name in HASHTAGS and not low <= len(tags) <= high:
            bad(f"{where}.hashtags", f"{PLATFORM_NAMES[name]} has {len(tags)} hashtags; it takes "
                + (f"{low} to {high}." if low else f"at most {high}."), f"Give {PLATFORM_NAMES[name]} "
                + (f"{low} to {high}" if low else f"{high} or fewer") + " specific hashtags.")
        if name == "instagram":
            lines = str(block.get("caption") or "").splitlines()
            line = lines[0] if lines else ""
            if len(line) > INSTAGRAM_LINE_MAX:
                bad(f"{where}.caption", f"The first line is {len(line)} characters; Instagram shows {INSTAGRAM_LINE_MAX}.",
                    f"Shorten line 1 to {INSTAGRAM_LINE_MAX} characters, hook and search phrase first.")
        if name == "youtube":
            title = str(block.get("title") or "")
            if not title.strip() or len(title) > YOUTUBE_TITLE_MAX:
                bad(f"{where}.title", f"The title is {len(title)} characters; it takes 1 to {YOUTUBE_TITLE_MAX}.",
                    f"Write a title of at most {YOUTUBE_TITLE_MAX} characters.")
            n = len(HASHTAG.findall(str(block.get("description") or "")))
            if not YOUTUBE_HASHTAGS[0] <= n <= YOUTUBE_HASHTAGS[1]:
                bad(f"{where}.description", f"The description has {n} hashtags; it takes {YOUTUBE_HASHTAGS[0]} to "
                    f"{YOUTUBE_HASHTAGS[1]}.", "Put 2 or 3 hashtags in the description.")
        if name == "tiktok" and ctx.product_level in BRAND_LEVELS and not _text(block.get("product")):
            bad(f"{where}.product", f"The product is {ctx.product_level}, so TikTok needs the “Your brand” disclosure.",
                "Fill product with the disclosure step.")
        for field, text in _texts(block):
            _post_text(bad, f"{where}.{field}", text)
        caption = block.get("caption")
        if isinstance(caption, str) and _questions(caption) > 1:
            bad(f"{where}.caption", "The caption asks more than one question.", "Keep one genuine question.")
    if plugin.get("ai_label") is False and ctx.ai_label in ("required", "on") and not ctx.filmed_by_person:
        bad("plugin.ai_label", f"The AI label must be on here (it is {ctx.ai_label.replace('_', ' ')}).",
            "Set plugin.ai_label to true and give the in-app step on each platform.")
    sound = plugin.get("trending_sound")
    if isinstance(sound, dict):
        if ctx.account_type == "business" and not _text(plugin.get("business_alternative")):
            bad("plugin.business_alternative", "A business account cannot use a trending sound from the app's library.",
                "Name a commercial-library alternative.")
        if sound.get("replaces_track") is True and "_nosound" not in str(kit.get("video") or ""):
            bad("video", "The trending sound replaces the track, so the video needs its _nosound file.",
                "Name the _nosound export in video.")
    return out


# --- the .md beside the JSON ------------------------------------------------------------------------

LABELS = {
    "en": {"title": "Posting kit", "video": "Video", "cover": "Cover", "product": "Product", "caption": "Caption",
           "hashtags": "Hashtags", "name": "Title", "description": "Description", "ai": "AI label",
           "sound": "Sound", "trending": "Trending sound", "alternative": "Business account alternative"},
    "pl": {"title": "Zestaw do publikacji", "video": "Wideo", "cover": "Okładka", "product": "Produkt",
           "caption": "Opis posta", "hashtags": "Hashtagi", "name": "Tytuł", "description": "Opis filmu",
           "ai": "Etykieta AI", "sound": "Dźwięk", "trending": "Trendujący dźwięk",
           "alternative": "Alternatywa dla konta firmowego"},
}


def _fence(text: str) -> list[str]:
    return ["```", text, "```"]


def to_md(kit: dict, lang: str) -> str:
    """templates/posting_kit_template.md's sections (its `## ` headings are `PLATFORM_NAMES`, which a test
    compares to the template), filled: one per platform in the kit."""
    t = LABELS.get(lang, LABELS["en"])
    plugin = kit.get("plugin") or {}
    cover = (kit.get("cover") or {}).get("file")
    head = [f"# {t['title']} {kit.get('id')} {kit.get('version')} ({kit.get('channel')})", ""]
    meta = [f"{t['video']}: `{kit.get('video')}`"] + ([f"{t['cover'].lower()}: `{cover}`"] if cover else []) \
        + ([f"{t['product'].lower()}: {kit['product']}"] if kit.get("product") else [])
    lines = head + [" · ".join(meta), ""]
    for name, block in (kit.get("platforms") or {}).items():
        lines += [f"## {PLATFORM_NAMES.get(name, name)}"]
        if block.get("title"):
            lines += [f"**{t['name']}:**"] + _fence(block["title"])
        for field, key in (("caption", "caption"), ("description", "description")):
            if block.get(field):
                lines += [f"**{t[key]}:**"] + _fence(block[field])
        if block.get("hashtags"):
            lines += [f"**{t['hashtags']}:**"] + _fence(" ".join(block["hashtags"]))
        for field, key in (("cover", "cover"), ("ai_label", "ai"), ("sound", "sound"), ("product", "product")):
            if block.get(field):
                lines.append(f"**{t[key]}:** {block[field]}")
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
    c.add_argument("--ai-label", choices=AI_LABELS, help="default: not_required for a script")


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
    problems = check(data, ctx)
    if problems:
        return cli.refuse_problems(args, rel, problems)
    stepchecks.mark(run, KEY, path)
    message = (f"{rel} holds the platform rules for {', '.join(PLATFORM_NAMES[p] for p in data['platforms'])} "
               f"({ctx.language}). Write its .md with tm kit md.")
    cli.emit(args, {"status": "done", "file": rel, "platforms": list(data["platforms"]), "message": message}, message)
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
    text = to_md(data, str(data.get("language") or "en"))
    run.assert_writable(out)
    try:
        with open(out, "x", encoding="utf-8", newline="\n") as fh:   # never over an earlier .md (OV13)
            fh.write(text)
    except FileExistsError:
        raise Stop(f"{done} is already written and is never written over. To change it, write the kit as a new "
                   f"version, check it, then write its .md; {AGAIN}.") from None
    manifest.record(run, done, done.split("/", 1)[0], "tm kit md", parent=rel)
    cli.emit(args, {"status": "done", "file": done, "message": f"Wrote {done}."}, f"Wrote {done}.")
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
