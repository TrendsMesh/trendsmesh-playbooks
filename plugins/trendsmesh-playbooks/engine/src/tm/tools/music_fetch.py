"""Music for the edit (organic video's D2 and G1, issue 89): a Mixkit track found, fetched and indexed, and the tracks
offered copied into the run.

    tm tool music_fetch --run RUN --search "<words>" [--offer ID ...] [--json]
    tm tool music_fetch --run RUN --mixkit ID [--page URL] [--yes] [--json]
    tm tool music_fetch --run RUN --copy TRACK [--copy TRACK ...] [--json]

- `--search`: the tracks Mixkit's search lists for the words (`https://mixkit.co/free-stock-music/discover/<words>/`):
  id, title, author, length, tags (its moods among them) and the preview, which is the track's own file. Free.
  With `--offer ID` (again for each, issue #142): the tracks D2 offers, each preview (the track's own file) copied
  into the run, `02_research/music/mixkit-<title>-<id>.mp3`, tagged, with its licence and source in the manifest,
  so the style, voice and music page plays them with their licence line and no question is asked first. Picking one
  is the user's yes: `tm page decision taste --record` (`organic_pages.taste.take`) files it into the music library
  and indexes it (`file_picked`); a track not picked stays only in the run.
- `--mixkit ID`: the track's card on the Mixkit page that lists it (`--page`, a mixkit.co address; default the search
  page the track was found on, or Mixkit's music front page) and its file's size: title, author, length, size and
  licence (the Mixkit Stock Music Free License, which allows commercial use without credit). Nothing is downloaded:
  it stops (exit 2) so the user is asked. With `--yes`, after the user's yes, the file (Mixkit's fixed address,
  `assets.mixkit.co/music/<id>/<id>.mp3`, no account) is downloaded into the channel's music folder as
  `mixkit-<title>-<id>.mp3`, tagged with its title, author, moods, licence and source, and the folder is indexed
  (`tm tool music_index`: the run's next `02_research/music_index_vNN.csv`, every field filled). A track already
  there is never downloaded again.
- `--copy TRACK`: tracks of the run's music folders (each by its name, or a path; `folders`) copied into the run,
  `02_research/music/<name>` (the same file again is reused, never overwritten): the 2 to 3 offered at D2, which the
  style, voice and music page plays (a page plays only the run's own files), and so the edit's `music.src` names the
  picked one in the run.

The channel's music folder is the channel profile's `music.folder` (a path, or one inside the workspace), else
`library/channels/<channel>/music/`. A run without a channel (Create an ad, issue #144) keeps a fetched track in its
`03_wip/audio/`, and, when the run has a brand, in the brand's `library/brands/<slug>/music/` too, which is indexed,
so a later run of the brand finds it (`channel_folder`). `folders` lists every music folder of the workspace, the
run's own first: the other channels' and brands' folders give only free-licence tracks (Mixkit's: #148 line 23, a
channel's own or bought tracks stay with it). Only mixkit.co is read; only the track's mp3 on assets.mixkit.co is
downloaded.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from tm import __version__, brand, config, manifest, state, trend_spool
from tm.tools import _common as c
from tm.tools import music_index

FRONT = "https://mixkit.co/free-stock-music/"
SEARCH = "https://mixkit.co/free-stock-music/discover/{words}/"
FILE = "https://assets.mixkit.co/music/{id}/{id}.mp3"
LICENCE = "Mixkit Stock Music Free License"
LICENCE_URL = "https://mixkit.co/license/#musicFree"
RUN_MUSIC = "02_research/music"
RUN_AUDIO = "03_wip/audio"            # a run without a channel keeps its fetched track here (issue #144)
OFFER_SOURCE = "tm tool music_fetch --offer"
FETCH_SOURCE = "tm tool music_fetch --mixkit"
LICENCE_LINE = f"{LICENCE} ({LICENCE_URL}): free for commercial use, in organic videos and ads, no credit needed"
MAX_MB = 60
USER_AGENT = f"trendsmesh-playbooks/{__version__} (music for an edit; one track after the user's yes)"
TIMEOUT = 60


def _get(url: str) -> str:
    import requests

    answer = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if answer.status_code != 200:
        raise c.ToolError(f"Mixkit answered {answer.status_code} for {url}. Nothing was downloaded.")
    return answer.text


def _size(url: str) -> int | None:
    import requests

    answer = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
    if answer.status_code != 200 or not answer.headers.get("Content-Type", "").startswith("audio/"):
        raise c.ToolError(f"Mixkit has no track file at {url} (it answered {answer.status_code}). Nothing was "
                          "downloaded.")
    size = answer.headers.get("Content-Length")
    return int(size) if size and size.isdigit() else None


def _download(url: str, dest: Path) -> None:
    import requests

    with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True) as answer:
        if answer.status_code != 200 or not answer.headers.get("Content-Type", "").startswith("audio/"):
            raise c.ToolError(f"Mixkit answered {answer.status_code} for {url}. Nothing was kept.")
        got = 0
        with dest.open("wb") as fh:
            for chunk in answer.iter_content(1 << 16):
                got += len(chunk)
                if got > MAX_MB * 1_000_000:
                    raise c.ToolError(f"The track is over {MAX_MB} MB, which no Mixkit track is. Nothing was kept.")
                fh.write(chunk)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def cards(page: str) -> list[dict]:
    """The music cards of a Mixkit page: [{id, title, author, length, tags, moods, preview}]."""
    out = []
    for chunk in re.split(r'<div class="item-grid-card[ "]', page)[1:]:
        found = re.search(r'data-audio-player-item-id-value="(\d+)"', chunk)
        title = re.search(r'class="item-grid-card__title"[^>]*>(.*?)</h2>', chunk, re.S)
        if not (found and title):
            continue
        author = re.search(r'class="item-grid-music-preview__author"[^>]*>(.*?)</p>', chunk, re.S)
        links = re.findall(r'<a class="meta-links__link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
        length = re.search(r">\s*(\d{1,2}:\d{2})\s*<", chunk)
        preview = re.search(r'data-audio-player-preview-url-value="([^"]+)"', chunk)
        tid = found.group(1)
        out.append({"id": tid, "title": _text(title.group(1)),
                    "author": re.sub(r"^by\s+", "", _text(author.group(1))) if author else "",
                    "length": length.group(1) if length else "", "tags": [_text(t) for _, t in links],
                    "moods": [_text(t) for href, t in links if "/mood/" in href],
                    "preview": preview.group(1) if preview else FILE.format(id=tid)})
    return out


def _mixkit_page(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() not in ("mixkit.co", "www.mixkit.co"):
        raise c.ToolError(f"--page must be a Mixkit page (https://mixkit.co/...), not {url}. Nothing was read.")
    return url


def _words_slug(words: str) -> str:
    plain = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    if not slug:
        raise c.ToolError(f"--search {words!r} needs words in Latin letters (Mixkit searches in English).")
    return slug


def _channel(run) -> str | None:
    import json

    found = (state.load(run).organic or {}).get("channel")
    try:
        said = json.loads((run.path / "00_raw" / "proposal.json").read_text(encoding="utf-8-sig"))
        found = said.get("channel") or found
    except (OSError, ValueError, AttributeError):
        pass
    if not found:
        channels = config.load(run).get("channels") if (run.path / config.FILE).is_file() else None
        found = channels[0] if isinstance(channels, list) and channels else None
    return found if isinstance(found, str) and found.strip() else None


def _channel_music(workspace: Path, name: str) -> Path:
    """A channel's music folder: its profile's `music.folder`, else `library/channels/<key>/music/`."""
    try:
        profile = brand.latest(workspace, name, kind="channel") or {}
    except ValueError as exc:
        raise c.ToolError(str(exc)) from None
    folder = (profile.get("music") or {}).get("folder") if isinstance(profile.get("music"), dict) else None
    if isinstance(folder, str) and folder.strip():
        path = Path(folder).expanduser()
        return path if path.is_absolute() else workspace / path
    return workspace / brand.CHANNEL_DIR / brand.channel_key(name) / "music"


def run_brand(run) -> str | None:
    """The run's brand (issue #144): the name `tm tool site brand` read (`02_research/brand_vNN.json` `brand`), else
    config.yaml `brand.name`, else the name in `brand.url`'s address (linear.app is linear); None without one."""
    import json

    latest = run.latest("02_research", "brand", "json")
    try:
        said = json.loads(latest.read_text(encoding="utf-8-sig")).get("brand") if latest else None
    except (OSError, ValueError, AttributeError):
        said = None
    cfg = config.load(run) if (run.path / config.FILE).is_file() else {}
    given = cfg.get("brand") if isinstance(cfg.get("brand"), dict) else {}
    url = given.get("url")
    if not said and isinstance(url, str) and url.strip():
        from tm.tools import site

        said = site.brand_name(url)
    said = said or given.get("name")
    return said.strip() if isinstance(said, str) and said.strip() else None


def brand_music(workspace: Path, name: str) -> Path:
    return workspace / brand.DIR / brand.channel_key(name) / "music"


def channel_folder(run) -> Path:
    """The run's own music folder (the module docstring): the channel's; without a channel, the brand's; without
    either, the run's 03_wip/audio/."""
    workspace = trend_spool.workspace_of(run)
    name = _channel(run)
    if name is not None:
        return _channel_music(workspace, name)
    owner = run_brand(run)
    return brand_music(workspace, owner) if owner else run.path / RUN_AUDIO


def folders(run) -> list[dict]:
    """Every music folder of the workspace, `{path, channel, own}`, the run's own first (its channel's; without a
    channel, its brand's and then 03_wip/audio/), then each other channel's (`library/channels/*`, or its profile's
    `music.folder`) and brand's (`library/brands/*/music/`), labelled with its channel or brand key. Only folders
    that exist, except the run's own."""
    workspace = trend_spool.workspace_of(run)
    name = _channel(run)
    own_key = brand.channel_key(name) if name else (brand.channel_key(run_brand(run)) if run_brand(run) else "")
    out = [{"path": channel_folder(run), "channel": own_key, "own": True}]
    if name is None and run_brand(run):
        out.append({"path": run.path / RUN_AUDIO, "channel": own_key, "own": True})
    seen = {p["path"].resolve() for p in out}
    for root, of in ((workspace / brand.CHANNEL_DIR, lambda d: _channel_music(workspace, d.name)),
                     (workspace / brand.DIR, lambda d: d / "music")):
        for d in sorted(x for x in root.iterdir() if x.is_dir()) if root.is_dir() else ():
            try:
                folder = of(d)
            except c.ToolError:      # another channel's damaged profile: its default folder
                folder = d / "music"
            if folder.is_dir() and folder.resolve() not in seen:
                seen.add(folder.resolve())
                out.append({"path": folder, "channel": d.name, "own": False})
    return out


def free(path: Path) -> bool:
    """A track under the free licence (Mixkit's, its tags say), which may be offered to any channel."""
    try:
        tags = music_index._probe(path)["tags"]
    except (subprocess.CalledProcessError, ValueError, OSError):
        return False
    return LICENCE.casefold() in " ".join(str(tags.get(k, "")) for k in ("licence", "copyright")).casefold()


def _shown(path: Path, run) -> str:
    """A path as the user knows it: inside the workspace relative to it, else as it is."""
    try:
        return path.resolve().relative_to(trend_spool.workspace_of(run).resolve()).as_posix()
    except ValueError:
        return str(path)


def _track(card: dict, size: int | None) -> dict:
    return {"id": card["id"], "title": card["title"], "author": card["author"], "length": card["length"],
            "moods": card["moods"], "tags": card["tags"],
            "size_mb": round(size / 1_000_000, 1) if size is not None else None,
            "licence": LICENCE, "licence_url": LICENCE_URL, "source": FILE.format(id=card["id"])}


def _file_name(card: dict) -> str:
    plain = unicodedata.normalize("NFKD", card["title"]).encode("ascii", "ignore").decode("ascii").lower()
    return f"mixkit-{re.sub(r'[^a-z0-9]+', '-', plain).strip('-') or 'track'}-{card['id']}.mp3"


def _tag(src: Path, dest: Path, track: dict) -> None:
    meta = {"title": track["title"], "artist": track["author"], "genre": ", ".join(track["moods"] or track["tags"]),
            "licence": track["licence"], "copyright": f"{LICENCE} ({LICENCE_URL})", "source": track["source"]}
    argv = [c.ffmpeg_bin(), "-nostdin", "-v", "error", "-i", c.media(src), "-map", "0:a", "-c", "copy",
            "-id3v2_version", "3"]
    for key, value in meta.items():
        argv += ["-metadata", f"{key}={value}"]
    subprocess.run([*argv, "-f", "mp3", c.media(dest)], capture_output=True, check=True)


def _get_track(track: dict, dest: Path) -> None:
    """The track's file into `dest`, tagged (`_tag`), never a part file left; a file already there is kept."""
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f".{dest.name}.part")
    try:
        _download(track["source"], part)
        _tag(part, dest, track)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        part.unlink(missing_ok=True)


def _licence_params(track: dict) -> dict:
    return {"mixkit": track["id"], "title": track["title"], "author": track["author"], "licence": LICENCE,
            "licence_url": LICENCE_URL, "source": track["source"]}


def offer(run, found: list[dict], ids: list[str]) -> list[dict]:
    """The offered tracks' previews (each the track's own file) copied into the run's 02_research/music/, tagged, with
    the licence in the manifest (issue #142): one row per track, `{id, title, author, length, file, licence,
    licence_line, source}`."""
    by_id = {t["id"]: t for t in found}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise c.ToolError(f"--offer {', '.join(missing)}: not among the tracks this search lists "
                          f"({', '.join(by_id) or 'none'}). Nothing was copied.")
    out = []
    for tid in dict.fromkeys(ids):
        track = by_id[tid]
        dest = run.path / RUN_MUSIC / _file_name(track)
        new = not dest.is_file()
        _get_track(track, dest)
        if new:
            c.record(run, dest, OFFER_SOURCE, None, params=_licence_params(track), cost="free")
        out.append({"id": tid, "title": track["title"], "author": track["author"], "length": track["length"],
                    "file": c.rel(run, dest), "licence": LICENCE, "licence_line": LICENCE_LINE,
                    "source": track["source"]})
    return out


def search(run, words: str, offers: list[str] | None = None) -> tuple[dict, str]:
    page = SEARCH.format(words=_words_slug(words))
    found = [_track(card, None) for card in cards(_get(page))]
    lines = [f"{t['id']}: {t['title']} by {t['author']}, {t['length']} ({', '.join(t['tags'])}) {t['source']}"
             for t in found]
    text = (f"{len(found)} Mixkit track(s) for {words!r} on {page}:\n" + "\n".join(lines) if found
            else f"Mixkit lists no track for {words!r} ({page}): try other words in English.")
    payload: dict = {"page": page, "tracks": found}
    if offers:
        payload["offered"] = offer(run, found, offers)
        payload["outputs"] = [t["file"] for t in payload["offered"]]
        text += ("\nOffered, in the run with their licence (" + LICENCE_LINE + "): "
                 + ", ".join(t["file"] for t in payload["offered"])
                 + ". Put them on the style, voice and music page; the user's pick is filed into the library when "
                   "the page's decision is recorded.")
    return payload, text


def file_picked(run, rel: str) -> dict | None:
    """The track the user picked at D2 (`taste.take`), when it is a Mixkit offer of this run (`--offer`): copied into
    the run's own music folder (`channel_folder`) and that folder indexed, as `--mixkit --yes` does; `{file, index}`
    (the file workspace-relative), or None for any other track (it is in the library already, or the user's own)."""
    rel = str(rel).replace("\\", "/")
    if not any(r["file"] == rel and r["source"] == OFFER_SOURCE for r in manifest.rows(run)):
        return None
    src = run.path / rel
    if not src.is_file():
        return None
    folder = channel_folder(run)
    dest = folder / src.name
    if not dest.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f".{dest.name}.part"
        shutil.copyfile(src, part)
        c.replace(part, dest)
    out, _, _ = music_index.index(run, folder)
    return {"file": _shown(dest, run), "index": c.rel(run, out)}


def fetch(run, tid: str, page: str | None, yes: bool) -> tuple[dict, str, int]:
    if not re.fullmatch(r"\d{1,7}", tid):
        raise c.ToolError(f"--mixkit takes the track's number (e.g. 580), not {tid!r}.")
    page = _mixkit_page(page) if page else FRONT
    card = next((x for x in cards(_get(page)) if x["id"] == tid), None)
    if card is None:
        raise c.ToolStop(f"Track {tid} is not on {page}: give --page, the Mixkit page that lists it (the search page "
                         "--search printed, or a mood page). Nothing was downloaded.")
    track = _track(card, _size(FILE.format(id=tid)))
    channel = _channel(run)
    owner = None if channel else run_brand(run)
    folder = channel_folder(run) if channel else run.path / RUN_AUDIO      # where the track goes first
    library = brand_music(trend_spool.workspace_of(run), owner) if owner else None
    dest = folder / _file_name(card)
    said = f"{track['title']} by {track['author']}, {track['length']}, {track['size_mb']} MB, {LICENCE_LINE}"
    where = (f"{_shown(folder, run)}, and the folder is indexed" if channel else
             f"the run's {RUN_AUDIO}/" + (f" and the brand's music library {_shown(library, run)}, which is indexed"
                                         if library else " (the run names no brand, so no library keeps it)"))
    if not yes:
        return ({"track": track, "folder": _shown(folder, run), **({"library": _shown(library, run)} if library else {})},
                f"{said}. Nothing was downloaded. Ask the user; after their yes run again with --yes: it goes into "
                f"{where}.", 2)
    new = not dest.is_file()
    _get_track(track, dest)
    shown = _shown if channel else (lambda path, run: c.rel(run, path))   # a run's own file: run-relative
    payload = {"track": track, "file": shown(dest, run), "folder": shown(folder, run)}
    if not channel and new:      # the run's own copy: its licence in the manifest (issue #144)
        c.record(run, dest, FETCH_SOURCE, None, params=_licence_params(track), cost="free")
    indexed = folder if channel else library
    if library is not None:
        kept = library / dest.name
        if not kept.is_file():
            library.mkdir(parents=True, exist_ok=True)
            part = library / f".{dest.name}.part"
            shutil.copyfile(dest, part)
            c.replace(part, kept)
        payload["library"] = _shown(kept, run)
    text = f"Fetched {said} into {payload['file']}"
    if indexed is not None:
        out, rows, _ = music_index.index(run, indexed)
        payload.update(index=c.rel(run, out), outputs=[c.rel(run, out)])
        text += (f"{' and ' + payload['library'] if library else ''}, and indexed {_shown(indexed, run)} ({len(rows)} "
                 f"tracks) into {c.rel(run, out)}")
    else:
        payload["outputs"] = [payload["file"]]
    if channel:
        text += f". To offer it: tm tool music_fetch --run <run> --copy {dest.name}."
    else:
        text += f". The edit's music names {payload['file']}."
    return payload, text, 0


def _source(run, track: str) -> tuple[Path, str | None]:
    """(the track's file, the other channel or brand it comes from, None for the run's own): the run's own folders
    first, then the workspace path, then every other folder, where only a free-licence track may be taken."""
    places = folders(run)
    given = Path(track).expanduser()
    if given.is_absolute():
        return given, None
    for f in (x for x in places if x["own"]):
        if (f["path"] / given).is_file():
            return f["path"] / given, None
    if (trend_spool.workspace_of(run) / given).is_file():
        return trend_spool.workspace_of(run) / given, None
    others = [f for f in places if not f["own"] and (f["path"] / given).is_file()]
    for f in others:
        if free(f["path"] / given):
            return f["path"] / given, f["channel"]
    if others:
        raise c.ToolError(f"{track} is in {others[0]['channel']}'s music, and only free-licence tracks ({LICENCE}) are "
                          f"offered across channels: a channel's own or bought tracks stay with it. Pick another "
                          "track, or fetch one (tm tool music_fetch --search).")
    raise c.ToolError(f"There is no track {track} in the channel's music folder {_shown(places[0]['path'], run)} or "
                      "any other music folder: give its name as the index lists it, or fetch one first (tm tool "
                      "music_fetch --mixkit <id>).")


def copy(run, track: str) -> tuple[str, str | None]:
    """One track of the run's music folders copied into the run: (its run-relative path, the other channel it comes
    from or None)."""
    src, other = _source(run, track)
    dest = run.path / RUN_MUSIC / src.name
    if dest.is_file() and dest.read_bytes() != src.read_bytes():
        dest = run.unique_path(dest)
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(f".{dest.name}.part")
        shutil.copyfile(src, part)
        c.replace(part, dest)
        c.record(run, dest, "tm tool music_fetch --copy", src.name,
                 params={"from": _shown(src, run), **({"channel": other} if other else {})}, cost="free")
    return c.rel(run, dest), other


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("music_fetch", "Music for the edit: a Mixkit track found, fetched after the user's yes, indexed; "
                 "the offered tracks copied into the run.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--search", help="words to search Mixkit's music for, in English")
    mode.add_argument("--mixkit", help="a Mixkit track's number: shown, and with --yes fetched")
    mode.add_argument("--copy", action="append", help="a track of the run's music folders to copy into the run "
                      "(again for each track offered); another channel's only under the free licence")
    p.add_argument("--offer", action="append", help="with --search: a listed track's number to offer at D2, copied into "
                   "the run with its licence (again for each)")
    p.add_argument("--page", help="the Mixkit page that lists the track (default: Mixkit's music front page)")
    p.add_argument("--yes", action="store_true", help="the user said yes: download the track")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    if a.offer and not a.search:
        raise c.ToolError("--offer takes the tracks of a search: tm tool music_fetch --run <run> --search \"<mood>\" "
                          "--offer <id> --offer <id>. Nothing was copied.")
    if a.search:
        payload, text = search(run, a.search, a.offer)
    elif a.copy:
        done = [copy(run, track) for track in a.copy]
        other = {rel: ch for rel, ch in done if ch}
        payload = {"outputs": [rel for rel, _ in done], **({"from": other} if other else {})}
        text = (f"Copied into the run: {', '.join(payload['outputs'])}. The page offers them; the edit's music.src is "
                "the picked one." + "".join(f" {rel} is from {ch}'s music (free licence)." for rel, ch in other.items()))
    else:
        payload, text, code = fetch(run, a.mixkit, a.page, a.yes)
        if code == 2:
            import json

            print(json.dumps({"status": "stop", **payload, "message": text}, ensure_ascii=False) if a.json else text)
            return 2
    return c.finish(a, {"tool": "music_fetch", **payload}, text)


if __name__ == "__main__":
    raise SystemExit(main())
