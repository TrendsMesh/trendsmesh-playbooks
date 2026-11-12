"""Brand and channel profiles, shared by the playbooks, in the workspace's library:
`library/brands/<slug>/brand_vNN.json` and `library/channels/<slug>/channel_vNN.json`.

    tm brand check --file F [--run R] [--json]           the agent's draft against the rules (exit 2 with the problems)
    tm brand save --run R --file F [--confirmed] [--json]  check, then save a new version in the library
    tm brand show --name N [--kind brand|channel] [--workspace W] [--json]   the latest saved profile
    tm brand packshot --name <store> --product P --file F --run R [--json]   a store's packshot, kept once

A brand profile (`brand/1`, drafted by the agent at A1 as `03_wip/brand_vNN.json`):

    {"schema": "brand/1", "kind": "brand", "brand": "...", "stands_for": "<one sentence>",
     "tone": ["w1", "w2", "w3"], "off_limits": ["..."], "off_limits_asked": true,
     "claims": [{"claim": "...", "wording": "...", "source": "<url or file>"}],
     "competitors": ["..."], "guide": {"source": "file|url|none", "where": "..."},
     "drafted_from": ["landing", "ads", "guide", "user"], "confirmed": "YYYY-MM-DD" | null,
     "catalog": {"products": [{"name": "...", "packshot": "<library path>" | null, "problems": ["..."]}]}}

`catalog` is optional: a store's catalogue, which every channel naming that store shares (organic
video, the plan's decision 12). Its packshots are made once per store (OV5) and kept beside the
profile, `library/brands/<slug>/packshots/<slug(product)>_vNN.<ext>`.

A channel profile (`channel/1`, organic video's A1, drafted as `03_wip/channel_<slug>_vNN.json`):

    {"schema": "channel/1", "kind": "channel", "channel": "...", "store": "<brand>" | null,
     "platforms": ["tiktok", "instagram", "youtube", "facebook"], "account_type": "creator|business",
     "audience_language": "pl", "context": {"films": "...", "topic": "...", "audience": "...",
     "style": "...", "performed_links": []}, "product_role": "not_shown|incidental|featured|soft_mention|hero",
     "content_rules": ["..."], "voice": {"narrator_elevenlabs_id", "host_description", "host_image"},
     "music": {"folder", "index"}, "assumptions": ["..."], "confirmed": "YYYY-MM-DD" | null}

`context.films`, `topic` and `audience` are the bubble the trend search starts from (OV1). A
channel that sells nothing (`store: null`) never shows a product; a named store must have a saved
brand profile with products. A channel's `confirmed` date is the user's: only `save(...,
confirmed=True)` (`--confirmed`) after the user's decision at the `profile` check-in sets it, and
a later version may only carry the date the saved profile already has.

Versions are append-only: a save writes the next `<kind>_vNN.json` and never touches an earlier one.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import date
from pathlib import Path

from tm import cli, config, manifest, paths, state, trend_spool
from tm.config import Problem
from tm.runfolder import STAGES, RunFolder, slug as _slug
from tm.stops import AGAIN, Stop

SCHEMA = "brand/1"
CHANNEL_SCHEMA = "channel/1"
KINDS = ("brand", "channel")
GUIDE_SOURCES = ("file", "url", "none")
DRAFTED_FROM = ("landing", "ads", "guide", "user")
DIR = Path("library") / "brands"
CHANNEL_DIR = Path("library") / "channels"
DIRS = {"brand": DIR, "channel": CHANNEL_DIR}   # kind -> library folder; the kind is also the file stem
STEM = "brand"
SOURCE = "tm brand save"
PACKSHOTS = "packshots"
PACKSHOT_SOURCE = "tm brand packshot"
PACKSHOT_TYPES = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpg", ".webp": ".webp"}  # suffix -> kept as
PLATFORMS = ("tiktok", "instagram", "youtube", "facebook")
ACCOUNT_TYPES = ("creator", "business")
PRODUCT_ROLES = ("not_shown", "incidental", "featured", "soft_mention", "hero")  # OV5, from none to hero
BUBBLE = ("films", "topic", "audience")  # OV1: the trend search starts from these
CONFIRMED_BY_USER = "A channel's profile is confirmed by the user."
_SENTENCE_BREAK = re.compile(r"([^\s]*[.!?])\s+[\"'“‘(\[]?[A-Z]")
_ABBREVIATIONS = ("e.g.", "i.e.", "vs.", "etc.", "no.", "mr.", "ms.", "dr.", "st.")
_CLOSERS = "\"'”’)]}»"


def _one_sentence(text: str) -> bool:
    """One sentence: ends with . ! or ? (a closing quote or bracket may follow), and no stop inside is followed
    by a space and a capital letter, unless the word before it is a common abbreviation."""
    text = text.strip().rstrip(_CLOSERS)
    if not text.endswith((".", "!", "?")):
        return False
    return not any(m.group(1).lower() not in _ABBREVIATIONS for m in _SENTENCE_BREAK.finditer(text))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _list_of_text(value: object) -> bool:
    return isinstance(value, list) and all(_text(v) for v in value)


def _confirmed_problem(confirmed: object) -> bool:
    if confirmed is None:
        return False
    try:
        return not (isinstance(confirmed, str) and date.fromisoformat(confirmed).isoformat() == confirmed)
    except ValueError:
        return True


def _text_or_none(value: object) -> bool:
    return value is None or _text(value)


def _catalog(catalog: object, bad) -> None:
    """A brand profile's optional catalogue: {products: [{name, packshot, problems}]}, names unique."""
    products = catalog.get("products") if isinstance(catalog, dict) else None
    if not isinstance(products, list):
        bad("catalog", "catalog must be {products: [{name, packshot, problems}]}.",
            "Write the store's products, or leave catalog out when nothing is sold.")
        return
    seen: set[str] = set()
    for i, p in enumerate(products):
        where = f"catalog.products[{i}]"
        if not isinstance(p, dict):
            bad(where, "A product must be an object {name, packshot, problems}.", "Rewrite it.")
            continue
        name = p.get("name")
        if not _text(name):
            bad(f"{where}.name", "The product has no name.", "Write its name.")
        elif name.strip().casefold() in seen:
            bad(f"{where}.name", f"{name!r} is in the catalogue twice.", "Keep one entry per product.")
        else:
            seen.add(name.strip().casefold())
        if not _text_or_none(p.get("packshot")):
            bad(f"{where}.packshot", "packshot must be the packshot's library path, or null.",
                "Save it with tm brand packshot, which writes the path, or set it to null.")
        if not _list_of_text(p.get("problems")):
            bad(f"{where}.problems", "problems must be a list of texts (empty when none is known).",
                "Write the problems the product solves, or [].")


def _store_problem(store: str, workspace: Path, bad) -> None:
    """A named store needs a saved brand profile with products (OV1: its channels share one catalogue)."""
    try:
        saved = latest(workspace, store)
    except ValueError as exc:
        bad("store", str(exc), "Fix the store's saved profile, then check the channel again.")
        return
    if saved is None:
        bad("store", f"No brand profile is saved for the store {store!r}, so its catalogue is unknown.",
            "Save the store's profile with its catalogue first (tm brand save), then check the channel "
            "again; or set store to null and product_role to not_shown when nothing is sold.")
    elif not (saved.get("catalog") or {}).get("products"):
        bad("store", f"The store {store!r} has no products in its catalogue.",
            "Add catalog.products to the store's brand profile and save it, or set store to null and "
            "product_role to not_shown.")


def _check_channel(profile: dict, workspace: Path | None, bad) -> None:
    if profile.get("schema") != CHANNEL_SCHEMA:
        bad("schema", f"The schema is {profile.get('schema')!r}.", f"Set it to {CHANNEL_SCHEMA!r}.")
    if not _text(profile.get("channel")):
        bad("channel", "The channel has no name.", "Write the channel's name.")
    platforms = profile.get("platforms")
    if not (isinstance(platforms, list) and platforms and all(p in PLATFORMS for p in platforms)
            and len(set(platforms)) == len(platforms)):
        bad("platforms", f"platforms must be one or more of {', '.join(PLATFORMS)}, each once, not {platforms!r}.",
            "List the platforms the channel posts on.")
    if profile.get("account_type") not in ACCOUNT_TYPES:
        bad("account_type", f"account_type must be {' or '.join(ACCOUNT_TYPES)}, not {profile.get('account_type')!r}.",
            "Ask whether the accounts are creator or business accounts (it decides the sounds allowed).")
    if not _text(profile.get("audience_language")):
        bad("audience_language", "The audience language is missing (captions and speech are in it).",
            "Write it from the channel, and confirm it with the user.")
    context = profile.get("context")
    if not isinstance(context, dict):
        bad("context", "context must be {films, topic, audience, style, performed_links}.",
            "Write what the channel films, about what and for whom.")
    else:
        for key in BUBBLE:
            if not _text(context.get(key)):
                bad(f"context.{key}", f"context.{key} is empty, and the trend search starts from it (OV1: the "
                    "bubble comes from what the channel films, about what and for whom).",
                    f"Ask the user, then write context.{key}.")
        if not _text_or_none(context.get("style")):
            bad("context.style", "context.style must be a text, or null.", "Write the channel's style.")
        if not _list_of_text(context.get("performed_links", [])):
            bad("context.performed_links", "performed_links must be a list of links ([] when none is given).",
                "Write the links, or [].")
    role = profile.get("product_role")
    store = profile.get("store")
    if role not in PRODUCT_ROLES:
        bad("product_role", f"product_role must be one of {', '.join(PRODUCT_ROLES)}, not {role!r}.",
            "Ask the user how much the product may be shown.")
    if store is None:
        if role in PRODUCT_ROLES and role != "not_shown":
            bad("product_role", f"Nothing is sold (store is null), so the product cannot be {role}.",
                "Set product_role to not_shown, or name the store whose catalogue the channel shows.")
    elif not _text(store):
        bad("store", "store must be the name of a saved store profile, or null when nothing is sold.",
            "Name the store, or set it to null.")
    else:
        if workspace is None:
            raise ValueError("A channel profile that names a store is checked against the workspace's "
                             "library: pass the workspace.")
        _store_problem(store, Path(workspace), bad)
    for key, what in (("content_rules", "content_rules"), ("assumptions", "assumptions")):
        if not _list_of_text(profile.get(key)):
            bad(key, f"{what} must be a list of texts ([] when there are none).", f"Write {what} as a list.")
    for key, keys in (("voice", ("narrator_elevenlabs_id", "host_description", "host_image")),
                      ("music", ("folder", "index"))):
        group = profile.get(key)
        if not (isinstance(group, dict) and all(_text_or_none(group.get(k)) for k in keys)):
            bad(key, f"{key} must be {{{', '.join(keys)}}}, each a text or null.",
                f"Write {key} as an object, with null for what is not known yet.")
    if _confirmed_problem(profile.get("confirmed")):
        bad("confirmed", f"confirmed is {profile.get('confirmed')!r}.",
            "Use null; tm brand save --confirmed sets the date once the user accepts the profile.")


def check(profile: object, *, workspace: Path | None = None) -> list[Problem]:
    """What is wrong with a profile; an empty list when it can be saved. The kind is read first, so a
    channel is checked against channel/1. A channel that names a store is checked against the saved
    store profile in `workspace`'s library (ValueError when no workspace is given)."""
    if not isinstance(profile, dict):
        return [Problem("profile", "The profile must be one JSON object.", "Write it as one object.")]
    out: list[Problem] = []

    def bad(field: str, what: str, todo: str) -> None:
        out.append(Problem(field, what, todo))

    kind = profile.get("kind")
    if kind == "channel":
        _check_channel(profile, workspace, bad)
        return out
    if profile.get("schema") != SCHEMA:
        bad("schema", f"The schema is {profile.get('schema')!r}.", f"Set it to {SCHEMA!r}.")
    if kind != "brand":
        bad("kind", f"The kind is {kind!r}.", f"Use one of {', '.join(KINDS)}.")
    if not _text(profile.get("brand")):
        bad("brand", "The brand has no name.", "Write the brand's name.")
    stands = profile.get("stands_for")
    if not _text(stands) or not _one_sentence(stands):
        bad("stands_for", "What the brand stands for must be one sentence, with one stop at the end.",
            "Rewrite it as one sentence.")
    tone = profile.get("tone")
    if not (isinstance(tone, list) and len(tone) == 3 and all(_text(w) and len(w.split()) == 1 for w in tone)):
        bad("tone", "The tone must be exactly three words.", "Give three single words, e.g. [\"warm\", \"plain\", \"dry\"].")
    if not _list_of_text(profile.get("off_limits")):
        bad("off_limits", "off_limits must be a list of texts (empty when nothing is off limits).",
            "Write the list, or [] when the user says nothing is.")
    if profile.get("off_limits_asked") is not True:
        bad("off_limits_asked", "The user was not asked what is off limits.",
            "Ask \"anything off-limits?\" on the confirmation card, then set off_limits_asked to true.")
    claims = profile.get("claims")
    if not isinstance(claims, list):
        bad("claims", "claims must be a list.", "Write the list of claims (empty when there are none).")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                bad(f"claims[{i}]", "A claim must be an object {claim, wording, source}.", "Rewrite it.")
                continue
            for key in ("claim", "wording"):
                if not _text(c.get(key)):
                    bad(f"claims[{i}].{key}", f"The claim has no {key}.", f"Write its {key}.")
            if not _text(c.get("source")):
                bad(f"claims[{i}].source", f"The claim {c.get('claim')!r} has no source.",
                    "Name the page or file it comes from, or drop the claim.")
    if not _list_of_text(profile.get("competitors")):
        bad("competitors", "competitors must be a list of names.", "Write the list ([] when there are none).")
    guide = profile.get("guide")
    if not (isinstance(guide, dict) and guide.get("source") in GUIDE_SOURCES):
        bad("guide", "guide must be {source: file|url|none, where}.", "Say where the brand guide is, or source \"none\".")
    drafted = profile.get("drafted_from")
    if not (isinstance(drafted, list) and drafted and all(d in DRAFTED_FROM for d in drafted)):
        bad("drafted_from", "drafted_from must list what the draft came from.",
            f"Use one or more of {', '.join(DRAFTED_FROM)}.")
    if _confirmed_problem(profile.get("confirmed")):
        bad("confirmed", f"confirmed is {profile.get('confirmed')!r}.",
            "Use null until the user confirms, then the date, YYYY-MM-DD.")
    if "catalog" in profile:
        _catalog(profile["catalog"], bad)
    return out


def _kind(profile: dict) -> str:
    return "channel" if profile.get("kind") == "channel" else "brand"


def _folder(workspace: Path, name: str, kind: str = "brand") -> Path:
    return Path(workspace) / DIRS[kind] / _slug(name).lower()   # for a channel, its channel_key


def _versions(folder: Path, stem: str = STEM, ext: str = r"json") -> list[tuple[int, Path]]:
    """The <stem>_vNN.<ext> files in `folder`, by NN (`ext` is a regular expression)."""
    found = []
    for p in folder.glob(f"{stem}_v*") if folder.is_dir() else []:
        m = re.fullmatch(rf"{re.escape(stem)}_v(\d+)\.{ext}", p.name)
        if m:
            found.append((int(m.group(1)), p))
    return sorted(found)


def _write_new(folder: Path, stem: str, data: str | bytes, start: int, ext: str = ".json") -> Path:
    """Create <stem>_vNN<ext> with the lowest free NN from `start`; an existing file is never opened for writing."""
    folder.mkdir(parents=True, exist_ok=True)
    n = start
    while True:
        path = folder / f"{stem}_v{n:02d}{ext}"
        try:
            if isinstance(data, bytes):
                with open(path, "xb") as fh:
                    fh.write(data)
            else:
                with open(path, "x", encoding="utf-8") as fh:
                    fh.write(data)
            return path
        except FileExistsError:
            n += 1


def _user_accepted_profile(run: RunFolder | None, profile: dict) -> bool:
    """The user accepted this profile at the `profile` check-in. A brand, or the channel of a one-channel run,
    is confirmed by any user `profile` decision; in a run of several channels each channel needs its own,
    whose note names its key (`tm decide profile accept --note cat-corner`, then `--change` for the next)."""
    if run is None:
        return False
    decisions = [d for d in state.load(run).decisions if d.get("checkin") == "profile" and d.get("by") == "user"]
    if _kind(profile) == "brand":
        return bool(decisions)
    key = channel_key(str(profile.get("channel", "")))
    if any(key in {channel_key(w) for w in re.findall(r"[\w-]+", str(d.get("note") or ""))}
           for d in decisions):  # a word of the note is the key, letters with diacritics too
        return True
    try:
        channels = config.load(run).get("channels")
    except ValueError:
        channels = None
    return bool(decisions) and channels == [key]


def save(workspace: Path, profile: dict, *, run: RunFolder | None, confirmed: bool = False) -> Path:
    """Write the profile as its kind's next library version and return its path. Refuses (ValueError) a
    profile that breaks the rules. With a run, the run keeps a copy in 04_final and a manifest row.

    `confirmed` sets the profile's `confirmed` to today, and needs `run` with the user's decision at
    the `profile` check-in. A channel draft cannot bring a date of its own, except the one its latest
    saved version already has."""
    problems = check(profile, workspace=workspace)
    if problems:
        raise ValueError(f"The {_kind(profile)} profile is not ready: "
                         + " ".join(f"{p.field}: {p.what}" for p in problems))
    kind = _kind(profile)
    if confirmed:
        if not _user_accepted_profile(run, profile):
            raise ValueError(f"{CONFIRMED_BY_USER} Ask the user at the profile check-in (tm decide profile accept; "
                             "in a run of several channels, one decision per channel with --note <channel key>), "
                             "then save it with --confirmed.")
        profile = {**profile, "confirmed": date.today().isoformat()}
    elif kind == "channel" and profile.get("confirmed") is not None:
        saved = latest(workspace, profile[kind], kind=kind)
        if saved is None or saved.get("confirmed") != profile["confirmed"]:
            raise ValueError(f"{CONFIRMED_BY_USER} Set confirmed to null in the draft; tm brand save --confirmed "
                             "sets the date after the user accepts it at the profile check-in.")
    folder = _folder(workspace, profile[kind], kind)
    versions = _versions(folder, kind)
    text = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    saved = _write_new(folder, kind, text, (versions[-1][0] if versions else 0) + 1)
    if run is not None:
        kept = run.next_version("04_final", kind, "json")
        kept.write_text(text, encoding="utf-8")
        manifest.record(run, f"04_final/{kept.name}", "04_final", SOURCE,
                        params={"library": saved.relative_to(Path(workspace)).as_posix()})
    return saved


def channel_key(name: str) -> str:
    """A channel's one key, its slug: the library folder and config.yaml `channels` ("Cat Corner" -> cat-corner)."""
    return _slug(name).lower()


def _newest(workspace: Path, kind: str, folder_name: str, same,
            skipped: list[str] | None = None) -> tuple[dict, Path] | None:
    """The newest profile of `kind` in the kind's folder for `folder_name` for which `same(profile)` holds, and its
    file. A file whose own `kind` is another is never read as this kind: it is skipped, and named in `skipped`."""
    for _, path in reversed(_versions(_folder(workspace, folder_name, kind), kind)):
        rel = path.relative_to(Path(workspace)).as_posix()
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            profile = exc
        if not isinstance(profile, dict):
            raise ValueError(f"{rel} is damaged (not one JSON object), so the saved profiles of {folder_name!r} "
                             "cannot be read. Fix or delete that file, then run this again.")
        if profile.get("kind") != kind:
            if skipped is not None:
                skipped.append(f"{rel} is not a {kind} profile (its kind is {profile.get('kind')!r})")
            continue
        if same(profile):
            return profile, path
    return None


def latest(workspace: Path, name: str, kind: str = "brand", skipped: list[str] | None = None) -> dict | None:
    """The latest saved profile of a brand or a channel, else None (`latest_saved`, without its file)."""
    found = latest_saved(workspace, name, kind, skipped)
    return found[0] if found else None


def latest_saved(workspace: Path, name: str, kind: str = "brand",
                 skipped: list[str] | None = None) -> tuple[dict, Path] | None:
    """The latest saved profile of a brand (or, with kind="channel", a channel) and its file, else None. A brand is
    matched by its name: names that share a folder (\"A&B\", \"A B\") are told apart by the profile's
    own `brand`. A channel is matched by its key (`channel_key`), as config.yaml names it, so "Cat Corner"
    and "cat-corner" are the same channel. Files of the other kind are skipped (named in `skipped`)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}, not {kind!r}.")
    if kind == "channel":
        key = channel_key(name)
        return _newest(workspace, kind, key, lambda p: channel_key(str(p.get("channel", ""))) == key, skipped)
    want = name.strip().casefold()
    return _newest(workspace, kind, name, lambda p: str(p.get(kind, "")).strip().casefold() == want, skipped)


def saved_from(workspace: Path, saved: Path) -> dict | None:
    """The run a saved profile came from (issue 59: a profile offered for reuse names its run and date): the run
    whose manifest has the row `tm brand save` wrote for this library file, so a profile saved before this was
    asked is found too. None for a profile saved without a run, or whose run is no longer in the workspace."""
    workspace = Path(workspace)
    rel = saved.relative_to(workspace).as_posix()
    for man in sorted((workspace / "runs").glob("*/*/manifest.md")):
        run = RunFolder(man.parent)
        for row in manifest.rows(run):
            if row["source"] != SOURCE:
                continue
            try:
                params = json.loads(row["params"] or "{}")
            except ValueError:
                continue
            if isinstance(params, dict) and params.get("library") == rel:
                try:
                    created = state.load(run).created
                except (OSError, ValueError):
                    created = None
                return {"run": run.path.name, "folder": run.path.relative_to(workspace).as_posix(),
                        "created": created, "saved": row["date"] or None}
    return None


def _origin_line(profile: dict, rel: str, origin: dict | None) -> str:
    """One sentence for the reuse card: where the profile was saved from, and when the user confirmed it."""
    confirmed = (f"; the user confirmed it on {profile['confirmed']}" if profile.get("confirmed")
                 else "; the user has not confirmed it")
    if origin is None:
        return f"{rel} was saved without a run this workspace still has{confirmed}."
    return (f"{rel} was saved from the run {origin['run']} (started {origin['created']}) on "
            f"{origin['saved']}{confirmed}.")


# --- a store's packshots (OV5: made once per store, shared by its channels) -----------------------

def save_packshot(workspace: Path, store: str, product: str, source: Path, *, run: RunFolder) -> tuple[Path, Path]:
    """Copy `source` (an image inside the run) to the store's next
    `library/brands/<slug>/packshots/<slug(product)>_vNN.<ext>`, save a new brand version whose catalogue
    names it, and add a manifest row. Returns (packshot, brand profile). Never overwrites."""
    profile = latest(workspace, store)
    if profile is None:
        raise Stop(f"No brand profile named {store!r} in {DIR.as_posix()}/: save the store's profile with its "
                   f"catalogue first (tm brand save), then run this again; {AGAIN}.")
    products = [p for p in (profile.get("catalog") or {}).get("products") or [] if isinstance(p, dict)]
    match = [p for p in products if str(p.get("name", "")).strip().casefold() == product.strip().casefold()]
    if not match:
        names = ", ".join(str(p.get("name")) for p in products) or "it has no products"
        raise Stop(f"{product!r} is not in the catalogue of {profile['brand']} ({names}). Add it to "
                   f"catalog.products and save the profile (tm brand save), then run this again; {AGAIN}.")
    source = Path(source)
    try:
        rel = source.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{source} is not inside the run folder: save the packshot in the run first "
                         "(for example 00_raw/<name>.png), then run this again.") from None
    ext = PACKSHOT_TYPES.get(source.suffix.lower())
    if ext is None:
        raise ValueError(f"{rel} is not a packshot image: give a PNG, JPG or WebP file.")
    if rel.split("/")[0] not in STAGES:  # e.g. at the run's root: the run keeps it as an original, in 00_raw
        kept = run.unique_path(f"00_raw/{source.name}")
        with open(kept, "xb") as fh:
            fh.write(source.read_bytes())
        rel = kept.relative_to(run.path).as_posix()
    folder = _folder(workspace, profile["brand"]) / PACKSHOTS
    stem = _slug(product).lower()
    versions = _versions(folder, stem, r"[a-z]+")
    shot = _write_new(folder, stem, source.read_bytes(), (versions[-1][0] if versions else 0) + 1, ext)
    shot_rel = shot.relative_to(Path(workspace)).as_posix()
    updated = copy.deepcopy(profile)
    for p in updated["catalog"]["products"]:
        if isinstance(p, dict) and str(p.get("name", "")).strip().casefold() == product.strip().casefold():
            p["packshot"] = shot_rel
    saved = save(workspace, updated, run=run)
    manifest.record(run, rel, rel.split("/")[0], PACKSHOT_SOURCE,  # a stage folder, as checked above
                    params={"library": shot_rel, "store": profile["brand"], "product": match[0]["name"]})
    return shot, saved


# --- the profile_written step check (organic video's A1) -------------------------------------------

def channel_gap(run: RunFolder) -> str | None:
    """A1 is done once every channel the run's config names (`channels`, slugs) has a saved profile in
    the library that passes the channel check. B1 asks the same, since a `reuse` at `reuse_profile`
    skips A1. Reads only. The gaps, or None."""
    return _channels_gap(run, confirmed=False)


def confirmed_gap(run: RunFolder) -> str | None:
    """`reuse_profile` reuse is recorded once every channel the run's config names has a saved,
    checked profile that the user confirmed (its `confirmed` date): a reuse skips A1, where a new
    profile is drafted and confirmed. Reads only. The gaps, or None."""
    return _channels_gap(run, confirmed=True)


def _channels_gap(run: RunFolder, *, confirmed: bool) -> str | None:
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = {}
    channels = cfg.get("channels")
    if not (isinstance(channels, list) and channels and all(_text(c) for c in channels)):
        return "config.yaml channels names the channel this run is for (tm config write at A0)"
    workspace = trend_spool.workspace_of(run)
    gaps = []
    for slug in channels:
        where = f"{CHANNEL_DIR.as_posix()}/{slug}/channel_vNN.json"
        skipped: list[str] = []
        try:
            profile = latest(workspace, slug, kind="channel", skipped=skipped)
            problems = check(profile, workspace=workspace) if profile is not None else []
        except ValueError as exc:
            gaps.append(f"the saved profiles of the channel {slug} can be read ({exc})")
            continue
        if profile is None:
            not_read = f"; {'; '.join(skipped)}" if skipped else ""
            gaps.append(f"the channel profile {slug} is saved with tm brand save ({where}){not_read}")
        elif problems:
            gaps.append(f"the saved channel profile {slug} passes tm brand check "
                        f"({'; '.join(p.field + ': ' + p.what for p in problems)})")
        elif confirmed and not profile.get("confirmed"):
            gaps.append(f"the saved channel profile {slug} is confirmed by the user")
    return ", and ".join(gaps) or None


# --- command line -----------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="check the agent's brand or channel profile draft")
    c.add_argument("--run", help="the run folder: --file is then found from here first, else in the run")
    c.add_argument("--file", required=True, help="the draft, 03_wip/brand_vNN.json or 03_wip/channel_<slug>_vNN.json")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("save", help="save the checked profile as its next library version")
    s.add_argument("--run", required=True, help="the run folder")
    s.add_argument("--file", required=True, help="the draft (from here first, else in the run)")
    s.add_argument("--confirmed", action="store_true",
                   help="the user accepted it at the profile check-in: set confirmed to today")
    s.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="the latest saved profile of a brand or channel")
    sh.add_argument("--name", required=True, help="the brand's or channel's name")
    sh.add_argument("--kind", choices=KINDS, default="brand")
    sh.add_argument("--workspace", help="default the current workspace")
    sh.add_argument("--json", action="store_true")
    ps = sub.add_parser("packshot", help="keep a product's packshot once for its store, in the store's catalogue")
    ps.add_argument("--name", required=True, help="the store's brand name")
    ps.add_argument("--product", required=True, help="the product's name in the catalogue")
    ps.add_argument("--file", required=True, help="the image, inside the run (from here first, else in the run)")
    ps.add_argument("--run", required=True, help="the run folder")
    ps.add_argument("--json", action="store_true")


def _load(path: str | Path) -> object:
    """The draft at `path`. A path that names no file is a bad argument (OSError, exit 1); a draft that
    is not JSON is the agent's file to fix (Stop, exit 2)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{path} is not valid JSON ({exc}). Write the profile again as one JSON object, then run this "
                   f"again; {AGAIN}.") from exc


def _what(profile: object) -> str:
    return f"{_kind(profile)} profile" if isinstance(profile, dict) else "profile"


def _problems(args: argparse.Namespace, profile: object, problems: list[Problem]) -> int:
    lines = [f"- {p.field}: {p.what} {p.todo}" for p in problems]
    message = (f"The {_what(profile)} needs fixing:\n" + "\n".join(lines)
               + f"\nFix the file, then check it again; {AGAIN}.")
    cli.emit(args, {"status": "stop", "message": message,
                    "problems": [{"field": p.field, "what": p.what, "todo": p.todo} for p in problems]}, message)
    return 2


def _done(args: argparse.Namespace, saved: Path, workspace: Path) -> int:
    rel = saved.relative_to(workspace).as_posix()
    cli.emit(args, {"status": "done", "file": rel, "message": f"Saved {rel}."}, f"Saved {rel}.")
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        if args.action == "show":
            workspace = Path(args.workspace) if args.workspace else paths.workspace()
            skipped: list[str] = []
            found = latest_saved(workspace, args.name, kind=args.kind, skipped=skipped)
            if found is None:
                not_read = f" Not read: {'; '.join(skipped)}." if skipped else ""
                return cli.fail(args, f"No {args.kind} profile named {args.name!r} in "
                                      f"{DIRS[args.kind].as_posix()}/.{not_read}")
            profile, path = found
            origin = saved_from(workspace, path)
            line = _origin_line(profile, path.relative_to(workspace).as_posix(), origin)
            cli.emit(args, {"status": "done", "profile": profile, "file": path.relative_to(workspace).as_posix(),
                            "saved_from": origin, "message": line},
                     f"{line}\n{json.dumps(profile, ensure_ascii=False, indent=2)}")
            return 0
        run = RunFolder.open(Path(args.run)) if args.run else None
        workspace = trend_spool.workspace_of(run) if run else paths.workspace()
        if args.action == "packshot":
            shot, _ = save_packshot(workspace, args.name, args.product, run.given(args.file), run=run)
            return _done(args, shot, workspace)
        profile = _load(run.given(args.file) if run else args.file)
        problems = check(profile, workspace=workspace)
        if problems:
            return _problems(args, profile, problems)
        if args.action == "check":
            message = f"The {_what(profile)} is ready to save."
            cli.emit(args, {"status": "done", "message": message}, message)
            return 0
        return _done(args, save(workspace, profile, run=run, confirmed=args.confirmed), workspace)
    except Stop as exc:
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("brand", _setup, _run)
