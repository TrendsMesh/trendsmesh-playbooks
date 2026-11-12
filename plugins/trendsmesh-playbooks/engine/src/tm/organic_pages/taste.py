"""The style, voice and music page (organic video D2, issue #83 point 2): the voiceover script with its times and a
note on each line, 2 to 3 styles, a few voices with a player (the library's and the user's own), and the music, each
heard or seen before it is chosen.

    page_json(run, options_file)   the page's data (tm.organic_pages.choices)
    take(run, *, file, text)       03_wip/taste_vNN.json, and the next 03_wip/pack_vNN.json with `taste` filled in

The agent writes what to offer as `03_wip/taste_options_vNN.json` (the next version for every change), from the run's
own files only:

    {"styles": [{"id", "label", "why", "preview", "recommended"}],
     "voices": [{"voice_id", "name", "why", "preview", "source": "library|mine", "recommended"}],
     "music": {"trending": {"name", "link", "why"} | null,
               "tracks": [{"file", "title", "why", "licence", "recommended"}]}}

A voice row may be a row of `tm tool elevenlabs voices --json` as it is (`preview_file` is read as `preview`), from the
library search or from `--mine`, the user's own voices (a row with `category`, which only `--mine` gives, is
`source: "mine"`). A track's `file` may be the name `tm tool music_fetch --copy` copied into `02_research/music/` (a row of the music
index taken as it is). `preview` and `file` are run files (a voice's preview clip as `tm tool elevenlabs voices` saves it, the user's own
voices' as `voices --mine` does; a track copied into the run): the page carries them, since it cannot play a sound
from another site. Styles are offered for an animation only, voices when someone speaks off screen, as D2 says; the
script is the recipe-checked pack's lines. Music: "No track, I'll add a sound in the app" comes first; the default is
the trending sound when trend research found one that fits (the user adds it in the app at posting), else the
recommended track, else no track.

`take` reads the choices (the page, or the user's words in chat) into `03_wip/taste_vNN.json` = `{style, voice:
{voice_id, name, source} | null, music: {kind: none|trending|track, file, title, name, link}, line_notes, notes}` and
writes the next pack version with `taste` filled in (`by: user`), so the agent does not copy the picks by hand: check
it again with `tm organic pack check --stage recipe`.
"""

from __future__ import annotations

import json
from pathlib import Path

from tm import manifest, organic_pages, stepchecks, state
from tm.organic_pages import choices
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "taste"
OPTIONS = "taste_options"
STEM = "taste"
WIP = "03_wip"
_T = "organic.taste."
NO_TRACK = "none"
TRENDING = "trending"
OPTIONS_SOURCE = "agent's taste options (D2)"


def _recipe_pack(run: RunFolder) -> tuple[str, dict]:
    """The latest pack, checked at the recipe stage and unchanged since: (its run path, the pack)."""
    gap = stepchecks.fresh(run, "recipe", WIP, "pack", "json")
    entry = state.load(run).checked.get("recipe") or {}
    if gap is not None or not entry.get("file"):
        raise Stop(f"The style, voice and music page shows the recipe's script, and {gap or 'no recipe is checked'}: "
                   f"check the pack first (tm organic pack check --stage recipe), then build the page; {AGAIN}.")
    try:
        return entry["file"], json.loads((run.path / entry["file"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise Stop(f"{entry['file']} cannot be read: write the recipe again and check it; {AGAIN}.") from None


def _options(run: RunFolder, rel: str | None) -> tuple[str, dict]:
    path = run.path / rel if rel else run.latest(WIP, OPTIONS, "json")
    if path is None or not Path(path).is_file():
        raise Stop(f"Write what to offer first, {WIP}/{OPTIONS}_vNN.json (styles, voices, music, each from the run's own "
                   f"files: flow.md D2), then build the page; {AGAIN}.")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise Stop(f"{Path(path).name} is not JSON ({exc}): write it again as a new version; {AGAIN}.") from None
    if not isinstance(data, dict):
        raise Stop(f"{Path(path).name} must be an object with styles, voices and music; {AGAIN}.")
    return Path(path).resolve().relative_to(run.path.resolve()).as_posix(), data


def _clock(at: object) -> str:
    if isinstance(at, list) and len(at) == 2 and all(isinstance(x, (int, float)) for x in at):
        return f"{at[0]:g}–{at[1]:g} s"
    return ""


RUN_MUSIC = "02_research/music"     # where `tm tool music_fetch --copy` puts the offered tracks (issue #89)


def track_row(run: RunFolder, x: dict) -> dict:
    """A track as offered: its `file` a run file, or a name `tm tool music_fetch --copy` copied into
    `02_research/music/` (so a row of the music index, whose `file` is the name in the channel's folder, is taken as
    it is)."""
    if not (isinstance(x, dict) and isinstance(x.get("file"), str) and x["file"].strip()):
        return x
    given = x["file"].replace("\\", "/")
    if (run.path / given).is_file() and not Path(given).is_absolute():
        return x
    copied = f"{RUN_MUSIC}/{Path(given).name}"
    return {**x, "file": copied} if (run.path / copied).is_file() else x


def voice_row(v: dict) -> dict:
    """A voice as offered: a row of `tm tool elevenlabs voices --json` taken as it is (`preview_file` -> `preview`;
    a `--mine` row, which has `category`, is the user's own)."""
    if not isinstance(v, dict):
        return v
    source = v.get("source") or ("mine" if "category" in v else "library")
    return {**v, "preview": v.get("preview") or v.get("preview_file"), "source": source}


def _problems(opts: dict) -> list[str]:
    out = []
    for key in ("styles", "voices"):
        items = opts.get(key) or []
        if not isinstance(items, list):
            out.append(f"{key} must be a list")
            continue
        for n, item in enumerate(items, 1):
            ident = item.get("id" if key == "styles" else "voice_id") if isinstance(item, dict) else None
            if not (isinstance(ident, str) and ident.strip()):
                out.append(f"{key} {n} needs its {'id' if key == 'styles' else 'voice_id'}")
            if key == "voices" and isinstance(item, dict) and not item.get("preview"):
                out.append(f"voice {ident}: a voice is offered with its preview clip (a run file), so it is heard first; "
                           "leave out a voice the tool found no preview for")
    music = opts.get("music") or {}
    if not isinstance(music, dict):
        return out + ["music must be an object with trending and tracks"]
    for n, track in enumerate(music.get("tracks") or [], 1):
        if not (isinstance(track, dict) and isinstance(track.get("file"), str) and track["file"].strip()):
            out.append(f"track {n} needs its file in the run")
    trending = music.get("trending")
    if trending is not None and not (isinstance(trending, dict) and isinstance(trending.get("name"), str)):
        out.append("music.trending is {name, link, why} or null")
    return out


def _slug_id(text: str, taken: set[str]) -> str:
    from tm.organic_gates import item_id
    return item_id(text, taken)


def page_json(run: RunFolder, options_file: str | None = None) -> dict:
    """The page's data, from the recipe-checked pack (its language and script) and the options file."""
    pack_rel, pack = _recipe_pack(run)
    opts_rel, opts = _options(run, options_file)
    if isinstance(opts.get("voices"), list):
        opts = {**opts, "voices": [voice_row(v) for v in opts["voices"]]}
    music_opts = opts.get("music")
    if isinstance(music_opts, dict) and isinstance(music_opts.get("tracks"), list):
        opts = {**opts, "music": {**music_opts, "tracks": [track_row(run, x) for x in music_opts["tracks"]]}}
    bad = _problems(opts)
    if bad:
        raise Stop(f"{opts_rel} needs fixing: {'; '.join(bad[:5])}. Write the next version, then build again; {AGAIN}.")
    tr = organic_pages.translator(organic_pages.lang_of(pack))
    t = lambda key, **v: tr(_T + key, **v)
    sections = []
    lines = [ln for ln in pack["script"]["lines"] if ln.get("speaker") != "none"]
    if lines:
        sections.append({"id": "script", "kind": "text", "title": t("script"), "hint": t("script_hint"),
                         "lines": [{"id": str(ln["n"]), "at": _clock(ln.get("at")), "text": ln["text"]} for ln in lines],
                         "note": t("script_note")})
    styles = opts.get("styles") or []
    if styles:
        taken: set[str] = set()
        rec = any(s.get("recommended") for s in styles)
        sections.append({"id": "style", "kind": "one", "title": t("style"), "hint": t("style_hint"), "note": t("note"),
                         "options": [{"id": _slug_id(str(s["id"]), taken), "label": str(s.get("label") or s["id"]),
                                      "means": s.get("why") or "", "recommended": bool(s.get("recommended")),
                                      "default": bool(s.get("recommended")) or (not rec and n == 0),
                                      "media": [{"src": s["preview"], "caption": str(s.get("label") or s["id"])}]
                                      if s.get("preview") else []}
                                     for n, s in enumerate(styles)]})
    voices = opts.get("voices") or []
    if voices:
        taken = set()
        rec = any(v.get("recommended") for v in voices)
        sections.append({"id": "voice", "kind": "one", "title": t("voice"), "hint": t("voice_hint"), "note": t("note"),
                         "options": [{"id": _slug_id(str(v["voice_id"]), taken), "label": str(v.get("name") or v["voice_id"]),
                                      "means": v.get("why") or "", "recommended": bool(v.get("recommended")),
                                      "badge": t("voice_mine") if v.get("source") == "mine" else None,
                                      "default": bool(v.get("recommended")) or (not rec and n == 0),
                                      "media": [{"src": v["preview"], "caption": str(v.get("name") or "")}]}
                                     for n, v in enumerate(voices)]})
    music = opts.get("music") or {}
    trending = music.get("trending")
    tracks = music.get("tracks") or []
    rec_track = next((n for n, x in enumerate(tracks) if x.get("recommended")), None)
    options = [{"id": NO_TRACK, "label": t("no_track"), "means": t("no_track_means"),
                "default": trending is None and rec_track is None}]
    if trending:
        options.append({"id": TRENDING, "label": t("trending", name=trending["name"]),
                        "means": " ".join(x for x in (trending.get("why") or "", t("trending_means")) if x),
                        "link": trending.get("link"), "default": True, "recommended": True})
    taken = {NO_TRACK, TRENDING}
    for n, x in enumerate(tracks):
        title = str(x.get("title") or Path(x["file"]).stem)
        means = " · ".join(v for v in (x.get("why") or "", x.get("author") or "", x.get("licence") or "") if v)
        options.append({"id": _slug_id(f"track-{Path(x['file']).stem}", taken), "label": title, "means": means,
                        "recommended": n == rec_track and not trending, "default": n == rec_track and not trending,
                        "media": [{"src": x["file"], "caption": title}]})
    sections.append({"id": "music", "kind": "one", "title": t("music"), "hint": t("music_hint"), "options": options,
                     "note": t("note")})
    data = {"page": PAGE, "lang": pack.get("lang") or "en", "title": t("title", title=pack["title"]),
            "lede": t("lede"), "run": choices.run_ref(run), "date": choices.today(), "sections": sections, "total": None,
            "plugin": {"pack": pack_rel, "options": opts_rel,
                       "styles": {o["id"]: s for o, s in zip(sections_of(sections, "style"), styles)},
                       "voices": {o["id"]: v for o, v in zip(sections_of(sections, "voice"), voices)},
                       "tracks": {o["id"]: x for o, x in zip(sections_of(sections, "music")[1 + bool(trending):], tracks)},
                       "trending": trending}}
    return data


def sections_of(sections: list[dict], sid: str) -> list[dict]:
    return next((s["options"] for s in sections if s["id"] == sid), [])


def build(run: RunFolder, options_file: str | None = None) -> dict:
    data = page_json(run, options_file)
    return choices.build(run, data, pack=data["plugin"]["pack"], options=data["plugin"]["options"])


# --- the picks -----------------------------------------------------------------------------------------------

def take(run: RunFolder, *, file: Path | None = None, text: Path | None = None, got: dict | None = None) -> dict:
    """The picks into `03_wip/taste_vNN.json`, and the next pack version with `taste` filled in (`by: user`); `got`:
    answers already read (`choices.from_docs`, the run page's)."""
    got = got or choices.read(run, PAGE, file=file, text=text)
    a, plugin = got["answers"], got["data"]["plugin"]
    style = voice = None
    if "style" in a and a["style"]["choice"]:
        s = plugin["styles"][a["style"]["choice"]]
        style = str(s.get("label") or s["id"])
    if "voice" in a and a["voice"]["choice"]:
        v = plugin["voices"][a["voice"]["choice"]]
        voice = {"voice_id": v["voice_id"], "name": v.get("name"), "source": v.get("source") or "library"}
    pick = a["music"]["choice"] or NO_TRACK
    if pick == NO_TRACK:
        music = {"kind": "none"}
    elif pick == TRENDING:
        music = {"kind": "trending", "name": plugin["trending"]["name"], "link": plugin["trending"].get("link")}
    else:
        x = plugin["tracks"][pick]
        music = {"kind": "track", "file": x["file"], "title": x.get("title") or Path(x["file"]).stem,
                 "licence": x.get("licence")}
    notes = {k: v["note"] for k, v in a.items() if v["note"]}
    line_notes = (a.get("script") or {}).get("notes") or {}
    body = {"style": style, "voice": voice, "music": music, "line_notes": line_notes, "notes": notes,
            "pack": plugin["pack"]}
    picks = choices.record(run, PAGE, STEM, body, got)
    pack_rel = _next_pack(run, plugin["pack"], style, voice, music, picks)
    return {"file": picks, "pack": pack_rel, "picks": body, "from": got["from"], "source": got["source"],
            "done": got["done"], "folder": got["folder"]}


def taste_field(style, voice, music) -> dict:
    """The pack's `taste` from the picks (the pack's schema: strings, `by: user`)."""
    words = None
    if music["kind"] == "track":
        words = music["title"]
    elif music["kind"] == "trending":
        words = f"trending: {music['name']}"
    return {"style": style, "voice": f"{voice['name']} ({voice['voice_id']})" if voice else None, "music": words,
            "by": "user", "why": None}


def _next_pack(run: RunFolder, pack_rel: str, style, voice, music, picks: str) -> str | None:
    """The next pack version: the latest pack as it is, its `taste` the user's picks. None when the latest pack is
    not the one the page was built from (a newer recipe since): then the agent copies the picks into it."""
    latest = run.latest(WIP, "pack", "json")
    if latest is None or latest.relative_to(run.path).as_posix() != pack_rel:
        return None
    pack = json.loads(latest.read_text(encoding="utf-8-sig"))
    pack["taste"] = taste_field(style, voice, music)
    out = run.next_version(WIP, "pack", "json")
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=2)
    rel = out.relative_to(run.path).as_posix()
    manifest.record(run, rel, WIP, "tm organic decisions --page taste", parent=picks)
    return rel
