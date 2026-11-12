"""Create an ad (playbook 05), S8 and S9: the Meta copy (CA13), its check, the accepted copy, the copy page's data,
and the delivery check.

The draft, `03_wip/copy_vNN.json`, is written by the agent, one entry per ad (the main cut, and the short and long
cuts when there are any), each with `key` (the ad key: `utm_content`), `ad_name`, `video_title`, `cta` (one of
Meta's call-to-action types), `display_link`, `url`, and `primary_texts`, `headlines` and `descriptions`, each a list
of `copy.count` (5) items `{"text", "claims": [claim ids]}`. `tm ad copy check` refuses: a wrong count, a text over
its limit (125 / 40 / 30 characters), a claim that is not checked, **a number that is in none of the text's claims**
(CA3: never an invented number), **a promise of results or availability that none of its claims says** (CA3), a CTA
that is not Meta's, a link or URL off the brand's site, UTM missing or `utm_content` not the ad key, and a name that
reads like "Ad 1".

The promises are phrases of the market language (the copy's own), in the string table as `checks.promise_results`
and `checks.promise_availability` (tm.i18n: English and Polish ship; another language is the agent's translation,
`tm i18n export` / `import`): comma-separated, matched as whole words in any case, a word ending in `*` taking any
ending ("guarantee*", "gwarant*"). A phrase in a text passes only when one of the claims the text names says it too.
A market language with no list is checked for numbers only, and `promise_note` says so plainly: read the copy for
promises yourself, or translate the table.

After the copy check-in, the user's choices (kept, edited, dropped; `03_wip/copy_decisions_vNN.json`: per ad key,
per list, `{"n": the draft's number, "text": the text as kept or edited, "keep": true or false}`) become the
accepted copy, `04_final/copy_vNN.json`, through `tm ad copy accept`: each kept text is checked again (an edit
keeps the draft's claims), and at least one primary text and one headline stay. Nothing is uploaded before it exists.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse


from tm import create_config, create_plan, i18n, state, stepchecks
from tm.config import Problem
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder

WIP, FINAL = create_config.WIP, "04_final"
DRAFT, DECISIONS, ACCEPTED = "copy", "copy_decisions", "copy"
KEY_DRAFT, KEY_ACCEPTED = "ad_copy", "ad_copy_final"
LISTS = {"primary_texts": ("copy.primary_max", "ad.copy.primary"),
         "headlines": ("copy.headline_max", "ad.copy.headline"),
         "descriptions": ("copy.description_max", "ad.copy.description")}
# Meta's call-to-action types a video ad with a website takes (the Marketing API's call_to_action_type).
META_CTAS = ("LEARN_MORE", "SHOP_NOW", "SIGN_UP", "SUBSCRIBE", "DOWNLOAD", "GET_OFFER", "GET_QUOTE", "BOOK_TRAVEL",
             "CONTACT_US", "APPLY_NOW", "ORDER_NOW", "WATCH_MORE", "GET_STARTED", "REQUEST_TIME", "SEE_MENU",
             "BUY_NOW", "INSTALL_APP", "USE_APP", "TRY_IT", "JOIN_WAITLIST")
UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_content")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
GENERIC = re.compile(r"^\s*(new\s+)?(ad|ads|ad set|adset|campaign|creative|video|test)\s*[#_-]?\s*\d*\s*$", re.I)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _host(url: str) -> str:
    host = (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def readable(name: object) -> bool:
    """A name that says what it is (product, test, audience, concept), not "Ad set 1" (CA14)."""
    return _text(name) and not GENERIC.match(str(name)) and len(re.findall(r"[^\W\d_]{2,}", str(name))) >= 2


def _cfg(run: RunFolder) -> dict:
    return create_config.load(run)


PROMISES = {"results": ("checks.promise_results", "a result"),
            "availability": ("checks.promise_availability", "availability")}


def _claims(run: RunFolder) -> dict[str, str]:
    """The checked claims' texts by id."""
    data = create_plan.checked(run, create_plan.CLAIMS) or {}
    return {c["id"]: str(c.get("text", "")) for c in data.get("claims") or []
            if isinstance(c, dict) and _text(c.get("id"))}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _phrase(phrase: str) -> re.Pattern:
    """A phrase as whole words in any case; a word ending in `*` takes any ending."""
    parts = []
    for word in _fold(phrase).split():
        open_end = word.endswith("*")
        parts.append(re.escape(word.rstrip("*")) + (r"\w*" if open_end else ""))
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)")


def _market(run: RunFolder) -> str:
    return i18n.languages_of(_cfg(run)).market


def promises(run: RunFolder) -> list[tuple[str, str, re.Pattern]] | None:
    """(kind, phrase, pattern) of every promise phrase of the run's market language, or None when that language
    has no list (both keys of the string table are needed)."""
    table = i18n.table(_market(run))
    out = []
    for kind, (key, _) in PROMISES.items():
        text = table.get(key)
        if not isinstance(text, str):
            return None
        out += [(kind, p.strip(), _phrase(p.strip())) for p in text.split(",") if p.strip().rstrip("*")]
    return out


def promise_note(run: RunFolder) -> str | None:
    """What the promise check could not read, said plainly; None when the market language has its list."""
    if promises(run) is not None:
        return None
    lang = _market(run)
    return (f"{i18n.name(lang)} ({lang}), the copy's market language, has no list of promise phrases, so the copy "
            "was checked for numbers only. Read every text for promises of results or availability yourself (CA3: "
            "only what a checked claim says), or translate the string table (tm i18n export --lang "
            f"{lang}, then tm i18n import) and check again.")


def _text_problems(where: str, item: object, limit: int, claims: dict[str, str],
                   phrases: list[tuple[str, str, re.Pattern]] | None = None) -> list[Problem]:
    if not (isinstance(item, dict) and _text(item.get("text"))):
        return [Problem(where, f"{where} has no text.", "Write it.")]
    out, text = [], item["text"]
    if len(text) > limit:
        out.append(Problem(where, f"{where} has {len(text)} characters, over the {limit} allowed.", "Shorten it."))
    named = item.get("claims") or []
    unknown = [c for c in named if c not in claims]
    if unknown:
        out.append(Problem(where, f"{where} names claims that are not checked: {', '.join(map(str, unknown))}.",
                           "Use only the checked claims (CA3)."))
    backing = [claims[c] for c in named if c in claims]
    allowed = set().union(*(create_plan.numbers(t) for t in backing)) if backing else set()
    invented = sorted(create_plan.numbers(text) - allowed)
    if invented:
        out.append(Problem(where, f"{where} says {', '.join(invented)}, which is in none of its claims.",
                           "Take the number out, or name the checked claim it comes from (CA3: no invented numbers)."))
    said = [_fold(t) for t in backing]
    for kind, phrase, pattern in phrases or []:
        if pattern.search(_fold(text)) and not any(pattern.search(t) for t in said):
            out.append(Problem(where, f"{where} promises {PROMISES[kind][1]} (\"{phrase}\"), which none of its "
                               "claims says.", "Take the promise out, or name the checked claim that says it (CA3: "
                               "the copy never promises results or availability)."))
    return out


def _ad_problems(run: RunFolder, ad: object, n: int, cfg: dict, claims: dict[str, str],
                 lists_needed: bool = True) -> list[Problem]:
    if not isinstance(ad, dict):
        return [Problem(f"ads[{n}]", f"Ad {n} must be an object.", "Write it again.")]
    out: list[Problem] = []
    key = ad.get("key")
    label = key if _text(key) else f"ad {n}"
    if not (isinstance(key, str) and KEY_RE.match(key)):
        out.append(Problem(f"ads[{n}].key", f"{label}'s key must be lowercase letters, digits, - or _ (it is the "
                           "utm_content).", "Give it a key."))
    for field in ("ad_name", "video_title"):
        if not readable(ad.get(field)):
            out.append(Problem(f"ads[{n}].{field}", f"{label}'s {field} ({ad.get(field)!r}) does not say what it is.",
                               "Name it by product, test, audience and concept, never like \"Ad 1\" (CA14)."))
    if ad.get("cta") not in META_CTAS:
        out.append(Problem(f"ads[{n}].cta", f"{label}'s call to action {ad.get('cta')!r} is not one of Meta's.",
                           f"Pick one of {', '.join(META_CTAS)}."))
    brand = _host(str(cfg["brand"].get("url") or ""))
    link = ad.get("display_link")
    if not (_text(link) and _host(link) == brand):
        out.append(Problem(f"ads[{n}].display_link", f"{label}'s display link {link!r} is not the brand's site "
                           f"({brand}).", "Use the site's address."))
    url = ad.get("url")
    parsed = urlparse(url) if _text(url) else None
    if not (parsed and parsed.scheme in ("http", "https") and (_host(url) == brand or _host(url).endswith("." + brand))):
        out.append(Problem(f"ads[{n}].url", f"{label}'s URL {url!r} does not go to the brand's site ({brand}).",
                           "Use a page of the site."))
    else:
        query = parse_qs(parsed.query)
        missing = [k for k in UTM if not query.get(k) or not query[k][0].strip()]
        if missing:
            out.append(Problem(f"ads[{n}].url", f"{label}'s URL lacks {', '.join(missing)}.", "Add the UTM tags."))
        elif query["utm_content"][0] != key:
            out.append(Problem(f"ads[{n}].url", f"{label}'s utm_content is {query['utm_content'][0]!r}, not the ad key "
                               f"{key!r}.", "Set utm_content to the ad key (CA13)."))
    count = cfg["copy"]["count"]
    phrases = promises(run)
    for field, (limit_key, _) in LISTS.items():
        items = ad.get(field)
        if not isinstance(items, list):
            out.append(Problem(f"ads[{n}].{field}", f"{label} has no {field}.", f"Write {count}."))
            continue
        if lists_needed and len(items) != count:
            out.append(Problem(f"ads[{n}].{field}", f"{label} has {len(items)} {field}, not {count}.",
                               f"Write {count} (CA13)."))
        limit = cfg["copy"][limit_key.split(".")[1]]
        for i, item in enumerate(items, 1):
            out.extend(_text_problems(f"{label} {field}[{i}]", item, limit, claims, phrases))
    return out


def check_draft(run: RunFolder, data: dict) -> list[Problem]:
    cfg = _cfg(run)
    out: list[Problem] = []
    if create_plan.checked_file(run, create_plan.CLAIMS) is None:
        out.append(Problem("claims", "The claims are not checked.", "Check them first (tm ad check claims)."))
    ads = data.get("ads")
    if not (isinstance(ads, list) and ads):
        return out + [Problem("ads", "The copy has no ad.", "Write the copy per ad.")]
    claims = _claims(run)
    keys = [a.get("key") for a in ads if isinstance(a, dict)]
    if len(set(keys)) != len(keys):
        out.append(Problem("ads", "Two ads share a key.", "Give each ad its own key."))
    for n, ad in enumerate(ads, 1):
        out.extend(_ad_problems(run, ad, n, cfg, claims))
    return out


def _path(run: RunFolder, file: str | Path, stage: str, stem: str) -> tuple[Path, str]:
    path = run.given(str(file))
    try:
        rel = path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{file} is not inside the run folder.") from None
    latest = run.latest(stage, stem, "json")
    if latest is None or latest.resolve() != path.resolve():
        raise ValueError(f"{rel} is not the latest {stage}/{stem}_vNN.json: use the latest version.")
    return path, rel


def _load(path: Path) -> tuple[dict | None, list[Problem]]:
    return create_plan._read(path)


def check(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm ad copy check`: check the latest draft; a clean one is marked."""
    if state.load(run).playbook != CREATE_AD:
        raise ValueError("tm ad copy is for Create an ad runs.")
    path, rel = _path(run, file, WIP, DRAFT)
    data, problems = _load(path)
    if data is None:
        return rel, problems
    problems = check_draft(run, data)
    if not problems:
        stepchecks.mark(run, KEY_DRAFT, path)
    return rel, problems


def draft(run: RunFolder) -> dict | None:
    if stepchecks.fresh(run, KEY_DRAFT, WIP, DRAFT, "json") is not None:
        return None
    return _load(run.latest(WIP, DRAFT, "json"))[0]


def accept(run: RunFolder, file: str | Path) -> tuple[str, list[Problem]]:
    """`tm ad copy accept`: the user's choices on the checked draft become `04_final/copy_vNN.json` (checked again)."""
    if state.load(run).playbook != CREATE_AD:
        raise ValueError("tm ad copy is for Create an ad runs.")
    path, rel = _path(run, file, WIP, DECISIONS)
    choices, problems = _load(path)
    if choices is None:
        return rel, problems
    base = draft(run)
    if base is None:
        return rel, [Problem("copy", "The latest copy draft is not checked.", "Check it first (tm ad copy check).")]
    by_key = {a["key"]: a for a in base["ads"]}
    picked = {c.get("key"): c for c in choices.get("ads") or [] if isinstance(c, dict)}
    if set(picked) != set(by_key):
        return rel, [Problem("ads", f"The choices cover the ads {sorted(map(str, picked))}, not the draft's "
                             f"{sorted(by_key)}.", "Give the user's choice for every ad.")]
    out_ads, problems = [], []
    for key, ad in by_key.items():
        new = {k: v for k, v in ad.items() if k not in LISTS}
        for field in LISTS:
            kept = []
            for c in picked[key].get(field) or []:
                n = c.get("n") if isinstance(c, dict) else None
                if not (isinstance(n, int) and 1 <= n <= len(ad[field])):
                    problems.append(Problem(f"{key} {field}", f"A choice names text {n!r}, not one of the draft's.",
                                            "Name each text by its number in the draft."))
                    continue
                if c.get("keep") is True:
                    text = c.get("text") if _text(c.get("text")) else ad[field][n - 1]["text"]
                    kept.append({"text": text, "claims": ad[field][n - 1].get("claims") or [], "n": n})
            new[field] = kept
        for field in ("primary_texts", "headlines"):
            if not new[field]:
                problems.append(Problem(f"{key} {field}", f"{key} keeps no {field}.",
                                        "Keep at least one, or ask the user for a text."))
        out_ads.append(new)
    if problems:
        return rel, problems
    cfg = _cfg(run)
    claims = _claims(run)
    for n, ad in enumerate(out_ads, 1):
        problems.extend(_ad_problems(run, ad, n, cfg, claims, lists_needed=False))
    if problems:
        return rel, problems
    target = run.next_version(FINAL, ACCEPTED, "json")
    target.parent.mkdir(parents=True, exist_ok=True)
    note = choices.get("note")
    target.write_text(json.dumps({"ads": out_ads, "note": note if _text(note) else None, "from": rel},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    stepchecks.mark(run, KEY_ACCEPTED, target)
    return target.relative_to(run.path).as_posix(), []


def accepted(run: RunFolder) -> dict | None:
    """The accepted copy, when its latest version is the one `accept` wrote, unchanged; else None."""
    if stepchecks.fresh(run, KEY_ACCEPTED, FINAL, ACCEPTED, "json") is not None:
        return None
    return _load(run.latest(FINAL, ACCEPTED, "json"))[0]


def page_data(run: RunFolder) -> dict:
    """What the copy page shows (references/pages.md "Copy"): per ad its facts and each text with its live count
    against its limit and a keep tick; the question. Until the page is built, the card in chat shows the same. Its
    words are in the working language (`lang`), or in English with `language_warning` when it has no translation;
    the texts themselves are in the market language, as written."""
    data = draft(run) or {"ads": []}
    cfg = _cfg(run)
    tr, built = create_config.page_words(run)
    ads = []
    for ad in data["ads"]:
        lists = {}
        for field, (limit_key, label) in LISTS.items():
            limit = cfg["copy"][limit_key.split(".")[1]]
            lists[field] = {"label": tr(label), "items": [
                {"n": i, "text": it["text"], "limit": limit, "count": len(it["text"]), "keep": True,
                 "count_text": tr("ad.copy.count" if len(it["text"]) <= limit else "ad.copy.over",
                                  n=len(it["text"]), limit=limit)}
                for i, it in enumerate(ad.get(field) or [], 1)]}
        ads.append({"key": ad["key"], "facts": {k: ad.get(k) for k in ("ad_name", "video_title", "cta",
                                                                      "display_link", "url")},
                    "facts_label": tr("ad.copy.facts"), **lists})
    return {"lang": built.lang, "language_warning": built.warning, "title": tr("ad.copy.title"),
            "question": tr("ad.copy.question"), "keep_label": tr("ad.copy.keep"), "ads": ads}


# --- step checks ---------------------------------------------------------------

def copy_gap(run: RunFolder) -> str | None:
    gap = stepchecks.fresh(run, KEY_DRAFT, WIP, DRAFT, "json")
    return f"the Meta copy passes tm ad copy check ({gap})" if gap else None


def _in_manifest(run: RunFolder, rel: str) -> bool:
    manifest = run.path / "manifest.md"
    return manifest.is_file() and f"| {rel} |" in manifest.read_text(encoding="utf-8")


def delivered_gap(run: RunFolder) -> str | None:
    """S9 is done once the accepted copy exists and every ad in it has its video and thumbnail in 04_final, each in
    the manifest."""
    copy = accepted(run)
    if copy is None:
        return f"the accepted copy is written ({FINAL}/copy_vNN.json, tm ad copy accept after the copy check-in)"
    gaps = []
    for ad in copy["ads"]:
        video = run.latest(FINAL, ad["key"], "mp4")
        thumbs = [p for p in (run.latest(FINAL, f"{ad['key']}_thumb", ext) for ext in ("jpg", "png")) if p]
        for what, path in (("video", video), ("thumbnail", thumbs[0] if thumbs else None)):
            if path is None:
                gaps.append(f"{ad['key']}'s {what} is in {FINAL} ({ad['key']}"
                            f"{'_thumb' if what == 'thumbnail' else ''}_vNN.{'mp4' if what == 'video' else 'jpg'})")
            elif not _in_manifest(run, path.relative_to(run.path).as_posix()):
                gaps.append(f"{path.relative_to(run.path).as_posix()} is recorded in the manifest (tm record)")
    return ", and ".join(gaps) or None
