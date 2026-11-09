"""The agent's customer-voice themes (CB5), checked against the raw items. Shared by the playbooks.

    tm voice check --run R --file 02_research/voice/voice_themes_vNN.json [--json]

The agent codes the items of `02_research/voice/items.jsonl` (`tm voice`) into themes and writes
`voice_themes_vNN.json`:

    {"schema": "voice-themes/1",
     "samples": [{"source": "reddit_post", "community": "r/…", "query": "…", "items": 100}],
     "themes": [{"id": "T01", "title": "…", "kind": "aspect|pain|desire|objection|outcome",
                 "items": ["<item id>"], "quotes": [{"item_id": "…", "text": "…"}]}],
     "language_bank": [{"phrase": "…", "item_id": "…"}],
     "brand_claims": [{"claim": "…", "source": "<landing file>", "verdict": "repeated|not_repeated|contradicted",
                       "items": []}],
     "brand_never_mentions": ["T07"], "thin": null}

A theme's frequency is `len(items)`: there is no separate count to get wrong. The check proves what
the file says against the items: every item id is logged (and is tier A or B: the brand's own words
never count as customer evidence), and a theme lists each item once; every quote and bank phrase is
in its item's title or text, starting and ending on whole words, after normalising case, whitespace,
curly quotes and the ellipsis character; the bank holds `voice.bank_min`–`voice.bank_max` distinct
phrases, or, when `thin` gives the reason, at least one; every sample names its query (the archive
gives keyword samples, so a count is a frequency within one); every brand claim has a source.

On a pass the file is marked (`stepchecks.mark(run, "voice", file)`); B2's `voice_checked` step check
then asks that the latest themes file is that one, unchanged.
"""

from __future__ import annotations

import argparse
import json
import re

from tm import audience, cli, config, json_schema, stepchecks, voice
from tm.config import Problem
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

KEY = "voice"
STEM = "voice_themes"
SCHEMA_ID = "voice-themes/1"
KINDS = ("aspect", "pain", "desire", "objection", "outcome")
VERDICTS = ("repeated", "not_repeated", "contradicted")
COUNTED_TIERS = tuple(voice.TIERS)   # A and B
NAME = re.compile(rf"^{re.escape(voice.STAGE)}/{STEM}_v\d+\.json$")
# Curly and look-alike quotes (U+02BC modifier apostrophe, U+2032/U+2033 primes) and the ellipsis
# character are written the plain way before comparing.
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u02bc": "'", "\u2032": "'",
                        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
                        "\u2026": "..."})
_WORD = re.compile(r"\w")
_SHAPE_TODO = f"Write the file in the {SCHEMA_ID} shape (references/voice.md), then check it again."

_TEXTS = {"type": "array", "items": {"type": "string"}}
SCHEMA: dict = {
    "type": "object",
    "required": ["schema", "samples", "themes", "language_bank", "brand_claims", "brand_never_mentions", "thin"],
    "properties": {
        "schema": {"const": SCHEMA_ID},
        "samples": {"type": "array", "items": {
            "type": "object", "required": ["source", "community", "items"],
            "properties": {"source": {"type": "string"}, "community": {"type": "string"},
                           "query": {"type": ["string", "null"]}, "items": {"type": "integer"}}}},
        "themes": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["id", "title", "kind", "items", "quotes"],
            "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "kind": {"enum": list(KINDS)},
                           "items": {**_TEXTS, "minItems": 1},
                           "quotes": {"type": "array", "items": {"$ref": "#/definitions/quote"}}}}},
        "language_bank": {"type": "array", "items": {
            "type": "object", "required": ["phrase", "item_id"],
            "properties": {"phrase": {"type": "string"}, "item_id": {"type": "string"}}}},
        "brand_claims": {"type": "array", "items": {
            "type": "object", "required": ["claim", "verdict", "items"],
            "properties": {"claim": {"type": "string"}, "source": {"type": ["string", "null"]},
                           "verdict": {"enum": list(VERDICTS)}, "items": _TEXTS}}},
        "brand_never_mentions": _TEXTS,
        "thin": {"type": ["string", "null"]},
    },
    "definitions": {"quote": {"type": "object", "required": ["item_id", "text"],
                              "properties": {"item_id": {"type": "string"}, "text": {"type": "string"}}}},
}


def _norm(text: str | None) -> str:
    """Case, runs of whitespace, curly quotes and the ellipsis character do not count against a
    verbatim quote."""
    return " ".join((text or "").translate(_PLAIN).split()).casefold()


def _edges(quote: str) -> str:
    """`quote` (normalised) as a pattern that starts and ends on whole words: a letter or digit at an
    edge must not continue a word of the item, and an apostrophe followed by a letter belongs to the
    word ("I can" is not in "I can't", "t lucid" is not in "can't lucid")."""
    first, last = quote[0], quote[-1]
    before = r"(?<!\w)(?<!\w')" if _WORD.match(first) else (r"(?<!\w)" if first == "'" else "")
    after = r"(?!\w)(?!'\w)" if _WORD.match(last) else (r"(?!\w)" if last == "'" else "")
    return before + re.escape(quote) + after


def _found(quote: str, texts: list[str]) -> bool:
    pattern = re.compile(_edges(_norm(quote)))
    return any(pattern.search(_norm(t)) for t in texts)


def _where_it_parts(quote: str, texts: list[str]) -> str:
    """Where the quote leaves the item's words, for the problem message (compared in lower case)."""
    q = _norm(quote)
    best, rest = "", ""
    for text in map(_norm, texts):
        lo, hi = 0, len(q)
        while lo < hi:   # the longest start of the quote that is in this text
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if q[:mid] in text else (lo, mid - 1)
        if lo > len(best):
            at = text.find(q[:lo]) + lo
            best, rest = q[:lo], text[at:at + 24]
    if not best.strip():
        return "not even its first words are in the item"
    if best == q:
        return f"its words are there, but it starts or ends inside a word (the item goes on {rest!r})"
    return f"it matches as far as {best!r}, where the item goes on {rest!r} (compared in lower case)"


def _setting(run: RunFolder, cfg: dict, path: str):
    """A setting of the run's config, else its playbook's default."""
    found = config._get(cfg or {}, path)
    if found is None:
        module = config._for_playbook(run)
        found = config._get(module.DEFAULTS if module else config.DEFAULTS, path)
    if found is None:
        raise ValueError(f"{path} is not a setting of this run's playbook.")
    return found


def _shape(data: object) -> list[Problem]:
    out = []
    for line in json_schema.problems(data, SCHEMA, name=STEM):
        where = line.split(" ", 1)[0]
        out.append(Problem(where.removeprefix(STEM + ".") if where != STEM else STEM, line, _SHAPE_TODO))
    return out


def check(run: RunFolder, data: object, cfg: dict) -> list[Problem]:
    """What in the themes file `data` the items of the run do not bear out; empty when it holds.
    A file not in the voice-themes/1 shape gives its shape problems alone. A damaged items log is a
    Stop (from `tm voice`), so nothing is proven on a log that cannot be read."""
    shape = _shape(data)
    if shape:
        return shape
    items = {row.get("id"): row for row in voice._logged(run)}
    out: list[Problem] = []

    def logged(field: str, item_id: str) -> dict | None:
        """The item, or None with the problem added."""
        row = items.get(item_id)
        if row is None:
            out.append(Problem(field, f"{item_id} is not in {voice.ITEMS}.",
                               "Use the id of an item the run collected (tm voice), or collect or import it first."))
            return None
        tier = row.get("tier")
        if tier is None:
            out.append(Problem(field, f"{item_id} has no tier in {voice.ITEMS}.",
                               "Import its file again with tm voice import --tier A|B, or use another item."))
            return None
        if tier not in COUNTED_TIERS:
            out.append(Problem(field, f"{item_id} is tier {tier}: {voice.TIER_C}.",
                               "Use an item of tier A (own customers) or B (category)."))
            return None
        return row

    def verbatim(field: str, item_id: str, text: str, what: str) -> None:
        if not text.strip():
            out.append(Problem(field, f"The {what} is empty.", f"Copy the {what} from the item's words."))
            return
        row = logged(field, item_id)
        if row is None:
            return
        texts = [row.get("title") or "", row.get("text") or ""]
        if not _found(text, texts):
            out.append(Problem(field, f"The {what} is not verbatim in {item_id}'s title or text: {text!r}; "
                               f"{_where_it_parts(text, texts)}.",
                               "Copy one unbroken stretch of that item's words, starting and ending on whole words "
                               "(case, spaces, curly quotes and … aside), and split an elided quote into two; or "
                               "name the item it comes from."))

    for i, sample in enumerate(data["samples"]):
        if not (sample.get("query") or "").strip():
            out.append(Problem(f"samples[{i}]", f"The sample from {sample['community'] or sample['source']} names "
                               "no query.", "Give the keyword it was pulled by: a theme's count is a frequency "
                               "within keyword samples, not a share of the community. For a sample pulled without "
                               "a keyword, leave it out or describe in query how it was pulled."))
    seen: set[str] = set()
    for i, theme in enumerate(data["themes"]):
        if theme["id"] in seen:
            out.append(Problem(f"themes[{i}]", f"The theme id {theme['id']} is used twice.",
                               "Give every theme its own id, or merge the two."))
        seen.add(theme["id"])
        listed: set[str] = set()
        for j, item_id in enumerate(theme["items"]):
            if item_id in listed:
                out.append(Problem(f"themes[{i}].items[{j}]", f"{item_id} is listed twice; a theme counts each item "
                                   "once (its frequency is the number of its items).", "Remove the repeat."))
                continue
            listed.add(item_id)
            logged(f"themes[{i}].items[{j}]", item_id)
        for j, quote in enumerate(theme["quotes"]):
            verbatim(f"themes[{i}].quotes[{j}]", quote["item_id"], quote["text"], "quote")

    bank = data["language_bank"]
    low, high = _setting(run, cfg, "voice.bank_min"), _setting(run, cfg, "voice.bank_max")
    thin = (data["thin"] or "").strip()
    if len(bank) > high:
        out.append(Problem("language_bank", f"The language bank has {len(bank)} phrases; CB5 asks for {low}–{high}.",
                           f"Keep the {high} strongest."))
    elif thin and not bank:
        out.append(Problem("language_bank", "The language bank is empty.",
                           "Even thin customer voice gives one phrase: add it with its item."))
    elif not thin and len(bank) < low:
        out.append(Problem("language_bank", f"The language bank has {len(bank)} phrases; CB5 asks for {low}–{high}.",
                           f"Add phrases from the items, or, when the customer voice is too thin for {low}, say why "
                           "in thin (then one phrase is enough)."))
    phrases: dict[str, int] = {}
    for i, entry in enumerate(bank):
        key = _norm(entry["phrase"])
        if key and key in phrases:
            out.append(Problem(f"language_bank[{i}]", f"The phrase repeats language_bank[{phrases[key]}].",
                               "Keep one: the bank counts each phrase once."))
            continue
        phrases.setdefault(key, i)
        verbatim(f"language_bank[{i}]", entry["item_id"], entry["phrase"], "phrase")

    for i, claim in enumerate(data["brand_claims"]):
        if not (claim.get("source") or "").strip():
            out.append(Problem(f"brand_claims[{i}]", f"The brand claim {claim['claim']!r} has no source.",
                               "Name the file it comes from (the landing page, brand guide or ad you saved)."))
        for j, item_id in enumerate(claim["items"]):
            logged(f"brand_claims[{i}].items[{j}]", item_id)
    for i, theme_id in enumerate(data["brand_never_mentions"]):
        if theme_id not in seen:
            out.append(Problem(f"brand_never_mentions[{i}]", f"{theme_id} is not a theme of this file.",
                               "Name the id of one of its themes."))
    return out


def checked_gap(run: RunFolder) -> str | None:
    """The `voice_checked` step check: the latest themes file passed tm voice check, unchanged since."""
    return stepchecks.fresh(run, KEY, voice.STAGE, STEM, "json")


# --- command line (tm voice check; voice.py adds the parser) -----------------------------------------

def add_parser(sub: argparse._SubParsersAction) -> None:
    c = sub.add_parser("check", help="check the themes, quotes and language bank against the items (CB5)")
    c.add_argument("--run", required=True, help="the run folder")
    c.add_argument("--file", required=True, help=f"the themes file, {voice.STAGE}/{STEM}_vNN.json")
    c.add_argument("--json", action="store_true")


def run_check(args: argparse.Namespace, run: RunFolder) -> int:
    path, rel = audience.inside(run, args.file)    # ValueError: not a file of this run
    path = path.resolve()                          # the file checked is the file marked, wherever tm runs
    if not NAME.fullmatch(rel):
        raise ValueError(f"The themes are written as {voice.STAGE}/{STEM}_vNN.json; {rel} is not.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:   # not JSON, or not UTF-8
        raise Stop(f"{rel} is not valid JSON ({exc}). Write it again as one JSON object, then check it again; "
                   f"{AGAIN}.") from None
    cfg = config.load(run) if (run.path / config.FILE).is_file() else {}
    problems = check(run, data, cfg)
    if problems:
        return cli.refuse_problems(args, rel, problems)
    stepchecks.mark(run, KEY, path)
    ranked = sorted(data["themes"], key=lambda t: -len(t["items"]))
    themes = ", ".join(f"{t['id']} ({len(t['items'])})" for t in ranked)
    message = (f"{rel} holds: every quote and all {len(data['language_bank'])} bank phrases are verbatim in their "
               f"items. Themes by frequency: {themes}.")
    cli.emit(args, {"status": "done", "file": rel, "themes": len(data["themes"]),
                    "bank": len(data["language_bank"]), "message": message}, message)
    return 0
