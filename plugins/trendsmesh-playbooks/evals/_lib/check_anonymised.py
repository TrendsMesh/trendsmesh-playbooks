#!/usr/bin/env python3
"""Checks that nothing from the example runs' real data is in evals/.

    python3 evals/_lib/check_anonymised.py [--examples <dir with the example runs>] [--root <evals tree>]

1. Always: every number of 12 or more digits anywhere under evals/ (not results/) must be one of the
   synthetic ids made in meta_data.py, and there is no 32-character hex id, no TikTok creator link, no
   Reddit user named in a text (u/<name> or /u/<name>, other than the aliases u/creator and
   u/creator_NNNN), no name given on another site ("on Wattpad as <name>") and no reddit.com link.
2. With --examples (default: the handoff v02 and v03 folders, the trend research handoff's, the
   creative brief handoff's and the organic video handoff's, those that are there): none of the example runs' own ids (JSON values
   under id-like keys, the ad account's and pages' ids among them, a Reddit post's or comment's id of
   any length with the ids its comments name, digit runs of 8 or more in the manifests and notes,
   32-character hex ids, a Goodreads review id) or handles (a video's creator, a Reddit author of 3
   characters or more, a Goodreads reader's full name or handle-like name) appears as a whole token, and
   every Goodreads review header names "Reviewer N" and "review N". View
   counts are statistics, not ids, and stay: a digit run of the notes that is a count in the runs'
   JSON (views, likes, shares, reach) is not taken as an id (the beauty dry run's notes list view
   counts).
3. What it does not take as an original, on purpose (each kept as narrow as found):
   - a plain lowercase word under an `id` key (`PLAIN_WORD`: a page item's name in the organic video gates,
     "narrator", "host-en-pl"; the other handoffs lose no id with it);
   - `PUBLIC_ACCOUNTS`, three public accounts whose handle is a game's or a public figure's own name: the
     organic video handoff has videos by them, and other runs' captions name them. gen_mocks.py imports this
     set (the generator keeps their names in texts and still aliases them as creators), so this file is one
     of the generator's dependencies.
Exit 0 when clean, 1 with the findings listed. The committed tree takes about two minutes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
sys.path.insert(0, str(HERE))
import meta_data as m  # noqa: E402

ALLOWED = set(m.SYNTHETIC_IDS)
# v02's example runs (v1's evals), v03's (the re-cut evals: Ad 3, ad_2, ExampleTravel), the trend research
# handoff's beauty dry run (the PB04 evals), the creative brief handoff's LD dry run (the PB02 evals) and the
# organic video handoff's ExampleEdu walkthrough and pet store runs (the PB03 evals)
DEFAULT_EXAMPLES = [EVALS.parents[2] / "handoff" / v / "examples"
                    for v in ("refresh-ad_v02", "refresh-ad_v03", "trend-research_v01", "creative-brief_v02",
                              "organic-video_v02")]
ID_KEYS = {"id", "ad_id", "asset_id", "account_id", "video_id", "creator_id", "adset_id", "campaign_id",
           "ad_account_id", "page_id", "pixel_id", "origin_fbid", "origin_fbids"}
# A handle: a video's creator, or the author of a Reddit post or comment (the LD dry run's voice files).
HANDLE_KEYS = {"creator", "creator_id", "author"}
NOT_A_HANDLE = {"[deleted]", "AutoModerator"}
# Public accounts whose handle is a game's or a public figure's own name: the organic video handoff has videos by
# them, and other runs' captions name them ("Drop a hand if you miss old MrBeast"). The generators still replace
# them in the data they write; only their name in another run's text is not a finding.
PUBLIC_ACCOUNTS = {"fortnite", "mrbeast", "ishowspeed"}
# A page item named by a word, never an id (see originals).
PLAIN_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")
# A handle in a caption after a social label and a colon (Instagram, Telegram's "тгк", ig, ...), creator
# of the data or not; gen_mocks.py writes "creator" there.
SOCIAL_HANDLE = re.compile(r"(?i)(?<![\w])(instagram|insta|inst|ig|telegram|tg|тг|тгк|tiktok|snapchat|snap|youtube|yt|"
                           r"twitter|threads|facebook|fb)(\s*[:：]\s*)@?(?!creator|example-)([^\s#|,()\x22]+)")  # not an alias, not a synthetic "tiktok:example-NN" id
# A Reddit user named in a text: u/<name> or /u/<name>; gen_mocks.py writes u/creator or the author's alias.
REDDIT_USER = re.compile(r"(?<![\w])/?u/(?!creator(?:_\d+)?(?![\w-]))([A-Za-z0-9_-]{3,})")
# A name the writer gives on another site ("on Wattpad as <name>"); gen_mocks.py writes "creator".
PEN_NAME = re.compile(r"(?i)\b((?:on|at)\s+(?:wattpad|ao3|archive of our own|royal ?road|tumblr|medium|substack|"
                      r"patreon|deviantart|discord|instagram|tiktok|youtube)\s+(?:as|under)\s+@?)"
                      r"(?!creator\b)(\w[\w.-]*\w|\w)")
# A link to reddit.com or one of its hosts (www., old., ...), with or without its scheme; gen_mocks.py
# writes https://example.com/r/<n>. Another site whose name ends in "reddit" is not Reddit.
REDDIT_LINK = re.compile(r"(?<![\w.-])(?:https?://)?(?:[\w-]+\.)?reddit\.com/|(?<![\w.-])redd\.it/")
# A Reddit post or comment (it names its subreddit): its id and the ids it names, whatever their length.
REDDIT_ID_KEYS = ("id", "link_id", "parent_id", "name")
# A review's header in a saved Goodreads text: the reader's name and the review id. gen_mocks.py writes
# "Reviewer N" and "review N"; any other header in evals/ is flagged.
GOODREADS_HEAD = re.compile(r"^=== #\d+ \| rating \d+ \| (.*?) \| review id .*?([A-Za-z0-9_-]{6,})\s*$", re.M)
GOODREADS_ANY_HEAD = re.compile(r"^=== #\d+ \| rating \d+ \| (.*?) \| review id (.*?)\s*$", re.M)
GOODREADS_ALIAS = re.compile(r"Reviewer \d+")
GOODREADS_ALIAS_ID = re.compile(r"review \d+")
# A reader's name is searched for elsewhere when it names a person: a full name ("Mara Kellow") or a
# handle-like word ("duskwren", "QuillFern"). A capitalised first name alone ("Otto", "Wanda") is a word
# in too many texts (a caption's "Otto", a review's "Sigmund Freud") to be a finding.
FIRST_NAME = re.compile(r"[A-Z][a-z]+")


def reader(name: str) -> str | None:
    words = re.findall(r"\w+", name)
    if len(words) >= 2 and len(name) >= 5:
        return name
    if len(words) == 1 and len(words[0]) >= 3 and not FIRST_NAME.fullmatch(words[0]):
        return words[0]
    return None
COUNT_KEYS = {"views", "likes", "shares", "comments", "videos", "creators", "estimated"}
TEXT = {".md", ".json", ".py", ".sh", ".yaml", ".yml", ".txt"}


def files(root: Path = EVALS) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and "results" not in p.relative_to(root).parts
            and p.suffix in TEXT and p.name != "check_anonymised.py"]


def originals(examples: Path) -> tuple[set[str], set[str]]:
    ids, words, counts, noted = set(), set(), set(), set()
    for f in examples.rglob("*"):
        if not f.is_file() or f.suffix not in {".json", ".md", ".txt", ".csv"}:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        ids |= set(re.findall(r"\b[0-9a-f]{32}\b", text))
        for name, review in GOODREADS_HEAD.findall(text):
            words |= {reader(name)} - {None}
            ids.add(review)
        if f.suffix != ".json":
            noted |= set(re.findall(r"(?<![\d.])\d{8,}(?![\d.])", text))
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if "subreddit" in x:
                    rids = {re.sub(r"^t\d_", "", x[k]) for k in REDDIT_ID_KEYS if isinstance(x.get(k), str)}
                    ids |= {r for r in rids if len(r) >= 5}
                for k, v in x.items():
                    if k in ID_KEYS and isinstance(v, (str, int)):
                        # a plain lowercase word (a page item's name in the organic video gates: "narrator",
                        # "host-en-pl") is not an id; a Reddit id of letters is taken below, by its subreddit
                        word = k == "id" and isinstance(v, str) and PLAIN_WORD.fullmatch(v) is not None
                        ids |= set(re.findall(r"\d{8,}", str(v))) | ({v} if isinstance(v, str) and len(v) >= 8
                                                                      and not word else set())
                    if k in ID_KEYS and isinstance(v, list):    # origin_fbids: a list of ids
                        ids |= {m for x in v if isinstance(x, (str, int)) for m in re.findall(r"\d{8,}", str(x))}
                    # a video creator of 3 characters is a word as often as a handle ("cnn", "uno"); a
                    # Reddit author of 3 is a person
                    if (k in HANDLE_KEYS and isinstance(v, str) and len(v) > (2 if k == "author" else 3)
                            and v not in NOT_A_HANDLE and v.lower() not in PUBLIC_ACCOUNTS):
                        words.add(v)
                    if k in COUNT_KEYS and isinstance(v, int) and not isinstance(v, bool):
                        counts.add(str(v))
                    stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    ids |= noted - (counts - ids)  # a noted digit run that is only ever a count is a statistic
    return {str(i) for i in ids}, words


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=Path, action="append",
                    help="a folder of example runs (repeatable; default: the handoff v02 and v03 folders)")
    ap.add_argument("--root", type=Path, default=EVALS, help="the tree to check (default: this evals/ folder)")
    args = ap.parse_args()
    root = args.root.resolve()
    found: list[str] = []
    fs = files(root)
    for f in fs:
        text = f.read_text(encoding="utf-8", errors="ignore")
        rel = f.relative_to(root)
        for n in set(re.findall(r"(?<![\d.])\d{12,}(?![\d.])", text)) - ALLOWED:
            # long numbers that are not ids (epoch-like counts in fixtures) are not expected here either
            found.append(f"{rel}: unexpected long number {n}")
        for h in set(re.findall(r"\b[0-9a-f]{32}\b", text)):
            found.append(f"{rel}: 32-character hex id {h}")
        if re.search(r"tiktok\.com/@", text):
            found.append(f"{rel}: a TikTok creator link")
        for m in SOCIAL_HANDLE.finditer(text):
            found.append(f"{rel}: a handle after a social label ({m.group(1)}: {m.group(3)[:3]}...)")
        for m in REDDIT_USER.finditer(text):
            found.append(f"{rel}: a Reddit user named in a text (u/{m.group(1)[:3]}...)")
        for m in PEN_NAME.finditer(text):
            found.append(f"{rel}: a pen name on another site ({m.group(2)[:3]}...)")
        if REDDIT_LINK.search(text):
            found.append(f"{rel}: a Reddit link")
        for m in GOODREADS_ANY_HEAD.finditer(text):
            if not (GOODREADS_ALIAS.fullmatch(m.group(1)) and GOODREADS_ALIAS_ID.fullmatch(m.group(2))):
                found.append(f"{rel}: a Goodreads header with a reader's name or review id")
    note = "examples not found: only the generic checks ran"
    folders = [d for d in (args.examples or DEFAULT_EXAMPLES) if d.is_dir()]
    if folders:
        ids, words = set(), set()
        for d in folders:
            i, w = originals(d)
            ids, words = ids | i, words | w
        # one pattern each (the beauty dry run alone has thousands of ids and handles), longest first,
        # with the same whole-token rules as one search per id or handle
        alt = lambda xs: "|".join(re.escape(x) for x in sorted(xs, key=len, reverse=True))  # noqa: E731
        # a Reddit id also as a comment names it (t3_<post>, t1_<comment>)
        id_rx = re.compile(rf"(?<![\w.])(?:t\d_)?({alt(ids)})(?![\w])") if ids else None
        # handles in any case: a caption may capitalise a handle
        word_rx = re.compile(rf"(?<![\w])(?:{alt(words)})(?![\w])", re.I) if words else None
        for f in fs:
            text = f.read_text(encoding="utf-8", errors="ignore")
            for i in sorted(set(id_rx.findall(text)) if id_rx else ()):
                found.append(f"{f.relative_to(root)}: original id {i[:4]}...")
            for w in sorted(set(word_rx.findall(text)) if word_rx else ()):
                found.append(f"{f.relative_to(root)}: creator handle {w[:3]}...")
        note = (f"checked against {len(ids)} ids and {len(words)} creator handles from "
                f"{', '.join(str(d) for d in folders)}")
    print(f"{len(fs)} files; {note}")
    for line in found:
        print("FOUND", line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
