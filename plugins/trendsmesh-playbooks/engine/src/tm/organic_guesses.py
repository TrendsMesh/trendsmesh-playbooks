"""Organic AI video on Free (issue #106): the trends an idea run guesses, without TrendsMesh.

A run on Free (`tm evidence guess`, refused until the user chose Free) searches no TrendsMesh: at B1 to B2 the
agent looks at what it can see alone (the platforms' trending tabs and public trend lists such as TikTok Creative
Center, the Meta Ad Library, the channel's own videos, web search, its own knowledge) and writes the trends it
guesses, each with where it was seen:

    03_wip/guess_trends_vNN.json = {"lang": "<page language>", "guesses": [
        {"id": "g1", "kind": "hook_trend" | "topic_trend" | "format_trend" | "sound_trend",
         "name": "<the hook, topic, format or sound>", "what": "<one line: what it is>",
         "source": "trending_tab" | "creative_center" | "ad_library" | "own_channel" | "web_search" | "own_knowledge",
         "url": "https://..." | null, "seen_on": "YYYY-MM-DD",
         "quote": "<a number exactly as that source shows it, e.g. '1.2M views on the hashtag page'>" | null}]}

`tm organic guesses check --run R --file F` checks it (`check`) and marks it (key `guesses`); B2's
`shortlist_written` and B3's `evidence_saved` ask for it on a Free run (`gap`). What it refuses keeps a guess
from passing as TrendsMesh data: no lifecycle stage ("rising", "act now", "too late", "past peak") in the
words, no count (creators, views, videos, a percentage) outside `quote`, a quote only with the link of the
source that shows it, a link only on https, and nothing but the agent's own judgement without a source.

Proposals on Free (`organic_proposals`) name these ids in `trends[].id`, never `pick` (a guess has no
evidence videos), and are Inspire only: a Recreate needs two real videos repeating now, which only
TrendsMesh gives. The channel's used trends keep a guess under `used_key` ("guess:<its name>").
"""

from __future__ import annotations

import re
from datetime import date

from tm import evidence, state, stepchecks
from tm.config import Problem
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

WIP = "03_wip"
STEM = "guess_trends"
KEY = "guesses"
NAME = re.compile(r"^03_wip/guess_trends_v\d{2,}\.json$")
FILE_PATTERN = "03_wip/guess_trends_vNN.json"
KINDS = ("hook_trend", "topic_trend", "format_trend", "sound_trend")
SOURCES = ("trending_tab", "creative_center", "ad_library", "own_channel", "web_search", "own_knowledge")
LEAST, MOST = 3, 12
GUESS_PREFIX = "guess-"   # a guessed trend's key (`used_key`); no TrendsMesh id starts with it
_ID = re.compile(r"^g\d{1,3}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A lifecycle stage is TrendsMesh's, never a guess's (English and Polish, the page languages).
_STAGE = re.compile(r"\b(rising|act now|too late|past peak|peaking|on the rise|rośnie|rosnąc\w*|za późno|"
                    r"po szczycie|działaj teraz)\b", re.IGNORECASE)
# A count a reader would take as data: a number with a unit of reach, or a percentage ("%" is no word character, so
# it stands outside the word boundary: "40% more" is a count too).
_COUNT = re.compile(r"\d[\d.,\s]*\s*(%|(k|m|mln|tys\.?|views?|creators?|videos?|posts?|wyświetle\w*|twórc\w*|"
                    r"film\w*)\b)", re.IGNORECASE)


def is_free(run: RunFolder) -> bool:
    """An organic video run on Free: its evidence is the agent's guess."""
    s = state.load(run)
    return s.playbook == ORGANIC_VIDEO and s.evidence == evidence.GUESS


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def as_data(text: object) -> str | None:
    """What in `text` would pass a guess off as TrendsMesh data: "stage" (a lifecycle stage), "count" (a number with a
    unit of reach), else None. The one rule of the guesses check, applied on Free to the ideas and the week too."""
    if not isinstance(text, str):
        return None
    if _STAGE.search(text):
        return "stage"
    if _COUNT.search(text):
        return "count"
    return None


def wording(idea: dict, where: str, keys: tuple[str, ...], out: list[Problem]) -> None:
    """Issue #170: on Free an idea's own words (`keys`; a list's items one by one) give no lifecycle stage and no
    number without its source (`as_data`): the guess's number lives in its `quote`, with the source's link."""
    for key in keys:
        value = idea.get(key)
        texts = [(f"{where}.{key}[{i}]", t) for i, t in enumerate(value)] if isinstance(value, list) \
            else [(f"{where}.{key}", value)]
        for field, text in texts:
            kind = as_data(text)
            if kind == "stage":
                out.append(Problem(field, f"{text!r} gives a lifecycle stage, and on Free there is none: only "
                                          "TrendsMesh measures one.", "Say what you saw, not how far along it is."))
            elif kind == "count":
                out.append(Problem(field, f"{text!r} holds a count, which would read as TrendsMesh data, and on Free "
                                          "no number appears without its source.",
                                   "Drop the number: it belongs only in the guess's quote, with its source's link "
                                   f"({FILE_PATTERN}), and the page shows it there."))


def check(data: object, *, today: date | None = None) -> list[Problem]:
    """Everything wrong in a guess_trends file; empty when it holds."""
    today = today or date.today()
    if not isinstance(data, dict) or not isinstance(data.get("guesses"), list):
        return [Problem("guesses", "The file is not an object with a guesses list.",
                        f"Write {{\"lang\": ..., \"guesses\": [...]}} ({FILE_PATTERN}).")]
    out: list[Problem] = []
    guesses = data["guesses"]
    if not LEAST <= len(guesses) <= MOST:
        out.append(Problem("guesses", f"The file holds {len(guesses)} guesses.",
                           f"Write {LEAST} to {MOST}: the trends you can see for this channel, each with its source."))
    seen: set[str] = set()
    for i, g in enumerate(guesses):
        at = f"guesses[{i}]"
        if not isinstance(g, dict):
            out.append(Problem(at, "A guess is not an object.", "Write each guess as an object."))
            continue
        gid = g.get("id")
        if not (isinstance(gid, str) and _ID.fullmatch(gid)) or gid in seen:
            out.append(Problem(f"{at}.id", f"The id {gid!r} is not g1, g2, ... or is used twice.",
                               "Number the guesses g1, g2, ..."))
        seen.add(gid if isinstance(gid, str) else "")
        if g.get("kind") not in KINDS:
            out.append(Problem(f"{at}.kind", f"The kind {g.get('kind')!r} is not one of {', '.join(KINDS)}.",
                               "Name the kind of trend."))
        for key in ("name", "what"):
            if not _text(g.get(key)):
                out.append(Problem(f"{at}.{key}", f"The guess has no {key}.", f"Write its {key}, one line."))
            elif as_data(g[key]) == "stage":
                out.append(Problem(f"{at}.{key}", f"{g[key]!r} gives a lifecycle stage, and on Free there is none: "
                                                  "only TrendsMesh measures one.",
                                   "Say what you saw, not how far along it is."))
            elif as_data(g[key]) == "count":
                out.append(Problem(f"{at}.{key}", f"{g[key]!r} holds a count, which would read as data.",
                                   "Put a number only in quote, as its source shows it, with the source's link."))
        source, url, quote = g.get("source"), g.get("url"), g.get("quote")
        if source not in SOURCES:
            out.append(Problem(f"{at}.source", f"The source {source!r} is not one of {', '.join(SOURCES)}.",
                               "Name where you saw it."))
        if url is not None and not (isinstance(url, str) and url.startswith("https://") and " " not in url):
            out.append(Problem(f"{at}.url", f"The link {url!r} is not an https link.", "Give the page's https link, "
                                                                                       "or null."))
        if source == "own_knowledge" and (url or quote):
            out.append(Problem(f"{at}.source", "A guess from your own knowledge has no link and no number.",
                               "Name the page you saw it on as its source, or drop the link and the number."))
        if source in SOURCES and source != "own_knowledge" and not url:
            out.append(Problem(f"{at}.url", f"A guess seen on {source} has no link to where.",
                               "Give the page's link, or make it own_knowledge."))
        if quote is not None and not (_text(quote) and url):
            out.append(Problem(f"{at}.quote", "A number needs the link of the source that shows it.",
                               "Give the link, or drop the number."))
        if quote is not None and _text(quote) and as_data(quote) == "stage":
            out.append(Problem(f"{at}.quote", f"{quote!r} gives a lifecycle stage.", "Quote the number alone."))
        day = g.get("seen_on")
        if not (isinstance(day, str) and _DAY.fullmatch(day)):
            out.append(Problem(f"{at}.seen_on", f"seen_on {day!r} is not a date.", "Write YYYY-MM-DD."))
        else:
            try:
                if date.fromisoformat(day) > today:
                    out.append(Problem(f"{at}.seen_on", f"seen_on {day} is after today.", "Write the day you saw it."))
            except ValueError:
                out.append(Problem(f"{at}.seen_on", f"seen_on {day!r} is not a date.", "Write YYYY-MM-DD."))
    return out


def gap(run: RunFolder) -> str | None:
    """B2 and B3 of a Free run: the latest guess_trends file passed `tm organic guesses check` and is unchanged."""
    why = stepchecks.fresh(run, KEY, WIP, STEM, "json")
    return None if why is None else (f"{why} (on Free: the trends you guess, each with its source, "
                                     f"{FILE_PATTERN}, tm organic guesses check)")


def latest(run: RunFolder) -> dict[str, dict]:
    """The checked guesses of the run by id ({} when none is checked)."""
    import json

    entry = state.load(run).checked.get(KEY)
    if not entry:
        return {}
    try:
        data = json.loads((run.path / entry["file"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, KeyError):
        return {}
    return {g["id"]: g for g in data.get("guesses") or [] if isinstance(g, dict) and isinstance(g.get("id"), str)}


def used_key(guess: dict) -> str:
    """A guessed trend's key in the channel's used trends and on the pages: from its kind and name, not its
    run-local id, so the same guess in a later run is the same trend; a trend id's characters only
    (`trends.TREND_ID`): "guess-hook-pov-you-finally"."""
    import hashlib
    import unicodedata

    name = unicodedata.normalize("NFKD", str(guess.get("name") or "")).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:60].strip("-")
    if not slug:   # a name in another script: its hash
        slug = hashlib.sha256(str(guess.get("name")).encode("utf-8")).hexdigest()[:12]
    kind = str(guess.get("kind") or "").removesuffix("_trend") or "trend"
    return f"{GUESS_PREFIX}{kind}-{slug}"


def is_guess_key(value: object) -> bool:
    return isinstance(value, str) and value.startswith(GUESS_PREFIX)


def source_line(guess: dict, words: dict[str, str] | None = None) -> str:
    """Where a guess was seen, for a page: "Seen on TikTok Creative Center, 2026-11-13 · <quote>"."""
    words = words or {}
    where = words.get(str(guess.get("source")), str(guess.get("source") or "").replace("_", " "))
    line = f"{where}, {guess.get('seen_on')}" if guess.get("source") != "own_knowledge" else where
    return line + (f" · {guess['quote']}" if _text(guess.get("quote")) else "")
